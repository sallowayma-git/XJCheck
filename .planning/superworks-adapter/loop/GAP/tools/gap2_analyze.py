"""GAP-2 analysis (read-only): multi-end wires of uncovered device terminals (GAP-2a and GAP-2b).

A GAP-2 wire is one SuperWORKS wire key whose member lines are a collinear run (legacy line group, merged along the
axis within gap_tol / numeric-text bridge) plus the one-to-one GWSW references of its contact lines. For each wire:
  axis            horizontal / vertical (from the run's member segments)
  n_members       member LINE segments of the key
  gaps            distinct gaps along the axis between consecutive member segments (> 0.6 units)
  max_gap         widest gap
  gap_text        number of gaps that contain a text insertion point (the inline-bridge case of the legacy merge)
  gap_split_ports number of gaps with ports on both sides (a port on each side = ports of different segments merged)
  port_on_gap_side  ports sitting within 1.0 units of a gap end
  dots_at_ports   ports whose contact has an SW connect dot (LD_CONNECT_DOT, dot within 1.2 units)
  dots_at_gaps    gaps with an SW connect dot in them
  n_ports         ports on the key (all categories), with categories
  overlap_passthrough  a port marker lying collinear with the run (the run passes through the marker)

Output: <work>/gap2_detail.parquet (one row per GAP-2 wire) and gap2_summary.json.
Usage: python gap2_analyze.py <gap_work_dir>
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib as G  # noqa: E402

DOT_TOL = 1.2


def classify_set(u):
    d = u[(u.category == "装置端子") & (u.reason == "no_matching_production_pair")]
    a = d[d.signature == "内部元件(无身份) + 端子 + 装置端子"].copy()
    a["subset"] = "GAP2a"
    b = d[d.signature == "端子 + 装置端子"].copy()
    b["subset"] = "GAP2b"
    return pd.concat([a, b], ignore_index=True)


def main(work: Path):
    u = pd.read_parquet(work / "uncovered.parquet")
    gap2 = classify_set(u)
    dots = []
    for f in glob.glob(str(ROUND / "p*" / "*" / "findings" / "sw_connect_dots.parquet")):
        pid = Path(f).parts[-4]
        dd = pd.read_parquet(f)
        if len(dd):
            dots.append(dd.assign(project=pid)[["project", "file_id", "x", "y"]])
    dots = pd.concat(dots, ignore_index=True)
    ins = pd.read_parquet(work / "inserts.parquet")
    sn = ins[ins.block == "SolidNode"][["project", "file_id", "x", "y"]]
    rows = []
    for proj in G.iter_projects(only=sorted(set(gap2.project))):
        sub = gap2[gap2.project == proj.pid]
        if not len(sub):
            continue
        top = proj.lines[proj.lines.source_block_name.map(lambda v: not G.text(v))]
        texts_by_file = {fid: t for fid, t in proj.texts.groupby("file_id")}
        ports_by_file = defaultdict(list)
        for p in proj.ports.to_dict("records"):
            ports_by_file[p["file_id"]].append(p)
        for r in sub.to_dict("records"):
            fid = r["file_id"]
            k = G.wire_key(proj, fid, str(r["wire_handle"]))
            mem = proj.members.get(k, [])
            if not mem:
                continue
            horiz = np.mean([abs(float(l["end_y"]) - float(l["start_y"])) < 1e-6 for l in mem]) >= 0.5
            if horiz:
                spans = sorted((min(float(l["start_x"]), float(l["end_x"])), max(float(l["start_x"]), float(l["end_x"])),
                                float(l["start_y"])) for l in mem)
                ax_lo = min(s[0] for s in spans)
                ax_hi = max(s[1] for s in spans)
                pos = lambda x, y: x  # noqa: E731
            else:
                spans = sorted((min(float(l["start_y"]), float(l["end_y"])), max(float(l["start_y"]), float(l["end_y"])),
                                float(l["start_x"])) for l in mem)
                ax_lo = min(s[0] for s in spans)
                ax_hi = max(s[1] for s in spans)
                pos = lambda x, y: y  # noqa: E731
            # gaps along the axis between the union of member spans
            merged = []
            for lo, hi, _c in spans:
                if merged and lo <= merged[-1][1] + 0.6:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])
            gaps = [(merged[i][1], merged[i + 1][0]) for i in range(len(merged) - 1)]
            gap_len = [b - a for a, b in gaps]
            # ports on the key: contacts projected on the axis
            ports = {}
            for p in ports_by_file.get(fid, []):
                for c in G.contacts_of(p):
                    h = str(c.get("wire_handle") or "")
                    if h and G.wire_key(proj, fid, h) == k:
                        ports[p["record_id"]] = (p, float(c["x"]), float(c["y"]))
            cats = Counter((p.get("category") or "") for p, _, _ in ports.values())
            port_axis = sorted(pos(x, y) for _, x, y in ports.values())
            gap_split = 0
            for a, b in gaps:
                left = [v for v in port_axis if v <= a + 1e-6]
                right = [v for v in port_axis if v >= b - 1e-6]
                if left and right:
                    gap_split += 1
            tf = texts_by_file.get(fid)
            tx = tf.insert_x.to_numpy(float) if tf is not None else np.array([])
            ty = tf.insert_y.to_numpy(float) if tf is not None else np.array([])
            gap_text = 0
            for a, b in gaps:
                if len(tx):
                    if horiz:
                        inside = (tx >= a - 0.5) & (tx <= b + 0.5) & (np.abs(ty - mem[0]["start_y"]) <= 6.0)
                    else:
                        inside = (ty >= a - 0.5) & (ty <= b + 0.5) & (np.abs(tx - mem[0]["start_x"]) <= 6.0)
                    gap_text += int(inside.any())
            dd = dots[(dots.project == proj.pid) & (dots.file_id == fid)]
            dd_xy = dd[["x", "y"]].to_numpy(float) if len(dd) else np.zeros((0, 2))
            dots_at_ports = 0
            for _, x, y in ports.values():
                if len(dd_xy) and (np.hypot(dd_xy[:, 0] - x, dd_xy[:, 1] - y) <= DOT_TOL).any():
                    dots_at_ports += 1
            dots_at_gaps = 0
            for a, b in gaps:
                mid = (a + b) / 2
                for dx, dy in dd_xy:
                    v = dx if horiz else dy
                    off = dy if horiz else dx
                    if a - 0.6 <= v <= b + 0.6 and abs(off - (mem[0]["start_y"] if horiz else mem[0]["start_x"])) <= 6.0:
                        dots_at_gaps += 1
                        break
            rows.append({
                "subset": r["subset"], "project": proj.pid, "file_id": fid, "port_id": r["port_id"],
                "wire_key": str(k), "axis": "horizontal" if horiz else "vertical", "n_members": len(mem),
                "n_gaps": len(gaps), "max_gap": max(gap_len) if gap_len else 0.0, "gap_text": gap_text,
                "gap_split_ports": gap_split, "n_ports": len(ports), "port_cats": json.dumps(dict(cats), ensure_ascii=False),
                "dots_at_ports": dots_at_ports, "dots_at_gaps": dots_at_gaps,
                "run_lo": ax_lo, "run_hi": ax_hi, "run_cross": float(mem[0]["start_y"] if horiz else mem[0]["start_x"]),
                "port_axis": json.dumps([round(v, 2) for v in port_axis]),
                "dxf": r["dxf"], "contact_x": float(r["contact_x"]), "contact_y": float(r["contact_y"]),
            })
    frame = pd.DataFrame(rows)
    frame.to_parquet(work / "gap2_detail.parquet", index=False)
    summ = {
        "n": {k: int(v) for k, v in Counter(frame.subset).items()},
        "axis": {f"{k[0]}|{k[1]}": int(v) for k, v in Counter(zip(frame.subset, frame.axis)).items()},
        "n_members": {f"{k[0]}|{k[1]}": int(v) for k, v in Counter(zip(frame.subset, frame.n_members.clip(upper=6))).items()},
        "n_gaps": {f"{k[0]}|{k[1]}": int(v) for k, v in Counter(zip(frame.subset, frame.n_gaps.clip(upper=4))).items()},
        "gap_text_any": {k: int(v) for k, v in Counter(zip(frame.subset, frame.gap_text > 0)).items() for k in [f"{k[0]}|{k[1]}"]},
        "gap_split_any": {f"{k[0]}|{k[1]}": int(v) for k, v in Counter(zip(frame.subset, frame.gap_split_ports > 0)).items()},
        "dots_at_ports_any": {f"{k[0]}|{k[1]}": int(v) for k, v in Counter(zip(frame.subset, frame.dots_at_ports > 0)).items()},
        "dots_at_gaps_any": {f"{k[0]}|{k[1]}": int(v) for k, v in Counter(zip(frame.subset, frame.dots_at_gaps > 0)).items()},
    }
    (work / "gap2_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))


ROUND = G.ROUND


if __name__ == "__main__":
    main(Path(sys.argv[1]))
