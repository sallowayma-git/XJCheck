"""B-1 FIX step 5: compare replay outputs for the five projects (read-only).

Runs compared per project:
  R13  = .tmp/superworks_round13_full        (historical; pre-dates HEAD commits)
  BASE = .tmp/loop_invis_base                (HEAD snapshot, no fix; clean A/B baseline)
  FIX  = .tmp/loop_invis                     (HEAD + invisible-text fix)

Pairs are matched by content key (sheet_id, pair_kind, left/right text_id, left/right value),
because pair_id counters shift when pairs disappear. Writes .tmp/loop_invis_compare/compare.json
and prints a compact table.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
PROJECTS = ["p051", "p062", "p069", "p071", "p075"]
RUNS = {
    "R13": ROOT / ".tmp/superworks_round13_full",
    "BASE": ROOT / ".tmp/loop_invis_base",
    "FIX": ROOT / ".tmp/loop_invis",
}
OUT = ROOT / ".tmp/loop_invis_compare"
PAIR_NAMES = {
    "p051": ["PC0075", "PC0104", "PC0127", "PC0152", "PC0203", "PC0204"],
    "p062": ["PC0019", "PC0125", "PC0120", "PC0121"],
    "p069": ["PC0074"],
    "p071": ["PC0053", "PC0052", "PC0054", "PC0019", "PC0001", "PC0010"],
    "p075": ["PC0232", "PC0440"],
}


def findings_dir(root: Path, proj: str) -> Path | None:
    hits = sorted(glob.glob(str(root / proj / "*" / "findings" / "pairs.parquet")))
    return Path(hits[0]).parent if hits else None


def load(root: Path, proj: str):
    fdir = findings_dir(root, proj)
    if fdir is None:
        return None, None, None
    pairs = pd.read_parquet(fdir / "pairs.parquet")
    issues_path = list(fdir.parent.glob("audit/issues.json")) or list((fdir.parent.parent).glob("audit/issues.json"))
    issues = json.loads(issues_path[0].read_text(encoding="utf-8")) if issues_path else []
    texts = pd.read_parquet(fdir / "texts.parquet") if (fdir / "texts.parquet").exists() else None
    return pairs, issues, texts


def key_of(row) -> tuple:
    # Coordinates keep otherwise-empty ordinary_pair rows (no text ids) distinct.
    def s(v):
        return "" if v is None or (isinstance(v, float) and v != v) else str(v)

    def c(v):
        return "" if v is None or (isinstance(v, float) and v != v) else f"{float(v):.3f}"

    return (s(row.sheet_id), s(row.pair_kind), s(row.line_group_id), s(row.left_text_id), s(row.right_text_id),
            s(row.left_value), s(row.right_value), c(row.left_coord_x), c(row.left_coord_y),
            c(row.right_coord_x), c(row.right_coord_y))


def status_counts(pairs: pd.DataFrame) -> dict:
    return {k: int(v) for k, v in pairs.status.value_counts().items()}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"projects": {}}
    for proj in PROJECTS:
        data = {name: load(root, proj) for name, root in RUNS.items()}
        entry: dict = {"status": {}, "issues": {}, "diff_vs_base": {}, "diff_vs_r13": {}, "named": {}}
        for name, (pairs, issues, _) in data.items():
            if pairs is None:
                entry["status"][name] = "MISSING"
                continue
            entry["status"][name] = status_counts(pairs)
            entry["issues"][name] = len(issues)
        base_p = data["BASE"][0]
        fix_p = data["FIX"][0]
        r13_p = data["R13"][0]

        def diff(a: pd.DataFrame, b: pd.DataFrame) -> dict:
            # Multiset per key: each key may map to several rows (e.g. repeated ordinary pairs).
            def group(frame):
                g: dict = {}
                for r in frame.itertuples(index=False):
                    g.setdefault(key_of(r), []).append(r)
                return g

            ga, gb = group(a), group(b)
            fmt = lambda r: {"pair_id": r.pair_id, "status": r.status, "left": r.left_value, "right": r.right_value,
                             "sheet": r.sheet_id, "left_text_id": r.left_text_id, "right_text_id": r.right_text_id,
                             "left_coord": [r.left_coord_x, r.left_coord_y], "right_coord": [r.right_coord_x, r.right_coord_y],
                             "rationale": r.rationale}
            vanished, appeared, changed = [], [], []
            for k in set(ga) | set(gb):
                ra, rb = ga.get(k, []), gb.get(k, [])
                sa = sorted(r.status for r in ra)
                sb = sorted(r.status for r in rb)
                if sa == sb:
                    continue
                if not rb:
                    vanished += [fmt(r) for r in ra]
                elif not ra:
                    appeared += [fmt(r) for r in rb]
                else:
                    changed.append({"before": [fmt(r) for r in ra], "after": [fmt(r) for r in rb]})
            return {
                "vanished": vanished,
                "appeared": appeared,
                "status_changed": changed,
                "n_vanished": len(vanished), "n_appeared": len(appeared), "n_status_changed": len(changed),
            }

        if base_p is not None and fix_p is not None:
            entry["diff_vs_base"] = diff(base_p, fix_p)
        if r13_p is not None and fix_p is not None:
            entry["diff_vs_r13"] = diff(r13_p, fix_p)
        # Named targets: locate by content in the base run (pair_id counters shift between runs),
        # then report the status of the same content key in the fix run (or "vanished").
        if base_p is not None and fix_p is not None:
            fix_groups: dict = {}
            for r in fix_p.itertuples(index=False):
                fix_groups.setdefault(key_of(r), []).append(r.status)
            base_by_id = {r.pair_id: r for r in base_p.itertuples(index=False)}
            r13_by_id = {r.pair_id: r for r in r13_p.itertuples(index=False)} if r13_p is not None else {}
            for name in PAIR_NAMES.get(proj, []):
                row: dict = {}
                for label, src in (("R13", r13_by_id), ("BASE", base_by_id)):
                    hit = src.get(name)
                    if hit is None:
                        row[label] = None
                        continue
                    row[label] = {"status": hit.status, "left": hit.left_value, "right": hit.right_value,
                                  "sheet": hit.sheet_id, "rationale": hit.rationale[:70]}
                hit = base_by_id.get(name)
                if hit is not None:
                    after = fix_groups.get(key_of(hit))
                    row["FIX_same_content"] = sorted(after) if after else "vanished"
                entry["named"][name] = row
        report["projects"][proj] = entry
    (OUT / "compare.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # Target sheets: per-sheet pass/review/discard counts, base vs fix, plus the sheet-level diff.
    target_sheets = {"p062": ["S0012", "S0013"], "p071": ["S0011"], "p075": ["S0014", "S0015"]}
    sheet_report: dict = {}
    for proj, sheets in target_sheets.items():
        base_p, _, _ = load(RUNS["BASE"], proj)
        fix_p, _, _ = load(RUNS["FIX"], proj)
        for sheet in sheets:
            def counts(frame):
                sub = frame[frame.sheet_id == sheet]
                return {k: int(v) for k, v in sub.status.value_counts().items()}
            sheet_report[f"{proj}/{sheet}"] = {"BASE": counts(base_p), "FIX": counts(fix_p)}
    report["target_sheets"] = sheet_report
    (OUT / "compare.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    for proj, entry in report["projects"].items():
        print(proj, "status", entry["status"], "issues", entry["issues"])
        for label in ("diff_vs_base", "diff_vs_r13"):
            d = entry.get(label) or {}
            if d:
                print(f"  {label}: vanished={d['n_vanished']} appeared={d['n_appeared']} status_changed={d['n_status_changed']}")
        for name, v in entry["named"].items():
            print("   named", name, v)
    for key, v in sheet_report.items():
        print("sheet", key, v)
    print("written", OUT / "compare.json")


if __name__ == "__main__":
    sys.exit(main())
