"""Render DXF close-ups for the LOGGEN phase-2 changes (read-only).

Usage: python render_loggen2.py <compare_dir> <replay_dir> <out_dir>

Samples (all of them, from the ten-project comparison):
  - B3 value fixes (sw_wire_route_fix): legacy numeric side replaced by the SW identity;
  - same-port annotations (sw_wire_route_conflict) on pairs that were not changed;
  - admitted pairs (new pairs, review: the record has no drawn wire, a same-strip bridge).
Panels reuse the round4 drawing helpers and the phase-1 panel builder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
TOOLS = ROOT / ".planning/superworks-adapter/loop/LOGGEN/tools"
sys.path.insert(0, str(TOOLS))
import render_loggen as base  # noqa: E402  (phase-1 panel builder and round4 renderer)

PROJECTS = ["p001", "p003", "p022", "p044", "p050", "p051", "p061", "p071", "p075", "p076"]


def route_row(findings: Path, record_id: str):
    routes = pd.read_parquet(findings / "sw_wire_routes.parquet")
    row = routes[routes.record_id == record_id]
    return None if row.empty else row.iloc[0]


def sample_from_route(findings: Path, record_id: str, pair: dict, label: str) -> dict:
    row = route_row(findings, record_id)
    ends = json.loads(row.ends_json)
    wire = row.wire_handle if isinstance(row.wire_handle, str) else None
    return {"record_id": record_id, "file_id": row.file_id, "sheet_id": row.sheet_id, "wire": wire,
            "linestyle": row.linestyle if isinstance(row.linestyle, str) else "", "kind": row.source_kind,
            "source_kind": row.source_kind, "ends": ends, "pair_id": pair["pair_id"],
            "pair_status": pair["status"], "side": pair.get("side", ""), "pair_value": pair["value"],
            "pair_kind": pair["pair_kind"], "label": label}


def main(compare_dir: Path, replay: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cache = base.r4.DxfCache()
    index = 0
    for pid in PROJECTS:
        summary = json.loads((compare_dir / f"{pid}.json").read_text(encoding="utf-8"))
        complete = json.loads((replay / pid / "complete.json").read_text(encoding="utf-8"))
        findings = Path(complete["project_dir"]) / "findings"
        pairs = pd.read_parquet(findings / "pairs.parquet")
        geo = base.Geometry(findings)
        files = base.dxf_map(pid)
        for change in summary["pairs_changed_detail"]:
            pair = pairs[pairs.pair_id == change["pair_id"]].iloc[0]
            evidence = json.loads(pair.evidence)
            routes = evidence.get("sw_wire_route_fix") or evidence.get("sw_wire_route_conflict") or []
            if not routes:
                continue
            kind = "fix" if evidence.get("sw_wire_route_fix") else "annotation"
            for item in routes[:1]:
                index += 1
                record = item["record_id"]
                pair_info = {"pair_id": pair.pair_id, "status": pair.status, "side": item.get("side", item.get("pair_side", "")),
                             "value": f"{change['left'][1]} | {change['right'][1]}", "pair_kind": pair.pair_kind}
                sample = sample_from_route(findings, record, pair_info, kind)
                panels = base.build_panels(pid, sample, geo, files, f"{kind}{index}")
                if not panels:
                    continue
                title = (f"B3 同端口数值修正 {index}：配对 {pair.pair_id} 右侧旧数字值 {change['right'][0]} 改为 SW 端口身份 {change['right'][1]}"
                         if kind == "fix" else
                         f"同端口注记 {index}：配对 {pair.pair_id} 侧值 {pair.right_value} 与记录端身份不一致（只记录，未改动）")
                base.render(out / f"{kind}_{index:02d}_{pid}_{pair.pair_id}.png", [title, f"记录 {record}"], panels, cache)
        for record_row in pd.read_parquet(findings / "sw_wire_routes.parquet").itertuples():
            if record_row.admission_status != "admitted_review":
                continue
            index += 1
            pair = pairs[pairs.pair_id == record_row.admitted_pair_id].iloc[0]
            sample = sample_from_route(findings, record_row.record_id,
                                       {"pair_id": pair.pair_id, "status": pair.status, "side": "",
                                        "value": f"{pair.left_value} | {pair.right_value}", "pair_kind": pair.pair_kind},
                                       "admitted")
            panels = base.build_panels(pid, sample, geo, files, f"admit{index}")
            if not panels:
                continue
            base.render(out / f"admitted_{index:02d}_{pid}_{pair.pair_id}.png",
                        [f"准入配对 {index}：{pid} {pair.left_value} ↔ {pair.right_value}（同排端子短接，记录无导线句柄，降为 review）",
                         f"记录 {record_row.record_id}"], panels, cache)
    print("rendered", index, out, flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
