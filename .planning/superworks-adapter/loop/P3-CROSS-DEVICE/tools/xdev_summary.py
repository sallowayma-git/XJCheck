"""P3-CROSS-DEVICE: full-run summary (read-only). Writes results/summary_<tag>.json.

usage: xdev_summary.py BASE_ROOT NEW_ROOT CENSUS_TAGGED_PARQUET TAG

Sections:
  pairs: total, status changes, guarded counts by submode / verdict / new status
  census_d3: the census D3 set (round-23 c-pass with no SW counterpart) and its status in the new run
  issues: added / removed issue rows keyed by (project, rule_id, sheet_id, message)
  coverage: sums of consumed / eligible for the strict and with_continuity views, base and new
  candidates: candidates accepted in base and rejected as path_crosses_symbol_body in new (stable key)
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

BASE, NEW, CENSUS, TAG = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
OUT = Path(__file__).resolve().parent / "results" / f"summary_{TAG}.json"


def project_dirs(root: Path) -> dict[str, Path]:
    out = {}
    for complete in root.glob("p*/complete.json"):
        out[complete.parent.name] = Path(json.loads(complete.read_text(encoding="utf-8"))["project_dir"])
    return out


def fdir(d: Path) -> Path:
    return d / "findings"


def content_key(row) -> tuple:
    def text(v):
        return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)

    return (row.sheet_id, text(row.left_text_id), text(row.right_text_id), text(row.left_value),
            text(row.right_value), row.pair_kind)


def evidence(v) -> dict:
    if isinstance(v, dict):
        return v
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return {}
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return {}


def issue_keys(d: Path, pid: str) -> Counter:
    path = d / "audit" / "issues.json"
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    keys: Counter = Counter()
    for it in items:
        keys[(pid, it.get("rule_id"), it.get("sheet_id"), it.get("message"))] += 1
    return keys


def main() -> None:
    base, new = project_dirs(BASE), project_dirs(NEW)
    census = pd.read_parquet(CENSUS)
    d3 = census[(census.tag == "c") & (census.status == "pass") & (census.sw_dup == "none")]
    out: dict = {"tag": TAG, "projects": len(set(base) & set(new))}
    status_changes: Counter = Counter()
    guarded: Counter = Counter()
    guarded_rows_by_pair: dict = {}
    issues_added: Counter = Counter()
    issues_removed: Counter = Counter()
    cov = {v: {"base": [0, 0], "new": [0, 0]} for v in ("strict", "with_continuity")}
    pair_total = {"base": 0, "new": 0}
    d3_status: Counter = Counter()
    accepted_to_path_rejected = 0
    per_project = {}
    for pid in sorted(set(base) & set(new)):
        b, n = base[pid], new[pid]
        pb = pd.read_parquet(fdir(b) / "pairs.parquet")
        pn = pd.read_parquet(fdir(n) / "pairs.parquet")
        pair_total["base"] += len(pb)
        pair_total["new"] += len(pn)
        # Pair ids shift when candidates change, so status changes are matched on content (sheet, end texts, values, kind).
        kb, kn = defaultdict(list), defaultdict(list)
        for row in pb.itertuples():
            kb[content_key(row)].append(row.status)
        for row in pn.itertuples():
            kn[content_key(row)].append(row.status)
        for k in set(kb) | set(kn):
            sb, sn = sorted(kb.get(k, [])), sorted(kn.get(k, []))
            if sb == sn:
                continue
            only_b = list((Counter(sb) - Counter(sn)).elements())
            only_n = list((Counter(sn) - Counter(sb)).elements())
            for x, y in zip(only_b, only_n):
                status_changes[f"{x}->{y}|{k[5]}"] += 1
        mn = pn.set_index("pair_id")
        for pair_id, row in mn.iterrows():
            ev = evidence(row.get("evidence"))
            check = ev.get("symbol_body_path_check")
            if check and check.get("verdict") in ("body", "ambiguous"):
                submode = ev.get("component_submode") or row.get("pair_kind")
                guarded[f"{submode}|{check.get('verdict')}|{row.get('status')}"] += 1
                guarded_rows_by_pair[(pid, pair_id)] = check.get("verdict")
        removed_ids = set(pb.pair_id) - set(pn.pair_id)
        out.setdefault("removed_pair_ids", 0)
        out["removed_pair_ids"] += len(removed_ids)
        # census D3
        for row in d3[d3.project_id == pid].itertuples():
            if row.pair_id in mn.index:
                ev = evidence(mn.at[row.pair_id, "evidence"])
                check = ev.get("symbol_body_path_check") or {}
                d3_status[f"{mn.at[row.pair_id, 'status']}|{check.get('verdict') or check.get('reason') or 'no_check'}"] += 1
            else:
                d3_status["removed"] += 1
        # issues
        ib, inew = issue_keys(b, pid), issue_keys(n, pid)
        issues_added += inew - ib
        issues_removed += ib - inew
        # coverage
        sb = json.loads((fdir(b) / "superworks_summary.json").read_text(encoding="utf-8"))
        sn = json.loads((fdir(n) / "superworks_summary.json").read_text(encoding="utf-8"))
        for view in cov:
            cb = (sb.get("coverage_views", {}).get(view) or {})
            cn = (sn.get("coverage_views", {}).get(view) or {})
            cov[view]["base"][0] += cb.get("consumed") or 0
            cov[view]["base"][1] += cb.get("eligible") or 0
            cov[view]["new"][0] += cn.get("consumed") or 0
            cov[view]["new"][1] += cn.get("eligible") or 0
        # candidates (stable key) accepted -> rejected path_crosses_symbol_body
        cb_ = pd.read_parquet(fdir(b) / "terminal_candidates.parquet")
        cn_ = pd.read_parquet(fdir(n) / "terminal_candidates.parquet")
        bk = cb_.set_index(["line_group_id", "side", "text_id"])
        nk = cn_[(cn_.status == "rejected") & (cn_.rejection_reason == "path_crosses_symbol_body")]
        for r in nk.itertuples():
            key = (r.line_group_id, r.side, r.text_id)
            if key in bk.index:
                row = bk.loc[key]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                if row["status"] == "accepted":
                    accepted_to_path_rejected += 1
        per_project[pid] = {"pairs": [len(pb), len(pn)], "issues": [sum(ib.values()), sum(inew.values())]}
    out["pairs_total"] = pair_total
    out["status_changes"] = dict(status_changes)
    out["status_changes_note"] = "matched on content key (sheet, end text ids, values, kind); unmatched pairs are not counted here"
    out["status_changes_total"] = sum(status_changes.values())
    out["guarded"] = dict(guarded)
    out["census_d3_status"] = dict(d3_status)
    out["census_d3_total_all_projects"] = int(len(d3))
    out["census_d3_total_in_run"] = int(sum(v for k, v in d3_status.items() if k != "removed")) if d3_status else 0
    out["issues_added"] = [list(k) + [v] for k, v in issues_added.items()]
    out["issues_removed"] = [list(k) + [v] for k, v in issues_removed.items()]
    out["issue_total"] = {"base": sum(sum(v.values()) for v in [issue_keys(base[p], p) for p in base if p in new]),
                          "new": sum(sum(v.values()) for v in [issue_keys(new[p], p) for p in base if p in new])}
    out["coverage"] = {view: {"base": v["base"], "new": v["new"],
                              "base_pct": round(100.0 * v["base"][0] / max(v["base"][1], 1), 2),
                              "new_pct": round(100.0 * v["new"][0] / max(v["new"][1], 1), 2)}
                       for view, v in cov.items()}
    out["candidates_accepted_to_path_rejected"] = accepted_to_path_rejected
    out["per_project"] = per_project
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("projects", "pairs_total", "status_changes_total", "census_d3_total_in_run",
                                          "census_d3_status", "issue_total", "coverage",
                                          "candidates_accepted_to_path_rejected")}, ensure_ascii=False, indent=1))
    print("issues added", len(out["issues_added"]), "removed", len(out["issues_removed"]))


if __name__ == "__main__":
    main()
