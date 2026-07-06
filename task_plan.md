# Task Plan: XJToolkit DWG Audit MVP Closure

## Goal
重新对齐并完成 [doc/任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 定义的 DWG 审计 MVP 主链：输入项目级 DWG，生成结构化 findings 运行态，先做页级分类，再按图种路由到对应识别器，产出 pair / table mapping / evidence，运行项目级规则引擎，并输出可复核异常报告。

## Current Phase
Phase 82

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

### Phase 58: Terminal Row Number Local Numeric Suppression
- [x] 只读恢复并确认当前受保护外部/并发改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`；当前 HEAD 为 `7a4af5b`。
- [x] 两个只读 explorer 与主线程真实样本核查一致确认：端子图中连续行号列仍会作为裸数字 ordinary pair 进入 review，例如 first `S0025 8 -> ?`、first `S0027 ? -> 4`、second `S0022 9 -> 116`、second `S0021 69 -> 318`。
- [x] 实现目标：在 `build_terminal_candidates()` 中对 `屏端子图` 同列连续 1..99 裸数字行号列做候选级抑制，标记为 `terminal_row_number_local_numeric / semantic_channel`，不再参与 ordinary pair 竞争。
- [x] 风险门槛：仅匹配同 sheet、同 x 列、纵向步进连续、数值相邻、长度至少 5 的端子图行号列；完整派生端子文本如 `3-21n116` 仍保留为 numeric 候选。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_terminal_candidates.py` -> `24 passed`
  - `python -m pytest -q tests\unit\test_page_extractors.py` -> `5 passed`
  - rules targeted slice -> `14 passed, 32 deselected`
  - `python -m pytest -q` -> `230 passed`
  - first fresh `.tmp/phase72_terminal_row_number_first_v2/...`: `pair_count=1586`, `issue_count=361`, `ordinary_pair=836`, `continuation=175`, `terminal_row_number_local_numeric=289`; `R-PAIR-LOW-CONFIDENCE 58 -> 12`，`R-PAIR-MISSING-SIDE 230 -> 196`
  - second fresh `.tmp/phase72_terminal_row_number_second_v2/2_2`: `pair_count=1637`, `issue_count=198`, `ordinary_pair=849`, `continuation=202`, `terminal_row_number_local_numeric=418`; `R-PAIR-LOW-CONFIDENCE 66 -> 3`，`R-PAIR-MISSING-SIDE 149 -> 125`
  - 点名伪 pair 已消失：first `S0025 8 -> ?`、first `S0027 ? -> 4`、second `S0022 9 -> 116`、second `S0021 69 -> 318`
  - second 红线保持：`wire_component_mapping=168`、`table_mapping=176`、`component_mapping=82`，acceptance suite required `3/3`
- [ ] 下一刀建议：继续只读审计后处理 wire inline split half-pair，或回到 Phase51 packaged sidecar/exe smoke；不要把 issue_count 下降当成隐藏关系目标。
- **Status:** complete

### Phase 59: Inline Numeric Bridge BBox Coverage
- [x] 只读恢复并确认当前受保护外部/并发改动仍限于 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md`；当前 HEAD 为 `ca2d8fc`。
- [x] 三个只读 explorer 与主线程审计一致确认：Phase72 后 first 仍有 35 条、second 仍有 6 条 `complementary_half_pair / inline_wire_split`，代表样本是被 inline 数字切断的同一根 wire chain。
- [x] 实现目标：在 `_has_inline_numeric_bridge()` 中用 TEXT bbox 的轴向区间判断是否覆盖断点间隙，修复真实 DWG 中 insert point 位于左线端附近但 bbox 横跨 gap 的漏桥接。
- [x] 风险门槛：只改线组 bridge 判断；不改 rules、不删除 issue、不扩 CLI/UI、不触碰受保护外部文件。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_line_groups.py` -> `9 passed`
  - `python -m pytest -q tests\unit\test_wire_components.py -k "inline_klp or input_matrix"` -> `5 passed, 1 deselected`
  - `python -m pytest -q tests\unit\test_page_extractors.py` -> `5 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or inline_klp or run_audit"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `231 passed`
  - first fresh `.tmp/phase73_inline_bridge_first/...`: `pair_count=1550`, `issue_count=327`, `ordinary_pair=800`, `wire_component_mapping=32`, `table_mapping=299`, `component_mapping=138`; `complementary_half_pair` 从 35 降到 2，剩余 2 条位于 `07 网络通讯回路图.dwg` 短 gap 边界。
  - second fresh `.tmp/phase73_inline_bridge_second/2_2`: `pair_count=1462`, `issue_count=191`, `ordinary_pair=674`, `wire_component_mapping=168`, `table_mapping=176`, `component_mapping=82`; `complementary_half_pair` 从 6 降到 0。
  - first `08/09/10` 与 second `08/12` 点名 inline split 页级 `complementary_half_pair` 均为 0；acceptance suite required `3/3`。
- [ ] 下一刀建议：继续只读审计 first `07 网络通讯回路图.dwg` 两条短 gap 半链，或转向 terminal/table/component 规则语义残差；Phase51 packaged sidecar smoke 仍独立。
- **Status:** complete

### Phase 60: Terminal Header Semantic Endpoint Exclusion
- [x] 只读恢复并确认当前工作区只有本轮允许更新的 `doc/任务书.md` 修改，以及外部/并发 `doc/page_findings/`、`doc/page_task_queue.md` 未跟踪目录；当前 HEAD 为 `0cac857`。
- [x] 按用户要求先刷新 `doc/任务书.md`：Phase52/53/54/55 旧“未实现/错配” backlog 已改为完成或过期；active backlog 收缩为 terminal semantic endpoint、inline KLP 116 residual、component-prefixed 218 residual 三条；背板表格与 component/table mapping branch 改写为 rules/acceptance 质量问题。
- [x] 实现目标：在 `TableExtractor` 的 table endpoint 谓词中排除 `I0/I0'/IA/UA/UB/UC/UN/3U0/3U0'` 等语义代号，使其不再进入 `terminal_header_table` 的 `table_mapping/pass` endpoint。
- [x] 风险门槛：只改 `src/dwg_audit/audit/table_extractor.py` 与表格抽取单测；不改 KLP residual、218 residual、rules、CLI/UI，也不移除正常 `terminal_header_table` 图关系。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_table_extractor.py` -> `14 passed`
  - `python -m pytest -q tests\unit\test_page_extractors.py` -> `5 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "terminal_header_table or table_extractor"` -> `3 passed, 17 deselected`
  - `python -m pytest -q` -> `232 passed`
  - second fresh `.tmp/phase74_terminal_header_semantic_second/2_2`: `pair_count=1460`, `issue_count=188`, `table_mapping=174`, `wire_component_mapping=168`, `input_matrix_wire_mapping=168`, `component_mapping=82`
  - `3-21ID9 -> I0` 与 `3-21QD7 -> I0` 的 `table_mapping/pass` 均为 `0`；`I0` 在 `S0021` 仍保留 `semantic_channel/not_numeric` candidate 证据 `8` 条。
  - 既有正常关系保持：`3-21ID9 -> 3-21n707`、`3-21QD7 -> 3-21n128` 仍为 `table_mapping/pass`；`terminal_header_table` by sheet 为 `S0021=32`、`S0022=7`、`S0023=112`、`S0024=23`。
- [ ] 下一刀候选只剩：`inline KLP 116 residual suppression`、`component-prefixed 218 residual suppression`、`backplate/component mapping rules semantics`；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 61: Component-Prefixed Local Number Residual Suppression
- [x] 只读恢复并确认当前 HEAD 为 `9f2bc50`，受保护外部/并发路径仍只有 `doc/page_findings/`、`doc/page_task_queue.md` 未跟踪，未纳入本轮写集。
- [x] 并发只读审计确认 `component_prefixed_signal_circuit` extractor 已闭合，first `S0017 / 16 高低压侧操作箱信号回路.dwg` 已稳定产出 `1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1` 等 `wire_component_mapping/pass`；本轮只处理旧普通 PairBuilder 裸 `218` residual。
- [x] 实现目标：把被 `component_prefixed_signal_circuit` 结构化映射消费的局部号 ordinary pair 标记为 `discard`、`ordinary_pair_eligible=False`，不覆盖外侧端子、不移除 `wire_component_mapping` 入图、不改 rules/CLI/UI。
- [x] 风险门槛：复用并扩展原 input matrix 覆盖逻辑；`input_matrix_wire_mapping` 仍覆盖矩阵局部号，`component_prefixed_signal_circuit` 只覆盖 `evidence.local_number_text_id`；非目标 `S0013` 裸 `218` review 不得被全局抑制。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_page_extractors.py` -> `7 passed`
  - `python -m pytest -q tests\unit\test_wire_components.py -k "component_prefixed_signal or input_matrix"` -> `6 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "component_prefixed_signal_circuit_mapping or run_audit or mixed_source"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `234 passed`
  - first fresh `.tmp/phase75_component_218_first/...`: `pair_count=1550`, `issue_count=311`, `wire_component_mapping=32`, `component_mapping=138`, `table_mapping=299`；`R-PAIR-MISSING-SIDE=147`
  - first `S0017` 旧 `PW0532 ? -> 218`、`PW0534 ? -> 218` 已为 `discard`，且 `covered_by_component_prefixed_signal_circuit=True`、`ordinary_pair_eligible=False`；结构化 `PWM0008 1-2n218 -> 1-4YD1`、`PWM0021 3-2n218 -> 3-4YD1` 保持 `wire_component_mapping/pass/confidence=0.95`
  - first 非目标 `S0013` 的 `PW0336 ? -> 218`、`PW0337 218 -> ?` 仍为 review，证明没有全局按数字 `218` 抑制
  - second fresh `.tmp/phase75_component_218_second/2_2`: `pair_count=1460`, `issue_count=188`, `wire_component_mapping=168`, `input_matrix_wire_mapping=168`, `component_mapping=82`, `table_mapping=174`
  - second 红线保持：`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218` 仍有 `wire_component_mapping/pass`；`1-21GD9 -> 1-21n218` 仍有 `table_mapping/pass`；`semantic_table_mapping_pass_endpoint_count=0`
- [ ] 下一刀候选只剩：`inline KLP 116 residual suppression`、`backplate/component mapping rules semantics`；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 62: Component Split Endpoint Rules Semantics
- [x] 只读恢复并确认当前 HEAD 为 `7fb59b9`；`doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md` 仍按外部/并发改动处理，不纳入本轮 rules 写集。
- [x] 只读审计确认 `inline KLP 116 residual suppression` 作为 active slice 已过期/收缩：first-set 代表 `1KLP1-2 -> 1n116`、`1-2KLP1-2 -> 1-2n116`、`3-2KLP1-2 -> 3-2n116` 已为 `wire_component_mapping/pass`；本轮不重开已闭合 extractor。
- [x] 实现目标：保留 `strip_two_port_component` 逗号拆分后的 `component_mapping/pass` 图关系和 issue 可见性，只把由同一原始逗号文本或拆分端点邻接产生的 one-to-many / many-to-one review 改为专用 `component_split_endpoint_group_review` 分类与文案。
- [x] 风险门槛：只改 `src/dwg_audit/audit/rules.py` 与 rules 单测；不改 extractor、pair 生成、acceptance fixture、CLI/UI，也不为了降低 issue_count 隐藏 component_mapping。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "one_to_many or many_to_one or component_branch or split_endpoint or backplate or terminal_header"` -> `11 passed, 37 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `48 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
  - `python -m pytest -q` -> `236 passed`
  - first fresh `.tmp/phase76_component_split_rules_first/...`: `pair_count=1550`, `issue_count=311`, pair_kind unchanged；`R-ONE-TO-MANY` 中 `component_split_endpoint_group_review=16`，`R-MANY-TO-ONE` 中 `component_split_endpoint_group_review=12`
  - first target issue 已重分类：`I0226` 为“组件逗号端点拆分待复核”，`I0270` 为“组件逗号端点邻接待复核”；`PCM0001/PCM0002/PCM0003/PCM0039` 等 component mappings 仍为 pass。
  - second fresh `.tmp/phase76_component_split_rules_second/2_2`: `pair_count=1460`, `issue_count=188`, pair_kind unchanged；split issue count `0`，`wire_component_mapping=168`、`component_mapping=82`、`table_mapping=174`、`semantic_table_mapping_pass_endpoint_count=0`
- [ ] 下一刀候选收缩为：`backplate virtual table same-sheet one-to-many scope semantics`、`terminal_header_table issue aggregation`、`inline signal page ordinary residual taxonomy guardrail`；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 63: Backplate Virtual Table Same-Sheet Scope Review
- [x] 只读恢复并确认当前 HEAD 为 `27e5435`；外部/并发 `doc/任务书.md`、`doc/page_findings/`、`doc/page_task_queue.md` 未纳入本轮写集。
- [x] 四个只读 explorer 与主线程 phase76 产物核查一致确认：first `S0021 / 20 非电量保护背板图.dwg` 的 18 条 `NKR308A-*` 同页背板虚拟表 one-to-many 仍是 generic “一对多待复核”，而非背板表格作用域语义。
- [x] 实现目标：保留所有 `backplate_virtual_table` `table_mapping/pass` 图关系和 issue 可见性，只把同页不同表格区域/表头 scope 的背板虚拟表 fanout 重分类为 `backplate_table_same_sheet_scope_review`。
- [x] 风险门槛：只改 `src/dwg_audit/audit/rules.py` 与 rules 单测；不改 `table_extractor.py`、classifier/router、PairBuilder、acceptance fixture、CLI/UI，也不减少 issue_count。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "backplate or one_to_many or many_to_one or component_split or terminal_header"` -> `13 passed, 37 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `50 passed`
  - backplate/table targeted integration -> `6 passed, 28 deselected`
  - `python -m pytest -q` -> `238 passed`
  - first fresh `.tmp/phase77_backplate_same_sheet_first/...`: `pair_count=1550`, `issue_count=311`, pair_kind and rule counts unchanged；`backplate_table_same_sheet_scope_review=18`，generic one-to-many review 从 `20` 降到 `2`
  - first target pairs remain pass `table_mapping`: `NKR308A-1 -> 5FD11`、`NKR308A-1 -> 5FD15`、`NKR308A-7 -> 5KLP1-2`、`NKR308A-7 -> 5KLP5-2`
  - second fresh `.tmp/phase77_backplate_same_sheet_second/2_2`: `pair_count=1460`, `issue_count=188`, pair_kind unchanged；terminal_header_table and semantic endpoint redlines unchanged。
- [ ] 下一刀候选：`terminal_header_table issue aggregation`、`inline signal page ordinary residual taxonomy guardrail`、`backplate/component many-to-one scope semantics`；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 64: Backplate Structured Shared Endpoint Review
- [x] 只读恢复并确认当前 HEAD 为 `33b9681`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 四个只读 explorer 与主线程 phase77 产物核查一致确认：first-set `R-MANY-TO-ONE` 剩余 18 条 generic 中，16 条含 `backplate_virtual_table` 与 `component_mapping`/`terminal_header_table`/背板虚拟表共享外部端点，属于 rules 语义过严；`KD6` component+terminal 与 `KD23` 纯 terminal-header 边界不纳入本轮。
- [x] 实现目标：保留所有 `table_mapping/pass` 与 `component_mapping/pass` 图关系和 issue 可见性，只把含背板虚拟表的结构化共享端点 many-to-one 重分类为 `backplate_structured_shared_endpoint_review`。
- [x] 风险门槛：只改 `src/dwg_audit/audit/rules.py` 与 rules 单测；必须含 `backplate_virtual_table` 才触发；普通 pair、纯 `terminal_header_table`、component+terminal 非背板共享端点仍保持 generic。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "structured_mapping_shared_endpoint or non_backplate_structured or many_to_one or backplate or terminal_header"` -> `11 passed, 42 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `53 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "run_audit or mixed_source"` -> `1 passed, 19 deselected`
  - `python -m pytest -q` -> `241 passed`
  - first fresh `.tmp/phase78_backplate_structured_shared_first/...`: `pair_count=1550`, `issue_count=311`, pair_kind unchanged；`R-MANY-TO-ONE` 中 `backplate_structured_shared_endpoint_review=16`，generic `多对一配对` 从 `18` 降到 `2`
  - first target examples reclassified: `5KLP8-1` (`PCM0089 + P0211`), `1QD5` (`PCK0002 + P0002`), `5FD25` (`PCK0006 + P0168`)。
  - remaining generic boundaries intentionally preserved: `KD6` (`PCM0050 + PTM0019 + PTM0025`) and `KD23` (`PTM0051 + PTM0054`)。
  - second fresh `.tmp/phase78_backplate_structured_shared_second/2_2`: `pair_count=1460`, `issue_count=188`, pair_kind unchanged；`backplate_structured_shared_endpoint_review=0`，`terminal_header_table_shared_endpoint_review=21`。
  - second redlines held: `1-21QD34 -> 1-21n218` and `3-21QD28 -> 3-21n218` remain `wire_component_mapping/pass`; `1-21GD9 -> 1-21n218` remains `table_mapping/pass`; `semantic_table_mapping_pass_endpoint_count=0`。
- [ ] 下一刀候选：`terminal_header_table issue aggregation`、`inline signal page ordinary residual wire-chain guardrail`；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 65: Terminal Header Table Issue Aggregation
- [x] 只读恢复并确认当前 HEAD 为 `ccd6ef6`；工作区有上一段代理留下的 `rule_base.py` / `test_pairs_and_rules.py` 未提交改动，受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md` 未纳入本轮写集。
- [x] 只读审计结论：`terminal_header_table` 的 `table_mapping/pass` 关系和专用 review 分类正确，second-set 主要噪声来自 43 条左右列多端 review 与 21 条共享端点 review 的行级洪峰；本轮只做 rules 层聚合，不改 extractor、不移除结构化关系。
- [x] 实现目标：在 `cluster_issues()` 中对 `terminal_header_table_multi_endpoint_review` 与 `terminal_header_table_shared_endpoint_review` 增加 range-aware 聚合；相邻 row range / shared endpoint suffix 连续时合并，间隔较远的自然簇保持分开。
- [x] 风险门槛：只改 `src/dwg_audit/audit/rule_base.py` 与 rules 单测；`pair_count`、`pair_kind`、`table_mapping/pass` 不漂移；singleton review 仍保留为独立 issue，不为了降低 issue_count 隐藏图关系。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "terminal_header_table or one_to_many or many_to_one"` -> `14 passed, 42 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `56 passed`
  - `python -m pytest -q tests\unit\test_table_extractor.py -k "terminal_header_table"` -> `3 passed, 11 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "terminal_header_table or table_mapping"` -> `4 passed, 16 deselected`
  - `python -m pytest -q` -> `244 passed`
  - first fresh `.tmp/phase79_terminal_header_aggregation_first/...`: `pair_count=1550`, `issue_count=305`, pair_kind unchanged；terminal-header 分类从 Phase78 的 8+7 行级 review 收敛为 `R-ONE-TO-MANY=5`、`R-MANY-TO-ONE=4`。
  - second fresh `.tmp/phase79_terminal_header_aggregation_second/2_2`: `pair_count=1460`, `issue_count=129`, pair_kind unchanged；terminal-header 分类收敛为 5 个自然 issue：4 个 `R-ONE-TO-MANY`、1 个 `R-MANY-TO-ONE`。
  - second 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系。
- [ ] 下一刀候选收缩为：`inline signal page ordinary residual wire-chain guardrail`；若回到产品化，则单独切 Phase51 packaged sidecar/exe smoke，不与 rules 聚合混入。
- **Status:** complete

### Phase 66: Inline Wire-Chain DIM Guardrail
- [x] 只读恢复并确认当前 HEAD 为 `3d6d0fd`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 两个只读 explorer 与主线程 phase79 产物核查一致确认：first `S0008 / 07 网络通讯回路图.dwg` 的 2 条 `complementary_half_pair` 来自 `CONNECT` 主水平线与 y 方向错位的纯 `DIM` 短线共享同一数字文本锚点，不应解释成同一根 inline broken wire chain。
- [x] 实现目标：只在 rules 诊断层增加 wire-chain guardrail；互补半链聚合必须要求 line group y 差不超过 inline tolerance，且两侧都不是纯 `DIM` 线；普通 `R-PAIR-MISSING-SIDE` 也不再对纯 `DIM` line group 报缺边。
- [x] 风险门槛：只改 `src/dwg_audit/audit/rules.py` 与 rules 单测；不改 `line_groups.py`、候选生成、PairBuilder、extractor、CLI/UI；不移除 pair graph input，`CONNECT` 主线缺边仍保持可见。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "complementary or missing_side"` -> `4 passed, 53 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `57 passed`
  - `python -m pytest -q` -> `245 passed`
  - first fresh `.tmp/phase80_inline_wire_chain_guardrail_first/...`: `pair_count=1550`, `issue_count=302`, pair_kind unchanged；`complementary_half_pair=0`；`R-PAIR-MISSING-SIDE=144`。
  - first target residuals no longer emit `互补半链待复核`：`PW0178 ? -> 701` and `PW0202 ? -> 601` remain ordinary missing-side on `CONNECT` line groups; `PW0182/GW0182` and `PW0205/GW0205` pure `DIM` short-line issues are suppressed at rules issue level.
  - second fresh `.tmp/phase80_inline_wire_chain_guardrail_second/2_2`: `pair_count=1460`, `issue_count=127`, pair_kind unchanged；`complementary_half_pair=0`。
  - second redlines held: `semantic_table_mapping_pass_endpoint_count=0`；`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` remain structured pass relationships.
- [ ] 下一刀候选：优先做只读审计后在剩余 ordinary missing-side/low-confidence 最大簇中选一个真实样本系统误解；若转向产品化，则单独切 Phase51 packaged sidecar/exe smoke。
- **Status:** complete

### Phase 67: Schematic Wire Logic Endpoint Mapping
- [x] 只读恢复并确认当前 HEAD 为 `2402b9a`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 两个只读 explorer 与主线程 Phase80 产物核查确认：second-set 最大剩余簇不是 terminal/header/table 规则问题，而是 `11/16 测控控制回路图2` 等二次原理图中 `1-21CD58`、`3-21CD58`、`1-21UD8` 这类逻辑端编号被 `not_numeric/noise_channel` 拒掉，导致 `? -> 511` ordinary missing-side。
- [x] 实现目标：在候选层增加窄范围 `wire_logic_endpoint_channel`，只接受二次原理图 horizontal/grid 线组附近形如 `^[13]-21[A-Z]{2,4}\d{1,3}$` 的逻辑端；PairBuilder 只在对侧存在数字候选时消费该通道，并把“逻辑端 + 数字端”升为 `pair_kind=wire_component_mapping` / `component_submode=schematic_wire_logic_endpoint`。
- [x] 风险门槛：不把普通非数字文本塞回 `terminal_numeric_channel`；逻辑端单侧不得制造新的 missing-side；不触碰 `table_extractor.py`、component/table extractor、rules、CLI/UI；保持端子表语义端 `I0/IA/UA/UB/UC/UN/3U0` 不进入 `table_mapping/pass` endpoint。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_terminal_candidates.py -k "schematic_logic_endpoint or semantic_marker or single_sided_schematic_logic"` -> `3 passed, 24 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `57 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or input_matrix or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `248 passed`
  - first fresh `.tmp/phase81_schematic_logic_endpoint_first_v2/...`: `pair_count=1550`, `issue_count=302`, pair_kind unchanged from Phase80；`wire_logic_endpoint_channel=0`，证明第一套未漂移。
  - second fresh `.tmp/phase81_schematic_logic_endpoint_second_v2/2_2`: `pair_count=1460`, `issue_count=58`; `R-PAIR-MISSING-SIDE=48`；`wire_component_mapping` 从 Phase80 的 `168` 增至 `245`，新增 77 条窄逻辑端结构化关系。
  - second targets hit: `1-21CD58 -> 511`、`3-21CD58 -> 511` 均为 `wire_component_mapping/review`，`11/16 测控控制回路图2` 的 missing-side 均为 0。
  - second 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` remain structured pass relationships。
- [ ] 下一刀候选：继续只读审计 second 剩余 `R-PAIR-MISSING-SIDE=48` 与 first `R-PAIR-MISSING-SIDE=144` 的真实结构；若转产品化，则单独切 Phase51/M11 packaged sidecar/exe smoke。
- **Status:** complete

### Phase 68: Schematic Complementary Half-Chain Geometry Review
- [x] 只读恢复并确认当前 HEAD 为 `75722bc`；工作区已有上一段代理留下的 `rules.py` / `test_pairs_and_rules.py` 未提交改动，受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md` 未纳入本轮写集。
- [x] 复核确认 Phase60 `terminal_header_table semantic endpoint exclusion` 已完成并提交；本轮不重开 `TableExtractor`，只收口 Phase81 剩余 ordinary missing-side 中的几何互补半链 rules 语义。
- [x] 实现目标：允许二次原理图 `grid` line group 在较宽符号间隙或小重叠下聚合为 `complementary_half_pair` review；保留 pair graph 和 missing-side 可见性，不把关系改成 pass/discard。
- [x] 必要保真修复：`run-audit --findings` 的 rerun loader 现在恢复 `LineGroup.orientation` 与 `row_band_id`，避免历史 findings audit-only 把 `grid` 误当 `horizontal`，导致 rules 验证和 fresh analyze 不一致。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "complementary or dim"` -> `4 passed, 55 deselected`
  - `python -m pytest -q tests\unit\test_rerun_audit.py` -> `2 passed`
  - `python -m pytest -q` -> `250 passed`
  - audit-only second `.tmp/phase82_complementary_audit_second_v2`: `issue_count=51`, `R-PAIR-MISSING-SIDE=41`, `complementary_half_pair=7`
  - audit-only first `.tmp/phase82_complementary_audit_first_v2`: `issue_count=278`, `R-PAIR-MISSING-SIDE=120`, `complementary_half_pair=24`
  - fresh second `.tmp/phase82_complementary_second_audit`: `pair_count=1460`, `issue_count=51`, pair_kind unchanged；`ordinary_pair=597`, `wire_component_mapping=245`, `table_mapping=174`, `component_mapping=82`
  - fresh first `.tmp/phase82_complementary_first_audit`: `pair_count=1550`, `issue_count=278`, pair_kind unchanged；`table_mapping=299`, `component_mapping=138`, `wire_component_mapping=32`
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second `1-21CD58 -> 511`、`3-21CD58 -> 511` 仍为 `wire_component_mapping/review`；`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍为结构化 pass 关系；first `1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307` 仍命中。
- [ ] 下一刀候选收缩为：second AC phase-label semantic/covered mapping、second DC/GND/function-label semantic mapping、second network-time/function-label semantic mapping、first prefixed external endpoints、first ZLP component two-port mapping；backplate/component/table mapping 继续按 rules/acceptance/display 质量单独切片。
- **Status:** complete

### Phase 69: ZLP Strip Two-Port Component Mapping
- [x] 只读恢复并确认当前 HEAD 为 `691ed3b`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 复核确认用户早前点名的 Phase60 `terminal_header_table semantic endpoint exclusion`、Phase61 `component-prefixed 218 residual suppression`、Phase62 `inline KLP 116 residual` 收缩均已完成；本轮不重开 `TableExtractor`、KLP/CLP extractor 或 rules 聚合。
- [x] 两个只读 explorer 与主线程 Phase82 产物核查一致确认：first `S0023 / 22 元件接线图2.dwg` 的 `1-2ZLP4` 与既有 KLP/CLP 长条双端口结构同构，块内端口 `1/2`、外部 `KD26 / 1-2n422` 和 vertical support line 都存在；旧输出仅因 body regex 不认 `ZLP` 留下 `PC0090 ? -> 422`。
- [x] 实现目标：把 `strip_two_port_component` body family 从 `KLP/CLP` 窄扩到同构 `ZLP`，输出 `component_mapping/pass`；不改候选层、PairBuilder、rules、CLI/UI、acceptance fixture，也不移除普通 pair graph 输入。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_component_diagrams.py -k "strip_two_port or zlp"` -> `9 passed, 9 deselected`
  - `python -m pytest -q tests\unit\test_component_diagrams.py` -> `18 passed`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "component or kk or strip or run_audit"` -> `10 passed, 10 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py` -> `59 passed`
  - `python -m pytest -q` -> `251 passed`
  - first fresh `.tmp/phase83_zlp_first/...` + `.tmp/phase83_zlp_first_audit`: `pair_count=1562`, `issue_count=272`, `component_mapping=150`, `R-PAIR-MISSING-SIDE=114`。
  - first target hit: `1-2ZLP4-1 -> KD26` and `1-2ZLP4-2 -> 1-2n422` are `component_mapping/pass/confidence=0.95/component_submode=strip_two_port_component`; former `PC0090 ? -> 422` and sibling `PC0104 ? -> 422` are now `discard` covered by component mapping.
  - first KLP/CLP and prefixed redlines held: `5KLP5-1 -> 5KLP3-1`, `5KLP5-1 -> 5KLP2-1`, `5KLP5-2 -> 5n307`, `1-2n218 -> 1-4YD1`, `3-2n218 -> 3-4YD1` remain structured pass mappings.
  - second fresh `.tmp/phase83_zlp_second/2_2` + `.tmp/phase83_zlp_second_audit`: `pair_count=1460`, `issue_count=51`, pair_kind unchanged from Phase82；`wire_component_mapping=245`, `table_mapping=174`, `component_mapping=82`。
  - second redlines held: `semantic_table_mapping_pass_endpoint_count=0`; `1-21CD58 -> 511`, `3-21CD58 -> 511`, `1-21QD34 -> 1-21n218`, `3-21QD28 -> 3-21n218`, `1-21GD9 -> 1-21n218` remain expected structured relations.
- [ ] 下一刀候选收缩为：second AC phase-label semantic/covered mapping、second DC/GND/function-label semantic mapping、second network-time/function-label semantic mapping、first prefixed external endpoints、backplate/component/table mapping rules semantics；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 70: Second DC/GND Function Semantic Mapping
- [x] 只读恢复并确认当前 HEAD 为 `92f8c3a`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 只读审计结论：second `S0006 / 06 直流回路图.dwg` 中 `DC 0-5V/4-20mA +/-` 与 `GND` 是二次原理图功能/语义端标签，旧候选层按 `not_numeric/noise_channel` 拒绝后留下普通缺边；本轮不触碰 AC phase、network-time、first prefixed endpoints 或 backplate/component/table rules。
- [x] 实现目标：新增窄范围 `schematic_semantic_endpoint_channel`，只在二次原理图 horizontal/grid 且直流上下文中接受 `DC 0-5V/4-20mA +/-` 与 `GND`；PairBuilder 只在对侧存在真实 `terminal_numeric_channel` 时消费，并输出 `pair_kind=semantic_mapping` / `semantic_mapping_kind=schematic_dc_function_label` / `ordinary_pair_eligible=False`。
- [x] 风险门槛：不把语义标签提升为 `terminal_numeric_channel` 或 ordinary hard pass；单侧语义标签不得制造新 missing-side review；端子图 `I0/IA/UA/UB/UC/UN/3U0` 仍只保留为 semantic / rejected candidate evidence，不进入 `table_mapping/pass` endpoint。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_terminal_candidates.py -k "schematic_dc or schematic_semantic_endpoint or schematic_logic_endpoint"` -> `5 passed, 25 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
  - `python -m pytest -q` -> `254 passed`
  - second fresh `.tmp/phase84_dc_semantic_second/2_2` + `.tmp/phase84_dc_semantic_second_audit`: `pair_count=1460`, `issue_count=45`, `R-PAIR-MISSING-SIDE=35`, `semantic_mapping=164`。
  - second targets now include semantic review relations: `611 -> DC 0-5V/4-20mA +`, `609 -> DC 0-5V/4-20mA +`, `607 -> DC 0-5V/4-20mA +`, and `GND -> 101` as `semantic_mapping/review` with `ordinary_pair_eligible=False`。
  - second redlines held: `semantic_table_mapping_pass_endpoint_count=0`; `I0/IA/UA/UB/UC/UN/3U0` remain `semantic_channel` rejected evidence on terminal pages; `1-21CD58 -> 511`, `3-21CD58 -> 511`, `1-21QD34 -> 1-21n218`, `3-21QD28 -> 3-21n218`, `1-21GD9 -> 1-21n218` remain expected structured relations.
  - first fresh `.tmp/phase84_dc_semantic_first/...` + `.tmp/phase84_dc_semantic_first_audit`: `pair_count=1562`, `issue_count=269`, `R-PAIR-MISSING-SIDE=111`, `semantic_mapping=106`; KLP/CLP/ZLP and prefixed structured redlines held.
- [ ] 下一刀候选收缩为：second AC phase-label semantic/covered mapping、second network-time/function-label semantic mapping、first prefixed external endpoints、backplate/component/table mapping rules semantics；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 71: Second Network-Time Function Semantic Mapping
- [x] 只读恢复并确认当前 HEAD 为 `d3bff0a`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 四个只读 explorer 与主线程 Phase84 产物核查确认：second `S0007 / 07 网络对时回路图.dwg` 的 `TD1..TD5`、`B+/-`、`B code +/-`、`Device alarm` 属于网络/对时功能标签，旧候选层按 `not_numeric/noise_channel` 拒绝后留下 8 条普通缺边；本轮不混入 AC phase、first prefixed endpoints 或 backplate rules。
- [x] 实现目标：沿 Phase70 的 `schematic_semantic_endpoint_channel` 窄扩 network/time sheet context，只接受 network-time 白名单标签；PairBuilder 复用完整“语义端 + 数字端”映射，并新增仅限 `schematic_network_time_label` 的同侧 annotation 语义，输出 `pair_kind=semantic_mapping` / `ordinary_pair_eligible=False`。
- [x] 风险门槛：不把任意英文/中文说明文本提升为 endpoint；不碰 page_classifier/router、component/table extractor、rules 主逻辑、CLI/UI；单侧标签仍不得制造 ordinary missing-side。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_terminal_candidates.py -k "network_time or schematic_dc or schematic_semantic_endpoint or schematic_logic_endpoint"` -> `7 passed, 25 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `256 passed`
  - second fresh `.tmp/phase85_network_time_second/2_2` + `.tmp/phase85_network_time_second_audit`: `pair_count=1460`, `issue_count=37`, `R-PAIR-MISSING-SIDE=27`, `semantic_mapping=172`；`S0007` issue 清零。
  - second target relations include `TD4 -> 602`, `TD2 -> 601`, `TD3 -> 602`, `TD1 -> 601`, plus `Device alarm -> 110` and `B+ -> 601` annotation semantics as `semantic_mapping/review`。
  - first fresh `.tmp/phase85_network_time_first/...` + `.tmp/phase85_network_time_first_audit`: `pair_count=1562`, `issue_count=258`, `R-PAIR-MISSING-SIDE=100`, `semantic_mapping=117`。
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second wire/component/table structured redlines and first KLP/ZLP/component-prefixed structured mappings all held.
- [ ] 下一刀候选收缩为：second AC phase-label semantic/covered mapping、first prefixed external endpoints、backplate/component/table mapping rules semantics；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 72: Second AC Phase-Label Semantic Annotation
- [x] 只读恢复并确认当前 HEAD 为 `a5522b7`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 两个只读 explorer 与主线程 Phase85 产物核查确认：second `S0004/S0005 / 04/05 交流回路图*.dwg` 中 `UA/UB/UC/UN/UX/3U0` 是 CT/VT AC phase/function label，旧候选层按 `not_numeric/noise_channel` 拒绝后留下 ordinary missing-side；本轮不混入 terminal-row、first prefixed endpoints 或 backplate rules。
- [x] 实现目标：沿 Phase70/71 的 `schematic_semantic_endpoint_channel` 窄扩 AC/CT-VT sheet context，只接受 `UA/UB/UC/UN/UX/3U0/3U0'`；PairBuilder 允许该 detail 进入同侧 annotation semantic，输出 `pair_kind=semantic_mapping` / `semantic_mapping_kind=schematic_ac_phase_label` / `ordinary_pair_eligible=False`。
- [x] 风险门槛：不接受 `I0/IA/IB/IC/IN` 为 AC phase label；端子图 `UA/UB/UC/UN/3U0` 仍保留为 `semantic_channel` / rejected evidence，不进入 schematic semantic endpoint，也不进入 `table_mapping/pass` endpoint；不把局部单字符 `1..6` 或 `1-21ZKK/3-21ZKK` 回灌为普通 endpoint。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_terminal_candidates.py -k "ac_phase or terminal_ac_marker or schematic_i0 or network_time or schematic_dc or schematic_semantic_endpoint"` -> `8 passed, 27 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `259 passed`
  - second fresh `.tmp/phase86_ac_phase_second/2_2` + `.tmp/phase86_ac_phase_second_audit`: `pair_count=1460`, `issue_count=33`, `R-PAIR-MISSING-SIDE=23`, `semantic_mapping=182`；新增 10 条 `schematic_ac_phase_label` semantic review。
  - second AC targets hit: `721 -> 3U0`、`723 -> UX`、`719 -> UC`、`717 -> UB`、`715 -> UA` 在 `04/05 交流回路图*.dwg` 中按候选窗口命中；`724 -> UX'` 与 `? -> 715/717/719` 另一半链仍是下一刀 covered/window 扩展候选。
  - first fresh `.tmp/phase86_ac_phase_first/...` + `.tmp/phase86_ac_phase_first_audit`: `pair_count=1562`, `issue_count=258`, `semantic_mapping=119`；新增 2 条 first AC semantic review，既有结构化红线保持。
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second `1-21CD58 -> 511`、`3-21CD58 -> 511`、`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍命中；first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 仍命中。
- [ ] 下一刀候选收缩为：second AC phase-label covered/window residual (`724 -> UX'` 与 `? -> 715/717/719` 半链)、first prefixed external endpoints、backplate/component/table mapping rules semantics；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 73: Second AC Phase-Label Covered Half-Lines
- [x] 只读恢复并确认当前 HEAD 为 `9a8bd37`；工作区继承上一段未提交实现，仅涉及 `page_extractors.py` 与 `test_page_extractors.py`，受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md` 未纳入本轮写集。
- [x] 审计结论：Phase86 second AC 剩余 7 条中，6 条 `? -> 715/717/719` sibling half-lines 与已存在的 `schematic_ac_phase_label` semantic mapping 共用同一个 numeric text，属于结构化语义关系覆盖下的普通半边 residual；`724 -> UX'` 尚无既有 semantic mapping，需要后续 strict nearby/window annotation 切片。
- [x] 实现目标：只在 `WireDiagramExtractor` 输出后扫描二次原理图内 `schematic_ac_phase_label` semantic mapping 的 `numeric_endpoint_text_id`，把共享该 numeric text 的 ordinary 单侧半边 pair 降为 `discard`，并标记 `covered_by_schematic_ac_phase_label_semantic_mapping`；不改候选窗口、PairBuilder、rules、table/component extractor 或 CLI/UI。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_page_extractors.py -k "ac_phase or input_matrix or terminal_prefixed"` -> `10 passed`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
  - `python -m pytest -q tests\unit\test_terminal_candidates.py -k "ac_phase or terminal_ac_marker or schematic_i0"` -> `3 passed, 32 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `262 passed`
  - second fresh `.tmp/phase87_ac_covered_second/2_2` + `.tmp/phase87_ac_covered_second_audit`: `pair_count=1460`, `issue_count=27`, `ordinary_pair review=21`；6 条 AC sibling half-lines 被 coverage discard，AC residual 只剩 `PW0047/GW0047 724 -> ?`。
  - first fresh `.tmp/phase87_ac_covered_first/...` + `.tmp/phase87_ac_covered_first_audit`: `pair_count=1562`, `issue_count=256`，既有 KLP/ZLP/218 structured redlines held。
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second `1-21CD58 -> 511`、`3-21CD58 -> 511`、`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍命中；first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 仍命中。
- [ ] 下一刀候选收缩为：second AC `724 -> UX'` strict nearby/window annotation、first prefixed external endpoints、backplate/component/table mapping rules semantics；每刀仍需先只读审计再做最小实现。
- **Status:** complete

### Phase 74: Second AC UX Prime Strict Line-Span Annotation
- [x] 只读恢复并确认当前 HEAD 为 `35cb72f`；工作区继承上一段未提交实现，仅涉及 `src/dwg_audit/audit/candidates.py` 与 `tests/unit/test_terminal_candidates.py`，受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md` 未纳入本轮写集。
- [x] 审计结论：second `S0005 / 05 交流回路图2.dwg` 的 `PW0047/GW0047 724 -> ?` 是 AC 相量语义标注残留；数字 `724` 与 `UX'` 位于同一严格 line-span 行带内，应形成 `schematic_ac_phase_label` 的 `semantic_mapping/review`，而不是普通 missing-side。
- [x] 实现目标：在 `build_terminal_candidates()` 中只为二次原理图 AC phase label 增加严格 line-span 候选补充，支持 `UX'`；新增跨行 AC 语义端 guard，但只作用于 `schematic_ac_phase_label`，避免误伤 DC/network-time 语义端。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_terminal_candidates.py -k "network_time or schematic_dc or schematic_semantic_endpoint or ac_phase or ux_prime or schematic_i0"` -> `10 passed, 29 deselected`
  - `python -m pytest -q tests\unit\test_page_extractors.py -k "ac_phase or input_matrix or terminal_prefixed"` -> `10 passed`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "semantic_mapping or missing_side"` -> `7 passed, 52 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `266 passed`
  - second fresh `.tmp/phase88_ac_ux_prime_second_v3/2_2` + `.tmp/phase88_ac_ux_prime_second_v3_audit`: `pair_count=1460`, `issue_count=26`, `ordinary_pair=571`, `semantic_mapping=183`, AC issue count `0`。
  - second target hit: `PW0047/GW0047 724 -> ?` is now `semantic_mapping/review` with `semantic_endpoint=UX'`, `numeric_endpoint=724`, `ordinary_pair_eligible=False`；`GW0048/T0134 UX'` is rejected as `schematic_semantic_out_of_row`。
  - DC regression held: `PW0106 607 -> DC 0-5V/4-20mA +` remains `semantic_mapping/review` after narrowing the row guard to AC labels only。
  - first fresh `.tmp/phase88_ac_ux_prime_first/...` + `.tmp/phase88_ac_ux_prime_first_audit`: `pair_count=1562`, `issue_count=256`，KLP/ZLP/218 structured redlines held。
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second `1-21CD58 -> 511`、`3-21CD58 -> 511`、`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` 仍命中；first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2n218 -> 1-4YD1`、`3-2n218 -> 3-4YD1`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` 仍命中。
- [ ] 下一刀候选收缩为：first prefixed external endpoints、backplate/component/table mapping rules semantics；若转向产品化，packaged sidecar/exe smoke 必须作为独立切片。
- **Status:** complete

### Phase 75: First Prefixed External Endpoint Mapping
- [x] 只读恢复并确认当前 HEAD 为 `c0dc1f7`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 审计结论：first `S0009/S0010/S0011` 中 `1QD5 / 1-2QD12 / 3-2QD12` 与同行裸 `105` 是前缀外部端到本页 `n###` 逻辑端的结构化关系；旧输出留下 `? -> 105` 普通缺边。`S0012` 的 `5FD25 -> 5n105` 属于 FD 变体，本轮不混入。
- [x] 实现目标：在 `wire_components.py` 增加 `first_prefixed_external_endpoint_mapping` 子模式，只接受非 `*-21QD*` 的 QD 外部端与同行 3 位局部号；在 `WireDiagramExtractor` 中只对当前普通单侧 residual 的局部号启用该子模式，避免把整片 QD 表无差别提升入图。
- [x] 覆盖策略：`page_extractors.py` 只用新结构关系的 `local_number_text_id` 覆盖普通半边 pair，外部端文本自身不被覆盖；`input_matrix_wire_mapping=168` 与 terminal semantic/table 红线保持隔离。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_wire_components.py -k "prefixed or input_matrix or inline_klp"` -> `10 passed`
  - `python -m pytest -q tests\unit\test_page_extractors.py -k "prefixed or input_matrix or terminal_prefixed"` -> `9 passed, 3 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "wire_component or missing_side or semantic_mapping"` -> `7 passed, 52 deselected`
  - `python -m pytest -q` -> `272 passed`
  - first fresh `.tmp/phase75_prefixed_external_first_v2/...` + `.tmp/phase75_prefixed_external_first_v2_audit`: `pair_count=1584`, `issue_count=232`, `wire_component_mapping=54`；新增 `first_prefixed_external_endpoint_mapping=22`。
  - first target hits: `1QD5 -> 1n105`、`1-2QD12 -> 1-2n105`、`3-2QD12 -> 3-2n105` are `wire_component_mapping/pass`；`PW0225/PW0250/PW0275 ? -> 105` are now `ordinary_pair/discard` with `covered_by_first_prefixed_external_endpoint_mapping=True`；`PW0309 ? -> 105` remains review because FD variant is out of scope.
  - second fresh `.tmp/phase75_prefixed_external_second_v2/2_2` + `.tmp/phase75_prefixed_external_second_v2_audit`: `pair_count=1460`, `issue_count=26`, `wire_component_mapping=245`, `input_matrix_wire_mapping=168`, `first_prefixed_external_endpoint_mapping=0`。
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second `1-21CD58 -> 511`、`3-21CD58 -> 511`、`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` held；first KLP/ZLP/218 structured redlines held。
- [ ] 下一刀候选收缩为：FD prefixed external endpoint residual (`5FD25 -> 5n105`)；backplate/component/table mapping rules semantics；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

### Phase 76: FD Prefixed External Endpoint Residual
- [x] 只读恢复并确认当前 HEAD 为 `1396809`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 两个只读 explorer 与主线程 parquet 核查一致确认：first `S0012 / 11 非电量开入回路.dwg` 的 `PW0309 ? -> 105` 是系统误解；`T0801=5FD25` 与 `T0830=105` 同行，页面 scope 为 `5n BINARY INPUT`，且背板/元件结构化证据中已有 `NDY306A-5 -> 5FD25`、`5DK-2 -> 5FD25` corroboration。
- [x] 实现目标：将 `first_prefixed_external_endpoint_mapping` 的端点族从 QD 窄扩到 `QD|FD`，仍保留非 `*-21QD*`、二次原理图、同行、右侧局部号、ordinary 单侧 residual eligible gate；不改 rules、table/component extractor、candidate 主逻辑或 CLI/UI。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_wire_components.py -k "prefixed or input_matrix or inline_klp"` -> `12 passed`
  - `python -m pytest -q tests\unit\test_page_extractors.py -k "prefixed or input_matrix or terminal_prefixed"` -> `9 passed, 3 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "wire_component or missing_side or semantic_mapping"` -> `7 passed, 52 deselected`
  - `python -m pytest -q` -> `274 passed`
  - first fresh `.tmp/phase76_fd_prefixed_first/...` + `.tmp/phase76_fd_prefixed_first_audit`: `pair_count=1589`, `issue_count=226`, `wire_component_mapping=59`；`first_prefixed_external_endpoint_mapping=27`。
  - first FD targets hit: `5FD25 -> 5n105` plus same-family `5FD3 -> 5n114`、`5FD26 -> 5n132`、`5FD1 -> 5n103` on the 5n input page；`PW0309 ? -> 105` is now `ordinary_pair/discard` with `covered_by_first_prefixed_external_endpoint_mapping=True`。
  - second fresh `.tmp/phase76_fd_prefixed_second/2_2` + `.tmp/phase76_fd_prefixed_second_audit`: `pair_count=1460`, `issue_count=26`, `wire_component_mapping=245`, `input_matrix_wire_mapping=168`, `first_prefixed_external_endpoint_mapping=0`。
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second `1-21CD58 -> 511`、`3-21CD58 -> 511`、`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` held；first KLP/ZLP/218 structured redlines held。
- [ ] 下一刀候选收缩为：second inline wire split `505` half-chain bridge；second component vertical `401` mapping upgrade；backplate/component/table mapping rules semantics；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

### Phase 77: Second Inline Wire Split 505 Half-Chain Continuation
- [x] 只读恢复并确认当前 HEAD 为 `29168e4`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 主线程与两个只读 explorer 核查一致确认：second `S0014 / 14 测控2开入回路图3.dwg` 的 `PW0438 ? -> 505` 与 `PW0440 505 -> ?` 共享 `T1479=505`、同 row band、`bridge_gap=18.75`，属于 `Emergency stop / 调压急停` 元件区域的一条 inline wire split half-chain，不是两个真实普通缺端。
- [x] 实现目标：在 `WireDiagramExtractor` 的 pair 后处理层增加窄范围 inline split continuation 标记，只处理二次原理图内同 sheet/text/value 的互补普通半边、horizontal/grid 线组、同 row band、gap/y delta 合法的场景；命中后保留 pair 证据为 `pair_kind=continuation` / `ordinary_pair_eligible=False`，不改 `pairs.py` 端子 continuation、不调 `line_groups.py` 阈值、不动 rules 主逻辑或 CLI/UI。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_page_extractors.py -k "inline_wire_split or input_matrix or prefixed or ac_phase"` -> `14 passed`
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "complementary or missing_side or continuation"` -> `10 passed, 49 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `276 passed`
  - second fresh `.tmp/phase77_inline_wire_split_second/2_2` + `.tmp/phase77_inline_wire_split_second_audit`: `pair_count=1460`, `issue_count=25`, `R-PAIR-MISSING-SIDE=15`, `continuation=204`。
  - `PW0438` and `PW0440` are now `continuation/review` with `semantic_kind=continuation_inline_wire_split`, `continuation_kind=schematic_inline_wire_split_half_chain`, `covered_by_inline_wire_split_half_chain=True`, `shared_text_id=T1479`, `shared_value=505`, `bridge_gap=18.75`; no `505` issue remains.
  - Guardrails held: `PW0439 505 -> 506` remains `ordinary_pair/discard`; `PW0442 ? -> 501` remains an ordinary missing-side review; `semantic_table_mapping_pass_endpoint_count=0`; `input_matrix_wire_mapping=168`; second `1-21CD58 -> 511`, `3-21CD58 -> 511`, `1-21QD34 -> 1-21n218`, `3-21QD28 -> 3-21n218`, `1-21GD9 -> 1-21n218` remain structured relations.
- [ ] 下一刀候选收缩为：second component vertical `401` mapping upgrade；backplate/component/table mapping rules semantics；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

### Phase 78: Second Component Vertical 401 Endpoint Bridge
- [x] 只读恢复并确认当前 HEAD 为 `e8d9ecd`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 两个只读 explorer 与主线程 parquet 核查一致确认：second `S0020 / 20 元件接线图2.dwg` 的 `PC0077 4 -> 401`、`PC0090 6 -> 401` 是 `FJL-25-2A_Mirror` 双端口块上下端点桥接，真实结构应为 `3-21ZK-4 -> 3-21n401` 与 `1-21ZK-6 -> 1-21n401`，旧 ordinary review 来自派生数字而非图纸问题。
- [x] 实现目标：在 `ComponentDiagramExtractor` 中新增 `strip_two_port_endpoint_bridge` 窄 submode，只接受同前缀 `*-21ZK-#` 顶端点与 `*-21n###` 底端点、上下 pin `1/2`、支撑竖线同时成立的场景；输出直接 `component_mapping/pass`，并用 consumed line group 覆盖旧 ordinary pair。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_component_diagrams.py -k "strip_two_port or endpoint_bridge"` -> `12 passed, 9 deselected`
  - `python -m pytest -q tests\unit\test_page_extractors.py -k "component or inline_wire_split or input_matrix or prefixed"` -> `11 passed, 3 deselected`
  - `python -m pytest -q tests\integration\test_analyze_project.py -k "wire_component or run_audit or terminal_header_table"` -> `2 passed, 18 deselected`
  - `python -m pytest -q` -> `279 passed`
  - second fresh `.tmp/phase78_component_vertical_401_second/2_2` + `.tmp/phase78_component_vertical_401_second_audit`: `pair_count=1462`, `issue_count=23`, `component_mapping=84`；新增 `PCB0001 3-21ZK-4 -> 3-21n401` 与 `PCB0002 1-21ZK-6 -> 1-21n401` 均为 `component_mapping/pass`。
  - `PC0077 4 -> 401` 与 `PC0090 6 -> 401` 均已 `ordinary_pair/discard`，带 `covered_by_component_mapping=True`；`GC0077/GC0090` 不再产生 `401` 相关 issue。
  - first fresh `.tmp/phase78_component_vertical_401_first/...` + `.tmp/phase78_component_vertical_401_first_audit`: `pair_count=1581`, `issue_count=212`, `component_mapping=150`；first KLP/ZLP/218 structured redlines held。
  - 红线保持：`semantic_table_mapping_pass_endpoint_count=0`；second `1-21CD58 -> 511`、`3-21CD58 -> 511`、`1-21QD34 -> 1-21n218`、`3-21QD28 -> 3-21n218`、`1-21GD9 -> 1-21n218` held；first `5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1`、`5KLP5-2 -> 5n307`、`1-2ZLP4-1 -> KD26`、`1-2ZLP4-2 -> 1-2n422` held。
- [ ] 下一刀候选收缩为：backplate/component/table mapping rules semantics；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

### Phase 79: Backplate Scope Review Aggregation
- [x] 只读恢复并确认当前 HEAD 为 `813fed7`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 审计结论：first fresh audit 的最大结构化 rules 噪声是 `R-CROSS-PAGE-CONFLICT=66`，全部为 `table_mapping/review` 背板虚拟表格作用域复用；证据中已有 `one_to_many_classification=backplate_table_scope_review`、`table_mapping_mode=backplate_virtual_table`、`source_block_names`、`header_prefixes`，不应写成 extractor 缺失。
- [x] 实现目标：只在规则聚合 / 诊断层收口，不改 extractor、不移除 `table_mapping` 入图；按 `rule_id + classification + table_mapping_mode + header_prefixes + source_block_names` 聚合背板 cross-page scope review，并把 specialized `R-CROSS-PAGE-CONFLICT` 诊断为 `rule_too_strict`。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "backplate or cross_page"` -> `7 passed, 53 deselected`
  - `python -m pytest -q tests\unit\test_issue_diagnostics.py` -> `3 passed`
  - `python -m pytest -q` -> `281 passed`
  - first rules-only audit `.tmp/phase79_backplate_scope_first_audit`: `issue_count=153`，`R-CROSS-PAGE-CONFLICT=7`，cross-page root cause 全部为 `rule_too_strict`；Phase78 first findings pair_count 保持 `1581`。
  - second rules-only audit `.tmp/phase79_backplate_scope_second_audit`: `issue_count=23`，规则分布保持 `R-PAIR-MISSING-SIDE=15`、`R-ONE-TO-MANY=6`、`R-SEMANTIC-MAPPING-CONFLICT=1`、`R-MANY-TO-ONE=1`；Phase78 second findings pair_count 保持 `1462`。
- [ ] 下一刀候选收缩为：backplate/component/table mapping rules semantics 的剩余同页 / many-to-one / 默认展示口径；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

### Phase 80: Backplate Same-Sheet Scope Review Aggregation
- [x] 只读恢复并确认当前 HEAD 为 `07614f5`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 审计结论：Phase79 后 first `S0021 / 20 非电量保护背板图.dwg` 的 `NKR308A-1..18` 仍以 `backplate_table_same_sheet_scope_review` 行级 review 散开；这是同一 source block、同一表头组、连续行号的同页虚拟表格作用域复用，属于 rules/display 聚合缺口，不是 extractor 缺失。
- [x] 实现目标：只在 `rule_base.cluster_issues()` 聚合同页背板 scope review；按 sheet、source block、header prefix、raw header/header text ids 分簇，并仅合并连续行号范围，保留所有 related pair/evidence。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "backplate or cross_page"` -> `8 passed, 53 deselected`
  - `python -m pytest -q` -> `282 passed`
  - first rules-only audit `.tmp/phase80_backplate_same_sheet_scope_first_audit`: `issue_count=136`，`R-ONE-TO-MANY=24`；`backplate_table_same_sheet_scope_review` 从 `18` 条聚合为 `1` 条，`cluster_size=18`，保留 `36` 个 `cluster_pair_ids`。
  - second rules-only audit `.tmp/phase80_backplate_same_sheet_scope_second_audit`: `issue_count=23` 保持不变；Phase78 findings pair_count 保持 first `1581` / second `1462`。
- [ ] 下一刀候选收缩为：backplate/component/table mapping rules semantics 的 many-to-one/shared endpoint 默认展示分层、terminal header shared endpoint 区间展示、component split endpoint review 展示；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

### Phase 81: Terminal Header Shared Endpoint Interval Evidence
- [x] 只读恢复并确认当前 HEAD 为 `a59a15e`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 审计结论：Phase80 后 second `S0023 / 23 右侧端子图1.dwg` 的 `terminal_header_table_shared_endpoint_review` 已聚合为 1 条，但报告仍以单个 `1-21n210` 表述，未显示真实结构是 `1-21GD1..21` 与 `1-21QD26..46` 共享 `1-21n210..230` 的连续区间。
- [x] 实现目标：只在 `rule_base` 聚合证据和 issue summary/action 中补 terminal header shared endpoint 区间摘要；不改 TableExtractor、TerminalDiagramExtractor、PairBuilder、graph input、规则判定或 CLI/UI。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_pairs_and_rules.py -k "terminal_header_table or backplate or shared_endpoint"` -> `13 passed, 48 deselected`
  - `python -m pytest -q` -> `282 passed`
  - first rules-only audit `.tmp/phase81_terminal_header_interval_first_audit`: `issue_count=136` 保持不变；聚合 terminal-header shared endpoint issue 增加 `aggregated_*_ranges` 和区间化 summary。
  - second rules-only audit `.tmp/phase81_terminal_header_interval_second_audit`: `issue_count=23` 保持不变；`I0062` summary 显示 `logical=1-21GD1..1-21GD21, 1-21QD26..1-21QD46; shared=1-21n210..1-21n230`，recommended action 显示行号区间 `1..21, 26..46`。
- [ ] 下一刀候选收缩为：component split endpoint review 展示、many-to-one/shared endpoint 默认展示分层、backplate/component cross-scope shared endpoint 展示；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

### Phase 82: Component Split Endpoint Review Display
- [x] 只读恢复并确认当前 HEAD 为 `092798c`；工作区仅有受保护未跟踪 `doc/page_findings/`、`doc/page_task_queue.md`，未纳入本轮写集。
- [x] 两个只读 explorer 与主线程 Phase81 产物核查一致确认：first `S0024 / 23 元件接线图3.dwg` 的 `component_split_endpoint_group_review` 已有 `external_endpoint_raw_values`、`external_endpoint_splits`、`external_endpoint_text_ids`、`logical_endpoints` 证据；缺口是报告/UI 只显式展示 `one_to_many_classification`，`R-MANY-TO-ONE` 的 split review 没有同等一等展示字段。
- [x] 实现目标：只在报告与内部 Streamlit UI 展示层透出 `many_to_one_classification` 和统一 `review_classification`，并在 LineSemantics 摘要中显示 `component_submode`、`component_branch_kind`、`shared_endpoint`、`external_endpoint_splits`；不改 extractor、pair graph、rules 判定、issue 聚合或 CLI 产品表面。
- [x] 验证结果：
  - `python -m pytest -q tests\unit\test_report_artifacts.py -k "many_to_one_component_split or evidence_display"` -> `2 passed, 15 deselected`
  - `python -m pytest -q tests\unit\test_ui_app.py -k "classification"` -> `2 passed, 3 deselected`
  - `python -m pytest -q tests\unit\test_report_artifacts.py tests\unit\test_ui_app.py` -> `22 passed`
  - `python -m pytest -q` -> `284 passed`
  - first rules-only audit `.tmp/phase82_component_split_display_first_audit`: `issue_count=136` 保持不变；`component_split_endpoint_group_review=28`，其中 `R-ONE-TO-MANY=16`、`R-MANY-TO-ONE=12`；Markdown 出现 `ReviewClassification`、`OneToManyTriage`、`ManyToOneTriage` 与 split semantics，XLSX `review_classification` 命中 28 行、`many_to_one_classification` 命中 12 行。
  - second rules-only audit `.tmp/phase82_component_split_display_second_audit`: `issue_count=23` 保持不变；`component_split_endpoint_group_review=0`。
  - Phase78 findings pair counts 未漂移：first `pair_count=1581`，second `pair_count=1462`。
- [ ] 下一刀候选收缩为：many-to-one/shared endpoint 默认展示分层、backplate/component cross-scope shared endpoint 展示、acceptance golden 口径；packaged sidecar/exe smoke only as a separate product slice.
- **Status:** complete

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `rg.exe` 启动被 Windows 拒绝访问 | 在 Codex app bundled `rg.exe` 上执行全文检索 | 改用 PowerShell `Select-String` / `Get-ChildItem`，后续本轮不重复同一 `rg` 调用 |
| `Get-Content` 旧路径失败 | 读取 `src\dwg_audit\execution_service.py` / `src\dwg_audit\sidecar.py` | 当前文件已迁到 `src\dwg_audit\services\execution.py` 与 `src\dwg_audit\desktop\sidecar.py`，后续按新路径读取 |
| `Select-Object -Index 740..785` 范围参数失败 | 读取本地 Tauri crate 源码片段 | 改用 `Select-Object -Skip ... -First ...` |
| Tauri `cargo test` 首次失败：`frontendDist` 路径不存在 | 未先生成 `apps/desktop/dist` 时运行 Rust tests | 先执行 `npm run build` 生成 gitignored dist，再跑 cargo test |
| Windows `link.exe` 间歇性 `LNK1104` 无法打开 test exe 输出 | 重跑 `cargo test` 时链接阶段偶发锁定输出路径 | 查无残留进程后立即重试，同命令通过；记录为 Windows target/linker 临时锁竞争 |
| second-set verification helper `KeyError: right` | 用旧 `pairs.parquet` endpoint 列名检查 semantic endpoint rows | 改用当前 schema 的 `left_value/right_value` 重跑，确认 `semantic_table_mapping_pass_endpoint_count=0` |
| `run-audit` 写 `issues.parquet` 时 `ArrowInvalid` | 新增 `row_numbers` evidence 使用整数列表，与既有字符串行号 evidence 混合 | 将新 evidence 的 `row_numbers` 统一为字符串列表并重跑 targeted/full/fresh audit 通过 |
| terminal-header aggregation fresh first audit `TypeError: '<' not supported between instances of 'str' and 'int'` | natural sort key 同时比较数字开头端点和非数字开头字符串 | 将 `_natural_sort_key()` 改为稳定 tuple key 后重跑 targeted/full/fresh audit 通过 |
| Phase71 issue summary helper `KeyError: 'filename'` | 将 `issues.parquet` 与 `pages.parquet` merge 后直接按 `filename` groupby | 改用显式 `filename2/route_target2/sheet_category2` 映射列重跑统计 |
