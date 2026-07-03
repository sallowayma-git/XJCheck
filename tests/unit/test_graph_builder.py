from __future__ import annotations

from dwg_audit.audit.graph_builder import build_pair_graph
from dwg_audit.domain.models import Pair


def _pair(pair_id: str, left_value: str | None, right_value: str | None) -> Pair:
    return Pair(
        pair_id=pair_id,
        line_group_id=f"G-{pair_id}",
        sheet_id="S1",
        file_id="F1",
        selected_pair_candidate_id=None,
        left_value=left_value,
        right_value=right_value,
        confidence=0.95,
        status="pass",
        rationale="ok",
    )


def test_build_pair_graph_summarizes_adjacency_and_counts() -> None:
    graph = build_pair_graph(
        [
            _pair("P1", "101", "201"),
            _pair("P2", "101", "202"),
            _pair("P3", "301", "201"),
            _pair("P4", "101", "201"),
            _pair("P5", "201", "101"),
            _pair("P6", "101", None),
        ]
    )

    assert graph.left_to_rights == {
        "101": frozenset({"201", "202"}),
        "301": frozenset({"201"}),
        "201": frozenset({"101"}),
    }
    assert graph.right_to_lefts == {
        "201": frozenset({"101", "301"}),
        "202": frozenset({"101"}),
        "101": frozenset({"201"}),
    }
    assert graph.pair_lookup == frozenset(
        {
            ("101", "201"),
            ("101", "202"),
            ("301", "201"),
            ("201", "101"),
        }
    )
    assert graph.ordered_pair_counts == {
        ("101", "201"): 2,
        ("101", "202"): 1,
        ("301", "201"): 1,
        ("201", "101"): 1,
    }
    assert graph.unordered_pair_counts == {
        frozenset({"101", "201"}): 3,
        frozenset({"101", "202"}): 1,
        frozenset({"201", "301"}): 1,
    }


def test_build_pair_graph_keeps_self_loops_and_skips_incomplete_pairs() -> None:
    graph = build_pair_graph(
        [
            _pair("P1", "101", "101"),
            _pair("P2", "101", None),
            _pair("P3", None, "101"),
        ]
    )

    assert graph.left_to_rights == {"101": frozenset({"101"})}
    assert graph.right_to_lefts == {"101": frozenset({"101"})}
    assert graph.pair_lookup == frozenset({("101", "101")})
    assert graph.ordered_pair_counts == {("101", "101"): 1}
    assert graph.unordered_pair_counts == {frozenset({"101"}): 1}
