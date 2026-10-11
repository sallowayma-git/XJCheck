"""G2 gap census (read-only, round19 outputs): every merged collinear gap of 0.6 < gap <= 4 in the baseline line groups.

For each gap it records: whether a SW port marker lies within 1.0 units of each gap end (any port, and two different ports),
whether a text covers the gap by drawn extent (bbox) or by insertion point (GAP-2 window test), and whether a connect dot lies in it.
Prints the counts that decide how many gaps G2 could split, under the bbox test (used by G2) and the insertion test (GAP-2 README).
Usage: python g2_gap_probe.py  (writes .tmp/loop_g2_scratch/gaps_census.pkl)
"""
from __future__ import annotations

import collections
import json
import math
from pathlib import Path

import pandas as pd

ROUND = Path("F:/workspace/XJToolkit/.tmp/superworks_round19_full")
OUT = Path("F:/workspace/XJToolkit/.tmp/loop_g2_scratch")


def seg_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for fd in sorted(ROUND.glob("p*/*/findings")):
        pid = fd.parts[-3]
        try:
            lines = pd.read_parquet(fd / "lines.parquet")
            groups = pd.read_parquet(fd / "line_groups.parquet")
            ports = pd.read_parquet(fd / "sw_ports.parquet")
            texts = pd.read_parquet(fd / "texts.parquet")
            dots = pd.read_parquet(fd / "sw_connect_dots.parquet")
        except Exception:
            continue
        by_id = lines.set_index("line_id")
        port_rows = collections.defaultdict(list)
        for r in ports.itertuples():
            port_rows[r.sheet_id].append((r.record_id, r.start_x, r.start_y, r.end_x, r.end_y))
        text_rows = collections.defaultdict(list)
        for r in texts.itertuples():
            text_rows[r.sheet_id].append(r)
        dot_rows = collections.defaultdict(list)
        for r in dots.itertuples():
            dot_rows[r.sheet_id].append((r.x, r.y))
        for g in groups.itertuples():
            mids = json.loads(g.member_line_ids) if isinstance(g.member_line_ids, str) else list(g.member_line_ids)
            members = [by_id.loc[m] for m in mids if m in by_id.index]
            if not members:
                continue
            horizontal = [l for l in members if abs(l.start_y - l.end_y) <= 1e-6]
            vertical = [l for l in members if abs(l.start_x - l.end_x) <= 1e-6]
            if len(horizontal) >= len(vertical):
                segs = sorted((min(l.start_x, l.end_x), max(l.start_x, l.end_x), (l.start_y + l.end_y) / 2) for l in horizontal)
                axis = "x"
            else:
                segs = sorted((min(l.start_y, l.end_y), max(l.start_y, l.end_y), (l.start_x + l.end_x) / 2) for l in vertical)
                axis = "y"
            cursor = None
            for lo, hi, cross in segs:
                if cursor is not None and 0.6 < lo - cursor <= 4.0:
                    a, b = cursor, lo
                    if axis == "x":
                        end_a, end_b = (a, cross), (b, cross)
                        in_bbox = [t for t in text_rows[g.sheet_id] if str(t.text or "").strip()
                                   and t.bbox_max_x >= a - 0.5 and t.bbox_min_x <= b + 0.5
                                   and t.bbox_max_y >= cross - 4 and t.bbox_min_y <= cross + 4]
                        in_insert = [t for t in text_rows[g.sheet_id]
                                     if a - 0.5 <= t.insert_x <= b + 0.5 and abs(t.insert_y - cross) <= 6]
                        dot = any(a - 0.6 <= x <= b + 0.6 and abs(y - cross) <= 6 for x, y in dot_rows[g.sheet_id])
                    else:
                        end_a, end_b = (cross, a), (cross, b)
                        in_bbox = [t for t in text_rows[g.sheet_id] if str(t.text or "").strip()
                                   and t.bbox_max_y >= a - 0.5 and t.bbox_min_y <= b + 0.5
                                   and t.bbox_max_x >= cross - 4 and t.bbox_min_x <= cross + 4]
                        in_insert = [t for t in text_rows[g.sheet_id]
                                     if a - 0.5 <= t.insert_y <= b + 0.5 and abs(t.insert_x - cross) <= 6]
                        dot = any(a - 0.6 <= y <= b + 0.6 and abs(x - cross) <= 6 for x, y in dot_rows[g.sheet_id])
                    touch_a = {p[0] for p in port_rows[g.sheet_id] if seg_dist(*end_a, *p[1:]) <= 1.0}
                    touch_b = {p[0] for p in port_rows[g.sheet_id] if seg_dist(*end_b, *p[1:]) <= 1.0}
                    rows.append({
                        "pid": pid, "sheet": g.sheet_id, "axis": axis, "orientation": g.orientation,
                        "gap": round(b - a, 2), "ports_both_sides": bool(touch_a and touch_b),
                        "ports_distinct": any(x != y for x in touch_a for y in touch_b),
                        "text_bbox": len(in_bbox) > 0, "text_insert": len(in_insert) > 0, "dot": bool(dot),
                    })
                cursor = hi if cursor is None else max(cursor, hi)
    frame = pd.DataFrame(rows)
    frame.to_pickle(OUT / "gaps_census.pkl")
    print("merged gaps (0.6 < gap <= 4):", len(frame))
    print(frame.groupby(["orientation", "text_bbox"]).size().to_dict())
    both = frame.ports_both_sides
    print("ports on both sides:", int(both.sum()))
    print("ports on both sides, no text (bbox), no dot:", int((both & ~frame.text_bbox & ~frame["dot"]).sum()))
    print("ports on both sides, distinct ports, no text (bbox), no dot:",
          int((frame.ports_distinct & ~frame.text_bbox & ~frame["dot"]).sum()))
    print("ports on both sides, no text (insertion window, GAP-2 test), no dot:",
          int((both & ~frame.text_insert & ~frame["dot"]).sum()))
    print("  of which the bbox test finds text covering the gap:",
          int((both & ~frame.text_insert & ~frame["dot"] & frame.text_bbox).sum()))


if __name__ == "__main__":
    main()
