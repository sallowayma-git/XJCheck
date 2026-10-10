# L-15 修复说明：X 前缀 nearest 端口的身份

范围：只改 `src/dwg_audit/extract/superworks_semantics.py` 的端口身份组装，新增 1 个测试文件，按新语义更新 V-06 的一条断言。未做 git 操作，未全量回放，未改 `superworks_extractor.py` / `rules.py` / `candidates.py`。

## 1. 修改

`src/dwg_audit/extract/superworks_semantics.py`，TERMPOINT 端口身份组装处（F4c 分支，约 409-424 行）：

- 条件：端口为非「端子」类别；端口号匹配 `[A-Za-z]+\d+`（如 `X19`）；pin 的 `resolution_method == "definition_text_nearest"`；pin 规范值等于端口号的数字部分（`19`）。
- 变化：端口主身份 `endpoint` 改为 `标签-端口号`（`K742-X19`）；原数字身份 `标签-数字`（`K742-19`）写入 `pin["endpoint_aliases"]`。
- 其他情况保持原行为：纯数字端口号、非 nearest 的 pin、数字与端口号不一致（如 `X19` 配文字 `18`，身份仍为 `K742-18`，别名 `K742-X19`）。
- 通用路径（`:399-400` 的标签+端口号）未改。
- 连接线匹配（`_connect_labels` 的 `endpoint_identity` 取自端口）只比较 endpoint，改动后自动跟随；已用探针确认连接线端点与 component_mapping 左值随之变化（见第 3 节）。

## 2. 测试

- 新增 `tests/unit/test_superworks_loop_l15_xport.py`（4 项）：
  1. X 前缀且数字一致：`X19` → 身份 `K742-X19`，别名 `["K742-19"]`；相邻 `X18`、`X20` 不受影响。
  2. 纯数字端口号 `19`：身份 `K742-19`，无别名。
  3. 数字不一致（`X19` 配 `18`）：身份 `K742-18`，别名 `["K742-X19"]`。
  4. 连接线：连接线端点与 `X19` 端口重合，连接线标签的 `endpoint_identity == "K742-X19"`。
- 按新语义更新 `tests/unit/test_superworks_loop_v06_pins.py::test_nearest_digit_is_the_port_own_number_for_x_named_termpoints`：身份由 `K741-n` 改为 `K741-Xn`，别名由 `K741-Xn` 改为 `K741-n`。理由：该测试断言的正是本次修复要改变的旧身份；它的其余断言（nearest 为端口自身数字、邻近数字不抢占、等距不解析）未改。
- 结果：新文件 4 项与 V-06 文件 3 项全部通过；`pytest tests/unit -q` 全量 **1768 passed, 1 skipped**，无失败。

## 3. 单项目探针（7 项目）

命令：`replay.py --output .tmp/loopY1_probe --snapshot .planning/superworks-adapter/loopY1_src --workers 3 --projects p029 p031 p030 p004 p028 p035 p000`，7 项目全部 COMPLETE。

快照归因：快照的 `code_manifest` 与 `.tmp/superworks_round7_full` 相比只有 `dwg_audit\extract\superworks_semantics.py` 不同，因此探针中的全部差异均归因于本次改动。

| 指标 | 结果 |
|---|---|
| 连接线端点身份变化（sw_connect_labels） | **246**：p000 9、p004 18、p028 18、p029 64、p030 55、p031 64、p035 18（与 L-15 README 第 4 节逐项一致） |
| 上述 246 中可被端子排反向声明验证的条数 | 145 |
| 其中 与端子排反向声明一致：修复前 / 修复后 | **0 / 145（0% → 100%）** |
| 部件端口记录（sw_part_instances.ports）身份变化 | 504（全部为 nearest、X 形式、数字匹配）；未逐条核对其中挂连接线的数量 |
| component_mapping 左值变化 | 300（pair 总数 2846 不变，status 不变，pair_id 集合不变）；其中新左值出现在端子排反向声明中 187 条，修复前 0 条 |
| 装置端子 / 其他类别符号端口（sw_ports）身份变化 | 0 |
| 各规则 issue | 7 项目 issue 合计 6，修复前后逐条比对（rule_id、sheet、pair、左右值）无增减；R-PAIR-LOW-CONFIDENCE 1（p000），R-SUPERWORKS-CONFLICT 5（p000、p028、p029、p030、p031） |

差异说明：
- 连接线端点与 README 的 246 完全一致。部件端口记录层面的身份变化为 504 条（nearest X 形式端口），README 未给出这一口径，本次未能从 round7 数据复现 246 与 504 的换算关系，请以连接线口径为准。
- 一致率的判定口径：以本项目全部 `sw_strip_rows` 的连接值（规范化、去 `&`、按逗号拆分）作为端子排反向声明集合；可验证指端口的 `标签-端口号` 或 `标签-数字` 出现在该集合中。该口径未限定 reciprocal，属近似。

## 4. 限制

- 修复只覆盖 nearest 的 X 前缀端口；残余 nearest 数字端口（如 `PWR4` 对 `4`，README 第 4 节提到的 154 个）本次未处理。
- 「数字与 pin 规范值相同」是唯一的 X 修复判据；数字不一致的 X 端口仍为数字身份，别名保留 X 形式。
- 别名 `endpoint_aliases` 已写入 pin，但本次未修改任何规则读取别名的逻辑。
