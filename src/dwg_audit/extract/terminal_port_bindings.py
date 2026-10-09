from __future__ import annotations

import math
import json
import re
from collections.abc import Iterable
from typing import Any

from dwg_audit.domain.models import TerminalPortBinding
from dwg_audit.domain.models import TextItem


TERMINAL_PORT_BINDING_SCHEMA_VERSION = "terminal-port-binding-v1"
TERMINAL_PORT_GEOMETRY_TOLERANCE = 0.25

_SPECIAL_APPID = "LD_SYMB2_SPECIAL"
_SPECIAL_VALUE = "装置端子"
_TEXT_APPID_PATTERN = re.compile(r"LD_SYMB2_TERM_TEXT_\d+\Z")
_RECORD_INSERT_HANDLE_PATTERN = re.compile(r"(?i)([0-9A-F]+):\d+")
_HANDLE_PATTERN = re.compile(r"(?i)[0-9A-F]+\Z")
_PART_KEY_PATTERN = re.compile(r"PART2_\d+\Z")


def bind_labelled_terminal_ports(document: Any, texts: list[TextItem], proposals: list[Any]) -> None:
    """Bind reciprocal CAD labels to known terminal geometry, without any union.

    Unlike device XRECORD bindings, ordinary terminal labels may describe four
    independent outward contacts. The library must recognize the geometry and
    both CAD objects must reference each other in the same owner space.
    """
    from dwg_audit.audit.symbol_port_proposal import classify_definition_family

    definitions = {}
    for proposal in proposals:
        family = classify_definition_family(proposal.to_dict())
        if (family["family_id"] != "labelled_terminal.generic.v1"
                or family["classifier_status"] != "MATCHED"):
            continue
        ports = proposal.ports
        rule = family["matched_family_rule_id"]
        if family["classifier_confidence"] < 0.95:
            ports = _verified_radial_round_ports(proposal, document.blocks.get(proposal.definition_name))
            if not ports:
                continue
            count_name = "two" if len(ports) == 2 else "three"
            rule = f"verified-{count_name}-radial-contact-terminal-v1"
        definitions[proposal.definition_name] = (ports, rule)
    for text in texts:
        entity = document.entitydb.get(text.handle)
        if entity is None:
            continue
        refs = _xdata_strings(entity, "LD_SYMB2_LABEL", 1005)
        if len(refs) != 1:
            continue
        insert = document.entitydb.get(refs[0])
        if insert is None or insert.dxftype() != "INSERT":
            continue
        if _xdata_strings(insert, "LD_SYMB2_SPECIAL", 1000) != ["端子"]:
            continue
        if _xdata_strings(insert, "LD_SYMB2_LABEL", 1005) != [text.handle]:
            continue
        if insert.dxf.owner != entity.dxf.owner:
            continue
        known = definitions.get(insert.dxf.name)
        if known is None:
            continue
        local_ports, rule = known
        matrix = insert.matrix44()
        ports = []
        for port in local_ports:
            point = matrix.transform(port.local_position)
            direction = matrix.transform_direction(port.outward_direction).normalize()
            ports.append({
                "insert_handle": _entity_handle(insert), "text_handle": text.handle,
                "port_id": port.port_id, "position": [point.x, point.y],
                "outward_direction": [direction.x, direction.y],
                "family_rule": rule,
                "source": "reciprocal_cad_label_and_terminal_geometry",
                "electrical_union_eligible": False,
            })
        text.physical_ports_json = json.dumps(ports, ensure_ascii=False)


def _verified_radial_round_ports(proposal: Any, block: Any) -> tuple:
    """Verify two opposite contacts or recover a third radial side contact.

    Reuse normalized symbol features: a complete round body, radial leads
    and matching hidden contact markers must all agree. The coarse
    equal-arc family alone is never authority for extra attachment points.
    """
    from dwg_audit.audit.symbol_port_proposal import ProposedPort

    shape = (proposal.geometry_summary or {}).get("shape_features", {})
    histogram = shape.get("entity_histogram", {})
    count = histogram.get("LINE")
    if count not in {2, 3} or histogram != {"ARC": 2, "LINE": count, "LWPOLYLINE": count}:
        return ()
    arcs = shape.get("normalized_arcs", [])
    contacts = shape.get("normalized_closed_bulged_contacts", [])
    lines = shape.get("normalized_line_segments", [])
    if len(arcs) != 2 or len(contacts) != count or len(lines) != count:
        return ()
    center, radius = arcs[0]["center"], arcs[0]["radius"]
    tolerance = radius * 0.02
    if radius <= 0 or any(
        math.dist(arc["center"], center) > tolerance
        or abs(arc["radius"]-radius) > tolerance
        or abs(arc["sweep_deg"]-180) > 0.01 for arc in arcs
    ):
        return ()
    if math.dist(arcs[0]["midpoint"], arcs[1]["midpoint"]) < 1.98*radius:
        return ()
    if any(not c["invisible"] or not 0 < c["radius"] < radius*0.5 for c in contacts):
        return ()
    verified = []
    for contact in contacts:
        point = contact["center"]
        touching = [line for line in lines if min(math.dist(point, line[key]) for key in ("start", "end")) <= tolerance]
        if len(touching) != 1:
            return ()
        line = touching[0]
        inner = max((line["start"], line["end"]), key=lambda p: math.dist(p, point))
        outer_radius = math.dist(point, center)
        if abs(math.dist(inner, center)-radius) > tolerance or outer_radius <= 1.5*radius:
            return ()
        direction = [(point[i]-center[i])/outer_radius for i in (0, 1)]
        inner_direction = [(inner[i]-center[i])/radius for i in (0, 1)]
        if sum(a*b for a, b in zip(direction, inner_direction)) < 0.98:
            return ()
        verified.append((point, direction))
    # One opposite pair, optionally with one perpendicular side; never use
    # an open switch or arbitrary arc mechanism as terminal authority.
    dots = [sum(a*b for a, b in zip(verified[i][1], verified[j][1]))
            for i in range(count) for j in range(i+1, count)]
    if sum(dot < -0.98 for dot in dots) != 1 or sum(abs(dot) < 0.02 for dot in dots) != (2 if count == 3 else 0):
        return ()
    body = next((e for e in block if e.dxftype() == "ARC"), None)
    if body is None:
        return ()
    scale = max(shape["width"], shape["height"])
    return tuple(ProposedPort(
        port_id=f"RP{index}",
        local_position=(body.dxf.center.x+(point[0]-center[0])*scale,
                        body.dxf.center.y+(point[1]-center[1])*scale, body.dxf.center.z),
        outward_direction=(*direction, 0.0), port_type="ELECTRICAL", confidence=0.98,
        evidence_codes=("RADIAL_BODY_LEAD", "HIDDEN_CONTACT_MARKER"),
        source_ids=(f"machine_geometry_proposal:{proposal.definition_name}",),
    ) for index, (point, direction) in enumerate(verified, 1))


def bind_vendor_device_pin_labels(document: Any, texts: list[TextItem]) -> None:
    """Retain reciprocal pin-label ownership and its drawn boundary stub.

    This is label context, not a complete XRECORD port binding or a symbol
    library port proposal. A consumer must separately prove the device body
    and the actual external CONNECT lead before using it as a mapping.
    """
    by_handle = {text.handle: text for text in texts}
    contexts: dict[str, list[dict]] = {}
    for insert in document.modelspace().query("INSERT"):
        if _xdata_strings(insert, _SPECIAL_APPID, 1000) != [_SPECIAL_VALUE]:
            continue
        references = _terminal_text_references(insert)
        handles = {handle for values in references.values() for handle in values}
        if not references or len(handles) != 1 or any(not values for values in references.values()):
            continue
        handle = next(iter(handles))
        text = by_handle.get(handle)
        entity = document.entitydb.get(handle)
        if text is None or entity is None or not re.fullmatch(r"\d{2,4}", text.normalized_text):
            continue
        reciprocal = _terminal_text_references(entity)
        insert_handle = _entity_handle(insert)
        if set(references) != set(reciprocal) or any(values != {insert_handle} for values in reciprocal.values()):
            continue
        body_refs = _xdata_strings(insert, "LD_SYMB2_LABEL", 1005)
        if len(body_refs) != 1 or body_refs[0] not in by_handle:
            continue
        body = by_handle[body_refs[0]]
        body_entity = document.entitydb.get(body.handle)
        if body_entity is None or not re.fullmatch(r"\d+(?:-\d+)*n", body.normalized_text, re.IGNORECASE):
            continue
        if entity.dxf.owner != insert.dxf.owner or body_entity.dxf.owner != insert.dxf.owner:
            continue
        point = _point(insert.dxf.insert)
        if point is None:
            continue
        stub = _unique_outward_definition_line(insert, point, TERMINAL_PORT_GEOMETRY_TOLERANCE)
        if stub is None:
            continue
        chain = _declared_pin_stub_chain(insert, point, stub)
        if chain is None:
            continue
        contexts.setdefault(text.text_id, []).append({
            "source": "reciprocal_cad_device_pin_label", "insert_handle": insert_handle,
            "text_handle": handle, "body_text_id": body.text_id, "body_text_handle": body.handle,
            "body_value": body.normalized_text, "label_anchor": list(point),
            "stub_inner_point": list(chain[0]), "definition_line_handle": stub[0],
            "definition_stub_line_handles": chain[1],
            "complete_xrecord_binding": False, "internal_connectivity_inferred": False,
            "electrical_union_eligible": False,
        })
    for text in texts:
        candidates = contexts.get(text.text_id, [])
        if len(candidates) == 1:
            text.device_pin_label_json = json.dumps(candidates[0], ensure_ascii=False)


def _declared_pin_stub_chain(insert: Any, origin: tuple, stub: tuple) -> tuple | None:
    """Follow only the declared glyph's continuous straight LINE artwork."""
    matrix = insert.matrix44()
    segments = []
    for entity in insert.block():
        if entity.dxftype() != "LINE":
            continue
        start, end = matrix.transform(entity.dxf.start), matrix.transform(entity.dxf.end)
        segments.append((_entity_handle(entity), (start.x, start.y), (end.x, end.y)))
    current, handles = stub[3], [stub[0]]
    direction = [current[i]-origin[i] for i in (0, 1)]
    length = math.hypot(*direction)
    if length <= 0:
        return None
    for _ in range(len(segments)):
        choices = []
        for handle, start, end in segments:
            if handle in handles:
                continue
            for first, second in ((start, end), (end, start)):
                if math.dist(first, current) <= 1e-6:
                    choices.append((handle, second))
        if not choices:
            return current, handles
        if len(choices) != 1:
            return None
        handle, next_point = choices[0]
        vector = [next_point[i]-current[i] for i in (0, 1)]
        step = math.hypot(*vector)
        if step <= 0 or sum(vector[i]*direction[i] for i in (0, 1))/(step*length) < 0.999999:
            return None
        current = next_point
        handles.append(handle)
    return None


def extract_terminal_port_bindings(
    document: Any,
    *,
    sheet_id: str,
    file_id: str,
    tolerance: float = TERMINAL_PORT_GEOMETRY_TOLERANCE,
) -> list[TerminalPortBinding]:
    """Read complete vendor-owned terminal ports without inferring connectivity."""

    normalized_tolerance = _finite_number(tolerance)
    if normalized_tolerance is None or normalized_tolerance <= 0.0:
        return []
    records = _terminal_xrecords(document)
    if not records:
        return []

    try:
        inserts = list(document.modelspace().query("INSERT"))
    except Exception:
        return []

    bindings: list[TerminalPortBinding] = []
    for insert in inserts:
        try:
            binding = _binding_for_insert(
                document,
                insert,
                records,
                sheet_id=sheet_id,
                file_id=file_id,
                tolerance=normalized_tolerance,
            )
        except Exception:
            binding = None
        if binding is not None:
            bindings.append(binding)
    return bindings


def _binding_for_insert(
    document: Any,
    insert: Any,
    records: list[tuple[Any, dict[str, list[str]], list[str], set[str]]],
    *,
    sheet_id: str,
    file_id: str,
    tolerance: float,
) -> TerminalPortBinding | None:
    if _xdata_strings(insert, _SPECIAL_APPID, 1000) != [_SPECIAL_VALUE]:
        return None

    insert_handle = _entity_handle(insert)
    definition_name = _normalized_text(getattr(insert.dxf, "name", ""))
    owner_handle = _normalized_handle(getattr(insert.dxf, "owner", ""))
    if not insert_handle or not definition_name or not owner_handle:
        return None

    text_references = _terminal_text_references(insert)
    text_handles = {handle for handles in text_references.values() for handle in handles}
    if len(text_handles) != 1:
        return None
    text_handle = next(iter(text_handles))
    text_entity = document.entitydb.get(text_handle)
    if text_entity is None or text_entity.dxftype() not in {"TEXT", "MTEXT", "ATTRIB"}:
        return None
    if _normalized_handle(getattr(text_entity.dxf, "owner", "")) != owner_handle:
        return None

    reciprocal_references = _terminal_text_references(text_entity)
    reciprocal_handles = {
        handle for handles in reciprocal_references.values() for handle in handles
    }
    reciprocal_appids = {
        appid
        for appid in text_references.keys() & reciprocal_references.keys()
        if text_references[appid] == {text_handle}
        and reciprocal_references[appid] == {insert_handle}
    }
    if reciprocal_handles != {insert_handle} or not reciprocal_appids:
        return None
    text_value = _entity_text(text_entity)
    if not text_value:
        return None

    matching_records = [
        row
        for row in records
        if row[2] == [insert_handle]
        and insert_handle in row[3]
        and _SPECIAL_VALUE in row[3]
        and definition_name.casefold() in {token.casefold() for token in row[3]}
        and text_value.casefold() in {token.casefold() for token in row[3]}
    ]
    if len(matching_records) != 1:
        return None
    xrecord, fields, _, _ = matching_records[0]

    connect_values = fields.get("CONNECTLINEHANDLE", [])
    if len(connect_values) != 1:
        return None
    connect_handle = _normalized_handle(connect_values[0])
    if not connect_handle or not _HANDLE_PATTERN.fullmatch(connect_handle):
        return None
    connect_line = document.entitydb.get(connect_handle)
    if connect_line is None or connect_line.dxftype() != "LINE":
        return None
    if _normalized_handle(getattr(connect_line.dxf, "owner", "")) != owner_handle:
        return None
    if _normalized_text(getattr(connect_line.dxf, "layer", "")).casefold() != "connect":
        return None

    xrecord_owner_handle = _normalized_handle(getattr(xrecord.dxf, "owner", ""))
    xrecord_owner = document.entitydb.get(xrecord_owner_handle)
    if (
        not xrecord_owner_handle
        or xrecord_owner is None
        or xrecord_owner.dxftype() != "DICTIONARY"
        or not _dictionary_owns(xrecord_owner, xrecord)
    ):
        return None

    insert_point = _point(getattr(insert.dxf, "insert", None))
    connect_start = _point(getattr(connect_line.dxf, "start", None))
    connect_end = _point(getattr(connect_line.dxf, "end", None))
    if insert_point is None or connect_start is None or connect_end is None:
        return None
    if sum(
        (
            _points_close(connect_start, insert_point, tolerance),
            _points_close(connect_end, insert_point, tolerance),
        )
    ) != 1:
        return None

    port_line = _unique_outward_definition_line(insert, insert_point, tolerance)
    if port_line is None:
        return None
    definition_line_handle, port_line_start, port_line_end, port_point = port_line

    xrecord_handle = _entity_handle(xrecord)
    if not xrecord_handle:
        return None
    return TerminalPortBinding(
        schema_version=TERMINAL_PORT_BINDING_SCHEMA_VERSION,
        sheet_id=sheet_id,
        file_id=file_id,
        insert_handle=insert_handle,
        text_handle=text_handle,
        connect_line_handle=connect_handle,
        definition_line_handle=definition_line_handle,
        xrecord_handle=xrecord_handle,
        xrecord_owner_handle=xrecord_owner_handle,
        definition_name=definition_name,
        text_value=text_value,
        insert_x=insert_point[0],
        insert_y=insert_point[1],
        connect_start_x=connect_start[0],
        connect_start_y=connect_start[1],
        connect_end_x=connect_end[0],
        connect_end_y=connect_end[1],
        port_line_start_x=port_line_start[0],
        port_line_start_y=port_line_start[1],
        port_line_end_x=port_line_end[0],
        port_line_end_y=port_line_end[1],
        port_x=port_point[0],
        port_y=port_point[1],
    )


def _terminal_xrecords(
    document: Any,
) -> list[tuple[Any, dict[str, list[str]], list[str], set[str]]]:
    try:
        xrecords = list(document.objects.query("XRECORD"))
    except Exception:
        return []
    parsed = []
    for xrecord in xrecords:
        try:
            values = [str(tag.value).strip() for tag in xrecord.tags if tag.code == 1]
        except Exception:
            continue
        if not values or len(values) % 2:
            continue
        fields: dict[str, list[str]] = {}
        for key, value in zip(values[::2], values[1::2], strict=True):
            normalized_key = key.strip().upper()
            if not normalized_key:
                fields = {}
                break
            fields.setdefault(normalized_key, []).append(value.strip())
        if len(fields.get("LINENO", [])) != 1 or "CONNECTLINEHANDLE" not in fields:
            continue
        part_values = [
            value
            for key, rows in fields.items()
            if _PART_KEY_PATTERN.fullmatch(key)
            for value in rows
        ]
        if not part_values:
            continue
        line_handles = [
            match.upper()
            for value in fields["LINENO"]
            for match in _RECORD_INSERT_HANDLE_PATTERN.findall(value)
        ]
        part_tokens = {
            _normalized_text(token)
            for value in part_values
            for token in value.split("||")
            if _normalized_text(token)
        }
        parsed.append((xrecord, fields, line_handles, part_tokens))
    return parsed


def _terminal_text_references(entity: Any) -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}
    for appid, tags in _xdata_map(entity).items():
        appid_text = str(appid)
        if not _TEXT_APPID_PATTERN.fullmatch(appid_text):
            continue
        references[appid_text] = {
            handle
            for value in _tag_values(tags, 1005)
            if (handle := _normalized_handle(value)) and handle != "0"
        }
    return references


def _unique_outward_definition_line(
    insert: Any,
    insert_point: tuple[float, float],
    tolerance: float,
) -> tuple[str, tuple[float, float], tuple[float, float], tuple[float, float]] | None:
    try:
        source_children = list(insert.block())
        world_children = list(insert.virtual_entities())
    except Exception:
        return None
    candidates = []
    for index, world_child in enumerate(world_children):
        if world_child.dxftype() != "LINE" or index >= len(source_children):
            continue
        source_child = source_children[index]
        if source_child.dxftype() != "LINE":
            continue
        start = _point(getattr(world_child.dxf, "start", None))
        end = _point(getattr(world_child.dxf, "end", None))
        if start is None or end is None:
            continue
        start_at_origin = _points_close(start, insert_point, tolerance)
        end_at_origin = _points_close(end, insert_point, tolerance)
        if start_at_origin == end_at_origin:
            continue
        source_handle = _entity_handle(source_child)
        if not source_handle:
            continue
        candidates.append((source_handle, start, end, end if start_at_origin else start))
    return candidates[0] if len(candidates) == 1 else None


def _dictionary_owns(dictionary: Any, xrecord: Any) -> bool:
    xrecord_handle = _entity_handle(xrecord)
    try:
        return any(_entity_handle(value) == xrecord_handle for _, value in dictionary.items())
    except Exception:
        return False


def _xdata_map(entity: Any) -> dict[str, Iterable[Any]]:
    xdata = getattr(entity, "xdata", None)
    return (getattr(xdata, "data", {}) or {}) if xdata is not None else {}


def _xdata_strings(entity: Any, appid: str, code: int) -> list[str]:
    tags = _xdata_map(entity).get(appid)
    return _tag_values(tags, code) if tags is not None else []


def _tag_values(tags: Iterable[Any], code: int) -> list[str]:
    return [str(tag.value).strip() for tag in tags if tag.code == code]


def _entity_handle(entity: Any) -> str:
    return _normalized_handle(getattr(entity.dxf, "handle", ""))


def _normalized_handle(value: Any) -> str:
    return str(value or "").strip().upper()


def _normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _entity_text(entity: Any) -> str:
    if entity.dxftype() == "MTEXT":
        try:
            return _normalized_text(entity.plain_text())
        except Exception:
            return ""
    return _normalized_text(getattr(entity.dxf, "text", ""))


def _point(value: Any) -> tuple[float, float] | None:
    try:
        point = (float(value.x), float(value.y))
    except (AttributeError, TypeError, ValueError):
        return None
    return point if all(math.isfinite(item) for item in point) else None


def _points_close(
    left: tuple[float, float],
    right: tuple[float, float],
    tolerance: float,
) -> bool:
    return math.hypot(left[0] - right[0], left[1] - right[1]) <= tolerance


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    normalized = float(value)
    return normalized if math.isfinite(normalized) else None
