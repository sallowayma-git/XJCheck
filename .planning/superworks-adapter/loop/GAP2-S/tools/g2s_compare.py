"""GAP2-S comparison (read-only): round20 (HEAD) replay against a GAP2-S replay, per project.

Checks pairs and issues row by row (pair_id excluded: it is a sequence counter), line groups by member-set identity,
the device-internal links (added, lost, identified-element links), and the four coverage views from the summary.
Writes only the JSON given as the third argument.
Usage: python g2s_compare.py BEFORE_ROOT AFTER_ROOT OUT_JSON [pid ...]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

VIEWS = ("strict", "with_continuity", "with_internal", "total")


def complete(root: Path, pid: str) -> dict:
    return json.loads((root / pid / "complete.json").read_text(encoding="utf-8"))


def row_key(row: dict) -> str:
    row = {k: v for k, v in row.items() if k != "pair_id"}
    return json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)


def pair_rows(findings: Path) -> Counter:
    frame = pd.read_parquet(findings / "pairs.parquet")
    return Counter(row_key(r) for r in frame.to_dict(orient="records"))


def issue_rows(audit: Path) -> Counter:
    rows = json.loads((audit / "issues.json").read_text(encoding="utf-8"))
    return Counter(json.dumps(r, sort_keys=True, ensure_ascii=False, default=str) for r in rows)


def group_sets(findings: Path) -> Counter:
    frame = pd.read_parquet(findings / "line_groups.parquet")
    out = []
    for row in frame.itertuples():
        members = json.loads(row.member_line_ids) if isinstance(row.member_line_ids, str) else list(row.member_line_ids)
        out.append(json.dumps(sorted(members)))
    return Counter(out)


def link_ids(findings: Path) -> tuple[set, set]:
    frame = pd.read_parquet(findings / "sw_device_internal_links.parquet")
    ids = set(frame["link_id"]) if len(frame) else set()
    identified = set()
    if len(frame) and "element_port_id" in frame:
        for row in frame.to_dict("records"):
            if row.get("source") == "sw_internal_element" and row.get("element_port_id"):  # all SW-element links; identity count: g2s_identified_analysis.py
                identified.add(row["link_id"])
    return ids, identified


def main(before_root: Path, after_root: Path, out_json: Path, pids: list[str]) -> None:
    result = {}
    total = Counter()
    for pid in pids:
        b_dir, a_dir = Path(complete(before_root, pid)["project_dir"]), Path(complete(after_root, pid)["project_dir"])
        b_find, a_find = b_dir / "findings", a_dir / "findings"
        b_pairs, a_pairs = pair_rows(b_find), pair_rows(a_find)
        b_issues, a_issues = issue_rows(b_dir / "audit"), issue_rows(a_dir / "audit")
        b_groups, a_groups = group_sets(b_find), group_sets(a_find)
        b_links, _ = link_ids(b_find)
        a_links, a_identified = link_ids(a_find)
        b_sum = json.loads((b_find / "superworks_summary.json").read_text(encoding="utf-8"))
        a_sum = json.loads((a_find / "superworks_summary.json").read_text(encoding="utf-8"))
        rec = {
            "pairs": sum(b_pairs.values()), "pairs_after": sum(a_pairs.values()),
            "pairs_added": sum((a_pairs - b_pairs).values()), "pairs_removed": sum((b_pairs - a_pairs).values()),
            "issues": sum(b_issues.values()), "issues_after": sum(a_issues.values()),
            "issues_added": sum((a_issues - b_issues).values()), "issues_removed": sum((b_issues - a_issues).values()),
            "line_groups": sum(b_groups.values()), "line_groups_after": sum(a_groups.values()),
            "line_group_sets_added": sum((a_groups - b_groups).values()),
            "line_group_sets_removed": sum((b_groups - a_groups).values()),
            "links": len(b_links), "links_after": len(a_links),
            "links_added": len(a_links - b_links), "links_lost": len(b_links - a_links),
            "links_sw_element_after": len(a_identified),
            "coverage_before": {v: b_sum["coverage_views"][v]["consumed"] for v in VIEWS},
            "coverage_after": {v: a_sum["coverage_views"][v]["consumed"] for v in VIEWS},
            "eligible": b_sum["coverage_views"]["eligible"],
            "split_stats": {k: v for k, v in a_sum["device_internal"]["stats"].items() if k.startswith("split")},
        }
        result[pid] = rec
        for key in ("pairs", "pairs_added", "pairs_removed", "issues", "issues_added", "issues_removed",
                    "links", "links_after", "links_added", "links_lost", "line_group_sets_added",
                    "line_group_sets_removed"):
            total[key] += rec[key]
        print(pid, "pairs", rec["pairs"], "->", rec["pairs_after"], "(+%d -%d)" % (rec["pairs_added"], rec["pairs_removed"]),
              "issues", rec["issues"], "->", rec["issues_after"], "links", rec["links"], "->", rec["links_after"],
              "lost", rec["links_lost"], "coverage", rec["coverage_before"]["total"], "->", rec["coverage_after"]["total"],
              flush=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"projects": result, "total": dict(total)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TOTAL", dict(total))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
