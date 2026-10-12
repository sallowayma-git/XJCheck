"""Wire walk and device frame for the device-internal rule (WIRE-BREAK rounds 24-25). Pure geometry and SW marks.

From the open end of a wire, walk the segments that continue it: segments that share an end point (corners) and
segments whose end point lies on them (T junctions). The walk stops at a SuperWORKS symbol mark (a TERMPOINT): a
terminal body or an element pin is an end of the wire, never a connection through. Model-space lines and visible
LINE primitives of block instances (an element's own leads) are both walked.

A device frame is a closed axis-aligned rectangle of lines on the sheet that holds the device's terminal ports and
carries one label text equal to the terminal's device label, inside it or within FRAME_LABEL_GAP of its edge. A
frame is used only when exactly one such rectangle exists.
"""
from __future__ import annotations

import math
from collections import defaultdict

WALK_MAX_SEGMENTS = 400
WALK_POINT_TOL = 0.05
MARK_TOUCH_TOL = 1.0
FRAME_LABEL_GAP = 4.0
FRAME_EDGE_TOL = 0.05
FRAME_MIN_SIDE = 10.0
FRAME_MIN_LINE = 5.0


def point_segment_distance(point, segment) -> float:
    x1, y1, x2, y2 = segment
    px, py = point
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _on(point, segment) -> bool:
    return point_segment_distance(point, segment) <= WALK_POINT_TOL


def mark_touches(point, mark_segment) -> bool:
    return point_segment_distance(point, mark_segment) <= MARK_TOUCH_TOL + 1e-8


def segment_index(lines) -> dict[str, list[tuple[float, float, float, float]]]:
    """Model-space segments per sheet: (x1, y1, x2, y2). Block-internal lines (source_block_name) are excluded here."""
    index: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    for line in lines:
        if getattr(line, "source_block_name", None):
            continue
        index[line.sheet_id].append((float(line.start_x), float(line.start_y), float(line.end_x), float(line.end_y)))
    return index


def add_block_segments(index, block_rows) -> dict[str, list[tuple[float, float, float, float]]]:
    """Adds the visible LINE primitives of block instances (sheet_id, x1, y1, x2, y2 rows) to a segment index."""
    for sheet_id, x1, y1, x2, y2 in block_rows:
        index[sheet_id].append((float(x1), float(y1), float(x2), float(y2)))
    return index


def _touch_points(a, b):
    """End points of a and b that lie on the other segment (the contact points of two segments)."""
    points = []
    for end in ((a[0], a[1]), (a[2], a[3])):
        if _on(end, b):
            points.append(end)
    for end in ((b[0], b[1]), (b[2], b[3])):
        if _on(end, a):
            points.append(end)
    return points


def walk_wire(segments, start, marks=()) -> tuple[list, set, set]:
    """The wire that continues from start: its segments, its end points, and the SW marks it reaches.

    marks: (key, record_id, segment) symbol marks. A contact point that lies on a mark is not a connection: the mark
    ends the wire there and is reported as reached; the walk does not continue through a terminal or element pin.
    Capped at WALK_MAX_SEGMENTS segments.
    """
    segments = list(segments)
    reached: set[tuple[str, str]] = set()

    def marks_at(point):
        return [(key, rid) for key, rid, seg in marks if mark_touches(point, seg)]

    visited: list[tuple[float, float, float, float]] = []
    queue: list[tuple[float, float, float, float]] = []
    for segment in segments:
        if _on(start, segment):
            visited.append(segment)
            queue.append(segment)
    head = 0
    while head < len(queue) and len(visited) < WALK_MAX_SEGMENTS:
        current = queue[head]
        head += 1
        for other in segments:
            if other in visited:
                continue
            points = _touch_points(current, other)
            if not points:
                continue
            open_points = []
            for point in points:
                blocked = marks_at(point)
                if blocked:
                    reached.update(blocked)
                else:
                    open_points.append(point)
            if open_points:
                visited.append(other)
                queue.append(other)
    end_points = {(x, y) for seg in visited for (x, y) in ((seg[0], seg[1]), (seg[2], seg[3]))}
    for point in end_points:
        reached.update(marks_at(point))
    return visited, end_points, reached


def _inside(point, rect, tol=0.5) -> bool:
    x0, y0, x1, y1 = rect
    return x0 - tol <= point[0] <= x1 + tol and y0 - tol <= point[1] <= y1 + tol


def rectangles(segments) -> list[tuple[float, float, float, float]]:
    """Closed axis-aligned rectangles formed by the sheet's lines: two horizontal and two vertical lines that meet.

    Segments are model-space (x1, y1, x2, y2). Only lines of at least FRAME_MIN_LINE long count, and a rectangle needs
    both sides at least FRAME_MIN_SIDE long.
    """
    horizontal = defaultdict(list)
    vertical = defaultdict(list)
    for x1, y1, x2, y2 in segments:
        length = math.hypot(x2 - x1, y2 - y1)
        if length < FRAME_MIN_LINE:
            continue
        if abs(y1 - y2) <= FRAME_EDGE_TOL:
            horizontal[round(y1, 2)].append((min(x1, x2), max(x1, x2)))
        elif abs(x1 - x2) <= FRAME_EDGE_TOL:
            vertical[round(x1, 2)].append((min(y1, y2), max(y1, y2)))
    found = []
    by_extent = defaultdict(list)
    for y, spans in horizontal.items():
        for xa, xb in spans:
            by_extent[(round(xa, 2), round(xb, 2))].append(y)
    for (xa, xb), ys in by_extent.items():
        if xb - xa < FRAME_MIN_SIDE:
            continue
        ys = sorted(set(ys))
        for i, ya in enumerate(ys):
            for yb in ys[i + 1:]:
                if yb - ya < FRAME_MIN_SIDE:
                    continue
                if _spans_at(vertical, xa, ya, yb) and _spans_at(vertical, xb, ya, yb):
                    found.append((xa, ya, xb, yb))
    return found


def _spans_at(vertical, x, y0, y1) -> bool:
    for xv in vertical:
        if abs(xv - x) > FRAME_EDGE_TOL:
            continue
        for a, b in vertical[xv]:
            if a - FRAME_EDGE_TOL <= y0 and b + FRAME_EDGE_TOL >= y1:
                return True
    return False


def _text_gap(bbox, rect) -> float:
    """Chebyshev distance between a text bounding box and a rectangle (0 when they overlap)."""
    tx0, ty0, tx1, ty1 = bbox
    x0, y0, x1, y1 = rect
    gap_x = max(x0 - tx1, tx0 - x1, 0.0)
    gap_y = max(y0 - ty1, ty0 - y1, 0.0)
    return max(gap_x, gap_y)


def device_frame(rects, label, terminal_points, texts):
    """The one frame of the device: holds every terminal point and carries a label text equal to the device label.

    texts: (normalized_text, (x0, y0, x1, y1)) of the sheet. Returns the rectangle, or None when there is no frame or
    more than one (the frame rule is then not applicable).
    """
    if not label:
        return None
    holders = [r for r in rects if all(_inside(p, r) for p in terminal_points)]
    matches = [r for r in holders
               if any(text.strip().casefold() == label.casefold() and _text_gap(bbox, r) <= FRAME_LABEL_GAP
                      for text, bbox in texts)]
    return matches[0] if len(matches) == 1 else None


def inside_rect(point, rect) -> bool:
    return _inside(point, rect)
