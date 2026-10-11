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


def _text(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value).strip()


def _label_of(port) -> tuple[str, bool]:
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


def _far_pin(port_file: str, contact, wire_key, members, wire_endpoints, pins, label: str):
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
    block_label = _text(block.get("label_value"))
    if not block.get("label_resolved") or not block_label:
        return None, "label_unresolved", detail
    if block_label.casefold() != label.casefold():
        reason = "label_related" if _related(block_label.casefold(), label.casefold()) else "label_differs"
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


def build_device_internal_links(ports, wire_routes=(), wire_group_of=None, unregistered=(), wire_endpoints=None) -> dict:
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

    Returns {"links": [...], "covered": {device port record_id: [link_id]}, "stats": {...}}. Ports are read only.
    """
    stats = Counter()
    decisions = []
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
        label, resolved = _label_of(port)
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
                far, reason, detail = _far_pin(_text(port.get("file_id")), contact, wire, members, endpoints, pins, label)
                stats[f"unregistered:{reason}"] += 1
                decisions.append({"port_id": port.get("record_id"), "file_id": port.get("file_id"),
                    "sheet_id": port.get("sheet_id"), "device_label": label, "endpoint_identity": identity,
                    "wire_handle": handle, "reason": reason, **detail})
                if far is None:
                    stats["excluded:wire_no_other_port"] += 1
                else:
                    candidates.append({"handle": handle, "element": None, "wire_ports": wire_ports, "far": far})
                continue
            if len(others) > 1:
                reason = "excluded:wire_multi_end_internal" if all(
                    o.get("category") in INTERNAL_CATEGORIES for o in others) else "excluded:wire_multi_end"
                stats[reason] += 1
                continue
            element = others[0]
            category = element.get("category")
            if category not in INTERNAL_CATEGORIES:
                stats[f"excluded:other_end_category:{category or 'none'}"] += 1
                continue
            element_label, element_resolved = _label_of(element)
            if not element_resolved or not element_label:
                stats["excluded:element_label_unresolved"] += 1
                continue
            if element_label.casefold() != label.casefold():
                if _related(element_label.casefold(), label.casefold()):
                    stats["excluded:element_label_related"] += 1
                else:
                    stats["excluded:element_label_differs"] += 1
                continue
            candidates.append({"handle": handle, "element": element, "wire_ports": wire_ports, "far": None})
        if not candidates:
            continue
        if len(candidates) > 1:
            stats["excluded:multiple_internal_wires"] += 1
            continue
        candidate = candidates[0]
        handle, element, wire_ports, far = candidate["handle"], candidate["element"], candidate["wire_ports"], candidate["far"]
        pcl_ids = sorted(set(pcl.get(identity.casefold(), [])))
        if element is not None:
            link_id = "XDI:" + hashlib.sha1(
                f"{port.get('record_id')}|{element.get('record_id')}|{handle}".encode("utf-8")).hexdigest()[:16]
            element_fields = {
                "source": SOURCE_SW_ELEMENT, "element_port_id": element.get("record_id"),
                "element_block_record_id": None,
                "element_insert_handle": _text(element.get("insert_handle")),
                "element_label": _text(_label_of(element)[0]),
                "element_port_number": _text(element.get("port_number")),
                "far_x": None, "far_y": None, "pin_x": None, "pin_y": None,
            }
            stats["linked_sw_element"] += 1
        else:
            block = far["block"]
            link_id = "XDI:" + hashlib.sha1(
                f"{port.get('record_id')}|{block.get('record_id')}|{handle}".encode("utf-8")).hexdigest()[:16]
            element_fields = {
                "source": SOURCE_UNREGISTERED, "element_port_id": None,
                "element_block_record_id": block.get("record_id"),
                "element_insert_handle": _text(block.get("insert_handle")),
                "element_label": _text(block.get("label_value")),
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
        }
        links.append(link)
        covered[port.get("record_id")].append(link_id)
        stats["linked"] += 1
        stats["pcl_corroborated"] += int(bool(pcl_ids))
    stats["linked_ports"] = len(covered)
    return {"links": links, "covered": dict(covered), "stats": dict(stats), "unregistered_decisions": decisions}
