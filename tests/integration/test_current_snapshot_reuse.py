import json
import zlib
from io import StringIO
from pathlib import Path

import ezdxf
import pandas as pd

from dwg_audit.desktop.sidecar import analyze_session, DesktopEventWriter
from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.services.execution import run_analysis_workflow


def test_snapshot_reuses_results_after_cleanup_and_reaudits_changed_pages(tmp_path, monkeypatch):
    project = tmp_path / "input"
    project.mkdir()
    sources = [project / f"0{n} 控制回路图.dwg" for n in (4, 5)]
    for path in sources:
        path.write_bytes(b"AC1018-original")
    executable = tmp_path / "ODA.exe"
    executable.write_bytes(b"stub")
    conversions = []
    def convert(source, target, **_kwargs):
        conversions.append((source.name, source.read_bytes()))
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_lwpolyline([(-50, -50), (100, -50), (100, 100), (-50, 100)], close=True)
        msp.add_line((0, 40), (40, 40))
        msp.add_text("1XD1", dxfattribs={"insert": (0, 40), "height": 2})
        value = "2n200" if source.read_bytes().endswith(b"changed") else "2n100"
        msp.add_text(value, dxfattribs={"insert": (40, 40), "height": 2})
        doc.saveas(target)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter._detect_odafc_exe", lambda _c: executable)
    monkeypatch.setattr("dwg_audit.ingest.dwg_converter.odafc.convert", convert)
    db = tmp_path / "state.db"
    workspace = tmp_path / "sessions"
    def run(session, *, compact=True):
        return analyze_session(input_root=project, workspace_root=workspace, session_id=session,
            state_db_path=db, event_writer=DesktopEventWriter(StringIO()), compact_after_store=compact)
    run("first")
    assert not (workspace / "first").exists()
    assert len(conversions) == 2
    import dwg_audit.report.rerun as rerun
    original_audit = rerun.build_issues
    audits = []
    def audit(*args, **kwargs):
        audits.append(True)
        return original_audit(*args, **kwargs)
    monkeypatch.setattr(rerun, "build_issues", audit)
    import dwg_audit.pipeline as pipeline
    with monkeypatch.context() as exact:
        exact.setattr(pipeline, "extract_wire_pairs", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("Recognition repeated")))
        second = run("same", compact=False)
    assert len(conversions) == 2 and len(audits) == 1
    perf = json.loads((Path(second[0]["artifact_dir"]) / "performance.json").read_text(encoding="utf-8"))
    assert perf["stage_seconds"]["reused_page_count"] == 2
    # A readable but incomplete relation payload must recompute recognition,
    # while still retaining valid page facts and avoiding CAD conversion.
    from dwg_audit.extract.cad_extract import encode_page_facts
    store = DesktopStateStore(db)
    cache = store.load_current_page_facts()[str(project.resolve())]
    cache["_relations"]["facts"] = encode_page_facts({"pairs": []})
    with store._connect() as connection:
        connection.execute("UPDATE page_facts SET facts_blob = ?", (zlib.compress(json.dumps(cache).encode()),))
    run("bad-relations", compact=False)
    assert len(conversions) == 2 and len(audits) == 2
    sources[1].write_bytes(b"AC1018-changed")
    third = run("changed", compact=False)
    assert len(conversions) == 3 and conversions[-1][1] == b"AC1018-changed"
    changed_dir = Path(third[0]["artifact_dir"])
    assert json.loads((changed_dir / "performance.json").read_text(encoding="utf-8"))["stage_seconds"]["reused_page_count"] == 1
    full = run_analysis_workflow(input_root=project, output_root=tmp_path / "full")
    for name in ("pairs", "line_groups"):
        a = pd.read_parquet(changed_dir / "findings" / f"{name}.parquet")
        b = pd.read_parquet(full.project_dirs[0] / "findings" / f"{name}.parquet")
        pd.testing.assert_frame_equal(a, b)
    assert json.loads((changed_dir / "audit/issues.json").read_text(encoding="utf-8")) == json.loads((full.project_dirs[0] / "audit/issues.json").read_text(encoding="utf-8"))
    store = DesktopStateStore(db)
    assert {r["session_id"] for r in store.list_all_runs()} == {"changed"}
    assert len(store.load_current_page_facts()) == 1
