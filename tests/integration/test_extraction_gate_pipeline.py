from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from dwg_audit.pipeline import analyze_input_root
from dwg_audit.report.rerun import rerun_audit_from_findings
from dwg_audit.utils.config import load_config


def test_pipeline_persists_incomplete_extraction_machine_status(tmp_path: Path) -> None:
    project = tmp_path / "incomplete_project"
    project.mkdir()
    (project / "04 回路图.dwg").write_bytes(b"BROKEN")
    output_dir = tmp_path / "artifacts"

    class EventSink:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict[str, object]]] = []

        def emit(self, event_type: str, **payload: object) -> None:
            self.events.append((event_type, payload))

    event_sink = EventSink()
    analyze_input_root(
        project,
        output_dir,
        load_config(),
        logging.getLogger("test_extraction_gate_pipeline"),
        event_sink=event_sink,
    )

    run_summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    project_summary = run_summary[0]
    project_dir = Path(project_summary["artifact_dir"])
    gate_payload = json.loads(
        (project_dir / "extraction_completeness.json").read_text(encoding="utf-8")
    )
    findings_payload = json.loads(
        (project_dir / "findings" / "findings.json").read_text(encoding="utf-8")
    )

    assert project_summary["analysis_status"] == "INCOMPLETE_EXTRACTION"
    assert project_summary["clean_conclusion_allowed"] is False
    assert project_summary["incomplete_page_count"] == 1
    assert project_summary["failure_code_counts"] == {"INVALID_SOURCE_HEADER": 1}
    assert gate_payload["analysis_status"] == "INCOMPLETE_EXTRACTION"
    assert gate_payload["incomplete_sheet_ids"] == ["S0001"]
    assert gate_payload["pages"][0]["failure_codes"] == ["INVALID_SOURCE_HEADER"]
    assert findings_payload["analysis_status"] == "INCOMPLETE_EXTRACTION"
    assert findings_payload["clean_conclusion_allowed"] is False
    assert findings_payload["incomplete_page_count"] == 1
    assert findings_payload["failure_code_counts"] == {"INVALID_SOURCE_HEADER": 1}
    assert findings_payload["page_findings"][0]["extraction_status"] == "INCOMPLETE_EXTRACTION"
    assert findings_payload["page_findings"][0]["failure_codes"] == ["INVALID_SOURCE_HEADER"]
    incomplete_events = [payload for name, payload in event_sink.events if name == "incomplete_extraction"]
    assert incomplete_events == [
        {
            "project_root": str(project.resolve()),
            "analysis_status": "INCOMPLETE_EXTRACTION",
            "incomplete_page_count": 1,
            "failure_code_counts": {"INVALID_SOURCE_HEADER": 1},
        }
    ]
    finished_event = next(payload for name, payload in event_sink.events if name == "project_finished")
    assert finished_event["analysis_status"] == "INCOMPLETE_EXTRACTION"
    assert finished_event["clean_conclusion_allowed"] is False

    audit_dir = rerun_audit_from_findings(project_dir, load_config())
    issues = pd.read_parquet(audit_dir / "issues.parquet")
    assert len(pd.read_parquet(project_dir / "findings" / "pairs.parquet")) == 0
    assert set(issues["rule_id"]) == {"R-DATA-INCOMPLETE-EXTRACTION"}
    assert issues.iloc[0]["status"] == "review"
    assert issues.iloc[0]["pair_id"] is None
