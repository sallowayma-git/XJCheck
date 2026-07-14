from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dwg_audit.report.electrical_connection_review_pack import MACHINE_PROPOSED
from dwg_audit.report.electrical_connection_review_pack import SCHEMA_VERSION
from dwg_audit.report.electrical_connection_review_pack import build_electrical_connection_proposals
from dwg_audit.report.electrical_connection_review_pack import validate_electrical_connection_review_pack
from dwg_audit.report.electrical_connection_review_pack import write_electrical_connection_review_pack


def test_machine_proposed_pack_is_valid_but_never_authoritative(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "pack"

    result = write_electrical_connection_review_pack(
        project,
        project_id="P001",
        split="calibration_legacy",
        output_dir=pack_dir,
        max_proposals=20,
    )
    validation = validate_electrical_connection_review_pack(pack_dir)

    assert result["summary"]["proposal_count"] > 0
    assert result["summary"]["promotion_ready"] is False
    assert result["summary"]["certification_ready"] is False
    assert result["summary"]["critical_issue_eligible_count"] == 0
    assert result["summary"]["electrical_union_eligible_count"] == 0
    assert validation.valid is True
    assert validation.promotion_ready is False
    assert validation.certification_ready is False
    assert validation.human_confirmed_count == 0
    assert validation.machine_proposed_count == validation.proposal_count

    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["annotation_status"] == MACHINE_PROPOSED
    assert manifest["not_a_human_gold_standard"] is True
    assert manifest["primary_engine_unchanged"] is True
    assert (pack_dir / "HUMAN_REVIEW_CHECKLIST.md").is_file()

    proposals = json.loads((pack_dir / "proposals.json").read_text(encoding="utf-8"))[
        "proposals"
    ]
    assert all(row["annotation_status"] == MACHINE_PROPOSED for row in proposals)
    assert all(row["human_decision"] == "PENDING" for row in proposals)
    assert all(row["shadow_only"] is True for row in proposals)
    assert all(row["taskbook_citations"] for row in proposals)
    assert all(row["evidence_refs"] for row in proposals)


def test_ranking_prefers_ambiguous_cross_page_and_respects_max(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    proposals = build_electrical_connection_proposals(
        project,
        project_id="P001",
        split="calibration_legacy",
        max_proposals=3,
    )

    assert len(proposals) == 3
    assert proposals[0]["family"] == "CROSS_PAGE_ENDPOINT_MATCH"
    assert proposals[0]["labels"][0] == "103"
    assert proposals[0]["review_order"] == 1
    assert "LABEL_ALTERNATIVES_3" in proposals[0]["reason_codes"]


def test_family_quota_keeps_mixed_evidence_when_cross_page_dominates(
    tmp_path: Path,
) -> None:
    project = _project_bundle(tmp_path)
    # Inflate cross-page volume so raw top-N would exclude other families.
    findings = project / "findings"
    frame = pd.read_parquet(findings / "cross_page_endpoint_candidates_v1.parquet")
    rows = frame.to_dict(orient="records")
    for index in range(40):
        rows.append(
            {
                "match_id": f"XPM-extra-{index}",
                "label": f"X{index}",
                "sheet_id_a": "S010",
                "endpoint_id_a": f"EP-XA-{index}",
                "sheet_id_b": "S011",
                "endpoint_id_b": f"EP-XB-{index}",
                "relation": "CROSS_PAGE_LABEL",
                "state": "CANDIDATE",
                "reciprocal": True,
                "confidence": 0.99,
                "reason_codes": '["SHARED_AUTHORITATIVE_LABEL"]',
            }
        )
    pd.DataFrame(rows).to_parquet(
        findings / "cross_page_endpoint_candidates_v1.parquet", index=False
    )

    proposals = build_electrical_connection_proposals(
        project,
        project_id="P001",
        split="calibration_legacy",
        max_proposals=10,
    )
    families = {row["family"] for row in proposals}
    assert "CROSS_PAGE_ENDPOINT_MATCH" in families
    assert "SEMANTIC_ATTACHMENT_REVIEW" in families
    assert "OPEN_ENDPOINT_LABEL" in families
    assert "LEGACY_PAIR_CONNECTION_REVIEW" in families
    assert len(proposals) == 10


def test_human_status_or_union_flags_fail_closed(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "pack"
    write_electrical_connection_review_pack(
        project,
        project_id="P001",
        split="calibration_legacy",
        output_dir=pack_dir,
        max_proposals=5,
    )
    proposals_path = pack_dir / "proposals.json"
    payload = json.loads(proposals_path.read_text(encoding="utf-8"))
    payload["proposals"][0]["annotation_status"] = "HUMAN_CONFIRMED"
    payload["proposals"][0]["electrical_union_eligible"] = True
    proposals_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    validation = validate_electrical_connection_review_pack(pack_dir)

    assert validation.valid is False
    assert validation.promotion_ready is False
    assert any("HUMAN_STATUS_FORBIDDEN" in err for err in validation.errors)
    assert any("UNION_ELIGIBLE" in err for err in validation.errors)


def test_missing_findings_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="findings directory not found"):
        build_electrical_connection_proposals(
            tmp_path / "empty",
            project_id="P001",
            split="calibration_legacy",
        )


def test_heldout_split_is_marked_evaluation_only(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "heldout_pack"
    result = write_electrical_connection_review_pack(
        project,
        project_id="P002",
        split="heldout_test",
        output_dir=pack_dir,
        max_proposals=5,
    )
    assert result["manifest"]["heldout_evaluation_only"] is True
    assert result["manifest"]["heldout_usage"] == "evaluation_only_never_tuning"
    assert all(row["heldout_evaluation_only"] is True for row in result["proposals"])


def _project_bundle(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    findings = project / "findings"
    findings.mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "match_id": "XPM-1",
                "label": "103",
                "sheet_id_a": "S001",
                "endpoint_id_a": "EP-A1",
                "sheet_id_b": "S002",
                "endpoint_id_b": "EP-B1",
                "relation": "CROSS_PAGE_LABEL",
                "state": "CANDIDATE",
                "reciprocal": True,
                "confidence": 0.95,
                "reason_codes": '["SHARED_AUTHORITATIVE_LABEL"]',
            },
            {
                "match_id": "XPM-2",
                "label": "103",
                "sheet_id_a": "S001",
                "endpoint_id_a": "EP-A1",
                "sheet_id_b": "S003",
                "endpoint_id_b": "EP-B2",
                "relation": "CROSS_PAGE_LABEL",
                "state": "CANDIDATE",
                "reciprocal": True,
                "confidence": 0.9,
                "reason_codes": '["SHARED_AUTHORITATIVE_LABEL"]',
            },
            {
                "match_id": "XPM-3",
                "label": "103",
                "sheet_id_a": "S002",
                "endpoint_id_a": "EP-B1",
                "sheet_id_b": "S003",
                "endpoint_id_b": "EP-B2",
                "relation": "CROSS_PAGE_LABEL",
                "state": "CANDIDATE",
                "reciprocal": True,
                "confidence": 0.85,
                "reason_codes": '["SHARED_AUTHORITATIVE_LABEL"]',
            },
            {
                "match_id": "XPM-4",
                "label": "1-1N",
                "sheet_id_a": "S004",
                "endpoint_id_a": "EP-C1",
                "sheet_id_b": "S005",
                "endpoint_id_b": "EP-C2",
                "relation": "CROSS_PAGE_LABEL",
                "state": "CANDIDATE",
                "reciprocal": True,
                "confidence": 1.0,
                "reason_codes": '["SHARED_AUTHORITATIVE_LABEL"]',
            },
        ]
    ).to_parquet(findings / "cross_page_endpoint_candidates_v1.parquet", index=False)

    pd.DataFrame(
        [
            {
                "endpoint_id": "EP-OPEN-1",
                "sheet_id": "S001",
                "node_id": "N1",
                "electrical_network_id": "EN1",
                "coord_x": 10.0,
                "coord_y": 20.0,
                "source_line_ids": '["L1"]',
                "source_handles": '["H1"]',
                "boundary_state": "OPEN",
                "identity_kind": "NETWORK_OPEN",
                "namespace": "sheet:S001",
                "local_key": "N1",
                "label": "105",
                "attached_token_id": "TK1",
                "attached_token_kind": "TERMINAL_LOCAL",
                "attached_token_text": "105",
                "attachment_id": "SA1",
                "authority": "AUTHORITATIVE",
            },
            {
                "endpoint_id": "EP-OPEN-2",
                "sheet_id": "S002",
                "node_id": "N2",
                "electrical_network_id": "EN2",
                "coord_x": 11.0,
                "coord_y": 21.0,
                "source_line_ids": '["L2"]',
                "source_handles": '["H2"]',
                "boundary_state": "OPEN",
                "identity_kind": "NETWORK_OPEN",
                "namespace": "sheet:S002",
                "local_key": "N2",
                "label": None,
                "attached_token_id": None,
                "attached_token_kind": None,
                "attached_token_text": None,
                "attachment_id": None,
                "authority": "GEOMETRY_ONLY",
            },
        ]
    ).to_parquet(findings / "endpoint_identities_v1.parquet", index=False)

    pd.DataFrame(
        [
            {
                "decision_id": "CR1",
                "sheet_id": "S001",
                "attachment_id": "SA1",
                "token_id": "TK1",
                "constraint_kind": "LOW_MARGIN_REVIEW",
                "severity": "SOFT",
                "state": "REVIEW",
                "authority": "REVIEW_ONLY",
                "reason_codes": '["LOW_MARGIN"]',
            }
        ]
    ).to_parquet(findings / "constraint_decisions.parquet", index=False)

    pd.DataFrame(
        [
            {
                "attachment_id": "SA1",
                "sheet_id": "S001",
                "token_id": "TK1",
                "token_kind": "TERMINAL_LOCAL",
                "token_text": "105",
                "target_line_id": "L1",
                "target_x": 10.0,
                "target_y": 20.0,
                "selected": True,
                "score": 0.42,
                "margin": 0.01,
                "reason_codes": '["NEAREST_LINE_ENDPOINT"]',
                "constraint_reason_codes": "[]",
                "scope_reason_codes": '["NO_OWNER"]',
                "scope_state": "UNSCOPED",
            }
        ]
    ).to_parquet(findings / "semantic_attachment_candidates.parquet", index=False)

    pd.DataFrame(
        [
            {
                "pair_id": "PW1",
                "line_group_id": "GW1",
                "sheet_id": "S001",
                "left_value": "105",
                "right_value": None,
                "confidence": 0.4,
                "status": "review",
                "rationale": "missing right side",
                "confidence_bucket": "low",
                "left_coord_x": 10.0,
                "left_coord_y": 20.0,
                "right_coord_x": None,
                "right_coord_y": None,
                "pair_key": "105->?",
                "pair_kind": "continuation",
                "left_text_id": "T1",
                "right_text_id": None,
            }
        ]
    ).to_parquet(findings / "pairs.parquet", index=False)

    return project
