
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.report.hard_issue_eval import (
    evaluate_hard_issue_label_pack,
    evaluate_hard_issue_precision,
    predicted_hard_issues,
)


def test_predicted_hard_issues_filters_rules() -> None:
    issues = pd.DataFrame(
        [
            {"rule_id": "R-ONE-TO-MANY", "sheet_id": "S1"},
            {"rule_id": "R-PAIR-MISSING-SIDE", "sheet_id": "S1"},
            {"rule_id": "R-DUPLICATE-PAIR", "sheet_id": "S2"},
        ]
    )
    hard = predicted_hard_issues(issues)
    assert [row["rule_id"] for row in hard] == ["R-ONE-TO-MANY", "R-DUPLICATE-PAIR"]


def test_evaluate_hard_issue_precision_perfect_match(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    audit = project / "audit"
    audit.mkdir(parents=True)
    issues = [
        {
            "rule_id": "R-DUPLICATE-PAIR",
            "sheet_id": "S1",
            "filename": "a.dwg",
            "pair_id": "P1",
            "left_value": "1",
            "right_value": "2",
            "values": ["1", "2"],
        }
    ]
    pd.DataFrame(issues).to_parquet(audit / "issues.parquet", index=False)
    (audit / "audit_v2_summary.json").write_text(
        json.dumps({"witness_completeness": 1.0}), encoding="utf-8"
    )
    pack = {
        "hard_rule_ids": ["R-DUPLICATE-PAIR"],
        "policy": {"not_a_human_gold_standard": True, "label_basis": "test"},
        "projects": {
            "PTEST": {
                "labels": [
                    {
                        "rule_id": "R-DUPLICATE-PAIR",
                        "sheet_id": "S1",
                        "filename": "a.dwg",
                        "pair_id": "P1",
                        "left_value": "1",
                        "right_value": "2",
                        "values": ["1", "2"],
                    }
                ]
            }
        },
    }
    result = evaluate_hard_issue_precision(
        project_id="PTEST", project_dir=project, label_pack=pack
    )
    assert result["tp"] == 1
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["precision"] == 1.0
    assert result["precision_ge_99"] is True


def test_evaluate_label_pack_micro(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    audit = project / "audit"
    audit.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "rule_id": "R-ONE-TO-MANY",
                "sheet_id": "S1",
                "filename": "a.dwg",
                "pair_id": "P1",
                "left_value": "L",
                "right_value": "R",
                "values": [],
            },
            {
                "rule_id": "R-ONE-TO-MANY",
                "sheet_id": "S1",
                "filename": "a.dwg",
                "pair_id": "P2",
                "left_value": "X",
                "right_value": "Y",
                "values": [],
            },
        ]
    ).to_parquet(audit / "issues.parquet", index=False)
    pack_path = tmp_path / "labels.json"
    pack_path.write_text(
        json.dumps(
            {
                "hard_rule_ids": ["R-ONE-TO-MANY"],
                "policy": {"not_a_human_gold_standard": True},
                "projects": {
                    "PTEST": {
                        "labels": [
                            {
                                "rule_id": "R-ONE-TO-MANY",
                                "sheet_id": "S1",
                                "filename": "a.dwg",
                                "pair_id": "P1",
                                "left_value": "L",
                                "right_value": "R",
                                "values": [],
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    summary = evaluate_hard_issue_label_pack(pack_path, {"PTEST": project})
    assert summary["micro_tp"] == 1
    assert summary["micro_fp"] == 1
    assert summary["micro_fn"] == 0
    assert abs(summary["micro_precision"] - 0.5) < 1e-9


def test_missing_prediction_artifact_is_not_a_vacuous_precision_pass(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    pack_path = tmp_path / "labels.json"
    pack_path.write_text(
        json.dumps(
            {
                "hard_rule_ids": ["R-ONE-TO-MANY"],
                "policy": {"not_a_human_gold_standard": False},
                "projects": {
                    "PTEST": {
                        "labels": [
                            {
                                "rule_id": "R-ONE-TO-MANY",
                                "sheet_id": "S1",
                                "filename": "a.dwg",
                                "pair_id": "P1",
                                "left_value": "L",
                                "right_value": "R",
                                "values": [],
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    summary = evaluate_hard_issue_label_pack(pack_path, {"PTEST": project})

    assert summary["prediction_artifacts_valid"] is False
    assert summary["non_vacuous"] is False
    assert summary["micro_precision"] == 0.0
    assert summary["micro_precision_ge_99"] is False
    assert summary["micro_recall_ge_99"] is False
