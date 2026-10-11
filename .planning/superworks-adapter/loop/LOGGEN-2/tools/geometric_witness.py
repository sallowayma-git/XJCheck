"""Geometric witness for admitted wire-route pairs whose record carries no drawn wire handle.

Usage: python geometric_witness.py <admitted_json> <replay_dir> <out_json>

For each admitted pair, the two end contacts are the SuperWORKS port segments of the record ends
(sw_ports.parquet, each port's own tolerance). A witness is a path of drawn line segments of the
record's sheet (lines.parquet, model-space segments the audit read) that joins a segment endpoint
touching end 0 to a segment endpoint touching end 1. The breadth-first search walks segment
endpoints only. This is a geometric check: it says the drawing has a continuous line between the
two terminal contacts, not which wire it is.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


def node(x: float, y: float) -> tuple[float, float]:
    return round(float(x), 3), round(float(y), 3)


def near(p, q, tol: float) -> bool:
    return math.hypot(p[0] - q[0], p[1] - q[1]) <= tol + 1e-8


def _point_segment_distance(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    length_sq = vx * vx + vy * vy
    if length_sq == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / length_sq))
    return math.hypot(p[0] - (ax + t * vx), p[1] - (ay + t * vy))


def _touch(a, b, point, tol: float) -> bool:
    """A contact point touches a drawn segment when the segment passes within the port tolerance."""
    return _point_segment_distance(point, a, b) <= tol + 1e-8


def _segment_graph(segments):
    """Segments are neighbours when one's endpoint lies on the other (end-to-end or T junction)."""
    neighbours = defaultdict(set)
    grid = defaultdict(list)
    for index, (a, b) in enumerate(segments):
        for point in (a, b):
            grid[(math.floor(point[0] / 2), math.floor(point[1] / 2))].append(index)
    for index, (a, b) in enumerate(segments):
        for point in (a, b):
            cell = (math.floor(point[0] / 2), math.floor(point[1] / 2))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for other in grid.get((cell[0] + dx, cell[1] + dy), ()):
                        if other == index:
                            continue
                        c, d = segments[other]
                        if _point_segment_distance(point, c, d) <= 1e-3:
                            neighbours[index].add(other)
                            neighbours[other].add(index)
    return neighbours


def main(rows_path: Path, replay: Path, out: Path) -> None:
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    loaded: dict[str, tuple] = {}
    results = []
    for row in rows:
        pid = row["project"]
        if pid not in loaded:
            complete = json.loads((replay / pid / "complete.json").read_text(encoding="utf-8"))
            findings = Path(complete["project_dir"]) / "findings"
            loaded[pid] = (
                pd.read_parquet(findings / "lines.parquet"),
                pd.read_parquet(findings / "sw_ports.parquet"),
                pd.read_parquet(findings / "sw_wire_routes.parquet"),
            )
        lines_all, ports_all, routes_all = loaded[pid]
        route = routes_all[routes_all.record_id == row["record_id"]].iloc[0]
        ends = json.loads(route.ends_json)
        lines = lines_all[(lines_all.sheet_id == route.sheet_id)]
        if "source_block_name" in lines.columns:
            lines = lines[lines.source_block_name.isna()]
        contacts = []
        for end in ends[:2]:
            match = ports_all[(ports_all.file_id == end["file_id"])
                              & (ports_all.insert_handle.astype(str) == str(end["terminal_handle"]))
                              & (ports_all.port_number.astype(str) == str(end["port_number"]))]
            contacts.append([((r.start_x, r.start_y), (r.end_x, r.end_y), float(r.tolerance))
                             for r in match.itertuples()])
        segments = [((r.start_x, r.start_y), (r.end_x, r.end_y)) for r in lines.itertuples()]
        starts = [i for i, (a, b) in enumerate(segments)
                  if any(_touch(a, b, c, tol) or _touch(a, b, d, tol) for c, d, tol in contacts[0])]
        target_contacts = contacts[1] if len(contacts) > 1 else []
        targets = {i for i, (a, b) in enumerate(segments)
                   if any(_touch(a, b, c, tol) or _touch(a, b, d, tol) for c, d, tol in target_contacts)}
        neighbours = _segment_graph(segments)
        found = False
        seen = set(starts)
        queue = deque(starts)
        while queue and not found:
            current = queue.popleft()
            if current in targets:
                found = True
                break
            for nxt in neighbours.get(current, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        results.append({"project": pid, "pair_id": row["pair_id"], "record_id": row["record_id"],
                        "left": row["left"], "right": row["right"], "kind": row["kind"],
                        "contact_segments": [len(contacts[0]), len(contacts[1]) if len(contacts) > 1 else 0],
                        "start_segments": len(starts), "witness": bool(found)})
    summary = {"pairs": len(results), "witness": sum(r["witness"] for r in results),
               "no_witness": sum(not r["witness"] for r in results),
               "missing_contact": sum(1 for r in results if min(r["contact_segments"]) == 0)}
    out.write_text(json.dumps({"summary": summary, "pairs": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
