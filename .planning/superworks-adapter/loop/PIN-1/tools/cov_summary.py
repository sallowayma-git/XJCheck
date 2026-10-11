"""Strict (COV-GAP layer b) and continuity-inclusive coverage of replay directories, per project and in total.

Usage: python cov_summary.py <replay_dir> [<replay_dir> ...] --out <json>

Reads each project's findings/superworks_summary.json: port_coverage (strict) and
port_coverage_with_continuity (strict plus X2 continuity links). Projects are the p*/complete.json entries.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def project_summary(replay: Path, pid: str) -> dict | None:
    complete = replay / pid / "complete.json"
    if not complete.exists():
        return None
    project_dir = Path(json.loads(complete.read_text(encoding="utf-8"))["project_dir"])
    path = project_dir / "findings/superworks_summary.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    strict = data["port_coverage"]
    cont = data.get("port_coverage_with_continuity", {})
    return {"eligible": strict["eligible"], "consumed": strict["consumed"], "pass": strict.get("pass"),
            "ratio": strict["ratio"],
            "consumed_with_continuity": cont.get("consumed", strict["consumed"]),
            "ratio_with_continuity": cont.get("ratio")}


def main(argv: list[str]) -> None:
    out = Path(argv[argv.index("--out") + 1])
    replays = [Path(a) for a in argv[:argv.index("--out")]]
    result = {}
    for replay in replays:
        pids = sorted(p.parent.name for p in replay.glob("p*/complete.json"))
        per = {pid: project_summary(replay, pid) for pid in pids}
        per = {k: v for k, v in per.items() if v}
        total = {"projects": len(per)}
        for key in ("eligible", "consumed", "pass", "consumed_with_continuity"):
            total[key] = sum(v[key] or 0 for v in per.values())
        total["ratio"] = round(total["consumed"] / total["eligible"], 6) if total["eligible"] else None
        total["ratio_with_continuity"] = round(total["consumed_with_continuity"] / total["eligible"], 6) if total["eligible"] else None
        result[str(replay)] = {"total": total, "projects": per}
        print(replay, json.dumps(total, ensure_ascii=False), flush=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
