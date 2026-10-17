from __future__ import annotations

import json
import shutil
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.domain.issue_locations import derive_locations_from_refs
from dwg_audit.domain.issue_layers import USER_VISIBLE_RULE_IDS
from dwg_audit.desktop.lifecycle import cleanup_transient_workspaces
from dwg_audit.desktop.lifecycle import compact_session_workspace
from dwg_audit.desktop.lifecycle import default_preview_cache_root
from dwg_audit.desktop.lifecycle import default_workspace_root
from dwg_audit.desktop.lifecycle import session_lease
from dwg_audit.desktop.lifecycle import _safe_session_path
from dwg_audit.desktop.lifecycle import remove_workspace_directory
from dwg_audit.desktop.preview import build_preview_geometry_payloads
from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.state_store import IssueQueryFilters
from dwg_audit.desktop.state_store import default_state_db_path
from dwg_audit.report.artifacts import load_report_frames
from dwg_audit.services import run_analysis_workflow

DESKTOP_ISSUE_STATUSES = {"open", "ignored", "resolved", "false_positive"}


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
    session_workspace = _safe_session_path(resolved_workspace, run_session_id)
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
    prepared_projects = []
    stored_runs: list[dict[str, Any]] = []
    current_page_facts = {}
    try:
        with session_lease(resolved_workspace, run_session_id):
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
            cached_page_facts=state_store.load_current_page_facts(),
            current_page_facts=current_page_facts,
            )
            for project_dir in result.project_dirs:
                summary = _store_project_run(
                    state_store, session_id=run_session_id, project_dir=project_dir,
                    input_root=resolved_input, include_audit=include_audit, _prepared=prepared_projects,
                    page_facts=current_page_facts,
                )
                stored_runs.append(summary)
            state_store.commit_session_snapshot(run_session_id, prepared_projects)
    except BaseException:
        try:
            with session_lease(resolved_workspace, run_session_id):
                remove_workspace_directory(session_workspace, resolved_workspace, protected=[resolved_input])
        except BlockingIOError:
            pass  # Another live analysis owns the workspace; startup recovery will remove this failed session.
        raise

    for summary in stored_runs:
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
            if compact_info.get("removed_workspace"):
                summary["artifact_dir"] = ""
            summary["compacted"] = bool(compact_info.get("removed_workspace"))

    writer.emit(
        "run_finished",
        session_id=run_session_id,
        project_count=len(stored_runs),
        projects=stored_runs,
        compacted=bool(compact_info and compact_info.get("removed_workspace")),
    )
    return stored_runs


def list_recent_projects(*, state_db_path: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    return store.list_recent_projects(limit=limit)


def load_project_result(
    *,
    project_id: str,
    run_id: str | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any] | None:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    payload = store.load_latest_project_result(project_id, run_id=run_id)
    if payload is not None:
        _enrich_run_recognition_summary(payload["run"])
    return payload


def load_project_summary(
    *,
    project_id: str,
    run_id: str | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Return `{run, issue_count, page_finding_count}` for the latest run, with
    no issue or page payloads. Used by the result screen to render the page
    header and pager metadata without loading the full result set.
    """

    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    payload = store.load_project_summary(project_id, run_id=run_id)
    if payload is not None:
        _enrich_run_recognition_summary(payload["run"])
    return payload


def load_project_diagnostics(
    *,
    project_id: str,
    run_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    state_db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Return one page of internal diagnostic findings, separate from issues."""
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    payload = store.load_project_diagnostics_page(
        project_id,
        run_id=run_id,
        limit=limit,
        offset=offset,
    )
    if payload is not None:
        _enrich_run_recognition_summary(payload["run"])
        payload["recognition_summary"] = (payload["run"].get("metadata") or {}).get(
            "recognition_summary", {}
        )
    return payload


def load_project_issues(
    *,
    project_id: str,
    run_id: str | None = None,
    limit: int,
    offset: int = 0,
    search: str | None = None,
    severity: str | None = None,
    rule_id: str | None = None,
    status: str | None = None,
    triage: str | None = None,
    handling: str | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Return one page of issues for the latest run of ``project_id`` plus
    pager metadata. ``None`` is returned when the project has no stored run at
    all, so callers can distinguish "no project" from "empty issue list".
    """

    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    return store.load_project_issues_page(
        project_id,
        run_id=run_id,
        limit=limit,
        offset=offset,
        filters=IssueQueryFilters(
            search=search,
            severity=severity,
            rule_id=rule_id,
            status=status,
            triage=triage,
            handling=handling,
        ),
    )


def load_project_issue_detail(
    *,
    project_id: str,
    issue_id: str,
    run_id: str | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Resolve a single issue by ``issue_id`` for the latest run of the project.

    This avoids re-loading the entire issue array when the user clicks a row in
    a virtualized list and the issue was not present in the current page.
    """

    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    return store.load_project_issue_detail(
        project_id,
        run_id=run_id,
        issue_id=issue_id,
    )


def update_issue_status(
    *,
    project_id: str,
    issue_id: str,
    status: str,
    run_id: str | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    normalized_status = status.strip().lower()
    if normalized_status not in DESKTOP_ISSUE_STATUSES:
        allowed = ", ".join(sorted(DESKTOP_ISSUE_STATUSES))
        raise ValueError(f"Unsupported issue status: {status}. Expected one of: {allowed}")

    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    run = store.load_run_for_project(project_id, run_id=run_id)
    if run is None:
        raise FileNotFoundError(f"No stored result found for project_id={project_id}")

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
    resolved_workspace = workspace_root.expanduser().resolve()
    session_workspace = _safe_session_path(resolved_workspace, session_id)
    with session_lease(resolved_workspace, session_id):
        protected = [r["input_root"] for r in store.list_all_runs() if r.get("input_root")]
        deleted_runs = store.purge_session(session_id)
        removed_workspace = remove_workspace_directory(session_workspace, resolved_workspace, protected=protected)
    return {
        "session_id": session_id,
        "deleted_runs": deleted_runs,
        "removed_workspace": removed_workspace,
        "workspace_path": str(session_workspace),
    }


def delete_project_record(
    *,
    project_id: str,
    workspace_root: Path | None = None,
    state_db_path: Path | None = None,
    preview_cache_root: Path | None = None,
) -> dict[str, Any]:
    root = (workspace_root or default_workspace_root()).expanduser().resolve()
    with session_lease(root, "delete-project"):
        return _delete_project_record_unlocked(project_id=project_id, workspace_root=root,
            state_db_path=state_db_path, preview_cache_root=preview_cache_root)


DELETE_BUSY_MESSAGE = "分析进行中，请稍后再删除"


def delete_project_records(
    *,
    project_ids: list[str],
    workspace_root: Path | None = None,
    state_db_path: Path | None = None,
    preview_cache_root: Path | None = None,
) -> dict[str, Any]:
    """Delete several project records under a single workspace lease.

    The lease is taken once for the whole batch. Each id is attempted on its
    own: a failure is reported in that id's entry and the rest still run.
    A missing record counts as success (``not_found`` is set). A concurrent
    analysis makes the lease fail with ``BlockingIOError`` before anything runs.
    """
    root = (workspace_root or default_workspace_root()).expanduser().resolve()
    results: list[dict[str, Any]] = []
    with session_lease(root, "delete-project"):
        for project_id in dict.fromkeys(str(item) for item in project_ids):
            if not project_id.strip():
                results.append(_delete_outcome(project_id, ok=False, error="项目编号为空。"))
                continue
            try:
                payload = _delete_project_record_unlocked(
                    project_id=project_id,
                    workspace_root=root,
                    state_db_path=state_db_path,
                    preview_cache_root=preview_cache_root,
                )
            except FileNotFoundError:
                results.append(_delete_outcome(project_id, ok=True, not_found=True))
            except Exception as exc:  # report per project; keep the batch going
                results.append(_delete_outcome(project_id, ok=False, error=str(exc) or type(exc).__name__))
            else:
                results.append(_delete_outcome(project_id, ok=True, payload=payload))
    return {
        "results": results,
        "deleted_count": sum(1 for item in results if item["ok"]),
        "failed_count": sum(1 for item in results if not item["ok"]),
    }


def _delete_outcome(
    project_id: str,
    *,
    ok: bool,
    not_found: bool = False,
    error: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "project_id": project_id,
        "ok": ok,
        "not_found": not_found,
        "error": error,
        "deleted_runs": 0,
        "removed_paths": [],
    }
    if payload is not None:
        outcome["deleted_runs"] = payload.get("deleted_runs", 0)
        outcome["removed_paths"] = payload.get("removed_paths", [])
    return outcome


def _delete_project_record_unlocked(
    *, project_id: str, workspace_root: Path, state_db_path: Path | None,
    preview_cache_root: Path | None,
) -> dict[str, Any]:
    store = DesktopStateStore((state_db_path or default_state_db_path()).expanduser().resolve())
    resolved_workspace = (workspace_root or default_workspace_root()).expanduser().resolve()
    resolved_preview_cache = (preview_cache_root or default_preview_cache_root()).expanduser().resolve()
    runs = store.list_runs_for_project(project_id)
    if not runs:
        if any(row["project_id"] == project_id for row in store.list_recent_projects()):
            store.purge_project(project_id)
            return {"project_id": project_id, "deleted_runs": 0, "removed_paths": []}
        raise FileNotFoundError(f"No stored result found for project_id={project_id}")

    removed_paths: list[str] = []
    session_ids: set[str] = set()
    for run in runs:
        session_ids.add(str(run.get("session_id") or ""))
        artifact_dir = str(run.get("artifact_dir") or "").strip()
        if artifact_dir:
            path = Path(artifact_dir)
            if path.exists() and remove_workspace_directory(path, resolved_workspace, protected=[r["input_root"] for r in runs]):
                removed_paths.append(str(path))

    deleted_runs = store.purge_project(project_id)

    for session_id in session_ids:
        if not session_id:
            continue
        session_path = _safe_session_path(resolved_workspace, session_id)
        if session_path.exists():
            remaining = [
                item
                for item in store.list_all_runs()
                if str(item.get("session_id") or "") == session_id
            ]
            if not remaining:
                if remove_workspace_directory(session_path, resolved_workspace, protected=[r["input_root"] for r in runs]):
                    removed_paths.append(str(session_path))

    preview_dir = _safe_session_path(resolved_preview_cache, project_id)
    if preview_dir.exists() and remove_workspace_directory(preview_dir, resolved_preview_cache):
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
    _prepared: list[dict[str, Any]] | None = None,
    page_facts: dict | None = None,
) -> dict[str, Any]:
    manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
    frames = load_report_frames(
        project_dir,
        names=("pairs", "issues", "pages", "lines", "texts", "line_groups", "blocks", "primitive_segments", "sw_ports", "sw_part_instances"),
    )
    pairs = frames.get("pairs", pd.DataFrame())
    issues = frames.get("issues", pd.DataFrame())
    if not issues.empty and "rule_id" in issues.columns:
        issues = issues.copy()
        user_mask = issues["rule_id"].astype(str).isin(USER_VISIBLE_RULE_IDS)
        diagnostic_frame = issues.loc[~user_mask].copy()
        issues = issues.loc[user_mask].copy()
    else:
        diagnostic_frame = pd.DataFrame()
    diagnostics_path = project_dir / "audit" / "recognition_gap_diagnostics.jsonl"
    if diagnostics_path.is_file():
        try:
            diagnostic_frame = pd.read_json(diagnostics_path, lines=True)
        except (OSError, ValueError):
            diagnostic_frame = pd.DataFrame()
    issue_payload = _issue_payloads(issues)
    diagnostic_payload = _issue_payloads(diagnostic_frame)
    page_findings = findings_payload.get("page_findings", [])
    series_chains_path = project_dir / "audit" / "series_chains.json"
    series_chains = (
        json.loads(series_chains_path.read_text(encoding="utf-8"))
        if include_audit and series_chains_path.exists()
        else None
    )
    run_id = f"{session_id}:{manifest['project_id']}"
    metadata = {
        "include_audit": include_audit,
        "manifest_warnings": manifest.get("warnings", []),
        "page_findings_count": int(findings_payload.get("page_findings_count", len(page_findings))),
        "analysis_status": findings_payload.get("analysis_status", "COMPLETE"),
        "clean_conclusion_allowed": findings_payload.get("clean_conclusion_allowed", True),
        "incomplete_page_count": findings_payload.get("incomplete_page_count", 0),
        "failure_code_counts": findings_payload.get("failure_code_counts", {}),
        "recognition_summary": _build_recognition_summary(
            findings_payload,
            project_dir / "audit",
            diagnostic_frame=diagnostic_frame,
        ),
        "artifacts": {
            "project_dir": str(project_dir),
            "findings_dir": str(project_dir / "findings"),
            "audit_dir": str(project_dir / "audit"),
        },
    }
    run_payload = dict(
        run_id=run_id,
        session_id=session_id,
        project_id=str(manifest["project_id"]),
        project_name=str(manifest["project_name"]),
        input_root=str(input_root),
        artifact_dir=str(project_dir),
        status="completed" if metadata["clean_conclusion_allowed"] else "incomplete",
        sheet_count=int(manifest.get("sheet_count", 0)),
        pair_count=int(len(pairs)),
        issue_count=int(len(issues)),
        metadata=metadata,
        series_chains=series_chains,
    )
    prepared = {"run": run_payload, "issues": issue_payload, "diagnostics": diagnostic_payload, "pages": page_findings,
                "geometries": build_preview_geometry_payloads(frames)}
    project_root = str(Path(manifest.get("input_root", input_root)).resolve())
    prepared.update(project_root=project_root, page_facts=(page_facts or {}).get(project_root, {}))
    if _prepared is None:
        store.commit_session_snapshot(session_id, [prepared])
    else:
        _prepared.append(prepared)
    return {
        "run_id": run_id,
        "project_id": str(manifest["project_id"]),
        "project_name": str(manifest["project_name"]),
        "artifact_dir": str(project_dir),
        "sheet_count": int(manifest.get("sheet_count", 0)),
        "pair_count": int(len(pairs)),
        "issue_count": int(len(issues)),
        "diagnostic_count": int(metadata["recognition_summary"].get("diagnostic_count", 0)),
        "coverage_ratio": metadata["recognition_summary"].get("coverage_ratio"),
    }


def _enrich_run_recognition_summary(run: dict[str, Any]) -> None:
    metadata = run.setdefault("metadata", {})
    existing = metadata.get("recognition_summary")
    if isinstance(existing, dict) and "coverage_ratio" in existing and "unclosed_count" in existing:
        return
    artifact_dir_value = str(run.get("artifact_dir") or "").strip()
    if not artifact_dir_value:
        metadata["recognition_summary"] = {
            "coverage_ratio": None,
            "unclosed_count": 0,
            "diagnostic_count": 0,
            "by_rule": {},
            "by_presentation": {},
            "by_reason_code": {},
            "suppressed_count": 0,
            "suppressed_by": {},
            "by_page": [],
        }
        return
    artifact_dir = Path(artifact_dir_value)
    findings_path = artifact_dir / "findings" / "findings.json"
    audit_dir = artifact_dir / "audit"
    try:
        findings_payload = json.loads(findings_path.read_text(encoding="utf-8")) if findings_path.is_file() else {}
    except (OSError, ValueError):
        findings_payload = {}
    issues_path = audit_dir / "issues.parquet"
    diagnostic_frame = pd.DataFrame()
    if issues_path.is_file():
        try:
            all_issues = pd.read_parquet(issues_path)
            if "rule_id" in all_issues.columns:
                diagnostic_frame = all_issues.loc[
                    ~all_issues["rule_id"].astype(str).isin(USER_VISIBLE_RULE_IDS)
                ]
        except Exception:
            diagnostic_frame = pd.DataFrame()
    metadata["recognition_summary"] = _build_recognition_summary(
        findings_payload, audit_dir, diagnostic_frame=diagnostic_frame
    )


def _build_recognition_summary(
    findings_payload: dict[str, Any],
    audit_dir: Path,
    *,
    diagnostic_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    coverage = findings_payload.get("entity_coverage_summary") or {}
    summary_path = audit_dir / "recognition_gap_diagnostic_summary.json"
    try:
        diagnostic_summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    except (OSError, ValueError):
        diagnostic_summary = {}
    frame = diagnostic_frame if diagnostic_frame is not None else pd.DataFrame()
    by_rule = dict(diagnostic_summary.get("by_rule") or {})
    by_presentation = dict(diagnostic_summary.get("by_presentation") or {})
    by_reason = dict(diagnostic_summary.get("by_reason_code") or {})
    by_observation_reason = dict(diagnostic_summary.get("by_observation_reason_code") or {})
    unclosed_by_sheet: dict[str, int] = {}
    diagnostic_count = int(diagnostic_summary.get("diagnostic_count") or 0)
    unclosed_count = int(diagnostic_summary.get("unclosed_count") or 0)
    if not diagnostic_summary and not frame.empty:
        by_rule = frame.get("rule_id", pd.Series(dtype=str)).astype(str).value_counts().to_dict()
        diagnostic_count = int(len(frame))
        unclosed_mask = frame.get("rule_id", pd.Series(dtype=str)).astype(str).eq("R-RECOGNITION-GAP")
        unclosed_count = int(unclosed_mask.sum())
        for _, row in frame.loc[unclosed_mask].iterrows():
            sheet_id = str(row.get("sheet_id") or "project")
            unclosed_by_sheet[sheet_id] = unclosed_by_sheet.get(sheet_id, 0) + 1
            evidence = _decode_jsonish(row.get("evidence"))
            presentation = str(evidence.get("presentation") or "observation")
            by_presentation[presentation] = int(by_presentation.get(presentation, 0)) + 1
            reasons = evidence.get("resolution_reason_codes") or [
                reason
                for observation in evidence.get("resolution_observations") or []
                for reason in (observation.get("reason_codes") or [])
            ] or evidence.get("reason_codes") or ["unspecified"]
            for reason in reasons:
                by_reason[str(reason)] = int(by_reason.get(str(reason), 0)) + 1
            for reason in evidence.get("reason_codes") or []:
                by_observation_reason[str(reason)] = int(by_observation_reason.get(str(reason), 0)) + 1
    else:
        unclosed_by_sheet = {
            str(item.get("sheet_id") or "project"): int(item.get("unclosed_count") or 0)
            for item in diagnostic_summary.get("by_sheet", [])
        }
    pages = []
    for page in coverage.get("page_summaries", []) or []:
        if page.get("summary_scope") != "page":
            continue
        sheet_id = str(page.get("sheet_id") or "")
        pages.append(
            {
                "sheet_id": page.get("sheet_id"),
                "sheet_no": page.get("sheet_no"),
                "filename": page.get("filename"),
                "coverage_ratio": page.get("coverage_ratio"),
                "unclosed_count": unclosed_by_sheet.get(sheet_id, 0),
            }
        )
    return {
        "coverage_ratio": coverage.get("coverage_ratio"),
        "unclosed_count": unclosed_count,
        "diagnostic_count": diagnostic_count,
        "by_rule": by_rule,
        "by_presentation": by_presentation,
        "by_reason_code": by_reason,
        "by_observation_reason_code": by_observation_reason,
        "suppressed_count": int(diagnostic_summary.get("suppressed_count") or 0),
        "suppressed_by": diagnostic_summary.get("suppressed_by") or {},
        "by_page": pages,
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
        payload = (
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
                "handling_class": _string_value(evidence.get("handling_class")) if isinstance(evidence, dict) else "",
                "handling_label": _string_value(evidence.get("handling_label")) if isinstance(evidence, dict) else "",
                "review_group_id": _string_value(evidence.get("review_group_id")) if isinstance(evidence, dict) else "",
                "review_group_label": _string_value(evidence.get("review_group_label")) if isinstance(evidence, dict) else "",
                "review_group_size": int(evidence.get("review_group_size") or 1) if isinstance(evidence, dict) else 1,
                "issue_family": _string_value(evidence.get("issue_family")) if isinstance(evidence, dict) else "",
                "evidence": evidence if isinstance(evidence, dict) else {},
                "evidence_refs": evidence_refs if isinstance(evidence_refs, list) else [],
                "related_pair_ids": related_pair_ids if isinstance(related_pair_ids, list) else [],
                "sheet_ids": sheet_ids if isinstance(sheet_ids, list) else [],
                "values": values if isinstance(values, list) else [],
            }
        )
        payload["locations"] = derive_locations_from_refs(payload)
        payloads.append(payload)
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
