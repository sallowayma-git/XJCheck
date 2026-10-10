"""L-08: a far but reciprocal, resolvable terminal label is a layout observation, not a stale reference."""
from __future__ import annotations

import ezdxf

from dwg_audit.audit.superworks_extractor import _true_conflicts
from dwg_audit.extract.superworks_semantics import extract_superworks_semantics, normalize

IDENTITY = "1C12D6"


def _app(entity, app, tags):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, tags)


def _terminal(doc, label_value, label_at, back_link=True, forward_link=True):
    block = doc.blocks.new(f"TERM{len(doc.blocks)}")
    marker = block.add_lwpolyline([(-0.5, 0), (0.5, 0)])
    _app(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, "1")])
    insert = doc.modelspace().add_blockref(block.name, (0, 0))
    label = doc.modelspace().add_text(label_value, dxfattribs={"insert": label_at, "height": 2})
    _app(insert, "LD_SYMB2_SPECIAL", [(1000, "端子")])
    if forward_link:
        _app(insert, "LD_SYMB2_LABEL", [(1005, label.dxf.handle)])
    if back_link:
        _app(label, "LD_SYMB2_LABEL", [(1005, insert.dxf.handle)])
    return insert, label


def _extract(doc):
    return extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")


def test_far_reciprocal_resolvable_label_is_layout_observation_and_keeps_identity():
    doc = ezdxf.new()
    _terminal(doc, IDENTITY, (300, 3))
    data = _extract(doc)
    symbol = data.symbols[0]
    assert symbol.validation["label_distance"] > 30
    assert "stale_label_reference" not in symbol.reason_codes
    assert "label_far_from_symbol" in symbol.reason_codes
    assert symbol.endpoint_identity == normalize(IDENTITY)
    port = data.ports[0]
    assert "stale_label_reference" not in port.reason_codes
    assert port.endpoint_identity == normalize(IDENTITY)
    assert _true_conflicts(port.reason_codes) == []


def test_far_nonreciprocal_label_stays_stale():
    doc = ezdxf.new()
    _terminal(doc, IDENTITY, (300, 3), back_link=False)
    symbol = _extract(doc).symbols[0]
    assert "stale_label_reference" in symbol.reason_codes
    assert "label_far_from_symbol" not in symbol.reason_codes


def test_far_label_with_nearer_same_identity_text_on_sheet_stays_stale():
    doc = ezdxf.new()
    _terminal(doc, IDENTITY, (300, 3))
    doc.modelspace().add_text(IDENTITY, dxfattribs={"insert": (2, 3), "height": 2})
    symbol = _extract(doc).symbols[0]
    assert "stale_label_reference" in symbol.reason_codes
    assert "label_far_from_symbol" not in symbol.reason_codes
    assert "stale_label_reference" in _true_conflicts(symbol.reason_codes)


def test_nearer_same_identity_text_inside_a_block_counts():
    doc = ezdxf.new()
    _terminal(doc, IDENTITY, (300, 3))
    plain = doc.blocks.new("PLAIN_TEXT_HOLDER")
    plain.add_text(IDENTITY, dxfattribs={"insert": (0, 1), "height": 2})
    doc.modelspace().add_blockref("PLAIN_TEXT_HOLDER", (250, 0))
    symbol = _extract(doc).symbols[0]
    assert "stale_label_reference" in symbol.reason_codes
    assert "label_far_from_symbol" not in symbol.reason_codes


def test_same_identity_text_farther_than_the_label_does_not_make_it_stale():
    doc = ezdxf.new()
    _terminal(doc, IDENTITY, (300, 3))
    doc.modelspace().add_text(IDENTITY, dxfattribs={"insert": (600, 3), "height": 2})
    symbol = _extract(doc).symbols[0]
    assert "stale_label_reference" not in symbol.reason_codes
    assert "label_far_from_symbol" in symbol.reason_codes


def test_label_within_threshold_produces_no_layout_or_stale_reason():
    doc = ezdxf.new()
    _terminal(doc, IDENTITY, (20, 3))
    symbol = _extract(doc).symbols[0]
    assert not {"stale_label_reference", "label_far_from_symbol"} & set(symbol.reason_codes)
