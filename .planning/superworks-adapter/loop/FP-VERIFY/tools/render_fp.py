"""Read-only DXF renderer for FP-VERIFY. Reads frozen DXF (corpus_manifest) and round/current pickles.
Writes PNG only into the path given. Usage: render_fp.py SPEC.json  (spec: list of jobs)."""
import sys, json, os, math
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
ROOT = "F:/workspace/XJToolkit"
MAN = json.load(open(f"{ROOT}/.planning/superworks-adapter/corpus_manifest.json", encoding="utf-8"))
CUR = f"{ROOT}/.tmp/engine_coordination_full_acceptance/current"
R25 = f"{ROOT}/.tmp/superworks_round25_full"
CFG = Configuration.defaults().with_changes(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE)
_doc_cache = {}

def dxf_for(pid, fid):
    for p in MAN["projects"]:
        if p["project_id"] == pid:
            for f in p["files"]:
                if f["file_id"] == fid:
                    return f["dxf_path"]
    raise KeyError((pid, fid))

def doc_for(path):
    if path not in _doc_cache:
        _doc_cache.clear()
        _doc_cache[path] = ezdxf.readfile(path)
    return _doc_cache[path]

def fnum(v):
    try:
        x = float(v); return None if x != x else x
    except Exception:
        return None

def run_job(job, out_png):
    pid, fid, sid = job["project"], job["file_id"], job["sheet_id"]
    doc = doc_for(dxf_for(pid, fid))
    cx, cy, hw = job["cx"], job["cy"], job.get("half_width", 25.0)
    hh = job.get("half_height", hw * 0.6)
    xlim, ylim = (cx - hw, cx + hw), (cy - hh, cy + hh)
    fig, ax = plt.subplots(figsize=(11, 8.5), dpi=150)
    ctx = RenderContext(doc)
    be = MatplotlibBackend(ax)
    fe = Frontend(ctx, be, config=CFG)
    fe.draw_layout(doc.modelspace(), finalize=True)
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    # text labels inside window
    tx = job.get("texts_parquet")
    texts = pd.read_parquet(tx) if tx else None
    if texts is not None:
        sub = texts[(texts.sheet_id == sid) & (texts.insert_x.between(*xlim)) & (texts.insert_y.between(*ylim))]
        for t in sub.itertuples(index=False):
            ax.text(t.insert_x, t.insert_y, f"{t.text_id}:{t.text}", fontsize=5.5, color="#374151", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.6))
    # overlays
    for ov in job.get("overlays", []):
        col = ov["color"]; lw = ov.get("lw", 2.2)
        pts = ov.get("points", [])
        if len(pts) >= 2:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            ax.plot(xs, ys, color=col, lw=lw, alpha=0.85, zorder=10, solid_capstyle="round", linestyle=ov.get("ls", "-"))
        for p in ov.get("markers", []):
            ax.scatter([p[0]], [p[1]], s=ov.get("ms", 60), c=col, edgecolors="black", linewidths=0.5, zorder=12)
        if ov.get("label"):
            lx, ly = ov["label_at"]
            ax.text(lx, ly, ov["label"], fontsize=7.5, color=col, zorder=14,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col, lw=0.8, alpha=0.95))
    ax.set_title(job.get("title", ""), fontsize=10)
    fig.text(0.01, 0.01, job.get("footer", ""), fontsize=7.5, wrap=True)
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    for job in spec["jobs"]:
        run_job(job, job["out"])
        print("wrote", job["out"])
