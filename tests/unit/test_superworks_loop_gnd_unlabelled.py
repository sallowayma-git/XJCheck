"""G-1: public-ground shared endpoints and unlabelled component ports.

GND (public ground, 公共地): a GND endpoint shared by several left ends is one common-ground
net across terminal strips and devices, so it is not a many-to-one conflict. The exemption is
keyed on the shared right endpoint only; the same shape on an ordinary endpoint still reports,
and a GND left end on a non-ground right endpoint still reports.

Unlabelled port: a component port whose endpoint search window holds no external text at all is
flagged with missing_side_reason="unlabelled_port" and says so in the R-PAIR-MISSING-SIDE message.
A port with coincident conflicting labels, or with a non-endpoint external text in its window, is
not called unlabelled.
"""

from __future__ import annotations

from dataclasses import replace

from dwg_audit.audit import rules as R
from dwg_audit.audit.component_diagrams import extract_strip_two_port_component_pairs
from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.audit.rule_base import RuleContext
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG
from dwg_audit.utils.ids import IdFactory


# --- many-to-one fixtures -------------------------------------------------------------------

def _sheet(sheet_id: str) -> SheetRecord:
    return SheetRecord(
        sheet_id,
        sheet_id,
        f"{sheet_id}.dwg",
        1,
        "1",
        "WIRING",
        "wiring",
        "supplemental",
        "filename",
        True,
    )


def _ordinary(pair_id: str, sheet: str, left: str, right: str) -> Pair:
    evidence = {"source": "ordinary", "pair_kind": "ordinary_pair", "ordinary_pair_eligible": True}
    return Pair(
        pair_id, None, sheet, sheet, None, left, right, 0.99, "pass",
        "g1 fixture", [], "high", evidence, pair_kind="ordinary_pair",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-R",
    )


def _many_to_one_rule_messages(pairs: list[Pair]) -> list[str]:
    sheets = {pair.sheet_id: _sheet(pair.sheet_id) for pair in pairs}
    context = RuleContext(
        pairs=pairs,
        line_groups=[],
        sheets=list(sheets.values()),
        config=DEFAULT_CONFIG,
        terminal_candidates=[],
        high_threshold=0.92,
        duplicate_delta=0.08,
        reciprocal_required=False,
        group_map={},
        sheet_map=sheets,
        issue_factory=IssueFactory(issue_ids=IdFactory("I"), group_map={}, sheet_map=sheets),
    )
    return [issue.message for issue in R._run_many_to_one(context)]


def test_shared_gnd_endpoint_across_strips_is_not_many_to_one() -> None:
    pairs = [_ordinary("P1", "S1", "1C9D11", "GND"), _ordinary("P2", "S2", "JD11", "GND")]

    assert _many_to_one_rule_messages(pairs) == []


def test_same_shape_on_ordinary_endpoint_still_reports_many_to_one() -> None:
    pairs = [_ordinary("P1", "S1", "1C9D11", "X1"), _ordinary("P2", "S2", "JD11", "X1")]

    assert _many_to_one_rule_messages(pairs) == ["Right value X1 maps back to multiple left values."]


def test_gnd_left_end_on_ordinary_right_endpoint_still_reports() -> None:
    pairs = [_ordinary("P1", "S1", "GND", "X1"), _ordinary("P2", "S2", "JD11", "X1")]

    assert _many_to_one_rule_messages(pairs) == ["Right value X1 maps back to multiple left values."]


def test_ground_network_endpoint_predicate_uses_shared_name_identity() -> None:
    assert R._is_ground_network_endpoint("GND")
    assert R._is_ground_network_endpoint(" gnd ")
    assert not R._is_ground_network_endpoint("GND1")
    assert not R._is_ground_network_endpoint("JD11")
    assert not R._is_ground_network_endpoint(None)


# --- unlabelled component port fixtures -----------------------------------------------------

def _component_sheet() -> SheetRecord:
    return SheetRecord(
        sheet_id="S1",
        file_id="F1",
        filename="16 元件接线图2.dwg",
        sheet_order=16,
        sheet_no="16",
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
    x: float,
    y: float,
    *,
    layer: str = "0",
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


def _port_texts(*external: TextItem) -> list[TextItem]:
    return [
        _text("BODY", "8KLP3", 205.0, 205.3, layer="MARK"),
        _text("P1", "1", 208.9, 190.0, source_block_name="FJL-25-2A_Mirror"),
        _text("P2", "2", 208.9, 175.0, source_block_name="FJL-25-2A_Mirror"),
        _text("TOP", "8KLP2-1", 204.3, 195.4),
        *external,
    ]


def _unresolved_port_issue(texts: list[TextItem]):
    group = _support_group()
    pairs, consumed = extract_strip_two_port_component_pairs([_component_sheet()], texts, [group])
    assert consumed == {"GC0132"}
    unresolved = next(pair for pair in pairs if pair.right_value is None)
    issues = R.build_issues(pairs, [group], [_component_sheet()], DEFAULT_CONFIG)
    issue = next(
        item for item in issues
        if item.rule_id == "R-PAIR-MISSING-SIDE" and item.pair_id == unresolved.pair_id
    )
    return unresolved, issue


def test_port_with_empty_search_window_is_marked_unlabelled_in_message_and_evidence() -> None:
    unresolved, issue = _unresolved_port_issue(_port_texts())

    assert unresolved.evidence["unresolved_reason"] == "external_endpoint_missing"
    assert unresolved.evidence["missing_side_reason"] == "unlabelled_port"
    assert "端口 2 无任何外部标注" in issue.message
    assert "该元件端口（端口 2）无标注" in issue.explanation
    assert issue.evidence["missing_side_reason"] == "unlabelled_port"
    assert issue.evidence["missing_side_classification"] == "external_endpoint_missing"


def test_port_whose_window_holds_a_non_endpoint_text_is_not_called_unlabelled() -> None:
    # "112" is external text in the window but not a valid external endpoint value:
    # the port is labelled by something, so it keeps the generic message.
    unresolved, issue = _unresolved_port_issue(_port_texts(_text("NOTE", "112", 205.8, 169.8)))

    assert unresolved.evidence["unresolved_reason"] == "external_endpoint_missing"
    assert unresolved.evidence["missing_side_reason"] is None
    assert "无任何外部标注" not in issue.message
    assert "无标注" not in issue.explanation
    assert "missing_side_reason" not in issue.evidence


def test_coincident_conflicting_labels_are_not_called_unlabelled() -> None:
    texts = [
        _text("BODY", "8KLP3", 205, 205.3, layer="MARK"),
        replace(_text("P1", "1", 208.9, 190, source_block_name="FJL-25-2A Y4_Mirror"), handle="INSERT1:VIRTUAL:0"),
        replace(_text("P2", "2", 208.9, 175, source_block_name="FJL-25-2A Y4_Mirror"), handle="INSERT1:VIRTUAL:1"),
        _text("TOP", "8KLP2-1", 204.3, 195.4),
        _text("BOTTOM", "8n401", 205.8, 169.8),
        _text("CONFLICT", "8nB01", 205.82, 169.8),
    ]
    group = _support_group()
    pairs, _ = extract_strip_two_port_component_pairs([_component_sheet()], texts, [group])
    unresolved = next(pair for pair in pairs if pair.right_value is None)
    assert unresolved.evidence["unresolved_reason"] == "coincident_conflicting_labels"
    assert unresolved.evidence["missing_side_reason"] is None

    issues = R.build_issues(pairs, [group], [_component_sheet()], DEFAULT_CONFIG)
    issue = next(
        item for item in issues
        if item.rule_id == "R-PAIR-MISSING-SIDE" and item.pair_id == unresolved.pair_id
    )
    assert "无任何外部标注" not in issue.message
    assert "无标注" not in issue.explanation
    assert "missing_side_reason" not in issue.evidence
