"""Compare two replay runs project by project: pairs, issues, and SuperWORKS port coverage.

Usage: python compare_runs.py <base_run_dir> <new_run_dir> [--projects ...] [--json out.json]

Pairs and issues are compared as multisets of their content (issue_id is a sequence number and is ignored).
Coverage: the base run's `consumed` against the new run's `consumed` (must be equal) and against the new run's
`consumed_with_continuity` (the additive figure).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import xpage_io  # noqa: E402


def _pair_key(row):
    return (row["pair_id"], row["status"], str(row["left_value"]), str(row["right_value"]), str(row["pair_kind"]),
            str(row["sheet_id"]))


def _issue_key(issue):
    return tuple(str(issue.get(k, "")) for k in ("rule_id", "severity", "status", "pair_id", "sheet_id", "left_value",
                                                  "right_value", "message"))


def _project_dir(run_dir: Path, pid: str) -> Path:
    complete = json.loads((run_dir / pid / "complete.json").read_text(encoding="utf-8"))
    return Path(complete["project_dir"])


def compare_project(base_run: Path, new_run: Path, pid: str) -> dict:
    base_f = _project_dir(base_run, pid) / "findings"
    new_f = _project_dir(new_run, pid) / "findings"
    base_pairs = pd.read_parquet(base_f / "pairs.parquet", columns=["pair_id", "status", "left_value", "right_value", "pair_kind", "sheet_id"])
    new_pairs = pd.read_parquet(new_f / "pairs.parquet", columns=["pair_id", "status", "left_value", "right_value", "pair_kind", "sheet_id"])
    base_counter = Counter(_pair_key(r) for r in base_pairs.to_dict("records"))
    new_counter = Counter(_pair_key(r) for r in new_pairs.to_dict("records"))
    base_issues = json.loads((_project_dir(base_run, pid) / "audit" / "issues.json").read_text(encoding="utf-8"))
    new_issues = json.loads((_project_dir(new_run, pid) / "audit" / "issues.json").read_text(encoding="utf-8"))
    base_ic = Counter(_issue_key(i) for i in base_issues)
    new_ic = Counter(_issue_key(i) for i in new_issues)
    base_cov = pd.read_parquet(base_f / "sw_port_coverage.parquet", columns=["eligible", "consumed"])
    new_cov = pd.read_parquet(new_f / "sw_port_coverage.parquet", columns=["eligible", "consumed", "consumed_with_continuity"])
    base_cov = base_cov[base_cov.eligible.astype(bool)]
    new_cov = new_cov[new_cov.eligible.astype(bool)]
    new_summary = json.loads((new_f / "superworks_summary.json").read_text(encoding="utf-8"))
    base_summary = json.loads((base_f / "superworks_summary.json").read_text(encoding="utf-8"))
    eligible_base = int(base_cov.eligible.sum())
    eligible_new = int(new_cov.eligible.sum())
    return {
        "project_id": pid,
        "pairs_base": len(base_pairs), "pairs_new": len(new_pairs),
        "pairs_added": sum((new_counter - base_counter).values()),
        "pairs_removed": sum((base_counter - new_counter).values()),
        "issues_base": len(base_issues), "issues_new": len(new_issues),
        "issues_added": sum((new_ic - base_ic).values()),
        "issues_removed": sum((base_ic - new_ic).values()),
        "issue_added_samples": [list(k) for k in (new_ic - base_ic).keys()][:20],
        "issue_removed_samples": [list(k) for k in (base_ic - new_ic).keys()][:20],
        "eligible_base": eligible_base, "eligible_new": eligible_new,
        "consumed_base": int(base_cov.consumed.sum()), "consumed_new": int(new_cov.consumed.sum()),
        "consumed_with_continuity_new": int(new_cov.consumed_with_continuity.sum()),
        "port_coverage_base_summary": base_summary["port_coverage"]["ratio"],
        "port_coverage_new_summary": new_summary["port_coverage"]["ratio"],
        "port_coverage_with_continuity": new_summary.get("port_coverage_with_continuity", {}).get("ratio"),
        "cross_page_stats": new_summary.get("cross_page", {}).get("stats", {}),
        "cross_page_candidates": new_summary.get("cross_page", {}).get("candidate_counts", {}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_run")
    parser.add_argument("new_run")
    parser.add_argument("--projects", nargs="*", default=None)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    base_run, new_run = Path(args.base_run), Path(args.new_run)
    projects = args.projects or sorted(p.name for p in new_run.iterdir() if p.is_dir() and p.name.startswith("p"))
    rows = [compare_project(base_run, new_run, pid) for pid in projects]
    totals = Counter()
    for row in rows:
        for key in ("pairs_base", "pairs_new", "pairs_added", "pairs_removed", "issues_base", "issues_new",
                    "issues_added", "issues_removed", "eligible_base", "eligible_new", "consumed_base",
                    "consumed_new", "consumed_with_continuity_new"):
            totals[key] += row[key]
    summary = {"projects": projects, "totals": dict(totals), "rows": rows}
    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary["totals"], ensure_ascii=False, indent=1))
    for row in rows:
        print(row["project_id"], "pairs", row["pairs_base"], row["pairs_new"], "+", row["pairs_added"], "-", row["pairs_removed"],
              "| issues", row["issues_base"], row["issues_new"], "+", row["issues_added"], "-", row["issues_removed"],
              "| consumed", row["consumed_base"], row["consumed_new"], "cont", row["consumed_with_continuity_new"],
              "of", row["eligible_new"])


if __name__ == "__main__":
    main()
