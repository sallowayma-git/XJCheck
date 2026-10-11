# STRIPNAME：端子排行身份改用 DZ_SERIALNUMBER_NAME

只改识别身份构造与证据，未 commit / push。未改 V2 模块、`symbol_port_proposal.py`、`rules.py`（含“上接”续接名归并补丁，原样保留）、`cad_extract.py`、`candidates.py`、`component_diagrams.py`、`pipeline.py`、`superworks_loggen.py`。未加 PDF/OCR，未按项目/句柄/值特判，未整体豁免 SuperWORKS 来源。

## 1. 结论

- 端子排行身份改为 `DZ_SERIALNUMBER_NAME（端子排名）+ 行端子号`，表头只作校验并记录证据。
- 全语料 26544 行中，表头正常的 23389 行新旧身份 100% 一致；受影响 3155 行（3154 行“上接”续接表头，1 行表头为空）。
- 第二轮修复（本次）：p061 的 `3-21GD17 R-CROSS-PAGE-CONFLICT` 误报已消失。根因不在 `rules.py`，而在 `superworks_extractor.py` 的端子排归属（`StripMembership`）：它以原始表头文本建立“同排”判定，而续接行的表头是“上接3-21GD16”。修正为以端子排名判定同排，源头补齐，`rules.py` 未改。
- 6 个回放项目（p075、p061、p046、p045、p030、p048）：pairs 18477 条的 pass/review/discard 与修复前完全一致；issues 与 round13 比较 **无新增、无消失**（p061 由 0 → 0，p075 6 → 6，p030 1 → 1，其余 0 → 0，键完全相同）；已消费端口数不变。
- `rules.py` 的“上接”补丁：本次保持不动。实验表明在 6 个项目上关闭它，round13 与修复后的输出都不变，且全语料中 SuperWORKS 的“上接”值在修复后不再产生输入。是否删除留待全语料回放确认后的后续切片。

## 2. 根因（p061 3-21GD17 误报）

事实链（均已在代码与数据中核对）：

1. `3-21GD17` 在 S0031 上是端子排行 17 的身份。修复前，这一行的身份是 `上接3-21GD1617`，所以 `3-21GD17` 在 round13 中没有任何端子排行。
2. 同排判定 `StripMembership.header_for(value)`（`superworks_extractor.py`）对没有排行的端子，回落到项目排名（XML 中的端子排名前缀 `3-21GD`）。因此 round13 中 `3-21GD17` 与 `3-21GD16`（表头 `3-21GD`）同属 `3-21GD` 排，两条 S0008/S0014 的短接 `3-21GD17→3-21GD16` 带 `terminal_short_bridge=True`（`strip_membership=same_strip`）。
3. 修复后 `3-21GD17` 有了自己的排行，`StripMembership` 改用这一行的表头文本 `上接3-21GD16` 作为排标识。它与 `3-21GD16` 的 `3-21GD` 不相等，判为跨排（`terminal_cross_strip_link=True`，`strip_corroborated=False`）。按 G7 规则，未经排行佐证的跨排连接只是普通配对，不再是短接。
4. `_run_cross_page_conflict` 只把非短接的右端计入“多去向”。两条短接失去短接标记后，`3-21GD16` 成为第二个去向，S0008 与 S0014 出现跨页冲突。
5. 正常表头的行不受影响：它们的表头文本就是排名，同排短接一直带着短接标记。
6. 结论：第一轮修复的身份改动暴露了 `StripMembership` 依赖原始表头文本的问题。这是源头的结构字段（排标识）没有跟随身份的一致口径（端子排名），与 `rules.py` 的“上接”分支无关。

数据依据（`tools/crosspage_trace.py`、`tools/pair_evidence.py`、`tools/membership_flags.py`）：

- round13 中 `PSW1ffe…`、`PSW2976…` 两条 `3-21GD17→3-21GD16`：`terminal_short_bridge=True`，`strip_header=3-21GD`。
- 第一轮修复（v1）中同两条：`terminal_cross_strip_link=True`，`strip_corroborated=False`。
- 第一轮修复中全部 16 条因排标识改为续接表头文本而从同排变为跨排的 SuperWORKS 配对（p061 5 条、p046 3 条、p045 3 条、p030 3 条、p048 2 条）。第二轮修复后这 16 条全部恢复为同排，与 round13 的标记逐条一致（round13 → v2 标记变化 0 条）。

## 3. 改动

| 文件 | 位置 | 改动 |
|---|---|---|
| `src/dwg_audit/extract/superworks_semantics.py` | `extract_superworks_semantics` 端子排循环 | （第一轮）身份 = DZ 名 + 行端子号；无 DZ 名回落表头；`validation` 增加 `strip_name`、`strip_name_source`、`header_text`、`header_mismatch`。 |
| `src/dwg_audit/audit/superworks_extractor.py` | `mapping["header_prefix"]`，约 916 行 | （第一轮）改为 `row.validation.get("strip_name") or row.header.get("normalized")`。 |
| `src/dwg_audit/audit/superworks_extractor.py` | `StripMembership.__init__`，约 383 行 | （第二轮，根因修复）排标识改为 `row.validation.get("strip_name") or row.header.get("normalized")`，即按端子排名而非续接表头文本判定同排。 |
| `tests/unit/test_superworks_loop_strip_name.py` | 9 例 | 见第 4 节。 |

`rules.py` 未改动（`_CONTINUATION_MARK = "上接"`、`_CONTINUATION_HEADER_PATTERN` 仍在第 119–120 行）。

## 4. 测试

`tests/unit/test_superworks_loop_strip_name.py`，9 例，全部通过：

1. 续接表头取真实排名（`上接1QD15` + `16` → `1QD16`），证据字段正确。
2. 连字符装置前缀（`上接1-21QD15` + `16` → `1-21QD16`）。
3. 表头正常时身份不变（`7UD2`）。
4. DZ 缺失时回落表头逻辑（`1XD2`，`strip_name_source="header"`）。
5. DZ 缺失且为续接表头时保持旧拼接（回落路径不改）。
6. 表头为空、DZ 存在时取 DZ 名（`1C2D5`）。
7. （第二轮）两行同排（`3-21GD` 与 `上接3-21GD16`）在 `StripMembership` 中均为 `3-21GD`，`GD16–GD17` 的 `_strip_contract_fields` 为 `terminal_short_bridge=True`、`strip_membership=same_strip`，无跨排标记。
8. （第二轮）规则层回归：`3-21GD17` 的 S8 普通配对、S8/S14 同排短接（带短接标记）→ `_run_cross_page_conflict` 无 issue。
9. （第二轮）对照：同形状但短接未被佐证（跨排、未佐证）→ 仍报冲突。说明测试 8 的豁免来自短接标记，而非放宽规则。

全量：`python -m pytest tests/unit -q` → **1894 passed, 1 skipped**，无失败（第一轮为 1891，新增 3 例）。

## 5. 回放对比（6 个项目，第二轮代码）

快照：`.tmp/loop_stripname_v2_src` = round13 代码（`.tmp/loop_gnd_g1_src`）+ `superworks_semantics.py` + `superworks_extractor.py`（当前工作区版本）。输出：`.tmp/loop_stripname_v2`。

| 项目 | pairs（前=后） | pass / review / discard（前=后） | 身份变化的配对 | issues 前→后（键相同） | 已消费端口 前→后 |
|---|---|---|---|---|---|
| p075 | 2338 | 1355 / 315 / 668 | 306 | 6 → 6 | 762 → 762 |
| p061 | 4229 | 3029 / 634 / 566 | 156 | **0 → 0**（第一轮 0→1 的误报已消失） | 1261 → 1261 |
| p046 | 2852 | 2151 / 406 / 295 | 154 | 0 → 0 | 870 → 870 |
| p045 | 2904 | 2177 / 410 / 317 | 138 | 0 → 0 | 868 → 868 |
| p030 | 2368 | 1375 / 223 / 770 | 27 | 1 → 1 | 612 → 612 |
| p048 | 3786 | 2829 / 519 / 438 | 200 | 0 → 0 | 1140 → 1140 |

- pairs 新增 0、删除 0；全部 18477 条的 status 不变；`issues` 的 new / resolved 列表全部为空。
- 配对字段变化 981 条与第一轮完全一致：`left_value` 855 条（`上接…` → 真实身份），`pair_kind` 126 条（`ordinary_pair` → `bridge_mapping`，左右值不变）。第二轮没有新增字段变化，只恢复了 16 条 evidence 的同排标记（见第 2 节）。
- 已消费端口：6 项目共 5513 个，前后不变。
- 第一轮 v1 与第二轮 v2 的对比：`compare_v1_membership_regression.json`（v1 文件）与 `compare.json`（v2）。

### 5.1 GD16–GD17 同排短接是否被正确识别（需求第 2 点）

- 是。p061 中 `PSW1ffe…`（S0008）与 `PSW2976…`（S0014）均为 `3-21GD17→3-21GD16`，`terminal_short_bridge=True`，`strip_membership=same_strip`，`strip_header=3-21GD`。`_is_terminal_strip_bridge_claim` 判为短接，因此在 `_run_cross_page_conflict` 中不计入右端（去向）集合，不会构成“多去向”。
- 图证：`png/BRIDGE_p061_PSW1ffece25689601f0.png`，S0008 上 `3-21GD16` 与 `3-21GD17` 两个端子标注之间有一条直接导线，两端子同属 `3-21GD` 排（行 16 与行 17）。
- 注意：这两条配对的 `pair_kind` 仍为 `ordinary_pair`，与 round13 一致。`bridge_mapping` 的判定依赖两端位于同一表头实体（`_same_strip_relation`），而 16 与 17 分属两个表头块，因此不满足。短接由 `terminal_short_bridge` 标记识别，这是 round13 已有的行为，本次未改。

## 6. 截图核对

脚本：`tools/render_strip_pairs.py`、`tools/render_bridge_pairs.py`、`tools/montage.py`。DXF 只读。绿色为行，蓝色为表头，橙色为接线文字（去向），灰色为窗口内的线。图中行号、表头和接线文字都取自 DXF 实体。

### 6.1 pass 配对（13 例，`png/<pid>_<pair>.png`，合并图 `png/MONTAGE_01..04.png`）

| 图 | 项目 / 页 | 行 | 表头 | 接线文字（去向） | 旧身份 → 新身份 | 结论 |
|---|---|---|---|---|---|---|
| p075_PTMR0091 | p075 / S0016 | 142 | 上接1-26TD115 | 1-26n632 | 上接1-26TD115142 → 1-26TD142 | 一致 |
| p075_PTMR0308 | p075 / S0019 | 213 | 上接2-26TD192 | 2-26n823 | 上接2-26TD192213 → 2-26TD213 | 一致 |
| p061_PSWc3e430ab13f1219d | p061 / S0028 | 29 | 上接2-21C1D17 | 2-21n420 | 上接2-21C1D1729 → 2-21C1D29 | 一致 |
| p061_PTMR0283 | p061 / S0030 | 46 | 上接1-21QD16 | 1-21n230 | 上接1-21QD1646 → 1-21QD46 | 一致 |
| p061_PTMR0371 | p061 / S0031 | 17 | 上接3-21GD16 | 4-21DK2-11 | 上接3-21GD1617 → 3-21GD17 | 一致；第一轮误报的对象，本轮已无 issue |
| p046_PTMR0013 | p046 / S0019 | 33 | 上接2-21QD31 | 2-21n217 | 上接2-21QD3133 → 2-21QD33 | 一致 |
| p046_PTMR0019 | p046 / S0019 | 39 | 上接2-21QD31 | 2-21n223 | 上接2-21QD3139 → 2-21QD39 | 一致 |
| p045_PTMR0214 | p045 / S0021 | 77 | 上接1-21QD44 | 1-21n320 | 上接1-21QD4477 → 1-21QD77 | 一致（行 77 与 1-21n320 同一水平线，y=108.5） |
| p045_PTMR0151 | p045 / S0020 | 60 | 上接2-21CD48 | 2-21n510 | 上接2-21CD4860 → 2-21CD60 | 一致 |
| p030_PSWeef17d945e62bf0b | p030 / S0032 | 38 | 上接1-4Q1D29 | K862-2X13 | 上接1-4Q1D2938 → 1-4Q1D38 | 一致 |
| p030_PTMR0148 | p030 / S0032 | 26 | 上接1I3D12 | TF2-12 | 上接1I3D1226 → 1I3D26 | 一致 |
| p048_PTMR0369 | p048 / S0029 | 48 | 上接4-21QD10 | 4-21n528 | 上接4-21QD1048 → 4-21QD48 | 一致 |
| p048_PTMR0015 | p048 / S0026 | 21 | 上接3-21GD8 | 3-21n231 | 上接3-21GD821 → 3-21GD21 | 一致 |

- 13 例中，新身份的排名取自 DZ 名，行号与图上行文字一致，接线文字与该行同一水平线或紧邻。旧身份的拼接结果（如 `115` + `142` 拼成 `115142`）在图上没有对应的端子。
- 随机抽样（种子 7）：每项目 2 例 `left_value` 修正（12 例），加上 p061 的 `PTMR0371`。

### 6.2 bridge 与同排短接（3 例）

- `png/BRIDGE_p030_PSW4565779ed46b073e.png`：`1I3D23 — 1I3D22`，同一端子排（S0032），图中为一条直接导线连接两个相邻端子标注。
- `png/BRIDGE_p030_PSWe26aa7af1809d124.png`：`1I3D22 — 1I3D21`，同上。
- `png/BRIDGE_p061_PSW1ffece25689601f0.png`：`3-21GD17 — 3-21GD16`，同一端子排（3-21GD），S0008 上的直接导线（见 5.1）。

## 7. rules.py 中“上接”补丁

涉及 `rules.py` 的 `_CONTINUATION_MARK`、`_CONTINUATION_HEADER_PATTERN`、`_fold_continuation_identity`、`_pair_endpoint_identity`、`_terminal_row_logical_identity`。本次未改动，补丁保持原样。

证据：

1. 全语料 round13（77 个项目）中，含“上接”的端子值 2659 条，均为左端，且全部来自 SuperWORKS 行。`header_prefix` 以“上接”开头的同样 2659 条，全部来自 SuperWORKS。非 SuperWORKS 来源为 0。
2. 实验 A（第二轮代码，关闭补丁，`tools/make_norules_snapshot.py` 生成，`tools/norules_compare.py`）：6 个项目的 18477 条 pairs 的 status、left、right、pair_kind、issues、已消费端口与带补丁的回放**完全相同**。
3. 实验 B（round13 代码，关闭补丁，`tools/r13_counterfactual.py`，6 个项目）：已消费端口、pair status、issues 全部不变；`left_value` 也不变（补丁只影响规则层的分组判定）。
4. 补充检查：实验使用的关闭方式为将 `_CONTINUATION_MARK` 替换为 ASCII 标记 `@NOFOLD@`，并将续接正则替换为 `(?!)`。通过 `PYTHONPATH` 导入快照，已核对 `dwg_audit.audit.rules._CONTINUATION_MARK` 为 `'@NOFOLD@'`。

结论：在 6 个回放项目上，补丁在修复前后都不影响输出。全语料中，修复后的 SuperWORKS 续接值不再以“上接”形式进入 `rules.py`。本次只保留补丁，不删除，删除留待全语料回放确认后的切片。非 SuperWORKS 路径（`table_extractor.py` 自有的续接解析，约 2283 行）不受影响。

## 8. 限制与待决事项

1. 只回放了 6 个项目（按要求 3–6 个）。第二轮的 `StripMembership` 改动会影响所有含续接表头的 SuperWORKS 配对，其他 71 个项目的影响未验证。建议在下一切片做全语料回放，核对 issues。
2. `_same_strip_relation`（决定 `bridge_mapping` 的 `pair_kind`）仍以表头实体为键，因此跨表头块的同排短接保持 `ordinary_pair`（与 round13 一致）。统一为端子排名键属于后续切片。
3. 身份修正不带来端口消费增益。6 项目中 43 个身份变化的未消费端口修复后仍未消费，原因是同一端子另一接点的导线没有对应的端子排去向（例：p030 `1-4Q1D38` 的接点 `27611:1`）。ATTR-CENSUS 的“直接影响 75 个未消费端口”应理解为身份层面的影响。
4. `bridge_mapping` 重分类（126 条）是行为变化（见第 5 节），配对仍为 pass、左右值不变，但 `ordinary_pair_eligible` 改变，需责任人确认其与 F4/M2 语义一致。
5. p061 的 `3-21GD17` 在 S0008（原理图 MTEXT 标注）与 S0031（端子排行）之间是同名端子。S0008 上的 `3-21GD17→3-21GD16` 是同排短接，不计入去向，因此第一轮的跨页冲突是误报。这一判断依赖第 2 节的排归属修复，本身不是数据冲突。

## 9. 产出文件

- `README.md`（本文件）
- `compare.json`：第二轮（v2）6 项目 before/after 逐条对比
- `compare_v1_membership_regression.json`：第一轮（v1，未修 `StripMembership`）对比，保留作为根因证据
- `png/`：13 张 pass 配对、3 张 bridge 截图、4 张合并图
- `tools/`：
  - 身份：`identity_census.py`、`identity_consistency.py`、`evidence_check.py`
  - 回放对比：`compare_stripname.py`、`norules_compare.py`、`r13_counterfactual.py`、`affected_ports.py`
  - 根因诊断：`crosspage_harness.py`（对单项目 pairs 运行 `_run_cross_page_conflict`）、`crosspage_trace.py`（按端子分组展示各豁免结果）、`pair_evidence.py`（配对证据标记）、`membership_flags.py`（同排标记 round13 / v1 / v2 对比）
  - 快照与实验：`snapshot_check.py`、`make_norules_snapshot.py`、`shangjie_usage.py`、`select_projects.py`
  - 渲染：`render_strip_pairs.py`、`render_bridge_pairs.py`、`montage.py`、`samples.json`、`conflict_trace.py`
- `.tmp/` 中间产物：`loop_stripname_v2/`（第二轮回放输出）、`loop_stripname_v2_src/`（快照）、`loop_stripname_v2_norules/`（实验 A）、`loop_stripname_r13norules/`（实验 B）、`loop_stripname/`（第一轮输出，保留）、`loop_stripname_census/`、`loop_stripname_v2_pytest_unit.txt`、`loop_stripname_v2_run.txt`。

复现（仓库根目录，`PYTHONIOENCODING=utf-8`）：

```
python .planning/superworks-adapter/replay.py --output .tmp/loop_stripname_v2 --snapshot .tmp/loop_stripname_v2_src --workers 3 --projects p075 p061 p046 p045 p030 p048
python .planning/superworks-adapter/loop/STRIPNAME/tools/compare_stripname.py --before .tmp/superworks_round13_full --after .tmp/loop_stripname_v2 --projects p075 p061 p046 p045 p030 p048 --out .planning/superworks-adapter/loop/STRIPNAME/compare.json
PYTHONPATH=.tmp/loop_stripname_v2_src python .planning/superworks-adapter/loop/STRIPNAME/tools/crosspage_trace.py .tmp/loop_stripname_v2/p061/*/findings/pairs.parquet 3-21GD17
python .planning/superworks-adapter/loop/STRIPNAME/tools/render_strip_pairs.py --after .tmp/loop_stripname_v2 --before .tmp/superworks_round13_full --compare .planning/superworks-adapter/loop/STRIPNAME/compare.json --out .planning/superworks-adapter/loop/STRIPNAME/png --manifest .planning/superworks-adapter/loop/STRIPNAME/tools/samples.json --extra p061:PTMR0371
```
