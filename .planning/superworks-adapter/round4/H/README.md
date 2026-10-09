# 第四轮 H：R-DUPLICATE-PAIR / R-ONE-TO-MANY / R-MANY-TO-ONE 等复核（只读）

范围：只读。未改 src/，未提交，未删除，未全量回放。离线结果用 round4/G 的 harness 调用 rules.py 真实谓词（monkeypatch 仅在进程内生效）。明细见 details.json，分桶见 m2o_buckets.json，脚本与离线输出见 tools/ 与 *.json。数据：r3 = .tmp/superworks_round3_full，r4 = .tmp/superworks_round4_full，基线 = .tmp/superworks_baseline_timed。

## 0. 结论一览

| 规则 | 基线 | r3 | r4 | r4 判定 | 修复后预计 |
|---|---|---|---|---|---|
| R-DUPLICATE-PAIR | 0 | 1 | 68 | 68 条误报（G3） | 0 |
| R-ONE-TO-MANY | 0 | 11 | 68 | 64 误报（生产端命名）；4 待复核（存量） | 4 |
| R-MANY-TO-ONE | 13 | 643 | 110 | 基线 13 真实；其余 97 已见于 r3，约 44 倾向误报 | 66 |
| R-CROSS-PAGE-CONFLICT | 3 | 23 | 3 | 与基线逐条相同 | 3 |
| R-SUPERWORKS-CONFLICT | 0 | 21 | 18 | 未逐条判定（第 5 节） | 18 |

## 1. R-DUPLICATE-PAIR（68 条）

- 新增性：r3 仅 1 条（p006 8YD1→8n801，r4 中消失，见第 4 节末注）；r4 的 68 条全部新增。
- 共同模式（68/68）：每组恰 2 个 pair，一条 inline_two_port_component（原理图），一条 superworks_connect_line_port（SW 元件图连接线）。同一物理端口在两张图各描述一次，两条位于不同 sheet。
- 与生产端改动（F1/F3/F4/F5）无关：同组 pair 在 r3/r4 的 evidence 只多了 F4d 的 pin_resolution_method，端口、句柄、视图键相同。
- 根因（G3）：rules.py:2140 让 SW 连接线在 `_authoritative_schematic_inline_component_identity` 中返回身份三元组。rules.py:1878 `_is_authoritative_schematic_kk_component_duplicate` 要求“恰好 1 个 schematic 身份且等于 component-diagram 身份”，而该 SW pair 同时被计为 schematic 身份，计数变为 2，豁免失效。rules.py:1452 `_run_duplicate_pair` 因此报出。
- 证据（离线，同一规则代码）：r4 数据 G3 还原后 dup = 0；r3 数据全部 G 还原后 dup = 1、o2m = 11，与 r3 审计逐数一致，说明 r3 审计未包含 G 改动；r3 数据当前规则下 dup = 69。
- 判定：误报（同一端口两视图应豁免）。
- 修复：rules.py:1878 与 1910 两函数中，schematic 身份只取 inline 原理图 pair（排除 component_submode == superworks_connect_line_port），SW 身份只计入 component-diagram 角色。2089 backplate 路径不变。通用，无项目或值特判。
- 预计：68 → 0（离线验证：dup 0，o2m 68、m2o 110、cross 不变）。副作用只出现在 r3 形态数据：m2o 376 → 414（G3 对“SW 连接线 + table_mapping”组的偶然豁免被收回，例 p000 1KD5）；r4 数据无此变化。

## 2. R-ONE-TO-MANY（68 条）

- 新增性：r4 新增 64 条（全部 p075 8000_9000_-）；存量 4 条（p043/p044，r3 已有）。r3 的 11 条中 7 条在 r4 消失（p040 6 条、p061 1 条），均为同一 SW 连接线上的逗号拆分（如 "2FD1,2n317"、"1-21CD6,1-21ZK-9"），由 G1/G2 启用的 `_is_authoritative_comma_component_mapping_group`（rules.py:3256）豁免，属合法消除。
- 64 条模式：每个左值（如 1-26n-B码1+）对应 3 个右值（1-26TD1/49/97）。三个端口是同一实例 /3214C（或 /3205D）的插槽端口 401/501/601。同一端口在 wire_component_mapping 中仍为 "1-26n401"（正确），只有 component_mapping 被改名。
- 根因（生产端，F4a 锚点 + 标签 nearest 命名）：用 p075 F0014 缓存 DXF 复算实例 3214C。三枚“B码1+”文字锚点为 (157.5,235)、(197.5,235)、(237.5,235)，各距 401/501/601 端口 7.0，且各为独立文字实体（31DED/31EF8/32078）。候选筛选条件为距离 <= 3 倍文字高度 = 9.0（superworks_semantics.py:166-172）。r3 用插入点，距离约 10.9，未入候选，回落端口号；F4a 改用对齐点后距离 7.0 入候选，三端口同名。三列文字内容相同，标签值不是端口身份。
- F4b 共享标签豁免（superworks_semantics.py:185-190）不是此例的触发条件（三枚文字各只被一个端口采纳）。缺少的约束是：同一定义实例内，nearest 标签值须唯一。
- 判定：误报（生产端身份坍缩；规则的一对多判定本身正确）。
- 修复（superworks_semantics.py `_definition_ports`，nearest 选定后，约 L192-205）：若同一定义实例内 >=2 个端口采纳了同一规范化标签值且来自不同文字实体，则撤销这些 nearest 采纳，回落端口号（与 r3 一致）。保留“同一文字实体被多端口共用”的豁免。
- 预计：64 → 0（代理：r3 命名的同项目数据经当前规则离线计算，p075 o2m = 0）。存量 4 条待复核。
- 影响面：共享标签命名的 pair 共 10,102 条（70 项目）。其中仅 192 条（均在 p075）的 evidence.source 存在，进入规则图；其余 9,910 条因 source 缺失被 `_high_confidence_source_eligible` 排除。修复须先于补齐 source（G 轮偏离 3），否则会引入大量同类误报。
- 存量 4 条（p043/p044 S0020）：KK 端口 "4" 挂在同一水平线上两个候选端子（1-21n715 / 1-21n717），与 r3 相同，待复核，非回归。

## 3. R-MANY-TO-ONE（110 条，基线 13）

- 基线 13 条全部保留：p015/p021/p050/p071/p075 GND；p038/p049 KD26；p039 1-2GD3、1-2n221、3-2n221、KD1、KD6；p040 1ZK-3。
- 其余 97 条的 (项目, 右值) 键全部已在 r3 审计中出现：r4 相对 r3 无新增 m2o；r3 的 533 个键在 r4 消失。
- 分桶（round3_composition 键，在 parquet 上重算，13 桶，合计 97）：

| 桶 | 条数 | 项目 | 形态 | 可能原因 | 判定 |
|---|---|---|---|---|---|
| 1 | 51 | p074 48；p014/041/042 各 1 | 同 sheet 两个 terminal_header_table 同指右值 1-25U2D2 | 相邻两表头各有同名、不同位置的中间列端子（T3351@(41,216)、T3441@(71,96)）；rules.py:3941 因 text_id 与坐标不唯一返回 None | 合法相邻列（倾向）；p041/042 的 GND 按基线 GND 类待复核 |
| 2 | 15 | p027-p034 | SW 线网范围 "1-7UD20~21" 与表格成员 "1-7UD21" 同指 1U1D4 | 范围端不覆盖成员：`_bridge_covered_terminal_identities`（rules.py:95）只作用于 bridge claim，与 rules.py:1244-1245 注释“范围端不构成 m2o”不一致 | 误报 |
| 3 | 10 | p016-p021 | 1UD4 被 4 个视图以不同逻辑名描述：strip_lattice 1n2006、SW 连接线 TF-8（TSB-14 端口 8）、表格 UD4、线网 UD4 | 跨视图汇聚但名称不同；`_is_authoritative_cross_view_group`（rules.py:882）要求同一 (左,右) 在两视图重复 | 待复核 |
| 4 | 5 | p022-p024 | 背板 1n1423 + 表格 1-7UD21 + 线网范围 1-7UD20~21 同指 1U1D4 | 范围问题（同桶 2）加背板独立来源 | 部分误报，余待复核 |
| 5 | 4 | p061 | 背板 1-21n/BI2-20 与线网 1-21GD17 同指 1-21QD77 | 两个独立来源指向同一端子 | 待复核（倾向真实） |

- 其余 8 桶共 12 条：仅表格、两表头 3 条（p039/p043/p044）；terminal_header 共享端点 2 条（p038/p049，代码已标 review）；三视图 2 条（p040）；单条 5 条（p009、p014、p024、p057 x2）。
- 离线候选修复（基线 13/13 保留）：(a) 范围覆盖推广到所有 pair（rules.py:95 去掉 bridge 限制）-> 96 条；(b) 相邻列同名端子放宽（rules.py:3941 允许“两 pair 分列左右、行号相同、表头前缀不同”）-> 80 条；(a)+(b) -> 66 条。

## 4. R-CROSS-PAGE-CONFLICT（3 条）

- r4 与基线逐条相同：p050 1n/NCK305-5 -> 1CD3；p065 NCK305-1@c0 -> 1C1D1；p066 NCK305-5@c0 -> 1C2D1。
- r3 的 20 条非基线项在 r4 消失（G 轮 cross 规则豁免所致，见 G/README 第 5 节，未在本轮逐条归因）。
- 注（p006 dup，F1 引起）：r3 唯一的 dup（p006 8YD1->8n801）在 r4 消失。原因：r3 的 PSW3bb 行左右两侧同时写入 T5280，不满足单侧契约；F1 改为单侧写入后满足 `_is_authoritative_table_mapping_group`（rules.py:1654-1712），被豁免。两行 right_text_id 仍不同（T5280/T5281），严格说需人工确认，未复核。

## 5. R-SUPERWORKS-CONFLICT（r4 18 条，未逐条判定）

- 原因码：competing_physical_port_identities 10；competing_physical_port_instances 7；stale_label_reference 1。
- identities（10）：p022/p023/p028/p029/p030/p032/p033 为 F0010/F0011 /2008A 与 /200D2；p024/p031/p034 为 F0010/F0011 /1FB74 与 /1FBBC。
- instances（7）：p000 F0011 /19832 与 /19833；p037 F0011 /33ABE 与 /33BFD；p064 F0010 /2008A 与 /200D2；p071 F0004 /25271 与 /25FBA、/2525E 与 /25FA7、/2525F 与 /25FA8；p072 F0013 /33012 与 /33151。
- stale_label（1）：p020 F0017 /1285C:/1285C:150E9:2。

## 6. 修复优先级与风险

1. 规则，最小，已离线验证：rules.py:1878/1910 的 schematic 身份排除 SW 连接线，dup 68 -> 0。
2. 生产端，需重放验证：superworks_semantics.py `_definition_ports` 加标签唯一性，o2m 64 -> 0。会改名 10,102 条 pair，需对 70 个项目重跑，并先于 source 补齐。
3. 规则：范围覆盖推广（rules.py:95）与相邻列放宽（rules.py:3941），m2o 110 -> 66。相邻列放宽须抽检 p074 类样本，GND 类不纳入。

## 7. 限制

- 所有“预计”均为离线规则重算或代理，未重放。修复 2 的 64 -> 0 依据 r3 命名代理。
- m2o 桶 3、5（共 14 条）与存量 o2m 4 条未作最终判定。
- 未验证 DC 类共享标签在本轮数据中的实际形态（F4b 注释提及，本轮未见样本）。
