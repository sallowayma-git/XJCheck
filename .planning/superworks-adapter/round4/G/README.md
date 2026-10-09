# 第四轮 G：SuperWORKS 误报豁免（G1–G9）实施与离线复核

范围：只改 `src/dwg_audit/audit/rules.py`、`src/dwg_audit/audit/series_chains.py`、`tests/unit/test_superworks_round4_rules.py`。
未改 superworks_extractor.py / superworks_semantics.py / text_geometry.py，未提交，未删除文件，未做 77 项目全量回放。
离线复算只读使用 `.tmp/superworks_round3_full`、`.tmp/superworks_baseline_timed`、round4/D 的输出与 `probe.py`。

## 1. 修改函数清单（行号为当前文件）

rules.py
- 67–110 新增 `_TERMINAL_RANGE_DASHED_PATTERN`、`_terminal_range_members`（范围展开，复用旧链 `_TERMINAL_RANGE_FALLBACK_PATTERN`，另加允许连字符前缀的 `1-4Q1D7~8`）、`_bridge_covered_terminal_identities`（G5）、`_values_are_one_terminal_end`（G9）。
- 590 `_run_cross_page_conflict`：读取 `strip_links`；在 `len(rights)>1` 分支内加 G9（范围等价）与 G8（端子排佐证的一端多线）。
- 777 `_is_terminal_strip_bridge_claim`：G7，`terminal_cross_strip_link` 且 `strip_corroborated is True` 视为桥接 claim。
- 798 `_superworks_strip_link_index`、817 `_is_strip_recorded_one_end_multi_wire`（G8 的索引与判定）。
- 1189 新增 `_is_many_to_one_structured_exemption`：原 `_run_many_to_one` 中 1102–1137 的豁免序列抽出，供全组与非桥接子组共用（G6）。
- 1237 `_run_many_to_one`：`effective_lefts` 扣除桥接覆盖（G5，1246）；全组豁免未命中后对非桥接子组再判（G6，1257）。
- 2089 `_is_authoritative_schematic_inline_backplate_endpoint_group`：schematic 身份 set 去重（G3）。
- 2136 `_authoritative_schematic_inline_component_identity`：SW 连接线端口返回 `_authoritative_superworks_component_identity` 的三元组（G3）。
- 3324 `_is_authoritative_component_mapping_pair`：SW 连接线分支在 SW 早返回之前（G1）。
- 4116 `_authoritative_superworks_component_identity`：submode 末尾校验接受 `component_submode=="superworks_connect_line_port"`（G2，4172）。
- 4188 新增 `_table_endpoint_column_side`；4197 `_superworks_structured_source_kind` 的表格分支按端点所在列取值（左列/右列两种形态都接受）。

series_chains.py
- 20 `_PORT_OWNER_SUBMODES` 加入 `superworks_connect_line_port`；37 `_CORROBORATION_SUBMODE_PAIRS` 加入与 inline/kk/small_port_box 的三组对（G4）。
- 91 新增 `_is_superworks_connect_line_member`；162 `is_cross_view_terminal_series_chain` 的唯一性键（173）对 SW 连接线成员追加 submode（G4，见偏离 2）。

## 2. G1–G9 实施情况

| 项 | 实施 | 状态 |
|---|---|---|
| G1 | 3324：`component_submode==superworks_connect_line_port` 且 `structured_source==component_mapping` 且身份非空 → True | 已实施 |
| G2 | 4172：submode 校验接受 `component_submode==superworks_connect_line_port`，前置校验保留 | 已实施 |
| G3 | 2128：schematic 身份 set 去重；2136：SW 连接线身份返回相同三元组 | 已实施 |
| G4 | 20/37 加入 SW 连接线 submode 与三组对；162 唯一性键对 SW 连接线追加 submode | 已实施，键的范围见偏离 2 |
| G5 | 1246：effective_lefts 扣除桥接段覆盖的端子（`7QD9~10` 覆盖 `7QD9`、`7QD10`；`7UD16~18` 同理） | 已实施 |
| G6 | 1257：全组豁免未命中后对非桥接子组再判同一豁免序列，只增加豁免 | 已实施 |
| G7 | 786：`terminal_cross_strip_link` 且 `strip_corroborated is True` → 桥接 claim；未佐证者仍为普通配对；`terminal_short_bridge` 已由原分支识别 | 已实施 |
| G8 | 610 仅用于 R-CROSS-PAGE-CONFLICT；R-MANY-TO-ONE 不适用（偏离 1） | 部分实施，见偏离 1 |
| G9 | 610 区域：`_values_are_one_terminal_end`（范围与其成员视为同一端） | 已实施（仅跨页冲突） |
| A 同步 | 4197：`_superworks_structured_source_kind` 按端点列取值，round-3 右列形态与新左列形态均接受 | 已实施 |

## 3. 偏离与风险（需主线程裁决）

1. G8 不用于 R-MANY-TO-ONE。G8 同时用于 many-to-one 的离线版本会删除基线真实问题 11/13：p015/p021/p050/p071/p075 的 GND、p038/p049 的 KD26、p039 的 KD1/KD6/1-2GD3、p040 的 1ZK-3。这些组与 p038 KD23 的形态相同（同一右端、多个左端且端子排逐一记录），无法用非项目/值/句柄特判区分。按“不得删除基线真实问题”的约束，已撤掉 many-to-one 侧的 G8。G8 保留在 R-CROSS-PAGE-CONFLICT：基线 3/3 保留，p038 KD23 跨页冲突（页 09/13）已豁免，p038 KD26 跨页（3-2QD7/3-2QD8）同样豁免，而 KD26 的 many-to-one 仍按基线报出。
   测试 `test_g8_many_to_one_report_is_kept_...` 锁定这一约束。
2. G4 唯一性键的范围。字面改为 (sheet,file,component_submode) 会使同页 strip 与 KK 视图成链，破坏既有测试 `test_series_chain_rejects_same_physical_scope_and_keeps_conflict_visible`。因此只对 SW 连接线成员追加 submode，其余保持 (sheet,file)。
3. SW 连接线 Pair 的 eligibility。round-3 中 SW 连接线共 18.6k 条，其中 12,940 条 `evidence.source` 缺失（`structured_source=component_mapping` 且 `component_submode=superworks_connect_line_port`），这些 Pair 被 `_high_confidence_source_eligible` 拒绝，不进入任何规则分组；其余 5,693 条 `source=component_mapping` 参与规则。敏感性实验（contract_src：把缺失的 source 补为 component_mapping）使 R-MANY-TO-ONE 从 210 跳到 7,756，故不建议仅在生产端补 source，需整体复核。`_is_chain_member` 未为缺失 source 的 SW 连接线放宽（否则与规则入口不一致）。
4. round-3 的 SW 端子类别字段有损（GBK 字节被按 UTF-8 替换解码，`端子` 与 `装置端子` 无法可靠区分），离线 E/G7 派生只能依据 strip 表行中出现的端子值（见第 4 节）。
5. 未实施 D 中的 SW 说明列（D 桶，上界 50）与 GND 公共地白名单：二者不在 G1–G9 内，且 GND 在基线中为真实报出项，保留不动。

## 4. 离线重算方法

脚本：`round4/G/sim_g.py`（模式 `off|asis|contract|contract_src|minus_Gn`），辅助：`retention.py`、`bucket_residual.py`、`attribute_g.py`、`g6_detail.py`、`g8_detail.py`。输出 `sim_g_*.json`。
- 规则调用：真实 `R._run_many_to_one` / `R._run_cross_page_conflict`（修改后的 src），输入为 round-3 77 个项目的 `findings/pairs.parquet`。
- `off`：把 G1–G9 全部回退为修改前行为（harness 校验）。结果 many-to-one 643，与 round-3 审计与 D 的 V0 逐项一致（643/643），说明离线 harness 正确。
- `asis`：round-3 数据不变，仅 G 代码生效。
- `contract`：在 asis 上叠加两项派生，模拟 F 子代理将写入的字段：(a) sw_side=left 表行改为旧链左列形态（A）；(b) SW 普通配对两端均为 strip 表端子时，同 strip → `terminal_short_bridge`，跨 strip 且表中有行互相链接 → `terminal_cross_strip_link` + `strip_corroborated=True`，否则 `strip_corroborated=False`（E/G7）。派生结果：同 strip 2、跨 strip 佐证 451、未佐证 7。
- `contract_src`：敏感性，见偏离 3。

## 5. 离线结果

R-MANY-TO-ONE（原始规则输出条数，round-3 审计为 643，二者在无变更时一致）

| 模式 | 条数 | 说明 |
|---|---:|---|
| off（G 全部回退） | 643 | 与 round-3 一致 |
| asis（G 代码，数据不变） | 376 | 基线 13/13 保留 |
| contract（+A/E/G7 派生） | 210 | 基线 13/13 保留；相对 off 无新增标记 |
| contract_src（敏感性） | 7,756 | 不采纳，见偏离 3 |

留存按 D 的修复步骤（contract 模式）：

| D 步骤 | round-3 条数 | 仍报 | 备注 |
|---|---:|---:|---|
| A | 144 | 0 | 左列形态派生后全部豁免（asis 仍 144，依赖生产端改形态） |
| B | 54 | 0 | G1 |
| C | 111 | 0 | G2 |
| D | 50 | 50 | 说明列（D 桶）未实施，超出 G1–G9 |
| E | 113 | 106 | 派生只覆盖 strip 表可识别端子的 3 条同 strip + 451 跨 strip；余下为派生局限 |
| G | 12 | 6 | G5 覆盖后仍 6 条 |
| H | 23 | 0 | G3 |
| J | 77 | 19 | G6（39 条由 `structured_cardinality` 在去桥接子组上命中） |
| S+T | 30 | 0 | G4 |
| 残余 | 29 | 29 | 含 GND 9、串联晶格 10、KD23 类 6 等，按 D 结论保留 |

各 G 的边际贡献（asis 上逐项回退，many-to-one 变化）：G2 +166，G3 +61，G1 +52，G6 +39，G4 +30，G5 +4，G7 0。G8（cross）+6、G9（cross）+2。

R-CROSS-PAGE-CONFLICT（原始输出；round-3 审计为 23，后者经 `cluster_issues` 合并，离线未复现合并，仅按键比对）
- 全部回退：58；asis：50；contract：41，无新增。
- round-3 的 23 个键中，contract 仍报 6 个。

## 6. 基线保留逐条对照（contract 模式）

R-MANY-TO-ONE（基线 13 条，全部保留）
- p015 GND（左 1C9D-11）保留；p021 GND（左 1C9D-11）保留；p038 KD26（左 1-2ZLP4-1）保留；p039 1-2GD3（左 CD-23）保留；p039 1-2n221（左 1-2LP1-2）保留；p039 3-2n221（左 3-2LP1-2）保留；p039 KD1（左 1CLP1-1）保留；p039 KD6（左 1CLP2-1）保留；p040 1ZK-3（左 HD-1）保留；p049 KD26（左 1-2ZLP4-1）保留；p050 GND（左 1ID-5）保留；p071 GND（左 1-JD-21）保留；p075 GND（左 1-26TD-216）保留。

R-CROSS-PAGE-CONFLICT（基线 3 条，全部保留）
- p050 `1n/NCK305-5`（右 1CD3）保留；p065 `NCK305-1@c0`（右 1C1D1）保留；p066 `NCK305-5@c0`（右 1C2D1）保留。

## 7. 单元测试

- 新增 `tests/unit/test_superworks_round4_rules.py`：31 项，覆盖 G1–G9 各自的正例与反例，以及 A 的左右两列形态。
- 变异检查：分别关闭 G1、G2、G3、G5、G7、G8、G9、G4 时，对应正例测试失败（G6 因需要子组路径，无单独变异）。
- 全量 `pytest tests/unit -q`：本轮结束时 1644 passed, 1 skipped（同期另一子代理新增 `test_superworks_round4_producer.py`，计入总数，不属本轮修改）。
- 修改前基线：1590 passed, 1 skipped。

## 8. 给生产端（F 子代理）的依赖

- SW 端子排行 sw_side=left 行可改为旧链左列形态（`column_roles.left=terminal_endpoint`，端点在 `left_value/left_text_id`）；规则侧两种形态均接受。
- SW 连接线 Pair 若要参与规则，需写 `evidence.source="component_mapping"`（与 5,693 条已参与者一致），但须先整体复核（偏离 3）。
- G7 所需的 `terminal_cross_strip_link/strip_corroborated/strip_headers` 与 `terminal_short_bridge` 由生产端写入；离线派生值仅作估计，可能与生产端不同。
