from __future__ import annotations

import uuid
from collections import defaultdict
import heapq
from typing import Any

import pandas as pd


NETWORK_SCHEMA_VERSION = "electrical-network-v2"
NETWORK_ALGORITHM_VERSION = "asserted-only-components-v1"
_ID_NAMESPACE = uuid.UUID("fc1198b6-24ee-5cc4-83f8-39213a350f09")


def build_asserted_electrical_network_frames(
    geometry_nodes: pd.DataFrame,
    geometry_edges: pd.DataFrame,
    geometry_components: pd.DataFrame,
    topology_decisions: pd.DataFrame,
    *,
    source_handle_by_line: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    source_handle_by_line = source_handle_by_line or {}
    node_by_id = {
        str(row["geometry_node_id"]): row.to_dict()
        for _, row in geometry_nodes.iterrows()
    }
    component_ids = [str(value) for value in geometry_components.get("geometry_component_id", [])]
    union_find = _UnionFind(component_ids)
    component_sheet = {
        str(row["geometry_component_id"]): str(row["sheet_id"])
        for _, row in geometry_components.iterrows()
    }
    application_rows: list[dict[str, Any]] = []
    for _, decision in topology_decisions.iterrows():
        decision_id = str(decision["topology_decision_id"])
        state = str(decision["decision_state"])
        eligible = bool(decision["union_eligible"])
        left = _nullable_string(decision.get("component_a_id"))
        right = _nullable_string(decision.get("component_b_id"))
        applied = False
        if state != "ASSERTED" or not eligible:
            reason = "NON_ASSERTED_NOT_APPLIED"
        elif left is None or right is None or left == right:
            reason = "ALREADY_MATERIALIZED_IN_COMPONENT"
        elif left not in component_sheet or right not in component_sheet:
            reason = "COMPONENT_NOT_FOUND"
        elif component_sheet[left] != component_sheet[right]:
            reason = "CROSS_SHEET_UNION_FORBIDDEN"
        else:
            union_find.union(left, right)
            applied = True
            reason = "ASSERTED_COMPONENT_UNION"
        application_rows.append(
            {
                "topology_decision_id": decision_id,
                "decision_state": state,
                "union_eligible": eligible,
                "applied": applied,
                "application_reason_code": reason,
                "component_a_id": left,
                "component_b_id": right,
            }
        )

    components_by_root: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, component in geometry_components.iterrows():
        component_id = str(component["geometry_component_id"])
        components_by_root[union_find.find(component_id)].append(component.to_dict())

    network_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    open_rows: list[dict[str, Any]] = []
    network_by_component: dict[str, str] = {}
    for _, components in sorted(components_by_root.items()):
        component_ids_for_network = sorted(
            str(component["geometry_component_id"]) for component in components
        )
        sheet_id = str(components[0]["sheet_id"])
        network_id = _stable_id(sheet_id, *component_ids_for_network)
        for component_id in component_ids_for_network:
            network_by_component[component_id] = network_id
        edge_ids = sorted(
            {
                str(value)
                for component in components
                for value in _listish(component.get("edge_ids"))
            }
        )
        line_ids = sorted(
            {
                str(value)
                for component in components
                for value in _listish(component.get("source_line_ids"))
            }
        )
        node_ids = sorted(
            {
                str(value)
                for component in components
                for value in _listish(component.get("node_ids"))
            }
        )
        open_node_ids = sorted(
            {
                str(value)
                for component in components
                for value in _listish(component.get("open_node_ids"))
            }
        )
        junction_node_ids = sorted(
            {
                str(value)
                for component in components
                for value in _listish(component.get("junction_node_ids"))
            }
        )
        network_rows.append(
            {
                "electrical_network_id": network_id,
                "schema_version": NETWORK_SCHEMA_VERSION,
                "algorithm_version": NETWORK_ALGORITHM_VERSION,
                "sheet_id": sheet_id,
                "geometry_component_ids": component_ids_for_network,
                "source_line_ids": line_ids,
                "geometry_edge_ids": edge_ids,
                "node_ids": node_ids,
                "junction_node_ids": junction_node_ids,
                "open_node_ids": open_node_ids,
                "bbox": _combined_bbox(components),
                "total_length": round(
                    sum(float(component.get("total_length") or 0.0) for component in components),
                    6,
                ),
            }
        )
        for line_id in line_ids:
            member_rows.append(
                {
                    "electrical_network_id": network_id,
                    "sheet_id": sheet_id,
                    "member_type": "SOURCE_LINE",
                    "member_id": line_id,
                    "source_handle": source_handle_by_line.get(line_id),
                }
            )
        for edge_id in edge_ids:
            member_rows.append(
                {
                    "electrical_network_id": network_id,
                    "sheet_id": sheet_id,
                    "member_type": "GEOMETRY_EDGE",
                    "member_id": edge_id,
                    "source_handle": None,
                }
            )
        for node_id in open_node_ids:
            node = node_by_id.get(node_id, {})
            open_rows.append(
                {
                    "electrical_network_id": network_id,
                    "sheet_id": sheet_id,
                    "node_id": node_id,
                    "coord": _listish(node.get("coord")),
                    "source_line_ids": _listish(node.get("source_line_ids")),
                    "source_handles": sorted(
                        {
                            source_handle_by_line[line_id]
                            for line_id in _listish(node.get("source_line_ids"))
                            if line_id in source_handle_by_line
                        }
                    ),
                    "boundary_state": "OPEN",
                    "reason_code": "GEOMETRY_DEGREE_ONE_V1",
                }
            )

    boundary_rows: list[dict[str, Any]] = []
    for _, decision in topology_decisions.iterrows():
        state = str(decision["decision_state"])
        if state == "ASSERTED":
            continue
        component_ids_for_boundary = sorted(
            {
                value
                for value in (
                    _nullable_string(decision.get("component_a_id")),
                    _nullable_string(decision.get("component_b_id")),
                )
                if value is not None
            }
        )
        boundary_rows.append(
            {
                "possible_boundary_id": _stable_id(
                    "boundary", str(decision["topology_decision_id"])
                ),
                "topology_decision_id": str(decision["topology_decision_id"]),
                "sheet_id": str(decision["sheet_id"]),
                "decision_state": state,
                "decision_kind": str(decision["decision_kind"]),
                "geometry_component_ids": component_ids_for_boundary,
                "electrical_network_ids": sorted(
                    {
                        network_by_component[value]
                        for value in component_ids_for_boundary
                        if value in network_by_component
                    }
                ),
                "reason_codes": _listish(decision.get("reason_codes")),
                "requires_review": bool(decision.get("requires_review")),
            }
        )

    network_frame = pd.DataFrame(network_rows)
    member_frame = pd.DataFrame(member_rows)
    open_frame = pd.DataFrame(open_rows)
    boundary_frame = pd.DataFrame(boundary_rows)
    application_frame = pd.DataFrame(application_rows)
    non_asserted_applied = application_frame.loc[
        (application_frame.get("decision_state") != "ASSERTED")
        & application_frame.get("applied", False)
    ] if not application_frame.empty else application_frame
    summary = {
        "schema_version": "electrical-network-summary-v1",
        "network_count": len(network_frame),
        "member_count": len(member_frame),
        "open_endpoint_count": len(open_frame),
        "possible_boundary_count": len(boundary_frame),
        "asserted_union_application_count": int(application_frame["applied"].sum())
        if not application_frame.empty
        else 0,
        "non_asserted_union_application_count": len(non_asserted_applied),
    }
    return network_frame, member_frame, open_frame, boundary_frame, application_frame, summary


def build_network_endpoint_witness_frame(
    electrical_networks: pd.DataFrame,
    open_endpoints: pd.DataFrame,
    geometry_edges: pd.DataFrame,
    *,
    source_handle_by_line: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    source_handle_by_line = source_handle_by_line or {}
    edge_by_id = {
        str(row["geometry_edge_id"]): row.to_dict()
        for _, row in geometry_edges.iterrows()
    }
    open_by_network: dict[str, list[str]] = defaultdict(list)
    for _, row in open_endpoints.iterrows():
        open_by_network[str(row["electrical_network_id"])].append(str(row["node_id"]))
    rows: list[dict[str, Any]] = []
    for _, network in electrical_networks.iterrows():
        network_id = str(network["electrical_network_id"])
        adjacency: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
        for edge_id in _listish(network.get("geometry_edge_ids")):
            edge = edge_by_id.get(str(edge_id))
            if edge is None:
                continue
            left = str(edge["start_node_id"])
            right = str(edge["end_node_id"])
            length = float(edge.get("length") or 0.0)
            adjacency[left].append((right, str(edge_id), length))
            adjacency[right].append((left, str(edge_id), length))
        targets = sorted(set(open_by_network.get(network_id, [])))
        junction_targets = set(_listish(network.get("junction_node_ids")))
        network_nodes = set(_listish(network.get("node_ids")))
        for start in targets:
            target_kind = "OTHER_OPEN_ENDPOINT"
            distance, node_path, edge_path = _nearest_target_path(start, set(targets) - {start}, adjacency)
            if not node_path:
                target_kind = "JUNCTION"
                distance, node_path, edge_path = _nearest_target_path(
                    start, junction_targets - {start}, adjacency
                )
            if not node_path:
                target_kind = "NETWORK_NODE"
                distance, node_path, edge_path = _nearest_target_path(
                    start, network_nodes - {start}, adjacency
                )
            source_line_ids = sorted(
                {
                    str(edge_by_id[edge_id]["source_line_id"])
                    for edge_id in edge_path
                    if edge_id in edge_by_id
                }
            )
            resolved = bool(node_path)
            rows.append(
                {
                    "witness_id": _stable_id("witness", network_id, start),
                    "schema_version": "network-endpoint-witness-v1",
                    "electrical_network_id": network_id,
                    "sheet_id": str(network["sheet_id"]),
                    "start_node_id": start,
                    "target_node_id": node_path[-1] if resolved else None,
                    "target_kind": target_kind if resolved else None,
                    "node_path": node_path,
                    "geometry_edge_path": edge_path,
                    "source_line_ids": source_line_ids,
                    "source_handles": [
                        source_handle_by_line[line_id]
                        for line_id in source_line_ids
                        if line_id in source_handle_by_line
                    ],
                    "path_length": round(distance, 6) if resolved else None,
                    "weakest_evidence_state": "ASSERTED" if resolved else "UNKNOWN",
                    "reason_code": (
                        "SHORTEST_ASSERTED_GEOMETRY_PATH_V1"
                        if resolved
                        else "NO_ASSERTED_PATH_TO_OTHER_OPEN_ENDPOINT"
                    ),
                    "resolved": resolved,
                }
            )
    frame = pd.DataFrame(rows)
    summary = {
        "schema_version": "network-witness-summary-v1",
        "witness_count": len(frame),
        "resolved_count": int(frame["resolved"].sum()) if not frame.empty else 0,
        "unresolved_count": int((~frame["resolved"]).sum()) if not frame.empty else 0,
        "witness_completeness": round(
            float(frame["resolved"].mean()) if not frame.empty else 1.0, 6
        ),
    }
    return frame, summary


def build_network_validation_suspicions(
    electrical_networks: pd.DataFrame,
    possible_boundaries: pd.DataFrame,
    decision_applications: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, application in decision_applications.iterrows():
        if (
            str(application.get("decision_state")) == "ASSERTED"
            and bool(application.get("union_eligible"))
            and not bool(application.get("applied"))
            and str(application.get("application_reason_code"))
            not in {"ALREADY_MATERIALIZED_IN_COMPONENT"}
        ):
            rows.append(
                _suspicion_row(
                    "SPLIT_SUSPICION",
                    "ASSERTED_CONNECTION_NOT_MATERIALIZED",
                    topology_decision_id=str(application["topology_decision_id"]),
                )
            )

    for _, boundary in possible_boundaries.iterrows():
        network_ids = sorted(set(_listish(boundary.get("electrical_network_ids"))))
        component_ids = sorted(set(_listish(boundary.get("geometry_component_ids"))))
        if len(component_ids) >= 2 and len(network_ids) == 1:
            rows.append(
                _suspicion_row(
                    "OVERMERGE_SUSPICION",
                    "NON_ASSERTED_BOUNDARY_INSIDE_NETWORK",
                    electrical_network_id=str(network_ids[0]),
                    topology_decision_id=str(boundary["topology_decision_id"]),
                )
            )

    applied_pairs = [
        (
            str(row["component_a_id"]),
            str(row["component_b_id"]),
        )
        for _, row in decision_applications.iterrows()
        if bool(row.get("applied"))
    ]
    for _, network in electrical_networks.iterrows():
        component_ids = sorted(set(_listish(network.get("geometry_component_ids"))))
        if len(component_ids) < 2:
            continue
        links = _UnionFind(component_ids)
        for left, right in applied_pairs:
            if left in links.parent and right in links.parent:
                links.union(left, right)
        if len({links.find(value) for value in component_ids}) > 1:
            rows.append(
                _suspicion_row(
                    "OVERMERGE_SUSPICION",
                    "MULTI_COMPONENT_NETWORK_WITHOUT_ASSERTED_WITNESS",
                    electrical_network_id=str(network["electrical_network_id"]),
                )
            )

    frame = pd.DataFrame(rows)
    summary = {
        "schema_version": "network-validation-summary-v1",
        "suspicion_count": len(frame),
        "overmerge_suspicion_count": sum(
            row["suspicion_kind"] == "OVERMERGE_SUSPICION" for row in rows
        ),
        "split_suspicion_count": sum(
            row["suspicion_kind"] == "SPLIT_SUSPICION" for row in rows
        ),
        "reason_counts": {
            str(key): int(value)
            for key, value in sorted(
                pd.Series([row["reason_code"] for row in rows]).value_counts().items()
            )
        }
        if rows
        else {},
    }
    return frame, summary


def build_network_boundary_frame(
    open_endpoints: pd.DataFrame,
    pages: list[Any],
    blocks: list[Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    page_by_sheet = {str(page.sheet_id): page for page in pages}
    blocks_by_sheet: dict[str, list[Any]] = defaultdict(list)
    for block in blocks:
        blocks_by_sheet[str(block.sheet_id)].append(block)
    rows: list[dict[str, Any]] = []
    for _, endpoint in open_endpoints.iterrows():
        sheet_id = str(endpoint["sheet_id"])
        coord = _listish(endpoint.get("coord"))
        page = page_by_sheet.get(sheet_id)
        drawing_state = "UNKNOWN"
        drawing_reason = "DRAWING_BOUNDARY_NOT_ESTABLISHED"
        if page is not None and page.audit_area_bbox is not None and len(coord) >= 2:
            min_x, min_y, max_x, max_y = map(float, page.audit_area_bbox)
            edge_distance = min(
                abs(float(coord[0]) - min_x),
                abs(float(coord[0]) - max_x),
                abs(float(coord[1]) - min_y),
                abs(float(coord[1]) - max_y),
            )
            if edge_distance <= 1.0:
                drawing_state = "ASSERTED"
                drawing_reason = "AUDIT_AREA_EDGE_PROXIMITY_V1"
        nearby_blocks = []
        if len(coord) >= 2:
            nearby_blocks = sorted(
                block.block_id
                for block in blocks_by_sheet.get(sheet_id, [])
                if ((float(block.insert_x) - float(coord[0])) ** 2 + (float(block.insert_y) - float(coord[1])) ** 2) ** 0.5 <= 4.0
            )
        rows.append(
            {
                "network_boundary_id": _stable_id(
                    "network_boundary",
                    str(endpoint["electrical_network_id"]),
                    str(endpoint["node_id"]),
                ),
                "schema_version": "network-boundary-v1",
                "electrical_network_id": str(endpoint["electrical_network_id"]),
                "sheet_id": sheet_id,
                "node_id": str(endpoint["node_id"]),
                "coord": coord,
                "source_handles": _listish(endpoint.get("source_handles")),
                "drawing_boundary_state": drawing_state,
                "drawing_boundary_reason_code": drawing_reason,
                "symbol_boundary_state": "POSSIBLE" if nearby_blocks else "UNKNOWN",
                "symbol_boundary_evidence_ids": nearby_blocks,
                "cross_page_interruption_state": "UNKNOWN",
                "cross_page_reason_code": "DEFERRED_TO_SEMANTIC_CROSS_PAGE_RESOLVER",
                "review_required": drawing_state != "ASSERTED" or bool(nearby_blocks),
            }
        )
    frame = pd.DataFrame(rows)
    summary = {
        "schema_version": "network-boundary-summary-v1",
        "boundary_count": len(frame),
        "drawing_asserted_count": int(
            (frame.get("drawing_boundary_state") == "ASSERTED").sum()
        )
        if not frame.empty
        else 0,
        "symbol_possible_count": int(
            (frame.get("symbol_boundary_state") == "POSSIBLE").sum()
        )
        if not frame.empty
        else 0,
        "cross_page_unknown_count": int(
            (frame.get("cross_page_interruption_state") == "UNKNOWN").sum()
        )
        if not frame.empty
        else 0,
    }
    return frame, summary


def build_legacy_pair_network_equivalence_frame(
    pairs: list[Any],
    line_groups: list[Any],
    network_members: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    networks_by_line: dict[str, set[str]] = defaultdict(set)
    if not network_members.empty:
        for _, member in network_members.loc[
            network_members["member_type"] == "SOURCE_LINE"
        ].iterrows():
            networks_by_line[str(member["member_id"])].add(
                str(member["electrical_network_id"])
            )
    group_by_id = {str(group.line_group_id): group for group in line_groups}
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        group = group_by_id.get(str(pair.line_group_id))
        member_line_ids = sorted(str(value) for value in (group.member_line_ids if group else []))
        network_ids = sorted(
            {
                network_id
                for line_id in member_line_ids
                for network_id in networks_by_line.get(line_id, set())
            }
        )
        if not network_ids:
            status = "NO_V2_NETWORK"
        elif len(network_ids) == 1:
            status = "UNIQUE_V2_NETWORK"
        else:
            status = "MULTIPLE_V2_NETWORKS"
        rows.append(
            {
                "pair_id": str(pair.pair_id),
                "sheet_id": str(pair.sheet_id),
                "line_group_id": str(pair.line_group_id),
                "pair_kind": str(pair.pair_kind),
                "legacy_status": str(pair.status),
                "left_value": pair.left_value,
                "right_value": pair.right_value,
                "member_line_ids": member_line_ids,
                "electrical_network_ids": network_ids,
                "equivalence_status": status,
                "v2_changes_legacy_result": False,
            }
        )
    frame = pd.DataFrame(rows)
    summary = {
        "schema_version": "legacy-pair-network-equivalence-summary-v1",
        "pair_count": len(frame),
        "status_counts": {
            str(key): int(value)
            for key, value in frame.get("equivalence_status", pd.Series(dtype=str))
            .value_counts()
            .sort_index()
            .items()
        },
        "legacy_result_change_count": int(
            frame.get("v2_changes_legacy_result", pd.Series(dtype=bool)).sum()
        ),
    }
    return frame, summary


class _UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _stable_id(*parts: str) -> str:
    return f"EN2-{uuid.uuid5(_ID_NAMESPACE, '|'.join(parts))}"


def _listish(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return list(value.tolist())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _nullable_string(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def _combined_bbox(components: list[dict[str, Any]]) -> list[float] | None:
    boxes = [_listish(component.get("bbox")) for component in components]
    boxes = [box for box in boxes if len(box) == 4]
    if not boxes:
        return None
    return [
        min(float(box[0]) for box in boxes),
        min(float(box[1]) for box in boxes),
        max(float(box[2]) for box in boxes),
        max(float(box[3]) for box in boxes),
    ]


def _nearest_target_path(
    start: str,
    targets: set[str],
    adjacency: dict[str, list[tuple[str, str, float]]],
) -> tuple[float, list[str], list[str]]:
    if not targets:
        return 0.0, [], []
    queue: list[tuple[float, str, list[str], list[str]]] = [(0.0, start, [start], [])]
    best = {start: 0.0}
    while queue:
        distance, node, node_path, edge_path = heapq.heappop(queue)
        if distance > best.get(node, float("inf")):
            continue
        if node in targets:
            return distance, node_path, edge_path
        for neighbor, edge_id, edge_length in adjacency.get(node, []):
            candidate = distance + edge_length
            if candidate >= best.get(neighbor, float("inf")):
                continue
            best[neighbor] = candidate
            heapq.heappush(
                queue,
                (candidate, neighbor, [*node_path, neighbor], [*edge_path, edge_id]),
            )
    return 0.0, [], []


def _suspicion_row(
    suspicion_kind: str,
    reason_code: str,
    *,
    electrical_network_id: str | None = None,
    topology_decision_id: str | None = None,
) -> dict[str, Any]:
    return {
        "suspicion_id": _stable_id(
            "suspicion",
            suspicion_kind,
            reason_code,
            electrical_network_id or "",
            topology_decision_id or "",
        ),
        "schema_version": "network-validation-suspicion-v1",
        "suspicion_kind": suspicion_kind,
        "reason_code": reason_code,
        "electrical_network_id": electrical_network_id,
        "topology_decision_id": topology_decision_id,
        "review_only": True,
    }
