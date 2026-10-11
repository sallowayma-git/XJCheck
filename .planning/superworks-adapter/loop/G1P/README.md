# G1P：未登记 SYMB2 块引脚的装置内部连接（只计覆盖，不建配对）

分支 superworks-loop，基线 HEAD=556e999。未 commit、未 push。未改 V2 模块与 `symbol_port_proposal.py`，未加 PDF/OCR，判定只用几何与标签相等，未做项目、句柄或取值特判，未整体豁免 SuperWORKS 来源。

## 0. 结论

1. **新增 131 条装置内部链接**（10 项目，`source='unregistered_symb2_pin'`），来自 GAP-1 的 A 类（装置端子单端导线止于未登记 SYMB2 块的 TERMPOINT）中标签一致的部分。链接只计覆盖：不建配对，不改 issue。
2. **覆盖（10 项目，eligible 8645）**：合计口径 7463（86.33%）→ **7591（87.81%）**，+128 端口（+1.48 pp）；含内部口径 7250（83.86%）→ 7381（85.38%），+131（差 3 个端口原已被延续覆盖，见第 3 节）。严格口径与含延续口径不变。
3. **已有链接 0 条丢失**：1251 条 SW 元件内部链接全部保留，无歧义冲突（`excluded:multiple_internal_wires` 为 0）。
4. **pairs / issues 不变**：10 项目 20134 条配对全列逐行相同；10 条 issue 逐条相同。
5. **排除原因**：10 项目 509 条装置端子单端导线中，131 条建链，121 条远端块的标签与装置标签不同（外部元件），257 条远端没有未登记块的 TERMPOINT。标签无法解析、多块候选、相关标签（`1-1n` 与 `1n`）均为 0。
6. **目视**：正例 30 例，30/30 为本装置内部元件（开关、继电器或本装置图形块的引脚）；负例 6 例，6/6 为标签不同的外部元件，正确排除。
7. **耗时**：8 项目上新增步骤的增量很小（第 6 节）。
8. **与 GAP-1 的两处不一致（需 GAP 复核，本切片未修改 GAP 文档）**：
   - GAP-1 写“导线端点与块引脚顶点重合（0.00）”。本切片 131/131 例的远端都恰好位于 TERMPOINT 段的中点（段长 1.000，距两端各 0.500），即块的连接点。这与既有端口接触容差（0.6 倍段长）一致。
   - GAP-1 写“标签不一致 0 例，无法解析 640 例”。本切片 10 项目中，块标签与装置标签不同的有 121 例（如 `2-1ZKK`、`1KLP16`、`1ZKK1`，DXF 核对为 MTEXT 标签，属其它元件），无法解析的为 0 例。GAP 的文字表可能未覆盖 MTEXT。因此 GAP-1 的 +1851 估算不能直接采用：10 项目中块端单端导线 252 条，标签一致的只占 52%（131/252）。

## 1. 规则

**收集（已打开文档，不二次读 DXF）**，`src/dwg_audit/extract/superworks_semantics.py`：

- `walk()` 中，凡 INSERT 带 `LD_SYMB2_LABEL` 且无 `LD_SYMB2_SPECIAL`，记为未登记块 `data.unregistered_symb2`：记录句柄、实例路径、标签（`text_ref` 解析，即 walk 已得到的标签）、标签是否可解析、标签互指是否成立，标签互指是否成立（只记录，不作门槛）；以及块内全部 `LD_SYMB1LIB_TERMPOINT` 的两端点（经实例变换后的 WCS）。
- 未登记块**不进入** `symbols`、`ports`、`part_instances`，不参与配对与 issue。
- 每张图记录模型空间全部导线的两端点 `data.wire_endpoints[(file_id, 句柄)] = {side: (x, y)}`（与 `_wire_index` 同一集合，保证与接触点一致）。

**建链（`src/dwg_audit/audit/superworks_device_internal.py`）**：对装置端子的每条接触导线，若它在 SW 线组中无其它端口（单端导线）：

1. **远端端点**：导线线组成员的端点中，恰好出现一次（不与同组其它段共享，即非中间拐点）且不是本端子自己的接触点的那些点。
2. **块匹配**：远端端点与某未登记块的 TERMPOINT 端点距离 ≤ 0.6 × 该段长度（与 SW 端口的接触容差一致）。同一文件中，若远端落在**恰好一个**块上，进入下一步；落在多个块上则 `multiple_blocks`。
3. **标签**：块标签规范化后与装置标签 casefold 相等 → 建链 `source='unregistered_symb2_pin'`。标签不同（相关标签另计）或无法解析 → 只计数，不建。
4. **歧义**：端子的满足条件的导线若多于一条（含 SW 元件候选），按原规则不建（`excluded:multiple_internal_wires`）。
5. 链接字段：`element_block_record_id`、`element_insert_handle`、`element_label`、远端与块端坐标（`far_x/far_y`、`pin_x/pin_y`）；`element_port_id` 为空（块不是端口）。`link_id` 为 `XDI:` 加 `(端子, 块记录, 句柄)` 的哈希。

已有的 SW 元件链接增加字段 `source='sw_internal_element'`，判定与 `link_id` 不变。

**统计口径变化**：`excluded:wire_no_other_port` 现在只计“单端导线未被未登记块建链”的数量（10 项目为 378 = 509 − 131）。单端导线的分解见 `unregistered:*`。

## 2. 改动文件

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/extract/superworks_semantics.py` | `SuperworksData` 新增 `unregistered_symb2`、`wire_endpoints`（`extend` 同步）；`walk()` 收集未登记块；`_unregistered_symb2()`；`extract_superworks_semantics` 建端点索引。 |
| `src/dwg_audit/audit/superworks_device_internal.py` | `build_device_internal_links` 新增参数 `unregistered`、`wire_endpoints`；`_PinIndex`、`_far_pin`；单端导线分支；返回 `unregistered_decisions`（每条单端导线的判定明细）。 |
| `src/dwg_audit/report/superworks_artifacts.py` | 传入未登记块与端点；summary 增加 `link_count_by_source`、`unregistered_symb2`；新增 `sw_unregistered_symb2.parquet`（审计用）与 `sw_unregistered_pin_decisions.parquet`（判定明细）。 |
| `tests/unit/test_superworks_device_internal.py` | 新增 10 项测试（共 31 项，原 21 项不变）。 |

未改：V2 模块、`symbol_port_proposal.py`、`line_groups.py`、`pipeline.py`。

## 3. 数量与排除原因（10 项目）

| 项目 | eligible | 含内部 前→后 | 合计 前→后 | 配对行 | issues | 内部链接 前→后 | 未登记块 | 单端导线 | 候选 | 标签不同 | 远端无块 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p001 | 663 | 544→559 | 567→580 | 1324 相同 | 0 相同 | 108→123 | 44 | 72 | 15 | 7 | 50 |
| p003 | 378 | 303→305 | 320→321 | 655 相同 | 0 相同 | 46→48 | 18 | 31 | 2 | 1 | 28 |
| p022 | 747 | 592→599 | 631→638 | 1699 相同 | 1 相同 | 159→166 | 52 | 48 | 7 | 4 | 37 |
| p044 | 1315 | 993→1071 | 993→1071 | 3033 相同 | 1 相同 | 133→211 | 133 | 134 | 78 | 35 | 21 |
| p050 | 1134 | 864→893 | 871→900 | 2556 相同 | 1 相同 | 186→215 | 94 | 98 | 29 | 42 | 27 |
| p051 | 229 | 202→202 | 202→202 | 797 相同 | 0 相同 | 4→4 | 41 | 24 | 0 | 4 | 20 |
| p061 | 1931 | 1702→1702 | 1778→1778 | 4305 相同 | 0 相同 | 365→365 | 88 | 58 | 0 | 11 | 47 |
| p071 | 200 | 154→154 | 159→159 | 537 相同 | 3 相同 | 4→4 | 68 | 0 | 0 | 0 | 0 |
| p075 | 798 | 776→776 | 781→781 | 2346 相同 | 4 相同 | 6→6 | 7 | 8 | 0 | 8 | 0 |
| p076 | 1250 | 1120→1120 | 1161→1161 | 2882 相同 | 0 相同 | 240→240 | 57 | 36 | 0 | 9 | 27 |
| **合计** | **8645** | **7250→7381** | **7463→7591** | **20134 相同** | **10 相同** | **1251→1382** | **602** | **509** | **131** | **121** | **257** |

- 单端导线 509 = 候选 131 + 标签不同 121 + 远端无块 257。`unregistered:label_unresolved`、`unregistered:label_related`、`unregistered:multiple_blocks`、`unregistered:no_free_far_end` 均为 0。
- 未登记块共 602 个，标签全部可解析，TERMPOINT 段共 1293 个。
- 新增 131 条链接对应 131 个端口，其中 3 个端口原已被 X2 延续覆盖，因此合计口径只增 128，含内部口径增 131。

**四口径（10 项目，eligible 8645）**

| 口径 | 前 | 后 | 变化 |
|---|---|---|---|
| 严格（仅配对） | 6038（69.84%） | 6038（69.84%） | 0 |
| 含延续 | 6733（77.88%） | 6733（77.88%） | 0 |
| 含内部 | 7250（83.86%） | 7381（85.38%） | +131 |
| 合计 | 7463（86.33%） | 7591（87.81%） | +128 |

## 4. 目视（分层抽样，DXF 渲染）

- 抽样：`tools/g1p_sample.py`，种子 20261011，按（项目家族、项目、是否站点前缀标签、块标签前三位）分层轮转抽取。正例 30 例（`G1P_01`–`G1P_15`），负例 6 例（标签不同的单端导线，`G1P_16`–`G1P_18`）。每张图两例，每例两个面板：宽视图与紧邻视图。
- 标记：蓝 = 装置端子导线接点；红 = 单端导线远端；品红 = 未登记块 TERMPOINT 端；绿框 = 装置标签与块标签文字。标题写明标签、脚号、块句柄、距离与来源。
- 判定（单人目视，标签相等由程序判定，未逐例核对文字）：
  - 正例：30/30 为内部连接。开关、继电器（如 `1-1n` 的 WFB-821E 开关组、`2-1n` 的 WFB-822E-02 开关组、`1-7n` 的 ZYQ-810E 继电器）或 PAC-885G-H、PAC-861GA-GCN 本体的引脚。紧邻视图均可辨认导线与两端标记；大图纸（如 PAC-885G-H 的总图页）上宽视图偏小。
  - 负例：6/6 为外部元件（块标签 `AK`、`1ZKK1`、`1-26DK1`、`1-21ZK`、`2-1KLP3`、`1KLP16`，与装置标签不同），正确排除。
- 远端位置：131 例远端均位于 TERMPOINT 段中点（距最近端点 0.500，段长 1.000）。DXF 抽查 93 例中，46 例远端与块插入点距离为 0；其余差值（10.0、11.25）来自插入点的对象坐标换算，未逐例在 WCS 下核对。

图：`png/G1P_01.png` … `png/G1P_18.png`（共 18 张，≤20）；样例索引 `samples.json`。

## 5. 复现与工具（`tools/`）

- `g1p_compare.py <基线> <新> <out.json> <项目…>`：pairs 全列逐行比对、issues 逐条比对、四口径。结果 `compare_10.json`。
- `g1p_stats.py <基线> <新> details.json <项目…>`：覆盖、链接来源、判定原因、未登记块统计。结果 `details.json`。
- `g1p_sample.py <回放目录> <corpus_manifest.json> <输出目录>`：分层抽样与渲染。
- `g1p_timing.py <src> <输出> <项目…>`：整条回放的分步计时（封装 `extract_superworks_semantics`、`_device_internal_links` 与两个写出函数）。
- `g1p_micro.py <src> <out.json> <项目…>`：`extract_superworks_semantics` 微基准（同一 DXF，三次取最小）。

回放命令：
`python .planning/superworks-adapter/replay.py --output .tmp/loop_g1p --snapshot .tmp/loop_g1p_src2 --workers 3 --projects p001 p003 p022 p044 p050 p051 p061 p071 p075 p076`

## 6. 耗时（8 项目：p001 p003 p022 p044 p050 p051 p061 p071）

| 度量 | HEAD | 新 | 增量 |
|---|---|---|---|
| 提取阶段微基准（159 页，三次取最小，两轮交替） | 4.279 / 4.174 s（均值 4.227） | 4.303 / 4.234 s（均值 4.269） | +0.042 s，约 +1.0% |
| 设备内部链接构造（两轮） | 0.141 / 0.176 s | 0.155 / 0.151 s | 约 +0.01 s（噪声量级） |
| 两个写出函数（两轮） | 0.036 / 0.040 s | 0.076–0.085 s + 未登记块写出 0.029–0.030 s | 约 +0.07 s |
| 流水线合计耗时（两轮） | 175.9 / 176.1 s | 168.7 / 175.0 s | 整体差异为机器噪声（−4.1% / −0.6%），非本步骤所致 |

本步骤的新增计算合计约 0.12 秒（提取微增量 0.04 秒、链接构造与两个写出约 0.08 秒），占 8 项目流水线合计时间（约 176 秒）的 0.07% 左右。提取阶段的微增量约 1.0%，两轮波动同量级，结论以流水线占比为准。

## 7. 快照与并发

- 快照 `.tmp/loop_g1p_src2`：生成时 `git diff --stat -- src` 仅含 `superworks_device_internal.py`、`superworks_semantics.py`、`superworks_artifacts.py` 三个文件（本切片改动）。`line_groups.py` 与 HEAD 一致（快照中未混入 G2 的改动）。
- 之后对方在工作区修改了 `line_groups.py`（+182）、`page_extractors.py`、`pipeline.py`（未提交）。这些改动**不在**本快照中，回放与计时均不含对方改动。
- 全量 pytest 在隔离副本中运行（`git archive HEAD` 加本切片的 `src` 快照与测试文件，并复制 `tests/fixtures/superworks`）：**2009 通过，2 跳过，1 失败**。唯一失败 `tests/integration/test_analyze_project.py::test_analyze_project_routes_table_like_page_to_table_extractor_and_emits_table_mapping` 在 HEAD 副本上同样失败（既有问题，与本切片无关）。
- 工作区的 pytest 早先也跑过（2022 通过，1 失败，同一失败项），但那次包含了对方的未提交测试文件，以隔离副本结果为准。

## 8. 局限

- 目视为单人判定；清晰度为主观判断。标签相等由程序判定，文字未逐例核对。
- 只回放了 10 项目，77 项目的覆盖增量需由主线程全量回放确认。按 10 项目比例推算，增量远小于 GAP-1 的 +1851，因为其中约一半标签不同。
- 远端判定依赖线组的自由端。若 SW 线组跨越了不该合并的间隙（GAP-2 所述），远端可能取错；本切片未触碰线组。
- 未登记块的 TERMPOINT 只取首尾两端。一个块的多个 TERMPOINT 只要有一个端点匹配即计入；若同一远端落在同一块的两个 TERMPOINT 上，按同一块处理。
