"""Round-5 SuperWORKS producer fixes: same-value labels inside one definition instance
are not port identities (L1); terminal-strip '&' jumper connections (L2); a withdrawn
same-label adoption falls back to label + TERMPOINT port number (N1)."""
from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest
from ezdxf.math import Matrix44

from dwg_audit.audit.superworks_extractor import extract_superworks_pairs
from dwg_audit.domain.models import SwStripRow
from dwg_audit.extract.superworks_semantics import (SuperworksData, _definition_ports, _terminal_identity,
                                                    extract_superworks_semantics)


def _app(entity, app, values):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, values)


def _slot_block(doc, name, port_names):
    """Three vertical slot ports at y = 0, 10, 20 (segment x in [-1, 0]), named by port_names."""
    block = doc.blocks.new(name)
    for y, port_name in zip((0, 10, 20), port_names):
        port = block.add_lwpolyline([(0, y), (-1, y)])
        _app(port, "LD_SYMB1LIB_TERMPOINT", [(1000, port_name)])
    return block


def _ports_by_number(doc, insert):
    return {number: pin for _, number, _, _, _, pin in _definition_ports(doc, insert, Matrix44(), "/x")}


def test_same_caption_on_independent_texts_falls_back_to_port_numbers():
    # Three ports each with its own TEXT reading "B码1+", 7.0 away from its port:
    # nearest adoption would name all three alike, so each falls back to its port number.
    doc = ezdxf.new()
    block = _slot_block(doc, "SLOTSAME", ("401", "501", "601"))
    for y in (0, 10, 20):
        block.add_text("B码1+", dxfattribs={"height": 3.0, "insert": (-8.0, y)})
    insert = doc.modelspace().add_blockref("SLOTSAME", (0, 0))
    result = _ports_by_number(doc, insert)
    assert set(result) == {"401", "501", "601"}
    for pin in result.values():
        assert pin.get("resolved") is not True
        assert pin["nearest_rejected"]["reason"] == "same_value_distinct_text"
        assert "resolution_method" not in pin


def test_distinct_captions_on_independent_texts_are_kept_as_nearest_identities():
    doc = ezdxf.new()
    block = _slot_block(doc, "SLOTDIFF", ("401", "501", "601"))
    for y, caption in zip((0, 10, 20), ("B码1+", "B码2+", "B码3+")):
        block.add_text(caption, dxfattribs={"height": 3.0, "insert": (-8.0, y)})
    insert = doc.modelspace().add_blockref("SLOTDIFF", (0, 0))
    result = _ports_by_number(doc, insert)
    assert {number: pin["resolution_method"] for number, pin in result.items()} == {
        "401": "definition_text_nearest", "501": "definition_text_nearest", "601": "definition_text_nearest"}
    assert len({pin["normalized"] for pin in result.values()}) == 3


def test_one_text_entity_shared_by_ports_keeps_its_adoption():
    # One "DC" TEXT between port 1 (about 2.06 away) and port 2 (8.0 away): both ports
    # adopt the same text entity, the shared-terminal case, which keeps its adoption.
    doc = ezdxf.new()
    block = doc.blocks.new("SHAREDSAME")
    for y, name in ((0, "1"), (10, "2")):
        port = block.add_lwpolyline([(0, y), (-1, y)])
        _app(port, "LD_SYMB1LIB_TERMPOINT", [(1000, name)])
    block.add_text("DC", dxfattribs={"height": 3.0, "insert": (-1.5, 2.0)})
    insert = doc.modelspace().add_blockref("SHAREDSAME", (0, 0))
    result = _ports_by_number(doc, insert)
    assert result["1"]["normalized"] == "DC" and result["1"]["resolution_method"] == "definition_text_nearest"
    assert result["2"]["normalized"] == "DC" and result["2"]["resolution_method"] == "definition_text_nearest"


def test_same_caption_revocation_is_scoped_to_one_definition_instance():
    # Two INSERTs of the same block: each instance's ports are judged on their own
    # texts. Instance B's captions are distinct, so its ports keep their adoption.
    doc = ezdxf.new()
    block = _slot_block(doc, "SCOPED", ("401", "501", "601"))
    for y in (0, 10, 20):
        block.add_text("B码1+", dxfattribs={"height": 3.0, "insert": (-8.0, y)})
    insert_a = doc.modelspace().add_blockref("SCOPED", (0, 0))
    other = doc.blocks.new("SCOPEDOTHER")
    for y, port_name in zip((0, 10), ("1", "2")):
        port = other.add_lwpolyline([(0, y), (-1, y)])
        _app(port, "LD_SYMB1LIB_TERMPOINT", [(1000, port_name)])
    other.add_text("K1", dxfattribs={"height": 3.0, "insert": (-8.0, 0.0)})
    other.add_text("K2", dxfattribs={"height": 3.0, "insert": (-8.0, 10.0)})
    insert_b = doc.modelspace().add_blockref("SCOPEDOTHER", (100, 0))
    assert all(pin.get("resolved") is not True for pin in _ports_by_number(doc, insert_a).values())
    result_b = _ports_by_number(doc, insert_b)
    assert result_b["1"]["normalized"] == "K1" and result_b["2"]["normalized"] == "K2"


def _same_label_backplate(doc, name, port_names, caption="1n-02"):
    """Three ports, each with its own TEXT of one shared caption 7.0 away (a backplate row label)."""
    block = _slot_block(doc, name, port_names)
    for y in (0, 10, 20):
        block.add_text(caption, dxfattribs={"height": 3.0, "insert": (-8.0, y)})
    return doc.modelspace().add_blockref(name, (0, 0))


def _entries(doc, insert):
    return list(_definition_ports(doc, insert, Matrix44(), "/x"))


def test_same_label_with_distinct_port_numbers_is_revoked_to_port_numbers():
    # The B码 shape: every port has a distinct TERMPOINT number to fall back to.
    doc = ezdxf.new()
    insert = _same_label_backplate(doc, "BMADISTINCT", ("401", "501", "601"), caption="B码1+")
    entries = _entries(doc, insert)
    assert [number for _, number, *_ in entries] == ["401", "501", "601"]
    for *_, pin in entries:
        assert pin["nearest_rejected"]["reason"] == "same_value_distinct_text"


def test_same_label_with_repeated_port_numbers_keeps_nearest_adoption():
    # Backplate shape: the port numbers repeat, so no distinct fallback identity exists.
    doc = ezdxf.new()
    insert = _same_label_backplate(doc, "BACKREPEAT", ("1", "1", "1"))
    entries = _entries(doc, insert)
    assert len(entries) == 3
    for *_, pin in entries:
        assert pin["resolution_method"] == "definition_text_nearest"
    assert len({pin["normalized"] for *_, pin in entries}) == 1


def test_same_label_with_an_empty_port_number_keeps_nearest_adoption():
    # A port without a TERMPOINT number has no fallback: the whole group keeps its adoption,
    # including the ports that do have a number.
    doc = ezdxf.new()
    insert = _same_label_backplate(doc, "BACKEMPTY", ("401", "", "601"))
    entries = _entries(doc, insert)
    assert len(entries) == 3
    for *_, pin in entries:
        assert pin["resolution_method"] == "definition_text_nearest"


def test_partly_repeated_port_numbers_keep_nearest_adoption():
    # Two ports share the number "7" and the third has "9": the fallbacks are not
    # distinct within the group, so the group keeps its adoption.
    doc = ezdxf.new()
    insert = _same_label_backplate(doc, "BACKMIX", ("7", "7", "9"))
    entries = _entries(doc, insert)
    assert len(entries) == 3
    for *_, pin in entries:
        assert pin["resolution_method"] == "definition_text_nearest"


# ---- M2: same-strip / cross-strip contract on terminal-strip table mappings ----------------

def _strip_row(record_id, header, row, connections):
    return SwStripRow(record_id=record_id, sheet_id="S1", file_id="F1", row_handle=record_id[-4:],
                      header={"handle": "H" + header, "normalized": header, "resolved": True, "text_id": "T" + header},
                      row={"normalized": row, "text_id": "R" + row},
                      endpoint_identity=header + row, connections=connections,
                      validation={"handle_resolved": True, "reciprocal_ok": True}, reason_codes=[])


def _connection(value, side="right", branch="_1"):
    return {"value": value, "normalized": value, "text_id": "C" + value, "side": side, "branch": branch,
            "style": "端子排内接元件", "resolved": True, "reciprocal_ok": True, "handle": "X" + value}


def _page():
    return SimpleNamespace(sheet_id="S1", sheet_order=1, page_type="屏端子图", sheet_category="屏端子图",
                           audit_disposition="audit", audit_role="audit")


def _table_pairs(rows):
    data = SuperworksData()
    data.strip_rows.extend(rows)
    output, _, _ = extract_superworks_pairs(data, pages=[_page()], texts=[], lines=[], line_groups=[],
                                            pairs=[], table_mappings=[])
    return {(pair.left_value, pair.right_value): pair for pair in output
            if pair.evidence.get("pair_kind") == "table_mapping"}


def _stacked_strips():
    # 1-25U2D, 1-25U3D and 1-25U4D stacked; row 9 of U2D and U4D connect to U3D9.
    return [
        _strip_row("SWR:F1:S1:0001", "1-25U2D", "9", [_connection("1-25U3D9")]),
        _strip_row("SWR:F1:S1:0002", "1-25U3D", "9", [_connection("1-25U2D9", side="left")]),
        _strip_row("SWR:F1:S1:0003", "1-25U4D", "9", [_connection("1-25U3D9")]),
        _strip_row("SWR:F1:S1:0004", "1-25U2D", "5", []),
        _strip_row("SWR:F1:S1:0005", "1-25U2D", "2", [_connection("1-25U2D5")]),
        _strip_row("SWR:F1:S1:0006", "1-25U2D", "1", [_connection("1XD3")]),
    ]


def test_table_mapping_to_a_row_of_another_strip_is_a_cross_strip_link_corroborated_by_that_row():
    pairs = _table_pairs(_stacked_strips())
    pair = pairs[("1-25U2D9", "1-25U3D9")]
    assert pair.evidence["terminal_cross_strip_link"] is True
    assert pair.evidence["strip_headers"] == ["1-25U2D", "1-25U3D"]
    assert pair.evidence["strip_corroborated"] is True
    assert pair.evidence["strip_membership"] == "cross_strip"
    assert "terminal_short_bridge" not in pair.evidence


def test_cross_strip_table_mapping_is_uncorroborated_when_the_other_row_does_not_list_it_back():
    pairs = _table_pairs(_stacked_strips())
    # Row 1-25U3D9 lists only 1-25U2D9, so the 1-25U4D9 connection to it is not listed back.
    pair = pairs[("1-25U4D9", "1-25U3D9")]
    assert pair.evidence["terminal_cross_strip_link"] is True
    assert pair.evidence["strip_corroborated"] is False


def test_table_mapping_within_one_strip_is_a_terminal_short_bridge_with_its_header():
    pairs = _table_pairs(_stacked_strips())
    pair = pairs[("1-25U2D2", "1-25U2D5")]
    assert pair.evidence["terminal_short_bridge"] is True
    assert pair.evidence["strip_header"] == "1-25U2D"
    assert pair.evidence["strip_membership"] == "same_strip"
    assert "terminal_cross_strip_link" not in pair.evidence


def test_table_mapping_to_a_non_strip_identity_gets_no_contract_fields():
    pairs = _table_pairs(_stacked_strips())
    pair = pairs[("1-25U2D1", "1XD3")]
    for key in ("terminal_short_bridge", "terminal_cross_strip_link", "strip_header", "strip_headers",
                "strip_corroborated", "strip_membership"):
        assert key not in pair.evidence


# ---- N1: a withdrawn same-label adoption falls back to label + TERMPOINT port number -----

def test_terminal_identity_joins_label_and_pin_value_with_the_given_joiner():
    assert _terminal_identity("1n", "219") == "1n219"
    assert _terminal_identity("1n", "A1", "-") == "1n-A1"
    assert _terminal_identity("", "219") is None
    assert _terminal_identity("1n", "") is None


def _backplate_insert(doc, name, port_names, *, caption="02", label_value="1n", category=None):
    """Three slot ports, each with its own TEXT of one shared caption 7.0 away, inside a
    definition instance labelled label_value (a backplate row label on the connect side)."""
    block = _slot_block(doc, name, port_names)
    for y in (0, 10, 20):
        block.add_text(caption, dxfattribs={"height": 3.0, "insert": (-8.0, y)})
    insert = doc.modelspace().add_blockref(name, (0, 0))
    label = doc.modelspace().add_text(label_value, dxfattribs={"insert": (0, 25), "height": 2})
    if category is None:
        _app(insert, "LDPARTLAYT_PART", [(1000, "1")])
        _app(insert, "LDPARTLAYT_PARTLABEL_HANDLE", [(1005, label.dxf.handle)])
        _app(label, "LDPARTLAYT_PART_HANDLE", [(1005, insert.dxf.handle)])
    else:
        _app(insert, "LD_SYMB2_SPECIAL", [(1000, category)])
        _app(insert, "LD_SYMB2_LABEL", [(1005, label.dxf.handle)])
        _app(label, "LD_SYMB2_LABEL", [(1005, insert.dxf.handle)])
    return insert


def test_revoked_ports_of_a_part_take_label_plus_port_number_without_joiner():
    doc = ezdxf.new()
    _backplate_insert(doc, "N1PART", ("401", "501", "601"))
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    ports = {port["port_number"]: port for port in data.part_instances[0].ports}
    assert {number: port["endpoint_identity"] for number, port in ports.items()} == {
        "401": "1n401", "501": "1n501", "601": "1n601"}
    for port in ports.values():
        assert port["pin"]["resolved"] is False
        assert port["pin"]["pin_resolution_method"] == "termpoint_number_fallback"
        assert port["pin"]["nearest_rejected"]["reason"] == "same_value_distinct_text"


@pytest.mark.parametrize("category", ["装置端子", "内部元件"])
def test_revoked_ports_of_a_symbol_take_the_same_fallback_identity(category):
    doc = ezdxf.new()
    _backplate_insert(doc, "N1SYM" + category[:2], ("401", "501", "601"), category=category)
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    assert {port.port_number: port.endpoint_identity for port in data.ports} == {
        "401": "1n401", "501": "1n501", "601": "1n601"}
    assert {port.pin["pin_resolution_method"] for port in data.ports} == {"termpoint_number_fallback"}


def test_repeated_port_numbers_keep_the_nearest_adoption_identity():
    # No distinct fallback number exists, so the group keeps its adoption (label-pin form).
    doc = ezdxf.new()
    _backplate_insert(doc, "N1REPEAT", ("1", "1", "1"))
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    ports = data.part_instances[0].ports
    assert {port["endpoint_identity"] for port in ports} == {"1n-02"}
    for port in ports:
        assert port["pin"]["resolution_method"] == "definition_text_nearest"
        assert "pin_resolution_method" not in port["pin"]


def test_unrevoked_ports_keep_their_pin_based_identity():
    # Distinct captions: no revocation, so the identities are unchanged label-pin forms.
    doc = ezdxf.new()
    block = _slot_block(doc, "N1DISTINCT", ("401", "501", "601"))
    for y, caption in zip((0, 10, 20), ("01", "02", "03")):
        block.add_text(caption, dxfattribs={"height": 3.0, "insert": (-8.0, y)})
    insert = doc.modelspace().add_blockref("N1DISTINCT", (0, 0))
    label = doc.modelspace().add_text("1n", dxfattribs={"insert": (0, 25), "height": 2})
    _app(insert, "LDPARTLAYT_PART", [(1000, "1")])
    _app(insert, "LDPARTLAYT_PARTLABEL_HANDLE", [(1005, label.dxf.handle)])
    _app(label, "LDPARTLAYT_PART_HANDLE", [(1005, insert.dxf.handle)])
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    assert sorted(port["endpoint_identity"] for port in data.part_instances[0].ports) == ["1n-01", "1n-02", "1n-03"]

