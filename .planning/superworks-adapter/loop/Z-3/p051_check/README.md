# p051 S0009 核查：PC0052 / PC0080 cell-edge discard
结论：两条是 IGNORE 设备面板 WYD-811-401 内 LAN 口单元框底边，不是导线。discard 结论正确，但依据不成立：规则执行顺序早于面板标记，且探测带选择有缺陷。（只读，未改 src/，未全量回放）
## 1 对象（R10 pairs.parquet；R9 同 pair 为 review）
- PC0052：GC0052，y=58.127，x 118.02–160.52，成员 2A35B:VIRTUAL:150:2/164:2/205:2；已识别侧 T0887 "1"（175.96, 59.04）；INSERT 2A35B，块 WYD-811-401
- PC0080：GC0080，y=190.383，x 115.84–158.34，成员 2A1F2:VIRTUAL:150:2/164:2/205:2；已识别侧 T0788 "1"（173.78, 191.29）；INSERT 2A1F2，块 WYD-811-401
- table_cell_edge（两条同形）：owner、missing_end (118.02, 58.13)、outward -1、neighbour 2A35B:VIRTUAL:44:0（y 33.12）、centre 45.63、tol 3.75、leads [], texts [], clear true；PC0080 为 neighbour y 165.38、centre 177.88
- 其余：ordinary_pair_eligible False、ignored_panel_family_id communication.equipment_panel_ignored.v1、rule wyd-8com-12lan-complete-panel-v1（mark 写入）
## 2 截图
p051_S0009_cell_edge_pairs.png：DXF 底图（ezdxf + COLOR_SWAP_BW）；橙=线组，红=缺端，蓝虚线=LAN 单元框，绿=规则邻行，灰=被排除的顶边，黄=探测区，紫=缺端外侧符号，蓝框=已识别侧
## 3 判断：伪导线（discard 结论正确，依据应为面板 IGNORE）
- 线组是 LAN2/LAN4/LAN6 网口框底边，缺端为 LAN2 左下角；右侧 "1" 是 COM2 第 1 脚编号
- 160.5–176 与缺端外侧 111.5–118 之间无线段；块属 IGNORE 设备面板，面板内 VIRTUAL 线不进入普通端子图（page_extractors.py:2531 起）
## 4 离线为何未发现（已复现：R9 p051 单项目离线调用）
- 离线用 R9 数据，mark 已写入 ordinary_pair_eligible=False，门控 superworks_extractor.py:533 返回 False，原样调用 0 条变化
- pipeline.py:274 的 cell-edge 调用早于 :278 的 mark；去掉该键模拟顺序后，恰为两条变化
- 全库 R10（77 项目）：cell-edge discard 共 42 = p075 40（与离线一致）+ p051 2；p051 discard 445 到 447，issues 两轮均为 0
## 5 规则缺陷
- 邻行：:1159 要求覆盖跨度 >=50%，单元框顶边 y 70.20（跨度 12.5）被排除，唯一邻线为 y 33.12 的 CH 说明框边，被 :1408–1410 接受
- 探测带：centre=(58.13+33.12)/2（:1322）落在空带；缺端外侧 x 94–111.5 的符号轮廓若被探测，按 :1340 会计为引线而阻挡
## 6 补充条件（建议，未改代码）
1. 规则移到 mark_ignored 之后，或跳过 ignored_panel_family_id / ordinary_pair_eligible=False 的 pair
2. 邻行限同图层表格框，排除 CH 说明框；单侧唯一邻线不单独定义行距
3. 探测带取缺端所属单元带，并要求上下两侧探测均清空
4. 本例台账 reason 应改归面板 IGNORE
