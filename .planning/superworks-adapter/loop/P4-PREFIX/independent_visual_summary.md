# P4 prefix audit — independent raw-DXF identity review

## Method

逐例查看112个原始DXF底图panel；截图无绿色SW覆盖层、V1覆盖层和pipeline标注。只用原图文字、端子脚号和导线判断。若本地截图没有设备/柜体标签与目标端子形成可见关联，使用原始DXF扩大视口或单例重渲染；仍无法确证的记为uncertain。没有把`sw_identity`、pipeline字段或旧说明当作真值。

完整身份要求同时确认设备/柜体前缀及数字脚号。后缀另列判断，不把后缀正确等同于完整身份正确。`old_identity_verdict`保留旧合并脚本的判定，仅作对照；该字段此前被写死，未用于本次判读。

## Overall

| 范围 | correct | wrong | uncertain | Accuracy among determined | Confirmed-correct / all 112 |
|---|---:|---:|---:|---:|---:|
| Numeric suffix | 112 | 0 | 0 | 100.0% | 100.0% |
| Full device identity | 98 | 0 | 14 | 100.0% | 87.5% |

Pair manual decisions: yes 54, no 56, uncertain 2; manual rate among decided pairs = 54/110 = 49.1%.

Full identity has 98 visually confirmed correct, 0 visually contradicted, and 14 uncertain. The 100% accuracy is among the 98 determinate examples; 87.5% of all 112 are confirmed correct. Uncertain cases are excluded from the accuracy denominator and retained as unresolved.

## By format class

| format_class | n | correct | wrong | uncertain | Accuracy among determined | pair manual yes | no | pair uncertain | Manual rate among decided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| alpha-num | 9 | 9 | 0 | 0 | 100.0% | 9 | 0 | 0 | 100.0% |
| alpha-num-hyphen-num | 13 | 13 | 0 | 0 | 100.0% | 13 | 0 | 0 | 100.0% |
| n-number | 34 | 32 | 0 | 2 | 100.0% | 17 | 17 | 0 | 50.0% |
| section-n-number | 56 | 44 | 0 | 12 | 100.0% | 15 | 39 | 2 | 27.8% |

## By pair_kind

| pair_kind | n | correct | wrong | uncertain | Accuracy among determined | pair manual yes | no | pair uncertain | Manual rate among decided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ordinary_pair | 30 | 27 | 0 | 3 | 100.0% | 30 | 0 | 0 | 100.0% |
| semantic_mapping | 46 | 41 | 0 | 5 | 100.0% | 24 | 20 | 2 | 54.5% |
| wire_component_mapping | 36 | 30 | 0 | 6 | 100.0% | 0 | 36 | 0 | 0.0% |

## By status

| status | n | correct | wrong | uncertain | Accuracy among determined | pair manual yes | no | pair uncertain | Manual rate among decided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pass | 6 | 6 | 0 | 0 | 100.0% | 0 | 6 | 0 | 0.0% |
| review | 106 | 92 | 0 | 14 | 100.0% | 54 | 50 | 2 | 51.9% |

## Uncertain cases

| case | candidate | visible base-drawing evidence / limitation |
|---:|---|---|
| 47 | 4n1719 | 线1719可见连接到红色元件标识“2YJ3-1”；图面没有可见的4n装置标签与该端子直接相连，附近4n标题位于下方另一组虚线框。完整前缀无法独立确认。 |
| 49 | 1n208 | 黄色线号208在图面上与红色“1KK”指示回路相连；未见可将该端子归到1n装置的独立红色标签，完整身份无法确认。 |
| 60 | 3-4n604 | 线号604位于TC端子组，附近红色端子标识为3-4Q2D6；底图没有可见的3-4n装置标签与该端子直接相连，完整前缀无法确认。 |
| 62 | 1-4n229 | 线号229可见于跳闸信号回路；该视口和扩展原图均无1-4n设备/柜体标签与该线建立可见连接，完整前缀无法确认。 |
| 63 | 3-4n804 | 线号804位于TC端子组，附近红色端子标识为3-4Q2D6；底图没有可见的3-4n装置标签与该端子直接相连，完整前缀无法确认。 |
| 66 | 3-2n207 | 线号207位于绿色指示灯回路，图面标识为3-2KK；未见独立3-2n设备标签连接该端子，完整前缀无法确认。 |
| 71 | 1-1n118 | 黄色线号118位于1-KLP5输出行；原图没有1-1n装置标签与此端子直接相连，完整前缀无法确认。 |
| 72 | 2-1n112 | 黄色线号112位于2-1KLP1输出行；图中2-1n/WFB-822E-02标识对应另一组114/115等端子，没有可见连接到112的关系，完整前缀无法确认。 |
| 73 | 2-1n120 | 黄色线号120位于2-1KLP7输出行；图面没有2-1n装置标签与此端子直接相连，完整前缀无法确认。 |
| 74 | 2-1n213 | 黄色线号213位于1VP1及其线路；底图没有2-1n设备标签与此端子直接相连，完整前缀无法确认。 |
| 76 | 2-1n125 | 黄色线号125位于2-1KLP12输出行；原图没有2-1n装置标签与此端子直接相连，标题栏的输入组文字不能证明该前缀，完整身份无法确认。 |
| 77 | 2-1n117 | 黄色线号117位于2-1KLP4输出行；原图没有2-1n装置标签与此端子直接相连，完整前缀无法确认。 |
| 79 | 1-1n129 | 黄色线号129位于1-KLP11输出行；图面可见1-1Q与1-KLP元件标识，但未见1-1n装置标签与该端子直接相连，完整前缀无法确认。 |
| 87 | 1-2n201 | 黄色线号201位于1-4CD5合闸线圈回路；原图没有1-2n装置标签与此端子直接相连，完整前缀无法确认。 |

## Files

- `independent_visual_judgments.csv`: 112 row-level judgments; includes old verdict, suffix verdict, full identity judgment/reason, pair manual decision, raw screenshot file/panel, and expanded screenshot reference where used.
- `independent_visual_summary.md`: this summary and marginal counts.
- Raw screenshot assets are under `.tmp/precision_loop_20261015/P4-PREFIX-v2/full_identity_review/screenshots/`; original contact sheets have no audit overlay.
