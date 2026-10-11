"""PIN-M5 step 5: strict-coverage what-if for the M5 pins (read-only, round18 replay tables).

Baseline (COV-GAP layer b, round18, same as PIN-1 HEAD): consumed / eligible terminal endpoints.
For each strict M5 pin (unique logical pin, shared-terminal gate passed), the terminal endpoints on the same
wire whose identity equals one of the pin's terminal identities are the endpoints a new pair would consume.
A terminal counts only when it is eligible and not yet consumed. Distinct terminal ports are counted once.
Usage: python -X utf8 05_coverage.py
"""
import pickle, re, collections, json
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_m5_work")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
FAM = D["family"]
rows = pickle.load(open(WORK / "m5_pins.pkl", "rb"))
TERMINAL = ("端子", "装置端子")


def key_id(s):
    return re.sub(r"[\s\-_~]", "", str(s or "")).upper()


cov = {}
for c in T["coverage"]:
    cov[(c["pid"], c["port_id"])] = c
base_consumed = sum(1 for c in T["coverage"] if c["consumed"] and c["eligible"])
base_eligible = sum(1 for c in T["coverage"] if c["eligible"])
print("baseline consumed / eligible", base_consumed, base_eligible, round(base_consumed / base_eligible, 4))

term_by_wire = collections.defaultdict(list)  # (pid, fid, wire) -> terminal ports
for p in T["ports"]:
    if p["category"] not in TERMINAL or not p.get("endpoint_identity"):
        continue
    for c in p.get("wire_contacts") or []:
        term_by_wire[(p["pid"], p["file_id"], c.get("wire_handle"))].append(p)

gain_ids = collections.defaultdict(set)  # bucket -> set of (pid, port_id)
fam_gain = collections.Counter()
self_skip = collections.Counter()
for r in rows:
    if r.get("pred_strict") is None:
        continue
    bucket = r["cls"]
    Tset = set(r["T"])
    # F1 self-connection (superworks_extractor._self_connection_reason): a pin whose identity
    # label+number equals one of its own terminal identities would be rejected as a self-connection.
    if key_id(r["label"] + str(r["pred_strict"])) in {key_id(t) for t in Tset}:
        self_skip[bucket] += 1
        continue
    wires = [w for w in str(r["wire"]).split(",") if w]
    for w in wires:
        for p in term_by_wire.get((r["pid"], r["fid"], w), []):
            if key_id(p["endpoint_identity"]) not in Tset:
                continue
            c = cov.get((r["pid"], p["record_id"]))
            if c is None or not c["eligible"] or c["consumed"]:
                continue
            key = (r["pid"], p["record_id"])
            if key not in gain_ids[bucket]:
                gain_ids[bucket].add(key)
                fam_gain[FAM.get(r["pid"], "?") + "|" + bucket] += 1

allg = set()
for b, s in gain_ids.items():
    allg |= s
print("self-connection skipped", dict(self_skip))
print("gain per bucket", {b: len(s) for b, s in gain_ids.items()})
print("gain distinct total", len(allg))
new_consumed = base_consumed + len(allg)
print("strict coverage before", round(base_consumed / base_eligible, 4), "after", round(new_consumed / base_eligible, 4),
      "delta pp", round((new_consumed - base_consumed) / base_eligible * 100, 2))
print("by family|bucket", dict(fam_gain))
out = {"baseline_consumed": base_consumed, "eligible": base_eligible,
       "gain_by_bucket": {b: len(s) for b, s in gain_ids.items()}, "gain_total": len(allg),
       "after_rate": round(new_consumed / base_eligible, 6), "before_rate": round(base_consumed / base_eligible, 6),
       "by_family_bucket": dict(fam_gain), "self_connection_skipped": dict(self_skip)}
json.dump(out, open(WORK / "coverage_whatif.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
