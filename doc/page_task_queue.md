# Page Task Queue

更新时间：2026-07-06

说明：

- Coordinator 输入基于当前第二套样本实跑产物：
  - [pages.parquet](/F:/workspace/XJToolkit/.tmp/phase10_page_findings_second/2_2/findings/pages.parquet)
  - [page_findings/](/F:/workspace/XJToolkit/.tmp/phase10_page_findings_second/2_2/findings/page_findings)
- 第一轮不全量铺开 `52` 张图，而是先按三批推进。
- 当前先执行第一批：疑似“表格化 / 网格化最重”的页面，用来定义 `TableExtractor` 与 `WireDiagramExtractor` 的边界。
- 这些 Sheet Analyst 产物是内部分析记录，不是产品默认交付目录契约。
- Sheet Analyst 当前统一写入：
  - `doc/page_findings/batch1/<sheet_id>.md`
  - `doc/page_findings/batch1/<sheet_id>.json`

## Batch 1: Suspected Table-Like / Grid-Heavy Pages

| sheet_id | filename | 初始图种猜测 | 优先级 | 负责人状态 |
|---|---|---|---|---|
| `S0008` | `08 测控1开入回路图1.dwg` | 二次原理图（疑似强网格化，需判定是否应引入表格型专用策略） | `P0` | `completed` |
| `S0009` | `09 测控1开入回路图2.dwg` | 二次原理图（疑似强网格化，需判定是否应引入表格型专用策略） | `P0` | `completed` |
| `S0012` | `12 测控2开入回路图1.dwg` | 二次原理图（疑似强网格化，需判定是否应引入表格型专用策略） | `P0` | `completed` |
| `S0013` | `13 测控2开入回路图2.dwg` | 二次原理图（疑似强网格化，需判定是否应引入表格型专用策略） | `P0` | `completed` |

### Batch 1 共识（Sheet Analyst 交付后）

四页结论高度一致，不再是“疑似表格页”：

- 四页全部判定为 `二次原理图 / 开入回路图`，不是表格页，应继续走 `WireDiagramExtractor`，但要新增 `grid-aware / row-banded` 子模式。
- 主结构为三列重复横向回路（x≈72.5-145 / 197.5-270 / 322.5-395），16 个标准行带，y 步长约 10。
- 端子数字主源是 DIM 层独立文本，落在三个稳定列锚点 x≈90.6 / 215.6 / 340.6。
- 首页变体（`S0008`、`S0012`，标题 `BINARY INPUT 1`）顶部 y≈245-265 多一条公共/电源引导带，含 `GD/DC/KLP` 与行内数字 `231/232/331/332/532`，需单独分流。
- 主失败模式：同一物理行被符号块切成两段 pair（`?->X` / `X->?`），这是当前 `0 high-confidence` 的根因，不是页型走错。
- `table_like_geometry=False` 在四页上全部成立，证明“强网格化 ≠ 表格页”。

下一步进入 Type Reviewer 横向复核 → Findings Integrator 汇总 backlog → Script Planner 拆任务。

## Batch 2: Terminal / Component Pages

| sheet_id | filename | 初始图种猜测 | 优先级 | 负责人状态 |
|---|---|---|---|---|
| `S0019` | `19 元件接线图1.dwg` | 元件接线图 | `P1` | `completed` |
| `S0020` | `20 元件接线图2.dwg` | 元件接线图 | `P1` | `queued` |
| `S0021` | `21 左侧端子图1.dwg` | 屏端子图 | `P1` | `completed` |
| `S0023` | `23 右侧端子图1.dwg` | 屏端子图 | `P1` | `queued` |

### Batch 2 当前共识（已完成页）

- `S0019` 不该回退成普通 `WireDiagramExtractor`，也不该照搬 `S0020` 的 vertical 元件页规则。
- `S0019` 更像 `ComponentDiagramExtractor` 下的 `horizontal_component_block_pin` 子模式：
  - 短水平导线负责定位
  - 真实数字主源来自 `INSERT` 展开后的块内虚拟文本
  - 外部 `HD / GD / n### / K-# / JD#` 更像语义标签，不应直接与块内脚位硬配成 pair
- `S0021` 不是表格页，而是 `TerminalDiagramExtractor` 下的端子列带页。
- `S0021` 的数字匹配更依赖稳定列带 + 行锁定 + 端子代号正则抽值，而不是通用端点最近邻。
- Batch 2 已经证明：“元件接线图”和“端子图”都值得走页型专用子策略，而不是继续往统一大脚本里加全局阈值。

## Batch 3: Ordinary Wire Diagrams

| sheet_id | filename | 初始图种猜测 | 优先级 | 负责人状态 |
|---|---|---|---|---|
| `S0004` | `04 交流回路图1.dwg` | 二次原理图 | `P2` | `queued` |
| `S0005` | `05 交流回路图2.dwg` | 二次原理图 | `P2` | `queued` |
| `S0006` | `06 直流回路图.dwg` | 二次原理图 | `P2` | `queued` |
| `S0010` | `10 测控1控制回路图1.dwg` | 二次原理图 | `P2` | `queued` |

## Analyst Template

```md
# S001 / 08 xxx.dwg

- page_type:
- confidence:
- structure_summary:
- recognition_strategy:
- number_matching_strategy:
- high_confidence_signals:
- failure_modes:
- script_change_suggestions:
```
