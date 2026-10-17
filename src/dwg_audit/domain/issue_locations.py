"""Normalized user-facing locations of actionable issues ("位置清单").

Each user-visible issue carries ``evidence["locations"]``: one entry for every
place a reviewer has to look at (a terminal text on a sheet, a wire, a table
row, an unnumbered symbol pin). The desktop lists them and the preview crops
to their bounding boxes.

Locations are derived only from the issue's own evidence (its refs and its
observation sides). Nothing is looked up in the global pair list, so a
connection already discarded upstream, e.g. as device-internal, cannot be
revived here. Diagnostic rules never get locations.
"""

from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

from dwg_audit.domain.issue_layers import USER_VISIBLE_RULE_IDS

ROLE_CONFLICT_PARTY = "conflict_party"
ROLE_TABLE_ROW = "table_row"
ROLE_WIRE = "wire"
ROLE_UNNUMBERED_SYMBOL = "unnumbered_symbol"

UNNUMBERED_LABEL = "无编号"

# Bounding boxes are padded so a single text or a short wire is still visible.
# Drawing units are CAD world units (text height is about 2.5), so the minimum
# pad is a few units and grows with the span of the located objects.
_BBOX_PAD_MIN = 4.0
_BBOX_PAD_RATIO = 0.25

_LOCATION_FIELDS = (
    "location_id",
    "role",
    "sheet_id",
    "file_id",
    "filename",
    "sheet_no",
    "sheet_title",
    "sheet_order",
    "terminal",
    "peer",
    "text_id",
    "point",
    "peer_point",
    "wire",
    "bbox",
    "pair_id",
    "renderable",
)


def build_locations(issue: Any) -> list[dict[str, Any]]:
    """Locations for an Issue object or an issue payload dict."""
    return derive_locations_from_refs(issue)


def attach_locations(issue: Any) -> None:
    """Store normalized locations on a user-visible Issue; diagnostics are left untouched.

    Any previously stored list is ignored, so a re-run after the refs changed
    cannot keep stale locations.
    """
    if getattr(issue, "rule_id", None) not in USER_VISIBLE_RULE_IDS:
        return
    evidence = dict(issue.evidence or {})
    evidence.pop("locations", None)
    payload = _as_payload(issue)
    payload["evidence"] = evidence
    issue.evidence = {**evidence, "locations": derive_locations_from_refs(payload)}


def derive_locations_from_refs(payload: Any) -> list[dict[str, Any]]:
    """Locations from an Issue or payload dict. Stored locations win; otherwise derive from refs."""
    data = _as_payload(payload)
    evidence = _as_dict(data.get("evidence"))
    stored = evidence.get("locations")
    if isinstance(stored, list) and stored:
        return [_finish(_clean_location(item), index, data) for index, item in enumerate(stored) if isinstance(item, dict)]
    rule_id = str(data.get("rule_id") or "")
    if rule_id not in USER_VISIBLE_RULE_IDS:
        return []

    raw: list[dict[str, Any]] = []
    refs = [ref for ref in _as_list(data.get("evidence_refs")) if isinstance(ref, dict)]
    observation_refs = [ref for ref in refs if ref.get("kind") == "native_resolution"]
    pair_refs = [ref for ref in refs if ref.get("kind") != "native_resolution"]

    if _is_superworks_observation(rule_id, evidence):
        raw.extend(_observation_locations(data, evidence))
    for ref in observation_refs:
        raw.extend(_observation_ref_locations(data, ref))
    if not pair_refs and not raw:
        pair_refs = [_top_level_ref(data, evidence)]
    for ref in pair_refs:
        raw.append(_pair_ref_location(rule_id, data, ref))
    return [_finish(item, index, data) for index, item in enumerate(_dedupe(raw))]


# --- per-rule derivation -------------------------------------------------------

def _pair_ref_location(rule_id: str, data: dict[str, Any], ref: dict[str, Any]) -> dict[str, Any]:
    """One pair-based location; which side is the terminal depends on the rule."""
    left_known = ref.get("left_value") not in (None, "")
    if rule_id == "R-MANY-TO-ONE":
        # Several left values feed one right value: the shared right value is the terminal.
        terminal_side = "right"
    else:
        # Single-side pairs (missing left) are anchored on the side that exists.
        terminal_side = "left" if left_known or ref.get("right_value") in (None, "") else "right"
    if terminal_side == "left":
        terminal, peer = ref.get("left_value"), ref.get("right_value")
        text_id, point, peer_point = ref.get("left_text_id"), ref.get("point"), ref.get("peer_point")
    else:
        terminal, peer = ref.get("right_value"), ref.get("left_value")
        text_id, point, peer_point = ref.get("right_text_id"), ref.get("peer_point"), ref.get("point")

    if rule_id == "R-TABLE-MAPPING-SOURCE-CONFLICT" and ref.get("source_kind") != "table_mapping":
        role = ROLE_WIRE
    elif rule_id == "R-TABLE-MAPPING-SOURCE-CONFLICT":
        role = ROLE_TABLE_ROW
    else:
        role = ROLE_CONFLICT_PARTY

    wire = None
    if ref.get("line_group_id") and _is_point(ref.get("line_start")) and _is_point(ref.get("line_end")):
        wire = {
            "line_group_id": ref.get("line_group_id"),
            "start": _point(ref.get("line_start")),
            "end": _point(ref.get("line_end")),
        }
    return {
        "role": role,
        "sheet_id": ref.get("sheet_id") or data.get("sheet_id"),
        "file_id": ref.get("file_id") or data.get("file_id"),
        "filename": ref.get("filename") or data.get("filename"),
        "sheet_no": ref.get("sheet_no") or data.get("sheet_no"),
        "sheet_title": ref.get("sheet_title") or _as_dict(data.get("evidence")).get("sheet_title"),
        "sheet_order": ref.get("sheet_order", data.get("sheet_order")),
        "terminal": _text_or_none(terminal),
        "peer": _text_or_none(peer),
        "text_id": _text_or_none(text_id),
        "point": _point(point),
        "peer_point": _point(peer_point),
        "wire": wire,
        "pair_id": ref.get("pair_id"),
    }


def _observation_locations(data: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Port locations of a SuperWORKS observation (both sides, one entry per physical port)."""
    sides = [_as_dict(evidence.get("left")), _as_dict(evidence.get("right"))]
    locations = _port_locations(data, sides, sheet=_sheet_of(data, evidence))
    if not locations:
        wire = _observation_wire(evidence)
        if wire is not None:
            locations.append(_wire_location(data, wire, sheet=_sheet_of(data, evidence), values=(
                _text_or_none(sides[0].get("value")), _text_or_none(sides[1].get("value")))))
    return locations


def _observation_ref_locations(data: dict[str, Any], ref: dict[str, Any]) -> list[dict[str, Any]]:
    """Witness observations merged into one review item: the same port model, from the ref."""
    sides = [_as_dict(ref.get("left")), _as_dict(ref.get("right"))]
    sheet = {
        "sheet_id": ref.get("sheet_id"),
        "file_id": ref.get("file_id"),
        "filename": ref.get("filename"),
        "sheet_no": ref.get("sheet_no"),
        "sheet_title": ref.get("sheet_title"),
        "sheet_order": ref.get("sheet_order"),
    }
    locations = _port_locations(data, sides, sheet=sheet)
    if not locations and _is_point(ref.get("line_start")) and _is_point(ref.get("line_end")):
        wire = {"line_group_id": ref.get("line_group_id"), "start": ref.get("line_start"), "end": ref.get("line_end")}
        locations.append(_wire_location(data, wire, sheet=sheet, values=(None, None)))
    return locations


def _port_locations(data: dict[str, Any], sides: list[dict[str, Any]], *, sheet: dict[str, Any]) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    for index, side in enumerate(sides):
        peer_side = sides[1 - index] if len(sides) == 2 else {}
        peer = _text_or_none(peer_side.get("value"))
        for port in _as_list(side.get("ports")):
            if not isinstance(port, dict):
                continue
            start, end = _point(port.get("start")), _point(port.get("end"))
            if start is None or end is None:
                continue
            identity = _text_or_none(port.get("endpoint_identity")) or _text_or_none(side.get("value"))
            center = [(start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0]
            locations.append({
                "role": ROLE_CONFLICT_PARTY if identity else ROLE_UNNUMBERED_SYMBOL,
                **sheet,
                "terminal": identity or UNNUMBERED_LABEL,
                "peer": peer,
                "text_id": None,
                "point": center,
                "peer_point": None,
                "wire": None,
                "pair_id": None,
                "port_id": _text_or_none(port.get("port_id")),
                "port_box": [min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1])],
            })
    return locations


def _wire_location(data: dict[str, Any], wire: dict[str, Any], *, sheet: dict[str, Any], values: tuple[Any, Any]) -> dict[str, Any]:
    left, right = values
    return {
        "role": ROLE_WIRE,
        **sheet,
        "terminal": left or right,
        "peer": right if left else None,
        "text_id": None,
        "point": None,
        "peer_point": None,
        "wire": {"line_group_id": _text_or_none(wire.get("line_group_id")), "start": _point(wire.get("start")), "end": _point(wire.get("end"))},
        "pair_id": None,
    }


def _top_level_ref(data: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Single-pair issues written before refs carried coordinates: use the issue's own fields."""
    return {
        "pair_id": data.get("pair_id") or evidence.get("pair_id"),
        "sheet_id": data.get("sheet_id"),
        "file_id": data.get("file_id"),
        "filename": data.get("filename"),
        "sheet_no": data.get("sheet_no"),
        "sheet_title": evidence.get("sheet_title"),
        "sheet_order": data.get("sheet_order"),
        "line_group_id": data.get("line_group_id") or evidence.get("line_group_id"),
        "line_start": evidence.get("line_start"),
        "line_end": evidence.get("line_end"),
        "left_value": data.get("left_value"),
        "right_value": data.get("right_value"),
        "left_text_id": evidence.get("left_text_id"),
        "right_text_id": evidence.get("right_text_id"),
        "point": evidence.get("left_point"),
        "peer_point": evidence.get("right_point"),
        "source_kind": "table_mapping" if evidence.get("source") == "table_mapping" else "ordinary_pair",
    }


# --- shaping ---------------------------------------------------------------------

def _finish(item: dict[str, Any], index: int, data: dict[str, Any]) -> dict[str, Any]:
    """Fill the stable fields: id, bbox from the located objects, renderable flag."""
    issue_key = str(data.get("issue_id") or "issue")
    out = {key: item.get(key) for key in _LOCATION_FIELDS if key not in {"location_id", "bbox", "renderable"}}
    out["location_id"] = str(item.get("location_id") or f"{issue_key}#{index + 1}")
    out["role"] = str(item.get("role") or ROLE_CONFLICT_PARTY)
    out["sheet_id"] = _text_or_none(out.get("sheet_id"))
    out["file_id"] = _text_or_none(out.get("file_id"))
    out["point"] = _point(out.get("point"))
    out["peer_point"] = _point(out.get("peer_point"))
    out["wire"] = _clean_wire(out.get("wire"))
    stored_bbox = item.get("bbox")
    out["bbox"] = [round(float(v), 3) for v in stored_bbox] if _is_box(stored_bbox) else _location_bbox(out, item.get("port_box"))
    out["renderable"] = bool(out["sheet_id"]) and bool(out["bbox"] or out["point"] or out["wire"])
    if item.get("port_id"):
        out["port_id"] = item["port_id"]
    return out


def _clean_location(item: Any) -> dict[str, Any]:
    return dict(item) if isinstance(item, dict) else {}


def _location_bbox(item: dict[str, Any], port_box: Any = None) -> list[float] | None:
    points: list[list[float]] = []
    for value in (item.get("point"), item.get("peer_point")):
        if value:
            points.append(value)
    wire = item.get("wire")
    if isinstance(wire, dict):
        for value in (wire.get("start"), wire.get("end")):
            if value:
                points.append(value)
    boxes: list[list[float]] = []
    if _is_box(port_box):
        boxes.append(list(port_box))
    if not points and not boxes:
        return None
    xs = [p[0] for p in points] + [b[0] for b in boxes] + [b[2] for b in boxes]
    ys = [p[1] for p in points] + [b[1] for b in boxes] + [b[3] for b in boxes]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    pad = max(_BBOX_PAD_MIN, _BBOX_PAD_RATIO * max(max_x - min_x, max_y - min_y))
    return [round(min_x - pad, 3), round(min_y - pad, 3), round(max_x + pad, 3), round(max_y + pad, 3)]


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = (
            item.get("sheet_id"),
            item.get("port_id") or item.get("pair_id"),
            item.get("role"),
            item.get("terminal"),
            item.get("peer"),
            json.dumps(item.get("point"), sort_keys=True) if item.get("port_id") is None else None,
            json.dumps(item.get("wire"), sort_keys=True),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _sheet_of(data: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "sheet_id": data.get("sheet_id"),
        "file_id": data.get("file_id"),
        "filename": data.get("filename") or evidence.get("filename"),
        "sheet_no": data.get("sheet_no") or evidence.get("sheet_no"),
        "sheet_title": evidence.get("sheet_title"),
        "sheet_order": data.get("sheet_order") if data.get("sheet_order") is not None else evidence.get("sheet_order"),
    }


def _observation_wire(evidence: dict[str, Any]) -> dict[str, Any] | None:
    start, end = evidence.get("line_start"), evidence.get("line_end")
    if not (_is_point(start) and _is_point(end)):
        return None
    return {"line_group_id": evidence.get("line_group_id"), "start": start, "end": end}


def _is_superworks_observation(rule_id: str, evidence: dict[str, Any]) -> bool:
    """Coordinator observations embed their own two endpoint sides (IssueFactory pairs do not)."""
    return rule_id == "R-SUPERWORKS-CONFLICT" and isinstance(evidence.get("left"), dict) and isinstance(evidence.get("right"), dict)


def _clean_wire(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    start, end = _point(value.get("start")), _point(value.get("end"))
    line_group_id = _text_or_none(value.get("line_group_id"))
    if start is None and end is None and not line_group_id:
        return None
    return {"line_group_id": line_group_id, "start": start, "end": end}


def _as_payload(issue: Any) -> dict[str, Any]:
    if isinstance(issue, dict):
        return issue
    if hasattr(issue, "__dataclass_fields__"):
        return {field.name: getattr(issue, field.name) for field in fields(issue)}
    return {}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    return list(value) if isinstance(value, (list, tuple)) else []


def _is_point(value: Any) -> bool:
    return _point(value) is not None


def _point(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    if x != x or y != y:  # NaN
        return None
    return [x, y]


def _is_box(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 4 and all(isinstance(v, (int, float)) for v in value)


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "ROLE_CONFLICT_PARTY",
    "ROLE_TABLE_ROW",
    "ROLE_UNNUMBERED_SYMBOL",
    "ROLE_WIRE",
    "UNNUMBERED_LABEL",
    "attach_locations",
    "build_locations",
    "derive_locations_from_refs",
]
