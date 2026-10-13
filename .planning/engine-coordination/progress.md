# Progress

2026-10-13：开始架构设计，读取仓库 README、SuperWORKS 初始任务书、当前流水线和配置、round25 复核报告。当前设计范围只含架构文档，不动生产实现。

完成两项只读探索与主线程源码点验，形成 doc/engine-coordination.md：共享基础层、SW优先、对象状态与工作枚举、V1/V2能力调度、统一准入、前端投影、性能测量门槛及六阶段落地方案。整合用户“重复结果直接跳过”补充。生产代码与前端未改；未运行实施测试或性能回放。

架构完善：三名只读探子分别核对既有精度/性能证据、退出helper/SQLite生命周期与重复存储；全部返回后主线程点验源码。只读汇总round25时间/产物体积及本机空数据库。更新同一架构稿，明确条件首轮选择、小规模留出/同分母评测、一个协调模块、全库一个当前成功session快照、失败保留旧快照、受依赖约束的页级增量、清理顺序/安全根和数据库物理回收。未删除任何数据，未修改生产代码，不再推送远端。

开发：T0本地7ff8dea，固定baseline Git对象/输入配置，不复制源码；pipeline/workflow阶段计时，集成1项通过。T1实现事务batch、recent轻量20项、旧DB迁移、root OS锁（同时阻止分析与清理，不留每run锁文件）、safe path/输入保护、压缩门槛及退出先停止工作再spawn cleanup。Python26旧项+6新项通过（包含25批次、rollback/incomplete、迁移、活跃锁和源文件保护）；Rust cargo test32通过，tsc与request20通过。第一次cargo --lib不适用bin项目，改cargo test；首次清理测试2项失败因旧fixture把input_root写成临时session，修正fixture为独立输入，并新增真实保护负例。T2共享context/index/groups兼容入口已实现，page/SW/integration220项通过，p000真实回放正在进行。

T1本地236eb53。T2真实p000重放完成：1506→1506，pair_id/sheet/file/group/value/status/kind/confidence/text_ids逐条相同，issue rule/sheet/message相同。实现一个SharedRecognitionContext，缓存route线组和整页TextSpatialIndex及PathBodyChecker，保留旧签名可选参数。未运行完整77回放；T8统一完成。

T2本地0b86813。T3新增native_only首轮入口（延后依赖最终消费状态的wire-route admission），SW数据保留稳定源句柄/几何观察。完整wire可以不依赖legacy Pair；缺一端、完全无元数据和无Pair的确证冲突均有独立观察。旧extract签名默认行为保持；31项定向通过，含5项新协同行为断言。无Pair观察进入最终规则/UI的接线在T6完成，不声称已前端显示。

T4-T6本地6e0492e/28d2511/e997681：native首轮只将完整可靠关系关闭，V1保持完整上下文仅配对目标缺口；已原生覆盖的结构文本不生成重复Pair。p0393357→3101且两项真实多对一问题不变；p0001506→1458，主要减少已覆盖候选，四项numeric partial值补为SW完整身份并保持review。初次试跑发现p000竞争冲突依赖已discard的V1 Pair，已接无Pair观察最终审计后恢复同一冲突对象，另保留原生待审核缺口（不声称为确定图纸错误）。465项定向/集成通过，tsc/request20通过。
T7：当前SQLite原子快照加入压缩typed页事实与最终关系；不保留DXF或历史链。全相同页面无需CAD或关系重识别，项目审计仍重跑；变化页只读取变化页面，跨页关系仍保守项目重算；ID实体计数变化会使suffix重新抽取；XML/PRJ、配置、producer源码及ezdxf版本失效。xref或非production不复用（诊断nested proposal需源DXF）。测试清理后复用/单页/full结果逐项相同、XML/version、坏缓存和25批存储计数通过。Windows真实集成发现log FileHandler占用导致只剩日志目录，修正workflow finally关闭句柄与真实compacted返回，原始输入完整。
独立探子复核发现坏typed/缺字段relation导致失败，改为转换前验证并回退；discard不能吞掉原生gap，review分类与group字段已接入；同一symbol竞争组仍合并展示，但保留每个port/contact独立witness与object_key，避免丢定位。首轮全pytest2193通过1跳过144.25s；后续修正后的全套与实际77/性能仍未完成。
