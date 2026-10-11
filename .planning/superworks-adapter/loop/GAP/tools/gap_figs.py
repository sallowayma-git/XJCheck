"""GAP visual samples (read-only): stratified draw per class, two-panel DXF renders with geometry overlays.

Classes and strata (seeded, reproducible):
  G1T   GAP-1 wire ends on the interior of another wire (line_tee), strata = other SW ports in the same net (0,1,2,3+)
  G1P   GAP-1 wire ends on a pin vertex of an unregistered SYMB2 block (pin_touch), strata = label status
  G1F   GAP-1 wire end with no body block (frame or free) or a near miss, strata = far class
  G2A   GAP-2a run (internal element + device terminals), strata = gap text present x member count
  G2B   GAP-2b run (device terminals only), strata = gap text present x member count

Panels per sample: a wide context window and a tight window (around the far end for G1, the gap for G2).
Overlays: contact wire / run members (blue; green for the second member), port markers (blue squares), far end (red),
T-line (orange), block pin geometry (magenta), gap centre (red cross), texts inside the window (green).

Outputs: <out>/samples.json and <out>/png/GAP_<class>_<nn>.png (three samples per sheet).
Usage: python gap_figs.py <gap_work_dir> <out_dir>
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import ezdxf
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gaplib as G  # noqa: E402
import gap_render as R  # noqa: E402

SEED = 20261011
PER_SHEET = 3
TOL = 0.6
DOC_CACHE: dict = {}


def pick(frame: pd.DataFrame, strata: list[str], total: int, rng: random.Random) -> pd.DataFrame:
    groups = defaultdict(list)
    for idx, key in zip(frame.index, zip(*[frame[s].astype(str) for s in strata])):
        groups[key].append(idx)
    keys = sorted(groups, key=lambda k: (-len(groups[k]), str(k)))
    for k in keys:
        rng.shuffle(groups[k])
    picked = []
    while len(picked) < total and any(groups.values()):
        for k in keys:
            if groups[k] and len(picked) < total:
                picked.append(groups[k].pop())
    return frame.loc[picked]


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy or 1e-12
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def get_doc(path):
    if path not in DOC_CACHE:
        DOC_CACHE.clear()
        DOC_CACHE[path] = ezdxf.readfile(path)
    return DOC_CACHE[path]


class Ctx:
    """Per-project lookups: top lines by file, texts by file, ports by key."""

    def __init__(self, pid):
        proj = next(G.iter_projects(only=[pid]))
        self.proj = proj
        self.top = proj.lines[proj.lines.source_block_name.map(lambda v: not G.text(v))]
        self.texts = {fid: t for fid, t in proj.texts.groupby("file_id")}
        self.ports = proj.ports.to_dict("records")


_CTX: dict = {}


def ctx_for(pid):
    if pid not in _CTX:
        _CTX.clear()
        _CTX[pid] = Ctx(pid)
    return _CTX[pid]


def g1_build(row, work):
    c = ctx_for(row["project"])
    fid = row["file_id"]
    cx, cy = float(row["contact_x_x"]), float(row["contact_y_x"])
    fx, fy = float(row["far_x"]), float(row["far_y"])
    segs = [(cx, cy, fx, fy, "#1f4fd1", 2.4)]
    pts = [(cx, cy, "#1f4fd1"), (fx, fy, "#d11f1f")]
    notes = []
    tops = c.top[c.top.file_id == fid]
    if row["far_class"] in ("line_tee", "line_joint"):
        for r in tops.itertuples():
            if str(r.handle) == str(row["wire_handle"]):
                continue
            x0, y0, x1, y1 = float(r.start_x), float(r.start_y), float(r.end_x), float(r.end_y)
            if seg_dist(fx, fy, x0, y0, x1, y1) <= TOL or min(math.hypot(x0 - fx, y0 - fy), math.hypot(x1 - fx, y1 - fy)) <= TOL:
                segs.append((x0, y0, x1, y1, "#e07b00", 2.2))
                notes.append(f"他线 {r.handle} 接于本端末端")
    if row["sub"] == "pin_touch" and isinstance(row.get("best_handle"), str) and row["best_handle"]:
        doc = get_doc(row["dxf"])
        ins = doc.entitydb.get(row["best_handle"])
        if ins is not None:
            for ent in ins.virtual_entities():
                if ent.dxftype() == "LINE":
                    a, b = ent.dxf.start, ent.dxf.end
                    if min(math.hypot(a.x - fx, a.y - fy), math.hypot(b.x - fx, b.y - fy)) <= 3.0:
                        segs.append((a.x, a.y, b.x, b.y, "#c71585", 2.2))
            notes.append(f"未登记块 {row['best_block']}")
    win_wide = R.window_around([(cx, cy), (fx, fy)], pad=12, min_size=40)
    win_tight = R.window_around([(cx, cy), (fx, fy)], pad=3.5, min_size=12)
    texts = []
    tf = c.texts.get(fid)
    if tf is not None:
        for t in tf.itertuples():
            if win_wide[0] <= float(t.insert_x) <= win_wide[2] and win_wide[1] <= float(t.insert_y) <= win_wide[3]:
                texts.append((float(t.insert_x), float(t.insert_y), str(t.text)[:12], "#0a8a3a"))
    title = [f"[{row['subset']} {row['far_class']} / {row['sub']}] {row['project']} 文件 {fid} 端子 {row['identity']} 标签 {row['label']}",
             f"导线 {row['wire_handle']}  远端 ({fx:.1f},{fy:.1f})  块 {row.get('best_block', '')}  " + "; ".join(notes)]
    p1 = R.Panel(title + ["宽视图"], row["dxf"], win_wide, segs=segs, pts=pts, texts=texts)
    p2 = R.Panel(["紧邻视图"], row["dxf"], win_tight, segs=segs, pts=pts, texts=texts)
    record = {"far_class": row["far_class"], "sub": row["sub"], "net_other_ports": row.get("n_other_ports"),
              "best_block": row.get("best_block", ""), "label_text": row.get("label_text", ""),
              "far_xy": [fx, fy], "contact_xy": [cx, cy], "wire_handle": row["wire_handle"]}
    return [p1, p2], {"title": f"{row['far_class']} {row['identity']}", "record": record}


def g2_build(row, work):
    c = ctx_for(row["project"])
    fid = row["file_id"]
    key = eval(row["wire_key"]) if str(row["wire_key"]).startswith("(") else row["wire_key"]
    mem = c.proj.members.get(key, [])
    horiz = row["axis"] == "horizontal"
    segs = []
    for i, m in enumerate(mem):
        colour = "#1f4fd1" if i % 2 == 0 else "#1a9b4b"
        segs.append((float(m["start_x"]), float(m["start_y"]), float(m["end_x"]), float(m["end_y"]), colour, 2.4))
    pts, gap_marks = [], []
    seen = set()
    for p in c.ports:
        if p["file_id"] != fid or p["record_id"] in seen:
            continue
        for con in G.contacts_of(p):
            h = str(con.get("wire_handle") or "")
            if h and G.wire_key(c.proj, fid, h) == key:
                seen.add(p["record_id"])
                cat = p.get("category") or ""
                colour = {"装置端子": "#1f4fd1", "端子": "#8a2be2", "内部元件": "#d1831f"}.get(cat, "#555555")
                for x, y in ((p["start_x"], p["start_y"]), (p["end_x"], p["end_y"])):
                    pts.append((float(x), float(y), colour))
                pts.append((float(con["x"]), float(con["y"]), colour))
                break
    lo, hi = float(row["run_lo"]), float(row["run_hi"])
    cross = float(row["run_cross"])
    gaps = []
    ms = sorted(((min(m["start_x"], m["end_x"]), max(m["start_x"], m["end_x"])) if horiz
                 else (min(m["start_y"], m["end_y"]), max(m["start_y"], m["end_y"]))) for m in mem)
    for (a1, b1), (a2, b2) in zip(ms, ms[1:]):
        if a2 - b1 > 0.6:
            gaps.append(((b1 + a2) / 2, (a2 - b1)))
    if horiz:
        gap_marks = [(g, cross, "#e0301e") for g, _ in gaps]
    else:
        gap_marks = [(float(row["contact_x"]), g, "#e0301e") for g, _ in gaps]
    if gaps:
        gc, gl = gaps[0]
        cxy = (gc, cross) if horiz else (cross, gc)
    else:
        cxy = (float(row["contact_x"]), float(row["contact_y"]))
        gl = 0.0
    win_wide = R.window_around([(lo, cross), (hi, cross)] if horiz else [(cross, lo), (cross, hi)], pad=10, min_size=40)
    win_tight = R.window_around([cxy], pad=7.0, min_size=16)
    texts, gap_text = [], []
    tf = c.texts.get(fid)
    if tf is not None:
        for t in tf.itertuples():
            tx, ty = float(t.insert_x), float(t.insert_y)
            if win_wide[0] <= tx <= win_wide[2] and win_wide[1] <= ty <= win_wide[3]:
                texts.append((tx, ty, str(t.text)[:14], "#0a8a3a"))
                if gaps and win_tight[0] <= tx <= win_tight[2] and win_tight[1] <= ty <= win_tight[3]:
                    gap_text.append(str(t.text))
    pts_draw = [(x, y, col) for x, y, col in pts] + [(x, y, "#e0301e") for x, y, _ in gap_marks]
    title = [f"[{row['subset']} 成员={len(mem)} 断口={len(gaps)} 文字桥接={'有' if row['gap_text'] else '无'}] "
             f"{row['project']} 文件 {fid}",
             f"断口宽 {gl:.2f}  端口类别 {row['port_cats']}  断口内文字 {gap_text or '无'}"]
    p1 = R.Panel(title + ["宽视图"], row["dxf"], win_wide, segs=segs, pts=pts_draw, texts=texts)
    p2 = R.Panel(["紧邻视图（断口）"], row["dxf"], win_tight, segs=segs, pts=pts_draw, texts=texts)
    record = {"n_members": len(mem), "gaps": [round(g[1], 2) for g in gaps], "gap_text": gap_text,
              "port_cats": row["port_cats"], "port_axis": row["port_axis"], "axis": row["axis"]}
    return [p1, p2], {"title": f"n={len(mem)} gap={gl:.2f} text={'Y' if gap_text else 'N'}", "record": record}


def main(work: Path, out: Path):
    (out / "png").mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    detail = pd.read_parquet(work / "gap1_detail.parquet")
    net = pd.read_parquet(work / "net_gap1.parquet")[["port_id", "project", "n_other_ports"]]
    det = detail.merge(net, on=["port_id", "project"], how="left")
    det["net_bin"] = det.n_other_ports.fillna(-1).clip(upper=3).astype(int).astype(str)
    det["label_status"] = np.where(det.label_text.fillna("") == "", "no_label", "label_equal")
    g1 = det[det.subset == "GAP1"]
    g2 = pd.read_parquet(work / "gap2_inner.parquet")
    g2["text_flag"] = (g2.gap_text > 0).map({True: "text", False: "notext"})
    g2["n_members_s"] = g2.n_members.clip(upper=6).astype(str)
    plan = [
        ("G1T", g1[g1.far_class == "line_tee"], ["net_bin"], 12, g1_build),
        ("G1P", g1[g1["sub"] == "pin_touch"], ["label_status"], 10, g1_build),
        ("G1F", g1[g1["sub"].isin(["no_body", "near_geom"])], ["far_class"], 10, g1_build),
        ("G2A", g2[g2.subset == "GAP2a"], ["text_flag", "n_members_s"], 10, g2_build),
        ("G2B", g2[g2.subset == "GAP2b"], ["text_flag", "n_members_s"], 10, g2_build),
    ]
    samples, sheet_no = [], 0
    for cls, frame, strata, total, builder in plan:
        sel = pick(frame, strata, total, rng)
        recs = sel.to_dict("records")
        for i in range(0, len(recs), PER_SHEET):
            chunk = recs[i:i + PER_SHEET]
            sheet_no += 1
            panels, header, batch = [], [], []
            for j, row in enumerate(chunk):
                pl, meta = builder(row, work)
                panels.extend(pl)
                sid = f"{cls}-{i + j + 1:02d}"
                header.append(f"{sid}  {meta['title']}  [{row['project']} {row['file_id']}]")
                batch.append({"sample": sid, "class": cls, "sheet": f"GAP_{cls}_{sheet_no:02d}.png",
                              "project": row["project"], "file_id": row["file_id"], "port_id": row["port_id"],
                              "identity": row.get("identity", ""), **meta["record"]})
            R.render(out / "png" / f"GAP_{cls}_{sheet_no:02d}.png", [f"GAP 目视样例 {cls}（每行一例：宽视图 | 紧邻视图）"] + header,
                     panels, cols=2)
            samples.extend(batch)
    (out / "samples.json").write_text(json.dumps(samples, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("samples", len(samples), "sheets", sheet_no)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
