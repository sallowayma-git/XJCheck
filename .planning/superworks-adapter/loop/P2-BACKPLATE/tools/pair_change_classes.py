"""P2-BACKPLATE: classify every pair that changed between two replays (read-only).

Classes: J (backplate row misread superseded), I_after_prefix_fix (legacy duplicate of a same-sheet SW pass pair
that exists only because the corrected device prefix now matches it), I_other (other legacy duplicate), other
discard, identity_changed (status kept, endpoint text changed), status_changed_other, added / removed pair ids.
Usage: python pair_change_classes.py <base_root> <new_root> <out_json> [project ids ...]
"""
import sys, json, glob, os, collections
import pandas as pd

base, new, out_json = sys.argv[1:4]
only = set(sys.argv[4:])


def fpath(root, pid):
    h = glob.glob(os.path.join(root, pid, "*", "findings", "pairs.parquet"))
    return h[0] if h else None


summary = {}
totals = collections.Counter()
for pid_dir in sorted(glob.glob(os.path.join(new, "p[0-9][0-9][0-9]"))):
    pid = os.path.basename(pid_dir)
    if only and pid not in only:
        continue
    fb, fn = fpath(base, pid), fpath(new, pid)
    if not fb or not fn:
        continue
    b = pd.read_parquet(fb)
    n = pd.read_parquet(fn)
    bm = {r.pair_id: r for r in b.itertuples()}
    nm = {r.pair_id: r for r in n.itertuples()}
    c = collections.Counter()
    for pid_, r in nm.items():
        if pid_ not in bm:
            c["added"] += 1
            continue
        o = bm[pid_]
        if o.status == r.status:
            if (o.left_value, o.right_value) != (r.left_value, r.right_value):
                c["identity_changed(pass_kept)" if r.status == "pass" else "identity_changed(" + r.status + ")"] += 1
            continue
        key = f"{o.status}->{r.status}"
        rat = str(r.rationale or "")
        ev = r.evidence if isinstance(r.evidence, str) else ""
        if r.status == "review" and "backplate_row_misread" in ev:
            cls = "J_row_misread"
        elif r.status == "discard" and rat.startswith("backplate_row_misread"):
            cls = "J_row_misread"
        elif r.status == "discard" and rat.startswith("legacy_pair_duplicates_same_sheet_sw_pass"):
            changed = (o.left_value, o.right_value) != (r.left_value, r.right_value)
            cls = "I_after_identity_change" if changed else "I_other"
        elif r.status == "discard":
            cls = "other_discard:" + rat[:40]
        else:
            cls = "status_other:" + key
        c[cls] += 1
    for pid_ in bm:
        if pid_ not in nm:
            c["removed"] += 1
    summary[pid] = dict(c)
    totals.update(c)
json.dump(dict(per_project=summary, totals=dict(totals)), open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(dict(totals))
