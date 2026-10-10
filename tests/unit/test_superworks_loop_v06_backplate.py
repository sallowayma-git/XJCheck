"""V-06: backplate exemption must accept an equivalent SuperWORKS strip-row half.

The lattice pair and a SuperWORKS connect-line half describe the same terminal
strip row. The exemption must hold for either form, but only when the half's own
logical endpoint is the pin its external terminal lands on.
"""
from copy import deepcopy

import pytest

from dwg_audit.audit.rules import _is_authoritative_terminal_strip_backplate_attachment_group
from dwg_audit.audit.rules import _terminal_strip_row_witness
from dwg_audit.domain.models import Pair


def _lattice_pair():
    return Pair("LAT", "G", "S1", "F1", None, "1n2001", "1UD1", .95, "pass", "lattice", [], "high",
        {"source": "component_mapping", "component_submode": "terminal_strip_lattice",
         "terminal_strip_instance": "TF", "terminal_strip_insert_handle": "OWNER",
         "terminal_strip_instance_text_id": "INSTANCE", "terminal_strip_flank_line_ids": ["FLANK"],
         "left_terminal": "1n2001", "right_terminal": "1UD1",
         "left_terminal_text_id": "LEFT", "right_terminal_text_id": "RIGHT",
         "terminal_strip_left_pin": {"handle": "OWNER:VIRTUAL:51", "text_id": "PIN1", "value": "1"},
         "terminal_strip_right_pin": {"handle": "OWNER:VIRTUAL:50", "text_id": "PIN2", "value": "2"}},
        left_text_id="LEFT", right_text_id="RIGHT", pair_kind="component_mapping")


def _sw_half(*, logical="TF-1", port="1", external_side="right", external="1n2001", pin_side_values=None,
             pair_logical="TF-1", pair_external="* 1n2001"):
    """One SuperWORKS connect-line half of the row (TF-1 <-> 1n2001 at pin 1, TF-2 <-> 1UD1 at pin 2)."""
    left_pin = {"handle": "OWNER:VIRTUAL:51", "text_id": "PIN1", "value": "1", "coord": [48.5, 260.8]}
    right_pin = {"handle": "OWNER:VIRTUAL:50", "text_id": "PIN2", "value": "2", "coord": [58.4, 260.8]}
    if pin_side_values:
        for side, value in pin_side_values.items():
            (left_pin if side == "left" else right_pin)["value"] = value
    evidence = {
        "source": "component_mapping", "component_submode": "superworks_connect_line_port",
        "line_orientation": "terminal_strip_lattice_row", "independent_pin_verification": True,
        "sw_conflicts": [], "superworks": {"source": "superworks", "connect_line_id": "L6556"},
        "logical_endpoint": logical, "external_endpoint": external, "component_port": port,
        "terminal_strip_instance": "TF", "terminal_strip_insert_handle": "OWNER",
        "terminal_strip_instance_text_id": "INSTANCE", "terminal_strip_flank_line_ids": ["FLANK"],
        "terminal_strip_left_pin": left_pin, "terminal_strip_right_pin": right_pin,
        "terminal_strip_row_y": 260.17,
        "left_terminal": "1n2001", "right_terminal": "1UD1",
        "left_terminal_text_id": "LEFT", "right_terminal_text_id": "RIGHT",
    }
    return Pair("SWH", "G", "S1", "F1", None, pair_logical, pair_external, .99, "pass", "sw half", [], "high",
                evidence, left_text_id="INSTANCE", right_text_id="RIGHT", pair_kind="component_mapping")


def _table(*, right="TF-1", sheet="S2"):
    return Pair("TABLE", None, sheet, "F2", None, "1n2001", right, .98, "pass", "table", [], "high",
        {"source": "table_mapping", "table_mapping": {
            "mapping_mode": "backplate_virtual_table", "sheet_id": sheet, "logical_endpoint": "1n2001",
            "right_value": right, "right_text_id": "ATTACHMENT", "row_number_sequence_valid": True,
            "header_prefix": "1n20", "header_text_id": "HEADER", "middle_text_id": "ROW",
            "row_number": 1, "source_block_name": "BACKPLATE", "plugin_slot_authority": "same_row_model_and_slot",
            "column_roles": {"middle": "virtual_row_number", "right": "external_terminal_endpoint"}}},
        pair_kind="table_mapping")


def test_lattice_row_still_satisfies_the_exemption():
    assert _is_authoritative_terminal_strip_backplate_attachment_group([_lattice_pair(), _table()])


@pytest.mark.parametrize("half_kwargs", [
    {},  # TF-1 <-> 1n2001 (external on the right side of the pair, decorated as SuperWORKS emits it)
    {"logical": "TF-2", "port": "2", "external": "1UD1", "pair_logical": "TF-2", "pair_external": "1UD1 *"},
], ids=["pin1_half", "pin2_half"])
def test_equivalent_superworks_half_satisfies_the_exemption(half_kwargs):
    half = _sw_half(**half_kwargs)
    assert _terminal_strip_row_witness(half) is not None
    assert _is_authoritative_terminal_strip_backplate_attachment_group([half, _table()])


def test_superworks_half_with_a_wrong_attachment_is_still_reported():
    # The backplate claims 1n2001 lands on TF-2, but the row's pin 1 is what 1n2001 lands on.
    assert not _is_authoritative_terminal_strip_backplate_attachment_group([_sw_half(), _table(right="TF-2")])


@pytest.mark.parametrize("damage", [
    "missing_pin_verification",
    "pin_value_disagrees_with_port",
    "logical_not_the_pin_of_the_external_terminal",
    "external_not_on_the_row",
    "pair_logical_detached_from_strip",
    "sw_conflict_recorded",
    "missing_left_pin_handle",
    "missing_strip_flank",
    "no_external_text_id",
])
def test_superworks_half_without_equivalent_pin_evidence_does_not_match(damage):
    half = _sw_half()
    ev = half.evidence
    if damage == "missing_pin_verification":
        ev["independent_pin_verification"] = False
    elif damage == "pin_value_disagrees_with_port":
        ev["component_port"] = "2"
    elif damage == "logical_not_the_pin_of_the_external_terminal":
        ev["logical_endpoint"] = "TF-2"
        half.left_value = "TF-2"
    elif damage == "external_not_on_the_row":
        ev["external_endpoint"] = "1UD9"
        half.right_value = "1UD9"
    elif damage == "pair_logical_detached_from_strip":
        half.left_value = "TF-3"
    elif damage == "sw_conflict_recorded":
        ev["sw_conflicts"] = [{"reason_codes": ["unresolved_connect_line"]}]
    elif damage == "missing_left_pin_handle":
        ev["terminal_strip_left_pin"] = {"text_id": "PIN1", "value": "1"}
    elif damage == "missing_strip_flank":
        ev["terminal_strip_flank_line_ids"] = []
    elif damage == "no_external_text_id":
        ev["right_terminal_text_id"] = None
    assert not _is_authoritative_terminal_strip_backplate_attachment_group([half, _table()])


def test_source_alone_is_not_a_strip_row_witness():
    half = _sw_half()
    half.evidence["component_submode"] = "superworks_connect_line_port"
    half.evidence["line_orientation"] = "wire"
    assert _terminal_strip_row_witness(half) is None
    assert not _is_authoritative_terminal_strip_backplate_attachment_group([half, _table()])


def test_lattice_damage_cases_are_unchanged():
    lattice = _lattice_pair()
    table = _table()
    assert _is_authoritative_terminal_strip_backplate_attachment_group([lattice, table])
    bad = deepcopy(lattice)
    bad.evidence["terminal_strip_instance_text_id"] = None
    assert not _is_authoritative_terminal_strip_backplate_attachment_group([bad, table])
    assert not _is_authoritative_terminal_strip_backplate_attachment_group([lattice, table, deepcopy(table)])


def test_end_to_end_real_conflict_is_still_reported_beside_the_exempt_row():
    from dwg_audit.audit.rules import build_issues
    from dwg_audit.domain.models import SheetRecord
    from dwg_audit.utils.config import DEFAULT_CONFIG

    sheets = [SheetRecord("S1", "F1", "a.dwg", 1, "1", "A", "二次原理图", "primary", "filename", True),
              SheetRecord("S2", "F2", "b.dwg", 2, "2", "B", "二次原理图", "primary", "filename", True),
              SheetRecord("S3", "F3", "c.dwg", 3, "3", "C", "二次原理图", "primary", "filename", True)]
    # The strip row plus its backplate attachment is one consistent description: no cross-page conflict.
    consistent = build_issues([_lattice_pair(), _table()], [], sheets, DEFAULT_CONFIG)
    assert not any(i.rule_id == "R-CROSS-PAGE-CONFLICT" for i in consistent)
    # A third page that lands the same external terminal on another device is a genuine conflict.
    other = Pair("PLAIN", "G3", "S3", "F3", None, "1n2001", "1UD9", .95, "pass", "plain", [], "high", {},
                 pair_kind="ordinary_pair")
    conflicted = build_issues([_lattice_pair(), _table(), other], [], sheets, DEFAULT_CONFIG)
    assert any(i.rule_id == "R-CROSS-PAGE-CONFLICT" for i in conflicted)
