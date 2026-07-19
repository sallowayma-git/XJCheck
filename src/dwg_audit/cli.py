from __future__ import annotations

from pathlib import Path
import json

import typer

from dwg_audit.audit.symbol_library_review import SymbolReviewPromotionError
from dwg_audit.audit.symbol_library_review import load_symbol_review_document
from dwg_audit.audit.symbol_library_review import promote_symbol_review_document
from dwg_audit.desktop import DesktopEventWriter
from dwg_audit.desktop import analyze_session as run_desktop_session
from dwg_audit.desktop import cleanup_transient_workspaces as cleanup_desktop_workspaces
from dwg_audit.desktop import delete_project_record as delete_desktop_project_record
from dwg_audit.desktop import list_recent_projects as load_recent_projects
from dwg_audit.desktop import load_project_result as load_desktop_project_result
from dwg_audit.desktop import purge_session as purge_desktop_session
from dwg_audit.desktop import render_project_preview
from dwg_audit.desktop import update_issue_status as update_desktop_issue_status
from dwg_audit.report import compare_project_regressions
from dwg_audit.report import evaluate_corpus_census
from dwg_audit.report import evaluate_extraction_verification
from dwg_audit.report import evaluate_acceptance_project
from dwg_audit.report import evaluate_acceptance_suite
from dwg_audit.report import evaluate_hard_issue_label_pack
from dwg_audit.report import evaluate_promotion_gate
from dwg_audit.report import export_existing_reports
from dwg_audit.report import rerun_audit_from_findings
from dwg_audit.report import write_acceptance_report
from dwg_audit.report import write_acceptance_suite_report
from dwg_audit.report import write_baseline_manifest
from dwg_audit.report import write_corpus_census_artifacts
from dwg_audit.report import write_extraction_verification_artifacts
from dwg_audit.report import write_promotion_gate_evidence
from dwg_audit.report import write_regression_report
from dwg_audit.report import ElectricalConnectionReviewPackError
from dwg_audit.report import TopologyGoldPackError
from dwg_audit.report import build_topology_gold_template
from dwg_audit.report import consume_electrical_connection_review_pack
from dwg_audit.report import validate_electrical_connection_review_pack
from dwg_audit.report import validate_topology_gold_pack
from dwg_audit.report import write_electrical_connection_review_pack
from dwg_audit.services import run_analysis_workflow
from dwg_audit.utils.config import load_config
from dwg_audit.utils.config import write_default_config


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


@app.command("validate-symbol-review")
def validate_symbol_review(
    input_path: Path = typer.Option(
        ...,
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
) -> None:
    result = load_symbol_review_document(input_path)
    payload = {
        "input_path": str(input_path),
        **result.validation.to_dict(),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not result.validation.valid:
        raise typer.Exit(code=2)


@app.command("promote-symbol-review")
def promote_symbol_review(
    input_path: Path = typer.Option(
        ...,
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output_path: Path = typer.Option(
        ...,
        "--output",
        "-o",
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    force: bool = typer.Option(False, "--force"),
) -> None:
    if output_path.exists() and not force:
        raise typer.BadParameter(
            f"Output already exists: {output_path}; pass --force to replace it"
        )
    try:
        library = promote_symbol_review_document(input_path)
    except SymbolReviewPromotionError as exc:
        raise typer.BadParameter(str(exc)) from exc
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            library.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    typer.echo(f"Promoted symbol library written to {output_path}")


@app.command("build-topology-gold-template")
def build_topology_gold_template_cmd(
    project_dir: Path = typer.Option(
        ...,
        "--project",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Persisted project output containing source and extraction artifacts",
    ),
    project_id: str = typer.Option(..., "--project-id"),
    split: str = typer.Option(..., "--split"),
    output: Path = typer.Option(Path("topology_gold_pack"), "--output", "-o"),
) -> None:
    """Create a label-free, pending topology gold review pack."""

    try:
        build_topology_gold_template(
            project_dir,
            project_id=project_id,
            split=split,
            output_dir=output,
        )
    except TopologyGoldPackError as exc:
        raise typer.BadParameter(str(exc)) from exc
    validation = validate_topology_gold_pack(
        output,
        project_dir=project_dir,
        project_id=project_id,
        split=split,
    )
    payload = {"pack_dir": str(output), **validation.to_dict()}
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not validation.valid or validation.certification_ready:
        raise typer.Exit(code=2)


@app.command("validate-topology-gold")
def validate_topology_gold_cmd(
    pack_dir: Path = typer.Option(
        ...,
        "--pack",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    project_dir: Path = typer.Option(
        ...,
        "--project",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    project_id: str = typer.Option(..., "--project-id"),
    split: str = typer.Option(..., "--split"),
    require_certified: bool = typer.Option(
        False,
        "--require-certified",
        help="Return exit code 2 unless the pack is valid human-certified project gold",
    ),
) -> None:
    """Validate topology gold source binding and human-certification state."""

    validation = validate_topology_gold_pack(
        pack_dir,
        project_dir=project_dir,
        project_id=project_id,
        split=split,
    )
    payload = {"pack_dir": str(pack_dir), **validation.to_dict()}
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not validation.valid or (require_certified and not validation.certification_ready):
        raise typer.Exit(code=2)


@app.command("build-electrical-connection-review-pack")
def build_electrical_connection_review_pack_cmd(
    project_dir: Path = typer.Option(
        ...,
        "--project",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
        help="Persisted project output containing findings connection artifacts",
    ),
    project_id: str = typer.Option(..., "--project-id"),
    split: str = typer.Option(..., "--split"),
    output: Path = typer.Option(
        Path("electrical_connection_review_pack"),
        "--output",
        "-o",
    ),
    max_proposals: int = typer.Option(
        100,
        "--max-proposals",
        help="Maximum MACHINE_PROPOSED proposals retained after ranking",
    ),
) -> None:
    """Build a MACHINE_PROPOSED electrical connection review pack (never human gold)."""

    try:
        result = write_electrical_connection_review_pack(
            project_dir,
            project_id=project_id,
            split=split,
            output_dir=output,
            max_proposals=max_proposals,
        )
    except ElectricalConnectionReviewPackError as exc:
        raise typer.BadParameter(str(exc)) from exc

    validation = result["validation"]
    payload = {
        "pack_dir": result["pack_dir"],
        "proposal_count": result["summary"]["proposal_count"],
        "by_family": result["summary"]["by_family"],
        "validation": validation,
        "checklist": result["checklist_path"],
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not validation.get("valid") or validation.get("promotion_ready"):
        raise typer.Exit(code=2)


@app.command("validate-electrical-connection-review-pack")
def validate_electrical_connection_review_pack_cmd(
    pack_dir: Path = typer.Option(
        ...,
        "--pack",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    mode: str = typer.Option(
        "machine_draft",
        "--mode",
        help="machine_draft | human_decisions",
    ),
) -> None:
    """Validate a connection review pack safety contract."""

    validation = validate_electrical_connection_review_pack(pack_dir, mode=mode)
    payload = {"pack_dir": str(pack_dir), **validation.to_dict()}
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not validation.valid or validation.promotion_ready or validation.certification_ready:
        raise typer.Exit(code=2)


@app.command("consume-electrical-connection-review-pack")
def consume_electrical_connection_review_pack_cmd(
    pack_dir: Path = typer.Option(
        ...,
        "--pack",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional output directory for reviewed pack + ledger (defaults to pack)",
    ),
    reviewer: str | None = typer.Option(None, "--reviewer"),
    reviewed_at: str | None = typer.Option(
        None,
        "--reviewed-at",
        help="Timezone-aware ISO timestamp; defaults to now when decisions exist",
    ),
    require_complete: bool = typer.Option(
        False,
        "--require-complete",
        help="Exit 2 unless every proposal has a terminal human decision",
    ),
) -> None:
    """Consume human decisions into a ledger/routing summary without promoting gold."""

    try:
        result = consume_electrical_connection_review_pack(
            pack_dir,
            output_dir=output,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
            require_complete=require_complete,
        )
    except ElectricalConnectionReviewPackError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if (
        not result.get("valid")
        or result.get("promotion_ready")
        or result.get("certification_ready")
        or result.get("topology_gold_ready")
        or result.get("primary_engine_flip_ready")
    ):
        raise typer.Exit(code=2)


@app.command("analyze-project")
def analyze_project(
    input_path: Path = typer.Option(..., "--input", "-i", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    output_path: Path = typer.Option(..., "--output", "-o", file_okay=False, dir_okay=True, resolve_path=True),
    config_path: Path | None = typer.Option(None, "--config", "-c", exists=True, resolve_path=True),
) -> None:
    result = run_analysis_workflow(
        input_root=input_path,
        output_root=output_path,
        config_path=config_path,
        include_audit=False,
        log_path=output_path / "logs" / "analyze.log",
    )
    typer.echo("Analysis completed:")
    for path in result.project_dirs:
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


@app.command("freeze-baseline")
def freeze_baseline(
    project: Path = typer.Option(..., "--project", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    alias: str = typer.Option(..., "--alias"),
    input_root: Path = typer.Option(..., "--input-root", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    config_path: Path = typer.Option(..., "--config", "-c", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    arbitration: list[Path] = typer.Option([], "--arbitration", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    output_path: Path | None = typer.Option(None, "--output", "-o", file_okay=False, dir_okay=True, resolve_path=True),
    repo_root: Path = typer.Option(Path("."), "--repo-root", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    try:
        manifest_path = write_baseline_manifest(
            project,
            alias=alias,
            input_root=input_root,
            config_path=config_path,
            arbitration_paths=arbitration,
            output_dir=output_path,
            repo_root=repo_root,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Baseline manifest written to {manifest_path}")


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


@app.command(
    "evaluate-acceptance-suite",
    help="Internal acceptance harness for MVP proof over existing project artifacts.",
)
def evaluate_acceptance_suite_command(
    suite: Path = typer.Option(..., "--suite", exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    project_alias: list[str] = typer.Option([], "--project-alias"),
    output_path: Path | None = typer.Option(None, "--output", "-o", file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    alias_map: dict[str, Path] = {}
    for item in project_alias:
        if "=" not in item:
            raise typer.BadParameter("Each --project-alias must use the form alias=path")
        alias, raw_path = item.split("=", 1)
        resolved = Path(raw_path).expanduser().resolve()
        manifest_path = resolved / "manifest.json"
        if not manifest_path.exists():
            raise typer.BadParameter(f"No manifest.json found under {resolved}")
        alias_map[alias] = resolved
    if output_path is None:
        output_path = suite.parent / "acceptance_suite"
    write_acceptance_suite_report(suite, alias_map, output_path)
    suite_result = evaluate_acceptance_suite(suite, alias_map)
    typer.echo("Internal acceptance suite evaluation completed:")
    typer.echo(f"- required_passed_case_count: {suite_result['required_passed_case_count']}")
    typer.echo(f"- required_case_count: {suite_result['required_case_count']}")
    typer.echo(f"- acceptance_passed: {suite_result['acceptance_passed']}")
    typer.echo(f"- report_dir: {output_path}")


@app.command("analyze-session")
def analyze_session(
    input_path: Path = typer.Option(..., "--input", "-i", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    workspace_root: Path = typer.Option(Path(".desktop_workspace"), "--workspace-root", file_okay=False, dir_okay=True, resolve_path=True),
    session_id: str | None = typer.Option(None, "--session-id"),
    config_path: Path | None = typer.Option(None, "--config", "-c", exists=True, resolve_path=True),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
    include_audit: bool = typer.Option(True, "--include-audit/--skip-audit"),
    defer_cleanup: bool = typer.Option(False, "--defer-cleanup"),
) -> None:
    runs = run_desktop_session(
        input_root=input_path,
        workspace_root=workspace_root,
        config_path=config_path,
        session_id=session_id,
        include_audit=include_audit,
        state_db_path=state_db,
        event_writer=DesktopEventWriter(),
        compact_after_store=not defer_cleanup,
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
    run_id: str | None = typer.Option(None, "--run-id"),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    result = load_desktop_project_result(project_id=project_id, run_id=run_id, state_db_path=state_db)
    if result is None:
        raise typer.BadParameter(f"No stored result found for project_id={project_id}")
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("set-issue-status")
def set_issue_status(
    project_id: str = typer.Option(..., "--project-id"),
    issue_id: str = typer.Option(..., "--issue-id"),
    status: str = typer.Option(..., "--status"),
    run_id: str | None = typer.Option(None, "--run-id"),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    try:
        payload = update_desktop_issue_status(
            project_id=project_id,
            issue_id=issue_id,
            status=status,
            run_id=run_id,
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


@app.command("cleanup-workspaces")
def cleanup_workspaces(
    workspace_root: Path | None = typer.Option(None, "--workspace-root", file_okay=False, dir_okay=True, resolve_path=True),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    typer.echo(
        json.dumps(
            cleanup_desktop_workspaces(
                workspace_root=workspace_root,
                state_db_path=state_db,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command("delete-project-record")
def delete_project_record_cmd(
    project_id: str = typer.Option(..., "--project-id"),
    workspace_root: Path | None = typer.Option(None, "--workspace-root", file_okay=False, dir_okay=True, resolve_path=True),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    try:
        payload = delete_desktop_project_record(
            project_id=project_id,
            workspace_root=workspace_root,
            state_db_path=state_db,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("render-preview")
def render_preview(
    project_id: str = typer.Option(..., "--project-id"),
    run_id: str | None = typer.Option(None, "--run-id"),
    sheet_id: str | None = typer.Option(None, "--sheet-id"),
    issue_id: str | None = typer.Option(None, "--issue-id"),
    line_group_id: str | None = typer.Option(None, "--line-group-id"),
    output_dir: Path | None = typer.Option(None, "--output-dir", file_okay=False, dir_okay=True, resolve_path=True),
    state_db: Path | None = typer.Option(None, "--state-db", file_okay=True, dir_okay=False, resolve_path=True),
) -> None:
    try:
        payload = render_project_preview(
            project_id=project_id,
            run_id=run_id,
            sheet_id=sheet_id,
            issue_id=issue_id,
            line_group_id=line_group_id,
            output_dir=output_dir,
            state_db_path=state_db,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))



@app.command("evaluate-hard-issues")
def evaluate_hard_issues(
    label_pack: Path = typer.Option(..., "--labels", help="Hard-issue label pack JSON"),
    project: list[str] = typer.Option(..., "--project", help="Alias=dir pairs like P001=.tmp/foo"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Evaluate hard-issue precision/recall against a frozen label pack (no tuning)."""
    project_dirs: dict[str, Path] = {}
    for item in project:
        if "=" not in item:
            raise typer.BadParameter(f"Expected alias=dir, got: {item}")
        alias, raw = item.split("=", 1)
        project_dirs[alias.strip()] = Path(raw.strip())
    result = evaluate_hard_issue_label_pack(label_pack, project_dirs)
    out = output or Path("hard_issue_eval")
    out.mkdir(parents=True, exist_ok=True)
    (out / "hard_issue_eval.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    typer.echo("Hard-issue evaluation completed:")
    typer.echo(f"- projects: {result['project_count']}")
    typer.echo(f"- micro_precision: {result['micro_precision']}")
    typer.echo(f"- micro_recall: {result['micro_recall']}")
    typer.echo(f"- micro_precision_ge_99: {result['micro_precision_ge_99']}")
    typer.echo(f"- report: {out / 'hard_issue_eval.json'}")


@app.command("evaluate-promotion-gate")
def evaluate_promotion_gate_cmd(
    project: list[str] = typer.Option(
        ...,
        "--project",
        help="Alias=dir pairs like P001=.tmp/foo; optional Alias:split=dir",
    ),
    labels: Path | None = typer.Option(
        None,
        "--labels",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Optional frozen hard-issue label pack (cal/val only; never held-out tuning)",
    ),
    heldout_labels: Path | None = typer.Option(
        None,
        "--heldout-labels",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Optional human-gold held-out label pack used only for release promotion evidence",
    ),
    heldout: list[str] = typer.Option(
        [],
        "--heldout",
        help="Project ids treated as held-out evaluation-only (never tuning)",
    ),
    primary_engine: str | None = typer.Option(
        None,
        "--primary-engine",
        help="Optional assertion of the configured primary engine; must match --config",
    ),
    topology_truth: list[str] = typer.Option(
        [],
        "--topology-truth",
        help="Alias=CSV topology truth; scoped truth is reported but never promoted as project-wide gold",
    ),
    product_approval: bool = typer.Option(
        False,
        "--product-approval/--no-product-approval",
        help="Explicit product authorization required before recommending a primary flip",
    ),
    config_path: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Aggregate structural + hard-issue promotion evidence without flipping primary_engine."""
    project_dirs: dict[str, Path] = {}
    splits: dict[str, str] = {}
    for item in project:
        if "=" not in item:
            raise typer.BadParameter(f"Expected alias=dir or alias:split=dir, got: {item}")
        left, raw = item.split("=", 1)
        left = left.strip()
        alias = left
        split = None
        if ":" in left:
            alias, split = left.split(":", 1)
            alias = alias.strip()
            split = split.strip() or None
        project_path = Path(raw.strip()).expanduser().resolve()
        if not project_path.is_dir():
            raise typer.BadParameter(f"Project directory does not exist: {project_path}")
        project_dirs[alias] = project_path
        if split:
            splits[alias] = split
    heldout_ids = {item.strip() for item in heldout if item.strip()}
    for pid, split in splits.items():
        if str(split).strip().casefold().startswith("heldout"):
            heldout_ids.add(pid)
    topology_truth_paths: dict[str, Path] = {}
    for item in topology_truth:
        if "=" not in item:
            raise typer.BadParameter(f"Expected alias=truth.csv, got: {item}")
        alias, raw_path = item.split("=", 1)
        truth_path = Path(raw_path.strip()).expanduser().resolve()
        if not truth_path.is_file():
            raise typer.BadParameter(f"Topology truth file does not exist: {truth_path}")
        topology_truth_paths[alias.strip()] = truth_path
    config = load_config(config_path)
    configured_primary_engine = str(
        config.get("recognition", {}).get("primary_engine") or "legacy"
    )
    if primary_engine is not None and primary_engine != configured_primary_engine:
        raise typer.BadParameter(
            f"--primary-engine={primary_engine} does not match configured primary engine "
            f"{configured_primary_engine}"
        )
    try:
        evidence = evaluate_promotion_gate(
            projects=project_dirs,
            splits=splits,
            hard_issue_label_pack=labels,
            heldout_hard_issue_label_pack=heldout_labels,
            topology_truth_paths=topology_truth_paths,
            heldout_project_ids=heldout_ids,
            primary_engine=configured_primary_engine,
            product_approval=product_approval,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    out = output or Path("promotion_gate")
    paths = write_promotion_gate_evidence(evidence, out)
    decision = evidence.get("decision") or {}
    typer.echo("Promotion-gate evaluation completed:")
    typer.echo(f"- projects: {evidence['project_count']}")
    typer.echo(f"- structural_pass_all: {evidence['structural_pass_all']}")
    typer.echo(f"- hard_issue_precision_status: {decision.get('hard_issue_precision_status')}")
    typer.echo(f"- ready_for_review_only_v2_assist: {decision.get('ready_for_review_only_v2_assist')}")
    typer.echo(f"- ready_for_primary_engine_flip: {decision.get('ready_for_primary_engine_flip')}")
    typer.echo(f"- evidence: {paths['promotion_gate_evidence']}")
    typer.echo(f"- metrics: {paths['metrics_by_project']}")
    typer.echo(f"- decision_log: {paths['decision_log']}")
    typer.echo(f"- topology_metrics: {paths['topology_metrics_by_project']}")
    if not evidence["structural_pass_all"]:
        raise typer.Exit(code=2)


@app.command("evaluate-corpus-census")
def evaluate_corpus_census_cmd(
    project: list[str] = typer.Option(
        ...,
        "--project",
        help="Alias=dir pairs like P001=.tmp/foo; optional Alias:split=dir",
    ),
    heldout: list[str] = typer.Option(
        [],
        "--held-out",
        help="Project aliases treated as held-out reporting-only entries",
    ),
    output: Path = typer.Option(Path("corpus_census"), "--output", "-o"),
) -> None:
    """Aggregate persisted extraction census evidence without rerunning CAD."""

    project_dirs: dict[str, Path] = {}
    splits: dict[str, str] = {}
    for item in project:
        if "=" not in item:
            raise typer.BadParameter(f"Expected alias=dir or alias:split=dir, got: {item}")
        left, raw_path = item.split("=", 1)
        left = left.strip()
        alias = left
        split = None
        if ":" in left:
            alias, split = left.split(":", 1)
            alias = alias.strip()
            split = split.strip() or None
        if not alias:
            raise typer.BadParameter(f"Project alias is empty: {item}")
        project_path = Path(raw_path.strip()).expanduser().resolve()
        if not project_path.is_dir():
            raise typer.BadParameter(f"Project directory does not exist: {project_path}")
        project_dirs[alias] = project_path
        if split:
            splits[alias] = split

    evaluation = evaluate_corpus_census(
        project_dirs,
        splits=splits,
        held_out_projects={item.strip() for item in heldout if item.strip()},
    )
    paths = write_corpus_census_artifacts(evaluation, output)
    summary = evaluation["summary"]
    typer.echo("Corpus extraction census completed:")
    typer.echo(f"- projects: {summary['project_count']}")
    typer.echo(f"- status: {summary['status']}")
    typer.echo(f"- all_projects_valid: {summary['all_projects_valid']}")
    typer.echo(f"- by_project: {paths['by_project']}")
    typer.echo(f"- summary: {paths['summary']}")
    if summary["status"] != "VALID":
        raise typer.Exit(code=2)


@app.command("verify-extraction")
def verify_extraction_cmd(
    project: list[str] = typer.Option(
        ...,
        "--project",
        help="Alias=dir pairs like P001=.tmp/foo",
    ),
    output: Path = typer.Option(Path("extraction_verification"), "--output", "-o"),
) -> None:
    """Offline extraction health scorecard over persisted project bundles."""

    project_dirs: dict[str, Path] = {}
    for item in project:
        if "=" not in item:
            raise typer.BadParameter(f"Expected alias=dir, got: {item}")
        alias, raw_path = item.split("=", 1)
        alias = alias.strip()
        if not alias:
            raise typer.BadParameter(f"Project alias is empty: {item}")
        project_path = Path(raw_path.strip()).expanduser().resolve()
        if not project_path.is_dir():
            raise typer.BadParameter(f"Project directory does not exist: {project_path}")
        project_dirs[alias] = project_path

    evaluation = evaluate_extraction_verification(project_dirs)
    paths = write_extraction_verification_artifacts(evaluation, output)
    summary = evaluation["summary"]
    typer.echo("Extraction verification completed:")
    typer.echo(f"- projects: {summary['project_count']}")
    typer.echo(f"- status: {summary['status']}")
    typer.echo(
        f"- PASS/REVIEW/FAIL: {summary['pass_count']}/{summary['review_count']}/{summary['fail_count']}"
    )
    typer.echo(f"- by_project: {paths['by_project']}")
    typer.echo(f"- by_page: {paths['by_page']}")
    typer.echo(f"- summary: {paths['summary']}")
    typer.echo(f"- markdown: {paths['markdown']}")
    if summary["status"] == "FAIL":
        raise typer.Exit(code=2)


@app.command("evaluate-symbol-corpus-queue")
def evaluate_symbol_corpus_queue_cmd(
    project: list[str] = typer.Option(
        ...,
        "--project",
        help="Alias=dir pairs like P001=.tmp/foo; optional Alias:split=dir",
    ),
    heldout: list[str] = typer.Option(
        [],
        "--held-out",
        help="Project aliases treated as held-out reporting-only entries",
    ),
    top_n: int = typer.Option(50, "--top-n", help="Maximum queue rows to export"),
    include_held_out: bool = typer.Option(
        False,
        "--include-held-out-in-ranking",
        help="Dangerous: include held-out inventories in ranking. Default false.",
    ),
    output: Path = typer.Option(Path("symbol_corpus_queue"), "--output", "-o"),
) -> None:
    """Build a non-held-out Top-N symbol port review queue from persisted inventories."""

    from dwg_audit.report.symbol_corpus_queue import evaluate_symbol_corpus_queue
    from dwg_audit.report.symbol_corpus_queue import write_symbol_corpus_queue_artifacts

    project_dirs: dict[str, Path] = {}
    splits: dict[str, str] = {}
    for item in project:
        if "=" not in item:
            raise typer.BadParameter(f"Expected alias=dir or alias:split=dir, got: {item}")
        left, raw_path = item.split("=", 1)
        left = left.strip()
        alias = left
        split = None
        if ":" in left:
            alias, split = left.split(":", 1)
            alias = alias.strip()
            split = split.strip() or None
        if not alias:
            raise typer.BadParameter(f"Project alias is empty: {item}")
        project_path = Path(raw_path.strip()).expanduser().resolve()
        if not project_path.is_dir():
            raise typer.BadParameter(f"Project directory does not exist: {project_path}")
        project_dirs[alias] = project_path
        if split:
            splits[alias] = split

    evaluation = evaluate_symbol_corpus_queue(
        project_dirs,
        splits=splits,
        held_out_projects={item.strip() for item in heldout if item.strip()},
        top_n=top_n,
        include_held_out_in_ranking=include_held_out,
    )
    paths = write_symbol_corpus_queue_artifacts(evaluation, output)
    summary = evaluation["summary"]
    typer.echo("Symbol corpus queue completed:")
    typer.echo(f"- projects: {summary['project_count']}")
    typer.echo(f"- ranking_projects: {summary['ranking_project_count']}")
    typer.echo(f"- status: {summary['status']}")
    typer.echo(f"- queue_rows: {summary['queue_row_count']}")
    typer.echo(f"- held_out_usage: {summary['held_out_usage']}")
    typer.echo(f"- queue: {paths['queue_csv']}")
    typer.echo(f"- summary: {paths['summary']}")
    if summary["status"] not in {"VALID", "EMPTY"}:
        raise typer.Exit(code=2)
    if summary["critical_issue_eligible_count"] != 0:
        raise typer.Exit(code=2)


@app.command("generate-symbol-corpus-review-pack")
def generate_symbol_corpus_review_pack_cmd(
    queue: Path = typer.Option(
        ...,
        "--queue",
        "-q",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="symbol_corpus_queue_topn.json from evaluate-symbol-corpus-queue",
    ),
    project: list[str] = typer.Option(
        [],
        "--project",
        help="Optional Alias=dir pairs used to resolve inventory identity fields",
    ),
    top_n: int = typer.Option(10, "--top-n", help="How many ranked families to template"),
    output: Path = typer.Option(Path("symbol_corpus_review_pack"), "--output", "-o"),
) -> None:
    """Generate editable Top-N symbol review templates for human port annotation."""

    from dwg_audit.report.symbol_corpus_review_pack import write_symbol_corpus_review_pack

    project_dirs: dict[str, Path] = {}
    for item in project:
        if "=" not in item:
            raise typer.BadParameter(f"Expected alias=dir, got: {item}")
        alias, raw_path = item.split("=", 1)
        alias = alias.strip()
        if not alias:
            raise typer.BadParameter(f"Project alias is empty: {item}")
        project_path = Path(raw_path.strip()).expanduser().resolve()
        if not project_path.is_dir():
            raise typer.BadParameter(f"Project directory does not exist: {project_path}")
        project_dirs[alias] = project_path

    result = write_symbol_corpus_review_pack(
        queue,
        output,
        project_dirs=project_dirs or None,
        top_n=top_n,
    )
    summary = result["summary"]
    typer.echo("Symbol corpus review pack generated:")
    typer.echo(f"- status: {summary['status']}")
    typer.echo(f"- template_symbols: {summary['template_symbol_count']}")
    typer.echo(f"- critical_issue_eligible: {summary['critical_issue_eligible_count']}")
    typer.echo(f"- combined_template: {result['combined_template_path']}")
    typer.echo(f"- manifest: {result['manifest_path']}")
    if summary["critical_issue_eligible_count"] != 0:
        raise typer.Exit(code=2)
    if summary["status"] not in {"VALID", "EMPTY"}:
        raise typer.Exit(code=2)


@app.command("consume-symbol-review")
def consume_symbol_review_cmd(
    input_path: Path = typer.Option(
        ...,
        "--input",
        "-i",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    ),
    output: Path = typer.Option(Path("symbol_review_consumption"), "--output", "-o"),
    promote: bool = typer.Option(
        False,
        "--promote",
        help="Promote only when the document is promotion_ready; never auto-critical",
    ),
) -> None:
    """Validate (and optionally promote) a human symbol review without auto-critical."""

    from dwg_audit.report.symbol_corpus_review_pack import consume_symbol_review_document

    result = consume_symbol_review_document(
        input_path,
        output_dir=output,
        promote=promote,
    )
    summary = result["summary"]
    typer.echo("Symbol review consumption:")
    typer.echo(f"- valid: {summary['valid']}")
    typer.echo(f"- promotion_ready: {summary['promotion_ready']}")
    typer.echo(f"- promoted: {summary['promoted']}")
    typer.echo(
        f"- registered_human_confirmed: {summary['registered_human_confirmed_symbol_count']}"
    )
    typer.echo(f"- shadow_eligible_ports: {summary['shadow_eligible_port_count']}")
    typer.echo(f"- critical_issue_eligible: {summary['critical_issue_eligible_count']}")
    typer.echo(f"- summary: {output / 'symbol_review_consumption_summary.json'}")
    if not summary["valid"]:
        raise typer.Exit(code=2)
    if promote and not summary["promoted"]:
        raise typer.Exit(code=2)



@app.command("propose-symbol-ports")
def propose_symbol_ports_cmd(
    review: Path = typer.Option(
        ...,
        "--review",
        "-r",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Pending symbol review template JSON",
    ),
    dxf: list[Path] = typer.Option(
        ...,
        "--dxf",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
        help="Converted DXF files used to locate block definitions",
    ),
    output: Path = typer.Option(Path("symbol_port_proposals"), "--output", "-o"),
    max_ports: int = typer.Option(4, "--max-ports"),
) -> None:
    """Propose MACHINE_PROPOSED ports from DXF block geometry (never human-confirmed)."""

    from dwg_audit.audit.symbol_library_review import load_symbol_review_document
    from dwg_audit.audit.symbol_port_proposal import write_machine_proposed_review_pack

    result = write_machine_proposed_review_pack(
        review_document_path=review,
        dxf_paths=dxf,
        output_dir=output,
        max_ports=max_ports,
    )
    summary = result["summary"]
    validation = load_symbol_review_document(result["draft_path"]).validation
    typer.echo("Machine symbol port proposals:")
    typer.echo(f"- proposed_with_ports: {summary['proposed_with_ports']}")
    typer.echo(f"- total_ports: {summary['total_ports']}")
    typer.echo(f"- block_not_found: {summary['block_not_found']}")
    typer.echo(f"- draft_valid: {validation.valid}")
    typer.echo(f"- promotion_ready: {validation.promotion_ready}")
    typer.echo(f"- draft: {result['draft_path']}")
    typer.echo(f"- summary: {result['summary_path']}")
    if not validation.valid:
        raise typer.Exit(code=2)



def run() -> None:
    app()


if __name__ == "__main__":
    run()
