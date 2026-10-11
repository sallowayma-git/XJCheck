"""PIN-S step 10: visual sample spec for the final classes of 09_final.py (seeded, stratified).
Usage: python -X utf8 10_spec_final.py <out_spec.json> <seed>"""
import collections, importlib.util, json, random, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sp = importlib.util.spec_from_file_location("f9", HERE / "09_final.py"); F = importlib.util.module_from_spec(sp); sp.loader.exec_module(F)
out = Path(sys.argv[1]); rng = random.Random(int(sys.argv[2]))
pops = [r for r in F.M if r["in_replay"] and r["replay_category"] in F.INTERNAL and not r["replay_identity"] and not r["replay_part"]]
by = collections.defaultdict(list)
for r in pops:
    k, c = F.cls_for(r); by[k].append((r, c))
plan = [("D_pin_3to9", 6), ("B_pin_le3", 4), ("E_text_le3_nonpin", 3), ("F_none_le9", 3), ("C_pin_contested", 2), ("A_anchor_ok", 2)]
specs = []
for cls, n in plan:
    for i, (r, c) in enumerate(rng.sample(by[cls], min(n, len(by[cls])))):
        specs.append({"name": f"Q_{cls[:2]}_{i+1}", "pid": r["pid"], "fid": r["fid"], "instance": r["instance"], "marker": r["marker"],
                      "cls": cls, "label": r["replay_label"] or "", "chosen": c[2] if c else None,
                      "note": f"{r['pid']}/{r['fid']} block {r['block']} number {r['number']} wire {r['replay_wire']} other_end {r['other_end']}"})
json.dump(specs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(specs), collections.Counter(s["cls"] for s in specs).most_common())
