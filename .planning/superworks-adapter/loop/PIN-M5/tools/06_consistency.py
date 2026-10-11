"""PIN-M5 step 6: consistency metrics (read-only, round18 replay tables).

A  PCL far end (對端元件+端子号) resolvable to a known project terminal identity, by family.
   known = identities of 端子/装置端子 ports and terminal-strip rows of the project.
   resolved = far SW identity present, or far text identity (category 端子) known in the project.
F  forward connection check: schematic pin with label L and terminal set T; supported when some PCL row of a
   part labelled L reaches a terminal in T (sw identity, or text identity of a 端子 far end).
R  reverse connection check: PCL (part L, far terminal T) with a schematic pin of label L whose T contains T.
Usage: python -X utf8 06_consistency.py
"""
import pickle, re, collections, json
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_m5_work")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
FAM = D["family"]
rows = pickle.load(open(WORK / "m5_pins.pkl", "rb"))


def key_id(s):
    return re.sub(r"[\s\-_~]", "", str(s or "")).upper()


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


part_label = {}
for p in T["parts"]:
    lab = p["label"] or {}
    part_label[(p["pid"], p["file_id"], p["insert_handle"])] = norm(lab.get("normalized") or lab.get("value"))

known = collections.defaultdict(set)
for p in T["ports"]:
    if p["category"] in ("端子", "装置端子") and p.get("endpoint_identity"):
        known[p["pid"]].add(key_id(p["endpoint_identity"]))
for s in T["strips"]:
    if s.get("endpoint_identity"):
        known[s["pid"]].add(key_id(s["endpoint_identity"]))

# ---- A
A = collections.defaultdict(collections.Counter)
far_sets = collections.defaultdict(set)   # (pid, L) -> far terminal ids (sw or 端子-text)
for r in T["routes"]:
    if r["source_kind"] != "PCL":
        continue
    fam = FAM.get(r["pid"], "?")
    f = next((e for e in r["ends"] if e.get("role") == "FAR"), None)
    A[fam]["rows"] += 1
    if not f:
        A[fam]["no_far"] += 1
        continue
    sw = f.get("identity") if f.get("identity_source") == "sw_port" else None
    txt = f.get("far_text_identity")
    if sw:
        A[fam]["far_sw"] += 1
    if txt and key_id(txt) in known[r["pid"]]:
        A[fam]["text_known"] += 1
    ok = bool(sw) or bool(txt and key_id(txt) in known[r["pid"]])
    if ok:
        A[fam]["resolved"] += 1
    L = part_label.get((r["pid"], r["file_id"], r["owner_handle"]))
    if L:
        if sw:
            far_sets[(r["pid"], L)].add(key_id(sw))
        if txt and f.get("category") == "端子":
            far_sets[(r["pid"], L)].add(key_id(txt))

# ---- F: forward, per class and family
F = collections.defaultdict(collections.Counter)
for row in rows:
    if not row["label"] or not row["T"]:
        continue
    key = (row["cls"], FAM.get(row["pid"], "?"))
    if not row["label_in_layout"]:
        F[key]["label_not_in_layout"] += 1
        continue
    F[key]["eligible"] += 1
    if row["conn_supported"]:
        F[key]["supported"] += 1

# ---- R: reverse, per family
sch_pairs = collections.defaultdict(set)  # (pid, label) -> set of terminal ids of schematic pins
for row in rows:
    for t in row["T"]:
        sch_pairs[(row["pid"], row["label"])].add(t)
R = collections.Counter()
Rfam = collections.defaultdict(collections.Counter)
for (pid, L), fs in far_sets.items():
    fam = FAM.get(pid, "?")
    for t in fs:
        Rfam[fam]["layout_far_terminals"] += 1
        if t in sch_pairs.get((pid, L), set()):
            Rfam[fam]["supported_by_schematic"] += 1

out = {
    "A_by_family": {k: dict(v) for k, v in A.items()},
    "F_by_class_family": {f"{k[0]}|{k[1]}": dict(v) for k, v in F.items()},
    "R_by_family": {k: dict(v) for k, v in Rfam.items()},
}
json.dump(out, open(WORK / "consistency.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in A.items():
    n = v["rows"] - v.get("no_far", 0)
    print("A", k, dict(v), "resolved_rate", round(v.get("resolved", 0) / max(n, 1), 3))
for k, v in sorted(F.items()):
    print("F", k, dict(v))
for k, v in Rfam.items():
    print("R", k, dict(v))
