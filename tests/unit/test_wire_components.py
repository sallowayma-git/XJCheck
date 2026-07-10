from dwg_audit.audit.wire_components import extract_component_prefixed_signal_pairs
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem


def _make_sheet(sheet_category: str = "二次原理图") -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="16 高低压侧操作箱信号回路.dwg",
        sheet_order=16,
        sheet_no="16",
        sheet_title="高低压侧操作箱信号回路",
        sheet_category=sheet_category,
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


def test_extract_component_prefixed_signal_pairs_builds_scoped_visible_prefix_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("P1", "1n", 165.0, 279.5),
        _make_text("L1", "701", 135.6, 265.6),
        _make_text("E1", "1ID1", 80.0, 267.0),
        _make_text("L2", "702", 190.1, 265.6),
        _make_text("E2", "1ID4", 207.5, 267.5),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("1ID1", "1n701"),
        ("1ID4", "1n702"),
    }
    first = next(pair for pair in pairs if pair.left_value == "1ID1")
    assert first.status == "pass"
    assert first.pair_kind == "wire_component_mapping"
    assert first.evidence["component_submode"] == "scoped_visible_prefix_external_endpoint_mapping"
    assert first.evidence["scoped_prefix"] == "1n"
    assert first.evidence["external_endpoint"] == "1ID1"
    assert first.evidence["logical_endpoint"] == "1n701"


def test_extract_component_prefixed_signal_pairs_builds_input_matrix_wire_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("MP1", "1-21n", 120.0, 274.5),
        _make_text("MP1_DUP", "1-21n", 120.4, 274.6),
        _make_text("MP2", "1-21n", 180.0, 274.5),
        _make_text("RE1", "1-21QD12", 70.0, 87.12),
        _make_text("N1", "127", 90.6, 85.67),
        _make_text("RE2", "1-21QD28", 70.0, 120.0),
        _make_text("N2", "212", 90.6, 119.0),
        _make_text("RE3", "1-21QD44", 70.0, 151.0),
        _make_text("N3", "228", 90.6, 150.0),
        _make_text("LABEL1", "BI", 82.0, 85.7),
        _make_text("LABEL2", "开入", 82.0, 119.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert ("1-21QD12", "1-21n127") in pair_values
    assert ("1-21QD28", "1-21n212") in pair_values
    assert ("1-21QD44", "1-21n228") in pair_values
    assert len(pair_values) == 3
    first = next(pair for pair in pairs if pair.left_value == "1-21QD12")
    assert first.status == "pass"
    assert first.confidence == 0.95
    assert first.pair_kind == "wire_component_mapping"
    assert first.evidence["source"] == "wire_component_mapping"
    assert first.evidence["component_submode"] == "input_matrix_wire_mapping"
    assert first.evidence["matrix_prefix"] == "1-21n"
    assert first.evidence["matrix_prefix_text_id"] == "MP1"
    assert first.evidence["row_endpoint"] == "1-21QD12"
    assert first.evidence["local_number"] == "127"
    assert first.evidence["logical_endpoint"] == "1-21n127"
    assert first.evidence["row_band_id"]
    assert first.evidence["column_band_id"]


def test_extract_component_prefixed_signal_pairs_requires_input_matrix_gate() -> None:
    secondary_sheet = _make_sheet(sheet_category="一次接线图")
    missing_prefix_sheet = _make_sheet()
    texts = [
        _make_text("MP1", "1-21n", 120.0, 274.5),
        _make_text("MP2", "1-21n", 180.0, 274.5),
        _make_text("RE1", "1-21QD12", 70.0, 87.12),
        _make_text("N1", "127", 90.6, 85.67),
        _make_text("RE2", "1-21QD28", 70.0, 120.0),
        _make_text("N2", "212", 90.6, 119.0),
    ]

    assert extract_component_prefixed_signal_pairs([secondary_sheet], texts) == []
    assert extract_component_prefixed_signal_pairs([missing_prefix_sheet], texts[2:]) == []


def test_extract_component_prefixed_signal_pairs_builds_first_prefixed_external_endpoint_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("E1", "1QD5", 110.0, 229.2),
        _make_text("N1", "105", 135.6, 228.2),
        _make_text("E2", "1-2QD12", 110.0, 190.0),
        _make_text("N2", "105", 136.0, 189.2),
        _make_text("E3", "3-2QD12", 110.0, 150.0),
        _make_text("N3", "105", 136.0, 149.2),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {
        ("1QD5", "1n105"),
        ("1-2QD12", "1-2n105"),
        ("3-2QD12", "3-2n105"),
    }
    first = next(pair for pair in pairs if pair.left_value == "1QD5")
    assert first.status == "pass"
    assert first.pair_kind == "wire_component_mapping"
    assert first.evidence["component_submode"] == "first_prefixed_external_endpoint_mapping"
    assert first.evidence["external_endpoint"] == "1QD5"
    assert first.evidence["local_number"] == "105"
    assert first.evidence["logical_endpoint"] == "1n105"


def test_extract_component_prefixed_signal_pairs_builds_fd_first_prefixed_external_endpoint_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("E1", "5FD25", 135.0, 262.0),
        _make_text("N1", "105", 155.6, 260.7),
    ]

    pairs = extract_component_prefixed_signal_pairs(
        [sheet],
        texts,
        first_prefixed_eligible_local_text_ids={"N1"},
    )

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {("5FD25", "5n105")}
    first = pairs[0]
    assert first.evidence["component_submode"] == "first_prefixed_external_endpoint_mapping"
    assert first.evidence["external_endpoint"] == "5FD25"
    assert first.evidence["local_number"] == "105"
    assert first.evidence["logical_endpoint"] == "5n105"


def test_extract_component_prefixed_signal_pairs_prefers_visible_scope_over_first_prefixed_fallback() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("P1", "5n", 185.0, 279.5),
        _make_text("E1", "5FD25", 135.0, 262.0),
        _make_text("N1", "105", 155.6, 260.7),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {("5FD25", "5n105")}
    assert len(pairs) == 1
    assert pairs[0].evidence["component_submode"] == "scoped_visible_prefix_external_endpoint_mapping"


def test_extract_component_prefixed_signal_pairs_filters_first_prefixed_by_eligible_local_text_ids() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("E1", "1QD5", 110.0, 229.2),
        _make_text("N1", "105", 135.6, 228.2),
        _make_text("E2", "1QD6", 110.0, 210.0),
        _make_text("N2", "132", 136.0, 209.2),
        _make_text("E3", "5FD25", 110.0, 190.0),
        _make_text("N3", "105", 136.0, 189.2),
    ]

    pairs = extract_component_prefixed_signal_pairs(
        [sheet],
        texts,
        first_prefixed_eligible_local_text_ids={"N1"},
    )

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {("1QD5", "1n105")}


def test_extract_component_prefixed_signal_pairs_keeps_input_matrix_separate_from_first_prefixed() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("MP1", "1-21n", 120.0, 274.5),
        _make_text("MP2", "1-21n", 180.0, 274.5),
        _make_text("RE1", "1-21QD12", 70.0, 87.12),
        _make_text("N1", "127", 90.6, 85.67),
        _make_text("RE2", "1-21QD28", 70.0, 120.0),
        _make_text("N2", "212", 90.6, 119.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert pair_values == {
        ("1-21QD12", "1-21n127"),
        ("1-21QD28", "1-21n212"),
    }
    assert all(
        pair.evidence["component_submode"] == "input_matrix_wire_mapping"
        for pair in pairs
    )


def test_extract_component_prefixed_signal_pairs_rejects_unapproved_first_prefixed_letters() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("E1", "5DK25", 110.0, 229.2),
        _make_text("N1", "105", 135.6, 228.2),
        _make_text("E2", "5YD25", 110.0, 210.0),
        _make_text("N2", "106", 136.0, 209.2),
        _make_text("E3", "5FX25", 110.0, 190.0),
        _make_text("N3", "107", 136.0, 189.2),
    ]

    pairs = extract_component_prefixed_signal_pairs(
        [sheet],
        texts,
        first_prefixed_eligible_local_text_ids={"N1", "N2", "N3"},
    )

    assert pairs == []


def test_extract_component_prefixed_signal_pairs_requires_secondary_sheet_for_first_prefixed() -> None:
    sheet = _make_sheet(sheet_category="一次接线图")
    texts = [
        _make_text("E1", "1QD5", 110.0, 229.2),
        _make_text("N1", "105", 135.6, 228.2),
    ]

    assert extract_component_prefixed_signal_pairs([sheet], texts) == []


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


def test_extract_component_prefixed_signal_pairs_supports_single_sided_inline_klp_local_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("B1", "5KLP1", 115.0, 231.625),
        _make_text("P1", "1", 109.374302, 227.252793),
        _make_text("P2", "2", 119.374302, 227.252793),
        _make_text("E1", "207", 155.622905, 230.657933),
    ]

    lines = [
        _make_line("L1", 120.0, 230.0, 157.5, 230.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts, lines)

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("5KLP1-2", "5n207"),
    }
    first = pairs[0]
    assert first.evidence["component_submode"] == "inline_klp_component_port_mapping"
    assert first.evidence["local_number"] == "207"
    assert first.evidence["local_number_text_id"] == "E1"
    assert first.evidence["endpoint_side"] == "right"


def test_extract_component_prefixed_signal_pairs_builds_inline_zkk_body_port_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("B1", "3-2ZKK", 315.0, 153.65),
        _make_text("P1", "1", 304.374302, 150.934916),
        _make_text("P2", "2", 324.374302, 150.941899),
        _make_text("E1", "719", 335.625, 150.605016),
        _make_text("P3", "3", 304.374302, 140.927933),
        _make_text("P4", "4", 324.374302, 140.941899),
        _make_text("E2", "720", 335.625, 140.605016),
        _make_text("P5", "5", 304.374302, 130.941899),
        _make_text("P6", "6", 324.374302, 130.927933),
        _make_text("E3", "721", 335.625, 130.632793),
    ]

    lines = [
        _make_line("L1", 325.0, 150.0, 337.5, 150.0),
        _make_line("L2", 325.0, 140.0, 337.5, 140.0),
        _make_line("L3", 325.0, 130.0, 337.5, 130.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts, lines)

    assert {(pair.left_value, pair.right_value) for pair in pairs} == {
        ("3-2ZKK-2", "719"),
        ("3-2ZKK-4", "720"),
        ("3-2ZKK-6", "721"),
    }
    first = next(pair for pair in pairs if pair.left_value == "3-2ZKK-2")
    assert first.evidence["component_submode"] == "inline_body_port_mapping"
    assert first.evidence["component_family"] == "ZKK"
    assert first.evidence["local_number_text_id"] == "E1"


def test_extract_component_prefixed_signal_pairs_builds_scoped_wire_logic_body_port_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("SP1", "3-21n", 285.0, 217.0),
        _make_text("B1", "3-21DK1", 196.423569, 210.461523),
        _make_text("P1", "1", 186.874302, 198.784916),
        _make_text("P2", "2", 206.874302, 198.791899),
        _make_text("E1", "105", 265.622905, 198.162655),
        _make_text("P3", "3", 186.874302, 208.777933),
        _make_text("P4", "4", 206.874302, 208.791899),
        _make_text("E2", "103", 265.622905, 208.162655),
        _make_text("SP2", "1-21n", 285.0, 284.5),
        _make_text("B2", "1-21DK1", 196.423569, 277.961523),
        _make_text("P5", "1", 186.874302, 266.284916),
        _make_text("P6", "2", 206.874302, 266.291899),
        _make_text("E3", "105", 265.622905, 265.662655),
        _make_text("P7", "3", 186.874302, 276.277933),
        _make_text("P8", "4", 206.874302, 276.291899),
        _make_text("E4", "103", 265.622905, 275.662655),
    ]

    lines = [
        _make_line("L1", 207.5, 197.5, 267.5, 197.5),
        _make_line("L2", 207.5, 207.5, 267.5, 207.5),
        _make_line("L3", 207.5, 265.0, 267.5, 265.0),
        _make_line("L4", 207.5, 275.0, 267.5, 275.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts, lines)

    pair_values = {(pair.left_value, pair.right_value) for pair in pairs}
    assert {
        ("3-21DK1-2", "3-21n105"),
        ("1-21DK1-2", "1-21n105"),
    } <= pair_values
    assert ("3-21DK1-4", "3-21n103") not in pair_values
    assert ("1-21DK1-4", "1-21n103") not in pair_values
    first = next(pair for pair in pairs if pair.left_value == "3-21DK1-2")
    assert first.evidence["component_submode"] == "inline_body_port_mapping"
    assert first.evidence["component_body"] == "3-21DK1"
    assert first.evidence["component_port"] == "2"
    assert first.evidence["local_number"] == "105"


def test_extract_component_prefixed_signal_pairs_requires_line_evidence_for_scoped_wire_logic_body_port_mapping() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("SP1", "3-21n", 285.0, 217.0),
        _make_text("B1", "3-21DK1", 196.423569, 210.461523),
        _make_text("P1", "1", 186.874302, 198.784916),
        _make_text("P2", "2", 206.874302, 198.791899),
        _make_text("E1", "105", 265.622905, 198.162655),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts)

    assert pairs == []


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


def test_extract_component_prefixed_signal_pairs_keeps_unanchored_inline_local_number_row() -> None:
    sheet = _make_sheet()
    texts = [
        _make_text("B1", "1KLP1", 130.0, 105.0),
        _make_text("P1", "1", 120.0, 100.0),
        _make_text("P2", "2", 140.0, 100.0),
        _make_text("E2", "116", 170.0, 111.0),
    ]

    lines = [
        _make_line("L2", 140.0, 100.0, 168.0, 100.0),
    ]

    pairs = extract_component_prefixed_signal_pairs([sheet], texts, lines)

    assert pairs == []
