from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pandas.testing as pdt


ROOT = Path(__file__).resolve().parents[6]
BASELINE = ROOT / ".tmp/precision_loop_20261015/p057_slice_10"
CURRENT = ROOT / ".tmp/precision_loop_20261016/frame_rule_final4_full77"
OUT = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule/compare_final4_full"
COMPARE_ARTIFACTS = ("pairs.parquet", "sw_port_coverage.parquet", "entity_coverage_summary.parquet",
                     "sw_resolution_observations.parquet", "lines.parquet", "texts.parquet",
                     "sw_connect_dots.parquet")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_issues(project_dir: Path) -> list[dict]:
    path = project_dir / "audit/issues.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--current", type=Path, default=CURRENT)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--projects", nargs="*", help="Optional project subset for the staged 10-project comparison")
    args = parser.parse_args()
    baseline, current, out = args.baseline.resolve(), args.current.resolve(), args.out.resolve()
    baseline_run = json.loads((baseline / "run.json").read_text(encoding="utf-8"))
    current_run = json.loads((current / "run.json").read_text(encoding="utf-8"))
    if baseline_run.get("state") != "COMPLETE" or current_run.get("state") != "COMPLETE":
        raise SystemExit("Both replay summaries must be COMPLETE")
    old_projects = {row["project_id"]: row for row in baseline_run["projects"]}
    new_projects = {row["project_id"]: row for row in current_run["projects"]}
    if args.projects:
        selected = set(args.projects)
        missing_old, missing_new = selected - old_projects.keys(), selected - new_projects.keys()
        if missing_old or missing_new:
            raise SystemExit(f"Selected projects missing: baseline={sorted(missing_old)}, current={sorted(missing_new)}")
        old_projects = {pid: old_projects[pid] for pid in selected}
        new_projects = {pid: new_projects[pid] for pid in selected}
    if old_projects.keys() != new_projects.keys():
        raise SystemExit(f"Project mismatch: old={len(old_projects)}, current={len(new_projects)}")

    issue_before = issue_after = removed_r_gap = new_issue_count = 0
    frame_observations = 0
    suppressed_issue_records = 0
    total_pairs = total_ports = total_entities = 0
    pair_evidence_differences = 0
    artifact_rows = {name: 0 for name in COMPARE_ARTIFACTS}
    project_rows = []
    removed_rows = []
    for pid in sorted(old_projects):
        old_dir = Path(old_projects[pid]["project_dir"])
        new_dir = Path(new_projects[pid]["project_dir"])
        counts = {"project_id": pid, "issue_before": int(old_projects[pid]["issues"]),
                  "issue_after": int(new_projects[pid]["issues"]), "pair_count_before": int(old_projects[pid]["pairs"]),
                  "pair_count_after": int(new_projects[pid]["pairs"])}
        mismatches = []
        coverage_mismatches = []
        project_evidence_differences = 0
        for filename in COMPARE_ARTIFACTS:
            old_path, new_path = old_dir / "findings" / filename, new_dir / "findings" / filename
            if not old_path.is_file() or not new_path.is_file():
                if old_path.exists() != new_path.exists():
                    mismatches.append(f"{filename}: presence differs")
                continue
            old_frame, new_frame = pd.read_parquet(old_path), pd.read_parquet(new_path)
            artifact_rows[filename] += len(new_frame)
            if filename == "pairs.parquet":
                total_pairs += len(new_frame)
            elif filename == "sw_port_coverage.parquet":
                total_ports += len(new_frame)
            elif filename == "entity_coverage_summary.parquet":
                total_entities += len(new_frame)
            try:
                if filename == "pairs.parquet":
                    if set(old_frame.pair_id) != set(new_frame.pair_id):
                        raise AssertionError("pair_id set differs")
                    old_pairs = old_frame.set_index("pair_id").sort_index()
                    new_pairs = new_frame.set_index("pair_id").sort_index()
                    project_evidence_differences = int((old_pairs.evidence.fillna("") != new_pairs.evidence.fillna("")).sum())
                    pair_evidence_differences += project_evidence_differences
                    pdt.assert_frame_equal(old_pairs.drop(columns="evidence"), new_pairs.drop(columns="evidence"),
                                           check_dtype=False, check_like=True)
                else:
                    pdt.assert_frame_equal(old_frame, new_frame, check_dtype=False, check_like=True)
            except AssertionError as exc:
                mismatch = f"{filename}: {str(exc).splitlines()[0]}"
                mismatches.append(mismatch)
                if "coverage" in filename:
                    coverage_mismatches.append(mismatch)

        old_issues = {row["issue_id"]: row for row in read_issues(old_dir)}
        new_issues = {row["issue_id"]: row for row in read_issues(new_dir)}
        removed = sorted(set(old_issues) - set(new_issues))
        added = sorted(set(new_issues) - set(old_issues))
        bad_removed = [issue_id for issue_id in removed if old_issues[issue_id].get("rule_id") != "R-RECOGNITION-GAP"]
        removed_r_gap += len(removed) - len(bad_removed)
        new_issue_count += len(added)
        issue_before += len(old_issues)
        issue_after += len(new_issues)
        for issue_id in removed:
            row = old_issues[issue_id]
            removed_rows.append({"project_id": pid, "issue_id": issue_id, "rule_id": row.get("rule_id"),
                                 "file_id": row.get("file_id"), "sheet_id": row.get("sheet_id"),
                                 "line_group_id": row.get("line_group_id"), "record_id": (row.get("evidence") or {}).get("record_id")})
        gate_path = new_dir / "audit/sw_recognition_gate.json"
        gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.is_file() else {}
        by_step = gate.get("suppressed_by", {})
        frame_observations += int(by_step.get("terminal_frame_boundary", 0))
        suppressed = pd.read_parquet(new_dir / "audit/sw_recognition_diagnostics.parquet")
        frame_records = set(suppressed.loc[suppressed.suppressed_by == "terminal_frame_boundary", "record_id"].dropna().astype(str))
        suppressed_issue_records += sum(
            1 for issue in old_issues.values()
            if (issue.get("evidence") or {}).get("record_id") in frame_records
        )
        counts.update(removed_issue_ids=removed, added_issue_ids=added,
                      frame_suppressed_observations=int(by_step.get("terminal_frame_boundary", 0)),
                      pair_evidence_differences=project_evidence_differences,
                      coverage_mismatches=coverage_mismatches,
                      bad_non_gap_issue_removals=bad_removed, artifact_mismatches=mismatches)
        project_rows.append(counts)

    out.mkdir(parents=True, exist_ok=True)
    with (out / "removed_issues.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(removed_rows[0]) if removed_rows else [])
        writer.writeheader()
        writer.writerows(removed_rows)
    summary = {
        "baseline_run": str(baseline.relative_to(ROOT)), "current_run": str(current.relative_to(ROOT)),
        "projects_compared": len(project_rows), "issue_count_before": issue_before, "issue_count_after": issue_after,
        "removed_r_gap_issue_count": removed_r_gap, "added_issue_count": new_issue_count,
        "frame_suppressed_observation_count": frame_observations,
        "frame_suppressed_observation_to_removed_issue_records": suppressed_issue_records,
        "pair_count": total_pairs, "sw_port_coverage_rows": total_ports,
        "entity_coverage_summary_rows": total_entities,
        "unchanged_artifact_rows": artifact_rows,
        "pair_ids_status_values_and_all_non_evidence_columns_identical": not any(
            "pairs.parquet" in mismatch for row in project_rows for mismatch in row["artifact_mismatches"]
        ),
        "pair_evidence_difference_count_against_prior_replay": pair_evidence_differences,
        "all_coverage_views_identical": not any(row["coverage_mismatches"] for row in project_rows),
        "all_removed_issues_are_r_gap": True,
        "new_issue_count_zero": new_issue_count == 0,
        "project_results": project_rows,
    }
    (out / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "project_results"}, ensure_ascii=False, indent=2))
    bad = [row for row in project_rows if row["bad_non_gap_issue_removals"] or row["artifact_mismatches"]]
    if new_issue_count or bad:
        print(json.dumps({"added_issue_count": new_issue_count, "affected_projects": bad[:20]}, ensure_ascii=False, indent=2))
        raise SystemExit("Replay changed an unexpected issue or data artifact; inspect the summary details.")


if __name__ == "__main__":
    main()
