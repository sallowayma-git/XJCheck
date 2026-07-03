from __future__ import annotations

import pandas as pd

from dwg_audit.report import compare_regression_metrics
from dwg_audit.report.regression import summarize_regression_metrics


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
