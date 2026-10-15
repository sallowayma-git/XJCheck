"""Render nested duplicate-port conflict cases (read-only): sw_ports records of parent vs child instance at same contact."""
import sys, json, glob
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/FP-VERIFY/tools")
import pandas as pd
import render_fp as R
CUR = "F:/workspace/XJToolkit/.tmp/engine_coordination_full_acceptance/current/"
OUT = "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/FP-VERIFY/png/"
jobs = []
for pid, sid, fid, parent, child_marks in [
    ("p041", "S0012", "F0012", "/2F60B", ("1B9EA", "1B9ED")),
    ("p043", "S0013", "F0013", "/2F5F6", ("1B9EA", "1B9ED")),
]:
    f = glob.glob(f"{CUR}{pid}/*/findings")[0] + "/"
    sp = pd.read_parquet(f + "sw_ports.parquet")
    s = sp[sp.sheet_id == sid]
    par = s[(s.instance_path == parent) & s.marker_handle.isin(child_marks)]
    chi = s[(s.instance_path == parent + "/2F324") & s.marker_handle.isin(child_marks)]
    own = s[(s.instance_path == parent) & ~s.marker_handle.isin(child_marks)]
    ov = []
    for label, df, col in [("child /2F324 coil port records (native)", chi, "#16a34a"),
                           ("parent-path records of the SAME marker handles", par, "#ea580c"),
                           ("parent own pins (other handles)", own, "#9333ea")]:
        pts = []
        for r in df.itertuples():
            pts.append([r.start_x, r.start_y]); pts.append([r.end_x, r.end_y])
        if pts:
            ov.append({"color": col, "points": [], "markers": pts, "ms": 90, "label": f"{label}: {len(df)} rec", "label_at": [float(df.start_x.mean()) + 1.0, float(df.start_y.mean()) + 2.0 + 2.2 * len(ov)]})
    # wires touching the contact (from observations' object keys)
    ob = pd.read_parquet(f + "sw_resolution_observations.parquet")
    ob = ob[(ob.sheet_id == sid) & ob.reason_codes.astype(str).str.contains("competing")]
    wires = []
    for r in ob.itertuples():
        c = r.coords if not isinstance(r.coords, str) else json.loads(r.coords)
        if c is not None and len(c) == 4:
            wires.append(c)
    for i, c in enumerate(wires):
        ov.append({"color": "#2563eb", "points": [[c[0], c[1]], [c[2], c[3]]], "lw": 2.2, "markers": [], "label": None})
    cx = float(chi.start_x.mean()) if len(chi) else 205.0
    cy = float(chi.start_y.mean()) if len(chi) else 167.5
    recs = "; ".join(f"{r.record_id.split(':')[-3]}:{r.record_id.split(':')[-2]}" for r in pd.concat([chi, par]).itertuples())
    jobs.append({"project": pid, "file_id": fid, "sheet_id": sid, "cx": cx, "cy": cy, "half_width": 16, "half_height": 9,
                 "texts_parquet": glob.glob(f"{CUR}{pid}/*/findings/texts.parquet")[0],
                 "title": f"{pid} {sid}: nested duplicate port {child_marks[0]}/{child_marks[1]} under {parent} and {parent}/2F324 (gap 0.0)",
                 "footer": f"Green: child-instance records {parent}/2F324 (coil, native). Orange: same marker handles again as {parent} records (instance_path {parent}, owner {parent}/2F324). Blue: wires flagged competing (observations). Same coords, same marker, same port number.",
                 "out": OUT + f"CONF_{pid}_{sid}_nested_port.png", "overlays": ov})
    print(pid, "child", len(chi), "parent-same-marker", len(par), "own", len(own), "wires", len(wires))
json.dump({"jobs": jobs}, open("F:/workspace/XJToolkit/.tmp/fp_verify_work/spec_conf.json", "w", encoding="utf-8"), ensure_ascii=False)
