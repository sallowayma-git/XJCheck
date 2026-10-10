# Z-3 修复：表格单元格伪导线（台账类别 H，reason=table_cell_edge_no_outward）

## 1. 改动

- `src/dwg_audit/audit/superworks_extractor.py`：新增常量 `TABLE_CELL_REASON`、`CELL_FRAME_X_TOL_FRACTION=0.05`、`LEAD_CONTACT_FRACTION=0.05`、`GRID_PITCH_RATIO=2.0`；新增辅助函数 `_insert_owner`、`_is_vertical_line`、`_frame_covers`、`_cell_row_probe`；新增 `supersede_cell_edge_pairs(pairs, ledger, lines, line_groups, texts)`，位于 `supersede_border_row_duplicates` 之后。复用 Z-1 的 `_is_virtual_horizontal_line`、`_border_neighbours`、`_missing_end_points`、`_fillable_one_sided_pair`、`_text_outline`、`_outline_distance`、`_bbox_corners`、`BORDER_MIDLINE_TOL_FRACTION`、`BORDER_TEXT_TOL_HEIGHTS`、`BORDER_HORIZONTAL_TOL`。
- `src/dwg_audit/pipeline.py`：在 `supersede_border_row_duplicates` 调用之后加一处调用（4 行），传入 `audit_lines, line_groups, audit_texts`。
- `tests/unit/test_superworks_loop_z3_cells.py`：新增 18 个用例。
- 未改 SW 行，未删除任何 pair，未执行 git 操作，未全量回放。

## 2. 判定（全部满足才 discard）

1. 单侧 pair：复用 `_fillable_one_sided_pair`，要求 `status != discard`、`pair_kind == ordinary_pair`、来源非 superworks、恰一侧有值、`ordinary_pair_eligible` 非 False、非 DIM 层。
2. 线组成员全部为同一 INSERT 展开的 VIRTUAL 水平线（句柄 `{insert}:VIRTUAL:{n}`，INSERT 唯一）。
3. 线组两端各有同一 INSERT 的竖向线：x 距端点不超过 5% × 边跨度（`CELL_FRAME_X_TOL_FRACTION`），y 范围覆盖该水平线（容差 15% × 行距）。
4. 同块邻线：复用 `_border_neighbours`（同块、水平 VIRTUAL、覆盖缺端 x、共同跨度 ≥ 50%），并限定为网格邻行：间距不超过较近一侧间距的 2 倍（`GRID_PITCH_RATIO`）。
5. 缺端外侧：对每条网格邻行，行中心 `c = (y_线组 + y_邻线) / 2`（即半间距偏移，未写死 2.5 或 7.5）。探测矩形 x ∈ [缺端 x, 缺端 x ± 行距]，y ∈ c ± 15% 行距。
   - 引线：线段内侧延伸 ≤ 5% 行距（`LEAD_CONTACT_FRACTION`，以行距为依据）且外侧延伸 > 5% 行距。跨框的对称引脚标记不算引线。
   - 文字：缺端外侧 1.5 倍字高（`BORDER_TEXT_TOL_HEIGHTS`）内无文字，距离只相对缺端计算。
   - 所有网格邻行的探测都必须无引线、无文字。
6. 已被其他规则处理的不重复处理：`status == discard` 或 evidence 含 `table_border_row_duplicate` 的 pair 直接跳过。

动作：`status="discard"`，`rationale="table_cell_edge_no_outward: {owner}"`，`evidence["table_cell_edge"]` 记录 owner、缺端坐标、邻线句柄、各探测的行中心、容差、引线与文字 id；台账追加 `category="H"`、`reason="table_cell_edge_no_outward"`、`new_pairs=[]`。不删除 pair。

## 3. 偏离规格处与依据

a. 引线判定不能只看长度。数据统计：p075 的 SW 连接线（308 条）全部长 1.0；四个项目（p075、p000、p061、p072）合计的 SW 连接线中 1199 条有一个端点贴在列框上并向外延伸，仅 3 条跨框。缺端引脚标记同样长 1.0，是两点闭合多段线，跨在列框两侧（如 `3214C:VIRTUAL:639:0/1`，x 284.5–285.5）。因此判据是"从框起始向外"，而不是"长度"。首版没有这条判据，结果 p075 命中 0 条（引脚标记全部被当成引线）；加入后命中 34 条。

b. 文字判据只对缺端计算。首版同时对行中心计算距离，PC0073 下方行的标签 `1-26TD178 @`（x 286–306，y 117.45–120.9）距行中心 2.6、距缺端 4.96（> 1.5 × 3.0 = 4.5）。按规格"缺端外侧 1.5 倍字高"该标签不应阻挡，已改为只对缺端计算。修正后 PC0073/0074/0281/0282 命中。

c. 网格邻行。PC0138/PC0346 的上方最近平行线在 y=237.5（距 70，中间没有表格行线；本表行距为 5），首版把它当成需清空的探测行，导致两条被误挡。加入 `GRID_PITCH_RATIO=2` 后只保留间距不超过 2 倍较近一侧间距的平行线。已知限制：若块的某一侧只有一条平行线，该线自身定义行距而被接受；round9 的 40 条命中都有两侧邻线，本次未触发此分支。

d. 多条网格邻行的探测采用"全部清空"（保守）。

e. 台账 `new_pairs` 为空（本规则不涉及 SW 行）。

## 4. 单元测试

`tests/unit/test_superworks_loop_z3_cells.py`，18 项：

- 满足条件 → discard，台账 H，evidence 正确，pair 未删除；
- 跨框对称引脚标记不阻挡；外侧引线阻挡；缺端 1.5 字高内文字阻挡；超出半径的标签不阻挡；框内侧文字不阻挡；
- 双侧 pair、SW 来源 pair、非 ordinary pair、已 discard pair、他块成员、非 VIRTUAL 成员、竖向线组、无网格邻行、远邻行（超过 2 倍行距）被忽略、列框未覆盖线组、另一端无列框、其他 pair 不变 → 均不动。

结果：`pytest tests/unit/test_superworks_loop_z3_cells.py` 18 passed；`pytest tests/unit -q` 1836 passed, 1 skipped（Z-1 基线 1818 加本次 18）。

## 5. 全语料离线评估

输入：第九轮 `.tmp/superworks_round9_full` 的 pairs / lines / line_groups / texts，77 个项目，直接调用 `supersede_cell_edge_pairs`，未回放。

- 命中 40 条，全部在 p075（S0014 与 S0015，块 TS3000-Z01，INSERT 3214C / 3205D）：38 条 G2 报出 + PC0138、PC0346 两条抑制项。与 Z-3 README 的口径一致（预期 40）。
- 其他 76 个项目命中 0（预期 0）。
- 双侧 pair 改动 0（77 个项目全部检查）。
- GND 四条（PC0123、PC0185、PC0331、PC0393）为双侧（SW 文字已补全），未动。

## 6. 单项目验证（replay 探测）

命令：`python .planning/superworks-adapter/replay.py --output .tmp/loopZ4_probe --snapshot .planning/superworks-adapter/loopZ4_src --workers 3 --projects p075 p000 p061 p072`（快照由当前 src 复制）。四个项目均 COMPLETE。

- p075：pairs 仅 40 行变化（status review → discard，rationale 为 table_cell_edge_no_outward），其余 2298 行（含 evidence）不变；台账 H 行 40 条。R-PAIR-MISSING-SIDE 40 → 2（减少 38，与预期一致）；issues 45 → 7。被移除的 38 条 issue 的 pair_id 与 G2 报出清单逐条一致。剩余两条为 PC0232（G3，非 VIRTUAL 线，不在本规则范围）与 PC0440；它们的 issue_id 重新编号，review_group_size 由 20 变为 1（分组计数随移除而变化），其余内容一致。其他规则的 issue 去掉 issue_id 后内容完全一致。
- p000、p061、p072：pairs（全部字段含 evidence）与 issues（含 issue_id）与第九轮逐条一致；变化行数 0。
- 探测目录 `.tmp/loopZ4_probe` 与快照 `.planning/superworks-adapter/loopZ4_src` 已删除。

## 7. 截图（`fix_png/`，由第九轮几何直接绘制，逐张确认）

- `C1_PC0032_edge_group_frames.png`：线组（橙）、同块列框（蓝虚线）、网格邻行 1/2（绿），非网格远框（灰点）。确认。
- `C2_PC0039_grid_rows_probe.png`：两侧网格邻行 2/2，两个行中心探测（黄）外侧空白。确认：可判。
- `C3_PC0073_label_beyond_radius.png`：下方行标签距行中心近，但距缺端 4.96 > 4.5，不阻挡。确认。
- `C4_PC0138_far_border_ignored.png`：y=237.5 远框（距 70）被忽略，仅 y=162.5 网格邻行参与。确认。
- `C5_PC0032_pin_marks_not_leads.png`：缺端处跨框引脚标记（x 284.5–285.5）不计为引线，探测区清空。确认。
- `C6_PC0123_two_sided_untouched.png`：双侧 pair（SW 文字补全 GND）未被修改；行中心另有接地符号引线，双侧规则之外即不作用。确认。

## 8. 残留风险

- 规则只在 p075 命中，其他项目无同形样本可验证；75 个项目 0 命中是经验结果，不是证明。
- 网格与探测的阈值（2 倍行距、5% / 15% 行距、1.5 字高）来自本批数据，只在第九轮验证。
- 单侧平行线时行距由该线本身定义（见第 3 节 c）。
- 行距 ≥ 10 单位时，跨框引脚（半长 0.5）会被计为引线（5% 行距 ≥ 0.5），结果偏保守：只会少剔除，不会误剔除。
- 真实导线若画成表格边框且外侧既无引线也无文字，仍会被剔除，与 Z-3 README 第 7 节风险相同。

## Z4b：按 p051 核查修正 cell-edge 规则（台账 H，reason=table_cell_edge_no_outward）

### 1. 修改

- `src/dwg_audit/pipeline.py`：`supersede_border_row_duplicates` 与 `supersede_cell_edge_pairs` 移到 `mark_ignored_equipment_panel_ordinary_pairs` 之后执行。两条规则都跳过 `_panel_owned`（evidence 含 `ignored_panel_family_id`，或 `ordinary_pair_eligible` 为 False）的 pair，且不写台账。
- `superworks_extractor.py`，`supersede_cell_edge_pairs`：
  - 边的成员须同一 INSERT、同一图层（记为表格框图层）。
  - 邻线须与成员同 INSERT、同图层，且共同跨度不小于边跨度的 50%。
  - 两侧都有邻线（均在 2 倍最近行距内）即视为网格。只有一侧有邻线时，不能用它单独定义行距：同块、同图层的水平边框中，须存在 3 条连续等距线（间距与行距之差不超过行距的 10%），且包含该邻线。
  - 探测：缺端上、下两个行中心都必须清空（无引线、缺端 1.5 字高内无文字）。一侧无邻线时，该侧行中心取缺端 ±行距处。
  - 台账 reason 保持 `table_cell_edge_no_outward`；面板 IGNORE 的 pair 不写台账。
- `src/dwg_audit/audit/superworks_extractor.py`，`supersede_border_row_duplicates`：增加 `_panel_owned` 守卫（移动调用后对结果无影响，属于一致性修补）。
- `tests/unit/test_superworks_loop_z3_cells.py`：25 项（原 18 项，新增 7 项）。

### 2. 偏离规格的细化与理由

a. **等距判定只统计长度不小于边跨度 50% 的水平边框。** 块内有长 1 的 VIRTUAL 引脚短线（如 `3214C:VIRTUAL:627:0`、`:890:0`，y 间距 2.5），夹在 5 单位行之间。不过滤时，p075 的 6 条单侧命中全部失去等距确认（PC0032、PC0033、PC0138、PC0240、PC0241、PC0346），replay 结果为 cell-edge 34 而非 40。过滤后 6 条重新命中，两侧探测均清空。

b. **原单侧测试场景改为双侧网格。** `_world` 默认增加下方边框（y=92.5）。原先只有上方一条邻线，在新规则下不再直接命中，这是规则收紧的预期变化。另外，轮次 Z-3 记载"40 条命中都有两侧邻线"并不准确：round10 中有 6 条只有一侧邻线，通过等距判定命中。

### 3. 单元测试

- `tests/unit/test_superworks_loop_z3_cells.py`：25 passed。新增用例：下方行中心的引线阻挡；面板 IGNORE 的 pair（两种标记，参数化）不命中且无台账；p051 形态（唯一邻线为 CH 图层说明框边）不命中；单侧同图层但无等距三线不命中；单侧经等距三线确认后命中；1 单位引脚短线夹在行间不破坏等距判定。
- `pytest tests/unit -q`：1843 passed, 1 skipped（原 1836 加本次 7 项）。

### 4. 单项目回放（`.tmp/loopZ4b_probe2`，快照 `loopZ4b_src2`，项目 p075 p051 p000 p061）

- **p075**：cell-edge 40（第十轮 40）、border-row 32（第十轮 32）、R-PAIR-MISSING-SIDE 2（第十轮 2）。issues 7 条，与第十轮逐条一致（忽略 issue_id）。pairs 去掉 pair_id 与 `evidence.table_cell_edge` 后，与第十轮完全一致；40 条命中的差异仅是新增 `edge_layer`、`grid_basis`、`probes[].side` 字段。
- **p051**：PC0052、PC0080 为 review，rationale `missing left candidate`，evidence 无 `table_cell_edge` 键。cell-edge 0（第十轮 2），issues 0，与第十轮一致。未能与第九轮逐字段核对，因为 `.tmp` 下没有 `superworks_round9_full`。
- **p000、p061**：pairs 去掉 pair_id 后集合逐条一致（1417 行、4229 行），issues 一致。

注：pair_id 在两次运行之间会重新编号，逐行比较时须忽略 pair_id，否则会出现大量假差异。

### 5. 残留风险

- 只在 p075 有同形样本。p051 的负例已验证，其它项目的 0 命中仍是经验结果。
- 图层判定依赖边成员与表格框同图层（本批数据均为图层 0）。
