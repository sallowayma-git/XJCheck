# 第五轮 N：撤销后的端口回落身份（N1）与标签+端口号的原理图佐证（N2/N3）

范围：修改 `src/dwg_audit/extract/superworks_semantics.py`（N1）、`tests/unit/test_superworks_round5_producer.py`（新增 6 项 N1 测试）。未改 rules.py、series_chains.py、superworks_extractor.py 或其他文件；未提交；未删除文件；未全量回放（只跑 p075 p024 p038 p074）。未实施 N3 中的 (c)。

快照与产物：
- N1 快照 `.planning/superworks-adapter/round5N_src`（当前 src 副本）；探测输出 `.tmp/round5N_probe`；探测日志 `.tmp/round5N_probe_stdout.txt`。
- N2 脚本与结果：`round5/N/n2_corroboration.py`（主计算，输出 `n2_probe_summary.json`、`n2_probe_rows.json`（4 项目）与 `n2_all_summary.json`（77 项目 a/c））；`round5/N/n2_controls.py`（对照与 a/c 交叉表，输出 `n2_controls.json`）；N1 前后对比 `round5/N/n1_probe_compare.json`（由一次性内联脚本读取两组 parquet 生成，数字可由 findings 重算）。
- 对比基线：第四轮 `.tmp/superworks_round4_full`；M1+M2 `.tmp/round5M2_probe`。M1+M2 快照 `round5M2_src` 与当前 src 的 rules.py、series_chains.py、superworks_extractor.py、text_geometry.py、superworks_artifacts.py 逐字节相同，只有 superworks_semantics.py 不同（即 N1），因此 N1 与 M2 的对比是干净的。

## 0. 结论

| 项 | 状态 |
|---|---|
| N1 根因 | 已定位：`superworks_semantics.py` 第 340-341 行（修改后为 351-352 行），撤销后 pin 无 normalized 值，身份组装得 None；TERMPOINT 端口号从未参与身份组装 |
| N1 修复 | 已实施：撤销端口回落为 `标签 + normalize(端口号)`（无连字符），pin 记 `pin_resolution_method="termpoint_number_fallback"` |
| N1 p024/p038/p074/p075 component_mapping | 恢复到第四轮水平：249 / 357 / 235 / 324（M1+M2 为 119 / 167 / 117 / 320） |
| N1 p075 R-ONE-TO-MANY | 0（保持；第四轮 64） |
| N1 p074 R-MANY-TO-ONE | 0（保持；第四轮 48） |
| N2 (a) 第四轮身份佐证率（4 项目） | 3.8%（42 / 1103） |
| N2 (b) N1 回落身份佐证率（4 项目） | 56.2%（620 / 1103） |
| N2 (c) 全部 nearest 改用标签+端口号（4 项目） | 64.4%（710 / 1103）；77 项目 (a) 4.3%、(c) 66.0% |
| N3 | 触发条件满足（(c) 比 (a) 高 60.6 个百分点），但不建议直接实施 (c)，见第 6 节 |
| `pytest tests/unit -q` | 1678 passed, 1 skipped（M 轮为 1672 passed） |

## 1. N1 根因

撤销路径（`_definition_ports`，第 231 行）把同名采纳的端口的 pin 替换为 `{"resolved": False, "nearest_rejected": {...}}`，端口号（`ports[i]["number"]`）保留在 `number` 中，但身份组装只使用 pin 的规范化值：

- 原第 340 行：`pin_value = pin.get("normalized") if pin.get("resolved") else ""`，撤销端口得到空串；
- 原第 341 行：`endpoint = (endpoint + ("" if category == "装置端子" else "-") + pin_value) if endpoint and pin_value else None`，空串导致 `endpoint = None`。

因此撤销后的端口 `endpoint_identity` 为 None。`_connect_labels` 与 `extract_superworks_pairs`（component_mapping 生成处）都只按 `endpoint_identity` 相等来匹配连接线标签与端口，None 使这些端口无法被任何连接线标签指认，component_mapping 丢失。

## 2. N1 实施

- `_terminal_identity(label_value, pin_value, joiner="")`：装置端子身份的组装式（`label + pin_value`，空值返回 None），原第 341 行改为调用它（语义不变：装置端子 joiner="", 其他 "-"）。
- `_revoked_adoption(pin)`：判定 `nearest_rejected.reason == "same_value_distinct_text"`。
- 回落（第 353-360 行）：仅当 `endpoint is None`、端口有 TERMPOINT 端口号、且该端口为撤销端口时，`endpoint = label + normalize(端口号)`（与装置端子 pin 值的规范化函数一致，无连字符）；pin 记 `pin_resolution_method="termpoint_number_fallback"` 与 `fallback_identity`。
- pin 的 `resolved` 保持 False：不伪装成已解析的 pin，`independent_pin_verification` 保持 False；`corroborate_internal_pin_identities` 的 strip 反向佐证检查照常执行（有佐证的 `label-number` 形式仍优先，既有行为）。
- 范围：只作用于撤销端口；未撤销且无 pin 的端口仍为 None（未扩大范围）；`category == "端子"` 的端子条不变。
- 证据：component_mapping 的 `evidence.pin_resolution_method` 由 pin 派生，因此记录为 `termpoint_number_fallback`（探测中连接线端口计数 130 / 190 / 196 / 118，见第 4 节）。
- 无规则名、块名或值的特判。

## 3. N1 测试

`tests/unit/test_superworks_round5_producer.py` 新增 6 项：
- `_terminal_identity` 的拼接与空值；
- 部件端口（LDPARTLAYT_PART）的撤销端口得到 `1n401 / 1n501 / 1n601`（无连字符），pin 记 `termpoint_number_fallback`，`resolved` 为 False；
- 符号端口（装置端子、内部元件，参数化 2 项）得到同样的回落身份；
- 端口号重复（"1","1","1"）保留采纳身份 `1n-02`，不记 fallback；
- 未撤销的不同文字端口保持 `1n-01 / 1n-02 / 1n-03`。

`pytest tests/unit/test_superworks_round5_producer.py -q`：18 passed。`pytest tests/unit -q`：1678 passed, 1 skipped。

## 4. N1 探测（四项目）

| 项目 | 指标 | 第四轮 r4 | M1+M2 | N1 |
|---|---|---|---|---|
| p024 | pairs / component_mapping / table_mapping | 1842 / 249 / 416 | 1712 / 119 / 416 | 1842 / 249 / 416 |
| p024 | 连接线端口 pin 方法 | nearest 210 | nearest 80 | fallback 130，nearest 80 |
| p024 | issues | 3（R-MANY-TO-ONE 2，R-SUPERWORKS-CONFLICT 1） | 3 | 3（同 r4） |
| p038 | pairs / component_mapping / table_mapping | 2474 / 357 / 554 | 2284 / 167 / 554 | 2474 / 357 / 554 |
| p038 | 连接线端口 pin 方法 | nearest 294 | nearest 104 | fallback 190，nearest 104 |
| p038 | issues | 2（R-MANY-TO-ONE 2） | 0 | 0 |
| p074 | pairs / component_mapping / table_mapping | 2263 / 235 / 660 | 2145 / 117 / 660 | 2263 / 235 / 660 |
| p074 | 连接线端口 pin 方法 | nearest 162 | nearest 44 | fallback 118，nearest 44 |
| p074 | issues | 48（R-MANY-TO-ONE 48） | 0 | 0 |
| p075 | pairs / component_mapping / table_mapping | 2334 / 324 / 312 | 2330 / 320 / 312 | 2334 / 324 / 312 |
| p075 | 连接线端口 pin 方法 | nearest 316 | nearest 120 | fallback 196，nearest 120 |
| p075 | issues（R-ONE-TO-MANY / R-PAIR-MISSING-SIDE / R-MANY-TO-ONE） | 135（64 / 70 / 1） | 71（0 / 70 / 1） | 71（0 / 70 / 1） |

说明：
- N1 对 component_mapping 的恢复是精确的：四个项目的数量与第四轮完全相同，且 table_mapping 未变。
- 连接线端口身份数量：p024 中 227 条连接线端口在 r4 只有 147 个不同左端身份（"1n-02" 同时映射到 1XD7、1KLP14-2 等 10 个端口），N1 后 227 条有 226 个不同左端身份（如 `1n101 -> 1XD3`、`1n102 -> 1XD7`）。
- issues 对比：p038、p074 相对第四轮的下降来自 M2（端子排行同排/跨排标记）；N1 本身没有改变 issue 数（N1 与 M2 的 issue 相同）。
- 装置端子 category 端口（sw_ports）在四个项目中没有任何回落（回落只出现在部件端口），因此 `unresolved_pin_text` 的原因码对符号端口仍然存在；本轮未处理。
- R-TABLE-MAPPING-SOURCE-CONFLICT、R-CROSS-PAGE-CONFLICT 在四个项目的 N1 输出中均未出现（计数为 0）。

## 5. N2 佐证率

方法（`round5/N/n2_corroboration.py`）：

- 人口：第四轮 component_mapping 中 `component_submode == superworks_connect_line_port` 的端口（按 port_id 去重），四项目共 1103 个。
- 三种身份：
  - (a) 第四轮身份（sw_part_instances 中该端口的 endpoint_identity，如 `1n-02`）；
  - (b) N1 身份（同一 port record_id 在探测输出中的 endpoint_identity，如 `1n102`；未撤销的端口与 (a) 相同）；
  - (c) 对全部 definition_text_nearest 端口改为 `标签 + normalize(端口号)`，其他端口保持 (a)。
- 佐证：该身份（大小写不敏感）出现在同项目的二次原理图页（pages.sheet_category == 二次原理图）上的 `装置端子` sw_ports 或 sw_symbols 的 endpoint_identity 中，或出现在同页的非 SuperWORKS 生产 pairs 的左右端值中。SuperWORKS 来源的 pairs 被排除，以免 component_mapping 自我佐证。四项目每个项目的佐证值数量：p024 500、p038 456、p074 447、p075 662（9–13 张二次原理图页）。

### 5.1 按项目汇总（4 项目）

| 项目 | 人口 | (a) 命中 / 率 | (b) 命中 / 率 | (c) 命中 / 率 | 撤销端口数 |
|---|---|---|---|---|---|
| p024 | 226 | 10 / 4.4% | 139 / 61.5% | 137 / 60.6% | 129 |
| p038 | 324 | 18 / 5.6% | 153 / 47.2% | 143 / 44.1% | 189 |
| p074 | 229 | 14 / 6.1% | 132 / 57.6% | 126 / 55.0% | 118 |
| p075 | 324 | 0 / 0.0% | 196 / 60.5% | 304 / 93.8% | 196 |
| 合计 | 1103 | 42 / 3.8% | 620 / 56.2% | 710 / 64.4% | 632 |

77 项目（只有 (a)、(c)，因 (b) 需要探测结果）：人口 18718；(a) 813 / 18718 = 4.3%；(c) 12344 / 18718 = 66.0%。

### 5.2 对照（确定 (c) 的佐证是否有区分力；数字由 `n2_controls.py` 复算）

- 跨标签对照（同项目内，把 nearest 端口的端口号拼到另一个随机标签上）：44 / 980 = 4.5%。与 (a) 的 3.8% 接近，说明标签维度对佐证有很强的区分力。
- 同标签内端口号错位对照（同一部件内，把标签与别的端口号拼接）：694 / 949 = 73.1%（p024 68%、p038 51%、p074 73%、p075 96%）。

结论：(c) 的高佐证率主要来自"标签存在、且标签+端口号的格式与原理图装置端子一致"；同标签内换端口号仍会大概率命中，因此该指标无法证明某个具体端口号是正确的。(a) 的低佐证率很可能是格式问题："标签-脚号"几乎不出现在原理图身份中（26 个 (a) 命中的端口仍说明该格式偶尔正确，见 5.3）。

### 5.3 (a) 与 (c) 的逐端口交叉（4 项目，1103 个）

| 分组 | 人口 | a 与 c 都命中 | 仅 a 命中（改用 c 会丢失） | 仅 c 命中（改用 c 会获得） | 都不命中 |
|---|---|---|---|---|---|
| 全部 | 1103 | 16 | 26 | 694 | 367 |
| 撤销端口（definition_text_nearest，撤销） | 632 | 0 | 0 | 578 | 54 |
| 未撤销 nearest 端口 | 348 | 0 | 26 | 116 | 206 |

未撤销的 nearest 端口上，改用 (c) 净增 90 个佐证，但丢失 26 个原本正确的标签-脚号身份，例如 p038 `1-2KLP5-2`（(a) 命中）在 (c) 下为 `1-2KLP52`（未命中）。

### 5.4 十个样例

抽样方法：四项目全部 nearest 端口（980 个）用随机种子 11 抽 10 个，结果如下（"佐证"列为是否命中）。

| # | 项目 | 标签 | 端口号 | 撤销 | (a) 第四轮身份 | 佐证 | (b) N1 身份 | 佐证 | (c) 标签+端口号 | 佐证 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | p038 | 1-2ZLP1 | 2 | 否 | 1-2ZLP1-2 | 否 | 1-2ZLP1-2 | 否 | 1-2ZLP12 | 否 |
| 2 | p075 | 2-26n | 807 | 否 | 2-26n-串口4+ | 否 | 2-26n-串口4+ | 否 | 2-26n807 | 是 |
| 3 | p074 | 2-25n | 204 | 是 | 2-25n-04 | 否 | 2-25n204 | 是 | 2-25n204 | 是 |
| 4 | p075 | 2-26n | 526 | 是 | 2-26n-B码13- | 否 | 2-26n526 | 是 | 2-26n526 | 是 |
| 5 | p075 | 2-26n | 611 | 是 | 2-26n-B码6+ | 否 | 2-26n611 | 是 | 2-26n611 | 是 |
| 6 | p075 | 1-26n | 616 | 是 | 1-26n-B码8- | 否 | 1-26n616 | 是 | 1-26n616 | 是 |
| 7 | p038 | 1-2KLP5 | 2 | 否 | 1-2KLP5-2 | 是 | 1-2KLP5-2 | 是 | 1-2KLP52 | 否 |
| 8 | p038 | 1-2ZLP1 | 1 | 否 | 1-2ZLP1-1 | 否 | 1-2ZLP1-1 | 否 | 1-2ZLP11 | 否 |
| 9 | p074 | 1-25n | 216 | 是 | 1-25n-16 | 否 | 1-25n216 | 是 | 1-25n216 | 是 |
| 10 | p075 | 2-26n | 524 | 是 | 2-26n-B码12- | 否 | 2-26n524 | 是 | 2-26n524 | 是 |

第 1、8 号样例说明：未撤销的端口，(c) 的身份也未被原理图佐证，而 (a) 同样未被佐证，两者都不能确认。第 7 号样例说明 (c) 会丢失正确的标签-脚号身份。

## 6. N3 建议（未实施）

触发条件满足：(c) 比 (a) 高 60.6 个百分点（4 项目），77 项目高 61.7 个百分点。但是不建议据此直接对全部背板端口改用 (c)：

1. 未撤销的 nearest 端口上，(c) 丢失 26 个 (a) 的正确佐证（第 7 号样例类），净增仅 90 个，且这些端口的端口号是否正确无法由本指标判定。
2. 佐证率对端口号不敏感（同标签内换端口号对照 73.1%），因此它只证明"标签+端口号"这一格式在原理图中存在，不能证明端口号归属正确。
3. 若以佐证结果挑选身份（例如 (a) 佐证则用 (a)、否则 (c) 佐证则用 (c)），佐证率会因构造而接近 100%，失去证据意义。

建议：先做端口号级的独立验证再决定。可行的验证是：对连接线标签（目的文字，如 `1XD7`）与 (c) 身份在原理图中的对端（装置端子所连的目的文字）是否一致进行计数。只有该计数显示 (c) 显著优于 N1 的回落身份（已覆盖撤销端口），才考虑对未撤销的 nearest 端口改用 (c)。本轮未做该验证，未修改任何代码。

## 7. 限制

- N1 的回落只覆盖撤销端口；未撤销、无 pin 的端口仍为 None，这部分在四个项目上没有数据显示需要回落。
- 装置端子 category 端口的撤销端口在四个项目中未出现；其 `unresolved_pin_text` 原因码仍保留，未调整。
- N2 的佐证是存在性检查（身份是否出现），不是对端一致性检查；第 5.2 节的对照说明它对端口号的区分力有限。
- N2 的 (b) 只在四个探测项目上计算（77 项目需要全量回放，超出本轮范围）；(a)/(c) 的 77 项目数字基于第四轮数据。
- 探测只跑了四个项目，未全量回放。
- 第四轮 issue 计数是用旧版 rules.py 生成的，与当前 rules.py 不完全可比；issue 的 N1 对比以同一 rules.py 的 M1+M2 快照为准（第 4 节表中 M1+M2 列）。component_mapping、table_mapping、pairs 只受生产端影响，可直接与第四轮比较。
