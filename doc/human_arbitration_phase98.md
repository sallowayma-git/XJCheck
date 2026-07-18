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
| `SYMB2_M_PWF31` | P001 `06 直流回路图.dwg`, `1D34F`, `(339.9901,99.9881)` | `8f7479379424184442b346891c2040fe047a8756561435f42095f4e088b39cf1` | X 形双接点开关；整体忽略、上下内部不连通、无映射 | `switch.open.v1` |
| `SYMB2_M_PWF206` | `06 直流回路图.dwg`, `EE8C`, `(182.5,270.0)` | 人工记录 `b37828da...71f746`；当前抽取另见 `5ef6acf6...c9a90e` | DC 功能/变换图形，可忽略，无端口 | `non_electrical.functional_graphic.v1` |
| `SYMB2_M_PWF208` | `05 交流回路图2.dwg`, `2170A`, `(55.0,177.5)`；`21728`, `(55.0,202.5)` | `cfe71411f229bb03fbcff9605b5b3dc0ace82f26b83a4d53fee308559e04412d` | 左侧装置区器件图形，无端口、无联通 | `non_electrical.equipment_graphic.v1` |
| `SYMB2_M_PWF210` | `11 非电量开入回路.dwg`, `2CEAE`, `(162.5,80.0)` | `ef9845390ad82463e1efac6f04551d65d189a6d9a311ce8c2b1398021e70c7cc` | 无实际电气含义 | `non_electrical.placeholder.v1` |
| `SYMB2_M_PWF229` | `04 交流回路图1.dwg`, `1126C`, `(145.0,220.0)` | `4843ab10418b48bf18e403125a6c80ba490c88d0987c42f712b5c24c8503dc61` | 波浪/省略/端粒标记；左右两侧明确断开 | `line_break.non_connective.v1` |
| `SYMB2_S_PWF324` | `06 交换机回路图1.dwg`, `F86D`, `(57.5,195.0)` | `b5cc87f72424ca9b4ba46d97f97872e74f1c6f174334905b3ed05bd2d1cc73f0` | 以太网通信端口组件；不建立 P1/P2 等任何向外通信映射，整体忽略 | `communication.ethernet_port_ignored.v1` |
| `SYMB2_S_PWF330` | P001 `07 网络通讯回路图.dwg`, `1C27C`, `(135.0,257.5)` | `b65e304c63f2661098d380605c4000e75855fbfcc57985109fad3a21c1c88ed5` | ETHER/NET、LAN 通信端口组件；不建立任何通信或电气映射，整体忽略 | `communication.ethernet_port_ignored.v1` |
| `SYMB2_S_PWF316` | `05 信号回路图.dwg`, `A214`, `(627.5,464.375)` | `32f327c96740e2b52598d08b894a9071d6fbeff2f5404d1e81addf7e5ce741db` | ST 单模光纤通信端口；不建立 `1T/1R` 发送/接收映射，整体忽略 | `communication.optical_st_port_ignored.v1` |
| `SYMB2_S_PWF318` | `04 交流回路图1.dwg`, `11176`, 外层 `(40.0,220.0)`；嵌套展开 `(40.0,232.495)` | `a6c74f98075e063d0bd026cee40d021e30ded7fb6eabca346385d81d1f8f81e7` | 接地符号；不建立任何映射、端口、桥接或并网关系，整体忽略 | `electrical.ground_symbol_ignored.v1` |
| `SYMB2_S_PWF314` | P001 `17 差动保护背板图.dwg`, nested handle `3056A`, world `(400.7324,68.9934)`；P001/P003 指定 8 页均有实例 | `1ee219a2138f046ca744c25611726492fb54b31ef2126f57af79a85f66adb36a` | 继承既有接地符号权威；圆圈内阶梯接地变体整体忽略，零端口、零映射、禁止 connectivity/union | `electrical.ground_symbol_ignored.v1` |
| `Ld_DzbJD_Left` | P001 `17 差动保护背板图.dwg`, `30F34`, `(55.0,252.5)`；同定义亦见 P003 | `d2978aaddce462eeea764d8295a059d646b00da794aeab718a568e6470bbf56b` | 左侧阶梯/重复线画法的接地符号；无端口、无映射，整体忽略 | `electrical.ground_symbol_ignored.v1` |
| `Ld_DzbJD_Right` | P001 `27 右侧端子图2.dwg`, `2AF3`, `(115.0000017,157.5)`；P003 同定义 `3CD15`, `(92.5,160.0)` | `08a272799dbac4bf36f36ebcc1091f94b2273cf27fce8741a3cf31b150d5d123` | 右侧 DZB 辅助标记；无联通属性、无任何外部映射，整体忽略 | `electrical.nonconnective_dzb_right_marker_ignored.v1` |
| `A$C26C55624` | P001 `14 高操作回路图.dwg`, `276B6`, `(249.9986338,134.9945)` | `4f4abeddea8e309da9df83614ee3def2228b9e72a1f9a6e788b270ab13ec8fa1` | 三引线矩形器件图形；内部不连通、无任何映射意义，整体忽略 | `electrical.nonconnective_three_lead_box_ignored.v1` |
| `A$C08415381` | P001 `05 交流回路图2.dwg`, `216BC`, `(37.5,149.9999997)` | `59cf96d51fc55afa4f77a383e0ecf990270dbafbbcd454943b3473039f1a9e5b` | `HVS CB` 重复线圈/面板图形；整个组件无映射意义，整体忽略 | `electrical.nonconnective_repeated_coil_panel_ignored.v1` |
| `SYMB2_M_PWF182` | P001 `14 高操作回路图.dwg`, `27718`, `(82.4986,57.4945)`；同定义另有 `27719` | `de637c582be8e821b1cead5224227ebf5bbfc30d10f68ca7a36f9d20a3295526` | 圆内 X 与左右闭合接触区整体忽略；左右内部不连通、零端口、零映射、禁止 union | `electrical.nonconnective_crossed_circle_marker_ignored.v1` |
| `SYMB2_M_PWF192` | P001 `16 高低压侧操作箱信号回路.dwg`, `202A3`, `(109.9964,232.5055)`；同定义另有 `202D4/20325/20356` | `994da514414fa6239674d36dfc616a87430a5dafbab56f009f77b04469580830` | 带上方执行机构的开路开关图形整体忽略；两侧内部不连通、零端口、零映射、禁止 union | `electrical.nonconnective_actuated_open_switch_ignored.v1` |
| `SYMB2_S_PWF10` | P001 `14 高操作回路图.dwg`, `275F5`, `(355.9986,192.4945)`；同定义另有 `275F7` | `25548c2e6081ebe78ea8777dd91b07d6d3f4114392d2c3dcebf79cb16b454f53` | 直线/宽线接点/圆帽与不可见接触区构成的完整图形整体忽略；零端口、零映射、无联通意义 | `electrical.nonconnective_wide_contact_cap_marker_ignored.v1` |

补充确认：PWF165 附近的波浪/省略符号不能连接两侧数字，不得生成 `707→708`、`709→710`、`711→712` 等跨标记关系。

### IGNORE 几何族模型

- PWF194/PWF196：无 ARC/CIRCLE、两外向端、`LWPOLYLINE=2`、`LINE=3..4`、旋转无关长宽比约 6.5。
- PWF31：两个等半径圆接点间距约 `20r`，两条 `4r` 共线引线分别从接点向内，两条开放直线以公共中点形成 X，端点投影约为轴向 `±3.6r`、法向 `±4.8r`，并保留一个开放 bulged 机构路径。按接点—引线—X 中心拓扑做旋转/缩放泛化，X 偏心时保持 review。
- PWF229：四个等半径 ARC、两个 LWPOLYLINE、两外向端、长宽比大于 8。
- PWF208：两个等半径 ARC、细长主体、归一化 ARC 半径和引线直方图区别于基础端子。
- PWF171/PWF191：同属二极管忽略族的两个几何状态。PWF171 是双圆接点、三角/横杆和纵向引线构成的裸二极管；PWF191 是含 HATCH、外框、主二极管及下方重复小图形的矩形封装状态。两者分别建模，不用实体数量或 fingerprint 互相代替。
- PWF206：含两段 TEXT 的四外端功能图形；PWF165/PWF210 分别有独立的无 ARC 实体直方图和长宽比。
- PWF324：两段 `ETHERNET`/端口文字、2..3 个 LWPOLYLINE、4..5 个机器几何端口、无 LINE/ARC/CIRCLE，旋转无关长宽比 `1.0..1.4`；不同页面的两种画法归入同一忽略族。
- PWF330：同属以太网/LAN 端口忽略族的宽体状态，块内文字为 `ETHER`/`NET`、含 3 个 LWPOLYLINE；作为独立几何子规则按文字布局、闭合轮廓拓扑及旋转/缩放不变量识别，不再作为 PWF324 的负例，也不能仅靠宽高比或 fingerprint 吸收其他宽体图形。
- PWF316：单 ARC、单 LINE、双 LWPOLYLINE、两个机器几何端口、无块内文字，归一化 ARC 半径 `0.25..0.35`、长宽比 `1.6..2.1`；`ST单模/1T/1R` 是实例周边文字，不产生映射。
- PWF318：一个闭合圆形接点、单根引线和三条互相平行且长度逐级递减的接地横线；旋转/缩放后仍按线方向、平行关系、长度层级及圆形接点绑定识别。仅有相同实体数量但不具备该拓扑的普通分支不得被吸收。
- PWF314：独立规则 `circled-stepped-bar-ground-contact-v1` 要求完整 `4 LINE + 1 CIRCLE + 1` 个闭合 bulged `LWPOLYLINE`。三条同中心平行 bar 的长度比约 `1:0.75:0.5`、相邻间距约最长 bar 的 `0.25`；垂直 lead 从最长 bar 中点连接闭合接触区；外圆中心、半径与完整 motif 的包围关系同时受约束。规则仅使用相对向量、距离和比例，支持旋转、反射及统一缩放；外圆偏移、contact 脱离、bar 比例或间距失真时保持 review。独立 8 页 fresh replay 覆盖要求中的 10 个主 placements，并因 09/10 各有第二个父面板实例实际展开为 12 行；全部 `IGNORE / ports=[]`、零候选且无 topology/semantic/network member。
- `Ld_DzbJD_Left`：三条阶梯横线以 LINE 与 open LWPOLYLINE 重复绘制，重复 stem 与侧向引线绑定。精确人工成员保留 `electrical.ground_symbol_ignored.v1` 语义；该几何与已确认右侧标记互为镜像，未见 fingerprint 的完整命中进入共享 `electrical.nonconnective_stepped_marker_ignored.v1`，避免凭几何伪造“接地/右标记”语义差异。两者行为均为零端口 IGNORE。
- `Ld_DzbJD_Right`：三个逐级缩短、中心共线的平行条分别由 LINE 与开放双点 LWPOLYLINE 重合绘制；最长条中心连接一对重合正交杆及半长侧引线。按相对方向、长度比例、重合和端点绑定泛化，任一重绘条偏移或杆件拓扑不完整时保持 review。
- `A$C26C55624`：大矩形底部嵌套一个同宽小矩形，小矩形含对角线；三条等长平行引线以“两侧二对一”方式绑定大矩形边。按矩形边长比例、中心关系、对角角点和引线端点拓扑泛化，任一引线脱离或内部结构不完整时保持 review。
- `A$C08415381`：12 个等半径半圆构成 2×6 阵列，26 条线形成 25 条平行支线与一条正交 spine，四个圆接点重合为 spine 上两个接点位置；按阵列间距、半圆 sweep、骨架方向及接点绑定泛化，任一半圆或 spine/contact 拓扑偏移时保持 review。
- `SYMB2_M_PWF182`：完整定义为 `2 LINE + 1 CIRCLE + 2` 个闭合 bulged `LWPOLYLINE` 接触区。两 LINE 是共享圆心、端点落在圆周且彼此正交的完整直径；两个等半径接触区中心位于大圆相对两端，半径约 `0.267R`、中心距约 `2R`，接触区轴以约 `45°` 平分两条 X 直径。规则 `crossed-circle-opposed-contact-regions-v1` 仅使用相对几何，支持旋转/统一缩放；偏移任一接触区的同数量近似图形保持 review。精确成员、未见 fingerprint 和旋转缩放正例均为零端口 IGNORE；fresh replay 中 `27718/27719` 均零 network candidate、无 connectivity/union 产物。
- `SYMB2_M_PWF192`：完整定义为 `7 LINE + 2` 个闭合 bulged `LWPOLYLINE` 接触区。两个等半径接触区建立局部坐标轴和统一尺度；完整七线段无序模板同时验证两侧向内引线、斜置开路刀片，以及由一对重合斜杆、横杆、竖杆组成的上方执行机构。规则 `two-contact-actuated-open-switch-v1` 只使用相对坐标和拓扑，支持旋转、反射和统一缩放；偏移刀片或任一机构杆件的同数量近似图形保持 review。精确成员、未见 fingerprint 和旋转缩放正例均为零端口 IGNORE；独立 fresh replay `.tmp/phase151_pwf192_replay/phase151_pwf192_input` 中 `202A3/202D4/20325/20356` 均 `ports=[]`、零 network candidate，且无关联 topology application、semantic relation 或 network member。
- `SYMB2_S_PWF10`：完整定义恰为 `2 LWPOLYLINE`。可见开放 polyline 有三个共线顶点，第一顶点与不可见闭合圆形接触区同心，后两个顶点的起止宽度均为接触区直径；以接触半径 `R` 归一化后，三个顶点轴向位置固定为 `0/-13R/-5R`，两段长度为 `13R/8R`，全部 bulge 为 0。规则 `straight-wide-two-contact-cap-marker-v1` 同时检查完整顶点、宽度、可见性和接触区相对几何，支持旋转/统一缩放；偏移宽线顶点的近似图形保持 review。独立 fresh replay `.tmp/phase152_pwf10_replay/phase152_pwf10_input` 中 `275F5/275F7` 均 `ports=[]`、零 network candidate，且无关联 connectivity/union 产物。
- 新 fingerprint 完整命中上述模型时可自动输出 `GEOMETRY_FAMILY_NON_CONNECTIVE`；特征缺失或仅近似时保持 review，不得自动忽略。

## 3. 已确认基础端子族

| 定义 | 人工确认来源 | fingerprint | 结论 |
|---|---|---|---|
| `SYMB2_M_PWF87` | P001 `06 直流回路图.dwg`, `1D355`, `(322.4881,77.4881)` | 见当前人工成员策略 | 斜杠圆形双接点通用端子；实例名 `JD11`，两侧独立向外绑定，内部不连通 |
| `SYMB2_M_PWF89` | P001 `06 直流回路图.dwg`, `1D360`, `(222.4881,109.9881)`；同定义亦见 P003 | `84868127dc04f2454ab00c79d63b6d4a57792b2f47365725934a88bcf1986d65` | 斜杠圆形四接点通用端子；实例名 `JD1/JD2/JD6`，仅实际外接线方向独立绑定，四侧内部不连通 |
| `SYMB2_M_PWF231` | `04 交流回路图1.dwg`, `112CE`, `(77.5,220.0)` | `2ede8a4fcebd958209b99a25e477726c0b55f86b32d00650130a89acad0bf89c` | 基础端子；上方 `1ID1` 等为端子编号 |
| `SYMB2_M_PWF232` | `08 差动保护及信号回路.dwg`, `23348`, `(110.0011,224.9958)` | `5f5573087fee9f48a503ecdede638903fcb979dd5031aaf1e98e69d07f2707f8` | 基础端子；上方 `1QD5` 等为端子编号 |
| `SYMB2_M_PWF233` | `06 直流回路图.dwg`, `192A2`, `(50.0,272.5)` | `e2e32701027b07d3f74b5941716ca9328daf926abad92f0b4b5f2081b3f52fe2` | 基础端子；支持 `ZD1/ZD9` 等字母开头编号 |
| `SYMB2_M_PWF234` | `08 差动保护及信号回路.dwg`, `23358`, `(57.5011,237.4958)` | `03db302eda788e4107a4dc2e882e6da52af3d56ea388d8a8f5789e6892a52211` | 四向画法的基础端子 |
| `SYMB2_M_PWF238` | `04 交流回路图1.dwg`, `1129E`, `(207.5,220.0)` | `cce15b281bc0c0ef0df95453bffcd991d28e73e7683a513b4c3e5f979c243438` | 基础端子；`1ID4/1ID5/1ID6` 为编号 |
| `SYMB2_M_PWF239` | `06 直流回路图.dwg`, `EEB7`, `(150.0,252.5)` | `c578f4c57480a4eabf4f0affb3ac93a9ca7e3eef23ca67e810605b48f06ac99b` | 三引线画法的基础端子 |
| `SYMB2_M_PWF243` | `08 差动保护及信号回路.dwg`, `2334E`, `(60.0011,209.9991)`, 旋转 270° | `b3115ea33fe4e1b57d4cfa6394c3125c42f5776b589f8297b4053cf3d7a7a073` | 旋转画法的基础端子；`1QD2/1QD3` 为编号 |

统一业务规则：

- family 为 `labelled_terminal.generic.v1`，不能按 PWF 编号分别建立模型。
- 定义级支持多个严格几何子规则：紧凑双等半径 ARC 基础端子，以及中心圆/斜杠/对称圆接点的双接点或四接点 JD 端子；所有子规则都进入 `labelled_terminal.generic.v1`，不得按 PWF 编号拆族。
- 三项证据完整才输出 shadow `MEASURED_TERMINAL_ATTACHMENT`；标签近似并列为 `TERMINAL_BINDING_AMBIGUOUS`。
- 不根据端子主体自动合并左右/上下导线。
- JD 圆形端子每个方向只在存在 outward-aligned 外部导线证据时输出本实例名 attachment；未接线方向不输出，多个方向之间永不 union。
- PWF89 的实现验证已完成：旋转/缩放后的未见 fingerprint 仍命中共享族；斜线偏心或接点偏斜的同计数近似图保持 review。P001 实跑只保留 14 个真实接线方向，未接线方向不产生候选，缺少唯一 JD 名称的方向不借用邻近实例名。

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

### `SYMB2_M_PWF105` — A' 上下双行外部端口组件

- 来源：P001 `06 直流回路图.dwg`，handle `1D34C`，坐标 `(297.4885578,109.9881378)`；P003 同定义，fingerprint `55c2e04f990b264e93b235f7ed3c078a6034a853b3201192f447e7b346d8f06d`。
- 实例名 `A'` 与本地端口号 `1/2` 组合为 `A'-1`、`A'-2`；`A'-1` 只映射上方本侧线路，`A'-2` 只映射下方本侧线路。
- 两行端口内部不连通，不允许 `A'-1 ↔ A'-2` connectivity 或 union。几何族为 `component.external_strip_two_port.v1`。
- 定义级按单个 `1:2` 外框、四个等半径圆接点、两个重复嵌套行机构及接点相对间距识别；实例级必须同时绑定 `A'` 名称、本地数字 `1/2` 和对应行的精确外部线端点。外框角点不是端口。

### `SYMB2_S_PWF12a` — 通用单行接点机构

- 来源：P001 `06 直流回路图.dwg`，嵌套 handle `1D2D4/1D2D5` 见于 PWF105；独立 handle `1D382/1D383`；fingerprint `b440ea59c6edcaa2edd135cbfd3ca4d54f80bb2ea554a9ec7af3eeba5a6be3d0`。P003 亦见同定义，共 8 个实例。
- 人工裁决：该定义是 PWF105 使用的单行机构状态。成对行继承父/邻近实例名和本行数字，例如 `A'-1 → 上方本侧线路`、`A'-2 → 下方本侧线路`；各行内部互不连通，不允许 union。
- 泛化族为 `component.external_row_contact.v1`。定义级只提议一个与水平机构线绑定的外部接点；中心圆和偏置小接点属于机构图形，不是第二、第三个端口。
- 嵌套在已确认的 PWF105 两行外框中时，由父组件统一输出 `A'-1/A'-2`，PWF12a 子件不得重复发映射。独立放置时按附近实例名和唯一数字组合，例如真实 P001 的 `K-6`、`K-5`，各自只绑定本侧外线。
- 精确成员和旋转/缩放后的未见 fingerprint 均按几何命中；偏置接点不再位于圆心正交轴、两段机构线不共线/不相接、圆/接点半径比失真时保持 review。

### `LA38-11-209B-G` — FA 四独立端口组件

- 来源：P001 `21 元件接线图1.dwg`，handle `27F43`，坐标 `(65.0,102.49837)`，fingerprint `5b68b544d3f7834a0b52c64fa69de4c3a0a64ed859e6c95e11957707e1151eeb`；共 6 个实例。
- 人工裁决：代表实例名为 `5FA`，完整端口身份是 `5FA-11/12/13/14`。四个端口彼此不连接，只分别链接各自向外引线；例如 `5FA-13 → 5FD3`、`5FA-14 → 5n115`。
- 泛化族为 `component.external_multi_port.v1`，严格子规则 `four-numbered-independent-contact-panel-v1`。四个编号、四个大圆、四个外侧小接点和内部三线机构按完整 2×2 几何识别；内部三线只属于机构图形，不赋予端口间 conductivity。
- 端口提议必须以四个小外侧接点替换旧的三个自由极值，并携带原生 `11/12/13/14`。实例级名称位于端口阵列上方中心轴；左右外部端子文字不能反向抢作实例名。
- 真实代表实例输出 `5FA-13 → 5FD3`、`5FA-14 → 5n115`；没有实际外延线的 `5FA-11/12` 只保留端口身份，不伪造 mapping。所有实例均禁止端口间 internal connectivity 和 union。

### `SYMB2_M_PWF176` — FA 双接点机械执行器

- 来源：P001 `08 差动保护及信号回路.dwg`，handle `233C5`，坐标 `(85.07056,167.50439)`，fingerprint `8ffdfeebc545ed07bf9b740146cf2c8c729557b453649d679f18248d228d308e`；P001 共 6 个实例。
- 人工裁决：实例 `1FA` 的 `1FA-13` 与 `1FA-14` 始终不连通，只分别向自身外侧引线建立映射；已确认 `1FA-13 → 1QD3`。斜向开片和下方机械执行器均不赋予两端 conductivity 或 union。
- 泛化族为 `component.external_strip_two_port.v1`，严格子规则 `two-contact-mechanical-actuator-v1`。完整定义为 `9 LINE + 2` 个等半径闭合 bulged 接点：两个接点相距约 `22.5r`，各有一条约 `7.5r` 的向内共轴引线；一条约 `8.4r` 的斜向开片连接单侧内端；下方由五条短正交杆和一条横杆形成居中的执行器。
- 端口提议只取两个外侧圆接点中心，按接点中点反向确定 outward direction；实例级读取本实例 FA 名称及附近 `13/14`，组合完整端口身份。只有同一外部网络线路附近的结构化端子名才可成为外部端点；右侧未获人工确认时不得把附近裸数字擅自拼成端子名。
- 全 P001 真实验证输出 6 个实例、12 条独立映射：`1FA`、`1-2FA`、`3-2FA`、`5FA`、`1-4FA`、`3-4FA` 均形成各自 `-13/-14` 身份并绑定各自外线。代表实例为 `1FA-13 → 1QD3 / 233CE / EN2-df46...`，`1FA-14 → 233CB / EN2-0809...`；全部 `internal_connectivity_inferred=false`、`electrical_union_eligible=false`。
- 精确成员和旋转 `37°`、缩放 `1.8×` 的未见 fingerprint 均按几何命中；保持实体数量但偏移执行器中心杆的近似负例不命中。

### `A$C5C9C7C64` — LVS-CB 接地三排组件整体忽略

- 来源：P001 `04 交流回路图1.dwg`，代表 handle `112A6`，坐标 `(40.0,220.0)`，fingerprint `346f8b01c9cf292256cf0fecbd3c680e5e79471cfe21420fb1a2d311ed20007e`；同定义另见 `114FB`，并见于 `05 交流回路图2.dwg` 的 `21681/21799`，合计 4 个实例。
- 人工裁决：红框内完整 `LVS CB` 组件整体 IGNORE。三排机构、三个接点、左侧共用竖线、底部横线、接地子件及全部可见引线均无映射和联通意义；附近 `1ID7/1ID8/1ID9` 不得被绑定为该组件端点。
- 泛化族为 `electrical.nonconnective_grounded_three_row_cb_panel_ignored.v1`，严格子规则 `grounded-three-row-repeated-mechanism-panel-v1`。父级必须同时满足 `4 INSERT + 8 LINE + 3` 个闭合 bulged 接点、三接点等距共线、共享主杆、四排等距横线及三组分离引线与底部通长线的完整相对拓扑。
- 嵌套证据不使用子块名称：三个重复子件的直接几何签名均为 `2 ARC + 3 LINE + 2 LWPOLYLINE`，接地子件为 `4 LINE + 1 LWPOLYLINE`；同时校验三子件位于三组外侧引线端、等间距且同朝向，接地子件位于主杆底端并与重复子件相差 `180°`。
- 精确成员和旋转 `37°`、缩放 `1.8×` 的改名/未见 fingerprint 均输出零端口 IGNORE；保持实体数量但横移任一重复子件的负例保持 review。四个真实实例全部零候选，external attachment、internal connectivity 和 electrical union 均为 false。

### `A$C6A636705` — B+/B- 闭合电缆套管图形整体忽略

- 来源：P001 `07 网络通讯回路图.dwg`，代表 handle `1C298`，坐标 `(345.0,270.0)`，fingerprint `2c4f73274833c1b08e7320666b993c4bd5d3e1eedc7a3931b4075e334b8ec1f7`；同页另有 `1C2AB/1C2BB/1C2CB`，合计 4 个实例。
- 人工裁决：红框闭合胶囊整体 IGNORE。它不截断也不桥接下方实际导线：B+、B- 各自连续且互不连接，两者均不与独立的 `Shielding layer` 路径建立映射。代表 B+ 路径仍为 `TD1 → 1n601`。
- 泛化族为 `non_electrical.cable_sleeve_ignored.v1`，严格子规则 `closed-opposed-semicircle-cable-sleeve-v1`。定义级要求 `2 ARC + 2 LINE`：两圆弧等半径、扫角均为 `180°`、圆心间距约 `4r`，圆弧中点分别朝圆心轴两端向外；两直线等长约 `4r`、互相平行，并在圆心轴法向 `±r` 位置连接两个圆弧的对应端点，构成完整闭合 stadium。
- 真实 replay 中四实例全部零端口、零候选。B+ 源线 `1C28E / EN2-280c...` 与 B- 源线 `1C28F / EN2-26a8...` 保持两个不同网络；原有 `TD1 → 601` semantic pair 保持，结合可见设备作用域 `1n` 得到完整端点 `TD1 → 1n601`。没有 Shielding-layer relation。
- 精确成员和旋转 `37°`、缩放 `1.8×` 的改名/未见 fingerprint 均命中；保持实体数量但使下圆弧向内弯曲的近似负例保持 review。

### `SYMB2_M_PWF270` — 双行信号图形忽略组件

- 来源：P003 `05 信号回路图.dwg`，handle `A22C`，坐标 `(647.5,513.125)`；fingerprint `c983989529487b8e3894fc9dfc0d0acab9c04fe6a66161f36b695e5c80571396`，共 4 个实例。
- 人工裁决：四个机器候选均未接触外部线路，整个组件没有映射意义，整体纳入 IGNORE；不生成端口、external attachment、component mapping、内部连通或 electrical union。
- 泛化族为 `electrical.nonconnective_dual_row_signal_panel_ignored.v1`。严格识别两条等长主线、两组平移重复机构线、两个等半径圆、四个同尺寸小矩形、八个 HATCH，以及仅位于同一行两端的两个等半径圆接点；使用半径归一化距离、方向、平移重复关系和端点布局，支持旋转及统一缩放。
- 同实体数量但任一圆心、重复机构、矩形阵列、接点位置或 HATCH 数量不符时不得自动忽略；fingerprint 仅保留人工来源，不是泛化条件。

### `KK2P` — DK 四端口组件

- 来源：P001 `21 元件接线图1.dwg`，handle `27FDC`，坐标 `(47.5,252.5)`；fingerprint `3f7ef8a0ca8b88180e8cf7094e95355e6b2837e7e598cba3a19ce04e6445620a`。
- 上方圆圈内实例名经原图确认是 `1DK`；实例名与块内端口号 `1/2/3/4` 组合为完整身份 `1DK-1..4`。
- 四个端口内部互不连通，各自只向外映射：`1DK-1→ZD9`、`1DK-2→1QD5`、`1DK-3→ZD1`、`1DK-4→1QD1`。
- family 为 `component.external_multi_port.v1`；同类实例必须读取本实例圆圈名称，不得把 `1DK` 固化为定义常量。

### `DGICOM4000-4GX24GE-HV-HV` — 宽体交换机面板整体忽略

- 来源：P003 `11000 站控层网络通信柜/09 交换机接线图1.dwg`，handle `3B840`，坐标 `(220.5111363,170.9591146)`；fingerprint `9ab7144823696cf159b562ccd4a64c5801bdf99275c605494d4964302cc04bd1`，队列观测 4 个实例。
- 人工裁决：整个交换机面板整体 IGNORE。`P1..P24`、`GE1..GE24`、`GX25..GX28`、Console、FAULT、PWR1/PWR2、`+/L`、`-/N` 和 GND 均不建立通信或电气映射；不生成端口、external attachment、内部连通或 electrical union。
- 泛化族为 `communication.equipment_panel_ignored.v1`，严格子规则 `wide-ge-gx-power-switch-panel-v1`。定义级联合验证完整 GE/P/GX/T/R/Console/FAULT/PWR 文字阵列、24 个以上近方形接口单元、8 个等半径共线圆的 `3.36r/4.84r` 交替间距、至少 40 个闭合 bulged 接口轮廓及约 `4.22:1` 的宽体比例；支持旋转和统一缩放，不依赖定义名或 fingerprint。
- 负例边界：缺少任一完整 `P1..24`/`GE1..24` 标签、任一光口圆偏离共线轴或交替间距、接口单元不足、实体密度或宽体比例不符时不得自动忽略。
- 真实验证：精确成员输出 `HUMAN_CONFIRMED_MEMBER / IGNORE / ports=[]`；同一真实定义替换为未见 fingerprint 后输出 `MATCHED / IGNORE / ports=[]`。原图重跑中 handle `3B840` 与该 fingerprint 的实例级 network candidates 均为 0。
- whole-panel IGNORE 权威必须由所有嵌套后代继承：candidate/binding 阶段沿 `nested_path` 逐级解析全部祖先，只要任一祖先 proposal 经统一 classify/evaluate 得到 `behavior_mode=IGNORE` 且 `suppressed_by_policy=true`，该后代不得生成 symbol-port network candidate。此规则不依赖 DGICOM 名称、child 名称、child fingerprint 或固定层级；`A$C08084C19`、`A$C7E971F70` 仅是暴露该通用缺陷的真实样本，不登记为记忆式忽略成员。
- 祖先继承边界：`TABLE_CONTAINER`、`EXTERNAL_PORTS_ONLY`、`TERMINAL_NO_INTERNAL`、`WIRE_PRIMITIVE`、`REVIEW_ONLY` 等非 `IGNORE` 行为不得抑制嵌套 child；尤其必须保留背板表格、嵌套端子和多端口组件既有提取链路。
- post-change 真实验证：独立重跑 P003 `09/10 交换机接线图`，两页 DGICOM proposal 均保持 `communication.equipment_panel_ignored.v1 / wide-ge-gx-power-switch-panel-v1 / HUMAN_CONFIRMED_MEMBER / IGNORE / ports=[]`。`A$C08084C19` 与 `A$C7E971F70` 的 8 个 placements 仍保留 definition proposal/census，但 network candidates 合计为 0；目标 child 在 topology decisions/applications、semantic nodes/relations/evidence/constraints、endpoint witnesses、network members 中均为 0。

### `SYMB2_S_PWF24a` — 双圆接点标记整体忽略

- 来源：P003 `11000 站控层网络通信柜/06 交换机回路图1.dwg`，handle `119F7`，坐标 `(287.3410777,85.0)`；fingerprint `a662de3d914d6b22aa1b0d6f9e4a0a090de1e0cd8461224860fc8199cba2bf0f`，队列观测 2 个实例。
- 人工裁决：整个组件整体 IGNORE。上方带横杆的大圆、下方小圆及两者之间/下侧可见线路都不产生端口、external attachment、component mapping、内部连通或 electrical union。
- 泛化族为 `electrical.nonconnective_circle_contact_marker_ignored.v1`，严格子规则 `diameter-circle-offset-contact-marker-v1`。完整定义要求 `1 CIRCLE + 2 LINE + 1` 个闭合 bulged 圆接点 `+ 1 HATCH`：横杆必须是大圆直径；径向线从大圆边界连接小圆圆心；大圆/小圆半径比约 `2:1`，圆心距约 `2.5R`，径向线长约 `1.5R`，且与直径正交。所有关系按半径、向量和端点归一化，支持旋转和统一缩放，不依赖 PWF 名称或 fingerprint。
- 负例边界：小圆偏离径向轴、横杆不穿过大圆圆心、径向线未绑定大圆边界或小圆圆心、半径/距离比例或实体数量不符时不得自动忽略。
- 真实验证：精确成员输出 `HUMAN_CONFIRMED_MEMBER / IGNORE / ports=[]`；同一真实定义替换未见 fingerprint 后输出 `MATCHED / IGNORE / ports=[]`。原图重跑中 handle `119F7` 和该 fingerprint 均无实例级 network candidate。

### `A$C38910F98` — 面板内部水平线精确忽略

- 来源：P001 `11 非电量开入回路.dwg`，handle `2CF8F`，坐标 `(160.0,250.0)`；fingerprint `cd0346ad16ba285a9950c48c0611017efcd9490cc6d6d78c81442860902a75cf`，测试集仅观测 1 个实例。
- 人工裁决：红框内 50 单位水平线整体 IGNORE，左右两端明确不连通；不生成端口、external attachment、component mapping、内部连通或 electrical union。
- 安全边界：本项只使用精确 fingerprint 人工策略 `non_electrical.panel_internal_line.v1`，不建立“单条 LINE 即忽略”的几何泛化。当前 P001/P003 测试集共有 2 个仅含单条 LINE 的块定义：本项水平线和同页 `A$C72EB63F1` 垂直 180 单位线；后者未获裁决并保持 review。P003 无此类定义。
- 线网隔离：该嵌套 LINE 仅存在于 `primitive_segments`，未进入普通 `lines.parquet` 或 wire network；精确策略再清空它的符号端口和实例候选，因此不会连接左右网络。替换为未见 fingerprint 的同几何定义必须保持 `REVIEW_ONLY`，不得自动忽略。
- 未来如需泛化，只能基于完整设备大矩形的实例级包含关系、框架身份和内部线布局另建上下文规则，不能仅凭单线长度、方向、名称或坐标判定。

### `A$C72EB63F1` — 面板内部公共母线按审计范围精确忽略

- 来源：P001 `11 非电量开入回路.dwg`，handle `2CF90`，坐标 `(210.0,70.0)`；fingerprint `ae788d00fab7abcd6190c917d8f4c42e8613320b78143443b3849d7e9aea6e72`，测试集仅观测 1 个实例。定义内部是一条本地 `(0,0)→(0,180)` 的垂直 LINE。
- 原理事实：该垂直线在真实电气原理上是公共母线，本应连接相交的多条水平回路。
- 当前审计裁决：现阶段不校验该母线连接的各支路，因此将完整母线按审计范围整体 IGNORE；V2 不连接上下端，也不连接任何相交水平线路，不生成端口、mapping、network 或 union。该裁决是范围排除，不能解释为真实图纸中母线物理不导通。
- 安全实现：仅对精确 fingerprint 应用 `non_electrical.panel_internal_bus_excluded.v1`，不建立垂直单线几何忽略族。未见 fingerprint 的同几何垂直线必须保持 `REVIEW_ONLY`，普通导线和母线仍可进入拓扑分析。
- 真实验证：精确成员输出 `HUMAN_CONFIRMED_MEMBER / IGNORE / ports=[]`，handle `2CF90` 和目标 fingerprint 的 symbol-port network candidates 均为 0；同页水平精确忽略保持有效。

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

### `CD-WSK-H-J-G` — 上方圆圈命名的八独立端口组件

- 来源：P001 `21 元件接线图1.dwg`，handle `2739F`，坐标 `(133.75,52.5)`，fingerprint `d1202915a0dee8f65d4024cd3a144cf7de7147bacc5916dc7cd4b0ebad124bda`；当前队列观测 1 个实例。
- 人工裁决：左右共 8 个端口只分别向外连接，内部全部不连通。上方圆形标签内部文字是本实例名，完整端口身份必须组合为“实例名-端口号”；不得把定义名 `CD-WSK-H-J-G` 固化为实例名，也不得通过设备内部功能图形建立任何端口间 connectivity 或 electrical union。
- 泛化族为 `component.external_multi_port.v1`，严格子规则 `eight-numbered-side-contact-panel-v1`。完整定义要求 `13 LINE + 17 LWPOLYLINE + 31 TEXT + 1 INSERT`：八个等半径闭合 bulged 接点形成旋转不变的 2×4 阵列，八个等尺寸方形端口格形成对应 2×4 阵列，数字 `1..8` 分别绑定唯一接点；另有完整外框和直接子图元 census `12 LINE + 1 LWPOLYLINE` 的内部功能插入件。
- 端口提议直接取八个圆接点中心，并沿两列阵列的外法向确定左右 outward direction。实例名只允许从端口阵列上方、中心轴附近的圆形标签位置读取；设备内部 `L/N` 等单字母功能文字不能抢占实例名。每个端口只接受本侧精确外延线路及其网络附近的结构化端点文字。
- 真实 replay 中圆形标签实例名为 `K`，输出 `K-1..K-8`。实际有外延证据的映射为 `K-3→JR-1`、`K-4→JR-2`、`K-5→KZKK-2`、`K-6→KZKK-4`；`K-1/K-2/K-7/K-8` 在该实例无外线，保持 label-only，不虚构映射。全部八行 `internal_connectivity_inferred=false`、`electrical_union_eligible=false`。
- 精确成员与旋转 `37°`、缩放 `1.8×` 的未见 fingerprint 均命中；保持全部实体数量但偏移任一外侧接点的近似负例不得进入该族。

### `JR-01` — 上方圆圈命名的双圆双独立端口组件

- 来源：P001 `21 元件接线图1.dwg`，handle `273A5`，坐标 `(207.5,39.5)`，fingerprint `4045826f53f309b218e477ae0163c871aa498b1e0f5c11bf377ee81d26820279`；当前队列观测 1 个实例。
- 人工裁决：上方圆形标签内 `JR` 是实例名。端口 `1/2` 内部互不连通，只分别向外形成 `JR-1→K-3`、`JR-2→K-4`；不得由外框、两个大圆或编号邻接推断内部 conductivity 或 electrical union。
- 泛化族为 `component.external_strip_two_port.v1`，严格子规则 `horizontal-numbered-two-circle-box-v1`。完整定义要求 `2 CIRCLE + 3 LWPOLYLINE + 2 TEXT`：两个等半径大圆横向成对，两个等半径闭合 bulged 小接点分别位于对应大圆的同一外法向，数字 `1/2` 唯一绑定各自大圆/接点，另有长短边比约 `2.5:1` 的完整外框。
- 专用提议器只取两个小接点中心，outward direction 从对应大圆圆心指向小接点；旧 free-end 算法产生的四个外框角端口必须被完全替换。实例级读取端口阵列上方最近的短字母圆圈名，组合 `JR-1/JR-2`，再使用已有 component mapping 证据绑定 `K-3/K-4`。
- 真实单页 replay 输出 `HUMAN_CONFIRMED_MEMBER / horizontal_numbered_two_circle_box_ports_v1 / EXTERNAL_PORTS_ONLY`，并持久化 `JR-1→K-3 / PCS0001`、`JR-2→K-4 / PCS0002`；两行 `internal_connectivity_inferred=false`、`electrical_union_eligible=false`。
- 精确成员与旋转 `37°`、缩放 `1.8×` 的未见 fingerprint 均命中；保持实体数量但横移任一小接点的负例不得进入该族。

### `A$C1DEA74F8` — 窄框四级锯齿元件整体 IGNORE

- 来源：P001 `21 元件接线图1.dwg`，nested handle `27268`，world `(143.75,40.0)`，fingerprint `0b72b0b02116d00c0a8c196e1b45c6d693450315f37e77ba636c0a03065f3785`。人工确认完整图形整体忽略；上下不是端口，无外部映射、无内部联通，禁止 electrical union。
- 泛化族为 `electrical.nonconnective_vertical_zigzag_element_ignored.v1`，严格规则 `narrow-frame-four-cell-zigzag-v1`。完整定义必须为 `12 LINE + 1` 个闭合矩形 LWPOLYLINE：窄框长短比约 `2.801`，上下两条等长轴向引线各约框长 `0.2143`；框内五个等距轴向层级由四条同斜率跨框对角线占据，三个内部层级各有两条重合全宽横杆连接相邻对角线的异侧端点。
- fingerprint 仅登记人工 provenance。规则在矩形局部坐标中验证比例、层级、方向和端点绑定，支持旋转、反射与统一缩放；未见 fingerprint 的 `37° / 1.7×` 正例命中，保持同样 `12+1` primitive 数量但移动一条重复横杆的负例不命中。
- fresh 单页 replay 中 handle `27268` 为 `HUMAN_CONFIRMED_MEMBER / IGNORE / ports=[]`，且几何证据为 `narrow-frame-four-cell-zigzag-v1`；目标 candidates、topology、semantic、endpoint witness、network member 全为 0，全部 connectivity/union 标志为 false。
- 当前回归必须同时覆盖 P001 上述保护柜项目与完整 P003 `F:\workspace\XJToolkit\test\【出原理图】N2604HBJ20732J合同` 根目录（25 个柜体项目、450 张 DWG），不得将 P003 缩减为单个柜体子目录。

## 7. 待人工裁决区

本文件不保留历史机器猜测。清理后由最新 P001/P003 全量分析重新生成待裁决清单；只有用户明确回答后的条目才会移入以上“已确认”章节。

## Phase166 已确认泛化裁决

- `PWF166`：接地结构整体 IGNORE。六触点与四触点为两个独立完整几何 subtype；均为零端口、零映射、零联通、禁止 union，不以名称或 fingerprint 进行分类。
- `FJL-25-2A` / Mirror：只保留实际接线的 pins `1/2`，二者内部不连通，分别绑定本侧外线；外侧装饰触点不作为端口。
- `KK1P/KK2P/KK3P+OF11-12`：只保留主端口 `1..2/4/6`，以“上方实例名-端口号”形成身份并绑定同侧外线；OF 辅助区 `11/12/14` 整体不参与端口、映射或联通。
- `PWF172` LED/二极管发光箭头与 `PWF216` 窄框/底部斜线结构：完整图形整体 IGNORE，零端口、零映射、零联通。两者均已用完整相对拓扑在全部出现页 replay，不再进入人工队列。
- `DGICOM3000-4GX8GE-HV`：沿用 DGICOM 完整通信面板整体 IGNORE。GE/GX、Console、PWR/GND、光纤圆阵列和面板内部端口图形均不建立通信或电气映射；完整面板零端口、零联通、禁止 union。
# Phase 157-160 geometry contracts

PWF168 (58325f4a...), PWF209 (7cd4cc6f...), and PWF163 (dc5a2723...) are
whole-symbol IGNORE families. PWF175 (2d7264d3...) is a named isolated
two-port family: the upper instance name composes with native pins 1 and 2,
which bind only to their measured same-side routes. Fingerprints are retained
as provenance only; geometry matching is invariant to translation, rotation,
uniform scale, and reflection. All four prohibit inferred internal
connectivity and electrical union.
- Phase 157-160 repair: initial implementation used post-filter LWPOLYLINE counts and missed complete raw definitions. Replacement uses raw contacts plus normalized relative geometry; exact fingerprints are provenance only.
- Final full-root replay covers 13 cabinet units, 40 unique source DWGs, and all 421 real instances. PWF168=206, PWF209=89, and PWF163=63 are geometry-confirmed `IGNORE / ports=[]` with zero candidate/topology/semantic/witness/network artifacts.
- PWF175=63 instances emit exactly 126 outward ports. All 126 bind a same-side external line and compose a device identity; numeric designators such as `7QK` and subtype-scoped short alpha name `DYQK` both produce `instance-pin` identities. Internal connectivity and electrical union remain false.
- Switch-class IGNORE authorization (121 instances): eight supplied fingerprint prefixes are provenance only. All accepted unseen members must pass normalized relative geometry; ports, mapping, attachment, internal connectivity, critical eligibility and union are zero. PWF166 six-contact and four-contact variants are mutual geometry negatives.
- WFS polarity component: complete rounded body with two axial contacts and native `+/-` markers is an external-only two-port component. Compose the nearby instance designator with each polarity pin; each pin maps only to its own attached external line/network. The two pins never connect internally and never participate in electrical union. Fingerprint `888624f4...` is provenance; the classifier uses complete relative geometry.
- `ELXAL5-B11-209B`: both known fingerprints (`caa42087...`, `e91786a7...`) implement the same complete four-independent-port geometry. Native pins `11/12/13/14` compose with the instance name and map only to their own external line when present; unwired pins remain identities without fabricated mappings. All four are internally isolated/no-union. Same name does not authorize fingerprint merging; both are separately retained as provenance members of one strict geometry subtype.
- Switch IGNORE generalization addition: the complete PWF85 three-contact selector/slash artwork and complete PWF200/PWF204/PWF235 actuated-contact assemblies are electrical switch graphics under the repeated human authority “whole switch artwork IGNORE, internally non-connective, no ports or mappings.” Each geometry remains a separate strict subtype; this authority must not absorb outward 13/14 components whose ports were explicitly retained.
## Phase 166 historical-arbitration self-iteration: isolated components

- `SYMB2_M_PWF115`: four orthogonal basic-terminal contacts around a circular body. Emit four outward ports only; no pair is internally connected or union-eligible.
- `SYMB2_M_PWF98`: two axial contacts around a round body. Emit the two external ports independently; visible body geometry does not authorize an internal bridge.
- `SYMB2_M_PWF218`: two-contact dual-frame mechanism. Left/right ports attach only to their own external route; internal frame/diagonal artwork is non-conductive.
- `SYMB1_M_30401`: triangular-body axial component. Top/bottom contacts are independent external ports; the triangle does not connect them.
- `SYMB2_M_PWF259`: complete rectangular/diagonal mechanism is IGNORE. The four old proposals were bbox extrema rather than physical ports; emit no port, mapping, internal connectivity, or union.
- Engine acceptance requires complete normalized topology, transformed unseen positives, displaced near-negatives, and replay of every occurrence page. Exact fingerprints record adjudication provenance only.

## Phase 166 communication and routing markers

- `SYMB2_S_PWF3`: complete RX/TX remote-interface marker is IGNORE; its contact, round body and centre slash are recognition geometry only.
- `SYMB2_S_PWF303`: complete RX/ST parenthesis-contact optical marker is IGNORE and creates no communication mapping.
- `A$C3CE477D4` / `A$C7ECC553D`: the complete two-semicircle/two-parallel-line capsule is routing/line-break artwork, not a two-port component. Emit no ports, bridge, mapping, connectivity or union.
- Acceptance requires the complete relative topology; generic circles, generic two-contact symbols and ordinary parallel conductors are near-negatives and must not be suppressed.

## 2026-07-16 XJDZ numbered and functional contact arrays

- `XJDZ9-02 / XJDZ4-18 / XJDZ9-06 / XJDZ9-10` are complete numbered round-contact arrays. Every native pin `1..N` composes with the upper instance designator and maps only to its own outward same-side route. Pins are mutually isolated; no internal connectivity or electrical union is permitted.
- `XJDZ9-04-2N4-009` is the functional variant with exactly 11 native pins: `1..8、C+、G-、R-`. All 11 are mutually isolated and outward-only. The instance name is the upper round-tag value (`1-21KK / 2-21KK / 3-21KK` in the verified pages), not a side endpoint label.
- Human-confirmed example: `1-21KK-1 → 1-21ZK-2`. The same contract applies to every pin: `instance-pin → same-side external endpoint`; absent external wiring remains an unwired identity and must not create an internal bridge.
- Geometry authority is the complete body/contact/text topology, not the fingerprint: the pure-number family is a regular `2×N` grid; the functional family is a five-row pair grid plus one extra `R-` row. Both require one repeated outer contact per circle and one much larger rounded body. Rotated/scaled/reflected complete members match; displaced same-census near-negatives remain review.
- Full replay evidence: pure-number arrays cover 14 instances / 220 pins; XJDZ9-04 covers 3 DWGs / 7 instances / 77 pins. Every definition row is `MACHINE_GEOMETRY_RULE+HUMAN_EXACT_MEMBER`; internal connectivity and union are zero.
- S0025 structural terminal clarification: definition-owned BORDER routes preserve the complete logical endpoint and native definition pin (for example `3-21CD6 -> XJDZ9-02-2B4-001:8` and `1-21CD6,1-21ZK-9 -> XJDZ9-02-2B4-001:7`). Full `CD11 -> CD8` identities are also preserved. These are mapping facts only; they never connect XJDZ pins internally.
- Cardinality is physical-instance scoped: equal `XJDZ-definition:pin` strings from distinct INSERT handles are separate component instances. Multiple sources targeting the same pin on one INSERT remain review authority.
## Phase 176 — B3 三列表端子与 A2 背板裁决（2026-07-17）

- 三列表端子由“说明”锁定表结构；表头实例名与中间列端口号组合为完整逻辑端点，例如 `1UD-1`。
- 同一逻辑端口可以分别映射左右两侧外部端点，例如 `1UD-1 -> 1ZKK1-2`、`1UD-1 -> 1n2001`；这些映射不表示组件内部端口互联。
- 空白端口不建立映射；不得因同 y 或宽松 x 容差借用邻表端点。
- 相邻端子表可共享同一 `n` 端点，但必须由同 y、同端口号或完整 reciprocal 中心端子表闭环证明。
- BI/电压/开入/开出插件背板按独立多端口组件处理；各 pin 仅向外映射，内部不联通，不建立 electrical union。

## Phase 179：设备面板 IGNORE 回灌与 TS3000 结构化端口表（2026-07-18）

- 完整通信设备面板属于已确认的整体 IGNORE。普通 Pair 只有在同一页、同一定义、已批准实例 handle 且完整几何行为权威成立时，才可被面板拥有的几何或严格 MARK callout 阴影；不从面板丝印、HD/BCD 引脚格或内部图形建立通信/电气映射、端口、内部联通或 union。
- MARK callout 不是名称记忆规则。必须同时具备水平 MARK 线、裸数字侧、与面板 bbox 的 x 重叠、受控设备型号文字、作用域内 `1-40n` 类标签和限定距离；缺任一证据继续保留 Pair review。Proposal fingerprint 只作 provenance，不能单独授权 IGNORE。
- `TS3000-Z01` 不是设备面板 IGNORE，而是结构化多端口组件表 `structural.component_port_table_container.v1`。在同一 source block 中，作用域实例前缀、bank 槽号和两位原生端口号组合成完整逻辑端点，再映射同一行外部 TD 端子，例如 `1-26n432 -> 1-26TD46`、`2-26n432 -> 2-26TD46`。
- TS3000 每个端口独立向外映射，端口之间始终不连通、不建立 electrical union；有表格单元但无外部 TD 文本的行保持无映射，不得伪造端点。模型名 `TS3000-Z01` 仅作容器 provenance，不作为端口身份。
- 真实 fresh replay：`.tmp/phase179_full_533_fresh2` 覆盖 28 个项目、533 张有效 DWG、0 incomplete；`.tmp/phase179_full_533_audit2` 共 118 条（117 review、1 minor、0 critical）。TS3000 S0014/S0015 共 288 条独立映射，两个项目页各 144 条；8000/9000 仅保留四条真实 S0004 `1201/1204` 开端审核。
- 设备面板回放共阴影 221 条普通 Pair（214 条完整面板几何、7 条严格 MARK callout），fingerprint 与最终 proposal inventory 全部存在且一致；较 Phase178 移除 15 条、无新增 issue。上述结果只证明本轮合同闭环，剩余 review 行仍须后续几何/跨页证据循环，不得整体静默。

## Phase 180：既有端点裁决在 XD/YD/LD 信号页的泛化回放（2026-07-18）

- 本阶段没有新增器件内部联通裁决；沿用既有规则：端点只与实际同侧外延线路建立映射，组件端口之间不因图形或共享文字建立内部联通/electrical union。
- `XD / YD / LD` 在中央、远动、录波信号输出页表现为同一紧凑线路端点族。机器规则必须同时验证二次原理图路由、水平/网格线路、完整端点语法和 X/Y 均不超过 4 的端点贴合；不能按页名、单独文字或 fingerprint 记忆。
- `VD` 等非目标器件端点不属于这一通用线路候选。PAC S0014 仍由独立双端组件模型输出 `1F1-1 -> 1VD1`、`1F1-2 -> 1701` 等 8 条映射，全部 non-union。
- 全量回放新增 149 条结构同构的 YD/LD 线路映射，移除 29 条 PAC 单边误报且新增 issue 为 0；S0022 的 7 条超长误合并线路仍保留 review。该结果证明几何泛化生效，不授权静默其他 missing-side 或 many-to-one。
