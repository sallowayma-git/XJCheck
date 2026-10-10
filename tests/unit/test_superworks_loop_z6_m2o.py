"""Z-6 m2o: a many-to-one group is legal when every conflicting left end is on the shared net.

(a) the left and another member sit on the two sides of one terminal-header row (the other
    side may be a same-pin alias of that member);
(b) the left is, or is a same-pin alias of, a terminal joined to the shared right terminal by
    a SW terminal-terminal pass line;
(c) the left is a same-pin alias of a member that is explained by (a), (b) or (c).

Positive cases follow the p040 1GD1 shape and a direct-line shape; negative controls keep
the p040 1ZK-3 shape (one side unexplained), a component-port line, aliases with no path to
the shared terminal, and a group with one unexplained left end.
"""

from __future__ import annotations

from dwg_audit.audit import rules as R
from dwg_audit.audit.rule_base import IssueFactory
from dwg_audit.audit.rule_base import RuleContext
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


def _ctx(pairs: list[Pair]) -> RuleContext:
    sheets = {pair.sheet_id: _sheet(pair.sheet_id) for pair in pairs}
    return RuleContext(
        pairs=pairs,
        line_groups=[],
        sheets=list(sheets.values()),
        config=DEFAULT_CONFIG,
        terminal_candidates=[],
        high_threshold=0.92,
        duplicate_delta=0.08,
        reciprocal_required=False,
        group_map={},
        sheet_map=sheets,
        issue_factory=IssueFactory(issue_ids=IdFactory("I"), group_map={}, sheet_map=sheets),
    )


def _sw_line(pair_id: str, sheet: str, left: str, right: str, categories: tuple[str, str]) -> Pair:
    """SW wire joining two endpoints directly (superworks evidence with endpoint categories)."""
    evidence = {
        "source": "superworks",
        "pair_kind": "ordinary_pair",
        "ordinary_pair_eligible": True,
        "superworks": {
            "source": "superworks",
            "left": {"value": left, "category": categories[0]},
            "right": {"value": right, "category": categories[1]},
        },
    }
    return Pair(
        pair_id, None, sheet, sheet, None, left, right, 0.99, "pass",
        "z6 fixture", [], "high", evidence, pair_kind="ordinary_pair",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-R",
    )


def _table_row_side(
    pair_id: str,
    sheet: str,
    row_id: str,
    header: str,
    row_number: int,
    side: str,
    value: str,
) -> Pair:
    """One side of a terminal-header row: the pair runs from the row's middle terminal to the side terminal."""
    mapping = {
        "mapping_mode": "terminal_header_table",
        "sw_row_id": row_id,
        "sheet_id": sheet,
        "row_number": row_number,
        "header_prefix": header,
        "left_value": value if side == "left" else None,
        "right_value": value if side == "right" else None,
        "column_roles": {
            "left": "terminal_endpoint" if side == "left" else "empty",
            "middle": "row_number",
            "right": "terminal_endpoint" if side == "right" else "empty",
        },
    }
    evidence = {
        "source": "table_mapping",
        "pair_kind": "table_mapping",
        "structured_source": "table_mapping",
        "table_mapping": mapping,
    }
    return Pair(
        pair_id, None, sheet, sheet, None, f"{header}{row_number}", value, 0.99, "pass",
        "z6 table fixture", [], "high", evidence, pair_kind="table_mapping",
        left_text_id=f"{pair_id}-LT", right_text_id=f"{pair_id}-RT",
    )


def _device_table(pair_id: str, sheet: str, left: str, right: str, right_text_id: str) -> Pair:
    """Backplate terminal-table device record: the terminal sits in the external column."""
    mapping = {
        "mapping_mode": "backplate_virtual_table",
        "sheet_id": sheet,
        "header_prefix": "NDY306A",
        "row_number": 3,
        "column_roles": {
            "left": "virtual_row_number",
            "middle": "virtual_row_number",
            "right": "external_terminal_endpoint",
        },
        "left_value": None,
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
        "z6 table fixture", [], "high", evidence, pair_kind="table_mapping",
        left_text_id=f"{pair_id}-LT", right_text_id=right_text_id,
    )


def _component(
    pair_id: str,
    sheet: str,
    left: str,
    right: str,
    right_text_id: str,
    *,
    confidence: float = 0.99,
    status: str = "pass",
) -> Pair:
    """Component record naming a pin of the shared terminal (same right text id as the table record)."""
    evidence = {"source": "component_mapping", "pair_kind": "component_mapping", "structured_source": "component_mapping"}
    return Pair(
        pair_id, None, sheet, sheet, None, left, right, confidence, status,
        "z6 component fixture", [], "high", evidence, pair_kind="component_mapping",
        left_text_id=f"{pair_id}-LC", right_text_id=right_text_id,
    )


def _m2o_for(issues, right: str) -> list:
    return [issue for issue in issues if issue.rule_id == "R-MANY-TO-ONE" and issue.right_value == right]


# ---------------------------------------------------------------- (b) direct terminal lines


def test_b_every_left_on_a_direct_terminal_line_to_the_shared_terminal_is_legal() -> None:
    """Direct-line shape: both conflicting ends are joined to 1-2n221 by SW terminal-terminal lines."""
    pairs = [
        _sw_line("W1", "S17", "1-2n223", "1-2n221", ("装置端子", "装置端子")),
        _sw_line("W2", "S18", "1-2n224", "1-2n221", ("装置端子", "端子")),
    ]
    assert _m2o_for(R._run_many_to_one(_ctx(pairs)), "1-2n221") == []


def test_b_negative_component_port_line_is_not_a_terminal_line() -> None:
    """Negative control: a line whose right end is a component port does not explain its left end."""
    pairs = [
        _sw_line("W1", "S17", "1-2n223", "1-2n221", ("装置端子", "元件端子")),
        _sw_line("W2", "S18", "1-2n224", "1-2n221", ("装置端子", "装置端子")),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-2n221")) == 1


# ---------------------------------------------------------------- p040 1GD1 shape


def _gd1_shape_pairs(extra: list[Pair] | None = None) -> list[Pair]:
    """Row 162D (1n103 | 1GD1 | 1DK1-4), backplate device record 1n/NDY306A-3, pin alias 1n103,
    direct lines 1GD1-2YD1 and 1GD1-1n103 (terminal-terminal), component port 1DK1-4 on 1GD1."""
    return [
        _device_table("P1", "S16", "1n/NDY306A-3", "1GD1", "T2050"),
        _component("C1", "S16", "1n103", "1GD1", "T2050", confidence=0.5, status="review"),
        _component("C2", "S18", "1DK1-4", "1GD1", "T3063"),
        _sw_line("W2", "S09", "2YD1", "1GD1", ("端子", "端子")),
        _sw_line("W3", "S04", "1GD1", "1n103", ("端子", "装置端子")),
        _table_row_side("R1", "S21", "162D", "1GD", 1, "left", "1n103"),
        _table_row_side("R2", "S21", "162D", "1GD", 1, "right", "1DK1-4"),
        *(extra or []),
    ]


def test_p040_1gd1_shape_row_partner_alias_and_direct_line_is_legal() -> None:
    """Positive case: 1DK1-4 is explained by its row partner 1n103 (alias of 1n/NDY306A-3),
    1n/NDY306A-3 by the direct line 1GD1-1n103, and 2YD1 by the direct line 1GD1-2YD1."""
    assert _m2o_for(R._run_many_to_one(_ctx(_gd1_shape_pairs())), "1GD1") == []


def test_p040_1gd1_shape_with_unexplained_third_left_still_reported() -> None:
    """Negative control: one left end with no row, line or alias keeps the group reported."""
    extra = [_component("C9", "S30", "9ZZ1", "1GD1", "T7777")]
    assert len(_m2o_for(R._run_many_to_one(_ctx(_gd1_shape_pairs(extra))), "1GD1")) == 1


def test_c_negative_aliases_with_no_path_to_the_shared_terminal_do_not_explain_each_other() -> None:
    """Negative control: two names of one pin explain each other only through (c), so neither is explained.

    The pin's device side and its component record merge (Y3-a); the wire on S20 (the device sheet)
    is not a pass-through partner, so only the explained-member rule can decide the group.
    """
    pairs = [
        _device_table("T1", "S20", "1-21n/BI2-20", "1-21QD77", "T3343"),
        _component("C1", "S20", "1-21n320", "1-21QD77", "T3343"),
        _sw_line("W1", "S20", "9-21GD17", "1-21QD77", ("端子", "端子")),
    ]
    assert len(_m2o_for(R._run_many_to_one(_ctx(pairs)), "1-21QD77")) == 1


# ---------------------------------------------------------------- p040 1ZK-3 shape (kept)


def test_1zk3_shape_two_rows_with_the_same_name_still_reported() -> None:
    """p040 1ZK-3: 1Q4D3 and HD1 are one-sided rows of their own tables, both writing 1ZK-3.

    Neither row has a second side, and no SW terminal line joins either name to 1ZK-3,
    so the conflict stays reported.
    """
    pairs = [
        _table_row_side("R1", "S21", "18FE", "1Q4D", 3, "left", "1ZK-3"),
        _table_row_side("R2", "S21", "1EF9", "HD", 1, "left", "1ZK-3"),
    ]
    issues = _m2o_for(R._run_many_to_one(_ctx(pairs)), "1ZK-3")
    assert len(issues) == 1
    assert set(issues[0].evidence["conflicting_values"]) == {"1Q4D3", "HD1"}
