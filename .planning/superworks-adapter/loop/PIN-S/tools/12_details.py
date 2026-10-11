"""PIN-S step 12: assemble details.json (population, classes, families, anchors, M3 block mapping test, M4, coverage).
Reads the intermediate summaries written by 08/09/11 and recomputes the population and family tables.
Usage: python -X utf8 12_details.py <out_details.json>"""
import collections, importlib.util, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
spec = importlib.util.spec_from_file_location("f9", HERE / "09_final.py")
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
OUT = Path(sys.argv[1])

pops = [r for r in F.M if r["in_replay"] and r["replay_category"] in F.INTERNAL and not r["replay_identity"] and not r["replay_part"]]
out = {"population": {}, "classes": {}, "families": {}, "anchors_and_links": {}, "M3_block_mapping": {}, "truth_precision": {},
       "coverage": {}, "presence": {}, "m4": {}}

# ---- population
out["population"] = {
    "popS_port_level_no_identity": len(pops),
    "by_category": dict(collections.Counter(r["replay_category"] for r in pops)),
    "label_valid": sum(1 for r in pops if r["replay_label"]),
    "label_missing": sum(1 for r in pops if not r["replay_label"]),
    "wire_contact": sum(1 for r in pops if r["replay_wire"]),
    "other_end": dict(collections.Counter(r["other_end"] for r in pops)),
    "round16_popS_for_reference": 35963,
    "block_families": len({r["block"] for r in pops}),
}

# ---- classes (09 rules, strict pin token v2)
cc = collections.Counter(F.cls_for(r)[0] for r in pops)
out["classes"] = dict(sorted(cc.items()))

# ---- families: class mix for top blocks
by = collections.defaultdict(collections.Counter)
for r in pops:
    by[r["block"]][F.cls_for(r)[0]] += 1
out["families"] = {b: {"n": sum(c.values()), "mix": dict(c.most_common())}
                   for b, c in sorted(by.items(), key=lambda t: -sum(t[1].values()))}

# ---- anchors and TERM_TEXT links on Pop-S
anc = [r for r in pops if r["anchors"]]
out["anchors_and_links"] = {
    "popS_with_TERMTEXTPOINT_anchor": len(anc),
    "anchor_class_mix": dict(collections.Counter(F.cls_for(r)[0] for r in anc)),
    "popS_with_TERM_TEXT_link_for_its_number": sum(1 for r in pops if r["term_link_for_number"] is not None),
    "popS_TERM_TEXT_link_resolved": sum(1 for r in pops if r["truth"] is not None),
}

# ---- M3: block family mapping number -> displayed text, leave-one-instance-out on metadata truth (TX + TI)
truth = [r for r in F.M if r["truth"] is not None and (not r["in_replay"] or r["replay_category"] in ("线圈", "接插件"))]
bynum = collections.defaultdict(list)
for r in truth:
    bynum[(r["block"], r["number"])].append((r["instance"], F.norm(r["truth"])))
hit = tot = 0
stable_pairs = 0
for key, items in bynum.items():
    if len({v for _, v in items}) == 1:
        stable_pairs += 1
    for i, (inst, v) in enumerate(items):
        others = [w for j, (_, w) in enumerate(items) if j != i]
        if not others:
            continue
        tot += 1
        mode = collections.Counter(others).most_common(1)[0][0]
        hit += int(mode == v)
out["M3_block_mapping"] = {"pairs_block_number": len(bynum), "pairs_single_valued": stable_pairs,
                           "leave_one_out_instances": tot, "leave_one_out_correct": hit,
                           "accuracy": round(hit / tot, 4) if tot else None,
                           "note": "number->displayed text is taken as constant per block family; accuracy on TX+TI truth"}

# ---- truth precision of the 09 classes (links removed)
out["truth_precision"] = {"TX_popX_component": json.load(open(WORK / "classify" / "final_summary.json", encoding="utf-8"))["truth_precision_TX"],
                          "TI_internal_metadata": json.load(open(WORK / "classify" / "final_summary.json", encoding="utf-8"))["truth_precision_TI"]}

# ---- coverage (round18 strict baseline) and upper bounds from 09
fs = json.load(open(WORK / "classify" / "final_summary.json", encoding="utf-8"))
out["coverage"] = {k: fs[k] for k in ("coverage_base", "coverage_gain_terminal_ports_by_class", "coverage_upper_bound_A_B",
                                      "coverage_upper_bound_A_B_D")}
out["coverage"]["note"] = ("upper bounds assume every accepted pin forms a pair with its uncovered terminal; "
                           "D-class precision on Pop-S is visually near 0 (see README), so only A+B is credible")

# ---- presence (08) and M4 (11)
out["presence"] = json.load(open(WORK / "classify" / "presence_summary.json", encoding="utf-8")) if (WORK / "classify" / "presence_summary.json").exists() else {}
out["m4"] = json.load(open(WORK / "classify" / "m4_summary.json", encoding="utf-8"))

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ("population", "classes", "M3_block_mapping", "anchors_and_links")}, ensure_ascii=False, indent=1)[:3500])
