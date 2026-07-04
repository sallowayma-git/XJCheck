import json
from pathlib import Path

import pandas as pd

from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SidecarInfo
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.report.artifacts import write_audit_outputs
from dwg_audit.report.artifacts import write_project_artifacts


def test_write_project_artifacts_creates_findings_outputs(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/01.dwg",
        filename="01.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=1,
        detected_page_no="01",
        detected_from="filename",
        sheet_title="封面",
        sheet_category="封面/目录",
        skip_reason="matched skip keyword: 封面",
        valid_dwg_header=True,
        conversion_status="skipped",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[SidecarInfo("prj", None, "missing", None, ["No .prj sidecar found."])],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                "01.dwg",
                1,
                "01",
                "封面",
                "封面/目录",
                "skip",
                "filename",
                False,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan), tmp_path)

    assert (project_dir / "manifest.json").exists()
    assert (project_dir / "findings" / "findings.md").exists()
    assert (project_dir / "findings" / "findings.json").exists()
    assert (project_dir / "findings" / "polylines.parquet").exists()
    assert (project_dir / "findings" / "extraction_warnings.parquet").exists()


def test_write_audit_outputs_emits_issue_artifacts_with_evidence_fields(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/04.dwg",
        filename="04.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=4,
        detected_page_no="04",
        detected_from="filename",
        sheet_title="交流回路图1",
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[SidecarInfo("prj", None, "missing", None, ["No .prj sidecar found."])],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                "04.dwg",
                4,
                "04",
                "交流回路图1",
                "二次原理图",
                "primary",
                "filename",
                True,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    issue = Issue(
        issue_id="I0001",
        rule_id="R-CROSS-PAGE-CONFLICT",
        severity="critical",
        status="open",
        confidence=0.97,
        message="conflict",
        sheet_id="S0001",
        file_id="F0001",
        pair_id="P0001",
        line_group_id="G0001",
        left_value="101",
        right_value="201",
        evidence={
            "filename": "04.dwg",
            "sheet_no": "04",
            "sheet_order": 4,
            "line_start": [10.0, 20.0],
            "line_end": [40.0, 20.0],
        },
        title="跨页配对冲突",
        summary="数字 101 在不同跨页位置出现冲突配对。",
        explanation="同一线号在高置信 pair 中关联到了不一致的目标数字。",
        recommended_action="优先复核 04.dwg 上对应线端的跨页引用。",
    )
    pair = Pair(
        pair_id="P0001",
        line_group_id="G0001",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC1",
        left_value="101",
        right_value="201",
        confidence=0.97,
        status="pass",
        rationale="ok",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence={"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4},
    )
    review_pair = Pair(
        pair_id="P0002",
        line_group_id="G0002",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC2",
        left_value="202",
        right_value="301",
        confidence=0.74,
        status="review",
        rationale="right side has competing numeric candidates",
        alternative_pair_candidate_ids=["PC3"],
        confidence_bucket="review",
        evidence={
            "filename": "04.dwg",
            "sheet_no": "04",
            "sheet_order": 4,
            "line_start": [60.0, 25.0],
            "line_end": [96.0, 25.0],
        },
    )

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan, pairs=[pair, review_pair]), tmp_path)
    audit_dir = write_audit_outputs(
        project_dir,
        issues=[issue],
        pairs=[pair, review_pair],
        source_files=scan.manifest.source_files,
        project_name=scan.manifest.project_name,
    )
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
    findings_text = (project_dir / "findings" / "findings.md").read_text(encoding="utf-8")
    issues_payload = json.loads((audit_dir / "issues.json").read_text(encoding="utf-8"))
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert findings_payload["pair_evidence_summary"]["pairs_with_evidence"] == 2
    assert findings_payload["pair_evidence_summary"]["review_pairs"] == 1
    assert findings_payload["pair_evidence_summary"]["confidence_bucket_counts"] == {"high": 1, "review": 1}
    assert findings_payload["pair_evidence_summary"]["examples"][0]["summary"] == (
        "filename=04.dwg, sheet_no=04, sheet_order=4, line_group=G0001, left_value=101, right_value=201"
    )
    assert findings_payload["pair_evidence_summary"]["review_examples"][0]["pair_id"] == "P0002"
    assert "## Pair Evidence 摘要" in findings_text
    assert "## 待复核 Pair 概览" in findings_text
    assert "## 代表性 Pair 证据" in findings_text
    assert "ConfidenceBuckets: `{\"high\": 1, \"review\": 1}`" in findings_text
    assert "ReviewPairs: `1`" in findings_text
    assert "filename=04.dwg, sheet_no=04, sheet_order=4, line_group=G0001, left_value=101, right_value=201" in findings_text
    assert "`P0002` 202 -> 301 (status=review, bucket=review, conf=0.74)" in findings_text
    assert "rationale=right side has competing numeric candidates" in findings_text

    assert issues_payload[0]["issue_id"] == "I0001"
    assert json.loads(issues_payload[0]["evidence"])["filename"] == "04.dwg"

    assert "## 审计概览" in report_text
    assert "SeverityCounts: `{\"critical\": 1}`" in report_text
    assert "RuleCounts: `{\"R-CROSS-PAGE-CONFLICT\": 1}`" in report_text
    assert "ReviewPairs: `1`" in report_text
    assert "## 待复核 Pair" in report_text
    assert "`P0002` 202 -> 301 (status=review, bucket=review, conf=0.74)" in report_text
    assert "evidence=filename=04.dwg, sheet_no=04, sheet_order=4, line_start=[60.0, 25.0], line_end=[96.0, 25.0]" in report_text
    assert "## 异常清单" in report_text
    assert "### `I0001` 跨页配对冲突" in report_text
    assert "- Location: file=04.dwg, sheet_no=04, sheet_order=4, line_group=G0001, line_start=[10.0, 20.0], line_end=[40.0, 20.0]" in report_text
    assert "- Summary: 数字 101 在不同跨页位置出现冲突配对。" in report_text
    assert "- Explanation: 同一线号在高置信 pair 中关联到了不一致的目标数字。" in report_text
    assert "- RecommendedAction: 优先复核 04.dwg 上对应线端的跨页引用。" in report_text


def test_write_audit_outputs_respects_requested_report_formats(tmp_path: Path) -> None:
    issue = Issue(
        issue_id="I0001",
        rule_id="R-CROSS-PAGE-CONFLICT",
        severity="critical",
        status="open",
        confidence=0.91,
        message="conflict",
        sheet_id="S0001",
        file_id="F0001",
        pair_id="P0001",
        line_group_id="G0001",
        left_value="101",
        right_value="201",
        evidence_refs=[
            {
                "filename": "04.dwg",
                "sheet_no": "04",
                "sheet_order": 4,
                "line_group_id": "G0001",
            }
        ],
        title="跨页配对冲突",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[issue],
        pairs=[],
        source_files=[],
        project_name="Demo 项目",
        formats=["md"],
    )
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert (audit_dir / "audit_report.md").exists()
    assert not (audit_dir / "audit_report.html").exists()
    assert not (audit_dir / "issues.xlsx").exists()
    assert "- Evidence: ref1: filename=04.dwg, sheet_no=04, sheet_order=4" in report_text


def test_write_audit_outputs_adds_evidence_display_to_html_and_excel(tmp_path: Path) -> None:
    issue = Issue(
        issue_id="I0001",
        rule_id="R-CROSS-PAGE-CONFLICT",
        severity="critical",
        status="open",
        confidence=0.91,
        message="conflict",
        sheet_id="S0001",
        file_id="F0001",
        pair_id="P0001",
        line_group_id="G0001",
        left_value="101",
        right_value="201",
        evidence_refs=[
            {
                "filename": "04.dwg",
                "sheet_no": "04",
                "sheet_order": 4,
                "line_group_id": "G0001",
                "left_value": "101",
                "right_value": "201",
            }
        ],
        title="跨页配对冲突",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[issue],
        pairs=[],
        source_files=[],
        project_name="Demo 项目",
        formats="html,xlsx",
    )
    html = (audit_dir / "audit_report.html").read_text(encoding="utf-8")
    excel_issues = pd.read_excel(audit_dir / "issues.xlsx", sheet_name="issues")

    assert not (audit_dir / "audit_report.md").exists()
    assert "evidence_display" in html
    assert "ref1: filename=04.dwg, sheet_no=04, sheet_order=4" in html
    assert "evidence_display" in excel_issues.columns
    assert "filename=04.dwg" in excel_issues.loc[0, "evidence_display"]
    assert "left_value=101" in excel_issues.loc[0, "evidence_display"]
