"""G1P statistics (read-only): coverage views before and after, link sources, far-end decision reasons, block counts.

Usage: python g1p_stats.py <baseline_run_dir> <new_run_dir> <out_json> <project ids...>
Reads findings/superworks_summary.json, findings/sw_device_internal_links.parquet,
findings/sw_unregistered_pin_decisions.parquet and findings/sw_unregistered_symb2.parquet of each project.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

VIEWS = ("strict", "with_continuity", "with_internal", "total")


def project_dir(run: Path, pid: str) -> Path:
    return Path(json.loads((run / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"])


def main(base_run: Path, new_run: Path, out: Path, projects: list[str]) -> dict:
    per = {}
    totals = {"eligible": 0, "views": {v: {"base": 0, "new": 0} for v in VIEWS}, "links_base": 0, "links_new": 0,
              "links_lost": 0, "links_added": 0, "sources": Counter(), "reasons": Counter(),
              "stats": Counter(), "blocks": 0, "blocks_label_resolved": 0, "termpoints": 0}
    for pid in projects:
        b, n = project_dir(base_run, pid), project_dir(new_run, pid)
        sb = json.loads((b / "findings" / "superworks_summary.json").read_text(encoding="utf-8"))
        sn = json.loads((n / "findings" / "superworks_summary.json").read_text(encoding="utf-8"))
        eligible = sn["coverage_views"]["eligible"]
        views = {v: {"base": sb["coverage_views"][v]["consumed"], "new": sn["coverage_views"][v]["consumed"],
                     "base_ratio": sb["coverage_views"][v]["ratio"], "new_ratio": sn["coverage_views"][v]["ratio"]}
                 for v in VIEWS}
        lb = pd.read_parquet(b / "findings" / "sw_device_internal_links.parquet")
        ln = pd.read_parquet(n / "findings" / "sw_device_internal_links.parquet")
        lost = set(lb.link_id) - set(ln.link_id)
        added = set(ln.link_id) - set(lb.link_id)
        decisions = pd.read_parquet(n / "findings" / "sw_unregistered_pin_decisions.parquet")
        reasons = Counter(decisions.reason.tolist()) if len(decisions) else Counter()
        blocks = pd.read_parquet(n / "findings" / "sw_unregistered_symb2.parquet")
        sources = Counter(ln.source.fillna("sw_internal_element").tolist()) if len(ln) else Counter()
        per[pid] = {"eligible": eligible, "views": views, "links_base": len(lb), "links_new": len(ln),
                    "links_lost": len(lost), "links_added": len(added), "sources": dict(sources),
                    "decision_reasons": dict(reasons), "stats": sn["device_internal"]["stats"],
                    "unregistered_symb2": sn["device_internal"].get("unregistered_symb2"),
                    "single_end_decisions": len(decisions)}
        totals["eligible"] += eligible
        for v in VIEWS:
            totals["views"][v]["base"] += views[v]["base"]
            totals["views"][v]["new"] += views[v]["new"]
        totals["links_base"] += len(lb)
        totals["links_new"] += len(ln)
        totals["links_lost"] += len(lost)
        totals["links_added"] += len(added)
        totals["sources"].update(sources)
        totals["reasons"].update(reasons)
        totals["blocks"] += len(blocks)
        totals["blocks_label_resolved"] += int(blocks.label_resolved.sum()) if len(blocks) else 0
        totals["termpoints"] += int(blocks.termpoints.map(lambda s: len(json.loads(s))).sum()) if len(blocks) else 0
        totals["stats"].update({k: v for k, v in sn["device_internal"]["stats"].items() if isinstance(v, int)})
    for v in VIEWS:
        item = totals["views"][v]
        item["base_ratio"] = item["base"] / totals["eligible"]
        item["new_ratio"] = item["new"] / totals["eligible"]
    result = {"projects": per, "totals": {**{k: v for k, v in totals.items() if k not in ("sources", "reasons", "stats")},
                                          "sources": dict(totals["sources"]), "reasons": dict(totals["reasons"]),
                                          "stats": dict(totals["stats"])}}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


if __name__ == "__main__":
    res = main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
    print(json.dumps(res["totals"], ensure_ascii=False, indent=1))
