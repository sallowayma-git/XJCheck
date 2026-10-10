# L-07：p044 S0020 一对多存量 4 条（1-21ZKK1-4 / 1-21ZKK2-4）

## 结论
4 条全部为**误识别**：不是合法一对多，也不是真实接线问题。
- 端子 1-21n715 只接端口 4，1-21n717 只接端口 6；1-21n721 接端口 4，1-21n723 接端口 6。两条导线不是同一端口的两个分支。
- 误识别来自 SW 连接线路径：它把端口 6 的旧链配对改写成端口 4，同一左值 `1-21ZKK1-4` 因此指向两个右值。p043 同样两条，4 条 O2M 均由此产生。

## 1. 相关 pair（p044，findings/pairs.parquet）
| pair_id | 左值 → 右值 | 来源（component_submode） | 端口引脚 x | 图上实际 |
|---|---|---|---|---|
| PCK0036 | 1-21ZKK1-4 → 1-21n715 | 旧链 kk_multi_port_component | 369.0 | 正确 |
| PCK0038 | 1-21ZKK1-4 → 1-21n717 | superworks_connect_line_port | 368.75 | 误：n717 属端口 6（x=385） |
| PCK0030 | 1-21ZKK2-4 → 1-21n721 | 旧链 | 296.5 | 正确 |
| PCK0032 | 1-21ZKK2-4 → 1-21n723 | superworks_connect_line_port | 296.25 | 误：n723 属端口 6（x=312.5） |

PCK0038：component_port=4，external_endpoint=1-21n717，connect_text_id=T3721，connect_line_handle=2E079，pin_resolution_method=definition_text_reference。supersession 账本记录其旧值为 1-21ZKK1-6 → 1-21ZKK1-4（reason=validated_superworks_replacement），pair_id 沿用 PCK0038。

## 2. 图形证据（DXF F0020，块 1-21ZKK1，句柄 2D388）
- 块内 6 个引脚各占一格；水平线 y=132.5（即 L6063–L6065，GC0008）是元件外框，不是端子间导线。
- 顶部引脚：端口 2 x=352.5，端口 4 x=368.75，端口 6 x=385.0。
- 模型空间引线：2E075（x=352.5）连 "& 1-21n713"；2E079（x=368.75，127.5→126.5）接在端口 4 引脚末端，终点即 "& 1-21n715" 的对齐点；2E07D（x=385）连 "& 1-21n717"。
- 端子文字水平居中于各自引脚 x。端口 4 只有一条竖线，到 n715，n717 与端口 4 之间没有线，故"两个都接"不成立。
- 截图：`L07_p044_S0020_ZKK1_ports.png`、`L07_p044_S0020_ZKK2_ports.png`

## 3. 同页其他 KK 端口
- 页内 11 个 KK 实例、46 个引脚，按几何（引脚 x 对齐端子对齐点）核对：44 个引脚与图一致。
- 错误 2 条即上表 PCK0038、PCK0032；缺失 2 个：1-21ZKK1-6→1-21n717、1-21ZKK2-6→1-21n723（无 pair）。
- KK2P、KK1P、small_port_box 类全部正确；页内非 KK 块（LA38、XJDZ9）的部分无 pair 端子超出 L-07，未核。

## 4. 根因与代码位置
1. `src/dwg_audit/extract/superworks_semantics.py` `_connect_labels`（L458–483）：
   - L467 以文字插入点测距，未用对齐锚点（同文件 `text_anchor_wcs` L41 已存在）；居中文字的插入点与锚点相差约 8.6。
   - L468 半径 max(5, 3×字高)=9；L470 排序先比句柄差、后比距离。
   - 结果：&1-21n717（2E07E，锚点 385,131.5）取到 2E079（距离 7.7）；&1-21n715（2E07A）距 2E079 为 9.47 > 9，未关联（unresolved_connect_line）。
2. `src/dwg_audit/audit/superworks_extractor.py`：L739 起的 SW 连接线配对，L762 按 line_handle 取线，L800 `replace_claims`（定义 L504）直接覆盖旧链 pair 的左值；L745 只查 reason_codes，不核对 SW 端口号与旧链端口号是否一致。
3. 旧链 `src/dwg_audit/audit/component_diagrams.py` `extract_kk_multi_port_component_pairs`（L214）原本正确产出 1-21ZKK1-6→1-21n717（端口 6 与端子 x 差 2.9，在 `_KK_SLOT_ENDPOINT_X_TOL`=8 内，L77），随后被 SW 替换。

## 5. 通用修复方案（未改代码，无特判）
1. `_connect_labels` 以锚点为基准：优先选端点与锚点重合（≤0.5）的 LD_ConnectLine 线，并列时再比句柄差；仅在无重合线时回落到现有半径规则。
2. 防御性：SW 替换旧链 pair 时，若端口号不一致而旧链几何与该端子锚点吻合，则保留旧链并记 sw_conflicts。
3. 预期：PCK0038 变为 1-21ZKK1-6→n717，PCK0032 变为 1-21ZKK2-6→n723，缺失的两条恢复，4 条 O2M 消失。

## 6. 影响面（第四轮 77 个项目，DXF + parquet 离线统计，未重放）
- SW 连接标签（有 DXF）27185 条：锚点规则下 18807 条不变；6 条改线（KK：p043 2E43C、2E448，p044 2E07E、2E08A；非 KK：p000 1A3A7、p052 3CC87，后果未判定）；8222 条当前 unresolved 可新关联；53 条 GND 类锚点偏移约 3.6，须保留回落。
- 旧链 KK pair 被 SW 替换且端口号改变：6 条（p043 2、p044 2、p040 PCK0017/18 的 2-1n-1→KZKK-1、2-1n-3→KZKK-3，未看图）。
- 产生 O2M 的仅 p043/p044 共 4 条；其余 64 条属 L-01（p075）。风险：8222 条新关联会改变 SW 派生 pair 集合，修复后须全量重放并对比 m2o/o2m/dup/missing，不能只凭离线统计。

## 7. 限制
几何判定依据缓存 DXF（ezdxf）与 parquet；未运行流水线，未改 src/；未核 p040 与非 KK 改线的后果。
