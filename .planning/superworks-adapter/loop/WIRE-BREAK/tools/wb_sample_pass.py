"""Stratified sample of new or newly-pass wire pairs, rendered as composite before/after panels (read-only; PNG only).

Stratum A: pairs whose content key was in base with another status (5 in the 10-project pool; all taken).
Stratum B: pairs absent in base (43); spread over projects with random.Random(20261011).
Each panel shows the AFTER line groups of the pair's sheet within a window around the pair's group, the SW ports
(red squares) and the unregistered TERMPOINTs (green), with the pair's group drawn in bold orange.
"""
import glob, importlib.util, json, random
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
spec = importlib.util.spec_from_file_location("gap_render", str(ROOT / ".planning/superworks-adapter/loop/GAP/tools/gap_render.py"))
gr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gr)
pool = json.load(open(ROOT / ".tmp/wb_pass_pool.json", encoding="utf-8"))
A = [r for r in pool if r["base_status"] != "none"]
B = [r for r in pool if r["base_status"] == "none"]
rng = random.Random(20261011)
by_pid = {}
for r in B:
    by_pid.setdefault(r["pid"], []).append(r)
chosen_b = []
pids = sorted(by_pid)
while len(chosen_b) < 25:
    for pid in pids:
        if by_pid[pid] and len(chosen_b) < 25:
            chosen_b.append(by_pid[pid].pop(rng.randrange(len(by_pid[pid]))))
sample = A + chosen_b
json.dump(sample, open(ROOT / ".tmp/wb_pass_sample.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
COLOURS = ["#1f77b4", "#2ca02c", "#9467bd", "#8c564b", "#17becf", "#bcbd22"]
out_dir = ROOT / ".planning/superworks-adapter/loop/WIRE-BREAK/png"
for chunk_index in range(0, len(sample), 6):
    chunk = sample[chunk_index:chunk_index + 6]
    panels, header = [], [f"WIRE-BREAK sample of new / newly-pass wire pairs (after), {chunk_index + 1}-{chunk_index + len(chunk)} of {len(sample)}",
                          "orange: the pair's line group; red: SW ports; green: SYMB2 TERMPOINTs; other colours: other groups"]
    for r in chunk:
        nd = next(Path(ROOT / ".tmp/superworks_round23_full").glob(f"{r['pid']}/*/findings"))
        bd = next(Path(ROOT / ".tmp/superworks_round22_full").glob(f"{r['pid']}/*/findings"))
        lg = pd.read_parquet(nd / "line_groups.parquet")
        g = lg[lg.line_group_id == r["group"]]
        if g.empty:
            continue
        g = g.iloc[0]
        x0, x1 = min(g.start_x, g.end_x), max(g.start_x, g.end_x)
        y0, y1 = min(g.start_y, g.end_y), max(g.start_y, g.end_y)
        window = (x0 - 12, y0 - 12, x1 + 12, y1 + 12)
        sheet_lg = lg[lg.sheet_id == r["sheet"]]
        segs = []
        for i, s in enumerate(sheet_lg.itertuples()):
            if s.end_x < window[0] or s.start_x > window[2] or max(s.start_y, s.end_y) < window[1] or min(s.start_y, s.end_y) > window[3]:
                continue
            colour = "#ff7f0e" if s.line_group_id == r["group"] else COLOURS[i % len(COLOURS)]
            segs.append((s.start_x, s.start_y, s.end_x, s.end_y, colour, 3.0 if colour == "#ff7f0e" else 1.6))
        ports = pd.read_parquet(nd / "sw_ports.parquet")
        ports = ports[ports.sheet_id == r["sheet"]]
        pts = [((p.start_x + p.end_x) / 2, p.start_y, "#d62728") for p in ports.itertuples()
               if window[0] <= p.start_x <= window[2] and window[1] <= p.start_y <= window[3]]
        u = pd.read_parquet(nd / "sw_unregistered_symb2.parquet")
        u = u[u.sheet_id == r["sheet"]]
        for ur in u.itertuples():
            for t in json.loads(ur.termpoints):
                mx = (t["a"][0] + t["b"][0]) / 2
                if window[0] <= mx <= window[2] and window[1] <= t["a"][1] <= window[3]:
                    pts.append((mx, t["a"][1], "#2ca02c"))
        fe = pd.read_parquet(nd / "source_files.parquet")
        fid = pd.read_parquet(nd / "pages.parquet").query("sheet_id == @r['sheet']").file_id.iloc[0]
        dxf = sorted(glob.glob(str(ROOT / ".tmp/superworks_round22_full" / r["pid"] / "cache/converted_dxf" / f"{fid}_*.dxf")))[0]
        title = [f"{r['pid']} {r['sheet']} {r['left']} <-> {r['right']}", f"{r['kind']} · pass · group {r['group']}",
                 "base: " + ("absent" if r["base_status"] == "none" else "other status")]
        panels.append(gr.Panel(title, dxf, window, segs=segs, pts=pts))
    if panels:
        gr.render(out_dir / f"WB_pass_sample_{chunk_index // 6 + 1:02d}.png", header, panels, cols=3)
print("sample", len(sample), "pngs", (len(sample) + 5) // 6)
