"""MULTI-SEG: assemble details.json from the work tables (read-only on src; writes the loop folder only).

Inputs (.tmp/multiseg_work): cls870.json, sig870.json (ms_gapclass), sample_cases.json (ms_sample), final_summary.json
(ms_final), sim_totals_M_prod_M0_M1_M2.json (ms_sim). Output: loop/MULTI-SEG/details.json.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/multiseg_work")
OUT = Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/MULTI-SEG/details.json")


def family(sig: str) -> str:
    left, gaps, right = sig.split("|")[0], sig.split("|")[1], sig.split("|")[2]
    if "UNREG2" in gaps and "BODY" in gaps and "SWELEM" not in gaps and "DEVBODY" not in gaps and "FRAME" not in gaps:
        return "F1 端点|本体|未登记两引脚符号|端子"
    if "FRAME" in gaps:
        return "F4 框线/拐角/分支（含框线穿越）"
    if "DEVBODY" in gaps:
        return "F3 装置端子串接（多本体）"
    if "SWELEM" in gaps:
        return "F2 端子|内部元件触点|本体|端子"
    return "F5 其它"


def main():
    cls = json.loads((WORK / "cls870.json").read_text(encoding="utf-8"))
    sig = json.loads((WORK / "sig870.json").read_text(encoding="utf-8"))
    sample = json.loads((WORK / "sample_cases.json").read_text(encoding="utf-8"))
    final = json.loads((WORK / "final_summary.json").read_text(encoding="utf-8"))
    sims = json.loads((WORK / "sim_totals_M_prod_M0_M1_M2.json").read_text(encoding="utf-8"))

    sigc = Counter(s["signature"] for s in sig)
    famc = Counter(family(s["signature"]) for s in sig)
    gapc = Counter(g for s in sig for g in s["gaps"] if g != "BODY")
    leftc = Counter(s["left"] for s in sig)
    rightc = Counter(s["right"] for s in sig)
    pieces = Counter(s["n_pieces"] for s in sig)
    lines = Counter(s["n_lines"] for s in sig)
    orient = Counter(s["orientation"] for s in sig)

    cases = []
    for item in sample:
        s = sig[item["index"]]
        cases.append({"png": item["png"], "index": item["index"], "pid": s["pid"], "file_id": s["file_id"],
                      "sheet_id": s["sheet_id"], "line_group_id": s["line_group_id"], "identity": s["identity"],
                      "port_a": s["port_a"], "port_b": s["port_b"], "n_pieces": s["n_pieces"],
                      "signature": s["signature"], "family": family(s["signature"]), "gaps": s["gaps"],
                      "left": s["left"], "right": s["right"]})

    out = {
        "slice": "MULTI-SEG",
        "scope": "round21 products (77 projects, frozen corpus). Read-only: src/ and tests/ untouched; no git.",
        "population": {
            "refused_candidates": len(sig),
            "unique_line_groups": len({(s["pid"], s["line_group_id"]) for s in sig}),
            "pieces_end_point_components": dict(pieces),
            "raw_lines_per_group": dict(sorted(lines.items())),
            "orientation": dict(orient),
            "note": "'段' in the GAP2-S README means end-point components (pieces); the raw LINE count is 3 to 6.",
        },
        "classification": {
            "signature_counts": dict(sigc.most_common()),
            "family_counts": dict(famc.most_common()),
            "non_body_gap_classes": dict(gapc),
            "left_end_classes": dict(leftc),
            "right_end_classes": dict(rightc),
        },
        "visual": {
            "sample_cases": len(cases),
            "png_files": sorted({c["png"] for c in cases}) + ["MS_R01.png"],
            "cases": cases,
            "removed_check_png": "MS_R01.png (4 production candidates removed by M2, all through a 2-pin element)",
        },
        "offline_simulation": {
            "method_definitions": {
                "M_prod": "production GAP2-S terminal split (2-piece rule), guard applied",
                "M0": "no split (line groups as they are), guard applied",
                "M1": "body cut at every device-terminal body, any number of pieces",
                "M2": "M1 plus cut at every element-bracketed gap (unregistered two-pin span, SuperWORKS element or device "
                      "block bracketed by two TERMPOINTs of one insert, model line crossing the gap); label and dot gaps merged",
            },
            "totals": sims["totals"],
            "validation": {"M_prod_links": sims["totals"]["M_prod"]["links"], "expected_M_prod": 18646,
                           "M0_links": sims["totals"]["M0"]["links"], "expected_M0": 14704},
        },
        "outcome_of_870_ports_under_M2": final["ports_870"],
        "device_internal_delta_M_prod_to_M2": {"lost": final["lost"], "gained": final["gained"]},
        "external_candidate_delta_M2_vs_prod": {"only_in_M2": final["ext_only_m2"],
                                                "only_in_prod_removed": final["ext_only_prod"]},
        "unknown_topology_under_M2": {"reason_counts": final["unknown"],
                                      "examples": final["unknown_examples"]},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", OUT, len(json.dumps(out)))


if __name__ == "__main__":
    main()
