#!/usr/bin/env python3
"""Validate this review package before delivery."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED = [
    "README.md",
    "MASTER_TASKBOOK.md",
    "MIGRATION_CHECKLIST.md",
    "configs/topology_v2.example.yml",
    "configs/symbol_library.example.yml",
    "schemas/symbol_library.schema.json",
    "schemas/topology_findings.schema.json",
    "schemas/project_profile.schema.json",
    "schemas/issue_v2.schema.json",
    "pseudocode/01_pipeline.py",
    "pseudocode/02_geometry_graph.py",
    "pseudocode/03_symbol_port_binding.py",
    "pseudocode/04_constraint_resolver.py",
    "pseudocode/05_cross_page_audit.py",
    "scripts/run_corpus_baseline.py",
    "scripts/build_failure_queue.py",
    "scripts/bootstrap_symbol_library.py",
    "scripts/compare_engines.py",
    "sources/source_matrix.md",
    "reports/inventory_summary.json",
    "reports/project_inventory.csv",
    "reports/page_inventory.csv",
    "reports/contact_first.png",
    "reports/contact_second.png",
    "reports/contact_third_diverse.png",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    return parser.parse_args()


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def main() -> int:
    args = parse_args()
    root = args.package.resolve()
    checks: list[dict[str, Any]] = []

    for relative in REQUIRED:
        path = root / relative
        add_check(checks, f"required:{relative}", path.exists(), str(path))

    for path in sorted((root / "schemas").glob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
            add_check(checks, f"json:{path.name}", True, "valid JSON")
        except Exception as exc:
            add_check(checks, f"json:{path.name}", False, str(exc))

    for path in sorted((root / "configs").glob("*.yml")):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
            add_check(checks, f"yaml:{path.name}", True, "valid YAML")
        except Exception as exc:
            add_check(checks, f"yaml:{path.name}", False, str(exc))

    for directory in (root / "scripts", root / "pseudocode"):
        for path in sorted(directory.glob("*.py")):
            try:
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
                add_check(checks, f"python:{path.relative_to(root)}", True, "syntax valid")
            except Exception as exc:
                add_check(checks, f"python:{path.relative_to(root)}", False, str(exc))

    for path in sorted((root / "reports").glob("*.csv")):
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
            add_check(checks, f"csv:{path.name}", bool(header), f"columns={len(header or [])}")
        except Exception as exc:
            add_check(checks, f"csv:{path.name}", False, str(exc))

    for path in sorted((root / "reports").glob("*.png")):
        signature = path.read_bytes()[:8] if path.exists() else b""
        add_check(checks, f"png:{path.name}", signature == b"\x89PNG\r\n\x1a\n", f"bytes={path.stat().st_size if path.exists() else 0}")

    passed = all(check["passed"] for check in checks)
    payload = {
        "package": str(root),
        "passed": passed,
        "check_count": len(checks),
        "failed_count": sum(not check["passed"] for check in checks),
        "checks": checks,
    }
    (root / "VALIDATION_REPORT.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Package Validation", "", f"Overall: {'PASS' if passed else 'FAIL'}", ""]
    for check in checks:
        lines.append(f"- [{'x' if check['passed'] else ' '}] {check['name']}: {check['detail']}")
    (root / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("passed", "check_count", "failed_count")}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
