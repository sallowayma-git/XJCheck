"""Read one project's findings (round outputs) into the plain records used by audit/superworks_cross_page.py.

Read-only. Also returns the coordinates the renderer needs (strip row and destination text positions, port
positions), which the production module does not use.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")


def _json(value):
    if value is None or (isinstance(value, float) and value != value):
        return []
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return []


def findings_dir(run_dir: Path, project_id: str) -> Path:
    return next(p for p in (Path(run_dir) / project_id).glob("*/findings") if p.is_dir())


def load(findings: Path):
    pages_df = pd.read_parquet(findings / "pages.parquet", columns=["sheet_id", "file_id", "sheet_no", "filename", "page_type"])
    pages = [{"file_id": r.file_id, "sheet_no": r.sheet_no} for r in pages_df.itertuples()]
    page_info = {r.file_id: {"sheet_no": str(r.sheet_no), "filename": r.filename, "page_type": r.page_type,
                             "sheet_id": r.sheet_id} for r in pages_df.itertuples()}
    ports_df = pd.read_parquet(findings / "sw_ports.parquet", columns=[
        "record_id", "file_id", "sheet_id", "insert_handle", "port_number", "endpoint_identity", "category",
        "wire_contacts", "start_x", "start_y", "end_x", "end_y"])
    ports, port_xy = [], {}
    for r in ports_df.itertuples():
        contacts = _json(r.wire_contacts)
        ports.append({"record_id": r.record_id, "file_id": r.file_id, "sheet_id": r.sheet_id,
                      "insert_handle": r.insert_handle, "port_number": r.port_number,
                      "endpoint_identity": r.endpoint_identity, "category": r.category,
                      "has_wire_contact": bool(contacts)})
        port_xy[r.record_id] = (float(r.start_x), float(r.start_y), contacts)
    pairs_df = pd.read_parquet(findings / "pairs.parquet", columns=[
        "pair_id", "status", "sheet_id", "left_value", "right_value", "left_text_id", "right_text_id", "evidence"])
    pairs = []
    for r in pairs_df.itertuples():
        ev = r.evidence if isinstance(r.evidence, dict) else (_json(r.evidence) if isinstance(r.evidence, str) else {})
        sw = (ev or {}).get("superworks") or {}
        pairs.append({"pair_id": r.pair_id, "status": r.status, "sheet_id": r.sheet_id,
                      "left_value": r.left_value, "right_value": r.right_value,
                      "left_text_id": r.left_text_id, "right_text_id": r.right_text_id,
                      "left_port_ids": list((sw.get("left") or {}).get("port_ids") or []),
                      "right_port_ids": list((sw.get("right") or {}).get("port_ids") or [])})
    strips_df = pd.read_parquet(findings / "sw_strip_rows.parquet", columns=[
        "record_id", "sheet_id", "file_id", "row_handle", "endpoint_identity", "row", "connections", "potentials",
        "cross_page_refs"])
    strips, strip_xy = [], {}
    for r in strips_df.itertuples():
        connections = _json(r.connections)
        potentials = _json(r.potentials)
        strips.append({"record_id": r.record_id, "sheet_id": r.sheet_id, "file_id": r.file_id,
                       "endpoint_identity": r.endpoint_identity, "connections": connections,
                       "cross_page_refs": _json(r.cross_page_refs)})
        row = _json(r.row)
        strip_xy[r.record_id] = {
            "row": (row.get("x"), row.get("y")) if isinstance(row, dict) else (None, None),
            "connections": [(c.get("x"), c.get("y")) for c in connections],
            "potentials": [(p.get("x"), p.get("y")) for p in potentials],
        }
    return {"strips": strips, "ports": ports, "pairs": pairs, "pages": pages, "page_info": page_info,
            "port_xy": port_xy, "strip_xy": strip_xy}
