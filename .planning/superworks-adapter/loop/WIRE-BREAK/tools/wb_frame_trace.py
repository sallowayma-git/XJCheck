"""Offline trace of the frame rule for one pair of a run (read-only): the frame, the label text, and each pin reached.

usage: wb_frame_trace.py RUN_ROOT PROJECT PAIR_ID
"""
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, "F:/workspace/XJToolkit/src")
from dwg_audit.audit.superworks_wire_walk import (device_frame, rectangles, segment_index, walk_wire, mark_touches)  # noqa: E402
from dwg_audit.audit.superworks_device_internal import label_of  # noqa: E402

root, pid, pair_id = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
f = next(root.glob(f"{pid}/*/findings"))
pairs = pd.read_parquet(f / "pairs.parquet").set_index("pair_id")
p = pairs.loc[pair_id]
lg = pd.read_parquet(f / "line_groups.parquet").set_index("line_group_id")
g = lg.loc[p.line_group_id]
sheet = p.sheet_id
lines = pd.read_parquet(f / "lines.parquet")


class L: pass
objs = []
for r in lines.itertuples():
    if r.sheet_id != sheet: continue
    o = L(); o.sheet_id = r.sheet_id; o.start_x, o.start_y, o.end_x, o.end_y = r.start_x, r.start_y, r.end_x, r.end_y
    o.source_block_name = None if pd.isna(r.source_block_name) else r.source_block_name
    objs.append(o)
model = segment_index(objs)[sheet]
prim = pd.read_parquet(f / "primitive_segments.parquet")
blocks = []
for r in prim[(prim.sheet_id == sheet) & (prim.primitive_kind == "LINE") & prim.definition_name.notna()].itertuples():
    if r.visible is False: continue
    gj = json.loads(r.world_geometry_json)
    blocks.append((float(gj["start"][0]), float(gj["start"][1]), float(gj["end"][0]), float(gj["end"][1])))
ports = pd.read_parquet(f / "sw_ports.parquet"); ports = ports[ports.sheet_id == sheet]
unreg = pd.read_parquet(f / "sw_unregistered_symb2.parquet"); unreg = unreg[unreg.sheet_id == sheet]
texts = pd.read_parquet(f / "texts.parquet"); texts = texts[texts.sheet_id == sheet]
text_rows = [(str(t.normalized_text or t.text).strip(), (t.bbox_min_x, t.bbox_min_y, t.bbox_max_x, t.bbox_max_y)) for t in texts.itertuples() if str(t.text).strip()]
# terminal ports touching the group end
ends = [(g.start_x, g.start_y), (g.end_x, g.end_y)]
term = ports[(ports.category == "装置端子")]
touch = [q for q in term.itertuples() if any(mark_touches(e, (q.start_x, q.start_y, q.end_x, q.end_y)) for e in ends)]
label = label_of({"label": touch[0].label})[0] if touch else ""
terminal_points = [((q.start_x + q.end_x) / 2, (q.start_y + q.end_y) / 2) for q in touch]
term_keys = {q.symbol_id for q in touch}
far = [e for e in ends if not any(mark_touches(e, (q.start_x, q.start_y, q.end_x, q.end_y)) for q in touch)]
marks = []
for q in ports[ports.sheet_id == sheet].itertuples():
    lab, res = label_of({"label": q.label})
    marks.append((q.symbol_id, q.record_id, (q.start_x, q.start_y, q.end_x, q.end_y), q.category, lab, res, False))
for u in unreg.itertuples():
    for t in json.loads(u.termpoints):
        marks.append((f"SW:{u.file_id}:{sheet}:{u.instance_path}", f"{u.record_id}#{t['number']}",
                      (t["a"][0], t["a"][1], t["b"][0], t["b"][1]), "", u.label_value, bool(u.label_resolved), True))
walk_marks = [(k, rid, seg) for k, rid, seg, *_ in marks]
visited, endpts, reached = walk_wire(model + blocks, far[0], walk_marks)
print("pair", pair_id, "terminal", [q.endpoint_identity for q in touch], "label", label, "open end", far)
rects = rectangles(model)
print("rectangles on sheet holding terminal:", [r for r in rects if all(r[0] - .5 <= x <= r[2] + .5 and r[1] - .5 <= y <= r[3] + .5 for x, y in terminal_points)])
print("frame:", device_frame(rects, label, terminal_points, text_rows))
print("walked segments", len(visited), "reached marks:")
for k, rid, seg, cat, lab, res, unreg_ in marks:
    if (k, rid) in reached and k not in term_keys:
        print("  ", rid, "cat", cat or "(unregistered)", "label", lab, "resolved", res, "unregistered", unreg_)
