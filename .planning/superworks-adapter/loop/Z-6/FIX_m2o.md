# Z-6 m2o 修复说明：R-MANY-TO-ONE 同网豁免（只减误报）

范围：只改 `src/dwg_audit/audit/rules.py`，新增 `tests/unit/test_superworks_loop_z6_m2o.py`。未碰 candidates.py，未做 git 操作，未全量回放。离线数据为 `.tmp/superworks_round11_full`，工具与输出在 scratchpad（未入仓）。

## 1. 结论

| 项 | 结果 |
|---|---|
| R-MANY-TO-ONE（离线，第十一轮 pairs） | 14 -> 12 |
| 消除 | p040 1GD1、p040 2GD1（2 条） |
| 保留 | GND 9 条；p039 1-2n221、3-2n221（2 条，未达预期，见 §4）；p040 1ZK-3（1 条） |
| R-CROSS-PAGE-CONFLICT / R-DUPLICATE-PAIR / R-ONE-TO-MANY | 38 / 0 / 0，逐条不变 |
| 新增单元测试 | 6 项全部通过 |
| `pytest tests/unit -q` | 1854 passed, 1 skipped |

预期 m2o 14 -> 10 未达成，差的 2 条是 p039；原因与可选补充见 §4。

## 2. 改动位置（rules.py 当前行号）

| 行号 | 内容 |
|---|---|
| 335–337 | `_SW_TERMINAL_ENDPOINT_CATEGORIES`：SW 端子标签（端子 / 装置端子） |
| 339 | `_sw_terminal_direct_partners`：与右值之间的 SW 端子-端子直连 pass 线的另一端（分句 b 的依据）。要求 `evidence.superworks` 的 left/right 两端类别均为端子标签；排除桥接、非 pass、元件端口连线（如 `superworks_connect_line_port`，无 left/right 字典） |
| 363 | `_is_net_explained_many_to_one_group`：组内每个冲突左值都须满足 (a)/(b)/(c)，否则组仍报 |
| 1634 | `_run_many_to_one`：在 Y3-b 直通豁免之后、结构豁免之前调用，满足则 `continue` |

只做"减少 issue"，不增加新 issue，不改变其他分支。

## 3. 三条子句（结构字段，无值特判，无注记判据）

- (a) 行两侧：左值 L 与 R 的一个 terminal_header_table 行（`_terminal_row_side_index`，中间列为 R）的一侧同处；该行另一侧须与组内另一成员为同针别名。复用 L-16 R3 的行索引。
- (b) 直连：L（或其同针别名）是 SW 端子-端子直连 pass 线（`superworks.left/right` 类别均为端子标签）另一端，直连的另一端为 R。
- (c) 同针别名：L 与组内某成员同针，且该成员已由 (a)/(b) 或传递地由 (c) 解释。同针判定复用 L-16b Y3-a（`_same_pin_alias_roots`：同 sheet、同 right_text_id 上表格记录与元件记录共存）。(c) 采用不动点传播，避免两个互为别名、与右值无通路的名字相互解释。

未使用 F4c `endpoint_aliases`：本组相关记录的 evidence 中没有该字段。

## 4. 与指令不一致之处（如实记录）

**p039 I0001 / I0002 未消除。** 两条组的左值为 `1-2LP1-2`（PCM0024，元件端口，S0025）与 `1-2n223`（P0179 表格，S0022；PSW381 直连，S0017）；右值 `1-2n221`。

- `1-2n223` 满足 (b)：PSW381 为 n223—n221 直连 pass（两端均为装置端子）。
- `1-2LP1-2` 不满足 (a)/(b)/(c)：
  - (a)：无 terminal_header 行含 LP1-2 与 n223。
  - (b)：与 n221 无直连 pass 线。其元件体 `1-2LP1` 的外接连线 PWM0275 接的是 n223（不是 n221），且 PWM0275 为元件端口连线（`wire_component_mapping`，scoped_visible_prefix），不是端子-端子直连。
  - (c)：同 sheet、同 right_text_id 上无表格记录（S0025 上只有 PCM0024 与 PCB0002 两条元件/语义记录），Y3-a 不归并。
- 因此按指令"任一左值无解释即仍报"，两条保留。

PWM0275 与 PSW381 的左端 text id 相同（T1970，同为 S0017 的 n223 端子文字），这是"元件体一跳经端子到 R"的同网证据。该路径不属于 (a)/(b)/(c) 的字面定义，本次未实现。若需要消除这两条，需由负责人确认是否新增一条子句（例如：元件端口所在元件体的外接端，与一个分句 (b) 端子同文字），并补充对应的反例测试。我未自行加入，以免超出指令边界。

## 5. 逐条差异（离线，round11）

| # | 项目 | 规则 | 右值 | 左值 | 结论 |
|---|---|---|---|---|---|
| 1 | p040 | R-MANY-TO-ONE | 1GD1 | 1n/NDY306A-3、1DK1-4、2YD1 | 消除：2YD1 (b) 直连 PSW3a56；1n/NDY306A-3 (b) 经同针别名 1n103（Y3-a，S0016 T2050）与直连 PSW28b4；1DK1-4 (a) 行 162D 另一侧 1n103 为同针别名 |
| 2 | p040 | R-MANY-TO-ONE | 2GD1 | 2n/NDY306A-3、2DK1-4、1YD1 | 消除：1YD1 (b) 直连 PSW94b2/PSW9827；2n/NDY306A-3 (b) 经同针别名 2n103（Y3-a，S0017 T2616）与直连 PSWcdf1/PSWa479；2DK1-4 (a) 行 1851 另一侧 2n103 |
| - | p039 | R-MANY-TO-ONE | 1-2n221、3-2n221 | 见 §4 | 保留（左值 LP1-2 无解释） |
| - | p040 | R-MANY-TO-ONE | 1ZK-3 | 1Q4D3、HD1 | 保留：HD1 无任何子句解释（HD 行 1EF9 仅一侧，无直连），1Q4D3 的直连线 PSW495 为元件连线、无端子类别，不计入 (b) |
| - | GND 9 条 | R-MANY-TO-ONE | GND | 各组 | 保留（逐条不变） |
| - | 其他规则 | | | | 无变化（cross 38、dup 0、o2m 0） |

## 6. 单元测试

`tests/unit/test_superworks_loop_z6_m2o.py`（6 项，全部通过）：

- (b) 正例：两个左值均为端子-端子直连到同一右端子，不报。
- (b) 反例：直连的右端为元件端口（类别 元件端子），不计直连，仍报。
- p040 1GD1 形态正例：行 162D 两侧（1n103 / 1DK1-4）+ 同针别名 1n103（Y3-a）+ 直连 1GD1-1n103 与 1GD1-2YD1，不报。
- p040 1GD1 形态反例：额外加入无解释的左值 9ZZ1，仍报。
- (c) 反例：两个互为同针别名的名字，与右值无通路，仍报（不动点传播生效）。
- p040 1ZK-3 形态反例：1Q4D3 与 HD1 各自单侧行写同一 1ZK-3，仍报，且冲突左值集合为 {1Q4D3, HD1}。

全量：`pytest tests/unit -q` 为 1854 passed, 1 skipped。

## 7. 限制

- 离线重算为 rules 层（`_run_many_to_one` 等 runner 直接调用），未经 producer；与 L-16b 口径一致。
- (b) 的 SW 端子类别判定依赖 `evidence.superworks.left/right.category`，对没有该字典的直连记录不生效（保守，只会少豁免）。
- 1GD1 / 2GD1 的豁免依赖 Y3-a 同针归并（同 sheet、同 right_text_id）；跨 sheet 的同网别名不在范围内。
