from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import pytest

from dwg_audit.desktop import preview as preview_module
from dwg_audit.desktop import sidecar as sidecar_module
from dwg_audit.desktop.lifecycle import cleanup_stale_workspaces
from dwg_audit.desktop.lifecycle import session_lease
from dwg_audit.desktop.preview import _expand_focus_extent_for_pan
from dwg_audit.desktop.preview import build_preview_geometry_payloads
from dwg_audit.desktop.preview import _normalize_focus_boxes
from dwg_audit.desktop.preview import render_project_preview
from dwg_audit.desktop.sidecar import cleanup_transient_workspaces
from dwg_audit.desktop.sidecar import compact_session_workspace
from dwg_audit.desktop.sidecar import delete_project_record
from dwg_audit.desktop.sidecar import delete_project_records
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


def _record_demo_run(
    store: DesktopStateStore,
    *,
    run_id: str,
    session_id: str,
    artifact_dir: str,
    issue=None,
    series_chains=None,
) -> None:
    store.record_run(
        run_id=run_id,
        session_id=session_id,
        project_id="demo-project",
        project_name="Demo Project",
        input_root=str(Path(artifact_dir).parents[2] / "input" if artifact_dir else Path(".")),
        artifact_dir=artifact_dir,
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={"demo": True},
        series_chains=series_chains,
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
        series_chains={"chain_count": 1, "chains": [{"junction_value": "1UD1"}]},
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
    assert loaded["series_chains"] == {"chain_count": 1, "chains": [{"junction_value": "1UD1"}]}
    assert str(loaded["run"].get("artifact_dir") or "") == ""


def test_store_project_run_keeps_chain_json_for_desktop_result(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "project"
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    findings_dir.mkdir(parents=True)
    audit_dir.mkdir()
    (project_dir / "manifest.json").write_text(
        json.dumps({"project_id": "demo-project", "project_name": "Demo Project", "sheet_count": 1}),
        encoding="utf-8",
    )
    (findings_dir / "findings.json").write_text(
        json.dumps({"page_findings": [], "page_findings_count": 0}),
        encoding="utf-8",
    )
    chain_report = {"chain_count": 1, "continuation_count": 0, "chains": [{"junction_value": "1UD1"}]}
    (audit_dir / "series_chains.json").write_text(json.dumps(chain_report), encoding="utf-8")
    (audit_dir / "recognition_gap_diagnostics.jsonl").write_text(
        json.dumps(
            {
                "issue_id": "GAP-1",
                "rule_id": "R-RECOGNITION-GAP",
                "title": "Unresolved endpoint",
                "severity": "review",
                "status": "open",
                "confidence": 0.2,
                "sheet_id": "S1",
                "evidence": {"presentation": "terminal", "reason_codes": ["unresolved_endpoint_identity"]},
            }
        ) + "\n",
        encoding="utf-8",
    )
    empty_frames = {name: pd.DataFrame() for name in ("pairs", "issues", "pages", "lines", "texts", "line_groups", "blocks")}
    monkeypatch.setattr(sidecar_module, "load_report_frames", lambda *_args, **_kwargs: empty_frames)
    monkeypatch.setattr(sidecar_module, "build_preview_geometry_payloads", lambda _frames: [])

    store = DesktopStateStore(tmp_path / "desktop_state.db")
    sidecar_module._store_project_run(
        store,
        session_id="session-chain",
        project_dir=project_dir,
        input_root=tmp_path,
        include_audit=True,
    )

    loaded = store.load_latest_project_result("demo-project")
    assert loaded is not None
    assert loaded["series_chains"] == chain_report
    diagnostics = store.load_project_diagnostics_page("demo-project", run_id="session-chain:demo-project")
    assert diagnostics is not None
    assert diagnostics["total"] == 1
    assert diagnostics["items"][0]["issue_id"] == "GAP-1"


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


def _record_project(store: DesktopStateStore, *, project_id: str, artifact_dir: Path) -> None:
    session_id = f"session-{project_id}"
    store.record_run(
        run_id=f"{session_id}:{project_id}",
        session_id=session_id,
        project_id=project_id,
        project_name=project_id,
        input_root=str(artifact_dir.parent / "input"),
        artifact_dir=str(artifact_dir),
        status="completed",
        sheet_count=1,
        pair_count=1,
        issue_count=1,
        metadata={"demo": True},
    )
    store.replace_issue_summaries(f"{session_id}:{project_id}", [_issue_payload(evidence={})])


def test_delete_project_records_batch_removes_each_and_treats_missing_as_done(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    store = DesktopStateStore(state_db)
    artifact_dirs = {}
    for project_id in ("alpha-project", "beta-project"):
        artifact_dir = workspace_root / f"session-{project_id}" / project_id
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "tmp.txt").write_text("tmp", encoding="utf-8")
        artifact_dirs[project_id] = artifact_dir
        _record_project(store, project_id=project_id, artifact_dir=artifact_dir)

    payload = delete_project_records(
        project_ids=["alpha-project", "ghost-project", "beta-project"],
        workspace_root=workspace_root,
        state_db_path=state_db,
    )

    assert [item["project_id"] for item in payload["results"]] == ["alpha-project", "ghost-project", "beta-project"]
    assert all(item["ok"] for item in payload["results"])
    ghost = payload["results"][1]
    assert ghost["not_found"] is True
    assert payload["results"][0]["deleted_runs"] == 1
    assert payload["deleted_count"] == 3
    assert payload["failed_count"] == 0
    assert not artifact_dirs["alpha-project"].exists()
    assert not artifact_dirs["beta-project"].exists()
    assert list_recent_projects(state_db_path=state_db) == []


def test_delete_project_records_reports_failure_per_project_and_continues(tmp_path: Path, monkeypatch) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    store = DesktopStateStore(state_db)
    for project_id in ("alpha-project", "bad-project", "gamma-project"):
        artifact_dir = workspace_root / f"session-{project_id}" / project_id
        artifact_dir.mkdir(parents=True)
        _record_project(store, project_id=project_id, artifact_dir=artifact_dir)

    original = sidecar_module._delete_project_record_unlocked

    def flaky(*, project_id, **kwargs):
        if project_id == "bad-project":
            raise RuntimeError("disk unavailable")
        return original(project_id=project_id, **kwargs)

    monkeypatch.setattr(sidecar_module, "_delete_project_record_unlocked", flaky)

    payload = delete_project_records(
        project_ids=["bad-project", "alpha-project", "gamma-project"],
        workspace_root=workspace_root,
        state_db_path=state_db,
    )

    by_id = {item["project_id"]: item for item in payload["results"]}
    assert by_id["bad-project"]["ok"] is False
    assert "disk unavailable" in by_id["bad-project"]["error"]
    assert by_id["alpha-project"]["ok"] is True
    assert by_id["gamma-project"]["ok"] is True
    assert payload["failed_count"] == 1
    assert payload["deleted_count"] == 2
    remaining = {item["project_id"] for item in list_recent_projects(state_db_path=state_db)}
    assert remaining == {"bad-project"}


def test_delete_project_records_refuses_while_analysis_holds_workspace(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace_root = tmp_path / "workspace"
    store = DesktopStateStore(state_db)
    artifact_dir = workspace_root / "session-alpha" / "alpha-project"
    artifact_dir.mkdir(parents=True)
    _record_project(store, project_id="alpha-project", artifact_dir=artifact_dir)

    with session_lease(workspace_root, "analysis"):
        with pytest.raises(BlockingIOError):
            delete_project_records(
                project_ids=["alpha-project"],
                workspace_root=workspace_root,
                state_db_path=state_db,
            )

    assert artifact_dir.exists()
    assert [item["project_id"] for item in list_recent_projects(state_db_path=state_db)] == ["alpha-project"]


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
    assert preview["viewport_scale"] == 2.52
    assert preview["overscan_factor"] == 2.52
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


def _focus_geometry_payload() -> list[dict]:
    return [
        {
            "schema_version": 1,
            "sheet_id": "S1",
            "pages": [
                {
                    "sheet_id": "S1",
                    "filename": "01.dwg",
                    "sheet_no": "01",
                    "sheet_title": "Focus Sheet",
                    "extent_bbox": [0.0, 0.0, 200.0, 100.0],
                    "frame_bbox": [0.0, 0.0, 200.0, 100.0],
                    "audit_area_bbox": [0.0, 0.0, 200.0, 100.0],
                }
            ],
            "lines": [
                {"line_id": "L1", "sheet_id": "S1", "start_x": 20.0, "start_y": 20.0, "end_x": 40.0, "end_y": 20.0},
                {"line_id": "L2", "sheet_id": "S1", "start_x": 150.0, "start_y": 65.0, "end_x": 170.0, "end_y": 65.0},
            ],
            "texts": [],
            "line_groups": [],
            "blocks": [],
        }
    ]


def test_render_project_preview_focus_bboxes_draws_each_location_box(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    run_id = "session-focus:demo-project"
    _record_demo_run(store, run_id=run_id, session_id="session-focus", artifact_dir="")
    store.replace_preview_geometries(run_id, _focus_geometry_payload())
    boxes = [[15.0, 15.0, 45.0, 25.0], [145.0, 60.0, 175.0, 70.0]]

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        sheet_id="S1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
        focus_bboxes=boxes,
    )

    svg = Path(preview["preview_path"]).read_text(encoding="utf-8")
    assert preview["cropped_to_issue"] is True
    assert 'data-focus-count="2"' in svg
    assert svg.count("data-focus-index=") == 2
    assert ">A</text>" in svg and ">B</text>" in svg
    focus = preview["focus_bbox"]
    for x0, y0, x1, y1 in boxes:
        assert focus[0] <= x0 and focus[1] <= y0 and focus[2] >= x1 and focus[3] >= y1


def test_render_project_preview_drops_malformed_focus_boxes(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    run_id = "session-focus-one:demo-project"
    _record_demo_run(store, run_id=run_id, session_id="session-focus-one", artifact_dir="")
    store.replace_preview_geometries(run_id, _focus_geometry_payload())

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        sheet_id="S1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
        focus_bboxes=[[15.0, 15.0, 45.0, 25.0], [15.0, 15.0, 45.0, 25.0], ["bad"]],
    )

    svg = Path(preview["preview_path"]).read_text(encoding="utf-8")
    assert 'data-focus-count="2"' in svg
    assert ">A</text>" in svg
    assert _normalize_focus_boxes([[45, 25, 15, 15], [1, 2, 3], [0, 0, float("nan"), 1]]) == [(15.0, 15.0, 45.0, 25.0)]


def test_render_project_preview_focus_boxes_work_without_an_issue(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    run_id = "session-focus-sheet:demo-project"
    _record_demo_run(store, run_id=run_id, session_id="session-focus-sheet", artifact_dir="")
    store.replace_preview_geometries(run_id, _focus_geometry_payload())

    preview = render_project_preview(
        project_id="demo-project",
        sheet_id="S1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
        focus_bboxes=[[145.0, 60.0, 175.0, 70.0]],
    )

    svg = Path(preview["preview_path"]).read_text(encoding="utf-8")
    assert preview["cropped_to_issue"] is True
    assert preview["issue_id"] is None
    assert 'data-focus-count="1"' in svg
    focus = preview["focus_bbox"]
    assert focus[0] <= 145.0 and focus[2] >= 175.0 and focus[1] <= 60.0 and focus[3] >= 70.0



_LOCATED_EVIDENCE = {
    "filename": "01.dwg",
    "sheet_no": "01",
    "locations": [
        {
            "location_id": "L1",
            "role": "wire",
            "sheet_id": "S1",
            "file_id": "F1",
            "filename": "01.dwg",
            "sheet_no": "01",
            "sheet_title": "",
            "sheet_order": 1,
            "terminal": None,
            "peer": None,
            "text_id": None,
            "point": None,
            "bbox": [10.0, 20.0, 90.0, 40.0],
            "renderable": True,
        }
    ],
}


def test_render_project_preview_flags_missing_sheet_geometry_for_located_issue(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id="session-a:demo-project",
        session_id="session-a",
        artifact_dir="",
        issue=_issue_payload(evidence=dict(_LOCATED_EVIDENCE)),
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    assert preview["source"] == "sqlite_summary"
    assert preview["geometry_missing"] is True
    assert preview["geometry_missing_message"] == "该图纸几何数据缺失，请重新校验项目"


def test_render_project_preview_does_not_flag_unlocated_issue_as_missing_geometry(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    _record_demo_run(
        store,
        run_id="session-a:demo-project",
        session_id="session-a",
        artifact_dir="",
        issue=_issue_payload(evidence={}),
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    assert preview["source"] == "sqlite_summary"
    assert preview["geometry_missing"] is False
    assert preview["geometry_missing_message"] is None


def test_render_project_preview_does_not_flag_missing_geometry_when_sheet_geometry_is_retained(tmp_path: Path) -> None:
    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    run_id = "session-a:demo-project"
    _record_demo_run(
        store,
        run_id=run_id,
        session_id="session-a",
        artifact_dir="",
        issue=_issue_payload(evidence=dict(_LOCATED_EVIDENCE)),
    )
    store.replace_preview_geometries(
        run_id,
        [{"schema_version": 1, "sheet_id": "S1", "pages": [], "lines": [], "texts": [], "line_groups": [], "blocks": []}],
    )

    preview = render_project_preview(
        project_id="demo-project",
        issue_id="I1",
        state_db_path=state_db,
        output_dir=tmp_path / "previews",
    )

    assert preview["source"] == "sqlite_summary"
    assert preview["geometry_missing"] is False
    assert preview["geometry_missing_message"] is None
