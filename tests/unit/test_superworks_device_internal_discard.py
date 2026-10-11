"""DEV-INT-DISCARD: the device-internal rule as one verdict, and its pair-layer discard (silent, no issue)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from dwg_audit.audit.superworks_device_internal import DEVICE_INTERNAL, device_internal_verdict
from dwg_audit.audit.superworks_extractor import (
    DEVICE_INTERNAL_DISCARD,
    _discard_device_internal_pairs,
    build_superworks_issues,
)
from dwg_audit.domain.models import Pair, SwPort


def _label(text, resolved=True):
    return {"normalized": text, "resolved": resolved, "value": text}


def _terminal(identity="1n705", label="1n", resolved=True, category="装置端子"):
    return {"category": category, "identity": identity, "label": label, "label_resolved": resolved}


def _other(category="内部元件", label="1n", resolved=True, unregistered=False):
    return {"category": category, "label": label, "label_resolved": resolved, "unregistered": unregistered}


# --- the verdict -----------------------------------------------------------------------------------------------

def test_verdict_accepts_own_internal_element_and_own_unregistered_pin():
    assert device_internal_verdict(_terminal(), _other()) == DEVICE_INTERNAL
    assert device_internal_verdict(_terminal(), _other(category="线圈")) == DEVICE_INTERNAL
    assert device_internal_verdict(_terminal(), _other(category="", unregistered=True)) == DEVICE_INTERNAL


@pytest.mark.parametrize("terminal, other, reason", [
    (_terminal(category="端子"), _other(), "terminal_not_device"),
    (_terminal(resolved=False), _other(), "terminal_label_unresolved"),
    (_terminal(identity="1n"), _other(), "terminal_identity_not_label_prefixed"),
    (_terminal(identity="2n705"), _other(), "terminal_identity_not_label_prefixed"),
    (_terminal(), _other(category="端子"), "other_end_category:端子"),
    (_terminal(), _other(category=""), "other_end_category:none"),
    (_terminal(), _other(label="", resolved=False), "other_label_unresolved"),
    (_terminal(), _other(label="1-1n"), "other_label_related"),
    (_terminal(), _other(label="2n"), "other_label_differs"),
])
def test_verdict_names_the_first_reason_it_is_not_internal(terminal, other, reason):
    assert device_internal_verdict(terminal, other) == reason


def test_verdict_label_comparison_is_casefold_exact():
    assert device_internal_verdict(_terminal(identity="1N705", label="1N"), _other(label="1n")) == DEVICE_INTERNAL


# --- the pair layer -------------------------------------------------------------------------------------------

def _port(record_id, category, *, identity=None, label="1n", contacts=("W1",)):
    return SwPort(record_id=record_id, sheet_id="S1", file_id="F1", insert_handle=record_id.upper(), port_number="1",
                  category=category, endpoint_identity=identity, label=_label(label),
                  wire_contacts=[{"wire_handle": handle, "wire_side": 0} for handle in contacts])


def _pair(pair_id, left, right, *, status="pass", kind="wire_component_mapping", sw_conflicts=(), extra=None):
    """left/right: (value, sw side dict). The evidence carries SuperWORKS sides, as the producers write them."""
    evidence = {"source": "superworks", "superworks": {"left": left[1], "right": right[1]},
                "sw_conflicts": list(sw_conflicts), **(extra or {})}
    return Pair(pair_id=pair_id, line_group_id="GW1", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                left_value=left[0], right_value=right[0], confidence=0.9, status=status, rationale="r",
                evidence=evidence, pair_kind=kind)


def _sw(value, category, port_ids, **extra):
    return (value, {"value": value, "category": category, "port_ids": list(port_ids), **extra})


def _data(*ports):
    return SimpleNamespace(ports=list(ports))


def test_pass_pair_between_own_device_terminal_and_internal_element_is_discarded():
    data = _data(_port("D1", "装置端子", identity="1n705"), _port("Q1", "内部元件", identity="1n-DC"))
    pair = _pair("P1", _sw("1n705", "装置端子", ["D1"]), _sw("1n-DC", "内部元件", ["Q1"]))
    output = [pair]
    stats = _discard_device_internal_pairs(output, data)
    new = output[0]
    assert new.status == "discard"
    assert new.evidence["discard_reason"] == DEVICE_INTERNAL_DISCARD
    detail = new.evidence["device_internal_discard"]
    assert detail["status_before"] == "pass"
    assert detail["terminal_identity"] == "1n705" and detail["terminal_port_ids"] == ["D1"]
    assert detail["other_identity"] == "1n-DC" and detail["other_port_ids"] == ["Q1"]
    assert detail["other_unregistered"] is False
    assert stats == {"discarded:pass": 1, "discarded:pass:wire_component_mapping": 1}
    # The original pair is untouched (the discard is a new Pair).
    assert pair.status == "pass" and "discard_reason" not in pair.evidence


def test_bare_number_pair_value_still_reads_the_port_identity():
    # An ordinary pair names the terminal by its bare number ("719"); the port's identity is "1n719".
    data = _data(_port("D1", "装置端子", identity="1n719"), _port("Q1", "内部元件", identity=None))
    pair = Pair(pair_id="P8", line_group_id="GW3", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                left_value="707", right_value="719", confidence=0.4, status="review", rationale="r",
                evidence={"source": "superworks", "superworks": {
                    "left": {"value": None, "category": "内部元件", "port_ids": ["Q1"]},
                    "right": {"value": "1n719", "category": "装置端子", "port_ids": ["D1"]}}},
                pair_kind="ordinary_pair")
    output = [pair]
    _discard_device_internal_pairs(output, data)
    assert output[0].status == "discard"
    detail = output[0].evidence["device_internal_discard"]
    assert detail["terminal_identity"] == "1n719" and detail["other_identity"] == "707"


def test_review_pair_to_an_unregistered_pin_of_the_same_device_is_discarded():
    data = _data(_port("D1", "装置端子", identity="1n705"))
    slot = [{"identity": "1n-2", "record_device": "1n", "identity_source": "symb2_text_slot"}]
    pair = _pair("P2", _sw("1n705", "装置端子", ["D1"]),
                 ("1n-2", {"value": "1n-2", "category": "", "port_ids": [], "identity_source": "symb2_text_slot"}),
                 status="review", extra={"symb2_text_slot": slot})
    output = [pair]
    _discard_device_internal_pairs(output, data)
    assert output[0].status == "discard"
    assert output[0].evidence["device_internal_discard"]["other_unregistered"] is True
    assert output[0].evidence["device_internal_discard"]["other_label"] == "1n"


@pytest.mark.parametrize("left, right", [
    # other end is another device's internal element (label differs / related)
    (_sw("1n705", "装置端子", ["D1"]), _sw("2n-DC", "内部元件", ["Q2"])),
    (_sw("1n705", "装置端子", ["D1"]), _sw("1-1n-DC", "内部元件", ["Q3"])),
    # other end is a terminal strip terminal, or another device terminal
    (_sw("1n705", "装置端子", ["D1"]), _sw("1QD5", "端子", ["T1"])),
    (_sw("1n705", "装置端子", ["D1"]), _sw("1n706", "装置端子", ["D4"])),
    # the device-terminal end is a terminal strip terminal
    (_sw("1n705", "端子", ["T9"]), _sw("1n-DC", "内部元件", ["Q1"])),
])
def test_pairs_that_are_not_device_internal_are_kept(left, right):
    data = _data(_port("D1", "装置端子", identity="1n705"), _port("Q1", "内部元件", identity="1n-DC"),
                 _port("Q2", "内部元件", identity="2n-DC", label="2n"), _port("Q3", "内部元件", identity="1-1n-DC", label="1-1n"),
                 _port("T1", "端子", identity="1QD5", label="1QD"), _port("D4", "装置端子", identity="1n706"),
                 _port("T9", "端子", identity="1n705", label="1n"))
    output = [_pair("P3", left, right)]
    stats = _discard_device_internal_pairs(output, data)
    assert output[0].status == "pass"
    assert "discard_reason" not in output[0].evidence
    assert not any(key.startswith("discarded:") for key in stats)


def test_discard_pairs_and_pairs_without_superworks_sides_are_left_alone():
    data = _data(_port("D1", "装置端子", identity="1n705"), _port("Q1", "内部元件", identity="1n-DC"))
    done = _pair("P4", _sw("1n705", "装置端子", ["D1"]), _sw("1n-DC", "内部元件", ["Q1"]), status="discard")
    plain = Pair(pair_id="P5", line_group_id="GW2", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                 left_value="1n705", right_value="1n-DC", confidence=0.5, status="review", rationale="r",
                 evidence={}, pair_kind="ordinary_pair")
    output = [done, plain]
    _discard_device_internal_pairs(output, data)
    assert output[0] is done and output[1].status == "review"


def test_discarded_pair_raises_no_superworks_issue_even_with_a_true_conflict():
    conflict = ["competing_physical_port_identities"]
    discarded = _pair("P6", _sw("1n705", "装置端子", ["D1"]), _sw("1n-DC", "内部元件", ["Q1"]),
                      status="discard", sw_conflicts=conflict,
                      extra={"discard_reason": DEVICE_INTERNAL_DISCARD})
    live = _pair("P7", _sw("1n706", "装置端子", ["D4"]), _sw("1n-DD", "内部元件", ["Q4"]),
                 status="pass", sw_conflicts=conflict)

    class _Factory:
        def build(self, rule_id, severity, pair, message, **kwargs):
            return {"rule": rule_id, "pair": pair.pair_id}

    issues = build_superworks_issues(SimpleNamespace(pairs=[discarded, live], issue_factory=_Factory()))
    assert [issue["pair"] for issue in issues] == ["P7"]


def test_external_pair_overrules_a_wire_level_device_internal_link(tmp_path):
    """A terminal on a wire that also reaches a foreign pin: its non-discard pair is external, so it stays covered."""
    from dwg_audit.domain.models import SheetRecord
    from dwg_audit.extract.superworks_semantics import SuperworksData
    from dwg_audit.report.superworks_artifacts import write_superworks_artifacts
    import pandas as pd

    page = SheetRecord("S1", "F1", "01 x.dwg", 1, "01", "x", "二次原理图", "primary", "filename", True,
                       audit_disposition="audit")
    device = SwPort(record_id="D1", sheet_id="S1", file_id="F1", insert_handle="HD", port_number="1",
                    category="装置端子", endpoint_identity="1n705", label=_label("1n"),
                    wire_contacts=[{"wire_handle": "W1", "wire_side": 0}])
    element = SwPort(record_id="Q1", sheet_id="S1", file_id="F1", insert_handle="HQ", port_number="1",
                     category="内部元件", endpoint_identity=None, label=_label("1n"),
                     wire_contacts=[{"wire_handle": "W1", "wire_side": 1}])
    data = SuperworksData(ports=[device, element])
    line = SimpleNamespace(file_id="F1", line_id="L1", handle="W1", source_block_name=None,
                           start_x=0.0, start_y=0.0, end_x=1.0, end_y=0.0)
    group = SimpleNamespace(file_id="F1", member_line_ids=["L1"])
    external = Pair(pair_id="PX", line_group_id="GW9", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                    left_value="1n705", right_value="1KLP3-2", confidence=0.9, status="review", rationale="r",
                    evidence={"source": "superworks", "superworks": {
                        "left": {"value": "1n705", "category": "装置端子", "port_ids": ["D1"]},
                        "right": {"value": "1KLP3-2", "category": "", "port_ids": []}}},
                    pair_kind="wire_component_mapping")
    artifacts = SimpleNamespace(superworks=data, superworks_supersession=[], lines=[line], line_groups=[group],
                                scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"), pages=[page]),
                                pairs=[external])
    write_superworks_artifacts(artifacts, tmp_path)
    summary = json.loads((tmp_path / "superworks_summary.json").read_text(encoding="utf-8"))
    assert summary["device_internal"]["overruled_by_external_pair_ports"] == 1
    assert summary["device_internal"]["excluded_device_internal_ports"] == 0
    assert summary["coverage_views"]["strict"]["consumed"] == 1
    assert summary["coverage_views"]["strict_excl_device_internal"]["eligible"] == 1
    coverage = pd.read_parquet(tmp_path / "sw_port_coverage.parquet").set_index("port_id")
    assert bool(coverage.loc["D1", "consumed"]) and bool(coverage.loc["D1", "device_internal_overruled"])
    assert not bool(coverage.loc["D1", "excluded_device_internal"])


# --- terminal-form identities (DEV-INT-DISCARD correction) ----------------------------------------------------

from dwg_audit.audit.superworks_device_internal import (  # noqa: E402
    build_device_internal_links,
    is_terminal_form,
)


@pytest.mark.parametrize("identity, label, expected", [
    ("1-21n332", "1-21n", True),     # device label + pure-digit pin: a terminal
    ("1n705", "1n", True),
    ("1n-DC", "1n", False),          # a dash separates a function name: an element pin
    ("3-4n-I", "3-4n", False),
    ("1n-3", "1n", False),           # label-digit pin: an element pin
    ("2n705", "1n", False),          # other device
    ("1n", "1n", False),             # no pin number
    ("1n70A", "1n", False),
    ("707", "1n", False),            # bare number: no device label, not terminal-form
    ("", "1n", False),
])
def test_terminal_form_is_device_label_plus_pure_digits(identity, label, expected):
    assert is_terminal_form(identity, label) is expected


def test_element_with_terminal_form_identity_is_not_internal_but_element_forms_are():
    terminal = {"category": "装置端子", "identity": "1-21n331", "label": "1-21n", "label_resolved": True}
    assert device_internal_verdict(terminal, {"category": "内部元件", "label": "1-21n", "label_resolved": True,
                                              "identity": "1-21n332"}) == "other_identity_terminal_form"
    assert device_internal_verdict(terminal, {"category": "内部元件", "label": "1-21n", "label_resolved": True,
                                              "identity": "1-21n-DC"}) == DEVICE_INTERNAL
    assert device_internal_verdict(terminal, {"category": "内部元件", "label": "1-21n", "label_resolved": True,
                                              "identity": None}) == DEVICE_INTERNAL


def test_coil_and_unregistered_pin_are_internal_whatever_their_identity():
    terminal = {"category": "装置端子", "identity": "1n705", "label": "1n", "label_resolved": True}
    coil = {"category": "线圈", "label": "1n", "label_resolved": True, "identity": "1n706"}
    pin = {"category": "", "label": "1n", "label_resolved": True, "unregistered": True, "identity": "1n706"}
    assert device_internal_verdict(terminal, coil) == DEVICE_INTERNAL
    assert device_internal_verdict(terminal, pin) == DEVICE_INTERNAL


def test_pair_to_a_terminal_form_element_is_kept_and_an_element_form_pair_is_discarded():
    data = _data(_port("D1", "装置端子", identity="1-21n331", label="1-21n"),
                 _port("Q1", "内部元件", identity=None, label="1-21n"),
                 _port("Q2", "内部元件", identity=None, label="1-21n"))
    terminal_form = _pair("PT1", _sw("1-21n331", "装置端子", ["D1"]), _sw("1-21n332", "内部元件", ["Q1"]))
    element_form = _pair("PE1", _sw("1-21n331", "装置端子", ["D1"]), _sw("1-21n-DC", "内部元件", ["Q2"]))
    output = [terminal_form, element_form]
    stats = _discard_device_internal_pairs(output, data)
    assert output[0].status == "pass" and "discard_reason" not in output[0].evidence
    assert output[1].status == "discard"
    assert stats == {"kept:other_identity_terminal_form": 1, "discarded:pass": 1,
                     "discarded:pass:wire_component_mapping": 1}


def test_dev_int_uses_the_pair_identity_of_an_element_port():
    def dict_port(record_id, category, identity):
        return {"record_id": record_id, "file_id": "F1", "sheet_id": "S1", "insert_handle": record_id, "port_number": "1",
                "category": category, "endpoint_identity": identity, "label": _label("1-21n"),
                "wire_contacts": [{"wire_handle": "W1", "wire_side": 0}]}
    ports = [dict_port("D1", "装置端子", "1-21n331"), dict_port("Q1", "内部元件", None)]
    kept = build_device_internal_links(ports, [], element_identities={"Q1": "1-21n332"})
    assert kept["links"] == []
    assert kept["stats"]["excluded:other_identity_terminal_form"] == 1
    linked = build_device_internal_links(ports, [], element_identities={"Q1": "1-21n-DC"})
    assert [l["port_id"] for l in linked["links"]] == ["D1"]
    assert linked["links"][0]["element_identity"] == "1-21n-DC"


def test_a_link_whose_port_a_pair_names_is_marked_overruled(tmp_path):
    from dwg_audit.domain.models import SheetRecord
    from dwg_audit.extract.superworks_semantics import SuperworksData
    from dwg_audit.report.superworks_artifacts import write_superworks_artifacts
    import pandas as pd

    page = SheetRecord("S1", "F1", "01 x.dwg", 1, "01", "x", "二次原理图", "primary", "filename", True,
                       audit_disposition="audit")
    device = SwPort(record_id="D1", sheet_id="S1", file_id="F1", insert_handle="HD", port_number="1",
                    category="装置端子", endpoint_identity="1n705", label=_label("1n"),
                    wire_contacts=[{"wire_handle": "W1", "wire_side": 0}])
    element = SwPort(record_id="Q1", sheet_id="S1", file_id="F1", insert_handle="HQ", port_number="1",
                     category="内部元件", endpoint_identity=None, label=_label("1n"),
                     wire_contacts=[{"wire_handle": "W1", "wire_side": 1}])
    data = SuperworksData(ports=[device, element])
    line = SimpleNamespace(file_id="F1", line_id="L1", handle="W1", source_block_name=None,
                           start_x=0.0, start_y=0.0, end_x=1.0, end_y=0.0)
    group = SimpleNamespace(file_id="F1", member_line_ids=["L1"])
    external = Pair(pair_id="PX", line_group_id="GW9", sheet_id="S1", file_id="F1", selected_pair_candidate_id=None,
                    left_value="1n705", right_value="1KLP3-2", confidence=0.9, status="pass", rationale="r",
                    evidence={"source": "superworks", "superworks": {
                        "left": {"value": "1n705", "category": "装置端子", "port_ids": ["D1"]},
                        "right": {"value": "1KLP3-2", "category": "", "port_ids": []}}},
                    pair_kind="wire_component_mapping")
    artifacts = SimpleNamespace(superworks=data, superworks_supersession=[], lines=[line], line_groups=[group],
                                scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"), pages=[page]),
                                pairs=[external])
    write_superworks_artifacts(artifacts, tmp_path)
    links = pd.read_parquet(tmp_path / "sw_device_internal_links.parquet")
    assert len(links) == 1 and bool(links.overruled_by_pair.iloc[0])


def test_element_identity_of_another_name_is_not_discarded_and_bare_or_absent_identity_is():
    terminal = {"category": "装置端子", "identity": "1n832", "label": "1n", "label_resolved": True}
    foreign = {"category": "内部元件", "label": "1n", "label_resolved": True, "identity": "1QD39"}
    bare = {"category": "内部元件", "label": "1n", "label_resolved": True, "identity": "707"}
    absent = {"category": "内部元件", "label": "1n", "label_resolved": True, "identity": None}
    assert device_internal_verdict(terminal, foreign) == "other_identity_foreign"
    assert device_internal_verdict(terminal, bare) == DEVICE_INTERNAL
    assert device_internal_verdict(terminal, absent) == DEVICE_INTERNAL


def test_pair_and_dev_int_keep_a_foreign_named_element():
    data = _data(_port("D1", "装置端子", identity="1n832"), _port("Q1", "内部元件", identity=None, label="1n"))
    pair = _pair("PF1", _sw("1n832", "装置端子", ["D1"]), ("1QD39", {"value": "1QD39", "category": "内部元件",
                                                                       "port_ids": ["Q1"]}))
    output = [pair]
    _discard_device_internal_pairs(output, data)
    assert output[0].status == "pass"
    ports = [{"record_id": "D1", "file_id": "F1", "sheet_id": "S1", "insert_handle": "D1", "port_number": "1",
              "category": "装置端子", "endpoint_identity": "1n832", "label": _label("1n"),
              "wire_contacts": [{"wire_handle": "W1", "wire_side": 0}]},
             {"record_id": "Q1", "file_id": "F1", "sheet_id": "S1", "insert_handle": "Q1", "port_number": "1",
              "category": "内部元件", "endpoint_identity": None, "label": _label("1n"),
              "wire_contacts": [{"wire_handle": "W1", "wire_side": 1}]}]
    result = build_device_internal_links(ports, [], element_identities={"Q1": "1QD39"})
    assert result["links"] == []
    assert result["stats"]["excluded:other_identity_foreign"] == 1
