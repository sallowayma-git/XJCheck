# V-06 FIX_star：SW 外部端点值去除 * 与 & 装饰

范围：src/dwg_audit/audit/superworks_extractor.py；新增 tests/unit/test_superworks_loop_v06_star.py。未改 rules.py，未做 git 写操作，未全量回放。

## 1. 第六轮统计（.tmp/superworks_round6_full，77 项目）

- 带 "*" 的 pair 值只出现在 right_value：4257 条 pair，分布 60 个项目。左值 0 条。
- 全部为 pair_kind=component_mapping、status=pass，即 connect-line 路径（superworks_extractor.py 782 行对应分支）。
- 形态：前缀 "* X" 2155 条值，后缀 "X *" 2102 条值，中间位置 0 条。另有 108 个值为双星（如 "** 1ID1"、"1Bn1 **"），仍仅位于首尾。
- 去除首尾 "*" 后，结果与同项目内不带 * 的端点值一致：4257/4257。
- "&" 残留 0 条。
- strip 路径（696 行对应分支）：sw_strip_rows 的 connection value 中含 "*" 或 "&" 为 0（6952 行）。
- 结论："*" 为纯装饰，只出现在首尾，去除安全。中间位置的 "*" 未触及。

## 2. 修改

- 新增 `_SW_ENDPOINT_DECORATION_PATTERN = ^[\s&*]+|[\s&*]+$` 与 `_clean_sw_endpoint_value()`：先 NFKC/normalize，再去首尾的 "&"、"*" 及其间空白。中间字符与 "@" 原样保留（L-17 暂缓）。
- 应用位置：
  - `_destination_keys`（约 343 行）：由 `strip("&")` 改为同一清洗函数，保证目的端 key 与 destination 一致。
  - strip 路径 values（约 696 行附近）。
  - connect-line 路径 values（约 782 行附近）。
- raw 字段：connect-line 路径原已写入 `evidence.external_endpoint_raw = label.text["value"]`（原文），本次未改。strip 路径的 mapping 无 raw 字段，本次未新增字段，以免改变 table_mapping evidence 结构；r6 数据中该路径本就无 * 或 &。
- 与 component_diagrams.py:381 的差异：旧 lattice 正则 `^[&*]\s*|\s*[&*]$` 每端只去一个字符，对 "** 1ID1" 会残留 "* 1ID1"。本实现去整段装饰。未直接复用该私有函数，以免跨模块依赖私有名。

## 3. 单元测试

- tests/unit/test_superworks_loop_v06_star.py：19 项，全部通过。覆盖：前后缀 "*"/"&" 去除（含双星、混合、全角）；中间字符不变（"1I*2D1"、"1I&2"、"A * B"）；"@" 不变（"1-42TD1 @"、"@1-42TD1"、"1-42TD1@c1"）；端到端 extract_superworks_pairs 下 right_value 为干净值且 `external_endpoint_raw` 保留原文（"* ZD1"、"ZD2 *"）。
- `pytest tests/unit -q`：1748 passed, 1 skipped（工作区含其他未提交修改时的结果）。

## 4. 单项目验证（p016 p018 p020 p050 p000）

快照 `.planning/superworks-adapter/loopX1_src` 为当前 src，包含 rules.py 等进行中修改。为区分归因，另建对照快照 loopX1_ctrl_src（仅将本次改动回退为旧的 `strip("&")` 语义），对 p050 单独回放。

带 * 或 & 的右值（pair 数）：

| 项目 | r6 | 修复后 |
|---|---|---|
| p016 | 321 | 0 |
| p018 | 209 | 0 |
| p020 | 210 | 0 |
| p050 | 38 | 0 |
| p000 | 16 | 0 |
| 合计 | 794 | 0 |

变化键核对：五个项目中，所有消失的 (sheet,left,right,kind) 键都恰好对应一个新增键，且新增键 = 原值去除首尾 * & 后的结果。非星号键变化数为 0。

pairs 按 kind/status（五项目合计，r6 → 修复后）：

| kind / status | r6 | new | diff |
|---|---|---|---|
| bridge_mapping / pass | 320 | 320 | 0 |
| component_mapping / pass | 2451 | 2287 | -164 |
| continuation / review | 764 | 764 | 0 |
| ordinary_pair / discard, pass, review | 2801 / 85 / 180 | 2801 / 85 / 180 | 0 |
| semantic_mapping / review | 500 | 500 | 0 |
| table_mapping / pass | 2539 | 2539 | 0 |
| wire_component_mapping / discard, pass, review | 65 / 2105 / 5 | 65 / 2105 / 5 | 0 |
| 合计 | 11815 | 11651 | -164 |

-164 全部位于 p050，且对照快照中同样出现，与本次改动无关（见下）。

各规则 issue 与第六轮差异：

- p016、p018、p020：issue 数 0 → 0，无差异。
- p000：R-PAIR-LOW-CONFIDENCE 1 → 1，R-SUPERWORKS-CONFLICT 1 → 1，同键。
- p050：r6 为 4 条，修复后为 2 条。
  - I0013 R-MANY-TO-ONE（S0028，1QD2 → 1KLP1-1）与 I0014 R-MANY-TO-ONE（S0028，1QD5 → 1KLP29-1）消失。
  - 对照快照（仅回退本次改动）同样消失，故不是本次改动导致。成因：r6 中 S0026 同一对 1KLP2-1 → 1KLP1-1 有一条旧路径 pair（PAB0100，strip_two_port_component）与 SW pair 并存；对照与修复后均被去重，且 164 条 SW component 重复行也合并为 1 条。这些去重来自工作区其他未提交修改（snapshot 中的 rules.py、superworks_semantics.py、pipeline.py 等），非本次改动。
  - 其余 issue 两侧一致：R-MANY-TO-ONE S0030 1ID5/GND，R-CROSS-PAGE-CONFLICT S0023 1n/NCK305-5/1CD3。

## 5. 是否因值变干净而新增 多对一 / 跨页冲突 / 重复配对

- p050 对照 vs 修复后：issue 列表完全相同；sheet/left/right/kind 重复行数均为 756；pair_id 无重复。
- 其余四项目 r6 vs 修复后：重复行数相同（p016 912、p018 691、p020 963、p000 569）。
- 结论：本次清洗未新增任何多对一、跨页冲突或重复配对。

## 6. 未处理与注意

- "@" 按 L-17 暂缓，未剥离。
- 本次未全量回放；全量影响需另行确认。
- p050 的 R-MANY-TO-ONE 两条消失属于工作区其他未提交改动的效果，需由 rules.py 等改动的负责方核对。
- 临时产物：.tmp/loopX1_probe、.tmp/loopX1_ctrl、.planning/superworks-adapter/loopX1_src、loopX1_ctrl_src 已按要求清理。
