from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dwg_audit.report.baseline import write_baseline_manifest


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
    assert all(payload["redlines"].values())
    assert (output.parent / "config.yml").exists()
    assert (output.parent / "arbitration" / "arbitration.md").exists()
    pair_artifact = next(
        item for item in payload["artifacts"]["files"] if item["path"] == "findings/pairs.parquet"
    )
    assert pair_artifact["rows"] == 1


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
