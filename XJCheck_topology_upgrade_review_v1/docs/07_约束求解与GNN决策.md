# 约束求解与 GNN 决策

## 1. 推荐顺序

```text
规则/几何候选
-> 全局约束求解
-> 可解释 ranker
-> 异构 GNN（仅在证明确有必要时）
```

## 2. CP-SAT 变量示例

```text
x_bridge[c]      候选 gap 是否接受
x_port_bind[p,n] port p 是否绑定 net n
x_text_bind[t,e] text t 是否绑定 endpoint e
x_cross[a,b]     endpoint a/b 是否跨页匹配
```

硬约束：

- 每个 port 最多绑定一个主 net；
- 每个 terminal token 最多绑定一个主 endpoint；
- REJECTED topology edge 永不选择；
- symbol isolated ports 不得合并；
- 一个 endpoint 在一对一模式下最多一个跨页 counterpart；
- incomplete reader page 不参与 hard audit。

软约束：

- 距离更近；
- 方向一致；
- sidecar prefix 匹配；
- reciprocal；
- 同一项目重复模式；
- 少用低置信 bridge；
- 少产生未标注 open endpoint。

## 3. 模型前的树模型

在标注量有限时，优先训练：

- `bridge_valid_ranker`；
- `text_attachment_ranker`；
- `symbol_family_ranker`；
- `crossing_classifier`。

优点：

- 可导出 feature importance；
- 易校准；
- CPU 推理；
- 与 CP-SAT 自然结合；
- 失败样本更易分析。

## 4. 异构 GNN 输入

节点特征：

- segment 几何、图层、长度、角度；
- junction 类型与 degree；
- block fingerprint；
- port local/global geometry；
- text token 类型与位置；
- page zone；
- sidecar prior。

边类型：

- touches；
- intersects；
- near；
- aligned；
- inside；
- same_row；
- same_column；
- block_owns；
- port_candidate；
- text_candidate；
- cross_page_candidate。

## 5. 标签与数据泄漏

标签单位必须明确：

- junction decision；
- bridge decision；
- symbol family；
- port binding；
- text role；
- text attachment；
- cross-page match。

禁止用同一项目的页面分别进入训练和测试。相同 block definition 的近重复实例也应防止跨 split 泄漏。

## 6. 模型上线策略

```text
OFF -> SHADOW -> REVIEW_ASSIST -> LIMITED_AUTO
```

- SHADOW：仅记录预测；
- REVIEW_ASSIST：给人工排序；
- LIMITED_AUTO：只对校准后的高精度区间自动选择；
- 永不直接产生 critical issue。

## 7. 校准

使用 reliability diagram、ECE、precision-at-threshold。业务阈值按“自动错误 precision”设定，不按总体 accuracy 设定。
