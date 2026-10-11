# XPAGE-2：跨页矛盾候选的等价组收敛

分支 superworks-loop，基线 HEAD=9c1124e。未 commit、未 push；未改 V2 模块与 `symbol_port_proposal.py`；未加 PDF/OCR；无项目、句柄、数值特判；未整体豁免 SuperWORKS 来源。判定修改在 `src/dwg_audit/audit/superworks_cross_page.py`，接线在 `src/dwg_audit/report/superworks_artifacts.py`。

## 0. 结论

1. **等价组来源**：端子排上的黄色圆点与黄色短线（短接片）不在 XDATA 中，是页面几何。每张端子表的一列上，每行单元中心有一个黄色小圆（CIRCLE，颜色 2，半径 0.75），相邻两圆之间由两段长 1.75 的竖线跨过行边界相连（LINE，颜色 2）。`findings/lines.parquet` 保留了这些竖线，据此可以判出相邻行的短接，全量 13695 对。DXF 颜色核对：F0014、F0020 的短接段与圆均为颜色 2。其余结构化来源：范围端子（`U3D7~8` 包含 `U3D7`、`U3D8`）；一跳互指（行 A 的远端值为行 B 的身份，B 的远端值为 A 的身份，即两行间有一根直接导线）；同一目标端口被两行以上声明（共节点，仅限已消费目标）。
2. **候选数变化**：`contradiction_candidate` 2006 → **3**；`identity_mismatch_unconsumed` 1632 → **289**（全量 77 项目，离线用同一生产函数重算）。
3. **最终抽样精度**：剩余候选中抽 **43 例**（第 3 轮剩余 19 + 第 4 轮新抽 24），目视判定：疑似真实不一致 **19 例（44%）**；其余为命名写法（连字符）7、装置编号族（范围端子 `U1Dx~y`）16、同一水平导线上的标签 1。精度远低于 95%，且 `contradiction_candidate` 只剩 3 例，无法达到 40 例样本。
4. **是否加规则**：**否**。不新增 `R-CROSS-PAGE-DESTINATION-MISMATCH`，不产生新 issue。
5. **回放（10 项目）**：pairs 19677、issues 10 与 round17 逐条一致（增减均为 0）；consumed 5581 不变；含延续覆盖 6366 不变。候选：`contradiction_candidate` 123 → 0，`identity_mismatch_unconsumed` 148 → 11。
6. **单元测试**：`tests/unit/test_superworks_cross_page_links.py` 22 项（原 15 项 + 新增 7 项）；全量 `pytest tests/unit` 为 1936 passed, 1 skipped。

XPAGE 中的 9/10 精度判断已作废（见 `XPAGE/README.md` 末尾的主线程复核）。

## 1. 等价组来源（结构化来源的核查）

| 来源 | 结论 | 证据 |
|---|---|---|
| 短接片 XDATA（`LD_DZPNO_*`、`LD_CONNECT_DOT`） | 不可用 | 黄色圆与竖线无 XDATA。`LD_CONNECT_DOT` 只在原理图页（p001 中为 S0004/S0007/S0008/S0009/S0010），端子表页上没有。`LD_DZPNO_DXLX` 的取值（`&`、`*`、`@`）与 `LD_DZPNO_SymbBwrite` 的取值（`UA` 等）不是短接标记。 |
| `series_chains.json` | 不可用 | p001 的 `chain_count` 为 0。 |
| `terminal_short_bridge` / `strip_corroborated`（extractor） | 已覆盖的子集 | 同表同名引用在配对层已建立，本次不重复建模。 |
| `LD_DzbJD_JDBlock` | 不可用 | `src/` 中无引用（只在 `symbol_port_proposal.py` 的一条说明文字中出现）。 |
| 页面几何短接（采用） | 采用 | 竖直长 1.75 的线段成对跨过行边界，两端分别落在相邻行的圆上（圆心 = 行文字 y + 1.5，行距 5）。F0014 中 `7UD16-17-18`、`1ID5-6-7-8`、`ZD1-2`，F0020 中 `4P2D1…10`，与颜色 2 的 DXF 段一一对应。 |
| 范围端子（采用） | 采用 | `expand_identity`：`U3D7~8` → `{u3d7~8, u3d7, u3d8}`。 |
| 一跳互指（采用） | 采用 | 行 A 的连接文字为行 B 的身份，且 B 的连接文字含 A 的身份（互指）。 |
| 共节点（采用，仅已消费目标） | 采用 | 对未消费目标也使用时会把 1632 → 685 的弱候选过度解释，因此限定。 |

几何规则放在生产代码中：`short_bridge_pairs(strip_rows, lines)`（`superworks_cross_page.py`），由 `superworks_artifacts._cross_page_continuity` 用 `artifacts.lines` 与行位置调用。规则不读颜色（产物中不保存颜色），只依赖几何，颜色仅用于核对。

## 2. 判定修改（`superworks_cross_page.py`）

- 第一遍解析所有“行 → 目标”引用（行需有支撑配对），记录每个目标端口被哪些行声明。
- 第二遍对不一致的引用（`differs`）依次判断，任一成立即为等价：
  1. 目标身份 ∈ 行所在等价组的身份（`target_in_group`）；
  2. 目标身份 ∈ 等价组的远端值（`target_in_group_far`，即 `continuity_conn` 在组上的推广）；
  3. 目标的另一端 ∈ 等价组的身份或远端值（`other_in_group`）；
  4. 一跳（互指行所在组）上的身份或远端值（`target_in_hop` / `other_in_hop`）；
  5. 已消费目标且被 ≥2 行声明（`shared_target_node`）。
  成立则 `relation = continuity_group`，记入 `links`，`covers_target = False`，不计覆盖、不成为候选。
- 已消费目标的另一端没有值（PW 系列遗留配对）时不计候选（`consumer_other_empty`，全量 29 条），因为没有可比较的证据。
- 既有语义不变：`continuity_conn` / `continuity_row` 的覆盖、`multi_claim_not_covered`、`consumed_agrees` 的跳过。
- 连续覆盖不因等价组增加（未经抽样验证，不计入）：全量 `covered_targets` 仍为 7854。
- 输出变化：`sw_cross_page_links` 全量行数 11880 → 15134（+3254，即 `continuity_group` 记录数，与各解释原因之和一致）；`summary.cross_page.stats` 新增 `bridge_links` 与各 `continuity_group:<reason>`。

## 3. 迭代（候选数与抽样）

| 轮 | 规则（累计） | contradiction_candidate | identity_mismatch_unconsumed | 抽样与判定 |
|---|---|---|---|---|
| 0 | X2 基线（round17） | 2006 | 1632 | 旧 10 例（XPAGE，已作废） |
| 1 | + 黄线短接链（几何） | 387 | 未单列 | 未抽样 |
| 2 | + 一跳互指 + 范围展开 | 260 | 未单列 | `png/it2/` 42 例（seed 17）：另一端无值 10；共节点（同一已消费目标 ≥2 行）约 30；同线/同族 1；疑似真实 1–2（仅部分目视，其余以数据与同族图判定） |
| 3 | + 共节点（仅已消费）+ 另一端无值不计候选 | **3** | 685 | `png/it3/` 43 例（seed 17，池 688）：其中 24 例在第 4 轮被解释（W 族与部分 D 族，目标身份为组内远端），剩余 19 例：疑似真实 4 例（21%），其余为 B 类 15 例 |
| 4 | + 目标身份 ∈ 组远端 / 一跳远端 | **3** | **289** | `it4/` 新抽 24 例（seed 29）：疑似真实 15 例（63%），B 类 9 例 |

合计最终剩余池中抽样 43 例（第 3 轮剩余 19 + 第 4 轮 24）：疑似真实 19 例（44%）。

说明：第 1、2 轮的候选数来自 `tools/xp2_eval.py` 的分项标记（与生产函数语义一致，但不是直接跑生产函数）；第 3、4 轮来自生产函数 `build_cross_page_links`（`tools/xp2_offline.py`）。`identity_mismatch_unconsumed` 只在生产函数中单独计数。

## 4. 最终抽样表（43 例，目视判定）

判定说明：A = 疑似真实不一致（行的远端值或去向与目标端口所接线号/装置明显不同，图上未见等价）；B1 = 命名写法（连字符，`K861-2X3` 与 `K8612X3`）；B2 = 装置编号族（目标为 `U1Dx~y` 范围端子，行为 `Uk Dx`，D 号一致、U 号不同）；B3 = 同一水平导线上的其他标签（需要导线几何规则，未实现）。B2 中 R21、R24、R38、R39、R41、R42 与 W06 按同族归类，未逐张目视。

| 样本 | 项目 | 行 → 目标（页） | 行远端值 | 目标另一端 | 判定 | 说明 |
|---|---|---|---|---|---|---|
| C01 | p069 | 57UD16 → 57nD10（5 页） | 57nd8 | 57nd12 | B3 | 57UD16 与目标 57nD10 共在同一水平导线（D8/D10/D12 标签），另一端 57nD12 同线 |
| C02 | p000 | 1KD5 → 1n114（5 页） | 1clp4-1, 1qd19 | 1qd22 | A | 1KD5 → 1n114；目标 114 线去向 1qd22，图上未见等价（待人工核对） |
| C03 | p000 | 1QD12 → 1QD10（7 页） | 1n413 | 1qd9 | A | 1QD12 → 7 页 1QD10；该端子实际接线连 1QD9（同一水平线），与行远端 1n413 不符 |
| D20 | p029 | 3-4X1D1 → K8632X2（21 页） | k863-2x2 | - | B1 | 远端 k863-2x2 与目标 K8632X2 只差连字符 |
| D24 | p029 | 1-4Q1D27 → K8611X9（15 页） | k861-1x9 | - | B1 | 远端 k861-1x9 与目标 K8611X9 只差连字符 |
| D25 | p030 | 3-4QD24 → K8632X13（21 页） | fzj4-1, k863-2x13 | - | B1 | 远端 k863-2x13 与目标 K8632X13 只差连字符 |
| D26 | p049 | 3-4QD22 → 3-2n226（15 页） | 3-4fa-14 | - | A | 远端 3-4fa-14，目标线号 3-2n226，装置不同 |
| D30 | p030 | 3-4XD1 → K8632X2（21 页） | k863-2x2 | - | B1 | 远端 k863-2x2 与目标 K8632X2 只差连字符 |
| D31 | p031 | 1-4Q2D25 → K8621X7（16 页） | k742-x4 | - | A | 远端 k742-x4，目标为 K862 装置 1X7 |
| R34 | p074 | 1-25U6D3 → 1-25U1D3~4（4 页） | 1-25zkk6-3 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R35 | p074 | 1-25U8D3 → 1-25U1D3~4（4 页） | 1-25zkk8-3 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R36 | p074 | 1-25U5D6 → 1-25U1D5~6（4 页） | 1-25u4d6, 1-25u6d6 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R37 | p074 | 2-25U6D2 → 2-25U1D1~2（6 页） | 2-25u5d2, 2-25u7d2 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R38 | p074 | 2-25U5D2 → 2-25U1D1~2（6 页） | 2-25u4d2, 2-25u6d2 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R39 | p074 | 1-25U8D4 → 1-25U1D3~4（4 页） | 1-25u7d4 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R40 | p074 | 2-25U4D3 → 2-25U1D3~4（6 页） | 2-25zkk4-3 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R41 | p074 | 1-25U7D5 → 1-25U1D5~6（4 页） | 1-25zkk7-5 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R42 | p074 | 2-25U7D5 → 2-25U1D5~6（6 页） | 2-25zkk7-5 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| R43 | p074 | 1-25U6D1 → 1-25U1D1~2（4 页） | 1-25zkk6-1 | - | B2 | 目标为 1-25U1/2-25U1 范围端子，D 号与行一致、U 号族不同 |
| W01 | p024 | 2-7XD1 → 1n101（12 页） | 1-7xd2, 2-7n819 | - | A | 2-7XD1 远端 1-7xd2/2-7n819，目标线号 1n101 不见于本行 |
| W02 | p037 | 4Q1D33 → 4n1005（10 页） | 4n1711 | - | A | 4Q1D33 远端 4n1711，目标线号 1005 |
| W03 | p057 | 7QD18 → 7n202（6 页） | 7qk-4 | - | A | 7QD18 远端 7qk-4，目标线号 202 |
| W04 | p057 | 7QD17 → 7n202（6 页） | 7n602 | - | A | 7QD17 远端 7n602，目标线号 202（同页相邻 602/202） |
| W05 | p072 | 1YD1 → 1n1327（11 页） | 1n1316 | - | A | 1YD1 远端 1n1316，目标线号 1327 |
| W06 | p024 | 2-7XD2 → 1n101（12 页） | 2-7n820 | - | A | 2-7XD2 远端 2-7n820，目标线号 1n101（同族 W01，未逐张目视） |
| W07 | p073 | 1YD1 → 1n1327（11 页） | 1n1316 | - | A | 1YD1 远端 1n1316，目标线号 1327（与 W05 同行） |
| W08 | p037 | 4Q1D32 → 4n1005（10 页） | 4n1710 | - | A | 4Q1D32 远端 4n1710，目标线号 1005 |
| D09 | p030 | 1-4Q2D15 → K8621X5（16 页） | k862-1x5 | - | B1 | 远端 k862-1x5 与目标 K8621X5 只差连字符 |
| D10 | p000 | 4P2D2 → K8612X6（9 页） | fzj1-8 | - | A | 4P2D2 远端 fzj1-8，目标为 K861 装置 2X6 |
| D11 | p000 | 4Q1D24 → K8612X13（9 页） | fzj2-1, k861-2x13 | - | B1 | 远端 k861-2x13 与目标 K8612X13 只差连字符 |
| D12 | p004 | 4Q1D16 → K8611X5（9 页） | fzj1-3 | - | A | 4Q1D16 远端 fzj1-3，目标为 K861 装置 1X5 |
| D13 | p030 | 1-4Q1D25 → K8611X7（15 页） | k741-x4 | - | A | 1-4Q1D25 远端 k741-x4，目标为 K861 装置 1X7 |
| D14 | p033 | 1-7QD9 → 1QD23（9 页） | 1-7n832, 1qd24 | - | A | 1-7QD9 远端 1qd24，目标 1QD23（相邻编号） |
| D15 | p029 | 1-4Q1D28 → K8611X9（15 页） | fzj1-7 | - | A | 1-4Q1D28 远端 fzj1-7，目标为 K861 装置 1X9 |
| D16 | p060 | 1-21YD1 → 2-21GD1（5 页） | 1-21n108, 2-21gd17 | - | A | 1-21YD1 远端 2-21gd17，目标 2-21GD1（相邻编号） |
| D17 | p029 | 3-4Q2D16 → K8641X5（24 页） | fzj5-3 | - | A | 3-4Q2D16 远端 fzj5-3，目标为 K864 装置 1X5 |
| D18 | p004 | 4XD5 → K8612X3（9 页） | k861-2x3 | - | B1 | 远端 k861-2x3 与目标 K8612X3 只差连字符 |
| R19 | p074 | 1-25U4D4 → 1-25U1D3~4（4 页） | 1-25u3d4, 1-25u5d4 | - | B2 | 目标为 U1 范围端子，D 号与行一致、U 号族不同 |
| R20 | p074 | 2-25U4D5 → 2-25U1D5~6（6 页） | 2-25zkk4-5 | - | B2 | 目标为 U1 范围端子，D 号与行一致、U 号族不同 |
| R21 | p074 | 1-25U4D1 → 1-25U1D1~2（4 页） | 1-25zkk4-1 | - | B2 | 目标为 U1 范围端子，D 号与行一致、U 号族不同 |
| R22 | p074 | 2-25U6D1 → 2-25U1D1~2（6 页） | 2-25zkk6-1 | - | B2 | 目标为 U1 范围端子，D 号与行一致、U 号族不同 |
| R23 | p074 | 2-25U7D4 → 2-25U1D3~4（6 页） | 2-25u6d4, 2-25u8d4 | - | B2 | 目标为 U1 范围端子，D 号与行一致、U 号族不同 |
| R24 | p074 | 1-25U7D4 → 1-25U1D3~4（4 页） | 1-25u6d4, 1-25u8d4 | - | B2 | 目标为 U1 范围端子，D 号与行一致、U 号族不同 |

## 5. 是否启用规则

不启用。`R-CROSS-PAGE-DESTINATION-MISMATCH` 的门槛是抽样精度 ≥95% 且样本 ≥40。本次最终抽样为 44%，且 `contradiction_candidate` 只有 3 例。`identity_mismatch_unconsumed`（289 例）的主要成分是命名写法与装置编号族（B1 + B2 = 23/43 ≈ 53%），它们本身就是等价未识别，不应报为问题。

后续建议（需单独决定，不在本切片内）：
- 连字符归一（`K861-2X3` ↔ `K8612X3`）是否作为身份形式的通用归一，需要确认它不会合并真实不同的装置。
- 装置编号族（`U1Dx~y` 与 `Uk Dx`）是否属于图纸命名约定，需要图纸或设计方确认。
- 同一水平导线上的多个标签（B3）可用“目标与另一端位于同一绘制导线”的几何规则解释。

## 6. 回放对比

- 10 项目回放（`.tmp/loop_xpage2_10proj`，快照 `.tmp/loop_xpage2_src`）与 `.tmp/superworks_round17_full` 逐项目对比（`XPAGE/tools/compare_runs.py`）：pairs 19677 = 19677（增减 0），issues 10 = 10（增减 0），consumed 5581 = 5581，`consumed_with_continuity` 6366 = 6366。
- 候选（10 项目）：`contradiction_candidate` 0（round17 为 123），`identity_mismatch_unconsumed` 11（round17 为 148）。与离线生产函数的 10 项目结果一致（11）。
- 全量：未做全量回放（未加规则；pairs/issues 不变由 10 项目回放与只读的函数保证）。全量候选与连接表的变化由离线 `xp2_offline.py` 给出（`.tmp/loop_xpage2/offline_full_final.json`）。
- 新增 issue：全量 0，10 项目 0。无新增 issue，因此无需截图复核。

## 7. 遗留风险

1. **几何规则的边界**：依赖竖线长 1.75、行距 5、列位于行单元中心偏移 2.5 处。其他比例的图纸会漏检（偏保守，只会多留候选）。未对全量做颜色核对，仅 F0014、F0020 的段与圆做了 DXF 颜色核对。
2. **共节点规则（`shared_target_node`，全量 228 例）**：可能遮蔽“两行中有一行写错目标”的真实不一致。未逐条核对。
3. **目标身份 ∈ 组远端（`target_in_group_far`，全量 989 例）**：新增解释量最大的一类，只对 W 族与少量样例做了核对（W05、W06、1XD2 等）。
4. **渲染器显示不完整**：`round4` 的 DXF 渲染对部分黄圆未画出（F0020 的 4P2D 表第 4、5 行的圆在 DXF 中存在），目视判读时以 DXF 为准。
5. **真实不一致的线索**：`C03`（p000，行 1QD12 → 7 页 1QD10，但该端子实接 1QD9）、`C02`（p000，行 1KD5 → 1n114）等，建议人工核对，不应直接作为问题报告。
6. **未解决的等价类型**：B1（连字符命名）、B2（装置编号族）、B3（同线标签）。它们占抽样的 24/43，是精度不足的主因。

## 8. 文件

- `README.md`：本文件。
- `png/it2/`（42 张）、`png/it3/`（43 张 + `index.json`）、`it4/png/`（24 张 + `index.json`）：各轮抽样的两面板 PNG。`png/it3/` 中 24 张已被第 4 轮解释，仅作记录。第 2 轮的索引文件在覆盖中丢失，抽样编号可由 `xp2_sample.py --seed 17` 复现。
- `judgements_final.json`：最终 43 例的判定（标签与说明）。
- `tools/`：
  - `xp2_load.py`：读取 round17 产物（含行的表头分组）。
  - `xp2_bridge.py`：第 1 轮的几何短接链（与生产函数同一规则，保留以复现第 1–2 轮）。
  - `xp2_eval.py`：第 1–3 轮的分项标记与候选统计。
  - `xp2_offline.py`：用生产函数离线重算全量。
  - `xp2_sample.py`、`xp2_sample_prod.py`：分层抽样与渲染。
  - `xp2_judgements.py`：目视判定表与 `judgements_final.json`。
- 生产代码：`src/dwg_audit/audit/superworks_cross_page.py`（`short_bridge_pairs`、`expand_identity`、`build_cross_page_links(..., bridges=())`），`src/dwg_audit/report/superworks_artifacts.py`（接入 `artifacts.lines`）。
- 测试：`tests/unit/test_superworks_cross_page_links.py`（22 项）。
- 临时产物：`.tmp/loop_xpage2/`（评估 JSON、离线重算、回放日志、对比 JSON、判定表），`.tmp/loop_xpage2_10proj/`（10 项目回放），`.tmp/loop_xpage2_src/`（回放快照）。
- 复现：
  - `python .planning/superworks-adapter/loop/XPAGE-2/tools/xp2_offline.py .tmp/superworks_round17_full .tmp/loop_xpage2/offline_full_final.json`
  - `python .planning/superworks-adapter/replay.py --output .tmp/loop_xpage2_10proj --snapshot .tmp/loop_xpage2_src --projects p001 p003 p022 p044 p050 p051 p061 p071 p075 p076`
  - `python .planning/superworks-adapter/loop/XPAGE/tools/compare_runs.py .tmp/superworks_round17_full .tmp/loop_xpage2_10proj --json .tmp/loop_xpage2/compare_10proj.json`
