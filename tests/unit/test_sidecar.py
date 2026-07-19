from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest
import dwg_audit.desktop.preview as preview_module

from dwg_audit.desktop.sidecar import DesktopEventWriter
from dwg_audit.desktop.sidecar import analyze_session
from dwg_audit.desktop.sidecar import load_project_result
from dwg_audit.desktop.sidecar import list_recent_projects
from dwg_audit.desktop.sidecar import purge_session
from dwg_audit.desktop.preview import render_project_preview
from dwg_audit.desktop.sidecar import update_issue_status
from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.services import AnalysisRunResult


def test_analyze_session_emits_events_and_stores_project_result(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    state_db = tmp_path / "desktop_state.db"
    input_root.mkdir()
    project_dir = workspace_root / "session-a" / "demo_project"
    _write_project_output(project_dir)

    def fake_run_analysis_workflow(**kwargs):
        assert kwargs["input_root"] == input_root.resolve()
        assert kwargs["output_root"] == (workspace_root / "session-a").resolve()
        assert kwargs["include_audit"] is True
        assert kwargs["log_path"] == workspace_root / "session-a" / "logs" / "desktop_session.log"
        kwargs["event_sink"].emit("progress", stage="pair", pair_count=2)
        kwargs["on_project_artifacts_ready"](project_dir)
        kwargs["event_sink"].emit("audit_finished", project_dir=str(project_dir), issue_count=1)
        return AnalysisRunResult(
            input_root=kwargs["input_root"],
            output_root=kwargs["output_root"],
            project_dirs=[project_dir],
            audit_dirs=[project_dir / "audit"],
            config_path=None,
            run_summary_path=workspace_root / "session-a" / "run_summary.json",
            config={"demo": True},
        )

    monkeypatch.setattr("dwg_audit.desktop.sidecar.run_analysis_workflow", fake_run_analysis_workflow)

    stream = StringIO()
    runs = analyze_session(
        input_root=input_root,
        workspace_root=workspace_root,
        session_id="session-a",
        state_db_path=state_db,
        event_writer=DesktopEventWriter(stream),
    )

    assert runs[0]["project_id"] == "demo-project"
    recent = list_recent_projects(state_db_path=state_db)
    assert len(recent) == 1
    assert recent[0]["project_name"] == "Demo Project"
    result = load_project_result(project_id="demo-project", state_db_path=state_db)
    assert result is not None
    assert result["run"]["project_name"] == "Demo Project"
    assert result["issues"][0]["rule_id"] == "R-PAIR-LOW-CONFIDENCE"
    assert result["issues"][0]["issue_type"] == "pair_low_confidence"
    assert result["issues"][0]["summary"] == "Low confidence pair"
    assert result["issues"][0]["evidence_refs"] == [{"pair_id": "P2", "filename": "01.dwg", "sheet_no": "01"}]
    assert result["page_findings"][0]["sheet_id"] == "S1"
    assert result["page_findings"][0]["page_type"] == "二次原理图"
    assert result["page_findings"][0]["route_target"] == "WireDiagramExtractor"
    assert result["page_findings"][0]["open_questions"] == ["Need manual review for ambiguous right-side labels."]

    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert lines[0]["event"] == "run_started"
    assert any(line["event"] == "project_stored" for line in lines)
    assert lines[-1]["event"] == "run_finished"


def test_analyze_session_discards_workspace_when_workflow_fails(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    input_root.mkdir()

    def fail_workflow(**_kwargs):
        raise RuntimeError("conversion failed")

    monkeypatch.setattr("dwg_audit.desktop.sidecar.run_analysis_workflow", fail_workflow)

    with pytest.raises(RuntimeError, match="conversion failed"):
        analyze_session(
            input_root=input_root,
            workspace_root=workspace_root,
            session_id="failed-session",
            state_db_path=tmp_path / "desktop_state.db",
            event_writer=DesktopEventWriter(StringIO()),
        )

    assert not (workspace_root / "failed-session").exists()


def test_purge_session_removes_workspace_and_state_rows(tmp_path: Path) -> None:
    session_id = "session-z"
    workspace_root = tmp_path / "workspace"
    state_db = tmp_path / "desktop_state.db"
    workspace_dir = workspace_root / session_id
    workspace_dir.mkdir(parents=True)

    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="session-z:demo-project",
        session_id=session_id,
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(workspace_dir / "demo_project"),
        status="completed",
        sheet_count=1,
        pair_count=2,
        issue_count=1,
        metadata={"demo": True},
    )
    store.replace_issue_summaries(
        "session-z:demo-project",
        [
            {
                "issue_id": "I1",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "issue_type": "pair_low_confidence",
                "title": "Low Confidence",
                "summary": "Low confidence pair",
                "explanation": "Pair score is below the automatic pass threshold.",
                "recommended_action": "Review both endpoint labels.",
                "severity": "review",
                "status": "open",
                "confidence": 0.74,
                "sheet_id": "S1",
                "file_id": "F1",
                "filename": "01.dwg",
                "sheet_no": "01",
                "line_group_id": "G1",
                "left_value": "101",
                "right_value": "201",
                "primary_pair_id": "P2",
                "one_to_many_classification": "",
                "evidence": {"filename": "01.dwg"},
                "evidence_refs": [{"pair_id": "P2", "filename": "01.dwg", "sheet_no": "01"}],
                "related_pair_ids": ["P3"],
                "sheet_ids": ["S1"],
                "values": ["101", "201"],
            }
        ],
    )

    result = purge_session(session_id=session_id, workspace_root=workspace_root, state_db_path=state_db)

    assert result["deleted_runs"] == 1
    assert result["removed_workspace"] is True
    assert not workspace_dir.exists()
    assert list_recent_projects(state_db_path=state_db) == []


def test_render_project_preview_writes_svg_with_issue_highlight(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    artifact_dir = tmp_path / "artifacts" / "demo_project"
    _write_preview_project_output(artifact_dir)

    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(artifact_dir),
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={"demo": True},
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    preview_path = Path(preview["preview_path"])
    assert preview_path.exists()
    svg = preview_path.read_text(encoding="utf-8")
    assert "<svg" in svg
    assert "id=\"issue-highlight\"" in svg
    assert "view=issue-crop" in svg
    assert "sheet=01" in svg
    assert preview.get("cropped_to_issue") is True
    assert isinstance(preview.get("focus_bbox"), list)
    assert len(preview["focus_bbox"]) == 4


def test_render_project_preview_reads_only_rendering_frames(monkeypatch, tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    artifact_dir = tmp_path / "artifacts" / "demo_project"
    _write_preview_project_output(artifact_dir)
    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(artifact_dir),
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={},
    )
    requested: list[tuple[str, ...] | None] = []
    original = preview_module.load_report_frames

    def spy_load_report_frames(path: Path, names=None):
        requested.append(tuple(names) if names is not None else None)
        return original(path, names=names)

    monkeypatch.setattr(preview_module, "load_report_frames", spy_load_report_frames)

    preview = render_project_preview(
        project_id="demo-project",
        sheet_id="S1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    assert Path(preview["preview_path"]).exists()
    assert requested == [("issues", "pages", "lines", "texts", "line_groups")]


def test_render_project_preview_prefers_explicit_line_group_override(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    artifact_dir = tmp_path / "artifacts" / "demo_project"
    _write_preview_project_output(artifact_dir)

    line_groups_path = artifact_dir / "findings" / "line_groups.parquet"
    line_groups = pd.read_parquet(line_groups_path)
    line_groups = pd.concat(
        [
            line_groups,
            pd.DataFrame(
                [
                    {
                        "line_group_id": "G2",
                        "sheet_id": "S1",
                        "file_id": "F1",
                        "start_x": 10.0,
                        "start_y": 50.0,
                        "end_x": 90.0,
                        "end_y": 50.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    line_groups.to_parquet(line_groups_path, index=False)

    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(artifact_dir),
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={"demo": True},
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        line_group_id="G2",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    svg = Path(preview["preview_path"]).read_text(encoding="utf-8")
    assert "id=\"issue-highlight\"" in svg
    assert "view=issue-crop" in svg
    # Cropped canvas is fixed-size; highlight must still draw the override segment endpoints.
    assert "stroke=\"#b02d20\"" in svg
    assert preview.get("cropped_to_issue") is True


def test_update_issue_status_syncs_state_store_and_audit_files(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    artifact_dir = tmp_path / "artifacts" / "demo_project"
    _write_preview_project_output(artifact_dir)

    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(artifact_dir),
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={"demo": True},
    )
    store.replace_issue_summaries(
        "session-a:demo-project",
        [
            {
                "issue_id": "I1",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "issue_type": "pair_low_confidence",
                "title": "Low Confidence",
                "summary": "Low confidence pair",
                "explanation": "Pair score is below the automatic pass threshold.",
                "recommended_action": "Review both endpoint labels.",
                "severity": "review",
                "status": "open",
                "confidence": 0.74,
                "sheet_id": "S1",
                "file_id": "F1",
                "filename": "01.dwg",
                "sheet_no": "01",
                "line_group_id": "G1",
                "left_value": "101",
                "right_value": "201",
                "primary_pair_id": "P1",
                "one_to_many_classification": "review",
                "evidence": {"filename": "01.dwg", "sheet_no": "01"},
                "evidence_refs": [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}],
                "related_pair_ids": ["P2"],
                "sheet_ids": ["S1", "S2"],
                "values": ["101", "201", "202"],
            }
        ],
    )

    payload = update_issue_status(
        project_id="demo-project",
        issue_id="I1",
        status="resolved",
        state_db_path=state_db,
    )

    assert payload["status"] == "resolved"
    assert payload["issue"]["one_to_many_classification"] == "review"
    assert payload["issue"]["evidence_refs"] == [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}]
    refreshed = load_project_result(project_id="demo-project", state_db_path=state_db)
    assert refreshed is not None
    assert refreshed["issues"][0]["status"] == "resolved"
    assert refreshed["issues"][0]["related_pair_ids"] == ["P2"]

    audit_frame = pd.read_parquet(artifact_dir / "audit" / "issues.parquet")
    assert audit_frame.loc[audit_frame["issue_id"].astype(str) == "I1", "status"].iloc[0] == "resolved"
    audit_payload = json.loads((artifact_dir / "audit" / "issues.json").read_text(encoding="utf-8"))
    assert audit_payload[0]["status"] == "resolved"


def _write_project_output(project_dir: Path) -> None:
    findings = project_dir / "findings"
    audit = project_dir / "audit"
    findings.mkdir(parents=True, exist_ok=True)
    audit.mkdir(parents=True, exist_ok=True)

    (project_dir / "manifest.json").write_text(
        json.dumps(
            {
                "project_name": "Demo Project",
                "project_id": "demo-project",
                "sheet_count": 1,
                "file_count": 1,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (findings / "findings.json").write_text(
        json.dumps(
            {
                "page_findings_count": 1,
                "page_findings": [
                    {
                        "sheet_id": "S1",
                        "file_id": "F1",
                        "filename": "01.dwg",
                        "sheet_no": "01",
                        "sheet_order": 1,
                        "sheet_title": "交流回路图1",
                        "page_type": "二次原理图",
                        "page_type_confidence": 0.9,
                        "audit_role": "primary",
                        "route_target": "WireDiagramExtractor",
                        "layout_summary": {"layout_name": "Model"},
                        "structure_summary": {"line_group_count": 2, "pair_count": 2},
                        "recognition_strategy": "Use wire-diagram routing.",
                        "number_matching_strategy": "Use horizontal line groups and endpoint windows.",
                        "high_confidence_signals": ["Two non-discard pairs found."],
                        "open_questions": ["Need manual review for ambiguous right-side labels."],
                        "warnings": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "pair_id": "P1",
                "status": "pass",
                "confidence_bucket": "high",
                "confidence": 0.97,
                "left_value": "101",
                "right_value": "201",
            },
            {
                "pair_id": "P2",
                "status": "review",
                "confidence_bucket": "review",
                "confidence": 0.74,
                "left_value": "102",
                "right_value": "202",
            },
        ]
    ).to_parquet(findings / "pairs.parquet", index=False)
    pd.DataFrame(
        [
            {
                "issue_id": "I1",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "issue_type": "pair_low_confidence",
                "title": "Low Confidence",
                "message": "Low confidence pair",
                "summary": "Low confidence pair",
                "explanation": "Pair score is below the automatic pass threshold.",
                "recommended_action": "Review both endpoint labels.",
                "severity": "review",
                "status": "open",
                "confidence": 0.74,
                "sheet_id": "S1",
                "file_id": "F1",
                "line_group_id": "G1",
                "left_value": "102",
                "right_value": "202",
                "primary_pair_id": "P2",
                "related_pair_ids": json.dumps(["P3"], ensure_ascii=False),
                "sheet_ids": json.dumps(["S1"], ensure_ascii=False),
                "values": json.dumps(["102", "202"], ensure_ascii=False),
                "evidence_refs": json.dumps([{"pair_id": "P2", "filename": "01.dwg", "sheet_no": "01"}], ensure_ascii=False),
                "evidence": json.dumps({"filename": "01.dwg", "sheet_no": "01", "one_to_many_classification": "review"}, ensure_ascii=False),
            }
        ]
    ).to_parquet(audit / "issues.parquet", index=False)


def _write_preview_project_output(project_dir: Path) -> None:
    findings = project_dir / "findings"
    audit = project_dir / "audit"
    findings.mkdir(parents=True, exist_ok=True)
    audit.mkdir(parents=True, exist_ok=True)

    (project_dir / "manifest.json").write_text(
        json.dumps(
            {
                "project_name": "Demo Project",
                "project_id": "demo-project",
                "sheet_count": 1,
                "file_count": 1,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                "sheet_id": "S1",
                "file_id": "F1",
                "filename": "01.dwg",
                "sheet_order": 1,
                "sheet_no": "01",
                "sheet_title": "Demo Sheet",
                "audit_role": "primary",
                "page_no_source": "filename",
                "is_primary_audit_candidate": True,
                "extent_bbox": json.dumps([0, 0, 120, 80], ensure_ascii=False),
                "frame_bbox": json.dumps([0, 0, 120, 80], ensure_ascii=False),
                "audit_area_bbox": json.dumps([0, 0, 120, 80], ensure_ascii=False),
            }
        ]
    ).to_parquet(findings / "pages.parquet", index=False)
    pd.DataFrame(
        [
            {
                "line_id": "L1",
                "sheet_id": "S1",
                "file_id": "F1",
                "start_x": 10.0,
                "start_y": 20.0,
                "end_x": 90.0,
                "end_y": 20.0,
            }
        ]
    ).to_parquet(findings / "lines.parquet", index=False)
    pd.DataFrame(
        [
            {
                "text_id": "T1",
                "sheet_id": "S1",
                "file_id": "F1",
                "text": "101",
                "normalized_text": "101",
                "is_numeric_candidate": True,
                "height": 2.5,
                "insert_x": 15.0,
                "insert_y": 22.0,
            }
        ]
    ).to_parquet(findings / "texts.parquet", index=False)
    pd.DataFrame(
        [
            {
                "line_group_id": "G1",
                "sheet_id": "S1",
                "file_id": "F1",
                "start_x": 10.0,
                "start_y": 20.0,
                "end_x": 90.0,
                "end_y": 20.0,
            }
        ]
    ).to_parquet(findings / "line_groups.parquet", index=False)
    pd.DataFrame(
        [
            {
                "issue_id": "I1",
                "sheet_id": "S1",
                "line_group_id": "G1",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "status": "open",
                "title": "Low Confidence",
                "evidence": json.dumps(
                    {
                        "filename": "01.dwg",
                        "sheet_no": "01",
                        "line_start": [10.0, 20.0],
                        "line_end": [90.0, 20.0],
                    },
                    ensure_ascii=False,
                ),
            }
        ]
    ).to_parquet(audit / "issues.parquet", index=False)
