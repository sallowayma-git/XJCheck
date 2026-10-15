# 任务：提升 SuperWORKS 识别与三引擎协调的精度

在 `F:\workspace\XJToolkit` 上工作。这是二次接线图（DWG→DXF）的端子、导线审计工具。最近几轮的改动，让识别出的元件和端子数量明显增加，覆盖率也提高了。现在的重点是**精度**：通过的配对要准，报出的问题要真。

## 一、必须遵守的口径（用户已经定下，不得改变）

1. **SuperWORKS 优先，三引擎协调。** 主路由是 SuperWORKS（SW）属性识别，依据 DXF 里的 LD_* XDATA、XRECORD 和 TERMPOINT。SW 闭合不了的缺口交给 V1（手写规则路由）或 V2（几何端口推断）。三个引擎都闭合不了的，才作为问题报出。
2. **宁可报出，也不静默放过真实问题。** 只允许减少误报；凡是会把真实问题藏起来的改动，一律不做。
3. **不做特判。** 禁止按项目、取值、句柄或块名写特判，也禁止对 SW 来源整体豁免。所有判据都要能泛化到新图纸：只依赖 SW 元数据和几何原理。遇到无法归类的形态，写进未知形态清单，供人工复核。
4. **装置内部连接静默丢弃。** 装置内部连接指装置端子（如 1n112）与同一装置标签的内部元件之间的连接，内部元件包括 1n-DC、光耦、线圈、电阻、未登记块的引脚。这类连接不进入匹配，从覆盖率分母中剔除，台账原因记为 `discard_reason=device_internal`。例外：同一装置两个端子之间的背板跳线（如 1-21n532↔1-21n332）属于外部接线，必须保留。
5. **导线在端子本体和元件符号处断开。** 每一段都连到它相邻的端子或元件，不能把一整行合成一个线组。
6. **叠放的矛盾文字取最晚的一批。** 按句柄先后判断；判断不出先后时，报待核验，并写明“检测到文字重叠”。
7. **GND 公共地合法，不报多对一。** 端口无标注的报出，说明里写清“无标注”。
8. **不改 V2 模块和 `symbol_port_proposal.py`，不加 PDF/OCR。**

## 二、现状与基线

- 分支 `superworks-loop`。远端是 sallowayma-git/XJCheck；推送遇到 403 时，执行 `gh auth switch -u sallowayma-git`。
- 规划和证据文档在 `.planning/superworks-adapter/loop/`。先读这几份：
  - `active_issues.md`
  - `STATUS-2026-10-15/README.md`
  - `GAP-TRIAGE/README.md`
  - `FP-VERIFY/README.md`
  - `LEGACY-CENSUS/README.md`
  - `PIN-1/README.md`
  - `PIN-S/README.md`
  - `DEV-INT-DISCARD/README.md`
  - `WIRE-BREAK/README.md`
  - `P2-BACKPLATE/IMPL.md`
- 协调模块的设计与进度在 `.planning/engine-coordination/` 下，看 `task_plan.md`、`progress.md`、`findings.md`。
- 研究基线是第二十五轮：`.tmp/superworks_round25_full`，代码快照 `.planning/superworks-adapter/round25_full_src`。当时 issue 38 条；剔除装置内部后，严格覆盖率 81.99%，含跨页延续 84.40%。
- 协调模块（HEAD 2594dbe）的全量输出在 `.tmp/engine_coordination_full_acceptance/current`。
- 回放命令：`python .planning/superworks-adapter/replay.py --output <dir> --snapshot <dir> --workers 3 [--projects p001 ...]`。冻结的 DXF 缓存由 `.planning/superworks-adapter/corpus_manifest.json` 指向，只读，不要删。
- **另一组修复正在进行。** 主线程的子代理正在改：
  - `superworks_extractor.py` 和 `superworks_semantics.py`：FP-FIX，修复 425 条 lattice 误恢复、8 条嵌套重复冲突、p061 边框低置信；
  - `recognition_coordinator.py`：GAP-COORD，缺口闭合门禁的前 4 步。

  这两项提交之前，不要改这三个文件。

## 三、任务

### 阶段 0：先建精度基准（只读，不改 src）

1. 在 HEAD 的全量输出上，按以下维度给 pass 配对分层：
   - 来源：SW 原生、SW 线路记录（LOGGEN/PCL）、SW 引脚身份（PIN-1 symb2_text_slot）、V1 被 SW 佐证、纯 V1、背板佐证；
   - `pair_kind`；
   - 页面类型；
   - 项目家族。
2. 每一层随机抽样，每层至少 20 例；大的层按比例增加。用 DXF 渲染局部截图，目视判断配对两端是不是真实连接的两个对象。
3. 算出每层的精度和 95% 下限，找出错误集中的形态。
4. 对 review 配对和 issue 也按类抽样，算出“确实需要人工核对”的比例。
5. 产出放在 `.planning/superworks-adapter/loop/PRECISION-BASELINE/`：README（中文，给出精度表和错误形态 Top 10）、截图、工具脚本。

### 阶段 1：按错误形态逐个修复（等阶段 0 和上面两项修复都提交后再动手）

每个切片按这个循环做：

1. 选一个错误形态，读 DXF 或截图定位根因。
2. 写通用修复：判据基于元数据或几何，并写清新图纸遇到同类情况怎么处理。
3. 加单元测试，必要时加合成 DXF 夹具。
4. 跑 `python -m pytest tests -q`。必须是全量，包括 integration，不能只跑 unit。
5. 单页验证：重跑出问题的那一页，确认这页所有端子都正确。
6. 10 个项目回放，与基线对比：issue 按 rule+message+sheet 逐条比；pairs 按状态和类别比；覆盖率各口径比。
   - 每条新增 issue 都要截图判断：真问题保留，误报必须修掉。
   - 新增或升为 pass 的配对，抽查至少 30 例。
7. 达标后跑全量回放（77 个项目）。
8. 更新规划文档，按切片单独提交并推送；清理不再需要的临时目录。

候选切片（先按阶段 0 的数据排定优先级，下面只是参考）：

- **PIN-1 的 4,802 条 SW 引脚身份配对**：抽样 158/158 正确，但只有单人判定。做一次独立的二次核验，至少 149 例，达标后再决定能否升为 pass。
- **协调模块的 P4 设备前缀补全**（例如 `607→1n607`，提交 28d2511，共 1,389 条）：逐类核验，判断是否会引入错误身份。
- **V2 疑似错绑**：271 条 V2 文字与端子身份不一致；判断能否用 V2 做补证，或者应该停止使用。
- **低置信错配**：多为把相邻导线的接点号错配到本线；**p057 有 95 条背板前缀**取自 MARK 层模板字段。
- **线组层残留**：283 条穿越符号的 discard 冗余，以及 WIRE-BREAK 尚未实现的形态 T7（框线穿越）、T8（T 接）、T11（空白端）。
- **GAP-TRIAGE 第 6 步**：已登记符号引脚的几何挂接（1,456）和未登记引脚的脚号文字（842）。每类抽检至少 30 例，确认精度后才能开放。

### 不要做（需要用户先裁决）

- 端子排竖向轨线 T 接（G1T）的证据口径；
- 无脚号元件的连接是否计入覆盖；
- DC/DC 模块算外部还是内部；
- 改变 issue 的呈现方式。

遇到这几项，只出评估，不实施。

## 四、交付

- 每个切片完成后，用中文给出：改了什么（文件和函数）、精度前后对比、issue 和 pairs 变化及逐条判断、覆盖率、测试结果、遗留风险。
- 结论必须有截图证据。子代理说某个失败“原本就有”，要用 `git worktree` 在上一个提交上复核。
- 保持仓库干净：大的中间表放 `.tmp`；规划目录只留 README、少量有代表性的截图和工具脚本。
