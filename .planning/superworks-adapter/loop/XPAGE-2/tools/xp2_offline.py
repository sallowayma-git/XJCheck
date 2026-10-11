"""Offline re-run of the production module (audit/superworks_cross_page.py) on round17 findings (read-only).

Bridges come from the drawn lines of each project's findings, through short_bridge_pairs (same as the artifacts
layer). Usage: python xp2_offline.py <run_dir> <out_json> [--projects ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import xp2_load  # noqa: E402
from dwg_audit.audit import superworks_cross_page as xc  # noqa: E402
import pandas as pd  # noqa: E402


def run_project(run_dir: Path, pid: str) -> dict:
    data = xp2_load.load_project(run_dir, pid)
    info = data["strip_info"]
    rows = []
    for s in data["strips"]:
        meta = info[s["record_id"]]
        rows.append({"file_id": s["record_id"].split(":")[1], "record_id": s["record_id"],
                     "group": meta["header_handle"], "x": meta["row_xy"][0], "y": meta["row_xy"][1]})
    l = pd.read_parquet(data["findings"] / "lines.parquet", columns=["file_id", "start_x", "start_y", "end_x", "end_y"])
    lines = [{"file_id": a, "x0": b, "y0": c, "x1": d, "y1": e} for a, b, c, d, e in
             zip(l.file_id, l.start_x, l.start_y, l.end_x, l.end_y)]
    bridges = xc.short_bridge_pairs(rows, lines)
    result = xc.build_cross_page_links(data["strips"], data["ports"], data["pairs"], data["pages"], bridges=bridges)
    return {"project_id": pid, "bridges": len(bridges), "stats": result["stats"], "links": result["links"],
            "candidates": result["candidates"], "covered": {k: v for k, v in result["covered"].items()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("out_json")
    parser.add_argument("--projects", nargs="*", default=None)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    projects = args.projects or sorted(p.name for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("p") and (p / "complete.json").exists())
    out, totals = [], Counter()
    for pid in projects:
        res = run_project(run_dir, pid)
        out.append(res)
        for k, v in res["stats"].items():
            if k != "covered_targets":
                totals[k] += v
        totals["covered_targets"] += res["stats"].get("covered_targets", 0)
        totals["bridges"] += res["bridges"]
        print(pid, res["bridges"], len(res["candidates"]), Counter(c["candidate"] for c in res["candidates"]).most_common(), flush=True)
    Path(args.out_json).write_text(json.dumps({"projects": out, "totals": dict(totals)}, ensure_ascii=False, default=str), encoding="utf-8")
    print("TOTALS", json.dumps(dict(totals), ensure_ascii=False))


if __name__ == "__main__":
    main()
