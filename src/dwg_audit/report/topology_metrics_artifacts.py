from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from dwg_audit.report.topology_metrics import SCHEMA_VERSION as PROJECT_SCHEMA_VERSION


SCHEMA_VERSION = "topology-metrics-summary-v1"

_EVALUATION_STATUSES = {
    "INVALID",
    "STRUCTURAL_ONLY",
    "MEASURED_SCOPED",
    "MEASURED_PROJECT",
}

_METRIC_COLUMNS = (
    "junction_precision",
    "junction_recall",
    "pairwise_connectivity_precision",
    "pairwise_connectivity_recall",
    "pairwise_connectivity_f1",
    "open_endpoint_precision",
    "open_endpoint_recall",
    "witness_completeness",
)

_COUNT_COLUMNS = (
    "truth_sample_count",
    "truth_sheet_count",
    "junction_true_positive_count",
    "junction_false_positive_count",
    "junction_false_negative_count",
    "network_overmerge_suspicion_count",
    "network_split_suspicion_count",
    "network_overmerge_count",
    "network_split_count",
    "pairwise_connectivity_true_positive_count",
    "pairwise_connectivity_false_positive_count",
    "pairwise_connectivity_false_negative_count",
    "open_endpoint_true_positive_count",
    "open_endpoint_false_positive_count",
    "open_endpoint_false_negative_count",
    "witness_complete_count",
    "witness_total_count",
    "non_asserted_union_violation_count",
    "v2_changes_legacy_result_count",
)

_CSV_COLUMNS = (
    "project_id",
    "split",
    "schema_version",
    "evaluation_status",
    "artifact_contract_status",
    "artifact_contract_errors",
    "structural_metrics_complete",
    "metrics_complete",
    "measurement_scope",
    *_COUNT_COLUMNS[:2],
    *_COUNT_COLUMNS[2:5],
    "junction_precision",
    "junction_recall",
    *_COUNT_COLUMNS[5:9],
    *_COUNT_COLUMNS[9:12],
    "pairwise_connectivity_precision",
    "pairwise_connectivity_recall",
    "pairwise_connectivity_f1",
    *_COUNT_COLUMNS[12:15],
    "open_endpoint_precision",
    "open_endpoint_recall",
    *_COUNT_COLUMNS[15:17],
    "witness_completeness",
    *_COUNT_COLUMNS[17:],
    "artifact_status",
    "artifact_errors",
    "truth_metric_status",
    "project_dir",
    "truth_path",
)

_REQUIRED_DICT_COLUMNS = (
    "artifact_status",
    "artifact_errors",
    "truth_metric_status",
)


def write_topology_metrics_artifacts(
    metrics_by_project: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Path]:
    """Write deterministic topology evidence without completing absent metrics.

    The project evaluator deliberately retains some diagnostic values when a
    bundle is invalid. Those values stay visible in the CSV, but invalid rows
    never contribute to corpus minima or totals in the JSON summary.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = sorted(
        (_normalize_row(metrics) for metrics in metrics_by_project),
        key=lambda row: (
            str(row.get("project_id") or ""),
            str(row.get("split") or ""),
            str(row.get("project_dir") or ""),
        ),
    )
    csv_path = output_dir / "topology_metrics_by_project.csv"
    summary_path = output_dir / "topology_metrics_summary.json"

    _write_csv(rows, csv_path)
    summary_path.write_text(
        json.dumps(_summarize(rows), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return {"by_project": csv_path, "summary": summary_path}


def _normalize_row(metrics: dict[str, Any]) -> dict[str, Any]:
    source = metrics if isinstance(metrics, dict) else {}
    errors: list[str] = []
    row: dict[str, Any] = {column: None for column in _CSV_COLUMNS}

    project_id = _optional_text(source.get("project_id"))
    if project_id is None:
        errors.append("missing project_id")
    row["project_id"] = project_id
    row["split"] = _optional_text(source.get("split"))

    schema_version = _optional_text(source.get("schema_version"))
    row["schema_version"] = schema_version
    if schema_version != PROJECT_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {PROJECT_SCHEMA_VERSION}"
        )

    status = _optional_text(source.get("evaluation_status"))
    status = status.upper() if status is not None else "INVALID"
    if status not in _EVALUATION_STATUSES:
        errors.append("invalid evaluation_status")
        status = "INVALID"
    row["evaluation_status"] = status

    for key in ("structural_metrics_complete", "metrics_complete"):
        value = source.get(key)
        if not isinstance(value, bool):
            errors.append(f"{key} must be boolean")
            value = False
        row[key] = value

    scope = _optional_text(source.get("measurement_scope"))
    scope = scope.casefold() if scope is not None else None
    if scope not in {None, "scoped", "project"}:
        errors.append("measurement_scope must be scoped, project, or null")
        scope = None
    row["measurement_scope"] = scope

    for key in _METRIC_COLUMNS:
        if key not in source:
            errors.append(f"missing {key}")
            row[key] = None
            continue
        value = _bounded_metric(source.get(key))
        if source.get(key) is not None and value is None:
            errors.append(f"{key} must be finite and within [0, 1]")
        row[key] = value

    for key in _COUNT_COLUMNS:
        if key not in source:
            errors.append(f"missing {key}")
            row[key] = None
            continue
        value = _nonnegative_int(source.get(key))
        if source.get(key) is not None and value is None:
            errors.append(f"{key} must be a non-negative integer or null")
        row[key] = value

    for key in _REQUIRED_DICT_COLUMNS:
        value = source.get(key)
        if not isinstance(value, dict):
            errors.append(f"{key} must be an object")
            value = {}
        row[key] = dict(sorted(value.items(), key=lambda item: str(item[0])))

    row["project_dir"] = _optional_text(source.get("project_dir"))
    if row["project_dir"] is None:
        errors.append("missing project_dir")
    row["truth_path"] = _optional_text(source.get("truth_path"))

    structural_complete = row["structural_metrics_complete"] is True
    metrics_complete = row["metrics_complete"] is True
    if status != "INVALID" and not structural_complete:
        errors.append("non-INVALID evaluation requires structural metrics")
    if metrics_complete and status != "MEASURED_PROJECT":
        errors.append("metrics_complete requires MEASURED_PROJECT")
    if status == "STRUCTURAL_ONLY" and (metrics_complete or scope is not None):
        errors.append("STRUCTURAL_ONLY requires incomplete metrics and null scope")
    if status == "MEASURED_SCOPED" and (metrics_complete or scope != "scoped"):
        errors.append("MEASURED_SCOPED requires scoped, incomplete metrics")
    if status == "MEASURED_PROJECT" and (
        not metrics_complete or scope != "project"
    ):
        errors.append("MEASURED_PROJECT requires complete project-scope metrics")
    if status == "MEASURED_PROJECT" and any(
        row[key] is None
        for key in (
            "junction_precision",
            "junction_recall",
            "pairwise_connectivity_precision",
            "pairwise_connectivity_recall",
            "pairwise_connectivity_f1",
            "open_endpoint_precision",
            "open_endpoint_recall",
        )
    ):
        errors.append("MEASURED_PROJECT cannot contain null truth metrics")

    row["artifact_contract_errors"] = sorted(set(errors))
    row["artifact_contract_status"] = "VALID" if not errors else "INVALID"
    return row


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: _csv_value(row.get(key)) for key in _CSV_COLUMNS}
            )


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    effective_statuses = [
        row["evaluation_status"]
        if row.get("artifact_contract_status") == "VALID"
        else "INVALID"
        for row in rows
    ]
    status_counts = Counter(effective_statuses)
    contract_valid_count = sum(
        row.get("artifact_contract_status") == "VALID" for row in rows
    )
    structurally_complete_count = sum(
        _aggregate_eligible(row)
        and row.get("structural_metrics_complete") is True
        for row in rows
    )

    minimums = {
        key: _complete_minimum(rows, key)
        for key in (
            "junction_precision",
            "junction_recall",
            "pairwise_connectivity_precision",
            "pairwise_connectivity_recall",
            "pairwise_connectivity_f1",
            "open_endpoint_precision",
            "open_endpoint_recall",
        )
    }
    overmerge = _count_summary(rows, "network_overmerge_count")
    split = _count_summary(rows, "network_split_count")
    junction = _availability(
        rows,
        ("junction_precision", "junction_recall"),
    )
    connectivity = _availability(
        rows,
        (
            "pairwise_connectivity_precision",
            "pairwise_connectivity_recall",
            "pairwise_connectivity_f1",
        ),
    )
    open_endpoint = _availability(
        rows,
        ("open_endpoint_precision", "open_endpoint_recall"),
    )

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_status": (
            "VALID"
            if rows and contract_valid_count == len(rows)
            else "INVALID"
        ),
        "project_count": len(rows),
        "artifact_contract_valid_project_count": contract_valid_count,
        "artifact_contract_invalid_project_count": len(rows) - contract_valid_count,
        "evaluation_status_counts": dict(sorted(status_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "structural_metrics_complete_project_count": structurally_complete_count,
        "structural_metrics_incomplete_project_count": (
            len(rows) - structurally_complete_count
        ),
        "all_projects_structurally_complete": bool(rows)
        and structurally_complete_count == len(rows),
        "all_projects_measured_project": bool(rows)
        and all(status == "MEASURED_PROJECT" for status in effective_statuses),
        "minimums": minimums,
        "network_errors": {
            "overmerge_total": overmerge["total"],
            "split_total": split["total"],
            "overmerge_available_project_count": overmerge["available_project_count"],
            "overmerge_missing_project_count": overmerge["missing_project_count"],
            "split_available_project_count": split["available_project_count"],
            "split_missing_project_count": split["missing_project_count"],
        },
        "availability": {
            "junction": junction,
            "connectivity": connectivity,
            "open_endpoint": open_endpoint,
        },
    }
    summary.update({f"min_{key}": value for key, value in minimums.items()})
    summary.update(
        {
            "network_overmerge_count_total": overmerge["total"],
            "network_split_count_total": split["total"],
            "junction_available_project_count": junction["available_project_count"],
            "junction_missing_project_count": junction["missing_project_count"],
            "connectivity_available_project_count": connectivity[
                "available_project_count"
            ],
            "connectivity_missing_project_count": connectivity[
                "missing_project_count"
            ],
            "open_endpoint_available_project_count": open_endpoint[
                "available_project_count"
            ],
            "open_endpoint_missing_project_count": open_endpoint[
                "missing_project_count"
            ],
        }
    )
    return summary


def _availability(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    complete = 0
    partial = 0
    for row in rows:
        present = sum(
            _aggregate_metric(row, key) is not None for key in keys
        )
        if present == len(keys):
            complete += 1
        elif present:
            partial += 1
    missing = len(rows) - complete - partial
    return {
        "available_project_count": complete,
        "partial_project_count": partial,
        "missing_project_count": missing,
        "all_projects_available": bool(rows) and complete == len(rows),
    }


def _complete_minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [_aggregate_metric(row, key) for row in rows]
    if not rows or any(value is None for value in values):
        return None
    return min(value for value in values if value is not None)


def _count_summary(rows: list[dict[str, Any]], key: str) -> dict[str, int | None]:
    values = [_aggregate_count(row, key) for row in rows]
    available = sum(value is not None for value in values)
    return {
        "total": (
            sum(value for value in values if value is not None)
            if rows and available == len(rows)
            else None
        ),
        "available_project_count": available,
        "missing_project_count": len(rows) - available,
    }


def _aggregate_eligible(row: dict[str, Any]) -> bool:
    return (
        row.get("artifact_contract_status") == "VALID"
        and row.get("evaluation_status") != "INVALID"
    )


def _aggregate_metric(row: dict[str, Any], key: str) -> float | None:
    if not _aggregate_eligible(row) or row.get("evaluation_status") not in {
        "MEASURED_SCOPED",
        "MEASURED_PROJECT",
    }:
        return None
    return _bounded_metric(row.get(key))


def _aggregate_count(row: dict[str, Any], key: str) -> int | None:
    if not _aggregate_eligible(row):
        return None
    return _nonnegative_int(row.get(key))


def _bounded_metric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) and 0.0 <= parsed <= 1.0 else None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        serializable = sorted(value) if isinstance(value, set) else value
        return json.dumps(
            serializable,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return value
