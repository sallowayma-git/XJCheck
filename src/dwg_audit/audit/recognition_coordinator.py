"""Shared recognition facts and bounded, object-scoped engine coordination.

Geometry is shared; evidence admission remains owned by the existing producers.
No engine scores are compared and no possible geometry is promoted to a fact.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from time import perf_counter

from dwg_audit.audit.candidates import GROUND_NETWORK_NAME_PATTERN, TextSpatialIndex
from dwg_audit.audit.superworks_device_internal import on_device_internal_wire
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
    port_indexes: dict = field(default_factory=dict)

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

    def admit(self, page, left_value, right_value, left_text_id, right_text_id, *, kind=None, body_text_id=None, port_number=None, line_group=None):
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
                    sw = fixed.evidence.get("superworks") or {}
                    border_candidate = (line_group is not None and
                        {str(layer).upper() for layer in line_group.layer_hints} == {"BORDER"} and
                        sw.get("connect_line_geometry_unique") and sw.get("connect_line_id") and
                        sw["connect_line_id"] not in line_group.member_line_ids)
                    if _pair_endpoints_equivalent(claim, fixed) or ((same_pin or border_candidate) and _ends_equivalent(external.normalized_text, fixed.right_value)):
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


# GAP-COORD: gate, presentation and diagnostics for R-RECOGNITION-GAP.
GAP_STEPS = ("device_internal", "continuity", "physical_v1", "terminal_frame_boundary", "x_element_only", "self_loop")
TERMINAL_CATEGORIES = frozenset({"装置端子", "端子"})
DEVICE_TERMINAL = "装置端子"
ELEMENT_CATEGORIES = frozenset({"内部元件", "线圈"})
NON_TERMINAL_CATEGORIES = frozenset({"内部元件", "线圈", "接地", "接插件", "", None})
PHYSICAL_OVERLAP_RATIO = 0.8
PHYSICAL_COLLINEAR_TOL = 0.8
FRAME_BOUNDARY_TOL = 0.6
FRAME_STUB_MAX_LENGTH = 50.0
UNPINNED_GAP_CLASS = "unpinned_element"


@dataclass(slots=True)
class GapFacts:
    """Facts the gate reads from the SuperWORKS artifacts of one project. A None field disables its step."""
    internal_wires: dict | None = None  # (file_id, device port_id) -> wire handles of that port's device-internal link
    continuity_ports: frozenset | None = None  # port ids covered by a cross-page continuity link (covers_target)
    line_geometry: dict = field(default_factory=dict)  # (file_id, sheet_id, line_group_id) -> ((x1, y1), (x2, y2))
    frame_boundaries: dict | None = None  # (file_id, sheet_id) -> [{"rect": (x0, y0, x1, y1), "label": caption}]
    frame_connect_dots: dict | None = None  # (file_id, sheet_id) -> [(x, y)] explicit SW connection points
    frame_port_labels: dict | None = None  # (file_id, sheet_id) -> {port_id: exact SW terminal/device label}


@dataclass(slots=True)
class GapResolution:
    issues: list
    suppressed: list
    stats: dict


def _ident_key(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if GROUND_NETWORK_NAME_PATTERN.fullmatch(text):
        return "gnd"  # G-1: the shared ground network name is one identity on every side
    return text.casefold()


def _json_list(value) -> list:
    if isinstance(value, str):
        return json.loads(value) if value else []
    return list(value or [])


def _side(item, name) -> dict:
    return item.get(name) or {}


def _is_terminal_side(side) -> bool:
    return side.get("category") in TERMINAL_CATEGORIES and bool(side.get("port_ids"))


def _terminal_port_ids(endpoints) -> list:
    return sorted({pid for side in endpoints if side.get("category") in TERMINAL_CATEGORIES
                   for pid in side.get("port_ids", [])})


def _segment_on_geometry(segment, geometry, tol=PHYSICAL_COLLINEAR_TOL) -> float:
    """Fraction of the observed segment that lies on the geometry line (0.0 unless collinear within tol)."""
    (x1, y1), (x2, y2) = segment
    (ax, ay), (bx, by) = geometry
    length = math.hypot(x2 - x1, y2 - y1)
    span = math.hypot(bx - ax, by - ay)
    if length < 1e-6 or span < 1e-6:
        return 0.0
    ux, uy = (bx - ax) / span, (by - ay) / span
    for px, py in ((x1, y1), (x2, y2)):
        if abs((px - ax) * uy - (py - ay) * ux) > tol:
            return 0.0
    t1 = (x1 - ax) * ux + (y1 - ay) * uy
    t2 = (x2 - ax) * ux + (y2 - ay) * uy
    low, high = min(t1, t2), max(t1, t2)
    return max(0.0, min(high, span) - max(low, 0.0)) / length


def _pair_geometry(pair, facts):
    geometry = None
    if pair.line_group_id:
        geometry = facts.line_geometry.get((pair.file_id, pair.sheet_id, pair.line_group_id))
    if geometry is None:
        evidence = pair.evidence or {}
        start, end = evidence.get("line_start"), evidence.get("line_end")
        if start and end and len(start) >= 2 and len(end) >= 2:
            geometry = ((float(start[0]), float(start[1])), (float(end[0]), float(end[1])))
    return geometry


def _same_identity(pair_value, observed, aliases) -> bool:
    """Production identity rule (_ends_equivalent) with the G-1 ground name as one identity."""
    from dwg_audit.audit.superworks_extractor import _ends_equivalent
    if not pair_value or not observed:
        return False
    if _ident_key(pair_value) and _ident_key(pair_value) == _ident_key(observed):
        return True
    return _ends_equivalent(pair_value, observed, aliases)


def _physical_v1_pair(endpoints, coords, sheet_pairs):
    """pair_id of a non-discard V1 pair on the same physical segment whose identities name every identified side."""
    if not coords or len(coords) != 4:
        return None
    identified = [(side.get("value"), side.get("candidate_values") or ()) for side in endpoints if _ident_key(side.get("value"))]
    if not identified:
        return None
    segment = ((float(coords[0]), float(coords[1])), (float(coords[2]), float(coords[3])))
    for pair, geometry in sheet_pairs:
        if _segment_on_geometry(segment, geometry) < PHYSICAL_OVERLAP_RATIO:
            continue
        values = [pair.left_value, pair.right_value]
        if all(any(_same_identity(value, observed, aliases) for value in values) for observed, aliases in identified):
            return pair.pair_id
    return None


def _x_element_only(endpoints, end_geometry) -> bool:
    """Both ends are elements (no terminal side), with no SYMB2 termpoint and no vertical terminal rail at either end."""
    if any(side.get("category") not in NON_TERMINAL_CATEGORIES for side in endpoints):
        return False
    if not end_geometry or len(end_geometry) != 2:
        return False
    return not any(end.get("unreg_pin") or end.get("rail_t") for end in end_geometry)


def _self_loop(endpoints) -> bool:
    """Two contacts of one identity on the same SuperWORKS ports (the same logical terminal, F1)."""
    if any(not side.get("port_ids") for side in endpoints):
        return False
    keys = [_ident_key(side.get("value")) for side in endpoints]
    return bool(keys[0]) and keys[0] == keys[1]


def _unpinned_element(endpoints) -> bool:
    """One identified terminal side, and the other side an element whose pin carries no identity on the drawing."""
    terminal = [side for side in endpoints if _is_terminal_side(side) and _ident_key(side.get("value"))]
    element = [side for side in endpoints if side.get("category") in ELEMENT_CATEGORIES and not _ident_key(side.get("value"))]
    return len(terminal) == 1 and len(element) == 1 and terminal[0] is not element[0]


def _terminal_port_contacts(endpoints):
    """Contact points and tolerances recorded by the endpoint's own SuperWORKS ports."""
    contacts = []
    for side in endpoints:
        if side.get("category") not in TERMINAL_CATEGORIES or not side.get("port_ids"):
            continue
        for port in _json_list(side.get("ports")):
            start, end = port.get("start"), port.get("end")
            if not isinstance(start, (list, tuple)) or not isinstance(end, (list, tuple)) or len(start) < 2 or len(end) < 2:
                continue
            try:
                point = ((float(start[0]) + float(end[0])) / 2.0,
                         (float(start[1]) + float(end[1])) / 2.0)
                tolerance = float(port.get("tolerance") or FRAME_BOUNDARY_TOL)
            except (TypeError, ValueError):
                continue
            if math.isfinite(tolerance):
                contacts.append((point, max(FRAME_BOUNDARY_TOL, tolerance), str(port.get("port_id") or "")))
    return contacts


def _inside_frame(point, rect, tol=FRAME_BOUNDARY_TOL):
    x0, y0, x1, y1 = rect
    return x0 - tol <= point[0] <= x1 + tol and y0 - tol <= point[1] <= y1 + tol


def _frame_boundary_contacts(segment, rect, tol=FRAME_BOUNDARY_TOL):
    """Orthogonal intersections of a short lead and a rectangle edge; overlapping an edge is not a contact."""
    x1, y1, x2, y2 = segment
    x0, y0, rx1, ry1 = rect
    dx, dy = x2 - x1, y2 - y1
    contacts = []
    if abs(dy) <= tol and abs(dx) > tol:
        y = (y1 + y2) / 2.0
        if abs(y - y0) <= tol or abs(y - ry1) <= tol:
            return []  # The observation lies along the frame's horizontal edge.
        if y0 - tol <= y <= ry1 + tol:
            for x in (x0, rx1):
                if min(x1, x2) - tol <= x <= max(x1, x2) + tol:
                    contacts.append((x, y))
    elif abs(dx) <= tol and abs(dy) > tol:
        x = (x1 + x2) / 2.0
        if abs(x - x0) <= tol or abs(x - rx1) <= tol:
            return []  # The observation lies along the frame's vertical edge.
        if x0 - tol <= x <= rx1 + tol:
            for y in (y0, ry1):
                if min(y1, y2) - tol <= y <= max(y1, y2) + tol:
                    contacts.append((x, y))
    return list(dict.fromkeys(contacts))


def _frame_caption_matches_port(label, caption_keys):
    """Match the exact SW label, or its device prefix followed only by a numeric terminal suffix."""
    normalized = str(label or "").strip().casefold()
    if not normalized:
        return False
    for caption in caption_keys:
        if normalized == caption:
            return True
        if normalized.startswith(caption):
            suffix = normalized[len(caption):]
            if suffix and suffix.isdigit():
                return True
    return False


def _terminal_frame_boundary(item, endpoints, facts):
    """A short lead whose frame-edge intersection is itself a segment endpoint."""
    if facts.frame_boundaries is None or facts.frame_connect_dots is None or facts.frame_port_labels is None:
        return None
    coords = _json_list(item.get("coords"))
    if len(coords) != 4:
        return None
    try:
        segment = tuple(float(value) for value in coords)
    except (TypeError, ValueError):
        return None
    length = math.hypot(segment[2] - segment[0], segment[3] - segment[1])
    if length <= FRAME_BOUNDARY_TOL or length > FRAME_STUB_MAX_LENGTH:
        return None
    terminal_contacts = _terminal_port_contacts(endpoints)
    segment_endpoints = ((segment[0], segment[1]), (segment[2], segment[3]))
    if not any(math.hypot(point[0] - endpoint[0], point[1] - endpoint[1]) <= tolerance
               for point, tolerance, _ in terminal_contacts for endpoint in segment_endpoints):
        return None
    key = (item.get("file_id"), item.get("sheet_id"))
    dots = facts.frame_connect_dots.get(key, ())
    port_labels = facts.frame_port_labels.get(key, {})
    candidates = []
    for frame in facts.frame_boundaries.get(key, ()):
        rect = frame.get("rect") if isinstance(frame, dict) else None
        label = str(frame.get("label") or "").strip() if isinstance(frame, dict) else ""
        if not rect or len(rect) != 4 or not label:
            continue
        captions = frame.get("captions") or (label,)
        caption_keys = {str(caption).strip().casefold() for caption in captions if str(caption).strip()}
        contacts = _frame_boundary_contacts(segment, rect)
        if len(contacts) != 1:
            continue
        contact = contacts[0]
        boundary_endpoints = [index for index, endpoint in enumerate(segment_endpoints)
                              if math.hypot(contact[0] - endpoint[0], contact[1] - endpoint[1]) <= FRAME_BOUNDARY_TOL]
        if len(boundary_endpoints) != 1:
            continue  # A frame-edge intersection inside the observed segment is a crossing, not a stop.
        terminal_endpoint = segment_endpoints[1 - boundary_endpoints[0]]
        if any(math.hypot(contact[0] - point[0], contact[1] - point[1]) <= tolerance
               for point, tolerance, _ in terminal_contacts):
            continue  # A terminal port on the frame edge is a real endpoint, not a frame stop.
        inside_port_ids = {port_id for point, tolerance, port_id in terminal_contacts
                           if _inside_frame(point, rect)
                           and math.hypot(terminal_endpoint[0] - point[0],
                                          terminal_endpoint[1] - point[1]) <= tolerance}
        matching_inner_ports = {port_id for point, tolerance, port_id in terminal_contacts
                                if port_id in port_labels
                                and _frame_caption_matches_port(port_labels[port_id], caption_keys)
                                and _inside_frame(point, rect)
                                and math.hypot(terminal_endpoint[0] - point[0],
                                               terminal_endpoint[1] - point[1]) <= tolerance}
        if len(inside_port_ids) != 1 or matching_inner_ports != inside_port_ids:
            continue  # That inside terminal port's own SuperWORKS label must appear on the frame.
        if any(math.hypot(contact[0] - float(dot[0]), contact[1] - float(dot[1])) <= FRAME_BOUNDARY_TOL
               for dot in dots if isinstance(dot, (list, tuple)) and len(dot) >= 2):
            continue
        candidates.append({"rect": tuple(float(value) for value in rect), "label": label, "contact": contact})
    return candidates[0] if len(candidates) == 1 else None


def _gate_device_internal(endpoints, handles, file_id, facts, steps):
    """'device_internal' or 'continuity' when every terminal side is covered by the step, else None."""
    terminal_sides = [side for side in endpoints if side.get("category") in TERMINAL_CATEGORIES and side.get("port_ids")]
    if not terminal_sides:
        return None
    used_continuity = False
    for side in terminal_sides:
        ports = side.get("port_ids", [])
        by_wire = ("device_internal" in steps and facts.internal_wires is not None
            and side.get("category") == DEVICE_TERMINAL
            and any(on_device_internal_wire(facts.internal_wires, file_id, pid, handles) for pid in ports))
        if by_wire:
            continue
        by_continuity = ("continuity" in steps and facts.continuity_ports is not None
            and any(pid in facts.continuity_ports for pid in ports))
        if by_continuity:
            used_continuity = True
            continue
        return None
    return "continuity" if used_continuity else "device_internal"


def resolve_recognition_gaps(observations, pairs, pages, existing=(), *, facts=None, steps=GAP_STEPS) -> GapResolution:
    """Retain native errors and actionable uncovered gaps without inventing a Pair.

    Gate for an INCOMPLETE/AMBIGUOUS observation (a CONFIRMED_CONFLICT is never suppressed), in order:
    1. a device-internal discarded pair on the same line group (existing rule);
    2. ``device_internal``: every terminal side is a device terminal whose device-internal line link is on this wire;
       ``continuity``: every terminal side is covered by a cross-page continuity link (covers_target);
    3. ``physical_v1``: a non-discard V1 pair on the same physical segment (>= 80% overlap) whose identities include
       every identified side of the observation (line-group id is no longer the test);
    4. ``terminal_frame_boundary``: a short lead ends exactly at one unique closed captioned frame; the opposite
       endpoint must match one inside SuperWORKS terminal label and no connection dot may mark the contact;
       a segment whose frame-edge intersection lies in its interior remains reviewable;
    5. ``x_element_only``: no terminal side, and no termpoint or vertical terminal rail at either end;
    6. ``self_loop``: two contacts of one identity on SuperWORKS ports (F1).
    Suppressed observations are returned in ``suppressed`` for diagnostics. Presentation: one issue per uncovered
    terminal port; an identity-less element pin at a terminal is summarised as one issue per sheet.
    """
    import hashlib
    from dwg_audit.domain.models import Issue
    from dwg_audit.audit.superworks_extractor import _true_conflicts, _competing_object_id
    facts = facts or GapFacts()
    steps = frozenset(steps)
    stats = Counter()
    page_map = {p.sheet_id: p for p in pages}
    internal_groups = {(p.file_id, p.sheet_id, p.line_group_id) for p in pairs
        if p.status == "discard" and (p.evidence or {}).get("discard_reason") == "device_internal"}
    sheet_pairs = defaultdict(list)
    for pair in pairs:
        if pair.status == "discard":
            continue
        geometry = _pair_geometry(pair, facts)
        if geometry is not None:
            sheet_pairs[(pair.file_id, pair.sheet_id)].append((pair, geometry))
    seen = {(i.file_id, i.sheet_id, (i.evidence or {}).get("conflict_object_id"), reason)
            for i in existing for reason in (i.evidence or {}).get("reason_codes", [])}
    issue_by_key = {(i.file_id, i.sheet_id, (i.evidence or {}).get("conflict_object_id"), reason): i
        for i in existing for reason in (i.evidence or {}).get("reason_codes", [])}
    suppressed, kept, result = [], [], []
    for item in observations:
        state = item.get("state")
        if state not in {"CONFIRMED_CONFLICT", "INCOMPLETE", "AMBIGUOUS"}:
            continue
        endpoints = [_side(item, side) for side in ("left", "right")]
        if state == "CONFIRMED_CONFLICT":
            kept.append((item, endpoints))
            continue
        if (item.get("file_id"), item.get("sheet_id"), item.get("line_group_id")) in internal_groups:
            suppressed.append(_suppressed_row(item, "device_internal_pair", endpoints))
            stats["suppressed:device_internal_pair"] += 1
            continue
        if not item.get("connect_label_id") and not any(e.get("wire_touched") and e.get("port_ids") for e in endpoints):
            continue
        if not item.get("line_group_id") and not item.get("connect_label_id"):
            continue
        gate, pair_id, gate_details = _gate(item, endpoints, facts, steps, sheet_pairs)
        if gate is not None:
            suppressed.append({**_suppressed_row(item, gate, endpoints, gate_details), "pair_id": pair_id})
            stats[f"suppressed:{gate}"] += 1
            continue
        kept.append((item, endpoints))
    stats["kept_observations"] = len(kept)
    individual_terminals = set()
    for item, endpoints in kept:
        if item.get("state") != "CONFIRMED_CONFLICT" and not _unpinned_element(endpoints):
            individual_terminals.update(_terminal_port_ids(endpoints))
    individual, page_items = [], defaultdict(list)
    for item, endpoints in kept:
        pinless = item.get("state") != "CONFIRMED_CONFLICT" and _unpinned_element(endpoints)
        if pinless and not (set(_terminal_port_ids(endpoints)) & individual_terminals):
            page_items[(item.get("file_id"), item.get("sheet_id"))].append((item, endpoints))
        else:
            if _unpinned_element(endpoints):
                stats["unpinned_folded_into_terminal"] += 1
            individual.append((item, endpoints))
    # Terminal dedupe: observations that share a terminal port are one work item, so every uncovered terminal
    # appears in exactly one issue (union-find over the terminal ports of the individual observations).
    parent: dict[str, str] = {}

    def _root(port: str) -> str:
        parent.setdefault(port, port)
        while parent[port] != port:
            parent[port] = parent[parent[port]]
            port = parent[port]
        return port

    for item, endpoints in individual:
        if item.get("state") == "CONFIRMED_CONFLICT":
            continue
        terminals = _terminal_port_ids(endpoints)
        for other in terminals[1:]:
            parent[_root(other)] = _root(terminals[0])
        if terminals:
            _root(terminals[0])
    component_terminals: dict[str, set] = defaultdict(set)
    for item, endpoints in individual:
        terminals = _terminal_port_ids(endpoints) if item.get("state") != "CONFIRMED_CONFLICT" else []
        if terminals:
            component_terminals[_root(terminals[0])].update(terminals)
    for item, endpoints in individual:
        state = item.get("state")
        if state == "CONFIRMED_CONFLICT":
            reasons = _true_conflicts(item.get("reason_codes", []))
            terminals = []
        else:
            reasons = ["native_relation_incomplete"]
            terminals = sorted(component_terminals[_root(_terminal_port_ids(endpoints)[0])]) if _terminal_port_ids(endpoints) else []
        port_ids = sorted({pid for e in endpoints for pid in e.get("port_ids", [])})
        symbols = sorted({str(e["symbol_id"]) for e in endpoints if e.get("symbol_id")})
        for reason in reasons:
            if terminals:
                object_id = ",".join(terminals)
            else:
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
                        prior.evidence_refs.append(_observation_ref(item, endpoints, port_ids, page_map))
                continue
            seen.add(key)
            page = page_map.get(item.get("sheet_id"))
            coords = item.get("coords") or []
            evidence = {**item, "source": "superworks", "reason_codes": [reason],
                "resolution_reason_codes": item.get("reason_codes", []), "conflict_object_id": object_id,
                "handling_class": "review", "recognition_state": state, "resolution_observations": [item],
                "presentation": "terminal" if terminals else "observation", "terminal_port_ids": terminals}
            if len(coords) == 4:
                evidence.update(line_start=coords[:2], line_end=coords[2:])
            if page is not None:
                evidence.update(sheet_title=page.sheet_title)
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
            result[-1].evidence_refs = [_observation_ref(item, endpoints, port_ids, page_map, primary=True)]
            issue_by_key[key] = result[-1]
            stats["emitted:terminal" if terminals else "emitted:observation"] += 1
    for (file_id, sheet_id), items in sorted(page_items.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        result.append(_page_summary_issue(file_id, sheet_id, items, page_map))
        stats["emitted:page_summary"] += 1
        stats["page_summary_observations"] += len(items)
    from dwg_audit.audit.issue_triage import classify_and_group_issues
    return GapResolution(classify_and_group_issues(result), suppressed, dict(stats))


def _observation_ref(item, endpoints, port_ids, page_map, *, primary=False) -> dict:
    """Witness reference for one SuperWORKS observation: where it is, which ports it touches, what it says."""
    page = page_map.get(item.get("sheet_id"))
    coords = _json_list(item.get("coords"))
    has_line = len(coords) == 4
    sides = [{"value": side.get("value"), "category": side.get("category"),
              "ports": _json_list(side.get("ports"))} for side in endpoints]
    return {"kind": "native_resolution", "primary": primary, "record_id": item.get("record_id"),
        "object_key": item.get("object_key"), "file_id": item.get("file_id"), "sheet_id": item.get("sheet_id"),
        "filename": page.filename if page else None, "sheet_no": page.sheet_no if page else None,
        "sheet_title": page.sheet_title if page else None, "sheet_order": page.sheet_order if page else None,
        "line_group_id": item.get("line_group_id"),
        "line_start": coords[:2] if has_line else None, "line_end": coords[2:] if has_line else None,
        "coords": item.get("coords"), "port_ids": port_ids,
        "left_value": endpoints[0].get("value"), "right_value": endpoints[1].get("value"),
        "left": sides[0], "right": sides[1]}


def _gate(item, endpoints, facts, steps, sheet_pairs):
    """(gate step, closing pair id, audit details) for the first suppression, else (None, None, {})."""
    file_id, sheet_id = item.get("file_id"), item.get("sheet_id")
    handles = [str(h) for h in _json_list(item.get("source_handles"))]
    gate = _gate_device_internal(endpoints, handles, file_id, facts, steps)
    if gate is not None:
        return gate, None, {}
    if "physical_v1" in steps:
        pair_id = _physical_v1_pair(endpoints, _json_list(item.get("coords")), sheet_pairs.get((file_id, sheet_id), []))
        if pair_id:
            return "physical_v1", pair_id, {}
    if "terminal_frame_boundary" in steps:
        frame = _terminal_frame_boundary(item, endpoints, facts)
        if frame is not None:
            return "terminal_frame_boundary", None, frame
    if "x_element_only" in steps and item.get("end_geometry") is not None:
        if _x_element_only(endpoints, _json_list(item.get("end_geometry"))):
            return "x_element_only", None, {}
    if "self_loop" in steps and _self_loop(endpoints):
        return "self_loop", None, {}
    return None, None, {}


def build_resolution_issues(observations, pairs, pages, existing=(), *, facts=None, steps=GAP_STEPS):
    """Issues only. See resolve_recognition_gaps for the gate, the presentation and the diagnostics rows."""
    return resolve_recognition_gaps(observations, pairs, pages, existing, facts=facts, steps=steps).issues


def _suppressed_row(item, gate, endpoints, details=None) -> dict:
    row = {"record_id": item.get("record_id"), "object_key": item.get("object_key"), "file_id": item.get("file_id"),
        "sheet_id": item.get("sheet_id"), "line_group_id": item.get("line_group_id"), "state": item.get("state"),
        "suppressed_by": gate, "reason_codes": list(_json_list(item.get("reason_codes"))),
        "terminal_port_ids": _terminal_port_ids(endpoints), "coords": _json_list(item.get("coords")),
        "left_category": endpoints[0].get("category"), "right_category": endpoints[1].get("category"),
        "left_value": endpoints[0].get("value"), "right_value": endpoints[1].get("value")}
    if gate == "terminal_frame_boundary" and details:
        row.update(frame_rect=list(details["rect"]), frame_label=details["label"],
                   frame_contact=list(details["contact"]))
    return row


def _page_summary_issue(file_id, sheet_id, items, page_map):
    """One review issue for the terminals whose far end is an element pin with no identity on the drawing."""
    import hashlib
    from dwg_audit.domain.models import Issue
    terminals, observation_ids = {}, []
    for item, endpoints in items:
        observation_ids.append(item.get("record_id"))
        for side in endpoints:
            if _is_terminal_side(side):
                for pid in side.get("port_ids", []):
                    terminals.setdefault(pid, {"port_id": pid, "endpoint_identity": str(side.get("value") or "").strip(),
                        "coords": _json_list(item.get("coords")), "sheet_id": sheet_id, "file_id": file_id})
    page = page_map.get(sheet_id)
    sheet_label = (page.sheet_no if page else None) or str(sheet_id)
    count = len(terminals)
    key = (file_id, sheet_id, f"page:{UNPINNED_GAP_CLASS}", "native_relation_incomplete")
    message = f"图 {sheet_label} 有 {count} 个端子接到图面无脚号的元件引脚，已汇总为一条待审核，逐个端口见 terminal_ports。"
    evidence = {"source": "superworks", "presentation": "page_summary", "gap_class": UNPINNED_GAP_CLASS,
        "reason_codes": ["native_relation_incomplete"], "conflict_object_id": f"page:{sheet_id}:{UNPINNED_GAP_CLASS}",
        "handling_class": "review", "recognition_state": "INCOMPLETE", "terminal_count": count,
        "terminal_ports": list(terminals.values()), "observation_ids": observation_ids,
        "resolution_observations": [item for item, _ in items]}
    return Issue("ISW" + hashlib.sha256(repr(key).encode()).hexdigest()[:20],
        "R-RECOGNITION-GAP", "review", "open", 0.0, message, sheet_id, file_id, None, None, None, None,
        filename=page.filename if page else None, sheet_no=page.sheet_no if page else None,
        sheet_order=page.sheet_order if page else None, evidence=evidence,
        title="无脚号元件连接待审核", issue_type="recognition_gap",
        explanation="端子另一端接到的元件引脚在图面上没有脚号，无法由现有证据确定其身份。",
        recommended_action="在图纸上核对这些端子接入的元件引脚，并补充脚号或确认外部接线。")
