"""Offline trace of the wire-walk rule for named pairs (read-only).

usage: wb_walk_trace.py RUN_ROOT PROJECT PAIR_ID [PAIR_ID ...]
Re-runs superworks_wire_walk on the run's lines, line groups and SW marks and prints, for each pair, the open end,
the walked segments and every symbol reached (with its device-internal verdict against the terminal).
"""
import glob, json, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "F:/workspace/XJToolkit/src")
from dwg_audit.audit.superworks_device_internal import device_internal_verdict, label_of  # noqa: E402
from dwg_audit.audit.superworks_wire_walk import mark_touches, segment_index, walk_wire  # noqa: E402

root, pid, pair_ids = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
f = next(root.glob(f"{pid}/*/findings"))
pairs = pd.read_parquet(f / "pairs.parquet").set_index("pair_id")
lg = pd.read_parquet(f / "line_groups.parquet").set_index("line_group_id")
lines = pd.read_parquet(f / "lines.parquet")
ports = pd.read_parquet(f / "sw_ports.parquet")
unreg = pd.read_parquet(f / "sw_unregistered_symb2.parquet")


class L:
    pass


line_objs = []
for r in lines.itertuples():
    o = L()
    o.sheet_id, o.start_x, o.start_y, o.end_x, o.end_y = r.sheet_id, r.start_x, r.start_y, r.end_x, r.end_y
    o.source_block_name = getattr(r, "source_block_name", None) if hasattr(r, "source_block_name") else None
    if isinstance(o.source_block_name, float):
        o.source_block_name = None
    line_objs.append(o)
segs = segment_index(line_objs)
for pid_ in pair_ids:
    p = pairs.loc[pid_]
    g = lg.loc[p.line_group_id]
    sheet = p.sheet_id
    resolved = "left" if isinstance(p.left_value, str) and p.left_value else "right"
    term_value = p.left_value if resolved == "left" else p.right_value
    sheet_ports = ports[(ports.sheet_id == sheet) & (ports.category == "装置端子")]
    ends = [(g.start_x, g.start_y), (g.end_x, g.end_y)]
    touching = [q for q in sheet_ports.itertuples()
                if any(mark_touches(e, (q.start_x, q.start_y, q.end_x, q.end_y)) for e in ends)]
    term_ports = sheet_ports[sheet_ports.record_id.isin([q.record_id for q in touching])]
    term_value = touching[0].endpoint_identity if touching else term_value
    at = lambda pt: any(mark_touches(pt, (q.start_x, q.start_y, q.end_x, q.end_y)) for q in term_ports.itertuples())
    far = [e for e in ends if not at(e)]
    print(f"== {pid_} {sheet} resolved={term_value} far_end={far} group={p.line_group_id}")
    if len(far) != 1:
        print("   no single open end"); continue
    visited, end_points = walk_wire(segs.get(sheet, []), far[0])
    print(f"   walked segments {len(visited)}")
    term_keys = set(term_ports.symbol_id)
    for q in ports[ports.sheet_id == sheet].itertuples():
        if q.symbol_id in term_keys: continue
        if any(mark_touches(e, (q.start_x, q.start_y, q.end_x, q.end_y)) for e in end_points):
            lab, res = label_of({"label": q.label})
            v = device_internal_verdict({"category": "装置端子", "identity": term_value, "label": term_value.rstrip("0123456789"), "label_resolved": True},
                                        {"category": q.category, "label": lab, "label_resolved": res, "unregistered": False, "identity": q.endpoint_identity or ""})
            print(f"   SW port {q.record_id[-22:]} cat={q.category} id={q.endpoint_identity} label={lab} res={res} -> {v}")
    for u in unreg[unreg.sheet_id == sheet].itertuples():
        for t in json.loads(u.termpoints):
            seg = (t["a"][0], t["a"][1], t["b"][0], t["b"][1])
            if any(mark_touches(e, seg) for e in end_points):
                print(f"   UNREG {u.label_value} res={u.label_resolved} termpoint {t['number']} at {seg[:2]}")
