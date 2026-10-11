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

The functions take plain dictionaries, so they run on the in-memory production records and on the written
parquet rows alike. Identities are compared casefold-exact; nothing is matched by prefix or by value.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict

DEVICE_CATEGORY = "装置端子"
INTERNAL_CATEGORIES = frozenset({"内部元件", "线圈"})
RELATION = "device_internal"
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


def build_device_internal_links(ports, wire_routes=(), wire_group_of=None) -> dict:
    """Device-internal links of the eligible device terminals of one project.

    ports: dicts with record_id, file_id, sheet_id, insert_handle, port_number, category, endpoint_identity,
        label (dict with normalized and resolved, or JSON) and wire_contacts (dicts with wire_handle, or JSON).
    wire_routes: the sw_wire_routes rows of the project (dicts with source_kind, record_id, and ends or ends_json).
    wire_group_of: optional mapping (file_id, wire_handle) -> wire key. A SuperWORKS wire may be drawn as
        several LINE segments; the producer's line group names them as one wire. Without the mapping the
        wire is the contact's own handle.

    Returns {"links": [...], "covered": {device port record_id: [link_id]}, "stats": {...}}. Ports are read only.
    """
    stats = Counter()
    by_wire = defaultdict(list)
    group_of = wire_group_of or {}
    for port in ports:
        for contact in _contacts_of(port):
            handle = _text(contact.get("wire_handle"))
            if handle:
                key = (_text(port.get("file_id")), handle)
                wire_key = group_of.get(key, key)
                if all(member.get("record_id") != port.get("record_id") for member in by_wire[wire_key]):
                    by_wire[wire_key].append(port)
    pcl = pcl_index(wire_routes)

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
                stats["excluded:wire_no_other_port"] += 1
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
            candidates.append((handle, element, wire_ports))
        if not candidates:
            continue
        if len(candidates) > 1:
            stats["excluded:multiple_internal_wires"] += 1
            continue
        handle, element, wire_ports = candidates[0]
        pcl_ids = sorted(set(pcl.get(identity.casefold(), [])))
        link_id = "XDI:" + hashlib.sha1(
            f"{port.get('record_id')}|{element.get('record_id')}|{handle}".encode("utf-8")).hexdigest()[:16]
        link = {
            "link_id": link_id, "relation": RELATION, "port_id": port.get("record_id"),
            "file_id": port.get("file_id"), "sheet_id": port.get("sheet_id"),
            "device_label": label, "endpoint_identity": identity, "pin_tail": tail,
            "wire_handle": handle, "element_port_id": element.get("record_id"),
            "element_insert_handle": _text(element.get("insert_handle")),
            "element_label": _text(_label_of(element)[0]), "element_port_number": _text(element.get("port_number")),
            "wire_port_ids": sorted(_text(o.get("record_id")) for o in wire_ports),
            "pcl_corroborated": bool(pcl_ids), "pcl_record_ids": pcl_ids,
        }
        links.append(link)
        covered[port.get("record_id")].append(link_id)
        stats["linked"] += 1
        stats["pcl_corroborated"] += int(bool(pcl_ids))
    stats["linked_ports"] = len(covered)
    return {"links": links, "covered": dict(covered), "stats": dict(stats)}
