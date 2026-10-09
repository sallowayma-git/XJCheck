# 第四轮 D：R-MANY-TO-ONE 643 条分桶与根因（只读分析）

范围：round3 全量（643 条）对照基线（13 条）。src 只读，未改代码，未全量回放。修复效果为内存反事实模拟，需实施后用单元测试与全量回放复核。

## 1. 规则机制摘要（rules.py `_run_many_to_one`，1086 起）
- 分组键：`build_pair_graph` 按**原始右值字符串**分组（graph_builder.py:21）；左值去重只在早退处用规范化身份 `_terminal_endpoint_identity`（rules.py:3097，去非字母数字并大写）。
- 早退：有效左值（去桥接 claim）≤1 → 不报（1100）。
- 依次豁免（任一命中即不报）：串联链 `is_cross_view_terminal_series_chain`（1102）→ 同页数字三列（1107）→ 跨视图同一连接（1112）→ 结构化基数（1117）→ 组件-端子表跨图（1119，要求 len==2）→ 相邻表头 reciprocal 链（1125）→ reciprocal 物理簇（1131）→ XJDZ 实例脚（1137）。
- 仍未豁免则分类为 review：端子表共享端点 normal（1139）、逗号拆分组件（1171）、同页 strip 双端口（1203）、背板/端子+组件结构化（1225，即 `many_to_one_classification` 三类）；其余为通用「多对一配对」。
- 643 与 13 条：用 pairs.parquet 重建 Pair 并调用同一谓词，与真实规则输出逐项一致（0 项目不一致）。

## 2. 根因（全部为 round3 SuperWORKS 证据形态或身份变化导致基线豁免失效）
- 643 条中 630 条在基线中无同右值 FLAG；按成员对照分为：357 条「基线已豁免、左身份相同、SW 版失去豁免」（回归）；128 条基线无组、新增 SW 左端点；145 条基线已有组、新增左端点后失豁免；13 条基线即 FLAG。
- 修复累积归因（643 条，按上述顺序首次消除）：A 144、C 111、B 54、E 113、D 50、H 23、S+T 30、G 12、J 77，残余 29，新增 0。

## 3. 35 个桶（round3_composition 签名）结论摘要（全表见 buckets.json）
| 桶(rank) | 数量 | 结论 | 修复 | 修复后残余 |
|---|---:|---|---|---:|
| 1 背板表 + SW端子表行(sw_side=left) | 127 | 误报（回归） | A | 0 |
| 2 SW元件连接线 + SW端子表行 | 84 | 误报（回归） | C, A | 0 |
| 3 背板表 + SW原理图端子-端子跨接 | 69 | 合法（端子跨接） | E | 0 |
| 4 SW端子表行×2（同页两表头同端子） | 53 | 误报（回归）+GND 合法 | D；公共地白名单 | 2 |
| 5 旧strip元件 + SW元件连接线 | 51 | 误报（回归） | B | 0 |
| 6 背板表 + SW元件连接线 | 45 | 误报（回归） | C | 2（基线已报） |
| 7 背板表 + SW连接线 + SW原理图连线 | 29 | 合法（端子两侧接线+跨接） | J | 0 |
| 8 背板表 + inline元件 + SW连接线 | 23 | 误报（回归） | H | 0 |
| 9 背板表 + SW表行 + SW端子段跨接 | 21 | 合法（端子段短接） | G, J | 0 |
| 10 SW表行 + SW端子-端子跨接 | 21 | 合法（端子跨接） | E | 0 |
| 11 晶格 + SW连接线×2（串联节点） | 20 | 误报（串联链回归） | S+T | 0 |
| 15 晶格 + SW连接线 + SW表行 + SW连线 | 10 | 待复核 | 需扩展串联链 | 10 |
| 19 SW连接线 + SW表行×2（同端子 KD23） | 6 | 待复核（疑似真实） | 人工核对 | 6 |
其余 22 个桶均为 1–12 条：A/B/C/D/E/G/H/J 同类，合计已在 buckets.json。

## 4. 修复方案（改哪里）
- A（144）SW 端子表 sw_side=left 行写成旧链同形，或增加 endpoint_column；同步 `_superworks_structured_source_kind`（rules.py:4040）。
- C（111）SW 连接线补写旧链 `submode`；或 rules.py:4030 接受 `component_submode=='superworks_connect_line_port'`。
- B（54）`_is_authoritative_component_mapping_pair`（rules.py:3190）增加 SW 连接线分支，调用 `_authoritative_superworks_component_identity`。
- E（113）SW 端子-端子连线补写 `terminal_short_bridge=true`，使 `_is_terminal_strip_bridge_claim`（rules.py:716）命中。
- D（50，上界）SW 端子表行补写 has_shuoming_column/shuoming_text_id（候选 sw_strip_rows.potentials，需核对）。
- H（23）inline 豁免对 schematic 身份去重（rules.py:1962）；2006 起接受 SW 连接线身份。
- S+T（30）series_chains.py：SW 连接线子模式加入 _PORT_OWNER_SUBMODES 与 corroboration 对（:19-33）；唯一性键加入 component_submode（:155）。两者须同时做。
- G（12）effective_lefts（rules.py:1095）扣除被桥接段覆盖的端子（支持 7UD16~18 类段号）。
- J（77）豁免判定先全量，失败后用去桥接子组再判（rules.py:1117-1137），只增加豁免，不新增标记。
- 公共地（GND/xGDn）白名单：新增配置项（残余 9 条）。

## 5. H1–H4 数量化证据
- H1 不成立：全部为端子页的 issue 61 条，单页 53 条；多页 8 条均为两张端子图页（TD+TD）；端子图与端子表同时出现 0 条。
- H2 成立（已知合法模式）：右值为装置脚（如 2-1n323 类）的 issue 300 条（47%）；基线同右值组 227 条已豁免、4 条 FLAG、69 条无组；其中 73 条含端子类端点。修复后该类残余 3 条。
- H3 部分成立：成员值形态（基线 vs 第三轮，同一文本端点）：左侧仅破折号差异 552；左侧裸脚号 30；右侧裸脚号 38（如 425 对 1-21n425）；值不同 61（左）与 67（右）。基线无组的 128 条中，79 条端点在基线无对应 pair，49 条端点存在但值不同；其中 113 条主因是 SW 端子-端子跨接（E）。
- H4 主因：A、C、B、E、D、J 等 SW 形态/身份/桥接语义问题，归因合计 549 条；残余 29 条中 GND 9、串联晶格 10、KD23 类 6、其它 4。

## 6. 结论与风险
- 643 条中未发现可确认的真实多对一冲突；残余 29 条（GND 9 建议豁免，晶格 10 与 KD23 类 6 待人工核对）。
- 修复后预计残余：约 20 条（去掉 GND 9 之后），新增 0。
- 风险：E、G、J 改变「桥接 claim 不计为独立接线」的语义，需评审；D 为上界；S+T 须成对实施；公共地白名单为新增配置。
- 文件：buckets.json（35 桶、机制、H 统计、残余 issue 列表）；examples.md（前 6 桶各 5 例，含全部相关 pair 明细）。
