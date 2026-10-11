"""Render DXF crops for sampled changed pairs (read-only: DXF caches are never saved).

For each sampled pair (after replay) the crop shows the strip row TEXT (green), its header TEXT (blue),
the connection TEXT that names the destination (orange) and the LINEs in the window (grey).
Panel title: pair id, status, new identity (after) and legacy identity (before), destination.
Usage: python render_strip_pairs.py --after .tmp/loop_stripname --before .tmp/superworks_round13_full \
          --compare <compare.json> --out <png dir> --manifest <json>
"""
import argparse, glob, json, random
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
CORPUS = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))["projects"]


def J(x):
    return json.loads(x) if isinstance(x, str) else (x or {})


def dxf_for(pid, file_id):
    p = next(p for p in CORPUS if p["project_id"] == pid)
    return next(f["dxf_path"] for f in p["files"] if f["file_id"] == file_id)


def pair_frame(root, pid):
    d = glob.glob(f"{root}/{pid}/*/findings/pairs.parquet")[0]
    return pd.read_parquet(d).set_index("pair_id")


def draw(pid, pair_id, before_pairs, after_pairs, out_png):
    a = after_pairs.loc[pair_id]
    b = before_pairs.loc[pair_id] if pair_id in before_pairs.index else None
    ev = J(a.evidence)
    sw = ev.get("superworks") or {}
    tm = ev.get("table_mapping") or {}
    doc = ezdxf.readfile(dxf_for(pid, a.file_id))  # read-only
    msp = doc.modelspace()
    row = doc.entitydb.get(sw.get("row_handle"))
    head = doc.entitydb.get(sw.get("header_handle"))
    conn = doc.entitydb.get(sw.get("connection_handle"))
    def pos(e):
        return (float(e.dxf.insert.x), float(e.dxf.insert.y)) if e is not None else None
    pts = [p for p in (pos(row), pos(head), pos(conn)) if p]
    if not pts:
        return None
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    span_x = max(max(p[0] for p in pts) - min(p[0] for p in pts), 0) / 2 + 14
    span_y = max(max(p[1] for p in pts) - min(p[1] for p in pts), 0) / 2 + 9
    x0, x1, y0, y1 = cx - span_x, cx + span_x, cy - span_y, cy + span_y
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for e in msp:
        if e.dxftype() == "LINE":
            s, t = e.dxf.start, e.dxf.end
            if max(s.x, t.x) < x0 or min(s.x, t.x) > x1 or max(s.y, t.y) < y0 or min(s.y, t.y) > y1:
                continue
            ax.plot([s.x, t.x], [s.y, t.y], color="#9a9a9a", lw=0.8, zorder=1)
        elif e.dxftype() in ("TEXT", "MTEXT"):
            px, py = pos(e) if e.dxftype() == "TEXT" else (float(e.dxf.insert.x), float(e.dxf.insert.y))
            if x0 <= px <= x1 and y0 <= py <= y1:
                txt = e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()
                ax.text(px, py, txt, fontsize=6.5, color="#555555", ha="left", va="bottom", zorder=2)
    marks = [(row, "#1a7f37", "row"), (head, "#1f5fbf", "header"), (conn, "#d97706", "connection")]
    for e, color, label in marks:
        if e is None:
            continue
        px, py = pos(e)
        txt = e.dxf.text if e.dxftype() == "TEXT" else e.plain_text()
        ax.add_patch(Rectangle((px - 0.6, py - 0.6), 1.2 + 0.9 * len(str(txt)), 2.2, fill=False, ec=color, lw=1.6, zorder=3))
        ax.text(px, py + 2.6, f"{label}: {txt}", fontsize=8, color=color, ha="left", va="bottom", zorder=4)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=6)
    before_id = (b.left_value if b is not None else None)
    title = (f"{pid} {a.sheet_id} {pair_id} [{a.status} / {a.pair_kind}]\n"
             f"row identity before={before_id}  after={a.left_value}\n"
             f"destination={a.right_value}  strip_name={(J(sw.get('validation') or {}) or {}).get('strip_name', '?')}")
    ax.set_title(title, fontsize=8, loc="left")
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)
    return {"pid": pid, "pair_id": pair_id, "sheet_id": a.sheet_id, "file_id": a.file_id,
            "row_handle": sw.get("row_handle"), "header_handle": sw.get("header_handle"),
            "connection_handle": sw.get("connection_handle"), "status": str(a.status),
            "pair_kind_before": str(b.pair_kind) if b is not None else None, "pair_kind_after": str(a.pair_kind),
            "left_before": str(before_id), "left_after": str(a.left_value), "right": str(a.right_value),
            "header_text": (head.dxf.text if head is not None and head.dxftype() == "TEXT" else (head.plain_text() if head is not None else None)),
            "png": str(out_png)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--compare", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--per-project", type=int, default=2)
    ap.add_argument("--extra", nargs="*", default=[], help="pid:pair_id pairs to render in addition (e.g. p061:PTMR0371)")
    a = ap.parse_args()
    cmp_ = json.loads(Path(a.compare).read_text(encoding="utf-8"))
    rng = random.Random(a.seed)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    samples = []
    for pid, rep in cmp_.items():
        after = pair_frame(a.after, pid); before = pair_frame(a.before, pid)
        pass_left = [c["pair_id"] for c in rep["changed"] if "left_value" in c["fields"]
                     and after.loc[c["pair_id"], "status"] == "pass"]
        kind = [c["pair_id"] for c in rep["changed"] if "pair_kind" in c["fields"]]
        pick = rng.sample(pass_left, min(a.per_project, len(pass_left)))
        if kind:
            pick.append(kind[0])
        # New issue: sample the changed pairs that carry the conflicting left value named in the message.
        new_issue_ids = []
        for rule, _pair, message in rep["issues"]["new"]:
            left = message.split("Left value ", 1)[1].split(" maps", 1)[0]
            new_issue_ids += [c["pair_id"] for c in rep["changed"] if after.loc[c["pair_id"], "left_value"] == left]
        pick += new_issue_ids
        extra_here = [k for e_pid, k in (x.split(":", 1) for x in a.extra) if e_pid == pid]
        pick += extra_here
        for k in dict.fromkeys(pick):
            name = f"{pid}_{k}.png"
            rec = draw(pid, k, before, after, out / name)
            if rec:
                rec["sampled_as"] = ("former_conflict" if k in extra_here else "new_issue" if k in new_issue_ids
                                     else "pair_kind" if k in kind else "left_value")
                if rec["sampled_as"] == "left_value" and rec["left_after"] == rec["left_before"]:
                    rec["sampled_as"] = "pair_kind"
                samples.append(rec)
                print(name, rec["sampled_as"], rec["left_before"], "->", rec["left_after"], rec["right"], flush=True)
    Path(a.manifest).write_text(json.dumps(samples, ensure_ascii=False, indent=1), encoding="utf-8")
    print("samples", len(samples))
