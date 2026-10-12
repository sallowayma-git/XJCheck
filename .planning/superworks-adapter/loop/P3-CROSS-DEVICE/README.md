# P3-CROSS-DEVICE：V1 跨符号导线映射的拦截

分支 `superworks-loop`。基线 HEAD=e99fd86（round23 为对比基线，快照为 e99fd86 + 本切片四个文件）。未 commit、未 push；未改 V2 模块与 `symbol_port_proposal.py`；未加 PDF/OCR；判据无项目、句柄、取值、块名特判；未删除任何 V1 代码；控制台 `PYTHONIOENCODING=utf-8`。

**注意两点**：
1. 本切片开工后，P1 已在 HEAD 上提交 `f40be1a`（去重）与 `3d06572`（清理）。本切片的回放与对比仍以 e99fd86 为基线（快照未混入 P1 改动，按指示从 HEAD 恢复）。工作区（含 P1 已提交内容）的全量单元测试仍全部通过（2115 passed, 1 skipped）。合并到含 P1 的 HEAD 后，建议以 `f40be1a` 为基线复跑一次全量（本次未做，约 70 分钟）。
2. 本切片的根因落在 `wire_components.py`（它生成了这些配对），不在任务列出的 pairs.py / candidates.py / page_extractors.py / component_diagrams.py 之中。已按要求只改 V1 配对生成层：`wire_components.py`、`candidates.py`、`page_extractors.py`，以及 `line_groups.py` 中的判定器。`pairs.py` 与 `component_diagrams.py` 未改动（`pairs.py` 产出的配对由 `page_extractors.py` 的守卫调用覆盖）。

## 0. 结论

1. **根因。** 1,249 条的生成函数是 `wire_components.py`（`extract_component_prefixed_signal_pairs` 内三个子提取器）。它们只按文字位置配对：前缀列 + 最近的局部号 + 同一行最近的外部端点，不查两端之间的线段，`line_group_id` 为空。因此线组层在符号本体处的断开（WIRE-BREAK）对它们不起作用。另一个根因是 `candidates.py` 的文字候选搜索：文字可以挂到线组端点上，即使两者之间隔着符号本体。
2. **改动。** 两处同一判据：两端之间的轴向直线穿过同一符号的两个 TERMPOINT（SW 登记端口或未登记 SYMB2）时，**确定**穿过（无圆点、宽度 ≥ 2.0）降为 discard，**不确定**（圆点或窄体）降为 review。配对层（`wire_components.py` 守卫，并覆盖 `pairs.py` 产出的 V1 配对）与候选层（`candidates.py`，拒绝原因 `path_crosses_symbol_body`）分别调用同一个判定器 `PathBodyChecker`（`line_groups.py`，复用 WIRE-BREAK 的 `_MarkIndex`、`_gap_has_dot`、`SYMBOL_MIN_BODY_WIDTH`）。SW 自身的判定（带 `source=superworks` 证据的配对）不被改写。
3. **效果（全量 77 项目，最终代码）。** 1,249 条跨装置导线映射中，**921 条降为 discard，23 条降为 review，305 条仍为 pass**。普通配对的穿越 discard 由 4,171 降为 283，穿越 review 由 387 降为 0，穿越 pass 始终为 0。
4. **精度。** 抽样 36 + 17 + 12 例被拦截配对，**全部为真实穿越**（配对层 36/36，泛化守卫 17/17，候选层 11/12，另 1 例为框内语义标签，拒绝可接受）。残留 pass 抽样 12 例中，11 例未见穿越，1 例疑似穿过仅有单个 SW 端口的元件（残留限制，见第 7 节）。
5. **段覆盖。** 被拦截的 1,273 条（1,064 discard + 209 review）中，**1,159 条（91.0%）两端仍被其他非 discard 配对覆盖**（分段配对已接管）；113 条一端无覆盖；1 条两端无覆盖。10 项目抽样中的无覆盖主要是 `1ZKK` 内置端口一侧与接触器标签（第 4 节）。
6. **issue。** 全量 40 → 40，按 (项目, rule, sheet, message) 逐条相同（新增 0，消失 0）。10 项目 9 → 9，逐条相同。
7. **覆盖率。** 严格口径 51,964 → 51,957（−7）：失去 16 个端口（p038、p049 各 8 个），获得 9 个端口（p061 4、p043 2、p044 2、p064 1）。失去的例子：p038 线组 GW0502 右端的 `1-4QD24`，原由单侧配对 PW0502 消费；PW0502 的右端候选是文字 `225`（T1292），它位于端子体另一侧，候选层已拒绝，PW0502 随之消失。含延续口径 59,050 → 59,051（+1）：同样失去那 16 个端口，获得 17 个（p004 1、p005 1、p006 2、p043 2、p044 2、p061 4、p064 1、p067 2、p068 2）。
8. **文字搜索冗余。** **部分解决。** 候选层拒绝了 8,220 个此前 accepted 的候选（均为“文字位于端子体另一侧”），普通配对的穿越 discard 由 4,171 降为 283。剩余 283 条全部为“同一线组两端都有候选、线段在零间隙处连续穿过符号”（线组层未断开，属于 WIRE-BREAK 的遗留形态，本切片未处理）。
9. **需要主线程决定的一件事。** 候选层规则使单侧 review 挂接大幅减少（全量 review 单侧净减 443 条：1,311 条消失、868 条新增；双侧净减 189 条），discard 总数增加 1,894。10 项目逐条核对时，这些挂接的文字（123 条中 122 条）位于端子体另一侧，属于错误挂接；去掉后，对应线端不再以 review 形式出现（第 5.3 节）。

## 1. 根因：1,249 条的来源

口径：round23 全量中 `tag = c`（两端文字都能在同页 SW 端口上找到）、`status = pass`、同页与项目内都没有同值的 SW 配对（`sw_dup = none`）。LEGACY-CENSUS 的标签与重复判定用 `.planning/superworks-adapter/loop/LEGACY-CENSUS/tools/build_tagged.py` 与 `analysis.py` 复现（工作目录改到临时目录，结果一致）。

| 子模式（`component_submode`） | 条数 | 生成函数（`wire_components.py`） | 配对依据 |
|---|---:|---|---|
| `scoped_visible_prefix_external_endpoint_mapping` | 1,054 | `_extract_scoped_visible_prefix_external_endpoint_pairs`（约 L320），构造 `_build_scoped_visible_prefix_external_endpoint_pair`（约 L793） | 可见前缀列（如 `1n`）下方的局部号（|dx| ≤ 36，0 < dy ≤ 130），同一行最近的外部端点（|dy| ≤ 2.5，|dx| ≤ 75） |
| `first_prefixed_external_endpoint_mapping` | 175 | `_extract_first_prefixed_external_endpoint_pairs`（约 L398），构造 `_build_first_prefixed_external_endpoint_pair`（约 L939） | 外部端点自身的数字前缀（如 `1QD4` 的 `1`）与同一行最近的局部号 |
| `inline_body_port_mapping` | 20 | `_extract_inline_body_port_pairs`（约 L445），构造 `_build_inline_component_pair`（约 L1007） | 元件本体的端口文字与同一行最近的端点 |

三者的 `line_group_id` 全部为空：配对不经线组，所以 WIRE-BREAK 在线组层的断开对它们无效。另外，`candidates.py` 的 `build_terminal_candidates` 会把搜索框内的数字文字挂到线组端点上，而不检查端点与文字之间是否隔着符号（round23 全量中，这样形成的普通配对 discard 有 4,171 条、review 387 条穿越符号本体）。

## 2. 改动

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/audit/line_groups.py` | 新增 `PathBodyChecker`（路径判定器，每张图一个，复用 `_MarkIndex`、`_gap_has_dot`、`SYMBOL_MIN_BODY_WIDTH`、`_TERMINAL_TOUCH_TOLERANCE`）与 `path_body_checkers()`。常量 `_PATH_END_MARGIN = 1.0`、`_PATH_ALIGN_TOLERANCE = 2.5`。 |
| `src/dwg_audit/audit/wire_components.py` | `extract_component_prefixed_signal_pairs` 增加参数 `wire_break_evidence`；`guard_pairs_against_symbol_bodies`（公开，约 L229）对返回的配对逐条判定；SW 证据的配对跳过。 |
| `src/dwg_audit/audit/candidates.py` | `build_terminal_candidates` 增加参数 `path_checkers`；新拒绝原因 `path_crosses_symbol_body`；`_candidate_path_crosses_symbol_body`（约 L482）。 |
| `src/dwg_audit/audit/page_extractors.py` | 把 `wire_break_evidence` 传给候选构建与 `extract_component_prefixed_signal_pairs`；对 WireDiagramExtractor 的 `build_pairs` 产出（含 `pairs.py` 的 `schematic_wire_logic_endpoint`）调用 `guard_pairs_against_symbol_bodies`。 |
| `tests/unit/test_v1_cross_symbol_guard.py` | 20 项：判定器（两端子、两个符号、悬挂端子、锚点在端子上、圆点、窄体、竖向、斜向、行偏差）；配对守卫（无标记不变、穿越 discard、不确定 review、标记在别的行不变）；候选守卫（拒绝、无标记不变）；`pairs.py` 来源的守卫；SW 证据配对不变。 |

**判定规则（配对层与候选层共用）。**

- 路径：两锚点之间的轴向直线（|dy| ≤ 2.5 为横向，|dx| ≤ 2.5 为竖向；斜向或点状不判）。候选层的路径是线组端点到文字在线组方向上的投影。
- 穿越：同一符号（同一 symbol_key）的两个不同 TERMPOINT 标记，中心都严格位于路径内部（距两端 ≥ 1.0），且横向落在路径带内。候选层的线端一侧允许端点处的标记计入（端子就在线端上）。
- 带宽：`max(1.0 + min(dx,dy)/2, 2.5)`。锚点是文字插入点，常偏离它所标注的导线行约 2 个单位；2.5 与配对时的行对齐容差一致。相邻行一般相距 ≥ 5，不会误吸附。
- 结论：**body**（无圆点、宽度 ≥ 2.0）→ 配对 discard（`discard_reason = crosses_symbol_body`）。**ambiguous**（路径内有连接圆点，或宽度 < 2.0 的 1.25 节距端子排）→ 配对 review。候选 body → 候选 rejected。
- 不改的情形：无 SW/SYMB2 标记的图纸；斜向或点状路径；SW 证据配对；单侧配对（无两端坐标）。

**为什么 discard 而不是 review。** body 是两侧端子都确定位于直线上，直接连线不可能成立；两侧的端子或元件由线组层的分段配对给出（线组在符号本体处已断开）。圆点或窄体属于 WIRE-BREAK 的未知形态，证据不足，降为 review。

## 3. 抽样核对（目视，原图为冻结 DXF）

渲染：蓝线为配对路径，红框为 SW 端口，绿线为未登记 SYMB2 的 TERMPOINT，橙线为 V1 线组，洋红圈为锚点。图在 `png/`。

| 样本 | 数量 | 结果 | 图 |
|---|---:|---|---|
| A：配对层守卫拦截（10 项目分层抽样，最终代码） | 36 | 31 例 body（discard）与 5 例 ambiguous（review）**全部为真实穿越**：接触器 13/14 脚、1C3LP/1KLP 接触器、带两端子圆点的元件、线圈、端子排（1.25 节距引脚）。误拦截 0 例。 | `xdev_A_guarded_01..06.png` |
| B：泛化守卫（`pairs.py` 来源的 `schematic_wire_logic_endpoint`、`semantic_mapping`、`ordinary_pair`，全量 17 例） | 17 | 17 例全部为真实穿越（如 `14 ↔ Reset signal` 穿过 115 端子排，`625 ↔ 626` 穿过 PAC-861GA-GCN 设备框，`607 ↔ DC 0-5V` 穿过线圈）。 | `xdev_pairs_py_guard_01..03.png` |
| C：候选层拒绝（10 项目分层抽样） | 12 | 11 例文字位于端子或元件另一侧，拒绝正确；1 例（p003 GW0060「遥控复归接点」）是框内语义标签，拒绝可接受。 | `xdev_candidates_01..02.png` |
| D：census-D3 残留 pass（10 项目 83 条中抽样） | 12 | 11 例未见穿越；1 例（p022 `1QD24 ↔ 1n832`）疑似穿过仅有一个 SW 端口的元件（残留，见第 7 节）。 | `xdev_d3_residual_01..02.png` |

## 4. 分段覆盖（拦截后该行各段是否已由其他配对接管）

判定：被拦截配对的两端文字，在同图纸上是否仍出现在某个非 discard 配对中（文字级覆盖）。

- **全量 1,273 条被守卫作用的配对**（1,064 discard + 209 review）：两端都有覆盖 **1,159 条（91.0%）**；仅一端有覆盖 113 条（左端无 75，右端无 38）；两端都无 1 条。
- **10 项目 A 组 36 例**：32 例两端都有覆盖；4 例一端无覆盖：p022 PWM0009/0010/0011（`1ZKK1-5/-3/-1` 内置端口一侧，另一侧是 `1-7UD17~19` 等元件的引脚，该元件引脚到 ZKK 端口的线段没有配对）与 p026 PWM0104（接触器标签 `1-4CLP2`）。
- **缺口**：`inline_body_port` 类（内置端口）与接触器标签的线段，分段配对没有接管。这是线段配对层的缺口，本切片未修复。

## 5. 回放结果

### 5.1 10 项目（p001 p003 p022 p026 p044 p051 p061 p071 p074 p075，`.tmp/loop_xdev`）

| 指标 | round23 | 本切片 |
|---|---:|---:|
| pairs | 20,296 | 20,302 |
| 内容键匹配的状态变化 | — | pass→discard 106；pass→review 20；review→discard（semantic）1 |
| issues | 9 | 9（逐条相同） |
| 严格覆盖（consumed / eligible） | 5,918 / 8,618 | 5,924 / 8,618（+6） |
| 含延续覆盖 | 6,508 / 8,618 | 6,514 / 8,618（+6） |
| census-D3（183 条） | pass 183 | discard 98，review 2，pass 83 |

### 5.2 全量 77 项目（`.tmp/superworks_round24b_full`，快照 `round24b_full_src`）

| 指标 | round23 | 本切片 |
|---|---:|---:|
| pairs | 178,696 | 178,713 |
| pass / review / discard | 108,601 / 27,792 / 42,303 | 107,356 / 27,160 / 44,197 |
| 守卫作用的配对（pair 级） | — | discard 1,064（body）；review 209（ambiguous） |
| 内容键匹配的状态变化 | — | pass→discard 1,036；pass→review 208；review→discard 27；discard→review 1 |
| census-D3（1,249 条） | pass 1,249 | discard 921，review 23，pass 305（ID 与取值一致，0 处不一致） |
| 候选层拒绝（round23 中 accepted） | — | 8,220 |
| issues | 40 | 40（按项目、rule、sheet、message 逐条相同，新增 0，消失 0） |
| 严格覆盖 | 51,964 / 82,680（62.85%） | 51,957 / 82,680（62.84%，−7） |
| 含延续覆盖 | 59,050 / 82,680（71.42%） | 59,051 / 82,680（71.42%，+1） |

**离线穿越统计（同一判定器，全量，`tools/results/body_tally_full.json`）**

| 类别 | round23 | 本切片 |
|---|---:|---:|
| 普通配对 discard 且穿越符号 | 4,171 | 283 |
| 普通配对 review 且穿越符号 | 387 | 0 |
| 普通配对 pass 且穿越符号 | 0 | 0 |
| wire 配对 pass 且穿越符号 | 1,042 | 6（SW 身份校验产出，不改，见第 7 节） |
| wire 配对 pass 且不确定 | 217 | 8（同上） |
| 语义配对 review 且穿越符号 | 24 | 0（改为 discard 24） |

**残留的 283 条普通配对穿越 discard**：全部是“同一线组两端都有已接受候选”（线组在零间隙处连续穿过符号，WIRE-BREAK 的间隙判据不切），属于线组层的遗留，未改。

### 5.3 单侧 review 的消失（需主线程判断）

内容键对齐后，全量的未匹配配对（round23 有、本切片没有）：review 单侧 1,311 条、review 双侧 417 条、discard 单侧 635 条、discard 双侧 3,901 条；本切片新增：review 单侧 868 条、review 双侧 228 条、discard 单侧 5,357 条、discard 双侧 1,073 条。

- 单侧 review 的消失，来自候选层：10 项目中消失的 123 条单侧 review，其唯一候选 122 条由 accepted 变为 `path_crosses_symbol_body` 被拒（另 1 条候选仍 accepted）。这些文字位于端子体另一侧，挂接不可信。去掉后，线端不再有挂接，也不再以 review 形式报出。
- 单侧 discard 的增加，主要是两类，都不产生 issue：
  - 装置内部规则（DEV-INT，静默丢弃，`device_internal`）：全量由 3,009 条增至 4,647 条（+1,638，其中普通配对 +1,889，语义 −193，wire −57）。这主要是候选挂接变化后新形成的普通配对，落在装置内部标签上，按既有规则丢弃。**这部分数量增加较大，主线程应抽查其挂接是否合理。**
  - `scoped` 映射已覆盖的裸局部号（设计上不得作为普通配对输出，`_mark_wire_component_covered_ordinary_pairs` 的旧规则照常执行），新增约 927 条。
- **代价：** 线端在端子体处“另一端未识别”的信息不再以 review 出现。若主线程认为这类线端应保留为 review，需要另定规则（例如为被拒候选的线端生成单侧缺端 review）。本切片未做。issue 未因此变化。

### 5.4 耗时

同机顺序对照（HEAD 快照与新快照，各 1 次）：p003 6.6 s → 6.6 s；p051 6.2 s → 6.3 s（+1.6%，噪声范围）。

## 6. 文字搜索冗余：是否一并解决

- **已解决的部分。** 候选层的“文字在端子体另一侧仍被挂到线端”形态：8,220 个候选被拒绝，普通配对穿越 discard 由 4,171 降为 283，穿越 review 由 387 降为 0。
- **未解决的部分。** 同一线组两端都有候选、线段在零间隙处连续穿过符号的形态（283 条）：这是线组层的问题（WIRE-BREAK 的零间隙不切），需要线组层的新判据，本切片未碰线组的合并规则。

## 7. 遗留与限制

1. **依赖 SW 元数据。** 守卫只看 SuperWORKS 端口与未登记 SYMB2 的 TERMPOINT。无标记的元件不在范围内。全量 D3 残留 305 条中，仍可能有穿越非 SW 元件的配对（抽样 12 例中 1 例疑似）。要覆盖，需要 SW 之外的元件几何证据，本切片未做。
2. **单个 SW 端口的元件。** 两标记的本体判据要求同一元件有两个 TERMPOINT 位于路径上。仅有一个端口落在路径上的元件，不构成本体（抽样中的 `1QD24 ↔ 1n832`）。
3. **锚点偏差。** 锚点偏离导线行超过 2.5 时，路径判定不生效（D3 残留中所有配对都在 2.5 之内，未观察到此情形，但不保证）。
4. **SW 自身的配对。** 带 `source=superworks` 证据的配对不改写。其中 14 条 pass 配对按 SW 的身份校验穿过了符号本体（`SuperWORKS identity verified against existing wire endpoints`，6 条 body、8 条 ambiguous）。这是 SW 的判定，应由 SW 侧复核。
5. **宽度不足与圆点。** 守卫判为 ambiguous 的 209 条（均为 wire 配对）按 WIRE-BREAK 的未知形态降为 review。其中绝大多数是宽度不足 2.0（10 项目抽样为 1.25 节距的三针端子排，目视确认穿越），另有圆点 5 例（全量 ambiguous 统计：宽度不足 226、圆点 5）。这是保守处理，不是误判。
6. **覆盖口径的 −7。** 失去的 16 个端口（p038、p049 的 1-4QD24、1-4QD25、1-4QD13 等）原由单侧配对消费：该配对（如 PW0502，线组 GW0502）的右端候选 `225` 位于端子体另一侧，被候选层拒绝后，配对消失。两种口径下都不再消费。获得的端口（严格 9 个、含延续 17 个）来源未逐条核对。
7. **基线。** 见文件开头注意事项。

## 8. 新图纸同类情况如何处理

判据只依赖几何与 SW 元数据：轴向路径、同一符号的两个 TERMPOINT（SW 登记端口或未登记 SYMB2）、连接圆点、线宽。不使用块名、项目名、句柄、取值或页码。

- **同类新图纸：** 只要 SW 为元件或端子给出了 TERMPOINT，并且两个文字之间的直线穿过这两个 TERMPOINT，就自动降为 discard（无圆点、宽度 ≥ 2.0）或 review（圆点或窄体）。候选层与配对层的处理相同。
- **无 SW 元数据的图纸：** 规则不生效，行为与改前一致。这类图纸需要人工核对，或等待 SW 元数据覆盖。
- **不适用的情形（保持原状，需人工）：** 斜向路径、锚点偏差超过 2.5、只有一个端口在路径上的元件、SW 自身的配对（带 SW 证据）。
- **线组零间隙穿越（283 条）：** 不属于本规则；需要线组层的新判据。

## 9. 文件

- 代码：`src/dwg_audit/audit/line_groups.py`（`PathBodyChecker`、`path_body_checkers`）、`wire_components.py`（`guard_pairs_against_symbol_bodies`）、`candidates.py`（`_candidate_path_crosses_symbol_body`）、`page_extractors.py`（传参与调用）。
- 测试：`tests/unit/test_v1_cross_symbol_guard.py`（20 项）。全量 `python -m pytest tests/unit -q`：2115 passed, 1 skipped（工作区，含 P1 已提交的 `f40be1a`）。
- 快照：`.planning/superworks-adapter/round24b_full_src`（e99fd86 的 `src` + 本切片四个文件；与工作区仅在 P1 文件上不同，本切片未改）。
- 回放输出：`.tmp/loop_xdev`（10 项目）、`.tmp/superworks_round24b_full`（全量）。
- 图：`png/`（13 张）。
- 工具：`tools/`
  - `xdev_summary.py`：汇总（内容键对齐的状态变化、守卫计数、D3、issue、覆盖）。
  - `xdev_scan_all.py`：离线穿越扫描（同一判定器）。
  - `xdev_sample.py`、`xdev_candidate_sample.py`、`xdev_d3_residual.py`、`xdev_extra_check.py`：抽样渲染。
  - `xdev_compare.py`：按 pair_id 的逐项目对比（其中的状态变化计数不可靠，见脚本说明）。
- 结果：`tools/results/`
  - `summary_full.json`、`summary_ten.json`、`body_tally_full.json`、`scan_base_full.json`、`scan_new_full.json`；
  - `d3_census_1249_status.csv`（1,249 条的逐条状态）；
  - `guard_sample.json`、`candidate_sample.json`、`d3_residual_sample.json`（抽样清单）；
  - `port_consumption_changes.json`（端口消费的增减）。
- 复现：D3 集合用 LEGACY-CENSUS 的 `build_tagged.py` 与 `analysis.py`（输出目录改到临时目录）。

## 10. 未做 / 留给主线程

- 不 commit、不 push（按指示）。
- 未以 `f40be1a` 为基线复跑（见文件开头）。
- 线组层的零间隙穿越（283 条）未处理。
- 单侧 review 的消失（第 5.3 节）需要主线程决定是否保留。
- SW 自身的 14 条穿越配对（第 7 节第 4 条）交 SW 侧复核。
