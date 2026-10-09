# Round 4 C: 人工复核抽样截图

数据：`F:\workspace\XJToolkit\.tmp\superworks_round3_full`（第三轮，77 项目）；基线：`.tmp\superworks_baseline_timed`。
脚本：`round4_samples.py`（生成 96 张 issue 图、6 张接触表、index.json）；`overlap_check.py`（文字重叠调查，输出在 `overlap/`）。

## 各规则数量（全量 / 抽样）
- R-CROSS-PAGE-CONFLICT：23 / 23
- R-SUPERWORKS-CONFLICT：21 / 21（符号由 message 中的 SW 句柄经 entitydb 定位）
- R-ONE-TO-MANY：11 / 11
- R-DUPLICATE-PAIR：1 / 1
- R-PAIR-LOW-CONFIDENCE：10 / 10（其中 in_baseline=True 为 10 / 10）
- R-MANY-TO-ONE：643 全量，分桶后取前 6 桶，每桶 5 条，共 30 条

## R-MANY-TO-ONE 分桶（与 round3_composition.py 同一键；种子 20261009）
- B1 127 条：kinds=table_mapping，src=superworks|table_mapping，n=2，sheets=2
- B2 84 条：kinds=component_mapping|table_mapping，n=2，sheets=2
- B3 69 条：kinds=ordinary_pair|table_mapping，n=2，sheets=2
- B4 53 条：kinds=table_mapping，src=superworks，n=2，sheets=1
- B5 51 条：kinds=component_mapping，n=2，sheets=1
- B6 45 条：kinds=component_mapping|table_mapping，n=2，sheets=2

## 输出
- `samples/<组>__<项目>__<issue>.png`：每个 issue 一张，含全部相关配对（pair_id ∪ primary ∪ related）的局部图，红框为左右端点；SW 符号为红框外框、端口为橙框
- `samples/contact_<RULE>.png`：每条规则一张缩略接触表
- `index.json`：96 条记录（classification / reason 为 null）；240 个配对明细，其中 223 个已渲染

## 未渲染项
- 17 个 SW 配对无坐标（R-SUPERWORKS-CONFLICT），仅在图中标注"无坐标"；其符号已通过符号面板渲染

## 文字重叠调查（p024 PSW42d7e15403a896eb 1QD25/2-7QD9；p025 PSW30aa3991510e5a40 1-4Q1D2/5CD1）
(a) 原图重叠：原图由 `text_geometry_json` 角点（A2）绘制，在 p024 与 p025 两组上均重叠（x 方向 6.5 与 3.4 单位）。根因是 `src/dwg_audit/extract/text_geometry.py:22` 以 `fonts.make_font(..., 1.0)` 量宽，忽略样式 ST 的宽度系数 0.7。复算验证：用 1.0 得到 12.868 与 14.27，与 extraction 值完全一致；用 0.7 得到 9.007 与 9.989。
(b) 新渲染：正确对齐后不重叠。ezdxf 渲染的墨迹间距 p024 约 1.6、p025 约 1.9 单位；用样式系数的 advance 框（A4）在 p024 约重叠 0.47（几乎相接），p025 间距约 0.65。
(c) 桌面预览：会出现同样的重叠。`src/dwg_audit/desktop/preview.py:490-492` 只要有 `corners` 就走 `_render_cad_text`，`:630` 用 `textLength=line_widths` 拉伸，沿用了错误宽度。仅在无几何时才退回 `:498-505` 的左对齐插入点绘制，此路径会忽略对齐（A3 对 p025 重叠约 6.4）。预览本身没有 bug，问题在 extraction 的宽度估计。

## 其他观察
- 镜像 INSERT（extrusion=(0,0,-1)）的 `dxf.insert` 是 OCS 坐标。例：F0019 句柄 F019，insert_x=-212.5，实际 WCS 包围盒 x 206~214。脚本已改用包围盒中心作为符号位置，原始值保存在 `insert_raw_ocs`。`sw_symbols.insert_x` 也存在同样的问题，需另行核对。
- 基线 in_baseline 逐条核对通过：10 条低置信 issue 的 rule_id 与左右值在基线同项目中完全一致。
- 分类（classification / reason）未填写，留给复核人。
