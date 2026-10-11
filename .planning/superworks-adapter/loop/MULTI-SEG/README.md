# MULTI-SEG：多段线组（870 个被拒切候选）的性质、连接方法与离线模拟

分支 superworks-loop，基线 HEAD=3e3b2b6。只读研究：未修改 `src/`、`tests/`，未 git。数据为 `.tmp/superworks_round21_full`（77 项目），装置内部模块取 `.tmp/multiseg_src/superworks_device_internal_ref.py`（与 `src` 当前版本相同的副本，避免与并行子代理的改动相互干扰）。`.tmp/superworks_round22_full` 与 `.tmp/superworks_round21_full` 均未删除或写入。

## 0. 结论

1. **870 个候选的性质**：每个候选都是一个装置端子的两个 TERMPOINT（同 insert、同标识、间距 2.5），而这两个 TERMPOINT 的接触点落在同一线组的两侧。线组因此由 3 或 4 段（端点连通分量，即本文“段”）拼成。**端子本体两侧被合并**这一判断（GAP2-PAIR）成立，本体是真实的装置端子，间距 2.5 与两个 TERMPOINT 的几何一致。
2. **但线组另外几个间隙通常不是导线**：870 个候选中，本体之外还有 935 个非本体间隙，其中 668 个是“未登记两引脚符号”（SYMB2 块，两端各有一个 TERMPOINT，正好跨越间隙，宽 10），137 个是 SuperWORKS 内部元件或触点，118 个是另一装置端子的本体，12 个是穿过间隙的绘制线（框线或模块框）。没有任何间隙只由文字或圆点构成。因此这些线组里的“多段”不是一根导线，而是**本体与元件串联**的结果。线号标注断口的假设（G2）对这 870 个候选不成立。
3. **正确拓扑（典型）**：`左端对象 — 导线 — 端口a | 本体 | 端口b — 导线 — [两引脚符号 或 触点] — 导线 — 外部端子`。端口 a 与端口 b 是同一端子，电气上经本体贯通；两引脚符号或触点把导线断开，两侧不是同一网络。
4. **推荐方法（M2）**：按间隙类型切开（本体、两引脚符号跨越、内部元件/装置端子两端跨越、穿越线），只让纯文字间隙、圆点间隙与空的小间隙保持合并；本体切分不限段数。离线模拟（77 项目）：装置内部链接由生产的 18646 增至 **19276（+630，丢失 0）**，其中 295 为内部元件、335 为未登记引脚；外部候选中 **112 条“双端未配对”的生产候选被移除**（均在 10–11.3 宽的元件间隙处被切开；抽 4 例目视确认为经元件的误连，其余未逐例核对），新增双端口候选仅 16 条。
5. **不推荐 M1**（只做本体切分、不切元件间隙）：它新增 796 条双端口外部候选，其中约 780 条实际穿过两引脚元件，是假配对。
6. **未知形态**：M2 之后仍有 1091 / 1740 个端口未解决（占 870 候选端口的 63%），主要是“空白端”（绘制而无 SW 标记的触点）、多端节点（一根导线接 3 个以上 SW 端口，3716 个 wire 键）和单端导线（引脚指向未登记符号但标签不符）。这些应以 `unknown_topology` 原因码列出，不静默合并。

## 1. 范围与口径

- 候选：`split_terminal_wires` 中 `reason == components_not_two` 的 870 个候选（已复现：5630 候选，最终版 4748 接受 / 870 `components_not_two` / 3 `gap_crossed` / 9 `body_too_narrow`；round21 中 870 与 3 与此一致，9 个 1.25 宽候选当时被接受，最终版改为拒绝）。
- 866 个不同线组，845 个为 `grid` 方向（行带聚类），25 个为 `horizontal`。grid 线组由 `_build_grid_row_bands` 在同一行带内做共线合并，合并规则与水平模式相同（`_can_merge_axis_intervals`，间隙 ≤ 4.0，或行内数字文字桥接，信号/告警页最宽 20.0）。这是 870 个候选的主要来源。
- “段”：端点连通分量（与生产 `_end_point_components` 一致），3 段 809、4 段 61；原始 LINE/LWPOLYLINE 数为 3（802）、4（23）、5（4）、6（41）。GAP2-S README 中的“线组段数 3/4”实为连通分量数，此处更正。
- 几何与元数据：TERMPOINT（`start_x…end_y`、category、insert_handle、endpoint_identity）、`wire_contacts`、未登记 SYMB2 的 TERMPOINT 对（`sw_unregistered_symb2`）、连接圆点（`sw_connect_dots`）、文字（`texts`）、模型空间线（`lines`，排除块内线）。块名仅用于目视标注，不参与任何判据。

## 2. 分类计数（870 候选）

### 2.1 排列

| 项 | 计数 |
|---|---|
| 段数（连通分量）3 / 4 | 809 / 61 |
| 原始线段数 3 / 4 / 5 / 6 | 802 / 23 / 4 / 41（按候选计） |
| 方向 grid / horizontal | 845 / 25 |
| 端部横向偏移（同一水平线） | 0（全部共线，无台阶） |
| 端部或中部有非成员线接触（拐角/T） | 左端 拐角 4、分支 2；右端 拐角 18、分支 50 |

“有拐角/T 形分叉”在组内不存在（组内只有水平线）；拐角与 T 出现在组的外端，即竖向线接在组端点上（分支端的圆点数未单独统计）。

### 2.2 非本体间隙（935 个）

| 间隙类别 | 数 | 含义（目视与几何） |
|---|---|---|
| UNREG2：未登记两引脚符号，两个 TERMPOINT 恰好跨越间隙（宽 10.0） | 668 | 绘制的线圈/灯类符号，带标签（如 `5C3LP2`、`1C6LP1`），两端引脚号 1、2 |
| SWELEM：SuperWORKS 内部元件或线圈的 TERMPOINT 在间隙内（含宽 18.75 的虚线框内触点） | 137 | 登记的内部元件（触点、线圈），常带洋红引脚标记 |
| DEVBODY：另一装置端子的 TERMPOINT 在间隙内 | 118 | 同一线上的相邻装置端子本体（串接端子排） |
| FRAME：非成员绘制线穿过间隙（框线、模块框） | 12 | 装置框或 DC/DC 模块框穿越导线 |
| LBL / DOT / EMPTY | 0 | 这 870 个候选中不出现；纯文字间隙已在 2.3 中归为 UNREG2 或 DEVBODY |

候选本体间隙：866 个候选能在线组中定位到相邻两段之间的本体间隙，其中 865 个宽 2.5（4 个候选的两接触点不能在段端点上找到对应间隙，未计入）。

### 2.3 外端

| 位置 | 类别 | 数 |
|---|---|---|
| 左端 | 端子（端子排外部端子） | 204 |
| 左端 | 未登记 SYMB2 引脚（G1P 类） | 336 |
| 左端 | 空白（无任何 SW 点，绘制的无标记触点） | 177 |
| 左端 | 内部元件（SW 登记，洋红引脚） | 145 |
| 左端 | 装置端子 / 分支 / 拐角 | 2 / 2 / 4 |
| 右端 | 端子 | 801 |
| 右端 | 分支（T）/ 拐角 | 50 / 18 |
| 右端 | 内部元件 | 1 |

### 2.4 形态家族（按签名 = 外端 | 间隙序列 | 外端）

| 家族 | 候选数 | 典型签名（数） |
|---|---|---|
| F1 端点 \| 本体 \| 两引脚符号 \| 端子 | 654 | UNREG\|BODY-UNREG2\|TERM 332；BLANK\|BODY-UNREG2\|TERM 177；ELEM\|BODY-UNREG2\|TERM 145 |
| F2 端子 \| 内部触点 \| 本体 \| 端子 | 137 | TERM\|SWELEM-BODY\|TERM 112；TERM\|SWELEM-BODY-UNREG2\|TERM 12；TERM\|BODY-SWELEM\|CORNER 7；CORNER\|SWELEM-BODY\|TERM 4；BRANCH\|SWELEM-BODY\|TERM 2 |
| F3 装置端子串接（多本体） | 71 | TERM\|DEVBODY-DEVBODY-BODY\|BRANCH 43；TERM\|DEVBODY-BODY\|TERM 11；TERM\|DEVBODY-BODY\|BRANCH 7；TERM\|BODY-DEVBODY\|CORNER 4；TERM\|DEVBODY-BODY\|CORNER 4；TERM\|DEVBODY-BODY-UNREG2\|TERM 2 |
| F4 框线穿越/拐角/圆点分支 | 8 | UNREG\|BODY-FRAME\|CORNER 3；TERM\|FRAME-FRAME-DEVBODY\|TERM 2；DEVTERM\|FRAME-FRAME-DEVBODY\|TERM 2；UNREG\|BODY-FRAME\|ELEM 1 |

签名共 18 种（完整列表见 `details.json` 的 `classification.signature_counts`）。

## 3. 目视（40 例分层抽样 + 核对组 4 例）

抽样：签名分层，种子 20261011，每层最多 5 例（S8 层 4 例，其余 4 例已在家族层覆盖）。图 `png/MS_01.png` 至 `MS_20.png`，每图两例，各一宽视图与一本体近景；橙、蓝、绿、紫为线组各段（P0…P3），蓝框为候选端口，浅蓝框为其它装置端子，洋红为内部元件，深灰为端子，绿为未登记引脚，红点为连接圆点。**40 例均已目视**（单人判定）。

| 家族 | 目视例数 | 判定 |
|---|---|---|
| F1 | 15 | 本体为真实装置端子；本体另一侧经一个两引脚符号（有标签、两引脚号 1、2）才到外部端子。这一符号未被 SW 登记为端口，也不是导线。左端三种：未登记 SYMB2 触点（UNREG，MS_01、MS_02 等）、SW 内部触点（ELEM，洋红引脚，MS_06、MS_07、MS_08）、无 SW 标记的绘制触点（BLANK，MS_03–05）。**结论：两侧不构成连接，合并错误。** |
| F2 | 12 | 本体一侧为串联的登记内部触点（MS_08–10，含虚线装置框内的告警触点），或串联的内部触点加两引脚元件（MS_13–15）；另有 3 例为拐角/圆点 T 接（MS_16–18）。**结论：导线经触点后才到本体，应切开。圆点 T 接为真实连接，其分支接到绘制元件而非 SW 端口。** |
| F3 | 10 | 多个装置端子沿同一导线串接（端子排式，MS_11–13、MS_14–16 的 DEVBODY 段）：每个本体是贯通节点，中间段为装置端子与装置端子之间的直连导线，末端为分支。**结论：应逐本体切开，中间段是候选外部配对，末端分支需单独判定。** |
| F4 | 3 | 框线穿越（MS_20 的 DC/DC 模块框 #807、装置框内的线圈 #485 与 #720）。**结论：框线或绘制符号穿过导线时应切开，并记 FRAME。** |
| 核对组（`MS_R01.png`，4 例） | 4 | M2 移除的“装置端子—端子”生产候选（抽 4 例），导线中间均为绘制的线圈或触点（1KLP1、4-21KLP1、8YFA、1YFA）。**结论：这 4 例移除正确；其余 108 例未逐例目视，仅按间隙宽 10–11.3 与“两段间有符号”的规则归类。** |

目视局限：单人判定；元件标签在 DXF 中多数可读，但“同装置归属”依据 SW 标签引用，目视不能独立证明归属。

## 4. 连接方法与离线模拟

### 4.1 方法定义

- **M_prod**：生产的 GAP2-S（两段规则）。
- **M0**：不切分（线组即导线），仅保留元件标识守卫。
- **M1**：本体切分，不限段数：每个装置端子本体（同 insert、同标识、两 TERMPOINT 接触在相邻段的两侧、宽 ≥2.0 且与本体宽一致、间隙无穿越线、无圆点）都切开。
- **M2**：M1 加上元件间隙切分：间隙内若有“未登记两引脚符号跨越”（两端 TERMPOINT 恰在间隙两端）、“同 insert 的 SW 内部元件/装置端子 TERMPOINT 跨越间隙”、或“非成员线穿过间隙（不止于端点）”，则切开。纯文字间隙、圆点间隙与空的小间隙保持合并。单个 TERMPOINT 挂在导线端点上的元件不切（早期版本会把它误切，已修正并验证）。

### 4.2 复现校验

用同一套离线输入（端口、路由、未登记块、端点、线组、圆点）复现生产：M_prod 得 **18646**（与 GAP2-S 最终版一致，切分链接 3942），M0 得 **14704**（= round20 的 14801 减去 97 个元件标识守卫）。离线输入可信。

### 4.3 结果（77 项目，`details.json` 的 `offline_simulation`）

| 方法 | 装置内部链接 | 元件 / 未登记 | 相对生产 | 外部候选（wire 数） | 双端均已配对 | 单侧已配对 | 双端未配对 | 冲突（按候选计） | 新增端口（未 pass 覆盖） |
|---|---|---|---|---|---|---|---|---|---|
| M_prod | 18646 | 16450 / 2196 | 0 | 17674 | 17529 | 1 | 122 | 22 | 258 |
| M0 | 14704 | 12625 / 2079 | −3942 | 17674 | 17529 | 1 | 122 | 22 | 258 |
| M1 | 19126 | 16595 / 2531 | +480 | 22957 | 22138 | 1 | 796 | 22 | 1606 |
| **M2** | **19276** | 16745 / 2531 | **+630（丢失 0）** | 21885 | 21859 | 1 | 16 | **9** | 33 |

注：“冲突”按候选 wire 计：候选的某一端口已有 pass 伙伴，且该伙伴不是候选的另一端。配对按端口计（`sw_port_coverage.production_pairs`），不按身份值合并，因为同一装置端子的两个端口分别配对是正常的。

M_prod → M2 的外部候选变化：新增 4640 个 wire（4634 双端已配对且一致，6 个双端未配对）；移除 429 个（112 双端未配对、304 双端已配对、13 冲突）。移除的 112 个中，4 例经目视（`MS_R01.png`）确认为经元件的误连，其余 108 例未逐例核对。

870 候选的 1740 个端口在 M2 下的结局：装置内部链接 496（元件 161、未登记引脚 335），外部候选 153，**未解决 1091**。

### 4.4 对 R-* 规则的潜在影响

- 装置内部链接不进入 R-* 规则（GAP2-PAIR 已 grep 验证），故 M2 的 +630 链接不改变配对与 issue。
- 外部候选若将来接入配对：M2 的新增双端候选仅 16 个，冲突 9 个（按候选计，即其一端口已有其它 pass 伙伴；须先处理）。R-MANY-TO-ONE、R-ONE-TO-MANY 与 R-DUPLICATE-PAIR 的计数未通过规则引擎回放，此处未测，列为后续项。
- M1 不可接入：796 个新候选中约 780 个为穿越两引脚元件的假配对。

## 5. 泛化：依赖的原理与未知形态

### 5.1 依赖的通用原理（不依赖块名、项目或句柄）

1. **SW 端口元数据**：TERMPOINT 的 category、insert_handle、endpoint_identity、port_number 与 wire_contacts。同 insert 且同标识的两个装置端子端口即为一个端子本体。
2. **未登记 SYMB2 的 TERMPOINT 对**：同一块的两个 TERMPOINT 即为两引脚符号的两端（块名不用）。
3. **几何**：本体宽（两 TERMPOINT 中点距离，2.5 为二端口符号，1.25 为三针符号，后者拒绝切分）；间隙与线段的轴向关系；非成员线是否穿过、是否止于间隙（T）；圆点与文字是否在间隙内。
4. **拓扑**：线段按端点连通分量成段；段的外端接触的对象（SW 端口类别、未登记引脚、圆点、非成员线、空白）。

### 5.2 形态词表与未知形态

- 间隙类别词表（闭合）：`BODY`、`ELEMENT_SPAN`（未登记或 SW 块两端跨越）、`ELEMENT_INSIDE_UNBRACKETED`（不切，记为挂靠）、`FRAME`（穿越）、`DOT_JUNCTION`、`LABEL`、`EMPTY`、`UNKNOWN`。
- 外端词表（闭合）：`SW_TERM`、`SW_DEVTERM`、`SW_ELEM`、`UNREG_PIN`、`BRANCH`、`CORNER`、`BLANK`、`UNKNOWN`。
- 不在词表内、或违反假设的情形，写入产物 `sw_topology_unknown`（原因码 + 句柄样例）：
  - `gap_two_tp_not_bracketed`：两个 TERMPOINT 不属于同一块或不跨越间隙；
  - `body_width_nonstandard`：同 insert 对的宽度既非 2.5 也非 1.25；
  - `node_multi_sw_port_ge3`：一根导线接 3 个及以上 SW 端口（全项目 M2 口径 3716 个）；
  - `end_blank_drawn_symbol`：端点为绘制符号而无 SW 标记（本次 177 个候选的左端）；
  - `single_end_label_differs` / `no_far_pin`：单端导线指向未登记符号但标签不符或无对应引脚；
  - `dot_branch_unresolved`：圆点 T 接导向的非成员线无法归入任何段；
  - `gap_crossed_refused`：穿越线导致拒切（原 3 例 `gap_crossed`，M2 中按 FRAME 切开，未逐例核对）。
- 本次 M2 统计的 `unknown_topology` 原因计数见 `details.json` 的 `unknown_topology_under_M2`（如 `excluded:wire_no_other_port` 8597、`unregistered:no_far_pin` 6702、`excluded:wire_multi_end` 4050、`multi_port_wire_ge3` 3716）。

### 5.3 回归夹具（合成 DXF 片段，建议放入 tests 的新文件，本次未写）

| 夹具 | 构造 | 期望 |
|---|---|---|
| T1 二端口本体两侧导线 | 2 段，本体 2.5 | 切开，记 terminal_body |
| T2 串接三本体 | 4 段，3 个同 insert 对，末端分支 | 切 3 次，段间 pass-through 边 |
| T3 两引脚符号跨越 | 3 段，中间为两个 TERMPOINT 相距 10 的未登记块 | 切开，外端分别为 UNREG_PIN |
| T4 纯文字间隙 | 10 宽、只有标签文字，无符号 | 保持合并（反例） |
| T5 圆点间隙 | 2.5 间隙内有圆点 | 保持合并（反例） |
| T6 挂靠元件 | 间隙内单个 SW 元件 TERMPOINT 挂在一段端点（1C074 型） | 不切 |
| T7 穿越线 | 2.5 间隙内有竖线穿过 | 切开并记 FRAME |
| T8 T 接止于间隙 | 竖线止于间隙 | 保持合并并记 T |
| T9 三针符号 | 本体宽 1.25 | 拒绝，记 body_width_nonstandard |
| T10 多端节点 | 一段接 3 个 SW 元件 TERMPOINT | 不切，记 node_multi_sw_port_ge3 |
| T11 空白端 | 段端为绘制触点而无 SW 标记 | 记 end_blank_drawn_symbol，不成链 |
| T12 异 insert 跨越 | 两个不同 insert 的 TERMPOINT 跨越间隙 | 记 gap_two_tp_not_bracketed，不切 |

## 6. 实施建议与风险

### 6.1 建议（按顺序）

1. 在 `split_terminal_wires` 中把“两段”改为“按顺序的 k 段”：对每个间隙按 5.2 词表分类，切开 BODY、ELEMENT_SPAN、FRAME；合并 DOT_JUNCTION、LABEL、EMPTY（≤4.0）。切分只改 DEV-INT 的线组映射，不改线组与配对（与 GAP2-S 相同约束）。
2. 外部候选只写审计表（如 `sw_topology_candidates`），不接入配对；待 R-* 回放后再决定。
3. 写 `sw_topology_unknown`，列出原因码与句柄样例；不静默合并。
4. 按 5.3 增加回归夹具（T1–T12）。
5. 全量回放 77 项目，期望：装置内部链接约 19276，`pairs` 与 `issues` 逐条不变（M2 不接入配对），`sw_topology_unknown` 的计数与本报告一致。

### 6.2 风险

- **标签间隙未验证**：这 870 个候选中没有“仅文字”间隙，LBL 规则（纯文字合并）只能在被接受的线组上检验，需要单独抽样。
- **穿越线切分偏保守**：FRAME 规则会切开真正穿过导线的线条（M2 中相对生产未丢失任何链接端口，但未逐例核对）。
- **同 insert 跨越判定**：只校验两个 TERMPOINT 的 insert 与间距；多针元件若分属不同 insert，会进入 unknown。
- **根因在线组构建**：845 个 grid 线组中，多段拼接来自行内数字文字桥接（`inline_numeric_bridge_gap` 12，信号/告警页 20）跨过元件框。从源头（`line_groups.py`）修复会改变线组与配对，属于另一切片，本次不做。
- **未回放规则引擎**：外部候选的 R-* 影响未测；M2 的 9 个端口级冲突须先处理。
- **输入近似**：离线 wire_endpoints、未登记块与路由取自产物表，已通过 18646 / 14704 精确复现验证，但不等同于流水线内部对象。
- **目视样本**：40 例、单人判定，家族代表性有限。

## 7. 复现与文件

- 目录：`loop/MULTI-SEG/`
  - `details.json`：分类计数、签名表、40 例样例表（含 PNG 对应）、离线模拟结果、M2 的 870 端口结局、未知形态计数与样例。
  - `png/`：`MS_01.png` 至 `MS_20.png`（40 例目视样例），`MS_R01.png`（M2 移除候选的核对组）。共 21 张（≤25）。
  - `tools/`：`ms_common.py`（加载与候选复现）、`ms_geom.py`（几何索引）、`ms_classify.py`（870 候选分类）、`ms_gapclass.py`（最终间隙与外端分类，写 `sig870.json`）、`ms_sample.py`（分层抽样）、`ms_render.py`（DXF 渲染，依赖 `loop/GAP/tools/gap_render.py`）、`ms_sim.py`（M_prod/M0/M1/M2 离线模拟）、`ms_final.py`（M_prod 与 M2 对比）、`ms_details.py`（生成 details.json）；辅助脚本 `render_removed.py`、`removed_new.py`、`diag_m2.py`、`agg870.py`、`agg_gaps.py`、`gap_unreg.py`、`check_prim.py`。`ms_signature.py` 为早期旧签名版本，已由 `ms_gapclass.py` 取代，仅留作追溯。
- 运行顺序：`ms_classify.py` → `ms_gapclass.py` → `ms_sample.py` → `ms_render.py` → `ms_sim.py M_prod M0 M1 M2` → `ms_final.py` → `ms_details.py`。
- 中间表（可删）：`.tmp/multiseg_work/`（cls870.json、sig870.json、sim_detail_*.json、final_summary.json、removed_new.json 等）。`.tmp/multiseg_src/superworks_device_internal_ref.py` 为 `ms_common` 的依赖，删除前需确认不再使用；两者均为本次调研的中间产物，确认无需后可删。
- 更正：GAP2-S README 中“线组段数 3/4”为连通分量数；GAP2-PAIR 的“端子本体两侧被合并”结论保留，但 G2 的“线号标注断口”对这 870 个候选不成立（间隙为两引脚符号或元件）。
