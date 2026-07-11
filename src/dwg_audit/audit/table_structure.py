"""Geometry-only table-grid profiles.

The profile is deliberately independent from page names, sheet numbers and layers.  It
is a conservative input to later topology filtering: only lines participating in a
complete rectangular grid are returned as structural lines.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from typing import Any

from dwg_audit.domain.models import LineEntity


_ALGORITHM_VERSION = "table-structure-v1"


def build_table_structure_profiles(
    pages: Iterable[Any],
    lines: Iterable[LineEntity],
    page_classifications: Any = None,
    config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return verified rectangular grid profiles grouped by sheet.

    ``pages`` and ``page_classifications`` are accepted so callers can keep their
    normal extraction shape, but geometry is the only admission criterion.  In
    particular, a line is structural only when it supports a complete grid with at
    least two rows and two columns; incidental short leads stay out of the result.
    """
    del pages, page_classifications
    settings = (config or {}).get("table_structure", {}) if isinstance(config, Mapping) else {}
    coord_tol = float(settings.get("axis_tolerance", 0.5))
    endpoint_tol = float(settings.get("intersection_tolerance", coord_tol))
    min_axes = int(settings.get("min_axis_count", 3))
    min_axes = max(3, min_axes)

    by_sheet: dict[str, list[LineEntity]] = defaultdict(list)
    for line in lines:
        by_sheet[line.sheet_id].append(line)

    profiles: list[dict[str, Any]] = []
    for sheet_id, sheet_lines in sorted(by_sheet.items()):
        horizontal = [line for line in sheet_lines if abs(line.end_y - line.start_y) <= coord_tol and abs(line.end_x - line.start_x) > coord_tol]
        vertical = [line for line in sheet_lines if abs(line.end_x - line.start_x) <= coord_tol and abs(line.end_y - line.start_y) > coord_tol]
        if len(horizontal) < min_axes or len(vertical) < min_axes:
            continue

        h_axes = _cluster_axes(horizontal, lambda item: (item.start_y + item.end_y) / 2.0, coord_tol)
        v_axes = _cluster_axes(vertical, lambda item: (item.start_x + item.end_x) / 2.0, coord_tol)
        if len(h_axes) < min_axes or len(v_axes) < min_axes:
            continue

        crossings = _crossings(h_axes, v_axes, endpoint_tol)
        for h_nodes, v_nodes in _components(crossings, h_axes, v_axes):
            h_active, v_active = _complete_grid_axes(h_nodes, v_nodes, crossings, min_axes)
            if len(h_active) < min_axes or len(v_active) < min_axes:
                continue
            row_axes = sorted(h_axes[node]["coord"] for node in h_active)
            column_axes = sorted(v_axes[node]["coord"] for node in v_active)
            min_x, max_x = column_axes[0], column_axes[-1]
            min_y, max_y = row_axes[0], row_axes[-1]
            structural = _structural_ids(h_active, v_active, h_axes, v_axes, crossings)
            if not structural:
                continue
            density = sum(1 for h_node in h_active for v_node in v_active if v_node in crossings[h_node]) / (len(h_active) * len(v_active))
            profiles.append(
                {
                    "sheet_id": sheet_id,
                    "bbox": (min_x, min_y, max_x, max_y),
                    "row_axes": row_axes,
                    "column_axes": column_axes,
                    "structural_line_ids": sorted(structural),
                    "cell_count": (len(row_axes) - 1) * (len(column_axes) - 1),
                    "header_scope": {
                        "bbox": (min_x, row_axes[-2], max_x, max_y),
                        "row_axis_indices": [len(row_axes) - 2, len(row_axes) - 1],
                    },
                    "confidence": round(0.85 + 0.1 * density + min(0.05, 0.01 * (len(row_axes) + len(column_axes) - 6)), 3),
                    "reason_codes": ["GEOMETRY_COMPLETE_GRID", "GRID_AXES_VERIFIED", "STRUCTURAL_LINES_ONLY"],
                    "algorithm_version": _ALGORITHM_VERSION,
                }
            )
    return sorted(profiles, key=lambda item: (item["sheet_id"], item["bbox"], item["structural_line_ids"]))


def _cluster_axes(lines: list[LineEntity], coordinate: Any, tolerance: float) -> dict[int, dict[str, Any]]:
    clusters: list[list[LineEntity]] = []
    for line in sorted(lines, key=lambda item: (coordinate(item), item.line_id)):
        value = coordinate(line)
        if clusters and abs(value - sum(coordinate(member) for member in clusters[-1]) / len(clusters[-1])) <= tolerance:
            clusters[-1].append(line)
        else:
            clusters.append([line])
    return {index: {"coord": sum(coordinate(member) for member in members) / len(members), "lines": members} for index, members in enumerate(clusters)}


def _crossings(h_axes: Mapping[int, dict[str, Any]], v_axes: Mapping[int, dict[str, Any]], tolerance: float) -> dict[int, set[int]]:
    result: dict[int, set[int]] = {node: set() for node in h_axes}
    for h_node, h_axis in h_axes.items():
        y = h_axis["coord"]
        for v_node, v_axis in v_axes.items():
            x = v_axis["coord"]
            if any(_spans_x(line, x, tolerance) for line in h_axis["lines"]) and any(_spans_y(line, y, tolerance) for line in v_axis["lines"]):
                result[h_node].add(v_node)
    return result


def _components(crossings: Mapping[int, set[int]], h_axes: Mapping[int, Any], v_axes: Mapping[int, Any]) -> Iterable[tuple[set[int], set[int]]]:
    reverse: dict[int, set[int]] = {node: set() for node in v_axes}
    for h_node, v_nodes in crossings.items():
        for v_node in v_nodes:
            reverse[v_node].add(h_node)
    visited_h: set[int] = set()
    visited_v: set[int] = set()
    for start in h_axes:
        if start in visited_h or not crossings[start]:
            continue
        h_nodes: set[int] = set()
        v_nodes: set[int] = set()
        queue: deque[tuple[str, int]] = deque([("h", start)])
        while queue:
            kind, node = queue.popleft()
            visited = visited_h if kind == "h" else visited_v
            if node in visited:
                continue
            visited.add(node)
            (h_nodes if kind == "h" else v_nodes).add(node)
            neighbours = crossings[node] if kind == "h" else reverse[node]
            next_kind = "v" if kind == "h" else "h"
            queue.extend((next_kind, neighbour) for neighbour in neighbours)
        yield h_nodes, v_nodes


def _complete_grid_axes(h_nodes: set[int], v_nodes: set[int], crossings: Mapping[int, set[int]], min_axes: int) -> tuple[set[int], set[int]]:
    horizontal, vertical = set(h_nodes), set(v_nodes)
    while horizontal and vertical:
        next_horizontal = {node for node in horizontal if vertical.issubset(crossings[node])}
        next_vertical = {node for node in vertical if all(node in crossings[h_node] for h_node in next_horizontal)}
        if next_horizontal == horizontal and next_vertical == vertical:
            break
        horizontal, vertical = next_horizontal, next_vertical
    return (horizontal, vertical) if len(horizontal) >= min_axes and len(vertical) >= min_axes else (set(), set())


def _structural_ids(h_nodes: set[int], v_nodes: set[int], h_axes: Mapping[int, dict[str, Any]], v_axes: Mapping[int, dict[str, Any]], crossings: Mapping[int, set[int]]) -> set[str]:
    result: set[str] = set()
    for h_node in h_nodes:
        for line in h_axes[h_node]["lines"]:
            if sum(_spans_x(line, v_axes[v_node]["coord"], 0.0) for v_node in v_nodes) >= 2:
                result.add(line.line_id)
    for v_node in v_nodes:
        for line in v_axes[v_node]["lines"]:
            if sum(_spans_y(line, h_axes[h_node]["coord"], 0.0) for h_node in h_nodes) >= 2:
                result.add(line.line_id)
    return result


def _spans_x(line: LineEntity, x: float, tolerance: float) -> bool:
    return min(line.start_x, line.end_x) - tolerance <= x <= max(line.start_x, line.end_x) + tolerance


def _spans_y(line: LineEntity, y: float, tolerance: float) -> bool:
    return min(line.start_y, line.end_y) - tolerance <= y <= max(line.start_y, line.end_y) + tolerance
