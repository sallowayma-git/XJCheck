from dwg_audit.audit.component_diagrams import extract_kk_multi_port_component_pairs
from dwg_audit.audit.component_diagrams import extract_strip_two_port_component_pairs
from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem


def _make_sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="23 元件接线图3.dwg",
        sheet_order=23,
        sheet_no="23",
        sheet_title="TERMINAL BLOCKS WIRING",
        sheet_category="元件接线图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        page_type="元件接线图",
        page_subtype="horizontal_component",
        route_target="ComponentDiagramExtractor",
        audit_disposition="audit_required",
    )


def _make_text(
    text_id: str,
    value: str,
    x: float,
    y: float,
    *,
    layer: str = "TEXT",
    source_block_name: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> TextItem:
    bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y = bbox or (x, y - 1.0, x + 2.0, y + 1.0)
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{text_id}",
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=value.isdigit(),
        layer=layer,
        rotation_deg=0.0,
        height=2.5,
        insert_x=x,
        insert_y=y,
        bbox_min_x=bbox_min_x,
        bbox_min_y=bbox_min_y,
        bbox_max_x=bbox_max_x,
        bbox_max_y=bbox_max_y,
        source_block_name=source_block_name,
    )


def _make_vertical_group() -> LineGroup:
    return LineGroup(
        line_group_id="GC0132",
        sheet_id="S1",
        file_id="F1",
        start_x=207.0,
        start_y=191.3,
        end_x=207.0,
        end_y=176.3,
        length=15.0,
        wire_candidate_score=0.9,
        member_line_ids=["L1"],
        layer_hints=["CONNECT"],
        orientation="vertical",
    )


def _make_horizontal_group(line_group_id: str, y: float, *, start_x: float = 108.0, end_x: float = 140.0) -> LineGroup:
    return LineGroup(
        line_group_id=line_group_id,
        sheet_id="S1",
        file_id="F1",
        start_x=start_x,
        start_y=y,
        end_x=end_x,
        end_y=y,
        length=abs(end_x - start_x),
        wire_candidate_score=0.9,
        member_line_ids=[f"L{line_group_id}"],
        layer_hints=["CONNECT"],
        orientation="horizontal",
    )


def _make_block(block_id: str, name: str, x: float = 101.0, y: float = 75.0) -> BlockRecord:
    return BlockRecord(
        block_id=block_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{block_id}",
        name=name,
        layer="0",
        insert_x=x,
        insert_y=y,
        rotation_deg=0.0,
        attributes_json="{}",
    )


def test_extract_strip_two_port_component_pairs_builds_component_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3859", "5KLP9-1", 204.3, 195.4),
        _make_text("T3860", "5n112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs([sheet], texts, [_make_vertical_group()])

    assert consumed == {"GC0132"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("5KLP10-1", "5KLP9-1"),
        ("5KLP10-2", "5n112"),
    }
    assert {pair.pair_kind for pair in pairs} == {"component_mapping"}
    assert all(pair.status == "pass" for pair in pairs)
    first = next(pair for pair in pairs if pair.left_value == "5KLP10-1")
    assert first.evidence["source"] == "component_mapping"
    assert first.evidence["component_submode"] == "strip_two_port_component"
    assert first.evidence["component_block_name"] == "FJL-25-2A_Mirror"
    assert first.evidence["component_port_text_id"] == "T3806"
    assert first.evidence["external_endpoint_text_id"] == "T3859"


def test_extract_strip_two_port_component_pairs_requires_supporting_vertical_group() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3859", "5KLP9-1", 204.3, 195.4),
        _make_text("T3860", "5n112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs([sheet], texts, [])

    assert pairs == []
    assert consumed == set()


def test_extract_strip_two_port_component_pairs_skips_unsplit_comma_endpoint() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3859", "5FD2,5KLP10-1", 204.3, 195.4),
        _make_text("T3860", "5n112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs([sheet], texts, [_make_vertical_group()])

    assert pairs == []
    assert consumed == set()


def test_extract_strip_two_port_component_pairs_ignores_comma_endpoint_when_legal_candidate_exists() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T_BAD", "5FD2,5KLP10-1", 204.3, 195.4),
        _make_text("T3859", "5KLP9-1", 213.0, 195.2),
        _make_text("T3860", "5n112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs([sheet], texts, [_make_vertical_group()])

    assert consumed == {"GC0132"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("5KLP10-1", "5KLP9-1"),
        ("5KLP10-2", "5n112"),
    }
    assert all(pair.right_text_id != "T_BAD" for pair in pairs)


def test_extract_strip_two_port_component_pairs_requires_two_valid_external_endpoints() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3859", "5KLP9-1", 204.3, 195.4),
        _make_text("T3860", "112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs([sheet], texts, [_make_vertical_group()])

    assert pairs == []
    assert consumed == set()


def test_extract_kk_multi_port_component_pairs_builds_kk2p_four_outputs() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK2P", "KK2P")
    texts = [
        _make_text("BODY", "5DK", 100.0, 112.0, layer="MARK"),
        _make_text("P1", "1", 100.0, 90.0, layer="0", source_block_name="KK2P"),
        _make_text("P2", "2", 100.0, 80.0, layer="0", source_block_name="KK2P"),
        _make_text("P3", "3", 100.0, 70.0, layer="0", source_block_name="KK2P"),
        _make_text("P4", "4", 100.0, 60.0, layer="0", source_block_name="KK2P"),
        _make_text("E1", "ZD12", 20.0, 90.0, bbox=(139.0, 89.0, 141.0, 91.0)),
        _make_text("E2", "5FD25", 139.0, 80.0),
        _make_text("E3", "ZD4", 139.0, 70.0),
        _make_text("E4", "5FD1", 139.0, 60.0),
    ]
    groups = [
        _make_horizontal_group("G1", 90.0),
        _make_horizontal_group("G2", 80.0),
        _make_horizontal_group("G3", 70.0),
        _make_horizontal_group("G4", 60.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G1", "G2", "G3", "G4"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("5DK-1", "ZD12"),
        ("5DK-2", "5FD25"),
        ("5DK-3", "ZD4"),
        ("5DK-4", "5FD1"),
    }
    assert {pair.pair_kind for pair in pairs} == {"component_mapping"}
    assert all(pair.status == "pass" for pair in pairs)
    first = next(pair for pair in pairs if pair.left_value == "5DK-1")
    assert first.confidence == 0.95
    assert first.right_coord_x == 140.0
    assert first.evidence["source"] == "component_mapping"
    assert first.evidence["submode"] == "kk_multi_port_component"
    assert first.evidence["component_submode"] == "kk_multi_port_component"
    assert first.evidence["component_block_name"] == "KK2P"
    assert first.evidence["component_port_text_id"] == "P1"
    assert first.evidence["external_endpoint_text_id"] == "E1"


def test_extract_kk_multi_port_component_pairs_builds_kk3p_partial_outputs_only() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK3P", "KK3P", y=95.0)
    texts = [
        _make_text("BODY", "1-2ZKK", 100.0, 141.0, layer="MARK"),
        _make_text("P1", "1", 100.0, 120.0, layer="0", source_block_name="KK3P"),
        _make_text("P2", "2", 100.0, 110.0, layer="0", source_block_name="KK3P"),
        _make_text("P3", "3", 100.0, 100.0, layer="0", source_block_name="KK3P"),
        _make_text("P4", "4", 100.0, 90.0, layer="0", source_block_name="KK3P"),
        _make_text("P5", "5", 100.0, 80.0, layer="0", source_block_name="KK3P"),
        _make_text("P6", "6", 100.0, 70.0, layer="0", source_block_name="KK3P"),
        _make_text("E1", "1-2UD1", 179.0, 120.0),
        _make_text("E2", "1-2n719", 179.0, 110.0),
        _make_text("E6", "1-2n721", 179.0, 70.0),
    ]
    groups = [
        _make_horizontal_group("G1", 120.0, end_x=180.0),
        _make_horizontal_group("G2", 110.0, end_x=180.0),
        _make_horizontal_group("G3", 100.0, end_x=180.0),
        _make_horizontal_group("G4", 90.0, end_x=180.0),
        _make_horizontal_group("G5", 80.0, end_x=180.0),
        _make_horizontal_group("G6", 70.0, end_x=180.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G1", "G2", "G6"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-2ZKK-1", "1-2UD1"),
        ("1-2ZKK-2", "1-2n719"),
        ("1-2ZKK-6", "1-2n721"),
    }
    assert {pair.left_value for pair in pairs}.isdisjoint({"1-2ZKK-3", "1-2ZKK-4", "1-2ZKK-5"})


def test_extract_kk_multi_port_component_pairs_does_not_force_missing_external_endpoint() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK2P", "KK2P")
    texts = [
        _make_text("BODY", "1-21DK2", 100.0, 112.0, layer="MARK"),
        _make_text("P1", "1", 100.0, 90.0, layer="0", source_block_name="KK2P"),
        _make_text("P2", "2", 100.0, 80.0, layer="0", source_block_name="KK2P"),
        _make_text("P3", "3", 100.0, 70.0, layer="0", source_block_name="KK2P"),
        _make_text("P4", "4", 100.0, 60.0, layer="0", source_block_name="KK2P"),
        _make_text("E1", "ZD8", 139.0, 90.0),
        _make_text("E2", "1-21GD19", 139.0, 80.0),
        _make_text("UNCLEAR", "719", 139.0, 70.0),
    ]
    groups = [
        _make_horizontal_group("G1", 90.0),
        _make_horizontal_group("G2", 80.0),
        _make_horizontal_group("G3", 70.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G1", "G2"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-21DK2-1", "ZD8"),
        ("1-21DK2-2", "1-21GD19"),
    }


def test_extract_kk_multi_port_component_pairs_ignores_non_kk_blocks() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK1P", "KK1P")
    texts = [
        _make_text("BODY", "5DK", 100.0, 112.0, layer="MARK"),
        _make_text("P1", "1", 100.0, 90.0, layer="0", source_block_name="KK1P"),
        _make_text("P2", "2", 100.0, 80.0, layer="0", source_block_name="KK1P"),
        _make_text("E1", "ZD12", 139.0, 90.0),
        _make_text("E2", "5FD25", 139.0, 80.0),
    ]
    groups = [
        _make_horizontal_group("G1", 90.0),
        _make_horizontal_group("G2", 80.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert pairs == []
    assert consumed == set()


def test_extract_kk_multi_port_component_pairs_deduplicates_same_group_side_endpoint() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK3P", "KK3P", x=120.0, y=95.0)
    texts = [
        _make_text("BODY", "1-21ZKK", 120.0, 141.0, layer="MARK"),
        _make_text("P4", "4", 118.0, 110.0, layer="0", source_block_name="KK3P"),
        _make_text("P6", "6", 132.0, 110.0, layer="0", source_block_name="KK3P"),
        _make_text("E4", "1-21n715", 99.0, 110.0),
    ]
    groups = [_make_horizontal_group("GZ", 110.0, start_x=100.0, end_x=140.0)]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"GZ"}
    assert len(pairs) == 1
    assert pairs[0].left_value in {"1-21ZKK-4", "1-21ZKK-6"}
    assert pairs[0].right_value == "1-21n715"
