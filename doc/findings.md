# Findings

状态：已完成当前仓库、任务文档与样本 DWG 的首轮读图盘点，进入实现补齐与样本验证阶段。

更新时间：2026-07-03

用途：作为当前阶段的读图发现文档，记录已经确认的样本事实、工程约束、当前仓库实现状态，以及会直接影响实现与验收的关键结论。后续每完成一个里程碑，都应回写本文件。

## 1. 当前任务理解

基于 [任务书.md](./任务书.md) 和 [deep-research-report.md](./deep-research-report.md)，本项目 MVP 的目标明确为：

- 输入一套项目级 DWG 图纸。
- 在本地离线环境中抽取水平连接线两端数字。
- 建立 pair，并执行跨页一致性校验。
- 输出带证据链、置信度和定位信息的 findings / audit 报告。

这不是完整 CAD 软件，也不是电气语义理解系统。当前优先级仍然是“证据先行”，而不是“黑盒结论先行”。

## 2. 当前仓库真实状态

当前仓库不是空目录重建状态，已经存在可运行的 Python 实现骨架和单元测试：

- [pyproject.toml](/F:/workspace/XJToolkit/pyproject.toml)
- [src/dwg_audit/cli.py](/F:/workspace/XJToolkit/src/dwg_audit/cli.py)
- [src/dwg_audit/pipeline.py](/F:/workspace/XJToolkit/src/dwg_audit/pipeline.py)
- [src/dwg_audit/ingest](/F:/workspace/XJToolkit/src/dwg_audit/ingest)
- [src/dwg_audit/extract](/F:/workspace/XJToolkit/src/dwg_audit/extract)
- [src/dwg_audit/audit](/F:/workspace/XJToolkit/src/dwg_audit/audit)
- [src/dwg_audit/report](/F:/workspace/XJToolkit/src/dwg_audit/report)
- [src/dwg_audit/ui/app.py](/F:/workspace/XJToolkit/src/dwg_audit/ui/app.py)
- [tests/unit](/F:/workspace/XJToolkit/tests/unit)

直接结论：实现不是从零开始，而是在已有主链路上对齐任务书、补足抽取能力、增强证据链并完成样本验证。

## 3. 样本项目盘点

当前 `test/` 下有两套样本：

1. [110kV变压器保护柜](/F:/workspace/XJToolkit/test/110kV变压器保护柜)
2. [变压器测控柜(2圈变，2台测控)](</F:/workspace/XJToolkit/test/变压器测控柜(2圈变，2台测控)>)

已确认事实：

- `test/` 下共有 67 个文件。
- 其中 DWG 扩展名文件 54 个，总大小约 4.78 MB。
- `110kV变压器保护柜` 可作为主验证集。
- `变压器测控柜(2圈变，2台测控)` 更适合作为损坏容错集。

## 4. DWG 有效性事实

对当前 `test/` 目录的 DWG 头部检查后，已确认：

- 有效 DWG 头（`AC10*`）共 29 个。
- 无效 / 损坏头共 25 个。

项目分布：

- `110kV变压器保护柜`：有效 28，无效 2。
- `变压器测控柜(2圈变，2台测控)`：有效 1，无效 23。

直接结论：

- 转换、抽取、审计必须按文件级容错设计。
- 不能要求一个项目内所有页都成功转换后才继续。
- `manifest` 和 `findings` 必须记录每张图的转换成功、失败和失败原因。

## 5. Sidecar 与排序发现

### 5.1 `.prj`

两套样本的 `.prj` 并不是同一种格式：

- 保护柜 PRJ 是 `GBK/CP936` 文本格式，可解析出 `sheet_order / category / title`。
- 测控柜 PRJ 不是同类可读文本，更像二进制或私有序列化格式。

实现要求：

- `.prj` 解析必须同时支持“可读文本 PRJ”和“不可解析 PRJ”两条路径。
- 当 `.prj` 无法解析时，系统必须回退到文件名排序与标题推断，而不是整项目失败。

### 5.2 `LdDzbInfo.xml`

两套样本的 `LdDzbInfo.xml` 均可稳定提取设备名和端子排信息，可进入：

- `manifest.json`
- `findings/terminal_strips.parquet`
- findings 摘要中的端子排元数据说明

## 6. 页号与命名事实

保护柜样本中存在重复页号：

- `04 标牌及压板内容示意图.dwg`
- `04 交流回路图1.dwg`

直接结论：

- `sheet_no` 不能作为唯一键。
- 必须独立维护 `sheet_id` 与 `sheet_order`。
- 报告与证据链中必须同时保留 `sheet_order + filename + sheet_no`。

## 7. ODA 与转换约束

已确认本机安装了 ODA File Converter：

- `C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe`

同时确认了两个工程约束：

- ODA 不一定在 PATH 中，需要代码显式探测或补 PATH。
- ODA 对中文路径不稳定，因此正式实现应优先把待转换 DWG 复制到 ASCII staging 目录后再转换。

当前仓库实现已经采用 `cache/odafc_stage` 作为 staging 目录，并在转换时为每个源文件记录状态。

## 8. 当前实现能力盘点

当前代码已覆盖以下主链路：

- 项目扫描、DWG 头校验、页号/标题/类别推断
- `.prj` / `LdDzbInfo.xml` sidecar 解析
- ODA 转 DXF
- DXF 文本、线段、块抽取
- 水平线组归并
- 端点数字候选匹配
- Pair 构建
- 规则审计
- Findings / report 输出
- 最小 Streamlit 查看界面

本轮实现补齐后，重点会放在：

- findings / audit 目录结构与任务书对齐
- CLI 命令表面与任务书对齐
- `ATTRIB`、`POLYLINE`、manual bbox 抽取能力补足
- Issue 证据链增强
- 单元测试与真实样本链路验证

## 9. 主验证集与容错集策略

当前最合理的执行策略是：

1. 以 `110kV变压器保护柜` 作为主验证集，验证完整 findings -> audit 闭环。
2. 以 `变压器测控柜(2圈变，2台测控)` 作为损坏容错集，重点验证失败页记录与整项目不中断。
3. 不以“所有 DWG 均成功转换”作为阶段性通过条件。

## 10. 当前待确认点

以下问题仍需通过代码跑通后确认：

- 主验证集中的对象主要位于 `ModelSpace` 还是需补 `PaperSpace`。
- 图框与标题栏的启发式裁剪是否足够稳定。
- `ATTRIB` 进入文本候选后，数字候选召回率变化如何。
- 主验证集上的 Pair 精度、低置信度比例与主要误报来源。
- 默认启用的规则集中，哪些适合保留为自动 issue，哪些更适合先进入 review。

## 11. 下一步

下一步执行顺序：

1. 对齐 findings / audit 输出目录与 CLI 命令。
2. 补足 CAD 抽取中的 `ATTRIB`、`POLYLINE` 与 manual bbox。
3. 增强 Pair / Issue 证据链。
4. 补充单元测试并运行 `pytest`。
5. 用 `test/` 样本跑真实链路，记录 findings 与 audit 的实际输出结果。
