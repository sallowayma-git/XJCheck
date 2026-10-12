"""P3-CROSS-DEVICE: offline scan of every final pair's straight path against the SuperWORKS symbol marks (read-only).

usage: xdev_scan_all.py RUN_ROOT OUT_JSON [project ...]

Marks are rebuilt from the replay outputs the same way wire_break_evidence_by_sheet builds them (registered SW ports
keyed by symbol_id, unregistered SYMB2 TERMPOINTs keyed by SW:file:sheet:instance). The path test is the production
PathBodyChecker. Tallies by pair_kind, status and verdict; lists body-crossing pass/review pairs for review.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

from dwg_audit.audit.line_groups import PathBodyChecker, WireBreakEvidence


def marks_for(fd: Path, sheet_ids: set[str]):
    ports = pd.read_parquet(fd / "sw_ports.parquet")
    unreg = pd.read_parquet(fd / "sw_unregistered_symb2.parquet") if (fd / "sw_unregistered_symb2.parquet").exists() else pd.DataFrame()
    rows: dict[str, list] = {}
    for p in ports.itertuples():
        key = p.symbol_id or f"PORT:{p.record_id}"
        rows.setdefault(p.sheet_id, []).append((key, p.record_id, float(p.start_x), float(p.start_y), float(p.end_x), float(p.end_y)))
    for u in unreg.itertuples():
        key = f"SW:{u.file_id}:{u.sheet_id}:{u.instance_path}"
        for t in json.loads(u.termpoints):
            (ax, ay), (bx, by) = t.get("a") or (0.0, 0.0), t.get("b") or (0.0, 0.0)
            rows.setdefault(u.sheet_id, []).append((key, f"{u.record_id}#{t.get('number')}", float(ax), float(ay), float(bx), float(by)))
    dots_path = fd / "sw_connect_dots.parquet"
    dots = pd.read_parquet(dots_path) if dots_path.exists() else pd.DataFrame()
    out = {}
    for sheet in sheet_ids:
        sheet_dots = tuple((float(d.x), float(d.y)) for d in dots.itertuples() if getattr(d, "sheet_id", None) == sheet) if len(dots) else ()
        out[sheet] = PathBodyChecker(WireBreakEvidence(marks=tuple(rows.get(sheet, ())), dots=sheet_dots))
    return out


def main() -> None:
    run, out_json = Path(sys.argv[1]), Path(sys.argv[2])
    only = set(sys.argv[3:])
    result: dict = {}
    for pdir in sorted(run.glob("p*")):
        pid = pdir.name
        if only and pid not in only:
            continue
        if not (pdir / "complete.json").exists():
            continue
        fd = Path(glob.glob(str(pdir / "*" / "findings"))[0])
        pairs = pd.read_parquet(fd / "pairs.parquet")
        checkers = marks_for(fd, set(pairs.sheet_id))
        tally = Counter()
        body_rows = []
        for r in pairs.itertuples():
            if r.left_coord_x is None or pd.isna(r.left_coord_x) or pd.isna(r.right_coord_x):
                tally[(r.pair_kind, r.status, "no_coords")] += 1
                continue
            checker = checkers.get(r.sheet_id)
            if checker is None:
                tally[(r.pair_kind, r.status, "no_marks")] += 1
                continue
            verdict, detail = checker.verdict((r.left_coord_x, r.left_coord_y), (r.right_coord_x, r.right_coord_y))
            key = verdict or detail.get("reason", "clear")
            tally[(r.pair_kind, r.status, key)] += 1
            if verdict in ("body", "ambiguous"):
                body_rows.append({"pair_id": r.pair_id, "sheet": r.sheet_id, "status": r.status, "kind": r.pair_kind,
                                  "left": r.left_value, "right": r.right_value, "verdict": verdict, **detail})
        result[pid] = {"tally": {"|".join(map(str, k)): v for k, v in tally.items()}, "body_rows": body_rows}
        print(pid, sum(tally.values()), dict(Counter({k[2]: v for k, v in tally.items() if k[2] in ('body', 'ambiguous')})), flush=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    total = Counter()
    for pid, r in result.items():
        for k, v in r["tally"].items():
            total[k] += v
    for k, v in sorted(total.items(), key=lambda kv: -kv[1]):
        print(v, k)


if __name__ == "__main__":
    main()
