"""MULTI-SEG: stratified DXF renders of refused split candidates (read-only; writes PNG only).

Each case: a wide panel (the whole line group with its outer ends) and a zoom on the candidate terminal body.
Overlays: each piece of the group in its own colour and width 2.2 (blue, orange, green, purple, brown, pink);
device terminal TERMPOINTs of the candidate pair (blue boxes, labelled a / b); other device terminal TERMPOINTs
(light blue); internal element pins (magenta); plain terminals (dark grey); unregistered block pins (green);
connect dots (red circles); model lines that cross a gap or touch the group, not members (grey dashed).
Usage: python ms_render.py SAMPLE_JSON PNG_DIR   (SAMPLE_JSON: list of {"index", "png", "case"} as written by ms_sample.py)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
GAP_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
sys.path.insert(0, str(GAP_TOOLS))

import ms_common as M  # noqa: E402
import ms_geom as G  # noqa: E402
import gap_render as R  # noqa: E402

COLOURS = ["#1f78b4", "#ff7f00", "#33a02c", "#6a3d9a", "#b15928", "#e7298a"]
CAT_COLOUR = {"端子": "#404040", "内部元件": "#e7298a", "线圈": "#e7298a", "接地": "#8c510a", "装置端子": "#56b4e9"}
UNREG = "#00a060"
DOT = "#d7191c"
GREY = "#9e9e9e"
MANIFEST = M.manifest_info()


def dxf_of(pid, fid):
    return MANIFEST[pid]["files"][fid]["dxf_path"]


def build_case_geometry(proj: M.Project, cand_index_by_key):
    """Re-enumerate the split candidates of one project (cheap, cached per project) and return a lookup."""
    cands, groups, roots, segments, model, dots = M.enumerate_split_candidates(proj)
    return cands, groups, roots, segments


def draw_case(ax_title, proj, geo, cand, groups, roots, segments, window, zoom=False):
    fid = cand["file_id"]
    keys = cand["keys"]
    segs, pts, boxes, texts = [], [], [], []
    pieces = G.piece_extents(keys, segments, cand["roots"])
    piece_of = {}
    for i, p in enumerate(pieces):
        colour = COLOURS[i % len(COLOURS)]
        for key in p["keys"]:
            piece_of[key] = i
            s = segments[key]
            segs.append((s["sx"], s["sy"], s["ex"], s["ey"], colour, 2.2))
    x0, y0, x1, y1 = window
    for port in proj.ports:
        if M.text(port.get("file_id")) != fid:
            continue
        coords = [M.DI._number(port.get(k)) for k in ("start_x", "start_y", "end_x", "end_y")]
        if None in coords:
            continue
        ax, ay, bx, by = coords
        if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1:
            continue
        cat = M.text(port.get("category"))
        colour = CAT_COLOUR.get(cat, GREY)
        mark = (M.text(port.get("record_id")) in (M.text(cand["port_a"]["record_id"]), M.text(cand["port_b"]["record_id"])))
        if mark:
            colour = "#1f3fd1"
        boxes.append((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), colour))
        if mark:
            texts.append((min(ax, bx), max(ay, by) + 0.3, "a" if M.text(port["record_id"]) == M.text(cand["port_a"]["record_id"]) else "b", "#1f3fd1"))
    for block in proj.unreg:
        if M.text(block.get("file_id")) != fid:
            continue
        for tp in M.jload(block.get("termpoints"), []):
            (ax, ay), (bx, by) = tuple(tp["a"]), tuple(tp["b"])
            if max(ax, bx) < x0 or min(ax, bx) > x1 or max(ay, by) < y0 or min(ay, by) > y1:
                continue
            boxes.append((min(ax, bx), min(ay, by), max(ax, bx), max(ay, by), UNREG))
    for d in proj.dots:
        if M.text(d.get("file_id")) != fid:
            continue
        x, y = M.DI._number(d.get("x")), M.DI._number(d.get("y"))
        if x is not None and x0 <= x <= x1 and y0 <= y <= y1:
            pts.append((x, y, DOT))
    for l in proj.lines:
        if M.text(l.get("file_id")) != fid or M.text(l.get("source_block_name")):
            continue
        if (fid, M.text(l["line_id"])) in set(keys):
            continue
        sx, sy, ex, ey = (M.DI._number(l.get(k)) for k in ("start_x", "start_y", "end_x", "end_y"))
        if None in (sx, sy, ex, ey):
            continue
        if max(sx, ex) < x0 or min(sx, ex) > x1 or max(sy, ey) < y0 or min(sy, ey) > y1:
            continue
        segs.append((sx, sy, ex, ey, GREY, 0.8))
    for t in proj.texts:
        pass  # DXF already draws the model text; overlay texts are added only for the piece indices below
    for i, p in enumerate(pieces):
        cx = (p["xmin"] + p["xmax"]) / 2
        texts.append((cx, p["y"] + 1.2, "P%d" % i, COLOURS[i % len(COLOURS)]))
    return {"segs": segs, "pts": pts, "boxes": boxes, "texts": texts, "pieces": pieces}


def panel_for(proj, geo, cand, groups, roots, segments, window, title):
    info = draw_case(title, proj, geo, cand, groups, roots, segments, window)
    lines = title.split("\n")
    return R.Panel(lines, dxf_of(proj.pid, cand["file_id"]), window, segs=info["segs"], pts=info["pts"],
                   boxes=info["boxes"], texts=info["texts"])


def main(sample_path: Path, png_dir: Path):
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    cache = {}
    for item in sample:
        pid = item["case"]["pid"]
        if pid not in cache:
            findings = next((M.ROUND / pid).glob("*/findings"))
            proj = M.Project(pid, findings)
            cands, groups, roots, segments, model, dots = M.enumerate_split_candidates(proj)
            cache[pid] = (proj, cands, groups, roots, segments)
    png_dir.mkdir(parents=True, exist_ok=True)
    for item in sample:
        pid = item["case"]["pid"]
        proj, cands, groups, roots, segments = cache[pid]
        cand = next(c for c in cands if c["reason"] == "components_not_two"
                    and c["line_group_id"] == item["case"]["line_group_id"]
                    and M.text(c["port_a"]["record_id"]) == item["case"]["port_a"]
                    and M.text(c["port_b"]["record_id"]) == item["case"]["port_b"])
        item["_cand"] = cand
    # render: two cases per PNG
    for png_name, cases in _pairs(sample):
        panels, header = [], []
        for item in cases:
            c = item["case"]
            cand = item["_cand"]
            proj, _cands, groups, roots, segments = cache[c["pid"]]
            keys = cand["keys"]
            pieces = G.piece_extents(keys, segments, cand["roots"])
            x_lo = min(p["xmin"] for p in pieces) - 14
            x_hi = max(p["xmax"] for p in pieces) + 14
            y = c["y"]
            wide = (x_lo, y - 12, x_hi, y + 12)
            ca, cb = cand["ca"], cand["cb"]
            zc = ((ca[0] + cb[0]) / 2, y)
            zoom = (zc[0] - 9, y - 9, zc[0] + 9, y + 9)
            geo = None
            head = "%s  %s  %s  %s" % (c["index_label"], c["pid"], c["sheet_id"], c["identity"])
            body = ["%s  pieces=%d  signature=%s" % (c["sig_label"], len(pieces), c["signature"]),
                    "line group %s  file %s  orient %s" % (c["line_group_id"], cand["file_id"], cand["orientation"])]
            panels.append(panel_for(proj, geo, cand, groups, roots, segments, wide, "\n".join([head] + body + ["wide view"])))
            panels.append(panel_for(proj, geo, cand, groups, roots, segments, zoom, "\n".join([head, "zoom on candidate body"])))
            header.append(head + "  " + c["sig_label"])
        R.render(png_dir / png_name, header, panels, cols=2)
        print("png", png_name, flush=True)


def _pairs(sample):
    for k in range(0, len(sample), 2):
        yield sample[k]["png"], sample[k:k + 2]


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
