# DEV-INT-DISCARD：装置端子与本装置内部元件的连接改为静默丢弃（含主线程更正）

分支 superworks-loop，基线 HEAD=3e3b2b6。未 commit、未 push。未改 V2 模块与 `symbol_port_proposal.py`，未加 PDF/OCR，判定无项目、句柄或取值特判。控制台 `PYTHONIOENCODING=utf-8`。

用户口径（2026-10-11）：装置内部连接（装置端子 ↔ 本装置内部元件）不需要进入匹配，静默抛弃即可。
主线程更正（同日复核）：另一端身份若为装置端子形态（同装置标签 + 纯数字脚号）是端子间的外部跨接线，不得丢弃；只有元件引脚形态、线圈、未登记块引脚才是装置内部连接。

## 0. 结论

1. **判定统一为一个函数**：`device_internal_verdict`（`audit/superworks_device_internal.py`），配对层与 DEV-INT 线级链接共用，只看元数据（类别、装置标签、身份），不看几何、项目或取值。
2. **更正后的丢弃结果（全量 77 项目，最终代码）**：丢弃 **1422** 条，全部 `discard_reason=device_internal`。
   - **pass 460 条**（`wire_component_mapping`，SW 线组路径）：另一端身份 `-DC` 406，`-I` 54，其他 0。逐条清单：`tools/pass_discards_full77.csv`。
   - **review 962 条**：`ordinary_pair` 579、`semantic_mapping` 355、`wire_component_mapping` 28。另一端为内部元件 950（身份为空 754、裸数字 196），线圈 12（裸数字）。
   - **装置端子形态的丢弃：0**（更正前为 186 条 pass，全部改为保留）。
   - 另一端身份为异标签名（如 `1QD39`，元件标签仍为 `1n`）的 4 条 pass：不属于任何丢弃形态，保留（`kept:other_identity_foreign`）。
3. **issue 前后**：全量 41 → 41，新增 0、消失 0。10 项目 10 → 10，新增 0、消失 0。非装置内部的配对状态变化为 0。
4. **覆盖率（全量，eligible 82680）**：剔除装置内部后严格 **81.29%**，剔除后含延续 **83.84%**。严格 63.49% → 62.94%，含延续 72.03% → 71.54%。换算见第 5 节。
5. **目视**：10 例（新样本，pass 6、review 4）。9 例能确认为装置端子接同页内部元件引脚；1 例（`p003` S0008 `8n804`，review，另一端无身份）在裁剪图中无法确认，列为待复核。

## 1. 改动文件

| 文件 | 改动 |
|---|---|
| `src/dwg_audit/audit/superworks_device_internal.py` | 新增公共判定 `device_internal_verdict(terminal, other)`，返回 `device_internal` 或第一个不成立原因。新增 `is_terminal_form(identity, label)`（装置标签 + 纯数字脚号，如 `1-21n332`）与 `_element_form`（标签 + `-` + 引脚或功能名，如 `1n-DC`）。`label_of` 公开。线级判定统计键为 `excluded:<原因>`。`build_device_internal_links` 新增可选参数 `element_identities`（元件端口的身份映射），元件身份取端口自身身份，否则取配对文字身份。删除 GAP2-S 的元件标识守卫，新增 `linked_element_identified` 计数。 |
| `src/dwg_audit/audit/superworks_extractor.py` | 新增 `_pair_end`、`_discard_device_internal_pairs`：准入之后、字典校验之前，对所有带 SuperWORKS 两端的非 discard 配对调用判定（两个朝向）。命中则 `status=discard`，`evidence.discard_reason='device_internal'`，`evidence.device_internal_discard` 记录原状态、端子身份与端口、另一端类别、标签、身份、端口与是否未登记。`build_superworks_issues` 跳过此类配对。 |
| `src/dwg_audit/extract/superworks_semantics.py` | `SuperworksData` 新增字段 `device_internal_discard_stats`。 |
| `src/dwg_audit/report/superworks_artifacts.py` | 端口覆盖表新增 `excluded_device_internal`、`device_internal_pair_ids`、`device_internal_overruled`；删除 `consumed_with_internal`。覆盖口径为 4 个视图。删除 `port_coverage_with_internal`、`with_internal`、`total`。DEV-INT 调用时从非 discard 配对收集元件端的文字身份（`element_identities`）。线级链接新增 `overruled_by_pair` 标记（端口被非 discard 配对占用时为真，链接仅作审计）。strip 对照跳过装置内部丢弃的配对。summary 的 `device_internal` 段新增 `pair_discards`、`excluded_device_internal_ports`、`overruled_by_external_pair_ports`。 |
| `tests/unit/test_superworks_device_internal.py` | 守卫用例改为“仍为线级链接”；元件身份 fixture 由 `1n3` 改为元件形态 `1n-3`（`1n3` 按新规则是装置端子形态）。 |
| `tests/unit/test_superworks_device_internal_discard.py`（新增，39 项） | 判定各原因（含装置端子形态、异标签身份、线圈与未登记块、裸数字与空身份）；形态函数参数化；配对丢弃与保留；DEV-INT 身份映射；丢弃配对不产生 issue；外部配对否决线级链接（`overruled_by_pair`）。 |

全量单元测试（最终代码）：`python -m pytest tests/unit -q` → **2044 passed, 1 skipped**（基线 2005，新增 39）。

## 2. 判定规则（`device_internal_verdict`，最终版）

终端端（装置端子）须满足：类别 `装置端子`；装置标签已解析且非空；身份以装置标签开头且之后有脚号（`1n705` 对 `1n`）。

另一端判定：

1. 另一端类别为 `内部元件` 或 `线圈`，或为未登记 SYMB2 块引脚（无端口）。
2. 标签已解析，且与装置标签大小写不敏感地相等（`1-1n` 与 `1n` 不相等）。
3. **线圈与未登记块引脚**：直接判为装置内部，不看身份。
4. **内部元件**，按身份形态分：
   - 身份为**装置端子形态**（装置标签 + 纯数字，`1-21n332` 对 `1-21n`）→ `other_identity_terminal_form`，**不丢弃**（端子间跨接线）。
   - 身份为**元件形态**（装置标签 + `-` + 引脚或功能名，`1n-DC`、`3-4n-I`、`1n-3`）→ 装置内部，丢弃。
   - 身份为**空**或**裸数字**（如 `707`，无标签的元件引脚号）→ 未识别的元件引脚，按装置内部处理（与目视样本和 DEV-INT 一致）。
   - 身份为**其他异标签名**（如 `1QD39`，元件标签为 `1n`）→ 不属于任何丢弃形态，`other_identity_foreign`，保留。

身份取值优先级（配对层与 DEV-INT 一致）：端口自身 `endpoint_identity` → 配对的 SW 侧值 → 配对的裸值。端子侧同样如此（ordinary 配对的裸数字 `719` 不能代表 `1n719`）。

## 3. 更正过程（主线程复核）

主线程复核指出：650 条被丢弃的 pass 中有 186 条是同一装置两个端子之间的连接（如 p006 `1-21n532`↔`1-21n332`、`1-21n331`↔`1-21n232`，p005 `4n702`↔`4n401`），另一端身份为装置端子形态，SW 类别只是标成了内部元件。这是背板跳线/端子间短接线（装配时接的外部导线），接错是真实问题，不得静默丢弃。

处理：
- `device_internal_verdict` 增加装置端子形态规则（仅对 `内部元件` 生效；线圈与未登记块不受影响）。
- DEV-INT 线级判定同样应用：另一端身份为装置端子形态的线级链接不剔除。元件身份的来源见第 1 节 `element_identities`。该身份在 SW 端口上不存在（186 条的元件端口身份均为空），只存在于配对文字中，因此需要从配对层取值。
- 主线程要求以外的一处补充：另一端为异标签名（`1QD39` 等 4 条 pass）不符合任何丢弃形态，同样保留（判定为“不能归入任何丢弃形态”）。
- 线级链接若被非 discard 配对占用，标记 `overruled_by_pair`。

## 4. 丢弃数分类（全量，按另一端身份形态）

| 原状态 | 配对种类 | 另一端类别 | 身份形态 | 丢弃数 |
|---|---|---|---|---:|
| pass | wire_component_mapping | 内部元件 | `-DC` | 406 |
| pass | wire_component_mapping | 内部元件 | `-I` | 54 |
| pass | wire_component_mapping | 内部元件 | 其他 | 0 |
| review | ordinary_pair / semantic_mapping / wire_component_mapping | 内部元件 | 空 | 754 |
| review | ordinary_pair / semantic_mapping / wire_component_mapping | 内部元件 | 裸数字 | 196 |
| review | ordinary_pair / semantic_mapping / wire_component_mapping | 线圈 | 裸数字 | 12 |
| **装置端子形态** | — | — | — | **0** |
| **合计** | | | | **1422**（pass 460，review 962） |

更正前（主线程复核前）为 1612 条（pass 650）。减少的 190 条 = 186 条装置端子形态 pass + 4 条异标签名 pass。

保留（未丢弃）的装置端子侧配对，按原因计数（`pair_discards` 的 `kept:*`，端子侧计数）：
- `kept:other_identity_terminal_form` 186：端子间跨接线（主线程要求）。
- `kept:other_identity_foreign` 4：异标签名身份（第 3 节）。
- `kept:other_end_category:端子` 15978、`kept:other_end_category:装置端子` 2542、`kept:other_label_differs` 2001、`kept:other_end_category:none` 555、`kept:other_end_category:接地` 99、`kept:other_label_unresolved` 16、`kept:terminal_label_unresolved` 5。

PIN-1 的 4802 条 review 丢弃 0 条；LOGGEN-2 的 review 与旧链 component 配对丢弃 0 条（全量中没有任何带 `sw_wire_route` 证据的丢弃，全部为 SW 元件端）。

## 5. issue 与覆盖率

### 5.1 issue

- 全量：41 → 41，新增 0、消失 0（逐条相同）。
- 10 项目：10 → 10，新增 0、消失 0。
- 非装置内部的配对状态变化：0。

### 5.2 覆盖口径定义

| 视图 | 分子 | 分母 |
|---|---|---|
| `strict` | 配对占用（非 discard） | eligible |
| `with_continuity` | 配对或跨页延续 | eligible |
| `strict_excl_device_internal` | 配对占用，且不在排除集 | eligible − excluded |
| `with_continuity_excl_device_internal` | 配对或延续，且不在排除集 | eligible − excluded |

`excluded_device_internal`：端口有线级链接或是丢弃配对的端子端，且没有非 discard 配对占用（被外部配对否决的端口不排除）。

### 5.3 全量（77 项目，eligible 82680）

| 口径 | 旧（round21，收紧前） | 新（最终） |
|---|---|---|
| 严格 | 52494 / 82680 = 63.49% | 52039 / 82680 = **62.94%** |
| 含延续 | 59551 / 82680 = 72.03% | 59149 / 82680 = **71.54%** |
| 剔除装置内部后严格 | — | 52039 / 64013 = **81.29%** |
| 剔除装置内部后含延续 | — | 53668 / 64013 = **83.84%** |
| 旧“含内部” / 旧“合计”（已删除） | 85.49% / 87.45% | — |

排除端口 18667（分母 82680 − 18667 = 64013）。被外部配对否决的端口 478。线级链接 18752 → 19084。

### 5.4 10 项目（eligible 8500）

| 口径 | 旧 | 新 |
|---|---|---|
| 严格 | 5909 / 8500 = 69.52% | 5867 / 8500 = 69.02% |
| 含延续 | 6466 / 8500 = 76.07% | 6427 / 8500 = 75.61% |
| 剔除后严格 | — | 5867 / 6891 = **85.14%** |
| 剔除后含延续 | — | 5925 / 6891 = **85.98%** |

10 项目丢弃 70（pass 42，review 28）。排除端口 1609。线级链接 1607 → 1643。

换算说明：
- 旧“含内部”把装置内部端口计为已覆盖。新口径中这些端口既不计覆盖也不计分母，因此两者不能直接比较。
- 严格口径下降是因为丢弃的配对不再覆盖端口。被外部配对否决的端口仍计为覆盖。

### 5.5 逐项目（10 项目，最终代码）

| 项目 | 可计端口 | 丢弃 配对（pass / review） | 排除端口 | 严格 旧→新 | 含内部(旧) | 剔除后严格(新) | 剔除后含延续(新) | 链接 旧→新 |
|---|---:|---|---:|---|---:|---|---|---|
| p001 | 663 | 18（6 / 12） | 144 | 447/663 → 441/663 | 585/663 | 441/519 = 84.97% | 450/519 = 86.71% | 149 → 154 |
| p003 | 378 | 6（4 / 2） | 68 | 260/378 → 256/378 | 323/378 | 256/310 = 82.58% | 263/310 = 84.84% | 66 → 70 |
| p022 | 747 | 20（6 / 14） | 190 | 456/747 → 450/747 | 640/747 | 450/557 = 80.79% | 471/557 = 84.56% | 207 → 209 |
| p044 | 1315 | 2（2 / 0） | 243 | 860/1315 → 858/1315 | 1101/1315 | 858/1072 = 80.04% | 858/1072 = 80.04% | 241 → 243 |
| p050 | 1134 | 0（0 / 0） | 215 | 678/1134 → 678/1134 | 893/1134 | 678/919 = 73.78% | 685/919 = 74.54% | 215 → 215 |
| p051 | 229 | 8（8 / 0） | 16 | 198/229 → 190/229 | 206/229 | 190/213 = 89.20% | 190/213 = 89.20% | 8 → 16 |
| p061 | 1931 | 24（24 / 0） | 479 | 1338/1931 → 1314/1931 | 1794/1931 | 1314/1452 = 90.50% | 1320/1452 = 90.91% | 457 → 464 |
| p071 | 200 | 4（4 / 0） | 10 | 150/200 → 146/200 | 156/200 | 146/190 = 76.84% | 149/190 = 78.42% | 6 → 10 |
| p074 | 1105 | 4（4 / 0） | 254 | 752/1105 → 748/1105 | 1002/1105 | 748/851 = 87.90% | 748/851 = 87.90% | 252 → 256 |
| p075 | 798 | 0（0 / 0） | 6 | 770/798 → 770/798 | 776/798 | 770/792 = 97.22% | 775/792 = 97.85% | 6 → 6 |

注：表中“旧”为 round21 的结果（收紧前）。10 项目数字来自上一次更正后的回放；本次最终代码的 10 项目丢弃与覆盖与之一致（该 10 项目中无异标签名或装置端子形态的变化）。

### 5.6 对 round21 的其它差异

- 2 条 p037 与 1 条 p072 review 配对的 `evidence` 数值浮点不同（`closed_polyline_enclosure` 的 bbox 与宽高，例如 265.0 ↔ 265.21）。这是并行全量回放中的既有现象（GAP2-S 已记录 p037 同类差异），与本切片的判定无关，状态与 issue 不变。

## 6. 目视

10 例样本（`tools/visual_sample_10.json`，种子 20261011，按原状态与配对种类分层）：

| 例 | 项目 | 配对 | 状态 | 端子 ↔ 另一端 | 判定 |
|---|---|---|---|---|---|
| 1 | p051 | wire_component_mapping | pass | 2-25nPWR2-4 ↔ 2-25n-DC | 能确认 |
| 2 | p022 | wire_component_mapping | pass | 1n114 ↔ 1n-DC | 能确认 |
| 3 | p003 | wire_component_mapping | pass | 8n114 ↔ 8n-DC | 能确认 |
| 4 | p022 | wire_component_mapping | pass | 1n112 ↔ 1n-DC | 能确认 |
| 5 | p022 | wire_component_mapping | pass | 1n112 ↔ 1n-DC | 能确认 |
| 6 | p061 | wire_component_mapping | pass | 2-21n105 ↔ 2-21n-DC | 能确认 |
| 7 | p022 | ordinary_pair | review | 1n526 ↔ 525（裸数字） | 能确认（同页继电器触点） |
| 8 | p001 | ordinary_pair | review | 1n906 ↔ 905（裸数字） | 能确认（同页标题 1n） |
| 9 | p003 | ordinary_pair | review | 8n804 ↔ 空身份 | **不能确认**，待复核（裁剪图中无元件标签） |
| 10 | p001 | semantic_mapping | review | 1n720 ↔ 空身份 | 能确认（同页继电器 UA 触点） |

截图：`png/DD_01.png`–`DD_05.png`（每张两例，宽图与端子本体近景）。单人判定，元件标签多数在图上不可见，同装置归属依据 SW 标签。

## 7. 泛化说明：新图纸遇到同样情况如何处理

### 7.1 判定依赖什么

只依赖元数据，不依赖块名、项目、句柄或取值：

- 装置端子身份结构：类别 `装置端子`，身份为“装置标签 + 脚号”，标签解析自 SW 标签文字。
- 另一端类别：SW 元件端为 `内部元件` 或 `线圈`；未登记 SYMB2 块引脚以其记录的装置名为标签。
- 另一端身份形态：装置端子形态（标签 + 纯数字）为端子间跨接线，不丢弃；元件形态（标签 + `-` + 引脚或功能名）为装置内部，丢弃；空身份或无标签的裸数字为未识别的元件引脚，按装置内部处理；其它异标签名不丢弃。
- 线级判定（DEV-INT 链接，只用于覆盖口径，不用于丢弃）额外依赖导线线组、端子 TERMPOINT 与端子本体切分（GAP2-S）。

### 7.2 哪些情况会落入“未识别”，在哪里列出

产物位置：`findings/superworks_summary.json` → `device_internal`。

- 配对层 `pair_discards` 中的 `kept:*`（见第 4 节）。最需要复核的是 `kept:other_end_category:none`（555，另一端无类别）与 `kept:other_identity_foreign`（4，异标签名）。
- 线级层 `stats`：`excluded:wire_multi_end`（一根线上多个端口）、`excluded:wire_no_other_port` 与 `unregistered:no_far_pin`（单端线找不到远端未登记引脚）、`excluded:multiple_internal_wires`、`excluded:identity_missing`、`excluded:label_unresolved`、`split_refused:components_not_two`（870，三四段线组未切开）等。
- 否决与审计：`sw_port_coverage.parquet` 的 `device_internal_overruled`（478）；`sw_device_internal_links.parquet` 的 `overruled_by_pair`（463）；`sw_unregistered_pin_decisions.parquet`；`sw_unregistered_symb2.parquet`；`sw_terminal_splits.parquet`。

### 7.3 新图纸的处理步骤

1. 看 `kept:other_end_category:none`：另一端无法归类，抽样目视。
2. 看 `kept:other_identity_foreign`：异标签名身份，判断是否为元件标签写错或真正的外部连接。
3. 看 `excluded:wire_multi_end` 与 `split_refused:components_not_two`：导线合并与多段线组是主要盲区，需要单独规则，不应放宽线级判定。
4. 看 `device_internal_overruled`：同线有未登记引脚等线级盲区。
5. 标签写法不同但实际同装置（如 `1-1n` 与 `1n`）现行规则计为 `other_label_related` 不匹配，需要人工确认后再决定。

## 8. 需要用户决定的事项

- **裸数字与空身份的元件端（962 条 review）**：按现行规则视为元件引脚并丢弃。目视样本中 9 例能确认，1 例（#9）不能确认。这一大类是否接受，需要用户确认；如不接受，应改为保留并列为“元件引脚未识别”。
- **异标签名身份（4 条 pass）**：现行规则保留。需用户确认是否应视为外部连接。

## 9. 产物与复现

- `tools/devdisc_compare.py`：两次回放的对比。
- `tools/compare_10proj.json`、`tools/compare_full77.json`：对比结果。
- `tools/discards_10proj.json`、`tools/discards_full77.json`：每条丢弃的记录。
- `tools/pass_discards_full77.csv`：460 条 pass 丢弃的逐条清单。
- `tools/devdisc_visual.py`、`tools/visual_sample_10.json`：目视样本。
- `png/DD_01.png`–`DD_05.png`：10 例截图。
- 回放目录：`.tmp/superworks_round22_full`（全量，最终代码）；快照 `.planning/superworks-adapter/round22_full_src`。

复现：
- 10 项目：`python .planning/superworks-adapter/replay.py --output .tmp/loop_devdisc --snapshot .tmp/loop_devdisc_src --workers 3 --projects p001 p003 p022 p044 p050 p051 p061 p071 p074 p075`
- 全量：`python .planning/superworks-adapter/replay.py --output .tmp/superworks_round22_full --snapshot .planning/superworks-adapter/round22_full_src --workers 3`
- 对比：`python .planning/superworks-adapter/loop/DEV-INT-DISCARD/tools/devdisc_compare.py .tmp/superworks_round21_full .tmp/superworks_round22_full OUT.json --discards-json OUT_discards.json`
- 目视：`python .planning/superworks-adapter/loop/DEV-INT-DISCARD/tools/devdisc_visual.py RUN DISCARDS.json PNG_DIR SAMPLE.json 10 20261011`

## 10. 限制

- 截图只覆盖 10 例，不是每条 pass 都有截图。全部 460 条 pass 的逐条清单见 CSV。截图上限 15 张。
- 目视为单人判定，未做双人复核。
- 旧基线 round21 为收紧前代码，线级链接相差 106 条（GAP2-S 第 4.2 节）。覆盖率新旧对比已注明此差异，配对与 issue 不受影响。
- 外部配对否决与身份形态规则是对 DEV-INT 线级盲区的补偿，不是对其根因的修复。
