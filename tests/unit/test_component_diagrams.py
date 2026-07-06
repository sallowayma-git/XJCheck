from dwg_audit.audit.component_diagrams import extract_strip_two_port_component_pairs
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
) -> TextItem:
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
        bbox_min_x=x,
        bbox_min_y=y - 1.0,
        bbox_max_x=x + 2.0,
        bbox_max_y=y + 1.0,
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
