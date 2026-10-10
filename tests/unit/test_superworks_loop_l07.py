"""L-07: connect-label leader pairing is anchor-based; a legacy pair whose wire sits on the
label anchor is not overwritten by a SW result for a different port."""
from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest

from dwg_audit.audit.superworks_extractor import _legacy_pairs_on_label_anchor_with_other_port
from dwg_audit.extract.superworks_semantics import (SuperworksData, _connect_labels,
    extract_superworks_semantics)

ANCHOR = (385.0, 131.5)


def _app(entity, app, tags):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, tags)


def _label(doc, value, anchor, insert_dx=-4.6, height=2.5):
    """Centred text: insertion point is offset from the alignment point (the real anchor)."""
    text = doc.modelspace().add_text(value, dxfattribs={
        "insert": (anchor[0] + insert_dx, anchor[1]), "align_point": anchor,
        "halign": 1, "height": height})
    _app(text, "LD_ConnectLine", [(1000, "label")])
    return text


def _leader(doc, start, end):
    line = doc.modelspace().add_line(start, end)
    _app(line, "LD_ConnectLine", [(1000, "leader")])
    return line


# Part/port matching is empty in these fixtures, so every resolved leader reports unresolved_part_port.
GEOMETRY_REASONS = {"unresolved_connect_line", "ambiguous_connect_line", "connect_line_geometry_not_unique"}


def _geometry_reasons(label):
    return sorted(set(label.reason_codes) & GEOMETRY_REASONS)


def _connect(doc):
    data = SuperworksData()
    _connect_labels(doc, data, "S1", "F1")
    return {label.text["value"]: label for label in data.connect_labels}


def test_leader_whose_end_is_on_the_anchor_wins_over_closer_handle():
    doc = ezdxf.new()
    text = _label(doc, "& 1-21n717", ANCHOR)
    _leader(doc, (385.0, 136.5), (400.0, 136.5))          # near handle, 5 from anchor
    own = _leader(doc, ANCHOR, (385.0, 140.0))             # farther handle, on anchor
    label = _connect(doc)["& 1-21n717"]
    assert label.line_handle == own.dxf.handle
    assert _geometry_reasons(label) == []


def test_coincident_leaders_with_equal_handle_gap_are_ambiguous():
    doc = ezdxf.new()
    doc.appids.new("LD_ConnectLine")                        # registering the appid in _label would shift handles
    _leader(doc, (385.0, 131.5), (390.0, 120.0))           # handle T-1, on anchor
    _label(doc, "& 1-21n717", ANCHOR)
    _leader(doc, (385.0, 131.5), (380.0, 120.0))           # handle T+1, on anchor
    label = _connect(doc)["& 1-21n717"]
    assert "ambiguous_connect_line" in label.reason_codes


def test_n715_and_n717_resolve_to_their_own_leaders():
    """Mirrors L-07 p044 S0020: the n717 label used to pick the port-4 leader 9 units away."""
    doc = ezdxf.new()
    _label(doc, "& 1-21n715", (368.75, 126.5))
    port4 = _leader(doc, (368.75, 127.5), (368.75, 126.5))
    port6 = _leader(doc, ANCHOR, (385.0, 140.0))
    _label(doc, "& 1-21n717", ANCHOR, insert_dx=-8.6)
    labels = _connect(doc)
    assert labels["& 1-21n715"].line_handle == port4.dxf.handle
    assert labels["& 1-21n717"].line_handle == port6.dxf.handle
    assert _geometry_reasons(labels["& 1-21n715"]) == []
    assert _geometry_reasons(labels["& 1-21n717"]) == []


def test_radius_fallback_uses_anchor_within_label_radius():
    doc = ezdxf.new()
    _label(doc, "& 1-21n717", ANCHOR, height=2.5)           # radius max(5, 3*2.5) = 7.5
    leader = _leader(doc, (ANCHOR[0] + 4.0, ANCHOR[1]), (400.0, 150.0))
    label = _connect(doc)["& 1-21n717"]
    assert label.line_handle == leader.dxf.handle
    assert _geometry_reasons(label) == []


def test_gnd_style_offset_from_anchor_still_associates():
    """GND-class labels sit about 3.6 from their leader end; the fallback must keep them."""
    doc = ezdxf.new()
    _label(doc, "GND", ANCHOR)
    leader = _leader(doc, (ANCHOR[0] - 3.6, ANCHOR[1]), (370.0, 150.0))
    label = _connect(doc)["GND"]
    assert label.line_handle == leader.dxf.handle
    assert _geometry_reasons(label) == []


def test_leader_beyond_radius_stays_unresolved():
    doc = ezdxf.new()
    _label(doc, "& 1-21n715", ANCHOR)
    _leader(doc, (ANCHOR[0] + 9.0, ANCHOR[1]), (420.0, 160.0))
    label = _connect(doc)["& 1-21n715"]
    assert not label.line_handle
    assert "unresolved_connect_line" in label.reason_codes


def _legacy(port, group_ends, pair_id="PCK0038", group_id="LG1"):
    (sx, sy), (ex, ey) = group_ends
    return (SimpleNamespace(pair_id=pair_id, line_group_id=group_id,
                            evidence={"component_port": port}),
            {group_id: SimpleNamespace(line_group_id=group_id, start_x=sx, start_y=sy, end_x=ex, end_y=ey)})


def _sw_label(port_number, anchor=ANCHOR):
    return SimpleNamespace(port_number=port_number, record_id="SWC:F1:1",
                           text={"anchor_x": anchor[0], "anchor_y": anchor[1], "text_id": "T1"})


@pytest.mark.parametrize("legacy_port,sw_port", [("6", "4")])
def test_legacy_pair_kept_when_port_disagrees_and_wire_is_on_anchor(legacy_port, sw_port):
    pair, groups = _legacy(legacy_port, ((ANCHOR[0], 140.0), (ANCHOR[0] + 0.3, ANCHOR[1])))
    assert _legacy_pairs_on_label_anchor_with_other_port([pair], _sw_label(sw_port), groups) == [pair]


def test_legacy_pair_not_protected_when_port_agrees():
    pair, groups = _legacy("4", ((ANCHOR[0], 140.0), ANCHOR))
    assert _legacy_pairs_on_label_anchor_with_other_port([pair], _sw_label("4"), groups) == []


def test_legacy_pair_not_protected_when_wire_is_off_anchor():
    pair, groups = _legacy("6", ((ANCHOR[0], 140.0), (ANCHOR[0], ANCHOR[1] + 1.0)))
    assert _legacy_pairs_on_label_anchor_with_other_port([pair], _sw_label("4"), groups) == []


def test_legacy_pair_without_recorded_port_is_not_protected():
    pair, groups = _legacy(None, ((ANCHOR[0], 140.0), ANCHOR))
    assert _legacy_pairs_on_label_anchor_with_other_port([pair], _sw_label("4"), groups) == []


def test_semantics_extract_still_resolves_port_for_leader_on_anchor():
    """End-to-end through the public extractor: port 4 leader on the n715 anchor."""
    doc = ezdxf.new()
    block = doc.blocks.new("KKTERM")
    marker = block.add_lwpolyline([(-0.5, 0), (0.5, 0)])
    _app(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, "4")])
    insert = doc.modelspace().add_blockref(block.name, (368.75, 126.5))
    _app(insert, "LD_SYMB2_SPECIAL", [(1000, "端子")])
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    assert data.ports and data.ports[0].port_number == "4"


# Q2-a: pass 1 locks anchor-coincident leaders; the radius fallback (pass 2) cannot take them.
def test_offset_label_does_not_take_leader_locked_by_coincident_anchor():
    """Mirrors L-07 p043 port 103: GND (offset 3.6) and '& 1-1Q1D1' (on the leader end).
    GND is listed first so the outcome cannot depend on document order."""
    doc = ezdxf.new()
    gnd_anchor = (ANCHOR[0] - 2.0, ANCHOR[1] + 3.0)        # distance to ANCHOR is sqrt(13) = 3.6
    _label(doc, "GND", gnd_anchor)
    own = _leader(doc, ANCHOR, (ANCHOR[0] + 10.0, ANCHOR[1] + 10.0))
    _label(doc, "& 1-1Q1D1", ANCHOR)
    labels = _connect(doc)
    assert labels["& 1-1Q1D1"].line_handle == own.dxf.handle
    assert _geometry_reasons(labels["& 1-1Q1D1"]) == []
    assert not labels["GND"].line_handle
    assert "unresolved_connect_line" in labels["GND"].reason_codes


def test_offset_label_falls_back_to_an_unlocked_leader():
    doc = ezdxf.new()
    gnd_anchor = (ANCHOR[0] - 2.0, ANCHOR[1] + 3.0)
    _label(doc, "GND", gnd_anchor)
    _leader(doc, ANCHOR, (ANCHOR[0] + 10.0, ANCHOR[1] + 10.0))   # locked by '& 1-1Q1D1'
    _label(doc, "& 1-1Q1D1", ANCHOR)
    free = _leader(doc, (gnd_anchor[0] + 3.6, gnd_anchor[1]), (gnd_anchor[0] + 20.0, gnd_anchor[1] - 20.0))
    labels = _connect(doc)
    assert labels["GND"].line_handle == free.dxf.handle
    assert _geometry_reasons(labels["GND"]) == []


def test_offset_label_with_only_locked_leader_stays_unresolved():
    """No unlocked leader in radius: the offset label must not preempt the anchor-owned leader."""
    doc = ezdxf.new()
    _label(doc, "GND", (ANCHOR[0] - 2.0, ANCHOR[1] + 3.0))
    _label(doc, "& 1-1Q1D1", ANCHOR)
    own = _leader(doc, ANCHOR, (ANCHOR[0] + 10.0, ANCHOR[1] + 10.0))
    labels = _connect(doc)
    assert labels["& 1-1Q1D1"].line_handle == own.dxf.handle
    assert not labels["GND"].line_handle
    assert "unresolved_connect_line" in labels["GND"].reason_codes
