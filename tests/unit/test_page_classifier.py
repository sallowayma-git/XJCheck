from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.page_classifier import classify_pages
from dwg_audit.utils.config import DEFAULT_CONFIG


def _make_sheet(
    *,
    sheet_id: str = "S1",
    filename: str = "08 测控1开入回路图1.dwg",
    sheet_title: str = "测控1开入回路图1",
    sheet_category: str = "二次原理图",
    audit_role: str = "primary",
    audit_area_bbox: tuple[float, float, float, float] = (0.0, 0.0, 100.0, 80.0),
) -> SheetRecord:
    return SheetRecord(
        sheet_id=sheet_id,
        file_id="F1",
        filename=filename,
        sheet_order=8,
        sheet_no="08",
        sheet_title=sheet_title,
        sheet_category=sheet_category,
        audit_role=audit_role,
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=audit_area_bbox,
    )


def _make_horizontal_line(line_id: str, sheet_id: str, y: float, x1: float = 10.0, x2: float = 80.0) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id=sheet_id,
        file_id="F1",
        handle=f"H{line_id}",
        source_entity_type="LINE",
        layer="WIRE",
        start_x=x1,
        start_y=y,
        end_x=x2,
        end_y=y,
        length=x2 - x1,
        angle_deg=0.0,
        bbox_min_x=x1,
        bbox_min_y=y,
        bbox_max_x=x2,
        bbox_max_y=y,
    )


def _make_vertical_line(line_id: str, sheet_id: str, x: float, y1: float = 10.0, y2: float = 80.0) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id=sheet_id,
        file_id="F1",
        handle=f"H{line_id}",
        source_entity_type="LINE",
        layer="WIRE",
        start_x=x,
        start_y=y1,
        end_x=x,
        end_y=y2,
        length=y2 - y1,
        angle_deg=90.0,
        bbox_min_x=x,
        bbox_min_y=y1,
        bbox_max_x=x,
        bbox_max_y=y2,
    )


def _make_numeric_text(text_id: str, sheet_id: str, x: float, y: float, value: str = "101") -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id=sheet_id,
        file_id="F1",
        handle=f"TH{text_id}",
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=True,
        layer="TEXT",
        rotation_deg=0.0,
        height=2.5,
        insert_x=x,
        insert_y=y,
        bbox_min_x=x - 2,
        bbox_min_y=y - 2,
        bbox_max_x=x + 2,
        bbox_max_y=y + 2,
    )


def test_classify_pages_marks_grid_heavy_wire_diagram() -> None:
    """强网格化开入回路页应被判为 grid_heavy_wire_diagram 子型。"""
    sheet = _make_sheet()
    # 10 条水平线，y 间距 8.0（> grid_band_y_tolerance=5.0），形成 10 个行带
    lines = [_make_horizontal_line(f"L{i}", "S1", y=10.0 + i * 8.0) for i in range(10)]
    texts = [_make_numeric_text(f"T{i}", "S1", x=5.0, y=10.0 + i * 8.0) for i in range(10)]

    classifications = classify_pages([sheet], texts, lines, [], [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert classification.grid_heavy is True
    assert classification.page_type == "二次原理图"
    assert classification.page_subtype == "grid_heavy_wire_diagram"
    assert classification.audit_disposition == "audit_required"
    assert classification.route_target == "WireDiagramExtractor"
    assert classification.features["grid_band_count"] >= 8


def test_classify_pages_marks_table_like_page() -> None:
    """多 polyline + 水平线占优但不 grid_heavy 的页应判为表格型图。"""
    sheet = _make_sheet(
        filename="端子排图.dwg",
        sheet_title="端子排图",
        sheet_category=None,
        audit_role="primary",
    )
    # 5 条水平线，y 间距 15.0（5 个行带，不够 grid_heavy 但够 table_like）
    lines = [_make_horizontal_line(f"L{i}", "S1", y=10.0 + i * 15.0) for i in range(5)]
    polylines = [
        PolylineRecord(
            polyline_id=f"P{i}",
            sheet_id="S1",
            file_id="F1",
            handle=f"PH{i}",
            source_entity_type="LWPOLYLINE",
            layer="TABLE",
            vertex_count=4,
            is_closed=True,
            bbox_min_x=10.0 + i * 5,
            bbox_min_y=10.0,
            bbox_max_x=20.0 + i * 5,
            bbox_max_y=12.0,
        )
        for i in range(25)
    ]

    classifications = classify_pages([sheet], [], lines, polylines, [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert classification.table_like is True
    assert classification.page_type == "表格型图"
    assert classification.audit_disposition == "audit_required"
    assert classification.route_target == "TableExtractor"


def test_classify_pages_marks_vertical_component_page() -> None:
    """元件接线图 + 竖线占优应判为 vertical_component 子型，即使有 grid 特征。"""
    sheet = _make_sheet(
        filename="20 元件接线图2.dwg",
        sheet_title="元件接线图2",
        sheet_category="元件接线图",
    )
    # 8 条竖线，2 条水平线
    lines = [_make_vertical_line(f"V{i}", "S1", x=10.0 + i * 10.0) for i in range(8)]
    lines += [_make_horizontal_line(f"H{i}", "S1", y=5.0 + i * 30.0) for i in range(2)]

    classifications = classify_pages([sheet], [], lines, [], [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert classification.page_type == "元件接线图"
    assert classification.page_subtype == "vertical_component"
    assert classification.audit_disposition == "audit_required"
    assert classification.route_target == "ComponentDiagramExtractor"


def test_classify_pages_vertical_component_takes_priority_over_grid_heavy() -> None:
    """元件接线图 + 竖线占优即使满足 grid_heavy 条件，也应优先判为 vertical_component。"""
    sheet = _make_sheet(
        filename="20 元件接线图2.dwg",
        sheet_title="元件接线图2",
        sheet_category="元件接线图",
    )
    # 15 条竖线（vertical_ratio > 0.55），同时 10 条水平线（grid_band_count >= 8）
    lines = [_make_vertical_line(f"V{i}", "S1", x=10.0 + i * 6.0) for i in range(15)]
    lines += [_make_horizontal_line(f"H{i}", "S1", y=10.0 + i * 8.0) for i in range(10)]

    classifications = classify_pages([sheet], [], lines, [], [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    # 应判为 vertical_component，而不是 grid_heavy_wire_diagram
    assert classification.page_subtype == "vertical_component"
    assert classification.audit_disposition == "audit_required"
    assert classification.route_target == "ComponentDiagramExtractor"


def test_classify_pages_horizontal_component_takes_priority_over_grid_heavy() -> None:
    """元件接线图 + 横线占优即使满足 grid_heavy 条件，也不应退化成 wire diagram。"""
    sheet = _make_sheet(
        filename="19 元件接线图1.dwg",
        sheet_title="元件接线图1",
        sheet_category="元件接线图",
    )
    # 10 条水平线形成 grid-heavy，外加少量竖线让页面保持 component 风格
    lines = [_make_horizontal_line(f"H{i}", "S1", y=10.0 + i * 8.0) for i in range(10)]
    lines += [_make_vertical_line(f"V{i}", "S1", x=15.0 + i * 20.0, y1=12.0, y2=28.0) for i in range(3)]

    classifications = classify_pages([sheet], [], lines, [], [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert classification.page_type == "元件接线图"
    assert classification.page_subtype == "horizontal_component"
    assert classification.audit_disposition == "audit_required"
    assert classification.route_target == "ComponentDiagramExtractor"


def test_classify_pages_component_takes_priority_over_table_like_geometry() -> None:
    """元件接线图即使 polyline 很多且看起来像 table，也应优先走 ComponentDiagramExtractor。"""
    sheet = _make_sheet(
        filename="22 元件接线图2.dwg",
        sheet_title="元件接线图2",
        sheet_category="元件接线图",
    )
    lines = [_make_horizontal_line(f"H{i}", "S1", y=10.0 + i * 15.0) for i in range(6)]
    polylines = [
        PolylineRecord(
            polyline_id=f"P{i}",
            sheet_id="S1",
            file_id="F1",
            handle=f"PH{i}",
            source_entity_type="LWPOLYLINE",
            layer="TABLE",
            vertex_count=4,
            is_closed=True,
            bbox_min_x=10.0 + i * 3,
            bbox_min_y=10.0,
            bbox_max_x=20.0 + i * 3,
            bbox_max_y=12.0,
        )
        for i in range(30)
    ]

    classifications = classify_pages([sheet], [], lines, polylines, [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert classification.page_type == "元件接线图"
    assert classification.page_subtype == "horizontal_component"
    assert classification.audit_disposition == "audit_required"
    assert classification.route_target == "ComponentDiagramExtractor"


def test_classify_pages_skips_non_audit_page() -> None:
    """skip 页应判为 SkipExtractor。"""
    sheet = _make_sheet(
        filename="01 封面.dwg",
        sheet_title="封面",
        sheet_category="封面/目录",
        audit_role="skip",
    )

    classifications = classify_pages([sheet], [], [], [], [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert classification.route_target == "SkipExtractor"
    assert classification.audit_disposition == "skip_stable"


def test_classify_pages_features_contain_grid_band_count() -> None:
    """特征字典应包含 grid_band_count。"""
    sheet = _make_sheet()
    lines = [_make_horizontal_line(f"L{i}", "S1", y=10.0 + i * 8.0) for i in range(5)]

    classifications = classify_pages([sheet], [], lines, [], [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert "grid_band_count" in classification.features
    assert classification.features["grid_band_count"] == 5
    assert "horizontal_line_ratio" in classification.features


def test_classify_pages_marks_layout_page_as_classify_only() -> None:
    """背板/布置类页面默认只做分类，不进入配对审计。"""
    sheet = _make_sheet(
        filename="17 背板接线图1.dwg",
        sheet_title="背板接线图1",
        sheet_category="背板接线图",
        audit_role="secondary",
    )

    classifications = classify_pages([sheet], [], [], [], [], DEFAULT_CONFIG)
    classification = classifications["S1"]

    assert classification.page_type == "背板接线图"
    assert classification.route_target == "LayoutOnlyExtractor"
    assert classification.audit_disposition == "classify_only"
