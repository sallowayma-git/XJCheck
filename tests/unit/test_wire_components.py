from dwg_audit.audit.wire_components import extract_component_prefixed_signal_pairs
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
