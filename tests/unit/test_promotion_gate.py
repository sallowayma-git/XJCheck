from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dwg_audit.report.promotion_gate import (
    _topology_row_primary_ready,
    collect_project_promotion_metrics,
    evaluate_promotion_gate,
    write_promotion_gate_evidence,
)


def _write_healthy_project(project_dir: Path, *, pairs: int = 2, issues: int = 1) -> None:
    findings = project_dir / "findings"
    audit = project_dir / "audit"
    findings.mkdir(parents=True)
    audit.mkdir(parents=True)

    pd.DataFrame(
        [{"pair_id": f"P{i}", "pair_kind": "ordinary_pair", "status": "pass"} for i in range(pairs)],
        columns=["pair_id", "pair_kind", "status"],
    ).to_parquet(findings / "pairs.parquet", index=False)
    pd.DataFrame(
        [
            {
                "issue_id": f"I{i}",
                "rule_id": "R-PAIR-MISSING-SIDE",
                "sheet_id": "S1",
                "filename": "a.dwg",
                "pair_id": f"P{i}",
                "left_value": "1",
                "right_value": "2",
                "values": ["1", "2"],
            }
            for i in range(issues)
        ],
        columns=[
            "issue_id", "rule_id", "sheet_id", "filename", "pair_id",
            "left_value", "right_value", "values",
        ],
    ).to_parquet(audit / "issues.parquet", index=False)

    (project_dir / "extraction_completeness.json").write_text(
        json.dumps(
            {
                "analysis_status": "COMPLETE",
                "clean_conclusion_allowed": True,
                "incomplete_page_count": 0,
                "pages": [
                    {
                        "sheet_id": "S1",
                        "audit_role": "primary",
                        "audit_disposition": "audit_required",
                        "status": "COMPLETE",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (findings / "engine_comparison_v1.json").write_text(
        json.dumps(
            {
                "schema_version": "engine-comparison-v1",
                "v2_changes_legacy_result_count": 0,
                "pair_count": pairs,
            }
        ),
        encoding="utf-8",
    )
    (findings / "project_graph_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "project-graph-v1",
                "sources": {"possible_union": False},
            }
        ),
        encoding="utf-8",
    )
    (findings / "constraint_resolution_summary.json").write_text(
        json.dumps(
            {
                "strong_violation_count": 0,
                "inviolable_strong_constraints": True,
            }
        ),
        encoding="utf-8",
    )
    (findings / "topology_decision_summary.json").write_text(
        json.dumps({"non_asserted_union_violation_count": 0}),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"line_id": "L1", "sheet_id": "S1", "handle": "H1"},
            {"line_id": "L2", "sheet_id": "S1", "handle": "H2"},
        ]
    ).to_parquet(findings / "lines.parquet", index=False)
    pd.DataFrame(
        [
            {
                "topology_decision_id": "TD1",
                "junction_observation_id": "JO1",
                "sheet_id": "S1",
                "decision_kind": "endpoint_endpoint",
                "decision_state": "ASSERTED",
                "source_line_ids": ["L1", "L2"],
                "reason_codes": ["test"],
                "union_eligible": True,
                "union_applied": False,
            }
        ]
    ).to_parquet(findings / "topology_decisions.parquet", index=False)
    pd.DataFrame(
        [
            {
                "geometry_component_id": "GC1",
                "sheet_id": "S1",
                "source_line_ids": ["L1", "L2"],
                "open_node_ids": ["N1"],
                "junction_node_ids": ["J1"],
            }
        ]
    ).to_parquet(findings / "geometry_shadow_components.parquet", index=False)
    pd.DataFrame(
        [
            {
                "electrical_network_id": "EN1",
                "sheet_id": "S1",
                "source_line_ids": ["L1", "L2"],
                "node_ids": ["N1", "J1"],
                "junction_node_ids": ["J1"],
                "open_node_ids": ["N1"],
            }
        ]
    ).to_parquet(findings / "electrical_networks_v2.parquet", index=False)
    pd.DataFrame(
        [
            {
                "electrical_network_id": "EN1",
                "sheet_id": "S1",
                "node_id": "N1",
                "source_line_ids": ["L1"],
                "source_handles": ["H1"],
                "boundary_state": "OPEN",
            }
        ]
    ).to_parquet(findings / "network_open_endpoints_v2.parquet", index=False)
    pd.DataFrame(
        columns=["suspicion_id", "suspicion_kind", "review_only"]
    ).to_parquet(findings / "network_validation_suspicions_v2.parquet", index=False)
    pd.DataFrame(
        [
            {
                "pair_id": "P0",
                "equivalence_status": "UNIQUE_V2_NETWORK",
                "v2_changes_legacy_result": False,
            }
        ]
    ).to_parquet(findings / "legacy_pair_network_equivalence.parquet", index=False)
    (findings / "network_witness_summary.json").write_text(
        json.dumps(
            {
                "witness_count": 1,
                "resolved_count": 1,
                "unresolved_count": 0,
                "witness_completeness": 1.0,
            }
        ),
        encoding="utf-8",
    )
    (audit / "audit_v2_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "audit-v2-summary-v1",
                "witness_completeness": 1.0,
                "cluster_count": 1,
                "issue_count": issues,
            }
        ),
        encoding="utf-8",
    )
    (audit / "failure_queue_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "failure-queue-summary-v1",
                "critical_count": 0,
                "by_category": {},
                "by_severity": {},
                "by_routing": {},
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        columns=["failure_id", "severity", "category", "suggested_routing", "message"]
    ).to_parquet(audit / "failure_queue.parquet", index=False)


def test_collect_project_metrics_healthy(tmp_path: Path) -> None:
    project = tmp_path / "p001"
    _write_healthy_project(project)
    row = collect_project_promotion_metrics(
        project_id="P001", project_dir=project, split="calibration_legacy"
    )
    assert row["analysis_status"] == "COMPLETE"
    assert row["false_clean"] is False
    assert row["witness_completeness"] == 1.0
    assert row["possible_union"] is False
    assert row["v2_changes_legacy_result_count"] == 0
    assert row["failure_queue_critical_count"] == 0
    assert row["bundle_layout"] == "direct"


def test_collect_project_metrics_nested_runner_layout(tmp_path: Path) -> None:
    """Runner may nest findings under project_slug with cache/logs siblings."""
    alias_root = tmp_path / "P001"
    nested = alias_root / "WBH-812E-E1SA_example"
    _write_healthy_project(nested)
    (alias_root / "cache").mkdir()
    (alias_root / "logs").mkdir()
    (alias_root / "run_summary.json").write_text("{}", encoding="utf-8")

    row = collect_project_promotion_metrics(
        project_id="P001", project_dir=alias_root, split="calibration_legacy"
    )
    assert row["bundle_layout"] == "nested_project_slug"
    assert Path(row["bundle_dir"]) == nested.resolve()
    assert row["analysis_status"] == "COMPLETE"
    assert row["artifact_status"]["extraction_gate"] == "valid"
    assert row["artifact_status"]["pairs"] == "valid"
    assert row["artifact_status"]["issues"] == "valid"
    assert row["witness_completeness"] == 1.0
    assert row["false_clean"] is False


def test_evaluate_promotion_gate_review_only_ready_not_primary(tmp_path: Path) -> None:
    p001 = tmp_path / "p001"
    p003 = tmp_path / "p003"
    _write_healthy_project(p001, pairs=3, issues=2)
    _write_healthy_project(p003, pairs=1, issues=0)

    # Frozen hard labels matching only P001 hard issues emitted below.
    hard_issue = {
        "issue_id": "H1",
        "rule_id": "R-ONE-TO-MANY",
        "sheet_id": "S1",
        "filename": "a.dwg",
        "pair_id": "P0",
        "left_value": "1",
        "right_value": "2",
        "values": ["1", "2"],
    }
    audit = p001 / "audit"
    issues = pd.read_parquet(audit / "issues.parquet").to_dict(orient="records")
    issues.append(hard_issue)
    pd.DataFrame(issues).to_parquet(audit / "issues.parquet", index=False)

    labels = {
        "schema_version": "hard-issue-labels-v1",
        "hard_rule_ids": ["R-ONE-TO-MANY"],
        "policy": {
            "not_a_human_gold_standard": True,
            "label_basis": "test-frozen",
        },
        "projects": {
            "P001": {
                "labels": [
                    {
                        "rule_id": "R-ONE-TO-MANY",
                        "sheet_id": "S1",
                        "filename": "a.dwg",
                        "pair_id": "P0",
                        "left_value": "1",
                        "right_value": "2",
                        "values": ["1", "2"],
                    }
                ]
            },
            "P003": {"labels": []},
        },
    }
    label_path = tmp_path / "labels.json"
    label_path.write_text(json.dumps(labels), encoding="utf-8")

    evidence = evaluate_promotion_gate(
        projects={"P001": p001, "P003": p003},
        splits={"P001": "calibration_legacy", "P003": "validation"},
        hard_issue_label_pack=label_path,
        primary_engine="legacy",
    )
    assert evidence["structural_pass_all"] is True, evidence
    assert evidence["hard_issue_precision_ge_99"] is True
    assert evidence["decision"]["ready_for_review_only_v2_assist"] is True
    # Frozen non-human labels must not authorize primary flip.
    assert evidence["decision"]["ready_for_primary_engine_flip"] is False
    assert evidence["decision"]["primary_engine_current"] == "legacy"
    assert evidence["decision"]["heldout_used_for_tuning"] is False
    assert evidence["decision"]["hard_issue_precision_status"] == "PASS_ON_FROZEN_CALVAL_LABELS"

    out = write_promotion_gate_evidence(evidence, tmp_path / "gate")
    assert out["promotion_gate_evidence"].is_file()
    assert out["metrics_by_project"].is_file()
    assert out["decision_log"].is_file()
    assert out["topology_metrics_by_project"].is_file()
    assert out["topology_metrics_summary"].is_file()
    payload = json.loads(out["promotion_gate_evidence"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "promotion-gate-evidence-v1"
    topology_rows = pd.read_csv(out["topology_metrics_by_project"])
    assert set(topology_rows["evaluation_status"]) == {"STRUCTURAL_ONLY"}
    assert set(topology_rows["artifact_contract_status"]) == {"VALID"}
    topology_summary = json.loads(
        out["topology_metrics_summary"].read_text(encoding="utf-8")
    )
    assert topology_summary["artifact_status"] == "VALID"
    assert topology_summary["all_projects_structurally_complete"] is True
    assert topology_summary["evaluation_status_counts"] == {
        "STRUCTURAL_ONLY": 2
    }
    assert topology_summary["min_junction_precision"] is None
    assert topology_summary["min_pairwise_connectivity_f1"] is None


def test_false_clean_and_possible_union_fail_structural(tmp_path: Path) -> None:
    project = tmp_path / "bad"
    _write_healthy_project(project, pairs=0, issues=0)
    (project / "extraction_completeness.json").write_text(
        json.dumps(
            {
                "analysis_status": "INCOMPLETE_EXTRACTION",
                "clean_conclusion_allowed": True,
                "incomplete_page_count": 1,
                "pages": [
                    {
                        "sheet_id": "S1",
                        "audit_role": "primary",
                        "audit_disposition": "audit_required",
                        "status": "INCOMPLETE_EXTRACTION",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    findings = project / "findings"
    (findings / "project_graph_summary.json").write_text(
        json.dumps({"sources": {"possible_union": True}}),
        encoding="utf-8",
    )
    evidence = evaluate_promotion_gate(
        projects={"PBAD": project},
        splits={"PBAD": "validation"},
        primary_engine="legacy",
    )
    row = evidence["projects"][0]
    assert row["false_clean"] is True
    assert row["possible_union"] is True
    assert row["structural_pass"] is False
    assert "false_clean" in row["structural_fail_reasons"]
    assert "possible_union" in row["structural_fail_reasons"]
    assert evidence["decision"]["ready_for_review_only_v2_assist"] is False
    assert evidence["decision"]["ready_for_primary_engine_flip"] is False


def test_heldout_excluded_from_hard_label_eval(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    held = tmp_path / "held"
    _write_healthy_project(cal)
    _write_healthy_project(held)

    labels = {
        "hard_rule_ids": ["R-ONE-TO-MANY"],
        "policy": {"not_a_human_gold_standard": True},
        "projects": {"P001": {"labels": []}, "P002": {"labels": []}},
    }
    label_path = tmp_path / "labels.json"
    label_path.write_text(json.dumps(labels), encoding="utf-8")

    evidence = evaluate_promotion_gate(
        projects={"P001": cal, "P002": held},
        splits={"P001": "calibration_legacy", "P002": "heldout_test"},
        hard_issue_label_pack=label_path,
        heldout_project_ids={"P002"},
        primary_engine="legacy",
    )
    hard = evidence["hard_issue_eval"]
    assert hard is not None
    evaluated_ids = {row["project_id"] for row in hard["projects"]}
    assert evaluated_ids == {"P001"}
    assert evidence["heldout_count"] == 1
    assert evidence["decision"]["heldout_used_for_tuning"] is False


@pytest.mark.parametrize(
    "relative_path",
    [
        "findings/engine_comparison_v1.json",
        "findings/project_graph_summary.json",
        "findings/topology_decision_summary.json",
        "audit/failure_queue_summary.json",
        "audit/failure_queue.parquet",
        "audit/issues.parquet",
    ],
)
def test_missing_required_artifact_fails_closed(tmp_path: Path, relative_path: str) -> None:
    project = tmp_path / "project"
    _write_healthy_project(project)
    (project / relative_path).unlink()

    evidence = evaluate_promotion_gate(
        projects={"P1": project},
        splits={"P1": "validation"},
    )

    row = evidence["projects"][0]
    assert row["structural_pass"] is False
    assert any(reason.endswith("_missing_or_invalid") for reason in row["structural_fail_reasons"])
    assert evidence["decision"]["ready_for_review_only_v2_assist"] is False


@pytest.mark.parametrize("witness", [float("nan"), float("inf"), 1.01, -0.01, "bad"])
def test_invalid_witness_fails_closed(tmp_path: Path, witness: object) -> None:
    project = tmp_path / "project"
    _write_healthy_project(project)
    (project / "audit" / "audit_v2_summary.json").write_text(
        json.dumps({"witness_completeness": witness}),
        encoding="utf-8",
    )

    evidence = evaluate_promotion_gate(projects={"P1": project})
    row = evidence["projects"][0]

    assert row["witness_completeness"] is None
    assert row["structural_pass"] is False
    assert "audit_v2_summary_missing_or_invalid" in row["structural_fail_reasons"]


def test_unknown_unresolved_critical_is_a_structural_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_healthy_project(project)
    pd.DataFrame(
        [
            {
                "failure_id": "F1",
                "severity": "critical",
                "category": "unresolved_symbol",
                "suggested_routing": "SYMBOL",
                "message": "unknown high-impact symbol",
            }
        ]
    ).to_parquet(project / "audit" / "failure_queue.parquet", index=False)

    evidence = evaluate_promotion_gate(projects={"P1": project})
    row = evidence["projects"][0]

    assert row["unknown_or_unresolved_critical_count"] == 1
    assert "unknown_unresolved_critical" in row["structural_fail_reasons"]
    assert row["structural_pass"] is False


def _append_hard_issue(project: Path, issue_id: str) -> dict[str, object]:
    issue = {
        "issue_id": issue_id,
        "rule_id": "R-ONE-TO-MANY",
        "sheet_id": "S1",
        "filename": "a.dwg",
        "pair_id": "P0",
        "left_value": "1",
        "right_value": "2",
        "values": ["1", "2"],
    }
    path = project / "audit" / "issues.parquet"
    rows = pd.read_parquet(path).to_dict(orient="records")
    rows.append(issue)
    pd.DataFrame(rows).to_parquet(path, index=False)
    return {key: value for key, value in issue.items() if key != "issue_id"}


def _write_label_pack(path: Path, project_id: str, label: dict[str, object], *, human: bool) -> None:
    path.write_text(
        json.dumps(
            {
                "hard_rule_ids": ["R-ONE-TO-MANY"],
                "policy": {
                    "not_a_human_gold_standard": not human,
                    "label_basis": "human-heldout" if human else "frozen-calval",
                },
                "projects": {project_id: {"labels": [label]}},
            }
        ),
        encoding="utf-8",
    )


def _write_project_topology_truth(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "sheet_id": "S1",
                "decision_kind": "endpoint_endpoint",
                "reason_code": "test",
                "source_handles": "H1|H2",
                "expected_state": "ASSERTED",
                "source_line_id_a": "L1",
                "source_line_id_b": "L2",
                "expected_connected": True,
                "open_node_id": "N1",
                "expected_open": True,
                "measurement_scope": "project",
            }
        ]
    ).to_csv(path, index=False)


def test_primary_flip_rejects_legacy_csv_claiming_project_scope(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    held = tmp_path / "held"
    _write_healthy_project(cal)
    _write_healthy_project(held)
    cal_label = _append_hard_issue(cal, "HCAL")
    held_label = _append_hard_issue(held, "HHELD")
    cal_pack = tmp_path / "cal.json"
    held_pack = tmp_path / "held.json"
    cal_truth = tmp_path / "cal_topology.csv"
    held_truth = tmp_path / "held_topology.csv"
    _write_label_pack(cal_pack, "P001", cal_label, human=False)
    _write_label_pack(held_pack, "P002", held_label, human=True)
    _write_project_topology_truth(cal_truth)
    _write_project_topology_truth(held_truth)

    common = {
        "projects": {"P001": cal, "P002": held},
        "splits": {"P001": "calibration_legacy", "P002": "  HeldOut_Test "},
        "hard_issue_label_pack": cal_pack,
        "heldout_hard_issue_label_pack": held_pack,
        "topology_truth_paths": {"P001": cal_truth, "P002": held_truth},
        "primary_engine": "legacy",
    }
    without_approval = evaluate_promotion_gate(**common, product_approval=False)
    with_approval = evaluate_promotion_gate(**common, product_approval=True)

    assert without_approval["heldout_count"] == 1
    assert without_approval["decision"]["heldout_hard_pass"] is True
    assert without_approval["decision"]["ready_for_primary_engine_flip"] is False
    assert with_approval["decision"]["topology_metrics_primary_ready"] is False
    assert with_approval["decision"]["ready_for_primary_engine_flip"] is False
    assert with_approval["decision"]["primary_engine_recommended"] == "legacy"
    assert {
        row["evaluation_status"]
        for row in with_approval["topology_metrics_by_project"]
    } == {"MEASURED_SCOPED"}
    assert {
        row["measurement_scope"]
        for row in with_approval["topology_metrics_by_project"]
    } == {"scoped"}


def _project_ready_topology_row() -> dict[str, object]:
    return {
        "evaluation_status": "MEASURED_PROJECT",
        "structural_metrics_complete": True,
        "metrics_complete": True,
        "measurement_scope": "project",
        "truth_sample_count": 12,
        "truth_sheet_count": 3,
        "truth_metric_status": {
            "junction": "measured_project",
            "pairwise_connectivity": "measured_project",
            "open_endpoint": "measured_project",
        },
        "junction_precision": 1.0,
        "junction_recall": 1.0,
        "pairwise_connectivity_precision": 1.0,
        "pairwise_connectivity_recall": 1.0,
        "pairwise_connectivity_f1": 1.0,
        "open_endpoint_precision": 1.0,
        "open_endpoint_recall": 1.0,
        "network_overmerge_suspicion_count": 17,
        "network_split_suspicion_count": 9,
        "network_overmerge_count": 0,
        "network_split_count": 0,
    }


@pytest.mark.parametrize(
    "field",
    [
        "junction_precision",
        "junction_recall",
        "pairwise_connectivity_precision",
        "pairwise_connectivity_recall",
        "pairwise_connectivity_f1",
        "open_endpoint_precision",
        "open_endpoint_recall",
    ],
)
@pytest.mark.parametrize("invalid_value", [0.0, None, float("nan"), float("inf")])
def test_topology_primary_readiness_rejects_empty_or_nonfinite_metrics(
    field: str,
    invalid_value: object,
) -> None:
    row = _project_ready_topology_row()
    row[field] = invalid_value

    assert _topology_row_primary_ready(row) is False


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("network_overmerge_count", None),
        ("network_overmerge_count", 1),
        ("network_split_count", None),
        ("network_split_count", 1),
    ],
)
def test_topology_primary_readiness_requires_zero_real_network_errors(
    field: str,
    invalid_value: object,
) -> None:
    row = _project_ready_topology_row()
    row[field] = invalid_value

    assert _topology_row_primary_ready(row) is False


def test_topology_primary_readiness_does_not_treat_suspicion_as_gold() -> None:
    row = _project_ready_topology_row()

    assert row["network_overmerge_suspicion_count"] == 17
    assert row["network_split_suspicion_count"] == 9
    assert _topology_row_primary_ready(row) is True


def test_empty_human_label_pack_cannot_authorize_primary_flip(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    held = tmp_path / "held"
    _write_healthy_project(cal)
    _write_healthy_project(held)
    cal_label = _append_hard_issue(cal, "HCAL")
    cal_pack = tmp_path / "cal.json"
    held_pack = tmp_path / "held.json"
    _write_label_pack(cal_pack, "P001", cal_label, human=False)
    held_pack.write_text(
        json.dumps(
            {
                "hard_rule_ids": ["R-ONE-TO-MANY"],
                "policy": {"not_a_human_gold_standard": False},
                "projects": {"P002": {"labels": []}},
            }
        ),
        encoding="utf-8",
    )

    evidence = evaluate_promotion_gate(
        projects={"P001": cal, "P002": held},
        splits={"P001": "calibration_legacy", "P002": "heldout_test"},
        hard_issue_label_pack=cal_pack,
        heldout_hard_issue_label_pack=held_pack,
        primary_engine="legacy",
        product_approval=True,
    )

    assert evidence["heldout_hard_issue_eval"]["non_vacuous"] is False
    assert evidence["decision"]["ready_for_primary_engine_flip"] is False
