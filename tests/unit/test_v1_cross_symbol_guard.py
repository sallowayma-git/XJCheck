"""P3-CROSS-DEVICE: a V1 wire-component mapping whose straight path runs through a symbol body is not a direct wire.

Synthetic geometry. A mark is one TERMPOINT segment (symbol_key, record_id, x1, y1, x2, y2); a body is two marks of
one symbol on the path. The path test is PathBodyChecker (line_groups), the pair guard is in wire_components.
"""

from dwg_audit.audit.line_groups import (
    UNKNOWN_BODY_WIDTH_BELOW_MIN,
    UNKNOWN_DOT_IN_SYMBOL_GAP,
    PathBodyChecker,
    WireBreakEvidence,
    path_body_checkers,
)
from dwg_audit.audit.wire_components import extract_component_prefixed_signal_pairs
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem


def _sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="08 跳闸出口回路.dwg",
        sheet_order=8,
        sheet_no="08",
        sheet_title="跳闸出口回路",
        sheet_category="二次原理图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(0.0, 0.0, 300.0, 200.0),
    )


def _mark(symbol: str, record: str, x: float, y: float) -> tuple:
    """A TERMPOINT segment 1.0 long centred on x, on the line at y (horizontal path)."""
    return (symbol, record, x - 0.5, y, x + 0.5, y)


def _vmark(symbol: str, record: str, x: float, y: float) -> tuple:
    """A TERMPOINT segment 1.0 long centred on y, on the line at x (vertical path)."""
    return (symbol, record, x, y - 0.5, x, y + 0.5)


def _text(index: int, value: str, x: float, y: float) -> TextItem:
    return TextItem(
        f"T{index}", "S1", "F1", f"TH{index}", "TEXT", value, value, value.isdigit(), "DIM", 0.0, 2.5,
        x, y, x - 3.0, y - 1.0, x + 3.0, y + 1.0,
    )


def _evidence(marks=(), dots=()) -> dict[str, WireBreakEvidence]:
    return {"S1": WireBreakEvidence(marks=tuple(marks), dots=tuple(dots))}


def _checker(marks=(), dots=()) -> PathBodyChecker:
    return PathBodyChecker(WireBreakEvidence(marks=tuple(marks), dots=tuple(dots)))


# --- PathBodyChecker -------------------------------------------------------------------------------------------

def test_path_through_two_terminals_of_one_symbol_is_a_body() -> None:
    checker = _checker([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 100.0, 50.0)])

    verdict, detail = checker.verdict((60.0, 50.0), (130.0, 50.0))

    assert verdict == "body"
    assert detail["symbol_key"] == "K"
    assert detail["marks"] == ["K#1", "K#2"]


def test_marks_of_two_different_symbols_are_not_a_body() -> None:
    checker = _checker([_mark("A", "A#1", 90.0, 50.0), _mark("B", "B#1", 100.0, 50.0)])

    assert checker.verdict((60.0, 50.0), (130.0, 50.0)) == (None, {"reason": "no_body_on_path"})


def test_one_terminal_on_the_path_is_not_a_body() -> None:
    # A terminal hanging on the path: only one of the symbol's marks lies between the anchors.
    checker = _checker([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 150.0, 50.0)])

    assert checker.verdict((60.0, 50.0), (130.0, 50.0)) == (None, {"reason": "no_body_on_path"})


def test_mark_at_an_anchor_is_the_anchor_terminal_not_a_body() -> None:
    # The anchor sits on the first terminal; the second terminal is beyond the far anchor.
    checker = _checker([_mark("K", "K#1", 60.2, 50.0), _mark("K", "K#2", 150.0, 50.0)])

    assert checker.verdict((60.0, 50.0), (130.0, 50.0)) == (None, {"reason": "no_body_on_path"})


def test_connect_dot_on_the_body_span_makes_the_shape_ambiguous() -> None:
    checker = _checker(
        [_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 100.0, 50.0)],
        dots=[(95.0, 50.0)],
    )

    verdict, detail = checker.verdict((60.0, 50.0), (130.0, 50.0))

    assert verdict == "ambiguous"
    assert detail["reason"] == UNKNOWN_DOT_IN_SYMBOL_GAP


def test_body_narrower_than_the_minimum_width_is_ambiguous() -> None:
    # Three-pin pitch 1.25: two adjacent pins on the path.
    checker = _checker([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 91.25, 50.0)])

    verdict, detail = checker.verdict((60.0, 50.0), (130.0, 50.0))

    assert verdict == "ambiguous"
    assert detail["reason"] == UNKNOWN_BODY_WIDTH_BELOW_MIN


def test_marks_off_the_path_line_do_not_count() -> None:
    checker = _checker([_mark("K", "K#1", 90.0, 60.0), _mark("K", "K#2", 100.0, 60.0)])

    assert checker.verdict((60.0, 50.0), (130.0, 50.0)) == (None, {"reason": "no_body_on_path"})


def test_vertical_path_through_a_body_is_detected() -> None:
    checker = _checker([_vmark("K", "K#1", 50.0, 90.0), _vmark("K", "K#2", 50.0, 100.0)])

    verdict, _ = checker.verdict((50.0, 60.0), (50.0, 130.0))

    assert verdict == "body"


def test_marks_on_the_wire_row_count_when_the_anchor_text_sits_a_few_units_off_it() -> None:
    # Text insert points sit about 2 units above or below the wire row they label; the row is 2.5 apart from them.
    checker = _checker([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 100.0, 50.0)])

    verdict, _ = checker.verdict((60.0, 52.0), (130.0, 52.0))

    assert verdict == "body"


def test_diagonal_path_gets_no_verdict() -> None:
    checker = _checker([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 100.0, 50.0)])

    assert checker.verdict((60.0, 20.0), (130.0, 80.0)) == (None, {"reason": "not_axis_aligned"})


def test_small_row_offset_still_counts_as_one_row() -> None:
    # Scoped external endpoints are matched within a 2.5 row tolerance; the path stays horizontal.
    checker = _checker([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 100.0, 50.0)])

    verdict, _ = checker.verdict((60.0, 51.5), (130.0, 50.0))

    assert verdict == "body"


# --- wire-component guard --------------------------------------------------------------------------------------

def _scoped_texts(endpoint_y: float = 116.5) -> list[TextItem]:
    return [
        _text(1, "1n", 130.6, 150.0),        # visible n-prefix column header
        _text(2, "204", 130.6, 115.7),       # local number under the prefix
        _text(3, "1QD4", 55.9, endpoint_y),  # external endpoint on the same row
    ]


def test_scoped_mapping_without_symbol_marks_stays_pass() -> None:
    pairs = extract_component_prefixed_signal_pairs([_sheet()], _scoped_texts(), [], wire_break_evidence=None)

    assert [p.status for p in pairs] == ["pass"]


def test_scoped_mapping_across_a_symbol_body_is_discarded() -> None:
    marks = [_mark("K", "K#1", 90.0, 116.0), _mark("K", "K#2", 100.0, 116.0)]

    pairs = extract_component_prefixed_signal_pairs(
        [_sheet()], _scoped_texts(), [], wire_break_evidence=_evidence(marks),
    )

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.status == "discard"
    assert pair.evidence["discard_reason"] == "crosses_symbol_body"
    assert pair.evidence["symbol_body_path_check"]["verdict"] == "body"
    assert pair.evidence["legacy_rationale"].startswith("Scoped visible prefix mapping")


def test_scoped_mapping_with_an_ambiguous_body_is_review() -> None:
    marks = [_mark("K", "K#1", 90.0, 116.0), _mark("K", "K#2", 100.0, 116.0)]
    dots = [(95.0, 116.0)]

    pairs = extract_component_prefixed_signal_pairs(
        [_sheet()], _scoped_texts(), [], wire_break_evidence=_evidence(marks, dots),
    )

    assert [p.status for p in pairs] == ["review"]
    assert pairs[0].evidence["symbol_body_path_check"]["reason"] == UNKNOWN_DOT_IN_SYMBOL_GAP


def test_scoped_mapping_with_marks_beside_the_path_stays_pass() -> None:
    # Marks of a symbol above the row: not on the path.
    marks = [_mark("K", "K#1", 90.0, 140.0), _mark("K", "K#2", 100.0, 140.0)]

    pairs = extract_component_prefixed_signal_pairs(
        [_sheet()], _scoped_texts(), [], wire_break_evidence=_evidence(marks),
    )

    assert [p.status for p in pairs] == ["pass"]
    assert pairs[0].evidence["symbol_body_path_check"] == {"verdict": None, "reason": "no_body_on_path"}


def test_scoped_mapping_on_a_sheet_without_symbol_marks_records_why() -> None:
    pairs = extract_component_prefixed_signal_pairs([_sheet()], _scoped_texts(), [], wire_break_evidence=None)

    assert pairs[0].evidence["symbol_body_path_check"] == {"verdict": None, "reason": "no_symbol_marks_on_sheet"}


# --- terminal-candidate guard (text search radius) ----------------------------------------------------------------

def _wire_group() -> "LineGroup":
    from dwg_audit.domain.models import LineGroup

    return LineGroup(
        line_group_id="G1",
        sheet_id="S1",
        file_id="F1",
        start_x=100.0,
        start_y=50.0,
        end_x=130.0,
        end_y=50.0,
        length=30.0,
        wire_candidate_score=0.55,
        member_line_ids=["L1"],
        layer_hints=["0"],
        orientation="horizontal",
    )


def _left_candidate(candidates) -> object:
    matches = [c for c in candidates if c.line_group_id == "G1" and c.side == "left" and c.text == "204"]
    assert len(matches) == 1
    return matches[0]


def test_candidate_beyond_a_symbol_body_along_the_wire_is_rejected() -> None:
    from dwg_audit.audit.candidates import build_terminal_candidates
    from dwg_audit.utils.config import DEFAULT_CONFIG

    text = _text(1, "204", 90.0, 50.5)
    marks = [_mark("K", "K#1", 94.0, 50.0), _mark("K", "K#2", 97.0, 50.0)]
    checkers = path_body_checkers(_evidence(marks))

    candidates = build_terminal_candidates(
        [_wire_group()], [text], DEFAULT_CONFIG, [_sheet()], path_checkers=checkers,
    )

    candidate = _left_candidate(candidates)
    assert candidate.status == "rejected"
    assert candidate.rejection_reason == "path_crosses_symbol_body"


def test_candidate_without_symbol_marks_on_the_path_is_unchanged() -> None:
    from dwg_audit.audit.candidates import build_terminal_candidates
    from dwg_audit.utils.config import DEFAULT_CONFIG

    text = _text(1, "204", 90.0, 50.5)

    legacy = build_terminal_candidates([_wire_group()], [text], DEFAULT_CONFIG, [_sheet()])
    guarded = build_terminal_candidates(
        [_wire_group()], [text], DEFAULT_CONFIG, [_sheet()],
        path_checkers=path_body_checkers(_evidence([_mark("K", "K#1", 94.0, 80.0), _mark("K", "K#2", 97.0, 80.0)])),
    )

    assert _left_candidate(legacy).status == "accepted"
    assert _left_candidate(guarded).status == "accepted"


# --- pair guard for pairs built by pairs.py -----------------------------------------------------------------------

def _pair(pair_id: str, left_x: float, right_x: float, evidence: dict) -> object:
    from dwg_audit.domain.models import Pair

    return Pair(
        pair_id=pair_id,
        line_group_id=None,
        sheet_id="S1",
        file_id="F1",
        selected_pair_candidate_id=None,
        left_value="1QD4",
        right_value="1n204",
        confidence=0.9,
        status="pass",
        rationale="test",
        evidence=evidence,
        left_coord_x=left_x,
        left_coord_y=50.0,
        right_coord_x=right_x,
        right_coord_y=50.0,
        pair_kind="wire_component_mapping",
    )


def test_guard_discards_a_v1_pair_built_outside_the_component_extractor() -> None:
    from dwg_audit.audit.wire_components import guard_pairs_against_symbol_bodies

    checkers = path_body_checkers(_evidence([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 100.0, 50.0)]))
    pair = _pair("P1", 60.0, 130.0, {"component_submode": "schematic_wire_logic_endpoint"})

    guard_pairs_against_symbol_bodies([pair], checkers)

    assert pair.status == "discard"
    assert pair.evidence["discard_reason"] == "crosses_symbol_body"


def test_guard_leaves_superworks_evidence_pairs_unchanged() -> None:
    from dwg_audit.audit.wire_components import guard_pairs_against_symbol_bodies

    checkers = path_body_checkers(_evidence([_mark("K", "K#1", 90.0, 50.0), _mark("K", "K#2", 100.0, 50.0)]))
    pair = _pair("P2", 60.0, 130.0, {"source": "superworks", "superworks": {"partial": False}})

    guard_pairs_against_symbol_bodies([pair], checkers)

    assert pair.status == "pass"
    assert "symbol_body_path_check" not in pair.evidence
