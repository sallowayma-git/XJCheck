"""Cross-page continuity of terminal-strip rows (X2): links count as coverage, never as pairs, and a
disagreeing target is reported as a candidate. Page numbers decide the target; a handle that exists only on
another drawing is a stale reference."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pandas as pd

from dwg_audit.audit.superworks_cross_page import (
    CANDIDATE_CONSUMED,
    CANDIDATE_FREE,
    RELATION_CONN,
    RELATION_ROW,
    build_cross_page_links,
    page_number,
)
from dwg_audit.domain.models import SheetRecord, SwPort, SwStripRow
from dwg_audit.extract.superworks_semantics import SuperworksData
from dwg_audit.report.superworks_artifacts import write_superworks_artifacts

PAGES = [{"file_id": "F1", "sheet_no": "01"}, {"file_id": "F2", "sheet_no": "2"}, {"file_id": "F3", "sheet_no": "3"}]


def _row(identity="7UD1", connections=None, refs=None, file_id="F1", record_id="R1"):
    return {"record_id": record_id, "sheet_id": "S1", "file_id": file_id, "endpoint_identity": identity,
            "connections": connections if connections is not None else [{"text_id": "T1", "value": "1n705"}],
            "cross_page_refs": refs if refs is not None else [{"handle": "H9", "port_number": "1", "page_name": "02 x"}]}


def _port(record_id="P9", identity="1n705", category="装置端子", file_id="F2", wire=True, handle="H9", number="1"):
    return {"record_id": record_id, "file_id": file_id, "sheet_id": "S2", "insert_handle": handle, "port_number": number,
            "endpoint_identity": identity, "category": category, "has_wire_contact": wire}


def _pair(pair_id="PAIR1", left="7UD1", right="1n705", right_text="T1", left_text=None, status="pass",
          left_ports=(), right_ports=(), sheet="S1"):
    return {"pair_id": pair_id, "status": status, "sheet_id": sheet, "left_value": left, "right_value": right,
            "left_text_id": left_text, "right_text_id": right_text,
            "left_port_ids": list(left_ports), "right_port_ids": list(right_ports)}


def test_page_number_is_the_leading_digits_of_the_destination_text():
    assert page_number("13 非电量信号输出回路3") == "13"
    assert page_number("06 交直流回路") == "6"
    assert page_number("交直流回路") is None


def test_connection_named_far_identity_covers_the_free_target():
    result = build_cross_page_links([_row()], [_port()], [_pair()], PAGES)
    assert len(result["links"]) == 1
    link = result["links"][0]
    assert link["relation"] == RELATION_CONN and link["covers_target"] is True
    assert result["covered"] == {"P9": [link["link_id"]]}
    assert result["candidates"] == []


def test_same_terminal_name_on_the_target_page_is_a_row_continuity():
    row = _row(identity="7UD10", connections=[{"text_id": "T1", "value": "1zkk-1"}])
    result = build_cross_page_links([row], [_port(identity="7UD10", category="端子")],
                                    [_pair(left="7UD10", right="1zkk-1")], PAGES)
    assert result["links"][0]["relation"] == RELATION_ROW
    assert result["links"][0]["covers_target"] is True


def test_target_already_consumed_by_an_agreeing_pair_adds_no_coverage():
    other = _pair(pair_id="PAIR2", left="1n705", right="7UD1", left_ports=["P9"], sheet="S2")
    result = build_cross_page_links([_row()], [_port()], [_pair(), other], PAGES)
    assert result["links"][0]["covers_target"] is False
    assert result["covered"] == {}
    assert result["candidates"] == []


def test_consumed_target_whose_other_end_is_unrelated_is_a_contradiction_candidate():
    other = _pair(pair_id="PAIR2", left="1n888", right="1n999", left_ports=["P9"], sheet="S2")
    result = build_cross_page_links([_row()], [_port(identity="1n888")], [_pair(), other], PAGES)
    assert [c["candidate"] for c in result["candidates"]] == [CANDIDATE_CONSUMED]
    candidate = result["candidates"][0]
    assert candidate["consumer_other_values"] == ["1n999"] and candidate["consumer_pair_ids"] == ["PAIR2"]
    assert result["links"] == []


def test_free_target_with_a_different_identity_is_reported_not_covered():
    result = build_cross_page_links([_row()], [_port(identity="1n888")], [_pair()], PAGES)
    assert [c["candidate"] for c in result["candidates"]] == [CANDIDATE_FREE]
    assert result["covered"] == {}


def test_handle_that_exists_only_on_another_drawing_is_a_stale_reference():
    refs = [{"handle": "H9", "port_number": "1", "page_name": "03 other"}]
    result = build_cross_page_links([_row(refs=refs)], [_port()], [_pair()], PAGES)
    assert result["links"] == [] and result["candidates"] == []
    assert result["stats"]["handle_on_other_page"] == 1


def test_missing_page_or_absent_handle_is_counted_and_not_linked():
    refs = [{"handle": "NOPE", "port_number": "1", "page_name": "02 x"},
            {"handle": "H9", "port_number": "1", "page_name": "99 missing"}]
    result = build_cross_page_links([_row(refs=refs)], [_port()], [_pair()], PAGES)
    assert result["links"] == []
    assert result["stats"]["target_absent"] == 1 and result["stats"]["page_not_in_project"] == 1


def test_reference_to_the_same_page_is_not_cross_page():
    refs = [{"handle": "H9", "port_number": "1", "page_name": "01 x"}]
    result = build_cross_page_links([_row(refs=refs)], [_port(file_id="F1")], [_pair()], PAGES)
    assert result["links"] == [] and result["stats"]["same_page"] == 1


def test_discard_pair_does_not_support_the_row():
    result = build_cross_page_links([_row()], [_port()], [_pair(status="discard")], PAGES)
    assert result["links"] == [] and result["stats"]["row_has_no_strip_pair"] == 1


def test_target_without_wire_contact_is_linked_but_not_covered():
    result = build_cross_page_links([_row()], [_port(wire=False)], [_pair()], PAGES)
    assert result["links"][0]["covers_target"] is False and result["covered"] == {}


def test_non_terminal_target_is_skipped():
    result = build_cross_page_links([_row()], [_port(category="内部元件")], [_pair()], PAGES)
    assert result["links"] == [] and result["stats"]["target_not_terminal"] == 1


def test_two_rows_claiming_one_target_are_not_coverage():
    rows = [_row(record_id="R1"), _row(record_id="R2", identity="7UD2",
                                       connections=[{"text_id": "T2", "value": "1n705"}])]
    pairs = [_pair(), _pair(pair_id="PAIR3", left="7UD2", right="1n705", right_text="T2")]
    result = build_cross_page_links(rows, [_port()], pairs, PAGES)
    assert result["covered"] == {}
    assert result["stats"]["multi_claim_not_covered"] == 1
    assert all(link["covers_target"] is False for link in result["links"])


def test_inputs_are_not_modified():
    row, port, pair = _row(), _port(), _pair()
    before = copy.deepcopy((row, port, pair))
    build_cross_page_links([row], [port], [pair], PAGES)
    assert (row, port, pair) == before


def _page(sheet_id, file_id, number):
    return SheetRecord(sheet_id, file_id, f"{number} x.dwg", int(number), number, "x", "二次原理图", "primary",
                       "filename", True, audit_disposition="audit")


def test_artifacts_add_continuity_coverage_without_changing_pairs(tmp_path):
    strip = SwStripRow(record_id="R1", sheet_id="S1", file_id="F1", row_handle="H1", endpoint_identity="7UD1",
                       connections=[{"text_id": "T1", "value": "1n705", "side": "right"}],
                       cross_page_refs=[{"handle": "H9", "port_number": "1", "page_name": "02 x"}])
    target = SwPort(record_id="P9", sheet_id="S2", file_id="F2", insert_handle="H9", port_number="1",
                    category="装置端子", endpoint_identity="1n705", wire_contacts=[{"wire_handle": "W"}],
                    label={"resolved": True})
    pair = SimpleNamespace(pair_id="PAIR1", status="pass", sheet_id="S1", left_value="7UD1", right_value="1n705",
                           left_text_id=None, right_text_id="T1", pair_kind="table_mapping", evidence={})
    data = SuperworksData(strip_rows=[strip], ports=[target])
    artifacts = SimpleNamespace(superworks=data, superworks_supersession=[],
                                scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"),
                                                     pages=[_page("S1", "F1", "1"), _page("S2", "F2", "2")]),
                                pairs=[pair])
    write_superworks_artifacts(artifacts, tmp_path)
    summary = json.loads((tmp_path / "superworks_summary.json").read_text(encoding="utf-8"))
    assert summary["port_coverage"]["consumed"] == 0
    assert summary["port_coverage_with_continuity"]["consumed"] == 1
    assert summary["port_coverage_with_continuity"]["added_by_continuity"] == 1
    assert summary["cross_page"]["link_count"] == 1
    links = pd.read_parquet(tmp_path / "sw_cross_page_links.parquet")
    assert len(links) == 1 and bool(links.covers_target.iloc[0])
    coverage = pd.read_parquet(tmp_path / "sw_port_coverage.parquet")
    row = coverage.set_index("port_id").loc["P9"]
    assert json.loads(row.continuity_link_ids) == [links.link_id.iloc[0]]
    assert bool(row.consumed_with_continuity) and not bool(row.consumed)
    assert pair.status == "pass" and pair.evidence == {}


# XPAGE-2: equivalence of strip rows (short bridges, range terminals, one-hop wires, shared target nodes).
from dwg_audit.audit.superworks_cross_page import (  # noqa: E402
    RELATION_GROUP,
    short_bridge_pairs,
)


def _bridge_rows():
    return [{"record_id": "A", "file_id": "F1", "group": "H", "x": 60.0, "y": 123.5},
            {"record_id": "B", "file_id": "F1", "group": "H", "x": 60.0, "y": 118.5}]


def _bridge_lines(upper_mid_only=False):
    lines = [{"file_id": "F1", "x0": 66.0, "y0": 124.25, "x1": 66.0, "y1": 122.5},
             {"file_id": "F1", "x0": 66.0, "y0": 122.5, "x1": 66.0, "y1": 120.75}]
    return lines[:1] if upper_mid_only else lines


def test_short_bridge_joins_consecutive_rows_when_both_halves_are_drawn():
    assert short_bridge_pairs(_bridge_rows(), _bridge_lines()) == [("A", "B")]


def test_one_bridge_half_is_not_a_short_bridge():
    assert short_bridge_pairs(_bridge_rows(), _bridge_lines(upper_mid_only=True)) == []


def test_target_identity_held_by_a_bridged_row_is_an_equivalence_not_a_candidate():
    rows = [_row(record_id="R1", identity="7UD17", connections=[{"text_id": "T1", "value": "1n709"}]),
            _row(record_id="R2", identity="7UD18", connections=[{"text_id": "T2", "value": "1n710"}], refs=[])]
    pairs = [_pair(pair_id="PAIR1", left="7UD17", right="1n709", right_text="T1"),
             _pair(pair_id="PAIR2", left="7UD18", right="1n710", right_text="T2")]
    result = build_cross_page_links(rows, [_port(identity="1n710")], pairs, PAGES, bridges=[("R1", "R2")])
    link = result["links"][0]
    assert link["relation"] == RELATION_GROUP and link["equivalence"] == "target_in_group_far"
    assert link["covers_target"] is False and result["candidates"] == [] and result["covered"] == {}


def test_range_terminal_names_each_member_so_a_member_target_is_equivalent():
    row = _row(identity="U3D7~8", connections=[{"text_id": "T1", "value": "1n705"}])
    result = build_cross_page_links([row], [_port(identity="U3D8")], [_pair(left="U3D7~8")], PAGES)
    assert result["links"][0]["relation"] == RELATION_GROUP
    assert result["links"][0]["equivalence"] == "target_in_group"
    assert result["candidates"] == []


def test_one_hop_wire_between_two_rows_explains_the_other_end_of_the_target():
    rows = [_row(record_id="R1", identity="7UD18", connections=[{"text_id": "T1", "value": "1ud4"}]),
            _row(record_id="R2", identity="1UD4", connections=[{"text_id": "T2", "value": "7UD18"},
                                                              {"text_id": "T3", "value": "1n1522"}], refs=[])]
    pairs = [_pair(pair_id="PAIR1", left="7UD18", right="1ud4", right_text="T1"),
             _pair(pair_id="PAIR2", left="1n888", right="1n1522", left_ports=["P9"], sheet="S2")]
    result = build_cross_page_links(rows, [_port(identity="1n888")], pairs, PAGES)
    link = result["links"][0]
    assert link["relation"] == RELATION_GROUP and link["equivalence"] == "other_in_hop"
    assert result["candidates"] == []


def test_claimed_consumed_target_is_a_shared_node_not_a_candidate():
    rows = [_row(record_id="R1", identity="7UD1", connections=[{"text_id": "T1", "value": "1n705"}]),
            _row(record_id="R2", identity="7UD2", connections=[{"text_id": "T2", "value": "1n706"}])]
    pairs = [_pair(pair_id="PAIR1", left="7UD1", right="1n705", right_text="T1"),
             _pair(pair_id="PAIR3", left="7UD2", right="1n706", right_text="T2"),
             _pair(pair_id="PAIR2", left="1n888", right="1n999", left_ports=["P9"], sheet="S2")]
    result = build_cross_page_links(rows, [_port(identity="1n888")], pairs, PAGES)
    assert result["candidates"] == []
    assert {link["equivalence"] for link in result["links"]} == {"shared_target_node"}


def test_consumed_target_with_an_empty_other_end_has_no_evidence_to_compare():
    other = _pair(pair_id="PAIR2", left="1n888", right="", left_ports=["P9"], sheet="S2")
    result = build_cross_page_links([_row()], [_port(identity="1n888")], [_pair(), other], PAGES)
    assert result["candidates"] == []
    assert result["stats"]["consumer_other_empty"] == 1
