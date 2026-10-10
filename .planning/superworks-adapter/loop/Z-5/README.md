# Z-5：剩余 13 条 R-PAIR-MISSING-SIDE 逐条核查（只读）

数据：`.tmp/superworks_round9_full`（未改 src/，未 git，未全量回放，未删除数据）。截图 `png/`（13 张，DXF 直接绘制，橙=线组，红=缺侧，蓝=框选）。明细 `details.json`（13 项）。

## 1. 结论
- 13 条 = A 组 8（component_mapping，竖向 FJL 块）+ B 组 5（G3，MARK 层水平短线）。A 组 8 条为 p003 的 4 个唯一 pair，加上 p041–p044 的 PCM0023/PCM0027 各在两次运行中各报 1 次。
- SW 元数据均无法给出这 13 条的缺侧身份：p003 无 SW 标签；p041–p044 的底端端口在 SW 中无标签；B 组在 14–15 单位内无 SW 标签或端口。
- 分类：A1 底端双重叠标签 4（图面缺陷候选）；A2 底端端口无任何外部标注 4（图面未标注，备用脚或漏标）；B 跨页裸 n 标记 5（跨页线，非缺陷）。
- 更正 L-12：其「一线两目标」口径 b 与 S1 建议对 p041–p044 不成立。`&` 多值标签挂在端口 1（顶端，2-1KLP13-1），已被 4 条 SW pass 消费；端口 2 底端无标签，不能用它补齐。

## 2. 逐条摘要
- A1 p003 S0012 PCM0002/0005/0008/0012：底端端口 2 下方两条文字叠放于同一点（如 8nB01 与 8n401，Δx=0.02）。数字 8n4xx 与普通配对 PC0029/31/33/37（1↔8n4xx）被「Covered by component_mapping」丢弃。同页 PCM0010 仅一条 8n820 即 pass。他页无对应 8n4xx。
- A2 p041–p044 PCM0023/PCM0027：底端 port 2（y=38.75）下方 22 单位内无文字或引线，仅两个红色标记（y=37.5、33.5）。
- B1 p062 PC0019（52n）、B2 PC0125（58n）、B3 p071 PC0053（1n/51n/25n）、B4 p075 PC0232（1-26n）、B5 PC0440（2-26n）：缺侧为裸 n 线号。他页仅有 DIM/MXB 同名文字，无同形 MARK 线段；PC0053 的 1n/25n/51n 簇在 S0008–S0011 逐页坐标完全相同，无法唯一配对。

## 3. 为何没用上（代码位置）
- A1：component_diagrams.py:1481 `_strip_endpoint_conflicts` 将同位置异值标签判为冲突，端点置空（:1915 coincident_conflicting_labels）。component_diagrams.py:156 `consumed_group_ids.add` 在端子未解析时仍执行，page_extractors.py:355–377 据此把 PC0029 类普通配对标为 discard。
- A2：component_diagrams.py:1442 `_nearest_strip_external_endpoints` 底端窗口（1–9 单位）内无候选（:1915 external_endpoint_missing）。
- B：config.py:140–145 numeric_suffix_patterns 仅接受 n\d{3,}；candidates.py:249、:1949 将 52n、1-26n 判为 not_numeric 而成为噪声；config.py:99 将 MARK 列为去优先图层；project_graph.py:256 跨页候选只使用 AUTHORITATIVE（SW）身份。

## 4. 分类与通用修复建议
| 类 | 条数 | 建议 | 位置 |
|---|---:|---|---|
| A1 重叠双标签 | 4 | 同位置冲突且一值为 n\d{3} 时，若同页同类端口有单标签先例则取数字值，否则保持 review；不得丢弃 1↔n 普通配对 | component_diagrams.py:1481、:156；page_extractors.py:355 |
| A2 端口无标注 | 4 | 新增类别 unlabelled_port（备用脚候选），降级或单列；不做 SW 补全 | component_diagrams.py:1915 |
| B 跨页裸 n 标记 | 5 | 新增类别 cross_page_marker：MARK、水平、单端裸 n 文字、另一端无接触（排除近平行线，PC0053 另有 0.67 单位的近平行长线） | pairs.py:69–75；rules.py:430 附近 |

附带：线组构造把 PC0053 两条近平行短线合并为一组（端点取平均 y=281.70）。p041–p044 的 pages sheet_title 取到了 SW「&」文字（cad_extract.py:294，来源未核实，不影响配对）。

## 5. 需用户决定的口径
1. A1：8nB0x 与 8n4xx 哪个为真实外部端子，需对照原 DWG（同页 PCM0010 先例支持数字值）。
2. A2：底端无标注的端口 2 是备用脚（抑制）还是漏标（保留 review）。
3. B：裸 n 标记是否定为跨页标记并移出 R-PAIR-MISSING-SIDE（与 L-12 S4 方向一致）。
4. L-12 口径 b 对本组不适用，L-12 的 S1 建议需修正。
