"""L-16b Y3-a / Y3-b and L-12 S3: many-to-one pass-through and shared-text ownership.

Y3-a: two left names that a terminal-table record and a component record give on one
      sheet at one right text id name one physical pin (one end of the group).
Y3-b: a terminal with exactly two left pins, its device side (backplate terminal-table
      record whose terminal sits in the external column) and an ordinary external wire on
      another sheet, is a normal two-sided connection, not a many-to-one conflict.
S3:   a shared text between near-overlapping line groups is owned by the nearest line
      group only; the others are not reported as missing a side because of that text.

Each rule has a positive case and negative controls that keep real conflicts visible.
"""

from __future__ import annotations

from dwg_audit.audit import rules as R
from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.audit.rule_base import RuleContext
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import SheetRecord
from dwg_audit.utils.config import DEFAULT_CONFIG
from dwg_audit.utils.ids import IdFactory


def _sheet(sheet_id: str) -> SheetRecord:
    return SheetRecord(
        sheet_id,
        sheet_id,
        f"{sheet_id}.dwg",
        1,
        "1",
        "WIRING",
        "wiring",
        "supplemental",
        "filename",
        True,
    )


def _ctx(pairs: list[Pair], line_groups: list[LineGroup] | None = None) -> RuleContext:
    sheets = {pair.sheet_id: _sheet(pair.sheet_id) for pair in pairs}
    groups = line_groups or []
    group_map = {group.line_group_id: group for group in groups}
    return RuleContext(
        pairs=pairs,
        line_groups=groups,
        sheets=list(sheets.values()),
        config=DEFAULT_CONFIG,
        terminal_candidates=[],
        high_threshold=0.92,
        duplicate_delta=0.08,
        reciprocal_required=False,
        group_map=group_map,
        sheet_map=sheets,
        issue_factory=IssueFactory(issue_ids=IdFactory("I"), group_map=group_map, sheet_map=sheets),
    )


def _wire(pair_id: str, sheet: str, left: str, right: str) -> Pair:
    """Ordinary external wire between two endpoints (schematic wire, eligible ordinary pair)."""
    return Pair(
        pair_id, None, sheet, sheet, None, left, right, 0.99, "pass",
        "l16b fixture", [], "high", {"source": "superworks"}, pair_kind="ordinary_pair",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-R",
    )


def _device_table(
    pair_id: str,
    sheet: str,
    left: str,
    right: str,
    right_text_id: str,
    *,
    right_role: str = "external_terminal_endpoint",
) -> Pair:
    """Device-side record of a backplate terminal table (the terminal is in the external column)."""
    mapping = {
        "mapping_mode": "backplate_virtual_table",
        "sheet_id": sheet,
        "header_prefix": "BI2",
        "row_number": 20,
        "column_roles": {
            "left": "virtual_row_number",
            "middle": "virtual_row_number",
            "right": right_role,
        },
        "left_value": left,
        "right_value": right,
        "right_text_id": right_text_id,
    }
    evidence = {
        "source": "table_mapping",
        "pair_kind": "table_mapping",
        "structured_source": "table_mapping",
        "table_mapping": mapping,
    }
    return Pair(
        pair_id, None, sheet, sheet, None, left, right, 0.99, "pass",
        "l16b table fixture", [], "high", evidence, pair_kind="table_mapping",
        left_text_id=f"{pair_id}-LT", right_text_id=right_text_id,
    )


def _component(pair_id: str, sheet: str, left: str, right: str, right_text_id: str) -> Pair:
    """Component record naming the pin of the same terminal (component diagram)."""
    evidence = {"source": "component_mapping", "pair_kind": "component_mapping", "structured_source": "component_mapping"}
    return Pair(
        pair_id, None, sheet, sheet, None, left, right, 0.99, "pass",
        "l16b component fixture", [], "high", evidence, pair_kind="component_mapping",
        left_text_id=f"{pair_id}-LC", right_text_id=right_text_id,
    )


def _m2o_for(issues, right: str) -> list:
    return [issue for issue in issues if issue.rule_id == "R-MANY-TO-ONE" and issue.right_value == right]


# ---------------------------------------------------------------- Y3-b (pass-through)


def test_y3b_device_side_and_external_wire_are_one_two_sided_terminal() -> None:
    """Positive case (p061 1-21QD77 shape): table device side on S20, external wire on S08."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
    ]
    assert _m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77") == []


def test_y3b_negative_two_external_wires_still_reported() -> None:
    """Negative control: two external wires into one terminal are a real conflict."""
    pairs = [
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
        _wire("W2", "S09", "1-21GD18", "1-21QD77"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


def test_y3b_negative_two_device_sides_still_reported() -> None:
    """Negative control: two device-side table records on one terminal are a real conflict."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _device_table("T2", "S21", "2-21n/BI1-21", "1-21QD77", "T9001"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


def test_y3b_negative_wire_on_the_device_sheet_still_reported() -> None:
    """Negative control: a wire on the device record's own sheet is not the other side of the terminal."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _wire("W1", "S20", "1-21GD17", "1-21QD77"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


def test_y3b_negative_terminal_outside_external_column_still_reported() -> None:
    """Negative control: a table record whose terminal is not in the external column is not a device side."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343", right_role="virtual_row_number"),
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


def test_y3b_negative_third_left_pin_still_reported() -> None:
    """Negative control: a third left pin means the terminal is not a plain two-sided pass-through."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
        _wire("W2", "S09", "1-21GD18", "1-21QD77"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


# ---------------------------------------------------------------- Y3-a (same pin, two names)


def test_y3a_table_and_component_names_of_one_pin_merge() -> None:
    """Positive case: 1-21n/BI2-20 (table) and 1-21n320 (component) share sheet S20 and T3343.

    With the external wire they give three names; the two pin names merge to one end,
    so the terminal keeps two ends and the Y3-b pass-through applies.
    """
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _component("C1", "S20", "1-21n320", "1-21QD77", "T3343"),
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
    ]
    assert _m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77") == []


def test_y3a_two_names_of_one_pin_alone_are_one_end() -> None:
    """Positive case without a wire: the two pin names alone no longer form a many-to-one."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _component("C1", "S20", "1-21n320", "1-21QD77", "T3343"),
    ]
    assert _m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77") == []


def test_y3a_negative_names_on_other_sheet_do_not_merge() -> None:
    """Negative control: the same names on another sheet are not the same physical pin."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _component("C1", "S21", "1-21n320", "1-21QD77", "T3343"),
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


def test_y3a_negative_other_right_text_id_does_not_merge() -> None:
    """Negative control: a different right text id on the same sheet is a different terminal text."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _component("C1", "S20", "1-21n320", "1-21QD77", "T9999"),
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


def test_y3a_negative_two_table_names_do_not_merge() -> None:
    """Negative control: two names both from table records are not merged by name co-occurrence."""
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _device_table("T2", "S20", "1-21n320", "1-21QD77", "T3343"),
        _wire("W1", "S08", "1-21GD17", "1-21QD77"),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


# ---------------------------------------------------------------- S3 (shared text ownership)


def _horizontal(group_id: str, y: float, x1: float = 35.0, x2: float = 55.0) -> LineGroup:
    return LineGroup(
        group_id, "S1", "F1", x1, y, x2, y, x2 - x1, 0.4,
        member_line_ids=[], layer_hints=[], orientation="horizontal",
    )


def _text_claim(pair_id: str, group_id: str, y_text: float, x_text: float = 35.98) -> Pair:
    return Pair(
        pair_id, group_id, "S1", "F1", None, "01", None, 0.5, "review",
        "l16b shared text", [], "low", {}, pair_kind="ordinary_pair",
        left_text_id="T1", right_text_id=None,
        left_coord_x=x_text, left_coord_y=y_text,
    )


def _missing_side(issues) -> list:
    return [issue for issue in issues if issue.rule_id == "R-PAIR-MISSING-SIDE"]


def test_s3_shared_text_is_owned_by_the_nearest_line_group_only() -> None:
    """Positive case (p075 01 shape): two parallel groups 5 apart share text 01; the nearer owns it."""
    groups = [_horizontal("GA", 162.5), _horizontal("GB", 167.5)]
    pairs = [_text_claim("PA", "GA", 163.53), _text_claim("PB", "GB", 163.53)]
    issues = _missing_side(R._run_pair_missing_side(_ctx(pairs, groups)))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.title == "重复线文本归属待复核"
    assert issue.primary_pair_id == "PA"
    assert sorted(issue.related_pair_ids) == ["PB"]
    assert issue.evidence["owner_line_group_id"] == "GA"
    assert issue.evidence["non_owner_line_group_ids"] == ["GB"]


def test_s3_owner_follows_distance_to_the_text_not_the_order_of_pairs() -> None:
    """The text sits next to group GB: GB owns it even when its pair comes first."""
    groups = [_horizontal("GA", 162.5), _horizontal("GB", 167.5)]
    pairs = [_text_claim("PA", "GA", 166.8), _text_claim("PB", "GB", 166.8)]
    issues = _missing_side(R._run_pair_missing_side(_ctx(pairs, groups)))
    assert len(issues) == 1
    assert issues[0].primary_pair_id == "PB"
    assert issues[0].evidence["owner_line_group_id"] == "GB"


def test_s3_negative_distant_groups_sharing_text_are_both_reported() -> None:
    """Negative control: groups not overlapping in y are separate lines; each keeps its own finding."""
    groups = [_horizontal("GA", 162.5), _horizontal("GB", 190.5)]
    pairs = [_text_claim("PA", "GA", 163.53), _text_claim("PB", "GB", 163.53)]
    issues = _missing_side(R._run_pair_missing_side(_ctx(pairs, groups)))
    assert len(issues) == 2
    assert all(issue.title != "重复线文本归属待复核" for issue in issues)


def test_s3_point_segment_distance_is_the_nearest_point_of_the_segment() -> None:
    assert R._point_segment_distance(40.0, 163.0, 35.0, 162.5, 55.0, 162.5) == 0.5
    assert abs(R._point_segment_distance(60.0, 162.5, 35.0, 162.5, 55.0, 162.5) - 5.0) < 1e-9
    assert R._point_segment_distance(None, 163.0, 35.0, 162.5, 55.0, 162.5) == float("inf")
