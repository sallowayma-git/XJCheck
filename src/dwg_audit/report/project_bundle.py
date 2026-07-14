"""Resolve project output bundles across flat and nested runner layouts.

CLI/pipeline may write either:

- ``project_dir/findings`` + ``project_dir/audit`` (flat fixture layout), or
- ``project_dir/<project_slug>/findings`` with sibling ``cache``/``logs``
  (real multi-project runner layout).

Promotion/metrics readers must resolve the bundle root without inventing data.
"""

from __future__ import annotations

from pathlib import Path


def find_findings_dir(project_dir: Path) -> Path | None:
    """Return the shallowest ``findings`` directory under *project_dir*."""
    project_dir = Path(project_dir)
    direct = project_dir / "findings"
    if direct.is_dir():
        return direct
    matches = [path for path in project_dir.rglob("findings") if path.is_dir()]
    if not matches:
        return None
    matches.sort(key=lambda path: (len(path.parts), str(path)))
    return matches[0]


def resolve_project_bundle_dir(project_dir: Path) -> Path:
    """Return the directory that owns findings/audit/extraction artifacts.

    Prefer a direct ``project_dir/findings`` layout. When only a nested
    project-slug bundle exists, return that nested root. When nothing is
    found, return the original *project_dir* so callers fail closed with
    missing-artifact status rather than inventing paths.
    """
    project_dir = Path(project_dir)
    if (project_dir / "findings").is_dir():
        return project_dir
    findings = find_findings_dir(project_dir)
    if findings is None:
        return project_dir
    return findings.parent
