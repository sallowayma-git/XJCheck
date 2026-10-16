# P2-BACKPLATE 实施记录（修订二）：背板虚拟端子表的 SW 佐证、J 类取代与装置前缀修正

> 最新状态（2026-10-16）：第 14 节记录 DXF 可见性后续修复。此前 §6 关于 p057 的 95 条仍未修正，是当时的阶段结论，现已由可见性证据解决；p067 的 42 条连带变化也已逐张截图复核。

分支 `superworks-loop`。§0–§13 是此前修订的实施快照；本轮可见性修复及最新验证见 §14。未改 V2 模块与 `symbol_port_proposal.py`，未加 PDF / OCR，未删除 V1 代码，未按项目、句柄或值特判。

## 0. 结论

1. **同页行号冲突（32 条，32/32 为 V1 读错）改为 J 类取代，不再报 issue。** V1 配对置为 `discard`，台账新增类别 `J`（背板行号误读，被同页 SW 配对取代），evidence 记 `superseded_by` / `superseded_by_all` / `supersession_category='J'` 与冲突详情（SW 身份、SW 行、V1 行）。规则 `R-BACKPLATE-SW-ROW-CONFLICT` 已删除。
2. **装置前缀修正（`table_extractor.py`，通用规则）。** 页上"`<装置> REAR WIRING`"标题优先于模板装置字段，但仅当两者装置核心（去掉分区前缀与大写后缀）不同时替换；一致时保留模板原写法。离线评估：278 条装置前缀候选中 **183 条** 变为与 SW 一致（p067、p072 全部）；**原本一致的 3,670 条没有被改坏（0 条）**；另有 1,906 条原本无装置标签的背板配对获得与 SW 一致的复合装置名。
3. **p057 sheet 09 的 10 条“无法判断”放大复核后结论：V1 错**（装置前缀）。标题块可见的装置名是 **7n**（黄色字，位于型号 `ZYQ-820E-02` 之上）；V1 的 `1-1n` 来自同一位置的一组重叠 MARK 层模板字段（`1-1n`、`1n`、`25n`、`WXH-822A-P` 等），不可见。这 95 条装置前缀候选仍保留为候选，未被规则修正（语料内没有通用判据可在层叠字中选出可见者）。
4. **集成测试回退已修。** `table_extractor._build_three_column_mappings` 的数值单元格规则改为按**去重后的不同数值**计数；同值重复文字计一个，端口号阵列（不同数值）仍跳过。B-1 删除的假 table pass（p055 S0012、p071 S0008/S0009）在新回放中仍不存在（`numeric_three_column` 映射为 0）。
5. **测试：** `tests/` 全量 pytest：**2170 passed, 1 skipped**（含 integration）。
6. **issues：** 10 项目回放 13 个项目中 issues 逐条相同。**全量 77 项目 issues 为 40 → 38（不是 40）**：少的 2 条是 `R-CROSS-PAGE-CONFLICT`（p065 `NCK305-1@c0`、p066 `NCK305-5@c0`），原因是 V1 非复合名在两页上重名；装置前缀修正后两行分别为 `1n901 ↔ 1C1D1` 与 `1n1101 ↔ 1C17D1`（p065），`1n905 ↔ 1C2D1` 与 `1n1105 ↔ 1C18D1`（p066），与同页 SW pass 配对完全一致，SW 也证实终端不同。判定为误报消失，不是真实问题被隐藏。需主线程确认是否接受 38。

## 1. 数据口径与比较方法

- 基线：第二十四轮全量回放 `.tmp/superworks_round24_full`（与当前 HEAD 源码一致）。
- 10 项目回放（`.tmp/loop_p2bp`，快照 `.tmp/loop_p2bp_src`）：要求的 10 个项目（p002、p007、p023、p039、p050、p057、p058、p063、p072、p076）另加 p055、p071（B-1 假 table pass 复核）与 p067（装置前缀）共 13 个。
- 全量回放（`.tmp/superworks_round25_full`，快照 `.planning/superworks-adapter/round25_full_src`）。
- **比较注意：** pair_id 为顺序编号，p064 因新增 119 个配对，其后 ID 发生整体位移，按 pair_id 对齐无效。因此 pair 的逐类计数对 p064 之外的项目按 pair_id 对齐；p064 的新增与消失改用“台账 twin 核验”（每条被取代的 pass 都必须有同页或同项目的存活 SW pass 配对）与内容比对。
- issue 对比按 `(rule_id, message, sheet_id, filename)` 多重集合。

## 2. 改动清单

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/audit/superworks_extractor.py` | `corroborate_backplate_virtual_pairs`（佐证与候选，不变）；`supersede_backplate_row_misreads`（J 类取代，替换原 review 降级）；删除 `build_backplate_row_conflict_issues` 与其在 `build_superworks_issues` 中的调用。 |
| `src/dwg_audit/pipeline.py` | 调用顺序：`corroborate_backplate_virtual_pairs` → `supersede_backplate_row_misreads`（传入并更新 `superworks_supersession` 台账）。 |
| `src/dwg_audit/audit/table_extractor.py` | (a) 数值三列规则：按去重后的不同数值计数；(b) `_resolve_backplate_device_instance` 新增页标题“REAR WIRING”装置标题优先级（见 §4）；(c) `_backplate_device_core`。`_build_backplate_virtual_mappings` 将整页文字传入装置解析。 |
| `src/dwg_audit/domain/models.py` | `ProjectArtifacts.sw_backplate_contradictions` 字段。 |
| `src/dwg_audit/report/superworks_artifacts.py` | 写出 `sw_backplate_contradictions.parquet`（含 `action` 列）。 |
| `tests/unit/test_superworks_backplate_corroboration.py` | 24 条单元测试（佐证、候选、J 取代、无 issue、标题优先级、模板一致保留）。 |
| `.planning/superworks-adapter/loop/LEGACY-CENSUS/README.md` | 末尾“更正”一节（修订前版本；本次未改动其数字，见 §8）。 |

## 3. 佐证规则（方案 A，不变）

- 同项目 SW pass 配对共享外部端子 R（SW 端身份可解析为 `<dev><列><行:2>` 或 `<dev><字母><行:2>`），行号一致、装置规范化一致，则写 `evidence.sw_backplate_corroboration`，状态不变。
- 装置规范化：去掉尾部大写字母；仅一侧带 `\d+-` 分区前缀时忽略（`1-1n` ≈ `1n`），两侧都带时须相同。
- 无装置的 V1 配对不判断（`composite_device_instance` 为空）。

## 4. 装置前缀修正（`table_extractor.py`）

**优先级依据。** 当前取值顺序：(1) 表格块所在页的标题 / 文件名（`REAR WIRING` 或 `背板` 附近的装置实例）；(2) **本次新增**：整页唯一的“`<装置> REAR WIRING`”标题文字；(3) 原有模板装置字段（自由文字中的 `\d+-\d+[A-Za-z]` 形式，取最上方者）。

依据：页标题是图面印刷的标题栏文字，模板装置字段是块属性，在若干页上与标题冲突。冲突样本（离线核对）：p067 第 14 页标题 `4n REAR WIRING`，模板字段 `1-8n`；p072 第 19 页标题 `4n REAR WIRING 2`，模板字段 `1-1n`；两页的 SW 身份装置名均为 `4n`。标题优先且与 SW 身份一致。

**替换条件（修订后）。** 标题装置替换模板装置，仅当两者装置核心不同（`_backplate_device_core`：去掉 `^\d+-` 分区前缀与尾部大写字母；`1-8n` 与 `8n` 视为同一核心）。修订前版本无此条件，会把 200 条已与 SW 一致的 `1-8n` 写成 `8n`（只改字符串，身份仍一致），修订后已去除。

## 5. 离线评估（修订后规则，第二十四轮数据）

脚本：`tools/prefix_offline_eval.py`。对标题装置页（165 页）上的背板 pass 配对，对照同一终端 R 且行号一致的 SW pass 身份。

| 类别（当前装置 → 修正后） | 条数 | 说明 |
|---|---:|---|
| 一致 → 一致（字符串不变） | 3,670 | 保留，**0 条被改坏** |
| 不一致 → 一致（装置字符串改变） | 183 | p067 84 + p072 99；即 278 条装置前缀候选中的 183 条 |
| 无装置 → 一致（新增复合装置名） | 1,906 | 原本无复合装置名，修正后与 SW 一致 |
| 无同行 SW 对端（不变） | 127 | 装置不变，0 条改变 |
| 一致 → 不一致 / 不一致 → 不一致 | 0 / 0 | — |

278 条候选中：183 条变为与 SW 一致；95 条（p057 第 09 页）未变（见 §6）。

## 6. p057 sheet 09 的 10 条“无法判断”：放大复核结论

图：`png/P2BP_p057_review.png`。三幅：A 模板字段处（空白，无可见文字）；B 标题块（仅有 `REAR WIRING`，无装置名）；C 行 02 的 SW 身份点（外部标签 `7QD15, 7n302`）。

**关键发现。** 标题块中存在黄色可见装置名 `7n`（`T1292`，位于型号 `ZYQ-820E-02` 之上）。同一位置的 MARK 层有一组重叠文字（`1-1n`、`1n`、`25n`、`1`、`WXH-822A-P`、`WYD-811`、`WXH-821A-P` 等，高度 3 与不可见的高度 1 混杂），模板字段选中的 `1-1n` 不是可见的那一个。全项目 `1-1n` 仅出现这一次，而 `7n` 出现 153 次。

**结论：V1 错（装置前缀）。** SW 身份 `7n` 与可见装置名一致。修正方式未纳入规则：要从层叠文字中选出“可见”者需要额外的可见性判据，语料内没有通用依据（其余重叠组同样不可判定）。因此 95 条保留为候选（`device_prefix_differs`），并在 §8 列为后续项。

## 7. 同页行号冲突：J 类取代（32 条，全部 V1 错）

判定：32 / 32 为 V1 读错（14 条抽样 + 18 条普查补齐）。机制：22 条为 1-7n / 2-7n 表（V1 取中间序号格 `2`，行号 `32` 在右侧）；8 条为 PMU 采集器成对端子（V1 取左侧序号）；2 条为 p058 撇号规范化（`1PT-u3'` 与 `1PT-u3` 被合并）。

处理：J 类取代（`discard`）。台账 `superworks_supersession.parquet` 中 `J` 类共 32 条，每条 `old_pair` 为原 V1 配对，`new_pairs` 为同页 SW 配对；evidence 记 `superseded_by`、`superseded_by_all`、`supersession_category='J'`、`backplate_row_misread`（SW 身份、SW 行、V1 行、类型）。**不报 issue。**

选择取代而非修正值：正确连接已由同页 SW pass 配对表示；修正 V1 值需要改写 V1 身份生成，超出范围。

## 8. 回放对比

### 8.1 10 项目（13 个项目）回放

| 项目 | 佐证 | 候选 | pass→discard（J） | pass→discard（I，身份修正后） | 身份修正仍 pass | issues 前→后 |
|---|---:|---:|---:|---:|---:|---|
| p002 | 158 | 0 | 0 | 0 | 0 | 0 → 0 |
| p007 | 8 | 0 | 0 | 166 | 8 | 0 → 0 |
| p023 | 28 | 2 | 2 | 0 | 0 | 1 → 1 |
| p039 | 308 | 0 | 0 | 0 | 0 | 2 → 2 |
| p050 | 316 | 0 | 0 | 0 | 0 | 1 → 1 |
| p055 | 0 | 0 | 0 | 0 | 0 | 0 → 0 |
| p057 | 0 | 95 | 0 | 0 | 0 | 0 → 0 |
| p058 | 136 | 2 | 2 | 0 | 0 | 0 → 0 |
| p063 | 120 | 4 | 4 | 0 | 0 | 0 → 0 |
| p067 | 42 | 0 | 0 | 84 | 0 | 2 → 2 |
| p071 | 0 | 0 | 0 | 0 | 0 | 3 → 3 |
| p072 | 94 | 0 | 0 | 84 | 15 | 4 → 4 |
| p076 | 131 | 0 | 0 | 0 | 0 | 0 → 0 |

13 个项目的 issues 逐条相同（rule + message + sheet）。pass→discard 合计：J 8，I 334（均为与同页 SW pass 存活配对等值的重复）。

### 8.2 全量 77 项目

| 指标 | round24 | round25 |
|---|---:|---:|
| 配对总数 | 178,713 | 178,832（+119，全部在 p064） |
| 背板虚拟表 pass | 6,238 | 4,254（−1,984 = −1,989 取代 + 5 新增） |
| 佐证 `sw_backplate_corroboration` | — | 4,047 |
| 候选 parquet 行 | — | 127（95 装置前缀未变 + 32 J 已取代） |
| J 类取代 | — | 32 |
| issue 总数 | 40 | 38 |

**配对变化分类（全量）。** 身份修正两行与 I 类数量按 pair_id 对齐统计，p064 的 ID 位移使其中少量归类可能错位；每条 pass→discard 的 twin 核验与配对总数不受影响。

| 类别 | 条数 | 说明 |
|---|---:|---|
| J 类取代 | 32 | 同页 SW pass 配对取代（台账 J） |
| I 类（身份修正后与 SW 等值重复） | 1,957 | 原 `legacy_pair_duplicates_same_sheet_sw_pass` 规则；每条都有存活的 SW pass 配对 twin（全部核验通过） |
| 身份修正，仍 pass | 132 | 无装置 → 复合装置名或前缀替换 |
| 身份修正，已 discard | 70 | 已是 discard，仅文字变化 |
| 新增 pass（p064） | 5 | 复合网格新增；每条都与同页 SW pass 配对同端子（去掉 `@ ` 后）一致，属重复 |
| 新增 discard（p064） | 114 | 同上类型的 I 类重复 |

所有 1,989 条 pass→discard 都有存活的 SW pass twin（台账核验），**没有连接从 pass 集合中丢失**。

**issue 逐条对比（全量）：** 既有 40 条中 38 条保留；移除 2 条 `R-CROSS-PAGE-CONFLICT`（p065 `NCK305-1@c0`、p066 `NCK305-5@c0`），原因见 §0 第 6 条；新增 0 条。

## 9. 测试

- `tests/unit/test_superworks_backplate_corroboration.py`：24 条通过（新增 J 取代、无 issue、标题优先、模板一致保留、标题与模板冲突、多个标题忽略等）。
- 全量 `pytest tests`：**2170 passed, 1 skipped**（修订前 2163 通过 + 1 个回退失败，现已修复）。

## 10. 新图纸泛化

- **装置前缀。** 规则依赖页面上印刷的“`<装置> REAR WIRING`”标题，而非某个项目的名字；新图纸只要印有这样的标题即可使用。页无此标题时保持原行为。
- **J 类。** 依赖同页 SW pass 身份的行号可信。若 SW 身份本身错误，J 类会取代一条正确的 V1 配对，其后果是该连接只剩 SW 那一条；台账与 evidence 保留了可追溯信息。
- **数值三列。** 同值重复文字计一个；不同数值仍跳过，因此端口阵列仍不会变成映射。
- **可见装置标签。** 模板字段与可见标题不一致的情形（p057）尚无通用判据，见 §11。

## 11. 遗留风险与后续

1. **p057 层叠装置标签（95 条候选未修正）。** 需要“可见文字”的通用判据后再修。
2. **撇号规范化。** `_normalize_backplate_endpoint` 丢掉了 `'`，使 `1PT-u3'` 与 `1PT-u3` 合并（2 例 J 类）。影响范围未评估，需单独处理。
3. **残留的无装置配对。** 装置前缀修正后，p064、p065、p066 等项目仍有配对无复合装置名（其中多数已被 I 类取代）。
4. **I 规则对 `@ ` 前缀的漏判。** p064 中 `5n1305 ↔ TD2` 与同页 SW pass `5n1305 ↔ @ TD2` 等值，但 V1 配对未被 I 类取代（既有规则的限制），本次未改。
5. **issue 38 而非 40。** 2 条 `R-CROSS-PAGE-CONFLICT` 消失，由主线程确认是否接受。
6. **LEGACY-CENSUS 更正。** 已在第二十四轮基线的数字上更正（见该文件末尾）；本次 J 类与装置修正后，背板 pass 集合又减少 1,984，相应数字需随全量回放更新，本次未重写该文件的表。
7. **基线非确定性。** 同一快照重跑时，少量非背板配对的 `bbox` 浮点值不同（如 `PW0307`、`PW0243`、`PW0242`），与本次改动无关。

## 12. 文件与复现

- 判定数据：`loop/P2-BACKPLATE/judgements.json`（62 例，全部 V1 错；含机制）。
- 工具（`loop/P2-BACKPLATE/tools/`）：
  - `offline_candidates.py`：离线候选与佐证（回放 pairs）。
  - `sample_candidates.py`：分层抽样与普查（生成 cases.json）。
  - `render_judge.py`：DXF 判定图（`ABC` 三幅或 `AB` 两幅，每图行数可调）。
  - `render_p057_review.py`：p057 sheet 09 放大复核图。
  - `device_sheet_labels.py`：页上装置类文字与模板位置文字统计。
  - `prefix_offline_eval.py`：装置前缀修正的离线评估（标题页）。
  - `compare_replay.py`：两次回放的 issue 与状态比较（pair 按 ID，p064 见 §1）。
  - `pair_change_classes.py`：配对变化分类（pair 按 ID）。
- 图片（本次新增，`png/`，共 25 张）：`P2BP_sample_01_02.png` … `P2BP_sample_43_44.png`（22 张，抽样 44 例，ABC 三幅）；`P2BP_census_102_118.png`、`P2BP_census_119_132.png`（2 张，普查补齐 18 例，AB 两幅）；`P2BP_p057_review.png`（1 张，p057 放大复核）。原有 `P2BP_judge_1..3.png` 未改动。
- 回放输出：`.tmp/loop_p2bp`（13 项目）、`.tmp/superworks_round25_full`（全量）；比较 JSON：`.tmp/p2bp/cmp13d.json`、`.tmp/p2bp/pairchg13d.json`、`.tmp/p2bp/cmp_full2.json`、`.tmp/p2bp/pairchg_full.json`。

## 13. 判定表（62 例）

字段：编号（抽样 1–44；普查补充为原抽样编号或 101–132 的普查编号）、集合（sample / census）、V1 与 SW 的行或装置、判定、机制。

| 编号 | 集合 | 类别 | 项目 | 配对 | 页 | V1 | SW | 判定 | 机制 |
|---|---|---|---|---|---|---|---|---|---|
| 15 | sample | 装置前缀差异 | p057 | P0030 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 16 | sample | 装置前缀差异 | p067 | P0095 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 17 | sample | 装置前缀差异 | p072 | P0143 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 18 | sample | 装置前缀差异 | p057 | P0042 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 19 | sample | 装置前缀差异 | p067 | P0087 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 20 | sample | 装置前缀差异 | p072 | P0114 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 21 | sample | 装置前缀差异 | p057 | P0089 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 22 | sample | 装置前缀差异 | p067 | P0094 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 23 | sample | 装置前缀差异 | p072 | P0164 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 24 | sample | 装置前缀差异 | p057 | P0023 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 25 | sample | 装置前缀差异 | p067 | P0096 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 26 | sample | 装置前缀差异 | p072 | P0103 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 27 | sample | 装置前缀差异 | p057 | P0057 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 28 | sample | 装置前缀差异 | p067 | P0122 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 29 | sample | 装置前缀差异 | p072 | P0095 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 30 | sample | 装置前缀差异 | p057 | P0027 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 31 | sample | 装置前缀差异 | p067 | P0106 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 32 | sample | 装置前缀差异 | p072 | P0158 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 33 | sample | 装置前缀差异 | p057 | P0058 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 34 | sample | 装置前缀差异 | p067 | P0071 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 35 | sample | 装置前缀差异 | p072 | P0153 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 36 | sample | 装置前缀差异 | p057 | P0090 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 37 | sample | 装置前缀差异 | p067 | P0051 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 38 | sample | 装置前缀差异 | p072 | P0106 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 39 | sample | 装置前缀差异 | p057 | P0026 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 40 | sample | 装置前缀差异 | p067 | P0123 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 41 | sample | 装置前缀差异 | p072 | P0127 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 42 | sample | 装置前缀差异 | p057 | P0045 | 09 | dev 1-1n | dev 7n | V1 错 | 装置前缀：可见标题块写 7n，V1 取的 1-1n 为重叠 MARK 层模板字段之一 |
| 43 | sample | 装置前缀差异 | p067 | P0078 | 14 | dev 1-8n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 44 | sample | 装置前缀差异 | p072 | P0126 | 19 | dev 1-1n | dev 4n | V1 错 | 装置前缀：V1 取模板字段（1-8n / 1-1n），页标题为 4n REAR WIRING |
| 1 | sample | 同页行号冲突 | p031 | P0131 | 28 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 2 | sample | 同页行号冲突 | p024 | P0174 | 16 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 3 | sample | 同页行号冲突 | p063 | P0193 | 14 | row 03 | row 04 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |
| 4 | sample | 同页行号冲突 | p033 | P0235 | 24 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 5 | sample | 同页行号冲突 | p030 | P0117 | 25 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 6 | sample | 同页行号冲突 | p058 | P0073 | 14 | row 18 | row 17 | V1 错 | V1 规范化丢掉撇号：1PT-u3' 与 1PT-u3 被合并 |
| 7 | sample | 同页行号冲突 | p029 | P0137 | 28 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 8 | sample | 同页行号冲突 | p034 | P0253 | 24 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 9 | sample | 同页行号冲突 | p028 | P0127 | 22 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 10 | sample | 同页行号冲突 | p074 | P0191 | 14 | row 01 | row 02 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |
| 11 | sample | 同页行号冲突 | p023 | P0117 | 15 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 12 | sample | 同页行号冲突 | p022 | P0125 | 15 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 13 | sample | 同页行号冲突 | p032 | P0243 | 24 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 14 | sample | 同页行号冲突 | p031 | P0143 | 28 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 102 | census | 同页行号冲突 | p022 | P0137 | 15 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 103 | census | 同页行号冲突 | p023 | P0105 | 15 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 105 | census | 同页行号冲突 | p024 | P0131 | 15 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 106 | census | 同页行号冲突 | p024 | P0143 | 15 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 107 | census | 同页行号冲突 | p024 | P0162 | 16 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 110 | census | 同页行号冲突 | p028 | P0139 | 22 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 111 | census | 同页行号冲突 | p029 | P0125 | 28 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 113 | census | 同页行号冲突 | p030 | P0105 | 25 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 118 | census | 同页行号冲突 | p032 | P0255 | 24 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 119 | census | 同页行号冲突 | p033 | P0223 | 24 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 122 | census | 同页行号冲突 | p034 | P0265 | 24 | row 02 | row 32 | V1 错 | V1 取了 R 同行的中间序号格（插件序号 02），行号 32 在右侧 |
| 124 | census | 同页行号冲突 | p058 | P0077 | 14 | row 24 | row 23 | V1 错 | V1 规范化丢掉撇号：1PT-u3' 与 1PT-u3 被合并 |
| 125 | census | 同页行号冲突 | p063 | P0061 | 13 | row 01 | row 02 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |
| 126 | census | 同页行号冲突 | p063 | P0063 | 13 | row 03 | row 04 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |
| 127 | census | 同页行号冲突 | p063 | P0191 | 14 | row 01 | row 02 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |
| 129 | census | 同页行号冲突 | p074 | P0061 | 13 | row 01 | row 02 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |
| 130 | census | 同页行号冲突 | p074 | P0063 | 13 | row 03 | row 04 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |
| 132 | census | 同页行号冲突 | p074 | P0193 | 14 | row 03 | row 04 | V1 错 | 成对端子左侧序号（01/03）被取，R 挂在右侧（02/04） |

## 14. 2026-10-16 DXF 可见性后续修复

### 根因与通用判据

上一修订依赖图面的 REAR WIRING 装置文字和模板字段，但没有记录 DXF 实体的实际显示状态。p057 的模板提取把 DXF 中标记为不可见的 MARK 文字 `1-1n` 当成装置身份。现在抽取端记录 `TextItem.dxf_visible`，合并实体隐藏标志、ATTRIB/ATTDEF 标志、图层关闭/冻结状态和 INSERT 祖先可见性；缺少该字段的旧数据保留为 unknown。

装置解析只排除有明确隐藏证据的文字。没有复合模板字段时，新增的保守回退要求同页存在可见的 `REAR WIRING` 标题、唯一的可见纯装置号，以及唯一相邻的可见型号文字（距离不超过较大字高的 4 倍）。图面证据不唯一或可见性未知时不推断。已有可见复合模板字段仍保持优先。规则不依赖项目、文件名、句柄、装置值或块名；未改 V2 或 `symbol_port_proposal.py`。

### 逐页与逐例结果

| 页 | 旧错误映射 | 截图核验 | 单页重跑 |
|---|---:|---:|---|
| p057 F0009/S0009 | 95 条 `1-1n` 前缀 | 95/95 旧前缀判错；可见 MARK `7n` 位于型号 `ZYQ-820E-02` 上方 | 95/95 改为 `7n`，均因与同页 SW 配对重复而 discard；0 个 issue，0 条背板矛盾 |
| p067 F0013/S0013 | 42 条 `1-8n` 前缀 | 独立逐图复核 42/42；每例表格行、外部端子、可见 MARK `8n` 与可见 `8n REAR WIRING` 均支持新前缀 | 42/42 改为 `8n`；37 条重复映射 discard，5 条仍 pass；0 个 issue，0 条背板矛盾 |

两个受影响页共 137 个旧前缀全部错误；重算后 137/137 前缀与可见页面身份一致。p057 的 95 条及 p067 的 37 条不再占 pass 集合，因为已有同页 SW 配对；p067 另 5 条仍是 pass 且逐例正确。p067 证据：`png/P2BP_visibility_p067_P0001.png` 展示 discard 行，`png/P2BP_visibility_p067_P0032.png` 展示仍为 pass 的 TD1 行；p057 证据见 `png/P2BP_visibility_p057_P0001.png`。全量 42 张 p067 逐例截图与双组独立判定台账在 `.tmp/precision_loop_20261015/p067_visibility_screenshots/`。

### 回放、问题与覆盖

- 全量 `python -m pytest tests -q`：**2240 passed, 1 skipped**（含 integration）。
- 单页 p057 与 p067：上述映射结果均与完整回放中的同页结果一致；无新增 issue。
- 10 项目回放（含 p057、p067）：issue 新增/移除均为 0。状态变化只有 p057 95 条 `pass→discard` 和 p067 37 条 `pass→discard`；其余项目无配对变化。
- 77 项目回放：`run.json` 为 `COMPLETE`，77 项目、0 失败；测试快照与 10 项目回放的 111 个 Python 文件哈希一致。issue 新增/移除均为 0；配对状态变化仅 p057 与 p067 两页。所有项目页级覆盖行和覆盖总量相同。
- 覆盖台账中的 assignment-kind 计数有重分流：重复项从 `structured_mapping_endpoint` / `semantic_evidence` 分类转为 `covered_discard`；页级覆盖行及各项目覆盖总量不变。这是重复配对状态改变带来的记账类别变化，不是覆盖丢失。
- 比较明细：10 项目 `.tmp/precision_loop_20261015/p067_slice_10_comparison.json`；77 项目 `.tmp/precision_loop_20261015/p057_slice_77_comparison.json`；p057、p067 单页汇总分别在对应的 `p057_single_current_visibility_with_prj/summary.json`、`p067_single_visibility_with_prj/summary.json`。

实现与回归测试：`domain.models.TextItem` 和可见性辅助函数；`cad_extract._entity_visibility` 及 INSERT 可见性继承；`table_extractor._resolve_backplate_device_instance`、`_visible_standalone_backplate_device`。新增测试位于 `test_superworks_loop_invisible_text.py` 与 `test_superworks_backplate_corroboration.py`。截图生成器和单页重跑脚本见 `tools/p067_visibility_screenshots.py`、`tools/p067_single_page_replay.py`；完整逐例材料保存在 `.tmp`，规划目录只保留三张代表图。

**限制：** 当前可见性口径涵盖实体隐藏位、属性标志、图层开关/冻结和 INSERT 祖先；其他依赖 CAD 视口或打印配置的显示条件未建模。unknown 可见性不会触发新的纯装置号回退。
