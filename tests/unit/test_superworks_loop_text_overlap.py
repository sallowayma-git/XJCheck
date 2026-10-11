"""Stacked contradictory texts at one position (叠放矛盾文字).

Rule: when texts with different values share one position and their drawing order can be read
(hex DXF handles from one file, all independent model-space entities, pairwise distinct), the
latest text is used and earlier stacked texts are dropped with evidence only. When the order
cannot be read, the port stays unresolved for review and the issue names the overlapping values
("检测到文字重叠").
"""

from __future__ import annotations

from dwg_audit.audit import rules as R
from dwg_audit.audit.component_diagrams import extract_strip_two_port_component_pairs
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.extract.text_overlap import handle_order_key
from dwg_audit.extract.text_overlap import overlap_detected_text
from dwg_audit.extract.text_overlap import resolve_overlapping_texts
from dwg_audit.utils.config import DEFAULT_CONFIG


OLD_HANDLE = "12875"  # early batch, e.g. the 8nB01 label
NEW_HANDLE = "134B4"  # late batch, e.g. the 8n401 label


def _sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="12 元件接线图2.dwg",
        sheet_order=12,
        sheet_no="12",
        sheet_title="元件接线图2",
        sheet_category="元件接线图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        page_type="元件接线图",
        page_subtype="horizontal_component",
        route_target="ComponentDiagramExtractor",
        audit_disposition="audit_required",
    )


def _text(
    text_id: str,
    value: str,
    handle: str,
    x: float = 205.8,
    y: float = 169.8,
    *,
    file_id: str = "F1",
    layer: str = "0",
    entity_type: str = "TEXT",
    source_block_name: str | None = None,
) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id=file_id,
        handle=handle,
        entity_type=entity_type,
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


def _support_group() -> LineGroup:
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


def _strip_texts(*bottom_stack: TextItem) -> list[TextItem]:
    """A two-port strip (ports 1 and 2 in a block), a top label, and the stacked bottom labels."""
    return [
        _text("BODY", "8KLP3", "BODY", 205.0, 205.3, layer="MARK"),
        _text("P1", "1", "INS1:VIRTUAL:0", 208.9, 190.0, source_block_name="FJL-25-2A_Mirror"),
        _text("P2", "2", "INS1:VIRTUAL:1", 208.9, 175.0, source_block_name="FJL-25-2A_Mirror"),
        _text("TOP", "8KLP2-1", "TOPH", 204.3, 195.4),
        *bottom_stack,
    ]


def _extract(texts: list[TextItem]):
    group = _support_group()
    pairs, consumed = extract_strip_two_port_component_pairs([_sheet()], texts, [group])
    assert consumed == {"GC0132"}
    bottom = next(pair for pair in pairs if pair.evidence.get("endpoint_side") == "bottom")
    return pairs, bottom, group


def _missing_side_issue(pairs, group, pair_id: str):
    issues = R.build_issues(pairs, [group], [_sheet()], DEFAULT_CONFIG)
    return next(
        (item for item in issues if item.rule_id == "R-PAIR-MISSING-SIDE" and item.pair_id == pair_id),
        None,
    )


# --- helper: handle order and resolution ---------------------------------------------------------

def test_handle_order_key_accepts_plain_model_space_hex_only() -> None:
    assert handle_order_key(_text("A", "8n401", NEW_HANDLE)) == int(NEW_HANDLE, 16)
    assert handle_order_key(_text("B", "8n401", "HBOTTOM")) is None
    assert handle_order_key(_text("C", "8n401", "INS1:VIRTUAL:0")) is None
    assert handle_order_key(_text("D", "8n401", NEW_HANDLE, source_block_name="FJL")) is None
    assert handle_order_key(_text("E", "8n401", NEW_HANDLE, entity_type="ATTRIB")) is None


def test_resolution_takes_latest_handle_and_lists_superseded_text() -> None:
    early = _text("EARLY", "8nB01", OLD_HANDLE)
    late = _text("LATE", "8n401", NEW_HANDLE)

    resolution = resolve_overlapping_texts([early, late])

    assert resolution.resolved
    assert resolution.reason == "latest_handle"
    assert resolution.winner is late
    assert [item["text_id"] for item in resolution.superseded_evidence()] == ["EARLY"]
    assert resolution.superseded_evidence()[0] == {"text_id": "EARLY", "value": "8nB01", "handle": OLD_HANDLE}


def test_resolution_is_order_independent() -> None:
    early = _text("EARLY", "8nB01", OLD_HANDLE)
    late = _text("LATE", "8n401", NEW_HANDLE)

    assert resolve_overlapping_texts([late, early]).winner is late
    assert resolve_overlapping_texts([early, late]).winner is late


def test_three_stacked_texts_take_the_largest_handle() -> None:
    texts = [
        _text("T1", "8nB01", "12870"),
        _text("T2", "8n401", OLD_HANDLE),
        _text("T3", "8n402", NEW_HANDLE),
    ]

    resolution = resolve_overlapping_texts(texts)

    assert resolution.winner is texts[2]
    assert sorted(item["text_id"] for item in resolution.superseded_evidence()) == ["T1", "T2"]


def test_earlier_text_with_the_winner_value_is_not_superseded() -> None:
    same_value_early = _text("SAME", "8n401", OLD_HANDLE)
    other_early = _text("OTHER", "8nB01", "12870")
    late = _text("LATE", "8n401", NEW_HANDLE)

    resolution = resolve_overlapping_texts([same_value_early, other_early, late])

    assert resolution.winner is late
    assert [item["text_id"] for item in resolution.superseded_evidence()] == ["OTHER"]


def test_equal_handles_are_not_comparable() -> None:
    resolution = resolve_overlapping_texts([_text("A", "8nB01", NEW_HANDLE), _text("B", "8n401", NEW_HANDLE)])

    assert resolution.winner is None
    assert resolution.reason == "duplicate_handle"
    assert resolution.values == ("8n401", "8nB01")


def test_non_hex_handle_is_not_comparable() -> None:
    resolution = resolve_overlapping_texts([_text("A", "8nB01", OLD_HANDLE), _text("B", "8n401", "HBOTTOM")])

    assert resolution.winner is None
    assert resolution.reason == "handle_not_comparable"


def test_block_internal_text_is_not_comparable_with_model_space_text() -> None:
    resolution = resolve_overlapping_texts([
        _text("A", "8nB01", OLD_HANDLE),
        _text("B", "8n401", NEW_HANDLE, source_block_name="FJL-25-2A_Mirror"),
    ])

    assert resolution.winner is None
    assert resolution.reason == "handle_not_comparable"


def test_texts_from_different_files_are_not_comparable() -> None:
    resolution = resolve_overlapping_texts([
        _text("A", "8nB01", OLD_HANDLE, file_id="F1"),
        _text("B", "8n401", NEW_HANDLE, file_id="F2"),
    ])

    assert resolution.winner is None
    assert resolution.reason == "different_files"


def test_overlap_message_names_the_values() -> None:
    assert overlap_detected_text(["8n401", "8nB01"]) == "检测到文字重叠：8n401 / 8nB01"


# --- strip-port integration -----------------------------------------------------------------------

def test_readable_order_uses_latest_batch_and_drops_earlier_text_silently() -> None:
    texts = _strip_texts(
        _text("OLD", "8nB01", OLD_HANDLE),
        _text("NEW", "8n401", NEW_HANDLE, x=205.82),
    )

    pairs, bottom, group = _extract(texts)

    assert bottom.right_value == "8n401"
    assert bottom.right_text_id == "NEW"
    assert bottom.status == "pass"
    assert bottom.evidence["unresolved_component_port"] is False
    assert bottom.evidence["overlap_resolution"] == "latest_handle"
    assert bottom.evidence["overlap_winner_text_id"] == "NEW"
    assert bottom.evidence["overlapping_text_superseded"] == [
        {"text_id": "OLD", "value": "8nB01", "handle": OLD_HANDLE},
    ]
    assert _missing_side_issue(pairs, group, bottom.pair_id) is None


def test_readable_order_does_not_depend_on_text_id_order() -> None:
    texts = _strip_texts(
        _text("A-NEW", "8n401", NEW_HANDLE),
        _text("Z-OLD", "8nB01", OLD_HANDLE, x=205.82),
    )

    _, bottom, _ = _extract(texts)

    assert bottom.right_value == "8n401"
    assert bottom.right_text_id == "A-NEW"


def test_three_stacked_labels_resolve_to_the_largest_handle() -> None:
    texts = _strip_texts(
        _text("T1", "8nB01", "12870"),
        _text("T2", "8n401", OLD_HANDLE, x=205.81),
        _text("T3", "8n402", NEW_HANDLE, x=205.82),
    )

    pairs, bottom, group = _extract(texts)

    assert bottom.right_value == "8n402"
    assert bottom.status == "pass"
    assert sorted(item["text_id"] for item in bottom.evidence["overlapping_text_superseded"]) == ["T1", "T2"]
    assert _missing_side_issue(pairs, group, bottom.pair_id) is None


def test_equal_handles_keep_the_port_unresolved_and_name_the_overlap() -> None:
    texts = _strip_texts(
        _text("OLD", "8nB01", NEW_HANDLE),
        _text("NEW", "8n401", NEW_HANDLE, x=205.82),
    )

    pairs, bottom, group = _extract(texts)

    assert bottom.right_value is None
    assert bottom.status == "review"
    assert bottom.evidence["unresolved_reason"] == "coincident_conflicting_labels"
    assert bottom.evidence["overlap_resolution"] == "unresolved"
    assert bottom.evidence["overlap_unresolved_reason"] == "duplicate_handle"
    assert bottom.evidence["overlapping_text_values"] == ["8n401", "8nB01"]
    assert "overlapping_text_superseded" not in bottom.evidence

    issue = _missing_side_issue(pairs, group, bottom.pair_id)
    assert issue is not None
    assert "检测到文字重叠：8n401 / 8nB01" in issue.message
    assert "检测到文字重叠：8n401 / 8nB01" in issue.explanation
    assert issue.evidence["overlapping_text_values"] == ["8n401", "8nB01"]


def test_non_comparable_handles_keep_the_port_unresolved_and_name_the_overlap() -> None:
    texts = _strip_texts(
        _text("OLD", "8nB01", "HOLD"),
        _text("NEW", "8n401", NEW_HANDLE, x=205.82),
    )

    pairs, bottom, group = _extract(texts)

    assert bottom.right_value is None
    assert bottom.evidence["overlap_unresolved_reason"] == "handle_not_comparable"
    issue = _missing_side_issue(pairs, group, bottom.pair_id)
    assert "检测到文字重叠：8n401 / 8nB01" in issue.explanation


def test_non_overlapping_endpoint_is_unchanged() -> None:
    texts = _strip_texts(_text("ONLY", "8n401", NEW_HANDLE))

    pairs, bottom, group = _extract(texts)

    assert bottom.right_value == "8n401"
    assert bottom.status == "pass"
    for key in ("overlap_resolution", "overlap_winner_text_id", "overlapping_text_superseded",
                "overlapping_text_values", "overlap_unresolved_reason"):
        assert key not in bottom.evidence
    assert _missing_side_issue(pairs, group, bottom.pair_id) is None


def test_same_value_duplicate_is_not_a_conflict() -> None:
    texts = _strip_texts(
        _text("OLD", "8n401", OLD_HANDLE),
        _text("NEW", "8n401", NEW_HANDLE, x=205.82),
    )

    _, bottom, _ = _extract(texts)

    assert bottom.right_value == "8n401"
    assert bottom.status == "pass"
    assert "overlap_resolution" not in bottom.evidence


def test_stacked_bottom_label_does_not_change_the_top_side() -> None:
    def top_pair(texts):
        pairs, _, _ = _extract(texts)
        return next(pair for pair in pairs if pair.evidence.get("endpoint_side") == "top")

    stacked = top_pair(_strip_texts(
        _text("OLD", "8nB01", OLD_HANDLE),
        _text("NEW", "8n401", NEW_HANDLE, x=205.82),
    ))
    single = top_pair(_strip_texts(_text("ONLY", "8n401", NEW_HANDLE)))

    assert stacked.right_value == single.right_value
    assert stacked.status == single.status
    assert "overlap_resolution" not in stacked.evidence


# --- endpoint-bridge integration -------------------------------------------------------------------

def _bridge_texts(*bottom_stack: TextItem) -> list[TextItem]:
    return [
        _text("P1", "1", "INS1:VIRTUAL:0", 208.9, 190.0, source_block_name="FJL-25-2A_Mirror"),
        _text("P2", "2", "INS1:VIRTUAL:1", 208.9, 175.0, source_block_name="FJL-25-2A_Mirror"),
        _text("TOPB", "1-2ZK-1", "TOPH", 204.3, 195.4),
        *bottom_stack,
    ]


def _bridge_pairs(texts: list[TextItem]):
    from dwg_audit.audit.component_diagrams import extract_strip_two_port_endpoint_bridge_pairs

    pairs, _ = extract_strip_two_port_endpoint_bridge_pairs([_sheet()], texts, [_support_group()])
    return [pair for pair in pairs if pair.pair_kind == "semantic_mapping"]


def test_bridge_readable_order_uses_latest_endpoint() -> None:
    pairs = _bridge_pairs(_bridge_texts(
        _text("OLD", "1-2n401", OLD_HANDLE),
        _text("NEW", "1-2n402", NEW_HANDLE, x=205.82),
    ))

    assert len(pairs) == 1
    assert pairs[0].right_value == "1-2n402"
    assert pairs[0].evidence["overlap_resolution"] == "latest_handle"
    assert pairs[0].evidence["overlapping_text_superseded"] == [
        {"text_id": "OLD", "value": "1-2n401", "handle": OLD_HANDLE},
    ]


def test_bridge_unreadable_order_builds_no_pair_and_never_picks_by_text_id() -> None:
    pairs = _bridge_pairs(_bridge_texts(
        _text("A", "1-2n401", NEW_HANDLE),
        _text("B", "1-2n402", NEW_HANDLE, x=205.82),
    ))

    assert pairs == []


def test_bridge_latest_text_that_is_not_a_bridge_endpoint_builds_no_pair() -> None:
    pairs = _bridge_pairs(_bridge_texts(
        _text("OLD", "1-2n401", OLD_HANDLE),
        _text("NEW", "8n402", NEW_HANDLE, x=205.82),
    ))

    assert pairs == []


def test_bridge_same_value_stack_is_unchanged() -> None:
    pairs = _bridge_pairs(_bridge_texts(
        _text("OLD", "1-2n401", OLD_HANDLE),
        _text("NEW", "1-2n401", NEW_HANDLE, x=205.82),
    ))

    assert len(pairs) == 1
    assert pairs[0].right_value == "1-2n401"
    assert "overlap_resolution" not in pairs[0].evidence
