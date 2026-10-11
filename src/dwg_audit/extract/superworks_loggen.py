"""SuperWORKS wire-route records read from LD_SYMB2LOGGEN and LD_PARTCONNECTLINE.

Each record names the two ends of one drawn wire as SuperWORKS endpoint identities. The pages are
read from the DXF documents cad_extract already has open (read_page_wire_routes), and resolved
against the SuperWORKS ports (build_wire_route_rows). The rows are written to sw_wire_routes.parquet.

The rows feed production only through superworks_extractor: eligible records (two unconsumed
terminal ends on one audited sheet) become SuperWORKS wire pairs, and the others are reconciled
against existing pairs as evidence. This module itself never creates pairs or issues.

Two record kinds are read:
- LD_SYMB2LOGGEN_DICTIONARY (root dictionary, one XRECORD per wire): CONNECTLINEHANDLE
  names the wire, PART2_n name each end as "||device||pin||seq||side||block||terminal
  handle||category||...", LINENO names one end as "未定义<handle>:<port>".
- LD_PARTCONNECTLINE (extension dictionary of a component INSERT, groups of logical
  pins): each logical pin gives its wire (直线句柄), the far device/pin (对端元件) and
  optionally a cross-page wire label ("未定义<handle>:<port>_<page> <page name>").
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dwg_audit.extract.superworks_semantics import first, normalize, text_ref, xvalues

SCHEMA_VERSION = "sw-wire-route-v1"
LOGGEN_DICTIONARY = "LD_SYMB2LOGGEN_DICTIONARY"
PART_CONNECT_APPID = "LD_PARTCONNECTLINE"

_PART_KEY = re.compile(r"PART2_(\d+)\Z")
_HANDLE = re.compile(r"[0-9A-F]+\Z")
_CROSS_LABEL = re.compile(r"未定义([0-9A-Fa-f]+):([^_\s]+)(?:_(\d+))?(?:\s+(.*))?\Z")
_PCL_START_KEY = "逻辑端号"
_PCL_TERMINAL_CATEGORIES = {"端子", "装置端子"}
# A LOGGEN end whose INSERT SuperWORKS never registered (no LD_SYMB2_SPECIAL, so walk() drops it) can still
# name its pin from the INSERT's own label and TERM_TEXT slot. The identity is "label-slot", the same form
# as an internal component identity. It is an admission candidate, never a SuperWORKS port identity.
SYMB2_STATUS = "resolved_by_symb2_text"
SYMB2_IDENTITY_SOURCE = "symb2_text_slot"
_SYMB2_LABEL_APP = "LD_SYMB2_LABEL"
_SYMB2_SLOT_APP = "LD_SYMB2_TERM_TEXT_"


@dataclass(slots=True)
class PageWireRoutes:
    """Raw routes of one DXF page, before endpoint identities are resolved."""

    file_id: str
    sheet_id: str
    routes: list[dict[str, Any]]
    seconds: float


def _normalized_handle(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text and _HANDLE.fullmatch(text) else ""


def _parse_cross_label(value: str) -> dict[str, Any] | None:
    match = _CROSS_LABEL.fullmatch(str(value or "").strip())
    if not match:
        return None
    return {
        "handle": _normalized_handle(match[1]),
        "port_number": match[2],
        "page_no": match[3] or "",
        "page_name": (match[4] or "").strip(),
    }


def _parse_part2(value: str) -> dict[str, str]:
    """PART2_n: '||device||pin||seq||side||block||terminal||category||...'."""
    segments = str(value or "").split("||")
    def at(index: int) -> str:
        return segments[index].strip() if len(segments) > index else ""
    return {
        "device": at(1), "pin": at(2), "seq": at(3), "side": at(4),
        "block": at(5), "terminal_handle": _normalized_handle(at(6)), "category": at(7),
    }


def _parse_far_device(value: str) -> dict[str, str]:
    """对端元件: '1QD||||4||端子||导线类型:...' -> ['1QD', '', '4', '端子', ...]."""
    segments = str(value or "").split("||")
    def at(index: int) -> str:
        return segments[index].strip() if len(segments) > index else ""
    return {"device": at(0), "pin": at(2), "category": at(3)}


def _loggen_routes(doc: Any, file_id: str, sheet_id: str) -> list[dict[str, Any]]:
    try:
        root = doc.rootdict.get(LOGGEN_DICTIONARY)
    except Exception:
        root = None
    if root is None:
        return []
    routes = []
    for key, record in root.items():
        if record.dxftype() != "XRECORD":
            continue
        values = [str(tag.value) for tag in record.tags if tag.code == 1]
        if len(values) % 2:
            continue
        fields: dict[str, str] = {}
        for name, value in zip(values[::2], values[1::2]):
            fields.setdefault(name.strip().upper(), value)
        reasons = []
        wire_handle = _normalized_handle(fields.get("CONNECTLINEHANDLE"))
        ends = []
        for name in sorted((k for k in fields if _PART_KEY.fullmatch(k)), key=lambda k: int(_PART_KEY.fullmatch(k)[1])):
            part = _parse_part2(fields[name])
            ends.append({"role": name, "port_number": part["pin"], **part})
        if not ends:
            # Dictionary bookkeeping (e.g. FILEINFOR_OF_LAST_CREATED) carries no wire ends.
            continue
        lineno_raw = fields.get("LINENO", "")
        lineno = _parse_cross_label(lineno_raw)
        if lineno is None:
            reasons.append("lineno_unparsed")
        route = {
            "source_kind": "LOGGEN",
            "source_handle": str(record.dxf.handle),
            "owner_handle": str(getattr(record.dxf, "owner", "") or ""),
            "logical_pin": "",
            "wire_handles": [wire_handle] if wire_handle else [],
            "linestyle": fields.get("LINESTYLE", "").strip(),
            "lineno": {"raw": lineno_raw, **(lineno or {})},
            "ends": ends,
            "far_text": None,
            "reasons": reasons,
            "record_key": str(key),
        }
        if not wire_handle:
            reasons.append("wire_handle_missing")
        routes.append(route)
    return routes


def _compare_key(value: Any) -> str:
    return re.sub(r"\s+", "", normalize(str(value or ""))).casefold()


def _symb2_slot_evidence(doc: Any, insert: Any, end: dict[str, Any]) -> dict[str, Any]:
    """Pin identity of a LOGGEN end's INSERT from its own LD_SYMB2_LABEL and LD_SYMB2_TERM_TEXT_<pin>.

    Intrinsic checks only: both texts resolve and reference the INSERT back, the label equals the record
    device, and the slot text equals the record sequence number. Project-level checks (identity unique,
    pin single record, terminal strip row) belong to the admission step in superworks_extractor.
    """
    rejects: list[str] = []
    label_handle = first(insert, _SYMB2_LABEL_APP, 1005)
    label = text_ref(doc, label_handle)
    if not label_handle:
        rejects.append("label_missing")
    elif not label.get("resolved"):
        rejects.append("label_unresolved")
    elif insert.dxf.handle not in xvalues(doc.entitydb.get(label_handle), _SYMB2_LABEL_APP, 1005):
        rejects.append("label_nonreciprocal")
    pin = str(end.get("port_number") or "").strip()
    slot_app = _SYMB2_SLOT_APP + pin
    slot_handle = first(insert, slot_app, 1005) if pin else ""
    slot = text_ref(doc, slot_handle)
    if not pin:
        rejects.append("pin_missing")
    elif not slot_handle:
        rejects.append("slot_missing")
    elif not slot.get("resolved"):
        rejects.append("slot_unresolved")
    elif insert.dxf.handle not in xvalues(doc.entitydb.get(slot_handle), slot_app, 1005):
        rejects.append("slot_nonreciprocal")
    device = str(end.get("device") or "").strip()
    seq = str(end.get("seq") or "").strip()
    label_value = label.get("normalized", "") if label.get("resolved") else ""
    slot_value = slot.get("normalized", "") if slot.get("resolved") else ""
    if not device:
        rejects.append("device_missing")
    elif label_value and _compare_key(label_value) != _compare_key(device):
        rejects.append("label_device_mismatch")
    if not seq:
        rejects.append("seq_missing")
    elif slot_value and _compare_key(slot_value) != _compare_key(seq):
        rejects.append("slot_seq_mismatch")
    if label.get("resolved") and not label_value:
        rejects.append("label_blank")
    if slot.get("resolved") and not slot_value:
        rejects.append("slot_blank")
    identity = f"{label_value}-{slot_value}" if not rejects else None
    return {"identity": identity, "rejects": rejects,
            "label_text": label.get("value", ""), "label_handle": label_handle or None,
            "slot_text": slot.get("value", ""), "slot_handle": slot_handle or None,
            "record_device": device, "record_seq": seq}


def _pcl_entries(values: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for value in values:
        name, separator, text = value.partition(":")
        if not separator:
            continue
        name = name.strip()
        if name == _PCL_START_KEY:
            current = {}
            entries.append(current)
        if current is not None:
            current.setdefault(name, text)
    return entries


def _pcl_routes(doc: Any, file_id: str, sheet_id: str) -> list[dict[str, Any]]:
    routes = []
    for entity in doc.entitydb.values():
        if entity.dxftype() != "INSERT" or not getattr(entity, "has_extension_dict", False):
            continue
        try:
            xdict = entity.get_extension_dict()
            record = xdict.get(PART_CONNECT_APPID)
        except Exception:
            continue
        if record is None or record.dxftype() != "XRECORD":
            continue
        values = [str(tag.value) for tag in record.tags if tag.code == 1]
        owner = str(entity.dxf.handle)
        for entry in _pcl_entries(values):
            logical_pin = entry.get(_PCL_START_KEY, "").strip()
            wire_handle = _normalized_handle(entry.get("直线句柄"))
            far = _parse_far_device(entry.get("对端元件", ""))
            cross = _parse_cross_label(entry.get("线号", ""))
            reasons = []
            if not wire_handle:
                reasons.append("wire_handle_missing")
            if not logical_pin:
                reasons.append("logical_pin_empty")
            if cross is None and entry.get("线号", "").strip():
                reasons.append("wire_label_unparsed")
            routes.append({
                "source_kind": "PCL",
                "source_handle": record.dxf.handle,
                "owner_handle": owner,
                "owner_block": entity.dxf.name,
                "logical_pin": logical_pin,
                "wire_handles": [wire_handle] if wire_handle else [],
                "linestyle": entry.get("导线类型", "").strip(),
                "lineno": {"raw": entry.get("线号", ""), **(cross or {})},
                "ends": [{"role": "LOCAL", "terminal_handle": owner, "port_number": logical_pin,
                          "device": entity.dxf.name, "category": "", "side": "", "block": entity.dxf.name,
                          "terminal_handle_kind": "INSERT"}],
                "far_text": far if far["device"] else None,
                "far_cross": cross,
                "reasons": reasons,
                "record_key": f"{owner}:{logical_pin}",
            })
    return routes


def read_page_wire_routes(doc: Any, *, file_id: str, sheet_id: str) -> PageWireRoutes:
    """Read raw LOGGEN and PART_CONNECT routes from one open ezdxf document."""
    started = time.perf_counter()
    routes = _loggen_routes(doc, file_id, sheet_id) + _pcl_routes(doc, file_id, sheet_id)
    for route in routes:
        route["file_id"] = file_id
        route["sheet_id"] = sheet_id
        route["wire_entity_kinds"] = []
        for handle in route["wire_handles"]:
            entity = doc.entitydb.get(handle)
            route["wire_entity_kinds"].append(entity.dxftype() if entity is not None else None)
        for end in route["ends"]:
            if end.get("terminal_handle"):
                entity = doc.entitydb.get(end["terminal_handle"])
                end["terminal_handle_kind"] = entity.dxftype() if entity is not None else None
                if (route["source_kind"] == "LOGGEN" and entity is not None and entity.dxftype() == "INSERT"
                        and entity.xdata and _SYMB2_LABEL_APP in entity.xdata.data):
                    end["symb2"] = _symb2_slot_evidence(doc, entity, end)
            else:
                end.setdefault("terminal_handle_kind", None)
    return PageWireRoutes(file_id=file_id, sheet_id=sheet_id, routes=routes,
                          seconds=time.perf_counter() - started)


class EndpointIndex:
    """Endpoint identities of SuperWORKS symbols and parts, keyed by (file_id, insert handle)."""

    def __init__(self, superworks: Any, sheet_numbers: dict[str, str] | None = None):
        self.ports: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self.known: set[tuple[str, str]] = set()
        self.handles_by_file: dict[str, set[str]] = defaultdict(set)
        self.sheet_numbers = dict(sheet_numbers or {})
        for symbol in getattr(superworks, "symbols", []) or []:
            self.known.add((symbol.file_id, symbol.insert_handle))
        for port in getattr(superworks, "ports", []) or []:
            key = (port.file_id, port.insert_handle)
            self.known.add(key)
            self.ports[key].append({
                "port_number": str(port.port_number or ""),
                "identity": port.endpoint_identity or None,
                "category": port.category or "",
                "port_id": port.record_id,
                "reasons": list(port.reason_codes or []),
            })
        for part in getattr(superworks, "part_instances", []) or []:
            key = (part.file_id, part.insert_handle)
            self.known.add(key)
            for port in part.ports or []:
                self.ports[key].append({
                    "port_number": str(port.get("port_number", "") or ""),
                    "identity": port.get("endpoint_identity") or None,
                    "category": port.get("category", "") or "",
                    "port_id": port.get("record_id"),
                    "reasons": list(port.get("reason_codes", []) or []),
                })
        for file_id, handle in self.known:
            self.handles_by_file[handle].add(file_id)

    def same_page_end(self, file_id: str, handle: str, pin: str, entity_kind: str | None) -> dict[str, Any]:
        key = (file_id, handle)
        matches = [p for p in self.ports.get(key, []) if p["port_number"] == str(pin).strip()]
        if matches:
            identities = sorted({p["identity"] for p in matches if p["identity"]})
            if len(identities) == 1:
                return {"status": "resolved", "identity": identities[0], "identity_source": "sw_port",
                        "port_ids": sorted(p["port_id"] for p in matches if p["port_id"]),
                        "category": matches[0]["category"]}
            if not identities:
                reasons = sorted({r for p in matches for r in p["reasons"]})
                return {"status": "no_identity", "identity": None, "identity_source": None,
                        "port_ids": sorted(p["port_id"] for p in matches if p["port_id"]),
                        "category": matches[0]["category"], "detail": ",".join(reasons)}
            return {"status": "ambiguous_identity", "identity": None, "identity_source": None,
                    "port_ids": [], "category": matches[0]["category"], "detail": ",".join(identities)}
        if key in self.known:
            return {"status": "port_number_absent", "identity": None, "identity_source": None,
                    "port_ids": [], "category": "", "detail": str(pin)}
        if entity_kind == "INSERT":
            return {"status": "insert_not_sw", "identity": None, "identity_source": None,
                    "port_ids": [], "category": "", "detail": ""}
        if entity_kind is None:
            return {"status": "handle_missing", "identity": None, "identity_source": None,
                    "port_ids": [], "category": "", "detail": ""}
        return {"status": "not_insert", "identity": None, "identity_source": None,
                "port_ids": [], "category": "", "detail": entity_kind}

    def cross_page_end(self, handle: str, port: str, page_no: str) -> dict[str, Any]:
        files = sorted(self.handles_by_file.get(handle, ()))
        if not files:
            return {"status": "xpage_target_not_sw", "identity": None, "identity_source": None,
                    "port_ids": [], "file_id": None, "category": ""}
        if len(files) > 1 and page_no:
            wanted = page_no.lstrip("0")
            narrowed = [f for f in files if self.sheet_numbers.get(f, "").lstrip("0") == wanted]
            if narrowed:
                files = narrowed
        if len(files) != 1:
            return {"status": "xpage_ambiguous", "identity": None, "identity_source": None,
                    "port_ids": [], "file_id": None, "category": ""}
        file_id = files[0]
        result = self.same_page_end(file_id, handle, port, "INSERT")
        result["file_id"] = file_id
        return result


def _text_identity(device: str, pin: str, category: str) -> str | None:
    if not device or not pin:
        return None
    if category in _PCL_TERMINAL_CATEGORIES:
        return device + pin
    return device + "-" + pin


def _with_symb2_identity(result: dict[str, Any], end: dict[str, Any]) -> dict[str, Any]:
    """An INSERT that SuperWORKS never registered takes its label-slot identity when the intrinsic checks pass."""
    evidence = end.get("symb2")
    if result.get("status") != "insert_not_sw" or not evidence:
        return result
    if evidence.get("rejects") or not evidence.get("identity"):
        return {**result, "detail": "symb2:" + ",".join(evidence.get("rejects") or ["identity_missing"])}
    return {"status": SYMB2_STATUS, "identity": evidence["identity"], "identity_source": SYMB2_IDENTITY_SOURCE,
            "port_ids": [], "category": "", "detail": ""}


def resolve_wire_routes(pages: list[PageWireRoutes], index: EndpointIndex) -> list[dict[str, Any]]:
    """Attach endpoint identities to raw routes. Output rows are JSON-friendly."""
    rows = []
    for page in pages:
        for route in page.routes:
            ends_out = []
            reasons = list(route["reasons"])
            for end in route["ends"]:
                if route["source_kind"] == "PCL" and end["role"] == "LOCAL":
                    result = index.same_page_end(page.file_id, end["terminal_handle"], end["port_number"], "INSERT")
                    result["file_id"] = page.file_id
                    ends_out.append({**end, **result, "end_index": len(ends_out)})
                    continue
                result = _with_symb2_identity(index.same_page_end(page.file_id, end["terminal_handle"],
                                                                 end["port_number"], end.get("terminal_handle_kind")), end)
                result["file_id"] = page.file_id
                ends_out.append({**end, **result, "end_index": len(ends_out)})
            far_text = route.get("far_text")
            cross = route.get("far_cross")
            if route["source_kind"] == "PCL":
                far_identity = _text_identity(far_text["device"], far_text["pin"], far_text["category"]) if far_text else None
                far = {"role": "FAR", "terminal_handle": cross.get("handle") if cross else None,
                       "port_number": (cross or {}).get("port_number") or (far_text or {}).get("pin", ""),
                       "device": (far_text or {}).get("device", ""), "category": (far_text or {}).get("category", ""),
                       "side": "", "block": "", "terminal_handle_kind": None,
                       "far_text_identity": far_identity}
                if cross and cross.get("handle"):
                    result = index.cross_page_end(cross["handle"], cross["port_number"], cross.get("page_no", ""))
                    far.update({k: v for k, v in result.items() if k != "category"}, far_source="cross_page")
                    far["category"] = result.get("category") or far["category"]
                    far["xpage_page_name"] = cross.get("page_name", "")
                    if result["status"] != "resolved" and far_identity:
                        far.update(identity=far_identity, identity_source="text", status="resolved_by_text",
                                   detail=result["status"])
                elif far_identity:
                    far.update(identity=far_identity, identity_source="text", status="resolved_by_text",
                               far_source="text_only", port_ids=[])
                else:
                    far.update(identity=None, identity_source=None, status="no_far_end", far_source=None, port_ids=[])
                ends_out.append({**far, "end_index": len(ends_out)})
            lineno = route.get("lineno") or {}
            lineno_match = None
            if lineno.get("handle") and route["source_kind"] == "LOGGEN":
                lineno_match = next((e["end_index"] for e in ends_out
                                     if e.get("terminal_handle") == lineno["handle"]
                                     and str(e.get("port_number")) == str(lineno.get("port_number"))), None)
            resolved = [e for e in ends_out if e.get("status") in ("resolved", "resolved_by_text", SYMB2_STATUS)]
            for end in ends_out:
                if end.get("status") not in ("resolved", "resolved_by_text"):
                    reasons.append(f"end_{end['end_index']}_{end.get('status')}")
            rows.append({
                "schema_version": SCHEMA_VERSION,
                "record_id": f"SWWR:{page.file_id}:{route['source_kind']}:{route['record_key']}",
                "sheet_id": page.sheet_id,
                "file_id": page.file_id,
                "source_kind": route["source_kind"],
                "source_handle": route["source_handle"],
                "owner_handle": route["owner_handle"],
                "logical_pin": route["logical_pin"],
                "wire_handle": route["wire_handles"][0] if route["wire_handles"] else None,
                "wire_entity_kind": route["wire_entity_kinds"][0] if route["wire_entity_kinds"] else None,
                "linestyle": route["linestyle"],
                "end_count": len(ends_out),
                "resolved_end_count": len(resolved),
                "both_ends_resolved": len(ends_out) >= 2 and len(resolved) == len(ends_out),
                "lineno_raw": lineno.get("raw", ""),
                "lineno_end_index": lineno_match,
                "ends_json": _json(ends_out),
                "reason_codes_json": _json(sorted(set(reasons))),
                # Filled by the production admission step (superworks_extractor); None = not decided.
                "admission_status": None,
                "admission_reason": None,
                "admitted_pair_id": None,
            })
    return rows


def _json(value: Any) -> str:
    import json
    return json.dumps(value, ensure_ascii=False, default=str)


def build_wire_route_rows(pages: list[PageWireRoutes], superworks: Any,
                          sheet_numbers: dict[str, str] | None = None,
                          page_failures: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Resolve already-read pages against superworks. No DXF is opened here."""
    started = time.perf_counter()
    index = EndpointIndex(superworks, sheet_numbers)
    rows = resolve_wire_routes(pages, index)
    stats = {
        "schema_version": SCHEMA_VERSION,
        "page_count": len(pages) + len(page_failures or {}),
        "page_failures": dict(page_failures or {}),
        "row_count": len(rows),
        "read_seconds": sum(page.seconds for page in pages),
        "resolve_seconds": time.perf_counter() - started,
    }
    return rows, stats


def collect_wire_route_rows(sources: list[tuple[str, str, Path]], superworks: Any,
                            sheet_numbers: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read every page (sources: (file_id, sheet_id, dxf_path)) and resolve against superworks.

    Standalone entry for tests and tools: it opens each DXF once. The pipeline does not use it;
    cad_extract reads the routes from the document it already has open.
    Failures are counted per page and never raised.
    """
    import ezdxf

    pages: list[PageWireRoutes] = []
    failures: dict[str, str] = {}
    for file_id, sheet_id, path in sources:
        try:
            doc = ezdxf.readfile(str(path))
            pages.append(read_page_wire_routes(doc, file_id=file_id, sheet_id=sheet_id))
        except Exception as exc:  # diagnostic only: a bad page must not stop the pipeline
            failures[file_id] = type(exc).__name__
    return build_wire_route_rows(pages, superworks, sheet_numbers, failures)


def write_wire_route_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    import pandas as pd

    frame = pd.DataFrame(rows, columns=list(_ROW_COLUMNS))
    frame.to_parquet(path, index=False)


_ROW_COLUMNS = (
    "schema_version", "record_id", "sheet_id", "file_id", "source_kind", "source_handle",
    "owner_handle", "logical_pin", "wire_handle", "wire_entity_kind", "linestyle", "end_count",
    "resolved_end_count", "both_ends_resolved", "lineno_raw", "lineno_end_index",
    "ends_json", "reason_codes_json", "admission_status", "admission_reason", "admitted_pair_id",
)
