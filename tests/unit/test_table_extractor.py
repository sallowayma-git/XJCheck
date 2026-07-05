from dwg_audit.audit.table_extractor import extract_table_pairs
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG


def _make_sheet(
    *,
    sheet_id: str = "S1",
    audit_area_bbox: tuple[float, float, float, float] = (0.0, 0.0, 300.0, 200.0),
) -> SheetRecord:
    return SheetRecord(
        sheet_id=sheet_id,
        file_id="F1",
        filename="端子排图.dwg",
        sheet_order=1,
        sheet_no="01",
        sheet_title="端子排图",
        sheet_category=None,
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=audit_area_bbox,
    )


def _make_h_grid_line(line_id: str, y: float, x1: float = 10.0, x2: float = 290.0) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{line_id}",
        source_entity_type="LINE",
        layer="TABLE",
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


def _make_v_grid_line(line_id: str, x: float, y1: float = 10.0, y2: float = 190.0) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{line_id}",
        source_entity_type="LINE",
        layer="TABLE",
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


def _make_numeric_text(text_id: str, x: float, y: float, value: str) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
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


def test_extract_table_pairs_builds_three_column_mappings() -> None:
    """三列表格应生成中列关联左右列的高置信 Pair。"""
    sheet = _make_sheet()
    # 3 行 3 列网格：水平线 y=10, 60, 110, 160；竖直线 x=10, 100, 200, 290
    lines = [
        _make_h_grid_line("H1", y=10.0),
        _make_h_grid_line("H2", y=60.0),
        _make_h_grid_line("H3", y=110.0),
        _make_h_grid_line("H4", y=160.0),
        _make_v_grid_line("V1", x=10.0),
        _make_v_grid_line("V2", x=100.0),
        _make_v_grid_line("V3", x=200.0),
        _make_v_grid_line("V4", x=290.0),
    ]
    # 2 行数字：左列 101/201，中列 102/202，右列 103/203
    texts = [
        _make_numeric_text("T1", x=55, y=35, value="101"),
        _make_numeric_text("T2", x=150, y=35, value="102"),
        _make_numeric_text("T3", x=245, y=35, value="103"),
        _make_numeric_text("T4", x=55, y=85, value="201"),
        _make_numeric_text("T5", x=150, y=85, value="202"),
        _make_numeric_text("T6", x=245, y=85, value="203"),
    ]

    pairs, mappings = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    mapping = mappings[0]
    assert mapping["three_column"] is True
    assert mapping["row_count"] == 3  # 4 条水平线形成 3 个单元格行
    assert mapping["col_count"] == 3  # 4 条竖直线形成 3 个单元格列
    assert len(mapping["mappings"]) == 2  # 2 行有数字，1 行空

    # 每行应生成一个 Pair：中列 -> 右列
    assert len(pairs) == 2
    pair = pairs[0]
    assert pair.status == "pass"
    assert pair.confidence >= 0.92
    assert pair.evidence["source"] == "table_mapping"
    assert pair.confidence_bucket == "high"
    # 第一行：中列 102 -> 右列 103
    assert pair.left_value == "102"
    assert pair.right_value == "103"


def test_extract_table_pairs_returns_empty_for_non_grid_page() -> None:
    """没有网格线的页不应生成表格 Pair。"""
    sheet = _make_sheet()
    texts = [_make_numeric_text("T1", x=50, y=50, value="101")]
    lines = []  # 没有网格线

    pairs, mappings = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert pairs == []
    assert mappings == []


def test_extract_table_pairs_skips_non_three_column_tables() -> None:
    """非三列表格应只记录结构，不生成 Pair。"""
    sheet = _make_sheet()
    # 4 列网格（5 条竖直线）
    lines = [
        _make_h_grid_line("H1", y=10.0),
        _make_h_grid_line("H2", y=60.0),
        _make_h_grid_line("H3", y=110.0),
        _make_v_grid_line("V1", x=10.0),
        _make_v_grid_line("V2", x=80.0),
        _make_v_grid_line("V3", x=150.0),
        _make_v_grid_line("V4", x=220.0),
        _make_v_grid_line("V5", x=290.0),
    ]
    texts = [_make_numeric_text("T1", x=45, y=35, value="101")]

    pairs, mappings = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    # 5 条竖直线形成 4 个单元格列，不是三列，不应生成 Pair
    assert pairs == []
    if mappings:
        assert mappings[0]["three_column"] is False


def test_extract_table_pairs_pair_has_no_line_group_id() -> None:
    """表格 Pair 的 line_group_id 应为 None（它不是来自线组）。"""
    sheet = _make_sheet()
    lines = [
        _make_h_grid_line("H1", y=10.0),
        _make_h_grid_line("H2", y=60.0),
        _make_h_grid_line("H3", y=110.0),
        _make_v_grid_line("V1", x=10.0),
        _make_v_grid_line("V2", x=100.0),
        _make_v_grid_line("V3", x=200.0),
        _make_v_grid_line("V4", x=290.0),
    ]
    texts = [
        _make_numeric_text("T1", x=55, y=35, value="101"),
        _make_numeric_text("T2", x=150, y=35, value="102"),
        _make_numeric_text("T3", x=245, y=35, value="103"),
    ]

    pairs, _ = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert len(pairs) == 1
    assert pairs[0].line_group_id is None
