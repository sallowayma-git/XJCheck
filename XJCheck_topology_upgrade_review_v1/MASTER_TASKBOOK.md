# XJCheck 线网优先识别引擎升级开发任务书

版本：v1.0  
文档类型：PRD + 架构设计 + 算法规格 + 开发任务书 + Agent 执行协议  
适用仓库：当前 `XJCheck-master` 代码基线  
目标输入：普通产出型 DWG/DXF 项目，不假设保留 AutoCAD Electrical/EPLAN 原生电气对象  
目标输出：可解释、可回溯、低误报的跨页端子/连接关系审计结果

---

## 1. 执行摘要

当前项目已经具备完整的软件骨架、findings 体系、页面分类与路由、多个图种 Extractor、Pair/Issue 模型、本地界面和大量回归测试。问题不在于“项目还没做起来”，而在于连接真值的生成顺序仍然不正确：系统主要先根据 `LineGroup + 端点邻域文本` 生成 Pair，再在报告阶段构建 `wire_topology` 影子网络解释结果。

这种顺序会导致两个结构性风险：

1. **页面模板过拟合**：新图种出现时，系统倾向于增加页面专用正则、半链补偿、数字前缀、局部列、body-port 等规则；
2. **局部证据冒充连接真值**：几何附近的数字或块可以影响配对甚至线段桥接，但它们不一定属于同一电气网络。

目标架构必须改为：

```text
项目与侧车
  -> CAD Reader Adapter
  -> 原始实体标准化
  -> Geometry Graph（几何拓扑候选）
  -> Symbol-Port Graph（符号实例、端口和内部连通性）
  -> Electrical Net Graph（确定线网）
  -> Semantic Attachment Graph（文字、数字和端子身份附着）
  -> Project Cross-page Graph（项目级跨页端点）
  -> Constraint Resolver
  -> Rule Engine
  -> Issue + Witness Path
```

最终技术决策：

- **采用**原始 DWG/DXF 矢量对象作为主输入；
- **采用**确定性拓扑作为连接主干；
- **建设**企业/项目高频符号与端口依赖库；
- **采用**全局约束求解消除局部歧义；
- **保留但降级**邻域算法，仅用于生成文本/端点候选及 legacy shadow；
- **暂不让 GNN 接管**最终网络或 critical issue；
- **后续可引入**学习排序器或异构 GNN，用于边、符号、文字归属的概率消歧；
- **所有高风险自动结论必须具备**确定性证据、置信度分解和完整 witness path。

---

## 2. 产品目标与非目标

### 2.1 产品目标

用户导入一套项目目录。项目可能包含 10–40 张 DWG，也可能包含 `.prj`、端子排 XML 等侧车文件。系统在本地完成：

1. 识别项目边界、页序、页面类别和可审计范围；
2. 从 CAD 原始实体恢复线段、交点、符号实例和端口；
3. 构建页面内电气网络；
4. 将端子数字、线号、设备前缀、跨页标识附着到网络端点；
5. 在项目范围内建立跨页候选关系；
6. 检测数字不一致、缺失、歧义、一对多、多对一、重复和断网问题；
7. 输出页码、文件、坐标、实体 handle、网络路径、冲突对象、置信度和原因；
8. 把不确定情况放入人工复核，而不是强行判错。

### 2.2 MVP 核心

MVP 仍聚焦：

> 同一套图中，连接线网两端的数字/端子身份是否在跨页关系中一致。

但“端点”不再定义为一条水平 LineGroup 的左右边界，而定义为：

> `ElectricalNetwork` 的开放端点、符号端口或明确跨页中断点。

### 2.3 非目标

第一阶段不做：

- 完整电气功能仿真；
- 电流、电压、保护逻辑动作分析；
- 任意扫描 PDF 的全自动理解；
- 自动修改 DWG；
- 一次性建设完整 IEC/GB 符号库；
- 用 VLM/GNN 直接给出不可解释的最终错误结论；
- 为每个新文件名继续增加新的主链分支。

---

## 3. 本次语料审查结论

### 3.1 语料规模

本次压缩包实际包含：

- 第一组保护柜：1 套，28 张；
- 第二组测控柜：1 套，24 张；
- 第三组合同子项目：25 套，450 张；
- 合计：27 套，502 张 DWG。

所有项目都带有 `.prj` 和 `LdDzbInfo.xml`，全部 DWG 头为 AC1018。`.prj` 与实际文件未发现缺页/多页名称不一致；第一套存在重复页码 `04`，说明稳定主键必须使用 `sheet_order + file_id`，不能只用页码。

### 3.2 第三组域迁移

第三组不仅增加数量，还引入大量前两套不充分覆盖的结构族：

- 交换机回路/接线；
- 通信管理机；
- 防火墙；
- PMU 采集器和集中器背板；
- 操作箱多页原理与背板；
- 电度表接线；
- 时钟对时；
- 端子表；
- 主保护箱/非电量保护箱背面接线；
- 多种网络、远动、光纤、对时和接口联系图；
- 大量标题被当前标题族归为“其他/未知”。

这意味着“前两套达到 100%”并不构成泛化证明。训练、调参与最终测试必须按**项目**隔离，不能按页面随机拆分。

### 3.3 侧车文件的价值

`.prj` 提供：

- 项目名；
- 页面分组；
- 页序；
- 页面类别；
- 文件名。

`LdDzbInfo.xml` 提供：

- 项目/设备名；
- 端子排名称；
- 左/右侧；
- 端子排长度。

它们不能替代线网真值，但可作为：

- 页面路由先验；
- 端子排词表；
- scope/prefix 解析先验；
- 弱监督标签；
- 结果一致性检查。

`AirSwitchClassSet.xml` 在 27 套项目中均为空，当前不应被当作有效语义来源。

### 3.4 当前路由风险

当前 scan 级第三组路由为：

- WireDiagram：203；
- Component：47；
- Terminal：68；
- LayoutOnly：52；
- Skip：80。

其中背板页默认进入 `LayoutOnlyExtractor`，除非被几何规则识别为表格。`LayoutOnlyExtractor` 又不在 `_AUDIT_ROUTE_TARGETS`，所以不少背板页可能只分类、不进入连接审计。这与第三组包含大量 PMU/操作箱/保护箱背板的事实直接冲突。

### 3.5 当前代码的真实优点

不得推倒的现有资产：

- 项目扫描、sidecar 解析和稳定 manifest；
- CAD 实体抽取模型；
- findings/Parquet/JSON/Markdown 产物；
- 页面分类与路由框架；
- Pair、Issue、RuleBase 和报告；
- 前端和问题状态；
- 323 项回归测试；
- `wire_topology.py` 已具备 endpoint merge、T/十字交点、gap bridge、network 输出和 topology shadow；
- 现有规则经验可转化为符号库、文本角色和约束，而不是全部丢弃。

### 3.6 当前架构的核心缺口

1. `wire_topology` 在报告写出阶段才运行，不是 PairBuilder 的输入；
2. 使用 Union-Find 直接把候选桥接折叠为网络真值，缺少 `possible/rejected/unknown` 状态；
3. inline text 或 block span 可触发 bridge，证据过弱；
4. topology 文件本身仍含 KLP/CLP/ZKK 等角色正则，几何层与业务语义耦合；
5. 文本、符号端口与线网没有统一的全局约束；
6. 当前 Reader 自动探测只支持两个固定 Windows ODA 路径；
7. 页面分类仍依赖少量硬阈值和标题类别，不能稳定表达未知结构；
8. 同一条连接的最终 Issue 缺少从原始 handle 到跨页对象的完整 witness path。

---

## 4. 行业最佳实践反推

成熟 ECAD 的共性不是“OCR 更强”，而是设计数据从一开始就是对象化、连接化、库驱动和规则驱动的：

- AutoCAD Electrical 的审计对象包括未连接线端、缺失/重复线号、重复端子/引脚、无导线的连接属性和同一网络中的类别冲突；同时 wire gap 使用持久化 Xdata 指针，跨页 signal 使用命名 source/destination code；
- EPLAN 在检查前更新 connection data，再执行项目级检查；检查方案可配置，消息有严重度、页面、设备和位置，并覆盖端子、插头、电缆、设备、短路、环路、缺失 cross-reference 和 interruption point；
- Zuken E3 采用 object-oriented project data、intelligent component library、automatic connections、online terminal plan 和 signal cross-reference；
- Siemens Capital 明确区分 logical connectivity、physical wiring 和 topology，并在统一模型上做 correct-by-construction DRC。

普通 DWG 不保留这些完整对象，因此 XJCheck 应重建一个“审计所需的最小 ECAD 模型”，而不是试图仅凭画面邻域模拟成熟产品的结果。

本项目可借鉴的产品能力：

1. 项目级单一事实源；
2. 连接在审计前统一刷新；
3. 命名跨页端点和 reciprocal relationship；
4. 符号库明确端口和内部连通性；
5. 规则 scheme 可启停、配置和分级；
6. Issue 可忽略、修复、复查和追溯；
7. 自动错误和人工复核严格分层；
8. 所有消息可定位到页面和对象；
9. 规则不直接依赖 GUI 或原始文件读取；
10. 图面只是模型的视图，规则运行在模型上。

---

## 5. 目标领域模型

### 5.1 层 0：Project Manifest

对象：`Project`, `SourceFile`, `Sheet`, `SidecarFact`, `ReaderRun`。

必须字段：

- project_id / project_hash；
- source file SHA-256；
- sheet_order；
- filename_page_no / sidecar_page_no / titleblock_page_no；
- category prior；
- reader backend/version；
- unit/coordinate system；
- conversion warnings。

### 5.2 层 1：CAD Primitive Model

对象：

- `PrimitiveSegment`；
- `TextPrimitive`；
- `BlockInstance`；
- `BlockDefinition`；
- `ArcPrimitive`；
- `CirclePrimitive`；
- `InsertTransform`。

每个对象必须保留：

- 原始 entity handle；
- parent handle；
- 原始类型；
- layer/color/linetype；
- modelspace/layout；
- 世界坐标；
- 局部坐标；
- block nesting path；
- reader provenance。

### 5.3 层 2：Geometry Graph

节点类型：

- `EndpointNode`；
- `IntersectionNode`；
- `TJunctionNode`；
- `CrossingObservationNode`；
- `GapEndpointNode`；
- `SymbolBoundaryPoint`。

边类型：

- `PrimitiveEdge`；
- `SnapCandidateEdge`；
- `IntersectionCandidateEdge`；
- `GapCandidateEdge`。

每条候选关系具有状态：

```text
ASSERTED  确定连接，可进入 Net
POSSIBLE  有证据但未满足强约束
REJECTED  确定不连接
UNKNOWN   信息不足
```

### 5.4 层 3：Symbol-Port Graph

对象：

- `SymbolFamily`；
- `SymbolInstance`；
- `SymbolPort`；
- `PortBindingCandidate`；
- `InternalConnection`；
- `TextSlot`。

符号实例不是一个 bbox。它必须有：

- family；
- rotation/mirror/scale；
- 局部端口坐标；
- 变换后的世界端口坐标；
- 端口方向；
- 内部连接矩阵；
- 文字槽；
- unknown-family 状态。

### 5.5 层 4：Electrical Net Graph

对象：`ElectricalNetwork`, `NetworkMember`, `OpenEndpoint`, `NetworkPath`, `UncertainBoundary`。

Network 只包含 ASSERTED 连接。POSSIBLE 边不得提前 Union。

Network 必须记录：

- member primitive IDs；
- junction IDs；
- symbol port IDs；
- open endpoints；
- branch count；
- cycle count；
- bbox/length；
- uncertain adjacent edges；
- confidence decomposition；
- build decisions。

### 5.6 层 5：Semantic Attachment Graph

对象：

- `SemanticToken`；
- `TerminalToken`；
- `WireNumberToken`；
- `DeviceTagToken`；
- `CrossPageToken`；
- `PrefixScope`；
- `TextAttachmentCandidate`；
- `TextAttachment`。

关系：

- labels_port；
- labels_network；
- labels_endpoint；
- inside_symbol_slot；
- scopes_token；
- annotation_only。

### 5.7 层 6：Project Cross-page Graph

对象：

- `CrossPageEndpoint`；
- `EndpointIdentityCandidate`；
- `EndpointIdentity`；
- `CrossPageMatch`；
- `ProjectPair`。

跨页身份至少包含：

- normalized terminal value；
- prefix/scope；
- source sheet/order；
- network endpoint；
- direction；
- reference page/column（若存在）；
- reciprocal requirement；
- candidate alternatives。

### 5.8 层 7：Audit Model

对象：`RuleRun`, `Issue`, `EvidenceRef`, `WitnessPath`, `DecisionTrace`, `ReviewState`。

每个 Issue 必须有：

- rule_id/version；
- severity；
- auto/review；
- confidence；
- involved endpoints/networks；
- competing hypothesis；
- witness path；
- recommended action；
- resolution state；
- rerun lineage。

---

## 6. CAD Reader Adapter 规格

### 6.1 接口

```python
class CadReader(Protocol):
    backend_name: str
    backend_version: str

    def probe(self, path: Path) -> ReaderProbe: ...
    def read(self, path: Path, options: ReaderOptions) -> CadDocument: ...
    def export_preview(self, path: Path, out: Path) -> PreviewResult: ...
```

实现优先级：

1. `OdaDwgReader`：默认生产路径；
2. `DxfEzdxfReader`：转换后解析；
3. `RealDwgReader`：后续高保真/Windows 企业路径；
4. `LibreDwgReader`：实验/独立交叉验证；
5. `EmbeddedPreviewReader`：只做预览和 QC，绝不生成连接真值。

### 6.2 当前必须修复

现有 `_detect_odafc_exe()` 只探测两个 Windows 路径。必须支持：

- config absolute path；
- `shutil.which("ODAFileConverter")`；
- Linux `unix_exec_path`；
- AppImage；
- macOS；
- executable health check；
- backend capability matrix；
- reader fallback 和失败原因分类。

### 6.3 读取后验证

每页至少验证：

- 实体总数非零；
- modelspace/layout 分布；
- bbox 合理；
- 文本可读取率；
- block definition 可解析率；
- invalid entities；
- unit/header；
- preview 与实体 bbox 是否大致一致。

读取失败不得生成“无问题”报告，状态必须为 `INCOMPLETE_EXTRACTION`。

---

## 7. 线网抽取算法规格

### 7.1 实体归一化

将 LINE、LWPOLYLINE、POLYLINE、ARC 等转换为可求交 Primitive。弧线可保留解析表达或按容差离散，但必须保留 parent entity。

不再只抽取水平线。方向是特征，不是过滤前提。

### 7.2 坐标和块变换

所有 block 内图元按嵌套变换映射到 WCS：

```text
WCS = ParentTransform × InsertTranslation × Rotation × Scale × Mirror × LocalPoint
```

禁止只用 block insertion point 代表整个符号。

### 7.3 交点候选

空间索引生成以下候选：

- endpoint-endpoint；
- endpoint-on-segment；
- segment-segment intersection；
- collinear overlap；
- near-snap；
- gap；
- line-to-symbol-port。

### 7.4 Junction 分类

分类器输入：

- 几何距离与角度；
- 端点/线身角色；
- dot/circle presence；
- bridge arc presence；
- symbol port presence；
- layer/linetype；
- 重叠关系；
- 页面和项目模式；
- 可选模型分数。

输出：`ASSERTED/POSSIBLE/REJECTED/UNKNOWN` + reason codes。

### 7.5 十字交叉

默认策略必须保守：

- 有连接圆点或明确端点落在线身：可 ASSERT；
- 有跳线弧/桥符号：REJECT crossing connection；
- 两条完整线仅几何穿越且无连接证据：默认 UNKNOWN 或 REJECT，不能自动 Union；
- 符号库定义优先于纯几何。

### 7.6 Gap Bridge

Gap Bridge 不再直接 union。生成 `CandidateBridge`：

```json
{
  "left_node": "...",
  "right_node": "...",
  "gap": 12.4,
  "collinearity": 0.99,
  "intervening_text_ids": ["T..."],
  "intervening_symbol_ids": ["SI..."],
  "layer_compatibility": 1.0,
  "symbol_policy": "pass_through|isolated|unknown",
  "state": "POSSIBLE"
}
```

只有以下强证据组合才 ASSERT：

- 符号库明确 `pass_through`；或
- 两侧绑定到同一符号的内部导通端口；或
- 项目内同一 family 多个实例得到一致人工验证；或
- 高置信模型 + 硬约束无冲突 + 阈值达标。

“中间有文字”不能单独成为连接依据。

### 7.7 Network 物化

只对 ASSERTED 边做连通分量。POSSIBLE 边存放在 network boundary，不污染 network truth。

Network 构建后运行结构验证：

- 不合理的超大网络；
- 跨越多个不相关设备框；
- 异常高 degree；
- isolated one-segment network；
- unexpected cycles；
- 多个 competing gap bridge；
- 同一 port 被多网占用。

---

## 8. 符号与端口依赖库

### 8.1 为什么必须建设

普通 DWG 的连接歧义主要发生在：

- 符号遮挡导线；
- 元件内部端口是否导通；
- 端子排和设备框多端口；
- 跳线/连接点；
- 背板和元件页；
- 文本槽和局部编号；
- 通信设备端口。

没有端口模型，纯线网只能给出几何连通，不能给出电气连通。

### 8.2 建库策略

不要从完整 IEC 库开始。先从当前 502 张图中 bootstrap：

1. 统计 block name、normalized name、definition hash 和实例数；
2. 统计旋转、镜像、scale；
3. 统计外部线进入 bbox 的位置簇；
4. 统计 ATTRIB tags 和内部文本槽；
5. 统计与当前失败 Issue 的关联度；
6. 选 Top 20–50 高频/高风险 family 人工标注；
7. 将现有硬编码块知识迁移为 YAML；
8. 未知块进入 queue，不新增页面专用代码。

首批应覆盖当前代码已显式记忆的 family，包括但不限于：

- `FJL-25-2A_Mirror`；
- `KK2P` / `KK3P`；
- `JR-01` / `KK1P`；
- `WBH-814E-E1SA-101`；
- 高频 `PWF`；
- 当前 component/table extractor 中所有硬编码块。

### 8.3 符号 schema

见 `schemas/symbol_library.schema.json`。最小字段：

- family_id；
- aliases；
- block_name regex；
- geometry fingerprint；
- ports；
- internal connections；
- text slots；
- transform policy；
- electrical behavior；
- provenance；
- verification status；
- version。

### 8.4 未知符号策略

未知块不得被默认为导通或绝缘。处理为：

- 提取外部候选端口；
- 记录进入线位置；
- 给出 `UNKNOWN_SYMBOL_BEHAVIOR`；
- 若影响最终跨页结论，Issue 自动降为 review；
- 进入符号标注队列。

---

## 9. 文本、端子身份和局部语义

### 9.1 邻域逻辑的新角色

邻域搜索仍存在，但只生成候选：

```text
Text -> candidate labels Endpoint/Port/Net
```

它不能再定义：

```text
Text proximity -> connectivity truth
```

### 9.2 Token 解析

将文本拆成：

- raw text；
- normalized text；
- terminal prefix；
- local number；
- full terminal identity；
- wire number；
- device tag；
- page/column reference；
- semantic label；
- annotation。

示例：

```text
5FD25   -> prefix=5FD, local=25, terminal_identity=5FD:25
5n105   -> scope=5n, local=105
X1:13   -> strip=X1, terminal=13
```

### 9.3 候选特征

TextAttachmentCandidate 应包含：

- point-to-endpoint distance；
- bbox-to-branch distance；
- tangent/direction compatibility；
- side of port；
- same row/column；
- text layer/style/height；
- inside symbol text slot；
- sidecar terminal prefix membership；
- page zone；
- project repetition；
- competing candidate margin。

### 9.4 Scope 解析

现有 scoped prefix、body-port、local number 规则应转化为独立的 `ScopeResolver`，而不是散落在 candidates/pairs/topology 中。

作用域可能由以下边界定义：

- 同一 symbol；
- 同一 row band；
- 同一 branch；
- 同一 network；
- 同一 column；
- 同一 page zone；
- 直到下一个 prefix marker。

### 9.5 全局唯一性

一个文字默认只能作为一个主端子身份，但允许：

- wire-number copy；
- cross-reference display copy；
- table header scope；
- explicitly repeated annotation。

这些例外必须以 role 表达，而不是任意重复使用。

---

## 10. Constraint Resolver

### 10.1 为什么先做约束再做 GNN

当前很多错误来自多个局部候选互相竞争。全局约束可以在不依赖大量标签的情况下解决：

- 一个 port 最多绑定一个主网络；
- 一个 terminal token 最多绑定一个 endpoint；
- 一个 network endpoint 至多选择一个主跨页身份；
- symbol internal connectivity 不可违反；
- REJECTED crossing 不可因文本接近重新连接；
- 高置信 sidecar prefix 优先；
- reciprocal 要求在项目级满足；
- 多个近似最优解时必须 review。

### 10.2 求解目标

可使用 OR-Tools CP-SAT 或最小费用匹配：

```text
maximize
  Σ candidate_selected * calibrated_score
  - λ1 * unresolved_endpoint
  - λ2 * conflicting_identity
  - λ3 * possible_edge_used
  - λ4 * symbol_constraint_violation
```

硬约束永远不能被概率分数覆盖。

### 10.3 求解输出

必须保存：

- selected candidates；
- rejected candidates；
- objective；
- second-best gap；
- violated soft constraints；
- solver status；
- reason trace。

若第一和第二解的差距过小，进入人工 review。

---

## 11. 跨页匹配和审计规则

### 11.1 新 Pair 定义

旧定义：

```text
LineGroup.left_text -> LineGroup.right_text
```

新定义：

```text
CrossPageEndpoint A
  -> ElectricalNetwork / SymbolPort witness
  -> CrossPageEndpoint B
  -> EndpointIdentity
```

### 11.2 匹配候选

跨页候选来自：

- 完整端子身份相等；
- source/destination code；
- 页码/列号 reference；
- 同一 wire number；
- reciprocal token；
- sidecar terminal strip vocabulary；
- 方向和页面类别；
- 项目级唯一性。

### 11.3 规则

必须重写或新增：

- `R-NET-OPEN-END-UNLABELED`；
- `R-NET-DANGLING-SEGMENT`；
- `R-NET-OVERMERGE-SUSPECTED`；
- `R-NET-SPLIT-SUSPECTED`；
- `R-PORT-MULTIPLE-NETS`；
- `R-UNKNOWN-SYMBOL-AFFECTS-AUDIT`；
- `R-ENDPOINT-AMBIGUOUS-TEXT`；
- `R-CROSS-PAGE-MISSING-RECIPROCAL`；
- `R-CROSS-PAGE-IDENTITY-CONFLICT`；
- `R-CROSS-PAGE-ONE-TO-MANY`；
- `R-CROSS-PAGE-MANY-TO-ONE`；
- `R-SHEET-PAGE-MISMATCH`；
- `R-INCOMPLETE-EXTRACTION`。

### 11.4 Hard error 门槛

`critical/major auto issue` 只有在以下均满足时产生：

- Reader 完整；
- topology 为 ASSERTED；
- 涉及符号均已知，或不经过符号；
- text attachment 唯一；
- cross-page identity 唯一；
- 无接近的替代解释；
- confidence 校准达阈值；
- witness path 完整。

否则必须为 `review`。

---

## 12. 按图种处理策略

### 12.1 二次原理/普通回路图

主链：Geometry Graph → Symbol Ports → Net → Endpoint Text。

重点：分支、十字、跳线、元件遮挡、跨页箭头、开放端点。

### 12.2 元件接线图

主链：Symbol-first。

不能把每条内部图形线当导线。先识别 block/family/port，再将外部线绑定端口。一个设备框可能包含多排端口和内部说明。

### 12.3 背板接线图

必须从 `LayoutOnly` 升级为可审计图种。采用 hybrid：

- block/port；
- virtual terminal table；
- row/column grouping；
- external line binding；
- local labels。

背板不是纯布局图。

### 12.4 屏端子图/端子表

主链：Grid/row/column + terminal identity + bridge mapping。

表格线不是导线。应先重建表格和单元格，再解析端子排、行号、内部/外部侧、桥接关系。线网只用于局部接线，不可主导整页。

### 12.5 网络通信/交换机/防火墙/时钟图

采用 connector/port graph。线可能表示以太网、光纤、串口、对时或逻辑关联，不应统一视为导电 wire。

新增 `ConnectionMedium`：

- electrical_wire；
- ethernet；
- optical_fiber；
- serial_bus；
- time_sync；
- logical_reference；
- unknown。

MVP 可不理解协议，但至少防止不同媒介错误合并。

### 12.6 屏面布置/封面/目录/标签

只做 metadata/sidecar/QC，不进入连接审计。

### 12.7 Unknown 页面

禁止新增“按文件名硬编码的新 Extractor”。应：

1. 生成通用 page feature profile；
2. 跑 Geometry/Symbol/Table 三类候选分析；
3. 输出 route probabilities；
4. 进入人工 review；
5. 人工结果沉淀为结构族配置或训练样本。

---

## 13. 置信度与可解释性

### 13.1 拆分置信度

不得只保留一个 Pair score。至少包含：

- reader_confidence；
- extraction_confidence；
- geometry_confidence；
- junction_confidence；
- symbol_family_confidence；
- port_binding_confidence；
- network_confidence；
- text_role_confidence；
- text_attachment_confidence；
- cross_page_confidence；
- issue_confidence。

### 13.2 最弱证据原则

高风险 Issue 的置信度不应使用平均值掩盖短板，可按：

```text
issue_confidence = min(critical_components) * evidence_completeness * calibration_factor
```

### 13.3 Witness Path

每个 Issue 生成：

```text
DWG file / sheet
-> entity handle
-> primitive segment
-> junction decision
-> electrical network
-> symbol port（如有）
-> open endpoint
-> semantic token
-> cross-page identity
-> conflicting endpoint
```

前端即使不渲染 DWG，也能显示：文件、页、坐标、handle、数字、网络 ID、路径和原因。可选局部 SVG/PNG 仅用于辅助。

---

## 14. GNN/学习模型决策

### 14.1 当前结论

不应直接“上 GNN”替换现有规则。原生矢量数据提供精确几何，确定性构图应先完成。研究中更合理的路线也是先将矢量实体建图，再用图模型做线级语义或关系分类。

### 14.2 第一阶段学习任务

优先使用 GBDT/LightGBM/XGBoost 或 learning-to-rank：

- CandidateBridge 是否有效；
- TextAttachment 候选排序；
- SymbolFamily 候选排序；
- Junction connected/crossing 分类。

这些模型更易解释、数据需求更低、校准更简单。

### 14.3 GNN 适用任务

当局部模型在 held-out 项目上无法解决长距离上下文时，再建立异构图：

节点：segment, junction, symbol, port, text, zone, network_candidate。  
边：touches, intersects, near, aligned, inside, same_row, same_column, belongs_to, candidate_bridge, labels。

可选：Heterogeneous Graph Transformer、R-GCN、GAT。

### 14.4 禁止事项

GNN 不得直接：

- 强制合并两个大网络；
- 覆盖明确符号端口约束；
- 生成 critical issue；
- 把概率当作电气连接事实；
- 使用同项目页面同时出现在 train/test 的泄漏切分。

### 14.5 启动门槛

- 至少 10 套以上项目完成图结构标注；
- 按项目隔离 train/val/test；
- 每个任务至少数千个稳定标签；
- deterministic + symbol + constraint baseline 已建立；
- 模型在 held-out project 上有显著增益；
- 概率校准；
- 自动区间 precision 达业务门槛；
- 低于阈值全部 review。

---

## 15. 失败闭环 Loop

### 15.1 每次运行

```text
Run Reader
-> Build Findings V2
-> Legacy Pair shadow
-> Topology/Port/Constraint primary
-> Compare engines
-> Generate Failure Queue
-> Human review
-> Convert decision into reusable knowledge
-> Regression
-> Promote or rollback
```

### 15.2 Failure Queue 类别

- reader/conversion failure；
- zero-entity page；
- unknown page structure；
- unknown high-impact block；
- topology overmerge；
- topology split；
- ambiguous crossing；
- unresolved gap；
- unbound symbol port；
- unlabeled open endpoint；
- ambiguous text assignment；
- cross-page no candidate；
- cross-page multiple candidates；
- legacy/new engine disagreement；
- issue without witness path。

### 15.3 人工复核界面

每个 review tile 显示：

- DWG 内嵌预览或 DXF/SVG 局部图；
- primitive overlay；
- junction state；
- network color；
- symbol bbox 和 ports；
- text candidates；
- selected/rejected hypothesis；
- label controls。

### 15.4 知识沉淀优先级

人工结论依次沉淀为：

1. Reader bug；
2. deterministic geometry rule；
3. symbol family/port definition；
4. project profile/sidecar mapping；
5. global constraint；
6. model training example；
7. 页面专用例外（最后手段，必须有 expiry/owner）。

---

## 16. 代码改造总图

### 16.1 新目录

```text
src/dwg_audit/
  readers/
    base.py
    registry.py
    oda_reader.py
    ezdxf_reader.py
    realdwg_reader.py
    libredwg_reader.py

  topology/
    entity_normalizer.py
    block_transform.py
    spatial_index.py
    intersection_builder.py
    segment_splitter.py
    junction_classifier.py
    gap_candidates.py
    topology_decisions.py
    geometry_graph.py

  symbols/
    schema.py
    registry.py
    fingerprint.py
    instance_resolver.py
    port_transform.py
    port_binder.py
    internal_connectivity.py

  networks/
    net_builder.py
    network_validator.py
    open_endpoints.py
    path_finder.py

  semantics/
    token_parser.py
    text_role.py
    scope_resolver.py
    text_attachment.py
    terminal_identity.py
    cross_page_reference.py

  inference/
    constraint_resolver.py
    feature_builder.py
    ranker.py
    calibration.py
    optional_gnn.py

  audit_v2/
    project_graph.py
    rules/
    issue_builder.py
    witness_path.py
```

### 16.2 现有模块处置

- `audit/wire_topology.py`：拆分并前移，不再由 report 调用；
- `audit/line_groups.py`：保留为 legacy/display projection；
- `audit/candidates.py`：迁移为 text candidate features，禁止决定 connectivity；
- `audit/pairs.py`：迁移为 legacy shadow；新 Pair 来自 CrossPageEndpoint；
- `audit/wire_components.py`：硬编码 family 迁入 symbol registry/scope resolver；
- `page_extractors.py`：从“独立识别器”调整为“页面策略组合器”；
- `page_classifier.py`：输出多标签结构特征和 route probabilities，而非唯一模板；
- `report/artifacts.py`：只写产物，不再执行核心推理；
- `rules.py`：逐步迁到 Audit V2，Legacy Rules 并行比较。

### 16.3 Pipeline 新顺序

```python
manifest = scan_project()
documents = reader_registry.read_all(manifest)
primitives = normalize_entities(documents)
page_profiles = classify_page_structure(primitives, sidecars)
geometry_graph = build_geometry_graph(primitives)
symbols = resolve_symbol_instances(primitives, symbol_registry)
port_candidates = bind_ports(symbols, geometry_graph)
topology_decisions = decide_connectivity(geometry_graph, port_candidates)
networks = materialize_asserted_networks(topology_decisions)
tokens = parse_semantic_tokens(primitives.texts, sidecars)
attachments = build_text_attachment_candidates(tokens, networks, symbols)
solution = constraint_resolver.solve(port_candidates, attachments, topology_decisions)
cross_page_graph = build_cross_page_graph(solution, sidecars)
issues = audit_v2.run(cross_page_graph)
write_findings_v2(...)
```

---

## 17. Findings V2

必须新增表：

```text
primitive_segments.parquet
geometry_nodes.parquet
geometry_edges.parquet
junction_observations.parquet
topology_decisions.parquet
symbol_instances.parquet
symbol_ports.parquet
symbol_internal_connections.parquet
port_binding_candidates.parquet
port_bindings.parquet
electrical_networks.parquet
network_members.parquet
network_open_endpoints.parquet
semantic_tokens.parquet
text_attachment_candidates.parquet
text_attachments.parquet
cross_page_endpoints.parquet
cross_page_match_candidates.parquet
cross_page_matches.parquet
constraint_decisions.parquet
model_predictions.parquet
```

Findings V2 版本规则：

- `schema_version` 必须存在；
- 原始对象不可被覆盖；
- 推理层以 append-only decision 记录；
- 任何最终对象可回溯原始对象；
- 规则重跑不重新读 DWG；
- Reader/geometry 改变时才使 findings cache 失效；
- 规则配置变化只重跑 project graph/rules。

---

## 18. 开发里程碑

### M0：冻结基线与可复现运行，1 周

- 安装/探测 ODA；
- 27 套项目全量 current-head run；
- 保存 findings/issues/coverage；
- 运行本包 failure queue；
- 固定 legacy golden；
- 记录运行时间和失败率。

出口：502 页 Reader completion 报告；不允许把读取失败当 clean。

### M1：Reader Adapter 与跨平台修复，1–2 周

- 抽象 CadReader；
- Windows/Linux/AppImage；
- health check；
- per-file backend provenance；
- retry/fallback；
- preview extraction。

出口：目标环境 502/502 可读或有明确不可读原因。

### M2：Geometry Graph 主链，2–4 周

- entity normalization；
- nested block transforms；
- spatial index；
- intersections/splitting；
- topology decisions 四态；
- network materialization；
- overmerge/split diagnostics。

出口：不依赖 Pair 即可输出 network/open endpoint/witness。

### M3：Symbol Library Bootstrap，2–3 周

- block statistics；
- fingerprint；
- port-entry clustering；
- Top 20–50 family 人工标注；
- 迁移当前硬编码；
- unknown symbol queue。

出口：高影响块覆盖率和 port binding precision 可量化。

### M4：Semantic Attachment 与 ScopeResolver，2–4 周

- token parser；
- sidecar terminal vocabulary；
- text roles；
- network/port attachment candidates；
- scoped prefix；
- confidence margin。

出口：文本候选不再控制 topology；top-k recall 可评估。

### M5：Constraint Resolver，2–3 周

- CP-SAT/min-cost model；
- hard/soft constraints；
- competing solution；
- decision trace；
- review threshold。

出口：候选冲突得到全局一致解；模糊解自动 review。

### M6：跨页 Graph 与 Audit V2，2–4 周

- endpoint identities；
- reciprocal matching；
- conflict rules；
- witness path；
- issue clustering；
- legacy/new comparison。

出口：MVP 跨页匹配以 network endpoint 为基础。

### M7：前端复核与局部可视化，1–3 周

- failure queue；
- SVG/PNG tile；
- network overlay；
- symbol/port overlay；
- selected/rejected candidate；
- human label export。

出口：工程人员可定位、裁决并反馈。

### M8：学习模型评估，4–8 周，可选

- 数据清洗；
- project-held-out split；
- ranker baseline；
- calibration；
- optional heterogeneous GNN；
- shadow deployment。

出口：只有显著优于 deterministic/constraint baseline 才接入。

---

## 19. 测试和验收

### 19.1 单元测试

- 坐标变换；
- segment intersection；
- T/十字分类；
- dot/jumper；
- gap candidate；
- symbol port transform；
- internal connectivity；
- token parsing；
- scope；
- CP-SAT constraints；
- witness path。

### 19.2 Golden 图夹具

建立小型 DXF fixture：

- 连接十字；
- 非连接十字；
- T；
- 文字断线；
- 元件双端口；
- 未知块；
- 端子表；
- 跨页 source/destination；
- 故意冲突。

### 19.3 真实项目切分

不得把同一项目页面随机分散。使用 `reports/benchmark_split_proposal.csv` 为起点，最终：

- calibration：前两套，仅用于兼容；
- training：第三组一部分；
- validation：独立项目；
- heldout test：完全未调参的多结构项目。

### 19.4 指标

Reader：

- page read completion；
- entity coverage；
- text decode rate；
- unknown entity rate。

Topology：

- junction precision/recall；
- crossing false-connect rate；
- network overmerge rate；
- network split rate；
- open endpoint precision/recall。

Symbol：

- family coverage；
- port localization error；
- port binding precision；
- high-impact unknown count。

Semantic：

- text role accuracy；
- attachment top-1/top-3 recall；
- terminal identity accuracy；
- ambiguity calibration。

Audit：

- hard issue precision；
- true error recall；
- review yield；
- unexplained issue rate；
- witness completeness。

### 19.5 门槛

建议：

- critical/major 自动错误 precision ≥ 99%；
- crossing false-connect 接近 0；
- 任一 unresolved topology/symbol 不得产生 critical；
- 100% Issue 有页面、坐标、对象和 witness；
- 新项目进入 generic pipeline 不需要新增文件名分支；
- held-out project 指标必须单独报告；
- 任何指标下降可回滚到 legacy shadow。

---

## 20. 本地 Agent 执行约束

Agent 必须遵守：

1. 先生成 baseline，不直接改算法；
2. 一次只解决一个 failure family；
3. 不得用页面文件名/具体数字写主链补丁；
4. 优先修 Reader、Geometry、Symbol、Constraint；
5. 所有新知识必须进入 schema/config/library；
6. 所有候选保留，不只保存 winner；
7. 所有 union 必须来自 ASSERTED decision；
8. 规则不得直接读 DWG；
9. UI 不得执行推理；
10. 每次提交附带 held-out 结果和差异报告；
11. GNN 只能 shadow，直到 precision、calibration 和解释性门槛通过；
12. 发现不确定问题时输出 review，不允许静默忽略或强判。

Agent 每轮输出：

```text
run_manifest.json
findings_v2/
failure_queue.csv
engine_comparison.json
metrics_by_project.csv
review_tiles/
decision_log.md
```

---

## 21. Definition of Done

线网升级 MVP 完成的定义：

- 27 套项目可以批量读取；
- Reader 完整性可验证；
- topology 在 Pair 前构建；
- 候选连接有四态，不再把可能边提前合并；
- 高频符号端口库已建立；
- 背板页不再默认只分类；
- 端子表采用结构化表格语义；
- 文本邻域只生成候选；
- 全局约束选择最终 attachment/match；
- 跨页规则基于 NetworkEndpoint；
- Issue 有完整 witness path；
- legacy engine 处于 shadow，可比较和回滚；
- held-out 项目达到自动错误精度门槛；
- 未达到确定性门槛的结果全部进入 review。

---

## 22. 参考资料索引

详见 `sources/source_matrix.md`。行业和研究结论主要依据 Autodesk、EPLAN、Zuken、Siemens、ODA、ezdxf、GNU LibreDWG、Shapely、OR-Tools 的官方资料，以及矢量技术图 GNN、P&ID 图结构抽取和神经符号电气合规研究。
