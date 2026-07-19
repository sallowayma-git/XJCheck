from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any


def default_state_db_path() -> Path:
    local_app_data = Path.home() / "AppData" / "Local"
    return local_app_data / "dwg-audit" / "desktop_state.db"


@dataclass(slots=True)
class StoredRun:
    run_id: str
    session_id: str
    project_id: str
    project_name: str
    input_root: str
    artifact_dir: str
    created_at: str
    updated_at: str
    status: str
    sheet_count: int
    pair_count: int
    issue_count: int
    metadata: dict[str, Any]


class DesktopStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def record_run(
        self,
        *,
        run_id: str,
        session_id: str,
        project_id: str,
        project_name: str,
        input_root: str,
        artifact_dir: str,
        status: str,
        sheet_count: int,
        pair_count: int,
        issue_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = _now_iso()
        payload = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id,
                    session_id,
                    project_id,
                    project_name,
                    input_root,
                    artifact_dir,
                    created_at,
                    updated_at,
                    status,
                    sheet_count,
                    pair_count,
                    issue_count,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    project_id=excluded.project_id,
                    project_name=excluded.project_name,
                    input_root=excluded.input_root,
                    artifact_dir=excluded.artifact_dir,
                    updated_at=excluded.updated_at,
                    status=excluded.status,
                    sheet_count=excluded.sheet_count,
                    pair_count=excluded.pair_count,
                    issue_count=excluded.issue_count,
                    metadata_json=excluded.metadata_json
                """,
                (
                    run_id,
                    session_id,
                    project_id,
                    project_name,
                    input_root,
                    artifact_dir,
                    now,
                    now,
                    status,
                    sheet_count,
                    pair_count,
                    issue_count,
                    payload,
                ),
            )

    def replace_issue_summaries(self, run_id: str, issues: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM issue_summaries WHERE run_id = ?", (run_id,))
            conn.executemany(
                """
                INSERT INTO issue_summaries (
                    run_id,
                    issue_id,
                    rule_id,
                    issue_type,
                    title,
                    summary,
                    explanation,
                    recommended_action,
                    severity,
                    status,
                    confidence,
                    sheet_id,
                    file_id,
                    filename,
                    sheet_no,
                    line_group_id,
                    left_value,
                    right_value,
                    primary_pair_id,
                    one_to_many_classification,
                    evidence_json,
                    evidence_refs_json,
                    related_pair_ids_json,
                    sheet_ids_json,
                    values_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        str(issue.get("issue_id") or ""),
                        str(issue.get("rule_id") or ""),
                        str(issue.get("issue_type") or issue.get("rule_id") or ""),
                        str(issue.get("title") or issue.get("message") or ""),
                        str(issue.get("summary") or issue.get("title") or issue.get("message") or ""),
                        str(issue.get("explanation") or ""),
                        str(issue.get("recommended_action") or ""),
                        str(issue.get("severity") or ""),
                        str(issue.get("status") or ""),
                        float(issue.get("confidence") or 0.0),
                        str(issue.get("sheet_id") or ""),
                        str(issue.get("file_id") or ""),
                        str(issue.get("filename") or ""),
                        str(issue.get("sheet_no") or ""),
                        str(issue.get("line_group_id") or ""),
                        str(issue.get("left_value") or ""),
                        str(issue.get("right_value") or ""),
                        str(issue.get("primary_pair_id") or ""),
                        str(issue.get("one_to_many_classification") or ""),
                        json.dumps(issue.get("evidence") or {}, ensure_ascii=False, sort_keys=True),
                        json.dumps(issue.get("evidence_refs") or [], ensure_ascii=False, sort_keys=True),
                        json.dumps(issue.get("related_pair_ids") or [], ensure_ascii=False, sort_keys=True),
                        json.dumps(issue.get("sheet_ids") or [], ensure_ascii=False, sort_keys=True),
                        json.dumps(issue.get("values") or [], ensure_ascii=False, sort_keys=True),
                    )
                    for issue in issues
                ],
            )

    def replace_page_findings(self, run_id: str, page_findings: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM page_findings WHERE run_id = ?", (run_id,))
            conn.executemany(
                """
                INSERT INTO page_findings (
                    run_id,
                    sheet_id,
                    file_id,
                    filename,
                    sheet_no,
                    sheet_order,
                    sheet_title,
                    page_type,
                    page_type_confidence,
                    audit_role,
                    route_target,
                    layout_summary_json,
                    structure_summary_json,
                    recognition_strategy,
                    number_matching_strategy,
                    high_confidence_signals_json,
                    open_questions_json,
                    warnings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        str(item.get("sheet_id") or ""),
                        str(item.get("file_id") or ""),
                        str(item.get("filename") or ""),
                        str(item.get("sheet_no") or ""),
                        int(item.get("sheet_order") or 0),
                        str(item.get("sheet_title") or ""),
                        str(item.get("page_type") or ""),
                        float(item.get("page_type_confidence") or 0.0),
                        str(item.get("audit_role") or ""),
                        str(item.get("route_target") or ""),
                        json.dumps(item.get("layout_summary") or {}, ensure_ascii=False, sort_keys=True),
                        json.dumps(item.get("structure_summary") or {}, ensure_ascii=False, sort_keys=True),
                        str(item.get("recognition_strategy") or ""),
                        str(item.get("number_matching_strategy") or ""),
                        json.dumps(item.get("high_confidence_signals") or [], ensure_ascii=False, sort_keys=True),
                        json.dumps(item.get("open_questions") or [], ensure_ascii=False, sort_keys=True),
                        json.dumps(item.get("warnings") or [], ensure_ascii=False, sort_keys=True),
                    )
                    for item in page_findings
                ],
            )

    def list_recent_projects(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    run_id,
                    session_id,
                    project_id,
                    project_name,
                    input_root,
                    artifact_dir,
                    updated_at,
                    status,
                    sheet_count,
                    pair_count,
                    issue_count
                FROM runs
                ORDER BY updated_at DESC, project_name ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "run_id": row["run_id"],
                "session_id": row["session_id"],
                "project_id": row["project_id"],
                "project_name": row["project_name"],
                "input_root": row["input_root"],
                "artifact_dir": row["artifact_dir"],
                "updated_at": row["updated_at"],
                "status": row["status"],
                "sheet_count": int(row["sheet_count"]),
                "pair_count": int(row["pair_count"]),
                "issue_count": int(row["issue_count"]),
            }
            for row in rows
        ]

    def load_latest_project_result(self, project_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            run_row = conn.execute(
                """
                SELECT *
                FROM runs
                WHERE project_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            if run_row is None:
                return None
            issue_rows = conn.execute(
                """
                SELECT *
                FROM issue_summaries
                WHERE run_id = ?
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'major' THEN 1
                        WHEN 'minor' THEN 2
                        WHEN 'review' THEN 3
                        ELSE 9
                    END,
                    confidence DESC,
                    issue_id ASC
                """,
                (run_row["run_id"],),
            ).fetchall()
            page_rows = conn.execute(
                """
                SELECT *
                FROM page_findings
                WHERE run_id = ?
                ORDER BY sheet_order ASC, sheet_id ASC
                """,
                (run_row["run_id"],),
            ).fetchall()
        return {
            "run": _row_to_run(run_row),
            "issues": [_issue_row_to_summary(row) for row in issue_rows],
            "page_findings": [
                {
                    "sheet_id": row["sheet_id"],
                    "file_id": row["file_id"] or None,
                    "filename": row["filename"],
                    "sheet_no": row["sheet_no"] or None,
                    "sheet_order": int(row["sheet_order"]),
                    "sheet_title": row["sheet_title"],
                    "page_type": row["page_type"],
                    "page_type_confidence": float(row["page_type_confidence"]),
                    "audit_role": row["audit_role"],
                    "route_target": row["route_target"],
                    "layout_summary": json.loads(row["layout_summary_json"] or "{}"),
                    "structure_summary": json.loads(row["structure_summary_json"] or "{}"),
                    "recognition_strategy": row["recognition_strategy"],
                    "number_matching_strategy": row["number_matching_strategy"],
                    "high_confidence_signals": json.loads(row["high_confidence_signals_json"] or "[]"),
                    "open_questions": json.loads(row["open_questions_json"] or "[]"),
                    "warnings": json.loads(row["warnings_json"] or "[]"),
                }
                for row in page_rows
            ],
        }

    def latest_run_for_project(self, project_id: str) -> dict[str, Any] | None:
        """Resolve the most recent run dict for ``project_id`` without loading issues."

        Used by sidecar helpers that previously piggy-backed on
        ``load_latest_project_result`` just to read the run id, which forced a
        full issues/page_findings scan on every status/problem mutation.
        """

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM runs
                WHERE project_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return _row_to_run(row) if row is not None else None

    def count_issues(self, run_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM issue_summaries WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def count_page_findings(self, run_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM page_findings WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def list_issue_summaries_page(
        self,
        run_id: str,
        *,
        limit: int,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return one page of issue summaries with the same ordering as
        ``load_latest_project_result``.

        The ``total`` field is computed by a separate ``COUNT(*)`` so callers can
        render pager metadata without re-querying; ``limit`` and ``offset`` are
        echoed back so the caller can correlate the page with its request.
        """

        safe_limit = max(0, min(int(limit), 5000))
        safe_offset = max(0, int(offset))
        with self._connect() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) FROM issue_summaries WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            total = int(total_row[0]) if total_row is not None else 0
            rows = conn.execute(
                """
                SELECT *
                FROM issue_summaries
                WHERE run_id = ?
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'major' THEN 1
                        WHEN 'minor' THEN 2
                        WHEN 'review' THEN 3
                        ELSE 9
                    END,
                    confidence DESC,
                    issue_id ASC
                LIMIT ? OFFSET ?
                """,
                (run_id, safe_limit, safe_offset),
            ).fetchall()
        return {
            "items": [_issue_row_to_summary(row) for row in rows],
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }

    def load_issue_summary(self, run_id: str, issue_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM issue_summaries
                WHERE run_id = ? AND issue_id = ?
                """,
                (run_id, issue_id),
            ).fetchone()
        return _issue_row_to_summary(row) if row is not None else None

    def load_page_findings(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM page_findings
                WHERE run_id = ?
                ORDER BY sheet_order ASC, sheet_id ASC
                """,
                (run_id,),
            ).fetchall()
        return [
            {
                "sheet_id": row["sheet_id"],
                "file_id": row["file_id"] or None,
                "filename": row["filename"],
                "sheet_no": row["sheet_no"] or None,
                "sheet_order": int(row["sheet_order"]),
                "sheet_title": row["sheet_title"],
                "page_type": row["page_type"],
                "page_type_confidence": float(row["page_type_confidence"]),
                "audit_role": row["audit_role"],
                "route_target": row["route_target"],
                "layout_summary": json.loads(row["layout_summary_json"] or "{}"),
                "structure_summary": json.loads(row["structure_summary_json"] or "{}"),
                "recognition_strategy": row["recognition_strategy"],
                "number_matching_strategy": row["number_matching_strategy"],
                "high_confidence_signals": json.loads(row["high_confidence_signals_json"] or "[]"),
                "open_questions": json.loads(row["open_questions_json"] or "[]"),
                "warnings": json.loads(row["warnings_json"] or "[]"),
            }
            for row in rows
        ]

    def update_issue_status(self, *, run_id: str, issue_id: str, status: str) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE issue_summaries
                SET status = ?
                WHERE run_id = ? AND issue_id = ?
                """,
                (status, run_id, issue_id),
            ).rowcount
            if not updated:
                return None
            conn.execute(
                """
                UPDATE runs
                SET updated_at = ?
                WHERE run_id = ?
                """,
                (now, run_id),
            )
            row = conn.execute(
                """
                SELECT *
                FROM issue_summaries
                WHERE run_id = ? AND issue_id = ?
                """,
                (run_id, issue_id),
            ).fetchone()
        if row is None:
            return None
        return _issue_row_to_summary(row)

    def purge_session(self, session_id: str) -> int:
        with self._connect() as conn:
            run_ids = [
                row["run_id"]
                for row in conn.execute(
                    "SELECT run_id FROM runs WHERE session_id = ?",
                    (session_id,),
                ).fetchall()
            ]
            conn.execute("DELETE FROM page_findings WHERE run_id IN (SELECT run_id FROM runs WHERE session_id = ?)", (session_id,))
            conn.execute("DELETE FROM issue_summaries WHERE run_id IN (SELECT run_id FROM runs WHERE session_id = ?)", (session_id,))
            deleted = conn.execute("DELETE FROM runs WHERE session_id = ?", (session_id,)).rowcount
        return int(deleted or len(run_ids))

    def list_runs_for_project(self, project_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM runs
                WHERE project_id = ?
                ORDER BY updated_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    def list_all_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM runs
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    def purge_project(self, project_id: str) -> int:
        with self._connect() as conn:
            run_ids = [
                row["run_id"]
                for row in conn.execute(
                    "SELECT run_id FROM runs WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            ]
            if not run_ids:
                return 0
            placeholders = ",".join("?" for _ in run_ids)
            conn.execute(f"DELETE FROM page_findings WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM issue_summaries WHERE run_id IN ({placeholders})", run_ids)
            deleted = conn.execute(
                f"DELETE FROM runs WHERE run_id IN ({placeholders})",
                run_ids,
            ).rowcount
        return int(deleted or len(run_ids))

    def update_run_artifact_dir(self, *, run_id: str, artifact_dir: str) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET artifact_dir = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (artifact_dir, now, run_id),
            )

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    input_root TEXT NOT NULL,
                    artifact_dir TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sheet_count INTEGER NOT NULL,
                    pair_count INTEGER NOT NULL,
                    issue_count INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_project_id_updated_at
                ON runs(project_id, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_runs_session_id
                ON runs(session_id);

                CREATE TABLE IF NOT EXISTS issue_summaries (
                    run_id TEXT NOT NULL,
                    issue_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    issue_type TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    explanation TEXT NOT NULL DEFAULT '',
                    recommended_action TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    sheet_id TEXT NOT NULL DEFAULT '',
                    file_id TEXT NOT NULL DEFAULT '',
                    filename TEXT NOT NULL,
                    sheet_no TEXT NOT NULL,
                    line_group_id TEXT NOT NULL DEFAULT '',
                    left_value TEXT NOT NULL,
                    right_value TEXT NOT NULL,
                    primary_pair_id TEXT NOT NULL DEFAULT '',
                    one_to_many_classification TEXT NOT NULL DEFAULT '',
                    evidence_json TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                    related_pair_ids_json TEXT NOT NULL DEFAULT '[]',
                    sheet_ids_json TEXT NOT NULL DEFAULT '[]',
                    values_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (run_id, issue_id)
                );

                CREATE TABLE IF NOT EXISTS page_findings (
                    run_id TEXT NOT NULL,
                    sheet_id TEXT NOT NULL,
                    file_id TEXT NOT NULL DEFAULT '',
                    filename TEXT NOT NULL,
                    sheet_no TEXT NOT NULL DEFAULT '',
                    sheet_order INTEGER NOT NULL DEFAULT 0,
                    sheet_title TEXT NOT NULL DEFAULT '',
                    page_type TEXT NOT NULL DEFAULT '',
                    page_type_confidence REAL NOT NULL DEFAULT 0.0,
                    audit_role TEXT NOT NULL DEFAULT '',
                    route_target TEXT NOT NULL DEFAULT '',
                    layout_summary_json TEXT NOT NULL DEFAULT '{}',
                    structure_summary_json TEXT NOT NULL DEFAULT '{}',
                    recognition_strategy TEXT NOT NULL DEFAULT '',
                    number_matching_strategy TEXT NOT NULL DEFAULT '',
                    high_confidence_signals_json TEXT NOT NULL DEFAULT '[]',
                    open_questions_json TEXT NOT NULL DEFAULT '[]',
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (run_id, sheet_id)
                );
                """
            )
            _ensure_issue_summary_columns(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _issue_row_to_summary(row: sqlite3.Row) -> dict[str, Any]:
    evidence = json.loads(row["evidence_json"] or "{}")
    if not isinstance(evidence, dict):
        evidence = {}
    handling_class = str(evidence.get("handling_class") or "").strip()
    if not handling_class:
        # Backfill for runs stored before triage enrichment.
        from dwg_audit.audit.issue_triage import summarize_handling

        handling_class = next(
            (
                key
                for key, count in summarize_handling(
                    [
                        {
                            "rule_id": row["rule_id"],
                            "severity": row["severity"],
                            "confidence": float(row["confidence"] or 0.0),
                            "evidence": evidence,
                        }
                    ]
                ).items()
                if key != "other" and count
            ),
            "review",
        )
        evidence = {
            **evidence,
            "handling_class": handling_class,
            "handling_label": {
                "error": "确定性错误",
                "warning": "可能有错误",
                "review": "须人工校验",
            }.get(handling_class, "须人工校验"),
        }
    return {
        "issue_id": row["issue_id"],
        "rule_id": row["rule_id"],
        "issue_type": row["issue_type"] or row["rule_id"],
        "title": row["title"],
        "summary": row["summary"],
        "explanation": row["explanation"],
        "recommended_action": row["recommended_action"],
        "severity": row["severity"],
        "status": row["status"],
        "confidence": float(row["confidence"]),
        "sheet_id": row["sheet_id"] or None,
        "file_id": row["file_id"] or None,
        "filename": row["filename"],
        "sheet_no": row["sheet_no"],
        "line_group_id": row["line_group_id"] or None,
        "left_value": row["left_value"] or None,
        "right_value": row["right_value"] or None,
        "primary_pair_id": row["primary_pair_id"] or None,
        "one_to_many_classification": row["one_to_many_classification"] or None,
        "handling_class": handling_class or evidence.get("handling_class") or "review",
        "handling_label": evidence.get("handling_label")
        or {
            "error": "确定性错误",
            "warning": "可能有错误",
            "review": "须人工校验",
        }.get(handling_class, "须人工校验"),
        "review_group_id": evidence.get("review_group_id") or row["issue_id"],
        "review_group_label": evidence.get("review_group_label") or row["title"],
        "review_group_size": int(evidence.get("review_group_size") or 1),
        "issue_family": evidence.get("issue_family") or row["title"],
        "evidence": evidence,
        "evidence_refs": json.loads(row["evidence_refs_json"] or "[]"),
        "related_pair_ids": json.loads(row["related_pair_ids_json"] or "[]"),
        "sheet_ids": json.loads(row["sheet_ids_json"] or "[]"),
        "values": json.loads(row["values_json"] or "[]"),
    }


def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "session_id": row["session_id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "input_root": row["input_root"],
        "artifact_dir": row["artifact_dir"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
        "sheet_count": int(row["sheet_count"]),
        "pair_count": int(row["pair_count"]),
        "issue_count": int(row["issue_count"]),
        "metadata": json.loads(row["metadata_json"] or "{}"),
    }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_issue_summary_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(issue_summaries)").fetchall()
    }
    required = {
        "issue_type": "TEXT NOT NULL DEFAULT ''",
        "summary": "TEXT NOT NULL DEFAULT ''",
        "explanation": "TEXT NOT NULL DEFAULT ''",
        "recommended_action": "TEXT NOT NULL DEFAULT ''",
        "sheet_id": "TEXT NOT NULL DEFAULT ''",
        "file_id": "TEXT NOT NULL DEFAULT ''",
        "line_group_id": "TEXT NOT NULL DEFAULT ''",
        "primary_pair_id": "TEXT NOT NULL DEFAULT ''",
        "one_to_many_classification": "TEXT NOT NULL DEFAULT ''",
        "evidence_refs_json": "TEXT NOT NULL DEFAULT '[]'",
        "related_pair_ids_json": "TEXT NOT NULL DEFAULT '[]'",
        "sheet_ids_json": "TEXT NOT NULL DEFAULT '[]'",
        "values_json": "TEXT NOT NULL DEFAULT '[]'",
    }
    for column, definition in required.items():
        if column in existing:
            continue
        conn.execute(f"ALTER TABLE issue_summaries ADD COLUMN {column} {definition}")
