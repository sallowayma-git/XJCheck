"""Read-only before/after comparison of one replayed project (issues and pairs).

Usage: python compare_project.py <baseline_project_dir> <after_project_dir> <out_json>
Project dirs are the replay '<output>/<pid>/-' folders. Pairs are matched by a content key
(not pair_id, which can shift when pair construction changes).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


def _load(project: Path):
    pairs = pd.read_parquet(project / "findings/pairs.parquet")
    issues = json.loads((project / "audit/issues.json").read_text(encoding="utf-8"))
    return pairs, issues


def _pair_key(row) -> tuple:
    def norm(value):
        return None if value is None or (isinstance(value, float) and pd.isna(value)) else value
    return (
        norm(row.pair_kind), norm(row.left_value), norm(row.right_value),
        norm(row.left_text_id), norm(row.right_text_id), norm(row.line_group_id), norm(row.sheet_id),
    )


def _issue_key(issue) -> tuple:
    return (issue["rule_id"], issue.get("pair_id"), issue.get("sheet_id"), issue.get("left_value"), issue.get("right_value"))


def main(baseline: str, after: str, out: str) -> None:
    base_pairs, base_issues = _load(Path(baseline))
    new_pairs, new_issues = _load(Path(after))

    base_rows = Counter()
    base_status = {}
    for row in base_pairs.itertuples(index=False):
        key = _pair_key(row)
        base_rows[key] += 1
        base_status.setdefault(key, []).append(row.status)
    new_rows = Counter()
    new_status = {}
    for row in new_pairs.itertuples(index=False):
        key = _pair_key(row)
        new_rows[key] += 1
        new_status.setdefault(key, []).append(row.status)

    removed = sorted((base_rows - new_rows).elements(), key=str)
    added = sorted((new_rows - base_rows).elements(), key=str)
    status_changes = []
    for key in sorted(set(base_status) & set(new_status), key=str):
        if sorted(base_status[key]) != sorted(new_status[key]):
            status_changes.append({"key": list(key), "before": sorted(base_status[key]), "after": sorted(new_status[key])})

    base_issue_keys = Counter(_issue_key(i) for i in base_issues)
    new_issue_keys = Counter(_issue_key(i) for i in new_issues)
    result = {
        "pairs_before": len(base_pairs), "pairs_after": len(new_pairs),
        "issues_before": len(base_issues), "issues_after": len(new_issues),
        "pairs_removed": [list(k) for k in removed],
        "pairs_added": [list(k) for k in added],
        "pair_status_changes": status_changes,
        "issues_removed": [list(k) for k in (base_issue_keys - new_issue_keys).elements()],
        "issues_added": [list(k) for k in (new_issue_keys - base_issue_keys).elements()],
        "issues_after_detail": [
            {"rule_id": i["rule_id"], "status": i.get("status"), "pair_id": i.get("pair_id"),
             "left_value": i.get("left_value"), "right_value": i.get("right_value"),
             "sheet_no": i.get("sheet_no"), "message": i.get("message"),
             "explanation": i.get("explanation")}
            for i in new_issues
        ],
    }
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k in ("pairs_before", "pairs_after", "issues_before", "issues_after")}, ensure_ascii=False))
    print("pairs removed", len(removed), "added", len(added), "status changes", len(status_changes))
    print("issues removed", len(result["issues_removed"]), "added", len(result["issues_added"]))


if __name__ == "__main__":
    main(*sys.argv[1:4])
