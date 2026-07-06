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
            "pages": pd.DataFrame(
                [
                    {"sheet_id": "S1"},
                    {"sheet_id": "S2"},
                ]
            ),
            "texts": pd.DataFrame(
                [
                    {"text_id": "T1", "sheet_id": "S1", "is_numeric_candidate": True},
                    {"text_id": "T2", "sheet_id": "S1", "is_numeric_candidate": False},
                    {"text_id": "T3", "sheet_id": "S2", "is_numeric_candidate": True},
                ]
            ),
            "lines": pd.DataFrame(
                [
                    {"line_id": "L1", "sheet_id": "S1"},
                    {"line_id": "L2", "sheet_id": "S2"},
                ]
            ),
            "line_groups": pd.DataFrame([{"line_group_id": "G1", "sheet_id": "S1"}]),
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
        "extraction_counts": {
            "pages": 2,
            "texts": 3,
            "numeric_texts": 2,
            "lines": 2,
            "line_groups": 1,
        },
        "precision": None,
        "recall": None,
        "precision_recall_status": "not_computed",
    }


def test_compare_regression_metrics_reports_current_baseline_and_deltas() -> None:
    baseline = {
        "pages": pd.DataFrame(
            [
                {"sheet_id": "S1", "filename": "04.dwg", "sheet_order": 4},
                {"sheet_id": "S2", "filename": "05.dwg", "sheet_order": 5},
            ]
        ),
        "texts": pd.DataFrame(
            [
                {"text_id": "T1", "sheet_id": "S1", "is_numeric_candidate": True},
                {"text_id": "T2", "sheet_id": "S2", "is_numeric_candidate": False},
            ]
        ),
        "lines": pd.DataFrame(
            [
                {"line_id": "L1", "sheet_id": "S1"},
                {"line_id": "L2", "sheet_id": "S2"},
            ]
        ),
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
        "pages": pd.DataFrame(
            [
                {"sheet_id": "SX1", "filename": "04.dwg", "sheet_order": 4},
                {"sheet_id": "SX2", "filename": "05.dwg", "sheet_order": 5},
            ]
        ),
        "texts": pd.DataFrame(
            [
                {"text_id": "T1", "sheet_id": "SX1", "is_numeric_candidate": True},
                {"text_id": "T2", "sheet_id": "SX1", "is_numeric_candidate": True},
                {"text_id": "T3", "sheet_id": "SX2", "is_numeric_candidate": False},
            ]
        ),
        "lines": pd.DataFrame(
            [
                {"line_id": "L1", "sheet_id": "SX1"},
            ]
        ),
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
        "extraction_counts": {
            "line_groups": 0,
            "lines": -1,
            "numeric_texts": 1,
            "pages": 0,
            "texts": 1,
        },
    }
    assert comparison["precision"] is None
    assert comparison["recall"] is None
    assert comparison["precision_recall_status"] == "not_computed"
    assert comparison["non_regression_checks"]["texts"]["status"] == "ok"
    assert comparison["non_regression_checks"]["texts"]["comparison_mode"] == "per_page"
    assert comparison["non_regression_checks"]["lines"]["status"] == "regressed"
    assert comparison["non_regression_checks"]["lines"]["comparison_mode"] == "per_page"
    assert comparison["non_regression_checks"]["lines"]["dropped_sheets"] == [
        {
            "page_key": "0005:05.dwg",
            "sheet_id": "S2",
            "filename": "05.dwg",
            "sheet_order": 5,
            "baseline": 1,
            "current": 0,
            "delta": -1,
        }
    ]


def test_regression_metrics_tolerates_missing_frames_and_columns() -> None:
    comparison = compare_regression_metrics({}, {"pairs": pd.DataFrame([{"pair_id": "P1"}])})

    assert comparison["baseline"]["pair_count"] == 0
    assert comparison["current"]["pair_count"] == 1
    assert comparison["current"]["issue_count"] == 0
    assert comparison["current"]["rule_counts"] == {}
    assert comparison["current"]["status_counts"] == {"pairs": {}, "issues": {}}
    assert comparison["current"]["extraction_counts"] == {
        "pages": 0,
        "texts": 0,
        "numeric_texts": 0,
        "lines": 0,
        "line_groups": 0,
    }
    assert comparison["non_regression_checks"]["texts"]["status"] == "ok"
    assert comparison["non_regression_checks"]["texts"]["comparison_mode"] == "totals_only"
    assert comparison["non_regression_checks"]["lines"]["status"] == "ok"
    assert comparison["non_regression_checks"]["lines"]["comparison_mode"] == "totals_only"


def test_non_regression_check_flags_total_drop_when_sheet_ids_are_missing() -> None:
    comparison = compare_regression_metrics(
        {"texts": pd.DataFrame([{"text_id": "T1"}, {"text_id": "T2"}])},
        {"texts": pd.DataFrame([{"text_id": "T1"}])},
    )

    assert comparison["non_regression_checks"]["texts"]["status"] == "regressed"
    assert comparison["non_regression_checks"]["texts"]["comparison_mode"] == "totals_only"
    assert comparison["non_regression_checks"]["texts"]["dropped_sheets"] == []


def test_compare_regression_metrics_falls_back_when_sheet_order_is_not_numeric() -> None:
    comparison = compare_regression_metrics(
        {
            "pages": pd.DataFrame([{"sheet_id": "S1", "filename": "05.dwg", "sheet_order": "A05"}]),
            "lines": pd.DataFrame([{"line_id": "L1", "sheet_id": "S1"}]),
        },
        {
            "pages": pd.DataFrame([{"sheet_id": "SX1", "filename": "05.dwg", "sheet_order": "A05"}]),
            "lines": pd.DataFrame([]),
        },
    )

    assert comparison["non_regression_checks"]["lines"]["status"] == "regressed"
    assert comparison["non_regression_checks"]["lines"]["comparison_mode"] == "per_page"
    assert comparison["non_regression_checks"]["lines"]["dropped_sheets"] == [
        {
            "page_key": "05.dwg",
            "sheet_id": "S1",
            "filename": "05.dwg",
            "sheet_order": "A05",
            "baseline": 1,
            "current": 0,
            "delta": -1,
        }
    ]


def _write_project_artifacts(
    project_dir: Path,
    *,
    pair_statuses: list[str],
    issue_rules: list[str],
    page_sheet_ids: list[str] | None = None,
    text_sheet_ids: list[str] | None = None,
    line_sheet_ids: list[str] | None = None,
) -> None:
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
            {
                "sheet_id": sheet_id,
                "filename": f"{index + 4:02d}.dwg",
                "sheet_order": index + 4,
            }
            for index, sheet_id in enumerate(page_sheet_ids or ["S1", "S2"])
        ]
    ).to_parquet(findings_dir / "pages.parquet", index=False)
    pd.DataFrame(
        [
            {"text_id": f"T{index}", "sheet_id": sheet_id, "is_numeric_candidate": index % 2 == 0}
            for index, sheet_id in enumerate(text_sheet_ids or [], start=1)
        ]
    ).to_parquet(findings_dir / "texts.parquet", index=False)
    pd.DataFrame(
        [
            {"line_id": f"L{index}", "sheet_id": sheet_id}
            for index, sheet_id in enumerate(line_sheet_ids or [], start=1)
        ]
    ).to_parquet(findings_dir / "lines.parquet", index=False)
    pd.DataFrame([{"line_group_id": "G1", "sheet_id": "S1"}]).to_parquet(findings_dir / "line_groups.parquet", index=False)
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
    _write_project_artifacts(
        baseline,
        pair_statuses=["pass", "review"],
        issue_rules=["R-CROSS-PAGE-CONFLICT"],
        page_sheet_ids=["S1", "S2"],
        text_sheet_ids=["S1", "S2"],
        line_sheet_ids=["S1", "S2"],
    )
    _write_project_artifacts(
        current,
        pair_statuses=["pass", "pass", "fail"],
        issue_rules=["R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY"],
        page_sheet_ids=["SX1", "SX2"],
        text_sheet_ids=["SX1", "SX2", "SX2"],
        line_sheet_ids=["SX1"],
    )

    comparison = compare_project_regressions(baseline, current)
    report_dir = write_regression_report(baseline, current, output)
    markdown = (report_dir / "regression_report.md").read_text(encoding="utf-8")
    payload = json.loads((report_dir / "regression_report.json").read_text(encoding="utf-8"))

    assert comparison["baseline_project"]["project_name"] == "baseline"
    assert comparison["current_project"]["project_name"] == "current"
    assert comparison["delta"]["pair_count"] == 1
    assert comparison["delta"]["issue_count"] == 1
    assert comparison["delta"]["rule_counts"] == {"R-CROSS-PAGE-CONFLICT": 0, "R-ONE-TO-MANY": 1}
    assert comparison["non_regression_checks"]["lines"]["status"] == "regressed"
    assert "Regression Report" in markdown
    assert "Delta pair_count: `1`" in markdown
    assert "Delta texts: `1`" in markdown
    assert "Texts: status=`ok`" in markdown
    assert payload["delta"]["issue_count"] == 1
