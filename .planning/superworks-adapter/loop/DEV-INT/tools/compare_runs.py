"""DEV-INT comparison of two replay runs: pairs and issues as exact multisets, and the four coverage views.

Usage: python compare_runs.py <base_run_dir> <new_run_dir> [--projects ...] [--json out.json]

Pairs and issues are compared by content (pair_id, status, values, kind, sheet; rule, severity, status, pair,
sheet, values, message). issue_id is a sequence number and is ignored.

Coverage views (eligible = terminal and device-terminal ports with a wire contact and a resolved label):
- strict: consumed (pairs only);
- with_continuity: consumed_with_continuity (pairs or cross-page continuity);
- with_internal: consumed or device-internal link (pairs or device-internal);
- total: consumed_with_internal (pairs, continuity or device-internal).
The base run (before DEV-INT) has no device-internal links, so its with_internal view equals strict, and its
total view equals with_continuity.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd


def _pair_key(row):
    return (row["pair_id"], row["status"], str(row["left_value"]), str(row["right_value"]), str(row["pair_kind"]),
            str(row["sheet_id"]))


def _issue_key(issue):
    return tuple(str(issue.get(k, "")) for k in ("rule_id", "severity", "status", "pair_id", "sheet_id", "left_value",
                                                  "right_value", "message"))


def _project_dir(run_dir: Path, pid: str) -> Path:
    complete = json.loads((run_dir / pid / "complete.json").read_text(encoding="utf-8"))
    return Path(complete["project_dir"])


def _findings(run_dir: Path, pid: str) -> Path:
    # Projects are rewritten under the run folder; the recorded project_dir may name another drive.
    project = next((run_dir / pid).glob("*/findings"), None)
    return project if project is not None else _project_dir(run_dir, pid) / "findings"


def _audit(run_dir: Path, pid: str) -> Path:
    project = next((run_dir / pid).glob("*/audit"), None)
    return project if project is not None else _project_dir(run_dir, pid) / "audit"


def _coverage(findings: Path):
    coverage = pd.read_parquet(findings / "sw_port_coverage.parquet")
    coverage = coverage[coverage.eligible.astype(bool)]
    counts = {"eligible": int(len(coverage)), "strict": int(coverage.consumed.astype(bool).sum())}
    counts["with_continuity"] = int(coverage.consumed_with_continuity.astype(bool).sum()) \
        if "consumed_with_continuity" in coverage else counts["strict"]
    if "consumed_with_internal" in coverage:
        counts["total"] = int(coverage.consumed_with_internal.astype(bool).sum())
        internal_only = [bool(c) or bool(json.loads(i or "[]")) for c, i in
                         zip(coverage.consumed.astype(bool), coverage.device_internal_link_ids.fillna("[]"))]
        counts["with_internal"] = int(sum(internal_only))
    else:
        counts["total"] = counts["with_continuity"]
        counts["with_internal"] = counts["strict"]
    return counts


def compare_project(base_run: Path, new_run: Path, pid: str) -> dict:
    base_f, new_f = _findings(base_run, pid), _findings(new_run, pid)
    columns = ["pair_id", "status", "left_value", "right_value", "pair_kind", "sheet_id"]
    base_pairs = pd.read_parquet(base_f / "pairs.parquet", columns=columns)
    new_pairs = pd.read_parquet(new_f / "pairs.parquet", columns=columns)
    base_counter = Counter(_pair_key(r) for r in base_pairs.to_dict("records"))
    new_counter = Counter(_pair_key(r) for r in new_pairs.to_dict("records"))
    base_issues = json.loads((_audit(base_run, pid) / "issues.json").read_text(encoding="utf-8"))
    new_issues = json.loads((_audit(new_run, pid) / "issues.json").read_text(encoding="utf-8"))
    base_ic = Counter(_issue_key(i) for i in base_issues)
    new_ic = Counter(_issue_key(i) for i in new_issues)
    base_cov, new_cov = _coverage(base_f), _coverage(new_f)
    new_summary = json.loads((new_f / "superworks_summary.json").read_text(encoding="utf-8"))
    links = pd.read_parquet(new_f / "sw_device_internal_links.parquet") if (new_f / "sw_device_internal_links.parquet").exists() else pd.DataFrame()
    return {
        "project_id": pid,
        "pairs_base": len(base_pairs), "pairs_new": len(new_pairs),
        "pairs_added": sum((new_counter - base_counter).values()),
        "pairs_removed": sum((base_counter - new_counter).values()),
        "issues_base": len(base_issues), "issues_new": len(new_issues),
        "issues_added": sum((new_ic - base_ic).values()),
        "issues_removed": sum((base_ic - new_ic).values()),
        "eligible": new_cov["eligible"], "base_views": base_cov, "new_views": new_cov,
        "device_internal_links": int(len(links)),
        "device_internal_pcl": int(links.pcl_corroborated.astype(bool).sum()) if len(links) else 0,
        "device_internal_stats": new_summary.get("device_internal", {}).get("stats", {}),
        "summary_views": new_summary.get("coverage_views"),
    }


def _full_rows(frame):
    """Every column of a table as text, one tuple per row, sorted (order-independent)."""
    def text(value):
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return "" if value is None or (isinstance(value, float) and value != value) else str(value)
    return sorted(tuple(text(v) for v in row) for row in frame.itertuples(index=False))


def full_column_check(base_run: Path, new_run: Path, projects) -> dict:
    """Every pairs.parquet column and every issues.json record, per project, against the base run."""
    mismatched = {"pairs": [], "issues": []}
    counts = Counter()
    for pid in projects:
        base_f, new_f = _findings(base_run, pid), _findings(new_run, pid)
        a = _full_rows(pd.read_parquet(base_f / "pairs.parquet"))
        b = _full_rows(pd.read_parquet(new_f / "pairs.parquet"))
        counts["pairs_rows"] += len(a)
        if a != b:
            mismatched["pairs"].append(pid)
        ia = sorted(json.dumps(i, sort_keys=True, ensure_ascii=False, default=str)
                    for i in json.loads((_audit(base_run, pid) / "issues.json").read_text(encoding="utf-8")))
        ib = sorted(json.dumps(i, sort_keys=True, ensure_ascii=False, default=str)
                    for i in json.loads((_audit(new_run, pid) / "issues.json").read_text(encoding="utf-8")))
        counts["issues"] += len(ia)
        if ia != ib:
            mismatched["issues"].append(pid)
    return {"pairs_rows_compared": counts["pairs_rows"], "issues_compared": counts["issues"],
            "projects_with_column_mismatch": mismatched}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_run")
    parser.add_argument("new_run")
    parser.add_argument("--projects", nargs="*", default=None)
    parser.add_argument("--json", default=None)
    parser.add_argument("--full", action="store_true", help="also compare every pairs column and issue record")
    args = parser.parse_args()
    base_run, new_run = Path(args.base_run), Path(args.new_run)
    projects = args.projects or sorted(p.name for p in new_run.iterdir() if p.is_dir() and p.name.startswith("p"))
    rows = [compare_project(base_run, new_run, pid) for pid in projects]
    totals = Counter()
    for row in rows:
        for key in ("pairs_base", "pairs_new", "pairs_added", "pairs_removed", "issues_base", "issues_new",
                    "issues_added", "issues_removed", "eligible", "device_internal_links", "device_internal_pcl"):
            totals[key] += row[key]
        for view in ("strict", "with_continuity", "with_internal", "total"):
            totals[f"base_{view}"] += row["base_views"][view]
            totals[f"new_{view}"] += row["new_views"][view]
    ratios = {}
    for view in ("strict", "with_continuity", "with_internal", "total"):
        ratios[view] = {"base": totals[f"base_{view}"] / totals["eligible"] if totals["eligible"] else None,
                        "new": totals[f"new_{view}"] / totals["eligible"] if totals["eligible"] else None}
    summary = {"projects": projects, "totals": dict(totals), "ratios": ratios, "rows": rows,
               "pairs_and_issues_identical": all(r["pairs_added"] == r["pairs_removed"] == 0 and
                                                 r["issues_added"] == r["issues_removed"] == 0 for r in rows)}
    if args.full:
        summary["full_column_check"] = full_column_check(base_run, new_run, projects)
    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"totals": summary["totals"], "ratios": ratios,
                      "pairs_and_issues_identical": summary["pairs_and_issues_identical"]}, ensure_ascii=False, indent=1))
    for row in rows:
        print(row["project_id"], "pairs", row["pairs_base"], row["pairs_new"], "+", row["pairs_added"], "-", row["pairs_removed"],
              "| issues", row["issues_base"], row["issues_new"], "+", row["issues_added"], "-", row["issues_removed"],
              "| eligible", row["eligible"], "strict", row["new_views"]["strict"], "cont", row["new_views"]["with_continuity"],
              "int", row["new_views"]["with_internal"], "total", row["new_views"]["total"],
              "| links", row["device_internal_links"])


if __name__ == "__main__":
    main()
