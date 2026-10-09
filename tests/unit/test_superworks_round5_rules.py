"""Round-5 K: SuperWORKS false-positive reductions (K1-K3) and their negative controls.

K1: a SuperWORKS connect-line port is a component-diagram view, never a schematic role,
    so the one-schematic/one-diagram duplicate exemption holds for it.
K2: a range value (e.g. 1-7UD20~21) covers its member terminals (1-7UD21) within a group,
    for every pair, not only bridge claims.
K3: a terminal-strip jumper (strip_connection_jumper) is a bridge claim.

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


def _plain(pair_id: str, sheet: str, left: str, right: str, *, evidence: dict | None = None,
           status: str = "pass", confidence: float = 0.99) -> Pair:
    return Pair(
        pair_id, f"K-{pair_id}", sheet, sheet, None, left, right, confidence, status,
        "round5 fixture", [], "high", dict(evidence or {}), pair_kind="ordinary_pair",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-R",
    )


def _inline_pair(pair_id: str, sheet: str, body: str, port: str, external: str) -> Pair:
    """Schematic inline two-port component (the legacy schematic producer)."""
    logical = f"{body}-{port}"
    evidence = {
        "source": "component_mapping",
        "component_submode": "inline_two_port_component",
        "mapping_mode": "schematic_inline_two_port",
        "recognition_mode": "geometry_insert_backed_inline_two_port",
        "internal_connectivity_inferred": False,
        "electrical_union_eligible": False,
        "ordinary_pair_eligible": False,
        "component_body": body,
        "component_port": port,
        "logical_endpoint": logical,
        "external_endpoint": external,
        "component_body_text_id": f"{pair_id}-BODY",
        "component_port_text_id": f"{pair_id}-PORT",
        "component_block_handle": f"BLK-{pair_id}",
        "external_endpoint_text_id": f"{pair_id}-EXT",
    }
    return Pair(
        pair_id, None, sheet, sheet, None, logical, external, 0.99, "pass",
        "inline fixture", [], "high", evidence, pair_kind="component_mapping",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-EXT",
    )


def _connect_pair(pair_id: str, sheet: str, logical: str, external: str, *, body: str = "1ZKK") -> Pair:
    """SuperWORKS connect-line port (component-diagram view of the same port)."""
    port = logical.rsplit("-", 1)[-1]
    evidence = {
        "source": "component_mapping",
        "structured_source": "component_mapping",
        "component_submode": "superworks_connect_line_port",
        "logical_endpoint": logical,
        "external_endpoint": external,
        "external_endpoint_raw": external,
        "external_endpoint_split": external,
        "external_endpoint_text_id": f"{pair_id}-EXT",
        "component_body": body,
        "component_body_text_id": f"{pair_id}-BODY",
        "component_port": port,
        "component_port_text_id": None,
        "component_block_name": body,
        "supporting_line_ids": [f"L-{pair_id}"],
        "ordinary_pair_eligible": False,
        "electrical_union_eligible": False,
        "superworks": {
            "source": "superworks",
            "part_id": f"SW:{sheet}:/{body}",
            "instance_path": f"/{body}",
            "symbol_handle": "SYM1",
            "port_id": f"PORT-{pair_id}",
            "label_handle": "LBL1",
            "connection_handle": "CON1",
            "connect_line_handle": "CL1",
            "connect_line_geometry_unique": True,
            "port_resolution_method": "definition_text_nearest",
        },
        "sw_conflicts": [],
    }
    return Pair(
        pair_id, None, sheet, sheet, None, logical, external, 0.99, "pass",
        "connect-line fixture", [], "high", evidence, pair_kind="component_mapping",
        left_text_id=f"{pair_id}-L", right_text_id=f"{pair_id}-EXT",
    )


def _issues(issues, rule_id: str):
    return [issue for issue in issues if issue.rule_id == rule_id]


# ------------------------------------------------------------------- K1 ----

def test_k1_connect_line_port_is_not_a_schematic_role() -> None:
    inline = _inline_pair("I1", "S23", "1ZKK", "1", "1YD3")
    connect = _connect_pair("C1", "S24", "1ZKK-1", "1YD3")

    assert R._authoritative_schematic_role_identity(inline) == ("1ZKK", "1", "1YD3")
    assert R._authoritative_schematic_role_identity(connect) is None


def test_k1_schematic_inline_and_connect_line_views_are_one_port_not_a_duplicate() -> None:
    inline = _inline_pair("I1", "S23", "1ZKK", "1", "1YD3")
    connect = _connect_pair("C1", "S24", "1ZKK-1", "1YD3")

    assert R._is_authoritative_schematic_kk_component_duplicate([inline, connect])
    assert not _issues(R._run_duplicate_pair(_ctx([inline, connect])), "R-DUPLICATE-PAIR")


def test_k1_connect_line_view_still_counts_as_the_component_diagram_role() -> None:
    inline = _inline_pair("I1", "S23", "1ZKK", "1", "1YD3")
    connect = _connect_pair("C1", "S24", "1ZKK-1", "1YD3")

    assert R._authoritative_component_diagram_identity(connect) == ("1ZKK", "1", "1YD3")
    assert R._authoritative_component_diagram_identity(inline) is None


def test_k1_plain_duplicate_next_to_schematic_port_is_still_reported() -> None:
    # Negative: an ordinary pair with the same key has no component-diagram identity,
    # so it is a real duplicate claim and must stay visible.
    inline = _inline_pair("I1", "S23", "1ZKK", "1", "1YD3")
    plain = _plain("P1", "S24", "1ZKK-1", "1YD3")

    assert not R._is_authoritative_schematic_kk_component_duplicate([inline, plain])
    assert _issues(R._run_duplicate_pair(_ctx([inline, plain])), "R-DUPLICATE-PAIR")


def test_k1_two_connect_line_views_without_a_schematic_view_are_still_reported() -> None:
    # Negative: with no schematic role at all, two component-diagram claims on two
    # sheets are not one schematic/diagram pair and keep the duplicate report.
    first = _connect_pair("C1", "S23", "1ZKK-1", "1YD3")
    second = _connect_pair("C2", "S24", "1ZKK-1", "1YD3")

    assert not R._is_authoritative_schematic_kk_component_duplicate([first, second])
    assert _issues(R._run_duplicate_pair(_ctx([first, second])), "R-DUPLICATE-PAIR")


# ------------------------------------------------------------------- K2 ----

def test_k2_range_value_covers_its_member_in_a_group() -> None:
    # The range pair is an ordinary pair (not a bridge claim), as on round-4 data
    # where 1-7UD20~21 is written by the SuperWORKS net-line producer.
    span = _plain("SPAN", "S27", "1-7UD20~21", "1U1D4")
    member = _plain("MEM", "S28", "1-7UD21", "1U1D4")

    assert not R._is_terminal_strip_bridge_claim(span)
    assert not _issues(R._run_many_to_one(_ctx([span, member])), "R-MANY-TO-ONE")


def test_k2_range_covers_member_even_with_a_second_range_pair() -> None:
    pairs = [
        _plain("SPAN", "S27", "1-7UD20~21", "1U1D4"),
        _plain("MEM", "S28", "1-7UD21", "1U1D4"),
        _plain("SPAN2", "S29", "1-7UD20~21", "1U1D4"),
    ]

    assert not _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_k2_range_does_not_hide_a_non_member_left() -> None:
    # Negative: 1-7UD22 is outside 1-7UD20~21, so the group keeps two independent ends.
    pairs = [
        _plain("SPAN", "S27", "1-7UD20~21", "1U1D4"),
        _plain("MEM", "S28", "1-7UD21", "1U1D4"),
        _plain("OUT", "S29", "1-7UD22", "1U1D4"),
    ]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_k2_range_on_another_terminal_row_does_not_cover_the_member() -> None:
    # Negative: a same-number member on a different header prefix is a different terminal.
    pairs = [
        _plain("SPAN", "S27", "1-7UD20~21", "1U1D4"),
        _plain("MEM", "S28", "1-8UD21", "1U1D4"),
    ]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_k2_two_plain_terminals_without_a_range_still_conflict() -> None:
    pairs = [
        _plain("M1", "S27", "1-7UD21", "1U1D4"),
        _plain("M2", "S28", "1-7UD22", "1U1D4"),
    ]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


# ------------------------------------------------------------------- K3 ----

def test_k3_strip_connection_jumper_is_a_bridge_claim() -> None:
    jumper = _plain(
        "J1", "S16", "1-25U2D9", "1-25U3D9",
        evidence={"strip_connection_jumper": True, "jumper_target": "1-25U3D9"},
    )

    assert R._is_terminal_strip_bridge_claim(jumper)


def test_k3_two_jumpers_into_one_terminal_are_one_series_span() -> None:
    # Round-4 p074 S0016 shape: 1-25U2D9 -> 1-25U3D9 and 1-25U4D9 -> 1-25U3D9, both
    # from "&" jumper texts across adjacent strips, must not read as two wires.
    pairs = [
        _plain("J1", "S16", "1-25U2D9", "1-25U3D9", evidence={"strip_connection_jumper": True}),
        _plain("J2", "S16", "1-25U4D9", "1-25U3D9", evidence={"strip_connection_jumper": True}),
    ]

    assert not _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_k3_without_the_field_two_ordinary_wires_into_one_terminal_still_conflict() -> None:
    # Negative: the field is absent, so behaviour is unchanged.
    pairs = [
        _plain("N1", "S16", "1-25U2D9", "1-25U3D9"),
        _plain("N2", "S16", "1-25U4D9", "1-25U3D9"),
    ]

    assert not R._is_terminal_strip_bridge_claim(pairs[0])
    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")


def test_k3_false_flag_is_not_a_bridge_claim() -> None:
    pair = _plain("N1", "S16", "1-25U2D9", "1-25U3D9", evidence={"strip_connection_jumper": False})

    assert not R._is_terminal_strip_bridge_claim(pair)


def test_k3_jumper_does_not_hide_a_real_conflict_between_ordinary_wires() -> None:
    # Negative: one jumper plus two independent ordinary wires into 1-25U3D9 keeps the report.
    pairs = [
        _plain("J1", "S16", "1-25U2D9", "1-25U3D9", evidence={"strip_connection_jumper": True}),
        _plain("N1", "S17", "1-25U5D9", "1-25U3D9"),
        _plain("N2", "S18", "1-25U6D9", "1-25U3D9"),
    ]

    assert _issues(R._run_many_to_one(_ctx(pairs)), "R-MANY-TO-ONE")
