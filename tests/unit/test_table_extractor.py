from dwg_audit.audit.table_extractor import extract_table_pairs
from dwg_audit.audit.table_extractor import extract_component_panel_port_table_pairs
from dwg_audit.audit.table_extractor import extract_terminal_header_table_pairs
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
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


def _make_diagonal_line(
    line_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> LineEntity:
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{line_id}",
        source_entity_type="LINE",
        layer="TABLE",
        start_x=x1,
        start_y=y1,
        end_x=x2,
        end_y=y2,
        length=length,
        angle_deg=21.8,
        bbox_min_x=min(x1, x2),
        bbox_min_y=min(y1, y2),
        bbox_max_x=max(x1, x2),
        bbox_max_y=max(y1, y2),
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


def _make_component_panel_fixture(
    *,
    missing_slot4_port: int | None = None,
    include_instance: bool = True,
) -> tuple[SheetRecord, list[TextItem], list[LineEntity], list[LineGroup]]:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 260.0, 220.0))
    sheet.filename = "14 元件接线图2.dwg"
    sheet.sheet_title = "COMPONENT WIRING"
    sheet.sheet_category = "元件接线图"
    source = "RENAMED-PORT-TABLE"
    texts = [
        _make_text("MODEL", x=125.0, y=200.0, value=source),
    ]
    if include_instance:
        texts.append(_make_text("INSTANCE", x=95.0, y=200.0, value="1-26n"))
    lines: list[LineEntity] = []
    groups: list[LineGroup] = []
    for slot, title, x, td_start in (
        (4, "RS485", 60.0, 39),
        (5, "TTL", 120.0, 87),
        (6, "RS232", 180.0, 135),
    ):
        texts.extend(
            [
                _make_text(
                    f"SLOT-{slot}",
                    x=x,
                    y=185.0,
                    value=str(slot),
                    is_numeric_candidate=True,
                    source_block_name=source,
                ),
                _make_text(
                    f"TITLE-{slot}",
                    x=x + 7.0,
                    y=185.0,
                    value=title,
                    source_block_name=source,
                ),
            ]
        )
        for offset, port in enumerate(range(27, 33)):
            if slot == 4 and port == missing_slot4_port:
                continue
            y = 160.0 - offset * 5.0
            endpoint_x = x + 20.0
            row_id = f"ROW-{slot}-{port}"
            endpoint_id = f"END-{slot}-{port}"
            line_id = f"LINE-{slot}-{port}"
            group_id = f"GROUP-{slot}-{port}"
            texts.extend(
                [
                    _make_text(
                        row_id,
                        x=x,
                        y=y,
                        value=f"{port:02d}",
                        is_numeric_candidate=True,
                        source_block_name=source,
                    ),
                    _make_text(
                        endpoint_id,
                        x=endpoint_x,
                        y=y,
                        value=f"1-26TD{td_start + offset}",
                    ),
                ]
            )
            line_y = y - 1.0
            lines.append(
                LineEntity(
                    line_id=line_id,
                    sheet_id="S1",
                    file_id="F1",
                    handle=f"HPANEL:{slot}:{port}",
                    source_entity_type="LINE",
                    layer="0",
                    start_x=x,
                    start_y=line_y,
                    end_x=endpoint_x - 1.0,
                    end_y=line_y,
                    length=endpoint_x - x - 1.0,
                    angle_deg=0.0,
                    bbox_min_x=x,
                    bbox_min_y=line_y,
                    bbox_max_x=endpoint_x - 1.0,
                    bbox_max_y=line_y,
                    source_block_name=source,
                )
            )
            groups.append(
                LineGroup(
                    line_group_id=group_id,
                    sheet_id="S1",
                    file_id="F1",
                    start_x=x,
                    start_y=line_y,
                    end_x=endpoint_x - 1.0,
                    end_y=line_y,
                    length=endpoint_x - x - 1.0,
                    wire_candidate_score=0.85,
                    member_line_ids=[line_id],
                    layer_hints=["0"],
                    orientation="horizontal",
                    row_band_id=None,
                )
            )
    for suffix, y in (("LOW", 184.0), ("HIGH", 189.0)):
        line_id = f"HEADER-{suffix}"
        group_id = f"HEADER-GROUP-{suffix}"
        lines.append(
            LineEntity(
                line_id=line_id,
                sheet_id="S1",
                file_id="F1",
                handle=f"HPANEL:HEADER:{suffix}",
                source_entity_type="LINE",
                layer="0",
                start_x=50.0,
                start_y=y,
                end_x=90.0,
                end_y=y,
                length=40.0,
                angle_deg=0.0,
                bbox_min_x=50.0,
                bbox_min_y=y,
                bbox_max_x=90.0,
                bbox_max_y=y,
                source_block_name=source,
            )
        )
        groups.append(
            LineGroup(
                line_group_id=group_id,
                sheet_id="S1",
                file_id="F1",
                start_x=50.0,
                start_y=y,
                end_x=90.0,
                end_y=y,
                length=40.0,
                wire_candidate_score=0.55,
                member_line_ids=[line_id],
                layer_hints=["0"],
                orientation="horizontal",
                row_band_id=None,
            )
        )
    return sheet, texts, lines, groups


def test_component_panel_port_table_emits_scoped_independent_mappings() -> None:
    sheet, texts, lines, groups = _make_component_panel_fixture()

    pairs, tables, consumed = extract_component_panel_port_table_pairs(
        texts, lines, groups, [sheet]
    )

    assert len(pairs) == 18
    assert len(consumed) == 20
    assert {"HEADER-GROUP-LOW", "HEADER-GROUP-HIGH"} <= consumed
    assert tables[0]["mapping_semantics"] == (
        "independent_external_ports_no_internal_connectivity"
    )
    values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("1-26n432", "1-26TD44") in values
    assert ("1-26n532", "1-26TD92") in values
    assert ("1-26n632", "1-26TD140") in values
    assert {pair.pair_kind for pair in pairs} == {"component_mapping"}
    assert all(pair.evidence["ordinary_pair_eligible"] is False for pair in pairs)
    assert all(pair.evidence["electrical_union_eligible"] is False for pair in pairs)


def test_component_panel_port_table_rejects_a_sparse_slot() -> None:
    sheet, texts, lines, groups = _make_component_panel_fixture(
        missing_slot4_port=30
    )

    pairs, _, consumed = extract_component_panel_port_table_pairs(
        texts, lines, groups, [sheet]
    )

    assert len(pairs) == 12
    assert not any(str(pair.left_value).startswith("1-26n4") for pair in pairs)
    assert not any(group_id.startswith("GROUP-4-") for group_id in consumed)


def test_component_panel_port_table_requires_scoped_instance_beside_model() -> None:
    sheet, texts, lines, groups = _make_component_panel_fixture(
        include_instance=False
    )

    pairs, tables, consumed = extract_component_panel_port_table_pairs(
        texts, lines, groups, [sheet]
    )

    assert pairs == []
    assert tables == []
    assert consumed == set()


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


def test_extract_output_contact_matrix_maps_only_full_cell_diagonals() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 200.0, 160.0))
    sheet.page_subtype = "output_contact_matrix_table"
    rows = [10.0, 40.0, 70.0, 100.0]
    cols = [10.0, 50.0, 90.0, 130.0, 170.0]
    lines = [
        _make_h_grid_line(f"MH{index}", y=value, x1=cols[0], x2=cols[-1])
        for index, value in enumerate(rows)
    ] + [
        _make_v_grid_line(f"MV{index}", x=value, y1=rows[0], y2=rows[-1])
        for index, value in enumerate(cols)
    ]
    lines += [
        _make_diagonal_line("MARK1", 130.0, 70.0, 170.0, 100.0),
        _make_diagonal_line("MARK1_DUP", 130.0, 70.0, 170.0, 100.0),
        _make_diagonal_line("MARK2", 130.0, 40.0, 170.0, 70.0),
        # Same geometry in an unlabeled row is not a resolved matrix fact.
        _make_diagonal_line("UNLABELLED", 130.0, 10.0, 170.0, 40.0),
        # A short decoration inside a labelled cell must not count as a mark.
        _make_diagonal_line("SHORT", 140.0, 80.0, 150.0, 88.0),
    ]
    texts = [
        _make_text("ROW1", 20.0, 85.0, "出口1 Output 1"),
        _make_text("OBJ1", 60.0, 85.0, "跳GCB"),
        _make_text("CLP1", 100.0, 85.0, "1CLP1"),
        _make_text("ROW2", 20.0, 55.0, "出口2 Output 2"),
        _make_text("CLP2", 100.0, 55.0, "1CLP2"),
        _make_text("KLP", 145.0, 106.0, "1KLP7"),
        _make_text("FUNC", 145.0, 118.0, "负序过负荷"),
        _make_text("SUB", 145.0, 110.0, "信号 Signal"),
    ]

    pairs, tables = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert pairs == []
    assert len(tables) == 1
    assert tables[0]["matrix_table"] is True
    assert tables[0]["mapping_semantics"] == "non_conductive_contact_matrix"
    assert tables[0]["marked_cell_count"] == 2
    mappings = tables[0]["mappings"]
    assert {mapping["row_strap"] for mapping in mappings} == {"1CLP1", "1CLP2"}
    assert all(mapping["column_strap"] == "1KLP7" for mapping in mappings)
    assert all(mapping["is_electrical_connectivity"] is False for mapping in mappings)
    assert len(mappings[0]["mark_line_ids"]) == 2
    assert set(tables[0]["structural_text_ids"]) == {
        "ROW1",
        "OBJ1",
        "CLP1",
        "ROW2",
        "CLP2",
        "KLP",
        "FUNC",
        "SUB",
    }


def test_extract_output_contact_matrix_records_empty_matrix_without_fake_pairs() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 200.0, 160.0))
    sheet.page_subtype = "output_contact_matrix_table"
    rows = [10.0, 40.0, 70.0, 100.0]
    cols = [10.0, 50.0, 90.0, 130.0, 170.0]
    lines = [
        _make_h_grid_line(f"EH{index}", y=value, x1=cols[0], x2=cols[-1])
        for index, value in enumerate(rows)
    ] + [
        _make_v_grid_line(f"EV{index}", x=value, y1=rows[0], y2=rows[-1])
        for index, value in enumerate(cols)
    ]
    texts = [
        _make_text("ROW1", 20.0, 85.0, "出口1 Output 1"),
        _make_text("KLP", 145.0, 106.0, "1KLP7"),
    ]

    pairs, tables = extract_table_pairs(texts, lines, [], [sheet], DEFAULT_CONFIG)

    assert pairs == []
    assert len(tables) == 1
    assert tables[0]["matrix_table"] is True
    assert tables[0]["marked_cell_count"] == 0
    assert tables[0]["mappings"] == []
    assert tables[0]["structural_text_ids"] == []


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
    assert mappings[0]["mappings"][0]["logical_endpoint"] == "1-21QD-1"
    assert mappings[0]["mappings"][0]["left_value"] == "1-21n116"
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-21QD-1", "1-21n116"),
        ("1-21QD-2", "1-21n117"),
    }
    assert all(pair.status == "pass" for pair in pairs)
    assert all(pair.evidence["source"] == "table_mapping" for pair in pairs)
    assert pairs[0].evidence["table_mapping"]["mapping_mode"] == "terminal_header_table"


def test_extract_terminal_header_table_pairs_composes_header_hyphen_row() -> None:
    """Left-terminal three-column strip: header 1C5D + middle 10 + side 1n519 → 1C5D-10."""
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 220.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "21 左侧端子图1.dwg"
    texts = [
        _make_text("H", 252.0, 193.5, "1C5D"),
        _make_text("SH", 290.0, 193.75, "说明"),
        _make_text("R1", 254.25, 186.0, "1", is_numeric_candidate=True),
        _make_text("E1", 261.0, 186.0, "1n917"),
        _make_text("R2", 254.25, 181.0, "2", is_numeric_candidate=True),
        _make_text("E2", 261.0, 181.0, "1n918"),
        # stacked lower strip must not steal upper rows / break sequence
        _make_text("H2", 252.0, 113.5, "1C6D"),
        _make_text("SH2", 290.0, 113.75, "说明"),
        _make_text("R10", 253.5, 141.0, "10", is_numeric_candidate=True),
        _make_text("E10", 261.0, 141.0, "1n519"),
        _make_text("R11", 253.5, 136.0, "11", is_numeric_candidate=True),
        _make_text("E11", 261.0, 136.0, "1n516"),
        _make_text("R12", 253.5, 131.0, "12", is_numeric_candidate=True),
        _make_text("E12", 261.0, 131.0, "1n517"),
        _make_text("R13", 253.5, 126.0, "13", is_numeric_candidate=True),
        _make_text("E13", 261.0, 126.0, "1n518"),
        # fill remaining middle rows 3-9 so sequence is complete 1..13
        *[_make_text(f"R{n}", 254.25, 186.0 - 5.0 * (n - 1), str(n), is_numeric_candidate=True) for n in range(3, 10)],
        # lower strip rows
        _make_text("L1", 254.25, 106.0, "1", is_numeric_candidate=True),
        _make_text("LE1", 261.0, 106.0, "1n921"),
        _make_text("L2", 254.25, 101.0, "2", is_numeric_candidate=True),
        _make_text("LE2", 261.0, 101.0, "1n922"),
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("1C5D-10", "1n519") in pair_values
    assert ("1C5D-1", "1n917") in pair_values
    assert ("1C6D-1", "1n921") in pair_values
    assert all(pair.left_value and "-" in pair.left_value for pair in pairs if pair.left_value.startswith("1C5D"))
    mapping_modes = {
        row["mapping_mode"]
        for table in mappings
        for row in table["mappings"]
    }
    assert mapping_modes == {"terminal_header_table"}
    # upper strip must not absorb lower-strip row numbers into 1C5D-14+
    assert not any(pair.left_value == "1C5D-14" for pair in pairs)


def test_extract_terminal_header_table_pairs_accepts_shuoming_anchored_header_below_rows() -> None:
    """A 说明-anchored footer header owns the consecutive rows above it."""
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 180.0, 240.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "16 左侧端子图1.dwg"
    texts = [
        _make_text("H", 60.5, 128.5, "1-26TD"),
        _make_text("SH", 100.0, 128.75, "说明"),
        *[
            _make_text(
                f"R{row}",
                64.25,
                201.0 - 5.0 * (row - 1),
                str(row),
                is_numeric_candidate=True,
            )
            for row in range(1, 14)
        ],
        *[
            _make_text(
                f"E{row}",
                71.0,
                201.0 - 5.0 * (row - 1),
                endpoint,
            )
            for row, endpoint in enumerate(
                [
                    "1-26n105",
                    "1-26n108",
                    "1-26n111",
                    "2-26n105",
                    "2-26n108",
                    "2-26n111",
                    "2-26n105",
                    "1-26n106",
                    "1-26n110",
                    "1-26n113",
                    "2-26n106",
                    "2-26n110",
                    "2-26n113",
                ],
                start=1,
            )
        ],
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("1-26TD-10", "1-26n113") in pair_values
    assert ("1-26TD-11", "2-26n106") in pair_values
    assert ("1-26TD-13", "2-26n113") in pair_values
    assert len(pair_values) == 13
    assert mappings[0]["mappings"][0]["has_shuoming_column"] is True


def test_extract_terminal_header_table_pairs_accepts_shangjie_continuation() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 274.2))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "29 左侧端子图2.dwg"
    texts = [
        _make_text("H", 155.75, 276.0, "上接1YD48"),
        _make_text("SH", 197.5, 276.25, "说明"),
        _make_text("R49", 161.0, 268.5, "49", is_numeric_candidate=True),
        _make_text("E49", 168.5, 268.5, "1n520"),
        _make_text("R50", 161.0, 263.5, "50", is_numeric_candidate=True),
        _make_text("E50", 168.5, 263.5, "1n108"),
        _make_text("R51", 161.0, 258.5, "51", is_numeric_candidate=True),
        _make_text("E51", 168.5, 258.5, "1n104"),
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1YD-49", "1n520"),
        ("1YD-50", "1n108"),
        ("1YD-51", "1n104"),
    }
    mapping_rows = mappings[0]["mappings"]
    assert {row["continuation_from_row"] for row in mapping_rows} == {48}
    assert {row["header_prefix"] for row in mapping_rows} == {"1YD"}
    assert all(row["header_outside_audit_area"] is True for row in mapping_rows)


def test_extract_terminal_header_table_pairs_accepts_hyphenated_shangjie_continuation() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 271.7))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "20 右侧端子图1.dwg"
    texts = [
        _make_text("H", 176.0, 273.5, "上接1-21GD18"),
        _make_text("SH", 145.0, 273.75, "说明"),
        _make_text("R19", 183.5, 266.0, "19", is_numeric_candidate=True),
        _make_text("E19", 161.0, 266.0, "1-21DK2-2"),
        _make_text("R20", 183.5, 261.0, "20", is_numeric_candidate=True),
        _make_text("E20", 161.0, 261.0, "1-21n132"),
        _make_text("R21", 183.5, 256.0, "21", is_numeric_candidate=True),
        _make_text("E21", 161.0, 256.0, "1-21n231"),
    ]

    pairs, _ = extract_terminal_header_table_pairs(texts, [sheet])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-21GD-19", "1-21DK2-2"),
        ("1-21GD-20", "1-21n132"),
        ("1-21GD-21", "1-21n231"),
    }


def test_extract_terminal_header_table_pairs_keeps_blank_continuation_row_unmapped() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 271.7))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "17 左侧端子表1.dwg"
    texts = [
        _make_text("H", 152.5, 273.5, "上接4Q1D37"),
        _make_text("SH", 195.0, 273.75, "说明"),
        _make_text("R38", 158.5, 266.0, "38", is_numeric_candidate=True),
        _make_text("E38", 166.0, 266.0, "4n431"),
        _make_text("R39", 158.5, 261.0, "39", is_numeric_candidate=True),
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("4Q1D-38", "4n431"),
    }
    assert {row["logical_endpoint"] for row in mappings[0]["mappings"]} == {"4Q1D-38"}


def test_extract_terminal_header_table_pairs_rejects_unanchored_or_broken_continuation() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 274.2))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "continuation negative.dwg"
    texts = [
        _make_text("H", 155.75, 276.0, "上接1YD48"),
        _make_text("R49", 161.0, 268.5, "49", is_numeric_candidate=True),
        _make_text("E49", 168.5, 268.5, "1n520"),
        _make_text("R50", 161.0, 263.5, "50", is_numeric_candidate=True),
        _make_text("E50", 168.5, 263.5, "1n108"),
        _make_text("H2", 255.75, 276.0, "上接1LD48"),
        _make_text("SH2", 297.5, 276.25, "说明"),
        _make_text("R249", 261.0, 268.5, "49", is_numeric_candidate=True),
        _make_text("E249", 268.5, 268.5, "1n520"),
        _make_text("R251", 261.0, 258.5, "51", is_numeric_candidate=True),
        _make_text("E251", 268.5, 258.5, "1n104"),
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    assert pairs == []
    assert mappings == []


def test_continuation_header_does_not_steal_regular_header_endpoint() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 280.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "32 右侧端子图1.dwg"
    texts = [
        _make_text("CH", 272.5, 273.5, "上接1I3D19"),
        _make_text("CSH", 240.0, 273.75, "说明"),
        _make_text("CR20", 279.0, 266.0, "20", is_numeric_candidate=True),
        _make_text("CE20", 286.5, 266.0, "1n908"),
        _make_text("CR21", 279.0, 261.0, "21", is_numeric_candidate=True),
        _make_text("RH", 277.75, 208.5, "1QD"),
        _make_text("RSH", 240.0, 208.75, "说明"),
        _make_text("RR1", 279.25, 201.0, "1", is_numeric_candidate=True),
        _make_text("RE1", 286.5, 201.0, "1n112"),
        _make_text("RR2", 279.25, 196.0, "2", is_numeric_candidate=True),
        _make_text("RE2", 256.0, 196.0, "1KLP1-1"),
    ]

    pairs, _ = extract_terminal_header_table_pairs(texts, [sheet])

    assert ("1QD-2", "1KLP1-1") in {
        (pair.left_value, pair.right_value) for pair in pairs
    }


def test_extract_terminal_header_table_pairs_accepts_plain_instance_name_with_shuoming() -> None:
    """YD is an instance header when 说明 and a complete numbered strip anchor it."""
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 180.0, 240.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "16 左侧端子图1.dwg"
    endpoints = [
        "1-26n105",
        "1-26n108",
        "1-26n111",
        "2-26n105",
        "2-26n108",
        "2-26n111",
        "2-26n105",
        "1-26n106",
        "1-26n110",
        "1-26n113",
        "2-26n106",
        "2-26n110",
        "2-26n113",
    ]
    texts = [
        _make_text("H", 63.5, 208.5, "YD"),
        _make_text("SH", 100.0, 208.75, "说明"),
        *[
            _make_text(
                f"R{row}",
                64.25,
                201.0 - 5.0 * (row - 1),
                str(row),
                is_numeric_candidate=True,
            )
            for row in range(1, 14)
        ],
        *[
            _make_text(f"E{row}", 71.0, 201.0 - 5.0 * (row - 1), endpoint)
            for row, endpoint in enumerate(endpoints, start=1)
        ],
    ]

    pairs, _ = extract_terminal_header_table_pairs(texts, [sheet])

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("YD-10", "1-26n113") in pair_values
    assert ("YD-11", "2-26n106") in pair_values
    assert ("YD-13", "2-26n113") in pair_values
    assert len(pair_values) == 13


def test_extract_terminal_header_table_pairs_keeps_same_port_left_and_right_fanout() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 260.0, 240.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "23 右侧端子图1.dwg"
    texts = [
        _make_text("H", 150.0, 220.0, "1UD"),
        _make_text("SH", 100.0, 220.0, "说明"),
        _make_text("H2", 230.0, 220.0, "2UD"),
        _make_text("SH2", 250.0, 220.0, "说明"),
        _make_text("L1", 130.0, 210.0, "1ZKK1-2"),
        _make_text("R1", 150.0, 210.0, "1", is_numeric_candidate=True),
        _make_text("E1", 170.0, 210.0, "1n2001"),
        # Same-row endpoint from the next table must not be stolen by 1UD-1.
        _make_text("NEXT1", 220.0, 210.0, "1n2123"),
        _make_text("L2", 130.0, 205.0, "1ZKK1-4"),
        _make_text("R2", 150.0, 205.0, "2", is_numeric_candidate=True),
        _make_text("E2", 170.0, 205.0, "1n2003"),
        # A sparse far column is valid when it names a known terminal header.
        _make_text("R3", 150.0, 200.0, "3", is_numeric_candidate=True),
        _make_text("NEXT3", 220.0, 200.0, "2UD3"),
        # A blank port must not borrow an unrelated endpoint from that column.
        _make_text("R4", 150.0, 195.0, "4", is_numeric_candidate=True),
        _make_text("PEER7", 230.0, 195.0, "7", is_numeric_candidate=True),
        _make_text("NEXT4", 220.0, 195.0, "1n2124"),
    ]

    pairs, _ = extract_terminal_header_table_pairs(texts, [sheet])

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("1UD-1", "1ZKK1-2") in pair_values
    assert ("1UD-1", "1n2001") in pair_values
    assert ("1UD-2", "1ZKK1-4") in pair_values
    assert ("1UD-2", "1n2003") in pair_values
    assert ("1UD-1", "1n2123") not in pair_values
    assert ("1UD-3", "2UD3") in pair_values
    assert ("1UD-4", "1n2124") not in pair_values
    assert len(pair_values) == 5
    assert all(pair.pair_kind == "table_mapping" for pair in pairs)


def test_extract_terminal_header_table_pairs_excludes_semantic_endpoint_labels() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 260.0, 280.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "21 左侧端子图1.dwg"
    texts = [
        _make_text("H", 60.5, 163.5, "3-21ID"),
        _make_text("R1", 64.25, 156.0, "1", is_numeric_candidate=True),
        _make_text("E1", 71.0, 156.0, "3-21n701"),
        _make_text("S1", 91.0, 156.25, "I0"),
        _make_text("R2", 64.25, 151.0, "2", is_numeric_candidate=True),
        _make_text("E2", 71.0, 151.0, "3-21n702"),
        _make_text("S2", 91.0, 151.25, "3U0"),
    ]

    pairs, mappings = extract_terminal_header_table_pairs(texts, [sheet])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("3-21ID-1", "3-21n701"),
        ("3-21ID-2", "3-21n702"),
    }
    assert all(pair.right_value not in {"I0", "3U0"} for pair in pairs)
    mapping_endpoints = {
        row.get("left_value") or row.get("right_value")
        for table_mapping in mappings
        for row in table_mapping["mappings"]
    }
    assert "I0" not in mapping_endpoints
    assert "3U0" not in mapping_endpoints


def test_extract_terminal_header_table_pairs_accepts_accessory_port_designators() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 260.0, 280.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "right terminal accessories.dwg"
    texts = [
        _make_text("H", 190.0, 276.0, "JD"),
        _make_text("DESC", 152.0, 276.25, "说明"),
        _make_text("R1", 191.0, 268.5, "1", is_numeric_candidate=True),
        _make_text("E1", 168.5, 268.5, "AK-1"),
        _make_text("R2", 191.0, 263.5, "2", is_numeric_candidate=True),
        _make_text("E2", 168.5, 263.5, "CZ-L"),
        _make_text("R3", 191.0, 258.5, "3", is_numeric_candidate=True),
        _make_text("E3", 168.5, 258.5, "KZKK-3"),
        _make_text("G3", 198.5, 258.5, "GND"),
    ]

    pairs, _ = extract_terminal_header_table_pairs(texts, [sheet])

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("JD-1", "AK-1"),
        ("JD-2", "CZ-L"),
        ("JD-3", "KZKK-3"),
        ("JD-3", "GND"),
    }


def test_adjacent_terminal_headers_do_not_claim_each_others_endpoint_columns() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 280.0))
    sheet.sheet_category = "屏端子图"
    sheet.filename = "adjacent terminal strips.dwg"
    texts = [
        _make_text("HTD", 100.0, 276.0, "TD"),
        _make_text("STD", 60.0, 276.25, "说明"),
        _make_text("HJD", 190.0, 276.0, "JD"),
        _make_text("SJD", 152.0, 276.25, "说明"),
        _make_text("RT1", 100.0, 268.5, "1", is_numeric_candidate=True),
        _make_text("ET1", 76.0, 268.5, "1n1412"),
        _make_text("RJ1", 190.0, 268.5, "1", is_numeric_candidate=True),
        _make_text("EJ1", 168.5, 268.5, "AK-1"),
        _make_text("RT2", 100.0, 263.5, "2", is_numeric_candidate=True),
        _make_text("ET2", 76.0, 263.5, "1n1413"),
        _make_text("RJ2", 190.0, 263.5, "2", is_numeric_candidate=True),
        _make_text("EJ2", 168.5, 263.5, "CZ-L"),
    ]

    pairs, _ = extract_terminal_header_table_pairs(texts, [sheet])
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}

    assert pair_values == {
        ("TD-1", "1n1412"),
        ("TD-2", "1n1413"),
        ("JD-1", "AK-1"),
        ("JD-2", "CZ-L"),
    }


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
        _make_text("R3", x=208.75, y=233.75, value="03", is_numeric_candidate=True, source_block_name="WBH-814E-E1SA-101"),
        _make_text("E1", x=199.0, y=238.5, value="5FD15"),
        _make_text("E2", x=238.5, y=238.5, value="5FD16 *"),
        _make_text("E3", x=199.0, y=233.5, value="1U2D17"),
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
        ("NKR308A-3", "1U2D17"),
    }
    assert all(pair.evidence["source"] == "table_mapping" for pair in pairs)
    assert all(pair.evidence["pair_kind"] == "table_mapping" for pair in pairs)
    assert {pair.pair_kind for pair in pairs} == {"table_mapping"}
    assert pairs[0].evidence["table_mapping"]["source_block_name"] == "WBH-814E-E1SA-101"


def test_extract_table_pairs_builds_backplate_prefixed_endpoint_mappings() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 300.0, 260.0))
    sheet.filename = "18 高后备保护背板图.dwg"
    sheet.sheet_title = "高后备保护背板图"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"

    texts = [
        _make_text("H1", x=120.0, y=230.0, value="NDY306A", source_block_name="WBH-813E-E1SH-201"),
        _make_text("R1", x=116.0, y=220.0, value="01", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-201"),
        _make_text("R2", x=116.0, y=215.0, value="02", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-201"),
        _make_text("R3", x=116.0, y=210.0, value="03", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-201"),
        _make_text("E1", x=111.0, y=220.2, value="& 1-2QD1"),
        _make_text("E2", x=111.0, y=215.2, value="CD2"),
        _make_text("E3", x=111.0, y=210.2, value="YD3"),
    ]

    pairs, mappings = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    assert mappings[0]["mappings"][0]["mapping_mode"] == "backplate_virtual_table"
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {
        ("NDY306A-1", "1-2QD1"),
        ("NDY306A-2", "CD2"),
        ("NDY306A-3", "YD3"),
    }
    assert {pair.pair_kind for pair in pairs} == {"table_mapping"}


def test_extract_table_pairs_skips_sparse_backplate_header_group() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 300.0, 260.0))
    sheet.filename = "18 高后备保护背板图.dwg"
    sheet.sheet_title = "高后备保护背板图"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"

    texts = [
        _make_text("H1", x=120.0, y=230.0, value="LAN1", source_block_name="WBH-813E-E1SH-LAN"),
        _make_text("R1", x=116.0, y=220.0, value="01", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-LAN"),
        _make_text("R2", x=116.0, y=215.0, value="02", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-LAN"),
        _make_text("E1", x=111.0, y=220.2, value="LAN1"),
        _make_text("E2", x=111.0, y=215.2, value="LAN2"),
    ]

    pairs, mappings = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert pairs == []
    assert mappings == []


def test_sparse_backplate_header_does_not_reserve_rows_from_authoritative_header() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 300.0, 260.0))
    sheet.filename = "rear wiring.dwg"
    sheet.sheet_title = "REAR WIRING"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"
    block = "UNSEEN-BACKPLATE"
    texts = [
        # This higher candidate can see only row 1 (90-unit boundary). It is
        # too sparse and must not reserve that row/endpoint from NJL307.
        _make_text("WEAK", x=120.0, y=250.0, value="LAN1", source_block_name=block),
        _make_text("HEADER", x=120.0, y=170.0, value="NJL307", source_block_name=block),
        _make_text("R1", x=116.0, y=160.0, value="01", is_numeric_candidate=True, source_block_name=block),
        _make_text("R2", x=116.0, y=155.0, value="02", is_numeric_candidate=True, source_block_name=block),
        _make_text("R3", x=116.0, y=150.0, value="03", is_numeric_candidate=True, source_block_name=block),
        _make_text("E1", x=105.0, y=160.0, value="1U2D1"),
        _make_text("E2", x=105.0, y=155.0, value="1U2D2"),
        _make_text("E3", x=105.0, y=150.0, value="1U2D3"),
    ]

    pairs, mappings = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("NJL307-1", "1U2D1"),
        ("NJL307-2", "1U2D2"),
        ("NJL307-3", "1U2D3"),
    }
    assert len(mappings) == 1


def test_repeated_backplate_device_header_outranks_incidental_signal_label() -> None:
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 320.0, 260.0))
    sheet.filename = "rear wiring.dwg"
    sheet.sheet_title = "REAR WIRING"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"
    block = "UNSEEN-BACKPLATE"
    texts = [
        # LAN2 can geometrically see all three rows, but it is an incidental
        # signal label. Repeated NJL307 headers establish the device family.
        _make_text("SIGNAL", x=120.0, y=240.0, value="LAN2", source_block_name=block),
        _make_text("HEADER1", x=120.0, y=170.0, value="NJL307", source_block_name=block),
        _make_text("HEADER2", x=220.0, y=170.0, value="NJL307", source_block_name=block),
        _make_text("R1", x=116.0, y=160.0, value="01", is_numeric_candidate=True, source_block_name=block),
        _make_text("R2", x=116.0, y=155.0, value="02", is_numeric_candidate=True, source_block_name=block),
        _make_text("R3", x=116.0, y=150.0, value="03", is_numeric_candidate=True, source_block_name=block),
        _make_text("E1", x=105.0, y=160.0, value="1U2D1"),
        _make_text("E2", x=105.0, y=155.0, value="1U2D2"),
        _make_text("E3", x=105.0, y=150.0, value="1U2D3"),
    ]

    pairs, _ = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("NJL307-1@c0", "1U2D1"),
        ("NJL307-2@c0", "1U2D2"),
        ("NJL307-3@c0", "1U2D3"),
    }
    assert not any(pair.left_value.startswith("LAN2-") for pair in pairs)


def test_extract_table_pairs_builds_composite_pmu_instance_pin_mappings() -> None:
    """Composite PMU backplate: instance 1-25n + plugin bay + pin → external designator."""
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 400.0, 280.0))
    sheet.filename = "13 PMU采集器背板接线图1.dwg"
    sheet.sheet_title = "REAR WIRING 1-25n"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"
    block = "SPMU-857G-CG"

    texts = [
        _make_text("INST", x=200.0, y=250.0, value="1-25n"),
        # Plugin bay 2 开入插件
        _make_text("P2", x=130.0, y=230.0, value="2", source_block_name=block),
        _make_text("T2", x=142.0, y=230.0, value="开入插件", source_block_name=block),
        # Dual pin columns under bay 2
        _make_text("R01", x=120.0, y=220.0, value="01", is_numeric_candidate=True, source_block_name=block),
        _make_text("R02", x=150.0, y=220.0, value="02", is_numeric_candidate=True, source_block_name=block),
        _make_text("R03", x=120.0, y=215.0, value="03", is_numeric_candidate=True, source_block_name=block),
        _make_text("R04", x=150.0, y=215.0, value="04", is_numeric_candidate=True, source_block_name=block),
        _make_text("R05", x=120.0, y=210.0, value="05", is_numeric_candidate=True, source_block_name=block),
        # External designators beside pins
        _make_text("E1", x=105.0, y=220.0, value="1-25KLP1-2"),
        _make_text("E2", x=165.0, y=220.0, value="1-25QD1"),
        _make_text("E3", x=105.0, y=215.0, value="1-25QD2"),
        _make_text("E4", x=165.0, y=215.0, value="1-25QD3"),
        _make_text("E5", x=105.0, y=210.0, value="1-25QD4"),
        # Template signal headers (must not flood Ia1-13 style conflicts)
        _make_text("HIA", x=125.0, y=200.0, value="Ia1", source_block_name=block),
        _make_text("RIA", x=120.0, y=190.0, value="13", is_numeric_candidate=True, source_block_name=block),
        _make_text("EIA", x=100.0, y=190.0, value="1-25ZKK7-2"),
    ]

    pairs, mappings = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert mappings
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("1-25n201", "1-25KLP1-2") in pair_values
    assert ("1-25n202", "1-25QD1") in pair_values
    assert ("1-25n203", "1-25QD2") in pair_values
    assert ("1-25n204", "1-25QD3") in pair_values
    assert ("1-25n205", "1-25QD4") in pair_values
    # Template Ia1-13 must not appear as bare cross-page collision key.
    assert not any(left == "Ia1-13" for left, _ in pair_values)
    first = next(pair for pair in pairs if pair.left_value == "1-25n201")
    assert first.evidence["table_mapping"]["composite_device_instance"] == "1-25n"
    assert first.evidence["table_mapping"]["plugin_slot"] == 2


def test_extract_table_pairs_scopes_classic_backplate_headers_with_device_instance() -> None:
    """Classic NDY header still works; when instance present logical keys stay device-scoped."""
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 300.0, 260.0))
    sheet.filename = "18 高后备保护背板图.dwg"
    sheet.sheet_title = "REAR WIRING 1-2n"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"

    texts = [
        _make_text("INST", x=50.0, y=250.0, value="1-2n"),
        _make_text("H1", x=120.0, y=230.0, value="NDY306A", source_block_name="WBH-813E-E1SH-201"),
        _make_text("R1", x=116.0, y=220.0, value="01", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-201"),
        _make_text("R2", x=116.0, y=215.0, value="02", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-201"),
        _make_text("R3", x=116.0, y=210.0, value="03", is_numeric_candidate=True, source_block_name="WBH-813E-E1SH-201"),
        _make_text("E1", x=111.0, y=220.2, value="& 1-2QD1"),
        _make_text("E2", x=111.0, y=215.2, value="CD2"),
        _make_text("E3", x=111.0, y=210.2, value="YD3"),
    ]

    pairs, mappings = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert len(mappings) == 1
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    # No plugin bay number → instance-scoped header-row keys, not bare NDY306A-1 collisions.
    assert pair_values == {
        ("1-2n/NDY306A-1", "1-2QD1"),
        ("1-2n/NDY306A-2", "CD2"),
        ("1-2n/NDY306A-3", "YD3"),
    }
    assert pairs[0].evidence["table_mapping"]["composite_device_instance"] == "1-2n"


def test_extract_table_pairs_power_dual_column_and_bi_instance_scope() -> None:
    """测控 Power dual-column pins map left/right without stealing BI bay endpoints."""
    sheet = _make_sheet(audit_area_bbox=(0.0, 0.0, 420.0, 280.0))
    sheet.filename = "14 测控1装置背板.dwg"
    sheet.sheet_title = "1-21n REAR WIRING"
    sheet.sheet_category = "背板接线图"
    sheet.audit_role = "secondary"
    block = "FCK-851C-G-4"

    texts = [
        _make_text("INST", x=200.0, y=265.0, value="1-21n"),
        # Bay titles: 1 Power | 2 BI1
        _make_text("N1", x=56.0, y=243.0, value="1", source_block_name=block),
        _make_text("T1", x=69.0, y=243.0, value="Power", source_block_name=block),
        _make_text("N2", x=131.0, y=243.0, value="2", source_block_name=block),
        _make_text("T2", x=145.0, y=243.0, value="BI1", source_block_name=block),
        # Power dual pin columns (left x=56, right x=81)
        _make_text("P01", x=56.0, y=233.0, value="03", is_numeric_candidate=True, source_block_name=block),
        _make_text("P02", x=81.0, y=233.0, value="04", is_numeric_candidate=True, source_block_name=block),
        _make_text("P03", x=56.0, y=223.0, value="07", is_numeric_candidate=True, source_block_name=block),
        _make_text("P04", x=81.0, y=223.0, value="08", is_numeric_candidate=True, source_block_name=block),
        _make_text("P05", x=56.0, y=213.0, value="11", is_numeric_candidate=True, source_block_name=block),
        _make_text("P06", x=81.0, y=213.0, value="12", is_numeric_candidate=True, source_block_name=block),
        _make_text("P07", x=56.0, y=203.0, value="15", is_numeric_candidate=True, source_block_name=block),
        _make_text("P08", x=81.0, y=203.0, value="16", is_numeric_candidate=True, source_block_name=block),
        _make_text("P09", x=56.0, y=163.0, value="31", is_numeric_candidate=True, source_block_name=block),
        _make_text("P10", x=81.0, y=163.0, value="32", is_numeric_candidate=True, source_block_name=block),
        # Power external designators (left / right of dual columns)
        _make_text("E1", x=37.0, y=233.0, value="& 1-21DK1-4"),
        _make_text("E2", x=86.0, y=223.0, value="1-21YD1"),
        _make_text("E3", x=86.0, y=213.0, value="1-21KLP1-2"),
        _make_text("E4", x=43.0, y=203.0, value="1-21QD1"),
        _make_text("E5", x=86.0, y=163.0, value="1-21GD20"),
        # BI1 dual pin columns + externals (must not be stolen by Power)
        _make_text("B01", x=131.0, y=238.0, value="01", is_numeric_candidate=True, source_block_name=block),
        _make_text("B02", x=156.0, y=238.0, value="02", is_numeric_candidate=True, source_block_name=block),
        _make_text("B03", x=131.0, y=233.0, value="03", is_numeric_candidate=True, source_block_name=block),
        _make_text("B04", x=156.0, y=233.0, value="04", is_numeric_candidate=True, source_block_name=block),
        _make_text("B05", x=131.0, y=228.0, value="05", is_numeric_candidate=True, source_block_name=block),
        _make_text("BE1", x=117.0, y=238.0, value="1-21QD18"),
        _make_text("BE2", x=161.0, y=238.0, value="1-21QD19"),
        _make_text("BE3", x=117.0, y=233.0, value="1-21QD20"),
        _make_text("BE4", x=161.0, y=233.0, value="1-21QD21"),
        _make_text("BE5", x=117.0, y=228.0, value="1-21QD22"),
    ]

    pairs, mappings = extract_table_pairs(texts, [], [], [sheet], DEFAULT_CONFIG)

    assert mappings
    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}

    # Power bay 1 dual-column → instance+bay+pin keys
    assert ("1-21n103", "1-21DK1-4") in pair_values
    assert ("1-21n108", "1-21YD1") in pair_values
    assert ("1-21n112", "1-21KLP1-2") in pair_values
    assert ("1-21n115", "1-21QD1") in pair_values
    assert ("1-21n132", "1-21GD20") in pair_values

    # BI template rows stay device-scoped; never bare BI1-1 across 1-21n/2-21n pages.
    assert any(left.startswith("1-21n/BI1-") for left, _ in pair_values)
    assert any(right == "1-21QD18" and left.startswith("1-21n") for left, right in pair_values)
    assert not any(left == "BI1-1" for left, _ in pair_values)

    # Power must not steal BI bay endpoints.
    power_rights = {right for left, right in pair_values if left.startswith("1-21n1")}
    assert "1-21QD18" not in power_rights
    assert "1-21QD19" not in power_rights

    power_pair = next(pair for pair in pairs if pair.left_value == "1-21n108")
    assert power_pair.evidence["table_mapping"]["composite_device_instance"] == "1-21n"
    assert power_pair.evidence["table_mapping"]["plugin_slot"] == 1
    assert power_pair.evidence["table_mapping"]["plugin_title"] == "Power"


def test_extract_table_pairs_bi_scope_differs_across_device_instances() -> None:
    """Same template BI1 rows on 1-21n vs 2-21n must produce distinct logical keys."""
    block = "FCK-851C-G-1"

    def _sheet_bundle(instance: str, sheet_id: str, qd_prefix: str):
        sheet = _make_sheet(sheet_id=sheet_id, audit_area_bbox=(0.0, 0.0, 300.0, 280.0))
        sheet.filename = f"{sheet_id} 测控装置背板.dwg"
        sheet.sheet_title = f"{instance} REAR WIRING"
        sheet.sheet_category = "背板接线图"
        sheet.audit_role = "secondary"
        texts = [
            _make_text(f"{sheet_id}I", x=150.0, y=260.0, value=instance),
            _make_text(f"{sheet_id}H", x=145.0, y=243.0, value="BI1", source_block_name=block),
            _make_text(
                f"{sheet_id}R1",
                x=131.0,
                y=238.0,
                value="01",
                is_numeric_candidate=True,
                source_block_name=block,
            ),
            _make_text(
                f"{sheet_id}R2",
                x=156.0,
                y=238.0,
                value="02",
                is_numeric_candidate=True,
                source_block_name=block,
            ),
            _make_text(
                f"{sheet_id}R3",
                x=131.0,
                y=233.0,
                value="03",
                is_numeric_candidate=True,
                source_block_name=block,
            ),
            _make_text(f"{sheet_id}E1", x=117.0, y=238.0, value=f"{qd_prefix}QD18"),
            _make_text(f"{sheet_id}E2", x=161.0, y=238.0, value=f"{qd_prefix}QD19"),
            _make_text(f"{sheet_id}E3", x=117.0, y=233.0, value=f"{qd_prefix}QD20"),
        ]
        for text in texts:
            text.sheet_id = sheet_id
        return sheet, texts

    sheet_a, texts_a = _sheet_bundle("1-21n", "S14", "1-21")
    sheet_b, texts_b = _sheet_bundle("2-21n", "S15", "2-21")
    pairs, _ = extract_table_pairs(texts_a + texts_b, [], [], [sheet_a, sheet_b], DEFAULT_CONFIG)
    lefts = {pair.left_value for pair in pairs}
    assert any(left.startswith("1-21n/BI1-") for left in lefts)
    assert any(left.startswith("2-21n/BI1-") for left in lefts)
    assert "BI1-1" not in lefts
