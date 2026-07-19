from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from typer.testing import CliRunner

from dwg_audit.cli import app
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.report import rerun_audit_from_findings
from dwg_audit.report import write_project_artifacts
from dwg_audit.utils.config import DEFAULT_CONFIG


def _source_file(file_id: str, filename: str, sheet_order: int, sheet_no: str, title: str) -> SourceFileRecord:
    return SourceFileRecord(
        file_id=file_id,
        path=f"C:/demo/{filename}",
        filename=filename,
        ext=".dwg",
        sha256=f"sha-{file_id}",
        size_bytes=10,
        sheet_order=sheet_order,
        detected_page_no=sheet_no,
        detected_from="filename",
        sheet_title=title,
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
        dxf_path=f"C:/demo/{filename.replace('.dwg', '.dxf')}",
    )


def _sheet(sheet_id: str, file_id: str, filename: str, sheet_order: int, sheet_no: str, title: str) -> SheetRecord:
    return SheetRecord(
        sheet_id=sheet_id,
        file_id=file_id,
        filename=filename,
        sheet_order=sheet_order,
        sheet_no=sheet_no,
        sheet_title=title,
        sheet_category="二次原理图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
    )


def _pair(
    pair_id: str,
    line_group_id: str,
    sheet_id: str,
    file_id: str,
    left_value: str,
    right_value: str,
    confidence: float,
    filename: str,
    sheet_no: str,
    sheet_order: int,
) -> Pair:
    return Pair(
        pair_id=pair_id,
        line_group_id=line_group_id,
        sheet_id=sheet_id,
        file_id=file_id,
        selected_pair_candidate_id=f"PC-{pair_id}",
        left_value=left_value,
        right_value=right_value,
        confidence=confidence,
        status="pass",
        rationale="golden regression sample",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence={
            "filename": filename,
            "sheet_no": sheet_no,
            "sheet_order": sheet_order,
            "selected_score": confidence,
        },
    )


def _build_findings_only_project(output_dir: Path) -> Path:
    sources = [
        _source_file("F0001", "04.dwg", 4, "04", "交流回路图1"),
        _source_file("F0002", "05.dwg", 5, "05", "交流回路图2"),
    ]
    pages = [
        _sheet("S0001", "F0001", "04.dwg", 4, "04", "交流回路图1"),
        _sheet("S0002", "F0002", "05.dwg", 5, "05", "交流回路图2"),
    ]
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Golden Regression Project",
            project_name="Golden Regression Project",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=2,
            sheet_count=2,
            valid_dwg_files=2,
            invalid_dwg_files=0,
            source_files=sources,
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Golden Regression Project"},
            warnings=[],
        ),
        pages=pages,
        terminal_strips=[],
        project_root="C:/demo",
    )
    artifacts = ProjectArtifacts(
        scan=scan,
        line_groups=[
            LineGroup("G0001", "S0001", "F0001", 0, 0, 30, 0, 30, 0.95, ["L1"], ["CONNECT"]),
            LineGroup("G0002", "S0002", "F0002", 5, 10, 35, 10, 30, 0.95, ["L2"], ["CONNECT"]),
        ],
        pairs=[
            _pair("P0001", "G0001", "S0001", "F0001", "101", "201", 0.97, "04.dwg", "04", 4),
            _pair("P0002", "G0002", "S0002", "F0002", "101", "202", 0.96, "05.dwg", "05", 5),
        ],
    )
    return write_project_artifacts(artifacts, output_dir)


def _decode(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _regression_config() -> dict:
    config = deepcopy(DEFAULT_CONFIG)
    config["runtime"]["profile"] = "regression"
    return config


def _issue_snapshot(audit_dir: Path) -> list[dict[str, object]]:
    payload = json.loads((audit_dir / "issues.json").read_text(encoding="utf-8"))
    snapshots = []
    for issue in payload:
        evidence = _decode(issue["evidence"])
        evidence_refs = _decode(issue["evidence_refs"])
        snapshots.append(
            {
                "rule_id": issue["rule_id"],
                "severity": issue["severity"],
                "title": issue["title"],
                "primary_pair_id": issue["primary_pair_id"],
                "related_pair_ids": _decode(issue["related_pair_ids"]),
                "sheet_ids": _decode(issue["sheet_ids"]),
                "values": _decode(issue["values"]),
                "evidence": {
                    "filename": evidence["filename"],
                    "sheet_no": evidence["sheet_no"],
                    "sheet_order": evidence["sheet_order"],
                    "line_start": evidence["line_start"],
                    "line_end": evidence["line_end"],
                    "conflicting_values": evidence.get("conflicting_values"),
                    "pair_evidence": evidence["pair_evidence"],
                },
                "evidence_refs": [
                    {
                        "pair_id": ref["pair_id"],
                        "filename": ref["filename"],
                        "sheet_no": ref["sheet_no"],
                    }
                    for ref in evidence_refs
                ],
            }
        )
    return snapshots


def test_rerun_audit_from_findings_matches_golden_snapshot(tmp_path: Path) -> None:
    project_dir = _build_findings_only_project(tmp_path)

    audit_dir = rerun_audit_from_findings(project_dir, _regression_config())

    assert audit_dir == project_dir / "audit"
    assert _issue_snapshot(audit_dir) == [
        {
            "rule_id": "R-CROSS-PAGE-CONFLICT",
            "severity": "critical",
            "title": "跨页配对冲突",
            "primary_pair_id": "P0001",
            "related_pair_ids": ["P0002"],
            "sheet_ids": ["S0001", "S0002"],
            "values": ["101", "201", "202"],
            "evidence": {
                "filename": "04.dwg",
                "sheet_no": "04",
                "sheet_order": 4,
                "line_start": [0, 0],
                "line_end": [30, 0],
                "conflicting_values": ["201", "202"],
                "pair_evidence": {
                    "filename": "04.dwg",
                    "sheet_no": "04",
                    "sheet_order": 4,
                    "selected_score": 0.97,
                },
            },
            "evidence_refs": [
                {"pair_id": "P0001", "filename": "04.dwg", "sheet_no": "04"},
                {"pair_id": "P0002", "filename": "05.dwg", "sheet_no": "05"},
            ],
        },
    ]

    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")
    assert "R-CROSS-PAGE-CONFLICT" in report_text
    assert "R-ONE-TO-MANY" not in report_text
    assert "sheet_order=4" in report_text
    assert "line_group=G0001" in report_text

    runtime_profile = json.loads((audit_dir / "runtime_profile.json").read_text(encoding="utf-8"))
    assert runtime_profile == {
        "run_profile": "regression",
        "report_formats": ["md", "html", "xlsx"],
        "diagnostics_status": "generated",
    }
    assert (audit_dir / "audit_v2_issue_clusters.parquet").exists()
    assert (audit_dir / "failure_queue.parquet").exists()
    assert (audit_dir / "topology_shadow_report.json").exists()


def test_run_audit_cli_copies_regenerated_outputs_from_findings(tmp_path: Path) -> None:
    project_dir = _build_findings_only_project(tmp_path)
    copied_audit = tmp_path / "copied_audit"
    config_path = tmp_path / "regression.yml"
    config_path.write_text("runtime:\n  profile: regression\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-audit",
            "--findings",
            str(project_dir / "findings"),
            "--output",
            str(copied_audit),
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert str(copied_audit) in result.stdout
    assert (copied_audit / "audit_report.html").exists()
    assert (copied_audit / "issues.xlsx").exists()
    assert _issue_snapshot(copied_audit) == _issue_snapshot(project_dir / "audit")


def test_production_rerun_skips_diagnostics_and_heavy_report_formats(tmp_path: Path) -> None:
    project_dir = _build_findings_only_project(tmp_path)
    audit_dir = project_dir / "audit"
    copied_audit = tmp_path / "production_audit"
    copied_audit.mkdir()
    (copied_audit / "failure_queue_summary.json").write_text("stale", encoding="utf-8")
    (copied_audit / "audit_report.html").write_text("stale", encoding="utf-8")

    result = rerun_audit_from_findings(project_dir, DEFAULT_CONFIG, copied_audit)

    assert result == copied_audit
    for name in (
        "issue_witnesses_v2.parquet",
        "issue_witness_summary.json",
        "audit_v2_issue_clusters.parquet",
        "audit_v2_summary.json",
        "failure_queue.parquet",
        "failure_queue_summary.json",
        "topology_shadow_report.json",
        "topology_shadow_report.md",
        "issue_root_cause_audit.json",
        "issue_root_cause_audit.md",
        "audit_report.html",
        "issues.xlsx",
    ):
        assert not (audit_dir / name).exists()
        assert not (copied_audit / name).exists()

    assert (copied_audit / "issues.parquet").exists()
    assert (copied_audit / "audit_report.md").exists()
    assert not (copied_audit / "issue_root_cause_audit.json").exists()
    assert not (copied_audit / "issue_root_cause_audit.md").exists()
    runtime_profile = json.loads(
        (copied_audit / "runtime_profile.json").read_text(encoding="utf-8")
    )
    assert runtime_profile == {
        "run_profile": "production",
        "report_formats": ["md"],
        "diagnostics_status": "not_generated_for_profile",
    }
