"""Device-internal links of SuperWORKS device terminals (DEV-INT): rule, exclusions and wire grouping."""
from __future__ import annotations

import json

import pandas as pd

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
