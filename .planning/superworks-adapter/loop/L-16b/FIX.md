# L-16b 修复说明：rules.py 第七轮多对一与缺端口径（Y3-a / Y3-b / Y3-c）

范围：只改 `src/dwg_audit/audit/rules.py`，新增 `tests/unit/test_superworks_loop_l16b_rules.py`（15 项）。未改 superworks_semantics.py、superworks_extractor.py、candidates.py。未做 git 操作，未全量回放（离线只重算规则，数据为 `.tmp/superworks_round7_full`）。

## 1. 结论

| 项 | 结果 |
|---|---|
| R-MANY-TO-ONE | 18 → 14，消除 p061 4 条（1-21QD77、2-21QD31、3-21QD31、4-21QD71） |
| R-PAIR-MISSING-SIDE | 81 → 81，**无变化**（S3 未改变任何 owner，见 §4） |
| R-CROSS-PAGE-CONFLICT / R-ONE-TO-MANY / R-DUPLICATE-PAIR | 无变化（38 / 0 / 0，直接调用 runner 核对） |
| 其它规则 | 无变化（全流水线 issue 集合差异仅上述 4 条） |
| 全量 `pytest tests/unit -q` | 1808 passed, 1 skipped（含本次 15 项） |

## 2. 改动位置（rules.py 当前行号）

| 行号 | 内容 |
|---|---|
| 232 | `_PIN_NAME_COMPONENT_PAIR_KINDS`（component_mapping / wire_component_mapping） |
| 235 | `_pin_alias_index`：按右端终端身份索引全部记录（只分组，不判定） |
| 247 | `_same_pin_alias_roots`（Y3-a）：同 sheet 且同 right_text_id 上，表格记录与元件记录共存时，左名归并为同一针脚（并查集） |
| 281 | `_is_terminal_table_device_record`：背板端子表设备侧记录（mapping_mode=backplate_virtual_table，端子位于 external_terminal_endpoint 列） |
| 294 | `_is_two_sided_terminal_passthrough_group`（Y3-b）：归并后恰好两个左身份；一侧为设备侧表格记录（可含同针元件记录别名），另一侧为普通外线且与设备侧不同 sheet |
| 1518 | `_run_many_to_one`：构建 `pin_index` |
| 1538 | 在 `effective_lefts` 之后做 Y3-a 归并；归并后身份数 ≤1 则跳过 |
| 1552 | 在 R3 端子排一行判定之后做 Y3-b 豁免 |
| 467–474 | S3 的 duplicate_text_line_claim 的 extra 增加 `owner_line_group_id`、`non_owner_line_group_ids`；explanation 文案同步 |
| 566 / 595 | `_missing_side_text_claim_rank` 改为先比较文字锚点到线段的距离（`_point_segment_distance`），再比较 y 间隙、分数、长度、id |

## 3. 各项判定依据（结构字段，无值形态特判）

- Y3-a：`pair_kind`（table_mapping / component_mapping / wire_component_mapping）、`sheet_id`、`right_text_id`、右值终端身份。仅当同一 (sheet, right_text_id) 上同时存在表格记录与元件记录时才归并；两个都是表格记录、或 sheet/text id 不同，均不归并。
- Y3-b：`pair_kind == table_mapping`、`table_mapping.mapping_mode == backplate_virtual_table`、`column_roles.right == external_terminal_endpoint`（端子在表格外侧列）；外线侧为 `ordinary_pair` 且 `ordinary_pair_eligible` 非 False；两侧 sheet 不得相同。
- S3：线段距离（文字锚点到线组线段的最近距离），与现有 `_near_duplicate_missing_side_line_groups` 的近邻条件（y 差 ≤6、重叠 ≥35%）共用。

## 4. 与任务预期不一致之处（如实记录）

1. **Y3-a 在第七轮数据上不单独消除任何条目。** p061 的 1-21n320 元件记录（PSW52443，S0020，T3343）不在高置信图中（`ordinary_pair_eligible=False` / `component_mapping` 未入组），因此多对一分组里只有 `1-21n/BI2-20` 与 `1-21GD17` 两个左身份，归并无可作用。p061 的 4 条消除来自 Y3-b。Y3-a 已实现（含正反例单元测试证明其机制），但对当前语料为空操作（离线统计：归并次数 0）。
2. **S3 在第七轮数据上没有可消除的条目（预期约 8 条，实际 0）。** 8 个共享文字案例（p075 页14/15 的 `01`、`04`、`05`）中，文字锚点到线段的距离与原 y 间隙给出的 owner 相同（如 PC0131 为 owner，PC0138 为非 owner），且现有代码已经对非 owner 不单独报缺端（`duplicate_related_ids`），即已是“一个文字一个缺侧问题”。因此 S3 的落地只是把 owner 选择口径换成距离，并把非 owner 的线组写入 `non_owner_line_group_ids`，输出不变。
   - 未删除 `related_pairs` 中的非 owner：`tests/unit/test_pairs_and_rules.py` 的 `test_rules_group_near_duplicate_line_claims_for_one_missing_side_text` 与 `test_rules_do_not_transitively_merge_duplicate_line_claims` 固定了“关联全部线组”的契约（`related_pair_ids` 长度为 1）。删除会破坏这两项，且该文件不在允许修改范围内，故保留。
   - 因此 L-12 表中 S3 “预计消除 8” 在本数据上不成立，应改为“口径修正，计数不变”。
3. **Y3-b 的结构判定也命中 p040 的 1YD1、2YD1 两组**（右值 1YD1、2YD1 的 table 设备侧 + 外线结构）。这两组在第七轮基线中本就未报出，输出不变；但其跨装置 DC+ 的设计意图仍需工程确认（L-16b README §1），本次不改变该结论。p040 的 1GD1、2GD1（3 个左身份）不满足“恰好两个”，未被豁免，仍按 L-16b 结论保留。

## 5. 离线结果（第七轮 77 项目，全流水线 build_issues）

基线为修改前的 src 快照，修改后为仅替换 rules.py 的同一快照（避免其他并行修改干扰）。基线重算与 round7 `issues.parquet` 对照：R-MANY-TO-ONE 18、R-PAIR-MISSING-SIDE 81、R-PAIR-LOW-CONFIDENCE 10、R-SUPERWORKS-CONFLICT 17、R-CROSS-PAGE-CONFLICT 3，合计 129，与 parquet 一致。

差异明细（逐条）：

| # | 项目 | 规则 | 右值 | 左值 | 原 primary / related | 结论 |
|---|---|---|---|---|---|---|
| 1 | p061 | R-MANY-TO-ONE | 1-21QD77 | 1-21n/BI2-20（与 1-21GD17） | P0139 / PW0209 | 消除（Y3-b） |
| 2 | p061 | R-MANY-TO-ONE | 2-21QD31 | 2-21n/BI1-21（与 2-21GD17） | P0227 / PW0192 | 消除（Y3-b） |
| 3 | p061 | R-MANY-TO-ONE | 3-21QD31 | 3-21n/BI1-21（与 3-21GD17） | P0315 / PW0185 | 消除（Y3-b） |
| 4 | p061 | R-MANY-TO-ONE | 4-21QD71 | 4-21n/BI2-20（与 4-21GD17） | P0431 / PW0224 | 消除（Y3-b） |

其余：R-MANY-TO-ONE 保留 14 条（GND 9、p039 ×2、p040 的 1GD1、2GD1、1ZK-3 共 3），R-PAIR-MISSING-SIDE 81 条逐条不变（8 条 duplicate_text_line_claim 的 owner 与 primary 不变，related 不变）。R-CROSS-PAGE-CONFLICT 38（原始 runner）/ 3（流水线）不变。R-ONE-TO-MANY 与 R-DUPLICATE-PAIR 均为 0，不变。R-DUPLICATE-SAME-LINE 与 R-SUPERWORKS-CONFLICT 不在本次改动路径内，不变。

## 6. 单元测试

`tests/unit/test_superworks_loop_l16b_rules.py`（15 项，全部通过）：

- Y3-b：正例（设备侧表格 S20 + 外线 S08，1-21QD77 形态）；反例：两条外线、两条设备侧表格、外线与设备侧同 sheet、terminal 不在外侧列、第三个左身份，均仍报。
- Y3-a：正例（表格 1-21n/BI2-20 + 元件 1-21n320 + 外线，三身份归并后消除）；正例（仅两个同针名也不成多对一）；反例：不同 sheet、不同 right_text_id、两个表格记录，均不归并、仍报。
- S3：正例（两平行线组共享文字，近者为 owner，非 owner 不单独报，输出含 owner/non_owner 字段）；正例（文字靠近 GB 时 GB 为 owner，与 pair 顺序无关）；反例（y 相距 28 的两组，各自报）；点到线段距离函数。

对照（同一测试文件对修改前的 rules.py 运行，pytest `-o pythonpath=` 指向快照）：5 项正例失败、9 项反例通过，说明正例确实依赖本次改动、反例保持原行为。

全量：`pytest tests/unit -q` 为 1808 passed, 1 skipped。

## 7. 限制

- 离线重算只覆盖 pairs 的规则层，不含 producer；并行修改中的 candidates.py / pairs.py / superworks_extractor.py 的改动未纳入离线对比（对比基于快照）。
- Y3-b 的设备侧识别依赖 `mapping_mode == backplate_virtual_table`；其它端子表模式（如 terminal_header_table）不在豁免范围内，若语料中出现同类直通端子需另行结构化。
- 离线脚本位于 scratchpad（`l16b_r7/eval.py`、`raw.py`、`instr.py`），未写入仓库。
