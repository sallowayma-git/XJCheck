"""GAP2-S impact (read-only): what the element-identity guard would do to the 97 existing identified-element links.

For each link: is the element identity a value of a live pair (status not discard), is the device port already covered
by a pair or a continuity link without it, and how many ports would lose coverage if the link were dropped.
Usage: python g2s_identified_impact.py ROUND IDENTIFIED_JSON OUT_JSON
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROUND, IDENT, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
rows = json.loads(IDENT.read_text(encoding="utf-8"))["rows"]
by_project = {}
for r in rows:
    by_project.setdefault(r["project"], []).append(r)

stats = Counter()
detail = []
for pid, items in sorted(by_project.items()):
    findings = next(ROUND.glob(f"{pid}/*/findings"))
    pairs = pd.read_parquet(findings / "pairs.parquet")
    live = pairs[pairs["status"] != "discard"]
    live_values = set()
    for r in live.to_dict("records"):
        for key in ("left_value", "right_value"):
            if isinstance(r.get(key), str):
                live_values.add(r[key].casefold())
    coverage = pd.read_parquet(findings / "sw_port_coverage.parquet")
    cov = {r["port_id"]: r for r in coverage.to_dict("records")}
    links = pd.read_parquet(findings / "sw_device_internal_links.parquet")
    per_port = Counter(links["port_id"]) if len(links) else Counter()
    for r in items:
        identity_live = r["element_identity"].casefold() in live_values
        stats["element_identity_in_live_pair"] += int(identity_live)
        port = cov.get(r["port_id"], {})
        consumed = bool(port.get("consumed"))
        continuity = bool(port.get("consumed_with_continuity"))
        other_internal = per_port[r["port_id"]] > 1
        # Dropping this link would uncover the port only if no pair, continuity link, or other internal link covers it.
        would_uncover = not (consumed or continuity or other_internal)
        stats["port_covered_by_pair"] += int(consumed)
        stats["port_covered_by_continuity"] += int(continuity)
        stats["would_uncover_if_dropped"] += int(would_uncover)
        detail.append({"project": pid, "port_id": r["port_id"], "device_identity": r["device_identity"],
                       "element_identity": r["element_identity"], "element_identity_in_live_pair": identity_live,
                       "port_consumed": consumed, "port_continuity": continuity, "would_uncover": would_uncover,
                       "pcl": r["pcl"]})
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"stats": dict(stats), "rows": detail}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(dict(stats), ensure_ascii=False, indent=1))
