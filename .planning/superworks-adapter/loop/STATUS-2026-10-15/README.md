# 状态调研：superworks-loop 与对方“引擎协调”工作（2026-10-15）

只读调研。未修改任何已跟踪文件或对方文件，未执行 git commit/push/stash/checkout/reset，未删除目录，未建 worktree（全量测试通过，无需复核 d11d0b3）。唯一新建文件为本 README。会话草稿与中间表放在会话 scratchpad，未入库。

## 0. 结论先行

1. 对方在 d11d0b3 之后做了 24 个提交（22 个未推送），目标是“SuperWORKS 优先、缺口交给 V1/V2、冲突直报、单快照存储、退出清理”。代码路径已经从“V1 全量 + SW 后处理”改为“SW 原生首轮 + V1 只补未覆盖线组 + 统一审计”。
2. 工程层面成绩真实：HEAD（2594dbe）全量测试 2208 passed / 1 skipped；77 项目同机单 worker 交错回放，项目耗时中位数 21.00s → 18.14s（-13.6%），P95 -10.7%，性能门槛通过。
3. 但识别口径发生了实质变化，且对方文档声称的“77 项目关系逐条核对”尚未完成：
   - issue 从 38 增至 33,652，其中 33,602 条为新规则 R-RECOGNITION-GAP（review）。r25 的 38 条全部保留，无丢失。
   - 纯 V1 pass 从 2,027 增至 2,452（+425）。这 425 条在 r25 中被 SW 取代台账记录为 validated_superworks_replacement，现在与 SW 替代配对同时为 pass（双 pass 并存）。这与我们 P1/P3 的“取代”口径直接冲突，需要图面核验和裁决。
   - 覆盖率（严格、剔除装置内部）81.99% → 83.50%。分解：852 个新覆盖端口几乎全部由 SW 的 review 级配对覆盖（846 个 review、6 个 pass），pass 口径基本不变；513 个原先被静默剔除的装置端子因前缀补全后身份匹配，转为被 review 配对覆盖（贡献约 0.14 pp）。覆盖率提升主要来自 review 级覆盖，不宜当作“识别变准”的证据。
4. 我们的 P2（背板佐证 4,047）、J 类（32）、G-1（GND 合法）、叠放取最晚、跨符号拦截、导线断开等规则代码仍在，计数未变。但 I 类取代台账（28,481 → 22,103）和 A 类（59,433 → 93,781）含义已变：对方改为“已覆盖目标不生成 V1 配对”，不再生成后取代。
5. 我们 active_issues 的 G1T、WIRE-BREAK 未实现形态（T7/T8/T11）、GAP-2b、PIN-1、DC/DC、p057 等在本轮 diff 中均无改动，仍为待办。P4（设备前缀）被部分实现（28d2511 的 fixed identity 归一化，1,389 条配对）但未经用户裁决。
6. 建议：先不合并、不推送、不以 T8 通过为前提，先由用户裁决 4 个口径问题（见第 7 节），再决定是否继续对方的 T8 和我们的 loop。无需重跑 77 项目全量：对方的 current 输出已可直接核验（见第 8 节）。

## 1. 范围与方法

| 项 | 内容 |
|---|---|
| 分支与提交 | superworks-loop；d11d0b3..HEAD 共 24 提交（HEAD 2594dbe），`origin/superworks-loop..HEAD` 为 22 个未推送 |
| 对方工作区状态 | 未提交：`.planning/engine-coordination/progress.md`、`task_plan.md` 修改；未跟踪：`doc/engine-coordination-acceptance.md`、`.planning/engine-coordination/{acceptance,archive,compare}.py`、各 comparison json、`__pycache__` |
| 代码基线核对 | 对方 `engine_coordination_full_acceptance/base/code_manifest.json` 与 round25 清单完全一致，即 base = 我们的 round25 代码；current 清单与工作区文件字节一致，且工作区与 HEAD 无差异（仅换行符），故 current 回放即 2594dbe |
| 回放产物对比 | `.tmp/superworks_round25_full`（77 项目，issue 38）对 `.tmp/engine_coordination_full_acceptance/current`（77 项目，2594dbe）。逐项目比较 issues.json、pairs.parquet、sw_port_coverage.parquet、superworks_summary.json、superworks_supersession.parquet |
| 台账与普查 | 复用 `loop/LEGACY-ROUND25/census.py`，`--out` 指向 scratchpad，重算 r25 与 current 的纯 V1 / 背板佐证 / 取代分布 |
| 测试 | `python -m pytest tests -q -p no:cacheprovider`（全量，含 integration） |
| 未做 | 未运行 Rust cargo test、未运行前端 tsc；未做 DXF 图面核验（所有“疑似”结论均标注为待核验） |

复现注意：本终端工具输出对中文显示为乱码，数据本身为 UTF-8（已用 unicode escape 核对）。运行 Python 时用 `PYTHONIOENCODING=utf-8 python -I`。

## 2. 对方提交分组（d11d0b3..HEAD）

| 组 | 提交 | 做了什么 | 为什么 | 主要文件 |
|---|---|---|---|---|
| A 设计与基线 | f9b9770, a507ebd, 578dc22, 7ff8dea | 设计稿 `doc/engine-coordination.md`；基线冻结（baseline.json）；阶段计时；round25 普查重算（LEGACY-ROUND25） | 先证明“重复计算”的存在与成本，再设计调度 | doc/, .planning/engine-coordination/, pipeline.py（计时）, services/execution.py |
| B 共享基础 | 0b86813, b62b2f7, 11a6384 | 线组与文字空间索引、路径体检查器共享（SharedRecognitionContext）；CAD 共享成本与 V2 边际成本分开计量；production 不再遍历未消费的 canonical 影子场景 | 消除重复构建；首次 8 项目 perf gate 未通过，定位到 production 仍遍历未消费的影子场景 | audit/recognition_coordinator.py（新）, extract/cad_extract.py, pipeline.py |
| C 原生优先识别 | c6135f9, 6e0492e, 875ebf4, 29f7b5c | SW 独立解析原生关系（native_only），不依赖 V1 pair；V1 只对未闭合线组（target_line_group_ids）出候选；已覆盖的 component/table 产出前门禁（ScopedPairIds.admit）；按原生事实分派，保留权威端点身份 | 设计 §6：SW 完整解决的关系不再交给 V1/V2 | superworks_extractor.py, page_extractors.py, wire_components.py, component_diagrams.py, table_extractor.py, pairs.py, pipeline.py |
| D 判定与准入 | 28d2511, a8e9e5a | V2 复用已准入几何绑定；UNKNOWN/机器提议不得晋升；fixed SW identity 归一化（`fixed_fact_normalizations`）；固定身份冲突保留见证 | 设计 §7 统一判定 | recognition_coordinator.py（finalize_evidence）, rules.py（高置信资格排除 INCOMPLETE/AMBIGUOUS/CONFLICT/EXCLUDED 等） |
| E 缺口与审计呈现 | e997681, e864c63, 432754a | 无 Pair 的原生冲突与缺口进入问题（R-SUPERWORKS-CONFLICT / R-RECOGNITION-GAP，review），按页分组，每个物理见证保留；artifacts 落盘 sw_resolution_observations | 设计 §5 状态机；“不静默丢弃原生缺口” | recognition_coordinator.py（build_resolution_issues）, issue_triage.py, report/*.py |
| F 归属与所有权修正 | f9de76c, 1b0520d, 2594dbe | 原生 reconcile 与线索 map 限定到源文件（file_id, sheet_id, handle），修复跨文件同句柄遮蔽 5 个 SW pass；定义级 pin 按具体原生实例认领（104 条虚拟针脚重复）；物理插槽所有权；拒绝仅轮廓端口提升 | 8×3 与 77 项目探针发现的回归 | superworks_extractor.py, recognition_coordinator.py, pairs.py, page_extractors.py, table_extractor.py |
| G 存储/桌面/前端 | 236eb53, 9605b23, 14f6102, 68386f4, d8c5648, 11a6384（计时部分） | SQLite 原子提交一个完整成功 session；失败/取消/空批保留旧快照；最近项目 20 条轻量记录；退出先停工作再清理（OS 锁保护）；页事实与关系指纹增量复用；前端显示 incomplete；无 Pair 原生端口 overlay | 设计 §13 单快照与清理 | desktop/state_store.py, lifecycle.py, sidecar.py, apps/desktop/src/App.tsx, preview.py |

逐提交要点：
- 2594dbe：`_promote_xjdz_structural_component_pairs` 的门控改为仅 {native_pin, external_endpoint} 才提升；物理插槽归属。
- 1b0520d：`recognition_coordinator.py` 对定义级虚拟针脚按具体实例句柄认领，阻止与之重复的 V1 Pair/Candidate 构造（+27 行）。
- f9de76c：原生 reconcile 的 key 改为 (file_id, sheet_id, handle)，修复同名句柄跨文件碰撞。
- 28d2511：finalize_evidence 对 partial SW 侧按固定身份归一化，例如 `928 → 1n928`、`10 → FZJ5-10`、`15 → TF115`（1,389 条）。这是我们 active_issues 中“P4 设备前缀（待定）”的实现。
- e997681：`R-RECOGNITION-GAP` 进入 issue_triage 默认 handling=review。
- 11a6384：production 不再构建 canonical 影子场景；`_write_production_core_artifacts` 提前返回，故不影响生产产物（已核对代码）。

## 3. 对方架构与规划（SW 优先选择性协调）

设计（doc/engine-coordination.md，§1–§13）：
- 调度单位是端口、导线关系、元件实例端口、表格物理行和局部网络，不是整页。
- 首轮能力选择：有可核验原生语义的对象先由 SW 解析；无原生语义或不完整对象由 V1 局部补证；V2 只在端口/网络几何缺口时局部调用（准入合同 + 正反例）。不靠引擎名称排固定名次。
- 状态机：RESOLVED / CONFIRMED_CONFLICT / INCOMPLETE / AMBIGUOUS / EXCLUDED / ENGINE_FAILURE。确证冲突直报；未解析交补证；补不出则待审核。
- 统一判定：固定 SW 身份不被改写；多主张需同一物理对象才合并；不比较引擎分数。
- “被取代”：SW 已完整解决的关系不生成旧 pair；不再产生“已取代”台账行（设计 §8）。
- 验收门槛（§10–§12）：同机新旧交替至少 3 次，中位数与加权总时间不高于基线，P95 增幅 ≤5%；77 项目逐条核对纯 V1 2,027 与背板 4,047；问题数量变化逐条解释；覆盖与耗时同时验证。
- 存储（§13）：一个当前成功快照、失败保留旧快照、退出清理的安全根与 OS 锁。

进度（对方 task_plan/progress 与 acceptance 文档，截至其最新未提交版本）：
| 任务 | 状态 | 备注 |
|---|---|---|
| T0–T7 | complete | T7 增量复用已提交（14f6102） |
| T8 综合验证 | in_progress | 8 项目 3 轮门槛通过（19.44→16.08s 中位数）；77 项目性能交错回放已完成且 passed=true；77 项目关系逐条核对“待完成”；最终验收提交与摘要索引“待完成”；`full-comparison.json` 为 23:33 旧版本，已过时 |
| 全套测试 | 2208 passed / 1 skipped（HEAD 复跑一致） | doc 中“2,208”与本次一致 |

对方文档中仍写着：“新增原生缺口是待审核事项，不把它们统计为确证图纸错误”。但本轮 77 项目 33,602 条缺口的规模，doc 未给出数量级说明。

## 4. 验证现状

### 4.1 测试

- `python -m pytest tests -q -p no:cacheprovider`（HEAD 2594dbe，全量含 integration）：**2208 passed, 1 skipped，40.88 s，0 failures**。
- 我们 d11d0b3 记录为 2170 passed，本次为 2208 passed（增加 38）。无失败，故未建 worktree 复核。

### 4.2 性能（77 项目，workers=1，逐项目交错，base=round25 代码，current=2594dbe，同一冻结 DXF 缓存）

| 指标 | base | current | 变化 |
|---|---:|---:|---:|
| 项目耗时中位数 | 21.004 s | 18.139 s | -13.6% |
| 项目耗时合计 | 1,507.9 s | 1,295.4 s | -14.1% |
| 项目 P95 | 31.68 s | 28.29 s | -10.7% |

来源：`.tmp/engine_coordination_full_acceptance/full_performance.json`（passed=true）。8 项目 3 轮门槛另见 `.tmp/engine_coordination_perf_acceptance/performance_gate.json`。注意：这是冻结 DXF 的识别阶段对比，不是端到端含 ODA 转换的计时；且 ODA 冷转换未测。

### 4.3 回放结果对比（77 项目）

Issue 数量（按 项目+rule+sheet+message 多重集比较）：

| 规则 | r25 | current | 说明 |
|---|---:|---:|---|
| 总计 | 38 | 33,652 | |
| R-SUPERWORKS-CONFLICT | 17 | 25 | +8，见 5.3 |
| R-PAIR-LOW-CONFIDENCE | 13 | 17 | +4（p061 S0025），见 5.4 |
| R-PAIR-MISSING-SIDE | 4 | 4 | 与设计 §12 要求一致（p041–p044） |
| R-MANY-TO-ONE | 3 | 3 | 含 p039 两条、p040 一条 |
| R-CROSS-PAGE-CONFLICT | 1 | 1 | |
| R-RECOGNITION-GAP（新） | 0 | 33,602 | 全部 review，见 5.1 |

r25 的 38 条 issue 全部保留（无丢失）。

Pairs（178,832 → 172,733）：

| 状态 | r25 | current | Δ |
|---|---:|---:|---:|
| pass | 79,125 | 79,550 | +425 |
| review | 26,997 | 27,045 | +48 |
| discard | 72,710 | 66,138 | -6,572 |

按类型：wire_component_mapping 43,274 → 36,869（-6,405，多为不再生成的旧 discard）；component_mapping 28,312 → 28,737（+425 新增 lattice pass）；ordinary_pair 44,629 → 44,521；continuation 11,960 → 11,949；table_mapping 36,366、semantic_mapping 8,656、bridge_mapping 5,635 不变。

覆盖率（按 `coverage_views`，77 项目合计）：

| 口径 | r25 | current | Δ |
|---|---:|---:|---:|
| 严格 | 62.84%（51,957/82,680） | 64.49%（53,322/82,680） | +1.65 pp |
| 含延续 | 71.42%（59,051） | 73.07%（60,416） | +1.65 pp |
| 剔除装置内部 严格 | 81.99%（51,957/63,373） | 83.50%（53,322/63,857） | +1.51 pp |
| 剔除装置内部 含延续 | 84.40%（53,487/63,373） | 85.86%（54,826/63,857） | +1.46 pp |

分解（逐端口，同一 eligible 集合）：未覆盖转为覆盖 852 个端口，其中 846 个由 SW review 级配对覆盖、6 个由 SW pass 覆盖；装置内部剔除转为覆盖 513 个；未覆盖转为装置内部剔除 29 个；分母净增 484 = 513 − 29。r25 的 81.99%/84.40% 已复现，口径无误。逐步计算：513 端口的影响约 +0.14 pp，852 端口的影响约 +1.33 pp。

纯 V1 与背板佐证（重算 LEGACY-ROUND25 census.py）：

| 指标 | r25 | current |
|---|---:|---:|
| 纯 V1 pass | 2,027 | 2,452（+425） |
| 其中无同值 SW 对应 | 1,175 | 1,597 |
| 其中同页 SW 非 pass | 640 | 643 |
| 其中仅其他页 SW 对应 | 212 | 212 |
| 背板佐证 | 4,047（同页 3,612 + 其他页 435） | 4,047 |
| 台账 I / J | 28,481 / 32 | 22,103 / 32 |

r25 的 2,027 条纯 V1 pass 按（项目、sheet、左右值、文字 ID）全部在 current 中保留，零丢失；但 pair_id 有 1,381 条重编号（字段不变）。

台账分类（superworks_supersession）：A 59,433 → 93,781；B 10,270 → 4,125；C 25,657 → 70；F 4,373 → 0；I 28,481 → 22,103；D/E/G/H/J 不变。分类定义见 superworks_extractor.py `_category`（A 无旧配对，B 端点不同，C 文字 ID 相同但值不同，F 仅元数据不同，I 为同页重复旧配对）。

### 4.4 与对方自带对比文件的差异

`.planning/engine-coordination/full-comparison.json`（23:33 版本）：new_pairs 172,940、protected 2027/4047 逐条相同、missing_issues 0、changes 0；其 unaccounted 104 条正是 1b0520d 修复的虚拟针脚重复。该文件早于最终版本，不能代表 current。最终 77 项目对比应在最终代码上重跑 compare.py。

## 5. 口径变化清单（逐项）

### 5.1 新增原生缺口 R-RECOGNITION-GAP：33,602 条（review）【重大】

- 来源：`build_resolution_issues`，对 INCOMPLETE / AMBIGUOUS 且未被线组覆盖的原生观察生成。
- 分布：INCOMPLETE 33,391，AMBIGUOUS 211。端点侧别：双端 22,558，仅左 6,099，仅右 4,945。
- 原因码：unresolved_endpoint_identity + unresolved_pin_text 20,084；endpoint_identity_missing 9,079；missing_label_reference 类 4,091；same_logical_identity_other_contact 209；unresolved_pin_text 136；其他 3。
- 每项目 10–793 条；23 个 review 分组；`handling_class=review`，不计为确证错误。
- 与我们的关系：这正是 PIN-S / Pop-S（图面大多无脚号，决定“不接入”）与 GAP-1 未登记块引脚的一类对象。此前它们静默留在覆盖分母中，现在以 review 报出。
- 问题：我们的循环原则是“只允许减少误报、不得删除真实问题”，fail-closed，issue 长期保持 38–41。33k 条 review 会淹没真正的待审核项，并改变前端问题列表的体验。这需要用户裁决：是进入正式问题计数，还是作为覆盖缺口清单独立展示。

### 5.2 装置内部剔除 → 覆盖（513 端口）【口径变化】

- 513 个 “装置端子” 类端口原为 excluded_device_internal=True，现为 device_internal_overruled=True 且 consumed=True。
- 覆盖它们的是 SW 来源的 review 配对（source=superworks），例如 p000 S0007 端口 `SW:F0007:S0007:/1AD4C:...` 的 V1 配对 `928` 在 r25 为 review 且不匹配端口身份，current 变为 `1n928`（由 28d2511 的 fixed identity 归一化引起），因而匹配端口身份。
- 影响：分子与分母各 +513，对严格剔除装置内部覆盖率的影响约 +0.14 pp。这是“身份匹配导致的覆盖”，不是“装置内部连接被推翻”。规则 DEV-INT-DISCARD 本身未改，且仍报告 link_count 19,813 不变。
- 需裁决：装置端子既有内部连接又有外部 SW 配对时，是否应以外部配对为准（overrule）。我们此前 DEV-INT-DISCARD 的口径是“静默丢弃，并从分母剔除”。

### 5.3 SW 冲突新增 8 条：疑似嵌套路径重复计数【待核验，可能误报】

- 位置：p041–p044 的 S0012/S0013，reason=competing_physical_port_instances，state=CONFIRMED_CONFLICT。
- 竞争对象为 `SW:F0012:S0012:/2F60B` 与 `.../2F60B/2F324`（父块与子块嵌套实例）。两侧候选端口中出现相同句柄与端口号 `1B9EA:1`，分别以符号路径 `/2F60B` 与 `/2F60B/2F324` 出现。
- 推断：同一个嵌套子块端口被父、子两种路径各计一次，形成“竞争”。这是待核验假设，未经 DXF 验证。1b0520d 引入“具体实例认领”，可能与此相关。
- 建议：用 p041 S0012 的两个 observation 做图面核验；若属重复，则应在 `_competing_object_id` / 候选去重处修复。

### 5.4 低置信新增 4 条（p061 S0025）【待查】

- V1 ordinary_pair：11↔8（3 条，置信 0.903）、9↔9（1 条，置信 0.809），r25 中同端值配对完全不存在。
- 推断机制：C 类产出（component/table 前置门禁）跳过后，原被占用的线组被释放给普通配对。未验证。

### 5.5 425 条新增 V1 lattice pass，撤销 r25 的取代结论【重大，需裁决】

- 这 425 条是 component_mapping / terminal_strip_lattice，pass，无 SW 字段。
- 它们的文字端点键与 r25 台账中被取代的旧配对 **425/425 完全一致**。r25 台账对每条都记录为 validated_superworks_replacement（B 类，850 条台账行）。
- 这 850 条台账行对应的 SW 替代配对在 current 中全部仍为 pass，因此同一对端子上出现两个 pass 主张，且左端不同（例：`1n2001 ↔ 1UD1`（V1，新增）与 `TF-2 ↔ 1UD1`（SW，保留））。
- 对方将其解释为“保留 terminal-strip 整行跨行关系，不当作同一端口”（progress.md 未提交部分）。该解释与 r25 的 B 类取代结论相反，且 doc 中没有给出图面证据。
- 设计 §7 要求：下游 V1 主张与可靠 SW 事实冲突时拒绝该候选，不能双存。这里 SW 身份是固定的。
- 注意：仅凭“端子已有他人 pass”不能判定错误，因为 r25 中约 60% 的 pass 配对本来就共享端点文字（基线 59.88%，current 60.09%）。关键差异是 r25 明确做过取代判定。
- 需要：对 3–5 例做图面核验（优先 p016 S0021 的 1n2001/1UD1、1n2003/1UD2、1n2005/1UD3），确定哪一个是真实连接，再决定恢复取代或保留双主张并报冲突。

### 5.6 P4 设备前缀（部分实现，未经裁决）

- 28d2511 的 fixed identity 归一化（`fixed_fact_normalizations`）影响 1,389 条配对，例如 `417 → 1n417`、`432 → 3-2n432`、`10 → FZJ5-10`、`15 → TF115`。
- 本轮 pairs 变化中约 1,300 条属于此类（前缀/后缀匹配的近似统计）。
- 这是我们 active_issues 中 P4 “待定”的实现，但改动已入库，尚未经用户口径确认。

### 5.7 我们其他口径：规则仍在，计数不变或语义变化

| 我们的口径 | 本轮代码/结果 | 判断 |
|---|---|---|
| 装置内部静默丢弃并剔分母（DEV-INT-DISCARD） | 规则与 device_internal_discard 仍在；link_count 19,813 不变；excluded 19,307 → 18,823 | 口径部分改变，见 5.2 |
| 导线在符号处断开（WIRE-BREAK，线组层） | line_groups.py、superworks_device_internal.py 未改；coordinator 复用线组；symbol_cut_group_ids 仍被调用 | 未改（对方称 p000 逐条一致） |
| 叠放文字取最晚（OVERLAP） | “检测到文字重叠”与最晚规则代码仍在，未改 | 未改 |
| GND 公共地合法（G-1） | GND 相关代码仍在；R-MANY-TO-ONE 仍为 3 | 未改 |
| 背板佐证与 J 类 | 4,047 不变；J 32 不变 | 未改 |
| V1 去重 I 类（P1） | I 28,481 → 22,103；对方改为“已覆盖目标不生成 V1 配对” | 机制改变（由生成后取代改为不生成），台账语义变化 |
| 跨符号拦截（P3） | path_checkers 仍传入 build_terminal_candidates；wire_components 增加 admit 门禁 | 未改语义，增加门禁 |
| 高置信资格（rules.py） | `_high_confidence_source_eligible` 新增 recognition_state 排除（INCOMPLETE/AMBIGUOUS/CONFLICT/ENGINE_FAILURE/EXCLUDED） | 新增规则收紧，需确认其影响范围 |

## 6. 与我们 active_issues 未完成项的重叠与冲突

| 事项（active_issues） | 与对方改动的关系 | 状态 |
|---|---|---|
| G1T 端子排竖向轨线不作 T 接 | 本轮无命中 | 未动，仍待定 |
| L-20 低置信（候选阶段看不到 SW 补充线组） | 无改动；但 p061 S0025 新增 4 条低置信 | 未动；新增待查（5.4） |
| GAP-2b 开口端（972，装置端子多端线组） | 无改动；原生缺口 review 中可能包含其中一部分，但未核对 | 未解决，未核对是否被纳入 33k 中 |
| WIRE-BREAK 未实现 T7 框线穿越 / T8 T 接止于间隙 / T11 空白端 | 无改动 | 未动 |
| PIN-1 Pop-X 升 pass | 无改动（diff 无 Pop-X 相关） | 未动；R-RECOGNITION-GAP 是否与 Pop 类对象重叠未核对 |
| P4 设备前缀 | 部分由 28d2511 实现（5.6） | 被改变，待裁决 |
| p057 95 条模板前缀候选 | p057 pass 630 与表格 pass 223 不变，无命中 | 未动 |
| DC/DC 模块口径 | 无命中 | 未动 |
| V1 降级评估 | 未动；但纯 V1 集合 2,027 → 2,452（5.5） | 需要用新数字更新评估 |
| P1 去重（I 类取代 26,437） | 数字已变（I 22,103，A 93,781）；与 5.5 的双 pass 冲突 | 需要重算 |
| PIN-S / PIN-M5 等“不接入”结论 | 原生缺口以 review 报出（5.1） | 口径改变，需用户确认 |

## 7. 风险与需要裁决的问题（按优先级）

1. R-RECOGNITION-GAP 33,602 条是否进入正式 issue 计数（5.1）。
2. 425 条 V1 lattice 与 SW 替代双 pass 并存（5.5）。需图面核验后裁决：恢复取代，或保留双主张并报冲突。
3. 513 个装置端口的 overrule 是否允许（5.2）；以及 28d2511 的前缀归一化（P4）是否获批（5.6）。覆盖率 +1.5 pp 中，约 0.14 pp 来自 513 端口的 overrule，约 1.33 pp 来自 852 个新覆盖端口（几乎全为 SW review 级配对）。两者都应由用户确认口径，覆盖率不宜单独作为改进依据。
4. 8 条新增 SW 冲突是否为嵌套路径的重复计数（5.3）。若是，属于误报，应修。
5. p061 S0025 的 4 条新增低置信（5.4）：机制未知。
6. pair_id 重编号：纯 V1 集合中 1,381 条 pair_id 变化。若前端、已保存会话或引用依赖 pair_id，需核对（设计 §4 要求稳定 ID）。
7. 对方验收未闭合：77 项目关系最终对比待完成；最终验收提交与摘要索引待完成；full-comparison.json 已过时。
8. 本地未推送：对方 22 个提交；若后续推送分支，需先协调，不宜与我们的提交混推。
9. 未验证项：Rust cargo test、tsc、桌面端实际展示 33k 条 review 的体验与性能。

## 8. 建议（如何推进）

1. 不合并、不推送、不把 T8 标为通过。先给用户四个裁决点：R-RECOGNITION-GAP 的呈现方式（5.1）；425 条双 pass 的取代规则（5.5）；装置端口 overrule 与前缀归一化（5.2、5.6）；8 条 SW 冲突是否属于误报（5.3）。
2. 不需要重跑 77 项目全量。`.tmp/engine_coordination_full_acceptance/current` 已是 2594dbe 的完整 77 项目输出，可直接用于核验。如需复核，只做以下两件事：（a）在该目录上重跑 `LEGACY-ROUND25/census.py` 并保存到 `LEGACY-ROUND25/results-current/`，作为我们的新口径证据；（b）对 5.5 与 5.3 各抽 3–5 例做 DXF 截图核验（沿用 loop 既有的截图做法，输出放在我们自己的目录，不写入对方的 .tmp 目录）。
3. 若用户同意以对方代码为新基线，应在我们的 active_issues 中增加“对方改动影响”章节，把 P1、P3、P4、DEV-INT、PIN-S 的数字更新到 current，并把 round25 保留为对照基线。
4. 与对方的协调：请对方（a）完成 77 项目最终 compare.py 并替换过时的 full-comparison.json；（b）在 doc 中补充 33,602 条缺口的数量说明与 5.5 的解释；（c）对 8 条新增 SW 冲突和 p061 新增低置信给出机制说明。
5. 我们的 G1T、WIRE-BREAK T7/T8/T11、GAP-2b、PIN-1、DC/DC、p057 在本轮无改动，可以按原计划继续，但需在 5.1 决策后重新排优先级（GAP-2b 与 R-RECOGNITION-GAP 可能重叠）。
6. 本地分支纪律：对方的 22 个提交与我们的 d11d0b3 同在 superworks-loop。后续提交应区分范围，避免与对方未提交的 .planning/engine-coordination 文件冲突。

## 9. 附：关键证据位置与复现

- 对方设计：`doc/engine-coordination.md`（§1–§13）；验收草稿：`doc/engine-coordination-acceptance.md`（未跟踪）。
- 对方进度：`.planning/engine-coordination/progress.md`（含未提交尾部）、`task_plan.md`。
- 77 项目 current 产物：`.tmp/engine_coordination_full_acceptance/current/`（base 为 round25 代码的同机对照）；性能：`full_performance.json`。
- 8 项目门槛：`.tmp/engine_coordination_perf_acceptance/performance_gate.json`。
- 测试：`python -m pytest tests -q -p no:cacheprovider`（HEAD 2208 passed, 1 skipped）。
- 普查复现：`python -X utf8 .planning/superworks-adapter/loop/LEGACY-ROUND25/census.py --run .tmp/engine_coordination_full_acceptance/current --out <输出目录>`（本次输出在 scratchpad）。
- 对方核心代码：`src/dwg_audit/audit/recognition_coordinator.py`（新增 269 行，含 finalize_evidence 与 build_resolution_issues）；`src/dwg_audit/pipeline.py` 约 L279–L420（native-first 主流程）；`src/dwg_audit/audit/superworks_extractor.py` 的 `_category`（台账分类）、`_discard_device_internal_pairs`（装置内部丢弃）。
