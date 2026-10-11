"""PIN-1 step 4: DXF renders of sampled admission candidates (read-only).

Each sample is one PNG with a context panel and a close-up. Colours: red = the candidate pin marker (TERMPOINT
polyline of the pin number), green = the TERM_TEXT slot text linked to that pin, blue = the INSERT label text,
magenta = the terminal end of the record, orange = the record's wire end points.

Usage: python 02_render.py <sample_json> <out_dir> [index ...]
Writes <out_dir>/<sid>.png and <out_dir>/render_index.json (geometry facts for the judgement).
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path("F:/workspace/XJToolkit")
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"
R4 = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"


def load_r4():
    spec = importlib.util.spec_from_file_location("r4", str(R4))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dxf_map():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out = {}
    for p in man["projects"]:
        for f in p["files"]:
            out[(p["project_id"], f["file_id"])] = f["dxf_path"]
    return out


def xval(entity, app, code):
    if entity is None or not entity.xdata or app not in entity.xdata.data:
        return None
    vals = [t.value for t in entity.xdata.data[app] if t.code == code]
    return vals[0] if vals else None


def termpoint_segment(doc, insert, number):
    block = doc.blocks.get(insert.dxf.name)
    if block is None:
        return None
    m = insert.matrix44()
    for e in block:
        if e.dxftype() == "LWPOLYLINE" and e.xdata and "LD_SYMB1LIB_TERMPOINT" in e.xdata.data:
            if str(xval(e, "LD_SYMB1LIB_TERMPOINT", 1000)) == str(number):
                pts = [m.transform(p) for p in e.vertices_in_wcs()]
                if len(pts) >= 2:
                    return (pts[0].x, pts[0].y), (pts[-1].x, pts[-1].y)
    return None


def point_seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    vx, vy = bx - ax, by - ay
    den = vx * vx + vy * vy
    if not den:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / den))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def text_xy(doc, handle):
    e = doc.entitydb.get(handle) if handle else None
    if e is None:
        return None
    if e.dxftype() == "MTEXT":
        return float(e.dxf.insert.x), float(e.dxf.insert.y)
    if e.dxftype() in ("TEXT", "ATTRIB"):
        p = e.dxf.get("align_point") or e.dxf.insert
        return float(p.x), float(p.y)
    return None


def window_around(points, pad, min_size):
    xs = [p[0] for p in points if p is not None]
    ys = [p[1] for p in points if p is not None]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = max((x1 - x0), (y1 - y0), min_size) / 2
    return (cx - half, cy - half, cx + half, cy + half)


def geometry(doc, s):
    """Facts read straight from the DXF for one candidate. (None, reason) when it cannot be drawn."""
    ins = doc.entitydb.get(s["insert"])
    if ins is None or ins.dxftype() != "INSERT":
        return None, "insert_missing"
    if ins.dxf.owner != doc.modelspace().block_record_handle:
        return None, "nested_insert"
    seg = termpoint_segment(doc, ins, s["pin"])
    wire = doc.entitydb.get(s["wire"]) if s.get("wire") else None
    wire_pts = None
    if wire is not None and wire.dxftype() == "LINE":
        wire_pts = [(float(wire.dxf.start.x), float(wire.dxf.start.y)), (float(wire.dxf.end.x), float(wire.dxf.end.y))]
    term = doc.entitydb.get(s["term_insert"]) if s.get("term_insert") else None
    term_xy = (float(term.dxf.insert.x), float(term.dxf.insert.y)) if term is not None and term.dxftype() == "INSERT" else None
    slot_xy = text_xy(doc, xval(ins, f"LD_SYMB2_TERM_TEXT_{s['pin']}", 1005))
    label_xy = text_xy(doc, xval(ins, "LD_SYMB2_LABEL", 1005))
    wire_dist = min(point_seg_dist(p, seg[0], seg[1]) for p in wire_pts) if (seg and wire_pts) else None
    return dict(seg=seg, wire=wire_pts, term=term_xy, slot=slot_xy, label=label_xy, wire_dist=wire_dist), None


def main(sample_path, out_dir, only=None):
    samples = json.loads(Path(sample_path).read_text(encoding="utf-8"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dmap = dxf_map()
    r4 = load_r4()
    cache = r4.DxfCache()
    index = []
    for i, it in enumerate(samples):
        if only and i not in only:
            continue
        sid = it["sid"]
        dxf = dmap[(it["pid"], it["file"])]
        doc, _items, _ctx = cache.get(dxf)
        geo, skip = geometry(doc, it)
        rec = dict(sid=sid, pid=it["pid"], family=it["family"], file=it["file"], record=it["record"],
                   insert=it["insert"], pin=it["pin"], identity=it["identity"], label=it["label"], slot=it["slot"],
                   device=it["device"], seq=it["seq"], etype=it["etype"], term_identity=it["term_identity"],
                   wire=it["wire"], pair_id=it["pair_id"], skip=skip, png=None)
        if geo is None or geo["seg"] is None:
            rec["skip"] = skip or "no_marker"
            index.append(rec)
            print(sid, rec["skip"], flush=True)
            continue
        seg = geo["seg"]
        marker = ((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2)
        pts = [marker, seg[0], seg[1]] + ([geo["term"]] if geo["term"] else []) + (geo["wire"] or []) + \
              ([geo["label"]] if geo["label"] else []) + ([geo["slot"]] if geo["slot"] else [])
        ctx = window_around(pts, pad=14, min_size=40)
        close = window_around([marker, seg[0], seg[1]] + ([geo["slot"]] if geo["slot"] else []), pad=5, min_size=12)
        boxes = [(seg[0][0] - 0.4, seg[0][1] - 0.4, seg[0][0] + 0.4, seg[0][1] + 0.4, "red")]
        marks = [(marker[0], marker[1], "red")]
        if geo["slot"]:
            marks.append((geo["slot"][0], geo["slot"][1], "green"))
        if geo["label"]:
            marks.append((geo["label"][0], geo["label"][1], "blue"))
        if geo["term"]:
            marks.append((geo["term"][0], geo["term"][1], "magenta"))
        for p in geo["wire"] or []:
            marks.append((p[0], p[1], "orange"))
        head = [f"[{sid}] {it['pid']} {it['file']} {it['family']} | {it['identity']} (record {it['record'][-22:]})",
                f"候选身份 {it['identity']} | 标签 {it['label']} | 槽位文字 {it['slot']} | 脚号 {it['pin']} | 序号 {it['seq']} | 设备 {it['device']}",
                f"端子另一端 {it['term_identity']} | 导线句柄 {it['wire']} | 导线到标记距离 "
                f"{('%.2f' % geo['wire_dist']) if geo['wire_dist'] is not None else 'n/a'}"]
        p_ctx = r4.Panel(["上下文：红=脚号标记，绿=槽位文字，蓝=标签，洋红=端子，橙=导线端点"], dxf_path=dxf, window=ctx,
                         boxes=boxes, points=marks)
        p_close = r4.Panel(["近景：同一脚号标记"], dxf_path=dxf, window=close, boxes=boxes,
                           points=[(marker[0], marker[1], "red")] + ([(geo["slot"][0], geo["slot"][1], "green")] if geo["slot"] else []))
        fname = f"{sid}.png"
        r4._render_issue_png(out_dir / fname, head, [p_ctx, p_close], cache)
        rec.update(png=str(out_dir / fname), wire_dist=geo["wire_dist"], slot_present=geo["slot"] is not None,
                   label_present=geo["label"] is not None, term_present=geo["term"] is not None)
        index.append(rec)
        print(sid, fname, flush=True)
    (out_dir / "render_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], {int(x) for x in sys.argv[3:]} or None)
