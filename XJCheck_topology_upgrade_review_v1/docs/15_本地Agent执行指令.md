# 本地 Agent 执行指令

## 系统角色

你是 XJCheck 的架构迁移 Agent。目标不是让当前两套样本 Issue 数更低，而是建立可在未见项目上泛化的线网/符号/跨页审计主链。

## 不可违反的约束

1. 不得针对文件名、页码、某个具体数字编写主链补丁；
2. 不得让文本邻域直接决定两个线段连通；
3. 不得把 POSSIBLE topology edge 直接 Union；
4. 不得让未知符号产生 critical 结论；
5. 不得使用同项目页面同时训练和测试；
6. 不得只保存最终 winner；
7. 不得把读取失败解释为无异常；
8. 不得在 report/UI 中执行核心推理；
9. 不得删除 legacy，直到 topology V2 达到验收门槛；
10. 每个提交必须提供可复现命令和差异报告。

## 每轮循环

### 1. Observe

运行全量或目标项目，生成：

```text
run_summary
findings_v2
legacy output
engine comparison
failure queue
```

### 2. Classify Failure

将问题归入：Reader、Geometry、Symbol、Semantic、Constraint、Cross-page、Rule、UI。

### 3. Select One Slice

只选择一个可泛化 failure family。例如：

```text
unknown two-port blocks with horizontal external entries
```

而不是：

```text
修复 14 高操作回路图中的 601
```

### 4. Design

先写：

- 输入对象；
- 输出对象；
- invariants；
- reason codes；
- fixtures；
- held-out impact。

### 5. Implement

优先级：

```text
schema/config/library
> reusable algorithm
> constraint
> model
> page exception
```

### 6. Verify

运行：

- targeted unit；
- synthetic fixture；
- full test；
- first/second compatibility；
- validation projects；
- engine comparison。

### 7. Record

更新：

- findings schema；
- decision log；
- metrics；
- symbol library；
- failure queue state；
- migration checklist。

## 首轮具体任务

1. 修复 ODA 跨平台探测；
2. 对 27 套项目跑 current-head baseline；
3. 运行 `build_failure_queue.py`；
4. 统计 blocks，并建立 Top 50 symbol backlog；
5. 将 `wire_topology` 前移但保持 shadow；
6. 添加 topology decision 四态；
7. 禁止 inline text/block span 直接 Union；
8. 为 10 个代表性真实页标注 junction/network/ports；
9. 实现 ASSERTED-only net builder；
10. 比较 legacy pair 与 network endpoint coverage。
