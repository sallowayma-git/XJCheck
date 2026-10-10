# L-16 修复说明：rules.py 多对一误报（R1-R3，R4 未实施）

范围：只改 `src/dwg_audit/audit/rules.py`，新增 `tests/unit/test_superworks_loop_l16_rules.py`。未改 table_extractor.py、superworks_*、candidates.py。未做 git 操作，未全量回放。离线数据为第五轮 pairs（`.tmp/superworks_round5_full`），基线 `.tmp/superworks_baseline_timed`。工具与输出在 `loop/L-16/tools/`、`loop/L-16/eval_before.json`、`loop/L-16/eval_final.json`。

## 1. 改动位置（rules.py 当前行号）

| 位置 | 函数/常量 | 说明 |
|---|---|---|
| 114-230 | 新增 helper 块 | 见下表 |
| 118 | `_CONTINUATION_HEADER_PATTERN` | 与 table_extractor.py:2283 `_terminal_header_identity(allow_continuation=True)` 的正则相同，未 import 提取器 |
| 125 | `_fold_continuation_identity` | 去掉 上接 前缀后取身份 |
| 133 | `_terminal_row_logical_identity` | 行的端点身份 = 表头前缀（上接X 取 X）+ 行号 |
| 148 | `_pair_endpoint_identity` | R1：左值身份。上接值为该表格行本身端点时，归并为行端点（上接7U1D4892 + 行 92 -> 7U1D92） |
| 168 | `_range_member_identities_by_end` | R2：组内非桥接范围左值 -> 成员集合 |
| 180 | `_terminal_row_side_index` | R3：按 (sheet, sw_row_id) 收集表格行的左列/右列端子，仅索引左右两侧都有端子且两值不同的行 |
| 211 | `_is_terminal_row_junction_group` | R3 判定：组内全部端（范围端由成员解释）都是某一行两侧之一，且该行中间列端 = 组右值 |
| 1367 | `_run_many_to_one` | 1369-1371 建 `row_index`；1382 `effective_lefts` 改用 `_pair_endpoint_identity`；1391 调用 R3 判定，命中则 continue |

R2 的基础（范围覆盖成员）已由第五轮 K2 实现（`_bridge_covered_terminal_identities`，rules.py:95）。本轮补齐的是范围端在 R3 中的解释：范围 1-7UD20~21 由同行成员 1-7UD21 解释。

## 2. 实施情况

- **R1（已实施）**：仅在 `_run_many_to_one` 的左值身份比较中生效。只有当上接值等于该 table_mapping 行自身端点（header_prefix + row_number）时才用行端点身份；其余上接值退化为去掉 上接 后的裸文本。cross-page 规则未改（L-16 无该类条目，原始 cross 结果逐条不变）。
- **R2（已由 K2 实现，本轮补齐 R3 解释）**：见上。
- **R3（已实施）**：判定依据是 table_mapping evidence 的结构字段：`sw_row_id`、`sheet_id`、`column_roles`（middle 为 row_number，left/right 为 terminal_endpoint）、`header_prefix`、`row_number`、`left_value`/`right_value`。同一 (sheet, sw_row_id) 两侧都有端子时，该行中间列端 = 行端点。仅当组内所有左端都能被该行两侧之一解释时才豁免；组外的第三条线仍报。
- **R4（未实施）**：数据显示条件不成立，无法通用判定为合并条件。
  - p061 1-21QD77：表格记录 P0139 左坐标 (231.25,191.25)，元件记录 PSW52443 左坐标 (235.0,192.5)，距离 3.95，不满足 < 3。
  - 元件记录 `evidence.source` 缺失、`ordinary_pair_eligible=False`，被 `_high_confidence_source_eligible` 排除，根本不进入多对一图。合并无处可作用。
  - p061 4-21QD71：P0431 (228.75,198.75) 与 PSW7061 (232.5,200.0)，距离同为 3.95，同样被排除。

## 3. L-16 表 21 条新状态

| # | 项目 | 右值 | 修复前 | 修复后 | 依据 |
|---|---|---|---|---|---|
| 1 | p022 I0003 | 1U1D4 | 报 | 消除 | R2+R3：行 1U1D4（S0019，sw_row_id SWR:F0019:S0019:7AAF）两侧 1n1423 / 1-7UD21 |
| 2 | p022 I0002 | 1U1D5 | 报 | 消除 | R2+R3：行 1U1D5（S0019，7ABE）两侧 1n1422 / 1-7UD24 |
| 3 | p023 I0003 | 1U1D4 | 报 | 消除 | R2+R3：行 1U1D4（S0019，4B75） |
| 4 | p023 I0002 | 1U1D5 | 报 | 消除 | R2+R3：行 1U1D5（S0019，4B84） |
| 5 | p024 I0003 | 1U1D4 | 报 | 消除 | R1+R3：表头 上接1U1D3 行 4 即 1U1D4（S0020，C83A）两侧 1n1423 / 1-7UD21 |
| 6 | p024 I0002 | 1U1D5 | 报 | 消除 | R3：两侧 1n1422 / 1-7UD24 解释，1U1D6 为既有 bridge claim，不计端（`_is_terminal_strip_bridge_claim`，未改） |
| 7 | p027 I0001 | 3-4QD22 | 报 | 消除 | R1：上接3-4XD513（表头 上接3-4XD5 行 13）= 3-4XD13，与直连线 3-4XD13 同端 |
| 8 | p040 I0001 | 1GD1 | 报 | 保留 | R3 仅解释行 1GD1（S0021，162D）两侧 1DK1-4 / 1n103 中的 1DK1-4。组内 1n/NDY306A-3（背板 S0016）与 2YD1（S0009 普通线）不在该行，按要求保留 |
| 9 | p040 I0002 | 2GD1 | 报 | 保留 | 同 8；1YD1 为跨装置名，需人工 |
| 10 | p041 I0002 | GND | 报 | 保留 | F-g 公共地，未处理 |
| 11 | p042 I0002 | GND | 报 | 保留 | F-g |
| 12 | p043 I0004 | GND | 报 | 保留 | F-g；上接JD511 折叠为 JD511 后仍为两端 |
| 13 | p044 I0004 | GND | 报 | 保留 | F-g |
| 14 | p057 I0002 | 7U1D92 | 报 | 消除 | R1：上接7U2D4892（表头 上接7U2D48 行 92）= 7U2D92，与直连线 7U2D92 同端；7U1D91 为既有 bridge claim |
| 15 | p057 I0001 | 7U2D92 | 报 | 消除 | R1 镜像 |
| 16 | p061 I0001 | 1-21QD77 | 报 | 保留 | R4 不实施（见 2）。余下 1-21GD17（外线）与 1-21n/BI2-20（背板表格）仍是两个端 |
| 17 | p061 I0002 | 2-21QD31 | 报 | 保留 | 待人工，未处理 |
| 18 | p061 I0003 | 3-21QD31 | 报 | 保留 | 待人工，未处理 |
| 19 | p061 I0004 | 4-21QD71 | 报 | 保留 | R4 不实施（见 2） |
| 20 | p036 DUP | UD4 / 1UD4 | 未改 | 未改 | R-DUPLICATE-SAME-LINE，F-f 不在 R1-R4 范围，同线路径未触碰 |
| 21 | p037 DUP | 同 20 | 未改 | 未改 | 同 20 |

归类结果：消除 9 条（1-7、14、15），保留 10 条（8-13、16-19），未改 2 条（20-21）。

注：第 6 条依赖既有 bridge claim 判定（1U1D6 短接），这是第五轮已有逻辑，本轮未改。

## 4. 离线重算（第五轮 pairs，live rules.py）

| 规则 | 修复前 | 修复后 | 说明 |
|---|---:|---:|---|
| R-MANY-TO-ONE | 27 | **18** | 消除 9 条，明细见第 3 节 |
| R-CROSS-PAGE-CONFLICT（原始 runner） | 38 | 38 | 逐条相同 |
| R-CROSS-PAGE-CONFLICT（issues.parquet，cluster 后） | 3 | 3 | 基线 3/3 保留 |
| R-DUPLICATE-PAIR | 0 | 0 | 未变 |
| R-ONE-TO-MANY | 4 | 4 | 未变 |

- 修复前重算与第五轮 issues.parquet 一致（27 条 m2o），说明 harness 与实际运行口径相同。
- 基线 m2o 保留集：修复前后都是 8/13，且为同一集合：p015 GND、p021 GND、p039 1-2n221、p039 3-2n221、p040 1ZK-3、p050 GND、p071 GND、p075 GND。基线 GND 与 KD/1ZK 类均未变。
- 基线 cross 保留集 3/3 不变（p050 1n/NCK305-5、p065 NCK305-1@c0、p066 NCK305-5@c0）。

## 5. 测试

- `tests/unit/test_superworks_loop_l16_rules.py`：14 项，全部通过。
  - R1：正例 1（折叠到同端）；正例 2 配对 1 条残留冲突（7U2D91 仍报）；负例（行号不符 93；无表格证据时仅裸文本）；裸 上接JD511 折叠。
  - R2：正例（范围与成员同端）；负例（范围不吸收无关端 1-7UD30）。
  - R3：正例（p022 形态：范围 + 成员 + 背板左值）；正例（p024 形态：表头 上接1U1D3 行 4，R1+R3）；负例（组外第三条线仍报 ZZ9）；负例（左右线来自两个不同 sw_row_id 不豁免）；负例（仅单侧行不豁免）；负例（行端点为 1U1D5 不解释 1U1D4 组）；索引契约（仅双侧、两值不同）。
- 变异检查（`loop/L-16/tools/mutate_l16.py`，进程内关闭单项）：
  - R1 关闭：1 条正例失败。
  - R2 关闭（范围解释）：2 条失败。
  - R3 关闭：2 条失败。
- 全量 `pytest tests/unit -q`：**1716 passed, 1 skipped, 1 xfailed**，无失败。

## 6. 限制与未处理项

- GND 公共地（F-g）：第 10-13 条及基线 GND 未处理，按指示保留。
- p040 第 8/9 条：R3 只能解释同行的一侧，组内其余端不在同一行，按指示保留。
- p061 第 16、19 条：R4 不实施（见 2）。第 17、18 条待人工。
- 第 20-21 条（R-DUPLICATE-SAME-LINE，F-f）：未处理。
- R1 对 cross-page 规则未应用：L-16 无对应条目，且 cross 原始结果未变化。
- R3 的行索引来自全部高置信 table_mapping（按 sheet + sw_row_id）。组内的其他端可以来自别的 sheet（如 p022 1U1D4 组跨 S0007/S0014/S0019），与“同一 sheet、同一行”的两侧约束分开：两侧线必须来自同一行，组可跨 sheet。
