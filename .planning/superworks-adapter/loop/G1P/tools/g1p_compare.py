"""G1P replay comparison (read-only): pairs and issues against the round19 baseline, full columns, plus coverage views.

Usage: python g1p_compare.py <baseline_run_dir> <new_run_dir> <out_json> <project ids...>
Pairs are compared row by row over every column (sorted by pair_id, serialised with pandas to_json). Issues are
compared as the JSON list of the issues file. Coverage views and device-internal statistics come from
findings/superworks_summary.json. Both run directories must hold complete.json per project.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

VIEWS = ("strict", "with_continuity", "with_internal", "total")


def project_dir(run: Path, pid: str) -> Path:
    complete = json.loads((run / pid / "complete.json").read_text(encoding="utf-8"))
    return Path(complete["project_dir"])


def canonical_pairs(path: Path) -> list[str]:
    frame = pd.read_parquet(path).sort_values("pair_id").reset_index(drop=True)
    rows = json.loads(frame.to_json(orient="records", force_ascii=False))
    return [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows]


def main(base_run: Path, new_run: Path, out_path: Path, projects: list[str]) -> dict:
    result = {"projects": {}, "totals": {"pairs_base": 0, "pairs_new": 0, "pairs_identical_rows": 0,
                                          "issues_identical": True, "pairs_differing_rows": 0}}
    for pid in projects:
        b, n = project_dir(base_run, pid), project_dir(new_run, pid)
        pb, pn = canonical_pairs(b / "findings" / "pairs.parquet"), canonical_pairs(n / "findings" / "pairs.parquet")
        identical = pb == pn
        issues_b = json.loads((b / "audit" / "issues.json").read_text(encoding="utf-8"))
        issues_n = json.loads((n / "audit" / "issues.json").read_text(encoding="utf-8"))
        issues_same = issues_b == issues_n
        sb = json.loads((b / "findings" / "superworks_summary.json").read_text(encoding="utf-8"))
        sn = json.loads((n / "findings" / "superworks_summary.json").read_text(encoding="utf-8"))
        views = {}
        for view in VIEWS:
            views[view] = {"eligible": sb["coverage_views"]["eligible"],
                           "base": sb["coverage_views"][view]["consumed"],
                           "new": sn["coverage_views"][view]["consumed"],
                           "base_ratio": sb["coverage_views"][view]["ratio"],
                           "new_ratio": sn["coverage_views"][view]["ratio"]}
        result["projects"][pid] = {
            "pairs_base": len(pb), "pairs_new": len(pn), "pairs_identical_full_columns": identical,
            "pairs_rows_differing": sum(1 for x, y in zip(pb, pn) if x != y) + abs(len(pb) - len(pn)),
            "issues_base": len(issues_b), "issues_new": len(issues_n), "issues_identical": issues_same,
            "coverage_views": views,
            "device_internal_stats_new": sn["device_internal"]["stats"],
            "device_internal_link_count_new": sn["device_internal"]["link_count"],
            "device_internal_link_count_base": sb["device_internal"]["link_count"],
            "unregistered_symb2": sn["device_internal"].get("unregistered_symb2"),
            "link_count_by_source": sn["device_internal"].get("link_count_by_source"),
        }
        t = result["totals"]
        t["pairs_base"] += len(pb)
        t["pairs_new"] += len(pn)
        t["pairs_identical_rows"] += sum(1 for x, y in zip(pb, pn) if x == y)
        t["pairs_differing_rows"] += result["projects"][pid]["pairs_rows_differing"]
        t["issues_identical"] = t["issues_identical"] and issues_same
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    base, new, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    res = main(base, new, out, sys.argv[4:])
    print(json.dumps(res["totals"], ensure_ascii=False, indent=1))
