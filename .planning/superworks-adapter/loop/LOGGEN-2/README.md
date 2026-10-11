# LOGGEN-2：导线去向记录接入生产配对（第二阶段）

范围：`superworks-loop` 分支，HEAD=5a7a35a 起算。未 git 提交。未改 V2 模块、`src/dwg_audit/audit/symbol_port_proposal.py`，未加 PDF/OCR，未按项目/句柄/值特判，未整体豁免 SuperWORKS 来源。`PYTHONIOENCODING=utf-8`。

数据：10 项目（p001 p003 p022 p044 p050 p051 p061 p071 p075 p076，对比基线 `.tmp/superworks_round15_full`）；全语料 77 项目（对比基线 `.tmp/superworks_round15_full` 全部 77 个项目，回放 `.tmp/superworks_round16_full`，快照 `.planning/superworks-adapter/round16_full_src`）。临时目录保留：`.tmp/loop_loggen2_*`。

---

## 0. 结论摘要

1. **性能达标。** 去向读取不再二次打开 DXF。8 个项目单进程（L-11 方法，交替两轮取中位数）：HEAD 合计 156.67 s（其中二次读取 DXF 14.07 s），新版 142.56 s。去向相关增量：读取 walk 0.15 s + 解析 0.15 s + 识别阶段准入与对账约 0.5 s，合计约 0.8 s，占 142.6 s 的 **约 0.6%**（目标 ≤2%）。
2. **接入范围按指令收窄，覆盖率增量有限。** 10 项目严格口径 64.40% → 64.56%（+14 端口）；全语料 57.31% → 57.68%（+312 端口）。**pass 口径两者都没有变化**（10 项目 64.28%，全语料 57.27%），增量全部来自 review 配对。原因见第 5 节：第一阶段的大部分潜在增量是“端子 ↔ 内部元件引脚”，按指令排除在外。
3. **新增 issue：0。** 10 项目与全语料，逐项目比对 issue 的增减均为 0（全语料 41 → 41，逐项目集合相同）。因此没有需要逐条截图判定的新增 issue。
4. **新增配对 3（10 项目）/ 109（全语料）**，全部为 review（`wire_geometry_missing`，即记录无导线句柄，按指令降为 review）。**新增 pass 配对为 0**，故“抽 20 例 pass 截图”不适用；改为对 review 新增配对抽样 12 例截图并做几何连通性检验（第 6.4 节）。
5. **B3 数值修正生效**：10 项目 8 处、全语料 96 处（右侧 90、左侧 6），均为 review 配对的旧数字侧值被换成与记录端一致的 SW 端口身份。截图确认修正后的身份与图面标注一致。
6. **与 LOGGEN-MISMATCH 的关系：** 该子代理结论为身份构造无需修改，接线去向标签与远端身份不一致多为链式下一跳，不应作为审计判据。本次接入只用 SW 端口身份准入；去向文字只用于统计，因此不受影响，也未据此增加任何判定。

---

## 1. 改动文件与函数

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/extract/cad_extract.py` | `extract_cad_artifacts`：在已打开的 `doc` 处调用 `read_page_wire_routes`，结果放入 `superworks.wire_route_pages`；失败只记入 `wire_route_failures`。开关 `superworks_wire_routes.enabled`（默认 True）。 |
| `src/dwg_audit/extract/superworks_semantics.py` | `SuperworksData` 新增字段 `wire_route_pages`、`wire_route_failures`、`wire_route_rows`、`wire_route_stats`。 |
| `src/dwg_audit/extract/superworks_loggen.py` | 新增 `build_wire_route_rows`（只解析已读页面，不开 DXF）；`collect_wire_route_rows` 改为独立入口（仅测试与工具用，内部调用 `build_wire_route_rows`）；行新增 `admission_status`、`admission_reason`、`admitted_pair_id` 三列；模块说明更新。 |
| `src/dwg_audit/audit/superworks_extractor.py` | `_wire_pair`（新）：由原线组路径的配对构造代码抽出，线组路径与线记录准入共用，字段、状态规则、视图范围完全一致。`_admit_wire_routes`（新）：准入。`_check_consumed_end`、`_reconcile_consumed_wire_routes`（新）：B2 注记与 B3 修正。`_wire_route_census`（新）：不接入与跨页统计。`_run_wire_route_admission`（新）：调度。`extract_superworks_pairs` 新增可选参数 `wire_route_sheet_numbers`，在字典校验之前调用准入。 |
| `src/dwg_audit/pipeline.py` | `_write_sw_wire_routes(project_dir, superworks, logger)`：不再二次打开 DXF，直接写 `superworks.wire_route_rows` 与统计；`extract_superworks_pairs` 调用处传入全部页的页号。 |
| `tests/unit/test_superworks_wire_route_admission.py`（新） | 9 个用例：准入 pass、无导线降 review、端口已消费不准入、未解析端不准入、自环不准入、B3 修正、pass 配对同端口冲突注记、另一导线扇出不注记、统计。 |

全量单测：`python -m pytest tests/unit -q` → **1914 passed, 1 skipped**（HEAD 基线 1905 passed，新增 9）。

---

## 2. 接入规则（实际实现）

准入（B1）：一条去向记录同时满足以下条件才生成配对。

- 恰好两端；两端均为 SW 端口身份已解析（`status == resolved`，不接受仅文字解析的远端）；两端 SW 类别均为 `端子` 或 `装置端子`；两端在同一文件、同一已审计页。
- 两端端口均未被任何非 discard 配对的 SW 侧 `port_ids` 占用（保守口径，见第 5 节）；所在导线组没有非 discard 配对。
- 非自环（`_self_connection_reason` 为空）。
- 配对由 `_wire_pair` 构造：`ordinary_pair` / `bridge_mapping`（同排短接，经 `_same_strip_relation` 判定）/ `wire_component_mapping`，与线组路径相同。
- 状态：导线句柄存在于该页且在两端都触碰端口（`wire_contacts`）、且无真冲突时为 pass；否则为 review。原因码 `wire_geometry_missing`（无导线句柄或句柄无几何）、`wire_not_touching_port`（有几何但不接触端口）。review 原因只进入 `rationale`，不写入 `sw_conflicts`。
- 导线组：优先复用已有 GWSW 组，其次几何完全相同的线组，否则新建 GWSW 组。
- 配对额外带 `evidence.sw_wire_route = {record_id, source_kind, wire_handle, wire_confirmed, review_reasons}` 作为溯源字段。
- 不生成覆盖观察以外的任何 issue；准入只追加配对，从不替换或删除既有配对。

B2（一端已被消费的记录）：不新建配对。对每个已消费端，只比较 SW 端子身份：

- 同端口：配对侧值与记录身份不一致时，若配对为 review 且其 SW 侧身份与记录身份完全相等，则把旧数字侧值替换为该身份（B3，并记录 `sw_wire_route_fix`）；否则挂 `sw_wire_route_conflict`（`same_port_value_differs`）。
- 另一端：记录的另一端与配对的另一侧都是 SW 端子，且身份不等价；仅当同一导线时挂 `other_end_differs`，另一导线视为端口一对多（扇出），只计数不记录。

内部元件端：不接入，不比较（同一引脚在不同来源有多种命名，如 `8ID3` 与 `8n1505`，比较会产生噪声）。

B4（跨页）：只统计，不生成配对。全语料 28259 个跨页远端中，本端是端子的为 0（PCL 本端全部是元件引脚），因此按第 5 节的范围没有可接入对象。远端文字只做校验计数。

B5（内部元件端）：不接入，只统计（全语料 28049 条记录含内部端）。

---

## 3. 性能前后

方法：`replay.py --workers 1` 对 L-11 的 8 个项目（p000 p024 p030 p044 p050 p061 p070 p075），基线 `.tmp/loop_loggen2_base_src`（= HEAD，已与 `git show HEAD` 比对，忽略 CRLF），新版 `.tmp/loop_loggen2_src`（= 最终代码，与 `src/` 完全一致）；交替 base、new、base、new，每个项目取两轮中位数。脚本 `tools/perf_loggen2.py`，结果 `perf.json`，日志 `perf.log`。

| 项目 | HEAD 总耗时 (s) | 新版总耗时 (s) | HEAD 二次读取 (s) | 新版读取 walk (s) | 新版解析 (s) |
|---|---|---|---|---|---|
| p000 | 11.74 | 10.55 | 1.21 | 0.01 | 0.011 |
| p024 | 15.46 | 14.18 | 1.36 | 0.01 | 0.015 |
| p030 | 23.74 | 20.96 | 2.65 | 0.03 | 0.021 |
| p044 | 22.28 | 20.41 | 1.92 | 0.02 | 0.023 |
| p050 | 21.68 | 19.63 | 1.90 | 0.02 | 0.021 |
| p061 | 35.09 | 32.31 | 2.89 | 0.03 | 0.032 |
| p070 | 11.03 | 10.04 | 1.07 | 0.01 | 0.012 |
| p075 | 15.64 | 14.46 | 1.06 | 0.01 | 0.014 |
| **合计** | **156.67** | **142.56** | **14.07** | **0.15** | **0.15** |

阶段合计：抽取 86.79 → 86.35 s（−0.5%，噪声内）；识别 23.65 → 24.30 s（+0.65 s，含解析与准入、对账、统计）；其余阶段的差值主要是 HEAD 的二次 DXF 读取（14.07 s）。

相对不含去向读取的基线（新版即是）的增量：约 0.8 s / 142.6 s ≈ **0.6%**。HEAD 相对新版的总耗时差（−9%）完全来自去掉了二次读取，不是准入本身的收益。

---

## 4. 10 项目对比（`t10/`）

回放：`.tmp/loop_loggen2_t10`（最终代码）。对比工具 `tools/compare_loggen2.py`，结果 `t10/*.json`、`t10/summary.json`。

| 项目 | 配对新增 | 配对变更 | issue 增 | issue 减 | 说明 |
|---|---|---|---|---|---|
| p001 | 0 | 4 | 0 | 0 | B3 修正 4 处 |
| p003 | 0 | 0 | 0 | 0 | |
| p022 | 0 | 4 | 0 | 0 | B3 修正 4 处 |
| p044 | 1 | 0 | 0 | 0 | 准入 review 短接 1 条 |
| p050 | 0 | 0 | 0 | 0 | |
| p051 | 0 | 0 | 0 | 0 | |
| p061 | 1 | 1 | 0 | 0 | 准入 1 条；注记 1 条 |
| p071 | 0 | 0 | 0 | 0 | |
| p075 | 0 | 0 | 0 | 0 | |
| p076 | 1 | 1 | 0 | 0 | 准入 1 条；注记 1 条 |
| **合计** | **3** | **10** | **0** | **0** | |

- 配对新增 3 条：全部 `bridge_mapping`、review、`wire_geometry_missing`。
- 配对变更 10 条：8 条 B3 修正（右侧，旧值 `702/701/703/704/801/802`、`701/702` 等，改为 `7QD4–7QD7`、`1-7QD4–1-7QD7`，与 SW 身份一致）；2 条注记（PW0282、PW0210，侧值为描述文字“Manual closing of synchronization”，记录端身份 `1-21n331` / `1-21n232`，只记录，未改动）。
- 去除的配对：0。

严格口径（`tools/strict_coverage.py`，口径同 COV-GAP 层 b：端子/装置端子，eligible 8645）：

| 口径 | 第一阶段 (round15) | 第二阶段 | 变化 |
|---|---|---|---|
| 消费（非 discard，值一致） | 5567 (64.40%) | 5581 (64.56%) | +14 |
| 其中 pass | 5557 (64.28%) | 5557 (64.28%) | 0 |

---

## 5. 全语料对比（`full/`）

回放：`.tmp/superworks_round16_full`，77 个项目全部 COMPLETE，0 失败，快照 `round16_full_src`。对比结果 `full/summary.json`、`full/p000.json`–`full/p076.json`，严格覆盖 `full/strict_round15.json`、`full/strict_round16.json`。

| 指标 | round15 | round16 | 变化 |
|---|---|---|---|
| 配对数 | — | — | 新增 109（review：bridge_mapping 11、wire_component_mapping 98）；删除 0 |
| 配对变更 | — | — | 136：B3 修正 96（右 90、左 6）；注记 40（仅 evidence） |
| issue 总数 | 41 | 41 | 逐项目新增 0、消失 0，集合相同 |
| 严格消费 | 47380 / 82680 = 57.31% | 47692 / 82680 = 57.68% | +312 |
| 其中 pass | 47349 = 57.27% | 47349 = 57.27% | 0 |

注意：109 条新增配对对应 61 条不同记录，其余为同一记录在重复项目副本中的出现（语料中存在内容相同的重复项目，如 p041–p044、p025–p027、p016/p019/p020 等）。

全语料记录统计（`sw_wire_routes_stats.json` 汇总）：

| 类别 | 记录数 |
|---|---|
| 总记录（LOGGEN 53857 + PCL 28435） | 82292 |
| 准入 | 109 |

严格消费增量 312 的来源（全语料）：B3 修正后侧值与端口身份一致、计入消费约 96（review）；准入 109 条的两端口计入约 218（review）。两者之和约 314，与 312 相差 2（未逐一核对，可能是同一端口两类都计入）。pass 口径没有变化。

未准入原因（全语料，首个失败规则）：

| 原因 | 记录数 |
|---|---|
| 非两端（三端及以上 / 单端） `not_two_ends` | 25134 |
| 跨页端 `cross_page_end` | 22652 |
| 端口已被非 discard 配对占用 `end_consumed` | 21365 |
| 端未解析 `end_unresolved` | 12482 |
| 自环 `self_connection` | 318 |
| 页未审计 `sheet_not_audited` | 166 |
| 非端子端 `non_terminal_end` | 66 |

已消费端记录（未准入，只做注记）：`consumed_agree` 21329、`consumed_unchecked` 13533、`consumed_value_fixed` 96、`consumed_conflict` 60。

跨页统计（记录）：远端 SW 身份已解析且与远端文字一致 7371、不一致 15411、远端仅文字解析 5314、远端文字缺失 71、远端未解析 92。本端为端子的跨页记录为 0。

---

## 6. 新增 issue 与抽样判定

### 6.1 新增 issue 逐条判定

- 10 项目：新增 0，消失 0。
- 全语料：新增 0，消失 0（41 → 41，逐项目集合相同）。

因此没有需要逐条判定或截图的新增 issue。

### 6.2 B3 修正抽样截图（`png/`）

- `fix_01`–`fix_08`（p001 ×4、p022 ×4，全部 10 项目修正）：每张图导线终点处的端子旁均印有修正后的身份（如 `7QD5`），旧值为相邻的其他端子或数字候选。确认修正正确。
- `png_full/leftfix_A_p037_PW0303.png`：左侧修正 `1210 → 4n1310`，图上 `4n1310` 印于该导线端子旁，`1210` 属于下方另一端子。确认正确。
- `png_full/leftfix_B_p072_PW0104.png`：左侧修正 `0823 → 1QD11`，与上同类，未单独判读（同一机制）。

### 6.3 注记截图

- `annotation_10_p061_PW0282.png`、`annotation_12_p076_PW0210.png`：配对侧值为描述文字，记录端身份与之不一致，属于语义配对与 SW 端口的不一致，只注记，未改动，也未产生 issue。

### 6.4 准入配对（review）抽样与几何连通性

10 项目 3 条（`png/admitted_09`、`admitted_11`、`admitted_13`）：同排端子之间的绘制竖向母线连接，无导线句柄，降为 review。

全语料 109 条：

- 随机抽样 12 例（种子 20260711，`png_full/full_admitted_01`–`12`），目视判读：图上均可见从一个端子经绘制线段到另一端子的连接（如 `1I13D7 ↔ TF137`、`1I12D7 ↔ TF127`、`1I8D7 ↔ TF87`、`2-1ID7 ↔ 2-1ID6`），但记录本身无导线句柄。判为真实连接，可信度为 review 级。
- 几何连通性检验（`tools/geometric_witness.py`，`full/witness.json`）：以 SW 端口段为两端触点，在该页绘制线段图上做广度优先搜索，允许端点相接与 T 形接入。结果：**101 条有连续绘制路径，8 条无**（8 条实为 2 条不同记录的副本：`1-4n401 ↔ 1-4n201`（p025/p026/p027/p064，目视 `png_full/nowitness_A_p025.png` 一条沿母线可连，判为可能真实）与 `2-1ID7 ↔ 2-1ID6`（p041–p044，目视 `png_full/nowitness_B_p041.png` 无明确连线，**不确定**）。

这 2 条记录的 review 配对占用了端口，会计入严格口径的 review 级消费。它们不产生 issue，但证据较弱，建议人工复核（见第 8 节）。

---

## 7. 第一阶段“潜在增量”为何大幅缩小

第一阶段报告的严格口径潜在增量为 471 个端口（10 项目）。其中：

- 约 188 个端子端口与 283 个装置端子端口的另一端是**内部元件引脚**（非 SW 端子），按本次指令“内部元件端不接入”排除。
- 端子 ↔ 端子 / 装置端子 ↔ 装置端子 的记录（第一阶段 8 条，两端都无活动配对）：2 条是三端记录（不接入）；3 条是同排短接，准入为 review（见第 6.4 节）；3 条被排除，原因是端口被某个非 discard 的 junction 配对的 `port_ids` 列出（该配对的侧值为空、端口列表覆盖同一接点上的 36 个端口），按保守口径视为已占用。

若用户同意接入内部元件端，潜在增量仍在（第一阶段数据：内部元件端 2018 条、约 471 端口，10 项目严格口径上界约 +5.4 个百分点），但它依赖内部引脚身份（如 `1FA-13`），风险明显更高。**这是需要用户决定的范围问题**，本次未做。

---

## 8. 遗留风险与建议

1. **内部元件端未接入**（见第 7 节）：这是覆盖率增量小的主因。需要用户决定是否开放。
2. **无导线句柄的准入（109 条，61 条不同记录）**：按指令降为 review，但它们占了严格口径增量的大部分（约 218 端口，review 级）。其中 8 条（2 条不同记录）无几何连通证据，`2-1ID7 ↔ 2-1ID6` 目视不确定。建议：若希望严格口径只计 pass 级增量，应修改口径或暂不准入无导线句柄的记录；或者要求几何连通检验通过才准入（当前未实现）。
3. **同端口冲突只做注记**：全语料 60 条配对注记（`same_port_value_differs`），主要是描述型语义配对（侧值为文字说明而非端子身份）。它们不是导线去向错误，但说明这类配对的侧值与 SW 端口身份并不对应，可能是 review 配对的已知现象。
4. **另一端冲突从未触发**：`other_end_differs` 在全语料为 0 次。原因：可比较的情形要求记录另一端与配对另一侧同为 SW 端子，而已消费端的记录多为内部端或未解析端。该检查因此在本语料中基本是空操作。
5. **统计计数口径**：`conflict:same_port_value_differs` 的计数器按检查事件计数（同一配对可因两个已消费端被检查两次），去重后的配对注记为 2（10 项目）与 60（全语料）。
6. **B4 无可接入对象**：PCL 本端全部是元件引脚，跨页远端的 SW 身份只作为统计，没有生成配对。
7. **性能**：增量约 0.6%，达标。未测量“完全关闭去向读取”的基线；HEAD 与新版的差值即为二次读取成本（14.07 s）。
8. **未做的事**：未开放内部元件端接入；未对 `resolved_by_text` 远端生成配对；未修改 `test_superworks_loggen.py`（原有 7 个用例仍通过）。

---

## 9. 文件与复现

- `README.md`（本文件）
- `perf.json`、`perf.log`：计时
- `t10/`：10 项目对比（`pNNN.json`、`summary.json`、`strict_t10_new.json`）
- `full/`：全语料对比（`pNNN.json` ×77、`summary.json`、`strict_round15.json`、`strict_round16.json`、`admitted_rows.json`、`witness.json`）
- `png/`：B3 修正 8、注记 2、准入 3（10 项目）
- `png_full/`：左侧修正 2、全语料准入抽样 12、无几何通路样例 2
- `tools/`：`compare_loggen2.py`、`strict_coverage.py`、`perf_loggen2.py`、`render_loggen2.py`、`render_full_admitted.py`、`geometric_witness.py`

复现（仓库根目录，`PYTHONIOENCODING=utf-8`）：

```
python .planning/superworks-adapter/replay.py --output .tmp/loop_loggen2_t10 --snapshot .tmp/loop_loggen2_src --workers 3 --projects p001 p003 p022 p044 p050 p051 p061 p071 p075 p076
python .planning/superworks-adapter/replay.py --output .tmp/superworks_round16_full --snapshot .planning/superworks-adapter/round16_full_src --workers 3
python .planning/superworks-adapter/loop/LOGGEN-2/tools/compare_loggen2.py .tmp/superworks_round15_full .tmp/loop_loggen2_t10 .planning/superworks-adapter/loop/LOGGEN-2/t10 p001 p003 p022 p044 p050 p051 p061 p071 p075 p076
python .planning/superworks-adapter/loop/LOGGEN-2/tools/compare_loggen2.py .tmp/superworks_round15_full .tmp/superworks_round16_full .planning/superworks-adapter/loop/LOGGEN-2/full p000 ... p076
python .planning/superworks-adapter/loop/LOGGEN-2/tools/strict_coverage.py .tmp/superworks_round16_full .planning/superworks-adapter/loop/LOGGEN-2/full/strict_round16.json
python .planning/superworks-adapter/loop/LOGGEN-2/tools/perf_loggen2.py .tmp/loop_loggen2_base_src .tmp/loop_loggen2_src .tmp/loop_loggen2_perf
python .planning/superworks-adapter/loop/LOGGEN-2/tools/geometric_witness.py .tmp/loop_loggen2_full_admitted.json .tmp/superworks_round16_full .planning/superworks-adapter/loop/LOGGEN-2/full/witness.json
python -m pytest tests/unit -q
```
