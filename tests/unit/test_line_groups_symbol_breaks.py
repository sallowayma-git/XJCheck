"""WIRE-BREAK: line groups are cut at symbol bodies (terminal bodies and element symbols), synthetic geometry.

Fixtures follow loop/MULTI-SEG README section 5.3 where the shape can be written as plain lines, marks and texts.
A mark is one TERMPOINT segment (symbol_key, record_id, x1, y1, x2, y2); a symbol body is two marks of one symbol
on the two sides of a gap.
"""

from dwg_audit.audit.line_groups import (
    UNKNOWN_BODY_WIDTH_BELOW_MIN,
    UNKNOWN_DOT_IN_SYMBOL_GAP,
    WireBreakEvidence,
    build_line_groups,
    wire_break_evidence_by_sheet,
)
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SwConnectDot
from dwg_audit.domain.models import SwPort
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG


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


def _wire(index: int, x1: float, x2: float, y: float = 20.0) -> LineEntity:
    return LineEntity(
        f"L{index}", "S1", "F1", f"H{index}", "LINE", "WIRE",
        x1, y, x2, y, abs(x2 - x1), 0.0, min(x1, x2), y, max(x1, x2), y,
    )


def _text(index: int, value: str, x1: float, x2: float, y: float = 20.0) -> TextItem:
    return TextItem(
        f"T{index}", "S1", "F1", f"TH{index}", "TEXT", value, value, value.isdigit(), "DIM", 0.0, 2.5,
        (x1 + x2) / 2.0, y, x1, y - 1.0, x2, y + 1.0,
    )


def _mark(symbol: str, record: str, x: float, y: float = 20.0) -> tuple:
    """A TERMPOINT segment 1.0 long centred on x, on the line at y."""
    return (symbol, record, x - 0.5, y, x + 0.5, y)


def _groups(lines, marks=(), dots=(), texts=(), evidence_out=None):
    evidence = WireBreakEvidence(marks=tuple(marks), dots=tuple(dots))
    if evidence_out is not None:
        evidence_out.append(evidence)
    groups = build_line_groups(lines, [_sheet()], DEFAULT_CONFIG, list(texts), wire_break_evidence={"S1": evidence})
    return groups, evidence


def test_two_port_terminal_body_is_a_break() -> None:
    # T1: body 2.5 wide, one TERMPOINT of symbol A on each side of the gap.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]
    marks = [_mark("A", "P1", 50.0), _mark("A", "P2", 52.5)]

    groups, _ = _groups(lines, marks)

    assert [g.member_line_ids for g in groups] == [["L1"], ["L2"]]


def test_consecutive_bodies_split_into_one_piece_per_wire() -> None:
    # T2: three wires, two terminal bodies on one row.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 90.0), _wire(3, 92.5, 130.0)]
    marks = [_mark("A", "P1", 50.0), _mark("A", "P2", 52.5), _mark("B", "P3", 90.0), _mark("B", "P4", 92.5)]

    groups, _ = _groups(lines, marks)

    assert sorted(g.member_line_ids[0] for g in groups) == ["L1", "L2", "L3"]
    assert len(groups) == 3


def test_two_pin_symbol_spanning_a_ten_unit_gap_is_a_break() -> None:
    # T3: unregistered two-pin symbol (TERMPOINTs at both ends of the gap, width 10).
    lines = [_wire(1, 10.0, 50.0), _wire(2, 60.0, 100.0)]
    marks = [_mark("U", "U1", 50.0), _mark("U", "U2", 60.0)]

    groups, _ = _groups(lines, marks)

    assert len(groups) == 2


def test_numeric_label_does_not_bridge_a_symbol_body() -> None:
    # Numeric text bridges a 10-unit gap without a symbol (legacy), but never across a symbol body.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 60.0, 100.0)]
    label = [_text(1, "1431", 52.0, 58.0)]

    groups_plain, _ = _groups(lines, texts=label)
    groups_body, _ = _groups(lines, [_mark("U", "U1", 50.0), _mark("U", "U2", 60.0)], texts=label)

    assert len(groups_plain) == 1
    assert len(groups_body) == 2


def test_text_only_gap_keeps_the_wire_merged() -> None:
    # T4: a gap holding only a wire-number label is a wire broken by its label.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]
    label = [_text(1, "723", 49.0, 54.0)]

    groups, _ = _groups(lines, texts=label)

    assert len(groups) == 1


def test_connect_dot_in_a_symbol_gap_keeps_the_wire_merged_and_is_logged() -> None:
    # T5 (with a symbol): a dot inside a body gap is ambiguous; the legacy merge is kept and the gap is logged.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]
    marks = [_mark("A", "P1", 50.0), _mark("A", "P2", 52.5)]

    groups, evidence = _groups(lines, marks, dots=[(51.25, 20.0)])

    assert len(groups) == 1
    assert [row["reason_code"] for row in evidence.log] == [UNKNOWN_DOT_IN_SYMBOL_GAP]
    assert evidence.log[0]["action"] == "kept_merged"


def test_connect_dot_without_symbol_keeps_the_wire_merged() -> None:
    # T5: a dot in an empty gap of 2.5 keeps the wire merged (no symbol, nothing logged).
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]

    groups, evidence = _groups(lines, dots=[(51.25, 20.0)])

    assert len(groups) == 1
    assert evidence.log == []


def test_terminal_hanging_on_a_wire_end_does_not_cut() -> None:
    # T6: one TERMPOINT of a symbol on the wire end, the other symbol port absent: not a body.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]
    marks = [_mark("E", "E1", 50.0)]

    groups, _ = _groups(lines, marks)

    assert len(groups) == 1


def test_narrow_three_pin_pitch_is_kept_and_logged() -> None:
    # T9: 1.25 pitch of one symbol's pins is not a two-port body: merged, recorded as unknown.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 51.25, 100.0)]
    marks = [_mark("A", "P1", 50.0), _mark("A", "P3", 51.25)]

    groups, evidence = _groups(lines, marks)

    assert len(groups) == 1
    assert [row["reason_code"] for row in evidence.log] == [UNKNOWN_BODY_WIDTH_BELOW_MIN]


def test_marks_of_two_different_symbols_do_not_cut() -> None:
    # T12: TERMPOINTs of two different inserts on the two sides: no body, merged.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]
    marks = [_mark("A", "P1", 50.0), _mark("B", "P2", 52.5)]

    groups, evidence = _groups(lines, marks)

    assert len(groups) == 1
    assert evidence.log == []


def test_marks_on_another_row_do_not_cut() -> None:
    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]
    marks = [_mark("A", "P1", 50.0, y=40.0), _mark("A", "P2", 52.5, y=40.0)]

    groups, _ = _groups(lines, marks)

    assert len(groups) == 1


def test_symbol_with_one_mark_inside_the_gap_spans_the_break() -> None:
    # T10: element inside a gap: one TERMPOINT on the left wire end, the other inside the gap on the far side.
    lines = [_wire(1, 10.0, 50.0), _wire(2, 60.0, 100.0)]
    marks = [_mark("K", "K1", 50.0), _mark("K", "K2", 56.5)]

    groups, _ = _groups(lines, marks)

    assert len(groups) == 2


def test_evidence_collects_marks_from_ports_and_unregistered_blocks() -> None:
    port = SwPort(record_id="P1", sheet_id="S1", file_id="F1", symbol_id="SW:F1:S1:/A", insert_handle="A",
                  category="装置端子", start_x=49.5, start_y=20.0, end_x=50.5, end_y=20.0)
    block = {"record_id": "USY:F1:S1:/B", "sheet_id": "S1", "file_id": "F1", "instance_path": "/B",
             "termpoints": [{"number": "1", "a": (59.5, 20.0), "b": (60.5, 20.0)}]}
    dot = SwConnectDot(record_id="D1", sheet_id="S1", file_id="F1", x=51.0, y=20.0)

    evidence = wire_break_evidence_by_sheet([port], [dot], [block])["S1"]

    assert {(key, rid) for key, rid, *_ in evidence.marks} == {
        ("SW:F1:S1:/A", "P1"),
        ("SW:F1:S1:/B", "USY:F1:S1:/B#1"),
    }
    assert evidence.dots == ((51.0, 20.0),)
    assert not evidence.stats
    assert evidence.log == []


def test_symbol_cut_group_ids_marks_pieces_that_end_on_a_cut() -> None:
    from dwg_audit.audit.line_groups import symbol_cut_group_ids

    lines = [_wire(1, 10.0, 50.0), _wire(2, 52.5, 100.0)]
    evidence = WireBreakEvidence(marks=(_mark("A", "P1", 50.0), _mark("A", "P2", 52.5)))
    groups, ev = _groups(lines, evidence.marks)

    ids = symbol_cut_group_ids(groups, {"S1": ev})

    assert ids == {g.line_group_id for g in groups}
    assert symbol_cut_group_ids(groups, {}) == set()


def test_provisional_half_pair_rule_skips_pass_and_wire_route_pairs() -> None:
    from types import SimpleNamespace as NS

    from dwg_audit.audit.superworks_extractor import _is_provisional_half

    cut = {"G1"}
    half_review = NS(line_group_id="G1", status="review", left_value="612", right_value=None, evidence={})
    full_review = NS(line_group_id="G1", status="review", left_value="612", right_value="1n612", evidence={})
    full_pass = NS(line_group_id="G1", status="pass", left_value="612", right_value="1n612", evidence={})
    route = NS(line_group_id="G1", status="review", left_value="612", right_value="1n612",
               evidence={"sw_wire_route": {"record_id": "R"}})
    elsewhere = NS(line_group_id="G9", status="review", left_value="612", right_value=None, evidence={})

    assert _is_provisional_half(half_review, cut)
    assert _is_provisional_half(full_review, cut)
    assert not _is_provisional_half(full_pass, cut)
    assert not _is_provisional_half(route, cut)
    assert not _is_provisional_half(elsewhere, cut)
