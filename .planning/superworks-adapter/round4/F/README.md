# 第四轮 F：SuperWORKS 生产者修复（F1–F6）

范围：只改 `superworks_extractor.py`、`superworks_semantics.py`、`text_geometry.py` 与新增测试文件。未改 rules.py、series_chains.py；未提交；未删除文件；未做全量 77 项目回放（仅 p024 p038 p061）。

## 0. 结论一览

| 项 | 状态 | 要点 |
|---|---|---|
| F1 端子排 sw_side=left 形态 | 已实施 | 只有连接所在侧写值与 text_id；column_roles 与旧链左侧行同形（见 §1） |
| F2 has_shuoming_column / shuoming_text_id | **未实施** | 旧链的「说明」是每张端子表的表头单元格，SW 元数据中没有任何指向它的引用（见 §2） |
| F3 同排/跨排契约字段 | 已实施 | `terminal_short_bridge` / `strip_header` / `terminal_cross_strip_link` / `strip_corroborated` / `strip_headers` / `strip_membership`（见 §3） |
| F4a 文字真实锚点 | 已实施 | TEXT 用 ezdxf 放置点（对齐点），MTEXT 按 attachment_point 换算到基线锚点（见 §4.1） |
| F4b 元件框内标记不作脚号 | 已实施（通用规则） | 同一定义实例内，候选距离不得超过其他已解析脚号最大距离的 1.25 倍；被多个端口共用的标签豁免（见 §4.2） |
| F4c 端口名与显示数字 | 已实施 | TERMPOINT 名（IN2）与显示数字（2）并存时记录别名，并参与 strip 反向比对（见 §4.3） |
| F4d 反向佐证脚号独立标记 | 已实施 | `pin_resolution_method`，`independent_verification=False`，不计入独立验证计数（见 §4.4） |
| F5 镜像块 WCS 坐标 | 已实施 | INSERT 位置与文字插入点均转为 WCS；p061 F019 / FE9B 的 stale_label_reference 消失（见 §5） |
| F6 文字宽度用样式宽度系数 | 已实施 | TEXT 优先实体 width，否则样式 width；MTEXT 用样式 width（见 §6） |

验证：新增 `tests/unit/test_superworks_round4_producer.py` 24 项全部通过；`pytest tests/unit -q -k "superworks or text_geometry or terminal_identity or table"` 249 项通过；`pytest tests/unit -q` 全量通过（结果见 §7）。3 项目重放（p024 p038 p061）：SW 端子对分类完整，两端都能判定同排或跨排；p061 stale_label_reference 由 2 降为 0；FEIDIAO 块 J1 错配消失；同规则（rules.py 相同）A/B 下问题数 10→3、9→2、15→4，配对集合逐条一致（§7）。

## 1. F1：sw_side=left 端子排行形态

修改：`superworks_extractor.py` 中 `extract_superworks_pairs` 的端子排行循环。原来先写 `right_value=destination` 再 `update` 当前侧，导致 sw_side=left 行两侧同时有值，且 `column_roles` 为 `left=empty, right=terminal_endpoint`。现在按连接侧构造：当前侧写 `{side}_value/_text_id/_coord`，另一侧为 `None`，`column_roles` 跟随侧别。

对照（同一端子排 S0019，项目 p024，旧链样例取自 p000 的 PTMR0006，同形的左侧行）：

| 字段 | 旧链 TableExtractor（PTMR0006，左侧行） | SW 修改前（round3，1-7XD1，左侧行） | SW 修改后（round4F，1-7XD1） |
|---|---|---|---|
| pair left_value / right_value | 1UD-1 / 1ZKK-2 | 1-7XD1 / 1XD3 | 1-7XD1 / 1XD3 |
| pair left_text_id / right_text_id | T2436 / T2437 | T3145 / T3146 | T3145 / T3146 |
| tm.left_value / left_text_id / left_coord | 1ZKK-2 / T2437 / [128.5, 268.5] | 1XD3 / T3146 / [221.0, 206.0] | 1XD3 / T3146 / [221.0, 206.0] |
| tm.right_value / right_text_id / right_coord | None / None / None | **1XD3 / T3146** / None | None / None / None |
| column_roles | left=terminal_endpoint, middle=row_number, right=empty, description=shuoming | left=empty, middle=row_number, right=terminal_endpoint, description=empty | left=terminal_endpoint, middle=row_number, right=empty, description=empty |
| has_shuoming_column / shuoming_text_id | True / T2435 | False / None | False / None（F2 未实施） |
| endpoint_column_authority | nearest_header_or_named_row | superworks_reciprocal_row_reference | 同左（SW 来源保留） |

结论：列角色、侧别与 text_id 字段与旧链同形。剩余差异只有 F2（说明列）和 SW 来源标记。

依赖：`rules.py` 的 `_superworks_structured_source_kind`（当前工作树版本）已改为按 `_table_endpoint_column_side` 判断端子列侧别，左侧行仍被识别为 structured。已用 p024/p038/p061 的配对对该函数逐条核对：左侧 119/145/260 条全部为 True，与修改前一致。若该函数回退为只认右侧，左侧行会丢失 structured 状态。

## 2. F2：未实施（有证据表明 SW 元数据没有对应字段）

旧链 `shuoming_text_id` 指向的是每张端子表表头行的「说明」文字（例：S0019 中 TEXT「说明」位于 (100.0, 273.75)，与表头「ZD」(63.5, 273.5) 同一行，句柄 BC8C）。该文字在同一表的所有行中都是同一个 text_id。

证据（p024，全部为 file 级限定的句柄比对）：

1. 旧链 28 个 `shuoming_text_id`（按文件限定句柄）在全部 XDATA 中的引用数为 **0**（逐实体扫描 DXF 缓存的 modelspace 与所有 block 的 xdata）。
2. 同一 sheet 的 SW 端子排行行（`sw_strip_rows`）中，`raw_xdata` / `connections` / `potentials` / `header` / `row` 任一字段引用这些句柄的数量为 **0**（p024、p038、p061 合计 88 个不同的「说明」引用，结果均为 0）。
3. `potentials`（LD_DZPNO_DZPTEXTHANDLE）的取值中，等于「说明」的数量为 **0**（三个项目）。SW 的 potentials 是 `未定义N:M_页名` 形式的交叉引用或端子名。

样例（p024 S0019，旧链 has_shuoming 的说明文字，均为表头行上的「说明」单元格；12 个不同表头，全部无 SW 引用）：

| 表头 text_id | 旧链说明 text_id | 说明文字坐标 | 说明句柄 | 同 sheet SW 引用 |
|---|---|---|---|---|
| T3099 (ZD) | T3100 | (100.0, 273.75) | BC8C | 0 |
| T3496 | T3497 | (190.0, 273.75) | CBB6 | 0 |
| T3327 | T3328 | (280.0, 273.75) | C5D7 | 0 |
| T3223 | T3224 | (370.0, 273.75) | C1FA | 0 |
| T3231 | T3232 | (370.0, 248.75) | C2A3 | 0 |
| T3403 | T3404 | (100.0, 218.75) | C7F1 | 0 |
| T3143 | T3144 | (280.0, 213.75) | BE86 | 0 |
| T3249 | T3250 | (370.0, 203.75) | C372 | 0 |
| T3356 | T3357 | (190.0, 178.75) | C6C6 | 0 |
| T3160 | T3161 | (280.0, 173.75) | BF51 | 0 |
| T3433 | T3434 | (100.0, 153.75) | C8F0 | 0 |
| T3176 | T3177 | (280.0, 133.75) | C01B | 0 |

说明：同一句柄字符串在不同 sheet 可以对应不同实体（例如 C414 在 S0019 是数字 14，在 S0020 是「说明」），因此引用检查必须限定在同一文件与 sheet 内；首次粗略比对时的假阳性即由此产生，已排除。

因为无法证明与 SW 元数据的一一对应，按规则不补写 `has_shuoming_column` / `shuoming_text_id`（修改前后均为 False / None）。后果：SW 端子行不会进入依赖说明列的旧规则分支（rules.py 中 has_shuoming 条件），这一点需由规则侧接受。

## 3. F3：同排 / 跨排契约

实现：`superworks_extractor.py` 新增 `StripMembership` 与 `_classify_terminal_strip_pairs`，在 `extract_superworks_pairs` 末尾对输出配对执行。仅处理 `evidence.source=="superworks"`、`pair_kind` 为 `ordinary_pair` 或 `bridge_mapping`、且两端 `category` 均为「端子」的配对。

表头判定（只用元数据）：
1. 端子身份在 `sw_strip_rows` 中有行 → 取该行 `header.normalized`；多个不同表头则判为歧义（unknown）。
2. 精确身份无行时，先去掉范围后缀 `~N` 再查行。
3. 仍无行时，才用 `LdDzbInfo.xml` 的 `DZBNAMEITEM.DzbName` 做最长前缀匹配；余下部分必须以行号数字开头（允许字母后缀，如 `6A`）。
4. 都无法判定 → `strip_membership="unknown"`，不写两种标记。

写入字段：
- 同排：`terminal_short_bridge=True`，`strip_header="<表头>"`，`strip_membership="same_strip"`。
- 跨排：`terminal_cross_strip_link=True`，`strip_headers=["<左表头>","<右表头>"]`，`strip_corroborated`，`strip_membership="cross_strip"`。
- `strip_corroborated=True` 当且仅当：某一端的行（按该端身份或去范围后的身份命中）其 connections（左右两侧、_1 与 _2 分支，含逗号拆分；范围 `N~M` 展开为各成员）的规范化值包含另一端身份。

样例（p024 / p038 / p061，后处理结果）：
- 同排：`1I3D12 ↔ 1I3D15` → `1I3D`；`1-4QD2 ↔ 1-4QD22` → `1-4QD`。
- 范围标签：`U3D7~8 ↔ 1U3D4~5` → 跨排，表头 `U3D` / `1U3D`，corroborated=False；`2-7UD20~21 ↔ 1U2D4` → 跨排，`2-7UD` / `1U2D`，corroborated=True。
- 跨排已佐证：`3-4PD6 ↔ KD21`（`3-4PD` / `KD`，True）；`1-2QD3 ↔ CD23`（True）。
- 跨排未佐证：`3-21GD17 ↔ 3-21QD31`（False）。
- 未知：p061 中 `1-21CD6 ↔ 1-21CD6A` 在修改前因后缀 `A` 判为 unknown；放宽为「余下部分以数字开头」后判为同排 `1-21CD`。

计数（最终重放）：p024 同排 48 / 跨排 15（佐证 True 12, False 3）/ unknown 0；p038 同排 109 / 跨排 14（True 14）/ unknown 0；p061 同排 174 / 跨排 4（False 4）/ unknown 0。

与其他子代理的接口：`rules.py:784` 已读取 `terminal_short_bridge`，`rules.py:789` 已读取 `terminal_cross_strip_link` 且要求 `strip_corroborated is True`，字段名与契约一致。

## 4. F4：脚号解析

### 4.1 F4a 文字真实锚点（`superworks_semantics.py`）
- `text_ref` 的 `x/y` 现为 WCS 插入点，新增 `anchor_x/anchor_y`（同样经块变换）。
- TEXT / ATTRIB：ezdxf `get_placement()` 的点（非默认对齐时为对齐点；FIT/ALIGNED 取两点中点）。
- MTEXT：按 attachment_point 取布局框底边上的点（左列取左下角，中列取底边中点，右列取右下角）。
- 脚号候选的距离与并列判定统一使用 `anchor`。`x/y`（插入点）仍用于标签距离判定。

### 4.2 F4b 元件框内标记（通用规则，不按块名）
第一版候选距离只用插入点时，FEIDIAO-10A-Z-3-AC30 块的 J1 距端口 8.32（门限 9.0）被选中。`BORDER` 外框经检查包围了全部脚号标注（N、L、E、J1 均在框内），所以「只允许外侧标注」无法区分，未采用。

采用的规则：
1. 锚点距离替代插入点距离（J1 的对齐点使其距离变为 9.8，超出门限）。
2. 对同一定义实例，计算其他已解析脚号距离（引用解析的脚号用锚点到端口线段的距离；最近候选用其距离）。候选距离超过 `max(1.25 × 其他最大距离, 候选文字高度)` 时拒绝，并在端口 pin 中记录 `{"resolved": False, "nearest_rejected": {...}}`。
3. 豁免：若同一文字被本定义内多个端口共用（例如两个触点共用 DC 标签），则不套用上界。该豁免是在重放中发现的：不加豁免时 p038 有 8 个端口的 DC 脚号丢失（共用标签的锚点距离 7.40 大于 1.25 × 4.05）。

FEIDIAO 结果（同规则 A/B）：p024、p038 中 J1 最近脚号命中由 1 降为 0。p028 缓存直接解析：J 端口不再取 J1；N、L 仍解析（锚点距离 4.5）。p028 的 E 端口在单张 sheet 解析时不再有反向佐证（它依赖其他 sheet 的端子排行，单 sheet 测试不具代表性；重放中 p028 不在范围内）。

### 4.3 F4c 端口名与显示数字
TERMPOINT 名（如 IN2、OUT2）与显示数字（2）并存时，pin 中记录 `port_name` 与 `endpoint_aliases`（如 `HYKL-X12-IN2`）。`corroborate_internal_pin_identities` 对未解析端口同时尝试 `label-IN2` 与 `label-2` 两种候选，以端子排中实际写出的形式为准。别名通过 `_endpoint` 写入 wire 端的 `endpoint_aliases`（仅在非空时出现），并参与 F3 的 corroboration。

### 4.4 F4d 反向佐证脚号
- 由 `strip_reverse_corroboration` 解析的脚号：`pin_resolution_method="strip_reverse_corroboration"`，`independent_verification=False`，并且不计入 `independently_verified_ports`。
- 独立方法（instance_term_text、definition_text_reference、definition_text_nearest）写 `pin_resolution_method` 与 `independent_verification=True`。
- 元件连接配对的 evidence 新增顶层 `pin_resolution_method` 与 `independent_pin_verification`。

## 5. F5 镜像块 WCS
- `entity_insert_wcs(entity) = entity.ocs().to_wcs(entity.dxf.insert)`，用于 INSERT 位置（`sw_symbols.insert_x/y` 与 stale_label_reference 的距离）以及所有文字插入点与锚点。块内变换矩阵 `Insert.matrix44()` 已含 OCS，端口几何无需改动。
- 验证（缓存 DXF 直接解析）：p061 F019 insert_x -212.5 → 212.5；FE9B -345.0 → 345.0。修改前（同规则 A/B）p061 有 3 条 R-SUPERWORKS-CONFLICT（stale_label_reference），涉及 F019、EFDC、F08D、FE71、FE9B；修改后这 3 条全部消失，端口级 stale 标记为 0（symbol 级 stale 计数 2 → 0）。
- 连带影响：`_connect_labels` 的文字坐标改为 WCS，与 LINE 端点一致。`bind_text_ids` 仍用 `text_ref` 的 x/y 与 TextItem 的原始 OCS 插入点比较（仅在同一句柄出现多次且需要消歧时使用），镜像文字在此极少数情况下可能误判；未改动，记录为已知限制。

## 6. F6 文字宽度

修改：`text_geometry.py` 新增 `style_width_factor(entity)`；`cad_text_geometry` 对 TEXT/ATTRIB/ATTDEF，若实体没有自身 `width` 属性，则在副本上设置样式宽度系数（实体自身 width 优先）；MTEXT 的字体量宽改为样式宽度系数。
验证：样式宽度 0.7 时宽度比为 0.7（11.818 / 16.883）；实体自身 width=1.0 时不受样式影响；源实体不被修改。

消费者清单（修改前的 grep 结果）：
- 识别：`cad_extract.py` 把 `rotation_deg` 写入 TextItem，由 `page_extractors.py:1928` 用于识别。旋转角由顶边方向决定，与宽度无关，识别结果不变。
- 识别（新增）：`superworks_semantics.text_anchor_wcs` 对 MTEXT 使用布局角点，以底边中点/端点作为锚点，因此 F6 会影响 MTEXT 脚号候选的位置（仅 MTEXT；重放中的 p024/p038/p061 对配对无可观察变化）。
- 仅预览：`cad_extract.py` 的 text_geometry_json、`primitive_normalizer.py` 的 preview_geometry_json，以及 `desktop/preview.py`（textLength 等渲染）。
- `component_diagrams.py` 只用 bbox，不读取 geometry。

## 7. 测试与重放

单元测试：
- 新增 `tests/unit/test_superworks_round4_producer.py`：24 项，覆盖 F1（左右两侧各一）、F3（同排、范围、跨排佐证/未佐证、unknown、非端子不写）、F4a/b/c/d（锚点、MTEXT 锚点、共用标签、被拒绝的标记、别名、独立计数）、F5（镜像 INSERT 与 stale）、F6（样式宽度、实体宽度优先、MTEXT）。
- `pytest tests/unit -q -k "superworks or text_geometry or terminal_identity or table"`：249 passed。
- `pytest tests/unit -q`（最终代码）：1645 passed, 1 skipped。

重放（`replay.py --projects p024 p038 p061`）：
- 最终输出：`.tmp/round4F_probe3`；快照 `.planning/superworks-adapter/round4F_src3`。
- A/B（同一快照内只把三个文件换回修改前版本）：`.tmp/round4F_ab_pre2`，快照 `round4F_ab_pre2_src`。使用同一 rules.py（最终版本）。
  - 问题数：p024 10→3，p038 9→2，p061 15→4；规则变化主要是 R-MANY-TO-ONE（−6/−7/−5）、R-CROSS-PAGE-CONFLICT（−1/0/−3）、R-SUPERWORKS-CONFLICT（0/0/−3）。
  - 配对：三个项目的 pairs 数量与 (left,right,kind) 集合逐条一致（1842 / 2474 / 3977）。
  - 运行时间：差异在 1 秒以内（p024 19.4→20.2，p038 26.0→26.6，p061 46.4→46.4 秒）。
- 注意：`.tmp/superworks_round3_full` 的旧数据使用的是更早的 rules.py，其问题数（12/17/22）与本次 A/B 基线不可直接比较。
- 中间版本（`round4F_probe`、`round4F_probe2`）已被后续修复替代，保留未删除。
- 产物位置：快照目录 `.planning/superworks-adapter/round4F_src2`、`round4F_src3`、`round4F_ab_pre_src`、`round4F_ab_pre2_src`（均为 src 副本，其中 A/B 快照仅替换了三个修改文件）；输出 `.tmp/round4F_probe*`、`.tmp/round4F_ab_pre*`；汇总数据 `round4/F/probe_post_round4F.json`（round3 与最终对比）与 `round4/F/ab_clean_same_rules.json`（同规则 A/B）。

剩余问题（最终重放；均不在本次修改范围内，需规则侧或人工复核）：
- p024：R-MANY-TO-ONE 1U1D4、1U1D5；R-SUPERWORKS-CONFLICT（F0010 的 1FB74 与 1FBBC 竞争）。
- p038：R-MANY-TO-ONE KD23、KD26（端子表与元件映射共用端点，对应 round3 D 报告中的 KD23 类残余）。
- p061：R-MANY-TO-ONE 1-21QD77、2-21QD31、3-21QD31、4-21QD71。

同规则 A/B 中，修改前的问题中被消除的主要是 R-MANY-TO-ONE（p024 −6、p038 −7、p061 −5），以及 p061 的 R-CROSS-PAGE-CONFLICT（−3）与 R-SUPERWORKS-CONFLICT（−3，stale_label_reference，见 §5）。

## 8. 已知限制与未覆盖项
1. F2 未实施，SW 端子行的 `has_shuoming_column` 仍为 False。旧链中依赖说明列的分支不会对 SW 行生效。
2. `bind_text_ids` 使用 WCS 与 OCS 比较（见 §5）。
3. 锚点与共用标签豁免新增了部件端口的脚号解析。例如 FJL-25-2A_Mirror 的 `1'` 与 `1` 共用文字「1」，`1'` 由无脚号变为 `1`（距离 6.5），端点为 `1C2LP4-1`。最终重放中，部件端口的端点身份新增解析 p024 36 处、p038 54 处、p061 45 处，另有 J1 错配消失 p024 1 处、p038 1 处。这些结果与同号触点共用文字的结构一致，但未逐个人工核对。它们没有改变任何配对（三个项目的配对集合逐条一致）。SW 符号端口（sw_ports）的端点身份在三个项目中均无变化。
4. F4b 的 1.25 倍系数是经验值（取自 FEIDIAO 与 DC 两类样例），未在 77 项目上统计验证。
5. 未运行全量 77 项目回放（按指示只跑三项目）。
