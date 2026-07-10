from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import uuid
from typing import Any

import pandas as pd

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import SheetRecord


_HORIZONTAL = "horizontal"
_VERTICAL = "vertical"
_SKIP_DISPOSITIONS = {"skip_stable", "classify_only"}
_ID_NAMESPACE = uuid.UUID("e652bb42-1a49-50cb-b099-02d7b4eb4d8c")

_NODE_COLUMNS = [
    "geometry_node_id",
    "sheet_id",
    "coord",
    "kind",
    "source_line_ids",
    "evidence_line_ids",
    "degree",
    "snap_offsets",
    "state",
]
_EDGE_COLUMNS = [
    "geometry_edge_id",
    "sheet_id",
    "source_line_id",
    "start_node_id",
    "end_node_id",
    "start_coord",
    "end_coord",
    "length",
    "state",
]
_COMPONENT_COLUMNS = [
    "geometry_component_id",
    "sheet_id",
    "node_ids",
    "edge_ids",
    "source_line_ids",
    "open_node_ids",
    "junction_node_ids",
    "degree_histogram",
    "bbox",
    "total_length",
]
_PAIR_CONTEXT_COLUMNS = [
    "pair_id",
    "sheet_id",
    "line_group_id",
    "pair_kind",
    "pair_status",
    "left_value",
    "right_value",
    "geometry_context_status",
    "geometry_component_ids",
    "matched_line_ids",
    "member_line_count",
    "geometry_component_count",
    "nearest_component_gap",
    "gap_observation_ids",
    "gap_states",
]
_OBSERVATION_COLUMNS = [
    "observation_id",
    "schema_version",
    "project_id",
    "sheet_id",
    "observation_kind",
    "state",
    "node_a_id",
    "node_b_id",
    "component_a_id",
    "component_b_id",
    "distance",
    "alignment_error",
    "source_line_ids",
    "evidence_ids",
    "reason_code",
    "requires_review",
]


@dataclass(frozen=True)
class _NormalizedLine:
    line: LineEntity
    orientation: str
    axis_start: float
    axis_end: float
    cross_axis: float
    start_point: tuple[float, float]
    end_point: tuple[float, float]


@dataclass(frozen=True)
class _SplitPoint:
    point_id: str
    line_id: str
    coord: tuple[float, float]
    kind: str
    evidence_line_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ConnectionMarker:
    coord: tuple[float, float]
    source_line_ids: tuple[str, ...]


class _UnionFind:
    def __init__(self, ids: list[str]) -> None:
        self._parent = {item: item for item in ids}
        self._rank = {item: 0 for item in ids}

    def find(self, item: str) -> str:
        parent = self._parent[item]
        if parent != item:
            self._parent[item] = self.find(parent)
        return self._parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self._rank[left_root] < self._rank[right_root]:
            left_root, right_root = right_root, left_root
        self._parent[right_root] = left_root
        if self._rank[left_root] == self._rank[right_root]:
            self._rank[left_root] += 1


def build_geometry_graph_frames(
    artifacts: ProjectArtifacts,
    *,
    config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build a geometry-only shadow graph without text or block bridges."""
    config = config or {}
    sheet_map = {sheet.sheet_id: sheet for sheet in artifacts.scan.pages}
    lines_by_sheet: dict[str, list[LineEntity]] = defaultdict(list)
    for line in artifacts.lines:
        if _line_in_scope(line, sheet_map.get(line.sheet_id)):
            lines_by_sheet[line.sheet_id].append(line)

    node_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    for sheet_id, lines in sorted(lines_by_sheet.items()):
        nodes, edges, components = _build_sheet_geometry_graph(
            sheet_id=sheet_id,
            lines=lines,
            config=config,
        )
        node_rows.extend(nodes)
        edge_rows.extend(edges)
        component_rows.extend(components)

    node_frame = pd.DataFrame(node_rows).reindex(columns=_NODE_COLUMNS)
    edge_frame = pd.DataFrame(edge_rows).reindex(columns=_EDGE_COLUMNS)
    component_frame = pd.DataFrame(component_rows).reindex(columns=_COMPONENT_COLUMNS)
    edge_count_by_source = defaultdict(int)
    for row in edge_rows:
        edge_count_by_source[row["source_line_id"]] += 1
    summary = {
        "geometry_node_count": len(node_frame),
        "geometry_edge_count": len(edge_frame),
        "geometry_component_count": len(component_frame),
        "geometry_open_node_count": sum(len(row["open_node_ids"]) for row in component_rows),
        "geometry_junction_node_count": sum(len(row["junction_node_ids"]) for row in component_rows),
        "geometry_source_line_count": len(edge_count_by_source),
        "split_source_line_count": sum(
            1 for edge_count in edge_count_by_source.values() if edge_count > 1
        ),
    }
    return node_frame, edge_frame, component_frame, summary


def build_pair_geometry_shadow_frame(
    artifacts: ProjectArtifacts,
    geometry_components: pd.DataFrame,
    geometry_observations: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Project legacy pair line groups onto geometry components without changing Pair truth."""
    components_by_line: dict[str, set[str]] = defaultdict(set)
    for _, row in geometry_components.iterrows():
        component_id = str(row["geometry_component_id"])
        for line_id in row.get("source_line_ids", []) or []:
            components_by_line[str(line_id)].add(component_id)
    groups_by_id = {
        group.line_group_id: group for group in artifacts.line_groups
    }
    gap_observations_by_components: dict[frozenset[str], list[dict[str, Any]]] = defaultdict(list)
    if geometry_observations is not None and not geometry_observations.empty:
        for _, observation in geometry_observations.iterrows():
            if observation.get("observation_kind") != "endpoint_gap":
                continue
            component_ids = frozenset(
                str(value)
                for value in (observation.get("component_a_id"), observation.get("component_b_id"))
                if value is not None and not pd.isna(value)
            )
            if len(component_ids) == 2:
                gap_observations_by_components[component_ids].append(observation.to_dict())

    rows: list[dict[str, Any]] = []
    for pair in artifacts.pairs:
        group = groups_by_id.get(pair.line_group_id)
        member_line_ids = [str(line_id) for line_id in (group.member_line_ids if group else [])]
        matched_line_ids = sorted(
            line_id for line_id in member_line_ids if components_by_line.get(line_id)
        )
        component_ids = sorted(
            {
                component_id
                for line_id in member_line_ids
                for component_id in components_by_line.get(line_id, set())
            }
        )
        if group is None:
            context_status = "no_line_group"
        elif not component_ids:
            context_status = "no_geometry_component"
        elif len(component_ids) == 1:
            context_status = "unique_geometry_component"
        else:
            context_status = "multiple_geometry_components"
        relevant_gaps: list[dict[str, Any]] = []
        component_set = set(component_ids)
        for key, observations in gap_observations_by_components.items():
            if key.issubset(component_set):
                relevant_gaps.extend(observations)
        rows.append(
            {
                "pair_id": pair.pair_id,
                "sheet_id": pair.sheet_id,
                "line_group_id": pair.line_group_id,
                "pair_kind": pair.pair_kind,
                "pair_status": pair.status,
                "left_value": pair.left_value,
                "right_value": pair.right_value,
                "geometry_context_status": context_status,
                "geometry_component_ids": component_ids,
                "matched_line_ids": matched_line_ids,
                "member_line_count": len(member_line_ids),
                "geometry_component_count": len(component_ids),
                "nearest_component_gap": (
                    min(float(item["distance"]) for item in relevant_gaps)
                    if relevant_gaps
                    else None
                ),
                "gap_observation_ids": sorted(
                    str(item["observation_id"]) for item in relevant_gaps
                ),
                "gap_states": sorted({str(item["state"]) for item in relevant_gaps}),
            }
        )

    frame = pd.DataFrame(rows).reindex(columns=_PAIR_CONTEXT_COLUMNS)
    ordinary = frame.loc[frame["pair_kind"] == "ordinary_pair"] if not frame.empty else frame
    status_counts = {
        status: int(count)
        for status, count in ordinary["geometry_context_status"].value_counts().sort_index().items()
    }
    ordinary_count = int(len(ordinary))
    unique_count = status_counts.get("unique_geometry_component", 0)
    summary = {
        "pair_count": int(len(frame)),
        "ordinary_pair_count": ordinary_count,
        "ordinary_geometry_context_status_counts": status_counts,
        "ordinary_unique_geometry_context_ratio": round(
            unique_count / ordinary_count if ordinary_count else 0.0,
            6,
        ),
    }
    return frame, summary


def build_geometry_observation_frame(
    artifacts: ProjectArtifacts,
    geometry_nodes: pd.DataFrame,
    geometry_edges: pd.DataFrame,
    geometry_components: pd.DataFrame,
    *,
    config: dict | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Retain asserted, possible, rejected and unknown geometry observations."""
    config = config or {}
    project_id = artifacts.scan.manifest.project_id
    topology = config.get("topology", {})
    possible_gap = float(topology.get("geometry_graph_possible_gap_tolerance", 25.0))
    alignment_tol = float(topology.get("geometry_graph_gap_alignment_tolerance", 0.25))

    rows: list[dict[str, Any]] = []
    component_by_node: dict[str, str] = {}
    for _, component in geometry_components.iterrows():
        for node_id in component.get("node_ids", []) or []:
            component_by_node[str(node_id)] = str(component["geometry_component_id"])

    edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, edge in geometry_edges.iterrows():
        edge_dict = edge.to_dict()
        edges_by_node[str(edge["start_node_id"])].append(edge_dict)
        edges_by_node[str(edge["end_node_id"])].append(edge_dict)

    for _, node in geometry_nodes.iterrows():
        if int(node.get("degree", 0)) < 2:
            continue
        node_id = str(node["geometry_node_id"])
        incident_edges = edges_by_node.get(node_id, [])
        rows.append(
            _observation_row(
                project_id=project_id,
                sheet_id=str(node["sheet_id"]),
                observation_kind="junction",
                state="ASSERTED",
                node_a_id=node_id,
                node_b_id=None,
                component_a_id=component_by_node.get(node_id),
                component_b_id=None,
                distance=0.0,
                alignment_error=0.0,
                source_line_ids=list(node.get("source_line_ids", []) or []),
                evidence_ids=list(node.get("evidence_line_ids", []) or []),
                reason_code=f"asserted_{node.get('kind', 'junction')}_v1",
                requires_review=False,
            )
        )

    open_nodes = [
        node.to_dict()
        for _, node in geometry_nodes.iterrows()
        if int(node.get("degree", 0)) == 1
    ]
    gap_candidates = _collect_gap_candidates(
        open_nodes=open_nodes,
        edges_by_node=edges_by_node,
        component_by_node=component_by_node,
        possible_gap=possible_gap,
        alignment_tol=alignment_tol,
    )
    candidate_count_by_node: dict[str, int] = defaultdict(int)
    for candidate in gap_candidates:
        candidate_count_by_node[candidate["node_a_id"]] += 1
        candidate_count_by_node[candidate["node_b_id"]] += 1
    for candidate in gap_candidates:
        unique = (
            candidate_count_by_node[candidate["node_a_id"]] == 1
            and candidate_count_by_node[candidate["node_b_id"]] == 1
        )
        rows.append(
            _observation_row(
                project_id=project_id,
                sheet_id=candidate["sheet_id"],
                observation_kind="endpoint_gap",
                state="POSSIBLE" if unique else "UNKNOWN",
                node_a_id=candidate["node_a_id"],
                node_b_id=candidate["node_b_id"],
                component_a_id=candidate["component_a_id"],
                component_b_id=candidate["component_b_id"],
                distance=candidate["distance"],
                alignment_error=candidate["alignment_error"],
                source_line_ids=candidate["source_line_ids"],
                evidence_ids=[],
                reason_code=(
                    "unique_collinear_open_endpoint_gap_v1"
                    if unique
                    else "ambiguous_collinear_open_endpoint_gap_v1"
                ),
                requires_review=True,
            )
        )

    rows.extend(
        _rejected_crossing_observations(
            project_id=project_id,
            geometry_edges=geometry_edges,
            component_by_node=component_by_node,
        )
    )
    frame = pd.DataFrame(rows).reindex(columns=_OBSERVATION_COLUMNS)
    state_counts = {
        str(state): int(count)
        for state, count in frame["state"].value_counts().sort_index().items()
    } if not frame.empty else {}
    kind_counts = {
        str(kind): int(count)
        for kind, count in frame["observation_kind"].value_counts().sort_index().items()
    } if not frame.empty else {}
    return frame, {
        "observation_count": int(len(frame)),
        "state_counts": state_counts,
        "kind_counts": kind_counts,
        "requires_review_count": int(frame["requires_review"].sum()) if not frame.empty else 0,
    }


def _build_sheet_geometry_graph(
    *,
    sheet_id: str,
    lines: list[LineEntity],
    config: dict,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    topology = config.get("topology", {})
    snap_tol = float(topology.get("geometry_graph_asserted_snap_tolerance", 0.05))
    merge_crossings = bool(topology.get("merge_crossings", False))
    marker_max_span = float(topology.get("geometry_graph_marker_max_span", 1.0))
    marker_match_tol = float(topology.get("geometry_graph_marker_match_tolerance", 0.75))

    wire_lines, markers = _partition_connection_markers(
        lines,
        marker_max_span=marker_max_span,
    )
    normalized = _normalize_lines(wire_lines, config)
    if not normalized:
        return [], [], []

    split_points = _collect_split_points(
        normalized,
        snap_tol=snap_tol,
        merge_crossings=merge_crossings,
        markers=markers,
        marker_match_tol=marker_match_tol,
    )
    nodes, point_to_node = _canonicalize_nodes(
        sheet_id=sheet_id,
        split_points=split_points,
        snap_tol=snap_tol,
    )
    edges = _split_lines(
        sheet_id=sheet_id,
        normalized=normalized,
        split_points=split_points,
        point_to_node=point_to_node,
        nodes=nodes,
    )
    components = _materialize_components(sheet_id=sheet_id, nodes=nodes, edges=edges)
    return nodes, edges, components


def _collect_split_points(
    lines: list[_NormalizedLine],
    *,
    snap_tol: float,
    merge_crossings: bool,
    markers: list[_ConnectionMarker],
    marker_match_tol: float,
) -> list[_SplitPoint]:
    points_by_line: dict[
        str, list[tuple[tuple[float, float], str, tuple[str, ...]]]
    ] = defaultdict(list)
    for line in lines:
        points_by_line[line.line.line_id].extend(
            [(line.start_point, "endpoint", ()), (line.end_point, "endpoint", ())]
        )

    horizontals = [line for line in lines if line.orientation == _HORIZONTAL]
    verticals = [line for line in lines if line.orientation == _VERTICAL]
    bucket_size = max(snap_tol, 2.0)
    vertical_buckets: dict[int, list[_NormalizedLine]] = defaultdict(list)
    for vertical in verticals:
        vertical_buckets[math.floor(vertical.cross_axis / bucket_size)].append(vertical)
    for horizontal in horizontals:
        start_bucket = math.floor((horizontal.axis_start - snap_tol) / bucket_size)
        end_bucket = math.floor((horizontal.axis_end + snap_tol) / bucket_size)
        candidates = [
            vertical
            for bucket in range(start_bucket, end_bucket + 1)
            for vertical in vertical_buckets.get(bucket, [])
        ]
        for vertical in candidates:
            coord = (vertical.cross_axis, horizontal.cross_axis)
            if not (
                horizontal.axis_start - snap_tol <= coord[0] <= horizontal.axis_end + snap_tol
                and vertical.axis_start - snap_tol <= coord[1] <= vertical.axis_end + snap_tol
            ):
                continue
            horizontal_endpoint = _endpoint_at(horizontal, coord, snap_tol)
            vertical_endpoint = _endpoint_at(vertical, coord, snap_tol)
            marker = _marker_at(markers, coord, marker_match_tol)
            if (
                not horizontal_endpoint
                and not vertical_endpoint
                and not merge_crossings
                and marker is None
            ):
                continue
            kind = "crossing" if not horizontal_endpoint and not vertical_endpoint else "t_cross"
            if horizontal_endpoint and vertical_endpoint:
                kind = "endpoint_merge"
            evidence_line_ids: tuple[str, ...] = ()
            if marker is not None:
                kind = "connection_marker"
                evidence_line_ids = marker.source_line_ids
            points_by_line[horizontal.line.line_id].append((coord, kind, evidence_line_ids))
            points_by_line[vertical.line.line_id].append((coord, kind, evidence_line_ids))

    result: list[_SplitPoint] = []
    for line_id, raw_points in sorted(points_by_line.items()):
        deduped: dict[tuple[float, float], tuple[str, tuple[str, ...]]] = {}
        for coord, kind, evidence_line_ids in raw_points:
            key = (round(coord[0], 8), round(coord[1], 8))
            previous = deduped.get(key)
            if previous is None or _kind_rank(kind) > _kind_rank(previous[0]):
                deduped[key] = (kind, evidence_line_ids)
        for ordinal, (coord, (kind, evidence_line_ids)) in enumerate(sorted(deduped.items())):
            result.append(
                _SplitPoint(
                    point_id=f"{line_id}:{ordinal}",
                    line_id=line_id,
                    coord=coord,
                    kind=kind,
                    evidence_line_ids=evidence_line_ids,
                )
            )
    return result


def _canonicalize_nodes(
    *,
    sheet_id: str,
    split_points: list[_SplitPoint],
    snap_tol: float,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    union_find = _UnionFind([point.point_id for point in split_points])
    bucket_size = max(snap_tol, 0.5)
    buckets: dict[tuple[int, int], list[_SplitPoint]] = defaultdict(list)
    for point in split_points:
        buckets[_bucket(point.coord, bucket_size)].append(point)

    for point in split_points:
        bucket_x, bucket_y = _bucket(point.coord, bucket_size)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for candidate in buckets.get((bucket_x + dx, bucket_y + dy), []):
                    if candidate.point_id <= point.point_id:
                        continue
                    if _distance(point.coord, candidate.coord) <= snap_tol:
                        union_find.union(point.point_id, candidate.point_id)

    members_by_root: dict[str, list[_SplitPoint]] = defaultdict(list)
    for point in split_points:
        members_by_root[union_find.find(point.point_id)].append(point)

    rows: list[dict[str, Any]] = []
    point_to_node: dict[str, str] = {}
    for members in sorted(members_by_root.values(), key=_cluster_sort_key):
        coord = (
            sum(point.coord[0] for point in members) / len(members),
            sum(point.coord[1] for point in members) / len(members),
        )
        source_line_ids = sorted({point.line_id for point in members})
        evidence_line_ids = sorted(
            {line_id for point in members for line_id in point.evidence_line_ids}
        )
        kind = max((point.kind for point in members), key=_kind_rank)
        if kind == "endpoint" and len(source_line_ids) > 1:
            kind = "endpoint_merge"
        node_id = _stable_id(
            "geometry_node",
            sheet_id,
            *source_line_ids,
            f"{coord[0]:.8f}",
            f"{coord[1]:.8f}",
        )
        for point in members:
            point_to_node[point.point_id] = node_id
        rows.append(
            {
                "geometry_node_id": node_id,
                "sheet_id": sheet_id,
                "coord": [round(coord[0], 6), round(coord[1], 6)],
                "kind": kind,
                "source_line_ids": source_line_ids,
                "evidence_line_ids": evidence_line_ids,
                "degree": 0,
                "snap_offsets": [
                    {
                        "line_id": point.line_id,
                        "distance": round(_distance(point.coord, coord), 6),
                    }
                    for point in sorted(members, key=lambda item: item.point_id)
                ],
                "state": "ASSERTED",
            }
        )
    return rows, point_to_node


def _split_lines(
    *,
    sheet_id: str,
    normalized: list[_NormalizedLine],
    split_points: list[_SplitPoint],
    point_to_node: dict[str, str],
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    points_by_line: dict[str, list[_SplitPoint]] = defaultdict(list)
    for point in split_points:
        points_by_line[point.line_id].append(point)
    node_coord = {row["geometry_node_id"]: row["coord"] for row in nodes}
    rows: list[dict[str, Any]] = []
    for line in sorted(normalized, key=lambda item: item.line.line_id):
        points = sorted(
            points_by_line[line.line.line_id],
            key=lambda point: point.coord[0] if line.orientation == _HORIZONTAL else point.coord[1],
        )
        for ordinal, (left, right) in enumerate(zip(points, points[1:])):
            start_node_id = point_to_node[left.point_id]
            end_node_id = point_to_node[right.point_id]
            if start_node_id == end_node_id:
                continue
            start_coord = node_coord[start_node_id]
            end_coord = node_coord[end_node_id]
            length = _distance(start_coord, end_coord)
            if length <= 1e-9:
                continue
            rows.append(
                {
                    "geometry_edge_id": _stable_id(
                        "geometry_edge",
                        sheet_id,
                        line.line.line_id,
                        str(ordinal),
                        start_node_id,
                        end_node_id,
                    ),
                    "sheet_id": sheet_id,
                    "source_line_id": line.line.line_id,
                    "start_node_id": start_node_id,
                    "end_node_id": end_node_id,
                    "start_coord": start_coord,
                    "end_coord": end_coord,
                    "length": round(length, 6),
                    "state": "ASSERTED",
                }
            )

    degree: dict[str, int] = defaultdict(int)
    for edge in rows:
        degree[edge["start_node_id"]] += 1
        degree[edge["end_node_id"]] += 1
    for node in nodes:
        node["degree"] = degree.get(node["geometry_node_id"], 0)
    return rows


def _materialize_components(
    *, sheet_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    node_ids = [row["geometry_node_id"] for row in nodes]
    union_find = _UnionFind(node_ids)
    for edge in edges:
        union_find.union(edge["start_node_id"], edge["end_node_id"])

    nodes_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        nodes_by_root[union_find.find(node["geometry_node_id"])].append(node)
    edges_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        edges_by_root[union_find.find(edge["start_node_id"])].append(edge)

    rows: list[dict[str, Any]] = []
    for component_nodes in sorted(nodes_by_root.values(), key=lambda group: min(row["geometry_node_id"] for row in group)):
        root = union_find.find(component_nodes[0]["geometry_node_id"])
        component_edges = edges_by_root.get(root, [])
        if not component_edges:
            continue
        member_node_ids = sorted(row["geometry_node_id"] for row in component_nodes)
        edge_ids = sorted(row["geometry_edge_id"] for row in component_edges)
        degrees = [int(row["degree"]) for row in component_nodes]
        xs = [float(row["coord"][0]) for row in component_nodes]
        ys = [float(row["coord"][1]) for row in component_nodes]
        rows.append(
            {
                "geometry_component_id": _stable_id("geometry_component", sheet_id, *edge_ids),
                "sheet_id": sheet_id,
                "node_ids": member_node_ids,
                "edge_ids": edge_ids,
                "source_line_ids": sorted({row["source_line_id"] for row in component_edges}),
                "open_node_ids": sorted(
                    row["geometry_node_id"] for row in component_nodes if row["degree"] == 1
                ),
                "junction_node_ids": sorted(
                    row["geometry_node_id"] for row in component_nodes if row["degree"] >= 3
                ),
                "degree_histogram": {
                    str(degree): degrees.count(degree) for degree in sorted(set(degrees))
                },
                "bbox": [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)],
                "total_length": round(sum(float(row["length"]) for row in component_edges), 6),
            }
        )
    return rows


def _collect_gap_candidates(
    *,
    open_nodes: list[dict[str, Any]],
    edges_by_node: dict[str, list[dict[str, Any]]],
    component_by_node: dict[str, str],
    possible_gap: float,
    alignment_tol: float,
) -> list[dict[str, Any]]:
    bucket_size = max(possible_gap, 1.0)
    buckets: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for node in open_nodes:
        coord = node["coord"]
        buckets[
            (
                str(node["sheet_id"]),
                math.floor(float(coord[0]) / bucket_size),
                math.floor(float(coord[1]) / bucket_size),
            )
        ].append(node)

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for node in open_nodes:
        node_id = str(node["geometry_node_id"])
        incident = edges_by_node.get(node_id, [])
        if len(incident) != 1:
            continue
        coord = node["coord"]
        sheet_id = str(node["sheet_id"])
        bucket_x = math.floor(float(coord[0]) / bucket_size)
        bucket_y = math.floor(float(coord[1]) / bucket_size)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in buckets.get((sheet_id, bucket_x + dx, bucket_y + dy), []):
                    other_id = str(other["geometry_node_id"])
                    key = tuple(sorted((node_id, other_id)))
                    if node_id == other_id or key in seen:
                        continue
                    seen.add(key)
                    if component_by_node.get(node_id) == component_by_node.get(other_id):
                        continue
                    other_incident = edges_by_node.get(other_id, [])
                    if len(other_incident) != 1:
                        continue
                    orientation = _edge_orientation(incident[0])
                    if orientation is None or orientation != _edge_orientation(other_incident[0]):
                        continue
                    other_coord = other["coord"]
                    alignment_error = (
                        abs(float(coord[1]) - float(other_coord[1]))
                        if orientation == _HORIZONTAL
                        else abs(float(coord[0]) - float(other_coord[0]))
                    )
                    if alignment_error > alignment_tol:
                        continue
                    distance = _distance(coord, other_coord)
                    if distance <= 1e-9 or distance > possible_gap:
                        continue
                    if not _endpoints_face_each_other(
                        node_id=node_id,
                        node_coord=coord,
                        edge=incident[0],
                        other_node_id=other_id,
                        other_coord=other_coord,
                        other_edge=other_incident[0],
                    ):
                        continue
                    candidates.append(
                        {
                            "sheet_id": sheet_id,
                            "node_a_id": key[0],
                            "node_b_id": key[1],
                            "component_a_id": component_by_node.get(key[0]),
                            "component_b_id": component_by_node.get(key[1]),
                            "distance": round(distance, 6),
                            "alignment_error": round(alignment_error, 6),
                            "source_line_ids": sorted(
                                {
                                    str(incident[0]["source_line_id"]),
                                    str(other_incident[0]["source_line_id"]),
                                }
                            ),
                        }
                    )
    return candidates


def _endpoints_face_each_other(
    *,
    node_id: str,
    node_coord: Any,
    edge: dict[str, Any],
    other_node_id: str,
    other_coord: Any,
    other_edge: dict[str, Any],
) -> bool:
    gap = _unit_vector(node_coord, other_coord)
    inward = _unit_vector(node_coord, _other_edge_coord(edge, node_id))
    other_inward = _unit_vector(other_coord, _other_edge_coord(other_edge, other_node_id))
    return _dot(inward, gap) < -0.98 and _dot(other_inward, gap) > 0.98


def _rejected_crossing_observations(
    *,
    project_id: str,
    geometry_edges: pd.DataFrame,
    component_by_node: dict[str, str],
) -> list[dict[str, Any]]:
    rows = [row.to_dict() for _, row in geometry_edges.iterrows()]
    horizontals = [row for row in rows if _edge_orientation(row) == _HORIZONTAL]
    verticals = [row for row in rows if _edge_orientation(row) == _VERTICAL]
    bucket_size = 10.0
    vertical_buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for vertical in verticals:
        x = float(vertical["start_coord"][0])
        vertical_buckets[(str(vertical["sheet_id"]), math.floor(x / bucket_size))].append(vertical)

    observations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for horizontal in horizontals:
        x1, y = map(float, horizontal["start_coord"])
        x2 = float(horizontal["end_coord"][0])
        low_x, high_x = sorted((x1, x2))
        start_bucket = math.floor(low_x / bucket_size)
        end_bucket = math.floor(high_x / bucket_size)
        for bucket in range(start_bucket, end_bucket + 1):
            for vertical in vertical_buckets.get((str(horizontal["sheet_id"]), bucket), []):
                key = tuple(sorted((str(horizontal["geometry_edge_id"]), str(vertical["geometry_edge_id"]))))
                if key in seen:
                    continue
                seen.add(key)
                horizontal_component = component_by_node.get(str(horizontal["start_node_id"]))
                vertical_component = component_by_node.get(str(vertical["start_node_id"]))
                if horizontal_component == vertical_component:
                    continue
                x = float(vertical["start_coord"][0])
                y1 = float(vertical["start_coord"][1])
                y2 = float(vertical["end_coord"][1])
                low_y, high_y = sorted((y1, y2))
                if not (low_x + 1e-6 < x < high_x - 1e-6 and low_y + 1e-6 < y < high_y - 1e-6):
                    continue
                observations.append(
                    _observation_row(
                        project_id=project_id,
                        sheet_id=str(horizontal["sheet_id"]),
                        observation_kind="crossing",
                        state="REJECTED",
                        node_a_id=None,
                        node_b_id=None,
                        component_a_id=horizontal_component,
                        component_b_id=vertical_component,
                        distance=0.0,
                        alignment_error=0.0,
                        source_line_ids=sorted(
                            {str(horizontal["source_line_id"]), str(vertical["source_line_id"])}
                        ),
                        evidence_ids=[key[0], key[1]],
                        reason_code="unmarked_internal_crossing_policy_v1",
                        requires_review=False,
                    )
                )
    return observations


def _observation_row(
    *,
    project_id: str,
    sheet_id: str,
    observation_kind: str,
    state: str,
    node_a_id: str | None,
    node_b_id: str | None,
    component_a_id: str | None,
    component_b_id: str | None,
    distance: float,
    alignment_error: float,
    source_line_ids: list[str],
    evidence_ids: list[str],
    reason_code: str,
    requires_review: bool,
) -> dict[str, Any]:
    identity_parts = sorted(
        [
            *(value for value in (node_a_id, node_b_id) if value),
            *source_line_ids,
            reason_code,
        ]
    )
    return {
        "observation_id": _stable_id("geometry_observation", project_id, sheet_id, *identity_parts),
        "schema_version": "geometry-shadow/v1",
        "project_id": project_id,
        "sheet_id": sheet_id,
        "observation_kind": observation_kind,
        "state": state,
        "node_a_id": node_a_id,
        "node_b_id": node_b_id,
        "component_a_id": component_a_id,
        "component_b_id": component_b_id,
        "distance": round(float(distance), 6),
        "alignment_error": round(float(alignment_error), 6),
        "source_line_ids": sorted(set(source_line_ids)),
        "evidence_ids": sorted(set(evidence_ids)),
        "reason_code": reason_code,
        "requires_review": requires_review,
    }


def _edge_orientation(edge: dict[str, Any]) -> str | None:
    start = edge["start_coord"]
    end = edge["end_coord"]
    if abs(float(start[1]) - float(end[1])) <= 1e-6:
        return _HORIZONTAL
    if abs(float(start[0]) - float(end[0])) <= 1e-6:
        return _VERTICAL
    return None


def _other_edge_coord(edge: dict[str, Any], node_id: str) -> Any:
    return edge["end_coord"] if str(edge["start_node_id"]) == node_id else edge["start_coord"]


def _unit_vector(start: Any, end: Any) -> tuple[float, float]:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _dot(left: tuple[float, float], right: tuple[float, float]) -> float:
    return left[0] * right[0] + left[1] * right[1]


def _normalize_lines(lines: list[LineEntity], config: dict) -> list[_NormalizedLine]:
    angle_tol = float(config.get("geometry", {}).get("horizontal_angle_tolerance_deg", 2.0))
    normalized: list[_NormalizedLine] = []
    for line in lines:
        angle = abs(float(line.angle_deg))
        horizontal = angle <= angle_tol or abs(angle - 180.0) <= angle_tol
        vertical = abs(angle - 90.0) <= angle_tol
        if not horizontal and not vertical:
            continue
        if horizontal:
            axis_start, axis_end = sorted((line.start_x, line.end_x))
            cross_axis = (line.start_y + line.end_y) / 2.0
            start_point = (axis_start, cross_axis)
            end_point = (axis_end, cross_axis)
            orientation = _HORIZONTAL
        else:
            axis_start, axis_end = sorted((line.start_y, line.end_y))
            cross_axis = (line.start_x + line.end_x) / 2.0
            start_point = (cross_axis, axis_start)
            end_point = (cross_axis, axis_end)
            orientation = _VERTICAL
        normalized.append(
            _NormalizedLine(
                line=line,
                orientation=orientation,
                axis_start=axis_start,
                axis_end=axis_end,
                cross_axis=cross_axis,
                start_point=start_point,
                end_point=end_point,
            )
        )
    return normalized


def _partition_connection_markers(
    lines: list[LineEntity], *, marker_max_span: float
) -> tuple[list[LineEntity], list[_ConnectionMarker]]:
    by_parent: dict[str, list[LineEntity]] = defaultdict(list)
    for line in lines:
        if "POLYLINE" not in str(line.source_entity_type).upper():
            continue
        parent_handle = str(line.handle).split(":", 1)[0]
        by_parent[parent_handle].append(line)

    marker_line_ids: set[str] = set()
    markers: list[_ConnectionMarker] = []
    for members in by_parent.values():
        if len(members) != 2:
            continue
        left, right = members
        if max(float(left.length), float(right.length)) > marker_max_span:
            continue
        if not (
            _distance((left.start_x, left.start_y), (right.end_x, right.end_y)) <= 1e-6
            and _distance((left.end_x, left.end_y), (right.start_x, right.start_y)) <= 1e-6
        ):
            continue
        marker_line_ids.update((left.line_id, right.line_id))
        markers.append(
            _ConnectionMarker(
                coord=(
                    (left.start_x + left.end_x) / 2.0,
                    (left.start_y + left.end_y) / 2.0,
                ),
                source_line_ids=tuple(sorted((left.line_id, right.line_id))),
            )
        )
    return [line for line in lines if line.line_id not in marker_line_ids], markers


def _marker_at(
    markers: list[_ConnectionMarker],
    coord: tuple[float, float],
    tolerance: float,
) -> _ConnectionMarker | None:
    candidates = [marker for marker in markers if _distance(marker.coord, coord) <= tolerance]
    if not candidates:
        return None
    return min(candidates, key=lambda marker: _distance(marker.coord, coord))


def _endpoint_at(
    line: _NormalizedLine, coord: tuple[float, float], tolerance: float
) -> str | None:
    if _distance(line.start_point, coord) <= tolerance:
        return "start"
    if _distance(line.end_point, coord) <= tolerance:
        return "end"
    return None


def _line_in_scope(line: LineEntity, sheet: SheetRecord | None) -> bool:
    if sheet is None or sheet.audit_area_bbox is None:
        return False
    if (sheet.audit_disposition or "audit_required") in _SKIP_DISPOSITIONS:
        return False
    bbox = sheet.audit_area_bbox
    return _point_in_bbox(line.start_x, line.start_y, bbox) or _point_in_bbox(
        line.end_x, line.end_y, bbox
    )


def _point_in_bbox(x: float, y: float, bbox: tuple[float, float, float, float]) -> bool:
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def _bucket(coord: tuple[float, float], size: float) -> tuple[int, int]:
    return (math.floor(coord[0] / size), math.floor(coord[1] / size))


def _distance(left: Any, right: Any) -> float:
    return math.hypot(float(left[0]) - float(right[0]), float(left[1]) - float(right[1]))


def _kind_rank(kind: str) -> int:
    return {
        "endpoint": 0,
        "endpoint_merge": 1,
        "t_cross": 2,
        "crossing": 3,
        "connection_marker": 4,
    }.get(kind, 0)


def _cluster_sort_key(members: list[_SplitPoint]) -> tuple[float, float, str]:
    return (
        min(point.coord[0] for point in members),
        min(point.coord[1] for point in members),
        min(point.point_id for point in members),
    )


def _stable_id(kind: str, *parts: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, "|".join((kind, *parts))))
