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
