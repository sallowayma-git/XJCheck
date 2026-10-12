"""P2-BACKPLATE renderer (read-only; writes PNG only). Frozen DXF via corpus_manifest.json.
Overlays: blue circle = table row-number text; magenta dot = table header text; red circle = external endpoint R;
green square = SW port on the same sheet whose identity is the SW partner of R; orange = SW strip row (if on sheet).
"""
import sys, json, os, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import ezdxf
from ezdxf.addons.drawing import Frontend
from ezdxf.addons.drawing.config import ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import RenderContext
sys.path.insert(0, 'F:/workspace/XJToolkit/.tmp/p2bp_work')
from load_common import *
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
_DOC = {}
def doc_of(path):
    if path not in _DOC:
        try:
            _DOC[path] = ezdxf.readfile(path)
        except Exception:
            _DOC[path] = ezdxf.recover.readfile(path)[0]
    return _DOC[path]

def draw(ax, spec):
    doc = doc_of(spec['dxf'])
    msp = doc.modelspace()
    ctx = RenderContext(doc)
    cfg = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
    Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_layout(msp, finalize=False)
    pts = [p for p in spec['pts'] if p]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 10
    half = max(half, 22)
    x0, x1, y0, y1 = cx - half, cx + half, cy - half, cy + half
    mark = (x1 - x0) * 0.012
    for key, (xy, col, lab) in spec['marks'].items():
        if not xy: continue
        if key == 'sw':
            ax.add_patch(Rectangle((xy[0] - mark * 1.4, xy[1] - mark * 1.4), mark * 2.8, mark * 2.8, fill=False, ec=col, lw=1.8, zorder=55))
        else:
            ax.add_patch(plt.Circle((xy[0], xy[1]), mark * 1.1, fill=False, ec=col, lw=1.6, zorder=50))
        ax.text(xy[0] + mark * 1.6, xy[1] + mark * 1.4, lab, color=col, fontsize=7, zorder=60)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([]); ax.set_yticks([])

def run(specs, out_png, title):
    n = len(specs)
    fig, axes = plt.subplots(1, n, figsize=(5.2 * n, 5.4), dpi=100)
    if n == 1: axes = [axes]
    for ax, s in zip(axes, specs):
        draw(ax, s)
        ax.set_title(s['title'], fontsize=8)
    fig.suptitle(title, fontsize=9, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(out_png, dpi=100); plt.close(fig)
    print('wrote', out_png, flush=True)
