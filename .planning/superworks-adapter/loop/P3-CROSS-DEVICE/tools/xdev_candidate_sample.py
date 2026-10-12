"""P3-CROSS-DEVICE: stratified visual check of candidates rejected as path_crosses_symbol_body (read-only; PNG + JSON).

usage: xdev_candidate_sample.py BASE_ROOT NEW_ROOT OUT_JSON PNG_OUT [n]

Population: candidates accepted in the base replay (round 23) and rejected with path_crosses_symbol_body in the new
replay, matched by (project, line_group_id, side, text_id) (candidate ids are not stable across runs).
Each panel: blue = wire end (line-group end) to the candidate text, magenta = the text and the end, orange = the
V1 line groups of the sheet, red = SuperWORKS ports, green = unregistered SYMB2 TERMPOINTs.
"""
from __future__ import annotations

import glob
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from ezdxf.addons.drawing import Frontend  # noqa: E402
from ezdxf.addons.drawing.config import ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402
from ezdxf.addons.drawing.properties import RenderContext  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BASE, NEW, OUT_JSON, PNG_OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
N = int(sys.argv[5]) if len(sys.argv) > 5 else 12
PNG_OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(20261013)


def fdir(root: Path, pid: str) -> Path:
    return Path(glob.glob(str(root / pid / "*" / "findings"))[0])


def population():
    out = []
    for pdir in sorted(NEW.glob("p*")):
        pid = pdir.name
        if not (pdir / "complete.json").exists():
            continue
        b = pd.read_parquet(fdir(BASE, pid) / "terminal_candidates.parquet")
        n = pd.read_parquet(fdir(NEW, pid) / "terminal_candidates.parquet")
        bk = b.set_index(["line_group_id", "side", "text_id"])
        cut = n[(n.status == "rejected") & (n.rejection_reason == "path_crosses_symbol_body")]
        for r in cut.itertuples():
            k = (r.line_group_id, r.side, r.text_id)
            if k in bk.index:
                row = bk.loc[k]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                if row["status"] == "accepted":
                    out.append((pid, r))
    return out


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
    for xx, yy, label in ((lx, ly, "end"), (rx, ry, rec["text"])):
        ax.add_patch(plt.Circle((xx, yy), mark * 0.9, fill=False, ec="#d62fbf", lw=1.4, zorder=45))
        ax.text(xx + mark, yy + mark * 1.5, label, color="#d62fbf", fontsize=6.5, zorder=60)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])


def main() -> None:
    pop = population()
    print("population", len(pop))
    by_proj = defaultdict(list)
    for pid, r in pop:
        by_proj[pid].append(r)
    chosen = []
    keys = sorted(by_proj)
    while len(chosen) < min(N, len(pop)):
        for pid in keys:
            if by_proj[pid] and len(chosen) < N:
                chosen.append((pid, by_proj[pid].pop(rng.randrange(len(by_proj[pid])))))
    panels, records = [], []
    for pid, r in chosen:
        n = pd.read_parquet(fdir(NEW, pid) / "terminal_candidates.parquet")
        pages = pd.read_parquet(fdir(NEW, pid) / "pages.parquet")
        lg = pd.read_parquet(fdir(NEW, pid) / "line_groups.parquet")
        ports = pd.read_parquet(fdir(NEW, pid) / "sw_ports.parquet")
        unreg = pd.read_parquet(fdir(NEW, pid) / "sw_unregistered_symb2.parquet")
        fid = pages.loc[pages.sheet_id == r.sheet_id, "file_id"].iloc[0]
        dxf = sorted(glob.glob(str(NEW / pid / "cache" / "converted_dxf" / f"{fid}_*.dxf")))[0]
        ex, ey, tx, ty = float(r.endpoint_x), float(r.endpoint_y), float(r.text_insert_x), float(r.text_insert_y)
        pad = 16.0
        window = (min(ex, tx) - pad, min(ey, ty) - pad, max(ex, tx) + pad, max(ey, ty) + pad)
        lg_s = lg[lg.sheet_id == r.sheet_id]
        ports_s = ports[ports.sheet_id == r.sheet_id]
        unreg_s = unreg[unreg.sheet_id == r.sheet_id] if len(unreg) else unreg
        rec = {"lx": ex, "ly": ey, "rx": tx, "ry": ty, "text": str(r.text)}
        panels.append({"dxf": dxf, "window": window, "rec": rec, "lg": lg_s, "ports": ports_s, "unreg": unreg_s,
                       "title": [f"{pid} {r.sheet_id} {r.line_group_id} {r.side}", f"text {r.text}  value {r.value}",
                                 "rejected: path_crosses_symbol_body"]})
        records.append({"project": pid, "sheet": r.sheet_id, "line_group_id": r.line_group_id, "side": r.side,
                        "text": r.text, "value": r.value, "end_xy": [ex, ey], "text_xy": [tx, ty]})
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
        fig.suptitle(f"P3-CROSS-DEVICE candidates rejected by the body guard: {i + 1}-{i + len(chunk)} of {len(panels)}",
                     fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig(PNG_OUT / f"xdev_candidates_{i // 6 + 1:02d}.png", dpi=110)
        plt.close(fig)
    OUT_JSON.write_text(json.dumps({"population": len(pop), "sample": records}, ensure_ascii=False, indent=1,
                                   default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
