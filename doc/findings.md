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
