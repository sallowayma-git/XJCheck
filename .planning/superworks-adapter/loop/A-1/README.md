# A-1：Covered by component_mapping 丢弃普通配对的审计（只读）

数据：`.tmp/superworks_round12_full`（未改 src/，未 git，未全量回放，未删数据）。图 `A1_covered_pairs_8.png`，明细 `details.json`。

## 1. 机制（代码）
- `component_diagrams.py:156` `consumed_group_ids.add(support_group.line_group_id)`：在 `extract_strip_two_port_component_pairs` 内无条件执行。只要找到端口对、元件体和支撑竖线组即消费，不检查外部端子是否解析（`built_pairs` 至少 2 条，`len<2` 分支形同虚设）。
- `component_diagrams.py:134–141`：`_strip_endpoint_conflicts`（:1481）判为冲突时把 endpoint 置空，但不影响 :156 的消费。
- `page_extractors.py:355–377` `_mark_consumed_component_ordinary_pairs`：同组 `ordinary_pair` 一律 discard，rationale "Covered by component_mapping"。

## 2. 全语料统计（round12，76 个项目）
- 被 "Covered by component_mapping" 丢弃的普通配对：3388 条。
- 其中来自 strip 路径（:156）的：83 条，分布于 13 个项目。
- component_mapping 中外部端子为空/未解析/非 pass 的行：22 条，全部为 `strip_two_port_component`（190 行中 168 pass）。按项目：p003 4、p064 4、p004/005/006/028/067 各 2、p041–044 各 1。
- 与这 22 行同组的被丢弃普通配对：15 条。其中真正丢失信息 4 条（全在 p003），其余 11 条两端均无值（空配对），丢弃无损失。
- 其余 1473 条普通配对所在组，外部端子均非空且 pass，不构成问题。

## 3. 真正丢失的 4 条（p003 S0012）
PC0029（1↔8n401）、PC0031（1↔8n402）、PC0033（1↔8n405）、PC0037（1↔8n818）。底端端口 PCM0002/0005/0008/0012 因 `coincident_conflicting_labels` 为 review，其备选 8nB0x 与 8n4xx 同点叠放，普通配对的右端正是备选之一（text_id 精确匹配）。PC0035（820）为对照：PCM0010 已 pass 解析为 8n820，丢弃正确。

## 4. 截图判读（8 例，见 PNG）
- p003 四例：8n4xx 是真实绘制的底端标注，红叉落在叠放的两条备选上。但左端 "1" 是顶端端口 1 自身的编号（T1252 即 component_port），顶端已由 PCM0001 解析为 8KLP2-1。组线是元件内部的两端口连接线。因此该普通配对的左端不是外部端子，按原样恢复会与 PCM0001 冲突（端口1 出现两个外部端子）。丢失的是底端端口 2 的外部端子，"已覆盖"的理由对底端不成立。
- PC0035 对照：丢弃正确。p004 PC0038、p005 PC0060、p041 PC0061：空配对，丢弃无损失。

## 5. 修复方案与估计
- 不要把普通配对原样恢复为 pass。建议：`component_diagrams.py:156` 仅在该组底端/顶端外部端子已解析时记 consumed（按端侧记录）；`page_extractors.py:355` 对外部端子位于 `external_endpoint_alternatives` 的普通配对保留为 review，并注明"元件映射端子未解析"。
- 估计：恢复 4 条（全部 p003），状态 review（selected_score 0.8099，在 [0.75, 0.92) 区间，见 pairs.py:195–196 与 utils/config.py:170）；pass 0 条。
- 新增 issue：双侧值齐全，R-PAIR-MISSING-SIDE 不触发（rules.py:507）；R-PAIR-LOW-CONFIDENCE 可能新增 4 条 review（rules.py:846）。这些属于真实的待核验项（底端端口 2 外部端子不明），但与已有 4 条 PCM 缺侧 issue 重复，净增应在 0–4 之间。
- 跨页风险：401/402/405/818 作为裸数字出现在 S0007/S0008，与 Z-5 "他页无 8n4xx" 不矛盾（裸数字与 8n 前缀不同），需原 DWG 核对。未全量回放，以上为规则推演，未实际运行。

## 6. 修改点与风险
- `component_diagrams.py:156`（extract_strip_two_port_component_pairs）：改为按端侧记录消费。
- `page_extractors.py:355–377`（_mark_consumed_component_ordinary_pairs）：增加"外部端子已解析"条件。
- 风险：恢复的普通配对左端是端口标签，可能引入伪线；建议先不恢复，只把 review 信息挂到 PCM0002/5/8/12 的 issue 上。

## 7. 需用户决定
1. p003 底端叠放标签 8nB0x 与 8n4xx 哪个为真实外部端子，需对照原 DWG。
2. 是否接受"不恢复普通配对、仅补充备选信息"的方案（推荐），还是恢复为 review。
