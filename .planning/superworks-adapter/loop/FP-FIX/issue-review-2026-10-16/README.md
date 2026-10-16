# FP-FIX 新增问题逐例截图复核

本目录归档 FP-FIX 源码快照 `29a6c07` 的 77 项目回放中新增的 401 条 `R-RECOGNITION-GAP/unpinned_element` 页面摘要问题。

- 逐例结论：401 `valid_review`、0 误报、0 无法确定。
- 每条记录有一张独立截图；另附 67 张联系表用于快速浏览。
- `visual_judgments.csv` 是逐例判定和截图索引；`screenshots/manifest.json` 保留问题、图纸、端口和 DXF 相对路径信息。
- `summary.json` 汇总判定计数；`artifact_hashes.csv` 记录归档文件的 SHA-256 和字节数。

判定依据是截图中高亮的走线均连到已识别的橙色端子一端，另一端接到无法从图面确定脚号或身份的元件引脚。因此这些项目仍需要审核。回放 DXF 与源码快照位于本机 `.tmp`，未包含在本目录；逐例截图及判定可直接复查。
