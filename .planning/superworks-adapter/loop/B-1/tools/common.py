"""Shared helpers for the B-1 read-only audit (no writes outside loop/B-1)."""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import pandas as pd
import ezdxf, ezdxf.bbox  # noqa

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
ROUND = ROOT / ".tmp" / "superworks_round12_full"
MANIFEST = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
OUT = ROOT / ".planning/superworks-adapter/loop/B-1"

TARGETS = [
    # proj, run, pair_id, file_id, sheet_id, short name
    ("p062", "21000", "PC0019", "F0012", "S0012", "p062_PC0019_S0012"),
    ("p062", "21000", "PC0125", "F0013", "S0013", "p062_PC0125_S0013"),
    ("p071", "30000", "PC0053", "F0011", "S0011", "p071_PC0053_S0011"),
    ("p075", "8000_9000_-", "PC0232", "F0014", "S0014", "p075_PC0232_S0014"),
    ("p075", "8000_9000_-", "PC0440", "F0015", "S0015", "p075_PC0440_S0015"),
]


def findings(proj, run):
    return ROUND / proj / run / "findings"


def table(proj, run, name):
    return pd.read_parquet(findings(proj, run) / f"{name}.parquet")


def dxf_path(proj, file_id):
    for p in MANIFEST["projects"]:
        if p["project_id"] == proj:
            for f in p["files"]:
                if f["file_id"] == file_id:
                    return f["dxf_path"]
    raise KeyError((proj, file_id))


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def f(v):
    try:
        x = float(v)
        return None if x != x else x
    except Exception:
        return None


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if hasattr(o, "tolist"):
        return jsonable(o.tolist())
    if isinstance(o, float) and o != o:
        return None
    return o
