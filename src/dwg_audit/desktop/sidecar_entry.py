from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_LIGHTWEIGHT_COMMANDS = {
    "cleanup-stale-workspaces",
    "cleanup-workspaces",
    "compact-session-workspace",
    "list-recent-projects",
    "load-result",
    "set-issue-status",
}

_ISSUE_STATUSES = {"open", "ignored", "resolved", "false_positive"}


def _configure_text_stream_utf8(stream) -> None:
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="strict")


def _bounded_recent_limit(value: str) -> int:
    limit = int(value)
    if not 1 <= limit <= 200:
        raise argparse.ArgumentTypeError("limit must be between 1 and 200")
    return limit


def _non_negative_seconds(value: str) -> float:
    seconds = float(value)
    if seconds < 0:
        raise argparse.ArgumentTypeError("seconds must not be negative")
    return seconds


def _run_lightweight_command(argv: list[str]) -> bool:
    if not argv or argv[0] not in _LIGHTWEIGHT_COMMANDS:
        return False

    from dwg_audit.desktop.state_store import DesktopStateStore
    from dwg_audit.desktop.state_store import default_state_db_path

    command = argv[0]
    parser = argparse.ArgumentParser(prog=f"dwg-audit-sidecar {command}")
    parser.add_argument("--state-db", type=Path)
    if command == "list-recent-projects":
        parser.add_argument("--limit", type=_bounded_recent_limit, default=20)
        parser.add_argument("--workspace-root", type=Path)
        parser.add_argument("--older-than-seconds", type=_non_negative_seconds, default=3600.0)
    elif command == "load-result":
        parser.add_argument("--project-id", required=True)
    elif command == "set-issue-status":
        parser.add_argument("--project-id", required=True)
        parser.add_argument("--issue-id", required=True)
        parser.add_argument("--status", choices=sorted(_ISSUE_STATUSES), required=True)
    else:
        parser.add_argument(
            "--workspace-root",
            type=Path,
            required=command == "compact-session-workspace",
        )
        parser.add_argument("--preview-cache-root", type=Path)
        if command == "compact-session-workspace":
            parser.add_argument("--session-id", required=True)
        elif command == "cleanup-stale-workspaces":
            parser.add_argument("--older-than-seconds", type=_non_negative_seconds, default=3600.0)
    options = parser.parse_args(argv[1:])

    db_path = (options.state_db or default_state_db_path()).expanduser().resolve()
    store = DesktopStateStore(db_path)
    if command == "list-recent-projects":
        if options.workspace_root is not None:
            from dwg_audit.desktop.lifecycle import cleanup_stale_workspaces

            cleanup_stale_workspaces(
                workspace_root=options.workspace_root,
                state_db_path=db_path,
                older_than_seconds=options.older_than_seconds,
            )
        payload = {"projects": store.list_recent_projects(limit=options.limit)}
    elif command == "load-result":
        payload = store.load_latest_project_result(options.project_id)
        if payload is None:
            parser.error(f"No stored result found for project_id={options.project_id}")
    elif command == "set-issue-status":
        runs = store.list_runs_for_project(options.project_id)
        if not runs:
            parser.error(f"No stored result found for project_id={options.project_id}")
        latest_run = runs[0]
        # Legacy un-compacted runs still mirror status into parquet/JSON, so
        # preserve their full CLI path. Compact desktop runs are SQLite-only.
        if str(latest_run.get("artifact_dir") or "").strip():
            return False
        issue = store.update_issue_status(
            run_id=str(latest_run["run_id"]),
            issue_id=options.issue_id,
            status=options.status,
        )
        if issue is None:
            parser.error(f"No stored issue found for issue_id={options.issue_id}")
        payload = {
            "project_id": options.project_id,
            "run_id": latest_run["run_id"],
            "issue_id": options.issue_id,
            "status": options.status,
            "issue": issue,
        }
    else:
        from dwg_audit.desktop.lifecycle import cleanup_stale_workspaces
        from dwg_audit.desktop.lifecycle import cleanup_transient_workspaces
        from dwg_audit.desktop.lifecycle import compact_session_workspace

        if command == "compact-session-workspace":
            payload = compact_session_workspace(
                session_id=options.session_id,
                workspace_root=options.workspace_root,
                state_db_path=db_path,
            )
        elif command == "cleanup-stale-workspaces":
            payload = cleanup_stale_workspaces(
                workspace_root=options.workspace_root,
                state_db_path=db_path,
                preview_cache_root=options.preview_cache_root,
                older_than_seconds=options.older_than_seconds,
            )
        else:
            payload = cleanup_transient_workspaces(
                workspace_root=options.workspace_root,
                state_db_path=db_path,
                preview_cache_root=options.preview_cache_root,
            )

    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.stdout.flush()
    return True


def _run_oda_worker_command(argv: list[str]) -> int | None:
    """Dispatch the frozen one-shot ODA worker before importing the full CLI."""

    if not argv or argv[0] != "oda-worker":
        return None
    from dwg_audit.readers.oda_worker import main as run_oda_worker

    return int(run_oda_worker(argv[1:]))


def main() -> None:
    # Rust expects JSON bytes to be UTF-8 regardless of the Windows code page.
    _configure_text_stream_utf8(sys.stdout)
    _configure_text_stream_utf8(sys.stderr)
    worker_exit = _run_oda_worker_command(sys.argv[1:])
    if worker_exit is not None:
        raise SystemExit(worker_exit)
    if _run_lightweight_command(sys.argv[1:]):
        return

    from dwg_audit.cli import run

    run()


if __name__ == "__main__":
    main()
