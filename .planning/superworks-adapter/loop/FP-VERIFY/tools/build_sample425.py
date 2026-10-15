"""Stratified sample of the 425 restored terminal-strip V1 passes; renders overlay PNGs (read-only inputs)."""
import sys, json, os
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/FP-VERIFY/tools")
import pandas as pd
import render_fp as R
W = "F:/workspace/XJToolkit/.tmp/fp_verify_work/"
OUT = "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/FP-VERIFY/png/"
cur = pd.read_pickle(W + "cur_pairs.pkl")
g = pd.read_pickle(W + "new_pass.pkl")
g = g[g.pair_kind == "component_mapping"].drop_duplicates(["project_id", "pair_id"])
# strata: (project, sheet); 2 examples from larger strata, 1 from smaller, total 16
picks = []
for (pid, sid), grp in g.groupby(["project_id", "sheet_id"]):
    grp = grp.sort_values("left_coord_y").reset_index(drop=True)
    n = len(grp)
    idxs = sorted({n // 3, (2 * n) // 3}) if n >= 40 else [n // 2]
    for i in idxs:
        picks.append(grp.iloc[i])
print("picked", len(picks))
jobs = []
for k, v in enumerate(picks):
    pid, sid, fid = v.project_id, v.sheet_id, v.file_id
    ly, ry = v.left_coord_y, v.right_coord_y
    lx, rx = v.left_coord_x, v.right_coord_x
    ev = json.loads(v.evidence) if isinstance(v.evidence, str) else v.evidence
    row_y = ev["terminal_strip_row_y"]
    cs = cur[(cur.project_id == pid) & (cur.sheet_id == sid) & (cur.status == "pass") & (cur.pair_kind == "component_mapping")]
    sw = cs[cs.pair_id.str.startswith("PSW") & (cs.left_value.isin([v.left_value, v.right_value]) | cs.right_value.isin([v.left_value, v.right_value]))]
    ov = [{"color": "#2563eb", "points": [[lx, ly], [rx, ry]], "lw": 2.6, "markers": [[lx, ly], [rx, ry]],
           "label": f"V1 cur {v.pair_id} {v.left_value}-{v.right_value} (pass)", "label_at": [lx + 1, ly - 3.8]}]
    colors = ["#16a34a", "#ea580c", "#9333ea", "#0d9488"]
    for j, s in enumerate(sw.itertuples()):
        pts = [[s.left_coord_x, s.left_coord_y], [s.right_coord_x, s.right_coord_y]]
        ov.append({"color": colors[j % 4], "points": pts, "lw": 3.0, "markers": pts,
                   "label": f"SW {s.pair_id} {s.left_value}-{s.right_value} (pass)", "label_at": [s.left_coord_x - 6, s.left_coord_y + 2.5 + 2.2 * j]})
    gid = v.line_group_id
    ov.append({"color": "#7c3aed", "points": [[(lx + rx) / 2, row_y + 2.5], [(lx + rx) / 2, row_y - 0.5]], "lw": 0.1, "markers": [], "label": None})
    cx, cy = (lx + rx) / 2, row_y + 1.5
    name = f"FP425_{k:02d}_{pid}_{sid}_{v.pair_id}"
    jobs.append({"project": pid, "file_id": fid, "sheet_id": sid, "cx": cx, "cy": cy, "half_width": 19, "half_height": 11,
                 "texts_parquet": R.__dict__.get("TEXTS", None) or f"F:/workspace/XJToolkit/.tmp/engine_coordination_full_acceptance/current/{pid}/project/findings/texts.parquet",
                 "title": f"{pid} {sid} {v.left_value}-{v.right_value} row y={row_y:.2f}: restored V1 pass (blue) with SW pin pairs",
                 "footer": f"Blue: restored V1 {v.pair_id} {v.left_value}<->{v.right_value} (line group {gid}, TSB-14 border). "
                           + "; ".join(f"{s.pair_id} {s.left_value}<->{s.right_value} (SW pass)" for s in sw.itertuples()),
                 "out": OUT + name + ".png", "overlays": ov})
spec = {"jobs": jobs}
json.dump(spec, open(W + "spec_425.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump([{"project": j["project"], "sheet": j["sheet_id"], "png": os.path.basename(j["out"]), "pair": j["title"]} for j in jobs],
          open(W + "sample425_index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("jobs", len(jobs))
