"""Strict terminal-port coverage, recomputed from a run's raw tables (independent of superworks_artifacts).

Definition (the same as superworks_artifacts, which this checks):
- eligible: category in {端子, 装置端子}, has a wire contact, and its label is resolved;
- consumed (pairs only): a non-discard pair names the port in its SuperWORKS side, and that side's SuperWORKS
  value equals the pair's side value (casefold). This is the original strict definition, kept as the base figure;
- consumed_with_continuity: consumed, or eligible and covered by a cross-page continuity link
  (sw_cross_page_links.parquet, covers_target = True). This is the additive figure.

Usage: python coverage_strict.py <run_dir> [--projects ...] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

TERMINAL = {"端子", "装置端子"}


def _json(value):
    if value is None or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def project_coverage(findings: Path) -> dict:
    ports = pd.read_parquet(findings / "sw_ports.parquet", columns=["record_id", "category", "wire_contacts", "label"])
    eligible = {}
    for row in ports.itertuples():
        if row.category not in TERMINAL:
            continue
        label = _json(row.label) or {}
        if _json(row.wire_contacts) and label.get("resolved"):
            eligible[row.record_id] = True
    pairs = pd.read_parquet(findings / "pairs.parquet", columns=["status", "left_value", "right_value", "evidence"])
    consumed = set()
    for row in pairs.itertuples():
        if row.status == "discard":
            continue
        evidence = row.evidence if isinstance(row.evidence, dict) else (_json(row.evidence) or {})
        sw = evidence.get("superworks") or {}
        for side, value in (("left", row.left_value), ("right", row.right_value)):
            endpoint = sw.get(side) or {}
            sw_value = str(endpoint.get("value") or "").casefold()
            for port_id in endpoint.get("port_ids") or []:
                if sw_value and str(value or "").casefold() == sw_value:
                    consumed.add(port_id)
    covered = set()
    links_path = findings / "sw_cross_page_links.parquet"
    if links_path.exists():
        links = pd.read_parquet(links_path)
        if len(links) and "covers_target" in links.columns:
            covered = set(links.loc[links.covers_target.astype(bool), "target_port_id"])
    base = sum(1 for p in eligible if p in consumed)
    extended = sum(1 for p in eligible if p in consumed or p in covered)
    return {"eligible": len(eligible), "consumed": base, "consumed_with_continuity": extended,
            "added_by_continuity": extended - base, "covered_targets": len(covered & set(eligible))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--projects", nargs="*", default=None)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    run = Path(args.run_dir)
    result = {}
    for complete in sorted(run.glob("p*/complete.json")):
        pid = complete.parent.name
        if args.projects and pid not in args.projects:
            continue
        project_dir = Path(json.loads(complete.read_text(encoding="utf-8"))["project_dir"])
        findings = project_dir / "findings"
        result[pid] = project_coverage(findings)
    totals = Counter()
    for item in result.values():
        totals.update(item)
    totals = dict(totals)
    summary = {"totals": totals,
               "ratio_pairs_only": totals.get("consumed", 0) / totals["eligible"] if totals.get("eligible") else None,
               "ratio_with_continuity": totals.get("consumed_with_continuity", 0) / totals["eligible"] if totals.get("eligible") else None,
               "projects": result}
    if args.json:
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "projects"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
