"""GAP-1 far-end probe (read-only): what lies at the far end of each single-ended device-terminal wire.

Population: uncovered eligible device terminals, reason no_matching_production_pair, no other port on the wire, route
record single-ended (GAP1, 5144) or no route record (GAP1sib, 926). For each wire the far endpoint F is the wire
endpoint farther from the contact. Tests at F, in priority order (tolerance 0.6 units unless noted):
  port_at_far          another SW port marker or contact within 1.0 (should not occur for a dangling wire)
  insert_edge_unreg    F on the bounding-box edge of an INSERT without LD_SYMB2_SPECIAL (unregistered component)
  insert_edge_sw       F on the edge of an SW-registered INSERT
  insert_inside_unreg  F strictly inside an unregistered INSERT bounding box
  insert_inside_sw     F strictly inside an SW-registered INSERT bounding box
  line_joint           another top-level line has an endpoint at F (the wire continues)
  line_tee             F lies on the interior of another top-level line
  gap_continuation     another top-level line endpoint beyond F on the wire axis, within 6 units, offset <= 0.6
  text_only            a TEXT/MTEXT insertion point within 3 units
  free                 nothing recorded

Usage: python gap1_probe.py <gap_work_dir>  -> <gap_work_dir>/gap1_probe.parquet
Inputs: uncovered.parquet and inserts.parquet (from build_table.py and insert_index.py), round findings via gaplib.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib as G  # noqa: E402

TOL = 0.6


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    L2 = np.where(L2 == 0, 1e-12, L2)
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
    cx, cy = ax + t * dx, ay + t * dy
    return np.hypot(px - cx, py - cy), t


def select_population(u: pd.DataFrame) -> pd.DataFrame:
    d = u[(u.category == "装置端子") & (u.reason == "no_matching_production_pair")]
    g1 = d[d.signature.str.startswith("悬空") & d.route_note.isin(["单端记录(另一端未记录)", "无路由记录"])].copy()
    g1["subset"] = np.where(g1.route_note == "单端记录(另一端未记录)", "GAP1", "GAP1sib")
    return g1


def probe_wire(row, proj, fid, L, ins_rows, texts, ports_pts):
    """One wire. L: top-level line arrays of the file; returns the probe dict."""
    lid, ax_, ay_, bx_, by_ = L
    k = G.wire_key(proj, fid, str(row.wire_handle))
    own = {str(m["line_id"]) for m in proj.members.get(k, [])}
    cx, cy = float(row.contact_x), float(row.contact_y)
    fx, fy = float(row.far_x), float(row.far_y)
    wdx, wdy = fx - cx, fy - cy
    wl = math.hypot(wdx, wdy) or 1.0
    info = {"project": proj.pid, "file_id": fid, "port_id": row.port_id, "subset": row.subset,
            "far_x": fx, "far_y": fy, "contact_x": cx, "contact_y": cy, "wire_len": wl,
            "wire_handle": str(row.wire_handle), "wire_key": str(k)}
    pxs, pys, pids = ports_pts
    near_port = ""
    if len(pxs):
        dp = np.hypot(pxs - fx, pys - fy)
        for i in np.argsort(dp):
            if dp[i] > 1.0:
                break
            if pids[i] != row.port_id:
                near_port = pids[i]
                break
    info["port_at_far"] = near_port
    if len(lid):
        mask = np.array([x not in own for x in lid], dtype=bool)
        de_a = np.hypot(ax_ - fx, ay_ - fy)
        de_b = np.hypot(bx_ - fx, by_ - fy)
        end_hit = mask & ((de_a <= TOL) | (de_b <= TOL))
        dist_seg, t = seg_dist(np.full(len(lid), fx), np.full(len(lid), fy), ax_, ay_, bx_, by_)
        interior = mask & (dist_seg <= TOL) & (t > 0.02) & (t < 0.98) & ~end_hit
        info["line_joint_n"] = int(end_hit.sum())
        info["line_tee_n"] = int(interior.sum())
        # continuation: an endpoint E of another line lies beyond F on the wire's own axis (perpendicular offset
        # <= TOL, along-axis distance in (TOL, 6]), so the wire would carry on after a short break.
        ux, uy = wdx / wl, wdy / wl
        cand = []
        for arr_x, arr_y in ((ax_, ay_), (bx_, by_)):
            ex, ey = arr_x - fx, arr_y - fy
            along = ex * ux + ey * uy
            perp = np.abs(ex * uy - ey * ux)
            sel = mask & (along > TOL) & (along <= 6.0) & (perp <= TOL)
            cand.extend(float(v) for v in along[sel])
        info["gap_cont_min"] = min(cand) if cand else None
    else:
        info["line_joint_n"] = 0
        info["line_tee_n"] = 0
        info["gap_cont_min"] = None
    hits, nearest = [], None
    for b in ins_rows:
        if str(b["handle"]) == str(row.insert_handle):
            continue  # the port's own symbol is not the far end
        x0, y0, x1, y1 = b["xmin"], b["ymin"], b["xmax"], b["ymax"]
        if x0 is None or x0 != x0:
            continue
        if x0 - 1 <= fx <= x1 + 1 and y0 - 1 <= fy <= y1 + 1:
            edge = min(abs(fx - x0), abs(fx - x1), abs(fy - y0), abs(fy - y1))
            inside = x0 <= fx <= x1 and y0 <= fy <= y1
            hits.append((b["block"], bool(b["sw_special"]), edge, inside, b["handle"]))
        dist_b = math.hypot(max(x0 - fx, 0, fx - x1), max(y0 - fy, 0, fy - y1))
        if nearest is None or dist_b < nearest[0]:
            nearest = (dist_b, b["block"], bool(b["sw_special"]))
    info["insert_hits"] = [list(h) for h in hits]
    info["nearest_box_dist"] = nearest[0] if nearest else None
    info["nearest_box_block"] = nearest[1] if nearest else ""
    info["nearest_box_sw"] = nearest[2] if nearest else None
    tx, ty, ttext = texts
    tnear = None
    if len(tx):
        dt = np.hypot(tx - fx, ty - fy)
        j = int(np.argmin(dt))
        if dt[j] <= 3.0:
            tnear = (ttext[j], float(dt[j]))
    info["text_near"] = tnear[0] if tnear else ""
    info["text_dist"] = tnear[1] if tnear else None
    edge_hits = [h for h in hits if h[2] <= TOL and not h[3]]
    inside_hits = [h for h in hits if h[3]]
    if near_port:
        cls = "port_at_far"
    elif info["line_joint_n"] > 0:
        cls = "line_joint"
    elif info["line_tee_n"] > 0:
        cls = "line_tee"
    elif any(not h[1] for h in edge_hits):
        cls = "insert_edge_unreg"
    elif edge_hits:
        cls = "insert_edge_sw"
    elif any(not h[1] for h in inside_hits):
        cls = "insert_inside_unreg"
    elif inside_hits:
        cls = "insert_inside_sw"
    elif info["gap_cont_min"] is not None:
        cls = "gap_continuation"
    elif tnear:
        cls = "text_only"
    else:
        cls = "free"
    info["far_class"] = cls
    edge_pick = edge_hits[0] if edge_hits else None
    info["edge_block"] = edge_pick[0] if edge_pick else ""
    info["edge_handle"] = edge_pick[4] if edge_pick else ""
    return info


def main(work: Path):
    u = pd.read_parquet(work / "uncovered.parquet")
    ins_all = pd.read_parquet(work / "inserts.parquet")
    g1 = select_population(u)
    out = []
    projects = sorted(set(g1.project))
    for proj in G.iter_projects(only=projects):
        sub = g1[g1.project == proj.pid]
        ports_by_file = defaultdict_list()
        for p in proj.ports.to_dict("records"):
            for c in G.contacts_of(p):
                ports_by_file[p["file_id"]].append((float(c["x"]), float(c["y"]), p["record_id"]))
            for x, y in ((p["start_x"], p["start_y"]), (p["end_x"], p["end_y"])):
                ports_by_file[p["file_id"]].append((float(x), float(y), p["record_id"]))
        top = proj.lines[proj.lines.source_block_name.map(lambda v: not G.text(v))]
        for fid, rows in sub.groupby("file_id"):
            Lf = top[top.file_id == fid]
            L = (Lf.line_id.to_numpy(str), Lf.start_x.to_numpy(float), Lf.start_y.to_numpy(float),
                 Lf.end_x.to_numpy(float), Lf.end_y.to_numpy(float))
            tf = proj.texts[proj.texts.file_id == fid]
            texts = (tf.insert_x.to_numpy(float), tf.insert_y.to_numpy(float), tf.text.astype(str).to_numpy())
            pl = ports_by_file.get(fid, [])
            ports_pts = (np.array([a for a, _, _ in pl], float), np.array([b for _, b, _ in pl], float),
                         [c for _, _, c in pl])
            ins_rows = ins_all[(ins_all.project == proj.pid) & (ins_all.file_id == fid)].to_dict("records")
            for row in rows.itertuples():
                if not row.wire_handle:
                    continue
                out.append(probe_wire(row, proj, fid, L, ins_rows, texts, ports_pts))
    frame = pd.DataFrame(out)
    frame["insert_hits"] = frame.insert_hits.map(lambda h: json.dumps(h, ensure_ascii=False))
    frame.to_parquet(work / "gap1_probe.parquet", index=False)
    print(frame.groupby(["subset", "far_class"]).size().to_string())


def defaultdict_list():
    return defaultdict(list)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
