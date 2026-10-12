"""Pair breakdown between two replay roots (read-only): added / removed / status-changed, by kind and status.

usage: wb_pairs_breakdown.py BASE_ROOT NEW_ROOT OUT_JSON p001 p003 ...
Keys are content keys (sheet, left, right, pair_kind); the status of each side is kept, so a status change shows up
as one removed row and one added row with the same content key.
"""
import glob, json, sys
from collections import Counter
from pathlib import Path

import pandas as pd

base, new, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
pids = sys.argv[4:]


def load(root: Path, pid: str) -> pd.DataFrame:
    d = glob.glob(str(root / pid / "*" / "findings"))[0]
    df = pd.read_parquet(d + "/pairs.parquet")
    df["left_value"] = df.left_value.map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    df["right_value"] = df.right_value.map(lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    df["ckey"] = list(zip(df.sheet_id, df.left_value, df.right_value, df.pair_kind))
    return df


added, removed, changed = Counter(), Counter(), Counter()
examples = {"added": [], "removed": [], "changed": []}
for pid in pids:
    b, n = load(base, pid), load(new, pid)
    bc = Counter(zip(b.ckey, b.status))
    nc = Counter(zip(n.ckey, n.status))
    keys_b = Counter(b.ckey)
    keys_n = Counter(n.ckey)
    for (k, st), v in (nc - bc).items():
        if keys_b.get(k, 0) and any(s2 == st for (k2, s2) in bc if k2 == k):
            continue
        if keys_b.get(k, 0):
            changed[("new_status", st)] += v
        else:
            added[(st, k[3])] += v
            if len(examples["added"]) < 400:
                examples["added"].append([pid, *k, st])
    for (k, st), v in (bc - nc).items():
        if keys_n.get(k, 0) and any(s2 == st for (k2, s2) in nc if k2 == k):
            continue
        if keys_n.get(k, 0):
            changed[("old_status", st)] += v
        else:
            removed[(st, k[3])] += v
            if len(examples["removed"]) < 400:
                examples["removed"].append([pid, *k, st])
result = {"added_by_status_kind": {f"{s}|{kind}": v for (s, kind), v in added.most_common()},
          "removed_by_status_kind": {f"{s}|{kind}": v for (s, kind), v in removed.most_common()},
          "status_changed": {f"{a}|{b}": v for (a, b), v in changed.items()},
          "totals": {"added": sum(added.values()), "removed": sum(removed.values())},
          "examples": examples}
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "examples"}, ensure_ascii=False, indent=2))
