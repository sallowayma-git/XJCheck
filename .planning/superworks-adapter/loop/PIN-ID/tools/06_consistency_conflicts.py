"""PIN-ID step 2: internal-consistency checks of the candidate identities (read-only).

Checks
  K1  K_slot (label + TERM_TEXT slot text) vs K_rec (LOGGEN device + seq) on the same Pop-X pin.
  K2  K_rec vs the wire-linked terminal row (strip 端子排内接元件 text), where the row exists.
  K3  K_num (label + TERMPOINT port number) vs the identity already resolved on SuperWORKS internal ports
      (its suffix equals the number only in a small share of cases).
  K4  same candidate identity on several physical pins of one project (重号), and whether those pins have
      distinct terminal partners.
  K5  candidates on terminals that already have a non-discard pair (multi-source conflict): the existing pair's
      other-side value compared with the candidate. The list is written for the visual check (07).

Usage: python 06_consistency_conflicts.py <all.pkl> <pop_x.pkl> <pop_s.pkl> <scratch_dir>
"""
import collections
import json
import pickle
import re
import sys
from pathlib import Path

CAT_INT = {"内部元件", "线圈", "接插件", "接地"}


def main(all_pkl, popx_pkl, pops_pkl, scratch):
    D = pickle.load(open(all_pkl, "rb"))
    T, FAM = D["tables"], D["family"]
    px = pickle.load(open(popx_pkl, "rb"))
    ps = pickle.load(open(pops_pkl, "rb"))
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    cov = {c["port_id"]: c for c in T["coverage"]}
    out = {}

    # K1: slot vs record
    both = [x for x in px if x["k_rec"] and x["k_slot"]]
    out["K1_slot_vs_record"] = dict(pairs=len(both), agree=sum(1 for x in both if x["k_rec"].casefold() == x["k_slot"].casefold()))

    # K2: record vs wire-linked terminal row
    rows = collections.Counter(x["row_check"] for x in px if x["row_check"])
    checkable = rows.get("agree", 0) + rows.get("disagree_same_device_other_pin", 0) + rows.get("disagree_device_absent", 0)
    no_wire = sum(1 for x in px if x["row_check"] and (x["wire"] is None or (isinstance(x["wire"], float) and x["wire"] != x["wire"])))
    dis = [x for x in px if (x["row_check"] or "").startswith("disagree")]
    dis_nowire = sum(1 for x in dis if x["wire"] is None or (isinstance(x["wire"], float) and x["wire"] != x["wire"]))
    out["K2_record_vs_terminal_row"] = dict(
        counts=dict(rows), checkable=checkable,
        agree_rate=round(rows.get("agree", 0) / checkable, 4) if checkable else None,
        disagree_with_no_wire_handle=dis_nowire, disagree_total=len(dis),
        note="disagreements are mostly records without a wire handle (bus or polyline wires), see README")

    # K3: K_num vs resolved identities on SuperWORKS internal ports
    ident = [p for p in T["ports"] if p["category"] in CAT_INT and p["endpoint_identity"]]
    eq = 0
    for p in ident:
        lab = (p["label"] or {}).get("normalized") or ""
        ident_s = p["endpoint_identity"]
        suffix = ident_s[len(lab):].lstrip("-") if lab and ident_s.startswith(lab) else None
        if suffix is not None and suffix == p["port_number"]:
            eq += 1
    out["K3_termpoint_number_vs_identified"] = dict(identified_internal_ports=len(ident), suffix_equals_number=eq,
                                                    rate=round(eq / len(ident), 4) if ident else None)

    # K4: duplicates
    out["K4_duplicates"] = dict(popx=None, pops=None)
    dup_partner = collections.defaultdict(set)
    dup_loc = collections.defaultdict(set)
    for x in px:
        if x["k_rec"]:
            k = (x["pid"], x["k_rec"].casefold())
            dup_loc[k].add((x["file"], x["insert"], x["pin"]))
            if x["term_partner"]:
                dup_partner[k].add(x["other_identity"])
    multi = [k for k, v in dup_loc.items() if len(v) > 1]
    out["K4_duplicates"]["popx"] = dict(identities=len(dup_loc), multi_location=len(multi),
                                       multi_location_distinct_partners=sum(1 for k in multi if len(dup_partner[k]) > 1))
    dup_loc_s = collections.defaultdict(set)
    dup_partner_s = collections.defaultdict(set)
    for x in ps:
        if x["k_num"]:
            k = (x["pid"], x["k_num"].casefold())
            dup_loc_s[k].add((x["file"], x["insert"], x["port"]))
            if x["partner_identity"]:
                dup_partner_s[k].add(x["partner_identity"])
    multi_s = [k for k, v in dup_loc_s.items() if len(v) > 1]
    out["K4_duplicates"]["pops"] = dict(identities=len(dup_loc_s), multi_location=len(multi_s),
                                        multi_location_distinct_partners=sum(1 for k in multi_s if len(dup_partner_s[k]) > 1))

    # K5: candidates on terminals with an existing non-discard pair
    port_pairs = collections.defaultdict(list)
    for p in T["pairs"]:
        if p["status"] == "discard":
            continue
        sw = (p["evidence"] or {}).get("superworks") or {}
        for side in ("left", "right"):
            for pid_ in (sw.get(side) or {}).get("port_ids", []) or []:
                port_pairs[pid_].append((p, side))
    dup_partner_x = {k: v for k, v in dup_partner.items()}
    r1 = [x for x in px if x["k_agree"] and x["term_partner"] and len(dup_partner_x[(x["pid"], x["k_rec"].casefold())]) <= 1
          and x["row_check"] not in ("disagree_same_device_other_pin", "disagree_device_absent")]
    conflicts, seen = [], set()
    for x in r1:
        for pid_ in x["other_port_ids"]:
            c = cov.get(pid_)
            if not (c and c["eligible"] and c["consumed"]) or pid_ in seen:
                continue
            seen.add(pid_)
            for p, side in port_pairs.get(pid_, [])[:1]:
                other = p["right_value"] if side == "left" else p["left_value"]
                term = p["left_value"] if side == "left" else p["right_value"]
                conflicts.append(dict(pid=x["pid"], family=x["family"], file=x["file"], cand=x["k_rec"], term_port=pid_,
                                      term_identity=x["other_identity"], pair=p["pair_id"], pair_status=p["status"],
                                      pair_kind=p["pair_kind"], side=side, pair_other=str(other or ""),
                                      term_value=str(term or ""), numeric_other=bool(re.fullmatch(r"\s*\d+\s*", str(other or "")))))
    out["K5_conflicts_with_existing_pass_pairs"] = dict(
        unique_terminal_ports=len(conflicts),
        by_pair_kind=dict(collections.Counter(c["pair_kind"] for c in conflicts)),
        by_pair_status=dict(collections.Counter(c["pair_status"] for c in conflicts)),
        other_side_numeric_legacy=sum(1 for c in conflicts if c["numeric_other"]),
        by_family=dict(collections.Counter(FAM.get(c["pid"]) for c in conflicts)))
    (scratch / "r1_conflicts.json").write_text(json.dumps(conflicts, ensure_ascii=False, indent=1), encoding="utf-8")
    (scratch / "consistency.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
