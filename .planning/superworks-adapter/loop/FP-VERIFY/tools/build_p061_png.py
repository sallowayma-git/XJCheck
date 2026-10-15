"""p061 S0025 low-confidence review pairs: overlay on DXF (read-only). Border line groups in purple, r25 SW pass in green."""
import sys, json, glob
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/FP-VERIFY/tools")
import pandas as pd
import render_fp as R
CUR = glob.glob("F:/workspace/XJToolkit/.tmp/engine_coordination_full_acceptance/current/p061/*/findings")[0] + "/"
R25 = glob.glob("F:/workspace/XJToolkit/.tmp/superworks_round25_full/p061/*/findings")[0] + "/"
OUT = "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/FP-VERIFY/png/"
cur = pd.read_parquet(CUR + "pairs.parquet"); r25 = pd.read_parquet(R25 + "pairs.parquet")
lg = pd.read_parquet(CUR + "line_groups.parquet")
low = cur[(cur.sheet_id == "S0025") & (cur.status == "review") & (cur.pair_kind == "ordinary_pair")]
groups = ["GC0063", "GC0069", "GC0070", "GC0080"]
ov = []
for g in groups:
    r = lg[lg.line_group_id == g].iloc[0]
    ov.append({"color": "#7c3aed", "points": [[r.start_x, r.start_y], [r.end_x, r.end_y]], "lw": 3.2, "markers": [], "label": f"{g} BORDER (cur support)", "label_at": [r.start_x + 2, (r.start_y + r.end_y) / 2]})
for p in low.itertuples():
    ov.append({"color": "#dc2626", "points": [[p.left_coord_x, p.left_coord_y], [p.right_coord_x, p.right_coord_y]], "lw": 2.0,
               "markers": [[p.left_coord_x, p.left_coord_y], [p.right_coord_x, p.right_coord_y]], "ls": "--",
               "label": f"cur {p.pair_id} {p.left_value}-{p.right_value} review {p.confidence:.3f}", "label_at": [p.left_coord_x + 1.5, p.left_coord_y + 14]})
rp = r25[(r25.sheet_id == "S0025") & (r25.status == "pass") & (r25.pair_kind == "component_mapping") & (r25.line_group_id.isin(groups))]
for p in rp.itertuples():
    ov.append({"color": "#16a34a", "points": [[p.left_coord_x, p.left_coord_y], [p.right_coord_x, p.right_coord_y]], "lw": 2.4,
               "markers": [[p.left_coord_x, p.left_coord_y], [p.right_coord_x, p.right_coord_y]],
               "label": f"r25 {p.pair_id} {p.left_value}-{p.right_value} pass ({p.line_group_id})", "label_at": [p.left_coord_x + 1.5, p.left_coord_y - 6]})
fid = cur[cur.sheet_id == "S0025"].file_id.iloc[0]
texts = glob.glob("F:/workspace/XJToolkit/.tmp/engine_coordination_full_acceptance/current/p061/*/findings/texts.parquet")[0]
jobs = [
 {"project": "p061", "file_id": fid, "sheet_id": "S0025", "cx": 185, "cy": 215, "half_width": 125, "half_height": 62,
  "texts_parquet": texts, "title": "p061 S0025 overview: 4 low-confidence review pairs (red dashed) on BORDER groups (purple)",
  "footer": "Red dashed: cur review ordinary pairs (11-8 x3, 9-9 x1). Purple: BORDER line groups GC0063/69/70/80 (component frames, not wires). Green: r25 pass component pairs that used the same BORDER groups as support.",
  "out": OUT + "LOWCONF_p061_S0025_overview.png", "overlays": ov},
 {"project": "p061", "file_id": fid, "sheet_id": "S0025", "cx": 160, "cy": 215, "half_width": 32, "half_height": 40,
  "texts_parquet": texts, "title": "p061 S0025 zoom at x~160: PC0066 (11-8) and PC0067 (11-8) on BORDER GC0069/GC0070",
  "footer": "Same overlay as overview, zoomed on the x=160 frame lines.", "out": OUT + "LOWCONF_p061_S0025_zoom160.png", "overlays": ov},
]
json.dump({"jobs": jobs}, open("F:/workspace/XJToolkit/.tmp/fp_verify_work/spec_p061.json", "w", encoding="utf-8"), ensure_ascii=False)
print("low", len(low), "r25 green", len(rp))
