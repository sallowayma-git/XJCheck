"""Read-only analysis of pickles from build_diff.py: find current passes absent as passes in round25."""
import json, sys, os
import pandas as pd
from collections import Counter
W = sys.argv[1]
r = pd.read_pickle(os.path.join(W, "r25_pairs.pkl")); c = pd.read_pickle(os.path.join(W, "cur_pairs.pkl"))
rl = pd.read_pickle(os.path.join(W, "r25_ledger.pkl")); cl = pd.read_pickle(os.path.join(W, "cur_ledger.pkl"))
KEY = ["project_id", "file_id", "sheet_id", "left_value", "right_value", "left_text_id", "right_text_id"]
def k(df): return pd.Series(["|".join("" if pd.isna(v) else str(v) for v in t) for t in df[KEY].itertuples(index=False)], index=df.index)
r["k"] = k(r); c["k"] = k(c)
rp = set(r.loc[r.status == "pass", "k"]); cp = c[c.status == "pass"]
new = cp[~cp.k.isin(rp)]
print("current pass not pass in r25 (by content):", len(new))
print("kind:", new.pair_kind.value_counts().to_dict())
print("project:", new.project_id.value_counts().head(30).to_dict())
print("n unique projects:", new.project_id.nunique())
# r25 status for same key
r_by_k = r.groupby("k").status.agg(lambda s: tuple(sorted(s)))
print("r25 status of same content key:", Counter(r_by_k.reindex(new.k).fillna("ABSENT").map(str)).most_common(10))
# r25 pair_id for the same key (any status)
r_ids = r.groupby("k").pair_id.first()
new_r25_id = new.k.map(r_ids)
print("new with an r25 pair of same key:", new_r25_id.notna().sum())
new.to_pickle(os.path.join(W, "new_pass.pkl"))
# ledger: map r25 old pair ids
led = []
for e in rl.itertuples(index=False):
    old = None if e.old_pair is None or (isinstance(e.old_pair, float)) else json.loads(e.old_pair) if isinstance(e.old_pair, str) else e.old_pair
    led.append((e.project_id, e.category, e.reason, old["pair_id"] if isinstance(old, dict) else None))
L = pd.DataFrame(led, columns=["project_id", "category", "reason", "old_pid"])
print("ledger category x reason:\n", L.groupby(["category", "reason"]).size().to_string())
newids = set(new_r25_id.dropna())
old_ids_in_ledger = L[L.old_pid.notna()]
rr = r.set_index("pair_id")
cand = []
for pid, row in r.iterrows() if False else []: pass
# ledger rows whose old pair is the r25 pair with the content key of a new pass
hit = L.merge(r[["project_id", "pair_id", "k", "status"]], left_on=["project_id", "old_pid"], right_on=["project_id", "pair_id"], how="left")
hit["is_new"] = hit.k.isin(set(new.k))
print("ledger old pair -> is one of the new passes (content):\n", hit.groupby(["category", "reason", "is_new"]).size().to_string())
hit.to_pickle(os.path.join(W, "ledger_old_hit.pkl"))
