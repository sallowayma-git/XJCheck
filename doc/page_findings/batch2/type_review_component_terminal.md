# Batch 2 Type Review: component + terminal pages

Review scope:

- `S0019.md`
- `S0021.md`

这两页不属于同一图种，但它们一起定义了 Batch 2 最重要的边界：

- `S0019` 说明“元件接线图”不能只按普通导线页思路理解；
- `S0021` 说明“端子图”也不该误切到表格页，而应按端子列带专门处理。

## 1) `S0019` 的真正问题是什么

结论：`S0019` 继续留在 `ComponentDiagramExtractor`，但需要新增 `horizontal_component_block_pin` 子模式。

关键原因：

1. 当前 39 个 `line_group` 全为 horizontal，说明短水平导线确实是有效几何锚点。
2. 当前 92 个 accepted candidates 几乎都来自 `KK1P / KK2P / KK3P / CD-WSK-H-J-G` 的 `INSERT` 虚拟文本。
3. 非 discard pair 大量表现为 `2 -> 4`、`1 -> 3`、`1 -> 5`、`2 -> 2`、`1 -> 1`，这更像块内固定引脚模板，而不是块间接线语义。
4. 外部文本 `1-21n103 / 1-21GD19 / HD1 / K-5 / JD6` 目前大多被当成 `not_numeric` 丢弃，但它们明显承载器件位号、去向或语义标签。

直接结论：

- 主问题不是“没看到数字”，而是“只看到了块内脚号，还没把块外语义接上去”。

## 2) `S0021` 的真正问题是什么

结论：`S0021` 继续留在 `TerminalDiagramExtractor`，但需要新增 `terminal_strip_column_mode` 子模式。

关键原因：

1. 135 个 `line_group` 全为 horizontal，且稳定收敛为 4 个 span 家族。
2. accepted candidates 高度集中在固定的局部序号列、端子代号列和说明列。
3. 当前 discard 主因不是无数字，而是同一行内多列文本同时落入统一窗口，造成 `ambiguous candidate ordering`。
4. review 主要集中在 `DK/KLP/ZKK/UA/UB/UC/UN/3U0` 这类语义区，说明端子页后续需要“数值列”和“语义列”分轨，而不是继续扩大统一候选窗。

直接结论：

- 主问题不是“端子图没进主链”，而是“已经进主链，但还没进入列带感知模式”。

## 3) 两页合起来暴露出的架构结论

这两页一起说明，当前最值得做的不是再拧全局阈值，而是把“同样是 supplemental 页，也有完全不同的主信源”正式写进页型子策略：

- `S0019`：
  - 主信源是 `block pin evidence`
  - 导线只负责定位
  - 外部文本负责补语义
- `S0021`：
  - 主信源是 `terminal-strip columns`
  - 导线只负责锁定行
  - 端子代号正则负责抽值

所以 Batch 2 更像是在证明一件事：

- 当前系统已经不该再只有一个“pair builder”，而应进入“按图种拆专用策略”的阶段。

## 4) 推荐的后续子策略

### A. `horizontal_component_block_pin`

适用页：

- `S0019`
- 未来所有“短水平 stub + INSERT 引脚主导”的元件接线页

核心能力：

1. 线段先命中 block instance，而不是直接命中裸数字。
2. virtual numeric 升级为 `block pin evidence`，保留 `source_block_name / pin_slot / side`。
3. 同一虚拟 text 双端复用时，输出 `self_pair_from_same_virtual_text` 或 `internal_single_pin_stub`，不进普通 pair。
4. 外部标签进入语义通道，不再统一 `not_numeric` 丢弃。

### B. `terminal_strip_column_mode`

适用页：

- `S0021`
- 未来同类左/右侧端子图

核心能力：

1. 先按 span 家族分 strip。
2. 再按 y 步长锁行。
3. 每条 strip 分成局部序号列、代号列、语义列。
4. `\d+-\d+n(\d+)` 这类端子代号优先抽值。
5. `上接/下接/说明/未定义...回路图` 走旁路或黑名单，不进入普通 numeric ranking。
