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

from ezdxf.math import Matrix44, Vec3

from dwg_audit.domain.models import (SwSymbolInstance, SwPort, SwStripRow,
    SwPartInstance, SwConnectLabel, SwConnectDot, TextItem)


def normalize(value: str) -> str:
    # Same endpoint normalization used by the legacy page extractor.
    from dwg_audit.audit.candidates import _normalize_schematic_semantic_endpoint_value
    return _normalize_schematic_semantic_endpoint_value(unicodedata.normalize("NFKC", value))


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
    point = entity.dxf.insert
    if transform is not None:
        point = transform.transform(point)
    return {"handle": handle, "resolved": True, "value": value, "normalized": normalize(value),
            "x": float(point.x), "y": float(point.y), "height": float(entity.dxf.char_height if entity.dxftype() == "MTEXT" else entity.dxf.height), "text_id": None}


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

    def extend(self, other):
        for name in ("symbols", "ports", "strip_rows", "part_instances", "connect_labels", "connect_dots",
                     "coverage_observations", "conflict_observations"):
            getattr(self, name).extend(getattr(other, name))
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
            if not pin:
                candidates = []
                for ref in local_texts:
                    distance = _point_segment_distance(ref["x"], ref["y"], a.x, a.y, b.x, b.y)
                    height = float(ref.get("height") or 0.0)
                    if height > 0 and distance <= height * 3.0 + 1e-8:
                        candidates.append((distance, ref))
                candidates.sort(key=lambda item: (item[0], item[1].get("handle") or ""))
                if candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] >= max(0.25, candidates[0][1].get("height", 0.0) * 0.25)):
                    pin = dict(candidates[0][1])
                    pin["resolution_method"] = "definition_text_nearest"
                    pin["nearest_distance"] = candidates[0][0]
                    pin["reciprocal_ok"] = True
            if pin and not number:
                number = pin.get("normalized", "")
            yield entity, number, a, b, path, pin


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


def extract_superworks_semantics(doc, *, sheet_id: str, file_id: str) -> SuperworksData:
    start = time.perf_counter()
    data = SuperworksData()
    grid = _wire_index(doc)

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
            position = parent.transform(insert.dxf.insert)
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
                reasons.append("stale_label_reference")
            validation = {"handle_resolved": bool(label.get("resolved")), "reciprocal_ok": reciprocal,
                          "label_distance": distance, "stale_suspect": "stale_label_reference" in reasons}
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
                        endpoint = (endpoint + ("" if category == "装置端子" else "-") + pin_value) if endpoint and pin_value else None
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
            data.strip_rows.append(SwStripRow(record_id=f"SWR:{file_id}:{sheet_id}:{e.dxf.handle}", sheet_id=sheet_id,file_id=file_id,
                row_handle=e.dxf.handle,header=header,row=row, endpoint_identity=(header.get("normalized","")+row.get("normalized","")) or None,
                connections=connections,potentials=potentials,cross_page_refs=cross_refs, raw_xdata=raw(e),
                validation={"handle_resolved": bool(header.get("resolved")),"reciprocal_ok":reciprocal},reason_codes=sorted(set(reasons)),
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
    for e in tagged:
        if e.dxftype() not in ("TEXT","MTEXT"):
            continue
        text = text_ref(doc,e.dxf.handle)
        proposals = []
        for line in lines:
            distance = min(math.hypot(text["x"]-p.x,text["y"]-p.y) for p in (line.dxf.start,line.dxf.end))
            if distance <= max(5, text["height"]*3):
                proposals.append((abs(int(e.dxf.handle,16)-int(line.dxf.handle,16)),distance,line))
        proposals.sort(key=lambda p:(p[0],p[1]))
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
            candidate=f"{label.get('normalized')}-{number}" if label.get("normalized") else ""
            strip_refs=destinations.get(candidate.casefold(),[])
            if candidate and strip_refs:
                pin={"handle":None,"text_id":None,"value":number,"normalized":number,"resolved":True,
                     "reciprocal_ok":True,"resolution_method":"strip_reverse_corroboration",
                     "corroborating_strip_refs":strip_refs,
                     "corroborating_strip_text_ids":sorted({ref["connection_text_id"] for ref in strip_refs if ref.get("connection_text_id")})}
                if is_record:
                    port.pin=pin
                    port.endpoint_identity=candidate
                    port.reason_codes=[reason for reason in port.reason_codes if reason not in ("unresolved_pin_text","nonreciprocal_pin")]
                else:
                    port["pin"]=pin
                    port["endpoint_identity"]=candidate
                    port.setdefault("validation",{})["pin_resolution_method"]="strip_reverse_corroboration"
                    port["reason_codes"]=[reason for reason in port.get("reason_codes",[]) if reason not in ("unresolved_pin_text","nonreciprocal_pin")]
        method=pin.get("resolution_method") if pin.get("resolved") and pin.get("reciprocal_ok",True) else None
        counts[method if method in counts else "unresolved"]+=1
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
