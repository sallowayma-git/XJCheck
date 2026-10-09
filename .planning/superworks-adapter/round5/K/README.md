# 第五轮 K：R-DUPLICATE-PAIR 误报、范围端点覆盖、端子排跨接标记

范围：只改 `src/dwg_audit/audit/rules.py` 与新增 `tests/unit/test_superworks_round5_rules.py`。未改 superworks_extractor.py、superworks_semantics.py 等生产端文件，未提交，未删除文件，未做全量回放。离线数据为第四轮 pairs（`.tmp/superworks_round4_full`）与基线（`.tmp/superworks_baseline_timed`），离线调用的是 `src` 中的真实规则函数，未使用猴子补丁。工具与输出在 `round5/K/tools/` 与 `round5/K/eval_*.json`。

## 1. 修改函数（rules.py 当前行号）

| 位置 | 函数 | 项 | 改动 |
|---|---|---|---|
| 95 | `_bridge_covered_terminal_identities` | K2 | 去掉仅限 bridge claim 的过滤。bridge claim 仍两侧展开范围（G5 原行为）；非 bridge pair 展开其左值范围。 |
| 785–799 | `_is_terminal_strip_bridge_claim` | K3 | `evidence["strip_connection_jumper"] is True` 时返回 True。字段不存在时行为不变。 |
| 1262 | `_run_many_to_one` 中的 `effective_lefts` | K2 | 调用点不变，仅注释更新。 |
| 1892 | `_is_authoritative_schematic_kk_component_duplicate` | K1 | schematic 身份改用 `_authoritative_schematic_role_identity`。 |
| 1924 | `_authoritative_schematic_role_identity`（新增） | K1 | SW 连接线（`component_submode == superworks_connect_line_port`）返回 None；其余委托 `_authoritative_schematic_inline_component_identity`。 |
| 1937 | `_is_authoritative_schematic_small_port_component_duplicate` | K1 | 同上，同类函数同步修改。 |

未改动：`_authoritative_schematic_inline_component_identity`（2163，G3 对 SW 连接线返回身份的行为保留，供 backplate 路径使用）；`_is_authoritative_schematic_inline_backplate_endpoint_group`（2116，G3 去重保留）；`_terminal_header_table_shared_endpoint_info`（3968，未实施相邻列放宽）。

## 2. K1–K3 实施情况

- **K1（R-DUPLICATE-PAIR）**：schematic 身份只取原理图 inline pair。SW 连接线只计入 component-diagram 角色（`_authoritative_component_diagram_identity` 原样保留）。G3 的 schematic 计数问题由此消除。
- **K2（R-MANY-TO-ONE 范围覆盖）**：组内非 bridge pair 的左值范围（如 `1-7UD20~21`）覆盖其成员（如 `1-7UD21`），两者不再计为两个左值。复用 `_terminal_range_members`（含 `_TERMINAL_RANGE_DASHED_PATTERN`）。bridge claim 的两侧展开保持不变。
  - 实施过程中曾尝试非 bridge pair 的左右两侧都展开，离线结果相同（96），但右侧范围会把两个不同左值视为同一端，故收窄为仅左侧。
- **K3（端子排跨接）**：`strip_connection_jumper is True` 的 Pair 视为桥接 claim，因此不计入 effective_lefts。`jumper_target` 未参与判定（题目只要求布尔标记）。第四轮数据中该字段不存在，离线无法直接验证，见第 5 节。

## 3. 测试

- 新增 `tests/unit/test_superworks_round5_rules.py`：15 项，K1 5 项、K2 5 项、K3 5 项。每项各有正例与反例，反例包括：普通重复仍报（K1）、非成员左值仍报（K2）、无字段或 False 不生效（K3）、跨接不掩盖普通配线间的真实冲突（K3）。
- 既有 `tests/unit/test_superworks_round4_rules.py`：31 项全部通过（含 G3 backplate 去重、G5 桥接覆盖）。
- 全量 `pytest tests/unit -q`：**1664 passed, 1 skipped**。（其中含另一子代理新增的 round4/round5 producer 测试，本轮未修改。）
- 变异检查（`round5/K/tools/mutate_check.py`，进程内还原各项改动）：还原 K1、K2、K3 各自都使其 2 个正例失败，说明测试覆盖了改动点。

## 4. 离线计数（第四轮 pairs，live src）

| 规则 | 修改前 | 修改后 | 说明 |
|---|---:|---:|---|
| R-DUPLICATE-PAIR | 68 | **0** | K1 |
| R-ONE-TO-MANY | 68 | 68 | 未变（生产端问题，未处理） |
| R-MANY-TO-ONE | 110 | **96** | K2 消除 14 条；K3 数据侧 0 条 |
| R-CROSS-PAGE-CONFLICT | 38（原始 runner 输出）/ 3（issues.parquet，经 cluster 合并） | 38 / 3 | 未变（K2/K3 不影响 cross） |

基线保留核对：
- R-MANY-TO-ONE 基线 13 条：**13/13 保留**（p015/p021/p050/p071/p075 GND；p038/p049 KD26；p039 1-2GD3、1-2n221、3-2n221、KD1、KD6；p040 1ZK-3）。
- R-CROSS-PAGE-CONFLICT 基线 3 条：**3/3 保留**（p050 1n/NCK305-5→1CD3；p065 NCK305-1@c0→1C1D1；p066 NCK305-5@c0→1C2D1）。

## 5. R-MANY-TO-ONE 剩余按桶（H 第 3 节分桶，同口径键）

| 桶 | 修改前 | 修改后 | 说明 |
|---|---:|---:|---|
| 1 端子表相邻列（p074 48，p014/041/042 各 1） | 51 | 51 | K3 数据侧未触发，见下 |
| 2 范围与成员（p027–p034） | 15 | **1** | 消除 14 条。剩余 p027 `3-4QD22` 不含范围（左值 `�Ͻ�3-4XD513` 含 GBK 乱码前缀），不属于 K2 覆盖范围；H 文档把它归入桶 2 有误 |
| 3 同一端子四视图不同逻辑名（p016–p021） | 10 | 10 | 未处理（待复核） |
| 4 背板 + 表格 + 线网范围（p022–p024） | 5 | 5 | 余下为背板独立来源 `1n1423`，与范围无关，待复核 |
| 5 背板与线网（p061） | 4 | 4 | 未处理（待复核，倾向真实） |
| 其余 8 桶 | 12 | 12 | 未变 |
| 基线 13 条 | 13 | 13 | 全部保留 |

合计 110 → 96。

### K3 的离线验证结论（重要）

第四轮数据中没有 `strip_connection_jumper` 字段，因此按题目要求从原始文字推导，结果如下：

1. **字面推导（端子文字以 `&` 开头）**：标记 0 条，m2o 仍为 96。原因是 S0016 相关的 table_mapping 配对，其端子文字（如 T3427 `1-25U3D9`、T3523 `1-25U3D9`）本身不带 `&`；`sw_strip_rows.parquet` 的 connections 中也没有 `&` 值；以 `&` 开头的整串文字只在 S0013 出现（如 `& 1-25ZKK5-2`）。
2. **S0016 的 `&` 形态**：`texts.parquet` 中 S0016 共 92 个 `&`，全部是独立的单字符文字，紧邻几乎每个端子单元格（同一行的多个端子两侧都有 `&`）。
3. **几何相邻敏感性（仅测量，未采用）**：把"同行 |dy|<=0.5、0<|dx|<=20 的独立 `&` 文字"视为跨接，标记 2596 条配对，m2o 降到 38（基线仍 13/13）。但 `&` 不是跨接的特异信号，过度标记，不能采用。

因此 **K3 在规则侧已就绪，但第四轮数据上无法离线验证其对 bucket 1（51 条）的效果**。消除这 51 条需要生产端（端子排解析）在能确认"该 `&` 属于该端子的跨接连接"时写入 `evidence.strip_connection_jumper=True`（并建议写 `jumper_target`）。生产端需要先确定 `&` 与连接文字的归属规则（S0013 的整串形态与 S0016 的独立字符形态不同）。

## 6. 与任务说明的偏差与风险

- H 文档对桶 2 的计数（15 条全部为范围问题）不准确：实际 14 条为范围问题，p027 `3-4QD22` 为另一类。
- 题目预期"桶 2 的 15 条消除"，实际消除 14 条，原因同上。
- K3 的规则效果尚未在真实数据上验证，见第 5 节。H 文档"都来自带 & 的跨接文字"的说法在第四轮 texts 中无法直接复现（`&` 为独立文字）。
- K1 同时修改了 small-port 版本的函数。对 SW 连接线配对，small-port 身份恒为 None（SW 连接线不具备 small-port 身份），因此该函数对这类配对的返回值修改前后相同。本轮未对 small-port 分支单独计数。
- H 第 1 节提到 r3 形态数据上修复可能使 m2o 从 376 变为 414（SW 连接线 + table_mapping 组的 G3 豁免被收回）。本轮只在 r4 数据上核对，未核对 r3 数据。

## 7. 复现

```
cd F:/workspace/XJToolkit
PYTHONIOENCODING=utf-8 python .planning/superworks-adapter/round5/K/tools/k_eval.py <label>      # 写 round5/K/eval_<label>.json
PYTHONIOENCODING=utf-8 python .planning/superworks-adapter/round5/K/tools/k_jumper_sens.py raw adj   # K3 推导敏感性
PYTHONIOENCODING=utf-8 python .planning/superworks-adapter/round5/K/tools/mutate_check.py          # 变异检查
PYTHONIOENCODING=utf-8 python -m pytest tests/unit/test_superworks_round5_rules.py -q
```

`tools/` 中的 `load.py`、`offline_all.py`、`m2o_*_test.py` 等为从 `round4/H/tools` 只读复制的脚本，本轮未用于出具结论；`k_eval.py` 为本轮新增，与 `round4/H/m2o_buckets.py` 共用桶键函数（只读导入）。
