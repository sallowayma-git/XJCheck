"""Read-only: align round25 and current (2594dbe) pairs by content; list new passes and ledger status.
Writes only to the output dir given by --out (under .tmp/fp_verify_*)."""
import argparse, json, glob, os
from collections import Counter, defaultdict
import pandas as pd

R25 = "F:/workspace/XJToolkit/.tmp/superworks_round25_full"
CUR = "F:/workspace/XJToolkit/.tmp/engine_coordination_full_acceptance/current"

def clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)): return None
    s = str(v).strip(); return s or None

def load(run):
    rows, ledger, issues = [], [], []
    for proj in sorted(glob.glob(os.path.join(run, "p[0-9][0-9][0-9]"))):
        pid = os.path.basename(proj)
        fd, = glob.glob(os.path.join(proj, "*", "findings"))
        pairs = pd.read_parquet(os.path.join(fd, "pairs.parquet"))
        for p in pairs.itertuples(index=False):
            rows.append(dict(project_id=pid, pair_id=p.pair_id, file_id=p.file_id, sheet_id=p.sheet_id,
                             status=p.status, pair_kind=p.pair_kind, left_value=clean(p.left_value),
                             right_value=clean(p.right_value), left_text_id=clean(p.left_text_id),
                             right_text_id=clean(p.right_text_id), line_group_id=clean(p.line_group_id),
                             confidence=p.confidence, evidence=p.evidence, rationale=p.rationale,
                             left_candidate_id=clean(p.left_candidate_id), right_candidate_id=clean(p.right_candidate_id), left_coord_x=p.left_coord_x, left_coord_y=p.left_coord_y, right_coord_x=p.right_coord_x, right_coord_y=p.right_coord_y, left_score=p.left_score, right_score=p.right_score, wire_score=p.wire_score,
                             selected_pair_candidate_id=clean(p.selected_pair_candidate_id)))
        sup = pd.read_parquet(os.path.join(fd, "superworks_supersession.parquet"))
        for e in sup.itertuples(index=False):
            ledger.append(dict(project_id=pid, element_key=e.element_key, category=e.category, reason=e.reason,
                               old_pair=e.old_pair, new_pairs=e.new_pairs))
        iss = pd.read_parquet(os.path.join(fd, "..", "audit", "issues.parquet"))
        for i in iss.to_dict("records"):
            i = {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in i.items()}
            i["project_id"] = pid
            issues.append(i)
    return pd.DataFrame(rows), ledger, issues

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    r, rl, ri = load(R25); c, cl, ci = load(CUR)
    r.to_pickle(os.path.join(a.out, "r25_pairs.pkl")); c.to_pickle(os.path.join(a.out, "cur_pairs.pkl"))
    pd.DataFrame(rl).to_pickle(os.path.join(a.out, "r25_ledger.pkl")); pd.DataFrame(cl).to_pickle(os.path.join(a.out, "cur_ledger.pkl"))
    pd.DataFrame(ri).to_pickle(os.path.join(a.out, "r25_issues.pkl")); pd.DataFrame(ci).to_pickle(os.path.join(a.out, "cur_issues.pkl"))
    print("r25 pairs", len(r), "cur pairs", len(c), "r25 issues", len(ri), "cur issues", len(ci))
    print("r25 status", r.status.value_counts().to_dict()); print("cur status", c.status.value_counts().to_dict())
