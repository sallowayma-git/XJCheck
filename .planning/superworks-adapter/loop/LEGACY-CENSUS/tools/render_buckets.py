"""LEGACY-CENSUS step 3: render the 3 samples of each Top-10 bucket as one PNG (read-only; writes PNG only).

Panel overlays (DXF is drawn black on white from the frozen DXF in corpus_manifest.json):
  blue solid    legacy pair wire (left end -> right end)
  blue circle   legacy end point (text anchor when the end has no coordinate)
  magenta dot   text insert point of a legacy end
  orange        legacy line group of the pair (when the pair has one)
  red square    SuperWORKS port matched by text id on the same sheet (label: endpoint identity)
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from ezdxf.addons.drawing import Frontend  # noqa: E402
from ezdxf.addons.drawing.config import ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402
from ezdxf.addons.drawing.properties import RenderContext  # noqa: E402
import ezdxf  # noqa: E402

ROOT = "F:/workspace/XJToolkit"
WORK = os.path.join(ROOT, ".tmp/legacy_census_work")
PNG_DIR = os.path.join(ROOT, ".planning/superworks-adapter/loop/LEGACY-CENSUS/png")
os.makedirs(PNG_DIR, exist_ok=True)
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

_DOCS = {}


def load_doc(path):
    if path not in _DOCS:
        try:
            _DOCS[path] = ezdxf.readfile(path)
        except Exception:
            _DOCS[path] = ezdxf.recover.readfile(path)[0]
    return _DOCS[path]


def valid(xy):
    return xy and all(v is not None and v == v for v in xy)


def panel_points(s):
    pts = []
    if valid(s["left_xy"]):
        pts.append(s["left_xy"])
    if valid(s["right_xy"]):
        pts.append(s["right_xy"])
    for g in s["group_xy"]:
        pts += [[g[0], g[1]], [g[2], g[3]]]
    for a in s["sw_anchors"]:
        pts += [a["start"], a["end"]]
    for t in (s.get("text_anchors") or {}).values():
        pts.append(t["xy"])
    return pts


def draw_panel(ax, s):
    doc = load_doc(s["dxf"])
    msp = doc.modelspace()
    ctx = RenderContext(doc)
    config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
    Frontend(ctx, MatplotlibBackend(ax), config=config).draw_layout(msp, finalize=False)
    pts = panel_points(s)
    if not pts:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "no geometry", transform=ax.transAxes, ha="center")
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 9.0
    half = max(half, 18.0)
    x0, x1, y0, y1 = cx - half, cx + half, cy - half, cy + half
    span = x1 - x0
    mark = span * 0.012
    for g in s["group_xy"]:
        ax.plot([g[0], g[2]], [g[1], g[3]], color="#ff7f0e", lw=1.6, zorder=30)
    if valid(s["left_xy"]) and valid(s["right_xy"]):
        ax.plot([s["left_xy"][0], s["right_xy"][0]], [s["left_xy"][1], s["right_xy"][1]],
                color="#1f4fd1", lw=2.2, zorder=40)
    for side, xy in (("L", s["left_xy"]), ("R", s["right_xy"])):
        if valid(xy):
            ax.add_patch(plt.Circle((xy[0], xy[1]), mark * 0.9, fill=False, ec="#1f4fd1", lw=1.6, zorder=45))
            val = s["left_value"] if side == "L" else s["right_value"]
            ax.text(xy[0] + mark * 1.2, xy[1] + mark * 1.2, f"{side}:{val}", color="#1f4fd1", fontsize=7, zorder=60)
    for side, t in (s.get("text_anchors") or {}).items():
        x, y = t["xy"]
        ax.plot([x], [y], "o", color="#d62fbf", ms=3.5, zorder=50)
        ax.text(x + mark * 0.8, y - mark * 2.0, f"{side}:{t['text']}", color="#d62fbf", fontsize=6.5, zorder=60)
    for a in s["sw_anchors"]:
        mx, my = (a["start"][0] + a["end"][0]) / 2, (a["start"][1] + a["end"][1]) / 2
        ax.add_patch(Rectangle((mx - mark * 1.3, my - mark * 1.3), mark * 2.6, mark * 2.6, fill=False,
                               ec="#d62728", lw=1.6, zorder=55))
        ax.text(mx + mark * 1.6, my + mark * 1.6, f"SW {a['identity']}", color="#d62728", fontsize=6.5, zorder=60)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "raw"
    suffix = "" if mode == "raw" else "_d3"
    prefix = "bucket" if mode == "raw" else "d3"
    samples = json.load(open(os.path.join(WORK, f"samples{suffix}.json"), encoding="utf-8"))
    by_rank = {}
    for s in samples:
        by_rank.setdefault(s["rank"], []).append(s)
    index = []
    for rank in sorted(by_rank):
        group = sorted(by_rank[rank], key=lambda s: s["k"])
        fig, axes = plt.subplots(1, len(group), figsize=(5.4 * len(group), 5.0), dpi=100)
        if len(group) == 1:
            axes = [axes]
        head = group[0]
        fig.suptitle(f"Bucket #{rank}  {head['tag']} | {head['page_kind']} | {head['pair_kind']} | "
                     f"{head['obj_sub'] or '-'} | {head['reason']}", fontsize=9, y=0.995)
        for ax, s in zip(axes, group):
            draw_panel(ax, s)
            ax.set_title(f"{s['project_id']} {s['pair_id']} [{s['status']}]\n"
                         f"{s['left_value']} - {s['right_value']}  sheet {s['sheet_id']}", fontsize=8)
            index.append({"rank": rank, "k": s["k"], "project_id": s["project_id"], "pair_id": s["pair_id"],
                          "sheet_id": s["sheet_id"], "status": s["status"], "left_value": s["left_value"],
                          "right_value": s["right_value"], "bucket": s["bucket"]})
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        out = os.path.join(PNG_DIR, f"{prefix}_{rank:02d}.png")
        fig.savefig(out, dpi=100)
        plt.close(fig)
        print("wrote", out, flush=True)
    json.dump(index, open(os.path.join(WORK, f"render_index{suffix}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
