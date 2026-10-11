"""GAP2-PAIR gain and risk summary of the offline simulation (read-only).

All joins are project-qualified: a port_id repeats across projects (the same frozen DXF), so (project, port_id) is the key.
- gain: new method-S links on device terminals that are eligible and not yet consumed (uncovered.parquet from build_table);
- risk: new links on ports that already have a non-discard pair (consumed) or a continuity link;
- guard: a link is kept only when its internal element carries no endpoint identity (an element with an identity
  already takes part in a pair on that wire, which would be a conflict).
Writes sim_gain.json next to the simulation outputs.
Usage: python g2p_gain.py <sim_dir> <uncovered.parquet> <rounddir>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


def proj_of(path: Path) -> str:
    return path.parent.parent.parent.name


def main(sim_dir: Path, uncovered_path: Path, round_dir: Path):
    links = pd.read_parquet(sim_dir / "sim_links.parquet")
    unc = pd.read_parquet(uncovered_path)
    unc_key = set(zip(unc["project"], unc["port_id"]))
    unc_sig = dict(zip(zip(unc["project"], unc["port_id"]), unc["signature"]))
    consumed, continuity, ident = set(), set(), {}
    eligible_n = covered_n = 0
    for f in sorted(round_dir.glob("p*/*/findings/sw_port_coverage.parquet")):
        p = proj_of(f)
        cov = pd.read_parquet(f)
        eligible_n += int(cov["eligible"].astype(bool).sum())
        covered_n += int((cov["eligible"].astype(bool) & cov["consumed_with_internal"].astype(bool)).sum())
        for pid in cov.loc[cov["consumed"].astype(bool), "port_id"]:
            consumed.add((p, pid))
        for pid in cov.loc[cov["consumed_with_continuity"].astype(bool) & ~cov["consumed"].astype(bool), "port_id"]:
            continuity.add((p, pid))
    for f in sorted(round_dir.glob("p*/*/findings/sw_ports.parquet")):
        d = pd.read_parquet(f, columns=["record_id", "endpoint_identity"])
        p = proj_of(f)
        for rid, val in zip(d["record_id"], d["endpoint_identity"]):
            ident[(p, rid)] = val if isinstance(val, str) else ""

    keys = list(zip(links["project"], links["port_id"]))
    in_unc = pd.Series([k in unc_key for k in keys], index=links.index)
    pair_cons = pd.Series([k in consumed for k in keys], index=links.index)
    cont_cons = pd.Series([k in continuity for k in keys], index=links.index)
    elem_key = list(zip(links["project"], links["element_port_id"].fillna("")))
    guard_ok = pd.Series([ident.get(k, "") == "" for k in elem_key], index=links.index)

    out = {"new_links_no_guard": int(len(links)),
           "on_uncovered_eligible": int(in_unc.sum()),
           "on_pair_consumed": int(pair_cons.sum()),
           "on_continuity_consumed_only": int((cont_cons & ~pair_cons).sum()),
           "uncovered_by_signature": [[k, int(v)] for k, v in Counter(
               unc_sig[k] for k, m in zip(keys, in_unc) if m).most_common()],
           "element_source": [[k, int(v)] for k, v in Counter(links["source"].fillna("?")).most_common()],
           "ports_with_multiple_new_links": int((links.groupby(["project", "port_id"]).size() > 1).sum())}
    out["guard"] = {
        "blocked_total": int((~guard_ok).sum()),
        "blocked_on_pair_consumed": int((~guard_ok & pair_cons).sum()),
        "kept_total": int(guard_ok.sum()),
        "gain_on_uncovered_after_guard": int((guard_ok & in_unc).sum()),
        "kept_on_pair_consumed": int((guard_ok & pair_cons).sum()),
        "kept_on_continuity_consumed": int((guard_ok & cont_cons & ~pair_cons).sum()),
    }
    g = out["guard"]["gain_on_uncovered_after_guard"]
    out["coverage_total_baseline"] = {"covered": covered_n, "eligible": eligible_n}
    out["coverage_total_after_S"] = {"covered": covered_n + g, "eligible": eligible_n,
                                     "pct_before": round(covered_n / eligible_n * 100, 2),
                                     "pct_after": round((covered_n + g) / eligible_n * 100, 2),
                                     "gain_pp": round(g / eligible_n * 100, 2)}
    (sim_dir / "sim_gain.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
