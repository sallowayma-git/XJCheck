"""PIN-M5 step 3: diagnose 'no_match' rows (label present in layout, terminal present, no PCL pin reaches the
terminal). Classifies why the match fails, using round18 replay tables and the m5_pins output of 02.

Classes
  L_nofar     label L has no PCL row with a sw_port far identity at all (far identity unknown in layout)
  T_elsewhere terminal T is a far identity of this project, but on another label's part
  T_absent    terminal T is not a far identity of any PCL row in the project
  L_has_T     label L already reaches T (should not happen when status is no_match)
Usage: python -X utf8 03_diag_nomatch.py
"""
import pickle, re, collections, json
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_m5_work")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
rows = pickle.load(open(WORK / "m5_pins.pkl", "rb"))


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def key_id(s):
    return re.sub(r"[\s\-_~]", "", str(s or "")).upper()


part_label = {}
for part in T["parts"]:
    lab = part["label"] or {}
    part_label[(part["pid"], part["file_id"], part["insert_handle"])] = norm(lab.get("normalized") or lab.get("value"))

L_far = collections.defaultdict(set)   # (pid, L) -> far ids with sw_port identity
L_rows = collections.Counter()         # (pid, L) -> PCL rows
proj_far = collections.defaultdict(set)  # pid -> all far ids
for r in T["routes"]:
    if r["source_kind"] != "PCL":
        continue
    far = next((e for e in r["ends"] if e.get("role") == "FAR"), None) or {}
    L = part_label.get((r["pid"], r["file_id"], r["owner_handle"]))
    if not L:
        continue
    L_rows[(r["pid"], L)] += 1
    if far.get("identity_source") == "sw_port" and far.get("identity"):
        L_far[(r["pid"], L)].add(key_id(far["identity"]))
        proj_far[r["pid"]].add(key_id(far["identity"]))

cls_count = collections.Counter()
examples = collections.defaultdict(list)
for row in rows:
    if row["status"] != "no_match":
        continue
    pid, L, Ts = row["pid"], row["label"], set(row["T"])
    if not L_far.get((pid, L)):
        c = "L_nofar"
    elif any(t in proj_far[pid] for t in Ts):
        c = "T_elsewhere"
    else:
        c = "T_absent"
    key = (row["cls"], c)
    cls_count[key] += 1
    if len(examples[key]) < 8:
        examples[key].append({"pid": pid, "fid": row["fid"], "label": L, "T": sorted(Ts),
                              "L_far_sample": sorted(L_far.get((pid, L), set()))[:6], "L_rows": L_rows.get((pid, L), 0),
                              "device": row.get("device"), "record": row.get("record")})

for k, v in sorted(cls_count.items()):
    print(k, v)
out = {"counts": {f"{a}|{b}": v for (a, b), v in cls_count.items()},
       "examples": {f"{a}|{b}": v for (a, b), v in examples.items()}}
json.dump(out, open(WORK / "diag_nomatch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", WORK / "diag_nomatch.json")
