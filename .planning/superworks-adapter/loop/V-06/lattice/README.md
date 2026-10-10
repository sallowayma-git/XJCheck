# V-06 lattice：第六轮删除的 425 条 terminal_strip_lattice 映射核验（只读）

范围：pairs.parquet 中 component_mapping 且 status=pass；r5 20,943 / r6 28,454（与 V-06 一致）。删除集 425 行，分布于 11 个 sheet（p016–p021）。未改 src，未做 git 写操作（仅只读 git status），未全量回放。

## 1. 分类（425 条）
| 类别 | 条数 |
|---|---|
| 有等价替代 | 425 |
| 有替代但值不同 | 0 |
| 无替代 | 0 |

判定条件（全部满足）：同项目同 sheet；同端子排实例；SW 逻辑端点引脚号等于原行 lpin/rpin；SW 行 row_y 与原行相同（±0.05）；SW 外部端点去除 * & 空格后与原左/右值逐字相同。每条候选唯一。

替代形态：每条由两个半行替代，其中 425 个半行为 r6 新增（奇数引脚侧），425 个半行在 r5 已存在（偶数引脚侧，设备端）。设备-设备型 89 条（如 1I3D7 与 1I3D4，无导线）。

## 2. 值形式变化（非值不同）
- r5 原行为干净值：左 1n2107、右 1I2D1。
- r6 半行为：TF2-1 与 "* 1n2107"；TF2-2 与 "1I2D1 *"。
- 成因：lattice 路径经 component_diagrams.py:381 去除首尾 &、*；SW 路径（superworks_extractor.py:696、782）仅 strip("&")，保留 *。r5 的设备半行已带 *，r6 只剩带星形式。

## 3. 截图抽样（10 条，seed 20261010，每页至多 1 条）
png/S01–S10：左为 r5 lattice（红圈），右为 r6 SW 半行（蓝框）。
判定：10/10 为“两者都对（仅表示不同）”。红圈与蓝框落在同一端子排同一对引脚，两端文字均在窗口内。S07 为设备-设备型，两者都对。
限制：依据图面几何与文字，未在图上验证端子内部导通（同行两引脚视为同一端子，为两侧生产者共同假设）。

## 4. supersession 台账
- 已记录：r5 账本 425 条（old_pair=lattice，category B，reason=validated_superworks_replacement）；r6 账本 850 条（每条 lattice 对应 2 条，各指向一个半行）。
- 不足：reason 不区分新增半行与已存在半行，也不记录干净值到带星值的形式变化。

## 5. 审计 issue 影响
- 11 个 lattice sheet：issue r5 0、r6 0；pair 计数与 kind 计数不变。
- 6 个项目合计：r5 2 条，r6 1 条。p020 I0001 R-SUPERWORKS-CONFLICT（S0017，非 lattice sheet）消失，成因为 superworks_semantics.py 的 label_far_from_symbol 分支（r5 到 r6 代码差异），与删除无关。
- p050 新增 R-MANY-TO-ONE（I0013、I0014）与 lattice 无关：p050 在 r5 无 lattice 行，系 S0026、S0027 新增 SW 连接线引起。
- 规则输入变化（输出未变，有潜在风险）：左值聚合的跨 sheet 多右值组，lattice 行所在组 r5 为 201、r6 为 91，110 组失去跨页结构（wire 由左列移至右列）；r5 这 201 组未产生任何 issue。
- 背板豁免 rules.py:1882 要求 submode=terminal_strip_lattice（调用点 rules.py:742）。r5 有 104 行（104 个 project+left）满足其结构前提（同左值的 backplate_virtual_table 表格对在另一 sheet；完整豁免条件未逐项验证），r6 该豁免恒为 False。当前这些组已不跨 sheet，故无输出变化，属潜在回归。

## 6. 召回损失
- 连接层面：无。425 条连接在 r6 均仍有两端半行表示，r5 无连接消失。
- 输入形态层面：有，需修复（见第 7 节）。

## 7. 需修复模式与代码定位（建议，未改 src）
1. 值形式：SW 路径应与 lattice 一致去除 * 装饰，定位 superworks_extractor.py:696、782，参照 component_diagrams.py:381。会改变 r6 其它 SW 行的值，需回归。
2. 背板豁免：rules.py:1882 应接受 SW 端子排引脚证据（superworks_connect_line_port 且带 terminal_strip_instance、row_y、pin）。
3. 回归用例：p018 S0021/S0022、p020 S0026 共 104 组。

未覆盖：2 条 xjdz_structural_terminal、4 条 ZKK（V-06 已判定）、48 条 GND 值改变，不在本次 425 条范围。
明细：details.json（425 条，含 r5 坐标与 evidence 字段、两半行 id 与是否 r5 已存在、账本条数）。截图：png/S01–S10。
