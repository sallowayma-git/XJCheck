"""Stratified DXF renders for GAP triage classes (read-only inputs; writes PNG under GAP-TRIAGE/png and a sample manifest).

Each PNG holds up to five panels (one sampled gap per panel) for one triage group. Overlay colours:
  blue segment       = the observed unresolved wire segment (R-RECOGNITION-GAP coords)
  green square       = SuperWORKS port contact of the device terminal side (DEV)
  orange square      = SuperWORKS port contact of the other side
  magenta diamond    = V2 terminal geometry binding (terminal_candidates physical_endpoint_evidence) within 1.0
  red cross          = unregistered SYMB2 termpoint (block pin with no SuperWORKS port)
  grey lines         = other model-space lines of the same sheet inside the window
Run: PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 python -I triage_render.py
"""
from __future__ import annotations

import glob
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
LOOP = REPO / ".planning/superworks-adapter/loop/GAP-TRIAGE"
CUR = REPO / ".tmp/engine_coordination_full_acceptance/current"
WORK = REPO / ".tmp/gap_triage_work"
MANIFEST = REPO / ".planning/superworks-adapter/corpus_manifest.json"

_spec = importlib.util.spec_from_file_location("gap_render", str(REPO / ".planning/superworks-adapter/loop/GAP/tools/gap_render.py"))
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)

SEED = 20261015
PER_GROUP = 5
PAD = 9.0


def dxf_map():
    man = json.load(open(MANIFEST, encoding="utf-8"))
    out = {}
    for p in man["projects"]:
        for f in p["files"]:
            out[(p["project_id"], f["file_id"])] = f["dxf_path"]
    return out


GROUPS = {
    "A1_device_internal_excluded": lambda d: (d.cls == "A") & d["sub"].str.endswith("_excluded"),
    "A2_device_internal_not_excluded": lambda d: (d.cls == "A") & d["sub"].str.endswith("_not_excluded"),
    "B_v1_closed": lambda d: d.cls == "B",
    "C_v2_redundant": lambda d: d["sub"] == "C_v2_redundant",
    "C_v2_new": lambda d: d["sub"] == "C_v2_new",
    "D_xpage": lambda d: d.cls == "D",
    "X_element_only": lambda d: d.cls == "X",
    "E_rail_T": lambda d: d["sub"] == "E_rail_T",
    "E_bus_T": lambda d: d["sub"] == "E_bus_T",
    "E_reg_element_no_port": lambda d: d["sub"] == "E_reg_element_no_port",
    "E_port_both_ends": lambda d: d["sub"] == "E_port_both_ends",
    "E_unreg_pin": lambda d: d["sub"] == "E_unreg_pin",
    "E_unreg_element": lambda d: d["sub"] == "E_unreg_element",
    "E_open": lambda d: d["sub"] == "E_open",
    "E_text_only": lambda d: d["sub"] == "E_text_only",
}


def parse_xy(s):
    if not s:
        return None
    v = json.loads(s)
    return (float(v[0]), float(v[1])) if v and v[0] is not None else None


def load_project_aux(pid):
    fdir = glob.glob(str(CUR / pid / "*" / "findings"))[0]
    lines = pd.read_parquet(os.path.join(fdir, "lines.parquet"), columns=["file_id", "sheet_id", "start_x", "start_y", "end_x", "end_y"])
    ucp = pd.read_parquet(os.path.join(fdir, "sw_unregistered_symb2.parquet"))
    tc = pd.read_parquet(os.path.join(fdir, "terminal_candidates.parquet"), columns=["file_id", "sheet_id", "physical_endpoint_evidence"])
    v2 = []
    for r in tc.itertuples(index=False):
        pe = json.loads(r.physical_endpoint_evidence) if isinstance(r.physical_endpoint_evidence, str) and len(r.physical_endpoint_evidence) > 4 else {}
        if pe.get("position"):
            v2.append((r.file_id, r.sheet_id, float(pe["position"][0]), float(pe["position"][1])))
    unreg = []
    for r in ucp.itertuples(index=False):
        for tp in json.loads(r.termpoints or "[]"):
            for key in ("a", "b"):
                if tp.get(key):
                    unreg.append((r.file_id, r.sheet_id, float(tp[key][0]), float(tp[key][1])))
    return lines, v2, unreg


def build_panel(row, dxf, aux, lines_df, v2, unreg):
    coords = json.loads(row["coords"]) if row["coords"] else []
    if len(coords) != 4:
        return None
    p1, p2 = (coords[0], coords[1]), (coords[2], coords[3])
    lc = parse_xy(row["left_contact_xy"])
    rc = parse_xy(row["right_contact_xy"])
    fs = (row["file_id"], row["sheet_id"])
    pts_all = [p1, p2] + [q for q in (lc, rc) if q]
    window = gr.window_around(pts_all, pad=PAD, min_size=24.0)
    x0, y0, x1, y1 = window
    segs = [(p1[0], p1[1], p2[0], p2[1], "blue", 2.4)]
    # sheet lines in window, grey
    sub = lines_df[(lines_df.file_id == fs[0]) & (lines_df.sheet_id == fs[1])]
    cnt = 0
    for r in sub.itertuples(index=False):
        if max(r.start_x, r.end_x) < x0 or min(r.start_x, r.end_x) > x1 or max(r.start_y, r.end_y) < y0 or min(r.start_y, r.end_y) > y1:
            continue
        segs.append((r.start_x, r.start_y, r.end_x, r.end_y, "grey", 0.6))
        cnt += 1
        if cnt > 400:
            break
    pts = []
    if lc:
        pts.append((lc[0], lc[1], "green" if row["device_side"] == "L" else "orange"))
    if rc:
        pts.append((rc[0], rc[1], "green" if row["device_side"] == "R" else "orange"))
    for (f, s, x, y) in v2:
        if f == fs[0] and s == fs[1] and x0 <= x <= x1 and y0 <= y <= y1:
            pts.append((x, y, "magenta"))
    for (f, s, x, y) in unreg:
        if f == fs[0] and s == fs[1] and x0 <= x <= x1 and y0 <= y <= y1:
            pts.append((x, y, "red"))
    title = [
        f"{row['_group']} | {row['project']} {row['sheet_no']} {row['file_id']}/{row['sheet_id']} | cls {row['cls']} {row['sub']}",
        f"L {row['left_cat']} id={row['left_identity'] or '-'} port={row['left_port_number'] or '-'} | R {row['right_cat']} id={row['right_identity'] or '-'} port={row['right_port_number'] or '-'}",
        f"verdict={row['dev_verdict']} other={row['other_kind']} | V1 cov nd={row['cur_cov_nd']} val={row['cur_cov_val']} | V2 val={row['v2_end_value'] or '-'} | xpage={row['left_xpage_cover'] or row['right_xpage_cover'] or '-'}",
        f"res={row['res_reasons'] or '-'}",
    ]
    return gr.Panel(title, dxf, window, segs=segs, pts=pts)


def main():
    df = pd.read_pickle(WORK / "classified.pkl")
    df = df.reset_index(drop=True)
    dmap = dxf_map()
    rng = np.random.default_rng(SEED)
    manifest_rows = []
    png_dir = LOOP / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    cache_aux = {}
    panels_by_group = {}
    for gname, pred in GROUPS.items():
        sub = df[pred(df)].copy()
        if len(sub) == 0:
            print("empty", gname)
            continue
        idx = rng.choice(len(sub), size=min(PER_GROUP, len(sub)), replace=False)
        pick = sub.iloc[sorted(idx)]
        panels = []
        for _, row in pick.iterrows():
            row = row.copy()
            row["_group"] = gname
            pid = row["project"]
            if pid not in cache_aux:
                cache_aux.clear()
                cache_aux[pid] = load_project_aux(pid)
            lines_df, v2, unreg = cache_aux[pid]
            dxf = dmap.get((pid, row["file_id"]))
            pnl = build_panel(row, dxf, None, lines_df, v2, unreg)
            if pnl is None:
                continue
            panels.append(pnl)
            manifest_rows.append({"group": gname, "issue_id": row["issue_id"], "project": pid, "file_id": row["file_id"],
                                  "sheet_id": row["sheet_id"], "cls": row["cls"], "sub": row["sub"],
                                  "coords": row["coords"], "left_identity": row["left_identity"],
                                  "right_identity": row["right_identity"], "dev_verdict": row["dev_verdict"]})
        panels_by_group[gname] = panels
        out = png_dir / f"{gname}.png"
        header = [f"GAP-TRIAGE sample: {gname} (n in group {len(sub)}, drawn {len(panels)})",
                  "blue=gap segment, green=device port, orange=other port, magenta=V2 binding, red=unregistered pin, grey=sheet lines"]
        gr.render(out, header, panels, cols=3)
        print("rendered", gname, len(panels), flush=True)
    json.dump(manifest_rows, open(WORK / "render_samples.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("samples", len(manifest_rows))


if __name__ == "__main__":
    main()
