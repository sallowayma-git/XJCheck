"""L-16 R1-R3: many-to-one false-positive reductions and their negative controls.

R1: a 上接 continuation endpoint that is the logical endpoint of its own terminal-header
    row names the terminal of that row (上接7U1D4892 under header 上接7U1D48, row 92 is 7U1D92).
R2: a range left (1-7UD20~21) and its member left (1-7UD21) are one end of the group.
R3: the two side wires (left column and right column) of one two-sided terminal-header row
    are two legitimate ends of the row's middle terminal.

R4 (same-point double record) is not implemented: the second record is a component_mapping
without evidence.source, so it never enters the many-to-one graph.

Each rule has a positive case and negative controls that keep real conflicts visible.
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


def _wire(pair_id: str, sheet: str, left: str, right: str) -> Pair:
    """Ordinary wire pair between two endpoints (no structured evidence)."""
    return Pair(
        pair_id, None, sheet, sheet, None, left, right, 0.99, "pass",
        "l16 fixture", [], "high", {}, pair_kind="ordinary_pair",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-R",
    )


def _row_pair(
    pair_id: str,
    sheet: str,
    *,
    header: str,
    row: int,
    side: str,
    terminal: str,
    row_id: str,
) -> Pair:
    """SuperWORKS terminal-header row side.

    Mirrors the shape of round-5 table_mapping evidence: the pair's left value is the row's
    logical endpoint (header + row number, 上接 kept verbatim), its right value is the terminal
    in the column named by side.
    """
    logical = f"{header}{row}"
    scope = f"{sheet}:{row_id}"
    mapping = {
        "mapping_mode": "terminal_header_table",
        "sheet_id": sheet,
        "file_id": sheet,
        "header_prefix": header,
        "header_text_id": f"{pair_id}-HDR",
        "header_handle": f"HH-{row_id}",
        "row_number": row,
        "middle_value": str(row),
        "middle_text_id": f"{pair_id}-MID",
        "logical_endpoint": logical,
        "row_number_sequence_valid": True,
        "sw_row_id": row_id,
        "left_value": terminal if side == "left" else None,
        "left_text_id": f"{pair_id}-T" if side == "left" else None,
        "right_value": terminal if side == "right" else None,
        "right_text_id": f"{pair_id}-T" if side == "right" else None,
        "column_roles": {
            "left": "terminal_endpoint" if side == "left" else "empty",
            "middle": "row_number",
            "right": "terminal_endpoint" if side == "right" else "empty",
            "description": "empty",
        },
        "sw_branch": "_1",
        "sw_side": side,
        "scope_key": scope,
        "same_strip_destination": False,
    }
    evidence = {
        "source": "superworks",
        "pair_kind": "table_mapping",
        "structured_source": "table_mapping",
        "table_mapping": mapping,
        "sw_conflicts": [],
        "sw_validation_reasons": [],
        "superworks": {
            "source": "superworks",
            "row_handle": f"RH-{row_id}",
            "connection_handle": f"CH-{pair_id}",
            "side": side,
            "branch": "_1",
        },
    }
    return Pair(
        pair_id, None, sheet, sheet, None, logical, terminal, 0.99, "pass",
        "sw strip row", [], "high", evidence, pair_kind="table_mapping",
        left_text_id=f"{pair_id}-LG", right_text_id=f"{pair_id}-T",
    )


def _m2o(issues) -> list:
    return [issue for issue in issues if issue.rule_id == "R-MANY-TO-ONE"]


def _m2o_for(issues, right: str) -> list:
    return [issue for issue in _m2o(issues) if issue.right_value == right]


# ----------------------------------------------------------------- R1 ----

def test_r1_continuation_endpoint_folds_onto_matching_wire() -> None:
    """Positive case: 上接7U1D4892 (header 上接7U1D48, row 92) is 7U1D92, the same end as the wire 7U1D92."""
    pairs = [
        _wire("W1", "S1", "7U1D92", "7U2D92"),
        _row_pair("RP1", "S2", header="上接7U1D48", row=92, side="left", terminal="7U2D92", row_id="R-A"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert _m2o_for(issues, "7U2D92") == []
    assert R._pair_endpoint_identity(pairs[1], "上接7U1D4892") == "7U1D92"


def test_r1_continuation_endpoint_keeps_other_wire_as_second_end() -> None:
    """Positive case with a remaining conflict: 7U2D91 is a second end and stays reported."""
    pairs = [
        _wire("W1", "S1", "7U1D92", "7U2D92"),
        _wire("W2", "S1", "7U2D91", "7U2D92"),
        _row_pair("RP1", "S2", header="上接7U1D48", row=92, side="left", terminal="7U2D92", row_id="R-A"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    issue = _m2o_for(issues, "7U2D92")
    assert len(issue) == 1
    assert issue[0].evidence["conflicting_values"] == ["7U1D92", "7U2D91", "上接7U1D4892"]


def test_r1_negative_continuation_names_a_different_row() -> None:
    """Negative control: 上接7U1D48 with row 93 names 7U1D93, which is not 7U1D92."""
    pairs = [
        _wire("W1", "S1", "7U1D92", "7U2D92"),
        _wire("W2", "S1", "7U2D91", "7U2D92"),
        _row_pair("RP1", "S2", header="上接7U1D48", row=93, side="left", terminal="7U2D92", row_id="R-A"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert len(_m2o_for(issues, "7U2D92")) == 1


def test_r1_negative_continuation_without_table_row_keeps_bare_text() -> None:
    """Negative control: a 上接 value without its own row evidence folds to its bare text only."""
    pairs = [
        _wire("W1", "S1", "7U1D92", "7U2D92"),
        _wire("W2", "S1", "上接7U1D4892", "7U2D92"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert len(_m2o_for(issues, "7U2D92")) == 1


def test_r1_bare_continuation_text_folds_for_plain_names() -> None:
    """上接JD511 and JD511 (no row evidence) are the same name for the many-to-one identity."""
    assert R._pair_endpoint_identity(_wire("W", "S1", "上接JD511", "GND"), "上接JD511") == "JD511"


# ----------------------------------------------------------------- R2 ----

def test_r2_range_and_its_member_are_one_end() -> None:
    """Range 1-7UD20~21 and member 1-7UD21 on one right value are one end (not two)."""
    pairs = [
        _wire("W1", "S1", "1-7UD20~21", "1U1D4"),
        _wire("W2", "S1", "1-7UD21", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert _m2o_for(issues, "1U1D4") == []


def test_r2_negative_range_does_not_absorb_unrelated_terminal() -> None:
    """Negative control: 1-7UD30 is not a member of 1-7UD20~21."""
    pairs = [
        _wire("W1", "S1", "1-7UD20~21", "1U1D4"),
        _wire("W2", "S1", "1-7UD30", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert len(_m2o_for(issues, "1U1D4")) == 1


# ----------------------------------------------------------------- R3 ----

def _row_1u1d4(sheet: str = "S19", row_id: str = "R-7AAF") -> list[Pair]:
    """One terminal-header row 1U1D4: 1n1423 on the left column, 1-7UD21 on the right column."""
    return [
        _row_pair("RL", sheet, header="1U1D", row=4, side="left", terminal="1n1423", row_id=row_id),
        _row_pair("RR", sheet, header="1U1D", row=4, side="right", terminal="1-7UD21", row_id=row_id),
    ]


def test_r3_two_side_wires_of_one_terminal_row_are_one_terminal() -> None:
    """Positive case (p022 1U1D4 shape): range + member + backplate left on the row's two side wires."""
    pairs = _row_1u1d4() + [
        _wire("W1", "S7", "1-7UD20~21", "1U1D4"),
        _wire("W2", "S7", "1-7UD21", "1U1D4"),
        _wire("W3", "S14", "1n1423", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert _m2o_for(issues, "1U1D4") == []


def test_r3_negative_unrelated_third_wire_still_reported() -> None:
    """Negative control: an unrelated extra wire on the same terminal keeps the many-to-one finding."""
    pairs = _row_1u1d4() + [
        _wire("W1", "S7", "1-7UD20~21", "1U1D4"),
        _wire("W2", "S14", "1n1423", "1U1D4"),
        _wire("W3", "S9", "ZZ9", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    issue = _m2o_for(issues, "1U1D4")
    assert len(issue) == 1
    assert "ZZ9" in issue[0].evidence["conflicting_values"]


def test_r3_negative_side_wires_from_two_different_rows_are_not_one_terminal() -> None:
    """Negative control: the left and right wires must come from the same (sheet, sw_row_id)."""
    pairs = [
        _row_pair("RL", "S19", header="1U1D", row=4, side="left", terminal="1n1423", row_id="R-A"),
        _row_pair("RR", "S19", header="1U1D", row=4, side="right", terminal="1-7UD21", row_id="R-B"),
        _wire("W1", "S7", "1-7UD21", "1U1D4"),
        _wire("W2", "S14", "1n1423", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert len(_m2o_for(issues, "1U1D4")) == 1


def test_r3_negative_one_sided_row_is_not_a_junction() -> None:
    """Negative control: a row with only a left-column wire does not explain a second wire."""
    pairs = [
        _row_pair("RL", "S19", header="1U1D", row=4, side="left", terminal="1n1423", row_id="R-A"),
        _wire("W1", "S7", "1-7UD21", "1U1D4"),
        _wire("W2", "S14", "1n1423", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert len(_m2o_for(issues, "1U1D4")) == 1


def test_r3_negative_row_with_other_middle_terminal_does_not_apply() -> None:
    """Negative control: a row whose logical endpoint is 1U1D5 does not explain the 1U1D4 group."""
    pairs = [
        _row_pair("RL", "S19", header="1U1D", row=5, side="left", terminal="1n1423", row_id="R-A"),
        _row_pair("RR", "S19", header="1U1D", row=5, side="right", terminal="1-7UD21", row_id="R-A"),
        _wire("W1", "S7", "1-7UD21", "1U1D4"),
        _wire("W2", "S14", "1n1423", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert len(_m2o_for(issues, "1U1D4")) == 1


def test_r3_continuation_header_row_names_its_terminal() -> None:
    """Positive case (p024 1U1D4 shape): header 上接1U1D3 with row 4 is the terminal 1U1D4 (R1 + R3)."""
    pairs = [
        _row_pair("RL", "S20", header="上接1U1D3", row=4, side="left", terminal="1n1423", row_id="R-C8"),
        _row_pair("RR", "S20", header="上接1U1D3", row=4, side="right", terminal="1-7UD21", row_id="R-C8"),
        _wire("W1", "S7", "1-7UD20~21", "1U1D4"),
        _wire("W2", "S14", "1n1423", "1U1D4"),
    ]
    issues = R._run_many_to_one(_ctx(pairs))
    assert _m2o_for(issues, "1U1D4") == []


def test_r3_row_index_requires_both_sides_and_distinct_values() -> None:
    """Index contract: only two-sided rows with two distinct endpoint values are indexed."""
    index = R._terminal_row_side_index(_row_1u1d4())
    assert index == {"1U1D4": [frozenset({"1N1423", "17UD21"})]}
    one_sided = R._terminal_row_side_index(_row_1u1d4()[:1])
    assert one_sided == {}
