from dwg_audit.audit.line_groups import build_line_groups
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import PageClassification
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


def test_build_line_groups_bridges_wide_gap_when_same_inline_number_spans_it() -> None:
    lines = [
        LineEntity("L1", "S1", "F1", "H1", "LINE", "CONNECT", 152.5, 130.0, 187.5, 130.0, 35.0, 0.0, 152.5, 130.0, 187.5, 130.0),
        LineEntity("L2", "S1", "F1", "H2", "LINE", "CONNECT", 206.25, 130.0, 282.5, 130.0, 76.25, 0.0, 206.25, 130.0, 282.5, 130.0),
    ]
    sheets = [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="05 信号回路图.dwg",
            sheet_order=5,
            sheet_no="05",
            sheet_title="信号回路图",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="filename",
            is_primary_audit_candidate=True,
            audit_area_bbox=(0.0, 0.0, 320.0, 220.0),
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "TH1", "TEXT", "111", "111", True, "DIM", 0.0, 2.5, 186.25, 130.66, 184.0, 129.0, 190.0, 133.0)
    ]

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, texts)

    assert len(groups) == 1
    assert groups[0].start_x == 152.5
    assert groups[0].end_x == 282.5
    assert groups[0].member_line_ids == ["L1", "L2"]

    # The same 18.75-unit gap on a non-signal sheet stays split.
    sheets[0].filename = "04 直流回路图.dwg"
    sheets[0].sheet_title = "直流回路图"
    strict_groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, texts)
    assert len(strict_groups) == 2


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


def test_build_line_groups_filters_component_vertical_length_outlier() -> None:
    lines = [
        LineEntity("L0", "S1", "F1", "H0", "LINE", "WIRE", 25.0, 290.0, 25.0, 5.0, 285.0, -90.0, 25.0, 5.0, 25.0, 290.0),
        LineEntity("L1", "S1", "F1", "H1", "LINE", "WIRE", 60.0, 80.0, 60.0, 40.0, 40.0, -90.0, 60.0, 40.0, 60.0, 80.0),
        LineEntity("L2", "S1", "F1", "H2", "LINE", "WIRE", 100.0, 80.0, 100.0, 40.0, 40.0, -90.0, 100.0, 40.0, 100.0, 80.0),
        LineEntity("L3", "S1", "F1", "H3", "LINE", "WIRE", 140.0, 80.0, 140.0, 40.0, 40.0, -90.0, 140.0, 40.0, 140.0, 80.0),
        LineEntity("L4", "S1", "F1", "H4", "LINE", "WIRE", 180.0, 80.0, 180.0, 40.0, 40.0, -90.0, 180.0, 40.0, 180.0, 80.0),
        LineEntity("L5", "S1", "F1", "H5", "LINE", "WIRE", 220.0, 80.0, 220.0, 40.0, 40.0, -90.0, 220.0, 40.0, 220.0, 80.0),
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
            audit_area_bbox=(0.0, 0.0, 240.0, 300.0),
        )
    ]

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, [])

    assert len(groups) == 5
    assert all("L0" not in group.member_line_ids for group in groups)


def test_build_line_groups_uses_grid_orientation_for_grid_heavy_page() -> None:
    """grid_heavy 页应走 grid 行带聚类，输出 orientation=grid 的 LineGroup。"""
    from dwg_audit.domain.models import PageClassification

    lines = [
        LineEntity(f"L{i}", "S1", "F1", f"H{i}", "LINE", "WIRE", 10.0, y, 80.0, y, 70.0, 0.0, 10.0, y, 80.0, y)
        for i, y in enumerate([10.0, 18.0, 26.0, 34.0, 42.0, 50.0, 58.0, 66.0, 74.0, 82.0])
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
            audit_area_bbox=(0.0, 0.0, 100.0, 100.0),
        )
    ]
    classification = PageClassification(
        sheet_id="S1",
        page_type="二次原理图",
        page_subtype="grid_heavy_wire_diagram",
        page_type_confidence=0.88,
        table_like=False,
        grid_heavy=True,
        route_target="WireDiagramExtractor",
        features={"grid_band_count": 10},
    )

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, [], classifications={"S1": classification})

    assert len(groups) > 0
    assert all(group.orientation == "grid" for group in groups)
    # grid 行带聚类应把同一 y 值的线合并，row_band_id 不为空
    assert all(group.row_band_id is not None for group in groups)


def test_build_line_groups_grid_bridges_inline_numeric_split() -> None:
    """grid 模式下行带聚类应能桥接被 inline 数字切开的同一根线。"""
    from dwg_audit.domain.models import PageClassification

    lines = [
        LineEntity("L1", "S1", "F1", "H1", "LINE", "WIRE", 10.0, 20.0, 40.0, 20.0, 30.0, 0.0, 10.0, 20.0, 40.0, 20.0),
        LineEntity("L2", "S1", "F1", "H2", "LINE", "WIRE", 48.0, 20.1, 90.0, 20.1, 42.0, 0.1, 48.0, 20.1, 90.0, 20.1),
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
            audit_area_bbox=(0.0, 0.0, 100.0, 100.0),
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "TH1", "TEXT", "723", "723", True, "DIM", 0.0, 2.5, 44.0, 20.0, 43.0, 19.0, 47.0, 22.0)
    ]
    # 多条 y 间距大的水平线让 grid_band_count >= 8
    extra_lines = [
        LineEntity(f"X{i}", "S1", "F1", f"HX{i}", "LINE", "WIRE", 10.0, y, 80.0, y, 70.0, 0.0, 10.0, y, 80.0, y)
        for i, y in enumerate([30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 95.0])
    ]
    all_lines = lines + extra_lines
    classification = PageClassification(
        sheet_id="S1",
        page_type="二次原理图",
        page_subtype="grid_heavy_wire_diagram",
        page_type_confidence=0.88,
        table_like=False,
        grid_heavy=True,
        route_target="WireDiagramExtractor",
        features={"grid_band_count": 10},
    )

    groups = build_line_groups(all_lines, sheets, DEFAULT_CONFIG, texts, classifications={"S1": classification})

    # 应存在一个包含 L1 和 L2 的 grid group（被 inline 数字桥接）
    bridged = [g for g in groups if "L1" in g.member_line_ids and "L2" in g.member_line_ids]
    assert len(bridged) == 1
    assert bridged[0].orientation == "grid"


def test_build_line_groups_grid_bridges_inline_numeric_split_when_bbox_overlaps_gap() -> None:
    """DWG TEXT insert point may sit on the left segment while its bbox spans into the split gap."""
    from dwg_audit.domain.models import PageClassification

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
            audit_area_bbox=(0.0, 0.0, 180.0, 120.0),
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "TH1", "TEXT", "114", "114", True, "DIM", 0.0, 2.5, 90.6, 20.6, 90.6, 19.0, 95.3, 22.0)
    ]
    extra_lines = [
        LineEntity(f"X{i}", "S1", "F1", f"HX{i}", "LINE", "WIRE", 10.0, y, 80.0, y, 70.0, 0.0, 10.0, y, 80.0, y)
        for i, y in enumerate([30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0])
    ]
    classification = PageClassification(
        sheet_id="S1",
        page_type="二次原理图",
        page_subtype="grid_heavy_wire_diagram",
        page_type_confidence=0.88,
        table_like=False,
        grid_heavy=True,
        route_target="WireDiagramExtractor",
        features={"grid_band_count": 10},
    )

    groups = build_line_groups(lines + extra_lines, sheets, DEFAULT_CONFIG, texts, classifications={"S1": classification})

    bridged = [g for g in groups if "L1" in g.member_line_ids and "L2" in g.member_line_ids]
    assert len(bridged) == 1
    assert bridged[0].start_x == 32.5
    assert bridged[0].end_x == 145.0
    assert bridged[0].orientation == "grid"


def test_build_line_groups_keeps_component_page_out_of_grid_mode() -> None:
    from dwg_audit.domain.models import PageClassification

    lines = [
        LineEntity("L1", "S1", "F1", "H1", "LINE", "WIRE", 10.0, 20.0, 40.0, 20.0, 30.0, 0.0, 10.0, 20.0, 40.0, 20.0),
        LineEntity("L2", "S1", "F1", "H2", "LINE", "WIRE", 48.0, 20.1, 90.0, 20.1, 42.0, 0.1, 48.0, 20.1, 90.0, 20.1),
        LineEntity("L3", "S1", "F1", "H3", "LINE", "WIRE", 10.0, 40.0, 80.0, 40.0, 70.0, 0.0, 10.0, 40.0, 80.0, 40.0),
        LineEntity("L4", "S1", "F1", "H4", "LINE", "WIRE", 10.0, 50.0, 80.0, 50.0, 70.0, 0.0, 10.0, 50.0, 80.0, 50.0),
        LineEntity("L5", "S1", "F1", "H5", "LINE", "WIRE", 10.0, 60.0, 80.0, 60.0, 70.0, 0.0, 10.0, 60.0, 80.0, 60.0),
        LineEntity("L6", "S1", "F1", "H6", "LINE", "WIRE", 10.0, 70.0, 80.0, 70.0, 70.0, 0.0, 10.0, 70.0, 80.0, 70.0),
        LineEntity("L7", "S1", "F1", "H7", "LINE", "WIRE", 10.0, 80.0, 80.0, 80.0, 70.0, 0.0, 10.0, 80.0, 80.0, 80.0),
        LineEntity("L8", "S1", "F1", "H8", "LINE", "WIRE", 10.0, 90.0, 80.0, 90.0, 70.0, 0.0, 10.0, 90.0, 80.0, 90.0),
    ]
    sheets = [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="19 元件接线图1.dwg",
            sheet_order=19,
            sheet_no="19",
            sheet_title="元件接线图1",
            sheet_category="元件接线图",
            audit_role="supplemental",
            page_no_source="filename",
            is_primary_audit_candidate=True,
            audit_area_bbox=(0.0, 0.0, 100.0, 100.0),
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "TH1", "TEXT", "2", "2", True, "DIM", 0.0, 2.5, 44.0, 20.0, 43.0, 19.0, 47.0, 22.0)
    ]
    classification = PageClassification(
        sheet_id="S1",
        page_type="元件接线图",
        page_subtype="horizontal_component",
        page_type_confidence=0.88,
        table_like=False,
        grid_heavy=True,
        route_target="ComponentDiagramExtractor",
        features={"grid_band_count": 8},
    )

    groups = build_line_groups(lines, sheets, DEFAULT_CONFIG, texts, classifications={"S1": classification})

    assert len(groups) > 0
    assert all(group.orientation == "horizontal" for group in groups)


def _phase180_sheet(*, category: str = "二次原理图", filename: str = "22 录波信号输出回路图.dwg") -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename=filename,
        sheet_order=22,
        sheet_no="22",
        sheet_title=filename.removesuffix(".dwg"),
        sheet_category=category,
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(0.0, 0.0, 450.0, 450.0),
    )


def _phase180_grid_classification() -> PageClassification:
    return PageClassification(
        sheet_id="S1",
        page_type="二次原理图",
        page_subtype="grid_heavy_wire_diagram",
        page_type_confidence=0.95,
        table_like=False,
        grid_heavy=True,
        route_target="WireDiagramExtractor",
        features={"grid_band_count": 10},
    )


def test_build_line_groups_keeps_reversed_distant_collinear_islands_split() -> None:
    lines = [
        LineEntity("R1", "S1", "F1", "HR1", "LINE", "0", 362.5, 80.0, 392.5, 80.0, 30.0, 0.0, 362.5, 80.0, 392.5, 80.0),
        LineEntity("R2", "S1", "F1", "HR2", "LINE", "0", 362.5, 80.0, 392.5, 80.0, 30.0, 0.0, 362.5, 80.0, 392.5, 80.0),
        LineEntity("L1", "S1", "F1", "HL1", "LINE", "CONNECT", 114.744, 80.0015, 144.744, 80.0015, 30.0, 0.0, 114.744, 80.0015, 144.744, 80.0015),
    ]

    groups = sorted(build_line_groups(lines, [_phase180_sheet()], DEFAULT_CONFIG, []), key=lambda group: group.start_x)

    assert len(groups) == 2
    assert groups[0].member_line_ids == ["L1"]
    assert groups[0].length == 30.0
    assert groups[1].member_line_ids == ["R1", "R2"]
    assert groups[1].length == 30.0


def test_build_line_groups_merges_reversed_overlap_and_nearby_gap() -> None:
    for left_end_axis in (44.0, 60.0):
        lines = [
            LineEntity("R1", "S1", "F1", "HR1", "LINE", "WIRE", 48.0, 20.0, 90.0, 20.0, 42.0, 0.0, 48.0, 20.0, 90.0, 20.0),
            LineEntity("L1", "S1", "F1", "HL1", "LINE", "WIRE", 10.0, 20.0015, left_end_axis, 20.0015, left_end_axis - 10.0, 0.0, 10.0, 20.0015, left_end_axis, 20.0015),
        ]

        groups = build_line_groups(lines, [_phase180_sheet()], DEFAULT_CONFIG, [])

        assert len(groups) == 1
        assert groups[0].start_x == 10.0
        assert groups[0].end_x == 90.0


def test_build_line_groups_bridges_reversed_gap_with_inline_numeric_text() -> None:
    lines = [
        LineEntity("R1", "S1", "F1", "HR1", "LINE", "WIRE", 48.0, 20.0, 90.0, 20.0, 42.0, 0.0, 48.0, 20.0, 90.0, 20.0),
        LineEntity("L1", "S1", "F1", "HL1", "LINE", "WIRE", 10.0, 20.0015, 40.0, 20.0015, 30.0, 0.0, 10.0, 20.0015, 40.0, 20.0015),
    ]
    texts = [
        TextItem("T1", "S1", "F1", "TH1", "TEXT", "723", "723", True, "DIM", 0.0, 2.5, 44.0, 20.0, 43.0, 19.0, 47.0, 22.0)
    ]

    groups = build_line_groups(lines, [_phase180_sheet()], DEFAULT_CONFIG, texts)

    assert len(groups) == 1
    assert groups[0].start_x == 10.0
    assert groups[0].end_x == 90.0
    assert set(groups[0].member_line_ids) == {"L1", "R1"}


def test_build_line_groups_keeps_reversed_vertical_islands_split() -> None:
    lines = [
        LineEntity("T1", "S1", "F1", "HT1", "LINE", "0", 60.0, 392.5, 60.0, 362.5, 30.0, -90.0, 60.0, 362.5, 60.0, 392.5),
        LineEntity("T2", "S1", "F1", "HT2", "LINE", "0", 60.0, 392.5, 60.0, 362.5, 30.0, -90.0, 60.0, 362.5, 60.0, 392.5),
        LineEntity("B1", "S1", "F1", "HB1", "LINE", "CONNECT", 60.0015, 144.744, 60.0015, 114.744, 30.0, -90.0, 60.0015, 114.744, 60.0015, 144.744),
    ]
    sheet = _phase180_sheet(category="元件接线图", filename="20 元件接线图2.dwg")

    groups = sorted(build_line_groups(lines, [sheet], DEFAULT_CONFIG, []), key=lambda group: group.end_y)

    assert len(groups) == 2
    assert groups[0].member_line_ids == ["B1"]
    assert groups[1].member_line_ids == ["T1", "T2"]


def test_build_line_groups_grid_keeps_distant_collinear_islands_split() -> None:
    lines = [
        LineEntity("R1", "S1", "F1", "HR1", "LINE", "0", 362.5, 80.0, 392.5, 80.0, 30.0, 0.0, 362.5, 80.0, 392.5, 80.0),
        LineEntity("R2", "S1", "F1", "HR2", "LINE", "0", 362.5, 80.0, 392.5, 80.0, 30.0, 0.0, 362.5, 80.0, 392.5, 80.0),
        LineEntity("L1", "S1", "F1", "HL1", "LINE", "CONNECT", 114.744, 80.0015, 144.744, 80.0015, 30.0, 0.0, 114.744, 80.0015, 144.744, 80.0015),
    ]

    groups = sorted(
        build_line_groups(
            lines,
            [_phase180_sheet()],
            DEFAULT_CONFIG,
            [],
            classifications={"S1": _phase180_grid_classification()},
        ),
        key=lambda group: group.start_x,
    )

    assert len(groups) == 2
    assert all(group.orientation == "grid" for group in groups)
    assert groups[0].member_line_ids == ["L1"]
    assert groups[1].member_line_ids == ["R1", "R2"]
