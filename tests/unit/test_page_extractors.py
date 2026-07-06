from dwg_audit.audit.page_extractors import _mark_input_matrix_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_schematic_ac_phase_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_terminal_prefixed_endpoint_ordinary_pairs
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord


def _pair(
    evidence: dict[str, object],
    *,
    pair_kind: str = "ordinary_pair",
    left_text_id: str | None = None,
    right_text_id: str | None = None,
) -> Pair:
    return Pair(
        pair_id="P1",
        line_group_id="G1",
        sheet_id="S1",
        file_id="F1",
        selected_pair_candidate_id="PC1",
        left_value="21",
        right_value="211",
        confidence=0.81,
        status="review",
        rationale="left=21 right=211 score=0.81",
        alternative_pair_candidate_ids=[],
        confidence_bucket="review",
        evidence=evidence,
        left_text_id=left_text_id,
        right_text_id=right_text_id,
        pair_kind=pair_kind,
    )


def _sheet(category: str = "二次原理图") -> SheetRecord:
    return SheetRecord("S1", "F1", "04 交流回路图1.dwg", 4, "04", "CT AND VT INPUT", category, "primary", "filename", True)


def test_mark_terminal_prefixed_endpoint_ordinary_pairs_discards_bare_suffix_pair() -> None:
    pair = _pair(
        {
            "selected_left_text_id": "T1",
            "selected_right_text_id": "T2",
            "selected_left_raw_text": "21",
            "selected_right_raw_text": "3-21n211",
            "selected_left_is_derived_numeric": False,
            "selected_right_is_derived_numeric": True,
        }
    )
    table_mappings = [
        {
            "sheet_id": "S1",
            "mappings": [
                {
                    "mapping_mode": "terminal_header_table",
                    "middle_text_id": "T1",
                    "right_text_id": "T2",
                }
            ],
        }
    ]

    _mark_terminal_prefixed_endpoint_ordinary_pairs([pair], table_mappings)

    assert pair.status == "discard"
    assert pair.confidence_bucket == "low"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["covered_by_terminal_structured_endpoint"] is True


def test_mark_terminal_prefixed_endpoint_ordinary_pairs_keeps_plain_terminal_pair() -> None:
    pair = _pair(
        {
            "selected_left_text_id": "T1",
            "selected_right_text_id": "T2",
            "selected_left_raw_text": "21",
            "selected_right_raw_text": "211",
            "selected_left_is_derived_numeric": False,
            "selected_right_is_derived_numeric": False,
        }
    )

    _mark_terminal_prefixed_endpoint_ordinary_pairs([pair], [])

    assert pair.status == "review"
    assert "ordinary_pair_eligible" not in pair.evidence


def test_mark_terminal_prefixed_endpoint_ordinary_pairs_keeps_uncovered_row_lock() -> None:
    pair = _pair(
        {
            "selected_left_text_id": "T1",
            "selected_right_text_id": "T2",
            "selected_left_raw_text": "21",
            "selected_right_raw_text": "3-21n211",
            "selected_left_is_derived_numeric": False,
            "selected_right_is_derived_numeric": True,
        }
    )

    _mark_terminal_prefixed_endpoint_ordinary_pairs([pair], [])

    assert pair.status == "review"
    assert "ordinary_pair_eligible" not in pair.evidence


def test_mark_input_matrix_covered_ordinary_pairs_discards_bare_local_number_pair() -> None:
    ordinary = _pair({}, right_text_id="LOCAL127")
    matrix_pair = _pair(
        {
            "component_submode": "input_matrix_wire_mapping",
            "local_number_text_id": "LOCAL127",
        },
        pair_kind="wire_component_mapping",
        right_text_id="LOCAL127",
    )

    _mark_input_matrix_covered_ordinary_pairs([ordinary], [matrix_pair])

    assert ordinary.status == "discard"
    assert ordinary.confidence_bucket == "low"
    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["covered_by_input_matrix_wire_mapping"] is True


def test_mark_input_matrix_covered_ordinary_pairs_keeps_uncovered_or_structured_pairs() -> None:
    uncovered = _pair({}, right_text_id="LOCAL212")
    structured = _pair(
        {
            "component_submode": "input_matrix_wire_mapping",
            "local_number_text_id": "LOCAL127",
        },
        pair_kind="wire_component_mapping",
        right_text_id="LOCAL127",
    )

    _mark_input_matrix_covered_ordinary_pairs([uncovered, structured], [structured])

    assert uncovered.status == "review"
    assert structured.status == "review"
    assert "covered_by_input_matrix_wire_mapping" not in uncovered.evidence


def test_mark_input_matrix_covered_ordinary_pairs_discards_component_prefixed_local_number_pair() -> None:
    ordinary = _pair({}, right_text_id="LOCAL218")
    component_pair = _pair(
        {
            "component_submode": "component_prefixed_signal_circuit",
            "local_number_text_id": "LOCAL218",
            "external_endpoint_text_id": "EXT1",
        },
        pair_kind="wire_component_mapping",
        left_text_id="LOCAL218",
        right_text_id="EXT1",
    )

    _mark_input_matrix_covered_ordinary_pairs([ordinary], [component_pair])

    assert ordinary.status == "discard"
    assert ordinary.confidence_bucket == "low"
    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["covered_by_component_prefixed_signal_circuit"] is True
    assert "component local number" in ordinary.rationale


def test_mark_input_matrix_covered_ordinary_pairs_keeps_component_prefixed_external_endpoint_pair() -> None:
    ordinary = _pair({}, right_text_id="EXT1")
    component_pair = _pair(
        {
            "component_submode": "component_prefixed_signal_circuit",
            "local_number_text_id": "LOCAL218",
            "external_endpoint_text_id": "EXT1",
        },
        pair_kind="wire_component_mapping",
        left_text_id="LOCAL218",
        right_text_id="EXT1",
    )

    _mark_input_matrix_covered_ordinary_pairs([ordinary], [component_pair])

    assert ordinary.status == "review"
    assert "covered_by_component_prefixed_signal_circuit" not in ordinary.evidence


def test_mark_schematic_ac_phase_covered_ordinary_pairs_discards_shared_numeric_half_pair() -> None:
    ordinary = _pair(
        {
            "selected_right_text_id": "AC719",
        },
        right_text_id="AC719",
    )
    ordinary.left_value = None
    ordinary.right_value = "719"
    semantic = _pair(
        {
            "semantic_kind": "schematic_semantic_annotation",
            "semantic_mapping_kind": "schematic_ac_phase_label",
            "numeric_endpoint_text_id": "AC719",
            "semantic_endpoint_text_id": "PHASE_UC",
        },
        pair_kind="semantic_mapping",
        left_text_id="AC719",
    )

    _mark_schematic_ac_phase_covered_ordinary_pairs([ordinary, semantic], [_sheet()])

    assert ordinary.status == "discard"
    assert ordinary.confidence_bucket == "low"
    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["covered_by_schematic_ac_phase_label_semantic_mapping"] is True
    assert "AC phase numeric text" in ordinary.rationale
    assert semantic.status == "review"


def test_mark_schematic_ac_phase_covered_ordinary_pairs_keeps_non_ac_semantic_and_complete_pairs() -> None:
    ordinary = _pair({"selected_right_text_id": "DC611"}, right_text_id="DC611")
    ordinary.left_value = None
    ordinary.right_value = "611"
    complete = _pair({"selected_left_text_id": "AC719"}, left_text_id="AC719")
    complete.left_value = "719"
    complete.right_value = "UC"
    dc_semantic = _pair(
        {
            "semantic_mapping_kind": "schematic_dc_function_label",
            "numeric_endpoint_text_id": "DC611",
        },
        pair_kind="semantic_mapping",
        left_text_id="DC611",
    )
    ac_semantic = _pair(
        {
            "semantic_kind": "schematic_semantic_annotation",
            "semantic_mapping_kind": "schematic_ac_phase_label",
            "numeric_endpoint_text_id": "AC719",
        },
        pair_kind="semantic_mapping",
        left_text_id="AC719",
    )

    _mark_schematic_ac_phase_covered_ordinary_pairs([ordinary, complete, dc_semantic, ac_semantic], [_sheet()])

    assert ordinary.status == "review"
    assert "covered_by_schematic_ac_phase_label_semantic_mapping" not in ordinary.evidence
    assert complete.status == "review"
    assert "covered_by_schematic_ac_phase_label_semantic_mapping" not in complete.evidence


def test_mark_schematic_ac_phase_covered_ordinary_pairs_keeps_terminal_semantic_row_scope() -> None:
    ordinary = _pair({"selected_right_text_id": "AC719"}, right_text_id="AC719")
    ordinary.left_value = None
    ordinary.right_value = "719"
    terminal_semantic = _pair(
        {
            "semantic_kind": "terminal_semantic_mapping",
            "semantic_mapping_kind": "terminal_semantic_row",
            "numeric_endpoint_text_id": "AC719",
        },
        pair_kind="semantic_mapping",
        left_text_id="AC719",
    )

    _mark_schematic_ac_phase_covered_ordinary_pairs([ordinary, terminal_semantic], [_sheet("屏端子图")])

    assert ordinary.status == "review"
    assert "covered_by_schematic_ac_phase_label_semantic_mapping" not in ordinary.evidence
