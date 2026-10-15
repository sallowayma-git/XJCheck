"""GAP-COORD: the R-RECOGNITION-GAP gate, the terminal presentation and the audit rows.

Each gate step is tested on its own shape and on the shape it must not close. Inputs are plain observation rows and
Pair objects, as the report stage reads them from the parquet artifacts.
"""
from __future__ import annotations

from types import SimpleNamespace

from dwg_audit.audit.recognition_coordinator import (
    GapFacts,
    build_resolution_issues,
    resolve_recognition_gaps,
)
from dwg_audit.audit.superworks_device_internal import (
    device_internal_wire_index,
    on_device_internal_wire,
    wire_members_of_links,
)
from dwg_audit.domain.models import Pair
from dwg_audit.report.superworks_artifacts import _observation_end_geometry

DEV = "装置端子"
TERM = "端子"
INT = "内部元件"
COIL = "线圈"


def side(category=None, value=None, port_ids=(), **extra):
    return {"category": category, "value": value, "port_ids": list(port_ids), "wire_touched": bool(port_ids),
            "ports": [], "candidate_values": [value] if value else [], **extra}


def observation(record_id, left=None, right=None, *, coords=(0.0, 0.0, 10.0, 0.0), handles=("H1",),
                state="INCOMPLETE", reason_codes=(), end_geometry=None, sheet="S1", file="F1", line_group="G1"):
    return {"record_id": record_id, "object_key": record_id, "file_id": file, "sheet_id": sheet,
            "line_group_id": line_group, "state": state, "reason_codes": list(reason_codes),
            "source_handles": list(handles), "left": left or side(), "right": right or side(),
            "coords": list(coords), "connect_label_id": None, "end_geometry": end_geometry}


def pair(pair_id, left, right, *, status="pass", line_group="G1", sheet="S1", file="F1", evidence=None):
    item = Pair(pair_id, line_group, sheet, file, None, left, right, 0.99, status, "test")
    item.evidence = {"discard_reason": None, **(evidence or {})}
    if status == "discard" and evidence is None:
        item.evidence["discard_reason"] = "device_internal"
    return item


def gate_only(observations, pairs=(), facts=None, steps=None):
    kwargs = {} if steps is None else {"steps": steps}
    return resolve_recognition_gaps(observations, list(pairs), [], (), facts=facts, **kwargs)


def test_device_internal_line_link_closes_the_gap_only_on_its_own_wire():
    facts = GapFacts(internal_wires={("F1", "PD"): frozenset({"H1", "H2"})})
    on_wire = observation("on", left=side(DEV, "1n712", ["PD"]), right=side(INT, None, ["PE"]), handles=["H1"])
    off_wire = observation("off", left=side(DEV, "1n712", ["PD"]), right=side(INT, None, ["PE"]), handles=["H9"])
    result = gate_only([on_wire, off_wire], facts=facts)
    assert [row["record_id"] for row in result.suppressed] == ["on"]
    assert result.suppressed[0]["suppressed_by"] == "device_internal"
    assert len(result.issues) == 1
    assert gate_only([on_wire], facts=facts, steps=("continuity",)).issues


def test_device_internal_step_requires_every_terminal_side_to_be_covered():
    facts = GapFacts(internal_wires={("F1", "PD"): frozenset({"H1"})})
    other_terminal = observation("two", left=side(DEV, "1n712", ["PD"]), right=side(TERM, "1n713", ["PT"]), handles=["H1"])
    assert gate_only([other_terminal], facts=facts).issues
    assert gate_only([other_terminal], facts=facts, steps=("device_internal",)).suppressed == []


def test_continuity_closes_when_each_terminal_side_is_covered_by_a_continuity_link():
    facts = GapFacts(continuity_ports=frozenset({"PT1"}))
    covered = observation("cov", left=side(TERM, "1I3D3", ["PT1"]), right=side(COIL, None, ["PC"]))
    open_terminal = observation("open", left=side(TERM, "1I3D3", ["PT1"]), right=side(TERM, "1I3D4", ["PT2"]))
    result = gate_only([covered, open_terminal], facts=facts)
    assert [row["suppressed_by"] for row in result.suppressed] == ["continuity"]
    assert [row["record_id"] for row in result.suppressed] == ["cov"]


def test_physical_v1_closes_only_on_the_same_segment_with_agreeing_identity():
    facts = GapFacts(line_geometry={("F1", "S1", "G9"): ((0.0, 0.0), (20.0, 0.0))})
    good = pair("PG", "1n712", "X", line_group="G9", status="pass")
    terminal = side(DEV, "1n712", ["PD"])
    closed = observation("ok", left=terminal, right=side(INT, None, ["PE"]), coords=(0.0, 0.0, 10.0, 0.0), line_group="G9")
    result = gate_only([closed], pairs=[good], facts=facts)
    assert result.suppressed[0]["suppressed_by"] == "physical_v1"
    assert result.suppressed[0]["pair_id"] == "PG"

    mismatch = observation("bad", left=side(DEV, "1n999", ["PD"]), right=side(INT, None, ["PE"]), coords=(0.0, 0.0, 10.0, 0.0), line_group="G9")
    assert gate_only([mismatch], pairs=[good], facts=facts).issues

    off_line = observation("off", left=terminal, right=side(INT, None, ["PE"]), coords=(0.0, 5.0, 10.0, 5.0), line_group="G9")
    assert gate_only([off_line], pairs=[good], facts=facts).issues

    partial = observation("part", left=terminal, right=side(INT, None, ["PE"]), coords=(-12.0, 0.0, 8.0, 0.0), line_group="G9")
    assert gate_only([partial], pairs=[good], facts=facts).issues

    discarded = pair("PD", "1n712", "X", line_group="G9", status="discard", evidence={"discard_reason": "ordinary"})
    assert gate_only([closed], pairs=[discarded], facts=facts).issues


def test_physical_v1_treats_the_shared_ground_name_as_one_identity():
    facts = GapFacts(line_geometry={("F1", "S1", "G9"): ((0.0, 0.0), (20.0, 0.0))})
    ground_pair = pair("PGND", "GND", "1n5", line_group="G9")
    gnd_side = observation("gnd", left=side("接地", "GND", ["PG"]), right=side(DEV, "1n5", ["PD"]),
                           coords=(0.0, 0.0, 10.0, 0.0), line_group="G9")
    assert gate_only([gnd_side], pairs=[ground_pair], facts=facts).suppressed[0]["pair_id"] == "PGND"


def test_x_element_wire_needs_no_terminal_no_termpoint_and_no_rail():
    clean = [{"unreg_pin": False, "rail_t": False}, {"unreg_pin": False, "rail_t": False}]
    element_only = observation("x", left=side(INT, None, ["PA"]), right=side(COIL, None, ["PB"]), end_geometry=clean)
    assert gate_only([element_only]).suppressed[0]["suppressed_by"] == "x_element_only"

    rail = [{"unreg_pin": False, "rail_t": True}, {"unreg_pin": False, "rail_t": False}]
    assert gate_only([observation("rail", left=side(INT, None, ["PA"]), right=side(COIL, None, ["PB"]), end_geometry=rail)]).issues
    termpoint = [{"unreg_pin": True, "rail_t": False}, {"unreg_pin": False, "rail_t": False}]
    assert gate_only([observation("tp", left=side(INT, None, ["PA"]), right=side(COIL, None, ["PB"]), end_geometry=termpoint)]).issues
    terminal = observation("term", left=side(TERM, "1n7", ["PT"]), right=side(INT, None, ["PA"]), end_geometry=clean)
    assert gate_only([terminal]).issues
    unknown = observation("none", left=side(INT, None, ["PA"]), right=side(COIL, None, ["PB"]), end_geometry=None)
    assert gate_only([unknown]).issues


def test_self_loop_suppresses_only_two_contacts_of_one_identity():
    same = observation("same", left=side(DEV, "1n712", ["PA"]), right=side(TERM, "1n712", ["PB"]))
    assert gate_only([same]).suppressed[0]["suppressed_by"] == "self_loop"
    different = observation("diff", left=side(DEV, "1n712", ["PA"]), right=side(TERM, "1n713", ["PB"]))
    assert gate_only([different]).issues


def test_confirmed_conflict_is_never_suppressed_by_the_gate():
    facts = GapFacts(continuity_ports=frozenset({"PT1"}))
    conflict = observation("conflict", left=side(TERM, "1n7", ["PT1"]), right=side(INT, None, ["PA"]),
                           state="CONFIRMED_CONFLICT", reason_codes=["dangling_pin_handle"])
    result = gate_only([conflict], facts=facts)
    assert result.suppressed == []
    assert [issue.rule_id for issue in result.issues] == ["R-SUPERWORKS-CONFLICT"]


def test_unpinned_element_pins_at_terminals_are_one_page_summary():
    first = observation("u1", left=side(TERM, "1QD5", ["PT1"]), right=side(INT, None, ["PA"]), handles=["H1"])
    second = observation("u2", left=side(TERM, "1QD8", ["PT2"]), right=side(COIL, None, ["PB"]), handles=["H2"])
    issues = build_resolution_issues([first, second], [], [])
    assert len(issues) == 1
    evidence = issues[0].evidence
    assert issues[0].rule_id == "R-RECOGNITION-GAP"
    assert evidence["presentation"] == "page_summary"
    assert evidence["terminal_count"] == 2
    assert {row["port_id"] for row in evidence["terminal_ports"]} == {"PT1", "PT2"}
    assert evidence["review_group_label"].endswith("无脚号元件连接（2 个端子）")


def test_a_terminal_with_another_gap_keeps_its_unpinned_observation_in_the_terminal_issue():
    unpinned = observation("u", left=side(TERM, "1QD5", ["PT1"]), right=side(INT, None, ["PA"]), handles=["H1"])
    other = observation("o", left=side(TERM, "1QD5", ["PT1"]), right=side(TERM, "1QD6", ["PT2"]), handles=["H2"])
    issues = build_resolution_issues([unpinned, other], [], [])
    assert len(issues) == 1
    assert issues[0].evidence["presentation"] == "terminal"
    assert issues[0].evidence["terminal_port_ids"] == ["PT1", "PT2"]
    assert {row["record_id"] for row in issues[0].evidence["resolution_observations"]} == {"u", "o"}


def test_shared_terminals_give_one_issue_per_terminal():
    first = observation("a", left=side(TERM, "1n1", ["PT1"]), right=side(TERM, "1n2", ["PT2"]), handles=["H1"])
    second = observation("b", left=side(TERM, "1n2", ["PT2"]), right=side(TERM, "1n3", ["PT3"]), handles=["H2"])
    third = observation("c", left=side(TERM, "1n9", ["PT9"]), right=side(TERM, "1n8", ["PT8"]), handles=["H3"])
    issues = build_resolution_issues([first, second, third], [], [])
    ports = [port for issue in issues for port in issue.evidence["terminal_port_ids"]]
    assert sorted(ports) == ["PT1", "PT2", "PT3", "PT8", "PT9"]
    assert len(issues) == 2


def test_suppressed_rows_record_the_step_and_the_closing_pair():
    facts = GapFacts(line_geometry={("F1", "S1", "G9"): ((0.0, 0.0), (20.0, 0.0))})
    closed = observation("ok", left=side(DEV, "1n712", ["PD"]), right=side(INT, None, ["PE"]), line_group="G9")
    row = gate_only([closed], pairs=[pair("PG", "1n712", "X", line_group="G9")], facts=facts).suppressed[0]
    assert row["suppressed_by"] == "physical_v1"
    assert row["pair_id"] == "PG"
    assert row["terminal_port_ids"] == ["PD"]


def _line(handle, start, end, *, block=None):
    return SimpleNamespace(file_id="F1", sheet_id="S1", handle=handle, source_block_name=block,
                           start_x=start[0], start_y=start[1], end_x=end[0], end_y=end[1])


def test_end_geometry_flags_rails_split_into_pieces_and_termpoints():
    lines = [
        _line("C1", (10.0, 0.0), (10.0, 30.0)),
        _line("C2", (10.0, 30.0), (10.0, 60.0)),
        _line("S1", (40.0, 0.0), (40.0, 20.0)),
        _line("B1", (70.0, 0.0), (70.0, 99.0), block="BLOCK"),
        _line("OWN", (20.0, 0.0), (20.0, 60.0)),
        _line("H1", (0.0, 100.0), (60.0, 100.0)),
    ]
    rows = [
        {"record_id": "chain", "state": "INCOMPLETE", "file_id": "F1", "sheet_id": "S1", "source_handles": ["W"],
         "coords": [3.0, 40.0, 10.0, 40.0]},
        {"record_id": "short", "state": "INCOMPLETE", "file_id": "F1", "sheet_id": "S1", "source_handles": ["W"],
         "coords": [3.0, 10.0, 40.0, 10.0]},
        {"record_id": "block", "state": "INCOMPLETE", "file_id": "F1", "sheet_id": "S1", "source_handles": ["W"],
         "coords": [60.0, 50.0, 70.0, 50.0]},
        {"record_id": "pin", "state": "INCOMPLETE", "file_id": "F1", "sheet_id": "S1", "source_handles": ["W"],
         "coords": [0.0, 0.0, 5.0, 0.0]},
        {"record_id": "own", "state": "INCOMPLETE", "file_id": "F1", "sheet_id": "S1", "source_handles": ["OWN"],
         "coords": [20.0, 10.0, 20.0, 12.0]},
        {"record_id": "horizontal_rail", "state": "INCOMPLETE", "file_id": "F1", "sheet_id": "S1", "source_handles": ["W"],
         "coords": [5.0, 90.0, 5.0, 100.0]},
    ]
    data = SimpleNamespace(resolution_observations=rows, unregistered_symb2=[
        {"file_id": "F1", "sheet_id": "S1", "termpoints": [{"number": "1", "a": [0.5, 0.0], "b": [9.0, 9.0]}]}])
    geometry = _observation_end_geometry(SimpleNamespace(lines=lines), data)
    assert geometry["chain"][1]["rail_t"] is True
    assert geometry["short"][1]["rail_t"] is False and geometry["short"][0]["rail_t"] is False
    assert geometry["block"][0]["rail_t"] is False
    assert geometry["pin"][0]["unreg_pin"] is True
    # The wire under test is not evidence for a rail, but a rail that overlaps it still counts (C1/C2 at x=10 only).
    assert geometry["own"][0]["rail_t"] is False
    assert geometry["horizontal_rail"][1]["rail_t"] is True


def test_device_internal_wire_members_and_index_read_the_link_wire():
    mapping = {("F1", "11"): ("F1", "W:1"), ("F1", "12"): ("F1", "W:1")}
    links = [{"link_id": "L1", "file_id": "F1", "port_id": "PD", "wire_handle": "11"}]
    members = wire_members_of_links(links, mapping)
    assert members["L1"] == ["11", "12"]
    index = device_internal_wire_index([{**links[0], "wire_handles": members["L1"]}])
    assert on_device_internal_wire(index, "F1", "PD", ["12"])
    assert not on_device_internal_wire(index, "F1", "PD", ["99"])
    assert not on_device_internal_wire(index, "F1", "PX", ["11"])
