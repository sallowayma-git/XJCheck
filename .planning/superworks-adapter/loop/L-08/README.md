# L-08 R-SUPERWORKS-CONFLICT 核实（第四轮全量回放）

数据：`.tmp\superworks_round4_full`，18 条 `R-SUPERWORKS-CONFLICT`。只读核实，未改 src/，未全量回放。
方法：ezdxf 读取各项目 `cache\converted_dxf` 中的 INSERT，取 TERMPOINT 世界坐标（virtual_entities，已含镜像/旋转）、XDATA 标签及双向引用。两符号端口坐标在 0.6 内重合即判"叠放"。

## 结论
- 18 条中 **17 条为真实绘图缺陷**：同一接线端被两个 INSERT 叠放占用，分 6 组。
- **1 条误报**：p020 `stale_label_reference`，根因是距离阈值启发式。
- 17 条的两符号 TERMPOINT 坐标完全相同（间距 0.00，远小于 0.6），且同一批 CONNECT 导线端同时落在两符号端口上。

## 逐组结论
| 组 | 项目（文件 / sheet） | 符号句柄 A / B | 原因码 | 标签 A / B | 判定 | 依据 |
|---|---|---|---|---|---|---|
| G1 | p022,p023,p028,p029,p030,p032,p033（F0010/F0011 S0010/S0011） | 2008A / 200D2 | identities (7) | 1QD2 / 1QD3 | 真实缺陷 | 同块 SYMB2_M_PWF243 于 (250,245) rot 270；端口 1-3 坐标相同；两标签 MTEXT 同点重叠；导线 2008C/200D6/200D8 同接两符号 |
| G2 | p064（F0010 S0010） | 2008A / 200D2 | instances (1) | 1QD2 / 无（LD_SYMB2_LABEL=0） | 真实缺陷（无标签幽灵副本） | 同 G1 几何；200D2 端口无身份 |
| G3 | p024,p031,p034（F0010/F0011） | 1FB74 / 1FBBC | identities (3) | 1QD2 / 1QD3 | 真实缺陷 | 同块于 (244.96,247.58)；标签 1FB75/1FBBD 同点；导线 1FB76/1FBC0/1FBC2 同接 |
| G4 | p000（F0011 S0011 操作回路图3） | 19832 / 19833 | instances (1) | 无 / 1CD2 | 真实缺陷 | 同块 SYMB2_M_PWF231 于 (115,205)；导线 19837/1983B 同接 |
| G5 | p037（F0011 S0011）、p072（F0013 S0013） | 33ABE / 33BFD；33012 / 33151 | instances (2) | 外层 4n 相同；内层 1TBJc1 / 无 | 真实缺陷（中等置信） | 内部元件 SYMB2_M_PWF194 于 (395,70.007) rot 90；4n 组 138 成员中仅此处两符号同点；4 条导线同接两符号 |
| G6 | p071 三对（F0004 S0004） | 2525E/25FA7；2525F/25FA8；25271/25FBA | instances (3) | 一有一无（1-JD2/无；无/1-JD7；1-JD20/无） | 真实缺陷 | 各对同块同点；各对导线端 (22CA7,25255,2694B 等) 同接 |
| FP | p020（F0017 S0017 失灵启动输入接点2） | 1285C 端口2 | stale_label_reference (1) | 1C12D6 于 1285D，位置 (-130.9,484.8) | **误报** | 1285D 双向引用成立（1005=1285C）且解析成功，是该端子唯一身份文字；图框外（sheet x 0-415, y 0-279）；距离 299.3 仅因 >30 阈值触发 |

计数：identities 10 = G1 7 + G3 3；instances 7 = G2 1 + G4 1 + G5 2 + G6 3；stale 1 = p020。

## 代码定位
- superworks_extractor.py:48-61 `_coincident_ports`：接触间距 ≤ 容差即判竞争，17 条判据正确。
- :167-187 `_endpoint`：同一线端身份不同记 identities（:181）；身份相同、符号不同记 instances（:187）。
- :526-535 线端找端口（直接命中或 WireNetwork 可达）。
- :829-867 `build_superworks_issues`：对象 ID 取竞争符号对（:849）。
- superworks_semantics.py:317-318：端子标签距离 >30 即记 stale_label_reference，未用已算出的双向/唯一性结果（:305、:311）。
- superworks_extractor.py:16：stale_label_reference 属 _TRUE_CONFLICTS，因此误报进入 R-SUPERWORKS-CONFLICT。

## 误报 p020 的通用修复方案（不改代码）
1. 距离超阈值但 reciprocal_ok 且 handle_resolved 的标签，改记为 `label_far_from_symbol`（布局观察），不加入 _TRUE_CONFLICTS，仅进覆盖证据。
2. stale 只在以下情况保留：标签不双向；标签句柄不可解析；同 identity 在同页存在更近的标签。
3. 阈值改为相对量（符号包围盒或端口间距的倍数），并先判断标签是否在图框内；p020 的标签在图框外，应归为布局问题。
4. 回归用例：双向、解析成功、距离 300 的端子标签不得产生 R-SUPERWORKS-CONFLICT；非双向的远距标签仍须产生。

## 附注
- "同一模板页"口径：各项目源 DWG 的 sha256 不同，但转换后 DXF 中 INSERT 句柄、坐标与 XDATA 完全一致，据此合并为 G1、G3。修模板可消除这 10 条。
- G5 中等置信：内部元件无终端身份，依据为同点重复、同组唯一性例外和 4 导线共接。建议人工确认 33BFD 是否为残留副本。
- PNG（ezdxf drawing + matplotlib，COLOR_SWAP_BW；红实线=第一符号，蓝虚线=第二符号，绿=标签）：
  L-08_G1_p022_stack_2008A_200D2.png；L-08_G2_p064_stack_2008A_200D2_unlabelled.png；L-08_G3_p024_stack_1FB74_1FBBC.png；L-08_G4_p000_stack_19832_19833.png；L-08_G5_p037_stack_33ABE_33BFD_internal.png；L-08_G6_p071_three_stacks.png
- 中间数据在 scratchpad（l08_*.py/pkl/json），未写入仓库。
