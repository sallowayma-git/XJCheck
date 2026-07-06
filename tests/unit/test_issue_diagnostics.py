from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.services.issue_diagnostics import enrich_issues_with_root_causes
from dwg_audit.services.issue_diagnostics import write_issue_root_cause_audit


def _diagnostic_frames() -> dict[str, pd.DataFrame]:
    return {
        "pages": pd.DataFrame(
            [
                {
                    "sheet_id": "S1",
                    "filename": "08 信号回路.dwg",
                    "sheet_no": "08",
                    "page_type": "二次原理图",
                    "page_subtype": "grid_heavy_wire_diagram",
                    "route_target": "WireDiagramExtractor",
                    "audit_disposition": "audit_required",
                },
                {
                    "sheet_id": "S2",
                    "filename": "20 元件接线图2.dwg",
                    "sheet_no": "20",
                    "page_type": "元件接线图",
                    "page_subtype": "vertical_component",
                    "route_target": "ComponentDiagramExtractor",
                    "audit_disposition": "audit_required",
                },
            ]
        ),
        "pairs": pd.DataFrame(
            [
                {
                    "pair_id": "P1",
                    "sheet_id": "S1",
                    "left_value": "1",
                    "right_value": "116",
                    "left_candidate_id": "C1",
                    "right_candidate_id": "C2",
                    "pair_kind": "ordinary_pair",
                    "evidence": json.dumps({"pair_kind": "ordinary_pair"}),
                },
                {
                    "pair_id": "P2",
                    "sheet_id": "S1",
                    "left_value": None,
                    "right_value": "127",
                    "pair_kind": "ordinary_pair",
                    "evidence": json.dumps({"pair_kind": "ordinary_pair"}),
                },
                {
                    "pair_id": "P3",
                    "sheet_id": "S2",
                    "left_value": "43",
                    "right_value": "419",
                    "pair_kind": "ordinary_pair",
                    "evidence": json.dumps({"pair_kind": "ordinary_pair"}),
                },
            ]
        ),
        "terminal_candidates": pd.DataFrame(
            [
                {
                    "candidate_id": "C1",
                    "text_id": "T1",
                    "channel": "terminal_numeric_channel",
                    "source_block_name": None,
                },
                {
                    "candidate_id": "C2",
                    "text_id": "T2",
                    "channel": "terminal_numeric_channel",
                    "source_block_name": None,
                },
            ]
        ),
        "texts": pd.DataFrame(
            [
                {"text_id": "T1", "layer": "DIM"},
                {"text_id": "T2", "layer": "0"},
            ]
        ),
    }


def _issues_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "issue_id": "I1",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "sheet_id": "S1",
                "pair_id": "P1",
                "filename": "08 信号回路.dwg",
                "sheet_no": "08",
                "left_value": "1",
                "right_value": "116",
                "evidence": {},
            },
            {
                "issue_id": "I2",
                "rule_id": "R-PAIR-MISSING-SIDE",
                "sheet_id": "S1",
                "pair_id": "P2",
                "filename": "08 信号回路.dwg",
                "sheet_no": "08",
                "left_value": None,
                "right_value": "127",
                "evidence": {"chain_kind": "complementary_half_pair", "bridge_gap": 12.5},
            },
            {
                "issue_id": "I3",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "sheet_id": "S2",
                "pair_id": "P3",
                "filename": "20 元件接线图2.dwg",
                "sheet_no": "20",
                "left_value": "43",
                "right_value": "419",
                "evidence": {},
            },
        ]
    )


def test_enrich_issues_with_root_causes_classifies_core_symptoms() -> None:
    enriched = enrich_issues_with_root_causes(_diagnostic_frames(), _issues_frame())

    by_id = {row["issue_id"]: row for _, row in enriched.iterrows()}
    assert by_id["I1"]["root_cause"] == "candidate_noise"
    assert "text_layer:DIM" in by_id["I1"]["diagnostic_tags"]
    assert by_id["I2"]["root_cause"] == "pairing_wrong"
    assert by_id["I2"]["diagnostic_context"]["bridge_gap"] == 12.5
    assert by_id["I3"]["root_cause"] == "extractor_missing"
    assert by_id["I3"]["route_target"] == "ComponentDiagramExtractor"


def test_write_issue_root_cause_audit_persists_summary(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    enriched = write_issue_root_cause_audit(project_dir, _diagnostic_frames(), _issues_frame())
    audit_dir = project_dir / "audit"

    assert (audit_dir / "issues.parquet").exists()
    assert (audit_dir / "issues.json").exists()
    assert (audit_dir / "issue_root_cause_audit.json").exists()
    assert (audit_dir / "issue_root_cause_audit.md").exists()
    assert "root_cause" in enriched.columns

    summary = json.loads((audit_dir / "issue_root_cause_audit.json").read_text(encoding="utf-8"))
    assert summary["root_cause_counts"] == {
        "candidate_noise": 1,
        "extractor_missing": 1,
        "pairing_wrong": 1,
    }
    assert summary["rule_root_cause_counts"]["R-PAIR-MISSING-SIDE"] == {"pairing_wrong": 1}
