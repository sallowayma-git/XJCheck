# XJCheck 线网识别升级审查包 v1.0

本包基于以下两份实际输入完成：

1. `XJCheck-master.zip`：当前代码、任务书、进度记录与测试；
2. `110kV变压器保护柜.zip`：27 套项目、502 张 DWG，以及每套项目对应的 `.prj`、`LdDzbInfo.xml`、`AirSwitchClassSet.xml`。

本包不是泛泛的技术建议，而是一次针对当前仓库和测试语料的架构审查。核心结论是：

> 将“邻域找数字后直接生成 Pair”的逻辑退出连接关系主链，改为“CAD 原始实体 → 几何拓扑 → 符号端口 → 电气网络 → 文本语义附着 → 跨页端点身份 → 规则校验”。

GNN 暂不作为主引擎。第一优先级是确定性线网、符号/端口依赖库和全局约束求解；GNN 仅在这些基础稳定后用于候选边、符号族和文本归属的消歧。

## 首先阅读

- `MASTER_TASKBOOK.md`：需求、架构、算法、代码改造、Agent 工作流、任务分解与验收合一的主任务书；
- `MIGRATION_CHECKLIST.md`：可以直接逐项执行的迁移清单；
- `docs/01_实证审查结果.md`：本次对仓库和 502 张 DWG 语料的实际发现；
- `docs/11_代码改造任务分解.md`：精确到模块、接口和里程碑的开发任务；
- `docs/15_本地Agent执行指令.md`：给本地编码 Agent 的执行约束和循环协议。

## 实际审查产物

`reports/` 包含：

- 27 个项目、502 张 DWG 的项目级和页面级清单；
- 505 个端子排侧车记录；
- 第三组相对前两组新增的页面标题/结构族；
- 静态失败风险队列；
- 推荐的按项目隔离 benchmark split；
- 三组预览联系表和代表性页面预览；
- 当前环境下真实运行 `10000 远动通信柜` 的降级结果。

## 当前环境限制

当前容器没有安装 ODA File Converter、RealDWG 或 LibreDWG，因此无法在此环境中完成 502 张 DWG 的实体级全量抽取。已完成并纳入本包的实测包括：

- 解包、项目识别、页序和类别恢复；
- `.prj` / `LdDzbInfo.xml` 解析与一致性检查；
- 当前代码静态审查与 323 项测试运行；
- 当前 CLI 在无转换器环境下的真实降级运行；
- 502 张 DWG 内嵌预览的无依赖提取及视觉结构抽样；
- 可在安装 ODA 的目标环境直接运行的全语料基线、失败队列和符号库 bootstrap 脚本。

因此，文档中不会把“转换器缺失导致 0 实体”错误表述为识别算法准确率。实体级失败闭环需要按 `scripts/run_corpus_baseline.py` 在你的实际 Windows/ODA 环境执行。

## 建议执行顺序

```text
1. 安装 ODA File Converter，并修复跨平台 Reader Adapter
2. 运行 scripts/run_corpus_baseline.py 生成 27 套项目 current-head 基线
3. 运行 scripts/build_failure_queue.py 生成失败队列
4. 冻结 legacy golden，不再追加页面专用补丁
5. 前移 wire_topology，建立 Geometry Graph 与 TopologyDecision
6. 运行 scripts/bootstrap_symbol_library.py 建立高频符号/端口待标注清单
7. 接入 Symbol Registry、Port Binder 和 Constraint Resolver
8. 以项目为单位做 held-out 验证
9. 最后评估 ranker / GNN 是否有增益
```

## Executable helper scripts

The `scripts/` directory contains tested local helpers:

- `run_review_loop.py`: inventory -> baseline -> failure queue -> symbol bootstrap;
- `run_corpus_baseline.py`: isolated per-project current-head execution;
- `build_failure_queue.py`: page-level failure-family queue;
- `bootstrap_symbol_library.py`: high-impact block review backlog;
- `compare_engines.py`: legacy versus topology-V2 comparison;
- `corpus_inventory.py`: sidecar/page/route inventory without DWG conversion;
- `extract_dwg_preview.py` and `batch_extract_previews.py`: embedded preview visual QC;
- `validate_package.py`: delivery integrity check.

A typical target-environment command is:

```bash
python scripts/run_review_loop.py \
  --repo /path/to/XJCheck-master \
  --data /path/to/110kV-dataset \
  --output /path/to/review-run \
  --config /path/to/XJCheck-master/configs/default.yml \
  --oda "/path/to/ODAFileConverter"
```
