from __future__ import annotations

from typing import Any

__all__ = [
    "AnalysisRunResult",
    "enrich_issues_with_root_causes",
    "run_analysis_workflow",
    "write_issue_root_cause_audit",
]


def __getattr__(name: str) -> Any:
    if name in {"AnalysisRunResult", "run_analysis_workflow"}:
        from dwg_audit.services.execution import AnalysisRunResult
        from dwg_audit.services.execution import run_analysis_workflow

        return {
            "AnalysisRunResult": AnalysisRunResult,
            "run_analysis_workflow": run_analysis_workflow,
        }[name]
    if name in {"enrich_issues_with_root_causes", "write_issue_root_cause_audit"}:
        from dwg_audit.services.issue_diagnostics import enrich_issues_with_root_causes
        from dwg_audit.services.issue_diagnostics import write_issue_root_cause_audit

        return {
            "enrich_issues_with_root_causes": enrich_issues_with_root_causes,
            "write_issue_root_cause_audit": write_issue_root_cause_audit,
        }[name]
    raise AttributeError(f"module 'dwg_audit.services' has no attribute {name!r}")
