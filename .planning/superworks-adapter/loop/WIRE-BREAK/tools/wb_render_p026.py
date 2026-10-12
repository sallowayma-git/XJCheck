"""Before/after line-group renders for p026 S0008 (read-only; writes PNG only).

Reuses loop/GAP/tools/gap_render.py (DXF frontend + overlays). Each line group is drawn in its own colour; SW ports
are squares; the 5n/5C/5KD terminals and unregistered SYMB2 TERMPOINTs are drawn as marks.
"""
import glob, importlib.util, json, sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
spec = importlib.util.spec_from_file_location("gap_render", str(ROOT / ".planning/superworks-adapter/loop/GAP/tools/gap_render.py"))
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)

base_f = glob.glob(str(ROOT / ".tmp/superworks_round22_full/p026/*/findings"))[0]
new_f = glob.glob(str(ROOT / ".tmp/loop_wbreak/p026/*/findings"))[0]
dxf = sorted(glob.glob(str(ROOT / ".tmp/superworks_round22_full/p026/cache/converted_dxf/F0008_*.dxf")))[0]
out = ROOT / ".planning/superworks-adapter/loop/WIRE-BREAK/png"
out.mkdir(parents=True, exist_ok=True)
COLOURS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b", "#e377c2", "#17becf", "#bcbd22"]


def groups(findings):
    lg = pd.read_parquet(findings + "/line_groups.parquet")
    lg = lg[lg.sheet_id == "S0008"]
    segs = []
    for i, r in enumerate(lg.itertuples()):
        if not (150 <= r.start_y <= 250):
            continue
        segs.append((r.start_x, r.start_y, r.end_x, r.end_y, COLOURS[i % len(COLOURS)], 2.0))
    return segs


def ports():
    pt = pd.read_parquet(base_f + "/sw_ports.parquet")
    pt = pt[(pt.sheet_id == "S0008") & pt.start_y.between(150, 250)]
    return [((r.start_x + r.end_x) / 2, r.start_y, "#d62728") for r in pt.itertuples()]


def unreg():
    u = pd.read_parquet(base_f + "/sw_unregistered_symb2.parquet")
    u = u[u.sheet_id == "S0008"]
    pts = []
    for r in u.itertuples():
        for t in json.loads(r.termpoints):
            if 150 <= t["a"][1] <= 250:
                pts.append(((t["a"][0] + t["b"][0]) / 2, t["a"][1], "#2ca02c"))
    return pts


def panel(title, findings, window):
    pts = ports() + unreg()
    return gr.Panel([title], dxf, window, segs=groups(findings), pts=pts)


full = (120.0, 145.0, 275.0, 252.0)
zoom_1431 = (196.0, 186.0, 266.0, 200.0)
zoom_1521 = (196.0, 176.0, 266.0, 190.0)
gr.render(out / "WB_p026_S0008_before_after.png",
          ["p026 · 08 跳闸出口回路 (S0008) · line groups, rows y 150-250",
           "left: round22 (before, HEAD f068c88) · right: WIRE-BREAK (after)",
           "red squares: SW ports · green: unregistered SYMB2 TERMPOINTs · colours: one per line group"],
          [panel("BEFORE (round22)", base_f, full), panel("AFTER (WIRE-BREAK)", new_f, full)], cols=2)
gr.render(out / "WB_p026_S0008_zoom_1431_1521.png",
          ["p026 · S0008 zoom: row y=192.5 (5n1431 terminal, 5C3LP2 symbol, 5KD4) and row y=182.5 (5n1521)"],
          [panel("BEFORE y=192.5", base_f, zoom_1431), panel("AFTER y=192.5", new_f, zoom_1431),
           panel("BEFORE y=182.5", base_f, zoom_1521), panel("AFTER y=182.5", new_f, zoom_1521)], cols=2)
print("ok")
