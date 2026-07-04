from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dwg_audit.pipeline import analyze_input_root
from dwg_audit.report import rerun_audit_from_findings
from dwg_audit.utils.config import load_config
from dwg_audit.utils.logging import configure_logging


@dataclass(slots=True)
class UIAnalysisResult:
    input_root: Path
    output_root: Path
    project_dirs: list[Path]
    audit_dirs: list[Path]
    config_path: Path | None
    run_summary_path: Path | None


def discover_project_outputs(output_root: Path) -> list[Path]:
    if not output_root.exists():
        return []
    return sorted([path for path in output_root.iterdir() if path.is_dir() and (path / "manifest.json").exists()])


def run_ui_analysis(
    input_root: Path,
    output_root: Path,
    config_path: Path | None = None,
    *,
    include_audit: bool = True,
) -> UIAnalysisResult:
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
    logger = configure_logging(resolved_output / "logs" / "ui_analyze.log")
    project_dirs = analyze_input_root(resolved_input, resolved_output, config, logger)

    audit_dirs: list[Path] = []
    if include_audit:
        for project_dir in project_dirs:
            audit_dirs.append(rerun_audit_from_findings(project_dir, config))

    run_summary_path = resolved_output / "run_summary.json"
    return UIAnalysisResult(
        input_root=resolved_input,
        output_root=resolved_output,
        project_dirs=project_dirs,
        audit_dirs=audit_dirs,
        config_path=resolved_config,
        run_summary_path=run_summary_path if run_summary_path.exists() else None,
    )
