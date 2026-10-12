# LEGACY-CENSUS：V1 / V2 旧链在 SuperWORKS 回放中的贡献普查

分支 `superworks-loop`。数据：第二十三轮全量回放 `.tmp/superworks_round23_full`（77 个项目、1,745 张页、终态配对 178,696 条、issue 40 条），代码快照 `round23_full_src`，冻结 DXF 经 `corpus_manifest.json` 只读访问。未修改 `src/`、`tests/`，未执行 git，未删除任何 `.tmp` 目录。控制台 `PYTHONIOENCODING=utf-8`。

## 0. 结论摘要

1. **来源分布。** 终态 178,696 条配对按来源分为：a 纯 SW 产出 34,969 条；b 旧配对已被 SW 修正或确认 63,327 条；c 纯旧链且两端在 SW 都有端口 18,947 条；d 纯旧链且至少一端 SW 无端口 61,453 条。
2. **pass 里的旧链成分。** 108,601 条 pass 中，有 35,620 条（32.8%）由旧链驱动（c、d、以及只被 SW 看到一端的 b2p）。其中 **26,437 条与同页一条 SW pass 配对的端点身份完全相同**，是重复而非新连接；878 条身份在项目其他页由 SW 给出，640 条同页 SW 给出的是非 pass，82 条是 b2p。**真正只有旧链给出的 pass 只有 7,583 条（占 pass 的 7.0%）。**
3. **这 7,583 条是什么。** 5,544 条是背板虚拟端子表（项目内没有 SW 同值配对；目视行对齐一致）；1,249 条是 V1 的导线型元件映射，其中目视多数穿越元件符号，疑似过度合并；641 条是元件引脚与外部标签之间的直连（目视为真实直连；其中导线型 636 条里，295 条能确认元件块不在 SW 符号表中，341 条证据缺块名）；其余 149 条为元件/端子排类杂项。
4. **review 里的旧链成分。** 无 SW 对应的 review 有 16,084 条，几乎全是单侧的 continuation（9,526）和 semantic_mapping（6,290）。这些本来就是 review，降级不影响 pass。
5. **issues。** 40 条中，29 条锚定在 b2（其中 25 条是 SW 只看到一端的部分证据，4 条是其他 SW 标注）、2 条锚定在 b1、9 条锚定在纯旧链 d。去掉 c、d 后会消失 9 条（3 条跨页冲突、2 条多对一、4 条缺端），其余 31 条不变，没有缩减的情况。新增 issue 离线无法精确判定，只能给出上界（见第 4 节）。
6. **V2。** 抽取阶段对 1,745 张 DXF 的复现显示：非 SW 图块推断出 4,119 个（文件 × 定义）有端口的条目、共 17,541 个原始端口；其中策略允许发射的有 1,425 条、4,766 个端口。**没有任何生产逻辑消费这些发射端口。** 唯一的生产消费是装置面板 IGNORE：19 个非 SW 图块定义（文件 × 定义）的标记使 227 条配对（223 discard、4 review、0 pass）被抑制。SW 端子几何（`labelled_terminal`）的 V2 端口被 95 条配对使用（68 pass、9 review、18 discard），全部是 b2p。audit_v2、electrical_networks、symbol_port_shadow、project_graph、engine_comparison、pair_geometry_shadow 这些影子产物不被 pairs/issues 的生产逻辑读取，只被报告重建、失效诊断和发布门禁读取；而且在 `runtime.profile=production` 下根本不计算。
7. **建议。** V1 不宜整体降为 review-only。先做同页同值重复去重（约 26,437 条 pass，不需要新的 SW 能力，不丢连接身份），再处理三类真实缺口：背板虚拟端子表（5,544 条）、V1 穿元件导线（约 1,249 条，主要是 V1 自身的线组/分段问题）、元件引脚直连（约 641 条，其中 295 条确认为非 SW 图块）。V2 的非 SW 提议扩充可以冻结，影子产物也应冻结。

## 1. 方法与口径

**数据来源。** 每个项目的 `*/findings/pairs.parquet`（终态）、`superworks_supersession.parquet`（台账）、`sw_ports.parquet`、`sw_port_coverage.parquet`、`sw_symbols.parquet`、`pages.parquet`、`audit/issues.parquet`。证据列是 JSON 字符串，已解析。页面类型用 `route_target|page_subtype`，因为 parquet 中的中文 `page_type` 已经损坏。项目家族由项目根路径中的 `GJ-xx`、`N2604`、`PAC-885` 推出，其余归为 other。

**来源标签（每条终态配对一个）。**

| 标签 | 定义 |
|---|---|
| a | 纯 SW 产出：`evidence.source == superworks`，且不替代任何旧配对（台账 old 为空），或不在台账中 |
| b1 | 旧配对被 SW 修正：台账中该配对作为新配对出现，且类别含 B/C/D（端子身份或文字被改） |
| b2 | 旧配对被 SW 证据确认或标注：台账类别 E/F，或 evidence 含 `superworks` / `superworks_constraints` / `sw_conflicts`。子类：b2e 为 SW 身份一致；b2p 为 SW 只看到一端（`partial`）；b2x 其他 |
| c | 纯旧链（evidence 无 SW 字段，且不在台账中）：两端文字 id 或身份在同页 SW 端口的 label/pin 中都能找到 |
| d | 纯旧链：至少一端在同页找不到 SW 端口 |

**重复判定（sw_dup）。** 对 c、d 配对，取无序端点值对 (左值, 右值)。若同页存在 a、b 类 SW 配对的值对相同，则记为 `same_sheet_sw_pass`（SW 为 pass）或 `same_sheet_sw_nonpass`；否则若项目其他页存在，记为 `project_only`；都没有则为 `none`。这是身份级判定，平行导线可能被误判；本次抽样未见此类情况，但没有全量核验。

**目视。** 每个桶取 3 例（固定种子，尽量分散到不同项目）。用冻结 DXF 经 ezdxf 渲染，蓝线为旧配对（左右端点），红框为同页 SW 端口（按文字 id 匹配），紫点为文字插入点，橙线为旧线组。目视结论是人工判读，不是电气验证。

**限制。** coverage 未重算（需要回放）。新增 issue 只给离线上界。V2 的离线复现用 ezdxf 直接读取模型空间的 INSERT（非嵌套），与生产的 CadDocument 读取器略有差异。95 条实际使用的 V2 端口直接来自 pair 证据，不依赖离线复现。

## 2. 四类来源：按状态与分表

### 2.1 总表（按来源与状态）

| 来源 | pass | review | discard | 合计 |
|---|---:|---:|---:|---:|
| a 纯 SW 产出 | 29,366 | 5,506 | 97 | 34,969 |
| b1 旧配对被 SW 修正 | 36,088 | 1 | 8 | 36,097 |
| b2e 旧配对被 SW 身份确认 | 7,527 | 0 | 355 | 7,882 |
| b2p SW 只看到一端（部分） | 82 | 2,313 | 16,949 | 19,344 |
| b2x 其他 | 0 | 4 | 0 | 4 |
| c 纯旧链，两端有 SW 端口 | 18,525 | 22 | 400 | 18,947 |
| d 纯旧链，至少一端无 SW 端口 | 17,013 | 19,946 | 24,494 | 61,453 |
| **合计** | **108,601** | **27,792** | **42,303** | **178,696** |

c、d 中 pass 和 review 的重复情况（`sw_dup`）：

| 类 | 状态 | same_sheet_sw_pass | same_sheet_sw_nonpass | project_only | none |
|---|---|---:|---:|---:|---:|
| c | pass | 17,263 | 0 | 13 | 1,249 |
| c | review | 0 | 0 | 0 | 22 |
| d | pass | 9,174 | 640 | 865 | 6,334 |
| d | review | 0 | 81 | 3,803 | 16,062 |

### 2.2 按家族（a/b/c/d × 状态）

| 家族 | a P | a R | a D | b P | b R | b D | c P | c R | c D | d P | d R | d D | 合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| N2604 | 7,805 | 1,425 | 24 | 11,243 | 485 | 3,779 | 5,063 | 4 | 108 | 3,953 | 4,975 | 7,149 | 46,013 |
| GJ-75 | 6,280 | 1,278 | 4 | 10,949 | 769 | 5,259 | 3,210 | 0 | 48 | 4,125 | 4,956 | 4,994 | 41,872 |
| GJ-76 | 6,625 | 1,216 | 54 | 8,588 | 401 | 4,260 | 3,446 | 7 | 116 | 2,704 | 3,608 | 5,248 | 36,273 |
| GJ-85 | 2,177 | 381 | 0 | 3,102 | 131 | 694 | 2,302 | 0 | 13 | 1,568 | 1,544 | 1,171 | 13,083 |
| GJ-81 | 1,676 | 240 | 0 | 2,450 | 122 | 326 | 834 | 0 | 34 | 1,144 | 1,132 | 1,782 | 9,740 |
| GJ-80 | 1,046 | 267 | 0 | 2,036 | 148 | 948 | 1,174 | 1 | 23 | 1,119 | 965 | 983 | 8,710 |
| GJ-74 | 1,028 | 183 | 6 | 1,323 | 65 | 602 | 652 | 2 | 23 | 538 | 787 | 947 | 6,156 |
| other | 922 | 178 | 0 | 1,331 | 77 | 506 | 837 | 1 | 5 | 618 | 671 | 611 | 5,757 |
| GJ-73 | 606 | 153 | 0 | 1,059 | 53 | 411 | 430 | 3 | 7 | 527 | 543 | 723 | 4,515 |
| GJ-79 | 765 | 123 | 9 | 897 | 31 | 391 | 410 | 4 | 18 | 386 | 512 | 467 | 4,013 |
| PAC-885 | 436 | 62 | 0 | 719 | 36 | 136 | 167 | 0 | 5 | 331 | 253 | 419 | 2,564 |
| **合计** | **29,366** | **5,506** | **97** | **43,697** | **2,318** | **17,312** | **18,525** | **22** | **400** | **17,013** | **19,946** | **24,494** | **178,696** |

### 2.3 按 pair_kind

| pair_kind | a P | a R | a D | b P | b R | b D | c P | c R | c D | d P | d R | d D | 合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ordinary_pair | 1,111 | 0 | 0 | 290 | 1,011 | 16,077 | 0 | 7 | 392 | 0 | 253 | 24,485 | 43,626 |
| wire_component_mapping | 2,368 | 5,489 | 97 | 14,975 | 249 | 442 | 18,525 | 0 | 8 | 1,216 | 27 | 9 | 43,405 |
| table_mapping | 455 | 0 | 0 | 20,351 | 0 | 0 | 0 | 0 | 0 | 15,441 | 0 | 0 | 36,247 |
| component_mapping | 20,294 | 0 | 0 | 7,660 | 0 | 0 | 0 | 0 | 0 | 340 | 18 | 0 | 28,312 |
| continuation | 0 | 0 | 0 | 0 | 8 | 15 | 0 | 0 | 0 | 0 | 11,946 | 0 | 11,969 |
| semantic_mapping | 0 | 0 | 0 | 0 | 1,050 | 778 | 0 | 15 | 0 | 16 | 7,643 | 0 | 9,502 |
| bridge_mapping | 5,138 | 17 | 0 | 421 | 0 | 0 | 0 | 0 | 0 | 0 | 59 | 0 | 5,635 |
| **合计** | **29,366** | **5,506** | **97** | **43,697** | **2,318** | **17,312** | **18,525** | **22** | **400** | **17,013** | **19,946** | **24,494** | **178,696** |

### 2.4 按页面类型

| 页面类型（route_target / page_subtype） | a P | a R | a D | b P | b R | b D | c P | c R | c D | d P | d R | d D | 合计 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| WireDiagramExtractor / grid_heavy_wire_diagram | 6,508 | 4,621 | 56 | 14,189 | 2,061 | 16,262 | 17,424 | 3 | 293 | 1,235 | 320 | 3,603 | 66,575 |
| TerminalDiagramExtractor / - | 455 | 0 | 0 | 20,351 | 0 | 0 | 0 | 0 | 0 | 39 | 19,337 | 10,250 | 50,432 |
| TableExtractor / backplate_virtual_terminal_table | 16,668 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 14,971 | 0 | 0 | 31,639 |
| ComponentDiagramExtractor / horizontal_component | 2,176 | 0 | 0 | 7,496 | 4 | 0 | 0 | 0 | 0 | 274 | 52 | 8,117 | 18,119 |
| WireDiagramExtractor / - | 1,684 | 776 | 39 | 1,533 | 253 | 1,050 | 1,101 | 19 | 107 | 63 | 237 | 2,524 | 9,386 |
| TableExtractor / backplate_geometric_table | 1,450 | 0 | 0 | 128 | 0 | 0 | 0 | 0 | 0 | 431 | 0 | 0 | 2,009 |
| TableExtractor / three_column_candidate | 425 | 109 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 536 |
| **合计** | **29,366** | **5,506** | **97** | **43,697** | **2,318** | **17,312** | **18,525** | **22** | **400** | **17,013** | **19,946** | **24,494** | **178,696** |

## 3. 只有旧链给出的连接

### 3.1 pass 的构成

| 类别 | 条数 | 占 pass |
|---|---:|---:|
| pass 合计 | 108,601 | 100% |
| V1 驱动 pass（c + d + b2p） | 35,620 | 32.8% |
| 其中：与同页 SW pass 身份相同（重复） | 26,437 | 24.3% |
| 其中：与项目其他页 SW 身份相同 | 878 | 0.8% |
| 其中：同页 SW 身份相同但 SW 非 pass | 640 | 0.6% |
| 其中：b2p（SW 只看到一端） | 82 | 0.1% |
| 其中：纯旧链，无任何 SW 对应（D3） | 7,583 | 7.0% |

D3 的构成：背板虚拟端子表 5,516 条，背板几何表 28 条（合计 5,544）；导线型元件映射 1,249 条（全部在 `grid_heavy_wire_diagram` 的 scoped、first_prefixed、inline_body 路径）；元件引脚直连 641 条（其中 295 条确认为非 SW 图块）；元件与端子排杂项 149 条。

### 3.2 Top 10 桶（c、d 的 pass + review，按桶总量排序）

桶键 = 标签 | 页面类型 | pair_kind | 对象子类 | 原因。原因：c 为两端 SW 端口的状态，d 为无 SW 端口的端数（both_blind / one_side_blind）及匹配方式（identity_elsewhere 指身份只在项目其他页出现）。

| # | 桶（页面 / pair_kind / 对象 / 原因） | pass | review | 项目数 | 同页 SW 重复占比 | 无 SW 对应占比 | 目视结论 | 图 |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | d / TerminalDiagramExtractor/- / continuation / sk:continuation_single_sided / both_blind:none/none | 0 | 11,932 | 77 | 0.0% | 79.7% | continuation, single-sided (terminal row to another page)：one-sided by design; review only; no pass loss | `png/bucket_01.png` |
| 2 | c / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:explicit_external_device_lead / sw:port_consumed_by_other_sw_pair/port_consumed_by_other_sw_pair | 10,148 | 0 | 67 | 100.0% | 0.0% | explicit external lead: component pin to external label：visually real straight wire in 3/3; SW pass pair with identical values on the same sheet in 3/3 | `png/bucket_02.png` |
| 3 | d / TableExtractor/backplate_virtual_terminal_table / table_mapping / tm:backplate_virtual_table / both_blind:identity_elsewhere/identity_elsewhere | 7,473 | 0 | 56 | 91.4% | 0.6% | backplate virtual table, identity elsewhere on both ends：row alignment consistent; 91% already confirmed by an identical SW pass pair on the sheet | `png/bucket_03.png` |
| 4 | d / TerminalDiagramExtractor/- / semantic_mapping / sk:terminal_semantic_mapping / both_blind:none/none | 0 | 7,332 | 69 | 0.0% | 81.9% | semantic terminal mapping, single-sided annotation：one-sided; review only; no pass loss | `png/bucket_04.png` |
| 5 | d / TableExtractor/backplate_virtual_terminal_table / table_mapping / tm:backplate_virtual_table / both_blind:none/identity_elsewhere | 4,662 | 0 | 56 | 3.3% | 96.0% | backplate virtual table, one end with identity elsewhere：row alignment consistent; 96% no SW counterpart (SW blind) | `png/bucket_05.png` |
| 6 | c / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:scoped_visible_prefix_external_endpoint_mapping / sw:port_consumed_by_other_sw_pair/port_consumed_by_other_sw_pair | 4,319 | 0 | 65 | 79.0% | 21.0% | scoped visible prefix, component pin to external label：mixed: 79% duplicate an SW pass pair; the rest include device-crossing runs | `png/bucket_06.png` |
| 7 | c / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:input_matrix_wire_mapping / sw:port_consumed_by_other_sw_pair/port_consumed_by_other_sw_pair | 2,104 | 0 | 14 | 100.0% | 0.0% | input matrix wire mapping, device pin to label：straight wire visually real; 100% duplicate an SW pass pair | `png/bucket_07.png` |
| 8 | d / TableExtractor/backplate_virtual_terminal_table / table_mapping / tm:backplate_virtual_table / both_blind:identity_elsewhere/none | 1,775 | 0 | 56 | 94.9% | 1.6% | backplate virtual table, identity elsewhere on one end：row alignment consistent; 95% duplicate an SW pass pair | `png/bucket_08.png` |
| 9 | d / TableExtractor/backplate_virtual_terminal_table / table_mapping / tm:backplate_virtual_table / both_blind:none/none | 1,061 | 0 | 44 | 8.7% | 91.3% | backplate virtual table, neither end has identity：row alignment consistent; 91% no SW counterpart (SW blind) | `png/bucket_09.png` |
| 10 | c / WireDiagramExtractor/- / wire_component_mapping / cs:explicit_external_device_lead / sw:port_consumed_by_other_sw_pair/port_consumed_by_other_sw_pair | 710 | 0 | 52 | 100.0% | 0.0% | explicit external lead, short leads：visually real short wire in 3/3; 100% duplicate an SW pass pair | `png/bucket_10.png` |

整体读数：Top 10 中，桶 2、7、10 基本全部是 SW 已有同值 pass 的重复（端点身份完全相同）。桶 1、4 是单侧的 continuation / semantic 注释，本身就是 review。桶 3、5、8、9 是背板虚拟端子表的行映射，目视行对齐一致，但重复占比差异很大（桶 5、9 是 SW 盲区，桶 3、8 基本已被 SW 的同值 pass 覆盖）。桶 6 混合，既有重复也有穿元件的路径。

### 3.3 只有旧链给出的 pass 桶（D3 Top 7）

| # | 桶（页面 / pair_kind / 对象 / 原因） | pass | review | 项目数 | 同页 SW 重复占比 | 无 SW 对应占比 | 目视结论 | 图 |
|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | d / TableExtractor/backplate_virtual_terminal_table / table_mapping / tm:backplate_virtual_table / both_blind:none/identity_elsewhere | 4,477 | 0 | 51 | 3.3% | 96.0% | backplate virtual table, row label to label (identity on one side elsewhere)：row alignment consistent; no SW counterpart; the largest pure-V1 pass bucket | `png/d3_01.png` |
| 2 | d / TableExtractor/backplate_virtual_terminal_table / table_mapping / tm:backplate_virtual_table / both_blind:none/none | 969 | 0 | 38 | 8.7% | 91.3% | backplate virtual table, neither end has identity：row alignment consistent; no SW counterpart | `png/d3_02.png` |
| 3 | c / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:scoped_visible_prefix_external_endpoint_mapping / sw:port_consumed_by_other_sw_pair/port_consumed_by_other_sw_pair | 906 | 0 | 61 | 79.0% | 21.0% | scoped prefix, terminal to label：3/3 sampled cross a device symbol on the path; likely over-merged, needs manual check | `png/d3_03.png` |
| 4 | d / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:scoped_visible_prefix_external_endpoint_mapping / one_side_blind:none/port_by_text | 318 | 0 | 30 | 0.0% | 100.0% | scoped prefix, one side is a non-SW device pin：straight device-pin-to-label wire, visually real; SW blind on non-SW block | `png/d3_04.png` |
| 5 | d / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:inline_body_port_mapping / one_side_blind:none/port_by_text | 258 | 0 | 41 | 47.7% | 52.3% | inline body port, one side is a non-SW device pin：2/3 straight device-pin-to-label wires; 1/3 crosses a device circle on the path; SW blind on the device | `png/d3_05.png` |
| 6 | c / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:first_prefixed_external_endpoint_mapping / sw:port_consumed_by_other_sw_pair/port_consumed_by_other_sw_pair | 155 | 0 | 38 | 75.2% | 24.8% | first-prefixed mapping, row wire spanning several devices：3/3 span several device symbols; likely over-merged | `png/d3_06.png` |
| 7 | c / WireDiagramExtractor/grid_heavy_wire_diagram / wire_component_mapping / cs:scoped_visible_prefix_external_endpoint_mapping / sw:port_consumed_by_other_sw_pair/port_no_wire_contact | 128 | 0 | 40 | 0.0% | 97.0% | scoped prefix, one side with no wire contact in SW：mixed: straight runs and device-crossing runs | `png/d3_07.png` |

注：D3 的 pass 计数只统计 `sw_dup == none` 的配对。表中“无 SW 对应占比”是对完整桶的估计，不是 D3 子集的占比。

目视要点：
- 背板虚拟端子表（D3 桶 1、2）：行标签与右侧标签同一行对齐，单看图形是合理的表格行映射。SW 在该页没有 strip 或端口记录，因此无法覆盖。是否真实连接需要电气核对，本次只能确认表格几何一致。
- 导线型元件映射穿越元件（D3 桶 3、6）：抽样 3/3 的旧配对路径上有元件符号（D3 桶 3）或穿越多个元件（D3 桶 6），疑似过度合并。这更像 V1 线组把穿过元件的导线合并为一条，WIRE-BREAK 的切分依据是 SW 端口或未登记 SYMB2 的 TERMPOINT 标记，这些元件本体上未必有此类标记，需核对。
- 元件引脚直连（D3 桶 4、5）：元件引脚到外部标签的直线连接，桶 4 目视 3/3 为真实直连，桶 5 目视 2/3 为直连、1/3 穿过元件圆形符号。SW 在该端没有端口。在 D3 的 636 条导线型配对中，295 条能确认元件块不在 SW 符号表中，341 条的证据里没有块名，需要单独核对。

### 3.4 review 里只有旧链给出的部分

16,084 条：continuation 9,526、semantic_mapping 6,290、ordinary_pair 182、bridge_mapping 59、component_mapping 18、wire_component_mapping 9。continuation 与 semantic 目视为单侧（一端为空）的行注释或跨页去向，不是两端连接；它们已在 review 中，降级不增加 pass 损失。

## 4. issues 依赖与去掉 c、d 的影响

40 条 issue 的依赖来源：

| 规则 | 条数 | 锚定配对来源 |
|---|---:|---|
| R-SUPERWORKS-CONFLICT | 17 | b2p 16（discard）、b1 1（review） |
| R-PAIR-LOW-CONFIDENCE | 13 | b2p 9、b2x 4（review） |
| R-PAIR-MISSING-SIDE | 4 | d 4（review，p041–p044 的 PCM0023/PCM0027） |
| R-MANY-TO-ONE | 3 | d 2（p039）、b1 1（p040） |
| R-CROSS-PAGE-CONFLICT | 3 | d 3（p050、p065、p066，成员全部为 d） |

去掉 c、d 后的离线结果：消失 9 条，缩减 0 条，不变 31 条。消失的 9 条如下：

| 项目 | issue | 规则 | 锚定配对 | 成员来源 |
|---|---|---|---|---|
| p039 | I0002 | R-MANY-TO-ONE | PCM0024 | 2 个 d 成员（全部被去掉） |
| p039 | I0001 | R-MANY-TO-ONE | PCM0014 | 2 个 d 成员（全部被去掉） |
| p041 | I0001 | R-PAIR-MISSING-SIDE | PCM0023 | 1 个 d 成员（全部被去掉） |
| p042 | I0001 | R-PAIR-MISSING-SIDE | PCM0023 | 1 个 d 成员（全部被去掉） |
| p043 | I0001 | R-PAIR-MISSING-SIDE | PCM0027 | 1 个 d 成员（全部被去掉） |
| p044 | I0001 | R-PAIR-MISSING-SIDE | PCM0027 | 1 个 d 成员（全部被去掉） |
| p050 | I0001 | R-CROSS-PAGE-CONFLICT | P0208 | 24 个 d 成员（全部被去掉） |
| p065 | I0001 | R-CROSS-PAGE-CONFLICT | P0076 | 16 个 d 成员（全部被去掉） |
| p066 | I0001 | R-CROSS-PAGE-CONFLICT | P0034 | 36 个 d 成员（全部被去掉） |

离线无法精确判定新增 issue。上界：若 V1 的 pass 全部降为 review，纯旧链中 `ordinary_pair` 或 `component_mapping` 且两端有值的 pass 有 340 条，这些可能触发 R-PAIR-LOW-CONFIDENCE。该规则（`rules.py` 的 `_run_pair_low_confidence`）对非 discard、且为 ordinary 可用或 component_mapping、且不是高置信 pass 的配对报出，因此降级后会被纳入。这是上界，需要回放确认。

## 5. V2 使用情况

### 5.1 抽取阶段的提议（离线复现，1,745 张 DXF，11,968 行，全部为模型空间中的 INSERT 定义）

| 项 | 数量 |
|---|---:|
| SW 符号的 `labelled_terminal.generic.v1`（文件 × 定义） | 2,820 行，原始端口 7,145 |
| 非 SW 图块（文件 × 定义） | 6,016 行 |
| 　其中有端口的行 | 4,119 行，原始端口 17,541 |
| 　其中策略允许发射端口（`allow_port_emission=True`）的行 | 1,425 行，端口 4,766（多端元件 604 行/2,948；两端元件 814 行/1,628；通信面板 2 行/180；WFS 极性 5 行/10） |
| 　其中 `labelled_terminal` 族（会进入端子绑定） | 0 行 |

非 SW 有端口的行，按策略行为：IGNORE 2,263、EXTERNAL_PORTS_ONLY 1,425、REVIEW_ONLY 384、TABLE_CONTAINER 39、WIRE_PRIMITIVE 8。

### 5.2 实际被配对使用的情况

| 消费路径 | 配对数（pass / review / discard） | 来源 | 说明 |
|---|---|---|---|
| SW 端子几何绑定（`bind_labelled_terminal_ports` → `terminal_port_bindings` → `WireDiagramExtractor`） | 95（68 / 9 / 18） | 全部 b2p | 每条使用一个 SW 端子的物理端点；这 95 条都是 wire_component_mapping |
| 非 SW 发射端口 | 0 | — | 没有生产消费者：`allow_port_emission` 只在 `page_extractors.py:2572` 用于 IGNORE 判定，在 `symbol_port_proposal.py` 内部使用 |
| 装置面板 IGNORE（`mark_ignored_equipment_panel_ordinary_pairs`） | 227（0 / 4 / 223） | 非 SW 面板图块 | 只有 `communication.equipment_panel_ignored.v1` 族（19 行）；被抑制的旧配对全部为 discard 或 review |

结论：V2 的非 SW 提议，对配对的影响只有 227 条被抑制（且 0 条 pass）；其余约 17,500 个端口没有任何消费者。SW 端子几何绑定只出现在 b2p 中，它给 68 条 pass 提供了几何端点，但 SW 只看到一端。

### 5.3 影子产物是否被生产逻辑读取（grep 验证）

- `audit_v2.py`：`build_audit_v2_issue_clusters`、`summarize_audit_v2`、`compare_legacy_new_relations` 只在 `report/artifacts.py`（1368、1517、1529）和 `report/rerun.py`（294–303）调用。
- `electrical_networks.py`：只在 `report/artifacts.py`（1189–1256）调用。
- `symbol_port_shadow.py`：只在 `report/artifacts.py`（997–1020）调用。
- `geometry_graph.py`（pair_geometry_shadow）：`report/artifacts.py`（1229–1341）写出；`report/baseline.py`（79–82）读取其摘要。
- `project_graph.py`：`report/artifacts.py`（1360）调用；`report/rerun.py`（273）和 `report/promotion_gate.py`（244）读取。
- `failure_queue.py`：`report/artifacts.py`（1536）和 `report/rerun.py`（25）调用。
- 门禁与评估读取：`report/promotion_gate.py`（254、239）读取 `audit_v2_summary.json` 的 witness_completeness 和 `engine_comparison_v1.json`，经 CLI `evaluate-promotion-gate`（cli.py:690）作为放行判据；`report/hard_issue_eval.py`（159）经 CLI `evaluate-hard-issues`（cli.py:662）读取 `audit_v2_summary.json`。

这些影子产物只在 `report/artifacts.py` 的完整写出路径中计算。`runtime.profile` 为 `production` 时，`_write_production_core_artifacts` 会提前返回（artifacts.py:583–599），因此它们不被计算。本轮回放的 corpus 配置正是 `production`，所以回放产物中没有 `audit_v2_*`、`electrical_networks_v2`、`symbol_port_shadow_*` 等文件。代码默认 profile 是 `regression`（`utils/config.py:225`），所以未配置时的普通运行会计算它们。

### 5.4 与原设计口径的差异

`prompt.md` 第 140 行写的是 Topology V2 “目前只记录、不影响配对结果”。实际有两条生产路径消费 V2 的 symbol proposal：端子几何绑定（95 条 b2p）和装置面板 IGNORE（227 条）。这两条都是既有代码，不是本轮 SW 工作引入的。文档口径需要更新。

## 6. 结论与建议

### 6.1 V1 能否降为“只出 review 的兜底”

- **字面降级**（V1 驱动的 pass 35,620 条全部降为 review）：pass 从 108,601 降到 72,981，减少 32.8%。其中 26,437 条是与 SW pass 同页同值的重复，降级不丢连接身份，只是丢掉了重复计数；真正丢失的连接是 7,583 条 D3，外加 878、640、82 条有 SW 旁证但不完整的配对。
- **先去重再降级**（P1 之后）：pass 减少 26,437（去重本身，不需要降级）。之后 V1 驱动 pass 剩 9,183 条（8.5%）。
- **不建议直接降级 D3 的 7,583 条**：其中 5,544 条是背板表格，1,249 条穿元件导线（应先修），641 条是元件引脚直连（其中 295 条确认为非 SW 图块，需要 SW 或 V2 的身份）。

### 6.2 仍不可替代的能力

1. **V1 线组构建**：SW 的 b1 配对也依赖 V1 的线组（`line_groups`），所以降级只能限定在配对判定层，不能降到几何提取层。
2. **背板虚拟端子表的行映射**（D3 中 5,516 条）：SW 在这些页没有 strip 或端口记录。
3. **元件引脚与标签直连**（D3 中约 641 条，其中 295 条确认为非 SW 图块）：SW 在该端的盲区，目视为真实。
4. **装置面板 IGNORE 抑制**（V2 唯一生产消费，227 条）：抑制效果依赖 V2 的几何判定。
5. **单侧 continuation、semantic 注释**：只在 review 中，信息价值在于跨页去向提示。
6. **SW 端子几何绑定**（95 条，全部 b2p）：只在 SW 只看到一端时提供几何端点。

### 6.3 可以冻结的部分

- V2 非 SW 图块的提议扩充（`symbol_port_proposal.py` 新增家族）：发射端口没有消费者，继续扩充只增加 artifact，不增加 pass。
- V2 影子产物（audit_v2、electrical_networks、symbol_port_shadow、project_graph、engine_comparison、pair_geometry_shadow）：只被报告和门禁读取。冻结时需先处理门禁，因为 `evaluate-promotion-gate` 依赖 `witness_completeness` 与 `engine_comparison`。
- 手写端子库的扩充：不再新增按家族或按页型的规则。

### 6.4 降级前置条件（按序）

| 序号 | 动作 | 影响（离线） | 是否需要新 SW 能力 |
|---|---|---|---|
| P1 | 同页同值重复去重：c、d 中与同页 SW pass 配对身份相同的旧配对不再保留为 pass | pass −26,437，不丢身份 | 否（只用台账和现有 pass 配对） |
| P2 | 背板虚拟端子表：在 SW 侧给出 strip 或虚拟端子表覆盖；否则接受这 5,544 条降为 review | pass −5,544（若不覆盖） | 是（或接受降级） |
| P3 | V1 导线型元件映射的穿元件判据：直线路径穿越元件本体时不配对，或降为 review（抽样显示多数穿元件） | pass 最多 −1,249 | 否（V1 内部修正，需回放） |
| P4 | 元件引脚直连（295 条确认为非 SW 图块）：V2 提议的端口身份接入消费，或接受降为 review | pass −641（若不接入） | 是（或接受降级） |
| P5 | 回放验证：新增 issue（上界 340）和 coverage 变化 | — | 否 |

完成 P1 至 P4 后，V1 驱动的 pass 中剩下的是 878、640、82 条有旁证但不完整的配对，可以降为 review。此时 V1 才适合作为只出 review 的兜底。

## 7. 文件与复现

- `details.json`：全部表格、Top 桶、issue 依赖表（40 行）、V2 统计，以及每个桶的示例配对 id。
- `top10_buckets.csv`、`top7_buckets_d3.csv`：桶排序。
- `png/bucket_01..10.png`（c、d 的 Top 10）、`png/d3_01..07.png`（D3 Top 7）：每张含 3 个面板，共 17 张。
- `tools/`：`build_tagged.py`（标签与 c/d 分类）、`analysis.py`（重复标志与 issue 依赖）、`v2_proposals.py`（V2 提议离线复现）、`buckets.py`（桶与抽样）、`render_buckets.py`（渲染）、`report_tables.py`（details.json）、`make_readme.py`（本文件表格）。复现顺序：`build_tagged` → `v2_proposals` → `analysis` → `buckets`（raw 与 d3）→ `render_buckets`（raw 与 d3）→ `report_tables` → `make_readme`。
- 中间表：`.tmp/legacy_census_work/`（可删）：`pairs_tagged*.parquet`、`v2_proposals.parquet`、`v2_port_usage.parquet`、`samples*.json`、`analysis.json`、`v2_proposals.log`。

## 更正（P2-BACKPLATE）

本节更正上文第 3 节与 3.1 节中“背板虚拟端子表 5,544 条是 SW 盲区”的说法，并不改动上文的数字与表格。

- 背板虚拟端子表并非约 96% 为 SW 盲区。第二十三轮离线口径下，D3 背板行的 4,986 / 5,571（89.5%）已有同页 SW pass 配对共享同一外部端子 R 且行号一致（随机置换对照约 2.6%）。上文以“两端值对完全相等”判重，因端子文字写法不同（如 V1 `1-1n/NR1181C-3` 对 SW `1n0503`）而漏掉了这一类。
- 第二十四轮基线的背板虚拟表 pass 为 6,238 条。P2-BACKPLATE 修订后（全量回放 `round25`）：3,910 → 4,047 条获得 SW 佐证；同页行号冲突的 32 条经 J 类取代；装置前缀标题修正使 183 条候选与 SW 一致，剩余 95 条为候选。
- 修订后背板虚拟表 pass 为 4,254 条，其余为 discard（I 类重复或 J 类取代），每条 discard 都有存活的 SW pass 配对。
- 仍无 SW 佐证的背板 pass 主要是 V1 没有复合装置名的配对（装置修正后显著减少，但未全部消除），见 `loop/P2-BACKPLATE/IMPL.md` 第 11 节。
