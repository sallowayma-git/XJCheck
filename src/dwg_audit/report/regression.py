from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


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
