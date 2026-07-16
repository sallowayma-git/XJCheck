from __future__ import annotations

from pathlib import Path

import pandas as pd

from dwg_audit.report.symbol_corpus_queue import evaluate_symbol_corpus_queue
from dwg_audit.report.symbol_corpus_queue import write_symbol_corpus_queue_artifacts


def _write_project(
    root: Path,
    *,
    alias: str,
    fingerprint: str,
    definition_name: str,
    instance_count: int,
    pair_count: int = 0,
    issue_count: int = 0,
) -> Path:
    project_dir = root / alias
    findings = project_dir / "findings"
    findings.mkdir(parents=True)
    frame = pd.DataFrame(
        [
            {
                "symbol_definition_id": f"SD1-{alias}",
                "schema_version": "symbol-definition-v1",
                "fingerprint_version": "local-geometry-fingerprint-v1",
                "project_id": alias,
                "definition_name": definition_name,
                "definition_fingerprint": fingerprint,
                "instance_count": instance_count,
                "sheet_count": 1,
                "local_geometry_signature_count": 1,
                "transform_variant_count": 1,
                "text_slot_entity_types": [],
                "registry_status": "UNKNOWN",
                "symbol_family": None,
                "internal_connectivity_state": "UNKNOWN",
                "declared_port_count": 0,
                "critical_issue_eligible": False,
            }
        ]
    )
    frame.to_parquet(findings / "symbol_definitions_v1.parquet", index=False)
    if pair_count:
        pd.DataFrame({"pair_id": [f"P{i}" for i in range(pair_count)]}).to_parquet(
            findings / "pairs.parquet", index=False
        )
    if issue_count:
        audit = project_dir / "audit"
        audit.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"issue_id": [f"I{i}" for i in range(issue_count)]}).to_parquet(
            audit / "issues.parquet", index=False
        )
    return project_dir


def test_symbol_corpus_queue_excludes_held_out_from_ranking(tmp_path: Path) -> None:
    p001 = _write_project(
        tmp_path,
        alias="P001",
        fingerprint="fp-shared",
        definition_name="SYM_A",
        instance_count=10,
        pair_count=5,
        issue_count=2,
    )
    p003 = _write_project(
        tmp_path,
        alias="P003",
        fingerprint="fp-shared",
        definition_name="SYM_A",
        instance_count=4,
        pair_count=3,
        issue_count=1,
    )
    held = _write_project(
        tmp_path,
        alias="P002",
        fingerprint="fp-held",
        definition_name="SYM_HELD",
        instance_count=100,
        pair_count=50,
        issue_count=20,
    )

    evaluation = evaluate_symbol_corpus_queue(
        {"P001": p001, "P003": p003, "P002": held},
        splits={
            "P001": "calibration",
            "P003": "validation",
            "P002": "heldout_test",
        },
        held_out_projects={"P002"},
        top_n=10,
    )
    summary = evaluation["summary"]
    assert summary["ranking_project_count"] == 2
    assert summary["held_out_usage"] == "reporting_only"
    assert summary["critical_issue_eligible_count"] == 0
    assert len(evaluation["queue"]) == 1
    row = evaluation["queue"][0]
    assert row["definition_fingerprint"] == "fp-shared"
    assert row["total_instance_count"] == 14
    assert row["project_coverage"] == 2
    assert row["annotation_status"] == "PENDING_HUMAN_REVIEW"
    assert row["declared_port_count"] == 0
    assert "P002" not in row["project_ids"]

    paths = write_symbol_corpus_queue_artifacts(evaluation, tmp_path / "out")
    assert paths["queue_csv"].is_file()
    assert paths["summary"].is_file()
    assert paths["queue_json"].is_file()


def test_missing_findings_is_fail_closed(tmp_path: Path) -> None:
    missing = tmp_path / "P009"
    missing.mkdir()
    evaluation = evaluate_symbol_corpus_queue({"P009": missing}, top_n=5)
    assert evaluation["summary"]["status"] == "INVALID"
    assert evaluation["by_project"][0]["status"] == "MISSING"
    assert evaluation["queue"] == []
