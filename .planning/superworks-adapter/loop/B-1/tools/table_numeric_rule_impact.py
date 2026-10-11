"""B-1 FIX v2 impact: which numeric three-column rows does the "at most one numeral per cell" rule remove?

Read-only. Input: per-sheet pickles written by the DEBUG-only dump hook in a snapshot copy of
table_extractor.extract_table_pairs (never in the repo). Each pickle holds the raw arguments of
the sheet: sheet record, texts (before the invisible-text filter), lines and polylines.

For every sheet whose global grid has exactly three cell columns, this script:
  1. applies the invisible-text filter (as the fix does),
  2. reproduces the pre-rule numeric three-column rows (OLD = fix v1 logic),
  3. runs the current `_build_three_column_mappings` (NEW = with the rule),
  4. reports rows removed by the rule with each cell's numeral count and text sample.

Usage: python table_numeric_rule_impact.py <dump_root> [<dump_root> ...]
Writes JSON to .tmp/loop_invis2_impact/table_numeric_rule_impact.json.
"""
from __future__ import annotations

import glob
import json
import pickle
import sys
from pathlib import Path

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))

from dwg_audit.audit.table_extractor import (  # noqa: E402
    _assign_texts_to_cells,
    _build_cells,
    _build_header_semantic_mappings,
    _build_three_column_mappings,
    _detect_table_grid,
    _looks_like_numeric_value,
    _numeric_cell_text,
)
from dwg_audit.domain.models import is_invisible_text  # noqa: E402

OUT = ROOT / ".tmp" / "loop_invis2_impact"


def old_rows(cell_values, rows):
    """Pre-rule numeric three-column rows (identical to the fix v1 loop body)."""
    out = []
    for row_index in range(len(rows) - 1):
        left = _numeric_cell_text(cell_values.get((row_index, 0), []))
        mid = _numeric_cell_text(cell_values.get((row_index, 1), []))
        right = _numeric_cell_text(cell_values.get((row_index, 2), []))
        if mid is None or not _looks_like_numeric_value(mid.normalized_text):
            continue
        if left is None and right is None:
            continue
        out.append((row_index, mid, left, right))
    return out


def numeral_count(items):
    return sum(1 for t in items if _looks_like_numeric_value(t.normalized_text))


def main(argv: list[str]) -> None:
    roots = argv or [str(ROOT / ".tmp/loop_invis_dbg")]
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for root in roots:
        files += sorted(glob.glob(str(Path(root) / "*" / "table_dump" / "*.pkl")))
    report = {"sheets_scanned": 0, "sheets_three_column": 0, "old_rows": 0, "new_rows": 0, "removed": []}
    for path in files:
        with open(path, "rb") as fh:
            payload = pickle.load(fh)
        sheet = payload["sheet"]
        report["sheets_scanned"] += 1
        texts = [t for t in payload["texts"] if not is_invisible_text(t)]
        grid = _detect_table_grid(payload["lines"], payload["polylines"], sheet)
        if grid is None:
            continue
        rows, cols = grid
        if len(cols) - 1 != 3:
            continue
        report["sheets_three_column"] += 1
        cells = _build_cells(rows, cols)
        cell_values = _assign_texts_to_cells(texts, cells, sheet)
        if _build_header_semantic_mappings(cell_values, rows, sheet):
            continue  # header branch wins; numeric branch not reached (unchanged by the rule)
        old = old_rows(cell_values, rows)
        new_row_ids = {m["row_index"] for m in _build_three_column_mappings(cell_values, cols, rows, sheet)}
        report["old_rows"] += len(old)
        report["new_rows"] += len(new_row_ids)
        for row_index, mid, left, right in old:
            if row_index in new_row_ids:
                continue
            cell_info = {}
            for col, label in ((0, "left"), (1, "middle"), (2, "right")):
                items = cell_values.get((row_index, col), [])
                cell_info[label] = {
                    "numerals": numeral_count(items),
                    "texts": len(items),
                    "sample": [t.normalized_text for t in sorted(items, key=lambda t: (t.insert_y, t.insert_x))[:12]],
                }
            report["removed"].append({
                "project": Path(path).parts[-3],
                "sheet_id": sheet.sheet_id,
                "filename": sheet.filename,
                "row_index": row_index,
                "row_band_y": [round(rows[row_index], 2), round(rows[row_index + 1], 2)],
                "col_x": [round(c, 2) for c in cols],
                "middle": {"text_id": mid.text_id, "value": mid.normalized_text, "xy": [round(mid.insert_x, 2), round(mid.insert_y, 2)]},
                "right": None if right is None else {"text_id": right.text_id, "value": right.normalized_text, "xy": [round(right.insert_x, 2), round(right.insert_y, 2)]},
                "left": None if left is None else {"text_id": left.text_id, "value": left.normalized_text, "xy": [round(left.insert_x, 2), round(left.insert_y, 2)]},
                "cells": cell_info,
            })
    report["removed_count"] = len(report["removed"])
    (OUT / "table_numeric_rule_impact.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "removed"}, ensure_ascii=False, indent=2))
    for item in report["removed"]:
        print(item["project"], item["sheet_id"], "row", item["row_index"],
              "M", item["middle"]["value"], "R", item["right"] and item["right"]["value"],
              "numerals M/R", item["cells"]["middle"]["numerals"], item["cells"]["right"]["numerals"])


if __name__ == "__main__":
    main(sys.argv[1:])
