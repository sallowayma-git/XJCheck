"""L-12 S1 (Y2b): a one-sided legacy ordinary pair is completed from an unclaimed SuperWORKS connect text
whose layout outline lies within 1.5 text heights of the missing line end, outside that window at the
present end, and nearest to the missing end by a clear margin; every other case stays one-sided."""
from __future__ import annotations

import json
from dataclasses import replace

from dwg_audit.audit.superworks_extractor import (SW_LABEL_BOX_TOL_HEIGHTS, SW_LABEL_SEPARATION,
                                                  extract_superworks_pairs)
from dwg_audit.domain.models import LineGroup, Pair, SheetRecord, SwConnectLabel, TextItem
from dwg_audit.extract.superworks_semantics import SuperworksData

# Line from x=55 (present text end) to x=75 (missing end); the present text '13' sits left of 55.
MISSING_END = (75.0, 97.5)
PRESENT_END = (55.0, 97.5)


def _page():
    return SheetRecord("S1", "F1", "test.dwg", 1, "14", "test", "二次原理图", "primary", "filename", True,
                       audit_disposition="audit")


def _group():
    return LineGroup("GL12", "S1", "F1", PRESENT_END[0], PRESENT_END[1], MISSING_END[0], MISSING_END[1], 20.0, 1.0)


def _one_sided(pair_id="PC0051", value="13", text_id="T13", side="left", line_group_id="GL12"):
    coords = {"left_coord_x": 45.0, "left_coord_y": 97.5} if side == "left" else {"right_coord_x": 45.0, "right_coord_y": 97.5}
    values = {"left_value": value, "right_value": None} if side == "left" else {"left_value": None, "right_value": value}
    return Pair(pair_id, line_group_id, "S1", "F1", None, confidence=0.68, status="review",
                rationale="missing right candidate", evidence={"pair_kind": "ordinary_pair"},
                pair_kind="ordinary_pair", **values,
                left_text_id=text_id if side == "left" else None,
                right_text_id=text_id if side == "right" else None, **coords)


def _outline(anchor, height=3.0):
    """Bottom-middle layout box of a TEXT anchored at its bottom middle (4.1 high at height 3.0)."""
    ax, ay = anchor
    top = ay + 4.1 * height / 3.0
    return [[ax - 4.0, ay], [ax + 4.0, ay], [ax + 4.0, top], [ax - 4.0, top]]


def _label(value="YD10", anchor=(74.0, 100.0), text_id="TYD10", record_id="SWC:F1:1", sheet_id="S1",
           reason_codes=("unresolved_part_port",), height=3.0, corners=None, geometry=True):
    if corners is None and geometry:
        corners = _outline(anchor, height)
    return SwConnectLabel(record_id=record_id, sheet_id=sheet_id, file_id="F1",
                          text={"value": value, "text_id": text_id, "x": anchor[0] - 4.6, "y": anchor[1],
                                "anchor_x": anchor[0], "anchor_y": anchor[1], "handle": "H" + record_id[-1],
                                "height": height, "corners": corners},
                          reason_codes=list(reason_codes))


def _text_item(label):
    text = label.text
    corners = text["corners"]
    xs = [p[0] for p in corners] if corners else [text["x"]]
    ys = [p[1] for p in corners] if corners else [text["y"]]
    return TextItem(text_id=text["text_id"], sheet_id=label.sheet_id, file_id=label.file_id, handle=text["handle"],
                    entity_type="TEXT", text=text["value"], normalized_text=text["value"], is_numeric_candidate=False,
                    layer="TEXT", rotation_deg=0.0, height=text["height"], insert_x=text["x"], insert_y=text["y"],
                    bbox_min_x=min(xs), bbox_min_y=min(ys), bbox_max_x=max(xs), bbox_max_y=max(ys),
                    text_geometry_json=json.dumps({"corners": corners}) if corners else "{}")


def _run(pairs, labels, groups=None):
    data = SuperworksData(connect_labels=list(labels))
    return extract_superworks_pairs(data, pages=[_page()], texts=[_text_item(label) for label in labels], lines=[],
                                    line_groups=groups if groups is not None else [_group()],
                                    pairs=list(pairs), table_mappings=[])


def _row_group(group_id, start, end):
    return LineGroup(group_id, "S1", "F1", start[0], start[1], end[0], end[1], 20.0, 1.0)


def test_missing_side_is_completed_from_connect_text_and_stays_for_review():
    old = _one_sided()
    result, _, ledger = _run([old], [_label()])
    new = result[0]
    assert new.right_value == "YD10" and new.right_text_id == "TYD10"
    assert new.left_value == "13" and new.left_text_id == "T13"
    assert new.status == "review" and new.confidence_bucket == "review"
    assert new.confidence == old.confidence
    assert old.right_value is None and old.status == "review"          # the input pair is not mutated
    fill = new.evidence["sw_missing_side_fill"]
    assert fill["source"] == "superworks_connect_label" and fill["side"] == "right"
    assert fill["text_id"] == "TYD10" and fill["connect_label_id"] == "SWC:F1:1"
    assert fill["value"] == "YD10" and fill["attribution"] == "text_bbox"
    assert fill["bbox_distance"] == 2.5 and fill["text_height"] == 3.0
    assert fill["tolerance"] == 4.5 and fill["present_end_bbox_distance"] > fill["tolerance"]
    assert fill["second_end_distance"] == fill["present_end_bbox_distance"]
    assert len(ledger) == 1 and ledger[0]["reason"] == "sw_connect_label_missing_side_fill"
    assert ledger[0]["category"] == "A"


def test_missing_left_side_is_completed_symmetrically():
    pair = _one_sided(side="right", value="13", text_id="T13")
    group = LineGroup("GL12", "S1", "F1", MISSING_END[0], MISSING_END[1], PRESENT_END[0], PRESENT_END[1], 20.0, 1.0)
    pair = replace(pair, right_coord_x=45.0, right_coord_y=97.5)
    result, _, _ = _run([pair], [_label(anchor=(76.5, 100.0))], groups=[group])
    assert result[0].left_value == "YD10" and result[0].left_text_id == "TYD10"
    assert result[0].right_value == "13"
    assert result[0].evidence["sw_missing_side_fill"]["side"] == "left"


def test_anchor_midway_between_rows_but_outline_touching_own_row_is_completed():
    """The anchor is 2.5 from both row ends (the old anchor rule could not decide); the outline
    touches only the missing end's row, with a clear margin over the adjacent row."""
    neighbour = _row_group("GLB", (PRESENT_END[0], 102.5), (MISSING_END[0], 102.5))
    label = _label(anchor=(75.0, 100.0), corners=[[76.0, 95.0], [84.0, 95.0], [84.0, 99.1], [76.0, 99.1]])
    result, _, ledger = _run([_one_sided()], [label], groups=[_group(), neighbour])
    assert result[0].right_value == "YD10" and result[0].right_text_id == "TYD10"
    fill = result[0].evidence["sw_missing_side_fill"]
    assert fill["bbox_distance"] == 1.0 and fill["second_end_distance"] > fill["bbox_distance"] + fill["separation_min"]
    assert len(ledger) == 1


def test_outline_equidistant_from_both_rows_is_not_filled():
    neighbour = _row_group("GLB", (PRESENT_END[0], 102.5), (MISSING_END[0], 102.5))
    label = _label(anchor=(75.0, 100.0), corners=[[60.0, 99.0], [90.0, 99.0], [90.0, 101.0], [60.0, 101.0]])
    result, _, ledger = _run([_one_sided()], [label], groups=[_group(), neighbour])
    assert result[0].right_value is None and "sw_missing_side_fill" not in result[0].evidence and ledger == []


def test_distance_at_the_window_edge_is_filled_and_beyond_is_not():
    inside, _, _ = _run([_one_sided()], [_label(anchor=(75.0, 101.9))])      # outline 4.4 from missing end
    assert inside[0].right_value == "YD10"
    outside, _, ledger = _run([_one_sided()], [_label(anchor=(75.0, 102.1))])  # outline 4.6 from missing end
    assert outside[0].right_value is None and "sw_missing_side_fill" not in outside[0].evidence
    assert ledger == []
    assert SW_LABEL_BOX_TOL_HEIGHTS == 1.5


def test_window_scales_with_text_height():
    inside, _, _ = _run([_one_sided()], [_label(anchor=(75.0, 101.2), height=2.5)])   # 3.7 < 3.75
    assert inside[0].right_value == "YD10"
    assert inside[0].evidence["sw_missing_side_fill"]["tolerance"] == 3.75
    outside, _, ledger = _run([_one_sided()], [_label(anchor=(75.0, 101.3), height=2.5)])  # 3.8 > 3.75
    assert outside[0].right_value is None and ledger == []


def test_multi_value_connect_text_is_not_filled():
    old = _one_sided()
    result, _, ledger = _run([old], [_label(value="& 2-1KLP12-1,2-1KLP2-1")])
    assert result[0].right_value is None and result[0] is old and ledger == []


def test_connect_text_already_used_by_another_pair_is_not_filled():
    old = _one_sided()
    other = Pair("PC9", "GL99", "S1", "F1", None, "YD10", None, 0.9, "pass", "other", pair_kind="ordinary_pair",
                 left_text_id="TYD10")
    result, _, ledger = _run([old, other], [_label()])
    assert result[0].right_value is None and ledger == []


def test_connect_text_referenced_only_in_evidence_is_treated_as_used():
    old = _one_sided()
    other = Pair("PCX", "GL99", "S1", "F1", None, "1", "2", 0.9, "pass", "other", pair_kind="ordinary_pair",
                 evidence={"superworks": {"connection_text_id": "TYD10"}})
    result, _, _ = _run([old, other], [_label()])
    assert result[0].right_value is None


def test_text_claimed_by_two_one_sided_pairs_is_not_filled_for_either():
    """Two line groups with the same missing end: one unclaimed text cannot name both ends' remote."""
    twin = LineGroup("GL13", "S1", "F1", PRESENT_END[0], PRESENT_END[1], MISSING_END[0], MISSING_END[1], 20.0, 1.0)
    second = _one_sided(pair_id="PC0052", value="14", text_id="T14", line_group_id="GL13")
    result, _, ledger = _run([_one_sided(), second], [_label(anchor=(74.0, 99.0))], groups=[_group(), twin])
    assert result[0].right_value is None and result[1].right_value is None and ledger == []


def test_outline_within_window_of_another_line_end_on_the_sheet_is_not_filled():
    sibling = LineGroup("GLS", "S1", "F1", 74.0, 103.5, 90.0, 103.5, 16.0, 1.0)     # its end lies inside the outline
    result, _, ledger = _run([_one_sided()], [_label(anchor=(74.0, 100.0))], groups=[_group(), sibling])
    assert result[0].right_value is None and ledger == []


def test_text_within_window_of_both_ends_of_a_short_line_is_not_filled():
    short = LineGroup("GL12", "S1", "F1", PRESENT_END[0], PRESENT_END[1], 60.0, 97.5, 5.0, 1.0)
    result, _, ledger = _run([_one_sided()], [_label(anchor=(57.5, 99.5))], groups=[short])
    assert result[0].right_value is None and ledger == []


def test_text_without_outline_geometry_is_not_filled():
    result, _, ledger = _run([_one_sided()], [_label(geometry=False)])
    assert result[0].right_value is None and ledger == []


def test_functional_label_with_cjk_text_is_not_filled():
    result, _, ledger = _run([_one_sided()], [_label(value="系统告警(NO3)")])
    assert result[0].right_value is None and ledger == []


def test_unresolved_geometry_or_true_conflict_label_is_not_filled():
    for reasons in (("ambiguous_connect_line",), ("dangling_label_handle",)):
        result, _, ledger = _run([_one_sided()], [_label(reason_codes=reasons)])
        assert result[0].right_value is None and ledger == [], reasons


def test_label_on_another_sheet_is_not_filled():
    result, _, ledger = _run([_one_sided()], [_label(sheet_id="S9")])
    assert result[0].right_value is None and ledger == []


def test_complete_pair_is_left_untouched():
    complete = Pair("PC0051", "GL12", "S1", "F1", None, "13", "14", 0.95, "pass", "complete", pair_kind="ordinary_pair",
                    left_text_id="T13", right_text_id="T14", left_coord_x=45.0, left_coord_y=97.5,
                    right_coord_x=77.0, right_coord_y=97.5)
    result, _, ledger = _run([complete], [_label()])
    assert result[0] is complete and ledger == []


def test_superworks_sourced_or_non_ordinary_pair_is_not_filled():
    wire = replace(_one_sided(), pair_kind="wire_component_mapping")
    sourced = replace(_one_sided(pair_id="PC0077"), evidence={"source": "superworks", "pair_kind": "ordinary_pair"})
    result, _, ledger = _run([wire, sourced], [_label()])
    assert result[0].right_value is None and result[1].right_value is None and ledger == []


def test_label_beside_leader_end_with_margin_of_1_24_over_next_row_is_completed():
    """Shape of the four known-good GND fills of p075: the label sits right of the missing end
    (outline 3.0 away), and the next row end lies 4.24 away, a margin of 1.24."""
    group = _row_group("GL12", (370.0, 152.5), (390.0, 152.5))
    pair = replace(_one_sided(side="left", value="06"), left_coord_x=370.98, left_coord_y=153.53,
                   right_value=None, right_coord_x=None, right_coord_y=None)
    next_row = _row_group("GLN", (370.0, 157.5), (390.0, 157.5))
    label = _label(value="GND", anchor=(396.36, 150.38), text_id="TGND",
                   corners=[[393.0, 150.38], [399.71, 150.38], [399.71, 154.5], [393.0, 154.5]])
    result, _, ledger = _run([pair], [label], groups=[group, next_row])
    assert result[0].right_value == "GND" and result[0].right_text_id == "TGND"
    fill = result[0].evidence["sw_missing_side_fill"]
    assert fill["bbox_distance"] == 3.0 and abs(fill["second_end_distance"] - 4.2426) < 1e-3
    assert len(ledger) == 1


def test_separation_constant_is_one_text_unit():
    assert SW_LABEL_SEPARATION == 1.0
