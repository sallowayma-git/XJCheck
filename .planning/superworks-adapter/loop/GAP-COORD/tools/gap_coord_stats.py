"""GAP-COORD final statistics for the 10-project proxy replay (read-only; writes details.json next to the README).

Reads: .tmp/loop_gapcoord_analysis (observation_table, summary) and .tmp/loop_gapcoord_work/new (issues.json per project)
and .tmp/engine_coordination_full_acceptance/current (baseline issues.json).
Usage: python gap_coord_stats.py <out_json>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
BASE = REPO / ".tmp/engine_coordination_full_acceptance/current"
NEW = REPO / ".tmp/loop_gapcoord_work/new"
ANALYSIS = REPO / ".tmp/loop_gapcoord_analysis"
PIDS = ["p001", "p003", "p022", "p026", "p044", "p051", "p061", "p071", "p074", "p075"]
TERMINAL = {"装置端子", "端子"}
ELEMENT = {"内部元件", "线圈"}


def issues_of(root: Path, pid: str):
    run = next(p for p in (root / pid).glob("*") if (p / "audit").is_dir())
    return json.loads((run / "audit" / "issues.json").read_text(encoding="utf-8"))


def side(value):
    if isinstance(value, str) and value:
        return json.loads(value)
    return {}


def main(argv):
    out = Path(argv[0])
    per_project = {}
    presentation = Counter()
    terminal_ports = set()
    terminal_issue_sizes = Counter()
    page_summaries = 0
    page_summary_ports = set()
    baseline_total = 0
    new_total = 0
    for pid in PIDS:
        base = [i for i in issues_of(BASE, pid) if i["rule_id"] == "R-RECOGNITION-GAP"]
        new = [i for i in issues_of(NEW, pid) if i["rule_id"] == "R-RECOGNITION-GAP"]
        baseline_total += len(base)
        new_total += len(new)
        counts = Counter()
        for issue in new:
            evidence = issue.get("evidence") or {}
            kind = evidence.get("presentation") or "observation"
            presentation[kind] += 1
            counts[kind] += 1
            if kind == "terminal":
                ports = evidence.get("terminal_port_ids") or []
                terminal_issue_sizes[len(ports)] += 1
                terminal_ports.update((pid, p) for p in ports)
            elif kind == "page_summary":
                page_summaries += 1
                for entry in evidence.get("terminal_ports") or []:
                    page_summary_ports.add((pid, entry["port_id"]))
        per_project[pid] = {"baseline": len(base), "new": len(new), **dict(counts)}
    table = pd.read_parquet(ANALYSIS / "observation_table.parquet")
    remaining = table[table["new"].str.startswith("emitted")].copy()
    remaining["left_cat"] = [side(v).get("category") or "-" for v in remaining["left"]]
    remaining["right_cat"] = [side(v).get("category") or "-" for v in remaining["right"]]
    remaining["left_id"] = [bool(side(v).get("value")) for v in remaining["left"]]
    remaining["right_id"] = [bool(side(v).get("value")) for v in remaining["right"]]

    def klass(row):
        pair = {row.left_cat, row.right_cat}
        if pair & TERMINAL and (pair & ELEMENT) and not (row.left_id and row.right_id):
            return "terminal_element_unidentified"
        if pair & TERMINAL and (pair - TERMINAL - ELEMENT - {"-"}) == set() and not (row.left_id and row.right_id):
            return "terminal_terminal_one_unidentified"
        if pair & TERMINAL:
            return "terminal_other"
        return "no_terminal"

    remaining["klass"] = remaining.apply(klass, axis=1)
    class_counts = dict(Counter(remaining["klass"]))
    pair_counts = dict(Counter(f"{a}|{b}" for a, b in zip(remaining["left_cat"], remaining["right_cat"])).most_common(12))
    stats = json.loads((ANALYSIS / "summary.json").read_text(encoding="utf-8"))
    result = {
        "projects": PIDS,
        "gap_issues": {"baseline": baseline_total, "new": new_total, "per_project": per_project},
        "presentation_issues": dict(presentation),
        "terminal_issues": {"issues": presentation["terminal"], "distinct_terminal_ports": len(terminal_ports),
                            "ports_per_issue_histogram": dict(sorted(terminal_issue_sizes.items()))},
        "page_summary": {"issues": page_summaries, "distinct_terminal_ports": len(page_summary_ports)},
        "observations": {"baseline_emitted": int(table["old"].eq("emitted").sum()),
                         "new_emitted": int(remaining.shape[0]), "closed_from_baseline": stats["emitted_before_now_suppressed"],
                         "reappeared": stats["reappeared_from_group_suppressed"]},
        "closures_by_step_sequential": stats["per_step"],
        "closures_from_baseline_emitted": dict(Counter(
            table.loc[table["old"].eq("emitted") & table["new"].str.startswith("suppressed"), "new"])),
        "remaining_classes": class_counts,
        "remaining_side_pairs_top": pair_counts,
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main(sys.argv[1:])
