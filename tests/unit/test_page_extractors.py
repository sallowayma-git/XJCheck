from dwg_audit.audit.page_extractors import _mark_input_matrix_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_terminal_prefixed_endpoint_ordinary_pairs
from dwg_audit.domain.models import Pair


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
