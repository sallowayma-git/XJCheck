from pathlib import Path

import pytest

from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.lifecycle import session_lease, cleanup_stale_workspaces, cleanup_transient_workspaces


def project(session, name="project", *, geometries=None):
    return {"run": dict(run_id=f"{session}:{name}", session_id=session, project_id=name,
        project_name=name, input_root="C:/user/input", artifact_dir="", status="completed",
        sheet_count=1, pair_count=1, issue_count=1),
        "issues": [{"issue_id": "I1", "title": session}],
        "pages": [{"sheet_id": "S1"}],
        "geometries": geometries if geometries is not None else [{"sheet_id": "S1", "schema_version": 2}]}


def test_twenty_batches_retain_only_current_snapshot_and_bounded_recent_projects(tmp_path):
    store = DesktopStateStore(tmp_path / "state.db")
    for n in range(25):
        items = [project(f"s{n}", f"p{n}"), project(f"s{n}", "repeat")]
        for item in items:
            item.update(project_root=item["run"]["project_id"], page_facts={"page": {"fingerprint": f"s{n}"}})
        store.commit_session_snapshot(f"s{n}", items)
    assert {r["session_id"] for r in store.list_all_runs()} == {"s24"}
    recent = store.list_recent_projects()
    assert len(recent) == 20
    assert sum(r["snapshot_available"] for r in recent) == 2
    with store._connect() as conn:
        for table in ("runs", "issue_summaries", "page_findings", "preview_geometries", "page_facts"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 2
    assert store.load_current_page_facts()["repeat"]["page"]["fingerprint"] == "s24"


def test_second_project_failure_rolls_back_whole_batch(tmp_path):
    store = DesktopStateStore(tmp_path / "state.db")
    store.commit_session_snapshot("old", [project("old")])
    invalid = project("new", "bad", geometries=[{"sheet_id": "S1", "schema_version": 999}])
    with pytest.raises(ValueError, match="unsupported preview"):
        store.commit_session_snapshot("new", [project("new"), invalid])
    result = store.load_latest_project_result("project")
    assert result["run"]["session_id"] == "old"
    assert result["issues"][0]["title"] == "old"
    assert store.load_preview_geometry("old:project", "S1") is not None
    assert len(store.list_recent_projects()) == 1


def test_incomplete_batch_does_not_replace_success(tmp_path):
    store = DesktopStateStore(tmp_path / "state.db")
    store.commit_session_snapshot("old", [project("old")])
    unfinished = project("new")
    unfinished["run"]["status"] = "incomplete"
    with pytest.raises(ValueError, match="incomplete"):
        store.commit_session_snapshot("new", [unfinished])
    assert store.list_all_runs()[0]["session_id"] == "old"
    empty = project("empty")
    empty["run"]["sheet_count"] = 0
    with pytest.raises(ValueError, match="without drawing pages"):
        store.commit_session_snapshot("empty", [empty])
    assert store.list_all_runs()[0]["session_id"] == "old"


def test_sqlite_reuses_free_pages_and_compacts_only_large_idle_space(tmp_path):
    import os
    store = DesktopStateStore(tmp_path / "state.db")
    store.commit_session_snapshot("old", [project("old")])
    with store._connect() as conn:
        conn.execute("INSERT INTO page_facts VALUES (?, ?, ?)", ("old:project", "source", os.urandom(34 * 1024 * 1024)))
    large_size = store.db_path.stat().st_size
    store.commit_session_snapshot("new", [project("new")])
    assert store.db_path.stat().st_size == large_size  # freed pages remain available for reuse
    info = store.compact_database_if_needed()
    assert info["vacuumed"] and info["free_bytes"] > 32 * 1024 * 1024
    assert store.db_path.stat().st_size < large_size / 4
    assert store.load_latest_project_result("project")["issues"][0]["title"] == "new"
    assert not store.compact_database_if_needed()["vacuumed"]


def test_cleanup_skips_live_workspace_and_recovers_after_lease_released(tmp_path):
    root = tmp_path / "sessions"
    session = root / "live"
    session.mkdir(parents=True)
    (session / "work.dxf").write_text("work")
    db = tmp_path / "state.db"
    with session_lease(root, "live"):
        result = cleanup_stale_workspaces(workspace_root=root, state_db_path=db, older_than_seconds=0)
        assert result["skipped_active"]
        assert (session / "work.dxf").exists()
        assert cleanup_transient_workspaces(workspace_root=root, state_db_path=db)["skipped_active"]
    cleanup_stale_workspaces(workspace_root=root, state_db_path=db, older_than_seconds=0)
    assert not session.exists()


def test_persisted_artifact_path_cannot_authorize_deleting_input(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "original.dwg").write_bytes(b"source")
    store = DesktopStateStore(tmp_path / "state.db")
    payload = project("old")
    payload["run"].update(input_root=str(source), artifact_dir=str(source))
    store.commit_session_snapshot("old", [payload])
    cleanup_transient_workspaces(workspace_root=tmp_path / "sessions", state_db_path=store.db_path,
        preview_cache_root=tmp_path / "previews")
    assert (source / "original.dwg").read_bytes() == b"source"


def test_legacy_database_migration_retains_latest_complete_session(tmp_path):
    path = tmp_path / "state.db"
    store = DesktopStateStore(path)
    for session in ("old", "latest"):
        payload = project(session)
        store.record_run(**payload["run"])
        store.replace_issue_summaries(payload["run"]["run_id"], payload["issues"])
    with store._connect() as conn:
        conn.execute("DROP TABLE desktop_schema")
    migrated = DesktopStateStore(path)
    assert {r["session_id"] for r in migrated.list_all_runs()} == {"latest"}
    assert migrated.load_latest_project_result("project")["issues"][0]["title"] == "latest"


def test_migration_does_not_treat_one_finished_project_as_a_successful_batch(tmp_path):
    path = tmp_path / "state.db"
    store = DesktopStateStore(path)
    store.commit_session_snapshot("good", [project("good")])
    store.record_run(**project("partial", "finished")["run"])
    failed = project("partial", "failed")
    failed["run"]["status"] = "incomplete"
    store.record_run(**failed["run"])
    with store._connect() as conn:
        conn.execute("DELETE FROM desktop_schema WHERE key='single_snapshot_v2'")
    migrated = DesktopStateStore(path)
    assert {r["session_id"] for r in migrated.list_all_runs()} == {"good"}
    assert migrated.load_latest_project_result("project")["issues"][0]["title"] == "good"
    assert not next(r for r in migrated.list_recent_projects() if r["project_id"] == "finished")["snapshot_available"]
