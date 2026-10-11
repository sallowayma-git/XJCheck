# PIN-ID：端子 ↔ 元件引脚的引脚身份可得性评估（只读）

范围：只读评估，未修改 `src/`、`tests/`，未执行 git，未改动冻结 DXF 与 `corpus_manifest.json`。
数据：round16 全量回放 `.tmp/superworks_round16_full`（77 个项目，1745 张页，`sw_*` 产物与 `sw_wire_routes`）；冻结 DXF 由 `corpus_manifest.json` 的 `dxf_path` 指向，仅读取。
口径：严格覆盖口径沿用 COV-GAP 层 b（端子/装置端子，有导线接触且标签已解析为 eligible，非 discard 且 SW 证据命中并且值相等为 consumed），复用 `superworks_artifacts` 的判定，不另立口径。

## 0. 结论

1. **“内部元件引脚身份”在元数据里基本不可得。** SW 内部元件符号（类别 内部元件/线圈/接插件/接地）中无身份的端口共 35963 个，其中 33830 个有导线接触，18604 个导线另一端直接接在已识别的端子上（即 COV-GAP 的 O3 主体）。这些引脚的标签（`LD_SYMB2_LABEL`）有 29183 个可得，但脚号文字**没有任何元数据链接**：这些端口所在符号的 `LD_SYMB2_TERM_TEXT_n` 链接在 DXF 中仅 92 个端口有，块内 `LD_SYMB1LIB_TERMPOINT` 只有端口号（1000），没有指向文字的 1005 链接。
2. **块内 TERMPOINT 端口号不是图面脚号。** 对已有身份的 856 个内部端口，身份后缀与端口号相等的只有 56 个（6.5%）；视觉核对中图面脚号为 5、9、2，而端口号为 1 的例子也出现多次。以“标签 + 端口号”生成身份（K_num）不可接入：视觉 9 例中 0 例确认正确、3 例明确错误、6 例无法核实。
3. **一类新发现：被 SW 抽取整体丢弃的符号。** 扫描全部 1745 张 DXF，共 9734 个带 `LD_SYMB2_LABEL` 但**没有 `LD_SYMB2_SPECIAL`** 的 SYMB2 插入，5310 个带脚号文字链接。`superworks_semantics.walk()` 只在有类别时才登记符号与端口，因此这些符号完全不进入 `sw_ports`。其中 3513 个被导线去向记录（LOGGEN 中 `insert_not_sw` 的端）引用，共 8145 个引脚端。这些端的设备名与标签 100% 一致（8139/8139），脚号文字与记录序号 100% 一致（7735/7735）。
4. **对这一小类（Pop-X）的候选身份（标签 + 槽位文字，与 LOGGEN 序号/设备名互证）视觉核对 46/46 正确**（A 层 26 例 + 补抽 20 例）。点估计 100%，但单侧 95% 下限只有 93.7%，**未能统计证明达到 98%**。要证明下限 ≥98% 需要 149 例全部正确，目前还差 103 例。
5. **覆盖率上界。** 严格口径基线 57.68%（47692/82680）。若只接入 Pop-X 中“槽位文字与序号一致、端子未被消费、身份唯一、端子排行不冲突”的候选（R1，3188 个未消费端子），上界为 61.54%（+3.86 个百分点）；其中有导线句柄的 3041 个为 61.36%（+3.68），其余 147 个只能进 review。Pop-S 的 O3 主体（17333 量级）无法由元数据接入。
6. **新增 issue 风险。** 不加门控时，R1 会在 553 个已有非 discard 通过配对（532 个 pass）的端子上产生第二个不同身份的配对，必须拦截或进入复核。Pop-X 的同号重复身份只有 1 个涉及不同端子伙伴；Pop-S 的 K_num 同号重复有 379 个身份涉及不同端子伙伴，这是拒绝 K_num 的另一个理由。
7. **建议接入的来源：** 只接入 Pop-X 的 R1（以 review 级先行，取得 ≥149 例零错误后再升 pass）；不接入 K_num、不接入仅有序号的 R3（130 个，+0.16 个百分点）、不以端子排行不一致作为拒绝依据（视觉上多为总线拓扑造成的假阳性）。方案见第 8 节。

## 1. 数据与核对

| 项 | 数值 |
|---|---|
| 回放项目 / 页 | 77 / 1745（全部 `COMPLETE`） |
| SW 内部类端口（内部元件/线圈/接插件/接地） | 34111 + 1718 + 390 + 600 = 36819，无身份 35963 |
| SYMB2 插入带 LABEL 而无 SPECIAL（被丢弃） | 9734（其中带脚号文字链接 5310） |
| LOGGEN 中 `insert_not_sw` 的端 | 8145，全部对应上面被丢弃的符号（100%） |
| LOGGEN 已解析端的 SW 类别 | 端子 40975，装置端子 40197，接地 243，线圈 136，接插件 98；内部元件 0 |

LOGGEN 记录对“内部元件”类 SW 符号从不引用，因此 LOGGEN 无法为 Pop-S 提供脚号。

## 2. 人口定义

- **Pop-S**：`sw_ports` 中类别属于 内部元件/线圈/接插件/接地 且 `endpoint_identity` 为空的端口（35963）。
- **Pop-X**：LOGGEN 中 `insert_not_sw` 的引脚端（8145，3513 个符号）。这些符号没有 SW 端口，所以“无身份”体现在整个符号未登记。
- 导线另一端：同一文件、同一导线句柄上的其他端口（Pop-S）或 LOGGEN 记录的另一端（Pop-X）。“端子直连”指另一端为已识别的端子/装置端子。

## 3. 一、身份可得性（分来源）

### 3.1 Pop-S（SW 内部端口，无身份）

| 项 | 数量 | 占比 |
|---|---|---|
| 无身份端口 | 35963 | |
| 其中有导线接触 | 33830 | 94.1% |
| 导线另一端为已识别端子（端子直连） | 18604 | 51.7% |
| 其中有标签（可构造 标签+端口号） | 16642 | |
| 标签可得（LD_SYMB2_LABEL 有效） | 29183 | 81.1% |
| 标签缺失（无 LABEL 引用） | 6780 | 18.9% |
| 脚号文字可得（pin 已解析） | 160 | 0.4%（全部同时缺标签） |
| 符号带 LD_SYMB2_TERM_TEXT_n 链接（DXF 扫描） | 92 | 0.3% |
| TERMPOINT 端口号可得 | 35963 | 100%（但非图面脚号，见 K3） |

端口按家族分布（无身份）：正式典设 25726，N2604 合同 8675，变压器测控柜 580，PAC-885G-H 512，110kV 变压器保护柜 470。端子直连按家族：正式典设 13483，N2604 4407，变压器测控柜 314，PAC-885G-H 217，110kV 183。

### 3.2 Pop-X（被丢弃符号的引脚端，LOGGEN 中 `insert_not_sw`）

| 来源 | 可得 | 占比 |
|---|---|---|
| 符号标签（DXF，LD_SYMB2_LABEL 有效） | 8139 | 99.9% |
| 槽位脚号文字（LD_SYMB2_TERM_TEXT_<pin>） | 7735 | 95.0% |
| 记录设备名 + 序号（LOGGEN device + seq），K_rec | 7987 | 98.1% |
| 记录端 `device` 与符号标签一致 | 8139/8139 | 100%（有标签的全部） |
| 槽位文字与记录序号一致 | 7735/7735 | 100% |
| 另一端为已解析的端子（端子直连） | 7207 | 88.5% |
| 记录含导线句柄（CONNECTLINEHANDLE） | 6993 | 85.9% |

Pop-X 的类别字段在 LOGGEN 中为空（已对全部 8145 端在 PART2 第 7、8 段核对，无类别文字），符号也没有 `LD_SYMB2_SPECIAL`，因此**类别未知**；本报告不把它们称为“内部元件”。家族分布：正式典设 5643，N2604 2064，110kV 163，PAC-885G-H 149，变压器测控柜 126。

## 4. 二、未赋予身份的原因分布

| 人口 | 原因 | 数量 | 占比 |
|---|---|---|---|
| Pop-S | 标签引用缺失（missing_label_reference） | 6780 | 18.9% |
| Pop-S | 标签有效但无脚号文字链接（unresolved_pin_text） | 29153 | 81.0% |
| Pop-S | 标签有效、存在脚号文字链接却未使用 | 30 | 0.1% |
| Pop-S | 同标签+端口号落在多个物理引脚（K_num 重号） | 548 个身份 / 829 | 66% 的身份 |
| Pop-S | 端子排佐证（strip_reverse_corroboration）命中 | 0 | 端子排写的是图面脚号而非端口号；标签-端口号形式在排行中 0 次命中（无横线的 标签端口号形式 18 次） |
| Pop-X | 符号整体被丢弃（无 LD_SYMB2_SPECIAL） | 8145 | 100% |
| Pop-X | 槽位文字缺失（只能用 K_rec） | 410 | 5.0% |
| Pop-X | 另一端不是已解析端子（无端子直连） | 938 | 11.5% |
| Pop-X | 记录无导线句柄 | 1152 | 14.1% |
| Pop-X | 标签缺失 | 6 | 0.1% |

## 5. 三、候选生成与内部一致性

候选来源（脚本见 `tools/03_build_population.py`）：

- **K_num**（Pop-S）：标签 + `-` + 块内 TERMPOINT 端口号。
- **K_slot**（Pop-X）：符号标签 + `-` + `LD_SYMB2_TERM_TEXT_<pin>` 文字。
- **K_rec**（Pop-X）：LOGGEN 记录设备名 + `-` + 序号 seq。
- **K_row**（两类人口）：端子直连端子的端子排行中“端子排内接元件”文字，仅用于一致性检查，不生成身份。

一致性检查（`tools/06_consistency_conflicts.py`，结果见 `details.json` 的 `consistency`）：

| 检查 | 结果 | 解读 |
|---|---|---|
| K1 K_slot 与 K_rec（同一 Pop-X 引脚） | 7735/7735 一致（100%） | 两个独立元数据来源互证 |
| K2 K_rec 与端子直连端子排行文字 | 一致 3584，不一致 547（其中 65 同设备异脚、482 设备名不在排行中），无排行 3070；可比较中一致 86.8% | 不一致的 547 个中 526 个（96%）记录无导线句柄，多为总线/折线导线，排行只列出总线上的一个脚，属于拓扑造成的假阳性（见第 6 节视觉 C 层） |
| K3 K_num 与已识别内部端口身份 | 856 个已识别端口中，后缀等于端口号 56 个，6.5% | TERMPOINT 端口号是块内序号，不是图面脚号 |
| K4 同号重复（Pop-X K_rec） | 7940 个身份，47 个出现在多个物理引脚，其中 1 个涉及不同端子伙伴 | 很少，可控 |
| K4 同号重复（Pop-S K_num） | 829 个身份，548 个出现在多个引脚，379 个涉及不同端子伙伴 | 若接入会产生大量同号冲突 |
| K5 候选与已有非 discard 配对冲突（R1 且端子已消费） | 553 个端子（532 个 pass，21 个 review）；另一侧为裸数字旧值 25 个，其余为其它端子或脚号身份 | 不加门控会产生第二个不同身份的配对，见第 7、8 节 |

## 6. 四、视觉抽样（分层，共 66 例 + 冲突 4 例）

抽样脚本 `tools/05_sample_render.py`（种子 20261011 / 20261012），每例一张 PNG（上下文窗口 + 近景），红=脚号标记（TERMPOINT 折线），绿=脚号文字链接，蓝=标签，洋红=端子，橙=导线端点。判定标准：图上脚号文字与候选脚号一致、标签与候选标签一致、导线端点落在该标记上，三者都成立为 `correct`；与图相符但某一项不能完全确认为 `plausible`；图上找不到对应脚号为 `unverifiable`；脚号文字与候选不同为 `incorrect`。逐例判定记录在 `judgements.json`，图片在 `png/`。

| 层 | 来源 | n | correct | plausible | unverifiable | incorrect | 家族分布 |
|---|---|---|---|---|---|---|---|
| A | Pop-X R1（K_slot 与 K_rec 一致，身份唯一，端子排不冲突） | 26 | 26 | 0 | 0 | 0 | 正式典设 16，N2604 7，PAC 1，变压器测控柜 1，110kV 1 |
| A2 | 同上，第二次抽样（新种子，排除 A 层） | 20 | 20 | 0 | 0 | 0 | 正式典设 14，N2604 4，PAC 1，变压器测控柜 1 |
| B | Pop-X 仅 K_rec（槽位文字缺失） | 6 | 0 | 1 | 5 | 0 | 正式典设 4，PAC 1，110kV 1 |
| C | Pop-X K2 不一致（端子排行不一致） | 5 | 0 | 5 | 0 | 0 | 正式典设 3，110kV 1，变压器测控柜 1 |
| D | Pop-S K_num（标签 + 端口号） | 9 | 0 | 0 | 6 | 3 | 正式典设 4，N2604 2，变压器测控柜 1，PAC 1，110kV 1 |

- A 层（A + A2，46 例）：46/46 正确，点估计 100%，单侧 95% 精确下限 93.7%（`details.json` 的 `visual.A_all`）。A215 与 A217 是同一张图的两个项目副本，视为一个图样；A21 的记录无导线句柄，但图上导线确实连到该脚，仍判为正确。A07、A10、A15 等例证明 TERMPOINT 端口号与图面脚号不同（图上为 2，端口号为 1），而槽位文字与序号正确。
- B 层：B01、B02、B03、B05、B06 是同一种 CZ-N 装置模板，图上的 N 字样在器件顶部，导线却接在底部标记上，无法核实；B04 的 R- 是器件符号文字，判为 plausible。B 层不可核实的 5 例全部无导线句柄（B04 有导线句柄）。
- C 层：5 例图上脚号与候选一致（1、1、1、1、13），端子接在一根竖向总线上，总线连接多个脚，端子排行只列出其中之一。这说明 K2 的不一致多为总线假阳性，不能作为拒绝依据。
- D 层：D02（图上 5，端口号 1）、D04（图上 9，端口号 1）、D05（图上 2，端口号 1）三例明确错误；D01、D03、D06–D09 在标记处找不到脚号文字（D08 为单脚地线符号，只有 GND 字样）。K_num 确认 0 例正确，不可接入。
- 冲突例（`conflict_*.png`）：`bridge_mapping`（p000 F0007，候选 1FA-13 对现有同排短接 1QD4↔1QD7）图上导线确实从 1QD4 连到 1FA 的 13 脚，现有短接配对的走向存疑；`wire_component_mapping`（p000 F0011，候选 FZJ1-12 对现有 pass 配对的裸数字 12）图上脚号为 12，候选正确，旧值是修正对象；`semantic_mapping`（p006 F0011）候选 1-21ZK-1 与图上脚号 1 一致；`ordinary_pair`（p025 F0018，候选 3-4FA2-13 对现有 3-4Q2D2↔3-4Q2D17）导线从端子直连到 13 脚，现有普通配对看起来有误。这些冲突不能自动替换，需要复核。

## 7. 五、覆盖率估算与新增 issue

脚本 `tools/04_coverage_whatif.py`（严格口径，`tools/` 与 COV-GAP 层 b 一致；上界假设每个候选都能形成与端子的普通配对）。

| 规则 | 新增端子 | 严格覆盖 | 增量 |
|---|---|---|---|
| 基线（严格，round16） | | 47692 / 82680 = 57.68% | |
| R1：K_slot 与 K_rec 一致 + 身份唯一 + 端子排不冲突 + 端子未消费 | 3188 | 61.54% | +3.86 pp |
| 　其中有导线句柄（建议 pass 级候选） | 3041 | 61.36% | +3.68 pp |
| 　其中无导线句柄（建议 review 级） | 147 | | |
| R2：仅 K_slot 与 K_rec 一致（不看端子排） | 3198 | 61.55% | +3.87 pp |
| R3：仅 K_rec（无槽位文字） | 130 | 57.84% | +0.16 pp（不接入） |
| R4：K_rec（包含端子排不一致） | 3328 | 61.71% | +4.03 pp（不接入） |
| Pop-S：K_num（若接入） | 不建议接入（可达未消费端子 10859，错误率无法接受） | | |

- 按家族，R1 的增量：正式典设 1794，N2604 1147，110kV 103，PAC 92，变压器测控柜 52。
- COV-GAP 的 O3（17333）主体是 Pop-S（端子直连 18604 个引脚），本方案对它的增量为 0。
- **新增 issue 估计：**
  - 不加门控：R1 候选会在 553 个已有非 discard 配对的端子上产生第二个身份不同的配对（约 553 个潜在冲突 issue，其中 25 个是裸数字旧值，可作为修正）。
  - 加门控（只接入未消费端子）：约 1 个（Pop-X 同号重复且端子伙伴不同的身份 1 个）。
  - K_num 若接入：379 个同号身份涉及不同端子伙伴，即约 379 个真实同号冲突会被报出，同时产生大量伪连接。
- 第 7 节说明的“真实同号冲突会被报出来”在本方案中数量很小（Pop-X 1 个）；K_num 的 379 个则说明它本身不可靠。

## 8. 六、接入方案建议与门槛

### 8.1 来源门槛

| 来源 | 点估计精度 | 证据 | 结论 |
|---|---|---|---|
| Pop-X R1（K_slot 与 K_rec 一致，有导线句柄，身份唯一，端子未消费，端子排不冲突） | 100%（46/46） | 单侧 95% 下限 93.7% | 可接入为 review 级；升为 pass 需再抽 ≥149 例且全部正确（下限 ≥98%），当前缺 103 例 |
| Pop-X R1，无导线句柄 | 未单独抽样（A 层中 A21 一例可见导线） | | 只能 review |
| Pop-X R3（仅 K_rec） | 1 个 plausible / 6，5 个不可核实 | | 不接入 |
| Pop-X 端子排不一致（K2） | 视觉 5/5 plausible（总线） | | 不作拒绝依据，作 review 注记 |
| Pop-S K_num | 0 确认 / 9，3 个明确错误 | 与已识别名称一致率 6.5% | 不接入 |
| Pop-S 其它（标签+端口号以外，无元数据脚号） | 无元数据来源 | | 需要图面文字几何来源，另立评估（见第 12 节） |

### 8.2 接入点（建议，不在本次修改范围内）

- `src/dwg_audit/extract/superworks_loggen.py::read_page_wire_routes`：读取 DXF 时，对 LOGGEN 端指向的非 SW 插入（`insert_not_sw`），额外读取 `LD_SYMB2_LABEL` 文字与 `LD_SYMB2_TERM_TEXT_<pin>` 文字，作为 `slot_text`、`label_text`，并从记录中读取 `device`、`seq`。页面文档已打开，不需要二次读取 DXF。
- `src/dwg_audit/extract/superworks_loggen.py::EndpointIndex.same_page_end`：对 `insert_not_sw` 的端返回 `status=resolved`、`identity_source='symb2_text_slot'`、`identity = label + '-' + slot_text`，并附带 `record_seq_match` 标志（K1）。
- `src/dwg_audit/audit/superworks_extractor.py::_admit_wire_routes`：只对 `identity_source='symb2_text_slot'` 的端应用准入规则（见 8.3）。注意该文件目前有另一子代理在修改，接入时需要协调，本报告未触碰。

### 8.3 状态规则（建议）

- **pass**：K_slot 与 K_rec 一致；记录含导线句柄且该导线实体存在；另一端为已解析端子（端子/装置端子）且其端口未被任何非 discard 配对消费；同项目该身份只对应一个端子伙伴；若端子排行存在，则排行包含该身份。
- **review**：同上但导线句柄缺失；或仅 K_rec（无槽位文字）；或端子排行不一致且为总线拓扑（记录无导线句柄）；或同身份有多个端子伙伴。
- **reject**：标签缺失；设备名与标签不一致；另一端不是已解析端子；端子已被非 discard 配对消费（只进入冲突复核，不替换）。

### 8.4 结构化字段（建议）

`end.identity`，`end.identity_source`（`symb2_text_slot`），`end.label_text`，`end.slot_text`，`end.record_device`，`end.record_seq`，`end.terminal_port_number`（TERMPOINT 端口号，仅作记录，不作为脚号），`end.wire_handle`，`end.wire_entity_kind`，`end.row_check`（`agree` / `row_missing` / `disagree_*`），`route.admission_status` 与 `route.admission_reason`。

### 8.5 不要做的事

- 不要把 TERMPOINT 端口号当作脚号，不要用标签 + 端口号生成身份。
- 不要把端子排行的不一致当作身份错误，它在总线拓扑下会误报。
- 不要自动替换已有的通过配对；只替换裸数字旧值，且逐例复核。
- 不要改变 `walk()` 对无类别符号的处理（那会改变 SW 符号表与其它规则），先用 LOGGEN 端的路径做窄接入。

## 9. 七、对既有结论的修正与补充

1. LOGGEN-2 第 2 节（接入规则）提到“内部元件端的命名不一致（如 8ID3 与 8n1505）”。本次 Pop-X 的设备名与符号标签 100% 一致，槽位文字与序号 100% 一致，未见命名不一致；这一差异可能来自 Pop-S 的 K_num 或端子排的写法，而不是记录本身。
2. LOGGEN-2 将 `insert_not_sw` 视为“未被 SW 识别的元件引脚”。本次确认它们是 9734 个被 `walk()` 丢弃的 SYMB2 符号中被导线引用的那部分，且 5310 个符号带脚号文字链接。它们是本次唯一能给出可靠脚号的来源。
3. COV-GAP 的 O3 主体（17333 量级）与 Pop-S 端子直连的 18604 个引脚对应；它不是 Pop-X 类问题，本方案对其增量为 0。
4. ATTR-CENSUS 记录 `LD_SYMB1LIB_TERMTEXTPOINT` 指向 LWPOLYLINE；本次未把它纳入候选，未单独核实其在块内的指向。

## 10. 八、局限

- 视觉判定由单人完成，未做双盲复核；A 层 46 例中 A215/A217 为同一图样的副本，样本独立性略低。
- A 层样本数不足以统计证明 ≥98%；需要补抽到 ≥149 例全部正确。
- 覆盖率为上界：假设候选能形成普通配对，没有模拟配对与准入的完整流程。
- Pop-X 的类别未知，本次不区分它们是线圈、接插件还是其它元件。
- 记录无导线句柄的占 14%（Pop-X），其导线是否真的连到该脚只靠图面判断（A21 等例）。
- 只读 DXF 缓存；未重新转换 DWG。

## 11. 九、文件与复现

- `README.md`（本文件）
- `details.json`：人口、可得性、原因分布、一致性、覆盖率（`coverage`）、视觉分层结果（`visual`）、冲突例（`conflicts`）。
- `judgements.json`：逐例视觉判定（66 例）与判定标准。
- `samples.json`：66 例的抽样记录（层、家族、文件、候选、PNG 路径）。
- `png/`：66 张抽样图（`A*.png`、`B*.png`、`C*.png`、`D*.png`）+ 4 张冲突图（`conflict_*.png`）。
- `tools/`（按顺序）：
  - `01_load_replay.py <out.pkl>`：读取 77 个项目的回放表（`sw_ports`、`sw_symbols`、`sw_part_instances`、`sw_wire_routes`、`sw_strip_rows`、`sw_port_coverage`、`pairs`、`pages`）。
  - `02_scan_symb2.py <out.pkl>`：只读扫描冻结 DXF 中所有 SYMB2 插入（模型空间与块定义）。
  - `03_build_population.py <all.pkl> <scan.pkl> <out_dir>`：Pop-S 与 Pop-X 人口、候选与 K4 重号统计。
  - `04_coverage_whatif.py <all.pkl> <pop_x.pkl> <pop_s.pkl> <out.json>`：严格覆盖口径的 what-if。
  - `05_sample_render.py <all.pkl> <pop_x.pkl> <pop_s.pkl> <PIN-ID dir> <scratch>`：分层抽样与渲染（A2 补抽时设置 `EXTRA_A=1`）。
  - `06_consistency_conflicts.py <all.pkl> <pop_x.pkl> <pop_s.pkl> <scratch>`：K1–K5 一致性与冲突清单。
  - `07_conflict_render.py <all.pkl> <pop_x.pkl> <r1_conflicts.json> <png dir> <scratch>`：冲突例渲染。
  - `09_loggen_raw_category.py <pop_x.pkl> <corpus_manifest.json> <out.json>`：从 DXF 读回 LOGGEN 原始类别段（结果：8145 端全部为空）。
  - `08_final_summary.py <all.pkl> <PIN-ID dir> <scratch pop dir> <scratch cons dir>`：汇总生成 `details.json`。
- 运行环境：`python -X utf8`（`-I` 会忽略 `PYTHONIOENCODING`，控制台显示乱码但文件是 UTF-8）；依赖 `pandas`、`ezdxf`；`tools/05`、`tools/07` 读取 `.planning/superworks-adapter/round4/I/round4_samples_v2.py` 的绘图函数（只读导入）；`tools/03` 与 `tools/05` 的家族映射来自 `.planning/superworks-adapter/loop/COV-GAP/tools/family_map.json`。

### 中间大表（可删除）

中间产物（回放表 pickle、DXF 扫描结果、人口表、冲突清单、渲染缓存）保存在会话 scratchpad，不在仓库内：
`C:\Users\25788\AppData\Local\Temp\claude\F--workspace-XJToolkit\367e37bd-5006-413b-a449-e1c665a8b237\scratchpad\pin\`
（`all.pkl`、`scan_all.pkl`、`out\`、`cons\`、`render\`、`samples_first.json`、`x_ends.pkl`、`r1_conflicts.json`、`raw_category.json`）。完成评审后可删除该目录。仓库内 `.tmp/` 未新增文件。

## 12. 十、下一步（未做）

- 图面几何来源：Pop-S 的 D 层图上多数有脚号文字（5、9、2 等）却未被链接。若以“标记附近的模型空间文字”做几何身份，需要单独评估；当前 `_definition_ports` 只考虑块内文字，这是可能的缺口，本次未验证其精度。
- 补抽 A 层至 ≥149 例以统计证明 98%。
