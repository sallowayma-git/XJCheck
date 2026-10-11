"""PIN-ID step 5: assemble details.json from the population, consistency, what-if and visual-judgement outputs.

Usage: python 08_final_summary.py <all.pkl> <out_dir_pin_id> <scratch_pop_dir> <scratch_cons_dir>
Reads : scratch population (pop_s.pkl, pop_x.pkl, summary.json, whatif.json), consistency.json,
        samples.json and judgements.json (PIN-ID root), conflict_renders.json.
Writes: details.json (PIN-ID root).
"""
import collections
import json
import math
import pickle
import sys
from pathlib import Path


def missing(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or v == ""


def pct(a, b):
    return round(100.0 * a / b, 2) if b else None


def clopper_lower(k, n, alpha=0.05):
    """One-sided lower bound of a binomial proportion (exact, by bisection on the binomial CDF)."""
    if n == 0:
        return None
    if k == 0:
        return 0.0

    def cdf(p):
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k))

    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        # upper tail P(X >= k | p) = 1 - cdf(p); lower bound is the p where that tail equals alpha
        if 1 - cdf(mid) < alpha:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


def main(all_pkl, out_dir, pop_dir, cons_dir):
    out_dir, pop_dir, cons_dir = Path(out_dir), Path(pop_dir), Path(cons_dir)
    D = pickle.load(open(all_pkl, "rb"))
    T, FAM = D["tables"], D["family"]
    px = pickle.load(open(pop_dir / "pop_x.pkl", "rb"))
    ps = pickle.load(open(pop_dir / "pop_s.pkl", "rb"))
    pop_summary = json.loads((pop_dir / "summary.json").read_text(encoding="utf-8"))
    whatif = json.loads((pop_dir / "whatif.json").read_text(encoding="utf-8"))
    cons = json.loads((cons_dir / "consistency.json").read_text(encoding="utf-8"))
    samples = json.loads((out_dir / "samples.json").read_text(encoding="utf-8"))
    judg = json.loads((out_dir / "judgements.json").read_text(encoding="utf-8"))
    conflicts = json.loads((cons_dir / "conflict_renders.json").read_text(encoding="utf-8")) if (cons_dir / "conflict_renders.json").exists() else []
    conflict_judg = {
        "bridge_mapping": ("plausible_candidate", "candidate matches the drawn wire end (pin 13 of 1FA); the existing bridge pair 1QD4-1QD7 looks spurious"),
        "wire_component_mapping": ("candidate_corrects_legacy", "drawn 12 matches the candidate FZJ1-12; the existing pass pair holds a bare legacy number 12"),
        "semantic_mapping": ("plausible_candidate", "drawn 1 matches candidate 1-21ZK-1; existing review pair holds a bare legacy number 13"),
        "ordinary_pair": ("candidate_consistent_with_geometry", "the drawn wire runs from the terminal to pin 13 of 3-4FA2; the existing ordinary pair to terminal 3-4Q2D17 looks wrong"),
    }

    # ---- availability (Pop-S = SW internal ports without identity; Pop-X = insert_not_sw LOGGEN ends)
    ps_reason = collections.Counter()
    for x in ps:
        if not x["label_ok"]:
            ps_reason["label_reference_missing"] += 1
        elif x["scan_term_texts"]:
            ps_reason["label_ok_term_text_link_present_but_not_used"] += 1
        else:
            ps_reason["label_ok_no_pin_text_link"] += 1
    ps_by_family = collections.Counter(x["family"] for x in ps)
    ps_wire = sum(1 for x in ps if x["has_wire"])
    ps_term = sum(1 for x in ps if x["partner_identity"])
    ps_term_by_family = collections.Counter(x["family"] for x in ps if x["partner_identity"])
    ps_terminal_lab = sum(1 for x in ps if x["partner_identity"] and x["label_ok"])

    px_fields = collections.Counter()
    for x in px:
        px_fields["symbol_dropped_no_LD_SYMB2_SPECIAL"] += 1
        if not x["scan_has_label"]:
            px_fields["label_missing"] += 1
        if not x["slot_exists"]:
            px_fields["slot_text_missing"] += 1
        if not x["term_partner"]:
            px_fields["other_end_not_resolved_terminal"] += 1
        if missing(x["wire"]):
            px_fields["wire_handle_missing_in_record"] += 1
    px_family = collections.Counter(x["family"] for x in px)

    # ---- candidate availability per source (Pop-X)
    n_x = len(px)
    avail = dict(
        K_rec=sum(1 for x in px if x["k_rec"]),
        K_slot=sum(1 for x in px if x["k_slot"]),
        K_rec_and_K_slot_equal=sum(1 for x in px if x["k_agree"]),
        K_rec_only_slot_missing=sum(1 for x in px if x["k_rec"] and not x["slot_exists"]),
    )

    # ---- R1 gain split by wire-handle presence (for the admission design)
    dup_partner = collections.defaultdict(set)
    for x in px:
        if x["k_rec"] and x["term_partner"]:
            dup_partner[(x["pid"], x["k_rec"].casefold())].add(x["other_identity"])
    r1 = [x for x in px if x["k_agree"] and x["term_partner"] and len(dup_partner[(x["pid"], x["k_rec"].casefold())]) <= 1
          and x["row_check"] not in ("disagree_same_device_other_pin", "disagree_device_absent")]
    cov = {c["port_id"]: c for c in T["coverage"]}
    gain_ports = {}
    for x in r1:
        for pid_ in x["other_port_ids"]:
            c = cov.get(pid_)
            if c and c["eligible"] and not c["consumed"]:
                gain_ports.setdefault(pid_, x)
    with_wire = sum(1 for x in gain_ports.values() if not missing(x["wire"]))
    without_wire = len(gain_ports) - with_wire
    elig_total = sum(1 for c in T["coverage"] if c["category"] in ("端子", "装置端子") and c["eligible"])
    cons_total = sum(1 for c in T["coverage"] if c["category"] in ("端子", "装置端子") and c["eligible"] and c["consumed"])
    gain_pass_wire = with_wire

    # ---- visual results per stratum and family
    by = collections.defaultdict(list)
    for s in samples:
        key = s["stratum"]
        v = judg.get(s["png"].split("/")[-1].split("_")[0])
        verdict = (v or {}).get("verdict", "not_judged")
        by[key].append(dict(png=s["png"], pid=s["pid"], family=s.get("family"), file=s["file"], verdict=verdict,
                            note=(v or {}).get("note", "")))
    stratum_table = {}
    for key, rows in by.items():
        c = collections.Counter(r["verdict"] for r in rows)
        n = len(rows)
        stratum_table[key] = dict(
            n=n, correct=c.get("correct", 0), plausible=c.get("plausible", 0),
            unverifiable=c.get("unverifiable", 0), incorrect=c.get("incorrect", 0),
            by_family=dict(collections.Counter(r["family"] for r in rows)))
    a_rows = by.get("A", []) + by.get("A2", [])
    a_correct = sum(1 for r in a_rows if r["verdict"] == "correct")
    a_lower95 = clopper_lower(a_correct, len(a_rows))

    conflict_table = [dict(kind=k, verdict=v[0], note=v[1]) for k, v in conflict_judg.items()]

    details = dict(
        project="PIN-ID", scope="read-only; replay .tmp/superworks_round16_full (77 projects, 1745 pages); DXF from corpus_manifest.json",
        population=dict(
            pop_s=dict(total=pop_summary["pop_s_total"], with_wire=ps_wire, with_terminal_partner=ps_term,
                       terminal_partner_by_family=dict(ps_term_by_family), label_ok=pop_summary["pop_s_label_ok"],
                       reasons=dict(ps_reason), by_family=dict(ps_by_family),
                       pin_level_link_resolved=pop_summary["pop_s_pin_resolved"],
                       scan_term_text_links=pop_summary["pop_s_scan_term_text_links"],
                       terminal_partner_and_label=ps_terminal_lab),
            pop_x=dict(total_ends=n_x, symbols=pop_summary["pop_x_symbols"], reasons=dict(px_fields),
                       by_family=dict(px_family), term_partner=pop_summary["pop_x_term_partner"],
                       candidate_availability=avail),
        ),
        consistency=cons,
        duplicates=dict(pop_s=pop_summary["pop_s_dup_k_num"], pop_x=pop_summary["pop_x_dup_k_rec"]),
        visual=dict(
            strata=stratum_table,
            A_all=dict(n=len(a_rows), correct=a_correct, point_precision_pct=pct(a_correct, len(a_rows)),
                       exact_95_lower_bound=a_lower95,
                       note="draws A (seed 20261011) and A2 (seed 20261012) of the same accepted-source pool; A215 and A217 are copies of one drawing"),
            conflict_examples=conflict_table,
            samples=by,
        ),
        coverage=dict(
            baseline=whatif["baseline"], per_family_baseline=whatif["per_family_baseline"],
            rules=whatif["rules"],
            R1_unconsumed_gain_split=dict(total_ports=len(gain_ports), wire_handle_present=with_wire, wire_handle_missing=without_wire),
            R1_upper_strict_ratio_wire_present_only=round((cons_total + gain_pass_wire) / elig_total, 6),
            pop_s_naive_k_num_reachable_unconsumed_terminals=10859,
        ),
        conflicts=dict(
            r1_terminal_ports_already_consumed=cons["K5_conflicts_with_existing_pass_pairs"]["unique_terminal_ports"],
            detail=cons["K5_conflicts_with_existing_pass_pairs"],
        ),
    )
    (out_dir / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: details[k] for k in ("visual", "coverage")}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main(*sys.argv[1:5])
