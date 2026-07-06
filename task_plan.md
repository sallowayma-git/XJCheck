# Task Plan: XJToolkit DWG Audit MVP Closure

## Goal
重新对齐并完成 [doc/任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 定义的 DWG 审计 MVP 主链：输入项目级 DWG，生成结构化 findings 运行态，先做页级分类，再按图种路由到对应识别器，产出 pair / table mapping / evidence，运行项目级规则引擎，并输出可复核异常报告。

## Current Phase
Phase 57

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

### Phase 31: Page Classification Findings Contract
- [x] 重新按 current-head 任务书审计 `page classifier / router / table extractor` 证据，确认最近核心切片是“把页级分类/路由变成 findings 一等落盘状态”
- [x] 在 `SheetRecord/pages.parquet` 中显式持久化 `page_type / page_subtype / table_like / grid_heavy`
- [x] 把页级 `recognition_strategy` 改成反映真实的 `PageClassifier -> Page Router` 几何分类证据，而不是旧的 filename/.prj 启发式叙述
- [x] 复跑 targeted pytest、full pytest，以及 second-set current-head `analyze-project + run-audit`
- [x] 把任务书完成度审计与本轮裁决回写 `doc/findings.md` / `progress.md`，并准备本地提交
- **Status:** complete

### Phase 32: Table Real-No-Hit Findings Contract
- [x] 重新按 current-head 任务书审计，确认最近核心切片已收口到“把真实样本暂无 table hit 变成显式 findings 合同”
- [x] 在 `table_extraction_summary` 中显式持久化 `status / status_reason / classified_table_pages / classified_table_filenames / table_like_non_routed_pages`
- [x] 把 `findings.md` 项目级摘要补上 `## Table Extraction`，不再要求人工从 `table_pages=0` 反推结论
- [x] 核对 first/second fresh rerun，确认两套样本都显式输出 `no_table_pages_detected`，并记录第一套 `S0023` 的 table-like 非路由边界
- [x] 复跑 targeted pytest、full pytest，并把结果回写 `doc/findings.md` / `progress.md`
- **Status:** complete

### Phase 33: Issue Top-Level Review Contract
- [x] 重新按 current-head 任务书审计，确认最近核心切片已从 table real-no-hit 推进到 `issues.json` 顶层可复核字段合同
- [x] 在 `Issue` / `IssueFactory` / audit 导出链中显式持久化 `filename / sheet_no / sheet_order / rationale`
- [x] 保持 `evidence / evidence_refs` 作为明细层，同时让导出阶段对旧 issue 做字段回填
- [x] 复跑 targeted pytest、full pytest，以及两套真实样本 fresh `analyze-project + run-audit`
- [x] 把任务书完成度审计与本轮裁决回写 `doc/findings.md` / `progress.md`，并准备本地提交
- **Status:** complete

### Phase 34: Route-Specific Extractor Entry Proof
- [x] 重新按 current-head 任务书与 fresh real-sample 证据审计，确认最近核心切片已推进到“Wire / Component / Terminal 不能只共享一条 pairing 大链”
- [x] 把 `WireDiagramExtractor / ComponentDiagramExtractor / TerminalDiagramExtractor` 落成真实可执行的独立入口，并保留显式 supplemental `LayoutOnly` 审计兜底
- [x] 让 findings 运行态显式记录 `executed_extractor / extractor_execution_summary`
- [x] 复跑 targeted pytest、full pytest，以及两套真实样本 fresh `analyze-project + run-audit`
- [x] 把“入口分流已可证明且行为未漂移”的结论回写 `doc/findings.md` / `progress.md`，并准备本地提交
- **Status:** complete

### Phase 35: Full Route Execution Contract
- [x] 重新按 current-head 任务书审计，确认最近核心切片已从“pairing extractor 入口可证明”推进到“Table / LayoutOnly / Skip 也需要同层级执行或明确未执行证据”
- [x] 在 findings 合同层补齐所有 route target 的 `status / status_reason / routed_page_count / executed_page_count`
- [x] 给页级 findings 补 `execution_status`，显式区分 `executed / classify_only / skipped`
- [x] 复跑 targeted pytest、full pytest，以及两套真实样本 fresh `analyze-project + run-audit`
- [x] 把“全 route matrix 证据已显式落盘且行为未漂移”的结论回写 `doc/findings.md` / `progress.md`，并准备本地提交
- **Status:** complete

### Phase 36: MVP Acceptance Suite Proof
- [x] 重新按 current-head 任务书第 19 节审计，确认最近核心切片已收口到“真实正确样本 + 故障注入样本”的最小验收 suite proof
- [x] 在 `report/acceptance.py` 增加 suite evaluator / writer，并让结果可落盘为 json / markdown
- [x] 新增内部命令 `evaluate-acceptance-suite`，仅服务验收 harness，不扩成产品主界面
- [x] 固化 `mvp_minimum_suite.json`，把 fault-injected case 与 second-set real subsets 绑定为同一套 required suite
- [x] 复跑 targeted pytest、full pytest，并核对 current-head suite 产物通过
- [x] 把“internal harness only，下一步转向 exe 可调用单一执行入口”的裁决回写 `doc/findings.md` / `progress.md`
- **Status:** complete

### Phase 37: Single Execution Entry Audit
- [x] 重新按用户最新边界审计 `analyze-project / analyze-session / ui.actions.run_ui_analysis` 的共同执行链
- [x] 确认哪些逻辑已经共享在 `pipeline.analyze_input_root`，哪些仍散落在 CLI / sidecar / UI 包装层
- [x] 抽出 `run_analysis_workflow()`，把分析 + 可选审计主链收敛成 exe 可调用的 service entry
- [x] 让 CLI / Streamlit UI / desktop sidecar 复用同一 service entry，并保留 `project_artifacts_ready` 事件时机
- [x] 复跑 targeted pytest、full pytest，以及第二套真实样本 `analyze-session`
- **Status:** complete

### Phase 38: Backplate Virtual Table Closure
- [x] 用 fresh phase44 产物审计任务书新增的 `20 非电量保护背板图.dwg` 背板表格型缺口
- [x] 允许背板接线图展开必要 `INSERT.virtual_entities()`，让块内表头/行号进入抽取层
- [x] 在 PageClassifier 中把“背板 + 块内表头/行号 + 外部端点”升级为 `背板表格型图 / TableExtractor`
- [x] 在 TableExtractor 中新增 `backplate_virtual_table` 映射，输出 `NKR308A-1 -> 5FD15` 类高置信 `table_mapping`
- [x] 补 unit + integration 测试，并跑两套真实样本 smoke
- **Status:** complete

### Phase 39: Component-Prefixed Signal Circuit
- [x] 针对 `16 高低压侧操作箱信号回路.dwg` 识别 `component_prefixed_signal_circuit` 子模式
- [x] 识别左右元件分区顶部前缀 `1-2n` / `3-2n`
- [x] 将分区内局部数字合成为 `1-2n218` / `3-2n218`，再与同线外侧端子生成结构化映射
- [x] 补窄单测、集成测试和第一套真实样本验证
- **Status:** complete

### Phase 40: Inline Component Port Circuit
- [ ] 针对任务书中的线中元件端口型回路，识别嵌在线中的元件本体编号与端口 `1/2`
- [ ] 输出 `3-2KLP1-1 -> 3-2QD2`、`3-2KLP1-2 -> 3-2n116` 类结构化 `wire_component_mapping`
- [ ] 确认局部端口序号不再作为裸普通端子进入跨页审计
- [ ] 补窄单测、集成测试和真实样本验证
- **Status:** pending

### Phase 41: Issue Root-Cause Diagnostics
- [x] 按用户闭环把 `issue_count` 视为症状集合，建立 root_cause 临时归因分类
- [x] 新增 post-audit service 层能力，给 `issues.parquet/json` 补 `root_cause / diagnostic_context` 并输出聚合报告
- [x] 在第一套、第二套真实样本上只基于现有 findings 重跑 audit，确认归因产物可用
- [x] 用归因结果反推下一刀应优先看 `pairing_wrong` 的 inline wire split 与 component extractor missing，而不是盲目降噪
- **Status:** complete

## Key Questions
1. 线中元件端口型回路是否和 `component_prefixed_signal_circuit` 共用 `wire_component_mapping` pair_kind？
2. 线中元件端口型的元件 bbox 应优先从块/符号边界、端口号位置还是连接线断点推断？
3. 背板表格型页与组件前缀回路已进入结构化 pair 后，RuleEngine 是否需要按 pair_kind 进一步区分普通跨页冲突与结构化信源冲突？

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
| 页级分类/路由的 MVP 合同不能只停留在 `findings.json.page_findings` 里；`pages.parquet` 也应显式携带 `page_type / page_subtype / route_target / audit_disposition` | `pages.parquet` 是默认 findings SSoT 的主表之一，若它缺少 `page_type`，任务书中的“先分类再路由”只能通过聚合 JSON 间接证明 |
| 页级 `recognition_strategy` 不能继续写成“来自 filename/.prj/title keywords”，必须反映真实 `PageClassifier -> Page Router` 证据 | 否则 current-head 明明已由几何分类驱动路由，页级解释文案却仍在削弱甚至误述主链闭环程度 |
| 当真实样本当前 `table_pages=0` 时，`findings` 必须显式输出 `no_table_pages_detected`，不能要求人工从计数为零自行反推 | 任务书允许真实样本暂无 table hit，但前提是 current-head 要把“暂无命中”写成正式合同 |
| `table_like_geometry` 与最终 `route_target` 不应被混为一谈 | 第一套 `S0023` 已证明某些 component 页可以几何上偏 table-heavy，但语义上仍应走 `ComponentDiagramExtractor` |
| 当 `issues.json` 已经拥有复核证据时，最短主链切片不是“再去降 issue 数”，而是把 `filename / sheet_no / rationale` 提升成顶层稳定字段 | 任务书成功定义要求 run-audit 输出可直接复核；当前缺口在输出合同而不在规则数量 |
| per-type extractor 的最小闭环不需要立刻重写三套完全不同的大算法，但必须有真实不同的执行入口、可测试调用证据，以及 fresh real-sample 的执行摘要 | 这能最小风险地满足“不能继续依赖一条共享大脚本解释所有页型”的任务书要求 |
| 当 `Wire / Component / Terminal` 已有执行证据后，下一条更近的主链切片不是回到几何调参，而是把 `Table / LayoutOnly / Skip` 的执行或明确未执行状态补到同层级合同 | 否则 route matrix 仍只对三类 audited pair page 强，而对“表格暂无命中”“背板 classify_only”“封面 skip”还停留在间接说明 |
| `evaluate-acceptance-suite` 只允许作为内部验收 harness 存在，不构成继续扩产品 CLI 的方向许可 | 用户已明确要求产品主链转向 exe 可调用的单一执行入口，CLI 只保留调试/自动化/验收用途 |
| 第一层 exe 可调用入口应抽成 `run_analysis_workflow()`，而不是先大改 desktop sidecar | 这能让 CLI / UI / sidecar 立刻共享分析 + 可选审计主链，并把更复杂的状态落库与预览职责留给下一轮 session service |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `rg.exe` 无法在当前环境启动（拒绝访问） | 1 | 改用 PowerShell `Get-ChildItem` / `Get-Content` 继续检索 |
| `spawn_agent` 在 `fork_context=true` 时不能指定 `agent_type` | 1 | 改为无历史分叉的 explorer 子代理 |
| 子代理并发名额已满 | 1 | 复用现有子代理 `Parfit` 执行第二个只读审查任务 |
| `tauri build` 在 NSIS 资源下载阶段报 `timeout: global` | 1 | 先手动预热 NSIS 缓存，再重跑构建完成安装包产出 |
| 本轮尝试再拉一个只读 explorer 时命中 agent thread limit | 1 | 停止等待子代理，改为主线程本地直接核对 phase37 rerun 的 `findings.json` 关键字段 |
| `test_rerun_audit.py` 仍按旧 `issues.json` 形状断言导致 full pytest 失败 | 1 | 同步把 expected JSON 更新为包含新的顶层 `filename / sheet_no / sheet_order / rationale` 字段 |
| route-specific extractor 首版 fresh rerun 导致两套真实样本 issue 总量异常上升（second `519 -> 606`，first `345 -> 374`） | 1 | 先比对 rule 分布，定位为分路后 `line_group / candidate / pair` 编号在各子链内重新从 1 开始，触发项目内 ID 碰撞；给 `build_line_groups / build_terminal_candidates / build_pairs` 增加可注入 `IdFactory` 后恢复稳定基线 |
| 第一次 `analyze-session` 真实验证使用相对 `.tmp\phase43_service_session` 路径后，后续核对落点出现歧义 | 1 | 改用预创建的绝对路径 `.tmp\phase43_service_session_abs` 重跑，确认 workspace、state db 和 session 产物都稳定落盘 |

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
- 最新 `phase36_page_contract_second` 已确认：
  - second-set fresh `analyze-project + run-audit` 保持 `issue_count = 519`
  - `pages.parquet` 现在已显式带：
    - `page_type`
    - `page_subtype`
    - `page_type_confidence`
    - `table_like`
    - `grid_heavy`
    - `route_target`
    - `audit_disposition`
  - 代表页 current-head 结果为：
    - `04 交流回路图1.dwg -> 二次原理图 / grid_heavy_wire_diagram / WireDiagramExtractor`
    - `17 测控1装置背板.dwg -> 背板接线图 / LayoutOnlyExtractor`
    - `19 元件接线图1.dwg -> 元件接线图 / horizontal_component / ComponentDiagramExtractor`
    - `21 左侧端子图1.dwg -> 屏端子图 / TerminalDiagramExtractor`
  - `findings.json.page_findings[].recognition_strategy` 也已改成显式引用：
    - `PageClassifier labeled this page as ...`
    - `Page Router sent it to ...`
  - `table_extraction_summary` 仍保持：
    - `table_pages = 0`
    - `three_column_pages = 0`
    - `total_mappings = 0`
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

### Phase 42: Terminal Header Table Supplemental Mapping Closure
- [x] 实现目标：把端子图中“表头前缀 + 行号 + 同行端子端点”的 supplemental table mapping 收口为 `terminal_header_table`，让端子页在保留 `TerminalDiagramExtractor` 主路由的同时补出稳定 `table_mapping` pass pair。
- [x] 关键文件：
  - `src/dwg_audit/audit/table_extractor.py`
  - `src/dwg_audit/audit/page_extractors.py`
  - `src/dwg_audit/pipeline.py`
  - `tests/unit/test_table_extractor.py`
  - `tests/integration/test_analyze_project.py`
- [x] 验证命令与结果：
  - targeted pytest terminal-header/table-mapping slice -> `8 passed`
  - `python -m pytest -q` -> `189 passed`
  - second-set fresh `analyze-project + run-audit` evidence: `.tmp/phase49_terminal_header_gate_second/2_2` 产出 `176` 条 `terminal_header_table` 映射，覆盖 `S0021-S0024`，目标 `1-21QD1 -> 1-21n116` 仍为 `pass/confidence=0.95/table_mapping`，audit `issue_count=588`
  - first-set non-regression evidence: `.tmp/phase49_terminal_header_gate_first/...` 保留背板表格映射，`NKR308A-1 -> 5FD15` 仍为 `backplate_virtual_table/pass/confidence=0.95`
  - added terminal-header group structure gate and sparse header-like negative test to avoid promoting isolated terminal text into table mappings
- [ ] 下一刀建议：优先二选一切小片，不独占代码库：
  - line-in KLP port：补 `3-2KLP1-1 -> 3-2QD2` 这类 line-in component port 映射
  - component diagram mapping：继续收口元件接线图的结构化 component mapping

### Phase 43: Line-In KLP Component Port Mapping
- [x] 实现目标：在普通二次原理图中识别线中 `KLP` 本体、端口 `1/2`、左右外部端点，并追加 `wire_component_mapping` pass pair。
- [x] 风险门槛：不放开普通单字符端口候选；`inline_klp_component_port_mapping` 必须有左右水平线证据，裸三位数只在该线证据场景下按 KLP 前缀归一化为 `n###`。
- [x] 验证命令与结果：
  - `python -m pytest -q tests\unit\test_wire_components.py` -> `4 passed`
  - targeted integration slice -> `2 passed`
  - `python -m pytest -q` -> `193 passed`
  - first-set fresh `analyze-project + run-audit`: `.tmp/phase52_inline_klp_line_gated_first/...` 产出 `6` 条 `inline_klp_component_port_mapping`，其中四个目标 `1KLP1-1 -> 1QD2`、`1KLP1-2 -> 1n116`、`3-2KLP1-1 -> 3-2QD2`、`3-2KLP1-2 -> 3-2n116` 均为 `pass/confidence=0.95`
  - second-set fresh `analyze-project`: `.tmp/phase52_inline_klp_line_gated_second/2_2` 中 `inline_klp=0`，未在第二套误触发
- [ ] 下一刀建议：继续收口 `ComponentDiagramExtractor` 的元件接线图结构化 `component_mapping`，或处理 `R-ONE-TO-MANY` 对结构化表格/组件映射的规则语义。

### Phase 44: Table Mapping Relationship Contract
- [x] 任务书审计：重新按 `doc/任务书.md` 拆出 MVP 主链要求，并写入 `doc/findings.md` section 95。
- [x] 实现目标：把表格映射从“`ordinary_pair` + `evidence.source=table_mapping`”修正为显式 `pair_kind=table_mapping`。
- [x] 规则层同步：`_high_confidence_pairs()` 允许 `table_mapping` 在不冒充 ordinary pair 的前提下继续参与跨页冲突和 mixed-source 规则。
- [x] 验证命令与结果：
  - targeted table/rules tests -> `13 passed`
  - targeted analyze-project table tests -> `5 passed`
  - `python -m pytest -q` -> `193 passed`
  - first-set fresh `analyze-project + run-audit`: `.tmp/phase53_table_pair_kind_first/...` 产出 `pair_kind.table_mapping=144`，`NKR308A-1 -> 5FD15` 保持 `pass/confidence=0.95`
  - second-set fresh `analyze-project + run-audit`: `.tmp/phase53_table_pair_kind_second/2_2` 产出 `pair_kind.table_mapping=176`，`1-21QD1 -> 1-21n116` 保持 `pass/confidence=0.95`
- [ ] 下一刀建议：进入 `ComponentDiagramExtractor` 专用 `component_mapping`，优先 first `S0022/S0024` 或 second `S0019/S0020`。

### Phase 45: Strip Two-Port Component Mapping
- [x] 实现目标：在 `ComponentDiagramExtractor` 中为长条双端口元件接线图产出首个专用 `component_mapping`，覆盖 first `S0024 / 23 元件接线图3.dwg` 的 `5KLP10-1 -> 5KLP9-1` 与 `5KLP10-2 -> 5n112`。
- [x] 风险门槛：仅限 `元件接线图 / horizontal_component / ComponentDiagramExtractor`；仅使用 `FJL-25-2A_Mirror` 块内端口 `1/2`；必须有同列 KLP 本体、上下合法外部端点和支撑竖线；逗号端点、纯数字端点和 partial mapping 不 consume 普通 pair。
- [x] 规则层同步：`component_mapping` 可作为高置信图信源参与 cross-page / one-to-many / many-to-one / duplicate 等图规则；不放宽 `_ordinary_pair_eligible()`，也不为 component mapping 开置信度 bypass。
- [x] 验证命令与结果：
  - targeted component/rules tests -> `8 passed`
  - `python -m pytest -q` -> `201 passed`
  - first-set fresh `analyze-project + run-audit`: `.tmp/phase56_strip_component_safe_first/...` 产出 `component_mapping=10`，目标 `5KLP10-1 -> 5KLP9-1`、`5KLP10-2 -> 5n112` 均为 `pass/confidence=0.95/pair_kind=component_mapping`，逗号端点 component mapping = `0`，audit `issue_count=385`
  - second-set fresh `analyze-project + run-audit`: `.tmp/phase56_strip_component_safe_second/2_2` 产出 `component_mapping=8`，逗号端点 component mapping = `0`，audit `issue_count=584`
- [ ] 下一刀建议：继续 `ComponentDiagramExtractor` 的 `4输出/6输出` 组件实例抽取，或补 first `S0019/S0020` 背板几何表格的静默空结果。

### Phase 46: Backplate Geometric Table Endpoint Recovery
- [x] 实现目标：补齐 first `S0019/S0020` 已路由到 `TableExtractor` 但 `table_mapping=0` 的背板几何表格空结果。
- [x] 风险门槛：只扩展 `TableExtractor` 背板端点识别，不扩大 `PageClassifier` 路由；同一背板 header 至少 3 个端点命中才产出高置信 `table_mapping`。
- [x] 验证命令与结果：
  - targeted backplate tests -> `5 passed`
  - `python -m pytest -q` -> `203 passed`
  - first-set fresh `analyze-project + run-audit`: `.tmp/phase58_backplate_route_stable_first/...` 产出背板 `table_mapping`：`S0018=27`、`S0019=72`、`S0020=67`、`S0021=56`，代表关系 `NDY306A-3 -> 1-2QD1`、`NCZ343A-2 -> 1-4QD17`、`NDY306A-3 -> 3-2QD1`、`NCZ343A-2 -> 3-4QD17` 均命中
  - second-set fresh `analyze-project + run-audit`: `.tmp/phase58_backplate_route_stable_second/2_2` 中 `S0017/S0018` 普通装置背板保持 `LayoutOnlyExtractor / classify_only`，背板 table mappings `0`，`LAN*` table mappings `0`
- [ ] 下一刀建议：实现 `KK2P/KK3P` 多端口 `component_mapping`，需要把 `BlockRecord` 传入 `ComponentDiagramExtractor`，代表目标 first `S0022: 1DK-1 -> ZD9`、second `S0019: 1-21ZKK-2 -> 1-21n715`。

### Phase 47: KK Multi-Port Component Mapping
- [x] 实现目标：为 `ComponentDiagramExtractor` 增加 `KK2P/KK3P` 多端口组件映射，覆盖元件接线图 `4输出/6输出` 最小真实样本。
- [x] 并发分工：
  - worker `James` 负责 `component_diagrams.py` 与 `test_component_diagrams.py` 的核心抽取和单测。
  - worker `Lagrange` 负责 `pipeline.py` / `page_extractors.py` 的 `blocks` 传递与必要集成验证。
- [x] 风险门槛：不启用 `KK1P`，不强配缺目标端口，不扩大端子/普通回路逻辑，保留 strip two-port 行为不回退。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_component_diagrams.py` -> `10 passed`
  - `python -m pytest -q` -> `208 passed`
  - first-set fresh `analyze-project + run-audit`: `.tmp/phase60_kk_multi_port_dedup_first/...` 中 `21 元件接线图1.dwg` 新增 `17` 条 `kk_multi_port_component`，全项目 `component_mapping=27`，重复端点检查 `0`
  - second-set fresh `analyze-project + run-audit`: `.tmp/phase60_kk_multi_port_dedup_second/2_2` 中 `19 元件接线图1.dwg` 新增 `12` 条 `kk_multi_port_component`，全项目 `component_mapping=20`，重复端点检查 `0`
- [ ] 下一刀建议：继续补 `strip_two_port_component` 逗号外部端拆分，或进入端子图列角色/continuation 语义复核。

### Phase 48: Terminal Structured Endpoint Ordinary Bypass
- [x] 重新按任务书审计当前 phase60 主链，确认页级分类/路由/Table/Component 已有强证据，但端子页仍有被结构化表格映射覆盖的裸 suffix ordinary review。
- [x] 用两个只读子代理复核：
  - terminal/continuation 复核指出端子页仍有大量 `3-21n211 -> 211` 派生 suffix ordinary review。
  - route/table 复核确认 PageClassifier/Page Router/TableExtractor 主链已有强证据，下一刀应只做残留 ordinary 降级，不扩大路由。
- [x] 实现目标：端子页中已被 `terminal_header_table` 覆盖的完整端子文本，不再降级成裸数字 `ordinary_pair` review。
- [x] 风险门槛：没有表头结构覆盖证据的 row-lock synthetic 仍保持 review；不改候选阈值、不改 UI、不改 component/table mapping 数量。
- [x] 验证结果：
  - `python -m pytest -q` -> `211 passed`
  - first-set fresh `analyze-project + run-audit`: `.tmp/phase62_terminal_structured_cover_first/...`，terminal ordinary review `104 -> 85`，结构化映射不回退
  - second-set fresh `analyze-project + run-audit`: `.tmp/phase62_terminal_structured_cover_second/2_2`，terminal ordinary review `200 -> 87`，结构化映射不回退
- [ ] 下一刀建议：继续 terminal 剩余普通行列角色收敛，或补 `strip_two_port_component` 逗号端点拆分；二者都必须先有任务书审计证据再动手。

### Phase 49: Taskbook Re-Audit And Next Narrow Slice
- [x] 执行 planning catchup，并确认并发外部改动只限 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`
- [x] 启动两个只读子代理并发审计：MVP/验收边界与 Phase62 剩余缺口横向复核
- [x] 汇总子代理结论，选择一个不扩大 CLI / UI 的最小开发切片
- [x] 派 worker 负责 disjoint 写集，主线程只做集成审查、验证与提交
- [x] 完成 `strip_two_port_component` 逗号端点拆分，并在 first/second 真实样本上验证
- **Status:** complete

### Phase 50: Acceptance Redline Or Rule Semantics Follow-up
- [x] 重新审计 `mvp_minimum_suite` 与当前结构化关系口径，决定是刷新 golden 还是修正实现
- [x] 固定 fault-injected artifacts / alias，使 acceptance suite 可在本地稳定复跑
- [x] 用临时 `.tmp` artifact 证明完整 internal suite `3/3` 可达
- [x] 提炼 `acceptance_mini` 测试生成 helper 到 `tests/support`，不提交 `.tmp` 运行产物
- [x] 审计新增 `component_mapping` 后暴露的 many-to-one / branch issue，避免证据不足项继续作为 hard error
- [x] 为同页 `strip_two_port_component` 分支 / 多入口关系补充 `component_branch_review` 规则语义
- [x] 扩展 internal acceptance harness，使真实样本 golden 支持 `pair_kind/status/pair_key`
- **Status:** complete

### Phase 51: Desktop Exe Workflow Closure
- [x] 重新审计 exe 工作流是否仍依赖手工 CLI / 源码路径 / 本机 Python 环境
- [x] 明确 sidecar 打包或 runtime 复用策略，不继续扩产品 CLI
- [ ] 用最小端到端证据证明导入项目、启动分析、查看报告的 exe 主链
- **Status:** in_progress

#### Phase 51 Runtime Resolver Slice
- [x] 审计确认旧 Tauri bridge 固定执行 `python -m dwg_audit.cli`，并用编译时 `CARGO_MANIFEST_DIR/../../..` 找源码根；这只能证明开发态，不能证明安装后的 exe 无源码依赖。
- [x] 新增 `sidecar_runtime` resolver：优先 `DWG_AUDIT_SIDECAR_EXE`，其次 Tauri resource dir 下的 `dwg-audit-sidecar(.exe)`，最后才是开发源码 Python fallback。
- [x] release 策略收口：release 运行态不再隐式回退源码路径；只有 debug build 或显式 `DWG_AUDIT_ALLOW_SOURCE_FALLBACK=1` 才允许源码 fallback。
- [x] Tauri command bridge 继续调用同一组内部 sidecar/CLI 子命令，但产品面不新增 CLI；桌面 README 已记录 runtime contract。
- [x] 验证结果：
  - `npm run build` -> passed
  - `cargo test --manifest-path apps\desktop\src-tauri\Cargo.toml` -> `5 passed`
  - `cargo test --release --manifest-path apps\desktop\src-tauri\Cargo.toml` -> `5 passed`
  - `python -m pytest -q tests\unit\test_sidecar.py tests\unit\test_execution_service.py` -> `7 passed`
  - `python -m pytest -q` -> `217 passed`
  - `npm run tauri:build` -> produced `apps/desktop/src-tauri/target/release/bundle/nsis/DWG Audit Desktop_0.1.0_x64-setup.exe`
- [ ] 下一刀建议：产出并打包真实 `dwg-audit-sidecar` 可执行文件，然后用安装后的 exe 跑一次导入项目、启动分析、加载报告的桌面主链证据。

### Phase 52: Input Matrix Wire Mapping Closure
- [x] 恢复上下文并确认并发外部改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`。
- [x] 实现目标：在 `WireDiagramExtractor` 中识别开入矩阵的 `21QD` 行端点、`21n` 列前缀和三位局部号，产出显式 `wire_component_mapping/pass`。
- [x] 语义收口：被 `input_matrix_wire_mapping` 覆盖的局部号 ordinary 半边只降级为 `discard`，不删除结构化关系、不扩 CLI、不隐藏 issue graph。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_wire_components.py` -> `6 passed`
  - `python -m pytest -q tests\unit\test_page_extractors.py` -> `5 passed`
  - targeted integration slice -> `2 passed`
  - `python -m pytest -q` -> `221 passed`
  - second-set fresh `analyze-project + run-audit`: `.tmp/phase66_input_matrix_cover_second/2_2` 中 `wire_component_mapping=168`，`input_matrix` 覆盖 ordinary discard `336`，`issue_count=303`
  - second-set 目标命中：`S0008` 的 `1-21QD12 -> 1-21n127`、`1-21QD28 -> 1-21n212`、`1-21QD44 -> 1-21n228`；`S0012` 的 `3-21QD6 -> 3-21n127`、`3-21QD22 -> 3-21n212`、`3-21QD38 -> 3-21n228`
  - first-set fresh non-regression: `.tmp/phase66_input_matrix_cover_first/...` 中 `input_matrix_wire_mapping=0`、`covered_input_matrix_ordinary=0`、`issue_count=458`
- [ ] 下一刀建议：回到 Phase51 packaged sidecar/exe smoke，或继续按任务书审计 `small_port_box_component` / 输出几何 mismatch；二者都先做只读审计。
- **Status:** complete

### Phase 53: Small Port Box Component Mapping
- [x] 只读恢复并确认当前外部/并发改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`。
- [x] 并发审计确认 `small_port_box_component` 是任务书点名且当前未闭合的 ComponentDiagramExtractor 子模式；同时记录 `4输出/6输出` 端口绑定偏差留作下一刀。
- [x] 实现目标：在 `ComponentDiagramExtractor` 中识别 `AK/A'/KZKK/JR` 小型端口盒，输出 `component_mapping/pass`。
- [x] 风险门槛：只接受元件接线图路由下的 `KK1P/KK2P/JR-01` 小盒块、纯字母本体、块内完整端口集合，以及端口上下邻近外部端；不改普通候选、rules、TableExtractor 或 WireDiagramExtractor。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_component_diagrams.py` -> `16 passed`
  - targeted integration component slice -> `9 passed, 11 deselected`
  - `python -m pytest -q` -> `225 passed`
  - first-set fresh `.tmp/phase67_small_port_first_v2/...`: `pair_count=1533`, `issue_count=458`, `component_mapping=85`, `small_port_box_component=10`
  - second-set fresh `.tmp/phase67_small_port_second/2_2`: `pair_count=1585`, `issue_count=303`, `component_mapping=30`, `small_port_box_component=10`
  - 目标命中：`AK-1 -> JD1`、`AK-2 -> A'-1`、`A'-1 -> AK-2`、`A'-2 -> JD6`、`KZKK-1 -> JD8`、`KZKK-2 -> K-5`、`KZKK-3 -> JD3`、`KZKK-4 -> K-6`、`JR-1 -> K-3`、`JR-2 -> K-4`
- [ ] 下一刀建议：优先修正 `4输出/6输出` 的 KK2P/KK3P 端口几何绑定偏差，尤其 `5DK-2/4` 与 `1-2ZKK-2/4/6` 的真实人工标注口径。
- **Status:** complete

### Phase 54: KK Output Slot Geometry Binding
- [x] 只读恢复并确认当前外部/并发改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`。
- [x] 两个只读 explorer 复核确认 `4输出/6输出` 偏差来自 KK2P/KK3P 固定槽位未建模，而不是 rules 或报告层问题。
- [x] 实现目标：把 `kk_multi_port_component` 从“端口文字最近水平线远端”改为“固定 2x2 / 3x2 槽位 + 同列上/下外部端点”绑定。
- [x] 风险门槛：只改 `ComponentDiagramExtractor` 的 KK2P/KK3P 多端口子模式；不启用 KK1P、不改普通候选、不改 rules、不隐藏 component_mapping issue。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_component_diagrams.py -k "kk_multi_port"` -> `5 passed`
  - `python -m pytest -q tests\unit\test_component_diagrams.py` -> `16 passed`
  - `python -m pytest -q tests\unit\test_wire_components.py -k "input_matrix"` -> `2 passed, 4 deselected`
  - targeted integration component slice -> `9 passed, 11 deselected`
  - `python -m pytest -q` -> `225 passed`
  - first-set fresh `.tmp/phase68_kk_slot_first/...`: `pair_count=1552`, `issue_count=458`, `component_mapping=104`, `kk_multi_port_component=36`
  - first `S0022` 目标全命中：`5DK-1 -> ZD12`、`5DK-2 -> 5FD25`、`5DK-3 -> ZD4`、`5DK-4 -> 5FD1`、`1-2ZKK-1 -> 1-2UD1`、`1-2ZKK-2 -> 1-2n719`、`1-2ZKK-3 -> 1-2UD3`、`1-2ZKK-4 -> 1-2n720`、`1-2ZKK-5 -> 1-2UD5`、`1-2ZKK-6 -> 1-2n721`
  - first 旧错配 `5DK-2 -> 5FD1`、`5DK-4 -> 5FD25`、`1-2ZKK-2 -> 1-2n721`、`1-2ZKK-4 -> 1-2n719` 不再作为 pass `component_mapping`
  - second-set fresh `.tmp/phase68_kk_slot_second/2_2`: `pair_count=1601`, `issue_count=303`, `component_mapping=46`, `kk_multi_port_component=28`
  - second 代表目标 `1-21DK2-1 -> ZD8`、`1-21ZKK-2 -> 1-21n715` 命中；Phase52/66 input matrix 基线保持 `input_matrix_wire_mapping=168`、`covered_input_matrix_ordinary=336`
- [ ] 下一刀建议：继续只读审计 acceptance suite 的结构化 golden 口径，或回到 Phase51 packaged sidecar/exe smoke；不要在同一刀混入 terminal/rules/UI。
- **Status:** complete

### Phase 55: CLP Strip Component Mapping And Acceptance Redline Refresh
- [x] 只读恢复并确认当前外部/并发改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`。
- [x] 审计确认 `strip_two_port_component` 已有 FJL 块端口、上下外部端和支撑竖线门槛；本轮最小缺口是本体正则只认 `KLP`、漏掉同几何的 `CLP`。
- [x] 实现目标：让 FJL 双端口 strip 子模式同时识别 `KLP/CLP` 本体，产出 `component_mapping/pass`，并只在结构化关系生成后消费对应 ordinary pair。
- [x] 验收口径同步：把 `second_set_component_terminal_subset` 中 S0020 旧 `ordinary_pair/review` 裸数字 golden 刷新为 `3-21CLP2..7` 的 `component_mapping/pass/pair_key` 级 golden；不扩产品 CLI。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_component_diagrams.py` -> `17 passed`
  - `python -m pytest -q tests\unit\test_component_diagrams.py tests\integration\test_analyze_project.py -k "component or kk or strip"` -> `26 passed, 11 deselected`
  - `python -m pytest -q tests\integration\test_acceptance_evaluation.py` -> `5 passed`
  - `python -m dwg_audit.cli evaluate-acceptance-suite ... phase69_clp_strip_acceptance_v2` -> required `3/3`, `acceptance_passed=True`
  - `python -m pytest -q` -> `226 passed`
  - first-set fresh `.tmp/phase69_clp_strip_first/...`: `pair_count=1586`, `issue_count=441`, `component_mapping=138`, `strip_two_port_component=92`
  - first `S0023` 命中：`3-2CLP5-1 -> KD16`、`3-2CLP5-2 -> 3-2n414`；旧 `* -> 414` ordinary rows 为 `discard`
  - second-set fresh `.tmp/phase69_clp_strip_second/2_2`: `pair_count=1637`, `issue_count=285`, `component_mapping=82`, `strip_two_port_component=44`
  - second `S0020` 命中：`3-21CLP7-1 -> 3-21CD43`、`3-21CLP7-2 -> 3-21n419`；旧 `43 -> 419` ordinary rows 为 `discard`
  - Phase54 KK 代表目标与 Phase52 input matrix 红线保持：`5DK-2 -> 5FD25`、`1-2ZKK-2 -> 1-2n719`、`1-21DK2-1 -> ZD8`、`1-21ZKK-2 -> 1-21n715`、`input_matrix_wire_mapping=168`、`covered_input_matrix_ordinary=336`
- [ ] 下一刀建议：先做只读审计再决定继续 component 残差、terminal header table 规则语义，或回到 Phase51 packaged sidecar/exe smoke；不要把 issue_count 下降当成隐藏关系的目标。
- **Status:** complete

### Phase 56: Backplate Table Scoped Conflict Review
- [x] 只读恢复并确认当前外部/并发改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`。
- [x] 并发审计确认最新真实样本仍有 first-set `66` 个 `critical R-CROSS-PAGE-CONFLICT`，全部来自 `backplate_virtual_table` 同型表头跨背板页复用。
- [x] 实现目标：不移除 `table_mapping` 入图、不降低召回，只把背板虚拟表格跨装置/跨页作用域复用从全项目 critical conflict 重分类为 `review/backplate_table_scope_review`。
- [x] 风险门槛：普通 `table_mapping`/`component_mapping` 跨页冲突仍保持 critical；pair_count 与 pair_kind 分布不得变化。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "cross_page or table_mapping or component_mapping or one_to_many or many_to_one or semantic_mapping"` -> `18 passed, 26 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `44 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
  - `python -m pytest -q` -> `227 passed`
  - first-set fresh `.tmp/phase70_backplate_scope_first/...`: `pair_count=1586`, `issue_count=441`, `critical=0`, `review=435`, `minor=6`, `R-CROSS-PAGE-CONFLICT=66`, all cross-page classifications `backplate_table_scope_review`
  - first `table_mapping` 代表关系仍保留：`NDY306A-3 -> 1QD1`、`NDY306A-3 -> 1-2QD1`
  - second-set fresh `.tmp/phase70_backplate_scope_second/2_2`: `pair_count=1637`, `issue_count=285`, `wire_component_mapping=168`, `covered_input_matrix_ordinary=336`
  - acceptance suite on fresh second -> required `3/3`, all case precision/recall `1.0`
- [ ] 下一刀建议：继续只读审计后在 terminal header table 多端 review、terminal bare local numeric、或 wire inline split 三者中选一个最小切片；Phase51 packaged sidecar smoke 仍是独立交付链。
- **Status:** complete

### Phase 57: Terminal Header Table Multi-Endpoint Review
- [x] 只读恢复并确认当前外部/并发改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`。
- [x] 两个只读 explorer 与主线程产物核查一致确认：second `S0023 / 23 右侧端子图1.dwg` 的 `terminal_header_table` 多端关系仍被泛化成 ordinary one-to-many / many-to-one review。
- [x] 实现目标：保留 `table_mapping/pass` 图关系和 issue 可见性，只把同页 `terminal_header_table` 的左右列多端行、共享端点行重分类为专用 review 文案。
- [x] 风险门槛：仅匹配同页、高置信 `table_mapping`、`mapping_mode=terminal_header_table`、有效行号序列；one-to-many 需同一 `logical_endpoint + row_number` 且同时出现 left/right endpoint，many-to-one 需共享同一端点文本 id 或坐标。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "one_to_many or many_to_one or table_mapping or component_mapping or cross_page"` -> `16 passed, 30 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `46 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
  - `python -m pytest -q` -> `229 passed`
  - first-set fresh `.tmp/phase71_terminal_header_table_first/...`: `pair_count=1586`, `issue_count=441`, `pair_kind` unchanged; `terminal_header_table_multi_endpoint_review=8`、`terminal_header_table_shared_endpoint_review=7`
  - second-set fresh `.tmp/phase71_terminal_header_table_second/2_2`: `pair_count=1637`, `issue_count=285`, `pair_kind` unchanged; `terminal_header_table_multi_endpoint_review=44`、`terminal_header_table_shared_endpoint_review=22`
  - second 代表 issue 已重分类：`I0223 / PTMR0042+PTMR0043` 为“端子表左右列映射待复核”，`I0267 / PTM0042+PTMR0096` 为“端子表共享端点待复核”
  - acceptance suite on fresh second -> required `3/3`, `acceptance_passed=True`
- [ ] 下一刀建议：先做只读审计后在 terminal bare local numeric discard、wire inline split half-pair、或 Phase51 packaged sidecar smoke 中选一个独立切片。
- **Status:** complete

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `rg.exe` 启动被 Windows 拒绝访问 | 在 Codex app bundled `rg.exe` 上执行全文检索 | 改用 PowerShell `Select-String` / `Get-ChildItem`，后续本轮不重复同一 `rg` 调用 |
| `Get-Content` 旧路径失败 | 读取 `src\dwg_audit\execution_service.py` / `src\dwg_audit\sidecar.py` | 当前文件已迁到 `src\dwg_audit\services\execution.py` 与 `src\dwg_audit\desktop\sidecar.py`，后续按新路径读取 |
| `Select-Object -Index 740..785` 范围参数失败 | 读取本地 Tauri crate 源码片段 | 改用 `Select-Object -Skip ... -First ...` |
| Tauri `cargo test` 首次失败：`frontendDist` 路径不存在 | 未先生成 `apps/desktop/dist` 时运行 Rust tests | 先执行 `npm run build` 生成 gitignored dist，再跑 cargo test |
| Windows `link.exe` 间歇性 `LNK1104` 无法打开 test exe 输出 | 重跑 `cargo test` 时链接阶段偶发锁定输出路径 | 查无残留进程后立即重试，同命令通过；记录为 Windows target/linker 临时锁竞争 |
