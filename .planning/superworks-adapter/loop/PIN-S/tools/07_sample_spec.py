"""PIN-S step 7: stratified sample of markers for visual review (seeded), written as a render spec.

Strata: Pop-S classes (classifier of 05_classify), anchor-linked Pop-S, the largest Pop-S block families,
and metadata truth rows (TX Pop-X component, TP part definition) for reference.
Usage: python -X utf8 07_sample_spec.py <out_spec.json> [seed]
"""
import collections, json, random, sys, importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec_mod = importlib.util.spec_from_file_location("c5", HERE / "05_classify.py")
C5 = importlib.util.module_from_spec(spec_mod); spec_mod.loader.exec_module(C5)
M = C5.M
INTERNAL = C5.INTERNAL
out = Path(sys.argv[1])
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20261101
rng = random.Random(seed)

pops = [r for r in M if r["in_replay"] and r["replay_category"] in INTERNAL and not r["replay_identity"] and not r["replay_part"]]
by_cls = collections.defaultdict(list)
for r in pops:
    k, c = C5.classify(r)
    by_cls[k].append((r, c))
truth = {"TX": [], "TP": []}
for r in M:
    if r["truth"] is None:
        continue
    if not r["in_replay"]:
        truth["TX"].append(r)
    elif r["replay_part"] or r["truth_src"] == "definition_text_reference_block":
        truth["TP"].append(r)

plan = [
    ("B_model_owned", 5), ("C_contested", 3), ("E_nonpin_nearest", 5), ("H_far_only", 6), ("G_none", 4),
    ("A_anchor_ok", 3),
]
specs = []
def add(r, cls, chosen, name, note):
    specs.append({"name": name, "pid": r["pid"], "fid": r["fid"], "instance": r["instance"], "marker": r["marker"],
                  "cls": cls, "label": r["replay_label"] or "", "chosen": chosen, "note": note})

for cls, n in plan:
    rows = by_cls.get(cls, [])
    for i, (r, c) in enumerate(rng.sample(rows, min(n, len(rows)))):
        add(r, cls, c[2] if c else None, f"P_{cls[:3]}_{i+1}", f"{r['pid']}/{r['fid']} marker {r['marker']} number {r['number']} wire {r['replay_wire']}")
# anchor present but not accepted
anc_fail = [r for r in pops if r["anchors"] and C5.classify(r)[0] != "A_anchor_ok"]
for i, r in enumerate(rng.sample(anc_fail, min(3, len(anc_fail)))):
    add(r, "anchor_not_accepted", None, f"P_ANCFAIL_{i+1}", "TERMTEXTPOINT anchor present, not accepted")
# largest families
fam = collections.Counter(r["block"] for r in pops)
for blk, _n in fam.most_common(3):
    rows = [r for r in pops if r["block"] == blk]
    for i, r in enumerate(rng.sample(rows, 2)):
        k, c = C5.classify(r)
        add(r, "family_" + blk, c[2] if c else None, f"P_FAM_{blk[-3:]}_{i+1}", f"largest block {blk}, class {k}")
for i, r in enumerate(rng.sample(truth["TX"], 3)):
    k, c = C5.classify(r)
    add(r, "TX_truth_" + k, c[2] if c else None, f"T_TX_{i+1}", f"metadata truth {r['truth']!r} (link removed for classification)")
for i, r in enumerate(rng.sample(truth["TP"], 2)):
    k, c = C5.classify(r)
    add(r, "TP_truth_" + k, c[2] if c else None, f"T_TP_{i+1}", f"part definition truth {r['truth']!r}")
json.dump(specs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(specs), collections.Counter(s["cls"] for s in specs).most_common())
