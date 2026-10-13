# 第二十五轮后的 V1 剩余贡献

2026-10-13 接手会话 `367e37bd-5006-413b-a449-e1c665a8b237`。生产代码为 `d11d0b3`，输入为 `.tmp/superworks_round25_full` 的 77 个项目。仅重算统计，未修改生产识别、审计规则或配对状态。

## 结论

**V1 仍需保留，当前不宜整体改为只出 review。** 没有任何同值 SW 对应的 V1 pass 从 round23 的 7,583 条降到 round25 的 **1,175 条**，但这些包含元件引脚直连和剩余背板表格。另有 640 条只能找到 SW 非 pass、212 条只在其他页有对应、70 条仅有 SW 部分证据，不能当作已经被同页 SW pass 替代。

“没有同值 SW 对应”只是全项目无序端点字符串比较结果，不代表物理连接均正确，也不代表 SW 完全看不到这些对象。P2 背板佐证只核对行号、外部端子与装置，不能当作完整列身份或电气证明。不会为了减少旧链数量而直接降级。

## 最新计数

| 口径 | 条数 |
|---|---:|
| 终态 pairs | 178,832 |
| pass / review / discard | 79,125 / 26,997 / 72,710 |
| pass：SW 产出、修正或非部分标注（不含下两类） | 72,981 |
| pass：背板行+端子+装置佐证 | 4,047 |
| pass：SW 部分证据 | 70 |
| pass：没有 SW 证据的纯 V1 | 2,027 |
| 其中同页存在同值 SW pass | 0 |
| 其中同页只有同值 SW 非 pass | 640 |
| 其中只有其他页同值 SW 对应（不限状态） | 212 |
| 其中全项目没有同值 SW 对应 | **1,175** |

1,175 条占当前 pass 的 1.49%。它们是待调查的连接主张，不能等同于 1,175 根已确认独立且正确的导线。没有同页同值 SW 对应的纯 V1 pass 为 1,387 条（1,175 + 212）；不能把跨页旁证算作同页重复。

### 1,175 条的构成

| pair_kind | 条数 | 细分 |
|---|---:|---|
| wire_component_mapping | 842 | scoped_visible_prefix 466、inline_body_port 233、first_prefixed 118、inline_klp 25 |
| table_mapping | 218 | 背板虚拟表 179、端子表表头映射 39 |
| component_mapping | 99 | strip_two_port 76、small_port_box 12、kk_multi_port 6、inline_two_port 5 |
| semantic_mapping | 16 | strip_two_port_endpoint_bridge |

842 条导线型映射不等于剩余穿符号错误数，其中可能有真实非 SW 元件引脚直连。必须按图面和块属性核验，不能仅凭旧函数名称弃用。179 条未佐证背板表中包含 p057 已审计的 95 条模板前缀候选；这 95 条是已知 V1 前缀错误，仍应保留候选而非计作确认正确连接。

## 取代与问题核验

- I 类台账 **28,481** 条，J 类 **32** 条。逐条检查终态旧 pair 为 discard，且至少一个替代 pair 在终态仍是 pass，全部通过。台账 old_pair 的旧状态不用于当前计数。
- 4,047 条背板佐证逐条检查引用的伙伴在终态存在并为 pass；其中同页 3,612，其他页 435。此检查确认引用存活，不重复宣称电气正确性。
- issue 共 **38**：SW 冲突 17、低置信 13、缺端 4、多对一 3、跨页冲突 1，与会话末尾一致。
- 6 条 issue 直接锚定纯 V1：p039 两条多对一，p041–p044 四条无标注端口。剩余 p050 跨页问题锚定的是已有背板佐证的 V1 表格配对；佐证不使它自动免审。
- 这些是当前依赖定位，不是“降级后消失数量”预测。降级会不会隐藏旧问题或新增低置信问题，必须运行真实审计反事实后才能确定。

## 为什么本轮不直接改状态

1. `src/dwg_audit/audit/rules.py:1971` 的 `_high_confidence_pairs` 同时读 `status`、`confidence_bucket` 和 table_mapping。只改为 review 可能仍被某些高置信规则读取，不能保证想要的降级语义。
2. `rules.py:865` 的 `_run_pair_low_confidence` 对 component_mapping 的处理会受 pass 改 review 影响，人工核验队列可能增加。
3. `src/dwg_audit/pipeline.py:282` 的 SW 抽取仍消费旧链 line_groups。替换配对判定层不能推导出旧几何提取层可以删除。
4. V2 既有的端子几何绑定和面板 IGNORE 路径仍需保留。本轮未重新复现 V2 提议，也不把 round23 的 V2 数字冒充 round25 新统计。

## 后续切片

优先对 842 条导线型元件映射和 99 条元件映射分层核验：区分非 SW 图块真实脚号、未解析 SW 脚号、穿符号残留及已有跨页旁证。调查必须使用 DXF 块属性/引脚标记与图面，先建立通用准入或拒绝证据，再考虑生产修改。背板 179 条另按缺复合装置名、模板前缀和无伙伴分类；p057 不写项目特判。

已生成逐条定位清单 `results/independent_pass.csv`、`results/pure_legacy_pass.csv`（可再生，不提交）。下一轮可以直接按 project_id、pair_id、filename、sheet_id、text_id 回到图面定位。

## 复现与验证

```powershell
python -X utf8 .planning/superworks-adapter/loop/LEGACY-ROUND25/census.py --run .tmp/superworks_round25_full --out .planning/superworks-adapter/loop/LEGACY-ROUND25/results
```

保留 `results/summary.json`、`results/issue_dependencies.csv`、`results/input_manifest.json`；输入 SHA256 可核对原始 308 个 parquet。本脚本不会覆盖旧 round23 普查。

复核：另用原 LEGACY-CENSUS 的 `load_project` 独立建立来源和端点集合，加入背板 key，重新读 77 项目，得到相同 2,027 / 640 / 212 / 1,175。计数守恒、I/J 存活伙伴和背板伙伴检查均通过。初步探子给出的 1,384 在主线程复核时未复现，未采用。

本轮只改调查脚本和文档，未重新跑识别全量回放或 pytest；会话报告的 2,170 项测试通过属于 d11d0b3 的历史验证。
