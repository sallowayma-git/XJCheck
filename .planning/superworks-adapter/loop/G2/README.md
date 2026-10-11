# G2：空断口处拆分被错误合并的线组

分支 superworks-loop，基于 HEAD 556e999。未 commit、未 push。未改 V2 模块与 `symbol_port_proposal.py`，未加 PDF/OCR，未加开关，无按项目/句柄/取值的特判，未整体豁免 SuperWORKS 来源。

## 0. 结论

1. 判据已实现、可单元测试、端到端生效，但**在 77 个项目的语料里几乎不触发**：merged 间隙 5812 个中，满足“两侧为不同端口、无文字覆盖、无圆点”的只有 1 个（p039 S0012），且该例拆分正确（两根不同导线）。
2. 10 个项目回放：线组、配对、issue、四口径覆盖**全部无变化**。
3. GAP-2 报告的 1604 个“空断口”端口估计**不能复现为线组层面的空断口**。原因是 GAP 的文字判据只看插入点窗口；按文字实际覆盖断口（bbox）判定，2326 个“无插入点文字”的候选中有 2325 个被线号标注压在导线上（即文字断口，合并正确）。改按 GAP 的插入点判据拆分会误拆这些标注打断的导线，违反“只减少误报”，因此未采用。
4. 建议：不要把 GAP-2 当作独立的线组拆分收益项计入覆盖预估；GAP-2 的未覆盖端口需要另找根因（见 §7）。

## 1. 判据与改动

**位置**：`src/dwg_audit/audit/line_groups.py::_can_merge_axis_intervals`，仅在 `0 < gap <= gap_tol`（4.0）分支生效（原分支 `return True`）。水平、竖向、grid 三种路径共用。

**判据**（同时满足才拆分，即 `_can_merge_axis_intervals` 返回 False）：
- 间隙两端的端点（沿轴位置、横向为两线段的平均横坐标）各自落在某个 SuperWORKS 端口的标记线段上（点到线段距离 ≤ 1.0），且两端命中的端口**不是同一个**（一个端口横跨整段间隙时视为一根导线穿过一个端子，保持合并）。
- 间隙内无文字：任何非空文字的 bbox 与间隙（两端各外扩 0.6）在轴向相交，且横向与线段横坐标相距 ≤ 4.0。
- 间隙内无 SW 连接圆点（LD_CONNECT_DOT 中心，轴向外扩 0.6，横向 ≤ 4.0）。

其余情况（文字断口、圆点、零间隙、单侧无端口、单端口跨越、大间隙、无 SW 证据）保持原行为。

**端口来源（线组构建阶段拿不到端口时的处理）**：SW 数据在 `_extract_pairs_for_route` 调用线组构建之前已经产生（`pipeline.py` 中的 `superworks` 对象）。新增可选参数 `wire_break_evidence: dict[sheet_id, WireBreakEvidence]`，由 `wire_break_evidence_by_sheet(superworks.ports, superworks.connect_dots)` 按页分组构成；经 `page_extractors.py` 的 4 个公开 `extract_*_pairs` 与 `_extract_pairs_for_route` 传入 `build_line_groups`。默认 None，既有调用方与测试不受影响。

**改动文件**（工作区相对 HEAD）：
- `src/dwg_audit/audit/line_groups.py`（新增数据类、分组函数与判据辅助函数，约 177 行）
- `src/dwg_audit/audit/page_extractors.py`（参数透传，11 行）
- `src/dwg_audit/pipeline.py`（构建证据并传入各路由，8 行）
- `tests/unit/test_line_groups_empty_gap_split.py`（新文件，12 项）

## 2. 单元测试

`tests/unit/test_line_groups_empty_gap_split.py`，12 项：空断口两侧不同端口→拆分；文字断口→合并；圆点→合并；一侧无端口→合并；单端口跨越→合并；无 SW 证据→合并；另一页证据不影响→合并；间隙 > 4 保持拆分（旧行为）；端点接触→合并；竖向线组→拆分；grid 行带→拆分；证据按页分组。

既有 `tests/unit/test_line_groups.py` 16 项全部通过。

**全量 pytest**（隔离副本：HEAD 的 tests 与 pyproject，src 分别为 HEAD 与 G2 快照，因为 pyproject 的 `pythonpath=["src"]` 会优先使用工作区 src）：

| 版本 | 通过 | 失败 |
|---|---|---|
| HEAD 基线 | 1979 | 21 |
| G2 快照 | 1991（+12 新测试） | 21 |

两侧失败集合完全相同（经 diff 核对）：`test_analyze_project` 1、`test_cli` 2、`test_config` 5、`test_desktop_packaging` 9、`test_superworks_semantics` 3、`test_symbol_library_review` 1，均为 HEAD 既有失败，与本切片无关。注意：全量 pytest 运行于 rename 之前的快照；之后仅做了命名与类型注解整理（行为不变），重跑了线组测试（28 项通过）。

## 3. 10 项目回放对比（round19 基线 vs G2 快照）

回放：`replay.py --snapshot .tmp/loop_g2_src --projects p001 p003 p022 p044 p050 p051 p061 p071 p075 p076`，输出 `.tmp/loop_g2_final`（清理后的快照）。对比脚本 `tools/g2_compare.py`（只读，输出到 `.tmp/loop_g2_compare_final`）。配对按内容键比较（pair_id 为顺序计数器，线组变化会整体偏移）。

| 项目 | 线组 前→后 | 配对 前→后 | 新增/删除配对 | issue 前→后 | 新增/删除 issue |
|---|---|---|---|---|---|
| p001 | 1092→1092 | 984→984 | 0/0 | 0→0 | 0/0 |
| p003 | 646→646 | 455→455 | 0/0 | 0→0 | 0/0 |
| p022 | 1221→1221 | 1275→1275 | 0/0 | 1→1 | 0/0 |
| p044 | 2058→2058 | 2292→2292 | 0/0 | 1→1 | 0/0 |
| p050 | 1743→1743 | 1917→1917 | 0/0 | 1→1 | 0/0 |
| p051 | 621→621 | 373→373 | 0/0 | 0→0 | 0/0 |
| p061 | 3136→3136 | 3401→3401 | 0/0 | 0→0 | 0/0 |
| p071 | 425→425 | 293→293 | 0/0 | 3→3 | 0/0 |
| p075 | 1384→1384 | 1873→1873 | 0/0 | 4→4 | 0/0 |
| p076 | 2050→2050 | 2253→2253 | 0/0 | 0→0 | 0/0 |

- 线组：成员集合级对比，仅前有 0、仅后有 0。
- 状态变化：0。
- 四口径覆盖（strict / with_continuity / with_internal / total，consumed）：10 项目逐项前后完全相同（如 p001 为 447/488/544/567，p044 为 860/860/993/993）。
- R-ONE-TO-MANY / R-MANY-TO-ONE / R-DUPLICATE-PAIR：前后计数不变（本批次中 R-MANY-TO-ONE、R-ONE-TO-MANY、R-DUPLICATE-PAIR 均为 0 或未出现；输出的规则计数仅含 R-SUPERWORKS-CONFLICT 4、R-PAIR-MISSING-SIDE 1、R-CROSS-PAGE-CONFLICT 1、R-PAIR-LOW-CONFIDENCE 4，前后相同）。
- 同排短接（bridge_mapping）与新配对重复：不适用，无新增配对。

**新增 issue 逐条判定**：无（0 条新增，0 条删除）。
**新增 pass 配对抽样（≥20 例）**：不适用，无新增配对。

## 4. 端到端：唯一触发的一例（p039，不在 10 项目内）

`tools/g2_trace.py p039` 在快照上回放，包装 `_is_terminal_wire_break` 记录触发。触发 1 次：S0012，水平，间隙 347.5–350.0，y=240。

- 两端分别是导线 25920（止于 347.5）与 2591B（起于 350.0），两根不同的导线（图层 CONNECT，句柄不同）；端口 1（347–348）接 25920，端口 2（349.5–350.5）接 2591B，中间端口 3（348.25–349.25）无接触。`png/G2_only_empty_candidate_p039.png` 为该例。判定：**真实的两根导线，拆分正确**。
- 结果：线组 2554→2553（旧合并组消失，两段的成员集合在 SW 辅助线组中已存在，因此新增成员集合 0）；配对 2392→2392、issue 2→2、四口径 1083/1224/1318/1347 不变。

全量 77 项目的候选数（见 §6）为 1，因此全部语料中该判据触发仅此一次。

## 5. 抽样与截图

- `png/G2_label_covered_gaps.png`：4 例“插入点窗口判定为空、bbox 判定为文字覆盖”的断口（p000 S0004 y195 标注 1507；p014 S0006 y237.5 标注 114；p000 S0007 y255 标注 431；p014 S0007 y70 标注 2320）。导线（蓝）在标注框下方连续，标注压在导线上，属于文字断口，保持合并。
- `png/G2_only_empty_candidate_p039.png`：唯一触发例（§4）。

截图为单人判定，标注“导线压在标注下”的目视依据为图中蓝线穿过标注框、两端端口位于框内。

## 6. 缺口统计：GAP-2 估计为何不能复现

`tools/g2_gap_probe.py`（只读，round19 线组输出，77 项目）。统计全部 0.6 < gap ≤ 4 的已合并间隙：

| 指标 | 数量 |
|---|---|
| 已合并间隙总数 | 5812（grid 行带 5463，水平 349） |
| 两端各有端口（任一端口，允许同一端口） | 5618 |
| 两端各有端口 且 无文字（bbox） 且 无圆点 | 1 |
| 同上，且两端为不同端口 | 1（p039，§4） |
| 两端有端口 且 无文字（插入点窗口，GAP-2 判据） 且 无圆点 | 2326 |
| 其中 bbox 判据下仍有文字覆盖间隙 | 2325 |

GAP-2 报告的 1604 端口（前版估计）来自这类插入点窗口统计。插入点窗口只看文字插入点是否落在间隙内；线号标注（如 `1507`、`114`）的插入点常在间隙起点之外一点，而文字框覆盖整个间隙，导线由标注打断。按插入点判据会把 2325 个标注打断的合并拆开，属于误报，违背“只减少误报”的要求，因此没有采用。

与 GAP 报告的一致性：GAP 目视 G2E 空断口 9 例与文字断口 13 例中，文字断口为标注打断（合并正确，与本报告一致）；空断口样本是按插入点判据选出的，本报告的 bbox 判据对其中多数给出“文字覆盖”，因此 GAP-2 的“空断口”类别应重新界定。

## 7. 耗时

**顺序回放（workers=1），8 项目（p001 p003 p022 p044 p050 p051 p071 p075），HEAD 与 G2 交替、各两轮**：

| 轮次 | HEAD 基线 | G2 快照 | 增量 |
|---|---|---|---|
| 1 | 137.64 s | 148.10 s | +7.6% |
| 2 | 141.69 s | 137.02 s | −3.3% |
| 平均 | 139.67 s | 142.56 s | +2.07% |

两轮方向相反，单项目噪声约 ±10%，整体墙钟差值不可分辨。

**直接计量新增代码开销**（`tools/g2_trace.py` 包装 `_is_terminal_wire_break` 计时）：8 项目合计调用 278 次，累计 0.055 s，占 8 项目总耗时（约 138 s）的 0.04%，远低于 2% 上限。判据仅在 0 < gap ≤ 4 且两端有 SW 端口时进入耗时路径，多数调用在端口检查即返回。

## 8. 快照与工作区状态

- 回放快照 `.tmp/loop_g2_src`：由 `git archive HEAD src` 构建，再覆盖我的三个文件（line_groups.py、page_extractors.py、pipeline.py）。不含 G1P 的未提交改动。快照与当前工作区 `line_groups.py` 一致（已同步 rename）。
- 快照构建时（我的改动已写入之后）工作区 `git diff --stat -- src` 为：line_groups.py +177、page_extractors.py +11、pipeline.py +8，另有 G1P 的未提交改动 `superworks_device_internal.py` 165、`superworks_semantics.py` 40、`report/superworks_artifacts.py` 27。这三个 G1P 文件未进入我的快照。
- 我的 round19 基线：`.tmp/superworks_round19_full`，其 `code_manifest` 与 HEAD 的 src 逐文件（换行归一化后）一致，可作为 HEAD 基线。

## 9. 遗留风险与建议

1. **G2 收益预估作废**：1604 端口估计依赖插入点判据，不应计入覆盖预估（已发现 2325/2326 为标注打断）。建议 GAP-2 在覆盖路线图中移除或改为另立根因调查。
2. 几何圆点：线组输入无圆点图元，判据仅用 SW 的 LD_CONNECT_DOT。非 SW 圆点落在空断口处会被漏判（但该场景只出现在 SW 项目中，且语料中触发本就仅 1 次）。
3. 端口距离阈值 1.0 使用端口标记线段而非 SW 的接触容差（0.6×标记长度）。语料中 1714 个接触点与线端点距离均为 0.0，两种定义在实际数据上一致。
4. 判据依赖 SW 端口，只对 SW 项目生效；非 SW 页面行为完全不变。
5. 目视与文字覆盖判定为单人判断；“文字压在导线上”以 bbox 与线段相交为准，可能偏保守（保持合并）。
6. 本切片不改变任何 pair/issue/覆盖结果，全量回放由主线程合并后统一执行时，结果预期与 round19 相同（在 10 项目与 p039 上已验证）。

## 附：文件

- 代码：`src/dwg_audit/audit/line_groups.py`、`src/dwg_audit/audit/page_extractors.py`、`src/dwg_audit/pipeline.py`
- 测试：`tests/unit/test_line_groups_empty_gap_split.py`
- 工具：`tools/g2_compare.py`（10 项目对比，只读）、`tools/g2_trace.py`（单项目端到端与计时）、`tools/g2_gap_probe.py`（缺口统计）、`tools/g2_render.py`（截图）
- 图：`png/G2_label_covered_gaps.png`、`png/G2_only_empty_candidate_p039.png`
- 临时：`.tmp/loop_g2_src`（快照）、`.tmp/loop_g2_final`、`.tmp/loop_g2_compare_final`、`.tmp/loop_g2_time`、`.tmp/loop_g2_cost`、`.tmp/loop_g2_scratch`（均可删）
