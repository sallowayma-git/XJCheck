"""P3-CROSS-DEVICE: visual check of the census-D3 pairs that the guard left as pass (read-only; PNG + JSON).

usage: xdev_d3_residual.py RUN_ROOT RESIDUAL_JSON PNG_PREFIX_DIR [n]
RESIDUAL_JSON: list of {pid, pair_id, sheet, left, right, submode, lx, ly, rx, ry} (census D3 pairs with status pass).
Overlays as in xdev_sample.py: blue = pair path, magenta = anchors, red = SuperWORKS ports, green = SYMB2 TERMPOINTs,
orange = V1 line groups. A pair is judged "device crossed" when a symbol (non-SW or SW) lies between the anchors.
"""
from __future__ import annotations

import glob
import json
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
import ezdxf  # noqa: E402
from ezdxf.addons.drawing import Frontend  # noqa: E402
from ezdxf.addons.drawing.config import ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402
from ezdxf.addons.drawing.properties import RenderContext  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

RUN, RES, PNG = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
N = int(sys.argv[4]) if len(sys.argv) > 4 else 12
PNG.mkdir(parents=True, exist_ok=True)
rng = random.Random(20261014)


def fdir(pid):
    return Path(glob.glob(str(RUN / pid / "*" / "findings"))[0])


def draw(ax, dxf, window, rec, lg, ports, unreg):
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    ctx = RenderContext(doc)
    config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
    Frontend(ctx, MatplotlibBackend(ax), config=config).draw_layout(msp, finalize=False)
    x0, y0, x1, y1 = window
    mark = (x1 - x0) * 0.012
    for g in lg.itertuples():
        if g.end_x < x0 or g.start_x > x1 or max(g.start_y, g.end_y) < y0 or min(g.start_y, g.end_y) > y1:
            continue
        ax.plot([g.start_x, g.end_x], [g.start_y, g.end_y], color="#ff7f0e", lw=1.4, zorder=30)
    for p in ports.itertuples():
        mx, my = (p.start_x + p.end_x) / 2, (p.start_y + p.end_y) / 2
        if x0 <= mx <= x1 and y0 <= my <= y1:
            ax.add_patch(Rectangle((mx - mark, my - mark), mark * 2, mark * 2, fill=False, ec="#d62728", lw=1.4, zorder=35))
    for u in unreg.itertuples():
        for t in json.loads(u.termpoints):
            (ax_, ay_), (bx_, by_) = t["a"], t["b"]
            if x0 <= (ax_ + bx_) / 2 <= x1 and y0 <= (ay_ + by_) / 2 <= y1:
                ax.plot([ax_, bx_], [ay_, by_], color="#2ca02c", lw=2.0, zorder=36)
    lx, ly, rx, ry = rec["lx"], rec["ly"], rec["rx"], rec["ry"]
    ax.plot([lx, rx], [ly, ry], color="#1f4fd1", lw=2.2, zorder=40)
    for xx, yy, label in ((lx, ly, rec["left"]), (rx, ry, rec["right"])):
        ax.add_patch(plt.Circle((xx, yy), mark * 0.9, fill=False, ec="#d62fbf", lw=1.4, zorder=45))
        ax.text(xx + mark, yy + mark * 1.5, str(label), color="#d62fbf", fontsize=6.5, zorder=60)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])


def main():
    items = json.loads(RES.read_text(encoding="utf-8"))
    chosen = []
    by = {}
    for it in items:
        by.setdefault((it["pid"], it["submode"]), []).append(it)
    keys = sorted(by)
    while len(chosen) < min(N, len(items)):
        for k in keys:
            if by[k] and len(chosen) < N:
                chosen.append(by[k].pop(rng.randrange(len(by[k]))))
    panels, records = [], []
    cache = {}
    for it in chosen:
        pid = it["pid"]
        if pid not in cache:
            fd = fdir(pid)
            cache[pid] = (pd.read_parquet(fd / "line_groups.parquet"), pd.read_parquet(fd / "sw_ports.parquet"),
                          pd.read_parquet(fd / "sw_unregistered_symb2.parquet"), pd.read_parquet(fd / "pages.parquet"))
        lg, ports, unreg, pages = cache[pid]
        fid = pages.loc[pages.sheet_id == it["sheet"], "file_id"].iloc[0]
        dxf = sorted(glob.glob(str(RUN / pid / "cache" / "converted_dxf" / f"{fid}_*.dxf")))[0]
        window_pts = [(it["lx"], it["ly"]), (it["rx"], it["ry"])]
        xs = [p[0] for p in window_pts]
        ys = [p[1] for p in window_pts]
        pad = 14.0
        window = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
        panels.append({"dxf": dxf, "window": window,
                       "rec": {"lx": it["lx"], "ly": it["ly"], "rx": it["rx"], "ry": it["ry"],
                               "left": it["left"], "right": it["right"]},
                       "lg": lg[lg.sheet_id == it["sheet"]], "ports": ports[ports.sheet_id == it["sheet"]],
                       "unreg": unreg[unreg.sheet_id == it["sheet"]],
                       "title": [f"{pid} {it['sheet']} {it['pair_id']} [pass, census D3]",
                                 f"{it['submode']} | {it['left']} <-> {it['right']}"]})
        records.append({k: it[k] for k in ("pid", "pair_id", "sheet", "left", "right", "submode")})
    for i in range(0, len(panels), 6):
        chunk = panels[i:i + 6]
        cols = 3
        rows = (len(chunk) + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(cols * 5.2, rows * 4.9), squeeze=False)
        for ax in axes.flat:
            ax.set_axis_off()
        for ax, panel in zip(axes.flat, chunk):
            ax.set_axis_on()
            ax.set_facecolor("#1d2228")
            draw(ax, panel["dxf"], panel["window"], panel["rec"], panel["lg"], panel["ports"], panel["unreg"])
            ax.set_title("\n".join(panel["title"]), fontsize=7.5)
        fig.suptitle(f"P3-CROSS-DEVICE census-D3 pairs kept as pass: {i + 1}-{i + len(chunk)} of {len(panels)}", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig(PNG / f"xdev_d3_residual_{i // 6 + 1:02d}.png", dpi=110)
        plt.close(fig)
    (PNG.parent / "tools" / "results").mkdir(parents=True, exist_ok=True)
    (PNG.parent / "tools" / "results" / "d3_residual_sample.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
