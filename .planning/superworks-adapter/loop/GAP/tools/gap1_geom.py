"""GAP-1 far-end geometry (read-only): is the far endpoint on the drawn geometry of a block, and of which block?

For each GAP-1 wire (see gap1_probe.py) the INSERT candidates are the modelspace INSERTs whose bounding box (from
inserts.parquet) lies within 1 unit of the far endpoint F. Their world geometry is taken from ezdxf virtual entities
(LINE, LWPOLYLINE/POLYLINE segments, CIRCLE and ARC sampled). For each candidate:
  d_geom      distance from F to the nearest drawn segment or sampled arc point
  d_vertex    distance from F to the nearest vertex (segment end point), i.e. a pin-lead end
  n_segments  number of drawn segments (block size)
Candidates whose bounding box spans more than 40% of the sheet (SignBlock frames) are reported but flagged `frame`.

Output: <work>/gap1_geom.parquet, one row per wire: best candidate by d_geom among non-frame blocks, plus the
frame flag and all candidate summaries as JSON.

Usage: python gap1_geom.py <gap_work_dir>
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import ezdxf
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ezdxf import recover  # noqa: E402

FRAME_FRACTION = 0.40


def load_doc(path):
    try:
        return ezdxf.readfile(path)
    except Exception:  # noqa: BLE001
        doc, _ = recover.readfile(path)
        return doc


def block_geometry(ins):
    """World segments (x0,y0,x1,y1) and vertices of an INSERT's virtual entities."""
    segs, verts = [], []
    try:
        ents = list(ins.virtual_entities())
    except Exception:  # noqa: BLE001
        return segs, verts
    stack = list(ents)
    while stack:
        e = stack.pop()
        kind = e.dxftype()
        if kind == "INSERT":
            try:
                stack.extend(list(e.virtual_entities()))
            except Exception:  # noqa: BLE001
                pass
            continue
        if kind == "LINE":
            s, t = e.dxf.start, e.dxf.end
            segs.append((s.x, s.y, t.x, t.y))
            verts.extend([(s.x, s.y), (t.x, t.y)])
        elif kind in ("LWPOLYLINE",):
            pts = [(p[0], p[1]) for p in e.get_points("xy")]
            for a, b in zip(pts, pts[1:]):
                segs.append((a[0], a[1], b[0], b[1]))
            verts.extend(pts)
            if e.closed and len(pts) > 2:
                segs.append((pts[-1][0], pts[-1][1], pts[0][0], pts[0][1]))
        elif kind == "POLYLINE":
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            for a, b in zip(pts, pts[1:]):
                segs.append((a[0], a[1], b[0], b[1]))
            verts.extend(pts)
        elif kind in ("CIRCLE", "ARC"):
            c = e.dxf.center
            r = float(e.dxf.radius)
            if kind == "CIRCLE":
                a0, a1 = 0.0, 360.0
            else:
                a0, a1 = float(e.dxf.start_angle), float(e.dxf.end_angle)
                if a1 <= a0:
                    a1 += 360.0
            n = max(8, int((a1 - a0) / 15))
            pts = [(c.x + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                    c.y + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
            for a, b in zip(pts, pts[1:]):
                segs.append((a[0], a[1], b[0], b[1]))
    return segs, verts


def point_seg_dist(fx, fy, segs):
    if not segs:
        return math.inf
    a = np.array(segs, float)
    ax, ay, bx, by = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    dx, dy = bx - ax, by - ay
    L2 = np.where(dx * dx + dy * dy == 0, 1e-12, dx * dx + dy * dy)
    t = np.clip(((fx - ax) * dx + (fy - ay) * dy) / L2, 0, 1)
    return float(np.min(np.hypot(fx - (ax + t * dx), fy - (ay + t * dy))))


def main(work: Path):
    probe = pd.read_parquet(work / "gap1_probe.parquet")
    ins = pd.read_parquet(work / "inserts.parquet")
    uncov = pd.read_parquet(work / "uncovered.parquet")
    probe = probe.merge(uncov[["port_id", "project", "dxf", "insert_handle"]], on=["port_id", "project"], how="left")
    rows = []
    for (proj, fid, dxf), grp in probe.groupby(["project", "file_id", "dxf"]):
        cand_ins = ins[(ins.project == proj) & (ins.file_id == fid) & ins.xmin.notna()]
        if not len(cand_ins) or not isinstance(dxf, str):
            for r in grp.itertuples():
                rows.append({"port_id": r.port_id, "project": proj, "best_block": "", "best_handle": "", "d_geom": None,
                             "d_vertex": None, "frame_hit": False, "cands": "[]"})
            continue
        doc = load_doc(dxf)
        ms = doc.modelspace()
        cache = {}
        sheet_w = float(cand_ins.xmax.max() - cand_ins.xmin.min()) or 1.0
        sheet_h = float(cand_ins.ymax.max() - cand_ins.ymin.min()) or 1.0
        for r in grp.itertuples():
            fx, fy = float(r.far_x), float(r.far_y)
            near = cand_ins[(cand_ins.xmin - 1 <= fx) & (fx <= cand_ins.xmax + 1)
                            & (cand_ins.ymin - 1 <= fy) & (fy <= cand_ins.ymax + 1)
                            & (cand_ins.handle.astype(str) != str(r.insert_handle))]
            cands = []
            for c in near.itertuples():
                if c.handle not in cache:
                    try:
                        e = doc.entitydb.get(c.handle)
                        cache[c.handle] = block_geometry(e) if e is not None else ([], [])
                    except Exception:  # noqa: BLE001
                        cache[c.handle] = ([], [])
                segs, verts = cache[c.handle]
                d_geom = point_seg_dist(fx, fy, segs)
                d_vertex = min((math.hypot(fx - vx, fy - vy) for vx, vy in verts), default=math.inf)
                area_frac = ((c.xmax - c.xmin) * (c.ymax - c.ymin)) / (sheet_w * sheet_h)
                cands.append({"block": c.block, "handle": c.handle, "sw_special": bool(c.sw_special),
                              "d_geom": round(d_geom, 3), "d_vertex": round(d_vertex, 3), "n_segments": len(segs),
                              "frame": bool(area_frac > FRAME_FRACTION)})
            body = [c for c in cands if not c["frame"]]
            best = min(body, key=lambda c: c["d_geom"]) if body else None
            rows.append({"port_id": r.port_id, "project": proj, "best_block": best["block"] if best else "",
                         "best_handle": best["handle"] if best else "", "best_sw": best["sw_special"] if best else None,
                         "d_geom": best["d_geom"] if best else None, "d_vertex": best["d_vertex"] if best else None,
                         "n_segments": best["n_segments"] if best else 0,
                         "frame_hit": any(c["frame"] for c in cands), "cands": json.dumps(cands, ensure_ascii=False)})
    frame = pd.DataFrame(rows)
    frame.to_parquet(work / "gap1_geom.parquet", index=False)
    print("rows", len(frame))
    print("d_geom<=0.6:", int((frame.d_geom <= 0.6).sum()), " d_vertex<=0.6:", int((frame.d_vertex <= 0.6).sum()),
          " no body candidate:", int(frame.best_block.eq("").sum()))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
