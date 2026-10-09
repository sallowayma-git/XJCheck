# 第五轮 M：同名标签撤销收窄（M1）与端子排行映射的同排/跨排标记（M2）

范围：修改 `src/dwg_audit/extract/superworks_semantics.py`（M1，`_definition_ports`）、`src/dwg_audit/audit/superworks_extractor.py`（M2）、`tests/unit/test_superworks_round5_producer.py`。未改 rules.py、series_chains.py 或其他文件；未提交；未删除文件；未全量回放。

快照与产物：
- M1 快照 `.planning/superworks-adapter/round5M_src`（仅 M1 改动）；输出 `.tmp/round5M_probe`。
- M1+M2 快照 `.planning/superworks-adapter/round5M2_src`；输出 `.tmp/round5M2_probe`。
- 两快照的 rules.py 与 series_chains.py 逐字节相同，二者差异只在 superworks_extractor.py（M2），因此 M1 与 M2 的对比是干净的。
- 第四轮对照：`.tmp/superworks_round4_full`。注意第四轮是用旧 rules.py 跑的，相对第四轮的 issue 计数差异混入了并行子代理对 rules.py 的改动；component_mapping、table_mapping 与 pairs 数只受生产端影响。

## 0. 结论

| 项 | 状态 |
|---|---|
| M1 收窄 L1（撤销需回落身份可用且互异） | 已按规格实施；**未达成召回目标**，见 §1.3 |
| M1 p075 B码 身份消失 | 达成（component_mapping 中 B码 左端 0 条，第四轮 192 条；R-ONE-TO-MANY 64 -> 0） |
| M1 p024 / p038 component_mapping 恢复到 >= 第四轮 | **未达成**：249 -> 119，357 -> 167 |
| M2 端子排行映射的同排/跨排标记 | 已实施，复用 F3 的 `StripMembership` 与分类逻辑 |
| M2 p074 R-MANY-TO-ONE | 48 -> 0 |
| M2 不增加 R-TABLE-MAPPING-SOURCE-CONFLICT、R-CROSS-PAGE-CONFLICT | 达成（4 项目均为 0 条） |
| `pytest tests/unit -q` | 1672 passed, 1 skipped |

## 1. M1

### 1.1 实施

`_definition_ports` 的撤销步骤（同一定义实例内，采纳同一规范化标签且来自 >=2 个不同文字实体的端口）增加一道守卫：组内每个端口的 TERMPOINT 端口号（`ports[i]["number"]`，规范化后）都必须非空，且组内互不相同；否则整组保持 nearest 采纳。通用规则，无块名或值特判。

### 1.2 单元测试

`tests/unit/test_superworks_round5_producer.py` 中的 M1 用例：
- B码 形（三个端口号 401/501/601 互异，同名标签）：撤销，reason 为 `same_value_distinct_text`。
- 端口号重复（"1","1","1"）：保留 nearest 采纳。
- 端口号为空（"401","","601"）：整组保留，包括有号的端口。
- 部分重复（"7","7","9"）：保留。

注意：背板型用例是合成的，端口号人为重复。真实背板块的端口号是互异的（见 §1.3），因此这些用例验证的是守卫逻辑，不代表真实背板形态。

### 1.3 探测结果与问题

探测（M1 快照，四个项目）：

| 项目 | 指标 | 第四轮 | M1 | 说明 |
|---|---|---|---|---|
| p075 | component_mapping | 324（其中 B码 左端 192） | 320（B码 0） | B码 身份消失 |
| p075 | R-ONE-TO-MANY | 64 | 0 | 目标达成 |
| p075 | R-PAIR-MISSING-SIDE / R-MANY-TO-ONE | 70 / 1 | 70 / 1 | 不变 |
| p024 | component_mapping / pairs | 249 / 1842 | 119 / 1712 | 失 130 条 component_mapping，与 L1 一致 |
| p038 | component_mapping / pairs | 357 / 2474 | 167 / 2284 | 失 190 条，与 L1 一致 |
| p074 | component_mapping / pairs | 235 / 2263 | 117 / 2145 | 失 118 条（L1 未探测 p074） |

M1 在这四个项目上与 L1 的结果完全相同：守卫对这些项目未阻断任何撤销。原因如下，这推翻了 L1 README 的前提（"背板端口无可用回落身份"）：

- 丢失的组是背板/列式块的行号标签。例：p024 WBH-801-D1ST 上标签 "01" 挂在列端口 101、201、301…1101 上，每个端口的 TERMPOINT 号互异；p024 ZYQ-810E 的 "01" 挂在 701、801；p074 SPMU-857G-CG 的 "1-25n-02" 挂在 202、204…。守卫要求的回落号存在且互异，所以整组被撤销。
- 撤销后，端口的 pin 不再解析，`endpoint_identity`（标签 + "-" + 脚号）变为 None。SW 连接标签的身份仍是 "1n-01"，与端口不再匹配，component_mapping 就丢了。
- 这些端口的回落号本身是可解析的身份：例如 p024 中 "1n101" 作为端子排行身份存在（table_mapping 1n101 -> 1XD3）。所以"无可用回落"的前提不成立。
- 同一结构也出现在 B码 上（同一块、多个独立文字、各自距端口约 7.0、回落号互异）。仅凭定义内的几何与文字无法区分两者。区分信号在下游（右端值是否被端子排行表佐证），而 `_definition_ports` 看不到这些。

需要父代理决定的选项（未擅自实施）：
1. 接受召回损失（p024 -130、p038 -190、p074 -118 条 component_mapping），保留 M1 当前实现（与 L1 效果一致）。
2. 撤销 L1 整体（回到第四轮行为），接受 p075 的 64 条 R-ONE-TO-MANY 误报；B码 问题改由规则端处理。
3. 在下游（component_mapping 生成处）增加佐证判定：标签身份的右端值若被端子排行表佐证则保留。这需要跨阶段逻辑，本轮未实施，也未验证。

M1 守卫在当前数据中未阻断任何撤销；若选择 1 或 2，只需还原 `_definition_ports` 中的 `fallbacks` 守卫（或整段撤销块）。

## 2. M2

### 2.1 实施

- `StripMembership` 新增 `_match_keys`、`is_row_identity(value)`、`lists(owner, listed)`（单向：owner 的行是否列出 listed）；`corroborates` 改为调用 `lists` 的双向组合，F3 的行为不变。
- 新增 `_strip_contract_fields(membership, ..., directed=False)`：从 `_classify_terminal_strip_pairs` 中抽出 F3 的字段计算，F3 调用它（行为不变）；`directed=True` 时佐证只看右端（对方）行是否列出本端。
- 新增 `_table_mapping_strip_fields(membership, own_value, destination)`：仅当 destination 是端子排行身份（`is_row_identity`，精确或去范围后缀）时才计算字段，否则返回 {}。
- `extract_superworks_pairs`：在端子排行循环前创建一次 `membership = StripMembership(data)`，每个 table_mapping Pair 创建后调用 `new[-1].evidence.update(...)`；末尾的 F3 分类复用同一个 `membership`。
- 字段写在 Pair 的顶层 evidence（与 F3 一致），不写在 `evidence["table_mapping"]` 中。

佐证定义：对方行（destination 的行）的 connections（左右及 _2）是否列出本端身份；这与 F3 的双向佐证不同，因为 table_mapping 本身就是本行列出对方，双向判定会恒为真。

### 2.2 结果（M1+M2 快照）

| 项目 | table_mapping 总数 | 同排 | 跨排且佐证 | 跨排未佐证 | 非端子排行身份 | unknown |
|---|---|---|---|---|---|---|
| p024 | 416 | 0 | 10 | 5 | 401 | 0 |
| p038 | 554 | 0 | 20 | 2 | 532 | 0 |
| p074 | 660 | 0 | 114（S0016 56，S0018 56，S0017 1，S0019 1） | 0 | 546 | 0 |
| p075 | 312 | 0 | 0 | 0 | 312 | 0 |

- 同排标记在四个项目中均为 0：现有 `same_strip_destination` 字段在四个项目的 table_mapping 中也全为 0，所以真实数据中同排 table_mapping 并不存在；同排分支仅由单元测试覆盖。
- p074 S0016 的 `1-25U2D9 -> 1-25U3D9` 类 table_mapping 全部为跨排且佐证。

### 2.3 探测总表（第四轮 / M1 / M1+M2）

| 项目 | 指标 | 第四轮 | M1 | M1+M2 |
|---|---|---|---|---|
| p024 | pairs / component_mapping | 1842 / 249 | 1712 / 119 | 1712 / 119 |
| p024 | issues（R-MANY-TO-ONE / R-SUPERWORKS-CONFLICT） | 3（2 / 1） | 3（2 / 1） | 3（2 / 1） |
| p038 | pairs / component_mapping | 2474 / 357 | 2284 / 167 | 2284 / 167 |
| p038 | issues | 2（R-MANY-TO-ONE 2） | 2（2） | 0 |
| p074 | pairs / component_mapping / table_mapping | 2263 / 235 / 660 | 2145 / 117 / 660 | 2145 / 117 / 660 |
| p074 | issues（R-MANY-TO-ONE） | 48（48） | 48（48） | 0 |
| p075 | pairs / component_mapping | 2334 / 324 | 2330 / 320 | 2330 / 320 |
| p075 | issues（R-ONE-TO-MANY / R-PAIR-MISSING-SIDE / R-MANY-TO-ONE） | 135（64 / 70 / 1） | 71（0 / 70 / 1） | 71（0 / 70 / 1） |

R-TABLE-MAPPING-SOURCE-CONFLICT 与 R-CROSS-PAGE-CONFLICT 在四个项目的三个版本中均为 0，未增加。

M2 把 p074 的 48 条 R-MANY-TO-ONE 与 p038 的 2 条（KD23、KD26 类，第四轮已知的残余）一并消除。这是 rules.py 的 `_is_terminal_strip_bridge_claim` 把佐证的跨排连接当作桥接 claim 的结果（rules.py 中已有的 G7 规则），与第四轮 H 第 3 节桶 1 的"合法相邻列"判断方向一致；但它是对规则端的已有豁免的应用，不是新的规则。

## 3. 测试

- `pytest tests/unit/test_superworks_round5_producer.py tests/unit/test_superworks_round4_producer.py -q`：36 passed。
- `pytest tests/unit -q`：1672 passed, 1 skipped。
- 新增测试：M1 四项（§1.2）；M2 四项：跨排且佐证（U2D9 -> U3D9，由 U3D9 行列出 U2D9）、跨排未佐证（U4D9 -> U3D9）、同排（结构上的测试，真实数据中不出现）、非端子排行身份不写字段（1XD3）。

## 4. 限制

- M1 未达成召回目标（§1.3）；需父代理决定选项 1、2 或 3。
- M1 的背板型测试是合成的（端口号重复），与真实背板形态不符。
- M2 的同排分支在真实数据中未出现，仅由单元测试覆盖。
- 探测只跑了四个项目（p075 p024 p038 p074），未全量回放。
- 第四轮对照中 issue 计数混入了并行子代理对 rules.py 的改动；M1 与 M1+M2 之间的对比不受影响（两快照 rules.py 相同）。
