import sqlite3
from pathlib import Path

from dwg_audit.desktop.state_store import DesktopStateStore


def test_state_store_migrates_legacy_issue_summary_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "desktop_state.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE runs (
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

            CREATE TABLE issue_summaries (
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

    store = DesktopStateStore(db_path)
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir=str(tmp_path / "artifacts" / "demo-project"),
        status="completed",
        sheet_count=1,
        pair_count=2,
        issue_count=1,
        metadata={"demo": True},
    )
    store.replace_issue_summaries(
        "session-a:demo-project",
        [
            {
                "issue_id": "I1",
                "rule_id": "R-ONE-TO-MANY",
                "issue_type": "one_to_many",
                "title": "One-to-many requires review",
                "summary": "One-to-many cluster requires review.",
                "explanation": "Multiple targets share one source value.",
                "recommended_action": "Review the linked sheets.",
                "severity": "review",
                "status": "open",
                "confidence": 0.83,
                "sheet_id": "S1",
                "file_id": "F1",
                "filename": "01.dwg",
                "sheet_no": "01",
                "line_group_id": "G1",
                "left_value": "101",
                "right_value": "201",
                "primary_pair_id": "P1",
                "one_to_many_classification": "review",
                "evidence": {"filename": "01.dwg", "sheet_no": "01", "one_to_many_classification": "review"},
                "evidence_refs": [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}],
                "related_pair_ids": ["P2"],
                "sheet_ids": ["S1", "S2"],
                "values": ["101", "201", "202"],
            }
        ],
    )

    loaded = store.load_latest_project_result("demo-project")

    assert loaded is not None
    issue = loaded["issues"][0]
    assert issue["issue_type"] == "one_to_many"
    assert issue["summary"] == "One-to-many cluster requires review."
    assert issue["one_to_many_classification"] == "review"
    assert issue["related_pair_ids"] == ["P2"]
    assert issue["evidence_refs"] == [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}]
