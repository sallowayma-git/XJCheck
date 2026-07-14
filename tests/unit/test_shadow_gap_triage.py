from __future__ import annotations

from dwg_audit.report.shadow_gap_triage import build_shadow_gap_triage
from dwg_audit.report.shadow_gap_triage import classify_shadow_entity_type


def test_hatch_is_decorative_and_never_authorized() -> None:
    policy = classify_shadow_entity_type("HATCH")
    assert policy["relevance"] == "LIKELY_DECORATIVE"
    assert policy["adapter_authorized"] is False


def test_spline_and_point_remain_review_only() -> None:
    spline = classify_shadow_entity_type("SPLINE")
    point = classify_shadow_entity_type("POINT")
    assert spline["relevance"] == "POSSIBLE_ELECTRICAL_GEOMETRY"
    assert point["relevance"] == "POSSIBLE_MARKER"
    assert spline["adapter_authorized"] is False
    assert point["adapter_authorized"] is False


def test_project_triage_aggregates_counts_without_authorizing_adapters() -> None:
    triage = build_shadow_gap_triage(
        [
            {
                "file_id": "F1",
                "shadow_unsupported_entity_counts": {"HATCH": 10, "SPLINE": 2},
            },
            {
                "file_id": "F2",
                "shadow_unsupported_entity_counts": {"HATCH": 5, "POINT": 1},
            },
        ],
        project_id="P001",
    )
    assert triage["summary"]["any_adapter_authorized"] is False
    assert triage["summary"]["total_shadow_unsupported_entities"] == 18
    by_type = {row["entity_type"]: row for row in triage["rows"]}
    assert by_type["HATCH"]["entity_count"] == 15
    assert by_type["HATCH"]["file_count"] == 2
    assert by_type["SPLINE"]["entity_count"] == 2
    assert by_type["POINT"]["entity_count"] == 1
    assert all(row["adapter_authorized"] is False for row in triage["rows"])
