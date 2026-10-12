"""Summarise compare_runs.py output: status deltas, category I by kind/page, coverage deltas."""
import json
import sys
from collections import Counter

d = json.load(open(sys.argv[1], encoding="utf-8"))
tot_delta = Counter()
tot_I = Counter()
print("pid | status deltas (base->new, nonzero) | coverage strict base->new | with_continuity")
for pid, item in d.items():
    if "base" not in item:
        print(pid, item)
        continue
    b, n = item["base"], item["new"]
    deltas = {}
    for k in sorted(set(b["pair_status"]) | set(n["pair_status"])):
        diff = n["pair_status"].get(k, 0) - b["pair_status"].get(k, 0)
        if diff:
            deltas[k] = diff
            tot_delta[k] += diff
    for k, v in n["category_I_by_kind_page"].items():
        tot_I[k] += v
    cb = b["coverage"]["port_coverage"] or {}
    cn = n["coverage"]["port_coverage"] or {}
    wb = b["coverage"]["port_coverage_with_continuity"] or {}
    wn = n["coverage"]["port_coverage_with_continuity"] or {}
    print(pid, deltas, "|", (cb.get("consumed"), cb.get("eligible"), cb.get("pass")), "->",
          (cn.get("consumed"), cn.get("eligible"), cn.get("pass")), "|", (wb.get("consumed")), "->", (wn.get("consumed")),
          "| supersession cats base", b["supersession_categories"], "new", n["supersession_categories"])
print("TOTAL status deltas:", dict(tot_delta))
print("TOTAL category I by kind|page:", dict(tot_I), "sum", sum(tot_I.values()))
