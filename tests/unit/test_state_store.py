import sqlite3
from pathlib import Path

from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.state_store import IssueQueryFilters


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


def test_latest_run_order_is_immutable_when_cleanup_updates_artifacts(tmp_path: Path) -> None:
    store = DesktopStateStore(tmp_path / "desktop_state.db")
    for run_id in ("old", "new"):
        store.record_run(
            run_id=run_id,
            session_id=run_id,
            project_id="demo-project",
            project_name="Demo",
            input_root=str(tmp_path / "input"),
            artifact_dir=str(tmp_path / run_id),
            status="completed",
            sheet_count=1,
            pair_count=1,
            issue_count=0,
            metadata={},
        )
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE runs SET created_at = ?, updated_at = ? WHERE run_id = 'old'", ("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"))
        conn.execute("UPDATE runs SET created_at = ?, updated_at = ? WHERE run_id = 'new'", ("2026-01-02T00:00:00+00:00", "2026-01-02T00:00:00+00:00"))

    store.update_run_artifact_dir(run_id="new", artifact_dir="")
    store.update_run_artifact_dir(run_id="old", artifact_dir="")

    assert store.latest_run_for_project("demo-project")["run_id"] == "new"
    assert store.list_runs_for_project("demo-project")[0]["run_id"] == "new"


def test_pinned_project_pages_cannot_fall_back_to_another_run(tmp_path: Path) -> None:
    store = DesktopStateStore(tmp_path / "desktop_state.db")
    for run_id, title in (("old", "old issue"), ("new", "new issue")):
        store.record_run(
            run_id=run_id,
            session_id=run_id,
            project_id="demo-project",
            project_name="Demo",
            input_root=str(tmp_path / "input"),
            artifact_dir="",
            status="completed",
            sheet_count=1,
            pair_count=1,
            issue_count=1,
            metadata={},
        )
        store.replace_issue_summaries(
            run_id,
            [{"issue_id": "I1", "rule_id": "R", "title": title, "severity": "review", "status": "open", "confidence": 0.5, "evidence": {}}],
        )

    page = store.load_project_issues_page("demo-project", run_id="old", limit=10)
    assert page is not None
    assert page["run"]["run_id"] == "old"
    assert page["items"][0]["title"] == "old issue"
    assert store.load_project_issues_page("demo-project", run_id="missing", limit=10) is None

    detail = store.load_project_issue_detail("demo-project", run_id="old", issue_id="I1")
    assert detail is not None
    assert detail["run"]["run_id"] == "old"
    assert detail["issue"]["title"] == "old issue"


def test_summary_facets_and_filtered_pages_use_the_whole_pinned_run(tmp_path: Path) -> None:
    store = DesktopStateStore(tmp_path / "desktop_state.db")
    store.record_run(
        run_id="run",
        session_id="session",
        project_id="project",
        project_name="Project",
        input_root=str(tmp_path),
        artifact_dir="",
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=3,
        metadata={},
    )
    store.replace_issue_summaries(
        "run",
        [
            {
                "issue_id": "error",
                "rule_id": "R-CROSS-PAGE-CONFLICT",
                "title": "Cross page conflict",
                "severity": "major",
                "status": "open",
                "confidence": 0.9,
                "sheet_no": "01",
                "evidence": {"handling_class": "error", "review_group_id": "G1"},
            },
            {
                "issue_id": "warning",
                "rule_id": "R-ONE-TO-MANY",
                "title": "Branch connection",
                "severity": "minor",
                "status": "open",
                "confidence": 0.8,
                "sheet_no": "02",
                "one_to_many_classification": "branch",
                "evidence": {"review_group_id": "G1"},
            },
            {
                "issue_id": "review",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "title": "100% all manual review",
                "severity": "review",
                "status": "resolved",
                "confidence": 0.4,
                "sheet_no": "03",
                "evidence": {"one_to_many_classification": "review", "review_group_id": "G2"},
            },
        ],
    )

    summary = store.load_project_summary("project", run_id="run")
    assert summary is not None
    assert summary["issue_count"] == 3
    assert summary["issue_stats"] == {
        "total": 3,
        "open_count": 2,
        "serious_open_count": 1,
        "resolved_count": 1,
        "error_count": 1,
        "warning_count": 1,
        "review_count": 1,
        "group_count": 2,
    }
    assert summary["filter_options"]["triages"] == ["branch", "review"]

    warning_page = store.load_project_issues_page(
        "project",
        run_id="run",
        limit=10,
        filters=IssueQueryFilters(handling="warning"),
    )
    assert warning_page is not None
    assert warning_page["total"] == 1
    assert [item["issue_id"] for item in warning_page["items"]] == ["warning"]

    search_page = store.load_project_issues_page(
        "project",
        run_id="run",
        limit=10,
        filters=IssueQueryFilters(search="100%"),
    )
    assert search_page is not None
    assert [item["issue_id"] for item in search_page["items"]] == ["review"]

    all_search_page = store.load_project_issues_page(
        "project",
        run_id="run",
        limit=10,
        filters=IssueQueryFilters(search="all"),
    )
    assert all_search_page is not None
    assert [item["issue_id"] for item in all_search_page["items"]] == ["review"]

    triage_page = store.load_project_issues_page(
        "project",
        run_id="run",
        limit=10,
        filters=IssueQueryFilters(triage="review"),
    )
    assert triage_page is not None
    assert [item["issue_id"] for item in triage_page["items"]] == ["review"]
    assert store.load_project_issue_detail("project", run_id="run", issue_id="missing") is None


def test_issue_page_count_and_rows_start_inside_one_read_transaction(tmp_path: Path) -> None:
    db_path = tmp_path / "desktop_state.db"
    store = DesktopStateStore(db_path)
    store.record_run(
        run_id="run",
        session_id="session",
        project_id="project",
        project_name="Project",
        input_root=str(tmp_path),
        artifact_dir="",
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={},
    )
    store.replace_issue_summaries(
        "run",
        [{"issue_id": "I1", "rule_id": "R", "title": "Issue", "severity": "review", "status": "open", "confidence": 0.5, "evidence": {}}],
    )
    traces: list[str] = []

    def connect() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.set_trace_callback(traces.append)
        return conn

    store._connect = connect  # type: ignore[method-assign]
    page = store.list_issue_summaries_page("run", limit=10)

    assert page["total"] == 1
    begin_index = next(index for index, statement in enumerate(traces) if statement == "BEGIN")
    count_index = next(index for index, statement in enumerate(traces) if "SELECT COUNT(*)" in statement)
    assert begin_index < count_index
