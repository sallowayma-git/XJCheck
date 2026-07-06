import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from dwg_audit.cli import app


def test_init_config_writes_file(tmp_path: Path) -> None:
    runner = CliRunner()
    target = tmp_path / "config.yml"

    result = runner.invoke(app, ["init-config", "--output", str(target)])

    assert result.exit_code == 0
    assert target.exists()
    assert "project:" in target.read_text(encoding="utf-8")


def test_help_lists_taskbook_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init-config" in result.stdout
    assert "analyze-project" in result.stdout
    assert "export-findings" in result.stdout
    assert "run-audit" in result.stdout
    assert "export-report" in result.stdout
    assert "analyze-session" in result.stdout
    assert "list-recent-projects" in result.stdout
    assert "load-result" in result.stdout
    assert "set-issue-status" in result.stdout
    assert "render-preview" in result.stdout
    assert "purge-session" in result.stdout
    assert "serve" in result.stdout


def test_export_findings_lists_project_findings(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "demo_project"
    findings = project / "findings"
    findings.mkdir(parents=True)
    (project / "manifest.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(app, ["export-findings", "--output", str(tmp_path)])

    assert result.exit_code == 0
    assert str(findings) in result.stdout


def test_run_audit_generates_audit_from_findings_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    findings = tmp_path / "demo_project" / "findings"
    findings.mkdir(parents=True)
    (findings.parent / "manifest.json").write_text('{"project_name": "demo"}', encoding="utf-8")
    (findings / "findings.json").write_text("{}", encoding="utf-8")
    (findings / "findings.md").write_text("# Findings\n", encoding="utf-8")

    audit_dir = findings.parent / "audit"
    assert not audit_dir.exists()

    result = runner.invoke(app, ["run-audit", "--findings", str(findings)])

    assert result.exit_code == 0
    assert str(audit_dir) in result.stdout
    assert (audit_dir / "issues.json").exists()
    assert (audit_dir / "audit_report.md").exists()


def test_serve_outputs_streamlit_command(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "artifacts"
    project.mkdir()

    result = runner.invoke(app, ["serve", "--project", str(project)])

    assert result.exit_code == 0
    assert "streamlit run" in result.stdout
    assert str(project) in result.stdout


def test_export_report_passes_requested_formats(tmp_path: Path) -> None:
    runner = CliRunner()
    project = tmp_path / "demo_project"
    findings = project / "findings"
    audit = project / "audit"
    findings.mkdir(parents=True)
    audit.mkdir()
    (project / "manifest.json").write_text('{"project_name": "demo"}', encoding="utf-8")
    pd.DataFrame([{"pair_id": "P1", "status": "pass"}]).to_parquet(findings / "pairs.parquet", index=False)
    pd.DataFrame([{"file_id": "F1", "filename": "a.dwg"}]).to_parquet(findings / "source_files.parquet", index=False)
    pd.DataFrame([{"issue_id": "I1", "rule_id": "R1", "severity": "review", "status": "open"}]).to_parquet(
        audit / "issues.parquet",
        index=False,
    )

    result = runner.invoke(app, ["export-report", "--artifacts", str(project), "--format", "md"])

    assert result.exit_code == 0, result.output
    assert (audit / "audit_report.md").exists()
    assert not (audit / "audit_report.html").exists()
    assert not (audit / "issues.xlsx").exists()


def test_compare_regression_writes_report_files(tmp_path: Path) -> None:
    runner = CliRunner()
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    output = tmp_path / "regression"
    for project_dir, pair_count, issue_rules in (
        (baseline, 2, ["R-CROSS-PAGE-CONFLICT"]),
        (current, 3, ["R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY"]),
    ):
        findings = project_dir / "findings"
        audit = project_dir / "audit"
        findings.mkdir(parents=True)
        audit.mkdir()
        (project_dir / "manifest.json").write_text(f'{{"project_name": "{project_dir.name}", "project_id": "{project_dir.name}"}}', encoding="utf-8")
        pd.DataFrame([{"pair_id": f"P{index}", "status": "pass"} for index in range(pair_count)]).to_parquet(findings / "pairs.parquet", index=False)
        pd.DataFrame([{"issue_id": f"I{index}", "rule_id": rule_id, "status": "open"} for index, rule_id in enumerate(issue_rules, start=1)]).to_parquet(
            audit / "issues.parquet",
            index=False,
        )

    result = runner.invoke(
        app,
        ["compare-regression", "--baseline", str(baseline), "--current", str(current), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert (output / "regression_report.json").exists()
    assert (output / "regression_report.md").exists()
    assert "pair_count delta: 1" in result.stdout
    assert "issue_count delta: 1" in result.stdout


def test_list_recent_projects_cli_reads_state_db(tmp_path: Path) -> None:
    runner = CliRunner()
    state_db = tmp_path / "desktop_state.db"

    from dwg_audit.desktop.state_store import DesktopStateStore

    DesktopStateStore(state_db).record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(tmp_path / "workspace" / "session-a" / "demo_project"),
        status="completed",
        sheet_count=1,
        pair_count=2,
        issue_count=1,
        metadata={"demo": True},
    )

    result = runner.invoke(app, ["list-recent-projects", "--state-db", str(state_db)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["projects"][0]["project_id"] == "demo-project"


def test_load_result_cli_returns_project_payload(tmp_path: Path) -> None:
    runner = CliRunner()
    state_db = tmp_path / "desktop_state.db"

    from dwg_audit.desktop.state_store import DesktopStateStore

    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(tmp_path / "workspace" / "session-a" / "demo_project"),
        status="completed",
        sheet_count=1,
        pair_count=2,
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
                "evidence": {"filename": "01.dwg"},
                "evidence_refs": [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}],
                "related_pair_ids": ["P2"],
                "sheet_ids": ["S1"],
                "values": ["101", "201"],
            }
        ],
    )

    result = runner.invoke(app, ["load-result", "--project-id", "demo-project", "--state-db", str(state_db)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["run"]["project_id"] == "demo-project"
    assert payload["issues"][0]["issue_id"] == "I1"
    assert payload["issues"][0]["issue_type"] == "pair_low_confidence"
    assert payload["issues"][0]["related_pair_ids"] == ["P2"]
    assert payload["issues"][0]["evidence_refs"] == [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}]


def test_analyze_session_cli_emits_final_result_line(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    def fake_analyze_session(**kwargs):
        kwargs["event_writer"].emit("run_started", session_id="session-a")
        return [{"project_id": "demo-project", "project_name": "Demo Project"}]

    monkeypatch.setattr("dwg_audit.cli.run_desktop_session", fake_analyze_session)

    input_root = tmp_path / "input"
    input_root.mkdir()

    result = runner.invoke(app, ["analyze-session", "--input", str(input_root), "--workspace-root", str(tmp_path / "workspace")])

    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines[0]["event"] == "run_started"
    assert lines[-1]["event"] == "run_result"
    assert lines[-1]["projects"][0]["project_id"] == "demo-project"


def test_render_preview_cli_returns_preview_payload(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    preview_path = tmp_path / "preview.svg"
    captured: dict[str, object] = {}

    def fake_render_project_preview(**kwargs):
        captured.update(kwargs)
        return {"project_id": "demo-project", "preview_path": str(preview_path)}

    monkeypatch.setattr("dwg_audit.cli.render_project_preview", fake_render_project_preview)

    result = runner.invoke(
        app,
        ["render-preview", "--project-id", "demo-project", "--issue-id", "I1", "--line-group-id", "G2"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["project_id"] == "demo-project"
    assert payload["preview_path"] == str(preview_path)
    assert captured["line_group_id"] == "G2"


def test_set_issue_status_cli_returns_updated_payload(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(
        "dwg_audit.cli.update_desktop_issue_status",
        lambda **kwargs: {"project_id": "demo-project", "issue_id": "I1", "status": "resolved"},
    )

    result = runner.invoke(
        app,
        ["set-issue-status", "--project-id", "demo-project", "--issue-id", "I1", "--status", "resolved"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["issue_id"] == "I1"
    assert payload["status"] == "resolved"
