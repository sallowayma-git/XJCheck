"""Device-internal links of SuperWORKS device terminals (DEV-INT).

A device terminal ``装置端子`` (identity = device label + pin tail, e.g. ``1n705`` for label ``1n``, tail ``705``)
can be wired to a pin of an internal component of the same device (category ``内部元件`` or ``线圈`` whose label is
the device label). That wire is the device's own internal schematic, not an external connection: the internal
pin has no identity of its own, so the terminal stays uncovered by pairs. This module records such a wire as a
*device-internal link*, a coverage fact only. It creates no Pair, changes no issue, and never names the far end.

A link is built for an eligible device terminal (wire contact and resolved label) when, for exactly one of its
wires, the wire touches exactly two ports of its file: the terminal and one internal component port whose label
equals the terminal's device label after normalisation. A wire is one SuperWORKS wire: the union of the line
groups its LINE segments lie in (``wire_keys_from_lines``). Every other shape is counted, not linked:

- the wire has no other port (dangling), or more than one other port (a multi-end wire, left to the pair rules);
- the other port is a terminal, device terminal or any other category;
- the component label differs from the device label; a related label (``1-1n`` for ``1n``) is counted apart;
- the terminal has more than one such wire.

``pcl_corroborated`` is True when a PCL wire-route row, read from the device's wiring diagram, names the same
terminal identity as its LOCAL end (its logical pin number therefore equals the tail). It is evidence only, and
the link is recorded either way.

G1P extends the wire rule to an unregistered SYMB2 block (a block with LD_SYMB2_LABEL and without
LD_SYMB2_SPECIAL, so SuperWORKS registers no port for it). When a device terminal's wire has no other SuperWORKS
port, its far end is the free end of the wire (an end point no other segment of the same wire shares, and not the
terminal's own contact). If that far end lies on a TERMPOINT end of exactly one unregistered block, and the block's
label equals the device label after normalisation, the wire is a device-internal wire with ``source`` set to
``unregistered_symb2_pin``. The block is never a port: nothing is paired, and no issue changes. Other cases are
counted under ``unregistered:<reason>``: no free far end, no block at the far end, several blocks, an unresolved
label, or a different or related label.

GAP2-S adds a terminal-body split. A device terminal is drawn as a body whose two TERMPOINTs are the contacts of
its two wires: one wire runs into each side. The line-group builder joins two collinear segments whose gap is at
most 4.0, and the body gap is 2.5, so one SuperWORKS wire can hold both sides and several ports. When two device
terminal ports of one insert with one identity have their contacts on the two sides of one line group, the group
is cut at that gap (``split_terminal_wires``). The split is made here only: line groups and pairs are unchanged.
A cut is made only when all of these hold; otherwise it is refused and counted under ``split_refused:<reason>``:
the group consists of exactly two end-point components, one holding each contact; the two contacts lie on one
axis line; the body (the distance of the insert's two TERMPOINT midpoints) is at least SPLIT_MIN_BODY_WIDTH;
their distance is at least SPLIT_MIN_GAP and equals the body width within SPLIT_WIDTH_FACTOR; no model-space line
crosses the open gap; no connection dot lies at the open gap. DEV-INT-DISCARD: the device-internal rule is one function, ``device_internal_verdict``, shared by this module and
the pair layer. The pair layer discards a non-discard pair that the rule accepts (``discard_reason``
``device_internal``), so an internal element that carries an identity is no longer an exception: its wire is a
device-internal link like any other. The GAP2-S element guard is therefore gone.

The functions take plain dictionaries, so they run on the in-memory production records and on the written
parquet rows alike. Identities are compared casefold-exact; nothing is matched by prefix or by value.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict

DEVICE_CATEGORY = "装置端子"
INTERNAL_CATEGORIES = frozenset({"内部元件", "线圈"})
RELATION = "device_internal"
SOURCE_SW_ELEMENT = "sw_internal_element"
SOURCE_UNREGISTERED = "unregistered_symb2_pin"
# Same contact tolerance as a SuperWORKS port: 0.6 x the length of its TERMPOINT segment (superworks_semantics).
CONTACT_TOLERANCE_FACTOR = 0.6
# A far end is free when no other segment end of the wire coincides with it (rounded to this many decimals).
_POINT_DECIMALS = 3
_GRID_CELL = 2.0
_LEADING_DIGITS_DASH = re.compile(r"^\d+-")
# Terminal-body split (see the module docstring). Gap and width are measured in drawing units.
SPLIT_MIN_GAP = 0.5
# A device terminal body spanned by two TERMPOINTs (two-port terminal). Three-pin symbols have a 1.25 pitch and
# are not two-port bodies, so a cut across a span narrower than this is refused (body_too_narrow).
SPLIT_MIN_BODY_WIDTH = 2.0
SPLIT_LATERAL_TOL = 1.0
SPLIT_WIDTH_FACTOR = 0.1
SPLIT_SHRINK = 0.05
SPLIT_LINE_CLEARANCE = 0.02
SPLIT_DOT_CLEARANCE = 0.6
_ENDPOINT_TOL = 1e-3
_CONTACT_TOL = 0.01


def _text(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value).strip()


def label_of(port) -> tuple[str, bool]:
    label = port.get("label") or {}
    if isinstance(label, str):
        label = json.loads(label or "{}")
    return _text(label.get("normalized")), bool(label.get("resolved"))


def _contacts_of(port) -> list[dict]:
    contacts = port.get("wire_contacts") or []
    if isinstance(contacts, str):
        contacts = json.loads(contacts or "[]")
    return list(contacts)


def _ends_of(route) -> list[dict]:
    ends = route.get("ends")
    if ends is None:
        ends = json.loads(route.get("ends_json") or "[]")
    return list(ends)


def _related(a: str, b: str) -> bool:
    """Labels that look like the same device written with a station prefix (``1-1n`` and ``1n``)."""
    if a == b:
        return False
    base_a = _LEADING_DIGITS_DASH.sub("", a)
    base_b = _LEADING_DIGITS_DASH.sub("", b)
    return base_a == base_b or a.endswith("-" + b) or b.endswith("-" + a)


DEVICE_INTERNAL = "device_internal"
_PIN_NUMBER = re.compile(r"[0-9]+")


def is_terminal_form(identity, label) -> bool:
    """Whether an identity has the form of a device terminal: the device label followed by a pure-digit pin number.

    ``1-21n332`` is terminal-form for ``1-21n``; ``1n-DC``, ``3-4n-I`` and ``1n-3`` are not (a dash separates a pin or
    a function name from the label). Used to tell a terminal-to-terminal connection, which is an external wire, from
    a terminal-to-element connection, which is internal. Casefold-exact on the label, no value is special-cased.
    """
    identity, label = _text(identity), _text(label)
    if not identity or not label or not identity.casefold().startswith(label.casefold()):
        return False
    return bool(_PIN_NUMBER.fullmatch(identity[len(label):]))


def _element_form(identity, label) -> bool:
    """A label followed by a dash and a pin or function name: 1n-DC, 3-4n-I, 1n-3 (the element's own identity)."""
    identity, label = _text(identity), _text(label)
    return bool(label) and identity.casefold().startswith(label.casefold() + "-") and len(identity) > len(label) + 1


def device_internal_verdict(terminal, other) -> str:
    """The device-internal rule: one device terminal wired to an internal pin of its own device.

    terminal: category, identity, label and label_resolved of the SuperWORKS device-terminal end. Its identity is the
        device label plus a pin tail (``1n705`` for ``1n``). other: category, label and label_resolved of the other
        end. ``unregistered`` is True for an unregistered SYMB2 pin, which has no SuperWORKS port and so no category.
        The other end's identity is not compared: an internal pin may have none.
    Returns DEVICE_INTERNAL, or the first reason the two ends are not one device's internal connection. Labels are
    compared casefold-exact; a related label (``1-1n`` for ``1n``) gives its own reason and is never a match.
    """
    if _text(terminal.get("category")) != DEVICE_CATEGORY:
        return "terminal_not_device"
    label = _text(terminal.get("label"))
    identity = _text(terminal.get("identity"))
    if not (terminal.get("label_resolved") and label):
        return "terminal_label_unresolved"
    if not identity.casefold().startswith(label.casefold()) or len(identity) <= len(label):
        return "terminal_identity_not_label_prefixed"
    category = _text(other.get("category"))
    if not (other.get("unregistered") or category in INTERNAL_CATEGORIES):
        return f"other_end_category:{category or 'none'}"
    other_label = _text(other.get("label"))
    if not (other.get("label_resolved") and other_label):
        return "other_label_unresolved"
    if other_label.casefold() != label.casefold():
        return "other_label_related" if _related(other_label.casefold(), label.casefold()) else "other_label_differs"
    # An SW element's identity decides what the connection is. A terminal-form identity (device label + pure-digit
    # pin) makes it a terminal-to-terminal wire, external, not internal. An identity with a dash after the device
    # label (1n-DC, 3-4n-I, 1n-3) is an element pin or function name: internal. No identity, or a bare number with
    # no label (the element's own pin number), is an unidentified element pin: internal. Any other identity (it
    # begins with a different name) names something this rule cannot place, so it is not discarded.
    # Coils and unregistered pins are internal whatever their identity.
    if category == "内部元件":
        identity = _text(other.get("identity"))
        if is_terminal_form(identity, label):
            return "other_identity_terminal_form"
        if identity and not _PIN_NUMBER.fullmatch(identity) and not _element_form(identity, label):
            return "other_identity_foreign"
    return DEVICE_INTERNAL


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _point_key(point) -> tuple[float, float]:
    return round(point[0], _POINT_DECIMALS), round(point[1], _POINT_DECIMALS)


class _PinIndex:
    """TERMPOINT end points of the unregistered blocks of one project, bucketed per file.

    An end point of a TERMPOINT segment is a pin contact point of its block; it accepts a wire end within
    CONTACT_TOLERANCE_FACTOR x the segment length, the same contact tolerance SuperWORKS ports use.
    """

    def __init__(self, blocks):
        self.cells: dict[str, dict[tuple[int, int], list]] = defaultdict(lambda: defaultdict(list))
        self.max_tolerance: dict[str, float] = defaultdict(float)
        for block in blocks:
            file_id = _text(block.get("file_id"))
            for termpoint in block.get("termpoints") or []:
                a, b = tuple(termpoint["a"]), tuple(termpoint["b"])
                tolerance = CONTACT_TOLERANCE_FACTOR * _dist(a, b)
                self.max_tolerance[file_id] = max(self.max_tolerance[file_id], tolerance)
                for point in (a, b):
                    cell = (math.floor(point[0] / _GRID_CELL), math.floor(point[1] / _GRID_CELL))
                    self.cells[file_id][cell].append((block, point, tolerance, _text(termpoint.get("number"))))

    def at(self, file_id: str, point) -> list[tuple[dict, tuple[float, float], str]]:
        """(block, pin point, pin number) of every block end point this wire end point touches."""
        if file_id not in self.cells:
            return []
        reach = math.ceil((self.max_tolerance[file_id] + 1e-8) / _GRID_CELL)
        cx, cy = math.floor(point[0] / _GRID_CELL), math.floor(point[1] / _GRID_CELL)
        found = []
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                for block, pin, tolerance, number in self.cells[file_id].get((cx + dx, cy + dy), ()):
                    if _dist(point, pin) <= tolerance + 1e-8:
                        found.append((block, pin, number))
        return found


def _far_pin(port_file: str, contact, wire_key, members, wire_endpoints, pins, label: str, identity: str):
    """Decide the far end of a single-end wire of a device terminal against the unregistered blocks.

    Returns (candidate, reason, detail). candidate is None unless the far end lies on exactly one block whose
    label is the device label. reason names the outcome for the counters; detail names the block and the points
    it was decided on, when there is one (for the decision table).
    """
    device_point = None
    if contact.get("x") is not None and contact.get("y") is not None:
        device_point = (float(contact["x"]), float(contact["y"]))
    ends = []
    for member_file, member_handle in members.get(wire_key, [wire_key]):
        for point in (wire_endpoints.get((member_file, member_handle)) or {}).values():
            ends.append(tuple(point))
    counts = Counter(_point_key(point) for point in ends)
    # The terminal's own contact is not a far end; without a recorded contact point only shared ends are dropped.
    far_ends = [point for point in ends if counts[_point_key(point)] == 1
                and (device_point is None or _dist(point, device_point) > 1e-6)]
    if not far_ends:
        return None, "no_free_far_end", {}
    hits = {}
    for far in far_ends:
        for block, pin, number in pins.at(port_file, far):
            hits.setdefault(block["record_id"], (block, far, pin, number))
    if not hits:
        return None, "no_far_pin", {"far": far_ends[0]}
    if len(hits) > 1:
        return None, "multiple_blocks", {"blocks": sorted(hits)}
    block, far, pin, number = next(iter(hits.values()))
    detail = {"block_record_id": block.get("record_id"), "block_insert_handle": _text(block.get("insert_handle")),
              "block_label": _text(block.get("label_value")), "far": far, "pin": pin, "number": number}
    verdict = device_internal_verdict(
        {"category": DEVICE_CATEGORY, "identity": identity, "label": label, "label_resolved": True},
        {"unregistered": True, "label": _text(block.get("label_value")),
         "label_resolved": bool(block.get("label_resolved"))})
    if verdict != DEVICE_INTERNAL:
        reason = {"other_label_unresolved": "label_unresolved", "other_label_related": "label_related",
                  "other_label_differs": "label_differs"}.get(verdict, verdict)
        return None, reason, detail
    return {"block": block, "far": far, "pin": pin, "number": number}, "candidate", detail


def pcl_index(wire_routes) -> dict[str, list[str]]:
    """PCL LOCAL identity (casefold) -> record ids of the PCL rows that name it."""
    index = defaultdict(list)
    for route in wire_routes:
        if _text(route.get("source_kind")) != "PCL":
            continue
        for end in _ends_of(route):
            if end.get("role") != "LOCAL":
                continue
            identity = _text(end.get("identity"))
            if identity:
                index[identity.casefold()].append(_text(route.get("record_id")))
    return index


def wire_keys_from_lines(lines, line_groups) -> dict:
    """(file_id, wire handle) -> wire key, where one SuperWORKS wire is the union of the line groups it lies in.

    lines: dicts with file_id, line_id, handle and source_block_name (block-internal lines never own a wire handle,
        as in the extractor). line_groups: dicts with file_id and member_line_ids (a list or JSON). Lines in no group
        are left out, so their contact handle stands for the wire.
    """
    parent = {}

    def find(item):
        parent.setdefault(item, item)
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for group in line_groups:
        members = group.get("member_line_ids") or []
        if isinstance(members, str):
            members = json.loads(members or "[]")
        members = [(_text(group.get("file_id")), _text(member)) for member in members]
        for member in members:
            find(member)
        for member in members[1:]:
            parent[find(member)] = find(members[0])
    keys = {}
    ordered = sorted(lines, key=lambda line: bool(_text(line.get("source_block_name"))))
    for line in ordered:
        member = (_text(line.get("file_id")), _text(line.get("line_id")))
        handle = _text(line.get("handle"))
        if member in parent and handle:
            keys.setdefault((_text(line.get("file_id")), handle), (member[0], "W:" + find(member)[1]))
    return keys


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _termpoint_mid(port):
    coords = [_number(port.get(key)) for key in ("start_x", "start_y", "end_x", "end_y")]
    if any(c is None for c in coords):
        return None
    return ((coords[0] + coords[2]) / 2.0, (coords[1] + coords[3]) / 2.0)


def _ends(seg):
    return (seg["sx"], seg["sy"]), (seg["ex"], seg["ey"])


def _at_endpoint(seg, point) -> bool:
    return any(_dist(point, end) <= _CONTACT_TOL for end in _ends(seg))


def _point_segment_distance(point, a, b) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return _dist(point, a)
    t = max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / length_sq))
    return _dist(point, (ax + t * dx, ay + t * dy))


def _segment_distance(a, b, c, d) -> float:
    """Distance between the closed segments ab and cd (0 when they cross)."""
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = side(c, d, a), side(c, d, b)
    d3, d4 = side(a, b, c), side(a, b, d)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(_point_segment_distance(a, c, d), _point_segment_distance(b, c, d),
               _point_segment_distance(c, a, b), _point_segment_distance(d, a, b))


def _end_point_components(keys, segments) -> dict:
    """Components of one line group's members, joined where two member end points coincide."""
    parent = {key: key for key in keys}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    owners = defaultdict(list)
    for key in keys:
        for end in _ends(segments[key]):
            owners[_point_key(end)].append(key)
    for members in owners.values():
        for other in members[1:]:
            parent[find(other)] = find(members[0])
    return {key: find(key) for key in keys}


def _judge_split(a, b, ca, cb, component_count, file_id, dots, model_segments):
    """(refusal reason, None) or (None, geometry) for two device-terminal contacts of one group."""
    if component_count != 2:
        return "components_not_two", None
    mid_a, mid_b = _termpoint_mid(a), _termpoint_mid(b)
    if mid_a is None or mid_b is None:
        return "no_termpoint", None
    body = _dist(mid_a, mid_b)
    if body <= 0:
        return "no_body_width", None
    if body < SPLIT_MIN_BODY_WIDTH:
        return "body_too_narrow", None
    dx, dy = abs(cb[0] - ca[0]), abs(cb[1] - ca[1])
    gap = math.hypot(dx, dy)
    if gap < SPLIT_MIN_GAP:
        return "coincident_contacts", None
    if min(dx, dy) > SPLIT_LATERAL_TOL:
        return "not_axis_aligned", None
    if abs(gap - body) > SPLIT_WIDTH_FACTOR * body:
        return "width_mismatch", None
    ux, uy = (cb[0] - ca[0]) / gap, (cb[1] - ca[1]) / gap
    start = (ca[0] + SPLIT_SHRINK * ux, ca[1] + SPLIT_SHRINK * uy)
    end = (cb[0] - SPLIT_SHRINK * ux, cb[1] - SPLIT_SHRINK * uy)
    lo_x, hi_x = min(start[0], end[0]) - 1.0, max(start[0], end[0]) + 1.0
    lo_y, hi_y = min(start[1], end[1]) - 1.0, max(start[1], end[1]) + 1.0
    for seg in model_segments.get(file_id, ()):
        if max(seg["sx"], seg["ex"]) < lo_x or min(seg["sx"], seg["ex"]) > hi_x:
            continue
        if max(seg["sy"], seg["ey"]) < lo_y or min(seg["sy"], seg["ey"]) > hi_y:
            continue
        if _segment_distance(start, end, (seg["sx"], seg["sy"]), (seg["ex"], seg["ey"])) <= SPLIT_LINE_CLEARANCE:
            return "gap_crossed", None
    for dot in dots.get(file_id, ()):
        if _point_segment_distance(dot, start, end) <= SPLIT_DOT_CLEARANCE:
            return "dot_in_gap", None
    return None, {"body_width": body, "gap": gap, "lateral": min(dx, dy)}


def split_terminal_wires(ports, lines, line_groups, connect_dots=()) -> dict:
    """Cut line groups at the body gap between the two contacts of one device terminal (GAP2-S).

    ports: as build_device_internal_links; a device terminal needs its TERMPOINT (start_x, start_y, end_x, end_y).
    lines: dicts with file_id, line_id, handle, source_block_name and the end points sx, sy, ex, ey.
    line_groups: dicts with file_id and member_line_ids (a list or JSON). connect_dots: dicts with file_id, x, y.

    Returns {"mapping": {(file_id, handle): wire key}, "splits": [...], "refusals": Counter, "split_wire_keys": set,
    "partners": {wire key: [partner port ids]}}. A cut is applied to a whole line group, and only when it is
    verified: after the cut the two contacts must lie on different wire keys, or the cut is refused (still_merged).
    Inputs are read only; the mapping of an unsplit group equals wire_keys_from_lines on the same inputs.
    """
    refusals = Counter()
    segments = {}
    handle_keys = defaultdict(list)
    model_segments = defaultdict(list)
    for line in lines:
        file_id, line_id = _text(line.get("file_id")), _text(line.get("line_id"))
        coords = [_number(line.get(key)) for key in ("sx", "sy", "ex", "ey")]
        if not line_id or any(c is None for c in coords):
            continue
        handle = _text(line.get("handle"))
        seg = {"file_id": file_id, "handle": handle, "sx": coords[0], "sy": coords[1], "ex": coords[2], "ey": coords[3]}
        segments[(file_id, line_id)] = seg
        if handle:
            handle_keys[(file_id, handle)].append((file_id, line_id))
        if not _text(line.get("source_block_name")):
            model_segments[file_id].append(seg)
    groups = []
    for group in line_groups:
        file_id = _text(group.get("file_id"))
        members = group.get("member_line_ids") or []
        if isinstance(members, str):
            members = json.loads(members or "[]")
        keys = list(dict.fromkeys(key for key in ((file_id, _text(m)) for m in members) if key in segments))
        if len(keys) >= 2:
            groups.append(keys)
    group_roots, members_of = [], defaultdict(list)
    for index, keys in enumerate(groups):
        group_roots.append(_end_point_components(keys, segments))
        for key in keys:
            members_of[key].append(index)
    dots = defaultdict(list)
    for dot in connect_dots:
        x, y = _number(dot.get("x")), _number(dot.get("y"))
        if x is not None and y is not None:
            dots[_text(dot.get("file_id"))].append((x, y))

    contacts_in = defaultdict(list)
    for port in ports:
        if _text(port.get("category")) != DEVICE_CATEGORY or not _text(port.get("endpoint_identity")):
            continue
        file_id = _text(port.get("file_id"))
        for contact in _contacts_of(port):
            handle = _text(contact.get("wire_handle"))
            x, y = _number(contact.get("x")), _number(contact.get("y"))
            if not handle or x is None or y is None:
                continue
            for key in handle_keys.get((file_id, handle), ()):
                if not _at_endpoint(segments[key], (x, y)):
                    continue
                for index in members_of.get(key, ()):
                    contacts_in[index].append((port, handle, group_roots[index][key], (x, y)))

    accepted, examined = [], 0
    for index, items in contacts_in.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (a, handle_a, root_a, ca), (b, handle_b, root_b, cb) = items[i], items[j]
                if root_a == root_b or a.get("record_id") == b.get("record_id"):
                    continue
                if (a.get("file_id"), a.get("insert_handle")) != (b.get("file_id"), b.get("insert_handle")):
                    continue
                if _text(a.get("endpoint_identity")).casefold() != _text(b.get("endpoint_identity")).casefold():
                    continue
                examined += 1
                file_id = _text(a.get("file_id"))
                reason, geometry = _judge_split(a, b, ca, cb, len(set(group_roots[index].values())), file_id,
                                                dots, model_segments)
                if reason:
                    refusals[reason] += 1
                    continue
                accepted.append({"group": index, "file_id": file_id, "insert_handle": _text(a.get("insert_handle")),
                    "endpoint_identity": _text(a.get("endpoint_identity")), "port_a": a.get("record_id"),
                    "port_b": b.get("record_id"), "handle_a": handle_a, "handle_b": handle_b,
                    "root_a": root_a, "root_b": root_b, **geometry})

    def pieces(active):
        cut = {record["group"]: record for record in active}
        result = []
        for index, keys in enumerate(groups):
            if index not in cut:
                result.append({"file_id": keys[0][0], "member_line_ids": [key[1] for key in keys]})
                continue
            record = cut[index]
            for root in (record["root_a"], record["root_b"]):
                members = [key for key in keys if group_roots[index][key] == root]
                result.append({"file_id": keys[0][0], "member_line_ids": [key[1] for key in members]})
        return result

    def key_of(mapping, file_id, handle):
        return mapping.get((file_id, handle), (file_id, handle))

    active = list(accepted)
    for _ in range(len(accepted) + 1):
        mapping = wire_keys_from_lines(lines, pieces(active))
        still = [record for record in active
                 if key_of(mapping, record["file_id"], record["handle_a"])
                 == key_of(mapping, record["file_id"], record["handle_b"])]
        if not still:
            break
        for record in still:
            active.remove(record)
            refusals["still_merged"] += 1
    mapping = wire_keys_from_lines(lines, pieces(active))
    split_wire_keys, partners = set(), defaultdict(list)
    for record in active:
        partners[key_of(mapping, record["file_id"], record["handle_a"])].append(record["port_b"])
        partners[key_of(mapping, record["file_id"], record["handle_b"])].append(record["port_a"])
        for key in groups[record["group"]]:
            handle = segments[key]["handle"]
            if handle:
                split_wire_keys.add(key_of(mapping, key[0], handle))
    splits = [{"file_id": r["file_id"], "insert_handle": r["insert_handle"], "endpoint_identity": r["endpoint_identity"],
               "port_a": r["port_a"], "port_b": r["port_b"], "handle_a": r["handle_a"], "handle_b": r["handle_b"],
               "body_width": r["body_width"], "gap": r["gap"], "lateral": r["lateral"], "split_reason": "terminal_body"}
              for r in active]
    return {"mapping": mapping, "splits": splits, "examined": examined, "refusals": refusals,
            "split_wire_keys": split_wire_keys, "partners": dict(partners)}


def _element_identity(element, element_identities) -> str:
    """The identity of an internal element end: its own port identity, else the identity the pair layer read for
    that port (a terminal-form identity sits in the pair's text, not on the SW port)."""
    own = _text(element.get("endpoint_identity"))
    if own:
        return own
    return _text((element_identities or {}).get(element.get("record_id")))


def build_device_internal_links(ports, wire_routes=(), wire_group_of=None, unregistered=(), wire_endpoints=None,
                                terminal_split=None, element_identities=None) -> dict:
    """Device-internal links of the eligible device terminals of one project.

    ports: dicts with record_id, file_id, sheet_id, insert_handle, port_number, category, endpoint_identity,
        label (dict with normalized and resolved, or JSON) and wire_contacts (dicts with wire_handle, wire_side,
        x and y, or JSON).
    wire_routes: the sw_wire_routes rows of the project (dicts with source_kind, record_id, and ends or ends_json).
    wire_group_of: optional mapping (file_id, wire_handle) -> wire key. A SuperWORKS wire may be drawn as
        several LINE segments; the producer's line group names them as one wire. Without the mapping the
        wire is the contact's own handle.
    unregistered: dicts of the unregistered SYMB2 blocks (record_id, file_id, insert_handle, label_value,
        label_resolved, termpoints with a and b end points). Read only.
    wire_endpoints: {(file_id, wire handle): {wire_side: (x, y)}} end points of every model-space wire.

    terminal_split: optional {"lines": [...], "line_groups": [...], "connect_dots": [...]} (see the module docstring).
        When given, the wire mapping is computed here from these inputs with the body-gap cuts applied, and
        wire_group_of is not used. Without it the behaviour is the unsplit rule of the module.

    Returns {"links": [...], "covered": {device port record_id: [link_id]}, "stats": {...}, "terminal_splits": [...]}.
    Ports are read only.
    """
    stats = Counter()
    decisions = []
    split_wire_keys, partners, terminal_splits = set(), {}, []
    if terminal_split is not None:
        split = split_terminal_wires(ports, terminal_split["lines"], terminal_split["line_groups"],
                                     terminal_split.get("connect_dots", ()))
        wire_group_of = split["mapping"]
        split_wire_keys, partners, terminal_splits = split["split_wire_keys"], split["partners"], split["splits"]
        stats["split_examined"] = split["examined"]
        stats["split_accepted"] = len(terminal_splits)
        for reason, count in split["refusals"].items():
            stats[f"split_refused:{reason}"] += count
    by_wire = defaultdict(list)
    group_of = wire_group_of or {}
    members = defaultdict(list)
    for member, wire_key in group_of.items():
        if member != wire_key:
            members[wire_key].append(member)
    for port in ports:
        for contact in _contacts_of(port):
            handle = _text(contact.get("wire_handle"))
            if handle:
                key = (_text(port.get("file_id")), handle)
                wire_key = group_of.get(key, key)
                if all(member.get("record_id") != port.get("record_id") for member in by_wire[wire_key]):
                    by_wire[wire_key].append(port)
    pcl = pcl_index(wire_routes)
    pins = _PinIndex(unregistered)
    endpoints = wire_endpoints or {}

    links, covered = [], defaultdict(list)
    for port in ports:
        if port.get("category") != DEVICE_CATEGORY:
            continue
        stats["device_terminals"] += 1
        contacts = _contacts_of(port)
        label, resolved = label_of(port)
        identity = _text(port.get("endpoint_identity"))
        if not contacts:
            stats["excluded:no_wire_contact"] += 1
            continue
        if not (resolved and label):
            stats["excluded:label_unresolved"] += 1
            continue
        stats["eligible"] += 1
        if not identity:
            stats["excluded:identity_missing"] += 1
            continue
        if not identity.casefold().startswith(label.casefold()) or len(identity) <= len(label):
            stats["excluded:identity_not_label_prefixed"] += 1
            continue
        tail = identity[len(label):]
        candidates = []
        seen_wires = set()
        for contact in contacts:
            handle = _text(contact.get("wire_handle"))
            if not handle:
                continue
            file_key = (_text(port.get("file_id")), handle)
            wire = group_of.get(file_key, file_key)
            if wire in seen_wires:
                continue
            seen_wires.add(wire)
            wire_ports = by_wire.get(wire, [])
            others = [other for other in wire_ports if other.get("record_id") != port.get("record_id")]
            if not others:
                # G1P: a single-end wire may end on an unregistered SYMB2 pin instead of a SuperWORKS port.
                stats["single_end_wires"] += 1
                far, reason, detail = _far_pin(_text(port.get("file_id")), contact, wire, members, endpoints, pins,
                                               label, identity)
                stats[f"unregistered:{reason}"] += 1
                decisions.append({"port_id": port.get("record_id"), "file_id": port.get("file_id"),
                    "sheet_id": port.get("sheet_id"), "device_label": label, "endpoint_identity": identity,
                    "wire_handle": handle, "reason": reason, **detail})
                if far is None:
                    stats["excluded:wire_no_other_port"] += 1
                else:
                    candidates.append({"handle": handle, "element": None, "wire_ports": wire_ports, "far": far, "wire": wire})
                continue
            if len(others) > 1:
                reason = "excluded:wire_multi_end_internal" if all(
                    o.get("category") in INTERNAL_CATEGORIES for o in others) else "excluded:wire_multi_end"
                stats[reason] += 1
                continue
            element = others[0]
            element_label, element_resolved = label_of(element)
            element_id = _element_identity(element, element_identities)
            verdict = device_internal_verdict(
                {"category": DEVICE_CATEGORY, "identity": identity, "label": label, "label_resolved": resolved},
                {"category": element.get("category"), "label": element_label, "label_resolved": element_resolved,
                 "identity": element_id})
            if verdict != DEVICE_INTERNAL:
                stats[f"excluded:{verdict}"] += 1
                continue
            candidates.append({"handle": handle, "element": element, "wire_ports": wire_ports, "far": None, "wire": wire})
        if not candidates:
            continue
        if len(candidates) > 1:
            stats["excluded:multiple_internal_wires"] += 1
            continue
        candidate = candidates[0]
        handle, element, wire_ports, far = candidate["handle"], candidate["element"], candidate["wire_ports"], candidate["far"]
        wire = candidate["wire"]
        split_reason = "terminal_body" if wire in split_wire_keys else None
        if split_reason:
            stats["linked_on_split_wire"] += 1
        pcl_ids = sorted(set(pcl.get(identity.casefold(), [])))
        if element is not None:
            link_id = "XDI:" + hashlib.sha1(
                f"{port.get('record_id')}|{element.get('record_id')}|{handle}".encode("utf-8")).hexdigest()[:16]
            element_fields = {
                "source": SOURCE_SW_ELEMENT, "element_port_id": element.get("record_id"),
                "element_block_record_id": None,
                "element_insert_handle": _text(element.get("insert_handle")),
                "element_label": _text(label_of(element)[0]),
                "element_identity": _element_identity(element, element_identities) or None,
                "element_port_number": _text(element.get("port_number")),
                "far_x": None, "far_y": None, "pin_x": None, "pin_y": None,
            }
            stats["linked_sw_element"] += 1
            stats["linked_element_identified"] += int(bool(_element_identity(element, element_identities)))
        else:
            block = far["block"]
            link_id = "XDI:" + hashlib.sha1(
                f"{port.get('record_id')}|{block.get('record_id')}|{handle}".encode("utf-8")).hexdigest()[:16]
            element_fields = {
                "source": SOURCE_UNREGISTERED, "element_port_id": None,
                "element_block_record_id": block.get("record_id"),
                "element_insert_handle": _text(block.get("insert_handle")),
                "element_label": _text(block.get("label_value")),
                "element_identity": None,
                "element_port_number": far["number"],
                "far_x": far["far"][0], "far_y": far["far"][1], "pin_x": far["pin"][0], "pin_y": far["pin"][1],
            }
            stats["linked_unregistered"] += 1
        link = {
            "link_id": link_id, "relation": RELATION, "port_id": port.get("record_id"),
            "file_id": port.get("file_id"), "sheet_id": port.get("sheet_id"),
            "device_label": label, "endpoint_identity": identity, "pin_tail": tail,
            "wire_handle": handle, **element_fields,
            "wire_port_ids": sorted(_text(o.get("record_id")) for o in wire_ports),
            "pcl_corroborated": bool(pcl_ids), "pcl_record_ids": pcl_ids,
            "split_reason": split_reason, "split_partner_port_ids": sorted(partners.get(wire, [])),
        }
        links.append(link)
        covered[port.get("record_id")].append(link_id)
        stats["linked"] += 1
        stats["pcl_corroborated"] += int(bool(pcl_ids))
    stats["linked_ports"] = len(covered)
    return {"links": links, "covered": dict(covered), "stats": dict(stats), "unregistered_decisions": decisions,
            "terminal_splits": terminal_splits}


def wire_members_of_links(links, wire_mapping) -> dict:
    """link_id -> sorted handles of the SuperWORKS wire that the link's terminal contact lies on (GAP-COORD).

    wire_mapping: {(file_id, handle): wire key} as returned by ``split_terminal_wires(...)["mapping"]``. The members of a
    wire are every handle that maps to the contact's wire key. A contact handle outside the mapping is its own wire.
    Read only; links are not changed.
    """
    by_key = defaultdict(set)
    for (file_id, handle), key in wire_mapping.items():
        by_key[key].add(handle)
    result = {}
    for link in links:
        file_id, handle = _text(link.get("file_id")), _text(link.get("wire_handle"))
        key = wire_mapping.get((file_id, handle), (file_id, handle))
        members = by_key.get(key) or {handle}
        result[link["link_id"]] = sorted(set(members) | {handle})
    return result


def device_internal_wire_index(links) -> dict:
    """(file_id, terminal port_id) -> frozenset of the wire handles of that port's device-internal link (GAP-COORD).

    A terminal has at most one device-internal link (two candidate wires make it ambiguous and no link is built), so
    the index names the one wire the rule judged internal. Links without ``wire_handles`` fall back to ``wire_handle``.
    """
    index = {}
    for link in links:
        port_id = _text(link.get("port_id"))
        if not port_id:
            continue
        handles = link.get("wire_handles")
        if isinstance(handles, str):
            handles = json.loads(handles or "[]")
        members = set(handles or []) | {_text(link.get("wire_handle"))}
        index[(_text(link.get("file_id")), port_id)] = frozenset(h for h in members if h)
    return index


def on_device_internal_wire(index, file_id, port_id, handles) -> bool:
    """Whether any of the observed segment handles lies on the wire of the port's device-internal link (GAP-COORD)."""
    members = index.get((_text(file_id), _text(port_id)))
    return bool(members) and any(_text(handle) in members for handle in handles)
