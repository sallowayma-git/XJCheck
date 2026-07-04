from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.audit.rule_base import AuditRule
from dwg_audit.audit.rule_base import cluster_issues
from dwg_audit.audit.rule_base import select_rules
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.utils.ids import IdFactory


def _noop(_context):
    return []


def test_select_rules_preserves_registry_order() -> None:
    registry = [
        AuditRule("R-B", "B", "desc", "review", _noop),
        AuditRule("R-A", "A", "desc", "review", _noop),
        AuditRule("R-C", "C", "desc", "review", _noop),
    ]

    selected = select_rules(registry, {"R-A", "R-C"})

    assert [rule.rule_id for rule in selected] == ["R-A", "R-C"]


def test_issue_factory_builds_enriched_issue() -> None:
    sheet_map = {
        "S1": SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
        "S2": SheetRecord("S2", "F2", "b.dwg", 2, "02", "B", "二次原理图", "primary", "filename", True),
    }
    group_map = {
        "G1": LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        "G2": LineGroup("G2", "S2", "F2", 10, 0, 20, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    }
    pair = Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "a.dwg"})
    related_pair = Pair("P2", "G2", "S2", "F2", "PC2", "101", "202", 0.96, "pass", "ok", [], "high", {"filename": "b.dwg"})

    issue = IssueFactory(IdFactory("I"), group_map, sheet_map).build(
        "R-CROSS-PAGE-CONFLICT",
        "high",
        pair,
        "conflict",
        title="跨页配对冲突",
        explanation="same left maps to multiple rights",
        recommended_action="check references",
        related_pairs=[pair, related_pair],
        extra={"conflicting_values": ["201", "202"]},
    )

    assert issue.issue_id == "I0001"
    assert issue.severity == "critical"
    assert issue.title == "跨页配对冲突"
    assert issue.related_pair_ids == ["P2"]
    assert issue.sheet_ids == ["S1", "S2"]
    assert issue.values == ["101", "201", "202"]
    assert issue.evidence["filename"] == "a.dwg"
    assert issue.evidence["line_start"] == [0, 0]
    assert issue.evidence["line_end"] == [10, 0]
    assert issue.evidence_refs[1]["filename"] == "b.dwg"


def test_cluster_issues_merges_duplicate_ordered_pair_problems() -> None:
    sheet_map = {
        "S1": SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
        "S2": SheetRecord("S2", "F2", "b.dwg", 2, "02", "B", "二次原理图", "primary", "filename", True),
    }
    group_map = {
        "G1": LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        "G2": LineGroup("G2", "S2", "F2", 10, 0, 20, 0, 10, 0.9, ["L2"], ["CONNECT"]),
    }
    factory = IssueFactory(IdFactory("I"), group_map, sheet_map)
    issue_a = factory.build(
        "R-MISSING-RECIPROCAL",
        "major",
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.94, "pass", "ok", [], "high", {}),
        "missing reciprocal",
    )
    issue_b = factory.build(
        "R-MISSING-RECIPROCAL",
        "major",
        Pair("P2", "G2", "S2", "F2", "PC2", "101", "201", 0.96, "pass", "ok", [], "high", {}),
        "missing reciprocal",
    )

    clustered = cluster_issues([issue_a, issue_b])

    assert len(clustered) == 1
    assert clustered[0].primary_pair_id == "P1"
    assert clustered[0].related_pair_ids == ["P2"]
    assert clustered[0].sheet_ids == ["S1", "S2"]
    assert clustered[0].evidence["cluster_size"] == 2
    assert clustered[0].evidence["cluster_pair_ids"] == ["P1", "P2"]
    assert clustered[0].evidence["cluster_sheet_ids"] == ["S1", "S2"]
    assert len(clustered[0].evidence_refs) == 2
