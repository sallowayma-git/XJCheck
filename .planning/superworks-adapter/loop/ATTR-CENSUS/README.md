# ATTR-CENSUS：SuperWORKS 出图中未被识别引擎使用的端子排 / 导线属性普查

只读调研。未修改 `src/`、`tests/`，未执行 git，未改动冻结 DXF 缓存与 `corpus_manifest.json`。
中间产物（逐文件 JSON，合计约 360 MB）保存在会话临时目录，本目录只保留结论、`details.json` 与 `tools/`。

## 1. 结论

### 1.1 导线（wire）：有直接可读的“去向”，但在 XRECORD 字典里，不在导线实体上

- 导线 LINE / LWPOLYLINE 本体的 XDATA 只有导线类型 `LD_LINE_STYLE`（原理图 265 页），不含线号、端点句柄或去向。
- 去向写在两类 XRECORD 中，均未被识别引擎读取：
  - **原理图导线两端记录** `LD_SYMB2LOGGEN_DICTIONARY` 下的 XRECORD（53857 条，821 页）：`CONNECTLINEHANDLE` 给出导线句柄，`PART2_1` / `PART2_2` 给出两端的设备名、引脚、端子实体句柄与类别，`LINENO` 给出对端端子句柄与端口，`LINESTYLE` 给出导线类型。
  - **元件引脚—导线记录** `LD_PARTCONNECTLINE`（挂在元件 INSERT 的扩展字典上，28435 条，359 页）：每个逻辑端号给出导线句柄（直线句柄）、接线文字（如 `1YD2`、`& 1QD4`）、对端元件与端子号、跨页线号。
- 仅 `LINENO` 与 `CONNECTLINEHANDLE` 被用于装置端子绑定（`extract/terminal_port_bindings.py`），其余字段均未用。

### 1.2 端子排（terminal strip）：去向已可直接读到，且已经被使用

- 端子行的去向文字已由 `LDDZ_LEFT/RIGHTTEXT_HANDLE`（及 `_2` 分支）读取（`extract/superworks_semantics.py` 约 467 行），覆盖 26544 行中的 19076 行（71.9%）。
- 未用的端子排属性大多冗余：`LD_DZPNO_DXLX_OUT` 与已用的 `LD_DZPNO_DXLX` 在 6066/6066 个可比行上完全相同；`DZ_SERIALNUMBER_DZLX` 的“试验端子”与已用的 `LD_DZPNO_DZLX` 折线在 5973/5973 行上一一对应。
- 唯一有实际价值的未用字段是 `DZ_SERIALNUMBER_NAME`（端子排名），它用于修正身份错误（见 4.2）。
- 元件侧 PCL 的对端端子只新增 19 行去向（现有去向已覆盖大部分行），端子排侧增量很小，主要用途是与原理图侧交叉印证。

### 1.3 对匹配率的主要影响

- 未消费端口共 4727 个（`unconsumed_port_diagnostics.json`，与 strict consumption 94.28% 口径一致）。其中 **4667 个（98.7%）** 能在原理图导线两端记录中按（端子句柄, 引脚）精确找到，**4627 条**导线记录触及未消费端口，**68 条**两端均为未消费端口。
- 跨页线号指向的对侧 装置端子 实例：PCL 线号中的句柄在被指页中 **99.5%** 可解析，覆盖 963 个未消费端口（20.4%）。

## 2. Top 10 未使用属性

| 排名 | 键名（载体） | 全语料计数 | 语义 | 可提升的匹配类型 | 证据 |
|---|---|---|---|---|---|
| 1 | `LD_SYMB2LOGGEN` 导线两端记录（OBJECTS XRECORD：LINENO, CONNECTLINEHANDLE, PART2_n, LINESTYLE） | 53857 条 / 821 页 | 导线句柄 + 两端设备引脚 + 端子实体句柄 + 导线类型 | 二次原理图端口配对（去向），补 `no_matching_production_pair`（3934） | 未消费端口端点精确命中 4667/4727（98.7%）；有去向的 2227 个端口中，可比较的 1869 个另一端与端子排去向一致 1547 个（82.8%） |
| 2 | `LD_PARTCONNECTLINE`（元件 INSERT 扩展字典 XRECORD：逻辑端号, 线号, 直线句柄, 接线文字句柄, 对端元件） | 28435 条 / 359 页 | 元件引脚的对端端子、导线句柄、跨页线号 | 元件侧去向；与 #3 联合做跨页端子直连 | 对端端子在同项目端子排命中 19061/23894（79.8%）；未消费端口精确覆盖 963 个，身份一致 774/812（95.3%） |
| 3 | `LD_PARTCONNECTLINE` 线号中的跨页句柄（`未定义<H>:<端口>_<页号> <页名>`） | 28203 条（跨页形式） | 对侧 装置端子 INSERT 的句柄与端口，页名 | 跨页端子实例直连（仅定位，不依赖端子文字） | 句柄在被指页中存在 26325/26446（99.5%）；覆盖未消费端口 963 个，另有 505 个仅实例句柄相同（端口序号待定） |
| 4 | `LD_LINE_STYLE`（原理图导线，XDATA） | 13724 个实体 / 268 页（原理图 265 页） | 导线类型：电流回路线、电压回路线、四芯屏蔽线、接地线、以太网线等 | 配对候选的导线类型约束 | 未消费端口接触导线中 402/4731 带该属性（8.5%）；约 24% 实体为空 |
| 5 | `DZ_SERIALNUMBER_NAME`（端子行 XDATA，端子排名） | 26544 行 / 248 页 | 端子行所属端子排的真实名称 | 修正端子身份（表头续接说明），提供 PCL 对端端子的索引键 | 表头为“上接XXX”的行 3154 条（11.9%），流水线身份错误（如 `上接1QD1516`，真实为 `1QD16`）；直接影响未消费端口 75 个 |
| 6 | `LD_SHOW_LINE` / `LD_SHOW_TYPE`（跨页标签 MTEXT → LINE / 装置型号 TEXT） | 800 页 | 跨页标记标签所属的导线、对侧装置型号（如 `WXH-813-D1F`） | 跨页标记 → 导线 / 装置 的显式关联 | 指向 LINE 5787、TEXT 5205；未量化（语义待验证） |
| 7 | `LD_SYMB2_InsideLABEL`（符号 INSERT → 标签 MTEXT，如 `1n`、`1-21n`） | 71932 个实体 / 682 页 | 跨页符号的内部标签 | 跨页标记识别，辅助 PCL 对端 `n` 标记的页归属 | 有效指向 MTEXT 14703；未量化 |
| 8 | `LD_ GROUPPARTXRECT_TEXT` / `_XRECT`（标签框 LWPOLYLINE ↔ MTEXT） | 814 页（二次原理图 793） | 跨页标记的外框与标签 | 跨页标记几何识别 | 指向 MTEXT 5514；未量化 |
| 9 | `LD_SYMB1LIB_TERMTEXTPOINT`（符号库端子文字锚点） | 832 页（二次原理图 787） | 端子文字的定位点 | 未识别引脚文字（`unresolved_pin_text` 794）的定位 | 指向 LWPOLYLINE 4589；未量化 |
| 10 | `LDPARTLAYT_CIRCLE_HANDLE`（元件 INSERT → 引脚圆 CIRCLE） | 178 页（元件接线图 165） | 元件引脚圆的几何位置 | 元件接线图引脚几何锚点 | 指向 CIRCLE 7124；未量化 |

补充：`LD_SYMB_TERMAUTODIM`（端号自动标注 YES 179 条）与 `DZCONNECT_ELEMENT_CLASS`（装置端子 / 端子 / 线圈 / 接地）未量化，列为备选。

## 3. 方法与覆盖

- **全量扫描，非抽样**：1745 页（77 项目）全部逐个只读打开。扫描范围包括模型空间、全部块定义（20638 个）、ATTRIB、实体扩展字典、OBJECTS 中的 DICTIONARY / XRECORD / GROUP，以及根字典中的 `LD_DWG_DICITIONARY`、`LD_SYMB2LOGGEN_DICTIONARY`。
- **页型**（来自 round12 `pages.parquet`，按 file_id 与文件名关联）：二次原理图 839、屏端子图 248、背板表格型图 182、元件接线图 172、封面/目录 154、屏面布置图 118、表格型图 28、背板接线图 4。
- **项目家族**（按 `input_root` 归类）：正式典设(test) 1080 页、N2604 合同 450 页、变压器测控柜 107 页、110kV 变压器保护柜 77 页、PAC-885G-H 31 页。
- **代码使用核对**：字面量 grep（`src/dwg_audit/**/*.py`）加人工核对。字面量 grep 会漏掉 f-string 与前缀/正则拼接，例如 `LDDZ_{side}TEXT_HANDLE{branch}`（`superworks_semantics.py:467`）与 `LD_SYMB2_TERM_TEXT_` 前缀；`details.json` 中 `appids[*].code_status` 仅作索引，发现项的 `code_usage` 为人工核对结果。

## 4. 各发现明细

### 4.1 F1：`LD_SYMB2LOGGEN` 导线两端记录（排名 1）

- 载体：OBJECTS 中 `LD_SYMB2LOGGEN_DICTIONARY` 下的 XRECORD（代码 1 键值交替）。
- 计数：53857 条，覆盖 821 页（二次原理图 797、表格型图 24）；家族分布：正式典设 34142 条（518 页）、N2604 12704 条（194 页）、变压器测控柜 3888 条（59 页）、110kV 2332 条（38 页）、PAC-885G-H 791 条（12 页）。
- 字段：`CONNECTLINEHANDLE` 解析为 LINE（49074 条中的导线本体；其余 4783 条句柄缺失）；`PART2_n` 的 `||` 分隔串，依次为设备名、引脚、序号、侧别、符号块名、端子实体句柄、类别（端子 / 装置端子）、方向；端子实体句柄在同文件中 89794/89795 解析为 INSERT。每条记录端点数：2 端 28723 条，1 端 22684 条，3 端及以上约 2450 条。
- 样例（句柄 + 页面）：
  - `p000/F0004 04 交流回路图.dwg`，XRECORD `13AFD`，导线 `E2F2`，LINESTYLE `电流回路线:*`，端点 `1ID` 第 3 脚（端子 `E301`）与 `1n` 第 2 脚（装置端子 `E30E`）。
  - `p038/F0005 04 交流回路图1.dwg`，XRECORD `20F08`，导线 `112A4`，端点 `1ID` 第 1 脚（端子 `112A0`）与第 2 脚（端子 `1129E`）。
  - `p051/F0004 04 交直流回路图.dwg`，XRECORD `42675`，导线 `33505`，端点 `ZD` 第 3 脚（端子 `334F9`）与 `1-25DK1` 第 3 脚（端子 `334FF`）。
- 代码使用：`LINENO` 与 `CONNECTLINEHANDLE` 仅用于装置端子绑定（`terminal_port_bindings.py`，`_terminal_xrecords` 读取 `document.objects.query("XRECORD")`）；`PART2_n` 只作为绑定校验的 token；`LINESTYLE` / `LINECOLOR` / `LINEDIAMETER` 未用，且后两者全语料均为空。
- 匹配潜力：二次原理图未消费端口的配对与去向。未消费端口中 4367 个的接触导线出现在此类记录中（92.4%）。
- 一致性检验：`check_loggen_identity.py` 以端子排去向索引检验另一端。例如端子排行 `7UD/10` 的去向文字为 `1ZKK-1`，对应记录另一端为 `1ZKK` 第 1 脚；`7UD/12` 对应 `1ZKK-3`。全量：有去向的端口 2227 个，可比较 1869 个，一致 1547 个（82.8%），不一致 322 个（多为多端记录与区间身份）。
- 注意：导线类型非空率仅约 6%（3460/53857），只能作为约束。

### 4.2 F2：`LD_PARTCONNECTLINE` 元件引脚—导线记录（排名 2、3）

- 载体：元件 INSERT 的扩展字典 XRECORD（OBJECTS 中有同名镜像）；代码 1 字符串按 10 段一组，依次为 `逻辑端号 / 线号 / 导线类型 / 线号文字句柄 / 导线颜色代号文字句柄 / 接线文字句柄 / 直线句柄 / 接地图块句柄 / 接地文字句柄 / 对端元件`。
- 计数：28435 条，359 页（元件接线图 172 页 9655 条；背板表格型图 182 页 18584 条；背板接线图 4 页 166 条；二次原理图 1 页 30 条）。家族：正式典设 17341、N2604 7275、变压器测控柜 2070、110kV 1281、PAC-885G-H 468。
- 字段填充：对端元件 28259（99.4%）、直线句柄 28280（99.5%，其中解析为 LINE 27967）、接线文字句柄 28104（解析为 TEXT 27960）、线号 28259（跨页形式 28203）、导线类型 9301（33%）、接地图块句柄与接地文字句柄各 155。线号 字段中的句柄在同文件内为 MISSING（属于跨页引用，预期）。
- 样例：
  - `p000/F0015 15 元件接线图1.dwg`，元件 `B960`（ELXAL5-B11-209B），XRECORD `BB7C`，逻辑端号 `13`，线号 `未定义8ED7:1_05 交直流回路图`，直线句柄 `11EFF`，接线文字 `& 1QD4`，对端 `1QD` 端子 `4`。
  - `p000/F0015 15 元件接线图1.dwg`，元件 `B9BB`（FEIDIAO-10A-Z-3-AC30），XRECORD `BB5E`，逻辑端号 `E`，对端 `JD` 端子 `11`。
  - `p000/F0014 14 主保护背板接线图.dwg`，元件 `19E6B`，XRECORD `19FB5`，逻辑端号 `101`，线号 `未定义E78C:2_08 信号回路图`，直线句柄 `1A3A4`，接线文字 `1YD2`，对端 `1YD` 端子 `2`。
- 对端端子命中：PCL 的对端元件+端子号与同项目屏端子图的（端子排名, 行文字）匹配，命中 19061/23894（79.8%），未命中 4833 条；其余为跨页标记 `xn` 或非端子对端（4541 条）。
- 跨页线号：解析到被指页中同句柄的实体。在能定位目标页的 26446 次中，26325 次句柄存在（99.5%），121 次不存在；另有 1757 次目标页不在本项目中。被指实体为 INSERT（抽样 12 条中 11 条 `LD_SYMB2_SPECIAL=装置端子`，1 条为 `接地`），端口号对应其 `LD_SYMB2_TERM_TEXT_n` 槽位。
- 与未消费端口的关系：未消费端口全部位于二次原理图（4591）与表格型图（136）。以（实例句柄, 端口号）精确匹配，PCL 跨页引用覆盖 963 个（20.4%），身份一致 616 个（完全相等）+ 158 个（区间写法 `ZD6~7` 起点相符），不一致 38 个。另有 505 个“同一实例被引用但端口序号不同”，原因是同一 `装置端子` 符号的多个端子槽位可指向同一文字句柄，端口序号不能作为唯一键，应以跨页引用中的端子号为准。
- 元件侧：PCL 引脚中 28124/28435（98.9%）已在流水线的部件端口中出现，因此 PCL 的增量在去向，不在引脚。
- 端子排侧增量：PCL 对端命中的端子行中，现有去向为空、仅 PCL 能补的只有 19 行（26544 行中 `rows_pcl_gain_no_existing_dest`），增量很小。
- 代码使用：全部字段无引用（`src/` 中无 `LD_PARTCONNECTLINE`，无 `逻辑端号` / `对端元件` / `直线句柄` 读取）。

### 4.3 F3：`LD_LINE_STYLE`（排名 4）

- 载体：原理图导线的 XDATA（LINE 为主）。计数（深扫）：模型空间 6219 + 块定义 7505 = 13724 个实体（原理图 265 页）。取值：`电流回路线:*` 5026、`电压回路线:&` 4044、空 3340、`四芯屏蔽线:@` 740、`4.0接地线` 202、`2.5接地线` 109、`以太网线:#` 94 等（取值按 value probe 汇总）。
- 样例：`p000/F0004 04 交流回路图.dwg` 导线 `E2F2` = `电流回路线:*`；`p000/F0005 05 交直流回路图.dwg` 导线 `8EDD` 为空；`p001/F0004 04 交流回路图.dwg` 导线 `E352` = `电压回路线:&`。
- 未消费端口：接触导线 4731 条，带该属性的 402 条，覆盖 402/4727 = 8.5%。
- 代码使用：无引用。
- 注意：PCL 的直线句柄所指 LINE 上没有该属性（27967 条全部为空），即该属性只在部分线上存在。

### 4.4 F4：跨页标记标签 XDATA（排名 6–8）

- `LD_SHOW_LINE`（MTEXT → LINE）、`LD_SHOW_TYPE`（MTEXT → TEXT）：样例 `p000/F0004` 的 MTEXT `E384`（标签 `1n`）→ LINE `1280D`，→ TEXT `1280C`（`WXH-813-D1F`）。说明跨页标签同时带有导线与装置型号指针，但导线指针的语义尚未验证。
- `LD_SYMB2_InsideLABEL`（INSERT → MTEXT）：样例 `p000/F0007` 的 INSERT `1C073` → MTEXT `1C12F`（`1n`）。
- `LD_ GROUPPARTXRECT_TEXT`（LWPOLYLINE 框 → MTEXT）：样例 `p000/F0004` 的框 `E303` → MTEXT `E384`（`1n`）。
- 注意：上述指针中大量为 0（空），有效指向需逐个过滤。跨页标记的页归属仍需从 PCL / LOGGEN 的跨页句柄获得。
- 代码使用：全部无引用。未对未消费端口做量化。

### 4.5 F5：`DZ_SERIALNUMBER_NAME` 与表头身份缺陷（排名 5）

- 端子行 TEXT 的 XDATA `DZ_SERIALNUMBER_NAME` 给出端子排名（如 `7UD`、`TD`、`ZD`、`1QD`、`1-21QD`）。
- 表头 `LD_DZPNO_HEADHANDLE` 指向的文字与其相同的比例：23389/26543（88.1%）。其余 3154 行的表头为“上接XXX”续接说明（如 `上接1QD15`）。
- 流水线的 `endpoint_identity` 由表头文字与行文字拼接而成（`superworks_semantics.py` 约 483 行，`SwStripRow` 的 `endpoint_identity`），因此上述 3154 行的身份为 `上接1QD1516`（应为 `1QD16`）。
- 未消费端口中，身份在 DZ 口径存在而表头口径缺失的 75 个（直接受影响）；两口径都存在的 2153 个；仅表头存在的 112 个；两口径都不存在的 1594 个（多为设备级身份，如 `JD1`）；无身份 793 个。
- 样例：`p000/F0017 17 左侧端子表.dwg` 的 TEXT `23301`（DZ 名 `7UD`，行 `1`）；`p000/F0018 18 右侧端子表.dwg` 的 TEXT `130F9`（`TD`）；`p001/F0014 14 左侧端子表.dwg` 的 TEXT `1E591`（`ZD`）。
- 修复建议：身份改为 `DZ_SERIALNUMBER_NAME + 行文字`，表头仅作为校验。这是一个独立于属性补充的缺陷修复。

### 4.6 F6：符号端子文字锚点与元件引脚圆（排名 9、10）

- `LD_SYMB1LIB_TERMTEXTPOINT`：832 页，符号定义中的 LWPOLYLINE，指向 LWPOLYLINE 4589 次（例：`p000/F0004` 的 `9A57` → `9A55`）。
- `LDPARTLAYT_CIRCLE_HANDLE`：178 页，元件 INSERT → CIRCLE 7124 次（例：`p000/F0015` 的 `B960` → `B961`）。
- `LDPARTLAYT_LINE_HANDLE`：359 页，元件 INSERT → LINE 7533 次（例：`p000/F0014` 的 `19E6B` → `19E6F`）。该 LINE 与 PCL 直线句柄无重合（0/3704），应为元件引脚引线，不是连接导线。
- 代码使用：三者均无引用。未对未消费端口做量化。

### 4.7 F7：端号自动标注与元素类别（备选）

- `LD_SYMB_TERMAUTODIM`：1112 页，取值 `NO` 8967、`YES` 179。`YES` 表示端号由程序自动标注，图上可能没有端子文字，可解释部分 `unresolved_pin_text`。
- `DZCONNECT_ELEMENT_CLASS`：屏端子图 TEXT，取值 `装置端子` 31054、`端子` 2628、`线圈` 182、`接地` 144，可辅助区分 PCL 的 far_kind。
- 代码使用：无引用。

## 5. 否定结论（冗余或无增量）

| 键名 | 结论 | 依据 |
|---|---|---|
| `LD_DZPNO_DXLX_OUT` | 冗余 | 与已用的 `LD_DZPNO_DXLX` 在 6066/6066 个可比行上相同 |
| `DZ_SERIALNUMBER_DZLX` | 冗余 | “试验端子:粗线”5973 行全部与已用的 `LD_DZPNO_DZLX` 折线对应 |
| `LX`、`DZ_SERIALNUMBER_LAYER`、`DZ_SERIALNUMBER_HD` | 常量或低区分 | LX 全为 `0`；LAYER 全为 `1`；HD 仅 `6.20` / `8.20` |
| `LD_LINE_COLORCODE`、`LD_LINE_DIAMETER`、`LD_LINE_COLORVALUE`、`LINECOLOR`、`LINEDIAMETER` | 基本为空 | LOGGEN 中 LINECOLOR、LINEDIAMETER 非空均为 0 |
| `LD_SYMB_TERMHIDE` | 常量 | 全为 `NO` |
| `LD_SYMB_BOMANDLABEL`（扩展字典） | 模板值 | 推荐名称、方向“其它”、端号自动标注 NO 等 |
| GROUP 对象（326 个） | 与匹配无关 | 名称为 `GROUP_LPINFOTABLE`（128）、`GROUP_DwgDirTABLE`（120），集中在屏面布置图与封面/目录 |
| `LDBOM_*`、`PDZT_*`、`LD_ACTLABEL`、`LD_ACTTERM` | 与连接无关 | BOM、屏面布置标注，或仅 20 页的动作端子 |

## 6. 未完成或受限的部分

- 跨页标记（F4）与符号文字锚点（F6）未在未消费端口上量化，只给出存在性与样例。
- `LD_SHOW_LINE` 指向的 LINE 是否即标签所属导线，未验证。
- `LD_SYMB2LOGGEN` 中 3 端及以上记录（约 2450 条）按端点逐一判断，未做多端一致性统计。
- “另一端一致性”只对能在端子排索引中找到身份的端口评估（2227 个），其余 2440 个身份为设备级，无法用同一方法验证。
- 未消费端口的原因码见 `unconsumed_port_diagnostics.json`：`no_matching_production_pair` 3934、`partial_legacy_value_differs_from_full_SW_identity` 3859、`legacy_discard_retained` 3274、`endpoint_text_not_extracted` 798、`unresolved_endpoint_identity` 798、`unresolved_pin_text` 794、`nonreciprocal_pin` 631、`dangling_label_handle` 333。
- 未重新转换 DWG；全部结论基于冻结 DXF 缓存（manifest 中的 `dxf_path`，1745 个文件全部存在）。

## 7. 文件与复现

- `details.json`：全部 appid 表（162 项，含页型覆盖、家族覆盖、样例、代码引用）、候选属性取值、7 个发现的结构化数据、否定结论、Top 10 与复现命令。
- `tools/`：
  - 深扫与汇总：`build_index.py`、`deep_scan.py`、`aggregate.py`、`value_probe.py`、`aggregate_vp.py`
  - LD_PARTCONNECTLINE：`parse_pcl.py`、`aggregate_pcl.py`、`validate_links.py`、`wire_probe.py`、`part_overlap.py`
  - LD_SYMB2LOGGEN：`parse_loggen.py`、`analyze_loggen.py`、`check_loggen_identity.py`
  - 端口与覆盖：`analyze_unconsumed.py`、`crosspage_cover.py`、`analyze_wire_style.py`
  - 端子排：`strip_dest_index.py`、`strip_gain.py`、`strip_redundancy.py`、`strip_identity_check.py`
  - 汇总：`build_details.py`（读取上述输出，生成 `details.json`）
- 运行方式：工作目录为仓库根，`PYTHONIOENCODING=utf-8`，中间输出写入临时目录。各脚本的参数见 `details.json` 的 `reproduce` 字段。
