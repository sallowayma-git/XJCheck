"""Counterfactual: round13 code (before the source fix) with the rules.py 上接 fold disabled.

Compares .tmp/superworks_round13_full (as shipped) with .tmp/loop_stripname_r13norules (same code, fold off).
Run from the repository root. Prints per-project consumption, pair-status and issue deltas.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_stripname import load, _v

PIDS = ["p075", "p061", "p046", "p045", "p030", "p048"]
for pid in PIDS:
    r13 = load(".tmp/superworks_round13_full", pid)
    cf = load(".tmp/loop_stripname_r13norules", pid)
    cr = r13[2].set_index("port_id")
    cc = cf[2].set_index("port_id").reindex(cr.index)
    changed = int((cr.consumed.astype(bool) != cc.consumed.astype(bool)).sum())
    ap = r13[0].set_index("pair_id"); bp = cf[0].set_index("pair_id")
    st = sum(1 for k in ap.index.intersection(bp.index) if _v(ap.loc[k, "status"]) != _v(bp.loc[k, "status"]))
    lv = sum(1 for k in ap.index.intersection(bp.index) if _v(ap.loc[k, "left_value"]) != _v(bp.loc[k, "left_value"]))
    print(pid, "consumed round13", int(cr.consumed.sum()), "fold-off", int(cc.consumed.sum()),
          "ports changed", changed, "| pairs", len(ap), len(bp), "status changed", st,
          "left changed", lv, "| issues", len(r13[1]), len(cf[1]), flush=True)
