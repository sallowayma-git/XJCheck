# L-07 修复：连接文字按锚点配对引线；旧链端口冲突保护

范围：T0（测试断言）、T1（`_connect_labels` 锚点配对）、T2（旧链端口号核对）。未改 rules.py、component_diagrams.py 等文件，未做 git 操作，未全量回放。

## 修改

### src/dwg_audit/extract/superworks_semantics.py
- 新增常量 `CONNECT_ANCHOR_COINCIDENT_TOL = 0.5`。
- `_connect_labels`（约 L503）：
  - 距离改用 `text["anchor_x"], text["anchor_y"]`（即 `text_anchor_wcs`），不再用插入点 `x, y`。
  - 半径仍为 `max(5, 3×字高)`，以锚点为基准。
  - 先收集 `coincident`（某端点与锚点距离 ≤ 0.5）与 `nearby`（半径内）两组；`proposals = coincident or nearby`。
  - 排序仍为 (句柄差, 距离)；`ambiguous_connect_line` / `connect_line_geometry_not_unique` 判定逻辑不变。

### src/dwg_audit/audit/superworks_extractor.py
- 从 superworks_semantics 导入 `CONNECT_ANCHOR_COINCIDENT_TOL`。
- 新增 `_legacy_pairs_on_label_anchor_with_other_port(old, label, group_by_id)`：旧链 component pair 的 `component_port` 与 SW 端口号不同（且旧链非空），且该 pair 的 `line_group` 任一端点距连接文字锚点 ≤ 0.5，则返回该 pair。
- `extract_superworks_pairs` 连接文字循环：在构造 SW 新 pair 之前，若存在上述旧链 pair，则追加 `data.conflict_observations`（`kind=connect_line_port_disagreement`，`reason_code=connect_line_port_disagrees_with_legacy`），`continue`，保留旧链，不调用 `replace_claims`。
- 未写入 `sw_conflicts`：rules.py L1587、L4229 对任何非空 `sw_conflicts` 都有判定分支，写入会改变规则结果。该诊断仅在内存中的 `conflict_observations` 中；`report/superworks_artifacts.py` 只输出 `self_connection`，所以该诊断目前不会落盘（需要改 artifacts 文件，超出本次范围）。

### tests/unit/test_superworks_semantics.py
- 第 102 行：`test_dangling_stale_and_unattached_are_observable` 的断言由 `stale_label_reference` 改为 `label_far_from_symbol`（双向、可解析、距离约 141）。仅此一处。

### tests/unit/test_superworks_loop_l07.py（新增，11 用例，全部通过）
- 锚点重合线优先于句柄更近的线。
- 句柄差并列的两条重合线 → `ambiguous_connect_line`（测试内先注册 appid 以固定句柄间隔）。
- n715 / n717 同页配对到各自引线（复现 L-07 p044 S0020 的几何）。
- 半径回落：锚点 4 单位内的线可配对。
- GND 类偏移 3.6 仍可配对（回落规则保留）。
- 超过半径的引线仍为 `unresolved_connect_line`。
- 非双向远距标签仍为 `stale_label_reference`（T0 要求的 stale 覆盖，放在新文件中）。
- T2 辅助函数：端口不一致且旧链几何吻合 → 保留；端口一致 → 不保护；几何偏离 1.0 → 不保护；旧链端口未记录 → 不保护。

## 验证

### 单元测试
- `pytest tests/unit/test_superworks_loop_l07.py -q`：11 passed。
- `pytest tests/unit -q`：**1694 passed, 1 skipped, 1 failed**。
  - 失败项：`tests/unit/test_superworks_semantics.py::test_component_handle_adjacency_is_not_geometric_proof`（约第 214 行，断言 `result.line_handle == far.dxf.handle` 且 `connect_line_geometry_not_unique`）。
  - 原因：该用例中 TEXT 无对齐，锚点即插入点 (20,0)，恰好位于 `near` 线端点 (20,0) 上（距离 0）；`far` 线距离 4。按 T1 规则“优先选择端点与锚点重合的线”，应选 `near`。该断言与 T1 规则直接冲突，不是回归之外的偶然失败。
  - 按任务约束未改动该用例（只允许改第 102 行那一处）。**需要主线程决定**：（a）改写该用例为 T1 语义（期望 `near`，且不再有 `connect_line_geometry_not_unique`），或（b）放弃 T1 的“重合优先”规则。
- 修复前（P 状态）的基线：1683 passed，1 failed（即 T0 那条）。

### 单页回放（`replay.py --snapshot loopQ_src --projects p043 p044 p040 p000 p052`）
- 改动后产物：`.tmp/loopQ_probe`；改动前产物（同一代码，仅撤回 T1，T2 本身无法在 HEAD 中撤回，改动前快照 = HEAD 的 superworks_extractor.py + 撤回 T1 的 superworks_semantics.py）：`.tmp/loopQ_probe_before`。
- 改动前产物与 `.tmp/superworks_round5_full` 逐项一致（issue 与 pair 数均相同）。

#### p044 S0020（1-21ZKK1 / 1-21ZKK2，KK3P 实例）

| 端口 | 1-21ZKK1（改后） | 1-21ZKK2（改后） | 改前 |
|---|---|---|---|
| 1 | 1-21UD1 | 1-21UD6 | 同 |
| 2 | 1-21n713 | 1-21n719 | 同 |
| 3 | 1-21UD2 | 1-21UD7 | 同 |
| 4 | **1-21n715** | **1-21n721** | ZKK1-4→n717、ZKK2-4→n723（错，PCK0038、PCK0032） |
| 5 | 1-21UD3 | 1-21UD8 | 同 |
| 6 | **1-21n717** | **1-21n723** | 缺失（无 pair） |

- 引线几何：2E079（端口 4，x=368.75）与 2E07D（端口 6，x=385）分别与 "& 1-21n715" / "& 1-21n717" 锚点重合（距离 0.0 / 0.0），与 L-07 README 第 2 节一致。
- 改前后 KK 值级对比（左值、右值、端口）：仅上述 4 条变化（2 条错误移除，2 条恢复），其余 KK 引脚值不变（部分只是 `component_body` 或 `left_text_id` 表示变化，不影响映射）。
- R-ONE-TO-MANY：2 → 0。
- README 第 3 节“其余 44 个引脚”：值级未变化，沿用原核对结论。注意 XJDZ9 块新增 `1-1KK-4→1-1Q2D10`、`1-1KK-C+→1-1Q2D5`，属非 KK 块，未在本次几何核对范围内。

#### p043
- 同样的 4 条变化（ZKK1/ZKK2 的 4→6 修正与恢复），R-ONE-TO-MANY 2 → 0。

#### p040 KZKK-1..4（任务书写的 PCK0017/18 在当前产物中不存在）
- 当前 p040 中不存在 `2-1n-1→KZKK-1`、`2-1n-3→KZKK-3` 两条旧链 pair（改前与改后均无）。KZKK-1..4 的映射与改前完全一致（JD8、K-5、JD3、K-6），截图 `L07_p040_KZKK_unchanged.png` 核对端口 1/2/3/4 的位置与终端编号一致。
- 结论：README §6 中关于 p040 PCK0017/18 的离线推断未在回放中复现。

#### p000 1A3A7（文字 "1YD2"，锚点 (55.0, 246.79)）
- 改前：标签带有 `connect_line_geometry_not_unique` 与 `competing_connect_line_labels`，未产生 SW pair；所选引线 1A3A8（端口 102，y=241.79）距锚点 5.0。
- 改后：引线 1A3A4 端点与锚点重合（0.0），端口 101 段 (55.5..56.5, y=246.79) 距锚点 0.5；产生 `1n101 → 1YD2`（conn 1A3A4）与 `1n102 → 1YD9`（conn 1A3A8，原本也无 SW pair）。
- 截图 `L07_p000_1A3A7_leader.png`：“1YD2” 紧贴第 01 行，“1YD9” 位于第 02 行，改后正确。

#### p052 3CC87（文字 "1-42TD1 @"，锚点 (105.17, 241.0)）
- 改前：标签带有上述两条 reason，未产生 SW pair（旧链 `1-42nCOM1-3→1-42TD1` 保留）。
- 改后：引线 3CC84（x=105.17，端口 COM1-3，段距锚点 1.0，引线端点距锚点 0）。新增 `1-42nCOM1-3 → 1-42TD1 @`（conn 3CC84）与 `1-42nCOM1-4 → 1-42TD2 @`（conn 3CC88）。
- 截图 `L07_p052_3CC87_leader.png`：标签与第 3 号端子对齐，改后正确。

#### 截图（ezdxf 1.4.4，ColorPolicy.COLOR_SWAP_BW，matplotlib Agg）
- `loop/L-07/L07_p000_1A3A7_leader.png`
- `loop/L-07/L07_p052_3CC87_leader.png`
- `loop/L-07/L07_p040_KZKK_unchanged.png`
- `loop/L-07/L07_p043_port103_GND_competition.png`（额外，见下节问题 2）

### 5 项目对比（issue 与 pairs，对照 `.tmp/superworks_round5_full`）

round5 与改前完全一致，下表“改后”对照 round5：

| 项目 | issue 改前 → 改后 | 差异 | pairs 改前 → 改后 | component_mapping 改前 → 改后 |
|---|---|---|---|---|
| p043 | 4 → 2 | R-ONE-TO-MANY 2 → 0 | 2813 → 2943 | 373 → 503 |
| p044 | 4 → 2 | R-ONE-TO-MANY 2 → 0 | 2833 → 2967 | 378 → 512 |
| p040 | 3 → 3 | 无 | 2353 → 2415 | 375 → 437 |
| p000 | 2 → 2 | 无 | 1351 → 1417 | 184 → 250 |
| p052 | 0 → 0 | 无 | 655 → 697 | 88 → 130 |

其它 pair_kind（table_mapping、ordinary_pair、wire_component_mapping、semantic_mapping、bridge_mapping、continuation）数量全部不变。

#### component_mapping 差异逐类说明
- **同值替换（replaced）**：改前的旧链或 SW pair 被新 SW pair 替换，左值、右值、端口相同，仅 `left_text_id`（取自 SW 元件标签）或 `component_body` 表示变化。
  - p043 38、p044 38、p040 18、p000 20、p052 2。
  - 其中 strip_two_port_component 的替换（p043 30、p044 30、p040 18、p000 20）即属此类。
- **新增（added only）**：新解析的连接文字（改前因 reason 或距离原因无 SW pair）。
  - p043 135、p044 139、p040 64、p000 66、p052 42。
  - 新解析的 155/159/68/68/44 条标签中，几乎全部为锚点重合（0.0，仅 p052 有 1 条半径回落、1 条超半径为原有）。另外 p040 出现 `1KK-1 → 1ZK-2,1KK-3` 类逗号分隔目的地，产生同一端口两条 pair，这是 SW 元数据的既有多目的地语义，但 R-ONE-TO-MANY 不检查 SW pair（`ordinary_pair_eligible=False`），因此不会报 issue。
- **移除且无同值替换（removed only）**：
  - p043 5、p044 5、p040 2、p000 0、p052 0。
  - 其中 2 条为本次要修正的错误 pair（1-21ZKK1-4→n717、1-21ZKK2-4→n723）。
  - 其余 3（p043/p044）与 2（p040）为 GND 类，见下节问题 2，是**回归**。

### 两个 p000/p052 的 1 条 changed 对照（pair 层面）
- p000 1A3A7、p052 3CC87 的映射变化已在上文单独说明。
- 其它四条被改变的引线（p043 2E43C、2E448；p044 2E07E、2E08A）改后端口均由 4 改为 6，与 L-07 README 一致；锚点到端口段距离为 1.0，改前为 16.25。

## 未解决 / 需要主线程决定

1. **单元测试冲突（必须处理）**：`test_component_handle_adjacency_is_not_geometric_proof`（test_superworks_semantics.py 约第 214 行）与 T1 的“重合优先”规则相矛盾。未改动，见上文。
2. **GND 类 pair 回归（5 条，p043/p044 各 3 条、p040 2 条）**：
   - 例：p043 port 103 的引线 330AF（端点 (129, 227.5)）。
   - 改前：“GND”（锚点 (127, 230.5)，距离 3.6）经回落规则选中 330AF，产生 `1-1n103 → GND`。
   - 改后：“& 1-1Q1D1”（锚点 (129, 227.5)，与端点重合）同样选中 330AF。两个标签都带 `competing_connect_line_labels`，两者都不产生 SW pair，`1-1n103` 完全丢失。
   - 截图 `L07_p043_port103_GND_competition.png` 显示：端口 103（第 03 行）的引线对应 “& 1-1Q1D1”，“GND” 属于第 01 行的接地符号，改前的 `→ GND` 是错误的，改后的 `→ 1-1Q1D1` 才正确，但被竞争规则抑制。
   - 建议（未实现，超出 spec 字面）：回落规则不选取已被某个标签以重合方式占用的线（即 fallback 候选中剔除被其它标签锚点重合的 `line_handle`）。这样 GND 不再误配，`& 1-1Q1D1` 得到唯一 pair。需要主线程批准后再改并重放。
3. **新增关联规模**：本次 5 项目共新解析 494 条连接文字（p043 155、p044 159、p040 68、p000 68、p052 44）（大部分为重合锚点），component_mapping 增加 42–134 条/项目。锚点规则的几何依据充分，但 README §6 预测的全语料 8222 条新关联尚未全量核对；建议在全量回放前先处理问题 2。
4. **T2 诊断不落盘**：`connect_line_port_disagrees_with_legacy` 只在内存 `conflict_observations` 中。5 个项目的回放中该分支**一次都未触发**（改前后所有被替换的旧链端口号都与 SW 一致），因此 T2 的效果只能靠单元测试证明。如需落盘，需修改 `report/superworks_artifacts.py`（超出本次范围）。
5. **`@` 值残留（既有问题，未修）**：SW 标签值中的 `@` 标记（如 "1-42TD1 @"）未被剥离，导致同一端口同时存在 `→ 1-42TD1` 与 `→ 1-42TD1 @` 两条近似重复 pair。改前 p052 已有 29 条此类 pair，改后增至 54 条；issue 未增加，但值级去重可能受影响。
6. **p040 PCK0017/18 不存在**：README §6 的离线推断未在回放中复现，本次未对其做改前后对比。

## 产物清理
- 已删除 `.tmp/loopQ_probe`、`.tmp/loopQ_probe_before`、`.planning/superworks-adapter/loopQ_src`、`.planning/superworks-adapter/loopQ_before_src`（一次性探测产物）。
- 保留：`loop/L-07/` 下的 4 张 PNG（另有 p044 既有截图）与本 FIX.md。

## Q2：回落规则不得抢占已被锚点重合文字占用的引线

### 修改
- `src/dwg_audit/extract/superworks_semantics.py` `_connect_labels` 分两遍：
  - 第一遍：每个连接文字收集锚点重合（≤ `CONNECT_ANCHOR_COINCIDENT_TOL`）的引线，按（句柄差，距离）取第一条，并将其锁定。
  - 第二遍：仅对第一遍无重合引线的文字做半径回落，候选排除第一遍已锁定的引线。回落后仍有多个文字争同一未锁定引线时，沿用原有 `competing_connect_line_labels` 处理。
  - 记录按原文字顺序输出，结果与文字在图中的先后无关。
  - `superworks_extractor.py` 本轮未改。
- `tests/unit/test_superworks_semantics.py`：仅改 `test_component_handle_adjacency_is_not_geometric_proof`。
  - 场景一（near 线端点与锚点重合，far 仅句柄相邻）：期望改为 `near`，且不再有 `connect_line_geometry_not_unique`。
  - 场景二（无重合线，两条线距离相同、仅句柄不同）：仍选句柄更近者，并标 `connect_line_geometry_not_unique`。
- `tests/unit/test_superworks_loop_l07.py` 新增 3 个用例（Q2-a）：
  - `test_offset_label_does_not_take_leader_locked_by_coincident_anchor`：复现 p043 port 103（GND 在前、`& 1-1Q1D1` 在后）。`& 1-1Q1D1` 得到引线，GND 为 unresolved。
  - `test_offset_label_falls_back_to_an_unlocked_leader`：GND 回落到未锁定引线，`& 1-1Q1D1` 仍取重合引线。
  - `test_offset_label_with_only_locked_leader_stays_unresolved`：无可用引线时 GND 不抢占。

### 单元测试
- `pytest tests/unit/test_superworks_semantics.py tests/unit/test_superworks_loop_l07.py -q`：31 passed。
- `pytest tests/unit -q`：1715 passed, 1 skipped, 1 xfailed（全部通过；运行时并行子代理的 rules.py/candidates.py 状态以当时磁盘为准）。

### 单项目回放（`replay.py --snapshot loopQ2_src --projects p043 p044 p040 p000 p052`）
快照于回放启动时（约 00:43:49）复制 `src`，其中 rules.py 为当时的并行修改版本；回放启动后 rules.py 在磁盘上又被修改（00:43），因此本次结果对应快照版本，与当前磁盘 rules.py 不一定一致。

| 项目 | issue（round5 → Q2） | pairs（round5 → Q2） | component_mapping | 仅删除 | 仅新增 |
|---|---|---|---|---|---|
| p043 | 4 → 2（R-ONE-TO-MANY 2 → 0） | 2813 → 2946 | 373 → 506 | 5 | 138 |
| p044 | 4 → 2（R-ONE-TO-MANY 2 → 0） | 2833 → 2970 | 378 → 515 | 5 | 142 |
| p040 | 3 → 3 | 2353 → 2417 | 375 → 439 | 2 | 66 |
| p000 | 2 → 2 | 1351 → 1417 | 184 → 250 | 0 | 66 |
| p052 | 0 → 0 | 655 → 699 | 88 → 132 | 0 | 44 |

其它 pair_kind 数量与 round5 完全一致，变化只在 component_mapping。

验证项：
- p043、p044 的 `1-1n103 → 1-1Q1D1` 存在。
- p043、p044 的 ZKK 端口：ZKK1-4→n715、ZKK1-6→n717、ZKK2-4→n721、ZKK2-6→n723 均正确（两项目一致）。
- p040 无 `1-1` 前缀，对应为 `1n103 → 1GD1`、`2n103 → 2GD1`。
- p043、p044 的 `1-1n103 → GND` 不存在（见下表说明）。

#### component_mapping 仅删除条目逐条说明
| 项目 | 旧 pair | 判定 |
|---|---|---|
| p043 | `1-1n103` port103 → GND | 有替代：同端点（port 103）新 pair `1-1n103 → 1-1Q1D1` |
| p043 | `2-1n103` port103 → GND | 有替代：`2-1n103 → 2-1Q1D1` |
| p043 | `1-21n103` port103 → GND | 有替代：`1-21n103 → 1-21DK1-4` |
| p043 | PCK0038 `1-21ZKK1-4` port4 → 1-21n717 | 无替代：错误对，应为 `1-21ZKK1-4 → 1-21n715` |
| p043 | PCK0032 `1-21ZKK2-4` port4 → 1-21n723 | 无替代：错误对，应为 `1-21ZKK2-4 → 1-21n721` |
| p044 | 同 p043 的 5 条 | 同上（3 条有替代，2 条 ZKK 错误对无替代） |
| p040 | `1n103` port103 → GND | 有替代：`1n103 → 1GD1` |
| p040 | `2n103` port103 → GND | 有替代：`2n103 → 2GD1` |

- 「仅删除无替代」条目：p043 2、p044 2、p040 0、p000 0、p052 0。p043/p044 的 2 条即 ZKK 错误对；p040 不含 ZKK 错误对（与 L-07 FIX 的“p040 PCK0017/18 不存在”一致）。
- 与 Q 版本相比，GND 相关的 3/3/2 条「移除」**没有恢复**。原因：截图 `L07_p043_port103_GND_competition.png` 显示引线 330AF 水平位于 `& 1-1Q1D1` 行（端子 03，port 103），GND 文字的引线是另一条线（L 形、指向接地符号）。因此 `1-1n103 → GND` 本身是错误关联，正确结果是 `1-1n103 → 1-1Q1D1`，它已恢复。若任务书的“恢复”指保留旧 GND 对，与截图证据相反，需主线程确认。

### 连接文字「 @」后缀统计（5 项目，只报告，未修改）
`sw_connect_labels` 的 value 中含 "@" 共 94 条：
- 末尾为 " @"（如 "1-42TD1 @"）：37 条（p000 6，p052 31，其余 0）。
- 开头为 "@ "（如 "@ 1-21WD1"）：57 条（p043 12，p044 12，p040 8，p000 2，p052 23）。
- 同时首尾都有：0 条。
- 5 项目连接文字总数：487 + 496 + 417 + 231 + 138 = 1769（pass 后的 sw_connect_labels 记录数）。

### 未解决 / 需要主线程决定
1. GND 对是否“恢复”，见上文，需确认（当前判断：不恢复，GND→1-1n103 是错误对）。
2. 本次 `_connect_labels` 锁定的是第一遍每条文字选中的那一条引线（未锁定同一文字的其它重合候选）。若要求锁定所有重合引线，需另行确认。
3. 「 @」后缀仍未剥离（同一端口可能同时有 `→ 1-42TD1` 与 `→ 1-42TD1 @`），属既有问题，未修。

### 产物清理
- 已删除 `.tmp/loopQ2_probe` 与 `.planning/superworks-adapter/loopQ2_src`。
- 分析脚本仅位于 scratchpad，未写入项目目录。
