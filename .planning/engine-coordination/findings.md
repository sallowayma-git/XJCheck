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

## 完善架构的证据复核

- L-11 8项目单worker新旧交替2次，baseline→round7总时间126.15→141.99s（+12.6%），SW抽取/识别自身4.88/6.89s；输出规模不同，不是三引擎独立测速。
- P2行号冲突32/32为V1误读；前缀候选183修正，3670原一致0改坏；这是局部已审计证据，不是总体accuracy。
- LOGGEN-MISMATCH 103856/104390=99.49%为已解析身份与图面文字一致，534无法判定，不能当成SW总体连接正确率。
- V2 round23非SW发射端口4766无配对消费者；生产有95条端子几何绑定和227条panel IGNORE。不能说V2不参与，也不能独立排第一。
- lifecycle.py已实现compact、global和stale清理；Rust force_shutdown先spawn清理再kill写入进程，有并发/锁竞争风险；stale仅mtime，无活动会话锁。
- runs/issue_summaries/page_findings/preview_geometries每run持久保存，LIMIT20只限制显示，旧数据无自动裁剪。退出清DXF不等于SQLite只有一个快照。
- 快照按用户要求默认全库仅最近一次成功分析（一次批量可含多项目）；最近项目仅保留有限轻量路径摘要。新分析失败保留旧成功快照；不引入永久跨run DXF缓存、多代快照或复杂依赖图。

- 现有round25 77份complete与summary小字段重汇总：elapsed项目合计2267.855s，extract1267.787s、recognition548.314s，SW内计时70.178/106.549s。非新实验、非并行总墙钟，不是独立引擎排名。
- 同一回放pairs文件56.44MiB、SW summary59.99MiB、supersession98.59MiB，后两者有重复明细/完整快照，设计收敛为摘要+必要引用。来源仅研发回放，不冒充用户每次空间占用。
- 本机默认desktop_state.db只读：405504字节，runs/sessions/projects/preview_rows均0；当前无本机历史膨胀实测，增长风险由源代码留存策略确认。
- 原有preview快照缺完整增量识别合同，不能直接拿它当重算缓存。实施补齐最小页级关系、作用域ID与依赖版本，再复用；跨页/PCL依赖不明时保守重算项目。
