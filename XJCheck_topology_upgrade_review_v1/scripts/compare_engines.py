#!/usr/bin/env python3
"""Compare legacy and topology-V2 outputs at project, pair and issue levels."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def project_map(root: Path) -> dict[str, Path]:
    mapping = {}
    for manifest_path in root.rglob("manifest.json"):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        project_id = str(payload.get("project_id") or manifest_path.parent.name)
        mapping[project_id] = manifest_path.parent
    return mapping


def read_first_parquet(project_dir: Path, names: list[str]) -> pd.DataFrame:
    for name in names:
        candidates = list(project_dir.rglob(name))
        if candidates:
            return pd.read_parquet(candidates[0])
    return pd.DataFrame()


def normalize_relation_keys(frame: pd.DataFrame) -> set[str]:
    if frame.empty:
        return set()
    rows = frame.to_dict("records")
    keys = set()
    for row in rows:
        if row.get("canonical_identity"):
            keys.add(f"identity:{row['canonical_identity']}")
            continue
        if row.get("pair_key"):
            keys.add(f"pair:{row['pair_key']}")
            continue
        if row.get("pair_key_unordered"):
            keys.add(f"pair:{row['pair_key_unordered']}")
            continue
        left = row.get("left_value")
        right = row.get("right_value")
        if left is not None and right is not None:
            a, b = sorted([str(left), str(right)])
            keys.add(f"pair:{a}--{b}")
            continue
        source = row.get("source_endpoint_id")
        target = row.get("target_endpoint_id")
        if source and target:
            keys.add(f"endpoints:{source}->{target}")
    return keys


def load_issues(project_dir: Path) -> list[dict[str, Any]]:
    candidates = list(project_dir.rglob("issues.json"))
    if not candidates:
        return []
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("issues", "items", "records"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def issue_key(issue: dict[str, Any]) -> str:
    rule = issue.get("rule_id") or issue.get("issue_type") or "unknown"
    sheets = sorted(str(item) for item in issue.get("sheet_ids", []))
    values = sorted(str(item) for item in issue.get("values", []))
    summary = str(issue.get("summary") or issue.get("title") or "")
    return json.dumps([rule, sheets, values, summary], ensure_ascii=False)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    legacy_projects = project_map(args.legacy)
    v2_projects = project_map(args.v2)
    project_ids = sorted(set(legacy_projects) | set(v2_projects))

    summary_rows = []
    relation_diff_rows = []
    issue_diff_rows = []

    for project_id in project_ids:
        legacy_dir = legacy_projects.get(project_id)
        v2_dir = v2_projects.get(project_id)
        legacy_relations = normalize_relation_keys(
            read_first_parquet(legacy_dir, ["pairs.parquet"]) if legacy_dir else pd.DataFrame()
        )
        v2_relations = normalize_relation_keys(
            read_first_parquet(
                v2_dir,
                ["cross_page_matches.parquet", "selected_cross_page_matches.parquet", "pairs.parquet"],
            )
            if v2_dir
            else pd.DataFrame()
        )
        legacy_issues = {issue_key(item): item for item in load_issues(legacy_dir)} if legacy_dir else {}
        v2_issues = {issue_key(item): item for item in load_issues(v2_dir)} if v2_dir else {}

        common_relations = legacy_relations & v2_relations
        only_legacy_relations = legacy_relations - v2_relations
        only_v2_relations = v2_relations - legacy_relations
        common_issues = set(legacy_issues) & set(v2_issues)
        only_legacy_issues = set(legacy_issues) - set(v2_issues)
        only_v2_issues = set(v2_issues) - set(legacy_issues)

        summary_rows.append(
            {
                "project_id": project_id,
                "legacy_present": legacy_dir is not None,
                "v2_present": v2_dir is not None,
                "legacy_relation_count": len(legacy_relations),
                "v2_relation_count": len(v2_relations),
                "common_relation_count": len(common_relations),
                "only_legacy_relation_count": len(only_legacy_relations),
                "only_v2_relation_count": len(only_v2_relations),
                "legacy_issue_count": len(legacy_issues),
                "v2_issue_count": len(v2_issues),
                "common_issue_count": len(common_issues),
                "only_legacy_issue_count": len(only_legacy_issues),
                "only_v2_issue_count": len(only_v2_issues),
            }
        )
        for relation in sorted(only_legacy_relations):
            relation_diff_rows.append({"project_id": project_id, "side": "legacy_only", "relation_key": relation})
        for relation in sorted(only_v2_relations):
            relation_diff_rows.append({"project_id": project_id, "side": "v2_only", "relation_key": relation})
        for key in sorted(only_legacy_issues):
            issue_diff_rows.append({"project_id": project_id, "side": "legacy_only", "issue_key": key})
        for key in sorted(only_v2_issues):
            issue_diff_rows.append({"project_id": project_id, "side": "v2_only", "issue_key": key})

    write_csv(args.output / "engine_comparison_by_project.csv", summary_rows)
    write_csv(args.output / "relation_differences.csv", relation_diff_rows)
    write_csv(args.output / "issue_differences.csv", issue_diff_rows)
    aggregate = {
        "project_count": len(project_ids),
        "legacy_missing_projects": sorted(set(v2_projects) - set(legacy_projects)),
        "v2_missing_projects": sorted(set(legacy_projects) - set(v2_projects)),
        "total_legacy_relations": sum(row["legacy_relation_count"] for row in summary_rows),
        "total_v2_relations": sum(row["v2_relation_count"] for row in summary_rows),
        "total_common_relations": sum(row["common_relation_count"] for row in summary_rows),
        "total_legacy_issues": sum(row["legacy_issue_count"] for row in summary_rows),
        "total_v2_issues": sum(row["v2_issue_count"] for row in summary_rows),
        "warning": "Count reduction is not success by itself. Review project-held-out precision, recall and witness completeness.",
    }
    (args.output / "engine_comparison.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
