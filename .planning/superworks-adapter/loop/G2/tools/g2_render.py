"""G2 renders (diagnostic): wire gaps of merged line groups, drawn with SW ports and text boxes.

Panel content: wires (blue), SW port markers (red), text bounding boxes (green), gap (orange band).
Usage: python g2_render.py <out_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path("F:/workspace/XJToolkit")
ROUND = ROOT / ".tmp" / "superworks_round19_full"

# (project, sheet, gap_start, gap_end, cross, label text, panel title)
SAMPLES = [
    ("p000", "S0004", 341.0, 343.5, 195.0, "1507", "p000 S0004 y195: label 1507 covers the gap"),
    ("p014", "S0006", 240.0, 242.5, 237.5, "114", "p014 S0006 y237.5: label 114 covers the gap"),
    ("p000", "S0007", 132.5, 135.0, 255.0, "431", "p000 S0007 y255: label 431 covers the gap"),
    ("p014", "S0007", 375.0, 377.5, 70.0, "2320", "p014 S0007 y70: label 2320 covers the gap"),
]
EMPTY = ("p039", "S0012", 347.5, 350.0, 240.0, "", "p039 S0012 y240: only candidate with no text (split)")


def panel(ax, pid: str, sheet: str, a: float, b: float, cy: float, title: str, half: float = 8.0) -> None:
    fd = next((ROUND / pid).glob("*/findings"))
    lines = pd.read_parquet(fd / "lines.parquet")
    texts = pd.read_parquet(fd / "texts.parquet")
    ports = pd.read_parquet(fd / "sw_ports.parquet")
    cx = (a + b) / 2
    for r in lines[lines.sheet_id == sheet].itertuples():
        if max(r.start_x, r.end_x) < cx - half or min(r.start_x, r.end_x) > cx + half:
            continue
        if abs(r.start_y - cy) > half or abs(r.end_y - cy) > half:
            continue
        ax.plot([r.start_x, r.end_x], [r.start_y, r.end_y], color="#1f5fbf", lw=1.4, zorder=2)
    for r in ports[ports.sheet_id == sheet].itertuples():
        mx = (r.start_x + r.end_x) / 2
        if abs(mx - cx) > half or abs(r.start_y - cy) > half:
            continue
        ax.plot([r.start_x, r.end_x], [r.start_y, r.end_y], color="#d62728", lw=3.5, zorder=3, solid_capstyle="butt")
    for r in texts[texts.sheet_id == sheet].itertuples():
        if r.bbox_max_x < cx - half or r.bbox_min_x > cx + half or r.bbox_max_y < cy - half or r.bbox_min_y > cy + half:
            continue
        ax.add_patch(Rectangle((r.bbox_min_x, r.bbox_min_y), r.bbox_max_x - r.bbox_min_x,
                               r.bbox_max_y - r.bbox_min_y, fill=False, ec="#2ca02c", lw=0.9, zorder=4))
        ax.text(r.bbox_min_x, r.bbox_max_y + 0.4, str(r.text)[:14], fontsize=6, color="#2ca02c", zorder=5)
    ax.add_patch(Rectangle((a, cy - 1.0), b - a, 2.0, color="#ff7f0e", alpha=0.45, zorder=6))
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half * 0.6, cy + half * 0.6)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=7)
    ax.tick_params(labelsize=6)


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(9, 6.5), dpi=120)
    for ax, (pid, sheet, a, b, cy, _label, title) in zip(axes.flat, SAMPLES):
        panel(ax, pid, sheet, a, b, cy, title)
    fig.tight_layout()
    fig.savefig(out / "G2_label_covered_gaps.png")
    plt.close(fig)
    pid, sheet, a, b, cy, _label, title = EMPTY
    fig, ax = plt.subplots(figsize=(6, 4.2), dpi=120)
    panel(ax, pid, sheet, a, b, cy, title, half=6.0)
    fig.tight_layout()
    fig.savefig(out / "G2_only_empty_candidate_p039.png")
    plt.close(fig)
    print("rendered to", out)


if __name__ == "__main__":
    main(sys.argv[1])
