from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.report import compare_project_regressions
from dwg_audit.report import compare_regression_metrics
from dwg_audit.report.regression import summarize_regression_metrics
from dwg_audit.report.regression import write_regression_report


def test_summarize_regression_metrics_counts_pairs_issues_rules_and_statuses() -> None:
    metrics = summarize_regression_metrics(
        {
            "pairs": pd.DataFrame(
                [
                    {"pair_id": "P1", "status": "pass"},
                    {"pair_id": "P2", "status": "review"},
                    {"pair_id": "P3", "status": "review"},
                ]
            ),
            "issues": pd.DataFrame(
                [
                    {"issue_id": "I1", "rule_id": "R-CROSS-PAGE-CONFLICT", "status": "open"},
                    {"issue_id": "I2", "rule_id": "R-CROSS-PAGE-CONFLICT", "status": "open"},
                    {"issue_id": "I3", "rule_id": "R-ONE-TO-MANY", "status": "accepted"},
                ]
            ),
        }
    )

    assert metrics == {
        "pair_count": 3,
        "issue_count": 3,
        "rule_counts": {"R-CROSS-PAGE-CONFLICT": 2, "R-ONE-TO-MANY": 1},
        "status_counts": {
            "pairs": {"pass": 1, "review": 2},
            "issues": {"accepted": 1, "open": 2},
        },
        "precision": None,
        "recall": None,
        "precision_recall_status": "not_computed",
    }


def test_compare_regression_metrics_reports_current_baseline_and_deltas() -> None:
    baseline = {
        "pairs": pd.DataFrame(
            [
                {"pair_id": "P1", "status": "pass"},
                {"pair_id": "P2", "status": "review"},
            ]
        ),
        "issues": pd.DataFrame(
            [
                {"issue_id": "I1", "rule_id": "R-CROSS-PAGE-CONFLICT", "status": "open"},
            ]
        ),
    }
    current = {
        "pairs": pd.DataFrame(
            [
                {"pair_id": "P1", "status": "pass"},
                {"pair_id": "P2", "status": "pass"},
                {"pair_id": "P3", "status": "fail"},
            ]
        ),
        "issues": pd.DataFrame(
            [
                {"issue_id": "I1", "rule_id": "R-CROSS-PAGE-CONFLICT", "status": "open"},
                {"issue_id": "I2", "rule_id": "R-ONE-TO-MANY", "status": "open"},
            ]
        ),
    }

    comparison = compare_regression_metrics(baseline, current)

    assert comparison["baseline"]["pair_count"] == 2
    assert comparison["current"]["issue_count"] == 2
    assert comparison["delta"] == {
        "pair_count": 1,
        "issue_count": 1,
        "rule_counts": {"R-CROSS-PAGE-CONFLICT": 0, "R-ONE-TO-MANY": 1},
        "status_counts": {
            "pairs": {"fail": 1, "pass": 1, "review": -1},
            "issues": {"open": 1},
        },
    }
    assert comparison["precision"] is None
    assert comparison["recall"] is None
    assert comparison["precision_recall_status"] == "not_computed"


def test_regression_metrics_tolerates_missing_frames_and_columns() -> None:
    comparison = compare_regression_metrics({}, {"pairs": pd.DataFrame([{"pair_id": "P1"}])})

    assert comparison["baseline"]["pair_count"] == 0
    assert comparison["current"]["pair_count"] == 1
    assert comparison["current"]["issue_count"] == 0
    assert comparison["current"]["rule_counts"] == {}
    assert comparison["current"]["status_counts"] == {"pairs": {}, "issues": {}}


def _write_project_artifacts(project_dir: Path, *, pair_statuses: list[str], issue_rules: list[str]) -> None:
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    findings_dir.mkdir(parents=True)
    audit_dir.mkdir()
    (project_dir / "manifest.json").write_text(
        json.dumps({"project_name": project_dir.name, "project_id": project_dir.name}, ensure_ascii=False),
        encoding="utf-8",
    )
    pd.DataFrame([{"pair_id": f"P{index}", "status": status} for index, status in enumerate(pair_statuses, start=1)]).to_parquet(
        findings_dir / "pairs.parquet",
        index=False,
    )
    pd.DataFrame(
        [
            {"issue_id": f"I{index}", "rule_id": rule_id, "status": "open"}
            for index, rule_id in enumerate(issue_rules, start=1)
        ]
    ).to_parquet(audit_dir / "issues.parquet", index=False)


def test_compare_project_regressions_and_write_report(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    output = tmp_path / "regression"
    _write_project_artifacts(baseline, pair_statuses=["pass", "review"], issue_rules=["R-CROSS-PAGE-CONFLICT"])
    _write_project_artifacts(current, pair_statuses=["pass", "pass", "fail"], issue_rules=["R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY"])

    comparison = compare_project_regressions(baseline, current)
    report_dir = write_regression_report(baseline, current, output)
    markdown = (report_dir / "regression_report.md").read_text(encoding="utf-8")
    payload = json.loads((report_dir / "regression_report.json").read_text(encoding="utf-8"))

    assert comparison["baseline_project"]["project_name"] == "baseline"
    assert comparison["current_project"]["project_name"] == "current"
    assert comparison["delta"]["pair_count"] == 1
    assert comparison["delta"]["issue_count"] == 1
    assert comparison["delta"]["rule_counts"] == {"R-CROSS-PAGE-CONFLICT": 0, "R-ONE-TO-MANY": 1}
    assert "Regression Report" in markdown
    assert "Delta pair_count: `1`" in markdown
    assert payload["delta"]["issue_count"] == 1
