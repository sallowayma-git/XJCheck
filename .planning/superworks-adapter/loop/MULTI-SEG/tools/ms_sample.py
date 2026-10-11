"""MULTI-SEG: stratified visual sample of the 870 refused candidates (seed 20261011, read-only; writes JSON only).

Strata are the signatures of ms_signature.py. Large signatures get 5 cases, small ones get all, and the
branch/corner/dot family and the second-body family get one stratum each. Within a stratum the choice is seeded
random and spread over projects (round-robin over a shuffled project list), so one project does not dominate.
Output: .tmp/multiseg_work/sample_cases.json (list of {index, png, case}) for ms_render.py.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/multiseg_work")
SEED = 20261011
OUT = WORK / "sample_cases.json"


def stratum_of(sig: str):
    if sig == "UNREG|BODY-LBL|TERM":
        return "S1", 5
    if sig == "BLANK|BODY-LBL|TERM":
        return "S2", 5
    if sig == "ELEM|BODY-LBL|TERM":
        return "S3", 5
    if sig == "TERM|SYM-BODY|TERM":
        return "S4", 5
    if sig == "TERM|SYM-SYM-BODY|BRANCH":
        return "S5", 5
    if sig == "TERM|SYM-BODY-LBL|TERM":
        return "S6", 5
    if "BODY_O" in sig:
        return "S8", 4
    if "BRANCH" in sig or "CORNER" in sig or "DOT" in sig:
        return "S7", 5
    return "S9", 5


def main():
    recs = json.loads((WORK / "sig870.json").read_text(encoding="utf-8"))
    cls = json.loads((WORK / "cls870.json").read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    strata = defaultdict(list)
    for r, c in zip(recs, cls):
        name, _ = stratum_of(r["signature"])
        strata[name].append((r, c))
    picked = []
    quotas = {"S1": 5, "S2": 5, "S3": 5, "S4": 5, "S5": 5, "S6": 5, "S7": 5, "S8": 4, "S9": 5}
    for name in sorted(strata):
        items = strata[name]
        by_pid = defaultdict(list)
        for r, c in items:
            by_pid[r["pid"]].append((r, c))
        pids = sorted(by_pid)
        rng.shuffle(pids)
        for p in pids:
            rng.shuffle(by_pid[p])
        chosen = []
        while len(chosen) < min(quotas[name], len(items)):
            progressed = False
            for p in pids:
                if by_pid[p] and len(chosen) < quotas[name]:
                    chosen.append(by_pid[p].pop())
                    progressed = True
            if not progressed:
                break
        for r, c in chosen:
            picked.append((name, r, c))
    cases = []
    for idx, (name, r, c) in enumerate(picked):
        png = "MS_%02d.png" % (idx // 2 + 1)
        cases.append({"index": r["index"], "png": png, "case": {
            "pid": r["pid"], "file_id": r["file_id"], "sheet_id": r["sheet_id"], "identity": r["identity"],
            "line_group_id": r["line_group_id"], "port_a": c["port_a"], "port_b": c["port_b"],
            "signature": r["signature"], "sig_label": "stratum %s" % name, "index_label": "#%d" % r["index"],
            "y": c["y"], "pieces": c["n_pieces"]}})
    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = defaultdict(int)
    for name, r, _ in picked:
        counts[name] += 1
    print("sample", len(cases), dict(counts), "pngs", (len(cases) + 1) // 2)


if __name__ == "__main__":
    main()
