import pytest

from dwg_audit.audit.page_extractors import _mark_input_matrix_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_inline_wire_split_continuation_pairs
from dwg_audit.audit.page_extractors import _mark_schematic_ac_phase_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_schematic_ground_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _shadow_grid_wire_ordinary_pairs
from dwg_audit.audit.page_extractors import _shadow_ct_polarity_reference_ordinary_pairs
from dwg_audit.audit.page_extractors import _shadow_parallel_grid_separator_ordinary_pairs
from dwg_audit.audit.page_extractors import _shadow_connect_multidrop_rail_ordinary_pairs
from dwg_audit.audit.page_extractors import _shadow_closed_tall_polyline_enclosure_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_terminal_prefixed_endpoint_ordinary_pairs
from dwg_audit.audit.page_extractors import _promote_regular_terminal_row_array_pairs
from dwg_audit.audit.page_extractors import _promote_xjdz_structural_component_pairs
from dwg_audit.audit.page_extractors import _panel_model_label_matches
from dwg_audit.audit.page_extractors import mark_ignored_equipment_panel_ordinary_pairs
from dwg_audit.audit.rules import build_issues
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG


def _pair(
    evidence: dict[str, object],
    *,
    pair_id: str = "P1",
    line_group_id: str = "G1",
    pair_kind: str = "ordinary_pair",
    left_text_id: str | None = None,
    right_text_id: str | None = None,
    left_value: str = "21",
    right_value: str = "211",
) -> Pair:
    return Pair(
        pair_id=pair_id,
        line_group_id=line_group_id,
        sheet_id="S1",
        file_id="F1",
        selected_pair_candidate_id="PC1",
        left_value=left_value,
        right_value=right_value,
        confidence=0.81,
        status="review",
        rationale=f"left={left_value} right={right_value} score=0.81",
        alternative_pair_candidate_ids=[],
        confidence_bucket="review",
        evidence=evidence,
        left_text_id=left_text_id,
        right_text_id=right_text_id,
        pair_kind=pair_kind,
    )


def _sheet(
    category: str = "二次原理图",
    *,
    route_target: str | None = None,
    page_subtype: str | None = None,
    grid_heavy: bool | None = None,
) -> SheetRecord:
    return SheetRecord(
        "S1",
        "F1",
        "04 交流回路图1.dwg",
        4,
        "04",
        "CT AND VT INPUT",
        category,
        "primary",
        "filename",
        True,
        route_target=route_target,
        page_subtype=page_subtype,
        grid_heavy=grid_heavy,
    )


def _line_group(
    line_group_id: str,
    *,
    start_x: float,
    end_x: float,
    start_y: float = 135.0,
    end_y: float = 135.0,
    row_band_id: str = "RB1",
    orientation: str = "grid",
    wire_score: float = 0.85,
) -> LineGroup:
    return LineGroup(
        line_group_id=line_group_id,
        sheet_id="S1",
        file_id="F1",
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        length=abs(end_x - start_x),
        wire_candidate_score=wire_score,
        member_line_ids=[],
        layer_hints=[],
        orientation=orientation,
        row_band_id=row_band_id,
    )


def _parallel_separator_pair(
    *,
    pair_id: str,
    line_group_id: str,
    value: str | None = "211",
    text_id: str | None = "T211",
) -> Pair:
    evidence = {
        "line_orientation": "horizontal",
        "selected_left_candidate_id": "C211" if value is not None else None,
        "selected_left_text_id": text_id if value is not None else None,
        "selected_left_raw_text": value,
        "selected_right_candidate_id": None,
        "selected_right_text_id": None,
        "selected_right_raw_text": None,
    }
    pair = _pair(
        evidence,
        pair_id=pair_id,
        line_group_id=line_group_id,
        left_text_id=text_id if value is not None else None,
        left_value=value,
        right_value=None,
    )
    if value is None:
        pair.status = "discard"
        pair.confidence_bucket = "low"
    return pair


def _panel_line(
    line_id: str,
    *,
    handle: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    layer: str = "0",
    source_block_name: str | None = None,
    source_entity_type: str = "LINE",
) -> LineEntity:
    return LineEntity(
        line_id=line_id,
        sheet_id="S1",
        file_id="F1",
        handle=handle,
        source_entity_type=source_entity_type,
        layer=layer,
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        length=((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5,
        angle_deg=0.0,
        bbox_min_x=min(start_x, end_x),
        bbox_min_y=min(start_y, end_y),
        bbox_max_x=max(start_x, end_x),
        bbox_max_y=max(start_y, end_y),
        source_block_name=source_block_name,
    )


def _panel_text(
    text_id: str,
    value: str,
    *,
    x: float,
    y: float,
    layer: str = "0",
    source_block_name: str | None = None,
    handle: str | None = None,
) -> TextItem:
    return TextItem(
        text_id=text_id,
        sheet_id="S1",
        file_id="F1",
        handle=handle or f"H-{text_id}",
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
        bbox_max_x=x + max(1.0, len(value) * 1.5),
        bbox_max_y=y + 1.0,
        source_block_name=source_block_name,
    )


def _ct_polarity_reference_fixture(
    *,
    present_side: str = "right",
    reverse_line: bool = False,
    value: str = "3",
) -> tuple[
    Pair,
    list[SheetRecord],
    list[TextItem],
    list[LineGroup],
    list[LineEntity],
    list[TerminalCandidate],
]:
    missing_side = "left" if present_side == "right" else "right"
    evidence = {
        "line_group_id": "G_CT",
        "line_orientation": "horizontal",
        "line_start": [10.0, 50.0],
        "line_end": [110.0, 50.0],
        "pair_key": f"{value}->?" if present_side == "left" else f"?->{value}",
        "selected_pair_candidate_id": "PC1",
        "selected_left_candidate_id": "C_VALUE" if present_side == "left" else None,
        "selected_right_candidate_id": "C_VALUE" if present_side == "right" else None,
        "selected_left_text_id": "T_VALUE" if present_side == "left" else None,
        "selected_right_text_id": "T_VALUE" if present_side == "right" else None,
        "selected_left_raw_text": value if present_side == "left" else None,
        "selected_right_raw_text": value if present_side == "right" else None,
        "selected_left_channel": "terminal_numeric_channel" if present_side == "left" else None,
        "selected_right_channel": "terminal_numeric_channel" if present_side == "right" else None,
        "selected_left_channel_detail": None,
        "selected_right_channel_detail": None,
        "selected_left_is_derived_numeric": False,
        "selected_right_is_derived_numeric": False,
        "selected_left_source_block_name": None,
        "selected_right_source_block_name": None,
        "alternative_pair_candidate_ids": [],
        "score_breakdown": {"ambiguity_gap": None},
    }
    pair = _pair(
        evidence,
        pair_id="P_CT",
        line_group_id="G_CT",
        left_text_id="T_VALUE" if present_side == "left" else None,
        right_text_id="T_VALUE" if present_side == "right" else None,
        left_value=value if present_side == "left" else None,
        right_value=value if present_side == "right" else None,
    )
    setattr(pair, f"{present_side}_candidate_id", "C_VALUE")
    setattr(pair, f"{missing_side}_candidate_id", None)
    pair.pair_key = f"{value}->?" if present_side == "left" else f"?->{value}"
    setattr(pair, f"{present_side}_coord_x", 8.0 if present_side == "left" else 112.0)
    setattr(pair, f"{present_side}_coord_y", 50.0)
    group = LineGroup(
        "G_CT",
        "S1",
        "F1",
        10.0,
        50.0,
        110.0,
        50.0,
        100.0,
        0.55,
        ["L_CT"],
        ["0"],
        "horizontal",
    )
    line_start_x, line_end_x = (110.0, 10.0) if reverse_line else (10.0, 110.0)
    lines = [
        _panel_line(
            "L_CT",
            handle="H_CT",
            start_x=line_start_x,
            start_y=50.0,
            end_x=line_end_x,
            end_y=50.0,
        )
    ]
    value_x = 8.0 if present_side == "left" else 112.0
    texts = [
        _panel_text("T_VALUE", value, x=value_x, y=50.0),
        _panel_text("TL_P1", "P1", x=6.0, y=44.0),
        _panel_text("TL_P2", "P2", x=6.0, y=56.0),
        _panel_text("TL_S1", "S1", x=15.0, y=44.0),
        _panel_text("TL_S2", "S2", x=15.0, y=56.0),
        _panel_text("TL_STAR1", "*", x=9.0, y=48.0),
        _panel_text("TL_STAR2", "*", x=13.0, y=48.0),
        _panel_text("TR_P1", "P1", x=106.0, y=44.0),
        _panel_text("TR_P2", "P2", x=106.0, y=56.0),
        _panel_text("TR_S1", "S1", x=115.0, y=44.0),
        _panel_text("TR_S2", "S2", x=115.0, y=56.0),
        _panel_text("TR_STAR1", "*", x=109.0, y=48.0),
        _panel_text("TR_STAR2", "*", x=113.0, y=48.0),
        _panel_text("T_POLARITY", "CT subtractive polarity reference", x=50.0, y=90.0),
        _panel_text("T_POWER", "Power flow direction during normal operation", x=50.0, y=95.0),
        _panel_text("T_POWER_2", "功率流向", x=50.0, y=100.0),
    ]
    candidate = TerminalCandidate(
        candidate_id="C_VALUE",
        line_group_id="G_CT",
        sheet_id="S1",
        file_id="F1",
        side=present_side,
        text_id="T_VALUE",
        text=value,
        value=value,
        score=0.64,
        status="accepted",
        rejection_reason=None,
        endpoint_x=10.0 if present_side == "left" else 110.0,
        endpoint_y=50.0,
        distance_x=2.0,
        distance_y=0.0,
        text_insert_x=value_x,
        text_insert_y=50.0,
        vertical_alignment_score=1.0,
        horizontal_side_score=1.0,
        text_type_score=1.0,
        height_score=1.0,
        rank=1,
        source_block_name=None,
        channel="terminal_numeric_channel",
        channel_detail=None,
    )
    page = _sheet(route_target="WireDiagramExtractor")
    page.sheet_title = "Reference diagram"
    page.filename = "reference.dwg"
    return (
        pair,
        [page],
        texts,
        [group],
        lines,
        [candidate],
    )


def _ignored_panel_proposal(*, family_id: str = "communication.equipment_panel_ignored.v1") -> dict[str, object]:
    return {
        "sheet_id": "S1",
        "definition_name": "RENAMED-EQUIPMENT-PANEL",
        "definition_fingerprint": "geometry-proven-panel",
        "instance_handles": ["HPANEL"],
        "family_id": family_id,
        "matched_family_rule_id": "complete-equipment-panel-v1",
        "behavior_mode": "IGNORE",
        "allow_port_emission": False,
        "allow_external_attachment": False,
    }


def test_geometry_proven_equipment_panel_shadows_internal_ordinary_pairs() -> None:
    text_owned = _pair(
        {"selected_left_text_id": "TPIN"},
        pair_id="P-TEXT",
        line_group_id="G-TEXT",
        left_text_id="TPIN",
        left_value="4",
        right_value=None,
    )
    line_owned = _pair(
        {"selected_left_text_id": "TFREE"},
        pair_id="P-LINE",
        line_group_id="G-LINE",
        left_text_id="TFREE",
        left_value="5",
        right_value=None,
    )
    unrelated = _pair(
        {"selected_left_text_id": "TFREE"},
        pair_id="P-OTHER",
        line_group_id="G-OTHER",
        left_text_id="TFREE",
        left_value="6",
        right_value=None,
    )
    groups = [
        _line_group("G-TEXT", start_x=100.0, end_x=140.0, orientation="horizontal"),
        _line_group("G-LINE", start_x=100.0, end_x=140.0, orientation="horizontal"),
        _line_group("G-OTHER", start_x=220.0, end_x=260.0, orientation="horizontal"),
    ]
    groups[0].member_line_ids = ["L-TEXT"]
    groups[1].member_line_ids = ["L-LINE"]
    groups[2].member_line_ids = ["L-OTHER"]
    lines = [
        _panel_line(
            "L-TEXT", handle="HPANEL:VIRTUAL:1", start_x=100.0, start_y=135.0,
            end_x=140.0, end_y=135.0, source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
        _panel_line(
            "L-LINE", handle="HPANEL:VIRTUAL:2", start_x=100.0, start_y=130.0,
            end_x=140.0, end_y=130.0, source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
        _panel_line(
            "L-OTHER", handle="FREE-LINE", start_x=220.0, start_y=135.0,
            end_x=260.0, end_y=135.0,
        ),
    ]
    texts = [
        _panel_text(
            "TPIN",
            "4",
            x=100.0,
            y=135.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
            handle="HPANEL:TEXT:1",
        ),
        _panel_text("TFREE", "5", x=100.0, y=130.0),
    ]

    mark_ignored_equipment_panel_ordinary_pairs(
        [text_owned, line_owned, unrelated],
        groups,
        texts,
        lines,
        [_ignored_panel_proposal()],
    )

    for pair in (text_owned, line_owned):
        assert pair.evidence["ordinary_pair_eligible"] is False
        assert pair.evidence["ordinary_pair_shadow_reason"] == "ignored_equipment_panel_geometry"
        assert pair.evidence["ignored_panel_definition_fingerprint"] == "geometry-proven-panel"
    assert unrelated.evidence.get("ordinary_pair_eligible") is not False


def test_geometry_proven_equipment_panel_shadows_strict_mark_callout() -> None:
    callout = _pair(
        {
            "selected_left_text_id": "T5",
            "selected_left_raw_text": "5",
            "line_orientation": "horizontal",
        },
        pair_id="P-CALLOUT",
        line_group_id="G-CALLOUT",
        left_text_id="T5",
        left_value="5",
        right_value=None,
    )
    group = _line_group(
        "G-CALLOUT",
        start_x=120.0,
        end_x=170.0,
        start_y=160.0,
        end_y=160.0,
        orientation="horizontal",
    )
    group.member_line_ids = ["L-CALLOUT"]
    group.layer_hints = ["MARK"]
    lines = [
        _panel_line(
            "L-PANEL-BOTTOM", handle="HPANEL:VIRTUAL:1", start_x=100.0, start_y=50.0,
            end_x=200.0, end_y=50.0, source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
        _panel_line(
            "L-PANEL-TOP", handle="HPANEL:VIRTUAL:2", start_x=100.0, start_y=150.0,
            end_x=200.0, end_y=150.0, source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
        _panel_line(
            "L-CALLOUT", handle="FREE-MARK", start_x=120.0, start_y=160.0,
            end_x=170.0, end_y=160.0, layer="MARK",
        ),
    ]
    texts = [
        _panel_text("T5", "5", x=120.0, y=160.0, layer="MARK"),
        _panel_text("TSCOPE", "1-40n", x=132.0, y=160.4, layer="MARK"),
        _panel_text(
            "TMODEL",
            "RENAMED-EQUIPMENT-PANEL",
            x=120.0,
            y=156.7,
            layer="MARK",
        ),
    ]

    mark_ignored_equipment_panel_ordinary_pairs(
        [callout], [group], texts, lines, [_ignored_panel_proposal()]
    )

    assert callout.evidence["ordinary_pair_eligible"] is False
    assert callout.evidence["ordinary_pair_shadow_reason"] == "ignored_equipment_panel_mark_callout"


def test_equipment_panel_shadow_requires_authority_and_complete_mark_evidence() -> None:
    no_scope = _pair(
        {"selected_left_text_id": "T5", "selected_left_raw_text": "5"},
        pair_id="P-NO-SCOPE",
        line_group_id="G-CALLOUT",
        left_text_id="T5",
        left_value="5",
        right_value=None,
    )
    metadata_owned = _pair(
        {"selected_left_text_id": "TPIN"},
        pair_id="P-METADATA",
        line_group_id="G-PANEL",
        left_text_id="TPIN",
        left_value="32",
        right_value=None,
    )
    callout_group = _line_group(
        "G-CALLOUT", start_x=120.0, end_x=170.0, start_y=160.0, end_y=160.0,
        orientation="horizontal",
    )
    callout_group.member_line_ids = ["L-CALLOUT"]
    callout_group.layer_hints = ["MARK"]
    panel_group = _line_group("G-PANEL", start_x=100.0, end_x=140.0, orientation="horizontal")
    panel_group.member_line_ids = ["L-PANEL-TOP"]
    lines = [
        _panel_line(
            "L-PANEL-TOP", handle="HPANEL:VIRTUAL:2", start_x=100.0, start_y=150.0,
            end_x=200.0, end_y=150.0, source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
        _panel_line(
            "L-CALLOUT", handle="FREE-MARK", start_x=120.0, start_y=160.0,
            end_x=170.0, end_y=160.0, layer="MARK",
        ),
    ]
    texts = [
        _panel_text("T5", "5", x=120.0, y=160.0, layer="MARK"),
        _panel_text(
            "TMODEL",
            "RENAMED-EQUIPMENT-PANEL",
            x=120.0,
            y=156.7,
            layer="MARK",
        ),
        _panel_text(
            "TPIN",
            "32",
            x=100.0,
            y=135.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
            handle="HPANEL:TEXT:2",
        ),
    ]

    mark_ignored_equipment_panel_ordinary_pairs(
        [no_scope], [callout_group], texts, lines, [_ignored_panel_proposal()]
    )
    mark_ignored_equipment_panel_ordinary_pairs(
        [metadata_owned],
        [panel_group],
        texts,
        lines,
        [_ignored_panel_proposal(family_id="non_electrical.drawing_metadata.v1")],
    )

    assert no_scope.evidence.get("ordinary_pair_eligible") is not False
    assert metadata_owned.evidence.get("ordinary_pair_eligible") is not False


def test_equipment_panel_shadow_requires_an_approved_instance_handle() -> None:
    unapproved = _pair(
        {"selected_left_text_id": "TPIN"},
        pair_id="P-UNAPPROVED",
        line_group_id="G-UNAPPROVED",
        left_text_id="TPIN",
        left_value="8",
        right_value=None,
    )
    group = _line_group(
        "G-UNAPPROVED", start_x=220.0, end_x=260.0, orientation="horizontal"
    )
    group.member_line_ids = ["L-UNAPPROVED"]
    lines = [
        _panel_line(
            "L-APPROVED",
            handle="HPANEL:VIRTUAL:1",
            start_x=100.0,
            start_y=150.0,
            end_x=200.0,
            end_y=150.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
        _panel_line(
            "L-UNAPPROVED",
            handle="HOTHER:VIRTUAL:1",
            start_x=220.0,
            start_y=130.0,
            end_x=260.0,
            end_y=130.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
    ]
    texts = [
        _panel_text(
            "TPIN",
            "8",
            x=220.0,
            y=130.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
            handle="HOTHER:TEXT:1",
        )
    ]

    mark_ignored_equipment_panel_ordinary_pairs(
        [unapproved], [group], texts, lines, [_ignored_panel_proposal()]
    )

    assert unapproved.evidence.get("ordinary_pair_eligible") is not False


def test_equipment_panel_mark_callout_requires_the_actual_model_label() -> None:
    callout = _pair(
        {"selected_left_text_id": "T5", "selected_left_raw_text": "5"},
        pair_id="P-NOTE",
        line_group_id="G-CALLOUT",
        left_text_id="T5",
        left_value="5",
        right_value=None,
    )
    group = _line_group(
        "G-CALLOUT",
        start_x=120.0,
        end_x=170.0,
        start_y=160.0,
        end_y=160.0,
        orientation="horizontal",
    )
    group.member_line_ids = ["L-CALLOUT"]
    group.layer_hints = ["MARK"]
    lines = [
        _panel_line(
            "L-PANEL-TOP",
            handle="HPANEL:VIRTUAL:2",
            start_x=100.0,
            start_y=150.0,
            end_x=200.0,
            end_y=150.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
        ),
        _panel_line(
            "L-CALLOUT",
            handle="FREE-MARK",
            start_x=120.0,
            start_y=160.0,
            end_x=170.0,
            end_y=160.0,
            layer="MARK",
        ),
    ]
    texts = [
        _panel_text("T5", "5", x=120.0, y=160.0, layer="MARK"),
        _panel_text("TSCOPE", "1-40n", x=132.0, y=160.4, layer="MARK"),
        _panel_text("TNOTE", "NOTE", x=120.0, y=156.7, layer="MARK"),
    ]

    mark_ignored_equipment_panel_ordinary_pairs(
        [callout], [group], texts, lines, [_ignored_panel_proposal()]
    )

    assert callout.evidence.get("ordinary_pair_eligible") is not False


def test_firewall_panel_accepts_only_a_scoped_product_model_alias() -> None:
    row = {
        "definition_name": "NGFW4000-UFTG-3100-GW",
        "matched_family_rule_id": "firewall-eth-usb-optical-power-panel-v1",
    }

    assert _panel_model_label_matches(row, "HX-SFW-NF4203-E")
    assert _panel_model_label_matches(row, "NGFW4000-UFTG-3100-GW")
    assert not _panel_model_label_matches(row, "NOTE")
    assert not _panel_model_label_matches(row, "1-40n")
    assert not _panel_model_label_matches(
        {**row, "matched_family_rule_id": "compact-ge-gx-power-switch-panel-v1"},
        "HX-SFW-NF4203-E",
    )


def test_equipment_panel_shadow_evaluates_a_raw_human_proposal() -> None:
    raw = _ignored_panel_proposal()
    raw["definition_fingerprint"] = (
        "324c61d3d720cd06224bf81112169aa8a8cfdb5197a715181e376ea2cedfb2a5"
    )
    for key in (
        "family_id",
        "matched_family_rule_id",
        "behavior_mode",
        "allow_port_emission",
        "allow_external_attachment",
    ):
        raw.pop(key, None)
    pair = _pair(
        {"selected_left_text_id": "TPIN"},
        pair_id="P-RAW",
        line_group_id="G-RAW",
        left_text_id="TPIN",
        left_value="4",
        right_value=None,
    )
    group = _line_group("G-RAW", start_x=100.0, end_x=140.0, orientation="horizontal")
    group.member_line_ids = ["L-RAW"]
    lines = [
        _panel_line(
            "L-RAW",
            handle="HPANEL:VIRTUAL:1",
            start_x=100.0,
            start_y=135.0,
            end_x=140.0,
            end_y=135.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
        )
    ]
    texts = [
        _panel_text(
            "TPIN",
            "4",
            x=100.0,
            y=135.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
            handle="HPANEL:TEXT:1",
        )
    ]

    mark_ignored_equipment_panel_ordinary_pairs([pair], [group], texts, lines, [raw])

    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["ignored_panel_instance_handle"] == "HPANEL"


def test_equipment_panel_shadow_preserves_legacy_fingerprint_evidence() -> None:
    proposal = _ignored_panel_proposal()
    proposal["fingerprint"] = proposal.pop("definition_fingerprint")
    pair = _pair(
        {"selected_left_text_id": "TPIN"},
        pair_id="P-LEGACY-FINGERPRINT",
        line_group_id="G-LEGACY-FINGERPRINT",
        left_text_id="TPIN",
        left_value="4",
        right_value=None,
    )
    group = _line_group(
        "G-LEGACY-FINGERPRINT",
        start_x=100.0,
        end_x=140.0,
        orientation="horizontal",
    )
    group.member_line_ids = ["L-LEGACY-FINGERPRINT"]
    lines = [
        _panel_line(
            "L-LEGACY-FINGERPRINT",
            handle="HPANEL:VIRTUAL:1",
            start_x=100.0,
            start_y=135.0,
            end_x=140.0,
            end_y=135.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
        )
    ]
    texts = [
        _panel_text(
            "TPIN",
            "4",
            x=100.0,
            y=135.0,
            source_block_name="RENAMED-EQUIPMENT-PANEL",
            handle="HPANEL:TEXT:1",
        )
    ]

    mark_ignored_equipment_panel_ordinary_pairs(
        [pair], [group], texts, lines, [proposal]
    )

    assert pair.evidence["ordinary_pair_eligible"] is False
    assert (
        pair.evidence["ignored_panel_definition_fingerprint"]
        == "geometry-proven-panel"
    )


def test_mark_inline_wire_split_continuation_pairs_tags_shared_text_half_chain() -> None:
    left_half = _pair(
        {"selected_right_text_id": "T505"},
        pair_id="PW0438",
        line_group_id="GW0438",
        right_text_id="T505",
    )
    left_half.left_value = None
    left_half.right_value = "505"
    left_half.right_coord_y = 135.6
    right_half = _pair(
        {"selected_left_text_id": "T505"},
        pair_id="PW0440",
        line_group_id="GW0440",
        left_text_id="T505",
    )
    right_half.left_value = "505"
    right_half.right_value = None
    right_half.left_coord_y = 135.6
    line_groups = [
        _line_group("GW0438", start_x=87.5, end_x=127.5),
        _line_group("GW0440", start_x=146.25, end_x=237.5),
    ]

    _mark_inline_wire_split_continuation_pairs([left_half, right_half], line_groups, [_sheet()], {})

    assert left_half.pair_kind == "continuation"
    assert right_half.pair_kind == "continuation"
    assert left_half.evidence["ordinary_pair_eligible"] is False
    assert right_half.evidence["ordinary_pair_eligible"] is False
    assert left_half.evidence["covered_by_inline_wire_split_half_chain"] is True
    assert right_half.evidence["related_inline_wire_split_pair_id"] == "PW0438"
    assert left_half.evidence["continuation_kind"] == "schematic_inline_wire_split_half_chain"
    assert left_half.evidence["shared_text_id"] == "T505"
    assert left_half.evidence["bridge_gap"] == 18.75
    assert "continuation relation" in left_half.rationale
    assert not any(
        issue.rule_id == "R-PAIR-MISSING-SIDE"
        for issue in build_issues([left_half, right_half], line_groups, [_sheet()], DEFAULT_CONFIG)
    )


def test_mark_inline_wire_split_continuation_pairs_keeps_cross_row_or_non_schematic_pairs() -> None:
    left_half = _pair(
        {"selected_right_text_id": "T505"},
        pair_id="P1",
        line_group_id="G1",
        right_text_id="T505",
    )
    left_half.left_value = None
    left_half.right_value = "505"
    left_half.right_coord_y = 135.0
    right_half = _pair(
        {"selected_left_text_id": "T505"},
        pair_id="P2",
        line_group_id="G2",
        left_text_id="T505",
    )
    right_half.left_value = "505"
    right_half.right_value = None
    right_half.left_coord_y = 145.0
    line_groups = [
        _line_group("G1", start_x=87.5, end_x=127.5, row_band_id="RB1"),
        _line_group("G2", start_x=146.25, end_x=237.5, start_y=145.0, end_y=145.0, row_band_id="RB2"),
    ]

    _mark_inline_wire_split_continuation_pairs([left_half, right_half], line_groups, [_sheet("屏端子图")], {})

    assert left_half.pair_kind == "ordinary_pair"
    assert right_half.pair_kind == "ordinary_pair"
    assert "covered_by_inline_wire_split_half_chain" not in left_half.evidence
    assert "ordinary_pair_eligible" not in right_half.evidence


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


def test_mark_terminal_prefixed_endpoint_ordinary_pairs_shadows_bare_middle_row_restatement() -> None:
    """Ordinary 10→519 restates terminal_header_table middle-row geometry."""
    pair = _pair(
        {
            "selected_left_text_id": "T4000",
            "selected_right_text_id": "T4001",
            "selected_left_raw_text": "10",
            "selected_right_raw_text": "1n519",
            "selected_left_is_derived_numeric": False,
            "selected_right_is_derived_numeric": True,
        },
        left_value="10",
        right_value="519",
    )
    table_mappings = [
        {
            "sheet_id": "S1",
            "mappings": [
                {
                    "mapping_mode": "terminal_header_table",
                    "logical_endpoint": "1C5D-10",
                    "middle_text_id": "T4000",
                    "right_text_id": "T4001",
                    "right_value": "1n519",
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


def test_promote_regular_terminal_row_array_pairs_accepts_unique_stable_rows() -> None:
    pairs = []
    groups = []
    for index in range(6):
        pair = _pair(
            {
                "line_orientation": "horizontal",
                "selected_left_candidate_id": f"CL{index}",
                "selected_right_candidate_id": f"CR{index}",
                "selected_left_channel": "terminal_numeric_channel",
                "selected_right_channel": "terminal_numeric_channel",
                "score_breakdown": {"ambiguity_gap": None},
            },
            pair_id=f"P{index}",
            line_group_id=f"G{index}",
            left_text_id=f"TL{index}",
            right_text_id=f"TR{index}",
        )
        pair.left_value = str(181 - index)
        pair.right_value = str(801 - index)
        pairs.append(pair)
        groups.append(
            _line_group(
                f"G{index}",
                start_x=50.0,
                end_x=125.0,
                start_y=175.0 + index * 5.0,
                end_y=175.0 + index * 5.0,
                orientation="horizontal",
                row_band_id=None,
                wire_score=0.55,
            )
        )
    sheet = _sheet("屏端子图", route_target="TerminalDiagramExtractor")

    _promote_regular_terminal_row_array_pairs(pairs, groups, [sheet], DEFAULT_CONFIG)

    assert {pair.status for pair in pairs} == {"pass"}
    assert {pair.confidence_bucket for pair in pairs} == {"high"}
    assert all(pair.evidence["terminal_row_array_authority"] is True for pair in pairs)
    assert {pair.evidence["terminal_row_array_pitch"] for pair in pairs} == {5.0}


def test_promote_regular_terminal_row_array_pairs_accepts_short_consecutive_sequence() -> None:
    pairs = []
    groups = []
    for index, (left_value, right_value) in enumerate(((214, 824), (213, 823), (212, 822))):
        pair = _pair(
            {
                "line_orientation": "horizontal",
                "selected_left_candidate_id": f"CL{index}",
                "selected_right_candidate_id": f"CR{index}",
                "selected_left_channel": "terminal_numeric_channel",
                "selected_right_channel": "terminal_numeric_channel",
                "score_breakdown": {"ambiguity_gap": None},
            },
            pair_id=f"P{index}",
            line_group_id=f"G{index}",
            left_text_id=f"TL{index}",
            right_text_id=f"TR{index}",
        )
        pair.left_value = str(left_value)
        pair.right_value = str(right_value)
        pairs.append(pair)
        groups.append(
            _line_group(
                f"G{index}",
                start_x=145.0,
                end_x=220.0,
                start_y=255.0 + index * 5.0,
                end_y=255.0 + index * 5.0,
                orientation="horizontal",
                row_band_id=None,
            )
        )

    _promote_regular_terminal_row_array_pairs(
        pairs,
        groups,
        [_sheet("屏端子图", route_target="TerminalDiagramExtractor")],
        DEFAULT_CONFIG,
    )

    assert {pair.status for pair in pairs} == {"pass"}
    assert all(pair.evidence["terminal_row_array_size"] == 3 for pair in pairs)


def test_promote_regular_terminal_row_array_pairs_keeps_ambiguous_or_irregular_rows() -> None:
    pairs = []
    groups = []
    y_values = [100.0, 105.0, 111.3, 120.0, 132.7, 150.0]
    for index, y_value in enumerate(y_values):
        pair = _pair(
            {
                "line_orientation": "horizontal",
                "selected_left_candidate_id": f"CL{index}",
                "selected_right_candidate_id": f"CR{index}",
                "selected_left_channel": "terminal_numeric_channel",
                "selected_right_channel": "terminal_numeric_channel",
                "score_breakdown": {"ambiguity_gap": None},
            },
            pair_id=f"P{index}",
            line_group_id=f"G{index}",
            left_text_id=f"TL{index}",
            right_text_id=f"TR{index}",
        )
        pair.left_value = str(index + 1)
        pair.right_value = str(index + 101)
        if index == 0:
            pair.alternative_pair_candidate_ids = ["ALT"]
        pairs.append(pair)
        groups.append(
            _line_group(
                f"G{index}",
                start_x=50.0,
                end_x=125.0,
                start_y=y_value,
                end_y=y_value,
                orientation="horizontal",
                row_band_id=None,
            )
        )
    sheet = _sheet("屏端子图", route_target="TerminalDiagramExtractor")

    _promote_regular_terminal_row_array_pairs(pairs, groups, [sheet], DEFAULT_CONFIG)

    assert {pair.status for pair in pairs} == {"review"}
    assert not any(pair.evidence.get("terminal_row_array_authority") for pair in pairs)


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


def test_mark_input_matrix_covered_ordinary_pairs_discards_first_prefixed_external_local_number_pair() -> None:
    ordinary = _pair({}, right_text_id="LOCAL105")
    component_pair = _pair(
        {
            "component_submode": "first_prefixed_external_endpoint_mapping",
            "local_number_text_id": "LOCAL105",
            "external_endpoint_text_id": "EXT1",
        },
        pair_kind="wire_component_mapping",
        left_text_id="EXT1",
        right_text_id="LOCAL105",
    )

    _mark_input_matrix_covered_ordinary_pairs([ordinary], [component_pair])

    assert ordinary.status == "discard"
    assert ordinary.confidence_bucket == "low"
    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["covered_by_first_prefixed_external_endpoint_mapping"] is True
    assert "prefixed external local number" in ordinary.rationale


def test_mark_input_matrix_covered_ordinary_pairs_discards_scoped_visible_prefix_local_number_pair() -> None:
    ordinary = _pair({}, right_text_id="LOCAL701")
    component_pair = _pair(
        {
            "component_submode": "scoped_visible_prefix_external_endpoint_mapping",
            "local_number_text_id": "LOCAL701",
            "external_endpoint_text_id": "EXT1",
        },
        pair_kind="wire_component_mapping",
        left_text_id="EXT1",
        right_text_id="LOCAL701",
    )

    _mark_input_matrix_covered_ordinary_pairs([ordinary], [component_pair])

    assert ordinary.status == "discard"
    assert ordinary.confidence_bucket == "low"
    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["covered_by_scoped_visible_prefix_external_endpoint_mapping"] is True
    assert "scoped local number" in ordinary.rationale


def test_mark_input_matrix_covered_ordinary_pairs_discards_inline_body_port_local_number_pair() -> None:
    ordinary = _pair({}, right_text_id="LOCAL207")
    component_pair = _pair(
        {
            "component_submode": "inline_klp_component_port_mapping",
            "local_number_text_id": "LOCAL207",
            "external_endpoint_text_id": "EXT1",
        },
        pair_kind="wire_component_mapping",
        left_text_id="PORT2",
        right_text_id="LOCAL207",
    )

    _mark_input_matrix_covered_ordinary_pairs([ordinary], [component_pair])

    assert ordinary.status == "discard"
    assert ordinary.confidence_bucket == "low"
    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["covered_by_inline_klp_component_port_mapping"] is True
    assert "inline body-port mapping" in ordinary.rationale


def test_mark_input_matrix_covered_ordinary_pairs_keeps_first_prefixed_external_endpoint_pair() -> None:
    ordinary = _pair({}, right_text_id="EXT1")
    component_pair = _pair(
        {
            "component_submode": "first_prefixed_external_endpoint_mapping",
            "local_number_text_id": "LOCAL105",
            "external_endpoint_text_id": "EXT1",
        },
        pair_kind="wire_component_mapping",
        left_text_id="EXT1",
        right_text_id="LOCAL105",
    )

    _mark_input_matrix_covered_ordinary_pairs([ordinary], [component_pair])

    assert ordinary.status == "review"
    assert "covered_by_first_prefixed_external_endpoint_mapping" not in ordinary.evidence


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


def test_mark_schematic_ground_covered_ordinary_pairs_discards_gnd_shared_numeric_half_pair() -> None:
    ordinary = _pair({"selected_left_text_id": "DC101"}, left_text_id="DC101")
    ordinary.left_value = "101"
    ordinary.right_value = None
    semantic = _pair(
        {
            "semantic_kind": "schematic_semantic_endpoint",
            "semantic_mapping_kind": "schematic_dc_function_label",
            "semantic_endpoint": "GND",
            "numeric_endpoint_text_id": "DC101",
        },
        pair_kind="semantic_mapping",
        right_text_id="DC101",
    )

    _mark_schematic_ground_covered_ordinary_pairs([ordinary, semantic], [_sheet()])

    assert ordinary.status == "discard"
    assert ordinary.confidence_bucket == "low"
    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["covered_by_schematic_ground_semantic_mapping"] is True
    assert "GND-covered numeric text" in ordinary.rationale


def test_mark_schematic_ground_covered_ordinary_pairs_keeps_non_gnd_or_complete_pairs() -> None:
    ordinary = _pair({"selected_left_text_id": "DC611"}, left_text_id="DC611")
    ordinary.left_value = "611"
    ordinary.right_value = None
    complete = _pair({"selected_left_text_id": "DC101"}, left_text_id="DC101")
    complete.left_value = "101"
    complete.right_value = "GND"
    non_gnd_semantic = _pair(
        {
            "semantic_kind": "schematic_semantic_endpoint",
            "semantic_mapping_kind": "schematic_dc_function_label",
            "semantic_endpoint": "DC 0-5V/4-20mA +",
            "numeric_endpoint_text_id": "DC611",
        },
        pair_kind="semantic_mapping",
        right_text_id="DC611",
    )

    _mark_schematic_ground_covered_ordinary_pairs(
        [ordinary, complete, non_gnd_semantic],
        [_sheet()],
    )

    assert ordinary.status == "review"
    assert "covered_by_schematic_ground_semantic_mapping" not in ordinary.evidence
    assert complete.status == "review"
    assert "covered_by_schematic_ground_semantic_mapping" not in complete.evidence


def test_shadow_grid_wire_ordinary_pairs_marks_wire_grid_pairs_ineligible() -> None:
    ordinary = _pair({"line_orientation": "grid"})
    ordinary.status = "pass"
    ordinary.confidence_bucket = "high"

    _shadow_grid_wire_ordinary_pairs(
        [ordinary],
        [
            _sheet(
                route_target="WireDiagramExtractor",
                page_subtype="grid_heavy_wire_diagram",
                grid_heavy=True,
            )
        ],
    )

    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["ordinary_pair_shadow_only"] is True
    assert ordinary.evidence["ordinary_pair_shadow_reason"] == "wire_grid_primary"


def test_parallel_grid_separator_shadows_repeated_text_backed_rows() -> None:
    pairs = [
        _parallel_separator_pair(pair_id="P_TOP", line_group_id="G_TOP"),
        _parallel_separator_pair(pair_id="P_MIDDLE", line_group_id="G_MIDDLE"),
        _parallel_separator_pair(pair_id="P_EMPTY", line_group_id="G_EMPTY", value=None, text_id=None),
    ]
    groups = [
        _line_group("G_TOP", start_x=40.0, end_x=70.0, start_y=40.0, end_y=40.0, orientation="horizontal", row_band_id=None, wire_score=0.55),
        _line_group("G_MIDDLE", start_x=40.0, end_x=70.0, start_y=50.0, end_y=50.0, orientation="horizontal", row_band_id=None, wire_score=0.55),
        _line_group("G_EMPTY", start_x=40.0, end_x=70.0, start_y=60.0, end_y=60.0, orientation="horizontal", row_band_id=None, wire_score=0.55),
    ]
    lines = [
        _panel_line(
            "BOUNDARY",
            handle="H-BOUNDARY",
            start_x=70.0,
            start_y=30.0,
            end_x=70.0,
            end_y=40.0,
        )
    ]
    for index, group in enumerate(groups):
        line_id = f"L{index}"
        group.member_line_ids = [line_id]
        lines.append(_panel_line(line_id, handle=f"H{index}", start_x=40.0, start_y=40.0 + index * 10.0, end_x=70.0, end_y=40.0 + index * 10.0))

    _shadow_parallel_grid_separator_ordinary_pairs(pairs, groups, lines)

    for pair in pairs[:2]:
        assert pair.evidence["ordinary_pair_eligible"] is False
        assert pair.evidence["ordinary_pair_shadow_only"] is True
        assert pair.evidence["ordinary_pair_shadow_reason"] == "parallel_grid_separator"
    assert "ordinary_pair_shadow_reason" not in pairs[2].evidence


@pytest.mark.parametrize(
    "negative",
    [
        "two_rows",
        "different_values",
        "interior_drop",
        "block_member",
        "polyline_member",
        "alternative",
        "text_only_row",
        "discarded_claim",
        "uneven_spacing",
        "connect_layer",
        "invalid_text_id",
    ],
)
def test_parallel_grid_separator_fails_closed_for_non_authoritative_geometry(negative: str) -> None:
    top = _parallel_separator_pair(pair_id="P_TOP", line_group_id="G_TOP")
    middle = _parallel_separator_pair(pair_id="P_MIDDLE", line_group_id="G_MIDDLE")
    empty = _parallel_separator_pair(pair_id="P_EMPTY", line_group_id="G_EMPTY", value=None, text_id=None)
    if negative == "different_values":
        middle.left_text_id = "T212"
        middle.left_value = "212"
        middle.evidence["selected_left_text_id"] = "T212"
        middle.evidence["selected_left_raw_text"] = "212"
    if negative == "alternative":
        middle.alternative_pair_candidate_ids = ["ALT"]
    if negative == "text_only_row":
        empty.left_text_id = "T-UNBOUND"
    if negative == "discarded_claim":
        middle.status = "discard"
    if negative == "invalid_text_id":
        top.left_text_id = "NaN"
        top.evidence["selected_left_text_id"] = "NaN"
    pairs = [top, middle, empty]
    groups = [
        _line_group("G_TOP", start_x=40.0, end_x=70.0, start_y=40.0, end_y=40.0, orientation="horizontal", row_band_id=None, wire_score=0.55),
        _line_group("G_MIDDLE", start_x=40.0, end_x=70.0, start_y=50.0, end_y=50.0, orientation="horizontal", row_band_id=None, wire_score=0.55),
        _line_group("G_EMPTY", start_x=40.0, end_x=70.0, start_y=60.0, end_y=60.0, orientation="horizontal", row_band_id=None, wire_score=0.55),
    ]
    lines = []
    for index, group in enumerate(groups):
        line_id = f"L{index}"
        group.member_line_ids = [line_id]
        source_type = "LWPOLYLINE" if negative == "polyline_member" and index == 1 else "LINE"
        source_block = "BLOCK" if negative == "block_member" and index == 1 else None
        layer = "CONNECT" if negative == "connect_layer" else "0"
        lines.append(_panel_line(line_id, handle=f"H{index}", start_x=40.0, start_y=40.0 + index * 10.0, end_x=70.0, end_y=40.0 + index * 10.0, layer=layer, source_entity_type=source_type, source_block_name=source_block))
    if negative == "two_rows":
        groups.pop()
        pairs.pop()
        lines.pop()
    elif negative == "interior_drop":
        lines.append(_panel_line("DROP", handle="HDROP", start_x=55.0, start_y=35.0, end_x=55.0, end_y=65.0))
    elif negative == "uneven_spacing":
        groups[2].start_y = 65.0
        groups[2].end_y = 65.0
        lines[2].start_y = 65.0
        lines[2].end_y = 65.0

    _shadow_parallel_grid_separator_ordinary_pairs(pairs, groups, lines)

    assert all(pair.evidence.get("ordinary_pair_eligible") is not False for pair in pairs[:2])


def test_connect_multidrop_rail_shadows_single_sided_ordinary_pair() -> None:
    pair = _pair(
        {},
        line_group_id="G_RAIL",
        left_text_id="T828",
        left_value="828",
        right_value=None,
    )
    group = LineGroup(
        "G_RAIL", "S1", "F1", 10.0, 50.0, 90.0, 50.0, 80.0, 0.85, ["RAIL"], ["CONNECT"]
    )
    lines = [
        _panel_line("RAIL", handle="H0", start_x=10.0, start_y=50.0, end_x=90.0, end_y=50.0, layer="CONNECT"),
        _panel_line("DROP1", handle="H1", start_x=30.0, start_y=50.0, end_x=30.0, end_y=70.0, layer="CONNECT"),
        _panel_line("DROP2", handle="H2", start_x=70.0, start_y=20.0, end_x=70.0, end_y=50.0, layer="CONNECT"),
        _panel_line("CROSS", handle="H3", start_x=50.0, start_y=20.0, end_x=50.0, end_y=70.0, layer="CONNECT"),
    ]

    _shadow_connect_multidrop_rail_ordinary_pairs([pair], [group], lines)

    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["ordinary_pair_shadow_only"] is True
    assert pair.evidence["ordinary_pair_shadow_reason"] == "connect_multidrop_rail"
    assert pair.evidence["connect_multidrop_rail"] == {
        "member_line_ids": ["RAIL"],
        "interior_drop_line_ids": ["DROP1", "DROP2"],
        "interior_drop_xs": [30.0, 70.0],
        "interior_drop_count": 2,
    }


@pytest.mark.parametrize(
    ("present_side", "reverse_line", "value"),
    [("right", False, "3"), ("left", True, "7")],
)
def test_ct_polarity_reference_shadows_complete_single_sided_pair(
    present_side: str,
    reverse_line: bool,
    value: str,
) -> None:
    pair, pages, texts, groups, lines, candidates = _ct_polarity_reference_fixture(
        present_side=present_side,
        reverse_line=reverse_line,
        value=value,
    )

    _shadow_ct_polarity_reference_ordinary_pairs(
        [pair], pages, texts, groups, lines, candidates
    )

    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["ordinary_pair_shadow_only"] is True
    assert pair.evidence["ordinary_pair_shadow_reason"] == "ct_polarity_reference_annotation"
    annotation = pair.evidence["ct_polarity_reference_annotation"]
    assert annotation["line_id"] == "L_CT"
    assert annotation["selected_side"] == present_side
    assert annotation["selected_candidate_id"] == "C_VALUE"
    assert annotation["selected_text_id"] == "T_VALUE"
    assert annotation["semantic_text_ids"] == {
        "ct_polarity": ["T_POLARITY"],
        "power_flow": ["T_POWER", "T_POWER_2"],
    }
    assert set(annotation["endpoint_motif_text_ids"]["start"]) == {
        "TL_P1",
        "TL_P2",
        "TL_S1",
        "TL_S2",
        "TL_STAR1",
        "TL_STAR2",
    }
    assert set(annotation["endpoint_motif_text_ids"]["end"]) == {
        "TR_P1",
        "TR_P2",
        "TR_S1",
        "TR_S2",
        "TR_STAR1",
        "TR_STAR2",
    }


@pytest.mark.parametrize(
    "negative",
    [
        "polarity_without_motif",
        "p_labels_without_semantics",
        "missing_left_s2",
        "missing_right_s2",
        "one_star",
        "connect_layer",
        "block_owned_line",
        "polyline_line",
        "missing_group_member",
        "multiple_group_members",
        "complete_pair",
        "alternative",
        "ambiguity",
        "wrong_route",
        "pair_candidate_mismatch",
        "evidence_candidate_mismatch",
        "pair_text_mismatch",
        "evidence_text_mismatch",
        "raw_value_mismatch",
        "candidate_scope_mismatch",
        "geometry_mismatch",
        "nonnumeric_value",
        "derived_numeric",
        "present_channel_detail",
        "present_source_block",
        "pair_coord_mismatch",
        "candidate_text_insert_mismatch",
        "text_insert_mismatch",
        "malformed_candidate_endpoint",
        "duplicate_page",
        "duplicate_group",
        "duplicate_line",
        "duplicate_candidate",
        "duplicate_text",
        "candidate_channel_detail",
        "text_not_numeric_candidate",
        "malformed_member_list",
        "malformed_member_id",
        "candidate_distance_mismatch",
        "malformed_candidate_distance",
    ],
)
def test_ct_polarity_reference_keeps_incomplete_or_forged_pairs_fail_closed(
    negative: str,
) -> None:
    pair, pages, texts, groups, lines, candidates = _ct_polarity_reference_fixture()
    text_by_id = {text.text_id: text for text in texts}
    if negative == "polarity_without_motif":
        texts = [text for text in texts if not text.text_id.startswith(("TL_", "TR_"))]
    elif negative == "p_labels_without_semantics":
        texts = [text for text in texts if text.text_id not in {"T_POLARITY", "T_POWER"}]
    elif negative == "missing_left_s2":
        texts = [text for text in texts if text.text_id != "TL_S2"]
    elif negative == "missing_right_s2":
        texts = [text for text in texts if text.text_id != "TR_S2"]
    elif negative == "one_star":
        texts = [text for text in texts if text.text_id != "TL_STAR2"]
    elif negative == "connect_layer":
        lines[0].layer = "CONNECT"
    elif negative == "block_owned_line":
        lines[0].source_block_name = "CT_BLOCK"
    elif negative == "polyline_line":
        lines[0].source_entity_type = "LWPOLYLINE"
    elif negative == "missing_group_member":
        groups[0].member_line_ids = []
    elif negative == "multiple_group_members":
        groups[0].member_line_ids = ["L_CT", "L_EXTRA"]
        lines.append(_panel_line("L_EXTRA", handle="H_EXTRA", start_x=10.0, start_y=50.0, end_x=110.0, end_y=50.0))
    elif negative == "complete_pair":
        pair.left_value = "2"
        pair.left_text_id = "T_LEFT"
    elif negative == "alternative":
        pair.alternative_pair_candidate_ids = ["PC_ALT"]
    elif negative == "ambiguity":
        pair.ambiguity_gap = 0.1
    elif negative == "wrong_route":
        pages[0].route_target = "ComponentDiagramExtractor"
    elif negative == "pair_candidate_mismatch":
        pair.right_candidate_id = "C_OTHER"
    elif negative == "evidence_candidate_mismatch":
        pair.evidence["selected_right_candidate_id"] = "C_OTHER"
    elif negative == "pair_text_mismatch":
        pair.right_text_id = "T_OTHER"
    elif negative == "evidence_text_mismatch":
        pair.evidence["selected_right_text_id"] = "T_OTHER"
    elif negative == "raw_value_mismatch":
        pair.evidence["selected_right_raw_text"] = "4"
    elif negative == "candidate_scope_mismatch":
        candidates[0].file_id = "F2"
    elif negative == "geometry_mismatch":
        pair.evidence["line_end"] = [111.0, 50.0]
    elif negative == "nonnumeric_value":
        pair.right_value = "ABC"
        pair.pair_key = "?->ABC"
        pair.evidence["pair_key"] = "?->ABC"
        pair.evidence["selected_right_raw_text"] = "ABC"
        candidates[0].value = "ABC"
        candidates[0].text = "ABC"
        text_by_id["T_VALUE"].text = "ABC"
        text_by_id["T_VALUE"].normalized_text = "ABC"
    elif negative == "derived_numeric":
        pair.evidence["selected_right_is_derived_numeric"] = True
    elif negative == "present_channel_detail":
        pair.evidence["selected_right_channel_detail"] = "derived"
    elif negative == "present_source_block":
        pair.evidence["selected_right_source_block_name"] = "BLOCK"
    elif negative == "pair_coord_mismatch":
        pair.right_coord_x = 999.0
    elif negative == "candidate_text_insert_mismatch":
        candidates[0].text_insert_x = 999.0
    elif negative == "text_insert_mismatch":
        text_by_id["T_VALUE"].insert_x = 999.0
    elif negative == "malformed_candidate_endpoint":
        candidates[0].endpoint_x = None
    elif negative == "duplicate_page":
        pages.append(pages[0])
    elif negative == "duplicate_group":
        groups.append(groups[0])
    elif negative == "duplicate_line":
        lines.append(lines[0])
    elif negative == "duplicate_candidate":
        candidates.append(candidates[0])
    elif negative == "duplicate_text":
        texts.append(text_by_id["T_VALUE"])
    elif negative == "candidate_channel_detail":
        candidates[0].channel_detail = "derived"
    elif negative == "text_not_numeric_candidate":
        text_by_id["T_VALUE"].is_numeric_candidate = False
    elif negative == "malformed_member_list":
        groups[0].member_line_ids = None
    elif negative == "malformed_member_id":
        groups[0].member_line_ids = [["L_CT"]]
    elif negative == "candidate_distance_mismatch":
        candidates[0].distance_x = 999.0
    elif negative == "malformed_candidate_distance":
        candidates[0].distance_y = "bad"

    _shadow_ct_polarity_reference_ordinary_pairs(
        [pair], pages, texts, groups, lines, candidates
    )

    assert pair.evidence.get("ordinary_pair_shadow_reason") != "ct_polarity_reference_annotation"


@pytest.mark.parametrize(
    ("pair_changes", "group_layer", "extra_lines"),
    [
        ({}, "CONNECT", []),
        (
            {},
            "CONNECT",
            [
                _panel_line("SAME_X", handle="H4", start_x=30.1, start_y=50.0, end_x=30.1, end_y=80.0, layer="CONNECT"),
            ],
        ),
        (
            {},
            "CONNECT",
            [
                _panel_line("NON_CONNECT", handle="H5", start_x=70.0, start_y=50.0, end_x=70.0, end_y=80.0, layer="0"),
            ],
        ),
        (
            {},
            "CONNECT",
            [
                _panel_line("EDGE_SLANT", handle="H6", start_x=10.2, start_y=50.0, end_x=10.45, end_y=80.0, layer="CONNECT"),
            ],
        ),
        (
            {"alternative_pair_candidate_ids": ["ALT"]},
            "CONNECT",
            [
                _panel_line("DROP2", handle="H7", start_x=70.0, start_y=50.0, end_x=70.0, end_y=80.0, layer="CONNECT"),
            ],
        ),
        (
            {"ambiguity_gap": 0.1},
            "CONNECT",
            [
                _panel_line("DROP2", handle="H8", start_x=70.0, start_y=50.0, end_x=70.0, end_y=80.0, layer="CONNECT"),
            ],
        ),
        (
            {},
            "CONNECT",
            [
                _panel_line(
                    "BLOCK_DROP",
                    handle="H9",
                    start_x=70.0,
                    start_y=50.0,
                    end_x=70.0,
                    end_y=80.0,
                    layer="CONNECT",
                    source_block_name="BLOCK",
                ),
            ],
        ),
        (
            {},
            "CONNECT",
            [
                _panel_line(
                    "POLY_DROP",
                    handle="H10",
                    start_x=70.0,
                    start_y=50.0,
                    end_x=70.0,
                    end_y=80.0,
                    layer="CONNECT",
                    source_entity_type="LWPOLYLINE",
                ),
            ],
        ),
        ({"right_value": "829", "right_text_id": "T829"}, "CONNECT", []),
        ({}, "0", []),
    ],
)
def test_connect_multidrop_rail_keeps_incomplete_or_non_authoritative_geometry(
    pair_changes: dict[str, object],
    group_layer: str,
    extra_lines: list[LineEntity],
) -> None:
    pair = _pair(
        {},
        line_group_id="G_RAIL",
        left_text_id="T828",
        left_value="828",
        right_value=None,
    )
    for key, value in pair_changes.items():
        setattr(pair, key, value)
    group = LineGroup(
        "G_RAIL", "S1", "F1", 10.0, 50.0, 90.0, 50.0, 80.0, 0.85, ["RAIL"], [group_layer]
    )
    lines = [
        _panel_line("RAIL", handle="H0", start_x=10.0, start_y=50.0, end_x=90.0, end_y=50.0, layer=group_layer),
        _panel_line("DROP1", handle="H1", start_x=30.0, start_y=50.0, end_x=30.0, end_y=70.0, layer="CONNECT"),
        _panel_line("CROSS", handle="H3", start_x=70.0, start_y=20.0, end_x=70.0, end_y=80.0, layer="CONNECT"),
        *extra_lines,
    ]

    _shadow_connect_multidrop_rail_ordinary_pairs([pair], [group], lines)

    assert pair.evidence.get("ordinary_pair_eligible") is not False
    assert "ordinary_pair_shadow_reason" not in pair.evidence


def test_closed_tall_polyline_enclosure_edge_shadows_ordinary_pair() -> None:
    pair = _pair({}, line_group_id="G_FRAME", left_value="1027", right_value="1028")
    lines = _closed_tall_frame_lines()
    group = LineGroup(
        "G_FRAME", "S1", "F1", 105.0, 80.0, 150.0, 80.0, 45.0, 0.55, ["LF0"], ["0"]
    )

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["ordinary_pair_shadow_only"] is True
    assert pair.evidence["ordinary_pair_shadow_reason"] == "closed_tall_polyline_enclosure_edge"
    assert pair.evidence["closed_polyline_enclosure"] == {
        "parent_handle": "F41",
        "width": 45.0,
        "height": 190.0,
    }


def test_closed_polyline_duplicate_edge_shadows_only_with_unique_connect_claim() -> None:
    frame_pair = _pair(
        {},
        pair_id="P_FRAME",
        line_group_id="G_FRAME",
        left_text_id="T1731",
        left_value="1731",
        right_value=None,
    )
    connect_pair = _pair(
        {},
        pair_id="P_CONNECT",
        line_group_id="G_CONNECT",
        left_text_id="T1731",
        left_value="1731",
        right_value=None,
    )
    frame_lines = _closed_tall_frame_lines(height=90.0, y1=82.5)
    connect_line = _panel_line(
        "CONNECT_LINE",
        handle="CONNECT1",
        start_x=110.0,
        start_y=80.0,
        end_x=145.0,
        end_y=80.0,
        layer="CONNECT",
    )
    drop_lines = [
        _panel_line(
            "DROP1",
            handle="DROP1",
            start_x=120.0,
            start_y=80.0,
            end_x=120.0,
            end_y=60.0,
            layer="CONNECT",
        ),
        _panel_line(
            "DROP2",
            handle="DROP2",
            start_x=135.0,
            start_y=80.0,
            end_x=135.0,
            end_y=100.0,
            layer="CONNECT",
        ),
    ]
    frame_group = LineGroup(
        "G_FRAME", "S1", "F1", 105.0, 82.5, 150.0, 82.5, 45.0, 0.55, ["LF0"], ["0"]
    )
    connect_group = LineGroup(
        "G_CONNECT", "S1", "F1", 110.0, 80.0, 145.0, 80.0, 35.0, 0.85, ["CONNECT_LINE"], ["CONNECT"]
    )

    all_lines = [*frame_lines, connect_line, *drop_lines]
    _shadow_closed_tall_polyline_enclosure_ordinary_pairs(
        [frame_pair, connect_pair],
        [frame_group, connect_group],
        all_lines,
        [_panel_text("T1731", "1731", x=105.0, y=80.0)],
    )
    _shadow_connect_multidrop_rail_ordinary_pairs(
        [frame_pair, connect_pair],
        [frame_group, connect_group],
        all_lines,
    )

    assert frame_pair.evidence["ordinary_pair_eligible"] is False
    assert frame_pair.evidence["ordinary_pair_shadow_reason"] == "closed_polyline_duplicate_enclosure_edge"
    assert frame_pair.evidence["closed_polyline_enclosure"]["canonical_pair_id"] == "P_CONNECT"
    assert connect_pair.evidence["ordinary_pair_eligible"] is False
    assert connect_pair.evidence["ordinary_pair_shadow_reason"] == "connect_multidrop_rail"


def test_closed_polyline_duplicate_edge_fails_closed_without_text_height() -> None:
    frame_pair = _pair(
        {},
        pair_id="P_FRAME",
        line_group_id="G_FRAME",
        left_text_id="T1731",
        left_value="1731",
        right_value=None,
    )
    connect_pair = _pair(
        {},
        pair_id="P_CONNECT",
        line_group_id="G_CONNECT",
        left_text_id="T1731",
        left_value="1731",
        right_value=None,
    )
    lines = _closed_tall_frame_lines(height=90.0, y1=82.5)
    lines.append(
        _panel_line(
            "CONNECT_LINE",
            handle="CONNECT1",
            start_x=105.0,
            start_y=80.0,
            end_x=150.0,
            end_y=80.0,
            layer="CONNECT",
        )
    )
    groups = [
        LineGroup("G_FRAME", "S1", "F1", 105.0, 82.5, 150.0, 82.5, 45.0, 0.55, ["LF0"], ["0"]),
        LineGroup("G_CONNECT", "S1", "F1", 105.0, 80.0, 150.0, 80.0, 45.0, 0.85, ["CONNECT_LINE"], ["CONNECT"]),
    ]

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs(
        [frame_pair, connect_pair], groups, lines
    )

    assert frame_pair.evidence.get("ordinary_pair_eligible") is not False


def test_closed_polyline_duplicate_edge_rejects_short_connect_overlap() -> None:
    frame_pair = _pair(
        {},
        pair_id="P_FRAME",
        line_group_id="G_FRAME",
        left_text_id="T1731",
        left_value="1731",
        right_value=None,
    )
    connect_pair = _pair(
        {},
        pair_id="P_CONNECT",
        line_group_id="G_CONNECT",
        left_text_id="T1731",
        left_value="1731",
        right_value=None,
    )
    lines = _closed_tall_frame_lines(height=90.0, y1=82.5)
    lines.append(
        _panel_line(
            "CONNECT_LINE",
            handle="CONNECT1",
            start_x=120.0,
            start_y=80.0,
            end_x=130.0,
            end_y=80.0,
            layer="CONNECT",
        )
    )
    groups = [
        LineGroup("G_FRAME", "S1", "F1", 105.0, 82.5, 150.0, 82.5, 45.0, 0.55, ["LF0"], ["0"]),
        LineGroup("G_CONNECT", "S1", "F1", 120.0, 80.0, 130.0, 80.0, 10.0, 0.85, ["CONNECT_LINE"], ["CONNECT"]),
    ]

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs(
        [frame_pair, connect_pair],
        groups,
        lines,
        [_panel_text("T1731", "1731", x=120.0, y=80.0)],
    )

    assert frame_pair.evidence.get("ordinary_pair_eligible") is not False


@pytest.mark.parametrize(
    ("text_id", "connect_source_type", "connect_layer", "connect_start_x", "alternatives", "ambiguity_gap"),
    [
        ("NaN", "LINE", "CONNECT", 110.0, [], None),
        ("T1731", "LWPOLYLINE", "CONNECT", 110.0, [], None),
        ("T1731", "LINE", "0", 110.0, [], None),
        ("T1731", "LINE", "CONNECT", 110.0, ["ALT"], None),
        ("T1731", "LINE", "CONNECT", 110.0, [], 0.2),
        ("T1731", "LINE", "CONNECT", 90.0, [], None),
    ],
)
def test_closed_polyline_duplicate_edge_rejects_non_authoritative_connect_claim(
    text_id: str,
    connect_source_type: str,
    connect_layer: str,
    connect_start_x: float,
    alternatives: list[str],
    ambiguity_gap: float | None,
) -> None:
    frame_pair = _pair(
        {},
        pair_id="P_FRAME",
        line_group_id="G_FRAME",
        left_text_id=text_id,
        left_value="1731",
        right_value=None,
    )
    connect_pair = _pair(
        {},
        pair_id="P_CONNECT",
        line_group_id="G_CONNECT",
        left_text_id=text_id,
        left_value="1731",
        right_value=None,
    )
    connect_pair.alternative_pair_candidate_ids = alternatives
    connect_pair.ambiguity_gap = ambiguity_gap
    lines = _closed_tall_frame_lines(height=90.0, y1=82.5)
    lines.append(
        _panel_line(
            "CONNECT_LINE",
            handle="CONNECT1",
            start_x=connect_start_x,
            start_y=80.0,
            end_x=145.0,
            end_y=80.0,
            layer=connect_layer,
            source_entity_type=connect_source_type,
        )
    )
    groups = [
        LineGroup("G_FRAME", "S1", "F1", 105.0, 82.5, 150.0, 82.5, 45.0, 0.55, ["LF0"], ["0"]),
        LineGroup(
            "G_CONNECT",
            "S1",
            "F1",
            connect_start_x,
            80.0,
            145.0,
            80.0,
            145.0 - connect_start_x,
            0.85,
            ["CONNECT_LINE"],
            [connect_layer],
        ),
    ]

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs(
        [frame_pair, connect_pair],
        groups,
        lines,
        [_panel_text(text_id, "1731", x=110.0, y=80.0)],
    )

    assert frame_pair.evidence.get("ordinary_pair_eligible") is not False


def test_closed_tall_polyline_enclosure_keeps_group_with_connect_line() -> None:
    pair = _pair({}, line_group_id="G_WIRE", left_value="1201", right_value="1204")
    lines = _closed_tall_frame_lines()
    lines.append(
        _panel_line(
            "LC",
            handle="CONNECT1",
            start_x=127.5,
            start_y=80.0,
            end_x=167.5,
            end_y=80.0,
            layer="CONNECT",
        )
    )
    group = LineGroup(
        "G_WIRE", "S1", "F1", 105.0, 80.0, 167.5, 80.0, 62.5, 0.7, ["LF0", "LC"], ["0", "CONNECT"]
    )

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert pair.evidence.get("ordinary_pair_eligible") is not False


def test_closed_tall_polyline_enclosure_preserves_structured_mapping() -> None:
    mapping = _pair(
        {},
        line_group_id="G_FRAME",
        pair_kind="component_mapping",
        left_value="1-26n432",
        right_value="1-26TD46",
    )
    group = LineGroup(
        "G_FRAME", "S1", "F1", 105.0, 80.0, 150.0, 80.0, 45.0, 0.55, ["LF0"], ["0"]
    )

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs(
        [mapping], [group], _closed_tall_frame_lines()
    )

    assert mapping.evidence.get("ordinary_pair_eligible") is not False


def test_closed_polyline_requires_tall_enclosure_geometry() -> None:
    pair = _pair({}, line_group_id="G_FRAME")
    lines = _closed_tall_frame_lines(height=90.0)
    group = LineGroup(
        "G_FRAME", "S1", "F1", 105.0, 80.0, 150.0, 80.0, 45.0, 0.55, ["LF0"], ["0"]
    )

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert pair.evidence.get("ordinary_pair_eligible") is not False


def test_repeated_closed_polyline_enclosure_shadows_complete_half_pair() -> None:
    pair, group, lines = _repeated_enclosure_fixture()

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["ordinary_pair_shadow_only"] is True
    assert pair.evidence["ordinary_pair_shadow_reason"] == "closed_repeated_polyline_enclosure_edge"
    assert pair.evidence["closed_polyline_enclosure"] == {
        "parent_handles": ["RP0", "RP1", "RP2"],
        "parent_count": 3,
        "member_edge_line_ids": ["RF0L0", "RF1L0", "RF2L0"],
        "layer": "0",
        "width": 45.0,
        "height": 30.0,
        "shared_side": "left",
        "shared_value": "1201",
        "shared_text_id": "T1201",
    }


def test_repeated_closed_polyline_enclosure_accepts_right_side_vertical_edge() -> None:
    pair, group, lines = _repeated_enclosure_fixture(vertical=True)
    pair.left_value = None
    pair.left_text_id = None
    pair.left_candidate_id = None
    pair.right_value = "1201"
    pair.right_text_id = "T1201"
    pair.right_candidate_id = "C1201"
    for field in (
        "selected_left_candidate_id",
        "selected_left_text_id",
        "selected_left_raw_text",
        "selected_left_channel",
        "selected_left_source_block_name",
    ):
        pair.evidence[field] = None
    pair.evidence.update(
        {
            "selected_right_candidate_id": "C1201",
            "selected_right_text_id": "T1201",
            "selected_right_raw_text": "1201",
            "selected_right_is_derived_numeric": False,
            "selected_right_source_block_name": None,
        }
    )

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert pair.evidence["ordinary_pair_shadow_reason"] == "closed_repeated_polyline_enclosure_edge"
    assert pair.evidence["closed_polyline_enclosure"]["shared_side"] == "right"


@pytest.mark.parametrize(
    "negative",
    [
        "discarded",
        "already_ineligible",
        "shadow_only",
        "alternative",
        "ambiguity",
        "two_sided",
        "missing_selected_pair",
        "missing_selected_candidate",
        "mismatched_selected_text",
        "mismatched_raw_value",
        "absent_side_evidence",
        "derived_numeric",
        "line_evidence_mismatch",
        "padded_value",
        "padded_text_id",
        "padded_candidate_id",
    ],
)
def test_repeated_closed_polyline_enclosure_rejects_incomplete_pair_contract(negative: str) -> None:
    pair, group, lines = _repeated_enclosure_fixture()
    if negative == "discarded":
        pair.status = "discard"
    elif negative == "already_ineligible":
        pair.evidence["ordinary_pair_eligible"] = False
    elif negative == "shadow_only":
        pair.evidence["ordinary_pair_shadow_only"] = True
    elif negative == "alternative":
        pair.alternative_pair_candidate_ids = ["ALT"]
    elif negative == "ambiguity":
        pair.ambiguity_gap = 0.1
    elif negative == "two_sided":
        pair.right_value = "1202"
        pair.right_text_id = "T1202"
        pair.right_candidate_id = "C1202"
    elif negative == "missing_selected_pair":
        pair.selected_pair_candidate_id = None
    elif negative == "missing_selected_candidate":
        pair.evidence["selected_left_candidate_id"] = None
    elif negative == "mismatched_selected_text":
        pair.evidence["selected_left_text_id"] = "T-OTHER"
    elif negative == "mismatched_raw_value":
        pair.evidence["selected_left_raw_text"] = "1201 "
    elif negative == "absent_side_evidence":
        pair.evidence["selected_right_text_id"] = "T-GHOST"
    elif negative == "derived_numeric":
        pair.evidence["selected_left_is_derived_numeric"] = True
    elif negative == "line_evidence_mismatch":
        pair.evidence["line_end"] = [150.251, 80.0]
    elif negative == "padded_value":
        pair.left_value = " 1201"
        pair.evidence["selected_left_raw_text"] = " 1201"
    elif negative == "padded_text_id":
        pair.left_text_id = " T1201"
        pair.evidence["selected_left_text_id"] = " T1201"
    elif negative == "padded_candidate_id":
        pair.left_candidate_id = " C1201"
        pair.evidence["selected_left_candidate_id"] = " C1201"

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert pair.evidence.get("ordinary_pair_shadow_reason") != "closed_repeated_polyline_enclosure_edge"


@pytest.mark.parametrize(
    "negative",
    [
        "two_parents",
        "bbox_outside_tolerance",
        "cross_parent_layer",
        "block_owned_edge",
        "two_edges_from_one_parent",
        "mixed_frame_edges",
        "extra_connect_member",
        "duplicate_member_id",
        "group_scope_mismatch",
        "pair_scope_mismatch",
        "open_parent",
    ],
)
def test_repeated_closed_polyline_enclosure_rejects_incomplete_geometry(negative: str) -> None:
    third_x2 = 150.250001 if negative == "bbox_outside_tolerance" else 150.0
    pair, group, lines = _repeated_enclosure_fixture(third_x2=third_x2)
    if negative == "two_parents":
        lines = [line for line in lines if not line.line_id.startswith("RF2")]
        group.member_line_ids.remove("RF2L0")
    elif negative == "cross_parent_layer":
        for line in lines:
            if line.line_id.startswith("RF2"):
                line.layer = "DIM"
        group.layer_hints = ["0", "DIM"]
    elif negative == "block_owned_edge":
        next(line for line in lines if line.line_id == "RF2L0").source_block_name = "FRAME-BLOCK"
    elif negative == "two_edges_from_one_parent":
        group.member_line_ids.append("RF0L2")
    elif negative == "mixed_frame_edges":
        group.member_line_ids[-1] = "RF2L2"
    elif negative == "extra_connect_member":
        lines.append(
            _panel_line(
                "CONNECT",
                handle="CONNECT",
                start_x=105.0,
                start_y=80.0,
                end_x=150.0,
                end_y=80.0,
                layer="CONNECT",
            )
        )
        group.member_line_ids.append("CONNECT")
    elif negative == "duplicate_member_id":
        group.member_line_ids.append("RF2L0")
    elif negative == "group_scope_mismatch":
        group.file_id = "F2"
    elif negative == "pair_scope_mismatch":
        pair.file_id = "F2"
    elif negative == "open_parent":
        lines = [line for line in lines if line.line_id != "RF2L3"]

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert pair.evidence.get("ordinary_pair_shadow_reason") != "closed_repeated_polyline_enclosure_edge"


@pytest.mark.parametrize(("delta", "accepted"), [(0.25, True), (0.250001, False)])
def test_repeated_closed_polyline_enclosure_locks_bbox_tolerance(
    delta: float,
    accepted: bool,
) -> None:
    pair, group, lines = _repeated_enclosure_fixture(third_x2=150.0 + delta)

    _shadow_closed_tall_polyline_enclosure_ordinary_pairs([pair], [group], lines)

    assert (
        pair.evidence.get("ordinary_pair_shadow_reason")
        == "closed_repeated_polyline_enclosure_edge"
    ) is accepted


def _repeated_enclosure_fixture(
    *,
    third_x2: float = 150.0,
    vertical: bool = False,
) -> tuple[Pair, LineGroup, list[LineEntity]]:
    evidence = {
        "pair_kind": "ordinary_pair",
        "line_orientation": "vertical" if vertical else "horizontal",
        "line_start": [105.0, 80.0],
        "line_end": [105.0, 110.0] if vertical else [150.0, 80.0],
        "selected_pair_candidate_id": "PC1",
        "selected_left_candidate_id": "C1201",
        "selected_right_candidate_id": None,
        "selected_left_text_id": "T1201",
        "selected_right_text_id": None,
        "selected_left_raw_text": "1201",
        "selected_right_raw_text": None,
        "selected_left_is_derived_numeric": False,
        "selected_right_is_derived_numeric": False,
        "selected_left_source_block_name": None,
        "selected_right_source_block_name": None,
        "selected_right_channel": None,
        "alternative_pair_candidate_ids": [],
        "score_breakdown": {"ambiguity_gap": None},
    }
    pair = _pair(
        evidence,
        pair_id="P-REPEATED",
        line_group_id="G-REPEATED",
        left_text_id="T1201",
        left_value="1201",
        right_value=None,
    )
    pair.left_candidate_id = "C1201"
    group = (
        LineGroup(
            "G-REPEATED",
            "S1",
            "F1",
            105.0,
            80.0,
            105.0,
            110.0,
            30.0,
            0.55,
            ["RF0L3", "RF1L3", "RF2L3"],
            ["0"],
            "vertical",
        )
        if vertical
        else LineGroup(
            "G-REPEATED",
            "S1",
            "F1",
            105.0,
            80.0,
            150.0,
            80.0,
            45.0,
            0.55,
            ["RF0L0", "RF1L0", "RF2L0"],
            ["0"],
            "horizontal",
        )
    )
    lines: list[LineEntity] = []
    for index in range(3):
        lines.extend(
            _closed_frame_lines(
                parent_handle=f"RP{index}",
                line_prefix=f"RF{index}L",
                x2=third_x2 if index == 2 else 150.0,
            )
        )
    return pair, group, lines


def _closed_frame_lines(
    *,
    parent_handle: str,
    line_prefix: str,
    x1: float = 105.0,
    x2: float = 150.0,
    y1: float = 80.0,
    height: float = 30.0,
) -> list[LineEntity]:
    y2 = y1 + height
    return [
        _panel_line(
            f"{line_prefix}0",
            handle=f"{parent_handle}:0",
            start_x=x1,
            start_y=y1,
            end_x=x2,
            end_y=y1,
            source_entity_type="LWPOLYLINE",
        ),
        _panel_line(
            f"{line_prefix}1",
            handle=f"{parent_handle}:1",
            start_x=x2,
            start_y=y1,
            end_x=x2,
            end_y=y2,
            source_entity_type="LWPOLYLINE",
        ),
        _panel_line(
            f"{line_prefix}2",
            handle=f"{parent_handle}:2",
            start_x=x2,
            start_y=y2,
            end_x=x1,
            end_y=y2,
            source_entity_type="LWPOLYLINE",
        ),
        _panel_line(
            f"{line_prefix}3",
            handle=f"{parent_handle}:3",
            start_x=x1,
            start_y=y2,
            end_x=x1,
            end_y=y1,
            source_entity_type="LWPOLYLINE",
        ),
    ]


def _closed_tall_frame_lines(*, height: float = 190.0, y1: float = 80.0) -> list[LineEntity]:
    x1, x2, y2 = 105.0, 150.0, y1 + height
    return [
        _panel_line(
            "LF0", handle="F41:0", start_x=x1, start_y=y1, end_x=x2, end_y=y1,
            source_entity_type="LWPOLYLINE",
        ),
        _panel_line(
            "LF1", handle="F41:1", start_x=x2, start_y=y1, end_x=x2, end_y=y2,
            source_entity_type="LWPOLYLINE",
        ),
        _panel_line(
            "LF2", handle="F41:2", start_x=x2, start_y=y2, end_x=x1, end_y=y2,
            source_entity_type="LWPOLYLINE",
        ),
        _panel_line(
            "LF3", handle="F41:3", start_x=x1, start_y=y2, end_x=x1, end_y=y1,
            source_entity_type="LWPOLYLINE",
        ),
    ]


def test_shadow_communication_medium_ordinary_pairs_marks_serial_pages_ineligible() -> None:
    from dwg_audit.audit.page_extractors import _shadow_communication_medium_ordinary_pairs

    ordinary = _pair({"line_orientation": "horizontal"})
    ordinary.status = "review"
    ordinary.confidence_bucket = "review"
    sheet = _sheet(route_target="WireDiagramExtractor", page_subtype=None, grid_heavy=False)
    sheet.communication_media = ["serial"]

    _shadow_communication_medium_ordinary_pairs([ordinary], [sheet])

    assert ordinary.evidence["ordinary_pair_eligible"] is False
    assert ordinary.evidence["ordinary_pair_shadow_only"] is True
    assert ordinary.evidence["ordinary_pair_shadow_reason"] == "communication_medium"
    assert ordinary.evidence["communication_media"] == ["serial"]


def test_signal_alarm_cues_do_not_shadow_real_ordinary_pairs() -> None:
    from dwg_audit.audit.page_extractors import _shadow_signal_alarm_ordinary_pairs
    from dwg_audit.domain.models import TextItem

    ordinary = _pair({"line_orientation": "horizontal"})
    ordinary.status = "review"
    ordinary.confidence_bucket = "review"
    sheet = _sheet(route_target="WireDiagramExtractor", page_subtype=None, grid_heavy=False)
    sheet.sheet_category = "二次原理图"
    texts = [
        TextItem(
            text_id="T1",
            sheet_id=sheet.sheet_id,
            file_id="F1",
            handle="H1",
            entity_type="TEXT",
            text="电度表告警",
            normalized_text="电度表告警",
            is_numeric_candidate=False,
            layer="TEXT",
            rotation_deg=0.0,
            height=2.5,
            insert_x=40.0,
            insert_y=40.0,
            bbox_min_x=38.0,
            bbox_min_y=38.0,
            bbox_max_x=60.0,
            bbox_max_y=42.0,
        )
    ]

    _shadow_signal_alarm_ordinary_pairs([ordinary], [sheet], texts)

    assert ordinary.evidence.get("ordinary_pair_eligible") is not False
    assert "ordinary_pair_shadow_reason" not in ordinary.evidence


def test_promote_xjdz_structural_component_pairs_preserves_full_endpoint_and_pin() -> None:
    pair = _pair(
        {},
        line_group_id="GX1",
        left_text_id="TX_LEFT",
        right_text_id="TX_PIN",
        left_value="6",
        right_value="8",
    )
    group = _line_group(
        "GX1",
        start_x=10.0,
        end_x=10.0,
        start_y=20.0,
        end_y=0.0,
        orientation="vertical",
    )
    group.member_line_ids = ["LX1", "LX2", "LX3"]

    def text(text_id: str, value: str, *, block: str | None = None) -> TextItem:
        return TextItem(
            text_id=text_id,
            sheet_id="S1",
            file_id="F1",
            handle=text_id,
            entity_type="TEXT",
            text=value,
            normalized_text=value,
            is_numeric_candidate=value.isdigit(),
            layer="0",
            rotation_deg=0.0,
            height=2.5,
            insert_x=10.0,
            insert_y=10.0,
            bbox_min_x=9.0,
            bbox_min_y=9.0,
            bbox_max_x=11.0,
            bbox_max_y=11.0,
            source_block_name=block,
        )

    line = LineEntity(
        line_id="LX1",
        sheet_id="S1",
        file_id="F1",
        handle="HX1:VIRTUAL:1",
        source_entity_type="LINE",
        layer="BORDER",
        start_x=10.0,
        start_y=20.0,
        end_x=10.0,
        end_y=0.0,
        length=20.0,
        angle_deg=90.0,
        bbox_min_x=10.0,
        bbox_min_y=0.0,
        bbox_max_x=10.0,
        bbox_max_y=20.0,
        source_block_name="XJDZ9-02-2B4-001",
    )
    adjacent_definition_line = LineEntity(
        line_id="LX2",
        sheet_id="S1",
        file_id="F1",
        handle="HX2",
        source_entity_type="LINE",
        layer="BORDER",
        start_x=10.0,
        start_y=40.0,
        end_x=10.0,
        end_y=20.0,
        length=20.0,
        angle_deg=90.0,
        bbox_min_x=10.0,
        bbox_min_y=20.0,
        bbox_max_x=10.0,
        bbox_max_y=40.0,
        source_block_name="XJDZ9-06-4B4-011",
    )
    same_instance_definition_line = LineEntity(
        line_id="LX3",
        sheet_id="S1",
        file_id="F1",
        handle="HX1:VIRTUAL:2",
        source_entity_type="LINE",
        layer="BORDER",
        start_x=10.0,
        start_y=0.0,
        end_x=10.0,
        end_y=-20.0,
        length=20.0,
        angle_deg=90.0,
        bbox_min_x=10.0,
        bbox_min_y=-20.0,
        bbox_max_x=10.0,
        bbox_max_y=0.0,
        source_block_name="XJDZ9-02-2B4-001",
    )

    _promote_xjdz_structural_component_pairs(
        [pair],
        [group],
        [text("TX_LEFT", "3-21CD6"), text("TX_PIN", "8", block="XJDZ9-02-2B4-001")],
        [line, adjacent_definition_line, same_instance_definition_line],
    )

    assert pair.left_value == "3-21CD6"
    assert pair.right_value == "XJDZ9-02-2B4-001:8"
    assert pair.pair_kind == "component_mapping"
    assert pair.status == "pass"
    assert pair.evidence["internal_connectivity_inferred"] is False
    assert pair.evidence["electrical_union_eligible"] is False


def test_promote_xjdz_structural_component_pairs_requires_definition_owned_group() -> None:
    pair = _pair(
        {},
        line_group_id="GX2",
        left_text_id="TX_LEFT",
        right_text_id="TX_RIGHT",
        left_value="11",
        right_value="8",
    )
    group = _line_group("GX2", start_x=10.0, end_x=10.0, orientation="vertical")

    _promote_xjdz_structural_component_pairs([pair], [group], [], [])

    assert pair.left_value == "11"
    assert pair.right_value == "8"
    assert pair.pair_kind == "ordinary_pair"
    assert pair.status == "review"


def test_repeated_panel_geometry_shadows_only_single_sided_dim_silkscreen() -> None:
    from dwg_audit.audit.page_extractors import (
        _shadow_repeated_panel_silkscreen_ordinary_pairs,
    )
    from dwg_audit.domain.models import BlockRecord
    from dwg_audit.domain.models import TextItem

    sheet = _sheet(route_target="WireDiagramExtractor")
    sheet.sheet_category = "二次原理图"
    sheet.filename = "09 电度表通信回2.dwg"
    sheet.sheet_title = "COMMUNICATION CIRCUIT 2"
    blocks = [
        BlockRecord(
            block_id=f"B{row}",
            sheet_id=sheet.sheet_id,
            file_id="F1",
            handle=f"H{row}",
            name=f"PANEL_CELL_{row}",
            layer="0",
            insert_x=82.5,
            insert_y=142.5 + 22.5 * row,
            rotation_deg=0.0,
            attributes_json="{}",
        )
        for row in range(4)
    ]
    texts = [
        TextItem(
            text_id="T16",
            sheet_id=sheet.sheet_id,
            file_id="F1",
            handle="HT16",
            entity_type="TEXT",
            text="16",
            normalized_text="16",
            is_numeric_candidate=True,
            layer="DIM",
            rotation_deg=0.0,
            height=2.5,
            insert_x=83.6,
            insert_y=143.75,
            bbox_min_x=82.0,
            bbox_min_y=142.0,
            bbox_max_x=86.0,
            bbox_max_y=145.0,
        )
    ]
    silkscreen = _pair(
        {"selected_right_raw_text": "16"},
        pair_id="PSILK",
        right_text_id="T16",
    )
    silkscreen.left_value = None
    silkscreen.right_value = "16"
    real_pair = _pair(
        {"selected_left_raw_text": "16", "selected_right_raw_text": "35"},
        pair_id="PREAL",
        left_text_id="T16",
        right_text_id="T35",
    )
    real_pair.left_value = "16"
    real_pair.right_value = "35"

    _shadow_repeated_panel_silkscreen_ordinary_pairs(
        [silkscreen, real_pair],
        [sheet],
        texts,
        blocks,
    )

    assert silkscreen.evidence["ordinary_pair_eligible"] is False
    assert silkscreen.evidence["ordinary_pair_shadow_reason"] == "repeated_panel_numeric_silkscreen"
    assert real_pair.evidence.get("ordinary_pair_eligible") is not False


def test_panel_title_without_repeated_geometry_does_not_shadow_numeric_pair() -> None:
    from dwg_audit.audit.page_extractors import (
        _shadow_repeated_panel_silkscreen_ordinary_pairs,
    )

    sheet = _sheet(route_target="WireDiagramExtractor")
    sheet.sheet_category = "二次原理图"
    sheet.filename = "09 电度表通信回2.dwg"
    ordinary = _pair({}, right_text_id="T16")
    ordinary.left_value = None
    ordinary.right_value = "16"

    _shadow_repeated_panel_silkscreen_ordinary_pairs([ordinary], [sheet], [], [])

    assert ordinary.evidence.get("ordinary_pair_eligible") is not False


def test_shadow_hmc_silkscreen_ordinary_pairs_marks_hd_pin_stubs_ineligible() -> None:
    from dwg_audit.audit.page_extractors import _shadow_hmc_silkscreen_ordinary_pairs
    from dwg_audit.domain.models import TextItem

    hd_stub = _pair(
        {
            "line_orientation": "vertical",
            "selected_left_raw_text": "HD18",
            "selected_right_raw_text": None,
        },
        pair_id="PHD",
        left_text_id="T-HD",
    )
    hd_stub.left_value = "18"
    hd_stub.right_value = None
    hd_stub.status = "review"
    hd_stub.confidence_bucket = "review"

    bare_digit = _pair(
        {
            "line_orientation": "vertical",
            "selected_left_raw_text": None,
            "selected_right_raw_text": "3",
        },
        pair_id="PDIG",
        right_text_id="T-3",
    )
    bare_digit.left_value = None
    bare_digit.right_value = "3"
    bare_digit.status = "review"

    component_like = _pair(
        {
            "line_orientation": "vertical",
            "selected_left_raw_text": "4-21KLP2-1",
            "selected_right_raw_text": "4-21GD3",
        },
        pair_id="PCOMP",
        left_text_id="T-L",
        right_text_id="T-R",
    )
    component_like.left_value = "1"
    component_like.right_value = "3"
    component_like.status = "review"

    sheet = _sheet(
        category="元件接线图",
        route_target="ComponentDiagramExtractor",
        page_subtype="horizontal_component",
    )
    texts = [
        TextItem(
            text_id="T-HMC",
            sheet_id=sheet.sheet_id,
            file_id="F1",
            handle="H1",
            entity_type="TEXT",
            text="HMC-3C wiring diagram",
            normalized_text="HMC-3C wiring diagram",
            is_numeric_candidate=False,
            layer="TEXT",
            rotation_deg=0.0,
            height=2.5,
            insert_x=100.0,
            insert_y=180.0,
            bbox_min_x=90.0,
            bbox_min_y=178.0,
            bbox_max_x=160.0,
            bbox_max_y=182.0,
        ),
        TextItem(
            text_id="T-BCD",
            sheet_id=sheet.sheet_id,
            file_id="F1",
            handle="H2",
            entity_type="TEXT",
            text="BCD 1",
            normalized_text="BCD 1",
            is_numeric_candidate=False,
            layer="TEXT",
            rotation_deg=0.0,
            height=2.0,
            insert_x=140.0,
            insert_y=147.0,
            bbox_min_x=138.0,
            bbox_min_y=145.0,
            bbox_max_x=150.0,
            bbox_max_y=149.0,
        ),
    ]

    _shadow_hmc_silkscreen_ordinary_pairs(
        [hd_stub, bare_digit, component_like],
        [sheet],
        texts,
    )

    assert hd_stub.evidence["ordinary_pair_eligible"] is False
    assert hd_stub.evidence["ordinary_pair_shadow_reason"] == "hmc_panel_silkscreen"
    assert bare_digit.evidence["ordinary_pair_eligible"] is False
    assert bare_digit.evidence["ordinary_pair_shadow_reason"] == "hmc_panel_silkscreen"
    # Real component endpoints on the same sheet must remain audit-eligible.
    assert component_like.evidence.get("ordinary_pair_eligible") is not False
    assert "ordinary_pair_shadow_reason" not in component_like.evidence


def test_shadow_hmc_silkscreen_skips_pages_without_hmc_cues() -> None:
    from dwg_audit.audit.page_extractors import _shadow_hmc_silkscreen_ordinary_pairs

    ordinary = _pair(
        {
            "line_orientation": "vertical",
            "selected_left_raw_text": "HD18",
        },
        left_text_id="T1",
    )
    ordinary.left_value = "18"
    ordinary.status = "review"
    sheet = _sheet(
        category="元件接线图",
        route_target="ComponentDiagramExtractor",
    )
    # No HMC/BCD lattice texts → do not shadow even if a lone HD-looking label appears.
    _shadow_hmc_silkscreen_ordinary_pairs([ordinary], [sheet], texts=[])
    assert ordinary.evidence.get("ordinary_pair_eligible") is not False


def test_shadow_hmc_silkscreen_uses_metadata_title_when_other_texts_exist() -> None:
    from dwg_audit.audit.page_extractors import _shadow_hmc_silkscreen_ordinary_pairs
    from dwg_audit.domain.models import TextItem

    pin_stub = _pair(
        {
            "line_orientation": "vertical",
            "selected_left_raw_text": "HD18",
        },
        left_text_id="T-HD",
    )
    pin_stub.left_value = "18"
    sheet = _sheet(category="元件接线图", route_target="ComponentDiagramExtractor")
    sheet.sheet_title = "HMC panel"
    texts = [
        TextItem(
            text_id="T-OTHER",
            sheet_id=sheet.sheet_id,
            file_id="F1",
            handle="H1",
            entity_type="TEXT",
            text="unrelated note",
            normalized_text="unrelated note",
            is_numeric_candidate=False,
            layer="TEXT",
            rotation_deg=0.0,
            height=2.5,
            insert_x=10.0,
            insert_y=10.0,
            bbox_min_x=9.0,
            bbox_min_y=9.0,
            bbox_max_x=20.0,
            bbox_max_y=12.0,
        )
    ]

    _shadow_hmc_silkscreen_ordinary_pairs([pin_stub], [sheet], texts)

    assert pin_stub.evidence["ordinary_pair_eligible"] is False
    assert pin_stub.evidence["ordinary_pair_shadow_reason"] == "hmc_panel_silkscreen"

def test_long_bare_digit_geometry_does_not_shadow_missing_side_pairs() -> None:
    from dwg_audit.audit.page_extractors import _shadow_component_long_bare_digit_ordinary_pairs

    long_stub = _pair(
        {
            "line_orientation": "horizontal",
            "line_start": [20.0, 50.0],
            "line_end": [105.0, 50.0],
            "selected_right_raw_text": "3",
        },
        pair_id="PLONG",
        line_group_id="G_LONG",
        right_text_id="T3",
    )
    long_stub.left_value = None
    long_stub.right_value = "3"
    long_stub.status = "review"

    short_stub = _pair(
        {
            "line_orientation": "horizontal",
            "line_start": [20.0, 40.0],
            "line_end": [40.0, 40.0],
            "selected_right_raw_text": "2",
        },
        pair_id="PSHORT",
        line_group_id="G_SHORT",
        right_text_id="T2",
    )
    short_stub.left_value = None
    short_stub.right_value = "2"
    short_stub.status = "review"

    designator = _pair(
        {
            "line_orientation": "horizontal",
            "line_start": [20.0, 30.0],
            "line_end": [120.0, 30.0],
            "selected_right_raw_text": "ZD11",
        },
        pair_id="PTERM",
        line_group_id="G_TERM",
        right_text_id="TZ",
    )
    designator.left_value = None
    designator.right_value = "ZD11"
    designator.status = "review"

    sheet = _sheet(
        category="元件接线图",
        route_target="ComponentDiagramExtractor",
        page_subtype="horizontal_component",
    )
    groups = [
        LineGroup("G_LONG", "S1", "F1", 20, 50, 105, 50, 85.0, 0.9, ["L1"], ["CONNECT"]),
        LineGroup("G_SHORT", "S1", "F1", 20, 40, 40, 40, 20.0, 0.9, ["L2"], ["CONNECT"]),
        LineGroup("G_TERM", "S1", "F1", 20, 30, 120, 30, 100.0, 0.9, ["L3"], ["CONNECT"]),
    ]
    _shadow_component_long_bare_digit_ordinary_pairs(
        [long_stub, short_stub, designator],
        groups,
        [sheet],
    )
    assert long_stub.evidence.get("ordinary_pair_eligible") is not False
    assert short_stub.evidence.get("ordinary_pair_eligible") is not False
    assert designator.evidence.get("ordinary_pair_eligible") is not False


def test_external_designator_derived_pairs_remain_audit_eligible() -> None:
    from dwg_audit.audit.page_extractors import _shadow_external_designator_derived_ordinary_pairs

    cd_stub = _pair(
        {
            "line_orientation": "vertical",
            "selected_left_raw_text": "3-21CD43",
            "selected_left_is_derived_numeric": True,
        },
        pair_id="PCD",
        left_text_id="TCD",
    )
    cd_stub.left_value = "43"
    cd_stub.right_value = None
    cd_stub.status = "review"

    real_terminal = _pair(
        {
            "line_orientation": "vertical",
            "selected_left_raw_text": "n113",
            "selected_right_raw_text": "2-21KLP2-2",
        },
        pair_id="PREAL",
        left_text_id="TN",
        right_text_id="TK",
    )
    real_terminal.left_value = "113"
    real_terminal.right_value = "2"
    real_terminal.status = "review"

    sheet = _sheet(
        category="元件接线图",
        route_target="ComponentDiagramExtractor",
        page_subtype="horizontal_component",
    )
    _shadow_external_designator_derived_ordinary_pairs([cd_stub, real_terminal], [sheet])
    assert cd_stub.evidence.get("ordinary_pair_eligible") is not False
    assert real_terminal.evidence.get("ordinary_pair_eligible") is not False

def test_signal_alarm_cues_match_filename_and_generic_alarm_labels() -> None:
    from dwg_audit.audit.page_extractors import _sheet_has_signal_alarm_cues
    from dwg_audit.domain.models import TextItem

    sheet = _sheet(route_target="WireDiagramExtractor")
    sheet.sheet_category = "二次原理图"
    sheet.filename = "05 信号回路图.dwg"
    sheet.sheet_title = "信号回路图"
    assert _sheet_has_signal_alarm_cues(sheet, texts=[]) is True

    sheet2 = _sheet(route_target="WireDiagramExtractor")
    sheet2.sheet_category = "二次原理图"
    sheet2.filename = "04 直流回路图.dwg"
    texts = [
        TextItem(
            text_id="T1",
            sheet_id=sheet2.sheet_id,
            file_id="F1",
            handle="H1",
            entity_type="TEXT",
            text="失电告警",
            normalized_text="失电告警",
            is_numeric_candidate=False,
            layer="TEXT",
            rotation_deg=0.0,
            height=2.5,
            insert_x=10.0,
            insert_y=10.0,
            bbox_min_x=9.0,
            bbox_min_y=9.0,
            bbox_max_x=20.0,
            bbox_max_y=12.0,
        )
    ]
    assert _sheet_has_signal_alarm_cues(sheet2, texts=texts) is True


def test_mark_component_mapping_endpoint_covered_ordinary_pairs() -> None:
    from dwg_audit.audit.page_extractors import (
        _mark_component_mapping_endpoint_covered_ordinary_pairs,
    )

    mapping = _pair(
        {
            "source": "component_mapping",
            "selected_left_raw_text": "2-21KLP2-2",
            "selected_right_raw_text": "2-21n113",
        },
        pair_id="PCM",
        pair_kind="component_mapping",
        left_text_id="TL",
        right_text_id="TR",
    )
    mapping.left_value = "2-21KLP2-2"
    mapping.right_value = "2-21n113"
    mapping.pair_kind = "component_mapping"

    residual = _pair(
        {
            "line_orientation": "vertical",
            "selected_right_raw_text": "2-21n113",
        },
        pair_id="PRES",
        right_text_id="TR",
    )
    residual.left_value = None
    residual.right_value = "113"
    residual.status = "review"

    other = _pair(
        {
            "line_orientation": "vertical",
            "selected_right_raw_text": "n999",
        },
        pair_id="POTHER",
        right_text_id="TX",
    )
    other.left_value = None
    other.right_value = "999"
    other.status = "review"

    _mark_component_mapping_endpoint_covered_ordinary_pairs([residual, other], [mapping])
    assert residual.evidence["ordinary_pair_eligible"] is False
    assert (
        residual.evidence["ordinary_pair_shadow_reason"]
        == "covered_by_component_mapping_endpoint"
    )
    assert other.evidence.get("ordinary_pair_eligible") is not False


def test_component_mapping_endpoint_coverage_is_scoped_to_sheet() -> None:
    from dwg_audit.audit.page_extractors import (
        _mark_component_mapping_endpoint_covered_ordinary_pairs,
    )

    mapping = _pair(
        {"selected_right_raw_text": "n113"},
        pair_id="PCM",
        pair_kind="component_mapping",
        right_text_id="MAP-TR",
    )
    mapping.sheet_id = "S1"
    mapping.right_value = "n113"

    same_sheet = _pair(
        {"selected_right_raw_text": "n113"},
        pair_id="SAME",
        right_text_id="ORD-S1",
    )
    same_sheet.sheet_id = "S1"
    same_sheet.left_value = None
    same_sheet.right_value = "113"

    other_sheet = _pair(
        {"selected_right_raw_text": "n113"},
        pair_id="OTHER",
        right_text_id="ORD-S2",
    )
    other_sheet.sheet_id = "S2"
    other_sheet.left_value = None
    other_sheet.right_value = "113"

    _mark_component_mapping_endpoint_covered_ordinary_pairs(
        [same_sheet, other_sheet],
        [mapping],
    )

    assert same_sheet.evidence["ordinary_pair_eligible"] is False
    assert other_sheet.evidence.get("ordinary_pair_eligible") is not False


def test_component_mapping_endpoint_coverage_does_not_shadow_complete_ordinary_pair() -> None:
    from dwg_audit.audit.page_extractors import (
        mark_component_mapping_endpoint_covered_ordinary_pairs,
    )

    mapping = _pair(
        {"source": "component_mapping", "external_endpoint": "1701"},
        pair_id="PCM",
        pair_kind="component_mapping",
        right_text_id="TR",
    )
    mapping.left_value = "1F1-2"
    mapping.right_value = "1701"
    mapping.status = "pass"

    complete = _pair(
        {"selected_right_raw_text": "1701"},
        pair_id="PORD",
        right_text_id="TR",
    )
    complete.left_value = "OTHER"
    complete.right_value = "1701"

    mark_component_mapping_endpoint_covered_ordinary_pairs([complete], [mapping])

    assert complete.evidence.get("ordinary_pair_eligible") is not False


def test_component_mapping_endpoint_coverage_does_not_alias_device_suffix_to_bare_number() -> None:
    from dwg_audit.audit.page_extractors import (
        mark_component_mapping_endpoint_covered_ordinary_pairs,
    )

    mapping = _pair(
        {"source": "component_mapping", "external_endpoint": "1XD28"},
        pair_id="PCM",
        pair_kind="component_mapping",
        right_text_id="TMAP",
    )
    mapping.left_value = "1F1-2"
    mapping.right_value = "1XD28"
    mapping.status = "pass"
    ordinary = _pair(
        {"selected_left_raw_text": "28"},
        pair_id="PORD",
        left_text_id="TORD",
    )
    ordinary.left_value = "28"
    ordinary.right_value = None

    mark_component_mapping_endpoint_covered_ordinary_pairs([ordinary], [mapping])

    assert ordinary.evidence.get("ordinary_pair_eligible") is not False


def test_component_mapping_endpoint_coverage_keeps_strict_n_terminal_display_alias() -> None:
    from dwg_audit.audit.page_extractors import (
        mark_component_mapping_endpoint_covered_ordinary_pairs,
    )

    mapping = _pair(
        {"source": "component_mapping", "external_endpoint": "1-2n414"},
        pair_id="PCM",
        pair_kind="component_mapping",
        right_text_id="TMAP",
    )
    mapping.left_value = "1F1-2"
    mapping.right_value = "1-2n414"
    mapping.status = "pass"
    ordinary = _pair(
        {"selected_left_raw_text": "n414"},
        pair_id="PORD",
        left_text_id="TORD",
    )
    ordinary.left_value = "n414"
    ordinary.right_value = None

    mark_component_mapping_endpoint_covered_ordinary_pairs([ordinary], [mapping])

    assert ordinary.evidence["ordinary_pair_eligible"] is False

