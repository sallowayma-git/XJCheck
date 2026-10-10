"""Z-3 (category H) and Z-4b: a one-sided legacy pair whose line group is a table cell edge of one INSERT,
with grid-confirmed row neighbours on one layer, column frames at both ends, and nothing outward of the missing
end on either row centre, is retired as table_cell_edge_no_outward.  A lone neighbour (for example a note box
edge) does not define the grid; panel-owned pairs are never changed.  Every other case, and every SuperWORKS
row or two-sided pair, is left as it was."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from dwg_audit.audit.superworks_extractor import TABLE_CELL_REASON, supersede_cell_edge_pairs
from dwg_audit.domain.models import LineEntity, LineGroup, Pair, TextItem

SHEET = "S14"
FILE = "F14"
OWNER = "3214C"
EDGE_Y = 97.5          # the cell edge (member VIRTUAL line, span 55..75)
NEIGHBOUR_Y = 102.5    # the parallel grid border above, same span, five units above
LOWER_Y = 92.5         # the parallel grid border below, same span, five units below
PRESENT = (55.98, 98.53)  # present text '13' at the left end; the missing end is the right end (75, 97.5)
PANEL_FAMILY = "communication.equipment_panel_ignored.v1"


def _line(line_id, handle, start, end, source="LINE", layer="0"):
    return LineEntity(line_id=line_id, sheet_id=SHEET, file_id=FILE, handle=handle, source_entity_type=source,
                      layer=layer, start_x=start[0], start_y=start[1], end_x=end[0], end_y=end[1],
                      length=abs(end[0] - start[0]) + abs(end[1] - start[1]), angle_deg=0.0,
                      bbox_min_x=min(start[0], end[0]), bbox_min_y=min(start[1], end[1]),
                      bbox_max_x=max(start[0], end[0]), bbox_max_y=max(start[1], end[1]))


def _group(group_id, member_line_ids, start, end):
    return LineGroup(group_id, SHEET, FILE, start[0], start[1], end[0], end[1], abs(end[0] - start[0]), 0.4,
                     member_line_ids=list(member_line_ids), layer_hints=["0"], orientation="horizontal")


def _pair(pair_id="PC0051", group_id="GC0051", left="13", right=None, evidence=None, pair_kind="ordinary_pair",
          status="review", right_coord=None):
    ev = {"pair_kind": "ordinary_pair"} if evidence is None else dict(evidence)
    return Pair(pair_id, group_id, SHEET, FILE, None, left_value=left, right_value=right, confidence=0.5,
                status=status, rationale="missing right candidate", evidence=ev, pair_kind=pair_kind,
                left_text_id="T1", right_text_id=None if right is None else "T2",
                left_coord_x=PRESENT[0], left_coord_y=PRESENT[1],
                right_coord_x=None if right_coord is None else right_coord[0],
                right_coord_y=None if right_coord is None else right_coord[1])


def _text(text_id="TX1", bbox=(76.0, 96.0, 79.0, 98.5), height=3.0, value="ZZ"):
    x0, y0, x1, y1 = bbox
    corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    return TextItem(text_id=text_id, sheet_id=SHEET, file_id=FILE, handle="H" + text_id, entity_type="TEXT",
                    text=value, normalized_text=value, is_numeric_candidate=False, layer="TEXT", rotation_deg=0.0,
                    height=height, insert_x=x0, insert_y=y0, bbox_min_x=x0, bbox_min_y=y0, bbox_max_x=x1,
                    bbox_max_y=y1, text_geometry_json=json.dumps({"corners": corners}))


def _world(*, extra_lines=(), frames=True, neighbour=True, above=True, below=True, texts=(),
           edge_handle=f"{OWNER}:VIRTUAL:616", frame_y=(85.0, 115.0), frame_right_y=None):
    """A table of one INSERT on layer 0: edge at 97.5 (55..75), grid neighbours at 102.5 (above) and 92.5 (below),
    column frames at x=55 and x=75 covering 85..115, a divider at x=65.  Pair GC0051's only member is the edge."""
    lines = [_line("L1374", edge_handle, (55.0, EDGE_Y), (75.0, EDGE_Y), source="LWPOLYLINE")]
    if neighbour and above:
        lines.append(_line("L1375", f"{OWNER}:VIRTUAL:617", (55.0, NEIGHBOUR_Y), (75.0, NEIGHBOUR_Y)))
    if neighbour and below:
        lines.append(_line("L1376", f"{OWNER}:VIRTUAL:618", (55.0, LOWER_Y), (75.0, LOWER_Y)))
    if frames:
        lines.append(_line("L1380", f"{OWNER}:VIRTUAL:700", (55.0, frame_y[0]), (55.0, frame_y[1]), source="LWPOLYLINE"))
        right = frame_right_y or frame_y
        lines.append(_line("L1381", f"{OWNER}:VIRTUAL:701", (75.0, right[0]), (75.0, right[1]), source="LWPOLYLINE"))
    lines.append(_line("L1390", f"{OWNER}:VIRTUAL:702", (65.0, 85.0), (65.0, 115.0)))
    lines.extend(extra_lines)
    groups = [_group("GC0051", ["L1374"], (55.0, EDGE_Y), (75.0, EDGE_Y))]
    return lines, groups, list(texts)


def _run(pairs, world, ledger=None):
    lines, groups, texts = world
    return supersede_cell_edge_pairs(list(pairs), [] if ledger is None else ledger, lines, groups, texts)


def _status(result, pair_id="PC0051"):
    return next(p for p in result if p.pair_id == pair_id)


def test_cell_edge_without_outward_lead_is_discarded_and_recorded_as_category_h():
    world = _world()
    pair = _pair()
    result, ledger = _run([pair], world)
    new = _status(result)
    assert new.status == "discard"
    assert new.rationale.startswith(TABLE_CELL_REASON)
    assert len(result) == 1
    evidence = new.evidence["table_cell_edge"]
    assert evidence["owner"] == OWNER
    assert evidence["missing_side"] == "right"
    assert evidence["missing_end"] == [75.0, EDGE_Y]
    assert evidence["grid_basis"] == "both_sides"
    assert evidence["neighbour_handles"] == [f"{OWNER}:VIRTUAL:617", f"{OWNER}:VIRTUAL:618"]
    assert [probe["side"] for probe in evidence["probes"]] == ["higher_y", "lower_y"]
    assert all(probe["clear"] is True for probe in evidence["probes"])
    assert evidence["probes"][0]["tolerance"] == pytest.approx(0.75)
    assert len(ledger) == 1
    assert ledger[0]["category"] == "H"
    assert ledger[0]["reason"] == TABLE_CELL_REASON
    assert ledger[0]["new_pairs"] == []


def test_pin_mark_straddling_the_frame_is_not_a_lead():
    pin = [_line("L1400", f"{OWNER}:VIRTUAL:639:0", (74.5, 100.0), (75.5, 100.0), source="LWPOLYLINE")]
    result, _ = _run([_pair()], _world(extra_lines=pin))
    assert _status(result).status == "discard"


def test_lead_leaving_the_frame_at_row_centre_blocks_the_discard():
    lead = [_line("L1401", "32C56", (75.0, 100.0), (78.0, 100.0))]
    result, ledger = _run([_pair()], _world(extra_lines=lead))
    assert _status(result).status == "review"
    assert ledger == []


def test_lead_at_the_lower_row_centre_blocks_the_discard():
    # Both row centres (above and below the edge) must be clear, not only the one nearest the neighbour.
    lead = [_line("L1402", "32C57", (75.0, 95.0), (78.0, 95.0))]
    result, ledger = _run([_pair()], _world(extra_lines=lead))
    assert _status(result).status == "review"
    assert ledger == []


def test_text_within_one_and_a_half_heights_of_missing_end_blocks_the_discard():
    text = _text(bbox=(76.0, 96.0, 79.0, 98.5), height=3.0)  # 1.0 from (75, 97.5) < 4.5
    result, _ = _run([_pair()], _world(texts=[text]))
    assert _status(result).status == "review"


def test_text_beyond_one_and_a_half_heights_of_missing_end_does_not_block():
    # The label sits next to the row centre but 6+ from the missing end.
    text = _text(bbox=(80.0, 102.0, 84.0, 104.0), height=3.0)
    result, _ = _run([_pair()], _world(texts=[text]))
    assert _status(result).status == "discard"


def test_text_on_the_inner_side_of_the_frame_does_not_block():
    text = _text(bbox=(70.0, 96.0, 74.0, 98.5), height=3.0)
    result, _ = _run([_pair()], _world(texts=[text]))
    assert _status(result).status == "discard"


def test_two_sided_pair_is_never_changed():
    pair = _pair(right="GND", right_coord=(75.0, 97.5))
    result, ledger = _run([pair], _world())
    assert _status(result).status == "review"
    assert ledger == []


def test_superworks_source_pair_is_never_changed():
    pair = _pair(evidence={"pair_kind": "ordinary_pair", "source": "superworks"})
    result, ledger = _run([pair], _world())
    assert _status(result).status == "review"
    assert ledger == []


def test_non_ordinary_pair_kind_is_never_changed():
    pair = _pair(pair_kind="component_mapping")
    result, ledger = _run([pair], _world())
    assert _status(result).status == "review"
    assert ledger == []


def test_already_discarded_pair_is_not_processed_again():
    pair = _pair(status="discard")
    result, ledger = _run([pair], _world())
    assert _status(result).status == "discard"
    assert _status(result).rationale == "missing right candidate"
    assert ledger == []


@pytest.mark.parametrize("evidence", [
    {"pair_kind": "ordinary_pair", "ignored_panel_family_id": PANEL_FAMILY},
    {"pair_kind": "ordinary_pair", "ordinary_pair_eligible": False},
])
def test_panel_owned_pair_is_never_changed_and_writes_no_ledger_entry(evidence):
    # The panel IGNORE mark runs before this rule, so a panel-owned pair must never be retired here.
    result, ledger = _run([_pair(evidence=evidence)], _world())
    assert _status(result).status == "review"
    assert _status(result).evidence == evidence
    assert ledger == []


def test_member_from_another_insert_blocks_the_discard():
    other = _line("L1410", "3215D:VIRTUAL:9", (55.0, EDGE_Y), (75.0, EDGE_Y))
    lines, _, texts = _world()
    lines.append(other)
    groups = [_group("GC0051", ["L1374", "L1410"], (55.0, EDGE_Y), (75.0, EDGE_Y))]
    result, ledger = supersede_cell_edge_pairs([_pair()], [], lines, groups, texts)
    assert _status(result).status == "review"
    assert ledger == []


def test_member_that_is_not_virtual_blocks_the_discard():
    lines, groups, texts = _world()
    lines[0] = _line("L1374", "1F2A:0", (55.0, EDGE_Y), (75.0, EDGE_Y))
    result, ledger = supersede_cell_edge_pairs([_pair()], [], lines, groups, texts)
    assert _status(result).status == "review"
    assert ledger == []


def test_vertical_group_is_not_a_cell_edge():
    lines = [_line("L1374", f"{OWNER}:VIRTUAL:616", (75.0, 85.0), (75.0, 115.0), source="LWPOLYLINE")]
    groups = [_group("GC0051", ["L1374"], (75.0, 85.0), (75.0, 115.0))]
    result, ledger = supersede_cell_edge_pairs([_pair()], [], lines, groups, [])
    assert _status(result).status == "review"
    assert ledger == []


def test_no_grid_neighbour_blocks_the_discard():
    result, ledger = _run([_pair()], _world(neighbour=False))
    assert _status(result).status == "review"
    assert ledger == []


def test_neighbour_far_beyond_the_row_pitch_is_not_a_grid_row():
    # A border 70 above the edge is beyond two pitches of the 5-unit grid, so it is not a row neighbour and its
    # probe band (y 122..143) is never checked: the lead there does not block.
    far = [_line("L1420", f"{OWNER}:VIRTUAL:730", (55.0, 167.5), (75.0, 167.5))]
    lead = [_line("L1425", "32C99", (75.0, 135.0), (79.0, 135.0))]
    result, ledger = _run([_pair()], _world(extra_lines=far + lead))
    assert _status(result).status == "discard"
    assert _status(result).evidence["table_cell_edge"]["neighbour_handles"] == [
        f"{OWNER}:VIRTUAL:617", f"{OWNER}:VIRTUAL:618"]
    assert len(ledger) == 1


def test_lone_neighbour_on_another_layer_is_not_a_grid_row():
    # The p051 shape: the only horizontal line near the edge is a note box edge on layer CH of the same INSERT.
    # It is not on the table layer, so it does not define the row grid and the pair is not discarded.
    note_box = [_line("L1430", f"{OWNER}:VIRTUAL:44:0", (55.0, NEIGHBOUR_Y), (75.0, NEIGHBOUR_Y), layer="CH")]
    result, ledger = _run([_pair()], _world(above=False, below=False, extra_lines=note_box))
    assert _status(result).status == "review"
    assert ledger == []


def test_lone_same_layer_neighbour_without_equal_spacing_run_is_not_a_grid_row():
    # One side only and no three equally spaced parallel borders in the block: the neighbour cannot set the pitch.
    result, ledger = _run([_pair()], _world(below=False))
    assert _status(result).status == "review"
    assert ledger == []


def test_lone_neighbour_confirmed_by_equal_spacing_run_is_discarded():
    # One side only, but the block's own ladder (97.5, 102.5, 107.5) is equally spaced at the pitch: a grid.
    row = [_line("L1431", f"{OWNER}:VIRTUAL:619", (55.0, 107.5), (75.0, 107.5))]
    result, ledger = _run([_pair()], _world(below=False, extra_lines=row))
    new = _status(result)
    assert new.status == "discard"
    evidence = new.evidence["table_cell_edge"]
    assert evidence["grid_basis"] == "equal_spacing"
    assert evidence["neighbour_handles"] == [f"{OWNER}:VIRTUAL:617"]
    assert evidence["probes"][1]["neighbour_handle"] is None
    assert evidence["probes"][1]["neighbour_y"] == pytest.approx(EDGE_Y - 5.0)
    assert len(ledger) == 1


def test_pin_dash_between_rows_does_not_break_the_equal_spacing_ladder():
    # A one-unit VIRTUAL pin dash at y=100 sits between the edge (97.5) and the rows at 102.5 and 107.5. Without the
    # row-length filter the ladder would read 2.5 gaps and the lone neighbour would not be confirmed.
    row = [_line("L1431", f"{OWNER}:VIRTUAL:619", (55.0, 107.5), (75.0, 107.5))]
    dash = [_line("L1432", f"{OWNER}:VIRTUAL:639:0", (74.5, 100.0), (75.5, 100.0), source="LWPOLYLINE")]
    result, ledger = _run([_pair()], _world(below=False, extra_lines=row + dash))
    assert _status(result).status == "discard"
    assert _status(result).evidence["table_cell_edge"]["grid_basis"] == "equal_spacing"
    assert len(ledger) == 1


def test_frame_that_does_not_reach_the_edge_blocks_the_discard():
    # The right-hand frame stops at 99, short of the edge at 97.5 (tolerance 0.75).
    result, ledger = _run([_pair()], _world(frame_right_y=(99.0, 115.0)))
    assert _status(result).status == "review"
    assert ledger == []


def test_frame_on_the_other_end_is_required_too():
    result, ledger = _run([_pair()], _world(frames=False))
    assert _status(result).status == "review"
    assert ledger == []


def test_no_pair_is_removed_and_other_pairs_are_unchanged():
    keep = _pair(pair_id="PC0099", group_id="GCX", left="7", right="8")
    result, ledger = _run([_pair(), keep], _world())
    assert len(result) == 2
    assert _status(result, "PC0099") == keep
    assert _status(result).status == "discard"
    assert len(ledger) == 1
