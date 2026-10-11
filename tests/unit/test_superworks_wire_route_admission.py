"""Wire-route admission (LOGGEN phase 2): records become SuperWORKS pairs only when both ends are
unconsumed terminals; consumed-end records are reconciled as evidence and never become pairs."""
from __future__ import annotations

from collections import Counter

import ezdxf

from dwg_audit.audit.superworks_extractor import (
    _admit_wire_routes,
    _consumed_ports,
    _reconcile_consumed_wire_routes,
    _wire_route_census,
)
from dwg_audit.domain.models import LineEntity, Pair, SheetRecord
from dwg_audit.extract.superworks_loggen import build_wire_route_rows, read_page_wire_routes
from dwg_audit.extract.superworks_semantics import bind_text_ids, extract_superworks_semantics
from test_superworks_semantics import symbol, text_items, xdata


def _page():
    return SheetRecord("S1", "F1", "test.dwg", 1, "1", "test", "二次原理图", "primary", "filename", True,
                       audit_disposition="audit")


def _extract(doc):
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    bind_text_ids(data, text_items(doc))
    return data


def _loggen(doc, wire_handle, ends, linestyle="电流回路线:*"):
    """ends: [(insert_handle, pin, category)] written as PART2_1..n in LD_SYMB2LOGGEN_DICTIONARY."""
    dictionary = doc.rootdict.get("LD_SYMB2LOGGEN_DICTIONARY") or doc.rootdict.add_new_dict("LD_SYMB2LOGGEN_DICTIONARY")
    record = dictionary.add_xrecord("LD_SYMB2LOGGEN_1")
    values = [("CONNECTLINEHANDLE", wire_handle), ("LINESTYLE", linestyle)]
    for index, (handle, pin, category) in enumerate(ends, start=1):
        values.append((f"PART2_{index}", f"||1XD||{pin}||1||左||S||{handle}||{category}||"))
    record.reset([(1, value) for pair in values for value in pair])
    return record


def _line(doc, wire):
    return LineEntity(line_id="L1", sheet_id="S1", file_id="F1", handle=wire.dxf.handle,
                      source_entity_type="LINE", layer="0",
                      start_x=wire.dxf.start.x, start_y=wire.dxf.start.y,
                      end_x=wire.dxf.end.x, end_y=wire.dxf.end.y, length=19.0, angle_deg=0.0,
                      bbox_min_x=0.5, bbox_min_y=0.0, bbox_max_x=19.5, bbox_max_y=0.0)


def _two_terminal_document(linked=True):
    """Two terminal symbols (1XD2 at x=0, 1XD3 at x=20) joined by one wire between their contacts."""
    doc = ezdxf.new()
    first, _ = symbol(doc, "端子", "1XD2", at=(0, 0), pin_value="1")
    second, _ = symbol(doc, "端子", "1XD3", at=(20, 0), pin_value="1")
    wire = doc.modelspace().add_line((0.5, 0), (19.5, 0), dxfattribs={"layer": "0"})
    if linked:
        _loggen(doc, wire.dxf.handle, [(first.dxf.handle, "1", "端子"), (second.dxf.handle, "1", "端子")])
    return doc, first, second, wire


def _admit(doc, lines, output=None, line_groups=None):
    data = _extract(doc)
    page = read_page_wire_routes(doc, file_id="F1", sheet_id="S1")
    rows, _ = build_wire_route_rows([page], data, {"F1": "1"})
    output = [] if output is None else output
    line_groups = [] if line_groups is None else line_groups
    _admit_wire_routes(output, data, rows, lines=lines, line_groups=line_groups, audit_ids={"S1"},
                       page_map={"S1": _page()}, strip_rows_by_endpoint={}, xml_ranks={})
    return data, rows, output, line_groups


def _sw_side(data, insert_handle, port_number="1"):
    port = next(p for p in data.ports if p.insert_handle == insert_handle and str(p.port_number) == port_number)
    return {"value": port.endpoint_identity, "category": port.category, "text_id": port.label.get("text_id"),
            "port_ids": [port.record_id], "symbol_handle": port.insert_handle,
            "port_number": str(port.port_number), "wire_touched": True, "reason_codes": []}


def test_two_unconsumed_terminals_joined_by_a_confirmed_wire_are_admitted_as_pass() -> None:
    doc, first, second, wire = _two_terminal_document()
    data, rows, output, line_groups = _admit(doc, [_line(doc, wire)])

    assert len(output) == 1
    pair = output[0]
    assert (pair.left_value, pair.right_value) == ("1XD2", "1XD3")
    assert pair.status == "pass"
    assert pair.pair_kind == "ordinary_pair"
    assert pair.evidence["source"] == "superworks"
    assert pair.evidence["ordinary_pair_eligible"] is True
    assert pair.evidence["superworks"]["line_group_origin"] == "metadata_wire_reference"
    assert pair.evidence["sw_wire_route"]["wire_confirmed"] is True
    assert pair.line_group_id.startswith("GWSW")
    assert line_groups and line_groups[0].line_group_id == pair.line_group_id
    row = rows[0]
    assert row["admission_status"] == "admitted_pass"
    assert row["admitted_pair_id"] == pair.pair_id


def test_missing_wire_geometry_is_admitted_for_review_only() -> None:
    doc, _, _, _ = _two_terminal_document()
    data, rows, output, _ = _admit(doc, lines=[])

    assert len(output) == 1
    assert output[0].status == "review"
    assert output[0].line_group_id is None
    assert "wire_geometry_missing" in output[0].rationale
    assert rows[0]["admission_status"] == "admitted_review"


def test_end_consumed_by_another_pair_is_not_admitted() -> None:
    doc, first, second, wire = _two_terminal_document()
    data = _extract(doc)
    consumer = Pair(pair_id="PX", line_group_id="GX", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                    left_value="1XD2", right_value="9Z", confidence=.9, status="review", rationale="other",
                    evidence={"source": "superworks", "superworks": {"left": _sw_side(data, first.dxf.handle),
                                                                     "right": None}})
    page = read_page_wire_routes(doc, file_id="F1", sheet_id="S1")
    rows, _ = build_wire_route_rows([page], data, {"F1": "1"})
    output = [consumer]
    _admit_wire_routes(output, data, rows, lines=[_line(doc, wire)], line_groups=[], audit_ids={"S1"},
                       page_map={"S1": _page()}, strip_rows_by_endpoint={}, xml_ranks={})

    assert len(output) == 1
    assert rows[0]["admission_reason"] == "end_consumed"
    assert rows[0]["admission_status"] is None


def test_unresolved_end_is_never_admitted() -> None:
    doc = ezdxf.new()
    first, _ = symbol(doc, "端子", "1XD2", at=(0, 0), pin_value="1")
    wire = doc.modelspace().add_line((0.5, 0), (19.5, 0), dxfattribs={"layer": "0"})
    _loggen(doc, wire.dxf.handle, [(first.dxf.handle, "1", "端子"), ("FFFF", "3", "端子")])
    data, rows, output, _ = _admit(doc, [_line(doc, wire)])

    assert output == []
    assert rows[0]["admission_reason"] == "end_unresolved"


def test_self_connection_is_not_admitted() -> None:
    doc = ezdxf.new()
    first, _ = symbol(doc, "端子", "1XD2", at=(0, 0), pin_value="1")
    second, _ = symbol(doc, "端子", "1XD2", at=(20, 0), pin_value="1")
    wire = doc.modelspace().add_line((0.5, 0), (19.5, 0), dxfattribs={"layer": "0"})
    _loggen(doc, wire.dxf.handle, [(first.dxf.handle, "1", "端子"), (second.dxf.handle, "1", "端子")])
    data, rows, output, _ = _admit(doc, [_line(doc, wire)])

    assert output == []
    assert rows[0]["admission_reason"] == "self_connection"


def test_same_port_legacy_numeric_value_is_replaced_by_the_sw_identity() -> None:
    doc, first, second, wire = _two_terminal_document(linked=True)
    data = _extract(doc)
    legacy = Pair(pair_id="PL", line_group_id="GL", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                  left_value=None, right_value="702", confidence=.32, status="review", rationale="legacy",
                  pair_key="?->702", left_text_id=None, right_text_id="TX",
                  evidence={"source": "wire_component_mapping",
                            "superworks": {"source": "superworks", "left": None,
                                           "right": _sw_side(data, second.dxf.handle)}})
    page = read_page_wire_routes(doc, file_id="F1", sheet_id="S1")
    rows, _ = build_wire_route_rows([page], data, {"F1": "1"})
    # The record names 1XD3 on the second terminal; the legacy numeric value 702 disagrees.
    rows = [row for row in rows if row["source_kind"] == "LOGGEN"]
    output = [legacy]
    stats = Counter()
    _reconcile_consumed_wire_routes(rows, _consumed_ports(output), stats, lambda pair: set())

    assert legacy.right_value == "1XD3"
    assert legacy.status == "review"
    assert legacy.pair_key == "?->1XD3"
    assert legacy.evidence["sw_wire_route_fix"][0]["from_value"] == "702"
    assert stats["value_fixed"] == 1
    assert "sw_wire_route_conflict" not in legacy.evidence
    assert rows[0]["admission_status"] == "consumed_value_fixed"


def test_disagreeing_value_on_a_pass_pair_is_recorded_as_conflict_not_changed() -> None:
    doc, first, second, wire = _two_terminal_document(linked=True)
    data = _extract(doc)
    passing = Pair(pair_id="PP", line_group_id="GP", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                   left_value="1XD2", right_value="9Z", confidence=.99, status="pass", rationale="sw",
                   evidence={"source": "superworks", "superworks": {"left": _sw_side(data, first.dxf.handle),
                                                                    "right": _sw_side(data, second.dxf.handle)}})
    page = read_page_wire_routes(doc, file_id="F1", sheet_id="S1")
    rows, _ = build_wire_route_rows([page], data, {"F1": "1"})
    rows = [row for row in rows if row["source_kind"] == "LOGGEN"]
    stats = Counter()
    _reconcile_consumed_wire_routes(rows, _consumed_ports([passing]), stats, lambda pair: set())

    assert passing.right_value == "9Z"
    conflicts = passing.evidence["sw_wire_route_conflict"]
    assert [c["kind"] for c in conflicts] == ["same_port_value_differs"]
    assert conflicts[0]["record_identity"] == "1XD3"
    assert rows[0]["admission_status"] == "consumed_conflict"


def test_other_end_difference_on_another_wire_is_fanout_not_conflict() -> None:
    doc, first, second, wire = _two_terminal_document(linked=True)
    third, _ = symbol(doc, "端子", "1XD9", at=(40, 0), pin_value="1")
    data = _extract(doc)
    # The pair consumes the first terminal and a third terminal (1XD9), drawn on another wire.
    other = Pair(pair_id="PO", line_group_id="GO", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                 left_value="1XD2", right_value="1XD9", confidence=.99, status="pass", rationale="sw",
                 evidence={"source": "superworks", "superworks": {"left": _sw_side(data, first.dxf.handle),
                                                                  "right": _sw_side(data, third.dxf.handle)}})
    page = read_page_wire_routes(doc, file_id="F1", sheet_id="S1")
    rows, _ = build_wire_route_rows([page], data, {"F1": "1"})
    rows = [row for row in rows if row["source_kind"] == "LOGGEN"]
    stats = Counter()
    # The pair is drawn on a different wire: the port carries a second wire, which is fan-out.
    _reconcile_consumed_wire_routes(rows, _consumed_ports([other]), stats, lambda pair: {"OTHERWIRE"})

    assert "sw_wire_route_conflict" not in other.evidence
    assert stats["fanout:other_wire_other_end"] == 1
    assert rows[0]["admission_status"] == "consumed_fanout"


def test_census_counts_internal_ends_and_cross_page_text_fallback() -> None:
    rows = [
        {"source_kind": "PCL", "ends_json": '[{"role":"LOCAL","category":"","status":"resolved","far_source":null},'
                                            '{"role":"FAR","category":"端子","status":"resolved_by_text",'
                                            '"far_source":"cross_page","identity":"1-JD1","far_text_identity":"1-JD1"}]'},
        {"source_kind": "LOGGEN", "ends_json": '[{"role":"PART2_1","category":"端子","status":"resolved"},'
                                               '{"role":"PART2_2","category":"端子","status":"resolved"}]'},
    ]
    census = _wire_route_census(rows)
    assert census["records:PCL"] == 1 and census["records:LOGGEN"] == 1
    assert census["records_with_internal_end"] == 1
    assert census["cross_page_far_ends"] == 1
    assert census["cross_page_text_fallback"] == 1
