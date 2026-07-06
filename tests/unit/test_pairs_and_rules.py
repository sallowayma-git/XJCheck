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
    assert pairs[0].pair_key == "101->?"
    assert pairs[0].left_score == 0.95
    assert pairs[0].right_score == 0.0
    assert pairs[0].wire_score == 0.9


def test_build_pairs_discards_line_group_without_numeric_candidates() -> None:
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

    _, pairs = build_pairs(groups, [], sheets, DEFAULT_CONFIG)

    assert pairs[0].status == "discard"
    assert pairs[0].confidence_bucket == "low"
    assert pairs[0].left_value is None
    assert pairs[0].right_value is None


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
    assert not any(issue.rule_id == "R-ONE-TO-MANY" for issue in issues)
    conflict = next(issue for issue in issues if issue.rule_id == "R-CROSS-PAGE-CONFLICT")
    assert conflict.severity == "critical"
    assert conflict.evidence["filename"] == "a.dwg"
    assert conflict.evidence["sheet_no"] == "01"
    assert conflict.evidence["sheet_order"] == 1
    assert conflict.evidence["line_start"] == [0, 0]
    assert conflict.evidence["line_end"] == [10, 0]
    assert sorted(conflict.evidence["conflicting_values"]) == ["201", "202"]
    assert conflict.evidence["one_to_many_classification"] == "conflict"
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
    assert pair.confidence > 0.92
    assert pair.pair_key == "101->201"
    assert pair.left_score == 0.96
    assert pair.right_score == 0.95
    assert pair.wire_score == 0.9
    assert pair.ambiguity_gap is not None
    assert pair.evidence["pair_key"] == "101->201"
    assert pair.evidence["score_breakdown"] == {
        "left_score": 0.96,
        "right_score": 0.95,
        "wire_score": 0.9,
        "ambiguity_gap": pair.ambiguity_gap,
    }


def test_build_pairs_marks_strong_unambiguous_pair_as_pass() -> None:
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
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "left", "T2", "102", "102", 0.75, "accepted", None, 0, 0, 1.5, 0, 12.0, 20.0),
        TerminalCandidate("C0003", "G0001", "S0001", "F0001", "right", "T3", "201", "201", 0.95, "accepted", None, 100, 0, 1, 0, 90.0, 20.0),
        TerminalCandidate("C0004", "G0001", "S0001", "F0001", "right", "T4", "202", "202", 0.70, "accepted", None, 100, 0, 1.5, 0, 88.0, 20.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    assert pairs[0].status == "pass"
    assert pairs[0].confidence_bucket == "high"
    assert pairs[0].confidence > DEFAULT_CONFIG["confidence"]["high_threshold"]


def test_build_pairs_discards_full_pair_below_review_threshold() -> None:
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
            wire_candidate_score=0.35,
            member_line_ids=["L1"],
            layer_hints=["DIM"],
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "left", "T1", "101", "101", 0.55, "accepted", None, 0, 0, 1, 0, 10.0, 20.0),
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "right", "T2", "201", "201", 0.58, "accepted", None, 100, 0, 1, 0, 90.0, 20.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    assert pairs[0].status == "discard"
    assert pairs[0].confidence_bucket == "low"
    assert pairs[0].confidence < DEFAULT_CONFIG["confidence"]["review_threshold"]


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


def test_build_pairs_tags_same_value_terminal_continuation_semantics() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=310.0,
            start_y=235.0,
            end_x=385.0,
            end_y=235.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "27 右侧端子图2.dwg", 27, "27", "右侧端子图2", "屏端子图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "left", "T1", "3-2n420", "420", 0.84, "accepted", None, 310.0, 235.0, 23.0, 1.0, 333.0, 236.0),
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "right", "T2", "1-2n420", "420", 0.83, "accepted", None, 385.0, 235.0, 24.0, 1.0, 361.0, 236.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.left_value == "420"
    assert pair.right_value == "420"
    assert pair.pair_kind == "continuation"
    assert pair.status == "review"
    assert pair.evidence["semantic_kind"] == "continuation_same_value"
    assert pair.evidence["pair_kind"] == "continuation"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["selected_left_channel"] == "continuation_channel"
    assert pair.evidence["selected_right_channel"] == "continuation_channel"
    assert candidates[0].channel == "continuation_channel"
    assert candidates[1].channel == "continuation_channel"
    assert pair.evidence["selected_left_raw_text"] == "3-2n420"
    assert pair.evidence["selected_right_raw_text"] == "1-2n420"
    assert pair.evidence["selected_left_is_derived_numeric"] is True
    assert pair.evidence["selected_right_is_derived_numeric"] is True


def test_build_pairs_keeps_plain_same_value_terminal_pair_as_ordinary() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=310.0,
            start_y=235.0,
            end_x=385.0,
            end_y=235.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "27 右侧端子图2.dwg", 27, "27", "右侧端子图2", "屏端子图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "left", "T1", "420", "420", 0.84, "accepted", None, 310.0, 235.0, 23.0, 1.0, 333.0, 236.0),
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "right", "T2", "420", "420", 0.83, "accepted", None, 385.0, 235.0, 24.0, 1.0, 361.0, 236.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.pair_kind == "ordinary_pair"
    assert "semantic_kind" not in pair.evidence
    assert pair.evidence.get("ordinary_pair_eligible", True) is True
    assert pair.evidence["selected_left_is_derived_numeric"] is False
    assert pair.evidence["selected_right_is_derived_numeric"] is False


def test_build_pairs_tags_single_sided_terminal_continuation_from_derived_numeric() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=310.0,
            start_y=235.0,
            end_x=385.0,
            end_y=235.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "right", "T1", "3-21n328", "328", 0.86, "accepted", None, 341.0, 236.0, 7.0, 1.0, 341.0, 236.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.left_value is None
    assert pair.right_value == "328"
    assert pair.pair_kind == "continuation"
    assert pair.status == "review"
    assert pair.rationale == "missing left candidate; continuation relation"
    assert pair.evidence["semantic_kind"] == "continuation_single_sided"
    assert pair.evidence["pair_kind"] == "continuation"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["continuation_kind"] == "terminal_missing_left_continuation"
    assert pair.evidence["continuation_missing_side"] == "left"
    assert pair.evidence["selected_right_channel"] == "continuation_channel"
    assert candidates[0].channel == "continuation_channel"
    assert pair.evidence["selected_right_raw_text"] == "3-21n328"


def test_build_pairs_tags_single_sided_terminal_continuation_from_short_bridge_band() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=310.0,
            start_y=220.0,
            end_x=385.0,
            end_y=220.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "24 右侧端子图2.dwg", 24, "24", "右侧端子图2", "屏端子图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "right", "T1", "10", "10", 0.83, "accepted", None, 359.25, 221.0, 5.0, 1.0, 359.25, 221.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.left_value is None
    assert pair.right_value == "10"
    assert pair.pair_kind == "continuation"
    assert pair.status == "review"
    assert pair.rationale == "missing left candidate; continuation relation"
    assert pair.evidence["semantic_kind"] == "continuation_single_sided"
    assert pair.evidence["continuation_kind"] == "terminal_missing_left_continuation"
    assert pair.evidence["selected_right_channel"] == "continuation_channel"
    assert candidates[0].channel == "continuation_channel"


def test_build_pairs_tags_terminal_short_bridge_cross_column_as_bridge_mapping() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=310.0,
            start_y=226.0,
            end_x=385.0,
            end_y=226.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "left", "T1", "1-21n110", "110", 1.0, "accepted", None, 311.0, 226.0, 7.0, 1.0, 311.0, 226.0),
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "right", "T2", "3-21n330", "330", 0.8657, "accepted", None, 341.0, 226.0, 7.0, 1.0, 341.0, 226.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.left_value == "110"
    assert pair.right_value == "330"
    assert pair.pair_kind == "bridge_mapping"
    assert pair.status == "review"
    assert pair.rationale.startswith("left=110 right=330 score=")
    assert pair.rationale.endswith("; bridge mapping relation")
    assert pair.evidence["pair_kind"] == "bridge_mapping"
    assert pair.evidence["semantic_kind"] == "terminal_bridge_mapping"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["bridge_mapping_kind"] == "terminal_short_bridge_cross_column"
    assert pair.evidence["selected_left_channel"] == "continuation_channel"
    assert pair.evidence["selected_right_channel"] == "continuation_channel"
    assert candidates[0].channel == "continuation_channel"
    assert candidates[1].channel == "continuation_channel"


def test_build_pairs_tags_terminal_semantic_row_as_semantic_mapping() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=127.5,
            start_y=255.0,
            end_x=202.5,
            end_y=255.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "left", "T0", "3", None, 0.82, "rejected", "terminal_semantic_local_numeric", 151.75, 256.0, 4.5, 1.0, 151.75, 256.0, channel="semantic_channel", channel_detail="terminal_semantic_local_numeric"),
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "left", "T1", "3-21KLP2-1", None, 0.0, "rejected", "not_numeric", 128.5, 256.0, 8.0, 1.0, 128.5, 256.0, channel="semantic_channel", channel_detail="not_numeric"),
        TerminalCandidate("C0003", "G0001", "S0001", "F0001", "right", "T2", "1-21n108", "108", 0.8657, "accepted", None, 158.5, 256.0, 7.0, 1.0, 158.5, 256.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.left_value is None
    assert pair.right_value == "108"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.status == "review"
    assert pair.rationale == "missing left candidate; semantic mapping relation"
    assert pair.evidence["pair_kind"] == "semantic_mapping"
    assert pair.evidence["semantic_kind"] == "terminal_semantic_mapping"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["semantic_mapping_kind"] == "terminal_semantic_row"
    assert pair.evidence["semantic_marker_texts"] == ["3-21KLP2-1"]
    assert pair.evidence["selected_right_channel"] == "terminal_numeric_channel"
    assert candidates[2].channel == "terminal_numeric_channel"


def test_build_pairs_only_consumes_terminal_numeric_channel_candidates() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=0.0,
            start_y=0.0,
            end_x=75.0,
            end_y=0.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate(
            "C0001",
            "G0001",
            "S0001",
            "F0001",
            "left",
            "T1",
            "KLP2",
            "2",
            0.99,
            "accepted",
            None,
            0.0,
            0.0,
            1.0,
            1.0,
            20.0,
            0.0,
            channel="semantic_channel",
        ),
        TerminalCandidate(
            "C0002",
            "G0001",
            "S0001",
            "F0001",
            "left",
            "T2",
            "108",
            "108",
            0.81,
            "accepted",
            None,
            0.0,
            0.0,
            2.0,
            1.0,
            22.0,
            0.0,
            channel="terminal_numeric_channel",
        ),
        TerminalCandidate(
            "C0003",
            "G0001",
            "S0001",
            "F0001",
            "right",
            "T3",
            "208",
            "208",
            0.82,
            "accepted",
            None,
            75.0,
            0.0,
            2.0,
            1.0,
            53.0,
            0.0,
            channel="terminal_numeric_channel",
        ),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.left_value == "108"
    assert pair.right_value == "208"
    assert pair.evidence["selected_left_channel"] == "terminal_numeric_channel"


def test_rules_skip_terminal_continuation_same_value_pairs_from_ordinary_audit() -> None:
    pairs = [
        Pair(
            pair_id="P1",
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id="PC1",
            left_value="420",
            right_value="420",
            confidence=0.81,
            status="review",
            rationale="ambiguous candidate ordering",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "27.dwg",
                "pair_kind": "continuation",
                "semantic_kind": "continuation_same_value",
                "ordinary_pair_eligible": False,
            },
            pair_kind="continuation",
        ),
        Pair(
            "P2",
            "G2",
            "S2",
            "F2",
            "PC2",
            "420",
            "421",
            0.97,
            "pass",
            "ok",
            [],
            "high",
            {"filename": "28.dwg"},
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 310, 235, 385, 235, 75, 0.9, ["L1"], ["WIRE"], orientation="horizontal"),
        LineGroup("G2", "S2", "F2", 0, 0, 10, 0, 10, 0.9, ["L2"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "27 右侧端子图2.dwg", 27, "27", "右侧端子图2", "屏端子图", "supplemental", "filename", True),
        SheetRecord("S2", "F2", "28 回路图.dwg", 28, "28", "回路图", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert not any(issue.rule_id == "R-PAIR-LOW-CONFIDENCE" and issue.pair_id == "P1" for issue in issues)
    assert not any(issue.rule_id == "R-CROSS-PAGE-CONFLICT" for issue in issues)


def test_rules_skip_single_sided_terminal_continuation_pairs_from_missing_side_audit() -> None:
    pairs = [
        Pair(
            pair_id="P1",
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id="PC1",
            left_value=None,
            right_value="328",
            confidence=0.86,
            status="review",
            rationale="missing left candidate; continuation relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "21.dwg",
                "pair_kind": "continuation",
                "semantic_kind": "continuation_single_sided",
                "ordinary_pair_eligible": False,
                "continuation_kind": "terminal_missing_left_continuation",
            },
            pair_kind="continuation",
        ),
        Pair(
            "P2",
            "G2",
            "S2",
            "F2",
            "PC2",
            "420",
            "421",
            0.97,
            "pass",
            "ok",
            [],
            "high",
            {"filename": "28.dwg"},
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 310, 235, 385, 235, 75, 0.9, ["L1"], ["WIRE"], orientation="horizontal"),
        LineGroup("G2", "S2", "F2", 0, 0, 10, 0, 10, 0.9, ["L2"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True),
        SheetRecord("S2", "F2", "28 回路图.dwg", 28, "28", "回路图", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert not any(issue.rule_id == "R-PAIR-MISSING-SIDE" and issue.pair_id == "P1" for issue in issues)
    assert not any(issue.rule_id == "R-PAIR-LOW-CONFIDENCE" and issue.pair_id == "P1" for issue in issues)


def test_rules_skip_bridge_mapping_pairs_from_ordinary_audit() -> None:
    pairs = [
        Pair(
            pair_id="P1",
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id="PC1",
            left_value="110",
            right_value="330",
            confidence=0.89,
            status="review",
            rationale="bridge mapping relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "21.dwg",
                "pair_kind": "bridge_mapping",
                "semantic_kind": "terminal_bridge_mapping",
                "ordinary_pair_eligible": False,
                "bridge_mapping_kind": "terminal_short_bridge_cross_column",
            },
            pair_kind="bridge_mapping",
        ),
        Pair(
            "P2",
            "G2",
            "S2",
            "F2",
            "PC2",
            "420",
            "421",
            0.97,
            "pass",
            "ok",
            [],
            "high",
            {"filename": "28.dwg"},
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 310, 226, 385, 226, 75, 0.9, ["L1"], ["WIRE"], orientation="horizontal"),
        LineGroup("G2", "S2", "F2", 0, 0, 10, 0, 10, 0.9, ["L2"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True),
        SheetRecord("S2", "F2", "28 回路图.dwg", 28, "28", "回路图", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert not any(issue.pair_id == "P1" for issue in issues)


def test_rules_skip_semantic_mapping_pairs_from_ordinary_audit() -> None:
    pairs = [
        Pair(
            pair_id="P1",
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id="PC1",
            left_value=None,
            right_value="108",
            confidence=0.86,
            status="review",
            rationale="semantic mapping relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "21.dwg",
                "pair_kind": "semantic_mapping",
                "semantic_kind": "terminal_semantic_mapping",
                "ordinary_pair_eligible": False,
                "semantic_mapping_kind": "terminal_semantic_row",
                "semantic_marker_texts": ["3-21KLP2-1"],
            },
            pair_kind="semantic_mapping",
        ),
        Pair(
            "P2",
            "G2",
            "S2",
            "F2",
            "PC2",
            "420",
            "421",
            0.97,
            "pass",
            "ok",
            [],
            "high",
            {"filename": "28.dwg"},
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 127.5, 255.0, 202.5, 255.0, 75, 0.9, ["L1"], ["WIRE"], orientation="horizontal"),
        LineGroup("G2", "S2", "F2", 0, 0, 10, 0, 10, 0.9, ["L2"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True),
        SheetRecord("S2", "F2", "28 回路图.dwg", 28, "28", "回路图", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert not any(issue.pair_id == "P1" for issue in issues)


def test_rules_emit_semantic_mapping_conflict_for_cross_sheet_stable_singleton_endpoints() -> None:
    pairs = [
        Pair(
            pair_id="P1",
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id="PC1",
            left_value=None,
            right_value="114",
            confidence=0.86,
            status="review",
            rationale="semantic mapping relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "21 左侧端子图1.dwg",
                "sheet_no": "21",
                "sheet_order": 21,
                "pair_kind": "semantic_mapping",
                "semantic_kind": "terminal_semantic_mapping",
                "semantic_mapping_kind": "terminal_semantic_row",
                "semantic_marker_texts": ["3-21KLP2-1"],
            },
            pair_kind="semantic_mapping",
        ),
        Pair(
            pair_id="P2",
            line_group_id="G2",
            sheet_id="S2",
            file_id="F2",
            selected_pair_candidate_id="PC2",
            left_value=None,
            right_value="114",
            confidence=0.87,
            status="review",
            rationale="semantic mapping relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "23 右侧端子图1.dwg",
                "sheet_no": "23",
                "sheet_order": 23,
                "pair_kind": "semantic_mapping",
                "semantic_kind": "terminal_semantic_mapping",
                "semantic_mapping_kind": "terminal_semantic_row",
                "semantic_marker_texts": ["1-21ZK-3"],
            },
            pair_kind="semantic_mapping",
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["WIRE"]),
        LineGroup("G2", "S2", "F2", 0, 0, 10, 0, 10, 0.9, ["L2"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True),
        SheetRecord("S2", "F2", "23 右侧端子图1.dwg", 23, "23", "右侧端子图1", "屏端子图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    issue = next(item for item in issues if item.rule_id == "R-SEMANTIC-MAPPING-CONFLICT")
    assert issue.severity == "review"
    assert issue.right_value == "114"
    assert issue.evidence["terminal_value"] == "114"
    assert issue.evidence["semantic_targets"] == {
        "S1": "KLP2-1",
        "S2": "ZK-3",
    }
    assert issue.evidence["conflicting_values"] == ["KLP2-1", "ZK-3"]
    assert issue.evidence["semantic_conflict_kind"] == "cross_sheet_semantic_endpoint_mismatch"
    assert issue.related_pair_ids == ["P2"]
    assert {ref["pair_id"] for ref in issue.evidence_refs} == {"P1", "P2"}


def test_rules_ignore_semantic_mapping_conflict_when_sheet_local_target_is_not_stable() -> None:
    pairs = [
        Pair(
            pair_id="P1",
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id="PC1",
            left_value=None,
            right_value="509",
            confidence=0.86,
            status="review",
            rationale="semantic mapping relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "22 左侧端子图2.dwg",
                "sheet_no": "22",
                "sheet_order": 22,
                "pair_kind": "semantic_mapping",
                "semantic_kind": "terminal_semantic_mapping",
                "semantic_mapping_kind": "terminal_semantic_row",
                "semantic_marker_texts": ["1-21ZK-3"],
            },
            pair_kind="semantic_mapping",
        ),
        Pair(
            pair_id="P2",
            line_group_id="G2",
            sheet_id="S1",
            file_id="F1",
            selected_pair_candidate_id="PC2",
            left_value=None,
            right_value="509",
            confidence=0.84,
            status="review",
            rationale="semantic mapping relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "22 左侧端子图2.dwg",
                "sheet_no": "22",
                "sheet_order": 22,
                "pair_kind": "semantic_mapping",
                "semantic_kind": "terminal_semantic_mapping",
                "semantic_mapping_kind": "terminal_semantic_row",
                "semantic_marker_texts": ["1-21KK-G-"],
            },
            pair_kind="semantic_mapping",
        ),
        Pair(
            pair_id="P3",
            line_group_id="G3",
            sheet_id="S2",
            file_id="F2",
            selected_pair_candidate_id="PC3",
            left_value=None,
            right_value="509",
            confidence=0.87,
            status="review",
            rationale="semantic mapping relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "24 右侧端子图2.dwg",
                "sheet_no": "24",
                "sheet_order": 24,
                "pair_kind": "semantic_mapping",
                "semantic_kind": "terminal_semantic_mapping",
                "semantic_mapping_kind": "terminal_semantic_row",
                "semantic_marker_texts": ["3-21ZK-5"],
            },
            pair_kind="semantic_mapping",
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["WIRE"]),
        LineGroup("G2", "S1", "F1", 20, 0, 30, 0, 10, 0.9, ["L2"], ["WIRE"]),
        LineGroup("G3", "S2", "F2", 40, 0, 50, 0, 10, 0.9, ["L3"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "22 左侧端子图2.dwg", 22, "22", "左侧端子图2", "屏端子图", "supplemental", "filename", True),
        SheetRecord("S2", "F2", "24 右侧端子图2.dwg", 24, "24", "右侧端子图2", "屏端子图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert not any(item.rule_id == "R-SEMANTIC-MAPPING-CONFLICT" for item in issues)

def test_rules_emit_one_to_many_review_for_same_sheet_multi_target() -> None:
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "a.dwg"}),
        Pair("P2", "G2", "S1", "F1", "PC2", "101", "202", 0.96, "pass", "ok", [], "high", {"filename": "a.dwg"}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S1", "F1", 20, 0, 30, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    review = next(item for item in issues if item.rule_id == "R-ONE-TO-MANY")
    assert review.severity == "review"
    assert review.title == "一对多待复核"
    assert review.related_pair_ids == ["P2"]
    assert review.evidence["conflicting_values"] == ["201", "202"]
    assert review.evidence["one_to_many_classification"] == "review"
    assert "component_branch_review" not in review.evidence.values()


def test_rules_emit_one_to_many_component_branch_review_for_strip_two_port_component() -> None:
    pairs = [
        Pair(
            "P1",
            "G1",
            "S1",
            "F1",
            "PC1",
            "5KLP10-1",
            "5KLP9-1",
            0.97,
            "pass",
            "component mapping",
            [],
            "high",
            {
                "filename": "a.dwg",
                "source": "component_mapping",
                "component_submode": "strip_two_port_component",
            },
            pair_kind="component_mapping",
        ),
        Pair(
            "P2",
            "G2",
            "S1",
            "F1",
            "PC2",
            "5KLP10-1",
            "5KLP8-1",
            0.96,
            "pass",
            "component mapping",
            [],
            "high",
            {
                "filename": "a.dwg",
                "source": "component_mapping",
                "component_submode": "strip_two_port_component",
            },
            pair_kind="component_mapping",
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["COMPONENT"]),
        LineGroup("G2", "S1", "F1", 20, 0, 30, 0, 10, 0.9, ["L2"], ["COMPONENT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "元件接线图", "元件接线图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    review = next(item for item in issues if item.rule_id == "R-ONE-TO-MANY")
    assert review.severity == "review"
    assert review.title == "组件端子分支映射待复核"
    assert "冲突" not in review.explanation
    assert "冲突" not in review.recommended_action
    assert review.related_pair_ids == ["P2"]
    assert review.evidence["conflicting_values"] == ["5KLP8-1", "5KLP9-1"]
    assert review.evidence["one_to_many_classification"] == "component_branch_review"
    assert review.evidence["component_submode"] == "strip_two_port_component"


def test_rules_keep_regular_component_mapping_one_to_many_as_review() -> None:
    pairs = [
        Pair(
            "P1",
            "G1",
            "S1",
            "F1",
            "PC1",
            "5KLP10-1",
            "5KLP9-1",
            0.97,
            "pass",
            "component mapping",
            [],
            "high",
            {"filename": "a.dwg", "source": "component_mapping"},
            pair_kind="component_mapping",
        ),
        Pair(
            "P2",
            "G2",
            "S1",
            "F1",
            "PC2",
            "5KLP10-1",
            "5KLP8-1",
            0.96,
            "pass",
            "component mapping",
            [],
            "high",
            {"filename": "a.dwg", "source": "component_mapping"},
            pair_kind="component_mapping",
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["COMPONENT"]),
        LineGroup("G2", "S1", "F1", 20, 0, 30, 0, 10, 0.9, ["L2"], ["COMPONENT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "元件接线图", "元件接线图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    review = next(item for item in issues if item.rule_id == "R-ONE-TO-MANY")
    assert review.severity == "review"
    assert review.title == "一对多待复核"
    assert review.evidence["one_to_many_classification"] == "review"


def test_rules_emit_one_to_many_branch_when_left_value_allowlisted() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    config["rules"]["one_to_many_branch_left_values"] = ["101"]
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "a.dwg"}),
        Pair("P2", "G2", "S1", "F1", "PC2", "101", "202", 0.96, "pass", "ok", [], "high", {"filename": "a.dwg"}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S1", "F1", 20, 0, 30, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, config)

    branch = next(item for item in issues if item.rule_id == "R-ONE-TO-MANY")
    assert branch.severity == "minor"
    assert branch.title == "一对多合法分支"
    assert branch.evidence["one_to_many_classification"] == "branch"
    assert branch.related_pair_ids == ["P2"]


def test_rules_skip_discard_pairs_for_pair_quality_issues() -> None:
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", None, None, 0.18, "discard", "no numeric candidates", [], "low", {}),
        Pair("P2", "G2", "S1", "F1", "PC2", "101", None, 0.52, "review", "missing right candidate", [], "review", {}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S1", "F1", 10, 0, 20, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert all(issue.pair_id != "P1" for issue in issues)
    assert any(issue.rule_id == "R-PAIR-MISSING-SIDE" and issue.pair_id == "P2" for issue in issues)
    assert not any(issue.rule_id == "R-PAIR-LOW-CONFIDENCE" and issue.pair_id == "P2" for issue in issues)


def test_rules_only_emit_low_confidence_for_complete_pairs() -> None:
    pairs = [
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.80, "review", "ambiguous candidate ordering", [], "review", {}),
        Pair("P2", "G2", "S1", "F1", "PC2", "102", None, 0.80, "review", "missing right candidate", [], "review", {}),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S1", "F1", 10, 0, 20, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    assert any(issue.rule_id == "R-PAIR-LOW-CONFIDENCE" and issue.pair_id == "P1" for issue in issues)
    assert any(issue.rule_id == "R-PAIR-MISSING-SIDE" and issue.pair_id == "P2" for issue in issues)
    assert not any(issue.rule_id == "R-PAIR-LOW-CONFIDENCE" and issue.pair_id == "P2" for issue in issues)


def test_rules_aggregate_complementary_missing_side_pairs() -> None:
    pairs = [
        Pair(
            "P1",
            "G1",
            "S1",
            "F1",
            "PC1",
            None,
            "723",
            0.82,
            "review",
            "missing left candidate",
            [],
            "review",
            {},
            right_text_id="T723",
            right_coord_x=44.0,
            right_coord_y=20.0,
        ),
        Pair(
            "P2",
            "G2",
            "S1",
            "F1",
            "PC2",
            "723",
            None,
            0.83,
            "review",
            "missing right candidate",
            [],
            "review",
            {},
            left_text_id="T723",
            left_coord_x=48.0,
            left_coord_y=20.2,
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 10, 20, 40, 20, 30, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G2", "S1", "F1", 48, 20.1, 90, 20.1, 42, 0.9, ["L2"], ["CONNECT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "08 测控1开入回路图1.dwg", 8, "08", "测控1开入回路图1", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    missing_side = [issue for issue in issues if issue.rule_id == "R-PAIR-MISSING-SIDE"]
    assert len(missing_side) == 1
    issue = missing_side[0]
    assert issue.title == "互补半链待复核"
    assert issue.primary_pair_id == "P1"
    assert issue.related_pair_ids == ["P2"]
    assert issue.evidence["chain_kind"] == "complementary_half_pair"
    assert issue.evidence["shared_text_id"] == "T723"
    assert issue.evidence["bridge_gap"] == 8.0


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
    assert conflict.title == "多对一配对"
    assert conflict.right_value == "201"
    assert conflict.related_pair_ids == ["P2"]
    assert conflict.evidence["conflicting_values"] == ["101", "102"]
    assert "many_to_one_classification" not in conflict.evidence
    assert {ref["filename"] for ref in conflict.evidence_refs} == {"a.dwg", "b.dwg"}


def test_rules_emit_many_to_one_component_branch_review_for_strip_two_port_component() -> None:
    pairs = [
        Pair(
            "P1",
            "G1",
            "S1",
            "F1",
            "PC1",
            "5KLP10-1",
            "5KLP9-1",
            0.97,
            "pass",
            "component mapping",
            [],
            "high",
            {
                "filename": "a.dwg",
                "source": "component_mapping",
                "component_submode": "strip_two_port_component",
            },
            pair_kind="component_mapping",
        ),
        Pair(
            "P2",
            "G2",
            "S1",
            "F1",
            "PC2",
            "5KLP8-1",
            "5KLP9-1",
            0.96,
            "pass",
            "component mapping",
            [],
            "high",
            {
                "filename": "a.dwg",
                "source": "component_mapping",
                "component_submode": "strip_two_port_component",
            },
            pair_kind="component_mapping",
        ),
    ]
    groups = [
        LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["COMPONENT"]),
        LineGroup("G2", "S1", "F1", 20, 0, 30, 0, 10, 0.9, ["L2"], ["COMPONENT"]),
    ]
    sheets = [
        SheetRecord("S1", "F1", "a.dwg", 1, "01", "元件接线图", "元件接线图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, DEFAULT_CONFIG)

    review = next(item for item in issues if item.rule_id == "R-MANY-TO-ONE")
    assert review.severity == "review"
    assert review.title == "组件端子多入口映射待复核"
    assert "冲突" not in review.explanation
    assert "冲突" not in review.recommended_action
    assert review.related_pair_ids == ["P2"]
    assert review.evidence["conflicting_values"] == ["5KLP10-1", "5KLP8-1"]
    assert review.evidence["many_to_one_classification"] == "component_branch_review"
    assert review.evidence["component_submode"] == "strip_two_port_component"


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


def test_build_pairs_supports_vertical_group_side_labels() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=60.0,
            start_y=80.0,
            end_x=60.0,
            end_y=40.0,
            length=40.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="vertical",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "20 元件接线图2.dwg", 20, "20", "元件接线图2", "元件接线图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate("C0001", "G0001", "S0001", "F0001", "top", "T1", "101", "101", 0.96, "accepted", None, 60.0, 80.0, 0.5, 4.0, 60.5, 84.0),
        TerminalCandidate("C0002", "G0001", "S0001", "F0001", "bottom", "T2", "202", "202", 0.95, "accepted", None, 60.0, 40.0, 0.5, 4.0, 59.5, 36.0),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.status == "pass"
    assert pair.left_value == "101"
    assert pair.right_value == "202"
    assert pair.evidence["line_orientation"] == "vertical"
    assert pair.evidence["left_side_label"] == "top"
    assert pair.evidence["right_side_label"] == "bottom"


def test_build_pairs_discards_same_virtual_text_stub_on_horizontal_component_page() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=60.0,
            start_y=40.0,
            end_x=85.0,
            end_y=40.0,
            length=25.0,
            wire_candidate_score=0.92,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "19 元件接线图1.dwg", 19, "19", "元件接线图1", "元件接线图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate(
            "C0001", "G0001", "S0001", "F0001", "left", "T1", "2", "2", 0.96, "accepted", None, 60.0, 40.0, 1.0, 0.0,
            61.5, 40.0, source_block_name="KK1P"
        ),
        TerminalCandidate(
            "C0002", "G0001", "S0001", "F0001", "right", "T1", "2", "2", 0.95, "accepted", None, 85.0, 40.0, 1.0, 0.0,
            61.5, 40.0, source_block_name="KK1P"
        ),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.status == "discard"
    assert pair.rationale == "self_pair_from_same_virtual_text"
    assert pair.evidence["selected_left_source_block_name"] == "KK1P"
    assert pair.evidence["selected_right_source_block_name"] == "KK1P"


def test_build_pairs_discards_same_block_single_digit_internal_pin_pair_on_horizontal_component_page() -> None:
    groups = [
        LineGroup(
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            start_x=60.0,
            start_y=40.0,
            end_x=85.0,
            end_y=40.0,
            length=25.0,
            wire_candidate_score=0.92,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "19 元件接线图1.dwg", 19, "19", "元件接线图1", "元件接线图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate(
            "C0001", "G0001", "S0001", "F0001", "left", "T1", "2", "2", 0.96, "accepted", None, 60.0, 40.0, 1.0, 0.0,
            61.5, 40.0, source_block_name="KK2P"
        ),
        TerminalCandidate(
            "C0002", "G0001", "S0001", "F0001", "right", "T2", "4", "4", 0.95, "accepted", None, 85.0, 40.0, 1.0, 0.0,
            83.5, 40.0, source_block_name="KK2P"
        ),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.status == "discard"
    assert pair.rationale == "block_internal_pin_pair"
    assert pair.evidence["selected_left_source_block_name"] == "KK2P"
    assert pair.evidence["selected_right_source_block_name"] == "KK2P"


def test_build_pairs_keeps_same_block_multi_digit_component_pair() -> None:
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
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "19 元件接线图1.dwg", 19, "19", "元件接线图1", "元件接线图", "supplemental", "filename", True)
    ]
    candidates = [
        TerminalCandidate(
            "C0001", "G0001", "S0001", "F0001", "left", "T1", "101", "101", 0.96, "accepted", None, 0, 0, 1, 0,
            10.0, 20.0, source_block_name="COMP_ROW"
        ),
        TerminalCandidate(
            "C0002", "G0001", "S0001", "F0001", "right", "T2", "202", "202", 0.95, "accepted", None, 100, 0, 1, 0,
            90.0, 20.0, source_block_name="COMP_ROW"
        ),
    ]

    _, pairs = build_pairs(groups, candidates, sheets, DEFAULT_CONFIG)

    pair = pairs[0]
    assert pair.status == "pass"
    assert pair.left_value == "101"
    assert pair.right_value == "202"


def test_build_issues_emits_sheet_page_mismatch_when_filename_and_title_block_differ() -> None:
    """R-SHEET-PAGE-MISMATCH：文件名页码与标题栏页码不一致时应触发 major issue。"""
    config = deepcopy(DEFAULT_CONFIG)
    sheets = [
        SheetRecord(
            sheet_id="S0001",
            file_id="F0001",
            filename="08 测控1开入回路图1.dwg",
            sheet_order=8,
            sheet_no="09",  # 标题栏页码与文件名 08 不一致
            sheet_title="测控1开入回路图1",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="title_block",
            is_primary_audit_candidate=True,
        )
    ]

    issues = build_issues([], [], sheets, config)

    mismatch_issues = [issue for issue in issues if issue.rule_id == "R-SHEET-PAGE-MISMATCH"]
    assert len(mismatch_issues) == 1
    issue = mismatch_issues[0]
    assert issue.severity == "major"
    assert issue.issue_type == "sheet_page_mismatch"
    assert issue.evidence["filename_page_no"] == "08"
    assert issue.evidence["title_block_page_no"] == "09"


def test_build_issues_does_not_emit_sheet_page_mismatch_when_page_numbers_match() -> None:
    """文件名页码与标题栏页码一致时不应触发 R-SHEET-PAGE-MISMATCH。"""
    config = deepcopy(DEFAULT_CONFIG)
    sheets = [
        SheetRecord(
            sheet_id="S0001",
            file_id="F0001",
            filename="08 测控1开入回路图1.dwg",
            sheet_order=8,
            sheet_no="08",  # 一致
            sheet_title="测控1开入回路图1",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="title_block",
            is_primary_audit_candidate=True,
        )
    ]

    issues = build_issues([], [], sheets, config)

    mismatch_issues = [issue for issue in issues if issue.rule_id == "R-SHEET-PAGE-MISMATCH"]
    assert len(mismatch_issues) == 0


def test_build_issues_treats_table_mapping_pairs_as_high_confidence_source() -> None:
    """table_mapping Pair 应作为高置信信源参与跨页冲突校验。"""
    config = deepcopy(DEFAULT_CONFIG)
    # 两个 table_mapping pair：S1 的 101->102 和 S2 的 101->103
    # 同一左值 101 跨页映射到不同右值，应触发 R-CROSS-PAGE-CONFLICT
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id=None,
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id=None,
            left_value="101",
            right_value="102",
            confidence=0.95,
            status="pass",
            rationale="table mapping",
            confidence_bucket="high",
            evidence={"source": "table_mapping"},
            pair_kind="table_mapping",
        ),
        Pair(
            pair_id="P0002",
            line_group_id=None,
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id=None,
            left_value="101",
            right_value="103",
            confidence=0.95,
            status="pass",
            rationale="table mapping",
            confidence_bucket="high",
            evidence={"source": "table_mapping"},
            pair_kind="table_mapping",
        ),
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "t1.dwg", 1, "01", "t1", None, "primary", "filename", True),
        SheetRecord("S0002", "F0002", "t2.dwg", 2, "02", "t2", None, "primary", "filename", True),
    ]

    issues = build_issues(pairs, [], sheets, config)

    cross_page_issues = [issue for issue in issues if issue.rule_id == "R-CROSS-PAGE-CONFLICT"]
    assert len(cross_page_issues) >= 1
    issue = cross_page_issues[0]
    assert "101" in issue.values
    assert issue.evidence["one_to_many_classification"] == "conflict"


def test_build_issues_demotes_backplate_virtual_table_cross_page_scope_conflict() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id=None,
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id=None,
            left_value="NDY306A-3",
            right_value="1QD1",
            confidence=0.95,
            status="pass",
            rationale="backplate virtual table",
            confidence_bucket="high",
            evidence={
                "source": "table_mapping",
                "table_mapping": {
                    "mapping_mode": "backplate_virtual_table",
                    "source_block_name": "WBH-812E-E1SA-101",
                    "header_prefix": "NDY306A",
                    "row_number": 3,
                },
            },
            pair_kind="table_mapping",
        ),
        Pair(
            pair_id="P0002",
            line_group_id=None,
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id=None,
            left_value="NDY306A-3",
            right_value="3-2QD1",
            confidence=0.95,
            status="pass",
            rationale="backplate virtual table",
            confidence_bucket="high",
            evidence={
                "source": "table_mapping",
                "table_mapping": {
                    "mapping_mode": "backplate_virtual_table",
                    "source_block_name": "WBH-813E-E1SH-101",
                    "header_prefix": "NDY306A",
                    "row_number": 3,
                },
            },
            pair_kind="table_mapping",
        ),
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "17 差动保护背板图.dwg", 17, "17", "背板图", "背板图", "primary", "filename", True),
        SheetRecord("S0002", "F0002", "19 低后备保护背板图.dwg", 19, "19", "背板图", "背板图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, [], sheets, config)

    cross_page_issues = [issue for issue in issues if issue.rule_id == "R-CROSS-PAGE-CONFLICT"]
    assert len(cross_page_issues) == 1
    issue = cross_page_issues[0]
    assert issue.severity == "review"
    assert issue.title == "背板表格作用域待复核"
    assert issue.evidence["one_to_many_classification"] == "backplate_table_scope_review"
    assert issue.evidence["table_mapping_mode"] == "backplate_virtual_table"
    assert issue.evidence["source_block_names"] == ["WBH-812E-E1SA-101", "WBH-813E-E1SH-101"]
    assert issue.evidence["header_prefixes"] == ["NDY306A"]


def test_build_issues_treats_component_mapping_pairs_as_high_confidence_source() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id=None,
            left_value="5KLP10-1",
            right_value="5KLP9-1",
            confidence=0.95,
            status="pass",
            rationale="component mapping",
            confidence_bucket="high",
            evidence={"source": "component_mapping"},
            pair_kind="component_mapping",
        ),
        Pair(
            pair_id="P0002",
            line_group_id="G0002",
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id=None,
            left_value="5KLP10-1",
            right_value="5KLP8-1",
            confidence=0.95,
            status="pass",
            rationale="component mapping",
            confidence_bucket="high",
            evidence={"source": "component_mapping"},
            pair_kind="component_mapping",
        ),
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "23 元件接线图3.dwg", 23, "23", "元件接线图3", "元件接线图", "supplemental", "filename", True),
        SheetRecord("S0002", "F0002", "24 元件接线图4.dwg", 24, "24", "元件接线图4", "元件接线图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, [], sheets, config)

    cross_page_issues = [issue for issue in issues if issue.rule_id == "R-CROSS-PAGE-CONFLICT"]
    assert len(cross_page_issues) >= 1
    issue = cross_page_issues[0]
    assert "5KLP10-1" in issue.values
    assert issue.evidence["one_to_many_classification"] == "conflict"


def test_build_issues_does_not_treat_low_confidence_component_mapping_as_high_confidence_source() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id=None,
            left_value="5KLP10-1",
            right_value="5KLP9-1",
            confidence=0.95,
            status="pass",
            rationale="component mapping",
            confidence_bucket="high",
            evidence={"source": "component_mapping"},
            pair_kind="component_mapping",
        ),
        Pair(
            pair_id="P0002",
            line_group_id="G0002",
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id=None,
            left_value="5KLP10-1",
            right_value="5KLP8-1",
            confidence=0.60,
            status="review",
            rationale="weak component mapping",
            confidence_bucket="review",
            evidence={"source": "component_mapping"},
            pair_kind="component_mapping",
        ),
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "23 元件接线图3.dwg", 23, "23", "元件接线图3", "元件接线图", "supplemental", "filename", True),
        SheetRecord("S0002", "F0002", "24 元件接线图4.dwg", 24, "24", "元件接线图4", "元件接线图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, [], sheets, config)

    assert not any(issue.rule_id == "R-CROSS-PAGE-CONFLICT" for issue in issues)


def test_missing_reciprocal_graph_can_see_component_mapping_reverse_edge() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    config["rules"]["reciprocal_required"] = True
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id="PC0001",
            left_value="5KLP9-1",
            right_value="5KLP10-1",
            confidence=0.96,
            status="pass",
            rationale="ordinary pair",
            confidence_bucket="high",
            evidence={"filename": "ordinary.dwg"},
        ),
        Pair(
            pair_id="P0002",
            line_group_id="G0002",
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id=None,
            left_value="5KLP10-1",
            right_value="5KLP9-1",
            confidence=0.95,
            status="pass",
            rationale="component mapping",
            confidence_bucket="high",
            evidence={"source": "component_mapping"},
            pair_kind="component_mapping",
        ),
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "08 回路图.dwg", 8, "08", "回路图", "二次原理图", "primary", "filename", True),
        SheetRecord("S0002", "F0002", "23 元件接线图3.dwg", 23, "23", "元件接线图3", "元件接线图", "supplemental", "filename", True),
    ]

    issues = build_issues(pairs, [], sheets, config)

    assert not any(
        issue.rule_id == "R-MISSING-RECIPROCAL" and issue.primary_pair_id == "P0001"
        for issue in issues
    )


def test_build_issues_emits_mixed_source_conflict_for_table_mapping_vs_ordinary_pair() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id=None,
            left_value="101",
            right_value="102",
            confidence=0.95,
            status="pass",
            rationale="table mapping",
            confidence_bucket="high",
            evidence={"source": "table_mapping", "sheet_order": 5},
            pair_kind="table_mapping",
        ),
        Pair(
            pair_id="P0002",
            line_group_id="G0002",
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id="PC0002",
            left_value="101",
            right_value="103",
            confidence=0.97,
            status="pass",
            rationale="ordinary pair",
            confidence_bucket="high",
            evidence={"sheet_order": 8},
        ),
    ]
    groups = [
        LineGroup("G0001", "S0001", "F0001", 0, 0, 10, 0, 10, 0.9, ["L1"], ["TABLE"]),
        LineGroup("G0002", "S0002", "F0002", 20, 0, 40, 0, 20, 0.9, ["L2"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "05 回路表格图.dwg", 5, "05", "回路表格图", "表格型图", "primary", "filename", True),
        SheetRecord("S0002", "F0002", "08 回路图.dwg", 8, "08", "回路图", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, config)

    mixed = next(item for item in issues if item.rule_id == "R-TABLE-MAPPING-SOURCE-CONFLICT")
    assert mixed.severity == "major"
    assert mixed.left_value == "101"
    assert mixed.evidence["source_conflict_kind"] == "table_mapping_vs_ordinary_pair"
    assert mixed.evidence["table_mapping_values"] == ["102"]
    assert mixed.evidence["ordinary_pair_values"] == ["103"]
    assert mixed.evidence["conflicting_values"] == ["102", "103"]
    assert mixed.evidence["source_pair_counts"] == {"table_mapping": 1, "ordinary_pair": 1}
    assert mixed.related_pair_ids == ["P0002"]
    assert {ref["pair_id"] for ref in mixed.evidence_refs} == {"P0001", "P0002"}


def test_build_issues_skips_mixed_source_conflict_when_table_and_ordinary_agree() -> None:
    config = deepcopy(DEFAULT_CONFIG)
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id=None,
            left_value="101",
            right_value="102",
            confidence=0.95,
            status="pass",
            rationale="table mapping",
            confidence_bucket="high",
            evidence={"source": "table_mapping", "sheet_order": 5},
            pair_kind="table_mapping",
        ),
        Pair(
            pair_id="P0002",
            line_group_id="G0002",
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id="PC0002",
            left_value="101",
            right_value="102",
            confidence=0.97,
            status="pass",
            rationale="ordinary pair",
            confidence_bucket="high",
            evidence={"sheet_order": 8},
        ),
    ]
    groups = [
        LineGroup("G0001", "S0001", "F0001", 0, 0, 10, 0, 10, 0.9, ["L1"], ["TABLE"]),
        LineGroup("G0002", "S0002", "F0002", 20, 0, 40, 0, 20, 0.9, ["L2"], ["WIRE"]),
    ]
    sheets = [
        SheetRecord("S0001", "F0001", "05 回路表格图.dwg", 5, "05", "回路表格图", "表格型图", "primary", "filename", True),
        SheetRecord("S0002", "F0002", "08 回路图.dwg", 8, "08", "回路图", "二次原理图", "primary", "filename", True),
    ]

    issues = build_issues(pairs, groups, sheets, config)

    assert not any(item.rule_id == "R-TABLE-MAPPING-SOURCE-CONFLICT" for item in issues)
