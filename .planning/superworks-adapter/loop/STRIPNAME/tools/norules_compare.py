"""Experiment A: fixed code (v2) with and without the rules.py 上接 fold, field-by-field.

Run from the repository root. Prints per-project pair/field/issue/consumption differences.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_stripname import load, _v

A, B = ".tmp/loop_stripname_v2", ".tmp/loop_stripname_v2_norules"
PIDS = ["p075", "p061", "p046", "p045", "p030", "p048"]
tot = dict(pairs=0, missing=0, status=0, left=0, right=0, kind=0, issues_diff=0, ports_diff=0)
for pid in PIDS:
    a, b = load(A, pid), load(B, pid)
    ap, bp = a[0].set_index("pair_id"), b[0].set_index("pair_id")
    tot["pairs"] += len(ap)
    tot["missing"] += len(set(ap.index) ^ set(bp.index))
    for k in ap.index.intersection(bp.index):
        for f, key in [("status", "status"), ("left_value", "left"), ("right_value", "right"), ("pair_kind", "kind")]:
            if _v(ap.loc[k, f]) != _v(bp.loc[k, f]):
                tot[key] += 1
    ia = sorted(map(str, a[1])); ib = sorted(map(str, b[1]))
    if ia != ib:
        tot["issues_diff"] += 1
    ca = a[2].set_index("port_id"); cb = b[2].set_index("port_id").reindex(ca.index)
    tot["ports_diff"] += int((ca.consumed.astype(bool) != cb.consumed.astype(bool)).sum())
    print(pid, "pairs", len(ap), len(bp), "issues", len(a[1]), len(b[1]), "consumed", int(ca.consumed.sum()), int(cb.consumed.sum()), flush=True)
print(tot)
