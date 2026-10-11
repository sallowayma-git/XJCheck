"""PIN-S step 9: final Pop-S classes, class precision on metadata truth, wire-label test, coverage upper bound.

Pin-like (strict) text: digits 1-3, or 1-2 letters + digits 1-3, or digits + 1-2 letters.
Classes (first match wins):
  A_anchor_ok      TERMTEXTPOINT anchor linked to the marker; unique strict pin-like text within 4 of the anchor
  B_pin_le3        unique nearest strict pin-like text within 3 of the marker, owned by this marker
  C_pin_contested  strict pin-like text within 3, but tied with another text or nearer to another marker
  D_pin_3to9       no strict pin-like text within 3; nearest strict pin-like text within 9 (unique)
  E_text_le3_nonpin no strict pin-like text within 3; some other text (signal / function / name) within 3
  F_none_le9       nothing within 9
Usage: python -X utf8 09_final.py
"""
import collections, json, math, pickle, re
from pathlib import Path
import numpy as np

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
OUTD = WORK / "classify"
OUTD.mkdir(parents=True, exist_ok=True)
MK = pickle.load(open(WORK / "markers.pkl", "rb"))
M, TM = MK["rows"], MK["texts_model"]
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
INTERNAL = ("内部元件", "线圈", "接插件", "接地")
STRICT = re.compile(r"[+\-]|\d{1,3}|[A-Za-z]{1,4}\d{1,3}|\d{1,2}[A-Za-z]\d{1,2}|\d{1,3}[A-Za-z]{1,2}")  # v2 token rule (see README)


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def is_pin(v):
    return bool(STRICT.fullmatch(norm(v))) and len(norm(v)) <= 6


def cls_for(r):
    cands = r["cands"]  # sorted by seg distance; tuple idx: 0 src,1 kind,2 h,3 v,4 x,5 y,6 ht,7 dist,8 u,9 w,10 rank,11 nmw,12 second
    anc = None
    for h, cx, cy in r["anchors"]:
        near = sorted(((math.hypot(c[4] - cx, c[5] - cy), c) for c in cands), key=lambda t: t[0])
        near = [t for t in near if t[0] <= 4.0 and is_pin(t[1][3])]
        if near and (len(near) == 1 or near[1][0] - near[0][0] >= 0.5):
            anc = near[0][1]
            break
    if anc is not None:
        return "A_anchor_ok", anc
    pins3 = [c for c in cands if c[7] <= 3.0 and is_pin(c[3])]
    if pins3:
        c0 = pins3[0]
        if len(pins3) > 1 and pins3[1][7] - c0[7] < max(0.25, 0.25 * (c0[6] or 0)):
            return "C_pin_contested", c0
        if c0[10] not in (0, None) or (c0[12] is not None and c0[12] - c0[7] < 0.25):
            return "C_pin_contested", c0
        return "B_pin_le3", c0
    other3 = [c for c in cands if c[7] <= 3.0]
    if other3:
        return "E_text_le3_nonpin", other3[0]
    pins9 = [c for c in cands if c[7] <= 9.0 and is_pin(c[3])]
    if pins9:
        c0 = pins9[0]
        if len(pins9) > 1 and pins9[1][7] - c0[7] < max(0.25, 0.25 * (c0[6] or 0)):
            return "F_none_le9", None
        return "D_pin_3to9", c0
    return "F_none_le9", None


def precision(rows):
    tab = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        k, c = cls_for(r)
        tab[k][0] += 1
        if c is not None and norm(c[3]) == norm(r["truth"]):
            tab[k][1] += 1
    return {k: {"n": v[0], "correct": v[1], "precision": round(v[1] / v[0], 4) if v[0] else None} for k, v in sorted(tab.items())}


if __name__ == "__main__":
    pops = [r for r in M if r["in_replay"] and r["replay_category"] in INTERNAL and not r["replay_identity"] and not r["replay_part"]]
    res = {"n_popS": len(pops)}
    # --- Pop-S classes
    cc = collections.Counter(cls_for(r)[0] for r in pops)
    res["classes"] = dict(sorted(cc.items()))
    # --- truth precision (links removed); TX = Pop-X component symbols, TI = internal metadata
    tx = [r for r in M if r["truth"] is not None and not r["in_replay"]]
    ti = [r for r in M if r["truth"] is not None and r["in_replay"] and r["replay_category"] in ("线圈", "接插件")]
    res["truth_precision_TX"] = precision(tx)
    res["truth_precision_TI"] = precision(ti)
    res["truth_precision_TX_TI"] = precision(tx + ti)
    res["n_truth_TX"] = len(tx); res["n_truth_TI"] = len(ti)
    # --- wire-number test: strict pin-like text within 9 that sits on a wire contact (surrogate: wire label)
    wc = {}
    for p in T["ports"]:
        wc[(p["pid"], p["file_id"], p["instance_path"], p["marker_handle"])] = [(c["x"], c["y"]) for c in (p.get("wire_contacts") or [])]
    wire_flag = collections.Counter()
    for r in pops:
        k, c = cls_for(r)
        if c is None or k not in ("D_pin_3to9", "B_pin_le3", "C_pin_contested"):
            continue
        pts = wc.get((r["pid"], r["fid"], r["instance"], r["marker"]), [])
        if not pts:
            wire_flag["no_contact_points"] += 1
            continue
        dmin = min(math.hypot(c[4] - x, c[5] - y) for x, y in pts)
        wire_flag["text_within_2_of_wire_contact" if dmin <= 2 else "text_not_on_wire"] += 1
    res["wire_number_test"] = dict(wire_flag)
    # --- coverage upper bound: uncovered eligible terminal ports whose wire other end is a Pop-S marker of an accepted class
    cov = {(c["pid"], c["port_id"]): c for c in T["coverage"]}
    uncovered = {k for k, c in cov.items() if c["eligible"] and not c["consumed"]}
    all_ports = {(p["pid"], p["record_id"]): p for p in T["ports"]}
    wire_index = collections.defaultdict(list)
    for p in T["ports"]:
        for c in p.get("wire_contacts") or []:
            wire_index[(p["pid"], p["file_id"], c.get("wire_handle"))].append(p)
    gain = collections.Counter(); gain_ids = collections.defaultdict(set)
    for r in pops:
        k, c = cls_for(r)
        if k not in ("A_anchor_ok", "B_pin_le3", "D_pin_3to9"):
            continue
        port = next((p for p in [] ), None)
        for w in r["replay_wire"]:
            for q in wire_index.get((r["pid"], r["fid"], w), []):
                if q["instance_path"] == r["instance"] and q["marker_handle"] == r["marker"]:
                    continue
                if q["category"] in ("端子", "装置端子") and (r["pid"], q["record_id"]) in uncovered:
                    gain[k] += 1
                    gain_ids[k].add((r["pid"], q["record_id"]))
    total_elig = sum(1 for c in cov.values() if c["eligible"])
    cons = sum(1 for c in cov.values() if c["eligible"] and c["consumed"])
    res["coverage_base"] = {"eligible": total_elig, "consumed": cons, "rate": round(cons / total_elig, 4)}
    res["coverage_gain_terminal_ports_by_class"] = {k: {"pins": gain[k], "terminal_ports": len(gain_ids[k])} for k in gain}
    union = set().union(*[gain_ids[k] for k in ("A_anchor_ok", "B_pin_le3")]) if gain_ids else set()
    res["coverage_upper_bound_A_B"] = {"terminal_ports": len(union), "rate_gain": round(len(union) / total_elig, 4),
                                       "rate_after": round((cons + len(union)) / total_elig, 4)}
    union3 = union | (gain_ids.get("D_pin_3to9") or set())
    res["coverage_upper_bound_A_B_D"] = {"terminal_ports": len(union3), "rate_gain": round(len(union3) / total_elig, 4),
                                         "rate_after": round((cons + len(union3)) / total_elig, 4)}
    json.dump(res, open(OUTD / "final_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:4000])
