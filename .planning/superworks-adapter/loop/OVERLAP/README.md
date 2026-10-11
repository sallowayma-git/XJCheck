# OVERLAP：叠放矛盾文字的识别口径（未提交）

## 1. 口径（用户定义，通用）

同一位置叠放内容互相矛盾的文字时：

- 能读出先后：取最晚的一批参与识别与校验，较早的一批静默丢弃（不产生 issue，只在 evidence 留痕：`overlapping_text_superseded=[{text_id,value,handle}]`、`overlap_resolution="latest_handle"`）。
- 读不出先后：保持待核验（现有缺端 issue），issue 的 message 与 explanation 写明“检测到文字重叠：值1 / 值2”。

DXF 实体无时间戳。同一 DXF 文件内句柄（hex）按创建顺序单调递增，以此作为先后依据。可读出先后的条件（全部满足）：

- 每段文字都有可解析的十六进制句柄（纯 hex，排除 `…:VIRTUAL:n`、`…:ATTRIB:n` 等合成句柄）；
- 同一 DXF 文件（file_id 相同）；
- 都是模型空间独立实体（`source_block_name` 为空，且不是 ATTRIB）；块内文字与模型空间文字不可比；
- 句柄两两不等。

同值文字不构成矛盾；与最晚文字同值的较早文字不列入 superseded。三段以上叠放取句柄最大者。

## 2. 改动文件与函数

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/extract/text_overlap.py`（新增） | `resolve_overlapping_texts(texts) -> TextOverlapResolution(winner, superseded, reason, values)`；`handle_order_key(text)`；`overlap_detected_text(values)`；`TextOverlapResolution.superseded_evidence()`。口径写在模块 docstring。 |
| `src/dwg_audit/audit/component_diagrams.py` | `extract_strip_two_port_component_pairs`：冲突处改为先解析叠放文字，可判则取最晚文字为端点，不可判维持未解析；`_build_strip_two_port_pair` 新增 `overlap` 参数并写 evidence；新增 `_coincident_external_texts`、`_bridge_endpoint_after_overlap`、`_overlap_evidence`；`extract_strip_two_port_endpoint_bridge_pairs` 与 `_build_strip_endpoint_bridge_pair`（新增 `overlaps` 参数）接入同一口径。 |
| `src/dwg_audit/audit/rules.py` | `_run_pair_missing_side`：`unresolved_component_port` 分支在 evidence 含 `overlapping_text_values` 时，message 追加“检测到文字重叠：…”，explanation 前置同文，extra 记录值列表。新增 import `overlap_detected_text`。 |
| `tests/unit/test_superworks_loop_text_overlap.py`（新增） | 22 个用例（见第 4 节）。 |

未改动：V2 模块、`symbol_port_proposal.py`、`candidates.py`、`table_extractor.py`、`terminal_port_bindings.py`、`superworks_semantics.py`。

注：G-1 改动（GND 豁免、unlabelled_port）已在提交 `9d42375` 进入 HEAD，本次改动在其上未提交。TextItem 已有 `handle` 字段，抽取阶段保留原始 hex（`cad_extract._append_text` 直接使用 `entity.dxf.handle`），无需新增字段。

## 3. 接入点清单

已接入：

1. 双边端子条端点（`_strip_endpoint_conflicts` 路径，`component_diagrams.py` 约 :140）：p003 的 4 处底端叠放，可判则取晚批；不可判维持未解析，rules 报“检测到文字重叠”。
2. 端子条端点桥接（`extract_strip_two_port_endpoint_bridge_pairs` 的端点选取）：原实现按距离与 text_id 选最近者，叠放矛盾时静默择一。现：可判先后取晚批（且晚批须是本侧桥接端点）；不可判则不生成桥接配对（不再按 text_id 择一）。注意：桥接配对是 context 性质（pass），不产生 issue，因此不可判的桥接叠放在报告中不可见，属已知缺口，需主线程决定是否要为其补 issue。

未接入（及原因）：

- `superworks_semantics.py` 端子标签匹配（`_definition_ports`，`same_value_distinct_text`）：是同值、不同实体的“同一名称多处出现”，不是内容矛盾，既有口径不变；块内文字本就按口径不可比。
- `superworks_extractor.py` `_coincident_ports`：比较的是 SuperWORKS 符号端口实例的接触点身份（来自 SW 元数据），不是图面文字叠放，且其排序依据不是文字句柄，不套用本口径。
- `rules.py` `_duplicate_missing_side_text_claim_groups`、`page_extractors.py` `duplicate_text_ids`：分别是同一文字被多条线组认领、以及 text_id 重复，不是内容矛盾的叠放文字。
- `candidates.py`、`table_extractor.py`、`terminal_port_bindings.py`：关键词检索（ambig / coincid / conflict / duplicate）只命中“不同位置的数字近邻”歧义或不同语义的冲突，未找到同位置矛盾文字的判定逻辑。
- `component_diagrams.py` KK 多端口与小端口盒路径：本次未逐行核对；grep 未见同类同位置矛盾文字的判定。列为未核对项。

## 4. 测试

- `tests/unit/test_superworks_loop_text_overlap.py`：22 个用例，覆盖：句柄可比性（hex、合成、块内、ATTRIB）；可判先后取晚批与顺序无关；三段叠放取最大句柄；同值较早文字不列入 superseded；句柄相等、非 hex、块内与模型空间混合、跨文件 → 不可判；不可判时 issue message/explanation 含“检测到文字重叠：8n401 / 8nB01”；非叠放不变；同值重复不算冲突；上方端不受下方叠放影响；桥接端点的可判取晚批、不可判不生成配对、晚批非桥接端点不生成配对、同值不变。
- 全量：`python -m pytest tests/unit -q` → 1878 passed, 1 skipped（含 G-1 测试 7 项）。

## 5. 回放对比（p003，相对 `.tmp/superworks_round12_full`）

- 结果：`.tmp/loop_overlap_p003`；比较 `.tmp/loop_overlap_p003_compare.json`。
- issues：4 → 0。移除的 4 条均为 R-PAIR-MISSING-SIDE：PCM0002（8KLP3-2）、PCM0005（8KLP2-2）、PCM0008（8KLP1-2）、PCM0012（8CLP1-2）。
- pairs：637 → 637。按内容键比较，仅 4 条 component_mapping 变化（pair_id 保持不变）：

| pair_id | 左端 | 前：右端 / 状态 | 后：右端 / 状态 | 保留的文字 | 被丢弃的文字 |
|---|---|---|---|---|---|
| PCM0002 | 8KLP3-2 | 无 / review | 8n401 / pass | 8n401（句柄 134B4） | 8nB01（12875） |
| PCM0005 | 8KLP2-2 | 无 / review | 8n402 / pass | 8n402（134AE） | 8nB12（1286F） |
| PCM0008 | 8KLP1-2 | 无 / review | 8n405 / pass | 8n405（134A8） | 8nB02（12869） |
| PCM0012 | 8CLP1-2 | 无 / review | 8n818 / pass | 8n818（1349C） | 8nD02（12863） |

- 其他 633 条配对的键与状态均不变。PC0029/PC0031/PC0033/PC0037（1↔8n4xx）仍为 discard，现与 component_mapping 的 8n4xx 端点一致，结果自洽。
- 渲染：`OVERLAP/OVERLAP_p003_endpoints.png`（脚本 `tools/render_endpoints.py`，只读 DXF 缓存）。绿色为保留文字，红色为丢弃文字，显示位置有 -2.2 的仅显示偏移。已知限制：线组（灰色）未绘出，图中仅有文字与端点。

受影响项目回放（语料扫描后，选取有端点类叠放的 p022、p028、p071）：

- p022、p028：配对与 issue 均不变。
- p071：配对不变，issue 4 条（前 5 条）。移除的是 R-MANY-TO-ONE（右端 GND，左端 1-JD21）。这是 G-1 的 GND 豁免所致（round12 基线早于 G-1），与本次叠放改动无关，已由 pairs 不变佐证。

## 6. 全语料影响面（只读，`tools/corpus_scan.py`，输入 round12 的 texts.parquet）

- 扫描 77 个项目。叠放矛盾位置（同一页、同位置、值互异、模型空间非 MARK）：19 处。
- 可判先后：19 处；不可判：0 处。
- 其中“端点类”（含合法外部端点值的文字）15 处，分布在 p003（4）、p022/p023/p024（各 1）、p028–p034（各 1）、p071（1，“1-57DK2 / 1A”，可判取 1A）。
- 非端点类 4 处：p015、p021（“1n / 2n”）、p036（“WBH-802-D1RA / D1SA”）、p071（另一处，示例未列全，见 JSON），均可判。
- 示例（各 3 条，项目/页/值/句柄）：
  - 端点类可判：p003 S0012，8nD02 / 8n818（12863 / 1349C，取 8n818）；p003 S0012，8nB02 / 8n405（12869 / 134A8，取 8n405）；p003 S0012，8nB12 / 8n402（1286F / 134AE，取 8n402）。
  - 非端点类可判：p015 S0012，1n / 2n（2n 句柄 1327F，1n 句柄 1CCFC，取 1n）；p036 S0015，WBH-802-D1RA / WBH-802-D1SA（D1SA 句柄 18DBC，D1RA 句柄 1A1D9，取 WBH-802-D1RA）；p071 S0004，1-57DK2 / 1A（22D9A / 262E3，取 1A）。
  - 不可判：0 处，无示例。
- 注：以上为 round12 基线的文字统计，不是 issue 统计。端点类 15 处中，只有 p003 的 4 处实际改变了配对结果（见第 5 节）。p022–p034 的 1QD2/1QD3 叠放已回放，配对未变，说明其不在双边端子条端点的窗口内。

## 7. 未决事项（交主线程）

1. 桥接叠放不可判时不生成配对且无 issue，是否需要补 issue（当前语料中未见此类实例，待定）。
2. KK 多端口与小端口盒路径未核对，是否需要同口径。
3. 本次改动未提交，HEAD 已含 G-1（`9d42375`）。

## 8. 产出位置

- 改动：`src/dwg_audit/extract/text_overlap.py`、`src/dwg_audit/audit/component_diagrams.py`、`src/dwg_audit/audit/rules.py`、`tests/unit/test_superworks_loop_text_overlap.py`。
- 工具：`loop/OVERLAP/tools/`（`compare_project.py`、`render_endpoints.py`、`corpus_scan.py`）。
- 图：`loop/OVERLAP/OVERLAP_p003_endpoints.png`。
- 复核数据：`.tmp/loop_overlap_p003/`、`.tmp/loop_overlap_affected/`、`.tmp/loop_overlap_src/`、`.tmp/loop_overlap_p003_compare.json`、`.tmp/loop_overlap_corpus_scan.json`、`.tmp/loop_overlap_p0{22,28,71}_compare.json`。
