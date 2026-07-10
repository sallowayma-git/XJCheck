#!/usr/bin/env python3
"""Create a symbol review backlog from existing XJCheck findings.

The current findings do not preserve full block definitions, so this script is a
bootstrap only. It ranks block names by frequency, project spread and connection
impact, and emits machine-proposed YAML entries that require human verification.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--touch-radius", type=float, default=20.0)
    return parser.parse_args()


def find_project_dirs(root: Path) -> list[Path]:
    return sorted({path.parent for path in root.rglob("manifest.json")}, key=lambda path: str(path))


def read_table(project_dir: Path, name: str) -> pd.DataFrame:
    path = project_dir / "findings" / name
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def parse_attribute_tags(raw: Any) -> list[str]:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    if isinstance(raw, dict):
        return sorted(str(key) for key in raw)
    try:
        payload = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return []
    return sorted(str(key) for key in payload) if isinstance(payload, dict) else []


def nearby_endpoint_count(block_row: dict[str, Any], lines: pd.DataFrame, radius: float) -> int:
    if lines.empty:
        return 0
    x = float(block_row.get("insert_x", 0.0))
    y = float(block_row.get("insert_y", 0.0))
    same_sheet = lines[lines["sheet_id"] == block_row.get("sheet_id")]
    if same_sheet.empty:
        return 0
    count = 0
    r2 = radius * radius
    for row in same_sheet.to_dict("records"):
        for px, py in ((row.get("start_x"), row.get("start_y")), (row.get("end_x"), row.get("end_y"))):
            if px is None or py is None:
                continue
            if (float(px) - x) ** 2 + (float(py) - y) ** 2 <= r2:
                count += 1
    return count


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, Any]] = {}

    for project_dir in find_project_dirs(args.baseline):
        manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
        project_id = str(manifest.get("project_id"))
        blocks = read_table(project_dir, "blocks.parquet")
        lines = read_table(project_dir, "lines.parquet")
        if blocks.empty:
            continue
        for block in blocks.to_dict("records"):
            name = str(block.get("name") or "<anonymous>")
            record = records.setdefault(
                name,
                {
                    "block_name": name,
                    "instance_count": 0,
                    "projects": set(),
                    "sheets": set(),
                    "rotations": Counter(),
                    "attribute_tags": set(),
                    "nearby_endpoint_count": 0,
                    "instances_with_nearby_endpoints": 0,
                },
            )
            record["instance_count"] += 1
            record["projects"].add(project_id)
            record["sheets"].add(f"{project_id}:{block.get('sheet_id')}")
            record["rotations"][round(float(block.get("rotation_deg") or 0.0), 3)] += 1
            record["attribute_tags"].update(parse_attribute_tags(block.get("attributes_json")))
            touches = nearby_endpoint_count(block, lines, args.touch_radius)
            record["nearby_endpoint_count"] += touches
            if touches:
                record["instances_with_nearby_endpoints"] += 1

    rows = []
    for record in records.values():
        project_count = len(record["projects"])
        sheet_count = len(record["sheets"])
        impact = (
            math.log1p(record["instance_count"])
            * (1.0 + math.log1p(project_count))
            * (1.0 + record["instances_with_nearby_endpoints"] / max(record["instance_count"], 1))
        )
        rows.append(
            {
                "block_name": record["block_name"],
                "instance_count": record["instance_count"],
                "project_count": project_count,
                "sheet_count": sheet_count,
                "nearby_endpoint_count": record["nearby_endpoint_count"],
                "instances_with_nearby_endpoints": record["instances_with_nearby_endpoints"],
                "connection_impact_score": round(impact, 6),
                "rotations": json.dumps(record["rotations"], ensure_ascii=False, sort_keys=True),
                "attribute_tags": json.dumps(sorted(record["attribute_tags"]), ensure_ascii=False),
                "review_status": "unreviewed",
                "proposed_role": "unknown",
                "review_notes": "",
            }
        )
    rows.sort(key=lambda row: (-row["connection_impact_score"], -row["instance_count"], row["block_name"]))
    rows = rows[: args.top]

    fields = list(rows[0]) if rows else []
    with (args.output / "symbol_review_queue.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)

    families = []
    for row in rows:
        safe_id = "symbol_" + "".join(ch.lower() if ch.isalnum() else "_" for ch in row["block_name"]).strip("_")
        families.append(
            {
                "family_id": safe_id[:120] or "symbol_unknown",
                "display_name": row["block_name"],
                "aliases": [row["block_name"]],
                "recognition": {
                    "block_names": [row["block_name"]],
                    "block_name_regex": None,
                    "definition_hashes": [],
                    "geometry_fingerprint": {
                        "status": "missing_from_current_findings",
                        "bootstrap_instance_count": row["instance_count"],
                        "bootstrap_project_count": row["project_count"],
                    },
                },
                "role": "unknown",
                "electrical_behavior": "unknown",
                "ports": [],
                "internal_connections": [],
                "text_slots": [],
                "transforms": {
                    "allow_rotation": True,
                    "allow_mirror": True,
                    "allow_nonuniform_scale": False,
                },
                "verification": {
                    "status": "machine_proposed",
                    "source": "bootstrap_symbol_library.py",
                    "verified_instance_count": 0,
                    "reviewer": None,
                    "notes": "Resolve block definition fingerprint, ports and internal connectivity before enabling automatic audit.",
                },
            }
        )
    payload = {
        "schema_version": "1.0.0",
        "library_version": "0.1.0-bootstrap",
        "families": families,
    }
    (args.output / "machine_proposed_symbol_library.yml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    summary = {
        "unique_block_name_count": len(records),
        "review_queue_count": len(rows),
        "warning": "Current findings lack full block definitions and verified local port coordinates.",
    }
    (args.output / "symbol_bootstrap_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
