"""PIN-ID step 3: stratified visual sample of candidate pin identities (read-only DXF rendering).

Strata (sources x project family):
  A  Pop-X, rule R1 (slot text agrees with LOGGEN seq, unique, not contradicted by strip row)  -> accept candidate
  B  Pop-X, R3 (LOGGEN seq only, no slot text)                                               -> review
  C  Pop-X, strip row disagrees (wire-linked terminal row)                                     -> error-form probe
  D  Pop-S, K_num = label + TERMPOINT port number, wired to an identified terminal             -> rejected source
Each sample is rendered as one PNG with a context panel and a close-up panel. The judgement is made by a person
from the image and recorded in judgements.json (tools/06_judgements.py merges it into details.json).

Usage: python 05_sample_render.py <all.pkl> <pop_x.pkl> <pop_s.pkl> <out_dir_pin_id> <scratch_dir>
"""
import collections
import importlib.util
import json
import math
import os
import pickle
import random
import sys
from pathlib import Path

import ezdxf

ROOT = Path("F:/workspace/XJToolkit")
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"
R4 = ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"
SEED = 20261011
N_A, N_B, N_C, N_D = 26, 6, 5, 9
N_A_EXTRA = 20
FAMILY_SHORT = {"正式典设": "zhengshi", "N2604": "n2604"}


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
    """Return WCS endpoints (a, b) of the library TERMPOINT polyline numbered `number` in the insert's block."""
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


def find_model_insert(doc, handle):
    e = doc.entitydb.get(handle)
    if e is not None and e.dxftype() == "INSERT":
        return e
    return None


def text_xy(doc, handle):
    """Anchor of a TEXT/MTEXT/ATTRIB entity, or None when the handle is absent or not a text."""
    e = doc.entitydb.get(handle) if handle else None
    if e is None:
        return None
    if e.dxftype() == "MTEXT":
        return float(e.dxf.insert.x), float(e.dxf.insert.y)
    if e.dxftype() in ("TEXT", "ATTRIB"):
        p = e.dxf.get("align_point") or e.dxf.insert
        return float(p.x), float(p.y)
    return None


def pop_x_geometry(doc, s):
    ins = find_model_insert(doc, s["insert"])
    if ins is None:
        return None
    seg = termpoint_segment(doc, ins, s["pin"])
    lab_h = xval(ins, "LD_SYMB2_LABEL", 1005)
    tt_h = xval(ins, f"LD_SYMB2_TERM_TEXT_{s['pin']}", 1005)
    wire = doc.entitydb.get(s["wire"]) if s["wire"] else None
    wire_pts = None
    if wire is not None and wire.dxftype() == "LINE":
        wire_pts = [(float(wire.dxf.start.x), float(wire.dxf.start.y)), (float(wire.dxf.end.x), float(wire.dxf.end.y))]
    term = find_model_insert(doc, s["other_insert"]) if s.get("other_insert") else None
    term_xy = (float(term.dxf.insert.x), float(term.dxf.insert.y)) if term is not None else None
    lab_xy = text_xy(doc, lab_h)
    tt_xy = text_xy(doc, tt_h)
    return dict(seg=seg, label=lab_xy, term_text=tt_xy, wire=wire_pts, term=term_xy,
                insert_xy=(float(ins.dxf.insert.x), float(ins.dxf.insert.y)))


def pop_s_geometry(doc, s):
    """Pop-S: same geometry as Pop-X, read from the page; the marker is the TERMPOINT polyline of the port number."""
    ins = find_model_insert(doc, s["insert"])
    if ins is None:
        return None
    seg = termpoint_segment(doc, ins, s["port"])
    lab_h = xval(ins, "LD_SYMB2_LABEL", 1005)
    wire = doc.entitydb.get(s["wire"]) if s.get("wire") else None
    wire_pts = None
    if wire is not None and wire.dxftype() == "LINE":
        wire_pts = [(float(wire.dxf.start.x), float(wire.dxf.start.y)), (float(wire.dxf.end.x), float(wire.dxf.end.y))]
    term = find_model_insert(doc, s["other_insert"]) if s.get("other_insert") else None
    return dict(seg=seg, label=text_xy(doc, lab_h), term_text=None, wire=wire_pts,
                term=(float(term.dxf.insert.x), float(term.dxf.insert.y)) if term is not None else None,
                insert_xy=(float(ins.dxf.insert.x), float(ins.dxf.insert.y)))


def window_around(points, pad, min_size):
    xs = [p[0] for p in points if p is not None]
    ys = [p[1] for p in points if p is not None]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = max((x1 - x0), (y1 - y0), min_size) / 2
    return (cx - half, cy - half, cx + half, cy + half)


def main(all_pkl, popx_pkl, pops_pkl, out_dir, scratch):
    out_dir = Path(out_dir)
    png_dir = out_dir / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    D = pickle.load(open(all_pkl, "rb"))
    T, FAM = D["tables"], D["family"]
    pop_x = pickle.load(open(popx_pkl, "rb"))
    pop_s = pickle.load(open(pops_pkl, "rb"))
    dmap = dxf_map()
    r4 = load_r4()
    cache = r4.DxfCache()
    rng = random.Random(SEED)

    # --- strata
    dup_partner = collections.defaultdict(set)
    for x in pop_x:
        if x["k_rec"] and x["term_partner"]:
            dup_partner[(x["pid"], x["k_rec"].casefold())].add(x["other_identity"])
    # Only model-space symbols are sampled: their geometry is read straight from the page (no block nesting).
    A = [x for x in pop_x if x["model_owner"] and x["k_agree"] and x["term_partner"]
         and len(dup_partner[(x["pid"], x["k_rec"].casefold())]) <= 1
         and x["row_check"] not in ("disagree_same_device_other_pin", "disagree_device_absent")]
    B = [x for x in pop_x if x["model_owner"] and (not x["slot_exists"]) and x["k_rec"] and x["term_partner"]]
    C = [x for x in pop_x if x["model_owner"] and x["row_check"] in ("disagree_same_device_other_pin", "disagree_device_absent")]
    Dp = [x for x in pop_s if x["model_owner"] and x["partner_identity"] and x["label_ok"] and x["has_wire"]]

    def stratified(items, n, key):
        """Draw n items spread over families in proportion to their size, at least one per family present."""
        by = collections.defaultdict(list)
        for it in items:
            by[key(it)].append(it)
        total = sum(len(v) for v in by.values())
        picks = []
        for fam in sorted(by, key=lambda f: -len(by[f])):
            k = max(1, round(n * len(by[fam]) / total)) if total else 0
            picks.extend(rng.sample(by[fam], min(k, len(by[fam]))))
        rng.shuffle(picks)
        return picks[:n]

    samples = []
    if os.environ.get("EXTRA_A"):
        # Second draw for stratum A (new seed, excluding the first draw), so the A precision rests on more cases.
        prev = json.loads((out_dir / "samples.json").read_text(encoding="utf-8"))
        taken = {(r["pid"], r["file"], r["insert"], str(r["pin"])) for r in prev if r.get("stratum") == "A"}
        pool = [x for x in A if (x["pid"], x["file"], x["insert"], str(x["pin"])) not in taken]
        rng = random.Random(SEED + 1)
        picks = stratified(pool, N_A_EXTRA, lambda x: x["family"])
        for i, it in enumerate(picks, 1):
            samples.append(dict(stratum="A2", idx=i, src=it, pool=len(pool)))
    else:
        for name, pool, n, keyf in (("A", A, N_A, lambda x: x["family"]), ("B", B, N_B, lambda x: x["family"]),
                                    ("C", C, N_C, lambda x: x["family"]), ("D", Dp, N_D, lambda x: x["family"])):
            picks = stratified(pool, n, keyf)
            for i, it in enumerate(picks, 1):
                samples.append(dict(stratum=name, idx=i, src=it, pool=len(pool)))

    # --- render
    results = []
    for s in samples:
        it = s["src"]
        pid = it["pid"]
        dxf = dmap[(pid, it["file"])]
        doc, _items, _ctx = cache.get(dxf)
        if s["stratum"][0] in ("A", "B", "C"):
            geo = pop_x_geometry(doc, dict(insert=it["insert"], pin=it["pin"], wire=it["wire"],
                                           other_insert=it.get("other_insert")))
            port_key = f"{it['insert']}:{it['pin']}"
            ident_k = it["k_rec"]
            title_src = f"Pop-X (dropped SYMB2 symbol) | LOGGEN {it['record']} | wire {it['wire']}"
            term_id = it["other_identity"]
            label_text = it["scan_label"]
            slot_text = it["slot_text"]
            seq = it["seq"]
            dev = it["device"]
            row_check = it["row_check"]
        else:
            geo = pop_s_geometry(doc, dict(insert=it["insert"], port=it["port"],
                                           wire=(it["wire"][0] if it["wire"] else None),
                                           other_insert=it.get("partner_insert")))
            port_key = f"{it['insert']}:{it['port']}"
            ident_k = it["k_num"]
            title_src = f"Pop-S (SW internal port, no identity) | wire {','.join(str(w) for w in it['wire'])}"
            term_id = it["partner_identity"]
            label_text = it["label"]
            slot_text = None
            seq = None
            dev = None
            row_check = None
        seg = geo.get("seg") if geo else None
        if seg is None:
            results.append(dict(stratum=s["stratum"], idx=s["idx"], file=it["file"], pid=pid, status="no_marker"))
            continue
        marker_mid = ((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2)
        wire_dist = None
        if geo.get("wire"):
            wire_dist = min(point_seg_dist(p, seg[0], seg[1]) for p in geo["wire"])
        pts = [marker_mid, seg[0], seg[1]]
        if geo.get("term"):
            pts.append(geo["term"])
        if geo.get("wire"):
            pts.extend(geo["wire"])
        if geo.get("label"):
            pts.append(geo["label"])
        ctx = window_around(pts, pad=14, min_size=40)
        close = window_around([marker_mid, seg[0], seg[1]] + ([geo["term_text"]] if geo.get("term_text") else []), pad=5, min_size=12)
        boxes_ctx = [(seg[0][0] - 0.4, seg[0][1] - 0.4, seg[0][0] + 0.4, seg[0][1] + 0.4, "red")]
        marks_ctx = [(marker_mid[0], marker_mid[1], "red")]
        if geo.get("term_text"):
            marks_ctx.append((geo["term_text"][0], geo["term_text"][1], "green"))
        if geo.get("label"):
            marks_ctx.append((geo["label"][0], geo["label"][1], "blue"))
        if geo.get("term"):
            marks_ctx.append((geo["term"][0], geo["term"][1], "magenta"))
        for p in geo.get("wire") or []:
            marks_ctx.append((p[0], p[1], "orange"))
        head = [f"[{s['stratum']}{s['idx']}] {pid} {it['file']} {FAM.get(pid)} | stratum {s['stratum']} (pool {s['pool']})",
                f"{title_src}",
                f"候选身份 {ident_k} | 标签 {label_text} | 脚号(TERMPOINT) {it['pin'] if s['stratum'][0] in 'ABC' else it['port']} | 槽位文字 {slot_text} | 序号 {seq} | 设备 {dev}",
                f"端子另一端身份 {term_id} | 端子排行一致性 {row_check} | 导线到标记距离 {('%.2f' % wire_dist) if wire_dist is not None else 'n/a'}"]
        p_ctx = r4.Panel(["上下文窗口：红=脚号标记(TERMPOINT)，绿=脚号文字链接，蓝=标签，洋红=端子，橙=导线端点"],
                         dxf_path=dxf, window=ctx, boxes=boxes_ctx, points=marks_ctx)
        p_close = r4.Panel(["近景：同一脚号标记"], dxf_path=dxf, window=close,
                           boxes=boxes_ctx, points=[(marker_mid[0], marker_mid[1], "red")] +
                           ([(geo["term_text"][0], geo["term_text"][1], "green")] if geo.get("term_text") else []))
        fname = f"{s['stratum']}{s['idx']:02d}_{pid}_{it['file']}_{port_key.replace(':', '-')}.png"
        r4._render_issue_png(png_dir / fname, head, [p_ctx, p_close], cache)
        results.append(dict(stratum=s["stratum"], idx=s["idx"], pid=pid, family=FAM.get(pid), file=it["file"],
                            png=f"png/{fname}", ident=ident_k, label=label_text, pin=(it.get("pin") if s["stratum"][0] in "ABC" else it.get("port")),
                            slot=slot_text, seq=seq, device=dev, term_identity=term_id, row_check=row_check,
                            wire=(it.get("wire")),
                            record=it.get("record"), insert=it["insert"], wire_marker_distance=wire_dist,
                            term_text_present=bool(geo.get("term_text")), status="rendered"))
        print(s["stratum"], s["idx"], pid, fname, flush=True)
    if os.environ.get("EXTRA_A"):
        results = prev + results
    (scratch / "samples.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "samples.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("rendered", sum(1 for r in results if r.get("status") == "rendered"), "of", len(results))


if __name__ == "__main__":
    main(*sys.argv[1:6])
