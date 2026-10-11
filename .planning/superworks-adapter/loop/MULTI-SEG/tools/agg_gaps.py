import json, collections
recs = json.load(open("F:/workspace/XJToolkit/.tmp/multiseg_work/cls870.json", encoding="utf-8"))
cls = collections.Counter()
ex = collections.defaultdict(list)
for i, r in enumerate(recs):
    for g in r["gaps"]:
        if g["is_candidate_gap"]:
            continue
        tp_cats = sorted({t["category"] for t in g["termpoints"]})
        same_ident = sum(1 for t in g["termpoints"] if t["identity"] == r["identity"])
        other_dev = sum(1 for t in g["termpoints"] if t["category"] == "装置端子" and t["identity"] != r["identity"])
        tk = sorted({t["kind"] for t in g["texts"]})
        wb = "w<=2.5" if g["width"] <= 2.6 else ("w~10" if 9 <= g["width"] <= 11 else ("w~18.8" if 17 <= g["width"] <= 19 else "w_other"))
        key = (wb, "TP:" + "/".join(tp_cats) if tp_cats else "noTP", "X" if g["crossing_lines"] else "-", "D" if g["dots"] else "-",
               "txt:" + "/".join(tk) if tk else "notxt", "sameID=%d" % same_ident if same_ident else "")
        cls[key] += 1
        if len(ex[key]) < 3:
            ex[key].append((i, r["pid"], r["line_group_id"]))
for k, v in cls.most_common():
    print(v, k, ex[k][:2])
