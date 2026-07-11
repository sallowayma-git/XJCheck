"""Unit tests for Phase 119 constraint_resolver (shadow-only, no OR-Tools)."""

from __future__ import annotations

from dwg_audit.audit.constraint_resolver import ALGORITHM_VERSION
from dwg_audit.audit.constraint_resolver import LOW_MARGIN_THRESHOLD
from dwg_audit.audit.constraint_resolver import resolve_semantic_constraints


def _attachment(
    attachment_id: str,
    *,
    token_id: str = "TK1",
    sheet_id: str = "S1",
    selected: bool = True,
    score: float = 0.9,
    margin: float | None = 0.1,
    scope_state: str = "SCOPED",
    scope_key: str | None = "scope-a",
    target_line_id: str = "L1",
    target_endpoint: str = "start",
) -> dict:
    return {
        "attachment_id": attachment_id,
        "sheet_id": sheet_id,
        "token_id": token_id,
        "score": score,
        "selected": selected,
        "margin": margin,
        "scope_state": scope_state,
        "scope_key": scope_key,
        "target_line_id": target_line_id,
        "target_endpoint": target_endpoint,
    }


def test_duplicate_selected_marks_non_best_as_violation() -> None:
    rows = [
        _attachment("SA0002", score=0.5, margin=0.2),
        _attachment("SA0001", score=0.9, margin=0.2),
    ]

    annotated, decisions, summary = resolve_semantic_constraints(rows)

    by_id = {row["attachment_id"]: row for row in annotated}
    assert by_id["SA0001"]["constraint_authority"] == "AUTHORITATIVE"
    assert by_id["SA0001"]["constraint_state"] == "PASS"
    assert by_id["SA0002"]["constraint_authority"] == "REJECTED"
    assert by_id["SA0002"]["constraint_state"] == "VIOLATION"
    assert "DUPLICATE_SELECTED" in by_id["SA0002"]["constraint_reason_codes"]

    violations = [
        d
        for d in decisions
        if d["constraint_kind"] == "ONE_SELECTED_PER_TOKEN" and d["state"] == "VIOLATION"
    ]
    assert len(violations) == 1
    assert violations[0]["attachment_id"] == "SA0002"
    assert violations[0]["severity"] == "STRONG"
    assert violations[0]["authority"] == "REJECTED"
    assert summary["strong_violation_count"] == 1
    assert summary["authoritative_selected_count"] == 1
    assert summary["inviolable_strong_constraints"] is True
    assert summary["algorithm_version"] == ALGORITHM_VERSION


def test_ambiguous_scope_demotes_to_review_only() -> None:
    rows = [_attachment("SA0001", scope_state="AMBIGUOUS", margin=0.5)]

    annotated, decisions, summary = resolve_semantic_constraints(rows)

    row = annotated[0]
    assert row["constraint_authority"] == "REVIEW_ONLY"
    assert "SCOPE_AMBIGUITY" in row["constraint_reason_codes"]
    assert any(
        d["constraint_kind"] == "SCOPE_AMBIGUITY_NOT_AUTHORITATIVE"
        and d["authority"] == "REVIEW_ONLY"
        for d in decisions
    )
    assert summary["review_only_count"] == 1
    assert summary["authoritative_selected_count"] == 0


def test_conflict_scope_also_demotes() -> None:
    rows = [_attachment("SA0001", scope_state="CONFLICT", margin=0.5)]
    annotated, _, _ = resolve_semantic_constraints(rows)
    assert annotated[0]["constraint_authority"] == "REVIEW_ONLY"


def test_low_margin_selected_demotes_to_review_only() -> None:
    rows = [
        _attachment(
            "SA0001",
            margin=LOW_MARGIN_THRESHOLD - 0.001,
            scope_state="SCOPED",
        )
    ]

    annotated, decisions, summary = resolve_semantic_constraints(rows)

    row = annotated[0]
    assert row["constraint_authority"] == "REVIEW_ONLY"
    assert "LOW_MARGIN" in row["constraint_reason_codes"]
    assert any(d["constraint_kind"] == "LOW_MARGIN_REVIEW" for d in decisions)
    assert summary["review_only_count"] == 1


def test_empty_input_is_empty_safe() -> None:
    annotated, decisions, summary = resolve_semantic_constraints([])

    assert annotated == []
    assert decisions == []
    assert summary["decision_count"] == 0
    assert summary["strong_violation_count"] == 0
    assert summary["review_only_count"] == 0
    assert summary["authoritative_selected_count"] == 0
    assert summary["by_constraint_kind"] == {}
    assert summary["inviolable_strong_constraints"] is True


def test_does_not_mutate_input() -> None:
    original = [_attachment("SA0001", scope_state="AMBIGUOUS")]
    snapshot = dict(original[0])
    resolve_semantic_constraints(original)
    assert original[0] == snapshot
    assert "constraint_authority" not in original[0]


def test_cross_scope_competition_weak_review() -> None:
    rows = [
        _attachment(
            "SA0001",
            token_id="TK1",
            scope_key="scope-a",
            target_line_id="L1",
            target_endpoint="start",
            margin=0.5,
        ),
        _attachment(
            "SA0002",
            token_id="TK2",
            scope_key="scope-b",
            target_line_id="L1",
            target_endpoint="start",
            margin=0.5,
        ),
    ]

    annotated, decisions, summary = resolve_semantic_constraints(rows)

    by_id = {row["attachment_id"]: row for row in annotated}
    assert by_id["SA0001"]["constraint_authority"] == "REVIEW_ONLY"
    assert by_id["SA0002"]["constraint_authority"] == "REVIEW_ONLY"
    weak = [
        d
        for d in decisions
        if d["constraint_kind"] == "CROSS_SCOPE_COMPETITION" and d["severity"] == "WEAK"
    ]
    assert len(weak) == 2
    assert summary["review_only_count"] == 2


def test_default_scope_state_unscoped() -> None:
    rows = [
        {
            "attachment_id": "SA0001",
            "sheet_id": "S1",
            "token_id": "TK1",
            "score": 0.9,
            "selected": True,
            "margin": 0.5,
            "target_line_id": "L1",
            "target_endpoint": "start",
        }
    ]
    annotated, _, _ = resolve_semantic_constraints(rows)
    assert annotated[0]["scope_state"] == "UNSCOPED"
    assert annotated[0]["constraint_authority"] == "AUTHORITATIVE"


def test_decision_ids_are_sequential() -> None:
    rows = [
        _attachment("SA0001", score=0.9, margin=0.5),
        _attachment("SA0002", score=0.5, margin=0.5),
    ]
    _, decisions, _ = resolve_semantic_constraints(rows)
    ids = [d["decision_id"] for d in decisions]
    assert ids
    assert ids[0] == "CR0001"
    assert all(d.startswith("CR") for d in ids)
    assert all(isinstance(d["reason_codes"], list) for d in decisions)
