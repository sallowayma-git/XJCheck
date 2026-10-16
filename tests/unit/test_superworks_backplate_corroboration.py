from __future__ import annotations

from dwg_audit.audit.superworks_extractor import (corroborate_backplate_virtual_pairs, _bp_identity,
                                                  _bp_device_matches)
from dwg_audit.domain.models import Pair


def _bp(pair_id="PV1", left="1-1n201", right="7n601", *, row=1, device="1-1n", sheet="S0009", file="F0009",
        status="pass", mode="backplate_virtual_table"):
    table = {"mapping_mode": mode, "row_number": row, "composite_device_instance": device,
             "header_prefix": "1-1n2", "sheet_no": "09", "filename": "09 装置背板.dwg",
             "header_text_id": "T0690", "middle_text_id": "T0741"}
    return Pair(pair_id=pair_id, line_group_id=None, sheet_id=sheet, file_id=file, selected_pair_candidate_id=None,
                left_value=left, right_value=right, confidence=0.95, status=status, rationale="fixture",
                evidence={"source": "table_mapping", "table_mapping": table}, right_text_id="T1364",
                pair_kind="table_mapping")


def _sw(pair_id="PSW1", left="7n601", right="7n205", *, sheet="S0009", file="F0009", status="pass"):
    return Pair(pair_id=pair_id, line_group_id="GWSW1", sheet_id=sheet, file_id=file, selected_pair_candidate_id=None,
                left_value=left, right_value=right, confidence=0.99, status=status, rationale="fixture",
                evidence={"source": "superworks"}, pair_kind="wire_component_mapping")


def _run(pairs):
    return corroborate_backplate_virtual_pairs(list(pairs))


def _by_id(pairs):
    return {pair.pair_id: pair for pair in pairs}


def test_identity_forms_parse_numeric_alpha_and_bay_forms():
    assert _bp_identity("1n0503") == {"device": "1n", "row": 3, "form": "numeric"}
    assert _bp_identity("3-21n532") == {"device": "3-21n", "row": 32, "form": "numeric"}
    assert _bp_identity("1-25nA24") == {"device": "1-25n", "row": 24, "form": "alpha"}
    assert _bp_identity("1nP103") == {"device": "1n", "row": 3, "form": "numeric"}
    assert _bp_identity("TD9") is None
    assert _bp_identity("1KLP8-2") is None


def test_device_match_ignores_only_one_sided_bay_prefix():
    assert _bp_device_matches("1n", "1-1n")
    assert _bp_device_matches("1-1n", "1nP")
    assert not _bp_device_matches("1-25n", "1n")
    assert not _bp_device_matches("1-1n", "2-1n")


def test_row_terminal_device_agreement_adds_evidence_and_keeps_status():
    v1 = _bp(row=5, device="1-1n", right="TD9")
    sw = _sw(left="TD9", right="1n0505")
    out, cands = _run([v1, sw])
    pair = _by_id(out)["PV1"]
    assert pair.status == "pass"
    assert pair.evidence["sw_backplate_corroboration"]["sw_pair_id"] == "PSW1"
    assert pair.evidence["sw_backplate_corroboration"]["match"] == "row+terminal+device"
    assert pair.evidence["sw_backplate_corroboration"]["same_sheet"] is True
    assert cands == []


def test_agreement_across_sheets_is_corroborated_but_marked_other_sheet():
    v1 = _bp(row=5, device="1-1n", right="TD9")
    sw = _sw(left="TD9", right="1n0505", sheet="S0031", file="F0031")
    out, cands = _run([v1, sw])
    assert _by_id(out)["PV1"].evidence["sw_backplate_corroboration"]["same_sheet"] is False
    assert cands == []


def test_same_row_different_device_is_a_candidate_not_evidence():
    v1 = _bp(row=1, device="1-1n", right="7n601")
    sw = _sw(left="7n601", right="7n101")
    out, cands = _run([v1, sw])
    pair = _by_id(out)["PV1"]
    assert pair.status == "pass"
    assert "sw_backplate_corroboration" not in pair.evidence
    assert [c["contradiction_type"] for c in cands] == ["device_prefix_differs"]
    cand = cands[0]
    assert cand["pair_id"] == "PV1" and cand["sw_identity"] == "7n101"
    assert cand["v1_row"] == 1 and cand["sw_row"] == 1 and cand["sw_same_sheet"] is True


def test_same_sheet_row_conflict_with_equal_device_is_a_candidate():
    v1 = _bp(row=2, device="1-7n", right="1-7QD9")
    sw = _sw(left="1-7QD9", right="1-7n832")
    out, cands = _run([v1, sw])
    assert _by_id(out)["PV1"].status == "pass"
    assert [c["contradiction_type"] for c in cands] == ["same_sheet_row_conflict"]
    assert cands[0]["sw_row"] == 32 and cands[0]["v1_row"] == 2


def test_other_sheet_row_conflict_is_not_flagged():
    v1 = _bp(row=2, device="1-7n", right="1-7QD9")
    sw = _sw(left="1-7QD9", right="1-7n832", sheet="S0031", file="F0031")
    _, cands = _run([v1, sw])
    assert cands == []


def test_non_backplate_partner_gives_nothing():
    v1 = _bp(row=5, device="1-1n", right="TD9")
    sw = _sw(left="TD9", right="ZD2")
    out, cands = _run([v1, sw])
    assert "sw_backplate_corroboration" not in _by_id(out)["PV1"].evidence
    assert cands == []


def test_legacy_partner_is_not_used():
    v1 = _bp(row=5, device="1-1n", right="TD9")
    legacy = _sw(left="TD9", right="1n0505")
    legacy.evidence = {"pair_kind": "wire_component_mapping"}
    out, cands = _run([v1, legacy])
    assert "sw_backplate_corroboration" not in _by_id(out)["PV1"].evidence
    assert cands == []


def test_pair_without_composite_device_is_not_judged():
    v1 = _bp(row=5, device=None, right="TD9")
    sw = _sw(left="TD9", right="7n105")
    out, cands = _run([v1, sw])
    assert "sw_backplate_corroboration" not in _by_id(out)["PV1"].evidence
    assert cands == []


def test_non_pass_or_non_backplate_v1_pairs_are_ignored():
    review = _bp("PV2", row=5, device="1-1n", right="TD9", status="review")
    other_mode = _bp("PV3", row=5, device="1-1n", right="TD9", mode="terminal_header_table")
    sw = _sw(left="TD9", right="7n105")
    out, cands = _run([review, other_mode, sw])
    assert all("sw_backplate_corroboration" not in p.evidence for p in out if p.pair_id != "PSW1")
    assert cands == []


def test_discarded_or_review_sw_pair_does_not_corroborate():
    v1 = _bp(row=5, device="1-1n", right="TD9")
    sw = _sw(left="TD9", right="1n0505", status="review")
    out, cands = _run([v1, sw])
    assert "sw_backplate_corroboration" not in _by_id(out)["PV1"].evidence
    assert cands == []


def test_prefers_same_sheet_corroboration_when_several_partners_agree():
    v1 = _bp(row=5, device="1-1n", right="TD9")
    other = _sw("PSW_A", left="TD9", right="1n0505", sheet="S0031", file="F0031")
    same = _sw("PSW_Z", left="TD9", right="1n0505")
    out, _ = _run([v1, other, same])
    corr = _by_id(out)["PV1"].evidence["sw_backplate_corroboration"]
    assert corr["sw_pair_id"] == "PSW_Z" and corr["partner_count"] == 2


def test_at_sign_and_spaces_are_ignored_when_matching_terminal():
    v1 = _bp(row=5, device="1-1n", right="@ TD9")
    sw = _sw(left="TD9", right="1n0505")
    out, _ = _run([v1, sw])
    assert _by_id(out)["PV1"].evidence["sw_backplate_corroboration"]["sw_pair_id"] == "PSW1"


def test_no_sw_pairs_returns_input_unchanged():
    v1 = _bp()
    out, cands = _run([v1])
    assert out == [v1] and cands == []


def test_same_sheet_row_conflict_is_superseded_as_category_J_and_device_conflict_is_not():
    from dwg_audit.audit.superworks_extractor import supersede_backplate_row_misreads
    row_v1 = _bp("PR1", row=2, device="1-7n", right="1-7QD9")
    row_sw = _sw("PSWR", left="1-7QD9", right="1-7n832")
    dev_v1 = _bp("PD1", row=1, device="1-1n", right="7n601", sheet="S0010")
    dev_sw = _sw("PSWD", left="7n601", right="7n101", sheet="S0010")
    pairs, cands = corroborate_backplate_virtual_pairs([row_v1, row_sw, dev_v1, dev_sw])
    out, ledger = supersede_backplate_row_misreads(pairs, [], cands)
    by = _by_id(out)
    assert by["PR1"].status == "discard"
    ev = by["PR1"].evidence
    assert ev["supersession_category"] == "J"
    assert ev["superseded_by"] == "PSWR" and ev["superseded_by_all"] == ["PSWR"]
    assert ev["backplate_row_misread"]["sw_row"] == 32 and ev["backplate_row_misread"]["v1_row"] == 2
    assert by["PR1"].rationale.startswith("backplate_row_misread_superseded_by_same_sheet_sw")
    assert [e["category"] for e in ledger] == ["J"]
    assert ledger[0]["old_pair"]["pair_id"] == "PR1"
    assert by["PD1"].status == "pass"
    assert "supersession_category" not in by["PD1"].evidence
    actions = {c["contradiction_type"]: c["action"] for c in cands}
    assert actions == {"same_sheet_row_conflict": "superseded_category_J", "device_prefix_differs": "candidate_only"}


def test_row_misread_supersession_raises_no_issue_and_keeps_no_review_status():
    from dwg_audit.audit.superworks_extractor import supersede_backplate_row_misreads
    row_v1 = _bp("PR1", row=2, device="1-7n", right="1-7QD9")
    row_sw = _sw("PSWR", left="1-7QD9", right="1-7n832")
    pairs, cands = corroborate_backplate_virtual_pairs([row_v1, row_sw])
    out, _ = supersede_backplate_row_misreads(pairs, [], cands)
    assert all(p.status != "review" for p in out)
    import dwg_audit.audit.superworks_extractor as ext
    assert not hasattr(ext, "build_backplate_row_conflict_issues")


def test_no_row_conflict_means_no_supersession():
    from dwg_audit.audit.superworks_extractor import supersede_backplate_row_misreads
    v1 = _bp(row=5, device="1-1n", right="TD9")
    sw = _sw(left="TD9", right="1n0505")
    pairs, cands = corroborate_backplate_virtual_pairs([v1, sw])
    out, ledger = supersede_backplate_row_misreads(pairs, [], cands)
    assert _by_id(out)["PV1"].status == "pass"
    assert cands == [] and ledger == []


def _text(text_id, value, x=0.0, y=0.0, block=None, *, dxf_visible=None):
    from dwg_audit.domain.models import TextItem
    return TextItem(text_id=text_id, sheet_id="S1", file_id="F1", handle=text_id, entity_type="TEXT",
                    text=value, normalized_text=value, is_numeric_candidate=False, layer="0", rotation_deg=0.0,
                    height=2.5, insert_x=x, insert_y=y, bbox_min_x=x, bbox_min_y=y, bbox_max_x=x + 1,
                    bbox_max_y=y + 1, source_block_name=block, dxf_visible=dxf_visible)


def _sheet(title="4000908886-016000", filename="14 操作箱背板接线图.dwg"):
    from dwg_audit.domain.models import SheetRecord
    return SheetRecord(sheet_id="S1", file_id="F1", filename=filename, sheet_order=14, sheet_no="14",
                       sheet_title=title, sheet_category="背板接线图", audit_role="audit", page_no_source="x",
                       is_primary_audit_candidate=True)


def test_rear_wiring_caption_outranks_template_device_field():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    template = _text("T1", "1-8n", 210.3, 281.5)
    caption = _text("T2", "4n REAR WIRING", 318.5, 9.8)
    assert _resolve_backplate_device_instance([template], _sheet(), page_texts=[template, caption]) == "4n"


def test_rear_wiring_caption_with_index_suffix_is_recognised():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    template = _text("T1", "1-1n", 210.3, 281.5)
    caption = _text("T2", "4n REAR WIRING 2", 317.2, 9.8)
    assert _resolve_backplate_device_instance([template], _sheet(), page_texts=[caption]) == "4n"


def test_no_caption_keeps_existing_template_resolution():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    template = _text("T1", "1-1n", 210.3, 281.5)
    other = _text("T3", "REAR WIRING", 320.4, 9.8)
    assert _resolve_backplate_device_instance([template], _sheet(), page_texts=[other]) == "1-1n"


def test_caption_without_device_or_with_conflicting_captions_is_ignored():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    template = _text("T1", "1-1n", 210.3, 281.5)
    two = [_text("T2", "4n REAR WIRING 1", 317.2, 9.8), _text("T3", "7n REAR WIRING 2", 317.2, 9.8)]
    assert _resolve_backplate_device_instance([template], _sheet(), page_texts=two) == "1-1n"
    assert _resolve_backplate_device_instance([template], _sheet(), page_texts=[_text("T4", "REAR WIRING")]) == "1-1n"


def test_sheet_title_still_outranks_caption():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    caption = _text("T2", "4n REAR WIRING", 318.5, 9.8)
    assert _resolve_backplate_device_instance([], _sheet(title="1-25n REAR WIRING"), page_texts=[caption]) == "1-25n"


def test_template_that_agrees_with_caption_is_kept_as_written():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    template = _text("T1", "1-8n", 210.3, 281.5)
    caption = _text("T2", "8n REAR WIRING", 318.5, 9.8)
    assert _resolve_backplate_device_instance([template], _sheet(), page_texts=[caption]) == "1-8n"
    assert _resolve_backplate_device_instance([template], _sheet(), page_texts=[_text("T3", "4n REAR WIRING", 318.5, 9.8)]) == "4n"


def _standalone_rear_wiring_fixture(*, device="7n", model="ZYQ-820E-02", device_visibility=True,
                                    model_visibility=True, heading_visibility=True, model_x=213.86,
                                    model_y=264.63):
    hidden_template = _text("T1", "1-1n", 210.3, 281.5, dxf_visible=False)
    visible_device = _text("T2", device, 221.10, 268.40, dxf_visible=device_visibility)
    model_text = _text("T3", model, model_x, model_y, dxf_visible=model_visibility)
    heading = _text("T4", "REAR WIRING", 320.37, 9.78, dxf_visible=heading_visibility)
    return [hidden_template, visible_device, model_text], [hidden_template, visible_device, model_text, heading]


def test_standalone_rear_wiring_uses_unique_visible_device_and_adjacent_model():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    free_texts, page_texts = _standalone_rear_wiring_fixture()

    assert _resolve_backplate_device_instance(free_texts, _sheet(), page_texts=page_texts) == "7n"


def test_standalone_rear_wiring_fallback_requires_visible_heading_and_model_pair():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    free_texts, page_texts = _standalone_rear_wiring_fixture()

    assert _resolve_backplate_device_instance(free_texts, _sheet(), page_texts=page_texts[:-1]) is None
    assert _resolve_backplate_device_instance(
        free_texts, _sheet(), page_texts=[*page_texts[:-1], _text("T4", "REAR WIRING", 320.37, 9.78,
                                                                 dxf_visible=False)]
    ) is None
    distant = _standalone_rear_wiring_fixture(model_x=250.0, model_y=250.0)
    assert _resolve_backplate_device_instance(distant[0], _sheet(), page_texts=distant[1]) is None
    hidden_model = _standalone_rear_wiring_fixture(model_visibility=False)
    assert _resolve_backplate_device_instance(hidden_model[0], _sheet(), page_texts=hidden_model[1]) is None


def test_standalone_rear_wiring_fallback_rejects_ambiguous_or_unknown_evidence():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    free_texts, page_texts = _standalone_rear_wiring_fixture()
    ambiguous = [*free_texts, _text("T5", "8n", 240.0, 240.0, dxf_visible=True)]
    assert _resolve_backplate_device_instance(ambiguous, _sheet(), page_texts=page_texts) is None

    unknown = _standalone_rear_wiring_fixture(device_visibility=None, model_visibility=None,
                                               heading_visibility=None)
    assert _resolve_backplate_device_instance(unknown[0], _sheet(), page_texts=unknown[1]) is None


def test_standalone_rear_wiring_does_not_replace_a_visible_compound_template():
    from dwg_audit.audit.table_extractor import _resolve_backplate_device_instance
    free_texts, page_texts = _standalone_rear_wiring_fixture()
    visible_template = _text("T6", "2-4n", 205.0, 285.0, dxf_visible=True)

    assert _resolve_backplate_device_instance([*free_texts, visible_template], _sheet(),
                                              page_texts=page_texts) == "2-4n"
