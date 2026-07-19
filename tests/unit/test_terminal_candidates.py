from dwg_audit.audit.candidates import build_terminal_candidates
from dwg_audit.audit.pairs import build_pairs
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.config import DEFAULT_CONFIG


def test_build_terminal_candidates_assigns_ranks_and_component_scores() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "101", "101", True, "TEXT", 0.0, 2.5, 8.0, 20.0, 8.0, 19.0, 12.0, 22.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "102", "102", True, "TEXT", 0.0, 2.5, 6.0, 20.5, 6.0, 19.5, 10.0, 22.5),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "201", "201", True, "TEXT", 0.0, 2.5, 92.0, 20.0, 92.0, 19.0, 96.0, 22.0),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "TITLE", "TITLE", False, "TEXT", 0.0, 2.5, 9.0, 20.0, 9.0, 19.0, 17.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG)

    accepted_left = [item for item in candidates if item.side == "left" and item.status == "accepted"]
    accepted_right = [item for item in candidates if item.side == "right" and item.status == "accepted"]
    rejected = next(item for item in candidates if item.text_id == "T4" and item.status == "rejected")
    top_left = next(item for item in accepted_left if item.rank == 1)

    assert [item.rank for item in sorted(accepted_left, key=lambda item: item.rank or 99)] == [1, 2]
    assert top_left.vertical_alignment_score is not None
    assert top_left.horizontal_side_score is not None
    assert top_left.text_type_score == 1.0
    assert top_left.height_score == 1.0
    assert len(accepted_right) == 1
    assert accepted_right[0].rank == 1
    assert rejected.rank is None
    assert rejected.text_type_score == 0.0


def test_build_terminal_candidates_accepts_numeric_text_inside_line_endpoint_window() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "101", "101", True, "TEXT", 0.0, 2.5, 22.0, 20.0, 22.0, 19.0, 26.0, 22.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "201", "201", True, "TEXT", 0.0, 2.5, 78.0, 20.0, 78.0, 19.0, 82.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG)

    left_candidate = next(item for item in candidates if item.side == "left" and item.text_id == "T1")
    right_candidate = next(item for item in candidates if item.side == "right" and item.text_id == "T2")

    assert left_candidate.status == "accepted"
    assert right_candidate.status == "accepted"
    assert left_candidate.rejection_reason is None
    assert right_candidate.rejection_reason is None
    assert left_candidate.score > 0.0
    assert right_candidate.score > 0.0


def test_build_terminal_candidates_composes_named_component_port_at_wire_endpoint() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=32.5,
            end_y=20.0,
            length=22.5,
            wire_candidate_score=0.7,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1309", "1309", True, "DIM", 0.0, 2.5, 7.5, 20.7, 7.5, 19.8, 13.7, 22.7),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "9", "9", True, "DIM", 0.0, 2.5, 31.9, 21.0, 31.9, 20.1, 33.7, 23.0),
        TextItem("T3", "S1", "F1", "H3", "MTEXT", "DEVX", "DEVX", False, "DIM", 0.0, 3.0, 37.5, 21.6, 37.5, 20.6, 44.9, 24.0, color_index=1),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "10", "10", True, "DIM", 0.0, 2.5, 41.2, 21.0, 41.2, 20.1, 44.3, 23.0),
    ]
    sheets = [
        SheetRecord("S1", "F1", "09 通讯、对时及打印回路.dwg", 9, "09", "COMMUNICATION", "二次原理图", "primary", "filename", True)
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    port = next(item for item in candidates if item.text_id == "T2" and item.side == "right")
    assert port.status == "accepted"
    assert port.value == "DEVX9"
    assert port.channel == "wire_logic_endpoint_channel"
    assert port.channel_detail == "schematic_named_component_port"
    assert pairs[0].left_value == "1309"
    assert pairs[0].right_value == "DEVX9"
    assert pairs[0].pair_kind == "wire_component_mapping"
    assert pairs[0].evidence["logical_endpoint"] == "DEVX9"


def test_build_terminal_candidates_uses_component_side_for_two_digit_port() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 47.5, 20.0, 37.5, 0.7, ["L1", "L2"], ["CONNECT"])
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1307", "1307", True, "DIM", 0.0, 2.5, 7.5, 20.7, 7.5, 19.8, 13.7, 22.7),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "11", "11", True, "DIM", 0.0, 2.5, 31.2, 21.0, 31.2, 20.1, 34.3, 23.0),
        TextItem("T3", "S1", "F1", "H3", "MTEXT", "PORTDEV", "PORTDEV", False, "DIM", 0.0, 3.0, 37.5, 21.6, 37.5, 20.6, 49.0, 24.0),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "12", "12", True, "DIM", 0.0, 2.5, 41.2, 21.0, 41.2, 20.1, 44.3, 23.0),
    ]
    sheets = [
        SheetRecord("S1", "F1", "generic.dwg", 1, "01", "COMMUNICATION", "二次原理图", "primary", "filename", True)
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    port = next(item for item in candidates if item.text_id == "T2" and item.side == "right")
    opposite_port = next(item for item in candidates if item.text_id == "T4" and item.side == "right")
    assert port.value == "PORTDEV11"
    assert port.score >= 0.95
    assert opposite_port.value == "12"
    assert pairs[0].left_value == "1307"
    assert pairs[0].right_value == "PORTDEV11"
    assert pairs[0].pair_kind == "wire_component_mapping"


def test_build_terminal_candidates_keeps_unowned_dim_single_char_filtered() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 32.5, 20.0, 22.5, 0.7, ["L1"], ["CONNECT"])
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1309", "1309", True, "DIM", 0.0, 2.5, 7.5, 20.7, 7.5, 19.8, 13.7, 22.7),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "9", "9", True, "DIM", 0.0, 2.5, 31.9, 21.0, 31.9, 20.1, 33.7, 23.0),
    ]
    sheets = [
        SheetRecord("S1", "F1", "09 通讯、对时及打印回路.dwg", 9, "09", "COMMUNICATION", "二次原理图", "primary", "filename", True)
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    port = next(item for item in candidates if item.text_id == "T2" and item.side == "right")
    assert port.status == "rejected"
    assert port.rejection_reason == "single_char_layer_filtered"


def test_build_terminal_candidates_marks_binary_input_function_label_as_semantic_endpoint() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=105.0,
            start_y=195.0,
            end_x=145.0,
            end_y=195.0,
            length=40.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="grid",
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "116", "116", True, "DIM", 0.0, 2.5, 90.6, 195.7, 90.6, 194.8, 95.3, 197.7),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "BI 5/BCD1", "BI 5/BCD1", False, "DIM", 0.0, 2.5, 108.2, 196.1, 108.2, 195.2, 122.2, 198.1),
    ]
    sheets = [
        SheetRecord("S1", "F1", "12 测控2开入回路图1.dwg", 12, "12", "3-21n BINARY INPUT 1", "二次原理图", "primary", "filename", True)
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    numeric = next(item for item in candidates if item.text_id == "T1" and item.side == "left")
    semantic = next(item for item in candidates if item.text_id == "T2" and item.side == "left")
    assert numeric.status == "accepted"
    assert numeric.rank == 1
    assert semantic.status == "accepted"
    assert semantic.rank == 2
    assert semantic.value == "BI 5/BCD1"
    assert semantic.channel == "schematic_semantic_endpoint_channel"
    assert semantic.channel_detail == "schematic_binary_input_function_label"
    assert semantic.score < numeric.score


def test_build_terminal_candidates_marks_binary_input_description_as_semantic_endpoint() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=105.0,
            start_y=205.0,
            end_x=145.0,
            end_y=205.0,
            length=40.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="grid",
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "115", "115", True, "DIM", 0.0, 2.5, 90.6, 206.1, 90.6, 205.2, 95.3, 208.1),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "Manual closing of synchronization", "Manual closing of synchronization", False, "DIM", 0.0, 2.5, 108.2, 207.1, 108.2, 206.2, 157.2, 209.1),
    ]
    sheets = [
        SheetRecord("S1", "F1", "08 测控1开入回路图1.dwg", 8, "08", "1-21n BINARY INPUT 1", "二次原理图", "primary", "filename", True)
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    numeric = next(item for item in candidates if item.text_id == "T1" and item.side == "left")
    semantic = next(item for item in candidates if item.text_id == "T2" and item.side == "left")
    assert numeric.status == "accepted"
    assert numeric.rank == 1
    assert semantic.status == "accepted"
    assert semantic.rank == 2
    assert semantic.value == "Manual closing of synchronization"
    assert semantic.channel == "schematic_semantic_endpoint_channel"
    assert semantic.channel_detail == "schematic_binary_input_function_description"
    assert semantic.score < numeric.score


def test_build_terminal_candidates_keeps_control_output_description_out_of_binary_input_semantics() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=92.5,
            start_y=235.0,
            end_x=173.8,
            end_y=235.0,
            length=81.3,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="grid",
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "Manual closing of synchronization", "Manual closing of synchronization", False, "DIM", 0.0, 2.5, 160.0, 236.2, 160.0, 235.3, 210.0, 238.2)
    ]
    sheets = [
        SheetRecord("S1", "F1", "10 测控1控制回路图1.dwg", 10, "10", "1-21n CONTROL OUTPUT", "二次原理图", "primary", "filename", True)
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    rejected = next(item for item in candidates if item.text_id == "T1")
    assert rejected.status == "rejected"
    assert rejected.channel == "noise_channel"
    assert rejected.channel_detail == "not_numeric"


def test_build_terminal_candidates_accepts_schematic_logic_endpoint_mapping() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=102.5,
            start_y=81.96,
            end_x=152.5,
            end_y=81.96,
            length=50.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord(
            "S1",
            "F1",
            "11 测控1控制回路图2.dwg",
            11,
            "11",
            "1-21n CONTROL OUTPUT",
            "二次原理图",
            "primary",
            "filename",
            True,
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1-21CD58", "1-21CD58", False, "TEXT", 0.0, 2.5, 100.0, 83.0, 100.0, 81.5, 111.0, 84.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "511", "511", True, "TEXT", 0.0, 2.5, 155.0, 83.0, 155.0, 81.5, 160.0, 84.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    logic_candidate = next(item for item in candidates if item.text_id == "T1")
    numeric_candidate = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]
    assert logic_candidate.status == "accepted"
    assert logic_candidate.value == "1-21CD58"
    assert logic_candidate.channel == "wire_logic_endpoint_channel"
    assert logic_candidate.channel_detail == "schematic_wire_logic_endpoint"
    assert numeric_candidate.channel == "terminal_numeric_channel"
    assert pair.left_value == "1-21CD58"
    assert pair.right_value == "511"
    assert pair.pair_kind == "wire_component_mapping"
    assert pair.evidence["component_submode"] == "schematic_wire_logic_endpoint"
    assert pair.evidence["ordinary_pair_eligible"] is False


def test_build_terminal_candidates_maps_compact_xd_endpoints_in_both_directions() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 50.0, 20.0, 40.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G2", "S1", "F1", 10.0, 80.0, 50.0, 80.0, 40.0, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 中央信号输出回路图.dwg", 20, "20", "中央信号输出", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1XD3", "1XD3", False, "DIM", 0.0, 2.5, 9.0, 21.5, 7.0, 19.5, 13.0, 23.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "723", "723", True, "DIM", 0.0, 2.5, 51.0, 21.5, 49.0, 19.5, 55.0, 23.5),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "531", "531", True, "DIM", 0.0, 2.5, 9.0, 81.5, 7.0, 79.5, 13.0, 83.5),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "1XD49", "1XD49", False, "DIM", 0.0, 2.5, 51.0, 81.5, 49.0, 79.5, 58.0, 83.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    logic_candidates = {item.text_id: item for item in candidates if item.text_id in {"T1", "T4"}}
    assert logic_candidates["T1"].status == "accepted"
    assert logic_candidates["T1"].channel == "wire_logic_endpoint_channel"
    assert logic_candidates["T4"].status == "accepted"
    assert logic_candidates["T4"].channel == "wire_logic_endpoint_channel"
    by_group = {pair.line_group_id: pair for pair in pairs}
    assert (by_group["G1"].left_value, by_group["G1"].right_value) == ("1XD3", "723")
    assert (by_group["G2"].left_value, by_group["G2"].right_value) == ("531", "1XD49")
    assert by_group["G1"].pair_kind == "wire_component_mapping"
    assert by_group["G2"].pair_kind == "wire_component_mapping"
    assert by_group["G1"].evidence["ordinary_pair_eligible"] is False
    assert by_group["G2"].evidence["ordinary_pair_eligible"] is False


def test_build_terminal_candidates_maps_compact_yd_and_ld_signal_endpoints() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 115.0, 50.0, 145.0, 50.0, 30.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G2", "S1", "F1", 315.0, 65.0, 345.0, 65.0, 30.0, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G3", "S1", "F1", 115.0, 80.0, 145.0, 80.0, 30.0, 0.85, ["L3"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G4", "S1", "F1", 315.0, 95.0, 345.0, 95.0, 30.0, 0.85, ["L4"], ["CONNECT"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 信号输出回路图.dwg", 21, "21", "SIGNAL OUTPUT", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "718", "718", True, "DIM", 0.0, 2.5, 110.7, 51.3, 109.0, 49.5, 116.0, 53.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "1YD28", "1YD28", False, "DIM", 0.0, 2.5, 144.8, 52.0, 143.0, 50.0, 155.0, 54.0),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "519", "519", True, "DIM", 0.0, 2.5, 310.7, 66.3, 309.0, 64.5, 316.0, 68.5),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "1YD48", "1YD48", False, "DIM", 0.0, 2.5, 344.8, 67.0, 343.0, 65.0, 355.0, 69.0),
        TextItem("T5", "S1", "F1", "H5", "TEXT", "704", "704", True, "DIM", 0.0, 2.5, 110.7, 81.3, 109.0, 79.5, 116.0, 83.5),
        TextItem("T6", "S1", "F1", "H6", "TEXT", "1LD27", "1LD27", False, "DIM", 0.0, 2.5, 144.5, 82.0, 143.0, 80.0, 155.0, 84.0),
        TextItem("T7", "S1", "F1", "H7", "TEXT", "505", "505", True, "DIM", 0.0, 2.5, 310.7, 96.3, 309.0, 94.5, 316.0, 98.5),
        TextItem("T8", "S1", "F1", "H8", "TEXT", "1LD46", "1LD46", False, "DIM", 0.0, 2.5, 344.0, 97.0, 342.0, 95.0, 354.0, 99.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    by_group = {pair.line_group_id: pair for pair in pairs}
    assert (by_group["G1"].left_value, by_group["G1"].right_value) == ("718", "1YD28")
    assert (by_group["G2"].left_value, by_group["G2"].right_value) == ("519", "1YD48")
    assert (by_group["G3"].left_value, by_group["G3"].right_value) == ("704", "1LD27")
    assert (by_group["G4"].left_value, by_group["G4"].right_value) == ("505", "1LD46")
    assert all(pair.pair_kind == "wire_component_mapping" for pair in by_group.values())
    assert all(pair.evidence["ordinary_pair_eligible"] is False for pair in by_group.values())


def test_build_terminal_candidates_rejects_compact_xd_endpoint_from_adjacent_row() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 50.0, 20.0, 40.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G2", "S1", "F1", 10.0, 30.0, 50.0, 30.0, 40.0, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 中央信号输出回路图.dwg", 20, "20", "中央信号输出", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "924", "924", True, "DIM", 0.0, 2.5, 9.0, 22.0, 7.0, 20.0, 13.0, 24.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "925", "925", True, "DIM", 0.0, 2.5, 9.0, 32.0, 7.0, 30.0, 13.0, 34.0),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "1XD8", "1XD8", False, "DIM", 0.0, 2.5, 50.2, 22.0, 48.0, 20.0, 57.0, 24.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    same_row = next(item for item in candidates if item.line_group_id == "G1" and item.text_id == "T3")
    adjacent_row = next(item for item in candidates if item.line_group_id == "G2" and item.text_id == "T3")
    assert same_row.status == "accepted"
    assert same_row.channel == "wire_logic_endpoint_channel"
    assert adjacent_row.status == "rejected"
    assert adjacent_row.rejection_reason == "schematic_logic_endpoint_out_of_row"
    assert adjacent_row.channel == "noise_channel"
    by_group = {pair.line_group_id: pair for pair in pairs}
    assert (by_group["G1"].left_value, by_group["G1"].right_value) == ("924", "1XD8")
    assert by_group["G2"].right_value is None


def test_build_terminal_candidates_rejects_yd_endpoint_from_adjacent_row() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 50.0, 20.0, 40.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G2", "S1", "F1", 10.0, 30.0, 50.0, 30.0, 40.0, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 远动信号输出回路图.dwg", 21, "21", "REMOTE SIGNAL OUTPUT", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "718", "718", True, "DIM", 0.0, 2.5, 9.0, 22.0, 7.0, 20.0, 13.0, 24.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "719", "719", True, "DIM", 0.0, 2.5, 9.0, 32.0, 7.0, 30.0, 13.0, 34.0),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "1YD28", "1YD28", False, "DIM", 0.0, 2.5, 50.2, 22.0, 48.0, 20.0, 60.0, 24.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    same_row = next(item for item in candidates if item.line_group_id == "G1" and item.text_id == "T3")
    adjacent_row = next(item for item in candidates if item.line_group_id == "G2" and item.text_id == "T3")
    assert same_row.status == "accepted"
    assert adjacent_row.status == "rejected"
    assert adjacent_row.rejection_reason == "schematic_logic_endpoint_out_of_row"
    by_group = {pair.line_group_id: pair for pair in pairs}
    assert (by_group["G1"].left_value, by_group["G1"].right_value) == ("718", "1YD28")
    assert by_group["G2"].right_value is None


def test_build_terminal_candidates_does_not_promote_vd_component_endpoint() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 30.0, 80.0, 80.0, 80.0, 50.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal")
    ]
    sheets = [
        SheetRecord("S1", "F1", "14 交流电压回路2.dwg", 14, "14", "VT INPUT 2", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1VD1", "1VD1", False, "DIM", 0.0, 2.5, 29.0, 82.0, 27.0, 80.0, 38.0, 84.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "1701", "1701", True, "DIM", 0.0, 2.5, 80.0, 81.0, 78.0, 79.0, 88.0, 83.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    vd = next(item for item in candidates if item.text_id == "T1")
    assert vd.status == "rejected"
    assert vd.channel != "wire_logic_endpoint_channel"
    assert pairs[0].left_value is None
    assert pairs[0].right_value == "1701"


def test_build_terminal_candidates_does_not_attach_ld_label_inside_merged_long_group() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 114.7, 80.0, 392.5, 80.0, 277.8, 0.85, ["L1"], ["CONNECT"], orientation="horizontal")
    ]
    sheets = [
        SheetRecord("S1", "F1", "22 录波信号输出回路图.dwg", 22, "22", "RECORDER SIGNAL OUTPUT", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "704", "704", True, "DIM", 0.0, 2.5, 110.7, 81.3, 109.0, 79.5, 116.0, 83.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "1LD27", "1LD27", False, "DIM", 0.0, 2.5, 144.5, 82.0, 143.0, 80.0, 155.0, 84.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    assert all(item.text_id != "T2" or item.status == "rejected" for item in candidates)
    assert pairs[0].left_value == "704"
    assert pairs[0].right_value is None


def test_build_terminal_candidates_maps_q_device_endpoints_on_short_horizontal_leads() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 295.0, 215.0, 342.5, 215.0, 47.5, 0.625, ["L1", "L2"], ["CONNECT", "0"], orientation="horizontal"),
        LineGroup("G2", "S1", "F1", 295.0, 240.0, 342.5, 240.0, 47.5, 0.625, ["L3", "L4"], ["CONNECT", "0"], orientation="horizontal"),
        LineGroup("G3", "S1", "F1", 325.0, 210.0, 365.0, 210.0, 40.0, 0.55, ["L5"], ["0"], orientation="horizontal"),
        LineGroup("G4", "S1", "F1", 325.0, 221.5, 365.0, 221.5, 40.0, 0.55, ["L6"], ["0"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "05 交直流回路图.dwg", 5, "05", "AC&DC POWER SUPPLY", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "4Q2D20", "4Q2D20", False, "TEXT", 0.0, 2.5, 292.5, 217.4, 290.0, 215.0, 304.0, 219.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "829", "829", True, "TEXT", 0.0, 2.5, 325.6, 215.7, 324.0, 214.0, 332.0, 218.0),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "4Q1D35~36", "4Q1D35~36", False, "TEXT", 0.0, 2.5, 292.5, 242.4, 290.0, 240.0, 310.0, 244.0),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "831", "831", True, "TEXT", 0.0, 2.5, 325.6, 240.7, 324.0, 239.0, 332.0, 243.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    logic = {item.text_id: item for item in candidates if item.text_id in {"T1", "T3"} and item.status == "accepted"}
    assert logic["T1"].channel == "wire_logic_endpoint_channel"
    assert logic["T3"].channel == "wire_logic_endpoint_channel"
    by_group = {pair.line_group_id: pair for pair in pairs}
    assert (by_group["G1"].left_value, by_group["G1"].right_value) == ("4Q2D20", "829")
    assert (by_group["G2"].left_value, by_group["G2"].right_value) == ("4Q1D35~36", "831")
    assert by_group["G1"].pair_kind == "wire_component_mapping"
    assert by_group["G2"].pair_kind == "wire_component_mapping"
    assert by_group["G1"].evidence["ordinary_pair_eligible"] is False
    assert by_group["G2"].evidence["ordinary_pair_eligible"] is False
    duplicate_outline = next(
        item
        for item in candidates
        if item.line_group_id == "G3" and item.text_id == "T2" and item.side == "left"
    )
    farther_line = next(
        item
        for item in candidates
        if item.line_group_id == "G4" and item.text_id == "T2" and item.side == "left"
    )
    assert duplicate_outline.rejection_reason == "shared_numeric_anchor_owned_by_q_device_mapping"
    assert duplicate_outline.channel == "noise_channel"
    assert farther_line.status == "accepted"
    assert farther_line.value == "829"


def test_build_terminal_candidates_keeps_shared_numeric_anchor_when_q_owner_is_ambiguous() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 50.0, 20.0, 40.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G2", "S1", "F1", 10.0, 24.0, 50.0, 24.0, 40.0, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G3", "S1", "F1", 30.0, 22.0, 70.0, 22.0, 40.0, 0.55, ["L3"], ["0"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "05 交直流回路图.dwg", 5, "05", "AC&DC POWER SUPPLY", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "4Q1D1", "4Q1D1", False, "TEXT", 0.0, 2.5, 9.0, 21.0, 7.0, 19.0, 20.0, 23.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "4Q2D1", "4Q2D1", False, "TEXT", 0.0, 2.5, 9.0, 25.0, 7.0, 23.0, 20.0, 27.0),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "801", "801", True, "TEXT", 0.0, 2.5, 49.0, 22.0, 47.0, 20.0, 55.0, 24.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    shared_numeric = [item for item in candidates if item.text_id == "T3" and item.status == "accepted"]
    assert {item.line_group_id for item in shared_numeric} == {"G1", "G2", "G3"}
    assert all(item.value == "801" for item in shared_numeric)


def test_build_terminal_candidates_rejects_q_device_endpoint_outside_strict_geometry() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 42.5, 20.0, 32.5, 0.85, ["L1"], ["CONNECT"], orientation="grid"),
        LineGroup("G2", "S1", "F1", 10.0, 40.0, 90.0, 40.0, 80.0, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G3", "S1", "F1", 10.0, 60.0, 50.0, 60.0, 40.0, 0.85, ["L3"], ["CONNECT"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "06 交直流回路图.dwg", 6, "06", "AC&DC POWER SUPPLY", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "4Q2D31", "4Q2D31", False, "TEXT", 0.0, 2.5, 7.5, 22.4, 5.0, 20.0, 19.0, 24.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "929", "929", True, "TEXT", 0.0, 2.5, 40.0, 20.7, 38.0, 19.0, 46.0, 23.0),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "4Q1D38", "4Q1D38", False, "TEXT", 0.0, 2.5, 7.5, 42.4, 5.0, 40.0, 19.0, 44.0),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "1731", "1731", True, "TEXT", 0.0, 2.5, 87.0, 40.7, 85.0, 39.0, 95.0, 43.0),
        TextItem("T5", "S1", "F1", "H5", "TEXT", "4Q1D1", "4Q1D1", False, "TEXT", 0.0, 2.5, 7.5, 67.0, 5.0, 65.0, 19.0, 69.0),
        TextItem("T6", "S1", "F1", "H6", "TEXT", "801", "801", True, "TEXT", 0.0, 2.5, 47.0, 60.7, 45.0, 59.0, 55.0, 63.0),
        TextItem("T7", "S1", "F1", "H7", "TEXT", "1QD47~53", "1QD47~53", False, "TEXT", 0.0, 2.5, 7.5, 62.4, 5.0, 60.0, 21.0, 64.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    grid_qd = next(item for item in candidates if item.line_group_id == "G1" and item.text_id == "T1" and item.side == "left")
    long_qd = next(item for item in candidates if item.line_group_id == "G2" and item.text_id == "T3" and item.side == "left")
    adjacent_qd = next(item for item in candidates if item.line_group_id == "G3" and item.text_id == "T5" and item.side == "left")
    different_grammar = next(item for item in candidates if item.line_group_id == "G3" and item.text_id == "T7" and item.side == "left")
    assert grid_qd.rejection_reason == "schematic_q_device_endpoint_out_of_scope"
    assert long_qd.rejection_reason == "schematic_q_device_endpoint_out_of_scope"
    assert adjacent_qd.rejection_reason == "schematic_logic_endpoint_out_of_row"
    assert different_grammar.rejection_reason == "not_numeric"
    assert all(
        item.channel == "noise_channel"
        for item in (grid_qd, long_qd, adjacent_qd, different_grammar)
    )


def test_build_terminal_candidates_scopes_q_device_to_secondary_schematic_and_numeric_peer() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 42.5, 20.0, 32.5, 0.85, ["L1"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G2", "S2", "F2", 10.0, 40.0, 42.5, 40.0, 32.5, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "16 元件接线图.dwg", 16, "16", "ACCESSORIES WIRING", "元件接线图", "primary", "filename", True),
        SheetRecord("S2", "F2", "05 交流回路图.dwg", 5, "05", "AC CIRCUIT", "二次原理图", "primary", "filename", True),
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "4Q2D20", "4Q2D20", False, "TEXT", 0.0, 2.5, 7.5, 22.4, 5.0, 20.0, 19.0, 24.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "829", "829", True, "TEXT", 0.0, 2.5, 40.0, 20.7, 38.0, 19.0, 46.0, 23.0),
        TextItem("T3", "S2", "F2", "H3", "TEXT", "4Q2D20", "4Q2D20", False, "TEXT", 0.0, 2.5, 7.5, 42.4, 5.0, 40.0, 19.0, 44.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    component_q = next(item for item in candidates if item.line_group_id == "G1" and item.text_id == "T1" and item.side == "left")
    schematic_q = next(item for item in candidates if item.line_group_id == "G2" and item.text_id == "T3" and item.side == "left")
    assert component_q.status == "rejected"
    assert component_q.rejection_reason == "not_numeric"
    assert schematic_q.status == "accepted"
    assert schematic_q.channel == "wire_logic_endpoint_channel"
    schematic_pair = next(pair for pair in pairs if pair.line_group_id == "G2")
    assert schematic_pair.left_value is None
    assert schematic_pair.right_value is None
    assert schematic_pair.pair_kind == "ordinary_pair"


def test_build_terminal_candidates_keeps_malformed_or_out_of_scope_xd_text_out_of_logic_channel() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 50.0, 20.0, 40.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal"),
        LineGroup("G2", "S2", "F2", 10.0, 80.0, 50.0, 80.0, 40.0, 0.85, ["L2"], ["CONNECT"], orientation="horizontal"),
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 信号输出回路图.dwg", 20, "20", "信号输出", "二次原理图", "primary", "filename", True),
        SheetRecord("S2", "F2", "23 主保护箱背面接线图.dwg", 23, "23", "主保护箱背面接线图", "背板接线图", "supplemental", "filename", True),
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "XD1", "XD1", False, "DIM", 0.0, 2.5, 9.0, 21.0, 7.0, 19.0, 13.0, 23.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "1XD", "1XD", False, "DIM", 0.0, 2.5, 9.0, 21.0, 7.0, 19.0, 13.0, 23.0),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "A1XD2", "A1XD2", False, "DIM", 0.0, 2.5, 9.0, 21.0, 7.0, 19.0, 15.0, 23.0),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "1XD2说明", "1XD2说明", False, "DIM", 0.0, 2.5, 9.0, 21.0, 7.0, 19.0, 18.0, 23.0),
        TextItem("T5", "S2", "F2", "H5", "TEXT", "1XD2", "1XD2", False, "TEXT", 0.0, 2.5, 9.0, 81.0, 7.0, 79.0, 13.0, 83.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    scoped = [item for item in candidates if item.text_id in {"T1", "T2", "T3", "T4", "T5"}]
    assert scoped
    assert all(item.channel != "wire_logic_endpoint_channel" for item in scoped)
    assert all(item.status == "rejected" for item in scoped)


def test_build_pairs_does_not_emit_single_sided_compact_xd_endpoint_review() -> None:
    line_groups = [
        LineGroup("G1", "S1", "F1", 10.0, 20.0, 50.0, 20.0, 40.0, 0.85, ["L1"], ["CONNECT"], orientation="horizontal")
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 中央信号输出回路图.dwg", 20, "20", "中央信号输出", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1XD28", "1XD28", False, "DIM", 0.0, 2.5, 50.2, 22.0, 48.0, 20.0, 58.0, 24.0)
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    logic = next(item for item in candidates if item.text_id == "T1")
    assert logic.status == "accepted"
    assert logic.channel == "wire_logic_endpoint_channel"
    assert pairs[0].status == "discard"
    assert pairs[0].left_value is None
    assert pairs[0].right_value is None


def test_build_terminal_candidates_keeps_schematic_semantic_marker_out_of_logic_endpoint_channel() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=102.5,
            start_y=81.96,
            end_x=152.5,
            end_y=81.96,
            length=50.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "11 测控1控制回路图2.dwg", 11, "11", "CONTROL", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "I0", "I0", False, "TEXT", 0.0, 2.5, 100.0, 83.0, 100.0, 81.5, 104.0, 84.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "511", "511", True, "TEXT", 0.0, 2.5, 155.0, 83.0, 155.0, 81.5, 160.0, 84.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic_marker = next(item for item in candidates if item.text_id == "T1")
    assert semantic_marker.status == "rejected"
    assert semantic_marker.rejection_reason == "not_numeric"
    assert semantic_marker.channel == "noise_channel"
    assert pairs[0].left_value is None
    assert pairs[0].right_value == "511"


def test_build_pairs_does_not_emit_single_sided_schematic_logic_endpoint_review() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=102.5,
            start_y=81.96,
            end_x=152.5,
            end_y=81.96,
            length=50.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "11 测控1控制回路图2.dwg", 11, "11", "CONTROL", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1-21CD58", "1-21CD58", False, "TEXT", 0.0, 2.5, 100.0, 83.0, 100.0, 81.5, 111.0, 84.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    logic_candidate = next(item for item in candidates if item.text_id == "T1")
    assert logic_candidate.status == "accepted"
    assert logic_candidate.channel == "wire_logic_endpoint_channel"
    assert pairs[0].status == "discard"
    assert pairs[0].left_value is None
    assert pairs[0].right_value is None


def test_build_terminal_candidates_accepts_schematic_dc_function_label_mapping() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=134.99,
            start_y=65.0,
            end_x=170.0,
            end_y=65.0,
            length=35.01,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "06 直流回路图.dwg", 6, "06", "直流回路图", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem(
            "T1",
            "S1",
            "F1",
            "H1",
            "TEXT",
            "DC 0-5V/4-20mA +",
            "DC 0-5V/4-20mA +",
            False,
            "TEXT",
            0.0,
            2.5,
            132.5,
            66.0,
            128.0,
            64.5,
            151.0,
            67.5,
        ),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "611", "611", True, "TEXT", 0.0, 2.5, 172.5, 66.0, 171.0, 64.5, 177.0, 67.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic_candidate = next(item for item in candidates if item.text_id == "T1")
    numeric_candidate = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]

    assert semantic_candidate.status == "accepted"
    assert semantic_candidate.value == "DC 0-5V/4-20mA +"
    assert semantic_candidate.channel == "schematic_semantic_endpoint_channel"
    assert semantic_candidate.channel_detail == "schematic_dc_function_label"
    assert numeric_candidate.channel == "terminal_numeric_channel"
    assert pair.left_value == "DC 0-5V/4-20mA +"
    assert pair.right_value == "611"
    assert pair.status == "review"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["semantic_kind"] == "schematic_semantic_endpoint"
    assert pair.evidence["semantic_mapping_kind"] == "schematic_dc_function_label"
    assert pair.evidence["ordinary_pair_eligible"] is False


def test_build_terminal_candidates_keeps_low_alignment_dc_function_label_mapping() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=134.99,
            start_y=65.0,
            end_x=170.0,
            end_y=65.0,
            length=35.01,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "06 直流回路图.dwg", 6, "06", "直流回路图", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem(
            "T1",
            "S1",
            "F1",
            "H1",
            "TEXT",
            "DC 0-5V/4-20mA +",
            "DC 0-5V/4-20mA +",
            False,
            "TEXT",
            0.0,
            2.5,
            132.5,
            72.0,
            128.0,
            70.5,
            151.0,
            73.5,
        ),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "611", "611", True, "TEXT", 0.0, 2.5, 172.5, 66.0, 171.0, 64.5, 177.0, 67.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic_candidate = next(item for item in candidates if item.text_id == "T1")
    pair = pairs[0]

    assert semantic_candidate.status == "accepted"
    assert semantic_candidate.vertical_alignment_score == 0.0
    assert semantic_candidate.channel == "schematic_semantic_endpoint_channel"
    assert semantic_candidate.channel_detail == "schematic_dc_function_label"
    assert pair.left_value == "DC 0-5V/4-20mA +"
    assert pair.right_value == "611"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["semantic_mapping_kind"] == "schematic_dc_function_label"


def test_build_terminal_candidates_accepts_schematic_dc_gnd_mapping() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=100.0,
            start_y=45.0,
            end_x=150.0,
            end_y=45.0,
            length=50.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "06 直流回路图.dwg", 6, "06", "直流回路图", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "101", "101", True, "TEXT", 0.0, 2.5, 97.5, 46.0, 96.0, 44.5, 102.0, 47.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "GND", "GND", False, "TEXT", 0.0, 2.5, 152.5, 46.0, 151.0, 44.5, 157.0, 47.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic_candidate = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]

    assert semantic_candidate.status == "accepted"
    assert semantic_candidate.value == "GND"
    assert semantic_candidate.channel == "schematic_semantic_endpoint_channel"
    assert pair.left_value == "101"
    assert pair.right_value == "GND"
    assert pair.status == "review"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["numeric_endpoint"] == "101"
    assert pair.evidence["semantic_endpoint"] == "GND"


def test_build_pairs_does_not_emit_single_sided_schematic_semantic_endpoint_review() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=134.99,
            start_y=65.0,
            end_x=170.0,
            end_y=65.0,
            length=35.01,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "06 直流回路图.dwg", 6, "06", "直流回路图", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem(
            "T1",
            "S1",
            "F1",
            "H1",
            "TEXT",
            "DC 0-5V/4-20mA -",
            "DC 0-5V/4-20mA -",
            False,
            "TEXT",
            0.0,
            2.5,
            132.5,
            66.0,
            128.0,
            64.5,
            151.0,
            67.5,
        )
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic_candidate = next(item for item in candidates if item.text_id == "T1")
    assert semantic_candidate.status == "accepted"
    assert semantic_candidate.channel == "schematic_semantic_endpoint_channel"
    assert pairs[0].status == "discard"
    assert pairs[0].left_value is None
    assert pairs[0].right_value is None


def test_build_terminal_candidates_accepts_schematic_network_time_label_mapping() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=282.5,
            start_y=220.0,
            end_x=362.5,
            end_y=220.0,
            length=80.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord(
            "S1",
            "F1",
            "07 网络对时回路图.dwg",
            7,
            "07",
            "COMMUNICATION AND TIME SYNCHRONIZATION",
            "二次原理图",
            "primary",
            "filename",
            True,
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "TD4", "TD4", False, "TEXT", 0.0, 2.5, 281.0, 222.0, 280.0, 220.5, 286.0, 223.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "602", "602", True, "TEXT", 0.0, 2.5, 364.0, 220.7, 363.0, 219.5, 369.0, 222.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic_candidate = next(item for item in candidates if item.text_id == "T1")
    pair = pairs[0]

    assert semantic_candidate.status == "accepted"
    assert semantic_candidate.value == "TD4"
    assert semantic_candidate.channel == "schematic_semantic_endpoint_channel"
    assert semantic_candidate.channel_detail == "schematic_network_time_label"
    assert pair.left_value == "TD4"
    assert pair.right_value == "602"
    assert pair.status == "review"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["semantic_mapping_kind"] == "schematic_network_time_label"
    assert pair.evidence["ordinary_pair_eligible"] is False


def test_build_pairs_marks_single_sided_ac_phase_label_as_semantic_annotation() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=180.0,
            start_y=140.0,
            end_x=215.0,
            end_y=140.0,
            length=35.0,
            wire_candidate_score=0.55,
            member_line_ids=["L1"],
            layer_hints=["0"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "04 交流回路图1.dwg", 4, "04", "CT AND VT INPUT 1", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "721", "721", True, "DIM", 0.0, 2.5, 178.0, 140.7, 176.0, 139.5, 181.0, 142.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "3U0", "3U0", False, "DIM", 0.0, 2.5, 184.0, 141.0, 183.0, 139.5, 188.0, 142.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    phase_candidate = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]

    assert phase_candidate.status == "accepted"
    assert phase_candidate.value == "3U0"
    assert phase_candidate.channel == "schematic_semantic_endpoint_channel"
    assert phase_candidate.channel_detail == "schematic_ac_phase_label"
    assert pair.left_value == "721"
    assert pair.right_value is None
    assert pair.status == "review"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["semantic_kind"] == "schematic_semantic_annotation"
    assert pair.evidence["semantic_mapping_kind"] == "schematic_ac_phase_label"
    assert pair.evidence["semantic_endpoint"] == "3U0"
    assert pair.evidence["numeric_endpoint"] == "721"
    assert pair.evidence["ordinary_pair_eligible"] is False


def test_build_pairs_marks_line_span_ux_prime_as_ac_phase_semantic_annotation() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=165.0,
            start_y=130.0,
            end_x=215.0,
            end_y=130.0,
            length=50.0,
            wire_candidate_score=0.55,
            member_line_ids=["L1"],
            layer_hints=["0"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "05 交流回路图2.dwg", 5, "05", "CT AND VT INPUT 2", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "724", "724", True, "DIM", 0.0, 2.5, 160.625, 130.605, 160.625, 129.73, 165.275, 132.605),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "UX'", "UX'", False, "DIM", 0.0, 2.5, 184.179, 131.25, 184.179, 130.375, 188.829, 133.25),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    phase_candidate = next(item for item in candidates if item.text_id == "T2" and item.line_group_id == "G1")
    pair = pairs[0]

    assert phase_candidate.status == "accepted"
    assert phase_candidate.value == "UX'"
    assert phase_candidate.channel == "schematic_semantic_endpoint_channel"
    assert phase_candidate.channel_detail == "schematic_ac_phase_label"
    assert phase_candidate.side == "left"
    assert pair.left_value == "724"
    assert pair.right_value is None
    assert pair.status == "review"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["semantic_kind"] == "schematic_semantic_annotation"
    assert pair.evidence["semantic_mapping_kind"] == "schematic_ac_phase_label"
    assert pair.evidence["semantic_endpoint"] == "UX'"
    assert pair.evidence["numeric_endpoint"] == "724"
    assert pair.evidence["ordinary_pair_eligible"] is False


def test_build_terminal_candidates_keeps_far_ux_prime_out_of_ac_line_span_annotation() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=165.0,
            start_y=130.0,
            end_x=215.0,
            end_y=130.0,
            length=50.0,
            wire_candidate_score=0.55,
            member_line_ids=["L1"],
            layer_hints=["0"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "05 交流回路图2.dwg", 5, "05", "CT AND VT INPUT 2", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "724", "724", True, "DIM", 0.0, 2.5, 160.625, 130.605, 160.625, 129.73, 165.275, 132.605),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "UX'", "UX'", False, "DIM", 0.0, 2.5, 184.179, 136.0, 184.179, 135.125, 188.829, 138.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    assert not [item for item in candidates if item.text_id == "T2" and item.status == "accepted"]
    assert pairs[0].pair_kind == "ordinary_pair"
    assert pairs[0].left_value == "724"
    assert pairs[0].right_value is None


def test_build_terminal_candidates_rejects_cross_row_ux_prime_endpoint_hit() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=180.0,
            start_y=140.0,
            end_x=215.0,
            end_y=140.0,
            length=35.0,
            wire_candidate_score=0.55,
            member_line_ids=["L1"],
            layer_hints=["0"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "05 交流回路图2.dwg", 5, "05", "CT AND VT INPUT 2", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "723", "723", True, "DIM", 0.0, 2.5, 160.625, 140.605, 160.625, 139.73, 165.275, 142.605),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "UX", "UX", False, "DIM", 0.0, 2.5, 184.179, 141.25, 184.179, 140.375, 187.279, 143.25),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "UX'", "UX'", False, "DIM", 0.0, 2.5, 184.179, 131.25, 184.179, 130.375, 188.829, 133.25),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    cross_row = next(item for item in candidates if item.text_id == "T3")
    pair = pairs[0]

    assert cross_row.status == "rejected"
    assert cross_row.rejection_reason == "schematic_semantic_out_of_row"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["semantic_endpoint"] == "UX"
    assert pair.evidence["numeric_endpoint"] == "723"


def test_build_terminal_candidates_keeps_terminal_ac_marker_out_of_schematic_endpoint_channel() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=40.0,
            start_y=185.0,
            end_x=115.0,
            end_y=185.0,
            length=75.0,
            wire_candidate_score=0.55,
            member_line_ids=["L1"],
            layer_hints=["0"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "LEFT TERMINAL 1", "屏端子图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "UA", "UA", False, "DIM", 0.0, 2.5, 42.0, 185.6, 40.0, 184.5, 45.0, 187.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "3-21n720", "3-21n720", False, "DIM", 0.0, 2.5, 71.0, 185.6, 67.0, 184.5, 75.0, 187.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    phase_candidate = next(item for item in candidates if item.text_id == "T1")
    endpoint_candidate = next(item for item in candidates if item.text_id == "T2" and item.status == "accepted")
    assert phase_candidate.status == "rejected"
    assert phase_candidate.value is None
    assert phase_candidate.channel == "semantic_channel"
    assert phase_candidate.channel_detail == "not_numeric"
    assert endpoint_candidate.status == "accepted"
    assert endpoint_candidate.value == "720"
    assert endpoint_candidate.channel == "terminal_numeric_channel"


def test_build_terminal_candidates_keeps_schematic_i0_out_of_ac_phase_label_channel() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=180.0,
            start_y=210.0,
            end_x=215.0,
            end_y=210.0,
            length=35.0,
            wire_candidate_score=0.55,
            member_line_ids=["L1"],
            layer_hints=["0"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "04 交流回路图1.dwg", 4, "04", "CT AND VT INPUT 1", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "I0", "I0", False, "DIM", 0.0, 2.5, 184.0, 210.7, 183.0, 209.5, 188.0, 212.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "725", "725", True, "DIM", 0.0, 2.5, 178.0, 210.7, 176.0, 209.5, 181.0, 212.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    i0_candidate = next(item for item in candidates if item.text_id == "T1")
    assert i0_candidate.status == "rejected"
    assert i0_candidate.value is None
    assert i0_candidate.channel == "noise_channel"
    assert pairs[0].left_value == "725"
    assert pairs[0].pair_kind == "ordinary_pair"


def test_build_pairs_marks_single_sided_network_time_label_as_semantic_annotation() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=360.0,
            start_y=235.0,
            end_x=400.0,
            end_y=235.0,
            length=40.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="grid",
        )
    ]
    sheets = [
        SheetRecord(
            "S1",
            "F1",
            "07 网络对时回路图.dwg",
            7,
            "07",
            "COMMUNICATION AND TIME SYNCHRONIZATION",
            "二次原理图",
            "primary",
            "filename",
            True,
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "B+", "B+", False, "TEXT", 0.0, 2.5, 358.0, 236.0, 357.0, 234.5, 362.0, 237.5),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "601", "601", True, "TEXT", 0.0, 2.5, 360.5, 239.3, 359.0, 238.0, 365.0, 241.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic_candidate = next(item for item in candidates if item.text_id == "T1")
    pair = pairs[0]

    assert semantic_candidate.status == "accepted"
    assert semantic_candidate.channel_detail == "schematic_network_time_label"
    assert pair.left_value == "601"
    assert pair.right_value is None
    assert pair.status == "review"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["semantic_kind"] == "schematic_semantic_annotation"
    assert pair.evidence["semantic_endpoint"] == "B+"
    assert pair.evidence["numeric_endpoint"] == "601"
    assert pair.evidence["ordinary_pair_eligible"] is False


def test_build_pairs_marks_comm_rxd_gnd_as_network_time_semantic() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=237.5,
            start_y=210.0,
            end_x=277.5,
            end_y=210.0,
            length=40.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["CONNECT"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord(
            "S1",
            "F1",
            "09 通讯、对时及打印回路.dwg",
            9,
            "09",
            "COMMUNICATION AND TIME SYNCHRONIZATION",
            "二次原理图",
            "primary",
            "filename",
            True,
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1308", "1308", True, "DIM", 0.0, 2.5, 272.5, 205.66, 270.0, 204.0, 278.0, 208.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "RXD", "RXD", False, "DIM", 0.0, 2.5, 265.96, 203.75, 262.0, 202.0, 272.0, 206.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]
    assert semantic.status == "accepted"
    assert semantic.channel_detail == "schematic_network_time_label"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["semantic_endpoint"] == "RXD"
    assert "1308" in {pair.left_value, pair.right_value, pair.evidence.get("numeric_endpoint")}


def test_build_pairs_maps_hierarchical_control_box_endpoint() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=81.25,
            start_y=190.0,
            end_x=336.87,
            end_y=190.0,
            length=255.62,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord(
            "S1",
            "F1",
            "20 高压侧操作箱原理图2.dwg",
            20,
            "20",
            "CONTROL CIRCUIT 2 FOR HV SIDE",
            "二次原理图",
            "primary",
            "filename",
            True,
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "702", "702", True, "DIM", 0.0, 2.5, 71.84, 188.12, 70.0, 186.0, 76.0, 191.0),
        TextItem(
            "T2",
            "S1",
            "F1",
            "H2",
            "TEXT",
            "1-4C2D2",
            "1-4C2D2",
            False,
            "DIM",
            0.0,
            2.5,
            316.0,
            181.14,
            310.0,
            179.0,
            330.0,
            184.0,
        ),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    logic = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]
    assert logic.status == "accepted"
    assert logic.channel == "wire_logic_endpoint_channel"
    assert logic.value == "1-4C2D2"
    assert pair.pair_kind == "wire_component_mapping"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert {pair.left_value, pair.right_value} == {"702", "1-4C2D2"}


def test_build_pairs_marks_pressure_plate_reset_signal_as_binary_description() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=110.0,
            start_y=205.0,
            end_x=205.0,
            end_y=205.0,
            length=95.0,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord(
            "S1",
            "F1",
            "12 压板及功能接点开入图3.dwg",
            12,
            "12",
            "压板及功能接点开入",
            "二次原理图",
            "primary",
            "filename",
            True,
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "14", "14", True, "DIM", 0.0, 2.5, 101.0, 205.0, 99.0, 203.0, 105.0, 207.0),
        TextItem(
            "T2",
            "S1",
            "F1",
            "H2",
            "TEXT",
            "Enable remote operate",
            "Enable remote operate",
            False,
            "DIM",
            0.0,
            2.5,
            174.18,
            206.26,
            160.0,
            204.0,
            200.0,
            209.0,
        ),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    semantic = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]
    assert semantic.status == "accepted"
    assert semantic.channel_detail == "schematic_binary_input_function_description"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.evidence["ordinary_pair_eligible"] is False
    assert pair.evidence["semantic_endpoint"] == "Enable remote operate"


def test_build_terminal_candidates_deprioritizes_dim_single_character_numeric_text() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "721", "721", True, "TEXT", 0.0, 2.5, 6.5, 20.0, 6.5, 19.0, 12.0, 22.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "6", "6", True, "DIM", 0.0, 2.5, 8.0, 20.0, 8.0, 19.0, 12.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG)

    left_text_candidate = next(item for item in candidates if item.side == "left" and item.text_id == "T1")
    left_dim_candidate = next(item for item in candidates if item.side == "left" and item.text_id == "T2")

    assert left_text_candidate.status == "accepted"
    assert left_dim_candidate.status == "accepted"
    assert left_text_candidate.score > left_dim_candidate.score
    assert left_text_candidate.rank == 1
    assert left_dim_candidate.rank == 2


def test_build_terminal_candidates_rejects_dim_single_character_numeric_text_on_primary_page() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "04 回路图.dwg", 4, "04", "回路图", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "721", "721", True, "TEXT", 0.0, 2.5, 6.5, 20.0, 6.5, 19.0, 12.0, 22.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "6", "6", True, "DIM", 0.0, 2.5, 8.0, 20.0, 8.0, 19.0, 12.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    accepted = next(item for item in candidates if item.text_id == "T1")
    rejected = next(item for item in candidates if item.text_id == "T2")

    assert accepted.status == "accepted"
    assert accepted.rank == 1
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "single_char_layer_filtered"
    assert rejected.rank is None


def test_build_terminal_candidates_keeps_single_character_mark_candidate_on_terminal_page() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "6", "6", True, "MARK", 0.0, 2.5, 34.0, 20.0, 32.0, 19.0, 36.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    accepted = next(item for item in candidates if item.text_id == "T1")

    assert accepted.status == "accepted"
    assert accepted.rejection_reason is None
    assert accepted.rank == 1


def test_build_terminal_candidates_accepts_terminal_page_suffix_value_patterns() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "07 屏端子图.dwg", 7, "07", "屏端子图", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1-21n110", "1-21n110", False, "0", 0.0, 2.5, 36.0, 20.0, 36.0, 19.0, 44.0, 22.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "3-21n210", "3-21n210", False, "0", 0.0, 2.5, 116.0, 20.0, 116.0, 19.0, 124.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    left_candidate = next(item for item in candidates if item.side == "left" and item.text_id == "T1")
    right_candidate = next(item for item in candidates if item.side == "right" and item.text_id == "T2")

    assert left_candidate.status == "accepted"
    assert left_candidate.value == "110"
    assert left_candidate.rank == 1
    assert left_candidate.score > 0.0
    assert right_candidate.status == "accepted"
    assert right_candidate.value == "210"
    assert right_candidate.rank == 1
    assert right_candidate.score > 0.0


def test_build_terminal_candidates_uses_terminal_page_wider_search_window() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    terminal_sheet = [
        SheetRecord("S1", "F1", "07 屏端子图.dwg", 7, "07", "屏端子图", "屏端子图", "supplemental", "filename", True)
    ]
    plain_sheet = [
        SheetRecord("S1", "F1", "04 回路图.dwg", 4, "04", "回路图", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1-21n110", "1-21n110", False, "0", 0.0, 2.5, 36.0, 20.0, 36.0, 19.0, 44.0, 22.0),
    ]

    terminal_candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, terminal_sheet)
    plain_candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, plain_sheet)

    terminal_candidate = next(item for item in terminal_candidates if item.text_id == "T1")
    plain_candidate = [item for item in plain_candidates if item.text_id == "T1"]

    assert terminal_candidate.status == "accepted"
    assert terminal_candidate.value == "110"
    assert plain_candidate == []


def test_build_terminal_candidates_keeps_terminal_suffix_pattern_rejected_on_non_terminal_page() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "04 回路图.dwg", 4, "04", "回路图", "二次原理图", "primary", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1-21n110", "1-21n110", False, "0", 0.0, 2.5, 8.5, 20.0, 8.5, 19.0, 16.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    rejected = next(item for item in candidates if item.text_id == "T1")

    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "not_numeric"
    assert rejected.value is None


def test_build_terminal_candidates_supports_top_bottom_on_vertical_component_group() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=60.0,
            start_y=80.0,
            end_x=60.0,
            end_y=40.0,
            length=40.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="vertical",
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "101", "101", True, "TEXT", 0.0, 2.5, 60.5, 84.0, 59.5, 83.0, 63.0, 86.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "202", "202", True, "TEXT", 0.0, 2.5, 59.5, 36.0, 58.5, 35.0, 62.0, 38.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG)

    top_candidate = next(item for item in candidates if item.side == "top" and item.text_id == "T1")
    bottom_candidate = next(item for item in candidates if item.side == "bottom" and item.text_id == "T2")

    assert top_candidate.status == "accepted"
    assert top_candidate.rank == 1
    assert top_candidate.score > 0.0
    assert bottom_candidate.status == "accepted"
    assert bottom_candidate.rank == 1
    assert bottom_candidate.score > 0.0


def test_build_terminal_candidates_dedupes_shared_text_anchor_on_vertical_component_page() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=60.0,
            start_y=80.0,
            end_x=60.0,
            end_y=40.0,
            length=40.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="vertical",
        ),
        LineGroup(
            line_group_id="G2",
            sheet_id="S1",
            file_id="F1",
            start_x=65.0,
            start_y=80.0,
            end_x=65.0,
            end_y=40.0,
            length=40.0,
            wire_candidate_score=0.9,
            member_line_ids=["L2"],
            layer_hints=["WIRE"],
            orientation="vertical",
        ),
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 元件接线图2.dwg", 20, "20", "元件接线图2", "元件接线图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1", "1", True, "0", 0.0, 2.5, 61.8, 83.8, 60.8, 82.8, 63.8, 85.8),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "2", "2", True, "0", 0.0, 2.5, 61.9, 36.2, 60.9, 35.2, 63.9, 38.2),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    accepted = [item for item in candidates if item.status == "accepted"]
    rejected = [item for item in candidates if item.rejection_reason == "shared_text_anchor_reused"]

    assert {(item.line_group_id, item.side) for item in accepted} == {("G1", "top"), ("G1", "bottom")}
    assert {(item.line_group_id, item.side) for item in rejected} == {("G2", "top"), ("G2", "bottom")}


def test_build_terminal_candidates_extracts_component_suffix_values_on_vertical_page() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=60.0,
            start_y=80.0,
            end_x=60.0,
            end_y=40.0,
            length=40.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="vertical",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 元件接线图2.dwg", 20, "20", "元件接线图2", "元件接线图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "3-21CD43", "3-21CD43", False, "TEXT", 0.0, 3.0, 56.5, 84.1, 55.0, 82.0, 60.0, 86.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "3-21n419", "3-21n419", False, "TEXT", 0.0, 3.0, 56.5, 33.5, 55.0, 31.5, 60.0, 35.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    top_candidate = next(item for item in candidates if item.side == "top" and item.text_id == "T1")
    bottom_candidate = next(item for item in candidates if item.side == "bottom" and item.text_id == "T2")

    assert top_candidate.status == "accepted"
    assert top_candidate.value == "43"
    assert top_candidate.rank == 1
    assert bottom_candidate.status == "accepted"
    assert bottom_candidate.value == "419"
    assert bottom_candidate.rank == 1


def test_build_terminal_candidates_prefers_component_suffix_values_over_single_char_numeric() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=60.0,
            start_y=80.0,
            end_x=60.0,
            end_y=40.0,
            length=40.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="vertical",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 元件接线图2.dwg", 20, "20", "元件接线图2", "元件接线图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1", "1", True, "0", 0.0, 2.5, 61.8, 83.8, 60.8, 82.8, 63.8, 85.8),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "2", "2", True, "0", 0.0, 2.5, 61.9, 36.2, 60.9, 35.2, 63.9, 38.2),
        TextItem("T3", "S1", "F1", "H3", "TEXT", "3-21CD43", "3-21CD43", False, "TEXT", 0.0, 3.0, 56.5, 84.1, 55.0, 82.0, 60.0, 86.0),
        TextItem("T4", "S1", "F1", "H4", "TEXT", "3-21n419", "3-21n419", False, "TEXT", 0.0, 3.0, 56.5, 33.5, 55.0, 31.5, 60.0, 35.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    derived_top = next(item for item in candidates if item.text_id == "T3")
    derived_bottom = next(item for item in candidates if item.text_id == "T4")
    suppressed_top = next(item for item in candidates if item.text_id == "T1")
    suppressed_bottom = next(item for item in candidates if item.text_id == "T2")

    assert derived_top.status == "accepted"
    assert derived_top.value == "43"
    assert derived_top.rank == 1
    assert derived_bottom.status == "accepted"
    assert derived_bottom.value == "419"
    assert derived_bottom.rank == 1
    assert suppressed_top.status == "rejected"
    assert suppressed_top.rejection_reason == "superseded_by_derived_numeric"
    assert suppressed_bottom.status == "rejected"
    assert suppressed_bottom.rejection_reason == "superseded_by_derived_numeric"


def test_build_terminal_candidates_keeps_component_suffix_patterns_disabled_on_horizontal_component_page() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=10.0,
            start_y=20.0,
            end_x=90.0,
            end_y=20.0,
            length=80.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "19 元件接线图1.dwg", 19, "19", "元件接线图1", "元件接线图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "1-21n717", "1-21n717", False, "TEXT", 0.0, 3.0, 8.0, 20.0, 7.0, 18.0, 14.0, 22.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    rejected = next(item for item in candidates if item.text_id == "T1")
    assert rejected.status == "rejected"
    assert rejected.rejection_reason == "not_numeric"


def test_build_terminal_candidates_rejects_virtual_fjl_internal_pin_numbers() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=60.0,
            start_y=135.0,
            end_x=60.0,
            end_y=120.0,
            length=15.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="vertical",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 元件接线图2.dwg", 20, "20", "元件接线图2", "元件接线图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "9E3D:VIRTUAL:1", "TEXT", "1", "1", True, "0", 0.0, 2.5, 61.8, 133.8, 60.8, 132.8, 63.8, 135.8, "FJL-25-2A_Mirror"),
        TextItem("T2", "S1", "F1", "9E3D:VIRTUAL:0", "TEXT", "2", "2", True, "0", 0.0, 2.5, 61.9, 121.2, 60.9, 120.2, 63.9, 123.2, "FJL-25-2A_Mirror"),
        TextItem("T3", "S1", "F1", "T3", "TEXT", "LP3", "LP3", False, "TEXT", 0.0, 3.0, 60.2, 149.0, 58.0, 147.0, 66.0, 151.0),
        TextItem("T4", "S1", "F1", "T4", "TEXT", "FJL1-2.5/2A", "FJL1-2.5/2A", False, "TEXT", 0.0, 3.0, 56.5, 150.5, 55.0, 148.5, 67.0, 152.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    top_pin = next(item for item in candidates if item.text_id == "T1")
    bottom_pin = next(item for item in candidates if item.text_id == "T2")

    assert top_pin.status == "rejected"
    assert top_pin.rejection_reason == "block_internal_pin_number"
    assert bottom_pin.status == "rejected"
    assert bottom_pin.rejection_reason == "block_internal_pin_number"



def test_build_terminal_candidates_rejects_virtual_fjl_non_mirror_internal_pin_numbers() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=90.0,
            start_y=255.0,
            end_x=90.0,
            end_y=240.0,
            length=15.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="vertical",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "27 元件接线图4.dwg", 27, "27", "元件接线图4", "元件接线图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "8603:VIRTUAL:1", "TEXT", "1", "1", True, "0", 0.0, 2.5, 94.4, 254.2, 93.4, 253.2, 95.4, 255.2, "FJL-25-2A"),
        TextItem("T2", "S1", "F1", "8603:VIRTUAL:0", "TEXT", "2", "2", True, "0", 0.0, 2.5, 94.4, 239.2, 93.4, 238.2, 95.4, 240.2, "FJL-25-2A"),
        TextItem("T3", "S1", "F1", "T3", "TEXT", "4-21KLP2", "4-21KLP2", False, "MARK", 0.0, 3.0, 89.9, 269.4, 88.0, 267.0, 98.0, 271.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    top_pin = next(item for item in candidates if item.text_id == "T1")
    bottom_pin = next(item for item in candidates if item.text_id == "T2")

    assert top_pin.status == "rejected"
    assert top_pin.rejection_reason == "block_internal_pin_number"
    assert bottom_pin.status == "rejected"
    assert bottom_pin.rejection_reason == "block_internal_pin_number"


def test_build_terminal_candidates_extracts_hd_suffix_on_vertical_component_page() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=300.0,
            start_y=135.0,
            end_x=300.0,
            end_y=120.0,
            length=15.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="vertical",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "20 元件接线图2.dwg", 20, "20", "元件接线图2", "元件接线图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "HD5", "HD5", False, "TEXT", 0.0, 3.0, 300.2, 139.1, 298.0, 137.1, 304.0, 141.1),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "502", "502", True, "TEXT", 0.0, 2.5, 301.0, 121.0, 300.0, 120.0, 304.0, 123.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    top_candidate = next(item for item in candidates if item.text_id == "T1")
    bottom_candidate = next(item for item in candidates if item.text_id == "T2")

    assert top_candidate.status == "accepted"
    assert top_candidate.value == "5"
    assert bottom_candidate.status == "accepted"
    assert bottom_candidate.value == "502"


def test_build_terminal_candidates_row_locks_terminal_strip_candidates_to_same_row() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=127.5,
            start_y=45.0,
            end_x=202.5,
            end_y=45.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("L0", "S1", "F1", "H1", "TEXT", "21", "21", True, "TEXT", 0.0, 2.5, 150.998, 46.0, 149.0, 44.0, 153.0, 48.0),
        TextItem("L1", "S1", "F1", "H2", "TEXT", "22", "22", True, "TEXT", 0.0, 2.5, 150.998, 41.0, 149.0, 39.0, 153.0, 43.0),
        TextItem("L2", "S1", "F1", "H3", "TEXT", "20", "20", True, "TEXT", 0.0, 2.5, 150.998, 51.0, 149.0, 49.0, 153.0, 53.0),
        TextItem("R0", "S1", "F1", "H4", "TEXT", "3-21n211", "3-21n211", False, "TEXT", 0.0, 2.5, 158.5, 46.0, 156.0, 44.0, 162.0, 48.0),
        TextItem("R1", "S1", "F1", "H5", "TEXT", "3-21n212", "3-21n212", False, "TEXT", 0.0, 2.5, 158.5, 41.0, 156.0, 39.0, 162.0, 43.0),
        TextItem("R2", "S1", "F1", "H6", "TEXT", "3-21n210", "3-21n210", False, "TEXT", 0.0, 2.5, 158.5, 51.0, 156.0, 49.0, 162.0, 53.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    pair_candidates, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    accepted = [item for item in candidates if item.status == "accepted"]
    row_locked = [item for item in candidates if item.rejection_reason == "terminal_row_locked"]
    pair = pairs[0]

    assert {(item.text_id, item.rank) for item in accepted} == {("L0", 1), ("R0", 1)}
    assert {item.text_id for item in row_locked} == {"L1", "L2", "R1", "R2"}
    assert len(pair_candidates) == 1
    assert pair.left_value == "21"
    assert pair.right_value == "211"
    assert pair.status == "review"
    assert "ambiguous" not in pair.rationale
    assert pair.confidence > 0.75


def test_build_terminal_candidates_bypasses_terminal_strip_annotation_text() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=40.0,
            start_y=200.0,
            end_x=115.0,
            end_y=200.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "说明", "说明", False, "TEXT", 0.0, 2.5, 88.5, 200.0, 86.0, 198.0, 92.0, 202.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "上接3-21QD24/72", "上接3-21QD24/72", False, "TEXT", 0.0, 2.5, 88.5, 205.0, 86.0, 203.0, 98.0, 207.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    for text_id in {"T1", "T2"}:
        rejected = next(item for item in candidates if item.text_id == text_id)
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "terminal_strip_bypass_text"


def test_build_terminal_candidates_suppresses_terminal_row_number_column() -> None:
    line_groups = [
        LineGroup(
            line_group_id=f"G{index}",
            sheet_id="S1",
            file_id="F1",
            start_x=127.5,
            start_y=220.0 - index * 5.0,
            end_x=202.5,
            end_y=220.0 - index * 5.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=[f"L{index}"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
        for index in range(6)
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = []
    for index, number in enumerate(range(13, 19)):
        y = 221.0 - index * 5.0
        texts.extend(
            [
                TextItem(
                    f"N{index}",
                    "S1",
                    "F1",
                    f"HN{index}",
                    "TEXT",
                    str(number),
                    str(number),
                    True,
                    "TEXT",
                    0.0,
                    3.0,
                    151.0,
                    y,
                    149.0,
                    y - 2.0,
                    153.0,
                    y + 2.0,
                ),
                TextItem(
                    f"E{index}",
                    "S1",
                    "F1",
                    f"HE{index}",
                    "TEXT",
                    f"3-21n{130 + index}",
                    f"3-21n{130 + index}",
                    False,
                    "TEXT",
                    0.0,
                    3.0,
                    158.5,
                    y,
                    155.0,
                    y - 2.0,
                    164.0,
                    y + 2.0,
                ),
            ]
        )

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)

    row_numbers = [
        item
        for index in range(6)
        for item in candidates
        if item.text_id == f"N{index}" and item.line_group_id == f"G{index}" and item.side == "left"
    ]
    endpoints = [
        item
        for index in range(6)
        for item in candidates
        if item.text_id == f"E{index}" and item.line_group_id == f"G{index}" and item.side == "right"
    ]
    endpoint_channels = {item.channel for item in endpoints}
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    assert {item.text_id for item in row_numbers} == {f"N{index}" for index in range(6)}
    assert {item.rejection_reason for item in row_numbers} == {"terminal_row_number_local_numeric"}
    assert {item.channel for item in row_numbers} == {"semantic_channel"}
    assert {item.channel_detail for item in row_numbers} == {"terminal_row_number_local_numeric"}
    assert {item.status for item in endpoints} == {"accepted"}
    assert endpoint_channels == {"terminal_numeric_channel"}
    assert {pair.left_value for pair in pairs} == {None}
    assert {pair.right_value for pair in pairs} == {str(value) for value in range(130, 136)}


def test_build_terminal_candidates_supports_mirrored_right_terminal_strip_columns() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=40.0,
            start_y=48.5,
            end_x=115.0,
            end_y=48.5,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "23 右侧端子图1.dwg", 23, "23", "右侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("L0", "S1", "F1", "H1", "TEXT", "1-21n132", "1-21n132", False, "TEXT", 0.0, 2.5, 66.0, 48.5, 63.0, 46.5, 70.0, 50.5),
        TextItem("L1", "S1", "F1", "H2", "TEXT", "1-21n231", "1-21n231", False, "TEXT", 0.0, 2.5, 66.0, 43.5, 63.0, 41.5, 70.0, 45.5),
        TextItem("R0", "S1", "F1", "H3", "TEXT", "20", "20", True, "TEXT", 0.0, 2.5, 88.5, 48.5, 86.0, 46.5, 92.0, 50.5),
        TextItem("R1", "S1", "F1", "H4", "TEXT", "21", "21", True, "TEXT", 0.0, 2.5, 88.5, 43.5, 86.0, 41.5, 92.0, 45.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    pair_candidates, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    accepted = [item for item in candidates if item.status == "accepted"]
    row_locked = [item for item in candidates if item.rejection_reason == "terminal_row_locked"]
    pair = pairs[0]

    assert {(item.text_id, item.rank) for item in accepted} == {("L0", 1), ("R0", 1)}
    assert {item.text_id for item in row_locked} == {"L1", "R1"}
    assert len(pair_candidates) == 1
    assert pair.left_value == "132"
    assert pair.right_value == "20"
    assert pair.status == "review"
    assert "ambiguous" not in pair.rationale


def test_build_terminal_candidates_splits_left_terminal_short_bridge_roles() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=310.0,
            start_y=225.0,
            end_x=385.0,
            end_y=225.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("L0", "S1", "F1", "H1", "TEXT", "1-21n110", "1-21n110", False, "TEXT", 0.0, 3.0, 311.0, 226.0, 308.0, 224.0, 315.0, 228.0),
        TextItem("M0", "S1", "F1", "H2", "TEXT", "81", "81", True, "TEXT", 0.0, 3.0, 333.5, 226.0, 331.0, 224.0, 336.0, 228.0),
        TextItem("R0", "S1", "F1", "H3", "TEXT", "3-21n330", "3-21n330", False, "TEXT", 0.0, 3.0, 341.0, 226.0, 338.0, 224.0, 345.0, 228.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    left_candidate = next(item for item in candidates if item.text_id == "L0" and item.side == "left")
    right_candidate = next(item for item in candidates if item.text_id == "R0" and item.side == "right")
    middle_left = next(item for item in candidates if item.text_id == "M0" and item.side == "left")
    mirrored_left = next(item for item in candidates if item.text_id == "R0" and item.side == "left")
    mirrored_right = next(item for item in candidates if item.text_id == "L0" and item.side == "right")
    pair = pairs[0]

    assert left_candidate.status == "accepted"
    assert left_candidate.value == "110"
    assert left_candidate.rank == 1
    assert right_candidate.status == "accepted"
    assert right_candidate.value == "330"
    assert right_candidate.rank == 1
    assert middle_left.status == "rejected"
    assert middle_left.rejection_reason == "terminal_short_bridge_role_filtered"
    assert mirrored_left.status == "rejected"
    assert mirrored_left.rejection_reason == "terminal_short_bridge_role_filtered"
    assert mirrored_right.status == "rejected"
    assert mirrored_right.rejection_reason == "terminal_short_bridge_role_filtered"
    assert pair.left_value == "110"
    assert pair.right_value == "330"
    assert "ambiguous" not in pair.rationale


def test_build_terminal_candidates_keeps_single_numeric_column_one_sided_on_short_bridge() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=310.0,
            start_y=220.0,
            end_x=385.0,
            end_y=220.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "24 右侧端子图2.dwg", 24, "24", "右侧端子图2", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("T0", "S1", "F1", "H1", "TEXT", "10", "10", True, "TEXT", 0.0, 3.0, 359.25, 221.0, 357.0, 219.0, 362.0, 223.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    left_candidate = next(item for item in candidates if item.text_id == "T0" and item.side == "left")
    right_candidate = next(item for item in candidates if item.text_id == "T0" and item.side == "right")
    pair = pairs[0]

    assert left_candidate.status == "rejected"
    assert left_candidate.rejection_reason == "terminal_short_bridge_single_column"
    assert right_candidate.status == "accepted"
    assert right_candidate.value == "10"
    assert right_candidate.rank == 1
    assert pair.left_value is None
    assert pair.right_value == "10"
    assert pair.status == "review"
    assert pair.pair_kind == "continuation"
    assert pair.rationale == "missing left candidate; continuation relation"


def test_build_terminal_candidates_assigns_single_derived_bridge_column_to_its_visual_side() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=310.0,
            start_y=235.0,
            end_x=385.0,
            end_y=235.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("M0", "S1", "F1", "H1", "TEXT", "79", "79", True, "TEXT", 0.0, 3.0, 333.5, 236.0, 331.0, 234.0, 336.0, 238.0),
        TextItem("R0", "S1", "F1", "H2", "TEXT", "3-21n328", "3-21n328", False, "TEXT", 0.0, 3.0, 341.0, 236.0, 338.0, 234.0, 345.0, 238.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    middle_left = next(item for item in candidates if item.text_id == "M0" and item.side == "left")
    middle_right = next(item for item in candidates if item.text_id == "M0" and item.side == "right")
    derived_left = next(item for item in candidates if item.text_id == "R0" and item.side == "left")
    derived_right = next(item for item in candidates if item.text_id == "R0" and item.side == "right")
    pair = pairs[0]

    assert middle_left.status == "rejected"
    assert middle_left.rejection_reason == "terminal_short_bridge_single_column"
    assert middle_right.status == "rejected"
    assert middle_right.rejection_reason == "terminal_short_bridge_role_filtered"
    assert derived_left.status == "rejected"
    assert derived_left.rejection_reason == "terminal_short_bridge_single_column"
    assert derived_right.status == "accepted"
    assert derived_right.value == "328"
    assert pair.left_value is None
    assert pair.right_value == "328"
    assert pair.pair_kind == "continuation"
    assert pair.rationale == "missing left candidate; continuation relation"


def test_build_terminal_candidates_suppresses_local_numeric_on_terminal_semantic_row() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=127.5,
            start_y=255.0,
            end_x=202.5,
            end_y=255.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "21 左侧端子图1.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("S0", "S1", "F1", "H1", "TEXT", "3", "3", True, "TEXT", 0.0, 3.0, 151.75, 256.0, 149.5, 254.0, 154.0, 258.0),
        TextItem("S1", "S1", "F1", "H2", "TEXT", "3-21KLP2-1", "3-21KLP2-1", False, "TEXT", 0.0, 3.0, 128.5, 256.0, 124.5, 254.0, 132.5, 258.0),
        TextItem("S2", "S1", "F1", "H3", "TEXT", "1-21n108", "1-21n108", False, "TEXT", 0.0, 3.0, 158.5, 256.0, 155.0, 254.0, 162.0, 258.0),
        TextItem("S3", "S1", "F1", "H4", "TEXT", "+", "+", False, "TEXT", 0.0, 2.5, 91.0, 256.25, 90.0, 255.0, 92.0, 257.5),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    local_numeric = next(item for item in candidates if item.text_id == "S0" and item.side == "left")
    continuation = next(item for item in candidates if item.text_id == "S2" and item.side == "right")
    pair = pairs[0]

    assert local_numeric.status == "rejected"
    assert local_numeric.rejection_reason == "terminal_semantic_local_numeric"
    assert local_numeric.channel == "semantic_channel"
    assert local_numeric.channel_detail == "terminal_semantic_local_numeric"
    assert next(item for item in candidates if item.text_id == "S1").channel == "semantic_channel"
    assert continuation.status == "accepted"
    assert continuation.value == "108"
    assert continuation.channel == "terminal_numeric_channel"
    assert pair.left_value is None
    assert pair.right_value == "108"
    assert pair.pair_kind == "semantic_mapping"
    assert pair.rationale == "missing left candidate; semantic mapping relation"


def test_build_terminal_candidates_suppresses_local_numeric_on_terminal_semantic_ac_row() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=215.0,
            start_y=220.0,
            end_x=290.0,
            end_y=220.0,
            length=75.0,
            wire_candidate_score=0.9,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord("S1", "F1", "24 右侧端子图2.dwg", 24, "24", "右侧端子图2", "屏端子图", "supplemental", "filename", True)
    ]
    texts = [
        TextItem("A0", "S1", "F1", "H1", "TEXT", "AC230V L", "AC230V L", False, "TEXT", 0.0, 2.5, 216.0, 221.25, 212.0, 220.0, 220.0, 223.0),
        TextItem("A1", "S1", "F1", "H2", "TEXT", "3-21n511", "3-21n511", False, "TEXT", 0.0, 3.0, 241.0, 221.0, 238.0, 219.0, 245.0, 223.0),
        TextItem("A2", "S1", "F1", "H3", "TEXT", "1", "1", True, "TEXT", 0.0, 3.0, 264.25, 221.0, 262.0, 219.0, 267.0, 223.0),
        TextItem("A3", "S1", "F1", "H4", "TEXT", "AK-1", "AK-1", False, "TEXT", 0.0, 2.5, 241.0, 221.0, 238.0, 219.0, 245.0, 223.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    continuation = next(item for item in candidates if item.text_id == "A1" and item.side == "left")
    local_numeric = next(item for item in candidates if item.text_id == "A2" and item.side == "right")
    pair = pairs[0]

    assert local_numeric.status == "rejected"
    assert local_numeric.rejection_reason == "terminal_semantic_local_numeric"
    assert local_numeric.channel == "semantic_channel"
    assert local_numeric.channel_detail == "terminal_semantic_local_numeric"
    assert next(item for item in candidates if item.text_id == "A0").channel == "semantic_channel"
    assert continuation.status == "accepted"
    assert continuation.value == "511"
    assert continuation.channel == "terminal_numeric_channel"
    assert pair.left_value == "511"
    assert pair.right_value is None
    assert pair.pair_kind == "semantic_mapping"
    assert pair.rationale == "missing right candidate; semantic mapping relation"


def test_build_terminal_candidates_accepts_control_box_device_endpoint() -> None:
    line_groups = [
        LineGroup(
            line_group_id="G1",
            sheet_id="S1",
            file_id="F1",
            start_x=81.25,
            start_y=200.0,
            end_x=336.87,
            end_y=200.0,
            length=255.62,
            wire_candidate_score=0.85,
            member_line_ids=["L1"],
            layer_hints=["WIRE"],
            orientation="horizontal",
        )
    ]
    sheets = [
        SheetRecord(
            "S1",
            "F1",
            "20 高压侧操作箱原理图2.dwg",
            20,
            "20",
            "高压侧操作箱原理图2",
            "二次原理图",
            "primary",
            "filename",
            True,
        )
    ]
    texts = [
        TextItem("T1", "S1", "F1", "H1", "TEXT", "802", "802", True, "DIM", 0.0, 2.5, 71.84, 195.62, 69.0, 194.0, 76.0, 198.0),
        TextItem("T2", "S1", "F1", "H2", "TEXT", "TC2", "TC2", False, "DIM", 0.0, 2.5, 309.55, 195.0, 306.0, 193.0, 315.0, 198.0),
    ]

    candidates = build_terminal_candidates(line_groups, texts, DEFAULT_CONFIG, sheets)
    _, pairs = build_pairs(line_groups, candidates, sheets, DEFAULT_CONFIG)

    device = next(item for item in candidates if item.text_id == "T2")
    pair = pairs[0]
    assert device.status == "accepted"
    assert device.channel == "schematic_semantic_endpoint_channel"
    assert device.channel_detail == "schematic_device_endpoint"
    assert device.value == "TC2"
    assert pair.pair_kind == "semantic_mapping"
    assert {pair.left_value, pair.right_value} == {"802", "TC2"}
    assert pair.evidence.get("ordinary_pair_eligible") is False

