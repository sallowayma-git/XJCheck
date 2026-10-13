"""Shared recognition facts and bounded, object-scoped engine coordination.

Geometry is shared; evidence admission remains owned by the existing producers.
No engine scores are compared and no possible geometry is promoted to a fact.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from time import perf_counter

from dwg_audit.audit.candidates import TextSpatialIndex
from dwg_audit.audit.line_groups import build_line_groups, path_body_checkers
from dwg_audit.utils.ids import IdFactory


@dataclass(slots=True)
class SharedRecognitionContext:
    text_indexes: dict = field(default_factory=dict)
    path_checkers: dict = field(default_factory=dict)
    route_groups: dict = field(default_factory=dict)
    seconds: dict = field(default_factory=lambda: defaultdict(float))
    counts: dict = field(default_factory=lambda: defaultdict(int))

    @classmethod
    def create(cls, texts, wire_break_evidence=None):
        started = perf_counter()
        by_sheet = defaultdict(list)
        for text in texts:
            by_sheet[text.sheet_id].append(text)
        result = cls(text_indexes={sid: TextSpatialIndex(rows) for sid, rows in by_sheet.items()},
                     path_checkers=path_body_checkers(wire_break_evidence))
        result.seconds["indexes"] = perf_counter() - started
        result.counts["text_indexes_built"] = len(by_sheet)
        return result

    def groups_for_route(self, *, id_stem, pages, texts, lines, config, classifications, wire_break_evidence):
        key = (id_stem, tuple(sorted(p.sheet_id for p in pages)))
        if key not in self.route_groups:
            started = perf_counter()
            self.route_groups[key] = build_line_groups(lines, pages, config, texts,
                classifications=classifications, group_id_factory=IdFactory(f"G{id_stem}"),
                band_id_factory=IdFactory(f"RB{id_stem}"), wire_break_evidence=wire_break_evidence)
            self.seconds["line_groups"] += perf_counter() - started
            self.counts["route_group_builds"] += 1
        else:
            self.counts["route_group_reuses"] += 1
        return self.route_groups[key]
