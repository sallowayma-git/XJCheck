# Z-1 修复：表格边框行的单侧重复（台账类别 H）

## 1. 改动

- `src/dwg_audit/audit/superworks_extractor.py`：新增常量 `BORDER_MIDLINE_TOL_FRACTION=0.15`、`BORDER_TEXT_TOL_HEIGHTS=1.5`、`BORDER_HORIZONTAL_TOL=0.01`、`BORDER_NEIGHBOUR_MIN_SPAN_FRACTION=0.5`、`TABLE_BORDER_REASON`；新增辅助函数 `_is_virtual_horizontal_line`、`_connect_line_ids`、`_border_neighbours`、`_bbox_corners`；新增 `supersede_border_row_duplicates(pairs, ledger, lines, line_groups, texts)`，位于 `supersede_equivalent_component_duplicates` 之后。
- `src/dwg_audit/pipeline.py`：在 `supersede_equivalent_component_duplicates` 调用之后加一处调用（4 行），传入 `audit_lines, line_groups, audit_texts`。
- `tests/unit/test_superworks_loop_z1_border.py`：新增 15 个用例。
- 未改动 SW 行、未删除任何 pair、未动 git。

## 2. 判定（全部满足才 discard）

1. 旧对：`ordinary_pair`，恰一侧有值，非 discard，`ordinary_pair_eligible` 不为 False，非 superworks 来源，线组非 DIM 层（复用 `_fillable_one_sided_pair`）。
2. 线组成员全部为 `:VIRTUAL:` 句柄且为水平线。
3. 缺端 M = 距在位端较远的一端（复用 `_missing_end_points`）。
4. 邻边框 N：同一表格（句柄 `:VIRTUAL:` 前缀相同）、水平 VIRTUAL、覆盖 M.x、与 M 所在边框的共同跨度不小于 M 边框跨度的 50%；取 M 上方与下方各最近的一条。
5. 同页 SW pass 行 S 的连接短线端点 E 满足：|E.y − midline| ≤ 15% × 间距（midline = (M.y+N.y)/2，间距 = |N.y−M.y|），且 E.x 落在两边框共同跨度内（容差同为 15% 间距）。
6. S 的 `external_endpoint_text_id` 外框到 M 的距离 ≤ 1.5 × 字高。
7. 同一旧对若有多条合格 S（上下两侧各一行），全部记入台账；evidence 中 `sw_pair_id` 取中点偏差最小者，`sw_pair_ids` 列出全部。
8. 多条旧对认领同一 S 时，全部按边框 discard（R1）。

动作：旧对 `status="discard"`，`rationale="table_border_row_duplicates_sw_connect_stub: <S ids>"`，`evidence["table_border_row_duplicate"]` 记录 S、邻边框句柄、中点、偏差、文字距离与上限；台账追加 `category="H"`，`reason="table_border_row_duplicates_sw_connect_stub"`，`new_pairs` 为合格的 S（未改动）。

## 3. 与任务说明的偏差（需复核）

- 第 4 条新增「共同跨度不小于 50%」。原因：SW 引脚标记是 1 单位的 VIRTUAL 短划线（如 `3214C:VIRTUAL:890:0`，x 74.5–75.5，位于行中心 y=100），比真实边框 y=102.5 更近，且覆盖 M.x=75。若按“最近的水平 VIRTUAL 线”取邻边框，会取到短划线，中点判定全部失效（首次探测 p075 仅 discard 0 条）。加入跨度条件后，邻边框为整行边框。
- 第 5 条新增 E.x 位于两边框共同跨度内。任务说明未写 x 条件，这是为防止行中段的任意连接短线被误配。
- 第 7 条：任务说明的“唯一 S”未作为硬约束。中间版本要求唯一，结果漏掉 8 条（PC0069、PC0099、PC0137、PC0197、PC0277、PC0307、PC0345、PC0405：边框两侧各有一行 SW 短线，且两者都满足 4–6）。去掉唯一约束后，这 8 条按 R1 全部 discard。
- `ordinary_pair_eligible` 字段在这些旧对上缺失（不是 True）。按 `_fillable_one_sided_pair` 的约定，缺失视为可用。
- 第 6 条：外框优先取 `text_geometry_json` 的 corners；无 corners 时退回 bbox（代码中有，探测数据未专门统计其触发次数）。
- SW 连接线：优先 `superworks.connect_line_id`，无则 `supporting_line_ids`；`connect_line_geometry_unique is False` 的行不用。

## 4. 单元测试

`tests/unit/test_superworks_loop_z1_border.py`，15 项：
- 满足条件 → discard，台账 H，S 不变，未删除 pair；
- 中点容差内 0.7 → discard，超出 1.0 → 保留；
- 位于边框行本身的短线不算中点；
- 非 VIRTUAL 线组、非水平线组、无 SW pass 行、SW 连接线几何不唯一、非同页、非共同跨度、他表邻边框、文字距离 4.4（discard）/ 15（保留）、eligible=False、superworks 来源 → 保留；
- 1 单位 SW 短划线不得遮蔽真实邻边框；
- 上下两条边框共同认领同一 S → 两条都 discard，且 evidence 指向同一 S；
- 同一边框两侧各有合格 S → 台账记录两条 S。

全量：`pytest tests/unit -q` → 1818 passed, 1 skipped。

## 5. 单项目验证

探测：`replay.py --output .tmp/loopZ2_probe --snapshot .planning/superworks-adapter/loopZ2_src --workers 3 --projects p075 p072 p037 p070 p062`（快照由当前 src 复制，已删除）。对照基线：第八轮 `.tmp/superworks_round8_full`；另用与 src 相同但去掉调用的快照（已删除）复跑 p075/p072/p037/p070/p062 作为同代码对照，并单独复跑 p037 一次。

**p075**
- 旧对 discard 32 条（台账 H 32 行）；其余 2306 条的 status、rationale、evidence 与第八轮完全一致。
- R-PAIR-MISSING-SIDE：66 → 40（减少 26）；issues 总数 71 → 45。
- 32 条中，**26 条与 Z-1 G1 “报”清单完全一致**：PC0051、PC0057、PC0063、PC0069、PC0075、PC0081、PC0087、PC0093、PC0099、PC0130、PC0137、PC0191、PC0197、PC0259、PC0265、PC0271、PC0277、PC0283、PC0289、PC0295、PC0301、PC0307、PC0338、PC0345、PC0399、PC0405。
- 其余 6 条为 Z-1 “抑”清单：PC0105、PC0144、PC0203、PC0313、PC0352、PC0411。它们与报告的 PC0099/PC0137/PC0197/PC0307/PC0345/PC0405 共享同一 SW 行，按 R1 也应 discard。这 6 条在第八轮中没有 issue，因此不影响 issue 计数。
- issue 变化：删除的 66 条均为 R-PAIR-MISSING-SIDE，新增的 40 条为同规则的重算（G2 issue 的 `review_group_size` 由 33 变为 20，其余字段不变）。

**p072、p037、p070、p062**
- 与第八轮逐条一致：pairs 的 status/rationale/kind/值/文字 id 全部一致，discard 0 条，台账 H 0 行，issues 与第八轮逐条相同（p072 4 条、p037 1 条、p070 0 条、p062 2 条）。
- p037 有 2 条 `evidence` 中的 enclosure 浮点数（如 width 265.0 与 265.21）不同。同一基线两次复跑也出现这类差异，与本改动无关；status 与 issue 均未变。

Z-1 风险核对：
- R1（同一 YD 文字被上下两条边框认领）：按整体边框处理，两条都 discard（见 F02、F03）。
- R2（纯文字共享）：未使用文字共享规则。p072、p037、p070 没有受影响。
- R3（G2 的 42 条无 SW 对应）：未动（F05、F06 为保留示例）。
- R4（跨项目）：本次只验证了 p075 与另外 4 个项目，未做全量回放。

## 6. 截图（`fix_png/`，逐张确认）

- `F01_PC0051_discard_upper_stub.png`：旧线 97.5，上邻边框 102.5，中点 y=100 的 SW 短线 PSWdcc6a（YD10）位于 1.5 字高圆内；y=100 的 1 单位引脚短划线被标注为不作邻边框。确认：discard 正确。
- `F02_PC0099_discard_two_sided.png`：边框 137.5 两侧中点分别有 SW 行（y=140 YD1，y=135 YD8）。确认：两侧都合格，两条 SW 都进台账。
- `F03_PC0105_discard_shared_stub.png`：边框 142.5 的唯一合格 SW 行为 y=140 的 PSW1bdd，与 PC0099 共享。确认：按 R1 discard。
- `F04_PC0191_discard_1-26DK.png`：1-26DK 行，边框 212.5，中点 y=215 的 PSW7e3e（1-26DK1-2）。确认：discard 正确。
- `F05_PC0039_kept_no_sw.png`：边框 82.5 的中点 85 与 80 处无 SW 连接短线。确认：保留。
- `F06_PC0117_kept_no_sw.png`：边框 152.5（x 35–55）的中点处无 SW 连接短线。确认：保留。

## 7. 残留风险

- 6 条“抑”对按 R1 也被 discard。它们在本次 issue 计数中不产生变化，但口径上与 Z-1 的“报 26”不同。
- 邻边框跨度 50%、E.x 跨度条件是本次新增的约束（见第 3 节），只在 p075 验证过。
- 未做全量回放，其他项目的影响仅由 4 个项目与 p075 的探测推断。
