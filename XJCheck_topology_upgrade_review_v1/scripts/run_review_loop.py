#!/usr/bin/env python3
"""Orchestrate the evidence loop: inventory -> baseline -> failures -> symbols."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--oda", type=Path, default=None)
    parser.add_argument("--python", dest="python_executable", default=sys.executable)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args()


def run(command: list[str], log_path: Path, continue_on_error: bool) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    log_path.write_text(completed.stdout, encoding="utf-8")
    print(" ".join(command))
    print(f"exit_code={completed.returncode}; log={log_path}")
    if completed.returncode != 0 and not continue_on_error:
        raise SystemExit(completed.returncode)
    return completed.returncode


def main() -> int:
    args = parse_args()
    scripts = Path(__file__).resolve().parent
    args.output.mkdir(parents=True, exist_ok=True)
    records = []

    inventory_command = [
        args.python_executable,
        str(scripts / "corpus_inventory.py"),
        "--repo",
        str(args.repo),
        "--data",
        str(args.data),
        "--output",
        str(args.output / "inventory"),
    ]
    if args.config:
        inventory_command += ["--config", str(args.config)]
    records.append({"stage": "inventory", "exit_code": run(inventory_command, args.output / "logs" / "inventory.log", args.continue_on_error)})

    baseline_command = [
        args.python_executable,
        str(scripts / "run_corpus_baseline.py"),
        "--repo",
        str(args.repo),
        "--data",
        str(args.data),
        "--output",
        str(args.output / "baseline"),
        "--python",
        args.python_executable,
        "--resume",
    ]
    if args.config:
        baseline_command += ["--config", str(args.config)]
    if args.oda:
        baseline_command += ["--oda", str(args.oda)]
    if args.limit > 0:
        baseline_command += ["--limit", str(args.limit)]
    records.append({"stage": "baseline", "exit_code": run(baseline_command, args.output / "logs" / "baseline.log", args.continue_on_error)})

    failure_command = [
        args.python_executable,
        str(scripts / "build_failure_queue.py"),
        "--baseline",
        str(args.output / "baseline"),
        "--output",
        str(args.output / "failure_queue"),
    ]
    records.append({"stage": "failure_queue", "exit_code": run(failure_command, args.output / "logs" / "failure_queue.log", args.continue_on_error)})

    symbol_command = [
        args.python_executable,
        str(scripts / "bootstrap_symbol_library.py"),
        "--baseline",
        str(args.output / "baseline"),
        "--output",
        str(args.output / "symbol_bootstrap"),
        "--top",
        "100",
    ]
    records.append({"stage": "symbol_bootstrap", "exit_code": run(symbol_command, args.output / "logs" / "symbol_bootstrap.log", args.continue_on_error)})

    (args.output / "review_loop.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if all(record["exit_code"] == 0 for record in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
