from copy import deepcopy

from dwg_audit.audit.pairs import build_pairs
from dwg_audit.audit.rules import build_issues
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.utils.config import DEFAULT_CONFIG


def test_build_pairs_marks_missing_side_as_review() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=0,
            start_y=0,
            end_x=10,
            end_y=0,
            length=10,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True)
    ]
    candidates = [
        TerminalCandidate(
            candidate_id="C0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            side="left",
            text_id="T1",
            text="101",
            value="101",
            score=0.95,
            status="accepted",
            rejection_reason=None,
            endpoint_x=0,
            endpoint_y=0,
            distance_x=1,
            distance_y=0,
        )
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    assert pairs[0].status == "review"
    assert pairs[0].right_value is None
    assert pairs[0].confidence_bucket == "review"
    assert pairs[0].evidence["filename"] == "a.dwg"
    assert pairs[0].left_text_id == "T1"
    assert pairs[0].left_coord_x is None
    assert pairs[0].left_candidate_id == "C0001"


def test_rules_detect_cross_page_conflict() -> None:
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "a.dwg"}),
        Pair("P2", "G2", "S2", "F2", "PC2", "101", "202", 0.96, "pass", "ok", [], "high", {"filename": "b.dwg"}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S2", "F2", 0, 0, 10, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
        SheetRecord("S2", "F2", "b.dwg", 2, "02", "B", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert any(issue.rule_id == "R-CROSS-PAGE-CONFLICT" for issue in issues)
    assert any(issue.rule_id == "R-ONE-TO-MANY" for issue in issues)
    conflict = next(issue for issue in issues if issue.rule_id == "R-CROSS-PAGE-CONFLICT")
    assert conflict.severity == "critical"
    assert conflict.evidence["filename"] == "a.dwg"
    assert conflict.evidence["sheet_no"] == "01"
    assert conflict.evidence["sheet_order"] == 1
    assert conflict.evidence["line_start"] == [0, 0]
    assert conflict.evidence["line_end"] == [10, 0]
    assert sorted(conflict.evidence["conflicting_values"]) == ["201", "202"]
    assert conflict.evidence_refs[0]["filename"] == "a.dwg"


def test_build_pairs_keeps_selected_and_alternative_traceability() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=0,
            start_y=0,
            end_x=100,
            end_y=0,
            length=100,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "left", "T1", "101", "101", 0.96, "accepted", None, 0, 0, 1, 0, 10.0, 20.0),
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "left", "T2", "102", "102", 0.93, "accepted", None, 0, 0, 1.5, 0, 12.0, 20.0),
        TerminalCandidate("C0003", "G0001", "S0001", "F0001", "right", "T3", "201", "201", 0.95, "accepted", None, 100, 0, 1, 0, 90.0, 20.0),
        TerminalCandidate("C0004", "G0001", "S0001", "F0001", "right", "T4", "202", "202", 0.89, "accepted", None, 100, 0, 1.5, 0, 88.0, 20.0),
    ]

    pair_candidates, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    selected = next(item for item in pair_candidates if item.status == "selected")
    alternatives = [item for item in pair_candidates if item.status == "alternative"]
    pair = pairs[0]

    assert selected.left_text_id == "T1"
    assert selected.right_text_id == "T3"
    assert alternatives
    assert pair.left_candidate_id == "C0001"
    assert pair.right_candidate_id == "C0003"
    assert pair.left_text_id == "T1"
    assert pair.right_text_id == "T3"
    assert pair.left_coord_x == 10.0
    assert pair.left_coord_y == 20.0
    assert pair.right_coord_x == 90.0
    assert pair.right_coord_y == 20.0


def test_rules_ignore_low_confidence_pairs_for_cross_page_conflict() -> None:
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {}),
        Pair("P2", "G2", "S2", "F2", "PC2", "101", "202", 0.76, "review", "check", [], "review", {}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S2", "F2", 0, 0, 10, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
        SheetRecord("S2", "F2", "b.dwg", 2, "02", "B", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert not any(issue.rule_id == "R-CROSS-PAGE-CONFLICT" for issue in issues)
    assert any(issue.rule_id == "R-PAIR-LOW-CONFIDENCE" for issue in issues)


def test_rules_detect_duplicate_same_line_from_close_terminal_candidates() -> None:
    pair = Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.91, "review", "ambiguous", [], "review", {})
    groups = [LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"])]
    sheets = [SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True)]
    candidates = [
        TerminalCandidate("C1", "G1", "S1", "F1", "left", "T1", "101", "101", 0.95, "accepted", None, 0, 0, 1, 0),
        TerminalCandidate("C2", "G1", "S1", "F1", "left", "T2", "102", "102", 0.90, "accepted", None, 0, 0, 1.2, 0),
        TerminalCandidate("C3", "G1", "S1", "F1", "right", "T3", "201", "201", 0.96, "accepted", None, 10, 0, 1, 0),
    ]

    issues = build_issues([pair], groups, sheets, DEFAULT_CONFIG, terminal_candidates=candidates)

    issue = next(item for item in issues if item.rule_id == "R-DUPLICATE-SAME-LINE")
    assert issue.severity == "review"
    assert issue.evidence["side"] == "left"
    assert issue.evidence["candidate_values"] == ["101", "102"]


def test_rules_detect_many_to_one_conflict() -> None:
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "a.dwg"}),
        Pair("P2", "G2", "S2", "F2", "PC2", "102", "201", 0.96, "pass", "ok", [], "high", {"filename": "b.dwg"}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S2", "F2", 10, 0, 20, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
        SheetRecord("S2", "F2", "b.dwg", 2, "02", "B", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    conflict = next(item for item in issues if item.rule_id == "R-MANY-TO-ONE")
    assert conflict.severity == "review"
    assert conflict.right_value == "201"
    assert conflict.related_pair_ids == ["P2"]
    assert conflict.evidence["conflicting_values"] == ["101", "102"]
    assert {ref["filename"] for ref in conflict.evidence_refs} == {"a.dwg", "b.dwg"}


def test_rules_cluster_duplicate_missing_reciprocal_and_keep_duplicate_pair_issue() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    config["rules"]["reciprocal_required"] = True
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "a.dwg"}),
        Pair("P2", "G2", "S2", "F2", "PC2", "101", "201", 0.96, "pass", "ok", [], "high", {"filename": "b.dwg"}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S2", "F2", 10, 0, 20, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
        SheetRecord("S2", "F2", "b.dwg", 2, "02", "B", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, config)

    missing = [item for item in issues if item.rule_id == "R-MISSING-RECIPROCAL"]
    duplicates = [item for item in issues if item.rule_id == "R-DUPLICATE-PAIR"]

    assert len(missing) == 1
    assert missing[0].primary_pair_id == "P1"
    assert missing[0].related_pair_ids == ["P2"]
    assert missing[0].evidence["cluster_size"] == 2
    assert missing[0].evidence["cluster_pair_ids"] == ["P1", "P2"]
    assert len(missing[0].evidence_refs) == 2

    assert len(duplicates) == 1
    assert duplicates[0].evidence["occurrences"] == 2
    assert duplicates[0].related_pair_ids == ["P2"]
