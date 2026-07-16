from __future__ import annotations

import json

import pandas as pd

from dwg_audit.audit.topology_decisions import build_topology_decision_frames
from dwg_audit.audit.topology_decisions import topology_decision_invariant_violations


def _observations() -> pd.DataFrame:
    rows = []
    for index, (kind, state, reason) in enumerate(
        [
            ("junction", "ASSERTED", "asserted_endpoint_merge_v1"),
            ("endpoint_gap", "POSSIBLE", "unique_collinear_open_endpoint_gap_v1"),
            ("crossing", "REJECTED", "unmarked_internal_crossing_policy_v1"),
            ("endpoint_gap", "UNKNOWN", "ambiguous_collinear_open_endpoint_gap_v1"),
        ]
    ):
        rows.append(
            {
                "observation_id": f"O{index}",
                "project_id": "P",
                "sheet_id": "S",
                "observation_kind": kind,
                "state": state,
                "node_a_id": f"N{index}a",
                "node_b_id": f"N{index}b",
                "component_a_id": f"C{index}a",
                "component_b_id": f"C{index}b",
                "distance": float(index),
                "alignment_error": 0.0,
                "source_line_ids": [f"L{index}"],
                "evidence_ids": [],
                "reason_code": reason,
                "requires_review": state in {"POSSIBLE", "UNKNOWN"},
            }
        )
    return pd.DataFrame(rows)


def test_decisions_preserve_all_four_states_and_only_asserted_is_union_eligible() -> None:
    observations, decisions, summary = build_topology_decision_frames(_observations())

    assert list(observations["state"]) == [
        "ASSERTED",
        "POSSIBLE",
        "REJECTED",
        "UNKNOWN",
    ]
    assert decisions.loc[decisions["union_eligible"], "decision_state"].tolist() == [
        "ASSERTED"
    ]
    assert not decisions["union_applied"].any()
    assert summary["state_counts"] == {
        "ASSERTED": 1,
        "POSSIBLE": 1,
        "REJECTED": 1,
        "UNKNOWN": 1,
    }
    assert summary["non_asserted_union_violation_count"] == 0
    assert topology_decision_invariant_violations(decisions) == []


def test_decisions_are_deterministic_append_only_and_explainable() -> None:
    first_observations, first_decisions, _ = build_topology_decision_frames(
        _observations()
    )
    second_observations, second_decisions, _ = build_topology_decision_frames(
        _observations()
    )

    pd.testing.assert_frame_equal(first_observations, second_observations)
    pd.testing.assert_frame_equal(first_decisions, second_decisions)
    assert all(first_decisions["reason_codes"].map(len) == 2)
    assert all(
        json.loads(value)["selected"] in {"ASSERTED", "POSSIBLE", "REJECTED", "UNKNOWN"}
        for value in first_decisions["alternatives_json"]
    )


def test_invariant_verifier_detects_non_asserted_union_attempt() -> None:
    _, decisions, _ = build_topology_decision_frames(_observations())
    decisions.loc[decisions["decision_state"] == "POSSIBLE", "union_applied"] = True

    violations = topology_decision_invariant_violations(decisions)

    assert len(violations) == 1
