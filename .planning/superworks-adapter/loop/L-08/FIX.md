# L-08 修复：远距但双向可解析的端子标签不再记 stale_label_reference

依据：README.md 的 FP 结论（p020 F0017 S0017，符号 1285C，标签 1285D「1C12D6」，距离 299.3，双向引用成立、句柄可解析、为该端子唯一身份文字）。修复为通用规则，无项目/句柄特判。

## 修改

### src/dwg_audit/extract/superworks_semantics.py
- 新增 `_page_text_index(doc)`：按标准化值分组，收集本图纸模型空间及块内全部 TEXT/MTEXT 的页面 WCS 插入点（与 walk 相同的变换链）。
- `extract_superworks_semantics` 内新增闭包 `nearer_same_identity_text(label, position, distance)`：同页是否存在另一个同身份文字，且距符号比标签更近。索引惰性构建，只有远距端子标签才会触发。
- 端子距离判别（原 `if category == "端子" and distance > 30: reasons.append("stale_label_reference")`）改为：
  - 双向引用成立 且 标签已解析 且 同页无更近的同身份文字 → `label_far_from_symbol`（布局观察，不进入 `_TRUE_CONFLICTS`，符号身份照常保留）；
  - 其余情况（非双向，或存在更近同身份文字）→ 仍记 `stale_label_reference`。句柄不可解析时距离恒为 0，不进入此分支，原有的 `dangling_label_handle` 不受影响。
- 阈值 30 数值未改。

### src/dwg_audit/audit/superworks_extractor.py
- 未改（`_TRUE_CONFLICTS` 不需调整：`label_far_from_symbol` 不在其中，`stale_label_reference` 仍在其中）。

### tests/unit/test_superworks_loop_l08.py（新增，6 用例）
- 双向+可解析+距离 300：无 stale，有 label_far_from_symbol，symbol 与 port 的 endpoint_identity 保留为 `normalize("1C12D6")`，`_true_conflicts` 为空。
- 非双向远距：仍 stale。
- 同页（模型空间）有同身份更近文字：仍 stale。
- 同页块内（PLAIN 块嵌套）有同身份更近文字：仍 stale（验证索引覆盖块内文字）。
- 同身份文字比标签更远：不 stale，为 label_far_from_symbol。
- 距离 20（阈值内）：两个码都不出现。

## 验证

### 单元测试
- `pytest tests/unit/test_superworks_loop_l08.py -q`：6 passed。
- `pytest tests/unit -q`：1683 passed, 1 skipped, **1 failed**。
  - 失败项：`tests/unit/test_superworks_semantics.py::test_dangling_stale_and_unattached_are_observable`，断言第 102 行 `"stale_label_reference" in extract(doc).ports[0].reason_codes`。该用例构造的是双向、可解析、距离约 141 的端子标签，正是本次规则要求改判为 `label_far_from_symbol` 的情形，因此失败是规则变更的直接结果，不是回归。
  - 本次不能修改该文件（超出允许范围）。建议由主线程决定：将该断言改为 `label_far_from_symbol`（并保留非双向远距用例作为 stale 的覆盖），或在 test_superworks_semantics.py 中另行拆分。

### 探测回放（p020、p061，产物已删除）
- 快照：当前工作区 src（含本次修改）。
- p020：`R-SUPERWORKS-CONFLICT` 1 → 0；符号 `SW:F0017:S0017:/1285C` 的 reason 由 `stale_label_reference` 变为 `label_far_from_symbol`，其 4 个端口的 reason 同步变化；pairs 3019 = 3019。
- p061：pairs 3977 = 3977，issues 4 = 4，符号 reason 无差异。

**与 `.tmp\superworks_round4_full` 的其他差异（逐条说明）**：
- p020 的 `R-DUPLICATE-PAIR` 6 → 0、`R-MANY-TO-ONE` 3 → 0（共 9 条 issue 消失）。这些差异**不是**本次修改导致的：
  - 对照实验：快照中仅把本次分支回退为原始 `stale_label_reference`（其余保持当前工作区），同样得到 R-DUPLICATE-PAIR 0、R-MANY-TO-ONE 0，仅保留 R-SUPERWORKS-CONFLICT 1。
  - 原因：round4 基线快照与当前工作区在 `dwg_audit/audit/rules.py`、`dwg_audit/audit/superworks_extractor.py` 上存在差异（两个基线 code_manifest 对比可见），而这两个文件的未提交修改属于工作区既有改动，不在本次修改范围内。
  - 建议：主线程确认这 9 条消失是否符合预期（属于 rules.py 等未提交改动的效果，需单独核实）。
- 对照实验（回退本次分支）与 round4 基线的符号级 reason 完全一致（p020、p061 均 0 差异），说明语义抽取层面除本次改动外没有其他变化。

### 全语料影响估计（基于 .tmp\superworks_round4_full 各项目 findings/sw_symbols.parquet，共 77 个项目、68186 个符号、23069 个端子符号）
- 当前 `stale_label_reference` 的符号数：**1**（p020 的 SW:F0017:S0017:/1285C）。
- 其中双向且句柄可解析的：1。非双向或不可解析的：0。
- 按新规则转为 `label_far_from_symbol`：**1 个符号**（p020 1285C，由探测回放确认同页无更近同身份文字）。
- 对应端口：`sw_port_coverage.parquet` 中带 stale 的 4 行，全部属于 p020 1285C，转为 label_far 后同步变化。
- 全语料其余项目：0 影响。规则只可能把 stale 改判为 label_far（不会新增 stale），所以基于 round4 的 stale 集合，影响范围就是上面这 1 个符号。

## 未做 / 注意
- 未修改 rules.py 等其他文件，未做 git 操作，未全量回放。
- 探测用的临时快照与输出（.tmp/loopP_probe、.tmp/loopP_ctrl、.tmp/loopP_ctrl_src、.planning/superworks-adapter/loopP_src 及两个 stdout 文件）已删除。
- 上述 `test_dangling_stale_and_unattached_are_observable` 的失败需要主线程决定是否更新该用例；它是本次规则的预期结果变化。
