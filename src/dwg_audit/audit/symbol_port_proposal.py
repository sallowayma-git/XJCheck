"""Geometry-driven MACHINE_PROPOSED symbol port candidates.

Proposals are fail-closed draft annotations only:
- port / symbol annotation_status = MACHINE_PROPOSED
- registry_status remains UNKNOWN
- critical_issue_eligible remains false
- connectivity groups stay UNKNOWN / MACHINE_PROPOSED

They never count as human confirmation and cannot flip primary_engine.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROPOSAL_SCHEMA_VERSION = "symbol-port-proposal-v1"
SOURCE_KIND = "machine_geometry_proposal"
FAMILY_CLASSIFICATION_VERSION = "symbol-family-classification-v1"
BEHAVIOR_POLICY_VERSION = "symbol-behavior-policy-v1"
GEOMETRY_IGNORE_FAMILIES = frozenset(
    {
        "non_electrical.numeric_text.v1",
        "non_electrical.graphic.v1",
        "non_electrical.functional_graphic.v1",
        "non_electrical.equipment_graphic.v1",
        "non_electrical.placeholder.v1",
        "switch.open.v1",
        "line_break.non_connective.v1",
    }
)

# Human adjudications are keyed exclusively by observed geometry fingerprint.
# Block names are deliberately not used as a fallback: the same name may have
# different geometry and semantics in another project/version.
HUMAN_SYMBOL_PORT_POLICIES: dict[str, dict[str, str]] = {
    # Numeric/text block; not an electrical symbol.
    "39b95b5118323d4d8ec235cb43fb72f9b99c8d90ce9f4b2027ee2bdda6255ed5": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.numeric_text.v1",
        "reason": "Human adjudication: numeric/text block, not an electrical symbol.",
    },
    # Graphical symbols that must not create electrical ports or bridges.
    "9a1c6d15833092f32027442d19bd52f5f384395b0bb113e252e5bfbfe66cb85b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.graphic.v1",
        "reason": "Human adjudication: graphical symbol with no connectivity meaning.",
    },
    "a78b06f3c9ab76dc9d36aeecdecb3a32599dbbc55c0e186dbecce76a9ecc780b": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "switch.open.v1",
        "reason": "Human adjudication: open electrical switch; its sides are disconnected.",
    },
    "634756a0bafe88dd763d740c97fe13dbbd65921586360b6f96a87d2dc2a408f4": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "switch.open.v1",
        "reason": "Human adjudication: open electrical switch; its sides are disconnected.",
    },
    "b37828da29525da55540cc801a451c80b23b3b44b19cd00b7680ddfe1771f746": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.functional_graphic.v1",
        "reason": "Human adjudication: functional conversion symbol, not part of wire connectivity.",
    },
    "cfe71411f229bb03fbcff9605b5b3dc0ace82f26b83a4d53fee308559e04412d": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.equipment_graphic.v1",
        "reason": "Human adjudication: non-connective device graphic in the left-side equipment area.",
    },
    "ef9845390ad82463e1efac6f04551d65d189a6d9a311ce8c2b1398021e70c7cc": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "non_electrical.placeholder.v1",
        "reason": "Human adjudication: no actual electrical meaning.",
    },
    "4843ab10418b48bf18e403125a6c80ba490c88d0987c42f712b5c24c8503dc61": {
        "mode": "IGNORE_ELECTRICAL",
        "family_id": "line_break.non_connective.v1",
        "reason": "Human adjudication: line-break/omission symbol; its sides are disconnected.",
    },
    # KLP has independently useful external ports but no conductive path
    # through the body. Each port is bound to its own adjacent wire only.
    "61255c39029679e1151d9d4e8fe3884a538ea97638fa6f605d8a1d17713d8dc2": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_inline_two_port.v1",
        "reason": "Human adjudication: KLP ports attach to adjacent external wires only.",
    },
    "2ede8a4fcebd958209b99a25e477726c0b55f86b32d00650130a89acad0bf89c": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "5f5573087fee9f48a503ecdede638903fcb979dd5031aaf1e98e69d07f2707f8": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "03db302eda788e4107a4dc2e882e6da52af3d56ea388d8a8f5789e6892a52211": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "cce15b281bc0c0ef0df95453bffcd991d28e73e7683a513b4c3e5f979c243438": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "c578f4c57480a4eabf4f0affb3ac93a9ca7e3eef23ca67e810605b48f06ac99b": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "e2e32701027b07d3f74b5941716ca9328daf926abad92f0b4b5f2081b3f52fe2": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "b3115ea33fe4e1b57d4cfa6394c3125c42f5776b589f8297b4053cf3d7a7a073": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "family_id": "labelled_terminal.generic.v1",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "69f5c09b9bfe7e7c3c9db62eaa577a51b98801ec22bb366b8d5d2513ae1b247b": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_strip_two_port.v1",
        "reason": "Human adjudication: strip two-port component; each port maps to its own external endpoint.",
    },
    "e84d37eab1d5e64b04de0e6aae32137b3ae80676267d6e24e71266aa4b9e7ee9": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: multi-port component; each port maps to its own external endpoint.",
    },
    "835a7dcc7eae596a7b1a600a48f0e579bf800a22b1add1ffbcc44d2ddb95e054": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "family_id": "component.external_multi_port.v1",
        "reason": "Human adjudication: multi-port component; each port maps to its own external endpoint.",
    },
}


def human_symbol_port_policy(fingerprint: str | None) -> dict[str, str] | None:
    """Return an exact-fingerprint human policy, never a name-based guess."""

    if not fingerprint:
        return None
    return HUMAN_SYMBOL_PORT_POLICIES.get(str(fingerprint).strip().casefold())


def apply_human_symbol_policy_to_proposal_row(
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach family/policy evidence while preserving exact human overrides."""

    row = dict(proposal)
    policy = human_symbol_port_policy(row.get("definition_fingerprint"))
    family = classify_definition_family(row)
    behavior = evaluate_symbol_behavior(family, reviewed_policy=policy)
    row.update(family)
    row.update(behavior)
    row["internal_connectivity_inferred"] = False
    row["electrical_union_eligible"] = False
    row["critical_issue_eligible"] = False
    if policy is not None:
        row["human_adjudication_mode"] = policy["mode"]
        row["human_adjudication_reason"] = policy["reason"]
    if behavior["suppressed_by_policy"]:
        row["ports"] = []
        row["status"] = (
            "HUMAN_ADJUDICATED_NON_CONNECTIVE"
            if policy is not None and policy["mode"] == "IGNORE_ELECTRICAL"
            else "GEOMETRY_FAMILY_NON_CONNECTIVE"
        )
    return row


def is_high_confidence_terminal_geometry(proposal: Mapping[str, Any]) -> bool:
    """Recognize compact arc-body terminal geometry without using block names.

    Geometry alone is not enough to emit a terminal relation. Callers must also
    bind a structured terminal designator and an external line contact.
    """

    summary = proposal.get("geometry_summary")
    if not isinstance(summary, Mapping):
        return False
    shape = summary.get("shape_features")
    if not isinstance(shape, Mapping):
        return False
    try:
        arc_radii = [float(value) for value in shape.get("arc_radii", [])]
        primitive_count = int(shape.get("primitive_count", 0))
        text_count = int(shape.get("text_count", 0))
        width = float(shape.get("width"))
        height = float(shape.get("height"))
    except (TypeError, ValueError):
        return False
    if len(arc_radii) != 2 or any(radius <= 0.0 for radius in arc_radii):
        return False
    mean_radius = sum(arc_radii) / len(arc_radii)
    radius_spread = max(arc_radii) - min(arc_radii)
    invariant_size = max(width, height)
    return (
        radius_spread <= mean_radius * 0.05
        and 0.0 < invariant_size / mean_radius <= 5.2
        and primitive_count <= 12
        and text_count == 0
    )


def classify_definition_family(
    proposal: Mapping[str, Any],
    *,
    fingerprint: str | None = None,
) -> dict[str, Any]:
    """Classify a definition into a versioned family without granting authority."""

    observed_fingerprint = str(
        fingerprint or proposal.get("definition_fingerprint") or ""
    ).strip()
    reviewed_policy = human_symbol_port_policy(observed_fingerprint)
    summary = proposal.get("geometry_summary")
    shape = summary.get("shape_features") if isinstance(summary, Mapping) else None
    shape = shape if isinstance(shape, Mapping) else {}
    ports = [item for item in proposal.get("ports") or [] if isinstance(item, Mapping)]
    try:
        width = float(shape.get("width", 0.0))
        height = float(shape.get("height", 0.0))
        primitive_count = int(shape.get("primitive_count", 0))
        arc_count = len(shape.get("arc_radii") or [])
        circle_count = len(shape.get("circle_radii") or [])
    except (TypeError, ValueError):
        width = height = 0.0
        primitive_count = arc_count = circle_count = 0
    short_side = min(width, height)
    aspect_ratio = (
        max(width, height) / short_side if short_side > 1e-9 else 0.0
    )

    ignore_match = _match_confirmed_ignore_geometry_family(
        shape, port_count=len(ports), aspect_ratio=aspect_ratio
    )
    machine_family: str | None = ignore_match[0] if ignore_match else None
    matched_rule_id: str | None = ignore_match[1] if ignore_match else None
    classifier_status = "MATCHED" if ignore_match else "UNKNOWN"
    confidence = ignore_match[2] if ignore_match else 0.0
    if machine_family is None and is_high_confidence_terminal_geometry(proposal):
        machine_family = "labelled_terminal.generic.v1"
        matched_rule_id = "compact-equal-arc-terminal-v1"
        classifier_status = "MATCHED"
        confidence = 0.9
    elif machine_family is None and len(ports) >= 4 and primitive_count >= 16 and max(width, height) > 0.0:
        machine_family = "component.external_multi_port.v1"
        matched_rule_id = "repeated-external-port-geometry-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.75
    elif machine_family is None and (
        len(ports) == 2
        and aspect_ratio >= 4.0
        and arc_count + circle_count >= 2
    ):
        machine_family = "component.external_strip_two_port.v1"
        matched_rule_id = "elongated-round-end-two-port-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.7
    elif machine_family is None and len(ports) == 2 and aspect_ratio >= 4.0 and arc_count == 0:
        machine_family = "switch.open.candidate.v1"
        matched_rule_id = "elongated-gap-two-port-candidate-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.4
    elif machine_family is None and len(ports) == 2 and arc_count >= 4:
        machine_family = "line_break.non_connective.candidate.v1"
        matched_rule_id = "multi-arc-line-break-candidate-v1"
        classifier_status = "REVIEW_REQUIRED"
        confidence = 0.45

    reviewed_family = reviewed_policy.get("family_id") if reviewed_policy else None
    family_id = machine_family or reviewed_family
    source = "MACHINE_GEOMETRY_RULE" if machine_family else "UNKNOWN"
    if reviewed_family:
        source = (
            "MACHINE_GEOMETRY_RULE+HUMAN_EXACT_MEMBER"
            if machine_family == reviewed_family
            else "HUMAN_EXACT_MEMBER"
        )
        family_id = reviewed_family
        classifier_status = "HUMAN_CONFIRMED_MEMBER"
        confidence = 1.0
        matched_rule_id = matched_rule_id or "human-exact-member-v1"

    return {
        "family_schema_version": FAMILY_CLASSIFICATION_VERSION,
        "family_id": family_id,
        "family_version": "1" if family_id else None,
        "classifier_status": classifier_status,
        "classifier_confidence": confidence,
        "matched_family_rule_id": matched_rule_id,
        "family_evidence_source": source,
        "fingerprint_version": "local-geometry-fingerprint-v1",
        "exact_human_member": bool(reviewed_policy),
        "authority": "SHADOW_ONLY",
    }


def _match_confirmed_ignore_geometry_family(
    shape: Mapping[str, Any],
    *,
    port_count: int,
    aspect_ratio: float,
) -> tuple[str, str, float] | None:
    """Match confirmed non-connective families using normalized geometry only."""

    primitive_histogram = shape.get("primitive_histogram")
    entity_histogram = shape.get("entity_histogram")
    primitive_histogram = (
        primitive_histogram if isinstance(primitive_histogram, Mapping) else {}
    )
    entity_histogram = entity_histogram if isinstance(entity_histogram, Mapping) else {}

    def count(name: str) -> int:
        try:
            return int(entity_histogram.get(name, primitive_histogram.get(name, 0)))
        except (TypeError, ValueError):
            return 0

    arc_radii = [
        float(value)
        for value in shape.get("arc_radii") or []
        if isinstance(value, (int, float)) and float(value) > 0.0
    ]
    circle_count = len(shape.get("circle_radii") or [])
    short_side = min(float(shape.get("width") or 0.0), float(shape.get("height") or 0.0))
    normalized_arc_radius = (
        sum(arc_radii) / len(arc_radii) / short_side
        if arc_radii and short_side > 1e-9
        else 0.0
    )

    if (
        port_count == 2
        and not arc_radii
        and circle_count == 0
        and count("LINE") == 1
        and 5 <= count("LWPOLYLINE") <= 7
        and 2.0 <= aspect_ratio <= 2.8
    ):
        return (
            "non_electrical.numeric_text.v1",
            "confirmed-numeric-text-geometry-v1",
            0.95,
        )
    if (
        port_count >= 3
        and count("HATCH") >= 1
        and 10 <= count("LINE") <= 16
        and 2 <= count("LWPOLYLINE") <= 4
        and 1.0 <= aspect_ratio <= 1.4
    ):
        return (
            "non_electrical.graphic.v1",
            "confirmed-hatched-nonconnective-geometry-v1",
            0.96,
        )
    if (
        port_count == 2
        and not arc_radii
        and circle_count == 0
        and 3 <= count("LINE") <= 4
        and count("LWPOLYLINE") == 2
        and 5.5 <= aspect_ratio <= 7.5
    ):
        return ("switch.open.v1", "confirmed-open-switch-geometry-v1", 0.97)
    if (
        port_count >= 4
        and count("TEXT") >= 2
        and count("LINE") <= 2
        and 2 <= count("LWPOLYLINE") <= 4
        and 1.0 <= aspect_ratio <= 1.3
    ):
        return (
            "non_electrical.functional_graphic.v1",
            "confirmed-functional-graphic-geometry-v1",
            0.96,
        )
    if (
        port_count == 2
        and len(arc_radii) == 2
        and count("LINE") in {2, 3, 4}
        and count("LWPOLYLINE") in {2, 3}
        and 3.0 <= aspect_ratio <= 4.2
        and 0.45 <= normalized_arc_radius <= 0.6
    ):
        return (
            "non_electrical.equipment_graphic.v1",
            "confirmed-tall-equipment-graphic-geometry-v1",
            0.95,
        )
    if (
        port_count == 2
        and not arc_radii
        and circle_count == 0
        and 1 <= count("LINE") <= 3
        and 2 <= count("LWPOLYLINE") <= 4
        and 1.4 <= aspect_ratio <= 1.9
    ):
        return (
            "non_electrical.placeholder.v1",
            "confirmed-placeholder-geometry-v1",
            0.93,
        )
    if (
        port_count == 2
        and len(arc_radii) == 4
        and count("LWPOLYLINE") == 2
        and count("LINE") == 0
        and aspect_ratio >= 8.0
    ):
        return (
            "line_break.non_connective.v1",
            "confirmed-line-break-geometry-v1",
            0.98,
        )
    return None


def evaluate_symbol_behavior(
    family: Mapping[str, Any],
    *,
    reviewed_policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert family evidence into fail-closed behavior flags."""

    family_id = str(family.get("family_id") or "")
    reviewed_mode = str((reviewed_policy or {}).get("mode") or "")
    exact_ignore = reviewed_mode == "IGNORE_ELECTRICAL"
    geometry_ignore = bool(
        family_id in GEOMETRY_IGNORE_FAMILIES
        and family.get("classifier_status") == "MATCHED"
        and str(family.get("family_evidence_source") or "").startswith(
            "MACHINE_GEOMETRY_RULE"
        )
    )
    ignore = exact_ignore or geometry_ignore
    external_only = family_id.startswith("component.external_")
    terminal = family_id.startswith("labelled_terminal.")
    behavior_mode = (
        "IGNORE"
        if ignore
        else "TERMINAL_NO_INTERNAL"
        if terminal
        else "EXTERNAL_PORTS_ONLY"
        if external_only
        else "REVIEW_ONLY"
    )
    allow_ports = bool((terminal or external_only) and not ignore)
    return {
        "behavior_policy_version": BEHAVIOR_POLICY_VERSION,
        "behavior_mode": behavior_mode,
        "allow_port_emission": allow_ports,
        "allow_external_attachment": allow_ports,
        "allow_internal_connectivity": False,
        "allow_electrical_union": False,
        "allow_critical_issue": False,
        "suppressed_by_policy": ignore,
        "decision_reason_codes": [
            "HUMAN_EXACT_IGNORE_POLICY"
            if exact_ignore
            else "GEOMETRY_IGNORE_FAMILY_MATCH"
            if geometry_ignore
            else "FAMILY_EXTERNAL_ONLY_NO_INTERNAL"
            if external_only
            else "FAMILY_TERMINAL_NO_INTERNAL"
            if terminal
            else "MACHINE_FAMILY_REVIEW_ONLY"
        ],
        "authority": "SHADOW_ONLY",
    }


@dataclass(frozen=True, slots=True)
class ProposedPort:
    port_id: str
    local_position: tuple[float, float, float]
    outward_direction: tuple[float, float, float]
    port_type: str
    confidence: float
    evidence_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    notes: str | None = None

    def to_review_port(self) -> dict[str, Any]:
        return {
            "port_id": self.port_id,
            "local_position": list(self.local_position),
            "outward_direction": list(self.outward_direction),
            "port_type": self.port_type,
            "aliases": [],
            "source_ids": list(self.source_ids),
            "annotation_status": "MACHINE_PROPOSED",
        }

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["local_position"] = list(self.local_position)
        value["outward_direction"] = list(self.outward_direction)
        value["evidence_codes"] = list(self.evidence_codes)
        value["source_ids"] = list(self.source_ids)
        return value


@dataclass(frozen=True, slots=True)
class SymbolPortProposal:
    definition_name: str
    definition_fingerprint: str | None
    source_dxf: str | None
    ports: tuple[ProposedPort, ...]
    method: str
    status: str
    notes: tuple[str, ...] = ()
    geometry_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PROPOSAL_SCHEMA_VERSION,
            "definition_name": self.definition_name,
            "definition_fingerprint": self.definition_fingerprint,
            "source_dxf": self.source_dxf,
            "method": self.method,
            "status": self.status,
            "notes": list(self.notes),
            "geometry_summary": self.geometry_summary or {},
            "ports": [port.to_dict() for port in self.ports],
        }


def _round_point(point: tuple[float, float], digits: int = 4) -> tuple[float, float]:
    return (round(float(point[0]), digits), round(float(point[1]), digits))


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _normalize(vector: tuple[float, float]) -> tuple[float, float, float]:
    x, y = vector
    norm = math.hypot(x, y)
    if norm <= 1e-12:
        return (1.0, 0.0, 0.0)
    return (x / norm, y / norm, 0.0)


def _cluster_points(
    points: Sequence[tuple[float, float]],
    *,
    eps: float = 0.15,
) -> list[tuple[float, float]]:
    clusters: list[list[tuple[float, float]]] = []
    for point in points:
        placed = False
        for cluster in clusters:
            cx = sum(item[0] for item in cluster) / len(cluster)
            cy = sum(item[1] for item in cluster) / len(cluster)
            if _distance(point, (cx, cy)) <= eps:
                cluster.append(point)
                placed = True
                break
        if not placed:
            clusters.append([point])
    centroids: list[tuple[float, float]] = []
    for cluster in clusters:
        centroids.append(
            (
                sum(item[0] for item in cluster) / len(cluster),
                sum(item[1] for item in cluster) / len(cluster),
            )
        )
    return centroids


def extract_block_segments(block: Any) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], dict[str, int]]:
    """Return wire-like segments and entity-type counts from a block layout."""

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    counts: Counter[str] = Counter()
    try:
        entities = list(block)
    except Exception:
        return [], {}
    for entity in entities:
        try:
            entity_type = str(entity.dxftype() or "").upper()
        except Exception:
            continue
        counts[entity_type] += 1
        try:
            if entity_type == "LINE":
                start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
                segments.append((start, end))
            elif entity_type == "LWPOLYLINE":
                points = [
                    (float(point[0]), float(point[1]))
                    for point in entity.get_points("xy")
                ]
                for left, right in zip(points, points[1:]):
                    segments.append((left, right))
                if len(points) > 1 and bool(getattr(entity, "closed", False)):
                    segments.append((points[-1], points[0]))
            elif entity_type == "POLYLINE":
                points = []
                for vertex in entity.vertices:
                    try:
                        location = vertex.dxf.location
                        points.append((float(location.x), float(location.y)))
                    except Exception:
                        continue
                for left, right in zip(points, points[1:]):
                    segments.append((left, right))
                if len(points) > 1 and bool(getattr(entity, "is_closed", False)):
                    segments.append((points[-1], points[0]))
            elif entity_type == "ARC":
                center = (float(entity.dxf.center.x), float(entity.dxf.center.y))
                radius = float(entity.dxf.radius)
                start_angle = math.radians(float(entity.dxf.start_angle))
                end_angle = math.radians(float(entity.dxf.end_angle))
                start = (
                    center[0] + radius * math.cos(start_angle),
                    center[1] + radius * math.sin(start_angle),
                )
                end = (
                    center[0] + radius * math.cos(end_angle),
                    center[1] + radius * math.sin(end_angle),
                )
                segments.append((start, end))
            elif entity_type == "CIRCLE":
                # Circles alone do not create wire ports; skip.
                continue
        except Exception:
            continue
    return segments, dict(sorted(counts.items()))


def extract_block_shape_features(block: Any) -> dict[str, Any]:
    """Extract name-independent local geometry features for safe classification."""

    try:
        entities = list(block)
    except Exception:
        return {
            "arc_radii": [],
            "circle_radii": [],
            "primitive_count": 0,
            "primitive_histogram": {},
            "entity_histogram": {},
            "text_count": 0,
            "width": 0.0,
            "height": 0.0,
        }

    points: list[tuple[float, float]] = []
    arc_radii: list[float] = []
    circle_radii: list[float] = []
    primitive_count = 0
    primitive_histogram: Counter[str] = Counter()
    entity_histogram: Counter[str] = Counter()
    text_count = 0
    primitive_types = {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE"}
    text_types = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}

    def add_point(x: Any, y: Any) -> None:
        try:
            px = float(x)
            py = float(y)
        except (TypeError, ValueError):
            return
        if math.isfinite(px) and math.isfinite(py):
            points.append((px, py))

    def angle_on_arc(angle: float, start: float, end: float) -> bool:
        sweep = (end - start) % 360.0
        offset = (angle - start) % 360.0
        return offset <= sweep + 1e-9

    for entity in entities:
        try:
            entity_type = str(entity.dxftype() or "").upper()
        except Exception:
            continue
        entity_histogram[entity_type] += 1
        if entity_type in text_types:
            text_count += 1
        if entity_type not in primitive_types:
            continue
        primitive_count += 1
        primitive_histogram[entity_type] += 1
        try:
            if entity_type == "LINE":
                add_point(entity.dxf.start.x, entity.dxf.start.y)
                add_point(entity.dxf.end.x, entity.dxf.end.y)
            elif entity_type == "LWPOLYLINE":
                for point in entity.get_points("xy"):
                    add_point(point[0], point[1])
            elif entity_type == "POLYLINE":
                for vertex in entity.vertices:
                    location = vertex.dxf.location
                    add_point(location.x, location.y)
            elif entity_type == "ARC":
                cx = float(entity.dxf.center.x)
                cy = float(entity.dxf.center.y)
                radius = float(entity.dxf.radius)
                start = float(entity.dxf.start_angle) % 360.0
                end = float(entity.dxf.end_angle) % 360.0
                if radius > 0.0 and math.isfinite(radius):
                    arc_radii.append(radius)
                    for angle in (start, end, 0.0, 90.0, 180.0, 270.0):
                        if angle in (start, end) or angle_on_arc(angle, start, end):
                            radians = math.radians(angle)
                            add_point(
                                cx + radius * math.cos(radians),
                                cy + radius * math.sin(radians),
                            )
            elif entity_type == "CIRCLE":
                cx = float(entity.dxf.center.x)
                cy = float(entity.dxf.center.y)
                radius = float(entity.dxf.radius)
                if radius > 0.0 and math.isfinite(radius):
                    circle_radii.append(radius)
                    add_point(cx - radius, cy)
                    add_point(cx + radius, cy)
                    add_point(cx, cy - radius)
                    add_point(cx, cy + radius)
        except Exception:
            continue

    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
    else:
        width = 0.0
        height = 0.0
    return {
        "arc_radii": sorted(round(radius, 6) for radius in arc_radii),
        "circle_radii": sorted(round(radius, 6) for radius in circle_radii),
        "primitive_count": primitive_count,
        "primitive_histogram": dict(sorted(primitive_histogram.items())),
        "entity_histogram": dict(sorted(entity_histogram.items())),
        "text_count": text_count,
        "width": round(width, 6),
        "height": round(height, 6),
    }


def propose_ports_from_segments(
    segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
    *,
    source_id: str,
    max_ports: int = 4,
    cluster_eps: float = 0.2,
) -> tuple[list[ProposedPort], dict[str, Any], tuple[str, ...]]:
    """Propose electrical ports from free endpoints of wire-like geometry."""

    notes: list[str] = []
    if not segments:
        return [], {"segment_count": 0}, ("NO_SEGMENTS",)

    endpoint_hits: list[tuple[float, float]] = []
    adjacency: dict[tuple[float, float], list[tuple[float, float]]] = defaultdict(list)
    for start, end in segments:
        s = _round_point(start)
        e = _round_point(end)
        endpoint_hits.append(s)
        endpoint_hits.append(e)
        if s != e:
            adjacency[s].append(e)
            adjacency[e].append(s)

    degree = Counter(endpoint_hits)
    free_points = [point for point, count in degree.items() if count == 1]
    if not free_points:
        # Fall back to geometric extremes of all endpoints.
        free_points = list(degree.keys())
        notes.append("No degree-1 free endpoints; using geometric extremes.")

    clustered = _cluster_points(free_points, eps=cluster_eps)
    if not clustered:
        return [], {"segment_count": len(segments)}, ("NO_CLUSTERED_POINTS",)

    xs = [point[0] for point in clustered]
    ys = [point[1] for point in clustered]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    horizontal = width >= height

    def extremity_score(point: tuple[float, float]) -> float:
        if horizontal:
            return abs(point[0] - cx) + 0.15 * abs(point[1] - cy)
        return abs(point[1] - cy) + 0.15 * abs(point[0] - cx)

    ranked = sorted(clustered, key=extremity_score, reverse=True)

    # Repeated full-width rows are a stronger multi-port signal than raw bbox
    # aspect. This excludes decorative/mechanical free ends inside the symbol.
    selected: list[tuple[float, float]] = []
    paired_row_points: set[tuple[float, float]] = set()
    selected_complete_rows = False
    row_groups: list[list[tuple[float, float]]] = []
    for point in sorted(clustered, key=lambda item: (item[1], item[0])):
        for group in row_groups:
            mean_y = sum(item[1] for item in group) / len(group)
            if abs(point[1] - mean_y) <= cluster_eps:
                group.append(point)
                break
        else:
            row_groups.append([point])
    full_width_rows: list[tuple[float, tuple[float, float], tuple[float, float]]] = []
    if horizontal and width > 1e-6:
        edge_tolerance = max(cluster_eps * 2.0, width * 0.05)
        for group in row_groups:
            left = min(group, key=lambda item: item[0])
            right = max(group, key=lambda item: item[0])
            if (
                right[0] - left[0] >= width * 0.8
                and left[0] <= min_x + edge_tolerance
                and right[0] >= max_x - edge_tolerance
            ):
                full_width_rows.append(
                    (sum(item[1] for item in group) / len(group), left, right)
                )
    if max_ports >= 4 and len(full_width_rows) >= 2:
        for _, left, right in sorted(full_width_rows, key=lambda item: item[0]):
            for point in (left, right):
                if len(selected) >= max_ports:
                    break
                if all(_distance(point, existing) > cluster_eps for existing in selected):
                    selected.append(point)
                    paired_row_points.add(point)
            if len(selected) >= max_ports:
                break
        notes.append(
            "Selected paired full-width row endpoints for repeated multi-port geometry."
        )
        selected_complete_rows = True
    elif horizontal and width > 1e-6:
        left = min(clustered, key=lambda point: (point[0], abs(point[1] - cy)))
        right = max(clustered, key=lambda point: (point[0], -abs(point[1] - cy)))
        selected = [left, right]
        notes.append("Selected left/right extremes for horizontal schematic symbol.")
    elif height > 1e-6:
        bottom = min(clustered, key=lambda point: (point[1], abs(point[0] - cx)))
        top = max(clustered, key=lambda point: (point[1], -abs(point[0] - cx)))
        selected = [bottom, top]
        notes.append("Selected bottom/top extremes for vertical schematic symbol.")
    else:
        selected = ranked[: max(1, min(max_ports, 2))]
        notes.append("Degenerate bbox; selected ranked free endpoints.")

    # Only expand beyond 2 ports when free endpoints form a clearly 2D terminal
    # pattern (near-square spread). Elongated series symbols stay 2-port.
    aspect = (
        max(width, height) / min(width, height)
        if min(width, height) > 1e-6
        else 999.0
    )
    multi_terminal = max_ports > 2 and aspect <= 1.6
    if selected_complete_rows or len(selected) >= max_ports:
        pass
    elif multi_terminal:
        axis_extremes = [
            min(clustered, key=lambda point: (point[0], point[1])),
            max(clustered, key=lambda point: (point[0], -point[1])),
            min(clustered, key=lambda point: (point[1], point[0])),
            max(clustered, key=lambda point: (point[1], -point[0])),
        ]
        for point in axis_extremes:
            if len(selected) >= max_ports:
                break
            if all(_distance(point, existing) > cluster_eps for existing in selected):
                selected.append(point)
        notes.append("Expanded to multi-terminal extremes due to near-square free-end spread.")
    elif max_ports > 2:
        notes.append("Kept 2-port principal-axis proposal for elongated schematic symbol.")




    ports: list[ProposedPort] = []
    for index, point in enumerate(selected, start=1):
        # Outward direction: away from centroid; refine using attached neighbor if any.
        rounded = _round_point(point)
        neighbors = adjacency.get(rounded) or []
        if neighbors:
            # Average neighbor vector, then invert for outward.
            nx = sum(neighbor[0] - point[0] for neighbor in neighbors) / len(neighbors)
            ny = sum(neighbor[1] - point[1] for neighbor in neighbors) / len(neighbors)
            outward = _normalize((-nx, -ny))
            evidence = ("FREE_ENDPOINT", "OUTWARD_FROM_ATTACHED_SEGMENT")
        else:
            outward = _normalize((point[0] - cx, point[1] - cy))
            evidence = ("GEOMETRIC_EXTREME", "OUTWARD_FROM_CENTROID")
        if point in paired_row_points:
            evidence = (*evidence, "REPEATED_FULL_WIDTH_ROW_PORT")
        confidence = 0.55 if "FREE_ENDPOINT" in evidence else 0.4
        if len(selected) == 2:
            confidence += 0.15
        if "REPEATED_FULL_WIDTH_ROW_PORT" in evidence:
            confidence += 0.15
        ports.append(
            ProposedPort(
                port_id=f"MP{index}",
                local_position=(float(point[0]), float(point[1]), 0.0),
                outward_direction=outward,
                port_type="ELECTRICAL",
                confidence=min(confidence, 0.85),
                evidence_codes=evidence,
                source_ids=(source_id,),
                notes="Machine geometry proposal; requires human confirmation.",
            )
        )

    summary = {
        "segment_count": len(segments),
        "unique_endpoint_count": len(degree),
        "free_endpoint_count": len(free_points),
        "clustered_candidate_count": len(clustered),
        "bbox": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "width": width,
            "height": height,
        },
        "principal_axis": "horizontal" if horizontal else "vertical",
        "centroid": {"x": cx, "y": cy},
        "selected_port_count": len(ports),
    }
    return ports, summary, tuple(notes)


def propose_ports_from_block(
    block: Any,
    *,
    definition_name: str,
    definition_fingerprint: str | None = None,
    source_dxf: str | Path | None = None,
    max_ports: int = 4,
) -> SymbolPortProposal:
    source_id = f"{SOURCE_KIND}:{definition_name}"
    name_key = definition_name.casefold()
    if any(token in name_key for token in ("title", "border", "frame", "图框", "标题")):
        return SymbolPortProposal(
            definition_name=definition_name,
            definition_fingerprint=definition_fingerprint,
            source_dxf=str(source_dxf) if source_dxf is not None else None,
            ports=(),
            method="free_endpoint_extremes_v1",
            status="SKIPPED_NON_ELECTRICAL",
            notes=("Definition name looks like title/border geometry; no electrical ports proposed.",),
            geometry_summary={"skip_reason": "title_or_border_name"},
        )
    segments, entity_counts = extract_block_segments(block)
    shape_features = extract_block_shape_features(block)
    ports, geometry_summary, notes = propose_ports_from_segments(
        segments,
        source_id=source_id,
        max_ports=max_ports,
    )
    geometry_summary = {
        **geometry_summary,
        "entity_counts": entity_counts,
        "shape_features": shape_features,
    }
    status = "PROPOSED" if ports else "EMPTY"
    return SymbolPortProposal(
        definition_name=definition_name,
        definition_fingerprint=definition_fingerprint,
        source_dxf=str(source_dxf) if source_dxf is not None else None,
        ports=tuple(ports),
        method="free_endpoint_extremes_v1",
        status=status,
        notes=notes,
        geometry_summary=geometry_summary,
    )


def build_instance_port_network_candidates(
    definition_proposals: Any,
    instances: Any,
    texts: Any,
    lines: Any,
    network_members: Any,
    *,
    component_pairs: Any = None,
    label_radius: float = 3.5,
    component_label_radius: float = 25.0,
    terminal_label_ambiguity_tolerance: float = 0.5,
    endpoint_tolerance: float = 0.05,
) -> list[dict[str, Any]]:
    """Bind definition ports to instance labels and external networks.

    The result is shadow-only and never infers conductivity through a symbol.
    """

    proposal_rows = _mapping_rows(definition_proposals)
    instance_rows = _mapping_rows(instances)
    text_rows = _mapping_rows(texts)
    line_rows = _mapping_rows(lines)
    member_rows = _mapping_rows(network_members)
    component_pair_rows = _mapping_rows(component_pairs)

    networks_by_handle: dict[str, set[str]] = defaultdict(set)
    for row in member_rows:
        if str(row.get("member_type") or "") != "SOURCE_LINE":
            continue
        handle = str(row.get("source_handle") or "").strip()
        network_id = str(row.get("electrical_network_id") or "").strip()
        if handle and network_id:
            networks_by_handle[handle].add(network_id)

    component_mapping_by_port: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in component_pair_rows:
        if str(row.get("pair_kind") or "") != "component_mapping":
            continue
        sheet_key = str(row.get("sheet_id") or "").strip()
        port_key = str(row.get("left_value") or "").strip()
        endpoint = str(row.get("right_value") or "").strip()
        if sheet_key and port_key and endpoint:
            component_mapping_by_port[(sheet_key, port_key)].append(row)

    proposals_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    proposals_by_fingerprint: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in proposal_rows:
        file_id = str(row.get("file_id") or "").strip()
        name = str(row.get("definition_name") or "").strip()
        if file_id and name and row.get("ports"):
            proposals_by_key[(file_id, name.casefold())].append(row)
            fingerprint = str(row.get("definition_fingerprint") or "").strip().casefold()
            if fingerprint:
                proposals_by_fingerprint[(file_id, fingerprint)].append(row)

    numeric_label = re.compile(r"^[0-9]{1,3}$")
    terminal_designator = re.compile(
        r"^(?:[0-9]+[A-Za-z][A-Za-z0-9-]*|[A-Za-z]+[0-9][A-Za-z0-9-]*)$"
    )
    component_designator = re.compile(r"^\d+(?:-\d+)?[A-Za-z]{1,5}\d*$")
    candidates: list[dict[str, Any]] = []
    for instance in instance_rows:
        file_id = str(instance.get("file_id") or "").strip()
        sheet_id = str(instance.get("sheet_id") or "").strip()
        name = str(instance.get("definition_name") or "").strip()
        instance_id = str(instance.get("symbol_instance_id") or "").strip()
        instance_handle = str(instance.get("entity_handle") or "").strip()
        instance_fingerprint = str(
            instance.get("definition_fingerprint") or ""
        ).strip().casefold()
        policy = human_symbol_port_policy(instance_fingerprint)
        name_matching = proposals_by_key.get((file_id, name.casefold()), [])
        matching = (
            proposals_by_fingerprint.get((file_id, instance_fingerprint), [])
            if instance_fingerprint
            else []
        )
        binding_status = "FINGERPRINT_EXACT"
        if not matching:
            unversioned = [
                row
                for row in name_matching
                if not str(row.get("definition_fingerprint") or "").strip()
            ]
            conflicting = [
                row
                for row in name_matching
                if str(row.get("definition_fingerprint") or "").strip()
                and str(row.get("definition_fingerprint") or "").strip().casefold()
                != instance_fingerprint
            ]
            if instance_fingerprint and conflicting and not unversioned:
                candidates.append(
                    {
                        "schema_version": "symbol-port-network-candidate-v1",
                        "candidate_id": f"SPNC:{instance_id or instance_handle}:BINDING",
                        "project_id": instance.get("project_id"),
                        "sheet_id": sheet_id,
                        "file_id": file_id,
                        "symbol_instance_id": instance_id or None,
                        "symbol_instance_handle": instance_handle or None,
                        "definition_name": name,
                        "definition_fingerprint": instance.get("definition_fingerprint"),
                        "proposal_fingerprints": sorted(
                            {
                                str(row.get("definition_fingerprint") or "")
                                for row in conflicting
                            }
                        ),
                        "binding_status": "REJECTED_FINGERPRINT_MISMATCH",
                        "relation_kind": "PROPOSAL_TO_INSTANCE_BINDING",
                        "status": "REJECTED_FINGERPRINT_MISMATCH",
                        "confidence": 0.0,
                        "evidence_codes": ["DEFINITION_FINGERPRINT_MISMATCH"],
                        "annotation_status": "MACHINE_PROPOSED",
                        "authority": "SHADOW_ONLY",
                        "shadow_only": True,
                        "internal_connectivity_inferred": False,
                        "electrical_union_eligible": False,
                        "critical_issue_eligible": False,
                    }
                )
                continue
            matching = unversioned if unversioned else name_matching
            binding_status = (
                "LEGACY_NAME_FALLBACK_UNVERIFIED"
                if matching
                else "UNRESOLVED"
            )
        if len(matching) != 1:
            continue
        family = classify_definition_family(
            matching[0], fingerprint=instance_fingerprint or None
        )
        behavior = evaluate_symbol_behavior(family, reviewed_policy=policy)
        family_id = str(family.get("family_id") or "")
        if behavior.get("suppressed_by_policy"):
            continue
        terminal_geometry = is_high_confidence_terminal_geometry(matching[0])
        labelled_terminal = family_id.startswith("labelled_terminal.")
        component_port_model = family_id.startswith("component.external_")
        matrix = _instance_matrix(instance.get("transform_json"))
        if matrix is None:
            continue
        ports = [
            dict(row)
            for row in matching[0].get("ports") or []
            if isinstance(row, Mapping)
        ]
        world_ports: list[tuple[float, float, float]] = []
        world_outward_directions: list[tuple[float, float] | None] = []
        for port in ports:
            local = port.get("local_position") or []
            if not isinstance(local, Sequence) or len(local) < 2:
                world_ports.append((math.nan, math.nan, math.nan))
                world_outward_directions.append(None)
                continue
            local_point = (
                float(local[0]),
                float(local[1]),
                float(local[2]) if len(local) > 2 else 0.0,
            )
            world = _transform_point(matrix, local_point)
            world_ports.append(world)
            outward = port.get("outward_direction") or []
            if isinstance(outward, Sequence) and len(outward) >= 2:
                local_tip = (
                    local_point[0] + float(outward[0]),
                    local_point[1] + float(outward[1]),
                    local_point[2] + (float(outward[2]) if len(outward) > 2 else 0.0),
                )
                world_tip = _transform_point(matrix, local_tip)
                dx = world_tip[0] - world[0]
                dy = world_tip[1] - world[1]
                norm = math.hypot(dx, dy)
                world_outward_directions.append(
                    (dx / norm, dy / norm) if norm > 1e-12 else None
                )
            else:
                world_outward_directions.append(None)

        effective_endpoint_tolerance = endpoint_tolerance
        if terminal_geometry:
            shape = matching[0].get("geometry_summary", {}).get("shape_features", {})
            radii = [
                float(value)
                for value in shape.get("arc_radii", [])
                if isinstance(value, (int, float)) and float(value) > 0.0
            ]
            if radii:
                origin = _transform_point(matrix, (0.0, 0.0, 0.0))
                unit_x = _transform_point(matrix, (1.0, 0.0, 0.0))
                unit_y = _transform_point(matrix, (0.0, 1.0, 0.0))
                scale = max(
                    math.hypot(unit_x[0] - origin[0], unit_x[1] - origin[1]),
                    math.hypot(unit_y[0] - origin[0], unit_y[1] - origin[1]),
                )
                effective_endpoint_tolerance = max(
                    endpoint_tolerance,
                    (sum(radii) / len(radii)) * scale * 0.08,
                )

        eligible_texts: list[tuple[str, float, float, dict[str, Any]]] = []
        terminal_labels: list[tuple[float, str, dict[str, Any]]] = []
        component_labels: list[tuple[float, str, dict[str, Any]]] = []
        for text_row in text_rows:
            if str(text_row.get("sheet_id") or "") != sheet_id:
                continue
            if file_id and str(text_row.get("file_id") or "") != file_id:
                continue
            value = str(
                text_row.get("normalized_text") or text_row.get("text") or ""
            ).strip()
            try:
                x = float(text_row.get("insert_x"))
                y = float(text_row.get("insert_y"))
            except (TypeError, ValueError):
                continue
            if labelled_terminal and terminal_designator.fullmatch(value):
                terminal_labels.append((0.0, value, text_row))
            if component_port_model and component_designator.fullmatch(value):
                component_labels.append((0.0, value, text_row))
            if numeric_label.fullmatch(value):
                eligible_texts.append((value, x, y, text_row))

        if labelled_terminal:
            center = _transform_point(matrix, (0.0, 0.0, 0.0))
            terminal_labels = sorted(
                [
                    (
                        math.hypot(center[0] - float(row.get("insert_x")), center[1] - float(row.get("insert_y"))),
                        value,
                        row,
                    )
                    for _, value, row in terminal_labels
                ],
                key=lambda item: (item[0], item[1]),
            )
        terminal_labels_in_range = [
            item for item in terminal_labels if item[0] <= label_radius * 2.0
        ]
        nearest_terminal_by_value: dict[str, tuple[float, str, dict[str, Any]]] = {}
        for item in terminal_labels_in_range:
            nearest_terminal_by_value.setdefault(item[1], item)
        distinct_terminal_labels = sorted(
            nearest_terminal_by_value.values(), key=lambda item: (item[0], item[1])
        )
        terminal_label_ambiguous = bool(
            len(distinct_terminal_labels) > 1
            and distinct_terminal_labels[1][0] - distinct_terminal_labels[0][0]
            <= terminal_label_ambiguity_tolerance
        )
        bound_terminal = (
            distinct_terminal_labels[0]
            if distinct_terminal_labels and not terminal_label_ambiguous
            else None
        )
        if component_port_model:
            center = _transform_point(matrix, (0.0, 0.0, 0.0))
            component_labels = sorted(
                [
                    (
                        math.hypot(center[0] - float(row.get("insert_x")), center[1] - float(row.get("insert_y"))),
                        value,
                        row,
                    )
                    for _, value, row in component_labels
                ],
                key=lambda item: (item[0], item[1]),
            )
        component_label = (
            component_labels[0]
            if component_labels and component_labels[0][0] <= component_label_radius
            else None
        )

        label_pairs: list[tuple[float, int, int]] = []
        for port_index, world in enumerate(world_ports):
            if not math.isfinite(world[0]) or not math.isfinite(world[1]):
                continue
            for text_index, (_, x, y, _) in enumerate(eligible_texts):
                distance = math.hypot(world[0] - x, world[1] - y)
                if distance <= label_radius:
                    label_pairs.append((distance, port_index, text_index))
        assigned_labels: dict[
            int, tuple[float, tuple[str, float, float, dict[str, Any]]]
        ] = {}
        used_texts: set[int] = set()
        for distance, port_index, text_index in sorted(label_pairs):
            if port_index in assigned_labels or text_index in used_texts:
                continue
            assigned_labels[port_index] = (distance, eligible_texts[text_index])
            used_texts.add(text_index)

        sheet_lines = [
            row
            for row in line_rows
            if str(row.get("sheet_id") or "") == sheet_id
            and (not file_id or str(row.get("file_id") or "") == file_id)
        ]
        for port_index, (port, world, outward) in enumerate(
            zip(ports, world_ports, world_outward_directions)
        ):
            if not math.isfinite(world[0]) or not math.isfinite(world[1]):
                continue
            attached_lines: list[dict[str, Any]] = []
            for line in sheet_lines:
                try:
                    start = (float(line.get("start_x")), float(line.get("start_y")))
                    end = (float(line.get("end_x")), float(line.get("end_y")))
                except (TypeError, ValueError):
                    continue
                start_distance = math.hypot(world[0] - start[0], world[1] - start[1])
                end_distance = math.hypot(world[0] - end[0], world[1] - end[1])
                if min(start_distance, end_distance) > effective_endpoint_tolerance:
                    continue
                if terminal_geometry and outward is not None:
                    away = (
                        (end[0] - start[0], end[1] - start[1])
                        if start_distance <= end_distance
                        else (start[0] - end[0], start[1] - end[1])
                    )
                    away_norm = math.hypot(away[0], away[1])
                    if away_norm <= 1e-12:
                        continue
                    alignment = (
                        outward[0] * away[0] + outward[1] * away[1]
                    ) / away_norm
                    if alignment < 0.5:
                        continue
                attached_lines.append(line)

            label_binding = assigned_labels.get(port_index)
            explicit_label = label_binding[1][0] if label_binding else None
            label_row = label_binding[1][3] if label_binding else None
            label_distance_value = label_binding[0] if label_binding else None
            terminal_name = bound_terminal[1] if bound_terminal else None
            terminal_label_row = bound_terminal[2] if bound_terminal else None
            line_handles = sorted(
                {
                    str(row.get("handle") or "").strip()
                    for row in attached_lines
                    if str(row.get("handle") or "").strip()
                }
            )
            line_ids = sorted(
                {
                    str(row.get("line_id") or "").strip()
                    for row in attached_lines
                    if str(row.get("line_id") or "").strip()
                }
            )
            network_ids = sorted(
                {
                    network_id
                    for handle in line_handles
                    for network_id in networks_by_handle.get(handle, set())
                }
            )
            evidence_codes = ["DEFINITION_PORT_WORLD_TRANSFORM"]
            if explicit_label:
                evidence_codes.append("INSTANCE_LOCAL_NUMERIC_PORT_LABEL")
            if line_handles:
                evidence_codes.append("EXACT_EXTERNAL_LINE_ENDPOINT")
                if terminal_geometry and outward is not None:
                    evidence_codes.append("OUTWARD_LINE_ALIGNMENT")
            if network_ids:
                evidence_codes.append("EXTERNAL_NETWORK_MEMBERSHIP")
            terminal_model = (
                "HUMAN_CONFIRMED"
                if policy and policy["mode"] == "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY"
                else "GEOMETRY_HIGH_CONFIDENCE"
                if terminal_geometry
                else None
            )
            terminal_definition_evidence = bool(labelled_terminal)
            terminal_label_evidence = bool(terminal_name)
            terminal_wire_evidence = bool(line_handles)
            terminal_independent_evidence_complete = bool(
                terminal_definition_evidence
                and terminal_label_evidence
                and terminal_wire_evidence
                and not terminal_label_ambiguous
            )
            terminal_missing_evidence: list[str] = []
            if labelled_terminal:
                if not terminal_label_evidence:
                    terminal_missing_evidence.append("UNIQUE_STRUCTURED_DESIGNATOR")
                if not terminal_wire_evidence:
                    terminal_missing_evidence.append("EXTERNAL_WIRE_CONTACT")
            component_port_identity = (
                f"{component_label[1]}-{explicit_label}"
                if component_label and explicit_label
                else None
            )
            component_mappings = (
                component_mapping_by_port.get((sheet_id, component_port_identity), [])
                if component_port_identity
                else []
            )
            component_endpoints = sorted(
                {
                    str(row.get("right_value") or "").strip()
                    for row in component_mappings
                }
                - {""}
            )
            component_pair_ids = sorted(
                {
                    str(row.get("pair_id") or "").strip()
                    for row in component_mappings
                }
                - {""}
            )
            if labelled_terminal and terminal_label_ambiguous:
                status = "TERMINAL_BINDING_AMBIGUOUS"
                confidence = 0.4
            elif terminal_independent_evidence_complete:
                status = "MEASURED_TERMINAL_ATTACHMENT"
                confidence = 0.95 if terminal_model == "HUMAN_CONFIRMED" and network_ids else 0.9 if network_ids else 0.85
            elif labelled_terminal and terminal_label_evidence:
                status = "TERMINAL_LABEL_ONLY_REVIEW"
                confidence = 0.65
            elif labelled_terminal and terminal_wire_evidence:
                status = "TERMINAL_WIRE_ONLY_REVIEW"
                confidence = 0.6
            elif labelled_terminal:
                status = "TERMINAL_GEOMETRY_ONLY_REVIEW"
                confidence = 0.5
            elif explicit_label and line_handles:
                status = "MEASURED_EXTERNAL_ATTACHMENT"
                confidence = 0.95 if network_ids else 0.9
            elif component_endpoints:
                status = "MEASURED_COMPONENT_PORT_MAPPING"
                confidence = 0.95
            elif explicit_label:
                status = "LABEL_ONLY_REVIEW"
                confidence = 0.65
            elif line_handles:
                status = "GEOMETRY_ONLY_REVIEW"
                confidence = 0.6
            else:
                status = "UNRESOLVED"
                confidence = 0.0
            candidates.append(
                {
                    "schema_version": "symbol-port-network-candidate-v1",
                    "candidate_id": (
                        f"SPNC:{instance_id or instance_handle}:"
                        f"{explicit_label or port.get('port_id') or port_index}"
                    ),
                    "project_id": instance.get("project_id"),
                    "sheet_id": sheet_id,
                    "file_id": file_id,
                    "symbol_instance_id": instance_id or None,
                    "symbol_instance_handle": instance_handle or None,
                    "definition_name": name,
                    "definition_fingerprint": instance.get("definition_fingerprint"),
                    "binding_status": binding_status,
                    **family,
                    **behavior,
                    "machine_port_id": port.get("port_id"),
                    "explicit_port_label": explicit_label,
                    "terminal_designator": terminal_name,
                    "terminal_model": terminal_model,
                    "terminal_geometry_recognized": terminal_geometry,
                    "terminal_definition_evidence": terminal_definition_evidence,
                    "terminal_label_evidence": terminal_label_evidence,
                    "terminal_wire_evidence": terminal_wire_evidence,
                    "terminal_independent_evidence_complete": terminal_independent_evidence_complete,
                    "terminal_label_ambiguous": terminal_label_ambiguous,
                    "terminal_label_candidates": [
                        {
                            "value": value,
                            "distance": distance,
                            "text_id": row.get("text_id"),
                            "handle": row.get("handle"),
                        }
                        for distance, value, row in distinct_terminal_labels
                    ],
                    "terminal_missing_evidence": terminal_missing_evidence,
                    "terminal_label_handle": terminal_label_row.get("handle") if terminal_label_row else None,
                    "terminal_label_text_id": terminal_label_row.get("text_id") if terminal_label_row else None,
                    "component_designator": component_label[1] if component_label else None,
                    "component_designator_text_id": component_label[2].get("text_id") if component_label else None,
                    "component_port_identity": component_port_identity,
                    "component_mapping_external_endpoints": component_endpoints,
                    "component_mapping_pair_ids": component_pair_ids,
                    "cross_page_match_eligible": bool(component_endpoints),
                    "label_handle": label_row.get("handle") if label_row else None,
                    "label_text_id": label_row.get("text_id") if label_row else None,
                    "label_distance": label_distance_value,
                    "local_position": list(port.get("local_position") or []),
                    "world_position": [world[0], world[1], world[2]],
                    "effective_endpoint_tolerance": effective_endpoint_tolerance,
                    "attached_line_ids": line_ids,
                    "attached_line_handles": line_handles,
                    "external_network_ids": network_ids,
                    "relation_kind": "PORT_TO_EXTERNAL_NETWORK",
                    "status": status,
                    "confidence": confidence,
                    "evidence_codes": evidence_codes,
                    "internal_connectivity_inferred": False,
                    "dynamic_contact_state": "DEFER",
                    "annotation_status": "MACHINE_PROPOSED",
                    "authority": "SHADOW_ONLY",
                    "shadow_only": True,
                    "electrical_union_eligible": False,
                    "critical_issue_eligible": False,
                }
            )
    candidates.sort(
        key=lambda row: (
            str(row.get("sheet_id") or ""),
            str(row.get("symbol_instance_id") or ""),
            str(row.get("explicit_port_label") or row.get("machine_port_id") or ""),
        )
    )
    return candidates


def summarize_instance_port_network_candidates(candidates: Any) -> dict[str, Any]:
    """Summarize independent terminal evidence without granting authority."""

    rows = _mapping_rows(candidates)
    status_counts = Counter(str(row.get("status") or "UNRESOLVED") for row in rows)
    family_counts = Counter(str(row.get("family_id") or "UNKNOWN") for row in rows)
    binding_status_counts = Counter(
        str(row.get("binding_status") or "UNVERIFIED") for row in rows
    )
    behavior_mode_counts = Counter(
        str(row.get("behavior_mode") or "UNSPECIFIED") for row in rows
    )
    return {
        "schema_version": "symbol-port-network-candidate-summary-v1",
        "candidate_count": len(rows),
        "measured_external_attachment_count": status_counts.get(
            "MEASURED_EXTERNAL_ATTACHMENT", 0
        ),
        "measured_terminal_attachment_count": status_counts.get(
            "MEASURED_TERMINAL_ATTACHMENT", 0
        ),
        "measured_component_port_mapping_count": status_counts.get(
            "MEASURED_COMPONENT_PORT_MAPPING", 0
        ),
        "terminal_geometry_recognized_count": sum(
            bool(row.get("terminal_geometry_recognized")) for row in rows
        ),
        "independent_evidence_complete_count": sum(
            bool(row.get("terminal_independent_evidence_complete")) for row in rows
        ),
        "ambiguous_binding_count": sum(
            bool(row.get("terminal_label_ambiguous")) for row in rows
        ),
        "terminal_review_only_count": sum(
            str(row.get("status") or "").startswith("TERMINAL_")
            and row.get("status") != "MEASURED_TERMINAL_ATTACHMENT"
            for row in rows
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "binding_status_counts": dict(sorted(binding_status_counts.items())),
        "behavior_mode_counts": dict(sorted(behavior_mode_counts.items())),
        "rejected_fingerprint_mismatch_count": binding_status_counts.get(
            "REJECTED_FINGERPRINT_MISMATCH", 0
        ),
        "geometry_family_match_count": sum(
            str(row.get("family_evidence_source") or "").startswith(
                "MACHINE_GEOMETRY_RULE"
            )
            for row in rows
        ),
        "exact_human_member_count": sum(
            bool(row.get("exact_human_member")) for row in rows
        ),
        "explicit_label_count": sum(bool(row.get("explicit_port_label")) for row in rows),
        "network_bound_count": sum(bool(row.get("external_network_ids")) for row in rows),
        "internal_connectivity_inferred_count": sum(
            bool(row.get("internal_connectivity_inferred")) for row in rows
        ),
        "authority": "SHADOW_ONLY",
        "electrical_union_eligible_count": sum(
            bool(row.get("electrical_union_eligible")) for row in rows
        ),
        "critical_issue_eligible_count": sum(
            bool(row.get("critical_issue_eligible")) for row in rows
        ),
        "primary_engine_unchanged": True,
    }


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "iterrows"):
        return [dict(row) for _, row in value.iterrows()]
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        rows = []
        for item in value:
            if isinstance(item, Mapping):
                rows.append(dict(item))
            elif hasattr(item, "__dataclass_fields__"):
                rows.append(asdict(item))
        return rows
    return []


def _instance_matrix(raw: Any) -> list[list[float]] | None:
    payload = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, Mapping):
        return None
    matrix = payload.get("matrix44")
    chain = payload.get("chain")
    if matrix is None and isinstance(chain, Sequence) and chain:
        first = chain[0]
        if isinstance(first, Mapping):
            matrix = first.get("matrix44") or first.get("matrix")
    if not isinstance(matrix, Sequence):
        return None
    try:
        rows = [[float(cell) for cell in row] for row in matrix]
    except (TypeError, ValueError):
        return None
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        return None
    return rows


def _transform_point(
    matrix: list[list[float]], point: tuple[float, float, float]
) -> tuple[float, float, float]:
    x, y, z = point
    if (
        abs(matrix[3][3] - 1.0) <= 1e-9
        and abs(matrix[0][3]) <= 1e-9
        and abs(matrix[1][3]) <= 1e-9
    ):
        return (
            matrix[0][0] * x + matrix[1][0] * y + matrix[2][0] * z + matrix[3][0],
            matrix[0][1] * x + matrix[1][1] * y + matrix[2][1] * z + matrix[3][1],
            matrix[0][2] * x + matrix[1][2] * y + matrix[2][2] * z + matrix[3][2],
        )
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )



def find_block_in_documents(
    definition_names: Sequence[str],
    dxf_paths: Sequence[str | Path],
) -> tuple[Any, str, Path] | None:
    """Return first matching (block, name, path) for any definition name."""

    try:
        import ezdxf
    except Exception:
        return None
    wanted = {str(name).casefold(): str(name) for name in definition_names if str(name).strip()}
    if not wanted:
        return None
    for raw_path in dxf_paths:
        path = Path(raw_path)
        if not path.is_file():
            continue
        try:
            document = ezdxf.readfile(str(path))
        except Exception:
            continue
        try:
            block_names = {str(block.name): block for block in document.blocks}
        except Exception:
            continue
        for key, original in wanted.items():
            for block_name, block in block_names.items():
                if str(block_name).casefold() == key:
                    try:
                        if bool(getattr(block, "is_any_layout", False)):
                            continue
                    except Exception:
                        pass
                    return block, original, path
    return None


def propose_ports_for_queue_row(
    row: Mapping[str, Any],
    dxf_paths: Sequence[str | Path],
    *,
    max_ports: int = 4,
) -> SymbolPortProposal:
    names = row.get("definition_names") or []
    if isinstance(names, str):
        names = [part for part in names.split("|") if part]
    names = [str(name) for name in names if str(name).strip()]
    fingerprint = str(row.get("definition_fingerprint") or "") or None
    match = find_block_in_documents(names, dxf_paths)
    if match is None:
        return SymbolPortProposal(
            definition_name=names[0] if names else "UNKNOWN",
            definition_fingerprint=fingerprint,
            source_dxf=None,
            ports=(),
            method="free_endpoint_extremes_v1",
            status="BLOCK_NOT_FOUND",
            notes=("No matching block definition found in provided DXF set.",),
            geometry_summary={},
        )
    block, name, path = match
    return propose_ports_from_block(
        block,
        definition_name=name,
        definition_fingerprint=fingerprint,
        source_dxf=path,
        max_ports=max_ports,
    )


def apply_proposals_to_review_document(
    document: Mapping[str, Any],
    proposals_by_fingerprint: Mapping[str, SymbolPortProposal],
) -> dict[str, Any]:
    """Inject MACHINE_PROPOSED ports into a review document without authority."""

    payload = json.loads(json.dumps(document))  # deep copy via JSON
    symbols = payload.get("symbols")
    if not isinstance(symbols, list):
        return payload
    for symbol in symbols:
        if not isinstance(symbol, dict):
            continue
        fingerprint = str(symbol.get("fingerprint") or "")
        proposal = proposals_by_fingerprint.get(fingerprint)
        policy = human_symbol_port_policy(fingerprint)
        if proposal is None:
            continue
        if policy is not None and policy["mode"] == "IGNORE_ELECTRICAL":
            symbol["ports"] = []
            symbol["internal_connectivity_groups"] = []
            continue
        if not proposal.ports:
            continue
        source_id = f"{SOURCE_KIND}:{proposal.definition_name}"
        existing_sources = symbol.get("sources")
        if not isinstance(existing_sources, list):
            existing_sources = []
        if not any(
            isinstance(item, dict) and item.get("source_id") == source_id
            for item in existing_sources
        ):
            existing_sources.append(
                {
                    "source_id": source_id,
                    "source_kind": SOURCE_KIND,
                    "locator": proposal.source_dxf or proposal.definition_name,
                    "project_id": None,
                    "held_out": False,
                }
            )
        symbol["sources"] = existing_sources
        symbol["ports"] = [port.to_review_port() for port in proposal.ports]
        # Keep symbol-level status non-authoritative.
        symbol["annotation_status"] = "MACHINE_PROPOSED"
        symbol["registry_status"] = "UNKNOWN"
        symbol["critical_issue_eligible"] = False
        # A two-port geometry alone cannot establish conductivity. Human review
        # can explicitly suppress the old review-only series placeholder.
        if (
            len(proposal.ports) == 2
            and not (
                policy is not None
                and policy["mode"] in {
                    "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
                    "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
                }
            )
        ):
            symbol["internal_connectivity_groups"] = [
                {
                    "group_id": "MP_SERIES",
                    "port_ids": [proposal.ports[0].port_id, proposal.ports[1].port_id],
                    "state": "POSSIBLE",
                    "annotation_status": "MACHINE_PROPOSED",
                    "source_ids": [source_id],
                }
            ]
        else:
            symbol["internal_connectivity_groups"] = []
        review = symbol.get("review")
        if not isinstance(review, dict):
            review = {}
        # Pending review metadata must remain empty per review safety contract.
        # Machine notes live on workflow / proposal artifacts, not reviewer fields.
        review.update(
            {
                "status": "PENDING_HUMAN_REVIEW",
                "reviewer": None,
                "reviewed_at": None,
                "evidence_source_ids": [],
                "notes": None,
            }
        )
        symbol["review"] = review

    workflow = payload.get("review_workflow")
    if isinstance(workflow, dict):
        workflow["document_status"] = "PENDING_HUMAN_REVIEW"
        notes = workflow.get("notes")
        prefix = "Contains MACHINE_PROPOSED ports from geometry; not human-confirmed."
        workflow["notes"] = prefix if not notes else f"{notes} | {prefix}"
    return payload


def write_human_review_checklist(
    *,
    proposals: Sequence[Mapping[str, Any] | SymbolPortProposal],
    draft_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Write a human checklist for MACHINE_PROPOSED drafts (never auto-confirm)."""

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    draft_display = str(draft_path)
    lines = [
        "# Human Port Review Checklist (Machine Draft)",
        "",
        "These ports are **MACHINE_PROPOSED** from DXF block geometry.",
        "They are **not** human-confirmed and **cannot** flip `primary_engine`.",
        "",
        f"Draft document: `{draft_display}`",
        "",
        "## How to confirm a symbol",
        "1. Open the matching DWG/DXF block and verify terminal locations.",
        "2. Edit the draft JSON for that symbol:",
        "   - set each accepted port `annotation_status` to `HUMAN_CONFIRMED`",
        "   - set symbol `annotation_status` to `HUMAN_CONFIRMED`",
        "   - set `registry_status` to `REGISTERED` only if identity is trusted",
        "   - set connectivity `state` to `ASSERTED` only with human confirmation",
        "   - fill `review.reviewer`, `review.reviewed_at` (ISO8601), `review.status=HUMAN_CONFIRMED`",
        "   - set document `review_workflow.document_status=REVIEW_COMPLETE`",
        "3. Run: `dwg-audit validate-symbol-review -i <edited.json>`",
        "4. Run: `dwg-audit promote-symbol-review -i <edited.json> -o configs/approved_symbol_library.json`",
        "",
        "## Proposed symbols",
        "",
    ]
    for item in proposals:
        row = item.to_dict() if isinstance(item, SymbolPortProposal) else dict(item)
        name = str(row.get("definition_name") or "UNKNOWN")
        fingerprint = str(row.get("definition_fingerprint") or "")
        short_fp = fingerprint[:16] if fingerprint else "no-fingerprint"
        status = str(row.get("status") or "UNKNOWN")
        lines.append(f"### {name} (`{short_fp}`)")
        lines.append(f"- status: `{status}`")
        if row.get("source_dxf"):
            lines.append(f"- source DXF: `{row.get('source_dxf')}`")
        if row.get("method"):
            lines.append(f"- method: `{row.get('method')}`")
        notes = row.get("notes") or []
        if notes:
            if isinstance(notes, str):
                notes_text = notes
            else:
                notes_text = "; ".join(str(note) for note in notes if str(note).strip())
            if notes_text:
                lines.append(f"- notes: {notes_text}")
        ports = list(row.get("ports") or [])
        if ports:
            lines.append("- ports:")
            for port in ports:
                pos = port.get("local_position") or []
                direction = port.get("outward_direction") or []
                conf = port.get("confidence")
                codes = port.get("evidence_codes") or []
                pos_text = (
                    f"({float(pos[0]):.3f},{float(pos[1]):.3f})"
                    if len(pos) >= 2
                    else str(pos)
                )
                dir_text = (
                    f"({float(direction[0]):.2f},{float(direction[1]):.2f})"
                    if len(direction) >= 2
                    else str(direction)
                )
                conf_text = f"{float(conf):.2f}" if conf is not None else "n/a"
                code_text = ",".join(str(code) for code in codes) if codes else ""
                lines.append(
                    f"  - `{port.get('port_id')}` pos={pos_text} dir={dir_text} "
                    f"conf={conf_text}"
                    + (f" codes={code_text}" if code_text else "")
                )
            if len(ports) == 2:
                lines.append(
                    "- connectivity draft: `MP_SERIES` state=`POSSIBLE` "
                    f"ports={[port.get('port_id') for port in ports]}"
                )
        lines.append("- human decision: [ ] confirm  [ ] edit  [ ] reject")
        lines.append("")

    lines.extend(
        [
            "## Gate reminder",
            "- MACHINE_PROPOSED drafts never authorize critical issues.",
            "- Held-out human gold + product approval remain required before "
            "`primary_engine` can leave `legacy`.",
            "",
        ]
    )
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def write_machine_proposed_review_pack(
    *,
    review_document_path: str | Path,
    dxf_paths: Sequence[str | Path],
    output_dir: str | Path,
    queue_rows: Sequence[Mapping[str, Any]] | None = None,
    max_ports: int = 4,
) -> dict[str, Any]:
    """Load a Top-N review template, propose ports from DXFs, write draft pack."""

    source_path = Path(review_document_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    document = json.loads(source_path.read_text(encoding="utf-8"))

    rows = list(queue_rows or [])
    if not rows:
        for symbol in document.get("symbols") or []:
            if isinstance(symbol, dict):
                rows.append(
                    {
                        "definition_fingerprint": symbol.get("fingerprint"),
                        "definition_names": symbol.get("definition_names") or [],
                    }
                )

    proposals: dict[str, SymbolPortProposal] = {}
    proposal_rows: list[dict[str, Any]] = []
    for row in rows:
        proposal = propose_ports_for_queue_row(row, dxf_paths, max_ports=max_ports)
        fingerprint = str(row.get("definition_fingerprint") or proposal.definition_fingerprint or "")
        if fingerprint:
            proposals[fingerprint] = proposal
        proposal_rows.append(proposal.to_dict())

    drafted = apply_proposals_to_review_document(document, proposals)
    draft_path = output / "symbol_review_machine_proposed.json"
    draft_path.write_text(
        json.dumps(drafted, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    proposals_path = output / "symbol_port_proposals.json"
    proposals_path.write_text(
        json.dumps(
            {
                "schema_version": PROPOSAL_SCHEMA_VERSION,
                "proposal_count": len(proposal_rows),
                "proposed_with_ports": sum(1 for row in proposal_rows if row.get("ports")),
                "block_not_found": sum(
                    1 for row in proposal_rows if row.get("status") == "BLOCK_NOT_FOUND"
                ),
                "proposals": proposal_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema_version": "symbol-port-proposal-summary-v1",
        "input_review_document": str(source_path),
        "draft_review_document": str(draft_path),
        "proposal_count": len(proposal_rows),
        "proposed_with_ports": sum(1 for row in proposal_rows if row.get("ports")),
        "block_not_found": sum(
            1 for row in proposal_rows if row.get("status") == "BLOCK_NOT_FOUND"
        ),
        "total_ports": sum(len(row.get("ports") or []) for row in proposal_rows),
        "authority": "MACHINE_PROPOSED_ONLY",
        "human_confirmed": False,
        "promotion_ready": False,
        "critical_issue_eligible_count": 0,
        "primary_engine_unchanged": True,
    }
    summary_path = output / "symbol_port_proposal_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    checklist_path = write_human_review_checklist(
        proposals=proposal_rows,
        draft_path=draft_path,
        output_path=output / "HUMAN_REVIEW_CHECKLIST.md",
    )
    return {
        "summary": summary,
        "draft_path": draft_path,
        "proposals_path": proposals_path,
        "summary_path": summary_path,
        "checklist_path": checklist_path,
        "proposals": proposals,
        "document": drafted,
    }


__all__ = [
    "PROPOSAL_SCHEMA_VERSION",
    "ProposedPort",
    "SymbolPortProposal",
    "apply_human_symbol_policy_to_proposal_row",
    "apply_proposals_to_review_document",
    "build_instance_port_network_candidates",
    "classify_definition_family",
    "evaluate_symbol_behavior",
    "extract_block_segments",
    "extract_block_shape_features",
    "find_block_in_documents",
    "human_symbol_port_policy",
    "is_high_confidence_terminal_geometry",
    "propose_ports_for_queue_row",
    "propose_ports_from_block",
    "propose_ports_from_segments",
    "summarize_instance_port_network_candidates",
    "write_human_review_checklist",
    "write_machine_proposed_review_pack",
]
