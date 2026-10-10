# L-12 S1 修复记录：SuperWORKS 连接文字补全一侧缺失的旧链配对

## 修改

- `src/dwg_audit/audit/superworks_extractor.py`（仅此文件，+145 行）
  - 新增 `_fill_one_sided_pairs_from_connect_labels`，在 `extract_superworks_pairs` 的连接标签循环之后、字典告警之前调用。
  - 只处理：`pair_kind == "ordinary_pair"`、`ordinary_pair_eligible` 不为 False、`status != "discard"`、非 superworks 来源、恰好一侧为空、线组非纯 DIM 层、存在 present 侧坐标的配对。
  - 缺侧端定义：线组两端中，距 present 侧文字坐标较远的一端。
  - 补全条件（全部满足才补）：
    1. 连接文字锚点（`text.anchor_x/anchor_y`）到缺侧端距离 ≤ `SW_LABEL_MISSING_SIDE_TOL = 3.6`，且到 present 端距离 > 3.6；
    2. 同图页所有线端（任意线组的端点）中，只有缺侧端落在 3.6 窗口内（否则归属不明，不补）；
    3. 文字 `text_id` 未被任何 pair 使用（含 `left/right_text_id` 及 evidence 中所有 `*text_id` 字段）；
    4. 文字清洗（`_clean_sw_endpoint_value`）后非空、不含逗号分隔的多目标、不含 CJK（排除 `系统告警(NO3)` 类功能标签，口径 a 未定前保守处理）；
    5. 标签不带 `_TRUE_CONFLICTS` 中的冲突码，也不带 `ambiguous_connect_line` / `connect_line_geometry_not_unique`；
    6. 每个缺侧端只有唯一候选文字，每个文字只被唯一缺侧端认领。
  - 补全结果：缺侧 `*_value` 为清洗后的单一值，`*_text_id` 为文字 text_id，坐标为文字插入点；`status="review"`、`confidence_bucket="review"`，rationale 注明“legacy score does not apply”。`confidence` 保留原值（旧评分不适用，未重算）。
  - evidence 新增 `sw_missing_side_fill`：`source="superworks_connect_label"`、`side`、`connect_label_id`、`text_id`、`raw_value`、`value`、`anchor_distance`、`present_end_distance`、`tolerance`、`scoring="not_applicable_review"`。
  - ledger 追加一条 `reason="sw_connect_label_missing_side_fill"`，category 为 `A`（由 `_category` 判定：旧对不完整）。
  - 不修改已有两侧完整的 pair；不设置 `source="superworks"`，不改变其它规则对该 pair 的分类入口。
- `tests/unit/test_superworks_loop_l12_fill.py`（新增，14 条用例）：缺右侧/缺左侧补全；3.5 补全、4.0 不补（窗口边界）；多值不补；文字已被其它 pair 使用不补（含仅在 evidence 中引用）；两个线组共享同一缺侧端不补；同页其它线端进入窗口不补；短线两端均在窗口内不补；CJK 功能标签不补；ambiguous / true-conflict 标签不补；异页标签不补；两侧完整 pair 原样保留（同一对象）；非 ordinary 与 superworks 来源 pair 不补。

## 测试

- `pytest tests/unit/test_superworks_loop_l12_fill.py`：14 passed。
- `pytest tests/unit/test_superworks_extractor.py tests/unit/test_superworks_loop_l07.py` 等 superworks 相关用例：全部通过。
- `pytest tests/unit -q`（最终）：1780 passed, 1 skipped, 2 failed。失败为 `tests/unit/test_pairs_and_rules.py::test_rules_group_near_duplicate_line_claims_for_one_missing_side_text` 与 `test_rules_do_not_transitively_merge_duplicate_line_claims`。已验证：将 superworks_extractor.py 换回第七轮版本后同样失败；这两条用例不涉及 SuperWORKS 代码，失败来自并行子代理对 `rules.py` 的未完成修改（`_run_pair_missing_side` 的 duplicate claim 归属）。未修改这些文件。

## 单项目验证（p075 p041 p043 p000，快照含其它子代理进行中改动）

快照：`.planning/superworks-adapter/loopY2_src`（已删除）。探测目录 `.tmp/loopY2_probe`（已删除）。另建基线快照（第七轮 extractor + 当前其它文件）以隔离本次改动，已删除。

| 项目 | 变化（与基线相比，仅本改动） |
|---|---|
| p075 | pairs 2338 不变；仅 4 条 pair 改变（PC0123、PC0185、PC0331、PC0393，均为 GND 补全，status=review）；R-PAIR-MISSING-SIDE 70 → 66；R-PAIR-LOW-CONFIDENCE 0 → 4；总 issue 71 不变 |
| p041 / p043 / p000 | issues 与 pairs 与基线完全一致（0 差异） |

- 与第七轮数据（`.tmp/superworks_round7_full`）比较：p075 的 issue 数与第七轮一致（71）。p000 的 10 条 SuperWORKS pair 与第七轮不同，但基线（第七轮 extractor + 当前其它文件）与本次结果逐条一致，故这 10 条差异与本次改动无关，来自第七轮之后其它文件的改动。
- 补全 pair 的状态分布：review 4，pass 0（按要求不强制 pass）。
- 差异逐条：
  - 移除 R-PAIR-MISSING-SIDE：PC0123、PC0185、PC0331、PC0393。
  - 新增 R-PAIR-LOW-CONFIDENCE：同上 4 条（因补全后 status=review 且两侧完整，原先由缺侧规则报告的问题转由低置信规则报告）。

## 与预期（约 20）的差距与原因

预期 20 条未达成，只补了 4 条。原因是 README 所用的“文字锚点”与“插入点”测量给出不同结论：

- 按用户指定的锚点（`anchor_x/anchor_y`）测量：p075 的 YD*/1-26DK* 标签锚点位于 y=100，与相邻两行线端 97.5 和 102.5 的距离均为 2.69，无法区分归属。窗口内出现另一线端即按规则拒绝（fail-closed）。共 20 条（sheet 14 和 15 各 10 条）因此不补。
- 按插入点测量（README 所用口径）：这 20 条的插入点到归属行线端 1.41，到相邻行 4.12，唯一最近，归属清楚。README 的 20 条即来自此口径。
- 4 条 GND 补全的锚点距缺侧端 3.04，同图页其它线端最近 5.41，无歧义，已补全。

结论：锚点口径不能消解这 20 条的归属，需要口径决定。选项：
1. 维持锚点口径（本次实现）：仅 4 条补全，其余 20 条继续报 MISSING-SIDE。
2. 改用插入点并取最近归属（需用户确认）：预计再补 20 条，但文字插入点与 SW 引线端位置不一致，且会把“最近”当作唯一依据，需用户确认这是否符合 SuperWORKS 标签的图面含义。

本次未擅自改口径。

## 3.6 依据

- L-07 测试 `test_gnd_style_offset_from_anchor_still_associates`：GND 类标签锚点与引线端相距约 3.6。
- 本次实测补全的 GND 锚点距缺侧端 3.04，在窗口内；同页最近的其它线端 5.41，在窗口外。
- 锚点测量下相邻行线端仅相距 2.5 单位（锚点到两端均为 2.69），单靠 3.6 窗口无法消歧，故增加“同页其它线端不得进入窗口”的守卫。

## 截图

路径：`.planning/superworks-adapter/loop/L-12/fix_s1_png/`
- `L12S1_1_PC0123_filled.png`、`L12S1_2_PC0185_filled.png`、`L12S1_3_PC0331_filled.png`、`L12S1_4_PC0393_filled.png`：补全的 4 例（橙色为补全线组，绿色虚线为锚点到缺侧端，蓝色为 SW 连接文字锚点）。
- `L12S1_5_PC0051_control.png`、`L12S1_6_PC0130_control.png`：未补全的对照（红色为缺侧线组，文字锚点位于两行之间）。
- 说明：只有 4 例补全，故以 4 例补全加 2 例对照代替“6 例补全”。截图为直接用 PIL 绘制线段与文字，未使用 ColorPolicy。

## 未决口径

- a. 同行中部功能标签（系统告警(NO3)）：本次以 CJK 字符排除，未定正式规则。
- b. 一线两目标 `& 2-1KLP12-1,2-1KLP2-1`（p041–p044）：本次不补，留待口径。
- c. 锚点与插入点的归属口径（见上）。

## Y2b：文字外框归属（替代锚点测距）

### 修改

- `src/dwg_audit/audit/superworks_extractor.py`
  - 归属改用文字外框：`text_map[text_id].text_geometry_json` 的 `corners`（SW 连接记录本身不含外框，按 text_id 关联）。缺侧端、在位端到外框的距离，点在框内为 0。
  - 守卫（全部满足才补）：缺侧端外框距离 ≤ `SW_LABEL_BOX_TOL_HEIGHTS × 字高`（1.5，即 p075 的 3.0 字高时窗口 4.5）；在位端外框距离 > 窗口；缺侧端之外同图页最近线端的外框距离 − 缺侧端外框距离 ≥ `SW_LABEL_SEPARATION`（1.0）；未占用、单值、非 CJK、无真冲突码、无歧义线码、唯一候选、唯一认领、同图页、无外框则不补（均与 Y2 相同或为 fail-closed）。
  - 删除 `SW_LABEL_MISSING_SIDE_TOL = 3.6` 与锚点距离口径。
  - 证据 `sw_missing_side_fill` 字段：`attribution="text_bbox"`、`bbox_distance`、`present_end_bbox_distance`、`second_end_distance`（无其它线端时为 None）、`tolerance`、`separation_min`、`text_height`；其余字段不变。
  - 函数外仅一处改动：调用点新增 `text_map` 参数（`extract_superworks_pairs` 中已有该变量）。新增 `import json`。
- `tests/unit/test_superworks_loop_l12_fill.py`：20 条。原 14 条的语义保留，锚点改为外框（测试用例中的外框由锚点按 4.1 高的底边居中框构造）；新增 6 条：锚点居中但外框贴近所属行则补；外框与两行等距则不补；窗口随字高缩放；无外框不补；标签在线端右侧、次近间隔 1.24（GND 形态）则补；分隔常量。

### 阈值依据

- 窗口 1.5 字高：任务指定的约 1.5 倍字高。p075 字高 3.0 的窗口为 4.5，旧锚点窗口 3.6 相当于 1.2 字高。
- 分隔 1.0：任务给出的下限示例。首版取 `max(1.0, 0.5×字高) = 1.5` 时，p075 原有的 4 条 GND 补全（PC0123、PC0185、PC0331、PC0393，外框距缺侧端 3.00，次近线端 4.24，间隔 1.24）被拒绝，p075 的 R-PAIR-MISSING-SIDE 由 66 升到 70、LOW-CONFIDENCE 由 4 降到 0。已改为 1.0 并复验恢复。

### 测试

- `pytest tests/unit/test_superworks_loop_l12_fill.py`：20 passed。
- `pytest tests/unit -q`：1803 passed, 1 skipped, 0 failed（本轮 rules.py 相关的两条失败已不再出现）。

### 关键事实（与任务前提不符，需用户确认）

1. 改动前基线中，p075 的 332 条 SW 连接文字全部已被 pass 对直接引用（`left_text_id` / `right_text_id`），空闲连接文字为 0。YD* 与 1-26TD* 由 SW `component_mapping` 对（PSW*、PCV*）占用。因此 p075 页14/15 的 20 条旧链单侧对（如 PC0051、PC0057，缺侧文字为 YD10 等）没有可用的空闲文字，外框规则无论怎样都无法补全。原 FIX_S1 中“20 条仅是口径问题”的前提在当前基线下不成立，本次新增补全为 0。
2. 示例 YD10 的外框实测：所属行（y=97.5）距 1.000，相邻行（y=102.5）距 1.414，间隔 0.41，低于分隔 1.0，按本规则不补。FIX_S1 中 1.41 / 4.12 是插入点口径，不是外框口径。
3. 相邻行 5 单位间距、字高 3.0 的标签，外框与相邻行的间隔受框高限制，几乎无法达到 1.0；要让此类标签可归属，需降低分隔（约 0.4 以下），放宽唯一性，风险较高，需用户决定。

### 单项目验证（p075 p041 p043 p000）

快照 `.planning/superworks-adapter/loopY2b_src`（已删除），基线为改动前同快照（`loopY2b_base_src`，已删除）。探测目录 `.tmp/loopY2b_probe`（已删除）。

| 项目 | 补全条数 | pair 差异（相对改动前） | issue 差异 |
|---|---|---|---|
| p075 | 4（同基线：PC0123、PC0185、PC0331、PC0393，GND） | 0 | 0（71 不变，R-PAIR-MISSING-SIDE 66 不变，LOW-CONFIDENCE 4 不变） |
| p041 | 0 | 0 | 0 |
| p043 | 0 | 0 | 0 |
| p000 | 0 | 0 | 0 |

预期“约 24 = 原 4 + 新 ~20”未达成：新增 0。原因见上文事实 1。

### 截图

路径：`.planning/superworks-adapter/loop/L-12/fix_y2b_png/`
- `PC0123_filled.png`、`PC0185_filled.png`、`PC0331_filled.png`、`PC0393_filled.png`：补全的 4 例（橙色为线组，绿色为连接文字外框，红圈为缺侧端，蓝圈为在位端，紫线为缺侧端到外框的距离 3.00，灰线为同图页线）。已逐张核对：归属方向、距离与标注一致。
- `PC0051_control.png`、`PC0057_control.png`：未补全对照。最近的 YD10 外框已被 PSW pass 对占用，图中有标注。
- 说明：本次没有新的补全，故无 6 例新补全截图；以 4 例已补全加 2 例对照代替。

### 未决（需用户决定）

- A. 旧链单侧对与 SW pass 对重复占用同一文字（YD*、1-26TD*）：应按 SW 对为准归并旧单侧对，还是保持 MISSING-SIDE？这需要改动 pair 归并规则，不在本次范围。
- B. 分隔阈值：1.0 保住 4 例；若要覆盖相邻行间隔 0.41 的标签，需降到 0.4 以下，需用户确认。
- C. 旧未决口径 a、b 仍然存在（见上）。
