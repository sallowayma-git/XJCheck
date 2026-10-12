# WIRE-BREAK：线组构建在端子本体与元件符号处断开

分支 superworks-loop，基线 HEAD=f068c88（上次桌面退出时未落盘，本次从头重做）。未 commit、未 push。未改 V2 模块与 `symbol_port_proposal.py`，未加 PDF/OCR，未加开关，判据无项目、句柄、取值或块名特判，未整体豁免 SuperWORKS 来源。控制台 `PYTHONIOENCODING=utf-8`。

## 0. 结论

1. **规则**：线组（同一根线的合并段）在“符号本体”处断开。符号本体 = 同一符号的两个 TERMPOINT 标记分处间隙两侧（且至少一个贴住线端），间隙宽 ≥ 2.0。端子本体两侧的导线、两引脚符号、内部元件跨越的间隙都按此断开，各段分别连到相邻的端子或元件。
2. **单页 p026 F0008**：行 y=192.5 的线组原先把 5n1431 端子本体、5C3LP2 两引脚符号、5KD4 端子连成一条；改后在 1431 本体与 5C3LP2 两处断开，各段分别连到相邻端子或元件。`5n1431 ↔ 5C3LP2-2`、`5KD4 ↔ 5C3LP2-1` 的 SW 线路配对改前改后都存在（review）。该页线组 2156 → 2030；非 discard 配对不变，discard 配对替换 8 条（第 5 节）。
3. **10 项目**：issue 全部不变（逐条相同）；严格覆盖（不剔除）合计 5925/8618 → 5918/8618（−7），含延续 6518 → 6508（−10）；剔除装置内部口径见第 6 节。
4. **全量 77 项目**：线组 131163 → 125318；pairs 172529 → 178696（新增 7263、删除 1096）；issues 41 → 42（新增 2、消失 1，均已逐条判定，第 7 节）；剔除装置内部后严格覆盖 81.29% → 82.11%，含延续 83.84% → 84.53%；未剔除口径的严格覆盖 62.94% → 62.85%（消费端口净减 75，原因见第 6.3 节）。
5. **抽样**：30 例新增或变为 pass 的配对目视全部正确；消失的 322 条 pass 配对全部位于基线线组内一个符号本体的间隙上（机器核对）；消失的 121 条 review 配对中 15 条同样跨符号，其余 106 条被同页同值的完整配对替代或为两端皆空的退化配对。
6. **未知形态**：30 条（`body_width_below_min` 16、`dot_in_symbol_gap` 14），全部保留原合并结果并写入 `sw_topology_unknown.parquet` 供复核。
7. **DEV-INT 切分**：`split_terminal_wires` 在全量中由 4748 次切分降为 0（线组已在源头断开），保留为兼容（说明见第 9 节）。

## 1. 改动文件

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/audit/line_groups.py` | `WireBreakEvidence` 增加 `marks`（符号 TERMPOINT 标记）、`stats`、`log`、`cuts`；`wire_break_evidence_by_sheet` 接收未登记 SYMB2 的 TERMPOINT；新增 `_MarkIndex`、`_symbol_body_cuts`、`_symbol_gap_verdict`、`_symbol_body_between`、`symbol_cut_group_ids`；水平/竖向与 grid 两条合并路径都拒绝跨越符号本体的合并（包括数字文字桥接）。 |
| `src/dwg_audit/pipeline.py` | 传入未登记块 TERMPOINT；汇总 unknown 行与计数到 SuperworksData；计算切口线组 id。 |
| `src/dwg_audit/extract/superworks_semantics.py` | `SuperworksData` 新增 `topology_unknown`、`topology_stats`、`topology_cut_group_ids`。 |
| `src/dwg_audit/audit/superworks_extractor.py` | 线路配对准入：切口线组上的非 pass 配对（或缺端配对）不占用端口与线组；SW 线路配对顶替其占用的同端口临时配对（`displaced_provisional`）。 |
| `src/dwg_audit/audit/superworks_wire_walk.py`（第 13 轮新增） | 线网络遍历（拐角、T 接、分支相接），不跨符号本体；纯几何。 |
| `src/dwg_audit/report/superworks_artifacts.py` | 写 `sw_topology_unknown.parquet`；summary 增加 `topology` 段（计数、按原因计数）。 |
| `tests/unit/test_superworks_wire_walk.py`（第 13 轮新增，7 项） | 走线遍历与走线丢弃的合成夹具。 |
| `tests/unit/test_line_groups_symbol_breaks.py`（新增，15 项） | 合成几何夹具（见第 4 节）与准入规则测试。 |

未改：`superworks_device_internal.py`、V2 模块、`symbol_port_proposal.py`、`line_groups` 之外的合并规则（G2 判据原样保留）。

## 2. 断点判定（`_symbol_body_cuts` / `_symbol_gap_verdict`）

- **符号标记**：每个 SW 端口（`SwPort`，所有类别）的 TERMPOINT 线段，以及每个未登记 SYMB2 块的每个 TERMPOINT（`a→b` 线段）。同一符号的标记共享符号键（SW 端口为 `symbol_id`，未登记块为 `SW:file:sheet:instance_path`，与 `symbol_id` 同格式）。
- **候选间隙**：同一行带内两条候选线段（长度 ≥ 最小导线长度）之间的间隙 `(lo, hi)`，`0 < hi - lo ≤ 非信号页 12 / 信号告警页 20`。
- **符号本体**：在窗口 `[lo-1, hi+1]` 内（标记完全落在窗口内、横向在线上 ±1）有同一符号的两个不同标记 `m1`、`m2`，其中心分处间隙中点两侧（`c1 < mid < c2`），且 `m1` 贴住 `lo` 或 `m2` 贴住 `hi`（贴住 = 点到标记线段距离 ≤ 1.0）。“贴住”的容差沿用 SW 端口的 `_TERMINAL_TOUCH_TOLERANCE`。
- **断开**：判为符号本体的间隙，在任何合并路径（间隙 ≤ 4.0、数字文字桥接 ≤ 13/20）中都不合并；记入 `symbol_body_gap` 计数。
- **歧义形态**（保留原合并结果，并写入 unknown）：
  - 间隙内有连接圆点：`dot_in_symbol_gap`；
  - 间隙宽 < 2.0（三针符号 1.25 节距或两针过近）：`body_width_below_min`；
  - 线端同时贴住两个不同符号：`node_multi_symbol_at_end`（仍断开，并记录）。本次全量为 0 条。

## 3. 保持合并的情况

- 纯文字间隙（无符号标记）：数字文字桥接保持原行为（夹具 `test_text_only_gap_keeps_the_wire_merged`、`test_numeric_label_does_not_bridge_a_symbol_body` 的对照组）。
- 圆点间隙（无符号）：保持合并（夹具 `test_connect_dot_without_symbol_keeps_the_wire_merged`）。
- 零间隙与重叠：不变。
- 端口只在一侧（挂靠元件，一个 TERMPOINT 在线端）：不切（夹具 `test_terminal_hanging_on_a_wire_end_does_not_cut`）。
- 两个不同符号的标记分处两侧：不算符号本体（夹具 `test_marks_of_two_different_symbols_do_not_cut`）。
- 不同行：不切（夹具 `test_marks_on_another_row_do_not_cut`）。
- G2 判据（不同端口两侧、无文字、无圆点的空断口）保留在原位，本切片未改。

## 4. 夹具（`tests/unit/test_line_groups_symbol_breaks.py`，15 项全部通过）

| 夹具 | 对应 MULTI-SEG §5.3 | 结果 |
|---|---|---|
| 两端口本体 2.5（T1） | T1 | 切开 |
| 连续三本体（T2） | T2（段间直连） | 切开为三段 |
| 两引脚符号跨越 10（T3） | T3 | 切开 |
| 数字标签跨符号本体不桥接 | 本切片第 1 条 | 无符号时桥接，有符号时不桥接 |
| 纯文字间隙（T4） | T4 | 保持合并 |
| 圆点间隙无符号（T5） | T5 | 保持合并 |
| 圆点在符号间隙内 | 本切片 unknown | 保持合并并记 `dot_in_symbol_gap` |
| 挂靠元件（T6） | T6 | 不切 |
| 三针节距 1.25（T9） | T9 | 保持合并并记 `body_width_below_min` |
| 不同 insert 的标记（T12） | T12 | 不切 |
| 不同行的标记 | — | 不切 |
| 元件位于间隙内且一端贴住（T10 近似） | T10 | 切开 |
| SwPort 与未登记块合并为标记、圆点、key 格式 | — | 证据构建正确 |
| 切口线组判定 `symbol_cut_group_ids` | — | 切口端线组被标记 |
| 准入：`_is_provisional_half`（pass 与 sw_wire_route 不算临时） | — | 规则正确 |

未实现：T7（框线穿越）、T8（T 接止于间隙）、T11（空白端）。原因：本切片规则只以 SW 符号接点为断点（框线、T 接不是符号接点，保持原行为）；空白端没有对应的 SW 元数据，只能在 unknown 中列出，本次未出现独立的空白端记录。

## 5. 单页验证：p026 F0008（08 跳闸出口回路，S0008）

图：`png/WB_p026_S0008_before_after.png`（全页，改前/改后线组着色）、`png/WB_p026_S0008_zoom_1431_1521.png`（1431 行与 1521 行放大，上下各两行）。

- 行 y=192.5：改前 GW0135 = 171.25→257.5 跨过 5n1431 本体（口 1 在 205.5、口 2 在 207.0）与 5C3LP2（TERMPOINT 230.5 / 239.5）；改后为 171.25→205、207.5→230、240→257.5 三段，各段端点分别落在 5n1431 口 1 / 口 2、5C3LP2 的两个 TERMPOINT、5KD4 口 1 上。
- 行 y=152.5（5n1515 与 5n1527 之间有 5n 两引脚符号）与行 y=182.5（5n1509 与 5n1521）同理：符号本体两侧的线段分开。

改前后 S0008 配对（左、右值，状态，类别；来自 `findings/pairs.parquet`）：

| 配对 | 改前 | 改后 |
|---|---|---|
| `5n1431 ↔ 5C3LP2-2` | review，wire_component_mapping（SW 线路） | 同左（不变） |
| `5KD4 ↔ 5C3LP2-1` | review，wire_component_mapping（SW 线路） | 同左（不变） |
| `5n1527 ↔ 5C4LP4-2`、`5KD8 ↔ 5C4LP4-1` | review，wire_component_mapping（SW 线路） | 同左（不变） |
| `1419 ↔ 5KD4`、`1515 ↔ 5KD8`、`1509 ↔ 5KD5` 等 8 条 | discard，wire_component_mapping | 消失（跨 5n 符号本体的旧 discard 配对） |
| `1419 ↔ 1431`、`1515 ↔ 1527`、`1509 ↔ 1521` 等 8 条 | — | 新增 discard，ordinary_pair（文字候选穿过 5n 元件，见第 11 节遗留风险 1） |

本页非 discard 配对：改前改后相同（无增无减）；pairs 总数 49 → 57（均为 discard 的替换 8+8，外加线组变化导致的其余条目）。`sw_port_coverage` 中本页覆盖口径不变（严格剔除口径 736/897）。

## 6. 10 项目对比（`.tmp/superworks_round22_full` vs `.tmp/superworks_round23_full` 的 10 项目子集）

项目：p001 p003 p022 p026 p044 p051 p061 p071 p074 p075。`tools/wb_compare.py`，结果 `tools/results/wb_10_cmp.json`。

| 项目 | 线组 | pairs（新增/删除） | issues | 剔除装置内部严格覆盖（改前→改后） |
|---|---|---|---|---|
| p001 | 1092 → 1058 | 1324 → 1371（+52/−5） | 0 → 0 | 441/519 → 437/510 |
| p003 | 646 → 615 | 655 → 685（+32/−2） | 0 → 0 | 256/310 → 256/306 |
| p022 | 1221 → 1158 | 1699 → 1761（+80/−18） | 1 → 1 | 450/557 → 444/542 |
| p026 | 2156 → 2030 | 2491 → 2614（+135/−12） | 0 → 0 | 736/897 → 736/889 |
| p044 | 2058 → 2015 | 3033 → 3088（+63/−8） | 1 → 1 | 858/1072 → 858/1071 |
| p051 | 621 → 601 | 797 → 817（+23/−3） | 0 → 0 | 190/213 → 190/213 |
| p061 | 3136 → 2993 | 4305 → 4495（+230/−40） | 0 → 0 | 1330/1468 → 1333/1460 |
| p071 | 425 → 398 | 537 → 564（+31/−4） | 3 → 3 | 146/190 → 146/188 |
| p074 | 1645 → 1549 | 2455 → 2549（+96/−2） | 0 → 0 | 748/851 → 748/851 |
| p075 | 1384 → 1378 | 2346 → 2352（+6/−0） | 4 → 4 | 770/792 → 770/786 |

- 10 项目 issues 逐条相同（新增 0、消失 0）。
- 严格覆盖（不剔除）10 项目合计：5925/8618 → 5918/8618（68.75% → 68.67%）；含延续 6518 → 6508（75.63% → 75.52%）。变化项目：p001 −4、p022 −6、p061 +3（严格）；p001 −4、p003 −1、p022 −6、p061 +1（含延续）。
- 线组与配对变化的类别分解见 `tools/results/wb_breakdown10.json`。

### 6.1 pairs 分类（10 项目）

- 新增 pass：9（wire_component_mapping，已并入全量抽样）。
- 消失 pass：54（`tools/results/wb_removed_pass10.json`，全部机器核对为跨符号本体，见第 7.2 节）。

### 6.2 全量（77 项目）

| 指标 | 改前（round22） | 改后（round23） |
|---|---|---|
| 线组 | 131163 | 125318 |
| pairs | 172529 | 178696（+7263，−1096） |
| issues | 41 | 42（+2，−1） |
| 严格覆盖（不剔除） | 52039 / 82680 = 62.94% | 51964 / 82680 = 62.85% |
| 含延续（不剔除） | 59149 / 82680 = 71.54% | 59038 / 82680 = 71.41% |
| 严格（剔除装置内部） | 52039 / 64013 = 81.29% | 51964 / 63287 = 82.11% |
| 含延续（剔除装置内部） | 53668 / 64013 = 83.84% | 53499 / 63287 = 84.53% |
| DEV-INT 切分（`terminal_splits`） | 4748 | 0 |
| 装置内部链接 | 19084 | 19771 |
| 符号本体间隙（候选对，计数） | — | 12043 |
| `sw_topology_unknown` 行 | — | 30 |

说明：剔除装置内部后，分母由 64013 变为 63287（装置内部端口集合随切分变化）；未剔除口径的分母固定为 82680。

### 6.3 消费端口的增减（未剔除口径，净减 75）

- 共 105 个端口失去覆盖，30 个端口获得覆盖。
- 失去覆盖的 110 条占用链接全部为旧的 legacy 配对，且在新结果中按内容键已不存在：
  - 44 条来自 pass 配对：其基线线组内含符号本体（均为跨符号错误配对，见第 7.2 节）；
  - 66 条来自 review 配对：其中 15 条跨符号本体，其余 51 条被同页同值的完整配对替代或属于两端皆空的退化配对（见第 7.3 节）。
- 新增覆盖的 30 个端口：未逐条核对其来源（准入阶段 `displaced_provisional` 计数 p000 5、p022 13、p061 47，部分替换有此类贡献）。

## 7. 新增 / 消失 issue 与抽样

### 7.1 issue 逐条判定

| issue | 状态 | 判定 |
|---|---|---|
| p040 S0005 `R-PAIR-MISSING-SIDE` 配对 PW0054（612 ↔ 空，GW0054）| 新增 | **主线程复核判为误报（见第 13 节）；未消除**。原判定：图 `png/WB_p040_S0005_missing_side.png`。改前线组 GW0045 跨 132.5→200 覆盖了 2n612 端子本体（端子口在 147.0–150.5，间隙 2.5），没有任何配对，因此该端子右侧导线的“另一端未识别”被隐藏。改后端子本体断开，右侧 150→200 段的一端是 2n612，另一端止于绘图框线（200 处竖线），没有 SW 符号、没有可识别的对侧标注。它是 review 级的真实缺侧，原先被跨端子本体的合并掩盖。 |
| p040 S0005 `R-PAIR-MISSING-SIDE` 配对 PW0060（612 ↔ 空，GW0060）| 新增 | **主线程复核判为误报（见第 13 节）；未消除**。原判定：同类：1n612 端子（y=230）的右侧段止于框线，同样的缺侧。 |
| p000 `R-PAIR-LOW-CONFIDENCE`，基线配对 PW0256（4P1D2 ↔ 12，review，wire_component_mapping） | 消失 | **合理消失**。基线中该配对的右端为裸数字 `12`（低置信度）。改后同一端口 4P1D2 有 SW 线路记录给出的完整配对（4P1D2 ↔ FZJ1-11，review）。p000 的准入阶段 `displaced_provisional` 计数为 5，说明存在此类顶替；未逐条核对 PW0256 本身的替换链（线组 id 在两次运行间不一致，不能直接对应）。 |

### 7.2 消失的 pass 配对（322 条，全量）

- 类别：wire_component_mapping 259、bridge_mapping 54、ordinary_pair 9。
- 逐条核对（`tools/results/wb_removed_pass77.json`）：每条基线线组的未覆盖间隙内，都存在同一符号的两个 TERMPOINT 分处间隙两侧（`body` 字段给出符号键与间隙端点）。即全部为跨符号本体的错误配对（例：p071 S0006 YD4 ↔ YD13 bridge 配对跨过未登记两引脚符号 `2-57DK2`，TERMPOINT 位于 130.0/130.5 与 140.75/141.75 之间）。
- 说明：逐条的判据是机器核对；未对 322 条逐条截图，仅对 p071 的一例按坐标核实。

### 7.3 消失的 review 配对（121 条，全量）

- 15 条跨符号本体（同 7.2 的判据）。
- 106 条基线线组无内部缺口（缺侧半配对或两端皆空的配对）。自动归类（`tools/results/wb_removed_review77.json` 与脚本内核对）：81 条的同页同值在新结果中已有完整 pass 配对，1 条有 review 替代，24 条两端值皆为空（退化配对，随线组变化消失）。

### 7.4 新增 pass 抽样（30 例，目视）

- 总体 48 条（新增 43，由 review/discard 变为 pass 5）。抽样：5 条状态变化全部取上，其余 25 条按项目分层随机（`random.Random(20261011)`）。
- 图：`png/WB_pass_sample_01.png` 至 `WB_pass_sample_05.png`（每张 6 例，橙色为配对所在线组，红方块为 SW 端口，绿方块为未登记 TERMPOINT）。
- 结论：30 例全部为端子或元件引脚之间的直接导线（中间无被跨过的符号），配对正确。典型例：`1QD4 ↔ 13`、`1QD7 ↔ 13`、`8QD4 ↔ 13`、`3-4Q2D2 ↔ 13`、`14 ↔ 3-4QD17`、`12 ↔ YD12`。

## 8. 耗时

（见下表，`tools/wb_time8.sh`，顺序执行，每项目基线与改后各一次，无并行负载。）

| 项目 | 基线（s） | 改后（s） | 增量 |
|---|---:|---:|---:|
| p001 | 77.4 | 76.8 | -0.74% |
| p003 | 49.8 | 49.3 | -1.14% |
| p022 | 96.2 | 96.0 | -0.12% |
| p044 | 155.0 | 156.0 | +0.63% |
| p050 | 152.7 | 153.0 | +0.24% |
| p051 | 46.5 | 46.2 | -0.56% |
| p071 | 43.6 | 44.5 | +2.02% |
| p075 | 113.1 | 111.0 | -1.80% |
| 合计 | 734.2 | 732.8 | -0.18% |

结论：8 项目合计增量 -0.18%，远低于 3% 上限；单项目增量在 ±1.5% 内，属于测量噪声范围。耗时在本切片中主要由 ezdxf 读取与文本/几何提取决定，线组新增判据（`_symbol_body_cuts`、`symbol_cut_group_ids`）在 p022 的 cProfile 中合计约 0.2 秒（含剖析开销，占总耗时远低于 1%）。

## 9. DEV-INT 切分的处理

- 线组在源头断开后，DEV-INT 的 `split_terminal_wires` 在全量中由 4748 次降为 0：端子两侧已分属不同线组，`split_terminal_wires` 不再有可切的组。
- 决定：**保留为兼容**，不删除。理由：函数是纯读取、代价可忽略（耗时对比中已计入），且它覆盖源头规则未覆盖的形态（例如两个端子接触点落在同一线组两段、但未通过符号本体判据的情形）；删除会改变 DEV-INT 模块的接口与测试。若后续确认永远为 0，可单独清理，不属于本切片。
- DEV-INT 内的 G1P、装置内部丢弃规则不受影响。

## 10. 新图纸同类情况如何处理

1. **判据只依赖 SW 元数据与几何**：TERMPOINT 标记（SW 端口的 TERMPOINT、未登记 SYMB2 块的 TERMPOINT）、线段端点、圆点。没有块名、项目名、句柄或取值判断。
2. **同类新图纸**：只要符号的两个 TERMPOINT 分处线路两侧，即按符号本体断开；不论符号是否登记（未登记 SYMB2 块同样使用）。
3. **遇到不认识的形态**：间隙内有圆点、三针节距或两针过近（`body_width_below_min`、`dot_in_symbol_gap`）→ 保留原结果，写入 `sw_topology_unknown.parquet`（字段：页、原因码、动作、导线句柄、线号、左右标记），复核后再决定。`node_multi_symbol_at_end` 同样列出。
4. **无符号元数据的页**：规则不生效，行为与改前一致。
5. **切开后的新半配对**：切口线组上的非 pass 配对或缺端配对不占用 SW 端口；同端口的 SW 线路记录完整配对时顶替之（`displaced_provisional`）。这是对“符号另一端无文字候选”的通用处理，不依赖块名。

## 11. 遗留风险

1. **跨元件的文字候选配对（discard）**：文字候选的搜索半径仍会穿过元件（例：p026 S0008 的 `1515 ↔ 1527` 经过 5n 两引脚符号）。这些配对为 discard，不影响覆盖与 issue，但会增加配对表的噪声（全量新增 discard 约 4420 条，多为 ordinary_pair）。根因在 `candidates.py` 的端点文字搜索，不在线组层，未改。
2. **新增 review 缺侧 issue**：2 条（p040 PW0054、PW0060）。主线程复核判为误报（装置内部线圈连接），本轮未能按 SW 元数据消除，原因见第 13 节；需主线程决定是否批准几何归属原则。
3. **覆盖口径**：未剔除口径净减 75 个消费端口（第 6.3 节），剔除装置内部口径净增。两者的分母变化需要在报告中说明。
4. **标记间距的阈值**：贴住判据沿用 SW 端口的 1.0 容差，间隙宽 ≥ 2.0；`body_width_below_min` 的 2.0 为经验阈值（与 DEV-INT 的 `SPLIT_MIN_BODY_WIDTH` 一致）。
5. **未实现的形态**：框线穿越（T7）、T 接止于间隙（T8）、空白端（T11）未做独立判据。

## 12. 文件

- 代码：见第 1 节。
- 测试：`tests/unit/test_line_groups_symbol_breaks.py`（15 项）；全量 `python -m pytest tests/unit -q`：**2059 passed, 1 skipped**。
- 产物：
  - `.tmp/superworks_round23_full`（全量回放，77 项目，最终代码）；快照 `.planning/superworks-adapter/round23_full_src`；
  - `findings/sw_topology_unknown.parquet`（每个项目，30 行合计）；`summary.json` 的 `topology` 段。
- `png/`：`WB_p026_S0008_before_after.png`、`WB_p026_S0008_zoom_1431_1521.png`、`WB_p040_S0005_missing_side.png`、`WB_pass_sample_01..05.png`（共 8 张）。
- `tools/`：`wb_compare.py`（对比）、`wb_pairs_breakdown.py`（分类）、`wb_removed_pass.py`（消失配对核对）、`wb_sample_pass.py`（抽样渲染）、`wb_render_region.py`（区域渲染）、`wb_render_p026.py`（p026 单页渲染）、`wb_timing.py` / `wb_time_one.py` / `wb_time8.sh`（耗时）、`wb_lost_ports.py`（丢失端口）、`diag_consumed.py`（准入时占用端口的配对插桩）。
- `tools/results/`：全部对比与核对的 JSON 与全量 pytest 输出。

## 13. 第 24 轮：主线程复核（p040 误报、走线规则、PW0256 顶替）（结论 13.1 已由第 14 节取代）

### 13.1 主线程的结论与本轮实际结果

主线程判定 p040 的两条 PW0054、PW0060（612 ↔ 空）为误报：2n612 的内侧导线经竖线接到 611 线圈的右端，属于装置内部连接，应按 DEV-INT 口径静默丢弃（`discard_reason=device_internal`），不报缺端。要求：通用修复（不按项目或值特判），复用 `superworks_device_internal` 的公共判定，并检查全量中同类情况。

本轮实际结果：

- 实现了通用的**走线规则**（`superworks_wire_walk.py` + `_discard_walked_half_pairs`）：切分线组上的一侧配对，若其装置端子一侧能沿线网络（拐角、T 接、分支相接，不跨符号本体）从开口端走到的所有符号引脚都经 `device_internal_verdict` 判为 `DEVICE_INTERNAL`（且至少到达一个），则丢弃为 `device_internal`（rule `wire_walk_internal`）。到达非内部引脚（另一端子、异标签元件、无标签元件、其它符号）则保留。
- **p040 的两条配对未被丢弃，issue 未消除。** 原因（逐条追踪，`tools/wb_walk_trace.py`）：
  - PW0054 与 PW0060 的走线从缺端 (200,190)、(200,230) 出发，各只走过 2 段（2n612 的 L0098 与竖线 L0097），终点 (200,200) 处没有任何 SW 标记：线圈右端不是 SW 端口，也不是登记的未登记块引脚。走线找不到可判定的目标，规则不触发（`walk_kept:nothing_reached`）。
  - 与线圈对应的 SW 内部元件 EFAA（`SYMB2_M_PWF229`，两个实例 `/11EFF/EFAA` 与 `/15D1C/EFAA`）的元数据为 `LD_SYMB2_LABEL = 0`，标签未解析（`missing_label_reference`）。即使把块内线纳入走线，`device_internal_verdict` 也会因 `other_label_unresolved` 保留。
  - 因此按 SW 元数据，无法证明该线圈属于装置 2n。按"不得按值特判、依据 SW 元数据"的要求，本轮**不把它判为装置内部**。如要消除该 issue，需要主线程决定一条新原则（例如：标签未解析的内部线圈，经同框（图中 18086 方框）内的装置端子相连时归入该端子的装置）。该原则依赖几何归属而非 SW 元数据，需单独批准。
- 走线规则在 12 个项目中共丢弃 27 条缺端配对（全部为"只到达同标签内部引脚"：p040 6、p000 1、p001 1、p022 4、p044 2、p061 7、p074 6），保留 20 条（14 条到达空，4 条到达异标签引脚，2 条到达另一装置端子）。逐条抽查 6 例（p040 的 PW0106、PW0128、PW0143、PW0551、PW0604；p000 的 PW0018）：到达的都是同标签（1n/2n）的未登记块引脚或内部元件，判定与 DEV-INT 的既有 G1P 口径一致。这 27 条不影响 issue。

### 13.2 p000 的 PW0256 被什么顶替

- 基线 PW0256：4P1D2 ↔ 12（review，wire_component_mapping，score 0.874）。`12` 是相邻续线 GW0257 的左端（距离 1.25，且已被 PW0257 占用），本线真实右端为 FZJ1-11（FZJ111），与 Z-6 的判定一致（`loop/Z-6/README.md` 第 24 行）。
- 改后同一端口 4P1D2 由 SW 线路记录给出完整配对：`PSW0f5f4b611b6c016f`，4P1D2 ↔ FZJ1-11（review，wire_component_mapping）。准入阶段的 `displaced_provisional` 计数为 p000 5 条。
- 因此 PW0256 的 `R-PAIR-LOW-CONFIDENCE` issue 消失是正确的（低置信的裸数字配对被正确的线路配对取代）。

### 13.3 12 项目回放验证（最终代码，`.tmp/loop_fix`）

项目：p040 p000 p001 p003 p022 p026 p044 p051 p061 p071 p074 p075。

| 项目 | round22 issues | 修复后 issues | 新增 | 消失 |
|---|---:|---:|---|---|
| p040 | 1 | 3 | R-PAIR-MISSING-SIDE ×2（PW0054、PW0060，未消除） | 0 |
| p000 | 2 | 1 | 0 | R-PAIR-LOW-CONFIDENCE（PW0256，见 13.2） |
| p001 p003 p026 p051 p061 p074 | 0 | 0 | 0 | 0 |
| p022 p044 | 1 | 1 | 0 | 0 |
| p071 | 3 | 3 | 0 | 0 |
| p075 | 4 | 4 | 0 | 0 |

- 10 项目（p001 p003 p022 p026 p044 p051 p061 p071 p074 p075）issues 与 round22 逐条相同。
- p040 未达到"与 round22 逐条相同"：两条 612 缺端 issue 仍在（见 13.1）。
- 走线规则在上述 12 项目丢弃 27 条 review 缺端配对（p040 6、p000 1、p001 1、p022 4、p044 2、p061 7、p074 6），没有带来 issue 变化。

### 13.4 全量预计影响（未重跑全量）

- round23 全量回放用的是修复前代码（第 13 轮之前的 `round23_full_src`）。`round23_full_src` 已同步为本轮最终代码；全量结果 `.tmp/superworks_round23_full` 仍为修复前结果。
- 全量非 discard 的单侧配对由 21340 增至 21671（+331），这是切分新增的单侧配对，即走线规则可能处理的上限。按 12 项目的比例，预计走线规则会丢弃其中一部分（12 项目为 27 条），这些变化是 discard 层面的，不改变 issue。
- 预计 issue：相对 round22，全量仅 p000 的 PW0256 一条消失（round23 已包含），p040 的两条 612 仍在。全量其它 issue 预计不变（12 项目验证）。
- 若需要全量数字，需用 `round23_full_src` 重跑 77 项目（约 45 分钟）。本轮按主线程要求未做。

### 13.5 单元测试

- `tests/unit/test_superworks_wire_walk.py`（7 项）：拐角与 T 接、符号间隙不穿越、孤立端、块内线排除、半配对在到达同装置内部引脚时丢弃、异标签保留、无到达保留、非切分线组不遍历。
- 全量 `python -m pytest tests/unit -q`：**2066 passed, 1 skipped**。

## 14. 第 25 轮：框内装置内部线圈的判定（主线程批准的原则）

### 14.1 原则与实现

主线程批准：标签未解析的 SW 内部元件/线圈引脚（或未登记块引脚），若位于唯一的装置框内，且装置端子的走线全部在框内、途中不到达外部端子、其他装置端子或框外对象，则判为装置内部连接，丢弃（rule `wire_walk_internal_frame`）。约束：不得按项目、值或块名特判。

- **走线**（`superworks_wire_walk.walk_wire`）：从缺端开口处出发，沿模型线与块内可见 LINE 图元（元件自身引线，来自 `primitive_segments` 的世界坐标，经 pipeline 传入 `block_rows`）遍历，经拐角、T 接、分支相接；**遇到 SW 标记（TERMPOINT）即停止**，标记即为走线的端点，不穿过端子本体或元件引脚。
- **框识别**（`superworks_wire_walk.rectangles` / `device_frame`）：闭合的轴向矩形（四边线相接，最短边 ≥ 10，边线 ≥ 5）；必须包含该装置端子的全部端口点；框上（内）或紧邻框边（Chebyshev 距离 ≤ 4.0）有一个文字，规范化后与该端子的装置标签**精确相等**（大小写不敏感）；框必须唯一，找不到唯一框 → 规则不适用（`no_unique_frame`）。
- **判定**（`_discard_walked_half_pairs`）：到达的每个标记必须是：
  - 标签已解析的，`device_internal_verdict` 为 `DEVICE_INTERNAL`（rule `wire_walk_internal`，即第 24 轮的规则，本轮保持不变）；
  - 标签未解析的 SW 内部元件/线圈，或未登记块引脚：仅在唯一框内可接受（rule `wire_walk_internal_frame`）。
  - 走线的全部端点与到达的标记都必须在框内（否则 `walk_leaves_frame` / `reached_outside_frame`）。
  - 任何到达的端子（`端子`、`装置端子`）、其他类别、或异标签引脚 → 保持原状（`other_end_category:*`、`other_label_differs`）。

### 14.2 p040：两条 612 缺端消失

- PW0054（2n612）与 PW0060（1n612）由 `wire_walk_internal_frame` 丢弃。框分别为 (145,185)-(205,215)（标签 "2n"，距下边 3.45）与 (145,225)-(205,255)（标签 "1n"）。
- 走线：PW0054 从 (200,190) 经 L0097 到 (200,200)，再经 EFAA 元件的块内引线（165→200）到达 EFAA 口 2（标签未解析，`LD_SYMB2_LABEL = 0`）。PW0060 同理，到达 EFAA 另一实例。
- 块内引线在改前的 `lines` 中不存在，它来自 `primitive_segments`（`A$C13797B25[15D1C]` 的 165→200 与 150→155）。这是本轮加入块内 LINE 图元的原因。
- 复核后 p040 的 issues 与 round22 逐条相同（仅保留 `R-MANY-TO-ONE` S0021 1ZK-3），两条 612 缺端 issue 消失。

### 14.3 验证：11 项目（p000 + 10 项目）

`.tmp/r25`，代码同 `round23_full_src` 最终版。

| 项目 | round22 issues | 本轮 issues | 变化 |
|---|---:|---:|---|
| p000 | 2 | 1 | 消失 R-PAIR-LOW-CONFIDENCE（PW0256，见第 13.2 节） |
| p001 p003 p026 p051 p061 p074 | 0 | 0 | 无 |
| p022 p044 | 1 | 1 | 无（逐条相同） |
| p071 | 3 | 3 | 无 |
| p075 | 4 | 4 | 无 |

10 项目（p001 p003 p022 p026 p044 p051 p061 p071 p074 p075）issues 与 round22 逐条相同。

### 14.4 全量 77 项目：最终代码重跑（`.tmp/superworks_round23_full`，`round23_full_src` 同为最终代码）

对比：`tools/wb_compare.py`，结果 `tools/results/wb_full_r25.json`，按 `rule+sheet+title+severity+message`（去掉编号）比较。

| 指标 | round22 | 本轮 |
|---|---:|---:|
| issues | 41 | 40（消失 1：p000 的 PW0256 低置信问题；新增 0） |
| 线组 | 131163 | 125318 |
| pairs | 172529（新增 7263，删除 1096） | 178696 |
| 严格覆盖（不剔除） | 52039 / 82680 = 62.94% | 51964 / 82680 = 62.85% |
| 含延续（不剔除） | 59149 / 82680 = 71.54% | 59050 / 82680 = 71.42% |
| 严格（剔除装置内部） | 52039 / 64013 = 81.29% | 51964 / 63109 = 82.34% |
| 含延续（剔除装置内部） | 53668 / 64013 = 83.84% | 53499 / 63109 = 84.77% |

- 走线丢弃（全量）：229 条 review 缺端配对 → discard，其中 18 条为框规则（`walk_discarded_frame:review`）。其余 211 条为既有的同标签规则。
- 保留（全量）：`nothing_reached` 58、`other_label_differs` 11、`other_end_category:装置端子` 12、`other_end_category:端子` 6、`no_unique_frame` 2。
- 剔除装置内部口径的分母由 64013 变为 63109，因为装置内部端口集合随走线丢弃变化。

### 14.5 框规则的影响数与抽样（18 条，全部目视）

- 影响数（全量）：18 条配对被框规则丢弃，全部为 review 状态的单侧配对（semantic_mapping 或 ordinary_pair），都在切分线组上。
- 抽样：全部 18 条（`tools/wb_sample_frame.py`，种子 20261011；图 `png/WB_frame_sample_01..03.png`，每张 6 例）。
  - 框内为装置线圈回路（"直流输出 / DC output" 框内的线圈与 1-2n、2n、1n 端子）：p039（610、611、612 等）、p040（612、611）。
  - 框内为 DC/DC 模块（SW 登记为内部元件、标签未解析，框上为本装置标签 4n 或 ZSZ-812E 模块名）：p005、p006、p067。
  - 未发现误判形态：框内没有外部端子排，框内的装置标签与端子标签精确相等（例：p039 端子标签 "1-2n"，框底边下 3.45 的 "1-2n" 正确采用；相邻框的 "3-2n" 不相等，未误用）。
  - 残留：DC/DC 模块被规则视为装置内部，依据是 SW 的 `内部元件` 分类与框标签。若模块应属外部，需要主线程另行判断。
- 逐例追踪数据：`tools/wb_frame_trace.py`（框、标签、到达的标记）。

### 14.6 新图纸的泛化说明

- 判据只用：闭合线框（几何）、框内或紧邻框边的装置标签文字（文字，精确相等）、SW 标记的类别与标签解析状态（元数据）、块内可见线（图元几何）。不使用块名、项目名、句柄、取值或页码。
- 同类新图纸：只要装置框由闭合线框画出、框上有装置标签、元件或线圈的引脚落在框内，即按同一规则处理；框非唯一、标签不精确相等、走线离开框、途中有外部端子或其他装置端子，均保持原状并继续报出。
- 不适用的情形（保持原状，需人工）：无闭合框的图（如只有标签的端子排）、框上无装置标签、同一框内有两个不同装置标签的端子。
- 框内的 DC/DC 模块等 SW 登记的内部元件会被视为装置内部（见 14.5 残留）。

### 14.7 单元测试

- `tests/unit/test_superworks_wire_walk.py`（11 项）：走线（拐角、T 接、不跨符号、块内线排除）、框识别（闭合 / 不闭合）、框唯一性与标签精确匹配、未解析元件在唯一框内丢弃、框外或走线离框保留。
- 全量 `python -m pytest tests/unit -q`：**2070 passed, 1 skipped**。

### 14.8 文件

- 代码：`src/dwg_audit/audit/superworks_wire_walk.py`（新增，框与走线）、`src/dwg_audit/audit/superworks_extractor.py`（`_discard_walked_half_pairs`，框规则与标签判定）、`src/dwg_audit/pipeline.py`（`_block_line_rows`，传入块内 LINE 图元与文字）。
- 工具：`tools/wb_frame_trace.py`、`tools/wb_sample_frame.py`、`tools/wb_walk_trace.py`；结果 `tools/results/wb_full_r25.json`。
- 快照：`.planning/superworks-adapter/round23_full_src` 为最终代码；全量结果 `.tmp/superworks_round23_full` 为最终代码的结果。

