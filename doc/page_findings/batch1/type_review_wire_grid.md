# Batch 1 Type Review: wire-grid pages

Review scope: `S0008.md`, `S0009.md`, `S0012.md`, `S0013.md`.

## 1) 是否真的该走 TableExtractor

结论：**这四页都不应切到 TableExtractor，仍应走 `WireDiagramExtractor`，只是需要补一个“网格化开入回路页”子策略。**

| Page | Verdict | Why |
| --- | --- | --- |
| `S0008` | `WireDiagramExtractor` | 标题命中 `BINARY INPUT 1` / `开入回路图1`，主体仍是三列重复横向回路阵列；首页顶部只是多出 `GD/DC/KLP` 引导带，不改变主识别器。 |
| `S0009` | `WireDiagramExtractor` | 标题命中 `BINARY INPUT 2` / `开入回路图2`，主证据是 92 条 horizontal line_group，主体是三列重复回路，不是封闭格元。 |
| `S0012` | `WireDiagramExtractor` | 首页虽然“表格感”最强，但本质仍是三列横向回路阵列 + 顶部引导母线；95 条 line_group 全 horizontal，数字主要贴在线路附近自由文本上。 |
| `S0013` | `WireDiagramExtractor` | 与 `S0009` 同模板，属于标准 `BINARY INPUT 2` 阵列页；问题核心是一行被符号块切成两段，不是页型分类错误。 |

这批页的误导性在于：**行列非常整齐，看起来像表格；但可抽取对象并不是格元，而是被小符号打断的水平导线通道。**

## 2) 共性的结构规则

1. 标题/文件名都稳定命中 `BINARY INPUT 1/2`、`开入回路图1/2`，这是很强的页型先验。
2. 主体都可分成 3 个稳定列带，列锚点大致落在左/中/右三列，数字列也稳定集中在 `x≈90.6 / 215.6 / 340.6` 一带。
3. 主体有效行都落在重复行带内，`y≈85-235`，行距约 `10`；这是典型的 row-banded wire page，而不是 cell-banded table page。
4. 单个逻辑通道的真实结构基本都是：`左侧语义标签(QD/设备名)` -> `左短水平线` -> `中间端子数字` -> `符号块/短间隔` -> `右长水平线` -> `右侧语义标签(BI/说明)`。
5. 数字主证据来自 **DIM/自由文本数字**，不是块属性，也不是表格单元内容。
6. 都有“非标准带”需要分流：
   - `S0008/S0012` 首页顶部 `y≈245-265` 的 `GD/DC/KLP` 引导带与 inline numeric。
   - `S0009/S0013` 的公共线/电源带，以及 `y≈77.5` 的列头/尾线。
7. `BI xx`、`QDxx`、`GDxx` 更适合作为语义标签/定位锚点，不应与纯数字端子候选混用。

## 3) 问题归因拆分

### A. 分类问题

这是**次要问题**，主要是防止上游把它们误送到 `TableExtractor`。

应对方式：
- 加一个负向页型规则：命中 `BINARY INPUT` / `开入回路` 且主体由大量 horizontal line_group 构成时，优先锁到 `WireDiagramExtractor`。
- 不要把“强行列感”当成足够的表格证据；要区分“规则阵列的导线页”和“封闭格元的表页”。

### B. 导线抽取 / 线组合并问题

这是**主问题**，也是这批页当前最主要的失真来源。

核心症状：
- 同一逻辑行被符号块切成左右两段，当前被当成两条 pair。
- 同 y 的短线段与长线段没有在页型层先合并，导致后续一直出现镜像半配对。
- 顶部/底部公共线、列头短线被送入常规 pairing，制造大量低价值噪音。

需要的能力：
- `row-band clustering`：先按固定 y 节距聚行。
- `split-row merge / split-by-symbol-block merge`：把同一行内被固定小块打断的共线段合成一条逻辑通道。
- `header-bus / common-bus` 分流：公共线与首页引导带不要走普通端点配对。
- `semantic label separation`：`QD/GD/BI` 文本保留为语义标签，但默认不参与 terminal numeric pairing。

### C. 候选配对问题

这是**第二层问题**，大多是在线未合并后被放大的结果。

典型表现：
- 同一数字在符号块两侧各命中一次，形成 `duplicate single-sided hits`。
- inline numeric（如 `231/232/331/332/532`）不贴端点，纯端点窗口会漏。
- 非标准说明行（如 `Power loss alarm` / `Device alarm`）会被误判成“右侧缺失”。
- 说明文字、乱码文本如果窗口过宽，会污染候选选择。

需要的规则：
- 同 y、同数字、相邻两段且中间只隔固定符号块时，做 `duplicate-half-pair collapse`。
- 对稳定数字列加锚点先验，优先接受三列数字锚点附近的纯数字。
- 将 `inline numeric on bus` 单独记为一类，不混入普通端点候选。

## 4) 最值得优先实现的页型子策略

最高优先级建议：**在 `WireDiagramExtractor` 内实现共享的 `binary_input_grid` 子策略**，覆盖这类 `BINARY INPUT 1/2` 网格化开入回路页。

这个子策略至少应包含 5 个能力：

1. 页级识别：标题命中 `BINARY INPUT` / `开入回路`，且存在 3 列稳定水平回路阵列。
2. 行带聚类：按 `y≈85-235`、步长约 `10` 识别重复行。
3. 符号跨越合并：把被固定小块切开的左右水平段合并为一条逻辑通道。
4. 数字锚点优先：优先使用三列稳定数字列上的自由文本数字，压低块内数字和说明文本。
5. 语义标签分轨：`QD/GD/BI` 和说明文本单独保留，不直接参与 numeric pairing。

在此基础上，再加一个较小的补丁型子策略：**`binary_input_first_page_header_bus`**，专门处理 `S0008/S0012` 这类首页顶部引导带的 `GD/DC/KLP + inline numeric`。

## 5) 优先级判断

建议实现顺序：

1. `binary_input_grid` 的 `row-band + split-row merge`。
2. `duplicate-half-pair collapse` 与数字列锚点先验。
3. 首页/公共线分流（`header-bus`, `common-bus`, `column-head suppression`）。
4. 非标准说明行模板（如 alarm 行）与乱码区域降权。

如果只做一件事，优先做第 1 条。  
原因：这会同时修复 `S0009`、`S0012`、`S0013` 的主失真，并且能把“疑似表格页”的误判压力，从分类层转移回正确的导线页子策略层。
