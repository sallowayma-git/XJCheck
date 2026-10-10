"""V-06: X-named TERMPOINT ports and their nearest digit pin texts (K741/K742 class).

Terminal strips write a component pin as its port name (K741-X15); the SuperWORKS
drawing shows the same pin as its digit (15). The nearest digit beside each port
must therefore be the port's own number, and the port keeps the X-name as an alias.
"""
from __future__ import annotations

import ezdxf

from dwg_audit.extract.superworks_semantics import extract_superworks_semantics


def xdata(entity, app, values):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, values)


def grus_part(doc, rows, label_value="K741", name="GRUS"):
    """Component block: one TERMPOINT per row (y, port name) on the left edge,
    each with its digit text beside it, as in the GRUS-TCS drawing layout.
    rows: list of (y, port_name, digit_texts) where digit_texts is a list of
    (text, y_offset) pairs placed at x=-11."""
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


def ports_by_name(doc):
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    assert len(data.part_instances) == 1
    return {port["port_number"]: port for port in data.part_instances[0].ports}


def test_nearest_digit_is_the_port_own_number_for_x_named_termpoints():
    doc = ezdxf.new()
    # Digit text sits 1 unit below each pin's own row; the next pin's digit is 5 units away.
    rows = [(10, "X1", [("1", -0.9)]), (5, "X2", [("2", -0.9)]),
            (0, "X3", [("3", -0.9)]), (-5, "X4", [("4", -0.9)])]
    grus_part(doc, rows)
    ports = ports_by_name(doc)
    for number in ("1", "2", "3", "4"):
        port = ports[f"X{number}"]
        assert port["pin"]["resolved"] is True
        assert port["pin"]["normalized"] == number
        assert port["pin"]["resolution_method"] == "definition_text_nearest"
        # L-15: the identity takes the terminal-strip spelling; the digit form is the alias.
        assert port["endpoint_identity"] == f"K741-X{number}"
        assert port["pin"]["endpoint_aliases"] == [f"K741-{number}"]


def test_neighbour_digit_does_not_take_an_x_named_port():
    doc = ezdxf.new()
    rows = [(10, "X1", [("1", -0.9)]), (5, "X2", [("2", -0.9)]), (0, "X3", [("3", -0.9)])]
    grus_part(doc, rows)
    ports = ports_by_name(doc)
    # X2's digit lies about 4.2 units from X3's pin; X3's own digit is about 1.3 units away.
    assert ports["X3"]["pin"]["normalized"] == "3"
    assert ports["X3"]["pin"]["nearest_distance"] < 2.0


def test_equidistant_digits_leave_the_port_unresolved():
    doc = ezdxf.new()
    # Two digits equidistant from the same pin: no unique nearest, so no identity.
    rows = [(0, "X5", [("5", 0.9), ("6", -0.9)])]
    grus_part(doc, rows)
    port = ports_by_name(doc)["X5"]
    assert not port["pin"].get("resolved")
    assert port["endpoint_identity"] is None
