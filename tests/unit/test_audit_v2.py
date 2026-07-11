"""Unit tests for Phase 120 audit_v2 builders."""

from __future__ import annotations

from types import SimpleNamespace

from dwg_audit.audit.audit_v2 import (
    build_audit_v2_issue_clusters,
    compare_legacy_new_relations,
    summarize_audit_v2,
)


def test_audit_v2_clusters_by_rule_and_sheet() -> None:
    issues = [
        {
            "issue_id": "I1",
            "rule_id": "R-ONE-TO-MANY",
            "sheet_id": "S1",
            "severity": "warning",
            "pair_id": "P1",
            "message": "one to many",
            "evidence": {"handles": ["H1"]},
        },
        {
            "issue_id": "I2",
            "rule_id": "R-ONE-TO-MANY",
            "sheet_id": "S1",
            "severity": "major",
            "pair_id": "P2",
            "message": "one to many 2",
            "evidence": {},
        },
        {
            "issue_id": "I3",
            "rule_id": "R-PAIR-MISSING-SIDE",
            "sheet_id": "S2",
            "severity": "warning",
            "pair_id": "P3",
            "message": "missing",
        },
    ]
    clusters = build_audit_v2_issue_clusters(issues)
    assert len(clusters) == 2
    first = next(row for row in clusters if row["rule_id"] == "R-ONE-TO-MANY")
    assert first["issue_count"] == 2
    assert first["issue_ids"] == ["I1", "I2"]
    assert first["witness_status"] == "PRESENT"
    assert first["severity_max"] == "major"
    assert first["cluster_id"].startswith("AC-")
    assert first["pair_ids"] == ["P1", "P2"]
    assert first["message_summary"] == "one to many"
    summary = summarize_audit_v2(clusters, issues)
    assert summary["cluster_count"] == 2
    assert summary["issue_count"] == 3
    assert summary["witness_completeness"] == 0.5
    assert summary["legacy_issue_stream_retained"] is True
    assert summary["witness_present_count"] == 1
    assert summary["witness_unknown_count"] == 1


def test_severity_max_picks_highest() -> None:
    issues = [
        {
            "issue_id": "I1",
            "rule_id": "R1",
            "sheet_id": "S1",
            "severity": "minor",
            "message": "m1",
        },
        {
            "issue_id": "I2",
            "rule_id": "R1",
            "sheet_id": "S1",
            "severity": "critical",
            "message": "m2",
        },
        {
            "issue_id": "I3",
            "rule_id": "R1",
            "sheet_id": "S1",
            "severity": "major",
            "message": "m3",
        },
    ]
    clusters = build_audit_v2_issue_clusters(issues)
    assert len(clusters) == 1
    assert clusters[0]["severity_max"] == "critical"


def test_witness_unknown_when_no_evidence() -> None:
    issues = [
        {
            "issue_id": "I1",
            "rule_id": "R1",
            "sheet_id": "S1",
            "severity": "info",
            "message": "no evidence",
        }
    ]
    clusters = build_audit_v2_issue_clusters(issues)
    assert clusters[0]["witness_status"] == "UNKNOWN"


def test_simplenamespace_issue_objects() -> None:
    issues = [
        SimpleNamespace(
            issue_id="I1",
            rule_id="R-NS",
            sheet_id="S1",
            severity="major",
            message="from namespace",
            evidence={"handles": ["H1"]},
            pair_id="P1",
            primary_pair_id="P1",
            related_pair_ids=["P9"],
        ),
        SimpleNamespace(
            issue_id="I2",
            rule_id="R-NS",
            sheet_id="S1",
            severity="review",
            message="second",
            evidence=None,
            pair_id=None,
            primary_pair_id=None,
            related_pair_ids=None,
        ),
    ]
    clusters = build_audit_v2_issue_clusters(issues)
    assert len(clusters) == 1
    c = clusters[0]
    assert c["issue_ids"] == ["I1", "I2"]
    assert c["severity_max"] == "major"
    assert c["witness_status"] == "PRESENT"
    assert "P1" in c["pair_ids"]
    assert "P9" in c["pair_ids"]
    assert c["message_summary"] == "from namespace"


def test_compare_legacy_new_relations() -> None:
    report = compare_legacy_new_relations(
        [{"pair_id": "P1"}, {"pair_id": "P2"}, {"pair_id": "P3"}],
        [
            {"equivalence_status": "UNIQUE_V2_NETWORK", "v2_changes_legacy_result": True},
            {"equivalence_status": "UNIQUE_V2_NETWORK", "v2_changes_legacy_result": False},
            {"equivalence_status": "NO_NETWORK", "v2_changes_legacy_result": False},
        ],
    )
    assert report["pair_count"] == 3
    assert report["equivalence_row_count"] == 3
    assert report["v2_changes_legacy_result_count"] == 1
    assert abs(report["unique_v2_network_rate"] - 2 / 3) < 1e-9
    assert report["equivalence_status_counts"]["UNIQUE_V2_NETWORK"] == 2


def test_empty_issues_complete_witness() -> None:
    clusters = build_audit_v2_issue_clusters([])
    summary = summarize_audit_v2(clusters, [])
    assert clusters == []
    assert summary["witness_completeness"] == 1.0
    assert summary["cluster_count"] == 0
    assert summary["issue_count"] == 0
    assert summarize_audit_v2(None, None)["witness_completeness"] == 1.0
    empty_cmp = compare_legacy_new_relations(None, None)
    assert empty_cmp["pair_count"] == 0
    assert empty_cmp["unique_v2_network_rate"] == 0.0
