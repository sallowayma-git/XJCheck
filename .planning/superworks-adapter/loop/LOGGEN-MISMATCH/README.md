# LOGGEN-MISMATCH：去向记录的端口身份 与 图面标注（只读）

范围：只读分析。未修改 `src/`、`tests/`，未 git。`PYTHONIOENCODING=utf-8`。
数据：`.tmp/superworks_round14_full/pNNN/*/findings/`（77 个项目，全部含 `sw_wire_routes.parquet`，无跳过）。
冻结 DXF：`.planning/superworks-adapter/corpus_manifest.json` 指向的 `dxf_path`（只读）。未读取 `.tmp/superworks_round15_full`。

---

## 0. 结论摘要

1. **全语料一致性：** 77 个项目共 **104,390** 个唯一已解析端口（`sw_port` 来源；记录端共出现 131,280 次；同一端口的身份在各记录间无冲突）。与端口近旁图面文字比较：**一致 103,856（99.49%）**，**不一致 0**，**无法判定 534（0.51%）**。
2. **初版的 2,342 条“不一致”经形态归类与抽样核对，判为校验规则的缺口，不是身份错误。** 初版规则只接受纯数字引脚、把交叉引用文字（`* 2-25I5D1`、`& 2-25ZKK1-2`）当作本端标注、不认页眉字母与左侧组标题。逐类修正后，不一致为 0。修正的是校验（诊断）代码，未改任何身份构造。（逐条核对未全部完成，结论依据形态归类与抽样，见第 4 节。）
3. **supplement_03（p061 背板 FCK-851C-G-1，记录 `SWWR:F0022:PCL:9B07:532`）结论：(c)。** 端口 532 的身份正确（图上第 5 列第 32 行）。图上 "3-21n232" 不是 "32" 与 "3-21n2" 的拆分，而是一个完整文字实体，挂在导线 EE4B 上的**接线去向标签**，指向同一背板的第 2 列第 32 行端子 232（链式下一跳）。比对时取到的是去向标签，不是端口自身标注。
4. **(a)/(b)/(c) 判定：**
   - (a) 身份拼接错误：**未发现**。抽样的每一类（组标题 + 序号、标签 + 引脚、行首标签 + 单元格序号）在图上都能对上。
   - (b) 图纸真实不一致：**未确认**。仅有若干"端口处无标注、同号文字在别处"的情形（N1 桶，共 4 个样例端口），属于图面缺标注，需人工复核，不计为不一致。
   - (c) 取错或取不全图面文字：**是所有残余分歧的来源**（初版 2,342 条、现有无法判定 534 条的绝大部分）。
5. **修复方案：** 身份构造（`superworks_semantics.py` 的端口身份拼接、`superworks_loggen.py` 的解析）**无需修改**。
6. **新审计规则：不建议作为审计问题报出。** 原因：零结果的检出力弱（负对照中 33.5% 的末位改动仍被判一致，端子达 51.5%）；“最近标签”规则在端子排误报（976 例，抽样 6 例均为版面歧义）；接线去向标签与远端身份一致的仅 34.5%（多为链式下一跳）。若需要，只能作为人工复核清单（见第 6 节）。

---

## 1. 数据与口径

- **端口**：`sw_wire_routes.parquet` 中 `status == resolved` 且 `identity_source == sw_port` 的端，取 `port_ids[0]` 去重。每个端口的几何来自 `sw_ports.parquet`（页内 INSERT 的 SW 端口）或 `sw_part_instances.parquet` 的 `ports`（内部元件、背板端口），取两端中点。
- **图面文字**：`texts.parquet`，同一页（`file_id`）内，取包围盒中心；半径 R_NEAR = 12、R_WIDE = 30（页坐标单位）。
- **接线标签**：`sw_connect_labels.parquet` 的 `text_id`（LD_ConnectLine 文字），**单独处理，不作为本端标注**。以 `*`、`&` 开头的交叉引用文字同样不作为本端标注。
- **端点类别**：背板页（`text_assignments.page_type == 背板表格型图`）上的端口为“背板端口”；其余按 SW 类别（端子 / 装置端子）或 part 端口（内部元件）归类；线圈、接插件、接地归入“其他”。

---

## 2. 判定规则（最终版）

| 判定 | 含义 |
|---|---|
| `agree_exact` | 近旁（≤30）有文字与身份相同（忽略空白） |
| `agree_format` | 忽略连字符、`&`、`_`、`.` 后相同 |
| `agree_composed_pin` | 身份 = 图面上的标签 + 一个引脚文字（标签在图上存在；标签可为图中文字的子串且以字母或连字符结尾，如 K861-1X in K861-1X4） |
| `agree_segmented` | 身份 = 标签 + 多段近旁文字拼接（页眉字母 C + 行号 13 = C13；1X + 2 = 1X2；COM4 + A = COM4-A，忽略连字符） |
| `agree_*_contact_suffix` | 去掉末尾触点序号（-1、-2）后同上 |
| `agree_group_header_left` | 端子排组标题在端口左侧（≤40，同行带）+ 单元格数字（COM3 + 第 5 格 = COM3-5） |
| `agree_row_partial`（弱） | 仅背板：标签在图上，行号（末两位）在近旁 |
| `unrelated_text_nearby` | 最近的身份型近旁文字与身份不相似（无法判定） |
| `connect_only_*` | 仅有接线去向标签（无法判定） |
| `unverifiable` | R_WIDE 内无文字（无法判定） |
| `disagree_*` | 近旁身份型文字与身份相似但不同（本轮结果为 0） |

**规则演进（同一批数据）：**

| 版本（按运行顺序） | 不一致 | 主要变化 |
|---|---|---|
| 初版（朴素） | 2,342（前缀不同 1,971；前缀与端口均不同 371）；仅接线 1,160；无标注 242 | 复合引脚只认纯数字 |
| 接受字母引脚与段拼接 | 136 | 装置端子的 `K8611X4 = K861 + 1X4` 大多被认出 |
| 近旁身份文字取最近者作为依据（远处文字不作依据） | 62 | 不再因 30 单位内的任一身份文字判不一致 |
| 排除交叉引用文字（`*`、`&` 开头）+ 段拼接 | 14 | 去掉 `* 2-25I5D1` 等（背板 200 条的主要来源） |
| 忽略连字符的组合与左侧组标题规则（位置检索修正前） | 6 | COM4-A、COM3-5 等；修正前组标题检索有误 |
| 组标题行带容差 5 单位（引线偏移） | **0** | 端口比标题低 3–4 单位（引线） |

初版 2,342 条按类别与形态（初版规则输出）：
- 装置端子：前缀不同 1,811，前缀与端口均不同 37（`K8611X4` 对 `1X4`，即标签 + 字母引脚）。
- 内部元件：前缀不同 108，前缀与端口均不同 92（如 `1-25nPWR1-7` 对 `PWR1`）。
- 背板端口：前缀不同 52，前缀与端口均不同 200（交叉引用 `* 1-25I5D1` 与 `& 1-25ZKK5-4`，以及 `COM4-A` 对 `COM4`）。
- 其他：前缀与端口均不同 42（`1-40n-1TX` 对 `1TX`）。

---

## 3. 全语料结果

### 3.1 一致 / 不一致 / 无法判定

| 结论 | 数量 | 占比 |
|---|---|---|
| **一致** | **103,856** | **99.49%** |
| **不一致** | **0** | 0% |
| **无法判定** | **534** | 0.51% |

- 无法判定细分：无关的近旁身份型文字 400；仅接线去向标签 86；近旁无文字 48。
- 一致细分：精确 36,783（35.2%）；仅格式 11；复合（标签 + 引脚文字）47,812（45.8%）；多段拼接 4,267（4.1%）；左侧组标题 133（0.1%）；**仅行号一致（背板，弱证据）14,850（14.2%）**。

### 3.2 按端点类别

| 类别 | 端口数 | 一致 | 不一致 | 无法判定 |
|---|---|---|---|---|
| 端子 | 36,777 | 36,776 | 0 | 1 |
| 装置端子 | 39,386 | 39,350 | 0 | 36 |
| 内部元件 | 9,581 | 9,333 | 0 | 248 |
| 背板端口 | 18,468 | 18,219 | 0 | 249 |
| 其他（线圈、接插件、接地） | 178 | 178 | 0 | 0 |

### 3.3 校验有效性检查

- **负对照**（`control_check.py`）：抽取 3,990 个一致端口，将身份末位数字 +1 后重判，仍判一致 **1,335（33.5%）**。端子 732/1,420（51.5%）；装置端子 467/1,516（30.8%）；内部元件 83/339（24.5%）；背板 51/707（7.2%）。解释：端子排相邻编号的标签常在 30 单位内同时存在，因此“近旁有该文字”只是弱证据。**本检查不能证明无错绑定。**
- **端子最近标签检验**（`nearest_label_check.py`）：36,777 个端子端口中，身份文字即最近身份型文字 34,123（92.8%）；并列（差 < 1 单位）1,243；身份文字存在但另一文字更近 1,410，其中差 ≥ 2 单位的 976（3.8%）。
- **背板槽位证据**（18,468 个背板端口）：页眉单数字与首位数字相符 988、不符 19（全部为启发式误差：行号 "16" 竖排为上下两个文字 "1"、"6"，被误作页眉）、无页眉 17,461。列副本序（同行副本的左右次序）相符 4,986、不符 5,999、无 7,483。**副本序只适用于 9B07 类布局，不能作为通用核验依据。**
- **接线去向标签**（`wire_destination_checks`，28,111 行，21,480 条 PCL 记录，均为跨页端）：去向文字等于远端身份 9,688（34.5%，含仅格式 443）；等于远端对端文本而非远端身份 12,086（43.0%，含仅格式 50）；不同 6,337（22.5%）。不同的多为链式下一跳（如 `1KLP1-1` 的去向为 `1KLP2-1`，远端身份为 `1n112`），语义不同，不是错误。**因此“去向标签 ≠ 远端身份”不宜作为审计判据。**

### 3.4 与 LOGGEN 基线的关系

本次只读比较，未改变任何身份，LOGGEN README 中的 2,676 / 3,304 / 471 等计数不受影响。LOGGEN README 第 4 节对 supplement_03 的描述“近端标签部分被裁切，证据较弱”不准确：标签完整可读，是接线去向标签（见第 5 节）。

---

## 4. 各桶抽样与 (a)/(b)/(c) 判定（PNG 在 `png/`）

每张图 6 个面板（supplement 类 4 个），绿框 = 端口触点，金框 = 近旁本端文字，洋红 = 接线去向标签，橙 = 导线。逐例标注见 `details.json` 的 `judgments` 与 `samples`。

| 图 | 桶（n） | 抽样 | 判定 |
|---|---|---|---|
| `G1_group_header_left.png` | 左侧组标题（133） | 6 例：COM8-5（p051 F0009）、1-25nPWR1-4（p051）、2-25nPWR1-7（p062）、1-40n-PWR5（p056）、1-25nC02（p074）、25nPWR1-4（p071） | **(a) 无错误。** 身份 = 左侧组标题 + 单元格数字，与版面一致。原校验的缺口，已修正。 |
| `U1_unrelated_nearby.png` | 无关近旁身份文字（400） | 6 例：1-25nA12（p074）、2-26n627（p075）、1-25nC06（p074）、T1OUT1（p051）、2-25nB19（p074）、T2-IN1（p051） | **(c)。** 身份的页眉字母（A/B/C）、列号、组名或拼接段在窗口外；窗口内只有行号或端子名。端口处的行号与身份一致。未见真实冲突。 |
| `C1_connect_only_differs.png` | 仅接线去向标签（86） | 6 例：K863-1X4（p030 F0027）、1nP101（p072）、K861-1X5（p004）、K861-1X16（p000）、K864-1X4（p035）、K864-1X16（p029） | **(c)。** 端口处只有接线去向标签（链式下一跳或邻居）。本端编号（圈内数字或行号）可对应；设备前缀（K86x-1X）在窗口外，或只以交叉引用形式出现。 |
| `N1_unverifiable.png` | 近旁无文字（48） | 6 例：2-57n-PE1（p071）；1n1222（p009、p020）；1n205（p010、p018）；2-40n-1（p051） | **无法判定，待人工复核。** 1n1222 的编号 1222 只在页面 (383,288) 出现，距端口 278 单位；1n205 的 205 在 (248,626)，距端口 401 单位。端口处无标注。属图面缺标注，不计为不一致。2-57n-PE1 的 PE1 在页面别处。 |
| `R1_row_partial_connect_differs.png` | 行号一致、接线标签不同（14,258 之一） | 4 例：4n1018 行 18（p072）、2-21n326 行 26（p046）、2-21n315 行 15（p059）、1n2504 行 04（p017） | **(c)，同 supplement_03。** 行号与端口一致；同行的接线标签是去向（下一跳）。判为一致（弱证据）。 |
| `T1_terminal_not_nearest.png` | 端子：身份文字非最近（差 ≥ 2，976） | 6 例 | **版面歧义。** 引线偏移；范围标签（`7U2D5~10` 与 `7U2D1~4`）同时靠近；相邻标签交错。未见真实冲突。最近标签规则误报率高。 |
| `P1_pwr_header_conflict.png` | PWR 族：身份编号与左侧 PWR 标题不同（54） | 6 例：2-40nPWR2（p053、p056、p071）、1-40nPWR2（p062）、4-40nPWR2（p052）、1-40n-PWR4（p055） | **(a) 命名约定，不是冲突。** 标题 PWR1 覆盖第 1–3 格，PWR2 覆盖第 4–5 格；身份 = 行首标签 PWR + 单元格序号（第 2 格 → PWR2；第 4、5 格 → PWR4、PWR5）。标题是分组，不是编号。 |
| `CASE_supplement03_p061_9B07_532.png` | supplement_03 | 端口 532、232 与同行 | 见第 5 节。 |

**(c) 的形态归纳（残余与初版的主要来源）：** 页眉字母或列号不在窗口内；交叉引用文字（`*`、`&`）被误作本端标注；接线去向标签被误作端口标注；设备前缀只以交叉引用形式出现；拼接段分处两处（OUT 与 1）。

---

## 5. supplement_03（p061 F0022，背板 FCK-851C-G-1，记录 `SWWR:F0022:PCL:9B07:532`）

1. **“3-21n232” 的来源。** 不是 "32" 与 "3-21n2" 的拆分。图上是一个完整的 TEXT 实体（句柄 EE4C，插入点 (388.5, 153.5)，文字 "3-21n232"）。它在 `sw_connect_labels` 中挂在导线 **EE4B** 上（LD_ConnectLine，text_id T4507），是接线去向标签。紧邻其左侧的 "32" 是独立实体（T4050，(383.7, 153.75)）。
2. **端口 532 从哪来。** PCL 记录的逻辑端号 532 = 元件 9B07（FCK-851C-G-1）的端口 532，几何位于 (387, 155)。端口号 532 来自 TERMPOINT 名（pin 解析方法 `termpoint_number_fallback`：同值异文的 985E 被拒，回退到 TERMPOINT 端口号）。身份 = 背板标签 9B0D "3-21n" + "532" = `3-21n532`。
3. **图面上能否核对 532。** 该背板共 5 个列副本（x ≈ 83.7、158.7、233.7、308.7、383.7），每列在 y ≈ 153.75 都印有行号 "32"。端口 532 位于第 5 列（x = 387，与第 5 列 "32" 对齐）；端口 232 位于第 2 列（x = 162，与第 2 列 "32" 对齐）。三位端口号 = 列数字 + 两位行号。于是“第 5 列第 32 行 = 532”在几何上成立。本端的核对依据是行号 "32"（`agree_row_partial`，标签 "3-21n" 在图上）加上列序（rank 5 / 5）。
4. **为何出现 "232"。** “3-21n232”就是第 2 列第 32 行端子 232 的身份名。同一背板上，232 的接线标签 EE0A 印 "3-21n231,3-21n532"，231 的标签 EE08 印 "3-21GD21,3-21n232"。三者互相列出邻居，构成背板内的链式跳线：231 — 232 — 532。记录中 PCL 的 对端元件 文本 "3-21n||232" 与 EE4C 一致（均为链式下一跳）。
5. **跨页远端。** 远端 9091 port 1（F0006，直流回路图 1）的 SW 身份为 `3-21GD19`，与远端文本 `3-21n232` 不同。这是远端的已知问题（LOGGEN README 第 7 节风险：对端文本多为下一跳，而非直接邻居），**不属于本端身份不一致**。
6. **结论：(c)。** 端口 532 的身份正确，无需修改。比对时把接线去向标签当作了端口自身标注。本端的 9B07:532 ↔ F0006 跨页连接的结论不变。

---

## 6. 修复方案与新规则建议

**身份构造（a）：无需修改。** 本次抽样与负对照均未显示 `superworks_semantics.py` 的身份拼接或 `superworks_loggen.py` 的解析存在错误。需要注意的是：
- 背板 3 位端口号的首位（列 / 组序号）在多数布局中不能由图面直接核对（页眉单数字仅 988 例可核，副本序仅适用于 9B07 类布局）。这是“无法核验”，不是“有错误”，不应据此改代码。
- TERMPOINT 回退（`termpoint_number_fallback`）依赖 TERMPOINT 名，而不是图面引脚文字。该路径的身份是可靠的（如 532），但它的正确性只能靠布局几何验证。

**新审计规则（b）：不建议。** 理由：
1. 全语料 104,390 端口未出现可确认的不一致；但零结果的检出力很弱（负对照 33.5% 的末位改动仍判一致，端子 51.5%）。
2. “最近标签”类规则误报高（976 例，抽样 6 例均为版面歧义）。
3. 接线去向标签与远端身份一致的仅 34.5%；“去向标签 ≠ 远端身份”多为链式下一跳，语义不同。

**若仍需一个规则，最小判定条件（只在两边确定、且非已知等价格式时报）：**
- 端口为端子或装置端子；身份 I 的标签与引脚在端口 R ≤ 12 内均有图面文字（排除接线标签与 `*`、`&` 交叉引用文字）；
- I 与近旁全部本端身份型文字均不等价（忽略连字符、`&`、空白）；
- I 在整页都不以独立文字出现（单字母标签除外）；
- 端口有导线接触。

满足条件的估计约 48 条（即当前“近旁无文字”集合），其中至少 4 个样例端口（1n1222、1n205）为“同号文字在别处”的图面缺标注。**预计精度低，误报风险高（版面偏移、链式标签、拼接段分处两处）。** 建议只作为人工复核清单，而非审计问题。

**校验改进（可选，仅诊断用途）：** 本次的 `build_ends.py` 已包含：排除交叉引用文字；字母与段拼接；左侧组标题；忽略连字符的标签匹配。若将来需要对端子排做图面核验，可沿用这些规则，但应同时使用导线引线几何（本次未使用，见第 7 节）。

---

## 7. 局限

- **文本近旁测试，不是归属测试。** 未使用引线 / 导线几何判断“哪个标签属于哪个端口”，这是端子排误判与负对照结果偏弱的根本原因。
- **窗口大小。** R_NEAR = 12、R_WIDE = 30 单位。背板页眉字母、列号在窗口外的情形很多（U1、C1 的样例）。
- **仅覆盖 `sw_port` 来源的端口。** 仅文本身份（`resolved_by_text`）的远端与 `insert_not_sw` 端未纳入。
- **判定为存在性测试。** 复合判定只要求各段文字存在于近旁，不要求它们属于同一组件；因此一致率偏乐观，负对照显示其弱点。
- **抽样。** 每桶仅 4–6 例（固定种子），逐例判断为人工视图判读；未对全部 48 个“无文字”端口逐一看图。

---

## 8. 文件与复现

交付物（均在 `.planning/superworks-adapter/loop/LOGGEN-MISMATCH/` 下）：
- `README.md`（本文件）、`details.json`（汇总、逐例判定 `judgments`、抽样清单 `samples`）
- `png/`：`G1_group_header_left.png`、`U1_unrelated_nearby.png`、`C1_connect_only_differs.png`、`N1_unverifiable.png`、`R1_row_partial_connect_differs.png`、`T1_terminal_not_nearest.png`、`P1_pwr_header_conflict.png`、`CASE_supplement03_p061_9B07_532.png`
- `tools/`：`build_ends.py`（主比较）、`control_check.py`（负对照）、`nearest_label_check.py`（端子最近标签）、`render_samples.py`（桶抽样渲染）、`render_terminal_nearest.py`、`render_pwr_conflict.py`、`render_case_supplement03.py`、`aggregate.py`（写 `details.json`）

中间表（`ends.pkl` 等约 60 MB）保存在会话 scratchpad（`C:\Users\25788\AppData\Local\Temp\claude\F--workspace-XJToolkit\367e37bd-5006-413b-a449-e1c665a8b237\scratchpad\mismatch\`），不在项目内。

复现（`PYTHONIOENCODING=utf-8`，在仓库根目录）：
```
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/build_ends.py .tmp/superworks_round14_full <scratch>/mismatch
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/control_check.py <scratch>/mismatch .tmp/superworks_round14_full <scratch>/mismatch/control.json
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/nearest_label_check.py <scratch>/mismatch .tmp/superworks_round14_full <scratch>/mismatch/nearest_terminal.pkl
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/render_samples.py <scratch>/mismatch .tmp/superworks_round14_full .planning/superworks-adapter/loop/LOGGEN-MISMATCH/png <scratch>/mismatch/samples.json
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/render_terminal_nearest.py <scratch>/mismatch .tmp/superworks_round14_full <out>.png 6
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/render_pwr_conflict.py <scratch>/mismatch .tmp/superworks_round14_full <out>.png 6
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/render_case_supplement03.py .tmp/superworks_round14_full <out>.png
python .planning/superworks-adapter/loop/LOGGEN-MISMATCH/tools/aggregate.py <scratch>/mismatch .planning/superworks-adapter/loop/LOGGEN-MISMATCH/details.json <scratch>/mismatch/samples.json
```
（`<scratch>` = 会话 scratchpad 路径；`wire_checks.pkl`、`stats.json` 由 `build_ends.py` 写出。）
