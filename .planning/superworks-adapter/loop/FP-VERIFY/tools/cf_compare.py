"""Read-only: compare counterfactual replay (.tmp/fp_verify_replay/cf_skipfix) against round25 and current, per project."""
import pandas as pd, glob, json, sys
from collections import Counter
R25 = "F:/workspace/XJToolkit/.tmp/superworks_round25_full/"
CUR = "F:/workspace/XJToolkit/.tmp/engine_coordination_full_acceptance/current/"
CF = "F:/workspace/XJToolkit/.tmp/fp_verify_replay/cf_skipfix/"
def fd(base, pid): return glob.glob(f"{base}{pid}/*/findings")[0] + "/"
def ld(base, pid):
    f = fd(base, pid)
    p = pd.read_parquet(f + "pairs.parquet")
    iss = pd.read_parquet(glob.glob(f"{base}{pid}/*/audit/issues.parquet")[0])
    return p, iss
def key(p):
    return set(zip(p.sheet_id.astype(str), p.left_value.astype(str), p.right_value.astype(str), p.left_text_id.astype(str), p.right_text_id.astype(str), p.pair_kind.astype(str)))
def lattice(p):
    return int(sum(1 for e in p.evidence if (json.loads(e) if isinstance(e, str) else (e or {})).get("component_submode") == "terminal_strip_lattice"))
pids = sys.argv[1:] or ["p016", "p017", "p018", "p019", "p020", "p021", "p064", "p068"]
tot = Counter()
for pid in pids:
    r, ri = ld(R25, pid); c, ci = ld(CUR, pid); f, fi = ld(CF, pid)
    rp, cp, fp = key(r[r.status == "pass"]), key(c[c.status == "pass"]), key(f[f.status == "pass"])
    row = dict(pid=pid, r25_pass=len(rp), cur_pass=len(cp), cf_pass=len(fp),
               cur_minus_r25=len(cp - rp), cf_minus_r25=len(fp - rp), r25_minus_cf=len(rp - fp),
               cur_lattice=lattice(c[c.status == "pass"]), cf_lattice=lattice(f[f.status == "pass"]),
               r25_issues=len(ri), cur_issues=len(ci), cf_issues=len(fi))
    print(row)
    for k, v in row.items():
        if isinstance(v, int): tot[k] += v
    print("   cf issue rules:", dict(Counter(fi.rule_id)), "| cur:", dict(Counter(ci.rule_id)))
print("TOTAL", dict(tot))
