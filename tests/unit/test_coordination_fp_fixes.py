"""Regression tests for the three false-positive fixes of the native-first coordination (FP-FIX).

1. A connect label already owned by a native SuperWORKS component row retires the legacy component claims on
   that label (round-25 behaviour) without generating its row a second time.
2. A nested definition's port copy (recorded under an ancestor instance) is dropped when its owner's record is
   at the same contact; an ancestor/descendant pair is one contact, not a competitor. Real competitors and real
   identity conflicts are still reported.
3. A native component row takes the BORDER frame its connect stub ends on as its line group, so that frame is
   owned by the native row and is not released to the ordinary pairing.
"""
from __future__ import annotations

from dwg_audit.audit.recognition_coordinator import SharedRecognitionContext
from dwg_audit.audit.superworks_extractor import (_endpoint, _frame_group_at_stub, _nested_instances,
                                                  extract_superworks_pairs)
from dwg_audit.domain.models import LineGroup, Pair, SheetRecord, SwConnectLabel, SwPartInstance, SwPort
from dwg_audit.extract.superworks_semantics import SuperworksData

NATIVE_SUBMODE = "superworks_connect_line_port"


def _page():
    return SheetRecord("S1", "F1", "test.dwg", 1, "14", "test", "元件接线图", "primary", "filename", True,
                       audit_disposition="audit")


def _native_row(pair_id, *, connection_handle, left_text="TPIN", right_text="TLBL", left="3-21KK-2",
                right="3-21CD11"):
    evidence = {"component_submode": NATIVE_SUBMODE, "source": "superworks",
                "superworks": {"source": "superworks", "connection_handle": connection_handle, "part_id": "SW:F1:S1:/B2EE"}}
    return Pair(pair_id, None, "S1", "F1", None, left_value=left, right_value=right, confidence=0.99, status="pass",
                rationale="native", evidence=evidence, pair_kind="component_mapping", confidence_bucket="high",
                left_text_id=left_text, right_text_id=right_text)


def _legacy_component(pair_id, *, left_text, right_text, left="11", right="8", line_group_id="GC0069"):
    return Pair(pair_id, line_group_id, "S1", "F1", None, left_value=left, right_value=right, confidence=0.9033,
                status="review", rationale="legacy", evidence={"pair_kind": "ordinary_pair"},
                pair_kind="component_mapping", confidence_bucket="review", left_text_id=left_text,
                right_text_id=right_text)


def _label(text_id="TLBL", handle="HLBL", value="3-21CD11"):
    return SwConnectLabel(record_id="SWC:F1:1", sheet_id="S1", file_id="F1",
                          text={"value": value, "text_id": text_id, "handle": handle, "x": 150.0, "y": 190.0,
                                "anchor_x": 159.46, "anchor_y": 190.63, "height": 3.0},
                          line_handle="FCDC", start_x=159.46, start_y=190.63, end_x=160.46, end_y=190.63,
                          part_id="SW:F1:S1:/B2EE", port_number="2", endpoint_identity="3-21KK-2",
                          reason_codes=[])


def _part():
    return SwPartInstance(record_id="SW:F1:S1:/B2EE", sheet_id="S1", file_id="F1", insert_handle="B2EE",
                          instance_path="/B2EE", block_name="PART", label={"handle": "HPART", "text_id": "TPART",
                          "value": "3-21CD11"}, ports=[])


def _run_label(pairs, label):
    data = SuperworksData(connect_labels=[label], part_instances=[_part()])
    return extract_superworks_pairs(data, pages=[_page()], texts=[], lines=[], line_groups=[], pairs=list(pairs),
                                    table_mappings=[], shared_context=SharedRecognitionContext())


# 1. Native-owned connect label retires legacy claims, never duplicates the native row.

def test_native_owned_label_retires_legacy_component_claim_and_keeps_native_row_once():
    native = _native_row("PSWNAT", connection_handle="HLBL")
    legacy = _legacy_component("PC0066", left_text="TLBL", right_text="TOTHER")
    output, _, ledger = _run_label([native, legacy], _label())
    assert [p.pair_id for p in output] == ["PSWNAT"]
    retired = [entry for entry in ledger if entry["old_pair"] and entry["old_pair"]["pair_id"] == "PC0066"]
    assert len(retired) == 1
    assert retired[0]["category"] == "B"
    assert retired[0]["reason"] == "validated_superworks_replacement"
    assert [p["pair_id"] for p in retired[0]["new_pairs"]] == ["PSWNAT"]


def test_native_owned_label_leaves_unrelated_component_claims_alone():
    native = _native_row("PSWNAT", connection_handle="HLBL")
    unrelated = _legacy_component("PC0099", left_text="TELSE", right_text="TOTHER")
    output, _, ledger = _run_label([native, unrelated], _label())
    assert {p.pair_id for p in output} == {"PSWNAT", "PC0099"}
    assert not [entry for entry in ledger if entry["old_pair"] and entry["old_pair"]["pair_id"] == "PC0099"]


def test_label_without_native_row_still_generates_its_own_row():
    # No native row yet: the label's row is generated and replaces the legacy claim (round-25 path, id kept).
    legacy = _legacy_component("PC0066", left_text="TLBL", right_text="TOTHER")
    output, _, ledger = _run_label([legacy], _label())
    native_rows = [p for p in output if (p.evidence or {}).get("component_submode") == NATIVE_SUBMODE]
    assert len(native_rows) == 1
    assert native_rows[0].pair_kind == "component_mapping"
    assert any(entry["old_pair"] and entry["old_pair"]["pair_id"] == "PC0066" for entry in ledger)


# 2. Nested definition copies and ancestor/descendant contacts.

def _port(record_id, *, instance, marker, number, symbol_category, identity=None, definition=None,
          x=202.25, y=167.5, insert="2F60B"):
    validation = {"port_touched_by_wire": True}
    if definition is not None:
        validation["definition_path"] = definition
    return SwPort(record_id=record_id, sheet_id="S1", file_id="F1", symbol_id=f"SW:F1:S1:{instance}",
                  insert_handle=insert, instance_path=instance, marker_handle=marker, port_number=number,
                  category=symbol_category, start_x=x, start_y=y, end_x=x + 0.5, end_y=y, tolerance=0.3,
                  endpoint_identity=identity, label={}, pin={}, wire_contacts=[], validation=validation)


def _coil_contact(parent_identity="HHJB-V"):
    """The /A/B coil's terminal, its copy recorded under /A, and the parent's own pin at the same contact."""
    coil = _port("SW:F1:S1:/A/B:/A/B:M1:1", instance="/A/B", marker="M1", number="1", symbol_category="线圈",
                 definition="/A/B")
    copy = _port("SW:F1:S1:/A:/A/B:M1:1", instance="/A", marker="M1", number="1", symbol_category="内部元件",
                 definition="/A/B")
    parent_pin = _port("SW:F1:S1:/A:/A:P1:1", instance="/A", marker="P1", number="1", symbol_category="内部元件",
                       identity=parent_identity, definition="/A")
    return coil, copy, parent_pin


def test_nested_copy_is_dropped_and_owner_plus_parent_pin_is_one_contact_without_conflict():
    coil, copy, parent_pin = _coil_contact()
    # Walk order of the pipeline: the parent's own records precede the nested owner's record.
    endpoint = _endpoint([copy, parent_pin, coil])
    assert "competing_physical_port_instances" not in endpoint["reason_codes"]
    assert "competing_physical_port_identities" not in endpoint["reason_codes"]
    assert copy.record_id not in endpoint["port_ids"]
    assert coil.record_id in endpoint["port_ids"]
    assert endpoint["competing_ports"] == []
    assert endpoint["value"] == "HHJB-V"


def test_copy_without_owner_record_is_kept():
    coil, copy, parent_pin = _coil_contact()
    endpoint = _endpoint([copy, parent_pin])
    assert copy.record_id in endpoint["port_ids"]


def test_unrelated_instances_at_one_contact_still_compete():
    left = _port("SW:F1:S1:/X:/X:M2:1", instance="/X", marker="M2", number="1", symbol_category="内部元件")
    right = _port("SW:F1:S1:/Y:/Y:M3:1", instance="/Y", marker="M3", number="1", symbol_category="内部元件")
    endpoint = _endpoint([left, right])
    assert "competing_physical_port_instances" in endpoint["reason_codes"]


def test_ancestor_descendant_with_different_identities_still_conflicts():
    coil = _port("SW:F1:S1:/A/B:/A/B:M1:1", instance="/A/B", marker="M1", number="1", symbol_category="线圈",
                 identity="1n5", definition="/A/B")
    parent_pin = _port("SW:F1:S1:/A:/A:P1:1", instance="/A", marker="P1", number="1", symbol_category="内部元件",
                       identity="HHJB-V", definition="/A")
    endpoint = _endpoint([coil, parent_pin])
    assert "competing_physical_port_identities" in endpoint["reason_codes"]


def test_ancestor_descendant_relation_is_path_prefix_not_substring():
    left = _port("a", instance="/A/B", marker="M", number="1", symbol_category="线圈")
    right = _port("b", instance="/A", marker="M", number="1", symbol_category="内部元件")
    other = _port("c", instance="/AB", marker="M", number="1", symbol_category="内部元件")
    assert _nested_instances(left, right)
    assert not _nested_instances(left, other)


# 3. A native component row takes the frame its connect stub ends on as its line group.

def _frame(group_id, *, x, y0, y1, layers=("BORDER",), sheet="S1"):
    return LineGroup(group_id, sheet, "F1", x, y0, x, y1, abs(y1 - y0), 0.5, layer_hints=list(layers),
                     orientation="vertical")


def test_stub_takes_the_single_border_frame_it_ends_on():
    frame = _frame("GC0069", x=159.460082, y0=163.127865, y1=193.127865)
    other = _frame("GC0070", x=159.690404, y0=234.517425, y1=264.517425)
    assert _frame_group_at_stub(_label(), [other, frame]) == "GC0069"


def test_stub_takes_no_frame_when_the_frame_is_not_border_only():
    frame = _frame("GL1", x=159.460082, y0=163.127865, y1=193.127865, layers=("BORDER", "TEXT"))
    assert _frame_group_at_stub(_label(), [frame]) is None


def test_stub_takes_no_frame_when_two_frames_meet_it():
    first = _frame("GC1", x=159.460082, y0=163.127865, y1=193.127865)
    second = _frame("GC2", x=159.460082, y0=180.0, y1=200.0)
    assert _frame_group_at_stub(_label(), [first, second]) is None


def test_stub_ignores_frames_of_another_sheet():
    frame = _frame("GC0069", x=159.460082, y0=163.127865, y1=193.127865, sheet="S9")
    assert _frame_group_at_stub(_label(), [frame]) is None


def test_native_row_is_owned_by_the_frame_it_ends_on_in_the_native_pass():
    data = SuperworksData(connect_labels=[_label()], part_instances=[_part()])
    frame = _frame("GC0069", x=159.460082, y0=163.127865, y1=193.127865)
    output, _, _ = extract_superworks_pairs(data, pages=[_page()], texts=[], lines=[], line_groups=[frame], pairs=[],
                                            table_mappings=[], native_only=True)
    rows = [p for p in output if (p.evidence or {}).get("component_submode") == NATIVE_SUBMODE]
    assert len(rows) == 1
    assert rows[0].line_group_id == "GC0069"
