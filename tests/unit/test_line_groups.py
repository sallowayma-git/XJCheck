from dwg_audit.audit.line_groups import build_line_groups
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG


def test_build_line_groups_bridges_gap_split_by_inline_numeric_text() -> None:
    lines = [
        LineEntity("L1", "S1", "F1", "H1", "LINE", "WIRE", 10.0, 20.0, 40.0, 20.0, 30.0, 0.0, 10.0, 20.0, 40.0, 20.0),
        LineEntity("L2", "S1", "F1", "H2", "LINE", "WIRE", 48.0, 20.1, 90.0, 20.1, 42.0, 0.1, 48.0, 20.1, 90.0, 20.1),
    ]
    sheets = [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="05 交流回路图2.dwg",
            sheet_order=5,
            sheet_no="05",
            sheet_title="交流回路图2",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="filename",
            is_primary_audit_candidate=True,
            audit_area_bbox=(0.0, 0.0, 120.0, 80.0),
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "TH1", "TEXT", "723", "723", True, "DIM", 0.0, 2.5, 44.0, 20.0, 43.0, 19.0, 47.0, 22.0)
    ]

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, texts)

    assert len(groups) == 1
    assert groups[0].start_x == 10.0
    assert groups[0].end_x == 90.0
    assert groups[0].member_line_ids == ["L1", "L2"]


def test_build_line_groups_keeps_gap_split_without_inline_numeric_text() -> None:
    lines = [
        LineEntity("L1", "S1", "F1", "H1", "LINE", "WIRE", 10.0, 20.0, 40.0, 20.0, 30.0, 0.0, 10.0, 20.0, 40.0, 20.0),
        LineEntity("L2", "S1", "F1", "H2", "LINE", "WIRE", 48.0, 20.1, 90.0, 20.1, 42.0, 0.1, 48.0, 20.1, 90.0, 20.1),
    ]
    sheets = [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="05 交流回路图2.dwg",
            sheet_order=5,
            sheet_no="05",
            sheet_title="交流回路图2",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="filename",
            is_primary_audit_candidate=True,
            audit_area_bbox=(0.0, 0.0, 120.0, 80.0),
        )
    ]

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, [])

    assert len(groups) == 2


def test_build_line_groups_bridges_gap_just_above_previous_threshold() -> None:
    lines = [
        LineEntity("L1", "S1", "F1", "H1", "LINE", "WIRE", 32.5, 20.0, 92.5, 20.0, 60.0, 0.0, 32.5, 20.0, 92.5, 20.0),
        LineEntity("L2", "S1", "F1", "H2", "LINE", "WIRE", 105.0, 20.0, 145.0, 20.0, 40.0, 0.0, 105.0, 20.0, 145.0, 20.0),
    ]
    sheets = [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="08 测控1开入回路图1.dwg",
            sheet_order=8,
            sheet_no="08",
            sheet_title="测控1开入回路图1",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="filename",
            is_primary_audit_candidate=True,
            audit_area_bbox=(0.0, 0.0, 200.0, 80.0),
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "TH1", "TEXT", "112", "112", True, "DIM", 0.0, 2.5, 98.0, 20.0, 97.0, 19.0, 101.0, 22.0)
    ]

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, texts)

    assert len(groups) == 1
    assert groups[0].start_x == 32.5
    assert groups[0].end_x == 145.0


def test_build_line_groups_uses_vertical_orientation_for_component_pages() -> None:
    lines = [
        LineEntity("L1", "S1", "F1", "H1", "LINE", "WIRE", 60.0, 80.0, 60.0, 40.0, 40.0, -90.0, 60.0, 40.0, 60.0, 80.0),
    ]
    sheets = [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="20 元件接线图2.dwg",
            sheet_order=20,
            sheet_no="20",
            sheet_title="元件接线图2",
            sheet_category="元件接线图",
            audit_role="supplemental",
            page_no_source="filename",
            is_primary_audit_candidate=True,
            audit_area_bbox=(0.0, 0.0, 120.0, 120.0),
        )
    ]

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, [])

    assert len(groups) == 1
    assert groups[0].orientation == "vertical"
    assert groups[0].start_x == 60.0
    assert groups[0].end_x == 60.0
    assert groups[0].start_y == 80.0
    assert groups[0].end_y == 40.0
