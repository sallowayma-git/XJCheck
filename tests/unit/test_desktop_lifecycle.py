from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd

from dwg_audit.desktop import preview as preview_module
from dwg_audit.desktop.lifecycle import cleanup_stale_workspaces
from dwg_audit.desktop.preview import _expand_focus_extent_for_pan
from dwg_audit.desktop.preview import build_preview_geometry_payloads
from dwg_audit.desktop.preview import render_project_preview
from dwg_audit.desktop.sidecar import cleanup_transient_workspaces
from dwg_audit.desktop.sidecar import compact_session_workspace
from dwg_audit.desktop.sidecar import delete_project_record
from dwg_audit.desktop.sidecar import load_project_result
from dwg_audit.desktop.sidecar import list_recent_projects
from dwg_audit.desktop.state_store import DesktopStateStore


def _issue_payload(**overrides):
    base = {
        "issue_id": "I1",
        "rule_id": "R-PAIR-LOW-CONFIDENCE",
        "issue_type": "pair_low_confidence",
        "title": "Low Confidence",
        "summary": "Low confidence pair",
        "explanation": "Pair score is below the automatic pass threshold.",
        "recommended_action": "Review both endpoint labels.",
        "severity": "review",
        "status": "open",
        "confidence": 0.74,
        "sheet_id": "S1",
        "file_id": "F1",
        "filename": "01.dwg",
        "sheet_no": "01",
        "line_group_id": "G1",
        "left_value": "101",
        "right_value": "201",
        "primary_pair_id": "P1",
        "one_to_many_classification": "review",
        "evidence": {
            "filename": "01.dwg",
            "sheet_no": "01",
            "line_start": [10.0, 20.0],
            "line_end": [90.0, 20.0],
        },
        "evidence_refs": [{"pair_id": "P1", "filename": "01.dwg", "sheet_no": "01"}],
        "related_pair_ids": ["P1"],
        "sheet_ids": ["S1"],
        "values": ["101", "201"],
    }
    base.update(overrides)
    return base


def _record_demo_run(store: DesktopStateStore, *, run_id: str, session_id: str, artifact_dir: str, issue=None) -> None:
    store.record_run(
        run_id=run_id,
        session_id=session_id,
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(Path(artifact_dir).parent if artifact_dir else Path(".")),
        artifact_dir=artifact_dir,
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={"demo": True},
    )
    store.replace_issue_summaries(run_id, [issue or _issue_payload()])


def test_compact_session_workspace_removes_conversion_dir_and_keeps_sqlite(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    session_id = "session-compact"
    artifact_dir = workspace_root / session_id / "demo_project"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "blob.bin").write_bytes(b"x" * 64)

    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id=f"{session_id}:demo-project",
        session_id=session_id,
        artifact_dir=str(artifact_dir),
    )

    result = compact_session_workspace(
        session_id=session_id,
        workspace_root=workspace_root,
        state_db_path=state_db,
    )
    assert result["removed_workspace"] is True
    assert result["updated_runs"] == 1
    assert not (workspace_root / session_id).exists()

    loaded = load_project_result(project_id="demo-project", state_db_path=state_db)
    assert loaded is not None
    assert loaded["issues"][0]["issue_id"] == "I1"
    assert str(loaded["run"].get("artifact_dir") or "") == ""


def test_cleanup_transient_workspaces_clears_sessions_and_preview_cache(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    preview_cache = tmp_path / "preview-cache"
    session_dir = workspace_root / "session-cleanup"
    artifact_dir = session_dir / "demo_project"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "tmp.dxf").write_text("0\nENDSEC\n", encoding="utf-8")
    preview_dir = preview_cache / "demo-project"
    preview_dir.mkdir(parents=True)
    (preview_dir / "S1_I1_issue.svg").write_text("<svg/>", encoding="utf-8")

    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id="session-cleanup:demo-project",
        session_id="session-cleanup",
        artifact_dir=str(artifact_dir),
    )

    payload = cleanup_transient_workspaces(
        workspace_root=workspace_root,
        state_db_path=state_db,
        preview_cache_root=preview_cache,
    )
    assert payload["cleared_artifact_dirs"] == 1
    assert payload["removed_sessions"] >= 1
    assert payload["removed_preview_cache"] is True
    assert payload["kept_issue_records"] is True
    assert not session_dir.exists()
    assert not preview_cache.exists()

    loaded = load_project_result(project_id="demo-project", state_db_path=state_db)
    assert loaded is not None
    assert loaded["issues"][0]["issue_id"] == "I1"
    assert str(loaded["run"].get("artifact_dir") or "") == ""


def test_cleanup_stale_workspaces_preserves_recent_session(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    old_session = workspace_root / "old-session"
    recent_session = workspace_root / "recent-session"
    old_session.mkdir(parents=True)
    recent_session.mkdir(parents=True)
    old_file = old_session / "temporary.dxf"
    recent_file = recent_session / "temporary.dxf"
    old_file.write_text("old", encoding="utf-8")
    recent_file.write_text("recent", encoding="utf-8")
    old_timestamp = time.time() - 7200
    os.utime(old_file, (old_timestamp, old_timestamp))
    os.utime(old_session, (old_timestamp, old_timestamp))

    payload = cleanup_stale_workspaces(
        workspace_root=workspace_root,
        state_db_path=state_db,
        older_than_seconds=3600,
    )

    assert payload["removed_sessions"] == 1
    assert payload["skipped_recent_sessions"] == 1
    assert not old_session.exists()
    assert recent_session.exists()


def test_delete_project_record_removes_sqlite_and_local_artifacts(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    preview_cache = tmp_path / "preview-cache"
    session_id = "session-delete"
    artifact_dir = workspace_root / session_id / "demo_project"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "keep-me.tmp").write_text("tmp", encoding="utf-8")
    preview_dir = preview_cache / "demo-project"
    preview_dir.mkdir(parents=True)
    (preview_dir / "preview.svg").write_text("<svg/>", encoding="utf-8")

    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id=f"{session_id}:demo-project",
        session_id=session_id,
        artifact_dir=str(artifact_dir),
        issue=_issue_payload(evidence={}),
    )

    payload = delete_project_record(
        project_id="demo-project",
        workspace_root=workspace_root,
        state_db_path=state_db,
        preview_cache_root=preview_cache,
    )
    assert payload["deleted_runs"] == 1
    assert not artifact_dir.exists()
    assert not preview_dir.exists()
    assert list_recent_projects(state_db_path=state_db) == []
    assert load_project_result(project_id="demo-project", state_db_path=state_db) is None


def test_expand_focus_extent_for_pan_adds_more_context_below() -> None:
    focus = (80.0, 40.0, 120.0, 60.0)
    expanded = _expand_focus_extent_for_pan(
        focus,
        page_extent=(0.0, 0.0, 200.0, 100.0),
        factor=2.1,
        downward_share=0.68,
    )

    assert round((expanded[2] - expanded[0]) / (focus[2] - focus[0]), 2) == 2.1
    assert round((expanded[3] - expanded[1]) / (focus[3] - focus[1]), 2) == 2.1
    assert focus[1] - expanded[1] > expanded[3] - focus[3]


def test_preview_geometry_payload_is_bounded_and_reports_original_count(monkeypatch) -> None:
    monkeypatch.setitem(preview_module._RETAINED_PREVIEW_LIMITS, "lines", 3)
    frames = {
        "lines": pd.DataFrame(
            [
                {
                    "line_id": f"L{index}",
                    "sheet_id": "S1",
                    "start_x": float(index),
                    "start_y": float(index),
                    "end_x": float(index + 1),
                    "end_y": float(index),
                }
                for index in range(6)
            ]
        )
    }

    payload = build_preview_geometry_payloads(frames)[0]

    assert [row["line_id"] for row in payload["lines"]] == ["L0", "L2", "L4"]
    assert payload["entity_counts"]["lines"] == {"total": 6, "retained": 3}


def test_preview_geometry_survives_compaction_and_is_purged_with_run(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    session_id = "session-geometry"
    run_id = f"{session_id}:demo-project"
    artifact_dir = workspace_root / session_id / "demo_project"
    artifact_dir.mkdir(parents=True)

    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id=run_id,
        session_id=session_id,
        artifact_dir=str(artifact_dir),
    )
    store.replace_preview_geometries(
        run_id,
        [{"schema_version": 1, "sheet_id": "S1", "pages": [], "lines": [], "texts": [], "line_groups": [], "blocks": []}],
    )

    compact_session_workspace(session_id=session_id, workspace_root=workspace_root, state_db_path=state_db)

    assert store.load_preview_geometry(run_id, "S1") is not None
    assert store.purge_project("demo-project") == 1
    assert store.load_preview_geometry(run_id, "S1") is None


def test_render_project_preview_uses_retained_geometry_without_artifacts(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    run_id = "session-geometry:demo-project"
    _record_demo_run(
        store,
        run_id=run_id,
        session_id="session-geometry",
        artifact_dir="",
    )
    store.replace_preview_geometries(
        run_id,
        [
            {
                "schema_version": 1,
                "sheet_id": "S1",
                "pages": [
                    {
                        "sheet_id": "S1",
                        "filename": "01.dwg",
                        "sheet_no": "01",
                        "sheet_title": "Demo Sheet",
                        "extent_bbox": [0.0, 0.0, 120.0, 80.0],
                        "frame_bbox": [0.0, 0.0, 120.0, 80.0],
                        "audit_area_bbox": [0.0, 0.0, 120.0, 80.0],
                    }
                ],
                "lines": [
                    {"line_id": "L1", "sheet_id": "S1", "start_x": 10.0, "start_y": 20.0, "end_x": 90.0, "end_y": 20.0},
                    {"line_id": "L2", "sheet_id": "S1", "start_x": 45.0, "start_y": 5.0, "end_x": 55.0, "end_y": 5.0},
                ],
                "texts": [
                    {
                        "text_id": "T-neighbor",
                        "sheet_id": "S1",
                        "text": "LOWER-CONNECTION",
                        "normalized_text": "LOWER-CONNECTION",
                        "is_numeric_candidate": False,
                        "height": 2.5,
                        "insert_x": 45.0,
                        "insert_y": 5.0,
                    }
                ],
                "line_groups": [],
                "blocks": [
                    {"block_id": "B1", "sheet_id": "S1", "name": "DEVICE-A", "insert_x": 50.0, "insert_y": 5.0}
                ],
            }
        ],
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    svg = Path(preview["preview_path"]).read_text(encoding="utf-8")
    assert preview["source"] == "sqlite_geometry"
    assert preview["viewport_scale"] == 2.1
    assert preview["overscan_factor"] == 2.1
    assert "LOWER-CONNECTION" in svg
    assert 'id="page-blocks"' in svg
    assert "DEVICE-A" in svg


def test_render_project_preview_uses_sqlite_evidence_without_artifacts(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id="session-a:demo-project",
        session_id="session-a",
        artifact_dir="",
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )
    preview_path = Path(preview["preview_path"])
    assert preview_path.exists()
    svg = preview_path.read_text(encoding="utf-8")
    assert "<svg" in svg
    assert 'id="issue-highlight"' in svg
    assert "view=issue-crop" in svg
    assert preview.get("cropped_to_issue") is True
    assert preview.get("source") == "sqlite_evidence"
    assert isinstance(preview.get("focus_bbox"), list)
    assert len(preview["focus_bbox"]) == 4


def test_render_project_preview_uses_summary_when_sqlite_issue_has_no_coordinates(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id="session-a:demo-project",
        session_id="session-a",
        artifact_dir="",
        issue=_issue_payload(
            title="多对一配对",
            summary="多个端子映射到同一个右值。",
            filename="30 右侧端子图1.dwg",
            sheet_no="30",
            left_value="1U2D-13",
            right_value="1ID13",
            evidence={
                "filename": "30 右侧端子图1.dwg",
                "sheet_no": "30",
                "sheet_title": "RIGHT TERMINAL 1",
                "pair_evidence": {"line_orientation": "table"},
            },
        ),
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    preview_path = Path(preview["preview_path"])
    assert preview_path.exists()
    svg = preview_path.read_text(encoding="utf-8")
    assert "view=unlocated-summary" in svg
    assert "多对一配对" in svg
    assert "30 右侧端子图1.dwg" in svg
    assert "端子 1U2D-13 → 1ID13" in svg
    assert "无坐标定位" in svg
    assert preview["source"] == "sqlite_summary"
    assert preview["focus_bbox"] is None
    assert preview["cropped_to_issue"] is False
    assert preview["lightweight"] is True
