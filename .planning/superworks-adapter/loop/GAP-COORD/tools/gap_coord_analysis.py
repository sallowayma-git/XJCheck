"""GAP-COORD accounting: every R-RECOGNITION-GAP observation of the baseline, before and after the gate.

For each observation of the frozen 2594dbe findings (state INCOMPLETE/AMBIGUOUS) the table records
  old: emitted (in the baseline issue list) | group_suppressed (the legacy line-group rule hid it) | filtered (no wire/no group)
  new: emitted (in the new issue list, terminal or observation or page summary) | <gate step> | filtered
and writes per-step closure counts, the set of observations that the new code emits but the legacy rule hid (the
regression surface), and the sample list used for the DXF checks.

Usage: python gap_coord_analysis.py <out_dir> [pids...]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
BASELINE = REPO / ".tmp/engine_coordination_full_acceptance/current"
RUNS = REPO / ".tmp/loop_gapcoord_work/new"
DEFAULT_PIDS = ["p001", "p003", "p022", "p026", "p044", "p051", "p061", "p071", "p074", "p075"]


def _find(root: Path, pid: str) -> Path:
    return next(p for p in (root / pid).glob("*") if (p / "findings").is_dir())


def _list(value):
    if isinstance(value, str):
        return json.loads(value) if value else []
    return list(value or []) if value is not None and not (isinstance(value, float) and value != value) else []


def analyse_project(pid: str):
    base = _find(BASELINE, pid)
    run = next(p for p in (RUNS / pid).glob("*") if (p / "audit").is_dir())
    base_issues = json.loads((base / "audit" / "issues.json").read_text(encoding="utf-8"))
    new_issues = json.loads((run / "audit" / "issues.json").read_text(encoding="utf-8"))
    emitted_old, emitted_new, presentation_new = {}, {}, {}
    for issue in base_issues:
        if issue["rule_id"] != "R-RECOGNITION-GAP":
            continue
        for obs in (issue.get("evidence") or {}).get("resolution_observations") or []:
            emitted_old[obs["record_id"]] = issue["issue_id"]
    for issue in new_issues:
        if issue["rule_id"] != "R-RECOGNITION-GAP":
            continue
        presentation = (issue.get("evidence") or {}).get("presentation") or "observation"
        for obs in (issue.get("evidence") or {}).get("resolution_observations") or []:
            emitted_new[obs["record_id"]] = issue["issue_id"]
            presentation_new[obs["record_id"]] = presentation
    diag = pd.read_parquet(run / "audit" / "sw_recognition_diagnostics.parquet")
    suppressed_new = dict(zip(diag["record_id"], diag["suppressed_by"]))
    obs = pd.read_parquet(base / "findings" / "sw_resolution_observations.parquet")
    pairs = pd.read_parquet(base / "findings" / "pairs.parquet")
    covered_groups = set()
    for row in pairs.itertuples(index=False):
        evidence = json.loads(row.evidence) if isinstance(row.evidence, str) and row.evidence else {}
        if row.status != "discard" or evidence.get("discard_reason") == "device_internal":
            if isinstance(row.line_group_id, str):
                covered_groups.add((row.file_id, row.sheet_id, row.line_group_id))
    rows = []
    for item in obs.itertuples(index=False):
        if item.state not in ("INCOMPLETE", "AMBIGUOUS"):
            continue
        rid = item.record_id
        group = (item.file_id, item.sheet_id, item.line_group_id if isinstance(item.line_group_id, str) else None)
        if rid in emitted_old:
            old = "emitted"
        elif group in covered_groups:
            old = "group_suppressed"
        else:
            old = "filtered"
        if rid in emitted_new:
            new = "emitted:" + presentation_new[rid]
        elif rid in suppressed_new:
            new = "suppressed:" + suppressed_new[rid]
        else:
            new = "filtered"
        rows.append({"project": pid, "record_id": rid, "file_id": item.file_id, "sheet_id": item.sheet_id,
                     "line_group_id": group[2], "state": item.state, "old": old, "new": new,
                     "reason_codes": item.reason_codes, "coords": item.coords,
                     "left": item.left, "right": item.right, "source_handles": item.source_handles,
                     "emitted_new_issue": emitted_new.get(rid)})
    return rows, diag


def main(argv):
    out = Path(argv[0])
    pids = argv[1:] or DEFAULT_PIDS
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    diags = []
    for pid in pids:
        project_rows, diag = analyse_project(pid)
        rows.extend(project_rows)
        diag = diag.assign(project=pid)
        diags.append(diag)
        print(pid, len(project_rows), flush=True)
    table = pd.DataFrame(rows)
    table.to_parquet(out / "observation_table.parquet", index=False)
    pd.concat(diags, ignore_index=True).to_parquet(out / "suppressed_all.parquet", index=False)
    matrix = table.groupby(["old", "new"]).size().rename("n").reset_index()
    matrix.to_csv(out / "old_new_matrix.csv", index=False, encoding="utf-8")
    summary = {"observations": len(table), "old": dict(Counter(table["old"])), "new": dict(Counter(table["new"])),
               "reappeared_from_group_suppressed": int(((table["old"] == "group_suppressed") & table["new"].str.startswith("emitted")).sum()),
               "emitted_before_now_suppressed": int(((table["old"] == "emitted") & table["new"].str.startswith("suppressed")).sum()),
               "emitted_before_now_filtered": int(((table["old"] == "emitted") & (table["new"] == "filtered")).sum()),
               "per_step": dict(Counter(table.loc[table["new"].str.startswith("suppressed"), "new"]))}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
