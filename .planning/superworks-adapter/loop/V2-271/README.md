# V2-271 疑似错绑复核

## 结论

原 GAP-TRIAGE 报告中的 `C_v2_new=271` 不是已确认的 V2 错绑数。它来自只读分析工具的文字联接错误：`build_features.py` 以裸 `handle` 建立项目级文字映射，没有把 `file_id` 放入键。DXF 句柄只在单张图纸内唯一；不同图纸复用同一句柄时，工具可能拿另一张图的文字与当前端子身份比较。

旧的 271 个案例无需进入生产修复队列。按 `(file_id, handle)` 联接后，旧全量输出 316 个原始差异和后续 round26 输出 93 个原始差异都归零。`271` 是旧输出 316 个差异经 A/B/D 分类优先级吸收 45 条后的子集，不能与 316 或 93 混为同一人口。

这项核验只否定了“V2 文字值与端子身份冲突”的旧证据；它没有测量 V2 几何挂接本身的准确率。若以后单独开放 V2 几何挂接，仍需按新候选池重新抽截图。

## 可复核证据

- 错误联接位置：[`GAP-TRIAGE/tools/build_features.py`](../GAP-TRIAGE/tools/build_features.py)，读取 `texts.parquet` 时只选 `handle,text`，随后用 `text_handle` 查找；缺少 `file_id`。
- 错误分类位置：[`GAP-TRIAGE/tools/classify.py`](../GAP-TRIAGE/tools/classify.py)，将错误联接得到的 `v2_end_value` 与已知端子身份比较并生成 `C_v2_new`。
- 历史计数、输入和截图定义见 [`GAP-TRIAGE/README.md`](../GAP-TRIAGE/README.md) 的 C 类与限制说明；旧五例截图依赖错误的文字联接，不能作为错绑证据。
- 句柄碰撞实例：p009/F0011/S0011 与 p009/F0012/S0012 都有文字句柄 `2835E`。前一图纸的值是 `1QD22`，后一图纸的值是 `1QD28`。把项目内文字压成 `handle -> text` 会跨图取值；前一图纸的端子身份与它本图文字 `1QD22` 一致。
- 独立重算摘要：`.tmp/precision_loop_20261015/findings.md` 记录旧输出裸句柄差异 316、round26 裸句柄差异 93、文件作用域联接后两者均为 0。最新 P2 可见性修复后完整回放 `.tmp/precision_loop_20261015/p057_slice_10` 再次得到裸句柄差异 **93**、文件作用域差异 **0**；该回放 77/77 项目完成，0 失败，`R-RECOGNITION-GAP` 共 12,436 条。
- 最新回放复核实例：p024/F0007/S0007，issue `ISWe596dc08cf2307cd42b7`，线组 `GW0129`。候选文字句柄 `C657` 在 F0007 的值为 `U3D1~2`，而另一图纸 F0020 的同句柄值为 `2`。裸句柄映射产生差异，文件作用域值与已知端子身份 `U3D1~2` 相同。

## 处置

- 不改 V2 生产模块、`symbol_port_proposal.py` 或 pair 状态。
- 不把旧 C_v2_new 五例截图作为错绑样本，也不对这 271 条追加生产截图复核；其比较前提已经被文件作用域联接否定。
- 后续若复用 GAP-TRIAGE 的 V2 统计，应先按 `(file_id, handle)` 查文字，再把几何挂接与文字身份分开取样和报告。

