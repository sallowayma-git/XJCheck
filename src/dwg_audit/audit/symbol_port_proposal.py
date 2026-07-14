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

# Human adjudications are keyed exclusively by observed geometry fingerprint.
# Block names are deliberately not used as a fallback: the same name may have
# different geometry and semantics in another project/version.
HUMAN_SYMBOL_PORT_POLICIES: dict[str, dict[str, str]] = {
    # Numeric/text block; not an electrical symbol.
    "39b95b5118323d4d8ec235cb43fb72f9b99c8d90ce9f4b2027ee2bdda6255ed5": {
        "mode": "IGNORE_ELECTRICAL",
        "reason": "Human adjudication: numeric/text block, not an electrical symbol.",
    },
    # Graphical symbols that must not create electrical ports or bridges.
    "9a1c6d15833092f32027442d19bd52f5f384395b0bb113e252e5bfbfe66cb85b": {
        "mode": "IGNORE_ELECTRICAL",
        "reason": "Human adjudication: graphical symbol with no connectivity meaning.",
    },
    "a78b06f3c9ab76dc9d36aeecdecb3a32599dbbc55c0e186dbecce76a9ecc780b": {
        "mode": "IGNORE_ELECTRICAL",
        "reason": "Human adjudication: open electrical switch; its sides are disconnected.",
    },
    "634756a0bafe88dd763d740c97fe13dbbd65921586360b6f96a87d2dc2a408f4": {
        "mode": "IGNORE_ELECTRICAL",
        "reason": "Human adjudication: open electrical switch; its sides are disconnected.",
    },
    "b37828da29525da55540cc801a451c80b23b3b44b19cd00b7680ddfe1771f746": {
        "mode": "IGNORE_ELECTRICAL",
        "reason": "Human adjudication: functional conversion symbol, not part of wire connectivity.",
    },
    "cfe71411f229bb03fbcff9605b5b3dc0ace82f26b83a4d53fee308559e04412d": {
        "mode": "IGNORE_ELECTRICAL",
        "reason": "Human adjudication: non-connective device graphic in the left-side equipment area.",
    },
    "4843ab10418b48bf18e403125a6c80ba490c88d0987c42f712b5c24c8503dc61": {
        "mode": "IGNORE_ELECTRICAL",
        "reason": "Human adjudication: line-break/omission symbol; its sides are disconnected.",
    },
    # KLP has independently useful external ports but no conductive path
    # through the body. Each port is bound to its own adjacent wire only.
    "61255c39029679e1151d9d4e8fe3884a538ea97638fa6f605d8a1d17713d8dc2": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "reason": "Human adjudication: KLP ports attach to adjacent external wires only.",
    },
    "2ede8a4fcebd958209b99a25e477726c0b55f86b32d00650130a89acad0bf89c": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "e2e32701027b07d3f74b5941716ca9328daf926abad92f0b4b5f2081b3f52fe2": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "b3115ea33fe4e1b57d4cfa6394c3125c42f5776b589f8297b4053cf3d7a7a073": {
        "mode": "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY",
        "reason": "Human adjudication: generic terminal; the text above is its terminal designator.",
    },
    "69f5c09b9bfe7e7c3c9db62eaa577a51b98801ec22bb366b8d5d2513ae1b247b": {
        "mode": "EXTERNAL_PORTS_NO_INTERNAL_CONNECTIVITY",
        "reason": "Human adjudication: strip two-port component; each port maps to its own external endpoint.",
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
    """Apply a reviewed non-connectivity policy to a shadow proposal row."""

    row = dict(proposal)
    policy = human_symbol_port_policy(row.get("definition_fingerprint"))
    if policy is None:
        return row
    row["human_adjudication_mode"] = policy["mode"]
    row["human_adjudication_reason"] = policy["reason"]
    row["internal_connectivity_inferred"] = False
    row["electrical_union_eligible"] = False
    if policy["mode"] == "IGNORE_ELECTRICAL":
        row["ports"] = []
        row["status"] = "HUMAN_ADJUDICATED_NON_CONNECTIVE"
    return row


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
    ports, geometry_summary, notes = propose_ports_from_segments(
        segments,
        source_id=source_id,
        max_ports=max_ports,
    )
    geometry_summary = {
        **geometry_summary,
        "entity_counts": entity_counts,
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
    label_radius: float = 3.5,
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

    networks_by_handle: dict[str, set[str]] = defaultdict(set)
    for row in member_rows:
        if str(row.get("member_type") or "") != "SOURCE_LINE":
            continue
        handle = str(row.get("source_handle") or "").strip()
        network_id = str(row.get("electrical_network_id") or "").strip()
        if handle and network_id:
            networks_by_handle[handle].add(network_id)

    proposals_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in proposal_rows:
        file_id = str(row.get("file_id") or "").strip()
        name = str(row.get("definition_name") or "").strip()
        if file_id and name and row.get("ports"):
            proposals_by_key[(file_id, name.casefold())].append(row)

    numeric_label = re.compile(r"^[0-9]{1,3}$")
    terminal_designator = re.compile(
        r"^(?:[0-9]+[A-Za-z][A-Za-z0-9-]*|[A-Za-z]+[0-9][A-Za-z0-9-]*)$"
    )
    candidates: list[dict[str, Any]] = []
    for instance in instance_rows:
        file_id = str(instance.get("file_id") or "").strip()
        sheet_id = str(instance.get("sheet_id") or "").strip()
        name = str(instance.get("definition_name") or "").strip()
        instance_id = str(instance.get("symbol_instance_id") or "").strip()
        instance_handle = str(instance.get("entity_handle") or "").strip()
        policy = human_symbol_port_policy(instance.get("definition_fingerprint"))
        labelled_terminal = bool(
            policy
            and policy["mode"] == "LABELLED_TERMINAL_NO_INTERNAL_CONNECTIVITY"
        )
        matching = proposals_by_key.get((file_id, name.casefold()), [])
        if len(matching) != 1:
            continue
        matrix = _instance_matrix(instance.get("transform_json"))
        if matrix is None:
            continue
        ports = [
            dict(row)
            for row in matching[0].get("ports") or []
            if isinstance(row, Mapping)
        ]
        world_ports: list[tuple[float, float, float]] = []
        for port in ports:
            local = port.get("local_position") or []
            if not isinstance(local, Sequence) or len(local) < 2:
                world_ports.append((math.nan, math.nan, math.nan))
                continue
            world_ports.append(
                _transform_point(
                    matrix,
                    (
                        float(local[0]),
                        float(local[1]),
                        float(local[2]) if len(local) > 2 else 0.0,
                    ),
                )
            )

        eligible_texts: list[tuple[str, float, float, dict[str, Any]]] = []
        terminal_labels: list[tuple[float, str, dict[str, Any]]] = []
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
        bound_terminal = terminal_labels[0] if terminal_labels and terminal_labels[0][0] <= label_radius * 2.0 else None

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
        for port_index, (port, world) in enumerate(zip(ports, world_ports)):
            if not math.isfinite(world[0]) or not math.isfinite(world[1]):
                continue
            attached_lines: list[dict[str, Any]] = []
            for line in sheet_lines:
                try:
                    start = (float(line.get("start_x")), float(line.get("start_y")))
                    end = (float(line.get("end_x")), float(line.get("end_y")))
                except (TypeError, ValueError):
                    continue
                if min(
                    math.hypot(world[0] - start[0], world[1] - start[1]),
                    math.hypot(world[0] - end[0], world[1] - end[1]),
                ) <= endpoint_tolerance:
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
            if network_ids:
                evidence_codes.append("EXTERNAL_NETWORK_MEMBERSHIP")
            if terminal_name and line_handles:
                status = "MEASURED_TERMINAL_ATTACHMENT"
                confidence = 0.9 if network_ids else 0.85
            elif explicit_label and line_handles:
                status = "MEASURED_EXTERNAL_ATTACHMENT"
                confidence = 0.95 if network_ids else 0.9
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
                    "machine_port_id": port.get("port_id"),
                    "explicit_port_label": explicit_label,
                    "terminal_designator": terminal_name,
                    "terminal_label_handle": terminal_label_row.get("handle") if terminal_label_row else None,
                    "terminal_label_text_id": terminal_label_row.get("text_id") if terminal_label_row else None,
                    "label_handle": label_row.get("handle") if label_row else None,
                    "label_text_id": label_row.get("text_id") if label_row else None,
                    "label_distance": label_distance_value,
                    "local_position": list(port.get("local_position") or []),
                    "world_position": [world[0], world[1], world[2]],
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
    "extract_block_segments",
    "find_block_in_documents",
    "human_symbol_port_policy",
    "propose_ports_for_queue_row",
    "propose_ports_from_block",
    "propose_ports_from_segments",
    "write_human_review_checklist",
    "write_machine_proposed_review_pack",
]
