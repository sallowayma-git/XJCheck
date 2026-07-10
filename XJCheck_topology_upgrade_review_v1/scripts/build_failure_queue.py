#!/usr/bin/env python3
"""Build a page-level failure queue from current XJCheck artifacts.

This script does not decide how to fix a page. It creates reproducible review
slices for Reader, Geometry, Symbol, Semantic, Topology and Cross-page work.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline output root")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_table(project_dir: Path, name: str) -> pd.DataFrame:
    path = project_dir / "findings" / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def count_by_sheet(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty or "sheet_id" not in frame.columns:
        return {}
    return frame.groupby("sheet_id").size().astype(int).to_dict()


def numeric_count_by_sheet(texts: pd.DataFrame) -> dict[str, int]:
    if texts.empty or "sheet_id" not in texts.columns:
        return {}
    if "is_numeric_candidate" in texts.columns:
        selected = texts[texts["is_numeric_candidate"].fillna(False)]
    else:
        column = "normalized_text" if "normalized_text" in texts.columns else "text"
        selected = texts[texts[column].fillna("").astype(str).str.fullmatch(r"[0-9]+")]
    return selected.groupby("sheet_id").size().astype(int).to_dict()


def find_project_dirs(root: Path) -> list[Path]:
    return sorted({path.parent for path in root.rglob("manifest.json")}, key=lambda path: str(path))


def append_failure(rows: list[dict[str, Any]], base: dict[str, Any], family: str, severity: str, reason: str, score: float) -> None:
    rows.append(
        {
            **base,
            "failure_id": f"FQ{len(rows) + 1:06d}",
            "failure_family": family,
            "severity": severity,
            "risk_score": round(score, 4),
            "reason": reason,
            "status": "open",
            "review_label": "",
            "reviewer": "",
            "recommended_review": recommendation_for(family),
        }
    )


def recommendation_for(family: str) -> str:
    mapping = {
        "reader": "Check ODA path, conversion log, DWG validity and entity completeness before any audit conclusion.",
        "page_routing": "Review page capability labels; do not add a filename-only extractor branch.",
        "geometry": "Inspect primitive segments, intersections, open endpoints and possible topology decisions.",
        "symbol": "Add the high-impact block to the symbol backlog and verify ports/internal connectivity.",
        "semantic": "Review numeric text roles and top-k text-to-endpoint/port candidates.",
        "topology": "Inspect over-merge, split, possible bridge and network witness paths.",
        "cross_page": "Inspect endpoint identity scope and competing reciprocal matches across sheets.",
    }
    return mapping.get(family, "Review the evidence and assign a reusable failure label.")


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for project_dir in find_project_dirs(args.baseline):
        manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
        pages = read_table(project_dir, "pages.parquet")
        sources = read_table(project_dir, "source_files.parquet")
        texts = read_table(project_dir, "texts.parquet")
        lines = read_table(project_dir, "lines.parquet")
        blocks = read_table(project_dir, "blocks.parquet")
        line_groups = read_table(project_dir, "line_groups.parquet")
        terminal_candidates = read_table(project_dir, "terminal_candidates.parquet")
        pairs = read_table(project_dir, "pairs.parquet")
        networks = read_table(project_dir, "wire_networks.parquet")
        coverage = read_table(project_dir, "entity_coverage_summary.parquet")

        counts = {
            "text": count_by_sheet(texts),
            "numeric": numeric_count_by_sheet(texts),
            "line": count_by_sheet(lines),
            "block": count_by_sheet(blocks),
            "line_group": count_by_sheet(line_groups),
            "terminal_candidate": count_by_sheet(terminal_candidates),
            "pair": count_by_sheet(pairs),
            "network": count_by_sheet(networks),
        }
        source_by_file = sources.set_index("file_id").to_dict("index") if not sources.empty else {}
        coverage_by_sheet = coverage.set_index("sheet_id").to_dict("index") if not coverage.empty and "sheet_id" in coverage.columns else {}

        for page in pages.to_dict("records"):
            sheet_id = page.get("sheet_id")
            source = source_by_file.get(page.get("file_id"), {})
            base = {
                "project_id": manifest.get("project_id"),
                "project_dir": str(project_dir),
                "sheet_id": sheet_id,
                "sheet_order": page.get("sheet_order"),
                "sheet_no": page.get("sheet_no"),
                "filename": page.get("filename"),
                "sheet_title": page.get("sheet_title"),
                "sheet_category": page.get("sheet_category"),
                "audit_role": page.get("audit_role"),
                "route_target": page.get("route_target"),
                "page_type": page.get("page_type"),
                "page_type_confidence": page.get("page_type_confidence"),
                "conversion_status": source.get("conversion_status", "unknown"),
                "text_count": counts["text"].get(sheet_id, 0),
                "numeric_text_count": counts["numeric"].get(sheet_id, 0),
                "line_count": counts["line"].get(sheet_id, 0),
                "block_count": counts["block"].get(sheet_id, 0),
                "line_group_count": counts["line_group"].get(sheet_id, 0),
                "terminal_candidate_count": counts["terminal_candidate"].get(sheet_id, 0),
                "pair_count": counts["pair"].get(sheet_id, 0),
                "network_count": counts["network"].get(sheet_id, 0),
            }
            audit_required = page.get("audit_role") in {"primary", "supplemental"}
            entity_count = base["text_count"] + base["line_count"] + base["block_count"]

            if source.get("conversion_status") not in {"converted", "cached", "skipped"}:
                append_failure(rows, base, "reader", "critical", f"Conversion status is {source.get('conversion_status')}", 1.0)
            elif audit_required and entity_count == 0:
                append_failure(rows, base, "reader", "critical", "Audit-required page has zero extracted entities", 1.0)

            title = str(page.get("sheet_title") or "")
            route = str(page.get("route_target") or "")
            if "backplate" in str(page.get("page_type") or "").lower() or "LayoutOnly" in route or "Backplate" in route:
                if audit_required or "back" in title.lower():
                    append_failure(rows, base, "page_routing", "major", "Backplate-like page may be classify-only or under-audited", 0.90)
            if not route or route == "None" or float(page.get("page_type_confidence") or 0.0) < 0.60:
                append_failure(rows, base, "page_routing", "major", "Unknown or low-confidence page route", 0.85)

            if audit_required and base["line_count"] > 0 and base["network_count"] == 0:
                append_failure(rows, base, "topology", "major", "Lines were extracted but no wire network was materialized", 0.95)
            if audit_required and base["numeric_text_count"] > 0 and base["terminal_candidate_count"] == 0:
                append_failure(rows, base, "semantic", "major", "Numeric texts exist but no terminal candidates were generated", 0.90)
            if audit_required and base["line_group_count"] > 0 and base["pair_count"] == 0:
                append_failure(rows, base, "semantic", "major", "Candidate line groups exist but no pair was selected", 0.88)

            coverage_row = coverage_by_sheet.get(sheet_id, {})
            ratio = coverage_row.get("coverage_ratio")
            if ratio is not None and pd.notna(ratio) and float(ratio) < 0.65:
                append_failure(rows, base, "semantic", "review", f"Low entity assignment coverage: {float(ratio):.3f}", 0.75)
            unexplained_numeric = coverage_row.get("unexplained_numeric_texts")
            if unexplained_numeric is not None and pd.notna(unexplained_numeric) and int(unexplained_numeric) >= 3:
                append_failure(rows, base, "semantic", "review", f"Unexplained numeric texts: {int(unexplained_numeric)}", 0.80)

    fields = sorted({key for row in rows for key in row}) if rows else []
    with (args.output / "failure_queue.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if fields:
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda row: (-row["risk_score"], row["project_id"], row["sheet_order"] or 0)))

    summary = {
        "failure_count": len(rows),
        "failure_family_counts": dict(Counter(row["failure_family"] for row in rows)),
        "severity_counts": dict(Counter(row["severity"] for row in rows)),
        "project_count": len({row["project_id"] for row in rows}),
    }
    (args.output / "failure_queue_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
