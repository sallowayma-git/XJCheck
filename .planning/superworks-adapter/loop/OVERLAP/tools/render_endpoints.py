"""Render the four p003 F0012 bottom endpoints after the overlap rule (read-only DXF).

Reads the frozen DXF cache (never written) and the replay pair output under .tmp/loop_overlap_p003.
Each panel: the two stacked TEXT entities at the port-2 bottom position (winner green, superseded red),
the strip LINEs in the window (grey), and the resulting component_mapping right endpoint from the replay.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import Rectangle
import pandas as pd
import ezdxf

mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False

ROOT = Path("F:/workspace/XJToolkit")
OUT = ROOT / ".planning/superworks-adapter/loop/OVERLAP"
MAN = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
P3 = [p for p in MAN["projects"] if p["project_id"] == "p003"][0]
DXF = [f for f in P3["files"] if f["file_id"] == "F0012"][0]["dxf_path"]
PAIRS = pd.read_parquet(ROOT / ".tmp/loop_overlap_p003/p003/-/findings/pairs.parquet")

SITES = [
    ("PCM0002", 220.0, "8KLP3-2", "8nB01", "8n401"),
    ("PCM0005", 260.0, "8KLP2-2", "8nB12", "8n402"),
    ("PCM0008", 300.0, "8KLP1-2", "8nB02", "8n405"),
    ("PCM0012", 380.0, "8CLP1-2", "8nD02", "8n818"),
]


def main(out_name: str) -> None:
    doc = ezdxf.readfile(DXF)  # read-only: the cache file is never saved
    msp = doc.modelspace()
    texts = [e for e in msp if e.dxftype() in ("TEXT", "MTEXT")]
    lines = [e for e in msp if e.dxftype() == "LINE"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.6))
    for ax, (pid, x, port, old_value, new_value) in zip(axes, SITES):
        x0, x1, y0, y1 = x - 14, x + 14, 168, 206
        for line in lines:
            s, e = line.dxf.start, line.dxf.end
            if max(s.x, e.x) < x0 or min(s.x, e.x) > x1 or max(s.y, e.y) < y0 or min(s.y, e.y) > y1:
                continue
            ax.plot([s.x, e.x], [s.y, e.y], color="#999999", lw=0.8)
        for t in texts:
            ax_x = t.dxf.align_point.x if t.dxf.hasattr("align_point") and t.dxf.halign != 0 else t.dxf.insert.x
            ax_y = t.dxf.align_point.y if t.dxf.hasattr("align_point") and t.dxf.halign != 0 else t.dxf.insert.y
            value = t.dxf.text if t.dxftype() == "TEXT" else t.text
            if not (x0 <= ax_x <= x1 and y0 <= ax_y <= y1):
                continue
            color = "black"
            if value in (new_value,) and t.dxf.handle in ("134B4", "134AE", "134A8", "1349C"):
                color = "green"
            if value == old_value:
                color = "red"
            dy = -2.2 if color == "red" else 0.0  # display-only offset so both labels stay readable
            ax.text(ax_x, ax_y + dy, value, fontsize=9, color=color, ha="center", va="bottom")
            ax.plot([ax_x], [ax_y], marker="o", ms=2.5, color=color)
        ax.add_patch(Rectangle((x - 1.5, y0 + 1), 3, 4, fill=False, ec="#2a7", lw=0))
        row = PAIRS[(PAIRS.pair_kind == "component_mapping") & (PAIRS.left_value == port) & (PAIRS.sheet_id == "S0012")]
        right = row.right_value.iloc[0] if len(row) else None
        ax.set_title(f"{pid} port2 bottom x={x:g}\nright endpoint now: {right}", fontsize=10)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=7)
    fig.suptitle("p003 F0012 bottom endpoints: latest stacked text wins (green = kept, red = superseded, grey = strip line)", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / out_name, dpi=130)
    print("wrote", OUT / out_name)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "OVERLAP_p003_endpoints.png")
