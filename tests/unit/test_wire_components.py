from dwg_audit.audit.wire_components import extract_component_prefixed_signal_pairs
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem


def _make_sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="16 高低压侧操作箱信号回路.dwg",
        sheet_order=16,
        sheet_no="16",
        sheet_title="高低压侧操作箱信号回路",
        sheet_category="二次原理图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_area_bbox=(0.0, 0.0, 420.0, 280.0),
    )


def _make_text(text_id: str, value: str, x: float, y: float) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{text_id}",
        entity_type="TEXT",
        text=value,
        normalized_text=value,
        is_numeric_candidate=value.isdigit(),
        layer="DIM",
        rotation_deg=0.0,
        height=2.5,
        insert_x=x,
        insert_y=y,
        bbox_min_x=x - 2.0,
        bbox_min_y=y - 1.0,
        bbox_max_x=x + 2.0,
        bbox_max_y=y + 1.0,
    )


def _make_line(line_id: str, start_x: float, start_y: float, end_x: float, end_y: float) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=f"H{line_id}",
        source_entity_type="LINE",
        layer="CONNECT",
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        bbox_min_x=min(start_x, end_x),
        bbox_min_y=min(start_y, end_y),
        bbox_max_x=max(start_x, end_x),
        bbox_max_y=max(start_y, end_y),
        length=((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5,
        angle_deg=0.0,
    )


def test_extract_component_prefixed_signal_pairs_builds_logical_endpoint_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("P1", "1-2n", 130.0, 274.5),
        _make_text("L1", "218", 101.9, 263.8),
        _make_text("E1", "1-4YD1", 75.0, 264.5),
        _make_text("L2", "221", 154.4, 263.8),
        _make_text("E2", "1-4YD4", 182.5, 264.5),
        _make_text("P2", "3-2n", 295.0, 274.5),
        _make_text("L3", "218", 266.9, 263.8),
        _make_text("E3", "3-4YD1", 240.0, 264.5),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("1-2n218", "1-4YD1") in pair_values
    assert ("1-2n221", "1-4YD4") in pair_values
    assert ("3-2n218", "3-4YD1") in pair_values
    first = next(pair for pair in pairs if pair.left_value == "1-2n218")
    assert first.status == "pass"
    assert first.confidence == 0.95
    assert first.pair_kind == "wire_component_mapping"
    assert first.evidence["source"] == "wire_component_mapping"
    assert first.evidence["component_submode"] == "component_prefixed_signal_circuit"
    assert first.evidence["component_prefix"] == "1-2n"


def test_extract_component_prefixed_signal_pairs_builds_inline_klp_port_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("B1", "3-2KLP1", 130.0, 105.0),
        _make_text("P1", "1", 120.0, 100.0),
        _make_text("E1", "3-2QD2", 90.0, 105.5),
        _make_text("P2", "2", 140.0, 100.0),
        _make_text("E2", "116", 170.0, 104.5),
        _make_text("B2", "1KLP1", 130.0, 55.0),
        _make_text("P3", "1", 120.0, 50.0),
        _make_text("E3", "1QD2", 90.0, 55.5),
        _make_text("P4", "2", 140.0, 50.0),
        _make_text("E4", "116", 170.0, 54.5),
    ]

    lines = [
        _make_line("L1", 92.0, 100.0, 120.0, 100.0),
        _make_line("L2", 140.0, 100.0, 168.0, 100.0),
        _make_line("L3", 92.0, 50.0, 120.0, 50.0),
        _make_line("L4", 140.0, 50.0, 168.0, 50.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts, lines)

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {
        ("3-2KLP1-1", "3-2QD2"),
        ("3-2KLP1-2", "3-2n116"),
        ("1KLP1-1", "1QD2"),
        ("1KLP1-2", "1n116"),
    }
    first = next(pair for pair in pairs if pair.left_value == "3-2KLP1-1")
    assert first.status == "pass"
    assert first.pair_kind == "wire_component_mapping"
    assert first.evidence["component_submode"] == "inline_klp_component_port_mapping"
    assert first.evidence["component_body"] == "3-2KLP1"
    assert first.evidence["component_port"] == "1"
    assert first.evidence["supporting_line_ids"]


def test_extract_component_prefixed_signal_pairs_requires_inline_klp_line_evidence() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("B1", "3-2KLP1", 130.0, 105.0),
        _make_text("P1", "1", 120.0, 100.0),
        _make_text("E1", "3-2QD2", 90.0, 105.5),
        _make_text("P2", "2", 140.0, 100.0),
        _make_text("E2", "116", 170.0, 104.5),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    assert pairs == []


def test_extract_component_prefixed_signal_pairs_requires_complete_inline_klp_row() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("B1", "1KLP1", 130.0, 105.0),
        _make_text("P1", "1", 120.0, 100.0),
        _make_text("E1", "1QD2", 90.0, 105.5),
        _make_text("P2", "2", 140.0, 100.0),
        _make_text("E2", "116", 170.0, 111.0),
    ]

    lines = [
        _make_line("L1", 92.0, 100.0, 120.0, 100.0),
        _make_line("L2", 140.0, 100.0, 168.0, 100.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts, lines)

    assert pairs == []
