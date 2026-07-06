from dwg_audit.audit.table_extractor import extract_table_pairs
from dwg_audit.audit.table_extractor import extract_terminal_header_table_pairs
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


def _make_text(
    text_id: str,
    x: float,
    y: float,
    value: str,
    *,
    is_numeric_candidate: bool = False,
    source_block_name: str | None = None,
) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"TH{text_id}",
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=is_numeric_candidate,
        layer="TEXT",
        rotation_deg=0.0,
        height=2.5,
        insert_x=x,
        insert_y=y,
        bbox_min_x=x - 2,
        bbox_min_y=y - 2,
        bbox_max_x=x + 2,
        bbox_max_y=y + 2,
        source_block_name=source_block_name,
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


def test_extract_table_pairs_builds_header_semantic_three_column_mappings() -> None:
    sheet = _make_sheet()
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
    texts = [
        _make_text("T1", x=150, y=35, value="1-21QD"),
        _make_text("T2", x=55, y=85, value="1-21n552"),
        _make_text("T3", x=150, y=85, value="1", is_numeric_candidate=True),
        _make_text("T4", x=245, y=85, value="1-21n553"),
        _make_text("T5", x=55, y=135, value="1-21n554"),
        _make_text("T6", x=150, y=135, value="2", is_numeric_candidate=True),
        _make_text("T7", x=245, y=135, value="1-21n555"),
    ]

    pairs, mappings = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    table_mapping = mappings[0]
    assert table_mapping["three_column"] is True
    assert len(table_mapping["mappings"]) == 2
    first_row = table_mapping["mappings"][0]
    assert first_row["mapping_mode"] == "header_semantic_three_column"
    assert first_row["header_prefix"] == "1-21QD"
    assert first_row["row_number"] == 1
    assert first_row["logical_endpoint"] == "1-21QD1"
    assert first_row["left_value"] == "1-21n552"
    assert first_row["right_value"] == "1-21n553"
    assert first_row["row_number_sequence_valid"] is True

    assert len(pairs) == 4
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {
        ("1-21QD1", "1-21n552"),
        ("1-21QD1", "1-21n553"),
        ("1-21QD2", "1-21n554"),
        ("1-21QD2", "1-21n555"),
    }
    assert all(pair.evidence["source"] == "table_mapping" for pair in pairs)


def test_extract_terminal_header_table_pairs_builds_supplemental_mappings() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 260.0, 280.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "23 右侧端子图1.dwg"
    texts = [
        _make_text("H", 175.5, 276.0, "1-21QD"),
        _make_text("E1", 156.0, 268.5, "1-21n116"),
        _make_text("R1", 179.25, 268.5, "1", is_numeric_candidate=True),
        _make_text("N1", 185.0, 270.0, "未定义EBF8:2_08 测控1开入回路图1"),
        _make_text("E2", 156.0, 263.5, "1-21n117"),
        _make_text("R2", 179.25, 263.5, "2", is_numeric_candidate=True),
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    assert len(mappings) == 1
    assert mappings[0]["three_column"] is True
    assert mappings[0]["mappings"][0]["mapping_mode"] == "terminal_header_table"
    assert mappings[0]["mappings"][0]["logical_endpoint"] == "1-21QD1"
    assert mappings[0]["mappings"][0]["left_value"] == "1-21n116"
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-21QD1", "1-21n116"),
        ("1-21QD2", "1-21n117"),
    }
    assert all(pair.status == "pass" for pair in pairs)
    assert all(pair.evidence["source"] == "table_mapping" for pair in pairs)
    assert pairs[0].evidence["table_mapping"]["mapping_mode"] == "terminal_header_table"


def test_extract_terminal_header_table_pairs_skips_sparse_header_like_group() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 260.0, 280.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "ordinary terminals.dwg"
    texts = [
        _make_text("H", 175.5, 276.0, "1-21QD"),
        _make_text("R1", 179.25, 268.5, "1", is_numeric_candidate=True),
        _make_text("E1", 156.0, 268.5, "1-21n116"),
        _make_text("R2", 179.25, 263.5, "2", is_numeric_candidate=True),
        _make_text("N1", 130.0, 263.0, "普通端子说明"),
        _make_text("H2", 80.0, 230.0, "2-31QA"),
        _make_text("E2", 20.0, 220.0, "1-21n117"),
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    assert pairs == []
    assert mappings == []


def test_extract_table_pairs_prefers_numeric_text_when_cell_contains_note() -> None:
    sheet = _make_sheet()
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
    texts = [
        _make_numeric_text("T1", x=55, y=35, value="101"),
        _make_text("T2", x=145, y=30, value="NOTE"),
        _make_numeric_text("T3", x=150, y=35, value="102"),
        _make_numeric_text("T4", x=245, y=35, value="103"),
    ]

    pairs, mappings = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    assert mappings[0]["mappings"][0]["mapping_mode"] == "numeric_three_column"
    assert len(pairs) == 1
    assert (pairs[0].left_value, pairs[0].right_value) == ("102", "103")


def test_extract_table_pairs_header_semantic_ignores_non_terminal_note_side() -> None:
    sheet = _make_sheet()
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
    texts = [
        _make_text("T1", x=150, y=35, value="1-21QD"),
        _make_text("T2", x=55, y=85, value="备注"),
        _make_text("T3", x=150, y=85, value="1", is_numeric_candidate=True),
        _make_text("T4", x=245, y=85, value="1-21n553"),
        _make_text("T5", x=55, y=135, value="1-21n554"),
        _make_text("T6", x=150, y=135, value="2", is_numeric_candidate=True),
        _make_text("T7", x=245, y=135, value="1-21n555"),
    ]

    pairs, mappings = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    assert len(mappings[0]["mappings"]) == 2
    assert mappings[0]["mappings"][0]["left_value"] is None
    assert mappings[0]["mappings"][0]["right_value"] == "1-21n553"
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {
        ("1-21QD1", "1-21n553"),
        ("1-21QD2", "1-21n554"),
        ("1-21QD2", "1-21n555"),
    }


def test_extract_table_pairs_falls_back_to_numeric_mode_when_header_sequence_invalid() -> None:
    sheet = _make_sheet()
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
    texts = [
        _make_numeric_text("T1", x=55, y=35, value="100"),
        _make_text("T2", x=145, y=30, value="1-21QD"),
        _make_numeric_text("T3", x=150, y=35, value="101"),
        _make_numeric_text("T4", x=245, y=35, value="102"),
        _make_numeric_text("T5", x=55, y=85, value="200"),
        _make_numeric_text("T6", x=150, y=85, value="103"),
        _make_numeric_text("T7", x=245, y=85, value="104"),
    ]

    pairs, mappings = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    assert mappings[0]["mappings"][0]["mapping_mode"] == "numeric_three_column"
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {("101", "102"), ("103", "104")}


def test_extract_table_pairs_builds_backplate_virtual_table_mappings() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 300.0, 260.0))
    sheet.filename = "20 非电量保护背板图.dwg"
    sheet.sheet_title = "非电量保护背板图"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"

    texts = [
        _make_text(
            "H1",
            x=213.0,
            y=243.75,
            value="NKR308A(非电量选配)",
            source_block_name="WBH-814E-E1SA-101",
        ),
        _make_text("R1", x=208.75, y=238.75, value="01", is_numeric_candidate=True, source_block_name="WBH-814E-E1SA-101"),
        _make_text("R2", x=233.75, y=238.75, value="02", is_numeric_candidate=True, source_block_name="WBH-814E-E1SA-101"),
        _make_text("E1", x=199.0, y=238.5, value="5FD15"),
        _make_text("E2", x=238.5, y=238.5, value="5FD16"),
        _make_text("N1", x=213.0, y=239.0, value="调压重瓦斯开入", source_block_name="WBH-814E-E1SA-101"),
    ]

    pairs, mappings = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    assert mappings[0]["three_column"] is False
    assert mappings[0]["mappings"][0]["mapping_mode"] == "backplate_virtual_table"
    assert mappings[0]["mappings"][0]["header_prefix"] == "NKR308A"
    assert mappings[0]["mappings"][0]["raw_header_text"] == "NKR308A(非电量选配)"
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {
        ("NKR308A-1", "5FD15"),
        ("NKR308A-2", "5FD16"),
    }
    assert all(pair.evidence["source"] == "table_mapping" for pair in pairs)
    assert all(pair.evidence["pair_kind"] == "table_mapping" for pair in pairs)
    assert {pair.pair_kind for pair in pairs} == {"table_mapping"}
    assert pairs[0].evidence["table_mapping"]["source_block_name"] == "WBH-814E-E1SA-101"
