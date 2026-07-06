from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable

from dwg_audit.pipeline import analyze_input_root
from dwg_audit.report import rerun_audit_from_findings
from dwg_audit.utils.config import load_config
from dwg_audit.utils.logging import configure_logging


@dataclass(slots=True)
class AnalysisRunResult:
    input_root: Path
    output_root: Path
    project_dirs: list[Path]
    audit_dirs: list[Path]
    config_path: Path | None
    run_summary_path: Path | None
    config: dict[str, Any]


def run_analysis_workflow(
    *,
    input_root: Path,
    output_root: Path,
    config_path: Path | None = None,
    include_audit: bool = True,
    log_path: Path | None = None,
    event_sink: Any = None,
    on_project_artifacts_ready: Callable[[Path], None] | None = None,
) -> AnalysisRunResult:
    resolved_input = input_root.expanduser().resolve()
    resolved_output = output_root.expanduser().resolve()
    resolved_config = config_path.expanduser().resolve() if config_path else None

    if not resolved_input.exists():
        raise FileNotFoundError(f"Input path not found: {resolved_input}")
    if not resolved_input.is_dir():
        raise ValueError(f"Input path must be a directory: {resolved_input}")
    if resolved_config is not None and not resolved_config.exists():
        raise FileNotFoundError(f"Config path not found: {resolved_config}")

    resolved_output.mkdir(parents=True, exist_ok=True)
    config = load_config(resolved_config)
    logger = configure_logging(log_path or (resolved_output / "logs" / "analysis.log"))
    project_dirs = analyze_input_root(
        resolved_input,
        resolved_output,
        config,
        logger,
        event_sink=event_sink,
    )

    audit_dirs: list[Path] = []
    for project_dir in project_dirs:
        if on_project_artifacts_ready is not None:
            on_project_artifacts_ready(project_dir)
        if include_audit:
            audit_dirs.append(rerun_audit_from_findings(project_dir, config, event_sink=event_sink))

    run_summary_path = resolved_output / "run_summary.json"
    return AnalysisRunResult(
        input_root=resolved_input,
        output_root=resolved_output,
        project_dirs=project_dirs,
        audit_dirs=audit_dirs,
        config_path=resolved_config,
        run_summary_path=run_summary_path if run_summary_path.exists() else None,
        config=config,
    )
