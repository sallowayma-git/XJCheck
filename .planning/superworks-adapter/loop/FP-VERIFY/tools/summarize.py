"""Read-only summary of FP-VERIFY results -> tools/results.json (numbers quoted in README)."""
import json, glob
import pandas as pd
from collections import Counter
W = "F:/workspace/XJToolkit/.tmp/fp_verify_work/"
OUT = "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/FP-VERIFY/tools/results.json"
res = {}
lt = pd.read_pickle(W + "lattice_test.pkl").drop_duplicates(["project_id", "pair_id"])
res["lattice_425"] = {
    "unique_pairs": int(len(lt)),
    "per_project": {k: int(v) for k, v in lt.groupby("project_id").size().items()},
    "per_sheet": {f"{k[0]}|{k[1]}": int(v) for k, v in lt.groupby(["project_id", "sheet_id"]).size().items()},
    "same_row": int(lt.same_row.sum()),
    "native_through_wire": int((lt.native_through > 0).sum()),
    "lg_member_TSB14_virtual_border": int((lt.lg_member_src == "TSB-14").sum()),
    "both_labels_sw_pass_covered": int(((lt.sw_left == 1) & (lt.sw_right == 1)).sum()),
}
gain = pd.read_pickle(W + "new_pass.pkl").drop_duplicates(["project_id", "pair_id"])
res["gain_pass_r25_to_cur"] = {"total": int(len(gain)), "by_kind": {k: int(v) for k, v in gain.pair_kind.value_counts().items()}}
ci = pd.read_pickle(W + "cur_issues.pkl"); ri = pd.read_pickle(W + "r25_issues.pkl")
res["issues"] = {"r25_total": int(len(ri)), "cur_total": int(len(ci)),
                 "r25_by_rule": dict(Counter(ri.rule_id)), "cur_by_rule": dict(Counter(ci.rule_id))}
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])
