#!/usr/bin/env python3
"""Run the current XJCheck head project-by-project over a DWG corpus.

The runner intentionally isolates each project so one conversion crash cannot hide
other projects. It writes an effective config, full logs and a machine-readable
summary. Run it from the Python environment where XJCheck and ODA are available.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--oda", type=Path, default=None, help="ODA File Converter executable or AppImage")
    parser.add_argument("--python", dest="python_executable", default=sys.executable)
    parser.add_argument("--only", default="", help="Regex applied to project path")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--skip-audit", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def add_repo_to_path(repo: Path) -> None:
    sys.path.insert(0, str((repo / "src").resolve()))


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return cleaned[:80] or "project"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def prepare_config(args: argparse.Namespace) -> Path:
    import yaml

    source = args.config or args.repo / "configs" / "default.yml"
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    payload.setdefault("ingest", {})
    if args.oda:
        payload["ingest"]["odafc_path"] = str(args.oda.resolve())
    target = args.output / "effective_config.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target


def run_command(command: list[str], cwd: Path, env: dict[str, str], log_path: Path, timeout: int) -> tuple[int, float, str]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        output = completed.stdout
        return completed.returncode, time.perf_counter() - started, output
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\nTIMEOUT\n"
        return 124, time.perf_counter() - started, output
    finally:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if "output" in locals():
            log_path.write_text(output, encoding="utf-8")


def find_project_output(run_dir: Path) -> Path | None:
    candidates = sorted(path.parent for path in run_dir.rglob("manifest.json"))
    return candidates[0] if candidates else None


def table_count(project_dir: Path, filename: str) -> int | None:
    try:
        import pandas as pd
    except ImportError:
        return None
    path = project_dir / "findings" / filename
    if not path.exists():
        return None
    return int(len(pd.read_parquet(path)))


def issue_count(project_dir: Path) -> int | None:
    candidates = list(project_dir.rglob("issues.json"))
    if not candidates:
        return None
    payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("issues", "items", "records"):
            if isinstance(payload.get(key), list):
                return len(payload[key])
    return None


def summarize_project(project_dir: Path) -> dict[str, Any]:
    manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    statuses = Counter(item.get("conversion_status", "unknown") for item in manifest.get("source_files", []))
    return {
        "project_id": manifest.get("project_id"),
        "project_name": manifest.get("project_name"),
        "sheet_count": manifest.get("sheet_count"),
        "file_count": manifest.get("file_count"),
        "conversion_status_counts": json.dumps(statuses, ensure_ascii=False, sort_keys=True),
        "conversion_failed_count": sum(
            count for status, count in statuses.items() if status not in {"converted", "cached", "skipped"}
        ),
        "text_count": table_count(project_dir, "texts.parquet"),
        "line_count": table_count(project_dir, "lines.parquet"),
        "block_count": table_count(project_dir, "blocks.parquet"),
        "line_group_count": table_count(project_dir, "line_groups.parquet"),
        "terminal_candidate_count": table_count(project_dir, "terminal_candidates.parquet"),
        "pair_candidate_count": table_count(project_dir, "pair_candidates.parquet"),
        "pair_count": table_count(project_dir, "pairs.parquet"),
        "wire_junction_count": table_count(project_dir, "wire_junctions.parquet"),
        "wire_network_count": table_count(project_dir, "wire_networks.parquet"),
        "issue_count": issue_count(project_dir),
        "project_output": str(project_dir.resolve()),
    }


def main() -> int:
    args = parse_args()
    args.repo = args.repo.resolve()
    args.data = args.data.resolve()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    add_repo_to_path(args.repo)

    from dwg_audit.ingest.project_scanner import discover_project_roots

    roots = sorted(discover_project_roots(args.data), key=lambda path: str(path))
    if args.only:
        pattern = re.compile(args.only)
        roots = [root for root in roots if pattern.search(str(root))]
    if args.limit > 0:
        roots = roots[: args.limit]

    effective_config = prepare_config(args)
    env = os.environ.copy()
    repo_pythonpath = os.pathsep.join([str(args.repo / "src"), str(args.repo)])
    env["PYTHONPATH"] = repo_pythonpath + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if args.oda:
        env["ODA_FILE_CONVERTER"] = str(args.oda.resolve())
        env["PATH"] = str(args.oda.resolve().parent) + os.pathsep + env.get("PATH", "")

    rows: list[dict[str, Any]] = []
    for index, root in enumerate(roots, start=1):
        run_dir = args.output / "project_runs" / f"P{index:03d}_{slug(root.name)}"
        marker = run_dir / "run_record.json"
        if args.resume and marker.exists():
            rows.append(json.loads(marker.read_text(encoding="utf-8")))
            continue

        run_dir.mkdir(parents=True, exist_ok=True)
        analyze_command = [
            args.python_executable,
            "-m",
            "dwg_audit.cli",
            "analyze-project",
            "--input",
            str(root),
            "--output",
            str(run_dir),
            "--config",
            str(effective_config),
        ]
        analyze_code, analyze_seconds, _ = run_command(
            analyze_command, args.repo, env, run_dir / "analyze.log", args.timeout
        )
        project_dir = find_project_output(run_dir)
        record: dict[str, Any] = {
            "project_index": index,
            "source_root": str(root),
            "analyze_exit_code": analyze_code,
            "analyze_seconds": round(analyze_seconds, 3),
            "audit_exit_code": None,
            "audit_seconds": None,
        }

        if project_dir is not None:
            record.update(summarize_project(project_dir))
            if not args.skip_audit and analyze_code == 0:
                audit_command = [
                    args.python_executable,
                    "-m",
                    "dwg_audit.cli",
                    "run-audit",
                    "--findings",
                    str(project_dir / "findings"),
                    "--output",
                    str(project_dir / "audit"),
                    "--config",
                    str(effective_config),
                ]
                audit_code, audit_seconds, _ = run_command(
                    audit_command, args.repo, env, run_dir / "audit.log", args.timeout
                )
                record["audit_exit_code"] = audit_code
                record["audit_seconds"] = round(audit_seconds, 3)
                record["issue_count"] = issue_count(project_dir)
        else:
            record["project_output"] = None
            record["error"] = "No manifest.json was produced"

        marker.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append(record)
        write_csv(args.output / "run_summary.csv", rows)
        (args.output / "run_summary.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(record, ensure_ascii=False))

    aggregate = {
        "project_count": len(rows),
        "analyze_success_count": sum(row.get("analyze_exit_code") == 0 for row in rows),
        "audit_success_count": sum(row.get("audit_exit_code") == 0 for row in rows),
        "projects_with_conversion_failures": sum((row.get("conversion_failed_count") or 0) > 0 for row in rows),
        "total_pairs": sum((row.get("pair_count") or 0) for row in rows),
        "total_issues": sum((row.get("issue_count") or 0) for row in rows),
    }
    (args.output / "aggregate_summary.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0 if aggregate["analyze_success_count"] == len(rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
