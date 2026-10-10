# L-16 修复说明：R-DUPLICATE-SAME-LINE（p036 / p037，图 05 相位标注 UN 与 UD4）

状态：candidates.py 未采用修改（已还原，与 HEAD 一致）。根因位于 rules.py 竞争集；仅改 candidates.py 无法在不破坏既有语义注释设计的前提下消除该误报。建议的修复是 rules.py 中一行过滤，需用户批准或指派给正在修改 rules.py 的子代理（当前 rules.py 有未提交改动，本次未触碰）。

## 1. 根因

同一线端 (line_group, side) 上，相位标注 UN 与端子候选 UD4 同时被接受为带值候选：

- 相位标注白名单：`src/dwg_audit/audit/candidates.py:85-87`（`_SCHEMATIC_AC_PHASE_SEMANTIC_ENDPOINT_PATTERNS`，包含 `UN`）。
- 接受路径：
  - 普通扫描：`candidates.py:1570-1573`，`detail == "schematic_ac_phase_label"` 时 value 取相位名；`candidates.py:1924-1948` `_candidate_channel_hint` 将其标为 `schematic_semantic_endpoint_channel`；`candidates.py:378` 在 `else` 分支 `status = "accepted"`。
  - 线段跨度补充：`candidates.py:484-588` `_add_schematic_ac_phase_line_span_candidates`，`candidates.py:569` 接受。
- 竞争集：`src/dwg_audit/audit/rules.py`（当前行号 4439，原 4310）`_ambiguous_candidate_groups` 只按 `status == "accepted" and value` 收集，不区分通道；`rules.py:556` 起的 `_run_duplicate_same_line` 对同组前两名做 `abs(score差) < duplicate_delta(0.08)` 判定。

p036 / p037 GW0003 左端实例（第五轮 terminal_candidates）：UD4 score 1.0000（wire_logic_endpoint_channel，cad_owned_physical_terminal_label）、UN score 0.9244（schematic_semantic_endpoint_channel，距端点 dx 1.49 dy 1.0）；差 0.0756 < 0.08，触发 DUP。

## 2. 为什么不能只改 candidates.py

candidates.py 无法区分两类消费者：

- 规则竞争集（rules.py）：只看 accepted + value + score。
- 语义注释（pairs.py:680 `_single_sided_schematic_semantic_annotation`）：要求同一线端上有 accepted 的相位候选，并读取其 value。

相位标注在"单侧有数字端子、另一侧缺失"时作为语义注释是既有设计，并有测试覆盖。

试验：在 candidates.py 中对"同侧存在非相位带值候选时，相位候选 reject（reason `schematic_ac_phase_label_yields_to_terminal_identity`）"。结果 `tests/unit/test_terminal_candidates.py` 3 条失败：

- `test_build_pairs_marks_single_sided_ac_phase_label_as_semantic_annotation`
- `test_build_pairs_marks_line_span_ux_prime_as_ac_phase_semantic_annotation`
- `test_build_terminal_candidates_rejects_cross_row_ux_prime_endpoint_hit`

试验改动已还原。把 status 改为非 accepted 或 value 置空，都会同时切断注释路径；为压低分数而人为改 score 会使阈值耦合到 `duplicate_same_line_score_delta`，属于投机修补，未采用。

## 3. 建议修复（需批准，未在仓库内执行）

`src/dwg_audit/audit/rules.py` `_ambiguous_candidate_groups`（当前约 4439 行）：

```python
# before
if candidate.status == "accepted" and candidate.value:
# after
if candidate.status == "accepted" and candidate.value and candidate.channel_detail != "schematic_ac_phase_label":
```

语义：相位标注保留在语义通道、仍可作为 pair 语义注释；不再参与同线端的端子身份竞争（符合任务第 2 条）。无端子号时的相位标注不参与竞争，也不改变 pair 选择（端子数字仍按分数居首）。

scratch 验证（不改仓库）：在 src 快照副本的 rules.py 中仅应用上述一行后回放 p036/p037。快照副本与回放输出已按清理要求删除，结果以第 4.2 节表格为准。

## 4. 验证

### 4.1 单元测试
- 新增 `tests/unit/test_loop_l16_candidates.py`：3 passed（候选层守护：相位标注保持语义通道、同侧数字端子排名高于相位、无数字端子时相位不成为 terminal_numeric 身份）；1 xfailed（strict，规则层竞争，待 rules.py 修改；将 variant 替换后 `_ambiguous_candidate_groups` 返回 `{}`，已人工核对）。
- `pytest tests/unit -q`（运行时工作区）：1702 passed，1 skipped，1 xfailed（本次试跑时曾有 `test_superworks_semantics.py::test_component_handle_adjacency_is_not_geometric_proof` 失败，属其他子代理修改范围，之后已通过）。

### 4.2 单项目 replay（p036、p037，--workers 2）

快照差异：`loopS_src` 与第五轮快照 `code_manifest.json` 对比，仅 `dwg_audit/audit/superworks_extractor.py`、`dwg_audit/extract/superworks_semantics.py` 不同（其他子代理进行中的改动）。rules.py 在快照时与第五轮一致。

| 项目 | 运行 | pairs | component_mapping | pass / review / discard | issues |
|---|---|---|---|---|---|
| p036 | 第五轮 | 1838 | 304 | 1276 / 255 / 307 | R-DUPLICATE-SAME-LINE 1 |
| p036 | as-is（loopS_src） | 1882 | 348 (+44) | 1320 / 255 / 307 | R-DUPLICATE-SAME-LINE 1 |
| p036 | variant（rules 一行） | 1882 | 348 | 1320 / 255 / 307 | 无（DUP 消失） |
| p037 | 第五轮 | 1759 | 230 | 1071 / 363 / 325 | R-DUPLICATE-SAME-LINE 1，R-SUPERWORKS-CONFLICT 1 |
| p037 | as-is（loopS_src） | 1847 | 318 (+88) | 1159 / 363 / 325 | 同第五轮 |
| p037 | variant（rules 一行） | 1847 | 318 | 1159 / 363 / 325 | R-SUPERWORKS-CONFLICT 1（DUP 消失） |

逐类说明：
- pair_kind：ordinary_pair、wire_component_mapping、table_mapping、continuation、semantic_mapping、bridge_mapping 在三次运行中数量完全一致。唯一差异是 component_mapping（p036 +44，p037 +88），其 pass 数同步增加；discard 与 review 不变。该差异来自快照中 superworks_extractor.py / superworks_semantics.py 的其他子代理改动，与本任务无关。
- issues：as-is 与第五轮的 issue 集合一致；variant 仅移除 R-DUPLICATE-SAME-LINE，其余规则（含 R-SUPERWORKS-CONFLICT）数量不变。
- variant 相对 as-is：pairs 完全一致（规则层修改不改变 pair 选择），只有 DUP issue 消失。

## 5. 全语料影响估计（第五轮 terminal_candidates.parquet，77 项目，静态统计）

- 相位标注通道行 2228，其中 accepted 1681。
- accepted 相位候选中，同侧另有非相位带值 accepted 候选（参与竞争）1477 条，分布 56 个项目；竞争者通道为 wire_logic_endpoint 973 行、terminal_numeric 562 行。
- 无竞争（单独存在）204 条。
- 候选级模糊组（同侧前两名分差 < 0.08）：第五轮 252 组；移除相位候选后 219 组；减少 33 组，分布 12 个项目：p001、p002、p008、p009、p014、p028、p029、p032、p036、p037、p045、p056。
- 第五轮 R-DUPLICATE-SAME-LINE 实际 issue 仅 2 条（p036、p037）。其余 31 组未产生 issue，推测被 `_ordinary_pair_eligible` 或 pair 状态过滤，未逐一回放验证。
- 注意：采用建议修复后 pair 层在 p036/p037 已确认不变；其余 10 个项目的 pair 层影响未回放验证，需在后续有限回放中确认。

## 6. 待决策

1. 是否批准 rules.py `_ambiguous_candidate_groups` 的一行过滤（需与当前修改 rules.py 的子代理协调，避免冲突）。批准后移除测试中的 xfail 标记。
2. 任务第 3 条"无端子号时相位标注不被升格为端子身份"：当前实现保持其在语义通道（非 terminal_numeric）。pair 层仍可把单侧相位标注作为语义注释使用（既有设计，有测试覆盖）。若要求 pair 层也不得使用，需另行决策，会改变既有 semantic_mapping 证据。

## 7. 未做事项

- 未修改 candidates.py（与 HEAD 一致）、rules.py、pairs.py。
- 未执行 git 操作。
- 未做全量回放。

## 8. 已实施

- 修改位置：`src/dwg_audit/audit/rules.py` 第 4439-4443 行，`_ambiguous_candidate_groups` 收集条件增加 `candidate.channel_detail != "schematic_ac_phase_label"`（仅此一处）。
- 测试：`tests/unit/test_loop_l16_candidates.py` 移除规则层测试的 strict xfail 标记；同时移除已无用途的 `import pytest`。该文件 4 条用例全部通过。
- `pytest tests/unit -q` 全量：1716 passed，1 skipped，0 failed。
- 未修改 candidates.py、pairs.py、superworks_*.py；未执行 git 操作；未做全量回放。
