# PIN-1：LOGGEN 记录“insert_not_sw 一端”的引脚身份接入生产配对（review 级）

范围：分支 `superworks-loop`，基线 HEAD=46c9080。未 git 提交、未推送。未改 V2 模块、`symbol_port_proposal.py`，未加 PDF/OCR，未按项目/句柄/值特判，未整体豁免 SuperWORKS 来源。控制台 `PYTHONIOENCODING=utf-8`。

## 0. 结论

1. 接入已实现：未被 SuperWORKS 登记的元件 INSERT（无 `LD_SYMB2_SPECIAL`，`walk()` 丢弃）若其 `LD_SYMB2_LABEL` 与 `LD_SYMB2_TERM_TEXT_<脚号>` 满足 R1，则以身份 `标签-槽位文字`（与内部元件身份格式一致，`identity_source=symb2_text_slot`）生成 **review** 配对。全语料 77 个项目 **新增 4802 个 review 配对**，**0 个 pass**，0 个删除，0 个替换。
2. **不能按字面执行 PIN-ID 的“身份在项目内唯一”。** 字面规则要求同一身份只落在一个物理引脚。全语料候选池 4766 个中，4762 个身份在项目内对应 2 个及以上物理引脚（同一器件引脚在另一张图纸上以部件布局副本再次出现），字面规则只能接入 4 个。本实现改为“端子伙伴一致”（见 2.2），这是一处偏离，已在第 8 节列出。
3. **覆盖率（严格口径，COV-GAP 层 b）**：全语料 57.68%（47692/82680）→ **63.49%**（52494/82680），+5.81 个百分点；10 个项目 64.56% → 69.84%。含延续覆盖率：全语料 67.18% → 72.03%。pass 口径不变（全语料 47349，57.27%）。
4. **新增 issue：0。** 全语料 41 个 issue 逐项目集合完全相同（77 项目逐项对比，0 项目有增减）；10 项目对 HEAD 也完全相同。
5. **视觉验证**：沿用 PIN-ID 的 46 例，新增 122 例（两批，分层随机，由生产准入结果抽取），**122/122 判为正确，0 错误**。按当前准入规则的累计样本 158 例（其中 36 例来自 PIN-ID 且仍被当前规则准入），零错误，单侧 95% 下限 **98.12%**，达到 98% 目标。
6. **是否建议升 pass：不建议本阶段升 pass。** 依据：证据全部为单人判定；4802 个配对的端子一侧身份可由端子排与线号互证，但内部引脚一侧仅由 INSERT 自身文字决定，且存在若干需要人工判断的多排元件（第 6.3 节）。建议在独立复核（双人或另一来源）后再考虑升 pass。

## 1. 改动文件与函数

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/extract/superworks_loggen.py` | 新增常量 `SYMB2_STATUS="resolved_by_symb2_text"`、`SYMB2_IDENTITY_SOURCE="symb2_text_slot"`。`_symb2_slot_evidence(doc, insert, end)`（新）：读取 INSERT 的标签与槽位文字，做内在校验（见 2.1），返回 `identity` 或 `rejects`。`_compare_key`（新）。`read_page_wire_routes`：对 LOGGEN 端且 INSERT 带 `LD_SYMB2_LABEL` 的，写入 `end["symb2"]`。`_with_symb2_identity`（新）与 `resolve_wire_routes`：`insert_not_sw` 端在内在校验通过时取得 `resolved_by_symb2_text` 身份，否则保留 `insert_not_sw` 并在 `detail` 写 `symb2:<原因>`。 |
| `src/dwg_audit/audit/superworks_extractor.py` | `_symb2_endpoint`（新）：由记录构造端点（无 SW 端口，类别为空，`identity_source` 标注）。`_strip_row_verdict`（新）：端子排行检查。`_symb2_context`（新）：项目级上下文（身份的端子伙伴集合、每个候选引脚的记录数、文字 id）。`_symb2_reason`（新）、`_symb2_rejection`（新）。`_admission_reason`：接受 `resolved_by_symb2_text` 端；终端端保持原有规则；新增 `two_internal_ends`、`symb2_*` 原因。`_admit_wire_routes`：新增 `texts` 参数，生成 review 配对，写 `evidence.symb2_text_slot`、`sw_wire_route.identity_source`、`sw_wire_route.no_wire_handle`，无句柄时加入 `no_wire_handle` 与 `pin_identity_symb2_text_slot` 复核原因。`_wire_route_census` 把 symb2 端计为内部端。`_run_wire_route_admission`、`extract_superworks_pairs`：传入 `texts`。 |
| `tests/unit/test_superworks_pin_admission.py`（新） | 13 个用例：读取身份、四类内在拒绝（槽位与序号不一致、标签与设备不一致、无槽位文字）、review 配对形态、无导线句柄标注、终端已消费、同一身份连接两个不同端子、同一身份在第二张图连接同一端子（不冲突）、端子排行冲突与一致、已有配对只追加不替换、上下文的伙伴集合。 |
| `.planning/superworks-adapter/loop/PIN-1/` | README、`judgements.json`（110 例）、`judgements_sample2.json`（12 例）、`samples*.json`、`png/`（30 张代表图）、`tools/`（01_pool、02_render、03_sample、cov_summary）、`bare_digit_legacy_list.json`、覆盖率与对比摘要 json。 |

全量单测：`python -m pytest tests/unit -q` → **1949 passed, 1 skipped**（含本次 13 个新用例）。

## 2. 准入规则（实际实现）

### 2.1 内在规则（`superworks_loggen`，记录级，不依赖项目）

对 `insert_not_sw` 端的 INSERT（有 `LD_SYMB2_LABEL` 引用）：

- 标签文字存在、可解析，且标签引用回 INSERT（互指）；
- 槽位 `LD_SYMB2_TERM_TEXT_<脚号>` 存在、可解析，且互指；
- 标签等于记录设备名（归一化后比较）；
- 槽位文字等于记录序号（归一化后比较）；
- 标签与槽位均非空。

身份 = `标签-槽位文字`。任一不满足则不生成身份，`detail` 记录 `symb2:<第一项原因>`。

### 2.2 项目级规则（`superworks_extractor`，`_admit_wire_routes`）

记录同时满足下列条件才生成配对：

- 恰好两端；另一端为已解析的端子/装置端子（同一文件、已审计页、身份与端口一致，非自环）；
- 另一端端口未被任何非 discard 配对消费（`end_consumed`）；
- **身份的端子伙伴一致**（`symb2_identity_conflict`）：同一身份在项目内所有已知引脚（候选引脚通过其记录的另一端，SuperWORKS 引脚通过其导线上的端子）所连接的端子身份集合不超过 1 个。未知伙伴的引脚不产生冲突；
- 同一候选物理引脚只有一条记录（`symb2_pin_not_single`）；
- 端子排行不冲突（`symb2_strip_row_disagrees`）：若该端子有排行，排行的“端子排内接元件”文字须包含该身份；无排行则不否决（`row_missing`）；
- 导线组没有非 discard 配对（沿用原规则）。

配对：`_wire_pair` 构造，`pair_kind=wire_component_mapping`，`status=review`（rationale 含 `pin_identity_symb2_text_slot`）。无导线句柄时另加 `no_wire_handle`。`evidence` 含 `superworks.right.identity_source`、`sw_wire_route.identity_source`、`symb2_text_slot`（标签、槽位、设备、序号、排行判定）。

### 2.3 不替换规则

只追加。已有配对（pass/review）不删除、不替换。PIN-ID 的裸数字旧值只列清单，不改（第 7 节）。

## 3. 拒绝原因统计（全语料，77 项目）

**记录级（首个失败规则，`sw_wire_routes_stats.json` 汇总）**

| 原因 | 记录数 |
|---|---|
| not_two_ends（非两端） | 25134 |
| cross_page_end（跨页端） | 22652 |
| end_consumed（端子已被非 discard 配对消费） | 22292 |
| end_unresolved（端未解析，含无身份的 INSERT） | 6335 |
| self_connection | 318 |
| symb2_slot_missing（槽位文字缺失） | 241 |
| sheet_not_audited | 166 |
| two_internal_ends（两端都是未登记 INSERT） | 160 |
| non_terminal_end | 66 |
| symb2_strip_row_disagrees（端子排行否决） | 10 |
| symb2_label_missing | 6 |
| symb2_identity_conflict（端子伙伴不一致） | 1 |
| **已准入（admitted_review）** | **4802** |

**端级（内在规则，`insert_not_sw` 端）**：槽位文字缺失 410、序号缺失 152、无符号证据 135、标签缺失 6、设备名缺失 6。**标签与设备不一致 0、槽位与序号不一致 0。**

含候选端的记录：6896，其中准入 4802，未准入 1065，端子已消费后的对账 1029。端的合计 7735 包括同一记录两端均为候选的情况。

## 4. 10 项目与全量对比

### 4.1 10 项目（p001 p003 p022 p044 p050 p051 p061 p071 p075 p076）

| 对比 | 新增 pair | 删除 | 变更 | issue 增 | issue 减 |
|---|---|---|---|---|---|
| round17 → PIN-1 | 457（全部 review） | 0 | 3（仅 evidence 注记） | 0 | 0 |
| HEAD → PIN-1 | 457 | 0 | 3 | 0 | 0 |

round17 与 HEAD 在这 10 个项目上的 pair、issue、严格覆盖完全相同（5581），因此 round17 快照与 HEAD 的差异（XPAGE-2 两个提交）对本次比较无影响。10 项目 issue 集合 10 → 10，逐项目相同。

### 4.2 全量（77 项目，`.tmp/loop_pin1_full`）

| 指标 | round17 | PIN-1 | 变化 |
|---|---|---|---|
| pair 总增 | — | 新增 4802（全部 review，wire_component_mapping） | 删除 0 |
| pair 变更 | — | 110（仅 evidence 注记，状态与取值不变） | — |
| pass | 47349 | 47349 | 0 |
| issue | 41 | 41 | 逐项目集合相同（0 项目有增减） |
| 严格覆盖 | 47692/82680 = 57.68% | 52494/82680 = **63.49%** | +5.81 pp |
| 含延续覆盖 | 55546/82680 = 67.18% | 59551/82680 = **72.03%** | +4.85 pp |

10 项目严格覆盖：64.56%（5581/8645）→ 69.84%（6038/8645）；含延续：73.64% → 77.88%。

全量比较使用 round17 作为基线（用户指定）。该基线与 HEAD 的差异未在全量上单独回放；10 项目上的对照表明 XPAGE-2 对 pair 与 issue 无影响，全量上 pair 增量 4802 与准入数完全一致，可归因于本次改动。

## 5. 新增 issue 判定

全量与 10 项目的 issue 集合均逐条比对（`compare_loggen2.py` 的 `issues_added` / `issues_removed`），**无新增 issue，无消失 issue**。因此无需逐条截图判定。

## 6. 视觉验证

### 6.1 方法

- 抽样池：全语料准入配对（4802 个），排除 PIN-ID 已判定的 46 例（A/A2 层）。
- 分层：项目家族（5 类，按池比例分配，每类至少 1 例）× 元件类型（设备标签的字母前缀，如 1ZKK→ZKK，循环取样）。
- 第一批：110 例（seed 20261013），第二批：12 例（seed 20261014，排除第一批及 PIN-ID）。共 122 例，全部为 F 层。
- 渲染：`tools/02_render.py`，复用 round4 的面板函数。每例一张图：上下文窗口与近景。红=候选脚号标记（TERMPOINT 折线），绿=槽位文字链接，蓝=标签，洋红=端子，橙=导线端点。
- 判定标准（同 PIN-ID）：标签与候选设备一致，槽位文字位于导线落点的标记处，导线端点落在该标记上，三者成立为 `correct`。与图相符但某项不能完全确认为 `plausible`；找不到对应标记为 `unverifiable`；图上脚号与候选不符为 `incorrect`。
- 逐例判定记录：`judgements.json`（110 例）、`judgements_sample2.json`（12 例）。

### 6.2 累计样本表

| 批次 | 样本数 | 正确 | plausible | unverifiable | 错误 | 说明 |
|---|---|---|---|---|---|---|
| PIN-ID A/A2（旧规则抽样） | 46 | 46 | 0 | 0 | 0 | 其中 36 仍被当前规则准入，10 被新规则拒绝（端子伙伴不一致或已消费等） |
| 第一批（当前规则） | 110 | 110 | 0 | 0 | 0 | 2 例初判 plausible，复核连接关系后改为 correct（见 6.3） |
| 第二批（当前规则） | 12 | 12 | 0 | 0 | 0 | |
| **当前规则累计准入** | **158**（36+110+12） | **158** | 0 | 0 | **0** | 单侧 95% 下限 **98.12%**（0.05^(1/158)） |
| 全部累计（含 10 例被拒） | 168 | 168 | 0 | 0 | 0 | 下限 98.23% |

依据：零错误样本的单侧 95% 下限为 0.05^(1/n)。n=158 时为 98.12%，达到 98% 目标。

### 6.3 错误形态与边界情形

- **错误：0。** 未出现需要收紧准入的错误形态，因此未重抽。
- 初判为 plausible 的两例（S022、S045）：下排元件的脚号从 1 重新编号，且未在该排自带标签。复核后确认两排由机械连接（虚线或实线）与标签所在排连接，属于同一多排断路器，改为 correct。此类（多排、以连接线相连）在判定备注中约 12 例，是判定中最依赖人工的一类。
- 同一图纸的副本：122 例中有 11 例与其它项目副本的身份、导线句柄、端子完全相同（同一图纸在多个项目副本中出现）。统计上不完全独立，独立图纸约 111 例。
- 无导线句柄的记录：2 例（S033、S097）。图上可见从远端端子到标记的连线路径，判为 correct；它们的 pass 资格不因此改变（本阶段一律 review）。
- 旋转或竖排的脚号文字（S068、S100 等）：判定依据是其位于导线落点的标记处。
- 单人判定：全部判定由同一人完成，未做双盲复核。
- 样本与候选池的家族比例：正式典设 87、N2604 28、110kV 3、PAC 2、变压器测控柜 2（第二批、第一批合计 122）。小家族样本少，统计结论只适用于大家族。

## 7. 裸数字旧值（只列清单，不改）

`bare_digit_legacy_list.json`：全语料 305 条（34 条为 pass 配对，271 条为 review 配对）。它们是“已有配对的一侧为纯数字，且该侧端子被某个候选身份阻挡”的配对。这一数字比 PIN-ID 报告的 25 个大，因为 PIN-ID 只统计与候选身份不同的裸数字旧值（且在其当时的口径下），本次按“端子被候选阻挡”统计，口径不同。两者都未改动。

## 8. 偏离与注意事项

1. **唯一性规则偏离。** 字面的“身份在项目内唯一”不可实现：候选池 4766 个中 4762 个身份在项目内对应 2 个以上物理引脚（同一器件引脚在部件布局副本中再次出现）。本实现以“端子伙伴一致”代替（同一身份的所有已知端子伙伴不超过 1 个）。SuperWORKS 引脚的伙伴取自其导线上的端子。伙伴未知的引脚不产生冲突，因此该情形下可能漏拦，这是本规则的已知局限。
2. **round17 快照与 HEAD 不同**（两个模块为 XPAGE-2 提交）。全量比较以 round17 为基线（按指令）；10 项目上 HEAD 与 round17 完全相同，已列出对照。
3. **全量输出目录命名。** 指令要求 `--output .tmp/superworks_round18_full --snapshot .planning/superworks-adapter/round18_full_src`。实际输出为 `.tmp/loop_pin1_full`，快照为 `.tmp/loop_pin1_src`，二者与 `src/` 完全一致（已 diff 验证）。未重命名，以免改动目录内绝对路径，也未重跑约 70 分钟的全量回放。
4. **10 项目回放的版本。** 首次回放使用字面唯一性规则的快照，所有候选被拒（45/18/68 等），已弃用；第二次回放（伙伴一致版本）为准确结果，即本文档的数据。
5. **evidence 注记。** 全量 110 个既有配对的 evidence 增加了 `sw_wire_route.identity_source` 与 `no_wire_handle` 两个键（无导线句柄的既有记录）。状态、取值、rationale 不变。
6. 覆盖率为“配对级”：每个新配对消耗一个端子端口，同值（识别为 consumed）。严格覆盖增量 = 新增配对数（4802）。

## 9. 文件与复现

- `README.md`（本文件）
- `judgements.json`、`samples.json`（第一批）；`judgements_sample2.json`、`samples_sample2.json`（第二批）
- `png/`：30 张代表图（S001–S110 与 T 批中的代表例）。完整渲染在 `.tmp/loop_pin1_render_s1/`、`.tmp/loop_pin1_render_s2/`。
- `cov_full.json`、`cov10.json`：覆盖率摘要（`tools/cov_summary.py`）。
- `cmp_full_summary.json`、`cmp10_round17_vs_head_summary.json`、`cmp10_head_vs_pin1_summary.json`：`LOGGEN-2/tools/compare_loggen2.py` 输出。
- `bare_digit_legacy_list.json`：裸数字旧值清单（第 7 节）。
- `tools/`：`01_pool.py`（候选池，含身份的物理引脚计数）、`02_render.py`（渲染）、`03_sample.py`（分层抽样）、`cov_summary.py`（覆盖率）。
- 单测：`tests/unit/test_superworks_pin_admission.py`。
- 临时目录：`.tmp/loop_pin1_src`（快照）、`.tmp/loop_pin1_head_src`（HEAD 快照）、`.tmp/loop_pin1` / `.tmp/loop_pin1_full` / `.tmp/loop_pin1_head10`（回放输出）、`.tmp/superworks_round17_full`（基线）。
