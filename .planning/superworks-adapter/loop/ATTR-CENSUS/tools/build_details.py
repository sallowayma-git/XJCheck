"""由各分析脚本的输出组装 details.json（只读输入，仅写出 details.json）。

输入（均位于 --work 目录，文件名见下）:
  agg.json              aggregate.py      全部 appid 的深扫汇总
  vp_sum.json           aggregate_vp.py   候选 appid 的取值探测
  pcl_sum.json          aggregate_pcl.py  LD_PARTCONNECTLINE 汇总
  linkcheck2/*.json     validate_links.py 跨页线号与对端端子校验
  part_overlap.json     part_overlap.py   PCL 引脚与部件端口重叠
  crosspage_cover2.json crosspage_cover.py 跨页引用对未消费端口的覆盖
  strip_gain2.json      strip_gain.py     端子排去向增益
  strip_red.json        strip_redundancy.py 端子排属性冗余检查
  strip_identity.json   strip_identity_check.py 表头续接身份缺陷
  unconsumed_ana2.json  analyze_unconsumed.py
  wire_style.json       analyze_wire_style.py 未消费端口接触导线的 LD_LINE_STYLE 覆盖
  loggen_ana.json       analyze_loggen.py  LD_SYMB2LOGGEN 导线记录汇总与两端统计
  loggen_identity.json  check_loggen_identity.py 另一端与端子排去向一致性
  wp2/*.json            wire_probe.py     PCL 导线侧探测
用法: python build_details.py --work <dir> --out <details.json>
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os


def _load(work, name):
    return json.load(open(os.path.join(work, name), encoding="utf-8"))


def _pct(a, b):
    return round(100.0 * a / b, 2) if b else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    W = args.work

    agg = _load(W, "agg.json")
    vp = _load(W, "vp_sum.json")["apps"]
    pcl = _load(W, "pcl_sum.json")
    part = _load(W, "part_overlap.json")
    cc = _load(W, "crosspage_cover2.json")
    sg = _load(W, "strip_gain2.json")["totals"]
    sr = _load(W, "strip_red.json")
    sid = _load(W, "strip_identity.json")
    ua = _load(W, "unconsumed_ana2.json")
    ws = _load(W, "wire_style.json")
    lg = _load(W, "loggen_ana.json")
    lgi = _load(W, "loggen_identity.json")

    # 跨页线号校验（validate_links）汇总
    link = collections.Counter()
    link_b = collections.Counter()
    for f in glob.glob(os.path.join(W, "linkcheck2", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        if "error" in d:
            continue
        link.update(d["A"])
        link_b.update(d["B"])

    # 导线侧探测（wire_probe）汇总
    wp = collections.Counter()
    for f in glob.glob(os.path.join(W, "wp2", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        if "error" not in d:
            wp.update(d["counts"])

    total_pages = agg["total_pages_by_type"]
    n_files = agg["n_files_ok"]
    pcl_pt = pcl["per_page_type"]

    # 1. 全部 appid 表（深扫，全语料）
    appid_rows = {}
    for app, v in agg["appids"].items():
        cr = v.get("code_refs", {})
        used = bool(cr.get("literal_hits")) or bool(cr.get("pattern_note"))
        appid_rows[app] = {
            "entities": v["entities"],
            "by_scope_etype": v["by_scope_etype"],
            "files": v["files"],
            "pages_by_type": v["pages_by_type"],
            "pages_by_family": v["pages_by_family"],
            "top_signatures": [[s, n] for s, n in v["sigs_top"][:5]],
            "examples": [{k: ex[k] for k in ("pid", "fid", "pt", "filename", "scope", "etype", "handle", "vals") if k in ex}
                         for ex in v["examples"]],
            "code_literal_hits": cr.get("literal_hits", []),
            "code_pattern_note": cr.get("pattern_note"),
            "code_status": "referenced(literal/pattern)" if used else "unreferenced",
        }

    # 2. 候选属性取值（value probe）
    cand = {}
    for app, v in vp.items():
        cand[app] = {
            "files": v["files"],
            "pages_by_type": v["pages_by_type"],
            "entities_top": v["entities_by_pt_scope_type"],
            "string_values_top": v["str_top"][:12],
            "handle_target_types": v["h_type"],
            "handle_target_text_top": v["h_text_top"][:10],
            "examples": v["examples"],
        }

    # 3. 发现项
    lg_by_fam = {}
    for k, v in pcl["per_family_records"].items():
        lg_by_fam[k] = v

    findings = []

    findings.append({
        "id": "F1",
        "rank": 1,
        "title": "LD_SYMB2LOGGEN 导线两端记录（XRECORD，OBJECTS 中的 LD_SYMB2LOGGEN_DICTIONARY）",
        "carrier": "OBJECTS XRECORD 字典项（非 XDATA）；键：LINENO, LINESTYLE, LINECOLOR, LINEDIAMETER, CONNECTLINEHANDLE, PART2_n",
        "entity_types": "XRECORD（挂在 LD_SYMB2LOGGEN_DICTIONARY 下，每条一条导线）",
        "corpus": {
            "records": lg["A"].get("records"),
            "pages_with_records": lg["A"].get("pages_with_records"),
            "pages_by_type": lg["pages_by_type"],
            "ends_per_record": lg["ends_per_record"],
            "wire_handle_resolves": lg["wire_handle_type"],
            "linestyle_nonempty": lg["A"].get("records", 0) - lg["linestyle_values"].get("(空)", 0),
            "linecolor_nonempty": lg["linecolor_nonempty"],
            "linediameter_nonempty": lg["linediameter_nonempty"],
            "end_far_handle_resolves": lg["end_far_handle_type"],
        },
        "by_family_records": {"note": "按 page_index 家族统计见 loggen 原始结果；覆盖页数见 pages_with_records"},
        "examples": [
            {"file": "p000/F0004 04 交流回路图.dwg（二次原理图）", "xrecord": "13AFD (LD_SYMB2LOGGEN_1)",
             "wire": "E2F2 (LINE)", "LINESTYLE": "电流回路线:*", "LINENO": "未定义E301:3",
             "ends": ["1ID 第3脚，端子句柄 E301 (INSERT, 端子)", "1n 第2脚，端子句柄 E30E (INSERT, 装置端子)"]},
            {"file": "p038/F0005 04 交流回路图1.dwg（110kV变压器保护柜）", "xrecord": "20F08",
             "wire": "112A4 (LINE)", "LINESTYLE": "", "LINENO": "未定义112A0:1",
             "ends": ["1ID 第1脚，端子句柄 112A0 (INSERT, 端子)", "1ID 第2脚，端子句柄 1129E (INSERT, 端子)"]},
            {"file": "p051/F0004 04 交直流回路图.dwg（N2604合同）", "xrecord": "42675",
             "wire": "33505 (LINE)", "LINESTYLE": "", "LINENO": "未定义334F9:3",
             "ends": ["ZD 第3脚，端子句柄 334F9 (INSERT, 端子)", "1-25DK1 第3脚，端子句柄 334FF (INSERT)"]},
        ],
        "code_usage": {
            "used": ["LINENO 句柄与 CONNECTLINEHANDLE 仅用于装置端子绑定：src/dwg_audit/extract/terminal_port_bindings.py（_terminal_xrecords 读取 document.objects.query('XRECORD')，要求 LINENO 恰一个且含 CONNECTLINEHANDLE）",
                     "PART2_n 仅作为绑定校验的 token（同文件 _PART_KEY_PATTERN = PART2_\\d+）"],
            "unused": ["PART2_n 中的端点设备名/引脚/侧别/类别作为“另一端去向”未被使用（superworks_semantics.py 中无 PART2 解析）",
                       "LINESTYLE / LINECOLOR / LINEDIAMETER 无引用",
                       "其他 LD_SYMB2LOGGEN 记录未参与原理图端口与导线配对"],
        },
        "evidence": {
            "unconsumed_ports_total": lg.get("B_unconsumed_total"),
            "endpoint_exact_hit": lg["B_counts"].get("B2_endpoint_exact"),
            "endpoint_exact_hit_pct": _pct(lg["B_counts"].get("B2_endpoint_exact", 0), lg.get("B_unconsumed_total", 0)),
            "wire_contact_in_loggen": lg["B_counts"].get("B1_wire_in_loggen"),
            "records_touching_unconsumed": lg["C_pair_stats"].get("records_touching_unconsumed"),
            "two_end_records": lg["C_pair_stats"].get("two_end_records"),
            "two_end_one_end_unconsumed": lg["C_pair_stats"].get("two_end_one_end_unconsumed"),
            "two_end_both_ends_unconsumed": lg["C_pair_stats"].get("two_end_both_ends_unconsumed"),
            "other_end_vs_strip_destination": lgi["counts"],
            "other_end_agree_pct_of_evaluable": _pct(lgi["counts"].get("other_end_agrees_with_dest", 0),
                                                     lgi["counts"].get("other_end_agrees_with_dest", 0) +
                                                     lgi["counts"].get("other_end_disagrees_with_dest", 0)),
            "note_pct": "agree/(agree+disagree)，不含 record_has_single_end；与 top10 的 1547/1869 相同口径",
        },
        "match_potential": "二次原理图未消费端口的“配对/去向”：每条记录给出导线句柄与两端（设备+引脚+端子实体句柄），可直接补齐 no_matching_production_pair（3934）类端口的对端。",
        "caveats": [
            "LINESTYLE 非空率仅约 6%，导线类型多数缺失；仅作约束，不作为主键。",
            "另一端与端子排去向一致性：可评估 2227 条中 1547 条一致（69.5%），其余多为多端点记录或区间身份。",
            "多端（>2 端）记录约占 2.4%，需按端点逐一判断。"],
    })

    findings.append({
        "id": "F2",
        "rank": 2,
        "title": "LD_PARTCONNECTLINE（元件 INSERT 的扩展字典 XRECORD；OBJECTS 中同名字典项为其镜像）",
        "carrier": "INSERT 扩展字典 -> XRECORD，代码 1 字符串序列，每个逻辑端号 10 段：逻辑端号/线号/导线类型/线号文字句柄/导线颜色代号文字句柄/接线文字句柄/直线句柄/接地图块句柄/接地文字句柄/对端元件",
        "entity_types": "INSERT（元件）→ XRECORD；直线句柄 → LINE；接线文字句柄 → TEXT；线号 中的句柄 → INSERT（对侧装置端子）",
        "corpus": {
            "records": pcl["records_total"],
            "files_with_records": pcl["files_with_pcl"],
            "per_page_type": {k: v for k, v in pcl_pt.items() if v["records"]},
            "per_family_records": pcl["per_family_records"],
            "owner_kind_type": pcl["owner_kind_type"],
            "field_fill_nonempty": pcl["field_fill_nonempty"],
            "handle_resolution": pcl["handle_resolution"],
            "wire_label_class": pcl["wire_label_class"],
        },
        "examples": [
            {"file": "p000/F0015 15 元件接线图1.dwg（元件接线图）", "owner_insert": "B960 (ELXAL5-B11-209B)", "xrecord": "BB7C",
             "pin": "13", "线号": "未定义8ED7:1_05 交直流回路图", "直线句柄": "11EFF (LINE)", "接线文字句柄": "11F00 -> 文字 '& 1QD4'",
             "对端": "1QD 端子 4"},
            {"file": "p000/F0015 15 元件接线图1.dwg", "owner_insert": "B9BB (FEIDIAO-10A-Z-3-AC30)", "xrecord": "BB5E",
             "pin": "E", "线号": "未定义E2C0:E_05 交直流回路图", "直线句柄": "11ED9 (LINE)", "接线文字句柄": "11EDA",
             "对端": "JD 端子 11"},
            {"file": "p000/F0014 14 主保护背板接线图.dwg（背板表格型图）", "owner_insert": "19E6B", "xrecord": "19FB5",
             "pin": "101", "线号": "未定义E78C:2_08 信号回路图（句柄 E78C 在 08 信号回路图 中为 装置端子 INSERT，端口 2）",
             "直线句柄": "1A3A4 (LINE)", "接线文字句柄": "1A3A7 -> 文字 '1YD2'", "对端": "1YD 端子 2"},
        ],
        "code_usage": {"used": [], "unused": ["全部字段均无引用：src/ 中无 LD_PARTCONNECTLINE、无 '逻辑端号'/'对端元件'/'直线句柄' 等键名读取"]},
        "evidence": {
            "far_end_strip_match": link_b.get("strip_row_found"),
            "far_end_strip_missing": link_b.get("strip_row_missing"),
            "far_end_strip_match_pct": _pct(link_b.get("strip_row_found", 0),
                                            link_b.get("strip_row_found", 0) + link_b.get("strip_row_missing", 0)),
            "crosspage_handle_resolves_in_named_page": link.get("target_page_found_handle_yes"),
            "crosspage_handle_not_resolving": link.get("target_page_found_handle_no"),
            "crosspage_no_target_page": link.get("no_target_page_in_project"),
            "crosspage_marker_n_far_end": link.get("far_is_crosspage_marker_n"),
            "pins_already_in_sw_part_ports": part.get("counts", {}).get("pcl_pin_present_as_part_port"),
            "pins_not_in_sw_part_ports": part.get("counts", {}).get("pcl_pin_not_in_part_ports"),
            "unconsumed_exact_crosspage_cover": cc["counts"].get("covered_by_crosspage_ref"),
            "unconsumed_instance_only_cover": cc["counts"].get("instance_referenced_port_differs"),
            "crosspage_identity_equal": cc["counts"].get("identity_equal"),
            "crosspage_identity_range_consistent": cc["counts"].get("identity_range_prefix"),
            "crosspage_identity_differs": cc["counts"].get("identity_differs"),
            "strip_rows_total": sg.get("strip_rows"),
            "strip_rows_with_existing_dest": sg.get("rows_with_existing_dest"),
            "strip_rows_referenced_by_pcl": sg.get("rows_referenced_by_pcl"),
            "strip_rows_pcl_gain_without_existing_dest": sg.get("rows_pcl_gain_no_existing_dest"),
        },
        "match_potential": "元件侧引脚的“对端端子”（端子排行身份或对侧 装置端子 实例+端口）。引脚本身已几乎全部被部件端口覆盖，因此增量在去向，而非新增引脚。跨页句柄可直接指向对侧端子实例（已验证 99.5%）。",
        "caveats": [
            "对端端子命中端子排行后，新增行仅 19 条（现有 LDDZ 去向已覆盖 71.9% 的端子行），端子排侧增量很小，主要价值在于与原理图侧交叉印证。",
            "线号字段几乎全部为跨页形式，并非真实线号；真实线号仍需从页面文字取得。",
            "“未定义”仅表示线号未赋值，句柄与端口仍有效。"],
    })

    findings.append({
        "id": "F3",
        "rank": 3,
        "title": "LD_LINE_STYLE（原理图导线 LINE/LWPOLYLINE 的导线类型，XDATA）",
        "carrier": "XDATA 应用名 LD_LINE_STYLE，代码 1000 字符串",
        "entity_types": "LINE（模型空间 6206 + 块定义 7453）",
        "corpus": {"files": cand["LD_LINE_STYLE"]["files"], "pages_by_type": cand["LD_LINE_STYLE"]["pages_by_type"],
                   "entities_top": cand["LD_LINE_STYLE"]["entities_top"],
                   "string_values_top": cand["LD_LINE_STYLE"]["string_values_top"]},
        "examples": [{"file": ex["filename"], "pid": ex["pid"], "fid": ex["fid"], "handle": ex["handle"],
                      "value": ex["vals"][0][1] if ex.get("vals") else ""} for ex in cand["LD_LINE_STYLE"]["examples"][:3]],
        "code_usage": {"used": [], "unused": ["superworks_semantics.py / terminal_port_bindings.py 无 LD_LINE_STYLE 引用"]},
        "evidence": {
            "unconsumed_contact_wire_lines": ws["totals"].get("contact_lines"),
            "unconsumed_ports_with_style_wire": ws["totals"].get("any_style_port"),
            "unconsumed_ports_with_style_wire_pct": _pct(ws["totals"].get("any_style_port", 0), ws["totals"].get("ports", 0)),
            "style_values_on_contact_wires": {k[len("style_"):]: v for k, v in (ws.get("style_value_counts") or {}).items()},
        },
        "match_potential": "导线类型作为配对约束（电流回路/电压回路/屏蔽/接地），区分同一端子附近的多条候选线。覆盖有限（约 8.5% 的未消费端口接触线带有该属性）。",
        "caveats": ["约 24% 的 LINE 为空值。", "与 LOGGEN 的 LINESTYLE（非空约 6%）取值体系一致。"],
    })

    findings.append({
        "id": "F4",
        "rank": 4,
        "title": "跨页标记标签的 XDATA 指针：LD_SHOW_LINE / LD_SHOW_TYPE / LD_ GROUPPARTXRECT_* / LD_SYMB2_InsideLABEL",
        "carrier": "MTEXT/INSERT/LWPOLYLINE 上的 XDATA，1005 句柄指向 LINE、TEXT、INSERT、矩形 LWPOLYLINE",
        "entity_types": "MTEXT（标签 '1n'、'1-21n'）→ LINE / TEXT（装置型号如 WXH-813-D1F）；INSERT（装置/跨页符号）→ MTEXT（'1n'）；LWPOLYLINE（框）→ MTEXT",
        "corpus": {
            "LD_SHOW_LINE": {"files": cand["LD_SHOW_LINE"]["files"], "targets": cand["LD_SHOW_LINE"]["handle_target_types"]},
            "LD_SHOW_TYPE": {"files": cand["LD_SHOW_TYPE"]["files"], "targets": cand["LD_SHOW_TYPE"]["handle_target_types"],
                             "target_text_top": cand["LD_SHOW_TYPE"]["handle_target_text_top"]},
            "LD_SYMB2_InsideLABEL": {"files": cand["LD_SYMB2_InsideLABEL"]["files"], "entities_top": cand["LD_SYMB2_InsideLABEL"]["entities_top"],
                                     "targets": cand["LD_SYMB2_InsideLABEL"]["handle_target_types"],
                                     "target_text_top": cand["LD_SYMB2_InsideLABEL"]["handle_target_text_top"]},
            "LD_ GROUPPARTXRECT_TEXT": {"files": cand["LD_ GROUPPARTXRECT_TEXT"]["files"],
                                        "targets": cand["LD_ GROUPPARTXRECT_TEXT"]["handle_target_types"],
                                        "target_text_top": cand["LD_ GROUPPARTXRECT_TEXT"]["handle_target_text_top"]},
        },
        "examples": [
            {"file": "p000/F0004 04 交流回路图.dwg", "handle": "E384 (MTEXT '1n')", "XDATA": "LD_SHOW_LINE -> 1280D (LINE); LD_SHOW_TYPE -> 1280C (TEXT 'WXH-813-D1F')"},
            {"file": "p000/F0007 07 主保护接点联系图.dwg", "handle": "1C073 (INSERT)", "XDATA": "LD_SYMB2_InsideLABEL -> 1C12F (MTEXT '1n')"},
            {"file": "p000/F0004 04 交流回路图.dwg", "handle": "E303 (LWPOLYLINE 框)", "XDATA": "LD_ GROUPPARTXRECT_TEXT -> E384 (MTEXT '1n')"},
        ],
        "code_usage": {"used": [], "unused": ["LD_SHOW_LINE/LD_SHOW_TYPE/LD_SYMB2_InsideLABEL/LD_ GROUPPARTXRECT_* 无引用（grep 全 src）"]},
        "evidence": {"not_quantified_against_unconsumed": True},
        "match_potential": "跨页标记（如 1n、1-21n）与所属导线（LD_SHOW_LINE）、对侧装置型号（LD_SHOW_TYPE）的显式关联；可辅助判断哪条线跨页、指向哪个装置，但尚未在未消费端口上量化。",
        "caveats": ["LD_SYMB2_InsideLABEL 与 LD_ GROUPPARTXRECT 中大量指针为 0（空），有效指向需逐个过滤。"],
    })

    findings.append({
        "id": "F5",
        "rank": 5,
        "title": "DZ_SERIALNUMBER_NAME（端子排行的端子排名）——修正表头续接说明造成的身份错误",
        "carrier": "屏端子图 中端子行 TEXT 的 XDATA，代码 1000",
        "entity_types": "TEXT（端子行）",
        "corpus": {
            "rows_msp": sr["counts"].get("rows"),
            "header_present": sr["counts"].get("R1_header_present"),
            "header_equals_name": sr["counts"].get("R1_name_equals_header"),
            "header_equals_name_pct": _pct(sr["counts"].get("R1_name_equals_header", 0), sr["counts"].get("R1_header_present", 0)),
        },
        "identity_defect": {
            "header_continuation_rows": sid["counts"].get("header_continuation_shangjie"),
            "header_continuation_pct_of_rows": _pct(sid["counts"].get("header_continuation_shangjie", 0), sid["counts"].get("strip_rows", 0)),
            "example": sid.get("examples_header_continuation", [])[:3],
            "unconsumed_ports_affected_directly": sid["counts"].get("unconsumed_dz_row_but_header_identity_missing"),
            "unconsumed_identity_checks": {k: v for k, v in sid["counts"].items() if k.startswith("unconsumed_")},
        },
        "examples": [
            {"file": "p000/F0017 17 左侧端子表.dwg", "handle": "23301", "DZ_SERIALNUMBER_NAME": "7UD", "row": "1"},
            {"file": "p000/F0018 18 右侧端子表.dwg", "handle": "130F9", "DZ_SERIALNUMBER_NAME": "TD", "row": "1"},
            {"file": "p001/F0014 14 左侧端子表.dwg", "handle": "1E591", "DZ_SERIALNUMBER_NAME": "ZD", "row": "1"},
        ],
        "code_usage": {"used": [], "unused": ["DZ_SERIALNUMBER_NAME 无引用；端子身份 endpoint_identity 由表头 LD_DZPNO_HEADHANDLE 文字 + 行文字拼接（superworks_semantics.py 约 483 行）"]},
        "match_potential": "修正 endpoint_identity（表头为“上接1QD15”等续接说明时身份错误），并提供与 F2 对端端子一致的索引键。",
        "caveats": ["仅 75 个未消费端口被直接误伤，但受影响的端子行共 3154 条。"],
    })

    findings.append({
        "id": "F6",
        "rank": 6,
        "title": "LD_SYMB1LIB_TERMTEXTPOINT（符号库端子文字定位）与 LDPARTLAYT_CIRCLE_HANDLE（元件引脚圆）",
        "carrier": "符号定义内 LWPOLYLINE 的 XDATA 句柄；元件 INSERT 的 XDATA 句柄",
        "entity_types": "LWPOLYLINE -> LWPOLYLINE（端子文字点）；INSERT -> CIRCLE（引脚圆）",
        "corpus": {
            "LD_SYMB1LIB_TERMTEXTPOINT": {"files": cand["LD_SYMB1LIB_TERMTEXTPOINT"]["files"], "targets": cand["LD_SYMB1LIB_TERMTEXTPOINT"]["handle_target_types"],
                                          "pages_by_type": cand["LD_SYMB1LIB_TERMTEXTPOINT"]["pages_by_type"]},
            "LDPARTLAYT_CIRCLE_HANDLE": {"files": cand["LDPARTLAYT_CIRCLE_HANDLE"]["files"], "targets": cand["LDPARTLAYT_CIRCLE_HANDLE"]["handle_target_types"],
                                         "pages_by_type": cand["LDPARTLAYT_CIRCLE_HANDLE"]["pages_by_type"]},
            "LDPARTLAYT_LINE_HANDLE": {"files": cand["LDPARTLAYT_LINE_HANDLE"]["files"], "targets": cand["LDPARTLAYT_LINE_HANDLE"]["handle_target_types"],
                                       "overlap_with_pcl_straight_line": 0, "pairs_compared": 3704},
        },
        "examples": [
            {"file": "p000/F0004 04 交流回路图.dwg", "handle": "9A57 (LWPOLYLINE, 符号定义内)", "XDATA": "LD_SYMB1LIB_TERMTEXTPOINT -> 9A55"},
            {"file": "p000/F0015 15 元件接线图1.dwg", "handle": "B960 (INSERT ELXAL5-B11-209B)", "XDATA": "LDPARTLAYT_CIRCLE_HANDLE -> B961 (CIRCLE)"},
            {"file": "p000/F0014 14 主保护背板接线图.dwg", "handle": "19E6B (INSERT)", "XDATA": "LDPARTLAYT_LINE_HANDLE -> 19E6F (LINE)"},
        ],
        "code_usage": {"used": [], "unused": ["LD_SYMB1LIB_TERMTEXTPOINT、LDPARTLAYT_CIRCLE_HANDLE、LDPARTLAYT_LINE_HANDLE 均无引用"]},
        "match_potential": "原理图符号引脚与其文字的几何锚点（对应 unresolved_pin_text 类未消费端口，统计 794）；元件引脚圆的位置（元件接线图端口定位）。尚未量化。",
        "caveats": ["LDPARTLAYT_LINE_HANDLE 指向的 LINE 与 PCL 直线句柄无重合（0/3704），应为元件引脚引线而非连接导线。"],
    })

    findings.append({
        "id": "F7",
        "rank": 7,
        "title": "LD_SYMB_TERMAUTODIM / DZCONNECT_ELEMENT_CLASS（端号自动标注与元素类别）",
        "carrier": "符号定义 LWPOLYLINE 的 XDATA（TERMAUTODIM: YES/NO）；屏端子图 TEXT 的 XDATA（ELEMENT_CLASS: 装置端子/端子/线圈/接地）",
        "entity_types": "LWPOLYLINE（端子标记）、TEXT（端子排文字）",
        "corpus": {
            "LD_SYMB_TERMAUTODIM": {"files": cand["LD_SYMB_TERMAUTODIM"]["files"], "string_values": cand["LD_SYMB_TERMAUTODIM"]["string_values_top"]},
            "DZCONNECT_ELEMENT_CLASS": {"files": cand["DZCONNECT_ELEMENT_CLASS"]["files"], "string_values": cand["DZCONNECT_ELEMENT_CLASS"]["string_values_top"]},
        },
        "examples": [
            {"file": "p000/F0004 04 交流回路图.dwg", "handle": "9A52 (LWPOLYLINE)", "value": "NO"},
            {"file": "p000/F0017 17 左侧端子表.dwg", "handle": "23302 (TEXT)", "value": "装置端子"},
            {"file": "p001/F0014 14 左侧端子表.dwg", "handle": "1E615 (TEXT)", "value": "装置端子"},
        ],
        "code_usage": {"used": [], "unused": ["两个键均无引用"]},
        "match_potential": "端号自动标注 YES（仅 179 条）可解释“无端子文字”的引脚；ELEMENT_CLASS 可区分端子排文字类别，辅助判断 far_kind（端子/装置端子）。未量化。",
        "caveats": ["TERMAUTODIM 绝大多数为 NO，覆盖低。"],
    })

    # 4. 冗余或无增量的属性（否定结论）
    redundant = [
        {"appid": "LD_DZPNO_DXLX_OUT", "status": "冗余", "evidence": f"与已用的 LD_DZPNO_DXLX 指向文字在 {sr['counts'].get('R3_out_and_in_present')} 个可比行中 {sr['counts'].get('R3_out_equals_in')} 行完全相同（100%）"},
        {"appid": "DZ_SERIALNUMBER_DZLX", "status": "冗余", "evidence": f"“试验端子:粗线” {sr['counts'].get('R2_dzlx_test')} 行全部与已用的 LD_DZPNO_DZLX 折线（LWPOLYLINE）一一对应"},
        {"appid": "LX / DZ_SERIALNUMBER_LAYER / DZ_SERIALNUMBER_HD", "status": "常量或无区分度", "evidence": "LX 全为 '0'；LAYER 全为 '1'；HD 仅 6.20/8.20"},
        {"appid": "LD_LINE_COLORCODE / LD_LINE_DIAMETER / LD_LINE_COLORVALUE / LINECOLOR / LINEDIAMETER", "status": "基本为空", "evidence": f"LOGGEN 中 LINECOLOR 非空 {lg['linecolor_nonempty']} 条，LINEDIAMETER 非空 {lg['linediameter_nonempty']} 条"},
        {"appid": "LD_SYMB_TERMHIDE", "status": "常量", "evidence": "取值全为 NO"},
        {"appid": "LD_SYMB_BOMANDLABEL（扩展字典，符号 LWPOLYLINE）", "status": "模板值", "evidence": "推荐名称/方向“其它”/端号自动标注 NO 等为符号库模板，区分度低"},
        {"appid": "GROUP 对象", "status": "与匹配无关", "evidence": "326 个，名称为 GROUP_LPINFOTABLE(128)、GROUP_DwgDirTABLE(120)、其他(78)，集中在 屏面布置图/封面目录"},
        {"appid": "LDBOM_* / PDZT_* / LD_ACTLABEL / LD_ACTTERM", "status": "非连接相关", "evidence": "BOM、屏面布置图标注或少量动作端子（20 页）"},
    ]

    # 5. Top 10
    top10 = [
        {"rank": 1, "key": "LD_SYMB2LOGGEN XRECORD（LINENO / CONNECTLINEHANDLE / PART2_n）", "count": lg["A"].get("records"),
         "semantics": "导线两端记录：导线句柄 + 两端设备引脚 + 端子实体句柄 + 导线类型", "match": "二次原理图端口配对（去向），补 no_matching_production_pair",
         "evidence": f"未消费端口 4667/4727（{_pct(4667, 4727)}%）端点精确命中；有去向的 2227 个端口中，另一端可比较 1869 个，其中与端子排去向一致 1547 个（{_pct(1547,1869)}%）"},
        {"rank": 2, "key": "LD_PARTCONNECTLINE（元件 INSERT 扩展字典 XRECORD，对端元件+端子+跨页线号）", "count": pcl["records_total"],
         "semantics": "元件引脚的对端端子、导线句柄与跨页对侧端子实例", "match": "元件侧去向；跨页端子实例直连；identity 校验",
         "evidence": f"跨页句柄在指定页命中 {link.get('target_page_found_handle_yes')}/{link.get('target_page_found_handle_yes',0)+link.get('target_page_found_handle_no',0)}；未消费端口精确覆盖 {cc['counts'].get('covered_by_crosspage_ref')} 个，身份一致 {cc['counts'].get('identity_equal',0)+cc['counts'].get('identity_range_prefix',0)} 个"},
        {"rank": 3, "key": "LD_PARTCONNECTLINE 的 线号 跨页句柄（未定义H:端口_页号）", "count": link.get("far_is_crosspage_marker_n", None),
         "semantics": "对侧装置端子 INSERT 句柄 + 端口 + 页名（已验证在被指页存在）", "match": "跨页端子直连（与 #2 为同一字段，单独列出便于实现）",
         "evidence": "命中率 99.5%；跨页标记 n 作为对端占 4198 条"},
        {"rank": 4, "key": "LD_LINE_STYLE（原理图导线类型，XDATA）", "count": cand["LD_LINE_STYLE"]["entities_top"],
         "semantics": "导线类型：电流回路线/电压回路线/屏蔽线/接地线等", "match": "配对候选的导线类型约束",
         "evidence": f"未消费端口接触导线带该属性 {ws['totals'].get('any_style_port')}/{ws['totals'].get('ports')}（{_pct(ws['totals'].get('any_style_port',0), ws['totals'].get('ports',0))}%）"},
        {"rank": 5, "key": "DZ_SERIALNUMBER_NAME（端子排名）", "count": sr["counts"].get("rows"),
         "semantics": "端子行所属端子排的真实名称", "match": "修正身份（表头续接说明）、PCL 对端端子索引键",
         "evidence": f"表头续接身份错误 {sid['counts'].get('header_continuation_shangjie')} 行；直接影响未消费端口 {sid['counts'].get('unconsumed_dz_row_but_header_identity_missing')} 个"},
        {"rank": 6, "key": "LD_SHOW_LINE / LD_SHOW_TYPE（标签 → 导线 / 装置型号）", "count": cand["LD_SHOW_LINE"]["files"],
         "semantics": "跨页标记标签所属导线与对侧装置型号文字", "match": "跨页标记 → 导线/装置 的显式关联",
         "evidence": "二次原理图 775 页；未量化"},
        {"rank": 7, "key": "LD_SYMB2_InsideLABEL（符号 → 跨页标签 MTEXT）", "count": agg["appids"]["LD_SYMB2_InsideLABEL"]["entities"],
         "semantics": "跨页符号的内部标签（1n、1-21n 等）", "match": "跨页标记识别，辅助 PCL 对端 n 标记的页归属",
         "evidence": "682 页；未量化"},
        {"rank": 8, "key": "LD_ GROUPPARTXRECT_TEXT / XRECT（标签框）", "count": agg["appids"]["LD_ GROUPPARTXRECT_TEXT"]["entities"],
         "semantics": "跨页标记的外框（矩形 LWPOLYLINE）与其标签", "match": "跨页标记几何识别",
         "evidence": "793 页（二次原理图）；未量化"},
        {"rank": 9, "key": "LD_SYMB1LIB_TERMTEXTPOINT（符号端子文字定位）", "count": agg["appids"]["LD_SYMB1LIB_TERMTEXTPOINT"]["entities"],
         "semantics": "符号库中端子文字的锚点", "match": "unresolved_pin_text（794）类端口的引脚文字定位",
         "evidence": "787 张二次原理图；未量化"},
        {"rank": 10, "key": "LDPARTLAYT_CIRCLE_HANDLE（元件引脚圆）", "count": cand["LDPARTLAYT_CIRCLE_HANDLE"]["files"],
         "semantics": "元件 INSERT 对应引脚圆（CIRCLE）", "match": "元件接线图引脚几何锚点",
         "evidence": "178 页（165 元件接线图）；未量化"},
    ]

    details = {
        "meta": {
            "task": "SuperWORKS 出图 DXF 中未被识别引擎使用的端子排/导线属性普查（只读）",
            "corpus": "corpus_manifest.json：77 项目 / 1745 页；DXF 逐个只读打开，未修改 src/ tests/，未使用 git",
            "page_index": "page_index 由 round12 pages.parquet 按 (file_id, filename) 关联得到；页型取 page_type",
            "scan_scope": "全部 1745 页（非抽样）：模型空间、全部块定义、ATTRIB、扩展字典、OBJECTS（DICTIONARY/XRECORD/GROUP）",
            "families": {"正式典设(test)": 1080, "N2604合同": 450, "变压器测控柜": 107, "110kV变压器保护柜": 77, "PAC-885G-H": 31},
            "page_types": total_pages,
            "files_scanned_ok": n_files,
            "block_definitions_scanned": agg.get("block_definitions"),
            "note_families": "家族按 input_root 关键字归类，与任务书五类对应；“正式典设(test)”为 test/正式典设 下其余目录",
            "note_code_status": "appids 表中的 code_status 为字面量 grep 启发式（可能误中子串），仅作索引；各发现项的 code_usage 已逐一人工核对（含 f-string / startswith / 正则拼接）",
        },
        "appids": appid_rows,
        "candidate_values": cand,
        "findings": findings,
        "redundant_or_no_gain": redundant,
        "top10": top10,
        "strip_identity_defect": {
            "rows_with_header_continuation": sid["counts"].get("header_continuation_shangjie"),
            "examples": sid.get("examples_header_continuation", []),
            "unconsumed_identity_checks": {k: v for k, v in sid["counts"].items() if k.startswith("unconsumed_")},
        },
        "unconsumed_reason_codes": "见 unconsumed_port_diagnostics.json（4727）：no_matching_production_pair 3934；partial_legacy_value_differs_from_full_SW_identity 3859；legacy_discard_retained 3274；endpoint_text_not_extracted 798；unresolved_endpoint_identity 798；unresolved_pin_text 794；nonreciprocal_pin 631；dangling_label_handle 333",
        "limitations": [
            "以 F: 冻结 DXF 缓存为准（manifest 中的 dxf_path，全部存在）；未重新转换 DWG。",
            "“未消费端口”取自 unconsumed_port_diagnostics.json（4727 条），与 findings 中 strict consumption 94.28% 口径一致（82680 - 77953 = 4727）。",
            "各覆盖率是“可命中”的上界或下界说明已在字段中注明；未量化项已明确标注。",
            "跨页句柄解析在“被指页”文件中进行；同项目内找不到目标页文件的记录计入 no_target_page_in_project（1757）。",
            "LD_SYMB2LOGGEN 的“另一端”一致性仅对能在端子排行索引中找到身份的端口评估（2227 条）。",
        ],
        "reproduce": [
            "cd F:/workspace/XJToolkit; set PYTHONIOENCODING=utf-8",
            "python .planning/superworks-adapter/loop/ATTR-CENSUS/tools/build_index.py --out <W>/page_index2.json",
            "python .../deep_scan.py --index <W>/page_index2.json --work <W>/deep2 --workers 8",
            "python .../aggregate.py --index <W>/page_index2.json --work <W>/deep2 --out <W>/agg.json",
            "python .../value_probe.py --index <W>/page_index2.json --work <W>/vp --apps <候选列表> ; python .../aggregate_vp.py --work <W>/vp --out <W>/vp_sum.json",
            "python .../parse_pcl.py --index ... --work <W>/pcl ; python .../aggregate_pcl.py --work <W>/pcl --out <W>/pcl_sum.json",
            "python .../validate_links.py --index ... --pcl <W>/pcl --work <W>/linkcheck2",
            "python .../wire_probe.py --index ... --pcl <W>/pcl --work <W>/wp2",
            "python .../part_overlap.py --round12 .tmp/superworks_round12_full --pcl <W>/pcl --out <W>/part_overlap.json",
            "python .../analyze_unconsumed.py --diag .planning/superworks-adapter/unconsumed_port_diagnostics.json --index ... --pcl <W>/pcl --out <W>/unconsumed_ana2.json",
            "python .../crosspage_cover.py --diag ... --index ... --pcl <W>/pcl --out <W>/crosspage_cover2.json",
            "python .../strip_dest_index.py --index ... --work <W>/stripdest ; python .../strip_gain.py --index ... --pcl <W>/pcl --work <W>/sg2 --out <W>/strip_gain2.json",
            "python .../strip_redundancy.py --index ... --out <W>/strip_red.json",
            "python .../strip_identity_check.py --round12 .tmp/superworks_round12_full --stripdest <W>/stripdest --diag ... --out <W>/strip_identity.json",
            "python .../parse_loggen.py --index ... --work <W>/loggen ; python .../analyze_loggen.py --loggen <W>/loggen --diag ... --round12 ... --index ... --out <W>/loggen_ana.json",
            "python .../check_loggen_identity.py --diag ... --loggen <W>/loggen --stripdest <W>/stripdest --index ... --out <W>/loggen_identity.json",
            "python .../analyze_wire_style.py --diag ... --round12 ... --index ... --out <W>/wire_style.json",
            "python .../build_details.py --work <W> --out .planning/superworks-adapter/loop/ATTR-CENSUS/details.json",
        ],
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(details, fh, ensure_ascii=False, indent=1)
    print("written", args.out, os.path.getsize(args.out))


if __name__ == "__main__":
    main()
