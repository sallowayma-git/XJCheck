"""Single-process timing of the HEAD code (re-reads DXF for wire routes) against the phase-2 code.

Method (as loop/L-11): replay.py with --workers 1 over 8 projects, runs alternate base, new, base, new.
Each run writes its own output directory (replay resumes from complete.json, so names must be fresh).
Per project the median of the two runs is reported, with total, extract, recognition and other stages.

Usage: python perf_loggen2.py <base_snapshot> <new_snapshot> <work_dir>
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path("F:/workspace/XJToolkit")
REPLAY = ROOT / ".planning/superworks-adapter/replay.py"
PROJECTS = ["p000", "p024", "p030", "p044", "p050", "p061", "p070", "p075"]  # the L-11 set


def run_once(snapshot: Path, out: Path) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, str(REPLAY), "--output", str(out), "--snapshot", str(snapshot),
                    "--workers", "1", "--projects", *PROJECTS], cwd=str(ROOT), env=env, check=True)
    timings = {}
    for pid in PROJECTS:
        complete = json.loads((out / pid / "complete.json").read_text(encoding="utf-8"))
        stages = complete.get("stage_seconds", {})
        timings[pid] = {"total": complete["elapsed_seconds"], "extract": stages.get("extract"),
                        "recognition": stages.get("recognition")}
        stats_files = list(Path(complete["project_dir"]).glob("findings/sw_wire_routes_stats.json"))
        if stats_files:
            stats = json.loads(stats_files[0].read_text(encoding="utf-8"))
            timings[pid]["wire_read_seconds"] = stats.get("read_seconds")
            timings[pid]["wire_resolve_seconds"] = stats.get("resolve_seconds")
    return timings


def main(base_snapshot: Path, new_snapshot: Path, work: Path) -> None:
    work.mkdir(parents=True, exist_ok=True)
    plan = [("base", base_snapshot, "base1"), ("new", new_snapshot, "new1"),
            ("base", base_snapshot, "base2"), ("new", new_snapshot, "new2")]
    results = {}
    for label, snapshot, name in plan:
        print("RUN", label, name, flush=True)
        results.setdefault(label, []).append(run_once(snapshot, work / name))
        (work / "perf_partial.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {}
    for pid in PROJECTS:
        row = {}
        for label in ("base", "new"):
            runs = results[label]
            for key in ("total", "extract", "recognition"):
                row[f"{label}_{key}"] = statistics.median(run[pid][key] for run in runs)
            row[f"{label}_wire_resolve"] = statistics.median(run[pid].get("wire_resolve_seconds") or 0 for run in runs)
            row[f"{label}_wire_read"] = statistics.median(run[pid].get("wire_read_seconds") or 0 for run in runs)
        summary[pid] = row
    totals = {key: sum(summary[pid][key] for pid in PROJECTS) for key in summary[PROJECTS[0]]}
    report = {"projects": summary, "totals": totals,
              "increase_total_pct": 100 * (totals["new_total"] / totals["base_total"] - 1),
              "increase_extract_pct": 100 * (totals["new_extract"] / totals["base_extract"] - 1),
              "increase_recognition_pct": 100 * (totals["new_recognition"] / totals["base_recognition"] - 1),
              "raw": results}
    (work / "perf.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TOTAL", json.dumps({k: round(v, 2) if isinstance(v, float) else v for k, v in totals.items()}), flush=True)
    print("INCREASE total %.2f%% extract %.2f%% recognition %.2f%%" % (
        report["increase_total_pct"], report["increase_extract_pct"], report["increase_recognition_pct"]), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
