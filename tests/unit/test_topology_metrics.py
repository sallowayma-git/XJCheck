from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.report.topology_metrics import evaluate_project_topology_metrics


def _write_healthy_artifacts(project_dir: Path) -> None:
    findings = project_dir / "findings"
    findings.mkdir(parents=True)
    pd.DataFrame(
        [
            {"line_id": "L1", "sheet_id": "S1", "handle": "H1"},
            {"line_id": "L2", "sheet_id": "S1", "handle": "H2"},
            {"line_id": "L3", "sheet_id": "S1", "handle": "H3"},
            {"line_id": "L4", "sheet_id": "S1", "handle": "H4"},
        ]
    ).to_parquet(findings / "lines.parquet", index=False)
    pd.DataFrame(
        [
            {
                "topology_decision_id": "TD-1",
                "junction_observation_id": "JO-1",
                "sheet_id": "S1",
                "decision_kind": "intersection",
                "decision_state": "ASSERTED",
                "source_line_ids": ["L1", "L2"],
                "reason_codes": ["marker"],
                "union_eligible": True,
                "union_applied": True,
            },
            {
                "topology_decision_id": "TD-2",
                "junction_observation_id": "JO-2",
                "sheet_id": "S1",
                "decision_kind": "endpoint_endpoint_gap",
                "decision_state": "POSSIBLE",
                "source_line_ids": ["L3", "L4"],
                "reason_codes": ["gap"],
                "union_eligible": False,
                "union_applied": False,
            },
        ]
    ).to_parquet(findings / "topology_decisions.parquet", index=False)
    pd.DataFrame(
        [
            {
                "geometry_component_id": "GC-1",
                "sheet_id": "S1",
                "source_line_ids": ["L1", "L2", "L3"],
                "open_node_ids": ["N1", "N2"],
                "junction_node_ids": ["J1"],
            },
            {
                "geometry_component_id": "GC-2",
                "sheet_id": "S1",
                "source_line_ids": ["L4"],
                "open_node_ids": ["N3"],
                "junction_node_ids": [],
            },
        ]
    ).to_parquet(findings / "geometry_shadow_components.parquet", index=False)
    pd.DataFrame(
        [
            {
                "electrical_network_id": "EN-1",
                "sheet_id": "S1",
                "source_line_ids": ["L1", "L2", "L3"],
                "node_ids": ["N1", "N2", "J1"],
                "junction_node_ids": ["J1"],
                "open_node_ids": ["N1", "N2"],
            },
            {
                "electrical_network_id": "EN-2",
                "sheet_id": "S1",
                "source_line_ids": ["L4"],
                "node_ids": ["N3"],
                "junction_node_ids": [],
                "open_node_ids": ["N3"],
            },
        ]
    ).to_parquet(findings / "electrical_networks_v2.parquet", index=False)
    pd.DataFrame(
        [
            {
                "electrical_network_id": "EN-1",
                "sheet_id": "S1",
                "node_id": "N1",
                "source_line_ids": ["L1"],
                "source_handles": ["H1"],
                "boundary_state": "OPEN",
            },
            {
                "electrical_network_id": "EN-1",
                "sheet_id": "S1",
                "node_id": "N2",
                "source_line_ids": ["L3"],
                "source_handles": ["H3"],
                "boundary_state": "OPEN",
            },
            {
                "electrical_network_id": "EN-2",
                "sheet_id": "S1",
                "node_id": "N3",
                "source_line_ids": ["L4"],
                "source_handles": ["H4"],
                "boundary_state": "OPEN",
            },
        ]
    ).to_parquet(findings / "network_open_endpoints_v2.parquet", index=False)
    pd.DataFrame(
        [
            {
                "suspicion_id": "NS-1",
                "suspicion_kind": "OVERMERGE_SUSPICION",
                "review_only": True,
            },
            {
                "suspicion_id": "NS-2",
                "suspicion_kind": "SPLIT_SUSPICION",
                "review_only": True,
            },
        ]
    ).to_parquet(
        findings / "network_validation_suspicions_v2.parquet", index=False
    )
    pd.DataFrame(
        [
            {
                "pair_id": "P-1",
                "equivalence_status": "UNIQUE_V2_NETWORK",
                "v2_changes_legacy_result": False,
            },
            {
                "pair_id": "P-2",
                "equivalence_status": "MULTIPLE_V2_NETWORKS",
                "v2_changes_legacy_result": True,
            },
        ]
    ).to_parquet(
        findings / "legacy_pair_network_equivalence.parquet", index=False
    )
    (findings / "network_witness_summary.json").write_text(
        json.dumps(
            {
                "witness_count": 3,
                "resolved_count": 3,
                "unresolved_count": 0,
                "witness_completeness": 1.0,
            }
        ),
        encoding="utf-8",
    )


def test_evaluate_project_topology_metrics_healthy(tmp_path: Path) -> None:
    project_dir = tmp_path / "P001"
    _write_healthy_artifacts(project_dir)
    truth_path = tmp_path / "truth.csv"
    pd.DataFrame(
        [
            {
                "sheet_id": "S1",
                "junction_node_id": "J1",
                "expected_junction": True,
                "source_line_id_a": "L1",
                "source_line_id_b": "L2",
                "expected_connected": True,
                "open_node_id": "N1",
                "expected_open": True,
                "measurement_scope": "project",
            },
            {
                "sheet_id": "S1",
                "junction_node_id": "J2",
                "expected_junction": True,
                "source_line_id_a": "L1",
                "source_line_id_b": "L4",
                "expected_connected": False,
                "open_node_id": "J1",
                "expected_open": False,
                "measurement_scope": "project",
            },
        ]
    ).to_csv(truth_path, index=False)

    result = evaluate_project_topology_metrics(project_dir, truth_path)

    assert result["schema_version"] == "topology-metrics-v1"
    assert result["evaluation_status"] == "MEASURED_SCOPED"
    assert result["structural_metrics_complete"] is True
    assert result["metrics_complete"] is False
    assert result["measurement_scope"] == "scoped"
    assert set(result["artifact_status"].values()) == {"valid"}
    assert result["junction_precision"] == 1.0
    assert result["junction_recall"] == 0.5
    assert result["pairwise_connectivity_f1"] == 1.0
    assert result["open_endpoint_precision"] == 1.0
    assert result["open_endpoint_recall"] == 1.0
    assert result["network_overmerge_suspicion_count"] == 1
    assert result["network_split_suspicion_count"] == 1
    assert result["network_overmerge_count"] is None
    assert result["network_split_count"] is None
    assert result["witness_completeness"] == 1.0
    assert result["non_asserted_union_violation_count"] == 0
    assert result["v2_changes_legacy_result_count"] == 1


def test_evaluate_project_topology_metrics_missing_is_fail_closed(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "P002"
    _write_healthy_artifacts(project_dir)
    missing = project_dir / "findings" / "electrical_networks_v2.parquet"
    missing.unlink()

    result = evaluate_project_topology_metrics(project_dir)

    assert result["evaluation_status"] == "INVALID"
    assert result["metrics_complete"] is False
    assert result["artifact_status"]["electrical_networks_v2"] == "missing"
    assert result["pairwise_connectivity_f1"] is None
    assert result["witness_completeness"] is None
    assert result["network_overmerge_suspicion_count"] == 1
    assert result["non_asserted_union_violation_count"] == 0


def test_evaluate_project_topology_metrics_corrupt_is_fail_closed(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "P003"
    _write_healthy_artifacts(project_dir)
    corrupt = (
        project_dir
        / "findings"
        / "network_validation_suspicions_v2.parquet"
    )
    corrupt.write_bytes(b"not-a-parquet-file")

    result = evaluate_project_topology_metrics(project_dir)

    assert result["evaluation_status"] == "INVALID"
    assert result["artifact_status"]["network_validation_suspicions_v2"] == "invalid"
    assert result["network_overmerge_suspicion_count"] is None
    assert result["network_split_suspicion_count"] is None


def test_legacy_zero_row_suspicion_parquet_is_accepted_as_zero(tmp_path: Path) -> None:
    project_dir = tmp_path / "P004"
    _write_healthy_artifacts(project_dir)
    pd.DataFrame().to_parquet(
        project_dir / "findings" / "network_validation_suspicions_v2.parquet",
        index=False,
    )

    result = evaluate_project_topology_metrics(project_dir)

    assert result["evaluation_status"] == "STRUCTURAL_ONLY"
    assert result["structural_metrics_complete"] is True
    assert result["network_overmerge_suspicion_count"] == 0
    assert result["network_split_suspicion_count"] == 0
    assert result["network_overmerge_count"] is None
    assert result["network_split_count"] is None
