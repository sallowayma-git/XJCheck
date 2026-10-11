"""DEV-INT-DISCARD comparison of two replay runs (read-only).

Usage: python devdisc_compare.py BASE_RUN NEW_RUN OUT_JSON [--projects ...] [--discards-json OUT]

- Pairs: every pair is compared by its full row (pair_id included); status transitions are counted, and every
  transition is checked to be a device_internal discard.
- Issues: issues.json records compared as multisets (added / removed, listed).
- Coverage: the coverage views of superworks_summary.json (base views and new views, as each run wrote them).
- --discards-json: one record per pair the rule discarded in NEW (status before, kind, identities, port ids).
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd


def _findings(run: Path, pid: str) -> Path:
    project = next((run / pid).glob("*/findings"), None)
    if project is None:
        project = Path(json.loads((run / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"]) / "findings"
    return project


def _audit(run: Path, pid: str) -> Path:
    project = next((run / pid).glob("*/audit"), None)
    if project is None:
        project = Path(json.loads((run / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"]) / "audit"
    return project


def _text(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return "" if value is None or (isinstance(value, float) and value != value) else str(value)


def _evidence(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    return json.loads(value)


def _pair_rows(findings: Path) -> pd.DataFrame:
    return pd.read_parquet(findings / "pairs.parquet")


def _issue_keys(run: Path, pid: str) -> Counter:
    issues = json.loads((_audit(run, pid) / "issues.json").read_text(encoding="utf-8"))
    return Counter(json.dumps(i, sort_keys=True, ensure_ascii=False, default=str) for i in issues)


def compare_project(base: Path, new: Path, pid: str):
    bf, nf = _findings(base, pid), _findings(new, pid)
    bp, np_ = _pair_rows(bf), _pair_rows(nf)
    bmap = {r["pair_id"]: r for r in bp.to_dict("records")}
    nmap = {r["pair_id"]: r for r in np_.to_dict("records")}
    transitions = Counter()
    discards = []
    non_device_changes = []
    for pid_, new_row in nmap.items():
        old = bmap.get(pid_)
        if old is None:
            transitions[("added", new_row["status"], new_row["pair_kind"])] += 1
            continue
        if old["status"] == new_row["status"]:
            if _text(old["evidence"]) != _text(new_row["evidence"]) and new_row["status"] != "discard":
                transitions[("evidence_only", new_row["status"], new_row["pair_kind"])] += 1
            continue
        transitions[(old["status"], new_row["status"], new_row["pair_kind"])] += 1
        ev = _evidence(new_row["evidence"])
        if new_row["status"] == "discard" and ev.get("discard_reason") == "device_internal":
            detail = ev.get("device_internal_discard") or {}
            discards.append({"project": pid, "pair_id": pid_, "pair_kind": new_row["pair_kind"],
                             "status_before": old["status"], "sheet_id": new_row["sheet_id"],
                             "left_value": _text(new_row["left_value"]), "right_value": _text(new_row["right_value"]),
                             "terminal_identity": detail.get("terminal_identity"),
                             "terminal_label": detail.get("terminal_label"),
                             "terminal_port_ids": detail.get("terminal_port_ids"),
                             "other_identity": detail.get("other_identity"),
                             "other_category": detail.get("other_category"),
                             "other_label": detail.get("other_label"),
                             "other_port_ids": detail.get("other_port_ids"),
                             "other_unregistered": detail.get("other_unregistered")})
        else:
            non_device_changes.append({"pair_id": pid_, "from": old["status"], "to": new_row["status"]})
    for pair_id, old in bmap.items():
        if pair_id not in nmap:
            transitions[("removed", old["status"], old["pair_kind"])] += 1
    base_issues, new_issues = _issue_keys(base, pid), _issue_keys(new, pid)
    issues_added = list((new_issues - base_issues).elements())
    issues_removed = list((base_issues - new_issues).elements())
    bs = json.loads((bf / "superworks_summary.json").read_text(encoding="utf-8"))
    ns = json.loads((nf / "superworks_summary.json").read_text(encoding="utf-8"))
    return {"project": pid,
            "pairs_base": len(bp), "pairs_new": len(np_),
            "transitions": {"|".join(map(str, k)): v for k, v in transitions.items()},
            "non_device_internal_status_changes": non_device_changes,
            "device_internal_discards": len(discards),
            "issues_base": sum(_issue_keys(base, pid).values()), "issues_new": sum(new_issues.values()),
            "issues_added": issues_added, "issues_removed": issues_removed,
            "base_views": bs.get("coverage_views"), "new_views": ns.get("coverage_views"),
            "base_pair_discard_stats": bs.get("device_internal", {}).get("pair_discards"),
            "new_pair_discard_stats": ns.get("device_internal", {}).get("pair_discards"),
            "new_device_internal_stats": ns.get("device_internal", {}).get("stats"),
            "new_link_count": ns.get("device_internal", {}).get("link_count"),
            "base_link_count": bs.get("device_internal", {}).get("link_count"),
            "_discards": discards}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("new")
    parser.add_argument("out")
    parser.add_argument("--projects", nargs="*", default=None)
    parser.add_argument("--discards-json", default=None)
    args = parser.parse_args()
    base, new = Path(args.base), Path(args.new)
    projects = args.projects or sorted(p.name for p in new.iterdir() if p.is_dir() and p.name.startswith("p"))
    rows = [compare_project(base, new, pid) for pid in projects]
    discards = [d for r in rows for d in r.pop("_discards")]
    total = Counter()
    for r in rows:
        for k, v in r["transitions"].items():
            total[k] += v
    summary = {"projects": projects, "transition_totals": dict(total),
               "device_internal_discards": len(discards),
               "non_device_status_changes": sum(len(r["non_device_internal_status_changes"]) for r in rows),
               "issues_added": sum(len(r["issues_added"]) for r in rows),
               "issues_removed": sum(len(r["issues_removed"]) for r in rows),
               "issues_base": sum(r["issues_base"] for r in rows), "issues_new": sum(r["issues_new"] for r in rows)}
    Path(args.out).write_text(json.dumps({"summary": summary, "per_project": rows}, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    if args.discards_json:
        Path(args.discards_json).write_text(json.dumps(discards, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
