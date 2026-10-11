"""PIN-S step 2: per-DXF geometry extraction (read-only), run in parallel over the frozen corpus.

For every symbol-like INSERT (LD_SYMB2_* or LDPARTLAYT_PART xdata; walked like superworks_semantics.walk)
record its TERMPOINT markers (LWPOLYLINE with LD_SYMB1LIB_TERMPOINT, world endpoints), TERMTEXTPOINT anchors
(LWPOLYLINE with LD_SYMB1LIB_TERMTEXTPOINT, 1005 -> marker), own-block TEXT/MTEXT/ATTRIB and INSERT attribs,
the LD_SYMB2_TERM_TEXT_n links, and for each marker the candidate texts (model space and own block) within R
with marker-local coordinates (u along the pin, w across it) and an ambiguity record per candidate.
Model-space texts are scanned once per file.

Output: .tmp/pin_s_work/geom/<pid>_<fid>.pkl (one dict per DXF file).
Usage: python -X utf8 02_geom.py <all18.pkl> [workers]
"""
import math
import pickle
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import ezdxf
from ezdxf.math import Matrix44, Vec3

R_CAND = 9.0  # candidate radius (drawing units) around a marker segment, plus text height
OUT = Path("F:/workspace/XJToolkit/.tmp/pin_s_work/geom")
SYM_PREFIXES = ("LD_SYMB2_", "LDPARTLAYT_PART")


def text_value(e):
    t = e.dxftype()
    rot = float(getattr(e.dxf, "rotation", 0.0) or 0.0)
    if t == "MTEXT":
        return e.plain_text(), float(e.dxf.char_height or 0.0), (e.dxf.insert.x, e.dxf.insert.y), rot
    return e.dxf.text, float(e.dxf.height or 0.0), (e.dxf.insert.x, e.dxf.insert.y), rot


def xd_first(e, app, code=1000):
    if e is None or not e.xdata or app not in e.xdata.data:
        return None
    for c, v in e.xdata.data[app]:
        if c == code:
            return str(v)
    return None


def xd_link(e, app):
    """Last 1005 handle of an XDATA app."""
    if e is None or not e.xdata or app not in e.xdata.data:
        return None
    hs = [str(v) for c, v in e.xdata.data[app] if c == 1005]
    return hs[-1] if hs else None


def seg_point_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 1e-18:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def process(task):
    pid, fid, path = task
    out = {"pid": pid, "fid": fid, "path": path, "error": None}
    try:
        try:
            doc = ezdxf.readfile(path)
        except Exception:
            from ezdxf import recover
            doc, _ = recover.readfile(path)
        msp = doc.modelspace()
        mt = []  # model-space texts: (handle, value, x, y, height, rotation, layer)
        for e in msp:
            if e.dxftype() in ("TEXT", "MTEXT"):
                v, h, (x, y), rot = text_value(e)
                v = (v or "").strip()
                if v:
                    mt.append((e.dxf.handle, v, x, y, h, rot, e.dxf.layer))
        symbols = []

        def walk(entities, parent, path_, depth, chain):
            for insert in entities:
                if insert.dxftype() != "INSERT":
                    continue
                name = insert.dxf.name
                if name in chain or depth >= 32 or name not in doc.blocks:
                    continue
                instance = path_ + "/" + insert.dxf.handle
                world = insert.matrix44() @ parent
                is_sym = bool(insert.xdata) and any(a.startswith(SYM_PREFIXES) for a in insert.xdata.data)
                if is_sym:
                    special = xd_first(insert, "LD_SYMB2_SPECIAL")
                    label_h = xd_link(insert, "LD_SYMB2_LABEL") or xd_link(insert, "LDPARTLAYT_PARTLABEL_HANDLE")
                    term_links = {}
                    for app in insert.xdata.data:
                        if app.startswith("LD_SYMB2_TERM_TEXT_"):
                            term_links[app.removeprefix("LD_SYMB2_TERM_TEXT_")] = xd_link(insert, app)
                    own_texts = []
                    for att in insert.attribs:
                        v = (att.dxf.text or "").strip()
                        if v:
                            p = world.transform(Vec3(att.dxf.insert.x, att.dxf.insert.y, 0))
                            own_texts.append({"h": att.dxf.handle, "v": v, "x": p.x, "y": p.y,
                                              "ht": float(att.dxf.height or 0), "kind": "ATTRIB_INSERT"})
                    markers, anchors = [], []
                    for e in doc.blocks[name]:
                        t = e.dxftype()
                        if t == "LWPOLYLINE" and e.xdata:
                            if "LD_SYMB1LIB_TERMPOINT" in e.xdata.data:
                                pts = [world.transform(Vec3(p[0], p[1], 0)) for p in e.get_points()]
                                if len(pts) < 2:
                                    continue
                                a, b = pts[0], pts[-1]
                                markers.append({"instance": instance, "insert": insert.dxf.handle, "block": name,
                                                "category": special, "marker": e.dxf.handle,
                                                "number": xd_first(e, "LD_SYMB1LIB_TERMPOINT"),
                                                "tp_link": xd_link(e, "LD_SYMB1LIB_TERMPOINT"),
                                                "ax": a.x, "ay": a.y, "bx": b.x, "by": b.y,
                                                "termautodim": xd_first(e, "LD_SYMB_TERMAUTODIM")})
                            if "LD_SYMB1LIB_TERMTEXTPOINT" in e.xdata.data:
                                pts = [world.transform(Vec3(p[0], p[1], 0)) for p in e.get_points()]
                                if pts:
                                    anchors.append({"anchor": e.dxf.handle, "link": xd_link(e, "LD_SYMB1LIB_TERMTEXTPOINT"),
                                                    "cx": sum(p.x for p in pts) / len(pts),
                                                    "cy": sum(p.y for p in pts) / len(pts)})
                        elif t in ("TEXT", "MTEXT", "ATTRIB"):
                            v, h, (x, y), _rot = text_value(e)
                            v = (v or "").strip()
                            if v:
                                p = world.transform(Vec3(x, y, 0))
                                own_texts.append({"h": e.dxf.handle, "v": v, "x": p.x, "y": p.y, "ht": h, "kind": t})
                    org = world.transform(Vec3(0, 0, 0))
                    symbols.append({"instance": instance, "insert": insert.dxf.handle, "block": name,
                                    "category": special, "label_h": label_h, "term_links": term_links,
                                    "own_texts": own_texts, "anchors": anchors, "markers": markers,
                                    "ix": org.x, "iy": org.y,
                                    "xdata_apps": sorted(insert.xdata.data.keys())})
                walk(doc.blocks[name], world, instance, depth + 1, (*chain, name))

        walk(msp, Matrix44(), "", 0, ())

        # candidate search for each marker (model texts once per file; own-block texts per symbol)
        all_markers = [(m["instance"], m["marker"], m["ax"], m["ay"], m["bx"], m["by"])
                       for s in symbols for m in s["markers"]]
        for s in symbols:
            for m in s["markers"]:
                ax, ay, bx, by = m["ax"], m["ay"], m["bx"], m["by"]
                L = math.hypot(bx - ax, by - ay)
                ang = math.atan2(by - ay, bx - ax) if L > 1e-9 else 0.0
                mx, my = (ax + bx) / 2, (ay + by) / 2
                cm = []
                for h, v, x, y, ht, rot, layer in mt:
                    if abs(x - mx) > R_CAND + ht + L or abs(y - my) > R_CAND + ht + L:
                        continue
                    d = seg_point_dist(x, y, ax, ay, bx, by)
                    if d <= R_CAND + ht:
                        cm.append({"src": "model", "h": h, "v": v, "x": x, "y": y, "ht": ht, "rot": rot, "layer": layer,
                                   "dist": d, "u": (x - mx) * math.cos(ang) + (y - my) * math.sin(ang),
                                   "w": -(x - mx) * math.sin(ang) + (y - my) * math.cos(ang)})
                for t in s["own_texts"]:
                    d = seg_point_dist(t["x"], t["y"], ax, ay, bx, by)
                    if d <= R_CAND + t["ht"]:
                        cm.append({"src": "block", "kind": t["kind"], "h": t["h"], "v": t["v"], "x": t["x"], "y": t["y"],
                                   "ht": t["ht"], "rot": None, "layer": None, "dist": d,
                                   "u": (t["x"] - mx) * math.cos(ang) + (t["y"] - my) * math.sin(ang),
                                   "w": -(t["x"] - mx) * math.sin(ang) + (t["y"] - my) * math.cos(ang)})
                cm.sort(key=lambda c: c["dist"])
                cm = cm[:16]
                # ambiguity: how many other markers of this file lie within the same reach of the text
                for c in cm:
                    best = []
                    for (ins, mh, mx_a, my_a, mx_b, my_b) in all_markers:
                        d = seg_point_dist(c["x"], c["y"], mx_a, my_a, mx_b, my_b)
                        if d <= R_CAND + c["ht"]:
                            best.append((d, ins, mh))
                    best.sort()
                    own = (m["instance"], m["marker"])
                    rank = next((i for i, (_, ins, mh) in enumerate(best) if (ins, mh) == own), None)
                    second = next((d for d, ins, mh in best if (ins, mh) != own), None)
                    c["rank_marker"] = rank
                    c["n_markers_within"] = len(best)
                    c["second_marker_dist"] = second
                m["cands"] = cm
                m["ang"] = ang
                m["L"] = L
                m["mid"] = (mx, my)
        out["symbols"] = symbols
        out["model_texts"] = mt
        out["n_markers"] = len(all_markers)
    except Exception as exc:
        out["error"] = repr(exc)[:300] + " " + traceback.format_exc()[-400:]
    return out


def main():
    all18 = Path(sys.argv[1])
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    D = pickle.load(open(all18, "rb"))
    tasks = [(pid, fid, path) for (pid, fid), path in sorted(D["dxf"].items())]
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(process, tasks, chunksize=2):
            key = f"{res['pid']}_{res['fid']}"
            with open(OUT / f"{key}.pkl", "wb") as fh:
                pickle.dump(res, fh)
            done += 1
            if res.get("error"):
                print("ERR", key, res["error"][:200], flush=True)
            if done % 100 == 0:
                print("done", done, round(time.time() - t0), flush=True)
    print("finished", done, round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
