#!/usr/bin/env python3
"""Inventory a DWG corpus with XJCheck's current scanner and sidecar parser.

This script does not require DWG conversion. It is intended to run before the
entity-level baseline so that project boundaries, page order, route targets and
sidecar semantics are frozen independently from the recognition engine.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True, help="XJCheck repository root")
    parser.add_argument("--data", type=Path, required=True, help="Corpus root")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--config", type=Path, default=None, help="Optional current XJCheck YAML config")
    return parser.parse_args()


def add_repo_to_path(repo: Path) -> None:
    source = repo.resolve() / "src"
    if not source.exists():
        raise FileNotFoundError(f"Repository source directory not found: {source}")
    sys.path.insert(0, str(source))


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def top_level_group(data_root: Path, project_root: Path) -> str:
    relative = project_root.resolve().relative_to(data_root.resolve())
    return relative.parts[0] if relative.parts else project_root.name


def main() -> int:
    args = parse_args()
    add_repo_to_path(args.repo)

    from dwg_audit.ingest.project_scanner import discover_project_roots, scan_project
    from dwg_audit.ingest.sidecar_parser import extract_device_name, parse_prj, parse_terminal_xml
    from dwg_audit.utils.config import load_config

    config_path = args.config or args.repo / "configs" / "default.yml"
    config = load_config(config_path)
    roots = sorted(discover_project_roots(args.data), key=lambda path: str(path))

    project_rows: list[dict[str, Any]] = []
    page_rows: list[dict[str, Any]] = []
    terminal_rows: list[dict[str, Any]] = []
    sidecar_mismatches: list[dict[str, Any]] = []

    for project_index, root in enumerate(roots, start=1):
        scan = scan_project(root, config=config)
        group = top_level_group(args.data, root)
        prj_path = next(root.glob("*.prj"), None)
        prj_entries = []
        prj_encoding = None
        prj_warnings: list[str] = []
        if prj_path:
            prj_entries, _notes, prj_encoding, prj_warnings = parse_prj(prj_path)

        terminal_path = root / "LdDzbInfo.xml"
        strips = parse_terminal_xml(terminal_path) if terminal_path.exists() else []
        device_name = extract_device_name(terminal_path) if terminal_path.exists() else None

        actual_names = {path.name for path in root.glob("*.dwg")}
        prj_names = {entry.filename for entry in prj_entries}
        if prj_entries and actual_names != prj_names:
            sidecar_mismatches.append(
                {
                    "project_root": str(root),
                    "missing_from_disk": sorted(prj_names - actual_names),
                    "missing_from_prj": sorted(actual_names - prj_names),
                }
            )

        page_number_counts = Counter(page.sheet_no for page in scan.pages if page.sheet_no)
        project_rows.append(
            {
                "project_index": project_index,
                "group": group,
                "project_root": str(root.resolve()),
                "project_id": scan.manifest.project_id,
                "project_name": scan.manifest.project_name,
                "device_name": device_name or "",
                "dwg_count": scan.manifest.file_count,
                "valid_dwg_count": scan.manifest.valid_dwg_files,
                "invalid_dwg_count": scan.manifest.invalid_dwg_files,
                "prj_present": prj_path is not None,
                "prj_encoding": prj_encoding or "",
                "prj_warning_count": len(prj_warnings),
                "terminal_xml_present": terminal_path.exists(),
                "terminal_strip_count": len(strips),
                "duplicate_page_numbers": json_text(sorted(k for k, v in page_number_counts.items() if v > 1)),
                "route_counts": json_text(Counter(page.route_target or "None" for page in scan.pages)),
                "category_counts": json_text(Counter(page.sheet_category or "None" for page in scan.pages)),
                "audit_role_counts": json_text(Counter(page.audit_role for page in scan.pages)),
            }
        )

        for page in scan.pages:
            page_rows.append(
                {
                    "project_index": project_index,
                    "group": group,
                    "project_id": scan.manifest.project_id,
                    "project_root": str(root.resolve()),
                    "sheet_id": page.sheet_id,
                    "sheet_order": page.sheet_order,
                    "sheet_no": page.sheet_no or "",
                    "filename": page.filename,
                    "sheet_title": page.sheet_title,
                    "sheet_category": page.sheet_category or "",
                    "audit_role": page.audit_role,
                    "route_target": page.route_target or "",
                    "page_type_confidence": page.page_type_confidence,
                    "skip_reason": next((source.skip_reason for source in scan.manifest.source_files if source.file_id == page.file_id), None) or "",
                }
            )

        for strip in strips:
            terminal_rows.append(
                {
                    "project_index": project_index,
                    "group": group,
                    "project_id": scan.manifest.project_id,
                    "project_root": str(root.resolve()),
                    "device_name": device_name or "",
                    "name": strip.name,
                    "side": strip.style,
                    "length": strip.length,
                }
            )

    group_counts = Counter(row["group"] for row in project_rows)
    domain_shift_group = max(group_counts, key=group_counts.get) if group_counts else None
    reference_titles = {
        row["sheet_title"]
        for row in page_rows
        if row["group"] != domain_shift_group
    }
    unseen_rows = [
        row for row in page_rows
        if row["group"] == domain_shift_group and row["sheet_title"] not in reference_titles
    ]

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "project_inventory.csv", project_rows)
    write_csv(args.output / "page_inventory.csv", page_rows)
    write_csv(args.output / "terminal_strip_inventory.csv", terminal_rows)
    write_csv(args.output / "domain_shift_unseen_titles.csv", unseen_rows)
    (args.output / "sidecar_mismatch.json").write_text(
        json.dumps(sidecar_mismatches, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = {
        "project_count": len(project_rows),
        "dwg_count": sum(int(row["dwg_count"]) for row in project_rows),
        "valid_dwg_count": sum(int(row["valid_dwg_count"]) for row in project_rows),
        "terminal_strip_count": len(terminal_rows),
        "group_project_counts": dict(group_counts),
        "domain_shift_group": domain_shift_group,
        "domain_shift_unseen_page_count": len(unseen_rows),
        "sidecar_mismatch_count": len(sidecar_mismatches),
    }
    (args.output / "inventory_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
