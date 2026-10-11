import json, collections
recs = json.load(open("F:/workspace/XJToolkit/.tmp/multiseg_work/cls870.json", encoding="utf-8"))
print("records", len(recs), "unique groups", len({(r["pid"], r["line_group_id"]) for r in recs}))
print("pieces", collections.Counter(r["n_pieces"] for r in recs))
print("lines", collections.Counter(r["n_lines"] for r in recs))
print("orient", collections.Counter(r["orientation"] for r in recs))
print("yspread>0.05", sum(1 for r in recs if r["yspread"] > 0.05))
# gap types
gt = collections.Counter()
gw = collections.Counter()
for r in recs:
    for g in r["gaps"]:
        kinds = []
        if g["is_candidate_gap"]:
            kinds.append("CAND")
        if g["termpoints"]:
            kinds.append("TP")
        for t in g["texts"]:
            kinds.append("T:" + t["kind"])
        if g["dots"]:
            kinds.append("DOT")
        if g["crossing_lines"]:
            kinds.append("CROSS")
        key = "+".join(sorted(set(kinds))) or "EMPTY"
        gt[key] += 1
        gw[(round(g["width"], 1) if g["width"] < 30 else "30+", g["is_candidate_gap"])] += 1
print("gap composition (top 40):")
for k, v in gt.most_common(40):
    print("  ", v, k)
print("gap widths (cand vs other):")
for k, v in sorted(gw.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))[:60]:
    print("  ", k, v)
# end tokens
et = collections.Counter()
for r in recs:
    for side in ("outer_left", "outer_right"):
        et[tuple(r["ends"][side])] += 1
print("outer end tokens:")
for k, v in et.most_common(25):
    print("  ", v, k)
# candidate gap count per record
print("candidate gap found", collections.Counter(sum(1 for g in r["gaps"] if g["is_candidate_gap"]) for r in recs))
# other gaps: how many non-candidate gaps per record
print("non-candidate gaps per record", collections.Counter(sum(1 for g in r["gaps"] if not g["is_candidate_gap"]) for r in recs))
# category of ports
cat = collections.Counter((r["category_a"], r["category_b"]) for r in recs)
print("category pair", cat.most_common(10))
