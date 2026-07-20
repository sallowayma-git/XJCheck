from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from dwg_audit.desktop.sidecar_entry import _configure_text_stream_utf8
from dwg_audit.desktop.sidecar_entry import _run_lightweight_command
from dwg_audit.desktop.sidecar_entry import _run_oda_worker_command


REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_ROOT = REPO_ROOT / "apps" / "desktop"


def test_tauri_bundle_declares_sidecar_and_oda_resource_directories() -> None:
    config = json.loads((DESKTOP_ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))

    resources = config["bundle"]["resources"]

    assert resources["resources/sidecar/*"] == "sidecar/"
    assert resources["resources/oda/*"] == "oda/"
    # Tauri flattens a recursive glob into its destination. Map the Qt plugin
    # directory explicitly so qwindows.dll remains under oda/platforms/.
    assert resources["resources/oda/platforms/*"] == "oda/platforms/"
    assert config["bundle"]["targets"] == "nsis"


def test_sidecar_packaging_hook_matches_runtime_candidates() -> None:
    script = (DESKTOP_ROOT / "scripts" / "build-sidecar.ps1").read_text(encoding="utf-8")
    builder = (DESKTOP_ROOT / "scripts" / "build_sidecar_pyinstaller.py").read_text(
        encoding="utf-8"
    )
    runtime = (DESKTOP_ROOT / "src-tauri" / "src" / "sidecar_runtime.rs").read_text(encoding="utf-8")

    assert "dwg-audit-sidecar" in script
    assert "src-tauri\\resources\\sidecar" in script
    assert "build_sidecar_pyinstaller.py" in script
    assert "ezdxf.addons.odafc" in builder
    assert '"dwg_audit.desktop.sidecar"' in builder
    assert '"dwg_audit.desktop.lifecycle"' in builder
    assert '"dwg_audit.readers.oda_worker"' in builder
    assert "Frozen sidecar ODA worker smoke" in script
    assert "unsupported-test-operation" in script
    assert "WaitForExit(15000)" in script
    assert "taskkill.exe" in script
    assert "/T /F" in script
    assert "WaitForExit(2000)" in script
    # Console-subsystem sidecar preserves JSON pipes; CREATE_NO_WINDOW prevents flashes.
    assert "console=True" in builder
    assert "console=False" not in builder
    assert "sidecar" in runtime
    assert "dwg-audit-sidecar.exe" in runtime
    assert "CREATE_NO_WINDOW" in runtime
    assert "Stdio::null()" in runtime
    assert "ODAFC_PATH" in runtime
    assert "DWG_AUDIT_RESOURCE_DIR" in runtime
    assert "oda" in runtime
    assert "dwg_audit.desktop.sidecar_entry" in runtime

    main_rs = (DESKTOP_ROOT / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    assert 'windows_subsystem = "windows"' in main_rs

    assert "PREVIEW_GATE" in main_rs
    assert "PREVIEW_TIMEOUT" in main_rs
    assert "Preview request superseded" in main_rs
    assert "desktop_cancel_preview" in main_rs
    assert "desktop_cancel_result_load" in main_rs
    assert "ExitRequested" in main_rs
    assert "taskkill" in main_rs
    assert "drain_preview_pipe" in main_rs
    assert "ACTIVE_SIDECAR_PIDS" in main_rs
    assert "force_shutdown" in main_rs
    assert "CreateToolhelp32Snapshot" in main_rs
    assert "terminate_descendant_processes" in main_rs
    assert "TerminateProcess" in main_rs
    assert "client_session_epoch" in main_rs
    assert "ResultProcessControl" in main_rs
    assert "std::process::exit(0)" in main_rs

    app_tsx = (DESKTOP_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
    assert ".onCloseRequested" not in app_tsx
    assert "desktopApi.loadResultSummary" in app_tsx
    assert "desktopApi.loadResultIssues" in app_tsx
    assert "desktopApi.loadResult(projectId)" not in app_tsx
    assert "desktopApi.cancelResultLoad" in app_tsx
    assert "measureElement" in app_tsx


def test_oda_staging_and_release_scripts_exist() -> None:
    stage = (DESKTOP_ROOT / "scripts" / "stage-oda-resources.ps1").read_text(encoding="utf-8")
    release = (DESKTOP_ROOT / "scripts" / "build-windows-release.ps1").read_text(encoding="utf-8")
    oda_readme = (DESKTOP_ROOT / "src-tauri" / "resources" / "oda" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "ODAFileConverter.exe" in stage
    assert "platforms\\qwindows.dll" in stage
    assert "resources\\oda" in stage
    assert "stage-oda-resources.ps1" in release
    assert "platforms\\qwindows.dll" in release
    assert "build-sidecar.ps1" in release
    assert "tauri:build" in release
    assert "do not commit binaries" in oda_readme.lower() or "Binary ODA" in oda_readme


def test_python_sidecar_entrypoint_uses_existing_cli_contract() -> None:
    entrypoint = REPO_ROOT / "src" / "dwg_audit" / "desktop" / "sidecar_entry.py"
    content = entrypoint.read_text(encoding="utf-8")

    assert "from dwg_audit.cli import run" in content
    assert "run()" in content


def test_python_sidecar_entrypoint_dispatches_frozen_oda_worker(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_worker(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr("dwg_audit.readers.oda_worker.main", fake_worker)

    assert _run_oda_worker_command(["other-command"]) is None
    assert _run_oda_worker_command(["oda-worker"]) == 0
    assert calls == [[]]


def test_recent_projects_effect_runs_once_per_app_mount() -> None:
    app_tsx = (DESKTOP_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
    desktop_api = (DESKTOP_ROOT / "src" / "lib" / "desktopApi.ts").read_text(encoding="utf-8")

    assert re.search(
        r"useEffect\(\(\) => \{\s*void refreshRecentProjects\(\)\s*\}, \[\]\)",
        app_tsx,
    )
    assert "[refreshRecentProjects]" not in app_tsx
    assert "[handleDroppedPaths, screen]" not in app_tsx
    assert "[applyProcessEvents]" not in app_tsx
    assert "await refreshRecentProjects()" not in app_tsx
    assert "analysisInFlightRef.current" in app_tsx
    assert "return await this.loadResult(projectId)" not in desktop_api


def test_preview_commands_use_request_scoped_ownership() -> None:
    main_rs = (DESKTOP_ROOT / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    app_tsx = (DESKTOP_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
    desktop_api = (DESKTOP_ROOT / "src" / "lib" / "desktopApi.ts").read_text(encoding="utf-8")

    assert re.search(r"async fn desktop_render_preview\([^)]*request_id: String", main_rs)
    assert re.search(
        r"fn desktop_register_preview_session\([^)]*client_session_id: String",
        main_rs,
    )
    assert re.search(
        r"fn desktop_cancel_preview\([^)]*request_id: String,[^)]*request_generation: u64",
        main_rs,
    )
    assert "struct PreviewState" in main_rs
    assert "struct PreviewToken" in main_rs
    assert "ACTIVE_PREVIEW_PID" not in main_rs
    assert "PREVIEW_GENERATION" not in main_rs
    assert "known_client_sessions" in main_rs
    assert "client_session_epoch: Option<u64>" in main_rs
    assert "activate_client_session" not in main_rs

    assert "COMMANDS.registerPreviewSession" in desktop_api
    assert "async registerPreviewSession(clientSessionId: string): Promise<number>" in desktop_api
    assert re.search(
        r"COMMANDS\.renderPreview,\s*\{[^{}]*requestId,[^{}]*requestGeneration,",
        desktop_api,
        re.DOTALL,
    )
    assert re.search(
        r"cancelPreview\(\s*requestId: string,\s*requestGeneration: number,\s*clientSessionId:",
        desktop_api,
    )
    assert re.search(
        r"COMMANDS\.cancelPreview,\s*\{\s*requestId,\s*requestGeneration,\s*clientSessionId,\s*clientSessionEpoch,?",
        desktop_api,
    )
    assert "preview.request_id !== requestId" in app_tsx
    assert "previewClientSessionId" in app_tsx
    assert "previewClientSessionEpoch" in app_tsx
    assert "createPreviewContextKey" in app_tsx
    assert "normalized.project_id !== projectId" in desktop_api
    assert "normalized.issue_id !== issueId" in desktop_api
    assert "previewMode" in app_tsx
    assert "projectLoadGenerationRef" in app_tsx
    assert app_tsx.count("isCurrentRequest(projectLoadGenerationRef.current, generation)") >= 2


def test_python_sidecar_entrypoint_forces_utf8_output() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="gb18030")

    _configure_text_stream_utf8(stream)
    stream.write("多对一配对")
    stream.flush()

    assert stream.encoding.lower().replace("-", "") == "utf8"
    assert raw.getvalue().decode("utf-8") == "多对一配对"


def test_python_sidecar_entrypoint_lists_projects_without_full_cli(tmp_path: Path, capsys) -> None:
    state_db = tmp_path / "desktop_state.db"

    handled = _run_lightweight_command(
        ["list-recent-projects", "--state-db", str(state_db)]
    )

    assert handled is True
    assert json.loads(capsys.readouterr().out) == {"projects": []}


def test_python_sidecar_entrypoint_cleans_workspace_without_full_cli(tmp_path: Path, capsys) -> None:
    state_db = tmp_path / "desktop_state.db"
    workspace = tmp_path / "sessions"
    session = workspace / "abandoned-session"
    session.mkdir(parents=True)
    (session / "temporary.dxf").write_text("0\nEOF\n", encoding="utf-8")

    handled = _run_lightweight_command(
        [
            "cleanup-workspaces",
            "--workspace-root",
            str(workspace),
            "--state-db",
            str(state_db),
        ]
    )

    assert handled is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["removed_sessions"] == 1
    assert payload["kept_issue_records"] is True
    assert not session.exists()


def test_python_sidecar_entrypoint_updates_compact_issue_without_full_cli(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    updated: dict[str, str] = {}

    class FakeStore:
        def __init__(self, _db_path: Path) -> None:
            pass

        def list_runs_for_project(self, project_id: str):
            assert project_id == "demo-project"
            return [{"run_id": "session-a:demo-project", "artifact_dir": ""}]

        def update_issue_status(self, *, run_id: str, issue_id: str, status: str):
            updated.update(run_id=run_id, issue_id=issue_id, status=status)
            return {"issue_id": issue_id, "status": status}

    monkeypatch.setattr("dwg_audit.desktop.state_store.DesktopStateStore", FakeStore)

    handled = _run_lightweight_command(
        [
            "set-issue-status",
            "--project-id",
            "demo-project",
            "--issue-id",
            "I1",
            "--status",
            "resolved",
            "--state-db",
            str(tmp_path / "desktop_state.db"),
        ]
    )

    assert handled is True
    assert updated == {
        "run_id": "session-a:demo-project",
        "issue_id": "I1",
        "status": "resolved",
    }
    assert json.loads(capsys.readouterr().out)["status"] == "resolved"


def test_desktop_state_store_import_does_not_load_analysis_stack() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import dwg_audit.desktop.state_store; "
                "assert 'pandas' not in sys.modules; "
                "assert 'dwg_audit.cli' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr


def test_default_config_does_not_hardcode_machine_oda_install() -> None:
    config_py = (REPO_ROOT / "src" / "dwg_audit" / "utils" / "config.py").read_text(encoding="utf-8")
    default_yml = (REPO_ROOT / "configs" / "default.yml").read_text(encoding="utf-8")

    assert '"odafc_path": ""' in config_py
    assert 'odafc_path: ""' in default_yml
    assert "Program Files\\ODA" not in config_py
    assert "Program Files\\ODA" not in default_yml


def test_sidecar_build_avoids_collect_all_bloat() -> None:
    script = (DESKTOP_ROOT / "scripts" / "build-sidecar.ps1").read_text(encoding="utf-8")
    builder = (DESKTOP_ROOT / "scripts" / "build_sidecar_pyinstaller.py").read_text(encoding="utf-8")

    # Size-first path uses the filtered builder, not CLI collect-all flags.
    assert "build_sidecar_pyinstaller.py" in script
    code_lines = [line for line in script.splitlines() if not line.lstrip().startswith("#")]
    assert all("--collect-all" not in line for line in code_lines)
    assert "arrow_flight" in builder
    assert "streamlit" in builder
    assert "ezdxf.addons.odafc" in builder
    assert "pyarrow.flight" in builder
    # Unused / optional dependency pruning
    assert '"networkx"' in builder or "'networkx'" in builder
    assert "PIL" in builder  # excluded optional drawing stack
    assert "fontTools" in builder  # kept: ezdxf fonts require it
    assert "pygments" in builder
    assert "include/pyarrow" in builder


def test_oda_stage_prunes_optional_payloads() -> None:
    stage = (DESKTOP_ROOT / "scripts" / "stage-oda-resources.ps1").read_text(encoding="utf-8")

    assert "Optional payload prune" in stage
    assert "ModelerGeometry_27.1_16.tx" in stage
    assert "imageformats" in stage
    assert "W3Dtk.dll" in stage
    # Conversion-critical dim-block module must not be pruned.
    removals = stage.split("OptionalRemovals")[1] if "OptionalRemovals" in stage else stage
    assert "RecomputeDimBlock" not in removals



def test_result_pagination_contract_connects_python_cli_rust_and_frontend() -> None:
    """The Paginated result API must be plumbed through all three layers.

    Asserts that new lightweight subcommands were added to the dispatcher, the
    Rust side registered matching Tauri commands, the desktopApi exposed typed
    wrappers with the right COMMANDS entries, and the loader/sidecar functions
    in Python support the contract.
    """

    entry_path = REPO_ROOT / "src" / "dwg_audit" / "desktop" / "sidecar_entry.py"
    entry = entry_path.read_text(encoding="utf-8")
    assert '"load-result-summary"' in entry
    assert '"load-result-issues"' in entry
    assert '"load-result-issue-detail"' in entry
    assert "_bounded_page_size" in entry

    sidecar_path = REPO_ROOT / "src" / "dwg_audit" / "desktop" / "sidecar.py"
    sidecar = sidecar_path.read_text(encoding="utf-8")
    assert "def load_project_summary(" in sidecar
    assert "def load_project_issues(" in sidecar
    assert "def load_project_issue_detail(" in sidecar

    store_path = REPO_ROOT / "src" / "dwg_audit" / "desktop" / "state_store.py"
    store = store_path.read_text(encoding="utf-8")
    assert "def latest_run_for_project(" in store
    assert "def count_issues(" in store
    assert "def list_issue_summaries_page(" in store
    assert "def load_issue_summary(" in store
    assert "def count_page_findings(" in store

    main_rs_path = DESKTOP_ROOT / "src-tauri" / "src" / "main.rs"
    main_rs = main_rs_path.read_text(encoding="utf-8")
    assert "async fn desktop_load_result_summary(" in main_rs
    assert "async fn desktop_load_result_issues(" in main_rs
    assert "async fn desktop_load_result_issue_detail(" in main_rs
    assert "desktop_load_result_summary" in main_rs
    assert "desktop_load_result_issues" in main_rs
    assert "desktop_load_result_issue_detail" in main_rs
    assert "desktop_cancel_result_load" in main_rs
    assert '"--run-id"' in main_rs
    assert '"load-result-summary".to_string()' in main_rs
    assert '"load-result-issues".to_string()' in main_rs
    assert '"load-result-issue-detail".to_string()' in main_rs

    desktop_api_path = DESKTOP_ROOT / "src" / "lib" / "desktopApi.ts"
    desktop_api = desktop_api_path.read_text(encoding="utf-8")
    assert "loadResultSummary:" in desktop_api
    assert "loadResultIssues:" in desktop_api
    assert "loadResultIssueDetail:" in desktop_api
    assert "cancelResultLoad:" in desktop_api
    assert "async loadResultSummary(" in desktop_api
    assert re.search(
        r"async loadResultIssues\(\s*\n?\s*projectId: string,",
        desktop_api,
    )
    assert "function normalizeIssueSummary(issue: IssueSummary): IssueSummary" in desktop_api

    types_path = DESKTOP_ROOT / "src" / "types.ts"
    types = types_path.read_text(encoding="utf-8")
    assert "export type ProjectSummary" in types
    assert "export type IssuePage" in types
    assert "export type IssueDetail" in types


def test_python_lightweight_command_loads_result_summary(tmp_path: Path, capsys, monkeypatch) -> None:
    """`load-result-summary` must NOT touch issue_summaries rows. Just counts."""

    from dwg_audit.desktop.sidecar_entry import _run_lightweight_command

    state_db = tmp_path / "desktop_state.db"

    # Write a run directly then have the dispatcher read it through the store.
    from dwg_audit.desktop.state_store import DesktopStateStore

    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="demo-run",
        session_id="demo-session",
        project_id="demo-project",
        project_name="Demo",
        input_root=str(tmp_path),
        artifact_dir="",
        status="completed",
        sheet_count=2,
        pair_count=3,
        issue_count=5,
        metadata={},
    )
    store.replace_issue_summaries(
        "demo-run",
        [
            {
                "issue_id": f"I{i}",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "issue_type": "pair_low_confidence",
                "title": f"Issue {i}",
                "summary": f"summary {i}",
                "severity": "minor",
                "status": "open",
                "confidence": 0.1 * i,
                "evidence": {},
                "evidence_refs": [],
                "related_pair_ids": [],
                "sheet_ids": [],
                "values": [],
            }
            for i in range(5)
        ],
    )

    handled = _run_lightweight_command([
        "load-result-summary", "--project-id", "demo-project", "--run-id", "demo-run", "--state-db", str(state_db)
    ])

    assert handled is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["run_id"] == "demo-run"
    assert payload["issue_count"] == 5


def test_python_lightweight_command_paginates_issues(tmp_path: Path, capsys) -> None:
    from dwg_audit.desktop.sidecar_entry import _run_lightweight_command

    from dwg_audit.desktop.state_store import DesktopStateStore

    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="demo-run",
        session_id="demo-session",
        project_id="demo-project",
        project_name="Demo",
        input_root=str(tmp_path),
        artifact_dir="",
        status="completed",
        sheet_count=2,
        pair_count=3,
        issue_count=30,
        metadata={},
    )
    issues = [
        {
            "issue_id": f"I{i:03d}",
            "rule_id": "R-PAIR-LOW-CONFIDENCE",
            "issue_type": "pair_low_confidence",
            "title": f"Issue {i}",
            "summary": f"summary {i}",
            "severity": "minor",
            "status": "open",
            "confidence": 0.1,
            "evidence": {},
            "evidence_refs": [],
            "related_pair_ids": [],
            "sheet_ids": [],
            "values": [],
        }
        for i in range(30)
    ]
    store.replace_issue_summaries("demo-run", issues)

    handled = _run_lightweight_command(
        [
            "load-result-issues",
            "--project-id",
            "demo-project",
            "--run-id",
            "demo-run",
            "--limit",
            "10",
            "--offset",
            "5",
            "--state-db",
            str(state_db),
        ]
    )

    assert handled is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["run_id"] == "demo-run"
    assert payload["total"] == 30
    assert payload["limit"] == 10
    assert payload["offset"] == 5
    ids = [item["issue_id"] for item in payload["items"]]
    # Sorted by severity asc (all 'minor') → confidence desc → issue_id asc.
    # With identical confidence, issue_id asc dominates; offset 5 of 30 picks rows 5-14.
    assert ids == [f"I{i:03d}" for i in range(5, 15)]

    handled = _run_lightweight_command(
        [
            "load-result-issues",
            "--project-id",
            "demo-project",
            "--run-id",
            "demo-run",
            "--limit",
            "10",
            "--search",
            "summary 17",
            "--handling",
            "review",
            "--state-db",
            str(state_db),
        ]
    )
    assert handled is True
    filtered = json.loads(capsys.readouterr().out)
    assert filtered["total"] == 1
    assert [item["issue_id"] for item in filtered["items"]] == ["I017"]


def test_python_lightweight_command_loads_issue_detail(tmp_path: Path, capsys) -> None:
    from dwg_audit.desktop.sidecar_entry import _run_lightweight_command

    from dwg_audit.desktop.state_store import DesktopStateStore

    state_db = tmp_path / "desktop_state.db"
    store = DesktopStateStore(state_db)
    store.record_run(
        run_id="demo-run",
        session_id="demo-session",
        project_id="demo-project",
        project_name="Demo",
        input_root=str(tmp_path),
        artifact_dir="",
        status="completed",
        sheet_count=2,
        pair_count=3,
        issue_count=1,
        metadata={},
    )
    store.replace_issue_summaries(
        "demo-run",
        [
            {
                "issue_id": "I7",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "issue_type": "pair_low_confidence",
                "title": "Specific issue",
                "summary": "target-summary",
                "severity": "minor",
                "status": "open",
                "confidence": 0.4,
                "evidence": {"handling_class": "review"},
                "evidence_refs": [],
                "related_pair_ids": [],
                "sheet_ids": [],
                "values": [],
            }
        ],
    )

    handled = _run_lightweight_command(
        [
            "load-result-issue-detail",
            "--project-id",
            "demo-project",
            "--issue-id",
            "I7",
            "--run-id",
            "demo-run",
            "--state-db",
            str(state_db),
        ]
    )

    assert handled is True
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["run_id"] == "demo-run"
    assert payload["issue"]["issue_id"] == "I7"
    assert payload["issue"]["summary"] == "target-summary"
    assert payload["issue"]["handling_class"] == "review"

    handled = _run_lightweight_command(
        [
            "load-result-issue-detail",
            "--project-id",
            "demo-project",
            "--issue-id",
            "missing",
            "--run-id",
            "demo-run",
            "--state-db",
            str(state_db),
        ]
    )
    assert handled is True
    assert json.loads(capsys.readouterr().out) is None
