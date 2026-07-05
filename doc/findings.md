# Findings

状态：已完成规则层聚类、报告复核增强，并基于主验证集完成一轮 Pair 分流与候选召回优化，进入继续压降单侧缺失与提升高置信 Pair 占比阶段。

更新时间：2026-07-05

用途：作为当前阶段的读图发现文档，记录已经确认的样本事实、工程约束、当前仓库实现状态，以及会直接影响实现与验收的关键结论。后续每完成一个里程碑，都应回写本文件。

## 1. 当前任务理解

基于 [任务书.md](./任务书.md) 和 [deep-research-report.md](./deep-research-report.md)，本项目 MVP 的目标明确为：

- 输入一套项目级 DWG 图纸。
- 在本地离线环境中抽取水平连接线两端数字。
- 建立 pair，并执行跨页一致性校验。
- 输出带证据链、置信度和定位信息的 findings / audit 报告。

这不是完整 CAD 软件，也不是电气语义理解系统。当前优先级仍然是“证据先行”，而不是“黑盒结论先行”。

## 2. 当前仓库真实状态

当前仓库不是空目录重建状态，已经存在可运行的 Python 实现骨架和单元测试：

- [pyproject.toml](/F:/workspace/XJToolkit/pyproject.toml)
- [src/dwg_audit/cli.py](/F:/workspace/XJToolkit/src/dwg_audit/cli.py)
- [src/dwg_audit/pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py)
- [src/dwg_audit/ingest](/F:/workspace/XJToolkit/src/dwg_audit/ingest)
- [src/dwg_audit/extract](/F:/workspace/XJToolkit/src/dwg_audit/extract)
- [src/dwg_audit/audit](/F:/workspace/XJToolkit/src/dwg_audit/audit)
- [src/dwg_audit/report](/F:/workspace/XJToolkit/src/dwg_audit/report)
- [src/dwg_audit/ui/app.py](/F:/workspace/XJToolkit/src/dwg_audit/ui/app.py)
- [tests/unit](/F:/workspace/XJToolkit/tests/unit)

直接结论：实现不是从零开始，而是在已有主链路上对齐任务书、补足抽取能力、增强证据链并完成样本验证。

## 3. 样本项目盘点

当前 `test/` 下已确认有两套项目级样本根：

1. [110kV变压器保护柜](/F:/workspace/XJToolkit/test/110kV变压器保护柜)
2. [变压器测控柜(2圈变，2台测控)](</F:/workspace/XJToolkit/test/变压器测控柜(2圈变，2台测控)>)

已确认事实：

- 当前两套项目根分别为：
  - `WBH-812E-E1SA(二侧差动+调压)+WBH-813E-E1SH+WBH-813E-E1SH+WBH-814E-E1SA`
  - `变压器测控柜(2圈变，2台测控)`
- 当前 `test/` 下共有 `52` 个 DWG。
- 第一套项目 `28` 页，第二套项目 `24` 页。
- 第一套仍作为主验证集；第二套不再视为“损坏容错集”，而应作为独立页型补充验证集。

## 4. DWG 有效性事实

对当前 `test/` 两套项目重新用仓库扫描逻辑核对后，已确认：

- 有效 DWG 头（`AC10*`）共 `52` 个。
- 当前两套样本中未再观察到无效 / 损坏 DWG 头。

项目分布：

- 第一套项目：有效 `28`，无效 `0`。
- 第二套项目：有效 `24`，无效 `0`。

直接结论：

- 文件级容错设计仍然必要，但当前主样本假设应从“存在大量损坏页”修正为“当前两套样本整体可转、可扫、可形成完整项目级基线”。
- `manifest` 和 `findings` 仍必须记录每张图的转换成功、失败和失败原因，因为这仍是实际工程输入的基础保障。

## 5. Sidecar 与排序发现

### 5.1 `.prj`

当前两套样本的 `.prj` 都已经能被现有解析链读出页信息：

- 第一套 `.prj`：`gb18030`，状态 `parsed`。
- 第二套 `.prj`：`gb18030`，状态 `parsed`。

实现要求：

- 当前样本上的 `.prj` 已经不是主要阻塞项，后续排序与页号策略应优先复用 `.prj` 页序。
- 但从架构角度看，`.prj` 解析仍需保留“无法解析时回退到文件名 / 标题推断”的兜底路径，不能因为当前样本都可解析就删除回退能力。

### 5.2 `LdDzbInfo.xml`

两套样本的 `LdDzbInfo.xml` 均可稳定提取设备名和端子排信息，可进入：

- `manifest.json`
- `findings/terminal_strips.parquet`
- findings 摘要中的端子排元数据说明

## 6. 页号与命名事实

保护柜样本中存在重复页号：

- `04 标牌及压板内容示意图.dwg`
- `04 交流回路图1.dwg`

直接结论：

- `sheet_no` 不能作为唯一键。
- 必须独立维护 `sheet_id` 与 `sheet_order`。
- 报告与证据链中必须同时保留 `sheet_order + filename + sheet_no`。

## 7. ODA 与转换约束

已确认本机安装了 ODA File Converter：

- `C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe`

同时确认了两个工程约束：

- ODA 不一定在 PATH 中，需要代码显式探测或补 PATH。
- ODA 对中文路径不稳定，因此正式实现应优先把待转换 DWG 复制到 ASCII staging 目录后再转换。

当前仓库实现已经采用 `cache/odafc_stage` 作为 staging 目录，并在转换时为每个源文件记录状态。

## 8. 当前实现能力盘点

当前代码已覆盖以下主链路：

- 项目扫描、DWG 头校验、页号/标题/类别推断
- `.prj` / `LdDzbInfo.xml` sidecar 解析
- ODA 转 DXF
- DXF 文本、线段、块抽取
- 水平线组归并
- 端点数字候选匹配
- Pair 构建
- 规则审计
- Findings / report 输出
- 最小 Streamlit 查看界面

本轮实现补齐后，重点会放在：

- findings / audit 目录结构与任务书对齐
- CLI 命令表面与任务书对齐
- `ATTRIB`、`POLYLINE`、manual bbox 抽取能力补足
- Issue 证据链增强
- 单元测试与真实样本链路验证

## 9. 主验证集与容错集策略

当前最合理的执行策略是：

1. 以第一套保护柜项目作为主验证集，验证完整 findings -> audit 闭环。
2. 以第二套测控柜项目作为补充验证集，重点验证不同页型、不同标题和不同连线版式下的抽取 / 配对稳定性。
3. 不再把第二套样本默认当成“损坏样本”；它需要和第一套一样接受完整 findings / audit 基线验证。

## 10. 当前待确认点

以下问题仍需通过代码跑通后确认：

- 第二套测控柜项目的完整 findings / audit 指标基线仍需补跑。
- 当前两套样本中的主体对象是否主要位于 `ModelSpace`，以及 `PaperSpace` 是否只占少量边缘用例。
- 图框与标题栏的启发式裁剪是否足够稳定。
- `ATTRIB` 进入文本候选后，数字候选召回率变化如何。
- 主验证集上的 Pair 精度、低置信度比例与主要误报来源。
- 默认启用的规则集中，哪些适合保留为自动 issue，哪些更适合先进入 review。

## 11. 下一步

下一步执行顺序：

1. 先补第二套样本的完整 findings / audit 实跑基线，避免只在第一套样本上调参数。
2. 继续压降单侧缺失 Pair，重点分析仍然停留在 `missing left/right candidate` 的页型模式。
3. 针对 `DIM` / `MARK` 层单字符数字做降权或过滤，先解决高置信 `pass` 明显失真的问题。
4. 在线组阶段补“跨 inline 数字的断线重连”，减少同一根横线被拆成 `? -> 723` / `723 -> ?` 这类伪问题。
5. 重做页型策略：背板图不要误入 `primary`，端子图 / 元件接线图是否进入 pair / audit 需要显式策略而不是默认漏掉。

## 12. 2026-07-05 主验证集实跑结果

对 `test/110kV变压器保护柜` 的主验证集已完成一次真实链路验证，结论如下：

- `analyze-project` 成功跑通，输出了完整 `manifest/findings` 目录。
- 主验证项目统计为：`file_count=28`、`converted_pages=24`、`primary_audit_pages=17`。
- 当前抽取规模为：`line_groups=585`、`terminal_candidates=3025`、`pair_candidates=623`、`pairs=585`。
- `run-audit` 已成功生成 `audit/` 报告，当前输出 `1133` 个 issue，且全部为 `review` 级。
- 规则分布集中在：
  - `R-PAIR-MISSING-SIDE = 548`
  - `R-PAIR-LOW-CONFIDENCE = 585`
- 当前没有出现项目级高严重度冲突问题，说明此阶段的主瓶颈不是图间冲突规则，而是 Pair 召回、单侧缺失和置信度不足。
- 报告层现已能直接展示审计概览、待复核 Pair 概览、结构化 issue 证据块与 findings 代表性 Pair 证据，人工复核路径明显比首轮实现更清晰。

## 13. 2026-07-05 Pair 分流与候选召回优化结果

本轮针对主验证集补了两类关键改动：

1. `TerminalCandidate` 不再把“数字位于端点内侧”的情况硬判为 `wrong_side` 拒绝，而是允许进入打分。
2. `Pair` 正式落地 `pass / review / discard` 三态分流，并在审计阶段跳过 `discard`，避免“没有任何数字证据”的线段刷屏进入 issue。

对同一主验证集重新跑 `analyze-project + run-audit` 后，结果变为：

- `pairs=585` 保持不变，但结构明显改善。
- `both_present` 从 `37` 提升到 `102`。
- `pass` 从 `0` 提升到 `29`。
- `review` 为 `239`，`discard` 为 `317`。
- `issues` 从 `1133` 降到 `482`。
- 当前规则分布为：
  - `R-PAIR-LOW-CONFIDENCE = 239`
  - `R-PAIR-MISSING-SIDE = 231`
  - `R-DUPLICATE-PAIR = 8`
  - `R-CROSS-PAGE-CONFLICT = 2`
  - `R-ONE-TO-MANY = 2`

直接结论：

- 主流程已不再把所有 Pair 都压成 `review`。
- `discard` 分流已经开始承担“过滤明显无证据线段”的职责，符合任务书中 high-confidence / review / discard 的阶段 B 设计。
- 目前剩余瓶颈已从“完全没有 pass”转为“review 仍偏多，且单侧缺失仍有 231 条”，后续应继续聚焦页型特征、线段过滤和端点召回规则。

## 14. 2026-07-05 桌面端 sidecar 后端契约落地

为给后续 Tauri 桌面端直接接入，本轮已补一条最小可用的本地 sidecar 后端链路：

- 新增 CLI：
  - `analyze-session`
  - `list-recent-projects`
  - `load-result`
  - `purge-session`
- 新增 `DesktopEventWriter`，当前可输出 JSONL 事件流，已覆盖：
  - `run_started`
  - `project_started`
  - `progress`
  - `page_started`
  - `page_finished`
  - `warning`
  - `issue_found`
  - `audit_finished`
  - `project_stored`
  - `run_finished`
- 新增轻量 SQLite 状态库存储最近项目与 issue 摘要，当前已保存：
  - `run_id / session_id / project_id / project_name`
  - `input_root / artifact_dir`
  - `sheet_count / pair_count / issue_count`
  - issue 摘要行：`rule_id / severity / title / confidence / filename / sheet_no / 左右值 / evidence`

真实 smoke 结果：

- 已用 `analyze-session` 在 `110kV变压器保护柜` 样本上跑通一次完整链路。
- `list-recent-projects` 能返回最近项目摘要。
- `load-result` 能从 SQLite 成功载入最近一次项目结果与 `482` 条 issue 摘要。

直接结论：

- 桌面端已经不必直接拼装 Python 主流程命令，而可以围绕 sidecar 命令和 SQLite 最近项目结果继续实现。
- 当前 M9 后端侧最小契约已经出现，后续重点转向 Tauri 壳接入、过程页消费事件流、结果页消费最近项目结果。

## 15. 2026-07-05 桌面端脚手架推进

本轮已补的桌面端相关进展：

- `render-preview` 已作为 CLI/desktop sidecar 命令落地，能够基于 SQLite 最近项目结果重建 SVG 预览。
- 桌面端新增了 `set-issue-status` CLI，并把 issue 状态写回链打通到：
  - SQLite `issue_summaries`
  - `audit/issues.parquet`
  - `audit/issues.json`
- `apps/desktop` 已补齐 React + TypeScript 的最小可运行桥接：
  - `types.ts`
  - `lib/mockData.ts`
  - `lib/desktopApi.ts`
- 结果页已能展示并修改 `open / ignored / resolved / false_positive` 状态；非 Tauri 环境下通过 mock 数据联调。
- 当前前端检查状态：
  - `npm run check` 通过
  - `npm run build` 通过
- 当前 Rust 工具链仍未安装，因此 `src-tauri` 仅完成最小骨架和命令占位，未做原生编译验证。

直接结论：

- M9 不再只停留在 Streamlit 内部验证；正式桌面端壳已经进入可持续迭代状态。
- 下一步前端重点不再是“从零搭壳”，而是把 Tauri native bridge、目录选择、真实事件转发和真实 SQLite / preview 命令接起来。

## 16. 2026-07-05 第一套样本只读复核纠偏

针对现有 `.tmp/sample_run_v2` 与当前配置做了新一轮只读核验，已确认以下高优先级问题：

- `pairs.parquet` 当前 `pass=29`，且这 `29` 条全部至少有一侧是单字符数字，例如 `6 -> 721`、`4 -> 720`、`2 -> 112`；这说明当前高置信 `pass` 指标并不可靠。
- 已接受候选几乎全部来自 `DIM` / `MARK` 层，统计为：
  - `accepted_by_layer = {'DIM': 615, 'MARK': 26}`
  - `accepted_single_char_by_layer = {'DIM': 316, 'MARK': 19}`
- 这说明当前“纯数字即候选”的策略会把尺寸号、小序号等局部数字误推成端子号，必须在高置信路径上尽快降权或剔除。
- 线组阶段当前仍使用 `line_gap_tolerance = 4.0`，见 [line_groups.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/line_groups.py:18)。该阈值对被 inline 数字切开的横线不够，容易把同一根线拆成多段，继而诱发 `missing-left/right`。
- 第一套样本中 `17-20` 背板图当前仍被纳入 `primary`，且已实际产出少量 pair / issue；而 `21-26` 元件接线图 / 端子图目前是 `secondary`，`pair_count=0`、`issue_count=0`。

直接结论：

- 后续优化优先级应先从“候选质量”和“导线粒度”下手，而不是继续放宽召回。
- 页型策略必须从启发式关键词判断升级为更可解释的白名单 / 黑名单 / review 机制，否则会持续出现“该进的不进、该排的不排”的结构性偏差。

## 17. 2026-07-05 第二套样本完整基线补跑

对第二套 `变压器测控柜(2圈变，2台测控)` 已直接补跑完整 `analyze-project + run-audit`，产物位于：

- [second_project_baseline](/F:/workspace/XJToolkit/.tmp/second_project_baseline)

当前得到的真实基线如下：

- `file_count=24`
- `sheet_count=24`
- `converted_pages=21`
  - 另外 `3` 页为正常跳过：`01 封面`、`02 目录`、`03 屏面布置图`
- `primary_audit_pages=13`
- `line_groups=672`
- `pair_count=672`
- `issue_count=921`
- `pair_status = {'review': 464, 'discard': 208, 'pass': 0}`
- `issue_rules = {'R-PAIR-LOW-CONFIDENCE': 464, 'R-PAIR-MISSING-SIDE': 457}`

页型覆盖补充事实：

- `17-18` 装置背板在第二套样本中当前是 `secondary`，`pair_count=0`、`issue_count=0`。
- `19-24` 元件接线图 / 左右侧端子图也全部是 `secondary`，`pair_count=0`、`issue_count=0`。

直接结论：

- 第二套样本并不存在 `.prj` 不可解析或 DWG 大量损坏的问题；它已经可以作为完整基线继续压测算法。
- 第二套样本上的主要瓶颈仍然是 `low_confidence + missing_side`，说明问题确实集中在候选和线组，而不是输入损坏。
- 第二套样本当前没有出现第一套那种“背板误入 primary”的现象，说明页型误判并不是全局统一，而是样本相关规则缺口。

## 18. 2026-07-05 候选降权 + inline 数字断线重连回归

本轮围绕两项高优先级问题先做了最小可回归整改：

1. `DIM/MARK` 层单字符数字降权，但不直接删除候选。
2. 在线组阶段增加“gap 中存在 inline 数字时允许桥接”的逻辑。

对第一套样本重新实跑后的结果，相比旧基线：

- 旧基线 `baseline_v2`：
  - `pair_status = {'discard': 317, 'review': 239, 'pass': 29}`
  - `issue_rules = {'R-PAIR-LOW-CONFIDENCE': 239, 'R-PAIR-MISSING-SIDE': 231, 'R-DUPLICATE-PAIR': 8, 'R-CROSS-PAGE-CONFLICT': 2, 'R-ONE-TO-MANY': 2}`
  - `pass_single_char = 29`
- 只做单字符降权后：
  - `pair_status = {'discard': 320, 'review': 265, 'pass': 0}`
  - `issue_rules = {'R-PAIR-LOW-CONFIDENCE': 265, 'R-PAIR-MISSING-SIDE': 231}`
  - `pass_single_char = 0`
- 再叠加 inline 数字断线重连后：
  - `line_groups: 585 -> 560`
  - `pair_count: 585 -> 560`
  - `pair_status = {'discard': 302, 'review': 258, 'pass': 0}`
  - `issue_rules = {'R-PAIR-LOW-CONFIDENCE': 258, 'R-PAIR-MISSING-SIDE': 227}`
  - `pass_single_char = 0`

直接结论：

- 单字符降权已经成功消除了“假高置信 pass”。
- inline 数字断线重连开始产生正向效果：线组数下降、`discard` 下降、`missing_side` 从 `231` 降到 `227`。
- 当前 `pass` 仍为 `0`，说明这两步主要完成的是“纠偏”和“去伪高置信”，还没有把真正可靠的高置信 pair 重新抬起来；下一轮应继续做候选分层与页型约束，而不是急着把阈值放松回去。

## 19. 2026-07-05 页型策略显式化回归

本轮已把页型判定从“类别 + 标题关键词混杂”改成“类别优先、标题兜底”：

- `二次原理图` 明确作为 `primary`
- `背板接线图 / 元件接线图 / 屏端子图` 明确作为 `secondary`
- `元件接线图` 不再因为 `.prj` 使用了粗粒度 `背板接线图` 桶而混在一起

对两套样本重跑后的关键结果如下：

第一套保护柜样本：

- 修正前（已含单字符降权 + inline bridge，但页型策略未修）：
  - `primary_pages=17`
  - `pair_status = {'discard': 302, 'review': 258}`
  - `issue_rules = {'R-PAIR-LOW-CONFIDENCE': 258, 'R-PAIR-MISSING-SIDE': 227}`
  - `17-20` 背板图仍误入 `primary`，共产生 `7` 个 pair、`4` 个 issue
- 修正后：
  - `primary_pages=13`
  - `pair_status = {'discard': 297, 'review': 256}`
  - `issue_rules = {'R-PAIR-LOW-CONFIDENCE': 256, 'R-PAIR-MISSING-SIDE': 225}`
  - `17-20` 背板图已全部退出主审计链，`pair_count=0`、`issue_count=0`
  - `21-23` 现明确标注为 `元件接线图`

第二套测控柜样本：

- 修正前后 `primary_pages` 都为 `13`
- `pair_status` 保持 `{'review': 464, 'discard': 208}`
- `issue_rules` 保持 `{'R-PAIR-LOW-CONFIDENCE': 464, 'R-PAIR-MISSING-SIDE': 457}`
- 变化主要体现在页型语义更准确：
  - `19-20` 不再显示为笼统 `背板接线图`
  - 现在明确归类为 `元件接线图`

直接结论：

- 第一套样本里“背板图误入 primary”已被直接修正，而且这不是纯粹分类美化，而是实际减少了无效审计对象与 issue 噪音。
- 第二套样本此前本就没有背板误入问题，因此页型修正主要改善的是“类别语义正确性”，没有引入回归。
- 当前页型策略已经从“关键词泄漏”升级为“显式决策”，后续若要把元件接线图或端子图纳入审计，应走新的显式策略分支，而不是再放任标题关键词把它们偷偷带进主链。

补充实现状态：

- 当前配置已新增 `audit_supplemental_categories` 入口。
- 默认仍为空，因此两套样本当前行为不变：`元件接线图 / 屏端子图 / 背板图` 仍默认排除在主审计之外。
- 如果后续要针对某一类页型做试跑，不必再改代码主逻辑，只需显式把类别加入 `audit_supplemental_categories`，对应页会进入 `supplemental` 审计角色并纳入 pair / audit 主链。

## 20. 2026-07-05 Supplemental 页型试跑结论

本轮对两类候选 supplemental 页型分别做了真实试跑：

- `元件接线图`：
  - 第一套产物：[supplemental_component_first](/F:/workspace/XJToolkit/.tmp/supplemental_component_first)
  - 第二套产物：[supplemental_component_second](/F:/workspace/XJToolkit/.tmp/supplemental_component_second)
- `屏端子图`：
  - 第一套产物：[supplemental_terminal_first](/F:/workspace/XJToolkit/.tmp/supplemental_terminal_first)
  - 第二套产物：[supplemental_terminal_second](/F:/workspace/XJToolkit/.tmp/supplemental_terminal_second)

相对当前 baseline 的关键对比如下：

- 第一套 baseline `[page_strategy_first](/F:/workspace/XJToolkit/.tmp/page_strategy_first)`：
  - `included_pages=13`
  - `line_groups=553`
  - `pair_status = {'discard': 297, 'review': 256}`
  - `issue_count=481`
- 第二套 baseline `[page_strategy_second](/F:/workspace/XJToolkit/.tmp/page_strategy_second)`：
  - `included_pages=13`
  - `line_groups=672`
  - `pair_status = {'discard': 208, 'review': 464}`
  - `issue_count=921`

把 `元件接线图` 作为 supplemental 纳入后：

- 第一套 `included_pages: 13 -> 16`，但 `line_groups / pairs / issues` 全部不变。
- 第二套 `included_pages: 13 -> 15`，但 `line_groups / pairs / issues` 全部不变。
- 逐页结果全部是 `pair_count=0`、`issue_count=0`：
  - 第一套 `21-23 元件接线图`
  - 第二套 `19-20 元件接线图`

把 `屏端子图` 作为 supplemental 纳入后：

- 第一套 `included_pages: 13 -> 17`，`line_groups: 553 -> 948`，新增 `395` 个 pair，且全部为 `discard`；`issue_count` 仍为 `481`。
- 第二套 `included_pages: 13 -> 17`，`line_groups: 672 -> 1114`，新增 `442` 个 pair，且全部为 `discard`；`issue_count` 仍为 `921`。
- 逐页结果如下：
  - 第一套 `24-27 端子图` 共新增 `395` 个 pair，`both_present=0`，全部 `discard`
  - 第二套 `21-24 端子图` 共新增 `442` 个 pair，`both_present=0`，全部 `discard`

直接结论：

- 当前不应把 `元件接线图` 默认加入 `audit_supplemental_categories`。它现在不是“噪音很多”，而是“几乎没有进入可审计几何主链”。
- 当前也不应把 `屏端子图` 默认加入 `audit_supplemental_categories`。它虽有大量真实线组，但在现有候选与配对策略下只会制造大批 `discard`。
- 如果后续要优先攻克一个 supplemental 页型，应先做 `屏端子图`，因为它已经暴露出明确的“几何存在、候选不对”问题；`元件接线图` 则更像抽取层尚未真正理解的块驱动页型。

补充实现状态：

- 生成型 `findings.json / findings.md` 已补充 `primary_audit_pages / supplemental_audit_pages / included_audit_pages` 三组指标，避免 supplemental 试跑时仍把纳入页数误读成“主审计页数”。

## 21. 2026-07-05 屏端子图候选归一化试跑

针对 `屏端子图` 当前“几何存在但候选全空”的问题，本轮没有先放大搜索窗口，而是先补了一条保守的页型专用候选规则：

- 仅在 `sheet_category = 屏端子图` 时生效
- 允许把类似 `1-21n110`、`5n602` 这类文本按尾部 `n###` 模式归一化成数值候选
- 规则入口位于 `build_terminal_candidates`
- 默认配置通过 `page_category_overrides` 提供，不改变非端子图页型行为

真实试跑产物：

- 第一套：[terminal_suffix_first](/F:/workspace/XJToolkit/.tmp/terminal_suffix_first)
- 第二套：[terminal_suffix_second](/F:/workspace/XJToolkit/.tmp/terminal_suffix_second)

相对旧的 `屏端子图 supplemental` 试跑结果：

- 第一套旧结果 `[supplemental_terminal_first](/F:/workspace/XJToolkit/.tmp/supplemental_terminal_first)`：
  - `pair_status = {'discard': 395}`
  - `accepted_candidates = 0`
  - `issue_count = 0`
- 第一套新结果：
  - `pair_status = {'discard': 370, 'review': 25}`
  - `accepted_candidates = 43`
  - `accepted_values` 开始出现：`602 / 108 / 311 / 420 / 110 / 109 / 430 / 419 / 601`
  - `issue_count = 51`

- 第二套旧结果 `[supplemental_terminal_second](/F:/workspace/XJToolkit/.tmp/supplemental_terminal_second)`：
  - `pair_status = {'discard': 442}`
  - `accepted_candidates = 0`
  - `issue_count = 0`
- 第二套新结果：
  - `pair_status = {'discard': 428, 'review': 14}`
  - `accepted_candidates = 20`
  - `accepted_values` 开始出现：`110 / 109 / 508`
  - `issue_count = 28`

结构性变化：

- 第一套 `missing numeric candidates on both sides: 395 -> 370`
- 第二套 `missing numeric candidates on both sides: 442 -> 428`
- 新增的问题不再是“完全无候选”，而是开始转成：
  - `missing left candidate`
  - `missing right candidate`

直接结论：

- 这一步证明端子图的主问题确实不只是窗口大小，更是“文本数值归一化规则过严”。
- 页型专用候选归一化已经把一部分端子图从“完全无数字证据”推进到了“存在单侧数字证据、进入 review”。
- 但当前仍没有把端子图推进到稳定的双侧 pair；说明下一轮还需要继续解决另一侧候选来源，而不是现在就把 `屏端子图` 默认纳入主审计。

## 22. 2026-07-05 屏端子图专用窗口扩展试跑

在补了 `n###` 尾码归一化后，又对 `屏端子图` 做了只针对该页型的窗口扩展试跑：

- 试跑配置：`endpoint_search_radius_x: 30`
- 产物：
  - 第一套：[terminal_radius30_first](/F:/workspace/XJToolkit/.tmp/terminal_radius30_first)
  - 第二套：[terminal_radius30_second](/F:/workspace/XJToolkit/.tmp/terminal_radius30_second)

相对上一轮仅有 suffix 归一化的结果：

- 第一套上一轮 `[terminal_suffix_first](/F:/workspace/XJToolkit/.tmp/terminal_suffix_first)`：
  - `pair_status = {'discard': 370, 'review': 25}`
  - `issue_count = 51`
- 第一套扩窗后：
  - `pair_status = {'discard': 3, 'review': 392}`
  - `issue_count = 784`

- 第二套上一轮 `[terminal_suffix_second](/F:/workspace/XJToolkit/.tmp/terminal_suffix_second)`：
  - `pair_status = {'discard': 428, 'review': 14}`
  - `issue_count = 28`
- 第二套扩窗后：
  - `pair_status = {'review': 442}`
  - `issue_count = 884`

结构性变化：

- 这一步几乎把 terminal 页从“无候选导致 discard”整体推成了“单侧已有值、另一侧缺失”的 `review`。
- 真实原因并不是 regex 不够，而是大量可被当前 `n(?P<value>\\d{3,})$` 直接抽值的文本此前落在 `18` 之外、约 `26` 左右的位置。
- 扩窗后并没有稳定形成高质量双侧 pair，主要还是把 issue 形态从 `missing both sides` 推成了大规模 `missing left/right candidate`。

直接结论：

- `屏端子图` 的页型专用窗口扩展确实是有效的，它能系统性提升“至少保住一侧数字证据”的比例。
- 但它的代价也非常明确：review / issue 量会显著放大，因此当前仍不应把 `屏端子图` 直接纳入默认主审计。
- 当前最合理的状态是：把这条能力保留在页型 override 中，作为后续继续攻 terminal 页时的实验默认，而不是把它误表述成“端子图已完成支持”。
- 当前代码默认配置已把 `屏端子图 -> endpoint_search_radius_x = 30` 写入 `page_category_overrides`；由于 `audit_supplemental_categories` 默认仍为空，这不会改变当前主审计链，只会改善后续针对 terminal 页的实验/补跑基线。

## 23. 2026-07-05 Missing-Side / Low-Confidence 语义收口

本轮把 `R-PAIR-MISSING-SIDE` 与 `R-PAIR-LOW-CONFIDENCE` 的边界按任务书原文收紧：

- `R-PAIR-MISSING-SIDE`：一端有可靠数字，另一端没有可靠数字
- `R-PAIR-LOW-CONFIDENCE`：左右端都有数字，但 pair confidence 处于 review 区间

直接实现变化：

- 对于缺任一侧数字的 `review pair`，不再额外生成一条 `R-PAIR-LOW-CONFIDENCE`
- `R-PAIR-LOW-CONFIDENCE` 只保留给“双侧都有值但仍不够高置信”的 pair

直接结论：

- 这一步不会改变 `pairs.parquet` 里的 `status=review` 分布
- 它只会减少 issue 层的重复表达，让“单侧缺失”不再被同时记成“低置信度”

按当前 `pairs.parquet` 结构推导的真实降噪幅度如下：

- 第一套主 baseline `[page_strategy_first](/F:/workspace/XJToolkit/.tmp/page_strategy_first)`：
  - `review_pairs = 256`
  - 其中 `missing_side_review_pairs = 225`
  - 理论 issue 数从 `481 -> 256`，净减 `225`
- 第二套主 baseline `[page_strategy_second](/F:/workspace/XJToolkit/.tmp/page_strategy_second)`：
  - `review_pairs = 464`
  - 其中 `missing_side_review_pairs = 457`
  - 理论 issue 数从 `921 -> 464`，净减 `457`
- 第一套 terminal suffix 试跑 `[terminal_suffix_first](/F:/workspace/XJToolkit/.tmp/terminal_suffix_first)`：
  - 理论 issue 数从 `531 -> 281`，净减 `250`
- 第二套 terminal suffix 试跑 `[terminal_suffix_second](/F:/workspace/XJToolkit/.tmp/terminal_suffix_second)`：
  - 理论 issue 数从 `949 -> 478`，净减 `471`
- 第一套 terminal radius30 试跑 `[terminal_radius30_first](/F:/workspace/XJToolkit/.tmp/terminal_radius30_first)`：
  - 理论 issue 数从 `1265 -> 648`，净减 `617`
- 第二套 terminal radius30 试跑 `[terminal_radius30_second](/F:/workspace/XJToolkit/.tmp/terminal_radius30_second)`：
  - 理论 issue 数从 `1805 -> 906`，净减 `899`

说明：

- 上述数字按 `pairs.parquet` 的 `review pair` 结构推导，不依赖历史 `issues.json` 是否在其他轮次被重跑覆盖。
- 这一步让后续 terminal 页实验的 issue 统计更可读，因为新增的 `review` 将更多表示“真实单侧缺失”，而不是“缺失 + 低置信度”双重重复。

## 24. 2026-07-05 一对多语义先收敛到 review / branch groundwork

任务书已经明确要求把一对多从“纯报错”改成 `branch / review / conflict` 三态；但按当前样本与基线，最稳的自动结论仍然只有 `review`。

本轮在规则层做了最小收口：

- `R-CROSS-PAGE-CONFLICT` 继续保留为显式冲突规则，只覆盖“高置信 pair 且跨页指向不同目标”的情况。
- `R-ONE-TO-MANY` 不再把所有多目标配对统一打成高严重度错误。
- 同页的一对多默认降为 `review`，并在 `evidence.one_to_many_classification` 中明确标记为 `review`。
- 预留了项目级白名单 `rules.one_to_many_branch_left_values`；命中后同页一对多可见地输出为 `branch`，但默认配置保持空列表，不会擅自放行。
- 跨页一对多不再额外重复生成 `R-ONE-TO-MANY`，避免和 `R-CROSS-PAGE-CONFLICT` 双重计数；冲突语义统一收口到后者，并在 evidence 中标记 `one_to_many_classification=conflict`。

直接结论：

- 这一步还没有实现“自动识别合法 branch”，只是把表达方式从“默认判错”收紧为“默认待复核，允许项目配置声明 branch”。
- 这样更符合任务书 `10.8` 的保守语义，也避免继续把 `R-ONE-TO-MANY` 当作粗粒度错误数量来追指标。
- 下一步若要真正把 `branch` 做稳，需要补“一对多簇复核表”和项目先验，而不是继续只在 severity 上调参。

## 25. 2026-07-05 findings 产物补充一对多簇复核表

为了把后续 `branch / review / conflict` 校准建立在稳定证据上，本轮在 `findings.json / findings.md` 里新增了“一对多簇复核表”。

当前表结构直接基于 `pairs.parquet` 的完整 pair 构建，不依赖历史 `issues.json`：

- 以 `left_value` 聚类，只保留“同一左值对应多个不同右值”的簇。
- 每个簇记录：
  - `cluster_id`
  - `right_values`
  - `sheet_ids / sheet_nos / filenames`
  - `classification / classification_reason`
  - `status_counts / confidence_bucket_counts`
  - `reciprocal_pair_count`
  - 每条边的 `pair_id / confidence / status / summary`
- 当前分类规则是：
  - `branch`：命中 `rules.one_to_many_branch_left_values`
  - `conflict`：跨页且簇内 pair 当前都属于高置信
  - `review`：其余情况默认保守进入复核

直接结论：

- 这张表不是最终规则输出，而是“可稳定复核的证据底表”。
- 它的意义在于：后续要不要把某些簇升成 `branch`，或者把哪些跨页簇真正收敛成 `conflict`，终于可以直接基于 findings 产物抽样，而不必反复依赖临时 issue 数量。

## 26. 2026-07-05 报告与 UI 显式展示 one_to_many_classification

在上一轮规则收口后，`one_to_many_classification` 虽然已经写进 issue evidence，但还只是“藏在 JSON 里”的状态，不满足“结果页可见”的要求。

本轮继续把这层信息显式露到现有展示链：

- `audit_report.md` 在 issue 详情里新增 `OneToManyTriage`
- `audit_report.html / issues.xlsx` 的 issues 表新增 `one_to_many_classification` 列
- Streamlit UI 的 Issues 表和 issue detail 也会直接显示该字段
- Streamlit UI 的 Summary 页会直接展示 findings 里的“一对多簇复核表”

直接结论：

- 到这一步，当前 CLI / report / UI 三条现有结果链都已经能看见 `conflict / review / branch` 这类一对多语义标签，不再要求用户手动翻 raw evidence JSON。
- 这仍然不等于最终桌面端结果页已完成，但至少“结构现象 + 风险分级”已经开始进入实际展示层，而不是停留在规则内部。

## 27. 2026-07-05 Tauri 原生桥接接入 Python sidecar / SQLite

此前 `apps/desktop` 虽然已经有 Tauri 2 + React + TypeScript 壳，但 `src-tauri/src/main.rs` 里的 5 个 command 全部还是 stub，桌面端实际只能回退 mock。

本轮把原生桥接接到了现有 Python CLI：

- `desktop_analyze_session`
  - 调用 `python -m dwg_audit.cli analyze-session`
  - 把 JSONL 事件逐行转发成 Tauri 事件
  - 末尾 `run_result` 转回前端需要的 `{ projects }`
- `desktop_list_recent_projects`
  - 调用 `python -m dwg_audit.cli list-recent-projects`
- `desktop_load_result`
  - 调用 `python -m dwg_audit.cli load-result`
- `desktop_render_preview`
  - 调用 `python -m dwg_audit.cli render-preview`
- `desktop_set_issue_status`
  - 调用 `python -m dwg_audit.cli set-issue-status`

同时对齐了桌面端本地路径策略：

- workspace root：`%LOCALAPPDATA%/dwg-audit/sessions`
- state db：`%LOCALAPPDATA%/dwg-audit/desktop_state.db`
- Rust 侧显式注入 `PYTHONPATH=<repo>/src`，避免依赖“当前环境已 pip install”这一前提

直接结论：

- 到这一步，桌面端最大断点已经不再是“没有 native bridge”，而是“本机缺少 Rust toolchain，暂时不能把这条桥真正编译运行起来做端到端验收”。
- 这属于环境缺口，不再是应用内 command 设计层面的空白。

## 28. 2026-07-05 桌面端停止真实错误回退 mock，并补结果页三态/分数展示

在原生桥接接通后，如果前端仍然“native 报错就静默回退 mock”，会把真实失败伪装成假数据，这和桌面 MVP 的目标相冲突。

本轮继续收口桌面前端行为：

- `desktopApi` 仅在非 Tauri 环境下使用 mock
- 在 Tauri 环境下，native 调用失败会把错误抛回 UI，而不是偷偷回退 mock
- `App.tsx` 增加全局错误提示，覆盖：
  - recent projects 加载失败
  - analyze-session 失败
  - result 加载失败
  - preview 渲染失败
  - issue status 保存失败

同时把结果页再往任务书要求推进一层：

- issue table 新增 `1:N` 列，直接显示 `branch / review / conflict`
- issue detail 新增 `1:N triage`
- issue detail 新增 `Confidence breakdown`
- issue detail 将 evidence chain 与 raw evidence 分开显示，不再只剩一坨原始 JSON

验证情况：

- `apps/desktop` 前端构建通过：`npm run build`
- Python 相关回归通过：`python -m pytest -q tests/unit/test_sidecar.py tests/unit/test_cli.py tests/unit/test_ui_app.py`
- 本机仍缺 `cargo`，因此原生 Tauri 编译暂未完成验证

## 29. 2026-07-05 桌面端 SQLite issue payload 加厚，结果页支持更细筛选与详情

在原生桥接接通后，桌面端 `load-result` 仍然只返回“轻量 issue 摘要”，这会直接限制结果页与 SQLite 的价值：

- 不能稳定显示 `summary / explanation / recommended_action`
- 不能直接展示 `evidence_refs / related_pair_ids / sheet_ids / values`
- 不能按 `issue_type` 或一对多三态做更细筛选

本轮把 `DesktopStateStore` / `desktop.sidecar` 的 issue payload 做厚：

- SQLite `issue_summaries` 新增并兼容迁移：
  - `issue_type`
  - `summary`
  - `explanation`
  - `recommended_action`
  - `sheet_id / file_id / line_group_id`
  - `primary_pair_id`
  - `one_to_many_classification`
  - `evidence_refs_json / related_pair_ids_json / sheet_ids_json / values_json`
- `load-result` 现在会把这些字段以真实对象/数组返回，而不是只剩 `evidence_json`
- 额外补了一条 migration 回归，覆盖“旧 schema 自动补列后仍能正常 round-trip”

桌面前端同步做了两类收口：

- 结果页筛选：
  - `Severity`
  - `Rule`
  - `Status`
  - `1:N`
  - 文本搜索同时覆盖 `issue_type / summary / explanation / recommended_action / related_pair_ids / sheet_ids / values`
- 结果页详情：
  - `Issue type`
  - `Summary`
  - `Explanation`
  - `Recommended action`
  - `Related pairs / Related sheets / Observed values / Primary pair`
  - `Evidence refs`

过程页也顺手补齐了一部分任务书字段：

- live issue table 新增 `File` 列
- live issue table 新增 `Type` 列
- `issue_found` 事件现在会带 `issue_type` 和 `one_to_many_classification`

验证情况：

- `python -m pytest -q tests/unit/test_state_store.py tests/unit/test_sidecar.py tests/unit/test_cli.py`
- `python -m pytest -q`
- `apps/desktop` 前端构建通过：`npm run build`

## 30. 2026-07-05 桌面端启动页补齐原生文件夹选择与拖拽导入

此前 `apps/desktop` 的启动页虽然已经有输入框和按钮，但“Native folder picker” 只是占位文案，`.dropzone` 也只有样式，没有真实原生导入能力。

本轮把启动页的高优先级原生入口补齐到了真实链路：

- 前端新增 `desktopApi.pickProjectDirectory()`，在 Tauri 环境下通过 `@tauri-apps/plugin-dialog` 打开系统目录选择器。
- Rust 侧已注册 `tauri-plugin-dialog`，并在 capability 中补 `dialog:allow-open`，不再只是 React 单边假接线。
- 启动页现在支持：
  - 原生文件夹选择
  - 窗口级拖拽导入目录
  - 拖拽悬停 / 接收状态提示
  - 基于路径形态的最小输入校验，避免把单个 `DWG / DXF / prj / xml` 文件误当项目根
- 结果页顺手补了两项交互收口：
  - 切换项目时重置旧的 issue 筛选条件，避免“项目已切换但表格空白”这类伪空状态
  - 当前选中 issue 改为跟随 `filteredIssues`，并由 effect 统一刷新预览，避免右侧详情仍操作已被筛掉的隐藏项

同步文档状态：

- [apps/desktop/README.md](/F:/workspace/XJToolkit/apps/desktop/README.md) 已去掉“native directory picker / drag-and-drop 仍是 placeholder”的旧表述
- 当前 limitations 仍明确保留：
  - 本机缺 `cargo`，因此 Tauri/Rust 端到端编译仍未验证
  - 结果页尚未完成多证据切换、多 reference 预览切换与预览重生成控制

验证情况：

- `apps/desktop` 前端构建通过：`npm run build`
- 由于当前机器仍无 Rust toolchain，`src-tauri` 侧只完成代码接入，未做原生编译验收

## 31. 2026-07-05 结果页补齐预览来源切换，开始利用 `sheet_id / evidence_refs`

在上一轮 issue payload 加厚后，桌面端虽然已经能拿到：

- `sheet_id`
- `sheet_ids`
- `evidence_refs`
- `related_pair_ids`

但结果页实际仍只会对当前 issue 渲染一张默认预览，无法显式切换到相关页或 evidence ref 对应页，这和任务书里“更完整复核”方向还差一步。

本轮先不改 Python 预览生成逻辑，而是复用 `render-preview --sheet-id` 已有能力，把前端预览切换入口接出来：

- `App.tsx` 现在会从当前 issue 的：
  - `sheet_id`
  - `evidence_refs[].sheet_id`
  - `sheet_ids[]`
  聚合出 `previewOptions`
- 结果页新增 `Preview source` 下拉选择
- 切换选项后，前端会以 `issue_id + sheet_id` 重新请求 `renderPreview`
- 当前激活的预览来源会在结果页显式展示，不再只有一张“默认图”

顺手补的两项交互修正：

- 切项目时会清空旧的 issue 筛选条件，避免新项目被旧筛选误过滤成空表
- 当前选中 issue 现在跟随 `filteredIssues` 自动收口，避免右侧详情和状态保存仍指向已隐藏 issue

直接结论：

- 桌面端结果页现在已经不再只是“有 preview 区域”，而是开始利用结构化 evidence 在多相关页之间切换复核视角。
- 这仍然不是最终形态；当前还缺：
  - evidence refs 的更友好列表化展示
  - preview 失败重试 / 重生成控制
  - 多 evidence point 的红框切换
  - Rust/Tauri 原生端到端编译验收

验证情况：

- `apps/desktop` 前端构建再次通过：`npm run build`

## 33. 2026-07-05 evidence ref 点击已能把 `line_group_id` 传到预览高亮

上一轮 `evidence_refs` 点击入口虽然已经能切到相关页，但高亮仍然沿用“当前 issue 自己的 `line_group_id / evidence`”，这意味着：

- 点击 related ref 时，往往只是切页
- 不一定会高亮到该 ref 真正关联的那条线组

本轮把这条链路往下再穿了一层：

- Python `render_project_preview()` 新增可选 `line_group_id`
- CLI `render-preview` 新增 `--line-group-id`
- Tauri Rust `desktop_render_preview` 新增透传 `line_group_id`
- 前端 `desktopApi.renderPreview()` 新增 `lineGroupId` 参数
- 结果页点击某条 `evidence ref` 时，如果该 ref 带有 `line_group_id`，前端会把：
  - `sheet_id`
  - `line_group_id`
  一起传给 `render-preview`

当前行为边界：

- 对于 evidence ref 点击：
  - 若 ref 自带 `line_group_id`，当前预览会优先高亮该线组
  - 若只是切到其他相关页但没有具体线组，则仍然只做页级切换
- 这让结果页从“只能切页”提升为“在有结构化 ref 线组信息时，也能跟着切高亮目标”

验证情况：

- `apps/desktop` 前端构建通过：`npm run build`
- Python 回归通过：`python -m pytest -q tests/unit/test_sidecar.py tests/unit/test_cli.py`

## 32. 2026-07-05 结果页补 evidence refs 点击入口与预览重生成控制

在上一轮把 `Preview source` 下拉接出来后，结果页仍然有两个明显缺口：

- `evidence_refs` 还是原始 JSON，不是人工复核友好的入口
- 即使前端重复调用 `render-preview`，浏览器也可能继续复用同一路径图片缓存，因为当前预览文件名固定为 `"{sheet_id}_{issue_id}.svg"`

本轮继续把这两点收口：

- `Evidence refs` 现在会渲染成可点击列表，而不是只显示 JSON 文本
- 每条 ref 至少会显示：
  - `sheet_no / sheet_id`
  - `filename`
  - `pair_id / line_group_id`
  - `coord`（如果 evidence ref 里存在）
- 点击某条 ref 后，会把当前结果页的 `selectedPreviewSheetId` 切到该 ref 对应页，并复用现有 `render-preview --sheet-id` 重新生成预览
- 结果页新增 `Regenerate preview` 按钮
- `desktopApi.renderPreview()` 返回的 `preview_src` 现在会自动附带 cache-bust 查询参数，避免“后端已重写 SVG，但前端仍显示旧图”的伪失败

边界说明：

- 这一轮 `evidence_ref` 的定位仍然是“切到相关页复核”，不是“精确跳到 ref 专属红框”
- 原因是当前 Python `render_project_preview()` 的高亮逻辑仍只基于当前 issue 的 `evidence / line_group_id`，还没有消费某一条 `evidence_ref` 的专属高亮数据
- 因此当前实现是保守且真实的：先把页级切换和显式重生成做稳，再考虑 ref 级高亮

验证情况：

- `apps/desktop` 前端构建再次通过：`npm run build`

## 34. 2026-07-05 Tauri 原生构建已完成真实编译与 NSIS 打包

前几轮桌面端 `M9` 的主要不确定点已经从“代码是否能原生编译”收口到“本机原生构建链是否真的打通”。本轮把这条链做了端到端实跑，结论是：

- `src-tauri` 的 Rust 工程现在可以通过真实 `cargo check`
- `tauri build` 已能完成前端打包、Rust release 编译、`dwg_audit_desktop.exe` 生成和 NSIS 安装包输出
- 之前阻塞编译的 `icon.ico` 资源问题已经消除

本轮实际发现与处理如下：

- 旧的 `apps/desktop/src-tauri/icons/icon.png` 实际仍是 `343x361`，不是正方形；由它派生出来的 `icon.ico` 也不可靠，这正是此前 `failed to parse icon ... failed to fill whole buffer` 的根因。
- 先基于 `apps/desktop/src/assets/hero.png` 生成了一个透明底 `512x512` 的 square source，再通过官方命令：
  - `npx tauri icon src-tauri/icons/icon-source-square.png --output src-tauri/icons`
  重建了 `icon.ico / icon.png / 32x32 / 64x64 / 128x128 / icns / appx / android / ios` 整套图标资源。
- 重新跑：
  - `cargo check --manifest-path src-tauri\\Cargo.toml`
  已通过。
- 第一次、第二次 `npm run tauri:build` 都没有再卡在工程代码，而是卡在 Tauri bundler 下载 NSIS 资源时的 `timeout: global`。
- 手动把 NSIS 资源预热到本机缓存后，再次 `npm run tauri:build` 已通过，并产出：
  - `apps/desktop/src-tauri/target/release/dwg_audit_desktop.exe`
  - `apps/desktop/src-tauri/target/release/bundle/nsis/DWG Audit Desktop_0.1.0_x64-setup.exe`

直接结论：

- 桌面端当前不再只是“前端能 build、Rust 代码理论可编译”，而是已经有真实的 Windows 原生可执行文件和 NSIS 安装包。
- `M9` 原生桥接这一块的风险已经从“架构/代码未闭环”下降到“首次 bundler 依赖下载可能受网络影响”。这属于环境预热问题，不再是应用代码阻塞。

当前剩余与后续意义：

- `src-tauri` 的 `Cargo.toml / capabilities / tauri.conf / Cargo.lock / gen/schemas / icons` 已形成一组可提交的原生桌面收口改动。
- 这让主线程可以把重心从“Tauri 是否能落地”转回任务书主线中的 DWG findings / audit 质量整改，而不是继续卡在桌面外壳可用性不确定上。

## 35. 2026-07-05 第二套样本已补真实基线，页型补齐后端子页进入主链但元件接线图仍为 0 pair

用户最新反馈指出第二套 `变压器测控柜(2圈变，2台测控)` 需要补完整 findings / audit 基线。主线程与子代理核实后，当前结论应更新为更准确的版本：

- 仓库里已经存在几套第二套样本的完整 `.tmp` 产物，不是完全没有深跑证据，例如：
  - [page_strategy_second/2_2](/F:/workspace/XJToolkit/.tmp/page_strategy_second/2_2)
  - [second_project_baseline/2_2](/F:/workspace/XJToolkit/.tmp/second_project_baseline/2_2)
  - [sample_run_v3_secondset/2_2](/F:/workspace/XJToolkit/.tmp/sample_run_v3_secondset/2_2)
- 这些产物都包含 `manifest + findings + audit`，且 `.prj` / `LdDzbInfo.xml` 解析状态是好的。

在此基础上，本轮又用当前代码重新实跑了第二套：

- 新实跑目录：
  - [phase6_supplemental_default_second/2_2](/F:/workspace/XJToolkit/.tmp/phase6_supplemental_default_second/2_2)
- 命令：
  - `python -m dwg_audit.cli analyze-project --input test/变压器测控柜(2圈变，2台测控) --output .tmp/phase6_supplemental_default_second`
  - `python -m dwg_audit.cli run-audit --findings .tmp/phase6_supplemental_default_second/2_2/findings`

这次实跑里，页型策略已经向前推进了一步：

- `17-18` 背板页仍保持 `secondary`，没有再误入审计主链。
- `19-20` 元件接线图现在是 `supplemental`。
- `21-24` 左/右侧端子图现在是 `supplemental`。
- 整体页型计数变为：
  - `primary=13`
  - `supplemental=6`
  - `secondary=2`
  - `skip=3`

更关键的是，页型放开后的真实效果并不均匀：

- `21-24` 端子页已经实质进入 findings 主链，并产生大量几何/配对：
  - `21 左侧端子图1.dwg`: `135 line_groups / 135 pairs / 27 issues`
  - `22 左侧端子图2.dwg`: `85 line_groups / 85 pairs / 7 issues`
  - `23 右侧端子图1.dwg`: `130 line_groups / 130 pairs / 15 issues`
  - `24 右侧端子图2.dwg`: `92 line_groups / 92 pairs / 31 issues`
- 但 `19-20` 元件接线图虽然已经被纳入 `supplemental`，当前仍然：
  - `0 line_groups / 0 pairs / 0 issues`

直接结论：

- “页型没有纳入审计”已经不再是第二套 `21-24` 端子页的主阻塞；这些页现在已经被真实处理。
- `19-20` 元件接线图依然完全没有进入 pair 结果，说明下一步真正要打的点不是单纯 `audit_role`，而是这些页的几何/文本模式尚未被当前 `line_groups + terminal_candidates` 理解。
- 第二套最适合作为后续整改验证页的优先级可以定为：
  - `08 测控1开入回路图1.dwg`
  - `12 测控2开入回路图1.dwg`
  - `21 左侧端子图1.dwg`

## 36. 2026-07-05 候选降权与 inline 数字断线重连已经在当前代码里，但效果还没有闭环

用户最新核验里把以下两件事列为“最该先补”：

- `DIM` 层单字符数字降权 / 剔除
- 在线组合并阶段跨 inline 数字断线重连

主线程复核当前代码后，结论是这两条并不是完全空白，而是已经有第一轮工程化落地：

- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 已按图层与单字符组合施加 penalty：
  - `deprioritized_layers = ["DIM", "MARK"]`
  - `single_char_penalty_layers = ["DIM", "MARK"]`
  - `single_char_penalty`
- [line_groups.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/line_groups.py) 已支持：
  - `inline_numeric_bridge_gap`
  - `inline_numeric_bridge_y_tolerance`
  - `_has_inline_numeric_bridge(...)`
- 相关单测也已存在并可通过：
  - [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py)
  - [test_line_groups.py](/F:/workspace/XJToolkit/tests/unit/test_line_groups.py)
  - 本轮回归：`python -m pytest -q tests/unit/test_terminal_candidates.py tests/unit/test_line_groups.py` -> `8 passed`

这意味着：

- 当前主线不应再把这两点描述成“完全未实现”。
- 更准确的表述应是：“第一轮降权与 bridge 逻辑已经在代码里，但从 second-set 实跑结果看，力度和页型适配还不够，尚未把 `? -> 723 / 723 -> ? / 6 -> 721` 这类模式压到可接受水平。”
- 因此下一步重点不只是“有没有这条规则”，而是：
  - 参数力度是否足够
  - 是否需要按页型进一步加强
  - 是否还存在当前 bridge 逻辑没覆盖到的几何断裂模式

## 37. 2026-07-05 主回路页单字符 `DIM/MARK` 已在 primary 页直接拒收，second-set 相关噪声从 56 对降到 0

在上一轮复核里已经确认：当前代码虽然有 `DIM/MARK` 单字符 penalty，但在 second-set 主回路页里仍然留下了大量“单字符一侧”的 selected pair。实际统计显示：

- 在 [phase6_supplemental_default_second/2_2](/F:/workspace/XJToolkit/.tmp/phase6_supplemental_default_second/2_2) 中，
  - `primary` 页带单字符一侧的 pair 共有 `56` 个
  - 其中包含典型模式：
    - `6 -> 719`
    - `4 -> 717`
    - `2 -> 715`
    - `1 -> 1`

本轮做了更明确的主链收口：

- 在 [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py) 增加：
  - `page_category_overrides["二次原理图"].text.single_char_reject_layers = ["DIM", "MARK"]`
- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 增加 `single_char_layer_filtered` 拒收路径：
  - 对 `二次原理图` 页上的单字符 `DIM/MARK` 纯数字，直接不再进入 accepted candidate
  - `屏端子图` 仍保持原有宽松策略，不会把真实单字符端子号一起误杀

回归与实跑结果：

- 单测新增并通过：
  - `primary` 页：单字符 `DIM` 候选应被 reject
  - `屏端子图`：单字符 `MARK` 候选仍可 accepted
- second-set 实跑对照目录：
  - 旧基线：[phase6_supplemental_default_second/2_2](/F:/workspace/XJToolkit/.tmp/phase6_supplemental_default_second/2_2)
  - 单字符过滤后：[phase6_primary_single_char_filter_second/2_2](/F:/workspace/XJToolkit/.tmp/phase6_primary_single_char_filter_second/2_2)
- 对照结论：
  - `primary` 页“单字符一侧 pair”从 `56` 直接降到 `0`
  - `04 / 05 / 08 / 12` 里原先那批 `6/4/2 -> 7xx` selected pair 不再出现

这条规则的定位很清楚：

- 它是“把明显不可信的单字符主回路候选从主链里剔掉”
- 不是对 `08/12` 大量互补 missing-side 的主修复手段
- 那一类热点仍然主要受 `inline numeric bridge` 覆盖范围影响

## 38. 2026-07-05 `元件接线图` 已支持受控 `INSERT` 展开，`19` 从 0 pair 提升到 39 pair，`20` 仍暴露出方向问题

子代理和主线程的结论已经一致：第二套 `19/20` 的根因不能混为一谈。

### 38.1 当前结论

- `19 元件接线图1.dwg`
  - 主因是 `INSERT` 内容此前没有被展开到 `lines/texts`
  - 修正后已经能进入主链
- `20 元件接线图2.dwg`
  - 即使展开 `INSERT`，仍然因为主体几何是竖线端子桩、候选搜索仍按 `left/right` 语义，继续停在 `0 line_groups / 0 pairs`

### 38.2 实现方式

本轮在 [cad_extract.py](/F:/workspace/XJToolkit/src/dwg_audit/extract/cad_extract.py) 做了结构化收口：

- 抽取层新增统一 `_extract_graphic_entity(...)`
- `INSERT` 现在可以通过 `virtual_entities()` 展开块内：
  - `LINE`
  - `LWPOLYLINE`
  - `POLYLINE`
  - `TEXT`
  - `MTEXT`
  - `ATTRIB / ATTDEF`
- 但这个展开不是全局开启，而是受 [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py) 中：
  - `extract.insert_virtual_entity_categories = ["元件接线图"]`
  控制

这样做的原因是：全局展开 `INSERT` 会把 `04-16` 这类主回路页的抽取量整体抬高，不利于当前稳定性；把它先收口到 `元件接线图`，既能救 `19`，又不强行改变主回路页的主链行为。

### 38.3 测试与第二套实跑证据

新增集成测试并通过：

- `元件接线图` 页面默认会从 block 虚拟实体中抽出 line_group / pair
- `二次原理图` 页面默认不会因为 block 虚拟实体而自动引入同类候选线

新的 second-set 实跑目录：

- [phase6_component_insert_gap13_second_scoped/2_2](/F:/workspace/XJToolkit/.tmp/phase6_component_insert_gap13_second_scoped/2_2)

与旧基线 [phase6_supplemental_default_second/2_2](/F:/workspace/XJToolkit/.tmp/phase6_supplemental_default_second/2_2) 对照：

- `19 元件接线图1.dwg`
  - 旧：`0 line_groups / 0 pairs / 0 issues`
  - 新：`39 line_groups / 39 pairs / 12 issues`
- `20 元件接线图2.dwg`
  - 旧：`0 / 0 / 0`
  - 新：仍是 `0 / 0 / 0`
- `04-16` 主回路页的 line_group 数量回到了原来量级，没有保留“全局 block 展开”那种整体暴涨副作用

### 38.4 还没解决的下一步

`20` 现在留下来的问题已经更明确了，不再是“抽不到块内实体”，而是：

- 现有 [line_groups.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/line_groups.py) 只认水平线
- 现有 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 只认 `left/right` 端点

也就是说，下一步若要继续推进 `20`，应该新增 `元件接线图` 的方向感知 grouping / `top-bottom` 候选搜索，而不是继续在 `extract` 层兜圈子。

## 39. 2026-07-05 `inline_numeric_bridge_gap` 已从 12.0 提到 13.0，但 second-set `08/12` 大盘改善仍有限

子代理对 `08 / 12 / 21` 的只读分析给出一个很具体的判断：

- `08 / 12` 的主噪声大量来自“同一根线被 inline 数字切成两段”
- 一批典型 gap 落在 `12.5 ~ 12.75`
- 当前 `12.0` 会刚好漏掉它们

基于这个证据，本轮把 [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py) 中：

- `geometry.inline_numeric_bridge_gap`
  - `12.0 -> 13.0`

并补了单测，覆盖“略高于旧阈值的 gap 现在可以桥接”。

不过 second-set scoped 实跑结果说明，这条参数调优虽然方向正确，但还不是决定性收口：

- `08 测控1开入回路图1.dwg`
  - 旧：`95 issues`
  - 新：`96 issues`
- `12 测控2开入回路图1.dwg`
  - 旧：`89 issues`
  - 新：`89 issues`

这说明：

- `13.0` 这一步没有造成回退性爆炸，属于可接受的小调
- 但 `08/12` 的 missing-side 主问题并没有被这一个参数单独解决
- 后续更可能还需要：
  - 更精细的 bridge 触发条件
  - 或者把“同值互补链 `?->X / X->?`”作为 line-group / pair 后处理收口逻辑单独处理

## 40. 2026-07-05 `元件接线图2` 已进入纵向主链，second-set `20` 从 `0 pair` 提升到 `55 pair`

这一轮把 `元件接线图` 的方向问题真正落到了代码里，而不是停留在只读判断。

### 40.1 实现范围

本轮修改集中在三层：

- [line_groups.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/line_groups.py)
  - 新增 `horizontal / vertical / auto` 的 line-group orientation 选择
  - `元件接线图` 通过 [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py) 中：
    - `page_category_overrides["元件接线图"].geometry.line_group_orientation = "auto"`
    自动根据页内有效线段数量选择主方向
  - vertical 线组输出为：
    - `start = top`
    - `end = bottom`
    - `orientation = "vertical"`
- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
  - vertical 线组的候选 side 改为 `top / bottom`
  - 评分从横向 `dx` 语义切换为纵向 `dy` 语义
- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - 继续保留 `left_value / right_value` 字段兼容下游
  - 但在 evidence 中补充：
    - `line_orientation`
    - `left_side_label`
    - `right_side_label`

### 40.2 测试与真实样本结果

新增并通过：

- vertical line-group 单测
- vertical `top/bottom` candidate 单测
- vertical pair/evidence 单测
- `20 元件接线图2.dwg` 风格集成测试

全量回归：

- `python -m pytest -q`
  - `97 passed`

second-set 新实跑目录：

- [phase7_vertical_component_second/2_2](/F:/workspace/XJToolkit/.tmp/phase7_vertical_component_second/2_2)

关键结果：

- `19 元件接线图1.dwg`
  - 保持 `39 line_groups / 39 pairs / 12 issues`
  - orientation 仍为 `horizontal`
- `20 元件接线图2.dwg`
  - 旧：`0 line_groups / 0 pairs / 0 issues`
  - 新：`55 line_groups / 55 pairs / 55 issues`
  - `line_groups.orientation` 全为 `vertical`
- `primary` 页单字符一侧 pair
  - 继续保持 `0`

### 40.3 新暴露出的下一层问题

`20` 现在已经不再是“没进主链”，而是“进来了但候选质量还偏粗”。

我在新产物里看到的前几条 pair 典型是：

- `1 -> 1`
- `1 -> 2`

而且大多停在 `review / low-confidence`，说明下一步重点应该转成：

- vertical 页的候选过滤
- `DIM / MARK` 单字符在 `元件接线图` 上是否也需要更细的降权
- 或者 vertical 页专用的搜索窗口 / 评分策略

也就是说，`20` 的阻塞已经从“没有 pair”推进成“pair 太粗”，这是实质性前进。

## 41. 2026-07-05 `08/12` 的互补 missing-side 已做成 issue 聚合，issue 总量明显下降

前一轮只读判断认为，`08/12` 更适合做“issue 聚合”，而不是直接补写 pair。本轮已经按这个思路实现了一版保守收口。

### 41.1 实现方式

本轮在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 的 `R-PAIR-MISSING-SIDE` 里新增了互补半链聚合：

- 只处理 `status != discard` 的 missing-side pair
- 匹配模式为同页：
  - `? -> X`
  - `X -> ?`
- 核心锚点条件：
  - `right_text_id == left_text_id`
- 额外几何护栏：
  - 两段线都必须是 `horizontal`
  - `bridge_gap <= inline_numeric_bridge_gap`
  - `Y` 偏差 `<= inline_numeric_bridge_y_tolerance`

命中后：

- 不改写 pair 本体
- 不伪造新的 `X -> X`
- 只把两条单侧 issue 聚成一条：
  - title: `互补半链待复核`
  - evidence:
    - `chain_kind = complementary_half_pair`
    - `shared_text_id`
    - `shared_value`
    - `bridge_gap`
    - `bridge_y_delta`

### 41.2 回归与真实收益

新增单测覆盖：

- 两条互补 missing-side pair 应聚成 1 条 issue
- `primary_pair_id / related_pair_ids / evidence` 应保留两条原始 pair 的追踪关系

second-set 新 audit 结果：

- [phase7_vertical_component_second/2_2/audit](/F:/workspace/XJToolkit/.tmp/phase7_vertical_component_second/2_2/audit)

关键变化：

- `08 测控1开入回路图1.dwg`
  - 旧：`96 issues`
  - 新：`49 issues`
  - 其中：
    - `47` 条为聚合后的 `互补半链待复核`
    - `1` 条保留为尾项 missing-side
    - `1` 条低置信 pair
- `12 测控2开入回路图1.dwg`
  - 旧：`89 issues`
  - 新：`48 issues`
  - 其中：
    - `41` 条为聚合后的 `互补半链待复核`
    - `7` 条保留为尾项 missing-side

### 41.3 这个实现的边界

这版聚合是保守的：

- 它改善了 review 噪声密度
- 但没有改变 pair 数量，也没有假装问题已经自动修复

因此它适合作为当前阶段的“报告层收口”，但不等于几何层已经彻底理解了这些页。若后续继续推进，仍然值得考虑：

- 更精细的 inline bridge 触发条件
- 是否把类似聚合扩展到 vertical 页型
- 是否在 UI / report 上为“互补半链”提供更显式的展示语义

## 42. 2026-07-05 `元件接线图2` 的 vertical 噪声已先做“共享锚点去重 + 超长线过滤”，issue 从 55 降到 27

上一轮把 `20 元件接线图2.dwg` 拉进了主链，但主结果仍然是：

- `55 line_groups / 55 pairs / 55 issues`
- 其中几乎清一色是 `1 -> 2`

这一轮继续只看真实产物，主线程与两个只读子代理都得出了同一结论：这页的首要问题不是“候选分数略低”，而是**同一文本锚点被两根相邻竖线同时复用**。

### 42.1 噪声结构已经很清楚

以 [phase7_vertical_component_second/2_2](/F:/workspace/XJToolkit/.tmp/phase7_vertical_component_second/2_2) 的 findings 为证：

- `20` 的 accepted candidate 一共有 `110` 个：
  - `top = 55`
  - `bottom = 55`
- `110/110` 全都来自：
  - `layer = 0`
  - `text_len = 1`
  - value 只有：
    - `1`
    - `2`
- 其中 `54` 根短竖线并不是独立单元，而是 `27` 组相邻双线：
  - `x` 间距稳定约 `5`
  - `length` 基本都是 `15`
  - 每组双线复用同一对 `top/bottom text_id`

主线程实查到的典型复用模式：

- `T2512 / T2511` 同时被 `G0707` 和 `G0710` 命中
- `T2467 / T2466` 同时被 `G0708` 和 `G0711` 命中

这就解释了为什么上一轮会稳定产生：

- `54` 条 `1 -> 2`
- `1` 条 `1 -> 1`

而且都不是“多候选竞争选错”，而是每个 group-side 本来就只剩 1 个 accepted。

### 42.2 本轮实现：先去重共享锚点，再摘掉长线离群点

本轮在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 增加了 vertical component 页专用后处理：

- 只对：
  - `sheet_category == 元件接线图`
  - `group.orientation == vertical`
  生效
- 同一：
  - `sheet_id`
  - `side`
  - `text_id`
  若被多个 line_group 同时 accepted：
  - 只保留距离端点最近的一条
  - 其余改为：
    - `status = rejected`
    - `rejection_reason = shared_text_anchor_reused`

同时在 [line_groups.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/line_groups.py) 增加了一个很窄的 vertical outlier 过滤：

- 只对 `元件接线图 + vertical` 生效
- 用该页 vertical candidate 的长度中位数做基准
- 过滤 `> 3x median` 的极端长线

这样做的目标不是“彻底理解页语义”，而是先把这页最确定的两类噪声打掉：

- 一类是共享文本锚点的成对重复
- 一类是 `G0706` 这种明显不像真实端子线的超长边框线

### 42.3 测试与真实收益

新增并通过：

- 共享 `text_id` 的 vertical component candidate 去重单测
- vertical component 长线离群过滤单测

全量回归：

- `python -m pytest -q`
  - `99 passed`

新的 second-set 实跑目录：

- [phase8_vertical_dedupe_longline_second/2_2](/F:/workspace/XJToolkit/.tmp/phase8_vertical_dedupe_longline_second/2_2)

与上一轮 [phase7_vertical_component_second/2_2](/F:/workspace/XJToolkit/.tmp/phase7_vertical_component_second/2_2) 对照：

- `19 元件接线图1.dwg`
  - 保持 `39 line_groups / 39 pairs / 12 issues`
- `20 元件接线图2.dwg`
  - 旧：`55 line_groups / 55 pairs / 55 issues`
  - 新：`54 line_groups / 54 pairs / 27 issues`
  - 其中：
    - `shared_text_anchor_reused` 拒收了 `54` 个复用候选
    - `1 -> 1` 长线离群 pair 已消失
    - 剩余 `27` 条 issue 全是 `1 -> 2` 的 `R-PAIR-LOW-CONFIDENCE`
- `08 / 12`
  - 仍保持：
    - `49`
    - `48`
    条 issue，没有回退

### 42.4 还剩下的真正下一步

`20` 现在已经从“重复扩散 + 离群线混入”推进到了更纯粹的一层：

- 剩余的 `27` 条 `1 -> 2`，本质上是每组竖线模板里，局部 pin 号仍然压过了更长的上下文标签

主线程这轮实查到的另一条重要事实是：在很多端点窗口里，`1/2` 旁边其实同时存在更长的 `TEXT` 标签，例如：

- `3-21CD43`
- `3-21n419`
- `1-21CD53`
- `1-21n427`

但它们当前都因为“不被数值化”而落到 `not_numeric`。这说明下一步最值得继续推进的是：

- `元件接线图` 页专用的 suffix/value 派生规则
- 或者“单字符 pin 号遇到更长 TEXT 标签时”的上下文降权 / 拒收

也就是说，`20` 的问题已经从“重复复用导致虚胖”推进成了“真实标签理解还不够深”，这比上一轮更接近可用状态。

## 43. 2026-07-05 `元件接线图2` 的 suffix 派生已收口到 vertical 专用，`27` 条 review 中有 `24` 条变成具体语义值

上一轮结论已经说明：`20 元件接线图2.dwg` 剩余的 `27` 条低置信 pair，并不都是“没有长文本可用”，而是很多端点窗口里虽然同时存在更长的 `TEXT`，但当前没有被数值化。

这轮实现没有走“全局放宽 suffix 规则”的路线，而是做了两个更窄的收口：

- 在 [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py) 给 `元件接线图` 增加受控 `numeric_suffix_patterns`：
  - `n(?P<value>\d{3,})$`
  - `(?:CD|GD|ZK-?)(?P<value>\d{1,3})$`
- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 做两层额外护栏：
  - 只有 `group.orientation == vertical` 的 `元件接线图` 才启用这些 suffix 派生
  - 若同一端点已经命中派生数值，则同侧原始单字符数值会被改成 `superseded_by_derived_numeric`

这样做的原因很明确：

- 更早的宽放版本会让 `19 元件接线图1.dwg` 出现回退风险。
- 当前真正需要这类派生的是 `20` 的 vertical 模板页，而不是整个 `元件接线图` 类别。

### 43.1 测试与实跑证据

新增并通过：

- vertical component suffix 提取单测
- 派生值压过单字符 pin 号单测
- horizontal component 页禁用 suffix 派生单测
- 集成测试：`20 元件接线图2.dwg` 风格页面应产出 `43 -> 419`

当前全量回归：

- `python -m pytest -q`
  - `103 passed`

当前 second-set 新实跑目录：

- [phase8_component_suffix_scoped_second_rerun/2_2](/F:/workspace/XJToolkit/.tmp/phase8_component_suffix_scoped_second_rerun/2_2)

与上一轮 [phase8_vertical_dedupe_longline_second/2_2](/F:/workspace/XJToolkit/.tmp/phase8_vertical_dedupe_longline_second/2_2) 对照：

- `19 元件接线图1.dwg`
  - `39 pairs / 12 non-discard / 12 issues`
  - `12` 条非 discard pair 完全不变
- `20 元件接线图2.dwg`
  - 保持 `54 pairs / 27 non-discard / 27 issues`
  - 其中 `24/27` 条从泛化 `1 -> 2` 变成了更具体的值，例如：
    - `43 -> 419`
    - `53 -> 427`
    - `38 -> 416`
    - `3 -> 113`
    - `2 -> 112`
  - 仍剩 `3` 条 `1 -> 2`，对应线组：
    - `G0706`
    - `G0712`
    - `G0718`
- `08 / 12`
  - 仍保持：
    - `49`
    - `48`
    条 issue，没有回退

### 43.2 当前最重要的工程结论

- suffix 派生本身是有效的，但必须保持“`元件接线图 + vertical` 专用”这个收口。
- 这一轮已经证明，继续扩大规则作用域并不是当前最优先路径；更好的方向是只盯剩余 `3` 条 `1 -> 2` 的具体上下文。
- 从收益上看，这轮已经把 `20` 从“27 条同质化噪声”推进成了“只剩 3 条待专项解释的 residual pattern”，这是明显更接近可复核状态的真实进展。

## 44. 2026-07-05 `FJL` 虚拟块内部引脚号已被剔除，`20` 从 `27` 条 residual review 收敛到 `24`

子代理和主线程这轮把剩余 `3` 条泛化 `1 -> 2` 追到了更具体的根因：它们不是还缺一个 suffix regex，而是 `FJL-25-2A_Mirror` 的 `INSERT` 展开后，块内部固定引脚号 `1/2` 被直接当成 terminal candidate。

这 3 条残余 pair 分别是：

- `G0706`
- `G0712`
- `G0718`

共同特征：

- `text.handle` 都是 `:VIRTUAL:` 形式
- `source_block_name = FJL-25-2A_Mirror`
- 候选文本就是单字符 `1 / 2`
- 附近长文本更像器件位号 / 型号，例如：
  - `LP1 / LP2 / LP3`
  - `FJL1-2.5/2A`

因此本轮做的不是继续扩 suffix，而是补一条更窄的候选过滤：

- 在 [cad_extract.py](/F:/workspace/XJToolkit/src/dwg_audit/extract/cad_extract.py) 把 `source_block_name` 透传到 [TextItem](/F:/workspace/XJToolkit/src/dwg_audit/domain/models.py)
- 在 [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py) 为 `元件接线图` 增加：
  - `virtual_single_char_reject_blocks = ["FJL-25-2A_Mirror"]`
- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 增加 `block_internal_pin_number` 拒收路径：
  - 只对 `元件接线图 + vertical`
  - 只对 `:VIRTUAL:` 文本
  - 只对单字符数值
  - 只对命中白名单块名的情况

### 44.1 顺手补的 `HD#` 窄派生

子代理还发现另一类不同问题：

- `G0736` 顶部有 `HD6`
- `G0742` 顶部有 `HD5`

它们不是块内伪引脚号，而是当前还没数值化的短标签。所以本轮把：

- `HD(?P<value>\d{1,3})$`

也加入了同一条 `vertical-only` suffix 派生链，但保持和 `FJL` 内部引脚过滤分离，不混成一条模糊规则。

### 44.2 测试与 second-set 实跑结果

新增并通过：

- `FJL` 虚拟块内部 `1/2` 拒收单测
- `HD#` vertical suffix 提取单测
- `FJL-25-2A_Mirror` 风格集成测试

当前全量回归：

- `python -m pytest -q`
  - `106 passed`

当前 second-set 新实跑目录：

- [phase9_virtual_pin_filter_hd_second/2_2](/F:/workspace/XJToolkit/.tmp/phase9_virtual_pin_filter_hd_second/2_2)

关键结果：

- `19 元件接线图1.dwg`
  - 继续保持 `12` 条非 discard pair，不回退
- `20 元件接线图2.dwg`
  - `54 pairs / 24 non-discard / 24 issues`
  - 旧的 `3` 条 `FJL` 伪 `1 -> 2` 已完全消失
  - `HD6 -> 504` 与 `HD5 -> 502` 现在分别语义化为：
    - `6 -> 504`
    - `5 -> 502`
- `08 / 12`
  - 继续保持：
    - `49`
    - `48`
    条 issue，没有回退

### 44.3 当前结论

- 这轮证明，剩余 `3` 条并不是“再补一个 suffix 就能解决”的普通标签理解问题，而是 block virtual expansion 带来的局部伪候选。
- 对这类问题，最安全的修法是“白名单块名 + virtual 单字符过滤”，而不是全局压制所有单字符 `0` 层文本。
- `20` 现在已经从“残留 `1 -> 2` 噪声”推进到“24 条都带具体语义值的 residual review”，可解释性比上一轮明显更高。

## 45. 2026-07-05 vertical 语义已显式透传到 report / Streamlit / desktop 展示层

除了继续压降噪声，本轮还把已有 pair evidence 里的 vertical 语义尽量显式带到了展示层，避免人工复核时只能从 `left_value/right_value` 反推端点含义。

当前补丁覆盖：

- [report/artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
  - findings / audit markdown 现在会展示：
    - `line_orientation`
    - `left_side_label`
    - `right_side_label`
- [ui/app.py](/F:/workspace/XJToolkit/src/dwg_audit/ui/app.py)
  - Streamlit 的 issue / pair 详情与列表增加了 `line_orientation` 等字段
- [desktop/preview.py](/F:/workspace/XJToolkit/src/dwg_audit/desktop/preview.py)
  - 预览标题栏会优先显示 evidence 里的 orientation / side labels
  - 若 evidence 缺失，则回退读取 `line_groups.orientation`
- [apps/desktop/src/App.tsx](/F:/workspace/XJToolkit/apps/desktop/src/App.tsx)
  - desktop 结果页新增 orientation 列与 line semantics 详情

验证结果：

- `python -m compileall src/dwg_audit/report/artifacts.py src/dwg_audit/ui/app.py src/dwg_audit/desktop/preview.py`
  - 通过
- `npm run build`
  - 在 `apps/desktop` 下通过

这部分补丁不改变 pair / issue 生成逻辑，但显著提升了“当前 vertical 证据到底是什么意思”的可读性，为后续人工复核和桌面端交付都补上了可解释性。 

## 46. 2026-07-05 `page_findings/` 已落地为正式产物，second-set 24 页全部可输出页级文档

这一轮没有继续去改候选/配对逻辑，而是先补了任务书中一个非常明确但此前一直缺失的正式交付物：

- `findings/page_findings/<sheet_id>.json`
- `findings/page_findings/<sheet_id>.md`

对应实现已进入 [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)，并补了：

- 每页 `page_type`
- `page_type_confidence`
- `layout_summary`
- `structure_summary`
- `recognition_strategy`
- `number_matching_strategy`
- `high_confidence_signals`
- `open_questions`

同时项目级 [findings.json](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py) 现在也会显式带出：

- `page_findings_count`
- `page_findings`

### 46.1 回归与真实样本验证

这一批不是只停在代码层，而是已经补了测试和真实样本实跑：

- 单元 / 集成回归：
  - `python -m pytest -q tests/unit/test_report_artifacts.py tests/integration/test_analyze_project.py`
  - `16 passed`
- 全量回归：
  - `python -m pytest -q`
  - `106 passed`
- second-set 真实 `analyze-project`：
  - 产物目录：[phase10_page_findings_second/2_2](/F:/workspace/XJToolkit/.tmp/phase10_page_findings_second/2_2)

实跑结果已确认：

- 第二套样本 `24` 页全部生成了页级 findings。
- `findings/page_findings/` 下共有：
  - `24` 个 `.json`
  - `24` 个 `.md`
- 页级文档已能写清：
  - 当前页型
  - 当前 route target
  - 当前识别策略
  - 当前数字匹配策略
  - 当前高置信信号
  - 当前未理解区域 / open questions

例如 [S0004.md](/F:/workspace/XJToolkit/.tmp/phase10_page_findings_second/2_2/findings/page_findings/S0004.md) 已能明确写出：

- `PageType = 二次原理图`
- `RouteTarget = WireDiagramExtractor`
- `Layout Summary`
- `Structure Summary`
- `Recognition Strategy`
- `Number Matching Strategy`

### 46.2 这轮补齐了什么，没补齐什么

这轮真正补齐的是“页级证据产物”，不是“真正的页级分类器 / 路由器主链”。

也就是说，当前仓库现在已经不再只有项目级 `findings.md/json`，而是会为每页沉淀一份独立理解文档；这对人工复核、并行审图和后续多 Agent 分工都更贴近任务书。

但更深一层的结构性缺口仍然存在：

- 当前 `page_type`、`page_type_confidence` 与 `route_target` 仍主要来自现有 `sheet_category / audit_role` 和几何启发式总结，不是真正独立的 Page Classification Layer。
- 当前主流水线仍然是统一的：
  - `line_groups -> terminal_candidates -> pairs`
- 仓库里依然没有真正的：
  - `PageRouter`
  - `TableExtractor`
  - 三列表格高置信映射入规则引擎

所以这一轮的工程意义更准确地说是：

- 先把任务书要求的页级交付物补成正式产物；
- 再用这些页级产物把“当前是怎么理解每一页的、还没理解什么”显式暴露出来；
- 为下一轮真正推进 `Page Classification / Router / TableExtractor` 留出更清晰的证据基础。

## 47. 2026-07-06 任务书已改为“内部 findings 运行态”，`page_findings` 默认不再落盘

用户随后又明确修正了任务书语义，这一点必须覆盖掉上一轮“默认页级落盘”的假设：

- `5.1` 阶段 A 的输出，不再把 `findings/` 目录视为默认交付物
- `5.1.1` 页级并行审图要求，补了“内部运行态、可清理、不长期保留”
- `6` Findings 数据规范，明确它是内部 SSoT，而不是最终交付物
- `page_findings` 从“默认页级文件”改成“内存 / SQLite / 按需落盘记录”

这意味着：

- `findings` 仍然是系统内部最重要的结构化状态；
- 但正式产品默认不应该把它当作用户长期持有的输出目录；
- 尤其 `page_findings/<sheet_id>.md|json` 不应再默认每次都落盘，而应按调试 / 回归 / 研发分析需要显式开启。

## 48. 2026-07-06 `page_findings` 运行态已开始接到 SQLite / sidecar，而不是继续强化默认落盘

为对齐这条新语义，当前代码已经先做了两步收口：

- 默认仍会生成项目级 `findings.md/json` 与 parquet 调试材料，保持现有 CLI / regression 工作流可用；
- `page_findings/` 目录不再默认写出；
- 只有显式开启：
  - `runtime.persist_page_findings_files = true`
  才会把每页 `md/json` 真正落盘出来；
- 同时桌面端运行态已经开始把 `page_findings` 接到 SQLite / sidecar，而不是只依赖文件目录：
  - [state_store.py](/F:/workspace/XJToolkit/src/dwg_audit/desktop/state_store.py) 新增 `page_findings` 表
  - [sidecar.py](/F:/workspace/XJToolkit/src/dwg_audit/desktop/sidecar.py) 在 `analyze-session` 后把 `findings.json.page_findings` 载入 SQLite
  - [types.ts](/F:/workspace/XJToolkit/apps/desktop/src/types.ts) / [desktopApi.ts](/F:/workspace/XJToolkit/apps/desktop/src/lib/desktopApi.ts) / [mockData.ts](/F:/workspace/XJToolkit/apps/desktop/src/lib/mockData.ts) 已把 `ProjectResult.page_findings` 视为正式运行态字段

当前验证状态：

- `python -m pytest -q tests/unit/test_report_artifacts.py tests/unit/test_project_scanner.py tests/integration/test_analyze_project.py`
  - `25 passed`
- `python -m pytest -q`
  - `107 passed`
- `apps/desktop`
  - `npm run build` 通过

直接结论：

- 当前实现已经开始向“内部运行态 + 按需持久化”收口；
- 后续更值得继续推进的不是“再落更多默认页级文件”，而是把桌面端 / sidecar / SQLite 的内部状态承载彻底打通。

## 49. 2026-07-06 Batch 1 页级并行审图已补齐 `S0008`：4 张强网格化开入页都不该切到 `TableExtractor`

按照用户指定的页级并行工作流，本轮第一批 `Sheet Analyst` 已经补齐 4 张强网格化页面：

- [S0008.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0008.md)
- [S0009.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0009.md)
- [S0012.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0012.md)
- [S0013.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0013.md)

当前最重要的结论已经非常稳定：

- 这 4 张页都不是 `TableExtractor` 的目标页。
- 它们本质上仍是：
  - 三列重复
  - 横向导线主证据
  - `BINARY INPUT 1/2` 模板化很强的二次原理图
- `S0008/S0012` 只是首页变体，多了一段 `GD/DC/KLP` 顶部引导带，并没有改变主识别器。

### 49.1 这批页的问题分层

按 Findings Integrator 的角度，当前可以先收口成 4 类：

- 分类问题：
  - 当前不是主要矛盾。
  - 这 4 页都继续支持 `WireDiagramExtractor`，不该被推进 `TableExtractor`。
- 抽取 / 线组问题：
  - 主问题是同一物理行被小符号块切成左右两个半段。
  - 需要做 `row-band clustering`、`split-row merge`、`cross-symbol-block merge`。
- 配对问题：
  - 当前大量 `missing left/right candidate` 其实是镜像半配对，不是真正缺字。
  - 需要做 `duplicate-half-pair collapse` 与同 y / 同数字 / 短块分隔的合并去重。
- 专用脚本库问题：
  - 这批页值得进入“页型专用脚本库”，但脚本名不应叫 `TableExtractor`，而应是：
    - `binary_input_grid`
    - 或 `wire_grid_binary_input`

### 49.2 已稳定出现的共性规则

这 4 页共同暴露出的结构事实已经很一致：

- 主体审计区都是三列稳定列带。
- 主要回路行都按 y 方向近似等间距重复。
- 主证据数字都来自导线端点附近的自由文本数字，而不是块内文本。
- `BI xx`、`QDxx`、`GDxx` 更像语义标签 / 行标签，不应直接作为端子号。
- 首页常见顶部引导带 / 公共线 / 电源头，尾页常见尾线 / 告警说明行，都应从普通 pair 主链分流。

因此更正确的脚本方向应是：

1. 先按 `BINARY INPUT` 页型识别出三列 + 行带骨架。
2. 在每个 row band 里合并被符号块切开的水平段。
3. 只把稳定列锚点附近的纯数字当 numeric candidate 主源。
4. 把 `BI / QD / GD` 之类文本单独记为行语义，不参与端子数字竞争。
5. 对顶部 / 底部非标准带单独分流，不进入普通 pair 主链。

### 49.3 当前最值得进入开发 backlog 的事项

基于这 4 页，当前 backlog 可以先明确收敛为：

- `P0`：为 `BINARY INPUT 1/2` 页面新增 `row-band clustering`
- `P0`：新增 `cross-symbol-block merge`，把同一物理行的左右半段并回一个逻辑回路
- `P0`：新增 `duplicate-half-pair collapse`，收口镜像 `missing-left/right`
- `P1`：把 `BI xx / QDxx / GDxx` 从 numeric candidate 主链剥离，改为语义标签通道
- `P1`：对 `S0008/S0012` 这类首页顶部引导带、以及尾页尾线 / 告警说明行加页型特定抑制 / 分流
- `P2`：在页级 findings / SQLite 里补更直接的页型子标签，例如 `binary_input_first_page` / `binary_input_middle_page`

### 49.4 当前暂不该做的事

这 4 页也反过来说明，以下方向当前不该优先：

- 不应把这批页误判成表格页后直接推进 `TableExtractor`
- 不应继续扩大块内文本权重去抢数字主源
- 不应只拧全局 `gap` 常数来试图解决这类模板页

换句话说，这一批并发页审已经把方向从“是不是表格页”收口成了更具体的一句：

- 这是一类 `WireDiagramExtractor` 仍然正确、但必须加页型子策略的“重复行带开入回路页”。

## 49. 2026-07-06 PageClassifier + Router 真正执行路由 + grid-aware 子模式 + TableExtractor 雏形 + R-SHEET-PAGE-MISMATCH

本轮按任务书第 4-5 层和第 9 章要求，把当前最大的结构性缺口做了实质性落地。

### 49.1 新增 PageClassifier 模块（任务书第 4 层）

此前页型判定只靠文件名/sidecar 关键词，没有独立几何分类器。本轮新增 `src/dwg_audit/page_classifier.py`，基于 extract 后的真实几何特征判定页型：

- 特征计算：`horizontal_line_ratio`、`vertical_line_ratio`、`grid_band_count`（按 y 聚类水平线带）、`polyline_density`、`block_density`
- 分类规则（优先级从高到低）：
  1. `skip` 页 → `SkipExtractor`
  2. `table_like`（多 polyline + 水平线占优但不 grid_heavy）→ `TableExtractor`
  3. `元件接线图 + vertical_ratio >= 0.55` → `vertical_component`（优先于 grid_heavy，因为元件接线图的 grid 特征来自端子桩而非导线）
  4. `grid_heavy`（grid_band_count >= 8 且 horizontal_ratio >= 0.7）→ `grid_heavy_wire_diagram`
  5. 其余沿用 `sheet_category`

第二套样本 24 页实跑确认：
- S0008/S0009/S0012/S0013 全部正确判为 `grid_heavy_wire_diagram`（bands=20, h_ratio>0.93）
- S0021-S0024 端子图正确判为 `TerminalDiagramExtractor`
- S0017/S0018 背板图正确判为 `LayoutOnlyExtractor`

### 49.2 Page Router 真正参与执行路由（任务书第 5 层）

此前 `page_router.py` 的 `enrich_pages_with_routing` / `route_supports_pairing` 从未被调用，`pipeline.py` 无差别让所有审计页走同一条 PairBuilder。本轮：

- `pipeline.py` 在 extract 之后调用 `classify_pages` + `enrich_pages_from_classifications`
- 按 `route_target` 分流：
  - `TableExtractor` 页走 `extract_table_pairs`
  - 其余纳入审计的页（primary + supplemental）走 `build_line_groups → build_terminal_candidates → build_pairs`
- `page_router.py` 去掉 `"TableExtractor (planned)"` 占位，改为真实 `"TableExtractor"`

### 49.3 grid-aware 行带子模式（救 S0009 类页面）

按 S0009 analyst 建议，在 `line_groups.py` 新增 `orientation = "grid"` 支持：

- `_resolve_orientation` 在 `classification.grid_heavy == True` 时返回 `"grid"`
- 新增 `_build_grid_row_bands`：按 y 容差聚类水平线成行带，再在行带内做共线合并
- grid 行带的端点仍用 left/right 语义（行带是水平的），候选搜索和配对逻辑复用 horizontal 链
- 对 grid 页启用块内数字降权（`block_internal_numeric_penalty`，对应 analyst 建议④）
- evidence 里补 `row_band_id`

第二套样本实跑确认：
- line_groups orientation 从 `horizontal: 1147` 变成 `grid: 658, horizontal: 499`
- 658 个线组走了 grid 行带聚类
- R-PAIR-LOW-CONFIDENCE 从 37 降到 27（-10）
- 总 issue 从 406 降到 400（-6）

### 49.4 TableExtractor 雏形（任务书第 4 章 113-121 行）

新增 `src/dwg_audit/audit/table_extractor.py`，实现三列表格最小骨架：

- 表格骨架识别：从长水平/竖直线推断网格线
- 行列识别：按 y 聚类水平网格线 → 行；按 x 聚类竖直网格线 → 列
- 三列模式检测：单元格列数 == 3 时生成高置信映射
- 列间映射：中列 → 右列（或中列 → 左列）作为高置信 Pair
- 输出 Pair `confidence = 0.95, status = pass, evidence.source = table_mapping`

规则引擎已支持 table_mapping Pair 作为高置信信源参与跨页校验（`_high_confidence_pairs` 接受 `evidence.source == "table_mapping"`）。

当前两套样本没有真正的表格页，但路径已通，单元测试覆盖三列映射。

### 49.5 R-SHEET-PAGE-MISMATCH 规则（任务书第 9 章）

新增 `R-SHEET-PAGE-MISMATCH` 规则：
- 触发条件：文件名页码与标题栏页码不一致
- 输出：major，evidence 含 `filename_page_no`、`title_block_page_no`
- 已注册到 `_RULES` 和 `DEFAULT_CONFIG["rules"]["enable"]`

当前两套样本页码一致，未触发该规则，但单元测试覆盖了触发场景。

### 49.6 配置与文档对齐

- `DEFAULT_CONFIG` 新增：`grid_band_y_tolerance`、`grid_min_band_count`、`block_internal_numeric_penalty`
- `configs/default.yml` 同步成 `DEFAULT_CONFIG` 的完整 dump（修复了此前严重过时问题）
- `report/artifacts.py` 的 `page_findings` 现在消费 `PageClassification`，输出 `page_subtype`、`grid_heavy`、`classification_features`
- findings.json 新增 `table_extraction_summary`

### 49.7 测试覆盖

新增 15 个测试，全量 122 passed：
- `test_page_classifier.py`：grid_heavy 判定、table_like 判定、vertical_component 优先级
- `test_table_extractor.py`：三列映射、非三列跳过、line_group_id 为 None
- `test_line_groups.py`：grid orientation 行带聚类、inline 数字桥接
- `test_pairs_and_rules.py`：R-SHEET-PAGE-MISMATCH 触发/不触发、table_mapping 跨页冲突

### 49.8 当前边界与下一步

本轮没做的（明确边界）：
- 没改置信度公式（6 项加权）——这是下一轮
- 没实现任意列数 TableExtractor——只做三列
- 没碰桌面端/Tauri——本轮纯 Python 主链

下一步优先级：
1. 置信度公式校准（任务书第 8 章 6 项加权）
2. grid-aware 子模式的列锚点统计（analyst 建议③）
3. sidecar/desktop 的 `run_failed`、`purge-session` 暴露
4. TableExtractor 任意列数支持

## 50. 2026-07-06 Batch 2 `S0019` 证明：`元件接线图1` 不是普通导线页，而是 `horizontal_component_block_pin`

Batch 2 第一张已完成页审的元件页是：

- [S0019.md](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0019.md)
- [S0019.json](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0019.json)

这页给出的关键信号和 `S0020` 非常不同：

- 当前 `39` 个 `line_group` 全为 horizontal；
- 当前 `92` 个 accepted terminal candidates 几乎全部来自 `KK1P / KK2P / KK3P / CD-WSK-H-J-G` 的 `INSERT` 虚拟文本；
- 当前 non-discard pair 主体是：
  - `2 -> 4`
  - `1 -> 3`
  - `1 -> 5`
  - `2 -> 2`
  - `1 -> 1`

这说明：

- 这页不是“自由文本主导”的普通导线页；
- 也不是 `S0020` 那种 `vertical_component` 页；
- 它更像一类：
  - `horizontal_component_block_pin`

### 50.1 真正的主问题

主问题不是“系统看不到数字”，而是“系统只看到了块内引脚号，还没把块外语义接上去”。

换句话说：

- 导线逻辑本身仍然有价值：
  - 短水平 stub 确实能定位到 pin / block
- 但数字匹配主源应该换成：
  - `block pin evidence`
  - 而不是普通端点自由文本

当前 failure mode 已很明确：

- 把 block internal pin pairing 当成 external wiring pairing
- 同一虚拟 text 双端复用，产生：
  - `1 -> 1`
  - `2 -> 2`
- 顶部附件块被误读成低价值的内部脚位对，例如：
  - `7 -> 6`

### 50.2 对开发 backlog 的直接影响

这页最值得推动的不是全局阈值，而是一个新的元件页子策略：

- `horizontal_component_block_pin`

其最小能力集应是：

1. 保留 `source_block_name / pin_slot / virtual_handle` 级别的证据；
2. 为 `KK1P / KK2P / KK3P / CD-WSK-H-J-G` 建立 block pin template；
3. 把 `same virtual text on both ends` 单独标成：
   - `self_pair_from_same_virtual_text`
   - 或 `internal_single_pin_stub`
4. 把 `1-21n103 / 1-21GD19 / HD1 / K-5 / JD6` 等外围文本从 `not_numeric` 废弃流中救出来，进入语义通道。

直接结论：

- `S0019` 证明了“元件接线图”至少还要继续拆成：
  - `horizontal_component_block_pin`
  - `vertical_component`

## 51. 2026-07-06 Batch 2 `S0021` 证明：左侧端子图的主问题不是表格识别，而是 `terminal_strip_column_mode`

Batch 2 已完成的端子页是：

- [S0021.md](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0021.md)
- [S0021.json](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0021.json)

这页再次把“看起来很规整”和“应该进表格提取器”区分开了：

- `135` 个 `line_group` 全为 horizontal；
- 主结构是 4 组固定 span 家族：
  - `40-115`
  - `127.5-202.5`
  - `217.5-292.5`
  - `310-385`
- accepted candidates 高度集中在固定的：
  - 局部序号列
  - 端子代号列
  - 说明/续接列
- `table_like_geometry=False`

所以这页的主问题不是“没有表格链路”，而是“已经进入 TerminalDiagramExtractor，但还没有列带感知模式”。

### 51.1 当前为什么已经能进主链

这页之所以现在就能以 `supplemental` 进入主链，不是因为结果已经足够完美，而是因为它已经满足三条低风险条件：

1. 页型稳定：
   - `屏端子图`
   - `route_target=TerminalDiagramExtractor`
2. 主链可穿透：
   - `433` 条文本
   - `135` 个 `line_group`
   - `1494` 个 terminal candidate
   - `877` 个 pair candidate
3. 失败区域集中：
   - review 主要落在左半下段 `DK/KLP/ZKK/UA/UB/UC/UN/3U0` 语义区

这说明它现在更适合作为“补充证据页”参与主链，而不是继续被挡在页外。

### 51.2 真正的 backlog 是什么

当前最值得推进的页型子策略应是：

- `terminal_strip_column_mode`

它的最小能力集应是：

1. 先按 span 家族分 strip；
2. 再按 `y` 步长锁行；
3. 将列角色拆开：
   - 局部序号列
   - 端子代号列
   - 语义列
4. 提升 `\\d+-\\d+n(\\d+)` 这类端子代号的抽值优先级；
5. 将以下文本旁路，不再参与普通 numeric ranking：
   - `未定义.*回路图`
   - `说明`
   - `上接`
   - `下接`
   - strip 标题

### 51.3 直接结论

`S0021` 证明了一点：

- 对端子图来说，导线主要负责锁定行；
- 真正的数字匹配主源是：
  - 端子列带
  - 端子代号正则抽值
  - 而不是统一邻近窗口

所以 Batch 2 到当前为止已经把 backlog 再往前推了一层：

- Batch 1：
  - `binary_input_grid`
- Batch 2：
  - `horizontal_component_block_pin`
  - `terminal_strip_column_mode`

## 52. 2026-07-06 `horizontal_component_block_pin` 第一刀已落地：`S0019` 的块内引脚对不再主导 non-discard 结果

基于 Batch 2 的 `S0019` 页审结论，本轮先落了 `horizontal_component_block_pin` 的第一步，不是试图一次做完整模板化，而是先把最扭曲结果的两类噪声明确降级：

- `block_internal_pin_pair`
- `self_pair_from_same_virtual_text`

### 52.1 代码层变化

当前已实现的最小能力包括：

1. `TerminalCandidate` 现在显式保留 `source_block_name`；
2. `Pair` evidence 现在透传：
   - `selected_left_source_block_name`
   - `selected_right_source_block_name`
3. horizontal 元件页（以及真实样本里同等语义的 non-vertical component 页）新增两道 guard：
   - 同一虚拟 text 命中线段两端时，直接标成 `self_pair_from_same_virtual_text`
   - 左右两端都来自同一 block，且值都是单字符 pin 时，直接标成 `block_internal_pin_pair`
4. `line_groups.py` 新增约束：
   - `元件接线图` 不走 `grid` 模式
   - 仍只在 `horizontal / vertical component` 之间决策

### 52.2 为什么还要补“元件页不进 grid”

第一次真实样本复跑暴露出一个很关键的中间问题：

- `S0019` 虽然本质是 horizontal component 页，但在 page classifier 接入后被判成了 `grid_heavy`
- 这让它走进了 `grid` line-group 逻辑，导致第一版 horizontal guard 根本没触发

所以这一轮同时把边界收紧为：

- `元件接线图` 即使有强网格感，也不该走 `grid-aware wire` 链
- 它们应该只在：
  - `horizontal_component`
  - `vertical_component`
 之间切分

这和 Batch 2 的页审结论是一致的。

### 52.3 真实样本验证结果

针对第二套样本重新实跑：

- 目录：
  - [phase12_horizontal_component_guard_second_v2/2_2](/F:/workspace/XJToolkit/.tmp/phase12_horizontal_component_guard_second_v2/2_2)

关键结果：

- `19 元件接线图1.dwg`
  - `line_groups.orientation`
    - `grid: 39 -> horizontal: 39`
  - `pair_status`
    - `39 discard`
    - `0 review`
    - `0 pass`
  - rationale 分布：
    - `block_internal_pin_pair: 29`
    - `self_pair_from_same_virtual_text: 8`
    - `missing numeric candidates on both sides: 2`
- `20 元件接线图2.dwg`
  - 保持：
    - `vertical: 54`
    - `24 review`
    - `30 discard`
  - 没被这轮 horizontal guard 误伤

直接结论：

- 这一步虽然还没把 `S0019` 变成“能正确抽出外部连线语义”，
- 但已经成功把最误导人的一层结果从“看起来像真的 pair”改成了“显式的内部引脚噪声分类”，
- 这正是 `horizontal_component_block_pin` 应有的第一阶段行为。

### 52.4 当前仍未完成的部分

这轮还没有做的，是 `S0019` 真正下一层的模板化：

- 还没建立 `KK1P / KK2P / KK3P / CD-WSK-H-J-G` 的 block pin template
- 还没把 `1-21n103 / 1-21GD19 / HD1 / K-5 / JD6` 这类外围标签正式接成语义通道
- 还没把 `discard` 的 block pin evidence 升级成更结构化的 “single-ended pin record / block pin mapping”

因此这轮的意义应理解为：

- 先把假的 pair 打碎
- 再在下一轮把真的 block-pin-to-semantic 映射接起来

## 53. 2026-07-06 `terminal_strip_column_mode` 第一刀已落地：`S0021` 从“几乎全 discard”切到“标准端子行可见 review”

基于 Batch 2 的 `S0021` 页审结论，这一轮没有先扩大 regex，也没有先做一张大黑名单，而是把第一刀放在 `candidates.py` 的端子页候选层：

- `屏端子图` 不再只靠左右端点小窗找候选，而是改成 `line-span query`
- terminal 页 horizontal 候选新增专用打分：
  - 降低 x 方向惩罚
  - 提高同 row 候选得分
- 新增三条端子页专用 rejection path：
  - `terminal_row_locked`
  - `terminal_strip_bypass_text`
  - `terminal_strip_column_filtered`

这刀的目标很明确：

- 先把固定列带里的“上下相邻多行竞争”打掉
- 让 `21 -> 211`、`69 -> 318` 这类标准端子行先从 `discard` 翻成可见的 `review`
- 暂时不去碰 `DK/KLP/ZKK` 语义区和 `310-385` 短桥接列带的专用解释

### 53.1 第二套真实样本结果

对第二套样本重新实跑：

- 产物目录：
  - [phase13_terminal_strip_column_mode_second/2_2](/F:/workspace/XJToolkit/.tmp/phase13_terminal_strip_column_mode_second/2_2)

关键结果：

- `21 左侧端子图1.dwg / S0021`
  - `pair_status`
    - 旧：`discard:108 / review:27`
    - 新：`discard:18 / review:117`
  - 旧的 `ambiguous candidate ordering` 已基本退出主导
  - 当前主导 rationale 变成标准端子行的显式 pair，例如：
    - `21 -> 211`
    - `69 -> 318`
    - `20 -> 210`
  - 当前 issue 分布：
    - `R-PAIR-LOW-CONFIDENCE: 90`
    - `R-PAIR-MISSING-SIDE: 27`
    - `R-DUPLICATE-SAME-LINE: 9`

直接结论：

- 这页已经从“系统几乎看不见真实 pair”推进到“系统能看到大量真实 pair，但仍需继续提置信/去重”。
- 这正符合 `terminal_strip_column_mode` 的第一阶段目标。

### 53.2 为什么第二套总体 issue 反而变多

第二套样本总体 issue 从上一版的 `398` 提高到 `597`，这不是简单回退，而是一个可解释的显性化副作用：

- 旧版里，很多标准端子行直接停在 `discard`
- 这一版里，这些行被翻成了 `review`
- 因此它们现在会正式进入 audit 规则链，主要体现为：
  - `R-PAIR-LOW-CONFIDENCE`
  - 少量 `R-DUPLICATE-SAME-LINE`

换句话说：

- 旧版更像“看不见问题”
- 新版更像“先把真实 pair 显示出来，再继续压重复和提置信”

### 53.3 第一套样本未回退

为了确认这刀不是只对第二套过拟合，又补跑了第一套：

- 产物目录：
  - [phase13_terminal_strip_column_mode_first](/F:/workspace/XJToolkit/.tmp/phase13_terminal_strip_column_mode_first)

结果：

- 第一套总 issue 为 `446`
- 相比 Phase 11 记录的 `461` 没有回退，反而略有下降

这说明：

- 当前这刀虽然主要是为 `S0021` 服务，
- 但在第一套端子页上也没有造成明显副作用。

### 53.4 当前剩余缺口

这轮之后，端子图方向的 backlog 也更清晰了：

- `23 右侧端子图1.dwg` 仍然是：
  - `discard:130`
- `24 右侧端子图2.dwg` 仍然是：
  - `review:55 / discard:37`
- `S0021` 自身仍有两块未解决区域：
  - `310-385` 的短桥接列带
  - `DK/KLP/ZKK` 与 `UA/UB/UC/UN/3U0` 的语义区

所以更准确的下一步不是“继续加全局正则”，而是：

1. 为右侧端子图补一个 mirrored 的 `terminal_strip_column_mode`
2. 为 `310-385` 短桥接列带补单独列角色解释
3. 再决定 `DK/KLP/ZKK` 这类语义右端是进入 pair、语义通道，还是继续只做备注

## 54. 2026-07-06 `右侧端子图` mirrored terminal-strip 已落地：`S0023` 不再整页候选饥饿

在 `S0021` 的左侧端子图首刀之后，下一块最突出的缺口是：

- `23 右侧端子图1.dwg`

上一版真实样本里，这页是：

- `discard:130`
- 且全部 rationale 都是：
  - `missing numeric candidates on both sides`

但进一步核对 `terminal_candidates.parquet` 后已确认，这不是“页里没有数字”，而是“数字全被列带 gate 误过滤掉了”。

### 54.1 真正的问题是什么

当前样本已经证明，右侧端子图不能直接复用左侧端子图的列偏移。

左侧端子图 `S0021` 的稳定列带是：

- `start_x + 23.5`
- `start_x + 31.0`

而右侧端子图 `S0023` / `S0024` 的稳定列带则是：

- `start_x + 26.0` 左右的派生端子列
- `start_x + 48.5` 左右的纯数字列

典型样本：

- `S0023`
  - `[40,115] -> 66.0 / 88.5`
  - `[130,205] -> 156.0 / 178.5`
  - `[222.5,297.5] -> 248.5 / 271.0`
- `S0024`
  - `[35,110] -> 61.0 / 83.5`

所以旧版的问题不是没抽到对象，而是：

- 把右侧端子图按左侧端子图的列偏移规则过滤
- 结果把 `1-21n132`、`1-21n231`、`20`、`45` 这类本来很合理的文本全部打成：
  - `terminal_strip_column_filtered`

### 54.2 这轮代码变化

这一轮继续保持小切片，仍然只改端子页候选层，而不去碰 pair 规则层：

- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
  - `terminal_strip_layout_mode`
    - 现在会区分：
      - `left_terminal`
      - `right_terminal`
  - `terminal_strip_allowed_offset_range`
    - `left_terminal`
      - left: `22.5..25.5`
      - right: `29.5..32.5`
    - `right_terminal`
      - left: `24.5..28.5`
      - right: `47.0..50.5`

也就是说：

- 左侧端子图继续保持原来的列角色；
- 右侧端子图改成 mirrored 的列角色；
- `310-385` 这类短桥接列带仍先排除在专用 gate 之外，避免这一轮过拟合。

### 54.3 第二套真实样本结果

对第二套样本重新实跑：

- 产物目录：
  - [phase14_right_terminal_mirror_second/2_2](/F:/workspace/XJToolkit/.tmp/phase14_right_terminal_mirror_second/2_2)

关键结果：

- `23 右侧端子图1.dwg / S0023`
  - 旧：
    - `discard:130`
  - 新：
    - `review:114`
    - `discard:16`
  - 当前开始稳定产出 mirrored pair，例如：
    - `132 -> 20`
    - `229 -> 45`
    - `228 -> 44`
    - `227 -> 43`

- `24 右侧端子图2.dwg / S0024`
  - 旧：
    - `review:55 / discard:37`
    - 且经常左右两边选到同一文本
  - 新：
    - `review:54 / discard:38`
    - 但 pair 结构已更合理，开始稳定产出：
      - `421 -> 45`
      - `417 -> 41`
      - `418 -> 40`

直接结论：

- `S0023` 的主要问题已经从“完全看不见真实 pair”推进到“能看到大量真实 pair，但仍偏低置信”；
- `S0024` 也从“同一文本双侧复用”推进到“mirrored 列角色基本成立”。

### 54.4 为什么 issue 又上升

这一轮之后，第二套总体 issue 从 `597` 提高到 `654`，第一套总体 issue 也从 `446` 提高到 `559`。

这同样不应简单理解为回退，而是右侧端子页被显性化后的自然结果：

- 旧版里，右侧端子图的大量真实 pair 直接停在 `discard`
- 新版里，这些 pair 被翻成了 `review`
- 因此它们正式进入规则链，主要表现为：
  - `R-PAIR-LOW-CONFIDENCE`
  - 少量 `R-PAIR-MISSING-SIDE`

所以当前状态更准确地说是：

- 旧版：右侧端子页大量“隐身”
- 新版：右侧端子页大量“可见但待收敛”

### 54.5 当前剩余缺口

这轮之后，端子图方向的 backlog 再次收口：

1. `310-385` 的短桥接列带仍未进入专用解释
2. `DK/KLP/ZKK/CLP` 等语义列是否应进入 pair，仍未决定
3. 右侧端子图虽然能出 pair，但大量仍停在 `review`
4. 端子图下一阶段的核心不再是“扩大召回”，而是：
   - 去重
   - 提置信
   - 分离“标准端子行”和“语义设备行”

## 55. 2026-07-06 `310-385` 短桥接带已从假双侧配对收口为列角色规则

在 `phase14` 之后，端子图最明显的结构性噪声已经收敛到一类很具体的问题：

- `S0021` 的 `310-385` 区段会产出：
  - `110 -> 110`
  - `109 -> 109`
  - `328 -> 328`
- `S0024` 的同区段会产出整列：
  - `10 -> 10`
  - `9 -> 9`
  - `...`
  - `1 -> 1`

这类 pair 的共同点不是“数值抽不到”，而是候选层把短桥接带里的：

- 延续列
- 局部序号列
- 单列 continuation

全都一起塞进了左右两侧排序。

### 55.1 真实版面已经足够证明：这里不是普通双侧端子带

并发子代理和主线程对真实产物的复核现在已经对齐：

- 第二套 `S0021 / 21 左侧端子图1.dwg`
  - `x≈311`
    - `1-21n109/110`
  - `x≈333.5`
    - `73..81`
  - `x≈341`
    - `3-21n322..330`
  - 这不是普通的左右端子对，更像：
    - 左延续列
    - 中间局部序号列
    - 右延续列

- 第二套 `S0024 / 24 右侧端子图2.dwg`
  - `x≈359`
    - `10..1`
  - 旁边只有 `未定义...` 说明文字
  - 这不是双侧端子带，而是“单列局部序号带”

- 第一套 `S0027 / 26 右侧端子图1.dwg`
  - `x≈351`
    - `5n628 / 3-2n428 / 1-2n428 ...`
  - `x≈374`
    - `9..1`
  - `x≈381`
    - `1-2n420 / 1-2n110 / 3-2n108 ...`
  - 这再次证明：
    - 右侧端子页家族里稳定存在“延续列 - 局部序号列 - 延续列”的短桥接模式

所以这里的首要目标不是继续放宽召回，而是把局部序号列从普通 pair 候选里拆出去。

### 55.2 本轮代码收口

本轮继续保持小切片，只动候选层：

- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
  - 在 `terminal_strip_row_lock` 之后新增短桥接带角色收口
  - 触发范围：
    - `屏端子图`
    - horizontal line group
    - `length 70..80`
    - `start_x >= 300`
  - 行内按 numeric x 列聚类
  - 若同一行存在两个 derived continuation 列：
    - 左侧只保留最左 derived 列
    - 右侧只保留最右 derived 列
  - 若同一行只剩一个 derived continuation 列：
    - 按其相对列序决定是 left 还是 right 单侧 continuation
  - 若整行只有一根 numeric 列：
    - 只保留更合理的一侧
    - 另一侧改成 `missing side`

新增 rejection path：

- `terminal_short_bridge_role_filtered`
- `terminal_short_bridge_single_column`

这刀的目标很窄：

- 不再让局部序号列参与左右两侧普通排名
- 不再让同一根 numeric 列同时喂给左右两侧
- 先把假双侧 `X -> X` 压掉，再决定是否引入 specialized continuation semantics

### 55.3 回归与真实样本结果

针对本轮切片，先跑了候选 / 端子 / router 支撑回归：

- `python -m pytest -q tests/unit/test_terminal_candidates.py -k "short_bridge or mirrored_right_terminal or row_locks_terminal_strip"`
  - `4 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "mirrored_right_terminal_strip_candidates or row_locks_terminal_strip_candidates"`
  - `2 passed`
- `python -m pytest -q tests/unit/test_pairs_and_rules.py tests/unit/test_line_groups.py tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py`
  - `40 passed`

然后对两套真实样本重新实跑：

- 第二套：
  - [phase15_terminal_short_bridge_second/2_2](/F:/workspace/XJToolkit/.tmp/phase15_terminal_short_bridge_second/2_2)
- 第一套：
  - [phase15_terminal_short_bridge_first](/F:/workspace/XJToolkit/.tmp/phase15_terminal_short_bridge_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

关键结果：

- 第二套总体 issue：
  - `654 -> 648`
- 第一套总体 issue：
  - `559 -> 518`

- `S0021`
  - 旧：
    - `110 -> 110`
    - `109 -> 109`
    - `328 -> 328`
  - 新：
    - `110 -> 330`
    - `109 -> 329`
    - `? -> 328..322`
  - 也就是说，这个区段已经从“假双侧自配对”转成了“少量 bridge pair + 大量单侧 continuation”

- `S0024`
  - 旧：
    - `10 -> 10 .. 1 -> 1`
  - 新：
    - 全部变成 `missing left candidate`
  - 这和真实版面是一致的：这里只有单列局部序号，不该硬凑双侧 pair

- `S0027`
  - 旧：
    - 大量 `628 -> 628`、`427 -> 427`、`216 -> 216`
  - 新：
    - 大量变成单侧 continuation：
      - `628 -> ?`
      - `? -> 5`
      - `427 -> ?`
      - `216 -> ?`
  - 但双延续列同值仍残留：
    - `420 -> 420`
    - `110 -> 110`
    - `109 -> 109`
    - `430 -> 430`
    - `419 -> 419`

直接结论：

- 这轮已经成功解决“同一列被左右两侧同时吃掉”的主问题；
- 但对于“双延续列、同值、不同 text_id”的 continuation pair，系统还缺 specialized semantics。

### 55.4 现在剩下的端子页 backlog 更清楚了

短桥接带这刀落地后，端子图方向的 backlog 进一步收口成三件事：

1. 语义列分流
   - `DK/KLP/ZKK/CLP`
   - `UA/UB/UC/UN/3U0`
   - `AC230V`
   - `Shielding layer`
   - `说明 / 上接 / 未定义...`

2. 双延续列同值 continuation 的 specialized semantics
   - `420 -> 420`
   - `110 -> 110`
   - `109 -> 109`
   - 这类 pair 不再是“同一列双吃”，但也未必是普通端子 pair

3. 端子页 review pair 的提置信
   - 当前最该做的已不是继续放宽窗口
   - 而是：
     - 语义旁路
     - continuation-aware pairing
     - review / discard 的结构性降噪
