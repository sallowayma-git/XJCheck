"""PIN-1: a LOGGEN end whose INSERT SuperWORKS never registered takes the identity "label-slot" from the
INSERT's own LD_SYMB2_LABEL and LD_SYMB2_TERM_TEXT_<pin> texts (rule R1). Such a pair is admitted for review
only, never pass, and only when the intrinsic and project-level checks all hold."""
from __future__ import annotations

import json
from types import SimpleNamespace

import ezdxf

from dwg_audit.audit.superworks_extractor import _admit_wire_routes, _key
from dwg_audit.domain.models import Pair
from dwg_audit.extract.superworks_loggen import build_wire_route_rows, read_page_wire_routes
from test_superworks_semantics import symbol, xdata
from test_superworks_wire_route_admission import _extract, _line, _page, _sw_side


def _unregistered(doc, label_value, slot_value, *, pin="4", at=(0, 0)):
    """An element INSERT with a label and a TERM_TEXT slot but no LD_SYMB2_SPECIAL (walk() drops it)."""
    name = f"U{len(doc.blocks)}"
    block = doc.blocks.new(name)
    marker = block.add_lwpolyline([(-.5, 0), (.5, 0)])
    xdata(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, pin)])
    insert = doc.modelspace().add_blockref(name, at)
    label = doc.modelspace().add_text(label_value, dxfattribs={"insert": (at[0], at[1] + 3), "height": 2})
    xdata(insert, "LD_SYMB2_LABEL", [(1005, label.dxf.handle)])
    xdata(label, "LD_SYMB2_LABEL", [(1005, insert.dxf.handle)])
    if slot_value is not None:
        app = f"LD_SYMB2_TERM_TEXT_{pin}"
        slot = doc.modelspace().add_text(slot_value, dxfattribs={"insert": (at[0], at[1] + 1), "height": 2})
        xdata(insert, app, [(1000, pin), (1005, slot.dxf.handle)])
        xdata(slot, app, [(1005, insert.dxf.handle)])
    return insert


def _record(doc, wire_handle, ends):
    """LD_SYMB2LOGGEN record: ends are (device, pin, seq, insert handle, category)."""
    dictionary = doc.rootdict.get("LD_SYMB2LOGGEN_DICTIONARY") or doc.rootdict.add_new_dict("LD_SYMB2LOGGEN_DICTIONARY")
    record = dictionary.add_xrecord(f"LD_SYMB2LOGGEN_{len(dictionary)}")
    values = []
    if wire_handle:
        values.append(("CONNECTLINEHANDLE", wire_handle))
    values.append(("LINESTYLE", "电流回路线:*"))
    for index, (device, pin, seq, handle, category) in enumerate(ends, start=1):
        values.append((f"PART2_{index}", f"||{device}||{pin}||{seq}||左||S||{handle}||{category}||"))
    record.reset([(1, value) for pair in values for value in pair])
    return record


def _document(*, slot="4", seq="4", label="8ID3", device="8ID3", linked=True, category=""):
    """Terminal 1XD2 (registered) wired to an unregistered element pin 8ID3-4."""
    doc = ezdxf.new()
    terminal, _ = symbol(doc, "端子", "1XD2", at=(0, 0), pin_value="1")
    element = _unregistered(doc, label, slot, pin="4", at=(20, 0))
    wire = doc.modelspace().add_line((0.5, 0), (19.5, 0), dxfattribs={"layer": "0"})
    if linked:
        _record(doc, wire.dxf.handle, [(("1XD2"), "1", "1", terminal.dxf.handle, "端子"),
                                       (device, "4", seq, element.dxf.handle, category)])
    return doc, terminal, element, wire


def _rows(doc, data=None):
    data = data if data is not None else _extract(doc)
    page = read_page_wire_routes(doc, file_id="F1", sheet_id="S1")
    rows, _ = build_wire_route_rows([page], data, {"F1": "1"})
    return data, rows


def _admit(doc, *, lines=None, output=None, strip_rows=None, texts=None):
    data, rows = _rows(doc)
    output = [] if output is None else output
    if lines is None:
        lines = [_line(doc, wire) for wire in doc.modelspace().query("LINE")]
    _admit_wire_routes(output, data, rows, lines=lines, line_groups=[],
                       audit_ids={"S1"}, page_map={"S1": _page()}, strip_rows_by_endpoint=strip_rows or {},
                       xml_ranks={}, texts=texts)
    return data, rows, output


def _end(row, index):
    import json
    return json.loads(row["ends_json"])[index]


def test_unregistered_insert_end_takes_label_slot_identity_as_resolved_by_symb2_text() -> None:
    doc, _, element, _ = _document()
    _, rows = _rows(doc)
    end = _end(rows[0], 1)
    assert end["status"] == "resolved_by_symb2_text"
    assert end["identity"] == "8ID3-4"
    assert end["identity_source"] == "symb2_text_slot"
    assert end["symb2"]["rejects"] == []


def test_slot_text_not_matching_record_sequence_is_not_an_identity() -> None:
    doc, _, _, _ = _document(slot="5", seq="4")
    _, rows = _rows(doc)
    end = _end(rows[0], 1)
    assert end["status"] == "insert_not_sw"
    assert end["identity"] is None
    assert end["detail"] == "symb2:slot_seq_mismatch"


def test_label_not_matching_record_device_is_not_an_identity() -> None:
    doc, _, _, _ = _document(device="8ID9")
    _, rows = _rows(doc)
    assert _end(rows[0], 1)["detail"] == "symb2:label_device_mismatch"


def test_missing_slot_text_is_not_an_identity() -> None:
    doc, _, _, _ = _document(slot=None)
    _, rows = _rows(doc)
    assert _end(rows[0], 1)["detail"] == "symb2:slot_missing"


def test_admitted_pair_is_review_wire_component_mapping_with_symb2_identity() -> None:
    doc, terminal, element, wire = _document()
    data, rows, output = _admit(doc)
    assert len(output) == 1
    pair = output[0]
    assert pair.status == "review"
    assert pair.pair_kind == "wire_component_mapping"
    assert (pair.left_value, pair.right_value) == ("1XD2", "8ID3-4")
    assert pair.evidence["superworks"]["right"]["identity_source"] == "symb2_text_slot"
    assert pair.evidence["superworks"]["right"]["port_ids"] == []
    assert pair.evidence["sw_wire_route"]["identity_source"] == "symb2_text_slot"
    assert pair.evidence["sw_wire_route"]["no_wire_handle"] is False
    assert "pin_identity_symb2_text_slot" in pair.rationale
    assert pair.evidence["symb2_text_slot"][0]["identity"] == "8ID3-4"
    assert rows[0]["admission_status"] == "admitted_review"


def test_record_without_wire_handle_is_review_and_marked() -> None:
    doc, terminal, element, _ = _document(linked=False)
    _record(doc, None, [("1XD2", "1", "1", terminal.dxf.handle, "端子"),
                        ("8ID3", "4", "4", element.dxf.handle, "")])
    data, rows, output = _admit(doc, lines=[])
    assert len(output) == 1
    pair = output[0]
    assert pair.status == "review"
    assert "no_wire_handle" in pair.rationale and "wire_geometry_missing" in pair.rationale
    assert pair.evidence["sw_wire_route"]["no_wire_handle"] is True
    assert pair.line_group_id is None


def test_terminal_already_consumed_by_a_pair_is_not_admitted() -> None:
    doc, terminal, _, _ = _document()
    data = _extract(doc)
    consumer = Pair(pair_id="PX", line_group_id="GX", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                    left_value="1XD2", right_value="9Z", confidence=.9, status="review", rationale="other",
                    evidence={"source": "superworks", "superworks": {"left": _sw_side(data, terminal.dxf.handle),
                                                                     "right": None}})
    _, rows, output = _admit(doc, output=[consumer])
    assert output == [consumer]
    assert _end(rows[0], 0)["status"] == "resolved"
    assert rows[0]["admission_reason"] == "end_consumed"


def test_identity_wired_to_two_different_terminals_is_not_admitted() -> None:
    doc, _, _, _ = _document()
    other = _unregistered(doc, "8ID3", "4", pin="4", at=(40, 0))
    second_terminal, _ = symbol(doc, "端子", "1XD5", at=(80, 0), pin_value="1")
    _record(doc, None, [("1XD5", "1", "1", second_terminal.dxf.handle, "端子"),
                        ("8ID3", "4", "4", other.dxf.handle, "")])
    _, rows, output = _admit(doc, lines=[])
    assert [row["admission_reason"] for row in rows] == ["symb2_identity_conflict", "symb2_identity_conflict"]
    assert all(row["admission_status"] is None for row in rows)
    assert output == []


def test_same_identity_on_a_second_sheet_with_the_same_terminal_is_not_a_conflict() -> None:
    doc, _, _, _ = _document()
    other = _unregistered(doc, "8ID3", "4", pin="4", at=(40, 0))
    second_terminal, _ = symbol(doc, "端子", "1XD2", at=(80, 0), pin_value="1")
    _record(doc, None, [("1XD2", "1", "1", second_terminal.dxf.handle, "端子"),
                        ("8ID3", "4", "4", other.dxf.handle, "")])
    _, rows, output = _admit(doc, lines=[])
    assert [row["admission_status"] for row in rows] == ["admitted_review", "admitted_review"]
    assert len(output) == 2


def _terminal_handle(doc, label):
    return next(e.dxf.handle for e in doc.modelspace().query("TEXT") if e.dxf.text == label)


def test_identity_context_counts_a_registered_pin_wired_to_another_terminal_as_a_conflict() -> None:
    from dwg_audit.audit.superworks_extractor import _symb2_context
    port = SimpleNamespace(file_id="F1", category="内部元件", endpoint_identity="8ID3-4", insert_handle="I1",
                           port_number="4", wire_contacts=[{"wire_handle": "W1"}])
    terminal = SimpleNamespace(file_id="F1", category="端子", endpoint_identity="1XD9", insert_handle="T1",
                               port_number="1", wire_contacts=[{"wire_handle": "W1"}])
    data = SimpleNamespace(ports=[port, terminal], part_instances=[])
    row = {"record_id": "R1", "ends_json": json.dumps([
        {"status": "resolved", "category": "端子", "identity": "1XD2", "file_id": "F1", "terminal_handle": "T2", "port_number": "1"},
        {"status": "resolved_by_symb2_text", "category": "", "identity": "8ID3-4", "file_id": "F1",
         "terminal_handle": "I2", "port_number": "4"}])}
    context = _symb2_context([row], data, {}, [])
    assert context["partners_by_identity"][_key("8ID3-4")] == {_key("1XD9"), _key("1XD2")}


def test_terminal_strip_row_naming_another_component_rejects_the_identity() -> None:
    doc, _, _, _ = _document()
    strip = {_key("1XD2"): [(("F1", "H1"), SimpleNamespace(connections=[{"style": "端子排内接元件", "value": "8ID9-4"}]))]}
    _, rows, output = _admit(doc, strip_rows=strip)
    assert rows[0]["admission_reason"] == "symb2_strip_row_disagrees"
    assert output == []


def test_terminal_strip_row_naming_the_same_identity_admits() -> None:
    doc, _, _, _ = _document()
    strip = {_key("1XD2"): [(("F1", "H1"), SimpleNamespace(connections=[{"style": "端子排内接元件", "value": "8ID3-4"}]))]}
    _, rows, output = _admit(doc, strip_rows=strip)
    assert len(output) == 1
    assert output[0].evidence["symb2_text_slot"][0]["terminal_strip_verdict"] == "agree"


def test_existing_pairs_are_kept_and_the_new_pair_is_only_appended() -> None:
    doc, terminal, _, _ = _document()
    data = _extract(doc)
    existing = Pair(pair_id="PY", line_group_id="GY", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                    left_value="9X", right_value="9Y", confidence=.9, status="pass", rationale="other",
                    evidence={"source": "superworks", "superworks": {"left": None, "right": None}})
    _, rows, output = _admit(doc, output=[existing])
    assert output[0] is existing and existing.status == "pass"
    assert len(output) == 2
