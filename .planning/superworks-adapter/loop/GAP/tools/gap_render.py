"""Two-panel DXF renders with geometry overlays for GAP visual checks (read-only; writes PNG only).

Reuses the round-4 DXF cache and layout (ezdxf matplotlib frontend, colour-swapped black/white). Overlays:
  segs   = (x0, y0, x1, y1, colour, width)  wire segments, e.g. the wire group in blue, the far-end lines in orange
  pts    = (x, y, colour)                    port markers / contacts / far-end points (squares)
  boxes  = (xmin, ymin, xmax, ymax, colour)   bounding boxes, e.g. INSERT extents
  texts  = (x, y, text, colour)              label numbers next to the overlay
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from ezdxf.addons.drawing import Frontend  # noqa: E402
from ezdxf.addons.drawing.config import ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

_SPEC = importlib.util.spec_from_file_location(
    "r4", str(Path("F:/workspace/XJToolkit") / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"))
r4 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(r4)
CACHE = r4.DxfCache()


class Panel:
    def __init__(self, title_lines, dxf, window, segs=(), pts=(), boxes=(), texts=()):
        self.title_lines = list(title_lines)
        self.dxf = dxf
        self.window = window
        self.segs = list(segs)
        self.pts = list(pts)
        self.boxes = list(boxes)
        self.texts = list(texts)


def window_around(points, pad=8.0, min_size=20.0):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + pad
    half = max(half, min_size / 2)
    return (cx - half, cy - half, cx + half, cy + half)


def _draw(ax, panel: Panel):
    if not panel.dxf or not Path(panel.dxf).exists():
        ax.text(0.5, 0.5, "DXF missing", ha="center", va="center", transform=ax.transAxes, fontsize=8)
        ax.set_axis_off()
        return
    try:
        doc, items, ctx = CACHE.get(panel.dxf)
    except Exception as exc:  # noqa: BLE001
        ax.text(0.5, 0.5, f"DXF load failed: {exc}", ha="center", va="center", transform=ax.transAxes, fontsize=7)
        ax.set_axis_off()
        return
    x0, y0, x1, y1 = panel.window
    ents = [e for e, (bx0, by0, bx1, by1) in items if bx1 >= x0 and bx0 <= x1 and by1 >= y0 and by0 <= y1]
    config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
    Frontend(ctx, MatplotlibBackend(ax), config=config).draw_entities(ents)
    for sx0, sy0, sx1, sy1, colour, width in panel.segs:
        ax.plot([sx0, sx1], [sy0, sy1], color=colour, lw=width, solid_capstyle="round", zorder=40)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    span = max(x1 - x0, y1 - y0)
    mark = max(span * 0.012, 0.3)
    for xmin, ymin, xmax, ymax, colour in panel.boxes:
        ax.add_patch(Rectangle((xmin, ymin), xmax - xmin, ymax - ymin, fill=False, ec=colour, lw=1.2, zorder=45))
    for x, y, colour in panel.pts:
        ax.add_patch(Rectangle((x - mark, y - mark), 2 * mark, 2 * mark, fill=False, ec=colour, lw=1.5, zorder=50))
    for x, y, s, colour in panel.texts:
        ax.text(x, y, s, color=colour, fontsize=6, zorder=55, ha="left", va="bottom")
    ax.tick_params(labelsize=5)


def render(path: Path, header: list[str], panels: list[Panel], cols: int = 2):
    count = max(1, len(panels))
    cols = min(cols, count)
    rows = math.ceil(count / cols)
    cell_w, cell_h, text_h = 6.2, 5.0, 1.25
    head_h = 0.25 + 0.2 * len(header)
    width, height = cols * cell_w, head_h + rows * cell_h
    fig = plt.figure(figsize=(width, height), dpi=100, facecolor="white")
    fig.text(0.01, 1 - 0.1 / height, "\n".join(header), ha="left", va="top", fontsize=8.5, color="black")
    for index, panel in enumerate(panels):
        row, col = divmod(index, cols)
        top = head_h + row * cell_h
        fig.text((col * cell_w + 0.12) / width, 1 - (top + 0.05) / height, "\n".join(panel.title_lines),
                 ha="left", va="top", fontsize=6.8, color="black", linespacing=1.3)
        ax_top = top + text_h
        ax_h = cell_h - text_h - 0.2
        ax = fig.add_axes([(col * cell_w + 0.2) / width, 1 - (ax_top + ax_h) / height,
                           (cell_w - 0.4) / width, ax_h / height])
        _draw(ax, panel)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100, facecolor="white")
    plt.close(fig)
