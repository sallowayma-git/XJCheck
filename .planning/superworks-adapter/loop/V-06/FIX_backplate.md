# V-06 背板豁免修复说明（FIX_backplate）

范围：仅修改 `src/dwg_audit/audit/rules.py`，新增 `tests/unit/test_superworks_loop_v06_backplate.py`。未改生产端（superworks_extractor.py 未动），未做 git 操作，未全量回放，未删除文件。

## 1. 问题回顾
`_is_authoritative_terminal_strip_backplate_attachment_group`（rules.py 约 1956 行，调用点 742 行，`_run_cross_page_conflict`）原先只接受 `component_submode == "terminal_strip_lattice"` 的 pair 作为端子排行证据。第六轮中 p016–p021 的 lattice 映射被 SuperWORKS 连接线半行等价替代，因此该豁免对这些行恒为 False。

## 2. 等价字段核验（第六轮 `.tmp/superworks_round6_full/p016..p021/project/findings/pairs.parquet`）
SW 连接线半行（`component_submode == superworks_connect_line_port`，`line_orientation == terminal_strip_lattice_row`）携带与 lattice 行相同的整行证据：
- `left_terminal` / `right_terminal` 及其 `*_text_id`（外部端子，干净值）
- `terminal_strip_instance`、`terminal_strip_insert_handle`、`terminal_strip_instance_text_id`、`terminal_strip_flank_line_ids`、`terminal_strip_row_y`
- `terminal_strip_left_pin` / `terminal_strip_right_pin`（handle、text_id、value）

字段名与 lattice 相同，无需映射。差异只有两点，已在规则中处理：
- 半行的 pair 只暴露一个端点：`left_value` 为逻辑端 `TF<实例>-<pin>`，`right_value` 为外部端（850 条中 770 条带 `*` / `&` 装饰，干净值在 evidence 里）。
- 半行的 `left_text_id` 是实例文字（INSTANCE），不是外部端文字，因此不能直接用 pair 的 text_id 比较，必须读 evidence 的 `left_terminal_text_id` / `right_terminal_text_id`。
- 实例名按块区分（`TF`、`TF2`、`TF-27` 等），逻辑端形式为 `TF2-1`，不能用固定的 `TF-\d+` 正则。

## 3. 修改内容（rules.py）
1. 新增 `_strip_endpoint_decoration_free(value)`：去掉 `*`、`&`、空白（与 lattice 路径 component_diagrams.py:381 的规则一致）。
2. 新增 `_terminal_strip_row_witness(pair)`：返回 pair 所陈述的端子排行，或 None。
   - lattice pair：沿用原字段，行为不变。
   - SW 连接线半行：仅当同时满足以下语义条件才视为证据：
     - `line_orientation == terminal_strip_lattice_row`、SuperWORKS 来源、`independent_pin_verification is True`、`sw_conflicts` 为空；
     - 半行自身的外部端（归一化后）等于 `left_terminal` 或 `right_terminal`，并且该侧即为其 `component_port` 对应的 pin；
     - `logical_endpoint` 的规范化形式等于 `<terminal_strip_instance>-<component_port>`；
     - pair 的两个值恰好是 {逻辑端, 归一化外部端}。
   - 不满足任一条件则返回 None。来源本身（SuperWORKS）不构成证据。
3. `_is_authoritative_terminal_strip_backplate_attachment_group` 改为用 `_terminal_strip_row_witness` 取行信息。row 的 left/right/text_id 取自 row 本身（lattice 取 pair 字段，SW 半行取 evidence 字段）。其余检查（pin handle、VIRTUAL 前缀、text 唯一性、`<instance>-<pin>` 与 table.right_value 的规范化比较、plugin_slot_authority 等）保持原样。
   - 原来的 `strip.left_value != table.left_value` 改为 `row["left"] != table.left_value`。
   - 只要不是 table_mapping 的那一个 pair 就作为行候选，不再按 submode 搜索。

## 4. 单元测试（tests/unit/test_superworks_loop_v06_backplate.py，16 例）
- lattice 行命中（原行为不变）；lattice 的 instance_text_id 缺失仍不命中。
- 等价 SW 半行命中：pin1 半行（TF-1 | * 1n2001）、pin2 半行（TF-2 | 1UD1 *）。
- 同一行上错误的背板挂接（TF-2 而非 TF-1）仍不命中。
- 缺少等价引脚证据的 SW 半行不命中，9 种损坏：独立引脚验证为 False、pin value 与 port 不符、逻辑端不是外部端所在 pin、外部端不在该行、pair 逻辑端脱离排、sw_conflicts 非空、缺左 pin handle、缺 flank、缺外部端文字 id。
- 仅有 SW 来源、行方向不对的 SW pair 不作为行证据。
- 端到端（build_issues）：lattice + 背板表格对（同左值、跨页）不报 R-CROSS-PAGE-CONFLICT；加入另一页接到不同设备的真实冲突后仍报 R-CROSS-PAGE-CONFLICT。

结果：`pytest tests/unit/test_superworks_loop_v06_backplate.py -q` 16 passed；`pytest tests/unit -q` 1764 passed, 1 skipped。

## 5. 离线验证（p016–p021，只读）
离线脚本位于 scratchpad（v06/offline_backplate.py、compare_rules.py），直接调用 live `rules.py`，未写入任何项目文件。

### 5.1 谓词层面（同一行结构，r5 lattice 形态 vs r6 SW 半行形态）
| 形态 | 修复前命中 | 修复后命中 |
|---|---|---|
| r5 lattice + 背板表格对 | 481 对 / 298 行 | 481 对 / 298 行（不变） |
| r6 SW 半行 + 背板表格对 | 0 | 962 对 / 298 行 |

- r5 与 r6 的 298 个命中行逐一对应（按 项目、左外部端、右外部端 比较，两侧集合相同）。
- 两种形态下未命中的 9 行也一致（与 SW 修复无关）。
- 结构前提（同左值 backplate 表格对在另一页）两侧均为 307 行。

### 5.2 实时分组路径（`_run_cross_page_conflict` 的实际调用）
| 形态 | 谓词实时调用次数 | 结果 |
|---|---|---|
| r5 | 104 次（table_mapping + terminal_strip_lattice） | 104 次全部 True（与 README 的 104 吻合） |
| r6 | 0 次 | — |

- r6 中谓词从未被实时调用，修复前后一致。原因见第 6 节。

### 5.3 规则输出（build_issues，p016–p021，新旧谓词对比）
| 形态 | 修复前 issue | 修复后 issue | issue 键集合 |
|---|---|---|---|
| r5 | 2（R-SUPERWORKS-CONFLICT 1，R-MANY-TO-ONE 1） | 2 | 完全相同 |
| r6 | 1（R-MANY-TO-ONE 1） | 1 | 完全相同 |

与 details.json 记录的 "6 个项目合计 r5 2 条、r6 1 条" 一致。`compare_rules.py` 的旧版谓词为编辑前的原文（scratchpad/v06/old_predicate.py）。

## 6. 残留问题（需要决策，本次未做）
谓词修复后，SW 半行仍然进不了实时豁免路径：`_run_cross_page_conflict` 按 `pair.left_value` 分组，而 850 条 SW 半行的左值全部是逻辑端 `TF…`（外部端在右侧）。外部端组（如 1n2107）因此只剩背板表格对，不再跨页多右值，所以不产生 issue，这正是 README 所述“无输出变化、属潜在回归”的状态。

要让豁免在实时路径上真正生效，需要改分组：让 SW 端子排行半行按其外部端（evidence `left_terminal` / `right_terminal`）入组，或让豁免在分组后查找同行的兄弟半行。这会改变 R-MANY-TO-ONE、R-CROSS-PAGE-CONFLICT 等多条规则的输入，超出本次谓词修改的范围，未实施。建议作为单独任务，以 p016–p021 的 r6 数据回归。

## 7. 修改位置汇总
- `src/dwg_audit/audit/rules.py`：新增 `_strip_endpoint_decoration_free`、`_terminal_strip_row_witness`；修改 `_is_authoritative_terminal_strip_backplate_attachment_group`（约 1956 行起）。
- `tests/unit/test_superworks_loop_v06_backplate.py`：新增，16 例。
- `.planning/superworks-adapter/loop/V-06/FIX_backplate.md`：本说明。
