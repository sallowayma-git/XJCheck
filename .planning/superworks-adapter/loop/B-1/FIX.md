# B-1 修复切片：不可见文字 + 数值三列单元格规则（FIX，v2）

范围：R-PAIR-MISSING-SIDE 的 B 组 5 条（p062 PC0019/PC0125、p071 PC0053、p075 PC0232/PC0440）。
根因与证据见同目录 `README.md`、`details.json`。
未执行 git commit/push；未改 V2 模块、`symbol_port_proposal.py`、`component_diagrams.py`、`rules.py`；未加 PDF/OCR；无按项目、句柄或取值的特判。

v2 是主线程复核后的追加：删除 S0008 上由隐形数字和可见端口阵列产生的全部数值三列 pass，并去掉 `R-ONE-TO-MANY`。v1（隐形文字过滤）的内容保留在第 2、3 节。

---

## 0. 结论摘要

- p071 S0008 的 P0001'（COM2 端口格 "1" ↔ PWR2 旁 "1"）、P0002（"1" ↔ "5"）、以及 v1 中已删除的 P0001（隐形 "2" ↔ "1"）全部为假配对。P0003、P0004（S0009，隐形中列）同样为假。
- p055 S0012 的 P0001、P0002（"1" ↔ "1"，COM 端口阵列之间的配对）也是假配对，它们是同一种误配的另一个实例。
- 误配的共同机制：数值三列路径把一个**多数字的区域**当成单元格，并取其中第一个数字。
- 通用修复：数值三列行中，任一用到的单元格（左、中、右）若含超过一个数字，则跳过该行。语料中该规则影响的全部是假 pass，没有误伤真配对。

---

## 1. 根因：table_extractor 为什么会把 S0008 当成映射表

### 1.1 路径

- S0008 的 `sheet_category` 为“背板接线图”，`page_subtype=backplate_geometric_table`。
- `_build_backplate_virtual_mappings` 对该页无结果，于是落到通用网格路径：`extract_table_pairs` → `_detect_table_grid` → `_build_cells` → `_assign_texts_to_cells` → `_build_three_column_mappings`（`mapping_mode=numeric_three_column`）。
- `_build_three_column_mappings` 的数值分支只要求：中列能取到数字，且左或右之一能取到数字。

### 1.2 行、列从哪里来

`_detect_table_grid` 对全页所有长线和多段线取边界，不要求它们属于同一张表。S0008 的边界来源（经 DXF 缓存的 polyline 与 line 复原，见 `scratchpad`，与 `.tmp/loop_invis_dbg_pp/p071/table_dump/S0008.pkl` 一致）：

| 方向 | 位置 | 来源 |
|---|---|---|
| 列 | x=25.00 | layer 0 整页竖线（块 26043） |
| 列 | x=45.46、394.54 | BORDER 小框的左右边（块 24248） |
| 列 | x=220.00 | BORDER 小框内的分隔竖线（块 24248 的闭合多段线） |
| 行 | y=60、80、100 | layer 0 的小框（块 25C02） |
| 行 | y=142.74、225.00 | BORDER 框的上下边（块 24248） |
| 行 | y=147.50 | layer 0 外框（块 26043，x 25–415） |
| 行 | y=183.87 | BORDER 框内的分隔横线（块 24248 的闭合多段线） |

这些线属于不同的块，它们把页面切成 4 列、6 行的网格。网格本身并不是一张表：中列单元格为 x 45.46–220、y 147.5–183.87，右列单元格为 x 220–394.5、y 147.5–183.87。

### 1.3 行带容差与“2.5 单位”

- `_TABLE_GRID_LINE_TOL = 3.0` 只用于把同一条线的多个端点聚成一个边界（`_cluster_values`），它不是行带容差，行的归属也没有按行高比例判断。
- 单元格就是行列交叉的整块矩形。文字只要落在矩形内就归入该单元格。
- P0001' 中，中列 "1"（y=178.41）和右列 "1"（y=175.91）的 y 差 2.5 单位，只是两个文字在同一个大单元格内的偏差。2.5 不是任何阈值，它只说明两者都在 y 147.5–183.87 这个带内。

### 1.4 为什么会跨到 x 很远的 PWR2

- `_preferred_cell_text` 对单元格内的文字按 `(insert_y, insert_x)` 排序，取第一个数字。它不考虑距离，也不考虑单元格内还有多少个数字。
- 右列单元格宽 174.5（x 220–394.5），其中有 23 个数字，包括 x 356.7 处 PWR2 端口阵列的首位 "1"（T0511）。它之所以被取到，只是因为它的 `(y, x)` 排序最靠前，并不是因为它离中列近。

### 1.5 单元格内容（修复前，原始文字，`tools/table_rule_review.py` 输出）

| 误配 | 中列（文字数 / 数字数） | 右列（文字数 / 数字数） | 图面内容 |
|---|---|---|---|
| p071 S0008 P0001（v1 已删，隐形中列） | 24 / 7（含隐形 "2"） | 34 / 23 | 中列为空白处的隐形数字；右列为 PWR 端口阵列 |
| p071 S0008 P0001'（v2 删） | 21 / 4 | 34 / 23 | 中列为 COM1/COM2 端口阵列首位；右列为 PWR2 端口阵列首位 |
| p071 S0008 P0002（v2 删） | 13 / 5 | 34 / 23 | 中列为 COM1 阵列首位 "1"；右列为另一阵列的 "5" |
| p071 S0009 P0003（v1 已删） | 29 / 1（隐形 "4"） | 34 / 8 | 中列为隐形数字；右列为多个数字 |
| p071 S0009 P0004（v1 已删） | 31 / 2（含隐形 "2"） | 2 / 0（"PWR1"、"PWR2"） | 中列为隐形数字；右侧为远处的电源标签 |
| p055 S0012 P0001（v2 删） | 31 / 25 | 29 / 23 | 中列为 COM2 端口阵列首位；右列为 COM10 阵列首位 |
| p055 S0012 P0002（v2 删） | 41 / 20 | 42 / 23 | 同上，行 2 |

（图：`fix_png/rule_*.png`，每图画出检测到的单元格边界，虚线为网格线，圆圈为数字文字。）

---

## 2. v1：隐形文字过滤（保留）

- `domain/models.py`：`TextItem` 末尾新增 `raw_height: float | None = None`，新增 `INVISIBLE_TEXT_RAW_HEIGHT = 0.01` 与 `is_invisible_text()`。`None` 与 NaN 视为可见。
- `extract/cad_extract.py` `_append_text`：增加 `raw_height=float(height)`，`height` 与 bbox 的值不变。
- `audit/candidates.py`：主循环新增 `invisible_text` 拒绝分支；三个 `_add_schematic_*` 辅助通道同样跳过不可见文字。
- `audit/table_extractor.py` `extract_table_pairs` 入口：`texts = [t for t in texts if not is_invisible_text(t)]`，使表格所有通道都不读取不可见文字。

---

## 3. v2：数值三列单元格规则

### 3.1 规则

`audit/table_extractor.py` `_build_three_column_mappings` 数值分支，每行在取值之前检查：

```python
if any(
    sum(1 for item in cell_values.get((row_index, col), []) if _looks_like_numeric_value(item.normalized_text)) > 1
    for col in (0, 1, 2)
):
    continue
```

含义：数值三列的一行要求左、中、右每个被用到的单元格最多只有一个数字。一个单元格里有多个数字，说明它是一个阵列（端口号条等），不是一个表格值。备注或表头前缀与一个数字共存时仍然允许。

### 3.2 为什么选这一种

| 候选约束 | 是否采用 | 理由 |
|---|---|---|
| 行带容差按行高比例 | 否 | P0001' 的中列与右列在同一行带内，容差约束排除不了它。 |
| 端口阵列（连续 1..N 等距小格）识别 | 否 | 需要新增几何模式识别，影响面和误伤面都不清楚。 |
| 外列必须与中列属于同一网格 | 否 | S0008 的全部线都属于同一个 BORDER 框加外框，网格一致性检查不能排除这些误配。 |
| **单值单元格：一个单元格最多一个数字** | **采用** | 直接对应“表格单元格存一个值”。只删数值分支的行，不影响表头语义、端子表、背板通道。语料中没有任何真实数值三列配对会被误伤（见 3.3）。 |

### 3.3 影响面统计与抽样

**全语料数值三列 pass 数**：round13 全语料中 `numeric_three_column` 的 pass 为 6 条，分布在 p055 S0012（P0001、P0002）和 p071 S0008（P0001、P0002）、S0009（P0003、P0004）。`_build_table_pairs` 对每个数值映射恰好产生一条 pass，因此 6 条即全部数值映射。全语料其它 `table_mapping` pass 均为 `terminal_header_table`（20,845）或 `backplate_virtual_table`（15,402），不经过本规则。

**静态复核（只读脚本 `tools/table_numeric_rule_impact.py`）**：对 DXF 缓存的每张页面，复原检测到的网格与单元格内容，比较规则前（OLD，与 v1 一致）与规则后（NEW）的数值映射。

- 全语料 dump：77 个项目、210 张页面全部扫描（运行状态 COMPLETE，无失败）。有三列网格的页面为 6 张（p055 S0010、S0011、S0012；p062 S0011；p071 S0008、S0009），规则前数值映射 4 条（OLD 4），规则后 0 条（NEW 0），删除 4 条，结果见第 6 节。
- 规则删除的数值映射为 p055 S0012 P0001、P0002 与 p071 S0008 P0001'、P0002。这 4 条全部被截图确认为假配对（第 1.5 节）。p071 S0009 的 P0003、P0004 在 v1 中已由隐形过滤去掉，规则对其无额外作用。

**抽样截图（全部 6 例，≤20 的要求）**：`fix_png/rule_p055_S0012_row1.png`、`rule_p055_S0012_row2.png`、`rule_p071_S0008_row4.png`、`rule_p071_S0008_row5.png`、`rule_p071_S0009_row3.png`、`rule_p071_S0009_row4.png`。另有 v1 的截图：`table_P0001_S0008.png`、`table_P0002_S0008.png`、`table_P0003_S0009.png`、`table_P0004_S0009.png`、`table_new_pass_S0008.png`。

**真配对是否受影响**：本语料中没有任何数值三列映射被判定为真配对（6 例全部为隐形残留或端口阵列误配）。因此规则没有误伤真配对。规则对表头语义、端子表、背板通道没有任何改动，它们的 pass 与 v1 逐条一致（见第 5 节）。

### 3.4 测试

- `tests/unit/test_superworks_loop_invisible_text.py` 新增两例：中列含两个数字时不产生配对（`test_three_column_row_with_crowded_middle_cell_is_not_a_value_row`）；右列含两个数字时不产生配对（`test_three_column_row_with_crowded_outer_cell_is_not_a_value_row`）。两例都保留了同表其它单值行的配对。
- 既有用例 `test_extract_table_pairs_prefers_numeric_text_when_cell_contains_note`、`test_extract_table_pairs_falls_back_to_numeric_mode_when_header_sequence_invalid` 最初因规则过严而失败（它们的单元格是“备注 + 一个数字”或“表头前缀 + 一个数字”，属于合法值单元格）。规则已收紧为“数字个数 > 1”，两例恢复通过，行为与设计一致。
- 全量：`python -m pytest tests/unit -q` → **1905 passed, 1 skipped**。

---

## 4. 回放（v2 vs v1 vs HEAD 基线）

快照：`.tmp/loop_invis_src2`（HEAD + 4 个改动文件，其中 `table_extractor.py` 为 v2）；v1：`.tmp/loop_invis`；HEAD 基线：`.tmp/loop_invis_base`。输出：`.tmp/loop_invis2`，对比脚本 `tools/compare_v2.py`，结果 `.tmp/loop_invis2_compare/compare_v2.json`。

| 项目 | 运行 | pass | review | discard | issue |
|---|---|---|---|---|---|
| p051 | BASE | 298 | 12 | 445 | 0 |
| p051 | v1 | 298 | 6 | 451 | 0 |
| p051 | **v2** | 298 | 6 | 451 | 0 |
| p062 | BASE | 206 | 6 | 326 | 2 |
| p062 | v1 | 206 | 2 | 330 | 0 |
| p062 | **v2** | 206 | 2 | 330 | 0 |
| p069 | BASE | 1233 | 214 | 345 | 0 |
| p069 | v1 | 1233 | 213 | 346 | 0 |
| p069 | **v2** | 1233 | 213 | 346 | 0 |
| p071 | BASE | 215 | 7 | 281 | 4 |
| p071 | v1 | 213 | 6 | 282 | 4 |
| p071 | **v2** | **211** | 6 | 282 | **3** |
| p075 | BASE | 1355 | 315 | 668 | 6 |
| p075 | v1 | 1355 | 313 | 670 | 4 |
| p075 | **v2** | 1355 | 313 | 670 | 4 |

**v2 vs v1（只看规则带来的变化）**：

- p071：pass 删除 P0001'（1↔1）与 P0002（1↔5）；issue 删除 `R-ONE-TO-MANY`（S0008）。其余 pass、review、discard 不变。
- p051、p062、p069、p075：与 v1 完全一致（0 处变化）。

**v2 vs HEAD 基线（完整，与 v1 的累计变化）**：

- p071 S0008：全部数值 pass 已消失（P0001、P0002、P0001'），`R-ONE-TO-MANY` 已消失。S0008 不再有任何 table pass，满足预期。
- p071 S0009：P0003、P0004（隐形中列）消失。
- p071 S0011：与 v1 相同（5 条双端 discard 消失，PC0053 review 消失；新增的 3 条块内引脚 discard 为主线程已接受的 PC0019'、PC0054'、PC0001'，另有两条无候选 discard）。
- 其它 target 变化与 v1 相同：p051 PC0075/104/127/152/203/204、p062 PC0019/120/121/125、p069 PC0074、p075 PC0232/440 的 review 消失，替换为无候选 discard。

**全量 pytest 与五项目回放的覆盖说明**：五项目回放不包含 p055。p055 S0012 的 2 条数值 pass 被删除，是全语料影响的一部分，见第 6 节。

---

## 5. 与 v1 相比未发生变化的内容（核对）

- 五项目的 issue 与 pass/review/discard 计数除 p071 外与 v1 完全一致。
- 表头语义、端子表、背板通道、输出接点矩阵的所有 pass 不变，因为规则只作用于数值三列分支。

---

## 6. 全语料影响面（完整，已扫描 77 个项目）

复核命令：`tools/table_numeric_rule_impact.py .tmp/loop_invis_dbg`，结果 `.tmp/loop_invis2_impact/table_numeric_rule_impact.json`。输入为调试快照（HEAD + v1 + dump 钩子，dump 为原始文字，不做隐形过滤之外的改动）在全部 77 个项目上的 `extract_table_pairs` 输入。

| 项 | 数量 |
|---|---|
| 扫描的页面 | 210 |
| 有三列网格（`cols == 3`）的页面 | 6（p055 S0010、S0011、S0012；p062 S0011；p071 S0008、S0009）。其中数值映射只出现在 p055 S0012 与 p071 S0008；其余 4 张页面没有数值映射（均未命中表头语义分支） |
| 规则前数值映射行（OLD） | 4 |
| 规则后数值映射行（NEW） | 0 |
| 规则删除的行 | 4 |
| 删除的行所在项目 | p055 S0012（2）、p071 S0008（2） |
| 其中判定为真配对 | 0（全部为端口阵列或隐形残留，见第 1.5 节） |

- 删除的 4 条都是假配对；被保留的真配对数为 0，因为语料中不存在被规则保留的数值映射。
- 任何未在上表中的页面不受影响：表头语义、端子表、背板通道、输出接点矩阵都不走数值三列分支。
- 注意：p055 不在五项目回放范围内，因此 p055 S0012 的两条数值 pass 删除是全语料影响，需要主线程知悉。

---

## 7. 限制与未覆盖项（主线程知悉）

1. `component_diagrams.py` 617、748 行对隐形数字的标签级使用没有被 pair 关联计数覆盖。本切片不改该文件。
2. `candidates.py` 标签查找（约 1433–1495 行）读取邻近文字，不经过候选门控，隐形文字仍可能作为标签参与。未改动。
3. BLOCKS 内的 125 个隐形数字无法按句柄映射到引擎的虚拟句柄，只报告数量。
4. 引擎对 MTEXT 使用 `char_height or 0.0`。若某条 MTEXT 缺少组 40，会被判为不可见。本语料全部 565,000 余条文字实体都带组 40，此情形为 0。
5. 规则基于“单元格只能一个值”的假设。在其它语料上，若出现合法的多数字单元格，规则会跳过该行（不会产生误配，但会漏掉真配对）。本语料中未观察到这种情况。

---

## 8. 产物

- 代码：`src/dwg_audit/domain/models.py`、`src/dwg_audit/extract/cad_extract.py`、`src/dwg_audit/audit/candidates.py`、`src/dwg_audit/audit/table_extractor.py`
- 测试：`tests/unit/test_superworks_loop_invisible_text.py`（11 例）
- 截图：`fix_png/rule_*.png`（6 例）、`fix_png/table_*.png`（v1 的 4 例与 `table_new_pass_S0008.png`）、`fix_png/rule_review_summary.json`、`fix_png/table_invisible_check.json`
- 脚本：`tools/table_invisible_check.py`、`tools/table_new_pass_check.py`、`tools/compare_invis_replay.py`、`tools/invisible_impact_static.py`、`tools/table_numeric_rule_impact.py`、`tools/table_rule_review.py`、`tools/compare_v2.py`
- 运行目录：`.tmp/loop_invis`（v1）、`.tmp/loop_invis2`（v2）、`.tmp/loop_invis_base`（HEAD 基线）、`.tmp/loop_invis_src`、`.tmp/loop_invis_src2`、`.tmp/loop_invis_head`（快照）、`.tmp/loop_invis_dbg`、`.tmp/loop_invis_dbg_pp`（调试 dump，仅用于复核，快照中含调试钩子，不在仓库内）、`.tmp/loop_invis_compare`、`.tmp/loop_invis2_compare`、`.tmp/loop_invis_impact`、`.tmp/loop_invis2_impact`，以及运行日志 `.tmp/loop_invis*.txt`
