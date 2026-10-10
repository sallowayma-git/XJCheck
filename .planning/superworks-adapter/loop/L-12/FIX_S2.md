# L-12 S2 修复说明：非数字端子名准入（SW 词典）

范围：`src/dwg_audit/audit/candidates.py`、`src/dwg_audit/audit/pairs.py`（仅 build_pairs 候选通道衔接）、`tests/unit/test_loop_l12_lexicon.py`（新增）。未改 `pipeline.py`、`page_extractors.py`，未碰 `superworks_*.py`、`rules.py`。

## 1. 可行性判断

- 口径 a 的"功能标签不在词典中"前提**不成立**：SW 连接标签的设备端子名（`1-26n-系统告警(NO3)`、`1-26n-失电告警(NC1)`）与串口/脉冲/COM 同样出现在 SW 元数据里。本修复用文本形态排除功能标签（见 §4，需主线程确认）。
- **串口/脉冲 13–16、IRIG 在 SW 元数据中无身份**（SW 仅有 1–12 与 COM1–3），因此 p075 的 34 条 "no_lexicon_hit" 缺侧（串口/脉冲 13–16、IRIGB）**无法由本方案解决**，需另一数据源。
- 候选阶段拿不到 SW 数据：`build_terminal_candidates` 只收 line_groups/texts/config/sheets。要接入，需要主线程在 `pipeline.py` 与 `page_extractors.py` 做最小接线（见 §5）。本次在 candidates.py 中以可选参数 `endpoint_lexicon` 实现，默认 `None` 时行为与修改前一致。

## 2. 修改

### candidates.py
- 新增 `build_endpoint_lexicon(superworks)`：从 SW 数据取词典，全部来自元数据，不写手工列表。
  - 连接标签：清洗后的 `text.value`（如 `& YD10` -> `YD10`，`1-26DK2-2 &` -> `1-26DK2-2`）、`endpoint_identity`；若身份形如 `<n>-<n>n-<pin>`，取 `<pin>`（如 `1-26n-COM1` -> `COM1`）。
  - 端口：`endpoint_identity`、`label`/`pin` 别名；内部元件类别排除；`label` 仅为身份前缀（`1-26n` 对 `1-26n1201`）时视为设备名，不入词典。
  - 连接标签/端口身份中含 `\((NO|NC)\d+\)$` 的功能标签整体排除。
- `build_terminal_candidates(..., endpoint_lexicon=None)`：仅当数字及既有非数字通道均未给出值、且非物理端口绑定时，用规范化文字查词典（`_lexicon_terminal_value`，长度 ≥2，功能标签再次拒绝）。命中则通道为 `schematic_semantic_endpoint_channel`，细分 `sw_endpoint_lexicon_terminal`。
- 行距守卫：词典名与线端的 `|dy| > 3.0` 拒绝（`schematic_semantic_out_of_row`）。

### pairs.py（最小改动）
- `build_pairs` 中，在 `_enforce_text_endpoint_identity` 之后、top_k 截断之前，调用新增的 `_scope_lexicon_terminal_candidates`：某侧存在数字端子候选时，丢弃该侧的词典通道候选。
- 理由：candidates 阶段看到的数字候选可能在 pairs 阶段被 `text_identity_owned_by_other_endpoint` 降级，因此判定必须放在 pairs 阶段。
- 调整顺序（先作用域、后截断）对无词典候选的情况是空操作。

## 3. 验证

### 单元测试
- `tests/unit/test_loop_l12_lexicon.py`：11 通过。覆盖：词典纳入/排除（功能标签、设备前缀、内部元件）；词典内名称准入；规范化（`1-26DK2-2 &`）；词典外名称拒绝；无词典时拒绝；功能标签即使在词典中仍拒绝；行距外拒绝；数字候选不变；侧向作用域；配对取词典名仅在无数字侧。
- `test_terminal_candidates.py` + `test_loop_l16_candidates.py`：73 通过。
- `pytest tests/unit -q` 全量：1806 通过、1 跳过、2 失败，失败项为 `test_pairs_and_rules.py::test_rules_group_near_duplicate_line_claims_for_one_missing_side_text` 与 `test_rules_do_not_transitively_merge_duplicate_line_claims`。两者只调用 `build_issues`，不经过本次改动路径；在探测快照（旧 rules.py）下通过，判定为其他子代理正在修改的 `rules.py`（当前为 M 状态）所致，未处理。

### 单项目重放（4 项目，快照 + 环境变量门控接线，探测后已删除）
口径：同一快照、同一代码，基线（词典关闭）与新版（词典开启）各跑一次。

| 项目 | 配对数 | 问题数 基线 -> 新 | 说明 |
|---|---|---|---|
| p075 | 2338 -> 2338 | 71 -> 76 | MISSING 未解决组 72 -> 52（20 组已配对，见下；基线中 6 组折叠在重复线文字问题下，属于同一批未解决组，计数一致）；LOW +18；R-CROSS-PAGE-CONFLICT +1 |
| p000 | 1417 -> 1417 | 2 -> 3 | LOW +1（FZJ2-9 对 10，0.821） |
| p024 | 1921 -> 1921 | 1 -> 7 | LOW +6 |
| p061 | 4229 -> 4229 | 0 -> 19 | LOW +19 |

- p075 的 20 个已配对组：YD 类 12 组（YD1–YD13 中的 12 个）、DK 类 8 组（1-26DK1/2-2/4，2-26DK1/2-2/4）。GC0051（13 ↔ YD10）配对为 pass，但与 S0015 的 13 ↔ YD13 触发跨页冲突（见 §4.5）；GC0259 本身无新增问题。其余 18 组为 0.926 的 LOW（"ambiguous candidate ordering"，即审核级，未进入 pass）。
- 既有双侧配对：值与状态无变化。p075 的 4 条 GND 配对（PC0123/0185/0331/0393）值不变，置信由 0.476 升至 0.907，仍为 review。
- 其他项目的新增 LOW（p000/p024/p061 共 26 条）是新完整配对（数字 ↔ SW 名）。p061 的样例（PT0354，1-21CLP2-1 ↔ 1）目视为同一端子表行，合理，但它们都是审核级，需主线程判断是否接受。

### 词典自洽性核对
- p075 的 YD 类配对：对其中 10 条（审核级）核对，SW 连接标签的设备端子名与同行功能标签一致，10/10 通过（例：行 13 的 `系统告警(NO3)` 对应 SW 中 `YD10` 的 `1-26n-系统告警(NO3)`）。另 2 条 pass 配对未纳入该核对。
- DK/GND 类无法用同一方法核对（标签无设备端子名），目视样例（PC0130：行 05 对 `1-26DK2-2 &`）合理，未独立证实。
- 抽样截图（scratchpad，非仓库文件）：`C:/Users/25788/AppData/Local/Temp/claude/F--workspace-XJToolkit/367e37bd-5006-413b-a449-e1c665a8b237/scratchpad/l12_fix_s2/`，共 8 张：p075 的 PC0051、PC0069、PC0099、PC0130、PC0137、PC0259；p061 的 PT0354；p024 的 PT0154。

## 4. 残留与需决定事项

1. **接线（需主线程）**：`pipeline.py` 在 `superworks` 取得后调用 `build_endpoint_lexicon(superworks)`，并把结果加入各路由的 `extractor_kwargs`（wire/component/terminal/layout）；`page_extractors.py` 的四个公开函数与 `_extract_pairs_for_route` 增加 `endpoint_lexicon` 参数并传给 `build_terminal_candidates`。未接线时词典为空，结果与修改前一致。
2. **口径 a（需决定）**：功能标签排除依赖文本形态 `\((NO|NC)\d+\)$`。这是按文本形态排除，不是词典白名单，但仍需主线程确认是否接受。若不接受，需另给功能标签判定依据。
3. **串口/脉冲 13–16、IRIG**（p075 基线 34 组）：SW 无身份，本方案无法解决，需另一来源（如设备端子表）。
4. **行距阈值 3.0**：GC0075、GC0087 的名称位于相邻行（约 4 单位外），被守卫拒绝，未配对。放宽会带来跨行误配，未放宽。
5. **跨页冲突（p075，新增 1 条）**：S0014 与 S0015 为同模板，同一行号 13 分别对 YD10（1-26n 设备）与 YD13（2-26n 设备）。这是两个设备的合法差异，但规则会报跨页冲突，需决定是否豁免。
6. **与 rules.py 的交互**：p075 基线中 GC0099 的 "重复线文本归属" 问题因 GC0099 获得 YD1 而转为 LOW；rules.py 若调整重复线认领逻辑，需复核此组。
7. S2 中的 "同一文字被两线认领" 与 S3 相关，本次未处理。

## 5. 未做事项

- 未改 `pipeline.py`、`page_extractors.py`、`superworks_*.py`、`rules.py`。
- 未执行全量重放。
- 探测目录（`.tmp/loopY4_probe`、`.tmp/loopY4_probe_base`）与快照（`.planning/superworks-adapter/loopY4_src`）已删除。
- git 仅做只读查询（status/diff/log），无状态变更。
