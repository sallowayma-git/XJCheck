"""P2-BACKPLATE judgement renderer (read-only over frozen DXF; writes PNG only).

Per case three panels, all from the same frozen DXF sheet:
  A  zoom  +-15 units around the V1 row text and the external terminal R
  B  context  wider window around the V1 row text and its header text (device label, header prefix)
  C  SW zoom  +-15 units around the SW identity port that partners R on this sheet
Marks: blue circle = V1 row number text; magenta dot = V1 header text; red circle = external R;
green square = SW identity (partner of R); orange diamond = SW side at R.
Usage: python render_judge.py <cases.json> <out_dir> <prefix> [first_case_no last_case_no] [panels: ABC|AB] [rows per figure]
"""
import sys, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
import ezdxf
from ezdxf.addons.drawing import Frontend
from ezdxf.addons.drawing.config import ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import RenderContext

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
_DOC = {}


def doc_of(path):
    if path not in _DOC:
        try:
            _DOC[path] = ezdxf.readfile(path)
        except Exception:
            _DOC[path] = ezdxf.recover.readfile(path)[0]
    return _DOC[path]


def panel(ax, dxf, center, half, marks, title):
    doc = doc_of(dxf)
    cfg = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=cfg).draw_layout(doc.modelspace(), finalize=False)
    x0, x1 = center[0] - half, center[0] + half
    y0, y1 = center[1] - half, center[1] + half
    mark = (x1 - x0) * 0.014
    for kind, xy, color, label in marks:
        if xy is None:
            continue
        if not (x0 <= xy[0] <= x1 and y0 <= xy[1] <= y1):
            ax.text(x0 + 0.5, y0 + 0.5, "off-window: " + label, color=color, fontsize=6.5, zorder=60)
            continue
        if kind == "sw":
            ax.add_patch(Rectangle((xy[0] - mark * 1.5, xy[1] - mark * 1.5), mark * 3, mark * 3,
                                   fill=False, ec=color, lw=1.6, zorder=55))
        elif kind == "swR":
            d = mark * 1.6
            ax.add_patch(Polygon([(xy[0], xy[1] - d), (xy[0] + d, xy[1]), (xy[0], xy[1] + d), (xy[0] - d, xy[1])],
                                 closed=True, fill=False, ec=color, lw=1.4, zorder=55))
        elif kind == "hdr":
            ax.add_patch(plt.Circle((xy[0], xy[1]), mark * 0.6, color=color, zorder=50))
        else:
            ax.add_patch(plt.Circle((xy[0], xy[1]), mark * 1.2, fill=False, ec=color, lw=1.5, zorder=50))
        ax.text(xy[0] + mark * 1.8, xy[1] + mark * 1.2, label, color=color, fontsize=6.5, zorder=60)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=7.5)


def mid(a, b):
    return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def case_panels(c):
    row, R, sw_id, sw_R = c["row_xy"], c["R_xy"], c["sw_id_xy"], c["sw_R_xy"]
    hdr = [float(v) for v in c["header_coord"]] if c.get("header_coord") else None
    marks_v1 = [("row", row, "#1f4fd1", "V1 row %02d" % c["v1_row"]), ("R", R, "#c81e1e", "R " + str(c["R"])),
                ("sw", sw_id, "#1a9b3a", "SW " + str(c["sw_identity"])), ("swR", sw_R, "#e07b00", "SW side of R")]
    ctx_center = mid(row, hdr) if hdr else row
    ctx_half = max(40.0, (dist(row, hdr) / 2 + 14) if hdr else 40.0)
    ctx_marks = list(marks_v1)
    if hdr:
        ctx_marks.append(("hdr", hdr, "#d62fbf", "hdr " + str(c.get("header_prefix"))))
    sw_side = c["sw_left"] if c["sw_right"] == c["sw_identity"] else c["sw_right"]
    sw_marks = [("sw", sw_id, "#1a9b3a", "SW %s (dev %s, row %02d)" % (c["sw_identity"], c["sw_device"], c["sw_row"])),
                ("swR", sw_R, "#e07b00", "SW side " + str(sw_side))]
    return [
        (mid(row, R), 15.0, marks_v1, "A zoom +-15 (V1 row + R)"),
        (ctx_center, ctx_half, ctx_marks, "B context +-%d (V1 row + header)" % round(ctx_half)),
        (sw_id, 15.0, sw_marks, "C SW identity zoom +-15"),
    ]


def figure(cases, out_png, keep="ABC"):
    """keep: panel letters to draw (A zoom, B context, C SW zoom). Census figures use "AB" with six rows."""
    n = len(cases)
    cols = len(keep)
    if cols == 3:
        fig, axes = plt.subplots(n, 3, figsize=(16.0, 5.6 * n), dpi=110)
    else:
        fig, axes = plt.subplots(n, cols, figsize=(13.2, (4.3 if n <= 6 else 3.4) * n), dpi=110)
    if n == 1:
        axes = [axes]
    fig.subplots_adjust(left=0.01, right=0.99, top=0.985, bottom=0.01, wspace=0.10, hspace=0.34)
    for r, c in enumerate(cases):
        head = ("#%d %s | %s %s | sheet %s %s\n" % (c["case_no"], c["cls"], c["project"], c["pair_id"],
                                                  c["sheet_no"], c["filename"])
                + "V1: L=%s R=%s row %02d dev %s hdr %s  ||  SW: %s <-> %s (identity %s, row %02d, dev %s)"
                % (c["v1_left"], c["R"], c["v1_row"], c["v1_device"], c.get("header_prefix"),
                   c["sw_left"], c["sw_right"], c["sw_identity"], c["sw_row"], c["sw_device"]))
        panels = case_panels(c)
        for k, letter in enumerate(keep):
            center, half, marks, title = panels["ABC".index(letter)]
            panel(axes[r][k], c["dxf"], center, half, marks, title)
        pos = axes[r][0].get_position()
        fig.text(0.01, pos.y1 + 0.006, head, fontsize=8.5, va="bottom", ha="left")
    fig.savefig(out_png, dpi=110)
    plt.close(fig)
    print("wrote", out_png, flush=True)


if __name__ == "__main__":
    cases_path, out_dir, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
    lo, hi = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (0, 10 ** 9)
    keep = sys.argv[6] if len(sys.argv) > 6 else "ABC"
    per_fig = int(sys.argv[7]) if len(sys.argv) > 7 else (2 if keep == "ABC" else 6)
    cases = [c for c in json.load(open(cases_path, encoding="utf-8")) if lo <= c["case_no"] <= hi]
    os.makedirs(out_dir, exist_ok=True)
    for i in range(0, len(cases), per_fig):
        group = cases[i:i + per_fig]
        figure(group, os.path.join(out_dir, "%s_%03d_%03d.png" % (prefix, group[0]["case_no"], group[-1]["case_no"])), keep)
