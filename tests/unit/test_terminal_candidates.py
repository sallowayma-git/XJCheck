from dwg_audit.audit.candidates import build_terminal_candidates
from dwg_audit.domain.models import LineGroup
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
