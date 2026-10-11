"""LOGGEN-MISMATCH aggregation (read-only): writes details.json from the scratch products of the other tools.

Usage: python aggregate.py <scratch_dir> <out_json> [samples_json]

Reads: ends.pkl, wire_checks.pkl, nearest_terminal.pkl, control.pkl, control.json, stats.json, samples.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

GROUPS = {
    "agree_exact": "一致：精确文字",
    "agree_format": "一致：仅格式（连字符、&、_ 等）",
    "agree_composed_pin": "一致：标签 + 近旁引脚文字（复合）",
    "agree_composed_pin_contact_suffix": "一致：标签 + 引脚 + 触点序号后缀",
    "agree_composed_text": "一致：标签 + 近旁文字（复合）",
    "agree_composed_text_contact_suffix": "一致：标签 + 近旁文字 + 触点序号后缀",
    "agree_segmented": "一致：标签 + 多段近旁文字拼接",
    "agree_segmented_contact_suffix": "一致：多段拼接 + 触点序号后缀",
    "agree_group_header_left": "一致：左侧组标题 + 单元格数字",
    "agree_row_partial": "一致（弱）：仅行号文字近旁一致（背板）",
    "unrelated_text_nearby": "无法判定：仅有无关的近旁身份型文字",
    "connect_only_differs": "无法判定：仅有接线去向标签，且与身份不同",
    "connect_only_agree": "无法判定：仅有接线去向标签，与身份相同",
    "unverifiable": "无法判定：端口近旁无文字",
    "disagree_prefix_differs": "不一致：前缀不同（本端文字）",
    "disagree_prefix_and_port": "不一致：前缀与端口号均不同（本端文字）",
    "disagree_row_digits": "不一致：行号不同（背板）",
    "disagree_slot_digit": "不一致：槽位数字不同",
}


def group_of(verdict: str) -> str:
    if verdict.startswith("disagree"):
        return "不一致"
    if verdict.startswith("unrelated") or verdict.startswith("connect_only") or verdict == "unverifiable":
        return "无法判定"
    return "一致"


def main(scratch: Path, out_json: Path, samples_json: Path | None) -> None:
    ends = pd.read_pickle(scratch / "ends.pkl")
    ends = ends[ends.geometry.fillna(False).astype(bool)].copy()
    ends["group"] = ends.verdict.map(group_of)
    stats = json.loads((scratch / "stats.json").read_text(encoding="utf-8"))
    total = len(ends)
    out: dict = {"projects": stats["projects"], "projects_without_routes": stats["projects_without_routes"],
                 "unique_resolved_ports": total,
                 "end_occurrences_in_records": int(ends.records.sum()),
                 "identity_conflicts_within_port": int(ends.identity_conflict.sum())}

    out["group_totals"] = {g: {"n": int(n), "pct": round(100 * n / total, 2)}
                           for g, n in ends.group.value_counts().items()}
    out["verdict_totals"] = {v: {"n": int(n), "pct": round(100 * n / total, 2), "label": GROUPS.get(v, v)}
                             for v, n in ends.verdict.value_counts().items()}
    cls_order = ["端子", "装置端子", "内部元件", "背板端口", "其他"]
    table = pd.crosstab(ends.end_class, ends.group).reindex(cls_order).fillna(0).astype(int)
    out["by_class_group"] = {c: {g: int(table.loc[c, g]) for g in table.columns} | {"total": int(table.loc[c].sum())}
                             for c in table.index}
    vt = pd.crosstab(ends.verdict, ends.end_class).fillna(0).astype(int)
    out["by_class_verdict"] = {v: {c: int(vt.loc[v, c]) for c in vt.columns if c in vt.columns} for v in vt.index}

    back = ends[ends.end_class == "背板端口"]
    out["backplate_slot_evidence"] = {
        "header_digit_match": back.slot.map(lambda d: (d or {}).get("header_match") if isinstance(d, dict) else None)
        .map(lambda x: "none" if x is None or (isinstance(x, float) and pd.isna(x)) else ("match" if x else "mismatch")).value_counts().to_dict(),
        "copy_rank_match": back.slot.map(lambda d: (d or {}).get("rank_match") if isinstance(d, dict) else None)
        .map(lambda x: "none" if x is None or (isinstance(x, float) and pd.isna(x)) else ("match" if x else "mismatch")).value_counts().to_dict(),
    }

    wc = pd.read_pickle(scratch / "wire_checks.pkl")
    out["wire_destination_checks"] = {"rows": int(len(wc)), "records": int(wc.record_id.nunique()),
                                      "verdicts": wc.verdict.value_counts().to_dict()}

    nt = pd.read_pickle(scratch / "nearest_terminal.pkl")
    out["terminal_nearest_label"] = nt.status.value_counts().to_dict()
    nt["margin"] = nt.identity_dist - nt.nearest_dist
    out["terminal_nearest_label_margin_ge_2"] = int(((nt.status == "identity_present_not_nearest") & (nt.margin >= 2)).sum())

    ctl = json.loads((scratch / "control.json").read_text(encoding="utf-8"))
    out["negative_control"] = {"sampled": ctl["sampled"], "still_agree": ctl["still_agree_total"],
                               "by_class": ctl["by_class"], "mutated_verdicts": ctl["mutated_verdict_counts"]}

    if samples_json and samples_json.exists():
        out["samples"] = json.loads(samples_json.read_text(encoding="utf-8"))

    out_json.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"unique_ports": total, "group_totals": out["group_totals"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
