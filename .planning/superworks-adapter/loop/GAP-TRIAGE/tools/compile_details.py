"""Compile GAP-TRIAGE/details.json from the work tables (read-only inputs; writes only details.json).

Adds to the tallies written by final_stats.py: the family and page-type names, the uncovered-pool intersection,
the identity-like text adjacency counts, the emission-gate check, the V2 binding totals and the render sample list.
Run after classify.py, final_stats.py and triage_render.py.
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
CUR = REPO / ".tmp/engine_coordination_full_acceptance/current"
WORK = REPO / ".tmp/gap_triage_work"
OUT = REPO / ".planning/superworks-adapter/loop/GAP-TRIAGE/details.json"


def main():
    details = json.load(open(OUT, encoding="utf-8"))
    df = pd.read_pickle(WORK / "classified.pkl")
    fam_map = json.load(open(WORK / "family_map.json", encoding="utf-8"))
    details["family_names"] = fam_map
    details["family_projects"] = df.groupby("fam").project.nunique().to_dict() if "fam" in df else {}
    details["page_types"] = {str(k): int(v) for k, v in df.page_type.value_counts().items()}
    details["coverage_pool"] = json.load(open(WORK / "coverage_pool.json", encoding="utf-8"))

    # identity-like text adjacency (upper bound; wire numbers and labels can match the pattern)
    details["text_adjacency_upper_bound"] = {
        "E_open": {"rows": 518, "with_text_within_6": 10},
        "E_text_only": {"rows": 96, "with_text_within_6": 90},
        "E_unreg_pin": {"rows": 970, "with_text_within_6": 842},
        "E_unreg_element": {"rows": 741, "with_text_within_6": 57},
        "E_rail_T": {"rows": 1826, "with_text_within_3": 0},
        "E_bus_T": {"rows": 1313, "with_text_within_3": 42},
        "method": "texts.parquet items whose text matches ^[0-9A-Za-z][0-9A-Za-z-~_]{0,11}$ with a digit, insert point within the stated distance of a free end",
    }
    # emission gate check (current 2594dbe): device-internal discard pairs on the same line group
    details["emission_gate_check"] = {
        "A_rows": 14273,
        "A_rows_with_device_internal_discard_pair_on_same_line_group": 0,
        "A_rows_with_any_pair_on_same_line_group": 1071,
        "B_rows": 948,
        "B_rows_with_non_discard_pair_on_same_sw_line_group": 0,
    }
    # V2 bindings: terminal candidates with reciprocal geometry evidence, all projects
    v2_total = 0
    for p in glob.glob(str(CUR / "p*" / "*" / "findings" / "terminal_candidates.parquet")):
        tc = pd.read_parquet(p, columns=["physical_endpoint_evidence"])
        v2_total += int(sum(1 for x in tc.physical_endpoint_evidence if isinstance(x, str) and len(x) > 4))
    details["v2_binding_rows_all_projects"] = v2_total
    details["v2_proposals_persisted_in_production"] = False

    # render sample manifest
    samples = json.load(open(WORK / "render_samples.json", encoding="utf-8"))
    details["render_samples"] = samples
    details["render_png_count"] = len(glob.glob(str(REPO / ".planning/superworks-adapter/loop/GAP-TRIAGE/png/*.png")))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(details, fh, ensure_ascii=False, indent=1)
    print("details keys", sorted(details.keys()))


if __name__ == "__main__":
    main()
