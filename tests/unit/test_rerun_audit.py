from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.domain.models import Issue
from dwg_audit.report.rerun import rerun_audit_from_findings


def _sample_frames() -> dict[str, pd.DataFrame]:
    return {
        "pages": pd.DataFrame(
            [
                {
                    "sheet_id": "S0001",
                    "file_id": "F0001",
                    "filename": "04.dwg",
                    "sheet_order": 4,
                    "sheet_no": "04",
                    "sheet_title": "交流回路图1",
                    "sheet_category": "二次原理图",
                    "audit_role": "primary",
                    "page_no_source": "filename",
                    "is_primary_audit_candidate": True,
                    "source_refs": json.dumps(["filename"]),
                    "warnings": json.dumps([]),
                    "layout_name": None,
                    "drawing_units": None,
                    "extent_bbox": json.dumps([0.0, 0.0, 100.0, 100.0]),
                    "frame_bbox": json.dumps([1.0, 1.0, 99.0, 99.0]),
                    "title_block_bbox": None,
                    "audit_area_bbox": None,
                }
            ]
        ),
        "line_groups": pd.DataFrame(
            [
                {
                    "line_group_id": "G0001",
                    "sheet_id": "S0001",
                    "file_id": "F0001",
                    "start_x": 10.0,
                    "start_y": 20.0,
                    "end_x": 40.0,
                    "end_y": 20.0,
                    "length": 30.0,
                    "wire_candidate_score": 0.95,
                    "member_line_ids": json.dumps(["L1", "L2"]),
                    "layer_hints": json.dumps(["WIRE"]),
                }
            ]
        ),
        "pairs": pd.DataFrame(
            [
                {
                    "pair_id": "P0001",
                    "line_group_id": "G0001",
                    "sheet_id": "S0001",
                    "file_id": "F0001",
                    "selected_pair_candidate_id": "PC0001",
                    "left_value": "101",
                    "right_value": "201",
                    "confidence": 0.91,
                    "status": "review",
                    "rationale": "manual check",
                    "alternative_pair_candidate_ids": json.dumps(["PC0002"]),
                    "confidence_bucket": "medium",
                    "evidence": json.dumps({"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4}),
                    "left_candidate_id": "C0001",
                    "right_candidate_id": "C0002",
                    "left_text_id": "T0001",
                    "right_text_id": "T0002",
                    "left_coord_x": 10.0,
                    "left_coord_y": 20.0,
                    "right_coord_x": 40.0,
                    "right_coord_y": 20.0,
                }
            ]
        ),
        "terminal_candidates": pd.DataFrame(
            [
                {
                    "candidate_id": "C0001",
                    "line_group_id": "G0001",
                    "sheet_id": "S0001",
                    "file_id": "F0001",
                    "side": "left",
                    "text_id": "T0001",
                    "text": "101",
                    "value": "101",
                    "score": 0.95,
                    "status": "accepted",
                    "rejection_reason": None,
                    "endpoint_x": 10.0,
                    "endpoint_y": 20.0,
                    "distance_x": 1.0,
                    "distance_y": 0.0,
                    "text_insert_x": 10.0,
                    "text_insert_y": 20.0,
                    "vertical_alignment_score": 1.0,
                    "horizontal_side_score": 0.95,
                    "text_type_score": 1.0,
                    "height_score": 1.0,
                    "rank": 1,
                }
            ]
        ),
    }


def _sample_issue() -> Issue:
    return Issue(
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
    )


def _write_report_stubs(project_dir: Path) -> None:
    audit_dir = project_dir / "audit"
    (audit_dir / "audit_report.md").write_text("# Audit Report\n", encoding="utf-8")
    (audit_dir / "audit_report.html").write_text("<html><body>report</body></html>", encoding="utf-8")
    (audit_dir / "issues.xlsx").write_bytes(b"xlsx")


def test_rerun_audit_from_findings_generates_audit_outputs(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    frames = _sample_frames()
    issue = _sample_issue()

    def fake_load_report_frames(path: Path) -> dict[str, pd.DataFrame]:
        assert path == project_dir
        return frames

    def fake_build_issues(pairs, line_groups, pages, config, terminal_candidates=None):
        assert [page.sheet_id for page in pages] == ["S0001"]
        assert [group.line_group_id for group in line_groups] == ["G0001"]
        assert [pair.pair_id for pair in pairs] == ["P0001"]
        assert pairs[0].left_text_id == "T0001"
        assert pairs[0].left_coord_x == 10.0
        assert [candidate.candidate_id for candidate in terminal_candidates] == ["C0001"]
        assert terminal_candidates[0].text_insert_x == 10.0
        assert terminal_candidates[0].vertical_alignment_score == 1.0
        assert terminal_candidates[0].rank == 1
        assert config == {"audit": {"strict": True}}
        return [issue]

    def fake_export_existing_reports(path: Path) -> None:
        assert path == project_dir
        audit_dir = project_dir / "audit"
        assert (audit_dir / "issues.parquet").exists()
        assert (audit_dir / "issues.json").exists()
        _write_report_stubs(project_dir)

    monkeypatch.setattr("dwg_audit.report.rerun.load_report_frames", fake_load_report_frames)
    monkeypatch.setattr("dwg_audit.report.rerun.build_issues", fake_build_issues)
    monkeypatch.setattr("dwg_audit.report.rerun.export_existing_reports", fake_export_existing_reports)

    result = rerun_audit_from_findings(project_dir, {"audit": {"strict": True}})

    audit_dir = project_dir / "audit"
    assert result == audit_dir
    assert (audit_dir / "issues.parquet").exists()
    assert (audit_dir / "issues.json").exists()
    assert (audit_dir / "issue_root_cause_audit.json").exists()
    assert (audit_dir / "issue_root_cause_audit.md").exists()
    assert (audit_dir / "audit_report.md").exists()
    assert (audit_dir / "audit_report.html").exists()
    assert (audit_dir / "issues.xlsx").exists()

    issues_json = json.loads((audit_dir / "issues.json").read_text(encoding="utf-8"))
    assert len(issues_json) == 1
    issue_row = issues_json[0]
    assert issue_row["issue_id"] == "I0001"
    assert issue_row["rule_id"] == "R-CROSS-PAGE-CONFLICT"
    assert issue_row["filename"] == "04.dwg"
    assert issue_row["root_cause"] == "rule_too_strict"
    assert issue_row["pair_kind"] == "ordinary_pair"
    assert issue_row["diagnostic_context"]["route_target"] is None

    issues_frame = pd.read_parquet(audit_dir / "issues.parquet")
    assert issues_frame.loc[0, "rule_id"] == "R-CROSS-PAGE-CONFLICT"
    assert issues_frame.loc[0, "root_cause"] == "rule_too_strict"
    evidence = issues_frame.loc[0, "evidence"]
    assert evidence["filename"] == issue.evidence["filename"]
    assert evidence["sheet_no"] == issue.evidence["sheet_no"]
    assert evidence["sheet_order"] == issue.evidence["sheet_order"]
    assert evidence["line_start"].tolist() == issue.evidence["line_start"]
    assert evidence["line_end"].tolist() == issue.evidence["line_end"]


def test_rerun_audit_from_findings_copies_outputs_to_output_dir(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    output_dir = tmp_path / "copied-audit"
    issue = _sample_issue()

    monkeypatch.setattr("dwg_audit.report.rerun.load_report_frames", lambda path: _sample_frames())
    monkeypatch.setattr("dwg_audit.report.rerun.build_issues", lambda pairs, line_groups, pages, config, terminal_candidates=None: [issue])
    monkeypatch.setattr("dwg_audit.report.rerun.export_existing_reports", lambda path: _write_report_stubs(path))

    result = rerun_audit_from_findings(project_dir, {}, output_dir=output_dir)

    audit_dir = project_dir / "audit"
    assert result == output_dir
    for name in (
        "issues.parquet",
        "issues.json",
        "issue_root_cause_audit.json",
        "issue_root_cause_audit.md",
        "audit_report.md",
        "audit_report.html",
        "issues.xlsx",
    ):
        assert (audit_dir / name).exists()
        assert (output_dir / name).exists()

    assert (output_dir / "issues.json").read_text(encoding="utf-8") == (audit_dir / "issues.json").read_text(encoding="utf-8")
    assert (output_dir / "issue_root_cause_audit.json").read_text(encoding="utf-8") == (
        audit_dir / "issue_root_cause_audit.json"
    ).read_text(encoding="utf-8")
    assert (output_dir / "audit_report.html").read_text(encoding="utf-8") == (audit_dir / "audit_report.html").read_text(encoding="utf-8")
    assert (output_dir / "issues.xlsx").read_bytes() == (audit_dir / "issues.xlsx").read_bytes()
