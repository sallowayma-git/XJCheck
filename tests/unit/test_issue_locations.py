from dwg_audit.domain.issue_locations import attach_locations
from dwg_audit.domain.issue_locations import build_locations
from dwg_audit.domain.issue_locations import derive_locations_from_refs
from dwg_audit.domain.models import Issue


def _issue(rule_id: str, **overrides) -> Issue:
    base = dict(
        issue_id="I1", rule_id=rule_id, severity="review", status="open", confidence=0.8, message="m",
        sheet_id="S1", file_id="F1", pair_id="P1", line_group_id="G1", left_value="101", right_value="201",
        evidence={}, evidence_refs=[],
    )
    base.update(overrides)
    return Issue(**base)


def test_diagnostic_rules_never_get_locations() -> None:
    issue = _issue("R-SHEET-PAGE-MISMATCH", evidence_refs=[{"pair_id": "P1", "sheet_id": "S1", "point": [1, 2]}])

    assert build_locations(issue) == []
    attach_locations(issue)
    assert "locations" not in issue.evidence


def test_single_pair_without_coordinates_is_listed_but_not_renderable() -> None:
    issue = _issue(
        "R-PAIR-MISSING-SIDE",
        evidence_refs=[{"pair_id": "P1", "sheet_id": "S1", "filename": "01.dwg", "sheet_no": "01",
                        "left_value": "101", "right_value": None, "point": None, "peer_point": None,
                        "line_group_id": None}],
    )

    locations = build_locations(issue)

    assert len(locations) == 1
    assert locations[0]["renderable"] is False
    assert locations[0]["bbox"] is None and locations[0]["point"] is None and locations[0]["wire"] is None
    assert locations[0]["terminal"] == "101" and locations[0]["sheet_no"] == "01"


def test_legacy_issue_without_refs_uses_top_level_fields() -> None:
    issue = _issue(
        "R-PAIR-LOW-CONFIDENCE",
        evidence={"line_start": [10, 20], "line_end": [90, 20], "left_point": [11, 21], "right_point": [89, 21]},
        evidence_refs=[],
    )

    locations = build_locations(issue)

    assert len(locations) == 1
    assert locations[0]["point"] == [11.0, 21.0]
    assert locations[0]["wire"]["start"] == [10.0, 20.0]
    assert locations[0]["renderable"] is True
    assert locations[0]["bbox"][0] <= 10.0 and locations[0]["bbox"][2] >= 89.0


def test_attach_ignores_stale_stored_locations_and_is_idempotent() -> None:
    issue = _issue(
        "R-CROSS-PAGE-CONFLICT",
        evidence={"locations": [{"location_id": "stale", "sheet_id": "SX", "terminal": "999", "renderable": True}]},
        evidence_refs=[{"pair_id": "P1", "sheet_id": "S1", "left_value": "101", "right_value": "201",
                        "point": [1, 2], "line_group_id": "G1", "line_start": [0, 0], "line_end": [10, 0]}],
    )

    attach_locations(issue)
    first = issue.evidence["locations"]
    attach_locations(issue)

    assert first == issue.evidence["locations"]
    assert [loc["sheet_id"] for loc in first] == ["S1"]
    assert first[0]["terminal"] == "101"


def test_stored_locations_are_normalized_with_a_bbox() -> None:
    payload = {
        "issue_id": "I9",
        "rule_id": "R-MANY-TO-ONE",
        "evidence": {"locations": [{"role": "conflict_party", "sheet_id": "S2", "point": [5, 5]}]},
        "evidence_refs": [],
    }

    locations = derive_locations_from_refs(payload)

    assert locations[0]["location_id"] == "I9#1"
    assert locations[0]["sheet_id"] == "S2" and locations[0]["renderable"] is True
    assert locations[0]["bbox"] is not None
