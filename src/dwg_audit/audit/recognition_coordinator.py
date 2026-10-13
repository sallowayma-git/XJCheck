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
    native_pairs: list = field(default_factory=list)
    closed_groups: set = field(default_factory=set)
    endpoint_cache: dict = field(default_factory=dict)
    native_text_claims: dict = field(default_factory=dict)
    supplemental_for: dict = field(default_factory=dict)

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

    def accept_native(self, pairs, observations):
        self.native_pairs = pairs
        self.closed_groups = {(p.sheet_id, p.line_group_id) for p in pairs
            if p.line_group_id and (p.status == "pass" or p.evidence.get("sw_conflicts"))}
        self.closed_groups.update((r["sheet_id"], r["line_group_id"]) for r in observations
            if r.get("state") in {"EXCLUDED", "CONFIRMED_CONFLICT"} and r.get("line_group_id"))
        for pair in pairs:
            if pair.status != "pass" or not pair.left_value or not pair.right_value:
                continue
            sw = pair.evidence.get("superworks") or {}
            ids = []
            for side in ("left", "right"):
                endpoint = sw.get(side) or {}
                ids.append({getattr(pair, f"{side}_text_id"), endpoint.get("text_id"),
                    endpoint.get("label_text_id"), endpoint.get("pin_text_id")} - {None, ""})
            for left in ids[0]:
                for right in ids[1]:
                    self.native_text_claims.setdefault((pair.file_id, pair.sheet_id, left, right), []).append(pair)

    def pair_ids(self, stem):
        return ScopedPairIds(stem, self)


class ScopedPairIds(IdFactory):
    def __init__(self, stem, context):
        super().__init__(stem)
        self.context = context

    def admit(self, page, left_value, right_value, left_text_id, right_text_id, *, kind=None):
        from types import SimpleNamespace
        from dwg_audit.audit.superworks_extractor import _pair_endpoints_equivalent
        claims = self.context.native_text_claims
        candidates = list(claims.get((page.file_id, page.sheet_id, left_text_id, right_text_id), []))
        candidates += claims.get((page.file_id, page.sheet_id, right_text_id, left_text_id), [])
        claim = SimpleNamespace(left_value=left_value, right_value=right_value)
        def covered(fixed):
            if _pair_endpoints_equivalent(claim, fixed):
                return True
            # A reciprocal SW strip row owns its actual row and destination text,
            # even when V1 spells the row prefix differently. Never apply this to wires.
            if kind == "table_mapping" and fixed.evidence.get("superworks", {}).get("row_id"):
                from dwg_audit.audit.superworks_extractor import _ends_equivalent
                return _ends_equivalent(right_value, fixed.right_value)
            return False
        if any(covered(fixed) for fixed in candidates):
            self.context.counts["v1_structured_claims_skipped"] += 1
            return False
        return True

