# V-06 修复：同键双映射（SW 连接线与遗留 component_mapping 并存）

范围：只改 `src/dwg_audit/audit/superworks_extractor.py`，新增 `tests/unit/test_superworks_loop_v06_dedupe.py`。未改 `pipeline.py`、`rules.py`，未做 git 操作，未全量回放。

## 1. 根因（第六轮数据核对）

48 条全部位于 p050（PAC-885G-H），sheet S0025/S0026/S0027。
- 旧行 44 条 `strip_two_port_component`、4 条 `inline_two_port_component`，pair_id 为 PAB*，即 `backplate_components.py` 的 accessory/backplate 产出（`strip_two_port_component` 在 :432，`inline_two_port_component` 在 :258/:573，`pair_id` 工厂 `IdFactory("PAB")` 在 :101）。
- 每个键的 SW 行与旧行 sheet、左值、右值、端口号（"1"）、连接文字 text_id（`right_text_id`，如 T4117、T3855）全部一致。只有 left_text_id 不同：旧行是端口引脚文字，SW 行是部件标签文字。
- 替代逻辑没有覆盖旧行，原因是执行顺序：
  - `pipeline.py:227` 先调用 `extract_superworks_pairs`，其 connect_label 循环（`superworks_extractor.py:765-768`）只在入参 `pairs` 中找旧行。
  - `pipeline.py:240-247` 之后才调用 accessory pass 并 `pairs.extend(accessory_pairs)`，这些旧行进入 `pairs` 时 SW 替代已经结束。
  - 插桩验证（p050，`round6_full_src`）：SW 入参 1895 条，其中 S0025/S0026 没有任何 component_mapping 行。supersession 台账中 467 条 `part:` 记录全部为类别 A（无旧行），没有一条引用这 48 个旧 pair_id。
- 若旧行在入参中，label 循环的匹配条件（同 sheet、pair_kind、`label.text.text_id ∈ (left_text_id, right_text_id)`）对这 48 条都成立，因此根因是“旧行不在入参中”，不是匹配条件失效。

## 2. 修改

新增 `supersede_equivalent_component_duplicates(pairs, ledger)`（`superworks_extractor.py:864-905` 一带，`_is_sw_component_row` / `_component_identity` 为辅助函数）：
- 等价判定：同 sheet、同 left_value、同 right_value、同 `component_port`、同 `right_text_id`。SW 行以 `component_submode == "superworks_connect_line_port"` 识别。
- 只淘汰状态为 pass 的非 SW component_mapping 行，且必须存在等价 SW 行；SW 行之间不互相淘汰；不等价的旧行（右文字、端口、右值、状态任一不同）保留。
- 被淘汰的行写入 supersession 台账，类别 `G`，reason `superworks_connect_line_port_supersedes_equivalent_legacy_row`，`old_pair` 为完整旧行，`new_pairs` 为 SW 行。

接线位置（未实施，见第 5 节）：`pipeline.py` 在 accessory 块之后、`mark_ignored_equipment_panel_ordinary_pairs(` （:263）之前调用一次：
```python
from dwg_audit.audit.superworks_extractor import supersede_equivalent_component_duplicates
pairs, superworks_supersession = supersede_equivalent_component_duplicates(pairs, superworks_supersession)
```

## 3. 测试

- `tests/unit/test_superworks_loop_v06_dedupe.py`，9 条：等价 strip 旧行被替代（SW 保留、台账 G 正确）；inline 子模式同样被替代；右文字不同、端口不同、右值不同、旧行 review 状态均保留；SW 行之间不互相淘汰；无 SW 行时原样返回；SW 行为 review 时不淘汰旧行。
- `pytest tests/unit -q`：1725 passed, 1 skipped。

## 4. 验证（p050 单项目，replay 产物在 .tmp，验证后已删除）

| 运行 | pairs | component_mapping(pass) | 同键 legacy+SW 双映射 | issues |
|---|---|---|---|---|
| r6（基线） | 2666 | 661 | 164 键 | 4 |
| loopW1 as-shipped（src 含本修复，但 pipeline 未接线） | 2666 | 661 | 164 键 | 4（与 r6 相同，无效果） |
| 变体（仅在 scratch 副本的 pipeline.py 加上第 2 节的调用） | 2502（−164） | 497（−164） | 0 | 2（与第五轮 p050 issue 集合一致） |

变体的其他检查：
- 非 component 行全部不变；保留下来的 2502 条 pair 的 left/right/text/line_group/evidence/status/confidence 与 r6 完全一致（已逐列核对）。
- 被删 164 条全部为 status pass 的 component_mapping：strip_two_port_component 124、opposed_port_panel 30、inline_two_port_component 8、four_port_contact_component 2；台账 G 164 条。
- 其中 48 条为本轮新增（同键双映射）；其余 116 条在第五轮中已是双映射（同键 legacy+SW，第五轮 p050 component_mapping 也是 564 行、116 键双映射）。这 116 条同属“旧行与 SW 行等价”的重复，按规则一并处理。如要只处理 48 条，需要额外区分新旧，我不建议这样做。
- 全部 sw_* 产物（sw_connect_labels、sw_ports、sw_port_coverage 等）与 r6 逐字节一致；superworks_summary.json 只多了 supersession G=164 以及计时字段。
- issues 差异：r6 的 4 条中，`R-MANY-TO-ONE` 的 GND 与 `R-CROSS-PAGE-CONFLICT` 保留；两条 `端子表组件共享端点待复核`（related PAB0100 对应 1KLP1-1，PAB0162 对应 1KLP29-1）消失。这两条的 related 旧行都有同键 SW 孪生行。去掉孪生行后规则输入不再重复，与第五轮 issue 集合一致。规则本身（rules.py）未改。
- 其他项目：对 r5 与 r6 全部 77 个项目的输出做同样的等价扫描，只有 p050 存在任何等价双映射（r5 116 条、r6 164 条）。因此该改动在本轮语料中只影响 p050，其他项目的输出不变。

## 5. 未完成 / 需要决定

- 修复在 `src` 中尚未生效：要让它生效必须在 `pipeline.py` 加上第 2 节的调用，这是本任务允许范围之外的文件。我没有修改 `pipeline.py`，等待确认后再接线。
- 备选方案：把 accessory pass 移到 `extract_superworks_pairs` 之前，让 `replace_claims` 直接覆盖旧行。这会改变 SW 循环对 accessory 行的标注与 `disputed` 判定，影响面更大，因此没有采用。
- 台账新增类别 `G`，`report/superworks_artifacts.py` 的 supersession 分类计数会多出一类，需确认无下游依赖。

## 6. 清理

已删除 `.tmp/loopW1_probe`、`.planning/superworks-adapter/loopW1_src`，以及 scratchpad 中的变体副本与输出（均由本次任务创建）。

## 7. 已接线

- `src/dwg_audit/pipeline.py`：在 accessory 块（`if accessory_mappings:` 之后）与 `mark_ignored_equipment_panel_ordinary_pairs(` 之前新增调用，台账变量为 `extract_superworks_pairs` 返回的 `superworks_supersession`（list），调用后以返回值重新绑定 `pairs` 与 `superworks_supersession`，随后进入 `ProjectArtifacts(superworks_supersession=...)`，由 `report/superworks_artifacts.py` 写出 `superworks_supersession.parquet`。
- 下游检查：`superworks_artifacts.py` 对台账仅做字符串化写入与 `Counter(category)` 统计，无枚举校验；`rules.py`、desktop、apps 均不读取 supersession 类别。类别 G 无需改动 schema，`superworks_artifacts.py` 未修改。
- 测试：`tests/unit/test_superworks_loop_v06_dedupe.py` 新增 1 条集成测试（按 pipeline 顺序：SW 行在前，accessory 产出的 `PAB0001` 真实旧行随后追加，调用淘汰后断言 PAB0001 被淘汰、PAB0002/0003 保留，台账 G 写出为 parquet 且 `supersession_categories == {"G": 1}`）。该 SW 行由手工构造为同身份行，未走完整 SW 连接线提取。`pytest tests/unit -q`：1726 passed, 1 skipped。
- 单项目回放（`replay.py --output .tmp/loopW1b_probe --snapshot .planning/superworks-adapter/loopW1b_src --workers 2 --projects p050 p016`，快照取自接线后的 src）：

| 运行 | pairs | component_mapping(pass) | 同键双映射 | issues | 台账 |
|---|---|---|---|---|---|
| p050 r6 | 2666 | 661 | 164 | 4 | 无 G |
| p050 接线后 | 2502 | 497 | 0 | 2 | G=164 |
| p016 r6（`.tmp/superworks_round6_full`） | 2648 | 558 | 0 | 0 | 无 G |
| p016 接线后 | 2648 | 558 | 0 | 0 | 无 G |

- p050 与 FIX_dedupe.md 变体预期（2502 / 497 / 0 / 2）一致；p016 与第六轮一致。回放产物与快照已删除。
- 注：`superworks_semantics.py` 为另一子代理进行中的修改，快照取自当时工作区，本次未触碰该文件。
- 函数实际位置为 `superworks_extractor.py:879-905`（上文 :864-905 包含常量与辅助函数，属同一段）。
