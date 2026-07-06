from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.ui.app import _filter_issues
from dwg_audit.ui.app import _issue_one_to_many_classification
from dwg_audit.ui.app import _one_to_many_cluster_rows
from dwg_audit.ui.app import _persist_issue_status


def test_filter_issues_filters_by_status_rule_sheet_and_value() -> None:
    issues = pd.DataFrame(
        [
            {
                "issue_id": "I1",
                "severity": "critical",
                "rule_id": "R-CROSS-PAGE-CONFLICT",
                "status": "open",
                "left_value": "101",
                "right_value": "201",
                "evidence": json.dumps({"sheet_no": "08"}, ensure_ascii=False),
            },
            {
                "issue_id": "I2",
                "severity": "review",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "status": "resolved",
                "left_value": "102",
                "right_value": "202",
                "evidence": json.dumps({"sheet_no": "09"}, ensure_ascii=False),
            },
        ]
    )

    filtered = _filter_issues(
        issues,
        severities=["critical"],
        rules=["R-CROSS-PAGE-CONFLICT"],
        statuses=["open"],
        sheet_query="08",
        value_query="101",
    )

    assert filtered["issue_id"].tolist() == ["I1"]


def test_persist_issue_status_updates_parquet_and_json(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    audit_dir = project_dir / "audit"
    audit_dir.mkdir(parents=True)

    issues = pd.DataFrame(
        [
            {"issue_id": "I1", "status": "open", "rule_id": "R1"},
            {"issue_id": "I2", "status": "review", "rule_id": "R2"},
        ]
    )
    issues.to_parquet(audit_dir / "issues.parquet", index=False)
    issues.to_json(audit_dir / "issues.json", orient="records", force_ascii=False, indent=2)

    _persist_issue_status(project_dir, "I1", "resolved")

    parquet_frame = pd.read_parquet(audit_dir / "issues.parquet")
    json_payload = json.loads((audit_dir / "issues.json").read_text(encoding="utf-8"))

    assert parquet_frame.loc[parquet_frame["issue_id"] == "I1", "status"].item() == "resolved"
    assert next(item for item in json_payload if item["issue_id"] == "I1")["status"] == "resolved"


def test_issue_one_to_many_classification_reads_from_evidence() -> None:
    row = pd.Series(
        {
            "issue_id": "I1",
            "evidence": json.dumps({"one_to_many_classification": "conflict"}, ensure_ascii=False),
        }
    )

    assert _issue_one_to_many_classification(row) == "conflict"


def test_one_to_many_cluster_rows_builds_summary_frame() -> None:
    frame = _one_to_many_cluster_rows(
        {
            "one_to_many_review_table": {
                "clusters": [
                    {
                        "left_value": "101",
                        "classification": "conflict",
                        "classification_reason": "cross_page_multi_target",
                        "right_values": ["201", "202"],
                        "sheet_nos": ["04", "05"],
                        "high_confidence_pair_count": 2,
                        "reciprocal_pair_count": 1,
                        "pair_count": 2,
                    }
                ]
            }
        }
    )

    assert frame.to_dict(orient="records") == [
        {
            "left_value": "101",
            "classification": "conflict",
            "classification_reason": "cross_page_multi_target",
            "right_values": "201,202",
            "sheet_nos": "04,05",
            "high_confidence_pairs": "2/2",
            "reciprocal_pairs": "1/2",
        }
    ]
