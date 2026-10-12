"""P3-CROSS-DEVICE comparison of two replay roots (read-only).

usage: xdev_compare.py BASE_ROOT NEW_ROOT OUT_JSON [project ...]

Per project: pairs (matched by pair_id; pair ids shift when candidates change, so the status-change counts here are
NOT reliable: use xdev_summary.py, which matches pairs by content), guarded pairs
(evidence symbol_body_path_check) by submode and verdict, issues by (rule_id, sheet_id, message) with
added / removed rows, and the coverage views from superworks_summary.json.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


def project_dirs(root: Path) -> dict[str, Path]:
    out = {}
    for complete in root.glob("p*/complete.json"):
        data = json.loads(complete.read_text(encoding="utf-8"))
        out[complete.parent.name] = Path(data["project_dir"])
    return out


def frame(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def pair_frame(d: Path) -> pd.DataFrame:
    return frame(d / "findings/pairs.parquet")


def evidence_of(value) -> dict:
    if isinstance(value, dict):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def issue_keys(d: Path) -> Counter:
    path = d / "audit/issues.json"
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    keys: Counter = Counter()
    for it in items:
        keys[json.dumps({k: it.get(k) for k in ("rule_id", "sheet_id", "message") if k in it},
                        ensure_ascii=False, sort_keys=True)] += 1
    return keys


def issue_rows(d: Path) -> list[dict]:
    path = d / "audit/issues.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def summary(d: Path) -> dict:
    path = d / "findings/superworks_summary.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    base_root, new_root, out_json = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    only = set(sys.argv[4:])
    base, new = project_dirs(base_root), project_dirs(new_root)
    result: dict = {}
    for pid in sorted(set(base) & set(new)):
        if only and pid not in only:
            continue
        b, n = base[pid], new[pid]
        pb, pn = pair_frame(b), pair_frame(n)
        mb = pb.set_index("pair_id") if len(pb) else pb
        mn = pn.set_index("pair_id") if len(pn) else pn
        common = mb.index.intersection(mn.index)
        changed = Counter()
        for pair_id in common:
            if mb.at[pair_id, "status"] != mn.at[pair_id, "status"]:
                changed[f"{mb.at[pair_id, 'status']}->{mn.at[pair_id, 'status']}|{mb.at[pair_id, 'pair_kind']}"] += 1
        removed_ids = set(mb.index) - set(mn.index)
        added_ids = set(mn.index) - set(mb.index)
        guarded = Counter()
        guarded_rows = []
        for pair_id, row in mn.iterrows():
            ev = evidence_of(row.get("evidence"))
            check = ev.get("symbol_body_path_check")
            if not check:
                continue
            submode = ev.get("component_submode") or row.get("pair_kind")
            guarded[f"{submode}|{check.get('verdict')}|{row.get('status')}"] += 1
            guarded_rows.append({"pair_id": pair_id, "sheet_id": row.get("sheet_id"), "status": row.get("status"),
                                 "submode": submode, "left": row.get("left_value"), "right": row.get("right_value"),
                                 "check": check})
        # Pairs whose status changed and that were not guarded would be a side effect of the change.
        unguarded_changes = 0
        for pair_id in common:
            if mb.at[pair_id, "status"] != mn.at[pair_id, "status"]:
                ev = evidence_of(mn.at[pair_id, "evidence"])
                if "symbol_body_path_check" not in ev:
                    unguarded_changes += 1
        ib, inew = issue_keys(b), issue_keys(n)
        added_issues = inew - ib
        removed_issues = ib - inew
        sb, sn = summary(b), summary(n)
        cov = lambda s, view: (s.get("coverage_views", {}).get(view) or {})
        views = {}
        for view in ("strict", "with_continuity", "strict_excl_device_internal",
                     "with_continuity_excl_device_internal"):
            views[view] = {"base": [cov(sb, view).get("consumed"), cov(sb, view).get("eligible")],
                           "new": [cov(sn, view).get("consumed"), cov(sn, view).get("eligible")]}
        result[pid] = {
            "pairs": {"base": len(mb), "new": len(mn), "added_ids": len(added_ids), "removed_ids": len(removed_ids),
                      "status_changed": dict(changed), "status_changed_total": sum(changed.values()),
                      "status_changed_unguarded": unguarded_changes},
            "guarded": dict(guarded),
            "guarded_rows": guarded_rows,
            "issues": {"base": sum(ib.values()), "new": sum(inew.values()),
                       "added": {k: v for k, v in added_issues.items()},
                       "removed": {k: v for k, v in removed_issues.items()}},
            "issue_rows_new": issue_rows(n),
            "coverage": views,
        }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    for pid, r in result.items():
        cov = r["coverage"]["strict"]
        print(pid, "pairs", r["pairs"]["base"], "->", r["pairs"]["new"],
              "status_changed", r["pairs"]["status_changed_total"], "unguarded", r["pairs"]["status_changed_unguarded"],
              "| guarded", sum(r["guarded"].values()),
              "| issues", r["issues"]["base"], "->", r["issues"]["new"],
              "(+%d/-%d)" % (sum(r["issues"]["added"].values()), sum(r["issues"]["removed"].values())),
              "| strict", cov["base"], "->", cov["new"])


if __name__ == "__main__":
    main()
