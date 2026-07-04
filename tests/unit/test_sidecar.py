from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pandas as pd

from dwg_audit.desktop.sidecar import DesktopEventWriter
from dwg_audit.desktop.sidecar import analyze_session
from dwg_audit.desktop.sidecar import load_project_result
from dwg_audit.desktop.sidecar import list_recent_projects
from dwg_audit.desktop.sidecar import purge_session
from dwg_audit.desktop.state_store import DesktopStateStore


def test_analyze_session_emits_events_and_stores_project_result(monkeypatch, tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    workspace_root = tmp_path / "workspace"
    state_db = tmp_path / "desktop_state.db"
    input_root.mkdir()
    project_dir = workspace_root / "session-a" / "demo_project"
    _write_project_output(project_dir)

    monkeypatch.setattr("dwg_audit.desktop.sidecar.load_config", lambda path: {"demo": True})
    monkeypatch.setattr("dwg_audit.desktop.sidecar.configure_logging", lambda path: object())

    def fake_analyze_input_root(input_path, output_path, config, logger, *, event_sink=None):
        assert input_path == input_root.resolve()
        assert output_path == (workspace_root / "session-a").resolve()
        if event_sink is not None:
            event_sink.emit("progress", stage="pair", pair_count=2)
        return [project_dir]

    def fake_rerun(project_path, config, output_dir=None, *, event_sink=None):
        assert project_path == project_dir
        if event_sink is not None:
            event_sink.emit("audit_finished", project_dir=str(project_path), issue_count=1)
        return project_path / "audit"

    monkeypatch.setattr("dwg_audit.desktop.sidecar.analyze_input_root", fake_analyze_input_root)
    monkeypatch.setattr("dwg_audit.desktop.sidecar.rerun_audit_from_findings", fake_rerun)

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

    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert lines[0]["event"] == "run_started"
    assert any(line["event"] == "project_stored" for line in lines)
    assert lines[-1]["event"] == "run_finished"


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
                "title": "Low Confidence",
                "severity": "review",
                "status": "open",
                "confidence": 0.74,
                "filename": "01.dwg",
                "sheet_no": "01",
                "left_value": "101",
                "right_value": "201",
                "evidence": {"filename": "01.dwg"},
            }
        ],
    )

    result = purge_session(session_id=session_id, workspace_root=workspace_root, state_db_path=state_db)

    assert result["deleted_runs"] == 1
    assert result["removed_workspace"] is True
    assert not workspace_dir.exists()
    assert list_recent_projects(state_db_path=state_db) == []


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
                "title": "Low Confidence",
                "message": "Low confidence pair",
                "severity": "review",
                "status": "open",
                "confidence": 0.74,
                "left_value": "102",
                "right_value": "202",
                "evidence": json.dumps({"filename": "01.dwg", "sheet_no": "01"}, ensure_ascii=False),
            }
        ]
    ).to_parquet(audit / "issues.parquet", index=False)
