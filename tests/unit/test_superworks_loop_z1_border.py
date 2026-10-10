"""Z-1 (category H): a one-sided legacy pair on a table border row is retired when a SuperWORKS pass
row already carries that row end: its connect stub lies on the midline between the border and its
neighbour, and its external text is within 1.5 text heights of the missing end.  Every other case,
and any SW row or pair not touched, is left as it was."""
from __future__ import annotations

import json
from dataclasses import asdict, replace

from dwg_audit.audit.superworks_extractor import supersede_border_row_duplicates
from dwg_audit.domain.models import LineEntity, LineGroup, Pair, TextItem

SHEET = "S14"
FILE = "F14"
OWNER = "3214C"
PRESENT = (55.98, 98.53)   # present text '13' (left side)
OLD_LINE_Y = 97.5          # border row whose missing end is (75, 97.5)


def _line(line_id, handle, start, end):
    return LineEntity(line_id=line_id, sheet_id=SHEET, file_id=FILE, handle=handle, source_entity_type="LINE",
                      layer="0", start_x=start[0], start_y=start[1], end_x=end[0], end_y=end[1],
                      length=abs(end[0] - start[0]) + abs(end[1] - start[1]), angle_deg=0.0,
                      bbox_min_x=min(start[0], end[0]), bbox_min_y=min(start[1], end[1]),
                      bbox_max_x=max(start[0], end[0]), bbox_max_y=max(start[1], end[1]))


def _group(group_id, member_line_ids, start, end):
    return LineGroup(group_id, SHEET, FILE, start[0], start[1], end[0], end[1], abs(end[0] - start[0]), 0.4,
                     member_line_ids=list(member_line_ids), layer_hints=["0"], orientation="horizontal")


def _old(pair_id="PC0051", group_id="GC0051", value="13", present=PRESENT, eligible=None, source=None):
    evidence = {"pair_kind": "ordinary_pair"}
    if eligible is not None:
        evidence["ordinary_pair_eligible"] = eligible
    if source is not None:
        evidence["source"] = source
    return Pair(pair_id, group_id, SHEET, FILE, None, left_value=value, right_value=None, confidence=0.5,
                status="review", rationale="missing right candidate", evidence=evidence,
                pair_kind="ordinary_pair", left_text_id="T2069", right_text_id=None,
                left_coord_x=present[0], left_coord_y=present[1], right_coord_x=None, right_coord_y=None)


def _sw(pair_id="PSW1", connect_line_id="LC1", external_text="TYD1", status="pass", unique=True):
    evidence = {"component_submode": "superworks_connect_line_port", "external_endpoint_text_id": external_text,
                "superworks": {"connect_line_id": connect_line_id, "connect_line_geometry_unique": unique},
                "supporting_line_ids": [connect_line_id]}
    return Pair(pair_id, None, SHEET, FILE, None, left_value="1-26n-COM1", right_value="YD1", confidence=0.9,
                status=status, rationale="sw", evidence=evidence, pair_kind="component_mapping",
                left_text_id="T2175", right_text_id=external_text)


def _text(text_id="TYD1", bbox=(76.0, 97.5, 79.0, 101.0), height=3.0):
    x0, y0, x1, y1 = bbox
    corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    return TextItem(text_id=text_id, sheet_id=SHEET, file_id=FILE, handle="H" + text_id, entity_type="TEXT",
                    text="YD1", normalized_text="YD1", is_numeric_candidate=False, layer="TEXT", rotation_deg=0.0,
                    height=height, insert_x=x0, insert_y=y0, bbox_min_x=x0, bbox_min_y=y0, bbox_max_x=x1,
                    bbox_max_y=y1, text_geometry_json=json.dumps({"corners": corners}))


def _world(stub_y=100.0, border_handle=f"{OWNER}:VIRTUAL:616", neighbour_handle=f"{OWNER}:VIRTUAL:617",
           neighbour_y=102.5, neighbour_span=(55.0, 75.0), text=None, extra_border=None):
    """Border GC0051 at y=97.5 (55..75), neighbour border above at 102.5, SW stub (75,stub_y)-(76,stub_y)."""
    lines = [_line("L1374", border_handle, (55.0, OLD_LINE_Y), (75.0, OLD_LINE_Y)),
             _line("L1400", neighbour_handle, (neighbour_span[0], neighbour_y), (neighbour_span[1], neighbour_y)),
             _line("LC1", "32C56", (75.0, stub_y), (76.0, stub_y))]
    if extra_border is not None:
        lines.append(extra_border)
    groups = [_group("GC0051", ["L1374"], (55.0, OLD_LINE_Y), (75.0, OLD_LINE_Y))]
    return lines, groups, [text or _text()]


def _run(pairs, sw_rows, world):
    lines, groups, texts = world
    return supersede_border_row_duplicates(list(pairs) + list(sw_rows), [], lines, groups, texts)


def test_border_row_with_sw_connect_stub_is_discarded_and_recorded_as_category_h():
    old, sw = _old(), _sw()
    world = _world()
    before_sw = asdict(sw)
    result, ledger = _run([old], [sw], world)
    new_old = next(p for p in result if p.pair_id == old.pair_id)
    assert new_old.status == "discard"
    assert "table_border_row_duplicates_sw_connect_stub" in new_old.rationale and "PSW1" in new_old.rationale
    record = new_old.evidence["table_border_row_duplicate"]
    assert record["sw_pair_id"] == "PSW1" and record["midline_y"] == 100.0 and record["stub_endpoint"] == [75.0, 100.0]
    assert old.status == "review" and "table_border_row_duplicate" not in old.evidence      # input not mutated
    assert len(result) == 2                                                                  # nothing removed
    assert asdict(next(p for p in result if p.pair_id == "PSW1")) == before_sw              # SW row unchanged
    assert len(ledger) == 1
    assert ledger[0]["category"] == "H" and ledger[0]["reason"] == "table_border_row_duplicates_sw_connect_stub"
    assert [p["pair_id"] for p in ledger[0]["new_pairs"]] == ["PSW1"]


def test_stub_inside_midline_tolerance_is_discarded_and_outside_is_kept():
    # spacing 5 -> tolerance 0.75 around the midline 100.0
    inside, ledger_in = _run([_old()], [_sw()], _world(stub_y=100.7))
    assert next(p for p in inside if p.pair_id == "PC0051").status == "discard" and len(ledger_in) == 1
    outside, ledger_out = _run([_old()], [_sw()], _world(stub_y=101.0))
    assert next(p for p in outside if p.pair_id == "PC0051").status == "review" and ledger_out == []


def test_stub_on_the_border_row_itself_is_not_a_midline_stub():
    result, ledger = _run([_old()], [_sw()], _world(stub_y=OLD_LINE_Y))
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_non_virtual_border_is_not_retired():
    world = _world(border_handle="12345")                # member handle without :VIRTUAL:
    result, ledger = _run([_old()], [_sw()], world)
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_non_horizontal_border_is_not_retired():
    lines, groups, texts = _world()
    lines[0] = _line("L1374", f"{OWNER}:VIRTUAL:616", (75.0, 90.0), (75.0, 97.5))   # vertical member
    groups[0] = _group("GC0051", ["L1374"], (75.0, 90.0), (75.0, 97.5))
    result, ledger = _run([_old()], [_sw()], (lines, groups, texts))
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_without_a_pass_sw_row_nothing_changes():
    result, ledger = _run([_old()], [_sw(status="review")], _world())
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []
    result, ledger = _run([_old()], [], _world())
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_sw_row_without_connect_line_geometry_is_not_used():
    result, ledger = _run([_old()], [_sw(unique=False)], _world())
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_external_text_beyond_1_5_heights_is_not_retired():
    far = _text(bbox=(90.0, 97.5, 93.0, 101.0))                # distance 15 from the missing end
    result, ledger = _run([_old()], [_sw()], _world(text=far))
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []
    edge = _text(bbox=(79.4, 97.5, 82.0, 101.0))               # distance 4.4 <= 4.5
    result, ledger = _run([_old()], [_sw()], _world(text=edge))
    assert next(p for p in result if p.pair_id == "PC0051").status == "discard" and len(ledger) == 1


def test_neighbour_in_another_table_is_not_a_border_neighbour():
    result, ledger = _run([_old()], [_sw()], _world(neighbour_handle="OTHER:VIRTUAL:617"))
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_stub_outside_the_shared_span_is_not_matched():
    result, ledger = _run([_old()], [_sw()], _world(neighbour_span=(55.0, 70.0)))
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_eligible_or_superworks_pairs_are_not_touched():
    for old in (_old(eligible=False), _old(source="superworks")):
        result, ledger = _run([old], [_sw()], _world())
        assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_border_pair_on_other_sheet_is_not_matched():
    other = replace(_sw(), sheet_id="S99")
    result, ledger = _run([_old()], [other], _world())
    assert next(p for p in result if p.pair_id == "PC0051").status == "review" and ledger == []


def test_two_borders_claiming_one_sw_row_are_both_retired():
    # Upper border at 102.5 (neighbour below 97.5) also has the stub on its midline (100.0);
    # its external text is 1.8 from the upper missing end and is claimed by both borders.
    upper_old = _old(pair_id="PC0057", group_id="GC0057", value="12", present=(55.98, 103.54))
    lines, groups, texts = _world(neighbour_y=102.5)
    lines = [l for l in lines if l.line_id != "L1400"]
    lines.append(_line("L1400", f"{OWNER}:VIRTUAL:617", (55.0, 102.5), (75.0, 102.5)))
    lines.append(_line("L1401", f"{OWNER}:VIRTUAL:618", (55.0, 92.5), (75.0, 92.5)))
    groups.append(_group("GC0057", ["L1400"], (55.0, 102.5), (75.0, 102.5)))
    pairs, ledger = supersede_border_row_duplicates([_old(), upper_old, _sw()], [], lines, groups, texts)
    statuses = {p.pair_id: p.status for p in pairs}
    assert statuses["PC0051"] == "discard" and statuses["PC0057"] == "discard"
    assert statuses["PSW1"] == "pass"
    assert len(ledger) == 2 and {e["old_pair"]["pair_id"] for e in ledger} == {"PC0051", "PC0057"}
    assert all(e["category"] == "H" for e in ledger)
    assert {p.evidence["table_border_row_duplicate"]["sw_pair_id"] for p in pairs
            if p.pair_id in {"PC0051", "PC0057"}} == {"PSW1"}


def test_short_sw_pin_tick_does_not_mask_the_adjacent_border():
    """A 1-unit VIRTUAL dash at the row centre (the SW pin mark) is nearer than the real border at 102.5;
    it does not cover the border span and must not be taken for the adjacent border."""
    tick = _line("LT", f"{OWNER}:VIRTUAL:890:0", (74.5, 100.0), (75.5, 100.0))
    result, ledger = _run([_old()], [_sw()], _world(extra_border=tick))
    assert next(p for p in result if p.pair_id == "PC0051").status == "discard" and len(ledger) == 1


def test_border_with_qualifying_sw_rows_on_both_sides_records_both_rows():
    """The border at 97.5 has an upper stub at 100.0 and a lower stub at 95.0 (each on a midline),
    and both external texts lie within 1.5 heights of its missing end: the pair is retired and both
    SW rows are recorded in the ledger; neither SW row changes."""
    lower_line = _line("L1402", f"{OWNER}:VIRTUAL:618", (55.0, 92.5), (75.0, 92.5))
    lower_stub = _line("LC2", "32C5X", (75.0, 95.0), (76.0, 95.0))
    lines, groups, _ = _world(extra_border=lower_line)
    lines.append(lower_stub)
    texts = [_text("TYD1"), _text("TYD2", bbox=(76.0, 93.0, 79.0, 96.5))]
    upper = _sw("PSW1", "LC1", "TYD1")
    lower = _sw("PSW2", "LC2", "TYD2")
    pairs, ledger = supersede_border_row_duplicates([_old(), upper, lower], [], lines, groups, texts)
    old = next(p for p in pairs if p.pair_id == "PC0051")
    assert old.status == "discard"
    assert old.evidence["table_border_row_duplicate"]["sw_pair_id"] == "PSW1"
    assert len(ledger) == 1 and [p["pair_id"] for p in ledger[0]["new_pairs"]] == ["PSW1", "PSW2"]
    assert asdict(next(p for p in pairs if p.pair_id == "PSW2")) == asdict(lower)
