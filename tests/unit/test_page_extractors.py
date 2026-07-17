from dwg_audit.audit.page_extractors import _mark_input_matrix_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_inline_wire_split_continuation_pairs
from dwg_audit.audit.page_extractors import _mark_schematic_ac_phase_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_schematic_ground_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import _shadow_grid_wire_ordinary_pairs
from dwg_audit.audit.page_extractors import _mark_terminal_prefixed_endpoint_ordinary_pairs
from dwg_audit.audit.page_extractors import _promote_regular_terminal_row_array_pairs
from dwg_audit.audit.rules import build_issues
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.utils.config import DEFAULT_CONFIG


def _pair(
    evidence: dict[str, object],
    *,
    pair_id: str = "P1",
    line_group_id: str = "G1",
    pair_kind: str = "ordinary_pair",
    left_text_id: str | None = None,
    right_text_id: str | None = None,
) -> Pair:
    return Pair(
        pair_id=pair_id,
        line_group_id=line_group_id,
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

