"""A small empty gap between two terminals is a wire break, not a merged wire (line_groups G2)."""

from dwg_audit.audit.line_groups import build_line_groups
from dwg_audit.audit.line_groups import wire_break_evidence_by_sheet
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SwConnectDot
from dwg_audit.domain.models import SwPort
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG


def _sheet(*, sheet_id: str = "S1", category: str = "二次原理图") -> SheetRecord:
    return SheetRecord(
        sheet_id=sheet_id,
        file_id="F1",
        filename="05 交流回路图2.dwg",
        sheet_order=5,
        sheet_no="05",
        sheet_title="交流回路图2",
        sheet_category=category,
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(0.0, 0.0, 120.0, 80.0),
    )


def _hline(line_id: str, x1: float, x2: float, y: float = 20.0, sheet_id: str = "S1") -> LineEntity:
    return LineEntity(
        line_id, sheet_id, "F1", f"H{line_id}", "LINE", "WIRE",
        x1, y, x2, y, abs(x2 - x1), 0.0, min(x1, x2), y, max(x1, x2), y,
    )


def _vline(line_id: str, y1: float, y2: float, x: float = 20.0, sheet_id: str = "S1") -> LineEntity:
    return LineEntity(
        line_id, sheet_id, "F1", f"H{line_id}", "LINE", "WIRE",
        x, y1, x, y2, abs(y2 - y1), 90.0, x, min(y1, y2), x, max(y1, y2),
    )


def _port(record_id: str, x1: float, x2: float, y: float = 20.0, sheet_id: str = "S1") -> SwPort:
    return SwPort(
        record_id=record_id, sheet_id=sheet_id, file_id="F1",
        start_x=x1, start_y=y, end_x=x2, end_y=y, category="装置端子", port_number="1",
    )


def _text(text_id: str, x1: float, x2: float, y1: float, y2: float, value: str = "1507") -> TextItem:
    return TextItem(
        text_id, "S1", "F1", f"T{text_id}", "MTEXT", value, value, True, "DIM", 0.0, 2.5,
        x1, y1, x1, y1, x2, y2,
    )


def _two_wires_with_gap(gap_start: float = 40.0, gap_end: float = 42.5) -> list[LineEntity]:
    """Wire A ends at gap_start, wire B starts at gap_end, both on y=20."""
    return [
        _hline("L1", 10.0, gap_start),
        _hline("L2", gap_end, 90.0),
    ]


def _terminal_ports() -> list[SwPort]:
    # One terminal marker on each side of the gap, each touching its wire end.
    return [_port("P1", 39.5, 40.5), _port("P2", 42.0, 43.0)]


def _groups(lines, texts=(), evidence=None, sheets=None, classifications=None):
    return build_line_groups(
        lines,
        sheets or [_sheet()],
        DEFAULT_CONFIG,
        list(texts),
        classifications=classifications,
        wire_break_evidence=evidence,
    )


def test_empty_gap_between_two_terminals_splits_wire_group() -> None:
    evidence = wire_break_evidence_by_sheet(_terminal_ports(), [])

    groups = _groups(_two_wires_with_gap(), evidence=evidence)

    assert len(groups) == 2
    assert sorted(group.member_line_ids for group in groups) == [["L1"], ["L2"]]


def test_wire_number_text_across_gap_keeps_merge() -> None:
    evidence = wire_break_evidence_by_sheet(_terminal_ports(), [])
    label = _text("1", 39.0, 44.0, 18.0, 22.0)

    groups = _groups(_two_wires_with_gap(), texts=[label], evidence=evidence)

    assert len(groups) == 1
    assert groups[0].member_line_ids == ["L1", "L2"]


def test_connect_dot_in_gap_keeps_merge() -> None:
    evidence = wire_break_evidence_by_sheet(
        _terminal_ports(),
        [SwConnectDot(record_id="D1", sheet_id="S1", file_id="F1", handle="DOT1", x=41.25, y=20.0)],
    )

    groups = _groups(_two_wires_with_gap(), evidence=evidence)

    assert len(groups) == 1


def test_gap_with_terminal_on_one_side_only_keeps_merge() -> None:
    evidence = wire_break_evidence_by_sheet([_port("P1", 39.5, 40.5)], [])

    groups = _groups(_two_wires_with_gap(), evidence=evidence)

    assert len(groups) == 1


def test_single_terminal_spanning_gap_keeps_merge() -> None:
    # One marker covers both wire ends: the wire passes through one terminal, it is not two wires.
    evidence = wire_break_evidence_by_sheet([_port("P1", 39.0, 44.0)], [])

    groups = _groups(_two_wires_with_gap(), evidence=evidence)

    assert len(groups) == 1


def test_no_sw_evidence_keeps_legacy_merge() -> None:
    groups = _groups(_two_wires_with_gap(), evidence=None)

    assert len(groups) == 1


def test_evidence_of_another_sheet_does_not_split() -> None:
    evidence = wire_break_evidence_by_sheet(
        [_port("P1", 39.5, 40.5, sheet_id="S2"), _port("P2", 42.0, 43.0, sheet_id="S2")], []
    )

    groups = _groups(_two_wires_with_gap(), evidence=evidence)

    assert len(groups) == 1


def test_gap_wider_than_tolerance_keeps_legacy_split() -> None:
    evidence = wire_break_evidence_by_sheet(
        [_port("P1", 39.5, 40.5), _port("P2", 45.5, 46.5)], []
    )

    groups = _groups(_two_wires_with_gap(gap_start=40.0, gap_end=46.0), evidence=evidence)

    assert len(groups) == 2


def test_touching_wire_ends_keep_merge_even_with_terminals() -> None:
    evidence = wire_break_evidence_by_sheet(
        [_port("P1", 39.5, 40.5), _port("P2", 39.5, 40.5)], []
    )

    groups = _groups([_hline("L1", 10.0, 40.0), _hline("L2", 40.0, 90.0)], evidence=evidence)

    assert len(groups) == 1


def test_vertical_orientation_split_uses_same_rule() -> None:
    lines = [_vline("V1", 10.0, 40.0), _vline("V2", 42.5, 90.0)]
    # Horizontal marker stubs at each wire end: on a vertical run they sit across the wire.
    ports = [
        SwPort(record_id="PV1", sheet_id="S1", file_id="F1", start_x=19.5, start_y=40.0, end_x=20.5, end_y=40.0,
               category="装置端子", port_number="1"),
        SwPort(record_id="PV2", sheet_id="S1", file_id="F1", start_x=19.5, start_y=42.5, end_x=20.5, end_y=42.5,
               category="装置端子", port_number="2"),
    ]
    evidence = wire_break_evidence_by_sheet(ports, [])
    sheet = _sheet(category="元件接线图")

    groups = build_line_groups(
        lines, [sheet], {**DEFAULT_CONFIG, "geometry": {**DEFAULT_CONFIG["geometry"], "line_group_orientation": "vertical"}},
        [], wire_break_evidence=evidence,
    )

    assert len(groups) == 2
    assert all(group.orientation == "vertical" for group in groups)


def test_grid_band_empty_gap_between_terminals_splits() -> None:
    classification = PageClassification(
        sheet_id="S1",
        page_type="二次原理图",
        page_subtype="grid_heavy_wire_diagram",
        page_type_confidence=0.95,
        table_like=False,
        grid_heavy=True,
        route_target="WireDiagramExtractor",
        features={"grid_band_count": 1},
    )
    evidence = wire_break_evidence_by_sheet(_terminal_ports(), [])

    groups = _groups(
        _two_wires_with_gap(),
        evidence=evidence,
        classifications={"S1": classification},
    )

    assert len(groups) == 2
    assert all(group.orientation == "grid" for group in groups)


def test_evidence_grouping_keeps_sheets_apart() -> None:
    evidence = wire_break_evidence_by_sheet(
        [_port("P1", 39.5, 40.5, sheet_id="S1"), _port("P2", 42.0, 43.0, sheet_id="S2")],
        [SwConnectDot(record_id="D1", sheet_id="S2", file_id="F1", handle="DOT1", x=1.0, y=1.0)],
    )

    assert set(evidence) == {"S1", "S2"}
    assert [row[0] for row in evidence["S1"].ports] == ["P1"]
    assert evidence["S2"].dots == ((1.0, 1.0),)
    assert evidence["S1"].dots == ()
