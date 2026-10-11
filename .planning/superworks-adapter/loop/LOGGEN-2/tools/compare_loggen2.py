"""Compare a LOGGEN phase-2 replay with a reference replay (round15 by default).

Usage: python compare_loggen2.py <reference_output> <new_output> <out_dir> [pid ...]

Per project it reports:
  - pairs: added / removed / changed (same pair_id, different content), grouped by status and pair_kind;
  - issues: added / removed, compared as canonical JSON minus issue_id;
  - strict coverage (sw_port_coverage.parquet, eligible terminal ports and consumed ports) before and after;
  - which findings tables differ.
Writes <out_dir>/<pid>.json and <out_dir>/summary.json. Nothing under src/ or tests/ is touched.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

DEFAULT_PROJECTS = ["p001", "p003", "p022", "p044", "p050", "p051", "p061", "p071", "p075", "p076"]
TERMINAL = {"端子", "装置端子"}


def project_dir(root: Path, pid: str) -> Path:
    return Path(json.loads((root / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"])


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def pair_rows(frame: pd.DataFrame) -> dict[str, dict]:
    rows = {}
    for record in frame.to_dict("records"):
        rows[record["pair_id"]] = {key: (None if isinstance(value, float) and value != value else value)
                                   for key, value in record.items()}
    return rows


def strict_coverage(directory: Path) -> dict[str, int]:
    coverage = pd.read_parquet(directory / "findings/sw_port_coverage.parquet")
    terminal = coverage[coverage.category.isin(TERMINAL)]
    eligible = terminal[terminal.eligible.astype(bool)]
    return {"eligible": int(len(eligible)), "consumed": int(eligible.consumed.astype(bool).sum())}


def issue_keys(path: Path) -> Counter:
    issues = json.loads(path.read_text(encoding="utf-8"))
    keys = Counter()
    for issue in issues:
        body = {key: value for key, value in issue.items() if key != "issue_id"}
        keys[canonical(body)] += 1
    return keys


def compare_project(pid: str, ref: Path, new: Path) -> dict:
    rd, nd = project_dir(ref, pid), project_dir(new, pid)
    rp = pd.read_parquet(rd / "findings/pairs.parquet")
    np_ = pd.read_parquet(nd / "findings/pairs.parquet")
    ra, na = pair_rows(rp), pair_rows(np_)
    added = [na[k] for k in na if k not in ra]
    removed = [ra[k] for k in ra if k not in na]
    changed = []
    for key in ra:
        if key in na and canonical(ra[key]) != canonical(na[key]):
            before, after = ra[key], na[key]
            fields = sorted(k for k in set(before) | set(after) if canonical(before.get(k)) != canonical(after.get(k)))
            changed.append({"pair_id": key, "fields": fields, "status": (before.get("status"), after.get("status")),
                            "left": (before.get("left_value"), after.get("left_value")),
                            "right": (before.get("right_value"), after.get("right_value")),
                            "pair_kind": before.get("pair_kind")})
    ri, ni = issue_keys(rd / "audit/issues.json"), issue_keys(nd / "audit/issues.json")
    issues_added = list((ni - ri).elements())
    issues_removed = list((ri - ni).elements())
    differing = []
    for path in sorted((rd / "findings").glob("*.parquet")):
        other = nd / "findings" / path.name
        if not other.exists():
            differing.append(path.name + ":missing")
            continue
        if path.name.startswith("sw_wire_routes"):
            continue
        if not pd.read_parquet(path).equals(pd.read_parquet(other)):
            differing.append(path.name)
    return {
        "project": pid,
        "pairs_reference": len(rp),
        "pairs_new": len(np_),
        "pairs_added": len(added),
        "pairs_added_by": dict(Counter(f"{p['status']}|{p['pair_kind']}" for p in added)),
        "pairs_removed": len(removed),
        "pairs_removed_by": dict(Counter(f"{p['status']}|{p['pair_kind']}" for p in removed)),
        "pairs_changed": len(changed),
        "pairs_changed_detail": changed,
        "added_pairs": [{k: p.get(k) for k in ("pair_id", "file_id", "sheet_id", "line_group_id", "left_value",
                                              "right_value", "status", "pair_kind", "rationale", "left_text_id",
                                              "right_text_id")} | {"record_id": (p.get("evidence") and json.loads(p["evidence"]).get("sw_wire_route", {}).get("record_id"))}
                         for p in added],
        "issues_reference": sum(ri.values()),
        "issues_new": sum(ni.values()),
        "issues_added": [json.loads(k) for k in issues_added],
        "issues_removed": [json.loads(k) for k in issues_removed],
        "findings_differing": differing,
        "strict_reference": strict_coverage(rd),
        "strict_new": strict_coverage(nd),
    }


def main(reference: Path, new: Path, out_dir: Path, projects: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for pid in projects:
        result = compare_project(pid, reference, new)
        (out_dir / f"{pid}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        summary[pid] = {k: v for k, v in result.items() if k not in ("pairs_changed_detail", "added_pairs",
                                                                     "issues_added", "issues_removed")}
        print(pid, {k: summary[pid][k] for k in ("pairs_added", "pairs_removed", "pairs_changed",
                                                  "issues_reference", "issues_new")}, flush=True)
    total = Counter()
    for entry in summary.values():
        total["pairs_added"] += entry["pairs_added"]
        total["pairs_removed"] += entry["pairs_removed"]
        total["pairs_changed"] += entry["pairs_changed"]
        total["issues_reference"] += entry["issues_reference"]
        total["issues_new"] += entry["issues_new"]
        total["eligible_ref"] += entry["strict_reference"]["eligible"]
        total["consumed_ref"] += entry["strict_reference"]["consumed"]
        total["eligible_new"] += entry["strict_new"]["eligible"]
        total["consumed_new"] += entry["strict_new"]["consumed"]
    summary["_total"] = dict(total)
    summary["_total"]["strict_ratio_reference"] = total["consumed_ref"] / total["eligible_ref"] if total["eligible_ref"] else None
    summary["_total"]["strict_ratio_new"] = total["consumed_new"] / total["eligible_new"] if total["eligible_new"] else None
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("TOTAL", summary["_total"], flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(Path(args[0]), Path(args[1]), Path(args[2]), args[3:] or DEFAULT_PROJECTS)
