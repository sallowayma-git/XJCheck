"""PIN-S step 6: render sample DXF windows (read-only) around Pop-S markers and truth markers.

Colours: grey = drawing; red = TERMPOINT marker of the sample; magenta = TERMTEXTPOINT anchor linked to it;
blue = device label (LD_SYMB2_LABEL); green = text chosen by the classifier; orange = other candidate texts
within the candidate radius; dark orange = wire entities touching the marker (replay wire handles).
Each panel is a 26 x 26 drawing-unit window; the close-up is 10 x 10.

Usage: python -X utf8 06_render.py <spec.json> <png_dir>
  spec.json: list of {"name","pid","fid","instance","marker","cls","note"}
"""
import json, math, pickle, sys, warnings
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
DXF = D["dxf"]


def window_items(msp, cx, cy, half):
    segs, texts, circles = [], [], []
    def add_entity(e, depth=0):
        t = e.dxftype()
        if t == "INSERT":
            if depth > 3:
                return
            try:
                for v in e.virtual_entities():
                    add_entity(v, depth + 1)
            except Exception:
                pass
            return
        try:
            if t == "LINE":
                s, en = e.dxf.start, e.dxf.end
                if min(s.x, en.x) > cx + half or max(s.x, en.x) < cx - half or min(s.y, en.y) > cy + half or max(s.y, en.y) < cy - half:
                    return
                segs.append(((s.x, s.y), (en.x, en.y), e.dxf.handle))
            elif t == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points()]
                if not pts:
                    return
                for (x, y) in pts:
                    if abs(x - cx) <= half and abs(y - cy) <= half:
                        break
                else:
                    return
                for a, b in zip(pts, pts[1:]):
                    segs.append((a, b, e.dxf.handle))
            elif t in ("ARC", "CIRCLE"):
                pts = list(e.flattening(0.2)) if t == "ARC" else list(e.flattening(0.2))
                if any(abs(p.x - cx) <= half and abs(p.y - cy) <= half for p in pts):
                    for a, b in zip(pts, pts[1:]):
                        segs.append(((a.x, a.y), (b.x, b.y), e.dxf.handle))
            elif t in ("TEXT", "MTEXT"):
                x, y = e.dxf.insert.x, e.dxf.insert.y
                if abs(x - cx) <= half and abs(y - cy) <= half:
                    val = e.plain_text() if t == "MTEXT" else e.dxf.text
                    h = e.dxf.char_height if t == "MTEXT" else e.dxf.height
                    texts.append((x, y, val, float(h or 2.5), e.dxf.handle))
        except Exception:
            pass

    for e in msp:
        if e.dxftype() == "INSERT":
            ix, iy = e.dxf.insert.x, e.dxf.insert.y
            if abs(ix - cx) > half + 60 or abs(iy - cy) > half + 60:
                continue
        add_entity(e)
    return segs, texts


def draw(spec, png_dir):
    key = (spec["pid"], spec["fid"])
    doc = ezdxf.readfile(DXF[key])
    msp = doc.modelspace()
    g = pickle.load(open(WORK / "geom" / f"{spec['pid']}_{spec['fid']}.pkl", "rb"))
    sym = None
    for s in g["symbols"]:
        if s["instance"] == spec["instance"]:
            sym = s
            break
    mk = None
    if sym:
        for m in sym["markers"]:
            if m["marker"] == spec["marker"]:
                mk = m
    if mk is None:
        return None
    cx, cy = (mk["ax"] + mk["bx"]) / 2, (mk["ay"] + mk["by"]) / 2
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6), dpi=110, gridspec_kw={"width_ratios": [1.1, 1]})
    for ax, half in zip(axes, (13.0, 5.0)):
        segs, texts = window_items(msp, cx, cy, half)
        lc = LineCollection([s[:2] for s in segs], colors="#777777", linewidths=0.6)
        ax.add_collection(lc)
        ax.set_xlim(cx - half, cx + half)
        ax.set_ylim(cy - half, cy + half)
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for (x, y, val, h, hh) in texts:
            ax.text(x, y, val, fontsize=max(5, min(9, h * 2.2)), color="#222222", ha="left", va="bottom")
        # wire contacts touching this marker
        wire_handles = set()
        for segment in segs:
            pass
        # overlays
        ax.plot([mk["ax"], mk["bx"]], [mk["ay"], mk["by"]], color="red", lw=2.6, solid_capstyle="butt", zorder=5)
        for h, ax_, ay_ in [(a[0], a[1], a[2]) for a in mk.get("anchors", [])] or []:
            pass
        for a in (sym.get("anchors") or []):
            if a.get("link") == mk["marker"]:
                ax.plot([a["cx"]], [a["cy"]], marker="s", ms=5, color="magenta", zorder=6)
        lbl = sym.get("label_h")
        for (x, y, val, h, hh) in texts:
            if hh == lbl:
                ax.text(x, y, val, fontsize=max(6, min(10, h * 2.4)), color="blue", ha="left", va="bottom", zorder=7)
        for c in mk["cands"][:6]:
            col = "#ff8c00"
            if spec.get("chosen") and c["h"] == spec.get("chosen"):
                col = "#00a040"
            ax.add_patch(Circle((c["x"], c["y"]), 0.25 * (half / 13 + 0.3), color=col, zorder=8))
            ax.text(c["x"], c["y"] + 0.6, c["v"], fontsize=8, color=col, zorder=9, fontweight="bold")
        for c in mk["cands"][:0]:
            pass
        title = f"{spec['name']} | {spec.get('cls','')} | blk {mk['block']} | no {mk['number']} | label {(spec.get('label') or '')}"
        ax.set_title(title if half > 6 else "close-up", fontsize=8 if half > 6 else 7)
    fig.text(0.01, 0.01, spec.get("note", "")[:220], fontsize=7)
    out = Path(png_dir) / f"{spec['name']}.png"
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(out)
    plt.close(fig)
    return str(out)


if __name__ == "__main__":
    specs = json.load(open(sys.argv[1], encoding="utf-8"))
    png_dir = Path(sys.argv[2]); png_dir.mkdir(parents=True, exist_ok=True)
    for s in specs:
        try:
            print(draw(s, png_dir), flush=True)
        except Exception as exc:
            print("ERR", s.get("name"), repr(exc)[:200], flush=True)
