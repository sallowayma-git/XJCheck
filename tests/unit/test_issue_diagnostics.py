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
                    "line_group_id": "G1",
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
                    "line_group_id": "G2",
                    "left_value": None,
                    "right_value": "127",
                    "pair_kind": "ordinary_pair",
                    "evidence": json.dumps({"pair_kind": "ordinary_pair"}),
                },
                {
                    "pair_id": "P3",
                    "sheet_id": "S2",
                    "line_group_id": "G3",
                    "left_value": "43",
                    "right_value": "419",
                    "pair_kind": "ordinary_pair",
                    "evidence": json.dumps({"pair_kind": "ordinary_pair"}),
                },
                {
                    "pair_id": "P4",
                    "sheet_id": "S1",
                    "line_group_id": "G4",
                    "left_value": None,
                    "right_value": "705",
                    "pair_kind": "ordinary_pair",
                    "evidence": json.dumps({"pair_kind": "ordinary_pair"}),
                },
                {
                    "pair_id": "P5",
                    "sheet_id": "S1",
                    "line_group_id": "G5",
                    "left_value": "721",
                    "right_value": "721",
                    "pair_kind": "ordinary_pair",
                    "evidence": json.dumps({"pair_kind": "ordinary_pair"}),
                },
            ]
        ),
        "line_groups": pd.DataFrame(
            [
                {"line_group_id": "G1", "orientation": "horizontal", "row_band_id": None},
                {"line_group_id": "G2", "orientation": "horizontal", "row_band_id": None},
                {"line_group_id": "G3", "orientation": "vertical", "row_band_id": None},
                {"line_group_id": "G4", "orientation": "grid", "row_band_id": "RBW0022"},
                {"line_group_id": "G5", "orientation": "grid", "row_band_id": "RBW0014"},
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
            {
                "issue_id": "I4",
                "rule_id": "R-PAIR-MISSING-SIDE",
                "sheet_id": "S1",
                "pair_id": "P4",
                "filename": "05 交流回路图2.dwg",
                "sheet_no": "05",
                "left_value": None,
                "right_value": "705",
                "evidence": {
                    "pair_evidence": {
                        "line_group_id": "G4",
                        "line_orientation": "grid",
                        "row_band_id": "RBW0022",
                    }
                },
            },
            {
                "issue_id": "I5",
                "rule_id": "R-PAIR-LOW-CONFIDENCE",
                "sheet_id": "S1",
                "pair_id": "P5",
                "filename": "05 交流回路图2.dwg",
                "sheet_no": "05",
                "left_value": "721",
                "right_value": "721",
                "evidence": {
                    "pair_evidence": {
                        "line_group_id": "G5",
                        "line_orientation": "grid",
                        "row_band_id": "RBW0014",
                    }
                },
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
    assert by_id["I4"]["root_cause"] == "pairing_wrong"
    assert "grid_row_band_endpoint_gap" in by_id["I4"]["diagnostic_tags"]
    assert by_id["I4"]["diagnostic_context"]["row_band_id"] == "RBW0022"
    assert by_id["I5"]["root_cause"] == "pairing_wrong"
    assert "row_band:RBW0014" in by_id["I5"]["diagnostic_tags"]


def test_enrich_issues_with_root_causes_classifies_cross_page_table_mapping_as_rule_review() -> None:
    frames = _diagnostic_frames()
    frames["pairs"] = pd.concat(
        [
            frames["pairs"],
            pd.DataFrame(
                [
                    {
                        "pair_id": "P4",
                        "sheet_id": "S1",
                        "left_value": "NDY306A-3",
                        "right_value": "1QD1",
                        "pair_kind": "table_mapping",
                        "evidence": json.dumps(
                            {
                                "source": "table_mapping",
                                "table_mapping": {
                                    "mapping_mode": "backplate_virtual_table",
                                    "header_prefix": "NDY306A",
                                },
                            }
                        ),
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    issues = pd.DataFrame(
        [
            {
                "issue_id": "I4",
                "rule_id": "R-CROSS-PAGE-CONFLICT",
                "sheet_id": "S1",
                "pair_id": "P4",
                "filename": "17 差动保护背板图.dwg",
                "sheet_no": "17",
                "left_value": "NDY306A-3",
                "right_value": "1QD1",
                "evidence": {
                    "one_to_many_classification": "backplate_table_scope_review",
                    "table_mapping_mode": "backplate_virtual_table",
                },
            },
        ]
    )

    enriched = enrich_issues_with_root_causes(frames, issues)

    row = enriched.iloc[0]
    assert row["root_cause"] == "rule_too_strict"
    assert row["pair_kind"] == "table_mapping"
    assert "specialized_relation_rule_review" in row["diagnostic_tags"]


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
        "pairing_wrong": 3,
    }
    assert summary["rule_root_cause_counts"]["R-PAIR-MISSING-SIDE"] == {"pairing_wrong": 2}
