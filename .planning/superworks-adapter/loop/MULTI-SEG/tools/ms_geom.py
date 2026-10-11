"""MULTI-SEG geometry and categorisation helpers (read-only).

Works on one Project (ms_common.Project) and one replayed split candidate. Everything is measured in the model space
of the file (the DXF drawing units); no block name, handle, project or label value is special-cased.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

import ms_common as M

DI = M.DI
GRID = 2.0
TEXT_PAD = 0.5          # axis margin when a text covers a gap
CROSS_TOL = 1.8         # horizontal band tolerance (line_groups.line_y_tolerance)
DOT_TOL = 0.6           # connect-dot clearance (same as the split replay)
CONTACT_FACTOR = 0.6    # SuperWORKS contact tolerance = 0.6 x TERMPOINT length

DIGITS = re.compile(r"^\d+$")


class Geo:
    """Per-project spatial indexes. Built once per project, used by all candidates of that project."""

    def __init__(self, proj: M.Project, cands_groups=None):
        self.proj = proj
        self.ports_by_file = defaultdict(list)     # file -> [(port, (ax, ay, bx, by))] TERMPOINT segments
        self.pins_by_file = defaultdict(list)      # file -> [(kind, record, a, b)] unregistered block termpoints
        self.texts_by_file = defaultdict(list)
        self.dots_by_file = defaultdict(list)
        self.model_by_file = defaultdict(list)     # model-space lines (no block), with keys
        for port in proj.ports:
            x1, y1, x2, y2 = (M.DI._number(port.get(k)) for k in ("start_x", "start_y", "end_x", "end_y"))
            if None in (x1, y1, x2, y2):
                continue
            self.ports_by_file[M.text(port["file_id"])].append((port, (x1, y1, x2, y2)))
        for block in proj.unreg:
            fid = M.text(block["file_id"])
            for tp in M.jload(block.get("termpoints"), []):
                a, b = tuple(tp["a"]), tuple(tp["b"])
                self.pins_by_file[fid].append((block, a, b, M.text(tp.get("number"))))
        for t in proj.texts:
            if M.text(t.get("source_block_name")) or not M.text(t.get("text")):
                continue
            self.texts_by_file[M.text(t["file_id"])].append(t)
        for d in proj.dots:
            x, y = M.DI._number(d.get("x")), M.DI._number(d.get("y"))
            if x is not None and y is not None:
                self.dots_by_file[M.text(d["file_id"])].append((x, y))
        for l in proj.lines:
            if M.text(l.get("source_block_name")):
                continue
            coords = [M.DI._number(l.get(k)) for k in ("start_x", "start_y", "end_x", "end_y")]
            if any(c is None for c in coords):
                continue
            self.model_by_file[M.text(l["file_id"])].append({
                "line_id": M.text(l["line_id"]), "handle": M.text(l["handle"]), "layer": M.text(l["layer"]),
                "sx": coords[0], "sy": coords[1], "ex": coords[2], "ey": coords[3]})

    # ---- queries -------------------------------------------------------------------------------------------
    def ports_at(self, fid, point, tol=None):
        """Ports whose TERMPOINT segment is touched by point (within the SuperWORKS contact tolerance)."""
        found = []
        for port, (x1, y1, x2, y2) in self.ports_by_file.get(fid, ()):
            length = math.hypot(x2 - x1, y2 - y1)
            t = tol if tol is not None else max(CONTACT_FACTOR * length, 0.05)
            if _pt_seg(point, (x1, y1), (x2, y2)) <= t + 1e-8:
                found.append(port)
        return found

    def pins_at(self, fid, point):
        found = []
        for block, a, b, number in self.pins_by_file.get(fid, ()):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            for p in (a, b):
                if math.hypot(point[0] - p[0], point[1] - p[1]) <= CONTACT_FACTOR * length + 1e-8:
                    found.append((block, number))
                    break
        return found

    def texts_in_rect(self, fid, x0, x1, y0, y1):
        """Model texts whose bbox overlaps the rectangle [x0,x1] x [y0,y1]."""
        out = []
        for t in self.texts_by_file.get(fid, ()):
            bx0, bx1 = sorted((float(t["bbox_min_x"]), float(t["bbox_max_x"])))
            by0, by1 = sorted((float(t["bbox_min_y"]), float(t["bbox_max_y"])))
            if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
                continue
            out.append(t)
        return out

    def dots_in_rect(self, fid, x0, x1, y0, y1):
        return [(x, y) for x, y in self.dots_by_file.get(fid, ()) if x0 <= x <= x1 and y0 <= y <= y1]

    def model_touching(self, fid, point, member_ids, tol=0.05):
        """Non-member model lines that have an end point at point, or pass through it (T or corner)."""
        ends, through = [], []
        px, py = point
        for l in self.model_by_file.get(fid, ()):
            if l["line_id"] in member_ids:
                continue
            if math.hypot(px - l["sx"], py - l["sy"]) <= tol or math.hypot(px - l["ex"], py - l["ey"]) <= tol:
                ends.append(l)
            elif _pt_seg(point, (l["sx"], l["sy"]), (l["ex"], l["ey"])) <= tol:
                through.append(l)
        return ends, through


def _pt_seg(p, a, b) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ls = dx * dx + dy * dy
    if ls == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ls))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def piece_extents(keys, segments, roots):
    """Pieces (end-point components) of one group: {root: {axis_min, axis_max, cross_values, keys}} (horizontal)."""
    pieces = defaultdict(lambda: {"keys": [], "xmin": math.inf, "xmax": -math.inf, "ys": []})
    for key in keys:
        seg = segments[key]
        root = roots[key]
        p = pieces[root]
        p["keys"].append(key)
        p["xmin"] = min(p["xmin"], seg["sx"], seg["ex"])
        p["xmax"] = max(p["xmax"], seg["sx"], seg["ex"])
        p["ys"].extend([seg["sy"], seg["ey"]])
    out = []
    for root, p in pieces.items():
        out.append({"root": root, "keys": p["keys"], "xmin": p["xmin"], "xmax": p["xmax"],
                    "y": (min(p["ys"]) + max(p["ys"])) / 2.0, "yspread": max(p["ys"]) - min(p["ys"])})
    out.sort(key=lambda p: (p["xmin"], p["xmax"]))
    return out


def pair_key(port):
    return (M.text(port.get("file_id")), M.text(port.get("insert_handle")))


def termpoint_mid(port):
    return DI._termpoint_mid(port)
