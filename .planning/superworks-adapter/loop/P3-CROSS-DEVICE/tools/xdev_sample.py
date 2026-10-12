"""P3-CROSS-DEVICE: stratified visual sample of guarded pairs and of residual pass pairs (read-only; PNG + JSON).

usage: xdev_sample.py RUN_ROOT OUT_DIR PNG_DIR

Pool A: pairs the guard discarded (verdict body) or sent to review (verdict ambiguous).
Pool B: wire-component pass pairs on the census-D3 set that the guard left as pass (no body found on the path).
Each pair gets a coverage note: whether its two end texts still appear in a non-discard pair on the same sheet
(segment coverage: the terminal or component on each side is connected by another pair).
Overlays: blue = the pair path (left anchor to right anchor), magenta = the two anchors, red = SuperWORKS ports,
green = unregistered SYMB2 TERMPOINTs, orange = V1 line groups of the sheet inside the window.
"""
from __future__ import annotations

import glob
import json
import random
import sys
from collections import defaultdict
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

RUN = Path(sys.argv[1])
OUT = Path(sys.argv[2])
PNG = Path(sys.argv[3])
CENSUS = Path(sys.argv[4]) if len(sys.argv) > 4 else None
OUT.mkdir(parents=True, exist_ok=True)
PNG.mkdir(parents=True, exist_ok=True)
RNG = random.Random(20261012)


def jload(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return {}
    if isinstance(v, dict):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return {}


def project_findings(pid: str) -> Path:
    return Path(glob.glob(str(RUN / pid / "*" / "findings"))[0])


def load_project(pid: str):
    fd = project_findings(pid)
    pairs = pd.read_parquet(fd / "pairs.parquet")
    lg = pd.read_parquet(fd / "line_groups.parquet")
    ports = pd.read_parquet(fd / "sw_ports.parquet")
    unreg = pd.read_parquet(fd / "sw_unregistered_symb2.parquet") if (fd / "sw_unregistered_symb2.parquet").exists() else pd.DataFrame()
    pages = pd.read_parquet(fd / "pages.parquet")
    return fd, pairs, lg, ports, unreg, pages


def dxf_for(pid: str, sheet_id: str, pages: pd.DataFrame) -> str | None:
    fid = pages.loc[pages.sheet_id == sheet_id, "file_id"].iloc[0]
    hits = sorted(glob.glob(str(RUN / pid / "cache" / "converted_dxf" / f"{fid}_*.dxf")))
    return hits[0] if hits else None


def coverage_note(pairs: pd.DataFrame, row) -> dict:
    """Non-discard pairs on the same sheet that use each end text of this pair."""
    same = pairs[(pairs.sheet_id == row.sheet_id) & (pairs.status != "discard") & (pairs.pair_id != row.pair_id)]
    out = {}
    for side, text_id in (("left", row.left_text_id), ("right", row.right_text_id)):
        if text_id is None or (isinstance(text_id, float) and pd.isna(text_id)):
            out[side] = None
            continue
        hit = same[(same.left_text_id == text_id) | (same.right_text_id == text_id)]
        out[side] = [{"pair_id": h.pair_id, "status": h.status, "kind": h.pair_kind,
                      "left": h.left_value, "right": h.right_value} for h in hit.head(3).itertuples()]
    return out


def draw(ax, dxf, window, rec, lg_sheet, ports_sheet, unreg_sheet):
    doc = ezdxf.readfile(dxf) if dxf else None
    if doc is not None:
        msp = doc.modelspace()
        ctx = RenderContext(doc)
        config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
        Frontend(ctx, MatplotlibBackend(ax), config=config).draw_layout(msp, finalize=False)
    x0, y0, x1, y1 = window
    mark = (x1 - x0) * 0.012
    for g in lg_sheet.itertuples():
        if g.end_x < x0 or g.start_x > x1 or max(g.start_y, g.end_y) < y0 or min(g.start_y, g.end_y) > y1:
            continue
        ax.plot([g.start_x, g.end_x], [g.start_y, g.end_y], color="#ff7f0e", lw=1.4, zorder=30)
    for p in ports_sheet.itertuples():
        mx, my = (p.start_x + p.end_x) / 2, (p.start_y + p.end_y) / 2
        if x0 <= mx <= x1 and y0 <= my <= y1:
            ax.add_patch(Rectangle((mx - mark, my - mark), mark * 2, mark * 2, fill=False, ec="#d62728", lw=1.4, zorder=35))
    for u in unreg_sheet.itertuples():
        for t in json.loads(u.termpoints):
            ax_, ay_ = t["a"]
            bx_, by_ = t["b"]
            if x0 <= (ax_ + bx_) / 2 <= x1 and y0 <= (ay_ + by_) / 2 <= y1:
                ax.plot([ax_, bx_], [ay_, by_], color="#2ca02c", lw=2.0, zorder=36)
    lx, ly, rx, ry = rec["lx"], rec["ly"], rec["rx"], rec["ry"]
    ax.plot([lx, rx], [ly, ry], color="#1f4fd1", lw=2.2, zorder=40)
    for xx, yy, label in ((lx, ly, rec["left"]), (rx, ry, rec["right"])):
        ax.add_patch(plt.Circle((xx, yy), mark * 0.9, fill=False, ec="#d62fbf", lw=1.4, zorder=45))
        ax.text(xx + mark, yy + mark * 1.5, label, color="#d62fbf", fontsize=6.5, zorder=60)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])


def render(path: Path, header: str, panels: list[dict]) -> None:
    cols = 3
    rows = (len(panels) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 5.2, rows * 4.9), squeeze=False)
    for ax in axes.flat:
        ax.set_axis_off()
    for ax, panel in zip(axes.flat, panels):
        ax.set_axis_on()
        ax.set_facecolor("#1d2228")
        draw(ax, panel["dxf"], panel["window"], panel["rec"], panel["lg"], panel["ports"], panel["unreg"])
        ax.set_title("\n".join(panel["title"]), fontsize=7.5)
    fig.suptitle(header, fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=110)
    plt.close(fig)


def build_panel(pid: str, row, pairs, lg, ports, unreg, pages):
    lx, ly, rx, ry = row.left_coord_x, row.left_coord_y, row.right_coord_x, row.right_coord_y
    pad = 14.0
    window = (min(lx, rx) - pad, min(ly, ry) - pad, max(lx, rx) + pad, max(ly, ry) + pad)
    sheet = row.sheet_id
    dxf = dxf_for(pid, sheet, pages)
    rec = {"lx": lx, "ly": ly, "rx": rx, "ry": ry, "left": str(row.left_value), "right": str(row.right_value)}
    lg_sheet = lg[lg.sheet_id == sheet]
    ports_sheet = ports[ports.sheet_id == sheet]
    unreg_sheet = unreg[unreg.sheet_id == sheet] if len(unreg) else unreg
    return {"dxf": dxf, "window": window, "rec": rec, "lg": lg_sheet, "ports": ports_sheet, "unreg": unreg_sheet}


def main() -> None:
    projects = sorted(p.name for p in RUN.glob("p*") if (p / "complete.json").exists())
    pool_a, pool_b = [], []
    cache = {}
    for pid in projects:
        fd, pairs, lg, ports, unreg, pages = load_project(pid)
        cache[pid] = (pairs, lg, ports, unreg, pages)
        for row in pairs.itertuples():
            ev = jload(row.evidence)
            check = ev.get("symbol_body_path_check") or {}
            if check.get("verdict") in ("body", "ambiguous") and row.pair_kind == "wire_component_mapping":
                pool_a.append((pid, row))
            elif (check.get("verdict") is None and check.get("reason") == "no_body_on_path"
                  and row.status == "pass" and row.pair_kind == "wire_component_mapping"):
                pool_b.append((pid, row))
    print("pool A", len(pool_a), "pool B", len(pool_b))

    def stratified(pool, n):
        by = defaultdict(list)
        for pid, row in pool:
            key = jload(row.evidence).get("component_submode", "?")
            by[(key, pid)].append((pid, row))
        keys = sorted(by)
        chosen = []
        while len(chosen) < min(n, len(pool)):
            progressed = False
            for key in keys:
                if by[key] and len(chosen) < n:
                    chosen.append(by[key].pop(RNG.randrange(len(by[key]))))
                    progressed = True
            if not progressed:
                break
        return chosen

    sample_a = stratified(pool_a, 36)
    sample_b = stratified(pool_b, 12)
    records = []
    for group, sample in (("A_guarded", sample_a), ("B_residual_pass", sample_b)):
        panels = []
        for pid, row in sample:
            pairs, lg, ports, unreg, pages = cache[pid]
            ev = jload(row.evidence)
            panel = build_panel(pid, row, pairs, lg, ports, unreg, pages)
            check = ev.get("symbol_body_path_check") or {}
            cov = coverage_note(pairs, row)
            title = [f"{pid} {row.sheet_id} {row.pair_id} [{row.status}]",
                     f"{ev.get('component_submode')} | {row.left_value} <-> {row.right_value}",
                     f"check {check.get('verdict')} {check.get('reason', '')} marks {check.get('marks', '')}"]
            panel["title"] = title
            panel["lg"] = panel["lg"]
            panels.append(panel)
            records.append({"group": group, "project": pid, "sheet": row.sheet_id, "pair_id": row.pair_id,
                            "status": row.status, "submode": ev.get("component_submode"),
                            "left": row.left_value, "right": row.right_value,
                            "left_text_id": row.left_text_id, "right_text_id": row.right_text_id,
                            "left_xy": [row.left_coord_x, row.left_coord_y],
                            "right_xy": [row.right_coord_x, row.right_coord_y],
                            "check": check, "coverage": cov})
        for i in range(0, len(panels), 6):
            name = f"xdev_{group}_{i // 6 + 1:02d}.png"
            render(PNG / name, f"P3-CROSS-DEVICE {group}: {i + 1}-{min(i + 6, len(panels))} of {len(panels)}",
                   panels[i:i + 6])
    (OUT / "sample.json").write_text(json.dumps(records, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("sampled", len(sample_a), len(sample_b))


if __name__ == "__main__":
    main()
