"""Collects the GAP counts and the visual verdicts into details.json (read-only over the .tmp/gap_* intermediates).

Usage: python summarize.py <gap_work_dir> <out_json>
Inputs: uncovered.parquet, gap1_detail.parquet, net_gap1.parquet, gap2_inner.parquet, gap2_gapcontent.parquet,
        gap2_labels.parquet (all produced by the tools in this folder), inserts.parquet.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

VISUAL = {
    # Per-sample reading of the rendered sheets (single reviewer). Categories:
    #   rail = wire ends on a vertical terminal-strip rail; pin = wire ends on an unregistered component pin lead;
    #   free = open end in blank space or beside a spare label; joint = wire meets another line's end (corner);
    #   sw_edge = end on a registered SW symbol edge with no port there; port_coincide = end on another port's marker;
    #   frame_break_empty = 2.5 gap at a terminal-strip frame, no text, no dot; text_break = gap holds a wire label;
    #   real_node = zero gap with a connect dot; large_gap_uncertain = 10 to 18.75 gap, not decided.
    "G1T": {"n": 12, "samples": {f"G1T-{i:02d}": "rail" for i in range(1, 13)}},
    "G1P": {"n": 10, "samples": {f"G1P-{i:02d}": "pin" for i in range(1, 11)}},
    "G1F": {"n": 10, "samples": {"G1F-01": "rail", "G1F-02": "free", "G1F-03": "joint", "G1F-04": "sw_edge",
                                 "G1F-05": "port_coincide", "G1F-06": "rail", "G1F-07": "free", "G1F-08": "joint",
                                 "G1F-09": "sw_edge", "G1F-10": "port_coincide"}},
    "G2A": {"n": 10, "samples": {"G2A-01": "frame_break_empty", "G2A-02": "text_break", "G2A-03": "text_break",
                                 "G2A-04": "large_gap_uncertain", "G2A-05": "real_node", "G2A-06": "text_break",
                                 "G2A-07": "text_break", "G2A-08": "text_break", "G2A-09": "text_break",
                                 "G2A-10": "large_gap_uncertain"}},
    "G2B": {"n": 10, "samples": {"G2B-01": "text_break", "G2B-02": "text_break", "G2B-03": "text_break",
                                 "G2B-04": "large_gap_uncertain", "G2B-05": "text_break", "G2B-06": "large_gap_uncertain",
                                 "G2B-07": "large_gap_uncertain", "G2B-08": "text_break", "G2B-09": "text_break",
                                 "G2B-10": "text_break"}},
    "G2E": {"n": 9, "samples": {f"E-{i:02d}": "frame_break_empty" for i in range(1, 10)}},
}


def tk(counter):
    return {"|".join(str(x) for x in k) if isinstance(k, tuple) else str(k): int(v) for k, v in counter.items()}


def main(work: Path, out_json: Path):
    u = pd.read_parquet(work / "uncovered.parquet")
    d1 = pd.read_parquet(work / "gap1_detail.parquet")
    net = pd.read_parquet(work / "net_gap1.parquet")
    g2 = pd.read_parquet(work / "gap2_inner.parquet")
    gc = pd.read_parquet(work / "gap2_gapcontent.parquet")
    lab = pd.read_parquet(work / "gap2_labels.parquet")
    ins = pd.read_parquet(work / "inserts.parquet")

    dev = u[u.category == "装置端子"]
    buckets = Counter(zip(dev.reason, dev.signature, dev.route_note))
    g1 = d1[d1.subset == "GAP1"]
    g1s = d1[d1.subset == "GAP1sib"]
    fam = Counter(re.sub(r"\d+", "#", str(b)) for b in g1.best_block if str(b))
    pin = g1[g1["sub"] == "pin_touch"]
    tee = g1[g1.far_class == "line_tee"]
    net_g1 = net[(net.subset == "GAP1")]
    net_bins = Counter(np.clip(net_g1.n_other_ports.fillna(-1), -1, 3).astype(int).tolist())
    gap_kind = {}
    for sub in ("GAP2a", "GAP2b"):
        kinds = Counter()
        for r in gc[gc.subset == sub].to_dict("records"):
            det = json.loads(r["gap_detail"])
            k = set("dot" if g["dot"] else "text" if g["text"] else "cross" if g["cross_lines"] else "empty" for g in det)
            kinds["+".join(sorted(k)) if k else "none"] += 1
        gap_kind[sub] = dict(kinds)
    run_kind = {}
    for sub in ("GAP2a", "GAP2b"):
        x = gc[gc.subset == sub]
        empty_run = sum(1 for r in x.to_dict("records") if any(g["text"] == 0 and g["dot"] == 0 and g["cross_lines"] == 0
                                                             for g in json.loads(r["gap_detail"])))
        run_kind[sub] = {"runs": int(len(x)), "with_empty_gap": int(empty_run)}
    ports_g2 = {sub: int((g2.subset == sub).sum()) for sub in ("GAP2a", "GAP2b")}
    # the GAP-2 wires with any empty gap (strict: no text, no dot, no crossing line)
    empty_ports = {}
    for sub in ("GAP2a", "GAP2b"):
        x = gc[gc.subset == sub].merge(g2[["port_id", "project"]], on=["port_id", "project"])
        empty_ports[sub] = int(sum(1 for r in x.to_dict("records")
                                  if any(g["text"] == 0 and g["dot"] == 0 and g["cross_lines"] == 0
                                         for g in json.loads(r["gap_detail"]))))
    details = {
        "population": {
            "eligible_uncovered_total": int(len(u)),
            "device_terminal_buckets_no_matching_pair": {
                "dangling_single_route": int(((dev.signature.str.startswith("悬空")) & (dev.route_note == "单端记录(另一端未记录)") & (dev.reason == "no_matching_production_pair")).sum()),
                "dangling_no_route": int(((dev.signature.str.startswith("悬空")) & (dev.route_note == "无路由记录") & (dev.reason == "no_matching_production_pair")).sum()),
                "multi_internal_unidentified_plus_terminal_plus_device": int(((dev.signature == "内部元件(无身份) + 端子 + 装置端子") & (dev.reason == "no_matching_production_pair")).sum()),
                "multi_terminal_plus_device": int(((dev.signature == "端子 + 装置端子") & (dev.reason == "no_matching_production_pair")).sum()),
            },
        },
        "gap1": {
            "n": int(len(g1)),
            "sub_by_far_class": tk(Counter(zip(g1["sub"], g1.far_class))),
            "pin_touch": {"n": int(len(pin)), "label_equal_device": int((pin.label_text != "").sum()),
                          "label_unresolved": int((pin.label_text == "").sum()),
                          "label_mismatch": int(((pin.label_text != "") & (~pin.label_equal_device)).sum()),
                          "term_text_slot_gt0": int((pin.term_text_slots.fillna(0) > 0).sum()),
                          "block_families": dict(fam)},
            "line_tee": {"n": int(len(tee)), "net_other_ports": tk(Counter(np.clip(tee.merge(net_g1[["port_id", "project", "n_other_ports"]], on=["port_id", "project"]).n_other_ports, 0, 3).astype(int).tolist()))},
            "sibling_926": {"n": int(len(g1s)), "sub_by_far_class": tk(Counter(zip(g1s["sub"], g1s.far_class)))},
            "net_bins_all_gap1": {str(k): v for k, v in net_bins.items()},
        },
        "gap2": {
            "ports": ports_g2,
            "unique_runs": {"GAP2a": int(g2[g2.subset == "GAP2a"][["project", "file_id", "wire_key"]].drop_duplicates().shape[0]),
                            "GAP2b": int(g2[g2.subset == "GAP2b"][["project", "file_id", "wire_key"]].drop_duplicates().shape[0])},
            "axis": tk(Counter(zip(g2.subset, g2.axis))),
            "n_members": tk(Counter(zip(g2.subset, g2.n_members.clip(upper=6)))),
            "interior_ports_gt0": int((g2.interior_ports > 0).sum()) if "interior_ports" in g2 else None,
            "gap_kind_per_gap": gap_kind,
            "runs_by_gap_content": run_kind,
            "runs_with_an_empty_gap": empty_ports,
            "label_continuity": tk(Counter(zip(lab.subset, lab.shared))),
            "label_either_side_empty": tk(Counter(zip(lab.subset, lab.either_empty))),
        },
        "visual_verdicts": VISUAL,
    }
    out_json.write_text(json.dumps(details, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(details, ensure_ascii=False, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
