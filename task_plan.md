# Task Plan: XJToolkit DWG Audit MVP Closure

## Goal
重新对齐并完成 [doc/任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 定义的 DWG 审计 MVP 主链：输入项目级 DWG，生成结构化 findings 运行态，先做页级分类，再按图种路由到对应识别器，产出 pair / table mapping / evidence，运行项目级规则引擎，并输出可复核异常报告。

## Current Phase
Phase 30

## Phases

### Phase 1: Requirements & Discovery
- [x] 对齐用户连续要求与当前 goal
- [x] 重读任务书与当前 findings
- [x] 识别当前已暂存改动、待提交批次与 M9 缺口
- **Status:** complete

### Phase 2: Planning & Safe Integration
- [x] 建立持久计划文件
- [x] 安排子代理做只读并行梳理
- [x] 结合主线程与子代理信息锁定本轮继续推进项
- **Status:** complete

### Phase 3: Commit Pending Batch
- [x] 复核当前 staged 改动
- [x] 本地提交已验证的桌面端结果页增强批次
- [x] 记录提交结果到 progress
- **Status:** complete

### Phase 4: M9 Native UX Implementation
- [x] 实现启动页原生导入入口高优先级缺口
- [x] 补充必要测试 / mock / README / findings
- [x] 确保不回滚并发 agent 或用户已有改动
- **Status:** complete

### Phase 5: Verification & Next Push
- [x] 运行针对性验证
- [x] 更新 task_plan / progress / findings
- [x] 明确下一阶段剩余缺口
- **Status:** complete

### Phase 6: Native Build Closure And DWG Follow-up
- [x] 修复 Tauri 图标资源，消除 `icon.ico` 解析失败
- [x] 完成 `cargo check` 原生验证
- [x] 完成 `tauri build` + NSIS 安装包真实产出
- [x] 集成并验证一轮 DWG 候选/线组/抽取整改
- [x] 把第二套样本基线补齐到 findings / audit 工作流
- **Status:** complete

### Phase 7: Component Orientation Follow-up
- [x] 在 `二次原理图` 上直接拒收单字符 `DIM/MARK`
- [x] 把 `INSERT` 虚拟实体展开收口为 `元件接线图` 专用
- [x] 让第二套 `19 元件接线图1.dwg` 进入非零 pair 状态
- [x] 为 `20 元件接线图2.dwg` 新增方向感知的 grouping / candidate 逻辑
- [x] 继续收敛 `08/12` 的互补 missing-side 主噪声
- **Status:** complete

### Phase 8: Residual Audit Quality Follow-up
- [x] 继续提高 `20 元件接线图2.dwg` 的候选质量，减少 `1/1`、`1/2` 类低置信配对
- [x] 评估互补半链聚合是否需要扩展到更多页型或垂直几何
- [x] 更新 findings / progress / commit，并为下一轮真实整改收口
- **Status:** complete

### Phase 9: Residual Component Semantics Follow-up
- [x] 继续收敛 `20` 剩余 3 条 `1 -> 2`，判断是否还需要 `HD#` 等更窄派生
- [x] 评估是否需要把 vertical 语义显式透传到报告/UI 展示层
- [x] 继续按真实样本对齐任务书中未完全理解的页型边界
- **Status:** complete

### Phase 10: Page Findings Alignment
- [x] 按任务书补齐 `findings/page_findings/<sheet_id>.md|json` 输出
- [x] 为页级产物补单元/集成测试，覆盖 payload 与落盘目录
- [x] 在第二套样本上实跑确认页级 findings 实际生成
- [x] 基于这批新证据决定下一步先补页级分类/路由，还是先收口 sidecar / desktop 剩余硬缺口
- **Status:** complete

### Phase 11: Internal Findings Runtime And Page-Level Analyst Workflow
- [x] 根据用户更新的任务书，把 `page_findings` 从“默认落盘文件”改为“内部运行态 / 按需落盘记录”
- [x] 保持默认 CLI / regression 链可用，同时让 `page_findings/*.md|json` 改为显式调试开关
- [x] 启动 Batch 1 页级并发审图，只看最强网格化的 4 页
- [x] 汇总 Batch 1 的页级结论，形成真正的 Type Review / Script Planner backlog
- [x] 启动并整合 Batch 2 的 `S0019 / S0021` 页级页审样本
- **Status:** complete

### Phase 12: Terminal Short-Bridge Strip Cleanup
- [x] 结合并发子代理与真实产物，确认 `310-385` 是“短桥接带”而不是普通双侧端子带
- [x] 在 `candidates.py` 为短桥接带增加按列角色分侧 / 单列单侧输出的窄规则
- [x] 补充短桥接带单测，并复跑 mirrored / row-lock / page-classifier 等支撑回归
- [x] 在第一套、第二套真实样本上复跑 analyze + audit，确认 `X -> X` 假双侧配对显著下降
- **Status:** complete

### Phase 13: Terminal Semantic-Row Local-Numeric Guard
- [x] 用并发子代理和真实产物确认 `DK/KLP/ZKK/CLP`、`UA/UB/UC/UN/3U0`、`AC230V`、`Shielding layer` 等语义行会把局部小数字误推成普通 pair
- [x] 在 `candidates.py` 增加 terminal semantic-row local-numeric suppression，并补齐窄单测
- [x] 复跑 targeted pytest 与两套真实样本 audit，对比 Phase 15 / Phase 16 的页级 tradeoff
- [x] 把“低置信 pair 降低、missing-side 显性化上升”的结论写回 findings / progress / plan
- **Status:** complete

### Phase 14: Taskbook Completion Audit
- [x] 逐条重读任务书，按“强证据 / 部分实现 / 未完成 / 偏航”重做完成度审计
- [x] 用并发子代理只读核验“页级分类/路由接管程度”和“TableExtractor 真实闭环程度”
- [x] 把任务书完成度审计与优先级裁决写回 `doc/findings.md`
- [x] 明确本轮唯一核心切片是“元件接线图不再误路由成 Wire/Table”
- **Status:** complete

### Phase 15: Component Route Closure
- [x] 修正 `page_classifier.py` 中元件接线图对 `grid_heavy/table_like` 的优先级
- [x] 补元件页优先级单测，避免 horizontal component 再被误判成 wire/table
- [x] 跑定向 pytest 与两套真实样本 `analyze-project + run-audit`
- [x] 用真实样本证明 component 页已回到 `ComponentDiagramExtractor`，并确认当前两套样本暂无稳定 table 命中
- **Status:** complete

### Phase 16: Taskbook Audit Refresh And TableExtractor Closure Proof
- [x] 以当前头部代码重新核验真实样本 `page_type / route_target / issue evidence` 证据，纠正旧审计结论
- [x] 为 `TableExtractor` 补一条 `analyze-project` 级 synthetic 闭环测试，证明表格页会独立命中路由并产出 `table_mapping`
- [x] 刷新 `page_findings` 中对 `TableExtractor` 的 recognizer / number-matching 描述，避免继续写成 “pending”
- [x] 复跑 targeted pytest、full pytest，以及 second-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 17: Terminal Semantic Channel Contract
- [x] 将 terminal 语义列从纯 `rejection_reason` 升级为显式 candidate `channel`
- [x] 让 PairBuilder 显式只消费 `terminal_numeric_channel`
- [x] 在 `page_findings` 结构摘要中按页汇总 terminal candidate channel counts
- [x] 复跑 targeted pytest、full pytest，以及 second-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 18: Continuation Pair-Kind Contract
- [x] 重新按当前头部代码审计“continuation / audit_disposition”两条最近缺口，确认本轮只做 continuation 语义收口
- [x] 把 continuation 从 `pair.evidence` 隐式标签升级为显式 `pair_kind` 合同
- [x] 让 continuation 不再伪装成 ordinary `pass/discard`，而是稳定保留为 review 证据并旁路 ordinary audit
- [x] 在 findings 运行态中补 `pair_kind_counts`，让 continuation 在页级/项目级摘要可见
- [x] 复跑 targeted pytest、full pytest，以及 first-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 19: Audit Disposition Contract
- [x] 重新按当前头部代码审计 `audit_disposition` 是否仍是最近分类合同缺口
- [x] 在 `PageClassification -> PageRouter -> pipeline -> findings/report` 贯通 `audit_disposition`
- [x] 让下游纳入审计判断显式基于 `audit_disposition=audit_required`
- [x] 复跑 targeted pytest、full pytest，以及 second-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 20: Single-Sided Terminal Continuation Semantics
- [x] 重新按任务书与当前头部真实样本确认“单侧 continuation”是最近关系语义缺口
- [x] 在 `pairs.py` 把端子页单侧 short-bridge / derived numeric half-pair 提升成显式 `pair_kind=continuation`
- [x] 让 `rules.py` 对这类 pair 旁路普通 `R-PAIR-MISSING-SIDE`
- [x] 复跑 targeted pytest、full pytest，以及 first/second-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 21: Terminal Short-Bridge Bridge-Mapping Contract
- [x] 重新按当前头部代码与 `phase23` 实样审计，确认 `bridge_mapping` 比 `semantic_mapping` 更接近任务书主链
- [x] 在 `pairs.py` 把端子页短桥接带里“双侧都来自 `n###` 派生文本、且值不同”的 relation 提升成显式 `pair_kind=bridge_mapping`
- [x] 让 report/evidence 显式展示 `bridge_mapping_kind`
- [x] 复跑 targeted pytest、full pytest，以及 first/second-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 22: Terminal Semantic-Mapping Contract
- [x] 重新按当前头部代码与 `phase24` 实样审计，确认 `semantic_mapping` 已出现可窄切的真实样本入口
- [x] 在 `pairs.py` 把 terminal 页“单侧 numeric relation + 同 line group 存在真实语义 marker”的 relation 提升成显式 `pair_kind=semantic_mapping`
- [x] 让 ordinary missing-side 聚合与 report/evidence 对 `semantic_mapping` 显式旁路并展示 `semantic_mapping_kind`
- [x] 复跑 targeted pytest、full pytest，以及 first/second-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 23: Continuation Candidate Channel Contract
- [x] 重新按 current-head 任务书审计，确认最近缺口已从 pair 级 relation 收口到 candidate 级 `continuation_channel`
- [x] 仅把已在 pair 层识别成 `continuation` / `bridge_mapping` 的 selected numeric candidate 回标成 `continuation_channel`
- [x] 保持 `semantic_mapping` selected numeric 继续留在 `terminal_numeric_channel`，不扩大为新大改
- [x] 复跑 targeted pytest、full pytest，以及 first/second-set 当前头部 `analyze-project + run-audit`
- **Status:** complete

### Phase 24: Semantic Mapping Project Consistency Rule
- [x] 重新按 current-head 任务书审计，确认最近缺口是 semantic-specific project rule，而不是再回页级路由或桌面层
- [x] 为 `pair_kind=semantic_mapping` 落一条最小跨页一致性规则，只处理 stable-singleton normalized endpoint 冲突
- [x] 复跑 targeted pytest、full pytest，以及 first/second-set 当前头部 `analyze-project + run-audit`
- [x] 把结果回写 `doc/findings.md` / `progress.md`，并准备本地提交
- **Status:** complete

### Phase 25: Table Mapping Mixed-Source Consistency Rule
- [x] 重新按 current-head 任务书审计，确认最近缺口已推进到 `table_mapping` vs `ordinary_pair` 的 mixed-source consistency
- [x] 为高置信 `table_mapping` 与 ordinary pair 落一条最小 source-aware 项目级一致性规则
- [x] 补齐 unit + `analyze-project -> run-audit` 级 synthetic 证明
- [x] 复跑 targeted pytest、full pytest，以及 first/second-set 当前头部 `analyze-project + run-audit`
- [x] 把结果回写 `doc/findings.md` / `progress.md`，并准备本地提交
- **Status:** complete

### Phase 26: Header-Semantic Table Mapping Hardening
- [x] 为 `TableExtractor` 补齐“表头前缀 + 行号 -> 逻辑语义端”的表头型三列表格抽取
- [x] 收口单元格主文本选择，避免备注文本破坏 numeric fallback 或被抬成高置信 `table_mapping`
- [x] 补齐 unit + `analyze-project` synthetic 证明，并复跑 full pytest 与两套真实样本
- [x] 把“功能已补齐、M10 仍未闭环”的裁决回写 `doc/findings.md` / `progress.md`
- **Status:** complete

### Phase 27: M10 Acceptance-Mini Harness
- [x] 重新按 current-head 任务书逐条审计，确认页级分类/路由主链已有强证据，而最近显式缺口已经收口到 `M10` / 第 19 节最小验收
- [x] 增加持久化 `acceptance-mini` 5 页夹具与标注 spec，覆盖非回路页跳过、正常 pair、冲突、缺失、多候选 review
- [x] 增加 `evaluate-acceptance` 评估链，量化 pair precision/recall、冲突命中、缺失命中、review 命中与 issue 字段完备性
- [x] 复跑定向 pytest、full pytest，以及 second-set 当前头部 `analyze-project + run-audit`
- [x] 把“acceptance 资产已补齐但 M10 仍未完全闭环”的裁决回写 `doc/findings.md` / `progress.md`
- **Status:** complete

### Phase 28: Real-Sample Scoped Acceptance Baseline
- [x] 重新按 current-head 任务书审计，确认最近缺口已从 synthetic acceptance 资产推进到“真实样本人工标注子集的 pair precision/recall”
- [x] 让 `evaluate-acceptance` 支持按页/图种作用域统计 complete pair precision/recall，避免 1 页标注被整项目其它页污染 precision
- [x] 补 scoped acceptance 集成测试，并新增第二套真实样本 `S0024` 的持久化标注 spec
- [x] 复跑 targeted pytest、full pytest，并在 current-head 第二套真实产物上执行 scoped acceptance
- [x] 把“真实样本第一份 precision/recall 基线已出现，下一步转向更多页与 texts/lines 基线”的裁决回写 `doc/findings.md` / `progress.md`
- **Status:** complete

### Phase 29: Multi-Page Real-Sample Pair Baseline Expansion
- [x] 重新按 current-head 任务书审计，并用只读子代理复核“最近缺口是否已转到 texts/lines 非回退量化”
- [x] 确认更近的缺口仍是“把真实样本 pair 量化从单页 scoped 证明扩成更有代表性的多页基线”
- [x] 让 acceptance scope 支持按 `filename + pair_key` 精确选样，避免高密度真实页被整页普通 pair 分母污染
- [x] 补 pair-ref scoped acceptance 集成测试，并新增第二套 `S0020 + S0024` 的持久化真实样本 spec
- [x] 复跑 targeted pytest、full pytest，并在本轮 fresh rerun 的第二套真实产物上执行 multi-page acceptance
- [x] 把“下一条缺口才更像 texts/lines 基线量化”的裁决回写 `doc/findings.md` / `progress.md`
- **Status:** complete

### Phase 30: Text And Line Non-Regression Quantification
- [x] 重新按 current-head 任务书审计，确认最近单一缺口已切到 `M10` 的“文本抽取不回退 / 线段召回不回退”
- [x] 在 `report/regression.py` 增加 `texts / numeric_texts / lines / line_groups` 抽取计数与 `texts / lines` 页级 no-regression 检查
- [x] 让 per-page 回归比较改用稳定页键 `filename + sheet_order`，并补 `sheet_order` 非数值容错
- [x] 复跑 targeted pytest、full pytest，以及 second-set current-head `compare-regression` 真实样本验证
- [x] 把结果回写 `doc/findings.md` / `progress.md`，并准备本地提交
- **Status:** complete

## Key Questions
1. `M10` 里下一条最近缺口是继续扩 real-sample pair baseline 到更多页型，还是把 `line_groups` 也升级成显式 no-regression status？
2. 若继续扩 real-sample baseline，优先纳入哪一类页更值当：更多 terminal 页、更多 component 页，还是首次纳入普通 wire 页？
3. 当前 `compare-regression` 已量化 texts / lines totals 与 per-page drops；是否还需要把这些指标显式接入 acceptance / CI 固定批次？
4. `S0020` 当前已回到 `ComponentDiagramExtractor`，但 `page_subtype` 仍是 `horizontal_component` 而 line_groups 是 `vertical`；是否需要单独收口这一层 subtype 判定？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| `doc/findings.md` 继续作为唯一权威发现文档 | 用户已明确指定该路径，避免根目录再复制一份 findings 造成漂移 |
| 先提交已通过回归的 staged 批次，再继续开发 | 这批变更已完成验证且彼此内聚，先落一个安全检查点最稳妥 |
| 本轮优先继续 `M9` 高价值桌面端缺口 | 当前任务书中桌面交付仍是最接近用户可见完成度的短板 |
| 启动页优先补“原生文件夹选择 + 拖拽导入” | 这是 M9 启动页中收益最高且与现有 sidecar 契约最贴合的真实缺口 |
| 结果页选中 issue 改为跟随 `filteredIssues` | 避免筛选后右侧详情仍操作被隐藏 issue 的交互错位 |
| 先完成 Tauri 原生编译与打包闭环，再切回 DWG 抽取质量整改 | 桌面端已接近可交付，先消除“能否原生落地”的不确定性，之后再把精力转回任务书主链 |
| `元件接线图` suffix 派生必须保持 `vertical-only` 收口 | 更宽的规则虽然能提升 `20`，但会给 `19` 这类 horizontal component 页引入回退风险 |
| `FJL-25-2A_Mirror` 的虚拟单字符 `1/2` 应视为块内固定引脚号，而不是真实端子候选 | 这类 residual 噪声来自 `INSERT` 展开后的局部伪候选，适合用白名单块名做极窄过滤 |
| 先把 `page_findings` 做成正式产物，再决定是否推进真正分类/路由改造 | 这是任务书里的硬性交付物，且能先把页级证据与剩余盲区显式暴露出来 |
| 用户更新任务书后，`page_findings` 应改为默认内部记录，只在调试时显式落盘 | 这更符合桌面端 / sidecar 运行态，也避免把中间产物误当正式交付物长期保留 |
| 路由/页分类半截基建与 `line_groups.py` 当前脏改动不进入本次提交 | 子代理审查已确认这组改动会打断元件页纵向链路，必须与稳定的 runtime/state 切片隔离 |
| Batch 2 的第一段代码优先落 `S0019` 的 `horizontal_component_block_pin` 护栏 | 当前代码已经具备 `source_block_name`、component orientation 和 virtual text 这些支点，先压掉块内伪 pair 收益最高 |
| `S0021` 的第一刀优先放在 `candidates.py` 的 terminal-strip 候选层，而不是先扩大 suffix regex | 当前主问题是固定列带内的多行竞争与 endpoint 语义错位，先做 line-span query + row-lock + 端子页专用打分，能最小风险地把真实 pair 从 discard 翻到 review |
| `右侧端子图` 应按 mirrored terminal-strip 处理，而不是复用左侧页列偏移 | 当前真实样本已证明右侧页稳定列带是 `start_x+26` 的派生端子列和 `start_x+48.5` 的纯数字列，直接复用左侧页 gate 会把整页候选过滤干净 |
| `310-385` 短桥接带要按“延续列 / 局部序号列 / 单侧 continuation”处理，而不是继续让同一列参与左右两侧候选排序 | 当前真实样本已经证明，这个区段的主要收益不是扩大召回，而是消除 `110 -> 110`、`10 -> 10` 这类假双侧自配对 |
| 任务书完成度必须以当前代码 + 当前测试 + 当前真实样本产物审计为准，而不是以桌面端完成度或历史叙事为准 | 用户已明确要求重新回到 DWG 审计 MVP 主链 |
| 元件接线图必须先保 `ComponentDiagramExtractor` 身份，不能再被 `grid_heavy/table_like` 抢走路由 | 这是当前两套真实样本里“页级分类 + 路由闭环”最短路径上的核心缺口 |
| 在真实样本暂无稳定表格页命中的前提下，`TableExtractor` 的 MVP 证明应改用隔离 synthetic `analyze-project` 集成测试，而不是继续等待假阳性真实页 | 任务书明确允许真实样本不足时用隔离合成/变异样本补足验证 |
| `page_findings` 对 `TableExtractor` 的说明不能继续写成 “still pending”，必须反映当前是否真的产出了 `table_mapping` | 任务书要求页级记录说明当前识别器和数字匹配策略，不能故意滞后于代码现状 |
| terminal 语义列的第一步不该先扩成新大表，而应先把 candidate `channel` 变成稳定合同，再让 PairBuilder 明确只消费 `terminal_numeric_channel` | 这能最小风险地把任务书 7.4 的“语义旁路”从隐式规则升级为可落盘运行态 |
| continuation 的第一步不该先扩大规则覆盖面，而应先把已识别出的 continuation 关系升级成显式 `pair_kind`，并让它稳定保留为 review 证据、旁路 ordinary audit | 这能最小风险地把任务书第 9 章“continuation 不能等价于 ordinary pair”落实到当前真实样本主链 |
| `audit_disposition` 的最小闭环应优先做成“分类输出 + pipeline 准入合同 + findings 落盘”，而不是先大改 `audit_role` 扫描策略 | 这能最小风险地补齐任务书第 4/5 层合同，同时避免和仍在演进的 continuation / semantic 语义切片互相缠绕 |
| 单侧 terminal half-pair 的下一刀应先落 pair 级 continuation，而不是先重构候选通道或直接发明 `bridge_mapping` | 这能复用现有 `pair_kind / ordinary_pair_eligible` 骨架，最小风险地把 `? -> 328`、`10 -> ?` 这类关系从普通 `R-PAIR-MISSING-SIDE` 中分流出去 |
| `bridge_mapping` 的第一刀应只覆盖端子页短桥接带里“双侧都来自 `n###` 派生文本且数值不同”的 cross-column relation | 这能把 `110 -> 330 / 109 -> 329` 这类任务书例子从 ordinary pair 中拆出，同时避免把正常端子行如 `21 -> 211` 一起误收 |
| `semantic_mapping` 的第一刀应只覆盖 terminal 页里“单侧 numeric relation + 同组存在真实语义 marker”的 relation | 这能把 `? -> 108` 与 `KLP/AC230V/I0'` 这类语义行从 continuation 中拆出，同时不误伤 `? -> 328` 或普通端子行 |
| `continuation_channel` 的第一刀只回标已在 pair 层识别成 `continuation` / `bridge_mapping` 的 selected numeric candidate | 这能最小风险地补齐任务书 7.4 的 candidate 四通道合同，同时不重写候选搜索、排序或 semantic mapping 边界 |
| semantic-specific 项目级规则的第一刀只做 `R-SEMANTIC-MAPPING-CONFLICT` | 这能直接消费现有 `semantic_mapping` pair 证据补上 terminal-to-semantic consistency，而不提前扩成更大的 semantic ledger |
| mixed-source 项目级规则的第一刀只做 `R-TABLE-MAPPING-SOURCE-CONFLICT` | 这能把第三类一致性从“table_mapping 进入通用 graph”升级成显式 source-aware contract，同时不先重写 `TableExtractor` 语义模型 |
| `texts / lines` 非回退量化应落在 `report/regression.py`，而不是继续塞进 acceptance evaluator | 这条指标比较的是 findings/audit 快照稳定性，不是人工标注 spec 命中率 |
| 页级 non-regression 比较必须优先使用 `filename + sheet_order` 这类稳定页键，而不是 `sheet_id` | fresh rerun 中 `sheet_id` 可能重编，直接按 `sheet_id` 比会把无回退误判成回退 |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `rg.exe` 无法在当前环境启动（拒绝访问） | 1 | 改用 PowerShell `Get-ChildItem` / `Get-Content` 继续检索 |
| `spawn_agent` 在 `fork_context=true` 时不能指定 `agent_type` | 1 | 改为无历史分叉的 explorer 子代理 |
| 子代理并发名额已满 | 1 | 复用现有子代理 `Parfit` 执行第二个只读审查任务 |
| `tauri build` 在 NSIS 资源下载阶段报 `timeout: global` | 1 | 先手动预热 NSIS 缓存，再重跑构建完成安装包产出 |

## Notes
- 本轮不要触碰其他 agent 正在改的文件内容；若发生重叠，先读清现状再合并。
- 每个阶段结束后回写 `progress.md`，关键发现回写 `doc/findings.md`。
- 当前桌面端下一优先级不再是“是否能原生构建”，因为 `cargo check` 与 `tauri build` 都已实跑通过。
- 当前主线程优先级已经重新收口到任务书主链；桌面端、preview、Tauri 打包都不再是主目标。
- 当前主线程应把更多注意力切回用户刚补充的 DWG 事实基线：第二套样本实跑、`DIM` 单字符候选降权、跨 inline 数字断线重连、页型策略收口。
- 第二套样本当前最适合作为后续整改验证的页面已经收敛为：
  - `08 测控1开入回路图1.dwg`
  - `12 测控2开入回路图1.dwg`
  - `21 左侧端子图1.dwg`
- 第二套当前实跑说明：`21-24` 端子页已经进入主链并产出大量 pair，但 `19-20` 元件接线图仍是 `0 line_groups / 0 pairs`，所以下一步不该只盯 `audit_role`，而要盯几何/候选层。
- 最新 scoped 实跑已把结论再推进一层：
  - `19 元件接线图1.dwg` 已从 `0 pair` 提升到 `39 pair / 12 issue`
  - `20 元件接线图2.dwg` 仍是 `0 pair`，下一步重点是竖线 / `top-bottom` 方向感知，而不是继续在 `INSERT` 展开层兜圈子
- `08/12` 上的 `inline_numeric_bridge_gap 13.0` 没有带来明显 issue 总量改善，后续更可能需要互补链级别的后处理，而不只是继续拧一个 gap 常数。
- 最新 `phase16_terminal_semantic_rows_{second,first}` 实跑已确认：
  - 第二套总体 issue `648 -> 697`，但构成从 `LOW-CONFIDENCE: 267 -> 203`、`MISSING-SIDE: 381 -> 494` 转移
  - 第一套总体 issue `518 -> 487`，同样表现为 `LOW-CONFIDENCE` 明显下降、`MISSING-SIDE` 显性化上升
  - 子代理只读复核认为这批被打掉的 `417->41`、`132->20`、`105->10`、`214->2` 更像语义行局部序号，而不是必须保留的 ordinary terminal pair
  - 所以下一步更适合做 continuation / semantic channel 的 specialized 解释，而不是立刻回滚这条候选层护栏
- 最新 `phase17_component_route_closure_{second,first}` 实跑已确认：
  - 第二套 `S0019/S0020` 已回到 `page_type=元件接线图`、`route_target=ComponentDiagramExtractor`
  - 第一套 `S0022/S0023/S0024` 已回到 `ComponentDiagramExtractor`，其中 `S0023` 不再是假 `TableExtractor`
  - 两套样本当前都没有稳定 `TableExtractor` 命中，`table_extraction_summary` 均为 `table_pages=0 / total_mappings=0`
  - 第二套总 issue 不变，第一套因 `S0023` 重新进入 component 审计链而 `487 -> 517`
- 最新 `phase7_vertical_component_second` 实跑已确认：
  - `20 元件接线图2.dwg` 进入 `55 line_groups / 55 pairs / 55 issues`，orientation 全为 `vertical`
  - `08 测控1开入回路图1.dwg` issue 总量 `96 -> 49`，其中 `47` 条变为“互补半链待复核”
  - `12 测控2开入回路图1.dwg` issue 总量 `89 -> 48`，其中 `41` 条变为“互补半链待复核”
- 最新 `phase8_vertical_dedupe_longline_second` 实跑已确认：
  - `20 元件接线图2.dwg` 从 `55 line_groups / 55 pairs / 55 issues` 进一步收敛到 `54 / 54 / 27`
  - 其中 `shared_text_anchor_reused` 拒收了 `54` 个复用候选
  - 长竖线离群 pair `1 -> 1` 已被移除，当前只剩 `27` 条 `1 -> 2` 的低置信 pair
- 最新 `phase8_component_suffix_scoped_second` 实跑已确认：
  - `19 元件接线图1.dwg` 的 `12` 条非 discard pair 完全不变
  - `20 元件接线图2.dwg` 的 `27` 条 review 中，有 `24` 条从泛化 `1 -> 2` 变成更具体的值，例如 `43 -> 419`、`53 -> 427`
  - `20` 仍剩 `3` 条 `1 -> 2`，对应当前没有长文本派生支持的端点
- 最新 `phase8_component_suffix_scoped_second_rerun` 再次确认：
  - 全量测试保持 `103 passed`
  - `20` 剩余 `3` 条泛化 pair 当前锁定在线组 `G0706 / G0712 / G0718`
  - 下一步应优先查 residual pattern，而不是扩大 suffix 规则作用域
- 当前最新本地提交：
  - `62c2dc3 Scope component suffix parsing to vertical pages`
  - `d5f79f4 Filter virtual component pins and expose line semantics`
- 最新 `phase9_virtual_pin_filter_hd_second` 实跑已确认：
  - 全量测试保持 `106 passed`
  - `20 元件接线图2.dwg` 从 `27` 条 non-discard 收敛到 `24`
  - `FJL` 虚拟块残余 `1 -> 2` 已完全消失
  - `HD6/HD5` 已进一步语义化为 `6 -> 504`、`5 -> 502`
- vertical 语义透传现状：
  - report markdown、Streamlit UI、desktop 结果页与 preview 已显式展示 `line_orientation / side labels`
  - 余下待收口的主要目标已经从“20 页 residual 噪声”切换到“页型边界与是否继续扩大补充页覆盖”
- 最新 `phase10_page_findings_second` 实跑已确认：
  - 第二套样本 `24` 页全部生成了 `page_findings`
  - `findings/page_findings/` 目录下共有 `24` 个 `.json` + `24` 个 `.md`
  - 当前页级产物已经能明确写出 `page_type / route_target / recognition_strategy / number_matching_strategy / open_questions`
- 当前任务书最明显的剩余结构性缺口已收敛为两条：
  - 真正的页级分类器 / 路由器 / `TableExtractor`
  - sidecar / desktop 的 `run_failed`、`purge-session` 暴露与报告下载闭环
- Batch 1 页级并发审图当前已收到的第一个结论：
  - `S0009` 不是纯表格页，而是“强网格化的开入回路二次原理图”
  - 这意味着下一步更像是给 `WireDiagramExtractor` 增加 `grid-aware / row-banded` 子模式，而不是粗暴切到 `TableExtractor`
- 子代理 `Pascal` 最新代码切片审查已确认：
  - `artifacts + sidecar/state_store + desktop types` 可以作为安全提交面
  - `domain/models.py + project_scanner.py + page_router.py + page_classifier.py + line_groups.py` 当前不应混提
- 最新 `phase12_horizontal_component_guard_second_v2` 真实样本已确认：
  - `S0019` 从 `grid:39` 回到 `horizontal:39`
  - `S0019` 的 39 条 pair 全部转为 discard，且理由已结构化为 `block_internal_pin_pair / self_pair_from_same_virtual_text`
  - `S0020` 维持 `vertical:54 / review:24 / discard:30`，未被误伤
- 最新 `phase13_terminal_strip_column_mode_second` 真实样本已确认：
  - `S0021` 从 `discard:108 / review:27` 变成 `discard:18 / review:117`
  - `ambiguous candidate ordering` 已基本退出主导，标准端子行开始稳定产出 `21 -> 211`、`69 -> 318` 这类 review pair
  - `S0021` 当前 issue 分布变成 `R-PAIR-LOW-CONFIDENCE: 90`、`R-PAIR-MISSING-SIDE: 27`、`R-DUPLICATE-SAME-LINE: 9`
  - 第二套总体 issue `398 -> 597` 是可解释的显性化副作用：原先被 discard 吞掉的标准端子行现在进入 review 主链
  - 第一套 `phase13_terminal_strip_column_mode_first` 总 issue 为 `446`，较 Phase 11 的 `461` 未回退
  - 端子页剩余最明显缺口已收敛为：
    - `23 右侧端子图1.dwg` 仍是 `discard:130`
    - `24 右侧端子图2.dwg` 仍是 `review:55 / discard:37`
    - `21` 的 `310-385` 短桥接列带与 `DK/KLP/ZKK` 语义区仍需专用策略
- 最新 `phase14_right_terminal_mirror_second` 真实样本已确认：
  - `S0023` 从 `discard:130` 变成 `review:114 / discard:16`
  - `S0024` 从“左右两侧常选到同一文本”收口为 `review:54 / discard:38`，开始稳定产出 `421 -> 45`、`417 -> 41` 这类 mirrored pair
  - 第二套总体 issue `597 -> 654`，主要新增为 `S0023/S0024` 被显性化后的 `R-PAIR-LOW-CONFIDENCE`
  - 第一套总体 issue `446 -> 559`，同样是右侧端子页从大量 discard 翻到 review 的显性化副作用，不应当被当作简单回退
- 这轮之后端子图方向的下一步已更清晰地收敛到：
    - `310-385` 短桥接列带单独列角色解释
    - `DK/KLP/ZKK` / `CLP` 等语义列是否进入 pair 或改走语义通道
    - 端子页 review pair 的提置信与去重，而不是继续放宽召回
- 最新 `phase35_regression_with_extraction_second` 已确认：
  - `compare-regression` 现在会同时输出：
    - `extraction_counts.pages/texts/numeric_texts/lines/line_groups`
    - `non_regression_checks.texts`
    - `non_regression_checks.lines`
  - second-set current-head 基线对比 `phase31 -> phase33` 结果为：
    - `pair_count delta = 0`
    - `issue_count delta = 0`
    - `texts delta = 0`
    - `lines delta = 0`
    - `line_groups delta = 0`
    - `numeric_texts delta = 0`
    - `texts status = ok`
    - `lines status = ok`
  - 额外容错已补：
    - `sheet_order` 非数值时回退到 `filename` 页键，不会在 markdown/json report 生成时崩溃
- 最新 `phase15_terminal_short_bridge_{second,first}` 真实样本已确认：
  - 第二套总体 issue `654 -> 648`
  - 第一套总体 issue `559 -> 518`
  - `S0021` 的短桥接带从 `110 -> 110 / 328 -> 328` 收口为：
    - `110 -> 330`
    - `109 -> 329`
    - `? -> 328..322`
  - `S0024` 的短桥接带从 `10 -> 10 .. 1 -> 1` 收口为整列 `missing left candidate`
  - `S0027` 的大量“单根延续列 + 局部序号列”也转成了单侧 continuation，但双延续列同值 `420 -> 420 / 110 -> 110` 仍存在
  - 所以下一步应优先处理：
    - 端子页语义列旁路 / 语义通道
    - 双延续列同值 continuation 的 specialized pair 语义
    - review pair 的提置信，而不是再放宽普通候选窗口
