"""Pair-level deltas of a candidate replay against a base run (read-only).

usage: python -X utf8 pair_delta.py <base_root> <cand_root> <pid> [pid ...]
Prints, over all given projects: pair counts by (pair_kind, status) delta, the removed ordinary discards grouped
by rationale, and how native SuperWORKS component rows agree with the base on line_group_id (matched by content).
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


def evidence(e):
    if isinstance(e, str):
        try:
            return json.loads(e)
        except Exception:
            return {}
    return e or {}


def native_rows(pairs):
    pass_rows = pairs[pairs.status == "pass"]
    mask = pass_rows.evidence.map(lambda e: evidence(e).get("component_submode") == "superworks_connect_line_port")
    out = {}
    for r in pass_rows[mask].itertuples():
        group = None if pd.isna(r.line_group_id) else str(r.line_group_id)
        key = (str(r.sheet_id), str(r.left_value), str(r.right_value), str(r.left_text_id), str(r.right_text_id))
        out.setdefault(key, []).append(group)
    return out


def main(argv):
    base_root, cand_root, pids = argv[0], argv[1], argv[2:]
    kinds = Counter()
    removed_discards = Counter()
    agree = Counter()
    for pid in pids:
        b = pd.read_parquet(os.path.join(project_dir(base_root, pid), "findings", "pairs.parquet"))
        c = pd.read_parquet(os.path.join(project_dir(cand_root, pid), "findings", "pairs.parquet"))
        cb = Counter(zip(b.pair_kind.astype(str), b.status.astype(str)))
        cc = Counter(zip(c.pair_kind.astype(str), c.status.astype(str)))
        for key in set(cb) | set(cc):
            if cc.get(key, 0) != cb.get(key, 0):
                kinds[key] += cc.get(key, 0) - cb.get(key, 0)
        disc = lambda d: d[(d.pair_kind == "ordinary_pair") & (d.status == "discard")]
        gone = Counter(zip(disc(b).sheet_id.astype(str), disc(b).left_value.astype(str), disc(b).right_value.astype(str),
                           disc(b).left_text_id.astype(str), disc(b).right_text_id.astype(str), disc(b).rationale.astype(str)))
        kept = Counter(zip(disc(c).sheet_id.astype(str), disc(c).left_value.astype(str), disc(c).right_value.astype(str),
                           disc(c).left_text_id.astype(str), disc(c).right_text_id.astype(str), disc(c).rationale.astype(str)))
        for key, n in (gone - kept).items():
            removed_discards[key[5]] += n
        nb, nc = native_rows(b), native_rows(c)
        for key in set(nb) & set(nc):
            bg, cg = sorted(map(str, nb[key])), sorted(map(str, nc[key]))
            agree["native_rows"] += len(nc[key])
            agree["same_group_list"] += bg == cg
            agree["base_has_group_cand_none"] += sum(1 for g in nb[key] if g) > sum(1 for g in nc[key] if g)
            agree["cand_has_group_base_none"] += sum(1 for g in nc[key] if g) > sum(1 for g in nb[key] if g)
    print("pair (kind,status) delta cand-base:")
    for key, n in sorted(kinds.items()):
        print(f"  {key}: {n:+d}")
    print("ordinary discards removed, by rationale:", sum(removed_discards.values()))
    for rationale, n in removed_discards.most_common(10):
        print(f"  {n:4d}  {rationale}")
    print("native component rows (pass) vs base, matched by content:", dict(agree))


if __name__ == "__main__":
    main(sys.argv[1:])
