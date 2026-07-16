from __future__ import annotations

from pathlib import Path

import pandas as pd

from dwg_audit.audit.topology_ground_truth import evaluate_topology_ground_truth


def test_ground_truth_fixture_has_stable_validation_scope() -> None:
    fixture = pd.read_csv(
        Path(__file__).parents[1] / "fixtures" / "topology_ground_truth_v1.csv"
    )

    assert len(fixture) == 12
    assert set(fixture["project_id"]) == {"P003"}
    assert set(fixture["expected_state"]) == {"ASSERTED", "REJECTED"}
    assert fixture["sample_id"].is_unique
    assert fixture["review_basis"].str.len().gt(0).all()


def test_ground_truth_evaluator_matches_handles_and_reports_false_crossings() -> None:
    lines = pd.DataFrame(
        [
            {"line_id": "L1", "handle": "H1"},
            {"line_id": "L2", "handle": "H2"},
        ]
    )
    decisions = pd.DataFrame(
        [
            {
                "sheet_id": "S1",
                "decision_kind": "intersection",
                "reason_codes": ["marker"],
                "source_line_ids": ["L1", "L2"],
                "decision_state": "ASSERTED",
            }
        ]
    )
    truth = pd.DataFrame(
        [
            {
                "sample_id": "G1",
                "sheet_id": "S1",
                "decision_kind": "intersection",
                "reason_code": "marker",
                "source_handles": "H1|H2",
                "expected_state": "REJECTED",
            }
        ]
    )

    result = evaluate_topology_ground_truth(decisions, lines, truth)

    assert result["matched_count"] == 1
    assert result["state_accuracy"] == 0.0
    assert result["asserted_crossing_false_connect_count"] == 1
