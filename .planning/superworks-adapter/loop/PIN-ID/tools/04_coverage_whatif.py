"""PIN-ID step 4: strict-coverage what-if for admitting candidate pin identities (read-only).

Strict口径 (same as COV-GAP layer b / strict_coverage.py): eligible = terminal (端子/装置端子) port with wire
contact and resolved label; consumed = a non-discard production pair naming the port with equal value.
The what-if counts eligible, currently unconsumed terminal ports whose wire partner is a Pop-X pin that a
given admission rule would identify. This is an upper bound: it assumes the admitted candidate forms an
ordinary pair with the terminal (the same assumption as LOGGEN-2 section 5).

Usage: python 04_coverage_whatif.py <all.pkl> <pop_x.pkl> <pop_s.pkl> <out_json>
"""
import collections
import json
import pickle
import sys

TERM = {"端子", "装置端子"}


def main(all_pkl, popx_pkl, pops_pkl, out_json):
    D = pickle.load(open(all_pkl, "rb"))
    T, FAM = D["tables"], D["family"]
    pop_x = pickle.load(open(popx_pkl, "rb"))
    pop_s = pickle.load(open(pops_pkl, "rb"))

    cov = {c["port_id"]: c for c in T["coverage"]}
    elig = [c for c in T["coverage"] if c["category"] in TERM and c["eligible"]]
    base_cons = sum(1 for c in elig if c["consumed"])
    base = {"eligible": len(elig), "consumed": base_cons, "ratio": round(base_cons / len(elig), 6)}
    per_family = collections.defaultdict(lambda: [0, 0])
    for c in elig:
        f = FAM.get(c["pid"])
        per_family[f][0] += 1
        per_family[f][1] += int(bool(c["consumed"]))

    # duplicate identities that have distinct terminal partners (from population builder)
    dup_partners = collections.defaultdict(set)
    dup_locs = collections.defaultdict(set)
    for x in pop_x:
        if x["k_rec"]:
            k = (x["pid"], x["k_rec"].casefold())
            dup_locs[k].add((x["file"], x["insert"], x["pin"]))
            if x["term_partner"]:
                dup_partners[k].add(x["other_identity"])

    def rule_ports(predicate):
        """Terminal port ids (eligible) that a rule would identify through their Pop-X wire partner."""
        out = set()
        for x in pop_x:
            if not (x["term_partner"] and x["other_port_ids"]):
                continue
            if not predicate(x):
                continue
            for pid_ in x["other_port_ids"]:
                out.add(pid_)
        return out

    def dup_ok(x):
        k = (x["pid"], x["k_rec"].casefold())
        return len(dup_partners[k]) <= 1

    rules = {
        "R1_slot_agree_rec_unique_row_not_disagree": lambda x: x["k_agree"] and dup_ok(x) and x["row_check"] != "disagree_same_device_other_pin"
                                                               and x["row_check"] != "disagree_device_absent",
        "R2_slot_agree_only": lambda x: x["k_agree"],
        "R3_rec_only_slot_missing": lambda x: (not x["slot_exists"]) and bool(x["k_rec"]),
        "R4_rec_only_including_row_disagree": lambda x: bool(x["k_rec"]),
    }
    res = {"baseline": base, "per_family_baseline": {k: {"eligible": v[0], "consumed": v[1]} for k, v in per_family.items()},
           "rules": {}}
    for name, pred in rules.items():
        ids = rule_ports(pred)
        target = [pid_ for pid_ in ids if pid_ in cov and cov[pid_]["eligible"] and not cov[pid_]["consumed"]]
        already = [pid_ for pid_ in ids if pid_ in cov and cov[pid_]["eligible"] and cov[pid_]["consumed"]]
        fam = collections.Counter(FAM.get(cov[p]["pid"]) for p in target)
        res["rules"][name] = {
            "candidate_terminal_ports": len(ids),
            "eligible_unconsumed_gain": len(target),
            "eligible_already_consumed": len(already),
            "upper_strict_ratio": round((base_cons + len(target)) / len(elig), 6),
            "gain_pp": round(100 * len(target) / len(elig), 3),
            "gain_by_family": dict(fam),
        }
    # Pop-S: identities that the wire-linked row check would give (unique row candidates only)
    s_ports = set()
    for x in pop_s:
        if x["partner_identity"] and len(x["row_candidates"]) == 1:
            pass
    res["pop_s_row_unique_candidates"] = sum(1 for x in pop_s if len(x["row_candidates"]) == 1)
    res["pop_s_k_num_gain_if_admitted"] = "not admitted: K_num is not a drawn name (see README)"

    # new-issue estimate: accepted candidates on terminals already consumed by a non-discard pair
    cons_conflict = 0
    for name in ("R1_slot_agree_rec_unique_row_not_disagree",):
        ids = rule_ports(rules[name])
        cons_conflict = sum(1 for pid_ in ids if pid_ in cov and cov[pid_]["eligible"] and cov[pid_]["consumed"])
    res["r1_terminals_already_consumed_would_get_second_pair"] = cons_conflict
    res["dup_identities_with_distinct_partners_popx"] = sum(1 for k, v in dup_partners.items() if len(v) > 1)
    json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
