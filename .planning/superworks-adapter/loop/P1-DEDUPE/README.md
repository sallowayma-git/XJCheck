# P1-DEDUPE：旧链与同页 SW 配对重复的去重

分支 `superworks-loop`，基线 HEAD `e99fd86`。未 commit、未 push；未改 V2 模块、`symbol_port_proposal.py`，未加 PDF/OCR，未按项目/句柄/值特判，未删除 V1 代码。

## 0. 结论

1. 新增 `supersede_legacy_duplicates_of_sw`（`src/dwg_audit/audit/superworks_extractor.py`），台账类别 **I**：纯旧链 pass/review 配对，若同页存在一条 SW pass 配对且两端按现有等价规则完全相同，则旧配对改为 `discard`，evidence 记 `superseded_by` / `superseded_by_all` / `supersession_category='I'`。
2. 全量 77 项目、1,745 张页：**被取代 26,437 条**，全部为 pass，review 为 0。与离线普查（LEGACY-CENSUS 的 26,437）完全一致。
3. **issues 逐条相同**：77/77 项目，issue 总数 40 → 40，按 rule+message+sheet 的多重集逐项一致。
4. **覆盖率不变**：77/77 项目的 `port_coverage`、`port_coverage_with_continuity`、`coverage_views` 全部与第二十三轮相同。
5. **未排除任何类型**。所有候选都经过了 rules.py 的依赖检查（见第 3 节），回放后 issues 无变化，故无需排除。
6. 同时只改了 `pipeline.py` 一处调用（3 行，位于 `supersede_cell_edge_pairs` 之后、`authoritative_component_pairs` 之前）。`supersede_legacy_duplicates_of_sw` 只读 `pairs` 与台账，不依赖 P3 的文件。
7. 单元测试 `tests/unit/test_superworks_legacy_dedupe.py` 25 项全部通过。全量 pytest：干净 HEAD 与 HEAD+本次改动 的失败集合完全相同（4 项，见第 6 节），本次改动新增 25 项通过。

## 1. 改动

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/audit/superworks_extractor.py` | 新增 `supersede_legacy_duplicates_of_sw`、`_ends_equivalent`、`_pair_endpoints_equivalent`、`_sw_end_aliases`、`_is_pure_legacy_pair`、`_is_sw_produced_pair`；常量 `LEGACY_DUPLICATE_CATEGORY='I'`、`LEGACY_DUPLICATE_REASON`、`SW_EVIDENCE_KEYS`。插在 `supersede_cell_edge_pairs` 之后 |
| `src/dwg_audit/pipeline.py` | 一处调用（注释 + 2 行 import/调用） |
| `tests/unit/test_superworks_legacy_dedupe.py` | 新增，25 项 |

台账行格式与 G、H 相同：`element_key='legacy_duplicate:<sheet>:<pair_id>'`，`category='I'`，`reason='legacy_pair_duplicates_same_sheet_sw_pass'`，`old_pair`（改前配对），`new_pairs`（同页 SW 配对，按 pair_id 排序）。类别 I 的含义：**旧链配对与同页 SW pass 配对端点完全等价，旧配对被取代**。报告层无需改动，`superworks_summary.json` 的 `supersession_categories` 会自动出现 `I`。

### 1.1 候选集合

- **SW 侧**（必须 pass）：`evidence.source == 'superworks'`，或 `component_submode == 'superworks_connect_line_port'` 的 component_mapping 行（与 `_is_sw_component_row` 同一判定）。
- **旧侧**（pass 或 review）：不在台账 old/new 中；evidence 不含 `superworks`、`superworks_constraints`、`sw_conflicts`、`sw_dictionary_warnings`；`source != 'superworks'`；非 SW component 行；不带 `ignored_panel_family_id`（整面板 IGNORE 归属）。
- 同页判定：`(file_id, sheet_id)` 相同。

SW 侧 **不含** b2 类（旧配对仅被 SW 注释或确认、evidence 含 SW 键）。这与普查口径一致，也避免取代那些被 SW 修改过的旧配对。

### 1.2 等价规则

`_ends_equivalent(legacy, sw, sw_aliases)`：

1. 两端先用 `_clean_sw_endpoint_value` 规范化（去 `&`、`*` 装饰与首尾空白，`normalize` 与 `_key` 在 `_identities_agree` 内完成）；空端直接不等价。
2. **双向**：`_identities_agree(a, b)` 且 `_identities_agree(b, a)`，即两个名称互相能指认对方（取现有 LOGGEN 等价函数，不另写）。双向要求用于排除以下"部分等价"：
   - 范围端子：`1-7UD20~21` 与 `1-7UD21` 只在一边为范围，另一边多出端点；
   - 字母前缀只在一侧出现（`1A7UD21` 与 `7UD21`）。
3. **别名**：旧端文本正好等于 SW 端在 `evidence.superworks.left/right.endpoint_aliases` 中记录的别名（且该 SW 端 value 与配对 value 一致）。这一分支与 `_identities_agree` 的别名分支相同，只是不再要求反向。
4. 无序：直连或交叉（左对左、右对右，或左对右、右对左）任一成立即可。
5. 端点数不等（旧配对一端为空，或多出 SW 没有的端点）一律不等价，不动。

## 2. 回放与对比

### 2.1 输入与基线

- 基线：`.tmp/superworks_round23_full`。`round23_full_src` 与 HEAD 的 src 在忽略 CR 后完全相同，因此基线代码 = HEAD，对比有效。
- 快照：`.tmp/loop_dedupe_src`（10 项目）与 `.planning/superworks-adapter/round24a_full_src`（77 项目）。两者都是 `git archive HEAD src` 加上本次的 `superworks_extractor.py` 与 `pipeline.py`；**不含** P3 尚未提交的 `line_groups.py`、`page_extractors.py`、`wire_components.py`、`candidates.py`。
- 10 项目：`.tmp/loop_dedupe`；77 项目：`.tmp/superworks_round24a_full`。

### 2.2 被取代数（按 pair_kind / 页面类型）

77 项目合计 26,437（17,263 + 9,164 + 10 与离线普查完全一致）：

| pair_kind | 页面类型（route_target / page_subtype） | 被取代 |
|---|---|---:|
| wire_component_mapping | WireDiagramExtractor / grid_heavy_wire_diagram | 16,187 |
| wire_component_mapping | WireDiagramExtractor / （无 subtype） | 1,076 |
| table_mapping | TableExtractor / backplate_virtual_terminal_table | 8,761 |
| table_mapping | TableExtractor / backplate_geometric_table | 403 |
| component_mapping | ComponentDiagramExtractor / horizontal_component | 10 |
| **合计** | | **26,437** |

10 项目合计 3,078（p001 138、p003 64、p022 273、p026 508、p044 574、p051 0、p061 890、p071 0、p074 333、p075 298）。离线预测（`tools/count_candidates.py`，基于 round23 输出）与回放逐项目一致。

被取代的 SW 配对全部为 pass。同一旧配对有多条 SW 配对时（46 例），取 pair_id 排序最小者记为 `superseded_by`，全部记入 `superseded_by_all`。

### 2.3 状态变化

77 项目每个 `pair_kind|status` 的增减只有：`wire_component_mapping|pass` −17,263、`table_mapping|pass` −9,164、`component_mapping|pass` −10，对应 `discard` 增加同样数量。review 与其他 status 无变化。配对总数 178,696 不变。

### 2.4 issues 逐条对比

- 10 项目：`issues_identical` 为 True 的有 10/10。
- 77 项目：77/77 为 True。issue 总数 40 → 40，多重集（rule_id | message | sheet_id）差集为空。
- 说明：本次只把旧配对的 status 从 pass 改为 discard；rules.py 中凡是按 `status != discard` 过滤的规则，少掉的正是这些重复配对，而重复配对的端点已由 SW 配对覆盖，所以 issues 不变。凡是不过滤 status 的规则（如 `_terminal_row_side_index`），仍能读到这些配对。

### 2.5 覆盖率对比

77/77 项目的以下字段全部不变：

- `port_coverage`：eligible、consumed、pass、ratio（例如 p001：437/663，pass 391，ratio 0.659）；
- `port_coverage_with_continuity`：consumed 481；
- `coverage_views`：strict、with_continuity、strict_excl_device_internal、with_continuity_excl_device_internal。

原因：被取代的旧配对与 SW 配对占用同样的 SW 端口，去重只改变旧配对的计数，不改变 SW 端口被消费的集合。

### 2.6 同一根线的验证

`tools/verify_and_render.py` 对全部 3,078 条（10 项目）做了检查：

- 取代者的值（无序）与旧配对完全相同：**3,078/3,078**。
- 取代者的 pass 状态：**3,078/3,078**。
- 文字 id（无序）完全相同：**2,052/3,078**。其余 1,026 条为 component_mapping 类的取代者，其左端 id 是元件引脚文字而旧行是端子排行文字，右端相同。这是两种生产方式的正常差别，不影响"同一根线"的判断，但说明文字 id 不能单独作为判据。
- 抽样 10 例（分层、固定种子 24）：`png/dedupe_samples_1.png`、`png/dedupe_samples_2.png`。每例蓝色为旧配对的两端连线，红色虚线与方框为 SW 配对的两端，目视两端位置一致（误差在几个绘图单位内）。这是目视检查，不是电气验证。

## 3. 保护检查（rules.py 与旧配对结构化字段）

1. **table_mapping（backplate_virtual_terminal_table，9,164 条）**：旧配对携带 `table_mapping`、`row_band_id`、`left_side_label`、`right_side_label`。
   - `_terminal_row_side_index` 读取全部 pair（不按 status 过滤），因此去重后端子排行侧信息仍在。
   - rules.py 约 1181、1912、2248、3440、3523、3649、4405、4473 行按 `status == pass` 过滤的读取，在回放中未引起 issue 变化。
   - 结论：安全，保留取代。
2. **explicit_external_device_lead（wire_component_mapping）**：`_resolved_by_explicit_external_lead` 要求某配对的 `external_lead_mapping_pair_id` 指向一条 pass 的旧配对。在 round23 最终配对中，**没有任何配对携带该字段**（统计为 0 条引用），因此本规则对候选集合无依赖。
3. **bridge / series / 跨页标记**：候选集合中没有 bridge_mapping；evidence 不含 `terminal_short_bridge`、`series_chain`、`strip_connection_jumper`、`cross_page` 类字段（`_is_terminal_strip_bridge_claim` 读取的字段不在候选中）。
4. **electrical_union_eligible、internal_connectivity_inferred、device_identity_authority、device_pin_label_context、physical_endpoint 等**：仅旧配对携带（约 1,311 条），但只在 `_resolved_by_explicit_external_lead`（见第 2 条，无引用）中被读取。回放 issues 不变。
5. **review 旧配对**：无同页 SW pass 取代者（0 条），因此无 review 被取代。

**结论：没有需要排除的类型。** 所有类型都通过了上述检查，并由回放 issues 逐条相同、覆盖率相同进一步确认。

## 4. 账目与报告

- 台账行数：round23 100,740 → round24a 127,177（+26,437，全部为类别 I）。
- 台账 parquet 体积随之增大（例：p061 2.50 MB → 3.21 MB），因为 `old_pair` 保存了完整 evidence。如需缩小，可只保留 pair_id，但这会偏离 G、H 的写法，未做。

## 5. 局限

- 等价判定仍是端点文本层面的。平行导线若端点相同，会被同样取代；本次抽样未见此类情况，但未做全量电气核对。
- 别名分支：只接受旧文本正好等于 SW 端记录的别名，不做更宽的别名推断。
- 文字 id 不一致的 1,026 条（component 类）只在值层面等价，未逐条核对元件引脚与端子排的对应关系。

## 6. 测试

- 新增 `tests/unit/test_superworks_legacy_dedupe.py`：25 项，全部通过。覆盖：直连与交叉、review、跨页/跨文件不取代、部分等价与多出端点、范围（两个方向）、字母前缀、装饰清洗、别名（属于与不属于本端）、带 SW 证据或在台账中的旧配对、panel 归属、已 discard、多取代者、无 SW pass 时原样返回、输入对象不被修改。
- 全量 pytest（干净导出，避免 P3 的未提交改动）：
  - 干净 HEAD：4 failed、2,096 passed、2 skipped。
  - HEAD + 本次改动：4 failed、2,121 passed、2 skipped（+25）。
  - 两者失败集合相同：`test_analyze_project_routes_table_like_page_to_table_extractor_and_emits_table_mapping`（`assert 0 == 3`，与改动无关，干净 HEAD 同样失败），以及 `test_superworks_semantics.py::test_real_fixture_metadata_is_retained[component|schematic|strip]`（导出包中缺少 DXF 夹具；在工作区中这三项通过）。
- 在工作区（含 P3 的未提交改动）中，上述四项里的三项通过，集成测试仍失败，与干净 HEAD 一致。

## 7. 文件

- `png/dedupe_samples_1.png`、`png/dedupe_samples_2.png`：10 例抽样。
- `tools/count_candidates.py`：离线普查复算（26,437，strict / sw_produced / census 三种口径）。
- `tools/compare_runs.py`：逐项目对比 issues、pair status、覆盖率、类别 I 统计。
- `tools/summarize_compare.py`：对比结果汇总。
- `tools/verify_and_render.py`：同一根线校验与抽样渲染。
- `tools/summary_round23_vs_r24a_77.json`、`tools/summary_round23_vs_r24a_10.json`：紧凑汇总（完整对比 JSON 约 114 MB，未保留）。
- `tools/verify.json`、`tools/samples.json`、`tools/superseded_pairs_r24a10.csv`：校验结果与 3,078 条清单。
- `tools/hits_sw_produced_prod.csv`（及 census / strict 两份）：离线候选清单。
- 回放输出：`.tmp/loop_dedupe`（10 项目）、`.tmp/superworks_round24a_full`（77 项目）。快照：`.tmp/loop_dedupe_src`（已删除）与 `.planning/superworks-adapter/round24a_full_src`。
