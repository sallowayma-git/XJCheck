"""Load round17-style findings for XPAGE-2 analysis (read-only). Adds strip-header grouping to xpage_io.load."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / ".planning/superworks-adapter/loop/XPAGE/tools"))
import xpage_io  # noqa: E402


def _j(value, default):
    if value is None or (isinstance(value, float) and value != value):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def load_project(run_dir: Path, project_id: str) -> dict:
    findings = xpage_io.findings_dir(run_dir, project_id)
    data = xpage_io.load(findings)
    strips_df = pd.read_parquet(findings / "sw_strip_rows.parquet", columns=[
        "record_id", "header", "row", "endpoint_identity", "connections", "potentials", "cross_page_refs",
        "validation", "dzlx", "dxlx", "symb_bwrite"])
    info = {}
    for r in strips_df.itertuples():
        header = _j(r.header, {})
        info[r.record_id] = {
            "header_handle": header.get("handle"), "header_value": header.get("normalized") or header.get("value"),
            "row_number": _j(r.row, {}).get("normalized"), "strip_name": (_j(r.validation, {}) or {}).get("strip_name"),
            "dzlx": r.dzlx, "dxlx": r.dxlx, "connections_full": _j(r.connections, []),
            "row_xy": (_j(r.row, {}).get("x"), _j(r.row, {}).get("y")),
        }
    data["strip_info"] = info
    data["findings"] = findings
    return data
