# FP-VERIFY：2594dbe 三类可疑变化的图面核验（只读）

日期：2026-10-15。范围：HEAD 2594dbe 的全量 77 项目输出（`.tmp/engine_coordination_full_acceptance/current`）对照 round25（`.tmp/superworks_round25_full`）。冻结 DXF 由 `.planning/superworks-adapter/corpus_manifest.json` 指向。

约束遵守情况：未修改 `src/`、`tests/`、`.planning/` 下任何已有文件；未执行 git 写操作（只用了 `git show/log/archive`）；未删除目录。对方工作区未提交的 `progress.md`、`task_plan.md` 为其原有改动，未触碰。新增仅限：本目录、`.tmp/fp_verify_*`。

## 0. 结论总览

| 项 | 可疑变化 | 结论 | 证据量 | 根因提交 / 函数 |
|---|---|---|---|---|
| 1 | 425 条 V1 lattice pass 恢复（与 SW pass 双存） | **误报**：V1 错，应保持被取代 | 结构检验 425/425；图面抽样 18 例 | 6e0492e；`superworks_extractor.extract_superworks_pairs` 连接标签循环的 `existing_native_parts` 跳过（`continue`），使 `replace_claims(...,"part:...")` 不再执行 |
| 1b | 同批另 6 条 `wire_component_mapping` 新 pass | 非新关系：同一线组、同一文字 id、同一坐标，只是左端值 `607→1n607` 等身份归一化（P4，待裁决） | 6/6 | 28d2511；`finalize_evidence` 的 fixed identity 归一化 |
| 2 | 8 条 R-SUPERWORKS-CONFLICT（1B9EA:1 等） | **误报**：同一物理端口被父、子两条实例路径各枚举一次 | DXF 嵌套 INSERT 核实；竞争对 gap 0.0；8/8 同型 | 端口枚举：`superworks_semantics._definition_ports`（既有，自 2e2f898 起）；冲突判定与报出：6e0492e（`_endpoint`/`_coincident_ports` 进入原生端点解析）、e997681、a8e9e5a |
| 3 | p061 S0025 4 条 R-PAIR-LOW-CONFIDENCE | **误报**：元件外框 BORDER 竖线被当作导线做普通配对 | 图面 2 张；4/4 同型 | 6e0492e（原生优先后 SW 部件配对不再携带框线 line_group_id）；`superworks_extractor` 部件 pass 的 `line_group_id` 取值分支 |

数字摘要（比例）：
- 425 条中，独立导线 0 条（0%）；全部为端子排内部导通派生的“行内贯通”关系（100%）。
- 2 条 SW 冲突中，同一物理端口重复 8/8（100%）；未发现 SW 本身错误的情形。
- 低置信 4 条全部为框线误配（100%）。

## 1. 数据与对齐方法

- 配对对齐：round25 与 current 的 pass 不能按 pair_id 对齐（pair_id 两轮之间重编号，且 round25 台账中的 old_pair 的 pair_id 会与别的 pair 撞号）。因此按内容键对齐：（project, sheet, 端子值无序对, 端子文字 id）。
- 425 条判定：current pass 中不在 round25 pass 集合里的 component_mapping 记录 425 条（分布 p016 95、p017 66、p018 63、p019 63、p020 72、p021 66；页 "元件接线图3/4"；项目族 GJ-75 WMH-800-D1C 的六个变体）。另有 6 条 wire_component_mapping（p064 S0009、p068 S0006）。
- 台账匹配：425 条全部能在 round25 台账中按端子无序对找到 `validated_superworks_replacement`（B 类，850 行，每条两行），旧配对原为 pass，但在 round25 最终 pairs 中已不存在。6 条 wire 项在台账中无对应。
- 工具：`tools/build_diff.py`（读取两轮产物并存 pickle）、`tools/diff_pass.py`、`tools/analysis_425.py`（台账匹配）。中间 pickle 位于 `.tmp/fp_verify_work/`。

## 2. 项 1：425 条恢复的 V1 lattice pass

### 2.1 形态分组（全部 425 条同型）

| 维度 | 取值 |
|---|---|
| lattice 类型 | `terminal_strip_lattice`（425/425），端子排实例 TSB-14（425/425），行距 5.0（425/425） |
| 页面类型 | 元件接线图（"ACCESSORIES WIRING-3/4"），每项目 1–2 页 |
| 项目家族 | GJ-75 WMH-800-D1C-国产化，6 个母线保护柜变体（p016–p021） |

按（项目，页）的数量见 `tools/results.json` 的 `lattice_425.per_sheet`。

### 2.2 结构检验（覆盖全部 425 条，`tools/lattice_test.py`）

| 检验 | 结果 | 含义 |
|---|---|---|
| 左右标签是否同一行（y 相等） | 425/425 | 不存在“跨行”关系，所谓“保留跨行关系”的依据不成立 |
| 框内是否有原生导线贯通（端子 pin 带内，x 覆盖端子框） | 0/425 | 1n2001 与 1UD1 之间没有一根实际导线 |
| 线组 member 的来源 | 425/425 为 TSB-14 块的虚拟边框线（BORDER 层，句柄 `163D0:VIRTUAL:*`） | V1 的“导线”其实是端子排本体的外框 |
| 两侧标签是否都已有 SW pass（TF-n 针脚配对） | 425/425 | SW 已用针脚级配对覆盖两端 |

图面证据：端子排每行为一个圆形端子（1/2、3/4…）。左侧线号（如 1n2001）经一段短引线接到左端子（pin 1），右侧 1UD1 经短引线接到右端子（pin 2）；两端子之间的框内无导线（见 `png/L1_p016_S0021_row1_overview.png`，蓝线为叠加的 V1 配对，原图框内无线）。SW 的 TF-1↔1n2001、TF-2↔1UD1 与 DXF 上的两段短引线一一对应，SW 配对是正确的。

判定：V1 恢复的 1n2001↔1UD1 是“经端子导通”派生的关系（电气上同网），不是一根导线的另一端。它与已存在的 SW 配对（TF-1↔1n2001、TF-2↔1UD1）描述同一物理行，是重复表达。按题目给定的三类判定：
- 真实的另一条导线：0/425
- 同一根线的错误另一端（V1 错，应保持被取代）：425/425（按“导线关系”口径）
- SW 错：0/425

注：若产品口径要求保留“端子导通”网络关系，应作为独立的非 pass 关系（例如 `terminal_through`）输出，不能作为导线 pass 与 SW 双存。

### 2.3 图面抽样（18 例，分层）

分层：（项目，页）共 11 层，每层取 1–2 例（`tools/build_sample425.py`）。每例图中：蓝色为恢复的 V1 配对，绿/橙为同行两条 SW 针脚配对，紫为线组（框线）。

- `png/FP425_00` … `png/FP425_17`，对应 `tools/sample425_index`（样例清单由脚本生成于 `.tmp/fp_verify_work/sample425_index.json`）。
- 已人工复核的代表：`FP425_00_p016_S0021_PCN0006.png`、`FP425_13_p020_S0026_PCN0039.png`、`L1_p016_S0021_row1_overview.png`。18 例与结构检验结论一致。

### 2.4 根因（已用回放因果验证）

回放（`tools/bisect_p016.py`，只读回放 p016，源码取自 `git archive`）：

| 提交 | p016 lattice pass | p016 总 pass |
|---|---:|---:|
| d11d0b3（round25 基线） | 0 | 1288 |
| c6135f9 | 0 | 1288 |
| 6e0492e | 95 | 1383 |
| 28d2511 / 29f7b5c / 875ebf4 / 2594dbe | 95 | 1383 |

引入点：6e0492e（“route native objects first and pair only uncovered V1 targets”）。

机制（`src/dwg_audit/audit/superworks_extractor.py`，`extract_superworks_pairs` 连接标签循环，HEAD 约 L1815–1822）：

```
existing_native_parts = {(file, sheet, connection_handle) for p in pairs if _is_sw_component_row(p)} ...
for label in data.connect_labels:
    if (label.file_id, label.sheet_id, label.text.get("handle")) in existing_native_parts:
        continue          # 直接跳过，后面的 old 查找与 replace_claims(old,new,f"part:...") 都不执行
    old = [p for p in pairs if ... label.text_id in (p.left_text_id, p.right_text_id)]
```

6e0492e 新增该跳过（f9de76c 改为按文件限定）。该跳过本意是避免重复生成原生已覆盖的部件配对，但它同时跳过了对 V1 旧配对的替代。V1 的 terminal-strip lattice 配对（1n2001↔1UD1）的端子 id 正是连接标签的文字 id，因此不再被替代。round25 中产生 850 行 B 类台账（element key `part:SWC:...`）的正是这条 `replace_claims` 调用。

辅助因素（未单独验证）：`component_diagrams.extract_terminal_strip_lattice_pairs` 的 `_build_uncovered` → `ScopedPairIds.admit`（875ebf4 引入）只在“针脚为虚拟句柄”或“传入 body_text_id”时才识别 SW 覆盖；lattice 的两端都是外部线号，因此门禁不拦截。

因果验证（反事实，`.tmp/fp_verify_src/cf_skipfix`，只改上述跳过分支，改为替代其中的 V1 旧配对）：
- p016：pass 集合与 round25 逐条相同（差异 0），lattice 95 → 0。
- p017–p021、p064、p068 回放同样处理：p017–p021 的 pass 集合与 round25 完全一致（cf 相对 round25 差异 0），lattice 合计 425 → 0。
- issue 总数不变（cf 与 current 逐项目相同）。p064/p068 的 6 条 wire 项不受影响（见 §5）。

### 2.5 修复建议与预计变化

- 修复：在 `existing_native_parts` 命中分支中，不要直接 `continue`，而是先对该 label 上的 legacy component_mapping 旧配对执行替代（只跳过“生成新配对”部分）；同时可在 `ScopedPairIds.admit` 中把“两端标签都已是同一部件 SW 针脚的外部端点”判为已覆盖（补充门禁缺口）。
- 预计：pass 79,550 → 79,125（减 425，与 round25 的 pass 总数一致；另 6 条 wire 项与 round25 的 6 条替换，见 §5）；R-* issue 不变（这 425 条未挂 issue）。

## 3. 项 2：8 条 R-SUPERWORKS-CONFLICT（p041–p044 的 S0012 / S0013）

### 3.1 是否同一物理端口：是

- DXF（`F0012` 对应 `12 发电机操作回路图.dwg`，`F0013` 对应 S0013 页）：父块 `INSERT 2F60B`（块 SYMB2_M_PWF128，位于 202.5, 167.5）的定义内嵌套了 `INSERT 2F324`（块 SYMB2_M_PWF21，位于父块原点）。即线圈只有一个，嵌在父符号内。
- SW 端口记录（sw_ports）中，同一标记 `1B9EA:1`、`1B9ED:2` 出现两次：
  - 子路径记录：instance `/2F60B/2F324`，owner `/2F60B/2F324`（线圈本体，类别“线圈”）；
  - 父路径副本：instance `/2F60B`，owner `/2F60B/2F324`（类别“内部元件”）。
  两条记录坐标完全相同（202.25 / 207.25, 167.5），`competing_ports` 的接触间隙为 0.0。
- 另有父块自有针脚 `2F325:1`、`2F328:2` 与线圈针脚坐标重合（同一接触的定义级针脚）。
- 结论：1B9EA:1 在父块路径与子块路径下是同一物理端子。8 条全部为“祖先实例 / 后代实例”同一接触（例如 `/2F5F6` 与 `/2F5F6/2F324`，`/2F60B` 与 `/2F60B/2F324`）。

图面：`png/CONF_p041_S0012_nested_port.png`、`png/CONF_p043_S0013_nested_port.png`（绿=子路径记录，橙=同标记的父路径副本，紫=父块自有针脚，蓝=竞争导线）。

### 3.2 根因

- 端口枚举（既有缺陷，不是 2594dbe 引入）：`src/dwg_audit/extract/superworks_semantics.py` 中 `_definition_ports`（约 L145）递归进入嵌套 INSERT（`yield from _definition_ports(doc, entity, world, path + "/" + handle, ...)`），而 `walk()`（约 L382，递归 L501）又会单独枚举子 INSERT。同一组 termpoint 因此在父路径与子路径下各产出一次。该函数自 2e2f898（2026-10-09）起未变。
- 证据：p041–p044 的 sw_ports 记录集合在 round25 与 current 中完全相同（1161/1169/2234/2250 行，差异 0）。因此端口枚举并非本轮改动。
- 报出机制的变化：
  - 6e0492e 的 native-first 端点解析使这些导线在无 Pair 的情况下也经过 `_endpoint`（`superworks_extractor.py` 约 L173）和 `_coincident_ports`（约 L54），按 `symbol_id` 不同即判为 `competing_physical_port_instances`；`_coincident_ports` 不检查祖先/后代关系，也不按标记去重。
  - round25 中没有这条观测通道（d11d0b3 的 superworks_extractor 无 `resolution_observations`），相同的竞争在 round25 中被静默丢弃；e997681（无 Pair 的原生冲突进入问题）与 a8e9e5a（每个物理见证单独保留，按 file/sheet/object/reason 分组）使其成为 R-SUPERWORKS-CONFLICT。

### 3.3 反事实验证（p041–p044，`tools/bisect_p016.py` 变体，结果见下）

| 方案 | R-SUPERWORKS-CONFLICT（每项目） | R-RECOGNITION-GAP 变化（每项目） | pass |
|---|---|---|---|
| current（2594dbe） | 2 | 基线 | 不变 |
| 仅豁免祖先/后代（`_coincident_ports`） | 0 | +5（端点身份变为未解析） | 不变 |
| 仅丢弃“instance≠owner”的父路径副本 | 2 | 不变 | 不变 |
| 两者组合 | 0 | +5（线圈针脚无标签，INCOMPLETE） | 不变 |

组合方案的 5 条新缺口原因码为 `missing_label_reference`、`unresolved_endpoint_identity`、`unresolved_pin_text`（即线圈端子没有可解析的文字标签），属于真实的未解析缺口，不是冲突。

“instance≠owner”副本规则经核验：p016、p061 为 0 条；p041–p044 各 4 条，共 16 条，每条都在归属实例下有对应的本体记录（16/16）。

### 3.4 修复建议与预计变化

- 通用修复（推荐两步）：
  1. 在 `_endpoint` 入口丢弃 `instance_path != owner` 的端口副本（前提：归属实例存在本体记录）；或更根本地在 `_definition_ports` 中不向父路径输出嵌套 INSERT 的 termpoint（需复核 sw_ports 覆盖统计）。
  2. `_coincident_ports` 中，祖先/后代实例在同一接触（间隙 0）视为同一物理接点，不判竞争。
- 预计（已在 p041–p044 实测）：R-SUPERWORKS-CONFLICT 25 → 17（减 8，与 round25 数量一致）；R-RECOGNITION-GAP 增加 20（4 项目各 +5，均为 review 级、线圈端子无标签的未解析缺口）；pass 不变。全量 77 项目未实测，嵌套结构是否在其他项目出现需全量复跑确认。

## 4. 项 3：p061 S0025 的 4 条 R-PAIR-LOW-CONFIDENCE

### 4.1 对象

| 配对 | 值 | 线组 | 置信 | 状态 |
|---|---|---|---:|---|
| PC0066 | 11↔8 | GC0069 | 0.903 | review |
| PC0067 | 11↔8 | GC0070 | 0.903 | review |
| PC0073 | 11↔8 | GC0080 | 0.903 | review |
| PC0061 | 9↔9 | GC0063 | 0.809 | review |

r25 中同页无这四条；r25 对应的线组上是 SW 部件 pass（PC0069 `3-21KK-2↔3-21CD11`、PC0070 `1-21KK-2↔1-21CD11`、PC0080 `2-21KK-2↔2-21CD11`，以及 GC0063 上的 `1-21ZK-1↔1-21CD6` 等）。在 current 中，这些 SW 部件 pass 变为原生输出（`line_group_id` 为空），同端点，同样 pass。

### 4.2 图面

`png/LOWCONF_p061_S0025_overview.png`、`png/LOWCONF_p061_S0025_zoom160.png`：紫色 GC0063/69/70/80 为元件框的竖线（框内为端子 1–8、C+、R-、11、8 等），红色虚线的 review 配对落在框线上，连接的是框上端子号；同一框线上的 SW 部件配对（绿）也使用这条框线。判定：误报。框线不是导线。

### 4.3 根因

- `superworks_extractor.py` 的部件配对循环（约 L1880–1897）：`line_group_id = producer_groups[0].line_group_id if len(...)==1 else (old[0].line_group_id if old else None)`。6e0492e 之后该部件在 cur 中没有 V1 旧配对（`old` 为空，未逐层核实 V1 旧配对为何不再生成），原生输出的部件 pass 因此不再挂载框线组。
- 框线组因此不再被占用，进入 `pipeline.py` 的 `target_line_group_ids`（约 L336，只排除 closed_groups，而框线组不在其中），再由 `_extract_pairs_for_route` 的 `build_pairs` 做普通配对，得到 11↔8、9↔9 的 review 配对。
- 相关提交：6e0492e（target 过滤与原生优先）。未做反事实回放（未证明修复后的数字，见下）。

### 4.4 修复建议与预计变化

- 修复：（a）原生部件 pass 应携带其支撑框线组 id，使该组被占用；或（b）普通配对跳过仅含 BORDER 图层、且位于元件符号边界上的线组（`layer_hints == {BORDER}`）。
- 预计：R-PAIR-LOW-CONFIDENCE 17 → 13（p061 减 4）；pass 不变（4 条均为 review）。该预计未经回放验证。

## 5. 6 条 wire_component_mapping 新 pass（p064 S0009、p068 S0006）

- 6 条为三组“同一线组、同一文字 id、同一坐标”的左端值变化：`607→1n607`、`609→1n609`、`608→1n608`（p064）；`112→1-1n112`、`111→1-1n111`、`110→1-1n110`（p068）。
- evidence 中 `fixed_fact_normalizations` 记录了 `before`/`after` 与 SW 固定身份；DXF 上的原始文字为“607”（T0446）等。属 28d2511 的 fixed identity 归一化（P4 设备前缀，active_issues 中待裁决项）。
- 判定：不是新增的导线关系；是身份口径变化。应交用户裁决，不能算作误报或真实恢复。
- cf 回放中这 6 条不变（它们不属于 lattice 机制）。

## 6. 需要用户裁决的口径

1. 425 条的产品口径：端子导通是否要作为独立关系呈现（建议：不作为导线 pass）。
2. P4 固定身份归一化（6 条 wire，以及 28d2511 的 1,389 条配对）是否获批。
3. 8 条嵌套冲突修复后会把线圈端子暴露为 review 缺口（20 条），是否接受。

## 7. 产物

- `README.md`（本文件）
- `png/`（23 张）：
  - 项 1：`FP425_00`–`FP425_17`（18 例，分层抽样），`L1_p016_S0021_row1_overview.png`（概览）
  - 项 2：`CONF_p041_S0012_nested_port.png`、`CONF_p043_S0013_nested_port.png`
  - 项 3：`LOWCONF_p061_S0025_overview.png`、`LOWCONF_p061_S0025_zoom160.png`
- `tools/`：
  - `build_diff.py`、`diff_pass.py`、`analysis_425.py`：对齐与台账匹配
  - `lattice_test.py`：425 条结构检验（全量）
  - `build_sample425.py`、`render_fp.py`、`spec_sample1.json`：样例渲染
  - `bisect_p016.py`：按提交回放（git archive 源码）
  - `cf_compare.py`：反事实与 round25 的 pass 集合比较
  - `build_conflict_png.py`、`build_p061_png.py`：项 2、项 3 渲染
  - `summarize.py`、`results.json`：汇总数字
- 中间数据（不入库）：`.tmp/fp_verify_work/`（pickle 与样例清单）、`.tmp/fp_verify_src/`（git archive 源码与反事实副本：cf_skipfix、cf_nested、cf_owner、cf_both）、`.tmp/fp_verify_replay/`（回放输出）。

## 8. 局限

- 图面抽样 18 例，结构检验覆盖全部 425 条；项 1 的“每例都是误报”由结构检验支撑，图面只抽查了其中 3 张的细节。
- 反事实只在 p016–p021（项 1）与 p041–p044（项 2）上运行，未跑全量 77 项目；项 3 的修复未做反事实。
- “instance≠owner”规则只在 p016、p041–p044、p061 上核验。
- 未运行 pytest，未修改仓库代码；所有反事实改动均在 `.tmp/fp_verify_src/` 的副本中进行。
