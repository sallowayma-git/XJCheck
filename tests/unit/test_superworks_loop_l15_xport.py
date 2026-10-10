"""L-15: an X-named TERMPOINT whose nearest-selected digit equals its number.

A component's pin drawn as "19" beside TERMPOINT "X19" takes the terminal-strip
spelling as its identity ("K742-X19"); the digit form ("K742-19") stays as an
alias. Only that case changes: numeric port numbers and digit mismatches keep
their previous identity.
"""
from __future__ import annotations

import ezdxf

from dwg_audit.extract.superworks_semantics import extract_superworks_semantics


def xdata(entity, app, values):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, values)


def component(doc, rows, label_value="K742", name="GRUS"):
    """Component block with one TERMPOINT per row (y, port_name, digit_texts) on the left
    edge; digit texts sit at x=-11 with the given y offsets, as in the GRUS-TCS layout."""
    block = doc.blocks.new(name)
    for y, port_name, digit_texts in rows:
        marker = block.add_lwpolyline([(-13, y), (-12, y)])
        xdata(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, port_name)])
        for text, offset in digit_texts:
            block.add_text(text, dxfattribs={"insert": (-11, y + offset), "height": 2})
    insert = doc.modelspace().add_blockref(name, (0, 0))
    label = doc.modelspace().add_text(label_value, dxfattribs={"insert": (0, 3), "height": 2})
    xdata(insert, "LDPARTLAYT_PART", [(1000, "1")])
    xdata(insert, "LDPARTLAYT_PARTLABEL_HANDLE", [(1005, label.dxf.handle)])
    xdata(label, "LDPARTLAYT_PART_HANDLE", [(1005, insert.dxf.handle)])
    return insert


def extract(doc):
    return extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")


def ports_by_name(data):
    assert len(data.part_instances) == 1
    return {port["port_number"]: port for port in data.part_instances[0].ports}


def test_x_named_port_with_matching_nearest_digit_takes_strip_spelling():
    doc = ezdxf.new()
    component(doc, [(15, "X18", [("18", -0.9)]), (10, "X19", [("19", -0.9)]), (5, "X20", [("20", -0.9)])])
    ports = ports_by_name(extract(doc))
    port = ports["X19"]
    assert port["pin"]["resolved"] is True
    assert port["pin"]["resolution_method"] == "definition_text_nearest"
    assert port["pin"]["normalized"] == "19"
    assert port["endpoint_identity"] == "K742-X19"
    # The digit form of the same pin is kept as an alias.
    assert port["pin"]["endpoint_aliases"] == ["K742-19"]
    # The neighbours keep their own identities.
    assert ports["X18"]["endpoint_identity"] == "K742-X18"
    assert ports["X20"]["endpoint_identity"] == "K742-X20"


def test_numeric_port_number_identity_is_unchanged():
    doc = ezdxf.new()
    component(doc, [(10, "19", [("19", -0.9)])])
    port = ports_by_name(extract(doc))["19"]
    assert port["pin"]["resolution_method"] == "definition_text_nearest"
    assert port["endpoint_identity"] == "K742-19"
    assert "endpoint_aliases" not in port["pin"]


def test_digit_mismatch_keeps_the_digit_identity():
    doc = ezdxf.new()
    # X19 has only the digit 18 beside it: the nearest pin does not name port 19.
    component(doc, [(10, "X19", [("18", -0.9)])])
    port = ports_by_name(extract(doc))["X19"]
    assert port["pin"]["normalized"] == "18"
    assert port["endpoint_identity"] == "K742-18"
    assert port["pin"]["endpoint_aliases"] == ["K742-X19"]


def test_connect_line_matches_the_x_named_identity():
    doc = ezdxf.new()
    component(doc, [(10, "X19", [("19", -0.9)])])
    # A leader from the port's end (-12, 10) to a connect label anchored at (-30, 10).
    line = doc.modelspace().add_line((-12, 10), (-30, 10))
    xdata(line, "LD_ConnectLine", [(1000, "1")])
    text = doc.modelspace().add_text("W19", dxfattribs={"insert": (-30, 10), "height": 2})
    xdata(text, "LD_ConnectLine", [(1000, "1")])
    data = extract(doc)
    assert len(data.connect_labels) == 1
    label = data.connect_labels[0]
    assert label.part_id is not None
    assert label.port_number == "X19"
    assert label.endpoint_identity == "K742-X19"
