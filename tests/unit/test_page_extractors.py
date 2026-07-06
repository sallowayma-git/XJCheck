from dwg_audit.audit.page_extractors import _mark_terminal_prefixed_endpoint_ordinary_pairs
from dwg_audit.domain.models import Pair


def _pair(evidence: dict[str, object]) -> Pair:
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
        pair_kind="ordinary_pair",
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
