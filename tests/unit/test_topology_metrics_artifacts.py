from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from dwg_audit.report.topology_metrics_artifacts import (
    write_topology_metrics_artifacts,
)


def _read_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_row(
    project_id: str,
    *,
    evaluation_status: str = "STRUCTURAL_ONLY",
    **overrides: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "project_id": project_id,
        "split": "validation",
        "schema_version": "topology-metrics-v1",
        "project_dir": f"C:/evidence/{project_id}",
        "truth_path": None,
        "evaluation_status": evaluation_status,
        "structural_metrics_complete": evaluation_status != "INVALID",
        "metrics_complete": evaluation_status == "MEASURED_PROJECT",
        "measurement_scope": (
            "project"
            if evaluation_status == "MEASURED_PROJECT"
            else "scoped"
            if evaluation_status == "MEASURED_SCOPED"
            else None
        ),
        "truth_sample_count": 0,
        "truth_sheet_count": 0,
        "artifact_status": {"truth": "not_provided"},
        "artifact_errors": {},
        "truth_metric_status": {
            "junction": "unmeasured_no_labels",
            "pairwise_connectivity": "unmeasured_no_labels",
            "open_endpoint": "unmeasured_no_labels",
        },
        "junction_true_positive_count": None,
        "junction_false_positive_count": None,
        "junction_false_negative_count": None,
        "junction_precision": None,
        "junction_recall": None,
        "network_overmerge_suspicion_count": 0,
        "network_split_suspicion_count": 0,
        "network_overmerge_count": 0,
        "network_split_count": 0,
        "pairwise_connectivity_true_positive_count": None,
        "pairwise_connectivity_false_positive_count": None,
        "pairwise_connectivity_false_negative_count": None,
        "pairwise_connectivity_precision": None,
        "pairwise_connectivity_recall": None,
        "pairwise_connectivity_f1": None,
        "open_endpoint_true_positive_count": None,
        "open_endpoint_false_positive_count": None,
        "open_endpoint_false_negative_count": None,
        "open_endpoint_precision": None,
        "open_endpoint_recall": None,
        "witness_complete_count": 1,
        "witness_total_count": 1,
        "witness_completeness": 1.0,
        "non_asserted_union_violation_count": 0,
        "v2_changes_legacy_result_count": 0,
    }
    row.update(overrides)
    return row


def test_write_topology_metrics_artifacts_healthy_projects(tmp_path: Path) -> None:
    rows = [
        _metric_row(
            "P003",
            evaluation_status="MEASURED_PROJECT",
            truth_path="C:/truth/P003.csv",
            truth_sample_count=10,
            truth_sheet_count=2,
            junction_precision=0.97,
            junction_recall=0.99,
            junction_true_positive_count=97,
            junction_false_positive_count=3,
            junction_false_negative_count=1,
            network_overmerge_count=2,
            network_overmerge_suspicion_count=2,
            pairwise_connectivity_precision=0.95,
            pairwise_connectivity_recall=0.94,
            pairwise_connectivity_f1=0.9449,
            pairwise_connectivity_true_positive_count=95,
            pairwise_connectivity_false_positive_count=5,
            pairwise_connectivity_false_negative_count=6,
            open_endpoint_precision=0.93,
            open_endpoint_recall=0.92,
            open_endpoint_true_positive_count=93,
            open_endpoint_false_positive_count=7,
            open_endpoint_false_negative_count=8,
        ),
        _metric_row(
            "P001",
            evaluation_status="MEASURED_PROJECT",
            truth_path="C:/truth/P001.csv",
            truth_sample_count=20,
            truth_sheet_count=3,
            junction_precision=1.0,
            junction_recall=0.98,
            junction_true_positive_count=98,
            junction_false_positive_count=0,
            junction_false_negative_count=2,
            network_split_count=1,
            network_split_suspicion_count=1,
            pairwise_connectivity_precision=0.99,
            pairwise_connectivity_recall=0.97,
            pairwise_connectivity_f1=0.9799,
            pairwise_connectivity_true_positive_count=99,
            pairwise_connectivity_false_positive_count=1,
            pairwise_connectivity_false_negative_count=3,
            open_endpoint_precision=0.96,
            open_endpoint_recall=0.95,
            open_endpoint_true_positive_count=96,
            open_endpoint_false_positive_count=4,
            open_endpoint_false_negative_count=5,
        ),
    ]
    paths = write_topology_metrics_artifacts(rows, tmp_path)

    assert paths == {
        "by_project": tmp_path / "topology_metrics_by_project.csv",
        "summary": tmp_path / "topology_metrics_summary.json",
    }
    with paths["by_project"].open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
        columns = list(csv_rows[0])
    assert [row["project_id"] for row in csv_rows] == ["P001", "P003"]
    assert "evaluation_status" in columns
    assert "status" not in columns
    assert csv_rows[0]["evaluation_status"] == "MEASURED_PROJECT"
    assert csv_rows[0]["artifact_contract_status"] == "VALID"
    assert csv_rows[0]["artifact_status"] == '{"truth":"not_provided"}'

    summary = _read_summary(paths["summary"])
    assert summary["artifact_status"] == "VALID"
    assert summary["evaluation_status_counts"] == {"MEASURED_PROJECT": 2}
    assert summary["min_junction_precision"] == 0.97
    assert summary["min_junction_recall"] == 0.98
    assert summary["min_pairwise_connectivity_f1"] == 0.9449
    assert summary["min_open_endpoint_precision"] == 0.93
    assert summary["network_overmerge_count_total"] == 2
    assert summary["network_split_count_total"] == 1
    assert summary["all_projects_measured_project"] is True


def test_invalid_project_diagnostics_do_not_enter_aggregate_scores(
    tmp_path: Path,
) -> None:
    paths = write_topology_metrics_artifacts(
        [
            _metric_row(
                "BROKEN",
                evaluation_status="INVALID",
                structural_metrics_complete=False,
                junction_precision=1.0,
                junction_recall=1.0,
                network_overmerge_count=0,
                network_split_count=0,
                pairwise_connectivity_precision=1.0,
                pairwise_connectivity_recall=1.0,
                pairwise_connectivity_f1=1.0,
                open_endpoint_precision=1.0,
                open_endpoint_recall=1.0,
            )
        ],
        tmp_path,
    )

    summary = _read_summary(paths["summary"])
    assert summary["artifact_status"] == "VALID"
    assert summary["evaluation_status_counts"] == {"INVALID": 1}
    assert summary["min_junction_precision"] is None
    assert summary["min_pairwise_connectivity_precision"] is None
    assert summary["min_open_endpoint_recall"] is None
    assert summary["network_overmerge_count_total"] is None
    assert summary["network_split_count_total"] is None
    assert summary["connectivity_available_project_count"] == 0
    assert summary["connectivity_missing_project_count"] == 1


def test_structural_only_row_cannot_claim_truth_scores(tmp_path: Path) -> None:
    paths = write_topology_metrics_artifacts(
        [
            _metric_row(
                "P001",
                junction_precision=1.0,
                junction_recall=1.0,
                pairwise_connectivity_precision=1.0,
                pairwise_connectivity_recall=1.0,
                pairwise_connectivity_f1=1.0,
                open_endpoint_precision=1.0,
                open_endpoint_recall=1.0,
            )
        ],
        tmp_path,
    )

    summary = _read_summary(paths["summary"])
    assert summary["evaluation_status_counts"] == {"STRUCTURAL_ONLY": 1}
    assert summary["min_junction_precision"] is None
    assert summary["min_pairwise_connectivity_f1"] is None
    assert summary["min_open_endpoint_precision"] is None
    assert summary["availability"]["junction"]["missing_project_count"] == 1


def test_partial_null_metrics_remain_unavailable_for_corpus_minimum(
    tmp_path: Path,
) -> None:
    paths = write_topology_metrics_artifacts(
        [
            _metric_row(
                "P001",
                evaluation_status="MEASURED_SCOPED",
                junction_precision=None,
                junction_recall=0.8,
                network_overmerge_count=None,
                pairwise_connectivity_precision=0.7,
                pairwise_connectivity_recall=None,
                pairwise_connectivity_f1=None,
                open_endpoint_precision=0.6,
                open_endpoint_recall=None,
            ),
            _metric_row(
                "P003",
                evaluation_status="MEASURED_SCOPED",
                junction_precision=0.9,
                junction_recall=None,
                network_split_count=None,
                pairwise_connectivity_precision=None,
                pairwise_connectivity_recall=0.65,
                pairwise_connectivity_f1=None,
                open_endpoint_precision=None,
                open_endpoint_recall=0.55,
            ),
        ],
        tmp_path,
    )

    summary = _read_summary(paths["summary"])
    assert summary["min_junction_precision"] is None
    assert summary["min_junction_recall"] is None
    assert summary["min_pairwise_connectivity_precision"] is None
    assert summary["min_pairwise_connectivity_recall"] is None
    assert summary["min_pairwise_connectivity_f1"] is None
    assert summary["min_open_endpoint_precision"] is None
    assert summary["min_open_endpoint_recall"] is None
    assert summary["network_overmerge_count_total"] is None
    assert summary["network_split_count_total"] is None
    assert summary["availability"]["connectivity"] == {
        "all_projects_available": False,
        "available_project_count": 0,
        "missing_project_count": 0,
        "partial_project_count": 2,
    }


def test_malformed_row_fails_artifact_contract_closed(tmp_path: Path) -> None:
    paths = write_topology_metrics_artifacts(
        [{"project_id": "P001", "evaluation_status": "COMPLETE"}],
        tmp_path,
    )

    with paths["by_project"].open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    summary = _read_summary(paths["summary"])
    assert row["evaluation_status"] == "INVALID"
    assert row["artifact_contract_status"] == "INVALID"
    assert "invalid evaluation_status" in row["artifact_contract_errors"]
    assert summary["artifact_status"] == "INVALID"
    assert summary["evaluation_status_counts"] == {"INVALID": 1}
    assert summary["all_projects_structurally_complete"] is False


def test_artifact_bytes_are_stable_across_input_order(tmp_path: Path) -> None:
    rows = [_metric_row("P003"), _metric_row("P001")]
    first = write_topology_metrics_artifacts(rows, tmp_path / "first")
    second = write_topology_metrics_artifacts(list(reversed(rows)), tmp_path / "second")

    assert first["by_project"].read_bytes() == second["by_project"].read_bytes()
    assert first["summary"].read_bytes() == second["summary"].read_bytes()
