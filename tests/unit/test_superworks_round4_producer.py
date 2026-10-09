"""Round-4 SuperWORKS producer fixes: strip table shape, terminal-strip contract,
pin proximity/alias/independence, mirrored INSERT coordinates, text width."""
from __future__ import annotations

from types import SimpleNamespace

import ezdxf
import pytest
from ezdxf.math import Matrix44, Vec3

from dwg_audit.audit.superworks_extractor import (StripMembership, _classify_terminal_strip_pairs,
                                                  extract_superworks_pairs)
from dwg_audit.domain.models import Pair, SwPartInstance, SwStripRow
from dwg_audit.extract.superworks_semantics import (SuperworksData, _definition_ports, corroborate_internal_pin_identities,
                                                    entity_insert_wcs, extract_superworks_semantics, text_anchor_wcs,
                                                    text_ref)
from dwg_audit.extract.text_geometry import cad_text_geometry


def _app(entity, app, values):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, values)


# ---- F5: mirrored INSERT coordinates are WCS -------------------------------------------

def test_mirrored_insert_position_is_converted_from_ocs_to_wcs():
    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.blocks.new("MIRROR")
    insert = msp.add_blockref("MIRROR", (100, 50), dxfattribs={"extrusion": (0, 0, -1)})
    assert tuple(round(v, 6) for v in entity_insert_wcs(insert)) == (-100.0, 50.0, 0.0)


def test_mirrored_symbol_is_not_flagged_stale_when_its_label_is_nearby():
    doc = ezdxf.new()
    msp = doc.modelspace()
    block = doc.blocks.new("MIRRORSYM")
    marker = block.add_lwpolyline([(-0.5, 0), (0.5, 0)])
    _app(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, "1")])
    insert = msp.add_blockref("MIRRORSYM", (100, 50), dxfattribs={"extrusion": (0, 0, -1)})
    label = msp.add_text("TB1", dxfattribs={"insert": (-100, 53), "height": 2})
    _app(insert, "LD_SYMB2_SPECIAL", [(1000, "端子")])
    _app(insert, "LD_SYMB2_LABEL", [(1005, label.dxf.handle)])
    _app(label, "LD_SYMB2_LABEL", [(1005, insert.dxf.handle)])
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    symbol = data.symbols[0]
    assert symbol.insert_x == pytest.approx(-100.0)
    assert symbol.insert_y == pytest.approx(50.0)
    assert "stale_label_reference" not in symbol.reason_codes


# ---- F4a: real text anchors -------------------------------------------------------------

def test_aligned_text_anchor_is_its_alignment_point():
    doc = ezdxf.new()
    text = doc.modelspace().add_text("J1", dxfattribs={"height": 3.0, "halign": 1, "valign": 0,
                                                       "align_point": (10, 5), "insert": (2, 1)})
    ref = text_ref(doc, text.dxf.handle)
    assert (ref["x"], ref["y"]) == pytest.approx((2.0, 1.0))
    assert (ref["anchor_x"], ref["anchor_y"]) == pytest.approx((10.0, 5.0))


def test_default_aligned_text_anchor_equals_insertion_point():
    doc = ezdxf.new()
    text = doc.modelspace().add_text("N", dxfattribs={"height": 3.0, "insert": (2, 1)})
    assert text_anchor_wcs(text).isclose(Vec3(2, 1, 0))


def test_mtext_anchor_converts_attachment_point_to_baseline_anchor():
    doc = ezdxf.new()
    top_left = doc.modelspace().add_mtext("ABC", dxfattribs={"char_height": 3.0, "insert": (20, 20), "attachment_point": 1})
    middle_centre = doc.modelspace().add_mtext("ABC", dxfattribs={"char_height": 3.0, "insert": (20, 20), "attachment_point": 5})
    corners = cad_text_geometry(top_left)["corners"]
    anchor = text_anchor_wcs(top_left)
    assert anchor.x == pytest.approx(corners[3][0]) and anchor.y == pytest.approx(corners[3][1])
    assert middle_centre.dxf.insert.isclose(Vec3(20, 20, 0))
    centre_anchor = text_anchor_wcs(middle_centre)
    assert centre_anchor.x == pytest.approx(20.0, abs=1e-6)
    assert centre_anchor.y < 20.0


def test_candidate_distance_uses_aligned_anchor_not_insertion():
    doc = ezdxf.new()
    block = doc.blocks.new("ANCHORBLK")
    marker = block.add_lwpolyline([(0, 0), (-1, 0)])
    _app(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, "")])
    # The insertion point is 0.5 from the port, but the centred text's anchor is 20 away.
    block.add_text("7", dxfattribs={"height": 3.0, "halign": 1, "align_point": (-20, 0), "insert": (-0.5, 0)})
    insert = doc.modelspace().add_blockref("ANCHORBLK", (0, 0))
    ports = list(_definition_ports(doc, insert, Matrix44(), "/x"))
    assert len(ports) == 1
    _, number, _, _, _, pin = ports[0]
    assert number == "" and not (pin or {}).get("resolved")


# ---- F4b: block-internal marker is not a pin ---------------------------------------------

def test_block_internal_marker_far_from_port_is_rejected_by_other_pins_bound():
    doc = ezdxf.new()
    block = doc.blocks.new("MARKERBLK")
    for y, name in ((0, "1"), (10, "2")):
        pl = block.add_lwpolyline([(0, y), (-1, y)])
        _app(pl, "LD_SYMB1LIB_TERMPOINT", [(1000, name)])
    port_c = block.add_lwpolyline([(0, 20), (-1, 20)])
    _app(port_c, "LD_SYMB1LIB_TERMPOINT", [(1000, "")])
    block.add_text("1", dxfattribs={"height": 3.0, "insert": (-2.0, 0.0)})
    block.add_text("2", dxfattribs={"height": 3.0, "insert": (-2.2, 10.0)})
    block.add_text("J1", dxfattribs={"height": 3.0, "insert": (-9.0, 20.0)})
    insert = doc.modelspace().add_blockref("MARKERBLK", (0, 0))
    result = {number: pin for _, number, _, _, _, pin in _definition_ports(doc, insert, Matrix44(), "/x")}
    assert result["1"]["normalized"] == "1" and result["1"]["resolution_method"] == "definition_text_nearest"
    assert result["2"]["normalized"] == "2"
    assert "" in result and not result[""].get("resolved")
    assert result[""]["nearest_rejected"]["handle"] and result[""]["nearest_rejected"]["distance"] == pytest.approx(8.0)


def test_label_shared_by_two_ports_of_one_block_is_not_rejected_by_the_bound():
    doc = ezdxf.new()
    block = doc.blocks.new("SHAREDBLK")
    port_a = block.add_lwpolyline([(0, 0), (-1, 0)])
    _app(port_a, "LD_SYMB1LIB_TERMPOINT", [(1000, "")])
    port_b = block.add_lwpolyline([(0, 10), (-1, 10)])
    _app(port_b, "LD_SYMB1LIB_TERMPOINT", [(1000, "")])
    # One DC label: 2.06 from port A (its nearest) and 8.0 from port B, both within 3 heights.
    block.add_text("DC", dxfattribs={"height": 3.0, "insert": (-1.5, 2.0)})
    insert = doc.modelspace().add_blockref("SHAREDBLK", (0, 0))
    pins = [pin for _, _, _, _, _, pin in _definition_ports(doc, insert, Matrix44(), "/x")]
    assert [pin.get("normalized") for pin in pins] == ["DC", "DC"]
    assert all(pin.get("resolution_method") == "definition_text_nearest" for pin in pins)


# ---- F4c / F4d: alias identity and independence of strip-reverse pins ---------------------

def _strip_row(record_id, header, row, connections):
    return SwStripRow(record_id=record_id, sheet_id="S1", file_id="F1", row_handle=record_id[-4:],
                      header={"handle": "H" + header, "normalized": header, "resolved": True, "text_id": "T" + header},
                      row={"normalized": row, "text_id": "R" + row},
                      endpoint_identity=header + row, connections=connections,
                      validation={"handle_resolved": True, "reciprocal_ok": True}, reason_codes=[])


def _connection(value, side="right", branch="_1", style="端子排内接元件"):
    return {"value": value, "normalized": value, "text_id": "C" + value, "side": side, "branch": branch,
            "style": style, "resolved": True, "reciprocal_ok": True, "handle": "X" + value}


def test_numbered_port_resolved_by_strip_alias_is_not_an_independent_pin():
    data = SuperworksData()
    data.strip_rows.append(_strip_row("SWR:F1:S1:AAAA", "ZD", "1", [_connection("HYKL-X12-2")]))
    part = SwPartInstance(record_id="PART1", sheet_id="S1", file_id="F1", insert_handle="I1", instance_path="/I1",
                          block_name="HYKL-X12-02", label={"normalized": "HYKL-X12", "text_id": "L1"}, part_no={},
                          part_type="", ports=[{"port_number": "OUT2", "endpoint_identity": None, "label": {"normalized": "HYKL-X12"},
                                                "pin": {"resolved": False}, "reason_codes": ["unresolved_pin_text"],
                                                "validation": {}, "category": "内部元件", "start_x": 0, "start_y": 0,
                                                "end_x": 1, "end_y": 0, "tolerance": 1, "record_id": "P1",
                                                "port_id": "P1"}],
                          raw_xdata={}, validation={}, reason_codes=[])
    data.part_instances.append(part)
    corroborate_internal_pin_identities(data)
    port = part.ports[0]
    assert port["endpoint_identity"] == "HYKL-X12-2"
    assert port["pin"]["resolution_method"] == "strip_reverse_corroboration"
    assert port["pin"]["pin_resolution_method"] == "strip_reverse_corroboration"
    assert port["pin"]["independent_verification"] is False
    assert data.pin_resolution_counts.get("independently_verified_ports", 0) == 0


def test_strip_reverse_pin_is_excluded_from_independent_counts_but_direct_pin_is_counted():
    data = SuperworksData()
    part = SwPartInstance(record_id="PART2", sheet_id="S1", file_id="F1", insert_handle="I2", instance_path="/I2",
                          block_name="B", label={"normalized": "CZ", "text_id": "L2"}, part_no={}, part_type="",
                          ports=[{"port_number": "E", "endpoint_identity": "CZ-E", "label": {"normalized": "CZ"},
                                  "pin": {"handle": "P", "resolved": True, "reciprocal_ok": True, "normalized": "E",
                                          "resolution_method": "instance_term_text"}, "reason_codes": [],
                                  "validation": {}, "category": "内部元件", "start_x": 0, "start_y": 0, "end_x": 1,
                                  "end_y": 0, "tolerance": 1, "record_id": "P2", "port_id": "P2"}],
                          raw_xdata={}, validation={}, reason_codes=[])
    data.part_instances.append(part)
    corroborate_internal_pin_identities(data)
    assert part.ports[0]["pin"]["pin_resolution_method"] == "instance_term_text"
    assert part.ports[0]["pin"]["independent_verification"] is True
    assert data.pin_resolution_counts["independently_verified_ports"] == 1


# ---- F1: terminal-strip row shape matches the legacy side layout --------------------------

def _page(sheet_id="S1"):
    return SimpleNamespace(sheet_id=sheet_id, sheet_order=1, page_type="屏端子图", sheet_category="屏端子图",
                           audit_disposition="audit", audit_role="audit")


@pytest.mark.parametrize("side", ["left", "right"])
def test_strip_row_mapping_fills_only_the_connection_side(side):
    data = SuperworksData()
    data.strip_rows.append(_strip_row("SWR:F1:S1:BBBB", "1-7XD", "1",
                                      [_connection("1XD3", side=side)]))
    output, mappings, _ = extract_superworks_pairs(data, pages=[_page()], texts=[], lines=[], line_groups=[],
                                                   pairs=[], table_mappings=[])
    assert len(output) == 1
    pair = output[0]
    mapping = pair.evidence["table_mapping"]
    other = "right" if side == "left" else "left"
    assert mapping[f"{side}_value"] == "1XD3"
    assert mapping[f"{side}_text_id"] == "C1XD3"
    assert mapping[f"{other}_value"] is None and mapping[f"{other}_text_id"] is None
    assert mapping["column_roles"] == {
        "left": "terminal_endpoint" if side == "left" else "empty",
        "middle": "row_number",
        "right": "terminal_endpoint" if side == "right" else "empty",
        "description": "empty",
    }
    assert mapping["sw_side"] == side
    assert pair.left_value == "1-7XD1" and pair.right_value == "1XD3"
    assert pair.left_text_id == "R1" and pair.right_text_id == "C1XD3"


# ---- F3: same-strip / cross-strip contract ------------------------------------------------

def _terminal_pair(left, right, left_aliases=(), right_aliases=()):
    evidence = {"source": "superworks", "pair_kind": "ordinary_pair",
                "superworks": {"left": {"category": "端子", "value": left, "endpoint_aliases": list(left_aliases)},
                               "right": {"category": "端子", "value": right, "endpoint_aliases": list(right_aliases)}}}
    return Pair(pair_id=f"{left}->{right}", line_group_id="G", sheet_id="S1", file_id="F1",
                selected_pair_candidate_id=None, left_value=left, right_value=right, confidence=.99,
                status="pass", rationale="", evidence=evidence)


def _membership_data():
    data = SuperworksData()
    data.strip_rows += [
        _strip_row("SWR:F1:S1:0001", "1-4Q2D", "1", [_connection("KD23")]),
        _strip_row("SWR:F1:S1:0002", "1-4Q2D", "3", []),
        _strip_row("SWR:F1:S1:0003", "KD", "23", [_connection("1-4Q2D1")]),
        _strip_row("SWR:F1:S1:0004", "1-4Q1D", "2", [_connection("5CD1")]),
        _strip_row("SWR:F1:S1:0005", "5CD", "1", []),
    ]
    data.dictionary = {"strip_order": [{"name": "1-4Q2D"}, {"name": "1-4Q1D"}, {"name": "7UD"}, {"name": "KD"},
                                       {"name": "5CD"}]}
    return data


def test_same_strip_pair_is_a_terminal_short_bridge_with_header():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("1-4Q2D1", "1-4Q2D3")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["terminal_short_bridge"] is True
    assert pair.evidence["strip_header"] == "1-4Q2D"
    assert pair.evidence["strip_membership"] == "same_strip"
    assert "terminal_cross_strip_link" not in pair.evidence


def test_range_label_resolves_to_its_strip_header_through_project_names():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("7UD16~18", "7UD17")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["terminal_short_bridge"] is True
    assert pair.evidence["strip_header"] == "7UD"


def test_row_number_with_letter_suffix_resolves_through_the_strip_name():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("1-4Q2D1", "1-4Q2D1A")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["strip_header"] == "1-4Q2D"
    assert pair.evidence["strip_membership"] == "same_strip"


def test_range_label_on_known_strip_row_uses_the_row_header():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("1-4Q2D3~7", "1-4Q2D1")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["strip_header"] == "1-4Q2D"
    assert pair.evidence["strip_membership"] == "same_strip"


def test_cross_strip_pair_is_corroborated_when_a_row_lists_the_other_end():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("KD23", "1-4Q2D1")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["terminal_cross_strip_link"] is True
    assert pair.evidence["strip_corroborated"] is True
    assert pair.evidence["strip_headers"] == ["KD", "1-4Q2D"]
    assert pair.evidence["strip_membership"] == "cross_strip"
    assert "terminal_short_bridge" not in pair.evidence


def test_cross_strip_pair_without_listing_is_not_corroborated():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("1-4Q1D2", "5CD1")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["terminal_cross_strip_link"] is True
    assert pair.evidence["strip_corroborated"] is True
    pair = _terminal_pair("1-4Q1D3", "5CD1")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["strip_corroborated"] is False


def test_undecidable_terminal_is_marked_unknown_without_either_flag():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("ZZ9", "1-4Q2D1")
    _classify_terminal_strip_pairs([pair], membership)
    assert pair.evidence["strip_membership"] == "unknown"
    assert "terminal_short_bridge" not in pair.evidence
    assert "terminal_cross_strip_link" not in pair.evidence


def test_non_terminal_pair_gets_no_contract_fields():
    membership = StripMembership(_membership_data())
    pair = _terminal_pair("1-4Q2D1", "1-4Q2D3")
    pair.evidence["superworks"]["right"]["category"] = "装置端子"
    _classify_terminal_strip_pairs([pair], membership)
    assert "strip_membership" not in pair.evidence


# ---- F6: text width uses the style width factor ------------------------------------------

@pytest.fixture()
def narrow_doc():
    doc = ezdxf.new()
    doc.styles.new("W07", dxfattribs={"width": 0.7, "font": "txt"})
    doc.styles.new("W10", dxfattribs={"font": "txt"})
    return doc


def test_text_layout_width_applies_style_width_factor(narrow_doc):
    msp = narrow_doc.modelspace()
    wide = msp.add_text("ABCDEFG", dxfattribs={"height": 2.5, "style": "W10", "insert": (10, 10)})
    narrow = msp.add_text("ABCDEFG", dxfattribs={"height": 2.5, "style": "W07", "insert": (10, 10)})
    ratio = cad_text_geometry(narrow)["width"] / cad_text_geometry(wide)["width"]
    assert ratio == pytest.approx(0.7, rel=1e-3)
    assert not narrow.dxf.hasattr("width")


def test_text_own_width_attribute_takes_precedence_over_style(narrow_doc):
    msp = narrow_doc.modelspace()
    wide = msp.add_text("ABCDEFG", dxfattribs={"height": 2.5, "style": "W10", "insert": (10, 10)})
    own = msp.add_text("ABCDEFG", dxfattribs={"height": 2.5, "style": "W07", "width": 1.0, "insert": (10, 10)})
    assert cad_text_geometry(own)["width"] == pytest.approx(cad_text_geometry(wide)["width"], rel=1e-6)


def test_mtext_layout_width_applies_style_width_factor(narrow_doc):
    msp = narrow_doc.modelspace()
    wide = msp.add_mtext("ABCDEFG", dxfattribs={"char_height": 2.5, "style": "W10", "insert": (10, 10)})
    narrow = msp.add_mtext("ABCDEFG", dxfattribs={"char_height": 2.5, "style": "W07", "insert": (10, 10)})
    ratio = cad_text_geometry(narrow)["width"] / cad_text_geometry(wide)["width"]
    assert ratio == pytest.approx(0.7, rel=1e-3)


# ---- F4a/F4b integration: a TERMPOINT name stays a plain port name -------------------------

def test_termpoint_name_without_pin_text_keeps_its_name_as_port_number():
    doc = ezdxf.new()
    block = doc.blocks.new("NAMEBLK")
    marker = block.add_lwpolyline([(0, 0), (-1, 0)])
    _app(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, "IN2")])
    insert = doc.modelspace().add_blockref("NAMEBLK", (0, 0))
    ports = list(_definition_ports(doc, insert, Matrix44(), "/x"))
    assert ports[0][1] == "IN2"
    assert ports[0][5] is None
