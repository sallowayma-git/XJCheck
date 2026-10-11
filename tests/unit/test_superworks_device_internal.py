"""Device-internal links of SuperWORKS device terminals (DEV-INT): rule, exclusions and wire grouping."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from dwg_audit.audit.superworks_device_internal import (
    build_device_internal_links,
    pcl_index,
    wire_keys_from_lines,
)


def _label(text, resolved=True):
    return {"normalized": text, "resolved": resolved, "value": text}


def _port(record_id, category, *, file_id="F1", identity=None, label="1n", port_number="1", contacts=("W1",),
          resolved=True):
    return {
        "record_id": record_id, "file_id": file_id, "sheet_id": "S1", "insert_handle": record_id.upper(),
        "port_number": port_number, "category": category, "endpoint_identity": identity,
        "label": _label(label, resolved) if label is not None else {}, "wire_contacts":
            [{"wire_handle": handle, "wire_side": 0} for handle in contacts],
    }


def _device(record_id="D1", identity="1n705", label="1n", contacts=("W1",), **kwargs):
    return _port(record_id, "装置端子", identity=identity, label=label, contacts=contacts, **kwargs)


def _internal(record_id="Q1", label="1n", contacts=("W1",), category="内部元件", **kwargs):
    return _port(record_id, category, identity=None, label=label, contacts=contacts, port_number="1", **kwargs)


def _pcl_row(record_id, identity, logical_pin="705"):
    ends = [{"role": "LOCAL", "identity": identity, "port_number": logical_pin}]
    return {"record_id": record_id, "source_kind": "PCL", "logical_pin": logical_pin,
            "ends_json": json.dumps(ends, ensure_ascii=False)}


def test_device_terminal_wired_to_own_internal_pin_is_linked():
    result = build_device_internal_links([_device(), _internal()], [])
    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link["port_id"] == "D1"
    assert link["element_port_id"] == "Q1"
    assert link["device_label"] == "1n"
    assert link["pin_tail"] == "705"
    assert link["wire_handle"] == "W1"
    assert link["pcl_corroborated"] is False
    assert result["covered"] == {"D1": [link["link_id"]]}
    assert result["stats"]["linked"] == 1


def test_pcl_row_naming_the_same_identity_corroborates():
    result = build_device_internal_links([_device(), _internal()], [_pcl_row("PCL1", "1n705")])
    link = result["links"][0]
    assert link["pcl_corroborated"] is True
    assert link["pcl_record_ids"] == ["PCL1"]
    assert result["stats"]["pcl_corroborated"] == 1


def test_pcl_row_with_other_identity_does_not_corroborate():
    result = build_device_internal_links([_device(), _internal()], [_pcl_row("PCL1", "1n706", "706")])
    assert result["links"][0]["pcl_corroborated"] is False


def test_pcl_row_is_only_read_from_pcl_rows():
    loggen = dict(_pcl_row("LG1", "1n705"), source_kind="LOGGEN")
    assert pcl_index([loggen]) == {}


def test_other_end_terminal_strip_is_not_internal():
    ports = [_device(), _port("T1", "端子", identity="1QD5", label="1QD", contacts=("W1",))]
    result = build_device_internal_links(ports, [])
    assert result["links"] == []
    assert result["stats"]["excluded:other_end_category:端子"] == 1


def test_wire_with_device_and_internal_and_terminal_is_multi_end():
    ports = [_device(), _internal(), _port("T1", "端子", identity="1QD5", label="1QD", contacts=("W1",))]
    result = build_device_internal_links(ports, [])
    assert result["links"] == []
    assert result["stats"]["excluded:wire_multi_end"] == 1


def test_wire_with_two_internal_pins_is_not_linked():
    ports = [_device(), _internal("Q1"), _internal("Q2")]
    result = build_device_internal_links(ports, [])
    assert result["links"] == []
    assert result["stats"]["excluded:wire_multi_end_internal"] == 1


def test_wire_without_other_port_is_dangling():
    result = build_device_internal_links([_device()], [])
    assert result["links"] == []
    assert result["stats"]["excluded:wire_no_other_port"] == 1


def test_related_label_is_counted_not_linked():
    result = build_device_internal_links([_device(identity="1n705"), _internal(label="1-1n")], [])
    assert result["links"] == []
    assert result["stats"]["excluded:element_label_related"] == 1


def test_different_label_is_counted_not_linked():
    result = build_device_internal_links([_device(identity="1n705"), _internal(label="2n")], [])
    assert result["links"] == []
    assert result["stats"]["excluded:element_label_differs"] == 1


def test_station_prefixed_device_identity_uses_its_full_label():
    result = build_device_internal_links(
        [_device(identity="2-1n323", label="2-1n"), _internal(label="2-1n")], [])
    link = result["links"][0]
    assert link["device_label"] == "2-1n"
    assert link["pin_tail"] == "323"


def test_device_identity_missing_is_excluded():
    result = build_device_internal_links([_device(identity=None), _internal()], [])
    assert result["links"] == []
    assert result["stats"]["excluded:identity_missing"] == 1


def test_identity_must_start_with_the_device_label():
    result = build_device_internal_links([_device(identity="2n705"), _internal()], [])
    assert result["links"] == []
    assert result["stats"]["excluded:identity_not_label_prefixed"] == 1


def test_unresolved_label_or_no_contact_is_excluded():
    no_label = build_device_internal_links([_device(resolved=False), _internal()], [])
    no_contact = build_device_internal_links([_device(contacts=()), _internal()], [])
    assert no_label["links"] == [] and no_label["stats"]["excluded:label_unresolved"] == 1
    assert no_contact["links"] == [] and no_contact["stats"]["excluded:no_wire_contact"] == 1


def test_two_internal_wires_for_one_terminal_are_ambiguous():
    ports = [_device(contacts=("W1", "W2")), _internal("Q1", contacts=("W1",)), _internal("Q2", contacts=("W2",))]
    result = build_device_internal_links(ports, [])
    assert result["links"] == []
    assert result["stats"]["excluded:multiple_internal_wires"] == 1


def test_wire_key_joins_segments_of_one_line_group():
    # Device terminal on segment W1; the internal pin on segment W2; both lie in one line group, which also
    # carries the terminal strip's segment W3. The group is one wire, so the terminal is multi-ended.
    lines = [
        {"file_id": "F1", "line_id": "L1", "handle": "W1", "source_block_name": None},
        {"file_id": "F1", "line_id": "L2", "handle": "W2", "source_block_name": None},
        {"file_id": "F1", "line_id": "L3", "handle": "W3", "source_block_name": None},
    ]
    groups = [{"file_id": "F1", "member_line_ids": ["L1", "L2"]}, {"file_id": "F1", "member_line_ids": ["L2", "L3"]}]
    keys = wire_keys_from_lines(lines, groups)
    assert keys[("F1", "W1")] == keys[("F1", "W2")] == keys[("F1", "W3")]
    ports = [_device(contacts=("W1",)), _internal("Q1", contacts=("W2",)),
             _port("T1", "端子", identity="1QD5", label="1QD", contacts=("W3",))]
    result = build_device_internal_links(ports, [], wire_group_of=keys)
    assert result["links"] == []
    assert result["stats"]["excluded:wire_multi_end"] == 1


def test_wire_key_ignores_block_internal_lines_for_handles_and_keeps_ungrouped_handles():
    lines = [
        {"file_id": "F1", "line_id": "L1", "handle": "H1", "source_block_name": None},
        {"file_id": "F1", "line_id": "L9", "handle": "H1", "source_block_name": "SYMB2_M_PWF191"},
    ]
    groups = [{"file_id": "F1", "member_line_ids": ["L1", "L9"]}]
    keys = wire_keys_from_lines(lines, groups)
    assert keys[("F1", "H1")][0] == "F1"
    assert ("F1", "H2") not in keys


def test_a_port_touching_two_segments_of_one_group_is_counted_once():
    keys = {("F1", "W1"): ("F1", "W:G"), ("F1", "W2"): ("F1", "W:G")}
    ports = [_device(contacts=("W1", "W2")), _internal("Q1", contacts=("W1",))]
    result = build_device_internal_links(ports, [], wire_group_of=keys)
    assert len(result["links"]) == 1
    assert result["links"][0]["wire_port_ids"] == ["D1", "Q1"]


def test_string_encoded_label_and_contacts_are_read():
    device = _device()
    device["label"] = json.dumps(_label("1n"), ensure_ascii=False)
    device["wire_contacts"] = json.dumps([{"wire_handle": "W1"}], ensure_ascii=False)
    internal = _internal()
    internal["label"] = json.dumps(_label("1n"), ensure_ascii=False)
    internal["wire_contacts"] = json.dumps([{"wire_handle": "W1"}], ensure_ascii=False)
    result = build_device_internal_links([device, internal], [])
    assert len(result["links"]) == 1


def test_ports_are_read_only_and_link_ids_are_stable():
    ports = [_device(), _internal()]
    snapshot = json.dumps(ports, sort_keys=True, ensure_ascii=False)
    first = build_device_internal_links(ports, [])
    second = build_device_internal_links(ports, [])
    assert json.dumps(ports, sort_keys=True, ensure_ascii=False) == snapshot
    assert first["links"][0]["link_id"] == second["links"][0]["link_id"]
    assert first["links"][0]["link_id"].startswith("XDI:")


def test_artifacts_add_internal_coverage_without_changing_pairs(tmp_path):
    from types import SimpleNamespace

    from dwg_audit.domain.models import SheetRecord, SwPort
    from dwg_audit.extract.superworks_semantics import SuperworksData
    from dwg_audit.report.superworks_artifacts import write_superworks_artifacts

    page = SheetRecord("S1", "F1", "01 x.dwg", 1, "01", "x", "二次原理图", "primary", "filename", True,
                       audit_disposition="audit")
    device = SwPort(record_id="D1", sheet_id="S1", file_id="F1", insert_handle="HD", port_number="1",
                    category="装置端子", endpoint_identity="1n705", label=_label("1n"),
                    wire_contacts=[{"wire_handle": "W1", "wire_side": 0}])
    element = SwPort(record_id="Q1", sheet_id="S1", file_id="F1", insert_handle="HQ", port_number="1",
                     category="内部元件", endpoint_identity=None, label=_label("1n"),
                     wire_contacts=[{"wire_handle": "W1", "wire_side": 1}])
    data = SuperworksData(ports=[device, element], wire_route_rows=[_pcl_row("PCL1", "1n705")])
    line = SimpleNamespace(file_id="F1", line_id="L1", handle="W1", source_block_name=None,
                           start_x=0.0, start_y=0.0, end_x=1.0, end_y=0.0)
    group = SimpleNamespace(file_id="F1", member_line_ids=["L1"])
    artifacts = SimpleNamespace(superworks=data, superworks_supersession=[], lines=[line], line_groups=[group],
                                scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"), pages=[page]),
                                pairs=[])
    write_superworks_artifacts(artifacts, tmp_path)
    summary = json.loads((tmp_path / "superworks_summary.json").read_text(encoding="utf-8"))
    assert summary["port_coverage"]["consumed"] == 0
    assert summary["port_coverage_with_continuity"]["consumed"] == 0
    assert summary["port_coverage_with_internal"]["consumed"] == 1
    assert summary["port_coverage_with_internal"]["added_by_continuity_and_internal"] == 1
    assert summary["device_internal"]["link_count"] == 1
    assert summary["device_internal"]["pcl_corroborated"] == 1
    assert summary["coverage_views"]["strict"]["consumed"] == 0
    assert summary["coverage_views"]["with_internal"]["consumed"] == 1
    assert summary["coverage_views"]["total"]["consumed"] == 1
    links = pd.read_parquet(tmp_path / "sw_device_internal_links.parquet")
    assert len(links) == 1 and links.port_id.iloc[0] == "D1"
    coverage = pd.read_parquet(tmp_path / "sw_port_coverage.parquet").set_index("port_id")
    assert json.loads(coverage.loc["D1", "device_internal_link_ids"]) == [links.link_id.iloc[0]]
    assert bool(coverage.loc["D1", "consumed_with_internal"]) and not bool(coverage.loc["D1", "consumed"])


# G1P: a single-end wire of a device terminal may end on an unregistered SYMB2 block (label, no LD_SYMB2_SPECIAL).


def _contact(handle, side, x, y):
    return {"wire_handle": handle, "wire_side": side, "x": x, "y": y}


def _device_at(contacts, identity="1n705", label="1n"):
    device = _device(identity=identity, label=label, contacts=())
    device["wire_contacts"] = list(contacts)
    return device


def _block(record_id="USY:F1:S1:B1", label="1n", resolved=True, a=(9.5, 0.0), b=(10.5, 0.0), number="1", insert="B1"):
    return {"record_id": record_id, "file_id": "F1", "sheet_id": "S1", "insert_handle": insert,
            "label_value": label, "label_resolved": resolved,
            "termpoints": [{"number": number, "a": a, "b": b}]}


def _single_wire():
    """Device contact at (0.5, 0) on W1; the wire runs to (10, 0)."""
    return {"wire_endpoints": {("F1", "W1"): {0: (0.5, 0.0), 1: (10.0, 0.0)}}}


def test_single_end_wire_on_matching_unregistered_pin_is_linked_as_coverage():
    device = _device_at([_contact("W1", 0, 0.5, 0.0)])
    result = build_device_internal_links([device], [], unregistered=[_block()], **_single_wire())
    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link["source"] == "unregistered_symb2_pin"
    assert link["element_block_record_id"] == "USY:F1:S1:B1"
    assert link["element_port_id"] is None
    assert link["element_label"] == "1n"
    assert (link["far_x"], link["far_y"]) == (10.0, 0.0)
    assert link["wire_port_ids"] == ["D1"]
    assert result["covered"] == {"D1": [link["link_id"]]}
    assert result["stats"]["unregistered:candidate"] == 1
    assert result["stats"]["linked_unregistered"] == 1
    assert "excluded:wire_no_other_port" not in result["stats"]
    assert result["unregistered_decisions"][0]["reason"] == "candidate"


def test_unregistered_label_must_equal_the_device_label():
    device = _device_at([_contact("W1", 0, 0.5, 0.0)])
    result = build_device_internal_links([device], [], unregistered=[_block(label="2n")], **_single_wire())
    assert result["links"] == []
    assert result["stats"]["unregistered:label_differs"] == 1
    assert result["stats"]["excluded:wire_no_other_port"] == 1


def test_station_prefixed_unregistered_label_is_counted_apart():
    device = _device_at([_contact("W1", 0, 0.5, 0.0)], identity="1-1n705", label="1-1n")
    result = build_device_internal_links([device], [], unregistered=[_block(label="1n")], **_single_wire())
    assert result["links"] == []
    assert result["stats"]["unregistered:label_related"] == 1


def test_unresolved_unregistered_label_is_not_linked():
    device = _device_at([_contact("W1", 0, 0.5, 0.0)])
    result = build_device_internal_links([device], [], unregistered=[_block(label="", resolved=False)],
                                         **_single_wire())
    assert result["links"] == []
    assert result["stats"]["unregistered:label_unresolved"] == 1


def test_two_blocks_at_the_far_end_are_ambiguous():
    device = _device_at([_contact("W1", 0, 0.5, 0.0)])
    blocks = [_block(record_id="USY:F1:S1:B1", insert="B1"), _block(record_id="USY:F1:S1:B2", insert="B2")]
    result = build_device_internal_links([device], [], unregistered=blocks, **_single_wire())
    assert result["links"] == []
    assert result["stats"]["unregistered:multiple_blocks"] == 1


def test_pin_contact_tolerance_is_the_port_rule_of_0_6_times_the_segment_length():
    # TERMPOINT segment (10.5, 0)-(10.5, 2): length 2, tolerance 1.2. The far end (10, 0) is 0.5 from a: a contact.
    device = _device_at([_contact("W1", 0, 0.5, 0.0)])
    near = build_device_internal_links([device], [], unregistered=[_block(a=(10.5, 0.0), b=(10.5, 2.0))],
                                       **_single_wire())
    assert len(near["links"]) == 1
    # Far end (7, 0): 3.5 from a and more from b, beyond the tolerance.
    miss = build_device_internal_links([_device_at([_contact("W1", 0, 0.5, 0.0)])], [],
                                       unregistered=[_block(a=(10.5, 0.0), b=(10.5, 2.0))],
                                       wire_endpoints={("F1", "W1"): {0: (0.5, 0.0), 1: (7.0, 0.0)}})
    assert miss["links"] == []
    assert miss["stats"]["unregistered:no_far_pin"] == 1


def test_an_interior_junction_of_one_wire_is_not_a_far_end():
    # Two segments of one line group meet at (5, 0); the free far end is (10, 0). A block on the junction is no far end.
    keys = {("F1", "W1"): ("F1", "W:G"), ("F1", "W2"): ("F1", "W:G")}
    endpoints = {("F1", "W1"): {0: (0.5, 0.0), 1: (5.0, 0.0)}, ("F1", "W2"): {0: (5.0, 0.0), 1: (10.0, 0.0)}}
    device = _device_at([_contact("W1", 0, 0.5, 0.0)])
    result = build_device_internal_links([device], [], wire_group_of=keys,
                                         unregistered=[_block(a=(4.5, 0.0), b=(5.5, 0.0))],
                                         wire_endpoints=endpoints)
    assert result["links"] == []
    assert result["stats"]["unregistered:no_far_pin"] == 1


def test_free_far_end_of_a_two_segment_wire_is_linked():
    keys = {("F1", "W1"): ("F1", "W:G"), ("F1", "W2"): ("F1", "W:G")}
    endpoints = {("F1", "W1"): {0: (0.5, 0.0), 1: (5.0, 0.0)}, ("F1", "W2"): {0: (5.0, 0.0), 1: (10.0, 0.0)}}
    device = _device_at([_contact("W1", 0, 0.5, 0.0)])
    result = build_device_internal_links([device], [], wire_group_of=keys, unregistered=[_block()],
                                         wire_endpoints=endpoints)
    assert len(result["links"]) == 1
    assert result["links"][0]["wire_handle"] == "W1"


def test_terminal_with_an_internal_wire_and_an_unregistered_wire_is_ambiguous():
    internal = _internal("Q1", contacts=("W2",))
    device = _device_at([_contact("W1", 0, 0.5, 0.0), _contact("W2", 0, 0.5, 5.0)])
    endpoints = {("F1", "W1"): {0: (0.5, 0.0), 1: (10.0, 0.0)}, ("F1", "W2"): {0: (0.5, 5.0), 1: (20.0, 5.0)}}
    result = build_device_internal_links([device, internal], [], unregistered=[_block()], wire_endpoints=endpoints)
    assert result["links"] == []
    assert result["stats"]["excluded:multiple_internal_wires"] == 1


def test_extraction_records_the_unregistered_block_and_the_artifacts_count_it_as_coverage_only(tmp_path):
    """From an open DXF: the block is recorded, adds no symbol, port, pair or issue; coverage gains one link."""
    from types import SimpleNamespace

    import ezdxf

    from dwg_audit.domain.models import SheetRecord
    from dwg_audit.extract.superworks_semantics import extract_superworks_semantics
    from dwg_audit.report.superworks_artifacts import _device_internal_links, write_superworks_artifacts
    from test_superworks_semantics import symbol, xdata

    doc = ezdxf.new()
    symbol(doc, "装置端子", "1n", pin_value="705")
    # Unregistered SYMB2 block at (10, 0): label "1n", TERMPOINT (9.5, 0)-(10.5, 0), no LD_SYMB2_SPECIAL.
    block = doc.blocks.new("SYMB2_M_PWF999")
    marker = block.add_lwpolyline([(-.5, 0), (.5, 0)])
    xdata(marker, "LD_SYMB1LIB_TERMPOINT", [(1000, "1")])
    insert = doc.modelspace().add_blockref("SYMB2_M_PWF999", (10, 0))
    label = doc.modelspace().add_text("1n", dxfattribs={"insert": (10, 3), "height": 2})
    xdata(insert, "LD_SYMB2_LABEL", [(1005, label.dxf.handle)])
    xdata(label, "LD_SYMB2_LABEL", [(1005, insert.dxf.handle)])
    doc.modelspace().add_line((0.5, 0), (9.5, 0), dxfattribs={"layer": "CONNECT"})
    data = extract_superworks_semantics(doc, sheet_id="S1", file_id="F1")
    assert [p.endpoint_identity for p in data.ports] == ["1n705"]
    assert not any(s.insert_handle == insert.dxf.handle for s in data.symbols)
    assert len(data.unregistered_symb2) == 1
    record = data.unregistered_symb2[0]
    assert record["label_value"] == "1n"
    assert record["termpoints"][0]["a"] == pytest.approx((9.5, 0.0))
    assert record["termpoints"][0]["b"] == pytest.approx((10.5, 0.0))
    device_links = _device_internal_links(SimpleNamespace(line_groups=[], lines=[]), data)
    assert [link["source"] for link in device_links["links"]] == ["unregistered_symb2_pin"]
    page = SheetRecord("S1", "F1", "01 x.dwg", 1, "01", "x", "二次原理图", "primary", "filename", True,
                       audit_disposition="audit")
    full = SimpleNamespace(superworks=data, superworks_supersession=[], lines=[], line_groups=[],
                           scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"), pages=[page]), pairs=[])
    write_superworks_artifacts(full, tmp_path)
    summary = json.loads((tmp_path / "superworks_summary.json").read_text(encoding="utf-8"))
    assert summary["port_coverage"]["consumed"] == 0
    assert summary["coverage_views"]["total"]["consumed"] == 1
    assert summary["device_internal"]["link_count_by_source"] == {"unregistered_symb2_pin": 1}
    assert summary["device_internal"]["unregistered_symb2"]["blocks"] == 1
    decisions = pd.read_parquet(tmp_path / "sw_unregistered_pin_decisions.parquet")
    assert decisions.reason.tolist() == ["candidate"]


# GAP2-S: terminal-body split. A device terminal's two contacts sit on the two sides of its body (gap 2.5); the
# line group that merges the two sides is cut there, so the terminal links to its own unlabelled internal pin.

from dwg_audit.audit.superworks_device_internal import split_terminal_wires  # noqa: E402


def _split_port(record_id, identity, contact, *, mid_x, insert="I1", category="装置端子", file_id="F1",
                wire_handle=None, element_label="1n"):
    x, y = contact
    wire_handle = wire_handle or ("W1" if x < 1.25 else "W2")
    port = {
        "record_id": record_id, "file_id": file_id, "sheet_id": "S1", "insert_handle": insert, "port_number": "1",
        "category": category, "endpoint_identity": identity, "label": _label(element_label if category != "装置端子" else "1n"),
        "wire_contacts": [{"wire_handle": wire_handle, "wire_side": 0, "x": x, "y": y}],
        "start_x": mid_x, "start_y": -0.5, "end_x": mid_x, "end_y": 0.5,
    }
    return port


def _split_lines(contact2_x=2.5):
    return [
        {"file_id": "F1", "line_id": "L1", "handle": "W1", "source_block_name": "", "sx": -10.0, "sy": 0.0, "ex": 0.0, "ey": 0.0},
        {"file_id": "F1", "line_id": "L2", "handle": "W2", "source_block_name": "", "sx": contact2_x, "sy": 0.0, "ex": 12.0, "ey": 0.0},
    ]


def _merged_group(members=("L1", "L2")):
    return {"file_id": "F1", "line_group_id": "G", "member_line_ids": list(members)}


def _split_case(*, element_identity=None, body_mid=2.5, device2_identity="1n705", device2_insert="I1", extra_lines=(),
                groups=None, dots=(), contact2_x=2.5):
    device1 = _split_port("D1", "1n705", (0.0, 0.0), mid_x=0.0)
    device2 = _split_port("D2", device2_identity, (contact2_x, 0.0), mid_x=body_mid, insert=device2_insert)
    element = _split_port("Q1", element_identity, (-10.0, 0.0), mid_x=-10.0, category="内部元件", element_label="1n")
    ports = [device1, device2, element]
    lines = _split_lines(contact2_x) + list(extra_lines)
    line_groups = groups if groups is not None else [_merged_group()]
    split = {"lines": lines, "line_groups": line_groups, "connect_dots": list(dots)}
    return ports, split


def test_body_gap_cuts_the_merged_wire_and_links_the_terminal_to_its_own_pin():
    ports, split = _split_case()
    unsplit = build_device_internal_links(ports, [], wire_group_of=wire_keys_from_lines(split["lines"], split["line_groups"]))
    assert unsplit["links"] == []
    assert unsplit["stats"]["excluded:wire_multi_end"] == 2  # both device terminals sit on the merged wire
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert [l["port_id"] for l in result["links"]] == ["D1"]
    link = result["links"][0]
    assert link["element_port_id"] == "Q1"
    assert link["split_reason"] == "terminal_body"
    assert link["split_partner_port_ids"] == ["D2"]
    assert result["terminal_splits"][0]["split_reason"] == "terminal_body"
    assert result["terminal_splits"][0]["gap"] == pytest.approx(2.5)
    assert result["stats"]["split_accepted"] == 1
    assert result["stats"]["linked_on_split_wire"] == 1


def test_identified_element_on_a_split_wire_is_not_linked_and_is_counted():
    ports, split = _split_case(element_identity="1n3")
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert result["links"] == []
    assert result["stats"]["excluded:element_identified"] == 1


def test_identified_element_on_an_unsplit_wire_is_not_linked_either():
    ports = [_device(), _port("Q1", "内部元件", identity="1n3", label="1n", contacts=("W1",))]
    result = build_device_internal_links(ports, [], terminal_split=None)
    assert result["links"] == []
    assert result["stats"]["excluded:element_identified"] == 1


def test_a_body_narrower_than_two_units_is_not_cut():
    ports, split = _split_case(body_mid=1.25, contact2_x=1.25)
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert result["links"] == []
    assert result["stats"]["split_refused:body_too_narrow"] == 1


def test_a_body_of_two_units_is_cut():
    ports, split = _split_case(body_mid=2.0, contact2_x=2.0)
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert [l["port_id"] for l in result["links"]] == ["D1"]
    assert result["links"][0]["split_reason"] == "terminal_body"


def test_connection_dot_in_the_gap_keeps_the_wire_merged():
    ports, split = _split_case(dots=[{"file_id": "F1", "x": 1.25, "y": 0.0}])
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert result["links"] == []
    assert result["stats"]["split_refused:dot_in_gap"] == 1


def test_gap_must_equal_the_insert_body_width():
    ports, split = _split_case(body_mid=4.0)
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert result["links"] == []
    assert result["stats"]["split_refused:width_mismatch"] == 1


def test_a_different_identity_or_insert_is_not_a_body_pair():
    ports, split = _split_case(device2_identity="1n706")
    assert build_device_internal_links(ports, [], terminal_split=split)["stats"].get("split_examined", 0) == 0
    ports, split = _split_case(device2_insert="I2")
    assert build_device_internal_links(ports, [], terminal_split=split)["stats"].get("split_examined", 0) == 0


def test_a_line_crossing_the_gap_refuses_the_cut():
    crossing = {"file_id": "F1", "line_id": "L9", "handle": "W9", "source_block_name": "",
                "sx": 1.25, "sy": -5.0, "ex": 1.25, "ey": 5.0}
    ports, split = _split_case(extra_lines=[crossing])
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert result["links"] == []
    assert result["stats"]["split_refused:gap_crossed"] == 1


def test_a_group_of_three_pieces_is_not_cut():
    loose = {"file_id": "F1", "line_id": "L7", "handle": "W7", "source_block_name": "",
             "sx": 20.0, "sy": 0.0, "ex": 30.0, "ey": 0.0}
    ports, split = _split_case(extra_lines=[loose], groups=[_merged_group(("L1", "L2", "L7"))])
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert result["links"] == []
    assert result["stats"]["split_refused:components_not_two"] == 1


def test_a_second_group_that_still_joins_both_sides_refuses_the_cut():
    loose = {"file_id": "F1", "line_id": "L7", "handle": "W7", "source_block_name": "",
             "sx": 20.0, "sy": 0.0, "ex": 30.0, "ey": 0.0}
    other = {"file_id": "F1", "line_group_id": "H", "member_line_ids": ["L1", "L2", "L7"]}
    ports, split = _split_case(extra_lines=[loose], groups=[_merged_group(), other])
    result = build_device_internal_links(ports, [], terminal_split=split)
    assert result["links"] == []
    assert result["stats"]["split_refused:still_merged"] == 1


def test_without_a_cut_the_split_mapping_is_the_line_group_mapping():
    ports, split = _split_case(device2_identity="1n706")
    mapping = split_terminal_wires(ports, split["lines"], split["line_groups"], split["connect_dots"])["mapping"]
    assert mapping == wire_keys_from_lines(split["lines"], split["line_groups"])


def test_split_reads_ports_and_lines_only_and_is_stable():
    ports, split = _split_case()
    before = json.dumps([ports, split], sort_keys=True, default=str)
    first = build_device_internal_links(ports, [], terminal_split=split)
    second = build_device_internal_links(ports, [], terminal_split=split)
    assert json.dumps([ports, split], sort_keys=True, default=str) == before
    assert [l["link_id"] for l in first["links"]] == [l["link_id"] for l in second["links"]]
