from dwg_audit.audit.issue_triage import classify_and_group_issues
from dwg_audit.audit.issue_triage import summarize_handling
from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.utils.ids import IdFactory


def _factory() -> IssueFactory:
    sheet_map = {
        "S1": SheetRecord("S1", "F1", "a.dwg", 1, "01", "A", "二次原理图", "primary", "filename", True),
        "S2": SheetRecord("S2", "F2", "b.dwg", 2, "02", "B", "二次原理图", "primary", "filename", True),
    }
    group_map = {
        "G1": LineGroup("G1", "S1", "F1", 0, 0, 10, 0, 10, 0.9, ["L1"], ["CONNECT"]),
        "G2": LineGroup("G2", "S1", "F1", 10, 0, 20, 0, 10, 0.9, ["L2"], ["CONNECT"]),
        "G3": LineGroup("G3", "S2", "F2", 0, 10, 10, 10, 10, 0.9, ["L3"], ["CONNECT"]),
    }
    return IssueFactory(IdFactory("I"), group_map, sheet_map)


def test_classify_and_group_issues_assigns_handling_buckets_and_sheet_groups() -> None:
    factory = _factory()
    low_a = factory.build(
        "R-PAIR-LOW-CONFIDENCE",
        "review",
        Pair("P1", "G1", "S1", "F1", "PC1", "101", "201", 0.61, "review", "ok", [], "low", {}),
        "low conf a",
        title="低置信度配对",
    )
    low_b = factory.build(
        "R-PAIR-LOW-CONFIDENCE",
        "review",
        Pair("P2", "G2", "S1", "F1", "PC2", "102", "202", 0.58, "review", "ok", [], "low", {}),
        "low conf b",
        title="低置信度配对",
    )
    conflict = factory.build(
        "R-CROSS-PAGE-CONFLICT",
        "high",
        Pair("P3", "G3", "S2", "F2", "PC3", "521", "622", 0.96, "pass", "ok", [], "high", {}),
        "conflict",
        title="跨页配对冲突",
        extra={"one_to_many_classification": "conflict"},
    )
    branch = factory.build(
        "R-ONE-TO-MANY",
        "review",
        Pair("P4", "G1", "S1", "F1", "PC4", "307", "411", 0.9, "pass", "ok", [], "high", {}),
        "branch",
        title="一对多合法分支",
        extra={"one_to_many_classification": "branch"},
    )

    classified = classify_and_group_issues([low_a, low_b, conflict, branch])
    counts = summarize_handling(classified)

    assert counts["error"] == 1
    assert counts["warning"] == 1
    assert counts["review"] == 2

    by_id = {issue.issue_id: issue for issue in classified}
    assert by_id[conflict.issue_id].evidence["handling_class"] == "error"
    assert by_id[branch.issue_id].evidence["handling_class"] == "warning"
    assert by_id[low_a.issue_id].evidence["handling_class"] == "review"
    assert by_id[low_a.issue_id].issue_type == "pair_low_confidence"
    assert by_id[conflict.issue_id].issue_type == "cross_page_conflict"

    # Same-sheet low-confidence findings collapse into one review group for UI.
    assert (
        by_id[low_a.issue_id].evidence["review_group_id"]
        == by_id[low_b.issue_id].evidence["review_group_id"]
    )
    assert by_id[low_a.issue_id].evidence["review_group_size"] == 2
    assert "共 2 处" in by_id[low_a.issue_id].evidence["review_group_label"]
    assert "须人工校验" in by_id[low_a.issue_id].evidence["review_group_label"]
    assert by_id[conflict.issue_id].evidence["handling_label"] == "确定性错误"
    assert by_id[branch.issue_id].evidence["handling_label"] == "可能有错误"
    assert by_id[low_a.issue_id].evidence["handling_label"] == "须人工校验"

    # Errors sort before warnings/reviews.
    assert classified[0].evidence["handling_class"] == "error"


def test_backplate_table_scope_review_is_demoted_to_review_not_error() -> None:
    """A1: bare template Ia1-13-style backplate scope reviews must not stay critical."""
    factory = _factory()
    scope = factory.build(
        "R-CROSS-PAGE-CONFLICT",
        "high",
        Pair("P5", "G3", "S2", "F2", "PC5", "Ia1-13", "1-25ZKK7-2", 0.95, "pass", "ok", [], "high", {}),
        "backplate scope",
        title="背板表格作用域待复核",
        extra={"one_to_many_classification": "backplate_table_scope_review"},
    )
    same_sheet = factory.build(
        "R-ONE-TO-MANY",
        "high",
        Pair("P6", "G1", "S1", "F1", "PC6", "NKR308A-1", "5FD15", 0.95, "pass", "ok", [], "high", {}),
        "same sheet scope",
        title="同页背板作用域待复核",
        extra={"one_to_many_classification": "backplate_table_same_sheet_scope_review"},
    )
    hard = factory.build(
        "R-CROSS-PAGE-CONFLICT",
        "high",
        Pair("P7", "G3", "S2", "F2", "PC7", "521", "622", 0.96, "pass", "ok", [], "high", {}),
        "real conflict",
        title="跨页配对冲突",
        extra={"one_to_many_classification": "conflict"},
    )

    classified = classify_and_group_issues([scope, same_sheet, hard])
    by_id = {issue.issue_id: issue for issue in classified}
    assert by_id[scope.issue_id].evidence["handling_class"] == "review"
    assert by_id[same_sheet.issue_id].evidence["handling_class"] == "review"
    assert by_id[hard.issue_id].evidence["handling_class"] == "error"
