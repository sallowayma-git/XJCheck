"""Attach DXF INSERT (symbol) hits to each gap end point (read-only; writes .tmp/gap_triage_work/features_ins.pkl).

For every R-RECOGNITION-GAP row, each end of the observed segment is tested against the expanded bounding box
(tolerance 0.6) of every INSERT in the same DXF file. An INSERT is:
  frame    title or sign blocks (Title_*, SignBlock_*): ignored
  reg      its handle appears in the SuperWORKS tables of the project (ports, symbols, part instances or
           unregistered SYMB2 rows): SuperWORKS knows the element
  unreg    anonymous or SYMB2 element that SuperWORKS does not know at all
Output columns: end1_ins / end2_ins = JSON list of {name, handle, kind, reg} for the hits at that end.
"""
from __future__ import annotations

import glob
import json
import os
from collections import defaultdict
from pathlib import Path

import ezdxf
import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
CUR = REPO / ".tmp/engine_coordination_full_acceptance/current"
WORK = REPO / ".tmp/gap_triage_work"
MANIFEST = REPO / ".planning/superworks-adapter/corpus_manifest.json"
TOL = 0.6


def dxf_map():
    man = json.load(open(MANIFEST, encoding="utf-8"))
    return {(p["project_id"], f["file_id"]): f["dxf_path"] for p in man["projects"] for f in p["files"]}


def is_frame(name: str) -> bool:
    return name.startswith("Title") or name.startswith("SignBlock")


def registry_handles(pid):
    fdir = glob.glob(str(CUR / pid / "*" / "findings"))[0]
    out = set()
    for name, col in (("sw_ports.parquet", "insert_handle"), ("sw_symbols.parquet", "insert_handle"),
                      ("sw_part_instances.parquet", "insert_handle"), ("sw_unregistered_symb2.parquet", "insert_handle")):
        p = os.path.join(fdir, name)
        if os.path.exists(p):
            out.update(str(v) for v in pd.read_parquet(p, columns=[col])[col].dropna())
    return out


def insert_boxes(path):
    doc = ezdxf.readfile(path)
    boxes = []
    for ent in doc.modelspace():
        if ent.dxftype() != "INSERT":
            continue
        xs, ys = [], []
        try:
            for v in ent.virtual_entities():
                for attr in ("start", "end", "center"):
                    p = getattr(v.dxf, attr, None) if hasattr(v, "dxf") else None
                    if p is not None:
                        xs.append(p[0]); ys.append(p[1])
                if v.dxftype() == "LWPOLYLINE":
                    for pt in v.get_points("xy"):
                        xs.append(pt[0]); ys.append(pt[1])
        except Exception:  # noqa: BLE001
            pass
        if not xs:
            ip = ent.dxf.insert
            xs, ys = [ip[0]], [ip[1]]
        boxes.append((ent.dxf.name, ent.dxf.handle, min(xs) - TOL, min(ys) - TOL, max(xs) + TOL, max(ys) + TOL))
    return boxes


def hits(point, boxes, reg):
    out = []
    if point is None:
        return out
    x, y = point
    for name, handle, x0, y0, x1, y1 in boxes:
        if x0 <= x <= x1 and y0 <= y <= y1:
            kind = "frame" if is_frame(name) else ("reg" if str(handle) in reg else "unreg")
            out.append({"name": name, "handle": handle, "kind": kind})
    return out


def main():
    df = pd.read_pickle(WORK / "features.pkl")
    dmap = dxf_map()
    end1, end2 = [], []
    by_pf = defaultdict(list)
    for i, r in enumerate(df.itertuples(index=False)):
        by_pf[(r.project, r.file_id)].append(i)
    res1, res2 = [None] * len(df), [None] * len(df)
    for n, ((pid, fid), idxs) in enumerate(by_pf.items()):
        reg = registry_handles(pid)
        boxes = insert_boxes(dmap[(pid, fid)])
        for i in idxs:
            coords = json.loads(df.iloc[i].coords) if df.iloc[i].coords else []
            if len(coords) != 4:
                res1[i] = []
                res2[i] = []
                continue
            p1 = (coords[0], coords[1])
            p2 = (coords[2], coords[3])
            res1[i] = hits(p1, boxes, reg)
            res2[i] = hits(p2, boxes, reg)
        print("done", pid, fid, len(idxs), flush=True)
    df = df.copy()
    df["end1_ins"] = [json.dumps(x, ensure_ascii=False) for x in res1]
    df["end2_ins"] = [json.dumps(x, ensure_ascii=False) for x in res2]
    df.to_pickle(WORK / "features_ins.pkl")
    print("rows", len(df))


if __name__ == "__main__":
    main()
