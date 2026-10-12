"""P2-BACKPLATE replay comparison (read-only). Compares a base replay with a new replay per project:
corroboration count, candidate count, pair status changes (pair_id keyed), non-corroboration evidence changes,
and issue differences keyed by (rule_id, message, sheet_id, filename).
Usage: python compare_replay.py <base_root> <new_root> <out_json> [project ids ...]
"""
import sys, json, glob, os, math, collections
import pandas as pd

base, new, out_json = sys.argv[1:4]
only = set(sys.argv[4:])


def findings(root, pid):
    hits = glob.glob(os.path.join(root, pid, "*", "findings"))
    return hits[0] if hits else None


def issues_of(root, pid):
    hits = glob.glob(os.path.join(root, pid, "*", "audit", "issues.json"))
    if not hits:
        return []
    rows = json.load(open(hits[0], encoding="utf-8"))
    return [(r.get("rule_id"), r.get("message"), r.get("sheet_id"), r.get("filename"), r.get("status"), r.get("severity")) for r in rows]


def evidence(s):
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s) if isinstance(s, str) and s else {}
    except Exception:
        return {}


summary = collections.OrderedDict()
projects = sorted(os.path.basename(p) for p in glob.glob(os.path.join(new, "p[0-9][0-9][0-9]")))
for pid in projects:
    if only and pid not in only:
        continue
    fb, fn = findings(base, pid), findings(new, pid)
    if not fb or not fn or not os.path.exists(os.path.join(new, pid, "complete.json")):
        continue
    pb = pd.read_parquet(os.path.join(fb, "pairs.parquet"))
    pn = pd.read_parquet(os.path.join(fn, "pairs.parquet"))
    eb = {r.pair_id: (r.status, evidence(r.evidence)) for r in pb.itertuples()}
    en = {r.pair_id: (r.status, evidence(r.evidence)) for r in pn.itertuples()}
    status_changes = collections.Counter()
    evidence_changes_other = 0
    corroborated = 0
    for pid_, (st, ev) in en.items():
        if "sw_backplate_corroboration" in ev:
            corroborated += 1
        if pid_ not in eb:
            status_changes["added:" + str(st)] += 1
            continue
        bst, bev = eb[pid_]
        if bst != st:
            status_changes[f"{bst}->{st}"] += 1
        ev_wo = {k: v for k, v in ev.items() if k != "sw_backplate_corroboration"}
        if ev_wo != bev:
            evidence_changes_other += 1
    for pid_ in eb:
        if pid_ not in en:
            status_changes["removed:" + str(eb[pid_][0])] += 1
    cand_path = os.path.join(fn, "sw_backplate_contradictions.parquet")
    cands = pd.read_parquet(cand_path) if os.path.exists(cand_path) else pd.DataFrame()
    ib, inew = issues_of(base, pid), issues_of(new, pid)
    cb, cn = collections.Counter(ib), collections.Counter(inew)
    added = sorted((cn - cb).elements(), key=str)
    removed = sorted((cb - cn).elements(), key=str)
    summary[pid] = dict(
        pairs_base=len(pb), pairs_new=len(pn),
        bp_pass_base=int(sum(1 for s, ev in eb.values() if s == "pass" and (ev.get("table_mapping") or {}).get("mapping_mode") == "backplate_virtual_table")),
        corroborated=corroborated,
        candidates=len(cands),
        candidate_types=dict(collections.Counter(cands.contradiction_type)) if len(cands) else {},
        status_changes=dict(status_changes),
        evidence_changes_other_than_corroboration=evidence_changes_other,
        issues_base=len(ib), issues_new=len(inew),
        issues_added=[list(x) for x in added], issues_removed=[list(x) for x in removed])
    print(pid, "corr", corroborated, "cand", len(cands), "status", dict(status_changes),
          "ev_other", evidence_changes_other, "issues", len(ib), "->", len(inew), flush=True)
json.dump(summary, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
print("wrote", out_json)
