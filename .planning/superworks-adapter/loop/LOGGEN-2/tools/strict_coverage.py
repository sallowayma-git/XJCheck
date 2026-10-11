"""Strict coverage (COV-GAP layer b, terminal ports) of one replay directory, over every project.

Usage: python strict_coverage.py <replay_dir> <out_json>

Reads each project's findings/sw_port_coverage.parquet, the table written by the production
artifacts. Eligible = terminal (端子 / 装置端子) port with wire contact and resolved label. Consumed
= a non-discard production pair whose SuperWORKS side names the port and whose side value equals
the endpoint identity (the production 'consumed'). Pass-consumed counts only pass pairs.
Also reports the per-project counts so the ten-project and full-corpus numbers can be compared.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

TERMINAL = {"端子", "装置端子"}


def main(replay: Path, out: Path) -> None:
    per_project = {}
    totals = {"eligible": 0, "consumed": 0, "consumed_pass": 0, "projects": 0}
    for complete in sorted(replay.glob("p*/complete.json")):
        pid = complete.parent.name
        project_dir = Path(json.loads(complete.read_text(encoding="utf-8"))["project_dir"])
        coverage = pd.read_parquet(project_dir / "findings/sw_port_coverage.parquet")
        terminal = coverage[coverage.category.isin(TERMINAL) & coverage.eligible.astype(bool)]
        consumed = int(terminal.consumed.astype(bool).sum())
        consumed_pass = int(terminal["pass"].astype(bool).sum()) if "pass" in terminal else None
        per_project[pid] = {"eligible": int(len(terminal)), "consumed": consumed, "consumed_pass": consumed_pass}
        totals["eligible"] += len(terminal)
        totals["consumed"] += consumed
        totals["consumed_pass"] += consumed_pass or 0
        totals["projects"] += 1
    totals["ratio"] = totals["consumed"] / totals["eligible"] if totals["eligible"] else None
    totals["ratio_pass"] = totals["consumed_pass"] / totals["eligible"] if totals["eligible"] else None
    out.write_text(json.dumps({"total": totals, "projects": per_project}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(totals, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
