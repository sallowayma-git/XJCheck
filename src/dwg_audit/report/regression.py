from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.report.artifacts import load_report_frames


FrameMap = Mapping[str, pd.DataFrame]


def summarize_regression_metrics(frames: FrameMap) -> dict[str, Any]:
    """Build lightweight regression metrics from persisted findings/audit frames."""
    pages = _frame(frames, "pages")
    texts = _frame(frames, "texts")
    lines = _frame(frames, "lines")
    line_groups = _frame(frames, "line_groups")
    pairs = _frame(frames, "pairs")
    issues = _frame(frames, "issues")

    return {
        "pair_count": int(len(pairs)),
        "issue_count": int(len(issues)),
        "rule_counts": _value_counts(issues, "rule_id"),
        "status_counts": {
            "pairs": _value_counts(pairs, "status"),
            "issues": _value_counts(issues, "status"),
        },
        "extraction_counts": {
            "pages": int(len(pages)),
            "texts": int(len(texts)),
            "numeric_texts": _truthy_count(texts, "is_numeric_candidate"),
            "lines": int(len(lines)),
            "line_groups": int(len(line_groups)),
        },
        "precision": None,
        "recall": None,
        "precision_recall_status": "not_computed",
    }


def compare_regression_metrics(baseline_frames: FrameMap, current_frames: FrameMap) -> dict[str, Any]:
    """Compare two findings/audit frame snapshots without requiring source DWG files."""
    baseline = summarize_regression_metrics(baseline_frames)
    current = summarize_regression_metrics(current_frames)
    baseline_pages = _frame(baseline_frames, "pages")
    current_pages = _frame(current_frames, "pages")

    return {
        "baseline": baseline,
        "current": current,
        "delta": {
            "pair_count": current["pair_count"] - baseline["pair_count"],
            "issue_count": current["issue_count"] - baseline["issue_count"],
            "rule_counts": _counter_delta(baseline["rule_counts"], current["rule_counts"]),
            "status_counts": {
                "pairs": _counter_delta(baseline["status_counts"]["pairs"], current["status_counts"]["pairs"]),
                "issues": _counter_delta(baseline["status_counts"]["issues"], current["status_counts"]["issues"]),
            },
            "extraction_counts": {
                key: int(current["extraction_counts"].get(key, 0)) - int(baseline["extraction_counts"].get(key, 0))
                for key in sorted(set(baseline["extraction_counts"]) | set(current["extraction_counts"]))
            },
        },
        "non_regression_checks": {
            "texts": _non_regression_check(
                _frame(baseline_frames, "texts"),
                _frame(current_frames, "texts"),
                baseline_pages,
                current_pages,
            ),
            "lines": _non_regression_check(
                _frame(baseline_frames, "lines"),
                _frame(current_frames, "lines"),
                baseline_pages,
                current_pages,
            ),
        },
        "precision": None,
        "recall": None,
        "precision_recall_status": "not_computed",
    }


def compare_project_regressions(baseline_project_dir: Path, current_project_dir: Path) -> dict[str, Any]:
    baseline_manifest = json.loads((baseline_project_dir / "manifest.json").read_text(encoding="utf-8"))
    current_manifest = json.loads((current_project_dir / "manifest.json").read_text(encoding="utf-8"))
    comparison = compare_regression_metrics(
        load_report_frames(baseline_project_dir),
        load_report_frames(current_project_dir),
    )
    comparison["baseline_project"] = {
        "project_name": baseline_manifest.get("project_name"),
        "project_id": baseline_manifest.get("project_id"),
        "path": str(baseline_project_dir.resolve()),
    }
    comparison["current_project"] = {
        "project_name": current_manifest.get("project_name"),
        "project_id": current_manifest.get("project_id"),
        "path": str(current_project_dir.resolve()),
    }
    return comparison


def write_regression_report(
    baseline_project_dir: Path,
    current_project_dir: Path,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison = compare_project_regressions(baseline_project_dir, current_project_dir)
    (output_dir / "regression_report.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "regression_report.md").write_text(
        _format_regression_markdown(comparison),
        encoding="utf-8",
    )
    return output_dir


def _format_regression_markdown(comparison: dict[str, Any]) -> str:
    baseline_project = comparison.get("baseline_project", {})
    current_project = comparison.get("current_project", {})
    baseline = comparison.get("baseline", {})
    current = comparison.get("current", {})
    delta = comparison.get("delta", {})

    lines = [
        "# Regression Report",
        "",
        f"Baseline: {baseline_project.get('project_name')} (`{baseline_project.get('path')}`)",
        f"Current: {current_project.get('project_name')} (`{current_project.get('path')}`)",
        "",
        "## Summary",
        "",
        f"- Baseline pair_count: `{baseline.get('pair_count', 0)}`",
        f"- Current pair_count: `{current.get('pair_count', 0)}`",
        f"- Delta pair_count: `{delta.get('pair_count', 0)}`",
        f"- Baseline issue_count: `{baseline.get('issue_count', 0)}`",
        f"- Current issue_count: `{current.get('issue_count', 0)}`",
        f"- Delta issue_count: `{delta.get('issue_count', 0)}`",
        "",
        "## Extraction Delta",
        "",
        f"- Baseline texts: `{baseline.get('extraction_counts', {}).get('texts', 0)}`",
        f"- Current texts: `{current.get('extraction_counts', {}).get('texts', 0)}`",
        f"- Delta texts: `{delta.get('extraction_counts', {}).get('texts', 0)}`",
        f"- Baseline lines: `{baseline.get('extraction_counts', {}).get('lines', 0)}`",
        f"- Current lines: `{current.get('extraction_counts', {}).get('lines', 0)}`",
        f"- Delta lines: `{delta.get('extraction_counts', {}).get('lines', 0)}`",
        f"- Delta line_groups: `{delta.get('extraction_counts', {}).get('line_groups', 0)}`",
        f"- Delta numeric_texts: `{delta.get('extraction_counts', {}).get('numeric_texts', 0)}`",
        "",
        "## Non-Regression Checks",
        "",
    ]

    for label, key in (("Texts", "texts"), ("Lines", "lines")):
        check = comparison.get("non_regression_checks", {}).get(key, {})
        drops = check.get("dropped_sheets", [])
        lines.append(
            f"- {label}: status=`{check.get('status')}` total_delta=`{check.get('total_delta')}` dropped_sheets=`{len(drops)}`"
        )
        if drops:
            preview = ", ".join(
                f"{item['page_key']}:{item['baseline']}->{item['current']}" for item in drops[:5]
            )
            lines.append(f"  - Drops: {preview}")

    lines.extend(["", "## Rule Delta", ""])

    rule_counts = delta.get("rule_counts", {})
    if rule_counts:
        for rule_id, diff in rule_counts.items():
            lines.append(f"- `{rule_id}`: `{diff}`")
    else:
        lines.append("- No rule deltas.")

    lines.extend(["", "## Status Delta", ""])
    pair_status = delta.get("status_counts", {}).get("pairs", {})
    issue_status = delta.get("status_counts", {}).get("issues", {})
    lines.append(f"- Pair statuses: `{json.dumps(pair_status, ensure_ascii=False, sort_keys=True)}`")
    lines.append(f"- Issue statuses: `{json.dumps(issue_status, ensure_ascii=False, sort_keys=True)}`")
    return "\n".join(lines) + "\n"


def _frame(frames: FrameMap, name: str) -> pd.DataFrame:
    frame = frames.get(name)
    return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()


def _value_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty or column not in frame.columns:
        return {}
    counts = frame[column].dropna().astype(str).value_counts().sort_index()
    return {str(key): int(value) for key, value in counts.items()}


def _truthy_count(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    values = frame[column].fillna(False)
    return int(values.astype(bool).sum())


def _counter_delta(baseline: Mapping[str, int], current: Mapping[str, int]) -> dict[str, int]:
    keys = sorted(set(baseline) | set(current))
    return {key: int(current.get(key, 0)) - int(baseline.get(key, 0)) for key in keys}


def _non_regression_check(
    baseline_frame: pd.DataFrame,
    current_frame: pd.DataFrame,
    baseline_pages: pd.DataFrame,
    current_pages: pd.DataFrame,
) -> dict[str, Any]:
    baseline_page_index = _page_index(baseline_pages)
    current_page_index = _page_index(current_pages)
    baseline_page_meta = _page_meta_by_key(baseline_pages)
    current_page_meta = _page_meta_by_key(current_pages)
    baseline_sheet_counts = _page_counts(baseline_frame, baseline_page_index)
    current_sheet_counts = _page_counts(current_frame, current_page_index)
    dropped_sheets = []
    for page_key in sorted(set(baseline_sheet_counts) | set(current_sheet_counts)):
        baseline_value = int(baseline_sheet_counts.get(page_key, 0))
        current_value = int(current_sheet_counts.get(page_key, 0))
        if current_value < baseline_value:
            baseline_meta = baseline_page_meta.get(page_key, {})
            current_meta = current_page_meta.get(page_key, {})
            dropped_sheets.append(
                {
                    "page_key": page_key,
                    "sheet_id": baseline_meta.get("sheet_id") or current_meta.get("sheet_id") or page_key,
                    "filename": baseline_meta.get("filename") or current_meta.get("filename") or "",
                    "sheet_order": baseline_meta.get("sheet_order") or current_meta.get("sheet_order"),
                    "baseline": baseline_value,
                    "current": current_value,
                    "delta": current_value - baseline_value,
                }
            )
    total_delta = int(len(current_frame)) - int(len(baseline_frame))
    comparison_mode = "per_page" if dropped_sheets or _has_sheet_ids(baseline_frame, current_frame) else "totals_only"
    return {
        "status": "regressed" if dropped_sheets or total_delta < 0 else "ok",
        "comparison_mode": comparison_mode,
        "baseline_total": int(len(baseline_frame)),
        "current_total": int(len(current_frame)),
        "total_delta": total_delta,
        "dropped_sheets": dropped_sheets,
    }


def _page_counts(frame: pd.DataFrame, page_index: dict[str, dict[str, Any]]) -> dict[str, int]:
    if frame.empty or "sheet_id" not in frame.columns:
        return {}
    counts: dict[str, int] = {}
    for sheet_id in frame["sheet_id"].dropna().astype(str):
        page_key = _page_key(page_index.get(sheet_id)) or sheet_id
        counts[page_key] = counts.get(page_key, 0) + 1
    return counts


def _page_index(pages: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if pages.empty or "sheet_id" not in pages.columns:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for row in pages.to_dict(orient="records"):
        sheet_id = str(row.get("sheet_id") or "")
        if not sheet_id:
            continue
        index[sheet_id] = row
    return index


def _page_meta_by_key(pages: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if pages.empty:
        return {}
    meta: dict[str, dict[str, Any]] = {}
    for row in pages.to_dict(orient="records"):
        page_key = _page_key(row)
        if not page_key:
            continue
        meta[page_key] = row
    return meta


def _page_key(page: dict[str, Any] | None) -> str:
    if not page:
        return ""
    filename = str(page.get("filename") or "")
    sheet_order = _normalized_sheet_order(page.get("sheet_order"))
    if sheet_order is not None and filename:
        return f"{sheet_order:04d}:{filename}"
    if filename:
        return filename
    return str(page.get("sheet_id") or "")


def _normalized_sheet_order(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_sheet_ids(baseline_frame: pd.DataFrame, current_frame: pd.DataFrame) -> bool:
    return "sheet_id" in baseline_frame.columns and "sheet_id" in current_frame.columns
