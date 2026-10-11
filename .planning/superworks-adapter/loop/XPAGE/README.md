# XPAGE：端子排跨页去向（X2）的连接建模与覆盖

分支 superworks-loop，基线 HEAD=bae326f。未 commit、未 push；未改 V2 模块与 `symbol_port_proposal.py`；未加 PDF/OCR；无项目、句柄、数值特判；未整体豁免 SuperWORKS 来源。

## 0. 结论摘要

1. **语义**：端子排行的跨页去向（`未定义<句柄>:<端口>_<页号> <页名>`）是一根导线的**另一端**。该导线在端子排页上已经被一条非 discard 配对记录（行身份 ↔ 去向身份，或行身份与行连接文字相同）。目标端口是同一根导线在另一页上的端点，不是另一条导线，也不是同一个物理端子的第二次绘制。
2. **建模**：不新增 SW 配对。新增“跨页延续关系”（continuity link），由独立模块 `src/dwg_audit/audit/superworks_cross_page.py` 产生，只在覆盖口径中计为“被消费”。原因：为同一连接再建一条配对会得到重复记录（同一导线两页各一条），这正是 F3 要求避免的情况，也会触发 `R-CROSS-PAGE-CONFLICT`（见 §2.4）。
3. **覆盖**：严格口径（仅配对）保持不变；新增“含延续关系”口径。10 项目：64.6% → 73.6%（+785 端口）；全量 77 项目：57.7% → 67.2%（+7854 端口）。
4. **问题数**：10 项目与全量的 `pairs.parquet`、`issues.json` 与 round16 逐条一致（增减均为 0）。本次改动不改变任何 issue。
5. **真实矛盾候选**：全量 2006 条（“目标已被另一根导线消费，且另一端不是本行身份或行连接的远端”）。抽样 10 例，目视 9 例像真实图纸不一致，1 例是范围写法误判（`U3D7~8`）。样本只有 10 例，达不到用户要求的 95% 精度，因此只报告，不新增 issue 规则。

## 1. 语义（10 例截图）

图位于 `png/`，每张拼图 4 个样例，左侧为端子排页（红），右侧为目标页（蓝）。

| 分类 | 图 | 目视结论 |
|---|---|---|
| 连接远端命中且目标空闲（continuity_conn，覆盖） | `covers_conn_1.png`、`covers_conn_2.png`（已目视 8 例；`covers_conn_3.png` 含 2 例未目视） | 端子排行的连接文字（如 `3-21n320`、`1-21n228`）与目标页上带同名标注的装置端子是同一根导线的两端。目标端子旁的导线就是端子排那根导线到达的地方。 |
| 行身份与目标同名（continuity_row，覆盖） | `covers_row_1.png`、`covers_row_2.png`、`covers_row_3.png`（共 10 例） | 同一线号在两页各标一次（如 `1QD30`、`4-21GD19`、`JD9`），目标页上的同名端子有导线接入。端子排行的内部连接与这根导线是同一根线的两端。 |
| 目标已被配对，另一端与本行一致（已覆盖） | `consumed_agrees_*.png` | 目标在目标页已有配对，另一端与本行或远端文字一致，不增加覆盖。 |
| 矛盾候选 | `contradiction_candidate_1..3.png`（10 例） | 见 §4。 |

关于“48% 身份相同”（COV-GAP X2 原记录）：身份相同时，两端是同一线号在两页上的两个端点（不同器件的引脚，或不同端子排上的同名端子），而不是“同一物理端口的两种画法”。“同名位置分开合法”的用户口径与此一致。

**对 COV-GAP 的更正**：COV-GAP B2 的第一例（`p035` 行 5LD19，去向 `1AE4D:1_13`）目标被写成 S0012（页 12）的 `5n421`。按页号 13 解析，目标是 S0013 的 `1AE4D:1`，身份为 `5n414`，与该行的连接文字 `5n414` 相同。COV-GAP 的目标选择忽略了页号；同一句柄 `1AE4D` 在页 12 与页 13 两个图中都存在（副本图纸复用句柄）。因此 COV-GAP 的“身份不一致”样例有一部分是错误的目标。

## 2. 建模

### 2.1 规则（`superworks_cross_page.py`）

- 目标解析：去向文字的页号（前导数字）必须与项目内唯一一张页的 `sheet_no` 相同，且该页上存在 `(句柄, 端口)`。只在别的页上存在该句柄的引用，判为陈旧引用，不连接（计数 `handle_on_other_page`）。
- 目标必须是 `端子` 或 `装置端子`，有身份，否则跳过。
- 行必须在一条连接文字上有非 discard 配对，否则跳过（计数 `row_has_no_strip_pair`）。
- 关系：
  - `continuity_conn`：目标身份 ∈ 行的远端值（连接文字，或该连接配对的另一端）。
  - `continuity_row`：目标身份 = 行身份。
  - 其余为 `differs`：只进入候选，不进入覆盖。
- 覆盖：目标在非 discard 配对中**未被消费**且有导线接触，则记为覆盖（`covers_target`）。同一目标被两条以上不同行声明时不覆盖（`multi_claim_not_covered`）。
- 比较使用 casefold 精确相等，不做前缀或数值推断。

### 2.2 产出

- `sw_cross_page_links.parquet`：每条解析成功的引用一行（关系、行、目标、远端值、支撑配对、覆盖标志）。
- `sw_cross_page_candidates.parquet`：`contradiction_candidate`、`identity_mismatch_unconsumed`。
- `sw_port_coverage.parquet` 新增两列：`continuity_link_ids`、`consumed_with_continuity`。`consumed` 不变。
- `superworks_summary.json` 新增 `port_coverage_with_continuity` 与 `cross_page`（统计与候选计数）。

### 2.3 改动文件

- 新增 `src/dwg_audit/audit/superworks_cross_page.py`：纯函数 `build_cross_page_links`。
- 修改 `src/dwg_audit/report/superworks_artifacts.py`：`write_superworks_artifacts` 中计算延续关系、写两张新表、新增两列与摘要字段；辅助函数 `_cross_page_continuity`、`_write_cross_page_tables`、`_continuity_coverage`。
- 新增 `tests/unit/test_superworks_cross_page_links.py`（15 项）。
- 未改动：`superworks_extractor.py`、`rules.py`、`superworks_semantics.py`、V2 模块、`symbol_port_proposal.py`。

### 2.4 为什么不建 SW 配对

- 每条有支撑的延续关系，其两端在端子排页上已有配对（远端文字即配对的另一端）。再建一条配对会得到同一连接的第二条记录。
- 按 `rules.py` 的读法（未执行，只据代码推断）：`_run_cross_page_conflict`（约 960–1060 行）按左值分组，同一左值在两页映射到不同右值即报 `R-CROSS-PAGE-CONFLICT`。例如行 `1QD30` 已配对到 `1KLP24-1`，再加一条 `1QD30 ↔ 1QD30` 的配对，右值集合变为两个，会触发该规则，除非逐条豁免。`R-DUPLICATE-PAIR`（约 1880 行）对完全相同的配对同样敏感。
- 因此把延续关系放在配对表之外，规则与 issue 不变，误报为零。代价是：问题发现不增加。这一点由矛盾候选的单独统计弥补（§4）。

## 3. 覆盖（严格口径与含延续口径）

口径定义：`eligible` = 端子/装置端子、有导线接触、标签已解析（与 `superworks_artifacts` 一致）。`consumed` = 非 discard 配对引用该端口，且 SW 侧值与配对侧值 casefold 相等。`consumed_with_continuity` = `consumed` 或（eligible 且被延续关系覆盖）。

`tools/coverage_strict.py` 从原始表独立重算，结果与产出的 `superworks_summary.json` 一致。

| 范围 | eligible | 仅配对（原口径） | 含延续 | 新增 |
|---|---|---|---|---|
| 10 项目（p001 p003 p022 p044 p050 p051 p061 p071 p075 p076） | 8645 | 5581（64.6%） | 6366（73.6%） | +785 |
| 全量 77 项目 | 82680 | 47692（57.7%） | 55546（67.2%） | +7854 |

- 原口径数字在 round16 与 round17 中完全相同（同一 eligible 与 consumed）。
- COV-GAP 报告的 57.3%（round12）与本表的 57.7%（round16/17 同口径）是不同回放轮次的结果，不直接比较。
- 全量 `pairs.parquet` 167726 条，round16 与 round17 逐条一致；`issues.json` 41 条，逐条一致。

## 4. 真实矛盾候选

定义：目标已被非 discard 配对消费，且该配对的另一端既不是行身份，也不是行远端值（`contradiction_candidate`）。目标空闲且身份与行远端值都不符，记为 `identity_mismatch_unconsumed`（弱候选）。

| 范围 | contradiction_candidate | identity_mismatch_unconsumed |
|---|---|---|
| 10 项目 | 123 | 148 |
| 全量 | 2006 | 1632 |

抽样（10 项目，`png/contradiction_candidate_1..3.png`，目视判定）：

| 行 → 目标端口 | 判定 |
|---|---|
| `7UD18` → `1UD4`（目标 1UD4 接 1n1522；7UD17 也指向同一目标） | 像真实不一致 |
| `JD32` → `JD34`（目标接 1-57npe2） | 像真实不一致 |
| `1ID6` → `1ID7`（目标接 1n1506，而 1n1506 正是同一端子排的第 7 行；1ID5、1ID8 也指向 1ID7） | 像真实不一致（多行声明同一目标） |
| `1I3D22` → `1n912`（目标接 1I3D23） | 像真实不一致 |
| `YD2` → `YD7`（目标接 yd6） | 像真实不一致 |
| `JD3` → `JD1`（目标接 jd2） | 像真实不一致 |
| `8QD2` → `8QD1`（目标接 8n112） | 像真实不一致 |
| `JD3` → `JD1`（另一项目） | 像真实不一致 |
| `JD36` → `JD34`（行远端文字为 `gnd`，却指向 JD34） | 像真实不一致 |
| `1U3D4` → `U3D7~8` | **误判**：范围写法 `U3D7~8` 包含 `U3D7`，属于命名形式差异 |

精度估计：约 9/10，样本量过小，不足以启用为 issue 规则（要求 ≥95%）。`identity_mismatch_unconsumed` 的 1632 条未做目视抽样。

## 5. 陈旧页号引用（图纸层面的线索）

- 10 项目：313 条引用的页号上没有该句柄，但别的页上有（占 2780 条的 11%）。其中 210 条按页名匹配到的目标身份与行一致，103 条不一致。
- 全量：1165 条（占 22736 条的 5%）。
- 例：`p044` 的 `F0023` 行 `ZD1` 指向“07 电源回路图”，但该页名对应的图是 `08 电源回路图.dwg`（页 8），句柄存在于页 8。图纸的页号标注疑似错误。
- 本次没有实现按页名的回退匹配（它会把页号判断换成页名判断，超出本切片范围）。这部分记为图纸层面的候选，留给后续决定。

## 6. 测试与回放

- 单元测试：`python -m pytest tests/unit -q` → 1929 passed, 1 skipped（含新增 15 项）。
- 10 项目回放：`.tmp/loop_xpage`（快照 `.tmp/loop_xpage_src`）。`compare_runs.py` 逐项目对比：pairs 与 issues 均无增减。
- 全量回放：`.tmp/superworks_round17_full`（快照 `.planning/superworks-adapter/round17_full_src`），77 项目全部 COMPLETE。全量对比见 `png/compare_full.json`；覆盖见 `png/coverage_full_*.json`。
- 新增关系抽样：10 项目的 `covers_conn` 与 `covers_row` 各抽 10 例，共 20 例。其中 16 例已目视（`covers_conn_1`、`covers_conn_2`、`covers_row_1`、`covers_row_2` 四张拼图），全部与 §1 的判定一致；剩余 4 例（`covers_conn_3`、`covers_row_3`）未目视，图已生成在 `png/` 中，待复核。

## 7. 遗留风险

1. **只读覆盖，不增加问题**：延续关系不进入规则。问题发现率的提升只能通过矛盾候选的人工或后续规则完成。
2. **continuity_row 依赖同名相等**：同名端子在两页出现时，可能误覆盖无关的端口。当前要求：显式引用（句柄+端口+页号）、行有支撑配对、目标有导线接触。20 例抽样未见误覆盖，但没有对全量做目视。
3. **多行声明同一目标**（全量 23 个端口）：不覆盖，也不成为候选，需要单独看。
4. **陈旧页号（§5）**：有 1165 条全量引用未连接。若图纸标注确有错误，这些是潜在的真实问题，目前未报告为 issue。
5. **`identity_mismatch_unconsumed`（1632 条）未目视**。
6. **COV-GAP 工具未直接复用**：其 `cov_gap.py` 依赖会话 scratchpad 中的中间 pickle，无法在仓库内重跑。本次用 `tools/coverage_strict.py` 按原始表重算严格口径，并与生产摘要核对一致。

## 8. 文件

- `png/`：`covers_conn_*.png`、`covers_row_*.png`、`consumed_*.png`、`contradiction_candidate_*.png`、`identity_mismatch_unconsumed_*.png`（拼图），`index.json`（10 项目样例索引），`study_10proj.json`、`study_full.json`、`compare_10proj.json`、`compare_full.json`、`coverage_full_*.json`。
- `tools/`：
  - `xpage_io.py`：读取一个项目的 findings（输入表）。
  - `xpage_study.py`：运行生产模块、统计、抽样渲染。
  - `shot_render.py`：端子排页与目标页的双面板渲染（复用 round4 绘图函数，只读导入）。
  - `compare_runs.py`：两轮回放逐项目对比（pairs、issues、覆盖）。
  - `coverage_strict.py`：严格口径与含延续口径的独立重算。
- 复现：
  - `python tools/xpage_study.py .tmp/superworks_round17_full .tmp/loop_xpage_full_study`
  - `python tools/compare_runs.py .tmp/superworks_round16_full .tmp/superworks_round17_full --json <out>`
  - `python tools/coverage_strict.py .tmp/superworks_round17_full --json <out>`

## 主线程复核（2026-10-11）
§4 的矛盾候选判定**不成立**。在 `contradiction_candidate_1.png` 中，端子排上的黄色圆点是短接片（连接点），把相邻行连在一起：7UD17–18、JD32–34、1ID5–8 都属于这种情况。同一短接组里，任一成员的跨页引用都可以指向组内另一成员在原理图上的端口。因此，「行 → 目标的另一端不等于本行」大多只是短接组内部的路由，不是图纸矛盾。9/10 的精度估计作废。下一步（XPAGE-2）：先按短接组（端子排短接片、bridge 和 series）把等价成员合并，再判定矛盾，并扩大抽样。
覆盖口径（含延续）本身成立：延续关系只在目标身份与行远端值或行身份精确相等时才建立。
