"""Unit tests for Phase 120 failure_queue builders."""

from __future__ import annotations

from dwg_audit.audit.failure_queue import (
    ROUTING,
    build_failure_queue,
    summarize_failure_queue,
)


def test_failure_queue_routes_incomplete_and_constraint() -> None:
    items = build_failure_queue(
        extraction_gate={
            "analysis_status": "INCOMPLETE",
            "incomplete_page_count": 2,
            "clean_conclusion_allowed": False,
        },
        constraint_summary={
            "strong_violation_count": 1,
            "inviolable_strong_constraints": False,
        },
        scope_summary={"ambiguous_count": 4},
        audit_v2_summary={"cluster_count": 2, "witness_completeness": 0.5},
        engine_comparison={"v2_changes_legacy_result_count": 1},
        project_graph_summary={
            "edge_counts": {"cross_page_candidates": 3},
            "unresolved": {"unlabeled_open_endpoints": 5},
            "node_counts": {"authoritative_endpoints": 1},
        },
        project_id="P001",
    )
    routings = {item["suggested_routing"] for item in items}
    assert "READER" in routings
    assert "PRIMITIVE" in routings
    assert "CONSTRAINT" in routings
    assert "TEXT_ATTACHMENT" in routings
    assert "TOPOLOGY" in routings
    assert "CROSS_PAGE" in routings
    assert "ENDPOINT" in routings
    for item in items:
        assert item["suggested_routing"] in ROUTING
        assert item["failure_id"].startswith("FQ-")
        assert item["state"] == "OPEN"
    summary = summarize_failure_queue(items)
    assert summary["item_count"] == len(items)
    assert summary["critical_count"] >= 1
    assert summary["failure_count"] == len(items)


def test_extraction_reader_vs_primitive() -> None:
    # With conversion codes → READER preferred path present
    items = build_failure_queue(
        extraction_gate={
            "analysis_status": "INCOMPLETE_EXTRACTION",
            "incomplete_page_count": 1,
            "clean_conclusion_allowed": False,
            "failure_code_counts": {"DXF_CONVERSION_FAILED": 2},
        },
        project_id="P",
    )
    routings = {i["suggested_routing"] for i in items}
    assert "READER" in routings
    assert "PRIMITIVE" in routings
    assert all(i["severity"] == "critical" for i in items)


def test_constraint_strong_violation() -> None:
    items = build_failure_queue(
        constraint_summary={"strong_violation_count": 2},
        project_id="P",
    )
    assert len(items) == 1
    assert items[0]["suggested_routing"] == "CONSTRAINT"
    assert items[0]["severity"] == "critical"


def test_witness_completeness_topology() -> None:
    items = build_failure_queue(
        audit_v2_summary={"witness_completeness": 0.0},
        project_id="P",
    )
    assert len(items) == 1
    assert items[0]["suggested_routing"] == "TOPOLOGY"
    assert items[0]["severity"] == "major"


def test_cross_page_review() -> None:
    items = build_failure_queue(
        cross_page_candidate_count=2,
        project_id="P",
    )
    assert len(items) == 1
    assert items[0]["suggested_routing"] == "CROSS_PAGE"
    assert items[0]["severity"] == "review"
    assert "never auto-accept" in items[0]["message"]


def test_page_capability_risk() -> None:
    items = build_failure_queue(
        page_capability_matrix=[
            {"page_id": "P1", "page_type_confidence": 0.3, "route": "wire"},
            {"page_id": "P2", "page_type_confidence": 0.9, "route": "table"},
        ],
        project_id="P",
    )
    assert len(items) == 1
    assert items[0]["suggested_routing"] == "PAGE_CAPABILITY"
    assert items[0]["severity"] == "review"


def test_failure_queue_empty_when_healthy() -> None:
    items = build_failure_queue(
        extraction_gate={
            "analysis_status": "COMPLETE",
            "incomplete_page_count": 0,
            "clean_conclusion_allowed": True,
        },
        constraint_summary={
            "strong_violation_count": 0,
            "inviolable_strong_constraints": True,
            "review_only_count": 10,
        },
        scope_summary={"ambiguous_count": 0},
        audit_v2_summary={"cluster_count": 0, "witness_completeness": 1.0},
        engine_comparison={"v2_changes_legacy_result_count": 0},
        project_graph_summary={
            "edge_counts": {"cross_page_candidates": 0},
            "unresolved": {"unlabeled_open_endpoints": 0},
            "node_counts": {"authoritative_endpoints": 0},
        },
        project_id="P001",
    )
    assert items == []
    summary = summarize_failure_queue(items)
    assert summary["item_count"] == 0
    assert summary["failure_count"] == 0
    assert summary["critical_count"] == 0
    assert summary["open_count"] == 0


def test_suggested_routing_in_allowed_set() -> None:
    items = build_failure_queue(
        extraction_gate={
            "analysis_status": "INCOMPLETE_EXTRACTION",
            "incomplete_page_count": 1,
            "clean_conclusion_allowed": False,
            "failure_code_counts": {"conversion_error": 1},
        },
        constraint_summary={"strong_violation_count": 1},
        audit_v2_summary={"witness_completeness": 0.5},
        cross_page_candidate_count=1,
        page_capability_matrix={"p1": {"page_type_confidence": 0.1}},
        project_id="P",
    )
    assert items  # non-empty
    for item in items:
        assert item["suggested_routing"] in ROUTING
