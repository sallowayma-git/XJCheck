# Findings

- 旧流水线先执行 V1 各路由完整提取，再用 line_groups/pairs/table_mappings 交给 SW。因此不能仅调整调用顺序。
- 旧任务书要求 V2 保持不变，但本次用户明确要求三引擎协同，本次设计允许改造 V2 的生产适配接口。
- 最新统计：纯 V1 pass 2,027；1,175 全项目无同值 SW 对应；背板行佐证4,047，不等于独立SW完整产出。
- 新设计需分开提取基础几何与识别判定、共享空间索引/基础拓扑，V1/V2按缺口使用。

- 两名只读探子完成：SW 在 extract_superworks_pairs 中依赖旧pair保留/替代逻辑，需拆为独立claims与兼容台账投影；无pair的未知对象也要显式排队。
- 主线程点验：V2 geometry_graph/semantic_attachment/constraint_resolver 是影子证据；production 在 artifacts.py:583 提前返回。但 cad_extract 中 proposal/terminal binding 及 panel IGNORE 已有生产消费，不能说V2全部不参与生产。
- Pair置信度与Issue置信度不同；已识别正确的两个事实仍可能产生真跨页冲突，最终统一审计不能跳过SW pass。
- 默认DEFAULT_CONFIG现在是production，resolve_runtime_profile的无配置函数回退为regression；设计必须通过已有配置明确行为，不凭老报告写“默认全量影子”。
- 前轮报告的 pipeline.py 路径误写成audit子目录；本设计使用真实 src/dwg_audit/pipeline.py 出处。

- 最新用户追问：2.6万条为配对输出，不是代码规则。现有I/J将原输出置discard并留台账，不独立报issue；新设计在调度前跳过完整SW覆盖主张，从源头避免重复结果。
- 未发现desktop正常UI存在“已取代”专门文案；目前该说法主要来自统计报告与内部证据。不以此推断或实施UI删除。
