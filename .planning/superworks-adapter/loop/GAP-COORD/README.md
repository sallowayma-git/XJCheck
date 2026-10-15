# GAP-COORD：R-RECOGNITION-GAP 协调闭合（GAP-TRIAGE 实施顺序 1–4）与呈现分层

分支 superworks-loop，基线 HEAD=2594dbe。未 commit、未 push。未改 V2 模块与 `symbol_port_proposal.py`，未加 PDF/OCR，判定无项目、句柄或取值特判。控制台 `PYTHONIOENCODING=utf-8`。

另一子代理在改 `superworks_extractor.py`、`superworks_semantics.py`，本切片未改这两个文件。回放快照 `.tmp/loop_gapcoord_src` 中这两个文件已从 HEAD 恢复。

## 0. 结论

1. **门禁（步骤 1–4）全部实现，只影响 issue 列表，不改 pairs、不改覆盖口径。** 被门禁移出的观察写入诊断产物 `sw_recognition_diagnostics.parquet`（带步骤名与闭合 pair），不丢弃。
2. **10 项目代理回放（冻结 2594dbe findings）：R-RECOGNITION-GAP issue 3103 → 1046（−2057，−66.3%）。** 观察 3949 → 2325：被门禁关闭 1630 条（基线已发射、现压掉）；旧版压掉、新版重新出现 6 条（均应保留，见 3.4）。
3. **逐步关闭数（基线已发射、现压掉，按门禁顺序）**：装置内部线级 1260、X 元件间导线 206、跨页延续 69、V1 物理线段 61、F1 自环 34。合计 1630。另有 479 条为既有“装置内部丢弃 pair 的线组”规则，本次未新增。
4. **抽样核对**：每步分层抽样 ≥10 例（共 66 例，17 张 DXF 渲染图 `png/GAPCOORD_01–17.png`）。目视判定 **60/60 关闭正确**（装置内部 12、跨页延续 12、物理线段 12、X 类 12、F1 12）；旧版压掉而新版重新出现的 6 条目视判定 **6/6 应保留为 issue**。误关闭形态已收紧（3.3）。
5. **呈现分层**：逐端子去重后 614 条端子 issue 覆盖 1098 个端子（每端子恰好属于一条 issue）；无脚号元件类按页汇总为 38 条页级 issue，覆盖 742 个端子；逐观察 issue 394 条。
6. **覆盖率**：未改 consumed、延续、装置内部覆盖的计算，覆盖各口径按构造不变（第 6 节）。
7. **需要主线程裁决**：X 类收紧规则的敏感度（3.5，闭合数 249–597）；F1 自环抑制（可能掩盖真正的重复身份错误，已保留在诊断产物中）。

## 1. 改动文件

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/audit/recognition_coordinator.py` | 新增 `GapFacts`、`GapResolution`、`resolve_recognition_gaps(observations, pairs, pages, existing, *, facts, steps)`（返回 issue、诊断行、统计）。`build_resolution_issues` 保留原签名，仅新增可选 `facts`、`steps`。门禁：`_gate`、`_gate_device_internal`、`_physical_v1_pair`、`_x_element_only`、`_self_loop`；呈现：`_page_summary_issue`、并查集端子去重。`CONFIRMED_CONFLICT` 永不被门禁关闭，也不进入页级汇总。 |
| `src/dwg_audit/audit/superworks_device_internal.py` | 只新增接口，不改现有函数：`wire_members_of_links(links, wire_mapping)`、`device_internal_wire_index(links)`、`on_device_internal_wire(index, file_id, port_id, handles)`。 |
| `src/dwg_audit/audit/issue_triage.py` | 页级汇总的分组键与标签（第 5 节）。 |
| `src/dwg_audit/report/superworks_artifacts.py` | 写出 `sw_resolution_observations.end_geometry`（元件间导线两端：SYMB2 termpoint、长度 ≥50 的线链；`_sheet_line_index`、`_reaches_long_line`、`_observation_end_geometry`）；写出 `sw_device_internal_links.wire_handles`（链接导线的全部句柄）。 |
| `src/dwg_audit/report/rerun.py` | 读取 `sw_port_coverage`、`sw_device_internal_links` 作为门禁事实（`_gap_facts`）；调用 `resolve_recognition_gaps`；写 `audit/sw_recognition_diagnostics.parquet` 与 `audit/sw_recognition_gate.json`（`_write_gap_diagnostics`），并登记到复制清单。 |
| `src/dwg_audit/report/artifacts.py` | `_FINDINGS_FRAME_NAMES` 增加 `sw_device_internal_links`（否则 rerun 读不到）。 |
| `tests/unit/test_gap_coordination.py` | 新增 14 项单测（第 7 节）。 |

## 2. 门禁规则（按顺序，首个命中即关闭）

对 INCOMPLETE/AMBIGUOUS 观察；CONFIRMED_CONFLICT 不参与门禁。

0. **既有规则**：同一线组上有装置内部丢弃的 pair → 关闭（`device_internal_pair`，479 条，本次未改）。
1. **装置内部线级（`device_internal`）**：所有端子侧（端子/装置端子）都满足：装置端子的 DEV-INT 线级链接所在导线（`wire_handles`）包含观察的 source handle。链接本身的成立条件不变（单根导线、恰好两端口、同标签内部元件/线圈/未登记块引脚；多端导线不算）。
2. **跨页延续（`continuity`）**：所有端子侧的端口都被延续关系覆盖（`sw_port_coverage.continuity_link_ids` 非空，即 `covers_target=True`）。与步骤 1 同一门禁，报告时单列。
3. **物理线段 V1（`physical_v1`，替代“同线组 ID”）**：存在非 discard V1 pair，其线组几何与观察线段共线（两端到直线距离 ≤0.8）且重叠 ≥80%，并且观察中每个有身份的一侧都被该 pair 的某一侧身份等价（生产规则 `_ends_equivalent`，双向一致；GND 按 G-1 视为同一身份）。观察两侧都无身份时不闭合。
4. **X 元件间导线（`x_element_only`）**：两侧都不是端子类（内部元件、线圈、接地、接插件或无端口）；两端均无 SYMB2 termpoint（1.5 单位内）；两端均未到达长度 ≥50 的线链（竖向或横向；首尾间隙 ≤12 的段合并成链；观察线段自身的 source handle 不计；端点到链的距离 ≤12 也算到达，即断线的另一侧也算）。
5. **F1 自环（`self_loop`）**：两侧都有 SW 端口，且身份相同（同一逻辑端子的两个触点，或两端子跨接）。

呈现（不是门禁）：端子去重（共享端子的观察合并为一条 issue，并查集）；无脚号元件类（一侧为有身份端子、另一侧为无身份内部元件/线圈）按页汇总。

## 3. 闭合数、抽样精度与误关闭收紧

### 3.1 逐步关闭数（10 项目）

| 步骤 | 门禁顺序闭合（含基线未发射） | 其中基线已发射、现压掉 | 说明 |
|---|---:|---:|---|
| 0 既有装置内部丢弃 pair | 479 | 0 | 旧规则已压掉，本次不变 |
| 1 装置内部线级 | 1313 | 1260 | 线级链接覆盖 |
| 1 跨页延续 | 69 | 69 | `covers_target` |
| 2 物理线段 V1 | 671 | 61 | 其余 610 条基线即被线组规则压掉，本次仍压掉 |
| 3 X 元件间导线 | 249 | 206 | 移入诊断 |
| 4 F1 自环 | 36 | 34 | 移入诊断 |
| **合计（基线已发射、现压掉）** | | **1630** | 3949 → 2325 |

### 3.2 抽样（DXF 渲染，`png/`，清单 `samples_manifest.json`，种子 20261015）

每步从“基线已发射、现压掉”的观察中分层抽样，每步 ≥10 例（装置内部按 SW 元件/未登记块 × PCL 佐证分层；延续按关系分层；物理线段按观察；X 按两端类别分层；F1 按观察）。图中蓝色为观察线段，绿为端子端口，橙为另一端端口，红叉为未登记引脚，灰为同页线，品红为 pair 线组（物理线段步骤）。

| 步骤 | 池大小 | 抽样 | 目视判定 | 说明 |
|---|---:|---:|---|---|
| 装置内部线级 | 1260 | 12 | 12/12 应关闭 | 端子接同标签的内部触点、线圈、继电器或未登记块引脚，图面可见元件 |
| 跨页延续 | 69 | 12 | 12/12 应关闭（11 明确，1 依 D 类口径） | 延续覆盖的是目标端子的导线，与 GAP-TRIAGE 的 D 类（5/5）一致；p001 GW0224 长导线的端子标注无法在截图内完全核对 |
| 物理线段 V1 | 61 | 12 | 12/12 应关闭 | V1 pair 沿同一导线，身份一致 |
| X 元件间导线 | 206 | 12 | 12/12 应关闭 | 仅元件之间或元件与接地/母线之间的导线，无端子符号；部分端点落在母线或接地上 |
| F1 自环 | 34 | 12 | 12/12 应关闭（F1 规则） | 同身份两个触点（跨接、一端子两触点）。真正的重复身份错误在图上也如此，因此只从 issue 移出，保留在诊断产物 |
| 旧版压掉、新版重现（R） | 6 | 6 | 6/6 应保留 | 见 3.4 |

判定为单人目视，未做双人复核。

### 3.3 误关闭形态与收紧记录

在抽样过程中发现并收紧的形态（均为“先误关闭、后收紧”）：

1. **虚线/断开的轨线被逐段判断**：端子排轨线或母线被端子、节点切成多段（每段 <50），逐段判断会把连到轨线的导线当作“无轨线”而关闭。改为首尾间隙 ≤12 的段合并成链后判断（12 覆盖虚线 10 单位的间隔）。
2. **断线**：观察线段在 11 单位处断开，另一侧是长度 ≥50 的竖线。改为端点到链的距离在 12 单位内也算“到达”。
3. **同线的真轨线被当作自身排除**：原先按几何重叠排除观察线段所在的线。改为只按观察的 source handle 排除被测线段本身。
4. **水平端子排未检查**：改为竖向与横向都检查。
5. **身份等价**：改用生产规则 `_ends_equivalent`（裸脚号 `327` 与 `1-4n327` 不等价，保留为 issue）。
6. **冲突被归入页级汇总**：修正，`CONFIRMED_CONFLICT` 永远逐条保留。

X 类闭合数随收紧的变化（10 项目，门禁顺序闭合数）：

| 版本 | 规则 | X 闭合数 | 10 项目 gap issue 总数 |
|---|---|---:|---:|
| a | 竖向逐段 ≥50（GAP-TRIAGE 原定义） | 597 | — |
| b | 竖向链，间隙 ≤8，同线按几何排除 | 582 | — |
| c | 竖向+横向链，间隙 ≤8，同线按几何排除 | 533 | — |
| d | 竖向+横向链，间隙 ≤8，按 source handle 排除 | 529 | — |
| e | 同 d，间隙 ≤12 | 432 | 882 |
| **f（当前）** | 同 e，加断线可达（端点到链 ≤12） | **249** | **1046** |

选择 f 是为了“误关闭必须收紧”。代价是 X 类 issue 增加。若主线程判断 f 过严，可在 `superworks_artifacts._reaches_long_line` 中去掉断线可达（改回 e）。

### 3.4 旧版压掉、新版重现的 6 条（均为保留）

| 项目/线组 | 观察两端身份 | 同线组 V1 pair | 原因 |
|---|---|---|---|
| p022 GW0234 | 端子 1QD7 / 无 | 13（review） | 身份不一致（1QD7 ≠ 13） |
| p026 GW0354 | 无 / 1-4n327 | 327（review） | 裸脚号 327 与 1-4n327 不等价（生产规则） |
| p026 GW0123、GW0372、GW0553、GW0588 | 两端都无身份 | 有身份（review） | 观察无身份，无从核对一致，保守保留 |

6 条都是 review 级 pair，几何重合（overlap=1.0），旧版以线组压掉，新版要求身份一致。

### 3.5 X 类规则的敏感度（需主线程裁决）

e 比 f 多闭合 183 条 X 观察，issue 约少 164 条（882 对 1046）。若认为 f 过严，选 e；若需要更保守，保留 f。

## 4. 剩余缺口分布（10 项目，门禁后仍发出的 2325 条观察）

| 类别（按两侧类别与身份） | 观察数 | 说明 |
|---|---:|---|
| 两侧都非端子（元件间导线） | 980 | X 规则未命中：端点到达长线链或有 termpoint，或缺少几何 |
| 端子 + 元件，元件引脚无身份 | 756 | 其中 610 条为页级汇总（无脚号元件类），146 条逐端子 |
| 端子 + 无类别或端子，一侧无身份 | 552 | 逐端子 |
| 端子 + 接地/接插件等其他 | 37 | 逐端子 |

按呈现：逐端子 issue 614（1098 端子）；页级汇总 38（742 端子，来自 610 条观察）；逐观察 issue 394。

GAP-TRIAGE 第 5–8 步（未实施）的 77 项目估算剩余量（来自 GAP-TRIAGE，未在本次回放中重算）：A 线级复核 1003；E_reg 引脚挂接 1456；E_unreg_pin 文字挂接 842；端子排轨线与母线 T 接 3139；无脚号元件 5982（本次已按页汇总）；人工逐条 1791。本次门禁之后这些类别的实际数量需由全量回放（每项目 `audit/sw_recognition_gate.json`）给出。

## 5. 呈现与前端（issue_triage）

- **逐端子 issue**（`evidence.presentation = "terminal"`）：`terminal_port_ids` 列出该组端子；观察合并在 `resolution_observations`。同一端子只属于一条 issue（并查集）。`review_group_id` 仍按图页分组（`review|R-RECOGNITION-GAP|sheet:<图页>`），与现有前端逻辑相同。
- **页级汇总**（`presentation = "page_summary"`）：`evidence.terminal_ports` 列出端口清单（`port_id`、`endpoint_identity`、`coords`、`sheet_id`、`file_id`），`terminal_count` 为端子数。分组为 `review|R-RECOGNITION-GAP|sheet:<图页>|unpinned_element`，标签为“须人工校验 · 图 NN · 无脚号元件连接（n 个端子）”。
- **逐观察 issue**（`presentation = "observation"`）：与原来相同。
- 前端（`desktop/state_store.py` 调用 `issue_triage`）读取的是 `review_group_id`、`review_group_label`、`handling_class`，本次未改前端代码。

## 6. 回放与对比

工具：`tools/gap_proxy_run.py`（代理回放）、`tools/compare_issues.py`、`tools/gap_coord_analysis.py`、`tools/gap_coord_render.py`、`tools/gap_coord_stats.py`。

- **代理的可信度**：HEAD 代码（`git archive HEAD src`）在冻结 findings 上重跑 report 阶段，10 项目的 R-RECOGNITION-GAP 为 3103 条、3949 条观察，与 baseline 完全一致；其他规则 0 差异（`compare_head_proxy_10proj.json`）。
- **新代码的代理回放**（`new` 模式）：先回填两个新列（用写出层自身函数基于 parquet 计算，见 `backfill`），再调用 `rerun_audit_from_findings`。其他规则 15 条与 baseline 逐条相同（added 0、removed 0；`compare_new_10proj.json`）。
- **pairs 不变**：门禁不写 pairs；代理回放中 pairs.parquet 原样使用。
- **覆盖率各口径不下降（按构造）**：`consumed`、`consumed_with_continuity`、装置内部覆盖的计算未改，`sw_port_coverage` 只新增读取。代理回放未重算 `sw_port_coverage`；主线程全量回放应以 `superworks_summary.json` 的 `coverage_views` 核对。
- **主线程回放**（未在本切片执行）：快照 `.tmp/loop_gapcoord_src`（HEAD 上的 extractor/semantics + 本切片改动）。命令：
  `python .planning/superworks-adapter/replay.py --output .tmp/loop_gapcoord --snapshot .tmp/loop_gapcoord_src --projects p001 p003 p022 p026 p044 p051 p061 p071 p074 p075`

## 7. 测试

- 新增 `tests/unit/test_gap_coordination.py`，14 项：装置内部线级（线内/线外、需全端子覆盖）、延续（逐端子覆盖）、物理线段 V1（同线、身份、离线、部分重叠、丢弃、GND）、X（端子、termpoint、轨线、缺失几何）、F1、冲突不被门禁关闭、页级汇总、端子去重、分流合并、诊断行、写出层轨线链（断开、自身排除、termpoint、水平轨线）、线级接口。
- 相关既有单测（`test_recognition_coordinator.py`、`test_issue_triage.py`、`test_superworks_device_internal*.py`、`test_superworks_cross_page_links.py`、`test_superworks_artifacts.py`、`test_rerun_*`、`test_report_artifacts.py`、`test_execution_service.py`、`test_superworks_loop_v06_dedupe.py`、`integration/test_extraction_gate_pipeline.py`）全部通过。
- 全量 `python -m pytest tests -q -p no:cacheprovider`（含 integration）：2235 passed，1 skipped，退出码 0（最终代码，工作区含另一子代理的未提交改动）。

## 8. 新图纸的泛化说明

- 门禁只读取元数据与几何：端子类别、装置标签、SW 线组句柄、链接的导线句柄、延续的 `covers_target`、V1 pair 的线组几何与身份、SYMB2 termpoint、线段几何。没有块名、项目、句柄或取值特判。
- 新图纸若缺少 SW 元数据（无装置内部链接、无延续、无 pair 几何），门禁对应步骤不关闭，结果保守。
- 几何阈值（0.8 重叠、0.8 共线、50 长度、12 合并间隙、1.5 termpoint、0.6 接触）以图纸单位计。新图纸的比例若与 DXF 语料不同，阈值需复核，尤其是 12 合并间隙与 50 长度。
- X 规则依赖“线链”识别。对只用块表达、没有线段的端子排无法识别；这种情形会保留为 issue（保守）。

## 9. 限制

- 代理回放基于冻结的 2594dbe findings（未重新抽取）；主线程全量回放应确认结果。
- 抽样判定为单人目视，每步 ≥10 例，未做双人复核。
- X 规则是几何启发式，敏感度见 3.5。
- F1 自环可能掩盖真正的重复身份错误（已保留在诊断产物，可人工复查）。
- 步骤 5–8 未实施（第 4 节为估算）。
- 写出层对装置内部链接多一次 `split_terminal_wires` 计算，未测量耗时。

## 10. 文件

| 路径 | 内容 |
|---|---|
| `README.md` | 本文档 |
| `details.json` | 第 3–4 节的统计（`tools/gap_coord_stats.py`） |
| `summary_observations.json`、`old_new_matrix.csv` | 观察级的旧/新状态矩阵 |
| `samples_manifest.json` | 66 例抽样清单（步骤、项目、记录、PNG） |
| `compare_new_10proj.json`、`compare_head_proxy_10proj.json` | 逐项目对比 |
| `png/GAPCOORD_01–17.png` | 抽样渲染（每张 4 例，末张 2 例，共 17 张） |
| `tools/` | 代理回放、对比、分析、渲染、统计脚本 |
| `.tmp/loop_gapcoord_work/new/`、`.tmp/loop_gapcoord_analysis/` | 代理回放输出与中间表（不入库） |
