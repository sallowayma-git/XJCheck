"""WIRE-BREAK round 24: wire walk and the walked device-internal discard of one-sided pairs (synthetic geometry)."""

from dwg_audit.audit.superworks_extractor import _discard_walked_half_pairs
from dwg_audit.audit.superworks_wire_walk import segment_index, walk_wire
from dwg_audit.domain.models import LineEntity, LineGroup, Pair, SwPort
from dwg_audit.extract.superworks_semantics import SuperworksData


def _seg(x1, y1, x2, y2):
    return (float(x1), float(y1), float(x2), float(y2))


def test_walk_follows_corners_and_t_junctions_but_not_gaps() -> None:
    # a horizontal wire, a corner up from its end, and a T junction on the vertical; a far segment across a gap
    segments = [_seg(0, 0, 10, 0), _seg(10, 0, 10, 8), _seg(10, 4, 14, 4), _seg(20, 0, 30, 0)]

    visited, ends, _ = walk_wire(segments, (0.0, 0.0))

    assert set(visited) == {_seg(0, 0, 10, 0), _seg(10, 0, 10, 8), _seg(10, 4, 14, 4)}
    assert (30.0, 0.0) not in ends


def test_walk_of_an_isolated_end_visits_nothing_but_the_segment_at_it() -> None:
    segments = [_seg(0, 0, 10, 0), _seg(20, 0, 30, 0)]

    visited, _, _ = walk_wire(segments, (0.0, 0.0))

    assert visited == [_seg(0, 0, 10, 0)]


def test_segment_index_excludes_block_internal_lines() -> None:
    def line(lid, x1, y1, x2, y2, block=None):
        return LineEntity(lid, "S1", "F1", lid, "LINE", "WIRE", x1, y1, x2, y2, 10.0, 0.0, x1, y1, x2, y2,
                          source_block_name=block)

    index = segment_index([line("A", 0, 0, 10, 0), line("B", 10, 0, 20, 0, block="BLK")])

    assert index["S1"] == [_seg(0, 0, 10, 0)]


def _line(lid, x1, y1, x2, y2):
    return LineEntity(lid, "S1", "F1", lid, "LINE", "WIRE", x1, y1, x2, y2, abs(x2 - x1) + abs(y2 - y1), 0.0,
                      min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _terminal(record, symbol, identity, label, x, y):
    return SwPort(record_id=record, sheet_id="S1", file_id="F1", symbol_id=symbol, insert_handle=symbol,
                  category="装置端子", endpoint_identity=identity, port_number="1",
                  start_x=x - 0.5, start_y=y, end_x=x + 0.5, end_y=y,
                  label={"normalized": label, "resolved": True})


def _half_pair(group_id, left_value, port_ids):
    return Pair(pair_id="PW1", line_group_id=group_id, sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                left_value=left_value, right_value=None, confidence=0.5, status="review", rationale="missing right",
                evidence={"superworks": {"left": {"value": left_value, "port_ids": port_ids, "category": "装置端子"}}},
                pair_kind="ordinary_pair")


def _data(ports, unregistered=()):
    data = SuperworksData()
    data.ports = list(ports)
    data.unregistered_symb2 = list(unregistered)
    data.topology_cut_group_ids = {"G1"}
    return data


def _group():
    return LineGroup(line_group_id="G1", sheet_id="S1", file_id="F1", start_x=10.0, start_y=20.0, end_x=40.0,
                     end_y=20.0, length=30.0, wire_candidate_score=1.0, member_line_ids=["L1"],
                     layer_hints=["WIRE"], orientation="horizontal")


def _block(label, resolved=True):
    return {"record_id": "USY:F1:S1:/B", "sheet_id": "S1", "file_id": "F1", "instance_path": "/B",
            "label_value": label, "label_resolved": resolved,
            "termpoints": [{"number": "1", "a": (38.5, 20.0), "b": (39.5, 20.0)},
                           {"number": "2", "a": (45.0, 20.0), "b": (46.0, 20.0)}]}


def test_half_pair_is_discarded_when_the_walk_reaches_only_the_same_devices_internal_pin() -> None:
    # terminal 2n612 at x=10 (contact); the wire runs 10 -> 40, and the open end at 40 reaches a 2n block pin.
    terminal = _terminal("T1", "SW:S1:/T", "2n612", "2n", 10.0, 20.0)
    data = _data([terminal], [_block("2n")])
    data.unregistered_symb2[0]["termpoints"] = [{"number": "1", "a": (39.5, 20.0), "b": (40.5, 20.0)}]
    lines = [_line("L1", 10.0, 20.0, 40.0, 20.0)]
    output = [_half_pair("G1", "2n612", ["SW:S1:/T:/T:D1:1"])]
    data.ports[0].record_id = "SW:S1:/T:/T:D1:1"

    stats = _discard_walked_half_pairs(output, data, lines, [_group()])

    assert stats == {"walk_discarded:review": 1}
    assert output[0].status == "discard"
    assert output[0].evidence["discard_reason"] == "device_internal"
    assert output[0].evidence["device_internal_discard"]["rule"] == "wire_walk_internal"


def test_half_pair_is_kept_when_the_reached_pin_has_another_label() -> None:
    terminal = _terminal("T1", "SW:S1:/T", "2n612", "2n", 10.0, 20.0)
    data = _data([terminal], [_block("1n")])
    data.unregistered_symb2[0]["termpoints"] = [{"number": "1", "a": (39.5, 20.0), "b": (40.5, 20.0)}]
    lines = [_line("L1", 10.0, 20.0, 40.0, 20.0)]
    output = [_half_pair("G1", "2n612", ["SW:S1:/T:/T:D1:1"])]
    data.ports[0].record_id = "SW:S1:/T:/T:D1:1"

    stats = _discard_walked_half_pairs(output, data, lines, [_group()])

    assert stats == {"walk_kept:other_label_differs": 1}
    assert output[0].status == "review"


def test_half_pair_is_kept_when_nothing_is_reached() -> None:
    terminal = _terminal("T1", "SW:S1:/T", "2n612", "2n", 10.0, 20.0)
    data = _data([terminal], [])
    lines = [_line("L1", 10.0, 20.0, 40.0, 20.0)]
    output = [_half_pair("G1", "2n612", ["SW:S1:/T:/T:D1:1"])]
    data.ports[0].record_id = "SW:S1:/T:/T:D1:1"

    stats = _discard_walked_half_pairs(output, data, lines, [_group()])

    assert stats == {"walk_kept:nothing_reached": 1}
    assert output[0].status == "review"


def test_pairs_outside_cut_groups_are_not_walked() -> None:
    terminal = _terminal("T1", "SW:S1:/T", "2n612", "2n", 10.0, 20.0)
    data = _data([terminal], [_block("2n")])
    data.topology_cut_group_ids = set()
    lines = [_line("L1", 10.0, 20.0, 40.0, 20.0)]
    output = [_half_pair("G1", "2n612", ["SW:S1:/T:/T:D1:1"])]

    stats = _discard_walked_half_pairs(output, data, lines, [_group()])

    assert stats == {}
    assert output[0].status == "review"


def _frame_lines():
    return [_seg(0, 0, 60, 0), _seg(60, 0, 60, 40), _seg(60, 40, 0, 40), _seg(0, 40, 0, 0)]


def test_rectangles_need_four_meeting_sides() -> None:
    from dwg_audit.audit.superworks_wire_walk import rectangles

    assert rectangles(_frame_lines()) == [(0.0, 0.0, 60.0, 40.0)]
    assert rectangles(_frame_lines()[:3]) == []


def test_device_frame_is_unique_and_needs_the_device_label() -> None:
    from dwg_audit.audit.superworks_wire_walk import device_frame

    rect = (0.0, 0.0, 60.0, 40.0)
    inside_label = [("2n", (20.0, 30.0, 24.0, 34.0))]
    adjacent_label = [("2n", (20.0, 43.0, 24.0, 46.0))]
    far_label = [("2n", (20.0, 60.0, 24.0, 64.0))]
    points = [(10.5, 20.0)]

    assert device_frame([rect], "2n", points, inside_label) == rect
    assert device_frame([rect], "2n", points, adjacent_label) == rect
    assert device_frame([rect], "2n", points, far_label) is None
    assert device_frame([rect], "1n", points, inside_label) is None
    assert device_frame([rect, (0.0, 0.0, 60.0, 40.0)], "2n", points, inside_label) is None


def _element(record, x, y):
    return SwPort(record_id=record, sheet_id="S1", file_id="F1", symbol_id=f"SW:S1:/{record}", insert_handle=record,
                  category="内部元件", endpoint_identity="", port_number="1",
                  start_x=x - 0.5, start_y=y, end_x=x + 0.5, end_y=y, label={"normalized": "", "resolved": False})


def _framed(label_text, extra_lines=()):
    from dwg_audit.domain.models import TextItem

    lines = [_line(f"F{i}", *seg) for i, seg in enumerate(_frame_lines())] + [
        _line("L1", 10.5, 20.0, 40.0, 20.0)] + [_line(f"X{i}", *seg) for i, seg in enumerate(extra_lines)]
    text = TextItem("TX", "S1", "F1", "TX", "TEXT", label_text, label_text, True, "DIM", 0.0, 2.5, 22.0, 32.0,
                    20.0, 30.0, 24.0, 34.0)
    return lines, [text]


def test_unresolved_element_inside_the_unique_frame_is_discarded_as_frame_internal() -> None:
    terminal = _terminal("T1", "SW:S1:/T", "2n612", "2n", 10.5, 20.0)
    element = _element("E1", 40.0, 20.0)
    data = _data([terminal, element], [])
    lines, texts = _framed("2n")
    group = LineGroup(line_group_id="G1", sheet_id="S1", file_id="F1", start_x=11.0, start_y=20.0, end_x=40.0,
                      end_y=20.0, length=29.0, wire_candidate_score=1.0, member_line_ids=["L1"], layer_hints=["WIRE"],
                      orientation="horizontal")
    output = [_half_pair("G1", "2n612", ["T1"])]

    stats = _discard_walked_half_pairs(output, data, lines, [group], texts=texts, block_rows=())

    assert stats == {"walk_discarded:review": 1, "walk_discarded_frame:review": 1}
    assert output[0].evidence["device_internal_discard"]["rule"] == "wire_walk_internal_frame"


def test_unresolved_element_outside_a_frame_or_with_a_leaving_wire_is_kept() -> None:
    terminal = _terminal("T1", "SW:S1:/T", "2n612", "2n", 10.5, 20.0)
    element = _element("E1", 40.0, 20.0)
    data = _data([terminal, element], [])
    lines, texts = _framed("1n")  # the frame carries another device's label: no frame for 2n
    group = LineGroup(line_group_id="G1", sheet_id="S1", file_id="F1", start_x=11.0, start_y=20.0, end_x=40.0,
                      end_y=20.0, length=29.0, wire_candidate_score=1.0, member_line_ids=["L1"], layer_hints=["WIRE"],
                      orientation="horizontal")
    output = [_half_pair("G1", "2n612", ["T1"])]

    stats = _discard_walked_half_pairs(output, data, lines, [group], texts=texts, block_rows=())

    assert stats == {"walk_kept:no_unique_frame": 1}
    assert output[0].status == "review"

    # the same frame and label, but the walk leaves the frame through the right edge
    lines, texts = _framed("2n", extra_lines=[(40.0, 20.0, 90.0, 20.0)])
    output = [_half_pair("G1", "2n612", ["T1"])]
    stats = _discard_walked_half_pairs(output, data, lines, [group], texts=texts, block_rows=())

    assert stats == {"walk_kept:walk_leaves_frame": 1}
