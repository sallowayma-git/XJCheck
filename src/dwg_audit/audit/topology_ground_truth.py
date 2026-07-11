from __future__ import annotations

from typing import Any

import pandas as pd


def evaluate_topology_ground_truth(
    decisions: pd.DataFrame,
    lines: pd.DataFrame,
    truth: pd.DataFrame,
) -> dict[str, Any]:
    handle_by_line = {
        str(row["line_id"]): str(row["handle"])
        for _, row in lines.iterrows()
    }
    predicted: dict[str, str] = {}
    for _, row in decisions.iterrows():
        reason_codes = _listish(row.get("reason_codes"))
        reason = str(reason_codes[0]) if reason_codes else ""
        handles = sorted(
            handle_by_line.get(str(line_id), f"missing:{line_id}")
            for line_id in _listish(row.get("source_line_ids"))
        )
        signature = _signature(
            str(row.get("sheet_id") or ""),
            str(row.get("decision_kind") or ""),
            reason,
            handles,
        )
        predicted[signature] = str(row.get("decision_state") or "UNKNOWN")

    rows: list[dict[str, Any]] = []
    for _, row in truth.iterrows():
        handles = sorted(str(row["source_handles"]).split("|"))
        signature = _signature(
            str(row["sheet_id"]),
            str(row["decision_kind"]),
            str(row["reason_code"]),
            handles,
        )
        expected = str(row["expected_state"])
        actual = predicted.get(signature)
        rows.append(
            {
                "sample_id": str(row["sample_id"]),
                "expected": expected,
                "actual": actual,
                "matched": actual is not None,
                "correct": actual == expected,
                "decision_kind": str(row["decision_kind"]),
            }
        )

    matched = [row for row in rows if row["matched"]]
    asserted_predictions = [row for row in matched if row["actual"] == "ASSERTED"]
    asserted_correct = [row for row in asserted_predictions if row["expected"] == "ASSERTED"]
    asserted_crossings = [
        row
        for row in asserted_predictions
        if row["decision_kind"] == "intersection"
    ]
    false_asserted_crossings = [
        row for row in asserted_crossings if row["expected"] != "ASSERTED"
    ]
    return {
        "schema_version": "topology-ground-truth-evaluation-v1",
        "sample_count": len(rows),
        "matched_count": len(matched),
        "correct_count": sum(row["correct"] for row in rows),
        "state_accuracy": round(
            sum(row["correct"] for row in rows) / len(rows) if rows else 0.0, 6
        ),
        "asserted_precision": round(
            len(asserted_correct) / len(asserted_predictions)
            if asserted_predictions
            else 0.0,
            6,
        ),
        "asserted_crossing_count": len(asserted_crossings),
        "asserted_crossing_false_connect_count": len(false_asserted_crossings),
        "rows": rows,
    }


def _signature(
    sheet_id: str,
    decision_kind: str,
    reason_code: str,
    handles: list[str],
) -> str:
    return "|".join([sheet_id, decision_kind, reason_code, *handles])


def _listish(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return list(value.tolist())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]
