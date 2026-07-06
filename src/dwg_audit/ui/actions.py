from __future__ import annotations

from pathlib import Path

from dwg_audit.services import AnalysisRunResult
from dwg_audit.services import run_analysis_workflow


UIAnalysisResult = AnalysisRunResult


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
    return run_analysis_workflow(
        input_root=resolved_input,
        output_root=resolved_output,
        config_path=config_path,
        include_audit=include_audit,
        log_path=resolved_output / "logs" / "ui_analyze.log",
    )
