# FP-FIX：修复 2594dbe 的三处误报回退（2026-10-15）

基线：HEAD `2594dbe`（分支 superworks-loop）。误报来源：`FP-VERIFY/README.md`（三项结论）与 `STATUS-2026-10-15/README.md`。
范围：只改 `src/dwg_audit/audit/superworks_extractor.py` 与 `src/dwg_audit/extract/superworks_semantics.py`；未改 `recognition_coordinator.py`、`pipeline.py`、V2 模块、`symbol_port_proposal.py`，未加 PDF/OCR，未做项目/句柄/值特判，未 commit / push。

## 0. 结论

| 项 | 2594dbe 现象 | 修复后 | 处理 |
|---|---|---|---|
| 1 lattice 恢复 pass | 425 条 V1 `terminal_strip_lattice` pass 与 SW pass 双存 | 0 条；pass 集合与 round25 逐条一致 | 原生已覆盖标签上，遗留配对按 round25 方式退役（台账 B 类） |
| 2 嵌套重复冲突 | 8 条 R-SUPERWORKS-CONFLICT（p041–p044） | 0 条（round25 水平）；新增 20 条 R-RECOGNITION-GAP（review） | 父路径副本丢弃；祖先/后代同接触不算竞争；新缺口经装置内部判定核验，0/20 满足，保留为缺口 |
| 3 p061 S0025 低置信 | 4 条 R-PAIR-LOW-CONFIDENCE（review） | 0 条 | 原生部件 pass 携带其连接短线端点落在的框线组，框线组被原生行占用 |

## 1. 改动

`superworks_extractor.py`

1. `extract_superworks_pairs` 连接标签循环：`existing_native_parts` 命中时不再直接 `continue`。遗留的 `component_mapping`（非 SW 行）若与 `_legacy_pairs_on_label_anchor_with_other_port` 判定冲突则只报告，否则调用新增的 `retire_claims` 退役，台账 `validated_superworks_replacement`，`new_pairs` 为已存在的原生行。原生行本身不重复生成。
2. `_endpoint`：入口调用 `_foreign_copy` 丢弃“副本”端口。副本定义：`validation["definition_path"]`（新增，见下）不等于 `instance_path`，且同一接触的端口中存在归属本体记录（`instance_path == definition_path`、同 marker、同端子号）。
3. `_coincident_ports` 增加 `same_contact` 参数；`_endpoint` 的**符号实例竞争**分支传入 `_nested_instances`（实例路径为祖先/后代关系，即 `/A` 与 `/A/B`，以路径前缀判断，不是子串）。**端子身份冲突分支不豁免**，祖先/后代身份不同仍报 `competing_physical_port_identities`（单测覆盖）。
4. `_frame_group_at_stub`（新）：连接短线的任一端点落在唯一一条“仅 BORDER 图层”的线组上时返回其组号，多于一条返回 None。仅用于原生首轮（`old` 为空、`producer_groups` 不唯一）时的 `line_group_id` 取值。
5. 抽出 `_report_legacy_disagreement`（原内联代码，行为不变）。

`superworks_semantics.py`

6. 端口 `validation` 增加 `definition_path`（marker 所在的定义实例路径）。这是 `_foreign_copy` 的依据；未改 `SwPort` 模型（`domain/models.py` 不在允许范围）。`sw_ports` 产物的 validation 字典因此多一个键。

新文件：`tests/unit/test_coordination_fp_fixes.py`（13 个用例）。

## 2. 三项的根因与证据

### 项 1：425 条 lattice

- 根因：`6e0492e` 的 `existing_native_parts` 分支直接跳过，使 `replace_claims(old,new,"part:...")` 不执行，V1 端子排配对未被替代。与 round25 的差别只在这一点。
- 证据：425 条两端标签都是原生 SW 行的外部端点文字（425/425 两端命中，0 条单端命中）。
- 门禁说明：任务要求在 `ScopedPairIds.admit` 补“两端标签已是同部件 SW 针脚外部端点”的覆盖判断。该函数在 `recognition_coordinator.py`，本次禁改，未改。替代实现为上面第 1 条的退役，输出层面等价（pass 集合一致）。若主线程希望在生成端也拦截，需要在 `covered()` 中加入“两端文字都是同一 SW 行的 `connection_text_id`/`external_endpoint_text_id`”判断。
- 退役条件是“遗留配对任一端是已被原生消费的标签”（与 round25 按标签替换的口径一致）。

### 项 2：8 条嵌套冲突

- 根因（已由 FP-VERIFY 核实，本次复现）：父块 `/2F60B` 递归遍历嵌套 INSERT `/2F60B/2F324`（线圈），在父路径下生成线圈端子的副本（`instance_path=/2F60B`，`definition_path=/2F60B/2F324`）；同一接触上还有父块自有针脚（`2F325:1`，identity `HHJB-V`，符号 `/2F60B`）。原先同接触的符号实例竞争判为冲突。
- 为何需要两步：只丢副本，父块自有针脚与线圈仍是“符号不同的同接触”，冲突仍在（FP-VERIFY 反事实：丢副本单独不降冲突）；只豁免祖先/后代，副本仍在并可能成为端口代表（反事实：+5 缺口）。两步组合后冲突 2→0，缺口 +5/项目。
- 新 20 条缺口（5 条/项目，共 4 项目）逐条用 `superworks_device_internal.device_internal_verdict` 核验（`tools/new_observations.py --src`）：**0/20 为装置内部连接**。判定结果：2/20 为装置端子一侧身份未解析（`terminal_identity_not_label_prefixed`，装置端子 `1-1n204` 的针脚身份为空）；3/20 两端都不是装置端子（`no_device_terminal_side`，元件↔元件，如 `STJ` 线圈 ↔ `HHJB`）。线圈侧即使在“装置端子↔线圈”的组合下，线圈所属元件标签（`HHJA`）也与装置端子标签（`1-1n204`）不同，不满足同一装置条件。因此不静默丢弃，保留为 review 缺口（与设计“不静默丢弃原生缺口”一致）。
- 残留：这 5 条缺口中有 `unresolved_endpoint_identity`，但端点值已有（`HHJA-V` / `HHJB-V`，来自父块自有针脚）。原因：`_endpoint` 以 `ports[0]` 为代表端口，而代表端口是无身份的线圈。这是 `_endpoint` 既有的代表端口选择问题，未在本次范围内修改，记为遗留。

### 项 3：p061 S0025 低置信

- 根因：4 条低置信为 V1 `ordinary_pair`（11↔8、9↔9，挂在框线组 GC0069/GC0070/GC0080/GC0063 上）。这些框线组在 2594dbe 中没有被原生行占用（原生行 `line_group_id` 全为空），因此不在 `target_line_group_ids` 的闭合集合里，被普通配对再次使用。
- 为何选“框线组占用”而非“退役”：这 4 条是 `ordinary_pair`，不在 `component_mapping` 的遗留集合里，退役逻辑碰不到（实测：仅恢复 round25 的“遗留组号”分支时，4 条仍在）。
- 选用的方案：原生首轮取值为 `producer_groups` 唯一时用之；否则用 `_frame_group_at_stub`。实测 p061 的 4 条低置信消失，组号与 round25 的部件 pass 组号一致（GC0069、GC0070、GC0080、GC0063 等）。
- 不选的方案（已试验并撤回）：把遗留部件配对的组号写回原生行（round25 的 `old[0].line_group_id` 分支）。该方案不能去掉 p061 的 4 条（见上），且与几何取值互相冲突，撤回。

## 3. 测试

- 单元：`tests/unit/test_coordination_fp_fixes.py` 13 项全过（退役/不重复生成/台账 B 类；副本丢弃；祖先/后代豁免与身份冲突保留；路径前缀非子串；框线组取值与歧义）。
- 相关单元：`tests/unit/test_superworks_*.py`、`test_recognition_coordinator.py`、`test_component_diagrams.py`、`test_pairs_and_rules.py` 全部通过（工作区复跑时曾出现 3 个 device_internal 相关失败，报错位于对方未提交的报表层改动 `report/superworks_artifacts.py`，与本次两个文件无关；之后的工作区复跑已全部通过）。
- 全量 `python -m pytest tests -q -p no:cacheprovider`（含 integration）：
  - 工作区（含对方当时的未提交改动）：2235 passed, 1 skipped，EXIT 0。
  - 干净副本（HEAD + 我的 3 个文件，补齐未跟踪的 `tests/fixtures/superworks/*.dxf`）：2220 passed, 2 skipped，EXIT 0。两个 skip 是本地未跟踪真实项目数据缺失（`P001 primitives not present`、`local real-project DXF unavailable`），与改动无关。

## 4. 回放对比（13 项目）

快照：`.tmp/loop_fpfix_src` = HEAD `src/` + 上述两个文件（不含对方的未提交改动，`tools/make_snapshot.sh` 生成）。输出：`.tmp/loop_fpfix`。

| 项目 | pass r25 | pass 2594dbe | pass 修复后 | lattice | issue 2594dbe→修复 | SW 冲突 | 低置信 | 缺口 R-RECOGNITION-GAP |
|---|---|---|---|---|---|---|---|---|
| p016 | 1288 | 1383 | 1288 | 95→0 | 528→528 | 0→0 | 0→0 | 528→528 |
| p017 | 981 | 1047 | 981 | 66→0 | 474→474 | 0→0 | 0→0 | 474→474 |
| p018 | 890 | 953 | 890 | 63→0 | 465→465 | 0→0 | 0→0 | 465→465 |
| p019 | 1171 | 1234 | 1171 | 63→0 | 610→610 | 0→0 | 0→0 | 610→610 |
| p020 | 1487 | 1559 | 1487 | 72→0 | 720→720 | 0→0 | 0→0 | 720→720 |
| p021 | 1369 | 1435 | 1369 | 66→0 | 683→683 | 0→0 | 0→0 | 683→683 |
| p041 | 748 | 748 | 748 | 0→0 | 290→293 | 2→0 | 0→0 | 287→292 |
| p042 | 766 | 766 | 766 | 0→0 | 293→296 | 2→0 | 0→0 | 290→295 |
| p043 | 1377 | 1377 | 1377 | 0→0 | 476→479 | 2→0 | 0→0 | 473→478 |
| p044 | 1399 | 1399 | 1399 | 0→0 | 478→481 | 2→0 | 0→0 | 475→480 |
| p061 | 2052 | 2052 | 2052 | 0→0 | 797→793 | 0→0 | 4→0 | 793→793 |
| p000 | 743 | 743 | 743 | 0→0 | 254→254 | 1→1 | 0→0 | 253→253 |
| p022 | 735 | 735 | 735 | 0→0 | 314→314 | 1→1 | 0→0 | 313→313 |
| 合计 | 15006 | 15431 | 15006 | 425→0 | 6382→6390 | | | |

逐类说明：

- **pass 集合**：修复后与 round25 逐条一致（丢失 0、新增 0，内容键 = sheet、两端值、两端文字 id、kind）。相对 2594dbe 丢失 425 条，全部为 lattice。
- **issue**（按 rule+sheet+message 多重集）：相对 2594dbe 去掉 R-SUPERWORKS-CONFLICT 8 条（p041–p044 的 S0012/S0013 各 2）与 R-PAIR-LOW-CONFIDENCE 4 条（p061 S0025），新增 R-RECOGNITION-GAP 20 条（p041–p044 的 S0012/S0013 各 5，review）。R-SUPERWORKS-CONFLICT 与 round25 同为 0（p041–p044）、1（p000、p022）。round25 没有 R-RECOGNITION-GAP 规则，该类增量来自 2594dbe 已有的缺口规则，本次只增加上述 20 条。
- **pair 层**（`tools/pair_delta.py`，修复相对 2594dbe）：`component_mapping/pass` -425；`ordinary_pair/discard` -111（按键多重集差 112 条：结构性框线 106 条，“Structural terminal-strip border, not an electrical wire.”；其余 6 条为框内针脚/小框类，rationale 为 `block_internal_pin_pair` 及 `top=… bottom=… score=…`）；`ordinary_pair/review` -4（即低置信）。`superworks_supersession` 中 B 类 +190（p016）等为 lattice 退役台账，每条被两端标签各处理一次，与 round25 的“每条两行”一致。
- **discard 说明**：框线被原生行占用后，V1 不再对其生成“结构性框线”discard，这是“V1 只处理未闭合线组”的设计效果。它不进入 pass、issue、覆盖汇总（summary 中覆盖相关键不变）。
- **原生行组号**（`pair_delta.py`、按内容键对齐，共 5831 条原生 pass 行）：2594dbe 全部为空；修复后 905 条带组号。相对 round25：组号列表完全一致 4014 条，round25 有组而修复后为空 1346 条（round25 取值依赖 V1 遗留部件配对，本次未复刻，见遗留），修复后有组而 round25 为空 40 条，两边都有组但不同 431 条（框线选择不同，见遗留）。
- **summary**：覆盖相关键（coverage）在 13 项目上全部不变；不同的键只有 `supersession_categories`（B 类计数）、`resolution_states`（CONFIRMED_CONFLICT→INCOMPLETE）与 `timing`。

## 5. 遗留与需裁决

1. `ScopedPairIds.admit` 未加门禁（禁改文件），由 §2 项 1 的退役替代，输出等价；生成端门禁待主线程决定。
2. 相对 round25，原生行的组号不完全一致（见 §4）：431 条“两边都有组但不同”（lattice 端子排虚拟边框上，几何选中的框线与 round25 取的 V1 遗留配对组不同）、1346 条 round25 有组而修复后为空（round25 取值依赖 V1 遗留部件配对，而原生首轮时该配对尚不存在）、40 条修复后有组而 round25 为空。组号决定框线闭合集合，本次经回放 pass 集合与 round25 逐条一致；要逐条对齐 round25 的组号，需要在 `coordinator.accept_native` 之前拿到遗留配对，属于调度改动，本次未做。
3. 20 条新增 R-RECOGNITION-GAP 为 review 级，是否接受由 coordinator 的裁决决定（FP-VERIFY §6-3 已列）。
4. `_endpoint` 代表端口选择（残留，见 §2 项 2）。
5. 未跑 77 项目全量（按任务要求由主线程统一跑）。`FRAME_TOUCH_TOL`、框线取值只在 13 项目上验证。

## 6. 复现

```
sh .planning/superworks-adapter/loop/FP-FIX/tools/make_snapshot.sh .tmp/loop_fpfix_src src/dwg_audit/audit/superworks_extractor.py src/dwg_audit/extract/superworks_semantics.py
PYTHONIOENCODING=utf-8 python -X utf8 .planning/superworks-adapter/replay.py --output .tmp/loop_fpfix --snapshot .tmp/loop_fpfix_src --projects p016 p017 p018 p019 p020 p021 p041 p042 p043 p044 p061 p000 p022
python -X utf8 .planning/superworks-adapter/loop/FP-FIX/tools/compare_fix.py .tmp/engine_coordination_full_acceptance/current .tmp/loop_fpfix p016 p017 p018 p019 p020 p021 p041 p042 p043 p044 p061 p000 p022
python -X utf8 .planning/superworks-adapter/loop/FP-FIX/tools/compare_fix.py .tmp/superworks_round25_full .tmp/loop_fpfix p016 p017 p018 p019 p020 p021 p041 p042 p043 p044 p061 p000 p022
python -X utf8 .planning/superworks-adapter/loop/FP-FIX/tools/pair_delta.py .tmp/engine_coordination_full_acceptance/current .tmp/loop_fpfix p016 p017 p018 p019 p020 p021 p041 p042 p043 p044 p061 p000 p022
python -X utf8 .planning/superworks-adapter/loop/FP-FIX/tools/new_observations.py .tmp/engine_coordination_full_acceptance/current .tmp/loop_fpfix p041 --src .tmp/loop_fpfix_src
```

工具：`tools/compare_fix.py`（pass 内容键、lattice、按规则 issue 计数）、`tools/pair_delta.py`（pair 类型/状态增减、discard 来源、原生组号一致性）、`tools/new_observations.py`（新增观察与装置内部判定）、`tools/make_snapshot.sh`（HEAD + 自有文件的隔离快照）。
