# Z-6 修复说明：候选级"数字标签归属他线端点"规则（未达成目标，不建议按当前版本合入）

范围：`src/dwg_audit/audit/candidates.py`（修改）、`tests/unit/test_loop_z6_candidates.py`（新增）。未改 rules.py，未做 git 操作，未全量回放。

## 1. 结论
- 规则已实现，单元测试与全量 `tests/unit` 通过（1854 passed，1 skipped）。
- pass 配对零影响：第十一轮语料与 5 项目探测中，pass 配对的状态与取值均未变化。
- **9 条 R-PAIR-LOW-CONFIDENCE 目标未修复**：它们的"他线"都是 SuperWORKS 补充线组（`GWSW...`），在候选阶段不可见，规则无从判定。见第 4 节。
- 生产探测中规则还带来副作用：新增 3 条 `R-PAIR-MISSING-SIDE`，多组 review/discard 配对变化（第 5 节）。在输入问题解决前，建议不合入当前版本。

## 2. 修改内容（candidates.py）
- `build_terminal_candidates` 中，与 `label_bound_to_other_physical_port` 同层新增分支（紧随其后）：
  条件为 `value.isdigit()` 且 `not physical_evidence`，且 `_is_label_bound_to_other_line_endpoint(...)` 为真，则 `rejection_reason = "label_bound_to_other_line_endpoint"`，`score = 0`。
- 判据：锚点（`text.insert_x/y`）到本线对应端点距离为 `own`；在半径 `1.5 × 字高` 内查找他线端点，记其距离为 `foreign`。当 `foreign ≤ own / 3` 且 `foreign ≤ 1.5 × 字高` 时拒绝。
- 新增 `_LineEndpointIndex`（每图纸一份，STRtree 查询，排除本线组）。
- 偏离规格的一处（需确认）：若半径内有**两条及以上不同他线**的端点（共享数字锚点），则不判定为归属他线，留给既有 shared-anchor 逻辑。原因：既有测试 `test_build_terminal_candidates_keeps_shared_numeric_anchor_when_q_owner_is_ambiguous`（`test_terminal_candidates.py:836`）在纯相对判据下失败（T3"801"同时贴近 G1、G2 端点，G3 候选被拒），而本次不允许修改该测试文件。
- 偏离说明二：新分支位于 physical 分支之后，已被其他原因拒绝的数字候选会改标为新原因（状态不变）。离线统计中此类改标 5 项目共约 166 处（actual_only）。

## 3. 测试
- `tests/unit/test_loop_z6_candidates.py` 5 例，全部通过：
  1. 他线端点紧邻文字（距 1.6），本线端点远（9.1）→ 本线候选 rejected，reason 为新原因，他线候选 accepted。
  2. 本线端点最近（1.4），他线端点 3.0 远（> 1/3）→ 本线 accepted，且无新原因。
  3. 两端都远（他线 9.0 > 1.5×字高）→ 不受规则影响。
  4. 两条他线共享锚点 → 本线 G1 accepted，不受新规则影响。
  5. 非数字标签（"AB"）→ 不受新规则影响。
- `pytest tests/unit/test_terminal_candidates.py tests/unit/test_loop_l16_candidates.py tests/unit/test_loop_z6_candidates.py`：78 passed（修改 shared 保护前有 1 例失败，已修复）。
- `pytest tests/unit -q`：1854 passed，1 skipped（运行时工作区含并行 rules.py 与 `test_superworks_loop_z6_m2o.py`，全部通过）。

## 4. 9 条目标为何未被修复（关键发现）
- 规则依赖的"他线"在离线数据中来自最终 `line_groups` 表。但 9 条目标的他线全部是 SuperWORKS 补充线组：
  PW0295 `GWSW0ecc42907ff73daa`；PW0063 `GWSW61c874da12800223`；PW0065 `GWSWf50c9200876ec0e1`；PW0111 `GWSW2673d84671cf8c2a`；PW0113 `GWSWd1beff9b29401a48`；PW0119 `GWSWca162f213e1250c3`；PW0096 `GWSWbb4d7f71c97affe9`；PW0098 `GWSWef20d98a35ac84b1`；PW0104 `GWSW369bf163f94a77f0`。
- `superworks_extractor.py:728-732` 在 `build_line_groups` 之后才 `line_groups.append(supplemental)`，而 `build_terminal_candidates` 仅在 `page_extractors.py:168` 调用，传入的是 legacy 线组。候选阶段看不到这些线，因此规则在生产中对 9 条目标均不生效（探测中 9 条目标的 CW 候选仍为 accepted）。
- 离线统计（使用含 GWSW 的最终表）曾显示 9 条目标全部可被拒，这一口径不符合生产，已作废。
- 数值复核：他线端点到锚点距离实测 1.55–1.61，本端距离 9.07（README 的"1.0–1.3"为另一度量口径）。
- 要真正修复，需让候选阶段看到 SW 补充线组（改动 page_extractors.py / superworks_extractor.py 的顺序或传参），超出本次允许的文件范围。若做此改动，需重做离线与探测。

## 5. 离线评估（全语料 77 项目）
口径：候选阶段可见的线组（排除 `GWSW` 前缀）。该口径已用对照运行校验：基线已接受候选中，离线命中与实际改标完全一致（offline_only = 0；p064/p067/p072/p073/p000 分别为 114/37/62/16/34）。

| 指标 | 结果 |
|---|---|
| 已接受数字候选（无物理绑定） | 52770 |
| 新规则拒绝（accepted→rejected） | 4646（8.8%） |
| 被 pass 配对精确选中的候选被拒 | **0** |
| 宽松口径（无候选 ID 的 pass 配对，文本与取值匹配） | 180，全部为 `inline_body_port_mapping`（177）与 `inline_two_port_component`（3），两条路径均不消费终端候选（wire_components.py / backplate_components.py 无引用） |
| 被 review 配对选中后被拒 | 573 个选中引用 |
| 被 discard 配对选中后被拒 | 1060 个选中引用 |

被拒的选中候选本端距离统计：均 > 3 单位（无本端贴近被拒的情况）。

注：早期含 GWSW 口径得到的 6313 被拒数字已作废（见第 4 节）。另，README 的"2462 / 1191"无法精确复算：按"6–10 单位、dx≤3、数字文字"的定义，本次得到 2642 个候选。

## 6. 单项目探测
- P1：当前 src 快照（`loopAB_src`，含并行 rules.py）；C：第十一轮 src + 本次 candidates.py（对照，隔离我的改动）。
- **P1 与 C 完全一致**（5 项目 pairs、issues 均无差异）：并行 rules.py 的当前改动对这 5 项目无影响，差异归因于本次 candidates.py。
- 9 条目标新状态（P1 与第十一轮相同）：全部仍为 `review`，配对不变（如 PW0295 5QD3↔13；PW0063 8QD4↔13；PW0065 14↔8QD8；PW0111 1QD4↔13；PW0113 14↔1QD22；PW0119 14↔1QD19；PW0096 1QD4↔13；PW0098 14↔1QD22；PW0104 14↔1QD19）。
- PW0256（p000）：`review 4P1D2↔12` → `discard`，其 LOW 问题消失。此变化来自 legacy 邻线 GW0257 的端点，规则在此生效。是否应记为"无配对"需口径确认。
- 副作用：新增 3 条 `R-PAIR-MISSING-SIDE`（均为 review）。
  - p064 PW0501：discard 831↔132 → review 仅 132（831 被拒，距 GWSW8f538158210b92f6 端点 1.08）。
  - p067 PW0118：discard 831↔132 → review 仅 132（同类）。
  - p072 PW0202：discard 1731↔832 → review 仅 832。
- issues 变化：p064 2→3；p067 2→3；p072 4→5；p073 3→3；p000 2→1。
- 配对（status/left/right）变化数：p064 43；p067 11；p072 19；p073 10；p000 23。变化全部在 review/discard 之间，pass 为 0。

## 7. 需要口径 / 决策
1. 是否允许候选阶段看到 SW 补充线组（需改 page_extractors.py / superworks_extractor.py）。这是 9 条目标能否修复的前提。
2. 是否接受新增的 R-PAIR-MISSING-SIDE（3 条）与 review/discard 变化。
3. PW0256 变为 discard 是否按"无配对"计。
4. 共享锚点保护的偏离是否接受（否则需要改 `test_terminal_candidates.py` 中的既有用例，超出本次范围）。
5. 若不采纳本次改动：`git checkout -- src/dwg_audit/audit/candidates.py` 并删除 `tests/unit/test_loop_z6_candidates.py`（未执行，本次未做 git 操作）。

## 8. 清理
- 已删除本次创建的探测目录与快照：`.tmp/loopAB_probe`、`.planning/superworks-adapter/loopAB_src`、`.tmp/loopZ6_control`、`.planning/superworks-adapter/loopZ6_control_src`、`.tmp/z6_*_run.log`。
- 未触碰 `.tmp/superworks_round11_full`、`round11_full_src` 与并行修改的 rules.py。
- 离线脚本与 JSON 结果位于会话 scratchpad（不在仓库内）。
