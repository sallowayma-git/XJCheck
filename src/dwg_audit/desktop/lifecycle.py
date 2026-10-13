from __future__ import annotations

import shutil
import time
import os
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any

from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.state_store import default_state_db_path


def default_workspace_root() -> Path:
    local_app_data = Path.home() / "AppData" / "Local"
    return local_app_data / "dwg-audit" / "sessions"


def default_preview_cache_root() -> Path:
    local_app_data = Path.home() / "AppData" / "Local"
    return local_app_data / "dwg-audit" / "preview-cache"


@contextmanager
def session_lease(workspace_root: Path, session_id: str):
    """One bounded cross-process workspace lock: analysis and cleanup never overlap."""
    root = workspace_root.expanduser().resolve()
    root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = root.parent / ("." + root.name + ".workspace.lock")
    with lock_path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BlockingIOError("Workspace is active; analysis/cleanup must wait") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def remove_workspace_directory(path: Path, root: Path, *, protected=()) -> bool:
    target, allowed = path.expanduser().resolve(), root.expanduser().resolve()
    if target == allowed or not target.is_relative_to(allowed):
        return False
    for item in protected:
        source = Path(item).expanduser().resolve()
        if source == target or source.is_relative_to(target) or target.is_relative_to(source):
            return False
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    return not target.exists()


def _cleanup_lease(function):
    @wraps(function)
    def run(**kwargs):
        root = (kwargs.get("workspace_root") or default_workspace_root()).expanduser().resolve()
        try:
            with session_lease(root, "cleanup"):
                return function(**kwargs)
        except BlockingIOError:
            return {"removed_workspace": False, "removed_sessions": 0, "updated_runs": 0,
                    "removed_preview_cache": False, "cleared_artifact_dirs": 0,
                    "removed_preview_entries": 0, "skipped_active": True, "kept_issue_records": True}
    return run


@_cleanup_lease

def compact_session_workspace(
    *,
    session_id: str,
    workspace_root: Path,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    """Delete one session workspace after its issue text is persisted."""
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    resolved_workspace = workspace_root.expanduser().resolve()
    session_workspace = _safe_session_path(resolved_workspace, session_id)
    updated_runs = 0
    runs = store.list_all_runs()
    protected = [r["input_root"] for r in runs if r.get("input_root")]
    removed_workspace = remove_workspace_directory(session_workspace, resolved_workspace, protected=protected)
    for run in runs:
        if str(run.get("session_id") or "") != session_id:
            continue
        if removed_workspace:
            store.update_run_artifact_dir(run_id=str(run["run_id"]), artifact_dir="")
            updated_runs += 1

    return {
        "session_id": session_id,
        "updated_runs": updated_runs,
        "removed_workspace": removed_workspace,
        "workspace_path": str(session_workspace),
    }


@_cleanup_lease
def cleanup_transient_workspaces(
    *,
    workspace_root: Path | None = None,
    state_db_path: Path | None = None,
    preview_cache_root: Path | None = None,
) -> dict[str, Any]:
    """Remove all regenerable desktop artifacts while keeping issue text."""
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    resolved_workspace = (workspace_root or default_workspace_root()).expanduser().resolve()
    resolved_preview_cache = (preview_cache_root or default_preview_cache_root()).expanduser().resolve()

    cleared_artifact_dirs = 0
    runs = store.list_all_runs()
    protected = [r["input_root"] for r in runs if r.get("input_root")]
    for run in runs:
        artifact_dir = str(run.get("artifact_dir") or "").strip()
        if artifact_dir:
            path = Path(artifact_dir)
            if not path.expanduser().resolve().is_relative_to(resolved_workspace):
                continue
            if not remove_workspace_directory(path, resolved_workspace, protected=protected):
                continue
            cleared_artifact_dirs += 1
        store.update_run_artifact_dir(run_id=str(run["run_id"]), artifact_dir="")

    removed_sessions = 0
    if resolved_workspace.exists():
        for child in list(resolved_workspace.iterdir()):
            if not child.is_dir():
                continue
            if remove_workspace_directory(child, resolved_workspace, protected=protected):
                removed_sessions += 1

    removed_preview_cache = False
    if resolved_preview_cache.exists():
        removed_preview_cache = remove_workspace_directory(resolved_preview_cache, resolved_preview_cache.parent, protected=protected)

    return {
        "cleared_artifact_dirs": cleared_artifact_dirs,
        "removed_sessions": removed_sessions,
        "removed_preview_cache": removed_preview_cache,
        "workspace_root": str(resolved_workspace),
        "kept_issue_records": True,
        "database_compaction": store.compact_database_if_needed(),
    }


@_cleanup_lease
def cleanup_stale_workspaces(
    *,
    workspace_root: Path | None = None,
    state_db_path: Path | None = None,
    preview_cache_root: Path | None = None,
    older_than_seconds: float = 3600.0,
) -> dict[str, Any]:
    """Recover abandoned workspaces without touching a recently active session."""
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    resolved_workspace = (workspace_root or default_workspace_root()).expanduser().resolve()
    resolved_preview_cache = (preview_cache_root or default_preview_cache_root()).expanduser().resolve()
    cutoff = time.time() - max(0.0, float(older_than_seconds))

    removed_sessions = 0
    skipped_recent_sessions = 0
    if resolved_workspace.exists():
        for child in list(resolved_workspace.iterdir()):
            if not child.is_dir():
                continue
            if _latest_tree_mtime(child) > cutoff:
                skipped_recent_sessions += 1
                continue
            result = compact_session_workspace.__wrapped__(
                session_id=child.name,
                workspace_root=resolved_workspace,
                state_db_path=store.db_path,
            )
            if result["removed_workspace"]:
                removed_sessions += 1

    removed_preview_entries = 0
    if resolved_preview_cache.exists():
        for child in list(resolved_preview_cache.iterdir()):
            if _latest_tree_mtime(child) > cutoff:
                continue
            if child.is_dir():
                remove_workspace_directory(child, resolved_preview_cache)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass
            if not child.exists():
                removed_preview_entries += 1

    return {
        "removed_sessions": removed_sessions,
        "skipped_recent_sessions": skipped_recent_sessions,
        "removed_preview_entries": removed_preview_entries,
        "older_than_seconds": max(0.0, float(older_than_seconds)),
        "workspace_root": str(resolved_workspace),
        "kept_issue_records": True,
    }


def _safe_session_path(workspace_root: Path, session_id: str) -> Path:
    normalized = session_id.strip()
    if not normalized or normalized in {".", ".."} or Path(normalized).name != normalized:
        raise ValueError(f"Invalid desktop session_id: {session_id!r}")
    session_path = (workspace_root / normalized).resolve()
    if session_path.parent != workspace_root:
        raise ValueError(f"Desktop session escapes workspace root: {session_id!r}")
    return session_path


def _latest_tree_mtime(path: Path) -> float:
    try:
        latest = path.stat().st_mtime
    except OSError:
        return time.time()
    if not path.is_dir():
        return latest
    try:
        for child in path.rglob("*"):
            try:
                latest = max(latest, child.stat().st_mtime)
            except OSError:
                continue
    except OSError:
        pass
    return latest
