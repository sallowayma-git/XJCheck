"""Short-bridge (yellow bar) equivalence of terminal-strip rows, from the drawn lines of the strip page (read-only).

A strip table draws, at one column x, a yellow circle at the centre of each row cell (centre y = row text y + 1.5)
and short vertical LINE segments (length 1.75) from a circle edge to the cell boundary. Two consecutive rows of the
same strip table are bridged when both halves of the segment chain exist at the boundary between them, at the same x.
The colour is not stored in the findings, so the rule uses the geometry only (verified against the DXF colours for
the p001 F0014 samples: the segments are colour 2 there).
"""
from __future__ import annotations

from collections import defaultdict

ROW_CENTRE_OFFSET = 1.5
CIRCLE_RADIUS = 0.75
SEGMENT_LENGTH = 1.75
TOL = 0.05


def _close(a, b, tol=TOL):
    return abs(a - b) <= tol


def bridge_pairs(strip_rows, lines):
    """strip_rows: dicts with record_id, file_id, group (header key), x, y. lines: dicts with file_id, x0,y0,x1,y1.

    Returns a list of (record_id_upper, record_id_lower, x) for the linked consecutive rows."""
    vertical = defaultdict(list)  # file_id -> list of (x, lo, hi)
    for line in lines:
        if not (_close(line["x0"], line["x1"], 0.01)):
            continue
        lo, hi = sorted((line["y0"], line["y1"]))
        if _close(hi - lo, SEGMENT_LENGTH, 0.02):
            vertical[line["file_id"]].append((line["x0"], lo, hi))
    groups = defaultdict(list)
    for row in strip_rows:
        if row.get("y") is None or row.get("x") is None:
            continue
        groups[(row["file_id"], row["group"])].append(row)
    links = []
    for (file_id, _), rows in groups.items():
        segments = vertical.get(file_id)
        if not segments or len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda r: -(float(r["y"]) + ROW_CENTRE_OFFSET))
        for upper, lower in zip(rows, rows[1:]):
            cu = float(upper["y"]) + ROW_CENTRE_OFFSET
            cl = float(lower["y"]) + ROW_CENTRE_OFFSET
            if not _close(cu - cl, 5.0, 0.05):
                continue
            mid = (cu + cl) / 2
            up_end, low_end = cu - CIRCLE_RADIUS, cl + CIRCLE_RADIUS
            xs_up = {x for x, lo, hi in segments if _close(lo, mid) and _close(hi, up_end) or _close(hi, mid) and _close(lo, up_end)}
            xs_low = {x for x, lo, hi in segments if _close(lo, mid) and _close(hi, low_end) or _close(hi, mid) and _close(lo, low_end)}
            shared = [x for x in xs_up if any(_close(x, y, 0.05) for y in xs_low)]
            if shared:
                links.append((upper["record_id"], lower["record_id"], min(shared)))
    return links


class Components:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def groups(self):
        out = defaultdict(set)
        for item in list(self.parent):
            out[self.find(item)].add(item)
        return list(out.values())
