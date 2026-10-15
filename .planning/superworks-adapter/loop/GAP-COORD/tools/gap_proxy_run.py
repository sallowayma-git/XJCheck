"""GAP-COORD proxy replay: rerun the report stage on frozen 2594dbe findings with a chosen src tree (read-only inputs).

The full pipeline (replay.py) is run by the main thread. This proxy exists to check the report-stage gate on the
frozen findings of HEAD 2594dbe without re-extracting: it copies each baseline project directory (minus the DXF cache),
backfills the two columns the new writer adds (``wire_handles`` on sw_device_internal_links and ``end_geometry`` on
sw_resolution_observations) by calling the writer's own functions on the parquet inputs, and then runs
``rerun_audit_from_findings`` from the chosen source tree.

Usage:
  PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 python -I gap_proxy_run.py <src_dir> <work_dir> <mode> [pids...]
  mode: "head" (no backfill; use with the HEAD src export) or "new" (backfill + working-tree src)
Writes <work_dir>/<pid>/<family>/ (copied project dir; audit/ regenerated) and <work_dir>/<mode>_summary.json.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

REPO = Path("F:/workspace/XJToolkit")
CURRENT = REPO / ".tmp/engine_coordination_full_acceptance/current"
MANIFEST = REPO / ".planning/superworks-adapter/corpus_manifest.json"
DEFAULT_PIDS = ["p001", "p003", "p022", "p026", "p044", "p051", "p061", "p071", "p074", "p075"]


def _records(frame):
    return [{k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()} for r in frame.to_dict("records")]


def _decode(value):
    if isinstance(value, str):
        return json.loads(value) if value else None
    return value


def backfill(findings: Path) -> None:
    """Add wire_handles (links) and end_geometry (observations) exactly as the new writer computes them."""
    import pandas as pd
    from dwg_audit.audit.superworks_device_internal import split_terminal_wires, wire_members_of_links
    from dwg_audit.report.superworks_artifacts import _observation_end_geometry

    ports = []
    for r in _records(pd.read_parquet(findings / "sw_ports.parquet")):
        ports.append({**r, "wire_contacts": _decode(r.get("wire_contacts")) or []})
    lines_frame = pd.read_parquet(findings / "lines.parquet")
    lines = [{"file_id": r["file_id"], "line_id": r["line_id"], "handle": r["handle"],
              "source_block_name": r.get("source_block_name"), "sx": r["start_x"], "sy": r["start_y"],
              "ex": r["end_x"], "ey": r["end_y"]} for r in _records(lines_frame)]
    line_objects = [SimpleNamespace(file_id=r["file_id"], sheet_id=r["sheet_id"], handle=r["handle"], source_block_name=r.get("source_block_name"),
                                    start_x=r["start_x"], start_y=r["start_y"], end_x=r["end_x"], end_y=r["end_y"],
                                    length=r["length"]) for r in _records(lines_frame)]
    groups = [{"file_id": r["file_id"], "member_line_ids": _decode(r.get("member_line_ids")) or []}
              for r in _records(pd.read_parquet(findings / "line_groups.parquet"))]
    dots = [{"file_id": r["file_id"], "x": r["x"], "y": r["y"]}
            for r in _records(pd.read_parquet(findings / "sw_connect_dots.parquet"))]
    mapping = split_terminal_wires(ports, lines, groups, dots)["mapping"]

    links_path = findings / "sw_device_internal_links.parquet"
    links = pd.read_parquet(links_path)
    link_rows = _records(links)
    members = wire_members_of_links(link_rows, mapping) if link_rows else {}
    links["wire_handles"] = [json.dumps(members.get(lid, []), ensure_ascii=False) for lid in links["link_id"]] if len(links) else []
    links.to_parquet(links_path, index=False)

    obs_path = findings / "sw_resolution_observations.parquet"
    observations = _records(pd.read_parquet(obs_path))
    decoded = [{**r, "left": _decode(r.get("left")), "right": _decode(r.get("right")), "coords": _decode(r.get("coords")),
                "source_handles": _decode(r.get("source_handles"))} for r in observations]
    unreg_frame = pd.read_parquet(findings / "sw_unregistered_symb2.parquet") if (findings / "sw_unregistered_symb2.parquet").exists() else None
    unreg = []
    if unreg_frame is not None:
        for r in _records(unreg_frame):
            unreg.append({"file_id": r["file_id"], "sheet_id": r["sheet_id"],
                          "termpoints": _decode(r.get("termpoints")) or []})
    data = SimpleNamespace(resolution_observations=decoded, unregistered_symb2=unreg)
    geometry = _observation_end_geometry(SimpleNamespace(lines=line_objects), data)
    frame = pd.read_parquet(obs_path)
    frame["end_geometry"] = [json.dumps(geometry[rid], ensure_ascii=False) if rid in geometry else None
                             for rid in frame["record_id"]]
    frame.to_parquet(obs_path, index=False)


def main(argv: list[str]) -> int:
    src_dir, work_dir, mode = Path(argv[0]), Path(argv[1]), argv[2]
    pids = argv[3:] or DEFAULT_PIDS
    sys.path.insert(0, str(src_dir))
    from dwg_audit.report.rerun import rerun_audit_from_findings

    config = json.loads(MANIFEST.read_text(encoding="utf-8"))["config"]
    summary = {}
    for pid in pids:
        source_dirs = sorted(p for p in (CURRENT / pid).glob("*") if (p / "findings").is_dir())
        if not source_dirs:
            raise SystemExit(f"no baseline project directory for {pid}")
        source = source_dirs[0]
        target = work_dir / mode / pid / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("cache", "logs", "*.dxf", "*.DXF"))
        if mode == "new":
            backfill(target / "findings")
        rerun_audit_from_findings(target, config, None)
        issues = json.loads((target / "audit" / "issues.json").read_text(encoding="utf-8"))
        gaps = [i for i in issues if i.get("rule_id") == "R-RECOGNITION-GAP"]
        summary[pid] = {"issues": len(issues), "gap_issues": len(gaps),
                        "gap_presentation": sorted({(i.get("evidence") or {}).get("presentation") or "none" for i in gaps}),
                        "gate_stats": _gate_stats(target / "audit")}
        print(pid, summary[pid]["issues"], summary[pid]["gap_issues"], flush=True)
    (work_dir / f"{mode}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def _gate_stats(audit_dir: Path):
    path = audit_dir / "sw_recognition_gate.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
