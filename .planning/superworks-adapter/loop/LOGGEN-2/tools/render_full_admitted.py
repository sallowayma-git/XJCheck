"""Render a seeded sample of the full-run admitted pairs (review, no drawn wire) for visual checking.

Usage: python render_full_admitted.py <admitted_json> <replay_dir> <out_dir> <count> <seed>
Reads the rows written from the full run (project, pair_id, record_id, left, right, kind).
Panels reuse the phase-1 builder (render_loggen.build_panels) and the round4 renderer.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / ".planning/superworks-adapter/loop/LOGGEN/tools"))
import render_loggen as base  # noqa: E402


def main(rows_path: Path, replay: Path, out: Path, count: int, seed: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    rng = random.Random(seed)
    sample = rng.sample(rows, min(count, len(rows)))
    cache = base.r4.DxfCache()
    for index, row in enumerate(sample, 1):
        pid = row["project"]
        complete = json.loads((replay / pid / "complete.json").read_text(encoding="utf-8"))
        findings = Path(complete["project_dir"]) / "findings"
        routes = pd.read_parquet(findings / "sw_wire_routes.parquet")
        route = routes[routes.record_id == row["record_id"]].iloc[0]
        pairs = pd.read_parquet(findings / "pairs.parquet")
        pair = pairs[pairs.pair_id == row["pair_id"]].iloc[0]
        sample_dict = {"record_id": route.record_id, "file_id": route.file_id, "sheet_id": route.sheet_id,
                       "wire": None, "linestyle": route.linestyle if isinstance(route.linestyle, str) else "",
                       "kind": route.source_kind, "source_kind": route.source_kind,
                       "ends": json.loads(route.ends_json), "pair_id": pair.pair_id, "pair_status": pair.status,
                       "side": "", "pair_value": f"{pair.left_value} | {pair.right_value}", "pair_kind": pair.pair_kind}
        geo = base.Geometry(findings)
        files = base.dxf_map(pid)
        panels = base.build_panels(pid, sample_dict, geo, files, f"F{index}")
        if not panels:
            print("no panel", pid, row["pair_id"], flush=True)
            continue
        base.render(out / f"full_admitted_{index:02d}_{pid}_{pair.pair_id}.png",
                    [f"全语料准入抽样 {index}：{pid} {pair.left_value} ↔ {pair.right_value}（{pair.pair_kind}，review，记录无导线句柄）",
                     f"记录 {route.record_id}"], panels, cache)
    print("rendered", len(sample), out, flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
