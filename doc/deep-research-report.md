# 面向 DWG 跨页端子数字匹配校验的一体化任务书

## 核心判断

基于你前面已经明确的边界，这个项目最优先的目标不是“理解整张电气图”，而是**在一套多页 DWG 中，把水平连接线两端的数字配对抽出来，并做跨页一致性校验**。从行业产品看，成熟产品也并不是先走黑盒识图路线，而是优先依赖**项目级数据、跨页引用、线号/连接号、端子管理、错误清单和可导航的审计结果**来完成校验。AutoCAD Electrical 提供 Drawing Audit、Electrical Audit、Cross-Reference、Signal Arrows、Terminal Strip Editor 等项目级检查与报告能力；EPLAN则提供在线/离线检查、消息管理、交叉引用、中断点跨页引用、端子排导航和 API 化检查动作。这说明你们的 MVP 应该走**确定性 CAD 几何+文本规则引擎**路线，而不是以 OCR 或视觉大模型为主线。citeturn5search0turn5search2turn5search1turn9search4turn1search3turn4search2turn4search14turn6search13turn7search0

如果从工程效率和成功率来排序，我的结论非常明确：**MVP 首选“本地 DWG 读入或先转 DXF，再做几何—文本抽取与项目级规则校验”**；OCR 和视觉大模型只作为后备兜底，用于两类异常场景：一类是文字对象缺失、炸开或退化；另一类是审计结果置信度低、需要生成“为什么低置信度”的辅助解释。PaddleOCR 目前已经把 PDF/图像转结构化数据做到很强，官方也强调其 3.x 系列提供复杂文档解析、服务部署和高精度 OCR/VLM 能力，但这更适合图像/PDF 路线；你们既然能拿到 DWG，就不应把 PaddleOCR 放在主链路上。citeturn8search0turn8search1turn8search4

对你们这种“本地部署、个人学习和私用、以高可靠审计为第一优先级”的场景，我建议采用一个**证据优先**的产品形态：先生成 findings，再生成 issue list，而不是先画一个复杂 CAD 前端。成熟产品也是这么做的：AutoCAD Electrical 的审计结果会把错误列成报告并支持 surf/navigation；EPLAN 的 Message Management 也是把检查结果收敛成消息数据库和可跳转清单。这意味着你们的第一版前端不需要完整 DWG 渲染，只要能把“第几页、哪条线、哪两个数字、为什么冲突、置信度多少、如何复核”说清楚，就已经贴近行业最佳实践。citeturn5search2turn5search10turn9search6turn0search5turn4search2

## 行业最佳实践反推

从 Autodesk 的产品路线看，AutoCAD Electrical 的自动化审查不是单点算法，而是**项目范围的连续性检查**。它有项目范围或图纸范围的线号更新能力，也有针对导线、线号和连接问题的 Drawing Audit 与 Electrical Audit。Electrical Audit 能列出缺失或重复的 wire number、重复 cable tag、无连接组件等问题；Drawing Audit 会清理浮空线号、错误指针、零长度导线等脏数据。再往上，Cross-Referencing 可以生成 Cross-reference report 和 Exception/Error report，Signal Arrows 则用“source/destination 同名代码”的方式把跨页延续的导线网络关联起来，并把 source 的 wire number 复制到 destination network。换句话说，Autodesk 的思路是：**先有稳定的项目级对象，再有全项目审计，再把异常变成可浏览、可回跳的报告。**citeturn1search4turn1search12turn5search0turn5search2turn5search1turn9search3turn9search4turn9search6

从 EPLAN 的产品路线看，重点不是“读懂整张图的电气意义”，而是**把项目数据持续检查、把跨页连接显示成可配置的交叉引用、把结果集中进消息系统**。EPLAN 明确区分在线检查和离线检查；在线检查会在编辑过程中即时写入 message database，离线检查可以在项目级、结构级或页级执行；消息管理可以按规则筛选，还可以对交叉引用对象执行 Go to；跨页连接则通过 interruption points 与 chain/star cross-reference 表达；端子和端子排则由专门的 navigator 管理。这种设计背后的方法论非常适合你们：**规则先于 AI、项目先于单页、消息与复核先于自动修改。**citeturn4search1turn4search2turn4search14turn0search5turn6search2turn6search4turn6search13turn1search5turn4search12

把这两家主流产品合在一起看，可以反推出你们应该借鉴的五个最佳实践。第一，**一定要项目级处理，不要单页处理**，因为跨页匹配天然依赖全套图。第二，**一定要保留 evidence chain**，即“哪条线、哪一端、哪一个数字、哪个候选被排除、为什么得出这个结论”。第三，**一定要做在线/离线双模式的架构准备**：MVP 先做离线批处理，后期再考虑读图后边改边检的“在线检查”。第四，**一定要把错误分成 hard error 和 review required**，因为成熟产品不会在高风险工程文档上把所有模糊项都直接判错。第五，**定位信息优先于复杂渲染**，因为 उद्योग实践里“消息 + 跳转 + 项目上下文”比“花哨画布”更重要。以上结论是对 Autodesk 和 EPLAN 官方能力组合的工程化归纳。citeturn5search8turn5search10turn4search2turn4search4turn0search5turn6search9

## 推荐技术栈与依赖

在“不优先考虑开源与否、以本地可部署与工程成功率为先”的前提下，我建议技术路线分成两层。**MVP 层**采用 `DWG -> DXF -> Python 解析与几何匹配`；**增强层**预留为 `直接 DWG SDK 读取/渲染`。原因很简单：Autodesk RealDWG 提供官方原生 DWG/DXF 读写能力，ODA Drawings SDK 也提供对 DWG/DGN 的访问、可视化、创建、编辑和保存；但这两条路的接入复杂度和开发门槛都高于“先稳妥转换，再做 DXF 解析”。ODA File Converter 则正好是这条 MVP 路线的最佳桥梁，它可批量在 DWG 和 DXF 之间转换，并支持 audit 标志；而 ezdxf 官方文档明确支持借助已安装的 ODA File Converter 来处理 DWG 转换。citeturn2search0turn2search1turn3search0turn3search11turn2search2turn10search0

因此，我建议你的**默认依赖组合**是：Windows 本地环境；ODA File Converter 作为 DWG 前处理；ezdxf 作为 DXF 抽取器；Shapely 负责平面几何和 STRtree 空间索引；NetworkX 负责把“数字—数字”关系组织成图并跑冲突、一对多、多对一等规则；pandas 与 openpyxl 负责 findings 和审计报告输出。这个组合非常贴合你们的任务边界：ezdxf 官方支持读取和修改 DXF，并可直接抽取 TEXT、MTEXT、ATTRIB 等文本内容；Shapely 专门处理平面几何运算；NetworkX 则非常适合构造页级/项目级关系图。citeturn10search0turn10search11turn10search15turn10search17turn11search0turn11search4turn11search1turn11search3

如果两套大图跑下来发现 `DWG -> DXF` 的保真度不够，或某些复杂块、扩展数据、特殊对象在 DXF 级别丢失，就升级到**高保真路径**：优先 ODA Drawings SDK，次选 RealDWG。两者都能直接面向原生 DWG 数据工作，其中 RealDWG 是 Autodesk 官方路线，ODA Drawings SDK 则是非常成熟的跨平台工程 SDK。这条升级路径不是为了让 MVP 立刻变重，而是为了在 findings 阶段就给未来留出“保真兜底”。citeturn2search0turn2search1turn2search5

渲染方面，我建议你**不要把完整 DWG 在线渲染当作一阶段要求**。如果必须要看图，优先做两种轻量证据呈现：一是页码+坐标+图纸文件名，二是异常区域的 PNG/PDF 小片段。ODA Drawings Explorer 可以用来渲染和检查 DWG/DGN 文件；ODA 也提供把 DWG/DXF 转 PDF 的示例应用。也就是说，对你们这种“本地校验工具”来说，最佳实践不是先做一整套 CAD 前端，而是先保证**问题定位足够可复核**。citeturn3search13turn3search6turn3search15

OCR 和视觉大模型只应作为 fallback。若发现图中关键数字并非原生 TEXT/MTEXT/ATTRIB，而是炸开为矢量线段，或者后续要兼容图片/PDF 数据集，再引入 PaddleOCR 3.x 或 PaddleOCR-VL 作为补充模块。官方文档显示 PaddleOCR 3.x 已覆盖复杂文档解析、结构化输出、服务部署和多语言 OCR，但这条链路应通过“低置信度兜底接口”接入，而非取代主流程。citeturn8search1turn8search3turn8search4

## 本地 Agent 读图与 Findings 工作流

本地 agent 的第一职责不是直接“找错”，而是**先把整套图读成结构化 findings**。这一点非常重要，因为后续的所有规则调优、误报分析、前端展示、人工复核，都会依赖 findings 作为证据底座。行业产品的共同特征也是先有项目级对象和消息，再有检查与导航，因此你的 agent 也应先完成“对象化”和“证据化”。citeturn5search1turn4search2turn7search0

我建议本地 agent 的固定工作流是这样的：先批量导入一个项目目录中的全部 DWG；然后用 ODA File Converter 批量转 DXF，并开启 audit；随后由解析器抽取所有页的文本实体、线实体、块引用、块属性、图层、坐标和布局信息；再基于页框和标题栏推断页码区与有效审计区；接着在有效区域内筛选“水平或近似水平”的连接线，合并共线碎线；之后在每条线的左右端点建立候选数字集合，保存所有候选而不是只保存胜者；最后再把这些候选和最终 pair 一起写入 findings。这样设计的好处是，哪怕第一版规则错了，你也能回看证据重算，而不需要重新读图。ODA File Converter 支持 audit/repair 处理；ezdxf 支持从 DXF 文档读取实体及其文本内容；Shapely 则可以把几何索引做得足够快。citeturn3search0turn2search2turn10search10turn10search11turn11search4

我建议 findings 目录至少输出六类文件：`pages.parquet`、`texts.parquet`、`lines.parquet`、`line_groups.parquet`、`pair_candidates.parquet` 和 `issues_seed.parquet`。其中 `pages` 记录页码、图名、图框范围、有效区域、标题栏区域；`texts` 记录文本内容、类型、bbox、旋转角度、字体高度、图层、是否像端子数字；`lines` 记录原始线段；`line_groups` 记录合并后的候选连接线；`pair_candidates` 记录每条线左右端的所有文本候选及其评分；`issues_seed` 则只记录尚未判定级别的异常线索。这些输出并非行业标准文件名，而是结合 Autodesk/EPLAN 的“项目对象 + 消息管理 + 导航”的最佳实践反推出来的最小证据集合。citeturn5search10turn0search5turn4search14

findings 文档本身建议再额外生成一份人可读的 `findings.md`，结构固定为：项目概况、页码识别策略、有效审计区域推断说明、文字分布统计、线段统计、疑似连接线统计、候选数字提取规则、已知不确定点、建议人工确认项。你后续给 agent 下达任何“优化软件”的任务，都应当以 `findings.md + parquet/csv 数据` 为依据，而不是让它每次从零读图。这样能把“读图问题”和“规则问题”分离开，极大提升开发效率和可追溯性。这也是工程软件里非常重要的 best practice：**先标准化证据，再演化规则。**

## 一体化规格文档

这个产品的**需求定义**可以收紧为一句话：输入一套多页 DWG 图纸，本地程序自动抽取每条目标连接线两端的数字配对，完成跨页匹配，并输出包含页码、坐标、配对结果、异常原因和置信度的审计报告。第一版的非目标也要写死：不做完整电气元件识别，不做任意风格图纸通吃，不做自动改图，不强依赖全图渲染，不把 OCR/VLM 作为主路径。这样的范围收敛，与 AutoCAD Electrical 和 EPLAN 的成熟做法是对齐的——它们的高价值能力同样集中在 project-wide checking、cross-reference、message/report 和 navigable issues 上，而不是把所有逻辑压成一个不可解释的黑盒。citeturn5search0turn5search1turn4search2turn4search14

这个产品的**核心数据模型**应当至少包括 `Sheet`、`TextItem`、`LineEntity`、`LineGroup`、`PairCandidate`、`Pair`、`Issue` 七类对象。`Sheet` 负责页级上下文；`TextItem` 负责记录候选数字的文本证据；`LineEntity` 保留原始 CAD 线段；`LineGroup` 表示合并后的“审计线”；`PairCandidate` 记录每端多个候选而不是一个候选；`Pair` 表示最终的端到端数字配对；`Issue` 表示异常或待复核对象。这样设计的直接好处，是把“提取结果”和“判定结果”分层，避免以后无法解释错误来源。对你们的高风险场景，这比任何“只留最终答案”的简化设计都可靠。

这个产品的**后端逻辑**应分成五个阶段。第一阶段是 `ingest`，负责项目目录扫描、DWG 转 DXF 和图纸初检。第二阶段是 `extract`，负责抽取文本与线段。第三阶段是 `understand-layout`，负责学习这套图的页框、标题栏和有效审计区。第四阶段是 `build-pairs`，负责从线两端找数字候选、评分并生成 pair。第五阶段是 `audit`，负责项目级冲突检测并写出报告。之所以建议把 `understand-layout` 单独拿出来，是因为 EPLAN 的交叉引用本质上依赖页框行列位置，Autodesk 的交叉引用和 signal arrows 也依赖项目上下文与引用位置；这说明**版式理解虽然不是电气理解，但在工程上是第一类能力**。citeturn6search9turn9search1turn9search4

这个产品的**规则引擎**至少要实现六类规则：同号冲突、一对多、多对一、缺失配对、重复配对、低置信度待复核。建议把每个结论拆成 `status + score + rationale + evidence` 四部分，其中 `status` 为 `pass / fail / review`，`score` 为 0 到 1 的置信度，`rationale` 是机器生成的一句话说明，`evidence` 则引用页码、坐标、线 ID、候选列表和距离分数。置信度不要只看 OCR 或文本内容本身，而要综合**距离、共线性、垂直偏差、层名、字体高度、端点唯一性、全项目重复模式**。对于高风险项，我建议阈值采取保守策略：`>=0.92` 视为高置信匹配，`0.75–0.92` 进入人工复核，`<0.75` 不进入自动判定。这一“保守阈值 + review bucket”的思路，和 EPLAN 的消息管理、AutoCAD Electrical 的 exception/error report 非常一致：不确定就交给人工，而不是强行自动修正。citeturn0search5turn4search2turn5search1turn5search10

这个产品的**前端形态**应当极简，但必须有用。第一版推荐本地 Web UI 或桌面壳，页面只做四块：项目导入、findings 浏览、异常列表、单条异常详情。异常详情至少显示：文件名、页码、线 ID、左右数字、左右坐标、冲突页、冲突数字、置信度、理由、候选列表。如果能做截图，就增加一个“局部图块预览”；如果一开始渲染困难，就只显示文字定位信息。不要在一阶段做复杂 CAD 交互；成熟产品的核心价值也不在炫技渲染，而在“消息、复核、跳转、项目一致性”。citeturn5search2turn9search6turn0search5

这个产品的**开发接口**也应保守设计。对外只需要四个主要命令或 API：`analyze-project`、`export-findings`、`run-audit`、`export-report`。如果你后面想把它交给本地 agent 继续优化，就再增加两个内部动作：`re-score-pairs` 和 `re-run-rules`。这两个动作必须只基于 findings 重算，不允许重新读图，以确保实验可复现。与此同时，参考 EPLAN 的 API 和 action 设计，你也可以预留“按页检查”“按项目检查”“只检查过滤后的页”等参数，因为将来数据集大了以后，这些都是很实用的工程能力。citeturn7search0turn7search1turn7search6turn7search9

## 实施阶段与风险控制

实施上，我建议把整个项目切成三个明确阶段。**第一阶段是读图与 findings 阶段**，目标不是抓错，而是证明你能稳定把一整套图变成结构化对象，并拿到可靠的页码、线段、候选数字和线端邻近证据。这个阶段的验收标准只有四个：导入成功率、页码识别正确率、目标线召回率、候选数字召回率。只要这四项还不稳定，绝不要急着写复杂规则。citeturn3search0turn10search0turn10search11

**第二阶段是 pair 构建与项目级审计阶段**。这一阶段开始运行真正的业务规则，但仍然要以“先精确、后召回”为原则。也就是说，宁可把模糊项打到 `review`，也不要为了追求全自动而提高误报和漏报。AutoCAD Electrical 和 EPLAN 的官方能力都体现出这个风格：它们把问题组织成报告、消息和可导航的异常，而不是默认静默修正所有问题；这对电力类图纸尤其重要。citeturn5search0turn5search1turn4search14turn4search2

**第三阶段是局部增强阶段**。只有在前两个阶段稳定后，才考虑三类增强：第一，切到直接 DWG SDK 以获得更高保真；第二，引入渲染或小图块预览；第三，在极少数低置信场景引入 PaddleOCR 或视觉模型兜底。这个顺序不能反，因为过早搞渲染和 AI，往往会掩盖真正的问题——是数据没读对，还是规则没写对。行业成熟产品之所以稳定，就在于它们的自动化校验建立在结构化工程数据、项目级规则和可追踪消息上，而不是建立在“看起来很聪明”的大模型直觉上。citeturn2search0turn2search1turn8search1turn8search4turn4search2turn5search10

最后，我给这个项目一个非常明确的路线建议：**第一版就做“DWG 本地读图 + findings + 跨页数字配对校验 + 置信度报告”，不做重前端，不做全语义，不做主链路 OCR**。工具选型上，优先 `ODA File Converter + ezdxf + Shapely + NetworkX + pandas/openpyxl`；若 findings 阶段暴露出 DWG 保真问题，再升级到 `ODA Drawings SDK` 或 `RealDWG`。产品交付上，优先“异常证据清单 + 坐标定位 + review 队列”，而不是“漂亮的 DWG 浏览器”。这条路线最贴近当前行业最佳实践，也最贴近你已经反复澄清的真实需求。citeturn3search0turn2search2turn10search0turn11search0turn11search3turn2search0turn2search1turn5search2turn0search5