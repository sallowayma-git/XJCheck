"""Read-only: match round25->current pass gains (425 lattice + 6 wire) to round25 ledger old pairs by unordered endpoint values.
Writes pickles into work dir. Usage: analysis_425.py WORKDIR"""
import json, sys, os
import pandas as pd
W = sys.argv[1].rstrip("/\\") + "/"
new = pd.read_pickle(W + "new_pass.pkl"); rl = pd.read_pickle(W + "r25_ledger.pkl"); r = pd.read_pickle(W + "r25_pairs.pkl")
def js(x):
    if x is None or (isinstance(x, float) and pd.isna(x)): return None
    return json.loads(x) if isinstance(x, str) else x
rows = []
for e in rl.itertuples(index=False):
    o = js(e.old_pair); news = js(e.new_pairs) or []
    if o:
        rows.append(dict(project_id=e.project_id, category=e.category, reason=e.reason, sheet_id=o.get("sheet_id"),
                         lv=o.get("left_value"), rv=o.get("right_value"), o_status=o.get("status"), element_key=e.element_key,
                         new_pairs=news))
L = pd.DataFrame(rows)
uk = lambda a, b: "|".join(sorted([str(a), str(b)]))
L["ukey"] = [uk(a, b) for a, b in zip(L.lv, L.rv)]
new["ukey"] = [uk(a, b) for a, b in zip(new.left_value, new.right_value)]
M = new.merge(L[["project_id", "sheet_id", "ukey", "category", "reason", "o_status", "element_key", "new_pairs"]],
              on=["project_id", "sheet_id", "ukey"], how="left")
M.to_pickle(W + "gain_matched.pkl")
print("gain rows", len(new), "matched rows", len(M))
print(M.groupby(["pair_kind", "category", "reason", "o_status"], dropna=False).size().to_string())
print("unique gain pairs matched:", M.groupby("pair_id").category.apply(lambda s: s.notna().any()).sum(), "of", new.pair_id.nunique())
