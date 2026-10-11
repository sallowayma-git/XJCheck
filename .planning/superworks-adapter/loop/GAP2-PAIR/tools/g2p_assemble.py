"""Assemble GAP2-PAIR details.json: the 20 sampled cases plus the counts, checks, simulation and gain summaries.

Usage: python g2p_assemble.py <details.json (cases list, rewritten)> <work_dir> <out_details.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(cases_path: Path, work: Path, out: Path):
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    counts = json.loads((work / "counts.json").read_text(encoding="utf-8"))
    checks = json.loads((work / "checks.json").read_text(encoding="utf-8"))
    sim_total = json.loads((work / "sim" / "sim_total.json").read_text(encoding="utf-8"))
    gain = json.loads((work / "sim" / "sim_gain.json").read_text(encoding="utf-8"))
    doc = {
        "scope": "GAP-2 2a/2b population (3028 uncovered device terminals, round19)",
        "baseline": "round19 = HEAD before uncommitted G1P (no unregistered-symbol data in round19)",
        "population_counts": counts,
        "checks": checks,
        "simulation_total_corpus_77": sim_total,
        "method_S_gain": {k: v for k, v in gain.items() if k != "by_project"},
        "cases_sampled": cases,
        "cases_note": "20 stratified cases (2a 10, 2b 10), seed 20261011; PNG GAP2P_01..10 hold two cases each (wide + zoom).",
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("wrote", out, len(cases), "cases")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
