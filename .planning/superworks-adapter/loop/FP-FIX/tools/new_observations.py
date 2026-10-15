"""List resolution observations present in a candidate run but not in a base run, for one project.

usage: python -X utf8 new_observations.py <base_root> <cand_root> <pid> [--src <snapshot src dir>]
With --src, each new observation's two ends are checked with superworks_device_internal.device_internal_verdict
(the device-internal rule, imported from that snapshot so the check matches the replay).
"""
import glob
import json
import os
import sys
from collections import Counter

import pandas as pd


def project_dir(root, pid):
    for hit in sorted(glob.glob(os.path.join(root, pid, "*", ""))):
        if os.path.isdir(os.path.join(hit, "findings")):
            return hit
    raise SystemExit(f"no findings under {root}/{pid}")


def as_obj(value):
    if value is None or (isinstance(value, float) and value != value):
        return None
    return json.loads(value) if isinstance(value, str) else value


def side_for_rule(symbols, side):
    label = (symbols.get(side.get("symbol_id")) or {})
    return {"category": side.get("category") or "", "label": label.get("normalized") or "",
            "label_resolved": bool(label.get("resolved")), "identity": side.get("value") or "",
            "unregistered": False}


def main(argv):
    src = None
    if "--src" in argv:
        i = argv.index("--src")
        src = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    base_root, cand_root, pid = argv[:3]
    base, cand = project_dir(base_root, pid), project_dir(cand_root, pid)
    if src:
        sys.path.insert(0, src)
        from dwg_audit.audit.superworks_device_internal import device_internal_verdict
    symbols = {}
    if src:
        sy = pd.read_parquet(os.path.join(cand, "findings", "sw_symbols.parquet"))
        symbols = {r.record_id: as_obj(r.label) or {} for r in sy.itertuples()}
    b = pd.read_parquet(os.path.join(base, "findings", "sw_resolution_observations.parquet"))
    c = pd.read_parquet(os.path.join(cand, "findings", "sw_resolution_observations.parquet"))
    seen = set(zip(b.object_key.astype(str), b.state.astype(str)))
    new = c[[(k, s) not in seen for k, s in zip(c.object_key.astype(str), c.state.astype(str))]]
    verdicts = Counter()
    for r in new.itertuples():
        left, right = as_obj(r.left) or {}, as_obj(r.right) or {}
        reasons = as_obj(r.reason_codes) or []
        verdict = "not_checked"
        if src:
            verdict = "no_device_terminal_side"
            for term, other in ((left, right), (right, left)):
                if term.get("category") == "装置端子":
                    verdict = device_internal_verdict(side_for_rule(symbols, term), side_for_rule(symbols, other))
                    break
        verdicts[verdict] += 1
        print(r.state, reasons, r.sheet_id, r.object_key[:90])
        print("   L", left.get("category"), left.get("symbol_id"), "value=", left.get("value"))
        print("   R", right.get("category"), right.get("symbol_id"), "value=", right.get("value"), "=>", verdict)
    print("new observations:", len(new), dict(verdicts))


if __name__ == "__main__":
    main(sys.argv[1:])
