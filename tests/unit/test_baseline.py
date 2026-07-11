from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dwg_audit.report.baseline import write_baseline_manifest


_SYMBOL_ARTIFACT_PATHS = (
    "findings/symbol_definitions_v1.parquet",
    "findings/symbol_instances_v1.parquet",
    "findings/unknown_symbol_queue_v1.parquet",
    "findings/symbol_inventory_summary.json",
)


def _write_bundle(project_dir: Path) -> None:
    findings = project_dir / "findings"
    audit = project_dir / "audit"
    findings.mkdir(parents=True)
    audit.mkdir()
    (project_dir / "manifest.json").write_text(
        json.dumps({"file_count": 1, "sheet_count": 1}),
        encoding="utf-8",
    )
    pairs = pd.DataFrame(
        [
            {
                "pair_id": "P1",
                "pair_kind": "ordinary_pair",
                "status": "pass",
            }
        ]
    )
    issues = pd.DataFrame(
        [
            {
                "issue_id": "I1",
                "pair_id": "P1",
                "rule_id": "R-TEST",
                "pair_kind": "ordinary_pair",
            }
        ]
    )
    pairs.to_parquet(findings / "pairs.parquet", index=False)
    issues.to_parquet(audit / "issues.parquet", index=False)
    pd.DataFrame([{"junction_id": "J1"}]).to_parquet(findings / "wire_junctions.parquet", index=False)
    pd.DataFrame([{"network_id": "N1"}]).to_parquet(findings / "wire_networks.parquet", index=False)
    pd.DataFrame([{"observation_id": "O1", "state": "POSSIBLE"}]).to_parquet(
        findings / "geometry_shadow_observations.parquet", index=False
    )
    (findings / "geometry_shadow_observation_summary.json").write_text(
        json.dumps(
            {
                "observation_count": 1,
                "state_counts": {"POSSIBLE": 1},
                "kind_counts": {"endpoint_gap": 1},
                "requires_review_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (findings / "pair_geometry_shadow_summary.json").write_text(
        json.dumps(
            {
                "pair_count": 1,
                "ordinary_pair_count": 1,
                "ordinary_geometry_context_status_counts": {
                    "unique_geometry_component": 1
                },
                "ordinary_unique_geometry_context_ratio": 1.0,
            }
        ),
        encoding="utf-8",
    )
    (findings / "findings.json").write_text(
        json.dumps(
            {
                "entity_coverage_summary": {
                    "total_texts": 1,
                    "audit_scope_texts": 1,
                    "assigned_texts": 1,
                    "unexplained_texts": 0,
                    "unexplained_numeric_texts": 0,
                    "unassigned_wire_segments": 0,
                    "unclassified_blocks": 0,
                    "out_of_scope_texts": 0,
                    "coverage_ratio": 1.0,
                    "identity_ok": True,
                    "suspicious_out_of_scope_expansion": False,
                }
            }
        ),
        encoding="utf-8",
    )
    (audit / "topology_shadow_report.json").write_text(
        json.dumps(
            {
                "candidate_issue_count": 1,
                "recoverable_issue_count": 0,
                "recoverable_ratio": 0.0,
                "reason_counts": {"no_signal": 1},
                "branch_local_status_counts": {"context_only": 1},
            }
        ),
        encoding="utf-8",
    )


def _write_symbol_inventory(findings_dir: Path) -> dict[str, Path]:
    definitions = pd.DataFrame(
        [
            {
                "symbol_definition_id": "SD1-demo",
                "definition_name": "DEMO_BLOCK",
                "instance_count": 2,
            }
        ]
    )
    instances = pd.DataFrame(
        [
            {"symbol_instance_id": "SI1-a", "definition_name": "DEMO_BLOCK"},
            {"symbol_instance_id": "SI1-b", "definition_name": "DEMO_BLOCK"},
        ]
    )
    unknown_queue = pd.DataFrame(
        [
            {
                "unknown_symbol_id": "US1-demo",
                "definition_name": "DEMO_BLOCK",
                "priority_score": 2,
            }
        ]
    )
    summary = {
        "schema_version": "symbol-inventory-summary-v1",
        "definition_count": 1,
        "instance_count": 2,
        "unknown_definition_count": 1,
        "registered_definition_count": 0,
        "unknown_critical_issue_eligible_count": 0,
    }
    paths = {
        "findings/symbol_definitions_v1.parquet": findings_dir / "symbol_definitions_v1.parquet",
        "findings/symbol_instances_v1.parquet": findings_dir / "symbol_instances_v1.parquet",
        "findings/unknown_symbol_queue_v1.parquet": findings_dir / "unknown_symbol_queue_v1.parquet",
        "findings/symbol_inventory_summary.json": findings_dir / "symbol_inventory_summary.json",
    }
    definitions.to_parquet(paths["findings/symbol_definitions_v1.parquet"], index=False)
    instances.to_parquet(paths["findings/symbol_instances_v1.parquet"], index=False)
    unknown_queue.to_parquet(paths["findings/unknown_symbol_queue_v1.parquet"], index=False)
    paths["findings/symbol_inventory_summary.json"].write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    return paths


def test_write_baseline_manifest_freezes_metrics_and_inputs(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    _write_bundle(project_dir)
    config = tmp_path / "config.yml"
    config.write_text("recognition: {}\n", encoding="utf-8")
    arbitration = tmp_path / "arbitration.md"
    arbitration.write_text("review evidence\n", encoding="utf-8")

    output = write_baseline_manifest(
        project_dir,
        alias="demo",
        input_root=tmp_path,
        config_path=config,
        arbitration_paths=[arbitration],
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"]["alias"] == "demo"
    assert payload["metrics"]["pair_count"] == 1
    assert payload["metrics"]["issue_count"] == 1
    assert payload["metrics"]["legacy_topology"] == {
        "wire_junction_count": 1,
        "wire_network_count": 1,
    }
    assert payload["metrics"]["graph_shadow"]["geometry_observations"]["state_counts"] == {
        "POSSIBLE": 1
    }
    assert payload["metrics"]["graph_shadow"]["pair_geometry"][
        "ordinary_unique_geometry_context_ratio"
    ] == 1.0
    assert payload["metrics"]["symbol_inventory"] == {}
    assert all(payload["redlines"].values())
    assert (output.parent / "config.yml").exists()
    assert (output.parent / "arbitration" / "arbitration.md").exists()
    pair_artifact = next(
        item for item in payload["artifacts"]["files"] if item["path"] == "findings/pairs.parquet"
    )
    assert pair_artifact["rows"] == 1
    assert not any(
        item["path"] == "reader_run.json" for item in payload["artifacts"]["files"]
    )
    assert not any(
        item["path"] in _SYMBOL_ARTIFACT_PATHS for item in payload["artifacts"]["files"]
    )


def test_write_baseline_manifest_inventories_optional_reader_run(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    _write_bundle(project_dir)
    reader_run = project_dir / "reader_run.json"
    reader_run.write_text(
        json.dumps(
            {
                "schema_version": "reader-run-manifest/v1",
                "project_id": "demo",
                "runs": [],
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.yml"
    config.write_text("recognition: {}\n", encoding="utf-8")

    output = write_baseline_manifest(
        project_dir,
        alias="demo",
        input_root=tmp_path,
        config_path=config,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    artifact = next(
        item for item in payload["artifacts"]["files"] if item["path"] == "reader_run.json"
    )
    assert artifact["size_bytes"] == reader_run.stat().st_size
    assert len(artifact["sha256"]) == 64


def test_write_baseline_manifest_inventories_optional_extraction_gate(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    _write_bundle(project_dir)
    gate = project_dir / "extraction_completeness.json"
    gate.write_text(
        json.dumps(
            {
                "analysis_status": "COMPLETE",
                "clean_conclusion_allowed": True,
                "pages": [],
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.yml"
    config.write_text("recognition: {}\n", encoding="utf-8")

    output = write_baseline_manifest(
        project_dir,
        alias="demo",
        input_root=tmp_path,
        config_path=config,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    artifact = next(
        item
        for item in payload["artifacts"]["files"]
        if item["path"] == "extraction_completeness.json"
    )
    assert artifact["size_bytes"] == gate.stat().st_size
    assert len(artifact["sha256"]) == 64


def test_write_baseline_manifest_inventories_optional_symbol_inventory(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    _write_bundle(project_dir)
    symbol_paths = _write_symbol_inventory(project_dir / "findings")
    config = tmp_path / "config.yml"
    config.write_text("recognition: {}\n", encoding="utf-8")

    output = write_baseline_manifest(
        project_dir,
        alias="demo",
        input_root=tmp_path,
        config_path=config,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    inventory_by_path = {item["path"]: item for item in payload["artifacts"]["files"]}
    for relative in _SYMBOL_ARTIFACT_PATHS:
        assert relative in inventory_by_path
        artifact = inventory_by_path[relative]
        assert artifact["size_bytes"] == symbol_paths[relative].stat().st_size
        assert len(artifact["sha256"]) == 64
        if relative.endswith(".parquet"):
            assert artifact["rows"] == (2 if "instances" in relative else 1)

    assert payload["metrics"]["symbol_inventory"] == {
        "schema_version": "symbol-inventory-summary-v1",
        "definition_count": 1,
        "instance_count": 2,
        "unknown_definition_count": 1,
        "registered_definition_count": 0,
        "unknown_critical_issue_eligible_count": 0,
    }
    # Symbol inventory is non-gating: redlines remain the established set only.
    assert "symbol" not in " ".join(payload["redlines"])
    assert all(payload["redlines"].values())


def test_write_baseline_manifest_succeeds_without_symbol_inventory(tmp_path: Path) -> None:
    """Old bundles without Phase 117 symbol artifacts still freeze cleanly."""
    project_dir = tmp_path / "project"
    _write_bundle(project_dir)
    config = tmp_path / "config.yml"
    config.write_text("recognition: {}\n", encoding="utf-8")

    output = write_baseline_manifest(
        project_dir,
        alias="legacy",
        input_root=tmp_path,
        config_path=config,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["project"]["alias"] == "legacy"
    assert payload["metrics"]["symbol_inventory"] == {}
    assert not any(
        item["path"] in _SYMBOL_ARTIFACT_PATHS for item in payload["artifacts"]["files"]
    )
    assert all(payload["redlines"].values())


def test_write_baseline_manifest_rejects_incomplete_bundle(tmp_path: Path) -> None:
    config = tmp_path / "config.yml"
    config.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Baseline bundle is incomplete"):
        write_baseline_manifest(
            tmp_path / "missing",
            alias="missing",
            input_root=tmp_path,
            config_path=config,
        )
