# LOGGEN：从图中直接读取导线去向（第一阶段，只读证据与评估）

范围：只读诊断。新增 `sw_wire_routes.parquet`，不参与 pairs、issues 或任何抽取决策。
数据：`.tmp/loop_loggen`（改动版）与 `.tmp/loop_loggen_base`（基线，与改动版仅差 pipeline 挂接与新模块）上的 10 个项目回放。
未修改：`cad_extract.py`、`candidates.py`、`component_diagrams.py`、`rules.py`、`superworks_semantics.py`、V2 模块、`symbol_port_proposal.py`。未做 git 提交。

## 0. 结论摘要

1. **可以直接读到导线两端去向。** 10 个项目共 8902 条去向记录，两端都解析到现有 SW 端口身份的占 67.2%；端点级解析率 92.3%。
2. **零影响已证明。** 同一代码基线下，有挂接与无挂接的回放，所有 pairs、issues、审计报告、SW 各表逐项相等。唯一差异是 `source_files.dxf_path` 中的输出目录名。
3. **与生产配对高度一致。** 7199 个生产配对侧（7017 精确 + 182 前缀等价）与记录身份一致；冲突只有 8 个，全部是 review 状态的旧版数字候选，其 SW 证据身份与记录一致（8/8），看图的 2 例确认记录正确。
4. **补充（记录两端都解析、生产无单一配对覆盖）3304 条**，其中 **1278 条是自环**（两端身份相同，生产的 F1 规则有意不出配对，不计增量）；**真正的增量候选 2026 条**。截图 10 例中 9 例在图上为真实或很可能的连线（其中 2 例为自环），1 例不确定。
5. **严格口径潜在提升：+471 个端口，约 +5.4 个百分点**（10 项目，64.4% → 69.8% 上界）。
6. **代价：** 为拿到 XRECORD，本阶段对每页多读了一次 DXF（禁止改动 `cad_extract.py` 导致无法复用已打开的文档），耗时约 +8.6%（18.4 s / 213.3 s）。第二阶段应在 `cad_extract.py` 的已打开文档处挂接，可去掉这部分开销。

## 1. 数据结构

### 1.1 解析来源（两种记录）

| 来源 | 载体 | 字段 | 说明 |
|---|---|---|---|
| `LOGGEN` | 根字典 `LD_SYMB2LOGGEN_DICTIONARY` 下的 XRECORD（每条一根导线） | `CONNECTLINEHANDLE`（导线 LINE 句柄）、`PART2_n`（第 n 端）、`LINENO`（一端的线号位置）、`LINESTYLE` | 每端 `||设备||引脚||序号||侧别||符号块||端子句柄||类别||...` |
| `PCL` | 元件 INSERT 扩展字典中的 `LD_PARTCONNECTLINE`（每个逻辑端号一组，10 个字段） | `逻辑端号`、`直线句柄`（导线）、`线号`（跨页标记 `未定义<句柄>:<端口>_<页号> <页名>`）、`对端元件`（`设备||||引脚||类别`）、`导线类型` | 本端为元件自身引脚；远端由跨页句柄或对端文本给出 |

跨页句柄的格式与 `superworks_semantics.py` 中 `cross_page_refs` 使用的 `未定义H:P_页` 相同。`cross_page_refs` 只存在于 `SwStripRow`，并且 `superworks_semantics.py` 不可改，因此本阶段在 `superworks_loggen.py` 中独立解析同一格式（未复用该结构）。

### 1.2 输出表 `findings/sw_wire_routes.parquet`（每条记录一行）

| 列 | 含义 |
|---|---|
| `record_id` | `SWWR:<file_id>:<LOGGEN|PCL>:<记录键>` |
| `source_kind`, `source_handle`, `owner_handle`, `logical_pin` | 来源类型；LOGGEN 为 XRECORD 句柄；PCL 为元件句柄与逻辑端号 |
| `wire_handle`, `wire_entity_kind`, `linestyle` | 导线句柄（LINE 时为 `LINE`）与导线类型文本 |
| `end_count`, `resolved_end_count`, `both_ends_resolved` | 端数（保留全部端，≥3 端不截断）、已解析端数、两端是否全部解析 |
| `lineno_raw`, `lineno_end_index` | LOGGEN 的 LINENO 原文及其指向的端序号（未匹配为空） |
| `ends_json` | 端列表（JSON），每端字段见 1.3 |
| `reason_codes_json` | 记录级与端级原因码 |

同时写出 `findings/sw_wire_routes_stats.json`（页数、页失败、读取耗时、总耗时）。

### 1.3 端字段（`ends_json` 中的每个对象）

`role`（`PART2_n` / `LOCAL` / `FAR`）、`end_index`、`file_id`、`terminal_handle`、`port_number`、`device`、`category`、`identity`、`identity_source`（`sw_port` / `text`）、`status`、`port_ids`，以及 FAR 端的 `far_source`（`cross_page` / `text_only`）、`xpage_page_name`、`far_text_identity`。

示例（p003，`SWWR:F0004:LOGGEN:LD_SYMB2LOGGEN_1`，导线 `1A945`，两端均解析）：
- PART2_1：端子 `1A933` 端口 2，设备 8QD，身份 `8QD1`（sw_port）
- PART2_2：装置端子 `1A93F` 端口 1，设备 8n，身份 `8n112`（sw_port）
- `LINENO=未定义1A933:2`，即 LINENO 指向第 0 端。

示例（p076，PCL，逻辑端号 101，本端 `2282C` 端口 101，身份 `8n101`；远端跨页 `3C82` 端口 1，身份 `8n801`，对端文本 `8YD2`）。

### 1.4 身份解析规则

- 端 = (文件, 实体句柄, 端口号)。实体必须是页内 INSERT；端口号为 SW 端口的 `port_number`（LOGGEN 的 pin 与之相等，已验证 99/105 端在首页直接匹配）。
- 身份取自 `superworks` 的 SW 端口 `endpoint_identity`（与生产 pairs 使用的身份相同），包括元件内部端口（`part_instances.ports`，身份形如 `1FA-13`）。
- 多个端口给出不同身份：`ambiguous_identity`；端口存在但身份为空：`no_identity`（附原因码）；实体不是 SW 符号/元件：`insert_not_sw`；端口号在已知实体中不存在：`port_number_absent`。
- 跨页（PCL 线号）：在项目内查找具有该句柄 SW 端口的文件；多文件时按页号（`sheet_no`）收窄；仍不唯一则 `xpage_ambiguous`。
- PCL 对端文本身份：`对端元件` 字段的设备+引脚（端子类 `设备+引脚`，其余 `设备-引脚`），标记 `identity_source=text`。装置端子的文本约定未验证（见第 6 节）。

## 2. 解析率（10 项目，`.tmp/loop_loggen`）

| 类型 | 记录数 | 两端均解析 | 比例 | 备注 |
|---|---|---|---|---|
| LOGGEN | 5643 | 2742 | 48.6% | 2 端 3527，1 端 1934（另一端不在本页 LOGGEN 中），≥3 端 182（保留全部端） |
| PCL | 3259 | 3238 | 99.4% | 均为 2 端：本端 + 远端 |
| 合计 | 8902 | 5980 | 67.2% | |

端级（16221 端）：解析 14964（92.3%）。

| 来源 · 角色 | 端数 | 解析 | 未解析原因 |
|---|---|---|---|
| LOGGEN PART2 | 9703 | 8471（87.3%） | `insert_not_sw` 983（多为未被 SW 识别的元件引脚）；`no_identity` 249（端子 17、装置端子 182、接地 69、内部元件 2） |
| PCL 本端 LOCAL | 3259 | 3255（99.9%） | `no_identity` 2；`port_number_absent` 2 |
| PCL 远端 FAR | 3259 | 3238（99.4%） | 跨页解析 2661（81.7%）；文本回退 577（跨页失败或无跨页标记）；`no_identity` 19；`no_far_end` 2 |

记录级原因：`wire_handle_missing` 401（PCL 直线句柄为空）；`logical_pin_empty` 2。

LINENO 核对：5560 条 LOGGEN 记录的 LINENO 与其某一端的（句柄, 端口）一致，83 条不一致。LINENO 是“带线号标注的那一端”，不是固定的“对端”（与 ATTR-CENSUS 4.1 的描述不同，以本次核对为准）。

## 3. 一致 / 冲突 / 补充

统计口径：
- 侧 = 生产配对的一侧（SW 证据中的 `symbol_handle`、`port_number` 与记录端的（文件, 句柄, 端口）相等）。仅统计非 discard 配对（pass + review）。
- 等价规则：沿用 `superworks_extractor` 的 `_key`、`_destination_keys`（范围端子）、`endpoint_aliases`（别名）；前缀等价为“记录身份以配对侧值结尾，且前缀含字母（如 `1n717` 对 `717`）”。
- 冲突 = 侧值与记录身份不等价。

### 3.1 侧级一致与冲突

| 结果 | 端子 | 装置端子 | 线圈 | 接插件 | 合计 |
|---|---|---|---|---|---|
| 一致（精确） | 4402 | 2577 | 6 | 32 | 7017 |
| 一致（前缀等价） | - | 182 | - | - | 182 |
| **冲突** | **8** | - | - | - | **8** |
| 被 discard 配对覆盖（不计入） | 29 | 43 | - | - | 72 |

冲突 8 条的特征（逐条核对）：
- 全部为 `review` 状态、`wire_component_mapping` 类型、侧为端子（`7QD4`、`7QD5`、`7QD6`、`7QD7`、`1-7QD4`、`1-7QD5`、`1-7QD6`、`1-7QD7`）；`pass` 配对中冲突为 0。
- 这些配对左侧缺失（`left_value` 为空，置信度 0.32，理由“missing left candidate”），右侧的侧值是旧版数字候选（如 `702`），而其自身的 SW 证据身份与记录身份**全部相等**（8/8）。

### 3.2 记录级覆盖与补充

| 类别 | 记录数 | 说明 |
|---|---|---|
| 两端均解析，且单一活动配对覆盖两端 | 2676 | 已覆盖 |
| 两端均解析，未被单一活动配对覆盖（补充候选） | 3304 | 下面分两类 |
| 其中：自环（两端身份相同） | 1278 | 生产 F1 规则（`_self_connection_reason`）有意不出配对，不计增量 |
| 其中：非自环，两端都无活动配对 | 1168 | |
| 其中：非自环，一端已有活动配对（在另一导线上） | 858 | 需要端口去重策略（见第 7 节） |

补充记录的 3304 条，其所在导线（同一 SW 导线组）在生产中**都没有任何活动配对**；`one_end_active` 的那一端，其端口的活动配对走的是另一根导线。

非自环补充（2026 条）的端类别分布（端数，单位：端）：

| 端类别 | 端数 |
|---|---|
| 内部元件（元件引脚，身份形如 `1FA-13`） | 2018 |
| 端子 | 1179 |
| 装置端子 | 672 |
| 未分类 | 174 |
| 线圈 / 接插件 / 接地 | 4 / 4 / 3 |

按组合（无活动配对 / 一端已有活动配对）：内部元件-端子 519 / 648；内部元件-装置端子 460 / 206；内部元件-接地 3 / 0；内部元件-未分类 174 / 0；内部元件-线圈 4 / 0；内部元件-接插件 0 / 4；端子-端子 3 / 0；端子-端子-端子 2 / 0；装置端子-装置端子 3 / 0。（完整键见 `.tmp/loop_loggen_eval/aggregate.json`。）

## 4. 截图结论（`png/`）

橙框 = 记录导线；绿 = 端 0；蓝 = 端 1（跨页端画在其目标页的 DXF 上，单独成面板）。

**冲突（8 例；SW 身份核对 8/8，看图 2 例）**
- `conflict_01_p001_F8F3.png`：图上端子旁印着 `7QD5`，导线落在该端；配对侧值 `702` 在该端上不存在。记录正确。
- `conflict_05_p022_17BD8.png`：端子旁印着 `1-7QD4`；配对侧值 `801` 不在该处。记录正确。
- 其余 6 例（`conflict_02/03/04/06/07/08`）未逐张看图，依据为 8/8 的 SW 证据身份与记录一致。
- 结论：冲突全部来自 review 候选的旧数字值，**记录（SW 端口身份）更可信**。

**补充（10 例，分层抽样，全部查看）**

| 图 | 项目 | 类型 | 判断 |
|---|---|---|---|
| supplement_01 | p076 | PCL，`3-21n417` ↔ 页 F0016 端子 `A7B8` | 真实连接（两页标签一致） |
| supplement_02 | p044 | PCL，`2-1n315` ↔ 页 F0010 `26F68` | 真实连接 |
| supplement_03 | p061 | PCL，`3-21n532` ↔ `3-21GD19` | 真实，近端标签部分被裁切，证据较弱 |
| supplement_04 | p061 | PCL，`2-21ZK-3` ↔ `2-21CD1` | 可能真实，近端旁边的标签为 `2-21CD3`，未能确认 |
| supplement_05 | p044 | LOGGEN，`1LD2` 端 4 ↔ `1LD2` 端 3 | 图上真实连线，**两端同一身份（自环）**，不计增量 |
| supplement_06 | p022 | LOGGEN，`1QD7` 端 2 ↔ `1QD7` 端 1 | 图上真实连线，**两端同一身份（自环）**，不计增量 |
| supplement_07 | p022 | PCL，远端为文本标签 `1C3LP8-2` | 真实连线，远端只能文本定位，不是 SW 端口 |
| supplement_08 | p061 | PCL，`1-21QD20` 与页 F0009 同标签 | 真实连接 |
| supplement_09 | p061 | PCL，`4-21WD1` 两页同标签 | 真实连接 |
| supplement_10 | p061 | PCL，远端 `703`（页 F0004） | 可能真实 |

非自环的 8 例中，5 例明确为真实连线（01、02、07、08、09），2 例较可能（03 近端标签被裁切；10 远端标签 703 与近端身份一致），1 例不确定（04：近端旁为 `2-21CD3` 标签，未能确认）。

**严格口径潜在提升（抽 4 例，看了 2 例）**：`strict_potential_01_p050`（端口 `1U1D1` 与导线连接）、`strict_potential_03_p051`（`1-25nPWR1-7` 与导线连接）为真实的导线接触点。其余 2 例未看。

## 5. 严格口径覆盖率的潜在提升

口径同 COV-GAP：eligible = 端子 / 装置端子且有导线接触、标签已解析（取自 `sw_port_coverage.parquet`）；consumed = 非 discard 生产配对中 SW 证据 `port_ids` 命中该端口且侧值与身份相等。

| 项 | 端子 | 装置端子 | 合计 |
|---|---|---|---|
| eligible | 4259 | 4386 | 8645 |
| consumed（当前） | 3469 | 2098 | 5567（64.4%） |
| 潜在（非自环，身份与记录端一致，记录两端均解析） | 188 | 283 | **471** |
| 潜在但自环（不计，F1 规则） | 64 | 709 | 773 |
| 潜在但身份不一致（不计） | - | 52 | 52 |

上界：(5567 + 471) / 8645 = **69.8%**（+5.4 个百分点）。按项目：p001 +34、p003 +17、p022 +75、p044 +71、p050 +73、p051 +22、p061 +99、p071 +20、p075 +9、p076 +51。

注：本次回放的当前基线为 64.4%（10 项目），不可与 COV-GAP 的 57.3%（round12，全语料）直接比较。

## 6. 零影响与耗时

**零影响（同一基线，有/无挂接）**：10 个项目的 `findings/*.parquet`（排除 `sw_wire_routes*`）、`audit/issues.json`、`audit/audit_report.md` 全部相等；`pairs.parquet` 行数与内容相等，issues 相等。唯一差异：`source_files.dxf_path` 的输出目录名（`loop_loggen_base` vs `loop_loggen`）。

**与 round13 的差异不由本次改动引起**：`.tmp/superworks_round13_full` 的代码快照与当前基线在 6 个文件上不同（`audit/component_diagrams.py`、`audit/rules.py`、`audit/superworks_extractor.py`、`extract/superworks_semantics.py`、`extract/text_overlap.py`（新）、`pipeline.py`）。在 p003 上，round13 与基线的 pass/review 状态数已不同（pass 340 vs 344），因此 round13 不能用来证明零影响。

**耗时**（10 项目）：去向记录提取合计 18.4 s（其中 DXF 读取 18.0 s），基线耗时合计 213.3 s，即 +8.6%。单项目最大为 p061（3.5 s，28 页）。

**其他**：
- `tests/unit`：1891 passed, 1 skipped（含 `tests/unit/test_superworks_loggen.py` 7 个用例）。
- 未挂接的回放与有挂接的回放（`loop_loggen_base` / `loop_loggen`）都保留在 `.tmp`。

## 7. 第二阶段接入生产的建议与风险

### 建议

1. **挂接点改到 `cad_extract.py` 的已打开文档处**（每页 `doc` 已存在，一行调用即可）。去掉重复读取，耗时接近 0。需要单独批准修改该文件。
2. **先做候选，不直接出 pass。** 只接入“两端均解析、非自环、两端都是端子/装置端子、两端都无活动配对”的记录（即 strict potential 的 471 个端口）。先以 review 状态输出，逐项目对比 issues 变化。
3. **端口去重：** `one_end_active`（858 条）中一端已有其他导线的活动配对。接入前需要“一端口一配对”的策略，否则会产生同一端口的第二条配对。
4. **冲突策略：** 对 review 旧数字值与 SW 身份不一致的情况（8/8 SW 身份正确），以 SW 身份为准；这是可以在下一阶段直接修复的小项。
5. **远端身份：** 跨页远端以跨页目标的 SW 身份为直接端点；`对端元件` 文本仅作校验，不作为端点（见风险）。
6. **内部元件（2018 个非自环端）**：身份来自元件 SW 端口（如 `1FA-13`），但生产没有对应配对。是否接入需单独评估（与 COV-GAP 的 S3 元件引脚身份一致，风险较高）。

### 风险

- **对端文本与跨页目标不一致。** PCL 中 3225 个跨页远端，对端文本与跨页目标 SW 身份一致的仅 1438 个（44.6%）；不一致多为命名差异（如 `1YD2` 对 `1n901`），更像是跨页端子之后的下一跳，而不是直接邻居。本阶段未在图上验证此推断，需要在第二阶段前抽样确认。装置端子的文本身份约定（设备+引脚）同样未验证。
- **1 端 LOGGEN 记录（1934）**：另一端不在本页 LOGGEN 中，可能是跨页线。未建立其远端，不计入任何统计。
- **LINENO 的语义**：不是固定的“对端”（5560 条匹配到某一端）；不可用作远端的唯一依据。
- **自环判定依赖 F1 规则**：自环记录（1278 条）在生产中有意不出配对；如果 F1 规则将来改变，这部分需要重新评估。
- **读取的 DXF 与生产一致性**：本次挂接只读 DXF，不改变任何既有输出；但若 DXF 缓存重建，需重新验证耗时与解析率。

## 8. 文件与复现

新增/修改（均在本次任务范围内）：
- 新增 `src/dwg_audit/extract/superworks_loggen.py`（解析器、端身份解析、写出）
- 修改 `src/dwg_audit/pipeline.py`：`_write_sw_wire_routes` 与一处调用（约 25 行，写 `findings/sw_wire_routes.parquet`，失败只记录告警；`config.superworks_wire_routes.enabled` 默认 True）
- 新增 `tests/unit/test_superworks_loggen.py`
- 新增 `.planning/superworks-adapter/loop/LOGGEN/tools/`：`eval_loggen.py`、`aggregate_loggen.py`、`zero_impact.py`、`render_loggen.py`
- 本 README 与 `png/`（8 张冲突、10 张补充、4 张严格口径潜在）

复现：
```
set PYTHONIOENCODING=utf-8
python .planning/superworks-adapter/replay.py --output .tmp/loop_loggen --snapshot .tmp/loop_loggen_src --workers 3 --projects p001 p003 p022 p044 p050 p051 p061 p071 p075 p076
python .planning/superworks-adapter/replay.py --output .tmp/loop_loggen_base --snapshot .tmp/loop_loggen_base_src --workers 3 --projects <同上>
python .planning/superworks-adapter/loop/LOGGEN/tools/eval_loggen.py .tmp/loop_loggen .tmp/loop_loggen_eval
python .planning/superworks-adapter/loop/LOGGEN/tools/aggregate_loggen.py .tmp/loop_loggen_eval
python .planning/superworks-adapter/loop/LOGGEN/tools/zero_impact.py .tmp/loop_loggen_base .tmp/loop_loggen .tmp/superworks_round13_full
python .planning/superworks-adapter/loop/LOGGEN/tools/render_loggen.py .tmp/loop_loggen_eval .tmp/loop_loggen .planning/superworks-adapter/loop/LOGGEN/png
python -m pytest tests/unit/test_superworks_loggen.py -q
```

中间产物：`.tmp/loop_loggen`、`.tmp/loop_loggen_base`、`.tmp/loop_loggen_src`、`.tmp/loop_loggen_base_src`、`.tmp/loop_loggen_eval`（`*.json` 逐项目结果、`aggregate.json`、`tables.txt`、`timing.json`）。
