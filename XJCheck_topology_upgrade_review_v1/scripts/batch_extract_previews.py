#!/usr/bin/env python3
"""Batch extract DWG embedded previews and create a manifest."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from extract_dwg_preview import extract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = sorted(args.data.rglob("*.dwg"), key=lambda path: str(path))
    if args.limit > 0:
        files = files[: args.limit]
    rows = []
    failures = []
    for index, source in enumerate(files, start=1):
        relative = source.relative_to(args.data)
        target = args.output / relative.with_suffix(".bmp")
        try:
            result = extract(source, target)
            rows.append({"index": index, "relative_path": str(relative), **result})
        except Exception as exc:
            failures.append({"relative_path": str(relative), "error": str(exc)})

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "preview_inventory.csv"
    fields = sorted({key for row in rows for key in row}) if rows else []
    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)
    summary = {
        "input_count": len(files),
        "success_count": len(rows),
        "failure_count": len(failures),
        "failures": failures,
        "warning": "Embedded previews are visual QC only and are not CAD entity truth.",
    }
    (args.output / "preview_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
