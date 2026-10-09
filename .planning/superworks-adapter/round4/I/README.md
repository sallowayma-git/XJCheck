# Round 4 I: 人工复核抽样截图（v2 抽样范围）

数据：`F:\workspace\XJToolkit\.tmp\superworks_round4_full`（第四轮，77 项目，360 条 issue）；基线：`.tmp\superworks_baseline_timed`。
脚本：`round4_samples_v2.py`（复制自 `round4/C/round4_samples.py`，仅改抽样范围、in_baseline、SW 符号位置字段与配色；原脚本未改动）。
运行：`python round4_samples_v2.py --run <round4_full> --baseline <baseline_timed> --output <round4/I>`，日志见 `run_log.txt`。

## 各规则数量（全量 / 抽样 / 其中 in_baseline=True）
- R-CROSS-PAGE-CONFLICT：3 / 3 / 3
- R-SUPERWORKS-CONFLICT：18 / 18 / 0（符号由 message 中的 SW 句柄经 entitydb 定位，共 35 个句柄，全部解析；17 个 SW 配对无坐标，仅标注"无坐标"）
- R-PAIR-LOW-CONFIDENCE：10 / 10 / 10
- R-DUPLICATE-PAIR：68 / 20 / 0（随机，seed 20261009）
- R-ONE-TO-MANY：68 / 20 / 0（随机，seed 20261009）
- R-MANY-TO-ONE：110 / 24 / 4
  - in_baseline=True 全部 4 条出图（组 `R-MANY-TO-ONE-IN_BASELINE`，项目 p039 I0001 至 I0004）
  - 其余 106 条按 round3_composition.py 同一键分桶，前 5 桶各随机 4 条（seed 20261009），共 20 条
    - B1 53 条 → 抽 4；B2 15 条 → 抽 4；B3 10 条 → 抽 4；B4 7 条 → 抽 4；B5 5 条 → 抽 4
    - B6 及之后未抽样（B6 4 条、B7 4 条等）

合计 95 条 issue 出图；`index.json` 共 95 条记录。

## in_baseline 定义
同项目（project_id）基线 `issues.json` 中存在同 rule_id 且 left_value、right_value 相同的 issue，则为 True。全量统计（`samples/_summary.json` 的 `in_baseline_totals`）：R-CROSS-PAGE-CONFLICT 3/3，R-PAIR-LOW-CONFIDENCE 10/10，R-MANY-TO-ONE 4/110，R-SUPERWORKS-CONFLICT 0/18，R-DUPLICATE-PAIR 与 R-ONE-TO-MANY 均为 0。

## R-MANY-TO-ONE 分桶
- 分桶键与 round3_composition.py 一致（kinds / sources / 配对数 / sheets / scopes / views / headers）。
- 分桶范围为非 in_baseline 的 106 条（不含已全部入图的 4 条）。
- 排序：按桶大小降序，再按键字符串。
- 前 5 桶的键见 `samples/_summary.json` 的 `buckets`，即本轮 B1–B5。

## SW 符号位置（WCS）
- 符号框取自 DXF entitydb 中 INSERT 的 `virtual_entities()` 包围盒，中心即符号位置，为 WCS 坐标，镜像块同样适用。原始 OCS 插入点保存在 `insert_raw_ocs`。
- 35 个句柄全部在 DXF 中解析到实体（`position_frame` 全部为 entitydb WCS）；没有走 `sw_symbols.insert_x/y` 回退路径。
- 本轮 SW 冲突 35 个句柄的 extrusion 均为 (0,0,1)，即抽样中无镜像块。
- 镜像路径用合成 DXF 验证：extrusion (0,0,-1) 时 centre 为 (-103.5, 51)，与 OCS 插入点经 `OCS.to_wcs` 得到的 (-100, 50) 及块偏移一致，未使用原始 (100, 50)。

## 文字宽度
渲染使用 ezdxf drawing 直接读取 DXF 中的文字样式，不经过 `src/dwg_audit/extract/text_geometry.py`，因此 text_geometry 宽度系数修复对本套图无影响。

## 配色修复（相对 round4/C）
- 原脚本 `Frontend` 默认配色对白色（ACI 7）实体不做处理，在白底 figure 上白线不可见，表现为只有红框、无线条。
- v2 对所有面板使用 `ColorPolicy.COLOR_SWAP_BW`，白色实体转为黑色，其他 ACI 颜色保留。
- 已用 I\samples\R-MANY-TO-ONE-IN_BASELINE__p039__I0001.png 复核：线条与文字可见。
- round4/C 原脚本采用同一绘制路径，其已生成图片可能存在同样的不可见线条问题，建议重新生成。

## 输出
- `samples/<组>__<项目>__<issue>.png`：每个 issue 一张（95 张）。
  - 组名：`R-CROSS-PAGE-CONFLICT`、`R-SUPERWORKS-CONFLICT`、`R-PAIR-LOW-CONFIDENCE`、`R-DUPLICATE-PAIR`、`R-ONE-TO-MANY`、`R-MANY-TO-ONE-B1`…`B5`、`R-MANY-TO-ONE-IN_BASELINE`。
  - 红框为左右端点；SW 符号为红框外框，端口为橙框。
- `samples/contact_<RULE>.png`：每规则一张接触表（共 6 张）。
- `samples/_summary.json`：规则全量数、抽样数、in_baseline 统计、分桶明细、SW 位置来源统计。
- `index.json`：95 条记录；`classification` / `reason` 为 null，留给复核人填写。`in_baseline` 对所有规则均已计算；`sample_reason` 记录抽样原因。
- `run_log.txt`：本次运行日志。

## 局限
- 本脚本只渲染复核截图，不做分类。
- 抽样为 seed 固定的随机抽样，非分层抽样（MTO 的 in_baseline 部分为全量）。
- R-PAIR-MISSING-SIDE（81 条）与 R-DUPLICATE-SAME-LINE（2 条）不在本轮抽样范围内。
