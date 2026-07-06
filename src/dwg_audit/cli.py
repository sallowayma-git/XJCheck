from __future__ import annotations

from pathlib import Path
import json

import typer

from dwg_audit.desktop import DesktopEventWriter
from dwg_audit.desktop import analyze_session as run_desktop_session
from dwg_audit.desktop import list_recent_projects as load_recent_projects
from dwg_audit.desktop import load_project_result as load_desktop_project_result
from dwg_audit.desktop import purge_session as purge_desktop_session
from dwg_audit.desktop import render_project_preview
from dwg_audit.desktop import update_issue_status as update_desktop_issue_status
from dwg_audit.pipeline import analyze_input_root
from dwg_audit.report import compare_project_regressions
from dwg_audit.report import evaluate_acceptance_project
from dwg_audit.report import export_existing_reports
from dwg_audit.report import rerun_audit_from_findings
from dwg_audit.report import write_acceptance_report
from dwg_audit.report import write_regression_report
from dwg_audit.utils.config import load_config
from dwg_audit.utils.config import write_default_config
from dwg_audit.utils.logging import configure_logging


app = typer.Typer(add_completion=False, no_args_is_help=True, help="Local DWG audit toolkit.")


@app.command("init-config")
def init_config(
    output: Path = typer.Option(Path("config.yml"), "--output", "-o"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    try:
        path = write_default_config(output, force=force)
    except FileExistsError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Default config written to {path}")


@app.command("analyze-project")
def analyze_project(
    input_path: Path = typer.Option(..., "--input", "-i", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    output_path: Path = typer.Option(..., "--output", "-o", file_okay=False, dir_okay=True, resolve_path=True),
    config_path: Path | None = typer.Option(None, "--config", "-c", exists=True, resolve_path=True),
) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    logger = configure_logging(output_path / "logs" / "analyze.log")
    config = load_config(config_path)
    written = analyze_input_root(input_path, output_path, config, logger)
    typer.echo("Analysis completed:")
    for path in written:
        typer.echo(f"- {path}")


@app.command("export-findings")
def export_findings(
    output_path: Path = typer.Option(..., "--output", "-o", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    projects = [path for path in output_path.iterdir() if path.is_dir() and (path / "manifest.json").exists()]
    if not projects:
        raise typer.BadParameter(f"No project outputs found under {output_path}")
    typer.echo("Findings available under:")
    for project in projects:
        typer.echo(f"- {project / 'findings'}")


@app.command("run-audit")
def run_audit(
    findings: Path = typer.Option(..., "--findings", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    output_path: Path | None = typer.Option(None, "--output", "-o", file_okay=False, dir_okay=True, resolve_path=True),
    config_path: Path | None = typer.Option(None, "--config", "-c", exists=True, resolve_path=True),
) -> None:
    project_dir = findings.parent if findings.name == "findings" else findings
    manifest_path = project_dir / "manifest.json"
    if not manifest_path.exists():
        raise typer.BadParameter(f"No manifest.json found under {project_dir}")
    config = load_config(config_path)
    audit_dir = rerun_audit_from_findings(project_dir, config, output_path)
    typer.echo(f"Audit artifacts available under {audit_dir}")


@app.command("export-report")
def export_report(
    artifacts: Path | None = typer.Option(None, "--artifacts", "-a", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    audit: Path | None = typer.Option(None, "--audit", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    fmt: str = typer.Option("xlsx,html,md", "--format"),
) -> None:
    target = artifacts
    if audit is not None:
        target = audit.parent if audit.name == "audit" else audit
    if target is None:
        raise typer.BadParameter("Provide either --artifacts or --audit")
    manifest_path = target / "manifest.json"
    if not manifest_path.exists():
        raise typer.BadParameter(f"No manifest.json found under {target}")
    try:
        export_existing_reports(target, formats=fmt)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Reports re-exported under {target / 'audit'} in formats: {fmt}")


@app.command("serve-ui")
def serve_ui(
    artifacts: Path = typer.Option(..., "--artifacts", "-a", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    typer.echo(
        "Run this command from your shell:\n"
        f"streamlit run {Path(__file__).resolve().parent / 'ui' / 'app.py'} -- --artifacts {artifacts}"
    )


@app.command("serve")
def serve(
    project: Path = typer.Option(..., "--project", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    typer.echo(
        "Run this command from your shell:\n"
        f"streamlit run {Path(__file__).resolve().parent / 'ui' / 'app.py'} -- --artifacts {project}"
    )


@app.command("compare-regression")
def compare_regression(
    baseline: Path = typer.Option(..., "--baseline", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    current: Path = typer.Option(..., "--current", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    output_path: Path = typer.Option(..., "--output", "-o", file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    for project_dir in (baseline, current):
        manifest_path = project_dir / "manifest.json"
        if not manifest_path.exists():
            raise typer.BadParameter(f"No manifest.json found under {project_dir}")
    write_regression_report(baseline, current, output_path)
    comparison = compare_project_regressions(baseline, current)
    typer.echo("Regression comparison completed:")
    typer.echo(f"- pair_count delta: {comparison['delta']['pair_count']}")
    typer.echo(f"- issue_count delta: {comparison['delta']['issue_count']}")
    typer.echo(f"- report_dir: {output_path}")


@app.command("evaluate-acceptance")
def evaluate_acceptance(
    project: Path = typer.Option(..., "--project", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    spec: Path = typer.Option(..., "--spec", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    output_path: Path | None = typer.Option(None, "--output", "-o", file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    manifest_path = project / "manifest.json"
    if not manifest_path.exists():
        raise typer.BadParameter(f"No manifest.json found under {project}")
    if output_path is None:
        output_path = project / "acceptance"
    write_acceptance_report(project, spec, output_path)
    evaluation = evaluate_acceptance_project(project, spec)
    typer.echo("Acceptance evaluation completed:")
    typer.echo(f"- pair_precision: {evaluation['pair_metrics']['precision']}")
    typer.echo(f"- pair_recall: {evaluation['pair_metrics']['recall']}")
    typer.echo(f"- acceptance_passed: {evaluation['acceptance_passed']}")
    typer.echo(f"- report_dir: {output_path}")


@app.command("analyze-session")
def analyze_session(
    input_path: Path = typer.Option(..., "--input", "-i", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    workspace_root: Path = typer.Option(Path(".desktop_workspace"), "--workspace-root", file_okay=False, dir_okay=True, resolve_path=True),
    session_id: str | None = typer.Option(None, "--session-id"),
    config_path: Path | None = typer.Option(None, "--config", "-c", exists=True, resolve_path=True),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
    include_audit: bool = typer.Option(True, "--include-audit/--skip-audit"),
) -> None:
    runs = run_desktop_session(
        input_root=input_path,
        workspace_root=workspace_root,
        config_path=config_path,
        session_id=session_id,
        include_audit=include_audit,
        state_db_path=state_db,
        event_writer=DesktopEventWriter(),
    )
    typer.echo(json.dumps({"event": "run_result", "projects": runs}, ensure_ascii=False))


@app.command("list-recent-projects")
def list_recent_projects(
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
    limit: int = typer.Option(20, "--limit", min=1, max=200),
) -> None:
    typer.echo(
        json.dumps(
            {
                "projects": load_recent_projects(state_db_path=state_db, limit=limit),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("load-result")
def load_result(
    project_id: str = typer.Option(..., "--project-id"),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    result = load_desktop_project_result(project_id=project_id, state_db_path=state_db)
    if result is None:
        raise typer.BadParameter(f"No stored result found for project_id={project_id}")
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("set-issue-status")
def set_issue_status(
    project_id: str = typer.Option(..., "--project-id"),
    issue_id: str = typer.Option(..., "--issue-id"),
    status: str = typer.Option(..., "--status"),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    try:
        payload = update_desktop_issue_status(
            project_id=project_id,
            issue_id=issue_id,
            status=status,
            state_db_path=state_db,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("purge-session")
def purge_session(
    session_id: str = typer.Option(..., "--session-id"),
    workspace_root: Path = typer.Option(Path(".desktop_workspace"), "--workspace-root", file_okay=False, dir_okay=True, resolve_path=True),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    typer.echo(
        json.dumps(
            purge_desktop_session(
                session_id=session_id,
                workspace_root=workspace_root,
                state_db_path=state_db,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("render-preview")
def render_preview(
    project_id: str = typer.Option(..., "--project-id"),
    sheet_id: str | None = typer.Option(None, "--sheet-id"),
    issue_id: str | None = typer.Option(None, "--issue-id"),
    line_group_id: str | None = typer.Option(None, "--line-group-id"),
    output_dir: Path | None = typer.Option(None, "--output-dir", file_okay=False, dir_okay=True, resolve_path=True),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    try:
        payload = render_project_preview(
            project_id=project_id,
            sheet_id=sheet_id,
            issue_id=issue_id,
            line_group_id=line_group_id,
            output_dir=output_dir,
            state_db_path=state_db,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def run() -> None:
    app()


if __name__ == "__main__":
    run()
