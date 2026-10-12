"""P3-CROSS-DEVICE: visual check of the pairs.py-built wire pairs (schematic wire-logic endpoints) that the generalized
guard now discards or reviews (read-only; PNG only).

usage: xdev_extra_check.py SCAN_JSON BASE_RUN PNG_OUT

Reads the body/ambiguous rows of the full-run offline scan for wire_component_mapping pass pairs without SuperWORKS
evidence and draws each path (from the scan's span and cross) on the round-23 DXF of its sheet.
"""
from __future__ import annotations

import glob
import json
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

SCAN, BASE, PNG = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
PNG.mkdir(parents=True, exist_ok=True)


def fdir(pid: str) -> Path:
    return Path(glob.glob(str(BASE / pid / "*" / "findings"))[0])


def main() -> None:
    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    rows = []
    for pid, r in scan.items():
        fd = fdir(pid)
        pairs = pd.read_parquet(fd / "pairs.parquet").set_index("pair_id")
        for b in r["body_rows"]:
            p = pairs.loc[b["pair_id"]]
            ev = json.loads(p.evidence)
            if "superworks" in ev or ev.get("source") == "superworks":
                continue
            # Only the pairs the generalized guard (pairs.py output) acted on.
            if ev.get("component_submode") == "schematic_wire_logic_endpoint" or p.pair_kind in ("semantic_mapping", "ordinary_pair"):
                if (ev.get("symbol_body_path_check") or {}).get("verdict") in ("body", "ambiguous"):
                    rows.append((pid, b, p))
    print("rows", len(rows))
    panels = []
    for pid, b, p in rows:
        fd = fdir(pid)
        pages = pd.read_parquet(fd / "pages.parquet")
        fid = pages.loc[pages.sheet_id == b["sheet"], "file_id"].iloc[0]
        dxf = sorted(glob.glob(str(BASE / pid / "cache" / "converted_dxf" / f"{fid}_*.dxf")))[0]
        lg = pd.read_parquet(fd / "line_groups.parquet")
        lg = lg[lg.sheet_id == b["sheet"]]
        ports = pd.read_parquet(fd / "sw_ports.parquet")
        ports = ports[ports.sheet_id == b["sheet"]]
        unreg = pd.read_parquet(fd / "sw_unregistered_symb2.parquet")
        unreg = unreg[unreg.sheet_id == b["sheet"]]
        orient = b["orientation"]
        if orient not in ("horizontal", "vertical"):
            orient = "horizontal" if abs(p.left_coord_x - p.right_coord_x) >= abs(p.left_coord_y - p.right_coord_y) else "vertical"
        lo, hi = b["span"]
        cross = b["cross"]
        if orient == "horizontal":
            x0, x1 = lo - 14, hi + 14
            y0, y1 = cross - 14, cross + 14
            seg = ((lo, cross), (hi, cross))
        else:
            x0, x1 = cross - 14, cross + 14
            y0, y1 = lo - 14, hi + 14
            seg = ((cross, lo), (cross, hi))
        panels.append({"dxf": dxf, "window": (x0, y0, x1, y1), "seg": seg, "lg": lg, "ports": ports, "unreg": unreg,
                       "title": [f"{pid} {b['sheet']} {b['pair_id']} [{b['status']} | {b['verdict']}]",
                                 f"{p.left_value} <-> {p.right_value} | {p.rationale[:40]}",
                                 f"marks {b.get('marks')}"]})
    cols = 3
    for i in range(0, len(panels), 6):
        chunk = panels[i:i + 6]
        rws = (len(chunk) + cols - 1) // cols
        fig, axes = plt.subplots(rws, cols, figsize=(cols * 5.2, rws * 4.9), squeeze=False)
        for ax in axes.flat:
            ax.set_axis_off()
        for ax, panel in zip(axes.flat, chunk):
            ax.set_axis_on()
            ax.set_facecolor("#1d2228")
            doc = ezdxf.readfile(panel["dxf"])
            ctx = RenderContext(doc)
            config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
            Frontend(ctx, MatplotlibBackend(ax), config=config).draw_layout(doc.modelspace(), finalize=False)
            x0, y0, x1, y1 = panel["window"]
            mark = (x1 - x0) * 0.012
            for g in panel["lg"].itertuples():
                if g.end_x < x0 or g.start_x > x1 or max(g.start_y, g.end_y) < y0 or min(g.start_y, g.end_y) > y1:
                    continue
                ax.plot([g.start_x, g.end_x], [g.start_y, g.end_y], color="#ff7f0e", lw=1.4, zorder=30)
            for pt in panel["ports"].itertuples():
                mx, my = (pt.start_x + pt.end_x) / 2, (pt.start_y + pt.end_y) / 2
                if x0 <= mx <= x1 and y0 <= my <= y1:
                    ax.add_patch(Rectangle((mx - mark, my - mark), mark * 2, mark * 2, fill=False, ec="#d62728", lw=1.4, zorder=35))
            for u in panel["unreg"].itertuples():
                for t in json.loads(u.termpoints):
                    (ax_, ay_), (bx_, by_) = t["a"], t["b"]
                    if x0 <= (ax_ + bx_) / 2 <= x1 and y0 <= (ay_ + by_) / 2 <= y1:
                        ax.plot([ax_, bx_], [ay_, by_], color="#2ca02c", lw=2.0, zorder=36)
            (sx, sy), (ex, ey) = panel["seg"]
            ax.plot([sx, ex], [sy, ey], color="#1f4fd1", lw=2.4, zorder=40)
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_aspect("equal", adjustable="box")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title("\n".join(panel["title"]), fontsize=7.2)
        fig.suptitle(f"P3-CROSS-DEVICE pairs.py wire-logic pairs under the generalized guard: {i + 1}-{i + len(chunk)} of {len(panels)}", fontsize=9.5)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig(PNG / f"xdev_pairs_py_guard_{i // 6 + 1:02d}.png", dpi=110)
        plt.close(fig)


if __name__ == "__main__":
    main()
