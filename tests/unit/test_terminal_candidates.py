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
    assert pair.rationale == "missing left candidate"


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
    assert pair.rationale == "missing left candidate"


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
    assert continuation.status == "accepted"
    assert continuation.value == "108"
    assert pair.left_value is None
    assert pair.right_value == "108"
    assert pair.rationale == "missing left candidate"


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
    assert continuation.status == "accepted"
    assert continuation.value == "511"
    assert pair.left_value == "511"
    assert pair.right_value is None
    assert pair.rationale == "missing right candidate"
