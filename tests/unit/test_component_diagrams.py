from dwg_audit.audit.component_diagrams import extract_kk_multi_port_component_pairs
from dwg_audit.audit.component_diagrams import extract_small_port_box_component_pairs
from dwg_audit.audit.component_diagrams import extract_strip_two_port_endpoint_bridge_pairs
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


def _make_vertical_group(
    line_group_id: str = "GC0132",
    *,
    x: float = 207.0,
    start_y: float = 191.3,
    end_y: float = 176.3,
) -> LineGroup:
    return LineGroup(
        line_group_id=line_group_id,
        sheet_id="S1",
        file_id="F1",
        start_x=x,
        start_y=start_y,
        end_x=x,
        end_y=end_y,
        length=abs(start_y - end_y),
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


def test_extract_strip_two_port_component_pairs_accepts_non_mirrored_definition() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("BODY", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("PORT1", "1", 208.9, 190.0, layer="0", source_block_name="fjl-25-2a"),
        _make_text("PORT2", "2", 208.9, 175.0, layer="0", source_block_name="fjl-25-2a"),
        _make_text("TOP", "5KLP9-1", 204.3, 195.4),
        _make_text("BOTTOM", "5n112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs(
        [sheet], texts, [_make_vertical_group()]
    )

    assert consumed == {"GC0132"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("5KLP10-1", "5KLP9-1"),
        ("5KLP10-2", "5n112"),
    }
    assert {pair.evidence["component_block_name"] for pair in pairs} == {"fjl-25-2a"}


def test_extract_strip_two_port_component_pairs_accepts_hierarchical_module_endpoint() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("BODY", "1-21CLP9", 49.85, 266.5, layer="MARK"),
        _make_text("PORT1", "1", 54.37, 251.28, layer="0", source_block_name="FJL-25-2A"),
        _make_text("PORT2", "2", 54.37, 236.29, layer="0", source_block_name="FJL-25-2A"),
        _make_text("TOP", "1-21C1D36", 48.24, 256.60),
        _make_text("BOTTOM", "1-21n427", 48.99, 231.0),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs(
        [sheet],
        texts,
        [_make_vertical_group("GC", x=52.5, start_y=252.5, end_y=237.5)],
    )

    assert consumed == {"GC"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-21CLP9-1", "1-21C1D36"),
        ("1-21CLP9-2", "1-21n427"),
    }


def test_extract_strip_two_port_component_pairs_rejects_malformed_hierarchical_endpoint() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("BODY", "1-21CLP9", 49.85, 266.5, layer="MARK"),
        _make_text("PORT1", "1", 54.37, 251.28, layer="0", source_block_name="FJL-25-2A"),
        _make_text("PORT2", "2", 54.37, 236.29, layer="0", source_block_name="FJL-25-2A"),
        _make_text("TOP", "1-21C-D36", 48.24, 256.60),
        _make_text("BOTTOM", "1-21n427", 48.99, 231.0),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs(
        [sheet],
        texts,
        [_make_vertical_group("GC", x=52.5, start_y=252.5, end_y=237.5)],
    )

    assert pairs == []
    assert consumed == set()


def test_extract_strip_two_port_component_pairs_accepts_clp_body() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3375", "3-21CLP7", 57.35, 209.0, layer="MARK"),
        _make_text("T3373", "1", 61.84, 193.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3372", "2", 61.9, 178.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3502", "3-21CD43", 56.49, 199.1),
        _make_text("T3503", "3-21n419", 56.49, 173.5),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs(
        [sheet],
        texts,
        [_make_vertical_group("GC0041", x=60.0, start_y=195.0, end_y=180.0)],
    )

    assert consumed == {"GC0041"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("3-21CLP7-1", "3-21CD43"),
        ("3-21CLP7-2", "3-21n419"),
    }
    assert {pair.pair_kind for pair in pairs} == {"component_mapping"}
    assert all(pair.evidence["component_submode"] == "strip_two_port_component" for pair in pairs)


def test_extract_strip_two_port_component_pairs_accepts_zlp_body() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3513", "1-2ZLP4", 250.73, 200.31, layer="MARK"),
        _make_text("T3511", "1", 254.58, 185.06, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3510", "2", 254.64, 170.06, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3647", "KD26", 252.23, 190.41),
        _make_text("T3648", "1-2n422", 249.98, 164.81),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs(
        [sheet],
        texts,
        [_make_vertical_group("GC0090", x=252.74, start_y=186.31, end_y=171.31)],
    )

    assert consumed == {"GC0090"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-2ZLP4-1", "KD26"),
        ("1-2ZLP4-2", "1-2n422"),
    }
    assert {pair.pair_kind for pair in pairs} == {"component_mapping"}
    assert all(pair.status == "pass" for pair in pairs)
    assert all(pair.evidence["component_submode"] == "strip_two_port_component" for pair in pairs)


def test_extract_strip_two_port_component_pairs_accepts_cabinet_module_clp_body() -> None:
    """Cabinet module tags like 1C3LP4 (letter+digits before LP) must map like classic KLP bodies."""
    sheet = _make_sheet()
    texts = [
        _make_text("T5337", "1C3LP4", 45.49, 241.50, layer="MARK"),
        _make_text("T5335", "1", 47.5, 227.5, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T5334", "2", 47.5, 212.5, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T5509", "1KD9", 47.0, 231.6),
        _make_text("T5510", "1n408", 46.25, 206.0),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs(
        [sheet],
        texts,
        [_make_vertical_group("GC0045", x=47.5, start_y=227.5, end_y=212.5)],
    )

    assert consumed == {"GC0045"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1C3LP4-1", "1KD9"),
        ("1C3LP4-2", "1n408"),
    }
    assert {pair.pair_kind for pair in pairs} == {"component_mapping"}
    assert all(pair.status == "pass" for pair in pairs)
    assert all(pair.evidence["component_submode"] == "strip_two_port_component" for pair in pairs)


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


def test_extract_strip_two_port_component_pairs_splits_comma_endpoint_for_same_port() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3859", "5KLP3-1,5KLP2-1", 204.3, 195.4),
        _make_text("T3860", "5n112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs([sheet], texts, [_make_vertical_group()])

    assert consumed == {"GC0132"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("5KLP10-1", "5KLP3-1"),
        ("5KLP10-1", "5KLP2-1"),
        ("5KLP10-2", "5n112"),
    }
    split_pairs = [pair for pair in pairs if pair.right_text_id == "T3859"]
    assert {pair.evidence["external_endpoint_raw"] for pair in split_pairs} == {"5KLP3-1,5KLP2-1"}
    assert {pair.evidence["external_endpoint_split"] for pair in split_pairs} == {"5KLP3-1", "5KLP2-1"}


def test_extract_strip_two_port_component_pairs_keeps_only_legal_comma_fragments() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3859", "5KLP3-1,112,A,中文说明,5KLP2-1", 204.3, 195.4),
        _make_text("T3860", "bad,5n112", 205.8, 169.8),
    ]

    pairs, consumed = extract_strip_two_port_component_pairs([sheet], texts, [_make_vertical_group()])

    assert consumed == {"GC0132"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("5KLP10-1", "5KLP3-1"),
        ("5KLP10-1", "5KLP2-1"),
        ("5KLP10-2", "5n112"),
    }


def test_extract_strip_two_port_component_pairs_skips_comma_group_without_both_sides() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("T3808", "5KLP10", 205.0, 205.3, layer="MARK"),
        _make_text("T3806", "1", 208.9, 190.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3805", "2", 208.9, 175.0, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("T3859", "112,A,中文说明", 204.3, 195.4),
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


def test_extract_strip_two_port_endpoint_bridge_pairs_builds_direct_zk_to_n_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("P1", "1", 301.844972, 193.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("P2", "2", 301.903631, 178.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("TOP", "3-21ZK-4", 296.493296, 199.103352),
        _make_text("BOTTOM", "3-21n401", 296.493296, 173.5),
    ]
    group = _make_vertical_group("GC0077", x=300.0, start_y=195.0, end_y=180.0)

    pairs, consumed = extract_strip_two_port_endpoint_bridge_pairs([sheet], texts, [group])

    assert consumed == {"GC0077"}
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.left_value == "3-21ZK-4"
    assert pair.right_value == "3-21n401"
    assert pair.left_text_id == "TOP"
    assert pair.right_text_id == "BOTTOM"
    assert pair.pair_kind == "component_mapping"
    assert pair.status == "pass"
    assert pair.evidence["component_submode"] == "strip_two_port_endpoint_bridge"
    assert pair.evidence["top_port_text_id"] == "P1"
    assert pair.evidence["bottom_port_text_id"] == "P2"
    assert pair.evidence["component_block_name"] == "FJL-25-2A_Mirror"
    assert pair.evidence["supporting_line_ids"] == ["L1"]


def test_extract_strip_two_port_endpoint_bridge_pairs_requires_matching_prefix() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("P1", "1", 381.844972, 253.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("P2", "2", 381.903631, 238.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("TOP", "1-21ZK-6", 376.493296, 259.103352),
        _make_text("BOTTOM", "3-21n401", 376.493296, 233.5),
    ]
    group = _make_vertical_group("GC0090", x=380.0, start_y=255.0, end_y=240.0)

    pairs, consumed = extract_strip_two_port_endpoint_bridge_pairs([sheet], texts, [group])

    assert pairs == []
    assert consumed == set()


def test_extract_strip_two_port_endpoint_bridge_pairs_rejects_plain_numeric_bottom() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("P1", "1", 301.844972, 193.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("P2", "2", 301.903631, 178.75, layer="0", source_block_name="FJL-25-2A_Mirror"),
        _make_text("TOP", "3-21ZK-4", 296.493296, 199.103352),
        _make_text("BOTTOM", "401", 296.493296, 173.5),
    ]
    group = _make_vertical_group("GC0077", x=300.0, start_y=195.0, end_y=180.0)

    pairs, consumed = extract_strip_two_port_endpoint_bridge_pairs([sheet], texts, [group])

    assert pairs == []
    assert consumed == set()


def test_extract_kk_multi_port_component_pairs_builds_kk2p_four_outputs() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK2P", "KK2P", x=87.5, y=252.5)
    texts = [
        _make_text("BODY", "5DK", 85.0, 279.0, layer="MARK"),
        _make_text("P1", "1", 79.0, 262.0, layer="0", source_block_name="KK2P"),
        _make_text("P2", "2", 79.0, 240.0, layer="0", source_block_name="KK2P"),
        _make_text("P3", "3", 94.0, 262.0, layer="0", source_block_name="KK2P"),
        _make_text("P4", "4", 94.0, 240.0, layer="0", source_block_name="KK2P"),
        _make_text("E1", "& ZD12", 78.0, 269.0),
        _make_text("E2", "& 5FD25", 78.0, 233.5),
        _make_text("E3", "& ZD4", 98.0, 269.0),
        _make_text("E4", "& 5FD1", 98.0, 233.5),
    ]
    groups = [
        _make_horizontal_group("G_TOP", 267.5, start_x=75.0, end_x=100.0),
        _make_horizontal_group("G_BOTTOM", 237.5, start_x=75.0, end_x=100.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G_TOP", "G_BOTTOM"}
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
    assert first.right_coord_x == 79.0
    assert first.evidence["source"] == "component_mapping"
    assert first.evidence["submode"] == "kk_multi_port_component"
    assert first.evidence["component_submode"] == "kk_multi_port_component"
    assert first.evidence["component_block_name"] == "KK2P"
    assert first.evidence["component_port_text_id"] == "P1"
    assert first.evidence["external_endpoint_text_id"] == "E1"
    assert next(pair for pair in pairs if pair.left_value == "5DK-2").evidence["external_endpoint_text_id"] == "E2"
    assert next(pair for pair in pairs if pair.left_value == "5DK-4").evidence["external_endpoint_text_id"] == "E4"


def test_extract_kk_multi_port_component_pairs_supports_of_suffix_and_letter_first_body() -> None:
    sheet = _make_sheet()
    block_name = "KK2P+OF11-12"
    block = _make_block("B_KK2P_OF", block_name, x=87.5, y=252.5)
    texts = [
        _make_text("BODY", "CJDK1", 85.0, 279.0, layer="MARK"),
        _make_text("P1", "1", 79.0, 262.0, layer="0", source_block_name=block_name),
        _make_text("P2", "2", 79.0, 240.0, layer="0", source_block_name=block_name),
        _make_text("P3", "3", 94.0, 262.0, layer="0", source_block_name=block_name),
        _make_text("P4", "4", 94.0, 240.0, layer="0", source_block_name=block_name),
        _make_text("OF11", "11", 103.0, 255.0, layer="0", source_block_name=block_name),
        _make_text("OF12", "12", 103.0, 245.0, layer="0", source_block_name=block_name),
        _make_text("OF14", "14", 103.0, 235.0, layer="0", source_block_name=block_name),
        _make_text("E1", "ZD18", 79.0, 269.0),
        _make_text("E2", "CJnP4", 79.0, 233.5),
        _make_text("E3", "ZD8", 98.0, 269.0),
        _make_text("E4", "CJnP3", 98.0, 233.5),
        _make_text("ENDPOINT_DISTRACTOR", "ZD17", 87.5, 272.0, layer="TEXT"),
    ]
    groups = [
        _make_horizontal_group("G_TOP", 267.5, start_x=75.0, end_x=100.0),
        _make_horizontal_group("G_BOTTOM", 237.5, start_x=75.0, end_x=100.0),
        _make_horizontal_group("G_AUX", 245.0, start_x=75.0, end_x=105.0),
        _make_horizontal_group("G_LONG", 255.0, start_x=20.0, end_x=105.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G_TOP", "G_BOTTOM", "G_AUX"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("CJDK1-1", "ZD18"),
        ("CJDK1-2", "CJnP4"),
        ("CJDK1-3", "ZD8"),
        ("CJDK1-4", "CJnP3"),
    }
    assert all(pair.evidence["component_block_name"] == block_name for pair in pairs)
    assert not any(pair.evidence["component_port"] in {"11", "12", "14"} for pair in pairs)


def test_extract_kk_multi_port_component_pairs_rejects_unreviewed_aux_suffix() -> None:
    sheet = _make_sheet()
    block_name = "KK2P+OF13-14"
    block = _make_block("B_BAD_OF", block_name, x=87.5, y=252.5)
    texts = [
        _make_text("BODY", "1DK", 85.0, 279.0, layer="MARK"),
        _make_text("P1", "1", 79.0, 262.0, layer="0", source_block_name=block_name),
        _make_text("E1", "ZD8", 79.0, 269.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, [], [block])

    assert pairs == []
    assert consumed == set()


def test_extract_kk_multi_port_component_pairs_builds_kk3p_six_outputs() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK3P", "KK3P", x=292.5, y=247.5)
    texts = [
        _make_text("BODY", "1-2ZKK", 289.0, 279.0, layer="MARK"),
        _make_text("P1", "1", 279.0, 257.0, layer="0", source_block_name="KK3P"),
        _make_text("P2", "2", 279.0, 235.0, layer="0", source_block_name="KK3P"),
        _make_text("P3", "3", 293.0, 257.0, layer="0", source_block_name="KK3P"),
        _make_text("P4", "4", 293.0, 235.0, layer="0", source_block_name="KK3P"),
        _make_text("P5", "5", 307.0, 257.0, layer="0", source_block_name="KK3P"),
        _make_text("P6", "6", 307.0, 235.0, layer="0", source_block_name="KK3P"),
        _make_text("E1", "& 1-2UD1", 279.0, 264.0),
        _make_text("E2", "& 1-2n719", 279.0, 228.0),
        _make_text("E3", "& 1-2UD3", 293.0, 269.0),
        _make_text("E4", "& 1-2n720", 293.0, 223.0),
        _make_text("E5", "& 1-2UD5", 307.0, 264.0),
        _make_text("E6", "& 1-2n721", 307.0, 228.0),
    ]
    groups = [
        _make_horizontal_group("G_TOP", 262.5, start_x=275.0, end_x=312.5),
        _make_horizontal_group("G_TOP_MID", 267.5, start_x=287.5, end_x=302.5),
        _make_horizontal_group("G_BOTTOM", 232.5, start_x=275.0, end_x=312.5),
        _make_horizontal_group("G_BOTTOM_MID", 227.5, start_x=287.5, end_x=302.5),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G_TOP", "G_BOTTOM", "G_BOTTOM_MID"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1-2ZKK-1", "1-2UD1"),
        ("1-2ZKK-2", "1-2n719"),
        ("1-2ZKK-3", "1-2UD3"),
        ("1-2ZKK-4", "1-2n720"),
        ("1-2ZKK-5", "1-2UD5"),
        ("1-2ZKK-6", "1-2n721"),
    }
    assert next(pair for pair in pairs if pair.left_value == "1-2ZKK-4").evidence["external_endpoint_text_id"] == "E4"


def test_extract_kk_multi_port_component_pairs_does_not_force_missing_external_endpoint() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KK2P", "KK2P", x=87.5, y=252.5)
    texts = [
        _make_text("BODY", "1-21DK2", 85.0, 279.0, layer="MARK"),
        _make_text("P1", "1", 79.0, 262.0, layer="0", source_block_name="KK2P"),
        _make_text("P2", "2", 79.0, 240.0, layer="0", source_block_name="KK2P"),
        _make_text("P3", "3", 94.0, 262.0, layer="0", source_block_name="KK2P"),
        _make_text("P4", "4", 94.0, 240.0, layer="0", source_block_name="KK2P"),
        _make_text("E1", "ZD8", 79.0, 269.0),
        _make_text("E2", "1-21GD19", 79.0, 233.5),
        _make_text("UNCLEAR", "719", 94.0, 269.0),
    ]
    groups = [
        _make_horizontal_group("G_TOP", 267.5, start_x=75.0, end_x=100.0),
        _make_horizontal_group("G_BOTTOM", 237.5, start_x=75.0, end_x=100.0),
    ]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G_TOP", "G_BOTTOM"}
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
        _make_text("BODY", "1-21ZKK", 120.0, 125.0, layer="MARK"),
        _make_text("P4", "4", 118.0, 90.0, layer="0", source_block_name="KK3P"),
        _make_text("P6", "6", 124.0, 90.0, layer="0", source_block_name="KK3P"),
        _make_text("E4", "1-21n715", 121.0, 82.0),
    ]
    groups = [_make_horizontal_group("GZ", 86.0, start_x=116.0, end_x=130.0)]

    pairs, consumed = extract_kk_multi_port_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"GZ"}
    assert len(pairs) == 1
    assert pairs[0].left_value == "1-21ZKK-4"
    assert pairs[0].right_value == "1-21n715"


def test_extract_small_port_box_component_pairs_builds_vertical_two_port_boxes() -> None:
    sheet = _make_sheet()
    ak_block = _make_block("B_AK", "KK1P", x=47.5, y=192.0)
    a_prime_block = _make_block("B_AP", "KK1P", x=77.5, y=192.0)
    texts = [
        _make_text("AK_BODY", "AK", 46.0, 218.5, layer="MARK"),
        _make_text("AK_P1", "1", 46.75, 201.79, layer="0", source_block_name="KK1P"),
        _make_text("AK_P2", "2", 46.75, 179.3, layer="0", source_block_name="KK1P"),
        _make_text("AK_E1", "JD1", 45.25, 208.6),
        _make_text("AK_E2", "A'-1", 44.5, 173.0),
        _make_text("AP_BODY", "A'", 76.0, 218.5, layer="MARK"),
        _make_text("AP_P1", "1", 76.75, 201.79, layer="0", source_block_name="KK1P"),
        _make_text("AP_P2", "2", 76.75, 179.3, layer="0", source_block_name="KK1P"),
        _make_text("AP_E1", "AK-2", 74.5, 208.6),
        _make_text("AP_E2", "JD6", 75.25, 173.0),
    ]
    groups = [
        _make_horizontal_group("G_AK1", 207.0, start_x=40.0, end_x=55.0),
        _make_horizontal_group("G_AK2", 177.0, start_x=40.0, end_x=55.0),
        _make_horizontal_group("G_AP1", 207.0, start_x=70.0, end_x=85.0),
        _make_horizontal_group("G_AP2", 177.0, start_x=70.0, end_x=85.0),
    ]

    pairs, consumed = extract_small_port_box_component_pairs([sheet], texts, groups, [ak_block, a_prime_block])

    assert consumed == {"G_AK1", "G_AK2", "G_AP1", "G_AP2"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("AK-1", "JD1"),
        ("AK-2", "A'-1"),
        ("A'-1", "AK-2"),
        ("A'-2", "JD6"),
    }
    first = next(pair for pair in pairs if pair.left_value == "AK-1")
    assert first.status == "pass"
    assert first.pair_kind == "component_mapping"
    assert first.evidence["component_submode"] == "small_port_box_component"
    assert first.evidence["component_block_name"] == "KK1P"
    assert first.evidence["component_port_text_id"] == "AK_P1"
    assert first.evidence["external_endpoint_text_id"] == "AK_E1"


def test_extract_small_port_box_component_pairs_builds_four_port_box() -> None:
    sheet = _make_sheet()
    block = _make_block("B_KZKK", "KK2P", x=117.5, y=192.5)
    texts = [
        _make_text("BODY", "KZKK", 114.5, 219.0, layer="MARK"),
        _make_text("P1", "1", 109.25, 202.29, layer="0", source_block_name="KK2P"),
        _make_text("P2", "2", 109.25, 179.8, layer="0", source_block_name="KK2P"),
        _make_text("P3", "3", 124.25, 202.28, layer="0", source_block_name="KK2P"),
        _make_text("P4", "4", 124.25, 179.8, layer="0", source_block_name="KK2P"),
        _make_text("E1", "& JD8", 103.75, 209.1),
        _make_text("E2", "K-5", 105.25, 173.5),
        _make_text("E3", "& JD3", 123.75, 209.1),
        _make_text("E4", "K-6", 125.25, 173.5),
    ]
    groups = [
        _make_horizontal_group("G1", 207.5, start_x=105.0, end_x=130.0),
        _make_horizontal_group("G2", 177.5, start_x=105.0, end_x=130.0),
    ]

    pairs, consumed = extract_small_port_box_component_pairs([sheet], texts, groups, [block])

    assert consumed == {"G1", "G2"}
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("KZKK-1", "JD8"),
        ("KZKK-2", "K-5"),
        ("KZKK-3", "JD3"),
        ("KZKK-4", "K-6"),
    }
    assert {pair.evidence["external_endpoint_raw"] for pair in pairs if pair.right_value in {"JD8", "JD3"}} == {
        "& JD8",
        "& JD3",
    }


def test_extract_small_port_box_component_pairs_builds_horizontal_jr_box() -> None:
    sheet = _make_sheet()
    block = _make_block("B_JR", "JR-01", x=207.5, y=39.5)
    texts = [
        _make_text("BODY", "JR", 206.0, 64.0, layer="MARK"),
        _make_text("P1", "1", 202.9, 35.5, layer="0", source_block_name="JR-01"),
        _make_text("P2", "2", 210.4, 35.5, layer="0", source_block_name="JR-01"),
        _make_text("E1", "K-3 &", 205.25, 40.5, bbox=(205.25, 39.45, 214.55, 42.9)),
        _make_text("E2", "K-4 &", 212.75, 40.5, bbox=(212.75, 39.45, 222.05, 42.9)),
    ]
    groups: list[LineGroup] = []

    pairs, consumed = extract_small_port_box_component_pairs([sheet], texts, groups, [block])

    assert consumed == set()
    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("JR-1", "K-3"),
        ("JR-2", "K-4"),
    }


def test_extract_small_port_box_component_pairs_requires_plain_mark_body() -> None:
    sheet = _make_sheet()
    block = _make_block("B_BAD", "KK1P", x=47.5, y=192.0)
    texts = [
        _make_text("BODY", "1DK", 46.0, 218.5, layer="MARK"),
        _make_text("P1", "1", 46.75, 201.79, layer="0", source_block_name="KK1P"),
        _make_text("P2", "2", 46.75, 179.3, layer="0", source_block_name="KK1P"),
        _make_text("E1", "JD1", 45.25, 208.6),
        _make_text("E2", "A'-1", 44.5, 173.0),
    ]

    pairs, consumed = extract_small_port_box_component_pairs([sheet], texts, [], [block])

    assert pairs == []
    assert consumed == set()
