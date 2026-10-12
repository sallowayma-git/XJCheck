"""Stratified sample of pairs discarded by the frame rule (wire_walk_internal_frame), rendered for visual check.

usage: wb_sample_frame.py RUN_ROOT OUT_PREFIX N SEED
Each panel: the sheet's model lines and block leads in a window around the pair's line group (after), the pair's
group in orange, SW ports red, unregistered TERMPOINTs green. Writes OUT_PREFIX_01.png ... (6 panels each).
"""
import glob
import importlib.util
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
spec = importlib.util.spec_from_file_location("gap_render", str(ROOT / ".planning/superworks-adapter/loop/GAP/tools/gap_render.py"))
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)

run_root, out_prefix, n, seed = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
rows = []
for f in sorted(run_root.glob("p*/*/findings/pairs.parquet")):
    pid = f.parts[-4]
    p = pd.read_parquet(f)
    hit = p[p.rationale.astype(str).str.contains("wire_walk_internal_frame")]
    for r in hit.itertuples():
        rows.append({"pid": pid, "sheet": r.sheet_id, "pair_id": r.pair_id, "group": r.line_group_id,
                     "left": "" if r.left_value is None or (isinstance(r.left_value, float)) else str(r.left_value),
                     "right": "" if r.right_value is None or (isinstance(r.right_value, float)) else str(r.right_value),
                     "kind": r.pair_kind})
print("frame-rule discards", len(rows))
rng = random.Random(seed)
by_pid = {}
for r in rows:
    by_pid.setdefault(r["pid"], []).append(r)
chosen = []
pids = sorted(by_pid)
while len(chosen) < min(n, len(rows)) and any(by_pid.values()):
    for pid in pids:
        if by_pid[pid] and len(chosen) < n:
            chosen.append(by_pid[pid].pop(rng.randrange(len(by_pid[pid]))))
json.dump(chosen, open(ROOT / ".tmp" / "wb_frame_sample.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
COL = ["#1f77b4", "#2ca02c", "#9467bd", "#8c564b", "#17becf"]
for k in range(0, len(chosen), 6):
    panels = []
    for r in chosen[k:k + 6]:
        f = next(run_root.glob(f"{r['pid']}/*/findings"))
        lg = pd.read_parquet(f / "line_groups.parquet")
        g = lg[lg.line_group_id == r["group"]]
        if g.empty:
            continue
        g = g.iloc[0]
        x0, x1 = min(g.start_x, g.end_x), max(g.start_x, g.end_x)
        y0, y1 = min(g.start_y, g.end_y), max(g.start_y, g.end_y)
        win = (x0 - 18, y0 - 18, x1 + 18, y1 + 18)
        ln = pd.read_parquet(f / "lines.parquet")
        ln = ln[ln.sheet_id == r["sheet"]]
        segs = []
        for i, s in enumerate(ln.itertuples()):
            if max(s.end_x, s.start_x) < win[0] or min(s.end_x, s.start_x) > win[2]:
                continue
            if max(s.end_y, s.start_y) < win[1] or min(s.end_y, s.start_y) > win[3]:
                continue
            segs.append((s.start_x, s.start_y, s.end_x, s.end_y, "#555555", 1.0))
        segs.append((g.start_x, g.start_y, g.end_x, g.end_y, "#ff7f0e", 3.0))
        ports = pd.read_parquet(f / "sw_ports.parquet")
        ports = ports[ports.sheet_id == r["sheet"]]
        pts = [((p.start_x + p.end_x) / 2, p.start_y, "#d62728") for p in ports.itertuples()
               if win[0] <= p.start_x <= win[2] and win[1] <= p.start_y <= win[3]]
        u = pd.read_parquet(f / "sw_unregistered_symb2.parquet")
        for ur in u[u.sheet_id == r["sheet"]].itertuples():
            for t in json.loads(ur.termpoints):
                mx = (t["a"][0] + t["b"][0]) / 2
                if win[0] <= mx <= win[2] and win[1] <= t["a"][1] <= win[3]:
                    pts.append((mx, t["a"][1], "#2ca02c"))
        fid = pd.read_parquet(f / "pages.parquet").query("sheet_id == @r['sheet']").file_id.iloc[0]
        dxf = sorted(glob.glob(str(ROOT / ".tmp/superworks_round22_full" / r["pid"] / "cache/converted_dxf" / f"{fid}_*.dxf")))[0]
        title = [f"{r['pid']} {r['sheet']} {r['left']} <-> {r['right']}", f"{r['kind']} · discarded by frame rule",
                 f"group {r['group']}"]
        panels.append(gr.Panel(title, dxf, win, segs=segs, pts=pts))
    if panels:
        gr.render(ROOT / ".planning/superworks-adapter/loop/WIRE-BREAK/png" / f"{out_prefix}_{k // 6 + 1:02d}.png",
                  [f"frame-rule discards: sample of {len(chosen)} (seed {seed}); orange: discarded wire group",
                   "grey: model lines; red: SW ports; green: unregistered TERMPOINTs"], panels, cols=3)
print("rendered", len(chosen))
