"""Geometric net components of the top-level wires of each file (read-only).

Two wire segments are connected when an endpoint of one lies within TOL of an endpoint of the other (joint) or within
TOL of the interior of the other (T-junction). Every SW port contact is attached to the component of its contact line.
This is the electrical-net view that the line-group builder does not provide (it merges collinear runs only).

For every GAP-1 wire (uncovered device terminal, single-ended) the output records: the component size, the other SW
ports of the same component (with categories and identities), and whether the component reaches a port that is
already paired. Output: <work>/net_gap1.parquet, one row per GAP-1 wire.

Usage: python net_components.py <gap_work_dir>
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib as G  # noqa: E402

TOL = 0.6


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def build_components(ax, ay, bx, by):
    n = len(ax)
    uf = UF(n)
    for i in range(n):
        # endpoint-endpoint and endpoint-on-interior of segment j
        ex = np.array([ax[i], bx[i]])
        ey = np.array([ay[i], by[i]])
        for ep_x, ep_y in ((ax[i], ay[i]), (bx[i], by[i])):
            dx, dy = bx - ax, by - ay
            L2 = np.where(dx * dx + dy * dy == 0, 1e-12, dx * dx + dy * dy)
            t = np.clip(((ep_x - ax) * dx + (ep_y - ay) * dy) / L2, 0, 1)
            dist = np.hypot(ep_x - (ax + t * dx), ep_y - (ay + t * dy))
            hit = np.nonzero(dist <= TOL)[0]
            for j in hit:
                uf.union(i, int(j))
    return [uf.find(i) for i in range(n)]


def main(work: Path):
    u = pd.read_parquet(work / "uncovered.parquet")
    g1 = pd.read_parquet(work / "gap1_detail.parquet")[["port_id", "project", "subset", "far_class", "sub"]]
    cols = ["port_id", "project", "file_id", "wire_handle", "wire_key", "signature", "far_class"]
    target = g1.merge(u[["port_id", "project", "file_id", "wire_handle", "wire_key", "contact_x", "contact_y"]],
                      on=["port_id", "project"], how="left")
    out = []
    for proj in G.iter_projects(only=sorted(set(target.project))):
        top = proj.lines[proj.lines.source_block_name.map(lambda v: not G.text(v))]
        ports_by_file = defaultdict(list)
        for p in proj.ports.to_dict("records"):
            ports_by_file[p["file_id"]].append(p)
        for fid, lf in top.groupby("file_id"):
            ax = lf.start_x.to_numpy(float); ay = lf.start_y.to_numpy(float)
            bx = lf.end_x.to_numpy(float); by = lf.end_y.to_numpy(float)
            handles = lf.handle.astype(str).to_numpy()
            comp = build_components(ax, ay, bx, by)
            comp_of = {h: c for h, c in zip(handles, comp)}
            comp_ports = defaultdict(set)
            for p in ports_by_file.get(fid, []):
                for c in G.contacts_of(p):
                    h = str(c.get("wire_handle") or "")
                    if h in comp_of:
                        comp_ports[comp_of[h]].add(p["record_id"])
            rec_by_id = {p["record_id"]: p for p in ports_by_file.get(fid, [])}
            sub = target[(target.project == proj.pid) & (target.file_id == fid)]
            for r in sub.to_dict("records"):
                h = str(r["wire_handle"])
                if h not in comp_of:
                    out.append({**r, "comp_size": 0, "comp_ports": "[]", "n_other_ports": 0})
                    continue
                c = comp_of[h]
                others = sorted(comp_ports.get(c, set()) - {r["port_id"]})
                info = [{"port": o, "cat": rec_by_id[o].get("category"), "identity": G.text(rec_by_id[o].get("endpoint_identity"))}
                        for o in others if o in rec_by_id]
                out.append({**r, "comp_size": int(sum(1 for x in comp if x == c)), "comp_ports": json.dumps(info, ensure_ascii=False),
                            "n_other_ports": len(others)})
    frame = pd.DataFrame(out)
    frame.to_parquet(work / "net_gap1.parquet", index=False)
    print(frame.groupby(["subset", "far_class"]).size().to_string())
    print(frame.n_other_ports.value_counts().sort_index().head(10).to_string())


if __name__ == "__main__":
    main(Path(sys.argv[1]))
