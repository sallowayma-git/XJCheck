"""B-1 FIX v2: compare the single-numeral-cell replay (v2) with the HEAD baseline and with fix v1.

Read-only. Reuses the content-key helpers of compare_invis_replay.py. Writes
.tmp/loop_invis2_compare/compare_v2.json and prints per-project counts, issue lists, and the
pair-level differences (vanished / appeared / status changed) for v2 vs v1 and v2 vs BASE.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_invis_replay import key_of, load  # noqa: E402

ROOT = Path("F:/workspace/XJToolkit")
PROJECTS = ["p051", "p062", "p069", "p071", "p075"]
RUNS = {"BASE": ROOT / ".tmp/loop_invis_base", "V1": ROOT / ".tmp/loop_invis", "V2": ROOT / ".tmp/loop_invis2"}
OUT = ROOT / ".tmp/loop_invis2_compare"


def issues_of(root: Path, proj: str):
    files = sorted(glob.glob(str(root / proj / "*" / "audit" / "issues.json")))
    return json.loads(Path(files[0]).read_text(encoding="utf-8")) if files else []


def diff(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    def group(frame):
        g: dict = {}
        for r in frame.itertuples(index=False):
            g.setdefault(key_of(r), []).append(r)
        return g

    ga, gb = group(a), group(b)
    fmt = lambda r: {"pair_id": r.pair_id, "status": r.status, "sheet": r.sheet_id, "kind": r.pair_kind,
                     "left": r.left_value, "right": r.right_value, "left_text_id": r.left_text_id,
                     "right_text_id": r.right_text_id, "rationale": str(r.rationale)[:90]}
    out = {"vanished": [], "appeared": [], "status_changed": []}
    for k in set(ga) | set(gb):
        ra, rb = ga.get(k, []), gb.get(k, [])
        if sorted(r.status for r in ra) == sorted(r.status for r in rb):
            continue
        if not rb:
            out["vanished"] += [fmt(r) for r in ra]
        elif not ra:
            out["appeared"] += [fmt(r) for r in rb]
        else:
            out["status_changed"].append({"before": [fmt(r) for r in ra], "after": [fmt(r) for r in rb]})
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for proj in PROJECTS:
        data = {name: load(root, proj)[0] for name, root in RUNS.items()}
        issues = {name: issues_of(root, proj) for name, root in RUNS.items()}
        entry = {
            "status": {name: (None if p is None else {k: int(v) for k, v in p.status.value_counts().items()})
                       for name, p in data.items()},
            "issues": {name: [{"rule": i.get("rule_id"), "sheet": (i.get("sheet_ids") or [None])[0]} for i in iss]
                       for name, iss in issues.items()},
            "v2_vs_v1": diff(data["V1"], data["V2"]),
            "v2_vs_base": diff(data["BASE"], data["V2"]),
        }
        report[proj] = entry
        print(proj, "status", entry["status"])
        print("  issues V1", [(x["rule"], x["sheet"]) for x in entry["issues"]["V1"]])
        print("  issues V2", [(x["rule"], x["sheet"]) for x in entry["issues"]["V2"]])
        for label in ("v2_vs_v1", "v2_vs_base"):
            d = entry[label]
            print(f"  {label}: vanished={len(d['vanished'])} appeared={len(d['appeared'])} changed={len(d['status_changed'])}")
            for x in d["vanished"]:
                print("    VANISH", x["pair_id"], x["status"], x["sheet"], x["kind"], repr(x["left"]), repr(x["right"]))
            for x in d["appeared"]:
                print("    APPEAR", x["pair_id"], x["status"], x["sheet"], x["kind"], repr(x["left"]), repr(x["right"]))
            for c in d["status_changed"]:
                print("    CHANGED", [(r["pair_id"], r["status"]) for r in c["before"]], "->", [(r["pair_id"], r["status"]) for r in c["after"]])
    (OUT / "compare_v2.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("written", OUT / "compare_v2.json")


if __name__ == "__main__":
    main()
