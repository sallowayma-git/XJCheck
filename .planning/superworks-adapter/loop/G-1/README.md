# G-1：GND 公共地豁免与端口无标注说明

口径（用户已定）：
1. R-MANY-TO-ONE 中“Right value GND maps back to multiple left values.”属于多块端子排/多个装置上的同名公共地，按合法处理，不再报。
2. R-PAIR-MISSING-SIDE 中元件端口无任何外部标注的 4 条继续报出供人工核验，但 message/explanation 明确写出“该端口无标注”。

## 改动文件与函数

- `src/dwg_audit/audit/candidates.py`
  - 新增模块常量 `GROUND_NETWORK_NAME_PATTERN = re.compile(r"^GND$", re.IGNORECASE)`。
  - `_SCHEMATIC_DC_SEMANTIC_ENDPOINT_PATTERNS`、`_SCHEMATIC_NETWORK_TIME_SEMANTIC_ENDPOINT_PATTERNS` 两处原本的 `^GND$` 改为引用该常量，行为不变。
- `src/dwg_audit/audit/rules.py`
  - 新增 `_is_ground_network_endpoint(value)`：共享端点名称是否为接地网络（复用上面的常量）。
  - `_run_many_to_one`：在 G6 非桥接子组豁免之后、terminal_header / split / structured_scope 等报告分支之前，若右侧共享端点是接地网络则 `continue`。沿用现有结构化豁免的静默跳过做法（代码中没有降为 info 的惯例）。只看共享右端点，不看左端，左侧为 GND 而右侧非地的分组仍报。
  - `_run_pair_missing_side`（component_mapping 分支）：当 pair.evidence 的 `missing_side_reason == "unlabelled_port"` 时，message 追加“（端口 N 无任何外部标注，可能为备用脚或漏标，请核验）”，explanation 前置“该元件端口（端口 N）无标注：其搜索窗口内没有任何外部标注文字。”，并在 issue extra 中写入 `missing_side_reason="unlabelled_port"`。`missing_side_classification`（即 `unresolved_reason`）原本已经通过 pair evidence 传到规则层，本次未改动这条链路。
- `src/dwg_audit/audit/component_diagrams.py`
  - 新增 `_strip_side_window_has_external_text(port, texts, side=)`：与 `_nearest_strip_external_endpoints` 同一窗口（x 容差 22，y 间距 1 至 9，同侧），判断窗口内是否存在任何非块内、非 MARK 的外部文字（不要求是合法端点值）。
  - `extract_strip_two_port_component_pairs` 循环中计算 `unlabelled_port`：该侧无端点、无冲突文字、非 label_only，且窗口内没有任何外部文字。
  - `_build_strip_two_port_pair` 新增参数 `unlabelled_port`，evidence 新增 `missing_side_reason`（"unlabelled_port" 或 None）。
- `tests/unit/test_superworks_loop_gnd_unlabelled.py`：新增 7 个用例。

## 判定依据

GND：
- 元数据不可用。这些多对一 pair 的 GND 端点来自 SuperWORKS 端子排表格（`table_mapping` / `terminal_header_table`），pair 上没有挂 SW 符号类别，`LD_SYMB2_SPECIAL=接地` 无法关联到这些端点。SW 字典也把 GND 列为 unknown_names（warning_only）。
- 因此用名称判定，统一使用已有的接地语义口径 `^GND$`（即 candidates.py 中 schematic GND 语义端点所用的同一模式），没有新增裸字符串比较。

无标注：
- 只有同时满足以下条件才标记 `unlabelled_port`：该侧无合法外部端点，无叠放冲突文字，且端点搜索窗口内没有任何外部文字。
- 窗口内若有非合法端点的外部文字（例如现有测试中的 `112`），不算无标注，保持原通用 message。
- 叠放冲突（`coincident_conflicting_labels`，如 p003 的 4 条）不标无标注。

## 测试结果

- `python -m pytest tests/unit/test_superworks_loop_gnd_unlabelled.py -q`：7 passed。
  - 覆盖：GND 共享端点在多条线上豁免；同形非地端点仍报；GND 左端 + 非地右端仍报；接地名称判定；无标注时 message/explanation/evidence 含说明；窗口内有非端点文字不算无标注；叠放冲突不算无标注。
- `python -m pytest tests/unit -q -x`：1856 passed, 1 skipped。

## 回放与前后对比

- 快照：`.tmp/loop_gnd_g1_src`
- 9 个项目输出：`.tmp/loop_gnd_g1`（p015 p021 p041 p042 p043 p044 p050 p071 p075，全部 COMPLETE）
- 对照（p003，不在 9 项目名单内，用于验证叠放冲突不被标注）：`.tmp/loop_gnd_g1_p003`
- 基线：`.tmp/superworks_round12_full`

按 (源文件, rule_id, message, pair_id, left, right, sheet) 逐条比较：

| 项目 | round12 | 新 | 变化 |
|---|---|---|---|
| p015 | 1 | 0 | -1 GND |
| p021 | 1 | 0 | -1 GND |
| p041 | 2 | 1 | -1 GND；PCM0023 缺端 message 加无标注说明 |
| p042 | 2 | 1 | -1 GND；PCM0023 缺端 message 加无标注说明 |
| p043 | 2 | 1 | -1 GND；PCM0027 缺端 message 加无标注说明 |
| p044 | 2 | 1 | -1 GND；PCM0027 缺端 message 加无标注说明 |
| p050 | 2 | 1 | -1 GND |
| p071 | 5 | 4 | -1 GND |
| p075 | 7 | 6 | -1 GND |
| 合计 | 24 | 15 | GND 多对一 -9；缺端 4 条保留（message 改写） |

- 除上表外没有其他 issue 增减或变化。
- p003 对照：4 条 coincident_conflicting_labels 缺端与 round12 完全一致，没有无标注说明。
- parquet 中 `right_value` 的 nan/None 差异仅为 pandas 读取 dtype 的表现，原始值均为 null。

## 其他说明

- 本次未 commit。
- 未修改 V2 模块与 `symbol_port_proposal.py`，未加 PDF/OCR，未按项目名、句柄或端子值写特判。
- `.planning/superworks-adapter/loop/active_issues.md` 处于已修改状态，但不是本次改动的文件。
- 公共地豁免目前仅覆盖名称 GND。其他接地类名称未在本次范围内扩展。
