from __future__ import annotations

from dwg_audit.audit.superworks_extractor import supersede_legacy_duplicates_of_sw
from dwg_audit.domain.models import Pair


def _pair(pair_id, left, right, *, sheet="S0001", file="F0001", status="pass", evidence=None,
          kind="wire_component_mapping", left_text="T1", right_text="T2"):
    return Pair(
        pair_id=pair_id, line_group_id="GW1", sheet_id=sheet, file_id=file,
        selected_pair_candidate_id=None, left_value=left, right_value=right,
        confidence=0.9, status=status, rationale="fixture", confidence_bucket="high",
        evidence=dict(evidence or {}), left_text_id=left_text, right_text_id=right_text,
        pair_key=f"{left}->{right}", pair_kind=kind,
    )


def _legacy(pair_id="PW_LEG", left="1A3", right="2B7", **kwargs):
    kwargs.setdefault("evidence", {"pair_kind": "wire_component_mapping"})
    return _pair(pair_id, left, right, **kwargs)


def _sw(pair_id="PW_SW", left="1A3", right="2B7", **kwargs):
    kwargs.setdefault("evidence", {"source": "superworks", "pair_kind": "wire_component_mapping"})
    return _pair(pair_id, left, right, **kwargs)


def _run(pairs, ledger=None):
    return supersede_legacy_duplicates_of_sw(list(pairs), list(ledger or []))


def _by_id(pairs):
    return {pair.pair_id: pair for pair in pairs}


def test_legacy_pass_repeated_by_same_sheet_sw_pass_is_discarded_with_ledger_entry():
    sw = _sw()
    legacy = _legacy()
    kept, ledger = _run([legacy, sw])
    out = _by_id(kept)
    assert out["PW_LEG"].status == "discard"
    assert out["PW_LEG"].evidence["superseded_by"] == "PW_SW"
    assert out["PW_LEG"].evidence["superseded_by_all"] == ["PW_SW"]
    assert out["PW_LEG"].evidence["supersession_category"] == "I"
    assert out["PW_LEG"].rationale.startswith("legacy_pair_duplicates_same_sheet_sw_pass")
    assert out["PW_SW"] == sw
    assert len(ledger) == 1
    entry = ledger[0]
    assert entry["category"] == "I"
    assert entry["element_key"] == "legacy_duplicate:S0001:PW_LEG"
    assert entry["old_pair"]["pair_id"] == "PW_LEG"
    assert entry["old_pair"]["status"] == "pass"
    assert [p["pair_id"] for p in entry["new_pairs"]] == ["PW_SW"]


def test_crossed_orientation_is_the_same_connection():
    legacy = _legacy(left="2B7", right="1A3")
    sw = _sw(left="1A3", right="2B7")
    kept, ledger = _run([legacy, sw])
    assert _by_id(kept)["PW_LEG"].status == "discard"
    assert len(ledger) == 1


def test_review_legacy_pair_is_also_retired():
    kept, ledger = _run([_legacy(status="review"), _sw()])
    assert _by_id(kept)["PW_LEG"].status == "discard"
    assert ledger[0]["old_pair"]["status"] == "review"


def test_other_sheet_does_not_supersede():
    kept, ledger = _run([_legacy(sheet="S0002"), _sw(sheet="S0001")])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_other_file_on_same_sheet_id_does_not_supersede():
    kept, ledger = _run([_legacy(file="F0002"), _sw(file="F0001")])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_partial_match_with_one_different_end_is_kept():
    kept, ledger = _run([_legacy(right="9Z9"), _sw()])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_legacy_with_extra_end_is_kept():
    # One-sided legacy pair (missing right end) has an endpoint SuperWORKS does not repeat.
    kept, ledger = _run([_legacy(right=None), _sw()])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_sw_pair_with_extra_end_is_not_a_superseder_for_a_partial_legacy():
    kept, ledger = _run([_legacy(right=None), _sw(right=None, left="1A3")])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_wider_legacy_range_is_partial_and_kept():
    kept, ledger = _run([_legacy(left="1-7UD20~21"), _sw(left="1-7UD21")])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_wider_sw_range_is_partial_and_legacy_kept():
    kept, ledger = _run([_legacy(left="1-7UD21"), _sw(left="1-7UD20~21")])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_letter_prefix_on_one_side_only_is_kept():
    kept, ledger = _run([_legacy(left="1A7UD21"), _sw(left="7UD21")])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_normalization_strips_sw_decoration_and_matches():
    kept, ledger = _run([_legacy(left="1n2107"), _sw(left="* 1n2107")])
    assert _by_id(kept)["PW_LEG"].status == "discard"
    assert len(ledger) == 1


def test_alias_recorded_on_sw_end_matches_the_legacy_text():
    sw = _sw(left="X1", evidence={"source": "superworks", "superworks": {
        "left": {"value": "X1", "endpoint_aliases": ["Y1"]}}})
    kept, ledger = _run([_legacy(left="Y1"), sw])
    assert _by_id(kept)["PW_LEG"].status == "discard"
    assert len(ledger) == 1


def test_alias_belonging_to_another_value_is_ignored():
    sw = _sw(left="X1", evidence={"source": "superworks", "superworks": {
        "left": {"value": "OTHER", "endpoint_aliases": ["Y1"]}}})
    kept, ledger = _run([_legacy(left="Y1"), sw])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_legacy_with_superworks_evidence_is_not_pure_and_is_kept():
    for key in ("superworks", "superworks_constraints", "sw_conflicts", "sw_dictionary_warnings"):
        legacy = _legacy(evidence={"pair_kind": "wire_component_mapping", key: [{"x": 1}]})
        kept, ledger = _run([legacy, _sw()])
        assert _by_id(kept)["PW_LEG"].status == "pass", key
        assert ledger == [], key


def test_legacy_pair_already_in_ledger_is_kept():
    existing = [{"element_key": "earlier", "category": "B", "reason": "x",
                 "old_pair": {"pair_id": "PW_LEG"}, "new_pairs": []}]
    kept, ledger = _run([_legacy(), _sw()], existing)
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert len(ledger) == 1


def test_legacy_pair_that_is_a_ledger_new_pair_is_kept():
    existing = [{"element_key": "earlier", "category": "B", "reason": "x",
                 "old_pair": {}, "new_pairs": [{"pair_id": "PW_LEG"}]}]
    kept, ledger = _run([_legacy(), _sw()], existing)
    assert _by_id(kept)["PW_LEG"].status == "pass"


def test_sw_review_pair_is_not_a_superseder():
    kept, ledger = _run([_legacy(), _sw(status="review")])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_legacy_superseded_by_sw_component_row():
    sw_row = _pair("PW_CMP", "1A3", "2B7", kind="component_mapping",
                   evidence={"source": "component_mapping", "component_submode": "superworks_connect_line_port",
                             "superworks": {"source": "superworks", "port_number": "1"}})
    kept, ledger = _run([_legacy(), sw_row])
    out = _by_id(kept)
    assert out["PW_LEG"].status == "discard"
    assert out["PW_LEG"].evidence["superseded_by"] == "PW_CMP"
    assert out["PW_CMP"].status == "pass"


def test_pure_legacy_component_mapping_is_not_treated_as_sw():
    legacy_cmp = _pair("PW_LCMP", "1A3", "2B7", kind="component_mapping",
                       evidence={"source": "component_mapping", "component_submode": "strip_two_port_component"})
    kept, ledger = _run([_legacy(), legacy_cmp])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_ignored_panel_owned_legacy_pair_is_kept():
    legacy = _legacy(evidence={"pair_kind": "wire_component_mapping", "ignored_panel_family_id": "PANEL1"})
    kept, ledger = _run([legacy, _sw()])
    assert _by_id(kept)["PW_LEG"].status == "pass"
    assert ledger == []


def test_discarded_legacy_pair_is_left_untouched():
    kept, ledger = _run([_legacy(status="discard"), _sw()])
    assert _by_id(kept)["PW_LEG"].status == "discard"
    assert "superseded_by" not in _by_id(kept)["PW_LEG"].evidence
    assert ledger == []


def test_multiple_sw_twins_record_the_first_pair_id_and_all_of_them():
    kept, ledger = _run([_legacy(), _sw(pair_id="PW_SW_B"), _sw(pair_id="PW_SW_A")])
    out = _by_id(kept)
    assert out["PW_LEG"].evidence["superseded_by"] == "PW_SW_A"
    assert out["PW_LEG"].evidence["superseded_by_all"] == ["PW_SW_A", "PW_SW_B"]
    assert [p["pair_id"] for p in ledger[0]["new_pairs"]] == ["PW_SW_A", "PW_SW_B"]


def test_no_sw_pass_pairs_returns_inputs_unchanged():
    legacy = _legacy()
    pairs = [legacy]
    ledger = [{"element_key": "earlier"}]
    out, out_ledger = supersede_legacy_duplicates_of_sw(pairs, ledger)
    assert out == pairs
    assert out_ledger is ledger
    assert out[0].status == "pass"


def test_evidence_of_the_input_pair_is_not_mutated():
    legacy = _legacy()
    before = dict(legacy.evidence)
    _run([legacy, _sw()])
    assert legacy.evidence == before
    assert legacy.status == "pass"
