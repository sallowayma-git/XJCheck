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
        "precision": None,
        "recall": None,
        "precision_recall_status": "not_computed",
    }


def compare_regression_metrics(baseline_frames: FrameMap, current_frames: FrameMap) -> dict[str, Any]:
    """Compare two findings/audit frame snapshots without requiring source DWG files."""
    baseline = summarize_regression_metrics(baseline_frames)
    current = summarize_regression_metrics(current_frames)

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
        "## Rule Delta",
        "",
    ]

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


def _counter_delta(baseline: Mapping[str, int], current: Mapping[str, int]) -> dict[str, int]:
    keys = sorted(set(baseline) | set(current))
    return {key: int(current.get(key, 0)) - int(baseline.get(key, 0)) for key in keys}
