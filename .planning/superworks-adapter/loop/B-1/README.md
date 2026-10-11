# B-1：R-PAIR-MISSING-SIDE 裸 n 线号单端 5 条视觉核查（只读）

数据：`.tmp/superworks_round12_full`（findings parquet）；DXF 取 `corpus_manifest.json` 指向的冻结缓存（只读，未删除或修改）。未改动 src/、tests/，未执行 git。截图 `B1_*.png`，证据 `details.json`，脚本与中间表在 `tools/`。

## 1. 结论

用户怀疑是识别引擎没认出来。核查结果：不是引擎漏接线，也不是跨页线号。5 条都是器件标注引线：4 条在 SuperWORKS 中绑定到器件（器件版式 LINE），1 条（PC0053）为未绑定的同形器件头。左端隐形数字是器件序号，裸 n 文字是器件标签，线段空端不接任何东西。引擎把隐形序号当成了可见端子，于是产生"缺一侧"。

| 项目 / pair | 页 | (a/b/c) | 一句话证据 |
|---|---|---|---|
| p062 PC0019（52n） | S0012 F0012 | c | 器件 170A7 (DELL XSQ) 的 LDPARTLAYT_LINE=170A9（本线段）、PARTNO=170AA（"7"）、PARTLABEL=170AB（52n）、PARTTYPE=170AC；空端 1 单位内无实体，最近器件块顶边 13.0 |
| p062 PC0125（58n） | S0013 F0013 | c | 器件 1152C (ATW1000-H) 的 LINE=11530、PARTNO=11531（"8"）、PARTLABEL=11532（58n）；空端距器件顶边 4.33，SW 端口最近 24.6 |
| p071 PC0053（1n/51n/25n） | S0011 F0011 | c（未绑定 + 线组合并产物） | 簇中所有元素 LDPARTLAYT_PART_HANDLE=0（未绑定器件）；线组由两条平行引线 2D7E 与 6F25 合并，空端实为 6F25 端部（与线组端点仅差 0.63） |
| p075 PC0232（1-26n） | S0014 F0014 | c | 器件 3214C (TS3000-Z01) 的 LINE=3214E、PARTNO=3214F（"8"）、PARTLABEL=32150（1-26n）；空端距器件顶边 8.0，无端口 |
| p075 PC0440（2-26n） | S0015 F0015 | c | 器件 3205D (TS3000-Z01) 的 LINE=3205F、PARTNO=32060（"9"）、PARTLABEL=32061（2-26n）；与 PC0232 几何完全相同（F0014/F0015 两页模板） |

逐项回答用户问题：
1. 缺失端在图面上接的是什么：什么也不接。空端 1 单位内只有本器件的标签文字；最近的几何是器件块边框（4.3–13 单位），PC0053 是另一条平行引线的端部（0.63 单位）。
2. (a) 引擎漏接：不成立，同页没有可接对象，且 SW 端口都不在空端附近。(b) 跨页去向：不成立，裸 n 是器件标签，不是线号；同名文字在其他页只是二次原理图上的 DIM 引用。(c) 其他：成立，器件标注引线被当成端子线。
3. XDATA：有，但只有版式类。5 条的线段、数字、标签、型号都挂在 `LDPARTLAYT_*` 记录上（器件 INSERT 持有 LINE/PARTNO/PARTLABEL/PARTTYPE 句柄，文字与线段反向指向 PART_HANDLE）。线段、数字、标签与器件 INSERT 上均无 `LD_ConnectLine`、`LD_SYMB2_LABEL`、`LD_CONNECT_DOT` 等连线元数据，因此没有 LD_* 能给出另一端身份。PC0053 的 PART_HANDLE 为 "0"，即未绑定。
4. 跨页器件唯一性：52n 仅对应 S0012 的 /170A7；58n 仅对应 S0013 的 /1152C；1-26n 仅对应 S0014 的 /3214C；2-26n 仅对应 S0015 的 /3205D。各自都在二次原理图页上有 DIM 引用（52n：F0005、F0007；58n：F0005、F0007；1-26n/2-26n：F0004–F0012）。器件能唯一确定，但引线没有另一端可跟随，所以"另一端"不适用。
5. 通用解析：不应把裸 n 当作线号端点，而应以 SW 器件实例（part_no、label）识别为标注引线（见第 3 节）。

## 2. 引擎丢失信息的位置（按链路）

1. **根因：文字高度被钳制**。`src/dwg_audit/extract/cad_extract.py:348`（bbox）与 `:362`（`height=max(height, 1.0)`，`_append_text`）。DXF 隐形文字 height=1e-05 被提升为 1.0。
2. **高度门放行**。`src/dwg_audit/audit/candidates.py:208`（`within_height = min_height <= text.height <= max_height`，min 1.0，见 `config.py:96`）。若保留原始 1e-05，`candidates.py:273` 会以 `height_out_of_range` 拒绝。
3. **端子候选被接受**，score 0.90（距离项与侧向项；隐形文字无高度加分）。5 条的左端候选 CC0032、CC0664、CC0345、CC4149、CC8207 均为 accepted。
4. **SW 已知但未消费**。`src/dwg_audit/extract/superworks_semantics.py:447` 把 `LDPARTLAYT_PARTNO_HANDLE` 写入 `sw_part_instances.part_no`，但候选与 pairs 路径不读取它来排除序号；`superworks_supersession` 对这些数字零记录。
5. **单侧登记为 review**。`src/dwg_audit/audit/pairs.py:69–75`：`missing right candidate`，status=review，confidence 0.44。没有"器件标注引线"分支。
6. **裸 n 被当噪声**（结果正确、理由错误）。`candidates.py:249`、`:1949`（not_numeric）；`config.py:140–145` 中元件接线图的 numeric_suffix_patterns 只接受 `n\d{3,}`（另有 CD/GD/ZK/HD 规则）。52n、1-26n、1-1n、25n 都被判为非数字。
7. **跨页路径不适用**。`src/dwg_audit/audit/project_graph.py:256`（build_cross_page_endpoint_candidates）只用 AUTHORITATIVE 标签。器件标签在多页出现，若用它做跨页端点，会把器件引用误连为线。本案不应进入该路径。
8. **MARK 降权（次要）**。`config.py:99`，penalty 0.03（`candidates.py:968`），不是决定因素。
9. **线组合并（仅 PC0053）**。`src/dwg_audit/audit/line_groups.py:412–466`（`_can_merge_axis_intervals`）：区间重叠时直接返回 True，横向差 1.26 ≤ `cross_axis_tolerance` 2.5（`config.py:86`）。两条平行引线被合并，端点取平均 y。
10. **文字锚点（次要，全局）**。`candidates.py:191–192` 使用 `text.insert_x`（原始 insert），居中对齐文字的对齐点偏差约 2.3 单位（52n：insert (305.84,136.01)，对齐点 (308.09,137.51)）。SW 侧的 `text_anchor_wcs` 已正确处理，端子候选路径未用。

## 3. 修复建议

- **F1（核心，`cad_extract.py:348/362`）**：保留原始 DXF 高度（TextItem 增加 raw_height；bbox 仍可用 max(h,1.0)）。raw_height<0.01 的数字文字从端子候选排除，reason 记为 `hidden_text`。效果见第 4 节。
- **F2（核心，`candidates.py` 端子循环 + `superworks_semantics.py:447` 的 part_no）**：若数字文字的 text_id 精确等于某 SW 实例的 part_no，则排除出 terminal 通道，并在 pairs 层标注为 `device_header_leader`（注释性，不计缺侧）。覆盖 13 条中的 SW 确认项。
- **F3（补充，`pairs.py:69–75`）**：无 SW 绑定的器件头（MARK 水平短线 ≤32 单位，一端隐形数字，上方 n 标签，下方器件型号，空端 1 单位内无实体）归为 `unbound_device_header`，不进入 R-PAIR-MISSING-SIDE。任一条件不满足则保持 review，不得只凭 n 标签判定。
- **F4（补充，`line_groups.py:412–466`）**：重叠区间横向差 >0.5 且两线各自带独立端子文字时不合并。PC0053 类需要语料回归，影响面预计较小。
- **不建议**：
  - 放宽 numeric_suffix 接受裸 n（如 52n、1-26n）。会生成 7↔52n、8↔58n 等错误 pair。
  - 把"裸 n 跨页标记"（Z-5 建议 B 的 cross_page_marker 类）用于这 5 条。证据不支持，应撤回 Z-5 第 3 条建议。
  - 把裸 n 规则推广到 DIM 或 CONNECT 层。那里的 171 条是真正的跨页线号关系（semantic_mapping）。

## 4. 影响面（round12 全语料）

- 77 个项目、1745 个 DXF 文件、488,951 条 TEXT。数字文字 height=1e-05 共 4,070 条（图层分布未逐条统计；另有 26,954 条非数字 height=0.001 同样被钳制，未逐条分析）。
- round12 审计文字中，隐形数字 3,945 条（全部 is_numeric_candidate=True）。其中仅 26 条实际成为 accepted 端子候选（p051 6、p062 4、p069 1、p071 13、p075 2），经 texts 表核对全部在 MARK 层。
- 这 26 条候选影响的 pair：
  - 14 条单端 review（全部 MARK、元件接线图、ordinary_pair）：其中 9 条带裸 n 标签（p051 PC0075/PC0104/PC0127/PC0152，p062 PC0019/PC0125，p071 PC0053，p075 PC0232/PC0440），5 条无 n 标签（p051 PC0203/PC0204，p062 PC0120/PC0121，p069 PC0074）。SW part_no 确认 13 条，PC0053 未确认。
  - 5 条双端 discard（p071：PC0052 为 1↔37 且两端都是隐形数字，PC0054 1↔6，PC0019 2↔2，PC0001 3↔14，PC0010 4↔11）。
  - 6 个候选未保留到任何 pair。
  - 另有 3 条 table_mapping pass（P0001、P0003、P0004，均在 p071 S0008/S0009）用隐形数字作为表格单元（T0441 "2"、T0659 "4"、T0653 "2"）。它们与同一器件头模板同形（AEC6 "2" + 2-2n + WYD-811），疑似误 pass。**须人工复核，本轮未确认是否误判。**
- 全语料单端 pair：25,218（review 22,124；discard 3,094；pass 0）。
- 缺侧端 16 单位内有裸 n 文字的单端 pair：193（review 191；discard 2；pass 0）。按线所在图层：
  - DIM 138（semantic_mapping，二次原理图跨页线号，不受 F1–F3 影响）
  - CONNECT 33（semantic/wire mapping，不受影响）
  - "0" 13（2 条 discard 为 GND 覆盖，11 条 review）
  - MARK 9（ordinary_pair、元件接线图、全部 review；其中 8 条 SW 确认，1 条为 PC0053）。这 9 条就是本类器件头，是 F1–F3 的目标。
- F1 对 DIM/CONNECT 无影响（26 条隐形候选全部在 MARK 层）。
- 风险点：3 条 table_mapping pass 依赖隐形数字，F1 实施时会一并改变，须先人工确认其正确性再决定是否纳入。

## 5. 对前一轮（Z-5）的修正

1. Z-5 称"SW 元数据无法给出这 13 条的缺侧身份"。本轮证实，B 组的 5 条在 SW 中有完整器件记录（PARTNO/PARTLABEL/PARTTYPE），Z-5 的 SW 检索只看了 label 与 port，漏掉了 part_no。
2. Z-5 把 B 组归为"跨页裸 n 标记"（建议 B、L-12 S4 方向）。本轮证据不支持，应改为器件标注引线。
3. Z-5 给出的 52n 位置 (305.84,136.01) 是原始 insert，对齐点为 (308.09,137.51)（见第 2 节第 10 条）。
4. Z-5 未识别高度钳制（cad_extract.py:362），这是 B 组的直接根因。

## 6. 需要用户决定的事项

1. 是否确认 B 组 5 条为器件标注引线，并据此撤回 Z-5 第 3 条与 L-12 S4 中"跨页裸 n"的建议。
2. 是否同意 F1（保留原始高度、隐形文字不进端子候选）作为核心修复。该修复会改变 14 条单端 review、5 条双端 discard，以及 3 条 table_mapping pass（需先人工复核）。
3. PC0053 的未绑定器件头是否按 F3 处理，还是保持 review。

## 7. 限制

- 所有结论基于 DXF 缓存与 round12 产物，未对照原 DWG，也未在 CAD 中目视验证。
- PNG 由 ezdxf 绘制，文字布局为近似渲染（已按 halign/valign 修正锚点）；宽视图中的标签在 PC0053 处重叠较多，细节以 details.json 为准。
- PC0053 的"未绑定器件头"判断依据是 PART_HANDLE=0 与与 S0008 模板的同形性，不是 SW 绑定证据。
- 隐形数字钳制的全语料统计仅覆盖 round12 已审计的文字（3,945 条）；未审计页的影响未计入。

## 8. 文件

- `B1_p062_PC0019_S0012.png`、`B1_p062_PC0125_S0013.png`、`B1_p071_PC0053_S0011.png`、`B1_p075_PC0232_S0014.png`、`B1_p075_PC0440_S0015.png`：每条两个面板（宽视图 ±60×±40 单位、近景 ±16×±10 单位）；橙=线组，绿=已识别一侧，红 X=缺失端点，框色=图层，灰虚线框=器件块，*隐形*=DXF 高度 1e-05。
- `details.json`：每条的 pair、线组、空端几何、周边文字（含 dxf_anchor 与 engine_insert）、XDATA、SW 实例、结论与证据；另含引擎链路、修复建议、影响面数字。
- `tools/`：
  - `common.py`：公共路径与读取
  - `analyze.py`：收集证据（输出 `_facts.json`）
  - `render.py`：绘制 PNG
  - `build_details.py`：生成 details.json
  - `corpus_single_end.py`：单端 pair 全语料统计（输出 `single_end_corpus.csv`）
  - `scan_invisible_text.py`：流式扫描全部 DXF 的 TEXT 高度（约 25 秒；输出 `dxf_text_heights_all.csv`，已删除以节省空间，需要时重跑）
  - `invisible_join.py`：隐形数字与 round12 候选/pair 关联（输出 `invisible_numeric_joined.csv`）
  - `impact.py`：端口距离与隐形候选 pair 明细（输出 `hidden_numeral_accepted_pairs.csv`、`_impact.json`）
  - `probe_dxf.py`、`probe_area.py`、`engine_view.py`、`sw_consumers.py`、`xref_labels.py`、`dump_targets.py`：探查脚本
