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

## 56. 2026-07-06 `terminal_semantic_local_numeric` 已落地：语义行里的局部小数字不再默认参与 ordinary pair

在 `phase15` 的短桥接带收口之后，端子页剩下的一类稳定噪声已经很明确：

- 行内同时有 `n###` 导出端子文本；
- 同时夹着 `DK/KLP/ZKK/CLP`、`UA/UB/UC/UN/3U0`、`AC230V`、`Shielding layer`、`CZ/AK` 之类语义文本；
- 旁边还挂着一个 `1..44` 的局部小数字；
- 当前系统会把这个小数字继续当 ordinary terminal，一路形成 `403 -> 10`、`602 -> 4`、`132 -> 20`、`417 -> 41` 这类低置信 pair。

### 56.1 本轮代码收口

本轮继续只动安全写面：

- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
  - 新增 `_TERMINAL_SEMANTIC_ROW_PATTERNS`
  - 新增 `_apply_terminal_semantic_row_local_numeric_filter(...)`
  - 在 short-bridge 角色收口之后、rank 赋值之前执行
- [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py)
  - 补两条窄单测：
    - `KLP` 语义行压掉 `3 -> 108` 左侧小数字
    - `AC230V` / `AK` 语义行压掉 `602 -> 4` 右侧小数字

当前 rejection path：

- `terminal_semantic_local_numeric`

触发条件刻意保持很窄：

- 仅 `屏端子图`
- 仅普通端子带 `start_x < 300`
- 仅 horizontal / non-vertical line group
- 行内必须先命中语义 marker
- 被压掉的必须是 `text == value`、纯数字、且长度 `<= 2` 的 accepted local numeric

### 56.2 回归与真实样本结果

支撑回归：

- `python -m pytest -q tests/unit/test_terminal_candidates.py -k "semantic or short_bridge or mirrored_right_terminal or row_locks_terminal_strip"`
  - `6 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "mirrored_right_terminal_strip_candidates or row_locks_terminal_strip_candidates"`
  - `2 passed`
- `python -m pytest -q tests/unit/test_pairs_and_rules.py tests/unit/test_line_groups.py tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py`
  - `40 passed`

真实样本 `run-audit`：

- 第二套：
  - [phase16_terminal_semantic_rows_second/2_2](/F:/workspace/XJToolkit/.tmp/phase16_terminal_semantic_rows_second/2_2)
  - 总 issue：`648 -> 697`
  - 但构成变为：
    - `R-PAIR-LOW-CONFIDENCE: 267 -> 203`
    - `R-PAIR-MISSING-SIDE: 381 -> 494`
- 第一套：
  - [phase16_terminal_semantic_rows_first](/F:/workspace/XJToolkit/.tmp/phase16_terminal_semantic_rows_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
  - 总 issue：`518 -> 487`
  - 构成变为：
    - `R-PAIR-LOW-CONFIDENCE: 143 -> 84`
    - `R-PAIR-MISSING-SIDE: 374 -> 402`

这说明这刀的主要效果不是“直接减少全部 issue”，而是把一批原本会冒充 ordinary pair 的低置信双侧配对，改写成更保守的单侧缺失。

### 56.3 关键页上的具体变化

- 第二套 `S0021`
  - `11 -> 708`、`9 -> 707`、`6 -> 704`、`20 -> 132` 这类语义行 pair 被改成 `missing left candidate`
  - 页级 issue `118 -> 113`
  - `LOW-CONFIDENCE -14`，`MISSING-SIDE +9`
- 第二套 `S0022`
  - `41 -> 417`、`10 -> 403`、`4 -> 509` 一类 pair 被改成单侧 continuation
  - 页级 issue `42 -> 72`
  - `LOW-CONFIDENCE -12`，`MISSING-SIDE +42`
- 第二套 `S0023 / S0024`
  - `132 -> 20`、`114 -> 4`、`417 -> 41`、`414 -> 36` 等 mirrored pair 被拆成单侧缺失
  - 这批变化主要来自含 `DK/KLP/ZK/CLP/CZ/GND` 的语义行
- 第一套 `S0025`
  - 页级 issue `140 -> 107`
  - 典型变化是 `14 -> 411`、`1 -> 103`、`1 -> 214` 被收口成 `missing left candidate`
- 第一套 `S0027`
  - 页级 issue `114 -> 129`
  - 但被打掉的多是 `210 -> 6`、`103 -> 1`、`702 -> 4` 这类 `DK/DC/IA'/3U0` 语义行小数字 pair
- 第一套 `S0028`
  - 页级 issue `34 -> 21`
  - `Shielding layer` / `B code` 一类语义行上的局部小数字明显被收口

### 56.4 并发子代理复核结论

并发子代理对 `S0021 / S0024 / S0027` 做了只读复核，结论偏正面：

- `S0024 / G1121 / 421 -> 44`
- `S0027 / G0852 / 105 -> 10`
- `S0027 / G1004 / 214 -> 2`

这些最像“可能误杀”的例子，复核后依然更像语义行里的局部序号，而不像必须保留的 ordinary terminal pair，因为同组同时存在：

- `CLP / KK / DK / CZ-E / GND`
- `IA' / IB' / IC' / 3U0`
- 或 `n###` continuation 文本

直接结论：

- 当前这条规则更像“净收益”，不建议立刻回滚。
- 它的副作用不是抽不到数字，而是把原先的假 ordinary pair 显性化成 `missing-side`。
- 因此端子页的下一步重点已经更清楚：
  1. continuation / semantic row 的 specialized pair 语义
  2. `missing-side` 中哪些应转为“语义旁注”而不是 issue
  3. 是否把 `DK/KLP/ZKK/CLP` 这类语义列真正送入单独通道，而不是继续让它们只以 rejection marker 身份存在

## 57. 2026-07-06 任务书逐条完成度审计

根据当前工作树、当前测试、当前 `.tmp` 真实样本产物，对 [任务书.md](./任务书.md) 的主链要求做一次重新对齐后的完成度审计。这里不再把“桌面端做了很多”当成功，而只看 DWG 审计 MVP 主链是否被强证据证明。

### 57.1 审计口径

本轮状态标签只分四类：

- `已完成（强证据）`
- `部分实现但未验证`
- `明确未完成`
- `已偏航`

强证据仅接受：

- 当前仓库代码
- 当前测试
- 当前 `.tmp` 真实样本产物
- 当前导出报告 / findings / audit

不接受“文件已经存在”“之前做过”“历史上跑通过”的间接叙述。

### 57.2 主链完成度总表

| 任务书要求 | 当前状态 | 证据 / 结论 |
|---|---|---|
| 输入一个项目目录下的多张 DWG，稳定生成结构化 findings 运行态 | 已完成（强证据） | 两套真实样本都能稳定产出 `manifest.json + findings/`，见 `.tmp/phase16_terminal_semantic_rows_{second,first}`。 |
| findings 默认属于内部运行态，不再把 `page_findings` 当默认正式交付物 | 已完成（强证据） | 最新真实样本产物默认没有 `findings/page_findings/` 目录，但 `findings.json` 仍保留 `page_findings_count/page_findings`。 |
| 先做页级分类，再决定识别器 | 部分实现但未验证 | `pipeline.py` 已先 `classify_pages()` 再 `enrich_pages_from_classifications()`；`findings.json.page_findings[]` 里也有 `page_type/route_target`。但真实样本里元件页仍被误判成 `WireDiagramExtractor` 或 `TableExtractor`，说明“已接入”不等于“已闭环”。 |
| Page Router 真实决定 extractor 分流 | 部分实现但未验证 | 当前强证据已能证明：`LayoutOnlyExtractor` 页不会进 PairBuilder，元件页已能稳定命中 `ComponentDiagramExtractor`，端子页已能稳定命中 `TerminalDiagramExtractor`。但 `Wire/Component/Terminal` 仍共享 PairBuilder 主链，不能说已经彻底拆成完全独立 extractor。 |
| 普通回路图不能继续退化成“所有图同一条几何 pair page” | 部分实现但未验证 | 真实产物已出现 `grid / horizontal / vertical` 三种 `line_group` 形态，说明不是所有页都完全同构；但 `Wire/Component/Terminal` 仍共享同一条 `build_line_groups -> build_terminal_candidates -> build_pairs` 主链，只是内部再分支。 |
| 普通回路图页型覆盖 | 已完成（强证据） | 两套样本中的 `04-16` 主回路页均稳定产出 `WireDiagramExtractor` 路由和非零 `line_group/pair`。 |
| 端子图页型覆盖 | 已完成（强证据） | 两套样本中的 `S0021-S0024` / `S0025-S0028` 稳定命中 `TerminalDiagramExtractor`，并产出大量 pair / issue。 |
| 元件接线图页型覆盖 | 已完成（强证据） | 最新 `phase17_component_route_closure_{second,first}` 中，第二套 `S0019/S0020` 与第一套 `S0022/S0023/S0024` 均已回到 `page_type=元件接线图`、`route_target=ComponentDiagramExtractor`，并保留 component 风格 pair 产物。 |
| 表格型图页型覆盖，或明确证明真实样本暂无该类命中 | 已完成（强证据） | 最新 `phase17_component_route_closure_{second,first}` 的 `table_extraction_summary` 都是 `table_pages=0 / total_mappings=0`，且两套真实样本都没有稳定 `TableExtractor` 命中；这说明当前两套真实项目里暂无被稳定识别出的表格型页。 |
| 表格型图要形成独立高置信信源（`table_mapping`） | 部分实现但未验证 | `table_extractor.py`、单测和规则接线都存在，但我在当前 `.tmp` 真实样本产物中没有找到任何 `table_mapping`、`evidence.source=table_mapping` 或非零 `table_extraction_summary`。 |
| 背板图必须识别但默认不进入配对审计 | 已完成（强证据） | 两套最新真实产物中背板图均为 `LayoutOnlyExtractor` / `line_group_count=0 / pair_count=0`。 |
| terminal 页语义列应从普通 pair 中正确分流 | 部分实现但未验证 | `terminal_semantic_local_numeric` 已在真实样本上起效，能把 `403->10`、`602->4`、`417->41` 一类伪 ordinary pair 收口为 `missing-side`；但它目前仍是 rejection guard，还没升级成独立“语义通道”。 |
| continuation 类 pair 需要专用语义，而不是继续误当普通 pair | 明确未完成 | `S0021/S0024/S0027` 的短桥接带虽然已不再 `X->X` 自配对，但 `420->420 / 110->110 / 109->109` 一类双延续列同值 continuation 仍没有专用语义。 |
| `run-audit` 输出 issue 必须具备可复核证据字段 | 部分实现但未验证 | `issues.json/parquet` 里确实有 `filename/sheet_id/line_group_id/left_value/right_value/rule_id/confidence/evidence_refs`，但 `evidence` 和 `evidence_refs` 当前被序列化成字符串，不是直接结构化对象。证据“存在”，但最终交付形态还不够干净。 |
| 规则必须基于 findings，不允许直接回读 DWG | 已完成（强证据） | `run-audit` 只消费 `findings/` 产物；`rules.py` 不触碰 DWG/DXF。 |
| 默认不把 `page_findings` 当长期正式交付 | 已完成（强证据） | 当前默认运行态已满足。 |
| 不能继续依赖单一大脚本解释所有图种 | 部分实现但未验证 | 方向上已经拆出 `PageClassifier / PageRouter / TableExtractor`，但真实样本还不能证明 component/table 分支已经稳定成立。 |
| 真实正确样本不应被打出大量 hard error 洪峰 | 已完成（强证据） | 当前两套真实样本的 issue 主要是 `review` 型 `R-PAIR-LOW-CONFIDENCE / R-PAIR-MISSING-SIDE`，没有出现“把整套图当明显错误”的 hard error 洪峰。 |

### 57.3 当前距离主链闭环最近的未完成项

在 `phase17_component_route_closure_{second,first}` 重新读图之后，元件页误路由问题已经明显收口，因此当前最接近任务书主链的剩余未完成项收敛为两条：

1. **continuation-aware pairing 仍未建立专用语义。**
   - `S0021/S0024/S0027` 里双延续列同值 `420->420 / 110->110 / 109->109` 仍未脱离普通 pair 语义。
2. **issue 证据虽然完整存在，但导出形态仍偏“字符串包 JSON”。**
   - `issues.json` / `issues.parquet` 中 `evidence`、`evidence_refs` 仍被序列化成字符串，而不是直接结构化对象。

这两条比“继续做桌面端”更接近任务书主链，也比继续堆 `candidates.py` 阈值更直接回答“审计证据是否可复核、continuation 是否被正确理解”。

### 57.4 本轮不应继续优先的工作

以下工作本身可能有价值，但在当前任务书闭环审计下，不应继续占主优先级：

1. 桌面端 UI / Tauri / preview / 报告交互体验
2. 继续单纯以总 issue 数升降来评价成功
3. 在 `candidates.py` 里继续做不回答页型问题的全局阈值堆叠
4. 把 `TableExtractor` 文件存在本身，当作“表格链已完成”的证明
5. 把 `page_findings` 默认落盘重新当作正式交付物

### 57.5 因此，本轮唯一合理的核心切片

基于以上审计，本轮主线程已经先完成了：

- **修正并验证“元件接线图不应再被误路由成 Wire/Table”这一页级分类/路由闭环切片。**

下一轮若继续沿任务书最短路径推进，更合适的目标将是：

- continuation-aware pairing 的专用语义；
- 或 issue 导出中的结构化证据收口。

## 58. 2026-07-06 `phase17_component_route_closure`：元件接线图已从 Wire/Table 误路由中收口

基于 57 节的任务书完成度审计，本轮只推进了一个核心切片：

- 修正页级分类器里“元件接线图先保组件页身份”的优先级；
- 不再让 `grid_heavy` 或 `table_like` 在真实元件页上抢走路由。

### 58.1 本轮代码变化

本轮只修改页级分类切片：

- [page_classifier.py](/F:/workspace/XJToolkit/src/dwg_audit/page_classifier.py)
  - `元件接线图` 现在优先判为：
    - `vertical_component`
    - 或 `horizontal_component`
  - 不再先被 `table_like` 或 `grid_heavy` 抢成：
    - `表格型图`
    - `二次原理图`
- [test_page_classifier.py](/F:/workspace/XJToolkit/tests/unit/test_page_classifier.py)
  - 新增：
    - horizontal component 优先于 `grid_heavy`
    - component 优先于 `table_like`

### 58.2 定向测试结果

- `python -m pytest -q tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py tests/unit/test_line_groups.py tests/unit/test_pairs_and_rules.py`
  - `42 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "component or terminal or page_findings or supplemental"`
  - `10 passed`

### 58.3 真实样本 rerun 结果

第二套：

- [phase17_component_route_closure_second/2_2](/F:/workspace/XJToolkit/.tmp/phase17_component_route_closure_second/2_2)
- `S0019 / 19 元件接线图1.dwg`
  - `page_type = 元件接线图`
  - `page_subtype = horizontal_component`
  - `route_target = ComponentDiagramExtractor`
  - `pair_count = 39`
- `S0020 / 20 元件接线图2.dwg`
  - `page_type = 元件接线图`
  - `route_target = ComponentDiagramExtractor`
  - `pair_count = 54`
  - `non_discard_pair_count = 24`
- 全项目 `route_target` 分布变成：
  - `WireDiagramExtractor: 13`
  - `ComponentDiagramExtractor: 2`
  - `TerminalDiagramExtractor: 4`
  - `LayoutOnlyExtractor: 2`
  - `SkipExtractor: 3`
- `table_extraction_summary`
  - `table_pages = 0`
  - `total_mappings = 0`

第一套：

- [phase17_component_route_closure_first](/F:/workspace/XJToolkit/.tmp/phase17_component_route_closure_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- `S0022 / 21 元件接线图1.dwg`
  - `route_target = ComponentDiagramExtractor`
  - `pair_count = 47`
- `S0023 / 22 元件接线图2.dwg`
  - 不再是假 `TableExtractor`
  - 现在为：
    - `page_type = 元件接线图`
    - `route_target = ComponentDiagramExtractor`
    - `pair_count = 68`
    - `non_discard_pair_count = 30`
- `S0024 / 23 元件接线图3.dwg`
  - `route_target = ComponentDiagramExtractor`
  - `pair_count = 36`
- 全项目 `table_extraction_summary`
  - `table_pages = 0`
  - `total_mappings = 0`

### 58.4 对任务书主链的意义

这轮的真正收益不是“issue 变少”，而是：

1. **元件接线图终于被真实样本明确命中到 `ComponentDiagramExtractor`。**
2. **之前那个假表格页 `S0023` 已被收回，不再拿“文件里有 TableExtractor”冒充表格链完成。**
3. **当前两套真实项目都没有稳定 `TableExtractor` 命中，因此现在可以更有把握地说：这两套真实样本中暂无被稳定识别出的表格型页。**

### 58.5 下游 audit 影响

- 第二套总 issue：
  - `697 -> 697`
  - 说明这刀主要修正的是页型/路由闭环证据，没有扰动现有审计结果。
- 第一套总 issue：
  - `487 -> 517`
  - 原因不是简单回退，而是 `S0023` 从假 `TableExtractor / 0 pair` 回到真实 component 链后，新增了 `30` 条 non-discard pair，正式进入审计主链。

直接结论：

- 从任务书视角看，这个变化是朝正确方向前进，因为它让“元件接线图属于 component 路由”这件事第一次被真实样本严格证明了。
- 当前仍不能把 `TableExtractor` 视为真实样本闭环能力，但现在至少不会再被假阳性的 `table_like` 页误导。

## 59. 2026-07-06 任务书完成度审计刷新：以当前头部代码 + `phase18/phase19` 产物为准，覆盖 57 节中过时判断

57 节里的两条关键判断已经被当前头部代码推翻，不能继续当作 SSoT：

1. `issues.json / issues.parquet` 的 `evidence`、`evidence_refs` 现在已经是结构对象，不再是 JSON 字符串。
2. `continuation_same_value` 已经进入 pair 语义层，并从 ordinary low-confidence / graph 规则里旁路，不再是“完全未开始”。

因此下面这版审计，统一以当前头部代码和下面这些新证据为准：

- 第一套当前头部真实样本：
  - [phase18_terminal_continuation_first findings.json](/F:/workspace/XJToolkit/.tmp/phase18_terminal_continuation_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/findings.json)
  - [phase18_terminal_continuation_first issues.json](/F:/workspace/XJToolkit/.tmp/phase18_terminal_continuation_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/audit/issues.json)
- 第二套当前头部真实样本：
  - [phase19_table_proof_second findings.json](/F:/workspace/XJToolkit/.tmp/phase19_table_proof_second/2_2/findings/findings.json)
  - [phase19_table_proof_second issues.json](/F:/workspace/XJToolkit/.tmp/phase19_table_proof_second/2_2/audit/issues.json)
- Synthetic 表格页集成证明：
  - [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)
  - 本轮定向 pytest：`11 passed`
- 当前全量测试：
  - `python -m pytest -q` -> `143 passed`

### 59.1 更新后的主链完成度总表

| 任务书要求 | 当前状态 | 当前强证据 |
|---|---|---|
| 输入项目目录下多张 DWG，稳定生成 findings 运行态 | 已完成（强证据） | `phase18/phase19` 两套真实样本都稳定生成 `manifest.json + findings/`。 |
| findings 默认属于内部运行态，不把 `page_findings` 当默认正式交付目录 | 已完成（强证据） | 两套最新真实样本都没有 `findings/page_findings/` 目录，且 `artifacts.findings` 列表不含 `page_findings/`。 |
| 每页都有稳定 `page_type` | 已完成（强证据） | 两套最新 [findings.json](/F:/workspace/XJToolkit/.tmp/phase19_table_proof_second/2_2/findings/findings.json) 的 `page_findings[]` 都有 `page_type`。 |
| 每页都有稳定 `route_target` | 已完成（强证据） | 两套最新 `pages.parquet` / `page_findings[]` 都有非空 `route_target`；第一套路由分布 `13/3/4/4/4`，第二套 `13/2/4/2/3`。 |
| Page Router 真实接管 extractor 分流 | 已完成（强证据） | 当前 pipeline 先 `classify_pages()` 再 `enrich_pages_from_classifications()`，并按 `route_supports_pairing / route_supports_table` 分出 pairing 链与 table 链，见 [pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py:86) 到 [pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py:164)。 |
| 普通回路图、元件接线图、端子图、背板图/skip 在真实样本中实际覆盖 | 已完成（强证据） | 第一套、第二套当前头部产物都已实际覆盖并分流到 `Wire / Component / Terminal / LayoutOnly / Skip`。 |
| 表格型图若真实样本暂无命中，需要明确证明；若要证明 extractor，则可用隔离 synthetic 样本 | 已完成（强证据） | 两套最新真实样本 `table_extraction_summary = 0/0/0`，且无 `TableExtractor` 命中；同时新增 `analyze-project` 级 synthetic 集成测试，证明表格页可命中 `TableExtractor` 并产出 `table_mapping`。 |
| TableExtractor 要形成独立高置信信源 | 已完成（强证据，synthetic） | 新集成测试证明：表格页 `route_target=TableExtractor`，`table_extraction_summary.table_pages=1`，`pairs.evidence.source=table_mapping`。真实样本当前仍无命中。 |
| `run-audit` issue 必须具备可复核证据 | 已完成（强证据） | 两套最新 `issues.json` 顶层已有 `rule_id/confidence/sheet_id/line_group_id/left_value/right_value/evidence/evidence_refs`；`filename/sheet_no` 存在于结构化 `evidence/evidence_refs` 中。 |
| terminal 页语义列应从普通 pair 中分流 | 部分实现但未验证 | 当前已有 `terminal_semantic_local_numeric` 等护栏，能把大量假 ordinary pair 收口为 `missing-side`；但还没有独立 `semantic_channel` 或专用 issue 语义。 |
| continuation 类 pair 需要专用语义 | 部分实现但未验证 | 当前 `continuation_same_value` 已在 [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py:359) 打标签，并在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py:197) 等处旁路 ordinary audit；但 pair 自身仍借用 `review` 状态壳，没有完全独立 channel。 |
| 页级分类结果应显式提供 `audit_disposition` | 部分实现但未验证 | 当前落盘的是 `audit_role + route_target`，没有单独 `audit_disposition` 字段。这在功能上接近，但合同仍未完全对齐任务书。 |
| 不能再依赖单一大脚本解释所有图种 | 部分实现但未验证 | 现在已经有 `PageClassifier / PageRouter / TableExtractor / per-type route`，但 `Wire/Component/Terminal` 仍共享较多 PairBuilder 主链。 |

### 59.2 当前距离主链闭环最近的未完成项

在 `phase18`、`phase19` 之后，当前离任务书主链最近、且最值得继续推进的剩余缺口已经收敛为这 3 条：

1. **terminal 页语义列仍只是 rejection guard，不是显式 `semantic_channel`。**
   - 现在能把很多假 ordinary pair 打成 `missing-side`，但系统还没有把这些语义列当成“被理解的语义证据”。
2. **`continuation_same_value` 只是“已打标签并旁路 ordinary audit”，还不是完全独立的 pair/channel 语义。**
   - 这条已经不再是“未开始”，但也还没到最终完成。
3. **`audit_disposition` 合同仍未显式落盘。**
   - 当前 `audit_role + route_target` 足够驱动运行，但任务书要求的字段名和分层语义还没有完整对齐。

### 59.3 本轮之后不应再优先的方向

以下方向此时继续投入，都会偏离“任务书主链证明”：

1. 桌面端 / Tauri / preview 交互细节
2. 用总 issue 数变化冒充成功
3. 继续把 `TableExtractor` 说成“未证明”，忽略当前 synthetic 闭环和真实样本无命中的双重证据
4. 继续把 `issues.evidence` 说成 JSON 字符串

## 60. 2026-07-06 `phase19_table_proof`：在真实样本无表格页命中的前提下，补齐 `TableExtractor` 的任务书级闭环证明

这轮只推进了一个核心切片：

- 不再等待真实样本里出现假阳性的 `TableExtractor` 页；
- 直接按任务书允许的路径，用隔离 synthetic `analyze-project` 集成测试证明表格页闭环；
- 同时把 `page_findings` 对 `TableExtractor` 的描述改成反映当前真实行为，而不是继续写成 “pending”。

### 60.1 本轮代码变化

- [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)
  - 新增项目级 synthetic 用例：
    - 同一项目里同时放一个普通回路页和一个表格页
    - 断言普通页走 `WireDiagramExtractor`
    - 断言表格页走 `TableExtractor`
    - 断言 `table_extraction_summary.table_pages = 1`
    - 断言 `pairs.evidence.source = table_mapping`
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
  - `page_findings` 现在会按页透出：
    - `table_mapping_count`
    - `three_column_table`
  - `TableExtractor` 页的 `recognition_strategy` / `number_matching_strategy` 不再默认写成 “still pending”
  - 当表格几何存在但未命中表格链时，`open_questions` 会明确提示“看起来像 table-heavy，但没有路由进 table extractor”

### 60.2 定向测试结果

- `python -m pytest -q tests/integration/test_analyze_project.py -k "table_like_page_to_table_extractor or component or terminal or supplemental"`
  - `11 passed`
- `python -m pytest -q tests/unit/test_table_extractor.py tests/unit/test_report_artifacts.py -k "table or page_findings"`
  - `6 passed`
- `python -m pytest -q`
  - `143 passed`

### 60.3 当前头部真实样本 rerun 结果

第二套最新 current-head 产物：

- [phase19_table_proof_second/2_2](/F:/workspace/XJToolkit/.tmp/phase19_table_proof_second/2_2)
- `route_target` 分布保持：
  - `WireDiagramExtractor: 13`
  - `ComponentDiagramExtractor: 2`
  - `TerminalDiagramExtractor: 4`
  - `LayoutOnlyExtractor: 2`
  - `SkipExtractor: 3`
- `table_extraction_summary`
  - `table_pages = 0`
  - `three_column_pages = 0`
  - `total_mappings = 0`
- `page_findings/` 目录仍未默认落盘
- `run-audit` 当前输出的 `issues.json`
  - `evidence` 是 `dict`
  - `evidence_refs` 是 `list`
  - `filename/sheet_no` 仍可直接从 `evidence` 读取

### 60.4 这轮对任务书主链的真正意义

这轮的价值不是“制造一个假表格真实样本”，而是把任务书里的这条要求真正补齐了：

- **真实样本当前暂无稳定表格页命中**，这件事现在有 current-head rerun 强证据；
- **`TableExtractor` 本身不是空壳**，因为它已经有项目级 synthetic `analyze-project` 闭环证明；
- **页级 findings 对表格页的解释不再滞后于代码现状**。

因此，从任务书角度看，`TableExtractor` 这条现在不应再被归类为“文件存在但未证明”。它更准确的状态已经变成：

- **真实样本暂无命中：已证明**
- **独立 extractor + high-confidence source：已用 synthetic 项目级闭环证明**

## 61. 2026-07-06 `phase20_semantic_channel_second`：terminal 语义列已经从隐式 rejection 升级成显式 candidate channel

这轮只推进一个很窄的切片：

- 不先发明新的 relation 表；
- 先把任务书 7.4 里的 terminal 语义旁路落成稳定运行态合同；
- 让 PairBuilder 明确只消费 `terminal_numeric_channel`。

### 61.1 本轮代码变化

- [models.py](/F:/workspace/XJToolkit/src/dwg_audit/domain/models.py)
  - `TerminalCandidate` 新增：
    - `channel`
    - `channel_detail`
- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
  - terminal 页的语义标签不再只体现在 `rejection_reason`：
    - `KLP/DK/ZKK/CLP/UA/UB/UC/UN/3U0/AC230V` 一类文本现在会落到 `semantic_channel`
    - 明显噪声如 `block_internal_pin_number`、`single_char_layer_filtered` 会落到 `noise_channel`
    - `terminal_semantic_local_numeric` 现在会显式把局部小数字改写到 `semantic_channel`
- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - `_accepted_sorted()` 现在显式只消费 `channel == terminal_numeric_channel` 的 accepted candidates
  - `pair.evidence` 现在会带：
    - `selected_left_channel / selected_right_channel`
    - `selected_left_channel_detail / selected_right_channel_detail`
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
  - `page_findings.structure_summary` 新增：
    - `terminal_candidate_channel_counts`
- [rerun.py](/F:/workspace/XJToolkit/src/dwg_audit/report/rerun.py)
  - `run-audit --findings` 现在会把 `terminal_candidates.parquet` 里的 `channel / channel_detail` 读回运行态

### 61.2 定向与全量测试结果

- `python -m pytest -q tests/unit/test_terminal_candidates.py -k "semantic or fjl or single_char"`
  - `7 passed`
- `python -m pytest -q tests/unit/test_pairs_and_rules.py -k "continuation_same_value or terminal_numeric_channel_candidates"`
  - `2 passed`
- `python -m pytest -q tests/unit/test_report_artifacts.py -k "page_findings or terminal_candidate_channels"`
  - `2 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "terminal or page_findings or table_like_page_to_table_extractor or component or supplemental"`
  - `11 passed`
- `python -m pytest -q`
  - `145 passed`

### 61.3 第二套真实样本 rerun 结果

- [phase20_semantic_channel_second/2_2](/F:/workspace/XJToolkit/.tmp/phase20_semantic_channel_second/2_2)
- route 分布保持不变：
  - `WireDiagramExtractor: 13`
  - `ComponentDiagramExtractor: 2`
  - `TerminalDiagramExtractor: 4`
  - `LayoutOnlyExtractor: 2`
  - `SkipExtractor: 3`
- `run-audit` 总 issue 保持：
  - `697`
- 默认仍不落盘 `findings/page_findings/` 目录

新的强证据是：terminal 语义列终于在 findings 运行态里可见了。

以 `S0021 / 21 左侧端子图1.dwg` 为例：

- `structure_summary.terminal_candidate_channel_counts` 现在是：
  - `terminal_numeric_channel: 1689`
  - `semantic_channel: 1055`
  - `noise_channel: 244`

全项目 `terminal_candidates.parquet` 现在也已经有：

- `channel`
- `channel_detail`

当前 second-set 的 `semantic_channel` 主要由这几类构成：

- `terminal_strip_bypass_text: 2808`
- `not_numeric: 776`
- `terminal_semantic_local_numeric: 201`

### 61.4 这轮对任务书主链的真正意义

这轮的价值不是让 issue 数下降，而是把任务书 7.4 的一句关键合同真正落地了：

- **terminal 语义列不再只是“被拒掉的数字”。**
- **它们现在是有显式通道名的运行态对象。**
- **普通 PairBuilder 也第一次被代码层明确约束为只消费 `terminal_numeric_channel`。**

因此，这条现在不应再被描述为“只有 rejection guard，没有显式语义通道”。更准确的状态已经变成：

- **candidate 级 `semantic_channel`：已完成**
- **pair / issue 级 continuation / semantic 解释：仍部分完成**

### 61.5 当前还剩的最近缺口

这轮之后，terminal 方向最接近任务书主链的剩余缺口进一步收敛为：

1. `continuation_same_value` 还只存在于 `pair.evidence`，没有 candidate / pair 顶层 `continuation_channel`
2. semantic-row 虽然已有 `semantic_channel`，但 `missing-side` pair / issue 还不会显式告诉你“哪一侧是被 semantic guard 抑制的”
3. `audit_disposition` 仍未作为独立字段落盘

## 62. 2026-07-06 任务书完成度审计刷新：在 `phase20` 之后，continuation 比 `audit_disposition` 更像语义主链断点

在当前头部代码上重新核对任务书 7.4 与第 9 章之后，最接近主链的两个缺口其实是：

1. continuation 仍只是 `pair.evidence` 里的局部补丁，而不是显式关系类型。
2. `audit_disposition` 仍未作为独立字段落盘。

这两条都是真缺口，但性质不同：

- `audit_disposition` 更像“分类合同收口”；
- continuation 则直接关系到“系统是否还在把续接/桥接关系误当 ordinary pair”。

考虑到任务书第 9 章明确要求：

- 进入规则前至少区分 `ordinary_pair / continuation / bridge_mapping / semantic_mapping`
- `continuation` 默认只进 review 证据，不直接制造 hard conflict

而当前真实样本里第一套恰好已经存在稳定的 continuation 证据，所以这一轮主线程先收口 continuation，而不是先改 `audit_disposition`。

### 62.1 本轮代码变化

- [models.py](/F:/workspace/XJToolkit/src/dwg_audit/domain/models.py)
  - `Pair` 新增：
    - `pair_kind`
- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - 普通 pair 现在默认显式写 `pair_kind = ordinary_pair`
  - `continuation_same_value` 现在不只写 `semantic_kind`，而是显式写：
    - `pair_kind = continuation`
    - `continuation_kind = terminal_same_value_bridge`
  - continuation 关系不再保留 `pass/discard` 外观，而是统一保留为 `review` 证据
- [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py)
  - `_ordinary_pair_eligible()` 现在会直接旁路非 `ordinary_pair`
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
  - `pair_evidence_summary` 新增：
    - `pair_kind_counts`
  - `page_findings.structure_summary` 新增：
    - `pair_kind_counts`
  - findings Markdown 现在也会显示：
    - `PairKindCounts`
- [rerun.py](/F:/workspace/XJToolkit/src/dwg_audit/report/rerun.py)
  - `run-audit --findings` 现在会从 parquet 回放：
    - `pair_kind`

### 62.2 定向与全量测试结果

- `python -m pytest -q tests/unit/test_pairs_and_rules.py -k "continuation or terminal_numeric_channel_candidates"`
  - `3 passed`
- `python -m pytest -q tests/unit/test_report_artifacts.py -k "continuation or pair_kind or page_findings or terminal_candidate_channels"`
  - `4 passed`
- `python -m pytest -q tests/unit/test_terminal_candidates.py -k "semantic or fjl or single_char"`
  - `7 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "terminal or page_findings or component or table_like_page_to_table_extractor or supplemental"`
  - `11 passed`
- `python -m pytest -q`
  - `147 passed`

### 62.3 第一套真实样本 rerun 结果

- [phase21_continuation_contract_first](/F:/workspace/XJToolkit/.tmp/phase21_continuation_contract_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

当前头部真实样本已经能给出下面这些强证据：

- `pair_evidence_summary.pair_kind_counts`
  - `{'continuation': 6, 'ordinary_pair': 1111}`
- `S0027 / 26 右侧端子图1.dwg`
  - `structure_summary.pair_kind_counts = {'ordinary_pair': 156, 'continuation': 6}`
- `pairs.parquet` 中 continuation 关系共有 `6` 条
  - 全部 `pair_kind = continuation`
  - 全部 `status = review`
  - 全部位于 `S0027`
- `issues.json` 中 continuation 相关 issue 数
  - `0`

也就是说，第一套样本里原先那批 `420 -> 420 / 110 -> 110 / 109 -> 109 / 430 -> 430 / 419 -> 419` 已经不再只是“ordinary pair + evidence 备注”，而是当前运行态里显式存在的 continuation 关系。

### 62.4 这轮对任务书主链的真正意义

这轮真正补齐的不是一个字段名，而是任务书第 9 章里这条语义边界：

- **continuation 不能直接等价为 ordinary pair。**

在当前头部代码和真实样本里，这条现在已经前进到了：

- `pair_kind=continuation`：已完成
- continuation 从 ordinary audit 旁路：已完成
- continuation 保留为 review 证据、而不是 hard conflict：已完成

因此，continuation 这条现在不应再被描述为“只有 `ordinary_pair_eligible=False` 的临时旁路”。更准确的状态已经变成：

- **pair 级 continuation 语义：已部分完成，且有真实样本强证据**
- **candidate 级 `continuation_channel`：仍未完成**

### 62.5 这轮之后最接近主链的剩余缺口

在 `phase21` 之后，离任务书主链最近的剩余缺口进一步收敛为：

1. candidate 侧仍没有独立 `continuation_channel`；当前 continuation 仍是“先走 numeric，再在 pair 层改写语义”
2. 单侧 continuation / bridge 记录（例如 `? -> 328`、`110 -> 330`）还没有形成同等明确的 specialized pair-kind
3. semantic-row 虽然已有 candidate `semantic_channel`，但 `missing-side` pair / issue 还不会显式写出“哪一侧被 semantic guard 抑制”
4. `audit_disposition` 仍未作为独立字段落盘

### 62.6 本轮之后仍不该优先的方向

以下方向这时继续投入，都会偏离任务书主链：

1. 继续用总 issue 数升降评估 continuation 切片成败
2. 回到桌面端 / Tauri / preview 交互细节
3. 在没有显式 relation contract 的前提下，继续只在 `candidates.py` 里堆更多全局阈值

## 63. 2026-07-06 `phase22_audit_disposition_second`：`audit_disposition` 已进入分类、准入和 findings 合同

这一轮只收口一条最近的分类合同缺口：

- 任务书第 4/5 层要求页级分类结果除了 `page_type` 之外，还要显式提供 `audit_disposition`
- 当前代码此前只有 `audit_role + route_target`
- pipeline 也还是靠 `is_primary_audit_candidate` 决定哪些页进入下游审计

### 63.1 本轮代码变化

- [models.py](/F:/workspace/XJToolkit/src/dwg_audit/domain/models.py)
  - `SheetRecord` 新增：
    - `audit_disposition`
  - `PageClassification` 新增：
    - `audit_disposition`
- [page_classifier.py](/F:/workspace/XJToolkit/src/dwg_audit/page_classifier.py)
  - 分类结果现在会同时给出：
    - `audit_required`
    - `classify_only`
    - `skip_stable`
  - 最小判定保持保守：
    - `SkipExtractor` -> `skip_stable`
    - `supplemental` 或真实审计型 route -> `audit_required`
    - 其余 layout-only 页 -> `classify_only`
- [page_router.py](/F:/workspace/XJToolkit/src/dwg_audit/page_router.py)
  - `enrich_pages_from_classifications()` 现在会把 `audit_disposition` 回填到 `SheetRecord`
  - `is_primary_audit_candidate` 现在跟随 `audit_disposition == audit_required` 同步
- [pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py)
  - `_is_downstream_audit_page()` 现在优先按 `audit_disposition` 决定下游纳入，而不是继续只看 scan 阶段旧字段
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
  - `findings.json` / `page_findings` 现在显式落：
    - `audit_disposition`
    - `audit_disposition_counts`
  - findings markdown 与 page findings markdown 也会显示这一字段
- [rerun.py](/F:/workspace/XJToolkit/src/dwg_audit/report/rerun.py)
  - `run-audit --findings` 回放 `pages.parquet` 时会把 `audit_disposition` 读回运行态

### 63.2 定向与全量测试结果

- `python -m pytest -q tests/unit/test_page_classifier.py tests/unit/test_report_artifacts.py tests/integration/test_analyze_project.py -k "audit_disposition or classify_pages or write_project_artifacts or includes_supplemental_pages_in_downstream_audit or routes_table_like_page_to_table_extractor or can_include_backplate_pages_as_supplemental_audit"`
  - `19 passed`
- `python -m pytest -q`
  - `148 passed`

### 63.3 第二套真实样本 rerun 结果

- [phase22_audit_disposition_second/2_2](/F:/workspace/XJToolkit/.tmp/phase22_audit_disposition_second/2_2)
- `pages.parquet` / `findings.json` 现在显式给出：
  - `audit_disposition_counts = {'audit_required': 19, 'classify_only': 2, 'skip_stable': 3}`
  - `included_audit_pages = 19`
- `route_target` 分布保持不变：
  - `WireDiagramExtractor: 13`
  - `ComponentDiagramExtractor: 2`
  - `TerminalDiagramExtractor: 4`
  - `LayoutOnlyExtractor: 2`
  - `SkipExtractor: 3`
- 关键页当前表现：
  - `17 测控1装置背板.dwg` -> `LayoutOnlyExtractor + classify_only`
  - `19 元件接线图1.dwg` -> `ComponentDiagramExtractor + audit_required`
  - `21 左侧端子图1.dwg` -> `TerminalDiagramExtractor + audit_required`
  - `01 封面.dwg` -> `SkipExtractor + skip_stable`
- `run-audit` 总 issue 保持：
  - `697`

### 63.4 这轮对任务书主链的真正意义

这轮补的不是单纯字段名，而是把“页级分类结果决定后续准入”这件事变成了显式合同：

- **`audit_disposition`：已完成并落盘**
- **pipeline 用 classifier-produced disposition 接管下游准入：已完成**
- **findings / page findings / pages.parquet 中可见 disposition：已完成**

所以，这条现在不应再被描述为“只有 `audit_role + route_target` 的近似实现”。更准确的状态已经变成：

- **分类级 `audit_disposition` 合同：已完成**
- **剩余最近缺口重新收敛到 continuation / bridge / semantic 关系解释，而不再是页级准入字段缺失**

## 64. 2026-07-06 `phase23_single_sided_continuation_{second,first}`：端子页单侧 half-pair 已从普通 `missing-side` 升级成显式 continuation

这一轮只推进一个很窄的关系语义切片：

- 不先重构 candidate 四通道；
- 不直接发明 `bridge_mapping`；
- 先把任务书第 9 章里最典型的 `? -> 328`、`10 -> ?` 这类端子页单侧 half-pair，从普通 `R-PAIR-MISSING-SIDE` 分流出去。

### 64.1 本轮代码变化

- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - continuation 语义从“同值双侧特例”扩成两段：
    - `continuation_same_value`
    - `continuation_single_sided`
  - 对 `屏端子图 + horizontal + 70-80` 的短线，若只命中单侧：
    - 命中 `n###` 派生 numeric 时，显式落 `pair_kind=continuation`
    - 位于右侧短桥接列带（`x>=300`）的单列数字，也显式落 `pair_kind=continuation`
  - evidence 新增：
    - `continuation_missing_side`
    - `continuation_kind=terminal_missing_left/right_continuation`
- [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py)
  - `R-PAIR-MISSING-SIDE` 现在会跳过 `pair_kind=continuation`
- [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py)
  - 新增单侧 derived continuation 和短桥单列 continuation 断言
  - 新增规则层“不再出普通 missing-side issue”断言
- [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py)
  - 现有 `? -> 328`、`? -> 108`、`511 -> ?`、`? -> 10` 样例已改成断言 `pair_kind=continuation`

### 64.2 定向与全量测试结果

- `python -m pytest -q tests/unit/test_pairs_and_rules.py -k "continuation or terminal_numeric_channel_candidates"`
  - `6 passed`
- `python -m pytest -q tests/unit/test_terminal_candidates.py -k "short_bridge or semantic_row or semantic_ac_row"`
  - `4 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "terminal or page_findings or component or supplemental or table_like_page_to_table_extractor"`
  - `11 passed`
- `python -m pytest -q tests/unit/test_report_artifacts.py -k "pair_kind or page_findings or terminal_candidate_channels"`
  - `3 passed`
- `python -m pytest -q`
  - `151 passed`

### 64.3 第二套真实样本 rerun 结果

- [phase23_single_sided_continuation_second/2_2](/F:/workspace/XJToolkit/.tmp/phase23_single_sided_continuation_second/2_2)

当前头部第二套样本的最关键变化：

- `pair_kind_counts`
  - 旧：`{'ordinary_pair': 1211}`
  - 新：`{'ordinary_pair': 1034, 'continuation': 177}`
- `issue_count`
  - `697 -> 520`
- `R-PAIR-MISSING-SIDE`
  - `494 -> 317`
- `R-PAIR-LOW-CONFIDENCE`
  - 保持 `203`
- 四张端子页里的 ordinary 单侧缺边 pair
  - `245 -> 68`

新增 continuation 只出现在第二套的端子页：

- `S0021 / 21 左侧端子图1.dwg`
- `S0022 / 22 左侧端子图2.dwg`
- `S0023 / 23 右侧端子图1.dwg`
- `S0024 / 24 右侧端子图2.dwg`

代表性新语义现在已经是：

- `? -> 708`
- `? -> 328`
- `? -> 108`
- `? -> 10`

它们不再继续伪装成 ordinary `missing-side` pair。

### 64.4 第一套真实样本 rerun 结果

- [phase23_single_sided_continuation_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA](/F:/workspace/XJToolkit/.tmp/phase23_single_sided_continuation_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

当前头部第一套样本的最关键变化：

- `pair_kind_counts`
  - 旧：`{'ordinary_pair': 1111, 'continuation': 6}`
  - 新：`{'ordinary_pair': 946, 'continuation': 171}`
- `issue_count`
  - `512 -> 347`
- `R-PAIR-MISSING-SIDE`
  - `432 -> 267`
- `R-PAIR-LOW-CONFIDENCE`
  - 保持 `79`

新增 continuation 同样只出现在端子页：

- `S0025 / 24 左侧端子图1.dwg`
- `S0027 / 26 右侧端子图1.dwg`
- `S0028 / 27 右侧端子图2.dwg`

说明这轮没有把普通回路图或网格页的 half-pair 一起误收成 continuation。

### 64.5 这轮对任务书主链的真正意义

任务书第 9 章最关键的一句是：

- `continuation` 不能直接等价为普通 pair，像 `? -> 328`、`110 -> 330`、`10 -> ?` 这类更可能是续接或桥接记录。

这轮真正补齐的是其中最小、但最常见的一半：

- **单侧 terminal continuation：已完成到 pair 级显式语义**
- **普通 `R-PAIR-MISSING-SIDE` 已不再吞掉这类端子页记录**
- **continuation 仍保持 review 证据，不制造 ordinary hard conflict**

因此，这条现在不应再被描述为“只有 same-value continuation 特例”。更准确的状态已经变成：

- **same-value continuation：已完成**
- **single-sided continuation：已完成**
- **bridge_mapping：仍未完成**
- **candidate 级 `continuation_channel`：仍未完成**

### 64.6 这轮之后最近的剩余缺口

在 `phase23` 之后，最接近任务书主链的剩余缺口进一步收敛为：

1. candidate 侧仍没有独立 `continuation_channel`
2. `110 -> 330` 这类短桥接列关系仍是 ordinary pair，还没有显式 `bridge_mapping`
3. `semantic_channel` 虽已完成候选旁路，但 pair / issue / report 仍缺 `semantic_mapping` 或 `suppressed_candidate_refs` 级证据

## 65. 2026-07-06 current-head 任务书审计刷新：`bridge_mapping` 已经比 `semantic_mapping` 更接近下一刀

在 `phase23` 之后，我又直接按当前头状态复核了任务书 7.4、7.5 和第 9 章，不再依据历史叙事，只依据当前代码、当前测试和最新真实样本产物：

- 第二套：
  - [phase23_single_sided_continuation_second/2_2](/F:/workspace/XJToolkit/.tmp/phase23_single_sided_continuation_second/2_2)
- 第一套：
  - [phase23_single_sided_continuation_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA](/F:/workspace/XJToolkit/.tmp/phase23_single_sided_continuation_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

### 65.1 当前强证据已经证明了什么

- 页级分类 / 路由 / table extractor 的主链闭环，仍以前几轮 current-head rerun 结论为准，没有被 `phase23` 推翻。
- terminal 语义列 candidate split 仍是已完成状态：
  - `candidates.py` 已显式给出 `terminal_numeric_channel / semantic_channel / noise_channel`
  - PairBuilder 仍只消费 `terminal_numeric_channel`
- continuation 语义现在已经不只覆盖 same-value case，也覆盖单侧 half-pair：
  - `? -> 328`
  - `? -> 108`
  - `10 -> ?`
  这些在 `phase23` 的真实样本里都已经变成 `pair_kind=continuation`，并退出 ordinary `R-PAIR-MISSING-SIDE`。

### 65.2 仍未完成、且离任务书主链最近的缺口是什么

当前离任务书第 9 章最近的剩余缺口，已经不再是 single-sided continuation，而是：

- **短桥接列里的双侧 cross-column relation 仍然停留在 ordinary pair，没有显式 `bridge_mapping`。**

当前第二套真实样本里最典型的 remaining case 是：

- `110 -> 330`
- `109 -> 329`

它们都位于 `S0021 / 21 左侧端子图1.dwg` 的右侧短桥接带中，当前仍表现为：

- `pair_kind=ordinary_pair`
- `status=review`
- `rationale=left=110 right=330 score=0.895`

而同一带里的单侧记录，例如：

- `? -> 328`

已经被 `phase23` 正确抬成 continuation。

这说明当前系统已经能识别“单侧待续接”，但还没有把“局部跨列桥接映射”从 ordinary pair 中拆出来。

### 65.3 为什么这更像 `bridge_mapping`，而不是继续扩大 `continuation`

我直接核对了 `phase23` 真实样本里的三类端子页关系：

1. `21 -> 211`
   - 左侧是 plain numeric
   - 右侧是 `3-21n211`
   - 这仍更像普通端子行映射，可以继续保留在 ordinary pair
2. `? -> 328`
   - 单侧已知
   - 另一侧被短桥列角色过滤掉
   - 这符合任务书里 continuation 的“单侧待续接”定义
3. `110 -> 330`
   - 左右两侧都来自 `n###` 派生文本
   - 同行中还夹着一列被 `terminal_short_bridge_role_filtered` 拒收的局部数字（例如 `81`）
   - 这更像“短桥接列 / 局部跨列映射”，而不是普通端子对端子配对

也就是说：

- **continuation** 解决的是“只有一侧被保留”的关系
- **bridge_mapping** 更适合解决“同一短桥接带内，两个派生列之间的局部 cross-column mapping”

任务书第 9 章给的例子本身也支持这点：

- `? -> 328`
- `110 -> 330`
- `10 -> ?`

其中前后两类更像 continuation，而中间这类更像 bridge_mapping。

### 65.4 为什么 `semantic_mapping` 现在还不是下一刀

`semantic_channel` 当前已经完成到：

- 候选被旁路
- ordinary pair 不再消费它
- findings 运行态能看到 channel counts

但它还没有进入：

- `semantic_mapping` relation object
- semantic-specific rule input
- semantic report ledger

这当然仍是未完成项，但相比之下，它离当前已有骨架更远。

而 `bridge_mapping` 现在只差：

- 在 pair 层把一类已稳定识别出的端子页关系，从 `ordinary_pair` 改写成 `bridge_mapping`
- 让它借用现有 `pair_kind != ordinary_pair` 的规则旁路能力

所以从“最短闭环路径”看，下一刀应优先选 `bridge_mapping`，而不是先回头做 semantic relation ledger。

### 65.5 当前最接近主链的单一核心切片

基于以上 current-head 审计，下一刀最合理的单一核心切片应定义为：

- **只把端子页右侧短桥接带里“左右两侧都来自 `n###` 派生文本、且两侧值不同”的关系，提升成显式 `pair_kind=bridge_mapping`。**

这条切片故意不做以下扩张：

- 不先引入 candidate 级 `continuation_channel`
- 不先做泛化 `semantic_mapping`
- 不把普通端子行映射如 `21 -> 211` 一起改写
- 不把所有双侧 derived pair 都粗暴升级成 bridge

### 65.6 本轮之后仍不该优先的方向

当前仍不该优先的方向包括：

1. 再回桌面端 / Tauri / preview
2. 继续只盯 issue 总数升降
3. 在 `candidates.py` 里继续堆更宽的全局阈值，而不显式回答“这是什么关系类型”
4. 在还没建立 `bridge_mapping` 前，就把 `semantic_mapping` 和 `continuation_channel` 一起做成大改

## 66. 2026-07-06 `phase24_bridge_mapping_{second,first}`：短桥接带里的 cross-column relation 已从 ordinary pair 升成显式 bridge_mapping

这一轮只推进了一个比 `phase23` 更窄的关系语义切片：

- 不扩大 continuation 的作用域
- 不先做 `semantic_mapping`
- 只处理端子页短桥接带里“双侧都来自 `n###` 派生文本、且数值不同”的 cross-column relation

### 66.1 本轮代码变化

- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - 在现有 terminal relation 语义分流里新增：
    - `pair_kind=bridge_mapping`
    - `semantic_kind=terminal_bridge_mapping`
    - `bridge_mapping_kind=terminal_short_bridge_cross_column`
  - 触发条件刻意保持很窄：
    - `屏端子图`
    - `horizontal`
    - 线长 `70-80`
    - 位于右侧短桥接带（`x>=300`）
    - 左右两侧都来自派生 numeric
    - 左右原文都匹配 `n###`
    - 左右值不同
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
  - pair 语义摘要现在会显式输出：
    - `bridge_mapping_kind`
- [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py)
  - 新增 `110 -> 330` 风格的 bridge_mapping 单测
  - 新增规则层“bridge_mapping 不再参与 ordinary audit”单测
- [test_report_artifacts.py](/F:/workspace/XJToolkit/tests/unit/test_report_artifacts.py)
  - 新增 bridge_mapping 语义在 audit markdown 中可见的断言

### 66.2 定向与全量测试结果

- `python -m pytest -q tests/unit/test_pairs_and_rules.py -k "bridge_mapping or continuation or terminal_numeric_channel_candidates"`
  - `8 passed`
- `python -m pytest -q tests/unit/test_terminal_candidates.py -k "short_bridge or semantic_row or semantic_ac_row"`
  - `4 passed`
- `python -m pytest -q tests/unit/test_report_artifacts.py -k "bridge_mapping or continuation or pair_kind or terminal_candidate_channels"`
  - `4 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "terminal or page_findings or component or supplemental or table_like_page_to_table_extractor"`
  - `11 passed`
- `python -m pytest -q`
  - `154 passed`

### 66.3 第二套真实样本 rerun 结果

- [phase24_bridge_mapping_second/2_2](/F:/workspace/XJToolkit/.tmp/phase24_bridge_mapping_second/2_2)

相对 `phase23`，第二套 current-head 新证据如下：

- `pair_kind_counts`
  - 旧：`{'ordinary_pair': 1034, 'continuation': 177}`
  - 新：`{'ordinary_pair': 1031, 'continuation': 177, 'bridge_mapping': 3}`
- `issue_count`
  - `520 -> 518`
- `R-PAIR-LOW-CONFIDENCE`
  - `203 -> 201`
- `R-PAIR-MISSING-SIDE`
  - 保持 `317`

更重要的是语义边界：

- `110 -> 330`
- `109 -> 329`

现在都已经变成：

- `pair_kind=bridge_mapping`
- `bridge_mapping_kind=terminal_short_bridge_cross_column`

而以下关系保持不变：

- `21 -> 211`
  - 仍是 `ordinary_pair`
- `10 -> 131`
  - 仍是 `ordinary_pair`
- `? -> 328`
  - 仍是 `continuation`

这说明这轮没有把普通端子行映射或单侧 continuation 混成同一类。

### 66.4 第一套真实样本 rerun 结果

- [phase24_bridge_mapping_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA](/F:/workspace/XJToolkit/.tmp/phase24_bridge_mapping_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

相对 `phase23`，第一套 current-head 新证据如下：

- `pair_kind_counts`
  - 旧：`{'ordinary_pair': 946, 'continuation': 171}`
  - 新：`{'ordinary_pair': 943, 'continuation': 171, 'bridge_mapping': 3}`
- `issue_count`
  - `347 -> 345`
- `R-PAIR-LOW-CONFIDENCE`
  - `79 -> 77`

新增 bridge_mapping 只出现在：

- `S0027 / 26 右侧端子图1.dwg`

代表样例为：

- `429 -> 108`

同样表现为：

- 左右两侧都来自派生 numeric
- 中间夹着被 `terminal_short_bridge_role_filtered` 的局部数字列

因此它也更像 bridge 带内的局部 cross-column relation，而不是普通端子对端子配对。

### 66.5 这轮对任务书主链的真正意义

任务书第 9 章要求在进入规则引擎前，至少先分清：

- `ordinary_pair`
- `continuation`
- `bridge_mapping`
- `semantic_mapping`

经过 `phase23 + phase24`，当前头状态已经从“只有 ordinary + continuation”往前推进到：

- `ordinary_pair`：已完成
- `continuation`：已完成到 same-value + single-sided
- `bridge_mapping`：已完成到最小 pair 级短桥接带合同
- `semantic_mapping`：仍未完成

这意味着当前系统已经不再把任务书里最典型的三类端子页关系硬塞进同一种 ordinary pair 壳：

- `? -> 328` -> continuation
- `110 -> 330` -> bridge_mapping
- `21 -> 211` -> ordinary_pair

### 66.6 这轮之后最近的剩余缺口

在 `phase24` 之后，离任务书主链最近的剩余缺口进一步收敛为：

1. candidate 侧仍没有独立 `continuation_channel`
2. `bridge_mapping` 目前只有最小 pair 级合同，还没有更系统的页内 bridge ledger
3. `semantic_channel` 仍未形成真正的 `semantic_mapping` relation / report / rule input

如果继续按“最短闭环路径”推进，下一刀更可能在：

- `semantic_mapping`
- 或更细的 bridge ledger

之间做新的 current-head 审计裁决，而不是再回桌面端或继续堆全局阈值。

## 67. 2026-07-06 current-head 任务书审计刷新：`semantic_mapping` 已经出现了可窄切的真实样本入口

在 `phase24` 之后，我继续按当前头状态复核了任务书 7.4 / 7.5 / 9，不再用历史叙事，而是直接检查：

- [phase24_bridge_mapping_second/2_2](/F:/workspace/XJToolkit/.tmp/phase24_bridge_mapping_second/2_2)
- [phase24_bridge_mapping_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA](/F:/workspace/XJToolkit/.tmp/phase24_bridge_mapping_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 当前代码：
  - [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
  - [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)

### 67.1 当前已经被强证据证明完成的 terminal 关系分流

到 `phase24` 为止，当前 terminal 方向已经有三类显式关系：

- `ordinary_pair`
  - 如 `21 -> 211`
- `continuation`
  - 如 `? -> 328`
  - 如 `10 -> ?`
- `bridge_mapping`
  - 如 `110 -> 330`
  - 如 `109 -> 329`

这三类在 current-head 真实样本里已经有稳定证据，不再只是测试夹具。

### 67.2 为什么 `semantic_mapping` 现在比“继续扩 bridge ledger”更接近下一刀

我又直接核查了 terminal 页里包含真实语义 marker 的 line group：

- `KLP`
- `DK`
- `CLP`
- `UA/UB/UC/UN/3U0`
- `AC230V`
- `Shielding layer`

当前代码已经能把这些文本旁路到 `semantic_channel`，但 pair 层还没有显式 relation object。

更关键的是，真实样本里已经出现了大批“**同一 line group 既有语义 marker，又有当前被记作 continuation 的单侧 numeric relation**”：

- 第二套 terminal 页里，这类 marker group 上的 pair 统计当前是：
  - `continuation: 99`
  - `ordinary_pair: 32`
- 第一套 terminal 页里，这类 marker group 上的 pair 统计当前是：
  - `continuation: 88`
  - `ordinary_pair: 65`

其中代表性 current-head 真实样例如：

- 第二套 `S0021 / G0890`
  - 语义文本：
    - `3-21KLP1-1`
    - `3-21KLP2-1`
  - 当前 pair：
    - `? -> 108`
    - 仍被记作 `continuation`
- 第一套 `S0025`
  - 语义文本：
    - `5DK-4`
    - `5KLP9-1`
    - `5CLP3-1`
  - 当前大量 pair：
    - `? -> 411`
    - `? -> 103`
    - `? -> 214`
    - 仍被记作 `continuation`

这说明当前系统已经有了：

1. 语义 marker 候选旁路
2. 同行 numeric terminal 候选
3. 行锁定 / 列角色稳定结构

但还没有把“terminal 到语义端/代号列/标签列”的关系显式抬成 `semantic_mapping`。

### 67.3 为什么这些关系不该继续留在 `continuation`

`continuation` 更适合表示：

- 单侧已知，另一侧待续接或待去向

但像 `KLP/DK/CLP/UA/AC230V` 这类语义行，当前很多 `? -> 108` 并不是“另一端未知的 terminal continuation”，而更像：

- terminal `108`
- 对应语义端 `KLP2`

也就是任务书第 9 章定义的：

- `semantic_mapping`：端子到语义端、代号列或标签列的映射

如果继续把它们留在 continuation 下，系统虽然避免了 ordinary 冲突，但仍然没有真正把“这是语义映射”说出来。

### 67.4 当前最接近主链的单一核心切片

基于 current-head 审计，下一刀最合理的单一核心切片已经收敛为：

- **只把 terminal 页中“单侧 numeric relation + 同 line group 存在真实语义 marker”的 relation，从 continuation 提升成显式 `semantic_mapping`。**

这条切片必须保持窄边界：

- 只处理 `屏端子图`
- 只处理 horizontal terminal row
- 只处理当前已经是 single-sided relation 的 case
- 只在 group 内存在真实语义 marker 文本时触发
- 不把 `terminal_strip_bypass_text` 或纯 `not_numeric` 杂项一并视为 semantic mapping
- 不改 ordinary pair
- 不改 bridge_mapping

### 67.5 为什么这轮不该先做更大的东西

当前仍不该优先的方向：

1. 继续扩大 `bridge_mapping` 作用域
2. 先做 candidate 级 `continuation_channel`
3. 只补 `suppressed_candidate_refs` 解释层，而不建立真正的 `semantic_mapping`
4. 再回桌面端 / preview / Tauri

## 68. 2026-07-06 `phase25_semantic_mapping_{second,first}`：terminal 页语义行已从 continuation 中拆出最小 `semantic_mapping`

这一轮只推进了一个 current-head 已经具备真实样本入口的关系切片：

- 不改 ordinary pair
- 不扩大 bridge_mapping
- 不先做 candidate 级 `continuation_channel`
- 只把 terminal 页中“单侧 numeric relation + 同组存在真实语义 marker”的 relation，从 continuation 提升成显式 `semantic_mapping`

### 68.1 本轮代码变化

- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - 在当前 terminal relation 语义分流里新增：
    - `pair_kind=semantic_mapping`
    - `semantic_kind=terminal_semantic_mapping`
    - `semantic_mapping_kind=terminal_semantic_row`
    - `semantic_mapping_missing_side`
    - `semantic_marker_texts`
  - 触发条件刻意保持窄边界：
    - `屏端子图`
    - `horizontal`
    - 线长 `70-80`
    - 当前是 single-sided relation
    - 选中的 numeric 仍来自 `n###` 派生文本
    - 同 line group 内存在真实语义 marker 文本
- [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py)
  - `R-PAIR-MISSING-SIDE` 和 complementary half-pair 聚合现在统一只处理 ordinary pair
  - continuation / bridge_mapping / semantic_mapping 都不再被 ordinary missing-side 规则重新吞回去
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
  - pair 语义摘要现在会显式输出：
    - `semantic_mapping_kind`
    - `semantic_markers`

### 68.2 定向与全量测试结果

- `python -m pytest -q tests/unit/test_pairs_and_rules.py -k "semantic_mapping or bridge_mapping or continuation or terminal_numeric_channel_candidates"`
  - `10 passed`
- `python -m pytest -q tests/unit/test_terminal_candidates.py -k "semantic_row or semantic_ac_row or short_bridge"`
  - `4 passed`
- `python -m pytest -q tests/unit/test_report_artifacts.py -k "semantic_mapping or bridge_mapping or continuation or pair_kind"`
  - `4 passed`
- `python -m pytest -q tests/integration/test_analyze_project.py -k "terminal or page_findings or component or supplemental or table_like_page_to_table_extractor"`
  - `11 passed`
- `python -m pytest -q`
  - `157 passed`

### 68.3 第二套真实样本 rerun 结果

- [phase25_semantic_mapping_second/2_2](/F:/workspace/XJToolkit/.tmp/phase25_semantic_mapping_second/2_2)

相对 `phase24`，第二套 current-head 现在变成：

- `pair_kind_counts`
  - 旧：`{'ordinary_pair': 1031, 'continuation': 177, 'bridge_mapping': 3}`
  - 新：`{'ordinary_pair': 1031, 'semantic_mapping': 157, 'continuation': 20, 'bridge_mapping': 3}`
- `issue_count`
  - 保持 `518`
- `R-PAIR-MISSING-SIDE`
  - 保持 `317`
- `R-PAIR-LOW-CONFIDENCE`
  - 保持 `201`

最关键的 current-head 边界现在已经清晰：

- `21 -> 211`
  - 仍是 `ordinary_pair`
- `110 -> 330`
  - 仍是 `bridge_mapping`
- `? -> 328`
  - 仍是 `continuation`
- `? -> 108`
  - 已是 `semantic_mapping`

第二套 current-head 的代表语义行例如：

- `KLP`
- `I0'`
- `AC230V`

这些现在不再只是 candidate channel 的旁路对象，而已经进入 pair 级 relation。

### 68.4 第一套真实样本 rerun 结果

- [phase25_semantic_mapping_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA](/F:/workspace/XJToolkit/.tmp/phase25_semantic_mapping_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

相对 `phase24`，第一套 current-head 现在变成：

- `pair_kind_counts`
  - 旧：`{'ordinary_pair': 943, 'continuation': 171, 'bridge_mapping': 3}`
  - 新：`{'ordinary_pair': 943, 'semantic_mapping': 103, 'continuation': 68, 'bridge_mapping': 3}`
- `issue_count`
  - 保持 `345`
- `R-PAIR-MISSING-SIDE`
  - 保持 `267`
- `R-PAIR-LOW-CONFIDENCE`
  - 保持 `77`

第一套当前被抬成 semantic_mapping 的代表语义行来自：

- `KLP`
- `DK`
- `CLP`

也就是说，这轮没有继续扩大到普通回路图，而是只在 terminal 页语义行里生效。

### 68.5 这轮对任务书主链的真正意义

任务书 7.4 与第 9 章要求：

- `semantic_channel` 不能只是“被旁路后消失”
- `semantic_mapping` 应表示“端子到语义端、代号列或标签列的对应关系”

经过 `phase25` 之后，当前头状态已经从：

- candidate 级 `semantic_channel`

推进到：

- pair 级 `semantic_mapping`

所以 terminal 方向当前已经形成四类显式页面内关系：

- `ordinary_pair`
- `continuation`
- `bridge_mapping`
- `semantic_mapping`

这意味着当前系统已经不再把 terminal 页所有关系都塞进同一个几何 pair 壳里。

### 68.6 这轮之后最近的剩余缺口

在 `phase25` 之后，离任务书主链最近的剩余缺口进一步收敛为：

1. candidate 侧仍没有独立 `continuation_channel`
2. `bridge_mapping` 与 `semantic_mapping` 目前都只是最小 pair 级合同，还没有更系统的 relation ledger / index
3. `semantic_mapping` 虽已进入 pair 级 relation，但还没有 semantic-specific 项目级一致性规则

如果继续按“最短闭环路径”推进，下一刀更可能是：

- semantic-specific index / rule input
- 或 candidate 级 `continuation_channel`

而不再是继续争论 terminal 页是否还只有 ordinary pair。

## 69. 2026-07-06 current-head 任务书审计刷新：`continuation_channel` 现在是最接近 7.4 合同的剩余缺口

在 `phase25` 之后，我再次只依据 current-head 代码、测试和真实样本产物复核了任务书 7.4 与第 9 章，结论是：

- pair 级四类关系现在都已经有最小合同：
  - `ordinary_pair`
  - `continuation`
  - `bridge_mapping`
  - `semantic_mapping`
- 但 candidate 级四通道仍然没有真正闭环。

### 69.1 当前已经完成到哪一步

当前 candidate 层仍只有三种显式 channel：

- `terminal_numeric_channel`
- `semantic_channel`
- `noise_channel`

这在代码里仍是当前事实，见 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py:18) 到 [20](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py:20)。

当前并没有：

- `continuation_channel`

与此同时，`pairs.py` 已经能够在 pair 层稳定识别：

- continuation
- bridge_mapping
- semantic_mapping

而 PairBuilder 仍只直接消费 `terminal_numeric_channel`，见 [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py:228)。

### 69.2 为什么这现在比 semantic-specific rule 更近

`semantic_mapping` 虽然还没有 semantic-specific 项目级一致性规则，但至少已经进入了 pair 级 relation。

而 `continuation_channel` 仍处于更早一层的合同缺口：

- 当前很多最终被识别成 continuation / bridge_mapping 的 selected numeric candidate，
  在 artifacts 里仍然看起来像普通 `terminal_numeric_channel`
- 这会让 findings 运行态在 candidate 维度上，仍然无法回答：
  - 哪些 numeric 实际属于普通 terminal pair 候选
  - 哪些 numeric 更像 continuation / bridge 提示

也就是说，当前系统虽然已经能在 pair 终点“纠正语义”，但在 candidate 起点还没有把四通道合同补齐。

### 69.3 current-head 真实样本支持这条切片足够窄

在 `phase25` 的真实样本里，当前非 ordinary 的 terminal pair 数量已经很收敛：

- 第二套：
  - `continuation: 20`
  - `bridge_mapping: 3`
  - 对应 selected candidate id 大约 `26` 个
- 第一套：
  - `continuation: 68`
  - `bridge_mapping: 3`
  - 对应 selected candidate id 大约 `80` 个

这说明：

- 如果下一刀只把“已经在 pair 层被识别成 continuation / bridge_mapping 的 selected numeric candidate”回标成 `continuation_channel`
- 这会是一个相对窄、相对低风险的 current-head 切片

它不会要求先重做：

- candidate 搜索窗口
- ordinary pair 排序
- semantic mapping 规则

### 69.4 当前最接近主链的单一核心切片

基于 current-head 审计，下一刀最合理的单一核心切片应定义为：

- **只把已在 pair 层识别成 `continuation` 或 `bridge_mapping` 的 selected numeric candidate，回标成显式 `continuation_channel`。**

这条切片故意不做以下扩张：

- 不把 `semantic_mapping` 的 numeric candidate 改成 continuation channel
- 不重做 candidate 排序算法
- 不改变 ordinary pair 的 candidate channel
- 不引入新的项目级 semantic / bridge 规则

### 69.5 为什么这轮不该优先做别的

当前仍不该优先的方向：

1. 继续扩大 semantic-specific 项目级规则
2. 再回桌面端 / preview / Tauri
3. 继续只在 `pairs.py` 里堆更多语义，而不把 candidate 四通道合同补齐

## 70. 2026-07-06 `phase26_continuation_channel_{second,first}`：candidate 级 `continuation_channel` 已完成最小闭环

这一轮只推进了 `phase25` 之后最近、也最窄的一条合同缺口：

- 不改 candidate 搜索窗口
- 不重排 ordinary pair
- 不扩大 semantic mapping
- **只把已在 pair 层识别成 `continuation` 或 `bridge_mapping` 的 selected numeric candidate，回标成显式 `continuation_channel`**

### 70.1 本轮代码变化

- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
  - 新增 `_CHANNEL_CONTINUATION = "continuation_channel"`
- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)
  - `_accepted_sorted()` 仍只消费 `terminal_numeric_channel`
  - 在 pair 语义已确定后，若当前 relation 属于：
    - `continuation`
    - `bridge_mapping`
  - 则对应 selected candidate 会被回标为：
    - `channel = continuation_channel`
    - `channel_detail = continuation_kind / bridge_mapping_kind`
  - `semantic_mapping` 刻意不跟着改写，selected numeric candidate 继续保留在 `terminal_numeric_channel`
- [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py)
  - 新增断言，确保：
    - continuation / bridge 的 selected channel 已变成 `continuation_channel`
    - semantic mapping 仍保持 `terminal_numeric_channel`
- [test_report_artifacts.py](/F:/workspace/XJToolkit/tests/unit/test_report_artifacts.py)
  - 新增 findings 汇总对 `continuation_channel` 的页级统计断言

### 70.2 定向与全量测试结果

- `python -m pytest -q tests/unit/test_pairs_and_rules.py -k "continuation or bridge_mapping or semantic_mapping or terminal_numeric_channel_candidates"`
  - `10 passed`
- `python -m pytest -q tests/unit/test_report_artifacts.py -k "continuation_candidate_channel_counts or terminal_candidate_channels or continuation or bridge_mapping or semantic_mapping"`
  - `6 passed`
- `python -m pytest -q`
  - `158 passed`

### 70.3 第二套真实样本 rerun 结果

- [phase26_continuation_channel_second/2_2](/F:/workspace/XJToolkit/.tmp/phase26_continuation_channel_second/2_2)

相对 `phase25`，第二套 current-head 的 pair / issue 结果保持不变：

- `pair_kind_counts`
  - `{'ordinary_pair': 1031, 'semantic_mapping': 157, 'continuation': 20, 'bridge_mapping': 3}`
- `issue_count`
  - 保持 `518`
- `R-PAIR-LOW-CONFIDENCE`
  - 保持 `201`
- `R-PAIR-MISSING-SIDE`
  - 保持 `317`

真正新增的是 candidate 层运行态证据：

- 全项目 `terminal_candidates.parquet` 现在有：
  - `continuation_channel = 26`
- `channel_detail` 分布为：
  - `terminal_missing_left_continuation = 20`
  - `terminal_short_bridge_cross_column = 6`
- 页级 findings 中：
  - `S0021` 出现 `continuation_channel = 14`
  - `S0024` 出现 `continuation_channel = 12`

这说明第二套里当前被判成：

- `? -> 328` 风格 continuation
- `110 -> 330` 风格 bridge mapping

其 selected numeric candidate 现在已经不会再伪装成普通 `terminal_numeric_channel`。

### 70.4 第一套真实样本 rerun 结果

- [phase26_continuation_channel_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA](/F:/workspace/XJToolkit/.tmp/phase26_continuation_channel_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

相对 `phase25`，第一套 current-head 的 pair / issue 结果同样保持不变：

- `pair_kind_counts`
  - `{'ordinary_pair': 943, 'semantic_mapping': 103, 'continuation': 68, 'bridge_mapping': 3}`
- `issue_count`
  - 保持 `345`
- `R-PAIR-LOW-CONFIDENCE`
  - 保持 `77`
- `R-PAIR-MISSING-SIDE`
  - 保持 `267`

candidate 层新增证据则更丰富：

- 全项目 `terminal_candidates.parquet` 现在有：
  - `continuation_channel = 80`
- `channel_detail` 分布为：
  - `terminal_missing_left_continuation = 34`
  - `terminal_missing_right_continuation = 28`
  - `terminal_same_value_bridge = 12`
  - `terminal_short_bridge_cross_column = 6`
- 页级 findings 中：
  - `S0025` 出现 `continuation_channel = 38`
  - `S0027` 出现 `continuation_channel = 42`

这也对应了第一套 current-head 已经存在的三种非 ordinary terminal 关系：

- `? -> X`
- `X -> ?`
- `X -> X` same-value continuation
- 以及少量 `bridge_mapping`

### 70.5 这轮对任务书主链的真正意义

任务书 7.4 在 terminal candidate 层期望的四通道，现在已经最小闭环为：

- `terminal_numeric_channel`
- `continuation_channel`
- `semantic_channel`
- `noise_channel`

同时又保持了两个重要边界：

1. PairBuilder 仍只直接消费 `terminal_numeric_channel`
2. `semantic_mapping` 的 selected numeric 不会被误并进 continuation channel

所以这一轮补上的不是“更多语义”，而是把 current-head 已经识别出来的 relation 语义，真正回写到了 candidate 运行态。

### 70.6 这轮之后最近的剩余缺口

在 `phase26` 之后，最接近任务书主链的剩余缺口已经进一步收敛为：

1. `semantic_mapping` 仍只有最小 pair 级合同，还没有 semantic-specific 项目级一致性规则
2. `bridge_mapping` 与 `semantic_mapping` 还没有更系统的 relation ledger / index
3. `continuation_channel` 已落地，但还没有更专门的 candidate-level 统计/规则消费方

也就是说，下一刀不再是“candidate 四通道是否完整”，而更可能是：

- semantic-specific project rule input
- 或更系统的 bridge / semantic ledger

## 71. 2026-07-06 current-head 任务书审计刷新：下一刀应是 semantic-specific project rule，而不是再回页级路由或桌面层

在 `phase26` 之后，我又按 current-head 重新对照了任务书主链，不再沿用历史叙事，而是直接核查：

- [任务书.md](/F:/workspace/XJToolkit/doc/任务书.md)
- 当前代码：
  - [page_classifier.py](/F:/workspace/XJToolkit/src/dwg_audit/page_classifier.py)
  - [page_router.py](/F:/workspace/XJToolkit/src/dwg_audit/page_router.py)
  - [pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py)
  - [table_extractor.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/table_extractor.py)
  - [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py)
- 当前测试：
  - [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)
  - [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py)
- 当前真实样本产物：
  - [phase26_continuation_channel_second/2_2](/F:/workspace/XJToolkit/.tmp/phase26_continuation_channel_second/2_2)
  - [phase26_continuation_channel_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA](/F:/workspace/XJToolkit/.tmp/phase26_continuation_channel_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

### 71.1 为什么页级分类器 / 路由器 / TableExtractor 暂时不是最近缺口

按任务书第 4/5 层，当前已经有几条足够强的 current-head 证据：

- `pipeline.py` 已在 extract 后显式调用 `classify_pages()`，并用 `enrich_pages_from_classifications()` 把 `route_target / audit_disposition` 回填到 page 运行态。
- 当前 pipeline 已真实分流为：
  - PairBuilder 链
  - TableExtractor 链
  - Layout / Skip 路径
- `test_analyze_project.py` 已覆盖：
  - 普通回路页走 `WireDiagramExtractor`
  - 表格页走 `TableExtractor`
  - 并产出 `table_mapping`
- 当前两套真实样本里，页级 findings / pages.parquet 已稳定带：
  - `page_type`
  - `route_target`
  - `audit_disposition`
- 真实样本中暂未出现稳定命中的表格页，但任务书明确允许在真实样本不足时，用隔离 synthetic / mutation case 证明 `TableExtractor` 命中路径；当前仓库已经有这条 synthetic 闭环证明。

直接结论：

- 这条链当前仍可继续增强，但它已经不再是“主链完全没证明”的状态。
- 如果现在继续把主要精力投入 page router / TableExtractor，本质上更像“加固已有证明”，而不是补最近的主链断点。

### 71.2 为什么 table mapping consistency 也不是最近缺口

任务书要求三类一致性之一是：

- 表格映射与图内端子映射之间的一致性

current-head 上，这条并不是完全空白：

- `table_extractor.py` 生成的 `table_mapping` pair 当前是高置信 `pass`
- `rules.py` 的 `_high_confidence_pairs()` 已明确把 `evidence.source == "table_mapping"` 纳入项目级 graph
- `test_pairs_and_rules.py` 已有单测证明：
  - `table_mapping` pair 会作为高置信信源参与 `R-CROSS-PAGE-CONFLICT`

这说明 table mapping 至少已经不是“识别出来就消失”，而是能进入现有项目级规则主链。

### 71.3 当前真正缺的，是 terminal -> semantic 的项目级一致性

任务书在开头就把 MVP 审计目标明确成三类一致性：

1. 端子号对端子号
2. 端子号对语义端
3. 表格映射对图内端子映射

其中 current-head 的最弱一条正是第 2 类：

- `semantic_mapping` 现在已经能被识别并落为显式 `pair_kind`
- 但 `rules.py` 当前所有项目级 graph / conflict / one-to-many 规则仍只吃：
  - `ordinary_pair`
  - 外加 `table_mapping` 作为 ordinary graph 的高置信信源
- `semantic_mapping` 当前只做到了：
  - 可落盘
  - 可展示
  - 可旁路 ordinary missing-side / low-confidence
- 但它**还没有任何 semantic-specific 项目级一致性规则**

这意味着系统现在已经能说出：

- “这是一条 terminal -> semantic relation”

却还不能进一步回答：

- “同一个 terminal 在不同页是否对应了冲突的 semantic endpoint”

这正是任务书主链里目前最接近、也最具体的剩余空洞。

### 71.4 下一刀应收窄成什么

基于 current-head 审计，下一刀最合理的单一核心切片应定义为：

- **只给 `semantic_mapping` 增加一条最小的项目级一致性规则：当同一 terminal 在不同 sheet 上稳定映射到不同的 normalized semantic endpoint 时，输出一条 semantic conflict issue。**

这条切片故意保持很窄：

- 只处理 `pair_kind = semantic_mapping`
- 只处理能正规化成稳定 semantic endpoint family 的 marker
  - 如 `DK / KLP / CLP / ZKK / KK / ZK`
- 只处理“每个 sheet 内各自已稳定到单一 endpoint”的 case
- 只处理跨 `sheet_id` 的冲突
- 不尝试一次性解决：
  - `IA/IB/IC/UN/3U0/I0` 这类相量/量纲复合 marker
  - semantic ledger 全量重构
  - 同页多 marker 噪声
  - bridge-specific 项目级规则

### 71.5 为什么这轮不该优先做别的

当前仍不该优先的方向：

1. 再回桌面端 / Tauri / preview
2. 继续只拧 `candidates.py` 全局阈值
3. 再去泛化 TableExtractor，而不先补 terminal -> semantic 一致性规则
4. 在 semantic rule 还没出现前，就先做更大的 bridge / semantic ledger 重构

## 72. 2026-07-06 semantic-specific project rule 已最小落地：`R-SEMANTIC-MAPPING-CONFLICT`

在 section 71 已经明确“下一刀应是 semantic-specific project rule”之后，我把这条规则按最小边界直接落进了 current-head：

- 新规则：`R-SEMANTIC-MAPPING-CONFLICT`
- 代码位置：
  - [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py)
  - [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py)
  - [default.yml](/F:/workspace/XJToolkit/configs/default.yml)
  - [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py)

### 72.1 规则边界

这次没有去做更大的 semantic ledger，只做了一条窄规则：

- 只消费 `pair_kind == "semantic_mapping"`
- 只从 `semantic_marker_texts` 中正规化少数稳定 family：
  - `DK`
  - `KLP`
  - `CLP`
  - `ZKK / KZKK`
  - `KK`
  - `ZK`
- 只接受“每个 sheet 内稳定到单一 normalized endpoint”的 terminal
- 只报跨 sheet 冲突
- 同页多 marker 噪声、`IA/IB/IC/UN/3U0/I0`、更大的 bridge/semantic ledger 都继续留到后面

也就是说，这条规则当前只回答一个问题：

- 同一个 terminal value，在不同页里是否稳定指向了不同 semantic endpoint

### 72.2 测试与回归结果

本轮新增验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping_conflict or semantic_mapping or table_mapping"` -> `5 passed`
- `python -m pytest -q` -> `160 passed`

新增单测只覆盖两件事：

- 跨 sheet 的 stable-singleton semantic endpoint 会报冲突
- 某个 sheet 内如果本地 endpoint 不稳定，则不报冲突

### 72.3 真实样本结果

第二套样本：

- 输出路径：[phase27_semantic_rule_second](/F:/workspace/XJToolkit/.tmp/phase27_semantic_rule_second/2_2)
- 总 issue：`518 -> 519`
- 新增 issue 仅 `1` 条，而且正是预期的 `R-SEMANTIC-MAPPING-CONFLICT`
- 具体冲突：
  - terminal `114`
  - `S0021 / 21 左侧端子图1.dwg -> KLP2-1`
  - `S0023 / 23 右侧端子图1.dwg -> ZK-3`

第一套样本：

- 输出路径：[phase27_semantic_rule_first](/F:/workspace/XJToolkit/.tmp/phase27_semantic_rule_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 总 issue 保持 `345`
- `R-SEMANTIC-MAPPING-CONFLICT = 0`

这说明当前边界至少满足三件事：

- 没有 flood
- 没有打乱 ordinary / continuation / bridge / semantic 既有 pair 分布
- 能在真实样本里命中一条可解释的 terminal-to-semantic inconsistency

### 72.4 当前裁决

这条 semantic-specific rule 已经从“任务书缺口”推进到了“current-head 已有最小闭环证明”。

因此下一步不该回去重做 page router / TableExtractor，也不该立刻扩大 semantic family；更合理的下一个候选缺口会是二选一：

1. `table_mapping` 对 `ordinary_pair` 的 mixed-source consistency 专项规则
2. 更系统的 semantic / bridge ledger，但前提是继续保持窄切片

## 73. 2026-07-06 current-head 任务书审计刷新：最近缺口已收口到 `table_mapping` vs `ordinary_pair` 的 mixed-source consistency

在 section 72 补完 `R-SEMANTIC-MAPPING-CONFLICT` 之后，我又重新按当前头部代码、当前测试和当前产物审了一遍任务书，不再沿用历史叙事。

这次重点核对的是三件事：

- 页级分类 / 路由 / `TableExtractor` 是否还属于“主链断点”
- 第三类一致性“表格映射与图内端子映射之间的一致性”到底做到哪一步
- 当前最近的一刀到底应该是“继续补功能”，还是“把已存在能力证明清楚”

### 73.1 为什么页级分类 / 路由 / `TableExtractor` 暂时不是最近缺口

结合 current-head 代码、测试和保留产物，当前至少已有以下强证据：

- `pipeline.py` 在 extract 后真实调用 `classify_pages()`，并把 `route_target / audit_disposition` 回填到 page 运行态。
- `TableExtractor` 不是“文件存在”，而是真有独立路由：
  - 表格页从 pairing 主链排除
  - 单独走 `extract_table_pairs()`
- 第二套真实样本 current-head 产物里，每页都有：
  - `page_type`
  - `route_target`
  - `audit_disposition`
- synthetic `analyze-project` 集成测试已经证明：
  - 普通回路页走 `WireDiagramExtractor`
  - 表格页走 `TableExtractor`
  - 表格页不再走 `line_groups`
  - 并且真实产出 `table_mapping`

更准确地说，当前仍然可以继续增强 page router / component subtype / table semantics，但它们已经不再是“主链完全没证明”的状态。

### 73.2 重新裁决第三类一致性：当前缺的不是 `table_mapping` 存在性，而是 mixed-source consistency

任务书开头把 MVP 的三类一致性写得很明确：

1. 端子号对端子号
2. 端子号对语义端
3. 表格映射对图内端子映射

第 1 类 current-head 一直存在普通 pair graph 规则。

第 2 类在 section 72 之后，已经有：

- `semantic_mapping` 显式 relation
- `R-SEMANTIC-MAPPING-CONFLICT`
- current-head 真实样本第二套仅新增 `1` 条可解释 semantic conflict

但第 3 类目前仍停在一个更弱的状态：

- `TableExtractor` 会生成高置信 `table_mapping` pair
- `_high_confidence_pairs()` 会把 `evidence.source == "table_mapping"` 放进高置信集合
- 也就是说，`table_mapping` 已经能被通用 pair graph 看见

可问题在于，当前还没有一条**显式的 source-aware mixed-source 规则**去回答：

- 同一个 left value，表格映射和图内普通 pair 是否彼此一致

换句话说，现在系统能证明：

- “表格页能被独立识别并产出高置信 pair”

但还不能清楚地区分：

- “这是普通 cross-page conflict”
- 还是
- “这是 `table_mapping` 和 ordinary pair 之间的 mixed-source inconsistency”

### 73.3 当前头部代码的更精确结论

这一点需要说得更细一点：

- 当前代码并不是完全看不见 mixed-source case。
- 如果把一个 `table_mapping` pair 和一个 ordinary high-confidence pair 一起送进现有 `build_issues()`，通用 `R-CROSS-PAGE-CONFLICT` 的确可能把它们当成普通 graph conflict 看见。

但这还不等于“第三类一致性已经被任务书层面证明完成”，因为：

- 当前没有单独的 mixed-source rule id
- 当前没有 source-aware 证据解释
- 当前测试也没有把“`table_mapping` vs ordinary pair`”当作独立目标明确证明

现有单测只明确证明了一件更弱的事：

- 两条 `table_mapping` pair 自己之间可以触发通用 `R-CROSS-PAGE-CONFLICT`

这还不够支撑“表格映射与图内端子映射之间的一致性”这条任务书主链。

### 73.4 当前裁决：下一刀应是最小 mixed-source consistency 规则

基于 current-head 审计，下一刀最合理的单一核心切片应定义为：

- **只为 `table_mapping` 与 `ordinary_pair` 增加一条最小 mixed-source consistency 规则，并补齐对应 unit/integration 证明。**

这条切片故意保持很窄：

- 只消费高置信 ordinary pair 与 `evidence.source == "table_mapping"` 的 pair
- 只处理相同 left value 的 source mismatch
- 只回答“表格映射和图内普通配对是否一致”
- 不同时扩展：
  - 更强的表头语义端合成
  - 更大的 table semantic ledger
  - component subtype 收口
  - page router 顶层彻底拆成三条独立 pairing extractor

这也意味着，当前不该优先回去做的方向包括：

1. 再回桌面端 / Tauri / preview
2. 再拧全局候选阈值
3. 再把 page router 写得更“好看”，但不补第三类一致性
4. 在 `table_mapping` vs ordinary pair 还没独立闭环前，就先做更大的 table semantic 推理

## 74. 2026-07-06 mixed-source consistency 已最小落地：`R-TABLE-MAPPING-SOURCE-CONFLICT`

在 section 73 把“最近缺口”重新裁成 `table_mapping` vs `ordinary_pair` 的 mixed-source consistency 之后，我按最小边界把这条规则落进了 current-head。

- 新规则：`R-TABLE-MAPPING-SOURCE-CONFLICT`
- 代码位置：
  - [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py)
  - [config.py](/F:/workspace/XJToolkit/src/dwg_audit/utils/config.py)
  - [default.yml](/F:/workspace/XJToolkit/configs/default.yml)
  - [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py)
  - [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)

### 74.1 这条规则现在具体做什么

这次仍然没有去重写 `TableExtractor`，而是只补一条 source-aware project rule：

- 只消费高置信 ordinary pair
- 外加 `evidence.source == "table_mapping"` 的高置信 pair
- 只看相同 `left_value`
- 当 `table_mapping` 与 ordinary pair 指向的 `right_value` 集合不一致时，输出一条 mixed-source issue

这条规则当前回答的是：

- 同一个 left value，表格映射和图内普通配对是否彼此一致

### 74.2 新增证明

本轮新增两层证明：

1. unit 级规则证明
- `table_mapping` 与 ordinary pair 冲突时，命中 `R-TABLE-MAPPING-SOURCE-CONFLICT`
- 两类 source 一致时，不报 mixed-source conflict

2. `analyze-project -> run-audit` 级 synthetic 证明
- 一页普通回路图
- 一页表格页
- 表格页独立走 `TableExtractor`
- 审计阶段能命中 mixed-source conflict

这条 synthetic 闭环很关键，因为它证明的已经不是“单独构造两个 Pair 送进 RuleEngine”，而是：

- 页级分类
- 路由
- `TableExtractor`
- findings 落盘
- `run-audit`

整条主链都能把 mixed-source inconsistency 提出来。

### 74.3 验证结果

定向验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "table_mapping or mixed_source or semantic_mapping_conflict"` -> `5 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "table_extractor or mixed_source_conflict"` -> `2 passed`

全量回归：

- `python -m pytest -q` -> `163 passed`

真实样本 rerun：

- 第二套：[phase28_table_mixed_source_second](/F:/workspace/XJToolkit/.tmp/phase28_table_mixed_source_second/2_2)
- 第一套：[phase28_table_mixed_source_first](/F:/workspace/XJToolkit/.tmp/phase28_table_mixed_source_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

真实样本 current-head 结果：

- 第二套总 issue 仍是 `519`
- 第一套总 issue 仍是 `345`
- 两套样本 `R-TABLE-MAPPING-SOURCE-CONFLICT = 0`
- 两套样本 `table_pages = 0 / total_mappings = 0`

这说明这刀满足三件事：

- synthetic 主链证明已经补上
- 在真实样本“暂无稳定表格页命中”的前提下，没有引入额外回退
- 第三类一致性现在不再只是“隐式靠通用 graph 也许能撞见”，而是有了显式 rule contract

### 74.4 当前裁决

到这一轮为止，任务书开头那三类关系的最小闭环已经分别具备：

1. 端子对端子：
   - ordinary pair + 普通 graph rules
2. 端子对语义端：
   - `semantic_mapping` + `R-SEMANTIC-MAPPING-CONFLICT`
3. 表格对端子：
   - `table_mapping` + `R-TABLE-MAPPING-SOURCE-CONFLICT`

但这不等于表格方向已经“完全完成”。当前仍然没补的是更强的表头型三列表格语义：

- `表头前缀 + 行号 -> 逻辑语义端`
- 例如 `1-21QD` + `1` => `1-21QD1`

所以 mixed-source consistency 已不是最近缺口；下一刀更像是二选一：

1. 表头型三列表格的逻辑语义端合成与 `table_mapping` 语义增强
2. M10 / 最小验收场景中的隔离故障注入与 Pair recall 量化证明

## 75. 2026-07-06 表头型三列表格已补齐，并额外完成一轮边界硬化

在 section 74 把 mixed-source consistency 收口之后，我继续按 current-head 任务书推进表格方向最近的功能缺口：

- `表头前缀 + 行号 -> 逻辑语义端`
- 同一行左右两侧端点分别输出高置信 `table_mapping`

这轮已经不是只补 rule，而是直接把 `TableExtractor` 的 stronger MVP 功能补进 current-head。

### 75.1 当前功能合同

本轮新增能力落在：

- [table_extractor.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/table_extractor.py)
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
- [test_table_extractor.py](/F:/workspace/XJToolkit/tests/unit/test_table_extractor.py)
- [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)

当前 `TableExtractor` 现在同时支持两类三列表格：

1. 数值三列表格
- 继续保留原有 `numeric_three_column`
- 中列数字与外列数字生成高置信映射

2. 表头型三列表格
- 首行中列识别 `header_prefix`
- 后续中列识别连续行号
- 合成 `logical_endpoint = header_prefix + row_number`
- 左右两侧 terminal-like 文本分别生成 `table_mapping`

page findings 里也补了表格结构摘要：

- `table_mapping_modes`
- `table_header_prefixes`
- `table_logical_endpoint_examples`
- `table_row_number_sequence_valid`

### 75.2 这轮额外修掉的两个真实风险

并行只读子代理指出，这组改动如果直接停在第一版，会有两个 P1 风险。我在主线程把它们一起收口了：

1. 备注文本误抬升为高置信 `table_mapping`
- 原始版本只要一侧像端子，另一侧非空文本也会被一起产出 pair
- 现在 header-semantic 外列只接受 terminal-like 文本；备注侧会保留为空，不再产出 `logical_endpoint -> 备注`

2. numeric fallback 被单元格杂讯打断
- 原始版本放开所有文本入格后，`_primary_cell_text()` 可能先选到 `NOTE`
- 现在 numeric 模式会优先选择数值文本，header 模式会分别优先选择 header / row-number / endpoint 文本
- 这样表头模式失败后，仍能稳定回退到 `numeric_three_column`

### 75.3 新增证明

单元测试新增/覆盖了三类关键边界：

- 单元格同时含 `NOTE + 数字` 时，numeric 模式仍优先选数字
- 表头语义行一侧是备注、一侧是真端子时，只输出真端子那一侧的 pair
- 首行像表头但行号序列不成立时，会稳定回退到 `numeric_three_column`

synthetic `analyze-project` 主链证明也已经补上：

- 表格页会独立路由到 `TableExtractor`
- `table_mapping_modes = {"header_semantic_three_column": 2}`
- 会生成：
  - `1-21QD1 -> 1-21n552`
  - `1-21QD1 -> 1-21n553`
  - `1-21QD2 -> 1-21n554`
  - `1-21QD2 -> 1-21n555`

### 75.4 验证结果

定向验证：

- `python -m pytest -q tests\unit\test_table_extractor.py` -> `8 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "table_extractor or header_semantic or mixed_source_conflict"` -> `3 passed`

全量回归：

- `python -m pytest -q` -> `168 passed`

真实样本 rerun：

- 第二套：[phase30_table_header_hardening_second](/F:/workspace/XJToolkit/.tmp/phase30_table_header_hardening_second/2_2)
- 第一套：[phase30_table_header_hardening_first](/F:/workspace/XJToolkit/.tmp/phase30_table_header_hardening_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

真实样本 current-head 结果保持稳定：

- 第二套总 issue 仍是 `519`
- 第一套总 issue 仍是 `345`
- 两套 `table_pages = 0 / total_mappings = 0`

这说明：

- 表头型三列表格能力已经具备功能闭环证明
- 但 current real samples 里仍然没有稳定命中的真实表格页
- 这轮改动没有把真实项目误抬成表格页，也没有引入额外 issue 洪峰

### 75.5 当前裁决

到这一轮为止，表格方向可以分成两层来看：

1. 功能层
- `TableExtractor` 的 stronger MVP 已经补到：
  - header prefix
  - row number
  - logical endpoint
  - bilateral `table_mapping`

2. 验收层
- `M10` / 最小验收仍未闭环
- 当前最明显缺口仍是：
  - 人工标注 pair precision / recall
  - 5 张隔离故障注入样本
  - issue 命中率与误报率的端到端评估

所以当前最近缺口已经不再是 `TableExtractor` 的表头语义功能，而更像是：

1. `M10` 回归验证闭环
2. 最小验收场景的故障注入与量化评估

## 76. 2026-07-06 current-head 任务书完成度审计：主链已基本成形，最近显式缺口转到 `M10`

在 section 75 完成表头型三列表格之后，我按当前仓库、当前测试、当前真实样本产物重新做了一轮任务书完成度审计，不再沿用历史叙事。

### 76.1 已有强证据证明完成

1. 真实样本里的页级分类 / 路由合同已经真实落盘
- 第二套 current-head [phase31_acceptance_second](/F:/workspace/XJToolkit/.tmp/phase31_acceptance_second/2_2) 里，每页都能在 `findings.json.page_findings` 看到：
  - `page_type`
  - `audit_disposition`
  - `route_target`
- 同时真实样本里不同图种已经落到不同 route：
  - `04 交流回路图1.dwg` -> `WireDiagramExtractor`
  - `17 测控1装置背板.dwg` -> `LayoutOnlyExtractor`
  - `19 元件接线图1.dwg` -> `ComponentDiagramExtractor`
  - `21 左侧端子图1.dwg` -> `TerminalDiagramExtractor`

2. 报告侧的 issue 可复核证据链已经具备 current-head 强证据
- 当前真实样本 `issues.json` / `audit_report.md` 已稳定包含：
  - `filename`
  - `sheet_id`
  - `line_group_id` 或几何锚点
  - `left_value / right_value`
  - `rule_id`
  - `confidence`
  - `message / explanation / recommended_action`
  - `evidence_refs`

3. 三类关系的最小功能闭环都已经有代码 + 测试 + rerun 证据
- 端子对端子：
  - ordinary pair + 普通 graph rules
- 端子对语义端：
  - `semantic_mapping` + `R-SEMANTIC-MAPPING-CONFLICT`
- 表格对端子：
  - `table_mapping` + `R-TABLE-MAPPING-SOURCE-CONFLICT`
- 表头型三列表格本身也已具备 `header_prefix + row_number -> logical_endpoint` 的 synthetic 主链证明

4. `page_findings` 默认内部运行态、非默认正式交付物，已经与任务书对齐
- default runtime 下不再强制落盘 `page_findings/*.md|json`
- 但 `findings.json` 内部仍保留结构化页级记录，满足内部 SSoT 目标

### 76.2 只有部分实现，仍不能宣称完全闭环

1. 页级分类器 / router 是“结果上成立”，但离任务书理想结构还有距离
- current-head 已经能稳定产出 `route_target`
- 但除 `TableExtractor` 外，其余页型目前更多还是“共用 PairBuilder 主链 + 图种专用分支/护栏”
- 所以从工程结构看仍是部分实现，不等于已经完全演化成四条彻底独立的 extractor 链

2. 表格页真分流在真实样本里仍没有命中
- current real samples 里 `table_pages = 0 / total_mappings = 0`
- 这说明 `TableExtractor` 的真实项目命中还没有强证据
- 但任务书同时明确允许：若真实样本里表格页不足，可用隔离 synthetic / mutation 样本补验证
- 所以这条更适合判定为“真实样本不足下的部分实现”，而不是当前最近的主缺口

3. `pages.parquet` 与 `page_findings` 的结构信息仍不完全对称
- `page_findings` 里有 `page_type`
- `pages.parquet` 当前更侧重 `route_target / audit_disposition / confidence`
- 这不影响当前 UI / report / rerun 主链，但从 findings 统一性上看仍可继续收口

### 76.3 已明确未完成

1. `M10`：回归测试与样本验证
- current-head 已有 regression 脚手架，但 `precision / recall` 仍是 `None`
- 还没有真实样本人工标注 pair 指标
- 还没有 texts / lines 召回不回退的真实基线量化
- 还没有把最小验收资产接成固定回归批次

2. 第 19 节最小验收场景
- 在本轮之前，repo 里还没有持久化的 5 页隔离故障注入验收夹具
- 也没有与之绑定的量化报告产物

### 76.4 当前裁决

基于 current-head，这一轮最接近任务书主链的未完成项已经不是继续往 `candidates.py` 或 table 语义里加局部规则，而是：

- **把 `M10` / 第 19 节最小验收从“脚手架”推进成“持久化资产 + 量化报告”。**

不应继续优先的方向包括：

1. 再回桌面端 / Tauri / preview
2. 再用 issue 总数变化冒充主链进展
3. 在 `M10` 仍空心时，继续大改 extractor 物理分层

## 77. 2026-07-06 `acceptance-mini` 已落地：最小验收第一次变成可复跑资产

在 section 76 把最近缺口收口到 `M10` 之后，我只推进了一条最短闭环切片：

- 增加持久化的 `acceptance-mini` 5 页夹具
- 增加与之绑定的标注 spec
- 增加量化 acceptance evaluator + CLI

### 77.1 新增资产

代码与夹具位置：

- [acceptance.py](/F:/workspace/XJToolkit/src/dwg_audit/report/acceptance.py)
- [cli.py](/F:/workspace/XJToolkit/src/dwg_audit/cli.py)
- [spec.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_mini/spec.json)
- [project/](/F:/workspace/XJToolkit/tests/fixtures/acceptance_mini/project)
- [test_acceptance_evaluation.py](/F:/workspace/XJToolkit/tests/integration/test_acceptance_evaluation.py)

`acceptance-mini` 当前覆盖：

- `1` 张非回路页
- `10` 组正常 pair
- `2` 组跨页冲突
- `2` 组单侧缺失
- `2` 组多候选 `review`

### 77.2 新评估链现在量化什么

`evaluate-acceptance` 当前会读取 `findings/ + audit/ + spec`，输出：

- complete pair `precision`
- complete pair `recall`
- skip page recall
- conflict issue recall
- missing issue recall
- review pair recall
- issue 字段完备性检查

这使任务书第 19 节里的 5 类最小验收要求，第一次变成了可量化、可落盘、可回归比较的资产，而不是只靠叙述说明。

### 77.3 新增证明

定向验证：

- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `1 passed`
- `python -m pytest -q tests\integration\test_acceptance_evaluation.py tests\integration\test_analyze_project.py -k "acceptance or table_extractor or header_semantic or mixed_source_conflict"` -> `4 passed`
- `python -m pytest -q tests\unit\test_regression_metrics.py tests\unit\test_rerun_regression.py` -> `6 passed`

全量回归：

- `python -m pytest -q` -> `169 passed`

Acceptance 集成测试已证明：

- `analyze-project -> run-audit -> evaluate-acceptance`

整条链可跑通，且在该 fixture 上当前结果为：

- pair precision = `1.0`
- pair recall = `1.0`
- conflict recall = `1.0`
- missing recall = `1.0`
- review recall = `1.0`
- skip page recall = `1.0`

### 77.4 真实样本稳定性

虽然这轮没有改动抽取主逻辑，我仍然按任务书要求复跑了第二套真实样本：

- [phase31_acceptance_second](/F:/workspace/XJToolkit/.tmp/phase31_acceptance_second/2_2)

current-head 结果保持稳定：

- `issue_count = 519`
- `R-PAIR-MISSING-SIDE = 317`
- `R-PAIR-LOW-CONFIDENCE = 201`
- `R-SEMANTIC-MAPPING-CONFLICT = 1`
- `table_pages = 0 / total_mappings = 0`

这说明本轮 acceptance 资产与新 CLI 没有把主链带偏。

### 77.5 当前裁决

到这一轮为止，`M10` 可以拆成两层来看：

1. 已经具备的层
- regression report 脚手架
- rerun-from-findings golden snapshot
- acceptance-mini 持久化夹具
- acceptance 量化 CLI / report

2. 仍未闭环的层
- 真实样本人工标注 pair precision / recall
- texts / lines 召回不回退的真实基线量化
- 把 acceptance 评估正式接成固定项目级回归批次

所以 current-head 最近的下一条缺口，更像是：

1. 真实样本人工标注与 pair 指标量化
2. texts / lines 回归基线量化

## 78. 2026-07-06 第一份真实样本 scoped acceptance 基线已出现

在 section 77 把 `acceptance-mini` 落成持久化资产之后，我继续按 current-head 把最近缺口再收窄一层：

- 不去同时做更大页标注、texts 基线、lines 基线
- 先只补“真实样本人工标注子集的 pair precision / recall”

### 78.1 先解决 evaluator 的结构性缺口

当前 `evaluate-acceptance` 原本只能按**整个项目**计算 complete pair precision。

这意味着只要标 1 页，整项目其他页的 complete pair 都会落进 `unexpected_pairs`，precision 会被无关页污染。这不适合“真实样本先做一小块人工标注”的工作流。

所以这轮先补的不是新抽取规则，而是 acceptance evaluator 的 scope 合同：

- 代码位置：[acceptance.py](/F:/workspace/XJToolkit/src/dwg_audit/report/acceptance.py)
- 新增 `pair_scope`
- 当前支持：
  - `included_sheet_ids`
  - `included_filenames`
  - `pair_kinds`
  - `statuses`

同时把 `acceptance_passed` 调整成：

- 当 `expected_skip_pages / expected_conflicts / expected_missing_issues / expected_review_pairs` 为空时，对应 check 自动跳过
- 不再因为 `expected_count = 0` 把 scoped spec 误判为失败

这一步的直接意义是：

- synthetic acceptance 仍然保持原样可跑
- 真实样本小范围标注现在终于能算出**不被整项目其它页污染**的 pair precision / recall

### 78.2 这轮为什么先选 `S0024`

我并发拉了只读子代理做页选择复核。子代理给出了两类有价值的建议：

- 一类更偏“full pair 密度高”的页，比如 `S0021 / S0023`
- 一类更偏“首批标注工作量小、ordinary pair 干净”的页，比如 `S0024`

主线程最后刻意选了第二类，原因很简单：

- 这轮的唯一目标是先证明“真实样本 scoped acceptance”能成立
- `S0024 / 24 右侧端子图2.dwg` 当前 ordinary complete pair 正好是 `7` 条
- 用一整页就能做出**有意义的 precision 分母**
- 又不用立即引入更复杂的 `pair_key` 级 scope 或几十条人工标注维护成本

本轮持久化 spec 放在：

- [second_set_terminal_s0024.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_real_subset/second_set_terminal_s0024.json)

当前标注的 `7` 组 pair 为：

- `406 -> 20`
- `409 -> 25`
- `412 -> 30`
- `415 -> 35`
- `418 -> 40`
- `421 -> 45`
- `428 -> 55`

scope 明确限制为：

- `sheet_id = S0024`
- `filename = 24 右侧端子图2.dwg`
- `pair_kind = ordinary_pair`

也就是说，这轮故意**不**把同页的大量 `semantic_mapping / continuation` 混进第一份 real-sample pair baseline。

### 78.3 新增证明

为了避免 scope 只在真实样本 spec 上“看起来可用”，我先补了一条 synthetic 集成测试：

- [test_acceptance_evaluation.py](/F:/workspace/XJToolkit/tests/integration/test_acceptance_evaluation.py)

它证明：

- 只评 `04 正常回路图A.dwg`
- 只消费 `ordinary_pair`
- 即使 spec 不再提供 skip/conflict/missing/review 期望项
- acceptance 仍然可以正确通过

本轮验证结果：

- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `2 passed`
- `python -m pytest -q tests\unit\test_regression_metrics.py tests\unit\test_rerun_regression.py` -> `6 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "acceptance or table_extractor or header_semantic or mixed_source_conflict"` -> `3 passed`
- `python -m pytest -q` -> `170 passed`

### 78.4 current-head 真实样本结果

我直接在第二套 current-head 产物上执行了 scoped acceptance：

- 命令输出目录：[phase32_real_subset_eval_s0024](/F:/workspace/XJToolkit/.tmp/phase32_real_subset_eval_s0024)

结果如下：

- `expected_pair_count = 7`
- `extracted_complete_pair_count = 7`
- `matched_pair_count = 7`
- `pair_precision = 1.0`
- `pair_recall = 1.0`
- `acceptance_passed = True`

这说明：

- 当前 `S0024` 这组 ordinary full pair 已经可以作为一份**真实样本、持久化、可复跑**的最小 precision / recall 基线
- 它不再只是 synthetic fixture 的成功案例

### 78.5 当前裁决

这一轮之后，`M10` 的状态更准确地说是：

1. 已经完成的层
- synthetic `acceptance-mini`
- scoped acceptance evaluator
- 第一份真实样本 `pair precision / recall` 持久化 spec

2. 仍未闭环的层
- 扩更多真实页，避免只停在 `S0024`
- 是否需要更细粒度的 `pair_key` 级 scope，来支持高密度页的“小样本标注”
- texts / lines 非回退基线量化

所以 current-head 最近的下一条缺口，已经不再是“有没有真实样本 precision / recall”，而更像是：

1. 把 real-sample scoped spec 从 `1` 页扩到多页
2. 把 texts / lines 基线也拉进同一套量化回归里

## 79. 2026-07-06 最近缺口重新裁决：先扩 real-sample pair baseline，再轮到 texts / lines

在 section 78 之后，我先没有直接往 `texts / lines` 量化上冲，而是又按 current-head 做了一次任务书裁决，并并发拉了只读子代理复核一个窄问题：

- 页级分类 / 路由 / `TableExtractor` / terminal semantic / continuation 已有当前证据的前提下
- 最近缺口是不是已经转到 `M10` 的 `texts / lines` 非回退量化

子代理给出的结论是：`No`。

主线程复核后，同意这个判断。

### 79.1 为什么现在还不该先跳到 texts / lines

因为虽然 `texts / lines` 非回退量化确实仍未完成，但离任务书最近的单一缺口其实还卡在更前一层：

- 真实样本 pair 量化虽然已经从 `0` 变成了 `1` 份持久化 spec
- 但 section 78 里那份 real-sample baseline 仍只覆盖：
  - `S0024 / 24 右侧端子图2.dwg`
  - `7` 条 `ordinary_pair`

这还不足以支撑“真实样本 pair precision / recall 已经有代表性基线”。

而任务书第 15 章里写得很直接：

- `Pair precision 和 recall 有量化指标`
- `文本抽取不回退`
- `线段召回不回退`

在这三项里，当前离闭环最近的仍然是第一项的**扩面**，不是后两项。

### 79.2 这轮真正补的不是新规则，而是 acceptance 的精确选样能力

如果继续沿用 section 78 的 scope 粒度，只能按整页筛：

- `included_sheet_ids`
- `included_filenames`
- `pair_kinds`
- `statuses`

问题在于，高密度真实页如 `S0020 / 20 元件接线图2.dwg` 有大量 ordinary full pair，其中一些还是重复 relation 行。

若按整页 scope：

- precision 分母会被整页所有 complete pair 放大
- 这迫使我们要么一次性标完整页几十条，要么得到被无关 pair 稀释的 precision

所以这轮 acceptance evaluator 又往前收了一小步：

- 代码位置：[acceptance.py](/F:/workspace/XJToolkit/src/dwg_audit/report/acceptance.py)
- 新增 `included_pair_refs`
- 格式是：
  - `{filename, pair_key}`

也就是说，真实样本现在可以按“文件名 + pair_key”精确选样，而不是只能整页吞下。

同时 complete pair 统计也改成按：

- `filename + left_value + right_value`

做去重，避免同一 relation 的重复行把 precision 分母虚增。

### 79.3 这轮新增的真实样本基线

本轮新增的持久化 spec 是：

- [second_set_component_terminal_subset.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_real_subset/second_set_component_terminal_subset.json)

它把 real-sample baseline 从“单页 terminal 7 对”扩到了两类 extractor：

1. `ComponentDiagramExtractor`
- `S0020 / 20 元件接线图2.dwg`
- 选入 `6` 对：
  - `18 -> 404`
  - `23 -> 407`
  - `28 -> 410`
  - `33 -> 413`
  - `38 -> 416`
  - `43 -> 419`

2. `TerminalDiagramExtractor`
- `S0024 / 24 右侧端子图2.dwg`
- 选入 `7` 对：
  - `406 -> 20`
  - `409 -> 25`
  - `412 -> 30`
  - `415 -> 35`
  - `418 -> 40`
  - `421 -> 45`
  - `428 -> 55`

合计：

- `13` 对真实样本 `ordinary_pair`

这比 section 78 的单页 `7` 对，更接近“多页 / 多 extractor 的真实样本 pair baseline”。

### 79.4 新增证明

为了避免新 scope 只在真实样本 spec 上“碰巧有用”，我先补了一条 integration test：

- [test_acceptance_evaluation.py](/F:/workspace/XJToolkit/tests/integration/test_acceptance_evaluation.py)

这条测试证明：

- acceptance evaluator 可以只消费显式 `included_pair_refs`
- 同时避免跨页相同 `pair_key` 的误命中

本轮验证结果：

- `python -m pytest -q tests\unit\test_regression_metrics.py tests\unit\test_cli.py -k "regression or compare_regression"` -> `5 passed`
- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `3 passed`
- `python -m pytest -q` -> `171 passed`

### 79.5 fresh real-sample rerun 与 acceptance 结果

我这轮重新对第二套样本跑了 fresh rerun：

- analyze 输出目录：[phase33_regression_second](/F:/workspace/XJToolkit/.tmp/phase33_regression_second/2_2)

current-head rerun 结果保持稳定：

- `issue_count = 519`
- `route_targets = {Wire: 13, Terminal: 4, Component: 2, LayoutOnly: 2, Skip: 3}`
- `audit_dispositions = {audit_required: 19, classify_only: 2, skip_stable: 3}`

然后直接在这份 fresh rerun 上执行新的多页 acceptance：

- 输出目录：[phase34_real_subset_component_terminal](/F:/workspace/XJToolkit/.tmp/phase34_real_subset_component_terminal)

结果如下：

- `expected_pair_count = 13`
- `extracted_complete_pair_count = 13`
- `matched_pair_count = 13`
- `pair_precision = 1.0`
- `pair_recall = 1.0`
- `acceptance_passed = True`

这说明：

- 当前 real-sample pair baseline 已经不再只靠单页 terminal 的 `7` 对成立
- 而是已经扩到了：
  - `ComponentDiagramExtractor`
  - `TerminalDiagramExtractor`

两类真实样本页的 `13` 对 baseline

### 79.6 当前裁决

经过这轮之后，“最近缺口”的排序更清楚了：

1. 当前已经明显 stronger 的层
- real-sample pair baseline 已从 `1` 页扩到多页 / 多 extractor
- pair precision / recall 的真实样本证据更接近任务书主链

2. 仍未闭环的层
- 还没有把更多真实页型继续并入 same acceptance family
- 也还没有把 `texts / lines` 非回退量化补上

所以 current-head 最近的下一条缺口，**现在**才更像是二选一：

1. 继续扩 real-sample pair baseline 到更多页 / 更多 page type
2. 补 `texts / lines` 非回退量化，让 `M10` 的后两项开始成形

## 80. 2026-07-06 `texts / lines` 非回退量化已经进入 current-head regression report

在 section 79 把最近缺口重新裁决到 `M10` 之后，我这轮没有再扩 extractor 或 acceptance 范围，而是只补一条更短的闭环：

- 让 `compare-regression` 不再只比较：
  - `pair_count`
  - `issue_count`
  - `rule_counts`
- 而是显式量化：
  - `texts`
  - `numeric_texts`
  - `lines`
  - `line_groups`
  - 以及 `texts / lines` 的页级 non-regression status

### 80.1 为什么这条要落在 regression，而不是 acceptance

这一条衡量的不是：

- 人工标注 spec 命中率

而是：

- findings / audit 快照在 fresh rerun 之间是否出现抽取回退

所以它应该落在：

- [regression.py](/F:/workspace/XJToolkit/src/dwg_audit/report/regression.py)

而不是继续塞进：

- [acceptance.py](/F:/workspace/XJToolkit/src/dwg_audit/report/acceptance.py)

这点现在已经通过代码结构正式体现出来。

### 80.2 current-head 现在具体会输出什么

`compare-regression` 当前新增两块结果：

1. `delta.extraction_counts`
- `pages`
- `texts`
- `numeric_texts`
- `lines`
- `line_groups`

2. `non_regression_checks`
- `texts`
- `lines`

每项当前都显式带：

- `status`
- `comparison_mode`
- `baseline_total`
- `current_total`
- `total_delta`
- `dropped_sheets`

其中 `comparison_mode` 用来说明这次比较到底是：

- `per_page`
- 还是 `totals_only`

这能避免“由于元数据不全而根本没法逐页比”时，还把结果包装成误导性的 `ok`。

### 80.3 页级比较现在如何避免 `sheet_id` 假回归

本轮最关键的实现收口是：

- 页级比较优先使用稳定页键 `filename + sheet_order`

而不是：

- `sheet_id`

原因是 fresh rerun 中 `sheet_id` 可能重编，直接按 `sheet_id` 比，明明没回退也会被误判成回退。

当前页键逻辑已经改成：

1. 有整数型 `sheet_order` 且有 `filename`
- 用 `0004:04 xxx.dwg` 这类稳定键

2. `sheet_order` 缺失或不是数字
- 安全回退到 `filename`

3. 只有在再没有别的页身份信息时
- 才回退到 `sheet_id`

额外容错也已经补上：

- `sheet_order` 非数字时不再在 report 生成时崩溃

### 80.4 这轮还顺手修掉了一个“误报 ok”的边界

并发只读子代理 `Hegel` 帮我抓到了一个中风险边界：

- 当 `texts` 或 `lines` 缺 `sheet_id` 列时
- `_page_counts()` 会直接返回空
- 旧实现只看 `dropped_sheets` 是否为空
- 所以就算 `current_total < baseline_total`，也会误报 `status = ok`

这条现在已经修掉：

- 缺 `sheet_id` 无法逐页比时，会落到 `comparison_mode = totals_only`
- 只要 `total_delta < 0`，就仍然判定为 `regressed`

也就是说：

- “不可逐页定位”

不再等价于：

- “没有回退”

### 80.5 新增证明

定向验证：

- `python -m pytest -q tests\unit\test_regression_metrics.py` -> `6 passed`
- `python -m pytest -q tests\unit\test_cli.py -k "compare_regression"` -> `1 passed`
- `python -m pytest -q tests\unit\test_rerun_regression.py` -> `2 passed`

全量回归：

- `python -m pytest -q` -> `173 passed`

### 80.6 second-set current-head 真实样本结果

我直接用 second-set 现成的 current-head rerun 重新生成了 regression report：

- baseline:
  - [phase31_acceptance_second](/F:/workspace/XJToolkit/.tmp/phase31_acceptance_second/2_2)
- current:
  - [phase33_regression_second](/F:/workspace/XJToolkit/.tmp/phase33_regression_second/2_2)
- output:
  - [phase35_regression_with_extraction_second](/F:/workspace/XJToolkit/.tmp/phase35_regression_with_extraction_second)

结果现在已经明确写进：

- [regression_report.json](/F:/workspace/XJToolkit/.tmp/phase35_regression_with_extraction_second/regression_report.json)
- [regression_report.md](/F:/workspace/XJToolkit/.tmp/phase35_regression_with_extraction_second/regression_report.md)

关键值为：

- `pair_count delta = 0`
- `issue_count delta = 0`
- `texts delta = 0`
- `lines delta = 0`
- `line_groups delta = 0`
- `numeric_texts delta = 0`
- `texts status = ok`
- `lines status = ok`
- 两项 `comparison_mode` 都是 `per_page`

这说明 current-head 在 second-set 这份真实样本上，已经不只是“pair / issue 没回退”，而是：

- 文本抽取总量没有回退
- 线段抽取总量没有回退
- 且逐页上也没有观察到掉页式回退

### 80.7 当前裁决

到这一轮为止，`M10` 可以更准确地分成三层：

1. 已有 current-head 强证据
- synthetic `acceptance-mini`
- real-sample multi-page pair precision / recall baseline
- regression report 中的 `texts / lines` 非回退量化

2. 已做但还不是最终形态
- `line_groups` 目前只有显式 count delta，还没有独立 non-regression status
- 当 `pages` 元数据缺失时，页级 identity 仍可能回退到 `sheet_id`

3. 最近下一条缺口
- 继续扩 real-sample pair baseline 到更多页型
- 或把 `line_groups` 也升级成显式 no-regression status

也就是说，当前已经不适合再说：

- “texts / lines 非回退还没有量化”

更准确的说法应该是：

- `texts / lines` 已量化
- 但 `line_groups` 仍只是 count 级别，没有独立 status

## 81. 2026-07-06 任务书审计刷新：页级分类/路由证据已够强，最近缺口转为“页级合同落盘 + Table real-no-hit”

在 section 80 之后，我重新按 current-head 对照 [任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 做了一次更窄的完成度审计，专盯：

- `Page Classification Layer`
- `Page Router Layer`
- `TableExtractor`
- 以及“findings 是否真的把页级分类当成一等运行态保存”

这轮结论不再沿用旧叙事，而是只基于 current code、tests 和 fresh real-sample rerun。

### 81.1 已有强证据证明完成

1. 真实样本里，每页都有稳定 `route_target`

second-set current-head fresh rerun：

- [phase36_page_contract_second](/F:/workspace/XJToolkit/.tmp/phase36_page_contract_second/2_2)

其中：

- [pages.parquet](/F:/workspace/XJToolkit/.tmp/phase36_page_contract_second/2_2/findings/pages.parquet)
- [findings.json](/F:/workspace/XJToolkit/.tmp/phase36_page_contract_second/2_2/findings/findings.json)

现在都能直接证明不同图种走了不同 route：

- `04 交流回路图1.dwg -> WireDiagramExtractor`
- `17 测控1装置背板.dwg -> LayoutOnlyExtractor`
- `19 元件接线图1.dwg -> ComponentDiagramExtractor`
- `21 左侧端子图1.dwg -> TerminalDiagramExtractor`

而且 `audit_disposition` 也稳定区分了：

- `audit_required`
- `classify_only`
- `skip_stable`

2. 页级分类不是只停留在 scan 阶段粗标签

代码上：

- [page_classifier.py](/F:/workspace/XJToolkit/src/dwg_audit/page_classifier.py)
- [pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py)
- [page_router.py](/F:/workspace/XJToolkit/src/dwg_audit/page_router.py)

当前主链已经是：

- extract 后先做 `PageClassification`
- 再由 `Page Router` 决定 route target
- 再分发到 pairing 链或 `TableExtractor` 链

这不是“文件存在所以算完成”，而是 current-head 真实在执行的路径。

3. 页级分类/路由现在已成为 `pages.parquet` 一等字段

这是本轮刚补齐的关键合同：

- `page_type`
- `page_subtype`
- `page_type_confidence`
- `table_like`
- `grid_heavy`
- `route_target`
- `audit_disposition`

也就是说，任务书第 5.1 / 第 6 节要求的页级分类信息，已经不再只躲在聚合 JSON 或临时内存里，而是进入了 default findings 主表。

4. 页级说明文本不再继续误述成“纯文件名/sidecar 分类”

本轮把：

- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)

里的 `recognition_strategy` 改成显式反映：

- `PageClassifier labeled this page as ...`
- `Page Router sent it to ...`

second-set fresh rerun 里的代表页当前会写成：

- `PageClassifier labeled this page as '二次原理图' / 'grid_heavy_wire_diagram' using features [...] and Page Router sent it to 'WireDiagramExtractor' ...`

这点很重要，因为旧文案虽然不影响算法，但会直接削弱任务书主链“先分类再路由”的可证明性。

### 81.2 只有部分实现，仍不能宣称完全闭环

1. `TableExtractor` 仍然没有真实样本 hit 证明

这条还是当前最明显的部分实现：

- two real sets 当前都还是 `table_pages = 0`
- `total_mappings = 0`

current-head 证据：

- [phase36_page_contract_second findings.json](/F:/workspace/XJToolkit/.tmp/phase36_page_contract_second/2_2/findings/findings.json)
- [phase30_table_header_hardening_first findings.json](/F:/workspace/XJToolkit/.tmp/phase30_table_header_hardening_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/findings.json)

这意味着：

- `TableExtractor` 的功能合同已被 unit + synthetic `analyze-project` 证明
- 但“真实样本里真的命中过表格页”这件事仍然没有证据

任务书允许“若真实样本中暂无表格页，则明确证明样本中暂无该类命中”，所以这条现在更像：

- 真实 hit 未出现
- real-no-hit 的证明合同还需要更显式

2. per-type extractor 更像“分类/路由合同成立”，还不是三条彻底独立执行栈

当前：

- Wire / Component / Terminal 的 route matrix 已真实成立
- 但其执行层仍有大量共享 pairing 主链 + 图种专用护栏

所以更准确的说法应是：

- “按图种分流合同成立”

而不是：

- “每种图已经完全成为互不共享的大型独立识别器”

这不算当前最近缺口，但也不该过度宣称。

### 81.3 已明确未完成

1. `TableExtractor` 的 real-hit / real-no-hit 正式证明仍未收口

因为现在 repo 能证明：

- synthetic 命中
- real sample `0 hit`

但还没把“为何可接受 `0 hit`”变成一条更正式、更显式的 current-head 合同。

2. `issue` JSON 的可复核字段仍主要通过 `evidence / evidence_refs` 暴露

current-head report markdown 已经能展示：

- 文件名
- 页码
- line_group
- pair values
- rule_id
- confidence
- explanation
- recommended_action
- evidence refs

但 `issues.json` 顶层字段本身仍没有把：

- `filename`
- `sheet_no`
- `rationale`

全部显式上提为顶层列。

这更偏报告合同，不是本轮最近切片，但它仍属于“部分实现而非最强形态”。

### 81.4 本轮唯一核心切片与裁决

基于上面的审计，本轮我没有继续追：

- 桌面端
- preview
- issue 总数变化
- 更宽的候选规则

而是只补了一条最近的结构性缺口：

- **把页级分类/路由变成 findings 主表级合同。**

具体体现为：

1. `pages.parquet` 现在直接携带 `page_type / page_subtype / route_target / audit_disposition`
2. `page_findings` 叙述文本现在显式反映 `PageClassifier -> Page Router`
3. second-set fresh rerun 证明这条改动没有破坏现有 route matrix 或 audit 结果：
   - `issue_count` 仍是 `519`
   - `table_pages` 仍是 `0`

### 81.5 当前最接近主链的下一条缺口

完成本轮之后，最近缺口已经不再是：

- “页级分类/路由有没有真的接管”

而更像是：

1. `TableExtractor` 的 real-hit / real-no-hit 证明
2. `issue` JSON 顶层可复核字段是否还要进一步上提

也就是说，当前最该继续优先的仍然是任务书主链里的：

- page/router/table 的真实闭环证明

而不是再转回：

- 桌面承载层
- issue 总量下降
- 候选层大范围调参

## 82. 2026-07-06 `TableExtractor` real-no-hit 证明已显式落盘

在 section 81 之后，我没有继续扩 extractor 或追 issue 数，而是只补一个更窄的 findings 合同：

- 当真实样本当前没有任何表格页命中时
- `findings.json` / `findings.md` 必须把这个结论显式写出来
- 不能再只靠人工去读 `table_pages=0` 自己推断

### 82.1 这轮代码上实际补了什么

代码位置：

- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)

`table_extraction_summary` 现在不再只是：

- `table_pages`
- `three_column_pages`
- `total_mappings`

而是额外带上：

- `status`
- `status_reason`
- `classified_table_pages`
- `classified_table_sheet_ids`
- `classified_table_filenames`
- `table_like_non_routed_pages`

也就是说，current-head 现在能区分三种状态：

1. `table_mappings_recovered`
2. `table_pages_routed_without_mappings`
3. `no_table_pages_detected`

同时 `findings.md` 也新增了 `## Table Extraction` 段，避免这个判断只藏在 JSON 里。

### 82.2 fresh real-sample rerun 现在如何写结论

我直接核对了两套 fresh rerun：

- [phase37_table_no_hit_second findings.json](/F:/workspace/XJToolkit/.tmp/phase37_table_no_hit_second/2_2/findings/findings.json)
- [phase37_table_no_hit_first findings.json](/F:/workspace/XJToolkit/.tmp/phase37_table_no_hit_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/findings.json)

第二套当前写成：

- `status = no_table_pages_detected`
- `status_reason = No page in this run was classified as a table page or routed to TableExtractor.`
- `classified_table_pages = 0`
- `classified_table_filenames = []`
- `table_like_non_routed_pages = []`

第一套当前也写成：

- `status = no_table_pages_detected`
- `classified_table_pages = 0`
- `classified_table_filenames = []`

这说明 current-head 已经能把“真实样本当前没有表格命中”作为稳定合同输出，而不是继续停留在隐式推断。

### 82.3 同时暴露出来的边界

第一套并不是“完全没有任何表格感几何”，因为它还显式保留了：

- `table_like_non_routed_pages = [{sheet_id: S0023, filename: 22 元件接线图2.dwg, page_type: 元件接线图, route_target: ComponentDiagramExtractor}]`

结合这页的 `page_findings` 当前表述，结论更准确地说是：

- 几何上有一页看起来偏 table-heavy
- 但 `PageClassifier` 仍把它收口成 `元件接线图 / horizontal_component`
- route target 仍然是 `ComponentDiagramExtractor`

所以这一轮证明的是：

- **真实样本当前没有任何页被正式分类成表格页，也没有任何页被路由到 `TableExtractor`。**

而不是：

- **真实样本里完全不存在带表格感几何的页面。**

### 82.4 新增测试与稳定性

本轮新增了：

- [test_report_artifacts.py](/F:/workspace/XJToolkit/tests/unit/test_report_artifacts.py) 中的 `no_table_pages_detected` 合同测试
- [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py) 中对 `table_mappings_recovered / classified_table_filenames` 的集成断言

本轮验证结果：

- `python -m pytest -q tests\unit\test_report_artifacts.py -k "no_table_pages_detected or page_classification_fields"` -> `2 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "routes_table_like_page_to_table_extractor_and_emits_table_mapping"` -> `1 passed`
- `python -m pytest -q` -> `175 passed`

### 82.5 当前裁决

到这一轮为止，任务书里关于 `TableExtractor` 的 current-head 说法需要更新成：

1. 已有强证据
- synthetic `analyze-project` 已证明表格页会走 `TableExtractor` 并产出 `table_mapping`
- real-sample findings 已显式证明当前两套样本暂无正式 table hit

2. 仍未完全闭环
- 还没有真实样本 `table_mappings_recovered`
- 第一套仍有 `table_like_non_routed_pages` 边界，说明 `table_like` 几何和最终路由并不等价

所以 current-head 最近的下一条缺口，更像是二选一：

1. 继续收口 `issue` JSON 顶层可复核字段
2. 或专门处理 `table_like_non_routed_pages` 这类“几何像表格、但语义仍应走 component”的解释边界

## 83. 2026-07-06 current-head 任务书完成度审计刷新

这一轮我重新按 [任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 的显式要求做了一次 current-head 审计，不再沿用“文件已经存在”或“历史上做过很多”的叙事，只看当前代码、当前测试和当前真实样本产物。

### 83.1 已有强证据证明完成

1. 真实样本 `analyze-project` 已稳定生成结构化 findings
- 当前两套真实样本都能稳定产出：
  - `findings.json`
  - `findings.md`
  - `pages.parquet`
  - `texts/lines/line_groups/pairs` 等 parquet
- 这满足了任务书第 2、4、5、6、18、20 节里“先形成 findings 运行态，再基于 findings 做后续工作”的主链要求。

2. 页级分类与路由已经在真实样本上真实接管
- current-head 真实样本已能稳定给出每页：
  - `page_type`
  - `page_subtype`
  - `route_target`
  - `audit_disposition`
- second-set current-head 代表页矩阵已明确证明：
  - 普通回路图 -> `WireDiagramExtractor`
  - 元件接线图 -> `ComponentDiagramExtractor`
  - 端子图 -> `TerminalDiagramExtractor`
  - 背板图 -> `LayoutOnlyExtractor`
- 这条现在属于强证据，而不是“文件存在即算完成”。

3. 主链已覆盖普通回路图、元件接线图、端子图
- 真实样本 current-head 已分别证明：
  - 普通回路图进入 `WireDiagramExtractor`
  - 元件接线图进入 `ComponentDiagramExtractor`
  - 端子图进入 `TerminalDiagramExtractor`
- 这满足了任务书第 2、4、20 节对多图种主链覆盖的核心要求。

4. 表格型图“真实样本暂无命中”的证明已成立
- synthetic `analyze-project` 已证明：
  - `TableExtractor` 会被真实路由命中
  - 会产出高置信 `table_mapping`
- 两套真实样本 current-head 又已显式输出：
  - `table_extraction_summary.status = no_table_pages_detected`
- 所以任务书第 4、5、20 节中“表格型图或明确证明样本中暂无该类命中”这一条，当前属于强证据完成。

5. `page_findings` 已不再是默认正式交付物
- current-head 默认把页级 findings 保持在内部运行态 payload 中
- 只有显式调试开关开启时才落盘 `page_findings/*.md|json`
- 这符合任务书第 5.1、5.1.1、6 节的 current-head 要求。

### 83.2 已有部分实现，但还没有达到最强合同

1. `issues.json` 的可复核证据目前仍是“部分强、部分间接”
- 当前顶层已经直接给出：
  - `sheet_id`
  - `file_id`
  - `line_group_id`
  - `left_value`
  - `right_value`
  - `rule_id`
  - `confidence`
  - `evidence_refs`
  - `summary / explanation / recommended_action`
- 但任务书成功定义里要求的人类复核核心字段中，以下几项现在还主要躲在 `evidence` 里：
  - `filename`
  - `sheet_no`
  - `rationale`
- 这意味着 run-audit 的证据合同已经可用，但还不够“顶层即读即用”。

2. per-type extractor 当前更像“路由合同成立”，还不是完全独立的执行栈
- 当前不同图种已经走不同 route target
- 但底层仍共享不少 pair / rule 骨架
- 这不违背 MVP 主链，但说明“不能再依赖单一大脚本解释所有图种”目前更接近部分成立，而不是最强形态。

3. 第一套仍存在 `table_like_non_routed_pages` 的解释边界
- `S0023 / 22 元件接线图2.dwg` 当前几何上偏 table-heavy
- 但语义上仍被收口到 `ComponentDiagramExtractor`
- 这说明 `table_like_geometry` 和最终 `route_target` 当前已被区分开，但这条边界还需要继续解释和稳固。

### 83.3 已明确未完成

1. `issues.json` 顶层可复核字段合同还没有完全收口
- 任务书要求 run-audit 的输出问题项能直接复核：
  - 文件名
  - 页码 / sheet_id
  - line_group_id 或定位锚点
  - 左右值或表格映射值
  - `rule_id`
  - `confidence`
  - `rationale`
  - `evidence refs`
- current-head 唯一最直接的缺口，已经收敛到：
  - `filename`
  - `sheet_no`
  - `rationale`
 还没有成为 `issues.json` 顶层字段。

### 83.4 已偏航但不应继续优先

1. 桌面端、sidecar、preview、Tauri 打包
- 这些承载层工作虽然有价值
- 但当前不再是任务书主链最近缺口
- 继续优先它们，会直接偏离“DWG 审计 MVP 是否已被严格证明”的目标。

2. 继续仅靠调 `candidates.py` 或全局阈值追 issue 数
- 当前最短缺口已经不是“再把 issue 数往下压”
- 而是把主链输出合同补强到足以支持人工复核与验收
- 所以再回到全局阈值堆规则，会属于明显次优先级。

### 83.5 本轮唯一核心切片裁决

基于以上审计，current-head 距离任务书主链最近的 1 个核心切片已经很明确：

- **把 `run-audit` 的 `issues.json` 提升成更强的顶层可复核证据合同。**

原因是：

1. 页级分类 / 路由 / real-sample table no-hit 已经有强证据
2. terminal semantic / continuation 也已经进入显式语义合同
3. 当前最直接卡在任务书成功定义上的，不是新的几何规则，而是 issue 输出字段仍需上提

所以这轮不该优先继续做：

- 桌面端承载层
- 总 issue 数下降
- 更宽的候选规则
- `table_like_non_routed_pages` 的进一步解释美化

而应先补：

- `issues.json` 顶层 `filename / sheet_no / rationale` 等人工复核最短路径字段

## 84. 2026-07-06 `issues.json` 顶层可复核字段合同已补强

在 section 83 做完 current-head 审计后，我没有继续回到几何规则或桌面层，而是只补一条最短主链缺口：

- 让 `run-audit` 产出的 `issues.json` 在顶层直接携带人工复核最常用字段
- 不再要求消费方每次都去 `evidence` 里反查

### 84.1 这轮代码上实际补了什么

代码位置：

- [models.py](/F:/workspace/XJToolkit/src/dwg_audit/domain/models.py)
- [rule_base.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rule_base.py)
- [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py)
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)

`Issue` 顶层现在新增并稳定输出：

- `filename`
- `sheet_no`
- `sheet_order`
- `rationale`

同时 `write_audit_outputs()` 在写 `issues.json / issues.parquet` 前，还会做一次回填：

- 若 issue 本体没显式带这些字段
- 就从 `evidence / evidence_refs` 中自动补回

这意味着：

- rule 层新产出的 issue 会直接带顶层字段
- 老式或手工构造的 issue，只要 evidence 里已有这些值，导出时也不会丢

### 84.2 current-head 真实样本结果

我重新对两套真实样本做了 fresh rerun：

- 第二套：
  - [phase38_issue_contract_second findings](/F:/workspace/XJToolkit/.tmp/phase38_issue_contract_second/2_2/findings/findings.json)
  - [phase38_issue_contract_second issues.json](/F:/workspace/XJToolkit/.tmp/phase38_issue_contract_second/2_2/audit/issues.json)
- 第一套：
  - [phase38_issue_contract_first findings](/F:/workspace/XJToolkit/.tmp/phase38_issue_contract_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/findings.json)
  - [phase38_issue_contract_first issues.json](/F:/workspace/XJToolkit/.tmp/phase38_issue_contract_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/audit/issues.json)

两个 fresh `issues.json` 现在都已经能直接看到：

- `filename`
- `sheet_no`
- `sheet_id`
- `line_group_id`
- `left_value / right_value`
- `rule_id`
- `confidence`
- `rationale`
- `evidence_refs`

代表性的 second-set 顶层样本现在是：

- `filename = 08 测控1开入回路图1.dwg`
- `sheet_no = 08`
- `sheet_id = S0008`
- `line_group_id = G0172`
- `right_value = 127`
- `confidence = 0.4882`
- `rationale = missing left candidate`

这条已经直接满足任务书成功定义里对 issue 可复核证据合同的主干要求。

### 84.3 这轮没有带来行为回退

两套真实样本 fresh rerun 的 issue 总量保持稳定：

- second-set `issue_count = 519`
- first-set `issue_count = 345`

说明这一轮是纯合同增强，而不是通过修改规则触发条件去“换结果”。

### 84.4 新增测试与回归结果

本轮补强了：

- [test_report_artifacts.py](/F:/workspace/XJToolkit/tests/unit/test_report_artifacts.py)
  - 验证 `issues.json` 顶层会出现 `filename / sheet_no / sheet_order / rationale`
- [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)
  - 验证真实 `run-audit` 链产出的 source-conflict issue 现在也带这些顶层字段
- [test_rerun_audit.py](/F:/workspace/XJToolkit/tests/unit/test_rerun_audit.py)
  - 同步更新旧的 `issues.json` 形状断言

验证结果：

- `python -m pytest -q tests\unit\test_report_artifacts.py -k "write_audit_outputs_emits_issue_artifacts_with_evidence_fields"` -> `1 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "source_conflict"` -> `1 passed`
- `python -m pytest -q` -> `175 passed`

### 84.5 并发只读复核结论

并发只读子代理对这轮裁决给出的结论，与主线程一致：

- current-head `issues.json` 之前已经“有证据但不在顶层”
- `filename / sheet_no / rationale` 是最明显的顶层合同缺口
- 相比继续扩几何规则，这条切片更贴近任务书的 run-audit 成功定义

### 84.6 当前裁决

到这一轮为止，任务书第 4 节成功定义中的 issue 证据合同可以更准确地说成：

1. 已有强证据完成
- `filename`
- `sheet_no / sheet_id`
- `line_group_id`
- `left_value / right_value`
- `rule_id`
- `confidence`
- `rationale`
- `evidence_refs`

2. 仍可继续增强但不再是最近硬缺口
- `line_start / line_end` 仍主要留在 `evidence`
- 表格型 issue 未来若出现真实命中，可能还需要更专门的顶层 mapping 字段

所以 current-head 最近的下一条缺口，已经不再是 issue 顶层字段，而更像是：

1. `table_like_non_routed_pages` 这类 page/router 解释边界是否还要更窄收口
2. 或继续证明 per-type extractor 已不再退化为“同一大脚本 + 少量护栏”

## 85. 2026-07-06 per-type extractor 入口已具备真实执行证据

在 section 84 之后，我没有回到几何调参，也没有继续追 issue 数，而是只补一条更贴近任务书主链的结构性缺口：

- `WireDiagramExtractor / ComponentDiagramExtractor / TerminalDiagramExtractor`
- 不能只作为 `route_target` 标签存在
- 必须在 current-head 里变成真实不同的执行入口，并且能被测试和 real-sample findings 一起证明

### 85.1 这轮代码上实际补了什么

代码位置：

- [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py)
- [pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py)
- [models.py](/F:/workspace/XJToolkit/src/dwg_audit/domain/models.py)
- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)
- [line_groups.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/line_groups.py)
- [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py)
- [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py)

current-head 现在新增了四个显式入口：

- `extract_wire_pairs()`
- `extract_component_pairs()`
- `extract_terminal_pairs()`
- `extract_layout_audit_pairs()`

其中前三个是本轮的主目标，第四个只是为了保持旧合同不回退：

- 默认 `LayoutOnlyExtractor` 仍然不是普通审计主链
- 但如果用户显式把背板页纳入 supplemental audit，仍会保留配对证据

pipeline 现在不再把所有 non-table audited pages 一次性喂给同一条共享 pairing 调用，而是：

1. 先按 `route_target` 把 audited pairing 页拆成不同子集
2. 再分别调用对应 extractor 入口
3. 最后把结果汇总回统一 findings / audit 产物

同时 findings 运行态新增：

- 页级 `executed_extractor`
- 页级 `structure_summary.extractor_entry_executed`
- 项目级 `extractor_execution_summary`

这意味着 current-head 已经不再只是“分类说你应该去哪”，而是能回答“这页实际上去了哪条执行入口”。

### 85.2 中途撞到的真实回归与修复

这轮第一版 fresh rerun 并不稳定：

- second-set `issue_count` 一度从 `519` 漂到 `606`
- first-set `issue_count` 一度从 `345` 漂到 `374`

新增问题主要表现为：

- `R-DUPLICATE-SAME-LINE` 异常增多

根因不是路由判定错了，而是：

- 分路后每条子链都各自从 `G0001 / C0001 / PC0001 / P0001` 重新编号
- 导致同一项目内不同 extractor 产物发生 ID 碰撞
- 进而让 rule 层把不相干实体误当成同一条线或同一个 pair 关系

修复方式是最小而直接的：

- 给 `build_line_groups()`
- `build_terminal_candidates()`
- `build_pairs()`

增加可注入 `IdFactory`

再由不同 extractor 入口传入 route-scoped 唯一前缀，例如：

- wire
- component
- terminal
- layout fallback

修完后，两套真实样本 fresh rerun 都回到了原稳定基线。

### 85.3 新增测试证据

本轮最关键的新增集成测试是：

- [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)
  - `test_analyze_project_executes_route_specific_pair_extractors`

它直接 monkeypatch 了 pipeline 中导入的三个 extractor 入口，证明：

- `04 回路图.dwg` 真实调用了 `extract_wire_pairs`
- `19 元件接线图1.dwg` 真实调用了 `extract_component_pairs`
- `21 左侧端子图1.dwg` 真实调用了 `extract_terminal_pairs`

同时它还断言 findings payload 里会直接出现：

- `executed_extractor = WireDiagramExtractor`
- `executed_extractor = ComponentDiagramExtractor`
- `executed_extractor = TerminalDiagramExtractor`

另外，本轮还顺手保住了旧合同：

- `test_analyze_project_can_include_backplate_pages_as_supplemental_audit`

没有因为分路而回退。

验证结果：

- `python -m pytest -q tests\integration\test_analyze_project.py -k "route_specific_pair_extractors or backplate_pages_as_supplemental_audit"` -> `2 passed`
- `python -m pytest -q` -> `176 passed`

### 85.4 current-head 真实样本结果

我重新对两套真实样本做了 fresh rerun：

- 第二套：
  - [phase40_route_extractors_second findings](/F:/workspace/XJToolkit/.tmp/phase40_route_extractors_second/2_2/findings/findings.json)
  - [phase40_route_extractors_second issues.json](/F:/workspace/XJToolkit/.tmp/phase40_route_extractors_second/2_2/audit/issues.json)
- 第一套：
  - [phase40_route_extractors_first findings](/F:/workspace/XJToolkit/.tmp/phase40_route_extractors_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/findings.json)
  - [phase40_route_extractors_first issues.json](/F:/workspace/XJToolkit/.tmp/phase40_route_extractors_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/audit/issues.json)

第二套 current-head 现在直接给出：

- `issue_count = 519`
- `extractor_execution_summary.executed_extractor_count = 3`
- `WireDiagramExtractor.page_count = 13`
- `ComponentDiagramExtractor.page_count = 2`
- `TerminalDiagramExtractor.page_count = 4`

代表页：

- `04 交流回路图1.dwg -> executed_extractor = WireDiagramExtractor`
- `19 元件接线图1.dwg -> executed_extractor = ComponentDiagramExtractor`
- `21 左侧端子图1.dwg -> executed_extractor = TerminalDiagramExtractor`
- `17 测控1装置背板.dwg -> executed_extractor = null`

第一套 current-head 现在直接给出：

- `issue_count = 345`
- `extractor_execution_summary.executed_extractor_count = 3`
- `WireDiagramExtractor.page_count = 13`
- `ComponentDiagramExtractor.page_count = 3`
- `TerminalDiagramExtractor.page_count = 4`

代表页：

- `04 交流回路图1.dwg -> executed_extractor = WireDiagramExtractor`
- `21 元件接线图1.dwg -> executed_extractor = ComponentDiagramExtractor`
- `24 左侧端子图1.dwg -> executed_extractor = TerminalDiagramExtractor`
- `17 差动保护背板图.dwg -> executed_extractor = null`

这说明 current-head 已经具备三层同时成立的证据：

1. route label 不同
2. pipeline 调用入口不同
3. fresh real-sample findings 里可直接看到执行摘要

### 85.5 当前裁决

到这一轮为止，关于任务书里“不能继续依赖同一大脚本解释所有页型”的说法，current-head 更准确的表述应该更新成：

1. 已有强证据完成
- Wire / Component / Terminal audited pages 已经真实经过不同 extractor 入口
- current-head findings 已显式记录 `executed_extractor`
- 两套 fresh rerun 保持 `issue_count` 稳定：
  - second-set `519`
  - first-set `345`

2. 仍不是最强形态
- 这些入口内部仍共享不少底层 line-group / candidate / pair 骨架
- `LayoutOnlyExtractor` 和 `TableExtractor` 的执行证据合同还没有做到完全同层级细化

所以 current-head 最近的下一条缺口，更像是：

1. `table_like_non_routed_pages` 的解释边界是否还要继续收口
2. 或把 `LayoutOnly / Table` 的执行证据也继续提升到与 Wire / Component / Terminal 同级的可见合同

## 86. 2026-07-06 全 route execution contract 已显式落盘

在 section 85 之后，我重新按 [任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 做了一次 current-head 审计，不再默认延续“现在已经很接近”的叙事。

### 86.1 重新审计后的 current-head 完成度判断

1. 已有强证据完成

- 每页 current-head 已有稳定：
  - `page_type`
  - `route_target`
  - `audit_disposition`
- `Wire / Component / Terminal` 已有真实不同 extractor 入口、测试调用证据和 fresh real-sample 执行摘要。
- `TableExtractor` 已有：
  - synthetic hit 证明
  - real-sample explicit no-hit 证明
- `issues.json` 顶层可复核字段已能直接满足任务书主干要求。

2. 仍属部分实现但不够对称

- 虽然 `Table / LayoutOnly / Skip` 的 route target 本身早就存在
- 但它们之前还没有和 `Wire / Component / Terminal` 一样，处在同一层级的执行状态合同里
- 例如：
  - 背板页为什么没有 pair
  - 封面为什么没有执行 extractor
  - 当前样本为什么 `TableExtractor` 是零页
  这些还主要靠人工从多个字段间接反推

基于这个审计，本轮唯一合理的单一切片不是继续调几何，也不是继续解释 `table_like_non_routed_pages`，而是：

- **把六类 canonical route target 的执行或明确未执行状态，统一提升成 findings 合同。**

### 86.2 这轮代码上实际补了什么

代码位置：

- [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py)

current-head 现在新增了两个关键合同：

1. 页级 `execution_status`

每页除了：

- `route_target`
- `executed_extractor`

之外，还显式携带：

- `execution_status`

当前最重要的状态是：

- `executed`
- `classify_only`
- `skipped`

这样背板页和封面页不再只是 `executed_extractor = null`，而是明确写出：

- 这页被故意 classify-only
- 这页被故意 skip

2. 项目级 `route_execution_summary`

`findings.json` 现在新增：

- `route_execution_summary.route_targets`

它不只覆盖已经执行过的 route，而是对所有 canonical route target 都显式给出：

- `status`
- `status_reason`
- `routed_page_count`
- `executed_page_count`
- `routed_sheet_ids`
- `routed_filenames`
- `routed_audit_disposition_counts`
- `pair_count / line_group_count / table_mapping_count`

也就是说，current-head 现在能明确区分：

- `executed`
- `no_pages_classified`
- `classify_only_pages_present`
- `skip_pages_present`

### 86.3 新增测试证据

这轮没有继续扩新的算法测试，而是补合同级证据：

- [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)

补强了三类场景：

1. table hit 场景
- `TableExtractor` 现在不仅有 `table_mapping`
- 还要求 `route_execution_summary.TableExtractor.status == executed`

2. supplemental + skip 场景
- `SkipExtractor` 现在要求显式输出 `skip_pages_present`
- `TableExtractor` 在无命中时要求显式输出 `no_pages_classified`

3. backplate supplemental fallback 场景
- 当背板页被显式纳入 supplemental audit 时
- `LayoutOnlyExtractor` 现在要求显式输出：
  - `status = executed`
  - `executed_extractor = LayoutOnlyAuditFallback`

验证结果：

- `python -m pytest -q tests\integration\test_analyze_project.py -k "routes_table_like_page_to_table_extractor_and_emits_table_mapping or includes_supplemental_pages_in_downstream_audit or can_include_backplate_pages_as_supplemental_audit"` -> `3 passed`
- `python -m pytest -q` -> `176 passed`

### 86.4 current-head 真实样本结果

我重新对两套真实样本做了 fresh rerun：

- 第二套：
  - [phase41_route_contract_second findings](/F:/workspace/XJToolkit/.tmp/phase41_route_contract_second/2_2/findings/findings.json)
  - [phase41_route_contract_second issues.json](/F:/workspace/XJToolkit/.tmp/phase41_route_contract_second/2_2/audit/issues.json)
- 第一套：
  - [phase41_route_contract_first findings](/F:/workspace/XJToolkit/.tmp/phase41_route_contract_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/findings.json)
  - [phase41_route_contract_first issues.json](/F:/workspace/XJToolkit/.tmp/phase41_route_contract_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/audit/issues.json)

第二套 current-head 现在直接写出：

- `issue_count = 519`
- `route_status`：
  - `WireDiagramExtractor = executed`
  - `ComponentDiagramExtractor = executed`
  - `TerminalDiagramExtractor = executed`
  - `TableExtractor = no_pages_classified`
  - `LayoutOnlyExtractor = classify_only_pages_present`
  - `SkipExtractor = skip_pages_present`

同时代表页也不再是“只能靠 null 猜原因”：

- `17 测控1装置背板.dwg`
  - `route_target = LayoutOnlyExtractor`
  - `executed_extractor = null`
  - `execution_status = classify_only`
- `01 封面.dwg`
  - `route_target = SkipExtractor`
  - `executed_extractor = null`
  - `execution_status = skipped`

第一套 current-head 同样稳定：

- `issue_count = 345`
- `route_status` 与第二套一致：
  - `Wire / Component / Terminal = executed`
  - `Table = no_pages_classified`
  - `LayoutOnly = classify_only_pages_present`
  - `Skip = skip_pages_present`

### 86.5 当前裁决

到这一轮为止，关于任务书第 4/5/20 节的 current-head 说法，应该进一步更新成：

1. 已有强证据完成

- 每页 current-head 有：
  - `page_type`
  - `route_target`
  - `audit_disposition`
- 普通回路图、元件接线图、端子图都已真实执行不同 extractor 入口
- 表格页当前真实样本暂无命中，且这一点现在已被 route-level 合同显式写为 `no_pages_classified`
- 背板页和非审计页现在也不再只是“没有后续产物”，而是显式写明：
  - `classify_only`
  - `skipped`

2. 仍未完全闭环

- `table_like_non_routed_pages` 仍是一条可继续收口的解释边界
- 任务书第 19 节“真实正确样本 + 故障注入样本”的最小验收，虽然资产和脚手架已有很多，但还值得再按 current-head 刷新一次更强裁决

所以 current-head 最近下一条缺口，更像是二选一：

1. 继续收口 `table_like_non_routed_pages`
2. 回到任务书第 19 节，刷新最小验收闭环证明，而不是继续扩更多零散功能

## 87. 2026-07-06 第 19 节最小验收闭环已补成 current-head suite proof

在 section 86 之后，我没有继续扩更多产品命令，也没有回去追桌面端表层功能，而是只补任务书第 19 节最近的一条证明缺口：

- 把“真实正确样本 + 隔离故障注入样本”的最小验收
- 收口成一个 current-head 可重复执行的内部 acceptance suite harness

### 87.1 这轮代码上实际补了什么

代码位置：

- [acceptance.py](/F:/workspace/XJToolkit/src/dwg_audit/report/acceptance.py)
- [__init__.py](/F:/workspace/XJToolkit/src/dwg_audit/report/__init__.py)
- [cli.py](/F:/workspace/XJToolkit/src/dwg_audit/cli.py)
- [test_acceptance_evaluation.py](/F:/workspace/XJToolkit/tests/integration/test_acceptance_evaluation.py)
- [mvp_minimum_suite.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_suite/mvp_minimum_suite.json)

current-head 现在新增了：

- `evaluate_acceptance_suite()`
- `write_acceptance_suite_report()`
- 内部命令 `evaluate-acceptance-suite`

这条命令的定位需要明确写死：

- 它是内部验收 harness
- 用于证明 MVP 在真实样本子集和故障注入样本上都能稳定跑通
- 它不是产品主界面
- 它不构成“继续扩 CLI surface” 的方向许可

### 87.2 suite 资产与 current-head 覆盖面

当前最小 suite 固定为 3 个 required case：

- `fault_injected_acceptance_mini`
- `real_second_component_terminal_subset`
- `real_second_terminal_s0024`

对应资产分别来自：

- [acceptance_mini spec](/F:/workspace/XJToolkit/tests/fixtures/acceptance_mini/spec.json)
- [second_set_component_terminal_subset](/F:/workspace/XJToolkit/tests/fixtures/acceptance_real_subset/second_set_component_terminal_subset.json)
- [second_set_terminal_s0024](/F:/workspace/XJToolkit/tests/fixtures/acceptance_real_subset/second_set_terminal_s0024.json)
- [mvp_minimum_suite.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_suite/mvp_minimum_suite.json)

这意味着 current-head 的第 19 节证明现在不再只靠：

- 单个 acceptance case
- 或零散的 real-sample rerun 描述

而是由一个 suite 把 synthetic fault injection 与 real-correct subset 明确绑在一起。

### 87.3 current-head 验证结果

本轮定向与全量验证结果：

- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `4 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "route_specific_pair_extractors or routes_table_like_page_to_table_extractor_and_emits_table_mapping"` -> `2 passed`
- `python -m pytest -q` -> `177 passed`

current-head suite 运行产物位于：

- [phase42_acceptance_suite report](/F:/workspace/XJToolkit/.tmp/phase42_acceptance_suite/acceptance_suite_report.json)
- [phase42_real_subset_component_terminal report](/F:/workspace/XJToolkit/.tmp/phase42_real_subset_component_terminal/acceptance_report.json)
- [phase42_acceptance_mini project](/F:/workspace/XJToolkit/.tmp/phase42_acceptance_mini/project)

suite 当前结果直接为：

- `acceptance_passed = true`
- `required_passed_case_count = 3`
- `required_case_count = 3`

分 case 结果为：

- `fault_injected_acceptance_mini` -> `16 / 16`, `precision = 1.0`, `recall = 1.0`
- `real_second_component_terminal_subset` -> `13 / 13`, `precision = 1.0`, `recall = 1.0`
- `real_second_terminal_s0024` -> `7 / 7`, `precision = 1.0`, `recall = 1.0`

### 87.4 这轮裁决

到这一轮为止，任务书第 19 节更准确的 current-head 说法应该更新成：

1. 已有强证据完成

- 最小验收不再只靠单个 case 或人工叙述
- synthetic fault-injected mini case 已纳入 suite
- real-correct second-set subset 已纳入 suite
- suite 当前可以稳定导出 json / markdown 验收报告

2. 必须显式约束的边界

- `evaluate-acceptance-suite` 只是内部验收入口
- 后续不得把它当成继续扩产品 CLI 的理由
- 产品主链应转回 exe 可调用的单一执行入口，而不是继续把能力拆成更多 `dwg-audit xxx`

3. 最近下一条缺口

- 不是继续扩 acceptance CLI
- 而是把当前分析/审计主链进一步收敛为 service/session API
- 让 CLI 与 exe 复用同一条执行入口

## 88. 2026-07-06 CLI / sidecar / UI 已收敛到单一执行入口

在 section 87 和用户补充边界之后，本轮没有继续新增 `dwg-audit xxx` 产品能力，而是把现有主执行链往 exe 可调用入口收敛。

### 88.1 这轮代码上实际补了什么

新增统一执行服务：

- [execution.py](/F:/workspace/XJToolkit/src/dwg_audit/services/execution.py)
- [__init__.py](/F:/workspace/XJToolkit/src/dwg_audit/services/__init__.py)

`run_analysis_workflow()` 现在集中负责：

- 输入目录与配置路径校验
- 输出目录创建
- `load_config`
- `configure_logging`
- `analyze_input_root`
- 可选 `rerun_audit_from_findings`
- 返回 `AnalysisRunResult`

三条旧入口现在改为调用同一层：

- [cli.py](/F:/workspace/XJToolkit/src/dwg_audit/cli.py)
- [sidecar.py](/F:/workspace/XJToolkit/src/dwg_audit/desktop/sidecar.py)
- [actions.py](/F:/workspace/XJToolkit/src/dwg_audit/ui/actions.py)

这意味着 current-head 的方向已经从“继续堆 CLI 命令”转成：

- CLI 是薄包装
- Streamlit 内部 UI 是薄包装
- Tauri sidecar / exe worker 也调用同一条 service 入口

### 88.2 事件与桌面端约束

为了避免抽 service 后削弱桌面端过程页，本轮保留了 `project_artifacts_ready` 时机：

- `run_analysis_workflow()` 支持 `on_project_artifacts_ready`
- `desktop.sidecar.analyze_session()` 通过回调继续在 audit 前发 `project_artifacts_ready`
- `event_sink` 继续透传给 analyze 与 audit 阶段

所以这轮不是把桌面端事件流藏进 CLI，而是把 exe 需要的执行语义下沉到 service。

### 88.3 验证结果

定向验证：

- `python -m pytest -q tests\unit\test_execution_service.py tests\unit\test_ui_actions.py tests\unit\test_sidecar.py` -> `10 passed`
- `python -m pytest -q tests\unit\test_cli.py -k "analyze_session or help_lists_taskbook_commands"` -> `2 passed`

全量验证：

- `python -m pytest -q` -> `179 passed`

真实第二套样本 exe-near session 验证：

- 命令路径：`analyze-session`
- 输入：`test\变压器测控柜(2圈变，2台测控)`
- 输出：[phase43_service_session_abs](/F:/workspace/XJToolkit/.tmp/phase43_service_session_abs)
- 状态库：[desktop_state.db](/F:/workspace/XJToolkit/.tmp/phase43_service_session_abs/desktop_state.db)

结果：

- `sheet_count = 24`
- `pair_count = 1211`
- `issue_count = 519`
- `project_artifacts_ready` 仍出现在 audit 前
- state store 能通过 `list-recent-projects` 读回项目结果

route status 仍稳定为：

- `WireDiagramExtractor = executed`
- `ComponentDiagramExtractor = executed`
- `TerminalDiagramExtractor = executed`
- `TableExtractor = no_pages_classified`
- `LayoutOnlyExtractor = classify_only_pages_present`
- `SkipExtractor = skip_pages_present`

### 88.4 当前裁决

这轮完成的是第一层收敛：

- 共同执行链已经有了 service 入口
- CLI / UI / sidecar 不再各自拼核心分析流程
- exe worker 后续可以直接复用 `run_analysis_workflow()`

仍未完全闭环的是第二层：

- desktop sidecar 仍负责状态落库、结果加载、预览、issue 状态更新
- 这些还没有统一成一个完整的 `SessionService`
- 终端 JSONL 输出里的中文在当前控制台仍有 mojibake 显示风险，但状态库与文件产物保持正常 UTF-8

所以最近下一条缺口已经不是继续抽 `analyze-project`，而是：

- 把桌面端 session orchestration 继续整理成 exe worker 更稳定消费的 service boundary
- 同时处理 JSONL 事件输出编码显示风险

## 89. 2026-07-06 任务书新增页型 current-head 审计：背板表格型与组件前缀信号回路

本轮按任务书最新要求重新审计 current-head，不再默认把下一步放在 CLI / desktop service 扩展上，而是回到真实 DWG 主链。fresh 产物来自：

- [phase44 first set](/F:/workspace/XJToolkit/.tmp/phase44_taskbook_audit_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- [phase44 second set](/F:/workspace/XJToolkit/.tmp/phase44_taskbook_audit_second/2_2)

### 89.1 强证据

两套样本均已完成 analyze + audit。第一套目标页的 current-head 分类如下：

- `16 高低压侧操作箱信号回路.dwg`
  - `sheet_id = S0017`
  - `page_type = 二次原理图`
  - `page_subtype = grid_heavy_wire_diagram`
  - `route_target = WireDiagramExtractor`
  - `audit_disposition = audit_required`
  - `pair_count = 28`
- `20 非电量保护背板图.dwg`
  - `sheet_id = S0021`
  - `page_type = 背板接线图`
  - `route_target = LayoutOnlyExtractor`
  - `audit_disposition = classify_only`
  - `pair_count = 0`

### 89.2 未完成或偏航

`20 非电量保护背板图.dwg` 是当前最硬的 MVP 主链缺口。任务书要求背板图中结构化插件/端子表不能被跳过，但 current-head 把该页直接留在 `LayoutOnlyExtractor / classify_only`，没有进入 `TableExtractor`，也没有产生 `table_mapping`。

该页真实文本已经包含表格型信号：

- 端点文本：`5FD15`、`5YD15`、`5KLP8-2` 等
- 插件/块标识文本：`WBH-814E-E1SA-101`
- 插件页/前缀文本：`5n`
- 图面结构：大量水平行带和按列排布的端点文本，但缺少传统竖向网格线

所以问题不是单纯 TableExtractor 三列表格不够强，而是两层同时缺：

- 分类/路由层没有把“背板接线图 + 结构化端点表”升级为可审计表格型页
- 表格抽取层目前偏向“有竖线/多段线网格”的三列表格，不理解这种“无竖线、行带 + 文本列 + 底部插件标识”的背板表

`16 高低压侧操作箱信号回路.dwg` 是第二个缺口。它已经进入 `WireDiagramExtractor`，但 current-head 只生成 review 级普通 pair；任务书示例要求识别类似 `1-2n218 -> 1-4YD1` 的组件前缀信号回路映射。该页文本中已经存在 `1-2n`、`3-2n`、`218`、`1-4YD1`，但当前 pair 仍停在局部数字候选层。

### 89.3 最近唯一切片裁决

最近一刀应先做 `20 非电量保护背板图.dwg` 的背板表格型闭环，而不是继续扩 CLI 或先做 `16` 的前缀信号回路。

理由：

- `20` 当前是 0 pair / classify-only，和任务书新增硬要求直接冲突
- 该页可以通过窄规则验证：路由到 `TableExtractor`，产出 `table_mapping`，并至少证明 `WBH-814E-E1SA-101` / `5n` / `5FD15` 这一类结构被理解
- `16` 已经进入审计链，只是语义拼接不足；风险低于 `20` 这种整页被跳过

本轮开发边界：

- 不把所有背板图粗暴纳入普通线组审计
- 不继续扩产品 CLI
- 只补背板表格型页的分类信号与专用表格映射能力

## 90. 2026-07-06 背板表格型页已闭环到 TableExtractor

本轮按 section 89 的裁决完成了背板表格型最小闭环，没有继续扩 CLI surface。核心变化是：

- 背板接线图现在允许展开必要的 `INSERT.virtual_entities()`
- PageClassifier 会把“背板 + 块内表头/行号 + 外侧端点”的页面升级为 `背板表格型图`
- Page Router 仍保持 `route_target = TableExtractor`，不新增产品命令或新 route 字面量
- TableExtractor 新增 `backplate_virtual_table` 映射模式，复用现有 `table_mapping` pair/evidence 合同

### 90.1 第一套真实样本验证

最终实跑产物：

- [phase46_backplate_first](/F:/workspace/XJToolkit/.tmp/phase46_backplate_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

关键页 `20 非电量保护背板图.dwg` 当前结果：

- `page_type = 背板表格型图`
- `page_subtype = backplate_virtual_terminal_table`
- `route_target = TableExtractor`
- `execution_status = executed`
- `text_count = 406`
- `table_mapping_count = 51`
- `table_mapping_modes = {"backplate_virtual_table": 51}`
- `table_header_prefixes = ["NDY306A", "NKR308A", "NTZ302A"]`

任务书点名样例已经命中：

- `NKR308A(非电量选配)` 被规范化为 `NKR308A`
- 行号 `01` 被规范化为端口序号 `1`
- 外侧端点 `5FD15` 被同 y 行锁定
- 输出 pair：`NKR308A-1 -> 5FD15`
- pair 状态：`pass`
- confidence：`0.95`
- evidence source：`table_mapping`
- rationale：`Backplate virtual table mapping: normalized block header plus row number associated with external terminal endpoint.`

第一套背板页现在整体路由为：

- `17 差动保护背板图.dwg -> 背板表格型图 / backplate_virtual_terminal_table / TableExtractor`
- `18 高后备保护背板图.dwg -> 背板表格型图 / backplate_geometric_table / TableExtractor`
- `19 低后备保护背板图.dwg -> 背板表格型图 / backplate_geometric_table / TableExtractor`
- `20 非电量保护背板图.dwg -> 背板表格型图 / backplate_virtual_terminal_table / TableExtractor`

第一套最终 audit issue 总量为 `370`。

### 90.2 第二套真实样本防误伤验证

最终实跑产物：

- [phase46_backplate_second](/F:/workspace/XJToolkit/.tmp/phase46_backplate_second/2_2)

第二套结果保持稳定：

- `sheet_count = 24`
- `pair_count = 1211`
- `issue_count = 519`
- `17 测控1装置背板.dwg -> 背板接线图 / LayoutOnlyExtractor / classify_only`
- `18 测控2装置背板.dwg -> 背板接线图 / LayoutOnlyExtractor / classify_only`
- `table_extraction_summary.status = no_table_pages_detected`

这说明本轮规则没有把普通测控背板页误拉进 `TableExtractor`。

### 90.3 测试与并发复核

新增/更新测试覆盖：

- `tests/unit/test_page_classifier.py`
- `tests/unit/test_table_extractor.py`
- `tests/integration/test_analyze_project.py`

验证结果：

- `python -m pytest -q tests\unit\test_page_classifier.py tests\unit\test_table_extractor.py` -> `19 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "backplate_virtual_table or header_semantic_three_column_table_mapping or routes_table_like_page_to_table_extractor_and_emits_table_mapping"` -> `3 passed`
- `python -m pytest -q` -> `182 passed`

并发子代理只读复核结论已吸收：

- 最小规则必须限定在 `sheet_category == 背板接线图`，避免误伤元件接线图、普通二次原理图、屏端子图
- 不应发明新的 route 字面量，必须继续使用 `TableExtractor`
- 新 mapping mode 必须显式接入 pair builder，否则会出现 findings 有 mapping 但 rules 没 pair 的半闭环

### 90.4 下一刀

背板表格型页的 MVP 主链已经从 `classify_only / 0 pair` 进入 `TableExtractor / table_mapping`。下一条最近主链缺口应转向：

- `16 高低压侧操作箱信号回路.dwg`
- 子模式：`component_prefixed_signal_circuit`
- 目标映射：`1-2n218 -> 1-4YD1`

这仍然是 DWG 审计主链，不是 CLI 扩张。

## 91. 2026-07-06 元件分区型普通回路图已输出 wire_component_mapping

在背板表格型闭环之后，本轮继续补任务书中点名的 `16 高低压侧操作箱信号回路.dwg`。该页仍保持：

- `page_type = 二次原理图`
- `page_subtype = grid_heavy_wire_diagram`
- `route_target = WireDiagramExtractor`

没有把它改路由到 ComponentDiagramExtractor 或 TableExtractor；新增能力是 WireDiagramExtractor 内的结构化附加信源。

### 91.1 实现策略

新增模块：

- [wire_components.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/wire_components.py)

该模块识别 `component_prefixed_signal_circuit` 子模式：

- 组件分区前缀：`1-2n`、`3-2n`
- 分区内局部三位数：如 `218`、`221`
- 同 y 外侧端点：如 `1-4YD1`、`1-4YD4`
- 输出逻辑端：`前缀 + 局部号`
- 输出 pair_kind：`wire_component_mapping`
- 输出 evidence source：`wire_component_mapping`

该逻辑在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 中只接入 `WireDiagramExtractor`，不改变普通候选排名。

### 91.2 第一套真实样本验证

最终实跑产物：

- [phase47_component_first](/F:/workspace/XJToolkit/.tmp/phase47_component_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

目标页 `16 高低压侧操作箱信号回路.dwg` 当前结果：

- `pair_count = 54`
- `ordinary_pair = 28`
- `wire_component_mapping = 26`
- `high_confidence_pair_count = 26`

任务书点名样例已经命中：

- `left_value = 1-2n218`
- `right_value = 1-4YD1`
- `status = pass`
- `confidence = 0.95`
- `pair_kind = wire_component_mapping`
- `evidence.source = wire_component_mapping`
- `component_submode = component_prefixed_signal_circuit`
- evidence 保留 prefix 文本、local number 文本、external endpoint 文本、坐标与 component bbox

同页还恢复了同模式映射，例如：

- `1-2n221 -> 1-4YD4`
- `3-2n218 -> 3-4YD1`
- `3-2n221 -> 3-4YD4`

背板表格型闭环未回退：

- `20 非电量保护背板图.dwg` 仍保持 `背板表格型图 / backplate_virtual_terminal_table / TableExtractor`
- `NKR308A-1 -> 5FD15` 仍存在

第一套最终 audit issue 总量仍为 `370`。

### 91.3 第二套真实样本防误伤验证

最终实跑产物：

- [phase47_component_second](/F:/workspace/XJToolkit/.tmp/phase47_component_second/2_2)

第二套保持稳定：

- `sheet_count = 24`
- `pair_count = 1211`
- `issue_count = 519`
- `wire_component_mapping = 0`
- `17/18 测控装置背板` 仍保持 `LayoutOnlyExtractor / classify_only`

这说明 `component_prefixed_signal_circuit` 规则没有误吸普通测控回路或普通背板页。

### 91.4 测试结果

新增/更新测试：

- [test_wire_components.py](/F:/workspace/XJToolkit/tests/unit/test_wire_components.py)
- [test_analyze_project.py](/F:/workspace/XJToolkit/tests/integration/test_analyze_project.py)

验证结果：

- `python -m pytest -q tests\unit\test_wire_components.py tests\integration\test_analyze_project.py -k "component_prefixed_signal_circuit or backplate_virtual_table"` -> `2 passed`
- `python -m pytest -q` -> `184 passed`

### 91.5 下一刀

任务书中普通回路图的另一个结构化子模式还未闭环：

- 线中元件端口型回路
- 目标形态：`3-2KLP1-1 -> 3-2QD2`、`3-2KLP1-2 -> 3-2n116`

下一步应继续沿用“结构化 pair_kind + evidence.source”的路线，而不是回到裸数字候选排名。

## 92. 2026-07-06 Issue root-cause audit 已接入 post-audit 主链

用户最新闭环要求把 `issue_count` 视为“症状集合”，先做归因而不是先降噪。本轮新增了 post-audit 诊断层：

- 给每条 issue 补 `root_cause`
- 补 `root_cause_confidence`
- 补 `root_cause_rationale`
- 补 `diagnostic_tags`
- 补 `diagnostic_context`
- 输出聚合产物 `audit/issue_root_cause_audit.json`
- 输出可读产物 `audit/issue_root_cause_audit.md`

首版 root-cause 分类与用户建议保持一致：

- `page_misclassified`
- `extractor_missing`
- `candidate_noise`
- `pairing_wrong`
- `relationship_missing`
- `rule_too_strict`
- `insufficient_evidence`

这层只解释症状，不改变规则引擎结果，也不直接压低 issue 数量。

### 92.1 第二套真实样本诊断结果

复用现有 findings，只重跑 audit：

- [phase47_component_second](/F:/workspace/XJToolkit/.tmp/phase47_component_second/2_2)

结果：

- `issue_count = 519`
- `candidate_noise = 33`
- `extractor_missing = 24`
- `insufficient_evidence = 287`
- `pairing_wrong = 174`
- `rule_too_strict = 1`

按页看，最强信号是：

- `08 测控1开入回路图1.dwg`: `47/49` 为 `pairing_wrong`
- `09 测控1开入回路图2.dwg`: `43/43` 为 `pairing_wrong`
- `12 测控2开入回路图1.dwg`: `41/48` 为 `pairing_wrong`
- `13 测控2开入回路图2.dwg`: `43/43` 为 `pairing_wrong`
- `20 元件接线图2.dwg`: `24/24` 为 `extractor_missing`
- `21/23` 端子图仍以 `insufficient_evidence` 为主，说明当前字段还不足以自动确认真实语义

这说明第二套的最大显性症状不是“规则太多”，而是两类工程缺口：

- 网格化开入回路里的 inline 数字断线 / 半链组合问题
- 元件接线图中专用 `component_mapping` 仍缺失

### 92.2 第一套真实样本诊断结果

复用现有 findings，只重跑 audit：

- [phase47_component_first](/F:/workspace/XJToolkit/.tmp/phase47_component_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)

结果：

- `issue_count = 370`
- `candidate_noise = 68`
- `extractor_missing = 68`
- `insufficient_evidence = 199`
- `pairing_wrong = 35`

第一套 top pages 显示：

- `24 左侧端子图1.dwg`: `43` issues，其中 `candidate_noise = 20`
- `22 元件接线图2.dwg`: `30` issues，全部为 `extractor_missing`
- `11 非电量开入回路.dwg`: `28` issues，其中 `pairing_wrong = 14`

第一套与第二套共同确认：元件接线图的下一步不应继续靠 ordinary pair 调分，而应继续补 `ComponentDiagramExtractor` 的结构化 mapping。

### 92.3 下一刀裁决

短期优先级从“看总 issue 数”改为“按 root_cause 最大桶处理”：

- 第一优先：`pairing_wrong`，尤其第二套 `08/09/12/13` 的 inline wire split。这里适合继续做 line chain 合并或把 complementary half-pair 从 issue 转成 review evidence。
- 第二优先：`extractor_missing`，尤其两套的 `元件接线图2`。这里应补 component 专用 mapping，而不是让普通 pair 报低置信。
- 第三优先：`insufficient_evidence`。这里不是马上写规则，而是补更细的候选/规则 cause hints，或等待人工语义反馈。

因此 Phase 40 的线中元件端口型回路仍是任务书主链缺口，但在当前用户闭环下，下一轮更稳的入口应先用 root-cause 聚合选择最大的症状类，不再凭 issue_count 直觉行动。

## 93. 2026-07-06 任务书完成度复审：表头型端子/表格页是最近主链缺口

本轮重新以当前 `doc/任务书.md` 为准，不用历史实现存在性冒充完成。任务书当前明确要求：

- 表格型图第一版重点支持“表头型三列表格”
- 表头前缀如 `1-21QD` 与中列行号 `1` 应合成 `1-21QD1`
- 同行左右接线端如 `1-21n116` 应生成高置信 `table_mapping`
- 中间列行号本身不能降级为普通端点近邻候选
- 端子图主信源应是行锁定、列角色、代号和同行对应关系，不应继续只套普通导线端点逻辑

### 93.1 当前强证据已完成

- 页级分类/路由结果已经进入 `pages.parquet`：第二套 `S0023 / 23 右侧端子图1.dwg` 当前可直接看到 `page_type=屏端子图`、`route_target=TerminalDiagramExtractor`、`audit_disposition=audit_required`。
- `TableExtractor` 已有 synthetic 表头三列表格骨架，也已能对第一套背板表格型真实页输出 `NKR308A-1 -> 5FD15`。
- `issues.json/parquet` 已有可复核字段和上一轮 root-cause 诊断字段。

### 93.2 当前未完成或证据不足

- 第二套真实 `S0023 / 23 右侧端子图1.dwg` 中，真实文本已存在：
  - `1-21QD` at approximately `(175.49, 276.0)`
  - row number `1` at approximately `(179.25, 268.5)`
  - `1-21n116` at approximately `(156.0, 268.5)`
- 但该页当前没有 `1-21QD1 -> 1-21n116` 这类 `table_mapping`。
- 当前 pairs 中可见 ordinary symptom：`116 -> 1`，说明行号仍在裸进入 PairBuilder。
- 该页不是传统三列表格网格页；它是端子页内部的“表头型列角色区域”。如果整页改路由为纯 `TableExtractor`，会误伤端子页其它区域；如果完全留在 `TerminalDiagramExtractor`，则表头映射永远不会进入 table path。

### 93.3 本轮唯一核心切片

本轮只做 `terminal_header_table` supplemental table extraction：

- 页面仍保持 `TerminalDiagramExtractor` 主路由，不把整页抢成纯表格页。
- 在 terminal extractor 中识别同页清晰的 `header prefix + row number + same-row terminal endpoint` 区域。
- 追加高置信 `table_mapping` pair，例如 `1-21QD1 -> 1-21n116`。
- findings 的 `table_extraction_summary` 和页级结构摘要必须能看到这批真实样本表头映射。
- 不在本轮重写端子页 ordinary pair，也不试图通过 issue_count 变化证明成功。

本轮不优先处理：

- 线中 KLP 端口型普通回路图
- `ComponentDiagramExtractor` 的 4/6 输出或长条双端口组件
- 背板几何表格 S0019/S0020 静默空结果
- 桌面端、预览、Tauri 或新的产品 CLI

### 93.4 本轮完成证据

已实现 `terminal_header_table` supplemental mapping，并保持端子页主路由为 `TerminalDiagramExtractor`。

最终 gate 后真实样本证据：

- 第二套 fresh 输出：[phase49_terminal_header_gate_second](/F:/workspace/XJToolkit/.tmp/phase49_terminal_header_gate_second/2_2)
- `table_extraction_summary.status = table_mappings_recovered`
- `total_mappings = 176`
- `table_pages = 4`
- `mapping_mode = terminal_header_table`
- `S0023 / 23 右侧端子图1.dwg` 中 `1-21QD1 -> 1-21n116` 已恢复为 `pass / confidence=0.95 / source=table_mapping`
- 第二套 audit `issue_count = 588`，这不是本轮成败指标；其中新增显性化的一对多主要应继续按 `rule_too_strict` / 关系语义处理

非回归证据：

- 第一套 fresh 输出：[phase49_terminal_header_gate_first](/F:/workspace/XJToolkit/.tmp/phase49_terminal_header_gate_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- `20 非电量保护背板图.dwg` 中 `NKR308A-1 -> 5FD15` 仍为 `backplate_virtual_table / pass / confidence=0.95`

为了避免把零散端子文本误提升为高置信表格关系，本轮还补了 group-level 结构证据门槛：同一表头组至少要有足够同行端点命中，且新增 sparse header-like 负向测试。

## 94. 2026-07-06 线中 KLP 端口型普通回路图完成证据

本轮补齐 `inline_klp_component_port_mapping`，用于普通二次原理图中的线中 KLP 端口关系。

规则边界：

- 只追加 `wire_component_mapping`，不放开普通单字符 `1/2` 候选。
- 必须有 KLP-like 本体、端口 `1/2`、左右外部端点，以及左右水平线证据。
- 裸三位数右端点只在该线支撑模式下按 KLP 前缀归一化，例如 `116 -> 1n116` 或 `3-2n116`。

真实样本证据：

- 第一套 fresh 输出：[phase52_inline_klp_line_gated_first](/F:/workspace/XJToolkit/.tmp/phase52_inline_klp_line_gated_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- `inline_klp_component_port_mapping = 6`
- `wire_component_mapping = 32`
- `pair_count = 1293`
- `issue_count = 390`
- `S0009 / 08 差动保护及信号回路.dwg`: `1KLP1-1 -> 1QD2`、`1KLP1-2 -> 1n116` 均为 `pass / confidence=0.95`
- `S0011 / 10 低后备保护及信号回路.dwg`: `3-2KLP1-1 -> 3-2QD2`、`3-2KLP1-2 -> 3-2n116` 均为 `pass / confidence=0.95`
- 同模式自然恢复 `S0010`: `1-2KLP1-1 -> 1-2QD2`、`1-2KLP1-2 -> 1-2n116`

第二套守门证据：

- 第二套 fresh 输出：[phase52_inline_klp_line_gated_second](/F:/workspace/XJToolkit/.tmp/phase52_inline_klp_line_gated_second/2_2)
- `inline_klp = 0`
- `wire_component_mapping = 0`

这说明本轮不是靠放宽候选召回，而是把一个明确的线中元件端口关系补成结构化 mapping。下一步更适合继续做元件接线图 `component_mapping`，或者让规则层更好理解这些结构化 mapping，避免把正确的一对多结构误报成普通冲突。

## 95. 2026-07-06 任务书完成度审计：当前主链仍未完全闭环

本轮重新按当前 [任务书](/F:/workspace/XJToolkit/doc/任务书.md) 审计，不用历史功能存在性代替完成证明。当前证据主要来自：

- 第一套 fresh 输出：[phase52_inline_klp_line_gated_first](/F:/workspace/XJToolkit/.tmp/phase52_inline_klp_line_gated_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 第二套 fresh 输出：[phase52_inline_klp_line_gated_second](/F:/workspace/XJToolkit/.tmp/phase52_inline_klp_line_gated_second/2_2)
- 第一套 audit 输出：[phase52 audit](/F:/workspace/XJToolkit/.tmp/phase52_inline_klp_line_gated_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/audit)

### 95.1 当前强证据已完成

| 要求 | 当前证据 |
|---|---|
| 项目目录多 DWG 输入并生成 findings | 第一套 `28` 页、第二套 `24` 页均有 `findings/pages.parquet`、`pairs.parquet`、`findings.json` |
| 页级分类字段进入主链 | `pages.parquet` 已有 `page_type / page_subtype / page_type_confidence / route_target / audit_disposition` |
| 不同图种走不同 extractor | 第一套 route 分布：`WireDiagramExtractor=13`、`TableExtractor=4`、`TerminalDiagramExtractor=4`、`ComponentDiagramExtractor=3`、`SkipExtractor=4`；第二套 route 分布：`WireDiagramExtractor=13`、`TerminalDiagramExtractor=4`、`ComponentDiagramExtractor=2`、`LayoutOnlyExtractor=2`、`SkipExtractor=3` |
| 表头型端子/表格 supplemental mapping | 第二套 `terminal_header_table=176`，`1-21QD1 -> 1-21n116` 为 `pass/confidence=0.95/source=table_mapping` |
| 背板虚拟表格 | 第一套 `NKR308A-1 -> 5FD15` 保持 `backplate_virtual_table/pass/confidence=0.95` |
| 普通回路图结构化子模式 | 第一套 `wire_component_mapping=32`，包含 `component_prefixed_signal_circuit=26` 和 `inline_klp_component_port_mapping=6` |
| issue 可复核证据字段 | 第一套 `issues.parquet` 有 `filename / sheet_no / sheet_id / line_group_id / left_value / right_value / rule_id / confidence / rationale / evidence / evidence_refs / root_cause` |
| page_findings 不再被当最终交付物 | 当前任务书已明确 page findings 属内部运行态；本轮没有把 `doc/page_findings/` 作为正式交付推进 |

### 95.2 部分实现但未达到任务书完成标准

| 要求 | 当前状态 | 缺口 |
|---|---|---|
| `TableExtractor` 作为独立高置信信源 | 真实样本已有 `evidence.source=table_mapping`，第一套 `144`、第二套 `176` | 顶层 `pair_kind` 仍统计为 `ordinary_pair`，没有显式 `table_mapping`；这与任务书中“结构化关系类型必须显式”的要求冲突 |
| 规则层统一消费结构化关系 | `wire_component_mapping` 已是显式 `pair_kind`，table mapping 可被部分规则按 `evidence.source` 识别 | `_high_confidence_pairs()` 仍先按 `_ordinary_pair_eligible()` 过滤；若把 table pair_kind 改正确，规则会漏掉表格信源，说明规则入口尚未真正结构化 |
| `ComponentDiagramExtractor` | 元件接线图已稳定路由到 `ComponentDiagramExtractor` | 仍没有 `component_mapping`；first `S0022-S0024` 和 second `S0019-S0020` 主要还是普通 pair/review/discard，不满足 4/6 输出或长条双端口组件要求 |
| 背板插件端子表 | first `S0019/S0020` 能进入背板表格型/`TableExtractor` 路径 | `NCZ343A` 类背板插件端子表仍未证明产出映射；不能用 `NKR308A` 虚拟表格代替该子类完成 |
| 端子图列角色/语义列 | 端子图路由正确，已有 `terminal_header_table` 和部分 `semantic_mapping / continuation / bridge_mapping` | 普通 terminal row、语义列、continuation 的 relationship kind 与规则语义仍不完整，不能只靠普通 pair 分数解释 |

### 95.3 明确未完成

- 元件接线图 `4输出/6输出`：任务书要求 `1-40DK2-1 -> ZD17` 等 `component_mapping`，当前没有强证据。
- 长条双端口元件接线图：任务书要求 `5KLP10-1 -> 5KLP9-1`、`5KLP10-2 -> 5n112`，当前没有强证据。
- 背板插件端子表 `NCZ343A`：任务书要求左右奇偶序号列绑定外侧端子，当前没有强证据。
- 结构化关系类型统一化：`table_mapping` 仍被顶层归为 `ordinary_pair`，与当前任务书第 9/10 章的关系类型要求不一致。

### 95.4 偏航或不应继续优先

- 不应继续用总 `issue_count` 变化证明成功。第一套 `issue_count=390`、第二套若重跑 audit 预计仍会大量显性化，这只是症状集合。
- 不应继续扩展桌面端、预览、Tauri 或新 CLI；当前主链缺口在 relationship kind、组件抽取和规则语义。
- 不应继续把端子、元件、表格都塞回普通 `ordinary_pair` 后再靠全局阈值调分。

### 95.5 本轮最近主链切片裁决

最近、最短且最贴近任务书主链的切片不是新增 UI，也不是继续调 `candidate` 阈值，而是：

**把所有表格映射 pair 的顶层 `pair_kind` 改为 `table_mapping`，并修正规则层高置信入口，使 `table_mapping` 在不冒充 `ordinary_pair` 的前提下继续参与跨页冲突和 mixed-source 规则。**

理由：

- 当前真实样本已经有稳定 table mapping，但关系类型仍错。
- 任务书明确要求 `table_mapping / wire_component_mapping / component_mapping` 是不同关系类型。
- 这是证明 `TableExtractor` 已成为独立信源的最短闭环。
- 修完后再进入更大的 `ComponentDiagramExtractor` 专用实现会更干净。

### 95.6 本轮切片完成证据

已完成 `table_mapping` 显式关系类型修正：

- `TableExtractor` 产出的表格映射现在顶层 `pair_kind = table_mapping`
- 表格映射 evidence 同步带 `pair_kind = table_mapping`
- 规则层高置信入口允许 `table_mapping` 作为结构化信源参与项目级规则，不再依赖它伪装成 `ordinary_pair`

验证结果：

- targeted table/rules tests: `13 passed`
- targeted analyze-project table tests: `5 passed`
- full pytest: `193 passed`

真实样本证据：

- 第一套 fresh 输出：[phase53_table_pair_kind_first](/F:/workspace/XJToolkit/.tmp/phase53_table_pair_kind_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 第一套 `pair_kind.table_mapping = 144`
- 第一套 `NKR308A-1 -> 5FD15` 仍为 `table_mapping / pass / confidence=0.95`
- 第二套 fresh 输出：[phase53_table_pair_kind_second](/F:/workspace/XJToolkit/.tmp/phase53_table_pair_kind_second/2_2)
- 第二套 `pair_kind.table_mapping = 176`
- 第二套 `1-21QD1 -> 1-21n116` 仍为 `table_mapping / pass / confidence=0.95`
- 两套 `run-audit` 均成功；issues 中已能看到 `pair_kind=table_mapping`

这轮之后，`TableExtractor` 作为独立高置信信源的 contract 更接近任务书要求。当前最强剩余缺口变为：`ComponentDiagramExtractor` 仍未产出 `component_mapping`。

## 96. 2026-07-06 下一刀裁决：先做长条双端口组件 `component_mapping`

任务书当前仍要求 `ComponentDiagramExtractor` 输出结构化 `component_mapping`，但真实产物中 `component_mapping=0`。本轮不继续调普通 PairBuilder，也不尝试一次性完成所有元件接线图。

在两个候选切片中：

- `4输出/6输出` 子类覆盖面更大，但布局规则和缺目标处理更多。
- `strip_two_port_component` 子类更窄：first `S0024 / 23 元件接线图3.dwg` 已有明确块名 `FJL-25-2A_Mirror`、端口 `1/2`、外部端和线证据。

因此本轮选择最短闭环切片：

**只实现 `strip_two_port_component`，目标输出 `5KLP10-1 -> 5KLP9-1` 与 `5KLP10-2 -> 5n112` 的 `component_mapping`。**

边界：

- 仅限 `ComponentDiagramExtractor` 路由下的 `元件接线图 / horizontal_component`。
- 仅限块内存在 `source_block_name=FJL-25-2A_Mirror` 的端口 `1/2`。
- 本体编号取同列上方元件文本，例如 `5KLP10`。
- 外部端取端口附近非块内文本原文，保留 `5KLP9-1`、`5n112`，不得降级为 `112`。
- 本轮不解决 `4输出/6输出`，不处理逗号拆分的全部泛化，只为后续组件库铺出 `component_mapping` contract。

### 96.1 `strip_two_port_component` 切片完成证据

已完成第一条 `ComponentDiagramExtractor` 专用结构化关系：

- 新增 `component_mapping` 顶层关系类型，不再把长条双端口元件接线图只留给普通 PairBuilder。
- 仅在 `元件接线图 / horizontal_component / ComponentDiagramExtractor` 下启用。
- 仅识别 `FJL-25-2A_Mirror` 块内端口 `1/2`、同列上方 `KLP` 本体、上下合法外部端点和支撑竖线。
- 端点候选阶段排除逗号组合、纯数字、单字符噪声；同一 strip 必须两端都合法才产出并 consume 普通 pair，避免 partial mapping 吃掉原始证据。
- 规则层把 `component_mapping` 纳入高置信图可见来源，但不加入 `table_mapping` 的置信度 bypass，也不放宽 `_ordinary_pair_eligible()`。

测试验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py tests\unit\test_pairs_and_rules.py -k "strip_two_port or component_mapping or reciprocal_graph"` -> `8 passed`
- `python -m pytest -q` -> `201 passed`

真实样本验证：

- 第一套 fresh 输出：[phase56_strip_component_safe_first](/F:/workspace/XJToolkit/.tmp/phase56_strip_component_safe_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 第一套 audit 输出：[phase56 first audit](/F:/workspace/XJToolkit/.tmp/phase56_strip_component_safe_first/audit)
- 第一套 `component_mapping = 10`，逗号端点 component mapping = `0`
- 目标页 `S0024 / 23 元件接线图3.dwg` 已产出：
  - `5KLP10-1 -> 5KLP9-1`，`pair_kind=component_mapping`，`status=pass`，`confidence=0.95`
  - `5KLP10-2 -> 5n112`，`pair_kind=component_mapping`，`status=pass`，`confidence=0.95`
- `S0024 / GC0132` 原普通 `? -> 112` 已被标记为 `discard`，rationale 为 `Covered by component_mapping from ComponentDiagramExtractor.`
- 第一套 audit `issue_count = 385`；root cause 分布：`insufficient_evidence=204`、`candidate_noise=68`、`rule_too_strict=40`、`extractor_missing=38`、`pairing_wrong=35`
- 第二套 fresh 输出：[phase56_strip_component_safe_second](/F:/workspace/XJToolkit/.tmp/phase56_strip_component_safe_second/2_2)
- 第二套 audit 输出：[phase56 second audit](/F:/workspace/XJToolkit/.tmp/phase56_strip_component_safe_second/audit)
- 第二套 `component_mapping = 8`，逗号端点 component mapping = `0`，集中在 `S0020` 的 `3-21KLP* / 1-21KLP*` strip 二端口结构。
- 第二套 audit `issue_count = 584`；root cause 分布：`insufficient_evidence=287`、`pairing_wrong=174`、`rule_too_strict=70`、`candidate_noise=33`、`extractor_missing=20`

本轮之后，`ComponentDiagramExtractor` 已不再是完全的 PairBuilder 包装，但只覆盖 `strip_two_port_component`。下一步仍应继续做元件接线图 `4输出/6输出` 或背板几何表格补齐，而不是继续扩 CLI。

## 97. 2026-07-06 背板几何表格补齐：只补抽取，不扩大路由

上一轮之后，first `S0019/S0020` 仍是 `backplate_geometric_table / TableExtractor` 但 `table_mapping_count=0`。并行只读审图确认：这两页不是没有结构，而是端点形态超出现有背板端点正则。

根因：

- `TableExtractor` 的背板虚拟表格逻辑只接受 `5FD15 / 1QD1` 这类端点。
- `S0019/S0020` 的真实端点大量是 `1-2QD1`、`1-4QD17`、`1-2CLP1-2`、`CD2`、`YD3`、`3-2QD1`、`3-4QD17`。
- 通用 grid 分支只记录 22/23 列空结构，不会为非三列表格产出映射。

本轮完成的最小修正：

- 只在 `TableExtractor` 背板虚拟表格端点识别里扩展 endpoint pattern，保留旧 `5FD15` 形态，同时接受带页/段前缀和纯字母前缀端点。
- 增加 header 级安全闸：同一背板 header 至少要有 3 个端点命中才释放高置信 `table_mapping`，避免零散 `LAN1/LAN2` 类小组被提升。
- 没有放宽 `PageClassifier` 背板路由条件。一次真实验收中曾发现若同步放宽分类器，会把第二套普通装置背板从 `LayoutOnlyExtractor` 升级为 `TableExtractor` 并产生 `LAN*` 映射；该路由放宽已撤回。

测试验证：

- `python -m pytest -q tests\unit\test_table_extractor.py tests\integration\test_analyze_project.py -k "backplate_virtual or backplate"` -> `5 passed`
- `python -m pytest -q` -> `203 passed`

真实样本验证：

- 第一套 fresh 输出：[phase58_backplate_route_stable_first](/F:/workspace/XJToolkit/.tmp/phase58_backplate_route_stable_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 第一套 audit 输出：[phase58 first audit](/F:/workspace/XJToolkit/.tmp/phase58_backplate_route_stable_first/audit)
- first 背板 `table_mapping` 分布：`S0018=27`、`S0019=72`、`S0020=67`、`S0021=56`
- first `S0019/S0020` 保持 `page_subtype=backplate_geometric_table`，但不再是空结果。
- 代表关系已命中：
  - `S0019`: `NDY306A-3 -> 1-2QD1`
  - `S0019`: `NCZ343A-2 -> 1-4QD17`
  - `S0020`: `NDY306A-3 -> 3-2QD1`
  - `S0020`: `NCZ343A-2 -> 3-4QD17`
  - `S0021`: `NKR308A-1 -> 5FD15` 保持不回退
- first 背板 `LAN*` table mappings = `0`
- first `pair_kind.table_mapping = 299`，audit `issue_count = 453`。issue 增加来自新增高置信表格信源进入规则图，不作为失败；后续应继续做 root-cause/规则语义，而不是为了降噪隐藏关系。
- 第二套 fresh 输出：[phase58_backplate_route_stable_second](/F:/workspace/XJToolkit/.tmp/phase58_backplate_route_stable_second/2_2)
- 第二套 audit 输出：[phase58 second audit](/F:/workspace/XJToolkit/.tmp/phase58_backplate_route_stable_second/audit)
- second `S0017/S0018` 普通装置背板保持 `LayoutOnlyExtractor / classify_only`，没有被误升级为 TableExtractor。
- second `pair_kind.table_mapping = 176`，全部仍来自端子图表头映射；背板 table mappings = `0`，`LAN*` table mappings = `0`，audit `issue_count = 584`。

并行子代理给出的下一刀候选：

- `KK2P/KK3P` 多端口组件映射可作为下一个 `ComponentDiagramExtractor` 子模式。
- 代表目标包括 first `S0022`: `1DK-1 -> ZD9`、`1-2ZKK-6 -> 1-2n721`；second `S0019`: `1-21DK2-1 -> ZD8`、`1-21ZKK-2 -> 1-21n715`。
- 该切片需要把 `BlockRecord` 传入 component extractor，改动面大于本轮背板正则补齐，适合作为下一轮独立提交。

## 98. 2026-07-06 当前任务书完成度审计：主链仍卡在多端口元件接线图

本轮重新读取当前未提交修改后的 [任务书](/F:/workspace/XJToolkit/doc/任务书.md)。任务书第 31-48 行定义 MVP 成功标准：批量 DWG 输入、每页对象/候选/配对、跨页规则、可复核报告；第 54-66 行要求“通用 CAD 抽取 + 页级分类器 + 规则路由 + 专用脚本库”；第 95-146 行明确 `ComponentDiagramExtractor` 必须支持元件接线图组件实例、`4输出/6输出` 与长条双端口 `component_mapping`；第 1723-1763 行把真实样本、故障注入样本、四类图型覆盖和可复核报告列为最终 MVP 验收。

当前强证据已完成：

| 要求 | 当前证据 |
|---|---|
| 批量读取真实项目 DWG 并生成 findings 运行态 | 最新 first 输出 [phase58 first](/F:/workspace/XJToolkit/.tmp/phase58_backplate_route_stable_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA) 为 `28` 页；latest second 输出 [phase58 second](/F:/workspace/XJToolkit/.tmp/phase58_backplate_route_stable_second/2_2) 为 `24` 页；均有 `pages/texts/lines/line_groups/pairs` parquet 与 `findings.json`。 |
| 每页有 `page_type` 与 `route_target`，且实际分流到不同 extractor | first route 分布：`Wire=13`、`Component=3`、`Terminal=4`、`Table=4`、`Skip=4`；second route 分布：`Wire=13`、`Component=2`、`Terminal=4`、`LayoutOnly=2`、`Skip=3`。 |
| 普通回路图结构化子模式 | first `wire_component_mapping=32`，已覆盖元件分区型和线中 KLP 端口型；代表映射如 `1-2n218 -> 1-4YD1`、`3-2KLP1-1 -> 3-2QD2` 已在前序 phase 真实 rerun 证明。 |
| 表头型端子/表格映射 | second `table_mapping=176` 来自端子页 `terminal_header_table`；代表 `1-21QD1 -> 1-21n116` 已为 `pass / confidence=0.95 / pair_kind=table_mapping`。 |
| 背板表格型图 | first 背板 `table_mapping` 分布为 `S0018=27`、`S0019=72`、`S0020=67`、`S0021=56`；代表 `NDY306A-3 -> 1-2QD1`、`NCZ343A-2 -> 1-4QD17`、`NKR308A-1 -> 5FD15` 均命中。second 普通装置背板保持 `LayoutOnlyExtractor / classify_only`，未误生成 `LAN*` table mapping。 |
| 长条双端口元件接线图基本路径 | first `S0024` 已输出 `5KLP10-1 -> 5KLP9-1`、`5KLP10-2 -> 5n112`；second `S0020` 自然命中 `3-21KLP* / 1-21KLP*` strip 结构。 |
| run-audit 可复核证据字段 | latest first/second `issues.parquet` 均包含 `filename / sheet_no / sheet_id / line_group_id / left_value / right_value / rule_id / confidence / rationale / evidence / evidence_refs / root_cause`。 |
| `page_findings` 不再作为正式默认交付目录 | 当前 `findings.json.page_findings` 是运行态汇总；默认 findings 输出未把 `page_findings/` 当正式交付目录。 |

部分实现但尚未达到任务书完成标准：

| 要求 | 当前状态 | 缺口 |
|---|---|---|
| `ComponentDiagramExtractor` 作为元件接线图专用识别器 | 路由已生效，`component_mapping` 已覆盖 `strip_two_port_component` 子类 | first `S0022 / 21 元件接线图1.dwg` 仍 `component_mapping=0`，`47` 条全是 `ordinary_pair discard`；second `S0019 / 19 元件接线图1.dwg` 仍 `component_mapping=0`，`39` 条全是 `ordinary_pair discard`。 |
| `4输出/6输出` 多端口组件实例 | 任务书第 111-123 行已给出端口布局和样例 | 尚未实现 `KK2P/KK3P` 或同构组件实例抽取，仍不能输出 `1DK-1 -> ZD9`、`1-2ZKK-6 -> 1-2n721`、`1-21ZKK-2 -> 1-21n715`。 |
| 长条双端口逗号外部端拆分 | 任务书第 135-137 行要求 `5KLP5-1 -> 5KLP3-1` 与 `5KLP5-1 -> 5KLP2-1` 分裂输出 | 当前为安全起见排除逗号端点，避免整串误当端子；尚未实现逗号拆分。 |
| 端子图列角色与 continuation/semantic 语义 | 已有 `semantic_mapping / continuation / bridge_mapping`，端子表头映射已分流 | 仍需验证普通端子行号、语义列、continuation 不再系统性制造伪普通 pair；这更偏规则语义收敛，而不是当前最短抽取缺口。 |
| 故障注入验收套件 | 已有内部 acceptance/evaluation 相关测试与 CLI harness | 本轮未重新证明第 19 章“真实样本 + 隔离故障注入样本”的完整验收闭环。 |

明确未完成或仍不能宣称完成：

- 不能宣称元件接线图 MVP 完成，因为 `4输出/6输出` 组件实例仍未产出 `component_mapping`。
- 不能宣称长条双端口完全完成，因为逗号外部端拆分尚未做。
- 不能用 issue 总数变化证明成功；latest first issue 为 `453`，second 为 `584`，这些只是症状集合。新增结构化关系会让规则图更可见，短期 issue 数上升并不等价于失败。
- 不能继续优先投入桌面端、Tauri、预览和新 CLI；当前阻塞在专用识别器主链。

本轮最短闭环裁决：

**下一刀应实现 `KK2P/KK3P` 多端口 `component_mapping`，覆盖元件接线图 `4输出/6输出` 的最小真实样本。**

理由：

- 任务书第 95-124、140-146 行把它列为 `ComponentDiagramExtractor` 的核心 MVP 能力。
- 当前真实产物已有强反证：first `S0022` 和 second `S0019` 路由正确但抽取仍为普通 discard pair。
- 并行子代理已只读确认可实现最小模式：使用 `BlockRecord` 锚定 `KK2P/KK3P`，块内端口号结合上方本体文本，按水平行线和外部端 bbox center 生成 `component_mapping`。
- 该切片比继续处理 terminal/continuation 规则更接近“主链识别器缺口”，也比 UI/报告补全更贴近任务书主线。

## 99. 2026-07-06 `KK2P/KK3P` 多端口元件映射闭环

本轮按 section 98 的裁决实现 `ComponentDiagramExtractor` 第二条专用组件关系：`KK2P/KK3P` 多端口组件映射。

实现边界：

- `pipeline.py` 只在 `ComponentDiagramExtractor` route 下传入同页 `BlockRecord`，没有扩大其它图种或 CLI。
- `page_extractors.py` 在现有 PairBuilder / strip two-port 后追加 `extract_kk_multi_port_component_pairs(...)`。
- `component_diagrams.py` 只启用 `KK2P / KK3P`，不启用 `KK1P`。
- 本体文本取块上方非 block 文本，端口文本取对应 block 的虚拟文本，外部端点按水平支撑线和 bbox center 匹配。
- 不强配缺失端口；同一 KK block 对同一支撑线同侧 / 同一 endpoint 只允许产出一次，避免 `ZKK-4`、`ZKK-6` 复用同一外部端。

测试验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py` -> `10 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py::test_analyze_project_executes_route_specific_pair_extractors` -> `1 passed`
- `python -m pytest -q` -> `208 passed`

真实样本验证：

- 第一套 fresh 输出：[phase60 first](/F:/workspace/XJToolkit/.tmp/phase60_kk_multi_port_dedup_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 第一套 audit 输出：[phase60 first audit](/F:/workspace/XJToolkit/.tmp/phase60_kk_multi_port_dedup_first/audit)
- first `pair_kind.component_mapping = 27`，其中 `21 元件接线图1.dwg` 从上一轮 `0` 变为 `17` 条 `kk_multi_port_component`。
- first 代表命中：
  - `5DK-2 -> 5FD1`
  - `5DK-4 -> 5FD25`
  - `1-2ZKK-2 -> 1-2n721`
  - `1-2ZKK-4 -> 1-2n719`
  - 既有 strip 目标 `5KLP10-1 -> 5KLP9-1`、`5KLP10-2 -> 5n112` 保持命中
- first KK duplicate endpoint check = `0`，audit `issue_count = 463`。
- 第二套 fresh 输出：[phase60 second](/F:/workspace/XJToolkit/.tmp/phase60_kk_multi_port_dedup_second/2_2)
- 第二套 audit 输出：[phase60 second audit](/F:/workspace/XJToolkit/.tmp/phase60_kk_multi_port_dedup_second/audit)
- second `pair_kind.component_mapping = 20`，其中 `19 元件接线图1.dwg` 从上一轮 `0` 变为 `12` 条 `kk_multi_port_component`。
- second 代表命中：
  - `1-21DK2-2 -> 1-21GD1`
  - `1-21DK2-4 -> 1-21GD19`
  - `1-21ZKK-2 -> 1-21n719`
  - `1-21ZKK-4 -> 1-21n715`
  - 既有 strip 目标 `3-21KLP2-1 -> 3-21GD3`、`1-21KLP1-2 -> 1-21n112` 保持命中
- second KK duplicate endpoint check = `0`，audit `issue_count = 584`。

当前裁决：

- `ComponentDiagramExtractor` 已不再只是普通 PairBuilder 包装，已经覆盖 `strip_two_port_component` 与 `KK2P/KK3P` 多端口两类真实组件结构。
- 仍不能宣称元件接线图完全完成：逗号外部端拆分仍未做，且 `KK2P/KK3P` 的端口编号真实语义还需要更多人工标注校准。
- 下一刀更适合做 `strip_two_port_component` 逗号端点拆分，或转向端子图列角色 / continuation 语义复核；不应继续扩产品 CLI。

## 100. 2026-07-06 phase60 后任务书审计：主链强证据与端子残留 ordinary 降级

本轮重新按当前 [任务书](/F:/workspace/XJToolkit/doc/任务书.md) 审计 phase60 真实样本，而不是沿用历史完成叙事。任务书当前关键要求包括：第 31-48 行的 MVP 页型/报告标准，第 54-66 行的“通用 CAD 抽取 + 页级分类器 + 路由 + 专用脚本库”，第 920-940 行的七类关系类型，第 1723-1763 行的真实样本/故障注入/最终 MVP 定义。

当前强证据：

| 要求 | 当前证据 |
|---|---|
| 每页稳定 `page_type / route_target / audit_disposition` | phase60 first 为 `28` 页，route 分布 `Wire=13 / Component=3 / Terminal=4 / Table=4 / Skip=4`；phase60 second 为 `24` 页，route 分布 `Wire=13 / Component=2 / Terminal=4 / LayoutOnly=2 / Skip=3`。 |
| 普通回路图不再只有普通 pair | first `wire_component_mapping=32`，已覆盖元件分区与线中 KLP 端口型。 |
| 元件接线图进入专用关系 | phase60 first `component_mapping=27`，其中 `21 元件接线图1.dwg=17`；phase60 second `component_mapping=20`，其中 `19 元件接线图1.dwg=12`。 |
| 表格/背板表格进入独立高置信信源 | phase60 first `table_mapping=299`，覆盖背板表格和端子表头；phase60 second `table_mapping=176`，覆盖端子表头。 |
| 端子图已有语义/延续/桥接分流 | phase60 second 端子页已有 `semantic_mapping=157`、`continuation=20`、`bridge_mapping=3`、`table_mapping=176`。 |
| issue 可复核字段 | phase60 两套 `issues.parquet` 均包含 `filename / sheet_no / sheet_id / line_group_id / left_value / right_value / rule_id / confidence / rationale / evidence / evidence_refs / root_cause`。 |

部分实现但仍需继续收敛：

| 要求 | 当前状态 | 缺口 |
|---|---|---|
| 端子图以行锁定、列角色和代号提取为主 | 已有 terminal header table、semantic/continuation/bridge channels | phase60 second 仍有端子页 `ordinary_pair review=200`，其中大量是 `3-21n211` 被降成裸 `211` 后与行号组成 `21 -> 211`。 |
| continuation 不应制造伪普通冲突 | 已有 `pair_kind=continuation` 且普通规则会旁路非 ordinary | 覆盖仍不完整，仍有部分单侧短数字留在 ordinary review。 |
| 表格/端子边界 | 端子页内 `terminal_header_table` 已产出 `table_mapping` | second 没有独立 `TableExtractor` 路由页；这是分类口径差异，不阻塞“有效映射可审计”，但仍需在后续验收说明中讲清。 |

并行只读复核结论：

- terminal/continuation 复核认为当前不足以宣称端子语义列/continuation 完全满足 MVP，因为端子页 ordinary review 仍多，且存在派生 `n###` suffix ordinary。
- route/table 复核认为 PageClassifier、Page Router、TableExtractor、ComponentDiagramExtractor 主链已有强证据；若继续开发，应只做残留 ordinary cleanup，不应重回大范围路由/UI/CLI。

主线程裁决：

**本轮只做“terminal structured endpoint ordinary bypass”窄切片。**

理由：

- 这直接对应任务书第 62 行“端子图不再套用普通回路图端点近邻策略”和第 930-934 行“非普通关系不能塞进 ordinary pair”。
- 它不扩大候选阈值，不修改路由，不碰 UI，不用 issue 总数下降冒充成功。
- 它只在存在 `terminal_header_table` 覆盖证据时，把已由结构化表格解释过的完整端子文本从裸 suffix ordinary review 中降级。

实现与验证：

- `page_extractors.py` 新增端子 route 后处理：若 ordinary pair 一侧选中 `3-21n211` 这类完整端子文本但 PairBuilder 只取裸 suffix，且该文本 ID 已被 `terminal_header_table` 映射覆盖，则标记为 `discard`、`ordinary_pair_eligible=False`、`covered_by_terminal_structured_endpoint=True`。
- 没有表头覆盖证据的 synthetic row-lock strip 保持 `review`，避免把普通端子行证据直接吞掉。
- `python -m pytest -q` -> `211 passed`。

真实样本验证：

- 第一套 fresh 输出：[phase62 first](/F:/workspace/XJToolkit/.tmp/phase62_terminal_structured_cover_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 第一套 audit 输出：[phase62 first audit](/F:/workspace/XJToolkit/.tmp/phase62_terminal_structured_cover_first/audit)
- first 端子页 ordinary review `104 -> 85`，被结构化覆盖降级 `19` 条；terminal ordinary low-confidence issues `66 -> 47`。
- first `component_mapping=27`、`table_mapping=299` 不回退。
- 第二套 fresh 输出：[phase62 second](/F:/workspace/XJToolkit/.tmp/phase62_terminal_structured_cover_second/2_2)
- 第二套 audit 输出：[phase62 second audit](/F:/workspace/XJToolkit/.tmp/phase62_terminal_structured_cover_second/audit)
- second 端子页 ordinary review `200 -> 87`，被结构化覆盖降级 `113` 条；terminal ordinary low-confidence issues `176 -> 63`。
- second `component_mapping=20`、`table_mapping=176` 不回退。

当前剩余最靠近任务书主链的缺口：

- 端子页仍有普通行列角色 residual ordinary review，需要继续按列角色/行锁定收敛，而不是全局调分。
- `strip_two_port_component` 的逗号外部端拆分仍未实现。
- 最小验收第 19 章的“真实正确样本 + 隔离故障注入样本”仍需要作为最终验收闭环重跑，不能只靠当前真实样本和单测宣称完成。

## 101. 2026-07-06 `strip_two_port_component` 逗号端点拆分闭环

本轮继续遵守“主线程做总调度、子代理并发执行”的约束。并行只读审计结论一致：phase62 后端子图剩余 ordinary review 已经混合为多类问题，不适合继续盲切；更确定的抽取缺口是 first `S0024 / 23 元件接线图3.dwg` 的长条双端口元件逗号外部端。

实现边界：

- 只在 `ComponentDiagramExtractor` 的 `strip_two_port_component` 子模式里拆分逗号端点。
- 不修改全局候选规则，不扩大端子图、普通回路图或 KK 多端口逻辑。
- 同一个外部端文本按英文逗号拆分后，只保留符合既有 endpoint pattern 的合法片段；空值、纯数字、单字符、中文说明片段不产出 mapping。
- 非逗号合法候选优先于逗号候选，避免离散合法端点被逗号噪声抢走。
- 只有上下端口两侧都至少有一个合法 endpoint 时，才 consume 原普通 line group。
- `component_mapping` 的 `right_text_id` 仍指向原始逗号文本，并在 evidence 中同时保留 `external_endpoint_raw` 与 `external_endpoint_split`。

测试验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py tests\unit\test_pairs_and_rules.py -k "strip_two_port or component_mapping"` -> `10 passed`
- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `4 passed`
- `python -m pytest -q` -> `213 passed`
- `git diff --check` -> no whitespace errors，仅有当前工作树 CRLF warning。

真实样本验证：

- 第一套 fresh 输出：[phase63 first](/F:/workspace/XJToolkit/.tmp/phase63_strip_comma_first/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA)
- 第一套 audit 输出：[phase63 first audit](/F:/workspace/XJToolkit/.tmp/phase63_strip_comma_first/audit)
- first `S0024` 的 `component_mapping` 从 phase62 的 `6` 增加到 `39`。
- first 全项目 `pair_kind.component_mapping` 从 `27` 增加到 `75`；其它主要关系类型不变：`ordinary_pair=943`、`table_mapping=299`、`semantic_mapping=103`、`continuation=68`、`wire_component_mapping=32`、`bridge_mapping=3`。
- 任务书点名目标已命中：
  - `5KLP5-1 -> 5KLP3-1`
  - `5KLP5-1 -> 5KLP2-1`
  - `5KLP5-2 -> 5n307`
- first audit issue `444 -> 458`。增加来自新增高置信 `component_mapping` 进入规则图后的可见一致性症状，不应通过隐藏关系来降噪，后续应做规则语义 / 分支语义解释。
- 第二套 fresh 输出：[phase63 second](/F:/workspace/XJToolkit/.tmp/phase63_strip_comma_second/2_2)
- 第二套 audit 输出：[phase63 second audit](/F:/workspace/XJToolkit/.tmp/phase63_strip_comma_second/audit)
- second 完全不漂移：`pair_count=1407`、`issue_count=471`、`component_mapping=20`、`table_mapping=176` 均与 phase62 一致。

并行验收审计提醒：

- 现有 `mvp_minimum_suite` 仍不能作为最终完成证明：真实 subset 的 ordinary pair golden 与后续结构化关系策略已经不完全一致，且 fault-injected artifacts 需要固定生成 / 绑定。
- 第一套真实正确样本仍存在较多 hard/critical symptoms，其中一部分 root cause 为 `insufficient_evidence`，后续不能把这类证据不足项继续当作最终 hard error。
- 桌面 `exe` 交付链仍需单独闭环：当前已有 service entry 与 Tauri 壳，但最终还要证明无手动 CLI / 无源码依赖的本地 exe 工作流。

当前裁决：

- `strip_two_port_component` 的任务书点名逗号拆分样例已经闭合。
- 下一步不应继续扩 CLI；最近的两条主线候选是：
  - 验收红线收口：刷新 acceptance suite，使其以结构化关系口径验证真实样本，并固定 fault-injected artifacts。
  - 规则语义收口：解释新增 `component_mapping` 后暴露的 many-to-one / branch 关系，避免真实正确图纸产生 hard error 洪峰。

## 102. 2026-07-06 组件分支 / 多入口规则语义：不隐藏关系，只修正 review 解释

phase63 之后 first issue 从 `444` 到 `458`，表面上是 `+14`。只读子代理与主线程共同拆分后确认，真实变化是：

- 新增 `29` 条 `component_mapping` 图关系 review issue。
- 同时消失 `15` 条原先的 `ordinary_pair / R-PAIR-MISSING-SIDE / extractor_missing`。
- 新增项全部是 `pair_kind=component_mapping`、`severity=review`、`root_cause=rule_too_strict`。
- 新增规则分布为 `R-ONE-TO-MANY=16`、`R-MANY-TO-ONE=13`。

这说明逗号拆分没有制造 hard error，而是把原先缺边症状提升成结构化组件映射后，让项目级图规则看到了组件端子分支 / 多入口关系。正确动作不是把 `component_mapping` 从高置信图里移除，也不是回滚抽取，而是把规则解释从“像冲突”改成“同页组件邻接结构待复核”。

本轮完成的最小规则语义修正：

- `R-ONE-TO-MANY`：当同页所有 linked pairs 都是 `pair_kind=component_mapping` 且 `component_submode=strip_two_port_component` 时，保留 `review`，但写入 `one_to_many_classification=component_branch_review`，标题改为“组件端子分支映射待复核”。
- `R-MANY-TO-ONE`：同样条件下写入 `many_to_one_classification=component_branch_review`，标题改为“组件端子多入口映射待复核”。
- 普通 `ordinary_pair`、普通 `component_mapping`、跨页关系与表格关系不走这个 specialized 文案。
- `component_mapping` 继续作为 high-confidence graph input，不隐藏 issue。

测试验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "one_to_many or many_to_one or component_mapping"` -> `9 passed`
- `python -m pytest -q` -> `216 passed`

真实样本验证：

- first audit rerun：[phase64 first audit](/F:/workspace/XJToolkit/.tmp/phase64_component_branch_rules_first/audit)
- first `issue_count=458`，与 phase63 一致。
- first 中 `component_branch_review=27`，其中 `R-ONE-TO-MANY=16`、`R-MANY-TO-ONE=11`。
- 剩余 2 条 many-to-one 没进 specialized 分类，是因为 linked pair 集合不是全员 `strip_two_port_component`，安全闸保持保守。
- second audit rerun：[phase64 second audit](/F:/workspace/XJToolkit/.tmp/phase64_component_branch_rules_second/audit)
- second `issue_count=471`，与 phase63 一致，`component_branch_review=0`，说明本轮没有影响第二套无逗号 strip 分支的关系图。

当前剩余主线：

- `mvp_minimum_suite` 仍需要刷新为结构化关系验收口径。当前失败主要来自旧 spec 仍断言 `S0024` 的裸数字 `ordinary_pair`，而当前系统已把这些关系表达为 `table_mapping/pass` 或结构化 review。
- `fault_injected` artifacts / alias 仍需固定到 suite，保证内部 harness 可稳定复跑。
- first 真实样本仍有一批 `R-CROSS-PAGE-CONFLICT` 与 `insufficient_evidence`，不能在最终验收里继续表现为 hard error 洪峰。

## 103. 2026-07-06 internal acceptance suite：支持结构化关系 golden

只读验收审计确认，上一版 `mvp_minimum_suite` 的真实样本失败不代表 phase63 主链倒退，而是验收资产仍停留在旧的裸数字 `ordinary_pair` 口径：

- second `S0024 / 24 右侧端子图2.dwg` 旧 spec 断言 `406 -> 20`、`409 -> 25` 等 `ordinary_pair/review`。
- 当前系统已经把这类端子表关系表达为 `table_mapping/pass`，例如 `1-21CD20 -> 1-21n406`。
- 旧 spec 还把 mixed component/terminal subset 限定为 `pair_kinds=["ordinary_pair"]` 与 `statuses=["review"]`，会排除结构化 pass 关系。

本轮完成的最小验收 harness 修正：

- `golden_pairs` 继续兼容旧字段 `filename / left_value / right_value`。
- `golden_pairs` 现在可选声明：
  - `pair_kind`
  - `status`
  - `pair_key`
- 若 spec 提供这些字段，匹配时必须同时满足；未提供时保持旧 ordinary-pair mini harness 兼容。
- extracted complete pair 去重也纳入 `pair_kind/status/pair_key`，避免结构化关系与普通关系在同一左右值上互相污染。
- suite 名称改为 `internal-mvp-minimum-acceptance-suite`，明确它是内部开发验收 harness，不是产品 CLI 主界面。

fixture 更新：

- [second_set_terminal_s0024.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_real_subset/second_set_terminal_s0024.json) 改为 6 条 phase63 `table_mapping/pass` golden：
  - `1-21CD20 -> 1-21n406`
  - `1-21CD25 -> 1-21n409`
  - `1-21CD30 -> 1-21n412`
  - `1-21CD35 -> 1-21n415`
  - `1-21CD40 -> 1-21n418`
  - `1-21CD45 -> 1-21n421`
- `428 -> 55` 没有硬迁为结构化 golden；phase63 当前还需要人工确认它真实应绑定哪一行 / 哪个表头端点。
- [second_set_component_terminal_subset.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_real_subset/second_set_component_terminal_subset.json) 保留 second `S0020` 的 6 条 `ordinary_pair/review`，并把 second `S0024` 改为上述 6 条 `table_mapping/pass`。

验证：

- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `5 passed`
- `python -m pytest -q` -> `217 passed`
- phase63 second 上执行 internal suite：
  - `real_second_component_terminal_subset`: expected `12`，matched `12`，precision `1.0`，recall `1.0`
  - `real_second_terminal_s0024`: expected `6`，matched `6`，precision `1.0`，recall `1.0`
  - suite overall 仍为 `False`，因为本轮未提供 `fault_injected` alias，`required_passed_case_count=2/3`

当前裁决：

- 真实 second-set 结构化关系验收口径已刷新到 current-head。
- `fault_injected_acceptance_mini` 仍需要固定 artifact 生成 / alias 绑定，才能让完整 internal suite 一键通过。
- 这仍是内部 harness，不应继续扩成用户产品 CLI；最终 exe 工作流后续应调用同一 service/session 能力。

补充验证：

- 主线程用现有 `acceptance_mini` 测试生成逻辑在 `.tmp/phase65_fault_injected_run` 临时生成 fault-injected artifact。
- 随后执行完整 internal suite：
  - `fault_injected=.tmp/phase65_fault_injected_run/artifacts/project`
  - `real_second=.tmp/phase63_strip_comma_second/2_2`
- 结果为 `required_passed_case_count=3/3`、`acceptance_passed=True`。
- 三个 case 结果：
  - `fault_injected_acceptance_mini`: expected `16`，matched `16`，precision `1.0`，recall `1.0`
  - `real_second_component_terminal_subset`: expected `12`，matched `12`，precision `1.0`，recall `1.0`
  - `real_second_terminal_s0024`: expected `6`，matched `6`，precision `1.0`，recall `1.0`

该 `.tmp` artifact 不应提交。下一步应把现有测试 helper 提炼为 `tests/support` 级 internal harness 支持代码，用测试证明 fault alias 可稳定生成，而不是把运行产物纳入版本库。

随后已完成测试支持闭环：

- 将 acceptance mini 的 fake DXF converter 与生成逻辑提炼到 [acceptance_mini.py](/F:/workspace/XJToolkit/tests/support/acceptance_mini.py)。
- integration test 现在直接使用当前 [mvp_minimum_suite.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_suite/mvp_minimum_suite.json)，先生成 `fault_injected` artifact，再构造最小 `real_second` 临时 artifact，断言 required case `3/3` 全部通过。
- 这证明 fault alias 绑定可以稳定复跑，同时没有提交 `.tmp` 产物，也没有新增产品 CLI。

验证：

- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `5 passed`
- `python -m pytest -q` -> `217 passed`

到这里，Phase50 的 internal acceptance harness 已完成三件事：

- 真实 second-set golden 已从旧 `ordinary_pair` 口径升级到结构化 `table_mapping/pass` 口径。
- fault-injected mini case 可通过测试 helper 稳定生成 artifact 并参与 suite。
- 完整 suite 在临时产物上已实证 `3/3` 可通过。

## 104. 2026-07-06 Desktop exe runtime contract：release 不再隐式依赖源码路径

Phase51 的只读审计确认，桌面主链已经有一层共享 service entry：

- `run_analysis_workflow()` 统一承载 analyze + optional audit。
- Python desktop sidecar 已能写入 session workspace / state DB，并支持 recent projects、load result、preview、issue status。
- Tauri frontend 已通过 native invoke 调用 analyze/list/load/preview/status。

但旧 Rust command bridge 仍固定执行 `python -m dwg_audit.cli`，并从编译时 `CARGO_MANIFEST_DIR/../../..` 推导源码根。这意味着此前只能证明开发态可用，不能证明安装后的 exe 脱离源码树和本机 Python 环境。

本轮完成的最小 runtime contract 修正：

- 新增 [sidecar_runtime.rs](/F:/workspace/XJToolkit/apps/desktop/src-tauri/src/sidecar_runtime.rs)。
- Tauri sidecar 解析顺序改为：
  - `DWG_AUDIT_SIDECAR_EXE`
  - Tauri resource dir 中的 `dwg-audit-sidecar.exe` / `dwg-audit-sidecar` / `sidecar/dwg-audit-sidecar.exe` / `sidecar/dwg-audit-sidecar`
  - 开发态 `python -m dwg_audit.cli` fallback
- release 运行态不再隐式回退源码路径；源码 fallback 只允许 debug build 或显式 `DWG_AUDIT_ALLOW_SOURCE_FALLBACK=1`。
- Rust command bridge 继续复用内部 sidecar/CLI 子命令，不新增产品 CLI 面。
- 桌面 README 已记录 runtime contract 和当前限制。

验证：

- `npm run build` -> passed
- `cargo test --manifest-path apps\desktop\src-tauri\Cargo.toml` -> `5 passed`
- `cargo test --release --manifest-path apps\desktop\src-tauri\Cargo.toml` -> `5 passed`
- `python -m pytest -q tests\unit\test_sidecar.py tests\unit\test_execution_service.py` -> `7 passed`
- `python -m pytest -q` -> `217 passed`
- `npm run tauri:build` -> 成功产出 [DWG Audit Desktop_0.1.0_x64-setup.exe](/F:/workspace/XJToolkit/apps/desktop/src-tauri/target/release/bundle/nsis/DWG%20Audit%20Desktop_0.1.0_x64-setup.exe)

当前裁决：

- Phase51 前两条已闭合：exe 工作流依赖点已审计清楚，sidecar runtime 策略已落代码合同。
- Phase51 还不能标 complete：真实 `dwg-audit-sidecar` 可执行文件尚未产出/进包，仍缺“安装后的 exe 导入项目 -> 启动分析 -> 加载报告”端到端证据。
- 下一刀应集中在 sidecar executable packaging，而不是继续扩 CLI 或继续改桌面 UI。

## 105. 2026-07-06 开入矩阵 input_matrix_wire_mapping：结构化覆盖裸数字 ordinary 半边

只读恢复和 second-set fresh 证据确认，`08/12 测控开入回路图1` 的主问题不是缺少普通 pair，而是系统此前把矩阵局部号同时表达成：

- 正确的结构化关系：`21QD` 行端点 -> `21n + 局部号`
- 错误的裸 ordinary 半边：`? -> 127`、`127 -> ?`

本轮完成的最小实现：

- 在 [wire_components.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/wire_components.py) 中新增 `input_matrix_wire_mapping` 子模式。
- 抽取条件保持窄门槛：
  - 至少两个 `\d+-21n` 列前缀
  - 至少两个 `\d+-21QD\d+` 行端点
  - 至少两个三位局部号
  - 局部号必须同时落在合法列前缀下方和同行 QD 端点右侧
- 产物为 `pair_kind=wire_component_mapping`、`status=pass`、`confidence=0.95`。
- evidence 显式记录 `component_submode=input_matrix_wire_mapping`、prefix/row/local 的 text id、坐标、row/column band。

随后在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 加了与 terminal/header table 覆盖逻辑一致的后处理：

- 若普通 `ordinary_pair` 使用的 text id 已被 `input_matrix_wire_mapping` 的 `local_number_text_id` 覆盖，则只标记为 `discard`。
- 设置 `ordinary_pair_eligible=False` 和 `covered_by_input_matrix_wire_mapping=True`。
- 不删除 `wire_component_mapping`，不隐藏结构化图关系，不扩 CLI。

fresh second-set 证据：

- `.tmp/phase66_input_matrix_cover_second/2_2`
- `pair_count=1575`
- `issue_count=303`
- `pair_kind` 分布：
  - `ordinary_pair=1031`
  - `wire_component_mapping=168`
  - `table_mapping=176`
  - `semantic_mapping=157`
  - `component_mapping=20`
  - `continuation=20`
  - `bridge_mapping=3`
- `covered_input_matrix_ordinary=336`
- `S0008 input_matrix_count=44`
  - `1-21QD12 -> 1-21n127`
  - `1-21QD28 -> 1-21n212`
  - `1-21QD44 -> 1-21n228`
- `S0012 input_matrix_count=38`
  - `3-21QD6 -> 3-21n127`
  - `3-21QD22 -> 3-21n212`
  - `3-21QD38 -> 3-21n228`
- `S0008/S0012` 上 `127/212/228` 的 non-discard 裸 ordinary 半边为 `0`。

fresh first-set 非回归：

- `.tmp/phase66_input_matrix_cover_first/...`
- `pair_count=1523`
- `issue_count=458`
- `input_matrix_wire_mapping=0`
- `covered_input_matrix_ordinary=0`

裁决：

- second-set `08/12` 开入矩阵已从 `? -> 127` 这类裸数字 review 转为结构化 `wire_component_mapping/pass`。
- `issue_count 471 -> 303` 是由被结构化关系覆盖的 ordinary 半边降级造成，不是隐藏或删除结构化关系。
- first-set 未出现 input-matrix 误触发，说明该门槛仍足够窄。

## 106. 2026-07-06 小型端口盒 small_port_box_component：AK / A' / KZKK / JR 结构化映射

本轮只读审计确认，任务书新增明确的 `small_port_box_component` 仍是空白能力：

- `component_diagrams.py` 只有 `strip_two_port_component` 和 `kk_multi_port_component`。
- first `S0022 / 21 元件接线图1.dwg` 与 second `S0019 / 19 元件接线图1.dwg` 都存在同构小端口盒。
- 真实文本证据包括：
  - 本体：`AK`、`A'`、`KZKK`、`JR`
  - 块内端口：`1/2` 或 `1/2/3/4`
  - 外部端：`JD1`、`A'-1`、`AK-2`、`JD6`、`JD8`、`K-5`、`JD3`、`K-6`、`K-3`、`K-4`
- 当前系统此前没有输出这些 `component_mapping`，小端口号仍只表现为被 discard 的普通端口线噪声。

本轮实现：

- 新增 [component_diagrams.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/component_diagrams.py) 中的 `extract_small_port_box_component_pairs()`。
- 在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 的 `ComponentDiagramExtractor` 分支接入该子模式。
- 抽取门槛保持窄：
  - 仅 `元件接线图 / horizontal_component / ComponentDiagramExtractor`
  - 仅 `KK1P`、`KK2P`、`JR-01` 小盒块
  - 本体必须是纯字母/撇号形态，例如 `AK`、`A'`、`KZKK`、`JR`
  - 块内端口集合必须完整
  - 外部端必须在端口上方或下方邻近位置
- 输出为 `pair_kind=component_mapping`、`status=pass`、`confidence=0.95`。
- evidence 记录 `component_submode=small_port_box_component`、本体/端口/外部端 text id、block id/name、bbox、supporting line ids。

fresh first-set 证据：

- `.tmp/phase67_small_port_first_v2/...`
- `pair_count=1533`
- `issue_count=458`
- `component_mapping=85`
- `small_port_box_component=10`
- first `S0022` 目标全部命中：
  - `AK-1 -> JD1`
  - `AK-2 -> A'-1`
  - `A'-1 -> AK-2`
  - `A'-2 -> JD6`
  - `KZKK-1 -> JD8`
  - `KZKK-2 -> K-5`
  - `KZKK-3 -> JD3`
  - `KZKK-4 -> K-6`
  - `JR-1 -> K-3`
  - `JR-2 -> K-4`

fresh second-set 证据：

- `.tmp/phase67_small_port_second/2_2`
- `pair_count=1585`
- `issue_count=303`
- `component_mapping=30`
- `small_port_box_component=10`
- second `S0019` 命中同一组 small-port 目标。
- Phase52 开入矩阵未回退：
  - `input_matrix_wire_mapping=168`
  - `covered_input_matrix_ordinary=336`
  - `1-21QD12 -> 1-21n127` 与 `3-21QD6 -> 3-21n127` 仍命中。

验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py` -> `16 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "component or kk or strip"` -> `9 passed, 11 deselected`
- `python -m pytest -q` -> `225 passed`

裁决：

- `small_port_box_component` 已从“未实现”推进到 first/second 真实样本双命中。
- 本轮没有通过降低 issue_count 来证明正确性；结构化关系新增后 project `issue_count` 保持稳定。
- `4输出/6输出` 的 KK2P/KK3P 端口绑定偏差仍未闭合，下一刀应单独处理，不能把本轮 small-port 视为 ComponentDiagramExtractor 全完成。

## 107. 2026-07-06 KK2P/KK3P 输出槽位几何绑定：4输出 / 6输出 端口纠偏

本轮只读审计确认，`4输出/6输出` 的残留偏差不是规则层或报告层造成，而是 `kk_multi_port_component` 抽取阶段没有采用任务书定义的固定端口槽位：

- 旧实现把 KK2P/KK3P 端口当作散点处理，对每个端口独立寻找最近水平线和线段远端。
- 真实 `4输出` 是左右两列、上下两排：左上 `1`、左下 `2`、右上 `3`、右下 `4`。
- 真实 `6输出` 是三列、上下两排：上排 `1/3/5`，下排 `2/4/6`。
- 因此旧产物会把同一行左右列外部端互换，并漏掉上排端口；代表偏差包括 `5DK-2 -> 5FD1`、`5DK-4 -> 5FD25`、`1-2ZKK-2 -> 1-2n721`、`1-2ZKK-4 -> 1-2n719`。

本轮实现：

- 在 [component_diagrams.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/component_diagrams.py) 中为 KK multi-port 增加固定槽位解释。
- `KK2P` 端口按 2 列 x 2 行绑定：`1/2` 属左列，`3/4` 属右列，奇数端口找同列上方外部端，偶数端口找同列下方外部端。
- `KK3P` 端口按 3 列 x 2 行绑定：`1/2`、`3/4`、`5/6` 分属三列。
- `_nearest_kk_external_endpoint()` 不再以“水平线远端”决定外部端，而是按同列 x 和上/下方向选择端点。
- `_nearest_kk_slot_supporting_group()` 保留水平线证据，确保映射仍有支撑线，不变成纯文本近邻。
- 单测 [test_component_diagrams.py](/F:/workspace/XJToolkit/tests/unit/test_component_diagrams.py) 改为真实两排几何，并显式断言 `5DK-2 -> 5FD25`、`5DK-4 -> 5FD1`、`1-2ZKK-4 -> 1-2n720` 等目标。

fresh first-set 证据：

- `.tmp/phase68_kk_slot_first/...`
- `pair_count=1552`
- `issue_count=458`
- `component_mapping=104`
- `kk_multi_port_component=36`
- first `S0022 / 21 元件接线图1.dwg` 目标全命中：
  - `5DK-1 -> ZD12`
  - `5DK-2 -> 5FD25`
  - `5DK-3 -> ZD4`
  - `5DK-4 -> 5FD1`
  - `1-2ZKK-1 -> 1-2UD1`
  - `1-2ZKK-2 -> 1-2n719`
  - `1-2ZKK-3 -> 1-2UD3`
  - `1-2ZKK-4 -> 1-2n720`
  - `1-2ZKK-5 -> 1-2UD5`
  - `1-2ZKK-6 -> 1-2n721`
- 旧错配不再作为 pass `component_mapping`：
  - `5DK-2 -> 5FD1`
  - `5DK-4 -> 5FD25`
  - `1-2ZKK-2 -> 1-2n721`
  - `1-2ZKK-4 -> 1-2n719`

fresh second-set 证据：

- `.tmp/phase68_kk_slot_second/2_2`
- `pair_count=1601`
- `issue_count=303`
- `component_mapping=46`
- `kk_multi_port_component=28`
- second `S0019 / 19 元件接线图1.dwg` 代表目标命中：
  - `1-21DK2-1 -> ZD8`
  - `1-21ZKK-2 -> 1-21n715`
- second input-matrix 非回归保持：
  - `input_matrix_wire_mapping=168`
  - `covered_input_matrix_ordinary=336`

验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py -k "kk_multi_port"` -> `5 passed`
- `python -m pytest -q tests\unit\test_component_diagrams.py` -> `16 passed`
- `python -m pytest -q tests\unit\test_wire_components.py -k "input_matrix"` -> `2 passed, 4 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "component or kk or strip"` -> `9 passed, 11 deselected`
- `python -m pytest -q` -> `225 passed`

裁决：

- `4输出/6输出` 的 KK2P/KK3P 端口绑定已从“最近线段远端”收口为任务书定义的固定槽位语义。
- 本轮新增的是结构化 `component_mapping` 真实命中，不靠隐藏 issue 或移除关系降低审计数；first `issue_count=458`、second `issue_count=303` 均保持稳定。
- 下一刀不应继续扩大 KK 规则面，除非先有新的人工标注偏差；更合适的方向是 acceptance suite 结构化 golden 口径，或回到 Phase51 packaged sidecar/exe smoke。

## 108. 2026-07-06 CLP strip component mapping：FJL 双端口组件从 KLP 扩展到 CLP，并刷新验收红线

只读审计确认，`strip_two_port_component` 的几何门槛已经足够窄：必须在 `元件接线图 / ComponentDiagramExtractor` 下同时具备 `FJL-25-2A_Mirror` 块内 `1/2` 端口、同列本体、上下合法外部端点和支撑竖线。本轮真实漏检不是普通候选或 rules 层问题，而是本体识别只接受 `KLP`，漏掉了同一几何形态的 `CLP`。

本轮实现：

- 在 [component_diagrams.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/component_diagrams.py) 中将 strip 本体正则从 `KLP` 扩展为 `KLP|CLP`。
- 在 [test_component_diagrams.py](/F:/workspace/XJToolkit/tests/unit/test_component_diagrams.py) 增加 CLP/FJL 真实几何风格单测，覆盖 `3-21CLP7-1 -> 3-21CD43`、`3-21CLP7-2 -> 3-21n419`。
- 在 [second_set_component_terminal_subset.json](/F:/workspace/XJToolkit/tests/fixtures/acceptance_real_subset/second_set_component_terminal_subset.json) 中把 S0020 旧 `ordinary_pair/review` 裸数字 golden 刷新为 `3-21CLP2..7` 的 `component_mapping/pass/pair_key` 级 golden。
- 同步更新 acceptance integration 的 synthetic real-second 项目，避免 suite 测试仍造旧 ordinary rows。

fresh first-set 证据：

- `.tmp/phase69_clp_strip_first/...`
- `pair_count=1586`
- `issue_count=441`
- `component_mapping=138`
- `strip_two_port_component=92`
- first `S0023 / 22 元件接线图2.dwg` 命中：
  - `3-2CLP5-1 -> KD16`
  - `3-2CLP5-2 -> 3-2n414`
- old `* -> 414` ordinary rows 已为 `discard`，说明消费发生在结构化 component mapping 生成之后。

fresh second-set 证据：

- `.tmp/phase69_clp_strip_second/2_2`
- `pair_count=1637`
- `issue_count=285`
- `component_mapping=82`
- `strip_two_port_component=44`
- second `S0020 / 20 元件接线图2.dwg` 命中：
  - `3-21CLP7-1 -> 3-21CD43`
  - `3-21CLP7-2 -> 3-21n419`
- old `43 -> 419` ordinary rows 已为 `discard`。
- Phase54 KK 红线仍命中：
  - `5DK-2 -> 5FD25`
  - `1-2ZKK-2 -> 1-2n719`
  - `1-21DK2-1 -> ZD8`
  - `1-21ZKK-2 -> 1-21n715`
- Phase52 input matrix 红线保持：
  - `input_matrix_wire_mapping=168`
  - `covered_input_matrix_ordinary=336`

验收红线：

- `evaluate-acceptance-suite` 在 `.tmp/phase69_clp_strip_second/2_2` 上恢复 required `3/3`，`acceptance_passed=True`。
- case metrics：
  - fault-injected mini：expected/matched `16/16`
  - real second component/terminal：expected/matched `18/18`
  - real second S0024 terminal：expected/matched `6/6`
  - 三个 case precision/recall 均为 `1.0`，missing/unexpected 均为空。

验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py` -> `17 passed`
- `python -m pytest -q tests\unit\test_component_diagrams.py tests\integration\test_analyze_project.py -k "component or kk or strip"` -> `26 passed, 11 deselected`
- `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `5 passed`
- `python -m pytest -q` -> `226 passed`

裁决：

- CLP strip 已从裸数字 ordinary review 语义升级为结构化 `component_mapping/pass`；本轮 issue_count 下降来自旧 ordinary 噪声被结构化关系覆盖，不是隐藏或删除 component relation。
- acceptance suite 的 S0020 golden 已跟上结构化口径，但 pair evidence 级 golden 仍未支持；后续如果需要更细验收，应单独扩 evaluator，而不是混入 extractor 切片。

## 109. 2026-07-06 背板虚拟表格跨页作用域：保留 table_mapping，critical 改为 review

只读审计和 phase69 产物核查确认，first-set 剩余 `66` 个 `critical R-CROSS-PAGE-CONFLICT` 全部来自 `backplate_virtual_table`。代表样本：

- `S0018 / 17 差动保护背板图.dwg`
- `NDY306A-3 -> 1QD1`
- 同一逻辑表头行在其他背板页还映射到 `1-2QD1`、`3-2QD1`、`5FD1`
- evidence 中明确有：
  - `mapping_mode=backplate_virtual_table`
  - `source_block_name=WBH-812E-E1SA-101` 或 `WBH-813E-E1SH-101`
  - `header_prefix=NDY306A`
  - `row_number=3`

裁决：

- 这些关系仍然是有效的结构化 `table_mapping/pass`，必须保留在图关系中参与审计。
- 但同型背板插件表格的 `header_prefix + row_number` 是局部表格逻辑端，在不同背板页/装置作用域下复用时，不应按“全项目同名左值必须唯一右值”直接打成 critical。
- 因此本轮只调整 rules 解释：`backplate_virtual_table` 跨页多右值保留为 `R-CROSS-PAGE-CONFLICT`，但 severity 改为 `review`，并标记 `one_to_many_classification=backplate_table_scope_review`。

本轮实现：

- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 中为 `_run_cross_page_conflict()` 增加背板虚拟表格作用域判断。
- 新增 `_is_backplate_virtual_table_scope_review()` 和 `_table_mapping_evidence()`，只匹配 `pair_kind=table_mapping` 且 `table_mapping.mapping_mode=backplate_virtual_table` 的 linked pairs。
- 普通 `table_mapping`、`component_mapping` 跨页多右值仍保持原 critical conflict 行为。
- 在 [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py) 增加 `NDY306A-3` 风格单测，证明背板虚拟表格被重分类为 review，而 generic table mapping 旧测试仍保持 conflict。

fresh first-set 证据：

- `.tmp/phase70_backplate_scope_first/...`
- `pair_count=1586`
- `issue_count=441`
- severity：
  - `critical=0`
  - `review=435`
  - `minor=6`
- rules：
  - `R-CROSS-PAGE-CONFLICT=66`
  - 这 66 条全部为 `backplate_table_scope_review`
- pair_kind 未漂移：
  - `ordinary_pair=943`
  - `table_mapping=299`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `continuation=68`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- 代表 `table_mapping/pass` 仍保留：
  - `NDY306A-3 -> 1QD1`
  - `NDY306A-3 -> 1-2QD1`

fresh second-set 证据：

- `.tmp/phase70_backplate_scope_second/2_2`
- `pair_count=1637`
- `issue_count=285`
- severity：全部 `review`
- `wire_component_mapping=168`
- `covered_input_matrix_ordinary=336`
- 代表目标仍命中：
  - `3-21CLP7-1 -> 3-21CD43`
  - `1-21ZKK-2 -> 1-21n715`

验收红线：

- `.tmp/phase70_backplate_scope_acceptance`
- required `3/3`
- `acceptance_passed=True`
- case metrics：
  - fault-injected mini：expected/matched `16/16`
  - real second component/terminal：expected/matched `18/18`
  - real second S0024 terminal：expected/matched `6/6`
  - 三个 case precision/recall 均为 `1.0`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "cross_page or table_mapping or component_mapping or one_to_many or many_to_one or semantic_mapping"` -> `18 passed, 26 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `44 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
- `python -m pytest -q` -> `227 passed`

裁决：

- 本轮没有通过降低召回或移除图关系来让结果“好看”；`issue_count` 与 `pair_count` 均保持不变。
- 改善点是 severity/解释层：真实正确样本不再因背板表格局部作用域复用出现 critical hard-error 洪峰。
- 下一刀仍应先只读审计，可在 terminal_header_table 多端 review、terminal bare local numeric、wire inline split 或 Phase51 packaged exe smoke 中选一个独立切片。

## 110. 2026-07-06 端子表头表格多端语义：保留 table_mapping，泛化一对多/多对一改为专用 review

只读审计确认，second-set `S0023 / 23 右侧端子图1.dwg` 中多条 `terminal_header_table` 结构化表格映射已经抽取正确，但 rules 层仍按泛化 one-to-many / many-to-one 文案解释。

代表样本：

- `I0223 / PTMR0042 + PTMR0043`
- `1-21QD1 -> 1-21n116`
- `1-21QD1 -> 1-21n524`
- evidence 中明确有：
  - `mapping_mode=terminal_header_table`
  - `header_prefix=1-21QD`
  - `row_number=1`
  - `logical_endpoint=1-21QD1`
  - 两条 pair 分别来自 `left_endpoint` 与 `right_endpoint`

共享端点代表样本：

- `I0267 / PTM0042 + PTMR0096`
- `1-21GD3 -> 1-21n212`
- `1-21QD28 -> 1-21n212`
- evidence 中两条 pair 共享同一端子文本 `T4341` 与坐标 `(156.0000039522472, 133.5)`，分别位于 `1-21GD` 右列与 `1-21QD` 左列。

裁决：

- 这些关系仍是有效的结构化 `table_mapping/pass`，必须保留在图关系中参与审计。
- 但同一端子表行的左右端列、以及同一端子文本被相邻表头行共享时，不应只输出泛化“一对多待复核 / 多对一配对”。
- 因此本轮只调整 rules 解释：issue 仍保留为 review，但增加 `terminal_header_table_multi_endpoint_review` 与 `terminal_header_table_shared_endpoint_review` 分类。

本轮实现：

- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 中为 `_run_one_to_many()` 增加 `terminal_header_table` 多端行判断。
- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 中为 `_run_many_to_one()` 增加 `terminal_header_table` 共享端点判断。
- 触发门槛保持很窄：同页、高置信 `table_mapping`、`mapping_mode=terminal_header_table`、有效行号序列；one-to-many 还要求同一 `logical_endpoint + row_number` 且左右端列同时出现；many-to-one 还要求共享端点文本 id 或坐标一致。
- 在 [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py) 增加两个真实样本风格单测。

fresh first-set 证据：

- `.tmp/phase71_terminal_header_table_first/...`
- `pair_count=1586`
- `issue_count=441`
- pair_kind 未漂移：
  - `ordinary_pair=943`
  - `table_mapping=299`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `continuation=68`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- 新分类：
  - `terminal_header_table_multi_endpoint_review=8`
  - `terminal_header_table_shared_endpoint_review=7`

fresh second-set 证据：

- `.tmp/phase71_terminal_header_table_second/2_2`
- `pair_count=1637`
- `issue_count=285`
- pair_kind 未漂移：
  - `ordinary_pair=1031`
  - `table_mapping=176`
  - `component_mapping=82`
  - `semantic_mapping=157`
  - `continuation=20`
  - `wire_component_mapping=168`
  - `bridge_mapping=3`
- 新分类：
  - `terminal_header_table_multi_endpoint_review=44`
  - `terminal_header_table_shared_endpoint_review=22`
- 代表 issue：
  - `I0223` 标题改为 `端子表左右列映射待复核`
  - `I0267` 标题改为 `端子表共享端点待复核`

验收红线：

- `.tmp/phase71_terminal_header_table_acceptance`
- required `3/3`
- `acceptance_passed=True`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "one_to_many or many_to_one or table_mapping or component_mapping or cross_page"` -> `16 passed, 30 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `46 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
- `python -m pytest -q` -> `229 passed`

裁决：

- 本轮没有改抽取器、没有删 `table_mapping`、没有扩 CLI/UI，也没有通过减少 issue_count 让报告变好看。
- 改善点是规则解释层：端子表头表格的真实多端关系现在有专用 review 语义，便于人工按表格行列复核。
- 下一刀更适合继续只读审计 terminal bare local numeric discard，或切到 wire inline split half-pair；Phase51 packaged sidecar smoke 仍是独立交付链。

## 111. 2026-07-07 端子图连续行号列：裸本地序号不再参与 ordinary pair 竞争

只读审计确认，最新真实样本中仍有一类稳定伪问题：端子图表格行号 / 序号列被当成普通端子数字候选，进而形成 `ordinary_pair/review`。

代表样本：

- first-set `S0025 / 24 左侧端子图1.dwg`：`PT0027` 为 `8 -> ?`，同列上下文是 `13,12,11,10,9,8,7,6,5,4,3`。
- first-set `S0027 / 26 右侧端子图1.dwg`：`? -> 4`，同列上下文是 `9,8,7,6,5,4,3,2,1`。
- second-set `S0022 / 22 左侧端子图2.dwg`：`9 -> 116`，左侧 `9` 是本地行号，右侧 `3-21n116` 才是完整端子文本。
- second-set `S0021 / 21 左侧端子图1.dwg`：`69 -> 318`，`69` 是连续行号列，`3-21n318` 是同行完整端子文本。

裁决：

- 这类裸数字不是跨页端子端点，也不应作为普通 `ordinary_pair` 的左右候选参与竞争。
- 它也不是应当隐藏的关系；应在候选层保留可解释拒绝原因，转入语义/说明证据通道。
- 完整派生端子文本，例如 `3-21n116`、`3-21n318`，必须继续作为可用 numeric candidate 保留。

本轮实现：

- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 中新增端子图连续行号列检测。
- 检测门槛保持窄口径：
  - 只作用于 `屏端子图` 非 vertical line group。
  - 候选文本必须是裸 `1..99`，且原文等于候选值。
  - 按同 sheet、近似同 x 列聚合。
  - 按 y 连续扫描，要求相邻 y 步进不超过 `6.0`、x 漂移不超过 `1.0`、数字相邻。
  - 只有连续 run 长度至少 `5` 才拒绝整列。
- 拒绝原因写为 `terminal_row_number_local_numeric`，候选通道写为 `semantic_channel`。
- 行号列检测放在 `terminal_semantic_local_numeric` 之前，使混有语义行的完整连续序号列先按更具体的 row-index 语义归类。
- 在 [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py) 增加 `13..18` 行号列单测，证明行号被拒绝而同行完整端子仍留在 numeric 通道。

fresh first-set 证据：

- `.tmp/phase72_terminal_row_number_first_v2/...`
- `pair_count=1586`，保持不变。
- `issue_count=441 -> 361`
- pair_kind：
  - `ordinary_pair=836`
  - `continuation=175`
  - `table_mapping=299`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- 候选拒绝：
  - `terminal_row_number_local_numeric=289`
  - `terminal_semantic_local_numeric=16`
- issue 变化：
  - `R-PAIR-LOW-CONFIDENCE=58 -> 12`
  - `R-PAIR-MISSING-SIDE=230 -> 196`
- 点名伪 pair 已消失：
  - `S0025 8 -> ?`
  - `S0027 ? -> 4`

fresh second-set 证据：

- `.tmp/phase72_terminal_row_number_second_v2/2_2`
- `pair_count=1637`，保持不变。
- `issue_count=285 -> 198`
- pair_kind：
  - `ordinary_pair=849`
  - `continuation=202`
  - `table_mapping=176`
  - `component_mapping=82`
  - `semantic_mapping=157`
  - `wire_component_mapping=168`
  - `bridge_mapping=3`
- 候选拒绝：
  - `terminal_row_number_local_numeric=418`
  - `terminal_semantic_local_numeric=9`
- issue 变化：
  - `R-PAIR-LOW-CONFIDENCE=66 -> 3`
  - `R-PAIR-MISSING-SIDE=149 -> 125`
- 点名伪 pair 已消失：
  - `S0022 9 -> 116`
  - `S0021 69 -> 318`
- 红线未漂移：
  - `wire_component_mapping=168`
  - `table_mapping=176`
  - `component_mapping=82`
  - input matrix 代表目标仍命中。

验收红线：

- `.tmp/phase72_terminal_row_number_acceptance_v2`
- required `3/3`
- `acceptance_passed=True`

验证：

- `python -m pytest -q tests\unit\test_terminal_candidates.py` -> `24 passed`
- `python -m pytest -q tests\unit\test_page_extractors.py` -> `5 passed`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "missing_side or low_confidence or continuation or semantic_mapping"` -> `14 passed, 32 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "terminal or row_lock or run_audit"` -> `5 passed, 15 deselected`
- `python -m pytest -q` -> `230 passed`

裁决：

- 本轮没有移除结构化 `table_mapping/component_mapping/wire_component_mapping`，也没有扩 CLI/UI。
- 改善点是候选语义：端子图行号列不再伪装成跨页端子候选，因而不再制造低置信和缺边伪 issue。
- 下一刀可继续只读审计 wire inline split half-pair，或回到 Phase51 packaged sidecar/exe smoke；两者仍应分开推进。

## 112. 2026-07-07 inline 数字断线桥接：用 TEXT bbox 覆盖 gap 而不是只看插入点

只读审计确认，Phase72 后仍有一类真实 wire path 残差：同一根水平导线被 inline 数字文本切断，但线组桥接没有恢复成同一条 chain，于是进入 `R-PAIR-MISSING-SIDE / complementary_half_pair`。

代表样本：

- second-set `08 测控1开入回路图1.dwg`：旧 `PW0251 ? -> 114` 与 `PW0252 114 -> ?` 共享文本 `T0355=114`，两段线 gap 约 `12.5`。
- first-set `08 差动保护及信号回路.dwg`：旧 `PW0220 ? -> 112` 与 `PW0221 112 -> ?` 同构。
- first-set `09 高后备保护及信号回路.dwg`：旧 `PW0238 ? -> 123` 与 `PW0239 123 -> ?` 同构。

根因：

- `_has_inline_numeric_bridge()` 已有 inline numeric bridge 逻辑，但只检查 `text.insert_x / insert_y` 是否落在 gap 内。
- 真实 DWG 的 TEXT 插入点常位于左线端附近，文字 bbox 才横跨断点间隙。例如 second `T0355=114` 的 insert x 约 `90.62`，bbox x 约 `[90.62, 95.27]`，左线 end x 为 `92.5`，右线 start x 为 `105.0`。
- 插入点低于 `previous_end_axis - 1.0` 时旧逻辑直接跳过，虽然文字 bbox 已经覆盖断点边缘。

本轮实现：

- 在 [line_groups.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/line_groups.py) 中把 inline bridge 的轴向命中条件改为 TEXT bbox 区间与扩展 gap 区间相交。
- horizontal/grid 使用 `bbox_min_x/bbox_max_x` 判断轴向覆盖，cross-axis 使用 bbox y 中心；vertical 对应使用 y 区间和 bbox x 中心。
- 保留原有 `inline_numeric_bridge_gap` 与 cross-axis tolerance，不改 rules、不删除 issue、不扩 CLI/UI。
- 在 [test_line_groups.py](/F:/workspace/XJToolkit/tests/unit/test_line_groups.py) 增加真实形态回归：`114` 的 insert point 在左线端附近、bbox 覆盖 gap，grid 行带应桥接 `L1/L2`。

fresh first-set 证据：

- `.tmp/phase73_inline_bridge_first/...`
- `pair_count=1550`
- `issue_count=327`
- pair_kind：
  - `ordinary_pair=800`
  - `wire_component_mapping=32`
  - `component_mapping=138`
  - `continuation=175`
  - `semantic_mapping=103`
  - `bridge_mapping=3`
  - `table_mapping=299`
- `complementary_half_pair`：`35 -> 2`
- 点名页级结果：
  - `08 差动保护及信号回路.dwg`：`complementary_half_pair=0`
  - `09 高后备保护及信号回路.dwg`：`complementary_half_pair=0`
  - `10 低后备保护及信号回路.dwg`：`complementary_half_pair=0`
  - 剩余 2 条位于 `07 网络通讯回路图.dwg`，gap 约 `4.7358`，属于后续独立短 gap 边界。

fresh second-set 证据：

- `.tmp/phase73_inline_bridge_second/2_2`
- `pair_count=1462`
- `issue_count=191`
- pair_kind：
  - `ordinary_pair=674`
  - `wire_component_mapping=168`
  - `component_mapping=82`
  - `continuation=202`
  - `semantic_mapping=157`
  - `bridge_mapping=3`
  - `table_mapping=176`
- `complementary_half_pair`：`6 -> 0`
- 点名页级结果：
  - `08 测控1开入回路图1.dwg`：`complementary_half_pair=0`
  - `12 测控2开入回路图1.dwg`：`complementary_half_pair=0`
- 红线未漂移：
  - `wire_component_mapping=168`
  - `input_matrix_wire_mapping=168`
  - `table_mapping=176`
  - `component_mapping=82`

验收红线：

- `.tmp/phase73_inline_bridge_acceptance`
- required `3/3`
- `acceptance_passed=True`

验证：

- `python -m pytest -q tests\unit\test_line_groups.py` -> `9 passed`
- `python -m pytest -q tests\unit\test_wire_components.py -k "inline_klp or input_matrix"` -> `5 passed, 1 deselected`
- `python -m pytest -q tests\unit\test_page_extractors.py` -> `5 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or inline_klp or run_audit"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `231 passed`

裁决：

- 本轮修的是 CAD TEXT 几何解释：插入点不等于文字占位范围。
- 改动没有隐藏 issue；first 剩余 2 条 `07 网络通讯回路图.dwg` 半链继续显式留在 review。
- 下一刀若继续 wire 主链，应先只读审计这 2 条短 gap 半链是否需要另一个线组边界规则；否则可转向 terminal/table/component 的规则语义残差。

## 113. 2026-07-07 terminal header table 语义端排除：I0/3U0 保留语义证据但不进 table_mapping endpoint

只读恢复确认，当前最新代码已闭合 `input_matrix_wire_mapping`、`small_port_box_component`、`kk_multi_port_component`、`strip_two_port_component(KLP/CLP)` 和 inline wire bbox bridge；本轮不再把这些旧 Phase52/53/54/55 backlog 当作待实现 extractor。

本轮先刷新 [任务书](/F:/workspace/XJToolkit/doc/任务书.md) 状态：

- Phase52/53/54/55 的“未实现/错配”旧 backlog 已改为已完成或过期。
- active backlog 收缩为三条：`terminal_header_table semantic endpoint exclusion`、`inline KLP 116 residual suppression`、`component-prefixed 218 residual suppression`。
- 背板表格和 component/table mapping branch 后续问题改写为 rules/acceptance 质量问题，不再写成 extractor 缺失。

真实缺陷：

- second-set `S0021 / 21 左侧端子图1.dwg` 中，`I0` 同行靠近两个 terminal header table 行号。
- Phase73 输出把它误当成 endpoint：
  - `PTM0008 3-21ID9 -> I0 table_mapping/pass`
  - `PTM0017 3-21QD7 -> I0 table_mapping/pass`
- 同一文本在 terminal candidates 中已经是 `semantic_channel/not_numeric`，说明普通端子候选层语义正确，漏点在 `TableExtractor` 的 endpoint 谓词。

本轮实现：

- 在 [table_extractor.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/table_extractor.py) 中为 table endpoint eligibility 增加语义代号排除：`I0/I0'/IA/UA/UB/UC/UN/3U0/3U0'`。
- 只影响 `_looks_like_table_endpoint()`，不删除 texts，不改 terminal candidates，不改 rules，不改 CLI/UI。
- 在 [test_table_extractor.py](/F:/workspace/XJToolkit/tests/unit/test_table_extractor.py) 增加负向断言：同一行出现 `3-21n701` 与 `I0` 时，只输出 `3-21ID1 -> 3-21n701`，不输出 `3-21ID1 -> I0`。

fresh second-set 证据：

- `.tmp/phase74_terminal_header_semantic_second/2_2`
- `pair_count=1460`
- `issue_count=188`
- pair_kind：
  - `ordinary_pair=674`
  - `wire_component_mapping=168`
  - `component_mapping=82`
  - `continuation=202`
  - `semantic_mapping=157`
  - `bridge_mapping=3`
  - `table_mapping=174`
- 点名 pair 已消失：
  - `3-21ID9 -> I0` 的 `table_mapping/pass` 数量为 `0`
  - `3-21QD7 -> I0` 的 `table_mapping/pass` 数量为 `0`
- `semantic_table_mapping_pass_endpoint_count=0`
- `I0` 仍保留语义证据：`S0021` 中 `8` 条 terminal candidate 为 `semantic_channel/not_numeric`。
- 正常 terminal header table 关系未回退：
  - `3-21ID9 -> 3-21n707` 仍为 `table_mapping/pass`
  - `3-21QD7 -> 3-21n128` 仍为 `table_mapping/pass`
  - terminal header table by sheet：`S0021=32`、`S0022=7`、`S0023=112`、`S0024=23`
- 红线未漂移：
  - `wire_component_mapping=168`
  - `input_matrix_wire_mapping=168`
  - `component_mapping=82`

验证：

- `python -m pytest -q tests\unit\test_table_extractor.py` -> `14 passed`
- `python -m pytest -q tests\unit\test_page_extractors.py` -> `5 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "terminal_header_table or table_extractor"` -> `3 passed, 17 deselected`
- `python -m pytest -q` -> `232 passed`

裁决：

- 本轮是 table extractor 语义端排除，不是 rules 降噪或关系隐藏。
- `table_mapping` 总数从 Phase73 second 的 `176` 变为 `174`，仅少掉两条 `I0` 误 endpoint；正常 terminal header table 和结构化 wire/component 红线保持。
- 下一轮候选只剩：`inline KLP 116 residual suppression`、`component-prefixed 218 residual suppression`、`backplate/component mapping rules semantics`。

## 114. 2026-07-07 component-prefixed 218 residual suppression：结构化元件分区映射覆盖裸局部号

只读审计确认，`component_prefixed_signal_circuit` extractor 已经闭合，first-set `S0017 / 16 高低压侧操作箱信号回路.dwg` 能产出高置信结构化关系；剩余问题不是重新实现 extractor，而是旧普通 PairBuilder 仍把同一个局部号文本 `218` 作为裸 ordinary half-pair 报 review。

真实缺陷：

- first-set `S0017` 中，结构化关系已存在：
  - `PWM0008 1-2n218 -> 1-4YD1 wire_component_mapping/pass/confidence=0.95`
  - `PWM0021 3-2n218 -> 3-4YD1 wire_component_mapping/pass/confidence=0.95`
- 同页旧普通 residual 仍出现：
  - `PW0532 ? -> 218 review`
  - `PW0534 ? -> 218 review`
- 这些 `218` 是元件分区内局部号，已经通过 `1-2n` / `3-2n` 前缀合成完整逻辑端；继续裸用为跨页端子会制造伪 `R-PAIR-MISSING-SIDE`。

本轮实现：

- 在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 中把 input matrix 局部号覆盖逻辑扩展为通用 `wire_component_mapping` 覆盖逻辑。
- `input_matrix_wire_mapping` 仍覆盖矩阵局部号文本；`component_prefixed_signal_circuit` 只覆盖 `evidence.local_number_text_id`，不覆盖外侧端子文本。
- 被覆盖的普通 pair 标记为 `discard`、`confidence_bucket=low`、`ordinary_pair_eligible=False`，并写入 `covered_by_component_prefixed_signal_circuit=True`。
- 不删除 `wire_component_mapping`，不改 rules，不扩 CLI/UI，不按数字 `218` 做全局抑制。
- 在 [test_page_extractors.py](/F:/workspace/XJToolkit/tests/unit/test_page_extractors.py) 增加两条单测：局部号文本被覆盖，外侧端子文本不被覆盖。

fresh first-set 证据：

- `.tmp/phase75_component_218_first/...`
- `pair_count=1550`
- `issue_count=311`
- pair_kind：
  - `ordinary_pair=800`
  - `wire_component_mapping=32`
  - `component_mapping=138`
  - `table_mapping=299`
  - `continuation=175`
  - `semantic_mapping=103`
  - `bridge_mapping=3`
- issue rule：
  - `R-PAIR-MISSING-SIDE=147`
  - `R-CROSS-PAGE-CONFLICT=66`
  - `R-ONE-TO-MANY=44`
  - `R-MANY-TO-ONE=37`
  - `R-PAIR-LOW-CONFIDENCE=12`
  - `R-DUPLICATE-PAIR=5`
- `S0017` 旧 residual 已收口：
  - `PW0532 ? -> 218` 为 `discard`，`covered_by_component_prefixed_signal_circuit=True`，`ordinary_pair_eligible=False`
  - `PW0534 ? -> 218` 为 `discard`，`covered_by_component_prefixed_signal_circuit=True`，`ordinary_pair_eligible=False`
  - `S0017 active ordinary 218 review count=0`
- 结构化目标保持：
  - `PWM0008 1-2n218 -> 1-4YD1` 仍为 `wire_component_mapping/pass/confidence=0.95`
  - `PWM0021 3-2n218 -> 3-4YD1` 仍为 `wire_component_mapping/pass/confidence=0.95`
- 非目标页未被误杀：
  - `S0013` 的 `PW0336 ? -> 218` 仍为 review
  - `S0013` 的 `PW0337 218 -> ?` 仍为 review
  - `S0013` 的 `PW0338 218 -> 212` 仍为 discard

fresh second-set 非回归证据：

- `.tmp/phase75_component_218_second/2_2`
- `pair_count=1460`
- `issue_count=188`
- pair_kind：
  - `ordinary_pair=674`
  - `wire_component_mapping=168`
  - `component_mapping=82`
  - `table_mapping=174`
  - `continuation=202`
  - `semantic_mapping=157`
  - `bridge_mapping=3`
- `input_matrix_wire_mapping_count=168`
- `component_prefixed_signal_circuit_count=0`
- `covered_component_prefixed_discard_count=0`
- 红线保持：
  - `1-21QD34 -> 1-21n218` 仍有 `wire_component_mapping/pass`
  - `3-21QD28 -> 3-21n218` 仍有 `wire_component_mapping/pass`
  - `1-21GD9 -> 1-21n218` 仍有 `table_mapping/pass`
  - `semantic_table_mapping_pass_endpoint_count=0`

验证：

- `python -m pytest -q tests\unit\test_page_extractors.py` -> `7 passed`
- `python -m pytest -q tests\unit\test_wire_components.py -k "component_prefixed_signal or input_matrix"` -> `6 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "component_prefixed_signal_circuit_mapping or run_audit or mixed_source"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `234 passed`

裁决：

- 本轮修的是结构化 `wire_component_mapping` 与旧 ordinary pair 的覆盖语义，不是 extractor 补缺，也不是 issue 隐藏。
- first issue_count 从 Phase73 的 `327` 降到 `311`，来自 `component_prefixed_signal_circuit` 覆盖的局部号 residual 收口；结构化 `wire_component_mapping` 数量保持 `32`。
- 下一轮候选只剩：`inline KLP 116 residual suppression`、`backplate/component mapping rules semantics`。

## 115. 2026-07-07 component split endpoint rules semantics：逗号拆分端点保留关系但改为专用复核分类

只读审计确认，`strip_two_port_component(KLP/CLP)` extractor 本身已经闭合，逗号外部端点也已拆成独立 `component_mapping/pass` 关系。本轮不移除这些关系，也不把 issue 隐藏；目标只是把由逗号拆分文本自然造成的 component fanout / shared endpoint issue，从泛化 branch review 改成更具体的 rules 语义分类。

真实缺陷：

- first-set `S0023 / 22 元件接线图2.dwg` 中，`3-2KLP1-1` 的外部端来自同一原始文本 `3-2QD2,3-2KLP3-1`。
- 结构化关系本身正确且必须保留：
  - `PCM0001 3-2KLP1-1 -> 3-2QD2 component_mapping/pass`
  - `PCM0002 3-2KLP1-1 -> 3-2KLP3-1 component_mapping/pass`
  - `PCM0003 3-2KLP1-2 -> 3-2n116 component_mapping/pass`
  - `PCM0039 1-2KLP1-2 -> 1-2n116 component_mapping/pass`
- 旧 issue 文案只表现为泛化 one-to-many / many-to-one component branch review，不能直接说明“多个端点来自逗号拆分文本组”。

本轮实现：

- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 新增 strip 双端口逗号拆分端点识别 helper。
- `R-ONE-TO-MANY` 对同一 raw comma text 拆出的多个端点输出：
  - title：`组件逗号端点拆分待复核`
  - `one_to_many_classification=component_split_endpoint_group_review`
  - evidence：`component_branch_kind=split_endpoint_group`、`external_endpoint_splits`、`external_endpoint_raw_values`、`external_endpoint_text_ids`、`logical_endpoints`
- `R-MANY-TO-ONE` 对共享端点来自逗号拆分组的邻接输出：
  - title：`组件逗号端点邻接待复核`
  - `many_to_one_classification=component_split_endpoint_group_review`
  - evidence 额外包含 `shared_endpoint`
- 在 [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py) 增加 one-to-many 与 many-to-one 两条专用规则单测。
- 不改 extractor、PairBuilder、acceptance fixture、CLI/UI，也不改变 `component_mapping` 入图。

fresh first-set 证据：

- `.tmp/phase76_component_split_rules_first/...`
- `pair_count=1550`
- `issue_count=311`
- pair_kind 未漂移：
  - `ordinary_pair=800`
  - `component_mapping=138`
  - `table_mapping=299`
  - `wire_component_mapping=32`
  - `continuation=175`
  - `semantic_mapping=103`
  - `bridge_mapping=3`
- rule count 未漂移：
  - `R-CROSS-PAGE-CONFLICT=66`
  - `R-DUPLICATE-PAIR=5`
  - `R-MANY-TO-ONE=37`
  - `R-ONE-TO-MANY=44`
  - `R-PAIR-LOW-CONFIDENCE=12`
  - `R-PAIR-MISSING-SIDE=147`
- 分类变化：
  - `R-ONE-TO-MANY`：`component_split_endpoint_group_review=16`
  - `R-MANY-TO-ONE`：`component_split_endpoint_group_review=12`
- 点名 issue：
  - `I0226` 现在为 `组件逗号端点拆分待复核`，`one_to_many_classification=component_split_endpoint_group_review`，text id `T3623`
  - `I0270` 现在为 `组件逗号端点邻接待复核`，`many_to_one_classification=component_split_endpoint_group_review`，text ids `T3623/T3855`

fresh second-set 非回归证据：

- `.tmp/phase76_component_split_rules_second/2_2`
- `pair_count=1460`
- `issue_count=188`
- pair_kind 未漂移：
  - `ordinary_pair=674`
  - `wire_component_mapping=168`
  - `component_mapping=82`
  - `table_mapping=174`
  - `continuation=202`
  - `semantic_mapping=157`
  - `bridge_mapping=3`
- `split issue count=0`
- 红线保持：
  - `input_matrix_wire_mapping_count=168`
  - `component_prefixed_signal_circuit_count=0`
  - `semantic_table_mapping_pass_endpoint_count=0`
  - `1-21QD34 -> 1-21n218` 仍有 `wire_component_mapping/pass`
  - `3-21QD28 -> 3-21n218` 仍有 `wire_component_mapping/pass`
  - `1-21GD9 -> 1-21n218` 仍有 `table_mapping/pass`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "one_to_many or many_to_one or component_branch or split_endpoint or backplate or terminal_header"` -> `11 passed, 37 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `48 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
- `python -m pytest -q` -> `236 passed`

裁决：

- 本轮是 rules/acceptance 质量问题收口，不是 extractor 缺失，也不是 issue 降噪隐藏。
- `component_mapping/pass` 仍进入图；issue 数量和 pair 分布不漂移，只让 review 文案表达真实成因。
- 下一轮候选收缩为：`backplate virtual table same-sheet one-to-many scope semantics`、`terminal_header_table issue aggregation`、`inline signal page ordinary residual taxonomy guardrail`。

## 116. 2026-07-07 backplate virtual table same-sheet scope review：同页背板虚拟表复用不再泛化成普通一对多

只读审计确认，`backplate_virtual_table` extractor 本身已经能稳定输出 `table_mapping/pass`。Phase56 已把跨页背板虚拟表复用从 critical conflict 改成 `backplate_table_scope_review`，但同页多个背板表格区域复用同一 `header_prefix + row_number` 时，仍落入 generic “一对多待复核”。

真实缺陷：

- first-set `S0021 / 20 非电量保护背板图.dwg` 中，同一页存在两个 `NKR308A` 表格区域：
  - `raw_header_text=NKR308A`
  - `raw_header_text=NKR308A(非电量选配)`
- 两个区域共享同一逻辑端行号，但指向不同外部端，例如：
  - `P0175 NKR308A-1 -> 5FD11 table_mapping/pass`
  - `P0193 NKR308A-1 -> 5FD15 table_mapping/pass`
  - `P0181 NKR308A-7 -> 5KLP1-2 table_mapping/pass`
  - `P0199 NKR308A-7 -> 5KLP5-2 table_mapping/pass`
- 这些关系是背板虚拟表格的同页分区/作用域复用，不应继续只显示为 generic `一对多待复核`。

本轮实现：

- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 的 `_run_one_to_many()` 中新增同页背板虚拟表 scope 分支。
- 新分支只匹配：
  - 全部 pair 都是 `pair_kind=table_mapping`
  - `mapping_mode=backplate_virtual_table`
  - 同一 sheet
  - 存在多个表格区域/作用域证据，例如不同 `raw_header_text`、`header_text_id`、`header_coord` 或 `source_block_name`
- 触发后 issue 仍保留为 `R-ONE-TO-MANY/review`，但标题改为 `背板表格同页作用域待复核`，并写入：
  - `one_to_many_classification=backplate_table_same_sheet_scope_review`
  - `table_mapping_mode=backplate_virtual_table`
  - `backplate_scope_kind=same_sheet_virtual_table`
  - `source_block_names`
  - `header_prefixes`
  - `raw_header_texts`
  - `header_text_ids`
  - `header_coords`
  - `row_numbers`
- 在 [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py) 增加正向单测和负向单测：真实 `NKR308A` 双表区应重分类；同一表区同一 scope 的冲突仍保留 generic review。
- 不改 `table_extractor.py`、PairBuilder、classification/router、acceptance fixture、CLI/UI，也不移除 `table_mapping` 入图。

fresh first-set 证据：

- `.tmp/phase77_backplate_same_sheet_first/...`
- `pair_count=1550`
- `issue_count=311`
- pair_kind 未漂移：
  - `ordinary_pair=800`
  - `table_mapping=299`
  - `continuation=175`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- rule count 未漂移：
  - `R-PAIR-MISSING-SIDE=147`
  - `R-CROSS-PAGE-CONFLICT=66`
  - `R-ONE-TO-MANY=44`
  - `R-MANY-TO-ONE=37`
  - `R-PAIR-LOW-CONFIDENCE=12`
  - `R-DUPLICATE-PAIR=5`
- `R-ONE-TO-MANY` 分类：
  - `backplate_table_scope_review=66`
  - `backplate_table_same_sheet_scope_review=18`
  - `component_split_endpoint_group_review=16`
  - `terminal_header_table_multi_endpoint_review=8`
  - generic `review=2`
- 点名关系保持：
  - `NKR308A-1 -> 5FD11` 仍为 `table_mapping/pass`
  - `NKR308A-1 -> 5FD15` 仍为 `table_mapping/pass`
  - `NKR308A-7 -> 5KLP1-2` 仍为 `table_mapping/pass`
  - `NKR308A-7 -> 5KLP5-2` 仍为 `table_mapping/pass`

fresh second-set 非回归证据：

- `.tmp/phase77_backplate_same_sheet_second/2_2`
- `pair_count=1460`
- `issue_count=188`
- pair_kind 未漂移：
  - `ordinary_pair=674`
  - `continuation=202`
  - `table_mapping=174`
  - `wire_component_mapping=168`
  - `semantic_mapping=157`
  - `component_mapping=82`
  - `bridge_mapping=3`
- terminal header table 既有语义保持：
  - `terminal_header_table_multi_endpoint_review=43`
  - `terminal_header_table_shared_endpoint_review=21`
- `semantic_table_mapping_pass_endpoint_count=0`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "backplate or one_to_many or many_to_one or component_split or terminal_header"` -> `13 passed, 37 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `50 passed`
- `python -m pytest -q tests\unit\test_table_extractor.py -k "backplate" tests\integration\test_analyze_project.py -k "backplate or run_audit or mixed_source"` -> `6 passed, 28 deselected`
- `python -m pytest -q` -> `238 passed`

裁决：

- 本轮是 rules 语义重分类，不是 extractor 补缺，也不是 issue 隐藏。
- 背板虚拟表 `table_mapping/pass` 仍完整进入图；issue_count 和 rule_count 不变，只让同页背板表格复用有可解释分类。
- 下一轮候选：`terminal_header_table issue aggregation`、`inline signal page ordinary residual taxonomy guardrail`、`backplate/component many-to-one scope semantics`。

## 117. 2026-07-07 backplate structured shared endpoint review：背板虚拟表与结构化映射共享外部端点不再泛化成普通多对一

只读审计确认，Phase77 first 的 `R-MANY-TO-ONE` 剩余 generic `多对一配对` 共有 18 条，其中 16 条都含 `backplate_virtual_table`。这些关系不是 extractor 缺失，也不是应删除的图关系；它们表示背板虚拟表、元件端口或端子表在同一实际外部端点处汇合。

真实缺陷：

- first-set `21 元件接线图1.dwg` 的 `kk_multi_port_component` 与背板虚拟表共享同一外部端，例如：
  - `PCK0002 1DK-2 -> 1QD5 component_mapping/pass`
  - `P0002 NDY306A-5 -> 1QD5 table_mapping/pass`
  - `PCK0006 5DK-2 -> 5FD25 component_mapping/pass`
  - `P0168 NDY306A-5 -> 5FD25 table_mapping/pass`
- first-set `23 元件接线图3.dwg` 的 `strip_two_port_component` 与背板虚拟表共享外部端：
  - `PCM0089 5KLP6-1 -> 5KLP8-1 component_mapping/pass`
  - `P0211 NTZ302A-1 -> 5KLP8-1 table_mapping/pass`
- first-set 背板虚拟表自身也存在同页共享外部端点：
  - `NDY306A-32 -> 5FD26`
  - `NKR308A-11 -> 5FD26`
- 这些原本都显示为 generic `多对一配对`，无法说明“背板结构化映射共享物理端点”的真实成因。

本轮实现：

- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 新增 `_structured_mapping_shared_endpoint_scope_info()`。
- `_run_many_to_one()` 在 generic fallback 前新增窄分支：
  - 全部 linked pairs 必须是 `pair_kind in {table_mapping, component_mapping}`
  - 至少一个 `table_mapping.mapping_mode=backplate_virtual_table`
  - 共享右端点必须与 `right_value` 一致
- 命中后 issue 仍保留为 `R-MANY-TO-ONE/review`，但标题改为 `背板结构化端点汇合待复核`，并写入：
  - `many_to_one_classification=backplate_structured_shared_endpoint_review`
  - `structured_scope_kind=backplate_shared_endpoint`
  - `shared_endpoint`
  - `pair_kinds`
  - `table_mapping_modes`
  - `component_submodes`
  - `source_block_names`
  - `header_prefixes`
  - `logical_endpoints`
- 在 [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py) 增加正负单测：component+backplate 应重分类；纯 terminal-header 共享端点和 component+terminal 非背板共享端点仍保持 generic。
- 不改 extractor、PairBuilder、acceptance fixture、CLI/UI，也不移除 `table_mapping` 或 `component_mapping` 入图。

fresh first-set 证据：

- `.tmp/phase78_backplate_structured_shared_first/...`
- `pair_count=1550`
- `issue_count=311`
- pair_kind 未漂移：
  - `ordinary_pair=800`
  - `table_mapping=299`
  - `continuation=175`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- `R-MANY-TO-ONE` 分类：
  - `backplate_structured_shared_endpoint_review=16`
  - `component_split_endpoint_group_review=12`
  - `terminal_header_table_shared_endpoint_review=7`
  - generic `<none>=2`
- 点名 issue 已重分类：
  - `5KLP8-1`：`PCM0089 + P0211`
  - `1QD5`：`PCK0002 + P0002`
  - `5FD25`：`PCK0006 + P0168`
- 点名边界保留 generic：
  - `KD6`：`PCM0050 + PTM0019 + PTM0025`，component+terminal 非背板
  - `KD23`：`PTM0051 + PTM0054`，纯 `terminal_header_table`

fresh second-set 非回归证据：

- `.tmp/phase78_backplate_structured_shared_second/2_2`
- `pair_count=1460`
- `issue_count=188`
- pair_kind 未漂移：
  - `ordinary_pair=674`
  - `continuation=202`
  - `table_mapping=174`
  - `wire_component_mapping=168`
  - `semantic_mapping=157`
  - `component_mapping=82`
  - `bridge_mapping=3`
- `backplate_structured_shared_endpoint_review=0`
- terminal header 既有语义保持：
  - `terminal_header_table_multi_endpoint_review=43`
  - `terminal_header_table_shared_endpoint_review=21`
- 红线保持：
  - `1-21QD34 -> 1-21n218` 仍为 `wire_component_mapping/pass`
  - `3-21QD28 -> 3-21n218` 仍为 `wire_component_mapping/pass`
  - `1-21GD9 -> 1-21n218` 仍为 `table_mapping/pass`
  - `semantic_table_mapping_pass_endpoint_count=0`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "structured_mapping_shared_endpoint or non_backplate_structured or many_to_one or backplate or terminal_header"` -> `11 passed, 42 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `53 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
- `python -m pytest -q` -> `241 passed`

裁决：

- 本轮是 backplate/component/table rules 语义重分类，不是 extractor 补缺，也不是 issue 隐藏。
- `pair_count`、`issue_count`、`pair_kind` 分布均不变；只让 16 条背板相关 many-to-one review 从 generic 文案变成可解释分类。
- 下一轮候选收缩为：`terminal_header_table issue aggregation`、`inline signal page ordinary residual wire-chain guardrail`。

## 118. 2026-07-07 terminal header table issue aggregation：端子表行级 review 洪峰收敛为自然簇

只读审计确认，Phase78 后 second-set 的端子表结构化关系本身正确：`terminal_header_table` 继续产出 `table_mapping/pass`，Phase60 语义端排除仍保持 `semantic_table_mapping_pass_endpoint_count=0`。真实问题不是 extractor 缺失，而是规则层把连续行带的同类结构现象逐行输出为 review：

- `terminal_header_table_multi_endpoint_review=43`
- `terminal_header_table_shared_endpoint_review=21`

本轮实现：

- 在 [rule_base.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rule_base.py) 的 `cluster_issues()` 中增加 terminal-header 专用聚合入口。
- 聚合只匹配：
  - `R-ONE-TO-MANY` + `one_to_many_classification=terminal_header_table_multi_endpoint_review`
  - `R-MANY-TO-ONE` + `many_to_one_classification=terminal_header_table_shared_endpoint_review`
- 聚合键保持窄范围：
  - multi endpoint 按 `sheet_id + header_prefix`，并要求 row range 相邻或重叠。
  - shared endpoint 按 `sheet_id + header_prefixes`，优先要求 shared endpoint 数字后缀相邻或重叠，再退回 row range。
- evidence 增加聚合字段：
  - `terminal_header_table_aggregate_review`
  - `aggregated_logical_endpoints`
  - `aggregated_row_numbers`
  - `aggregated_conflicting_values`
  - `aggregated_shared_endpoints`
  - `aggregated_shared_endpoint_text_ids`
- 不改 `TableExtractor`、PairBuilder、rules 语义分类、acceptance fixture、CLI/UI，也不移除任何 `table_mapping/pass` 图关系。

fresh first-set 证据：

- `.tmp/phase79_terminal_header_aggregation_first/...`
- `pair_count=1550`
- `issue_count=305`
- pair_kind 未漂移：
  - `ordinary_pair=800`
  - `table_mapping=299`
  - `continuation=175`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- terminal-header 分类：
  - `R-ONE-TO-MANY terminal_header_table_multi_endpoint_review=5`
  - `R-MANY-TO-ONE terminal_header_table_shared_endpoint_review=4`
- backplate/component rules 语义保持：
  - `backplate_table_scope_review=66`
  - `backplate_table_same_sheet_scope_review=18`
  - `backplate_structured_shared_endpoint_review=16`
  - `component_split_endpoint_group_review` one-to-many `16`、many-to-one `12`

fresh second-set 证据：

- `.tmp/phase79_terminal_header_aggregation_second/2_2`
- `pair_count=1460`
- `issue_count=129`
- pair_kind 未漂移：
  - `ordinary_pair=674`
  - `continuation=202`
  - `table_mapping=174`
  - `wire_component_mapping=168`
  - `semantic_mapping=157`
  - `component_mapping=82`
  - `bridge_mapping=3`
- terminal-header 行级洪峰收敛为 5 个自然 issue：
  - `R-ONE-TO-MANY / 1-21GD / rows 3-4`
  - `R-ONE-TO-MANY / 1-21GD / rows 20-21`
  - `R-ONE-TO-MANY / 1-21QD / rows 1-38`
  - `R-ONE-TO-MANY / 1-21CD / row 10` singleton 保留
  - `R-MANY-TO-ONE / 1-21GD + 1-21QD / shared endpoints 1-21n210-230`
- 红线保持：
  - `semantic_table_mapping_pass_endpoint_count=0`
  - `1-21QD34 -> 1-21n218` 仍为结构化 pass 关系
  - `3-21QD28 -> 3-21n218` 仍为 `wire_component_mapping/pass`
  - `1-21GD9 -> 1-21n218` 仍为 `table_mapping/pass`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "terminal_header_table or one_to_many or many_to_one"` -> `14 passed, 42 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `56 passed`
- `python -m pytest -q tests\unit\test_table_extractor.py -k "terminal_header_table"` -> `3 passed, 11 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "terminal_header_table or table_mapping"` -> `4 passed, 16 deselected`
- `python -m pytest -q` -> `244 passed`

裁决：

- 本轮是 rules / acceptance / 默认展示口径收口，不是 extractor 补缺。
- issue_count 下降只来自连续端子表行级 review 聚合；`pair_count` 和 `pair_kind` 分布未漂移。
- 下一轮候选收缩为：`inline signal page ordinary residual wire-chain guardrail`；若转产品化，则单独做 packaged sidecar/exe smoke，不混入 rules 切片。

## 119. 2026-07-07 inline wire-chain DIM guardrail：错位 DIM 短线不再被诊断为互补半链

只读审计确认，Phase79 first-set 剩余 2 条 `complementary_half_pair` 都在 `S0008 / 07 网络通讯回路图.dwg`。它们不是 `inline_klp_component_port_mapping` extractor 缺失，也不是应该桥接成同一根线的普通 inline 数字切断；当前问题是 rules 把主 `CONNECT` 水平线和 y 方向错位的纯 `DIM` 短线，因为共享同一个数字文本锚点而误解释为“互补半链”。

目标样本：

- `I0001 / PW0178 + PW0182`
  - `PW0178 / GW0178`: `? -> 701`, `CONNECT`, line `[257.5,145.0] -> [347.5,145.0]`
  - `PW0182 / GW0182`: `701 -> ?`, pure `DIM`, line `[352.235754,154.1] -> [377.764246,154.1]`
  - shared text `T0458=701`, insert `(345.622905,145.657933)`, bbox `[345.622905,144.782933,350.272905,147.657933]`
- `I0002 / PW0202 + PW0205`
  - `PW0202 / GW0202`: `? -> 601`, `CONNECT`, line `[257.5,225.0] -> [347.5,225.0]`
  - `PW0205 / GW0205`: `601 -> ?`, pure `DIM`, line `[352.235754,234.1] -> [377.764246,234.1]`
  - shared text `T0442=601`, insert `(345.622905,225.657933)`, bbox `[345.622905,224.782933,350.272905,227.657933]`

本轮实现：

- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 增加 `_line_groups_wire_chain_compatible()`：
  - complementary half-chain 聚合必须要求两个 horizontal line group 的 y 差不超过 `inline_numeric_bridge_y_tolerance`。
  - 两侧 line group 必须是 wire-chain candidate，纯 `DIM` line group 不允许充当 broken wire chain 的另一半。
- 增加 `_missing_side_line_group_candidate()`：
  - 普通 `R-PAIR-MISSING-SIDE` 不再对纯 `DIM` line group 报缺边。
  - `CONNECT` 主线缺边仍保留为普通 `端点数字缺失`，避免通过 rules 静音掩盖主线仍缺端点的事实。
- 在 [test_pairs_and_rules.py](/F:/workspace/XJToolkit/tests/unit/test_pairs_and_rules.py) 增加 first `07` 几何负例，证明 `CONNECT + y-offset DIM` 不再聚合为 `complementary_half_pair`。
- 不改 `line_groups.py`、`candidates.py`、`pairs.py`、extractor、acceptance fixture、CLI/UI，也不移除 pair graph input。

fresh first-set 证据：

- `.tmp/phase80_inline_wire_chain_guardrail_first/...`
- `pair_count=1550`
- `issue_count=302`
- pair_kind 未漂移：
  - `ordinary_pair=800`
  - `table_mapping=299`
  - `continuation=175`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- `complementary_half_pair=0`
- `R-PAIR-MISSING-SIDE=144`
- 目标变化：
  - `PW0178 ? -> 701` 保持普通 `端点数字缺失`
  - `PW0202 ? -> 601` 保持普通 `端点数字缺失`
  - `PW0182/GW0182` 与 `PW0205/GW0205` 纯 `DIM` 短线不再进入缺边 issue

fresh second-set 非回归证据：

- `.tmp/phase80_inline_wire_chain_guardrail_second/2_2`
- `pair_count=1460`
- `issue_count=127`
- pair_kind 未漂移：
  - `ordinary_pair=674`
  - `continuation=202`
  - `table_mapping=174`
  - `wire_component_mapping=168`
  - `semantic_mapping=157`
  - `component_mapping=82`
  - `bridge_mapping=3`
- `complementary_half_pair=0`
- 红线保持：
  - `semantic_table_mapping_pass_endpoint_count=0`
  - `1-21QD34 -> 1-21n218` 仍为结构化 pass 关系
  - `3-21QD28 -> 3-21n218` 仍为 `wire_component_mapping/pass`
  - `1-21GD9 -> 1-21n218` 仍为 `table_mapping/pass`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "complementary or missing_side"` -> `4 passed, 53 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `57 passed`
- `python -m pytest -q` -> `245 passed`

裁决：

- 本轮是 rules 诊断边界收口，不是 extractor 重写，也不是通过删除 pair 变好看。
- `pair_count` 和 `pair_kind` 分布均不变；用户可见 issue 只去掉纯 `DIM` 标注短线造成的假 wire-chain/缺边解释。
- 下一轮应重新只读审计剩余最大的 ordinary missing-side / low-confidence 簇，再选择一个真实系统误解切片；若转产品化，则 packaged sidecar/exe smoke 独立推进。

## 120. 2026-07-07 schematic wire logic endpoint mapping：测控控制回路逻辑端进入结构化关系

只读审计确认，Phase80 second-set 最大剩余缺边簇集中在 `11/16 测控控制回路图2` 等二次原理图。图上 `1-21CD58`、`3-21CD58`、`1-21UD8` 这类文本不是端子表语义说明，也不是普通噪声；它们是测控控制回路线侧逻辑端编号。旧候选层只接受数字或既有派生数字，因此这些逻辑端被记为 `not_numeric/noise_channel`，对侧数字 `511` 等只能形成 `? -> 511` 普通 missing-side。

本轮实现：

- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 增加 `wire_logic_endpoint_channel`：
  - 仅适用于 `sheet_category=二次原理图`。
  - 仅适用于 horizontal/grid 线组。
  - 仅接受 `^[13]-21[A-Z]{2,4}\d{1,3}$` 这类测控逻辑端形态。
- 在 [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py) 中只允许该通道与对侧真实 `terminal_numeric_channel` 配对。
- 完整配对升级为 `pair_kind=wire_component_mapping`、`component_submode=schematic_wire_logic_endpoint`，并保留逻辑端/数字端的 text id、raw text、side 证据。
- 单侧逻辑端不会制造新的 `R-PAIR-MISSING-SIDE` review。
- 本轮不触碰 `table_extractor.py`、component/table extractor、rules、CLI/UI，也不改变 terminal header table 的语义端排除红线。

fresh second-set 证据：

- `.tmp/phase81_schematic_logic_endpoint_second_v2/2_2`
- `pair_count=1460`
- `issue_count=58`
- `R-PAIR-MISSING-SIDE=48`
- pair_kind：
  - `ordinary_pair=597`
  - `wire_component_mapping=245`
  - `continuation=202`
  - `table_mapping=174`
  - `semantic_mapping=157`
  - `component_mapping=82`
  - `bridge_mapping=3`
- `wire_logic_endpoint_channel=665`
- 目标关系：
  - `1-21CD58 -> 511`：`wire_component_mapping/review`
  - `3-21CD58 -> 511`：`wire_component_mapping/review`
- `11 测控1控制回路图2.dwg` 与 `16 测控2控制回路图2.dwg` 的 missing-side count 均为 0。

fresh first-set 非回归证据：

- `.tmp/phase81_schematic_logic_endpoint_first_v2/...`
- `pair_count=1550`
- `issue_count=302`
- pair_kind 与 Phase80 保持一致：
  - `ordinary_pair=800`
  - `table_mapping=299`
  - `continuation=175`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`
- `wire_logic_endpoint_channel=0`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`
- `1-21QD34 -> 1-21n218` 仍为结构化 pass 关系
- `3-21QD28 -> 3-21n218` 仍为 `wire_component_mapping/pass`
- `1-21GD9 -> 1-21n218` 仍为 `table_mapping/pass`
- `I0/IA/UA/UB/UC/UN/3U0` 等端子表语义说明不得成为 `table_mapping/pass` endpoint 的合同仍有效。

验证：

- `python -m pytest -q tests\unit\test_terminal_candidates.py -k "schematic_logic_endpoint or semantic_marker or single_sided_schematic_logic"` -> `3 passed, 24 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `57 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or input_matrix or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `248 passed`

裁决：

- 本轮是二次原理图逻辑端候选/关系语义补齐，不是 terminal-header/table extractor 回退，也不是 rules 静音。
- 已闭合能力不得重开：`input_matrix_wire_mapping`、`small_port_box_component`、`kk_multi_port_component`、`strip_two_port_component(KLP/CLP)`、terminal header semantic endpoint exclusion/aggregation、inline DIM guardrail。
- 下一轮候选收缩为：second 剩余 `R-PAIR-MISSING-SIDE=48`、first 剩余 `R-PAIR-MISSING-SIDE=144`、backplate/component/table mapping rules semantics；若转产品化，则 packaged sidecar/exe smoke 单独推进。

## 121. 2026-07-07 schematic complementary half-chain geometry review：grid 半链以 review 聚合，rerun loader 保真

只读审计确认，Phase81 second-set 剩余 `R-PAIR-MISSING-SIDE=48` 中有一组真实结构不是新的 extractor 缺失，而是二次原理图中两个强几何半链共享同一个数字文本，但 line group 被标记为 `grid`，符号间隙可到 `17.5/18.75`。旧 complementary half-chain 只允许 `horizontal` 且 gap 必须落在普通 inline 范围内，因此这些半链被拆成两条普通缺边。

代表样本：

- second `S0004/S0005`，`04/05 交流回路图*.dwg`：`PW0015 + PW0016` 等共享 `719/717/715`，`bridge_gap=17.5`。
- second `S0014 / 14 测控2开入回路图3.dwg`：`PW0438 + PW0440`，`bridge_gap=18.75`。
- first 同构页也存在 24 个可聚合的 geometry half-chain review。

本轮实现：

- 在 [rules.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rules.py) 中允许 `horizontal/grid` line group 参与 `complementary_half_pair` 聚合。
- 对含 `grid` 的半链使用 `bridge_gap_min=-3.0`、`bridge_gap_max=max(inline_gap, 20.0)`，覆盖轻微重叠和较宽符号间隙。
- evidence 新增 `bridge_gap_min` / `bridge_gap_max`，方便复核为什么被聚合。
- 保留 `R-PAIR-MISSING-SIDE` / `review` 可见性；该规则只把两条互补缺边聚合为一条更准确的 review，不改成 pass/discard，也不删除 pair graph 输入。
- 在 [rerun.py](/F:/workspace/XJToolkit/src/dwg_audit/report/rerun.py) 修复 findings rerun loader：恢复 `LineGroup.orientation` 与 `row_band_id`。此前 audit-only 验证会把历史 findings 中的 `grid` 反序列化为默认 `horizontal`，导致 rules 验证和 fresh analyze 语义不一致。

fresh second-set 证据：

- `.tmp/phase82_complementary_second/2_2` + `.tmp/phase82_complementary_second_audit`
- `pair_count=1460`
- `issue_count=51`
- `R-PAIR-MISSING-SIDE=41`
- `complementary_half_pair=7`
- pair_kind 未漂移：
  - `ordinary_pair=597`
  - `wire_component_mapping=245`
  - `continuation=202`
  - `table_mapping=174`
  - `semantic_mapping=157`
  - `component_mapping=82`
  - `bridge_mapping=3`

fresh first-set 证据：

- `.tmp/phase82_complementary_first/...` + `.tmp/phase82_complementary_first_audit`
- `pair_count=1550`
- `issue_count=278`
- `R-PAIR-MISSING-SIDE=120`
- `complementary_half_pair=24`
- pair_kind 未漂移：
  - `ordinary_pair=800`
  - `table_mapping=299`
  - `continuation=175`
  - `component_mapping=138`
  - `semantic_mapping=103`
  - `wire_component_mapping=32`
  - `bridge_mapping=3`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系。
- first `1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307` 均保持命中。
- `I0/IA/UA/UB/UC/UN/3U0` 等语义说明文本仍不得成为 `table_mapping/pass` endpoint；当前候选表中这些标签保留为 rejected candidate evidence，不参与 endpoint 竞争。

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "complementary or dim"` -> `4 passed, 55 deselected`
- `python -m pytest -q tests\unit\test_rerun_audit.py` -> `2 passed`
- `python -m pytest -q` -> `250 passed`

裁决：

- 本轮是 rules 诊断语义和 findings rerun 保真修复，不是 extractor 补缺。
- issue_count 下降来自互补半链聚合：两条普通缺边合并成一条 review，而不是隐藏关系。
- 下一轮候选收缩为：second AC phase-label semantic/covered mapping、second DC/GND/function-label semantic mapping、second network-time/function-label semantic mapping、first prefixed external endpoints、first ZLP component two-port mapping；backplate/component/table mapping 继续作为 rules/acceptance/display 质量问题单独切。

## 122. 2026-07-07 ZLP strip two-port component mapping：同构长条双端口组件进入结构化关系

只读审计确认，first `S0023 / 22 元件接线图2.dwg` 中 `1-2ZLP4` 与已闭合的 KLP/CLP 长条双端口结构同构：上方本体编号为 `1-2ZLP4`，块内端口为 `1/2`，上端外部端为 `KD26`，下端外部端为 `1-2n422`，并有 vertical support line。旧输出只因为 `_COMPONENT_BODY_PATTERN` 未包含 `ZLP`，留下普通缺边 `PC0090 ? -> 422`。

本轮实现：

- 在 [component_diagrams.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/component_diagrams.py) 中把 `strip_two_port_component` body family 从 `KLP/CLP` 扩为 `KLP/CLP/ZLP`。
- 在 [test_component_diagrams.py](/F:/workspace/XJToolkit/tests/unit/test_component_diagrams.py) 中增加 ZLP 同构夹具，覆盖 `1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422`。
- 本轮不改候选层、PairBuilder、rules、CLI/UI 或 acceptance fixture；KLP/CLP 既有行为保持。

fresh first-set 证据：

- `.tmp/phase83_zlp_first/...` + `.tmp/phase83_zlp_first_audit`
- `pair_count=1562`
- `issue_count=272`
- `component_mapping=150`
- `R-PAIR-MISSING-SIDE=114`
- 目标关系：
  - `1-2ZLP4-1 -> KD26`：`component_mapping/pass/confidence=0.95`
  - `1-2ZLP4-2 -> 1-2n422`：`component_mapping/pass/confidence=0.95`
- 原 `PC0090 ? -> 422` 和同构 sibling `PC0104 ? -> 422` 均为 `discard`，理由为被 `ComponentDiagramExtractor` 的 `component_mapping` 覆盖。

fresh second-set 非回归证据：

- `.tmp/phase83_zlp_second/2_2` + `.tmp/phase83_zlp_second_audit`
- `pair_count=1460`
- `issue_count=51`
- pair_kind 与 Phase82 保持一致：
  - `ordinary_pair=597`
  - `wire_component_mapping=245`
  - `continuation=202`
  - `table_mapping=174`
  - `semantic_mapping=157`
  - `component_mapping=82`
  - `bridge_mapping=3`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1` 均保持命中

验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py -k "strip_two_port or zlp"` -> `9 passed, 9 deselected`
- `python -m pytest -q tests\unit\test_component_diagrams.py` -> `18 passed`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "component or kk or strip or run_audit"` -> `10 passed, 10 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `59 passed`
- `python -m pytest -q` -> `251 passed`

裁决：

- 本轮是同构组件 family 漏收补齐，不是重新实现 KLP/CLP extractor，也不是 rules 静音。
- 下一轮候选收缩为：second AC phase-label semantic/covered mapping、second DC/GND/function-label semantic mapping、second network-time/function-label semantic mapping、first prefixed external endpoints、backplate/component/table mapping rules semantics。

## 123. 2026-07-07 second DC/GND function semantic mapping：直流功能标签进入 semantic review 关系

只读审计确认，second `S0006 / 06 直流回路图.dwg` 中 `DC 0-5V/4-20mA +/-` 与 `GND` 不是普通数字端点，也不是 terminal-header table extractor 回退，而是二次原理图里的功能/语义端标签。旧候选层把这些文本拒为 `not_numeric/noise_channel`，导致相邻数字端留下普通 missing-side，例如 `611 -> ?` 与 `? -> 101`。

本轮实现：

- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 新增 `schematic_semantic_endpoint_channel`，只在 `二次原理图`、horizontal/grid、且文件名或标题含直流/DC 的上下文启用。
- 本切片只接受 `DC 0-5V/4-20mA +/-` 与 `GND`，不把 AC phase label、network-time label 或 first prefixed external endpoint 混入。
- 在 [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py) 中只允许该通道与对侧真实 `terminal_numeric_channel` 成对，并将关系标为 `pair_kind=semantic_mapping`、`semantic_mapping_kind=schematic_dc_function_label`、`ordinary_pair_eligible=False`。
- 单侧语义标签会被 PairBuilder scoped filter 移除，不制造新的 ordinary missing-side review。
- 在 [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py) 增加 DC 功能标签、GND 和单侧语义 guardrail 单测。

fresh second-set 证据：

- `.tmp/phase84_dc_semantic_second/2_2` + `.tmp/phase84_dc_semantic_second_audit`
- `pair_count=1460`
- `issue_count=45`
- `R-PAIR-MISSING-SIDE=35`
- `semantic_mapping=164`
- 新增/命中 semantic review 关系包括：
  - `611 -> DC 0-5V/4-20mA +`
  - `609 -> DC 0-5V/4-20mA +`
  - `607 -> DC 0-5V/4-20mA +`
  - `GND -> 101`
- 这些关系均为 `semantic_mapping/review`，并带 `ordinary_pair_eligible=False`。

fresh first-set 非回归证据：

- `.tmp/phase84_dc_semantic_first/...` + `.tmp/phase84_dc_semantic_first_audit`
- `pair_count=1562`
- `issue_count=269`
- `R-PAIR-MISSING-SIDE=111`
- `semantic_mapping=106`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `S0021 / 21 左侧端子图1.dwg` 中 `I0/IA/UA/UB/UC/UN/3U0` 仍保留为 `semantic_channel` rejected candidate evidence，不进入 `table_mapping/pass` endpoint。
- `PTM0008` 当前为 `3-21ID11 -> 3-21n708`，`PTM0017` 当前为 `3-21QD9 -> 3-21n130`，均不再是旧的 `... -> I0` 错误。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_terminal_candidates.py -k "schematic_dc or schematic_semantic_endpoint or schematic_logic_endpoint"` -> `5 passed, 25 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
- `python -m pytest -q` -> `254 passed`

裁决：

- 本轮是二次直流功能标签的语义关系收口，不是扩大普通数字端点解析，也不是隐藏 issue。
- 下一轮候选收缩为：second AC phase-label semantic/covered mapping、second network-time/function-label semantic mapping、first prefixed external endpoints、backplate/component/table mapping rules semantics。

## 124. 2026-07-07 second network-time function semantic mapping：网络对时标签进入 semantic review 关系

只读审计确认，second `S0007 / 07 网络对时回路图.dwg` 的 8 条 `R-PAIR-MISSING-SIDE` 不是图纸缺边，而是 `TD1..TD5`、`B+/-`、`B code +/-`、`Device alarm` 等网络/对时功能标签被候选层拒为 `not_numeric/noise_channel`，导致相邻端子号 `110/601/602` 被 ordinary PairBuilder 报为缺边。

本轮实现：

- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 沿用 `schematic_semantic_endpoint_channel`，仅在 `二次原理图` 且 sheet filename/title 命中 `网络/对时/COMMUNICATION/TIME SYNCHRONIZATION` 时接受 network-time 标签。
- 本切片只接受 `TD#`、`B+/-`、`B code +/-`、`Device alarm`，不把 AC phase label、一般中英文功能说明或 first prefixed external endpoint 混入。
- 在 [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py) 复用完整“语义端 + 数字端” `semantic_mapping`，并新增仅限 `schematic_network_time_label` 的同侧 annotation 语义，用于 `601` 与同侧 `B+` 这类真实形态。
- 单侧 network-time 标签不再制造 ordinary missing-side；输出仍是 `semantic_mapping/review`，保留人工复核证据。
- 在 [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py) 增加 network-time 对侧语义端和同侧 annotation 单测。

fresh second-set 证据：

- `.tmp/phase85_network_time_second/2_2` + `.tmp/phase85_network_time_second_audit`
- `pair_count=1460`
- `issue_count=37`
- `R-PAIR-MISSING-SIDE=27`
- `semantic_mapping=172`
- `S0007 / 07 网络对时回路图.dwg` issue 清零。
- 新增/命中 semantic review 关系包括：
  - `TD4 -> 602`
  - `TD2 -> 601`
  - `TD3 -> 602`
  - `TD1 -> 601`
  - `Device alarm -> 110`
  - `B+ -> 601` annotation semantics

fresh first-set 非回归证据：

- `.tmp/phase85_network_time_first/...` + `.tmp/phase85_network_time_first_audit`
- `pair_count=1562`
- `issue_count=258`
- `R-PAIR-MISSING-SIDE=100`
- `semantic_mapping=117`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_terminal_candidates.py -k "network_time or schematic_dc or schematic_semantic_endpoint or schematic_logic_endpoint"` -> `7 passed, 25 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `256 passed`

裁决：

- 本轮是网络/对时功能标签的语义关系收口，不是扩大普通数字端点解析，也不是 rules 静音。
- 下一轮候选收缩为：second AC phase-label semantic/covered mapping、first prefixed external endpoints、backplate/component/table mapping rules semantics。

## 125. 2026-07-07 second AC phase-label semantic annotation：交流相量标签进入 semantic review 关系

只读审计确认，second `S0004/S0005 / 04/05 交流回路图*.dwg` 中的 `UA/UB/UC/UN/UX/3U0/3U0'` 是 CT/VT 交流回路的相量/功能标签，不是普通数字端点，也不是端子图说明列。旧候选层把这些文本拒为 `not_numeric/noise_channel`，导致相邻数字端 `715/717/719/721/723/724` 留下 ordinary missing-side。

本轮实现：

- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 沿用 `schematic_semantic_endpoint_channel`，仅在 `二次原理图` 且 sheet filename/title 命中交流/AC/CT-VT context 时接受 AC phase label。
- 本切片只接受 `UA/UB/UC/UN/UX/3U0/3U0'`，不接受 `I0/IA/IB/IC/IN`，不把 `1-21ZKK/3-21ZKK` 或局部脚位 `1..6` 回灌成 ordinary endpoint。
- 在 [pairs.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/pairs.py) 让同侧 annotation 语义支持 `schematic_ac_phase_label`，输出仍是 `semantic_mapping/review`，并带 `ordinary_pair_eligible=False`。
- 在 [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py) 增加 AC annotation、端子图 AC marker 隔离、`I0` 不进入 AC phase label 通道的回归测试。

fresh second-set 证据：

- `.tmp/phase86_ac_phase_second/2_2` + `.tmp/phase86_ac_phase_second_audit`
- `pair_count=1460`
- `issue_count=33`
- `R-PAIR-MISSING-SIDE=23`
- `semantic_mapping=182`
- 新增 10 条 `schematic_ac_phase_label` semantic review 关系，包括：
  - `721 -> 3U0`
  - `723 -> UX`
  - `719 -> UC`
  - `717 -> UB`
  - `715 -> UA`
- second AC issue 从 Phase85 的 11 条降为 7 条；剩余为 `? -> 715/717/719` sibling half-lines 与 `724 -> ?`，需要下一刀 covered/window residual，不在本轮静音。

fresh first-set 非回归证据：

- `.tmp/phase86_ac_phase_first/...` + `.tmp/phase86_ac_phase_first_audit`
- `pair_count=1562`
- `issue_count=258`
- `semantic_mapping=119`
- first 中新增 2 条 `3U0 -> 723` AC semantic review，整体 issue_count 与 Phase85 持平。

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_terminal_candidates.py -k "ac_phase or terminal_ac_marker or schematic_i0 or network_time or schematic_dc or schematic_semantic_endpoint"` -> `8 passed, 27 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `259 passed`

裁决：

- 本轮是二次交流相量标签的语义 annotation 收口，不是扩大普通数字解析，也不是 rules 静音。
- 下一轮候选收缩为：second AC phase-label covered/window residual、first prefixed external endpoints、backplate/component/table mapping rules semantics。

## 126. 2026-07-07 second AC phase-label covered half-lines：已有 AC semantic mapping 覆盖的普通半边 residual 降级

只读审计确认，Phase86 second AC 剩余 7 条中有 6 条并不是新的端点识别缺口，而是与已有 `schematic_ac_phase_label` semantic mapping 共用同一个 numeric text 的 sibling half-line 普通缺边。典型形态是 `? -> 719` 与 sibling `719 -> UC` 共享 `T0007`；`? -> 717` / `? -> 715` 同理。`724 -> UX'` 没有既有 semantic mapping，仍保留为后续 strict nearby/window annotation 切片。

本轮实现：

- 在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 增加 `_mark_schematic_ac_phase_covered_ordinary_pairs()`。
- 该 helper 只在 `WireDiagramExtractor` 的 `build_pairs()` 之后运行，只扫描 `二次原理图`。
- 只采信 `pair_kind=semantic_mapping`、`semantic_mapping_kind=schematic_ac_phase_label`、`semantic_kind` 为 `schematic_semantic_endpoint` 或 `schematic_semantic_annotation` 的既有结构化关系。
- 只把共享同一 `numeric_endpoint_text_id` 的 ordinary 单侧半边 pair 标记为 `discard/low`，并写入 `ordinary_pair_eligible=False` 与 `covered_by_schematic_ac_phase_label_semantic_mapping=True`。
- 不扩大 AC semantic candidate window，不改 PairBuilder，不改 rules，不移除 `semantic_mapping` 或普通 pair graph。
- 在 [test_page_extractors.py](/F:/workspace/XJToolkit/tests/unit/test_page_extractors.py) 增加 shared numeric half-pair、非 AC semantic、complete pair、terminal semantic row scope 的窄单测。

fresh second-set 证据：

- `.tmp/phase87_ac_covered_second/2_2` + `.tmp/phase87_ac_covered_second_audit`
- `pair_count=1460`
- `issue_count=27`
- `ordinary_pair review=21`
- 被覆盖降级的 6 条 ordinary half-lines：
  - `PW0015 ? -> 719`
  - `PW0019 ? -> 717`
  - `PW0023 ? -> 715`
  - `PW0057 ? -> 719`
  - `PW0061 ? -> 717`
  - `PW0065 ? -> 715`
- AC residual 只剩 `PW0047/GW0047 724 -> ?`；附近 `UX'` 需要后续 strict nearby/window annotation，不在本轮静音。
- `pair_kind` counts 保持：`ordinary_pair=572`、`wire_component_mapping=245`、`continuation=202`、`semantic_mapping=182`、`table_mapping=174`、`component_mapping=82`、`bridge_mapping=3`。

fresh first-set 非回归证据：

- `.tmp/phase87_ac_covered_first/...` + `.tmp/phase87_ac_covered_first_audit`
- `pair_count=1562`
- `issue_count=256`
- `covered_by_schematic_ac_phase_label_count=2`
- `semantic_table_mapping_pass_endpoint_count=0`

红线保持：

- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_page_extractors.py -k "ac_phase or input_matrix or terminal_prefixed"` -> `10 passed`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
- `python -m pytest -q tests\unit\test_terminal_candidates.py -k "ac_phase or terminal_ac_marker or schematic_i0"` -> `3 passed, 32 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `262 passed`

裁决：

- 本轮是“已有 semantic evidence 覆盖普通半边 residual”的关系收口，不是 extractor 重写、候选窗口扩张或 rules 静音。
- 下一轮候选收缩为：second AC `724 -> UX'` strict nearby/window annotation、first prefixed external endpoints、backplate/component/table mapping rules semantics。

## 127. 2026-07-07 second AC UX prime strict line-span annotation：最后一条交流相量缺边进入 semantic review

只读审计确认，Phase87 second AC 唯一剩余 residual 是 `S0005 / 05 交流回路图2.dwg` 的 `PW0047/GW0047 724 -> ?`。该线段 `[165.0,129.9999997] -> [215.0,129.9999997]` 上，数字 `T0132=724` 位于同一行，语义文本 `T0134=UX'` 位于严格 line-span 内，应解释为 AC phase label annotation，而不是普通端点缺失。

本轮实现：

- 在 [candidates.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/candidates.py) 中将 AC phase label 白名单扩展为支持 `UX'`。
- 新增 `_add_schematic_ac_phase_line_span_candidates()`，只在 `二次原理图` horizontal/grid line group 上、且恰好已有一侧真实 `terminal_numeric_channel` 时扫描同线段跨度内的 AC phase semantic endpoint。
- 新增 AC-only 跨行 guard：endpoint window 中的 `schematic_ac_phase_label` 若垂直对齐分数为 0，则拒为 `schematic_semantic_out_of_row`；该 guard 不作用于 DC/network-time semantic endpoint。
- 在 [test_terminal_candidates.py](/F:/workspace/XJToolkit/tests/unit/test_terminal_candidates.py) 增加 `UX'` line-span 正例、far-y 负例、跨行 `UX'` endpoint-window 负例和低对齐 DC 语义端非回归测试。

fresh second-set 证据：

- `.tmp/phase88_ac_ux_prime_second_v3/2_2` + `.tmp/phase88_ac_ux_prime_second_v3_audit`
- `pair_count=1460`
- `issue_count=26`
- `ordinary_pair=571`
- `semantic_mapping=183`
- AC issue count `0`
- `PW0047/GW0047 724 -> ?` 现在为 `semantic_mapping/review`，evidence 包含 `semantic_kind=schematic_semantic_annotation`、`semantic_mapping_kind=schematic_ac_phase_label`、`semantic_endpoint=UX'`、`numeric_endpoint=724`、`ordinary_pair_eligible=False`。
- `GW0047/T0134 UX'` 被接受为同线段 line-span semantic candidate；相邻行 `GW0048/T0134 UX'` 被拒为 `schematic_semantic_out_of_row`。
- `PW0106 607 -> DC 0-5V/4-20mA +` 仍为 `semantic_mapping/review`，证明跨行 guard 已收窄到 AC labels，没有回退 DC 语义端。

fresh first-set 非回归证据：

- `.tmp/phase88_ac_ux_prime_first/...` + `.tmp/phase88_ac_ux_prime_first_audit`
- `pair_count=1562`
- `issue_count=256`
- KLP/ZLP/218 structured redlines 均保持命中。

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_terminal_candidates.py -k "network_time or schematic_dc or schematic_semantic_endpoint or ac_phase or ux_prime or schematic_i0"` -> `10 passed, 29 deselected`
- `python -m pytest -q tests\unit\test_page_extractors.py -k "ac_phase or input_matrix or terminal_prefixed"` -> `10 passed`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `266 passed`

裁决：

- 本轮是 second AC 最后一条 `724 -> UX'` 的严格 line-span 语义 annotation 收口，不是扩大普通 endpoint 解析，也不是 rules 静音。
- 下一轮候选收缩为：first prefixed external endpoints、backplate/component/table mapping rules semantics；packaged sidecar/exe smoke 只作为独立产品切片。

## 128. 2026-07-07 first prefixed external endpoint mapping：QD 外部端 residual 升级为结构化 wire-component 关系

只读审计确认，first `S0009/S0010/S0011` 中 `1QD5`、`1-2QD12`、`3-2QD12` 是带数字前缀的外部端，同行裸 `105` 应合成为 `1n105`、`1-2n105`、`3-2n105`。旧输出因为外部端文本不属于普通 numeric candidate，留下 `PW0225/PW0250/PW0275 ? -> 105` 普通缺边。`S0012` 的 `5FD25 -> 5n105` 属于 FD 变体，本轮保留为后续候选。

本轮实现：

- 在 [wire_components.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/wire_components.py) 增加 `first_prefixed_external_endpoint_mapping` 子模式。
- 该子模式只接受非 `*-21QD*` 的 QD 外部端与同行 3 位局部号，输出 `wire_component_mapping/pass`。
- `WireDiagramExtractor` 只对当前已经形成 ordinary 单侧 residual 的 local text 启用该子模式，避免把整片 QD 表无差别提升入图。
- 在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 中只用 `local_number_text_id` 覆盖普通半边 pair；外部端文本自身不被覆盖。
- 在 [test_wire_components.py](/F:/workspace/XJToolkit/tests/unit/test_wire_components.py) 和 [test_page_extractors.py](/F:/workspace/XJToolkit/tests/unit/test_page_extractors.py) 补 QD 正例、input-matrix 隔离、eligible-local gate、非二次页隔离和覆盖边界测试。

fresh first-set 证据：

- `.tmp/phase75_prefixed_external_first_v2/...` + `.tmp/phase75_prefixed_external_first_v2_audit`
- `pair_count=1584`
- `issue_count=232`
- `wire_component_mapping=54`
- `first_prefixed_external_endpoint_mapping=22`
- 目标命中：
  - `1QD5 -> 1n105`
  - `1-2QD12 -> 1-2n105`
  - `3-2QD12 -> 3-2n105`
- `PW0225/PW0250/PW0275 ? -> 105` 均为 `ordinary_pair/discard`，并带 `covered_by_first_prefixed_external_endpoint_mapping=True`。
- `PW0309 ? -> 105` 保持 review，因为 `5FD25 -> 5n105` 不在 QD-only 切片中。

fresh second-set 非回归证据：

- `.tmp/phase75_prefixed_external_second_v2/2_2` + `.tmp/phase75_prefixed_external_second_v2_audit`
- `pair_count=1460`
- `issue_count=26`
- `wire_component_mapping=245`
- `input_matrix_wire_mapping=168`
- `first_prefixed_external_endpoint_mapping=0`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_wire_components.py -k "prefixed or input_matrix or inline_klp"` -> `10 passed`
- `python -m pytest -q tests\unit\test_page_extractors.py -k "prefixed or input_matrix or terminal_prefixed"` -> `9 passed, 3 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "wire_component or missing_side or semantic_mapping"` -> `7 passed, 52 deselected`
- `python -m pytest -q` -> `272 passed`

裁决：

- 本轮是 QD 型 first prefixed external endpoint residual 的结构化抽取与普通半边覆盖，不是扩大普通 numeric candidate，也不是 rules 静音。
- 下一轮候选收缩为：FD prefixed external endpoint residual (`5FD25 -> 5n105`)、backplate/component/table mapping rules semantics；packaged sidecar/exe smoke 只作为独立产品切片。

## 129. 2026-07-07 FD prefixed external endpoint residual：`5FD25 -> 5n105` 进入结构化 wire-component 关系

只读审计确认，first `S0012 / 11 非电量开入回路.dwg` 的 `PW0309 ? -> 105` 不是图纸错误，而是系统未理解 FD 前缀外部端。该行 `GW0309 [137.5,260.0] -> [172.5,260.0]` 附近存在 `T0801=5FD25` 与 `T0830=105`，页面标题为 `5n BINARY INPUT`，应形成 `5FD25 -> 5n105`。背板与元件结构化关系中已有 `NDY306A-5 -> 5FD25` 和 `5DK-2 -> 5FD25`，进一步说明 `5FD25` 是真实外部端。

本轮实现：

- 在 [wire_components.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/wire_components.py) 将 `_FIRST_PREFIXED_EXTERNAL_ENDPOINT_PATTERN` 从 QD-only 扩为 `QD|FD`。
- 保持 `first_prefixed_external_endpoint_mapping` submode 不变，仍只捕获数字前缀并合成 `prefix + n + local_number`。
- 保持 ordinary 单侧 residual eligible gate、二次原理图 route boundary、同行/右侧局部号几何约束、非 `*-21QD*` input-matrix guard。
- 不改 rules、table/component extractor、candidate 主逻辑、CLI/UI。
- 在 [test_wire_components.py](/F:/workspace/XJToolkit/tests/unit/test_wire_components.py) 增加 FD 正例、FD eligibility 隔离和 `DK/YD/FX` 非授权字母负例。

fresh first-set 证据：

- `.tmp/phase76_fd_prefixed_first/...` + `.tmp/phase76_fd_prefixed_first_audit`
- `pair_count=1589`
- `issue_count=226`
- `wire_component_mapping=59`
- `first_prefixed_external_endpoint_mapping=27`
- 目标命中：
  - `5FD25 -> 5n105`
  - `PW0309 ? -> 105` 已为 `ordinary_pair/discard`，并带 `covered_by_first_prefixed_external_endpoint_mapping=True`
- 同族 FD residual 也被结构化：
  - `5FD3 -> 5n114`
  - `5FD26 -> 5n132`
  - `5FD1 -> 5n103`
- QD 目标仍保持：
  - `1QD5 -> 1n105`
  - `1-2QD12 -> 1-2n105`
  - `3-2QD12 -> 3-2n105`

fresh second-set 非回归证据：

- `.tmp/phase76_fd_prefixed_second/2_2` + `.tmp/phase76_fd_prefixed_second_audit`
- `pair_count=1460`
- `issue_count=26`
- `wire_component_mapping=245`
- `input_matrix_wire_mapping=168`
- `first_prefixed_external_endpoint_mapping=0`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_wire_components.py -k "prefixed or input_matrix or inline_klp"` -> `12 passed`
- `python -m pytest -q tests\unit\test_page_extractors.py -k "prefixed or input_matrix or terminal_prefixed"` -> `9 passed, 3 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "wire_component or missing_side or semantic_mapping"` -> `7 passed, 52 deselected`
- `python -m pytest -q` -> `274 passed`

裁决：

- 本轮是 FD 型 first prefixed external endpoint residual 的窄扩展，只允许 `QD|FD`，不是任意字母端泛化。
- 下一轮候选收缩为：second inline wire split `505` half-chain bridge、second component vertical `401` mapping upgrade、backplate/component/table mapping rules semantics；packaged sidecar/exe smoke 仍为独立产品切片。

## 130. 2026-07-07 second inline wire split 505：互补半链转为 continuation 证据

只读审计确认，second `S0014 / 14 测控2开入回路图3.dwg` 中的 `PW0438 ? -> 505` 与 `PW0440 505 -> ?` 不是两个真实缺端点。两条线共享 `T1479=505`，位于同一 `RBW0169` 行带，`GW0438 [87.5,135.0] -> [127.5,135.0]` 与 `GW0440 [146.25,135.0] -> [237.5,135.0]` 的 `bridge_gap=18.75`，`bridge_y_delta=0.0`。它们是 `Emergency stop / 调压急停` 元件区域里一条水平连接链被内联数字/元件符号切开的 half-chain。

本轮实现：

- 在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 增加 `_mark_inline_wire_split_continuation_pairs()`，只在 `WireDiagramExtractor` `build_pairs()` 后处理二次原理图互补 ordinary half-pairs。
- 命中条件保持窄范围：同 `sheet_id/text_id/value`、一条 missing-left 一条 missing-right、horizontal/grid line group、同 row band、合法 y delta 和 bridge gap。
- 命中后保留 pair 为 `review`，但把 `pair_kind` 改为 `continuation`，并写入 `ordinary_pair_eligible=False`、`semantic_kind=continuation_inline_wire_split`、`continuation_kind=schematic_inline_wire_split_half_chain`、`covered_by_inline_wire_split_half_chain=True`、`shared_text_id`、`shared_value`、`bridge_gap` 和 related pair 证据。
- 在 [test_page_extractors.py](/F:/workspace/XJToolkit/tests/unit/test_page_extractors.py) 增加正例、非二次/跨行负例，并断言标记后不会再触发 `R-PAIR-MISSING-SIDE`。
- 不改 `pairs.py` 的端子 continuation / bridge 语义，不调 `line_groups.py` 合并阈值，不改 rules 主逻辑，不碰 KLP residual、401 component vertical、backplate/component/table rules 或 CLI/UI。

fresh second-set 证据：

- `.tmp/phase77_inline_wire_split_second/2_2` + `.tmp/phase77_inline_wire_split_second_audit`
- `pair_count=1460`
- `issue_count=25`
- `R-PAIR-MISSING-SIDE=15`
- `continuation=204`
- `PW0438` 与 `PW0440` 现在均为 `continuation/review`，共享 `T1479=505`，`bridge_gap=18.75`，并互相记录 related pair。
- `505` / `PW0438` / `PW0440` 不再出现在 issue 中。
- `PW0439 505 -> 506` 保持 `ordinary_pair/discard`，没有被误升为普通 pass。
- 邻近 `PW0442 ? -> 501` 保持 `ordinary_pair/review`，仍作为独立 missing-side issue，不被本轮覆盖吞掉。

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- `input_matrix_wire_mapping=168`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化关系。

验证：

- `python -m pytest -q tests\unit\test_page_extractors.py -k "inline_wire_split or input_matrix or prefixed or ac_phase"` -> `14 passed`
- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "complementary or missing_side or continuation"` -> `10 passed, 49 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `276 passed`

裁决：

- 本轮是 second `505` inline wire split half-chain 的 pair 语义收口，不是 rules 静音，也不是全局线组合并阈值调整。
- 下一轮候选收缩为：second component vertical `401` mapping upgrade、backplate/component/table mapping rules semantics；packaged sidecar/exe smoke 仍为独立产品切片。

## 131. 2026-07-07 second component vertical 401：ZK 到 n401 端点桥接进入 component_mapping

只读审计确认，second `S0020 / 20 元件接线图2.dwg` 中的 `PC0077 4 -> 401` 与 `PC0090 6 -> 401` 不是低置信图纸问题，而是系统把完整端点 `3-21ZK-4`、`1-21ZK-6` 派生成裸数字后走了 ordinary pair。实图结构是 `FJL-25-2A_Mirror` 双端口块上下 pin `1/2` 之间的竖向端点桥接，底端分别是同前缀 `3-21n401`、`1-21n401`。

本轮实现：

- 在 [component_diagrams.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/component_diagrams.py) 新增 `strip_two_port_endpoint_bridge` 子模式。
- 该子模式只接受顶部 `^\d+-\d+ZK-\d+$`、底部同前缀 `^\d+-\d+n\d{3,}$`、上下 pin `1/2` 和支撑竖线同时成立的场景。
- 输出直接 `component_mapping/pass`：`3-21ZK-4 -> 3-21n401`、`1-21ZK-6 -> 1-21n401`。
- 在 [page_extractors.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/page_extractors.py) 注册该 submode，并复用 consumed line group 机制覆盖旧 ordinary pair。
- 在 [test_component_diagrams.py](/F:/workspace/XJToolkit/tests/unit/test_component_diagrams.py) 增加真实几何正例、前缀不一致负例、裸数字底端负例。

fresh second-set 证据：

- `.tmp/phase78_component_vertical_401_second/2_2` + `.tmp/phase78_component_vertical_401_second_audit`
- `pair_count=1462`
- `issue_count=23`
- `component_mapping=84`
- 目标命中：
  - `PCB0001 / GC0077 / T3494 -> T3495`: `3-21ZK-4 -> 3-21n401`, `component_mapping/pass`
  - `PCB0002 / GC0090 / T3468 -> T3469`: `1-21ZK-6 -> 1-21n401`, `component_mapping/pass`
- 旧普通 pair：
  - `PC0077 4 -> 401` 已为 `ordinary_pair/discard`，`covered_by_component_mapping=True`
  - `PC0090 6 -> 401` 已为 `ordinary_pair/discard`，`covered_by_component_mapping=True`
- `GC0077/GC0090` 与 `401` 不再产生 issue。

fresh first-set 非回归证据：

- `.tmp/phase78_component_vertical_401_first/...` + `.tmp/phase78_component_vertical_401_first_audit`
- `pair_count=1581`
- `issue_count=212`
- `component_mapping=150`

红线保持：

- `semantic_table_mapping_pass_endpoint_count=0`。
- second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`。
- second `1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍命中结构化关系。
- first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 均保持命中。

验证：

- `python -m pytest -q tests\unit\test_component_diagrams.py -k "strip_two_port or endpoint_bridge"` -> `12 passed, 9 deselected`
- `python -m pytest -q tests\unit\test_page_extractors.py -k "component or inline_wire_split or input_matrix or prefixed"` -> `11 passed, 3 deselected`
- `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
- `python -m pytest -q` -> `279 passed`

裁决：

- 本轮是 second component vertical `401` 的结构化端点桥接收口，不是放宽普通 endpoint 正则，也不是 rules 静音。
- 下一轮候选收缩为：backplate/component/table mapping rules semantics；packaged sidecar/exe smoke 仍为独立产品切片。

## 132. 2026-07-07 backplate scope review：跨页背板表格 review 从行级噪声聚合为作用域簇

只读审计确认，first `.tmp/phase78_component_vertical_401_first_audit` 中最大的结构化 rules 噪声不是 extractor 缺失，而是背板虚拟表格作用域复用被按每个逻辑端逐条展示：`R-CROSS-PAGE-CONFLICT=66`，全部为 `table_mapping/review`。这些 issue 已有证据字段 `one_to_many_classification=backplate_table_scope_review`、`table_mapping_mode=backplate_virtual_table`、`source_block_names`、`header_prefixes`，但聚类仍按 `left_value` 分散，诊断根因也被标成 `insufficient_evidence`。

本轮实现：

- 在 [rule_base.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rule_base.py) 增加背板 scope review 聚合，只匹配 `R-CROSS-PAGE-CONFLICT + backplate_table_scope_review + backplate_virtual_table`。
- 聚合 key 限定为 `rule_id / classification / table_mapping_mode / header_prefixes / source_block_names`，避免跨不同表头或不同背板作用域过度合并。
- 聚合证据新增 `backplate_scope_aggregate_review`、`aggregated_logical_endpoints`、`aggregated_conflicting_values`，并保留 `cluster_pair_ids`、`cluster_sheet_ids` 和原始 evidence refs。
- 在 [issue_diagnostics.py](/F:/workspace/XJToolkit/src/dwg_audit/services/issue_diagnostics.py) 将 specialized `R-CROSS-PAGE-CONFLICT` 归因为 `rule_too_strict`，与 `R-ONE-TO-MANY` / `R-MANY-TO-ONE` 的结构化关系诊断一致。
- 不改 TableExtractor / ComponentDiagramExtractor / PairBuilder，不从图中移除任何 `table_mapping`，不扩 CLI/UI。

fresh rules-only 证据：

- first `.tmp/phase79_backplate_scope_first_audit`
- `issue_count=153`
- `R-CROSS-PAGE-CONFLICT=7`
- `cross_page root_cause={"rule_too_strict": 7}`
- 典型聚合：
  - `NDY306A` + `WBH-812E-E1SA-101/WBH-813E-E1SH-101/WBH-814E-E1SA-101`: `cluster_size=8`
  - `NCK316A` + `WBH-812E-E1SA-101/WBH-813E-E1SH-101`: `cluster_size=12`
  - `NCZ343A` + `WBH-813E-E1SH-101`: `cluster_size=28`
- first Phase78 findings pair_count 保持 `1581`，`table_mapping=299`、`component_mapping=150` 未被移除。

second 非回归证据：

- second `.tmp/phase79_backplate_scope_second_audit`
- `issue_count=23`
- 规则分布保持：`R-PAIR-MISSING-SIDE=15`、`R-ONE-TO-MANY=6`、`R-SEMANTIC-MAPPING-CONFLICT=1`、`R-MANY-TO-ONE=1`
- second Phase78 findings pair_count 保持 `1462`
- `3-21ZK-4 -> 3-21n401` 与 `1-21ZK-6 -> 1-21n401` 仍为 `component_mapping/pass`

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "backplate or cross_page"` -> `7 passed, 53 deselected`
- `python -m pytest -q tests\unit\test_issue_diagnostics.py` -> `3 passed`
- `python -m pytest -q` -> `281 passed`

裁决：

- 本轮是背板跨页虚拟表格作用域 review 的聚合和诊断口径修正，不是 extractor 补漏，也不是静音规则。
- 下一轮候选收缩为：backplate/component/table mapping rules semantics 的同页 scope、many-to-one/shared endpoint、默认用户可见 review 分组；packaged sidecar/exe smoke 仍为独立产品切片。

## 133. 2026-07-07 backplate same-sheet scope：NKR308A 同页表格复用聚合为连续行带

只读审计确认，Phase79 后 first `S0021 / 20 非电量保护背板图.dwg` 仍有 18 条 `R-ONE-TO-MANY` / `backplate_table_same_sheet_scope_review` 行级 review。它们都来自 `backplate_virtual_table`：同一 `source_block_name=WBH-814E-E1SA-101`、同一 `header_prefix=NKR308A`、同一对 raw headers `NKR308A / NKR308A(非电量选配)`，行号为连续 `1..18`。这表示同一背板表头模板在同页不同区域复用，不是 extractor 缺失，也不是应删除的 `table_mapping`。

本轮实现：

- 在 [rule_base.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rule_base.py) 增加 `backplate_table_same_sheet_scope_review` 聚合。
- 聚合 key 限定为 rule/classification/table mode、sheet、source block、header prefix、raw header texts、header text ids。
- 仅当行号范围相邻或重叠时合并，避免把同页不同表格段过度并成一个问题。
- 聚合证据保留 `backplate_scope_aggregate_review`、`aggregated_logical_endpoints`、`aggregated_row_numbers`、`aggregated_conflicting_values`、`cluster_pair_ids`、`cluster_sheet_ids`。
- 不改 `rules.py` 判定、不改 extractor、不改 graph input、不扩 CLI/UI。

fresh rules-only 证据：

- first `.tmp/phase80_backplate_same_sheet_scope_first_audit`
- `issue_count=136`
- `R-ONE-TO-MANY=24`
- `backplate_table_same_sheet_scope_review=1`
- 聚合 issue `I0159`:
  - `cluster_size=18`
  - rows `1..18`
  - `aggregated_logical_endpoints=18`
  - `aggregated_conflicting_values=36`
  - `cluster_pair_ids=36`
- first Phase78 findings pair_count 保持 `1581`。

second 非回归证据：

- second `.tmp/phase80_backplate_same_sheet_scope_second_audit`
- `issue_count=23`，与 Phase79 保持一致。
- second Phase78 findings pair_count 保持 `1462`。

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "backplate or cross_page"` -> `8 passed, 53 deselected`
- `python -m pytest -q` -> `282 passed`

裁决：

- 本轮是背板同页虚拟表格作用域 review 的聚合收口，不是静音规则，也不是新增抽取器。
- 下一轮候选收缩为：many-to-one/shared endpoint 默认展示分层、terminal header shared endpoint 区间展示、component split endpoint review 展示；packaged sidecar/exe smoke 仍为独立产品切片。

## 134. 2026-07-07 terminal header shared endpoint：连续区间写入 review 证据和报告说明

只读审计确认，Phase80 后 second `S0023 / 23 右侧端子图1.dwg` 的最大 terminal_header_table shared endpoint review 已经是聚合 issue，但报告仍像单点问题一样描述 `1-21n210`。真实结构是同一张端子表中两个连续 header 区间共享一段连续端子列：`1-21GD1..1-21GD21` 与 `1-21QD26..1-21QD46` 共同对应 `1-21n210..1-21n230`。这些关系在 findings 中已是 `table_mapping/pass/high`，本轮只收口 rules/display 证据，不改抽取器。

本轮实现：

- 在 [rule_base.py](/F:/workspace/XJToolkit/src/dwg_audit/audit/rule_base.py) 为聚合后的 `terminal_header_table_shared_endpoint_review` 增加区间摘要证据。
- 新增字段：`terminal_header_table_interval_review`、`aggregated_logical_endpoint_ranges`、`aggregated_shared_endpoint_ranges`、`aggregated_row_number_ranges`。
- 聚合 issue 的 `summary / explanation / recommended_action` 改为明确显示区间结构，让 `audit_report.md` 和桌面 summary 字段不再只展示第一条共享端。
- 不改 `TableExtractor` / `TerminalDiagramExtractor` / `PairBuilder` / graph input，不隐藏或移除 `table_mapping`，不扩 CLI/UI。

fresh second-set 证据：

- `.tmp/phase81_terminal_header_interval_second_audit`
- `issue_count=23`，与 Phase80 保持一致。
- `I0062` now reports:
  - `aggregated_logical_endpoint_ranges=["1-21GD1..1-21GD21", "1-21QD26..1-21QD46"]`
  - `aggregated_shared_endpoint_ranges=["1-21n210..1-21n230"]`
  - `aggregated_row_number_ranges=["1..21", "26..46"]`
  - `summary="Terminal header table shared endpoints form contiguous intervals: logical=1-21GD1..1-21GD21, 1-21QD26..1-21QD46; shared=1-21n210..1-21n230."`
- `audit_report.md` 的 Summary / RecommendedAction 已显示上述区间和行号区间。

fresh first-set 非回归证据：

- `.tmp/phase81_terminal_header_interval_first_audit`
- `issue_count=136`，与 Phase80 保持一致。
- first 中已聚合的 terminal-header shared endpoint issue 增加 interval evidence；非连续片段仍以分段区间展示，不被强行合成单段。

验证：

- `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "terminal_header_table or backplate or shared_endpoint"` -> `13 passed, 48 deselected`
- `python -m pytest -q` -> `282 passed`

裁决：

- 本轮是 terminal_header_table shared endpoint 的区间证据和报告说明收口，不是 issue 静音，也不是表格抽取补漏。
- 下一轮候选收缩为：component split endpoint review 展示、many-to-one/shared endpoint 默认展示分层、backplate/component cross-scope shared endpoint 展示；packaged sidecar/exe smoke 仍为独立产品切片。

## 135. 2026-07-07 component split endpoint：逗号拆分 review 分类透出到报告和 UI

只读审计确认，Phase81 后 first `.tmp/phase81_terminal_header_interval_first_audit` 中仍有 `28` 条 `component_split_endpoint_group_review`：`R-ONE-TO-MANY=16`、`R-MANY-TO-ONE=12`。这些不是 `strip_two_port_component` extractor 缺失；证据中已经包含 `component_branch_kind=split_endpoint_group`、`external_endpoint_raw_values`、`external_endpoint_splits`、`external_endpoint_text_ids` 和 `logical_endpoints`。典型样本是 first `S0024 / 23 元件接线图3.dwg` 的 `I0138 / PCM0066`：`5KLP5-1 -> 5KLP3-1` 来自原始逗号文本 `5KLP3-1,5KLP2-1`，拆分端为 `5KLP2-1` 与 `5KLP3-1`，文本 ID 为 `T3841`。

本轮实现：

- 在 [artifacts.py](/F:/workspace/XJToolkit/src/dwg_audit/report/artifacts.py) 的报告 frame 中新增 `many_to_one_classification` 和统一 `review_classification`。
- `audit_report.md` issue 块现在同时展示 `ReviewClassification`、`OneToManyTriage` 与 `ManyToOneTriage`。
- LineSemantics 摘要改为合并读取 issue 顶层 evidence 与 nested `pair_evidence`，能显示 `component_submode=strip_two_port_component`、`component_branch_kind=split_endpoint_group`、`shared_endpoint`、`external_endpoint_splits`。
- 在 [app.py](/F:/workspace/XJToolkit/src/dwg_audit/ui/app.py) 给内部 Streamlit UI 增加 `many_to_one_classification` 和 `review_classification` 投影，问题表默认显示统一分类，详情仍保留来源字段。
- 不改 `ComponentDiagramExtractor`、`PairBuilder`、rules 判定、issue 聚合、graph input 或 CLI/UI 产品表面。

fresh rules-only 证据：

- first `.tmp/phase82_component_split_display_first_audit`
- `issue_count=136`，与 Phase81 保持一致。
- `component_split_endpoint_group_review=28`：
  - `R-ONE-TO-MANY=16`
  - `R-MANY-TO-ONE=12`
- `audit_report.md` 已包含：
  - `ReviewClassification: component_split_endpoint_group_review`
  - `OneToManyTriage: component_split_endpoint_group_review`
  - `ManyToOneTriage: component_split_endpoint_group_review`
  - `component_submode=strip_two_port_component`
  - `component_branch_kind=split_endpoint_group`
  - `external_endpoint_splits=5KLP2-1|5KLP3-1`
- `issues.xlsx` 中 `review_classification=component_split_endpoint_group_review` 命中 `28` 行，`many_to_one_classification=component_split_endpoint_group_review` 命中 `12` 行。

second 非回归证据：

- second `.tmp/phase82_component_split_display_second_audit`
- `issue_count=23`，与 Phase81 保持一致。
- `component_split_endpoint_group_review=0`。
- pair graph 未漂移：first `pair_count=1581`，second `pair_count=1462`。

验证：

- `python -m pytest -q tests\unit\test_report_artifacts.py -k "many_to_one_component_split or evidence_display"` -> `2 passed, 15 deselected`
- `python -m pytest -q tests\unit\test_ui_app.py -k "classification"` -> `2 passed, 3 deselected`
- `python -m pytest -q tests\unit\test_report_artifacts.py tests\unit\test_ui_app.py` -> `22 passed`
- `python -m pytest -q` -> `284 passed`

裁决：

- 本轮是 component split endpoint review 的报告/UI 展示语义收口，不是 issue 静音，也不是组件抽取器补漏。
- 下一轮候选收缩为：many-to-one/shared endpoint 默认展示分层、backplate/component cross-scope shared endpoint 展示、acceptance golden 口径；packaged sidecar/exe smoke 仍为独立产品切片。
