from __future__ import annotations

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass

from dwg_audit.domain.models import Pair

__all__ = ["PairGraphSummary", "build_pair_graph"]


@dataclass(slots=True)
class PairGraphSummary:
    left_to_rights: dict[str, frozenset[str]]
    right_to_lefts: dict[str, frozenset[str]]
    pair_lookup: frozenset[tuple[str, str]]
    ordered_pair_counts: dict[tuple[str, str], int]
    unordered_pair_counts: dict[frozenset[str], int]


def build_pair_graph(pairs: list[Pair]) -> PairGraphSummary:
    left_to_rights: dict[str, set[str]] = defaultdict(set)
    right_to_lefts: dict[str, set[str]] = defaultdict(set)
    ordered_pair_counts: Counter[tuple[str, str]] = Counter()
    unordered_pair_counts: Counter[frozenset[str]] = Counter()

    for pair in pairs:
        if not pair.left_value or not pair.right_value:
            continue

        ordered_edge = (pair.left_value, pair.right_value)
        unordered_edge = frozenset(ordered_edge)

        left_to_rights[pair.left_value].add(pair.right_value)
        right_to_lefts[pair.right_value].add(pair.left_value)
        ordered_pair_counts[ordered_edge] += 1
        unordered_pair_counts[unordered_edge] += 1

    return PairGraphSummary(
        left_to_rights={left: frozenset(rights) for left, rights in left_to_rights.items()},
        right_to_lefts={right: frozenset(lefts) for right, lefts in right_to_lefts.items()},
        pair_lookup=frozenset(ordered_pair_counts),
        ordered_pair_counts=dict(ordered_pair_counts),
        unordered_pair_counts=dict(unordered_pair_counts),
    )
