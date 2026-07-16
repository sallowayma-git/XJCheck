from __future__ import annotations

import json
import shutil
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.state_store import default_state_db_path
from dwg_audit.report.artifacts import load_report_frames
from dwg_audit.services import run_analysis_workflow

DESKTOP_ISSUE_STATUSES = {"open", "ignored", "resolved", "false_positive"}


def default_workspace_root() -> Path:
    local_app_data = Path.home() / "AppData" / "Local"
    return local_app_data / "dwg-audit" / "sessions"


def default_preview_cache_root() -> Path:
    local_app_data = Path.home() / "AppData" / "Local"
    return local_app_data / "dwg-audit" / "preview-cache"


class DesktopEventWriter:
    def __init__(self, stream = None) -> None:
        self.stream = stream or sys.stdout
        self._lock = threading.Lock()
        if hasattr(self.stream, "reconfigure"):
            self.stream.reconfigure(encoding="utf-8")

    def emit(self, event_type: str, **payload: Any) -> None:
        record = {"event": event_type, **payload}
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            self.stream.write(line)
            self.stream.flush()


def analyze_session(
    *,
    input_root: Path,
    workspace_root: Path,
    config_path: Path | None = None,
    session_id: str | None = None,
    include_audit: bool = True,
    state_db_path: Path | None = None,
    event_writer: DesktopEventWriter | None = None,
    compact_after_store: bool = True,
) -> list[dict[str, Any]]:
    resolved_input = input_root.expanduser().resolve()
    resolved_workspace = workspace_root.expanduser().resolve()
    resolved_workspace.mkdir(parents=True, exist_ok=True)
    resolved_config = config_path.expanduser().resolve() if config_path else None
    run_session_id = session_id or uuid.uuid4().hex
    session_workspace = resolved_workspace / run_session_id
    session_workspace.mkdir(parents=True, exist_ok=True)
    writer = event_writer or DesktopEventWriter()
    state_store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())

    writer.emit(
        "run_started",
        session_id=run_session_id,
        input_root=str(resolved_input),
        workspace_root=str(session_workspace),
        include_audit=include_audit,
    )
    result = run_analysis_workflow(
        input_root=resolved_input,
        output_root=session_workspace,
        config_path=resolved_config,
        include_audit=include_audit,
        log_path=session_workspace / "logs" / "desktop_session.log",
        event_sink=writer,
        on_project_artifacts_ready=lambda project_dir: writer.emit(
            "project_artifacts_ready",
            session_id=run_session_id,
            project_dir=str(project_dir),
        ),
    )

    stored_runs: list[dict[str, Any]] = []
    for project_dir in result.project_dirs:
        summary = _store_project_run(
            state_store,
            session_id=run_session_id,
            project_dir=project_dir,
            input_root=resolved_input,
            include_audit=include_audit,
        )
        stored_runs.append(summary)
        writer.emit("project_stored", session_id=run_session_id, **summary)

    compact_info: dict[str, Any] | None = None
    if compact_after_store:
        compact_info = compact_session_workspace(
            session_id=run_session_id,
            workspace_root=resolved_workspace,
            state_db_path=state_store.db_path,
        )
        writer.emit("workspace_compacted", **compact_info)
        for summary in stored_runs:
            summary["artifact_dir"] = ""
            summary["compacted"] = True

    writer.emit(
        "run_finished",
        session_id=run_session_id,
        project_count=len(stored_runs),
        projects=stored_runs,
        compacted=bool(compact_info),
    )
    return stored_runs


def list_recent_projects(*, state_db_path: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    return store.list_recent_projects(limit=limit)


def load_project_result(*, project_id: str, state_db_path: Path | None = None) -> dict[str, Any] | None:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    return store.load_latest_project_result(project_id)


def update_issue_status(
    *,
    project_id: str,
    issue_id: str,
    status: str,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    normalized_status = status.strip().lower()
    if normalized_status not in DESKTOP_ISSUE_STATUSES:
        allowed = ", ".join(sorted(DESKTOP_ISSUE_STATUSES))
        raise ValueError(f"Unsupported issue status: {status}. Expected one of: {allowed}")

    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    latest = store.load_latest_project_result(project_id)
    if latest is None:
        raise FileNotFoundError(f"No stored result found for project_id={project_id}")

    run = latest["run"]
    issue = store.update_issue_status(run_id=str(run["run_id"]), issue_id=issue_id, status=normalized_status)
    if issue is None:
        raise FileNotFoundError(f"No stored issue found for issue_id={issue_id}")

    artifact_dir = str(run.get("artifact_dir") or "").strip()
    if artifact_dir:
        _persist_issue_status_to_artifacts(Path(artifact_dir), issue_id=issue_id, status=normalized_status)
    return {
        "project_id": project_id,
        "run_id": run["run_id"],
        "issue_id": issue_id,
        "status": normalized_status,
        "issue": issue,
    }


def purge_session(
    *,
    session_id: str,
    workspace_root: Path,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    deleted_runs = store.purge_session(session_id)
    session_workspace = workspace_root.expanduser().resolve() / session_id
    removed_workspace = False
    if session_workspace.exists():
        shutil.rmtree(session_workspace, ignore_errors=True)
        removed_workspace = True
    return {
        "session_id": session_id,
        "deleted_runs": deleted_runs,
        "removed_workspace": removed_workspace,
        "workspace_path": str(session_workspace),
    }


def compact_session_workspace(
    *,
    session_id: str,
    workspace_root: Path,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    """Drop conversion/DXF/cache workspaces after issues are persisted to SQLite."""
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    session_workspace = workspace_root.expanduser().resolve() / session_id
    updated_runs = 0
    for run in store.list_all_runs():
        if str(run.get("session_id") or "") != session_id:
            continue
        store.update_run_artifact_dir(run_id=str(run["run_id"]), artifact_dir="")
        updated_runs += 1

    removed_workspace = False
    removed_bytes_estimate = 0
    if session_workspace.exists():
        removed_bytes_estimate = _dir_size_bytes(session_workspace)
        shutil.rmtree(session_workspace, ignore_errors=True)
        removed_workspace = not session_workspace.exists()

    return {
        "session_id": session_id,
        "updated_runs": updated_runs,
        "removed_workspace": removed_workspace,
        "removed_bytes_estimate": removed_bytes_estimate,
        "workspace_path": str(session_workspace),
    }


def cleanup_transient_workspaces(
    *,
    workspace_root: Path | None = None,
    state_db_path: Path | None = None,
    preview_cache_root: Path | None = None,
) -> dict[str, Any]:
    """Remove conversion sessions and regenerated preview cache; keep SQLite issue records."""
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    resolved_workspace = (workspace_root or default_workspace_root()).expanduser().resolve()
    resolved_preview_cache = (preview_cache_root or default_preview_cache_root()).expanduser().resolve()

    cleared_artifact_dirs = 0
    for run in store.list_all_runs():
        artifact_dir = str(run.get("artifact_dir") or "").strip()
        if not artifact_dir:
            continue
        path = Path(artifact_dir)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            cleared_artifact_dirs += 1
        store.update_run_artifact_dir(run_id=str(run["run_id"]), artifact_dir="")

    removed_sessions = 0
    if resolved_workspace.exists():
        for child in list(resolved_workspace.iterdir()):
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
                if not child.exists():
                    removed_sessions += 1

    removed_preview_cache = False
    if resolved_preview_cache.exists():
        shutil.rmtree(resolved_preview_cache, ignore_errors=True)
        removed_preview_cache = not resolved_preview_cache.exists()

    return {
        "cleared_artifact_dirs": cleared_artifact_dirs,
        "removed_sessions": removed_sessions,
        "removed_preview_cache": removed_preview_cache,
        "workspace_root": str(resolved_workspace),
        "kept_issue_records": True,
    }


def delete_project_record(
    *,
    project_id: str,
    workspace_root: Path | None = None,
    state_db_path: Path | None = None,
    preview_cache_root: Path | None = None,
) -> dict[str, Any]:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    resolved_workspace = (workspace_root or default_workspace_root()).expanduser().resolve()
    resolved_preview_cache = (preview_cache_root or default_preview_cache_root()).expanduser().resolve()
    runs = store.list_runs_for_project(project_id)
    if not runs:
        raise FileNotFoundError(f"No stored result found for project_id={project_id}")

    removed_paths: list[str] = []
    session_ids: set[str] = set()
    for run in runs:
        session_ids.add(str(run.get("session_id") or ""))
        artifact_dir = str(run.get("artifact_dir") or "").strip()
        if artifact_dir:
            path = Path(artifact_dir)
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                removed_paths.append(str(path))

    deleted_runs = store.purge_project(project_id)

    for session_id in session_ids:
        if not session_id:
            continue
        session_path = resolved_workspace / session_id
        if session_path.exists():
            remaining = [
                item
                for item in store.list_all_runs()
                if str(item.get("session_id") or "") == session_id
            ]
            if not remaining:
                shutil.rmtree(session_path, ignore_errors=True)
                removed_paths.append(str(session_path))

    preview_dir = resolved_preview_cache / project_id
    if preview_dir.exists():
        shutil.rmtree(preview_dir, ignore_errors=True)
        removed_paths.append(str(preview_dir))

    return {
        "project_id": project_id,
        "deleted_runs": deleted_runs,
        "removed_paths": removed_paths,
    }


def _store_project_run(
    store: DesktopStateStore,
    *,
    session_id: str,
    project_dir: Path,
    input_root: Path,
    include_audit: bool,
) -> dict[str, Any]:
    manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
    frames = load_report_frames(project_dir)
    pairs = frames.get("pairs", pd.DataFrame())
    issues = frames.get("issues", pd.DataFrame())
    issue_payload = _issue_payloads(issues)
    page_findings = findings_payload.get("page_findings", [])
    run_id = f"{session_id}:{manifest['project_id']}"
    metadata = {
        "include_audit": include_audit,
        "manifest_warnings": manifest.get("warnings", []),
        "page_findings_count": int(findings_payload.get("page_findings_count", len(page_findings))),
        "artifacts": {
            "project_dir": str(project_dir),
            "findings_dir": str(project_dir / "findings"),
            "audit_dir": str(project_dir / "audit"),
        },
    }
    store.record_run(
        run_id=run_id,
        session_id=session_id,
        project_id=str(manifest["project_id"]),
        project_name=str(manifest["project_name"]),
        input_root=str(input_root),
        artifact_dir=str(project_dir),
        status="completed",
        sheet_count=int(manifest.get("sheet_count", 0)),
        pair_count=int(len(pairs)),
        issue_count=int(len(issues)),
        metadata=metadata,
    )
    store.replace_issue_summaries(run_id, issue_payload)
    store.replace_page_findings(run_id, page_findings)
    return {
        "run_id": run_id,
        "project_id": str(manifest["project_id"]),
        "project_name": str(manifest["project_name"]),
        "artifact_dir": str(project_dir),
        "sheet_count": int(manifest.get("sheet_count", 0)),
        "pair_count": int(len(pairs)),
        "issue_count": int(len(issues)),
    }


def _issue_payloads(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    payloads: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        evidence = _decode_jsonish(row.get("evidence"))
        evidence_refs = _decode_jsonish(row.get("evidence_refs"))
        related_pair_ids = _decode_jsonish(row.get("related_pair_ids"))
        sheet_ids = _decode_jsonish(row.get("sheet_ids"))
        values = _decode_jsonish(row.get("values"))
        payloads.append(
            {
                "issue_id": row.get("issue_id"),
                "rule_id": row.get("rule_id"),
                "issue_type": _string_value(row.get("issue_type")) or _string_value(row.get("rule_id")),
                "title": _string_value(row.get("title")) or _string_value(row.get("message")),
                "summary": _string_value(row.get("summary")) or _string_value(row.get("title")) or _string_value(row.get("message")),
                "explanation": _string_value(row.get("explanation")),
                "recommended_action": _string_value(row.get("recommended_action")),
                "severity": _string_value(row.get("severity")),
                "status": _string_value(row.get("status")),
                "confidence": float(row.get("confidence") or 0.0),
                "sheet_id": _string_value(row.get("sheet_id")),
                "file_id": _string_value(row.get("file_id")),
                "filename": evidence.get("filename") if isinstance(evidence, dict) else "",
                "sheet_no": evidence.get("sheet_no") if isinstance(evidence, dict) else "",
                "line_group_id": _string_value(row.get("line_group_id")),
                "left_value": _nullable_string_value(row.get("left_value")),
                "right_value": _nullable_string_value(row.get("right_value")),
                "primary_pair_id": _string_value(row.get("primary_pair_id")),
                "one_to_many_classification": evidence.get("one_to_many_classification") if isinstance(evidence, dict) else "",
                "evidence": evidence if isinstance(evidence, dict) else {},
                "evidence_refs": evidence_refs if isinstance(evidence_refs, list) else [],
                "related_pair_ids": related_pair_ids if isinstance(related_pair_ids, list) else [],
                "sheet_ids": sheet_ids if isinstance(sheet_ids, list) else [],
                "values": values if isinstance(values, list) else [],
            }
        )
    return payloads


def _decode_jsonish(value: object) -> Any:
    if value is None:
        return {}
    if isinstance(value, float) and pd.isna(value):
        return {}
    if isinstance(value, dict):
        return _normalize_jsonish(value)
    if isinstance(value, list):
        return _normalize_jsonish(value)
    if isinstance(value, str):
        try:
            return _normalize_jsonish(json.loads(value))
        except json.JSONDecodeError:
            return {}
    return _normalize_jsonish(value)


def _normalize_jsonish(value: Any) -> Any:
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        value = value.tolist()
    if isinstance(value, dict):
        return {str(key): _normalize_jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_jsonish(item) for item in value]
    return value


def _string_value(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _nullable_string_value(value: object) -> str | None:
    text = _string_value(value)
    return text or None


def _persist_issue_status_to_artifacts(project_dir: Path, *, issue_id: str, status: str) -> None:
    audit_dir = project_dir / "audit"
    parquet_path = audit_dir / "issues.parquet"
    json_path = audit_dir / "issues.json"
    if not parquet_path.exists():
        return

    frame = pd.read_parquet(parquet_path)
    if "issue_id" not in frame.columns:
        return
    mask = frame["issue_id"].astype(str) == issue_id
    if not mask.any():
        return
    frame.loc[mask, "status"] = status
    frame.to_parquet(parquet_path, index=False)
    frame.to_json(json_path, orient="records", force_ascii=False, indent=2)


def _dir_size_bytes(path: Path) -> int:
    total = 0
    try:
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total
