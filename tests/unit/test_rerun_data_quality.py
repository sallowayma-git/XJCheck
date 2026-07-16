from __future__ import annotations

import json
from pathlib import Path

import pytest

from dwg_audit.audit.data_quality import DATA_QUALITY_RULE_ID
from dwg_audit.audit.data_quality import build_incomplete_extraction_issues
from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import SheetRecord


def _page() -> SheetRecord:
    return SheetRecord(
        sheet_id="S0001",
        file_id="F0001",
        filename="01.dwg",
        sheet_order=1,
        sheet_no="01",
        sheet_title="二次原理图",
        sheet_category="二次原理图",
        audit_role="primary",
        page_no_source="filename",
        is_primary_audit_candidate=True,
        audit_disposition="audit_required",
        route_target="WireDiagramExtractor",
    )


def _ordinary_issue() -> Issue:
    return Issue(
        issue_id="I0001",
        rule_id="R-PAIR-MISSING-SIDE",
        severity="review",
        status="review",
        confidence=0.8,
        message="ordinary",
        sheet_id="S0001",
        file_id="F0001",
        pair_id="P0001",
        line_group_id="G0001",
        left_value="101",
        right_value=None,
    )


def test_incomplete_extraction_with_zero_pairs_still_builds_page_issue(tmp_path: Path) -> None:
    payload = {
        "analysis_status": "INCOMPLETE_EXTRACTION",
        "clean_conclusion_allowed": False,
        "incomplete_page_count": 1,
        "incomplete_sheet_ids": ["S0001"],
        "failure_code_counts": {"ZERO_PRIMITIVES": 1, "KEY_ENTITIES_MISSING": 1},
        "pages": [
            {
                "sheet": "S0001",
                "file": "F0001",
                "filename": "01.dwg",
                "status": "INCOMPLETE_EXTRACTION",
                "failure_codes": ["ZERO_PRIMITIVES", "KEY_ENTITIES_MISSING"],
                "primitive_counts": {"text": 0, "line": 0, "block": 0, "polyline": 0, "total": 0},
                "warning_codes": ["read_dxf_failed"],
                "audit_disposition": "audit_required",
                "audit_role": "primary",
                "executed_extractor": None,
            }
        ],
    }
    (tmp_path / "extraction_completeness.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    issues = build_incomplete_extraction_issues(tmp_path, [], [_page()])

    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_id == "DQE0001"
    assert issue.rule_id == DATA_QUALITY_RULE_ID
    assert issue.issue_type == DATA_QUALITY_RULE_ID
    assert issue.status == "review"
    assert issue.pair_id is None
    assert issue.evidence["failure_codes"] == ["ZERO_PRIMITIVES", "KEY_ENTITIES_MISSING"]
    assert issue.evidence["primitive_count"] == 0
    assert issue.evidence["warnings"] == ["read_dxf_failed"]
    assert issue.evidence["audit_scope"]["audit_disposition"] == "audit_required"
    assert "重新执行" in (issue.recommended_action or "")


def test_complete_extraction_and_legacy_missing_artifact_build_no_issue(tmp_path: Path) -> None:
    assert build_incomplete_extraction_issues(tmp_path, [], [_page()]) == []
    (tmp_path / "extraction_completeness.json").write_text(
        json.dumps({"analysis_status": "COMPLETE", "clean_conclusion_allowed": True, "pages": []}),
        encoding="utf-8",
    )
    assert build_incomplete_extraction_issues(tmp_path, [], [_page()]) == []


def test_data_quality_issue_id_does_not_collide_with_ordinary_issue(tmp_path: Path) -> None:
    (tmp_path / "extraction_completeness.json").write_text(
        json.dumps(
            {
                "status": "INCOMPLETE_EXTRACTION",
                "complete": False,
                "page_results": [
                    {
                        "sheet_id": "S0001",
                        "complete": False,
                        "failure_codes": ["CONVERSION_FAILED"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    issues = build_incomplete_extraction_issues(tmp_path, [_ordinary_issue()], [_page()])
    assert issues[0].issue_id == "DQE0001"
    assert issues[0].issue_id != "I0001"


def test_corrupt_extraction_completeness_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "extraction_completeness.json"
    artifact.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid extraction completeness artifact"):
        build_incomplete_extraction_issues(tmp_path, [], [_page()])
