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

NATIVE_DISPATCH = {"RESOLVED": "retain", "CONFIRMED_CONFLICT": "report", "EXCLUDED": "exclude",
    "INCOMPLETE": "supplement", "AMBIGUOUS": "supplement", "ENGINE_FAILURE": "incomplete_analysis"}


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
    text_facts: dict = field(default_factory=dict)
    native_instance_claims: dict = field(default_factory=dict)

    @classmethod
    def create(cls, texts, wire_break_evidence=None):
        started = perf_counter()
        by_sheet = defaultdict(list)
        text_facts = {}
        for text in texts:
            by_sheet[text.sheet_id].append(text)
            text_facts[(text.file_id, text.sheet_id, text.text_id)] = text
        result = cls(text_indexes={sid: TextSpatialIndex(rows) for sid, rows in by_sheet.items()},
                     path_checkers=path_body_checkers(wire_break_evidence), text_facts=text_facts)
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
            if p.line_group_id and NATIVE_DISPATCH.get(p.evidence.get("native_resolution_state")) in {"retain", "report", "exclude"}}
        self.closed_groups.update((r["sheet_id"], r["line_group_id"]) for r in observations
            if r.get("state") in {"EXCLUDED", "CONFIRMED_CONFLICT"} and r.get("line_group_id"))
        for pair in pairs:
            if pair.evidence.get("native_resolution_state") != "RESOLVED" or not pair.left_value or not pair.right_value:
                continue
            sw = pair.evidence.get("superworks") or {}
            ids = []
            for side in ("left", "right"):
                endpoint = sw.get(side) or {}
                ids.append({getattr(pair, f"{side}_text_id"), endpoint.get("text_id"),
                    endpoint.get("label_text_id"), endpoint.get("pin_text_id")} - {None, ""})
            if sw.get("part_id"):
                ids[0].update({pair.evidence.get("component_port_text_id"), pair.evidence.get("component_body_text_id"), sw.get("label_text_id")} - {None, ""})
                ids[1].update({sw.get("connection_text_id"), pair.evidence.get("external_endpoint_text_id")} - {None, ""})
                handle = sw.get("symbol_handle")
                # Virtual definition pins are anchored to their concrete INSERT.
                # Nested paths need their full instance identity, not a bare handle.
                if handle and sw.get("instance_path") in (None, "", f"/{handle}"):
                    for right in ids[1]:
                        self.native_instance_claims.setdefault((pair.file_id, pair.sheet_id, handle, right), []).append(pair)
            for left in ids[0]:
                for right in ids[1]:
                    self.native_text_claims.setdefault((pair.file_id, pair.sheet_id, left, right), []).append(pair)

    def pair_ids(self, stem):
        return ScopedPairIds(stem, self)


class ScopedPairIds(IdFactory):
    def __init__(self, stem, context):
        super().__init__(stem)
        self.context = context

    def admit(self, page, left_value, right_value, left_text_id, right_text_id, *, kind=None, body_text_id=None, port_number=None):
        from types import SimpleNamespace
        from dwg_audit.audit.superworks_extractor import _pair_endpoints_equivalent
        claims = self.context.native_text_claims
        candidates = list(claims.get((page.file_id, page.sheet_id, left_text_id, right_text_id), []))
        candidates += claims.get((page.file_id, page.sheet_id, right_text_id, left_text_id), [])
        claim = SimpleNamespace(left_value=left_value, right_value=right_value)
        if kind in {"component_mapping", "ordinary_pair"}:
            from dwg_audit.audit.superworks_extractor import _ends_equivalent
            for pin_id, external_id in ((left_text_id, right_text_id), (right_text_id, left_text_id)):
                pin = self.context.text_facts.get((page.file_id, page.sheet_id, pin_id))
                external = self.context.text_facts.get((page.file_id, page.sheet_id, external_id))
                if pin is None or external is None or ":VIRTUAL:" not in pin.handle:
                    continue
                handle = pin.handle.split(":VIRTUAL:", 1)[0]
                for fixed in self.context.native_instance_claims.get((page.file_id, page.sheet_id, handle, external_id), []):
                    number = str(port_number or pin.normalized_text).strip()
                    fixed_number = str((fixed.evidence.get("superworks") or {}).get("port_number") or "")
                    same_pin = number.isdigit() and fixed_number.isdigit() and int(number) == int(fixed_number)
                    if _pair_endpoints_equivalent(claim, fixed) or (same_pin and _ends_equivalent(external.normalized_text, fixed.right_value)):
                        self.context.counts["v1_structured_claims_skipped"] += 1
                        return False
        def covered(fixed):
            if _pair_endpoints_equivalent(claim, fixed):
                return True
            # A reciprocal SW strip row owns its actual row and destination text,
            # even when V1 spells the row prefix differently. Never apply this to wires.
            if kind == "table_mapping" and fixed.evidence.get("superworks", {}).get("row_id"):
                from dwg_audit.audit.superworks_extractor import _ends_equivalent
                return _ends_equivalent(left_value if right_text_id == fixed.left_text_id else right_value, fixed.right_value)
            if kind == "component_mapping" and fixed.evidence.get("superworks", {}).get("part_id"):
                from dwg_audit.audit.superworks_extractor import _ends_equivalent
                return (body_text_id == fixed.evidence.get("component_body_text_id") and body_text_id is not None
                    and left_text_id == fixed.evidence.get("component_port_text_id")
                    and str(port_number) == str(fixed.evidence.get("component_port"))
                    and _ends_equivalent(right_value, fixed.right_value))
            return False
        if any(covered(fixed) for fixed in candidates):
            self.context.counts["v1_structured_claims_skipped"] += 1
            return False
        return True


def finalize_evidence(pairs, context):
    """Admit producer facts, preserve fixed SW sides, and keep draft geometry out of pass."""
    from dwg_audit.audit.superworks_extractor import _identities_agree, _true_conflicts
    for pair in pairs:
        evidence = pair.evidence or {}
        pair.evidence = evidence
        if pair.status == "discard":
            evidence["recognition_state"] = "EXCLUDED"
            continue
        conflicts = _true_conflicts(evidence.get("sw_conflicts") or [])
        sw = evidence.get("superworks") or {}
        partial = sw.get("partial") or sw.get("validation_only")
        if partial:
            for side in ("left", "right"):
                fixed = sw.get(side) or {}
                value = getattr(pair, f"{side}_value")
                identity = fixed.get("value")
                if not identity or not fixed.get("wire_touched") or fixed.get("reason_codes"):
                    continue
                if not value:
                    continue  # A missing geometric/semantic partner is not fabricated here.
                if _identities_agree(identity, value, fixed.get("endpoint_aliases", [])):
                    if str(value).isdigit() and str(identity) != str(value):
                        evidence.setdefault("fixed_fact_normalizations", []).append(
                            {"side": side, "before": value, "after": identity, "port_ids": fixed.get("port_ids", [])})
                        setattr(pair, f"{side}_value", identity)
                        pair.pair_key = f"{pair.left_value}->{pair.right_value}"
                        context.counts["fixed_identity_normalizations"] += 1
                else:
                    evidence.setdefault("engine_evidence_conflicts", []).append(
                        {"side": side, "candidate": value, "fixed_identity": identity,
                         "port_ids": fixed.get("port_ids", [])})
                    setattr(pair, f"{side}_value", identity)
                    pair.pair_key = f"{pair.left_value}->{pair.right_value}"
        physical = [evidence.get(f"selected_{side}_physical_endpoint") or {} for side in ("left", "right")]
        draft = any(p.get("annotation_status") == "MACHINE_PROPOSED" or
                    p.get("topology_state") in {"POSSIBLE", "UNKNOWN"} for p in physical)
        if any(p.get("source") == "reciprocal_cad_label_and_terminal_geometry" for p in physical):
            context.counts["verified_v2_geometry_bindings"] += 1
            evidence["engine_contributors"] = ["v1", "v2"] + (["superworks"] if sw else [])
        if conflicts:
            state = "CONFIRMED_CONFLICT"
        elif not pair.left_value or not pair.right_value:
            state = "INCOMPLETE"
        elif draft or evidence.get("engine_evidence_conflicts") or pair.status != "pass":
            state = "AMBIGUOUS"
        else:
            state = "RESOLVED"
        evidence["recognition_state"] = state
        if state != "RESOLVED":
            pair.status = "review"
            pair.confidence_bucket = "review"
            evidence["structured_source"] = None
        context.counts[f"final:{state}"] += 1
    return pairs


def build_resolution_issues(observations, pairs, pages, existing=()):
    """Retain native errors and actionable uncovered gaps without inventing a Pair."""
    import hashlib
    from dwg_audit.domain.models import Issue
    from dwg_audit.audit.superworks_extractor import _true_conflicts, _competing_object_id
    page_map = {p.sheet_id: p for p in pages}
    covered = {(p.file_id, p.sheet_id, p.line_group_id) for p in pairs
        if p.status != "discard" or (p.evidence or {}).get("discard_reason") == "device_internal"}
    seen = {(i.file_id, i.sheet_id, (i.evidence or {}).get("conflict_object_id"), reason)
            for i in existing for reason in (i.evidence or {}).get("reason_codes", [])}
    result = []
    issue_by_key = {(i.file_id, i.sheet_id, (i.evidence or {}).get("conflict_object_id"), reason): i
        for i in existing for reason in (i.evidence or {}).get("reason_codes", [])}
    for item in observations:
        state = item.get("state")
        if state not in {"CONFIRMED_CONFLICT", "INCOMPLETE", "AMBIGUOUS"}:
            continue
        endpoints = [item.get(side) or {} for side in ("left", "right")]
        if state != "CONFIRMED_CONFLICT":
            if (item.get("file_id"), item.get("sheet_id"), item.get("line_group_id")) in covered:
                continue
            if not item.get("connect_label_id") and not any(e.get("wire_touched") and e.get("port_ids") for e in endpoints):
                continue
            if not item.get("line_group_id") and not item.get("connect_label_id"):
                continue
        reasons = _true_conflicts(item.get("reason_codes", [])) if state == "CONFIRMED_CONFLICT" else ["native_relation_incomplete"]
        port_ids = sorted({pid for e in endpoints for pid in e.get("port_ids", [])})
        symbols = sorted({str(e["symbol_id"]) for e in endpoints if e.get("symbol_id")})
        for reason in reasons:
            object_id = (_competing_object_id(item) if reason.startswith("competing_physical_port") else None) or ",".join(port_ids) or ",".join(symbols) or item.get("connect_label_id") or item.get("line_group_id") or item["record_id"]
            key = (item.get("file_id"), item.get("sheet_id"), object_id, reason)
            if key in seen:
                prior = issue_by_key.get(key)
                if prior is not None:
                    # Keep one reviewer group for the same competing instances,
                    # but retain every physical port/contact as a separate witness.
                    refs = prior.evidence.setdefault("resolution_observations", [])
                    if not any(r["record_id"] == item["record_id"] for r in refs):
                        refs.append(item)
                        prior.evidence_refs.append({"kind": "native_resolution", "object_key": item.get("object_key"),
                            "sheet_id": item.get("sheet_id"), "coords": item.get("coords"), "port_ids": port_ids})
                continue
            seen.add(key)
            page = page_map.get(item.get("sheet_id"))
            coords = item.get("coords") or []
            evidence = {**item, "source": "superworks", "reason_codes": [reason],
                "resolution_reason_codes": item.get("reason_codes", []), "conflict_object_id": object_id,
                "handling_class": "review", "recognition_state": state, "resolution_observations": [item]}
            if len(coords) == 4:
                evidence.update(line_start=coords[:2], line_end=coords[2:])
            conflict = state == "CONFIRMED_CONFLICT"
            message = f"SuperWORKS metadata conflict {reason} on {object_id}." if conflict else "原生关系缺少可核验的端点或连接证据，需要审核。"
            result.append(Issue("ISW" + hashlib.sha256(repr(key).encode()).hexdigest()[:20],
                "R-SUPERWORKS-CONFLICT" if conflict else "R-RECOGNITION-GAP", "review", "open", 0.0,
                message, item.get("sheet_id"), item.get("file_id"), None, item.get("line_group_id"),
                endpoints[0].get("value"), endpoints[1].get("value"),
                filename=page.filename if page else None, sheet_no=page.sheet_no if page else None,
                sheet_order=page.sheet_order if page else None, evidence=evidence,
                title="SuperWORKS 元数据关联冲突" if conflict else "识别待审核",
                issue_type="superworks_conflict" if conflict else "recognition_gap",
                explanation="保留原始句柄和物理位置；补证没有消除这项冲突或缺口。",
                recommended_action="在图纸对应位置检查元数据、端点及连接。"))
            issue_by_key[key] = result[-1]
    from dwg_audit.audit.issue_triage import classify_and_group_issues
    return classify_and_group_issues(result)
