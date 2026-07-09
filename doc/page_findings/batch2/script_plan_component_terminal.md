# Script Plan / Batch 2: component + terminal pages

范围：

- `S0019`
- `S0021`

前提：

- 这两页都不该切向 `TableExtractor`
- 它们都继续留在现有主链，但必须拆成页型子策略

## Page-Type Split

元件页子策略：

- `horizontal_component_block_pin`
  - 适用于 `S0019`
  - 短水平导线定位
  - `INSERT` 虚拟文本为数字主源
  - 外部文本进入语义通道

端子页子策略：

- `terminal_strip_column_mode`
  - 适用于 `S0021`
  - 先按列带聚 strip
  - 再按 y 锁行
  - 数值列与语义列分轨

## Dev Tasks

### 1. 元件接线图：`horizontal_component_block_pin`

- 在线组/候选层保留 block 命中证据：
  - `source_block_name`
  - `virtual_handle`
  - `pin_slot_index`
- 为 `KK1P / KK2P / KK3P / CD-WSK-H-J-G` 建 block pin template
- 增加自配对抑制：
  - `same_virtual_text_both_sides`
  - `internal_single_pin_stub`
- 外部标签进入 side label / destination label 通道：
  - `1-21n103`
  - `1-21GD19`
  - `HD1`
  - `K-5`
  - `JD6`

### 2. 端子图：`terminal_strip_column_mode`

- 按 span 家族分组：
  - `40-115`
  - `127.5-202.5`
  - `217.5-292.5`
  - `310-385`
- 按 `|text_y - line_y| <= 1.2` 锁行
- 为每组列带定义列角色窗口：
  - 局部序号列
  - 端子代号列
  - 语义列
- 对 `\d+-\d+n(\d+)` 提升抽值优先级
- 对以下文本旁路：
  - `未定义.*回路图`
  - `说明`
  - `上接`
  - `下接`
  - strip 标题

### 3. 诊断与回归

- findings / SQLite 中补页型子标签：
  - `horizontal_component_block_pin`
  - `terminal_strip_column_mode`
- 新增 failure reason：
  - `self_pair_from_same_virtual_text`
  - `block_internal_pin_pair`
  - `terminal_column_ambiguous_ordering`
  - `semantic_terminal_row`
- 建立 Batch 2 定向回归：
  - `S0019`
  - `S0021`
  - 后续加入 `S0020`
  - 后续加入 `S0023`

## Implementation Order

1. `S0019` 的 `self_pair / internal pin` 抑制
2. `S0019` 的 block pin evidence 保留
3. `S0021` 的 strip span + row lock
4. `S0021` 的列角色窗口
5. 语义列 / 旁路文本分轨

## Success Criteria

- `S0019` 不再由 `2 -> 4 / 1 -> 3 / 1 -> 1 / 2 -> 2` 这类块内引脚对主导 non-discard 结果
- `S0021` 的 `ambiguous candidate ordering` 明显下降
- `S0021` 左半下段 review 开始从“完全 missing-right”收敛为“语义右端待解释”
- 两页都继续走原有 extractor，但主信源和失败模式被页型子策略显式建模
