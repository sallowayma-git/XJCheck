# Script Plan / Wire Grid Batch

范围：

- `S0009`
- `S0012`
- `S0013`
- `S0008`

结论前提：

- 这批页不进入 `TableExtractor`
- 继续走 `WireDiagramExtractor`
- 需要新增页型子策略，而不是继续调全局阈值

## Page-Type Split

主页型：

- `binary_input_grid`
  - 适用于 `BINARY INPUT 1/2`
  - 三列固定列带
  - 主体为横向重复回路行

首页变体：

- `binary_input_first_page_header_bus`
  - 额外处理顶部 `GD/DC` / 公共线 / 电源头引导带

尾页/说明行变体：

- `binary_input_tail_rows`
  - 抑制页底尾线
  - 抑制 `Power loss alarm` / `Device alarm` 这类说明行误入普通配对

## Dev Tasks

### 1. 分类与路由

- 在页分类阶段新增 `BINARY INPUT 1/2` 页型子标签
- 保持 route target 为 `WireDiagramExtractor`
- 增加防误送规则：
  - 三列稳定导线页不进入 `TableExtractor`

### 2. 导线抽取层

- 新增 `row-band clustering`
  - 识别 `y≈85-235`
  - 约 `10` 单位节距的重复行带
- 新增 `split-row merge`
  - 同一 row band 内
  - 两段水平线被固定短符号块隔开时
  - 合并成一个逻辑通道
- 新增 `header/footer suppression`
  - 抑制 `y≈77.5` 的列头短线
  - 分流 `y≈245-265` 的首页引导带

### 3. 候选与配对层

- 新增列锚点优先级
  - 优先保留 `x≈90.6 / 215.6 / 340.6` 附近纯数字
- 把以下文本从 numeric 主链剥离：
  - `BI xx`
  - `QDxx`
  - `GDxx`
- 新增 `duplicate-half-pair collapse`
  - 同 `y`
  - 同数字
  - 相邻半段共享一个符号块间隔
- 为告警说明行增加单独失败原因

### 4. 诊断与回归

- 在 findings / SQLite 中增加页型子标签：
  - `binary_input_grid`
  - `binary_input_first_page_header_bus`
- 新增 failure reason：
  - `split_by_symbol_block`
  - `duplicate_single_sided_hits`
  - `header_bus_inline_numeric`
  - `tail_row_suppressed`
- 建立 batch regression：
  - `S0008`
  - `S0009`
  - `S0012`
  - `S0013`

## Implementation Order

1. `row-band clustering`
2. `split-row merge`
3. `duplicate-half-pair collapse`
4. `BI/QD/GD` 语义标签通道
5. 首页引导带 / 尾部说明行分流

## Success Criteria

- 这批页继续由 `WireDiagramExtractor` 处理
- 镜像 `missing-left/right` 明显下降
- 同一数字跨小符号块的重复单侧命中显著下降
- 顶部公共线与页底说明行不再主导 issue 噪声
