"""DEV-INT-DISCARD visual sample of discarded pairs (read-only; writes PNGs and one JSON).

Usage: python devdisc_visual.py RUN_ROOT DISCARDS_JSON PNG_DIR SAMPLE_JSON N SEED

The sample is drawn from the discards of RUN_ROOT (devdisc_compare.py --discards-json), stratified by
(status before, pair kind), seeded. Each discard has a terminal (device terminal, blue box) and an other end
(internal element pin, magenta square). Each PNG holds two cases, each with a wide view and a terminal-body zoom.
Overlays: terminal TERMPOINT (blue box), element pin (magenta square), terminal wire (blue), element wire (magenta).
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

GAP_TOOLS = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/GAP/tools")
sys.path.insert(0, str(GAP_TOOLS))
import gap_render as R  # noqa: E402

BLUE, MAGENTA = "#1f78b4", "#e7298a"


def findings_of(run_root: Path, pid: str) -> Path:
    project = next((run_root / pid).glob("*/findings"), None)
    return project


def jload(value, default):
    if value is None or (isinstance(value, float) and value != value):
        return default
    return json.loads(value) if isinstance(value, str) else value


def main(run_root: Path, discards_json: Path, png_dir: Path, sample_json: Path, n: int, seed: int) -> None:
    import gaplib as G  # noqa: E402  (on sys.path via GAP_TOOLS)
    dxf_map = G.manifest_map()[0]
    discards = json.loads(discards_json.read_text(encoding="utf-8"))
    cache = {}
    pool = []
    for d in discards:
        pid = d["project"]
        if pid not in cache:
            fdir = findings_of(run_root, pid)
            ports = pd.read_parquet(fdir / "sw_ports.parquet")
            cache[pid] = (fdir, {r["record_id"]: r for r in ports.to_dict("records")},
                          pd.read_parquet(fdir / "lines.parquet"))
        fdir, ports, lines = cache[pid]
        term = ports.get((d["terminal_port_ids"] or [None])[0])
        other = ports.get((d["other_port_ids"] or [None])[0]) if d["other_port_ids"] else None
        if term is None:
            continue
        pool.append({**d, "term": term, "other": other, "file_id": term["file_id"], "lines": lines})
    # stratified by (status_before, pair_kind), seeded
    rng = random.Random(seed)
    strata = defaultdict(list)
    for item in sorted(pool, key=lambda x: (x["project"], x["pair_id"])):
        strata[(item["status_before"], item["pair_kind"])].append(item)
    chosen = []
    keys = sorted(strata)
    quota = {k: 1 for k in keys}
    left = n - len(keys)
    total = sum(len(strata[k]) for k in keys)
    for k in keys:
        quota[k] += int(left * len(strata[k]) / total) if total else 0
    while sum(quota.values()) > n:
        k = max(keys, key=lambda k: quota[k])
        quota[k] -= 1
    while sum(quota.values()) < min(n, total):
        k = max((k for k in keys if quota[k] < len(strata[k])), key=lambda k: len(strata[k]) - quota[k])
        quota[k] += 1
    for k in keys:
        rng.shuffle(strata[k])
        chosen += strata[k][:quota[k]]
    chosen = chosen[:n]

    def handle_segments(lines_df, file_id, handles, colour):
        sub = lines_df[(lines_df["file_id"] == file_id) & (lines_df["handle"].isin(list(handles)))]
        return [(float(s.start_x), float(s.start_y), float(s.end_x), float(s.end_y), colour, 2.2) for s in sub.itertuples()]

    def contact_handles(port):
        return {str(c.get("wire_handle")) for c in jload(port.get("wire_contacts"), []) or []}

    def mid(port):
        return ((float(port["start_x"]) + float(port["end_x"])) / 2, (float(port["start_y"]) + float(port["end_y"])) / 2)

    cases, rows = [], []
    for k, item in enumerate(chosen):
        term, other, lines = item["term"], item["other"], item["lines"]
        dxf = dxf_map.get((item["project"], item["file_id"]))
        cases.append((k, item, term, other, dxf, lines))
        rows.append({"case": k + 1, "project": item["project"], "pair_id": item["pair_id"], "pair_kind": item["pair_kind"],
                     "status_before": item["status_before"], "sheet": item["sheet_id"], "file_id": item["file_id"],
                     "terminal_identity": item["terminal_identity"], "terminal_port": term["record_id"],
                     "other_identity": item["other_identity"], "other_category": item["other_category"],
                     "other_port": (other or {}).get("record_id"), "other_unregistered": item["other_unregistered"]})

    png_dir.mkdir(parents=True, exist_ok=True)
    png_index = []
    for start in range(0, len(cases), 2):
        pair = cases[start:start + 2]
        panels = []
        header = ["DEV-INT-DISCARD 目视样本：装置端子与本装置内部元件相连的配对（被丢弃）。",
                  "蓝框=装置端子 TERMPOINT；品红方块=内部元件引脚；蓝线=端子导线；品红线=元件导线；灰=其它模型空间线。"]
        for k, item, term, other, dxf, lines in pair:
            pts_common = [mid(term)] + ([mid(other)] if other is not None else [])
            wide = R.window_around(pts_common, pad=8.0, min_size=24.0)
            zoom = R.window_around(pts_common, pad=2.5, min_size=8.0)
            segs = handle_segments(lines, item["file_id"], contact_handles(term), BLUE)
            if other is not None:
                segs += handle_segments(lines, item["file_id"], contact_handles(other), MAGENTA)
            boxes = [(float(term["start_x"]), float(term["start_y"]) - 0.3, float(term["end_x"]), float(term["end_y"]) + 0.3, BLUE)]
            pts = [(*mid(term), BLUE)] + ([(*mid(other), MAGENTA)] if other is not None else [])
            title = [f"#{k + 1} {item['project']} {item['sheet_id']}  {item['file_id']}  {item['pair_kind']} {item['status_before']}→丢弃",
                     f"装置端子 {item['terminal_identity']} 端口 {term.get('port_number')}",
                     f"另一端 {item['other_identity']} "
                     f"{'（未登记块引脚）' if item['other_unregistered'] else '（' + str(item['other_category']) + '）'}"]
            panels.append(R.Panel(title, dxf, wide, segs=segs, pts=pts, boxes=boxes))
            panels.append(R.Panel([f"#{k + 1} 近景（端子本体）"], dxf, zoom, segs=segs, pts=pts, boxes=boxes))
        name = f"DD_{start // 2 + 1:02d}.png"
        R.render(png_dir / name, header, panels, cols=2)
        png_index.append({"png": name, "cases": [c[0] + 1 for c in pair]})
        print("wrote", name, flush=True)
    sample_json.write_text(json.dumps({"seed": seed, "n": n, "pool": len(pool), "cases": rows, "png": png_index},
                                      ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("cases", len(rows), "pool", len(pool))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), int(sys.argv[5]),
         int(sys.argv[6]) if len(sys.argv) > 6 else 20261011)
