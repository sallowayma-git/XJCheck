# 人工电气符号裁决主记录

> 状态：当前唯一人工裁决历史文档（2026-07-15 整理）
> 活动实现要求仍以 `doc/任务书.md` 为准。本文件只记录用户已经明确确认的业务语义、原图证据及可泛化族规则。

## 1. 裁决原则

- 原始 DWG、INSERT handle、坐标和当时观测 fingerprint 用于 provenance，不作为族模型的唯一身份。
- fingerprint 发生漂移、重绘或实体表达变化时，应优先用已经确认的几何族及实例证据重新判定。
- “忽略”仅抑制电气语义：保留 CAD 对象和来源，不生成端口、桥接、Pair、Network、union 或独立 Issue。
- `+` 表示组件端与外部端子的映射关系，不表示组件内部短接。
- 未明确确认内部导通的器件一律 `internal_connectivity_inferred=false`、`electrical_union_eligible=false`。

## 2. 已确认 IGNORE / 不连通族

| 定义 | 人工确认来源 | 观测 fingerprint | 人工结论 | 泛化族 |
|---|---|---|---|---|
| `SYMB2_M_PWF165` | `04 交流回路图1.dwg`, `11266`, `(137.5,220.0)` | `39b95b5118323d4d8ec235cb43fb72f9b99c8d90ce9f4b2027ee2bdda6255ed5` | 数字/文字块，不是电气符号；无端口 | `non_electrical.numeric_text.v1` |
| `SYMB2_M_PWF171` | `11 非电量开入回路.dwg`, `2CE94`, `(161.25,235.0)` | `765aa9ba366baffab5550e90512b94fb6bc312a9866af101fe7e9ae6571d1c02` | 小型竖向二极管；不连通、不建立映射，整体忽略 | `electrical.diode_symbol_ignored.v1` |
| `SYMB2_M_PWF191` | `11 非电量开入回路.dwg`, `2CE58`, `(165.0,240.0)`；既有来源另见 `08 差动保护及信号回路.dwg`, `23353` | `9a1c6d15833092f32027442d19bd52f5f384395b0bb113e252e5bfbfe66cb85b` | 矩形封装二极管；不连通、不建立映射，整体忽略 | `electrical.diode_symbol_ignored.v1` |
| `SYMB2_M_PWF194` | `08 差动保护及信号回路.dwg`, `2337F`, `(290.0,235.0)` | `a78b06f3c9ab76dc9d36aeecdecb3a32599dbbc55c0e186dbecce76a9ecc780b` | 断开电气开关；左右不连通 | `switch.open.v1` |
| `SYMB2_M_PWF196` | `08 差动保护及信号回路.dwg`, `23397`, `(290.0,225.0)` | `634756a0bafe88dd763d740c97fe13dbbd65921586360b6f96a87d2dc2a408f4` | 断开电气开关；无可用电气端口 | `switch.open.v1` |
| `SYMB2_M_PWF206` | `06 直流回路图.dwg`, `EE8C`, `(182.5,270.0)` | 人工记录 `b37828da...71f746`；当前抽取另见 `5ef6acf6...c9a90e` | DC 功能/变换图形，可忽略，无端口 | `non_electrical.functional_graphic.v1` |
| `SYMB2_M_PWF208` | `05 交流回路图2.dwg`, `2170A`, `(55.0,177.5)`；`21728`, `(55.0,202.5)` | `cfe71411f229bb03fbcff9605b5b3dc0ace82f26b83a4d53fee308559e04412d` | 左侧装置区器件图形，无端口、无联通 | `non_electrical.equipment_graphic.v1` |
| `SYMB2_M_PWF210` | `11 非电量开入回路.dwg`, `2CEAE`, `(162.5,80.0)` | `ef9845390ad82463e1efac6f04551d65d189a6d9a311ce8c2b1398021e70c7cc` | 无实际电气含义 | `non_electrical.placeholder.v1` |
| `SYMB2_M_PWF229` | `04 交流回路图1.dwg`, `1126C`, `(145.0,220.0)` | `4843ab10418b48bf18e403125a6c80ba490c88d0987c42f712b5c24c8503dc61` | 波浪/省略/端粒标记；左右两侧明确断开 | `line_break.non_connective.v1` |
| `SYMB2_S_PWF324` | `06 交换机回路图1.dwg`, `F86D`, `(57.5,195.0)` | `b5cc87f72424ca9b4ba46d97f97872e74f1c6f174334905b3ed05bd2d1cc73f0` | 以太网通信端口组件；不建立 P1/P2 等任何向外通信映射，整体忽略 | `communication.ethernet_port_ignored.v1` |
| `SYMB2_S_PWF330` | P001 `07 网络通讯回路图.dwg`, `1C27C`, `(135.0,257.5)` | `b65e304c63f2661098d380605c4000e75855fbfcc57985109fad3a21c1c88ed5` | ETHER/NET、LAN 通信端口组件；不建立任何通信或电气映射，整体忽略 | `communication.ethernet_port_ignored.v1` |
| `SYMB2_S_PWF316` | `05 信号回路图.dwg`, `A214`, `(627.5,464.375)` | `32f327c96740e2b52598d08b894a9071d6fbeff2f5404d1e81addf7e5ce741db` | ST 单模光纤通信端口；不建立 `1T/1R` 发送/接收映射，整体忽略 | `communication.optical_st_port_ignored.v1` |
| `SYMB2_S_PWF318` | `04 交流回路图1.dwg`, `11176`, 外层 `(40.0,220.0)`；嵌套展开 `(40.0,232.495)` | `a6c74f98075e063d0bd026cee40d021e30ded7fb6eabca346385d81d1f8f81e7` | 接地符号；不建立任何映射、端口、桥接或并网关系，整体忽略 | `electrical.ground_symbol_ignored.v1` |
| `Ld_DzbJD_Left` | P001 `17 差动保护背板图.dwg`, `30F34`, `(55.0,252.5)`；同定义亦见 P003 | `d2978aaddce462eeea764d8295a059d646b00da794aeab718a568e6470bbf56b` | 左侧阶梯/重复线画法的接地符号；无端口、无映射，整体忽略 | `electrical.ground_symbol_ignored.v1` |
| `Ld_DzbJD_Right` | P001 `27 右侧端子图2.dwg`, `2AF3`, `(115.0000017,157.5)`；P003 同定义 `3CD15`, `(92.5,160.0)` | `08a272799dbac4bf36f36ebcc1091f94b2273cf27fce8741a3cf31b150d5d123` | 右侧 DZB 辅助标记；无联通属性、无任何外部映射，整体忽略 | `electrical.nonconnective_dzb_right_marker_ignored.v1` |
| `A$C26C55624` | P001 `14 高操作回路图.dwg`, `276B6`, `(249.9986338,134.9945)` | `4f4abeddea8e309da9df83614ee3def2228b9e72a1f9a6e788b270ab13ec8fa1` | 三引线矩形器件图形；内部不连通、无任何映射意义，整体忽略 | `electrical.nonconnective_three_lead_box_ignored.v1` |

补充确认：PWF165 附近的波浪/省略符号不能连接两侧数字，不得生成 `707→708`、`709→710`、`711→712` 等跨标记关系。

### IGNORE 几何族模型

- PWF194/PWF196：无 ARC/CIRCLE、两外向端、`LWPOLYLINE=2`、`LINE=3..4`、旋转无关长宽比约 6.5。
- PWF229：四个等半径 ARC、两个 LWPOLYLINE、两外向端、长宽比大于 8。
- PWF208：两个等半径 ARC、细长主体、归一化 ARC 半径和引线直方图区别于基础端子。
- PWF171/PWF191：同属二极管忽略族的两个几何状态。PWF171 是双圆接点、三角/横杆和纵向引线构成的裸二极管；PWF191 是含 HATCH、外框、主二极管及下方重复小图形的矩形封装状态。两者分别建模，不用实体数量或 fingerprint 互相代替。
- PWF206：含两段 TEXT 的四外端功能图形；PWF165/PWF210 分别有独立的无 ARC 实体直方图和长宽比。
- PWF324：两段 `ETHERNET`/端口文字、2..3 个 LWPOLYLINE、4..5 个机器几何端口、无 LINE/ARC/CIRCLE，旋转无关长宽比 `1.0..1.4`；不同页面的两种画法归入同一忽略族。
- PWF330：同属以太网/LAN 端口忽略族的宽体状态，块内文字为 `ETHER`/`NET`、含 3 个 LWPOLYLINE；作为独立几何子规则按文字布局、闭合轮廓拓扑及旋转/缩放不变量识别，不再作为 PWF324 的负例，也不能仅靠宽高比或 fingerprint 吸收其他宽体图形。
- PWF316：单 ARC、单 LINE、双 LWPOLYLINE、两个机器几何端口、无块内文字，归一化 ARC 半径 `0.25..0.35`、长宽比 `1.6..2.1`；`ST单模/1T/1R` 是实例周边文字，不产生映射。
- PWF318：一个闭合圆形接点、单根引线和三条互相平行且长度逐级递减的接地横线；旋转/缩放后仍按线方向、平行关系、长度层级及圆形接点绑定识别。仅有相同实体数量但不具备该拓扑的普通分支不得被吸收。
- `Ld_DzbJD_Left`：三条阶梯横线以 LINE 与 open LWPOLYLINE 重复绘制，重复 stem 与侧向引线绑定；作为接地族的独立几何状态按重合段、正交关系、长度层级和端点绑定识别，不依赖块名或 fingerprint。
- `Ld_DzbJD_Right`：三个逐级缩短、中心共线的平行条分别由 LINE 与开放双点 LWPOLYLINE 重合绘制；最长条中心连接一对重合正交杆及半长侧引线。按相对方向、长度比例、重合和端点绑定泛化，任一重绘条偏移或杆件拓扑不完整时保持 review。
- `A$C26C55624`：大矩形底部嵌套一个同宽小矩形，小矩形含对角线；三条等长平行引线以“两侧二对一”方式绑定大矩形边。按矩形边长比例、中心关系、对角角点和引线端点拓扑泛化，任一引线脱离或内部结构不完整时保持 review。
- 新 fingerprint 完整命中上述模型时可自动输出 `GEOMETRY_FAMILY_NON_CONNECTIVE`；特征缺失或仅近似时保持 review，不得自动忽略。

## 3. 已确认基础端子族

| 定义 | 人工确认来源 | fingerprint | 结论 |
|---|---|---|---|
| `SYMB2_M_PWF231` | `04 交流回路图1.dwg`, `112CE`, `(77.5,220.0)` | `2ede8a4fcebd958209b99a25e477726c0b55f86b32d00650130a89acad0bf89c` | 基础端子；上方 `1ID1` 等为端子编号 |
| `SYMB2_M_PWF232` | `08 差动保护及信号回路.dwg`, `23348`, `(110.0011,224.9958)` | `5f5573087fee9f48a503ecdede638903fcb979dd5031aaf1e98e69d07f2707f8` | 基础端子；上方 `1QD5` 等为端子编号 |
| `SYMB2_M_PWF233` | `06 直流回路图.dwg`, `192A2`, `(50.0,272.5)` | `e2e32701027b07d3f74b5941716ca9328daf926abad92f0b4b5f2081b3f52fe2` | 基础端子；支持 `ZD1/ZD9` 等字母开头编号 |
| `SYMB2_M_PWF234` | `08 差动保护及信号回路.dwg`, `23358`, `(57.5011,237.4958)` | `03db302eda788e4107a4dc2e882e6da52af3d56ea388d8a8f5789e6892a52211` | 四向画法的基础端子 |
| `SYMB2_M_PWF238` | `04 交流回路图1.dwg`, `1129E`, `(207.5,220.0)` | `cce15b281bc0c0ef0df95453bffcd991d28e73e7683a513b4c3e5f979c243438` | 基础端子；`1ID4/1ID5/1ID6` 为编号 |
| `SYMB2_M_PWF239` | `06 直流回路图.dwg`, `EEB7`, `(150.0,252.5)` | `c578f4c57480a4eabf4f0affb3ac93a9ca7e3eef23ca67e810605b48f06ac99b` | 三引线画法的基础端子 |
| `SYMB2_M_PWF243` | `08 差动保护及信号回路.dwg`, `2334E`, `(60.0011,209.9991)`, 旋转 270° | `b3115ea33fe4e1b57d4cfa6394c3125c42f5776b589f8297b4053cf3d7a7a073` | 旋转画法的基础端子；`1QD2/1QD3` 为编号 |

统一业务规则：

- family 为 `labelled_terminal.generic.v1`，不能按 PWF 编号分别建立模型。
- 定义级必须是紧凑双等半径 ARC 主体；实例级必须同时找到唯一结构化编号和 outward-aligned 外部导线接触。
- 三项证据完整才输出 shadow `MEASURED_TERMINAL_ATTACHMENT`；标签近似并列为 `TERMINAL_BINDING_AMBIGUOUS`。
- 不根据端子主体自动合并左右/上下导线。

## 4. 已确认外部端口组件族

### `SYMB2_M_PWF224` — KLP 双外部端口

- 来源：`08 差动保护及信号回路.dwg`, handle `23354`, `(85.0001,207.4991)`。
- fingerprint：`61255c39029679e1151d9d4e8fe3884a538ea97638fa6f605d8a1d17713d8dc2`。
- 端口 `1/2` 分别只连接本侧外部导线；组件内部不连通。
- 示例：`1KLP1-1 + 1QD2`；右侧端口只匹配右侧同一条线上的端子。

### `SYMB2_M_PWF236` — DK 四端口组件

- 来源：`06 直流回路图.dwg`, handle `EE97`, `(95.0,260.0)`。
- 人工记录 fingerprint `e84d37eab1d5...b9e7ee9`；当前抽取观测 `e84d37ea2bda...dee7ee9`，说明 fingerprint 可漂移。
- 实例名 + 端口号构成完整身份，如 `1DK-3`；每个端口只映射同侧外部端子，如 `1DK-3 + ZD1`。
- 四个端口内部互不连通。

### `SYMB2_M_PWF237` — ZKK 六端口组件

- 来源：`05 交流回路图2.dwg`, handle `216AD`, `(102.5,150.0)`。
- fingerprint：`835a7dcc7eae596a7b1a600a48f0e579bf800a22b1add1ffbcc44d2ddb95e054`。
- PWF236 的三排/六端口版本；例如 `1-2ZKK-1..6`，每个端口独立映射同侧外部端子，内部不连通。

### `SYMB2_M_PWF103` — AK 双外部端口组件

- 来源：P001 `06 直流回路图.dwg`，handle `1D348`，坐标 `(252.5563,109.9881)`；P003 同定义 handle `420DA`，fingerprint `eec06b5aa9987f50b15e7871e0545c46d26b47ec64abdf9ff796d67c2e328bee`。
- 实例名 `AK` 与本地端口号 `1/2` 组合为 `AK-1`、`AK-2`；`AK-1` 只映射左侧外部线路，`AK-2` 只映射右侧外部线路。
- 两端口内部不连通，不允许任何 `AK-1 ↔ AK-2` connectivity 或 union。几何族为 `component.external_strip_two_port.v1`。
- 定义级按四个共线等半径接点、与内侧接点同心的两个等半径圆、四条轴向线及三条叉形/斜向机构线的旋转缩放拓扑识别；实例级必须同时绑定短字母名称、唯一端口号和本侧精确外部线端点。

### `KK2P` — DK 四端口组件

- 来源：P001 `21 元件接线图1.dwg`，handle `27FDC`，坐标 `(47.5,252.5)`；fingerprint `3f7ef8a0ca8b88180e8cf7094e95355e6b2837e7e598cba3a19ce04e6445620a`。
- 上方圆圈内实例名经原图确认是 `1DK`；实例名与块内端口号 `1/2/3/4` 组合为完整身份 `1DK-1..4`。
- 四个端口内部互不连通，各自只向外映射：`1DK-1→ZD9`、`1DK-2→1QD5`、`1DK-3→ZD1`、`1DK-4→1QD1`。
- family 为 `component.external_multi_port.v1`；同类实例必须读取本实例圆圈名称，不得把 `1DK` 固化为定义常量。

### `FJL-25-2A_Mirror` — 长条上下双端口组件

- 来源：`22 元件接线图2.dwg`, handle `2F409`, `(55.2366,238.8056)`。
- fingerprint：`69f5c09b9bfe7e7c3c9db62eaa577a51b98801ec22bb366b8d5d2513ae1b247b`。
- 上下端口向外连接，内部不连通；圆形文字为实例名。
- 示例：`1-2CLP5-1 + KD15`、`1-2CLP5-2 + 1-2n414`。

统一泛化规则：

- DK/ZKK 使用 `component.external_multi_port.v1`；FJL/PWF224 新画法可进入 `component.external_strip_two_port.v1` 或相应 inline subtype。
- 几何族只提出端口拓扑；完整组件端身份必须由实例名、端口槽位、同侧导线和 `component_mapping` 共同构成。
- 所有组件端只允许外部 attachment 和跨页匹配，不允许任何端口间 union。

## 5. 当前实现验证

- 将 8 个已确认 IGNORE 正例全部替换为未登记 synthetic fingerprint 后，几何族模型仍全部正确忽略。
- PWF224、PWF231/233/234/239、PWF236/237 均未被 IGNORE 模型误吸收。
- FJL 在新 fingerprint 下仍进入外部双端口组件族。
- proposal/instance fingerprint 冲突必须输出 `REJECTED_FINGERPRINT_MISMATCH`，不能通过同名块静默绑定。

## 6. 已确认导线几何原语

### `A$C2E3F2C02` — 跨线跳弧

- 来源：P001 `14 高操作回路图.dwg`，handle `276BF`，坐标 `(209.9986338,142.4945)`，fingerprint `f9d454c009fff6e62f248535070beb3ce1787db373d260f7159948192c492bb8`；共观测 10 个实例。
- 该对象不是符号，而是导线画法：两段共线引线通过中间半圆弧连续，圆弧表示越过另一条导线后继续连接。
- 跳弧所属导线两端属于同一路径；被跨越导线保持自身连续，但两条路径在几何交点不连接，不得生成交叉点 union。
- 泛化模型必须使用“半圆 ARC 端点分别绑定两段共线外向 LINE、弦线与引线共线”的旋转/缩放不变拓扑；定义名、坐标和 fingerprint 仅作 provenance，不是正常识别条件。
- 该族不得走 IGNORE：应从符号复核中移除并转成 wire primitive，同时保留跳弧路径的左右连通。

## 7. 待人工裁决区

本文件不保留历史机器猜测。清理后由最新 P001/P003 全量分析重新生成待裁决清单；只有用户明确回答后的条目才会移入以上“已确认”章节。
