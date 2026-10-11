"""PIN-S step 11: M4 cross-check. The terminal-strip text "端子排内接元件" of a terminal names the device pin it is
wired to (e.g. "1YJJ1-1"). Two uses:
  (V) validation on Pop-X: LOGGEN routes give an independent identity (label-slot) for the non-SW end; compare it
      with the strip destination text of the terminal at the other end of the same route.
  (P) Pop-S candidates: for each Pop-S pin wired to an identified terminal, take the strip destination of that
      terminal whose device part equals the pin's label; report counts, uniqueness and agreement.
Usage: python -X utf8 11_strip_m4.py
"""
import collections, json, pickle, re
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
OUTD = WORK / "classify"
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
TERM = ("端子", "装置端子")
INTERNAL = ("内部元件", "线圈", "接插件", "接地")


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper().strip("&")


# strip destinations by (pid, file, terminal identity)
dest = collections.defaultdict(list)
for s in T["strips"]:
    ident = s.get("endpoint_identity")
    if not ident:
        continue
    for c in s.get("connections") or []:
        if c.get("style") != "端子排内接元件" or not c.get("resolved"):
            continue
        for v in str(c.get("value", "")).replace("，", ",").split(","):
            v = norm(v)
            if v:
                dest[(s["pid"], norm(ident))].append(v)

# (V) validation on LOGGEN routes with a terminal end and a Pop-X end that has a symb2 identity
pairs = collections.Counter()
examples = []
for rt in T["routes"]:
    if rt.get("source_kind") != "LOGGEN":
        continue
    ends = rt.get("ends") or []
    if len(ends) != 2:
        continue
    term = [e for e in ends if e.get("category") in TERM and e.get("identity")]
    other = [e for e in ends if e.get("category") not in TERM and (e.get("symb2") or {}).get("identity")]
    if len(term) != 1 or len(other) != 1:
        continue
    t, o = term[0], other[0]
    ident_t = norm(t["identity"]); ident_o = norm(o["symb2"]["identity"])
    cands = dest.get((rt["pid"], ident_t), [])
    label_o = norm(o.get("device"))
    # device terminals write "label+pin" (1n705); other parts "label-pin" (1YJJ1-1): compare without the dash
    matching = [v for v in cands if v.replace("-", "").startswith(label_o)]
    pairs["routes_with_term_and_popX_identity"] += 1
    if not cands:
        pairs["terminal_has_no_strip_destination"] += 1
        continue
    pairs["terminal_has_strip_destination"] += 1
    if not matching:
        pairs["no_destination_with_same_device"] += 1
        continue
    pairs["destination_with_same_device"] += 1
    if ident_o.replace("-", "") in [v.replace("-", "") for v in matching]:
        pairs["AGREE_identity_in_destinations"] += 1
    else:
        pairs["DISAGREE"] += 1
        if len(examples) < 12:
            examples.append({"pid": rt["pid"], "file": rt["file_id"], "term": ident_t, "popX": ident_o, "dest": matching[:4],
                             "wire": rt.get("wire_handle"), "linestyle": rt.get("linestyle")})
    if rt.get("wire_handle"):
        pairs["with_wire_handle"] += 1

# (P) Pop-S candidates from the replay: Pop-S ports (no identity) whose wire other end is an identified terminal port
wire_index = collections.defaultdict(list)
for p in T["ports"]:
    for c in p.get("wire_contacts") or []:
        wire_index[(p["pid"], p["file_id"], c.get("wire_handle"))].append(p)
pops = [p for p in T["ports"] if p["category"] in INTERNAL and not p["endpoint_identity"]]
pstat = collections.Counter()
cand_out = []
for p in pops:
    label = norm((p.get("label") or {}).get("normalized") or "").replace("-", "")
    if not label:
        pstat["no_label"] += 1
        continue
    got = set()
    term_seen = 0
    for c in p.get("wire_contacts") or []:
        for q in wire_index.get((p["pid"], p["file_id"], c.get("wire_handle")), []):
            if q is p or (q["instance_path"] == p["instance_path"] and q["marker_handle"] == p["marker_handle"]):
                continue
            if q["category"] in TERM and q.get("endpoint_identity"):
                term_seen += 1
                for v in dest.get((q["pid"], norm(q["endpoint_identity"])), []):
                    vv = v.replace("-", "")
                    if vv.startswith(label) and re.fullmatch(r"[A-Z0-9+~]+", vv[len(label):] or "x"):
                        got.add(v)
    if term_seen == 0:
        pstat["no_identified_terminal_neighbour"] += 1
    elif not got:
        pstat["terminal_neighbour_but_no_destination_match"] += 1
    elif len(got) == 1:
        pstat["unique_destination_candidate"] += 1
    else:
        pstat["multiple_destination_candidates"] += 1
    if got and len(cand_out) < 4000:
        cand_out.append({"pid": p["pid"], "rid": p["record_id"], "label": label, "cands": sorted(got)})

res = {"validation_LOGGEN": dict(pairs), "examples_disagree": examples, "popS_candidates": dict(pstat),
       "n_popS": len(pops)}
json.dump(res, open(OUTD / "m4_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(cand_out, open(OUTD / "m4_popS_candidates_sample.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])
