"""Read-only comparison of replay outputs for the FP-FIX change set.

usage: python -X utf8 compare_fix.py <base_root> <cand_root> [pid ...] [--json out.json]
Roots are directories whose children are project ids (p000 ...) each holding one project dir.
Pass identity is content based (sheet, values, text ids, kind) because pair_id is renumbered between runs.
Issue identity is (rule_id, sheet_id, message). Nothing is read from or written to the source tree.
"""
import glob
import json
import os
import sys
from collections import Counter

import pandas as pd

ISSUE_RULES = ("R-SUPERWORKS-CONFLICT", "R-PAIR-LOW-CONFIDENCE", "R-RECOGNITION-GAP")


def project_dir(root, pid):
    """The run directory under a project id: the child that holds findings/ (cache/ and logs/ are siblings)."""
    for hit in sorted(glob.glob(os.path.join(root, pid, "*", ""))):
        if os.path.isdir(os.path.join(hit, "findings")):
            return hit
    return None


def is_lattice(evidence):
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except Exception:
            return False
    return (evidence or {}).get("component_submode") == "terminal_strip_lattice"


def load(root, pid):
    d = project_dir(root, pid)
    if d is None:
        return None
    pairs = pd.read_parquet(os.path.join(d, "findings", "pairs.parquet"))
    issues = pd.read_parquet(os.path.join(d, "audit", "issues.parquet"))
    return pairs, issues


def pass_keys(pairs):
    p = pairs[pairs.status == "pass"]
    return Counter(zip(p.sheet_id.astype(str), p.left_value.astype(str), p.right_value.astype(str),
                       p.left_text_id.astype(str), p.right_text_id.astype(str), p.pair_kind.astype(str)))


def lattice_count(pairs):
    p = pairs[pairs.status == "pass"]
    return int(sum(1 for e in p.evidence if is_lattice(e)))


def issue_keys(issues):
    return Counter(zip(issues.rule_id.astype(str), issues.sheet_id.astype(str), issues.message.astype(str)))


def main(argv):
    out_json = None
    if "--json" in argv:
        i = argv.index("--json")
        out_json = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    base, cand = argv[0], argv[1]
    pids = argv[2:] or sorted(os.path.basename(p.rstrip(os.sep)) for p in glob.glob(os.path.join(cand, "p*")))
    report = {}
    totals = Counter()
    for pid in pids:
        b, c = load(base, pid), load(cand, pid)
        if b is None or c is None:
            report[pid] = {"missing": True, "base": b is not None, "cand": c is not None}
            continue
        bp, bi = b
        cp, ci = c
        bk, ck = pass_keys(bp), pass_keys(cp)
        lost = bk - ck
        gained = ck - bk
        bl, cl = lattice_count(bp), lattice_count(cp)
        bis, cis = issue_keys(bi), issue_keys(ci)
        rules_b = Counter(bi.rule_id.astype(str))
        rules_c = Counter(ci.rule_id.astype(str))
        row = {
            "pass_base": sum(bk.values()), "pass_cand": sum(ck.values()),
            "pass_lost": sum(lost.values()), "pass_gained": sum(gained.values()),
            "lattice_base": bl, "lattice_cand": cl,
            "issues_base": len(bi), "issues_cand": len(ci),
            "issues_lost": sum((bis - cis).values()), "issues_gained": sum((cis - bis).values()),
            "rules_base": {r: rules_b.get(r, 0) for r in ISSUE_RULES},
            "rules_cand": {r: rules_c.get(r, 0) for r in ISSUE_RULES},
            "lost_samples": [list(k) + [v] for k, v in list(lost.items())[:8]],
            "gained_samples": [list(k) + [v] for k, v in list(gained.items())[:8]],
            "gained_issue_by_rule_sheet": dict(Counter(f"{k[0]}|{k[1]}" for k in (cis - bis).elements())),
            "lost_issue_by_rule_sheet": dict(Counter(f"{k[0]}|{k[1]}" for k in (bis - cis).elements())),
        }
        report[pid] = row
        for key in ("pass_base", "pass_cand", "pass_lost", "pass_gained", "lattice_base", "lattice_cand",
                    "issues_base", "issues_cand", "issues_lost", "issues_gained"):
            totals[key] += row[key]
        print(f"{pid} pass {row['pass_base']}->{row['pass_cand']} (-{row['pass_lost']} +{row['pass_gained']}) "
              f"lattice {bl}->{cl} issues {row['issues_base']}->{row['issues_cand']} "
              f"(-{row['issues_lost']} +{row['issues_gained']}) "
              f"SWCONF {row['rules_base']['R-SUPERWORKS-CONFLICT']}->{row['rules_cand']['R-SUPERWORKS-CONFLICT']} "
              f"LOWCONF {row['rules_base']['R-PAIR-LOW-CONFIDENCE']}->{row['rules_cand']['R-PAIR-LOW-CONFIDENCE']} "
              f"GAP {row['rules_base']['R-RECOGNITION-GAP']}->{row['rules_cand']['R-RECOGNITION-GAP']}", flush=True)
    print("TOTAL", dict(totals))
    if out_json:
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump({"total": dict(totals), "projects": report}, fh, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1:])
