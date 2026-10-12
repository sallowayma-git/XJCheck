"""P1-DEDUPE verification (read-only on replay outputs; writes PNG and JSON only).

1. Agreement of every category-I pair with its SuperWORKS twin: text ids and values (unordered), over the
   10-project replay.  Writes tools/verify.json and tools/superseded_pairs_r24a10.csv.
2. Renders 10 stratified samples (seeded) into two PNG sheets of 5 panels:
   blue   legacy pair wire (left -> right) and its endpoint marks
   red    SuperWORKS twin endpoints (dashed line between them)
   orange SuperWORKS line group when the twin has one on the same file
   The DXF is the replay's converted copy of the frozen source file (black on white).
"""
from __future__ import annotations

import collections
import glob
import json
import os
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import ezdxf  # noqa: E402
from ezdxf.addons.drawing import Frontend  # noqa: E402
from ezdxf.addons.drawing.config import ColorPolicy, Configuration  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402
from ezdxf.addons.drawing.properties import RenderContext  # noqa: E402

ROOT = "F:/workspace/XJToolkit"
RUN = os.path.join(ROOT, ".tmp/loop_dedupe")
HERE = os.path.join(ROOT, ".planning/superworks-adapter/loop/P1-DEDUPE")
PNG = os.path.join(HERE, "png")
PROJECTS = ["p001", "p003", "p022", "p026", "p044", "p051", "p061", "p071", "p074", "p075"]
os.makedirs(PNG, exist_ok=True)
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def load_project(pid):
    pdir = glob.glob(os.path.join(RUN, pid, "*", "findings", "pairs.parquet"))[0]
    base = os.path.dirname(os.path.dirname(pdir))
    pairs = pd.read_parquet(pdir)
    pages = pd.read_parquet(os.path.join(base, "findings", "pages.parquet"))
    lines = pd.read_parquet(os.path.join(base, "findings", "line_groups.parquet"))
    ptype = {r.sheet_id: f"{r.route_target}|{r.page_subtype}" for r in pages.itertuples(index=False)}
    return pairs, lines, ptype


def dxf_for(pid, file_id):
    hits = glob.glob(os.path.join(RUN, pid, "cache", "converted_dxf", f"{file_id}_*.dxf"))
    return hits[0] if hits else None


def collect(pid):
    pairs, lines, ptype = load_project(pid)
    by_id = {r.pair_id: r for r in pairs.itertuples(index=False)}
    rows = []
    for r in pairs.itertuples(index=False):
        ev = json.loads(r.evidence) if isinstance(r.evidence, str) and r.evidence else {}
        if ev.get("supersession_category") != "I":
            continue
        twin = by_id[ev["superseded_by"]]
        rows.append(dict(
            project=pid, pair_id=r.pair_id, sw_pair_id=twin.pair_id, sheet_id=r.sheet_id,
            file_id=r.file_id, pair_kind=r.pair_kind, page=ptype.get(r.sheet_id, "?"),
            legacy_status=r.status, legacy_left=r.left_value, legacy_right=r.right_value,
            sw_left=twin.left_value, sw_right=twin.right_value,
            legacy_lt=r.left_text_id, legacy_rt=r.right_text_id,
            sw_lt=twin.left_text_id, sw_rt=twin.right_text_id,
            twin_pair_kind=twin.pair_kind, twin_status=twin.status,
            legacy_xy=[r.left_coord_x, r.left_coord_y, r.right_coord_x, r.right_coord_y],
            sw_xy=[twin.left_coord_x, twin.left_coord_y, twin.right_coord_x, twin.right_coord_y],
            sw_group=twin.line_group_id, multi=len(ev.get("superseded_by_all", []))))
    return lines, rows


def same_text(row):
    a = {row["legacy_lt"], row["legacy_rt"]}
    b = {row["sw_lt"], row["sw_rt"]}
    return None not in a and a == b


def same_value(row):
    return {row["legacy_left"], row["legacy_right"]} == {row["sw_left"], row["sw_right"]}


def has_xy(xy):
    return xy[0] == xy[0] and xy[1] == xy[1] and xy[2] == xy[2] and xy[3] == xy[3]


def draw_panel(ax, lines, row, pid):
    path = dxf_for(pid, row["file_id"])
    lxy, sxy = row["legacy_xy"], row["sw_xy"]
    pts = []
    if has_xy(lxy):
        pts += [(lxy[0], lxy[1]), (lxy[2], lxy[3])]
    if has_xy(sxy):
        pts += [(sxy[0], sxy[1]), (sxy[2], sxy[3])]
    if path:
        doc = ezdxf.readfile(path)
        ctx = RenderContext(doc)
        config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
        Frontend(ctx, MatplotlibBackend(ax), config=config).draw_layout(doc.modelspace(), finalize=False)
    if not pts:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "no coordinates", transform=ax.transAxes, ha="center")
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half = max(max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 10.0, 18.0)
    mark = 2 * half * 0.012
    grp = lines[(lines.line_group_id == row["sw_group"]) & (lines.file_id == row["file_id"])]
    for g in grp.itertuples(index=False):
        ax.plot([g.start_x, g.end_x], [g.start_y, g.end_y], color="#ff7f0e", lw=1.6, zorder=30)
    if has_xy(lxy):
        ax.plot([lxy[0], lxy[2]], [lxy[1], lxy[3]], color="#1f4fd1", lw=2.2, zorder=40)
        for x, y, lab in ((lxy[0], lxy[1], f"L {row['legacy_left']}"), (lxy[2], lxy[3], f"R {row['legacy_right']}")):
            ax.add_patch(plt.Circle((x, y), mark * 0.9, fill=False, ec="#1f4fd1", lw=1.6, zorder=45))
            ax.text(x + mark * 1.2, y + mark * 1.2, lab, color="#1f4fd1", fontsize=7, zorder=60)
    if has_xy(sxy):
        ax.plot([sxy[0], sxy[2]], [sxy[1], sxy[3]], color="#d62728", lw=1.2, ls="--", zorder=35)
        for x, y, lab in ((sxy[0], sxy[1], f"SW {row['sw_left']}"), (sxy[2], sxy[3], f"SW {row['sw_right']}")):
            ax.add_patch(plt.Rectangle((x - mark * 1.3, y - mark * 1.3), mark * 2.6, mark * 2.6, fill=False,
                                       ec="#d62728", lw=1.6, zorder=50))
            ax.text(x - mark * 1.2, y - mark * 3.2, lab, color="#d62728", fontsize=6.5, zorder=60)
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half, cy + half)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])


def main():
    lines_by, all_rows = {}, []
    for pid in PROJECTS:
        lines, rows = collect(pid)
        lines_by[pid] = lines
        all_rows += rows
    df = pd.DataFrame(all_rows)
    df["same_text"] = [same_text(r) for r in all_rows]
    df["same_value"] = [same_value(r) for r in all_rows]
    out = {
        "total_I": int(len(df)),
        "same_text_ids": int(df.same_text.sum()),
        "same_values": int(df.same_value.sum()),
        "same_text_and_value": int((df.same_text & df.same_value).sum()),
        "twin_status": dict(collections.Counter(df.twin_status)),
        "twin_pair_kind": dict(collections.Counter(df.twin_pair_kind)),
        "by_kind_page": dict(collections.Counter(df.pair_kind + "|" + df.page)),
        "multi_twin_cases": int((df.multi > 1).sum()),
    }
    mismatch = df[~(df.same_text & df.same_value)]
    out["mismatch_examples"] = mismatch.head(12)[
        ["project", "pair_id", "sw_pair_id", "pair_kind", "page", "legacy_left", "legacy_right", "sw_left",
         "sw_right", "legacy_lt", "legacy_rt", "sw_lt", "sw_rt"]].to_dict("records")
    df.to_csv(os.path.join(HERE, "tools", "superseded_pairs_r24a10.csv"), index=False, encoding="utf-8")
    with open(os.path.join(HERE, "tools", "verify.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({k: v for k, v in out.items() if k != "mismatch_examples"}, ensure_ascii=False, indent=2))

    rng = random.Random(24)

    def pick(mask, n):
        pool = df[mask]
        return [pool.iloc[i] for i in sorted(rng.sample(range(len(pool)), min(n, len(pool))))]

    picks = []
    picks += pick((df.pair_kind == "wire_component_mapping") & df.page.str.startswith("WireDiagramExtractor|grid"), 5)
    picks += pick((df.pair_kind == "wire_component_mapping") & df.page.str.endswith("|nan"), 2)
    picks += pick((df.pair_kind == "table_mapping") & df.page.str.contains("backplate_virtual"), 2)
    picks += pick((df.pair_kind == "table_mapping") & df.page.str.contains("backplate_geometric"), 1)
    sample_rows = []
    for sheet in range(2):
        chunk = picks[sheet * 5:(sheet + 1) * 5]
        fig, axes = plt.subplots(1, len(chunk), figsize=(5.2 * len(chunk), 5.6), dpi=100)
        for ax, row in zip(axes, chunk):
            draw_panel(ax, lines_by[row["project"]], row, row["project"])
            ax.set_title(f"{row['project']} {row['pair_id']} -> {row['sw_pair_id']} | {row['sheet_id']}\n"
                         f"{row['pair_kind']} | {str(row['page'])[:34]}\n"
                         f"{row['legacy_left']} - {row['legacy_right']} (text {row['legacy_lt']},{row['legacy_rt']})",
                         fontsize=7)
            sample_rows.append({"project": row["project"], "pair_id": row["pair_id"],
                                "sw_pair_id": row["sw_pair_id"], "pair_kind": row["pair_kind"],
                                "page": row["page"], "same_text": bool(row["same_text"]),
                                "same_value": bool(row["same_value"])})
        fig.suptitle("Blue: legacy category-I pair; dashed red: SuperWORKS twin; orange: SW line group",
                     fontsize=9, y=0.995)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        fig.savefig(os.path.join(PNG, f"dedupe_samples_{sheet + 1}.png"), dpi=100)
        plt.close(fig)
        print("wrote sheet", sheet + 1, flush=True)
    with open(os.path.join(HERE, "tools", "samples.json"), "w", encoding="utf-8") as fh:
        json.dump(sample_rows, fh, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
