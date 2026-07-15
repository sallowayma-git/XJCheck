from __future__ import annotations

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
import json
import math
import re
from typing import Any

import pandas as pd

from dwg_audit.audit.crossover_jump import FAMILY as CROSSOVER_JUMP_FAMILY
from dwg_audit.audit.crossover_jump import CrossoverJump
from dwg_audit.audit.crossover_jump import recognize_crossover_jumps
from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


_HORIZONTAL = "horizontal"
_VERTICAL = "vertical"
_SKIP_DISPOSITIONS = {"skip_stable", "classify_only"}
_RELEVANT_ISSUE_RULES = {"R-PAIR-MISSING-SIDE", "R-PAIR-LOW-CONFIDENCE"}
_SCOPED_PREFIX_RE = re.compile(r"^\d+(?:-\d+)*n$", re.I)
_SCOPED_LOCAL_ENDPOINT_RE = re.compile(r"^\d+(?:-\d+)*n\d+[A-Z]?$", re.I)
_PURE_NUMERIC_RE = re.compile(r"^\d+$")
_PORT_NUMBER_RE = re.compile(r"^(?:[1-9]|10|11|12|13|14)$")
_STRUCTURED_ENDPOINT_RE = re.compile(r"^\d+(?:-\d+)*[A-Z]{1,4}(?:\d+|-\d+)$", re.I)
_BODY_FAMILY_RE = re.compile(r"(?i)(?:KLP|CLP|ZKK|ZK|KK|FA)")
_SEMANTIC_HINT_RE = re.compile(
    r"[\u4e00-\u9fff\s']|3U0|IA|IB|IC|IN|DC|VT|Enable|Manual|Reset|Start|Differential|Backup",
    re.I,
)
_PORT_REASON_HINTS = {"terminal_row_number_local_numeric", "terminal_semantic_local_numeric"}
_BRANCH_LOCAL_ENDPOINT_ROLES = {
    "external_endpoint_candidate",
    "body_port_endpoint",
    "scoped_local_endpoint",
}
_BRANCH_LOCAL_CONTEXT_ROLES = {
    "scoped_prefix",
    "component_body",
    "port_number",
    "semantic_label",
    "range_or_group",
}

_JUNCTION_COLUMNS = [
    "junction_id",
    "sheet_id",
    "coord",
    "kind",
    "member_line_ids",
    "degree",
    "evidence_text_ids",
    "evidence_block_ids",
]

_NETWORK_COLUMNS = [
    "network_id",
    "sheet_id",
    "member_line_ids",
    "junction_ids",
    "open_endpoint_junctions",
    "bridged_gaps",
    "touched_text_ids",
    "line_group_ids",
    "bbox",
    "total_length",
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
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        rank_left = self._rank[root_left]
        rank_right = self._rank[root_right]
        if rank_left < rank_right:
            root_left, root_right = root_right, root_left
        self._parent[root_right] = root_left
        if rank_left == rank_right:
            self._rank[root_left] += 1

    def groups(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for item in self._parent:
            grouped[self.find(item)].append(item)
        return {
            root: sorted(members)
            for root, members in grouped.items()
        }


def build_wire_topology_frames(
    artifacts: ProjectArtifacts,
    *,
    config: dict | None = None,
    excluded_line_ids: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    excluded_line_ids = excluded_line_ids or set()
    sheet_map = {sheet.sheet_id: sheet for sheet in artifacts.scan.pages}
    line_group_ids_by_line = _line_group_ids_by_line(artifacts)
    junction_id_factory = IdFactory("J")
    network_id_factory = IdFactory("N")
    junction_rows: list[dict[str, Any]] = []
    network_rows: list[dict[str, Any]] = []

    lines_by_sheet: dict[str, list[LineEntity]] = defaultdict(list)
    for line in artifacts.lines:
        if (
            line.line_id not in excluded_line_ids
            and _line_in_scope(line, sheet_map.get(line.sheet_id))
        ):
            lines_by_sheet[line.sheet_id].append(line)

    texts_by_sheet: dict[str, list[TextItem]] = defaultdict(list)
    for text in artifacts.texts:
        if _text_in_scope(text, sheet_map.get(text.sheet_id)):
            texts_by_sheet[text.sheet_id].append(text)

    blocks_by_sheet: dict[str, list[BlockRecord]] = defaultdict(list)
    for block in artifacts.blocks:
        if _block_in_scope(block, sheet_map.get(block.sheet_id)):
            blocks_by_sheet[block.sheet_id].append(block)

    crossover_jumps = recognize_crossover_jumps(artifacts.primitive_segments)
    jumps_by_sheet_parent: dict[tuple[str | None, str | None], list[CrossoverJump]] = defaultdict(list)
    for jump in crossover_jumps:
        jumps_by_sheet_parent[(jump.sheet_id, jump.parent_handle)].append(jump)
    crossover_jumps_by_block_id: dict[str, list[CrossoverJump]] = {}
    for block in artifacts.blocks:
        matched = jumps_by_sheet_parent.get((block.sheet_id, block.handle), [])
        if matched:
            crossover_jumps_by_block_id[block.block_id] = matched

    for sheet_id, sheet_lines in sorted(lines_by_sheet.items()):
        sheet = sheet_map.get(sheet_id)
        if sheet is None:
            continue
        sheet_junctions, sheet_networks = _build_sheet_topology(
            sheet=sheet,
            lines=sheet_lines,
            texts=texts_by_sheet.get(sheet_id, []),
            blocks=blocks_by_sheet.get(sheet_id, []),
            crossover_jumps_by_block_id=crossover_jumps_by_block_id,
            line_group_ids_by_line=line_group_ids_by_line,
            config=config or {},
            junction_id_factory=junction_id_factory,
            network_id_factory=network_id_factory,
        )
        junction_rows.extend(sheet_junctions)
        network_rows.extend(sheet_networks)

    junction_frame = pd.DataFrame(junction_rows).reindex(columns=_JUNCTION_COLUMNS)
    network_frame = pd.DataFrame(network_rows).reindex(columns=_NETWORK_COLUMNS)
    summary = {
        "wire_junction_count": int(len(junction_frame)),
        "wire_network_count": int(len(network_frame)),
        "junction_kind_counts": dict(sorted(Counter(junction_frame.get("kind", [])).items())),
        "networks_with_bridges": int(
            sum(1 for row in network_rows if row.get("bridged_gaps"))
        ),
        "crossover_jump_count": len(crossover_jumps),
        "crossover_jump_bridge_count": sum(
            1
            for row in network_rows
            for gap in row.get("bridged_gaps", [])
            if gap.get("reason") == "crossover_jump"
        ),
        "crossover_jump_no_junction_count": sum(
            1
            for row in network_rows
            for gap in row.get("bridged_gaps", [])
            if gap.get("reason") == "crossover_jump" and gap.get("no_junction") is True
        ),
    }
    return junction_frame, network_frame, summary


def build_topology_shadow_report(
    *,
    issues_frame: pd.DataFrame,
    pairs_frame: pd.DataFrame,
    line_groups_frame: pd.DataFrame,
    wire_networks_frame: pd.DataFrame,
    wire_junctions_frame: pd.DataFrame,
    text_assignments_frame: pd.DataFrame,
    config: dict | None = None,
) -> dict[str, Any]:
    if issues_frame.empty:
        return {
            "candidate_issue_count": 0,
            "recoverable_issue_count": 0,
            "recoverable_ratio": 0.0,
            "issues": [],
            "reason_counts": {},
            "branch_local_status_counts": {},
        }

    networks_by_line_group = _networks_by_line_group(wire_networks_frame)
    line_groups_by_id = _line_groups_by_id(line_groups_frame)
    junctions_by_id = _junctions_by_id(wire_junctions_frame)
    pairs_by_id = {
        str(row["pair_id"]): row
        for _, row in pairs_frame.iterrows()
        if not pd.isna(row.get("pair_id"))
    }
    assignments_by_text_id = {
        str(row["text_id"]): row
        for _, row in text_assignments_frame.iterrows()
        if not pd.isna(row.get("text_id"))
    }
    pair_rows = [
        row
        for _, row in issues_frame.iterrows()
        if str(row.get("rule_id")) in _RELEVANT_ISSUE_RULES
    ]

    report_rows: list[dict[str, Any]] = []
    for row in pair_rows:
        line_group_id = _nullable_str(row.get("line_group_id"))
        related_pair_id = _nullable_str(row.get("pair_id"))
        pair_row = pairs_by_id.get(related_pair_id or "")
        line_group_row = line_groups_by_id.get(line_group_id or "")
        candidate_networks = networks_by_line_group.get(line_group_id or "", [])
        network = candidate_networks[0] if candidate_networks else None
        network_text_rows = _network_shadow_text_rows(
            network=network,
            pair_row=pair_row,
            assignments_by_text_id=assignments_by_text_id,
        )
        bridged_gaps = _jsonish(network.get("bridged_gaps")) if network is not None else []
        open_endpoint_junctions = _jsonish(network.get("open_endpoint_junctions")) if network is not None else []
        open_endpoint_rows = [
            junctions_by_id[junction_id]
            for junction_id in open_endpoint_junctions
            if junction_id in junctions_by_id
        ]
        if network is None:
            recoverable = False
            reason = "no_network_for_line_group"
            role_counts: dict[str, int] = {}
        else:
            recoverable, reason, role_counts = _classify_shadow_signal(
                network_text_rows=network_text_rows,
                bridged_gaps=bridged_gaps,
                open_endpoint_junctions=open_endpoint_junctions,
            )
        branch_local = _build_branch_local_proposal(
            issue_row=row,
            pair_row=pair_row,
            line_group_row=line_group_row,
            network_text_rows=network_text_rows,
            topology_reason=reason,
            open_endpoint_rows=open_endpoint_rows,
            config=config or {},
        )
        report_rows.append(
            {
                "issue_id": _nullable_str(row.get("issue_id")),
                "rule_id": _nullable_str(row.get("rule_id")),
                "pair_id": related_pair_id,
                "line_group_id": line_group_id,
                "filename": _nullable_str(row.get("filename")) or _read_issue_evidence(row, "filename"),
                "sheet_no": _nullable_str(row.get("sheet_no")) or _read_issue_evidence(row, "sheet_no"),
                "sheet_order": _nullable_int(row.get("sheet_order")) or _read_issue_evidence(row, "sheet_order"),
                "pair_label": f"{_nullable_str(row.get('left_value')) or '?'} -> {_nullable_str(row.get('right_value')) or '?'}",
                "network_id": _nullable_str(network.get("network_id")) if network is not None else None,
                "open_endpoint_count": len(open_endpoint_junctions),
                "bridged_gap_count": len(bridged_gaps),
                "extra_relevant_text_ids": [item["text_id"] for item in network_text_rows],
                "extra_relevant_texts": [item["text"] for item in network_text_rows],
                "extra_relevant_text_roles": [item["text_role"] for item in network_text_rows],
                "text_role_counts": role_counts if network is not None else {},
                "topology_recoverable": recoverable,
                "topology_reason": reason,
                "branch_local_status": branch_local["status"],
                "branch_local_reason": branch_local["reason"],
                "branch_local_missing_side": branch_local["missing_side"],
                "branch_local_row_y": branch_local["row_y"],
                "branch_local_row_band_id": branch_local["row_band_id"],
                "branch_local_candidate_count": branch_local["candidate_count"],
                "branch_local_candidates": branch_local["candidates"],
                "branch_local_contexts": branch_local["contexts"],
            }
        )

    reason_counts = dict(sorted(Counter(item["topology_reason"] for item in report_rows).items()))
    branch_local_status_counts = dict(
        sorted(Counter(item["branch_local_status"] for item in report_rows).items())
    )
    recoverable_count = sum(1 for item in report_rows if item["topology_recoverable"])
    return {
        "candidate_issue_count": len(report_rows),
        "recoverable_issue_count": recoverable_count,
        "recoverable_ratio": round(recoverable_count / len(report_rows), 4) if report_rows else 0.0,
        "issues": report_rows,
        "reason_counts": reason_counts,
        "branch_local_status_counts": branch_local_status_counts,
    }


def render_topology_shadow_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Topology Shadow Report",
        "",
        f"- CandidateIssues: `{payload.get('candidate_issue_count', 0)}`",
        f"- RecoverableIssues: `{payload.get('recoverable_issue_count', 0)}`",
        f"- RecoverableRatio: `{payload.get('recoverable_ratio', 0.0)}`",
        f"- ReasonCounts: `{json.dumps(payload.get('reason_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- BranchLocalStatusCounts: `{json.dumps(payload.get('branch_local_status_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Issue Detail",
        "",
    ]
    issues = payload.get("issues", [])
    if not issues:
        lines.append("- 当前没有需要拓扑影子分析的 ordinary missing/low-confidence issue。")
        return "\n".join(lines) + "\n"
    for item in issues:
        lines.append(
            f"- `{item['issue_id']}` {item['pair_label']} "
            f"(rule={item['rule_id']}, network={item['network_id'] or '-'}, "
            f"recoverable={item['topology_recoverable']}, reason={item['topology_reason']}, "
            f"branch_local={item.get('branch_local_status')}:{item.get('branch_local_reason')}, "
            f"bridges={item['bridged_gap_count']}, open_endpoints={item['open_endpoint_count']}, "
            f"roles={json.dumps(item.get('text_role_counts', {}), ensure_ascii=False, sort_keys=True)}, "
            f"candidates={json.dumps([candidate.get('text') for candidate in item.get('branch_local_candidates', [])], ensure_ascii=False)}, "
            f"contexts={json.dumps([context.get('text') for context in item.get('branch_local_contexts', [])], ensure_ascii=False)}, "
            f"extra_texts={json.dumps(item['extra_relevant_texts'], ensure_ascii=False)})"
        )
    return "\n".join(lines) + "\n"


def _build_sheet_topology(
    *,
    sheet: SheetRecord,
    lines: list[LineEntity],
    texts: list[TextItem],
    blocks: list[BlockRecord],
    crossover_jumps_by_block_id: dict[str, list[CrossoverJump]],
    line_group_ids_by_line: dict[str, list[str]],
    config: dict,
    junction_id_factory: IdFactory,
    network_id_factory: IdFactory,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_lines = _normalize_lines(lines, config)
    if not normalized_lines:
        return [], []

    topology_config = config.get("topology", {})
    snap_tol = float(topology_config.get("junction_snap_tolerance", 1.8))
    cross_tol = float(topology_config.get("cross_axis_tolerance", 2.5))
    bridge_gap = float(topology_config.get("bridge_gap_tolerance", 18.0))
    text_gap = float(topology_config.get("inline_text_bridge_gap", 18.0))
    block_gap = float(topology_config.get("block_span_bridge_gap", 24.0))
    touch_tol = float(topology_config.get("text_touch_tolerance", 4.0))
    merge_crossings = bool(topology_config.get("merge_crossings", False))

    union_find = _UnionFind([item.line.line_id for item in normalized_lines])
    consumed_endpoints: set[tuple[str, str]] = set()
    connection_events: list[dict[str, Any]] = []
    crossing_events: list[dict[str, Any]] = []

    _collect_endpoint_merges(
        normalized_lines,
        snap_tol=snap_tol,
        union_find=union_find,
        consumed_endpoints=consumed_endpoints,
        events=connection_events,
    )
    _collect_orthogonal_intersections(
        normalized_lines,
        snap_tol=snap_tol,
        cross_tol=cross_tol,
        merge_crossings=merge_crossings,
        union_find=union_find,
        consumed_endpoints=consumed_endpoints,
        connection_events=connection_events,
        crossing_events=crossing_events,
    )
    _collect_gap_bridges(
        normalized_lines,
        texts=texts,
        blocks=blocks,
        crossover_jumps_by_block_id=crossover_jumps_by_block_id,
        cross_tol=cross_tol,
        bridge_gap=bridge_gap,
        text_gap=text_gap,
        block_gap=block_gap,
        union_find=union_find,
        consumed_endpoints=consumed_endpoints,
        events=connection_events,
    )

    groups = union_find.groups()
    line_by_id = {item.line.line_id: item for item in normalized_lines}
    junction_rows, network_rows = _materialize_topology_rows(
        sheet_id=sheet.sheet_id,
        groups=groups,
        line_by_id=line_by_id,
        texts=texts,
        line_group_ids_by_line=line_group_ids_by_line,
        consumed_endpoints=consumed_endpoints,
        connection_events=connection_events,
        crossing_events=crossing_events,
        touch_tol=touch_tol,
        junction_id_factory=junction_id_factory,
        network_id_factory=network_id_factory,
    )
    return junction_rows, network_rows


def _materialize_topology_rows(
    *,
    sheet_id: str,
    groups: dict[str, list[str]],
    line_by_id: dict[str, _NormalizedLine],
    texts: list[TextItem],
    line_group_ids_by_line: dict[str, list[str]],
    consumed_endpoints: set[tuple[str, str]],
    connection_events: list[dict[str, Any]],
    crossing_events: list[dict[str, Any]],
    touch_tol: float,
    junction_id_factory: IdFactory,
    network_id_factory: IdFactory,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    junction_rows: list[dict[str, Any]] = []
    open_junction_ids_by_network: dict[str, list[str]] = defaultdict(list)
    connection_junction_ids_by_network: dict[str, list[str]] = defaultdict(list)
    bridged_gaps_by_network: dict[str, list[dict[str, Any]]] = defaultdict(list)

    line_root = {line_id: root for root, members in groups.items() for line_id in members}
    network_id_by_root = {root: network_id_factory.next() for root in sorted(groups)}

    for event in [*connection_events, *crossing_events]:
        member_line_ids = sorted(set(event["member_line_ids"]))
        roots = {line_root[line_id] for line_id in member_line_ids if line_id in line_root}
        junction_id = junction_id_factory.next()
        row = {
            "junction_id": junction_id,
            "sheet_id": sheet_id,
            "coord": [round(event["coord"][0], 4), round(event["coord"][1], 4)],
            "kind": event["kind"],
            "member_line_ids": member_line_ids,
            "degree": len(member_line_ids),
            "evidence_text_ids": sorted(set(event.get("evidence_text_ids", []))),
            "evidence_block_ids": sorted(set(event.get("evidence_block_ids", []))),
        }
        junction_rows.append(row)
        if event["kind"] == "crossing_observation":
            continue
        for root in roots:
            network_id = network_id_by_root[root]
            connection_junction_ids_by_network[network_id].append(junction_id)
            if event["kind"] == "bridge":
                bridged_gaps_by_network[network_id].append(
                    {
                        "gap": round(float(event.get("gap", 0.0)), 4),
                        "reason": event.get("reason"),
                        "evidence_text_ids": row["evidence_text_ids"],
                        "evidence_block_ids": row["evidence_block_ids"],
                        "crossover_family": event.get("crossover_family"),
                        "crossover_parent_handles": event.get("crossover_parent_handles", []),
                        "crossover_primitive_ids": event.get("crossover_primitive_ids", []),
                        "no_junction": bool(event.get("no_junction", False)),
                    }
                )

    for root, member_line_ids in sorted(groups.items()):
        network_id = network_id_by_root[root]
        for line_id in member_line_ids:
            norm_line = line_by_id[line_id]
            for endpoint_name, point in (("start", norm_line.start_point), ("end", norm_line.end_point)):
                if (line_id, endpoint_name) in consumed_endpoints:
                    continue
                junction_id = junction_id_factory.next()
                junction_rows.append(
                    {
                        "junction_id": junction_id,
                        "sheet_id": sheet_id,
                        "coord": [round(point[0], 4), round(point[1], 4)],
                        "kind": "endpoint",
                        "member_line_ids": [line_id],
                        "degree": 1,
                        "evidence_text_ids": [],
                        "evidence_block_ids": [],
                    }
                )
                open_junction_ids_by_network[network_id].append(junction_id)

    network_rows: list[dict[str, Any]] = []
    for root, member_line_ids in sorted(groups.items()):
        network_id = network_id_by_root[root]
        member_lines = [line_by_id[line_id] for line_id in member_line_ids]
        line_group_ids = sorted(
            {
                group_id
                for line_id in member_line_ids
                for group_id in line_group_ids_by_line.get(line_id, [])
            }
        )
        touched_text_ids = sorted(
            {
                text.text_id
                for text in texts
                if any(_text_touches_line(text, line, tolerance=touch_tol) for line in member_lines)
            }
        )
        for gap in bridged_gaps_by_network.get(network_id, []):
            touched_text_ids.extend(gap.get("evidence_text_ids", []))
        bbox = _network_bbox(member_lines)
        total_length = round(sum(item.line.length for item in member_lines), 4)
        network_rows.append(
            {
                "network_id": network_id,
                "sheet_id": sheet_id,
                "member_line_ids": member_line_ids,
                "junction_ids": sorted(set(connection_junction_ids_by_network.get(network_id, []))),
                "open_endpoint_junctions": sorted(set(open_junction_ids_by_network.get(network_id, []))),
                "bridged_gaps": bridged_gaps_by_network.get(network_id, []),
                "touched_text_ids": sorted(set(touched_text_ids)),
                "line_group_ids": line_group_ids,
                "bbox": bbox,
                "total_length": total_length,
            }
        )
    return junction_rows, network_rows


def _collect_endpoint_merges(
    normalized_lines: list[_NormalizedLine],
    *,
    snap_tol: float,
    union_find: _UnionFind,
    consumed_endpoints: set[tuple[str, str]],
    events: list[dict[str, Any]],
) -> None:
    endpoints: list[dict[str, Any]] = []
    for line in normalized_lines:
        endpoints.append({"line_id": line.line.line_id, "endpoint": "start", "coord": line.start_point})
        endpoints.append({"line_id": line.line.line_id, "endpoint": "end", "coord": line.end_point})

    bucket_size = max(snap_tol, 0.5)
    buckets: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for item in endpoints:
        x, y = item["coord"]
        buckets[(round(x / bucket_size), round(y / bucket_size))].append(item)

    visited: set[tuple[str, str]] = set()
    for bucket_items in buckets.values():
        for item in bucket_items:
            endpoint_key = (item["line_id"], item["endpoint"])
            if endpoint_key in visited:
                continue
            cluster = [item]
            visited.add(endpoint_key)
            changed = True
            while changed:
                changed = False
                for candidate in bucket_items:
                    candidate_key = (candidate["line_id"], candidate["endpoint"])
                    if candidate_key in visited:
                        continue
                    if any(_distance(candidate["coord"], member["coord"]) <= snap_tol for member in cluster):
                        cluster.append(candidate)
                        visited.add(candidate_key)
                        changed = True
            line_ids = sorted({member["line_id"] for member in cluster})
            if len(line_ids) <= 1:
                continue
            for left, right in zip(line_ids, line_ids[1:]):
                union_find.union(left, right)
            for member in cluster:
                consumed_endpoints.add((member["line_id"], member["endpoint"]))
            avg_x = sum(member["coord"][0] for member in cluster) / len(cluster)
            avg_y = sum(member["coord"][1] for member in cluster) / len(cluster)
            events.append(
                {
                    "kind": "endpoint_merge",
                    "coord": (avg_x, avg_y),
                    "member_line_ids": line_ids,
                    "evidence_text_ids": [],
                    "evidence_block_ids": [],
                }
            )


def _collect_orthogonal_intersections(
    normalized_lines: list[_NormalizedLine],
    *,
    snap_tol: float,
    cross_tol: float,
    merge_crossings: bool,
    union_find: _UnionFind,
    consumed_endpoints: set[tuple[str, str]],
    connection_events: list[dict[str, Any]],
    crossing_events: list[dict[str, Any]],
) -> None:
    horizontals = [item for item in normalized_lines if item.orientation == _HORIZONTAL]
    verticals = [item for item in normalized_lines if item.orientation == _VERTICAL]
    if not horizontals or not verticals:
        return

    bucket_size = max(cross_tol, 2.0)
    vertical_buckets: dict[int, list[_NormalizedLine]] = defaultdict(list)
    for line in verticals:
        vertical_buckets[round(line.cross_axis / bucket_size)].append(line)

    seen_pairs: set[tuple[str, str]] = set()
    for horizontal in horizontals:
        start_bucket = round(horizontal.axis_start / bucket_size)
        end_bucket = round(horizontal.axis_end / bucket_size)
        for bucket in range(start_bucket - 1, end_bucket + 2):
            for vertical in vertical_buckets.get(bucket, []):
                pair_key = tuple(sorted((horizontal.line.line_id, vertical.line.line_id)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                if not (
                    horizontal.axis_start - snap_tol <= vertical.cross_axis <= horizontal.axis_end + snap_tol
                    and vertical.axis_start - snap_tol <= horizontal.cross_axis <= vertical.axis_end + snap_tol
                ):
                    continue
                coord = (vertical.cross_axis, horizontal.cross_axis)
                horizontal_endpoint = _line_endpoint_at_point(horizontal, coord, snap_tol)
                vertical_endpoint = _line_endpoint_at_point(vertical, coord, snap_tol)
                member_line_ids = [horizontal.line.line_id, vertical.line.line_id]
                if horizontal_endpoint and vertical_endpoint:
                    union_find.union(member_line_ids[0], member_line_ids[1])
                    consumed_endpoints.add((horizontal.line.line_id, horizontal_endpoint))
                    consumed_endpoints.add((vertical.line.line_id, vertical_endpoint))
                    connection_events.append(
                        {
                            "kind": "endpoint_merge",
                            "coord": coord,
                            "member_line_ids": member_line_ids,
                            "evidence_text_ids": [],
                            "evidence_block_ids": [],
                        }
                    )
                elif horizontal_endpoint or vertical_endpoint:
                    union_find.union(member_line_ids[0], member_line_ids[1])
                    if horizontal_endpoint:
                        consumed_endpoints.add((horizontal.line.line_id, horizontal_endpoint))
                    if vertical_endpoint:
                        consumed_endpoints.add((vertical.line.line_id, vertical_endpoint))
                    connection_events.append(
                        {
                            "kind": "t_cross",
                            "coord": coord,
                            "member_line_ids": member_line_ids,
                            "evidence_text_ids": [],
                            "evidence_block_ids": [],
                        }
                    )
                else:
                    if merge_crossings:
                        union_find.union(member_line_ids[0], member_line_ids[1])
                    crossing_events.append(
                        {
                            "kind": "crossing_observation",
                            "coord": coord,
                            "member_line_ids": member_line_ids,
                            "evidence_text_ids": [],
                            "evidence_block_ids": [],
                        }
                    )


def _collect_gap_bridges(
    normalized_lines: list[_NormalizedLine],
    *,
    texts: list[TextItem],
    blocks: list[BlockRecord],
    crossover_jumps_by_block_id: dict[str, list[CrossoverJump]],
    cross_tol: float,
    bridge_gap: float,
    text_gap: float,
    block_gap: float,
    union_find: _UnionFind,
    consumed_endpoints: set[tuple[str, str]],
    events: list[dict[str, Any]],
) -> None:
    by_orientation: dict[str, list[_NormalizedLine]] = defaultdict(list)
    for line in normalized_lines:
        by_orientation[line.orientation].append(line)

    for orientation, lines in by_orientation.items():
        if len(lines) < 2:
            continue
        bucket_size = max(cross_tol, 2.0)
        buckets: dict[int, list[_NormalizedLine]] = defaultdict(list)
        for line in lines:
            buckets[round(line.cross_axis / bucket_size)].append(line)
        seen_pairs: set[tuple[str, str]] = set()
        for bucket, bucket_lines in buckets.items():
            candidates = [*bucket_lines, *buckets.get(bucket + 1, []), *buckets.get(bucket - 1, [])]
            for line in bucket_lines:
                for other in candidates:
                    if line.line.line_id == other.line.line_id:
                        continue
                    pair_key = tuple(sorted((line.line.line_id, other.line.line_id)))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    if abs(line.cross_axis - other.cross_axis) > cross_tol:
                        continue
                    left, right = sorted((line, other), key=lambda item: item.axis_start)
                    gap = right.axis_start - left.axis_end
                    if gap <= 0 or gap > bridge_gap:
                        continue
                    evidence_text_ids = _inline_text_bridge_ids(
                        left=left,
                        right=right,
                        texts=texts,
                        max_gap=text_gap,
                    )
                    evidence_block_ids = _block_span_bridge_ids(
                        left=left,
                        right=right,
                        blocks=blocks,
                        max_gap=block_gap,
                    )
                    if not evidence_text_ids and not evidence_block_ids:
                        continue
                    matched_jumps = [
                        jump
                        for block_id in evidence_block_ids
                        for jump in crossover_jumps_by_block_id.get(block_id, [])
                    ]
                    reason = (
                        "crossover_jump"
                        if matched_jumps
                        else "inline_text"
                        if evidence_text_ids
                        else "block_span"
                    )
                    union_find.union(left.line.line_id, right.line.line_id)
                    consumed_endpoints.add((left.line.line_id, "end"))
                    consumed_endpoints.add((right.line.line_id, "start"))
                    coord = _gap_midpoint(left, right)
                    events.append(
                        {
                            "kind": "bridge",
                            "coord": coord,
                            "member_line_ids": [left.line.line_id, right.line.line_id],
                            "gap": gap,
                            "reason": reason,
                            "evidence_text_ids": evidence_text_ids,
                            "evidence_block_ids": evidence_block_ids,
                            "crossover_family": CROSSOVER_JUMP_FAMILY if matched_jumps else None,
                            "crossover_parent_handles": sorted(
                                {str(jump.parent_handle) for jump in matched_jumps if jump.parent_handle}
                            ),
                            "crossover_primitive_ids": sorted(
                                {
                                    primitive_id
                                    for jump in matched_jumps
                                    for primitive_id in (*jump.line_ids, jump.arc_id)
                                }
                            ),
                            "no_junction": bool(matched_jumps),
                        }
                    )


def _normalize_lines(lines: list[LineEntity], config: dict) -> list[_NormalizedLine]:
    angle_tol = float(config.get("geometry", {}).get("horizontal_angle_tolerance_deg", 2.0))
    normalized: list[_NormalizedLine] = []
    for line in lines:
        angle = abs(line.angle_deg)
        horizontal = angle <= angle_tol or abs(angle - 180.0) <= angle_tol
        vertical = abs(angle - 90.0) <= angle_tol
        if not horizontal and not vertical:
            continue
        if horizontal:
            axis_start = min(line.start_x, line.end_x)
            axis_end = max(line.start_x, line.end_x)
            cross_axis = (line.start_y + line.end_y) / 2.0
            start_point = (axis_start, cross_axis)
            end_point = (axis_end, cross_axis)
            orientation = _HORIZONTAL
        else:
            axis_start = min(line.start_y, line.end_y)
            axis_end = max(line.start_y, line.end_y)
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


def _line_group_ids_by_line(artifacts: ProjectArtifacts) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for group in artifacts.line_groups:
        for line_id in group.member_line_ids:
            mapping[str(line_id)].append(group.line_group_id)
    return {
        line_id: sorted(set(group_ids))
        for line_id, group_ids in mapping.items()
    }


def _line_in_scope(line: LineEntity, sheet: SheetRecord | None) -> bool:
    if sheet is None or sheet.audit_area_bbox is None:
        return False
    if (sheet.audit_disposition or "audit_required") in _SKIP_DISPOSITIONS:
        return False
    return _point_in_bbox(line.start_x, line.start_y, sheet.audit_area_bbox) or _point_in_bbox(
        line.end_x,
        line.end_y,
        sheet.audit_area_bbox,
    )


def _text_in_scope(text: TextItem, sheet: SheetRecord | None) -> bool:
    if sheet is None or sheet.audit_area_bbox is None:
        return False
    if (sheet.audit_disposition or "audit_required") in _SKIP_DISPOSITIONS:
        return False
    return _point_in_bbox(text.insert_x, text.insert_y, sheet.audit_area_bbox)


def _block_in_scope(block: BlockRecord, sheet: SheetRecord | None) -> bool:
    if sheet is None or sheet.audit_area_bbox is None:
        return False
    if (sheet.audit_disposition or "audit_required") in _SKIP_DISPOSITIONS:
        return False
    return _point_in_bbox(block.insert_x, block.insert_y, sheet.audit_area_bbox)


def _text_touches_line(text: TextItem, line: _NormalizedLine, *, tolerance: float) -> bool:
    if line.orientation == _HORIZONTAL:
        if text.bbox_max_x < line.axis_start - 1.0 or text.bbox_min_x > line.axis_end + 1.0:
            return False
        return text.bbox_min_y - tolerance <= line.cross_axis <= text.bbox_max_y + tolerance
    if text.bbox_max_y < line.axis_start - 1.0 or text.bbox_min_y > line.axis_end + 1.0:
        return False
    return text.bbox_min_x - tolerance <= line.cross_axis <= text.bbox_max_x + tolerance


def _network_bbox(lines: list[_NormalizedLine]) -> list[float]:
    return [
        round(min(line.line.bbox_min_x for line in lines), 4),
        round(min(line.line.bbox_min_y for line in lines), 4),
        round(max(line.line.bbox_max_x for line in lines), 4),
        round(max(line.line.bbox_max_y for line in lines), 4),
    ]


def _point_in_bbox(x: float, y: float, bbox: tuple[float, float, float, float] | None) -> bool:
    if bbox is None:
        return False
    min_x, min_y, max_x, max_y = bbox
    return min_x <= x <= max_x and min_y <= y <= max_y


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _line_endpoint_at_point(
    line: _NormalizedLine,
    coord: tuple[float, float],
    tolerance: float,
) -> str | None:
    if _distance(line.start_point, coord) <= tolerance:
        return "start"
    if _distance(line.end_point, coord) <= tolerance:
        return "end"
    return None


def _inline_text_bridge_ids(
    *,
    left: _NormalizedLine,
    right: _NormalizedLine,
    texts: list[TextItem],
    max_gap: float,
) -> list[str]:
    gap = right.axis_start - left.axis_end
    if gap <= 0 or gap > max_gap:
        return []
    matched: list[str] = []
    if left.orientation == _HORIZONTAL:
        cross_axis = (left.cross_axis + right.cross_axis) / 2.0
        for text in texts:
            if text.bbox_max_x < left.axis_end - 1.0 or text.bbox_min_x > right.axis_start + 1.0:
                continue
            if text.bbox_min_y - 4.0 <= cross_axis <= text.bbox_max_y + 4.0:
                matched.append(text.text_id)
    else:
        cross_axis = (left.cross_axis + right.cross_axis) / 2.0
        for text in texts:
            if text.bbox_max_y < left.axis_end - 1.0 or text.bbox_min_y > right.axis_start + 1.0:
                continue
            if text.bbox_min_x - 4.0 <= cross_axis <= text.bbox_max_x + 4.0:
                matched.append(text.text_id)
    return sorted(set(matched))


def _block_span_bridge_ids(
    *,
    left: _NormalizedLine,
    right: _NormalizedLine,
    blocks: list[BlockRecord],
    max_gap: float,
) -> list[str]:
    gap = right.axis_start - left.axis_end
    if gap <= 0 or gap > max_gap:
        return []
    matched: list[str] = []
    if left.orientation == _HORIZONTAL:
        cross_axis = (left.cross_axis + right.cross_axis) / 2.0
        for block in blocks:
            if left.axis_end - 1.0 <= block.insert_x <= right.axis_start + 1.0 and abs(block.insert_y - cross_axis) <= 4.0:
                matched.append(block.block_id)
    else:
        cross_axis = (left.cross_axis + right.cross_axis) / 2.0
        for block in blocks:
            if left.axis_end - 1.0 <= block.insert_y <= right.axis_start + 1.0 and abs(block.insert_x - cross_axis) <= 4.0:
                matched.append(block.block_id)
    return sorted(set(matched))


def _gap_midpoint(left: _NormalizedLine, right: _NormalizedLine) -> tuple[float, float]:
    mid_axis = (left.axis_end + right.axis_start) / 2.0
    cross_axis = (left.cross_axis + right.cross_axis) / 2.0
    if left.orientation == _HORIZONTAL:
        return (mid_axis, cross_axis)
    return (cross_axis, mid_axis)


def _networks_by_line_group(network_frame: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if network_frame.empty:
        return {}
    for _, row in network_frame.iterrows():
        payload = {column: row[column] for column in network_frame.columns}
        for line_group_id in _jsonish(row.get("line_group_ids")):
            mapping[str(line_group_id)].append(payload)
    return dict(mapping)


def _line_groups_by_id(line_groups_frame: pd.DataFrame) -> dict[str, pd.Series]:
    if line_groups_frame.empty:
        return {}
    return {
        str(row["line_group_id"]): row
        for _, row in line_groups_frame.iterrows()
        if not pd.isna(row.get("line_group_id"))
    }


def _junctions_by_id(wire_junctions_frame: pd.DataFrame) -> dict[str, pd.Series]:
    if wire_junctions_frame.empty:
        return {}
    return {
        str(row["junction_id"]): row
        for _, row in wire_junctions_frame.iterrows()
        if not pd.isna(row.get("junction_id"))
    }


def _network_shadow_text_rows(
    *,
    network: dict[str, Any] | None,
    pair_row: pd.Series | None,
    assignments_by_text_id: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    if network is None:
        return []
    excluded = {
        _nullable_str(pair_row.get("left_text_id")) if pair_row is not None else None,
        _nullable_str(pair_row.get("right_text_id")) if pair_row is not None else None,
    }
    extra_rows: list[dict[str, Any]] = []
    for text_id in _jsonish(network.get("touched_text_ids")):
        if text_id in excluded:
            continue
        assignment = assignments_by_text_id.get(str(text_id))
        if assignment is None:
            continue
        text = _nullable_str(assignment.get("text")) or ""
        text_role = _classify_network_text_role(assignment)
        if text_role is None:
            continue
        extra_rows.append(
            {
                "text_id": str(text_id),
                "text": text,
                "assignment_kind": _nullable_str(assignment.get("assignment_kind")),
                "candidate_channel": _nullable_str(assignment.get("candidate_channel")),
                "rejection_reason": _nullable_str(assignment.get("rejection_reason")),
                "explain_reason": _nullable_str(assignment.get("explain_reason")),
                "text_role": text_role,
                "insert_x": _nullable_float(assignment.get("insert_x")),
                "insert_y": _nullable_float(assignment.get("insert_y")),
            }
        )
    return extra_rows


def _build_branch_local_proposal(
    *,
    issue_row: pd.Series,
    pair_row: pd.Series | None,
    line_group_row: pd.Series | None,
    network_text_rows: list[dict[str, Any]],
    topology_reason: str,
    open_endpoint_rows: list[pd.Series],
    config: dict,
) -> dict[str, Any]:
    if line_group_row is None:
        return {
            "status": "no_line_group_geometry",
            "reason": "no_line_group_geometry",
            "missing_side": _missing_side(issue_row),
            "row_y": None,
            "row_band_id": None,
            "candidate_count": 0,
            "candidates": [],
            "contexts": [],
        }

    missing_side = _missing_side(issue_row)
    if missing_side not in {"left", "right"}:
        return {
            "status": "not_single_sided",
            "reason": "not_single_sided_issue",
            "missing_side": missing_side,
            "row_y": _line_group_row_y(line_group_row),
            "row_band_id": _nullable_str(line_group_row.get("row_band_id")),
            "candidate_count": 0,
            "candidates": [],
            "contexts": [],
        }

    topology_config = config.get("topology", {})
    row_tol = float(topology_config.get("branch_local_row_y_tolerance", 3.5))
    side_margin = float(topology_config.get("branch_local_side_margin", 2.0))
    candidate_limit = int(topology_config.get("branch_local_candidate_limit", 5))
    anchor_distance = float(topology_config.get("branch_local_open_endpoint_anchor_distance", 10.0))
    anchor_row_tol = float(topology_config.get("branch_local_open_endpoint_row_tolerance", 4.0))

    row_y = _line_group_row_y(line_group_row)
    start_x = min(
        _nullable_float(line_group_row.get("start_x")) or 0.0,
        _nullable_float(line_group_row.get("end_x")) or 0.0,
    )
    end_x = max(
        _nullable_float(line_group_row.get("start_x")) or 0.0,
        _nullable_float(line_group_row.get("end_x")) or 0.0,
    )
    anchor_x = start_x if missing_side == "left" else end_x
    compatible_open_endpoints = _compatible_open_endpoints(
        open_endpoint_rows=open_endpoint_rows,
        row_y=row_y,
        side=missing_side,
        start_x=start_x,
        end_x=end_x,
        side_margin=side_margin,
    )

    same_row_rows = [
        row
        for row in network_text_rows
        if row.get("insert_y") is not None
        and row_y is not None
        and abs(float(row["insert_y"]) - row_y) <= row_tol
    ]

    endpoint_candidates = []
    contexts = []
    for item in same_row_rows:
        payload = _branch_local_text_payload(
            item=item,
            anchor_x=anchor_x,
            row_y=row_y,
            side=missing_side,
            start_x=start_x,
            end_x=end_x,
            side_margin=side_margin,
        )
        if item.get("text_role") in _BRANCH_LOCAL_ENDPOINT_ROLES:
            payload.update(
                _branch_local_open_endpoint_anchor(
                    payload=payload,
                    open_endpoints=compatible_open_endpoints,
                    anchor_distance=anchor_distance,
                    anchor_row_tol=anchor_row_tol,
                )
            )
            endpoint_candidates.append(payload)
        elif item.get("text_role") in _BRANCH_LOCAL_CONTEXT_ROLES:
            contexts.append(payload)

    endpoint_candidates.sort(
        key=lambda item: (
            0 if item.get("anchored_open_endpoint_count", 0) > 0 else 1,
            _branch_local_role_priority(item.get("text_role"), topology_reason),
            item.get("open_endpoint_anchor_distance", 9999.0),
            item.get("side_distance", 9999.0),
            item.get("row_delta", 9999.0),
            item.get("text") or "",
        )
    )
    contexts.sort(
        key=lambda item: (
            item.get("row_delta", 9999.0),
            item.get("side_distance", 9999.0),
            item.get("text") or "",
        )
    )
    side_candidates = [item for item in endpoint_candidates if item.get("side_ok")]
    anchored_side_candidates = [
        item for item in side_candidates if int(item.get("anchored_open_endpoint_count", 0)) > 0
    ]
    meaningful_contexts = [item for item in contexts if item.get("text_role") != "port_number"]

    if len(anchored_side_candidates) == 1:
        status = "unique_candidate"
        reason = "single_same_side_open_endpoint_anchored_candidate"
    elif len(anchored_side_candidates) > 1:
        status = "ambiguous_candidates"
        reason = "multiple_open_endpoint_anchored_candidates"
    elif len(side_candidates) == 1:
        status = "unique_candidate"
        reason = "single_same_row_same_side_structured_candidate"
    elif len(side_candidates) > 1:
        status = "ambiguous_candidates"
        reason = "multiple_same_row_same_side_structured_candidates"
    elif meaningful_contexts or topology_reason in {
        "scoped_local_number_cluster",
        "body_port_cluster",
        "semantic_local_cluster",
    }:
        status = "context_only"
        reason = "same_row_structural_context_without_same_side_candidate"
    else:
        status = "no_candidate"
        reason = "no_same_row_same_side_structured_signal"

    return {
        "status": status,
        "reason": reason,
        "missing_side": missing_side,
        "row_y": row_y,
        "row_band_id": _nullable_str(line_group_row.get("row_band_id")),
        "candidate_count": len(anchored_side_candidates) if anchored_side_candidates else len(side_candidates),
        "candidates": (anchored_side_candidates or side_candidates)[:candidate_limit],
        "contexts": contexts[:candidate_limit],
    }


def _branch_local_text_payload(
    *,
    item: dict[str, Any],
    anchor_x: float,
    row_y: float | None,
    side: str,
    start_x: float,
    end_x: float,
    side_margin: float,
) -> dict[str, Any]:
    insert_x = _nullable_float(item.get("insert_x"))
    insert_y = _nullable_float(item.get("insert_y"))
    row_delta = abs(insert_y - row_y) if insert_y is not None and row_y is not None else None
    side_distance: float | None = None
    side_ok = False
    if insert_x is not None:
        if side == "left":
            side_distance = anchor_x - insert_x
            side_ok = insert_x <= start_x - side_margin
        else:
            side_distance = insert_x - anchor_x
            side_ok = insert_x >= end_x + side_margin
    return {
        "text_id": item.get("text_id"),
        "text": item.get("text"),
        "text_role": item.get("text_role"),
        "assignment_kind": item.get("assignment_kind"),
        "candidate_channel": item.get("candidate_channel"),
        "rejection_reason": item.get("rejection_reason"),
        "insert_x": insert_x,
        "insert_y": insert_y,
        "row_delta": round(row_delta, 4) if row_delta is not None else None,
        "side_distance": round(side_distance, 4) if side_distance is not None else None,
        "side_ok": side_ok,
    }


def _branch_local_role_priority(text_role: Any, topology_reason: str) -> int:
    if topology_reason == "body_port_cluster":
        priority = {
            "body_port_endpoint": 0,
            "external_endpoint_candidate": 1,
            "scoped_local_endpoint": 2,
        }
    else:
        priority = {
            "external_endpoint_candidate": 0,
            "body_port_endpoint": 1,
            "scoped_local_endpoint": 2,
        }
    return priority.get(str(text_role), 9)


def _compatible_open_endpoints(
    *,
    open_endpoint_rows: list[pd.Series],
    row_y: float | None,
    side: str,
    start_x: float,
    end_x: float,
    side_margin: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in open_endpoint_rows:
        coord = _jsonish(row.get("coord"))
        if not isinstance(coord, (list, tuple)) or len(coord) != 2:
            continue
        x = _nullable_float(coord[0])
        y = _nullable_float(coord[1])
        if x is None or y is None:
            continue
        side_ok = x <= start_x - side_margin if side == "left" else x >= end_x + side_margin
        if not side_ok:
            continue
        rows.append(
            {
                "junction_id": _nullable_str(row.get("junction_id")),
                "x": x,
                "y": y,
                "row_delta": round(abs(y - row_y), 4) if row_y is not None else None,
            }
        )
    return rows


def _branch_local_open_endpoint_anchor(
    *,
    payload: dict[str, Any],
    open_endpoints: list[dict[str, Any]],
    anchor_distance: float,
    anchor_row_tol: float,
) -> dict[str, Any]:
    insert_x = _nullable_float(payload.get("insert_x"))
    insert_y = _nullable_float(payload.get("insert_y"))
    if insert_x is None or insert_y is None:
        return {
            "open_endpoint_anchor_distance": None,
            "anchored_open_endpoint_ids": [],
            "anchored_open_endpoint_count": 0,
        }

    anchored: list[tuple[float, str]] = []
    for endpoint in open_endpoints:
        endpoint_x = _nullable_float(endpoint.get("x"))
        endpoint_y = _nullable_float(endpoint.get("y"))
        if endpoint_x is None or endpoint_y is None:
            continue
        row_delta = abs(insert_y - endpoint_y)
        if row_delta > anchor_row_tol:
            continue
        distance = _distance((insert_x, insert_y), (endpoint_x, endpoint_y))
        if distance > anchor_distance:
            continue
        junction_id = _nullable_str(endpoint.get("junction_id"))
        if junction_id is None:
            continue
        anchored.append((distance, junction_id))

    anchored.sort(key=lambda item: (item[0], item[1]))
    return {
        "open_endpoint_anchor_distance": round(anchored[0][0], 4) if anchored else None,
        "anchored_open_endpoint_ids": [junction_id for _, junction_id in anchored],
        "anchored_open_endpoint_count": len(anchored),
    }


def _missing_side(issue_row: pd.Series) -> str:
    left_value = _nullable_str(issue_row.get("left_value"))
    right_value = _nullable_str(issue_row.get("right_value"))
    if left_value is None and right_value is not None:
        return "left"
    if right_value is None and left_value is not None:
        return "right"
    return "unknown"


def _line_group_row_y(line_group_row: pd.Series) -> float | None:
    start_y = _nullable_float(line_group_row.get("start_y"))
    end_y = _nullable_float(line_group_row.get("end_y"))
    if start_y is None and end_y is None:
        return None
    if start_y is None:
        return end_y
    if end_y is None:
        return start_y
    return round((start_y + end_y) / 2.0, 4)


def _classify_shadow_signal(
    *,
    network_text_rows: list[dict[str, Any]],
    bridged_gaps: list[Any],
    open_endpoint_junctions: list[Any],
) -> tuple[bool, str, dict[str, int]]:
    role_counts = Counter(
        item["text_role"]
        for item in network_text_rows
        if item.get("text_role")
    )
    has_external = role_counts.get("external_endpoint_candidate", 0) > 0
    has_scoped = role_counts.get("scoped_prefix", 0) > 0 or role_counts.get("scoped_local_endpoint", 0) > 0
    has_body = role_counts.get("component_body", 0) > 0 or role_counts.get("body_port_endpoint", 0) > 0
    has_ports = role_counts.get("port_number", 0) > 0
    has_local = role_counts.get("local_numeric", 0) > 0
    has_semantic = role_counts.get("semantic_label", 0) > 0 or role_counts.get("range_or_group", 0) > 0

    if has_scoped and has_local:
        return False, "scoped_local_number_cluster", dict(sorted(role_counts.items()))
    if has_body and (has_ports or has_local):
        return False, "body_port_cluster", dict(sorted(role_counts.items()))
    if has_external and (bridged_gaps or len(open_endpoint_junctions) >= 2):
        return True, "topology_recoverable_external_endpoint_present", dict(sorted(role_counts.items()))
    if has_local or has_semantic:
        return False, "semantic_local_cluster", dict(sorted(role_counts.items()))
    return False, "no_additional_topology_signal", dict(sorted(role_counts.items()))


def _classify_network_text_role(assignment: pd.Series) -> str | None:
    assignment_kind = _nullable_str(assignment.get("assignment_kind")) or ""
    if assignment_kind == "out_of_scope":
        return None

    text = (_nullable_str(assignment.get("text")) or "").strip()
    if not text:
        return None

    candidate_channel = _nullable_str(assignment.get("candidate_channel")) or ""
    rejection_reason = _nullable_str(assignment.get("rejection_reason")) or ""
    explain_reason = _nullable_str(assignment.get("explain_reason")) or ""

    if _SCOPED_PREFIX_RE.fullmatch(text):
        return "scoped_prefix"
    if _SCOPED_LOCAL_ENDPOINT_RE.fullmatch(text):
        return "scoped_local_endpoint"
    if _PURE_NUMERIC_RE.fullmatch(text):
        if _PORT_NUMBER_RE.fullmatch(text) or explain_reason in _PORT_REASON_HINTS:
            return "port_number"
        return "local_numeric"
    if "~" in text:
        return "range_or_group"
    if _BODY_FAMILY_RE.search(text):
        if re.search(r"-\d+$", text):
            return "body_port_endpoint"
        return "component_body"
    if _SEMANTIC_HINT_RE.search(text):
        return "semantic_label"
    if assignment_kind == "structured_mapping_endpoint":
        return "external_endpoint_candidate"
    if candidate_channel == "wire_logic_endpoint_channel":
        return "external_endpoint_candidate"
    if _STRUCTURED_ENDPOINT_RE.fullmatch(text):
        return "external_endpoint_candidate"
    if assignment_kind in {"semantic_evidence", "continuation_evidence"}:
        return "semantic_label"
    if candidate_channel in {"semantic_channel", "continuation_channel"}:
        return "semantic_label"
    if candidate_channel == "noise_channel" and rejection_reason == "not_numeric":
        return "semantic_label"
    return "other"


def _read_issue_evidence(row: pd.Series, key: str) -> Any:
    for column in ("evidence", "evidence_refs"):
        payload = _jsonish(row.get(column))
        if isinstance(payload, dict) and key in payload:
            return payload.get(key)
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and key in item:
                    return item.get(key)
    return None


def _jsonish(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        return value.tolist()
    return value


def _nullable_str(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value)
    return None if text in {"", "None", "nan"} else text


def _nullable_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nullable_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
