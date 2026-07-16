from __future__ import annotations

from dwg_audit.audit.scope_resolver import ALGORITHM_VERSION
from dwg_audit.audit.scope_resolver import resolve_attachment_scopes


def _token(
    token_id: str,
    token_kind: str,
    text: str,
    x: float,
    y: float,
    *,
    sheet_id: str = "S1",
    prefix: str | None = None,
    bbox: list[float] | None = None,
) -> dict:
    row: dict = {
        "token_id": token_id,
        "sheet_id": sheet_id,
        "token_kind": token_kind,
        "normalized_text": text,
        "raw_text": text,
        "prefix": prefix,
        "family": None,
        "ordinal": None,
        "local_number": None,
        "insert_x": x,
        "insert_y": y,
    }
    if bbox is not None:
        row["bbox"] = bbox
    return row


def _attachment(
    token_id: str,
    *,
    sheet_id: str = "S1",
    token_kind: str = "EXTERNAL_ENDPOINT",
    attachment_id: str = "SA0001",
) -> dict:
    return {
        "attachment_id": attachment_id,
        "sheet_id": sheet_id,
        "token_id": token_id,
        "token_kind": token_kind,
        "selected": True,
        "rank": 1,
        "margin": 0.1,
        "state": "SELECTED",
    }


def test_scoped_prefix_exact_prefix_match_resolves_external_endpoint() -> None:
    tokens = [
        _token("TK-P1", "SCOPED_PREFIX", "1n", 0.0, 0.0, prefix="1"),
        _token("TK-E1", "EXTERNAL_ENDPOINT", "1QD1", 10.0, 0.0, prefix="1"),
    ]
    attachments = [_attachment("TK-E1", token_kind="EXTERNAL_ENDPOINT")]

    scoped, decisions, summary = resolve_attachment_scopes(tokens, attachments)

    assert len(scoped) == 1
    row = scoped[0]
    assert row["scope_kind"] == "SCOPED_PREFIX"
    assert row["scope_key"] == "1"
    assert row["scope_state"] == "RESOLVED"
    assert row["scope_token_id"] == "TK-P1"
    assert "PREFIX_EQUALITY" in row["scope_reason_codes"]
    assert row["scope_confidence"] == 0.95
    assert summary["algorithm_version"] == ALGORITHM_VERSION
    assert summary["algorithm_version"] == "scope-resolver-v1"
    assert summary["scoped_attachment_count"] == 1
    assert all(d["algorithm_version"] == "scope-resolver-v1" for d in decisions)
    assert any(d["state"] == "RESOLVED" and d["scope_kind"] == "SCOPED_PREFIX" for d in decisions)


def test_geometric_terminal_local_near_prefix_resolves_far_unscoped() -> None:
    tokens = [
        _token("TK-P5", "SCOPED_PREFIX", "5n", 100.0, 50.0, prefix="5"),
        _token("TK-T-near", "TERMINAL_LOCAL", "12", 110.0, 50.0),
        _token("TK-T-far", "TERMINAL_LOCAL", "99", 300.0, 50.0),
    ]
    attachments = [
        _attachment("TK-T-near", token_kind="TERMINAL_LOCAL", attachment_id="SA0001"),
        _attachment("TK-T-far", token_kind="TERMINAL_LOCAL", attachment_id="SA0002"),
    ]

    scoped, _decisions, summary = resolve_attachment_scopes(tokens, attachments)

    by_token = {row["token_id"]: row for row in scoped}
    near = by_token["TK-T-near"]
    far = by_token["TK-T-far"]

    assert near["scope_kind"] == "SCOPED_PREFIX"
    assert near["scope_key"] == "5"
    assert near["scope_state"] == "RESOLVED"
    assert near["scope_token_id"] == "TK-P5"
    assert "GEOMETRIC_NEIGHBORHOOD" in near["scope_reason_codes"]
    assert near["scope_confidence"] == 0.9

    assert far["scope_kind"] is None
    assert far["scope_state"] == "UNSCOPED"
    assert far["scope_confidence"] == 0.0
    assert "NO_OWNER" in far["scope_reason_codes"]

    assert summary["scoped_attachment_count"] == 1
    assert summary["unscoped_attachment_count"] == 1


def test_body_port_resolves() -> None:
    tokens = [
        _token("TK-B1", "COMPONENT_BODY", "1KLP1", 0.0, 0.0),
        _token("TK-P1", "COMPONENT_PORT", "1", 5.0, 0.0),
    ]
    attachments = [_attachment("TK-P1", token_kind="COMPONENT_PORT")]

    scoped, decisions, summary = resolve_attachment_scopes(tokens, attachments)

    assert len(scoped) == 1
    row = scoped[0]
    assert row["scope_kind"] == "BODY_PORT"
    assert row["scope_key"] == "1KLP1"
    assert row["scope_state"] == "RESOLVED"
    assert row["scope_token_id"] == "TK-B1"
    assert "NEAREST_BODY" in row["scope_reason_codes"]
    assert row["scope_confidence"] == 0.9
    assert summary["scoped_attachment_count"] == 1
    assert any(d["scope_kind"] == "BODY_PORT" and d["state"] == "RESOLVED" for d in decisions)


def test_body_port_equidistant_ambiguous() -> None:
    tokens = [
        _token("TK-B1", "COMPONENT_BODY", "1KLP1", -10.0, 0.0),
        _token("TK-B2", "COMPONENT_BODY", "1KLP2", 10.0, 0.0),
        _token("TK-P1", "COMPONENT_PORT", "1", 0.0, 0.0),
    ]
    attachments = [_attachment("TK-P1", token_kind="COMPONENT_PORT")]

    scoped, decisions, summary = resolve_attachment_scopes(tokens, attachments)

    assert len(scoped) == 1
    row = scoped[0]
    assert row["scope_kind"] == "BODY_PORT"
    assert row["scope_state"] == "AMBIGUOUS"
    assert row["scope_confidence"] == 0.7
    assert "MULTIPLE_OWNERS" in row["scope_reason_codes"]
    assert summary["ambiguous_count"] == 1
    assert any(d["state"] == "AMBIGUOUS" and d["scope_kind"] == "BODY_PORT" for d in decisions)


def test_semantic_row_marker_nearby_terminal_resolves() -> None:
    tokens = [
        _token("TK-M1", "ANNOTATION", "1KLP", 0.0, 10.0),
        _token("TK-T1", "TERMINAL_LOCAL", "5", 10.0, 10.0),
    ]
    attachments = [_attachment("TK-T1", token_kind="TERMINAL_LOCAL")]

    scoped, decisions, summary = resolve_attachment_scopes(tokens, attachments)

    assert len(scoped) == 1
    row = scoped[0]
    assert row["scope_kind"] == "SEMANTIC_ROW"
    assert row["scope_key"] == "1KLP"
    assert row["scope_state"] == "RESOLVED"
    assert row["scope_token_id"] == "TK-M1"
    assert "SEMANTIC_ROW_MARKER" in row["scope_reason_codes"]
    assert row["scope_confidence"] == 0.9
    assert summary["scoped_attachment_count"] == 1
    assert any(d["scope_kind"] == "SEMANTIC_ROW" and d["state"] == "RESOLVED" for d in decisions)


def test_attachments_are_shallow_copies_input_not_mutated() -> None:
    tokens = [
        _token("TK-P1", "SCOPED_PREFIX", "1n", 0.0, 0.0, prefix="1"),
        _token("TK-E1", "EXTERNAL_ENDPOINT", "1QD1", 10.0, 0.0, prefix="1"),
    ]
    original = _attachment("TK-E1", token_kind="EXTERNAL_ENDPOINT")
    attachments = [original]

    scoped, _decisions, _summary = resolve_attachment_scopes(tokens, attachments)

    assert "scope_kind" not in original
    assert "scope_state" not in original
    assert len(scoped) == 1
    assert scoped[0] is not original
    assert id(scoped[0]) != id(original)
    assert "scope_kind" in scoped[0]
    assert scoped[0]["scope_state"] == "RESOLVED"
    # selected/rank remain geometry-only
    assert scoped[0]["selected"] is True
    assert scoped[0]["rank"] == 1


def test_empty_tokens_attachments_zero_summary() -> None:
    scoped, decisions, summary = resolve_attachment_scopes([], [])

    assert scoped == []
    assert decisions == []
    assert summary["algorithm_version"] == "scope-resolver-v1"
    assert summary["attachment_count"] == 0
    assert summary["scoped_attachment_count"] == 0
    assert summary["unscoped_attachment_count"] == 0
    assert summary["ambiguous_count"] == 0
    assert summary["conflict_count"] == 0
    assert summary["decision_count"] == 0
    assert summary["by_scope_kind"] == {}
    assert summary["by_state"] == {}
