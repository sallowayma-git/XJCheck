"""WIRE-BREAK comparison of two replay roots (read-only).

usage: wb_compare.py BASE_ROOT NEW_ROOT OUT_JSON [project ...]
Compares, per project: line groups, pairs (content key), issues, coverage views, device-internal links,
terminal splits and the new sw_topology_unknown rows. Pairs are keyed by content, not by pair_id.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


def project_dirs(root: Path) -> dict[str, Path]:
    out = {}
    for complete in root.glob("p*/complete.json"):
        data = json.loads(complete.read_text(encoding="utf-8"))
        out[complete.parent.name] = Path(data["project_dir"])
    return out


def frame(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def line_group_keys(d: Path) -> Counter:
    lg = frame(d / "findings/line_groups.parquet")
    keys = Counter()
    for r in lg.itertuples():
        keys[(r.sheet_id, round(r.start_x, 3), round(r.start_y, 3), round(r.end_x, 3), round(r.end_y, 3))] += 1
    return keys


def pair_keys(d: Path) -> Counter:
    pr = frame(d / "findings/pairs.parquet")
    keys = Counter()
    for r in pr.itertuples():
        left = "" if pd.isna(r.left_value) else str(r.left_value)
        right = "" if pd.isna(r.right_value) else str(r.right_value)
        keys[(r.sheet_id, left, right, r.status, str(r.pair_kind))] += 1
    return keys


def issue_keys(d: Path) -> Counter:
    path = d / "audit/issues.json"
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    keys = Counter()
    for it in items:
        keys[json.dumps({k: it.get(k) for k in ("rule_id", "sheet_id", "title", "severity", "message") if k in it},
                        ensure_ascii=False, sort_keys=True)] += 1
    return keys


def summary(d: Path) -> dict:
    path = d / "findings/superworks_summary.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def diff(a: Counter, b: Counter) -> dict:
    added = b - a
    removed = a - b
    return {"added": sum(added.values()), "removed": sum(removed.values()),
            "added_sample": [list(k) if isinstance(k, tuple) else k for k in list(added)[:5]],
            "removed_sample": [list(k) if isinstance(k, tuple) else k for k in list(removed)[:5]]}


def main() -> None:
    base_root, new_root, out_json = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    only = set(sys.argv[4:])
    base, new = project_dirs(base_root), project_dirs(new_root)
    result = {}
    for pid in sorted(set(base) & set(new)):
        if only and pid not in only:
            continue
        b, n = base[pid], new[pid]
        sb, sn = summary(b), summary(n)
        cov = lambda s, view: (s.get("coverage_views", {}).get(view) or {})
        views = {}
        for view in ("strict", "with_continuity", "strict_excl_device_internal", "with_continuity_excl_device_internal"):
            views[view] = {"base": [cov(sb, view).get("consumed"), cov(sb, view).get("eligible")],
                           "new": [cov(sn, view).get("consumed"), cov(sn, view).get("eligible")]}
        unknown = frame(n / "findings/sw_topology_unknown.parquet")
        result[pid] = {
            "line_groups": {"base": sum(line_group_keys(b).values()), "new": sum(line_group_keys(n).values()),
                            "diff": diff(line_group_keys(b), line_group_keys(n))},
            "pairs": {"base": sum(pair_keys(b).values()), "new": sum(pair_keys(n).values()),
                      "diff": diff(pair_keys(b), pair_keys(n))},
            "issues": {"base": sum(issue_keys(b).values()), "new": sum(issue_keys(n).values()),
                       "diff": diff(issue_keys(b), issue_keys(n))},
            "coverage": views,
            "device_internal_links": {"base": sb.get("device_internal", {}).get("link_count"),
                                      "new": sn.get("device_internal", {}).get("link_count")},
            "terminal_splits": {"base": sb.get("device_internal", {}).get("terminal_splits"),
                                "new": sn.get("device_internal", {}).get("terminal_splits")},
            "topology": sn.get("topology", {}),
            "unknown_rows": len(unknown),
        }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for pid, r in result.items():
        print(pid, "LG", r["line_groups"]["base"], "->", r["line_groups"]["new"],
              "| pairs", r["pairs"]["base"], "->", r["pairs"]["new"],
              "(+%d/-%d)" % (r["pairs"]["diff"]["added"], r["pairs"]["diff"]["removed"]),
              "| issues", r["issues"]["base"], "->", r["issues"]["new"],
              "| unknown", r["unknown_rows"])


if __name__ == "__main__":
    main()
