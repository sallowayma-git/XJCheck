"""XPAGE-2 offline re-evaluation of contradiction candidates with equivalence groups (read-only).

Usage: python xp2_eval.py <run_dir> <out_json> [--projects ...]
Rules are switched by name so that each iteration's candidate count can be logged.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import xp2_load  # noqa: E402
import xp2_bridge  # noqa: E402
from dwg_audit.audit import superworks_cross_page as xc  # noqa: E402

RANGE = re.compile(r"(.+?)(\d+)[~～](\d+)")


def expand(identity: str) -> set[str]:
    """Identity keys a strip identity names: 'U3D7~8' -> {'u3d7~8','u3d7','u3d8'} (casefold)."""
    text = (identity or "").strip().casefold()
    keys = {text} if text else set()
    match = RANGE.fullmatch(identity.strip()) if identity else None
    if match and 0 <= int(match[3]) - int(match[2]) < 200:
        keys.update(f"{match[1]}{n}".casefold() for n in range(int(match[2]), int(match[3]) + 1))
    return keys


def project_eval(run_dir: Path, pid: str) -> tuple[list[dict], dict]:
    data = xp2_load.load_project(run_dir, pid)
    result = xc.build_cross_page_links(data["strips"], data["ports"], data["pairs"], data["pages"])
    info = data["strip_info"]
    strips = {r["record_id"]: r for r in data["strips"]}
    lines_df = []
    rows = []
    for rid, s in strips.items():
        meta = info[rid]
        xy = meta["row_xy"]
        rows.append({"record_id": rid, "file_id": s.get("file_id") or rid.split(":")[1], "group": meta["header_handle"],
                     "x": xy[0], "y": xy[1], "ident": s.get("endpoint_identity") or ""})
    findings = data["findings"]
    import pandas as pd
    l = pd.read_parquet(findings / "lines.parquet", columns=["file_id", "start_x", "start_y", "end_x", "end_y"])
    lines = [{"file_id": a, "x0": b, "y0": c, "x1": d, "y1": e} for a, b, c, d, e in
             zip(l.file_id, l.start_x, l.start_y, l.end_x, l.end_y)]
    bridges = xp2_bridge.bridge_pairs(rows, lines)
    comp = xp2_bridge.Components()
    for rid in strips:
        comp.find(rid)
    for a, b, _ in bridges:
        comp.union(a, b)
    # Identity index for one-hop cross-strip references (row names another row's identity, and back).
    by_ident = defaultdict(list)
    for rid, s in strips.items():
        for key in expand(s.get("endpoint_identity") or ""):
            by_ident[key].append(rid)
    far_of = {}
    for rid, s in strips.items():
        far_of[rid] = xc._connection_values(s.get("connections") or [])
    reciprocal = defaultdict(set)
    for rid, s in strips.items():
        for value in far_of[rid]:
            for other in by_ident.get(value, []):
                if other != rid and (far_of[other] & expand(s.get("endpoint_identity") or "")):
                    reciprocal[rid].add(other)
    members = {}
    for group in comp.groups():
        for rid in group:
            members[rid] = group
    claimants = defaultdict(set)
    for rec in result["links"] + result["candidates"]:
        claimants[rec["target_port_id"]].add(rec["strip_record_id"])
    records = []
    for cand in result["candidates"]:
        rid = cand["strip_record_id"]
        grp = members.get(rid, {rid})
        ident_keys = set()
        far_keys = set()
        for m in grp:
            ident_keys |= expand(strips[m].get("endpoint_identity") or "")
            far_keys |= {k for v in far_of[m] for k in expand(v)}
        hop_ident, hop_far = set(), set()
        for m in grp:
            for other in reciprocal.get(m, set()):
                og = members.get(other, {other})
                for o in og:
                    hop_ident |= expand(strips[o].get("endpoint_identity") or "")
                    hop_far |= {k for v in far_of[o] for k in expand(v)}
        target_keys = expand(cand["target_identity"])
        other_vals = {k for v in cand.get("consumer_other_values") or [] for k in expand(v)}
        flags = {
            "target_in_group": bool(target_keys & ident_keys),
            "other_in_group_identity": bool(other_vals & ident_keys),
            "other_in_group_far": bool(other_vals & far_keys),
            "target_in_hop": bool(target_keys & hop_ident),
            "other_in_hop": bool(other_vals & (hop_ident | hop_far)),
            "other_in_hop_far": bool(other_vals & hop_far),
            "target_shared_by_rows": len(claimants[cand["target_port_id"]]) >= 2,
        }
        records.append({**cand, "project_id": pid, "group_size": len(grp), "group_members": sorted(strips[m].get("endpoint_identity") or "" for m in grp),
                        "hop_count": sum(1 for m in grp if reciprocal.get(m)), "flags": flags,
                        "bridge_count": sum(1 for a, _, _ in bridges if a in grp)})
    meta = {"project_id": pid, "bridges": len(bridges), "stats": result["stats"],
            "candidate_count": len(result["candidates"])}
    return records, meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("out_json")
    parser.add_argument("--projects", nargs="*", default=None)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    projects = args.projects or sorted(p.name for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("p") and (p / "complete.json").exists())
    out, metas = [], []
    for pid in projects:
        records, meta = project_eval(run_dir, pid)
        out.extend(records)
        metas.append(meta)
        print(pid, meta["candidate_count"], meta["bridges"], flush=True)
    Path(args.out_json).write_text(json.dumps({"records": out, "meta": metas}, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
