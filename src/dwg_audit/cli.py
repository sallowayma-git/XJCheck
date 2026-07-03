from __future__ import annotations

from pathlib import Path

import typer

from dwg_audit.pipeline import analyze_input_root
from dwg_audit.report import export_existing_reports
from dwg_audit.report import rerun_audit_from_findings
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


def run() -> None:
    app()


if __name__ == "__main__":
    run()
