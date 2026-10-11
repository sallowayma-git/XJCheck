"""Assemble loop/B-1/details.json from collected facts and the verdicts (read-only inputs)."""
import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *

FACTS = json.loads((OUT / "tools" / "_facts.json").read_text(encoding="utf-8"))
IMPACT = json.loads((OUT / "tools" / "_impact.json").read_text(encoding="utf-8"))

VERDICT = {
    "p062_PC0019_S0012": dict(
        verdict="c", subtype="bound device header leader (SW part-layout LINE)",
        summary="线段左端隐形数字 '7' 是 SW 器件 /170A7 (DELL XSQ) 的序号 PARTNO；上方 52n 为该器件 PARTLABEL；下方 XSQ_22E2HM 为 PARTTYPE。线段右端 1 单位内无任何实体，不是待接线端。",
        evidence=[
            "DXF XDATA: 器件 INSERT 170A7 的 LDPARTLAYT_LINE_HANDLE=170A9（即本线段）、PARTNO_HANDLE=170AA（'7'）、PARTLABEL_HANDLE=170AB（52n）、PARTTYPE_HANDLE=170AC（XSQ_22E2HM）。",
            "数字 '7' 的 DXF TEXT height=1e-05（屏幕不可见），引擎 cad_extract 钳制为 1.0 后成为 terminal_numeric_channel 候选 CC0032 score 0.90。",
            "右端 (315.60,135.61) 1 单位内仅有 170AC 文字包围盒；最近几何为器件块顶边 LINE 1709A（y=122.61，距离 13.0）。",
            "SW 端口：DELL XSQ 仅 DY（333.98,88.90，距空端 50.2，经 CZ-J1 同页连接）与 XK（52n-HDMI）两个端口，均不在空端附近。",
            "52n 在 SW 中唯一对应 /170A7（sw_part_instances）；其他页 52n 仅为二次原理图 DIM 引用（F0005 (68.13,107.36)、F0007 (295,234.5)）。",
            "round12 supersession 无 170AA 相关记录；pairs 中 PC0019 为 ordinary_pair review（missing right candidate，0.44）。",
        ],
        png="B1_p062_PC0019_S0012.png"),
    "p062_PC0125_S0013": dict(
        verdict="c", subtype="bound device header leader (SW part-layout LINE)",
        summary="隐形数字 '8' 为 SW 器件 /1152C (ATW1000-H) 的 PARTNO；上方 58n 为 PARTLABEL；下方 ATW1000-H 为 PARTTYPE。空端距器件块顶边 4.33 单位，无接触。",
        evidence=[
            "DXF XDATA: 器件 1152C 的 LDPARTLAYT_LINE_HANDLE=11530、PARTNO=11531（'8'）、PARTLABEL=11532（58n）、PARTTYPE=11533（ATW1000-H）。",
            "'8' DXF height=1e-05，引擎钳制为 1.0，候选 CC0664 accepted score 0.90。",
            "空端 (221.51,282.10) 1 单位内无线段/端子实体；最近几何为 ATW1000-H 顶边 LINE 114DD（y=277.77，距离 4.33）。",
            "SW 端口最近距离 24.6（HDMI3 (236.75,262.77)），空端附近无端口。",
            "58n 的 SW 连接（DY→CZ-J2、HDMI→52nHDMI、HDMI1→1-25nHDMI、HDMI2→2-25nHDMI）共 4 条 pass，均不经过本线段。",
        ],
        png="B1_p062_PC0125_S0013.png"),
    "p071_PC0053_S0011": dict(
        verdict="c", subtype="unbound device header (orphan LDPARTLAYT, PART_HANDLE=0) plus line-group merge artifact",
        summary="线组 GC0053 由两条近平行的 MARK 引线 2D7E（y=281.07，x 207.1–219.9）与 6F25（y=282.33，x 209.9–225.9）合并而成；左端 '1'（T1112）属于 2D7E，右端空端（225.88）实为 6F25 的端部，两者仅差 0.63 单位。该簇（1n/1-1n/25n/51n + WHH-811A/WXH-822A-P/WYD-811/MOXA）与 S0008 的器件头模板同形，但未绑定到任何 SW 器件。",
        evidence=[
            "XDATA: 2D7E、2D7F、2D80、2D81、6F25、6F26、6F27、6F28、BEFB–BEFE 等全部 LDPARTLAYT_PART_HANDLE='0'（无父器件），线段无 LINE_HANDLE 绑定。",
            "对照：S0008 上 2424A–2424D（25n/MCE-812-B/序号 1）绑定到 PART 24248，结构相同；未绑定的 ADD1–ADD4（2-2n/WYD-811）亦为 PART_HANDLE=0。",
            "线组成员 L3480（2D7E）与 L3482（6F25）；线组端点取平均 y=281.70，故空端 (225.875,281.70) 距 6F25 端点 (225.875,282.33) 仅 0.63。",
            "merge 机制：line_groups.py:_can_merge_axis_intervals (412–466) 在区间重叠且横向差 1.26 ≤ cross_axis_tolerance 2.5 时直接返回 True。",
            "S0011 全部 12 个 SW 实例的端口与空端最近距离 25.7（/26422 序号 1），空端附近无 SW 端口。",
            "S0011 无任何 SW 记录含 WYD-811/WXH-822A-P/WHH-811A/MOXA 字串（sw_symbols/sw_connect_labels/sw_part_instances 均为 0）。",
        ],
        png="B1_p071_PC0053_S0011.png"),
    "p075_PC0232_S0014": dict(
        verdict="c", subtype="bound device header leader (SW part-layout LINE)",
        summary="隐形数字 '8' 为 SW 器件 /3214C (TS3000-Z01, MASTER CLOCK) 的 PARTNO；上方 1-26n 为 PARTLABEL；下方 TS3000-Z01 为 PARTTYPE。空端距器件块顶边 8.0 单位，无接触。",
        evidence=[
            "XDATA: 器件 3214C 的 LDPARTLAYT_LINE_HANDLE=3214E、PARTNO=3214F（'8'）、PARTLABEL=32150（1-26n）、PARTTYPE=32151（TS3000-Z01）。",
            "'8' DXF height=1e-05，引擎钳制为 1.0，候选 CC4149 accepted 0.90。",
            "空端 (227.51,260.50) 1 单位内仅 32151 文字包围盒；最近几何为器件块顶边 BORDER LINE 320E4/3214A（y=252.5，距离 8.0）。",
            "器件 3214C 共 202 个端口（405–428、501–528、801–817… 等）；最近端口 601 距空端 30.6，无端口落在空端。",
        ],
        png="B1_p075_PC0232_S0014.png"),
    "p075_PC0440_S0015": dict(
        verdict="c", subtype="bound device header leader (SW part-layout LINE)",
        summary="与 PC0232 同形（F0015 页）：隐形数字 '9' 为器件 /3205D (TS3000-Z01) 的 PARTNO，上方 2-26n 为 PARTLABEL。两页（F0014/F0015）几何坐标完全相同，器件块相同。",
        evidence=[
            "XDATA: 器件 3205D 的 LDPARTLAYT_LINE_HANDLE=3205F、PARTNO=32060（'9'）、PARTLABEL=32061（2-26n）、PARTTYPE=32062（TS3000-Z01）。",
            "'9' DXF height=1e-05，引擎钳制为 1.0，候选 CC8207 accepted 0.90。",
            "空端距器件块顶边 8.0 单位，1 单位内无实体（同 PC0232）。",
        ],
        png="B1_p075_PC0440_S0015.png"),
}

ENGINE_CHAIN = [
    dict(step="1 文字高度钳制（根因）", where="src/dwg_audit/extract/cad_extract.py:348 与 :362（_append_text）",
         what="height=max(height, 1.0)：DXF 隐形文字 height=1e-05 被提升为 1.0，之后全部高度判断都以 1.0 为准。"),
    dict(step="2 高度门放行", where="src/dwg_audit/audit/candidates.py:208 与 :273；config.py:96 min_text_height=1.0（text 段）",
         what="within_height=min<=text.height<=max：钳制后 1.0 通过；若保留原始 1e-05 应为 height_out_of_range 拒绝。"),
    dict(step="3 端子候选接受", where="src/dwg_audit/audit/candidates.py（terminal 候选循环，约 :189–:330）",
         what="隐形数字处于线端 radius 内，score 0.90（距离项+侧向项；无高度加分，因 1.8<=h<=3.5 不满足）。SW 序号 PARTNO 未被排除。"),
    dict(step="4 SW 已知但未消费", where="src/dwg_audit/extract/superworks_semantics.py:447（part_no=LDPARTLAYT_PARTNO_HANDLE）",
         what="sw_part_instances.part_no 已记录该数字的 text_id，但候选/pairs 路径不读取它来排除序号文字；superworks_supersession 对这些数字零记录。"),
    dict(step="5 缺侧登记为 review", where="src/dwg_audit/audit/pairs.py:69–75（build_pairs 单侧分支）",
         what="只有一侧有候选：rationale='missing right candidate'，status=review，confidence 0.44；没有'器件标注引线'分支。"),
    dict(step="6 裸 n 标签被当噪声（正确结果、错误理由）", where="candidates.py:249 与 :1949（not_numeric）；config.py:140–145（元件接线图 numeric_suffix_patterns：n 后缀仅 n\\d{3,}；另有 CD/GD/ZK/HD 规则）",
         what="52n、1-26n、2-26n、1-1n、25n 被判为非数字，成为 noise。它们实为器件标签（SW PARTLABEL），不是端子线号。"),
    dict(step="7 跨页路径不适用", where="src/dwg_audit/audit/project_graph.py:256（build_cross_page_endpoint_candidates，仅 AUTHORITATIVE）",
         what="器件标签在多页出现（二次原理图 DIM 引用）。若把裸 n 当跨页端点，会把器件引用误连为线。本案无需进入该路径。"),
    dict(step="8 MARK 降权（次要）", where="config.py:99 deprioritized_layers；candidates.py:968",
         what="仅 penalty 0.03，不是决定因素（候选分数仍为 0.90）。"),
    dict(step="9 线组合并（仅 PC0053）", where="src/dwg_audit/audit/line_groups.py:412–466（_can_merge_axis_intervals）",
         what="两条近平行重叠短线（横向差 1.26 ≤ cross_axis_tolerance 2.5）被合并；端点取平均 y，左右端来自不同引线。"),
    dict(step="10 文字锚点（次要，全局）", where="candidates.py:191–192（text.insert_x）；cad_extract 使用原始 insert",
         what="居中对齐文字（halign=1）的 insert 不是对齐点：52n 原始 (305.84,136.01)，对齐点 (308.09,137.51)，偏差约 2.3 单位。superworks_semantics 已用 text_anchor_wcs，端子候选路径未用。"),
]

FIX = [
    dict(id="F1", priority="核心", target="cad_extract.py:348、:362（_append_text）",
         change="保留原始 DXF 高度（TextItem.height 或新增 raw_height）；bbox 仍可用 max(height,1.0) 估算。隐形文字（raw_height<0.01）从端子候选排除，reason 记为 hidden_text。",
         effect="语料中 26 个钳制后被接受的数字文字失去候选资格；影响 14 条单端 review、5 条双端 discard、6 个无 pair 的候选；另有 3 条 table_mapping pass 依赖隐形数字，须先人工复核（见 README）。",
         guard="只针对 raw height<0.01 的数字文字；可见数字的候选逻辑不变。"),
    dict(id="F2", priority="核心", target="candidates.py 端子候选循环；superworks_semantics.py:447 产出的 part_no",
         change="若数字文字的 text_id 是某 SW 实例的 part_no（序号），则排除出 terminal 通道，并在 pairs 层标记 device_header_leader（注释性，非缺侧）。",
         effect="覆盖 SW 确认的 13 条（14 条中去掉 PC0053）。",
         guard="只在 SW 实例存在且 part_no.text_id 精确匹配时生效。"),
    dict(id="F3", priority="补充", target="pairs.py:69–75（build_pairs 单侧分支）",
         change="对无 SW 绑定的器件头：MARK 水平短线（≤32 单位）、一端隐形数字、上方 n 标签、下方器件型号文字，且空端 1 单位内无实体 → 归为 unbound_device_header（注释性），不进入 R-PAIR-MISSING-SIDE。",
         effect="PC0053 类（无 SW 绑定）。",
         guard="任何一条条件不满足则保持 review；不得仅凭 n 标签判定。"),
    dict(id="F4", priority="补充", target="line_groups.py:412–466（_can_merge_axis_intervals）",
         change="重叠区间的横向差 >0.5 且两线各自带独立端子文字时，不合并（当前对 1.26 单位仍合并）。",
         effect="PC0053 线组拆分为两条引线。需语料回归，预计影响面小但需评估。",
         guard="仅在两线端点各自有候选文字时拆分；默认行为不变。"),
    dict(id="F5", priority="不建议", target="config.py:140–145（numeric_suffix_patterns）",
         change="不要放宽为接受裸 n（如 52n、1-26n）。",
         effect="会产生 7↔52n、8↔58n 等错误 pair，把器件标签当线号。",
         guard="—"),
    dict(id="F6", priority="不建议", target="裸 n 跨页分类（Z-5 建议 B 的 cross_page_marker 类）",
         change="不应把 B 组视为跨页标记。Z-5 第 3 条建议应撤回：证据表明这是器件标注头，不是跨页线号。",
         effect="—",
         guard="DIM/CONNECT 层的裸 n（约 171 条，semantic_mapping）是真正的跨页线号关系，不得一并纳入。"),
]

out = dict(
    scope="R-PAIR-MISSING-SIDE residual B group (5 items) in .tmp/superworks_round12_full; read-only; no src/tests/git changes",
    method=dict(dxf="manifest dxf_path (frozen cache), ezdxf readfile, read-only; round12 findings parquet; SW XDATA via ezdxf xdata.data keyed by application/record name"),
    items=[],
    engine_chain=ENGINE_CHAIN,
    fix_recommendations=FIX,
    impact=IMPACT,
    corpus_stats=dict(
        projects=77, dxf_files=1745, dxf_text_entities=488951,
        numeric_text_height_1e_05=4070,
        numeric_hidden_in_round12_audited_texts=3945,
        hidden_numerals_accepted_as_terminal_candidates=26,
        accepted_projects={"p051": 6, "p062": 4, "p069": 1, "p071": 13, "p075": 2},
        single_ended_pairs_total=25218, single_ended_status={"review": 22124, "discard": 3094, "pass": 0},
        bare_n_within16_of_missing_end=193, bare_n_status={"review": 191, "discard": 2, "pass": 0},
        bare_n_by_line_layer={"DIM": 138, "CONNECT": 33, "0": 13, "MARK": 9},
        mark_leader_bare_n=dict(total=9, status={"review": 9}, sw_part_no_confirmed=8, unbound=1,
                                projects={"p051": 4, "p062": 2, "p071": 1, "p075": 2}),
        hidden_numeral_single_ended_review=dict(total=14, with_bare_n_label=9, without_label=5, sw_part_no_confirmed=13),
        table_mapping_pass_using_hidden_numerals=["P0001 p071 S0008 T0441 '2'", "P0003 p071 S0009 T0659 '4'", "P0004 p071 S0009 T0653 '2'"],
    ),
)
for name, F in FACTS.items():
    v = VERDICT[name]
    item = dict(
        id=f"B-{name}", project=F["project"], run=F["run"], pair_id=F["pair_id"], file_id=F["file_id"],
        sheet_id=F["sheet_id"], sheet_no=F["sheet_no"], sheet_title=F["sheet_title"],
        sheet_category=F["sheet_category"], filename=F["filename"],
        pair=F["pair"], line_group=F["line_group"],
        identified_side=dict(side=F["identified_side"], point=F["identified_point"], text=F["numeral"]),
        missing_side=dict(point=F["missing_point"], entities_within_1_unit=F["entities_touching_missing_end_1unit"],
                          nearest_geometry=F["nearest_geometry_to_missing_end"][:3],
                          nearest_text_bbox=F["nearest_text_bbox_to_missing_end"][:3]),
        nearby_texts=F["nearby_texts"],
        inserts_near_stub=F["inserts_near_stub"],
        sw_part_with_numeral=F["sw_part_with_numeral"],
        sw_part_instances_on_sheet=F["sw_part_instances_on_sheet"][:6],
        verdict=dict(code=v["verdict"], subtype=v["subtype"], summary=v["summary"], evidence=v["evidence"]),
        png=f"loop/B-1/{v['png']}",
    )
    out["items"].append(jsonable(item))
json.dump(out, open(OUT / "details.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("written details.json items", len(out["items"]))
