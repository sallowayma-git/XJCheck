from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from dwg_audit.cli import app
from dwg_audit.report.acceptance import evaluate_acceptance_project
from tests.support.acceptance_mini import prepare_acceptance_mini_run


def _prepare_real_second_minimum_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "real_second_project"
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    findings_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)

    (project_dir / "manifest.json").write_text(
        json.dumps({"project_id": "real-second-minimum", "project_name": "real-second-minimum"}),
        encoding="utf-8",
    )
    (findings_dir / "findings.json").write_text(
        json.dumps({"page_findings": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (audit_dir / "issues.json").write_text("[]", encoding="utf-8")

    rows = [
        ("20 元件接线图2.dwg", "S0020", "3-21CLP2-1", "3-21CD18", "component_mapping", "pass", "3-21CLP2-1->3-21CD18"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP2-2", "3-21n404", "component_mapping", "pass", "3-21CLP2-2->3-21n404"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP3-1", "3-21CD23", "component_mapping", "pass", "3-21CLP3-1->3-21CD23"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP3-2", "3-21n407", "component_mapping", "pass", "3-21CLP3-2->3-21n407"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP4-1", "3-21CD28", "component_mapping", "pass", "3-21CLP4-1->3-21CD28"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP4-2", "3-21n410", "component_mapping", "pass", "3-21CLP4-2->3-21n410"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP5-1", "3-21CD33", "component_mapping", "pass", "3-21CLP5-1->3-21CD33"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP5-2", "3-21n413", "component_mapping", "pass", "3-21CLP5-2->3-21n413"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP6-1", "3-21CD38", "component_mapping", "pass", "3-21CLP6-1->3-21CD38"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP6-2", "3-21n416", "component_mapping", "pass", "3-21CLP6-2->3-21n416"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP7-1", "3-21CD43", "component_mapping", "pass", "3-21CLP7-1->3-21CD43"),
        ("20 元件接线图2.dwg", "S0020", "3-21CLP7-2", "3-21n419", "component_mapping", "pass", "3-21CLP7-2->3-21n419"),
        ("24 右侧端子图2.dwg", "S0024", "1-21CD20", "1-21n406", "table_mapping", "pass", "1-21CD20->1-21n406"),
        ("24 右侧端子图2.dwg", "S0024", "1-21CD25", "1-21n409", "table_mapping", "pass", "1-21CD25->1-21n409"),
        ("24 右侧端子图2.dwg", "S0024", "1-21CD30", "1-21n412", "table_mapping", "pass", "1-21CD30->1-21n412"),
        ("24 右侧端子图2.dwg", "S0024", "1-21CD35", "1-21n415", "table_mapping", "pass", "1-21CD35->1-21n415"),
        ("24 右侧端子图2.dwg", "S0024", "1-21CD40", "1-21n418", "table_mapping", "pass", "1-21CD40->1-21n418"),
        ("24 右侧端子图2.dwg", "S0024", "1-21CD45", "1-21n421", "table_mapping", "pass", "1-21CD45->1-21n421"),
    ]
    pd.DataFrame(
        [
            {
                "filename": filename,
                "sheet_id": sheet_id,
                "left_value": left_value,
                "right_value": right_value,
                "pair_kind": pair_kind,
                "status": status,
                "pair_key": pair_key,
            }
            for filename, sheet_id, left_value, right_value, pair_kind, status, pair_key in rows
        ]
    ).to_parquet(findings_dir / "pairs.parquet", index=False)
    return project_dir


def _prepare_real_first_review_issue_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "real_first_project"
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    findings_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)

    (project_dir / "manifest.json").write_text(
        json.dumps({"project_id": "real-first-minimum", "project_name": "real-first-minimum"}),
        encoding="utf-8",
    )
    (findings_dir / "findings.json").write_text(
        json.dumps({"page_findings": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    pd.DataFrame(
        columns=["filename", "sheet_id", "left_value", "right_value", "pair_kind", "status", "pair_key"]
    ).to_parquet(findings_dir / "pairs.parquet", index=False)
    issues = [
        {
            "issue_id": "I0192",
            "rule_id": "R-MANY-TO-ONE",
            "severity": "review",
            "confidence": 0.9,
            "status": "open",
            "sheet_id": "S0022",
            "sheet_no": "21",
            "filename": "21 元件接线图1.dwg",
            "line_group_id": None,
            "left_value": "1DK-2",
            "right_value": "1QD1",
            "values": ["1QD1", "1QD5"],
            "summary": "Backplate structured mappings share a component-scope endpoint cluster: shared=1QD1, 1QD5.",
            "recommended_action": "Review the component-scope endpoint cluster without removing structured mappings.",
            "evidence_refs": ["P0001@S0022", "P0002@S0022", "PCK0002@S0022", "PCK0004@S0022"],
            "evidence": {
                "filename": "21 元件接线图1.dwg",
                "sheet_no": "21",
                "table_mapping": "backplate_virtual_table",
                "many_to_one_classification": "backplate_structured_shared_endpoint_review",
                "backplate_structured_shared_endpoint_aggregate_review": True,
                "cluster_size": 2,
                "aggregated_shared_endpoints": ["1QD1", "1QD5"],
                "aggregated_logical_endpoints": ["1DK-2", "1DK-4", "NDY306A-3", "NDY306A-5"],
                "cluster_pair_ids": ["P0001", "P0002", "PCK0002", "PCK0004"],
                "pair_kinds": ["component_mapping", "table_mapping"],
                "table_mapping_modes": ["backplate_virtual_table"],
                "component_submodes": ["kk_multi_port_component"],
            },
        },
        {
            "issue_id": "I0194",
            "rule_id": "R-MANY-TO-ONE",
            "severity": "review",
            "confidence": 0.9,
            "status": "open",
            "sheet_id": "S0022",
            "sheet_no": "21",
            "filename": "21 元件接线图1.dwg",
            "line_group_id": None,
            "left_value": "5DK-2",
            "right_value": "5FD1",
            "values": ["5FD1", "5FD25"],
            "summary": "Backplate structured mappings share a component-scope endpoint cluster: shared=5FD1, 5FD25.",
            "recommended_action": "Review the component-scope endpoint cluster without removing structured mappings.",
            "evidence_refs": ["P0167@S0022", "P0168@S0022", "PCK0006@S0022", "PCK0008@S0022"],
            "evidence": {
                "filename": "21 元件接线图1.dwg",
                "sheet_no": "21",
                "table_mapping": "backplate_virtual_table",
                "many_to_one_classification": "backplate_structured_shared_endpoint_review",
                "backplate_structured_shared_endpoint_aggregate_review": True,
                "cluster_size": 2,
                "aggregated_shared_endpoints": ["5FD1", "5FD25"],
                "aggregated_logical_endpoints": ["5DK-2", "5DK-4", "NDY306A-3", "NDY306A-5"],
                "cluster_pair_ids": ["P0167", "P0168", "PCK0006", "PCK0008"],
                "pair_kinds": ["component_mapping", "table_mapping"],
                "table_mapping_modes": ["backplate_virtual_table"],
                "component_submodes": ["kk_multi_port_component"],
            },
        },
        {
            "issue_id": "I0196",
            "rule_id": "R-MANY-TO-ONE",
            "severity": "review",
            "confidence": 0.9,
            "status": "open",
            "sheet_id": "S0022",
            "sheet_no": "21",
            "filename": "21 元件接线图1.dwg",
            "line_group_id": None,
            "left_value": "1-2DK-2",
            "right_value": "1-2QD1",
            "values": ["1-2QD1", "1-2QD12"],
            "summary": "Backplate structured mappings share a component-scope endpoint cluster: shared=1-2QD1, 1-2QD12.",
            "recommended_action": "Review the component-scope endpoint cluster without removing structured mappings.",
            "evidence_refs": ["P0028@S0022", "P0029@S0022", "PCK0010@S0022", "PCK0012@S0022"],
            "evidence": {
                "filename": "21 元件接线图1.dwg",
                "sheet_no": "21",
                "table_mapping": "backplate_virtual_table",
                "many_to_one_classification": "backplate_structured_shared_endpoint_review",
                "backplate_structured_shared_endpoint_aggregate_review": True,
                "cluster_size": 2,
                "aggregated_shared_endpoints": ["1-2QD1", "1-2QD12"],
                "aggregated_logical_endpoints": ["1-2DK-2", "1-2DK-4", "NDY306A-3", "NDY306A-5"],
                "cluster_pair_ids": ["P0028", "P0029", "PCK0010", "PCK0012"],
                "pair_kinds": ["component_mapping", "table_mapping"],
                "table_mapping_modes": ["backplate_virtual_table"],
                "component_submodes": ["kk_multi_port_component"],
            },
        },
        {
            "issue_id": "I0198",
            "rule_id": "R-MANY-TO-ONE",
            "severity": "review",
            "confidence": 0.9,
            "status": "open",
            "sheet_id": "S0022",
            "sheet_no": "21",
            "filename": "21 元件接线图1.dwg",
            "line_group_id": None,
            "left_value": "3-2DK-2",
            "right_value": "3-2QD1",
            "values": ["3-2QD1", "3-2QD12"],
            "summary": "Backplate structured mappings share a component-scope endpoint cluster: shared=3-2QD1, 3-2QD12.",
            "recommended_action": "Review the component-scope endpoint cluster without removing structured mappings.",
            "evidence_refs": ["P0100@S0022", "P0101@S0022", "PCK0014@S0022", "PCK0016@S0022"],
            "evidence": {
                "filename": "21 元件接线图1.dwg",
                "sheet_no": "21",
                "table_mapping": "backplate_virtual_table",
                "many_to_one_classification": "backplate_structured_shared_endpoint_review",
                "backplate_structured_shared_endpoint_aggregate_review": True,
                "cluster_size": 2,
                "aggregated_shared_endpoints": ["3-2QD1", "3-2QD12"],
                "aggregated_logical_endpoints": ["3-2DK-2", "3-2DK-4", "NDY306A-3", "NDY306A-5"],
                "cluster_pair_ids": ["P0100", "P0101", "PCK0014", "PCK0016"],
                "pair_kinds": ["component_mapping", "table_mapping"],
                "table_mapping_modes": ["backplate_virtual_table"],
                "component_submodes": ["kk_multi_port_component"],
            },
        },
    ]
    (audit_dir / "issues.json").write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")
    return project_dir


def test_acceptance_mini_project_produces_quantified_acceptance_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fixture_root, project_dir = prepare_acceptance_mini_run(monkeypatch, tmp_path)
    spec_path = fixture_root / "spec.json"

    runner = CliRunner()
    acceptance_dir = tmp_path / "acceptance_report"
    evaluate = runner.invoke(
        app,
        [
            "evaluate-acceptance",
            "--project",
            str(project_dir),
            "--spec",
            str(spec_path),
            "--output",
            str(acceptance_dir),
        ],
    )
    assert evaluate.exit_code == 0, evaluate.output

    payload = json.loads((acceptance_dir / "acceptance_report.json").read_text(encoding="utf-8"))
    assert payload["acceptance_passed"] is True
    assert payload["pair_metrics"]["expected_pair_count"] == 16
    assert payload["pair_metrics"]["matched_pair_count"] == 16
    assert payload["pair_metrics"]["precision"] == 1.0
    assert payload["pair_metrics"]["recall"] == 1.0
    assert payload["skip_page_metrics"]["matched_count"] == 1
    assert payload["conflict_issue_metrics"]["matched_count"] == 2
    assert payload["missing_issue_metrics"]["matched_count"] == 2
    assert payload["review_pair_metrics"]["matched_count"] == 2
    assert payload["issue_field_coverage"]["all_required_fields_present"] is True

    markdown = (acceptance_dir / "acceptance_report.md").read_text(encoding="utf-8")
    assert "Acceptance Report" in markdown
    assert "Precision: `1.0`" in markdown
    assert "Recall: `1.0`" in markdown


def test_acceptance_evaluation_supports_scoped_pair_metrics(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, project_dir = prepare_acceptance_mini_run(monkeypatch, tmp_path)
    scoped_spec = {
        "name": "acceptance-mini-scoped-page",
        "pair_recall_threshold": 0.9,
        "pair_scope": {
            "included_filenames": ["04 正常回路图A.dwg"],
            "pair_kinds": ["ordinary_pair"],
        },
        "golden_pairs": [
            {"filename": "04 正常回路图A.dwg", "left_value": "101", "right_value": "201"},
            {"filename": "04 正常回路图A.dwg", "left_value": "102", "right_value": "202"},
            {"filename": "04 正常回路图A.dwg", "left_value": "103", "right_value": "203"},
            {"filename": "04 正常回路图A.dwg", "left_value": "104", "right_value": "204"},
            {"filename": "04 正常回路图A.dwg", "left_value": "301", "right_value": "401"},
            {"filename": "04 正常回路图A.dwg", "left_value": "302", "right_value": "501"},
        ],
    }
    spec_path = tmp_path / "scoped_spec.json"
    spec_path.write_text(json.dumps(scoped_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    runner = CliRunner()
    acceptance_dir = tmp_path / "acceptance_scoped_report"
    evaluate = runner.invoke(
        app,
        [
            "evaluate-acceptance",
            "--project",
            str(project_dir),
            "--spec",
            str(spec_path),
            "--output",
            str(acceptance_dir),
        ],
    )
    assert evaluate.exit_code == 0, evaluate.output

    payload = json.loads((acceptance_dir / "acceptance_report.json").read_text(encoding="utf-8"))
    assert payload["acceptance_passed"] is True
    assert payload["pair_scope"]["included_filenames"] == ["04 正常回路图A.dwg"]
    assert payload["pair_metrics"]["expected_pair_count"] == 6
    assert payload["pair_metrics"]["extracted_complete_pair_count"] == 6
    assert payload["pair_metrics"]["matched_pair_count"] == 6
    assert payload["pair_metrics"]["precision"] == 1.0
    assert payload["pair_metrics"]["recall"] == 1.0
    assert payload["skip_page_metrics"]["expected_count"] == 0


def test_acceptance_evaluation_supports_scoped_pair_keys_and_unique_complete_pairs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, project_dir = prepare_acceptance_mini_run(monkeypatch, tmp_path)
    scoped_spec = {
        "name": "acceptance-mini-scoped-pair-keys",
        "pair_recall_threshold": 0.9,
        "pair_scope": {
            "included_pair_refs": [
                {"filename": "04 正常回路图A.dwg", "pair_key": "101->201"},
                {"filename": "04 正常回路图A.dwg", "pair_key": "301->401"},
                {"filename": "05 正常回路图B.dwg", "pair_key": "301->402"}
            ],
            "pair_kinds": ["ordinary_pair"],
        },
        "golden_pairs": [
            {"filename": "04 正常回路图A.dwg", "left_value": "101", "right_value": "201"},
            {"filename": "04 正常回路图A.dwg", "left_value": "301", "right_value": "401"},
            {"filename": "05 正常回路图B.dwg", "left_value": "301", "right_value": "402"},
        ],
    }
    spec_path = tmp_path / "scoped_pair_keys_spec.json"
    spec_path.write_text(json.dumps(scoped_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    runner = CliRunner()
    acceptance_dir = tmp_path / "acceptance_pair_keys_report"
    evaluate = runner.invoke(
        app,
        [
            "evaluate-acceptance",
            "--project",
            str(project_dir),
            "--spec",
            str(spec_path),
            "--output",
            str(acceptance_dir),
        ],
    )
    assert evaluate.exit_code == 0, evaluate.output

    payload = json.loads((acceptance_dir / "acceptance_report.json").read_text(encoding="utf-8"))
    assert payload["acceptance_passed"] is True
    assert payload["pair_scope"]["included_pair_refs"] == [
        {"filename": "04 正常回路图A.dwg", "pair_key": "101->201"},
        {"filename": "04 正常回路图A.dwg", "pair_key": "301->401"},
        {"filename": "05 正常回路图B.dwg", "pair_key": "301->402"},
    ]
    assert payload["pair_metrics"]["expected_pair_count"] == 3
    assert payload["pair_metrics"]["extracted_complete_pair_count"] == 3
    assert payload["pair_metrics"]["matched_pair_count"] == 3
    assert payload["pair_metrics"]["precision"] == 1.0
    assert payload["pair_metrics"]["recall"] == 1.0


def test_acceptance_evaluation_matches_structured_golden_pair_fields(tmp_path: Path) -> None:
    project_dir = tmp_path / "structured_project"
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    findings_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)
    (findings_dir / "findings.json").write_text(
        json.dumps({"page_findings": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (audit_dir / "issues.json").write_text("[]", encoding="utf-8")
    pd.DataFrame(
        [
            {
                "filename": "24 右侧端子图2.dwg",
                "sheet_id": "S0024",
                "left_value": "1-21CD20",
                "right_value": "1-21n406",
                "pair_kind": "table_mapping",
                "status": "pass",
                "pair_key": "1-21CD20->1-21n406",
            },
            {
                "filename": "24 右侧端子图2.dwg",
                "sheet_id": "S0024",
                "left_value": "1-21CD20",
                "right_value": "1-21n406",
                "pair_kind": "ordinary_pair",
                "status": "pass",
                "pair_key": "406->20",
            },
            {
                "filename": "24 右侧端子图2.dwg",
                "sheet_id": "S0024",
                "left_value": "1-21CD20",
                "right_value": "1-21n406",
                "pair_kind": "table_mapping",
                "status": "review",
                "pair_key": "review:1-21CD20->1-21n406",
            },
        ]
    ).to_parquet(findings_dir / "pairs.parquet", index=False)

    base_golden = {
        "filename": "24 右侧端子图2.dwg",
        "left_value": "1-21CD20",
        "right_value": "1-21n406",
    }
    matching_spec = {
        "name": "structured-golden-fields-match",
        "golden_pairs": [
            {
                **base_golden,
                "pair_kind": "table_mapping",
                "status": "pass",
                "pair_key": "1-21CD20->1-21n406",
            }
        ],
    }
    spec_path = tmp_path / "structured_match.json"
    spec_path.write_text(json.dumps(matching_spec, ensure_ascii=False), encoding="utf-8")

    payload = evaluate_acceptance_project(project_dir, spec_path)
    assert payload["acceptance_passed"] is True
    assert payload["pair_metrics"]["matched_pair_count"] == 1
    assert payload["pair_metrics"]["recall"] == 1.0

    for field, value in (
        ("pair_kind", "semantic_mapping"),
        ("status", "fail"),
        ("pair_key", "missing-key"),
    ):
        mismatch_spec = {
            "name": f"structured-golden-{field}-mismatch",
            "golden_pairs": [{**base_golden, field: value}],
        }
        mismatch_spec_path = tmp_path / f"structured_{field}_mismatch.json"
        mismatch_spec_path.write_text(json.dumps(mismatch_spec, ensure_ascii=False), encoding="utf-8")

        mismatch_payload = evaluate_acceptance_project(project_dir, mismatch_spec_path)
        assert mismatch_payload["acceptance_passed"] is False
        assert mismatch_payload["pair_metrics"]["matched_pair_count"] == 0
        assert mismatch_payload["pair_metrics"]["missing_pairs"] == mismatch_spec["golden_pairs"]


def test_acceptance_evaluation_matches_structured_review_issue_fields(tmp_path: Path) -> None:
    project_dir = _prepare_real_first_review_issue_project(tmp_path)
    matching_spec = {
        "name": "structured-review-issue-match",
        "expected_review_issues": [
            {
                "rule_id": "R-MANY-TO-ONE",
                "filename": "21 元件接线图1.dwg",
                "sheet_id": "S0022",
                "severity": "review",
                "status": "open",
                "review_classification": "backplate_structured_shared_endpoint_review",
                "summary_contains": ["component-scope endpoint cluster", "1QD1, 1QD5"],
                "evidence_contains": {
                    "backplate_structured_shared_endpoint_aggregate_review": True,
                    "cluster_size": 2,
                    "aggregated_shared_endpoints": ["1QD1", "1QD5"],
                    "pair_kinds": ["component_mapping", "table_mapping"],
                    "table_mapping_modes": ["backplate_virtual_table"],
                    "component_submodes": ["kk_multi_port_component"],
                },
            }
        ],
    }
    spec_path = tmp_path / "structured_review_issue_match.json"
    spec_path.write_text(json.dumps(matching_spec, ensure_ascii=False), encoding="utf-8")

    payload = evaluate_acceptance_project(project_dir, spec_path)
    assert payload["acceptance_passed"] is True
    assert payload["review_issue_metrics"]["matched_count"] == 1
    assert payload["review_issue_metrics"]["recall"] == 1.0

    mismatch_spec = {
        "name": "structured-review-issue-mismatch",
        "expected_review_issues": [
            {
                **matching_spec["expected_review_issues"][0],
                "evidence_contains": {
                    "backplate_structured_shared_endpoint_aggregate_review": True,
                    "cluster_size": 3,
                },
            }
        ],
    }
    mismatch_spec_path = tmp_path / "structured_review_issue_mismatch.json"
    mismatch_spec_path.write_text(json.dumps(mismatch_spec, ensure_ascii=False), encoding="utf-8")

    mismatch_payload = evaluate_acceptance_project(project_dir, mismatch_spec_path)
    assert mismatch_payload["acceptance_passed"] is False
    assert mismatch_payload["review_issue_metrics"]["matched_count"] == 0
    assert mismatch_payload["review_issue_metrics"]["missing_items"] == mismatch_spec["expected_review_issues"]


def test_acceptance_suite_evaluation_summarizes_required_cases(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _, fault_injected_project = prepare_acceptance_mini_run(monkeypatch, tmp_path)
    real_first_project = _prepare_real_first_review_issue_project(tmp_path)
    real_second_project = _prepare_real_second_minimum_project(tmp_path)
    suite_path = Path(__file__).resolve().parents[1] / "fixtures" / "acceptance_suite" / "mvp_minimum_suite.json"

    runner = CliRunner()
    output_dir = tmp_path / "acceptance_suite_report"
    evaluate = runner.invoke(
        app,
        [
            "evaluate-acceptance-suite",
            "--suite",
            str(suite_path),
            "--project-alias",
            f"fault_injected={fault_injected_project}",
            "--project-alias",
            f"real_first={real_first_project}",
            "--project-alias",
            f"real_second={real_second_project}",
            "--output",
            str(output_dir),
        ],
    )
    assert evaluate.exit_code == 0, evaluate.output

    payload = json.loads((output_dir / "acceptance_suite_report.json").read_text(encoding="utf-8"))
    assert payload["acceptance_passed"] is True
    assert payload["suite_name"] == "internal-mvp-minimum-acceptance-suite"
    assert payload["required_case_count"] == 4
    assert payload["required_passed_case_count"] == 4
    assert payload["passed_case_count"] == 4
    assert {item["case_id"] for item in payload["cases"]} == {
        "fault_injected_acceptance_mini",
        "real_first_backplate_structured_shared_phase83",
        "real_second_component_terminal_subset",
        "real_second_terminal_s0024",
    }
    assert all(item["status"] == "evaluated" for item in payload["cases"])
    assert all(item["acceptance_passed"] is True for item in payload["cases"])

    markdown = (output_dir / "acceptance_suite_report.md").read_text(encoding="utf-8")
    assert "Acceptance Suite Report" in markdown
    assert "fault_injected_acceptance_mini" in markdown
    assert "real_first_backplate_structured_shared_phase83" in markdown
    assert "real_second_component_terminal_subset" in markdown
    assert "real_second_terminal_s0024" in markdown
