"""SuperWORKS source facts. Metadata binds identity; it never unions symbol ports."""
from __future__ import annotations

import math
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ezdxf.enums import TextEntityAlignment
from ezdxf.math import Matrix44, Vec3

from dwg_audit.domain.models import (SwSymbolInstance, SwPort, SwStripRow,
    SwPartInstance, SwConnectLabel, SwConnectDot, TextItem)
from dwg_audit.extract.text_geometry import cad_text_geometry

# A nearest-text pin candidate is rejected when it lies farther from its port
# than this factor times the largest distance of the other resolved pins of the
# same definition instance (see _definition_ports).
NEAREST_BOUND_FACTOR = 1.25
# A connect-label anchor that lies on a LD_ConnectLine endpoint (within this tolerance)
# identifies that leader; see _connect_labels.
CONNECT_ANCHOR_COINCIDENT_TOL = 0.5
PIN_INDEPENDENT_METHODS = ("instance_term_text", "definition_text_reference", "definition_text_nearest")
PIN_NON_INDEPENDENT_METHODS = ("strip_reverse_corroboration",)


def normalize(value: str) -> str:
    # Same endpoint normalization used by the legacy page extractor.
    from dwg_audit.audit.candidates import _normalize_schematic_semantic_endpoint_value
    return _normalize_schematic_semantic_endpoint_value(unicodedata.normalize("NFKC", value))


def entity_insert_wcs(entity) -> Vec3:
    """DXF insertion points are in the entity's OCS (a mirrored extrusion of
    (0,0,-1) flips X); every position used for matching must be WCS."""
    return entity.ocs().to_wcs(Vec3(entity.dxf.insert))


def text_anchor_wcs(entity) -> Vec3:
    """Real anchor of a text entity in WCS, used for pin-to-port proximity.

    TEXT/ATTRIB: ezdxf's placement point, i.e. the alignment point whenever the
    horizontal or vertical alignment is not the default, else the insertion point.
    MTEXT: the bottom-edge point of its layout box in the attachment column
    (left, centre or right) derived from attachment_point; the insertion point
    is the attachment point, so this converts it to the text's baseline anchor.
    """
    if entity.dxftype() == "MTEXT":
        corners = cad_text_geometry(entity).get("corners")
        if not corners or len(corners) != 4:
            return entity_insert_wcs(entity)
        bottom_left, bottom_right = Vec3(corners[3]), Vec3(corners[2])
        column = (int(entity.dxf.get("attachment_point", 1) or 1) - 1) % 3
        if column == 0:
            return bottom_left
        if column == 2:
            return bottom_right
        return (bottom_left + bottom_right) * 0.5
    alignment, point, second = entity.get_placement()
    if second is not None and alignment in (TextEntityAlignment.FIT, TextEntityAlignment.ALIGNED):
        point = point.lerp(second, factor=0.5)
    return entity.ocs().to_wcs(point)


def xvalues(entity, app: str, code: int) -> list[str]:
    if entity is None or not entity.xdata or app not in entity.xdata.data:
        return []
    return [str(t.value) for t in entity.xdata.data[app] if t.code == code and str(t.value) not in ("", "0")]


def raw(entity) -> dict:
    if entity is None or not entity.xdata:
        return {}
    return {app: [[t.code, str(t.value)] for t in tags if t.code != 1001]
            for app, tags in entity.xdata.data.items() if app.startswith(("LD", "LDDZ"))}


def first(entity, app: str, code: int = 1000) -> str:
    values = xvalues(entity, app, code)
    return values[0] if values else ""


def text_ref(doc, handle: str, transform: Matrix44 | None = None) -> dict:
    entity = doc.entitydb.get(handle) if handle else None
    if entity is None or entity.dxftype() not in ("TEXT", "MTEXT", "ATTRIB"):
        return {"handle": handle, "resolved": False, "value": "", "text_id": None}
    value = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
    point = entity_insert_wcs(entity)
    anchor = text_anchor_wcs(entity)
    if transform is not None:
        point = transform.transform(point)
        anchor = transform.transform(anchor)
    return {"handle": handle, "resolved": True, "value": value, "normalized": normalize(value),
            "x": float(point.x), "y": float(point.y),
            "anchor_x": float(anchor.x), "anchor_y": float(anchor.y),
            "height": float(entity.dxf.char_height if entity.dxftype() == "MTEXT" else entity.dxf.height), "text_id": None}


@dataclass(slots=True)
class SuperworksData:
    symbols: list[SwSymbolInstance] = field(default_factory=list)
    ports: list[SwPort] = field(default_factory=list)
    strip_rows: list[SwStripRow] = field(default_factory=list)
    part_instances: list[SwPartInstance] = field(default_factory=list)
    connect_labels: list[SwConnectLabel] = field(default_factory=list)
    connect_dots: list[SwConnectDot] = field(default_factory=list)
    dictionary: dict[str, Any] = field(default_factory=dict)
    pin_resolution_counts: dict[str, int] = field(default_factory=dict)
    coverage_observations: list[dict[str, Any]] = field(default_factory=list)
    conflict_observations: list[dict[str, Any]] = field(default_factory=list)
    extraction_seconds: float = 0.0
    recognition_seconds: float = 0.0
    # Wire-route records read from the DXF documents cad_extract already has open
    # (superworks_loggen.PageWireRoutes), and the resolved rows written after admission.
    wire_route_pages: list[Any] = field(default_factory=list)
    wire_route_failures: dict[str, str] = field(default_factory=dict)
    wire_route_rows: list[dict[str, Any]] = field(default_factory=list)
    wire_route_stats: dict[str, Any] = field(default_factory=dict)
    # G1P: INSERTs with LD_SYMB2_LABEL and without LD_SYMB2_SPECIAL (unregistered SYMB2 blocks). They
    # never enter ports or symbols; only device-internal links read their TERMPOINT ends.
    unregistered_symb2: list[dict[str, Any]] = field(default_factory=list)
    # Model-space wire end points of the sheet: (file_id, wire handle) -> {wire_side: (x, y)}.
    wire_endpoints: dict[tuple[str, str], dict[int, tuple[float, float]]] = field(default_factory=dict)

    def extend(self, other):
        for name in ("symbols", "ports", "strip_rows", "part_instances", "connect_labels", "connect_dots",
                     "coverage_observations", "conflict_observations", "unregistered_symb2"):
            getattr(self, name).extend(getattr(other, name))
        self.wire_endpoints.update(other.wire_endpoints)
        self.extraction_seconds += other.extraction_seconds


def _definition_ports(doc, insert, parent: Matrix44, path: str, seen=()):
    """Transform source vertices, preserving XDATA and definition handles."""
    name = insert.dxf.name
    if name in seen or len(seen) >= 32 or name not in doc.blocks:
        return
    world = insert.matrix44() @ parent
    local_texts = []
    for entity in doc.blocks[name]:
        if entity.dxftype() == "INSERT":
            yield from _definition_ports(doc, entity, world, path + "/" + entity.dxf.handle, (*seen, name))
        elif entity.dxftype() in ("TEXT", "MTEXT", "ATTRIB"):
            ref = text_ref(doc, entity.dxf.handle, world)
            if ref.get("resolved") and ref.get("normalized"):
                local_texts.append(ref)
    ports = []
    for entity in doc.blocks[name]:
        if entity.dxftype() == "LWPOLYLINE" and entity.xdata and "LD_SYMB1LIB_TERMPOINT" in entity.xdata.data:
            points = list(entity.vertices_in_wcs())
            if len(points) < 2:
                continue
            number = first(entity, "LD_SYMB1LIB_TERMPOINT")
            handle = first(entity, "LD_SYMB1LIB_TERMPOINT", 1005)
            pin = text_ref(doc, handle, world) if handle else None
            if pin and pin.get("resolved"):
                pin["resolution_method"] = "definition_text_reference"
                referenced = doc.entitydb.get(handle)
                # TERMPOINT's 1005 is a source-owned link to its pin text; the
                # library format does not require that TEXT to point back.
                pin["reciprocal_ok"] = bool(referenced and referenced.dxf.owner == entity.dxf.owner)
            else:
                pin = None
            a, b = world.transform(points[0]), world.transform(points[-1])
            if not number and pin:
                number = pin.get("normalized", "")
            ports.append({"entity": entity, "number": number, "a": a, "b": b, "pin": pin, "path": path})

    # Nearest-text candidates are measured from the real text anchor.  A candidate
    # is kept only when it is not farther from its port than the other resolved
    # pins of this same definition instance allow (block-internal labels such
    # as a contact marker sit at a distance no other pin of the block reaches).
    nearest = {}
    for index, port in enumerate(ports):
        if port["pin"] is not None:
            continue
        candidates = []
        for ref in local_texts:
            distance = _point_segment_distance(ref["anchor_x"], ref["anchor_y"], port["a"].x, port["a"].y, port["b"].x, port["b"].y)
            height = float(ref.get("height") or 0.0)
            if height > 0 and distance <= height * 3.0 + 1e-8:
                candidates.append((distance, ref))
        candidates.sort(key=lambda item: (item[0], item[1].get("handle") or ""))
        if candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] >= max(0.25, candidates[0][1].get("height", 0.0) * 0.25)):
            nearest[index] = candidates[0]
    # A label value names a port only when it names one text in this definition
    # instance. Several ports adopting the same value from different text entities
    # (e.g. one caption repeated beside each slot of a block) are not told apart by
    # it, so they fall back to their port numbers. Ports sharing one text entity
    # are the shared-terminal case below and keep their adoption.
    # The revocation is made only when every port of such a group has a usable
    # fallback identity (its TERMPOINT port number) and those numbers are distinct
    # within the group. Otherwise revoking would leave the ports with no identity at
    # all (e.g. a backplate whose one row label sits on several ports), so the
    # nearest adoption is kept.
    rejected = {}
    by_value = defaultdict(list)
    for index, (_, ref) in nearest.items():
        by_value[ref.get("normalized")].append(index)
    for indices in by_value.values():
        if len(indices) < 2 or len({nearest[index][1].get("handle") for index in indices}) < 2:
            continue
        fallbacks = [normalize(ports[index]["number"] or "") for index in indices]
        if not all(fallbacks) or len(set(fallbacks)) < len(fallbacks):
            continue
        for index in indices:
            distance, ref = nearest.pop(index)
            rejected[index] = {"handle": ref.get("handle"), "distance": distance, "reason": "same_value_distinct_text"}
    distances = {}
    for index, port in enumerate(ports):
        if port["pin"] is not None:
            pin = port["pin"]
            distances[index] = _point_segment_distance(pin["anchor_x"], pin["anchor_y"], port["a"].x, port["a"].y, port["b"].x, port["b"].y)
        elif index in nearest:
            distances[index] = nearest[index][0]
    # A text that several ports of this definition use (a shared terminal label such
    # as DC on two contacts) is not a block-internal marker; the bound does not apply.
    shared_handles = Counter(pin.get("handle") for pin in (port["pin"] for port in ports) if pin)
    shared_handles.update(ref.get("handle") for _, ref in nearest.values())
    for index, (distance, ref) in list(nearest.items()):
        if shared_handles[ref.get("handle")] > 1:
            continue
        others = [value for other, value in distances.items() if other != index]
        if not others:
            continue
        bound = max(NEAREST_BOUND_FACTOR * max(others), float(ref.get("height") or 0.0))
        if distance > bound + 1e-8:
            rejected[index] = {"handle": ref.get("handle"), "distance": distance, "bound": bound, "reason": "nearest_bound"}
            del nearest[index]

    for index, port in enumerate(ports):
        pin = port["pin"]
        number = port["number"]
        if pin is None and index in nearest:
            distance, ref = nearest[index]
            pin = dict(ref)
            pin["resolution_method"] = "definition_text_nearest"
            pin["nearest_distance"] = distance
            pin["reciprocal_ok"] = True
        elif pin is None and index in rejected:
            pin = {"resolved": False, "nearest_rejected": rejected[index]}
        if pin and not number:
            number = pin.get("normalized", "")
        yield port["entity"], number, port["a"], port["b"], port["path"], pin


def _terminal_identity(label_value, pin_value, joiner=""):
    """Endpoint identity of a label and a pin value: "1n" + "219" -> "1n219" for a device
    terminal (no joiner), "1n" + "-" + "A1" for other parts. None when either part is empty."""
    return label_value + joiner + pin_value if label_value and pin_value else None


def _revoked_adoption(pin) -> bool:
    """True when _definition_ports withdrew this port's same-label nearest adoption (L1)."""
    return (pin or {}).get("nearest_rejected", {}).get("reason") == "same_value_distinct_text"


def _point_segment_distance(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    denominator = vx * vx + vy * vy
    if not denominator:
        return math.hypot(px - ax, py - ay)
    fraction = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / denominator))
    return math.hypot(px - (ax + fraction * vx), py - (ay + fraction * vy))


def _wire_index(doc):
    grid = defaultdict(list)
    for e in doc.modelspace():
        if e.dxftype() == "LINE":
            points = [e.dxf.start, e.dxf.end]
        elif e.dxftype() == "LWPOLYLINE" and not e.closed and not xvalues(e, "LD_CONNECT_DOT", 1000):
            vertices = list(e.vertices_in_wcs())
            points = [vertices[0], vertices[-1]] if vertices else []
        else:
            continue
        for i, p in enumerate(points):
            grid[(math.floor(p.x / 2), math.floor(p.y / 2))].append((e.dxf.handle, i, p))
    return grid


def _contacts(grid, a, b, tolerance):
    found = {}
    for q in (a, b):
        radius = math.ceil(tolerance / 2) + 1
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for handle, side, point in grid.get((math.floor(q.x / 2) + dx, math.floor(q.y / 2) + dy), ()):
                    distance = math.hypot(point.x - q.x, point.y - q.y)
                    if distance <= tolerance + 1e-8:
                        key = handle, side
                        if key not in found or distance < found[key]["residual"]:
                            found[key] = {"wire_handle": handle, "wire_side": side, "x": float(point.x), "y": float(point.y), "residual": distance}
    return list(found.values())


def _page_text_index(doc):
    """Page-WCS insertion points of every TEXT/MTEXT on the sheet (model space and
    block-internal, through the same transforms as the walk), grouped by normalized value.
    Used to tell whether a same-identity text lies nearer to a symbol than its label."""
    index = defaultdict(list)

    def visit(entities, parent, seen=()):
        for entity in entities:
            kind = entity.dxftype()
            if kind in ("TEXT", "MTEXT"):
                value = entity.plain_text() if kind == "MTEXT" else entity.dxf.text
                normalized = normalize(value)
                if normalized:
                    point = parent.transform(entity_insert_wcs(entity))
                    index[normalized].append((entity.dxf.handle, float(point.x), float(point.y)))
            elif kind == "INSERT" and entity.dxf.name not in seen and len(seen) < 32 and entity.dxf.name in doc.blocks:
                visit(doc.blocks[entity.dxf.name], entity.matrix44() @ parent, (*seen, entity.dxf.name))

    visit(doc.modelspace(), Matrix44())
    return index


def _unregistered_symb2(doc, insert, world, label, file_id, sheet_id, instance) -> dict[str, Any]:
    """An unregistered SYMB2 block (LD_SYMB2_LABEL, no LD_SYMB2_SPECIAL): its label and its own TERMPOINT ends.

    Ends are WCS points of the block's LWPOLYLINE first and last vertices, transformed by the instance
    matrix (the same frame as _definition_ports). The label is the one walk() already resolved.
    """
    termpoints = []
    if insert.dxf.name in doc.blocks:
        for entity in doc.blocks[insert.dxf.name]:
            if entity.dxftype() == "LWPOLYLINE" and entity.xdata and "LD_SYMB1LIB_TERMPOINT" in entity.xdata.data:
                points = [world.transform(point) for point in entity.vertices_in_wcs()]
                if len(points) >= 2:
                    termpoints.append({"number": first(entity, "LD_SYMB1LIB_TERMPOINT"),
                                       "a": (float(points[0].x), float(points[0].y)),
                                       "b": (float(points[-1].x), float(points[-1].y))})
    label_entity = doc.entitydb.get(first(insert, "LD_SYMB2_LABEL", 1005))
    resolved = bool(label.get("resolved"))
    return {
        "record_id": f"USY:{file_id}:{sheet_id}:{instance}", "sheet_id": sheet_id, "file_id": file_id,
        "insert_handle": insert.dxf.handle, "instance_path": instance, "block_name": insert.dxf.name,
        "label_handle": label.get("handle") or None, "label_resolved": resolved,
        "label_value": label.get("normalized", "") if resolved else "",
        "label_reciprocal": insert.dxf.handle in xvalues(label_entity, "LD_SYMB2_LABEL", 1005),
        "termpoints": termpoints,
    }


def extract_superworks_semantics(doc, *, sheet_id: str, file_id: str) -> SuperworksData:
    start = time.perf_counter()
    data = SuperworksData()
    grid = _wire_index(doc)
    for cell in grid.values():
        for handle, side, point in cell:
            data.wire_endpoints.setdefault((file_id, handle), {})[side] = (float(point.x), float(point.y))
    page_index = {}

    def nearer_same_identity_text(label, position, distance) -> bool:
        """True when another text of this sheet carrying the label's identity lies nearer to the symbol."""
        identity = label.get("normalized")
        if not identity:
            return False
        if "index" not in page_index:
            # Built lazily: only far terminal labels ask, so ordinary sheets pay nothing.
            page_index["index"] = _page_text_index(doc)
        for handle, x, y in page_index["index"].get(identity, ()):
            if handle == label.get("handle") and math.hypot(x - label["x"], y - label["y"]) <= 1e-6:
                continue
            if math.hypot(x - position.x, y - position.y) < distance - 1e-9:
                return True
        return False

    def walk(entities, parent, path, seen=()):
        for insert in entities:
            if insert.dxftype() != "INSERT":
                continue
            instance = path + "/" + insert.dxf.handle
            world = insert.matrix44() @ parent
            category = first(insert, "LD_SYMB2_SPECIAL")
            label_handle = first(insert, "LD_SYMB2_LABEL", 1005) or first(insert, "LDPARTLAYT_PARTLABEL_HANDLE", 1005)
            label_entity = doc.entitydb.get(label_handle)
            # Block-local references receive their enclosing transform; model references do not.
            transform = parent if label_entity is not None and label_entity.dxf.owner == insert.dxf.owner and path else None
            label = text_ref(doc, label_handle, transform)
            reciprocal_app = "LD_SYMB2_LABEL" if category else "LDPARTLAYT_PART_HANDLE"
            reciprocal = insert.dxf.handle in xvalues(label_entity, reciprocal_app, 1005)
            position = parent.transform(entity_insert_wcs(insert))
            distance = math.hypot(label.get("x", position.x) - position.x, label.get("y", position.y) - position.y)
            reasons = []
            if label_handle and not label.get("resolved"):
                reasons.append("dangling_label_handle")
            elif label_handle and label.get("resolved") and not reciprocal:
                reasons.append("nonreciprocal_label")
            elif not label_handle:
                reasons.append("missing_label_reference")
            if label_handle and label_entity is not None and label_entity.dxf.owner != insert.dxf.owner:
                reasons.append("label_owner_mismatch")
            if category == "端子" and distance > 30:
                # Far from its symbol but reciprocally referenced, resolvable, and the only text
                # of its identity on the sheet nearest the symbol: a layout observation, not a
                # metadata conflict. Stale only when the reference itself is unsound or a nearer
                # same-identity text exists.
                if reciprocal and label.get("resolved") and not nearer_same_identity_text(label, position, distance):
                    reasons.append("label_far_from_symbol")
                else:
                    reasons.append("stale_label_reference")
            validation = {"handle_resolved": bool(label.get("resolved")), "reciprocal_ok": reciprocal,
                          "label_distance": distance, "stale_suspect": "stale_label_reference" in reasons}
            if not category and first(insert, "LD_SYMB2_LABEL", 1005):
                data.unregistered_symb2.append(_unregistered_symb2(doc, insert, world, label, file_id, sheet_id, instance))
            symbol_id = f"SW:{file_id}:{sheet_id}:{instance}"
            pin_texts = {}
            for app in raw(insert):
                if app.startswith("LD_SYMB2_TERM_TEXT_"):
                    number = app.removeprefix("LD_SYMB2_TERM_TEXT_")
                    pin = text_ref(doc, first(insert, app, 1005), transform)
                    pin["reciprocal_ok"] = insert.dxf.handle in xvalues(doc.entitydb.get(pin["handle"]), app, 1005)
                    pin_texts[number] = pin
            if category:
                data.symbols.append(SwSymbolInstance(record_id=symbol_id, sheet_id=sheet_id, file_id=file_id,
                    insert_handle=insert.dxf.handle, instance_path=instance, block_name=insert.dxf.name, category=category,
                    label=label, pin_texts=pin_texts, endpoint_identity=label.get("normalized") if category == "端子" else None,
                    insert_x=float(position.x), insert_y=float(position.y), raw_xdata=raw(insert), validation=validation, reason_codes=reasons,
                    dzlx=first(insert,"LD_CIRCUIT_DZLX"), dxlx=first(insert,"LD_CIRCUIT_DXLX"), main=first(insert,"LD_SYMB2_MAIN"), multi=first(insert,"LD_SYMB2_MULTI")))
            part_ports = []
            if category or (insert.xdata and "LDPARTLAYT_PART" in insert.xdata.data):
                for marker, number, a, b, marker_path, definition_pin in _definition_ports(doc, insert, parent, instance):
                    length = math.hypot(b.x - a.x, b.y - a.y)
                    tolerance = length * .6
                    pin = pin_texts.get(number, definition_pin or {})
                    if pin.get("resolved") and pin.get("reciprocal_ok") is True and not pin.get("resolution_method"):
                        pin["resolution_method"] = "instance_term_text"
                    if category == "装置端子" and not pin.get("resolved"):
                        # TERM_TEXT_n=0 is an unused display slot. A single, reciprocally
                        # referenced pin names this device-terminal instance, including its other contacts.
                        unique = {p.get("handle"):p for p in pin_texts.values() if p.get("resolved") and p.get("reciprocal_ok")}
                        if len(unique) == 1:
                            pin = next(iter(unique.values()))
                    endpoint = label.get("normalized") or None
                    if category != "端子":
                        pin_value = pin.get("normalized") if pin.get("resolved") else ""
                        endpoint = _terminal_identity(endpoint, pin_value, "" if category == "装置端子" else "-")
                        if endpoint is None and number and _revoked_adoption(pin):
                            # N1: a port whose same-label adoption was withdrawn has no pin value, so
                            # the line above yields None. Its TERMPOINT port number (normalized as a
                            # device-terminal pin value) gives the device-terminal identity form.
                            fallback = _terminal_identity(label.get("normalized") or None, normalize(str(number)))
                            if fallback:
                                endpoint = fallback
                                pin = {**pin, "pin_resolution_method": "termpoint_number_fallback", "fallback_identity": fallback}
                    if category != "端子" and label.get("normalized") and number and pin.get("resolved"):
                        # F4c: a TERMPOINT name such as IN2/OUT2 is displayed as its digit 2.
                        # Terminal strips write the name, so the name is kept as an alias identity.
                        port_name = str(number)
                        if port_name != pin.get("normalized") and re.fullmatch(r"[A-Za-z]+\d+", port_name):
                            digit_match = re.fullmatch(r"[A-Za-z]+(\d+)", port_name)
                            if (pin.get("resolution_method") == "definition_text_nearest" and endpoint
                                    and pin.get("normalized") == digit_match[1]):
                                # L-15: a nearest-selected digit of an X-named TERMPOINT (X19 beside "19")
                                # takes the terminal-strip spelling "label-X19" as its identity, as the
                                # strip writes it; the digit form "label-19" stays as an alias.
                                pin = {**pin, "port_name": port_name, "endpoint_aliases": [endpoint]}
                                endpoint = label.get("normalized") + "-" + port_name
                            else:
                                pin = {**pin, "port_name": port_name,
                                       "endpoint_aliases": [label.get("normalized") + ("" if category == "装置端子" else "-") + port_name]}
                    contacts = _contacts(grid, a, b, tolerance)
                    port_reasons = list(reasons)
                    if category != "端子" and category and not pin.get("resolved"):
                        port_reasons.append("unresolved_pin_text")
                    if pin and not pin.get("reciprocal_ok", True):
                        port_reasons.append("nonreciprocal_pin")
                    if not number:
                        port_reasons.append("unresolved_port_number")
                    port = SwPort(record_id=f"{symbol_id}:{marker_path}:{marker.dxf.handle}:{number}", sheet_id=sheet_id, file_id=file_id,
                        symbol_id=symbol_id, insert_handle=insert.dxf.handle, instance_path=instance, marker_handle=marker.dxf.handle,
                        port_number=number, category=category, start_x=float(a.x), start_y=float(a.y), end_x=float(b.x), end_y=float(b.y),
                        direction=first(marker,"LD_DIRECTION_SYMBLIB") or first(marker,"LD_PARTLIB_DOTCONDIRECT"), tolerance=tolerance,
                        endpoint_identity=endpoint, label=label, pin=pin, wire_contacts=contacts, raw_xdata=raw(marker),
                        validation={**validation, "port_touched_by_wire": bool(contacts)}, reason_codes=port_reasons)
                    if category:
                        data.ports.append(port)
                    else:
                        from dataclasses import asdict
                        part_ports.append(asdict(port))
                if not category:
                    data.part_instances.append(SwPartInstance(record_id=symbol_id, sheet_id=sheet_id, file_id=file_id,
                        insert_handle=insert.dxf.handle, instance_path=instance, block_name=insert.dxf.name,
                        label=label, part_no=text_ref(doc,first(insert,"LDPARTLAYT_PARTNO_HANDLE",1005)),
                        part_type=first(insert,"LDPARTLAYT_PARTTYPE_CONTENT"), ports=part_ports, raw_xdata=raw(insert), validation=validation, reason_codes=reasons))
            if insert.dxf.name not in seen and len(seen) < 32 and insert.dxf.name in doc.blocks:
                yield from walk(doc.blocks[insert.dxf.name], world, instance, (*seen, insert.dxf.name))
        return
        yield
    list(walk(doc.modelspace(), Matrix44(), ""))

    for e in doc.modelspace():
        if not e.xdata:
            continue
        if "LD_DZPNO_HEADHANDLE" in e.xdata.data:
            header_handle = first(e,"LD_DZPNO_HEADHANDLE",1005)
            header, row = text_ref(doc,header_handle), text_ref(doc,e.dxf.handle)
            header_entity = doc.entitydb.get(header_handle)
            reciprocal = e.dxf.handle in xvalues(header_entity,"LD_DZPHEAD_NOHANDLE",1005)
            reasons = [] if header.get("resolved") and reciprocal else ["invalid_strip_header_reference"]
            connections = []
            for side in ("LEFT", "RIGHT"):
                for branch in ("", "_2"):
                    handle = first(e,f"LDDZ_{side}TEXT_HANDLE{branch}",1005)
                    if not handle:
                        continue
                    ref = text_ref(doc,handle)
                    ref.update(side=side.lower(), branch=branch or "_1", style=first(doc.entitydb.get(handle),"LD_DZPTEXT_STYLE"))
                    ref["reciprocal_ok"] = e.dxf.handle in xvalues(doc.entitydb.get(handle),"LD_DZPTEXT_NOHANDLE",1005)
                    if not ref.get("resolved") or not ref["reciprocal_ok"]:
                        reasons.append("invalid_strip_connection_reference")
                    connections.append(ref)
            potentials = [text_ref(doc,h) for h in xvalues(e,"LD_DZPNO_DZPTEXTHANDLE",1005)]
            cross_refs = []
            for ref in potentials:
                for match in re.finditer(r"未定义([0-9A-Fa-f]+):(\d+)_(.+)", ref.get("value", "")):
                    cross_refs.append({"handle": match[1], "port_number": match[2], "page_name": match[3]})
            def attribute(app):
                return first(e,app) or text_ref(doc,first(e,app,1005)).get("value", "")
            # The strip's own name (DZ_SERIALNUMBER_NAME, on every row) is the identity prefix. The header
            # text is only a check: a continuation note such as "上接1QD15" names the rows above it, not the
            # strip, so it must not be read as the prefix ("上接1QD15" + "16" would give "上接1QD1516").
            header_value = header.get("normalized", "")
            dz_name = first(e, "DZ_SERIALNUMBER_NAME", 1000)
            if dz_name:
                strip_name, strip_name_source = normalize(dz_name), "dz_serialnumber_name"
            else:
                strip_name, strip_name_source = header_value, "header"
            header_mismatch = bool(dz_name) and header_value != strip_name
            data.strip_rows.append(SwStripRow(record_id=f"SWR:{file_id}:{sheet_id}:{e.dxf.handle}", sheet_id=sheet_id,file_id=file_id,
                row_handle=e.dxf.handle,header=header,row=row, endpoint_identity=(strip_name+row.get("normalized","")) or None,
                connections=connections,potentials=potentials,cross_page_refs=cross_refs, raw_xdata=raw(e),
                validation={"handle_resolved": bool(header.get("resolved")),"reciprocal_ok":reciprocal,
                            "strip_name": strip_name, "strip_name_source": strip_name_source,
                            "header_text": header.get("value", ""), "header_mismatch": header_mismatch},
                reason_codes=sorted(set(reasons)),
                symb_bwrite=attribute("LD_DZPNO_SymbBwrite"),dzlx=attribute("LD_DZPNO_DZLX"),dxlx=attribute("LD_DZPNO_DXLX")))
        if "LD_CONNECT_DOT" in e.xdata.data and e.dxftype() == "LWPOLYLINE":
            points = list(e.vertices_in_wcs())
            if points:
                center = sum(points, Vec3()) / len(points)
                data.connect_dots.append(SwConnectDot(record_id=f"SWD:{file_id}:{e.dxf.handle}",sheet_id=sheet_id,file_id=file_id,
                    handle=e.dxf.handle,x=float(center.x),y=float(center.y),raw_xdata=raw(e)))

    _connect_labels(doc, data, sheet_id, file_id)
    line_claims = Counter(label.line_handle for label in data.connect_labels if label.line_handle)
    for label in data.connect_labels:
        if label.line_handle and line_claims[label.line_handle] > 1:
            label.reason_codes.append("competing_connect_line_labels")
    # A same-symbol/same-pin group can have several physical contacts.
    # Repeated terminal drawings are legal (p044/1XD2 appears in two circuits).
    # Ownership conflicts are decided at a particular wire endpoint by the consumer.
    identities = defaultdict(set)
    for port in data.ports:
        if port.endpoint_identity:
            identities[port.symbol_id].add(port.endpoint_identity)
    for symbol in data.symbols:
        candidates = identities[symbol.record_id]
        if len(candidates) == 1:
            symbol.endpoint_identity = next(iter(candidates))
    data.extraction_seconds = time.perf_counter() - start
    return data


def _connect_labels(doc, data, sheet_id, file_id):
    tagged = [e for e in doc.modelspace() if e.xdata and "LD_ConnectLine" in e.xdata.data]
    lines = [e for e in tagged if e.dxftype() == "LINE"]
    candidates = []
    for e in tagged:
        if e.dxftype() not in ("TEXT","MTEXT"):
            continue
        text = text_ref(doc,e.dxf.handle)
        # Distances are measured from the text's real anchor (text_anchor_wcs), not its
        # insertion point: a centred label's insertion point sits well off its leader end.
        anchor_x, anchor_y = text["anchor_x"], text["anchor_y"]
        radius = max(5, text["height"]*3)
        coincident, nearby = [], []
        for line in lines:
            distance = min(math.hypot(anchor_x-p.x,anchor_y-p.y) for p in (line.dxf.start,line.dxf.end))
            handle_gap = abs(int(e.dxf.handle,16)-int(line.dxf.handle,16))
            if distance <= CONNECT_ANCHOR_COINCIDENT_TOL:
                coincident.append((handle_gap,distance,line))
            elif distance <= radius:
                nearby.append((handle_gap,distance,line))
        candidates.append((e,text,coincident,nearby))
    # Pass 1: a leader whose end sits on the label's anchor is that label's own leader.
    # Those leaders are claimed and locked before any radius fallback runs.
    locked = set()
    proposals_by_label = []
    for e,text,coincident,_ in candidates:
        proposals = sorted(coincident,key=lambda p:(p[0],p[1]))
        if proposals:
            locked.add(proposals[0][2].dxf.handle)
        proposals_by_label.append(proposals)
    # Pass 2: labels without an anchor-coincident leader fall back to the radius rule (GND-style
    # labels whose leader end is offset from the anchor). Leaders locked in pass 1 are excluded,
    # so an offset label cannot take a leader another label's anchor is sitting on.
    for index,(e,text,coincident,nearby) in enumerate(candidates):
        if coincident:
            continue
        proposals = sorted((p for p in nearby if p[2].dxf.handle not in locked),key=lambda p:(p[0],p[1]))
        proposals_by_label[index] = proposals
    for (e,text,_,_),proposals in zip(candidates,proposals_by_label):
        line = proposals[0][2] if proposals else None
        reasons = [] if line else ["unresolved_connect_line"]
        if len(proposals)>1 and proposals[0][:2] == proposals[1][:2]:
            reasons.append("ambiguous_connect_line")
        if proposals:
            nearest_distance=min(p[1] for p in proposals)
            nearest=[p for p in proposals if abs(p[1]-nearest_distance)<1e-8]
            if len(nearest)!=1 or nearest[0][2] is not line:
                reasons.append("connect_line_geometry_not_unique")
        rec = SwConnectLabel(record_id=f"SWC:{file_id}:{e.dxf.handle}",sheet_id=sheet_id,file_id=file_id,text=text,
            raw_xdata=raw(e),reason_codes=reasons)
        if line:
            rec.line_handle=line.dxf.handle
            rec.start_x,rec.start_y=float(line.dxf.start.x),float(line.dxf.start.y)
            rec.end_x,rec.end_y=float(line.dxf.end.x),float(line.dxf.end.y)
            matches=[]
            for part in data.part_instances:
                for port in part.ports:
                    residual=min(math.hypot(x-px,y-py) for x,y in ((rec.start_x,rec.start_y),(rec.end_x,rec.end_y))
                                 for px,py in ((port["start_x"],port["start_y"]),(port["end_x"],port["end_y"])))
                    if residual <= port["tolerance"]:
                        matches.append((part,port))
            unique={(part.record_id,port["endpoint_identity"]) for part,port in matches}
            if len(unique)==1:
                part,port=matches[0]
                rec.part_id,rec.port_number,rec.endpoint_identity=part.record_id,port["port_number"],port["endpoint_identity"]
                rec.reason_codes.extend(part.reason_codes+port["reason_codes"])
            else:
                rec.reason_codes.append("unresolved_part_port" if not unique else "ambiguous_part_port")
        data.connect_labels.append(rec)


def bind_text_ids(data: SuperworksData, texts: list[TextItem]):
    lookup = defaultdict(list)
    for text in texts:
        lookup[(text.sheet_id,text.file_id,text.handle)].append(text)
    def bind(ref, sheet_id, file_id):
        if not isinstance(ref,dict) or not ref.get("handle"):
            return
        candidates = lookup.get((sheet_id,file_id,ref["handle"]),[])
        if len(candidates)>1 and "x" in ref:
            candidates=sorted(candidates,key=lambda t:math.hypot(t.insert_x-ref["x"],t.insert_y-ref["y"]))
            if len(candidates)>1 and abs(math.hypot(candidates[0].insert_x-ref["x"],candidates[0].insert_y-ref["y"])-math.hypot(candidates[1].insert_x-ref["x"],candidates[1].insert_y-ref["y"]))<1e-8:
                return
        if candidates:
            ref["text_id"]=candidates[0].text_id
    for rec in (*data.symbols,*data.ports,*data.strip_rows,*data.part_instances,*data.connect_labels):
        for attr in ("label","pin","row","header","text","part_no"):
            bind(getattr(rec,attr,None),rec.sheet_id,rec.file_id)
        for ref in getattr(rec,"pin_texts",{}).values():
            bind(ref,rec.sheet_id,rec.file_id)
        for ref in (*getattr(rec,"connections",[]),*getattr(rec,"potentials",[])):
            bind(ref,rec.sheet_id,rec.file_id)
        for port in getattr(rec,"ports",[]):
            if isinstance(port,dict):
                bind(port.get("label"),rec.sheet_id,rec.file_id)
                bind(port.get("pin"),rec.sheet_id,rec.file_id)


def corroborate_internal_pin_identities(data: SuperworksData):
    """Resolve only exact internal-port identities corroborated by the strip text."""
    destinations = defaultdict(list)
    for row in data.strip_rows:
        if row.reason_codes or not row.validation.get("reciprocal_ok"):
            continue
        for connection in row.connections:
            if connection.get("style") != "端子排内接元件" or not connection.get("resolved") or not connection.get("reciprocal_ok"):
                continue
            for value in connection.get("value", "").replace("，", ",").split(","):
                if value.strip().strip("&"):
                    destinations[normalize(value.strip().strip("&")).casefold()].append({
                        "row_id": row.record_id, "row_handle": row.row_handle,
                        "header_handle": row.header.get("handle"),
                        "connection_handle": connection.get("handle"),
                        "connection_text_id": connection.get("text_id"),
                        "side": connection.get("side"), "branch": connection.get("branch")})

    counts = {"instance_term_text": 0, "definition_text_reference": 0,
              "definition_text_nearest": 0, "strip_reverse_corroboration": 0, "unresolved": 0}
    all_ports = [(port, port.category) for port in data.ports if port.category in ("内部元件", "线圈", "接插件")]
    all_ports.extend((port, "内部元件") for part in data.part_instances for port in part.ports)
    for port, _category in all_ports:
        is_record=hasattr(port,"pin")
        pin=port.pin if is_record else port.get("pin",{})
        number=port.port_number if is_record else port.get("port_number")
        label=port.label if is_record else port.get("label",{})
        if not pin.get("resolved") and number:
            label_key=label.get('normalized')
            # F4c: a TERMPOINT name (IN2) and its display digit (2) name one port;
            # a terminal strip may write either form, so both are candidates.
            digit_alias=re.fullmatch(r"[A-Za-z]+(\d+)",str(number))
            numbers=[str(number)]+([digit_alias[1]] if digit_alias else [])
            candidate=""
            strip_refs=[]
            if label_key:
                for option in numbers:
                    option_candidate=f"{label_key}-{option}"
                    option_refs=destinations.get(option_candidate.casefold(),[])
                    if option_refs:
                        candidate, strip_refs, number=option_candidate, option_refs, option
                        break
            if candidate and strip_refs:
                pin={"handle":None,"text_id":None,"value":number,"normalized":number,"resolved":True,
                     "reciprocal_ok":True,"resolution_method":"strip_reverse_corroboration",
                     # F4d: a pin resolved only from the strip's own reverse reference is
                     # recorded separately and never counted as independent verification.
                     "pin_resolution_method":"strip_reverse_corroboration","independent_verification":False,
                     "corroborating_strip_refs":strip_refs,
                     "corroborating_strip_text_ids":sorted({ref["connection_text_id"] for ref in strip_refs if ref.get("connection_text_id")})}
                if is_record:
                    port.pin=pin
                    port.endpoint_identity=candidate
                    port.reason_codes=[reason for reason in port.reason_codes if reason not in ("unresolved_pin_text","nonreciprocal_pin")]
                else:
                    port["pin"]=pin
                    port["endpoint_identity"]=candidate
                    port["pin_resolution_method"]="strip_reverse_corroboration"
                    port.setdefault("validation",{})["pin_resolution_method"]="strip_reverse_corroboration"
                    port["reason_codes"]=[reason for reason in port.get("reason_codes",[]) if reason not in ("unresolved_pin_text","nonreciprocal_pin")]
        method=pin.get("resolution_method") if pin.get("resolved") and pin.get("reciprocal_ok",True) else None
        if method and method not in PIN_NON_INDEPENDENT_METHODS:
            pin.setdefault("pin_resolution_method",method)
            pin.setdefault("independent_verification",method in PIN_INDEPENDENT_METHODS)
            if method in PIN_INDEPENDENT_METHODS:
                counts["independently_verified_ports"]=counts.get("independently_verified_ports",0)+1
        bucket=method if method in counts else "unresolved"
        counts[bucket]+=1
    part_by_id={part.record_id:part for part in data.part_instances}
    for label in data.connect_labels:
        part=part_by_id.get(label.part_id)
        if not part:
            continue
        matches={port.get("endpoint_identity") for port in part.ports
                 if str(port.get("port_number"))==str(label.port_number) and port.get("endpoint_identity")}
        if len(matches)==1:
            label.endpoint_identity=next(iter(matches))
            label.reason_codes=[reason for reason in label.reason_codes if reason!="unresolved_part_port"]
    total=len(all_ports)
    resolved=total-counts["unresolved"]
    counts["total_internal_ports"]=total
    counts["resolved_internal_ports"]=resolved
    counts["internal_pin_resolution_rate"]=round(resolved/total,6) if total else None
    counts["method_counts"]={key:counts[key] for key in
        ("instance_term_text","definition_text_reference","definition_text_nearest","strip_reverse_corroboration")}
    data.pin_resolution_counts=counts


def read_project_dictionary(root: Path) -> dict:
    names=set()
    strips=set()
    statuses={}
    strip_order=[]
    for filename in ("LdInfo.xml","LdDzbInfo.xml"):
        path=root/filename
        if not path.exists():
            statuses[filename]="missing"
            continue
        try:
            tree=ET.parse(path)
        except (ET.ParseError,OSError) as exc:
            statuses[filename]=f"parse_failed:{exc}"
            continue
        statuses[filename]="parsed"
        for element in tree.iter():
            for key,value in element.attrib.items():
                if key.casefold() in ("dzbname","partlabel","label","bomlabel","devicelabel"):
                    if key.casefold()=="dzbname":
                        strips.add(normalize(value))
                        strip_order.append({"name": normalize(value), "rank": len(strip_order) + 1,
                                            "style": element.attrib.get("DzbStyle"),
                                            "length": element.attrib.get("DzbLength")})
                    names.add(normalize(value))
                    match=re.fullmatch(r"(.+?)(\d+)[~～](?:\1)?(\d+)",value)
                    if match and 0<=int(match[3])-int(match[2])<=10000:
                        names.update(normalize(match[1]+str(n)) for n in range(int(match[2]),int(match[3])+1))
    return {"names":sorted(names),"strip_names":sorted(strips),"strip_order":strip_order,
            "files":statuses,"purpose":"warning_only"}
