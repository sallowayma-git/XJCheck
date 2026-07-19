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


def test_state_store_list_issue_summaries_page_paginates_large_runs(tmp_path: Path) -> None:
    """The pagination seam must stay stable for very large runs.

    A regression here would either balloon memory or break the pager
    contract (`total/limit/offset` plus server-side ordering identical to the
    full loader)."""

    store = DesktopStateStore(tmp_path / "desktop_state.db")
    store.record_run(
        run_id="session-a:demo-project",
        session_id="session-a",
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(tmp_path / "input"),
        artifact_dir="",
        status="completed",
        sheet_count=1,
        pair_count=2,
        issue_count=5_000,
        metadata={"demo": True},
    )
    store.replace_issue_summaries(
        "session-a:demo-project",
        [
            {
                "issue_id": f"I{i:05d}",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "issue_type": "pair_low_confidence",
                "title": f"Issue {i}",
                "summary": f"summary {i}",
                "explanation": "",
                "recommended_action": "",
                "severity": "minor",
                "status": "open",
                "confidence": 0.1,
                "sheet_id": "",
                "file_id": "",
                "filename": "01.dwg",
                "sheet_no": "01",
                "line_group_id": "",
                "left_value": "",
                "right_value": "",
                "primary_pair_id": "",
                "one_to_many_classification": "",
                "evidence": {},
                "evidence_refs": [],
                "related_pair_ids": [],
                "sheet_ids": [],
                "values": [],
            }
            for i in range(5_000)
        ],
    )

    assert store.count_issues("session-a:demo-project") == 5_000
    first = store.list_issue_summaries_page("session-a:demo-project", limit=50, offset=0)
    assert first["total"] == 5_000
    assert first["limit"] == 50
    assert first["offset"] == 0
    assert len(first["items"]) == 50
    assert first["items"][0]["issue_id"] == "I00000"

    later = store.list_issue_summaries_page("session-a:demo-project", limit=50, offset=4_950)
    assert later["total"] == 5_000
    assert later["offset"] == 4_950
    assert [item["issue_id"] for item in later["items"]] == [f"I{i:05d}" for i in range(4_950, 5_000)]

    detail = store.load_issue_summary("session-a:demo-project", "I03030")
    assert detail is not None
    assert detail["issue_id"] == "I03030"
    assert store.load_issue_summary("session-a:demo-project", "missing") is None
    assert store.count_page_findings("session-a:demo-project") == 0
