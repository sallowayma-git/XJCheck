"""PIN-M5 step 7: assemble details.json from the work outputs (read-only).

Inputs : .tmp/pin_m5_work/{all18.pkl, m5_pins.pkl, diag_nomatch.json, consistency.json, coverage_whatif.json,
         handle_scan/summary.json (optional), spec.json}
Output : .planning/superworks-adapter/loop/PIN-M5/details.json
"""
import json, pickle, re, collections
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_m5_work")
OUT = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/PIN-M5/details.json")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
FAM = D["family"]
rows = pickle.load(open(WORK / "m5_pins.pkl", "rb"))
cons = json.load(open(WORK / "consistency.json", encoding="utf-8"))
cov = json.load(open(WORK / "coverage_whatif.json", encoding="utf-8"))
diag = json.load(open(WORK / "diag_nomatch.json", encoding="utf-8"))
spec = json.load(open(WORK / "spec.json", encoding="utf-8"))


def key_id(s):
    return re.sub(r"[\s\-_~]", "", str(s or "")).upper()


def generic(L):
    return bool(re.fullmatch(r"[0-9]*-?[0-9]*[NnPpCc]", L or ""))


out = {"scope": "PIN-M5: schematic pin identity / connection via layout PCL (round18, read-only)"}

# 1. population and handle link
out["handle_link"] = {
    "scan": "tools/01_handle_scan.py (Pass A: 1005 XDATA/XRECORD refs in 1745 DXF; Pass B: cross-file resolution)",
    "refs_1005_total": 2075930,
    "dangling_in_own_file": 0,
    "note": "All 1005 handle references resolve inside their own drawing. Schematic symbol (LD_SYMB2_LABEL) and layout part "
            "(LDPARTLAYT_PARTLABEL_HANDLE) use file-local label handles; no cross-drawing handle link exists between a "
            "schematic symbol and a 元件接线图/背板 part. PCL 线号 cross-page references are text (未定义H:P_页) and reach "
            "terminal INSERTs of other pages (装置端子 14900+1605, 端子 7936+2010 far ends; no 内部元件 far end).",
}
fars = collections.Counter()
for r in T["routes"]:
    if r["source_kind"] != "PCL":
        continue
    for e in r["ends"]:
        if e.get("role") == "FAR":
            fars[e.get("category") or ""] += 1
out["pcl_far_categories"] = dict(fars)

# 2. populations
pop = collections.Counter(r["cls"] for r in rows)
out["populations"] = dict(pop)
out["ps_status"] = dict(collections.Counter(r["status"] for r in rows if r["cls"] == "PS"))
out["tx_status"] = dict(collections.Counter(r["status"] for r in rows if r["cls"] == "TX"))
out["ti_status"] = dict(collections.Counter(r["status"] for r in rows if r["cls"] == "TI"))

# 3. truth check B (TX Pop-X, TI coils/connectors)
def tr(cls, field):
    sub = [r for r in rows if r["cls"] == cls and r.get(field) is not None]
    ag = sum(1 for r in sub if r["agree_strict" if field == "pred_strict" else "agree"])
    return len(sub), ag
out["holdout_B"] = {}
for cls in ("TX", "TI"):
    n_u, a_u = (sum(1 for r in rows if r["cls"] == cls and r["pred"] is not None),
                sum(1 for r in rows if r["cls"] == cls and r["agree"]))
    n_s, a_s = (sum(1 for r in rows if r["cls"] == cls and r["pred_strict"] is not None),
                sum(1 for r in rows if r["cls"] == cls and r["agree_strict"]))
    by_src = collections.Counter((r["match_src"], bool(r["agree_strict"])) for r in rows if r["cls"] == cls and r["pred_strict"] is not None)
    out["holdout_B"][cls] = {"unique_predictions": n_u, "unique_agree": a_u,
                             "strict_predictions": n_s, "strict_agree": a_s,
                             "strict_by_source": {f"{k[0]}|{k[1]}": v for k, v in by_src.items()}}
out["holdout_B"]["TX_unique_before_gate"] = {"n": out["holdout_B"]["TX"]["unique_predictions"],
                                             "agree": out["holdout_B"]["TX"]["unique_agree"]}

# 4. Pop-S buckets
ps = [r for r in rows if r["cls"] == "PS"]
ps_strict = [r for r in ps if r["pred_strict"] is not None]
self_id = [r for r in ps_strict if key_id(r["label"] + str(r["pred_strict"])) in {key_id(t) for t in r["T"]}]
out["popS"] = {
    "total": len(ps),
    "by_category_status": {f"{k[0]}|{k[1]}": v for k, v in collections.Counter((r["status_src"], r["status"]) for r in ps).items()},
    "strict_unique": len(ps_strict),
    "strict_self_identity": len(self_id),
    "strict_admissible_nonself": len(ps_strict) - len(self_id),
    "strict_pred_equals_terminal_suffix": sum(1 for r in ps_strict if any(t.endswith(str(r["pred_strict"])) for t in r["T"])),
    "strict_generic_label": sum(1 for r in ps_strict if generic(r["label"])),
}
blk = collections.defaultdict(collections.Counter)
for r in ps:
    b = r.get("block") or "?"
    blk[b]["n"] += 1
    if r["pred_strict"] is not None:
        blk[b]["strict"] += 1
        if key_id(r["label"] + str(r["pred_strict"])) in {key_id(t) for t in r["T"]}:
            blk[b]["self"] += 1
    if r["status"] == "no_terminal":
        blk[b]["no_terminal"] += 1
    if r["status"] == "no_label":
        blk[b]["no_label"] += 1
out["popS_by_block"] = {k: dict(v) for k, v in sorted(blk.items(), key=lambda x: -x[1]["n"])[:20]}
out["popS_by_category_strict"] = dict(collections.Counter(r["status_src"] for r in ps_strict))

# 5. consistency
out["consistency"] = cons

# 6. no-match diagnosis
out["nomatch_diagnosis"] = diag["counts"]

# 7. coverage what-if
out["coverage"] = cov

# 8. visual judgements (from the 30 renders, judged in this session; see README 5)
out["visual"] = {
    "n": 30,
    "TX_n": 8, "PS_n": 22,
    "incorrect": 0,
    "both_checks_visible_correct": 8,
    "identity_visible_correct": 14,
    "consistent_not_fully_visible": 22,
    "note": "identity check = layout display number / truth agrees or wire number beside the pin agrees; "
            "connection check = terminal or far text visible on the same window and agreeing",
    "samples": [{"name": s["name"], "cls": s["cls"], "label": s["label"], "pred": s["pred"], "truth": s.get("truth"),
                 "T": s["T"], "match_src": s["match_src"], "block": s.get("block")} for s in spec],
}
out["visual"]["judgements"] = {
    "TX01": ["identity correct (layout display 4 = truth 4)", "connection plausible (terminal off-window)"],
    "TX02": ["correct", "correct (layout far text 1n1218 = T)"],
    "TX03": ["correct", "correct (far text UD8 = T)"],
    "TX04": ["correct", "correct (far text 1KD8 = T)"],
    "TX05": ["correct", "correct (far text 3-4Q1D5 = T 34Q1D5)"],
    "TX06": ["correct", "correct (far text ZD4 = T)"],
    "TX07": ["correct", "correct (far text ZD3 = T)"],
    "TX08": ["correct", "correct (far text JD6 = T)"],
    "PS01": ["correct (display 22 = column 2 + row 22 convention)", "correct (terminal 3-21n222 visible)"],
    "PS06": ["correct (display 14, pin 314)", "plausible"],
    "PS09": ["correct (display 11, pin 411)", "plausible"],
    "PS15": ["correct (display 21, pin 421)", "plausible (off-window)"],
    "PS18": ["correct (display 20, pin 720)", "plausible (off-window)"],
    "PS19": ["correct (display 5, pin 1X5)", "plausible (off-window)"],
    "others": "PS02-05, PS07-08, PS10-14, PS16-17, PS20-22: wire number beside pin = pin number, terminal or far text on the other page; not fully visible",
}

# 9. admission-level summary
out["admission_recommendation"] = {
    "TX_strict_gate": "unique logical pin AND schematic terminal not shared by several pins of the same label",
    "PS": "do not admit as identity or pair: pin identity label+number equals its terminal identity in 7282/7322 cases "
          "(F1 self-connection), and the logical number equals the terminal number in 7318/7322 cases",
}

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("saved", OUT, "keys", list(out.keys()))
