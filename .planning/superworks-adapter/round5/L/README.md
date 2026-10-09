# 第五轮 L：同实例同名标签不作端口身份（L1）与端子排 `&` 跨接（L2）

范围：修改 `src/dwg_audit/extract/superworks_semantics.py`（L1）与新增 `tests/unit/test_superworks_round5_producer.py`。未改 rules.py、series_chains.py 或其他文件；未提交、未删除、未全量回放。快照：`.planning/superworks-adapter/round5L_src`（L1 实施后的 src 副本，含同期其他子代理未完成的 rules.py 改动）；对照快照 `.tmp/round5L_ctrl_src`（同一快照，仅注释掉 L1 撤销步骤）。

## 1. L1 实施

- 函数：`dwg_audit.extract.superworks_semantics._definition_ports`。
- 位置：nearest 候选选定之后、距离与共享文字判定之前。
- 规则：同一定义实例内，若干端口采纳了规范化后相同的标签值，且这些端口来自 >=2 个不同文字实体（handle），则撤销这些端口的 nearest 采纳，它们回落为端口号；结果记为 `{"resolved": False, "nearest_rejected": {"handle", "distance", "reason": "same_value_distinct_text"}}`。
- 保留：同一文字实体被多端口共用（shared-terminal，如 DC）时不撤销。
- 附带：原有 bound 拒绝记录新增 `reason: "nearest_bound"`（纯增量字段）。
- 通用规则，无块名或值特判。

## 2. L1 测试

`tests/unit/test_superworks_round5_producer.py`（4 项）：
- 三端口各有独立同名文字「B码1+」（距离 7.0）：回落端口号，reason 为 same_value_distinct_text；
- 三个不同名文字：全部保留 nearest 采纳；
- 同一 DC 文字被两端口共用：保持采纳；
- 同一块的两个实例互不影响（按实例撤销）。

## 3. L1 探测（replay.py，snapshot round5L_src，控制组为同快照去掉撤销）

| 项目 | 对照（控制组，等同 r4） | L1 | 说明 |
|---|---|---|---|
| p075 pairs | 2334 | 2330 | 去掉 196 条 `1-26n-B码*` component_mapping，新增 192 条 `1-26n401` 等端口号身份（与 wire_component_mapping 一致）；component_mapping 中 B码 身份为 0 |
| p075 R-ONE-TO-MANY | 64 | 0 | 目标达成 |
| p075 R-PAIR-MISSING-SIDE / R-MANY-TO-ONE | 70 / 1 | 70 / 1 | 不变 |
| p024 pairs | 1842 | 1712 | 去掉 130 条 component_mapping（如 1n-01→1XD3、1n-02→1XD7），无替代 |
| p024 component_mapping | 249 | 119 | r3 也是 249，即 L1 使 p024 比 r3、r4 少 130 条 |
| p038 pairs | 2474 | 2284 | 去掉 190 条 component_mapping（如 1-2n-10→…），无替代 |
| p038 component_mapping | 357 | 167 | r3 也是 357 |
| p000 pairs（对比 r4 全量，未跑对照） | 1351 | 1283 | 去掉 76、新增 8；如 1n-25→1YD4 变为 K861-2X3→4XD4 类端口号身份 |

结论与风险（需父代理决策）：
- 对 p075 的 B码 问题，L1 达到目标。
- 对 p024、p038（背板表格型图，同一行号标签如 "1n-02" 同时挂在多个端口上）：L1 撤销后这些端口不产生 component_mapping，共损失 320 条（p024 130、p038 190），损失的右端子中，p024 的 130 个损失右端子中有 32 个在所有 pair 类型中都不再出现，其余 98 个仍由其他类型 pair 覆盖；p038 的 176 个损失右端子中有 22 个同样不再出现。这一损失不是“与第三轮行为一致”，因为 r3 同样保留这些对。
- 因此 L1 不是纯精度修复：它把“身份不唯一”的端口从 component 映射中移除，同时没有给它们提供端口号级的替代身份。是否接受这一召回损失，或需要为背板类（同名行号标签、多列端口）补充端口号+列的身份，请父代理决定，我未擅自扩大规则。

## 4. L1 受影响面估计（r4 全量数据，近似）

- 方法：以 `sw_ports` 与 `sw_part_instances.ports` 中 pin.resolution_method == definition_text_nearest 的端口，按 (file_id, instance_path, 标签规范值) 分组；>=2 端口且 >=2 个不同 handle 即计为受影响组。
- 结果：77 个项目中 nearest 采纳端口 54,174 个；受影响组 5,511 个，涉及端口 35,388 个（约 65%），分布于 76 个项目。端口数最多：p027 1124、p064 872、p025 868、p026 868、p061 784、p032/p033/p034 各 680。
- 这是端口层面估计，不是 pair 层面。探测显示 pair 层面变化远小于端口数（如 p000 仅 -76/+8），但 p024、p038 的 component_mapping 损失显著。
- 近似误差：实例按 instance_path 分组，嵌套定义可能合并或分拆。

## 5. L2 数据核实（未实施）

- 原始值以 & 开头的连接文字数（sw_strip_rows.connections，77 项目共 20,806 条连接项）：0。
- 字段 `dxlx`（LD_DZPNO_DXLX / LD_CIRCUIT_DXLX 属性）值为 "&" 的行有 1,992 条，这是属性值而非连接文字。
- 原始 DXF 缓存（.tmp/superworks_round4_full/*/cache/converted_dxf）中以 & 开头的 TEXT/MTEXT 共 5,601 个，分布于 392 个文件，例如 "& 1QD1,1n431"、"& 7UD1"、"& ZD8"。
- 身份核实：去掉 & 并规范化后，整值属于本项目 sw_strip_rows.endpoint_identity 的为 1,674 / 5,601 = 29.9%，远低于 90%。
- 样例（p000 F0014，前 12 个中的 10 个）：
  - "& 1QD12" → 1QD12 命中
  - "& 1QD13" → 1QD13 命中
  - "& 7UD1" → 7UD1 命中
  - "& 7UD3" → 7UD3 命中
  - "& 7UD17" → 7UD17 命中
  - "& 7UD5" → 7UD5 命中
  - "& 7UD7" → 7UD7 命中
  - "& 7UD21" → 7UD21 命中
  - "& 7UD9" → 7UD9 命中
  - "& 1QD1,1n431" → 未命中（逗号复合值，全部 token 也未命中）
- 另：5,601 个 & 文字中有 2,596 个的 handle 出现在本文件的 1005 XDATA 中，但 sw_strip_rows 的连接项中没有任何 & 开头的值；p000 F0014 的 19 个 & 文字中无一是连接项 handle。即当前抽取不会把 & 文字收进 connections，flag 在现有数据上不会触发。
- 判定：比例 < 90%，按要求不实施 `strip_connection_jumper` / `jumper_target`。superworks_extractor.py 未修改。

## 6. 测试

- `pytest tests/unit/test_superworks_round5_producer.py tests/unit/test_superworks_round4_producer.py -q`：28 passed。
- `pytest tests/unit -q`：1664 passed, 1 skipped。

## 7. 限制

- 对照组只跑了 p024/p038/p075；p000 对比的是 r4 全量而非同快照对照。
- 受影响面为近似，未全量回放。
- 其他子代理同时修改 rules.py 等文件，探测结果含其未完成改动的影响（对照组同样包含，故 L1 的差值仍有效）。
