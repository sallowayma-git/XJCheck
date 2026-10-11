"""Render same-strip bridge_mapping pairs: both terminal rows (by identity) and the wire between them.

Read-only. Green = left terminal row, purple = right terminal row, red crosses = pair wire endpoints,
grey = LINEs in the window. Usage: python render_bridge_pairs.py <pid> <pair_id> [<pair_id> ...]
"""
import glob, json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
import ezdxf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_strip_pairs import pair_frame, dxf_for, J  # noqa: E402

mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False
OUT = Path(__file__).resolve().parents[1] / "png"


def strip_row_handle(root, pid, identity):
    d = glob.glob(f"{root}/{pid}/*/findings/sw_strip_rows.parquet")[0]
    df = pd.read_parquet(d)
    hit = df[df.endpoint_identity.astype(str) == str(identity)]
    return (hit.iloc[0].row_handle, hit.iloc[0].file_id, hit.iloc[0].sheet_id) if len(hit) else (None, None, None)


def render(pid, pair_id, root="F:/workspace/XJToolkit/.tmp/loop_stripname_v2"):
    after = pair_frame(root, pid)
    a = after.loc[pair_id]
    lh, lf, ls = strip_row_handle(root, pid, a.left_value)
    rh, rf, rs = strip_row_handle(root, pid, a.right_value)
    dxf = dxf_for(pid, a.file_id)
    doc = ezdxf.readfile(dxf)  # read-only
    msp = doc.modelspace()
    pts = [(float(a.left_coord_x), float(a.left_coord_y)), (float(a.right_coord_x), float(a.right_coord_y))]
    rows = [doc.entitydb.get(h) for h in (lh, rh) if h]
    rows_xy = [(float(e.dxf.insert.x), float(e.dxf.insert.y)) for e in rows if e is not None]
    allp = pts + rows_xy
    cx = sum(p[0] for p in allp) / len(allp); cy = sum(p[1] for p in allp) / len(allp)
    sx = (max(p[0] for p in allp) - min(p[0] for p in allp)) / 2 + 12
    sy = (max(p[1] for p in allp) - min(p[1] for p in allp)) / 2 + 8
    x0, x1, y0, y1 = cx - sx, cx + sx, cy - sy, cy + sy
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for e in msp:
        if e.dxftype() == "LINE":
            s, t = e.dxf.start, e.dxf.end
            if max(s.x, t.x) < x0 or min(s.x, t.x) > x1 or max(s.y, t.y) < y0 or min(s.y, t.y) > y1:
                continue
            ax.plot([s.x, t.x], [s.y, t.y], color="#9a9a9a", lw=0.8, zorder=1)
        elif e.dxftype() in ("TEXT", "MTEXT"):
            px, py = float(e.dxf.insert.x), float(e.dxf.insert.y)
            if x0 <= px <= x1 and y0 <= py <= y1:
                txt = e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()
                ax.text(px, py, txt, fontsize=6.5, color="#555555", zorder=2)
    for (px, py), color in zip(pts, ["#c62828", "#c62828"]):
        ax.plot([px], [py], marker="x", ms=9, mew=2, color=color, zorder=5)
    for e, color, label in [(rows[0] if len(rows) > 0 else None, "#1a7f37", f"left {a.left_value}"),
                            (rows[1] if len(rows) > 1 else None, "#7b1fa2", f"right {a.right_value}")]:
        if e is None:
            continue
        px, py = float(e.dxf.insert.x), float(e.dxf.insert.y)
        txt = e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()
        ax.add_patch(plt.Rectangle((px - 0.6, py - 0.6), 1.2 + 0.9 * len(str(txt)), 2.2, fill=False, ec=color, lw=1.6, zorder=3))
        ax.text(px, py + 2.6, f"{label} (row {txt})", fontsize=8, color=color, zorder=4)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.tick_params(labelsize=6)
    ax.set_title(f"{pid} {a.sheet_id} {pair_id} [{a.status} / {a.pair_kind}]\n"
                 f"{a.left_value} -- {a.right_value}; strip rows on {ls} and {rs} (same strip: {ls == rs and lh is not None})",
                 fontsize=8, loc="left")
    fig.tight_layout()
    name = f"BRIDGE_{pid}_{pair_id}.png"
    fig.savefig(OUT / name, dpi=130)
    plt.close(fig)
    return name, {"pid": pid, "pair_id": pair_id, "left": a.left_value, "right": a.right_value,
                  "left_row": lh, "right_row": rh, "sheet": a.sheet_id, "status": str(a.status), "kind": str(a.pair_kind)}


if __name__ == "__main__":
    pid = sys.argv[1]
    results = [render(pid, pid_) for pid_ in sys.argv[2:]]
    for name, info in results:
        print(name, info, flush=True)
