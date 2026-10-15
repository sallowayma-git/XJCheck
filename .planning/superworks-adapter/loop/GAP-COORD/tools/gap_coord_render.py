"""GAP-COORD stratified DXF samples for each gate step (read-only inputs; writes PNG only).

Samples: for each step the observations the step changed (emitted in the baseline, suppressed now), stratified, plus the
observations the legacy rule hid and the new rule emits (the regression surface). Seed 20261015.
Overlay colours: blue = observed segment; green square = device terminal port of the observation; orange square = the
other side's port; magenta line = the closing V1 pair's line group (physical_v1) or the link's wire; red cross =
unregistered SYMB2 termpoint; grey = other model-space lines of the sheet in the window.

Usage: python gap_coord_render.py <out_png_dir> <out_manifest_json>
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
LOOP = REPO / ".planning/superworks-adapter/loop"
ANALYSIS = REPO / ".tmp/loop_gapcoord_analysis"
BASELINE = REPO / ".tmp/engine_coordination_full_acceptance/current"
MANIFEST = REPO / ".planning/superworks-adapter/corpus_manifest.json"
SEED = 20261015
PAD = 9.0
PER_PNG = 4

_spec = importlib.util.spec_from_file_location("gap_render", str(LOOP / "GAP/tools/gap_render.py"))
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)

TERMINAL = {"装置端子", "端子"}


def dxf_map():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {(p["project_id"], f["file_id"]): f["dxf_path"] for p in man["projects"] for f in p["files"]}


def base_dir(pid):
    return next(p for p in (BASELINE / pid).glob("*") if (p / "findings").is_dir()) / "findings"


def load_aux(pid):
    f = base_dir(pid)
    lines = pd.read_parquet(f / "lines.parquet", columns=["file_id", "sheet_id", "start_x", "start_y", "end_x", "end_y", "source_block_name"])
    lg = pd.read_parquet(f / "line_groups.parquet", columns=["line_group_id", "file_id", "sheet_id", "start_x", "start_y", "end_x", "end_y"])
    unreg = pd.read_parquet(f / "sw_unregistered_symb2.parquet", columns=["file_id", "sheet_id", "termpoints"])
    links = _frame(f / "sw_device_internal_links.parquet", ["port_id", "source", "pcl_corroborated", "element_label", "endpoint_identity"])
    xpage = _frame(f / "sw_cross_page_links.parquet", ["target_port_id", "relation", "covers_target"])
    return lines, lg, unreg, links, xpage


def _frame(path, columns):
    frame = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    for name in columns:
        if name not in frame:
            frame[name] = None
    return frame[columns]


def pts_of_unreg(unreg):
    out = []
    for r in unreg.itertuples(index=False):
        for tp in json.loads(r.termpoints or "[]"):
            for key in ("a", "b"):
                if tp.get(key):
                    out.append((r.file_id, r.sheet_id, float(tp[key][0]), float(tp[key][1])))
    return out


def jl(v):
    if isinstance(v, str):
        return json.loads(v) if v else []
    return v if isinstance(v, list) else []


def build_panel(row, dxf, aux, extra_line=None, title_head=""):
    lines, lg, unreg_pts = aux["lines"], aux["lg"], aux["unreg"]
    coords = jl(row["coords"])
    if len(coords) != 4:
        return None
    p1, p2 = (float(coords[0]), float(coords[1])), (float(coords[2]), float(coords[3]))
    left, right = jl(row["left"]), jl(row["right"])
    pts_all = [p1, p2]
    markers = []
    for side_name, side in (("L", left), ("R", right)):
        for port in (side or {}).get("ports") or []:
            for key in ("start", "end"):
                if port.get(key):
                    x, y = float(port[key][0]), float(port[key][1])
                    pts_all.append((x, y))
                    color = "green" if (side or {}).get("category") in TERMINAL else "orange"
                    markers.append((x, y, color))
    window = gr.window_around(pts_all, pad=PAD, min_size=24.0)
    x0, y0, x1, y1 = window
    segs = [(p1[0], p1[1], p2[0], p2[1], "blue", 2.4)]
    fs = (row["file_id"], row["sheet_id"])
    sub = lines[(lines.file_id == fs[0]) & (lines.sheet_id == fs[1])]
    count = 0
    for r in sub.itertuples(index=False):
        if max(r.start_x, r.end_x) < x0 or min(r.start_x, r.end_x) > x1 or max(r.start_y, r.end_y) < y0 or min(r.start_y, r.end_y) > y1:
            continue
        segs.append((r.start_x, r.start_y, r.end_x, r.end_y, "grey", 0.6))
        count += 1
        if count > 400:
            break
    if extra_line is not None:
        (ax, ay), (bx, by) = extra_line
        segs.append((ax, ay, bx, by, "magenta", 1.6))
    pts = list(markers)
    for (f, s, x, y) in unreg_pts:
        if f == fs[0] and s == fs[1] and x0 <= x <= x1 and y0 <= y <= y1:
            pts.append((x, y, "red"))
    lc = f"{(left or {}).get('category') or '-'}:{(left or {}).get('value') or '-'}"
    rc = f"{(right or {}).get('category') or '-'}:{(right or {}).get('value') or '-'}"
    title = [
        f"{title_head}",
        f"{row['project']} {row['sheet_id']} {row['file_id']} | {row.get('line_group_id') or '-'} | {row['record_id'][-10:]}",
        f"L {lc} | R {rc}",
        f"suppressed={row.get('suppressed') or '-'} pair={row.get('pair') or '-'}",
        f"reasons={row.get('reasons') or '-'}",
    ]
    return gr.Panel(title, dxf, window, segs=segs, pts=pts)


def strata_sample(df, group_cols, n_total, rng):
    """Up to n_total rows, spread across the strata of group_cols (round-robin over shuffled strata)."""
    if df.empty:
        return df.iloc[0:0]
    groups = [g.sample(frac=1.0, random_state=int(rng.integers(0, 2**31 - 1))) for _, g in df.groupby(group_cols, dropna=False)]
    picked, index = [], 0
    while len(picked) < min(n_total, len(df)):
        progressed = False
        for g in groups:
            if index < len(g):
                picked.append(g.iloc[index])
                progressed = True
                if len(picked) >= n_total:
                    break
        if not progressed:
            break
        index += 1
    return pd.DataFrame(picked)


def main(argv):
    out_png, out_manifest = Path(argv[0]), Path(argv[1])
    out_png.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    table = pd.read_parquet(ANALYSIS / "observation_table.parquet")
    suppressed = pd.read_parquet(ANALYSIS / "suppressed_all.parquet")
    dmap = dxf_map()
    aux_cache = {}
    pair_groups = {}
    for pid in sorted(set(table.project)):
        frame = pd.read_parquet(base_dir(pid) / "pairs.parquet", columns=["pair_id", "file_id", "sheet_id", "line_group_id"])
        for r in frame.itertuples(index=False):
            if isinstance(r.line_group_id, str):
                pair_groups[r.pair_id] = (r.file_id, r.sheet_id, r.line_group_id)

    def aux_for(pid):
        if pid not in aux_cache:
            lines, lg, unreg, links, xpage = load_aux(pid)
            geom = {(r.file_id, r.sheet_id, r.line_group_id): ((r.start_x, r.start_y), (r.end_x, r.end_y)) for r in lg.itertuples(index=False)}
            aux_cache[pid] = {"lines": lines, "lg": lg, "lg_geom": geom, "unreg": pts_of_unreg(unreg), "links": links, "xpage": xpage}
        return aux_cache[pid]

    # The emitted-to-suppressed rows, joined with the suppressed detail.
    keep = ["record_id", "project", "suppressed_by", "terminal_port_ids", "pair_id", "file_id", "sheet_id", "line_group_id"]
    sup = suppressed[[c for c in keep if c in suppressed]].merge(
        table[["record_id", "project", "left", "right", "coords", "old", "new", "reason_codes", "state"]],
        on=["record_id", "project"], how="left")
    sup = sup[sup["old"] == "emitted"]
    sup = sup.assign(step=sup["suppressed_by"])
    samples = []

    def add(df, title_key, n):
        picked = strata_sample(df, ["project", "_stratum"], n, rng) if "_stratum" in df else df.head(n)
        for _, row in picked.iterrows():
            samples.append((title_key, row))

    # Step 1: device-internal line link (strata: link source x pcl).
    dev = sup[sup.step == "device_internal"].copy()
    dev_link = []
    for _, row in dev.iterrows():
        aux = aux_for(row["project"])
        ports = [p for p in json.loads(row["terminal_port_ids"]) if isinstance(p, str)] if isinstance(row["terminal_port_ids"], str) else list(row["terminal_port_ids"] or [])
        match = aux["links"][aux["links"].port_id.isin(ports)] if ports else aux["links"].iloc[0:0]
        src = match.source.iloc[0] if len(match) else "none"
        pcl = bool(match.pcl_corroborated.iloc[0]) if len(match) else False
        dev_link.append(f"{src}|pcl={pcl}")
    dev = dev.assign(_stratum=dev_link)
    add(dev, "S1 device_internal", 12)

    cont = sup[sup.step == "continuity"].copy()
    rel = []
    for _, row in cont.iterrows():
        aux = aux_for(row["project"])
        ports = list(row["terminal_port_ids"] or []) if not isinstance(row["terminal_port_ids"], str) else json.loads(row["terminal_port_ids"])
        match = aux["xpage"][aux["xpage"].target_port_id.isin(ports) & (aux["xpage"].covers_target == True)]  # noqa: E712
        rel.append(match.relation.iloc[0] if len(match) else "none")
    cont = cont.assign(_stratum=rel)
    add(cont, "S1b continuity", 12)

    phys = sup[sup.step == "physical_v1"].copy()
    kinds = []
    for _, row in phys.iterrows():
        kinds.append("pair")
    phys = phys.assign(_stratum=kinds)
    add(phys, "S2 physical_v1", 12)

    xel = sup[sup.step == "x_element_only"].copy()
    def cat(value):
        side = jl(value)
        return str((side or {}).get("category") if isinstance(side, dict) else None)
    xel = xel.assign(_stratum=[cat(a) + "|" + cat(b) for a, b in zip(xel["left"], xel["right"])])
    add(xel, "S3 x_element_only", 12)

    loop = sup[sup.step == "self_loop"].copy()
    loop = loop.assign(_stratum="same_identity")
    add(loop, "S4 self_loop", 12)

    reappeared = table[(table["old"] == "group_suppressed") & table["new"].str.startswith("emitted")].copy()
    reappeared = reappeared.assign(_stratum="reappeared")
    for _, row in reappeared.iterrows():
        samples.append(("R reappeared (legacy group rule hid it)", row))

    manifest = []
    panels_by_png = []
    for title_key, row in samples:
        pid = row["project"]
        aux = aux_for(pid)
        dxf = dmap.get((pid, row["file_id"]))
        detail = {"record_id": row["record_id"], "project": pid, "file_id": row["file_id"], "sheet_id": row["sheet_id"],
                  "step": title_key, "new": row.get("new"), "old": row.get("old")}
        pair_line = None
        pair_id = row.get("pair_id") if "pair_id" in row else None
        if isinstance(pair_id, float):
            pair_id = None
        row_view = {"project": pid, "sheet_id": row["sheet_id"], "file_id": row["file_id"], "record_id": row["record_id"],
                    "line_group_id": row.get("line_group_id"), "coords": row["coords"], "left": row["left"], "right": row["right"],
                    "suppressed": row.get("suppressed_by") or row.get("new"), "pair": pair_id or "-",
                    "reasons": row.get("reason_codes") or row.get("reason_codes")}
        if pair_id and pair_id in pair_groups:
            geometry = aux["lg_geom"].get(pair_groups[pair_id])
            if geometry is not None:
                pair_line = geometry
        panel = build_panel(row_view, dxf, aux, extra_line=pair_line, title_head=title_key)
        if panel is None:
            continue
        panels_by_png.append((title_key, panel, detail))
    for start in range(0, len(panels_by_png), PER_PNG):
        chunk = panels_by_png[start:start + PER_PNG]
        index = start // PER_PNG + 1
        name = f"GAPCOORD_{index:02d}.png"
        keys = sorted({c[0] for c in chunk})
        header = [f"GAP-COORD sample sheet {index:02d}: {' / '.join(keys)}", "blue=observed segment; green=terminal port; orange=other port; red=unregistered termpoint; grey=sheet lines"]
        gr.render(out_png / name, header, [c[1] for c in chunk], cols=2)
        for _, _, detail in chunk:
            manifest.append({**detail, "png": name})
    out_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("samples", len(manifest), "pngs", (len(panels_by_png) + PER_PNG - 1) // PER_PNG)


if __name__ == "__main__":
    main(sys.argv[1:])
