from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "DesktopEventWriter",
    "analyze_session",
    "cleanup_transient_workspaces",
    "delete_project_record",
    "list_recent_projects",
    "load_project_result",
    "render_project_preview",
    "purge_session",
    "update_issue_status",
]

_EXPORTS = {
    "DesktopEventWriter": ("dwg_audit.desktop.sidecar", "DesktopEventWriter"),
    "analyze_session": ("dwg_audit.desktop.sidecar", "analyze_session"),
    "cleanup_transient_workspaces": ("dwg_audit.desktop.sidecar", "cleanup_transient_workspaces"),
    "delete_project_record": ("dwg_audit.desktop.sidecar", "delete_project_record"),
    "list_recent_projects": ("dwg_audit.desktop.sidecar", "list_recent_projects"),
    "load_project_result": ("dwg_audit.desktop.sidecar", "load_project_result"),
    "render_project_preview": ("dwg_audit.desktop.preview", "render_project_preview"),
    "purge_session": ("dwg_audit.desktop.sidecar", "purge_session"),
    "update_issue_status": ("dwg_audit.desktop.sidecar", "update_issue_status"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
