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
