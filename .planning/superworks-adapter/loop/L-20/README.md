# L-20：SW 补充线组（GWSW）前移对候选阶段的影响评估

只读离线评估，数据 `.tmp/superworks_round12_full`（77 项目）。未改 src、未回放、未 git。脚本与结果见 `tools/`。

## 1. 当前数据流
```
extract_cad_artifacts -> lines / texts / superworks(ports, wire_contacts, connect_labels, strip_rows)
pipeline.py 路由循环
  _extract_pairs_for_route (page_extractors.py:140)
    build_line_groups            旧链线组
    build_terminal_candidates    candidates.py:154，page_extractors.py:168 调用  <- 只见旧链线组
    build_pairs                  pairs.py:22（单侧/双侧、_scope_* 作用域）
    路由专用补充 + shadow_*       wire / component / terminal 各自的 pass
pipeline.py: table 路由 -> extract_superworks_pairs（路由后仅调用一次，superworks_extractor.py:683）
  L707-734 GWSW 生成；L752+ 逐组 SW 替换；L872 补充线组替代旧链；L1043 单侧补全
  -> accessory -> supersede_* 去重 -> mark_* -> 审计
```
GWSW 只依赖 lines、SW 接触集合及旧链线组成员/几何（仅作"旧链是否已建"的排除条件），不依赖候选与配对；它在候选阶段之后才追加，候选阶段因此看不到它。

## 2. 方案对比（合格数字候选 52770，存量配对 167623）
| 方案 | 改动 | 候选拒绝 | 直接消费配对 review/discard | pass 受影响 | 9 条命中 |
|---|---|---|---|---|---|
| Z 基线（Z-6 规则，只见旧链） | candidates.py | 4646（8.8%） | 1608（573/1035） | 直接 0；重放提升 1 | 0/9 |
| A 前移 SW 接触导线端点 | pipeline 生成集合；page_extractors 透传；candidates 新分支 | 6107（11.6%） | 2579（1054/1525） | 0 | 9/9 |
| B 全部原始导线端点 | 同 A，端点取 lines 全集 | 7374（14.0%），歧义跳过 29249 | 3482（1607/1875） | 直接 0；重放提升 3 | 9/9 |
| C 前移 GWSW 生成到路由内 | 拆出 superworks 生成函数 | 未评估 | 未评估 | 未知 | 预计 9/9 |
| D SW 标签绑定 | sw_ports.label | — | — | — | 不适用 |

- D 不适用：13 不是任何 SW 端口的 label（同元件 pin 1/2 为"内部元件"，label 未解析）。
- C 风险高：GWSW 共 57177 组（占终态线组 44%），会进入候选与 build_pairs，改变 SW 替换所依赖的 pairs_by_group 语义。

## 3. 推荐：方案 A
- 候选阶段只读上下文 `sw_contact_keys = {(sheet_id, wire_handle)}`，与 superworks_extractor.py:711 同口径；GWSW 生成与替换逻辑不改。
- 判据：数字候选、无物理绑定；半径 R=1.5×字高内的他线端点只属一条他线，且最近距离 f ≤ 本端距离/3 时拒绝（reason `label_bound_to_other_wire_endpoint`）。排除本组成员线。
- 依据：9/9 命中；直接与重放的 pass 变化均为 0；拒绝数比 B 少 1267。
- 改动：pipeline.py（路由循环前生成集合）；page_extractors.py（4 个 extract_* 加可选参数，经 _extract_pairs_for_route 传入 candidates.py:168）；candidates.py（L238 分支之后新增）。

## 4. 离线验证（方案 A）
- 9 条目标（均为 review）：该线两端的数字候选（选中的 9.07 与另一个 13.5–15.4）全部被拒，他线端点距离 1.55–1.61，比值 ≤0.18。Z 不命中，与 Z-6 一致。
- 重放 build_pairs 后 9 条全部变为 discard（两端无数字候选，另一端 CAD 物理端子按 _scope_wire_logic 剔除）。非 Z-6 预期的"缺端 review"。
  涉及：p064 PW0295；p067 PW0063/0065；p072 PW0111/0113/0119；p073 PW0096/0098/0104。
- pass 逐条：直接消费的 pass 为 0；455 条 SW 自有 pass（无候选 id）不受影响；重放提升 0。
- 额外影响（忠实口径，2579 条存量候选链接配对）：review→discard 940，discard→review 738，review→review 210，discard→discard 691；净 review −202、discard +202。
- 边界：A 拒绝中 593 条比值在 0.25–0.33；收紧为 f ≤ 本端/4 则拒绝 5514 条，9 条仍命中。校准：Z 口径重放的配对变化数与 Z-6 生产探测（5 项目）完全一致。

## 5. 限制与待决策
- 重放只到 build_pairs，未含 SW 替换、mark_*、去重；A 尚无生产探测。
- 同一物理导线拆成多个旧链组时，本组外的同线段可能被误判为他线（未验证）。
- 决策：(1) 9 条由 review 转 discard 是否接受；(2) discard→review 的 +738 复审量是否接受。
- 下一步（经批准）：实现 A，仅对 p000/p064/p067/p072/p073 做单项目探测。
