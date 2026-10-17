import io
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_audit.desktop import sidecar as sidecar_module
from dwg_audit.desktop.sidecar import DesktopEventWriter
from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.desktop.lifecycle import session_lease, cleanup_stale_workspaces, cleanup_transient_workspaces
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.ingest.project_scanner import discover_project_roots, scan_project
from dwg_audit.report.artifacts import write_project_artifacts
from dwg_audit.utils.config import DEFAULT_CONFIG


def project(session, name="project", *, geometries=None):
    return {"run": dict(run_id=f"{session}:{name}", session_id=session, project_id=name,
        project_name=name, input_root="C:/user/input", artifact_dir="", status="completed",
        sheet_count=1, pair_count=1, issue_count=1),
        "issues": [{"issue_id": "I1", "rule_id": "R-PAIR-LOW-CONFIDENCE", "title": session}],
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


def test_multi_project_snapshot_disambiguates_unicode_slug_collisions(tmp_path, monkeypatch):
    input_root = tmp_path / "项目 空间（全角）" / "多项目 总目录（审计）"
    project_names = ("110kV线路保护柜（单跳圈）", "110kV线路保护柜（双跳圈）")
    for name in project_names:
        project_root = input_root / name
        project_root.mkdir(parents=True)
        (project_root / "01 交流回路图.dwg").write_bytes(b"AC1018demo")

    production_config = deepcopy(DEFAULT_CONFIG)
    production_config["runtime"]["profile"] = "production"

    def fake_analysis_workflow(**kwargs):
        discovered = discover_project_roots(kwargs["input_root"])
        return SimpleNamespace(
            project_dirs=[
                write_project_artifacts(
                    ProjectArtifacts(scan=scan_project(root, production_config)),
                    kwargs["output_root"],
                    config=production_config,
                )
                for root in discovered
            ]
        )

    monkeypatch.setattr(sidecar_module, "run_analysis_workflow", fake_analysis_workflow)
    db_path = tmp_path / "desktop_state.db"
    result = sidecar_module.analyze_session(
        input_root=input_root,
        workspace_root=tmp_path / "sessions",
        state_db_path=db_path,
        session_id="session-multi-unicode",
        event_writer=DesktopEventWriter(io.StringIO()),
        compact_after_store=False,
    )

    store = DesktopStateStore(db_path)
    runs = store.list_all_runs()
    assert {run["project_id"] for run in runs} == set(project_names)
    assert len({run["artifact_dir"] for run in runs}) == 2
    assert all(run["session_id"] == "session-multi-unicode" for run in runs)
    assert len(result) == 2
    manifests = [
        (Path(run["artifact_dir"]) / "manifest.json").read_text(encoding="utf-8")
        for run in runs
    ]
    assert all(any(f'"project_id": "{name}"' in raw for raw in manifests) for name in project_names)


def test_crashed_workspace_lock_is_recovered_without_removing_saved_session(tmp_path):
    root = tmp_path / "sessions"
    crashed_session = root / "crashed-session"
    crashed_session.mkdir(parents=True)
    saved_state = tmp_path / "state.db"
    store = DesktopStateStore(saved_state)
    store.commit_session_snapshot("saved-session", [project("saved-session")])

    source_root = Path(__file__).resolve().parents[2] / "src"
    code = """
import os
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from dwg_audit.desktop.lifecycle import session_lease
root = Path(sys.argv[2])
session = Path(sys.argv[3])
with session_lease(root, "crashed-session"):
    (session / "unfinished.dxf").write_text("temporary", encoding="utf-8")
    os._exit(0)
"""
    subprocess.run(
        [sys.executable, "-c", code, str(source_root), str(root), str(crashed_session)],
        check=True,
    )

    assert (root.parent / ".sessions.workspace.lock").exists()
    cleanup_stale_workspaces(workspace_root=root, state_db_path=saved_state, older_than_seconds=0)

    assert not crashed_session.exists()
    assert [run["session_id"] for run in store.list_all_runs()] == ["saved-session"]
    assert store.load_latest_project_result("project")["run"]["session_id"] == "saved-session"


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
