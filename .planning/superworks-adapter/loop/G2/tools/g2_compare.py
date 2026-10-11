"""G2 comparison (read-only): round19 baseline (HEAD code) vs the G2 replay, for the 10 review projects.

Writes only under .tmp/loop_g2_compare/ (never the .planning regression*.json files that compare_runs.py overwrites).
Pair identity is content-based, because pair_id is a sequence counter that shifts when line groups change.
Usage: python g2_compare.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
BEFORE = ROOT / ".tmp" / "superworks_round19_full"
AFTER = ROOT / ".tmp" / "loop_g2"
OUT = ROOT / ".tmp" / "loop_g2_compare"
PIDS = ["p001", "p003", "p022", "p044", "p050", "p051", "p061", "p071", "p075", "p076"]
COVERAGE_VIEWS = ("strict", "with_continuity", "with_internal", "total")


def project_dir(base: Path, pid: str) -> Path:
    return Path(json.loads((base / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"])


def complete(base: Path, pid: str) -> dict:
    return json.loads((base / pid / "complete.json").read_text(encoding="utf-8"))


def pair_key(row: dict) -> tuple:
    return (row.get("sheet_id"), row.get("left_text_id"), row.get("right_text_id"),
            row.get("left_value"), row.get("right_value"), row.get("pair_kind"))


def load_pairs(findings: Path) -> dict:
    frame = pd.read_parquet(findings / "pairs.parquet")
    return {pair_key(r): r for r in frame.to_dict(orient="records")}


def load_issues(audit: Path) -> list[dict]:
    return json.loads((audit / "issues.json").read_text(encoding="utf-8"))


def issue_key(row: dict) -> tuple:
    return (row.get("rule_id"), row.get("sheet_id"), row.get("left_value"), row.get("right_value"))


def group_split_stats(before_findings: Path, after_findings: Path) -> dict:
    """Compare line groups by member-set identity (a line can sit in several groups, so no line->group map).

    only_before: legacy member sets that no longer exist after the change (merged groups that were split).
    only_after: member sets that are new after the change (the pieces of a split, or new singletons).
    """
    def sets(path: Path) -> list[frozenset]:
        frame = pd.read_parquet(path / "line_groups.parquet")
        out = []
        for row in frame.itertuples():
            members = json.loads(row.member_line_ids) if isinstance(row.member_line_ids, str) else list(row.member_line_ids)
            out.append(frozenset(members))
        return out

    before, after = sets(before_findings), sets(after_findings)
    before_set, after_set = set(before), set(after)
    only_before = [m for m in before_set if m not in after_set]
    only_after = [m for m in after_set if m not in before_set]
    return {"before_groups": len(before), "after_groups": len(after),
            "delta_groups": len(after) - len(before),
            "only_before_member_sets": len(only_before), "only_after_member_sets": len(only_after)}


def main() -> None:
    global AFTER, OUT, PIDS
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--after", default=str(AFTER))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--pids", nargs="*", default=PIDS)
    args = parser.parse_args()
    AFTER, OUT, PIDS = Path(args.after), Path(args.out), list(args.pids)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"projects": {}}
    totals = collections.Counter()
    rule_counts = {"before": collections.Counter(), "after": collections.Counter()}
    added_issues, removed_issues, added_pairs, removed_pairs = [], [], [], []
    for pid in PIDS:
        bdir, adir = project_dir(BEFORE, pid), project_dir(AFTER, pid)
        bf, af = bdir / "findings", adir / "findings"
        groups = group_split_stats(bf, af)
        bpairs, apairs = load_pairs(bf), load_pairs(af)
        added_keys = apairs.keys() - bpairs.keys()
        removed_keys = bpairs.keys() - apairs.keys()
        status_moves = collections.Counter(
            (bpairs[k].get("status"), apairs[k].get("status"))
            for k in apairs.keys() & bpairs.keys() if apairs[k].get("status") != bpairs[k].get("status")
        )
        added_kind = collections.Counter((apairs[k].get("pair_kind"), apairs[k].get("status")) for k in added_keys)
        removed_kind = collections.Counter((bpairs[k].get("pair_kind"), bpairs[k].get("status")) for k in removed_keys)
        for k in added_keys:
            row = apairs[k]
            added_pairs.append({"project": pid, **{f: row.get(f) for f in (
                "sheet_id", "left_value", "right_value", "pair_kind", "status", "line_group_id")}})
        for k in removed_keys:
            row = bpairs[k]
            removed_pairs.append({"project": pid, **{f: row.get(f) for f in (
                "sheet_id", "left_value", "right_value", "pair_kind", "status", "line_group_id")}})
        b_issues = load_issues(bdir / "audit")
        a_issues = load_issues(adir / "audit")
        b_index = {issue_key(r): r for r in b_issues}
        a_index = {issue_key(r): r for r in a_issues}
        new_keys = a_index.keys() - b_index.keys()
        gone_keys = b_index.keys() - a_index.keys()
        for r in b_issues:
            rule_counts["before"][r.get("rule_id")] += 1
        for r in a_issues:
            rule_counts["after"][r.get("rule_id")] += 1
        for k in sorted(new_keys):
            row = a_index[k]
            added_issues.append({"project": pid, **{f: row.get(f) for f in (
                "rule_id", "sheet_id", "left_value", "right_value", "pair_id", "severity")}})
        for k in sorted(gone_keys):
            row = b_index[k]
            removed_issues.append({"project": pid, **{f: row.get(f) for f in (
                "rule_id", "sheet_id", "left_value", "right_value", "pair_id", "severity")}})
        bsum = json.loads((bf / "superworks_summary.json").read_text(encoding="utf-8"))
        asum = json.loads((af / "superworks_summary.json").read_text(encoding="utf-8"))
        coverage = {view: {"eligible": bsum["coverage_views"]["eligible"],
                           "before": bsum["coverage_views"][view]["consumed"],
                           "after": asum["coverage_views"][view]["consumed"]} for view in COVERAGE_VIEWS}
        bc, ac = complete(BEFORE, pid), complete(AFTER, pid)
        report["projects"][pid] = {
            "line_groups": groups,
            "pairs": {"before": len(bpairs), "after": len(apairs), "added": len(added_keys),
                      "removed": len(removed_keys),
                      "status_moves": {f"{a}->{b}": n for (a, b), n in status_moves.items()},
                      "added_by_kind_status": {f"{k[0]}|{k[1]}": n for k, n in added_kind.items()},
                      "removed_by_kind_status": {f"{k[0]}|{k[1]}": n for k, n in removed_kind.items()}},
            "issues": {"before": len(b_issues), "after": len(a_issues),
                       "added": len(new_keys), "removed": len(gone_keys)},
            "coverage": coverage,
            "elapsed_seconds": {"before": bc["elapsed_seconds"], "after": ac["elapsed_seconds"]},
            "stage_seconds": {"before": bc.get("stage_seconds"), "after": ac.get("stage_seconds")},
        }
        totals["line_groups_delta"] += groups["delta_groups"]
        totals["line_groups_only_before"] += groups["only_before_member_sets"]
        totals["line_groups_only_after"] += groups["only_after_member_sets"]
        totals["pairs_added"] += len(added_keys)
        totals["pairs_removed"] += len(removed_keys)
        totals["issues_added"] += len(new_keys)
        totals["issues_removed"] += len(gone_keys)
    report["totals"] = dict(totals)
    report["rule_counts"] = {k: dict(v) for k, v in rule_counts.items()}
    (OUT / "g2_compare.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for name, rows in (("issues_added", added_issues), ("issues_removed", removed_issues),
                       ("pairs_added", added_pairs), ("pairs_removed", removed_pairs)):
        pd.DataFrame(rows).to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
    print(json.dumps(report["totals"], ensure_ascii=False))
    print(json.dumps(report["rule_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
