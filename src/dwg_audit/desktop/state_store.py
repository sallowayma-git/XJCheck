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
                    title,
                    severity,
                    status,
                    confidence,
                    filename,
                    sheet_no,
                    left_value,
                    right_value,
                    evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        str(issue.get("issue_id") or ""),
                        str(issue.get("rule_id") or ""),
                        str(issue.get("title") or issue.get("message") or ""),
                        str(issue.get("severity") or ""),
                        str(issue.get("status") or ""),
                        float(issue.get("confidence") or 0.0),
                        str(issue.get("filename") or ""),
                        str(issue.get("sheet_no") or ""),
                        str(issue.get("left_value") or ""),
                        str(issue.get("right_value") or ""),
                        json.dumps(issue.get("evidence") or {}, ensure_ascii=False, sort_keys=True),
                    )
                    for issue in issues
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
        return {
            "run": _row_to_run(run_row),
            "issues": [
                {
                    "issue_id": row["issue_id"],
                    "rule_id": row["rule_id"],
                    "title": row["title"],
                    "severity": row["severity"],
                    "status": row["status"],
                    "confidence": float(row["confidence"]),
                    "filename": row["filename"],
                    "sheet_no": row["sheet_no"],
                    "left_value": row["left_value"] or None,
                    "right_value": row["right_value"] or None,
                    "evidence": json.loads(row["evidence_json"] or "{}"),
                }
                for row in issue_rows
            ],
        }

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
        return {
            "issue_id": row["issue_id"],
            "rule_id": row["rule_id"],
            "title": row["title"],
            "severity": row["severity"],
            "status": row["status"],
            "confidence": float(row["confidence"]),
            "filename": row["filename"],
            "sheet_no": row["sheet_no"],
            "left_value": row["left_value"] or None,
            "right_value": row["right_value"] or None,
            "evidence": json.loads(row["evidence_json"] or "{}"),
        }

    def purge_session(self, session_id: str) -> int:
        with self._connect() as conn:
            run_ids = [
                row["run_id"]
                for row in conn.execute(
                    "SELECT run_id FROM runs WHERE session_id = ?",
                    (session_id,),
                ).fetchall()
            ]
            conn.execute("DELETE FROM issue_summaries WHERE run_id IN (SELECT run_id FROM runs WHERE session_id = ?)", (session_id,))
            deleted = conn.execute("DELETE FROM runs WHERE session_id = ?", (session_id,)).rowcount
        return int(deleted or len(run_ids))

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
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    filename TEXT NOT NULL,
                    sheet_no TEXT NOT NULL,
                    left_value TEXT NOT NULL,
                    right_value TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, issue_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


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
