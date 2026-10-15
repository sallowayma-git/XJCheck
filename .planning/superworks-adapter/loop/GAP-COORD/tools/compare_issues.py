"""Compare two issue lists per project: R-RECOGNITION-GAP by key, and every other rule by (rule, message, sheet).

Usage: python compare_issues.py <baseline_root> <run_root> <mode_dir_name> <out_json> [pids...]
baseline_root: .tmp/engine_coordination_full_acceptance/current (project dirs with audit/issues.json)
run_root: .tmp/loop_gapcoord_work/<mode>/<pid>/<family>/audit/issues.json (proxy run output)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT_PIDS = ["p001", "p003", "p022", "p026", "p044", "p051", "p061", "p071", "p074", "p075"]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def gap_key(issue):
    ev = issue.get("evidence") or {}
    return (issue.get("sheet_id"), ev.get("presentation") or "observation", ev.get("conflict_object_id") or "", issue.get("left_value"), issue.get("right_value"))


def other_key(issue):
    return (issue.get("rule_id"), issue.get("message"), issue.get("sheet_id"), issue.get("left_value"), issue.get("right_value"))


def main(argv):
    baseline_root, run_root, out_path = Path(argv[0]), Path(argv[1]), Path(argv[2])
    pids = argv[3:] or DEFAULT_PIDS
    report = {}
    for pid in pids:
        base_dir = next(p for p in (baseline_root / pid).glob("*") if (p / "audit").is_dir())
        base = load(base_dir / "audit" / "issues.json")
        run_dir = next(p for p in (run_root / pid).glob("*") if (p / "audit").is_dir())
        new = load(run_dir / "audit" / "issues.json")
        base_gap = [i for i in base if i["rule_id"] == "R-RECOGNITION-GAP"]
        new_gap = [i for i in new if i["rule_id"] == "R-RECOGNITION-GAP"]
        base_other = Counter(other_key(i) for i in base if i["rule_id"] != "R-RECOGNITION-GAP")
        new_other = Counter(other_key(i) for i in new if i["rule_id"] != "R-RECOGNITION-GAP")
        other_added = sum((new_other - base_other).values())
        other_removed = sum((base_other - new_other).values())
        base_obs = sum(len((i.get("evidence") or {}).get("resolution_observations") or []) for i in base_gap)
        new_obs = sum(len((i.get("evidence") or {}).get("resolution_observations") or []) for i in new_gap)
        report[pid] = {
            "baseline_gap_issues": len(base_gap), "new_gap_issues": len(new_gap),
            "baseline_gap_observations": base_obs, "new_gap_observations": new_obs,
            "new_presentation": dict(Counter((i.get("evidence") or {}).get("presentation") or "none" for i in new_gap)),
            "other_rules_added": other_added, "other_rules_removed": other_removed,
            "baseline_other": sum(base_other.values()), "new_other": sum(new_other.values()),
        }
        print(pid, report[pid], flush=True)
    totals = Counter()
    for item in report.values():
        for key in ("baseline_gap_issues", "new_gap_issues", "baseline_gap_observations", "new_gap_observations",
                    "other_rules_added", "other_rules_removed", "baseline_other", "new_other"):
            totals[key] += item[key]
    report["TOTAL"] = dict(totals)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("TOTAL", dict(totals))


if __name__ == "__main__":
    main(sys.argv[1:])
