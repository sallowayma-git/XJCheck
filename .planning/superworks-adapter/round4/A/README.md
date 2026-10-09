# 第四轮 A：规则计数与生产覆盖率（只读分析）

## 1. 规则计数
- 三轮 issue 合计：基线 129，第二轮 3,955，第三轮 792，与任务给出的参考值一致。明细见 `counts.md`。
- 第三轮 `R-SUPERWORKS-CONFLICT` 21 条：冲突对象按（项目, 对象）去重后为 21 个，无重复报告。
  - 原因码：`competing_physical_port_identities` 10，`competing_physical_port_instances` 7，`stale_label_reference` 4。
  - 交接文档写的「冲突对象 10（instances 7 + stale 3）」对不上：漏计了 identities 这一类 10 条，stale 实际为 4。10 无法从当前数据复现。

## 2. 覆盖率定义
- 分母：第三轮 `sw_port_coverage` 中 `eligible==True` 的端口，共 82,680（端子 36,853，装置端子 45,827）。
- 第三轮 F5 的严格覆盖（`round3_f5.py`）：分子为 `consumed`，即存在非 discard 的生产 pair，其 `evidence.superworks.{left,right}.port_ids` 包含该端口，且端口值与该侧值 casefold 相等。结果 47,532（57.49%），与 `round3_f5.json` 一致。
- F5 的「旧链同口径」：端口 `endpoint_identity` 与**同项目任一 status=pass 的非 SW pair** 的值相等即算，不限 sheet、不看坐标。结果 61,810（74.76%）。它用的是第三轮 run 的 pairs，不是基线。并集 70,560（85.34%）。
- 本次采用的统一口径（修改前后相同）：
  - 端口点取 `sw_ports` 的 start/end 中点。SW pair 的侧坐标与该中点一致。
  - 判定：同项目、同 sheet、status!=discard 的 pair，某一侧坐标距端口点 ≤ 2.0，且该侧值规范化后等于逻辑身份；装置端子另允许等于脚号文字。
  - 规范化：strip、去首尾 `&`、去空格、casefold。
  - 对照：只按坐标、不比值。
  - before = 基线 `pairs.parquet`；after = 第三轮 `pairs.parquet`（SW 与保留的旧链 pair 都算）。

## 3. 结果（`coverage.json`）
| 口径 | 修改前（基线） | 修改后（第三轮） |
|---|---|---|
| 严格（坐标+值） | 30,291（36.64%） | 51,872（62.74%） |
| 只按坐标（对照） | 30,355（36.71%） | 51,873（62.74%） |

- 修改后新增被消费的端口：22,020（after 有、before 无）。
- 退化端口（before 消费、after 未消费）：严格 439，只按坐标也是 439。涉及 28 个项目；p041–p044 与 p050 共 283 条，占 64%。
- 逐项目数据见 `coverage.json` 的 `per_project`。

## 4. 退化端口分类（`degraded_ports.csv`）
- A 同位置有非 discard 但值不同的 pair：0。
- B 同位置 pair 为 discard：41（12 个项目）。
- C 被 supersession 记录提及：6。抽查的 p000 三个替代 pair（PW0296/PW0302/PW0306）在最终输出中均为 discard，且不在该端口位置。
- D 在 sw_diagnostics 中：11，原因码均为 `same_logical_identity_other_contact`，即自连接被 F1 切断。这类是预期内的删除。
- E 其他：381。
  - E1 同一符号的兄弟端口：379。该端口仍被线接触，但同一身份值改挂到同符号上另一个同身份端口（多数相距 2.5 或 5.0，少数 100；原端口与新端口均有线接触）。涉及 24 个项目。before 状态 review 318、pass 61；其中 93 条 before pair 为单侧。
  - E4 其他：2（p025，PW0495/PW0588）。
- 其中 before pair 为单侧（另一侧缺失）的退化共 107 条。这类在本口径下仍算消费，需复核口径。

## 5. 对口径的敏感性
- 只按坐标与严格口径退化数相同（439），说明值条件不是退化的来源。
- 旧链侧坐标离端口点的偏差较大：SW 侧 95.7% 在 2.0 内；旧链侧 81.9% 在 2.0 内，18.0%（6,972 侧）落在 2–6 之间。2.0 的阈值对旧链 pair 很敏感。

## 6. 不确定或无法计算
- 退化端口数不是 0，未达到门槛。439 条均已分类，但 E1（379 条）的电气正确性未判定。需要按线组拓扑复核，本次未做。
- 同符号多端口共享脚号文字是普遍现象（70,755 个装置端子中 68,532 个与兄弟端口共享脚号 text handle），不能单独作为判据。
- pair_id 跨 run 不稳定，before/after 的链接用 sheet、line_group_id、值。
- supersession 记录与最终输出不一致（C 类），未逐条核实。
- 交接文档中「冲突对象 10」的来源无法确认。
- 未计算第四轮（无数据）。未渲染图片，未改动 src/。

## 文件
- `counts.md`：规则计数与 R-SUPERWORKS-CONFLICT 核对
- `coverage.json`：定义、总体与逐项目 before/after、退化分类、样例
- `degraded_ports.csv`：439 条退化端口明细
- 脚本：`t1_counts.py`、`t1_write.py`、`t1b.py`、`t1c.py`、`t1d.py`、`t2_coverage.py`、`t2_sem.py`、`t2_move.py`、`t2_diag.py`、`t2_ex.py`、`t2_sharedpin.py`
