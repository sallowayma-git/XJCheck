"""Before/after line-group render for one region of one project page (read-only; writes PNG only).

usage: wb_render_region.py PROJECT SHEET X0 Y0 X1 Y1 OUT_PNG [NEW_ROOT]
BEFORE = .tmp/superworks_round22_full, AFTER = NEW_ROOT (default .tmp/superworks_round23_full).
Line groups are drawn per group in its own colour; SW ports are red squares; SYMB2 TERMPOINTs green.
"""
import glob, importlib.util, json, sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
spec = importlib.util.spec_from_file_location("gap_render", str(ROOT / ".planning/superworks-adapter/loop/GAP/tools/gap_render.py"))
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)

pid, sheet = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
out = Path(sys.argv[7])
new_root = ROOT / (sys.argv[8] if len(sys.argv) > 8 else ".tmp/superworks_round23_full")
base_f = glob.glob(str(ROOT / ".tmp/superworks_round22_full" / pid / "*/findings"))[0]
new_f = glob.glob(str(new_root / pid / "*/findings"))[0]
file_id = pd.read_parquet(base_f + "/sw_ports.parquet").query("sheet_id == @sheet").file_id.iloc[0]
dxf = sorted(glob.glob(str(ROOT / ".tmp/superworks_round22_full" / pid / "cache/converted_dxf" / f"{file_id}_*.dxf")))[0]
COLOURS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b", "#e377c2", "#17becf", "#bcbd22"]
window = (x0, y0, x1, y1)


def segs(findings):
    lg = pd.read_parquet(findings + "/line_groups.parquet")
    lg = lg[lg.sheet_id == sheet]
    out_ = []
    for i, r in enumerate(lg.itertuples()):
        if r.end_x < x0 or r.start_x > x1 or r.start_y < y0 or r.start_y > y1:
            continue
        out_.append((r.start_x, r.start_y, r.end_x, r.end_y, COLOURS[i % len(COLOURS)], 2.0))
    return out_


pt = pd.read_parquet(base_f + "/sw_ports.parquet")
pt = pt[pt.sheet_id == sheet]
pts = [((a.start_x + a.end_x) / 2, a.start_y, "#d62728") for a in pt.itertuples()
       if x0 <= a.start_x <= x1 and y0 <= a.start_y <= y1]
u = pd.read_parquet(base_f + "/sw_unregistered_symb2.parquet")
u = u[u.sheet_id == sheet]
for r in u.itertuples():
    for t in json.loads(r.termpoints):
        mx, my = (t["a"][0] + t["b"][0]) / 2, t["a"][1]
        if x0 <= mx <= x1 and y0 <= my <= y1:
            pts.append((mx, my, "#2ca02c"))
gr.render(out, [f"{pid} {sheet} window x {x0}-{x1}, y {y0}-{y1}", "left: before (round22) · right: after (round23)"],
          [gr.Panel(["BEFORE"], dxf, window, segs=segs(base_f), pts=pts),
           gr.Panel(["AFTER"], dxf, window, segs=segs(new_f), pts=pts)], cols=2)
print("ok", out)
