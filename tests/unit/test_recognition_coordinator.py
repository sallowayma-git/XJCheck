import ezdxf

from dwg_audit.audit.superworks_extractor import extract_superworks_pairs
from dwg_audit.audit.recognition_coordinator import SharedRecognitionContext
from dwg_audit.audit.page_extractors import extract_wire_pairs
from dwg_audit.domain.models import LineGroup, SheetRecord
from dwg_audit.extract.superworks_semantics import SuperworksData
from dwg_audit.utils.config import load_config
from test_superworks_semantics import symbol, extract, text_items, xdata


def resolve(doc, data):
    page = SheetRecord("S1", "F1", "test.dwg", 1, "1", "test", "二次原理图",
        "primary", "filename", True, audit_disposition="audit")
    group = LineGroup("GW1", "S1", "F1", 0, 0, 20, 0, 20, 1)
    return extract_superworks_pairs(data, pages=[page], texts=text_items(doc), lines=[],
        line_groups=[group], pairs=[], table_mappings=[], native_only=True)


def test_complete_native_wire_resolves_without_a_legacy_pair():
    doc = ezdxf.new()
    symbol(doc, "端子", "1XD2")
    symbol(doc, "装置端子", "2-1n", at=(20, 0), pin_value="323")
    doc.modelspace().add_line((0, 0), (20, 0))
    data = extract(doc)
    pairs, _, _ = resolve(doc, data)
    assert len(pairs) == 1
    assert (pairs[0].left_value, pairs[0].right_value, pairs[0].status) == ("1XD2", "2-1n323", "pass")
    assert data.resolution_observations[0]["state"] == "RESOLVED"


def test_component_reconciliation_scopes_repeated_handles_to_the_source_file():
    from dataclasses import replace
    from dwg_audit.domain.models import Pair, LineEntity, SwConnectLabel, SwPartInstance

    pages = [SheetRecord("S1", "F1", "one.dwg", 1, "1", "one", "元件接线图",
        "primary", "filename", True, audit_disposition="audit")]
    pages.append(replace(pages[0], sheet_id="S2", file_id="F2", filename="two.dwg"))
    parts = [SwPartInstance(f"PART{n}", f"S{n}", f"F{n}", insert_handle="BODY",
        label={"text_id": f"TB{n}"}, ports=[{"port_number": "1", "endpoint_identity": f"DK{n}-1",
        "pin": {"independent_verification": True}}]) for n in (1, 2)]
    labels = [SwConnectLabel(f"C{n}", f"S{n}", f"F{n}",
        text={"handle": "SAME", "text_id": f"TD{n}", "value": f"ZD{n}"},
        line_handle="WIRE", part_id=f"PART{n}", port_number="1", endpoint_identity=f"DK{n}-1") for n in (1, 2)]
    lines = [LineEntity(f"L{n}", f"S{n}", f"F{n}", "WIRE", "LINE", "CONNECT",
        0, 0, 1, 0, 1, 0, 0, 0, 1, 0) for n in (1, 2)]
    native = Pair("NATIVE", None, "S1", "F1", None, "DK1-1", "ZD1", .99, "pass", "verified",
        pair_kind="component_mapping", evidence={"component_submode": "superworks_connect_line_port",
        "superworks": {"connection_handle": "SAME"}})
    output, _, _ = extract_superworks_pairs(SuperworksData(part_instances=parts, connect_labels=labels),
        pages=pages, texts=[], lines=lines, line_groups=[], pairs=[native], table_mappings=[],
        shared_context=SharedRecognitionContext.create([]))
    assert len(output) == 2
    second = next(p for p in output if p.file_id == "F2")
    assert (second.left_value, second.right_value) == ("DK2-1", "ZD2")
    assert second.evidence["supporting_line_ids"] == ["L2"]


def test_virtual_pin_ownership_preserves_native_identity_and_distinct_targets():
    from dataclasses import replace
    from dwg_audit.domain.models import Pair
    from test_component_diagrams import _make_text, _make_sheet

    page = _make_sheet()
    pin = replace(_make_text("PIN", "1", 0, 0), handle="ABC:VIRTUAL:7")
    external = _make_text("DEST", "JD8", 10, 0)
    other_pin = replace(pin, text_id="PIN2", normalized_text="2", handle="ABC:VIRTUAL:8")
    native = Pair("N", None, page.sheet_id, page.file_id, None, "KZKK-1", "JD8", .99, "pass", "verified",
        pair_kind="component_mapping", left_text_id="NATIVE_BODY", right_text_id="DEST",
        evidence={"native_resolution_state": "RESOLVED", "component_submode": "superworks_connect_line_port",
        "superworks": {"part_id": "SW:ABC", "symbol_handle": "ABC", "instance_path": "/ABC", "port_number": "1"}})
    context = SharedRecognitionContext.create([pin, other_pin, external])
    context.accept_native([native], [])
    ids = context.pair_ids("V1")
    assert not ids.admit(page, "WRONG_NAME-1", "JD8", "PIN", "DEST", kind="component_mapping", port_number="1")
    assert not ids.admit(page, "8", "1", "DEST", "PIN", kind="ordinary_pair")
    assert ids.admit(page, "WRONG_NAME-2", "JD8", "PIN2", "DEST", kind="component_mapping", port_number="2")
    row = replace(pin, text_id="ROW", handle="SEPARATE_LABEL")
    context.text_facts[(page.file_id, page.sheet_id, row.text_id)] = row
    assert ids.admit(page, "circuit", "JD8", "ROW", "DEST", kind="component_mapping")
    page2 = replace(page, file_id="F2", sheet_id="S2")
    for text in (pin, external):
        context.text_facts[("F2", "S2", text.text_id)] = replace(text, file_id="F2", sheet_id="S2")
    assert ids.admit(page2, "WRONG_NAME-1", "JD8", "PIN", "DEST", kind="component_mapping", port_number="1")


def test_unverified_or_nested_native_pin_does_not_claim_a_bare_insert_handle():
    from dataclasses import replace
    from dwg_audit.domain.models import Pair
    from test_component_diagrams import _make_text, _make_sheet

    page = _make_sheet()
    pin = replace(_make_text("PIN", "1", 0, 0), handle="ABC:VIRTUAL:7")
    external = _make_text("DEST", "JD8", 10, 0)
    for state, path in (("AMBIGUOUS", "/ABC"), ("RESOLVED", "/PARENT/ABC")):
        native = Pair("N", None, page.sheet_id, page.file_id, None, "KZKK-1", "JD8", .99, "pass", "candidate",
            evidence={"native_resolution_state": state,
            "superworks": {"part_id": "SW:ABC", "symbol_handle": "ABC", "instance_path": path, "port_number": "1"}})
        context = SharedRecognitionContext.create([pin, external])
        context.accept_native([native], [])
        assert context.pair_ids("V1").admit(page, "OTHER-1", "JD8", "PIN", "DEST", kind="component_mapping")


def test_partial_native_wire_retains_gap_and_reliable_side_without_pair():
    doc = ezdxf.new()
    symbol(doc, "端子", "1XD2")
    doc.modelspace().add_line((0, 0), (20, 0))
    data = extract(doc)
    pairs, _, _ = resolve(doc, data)
    assert pairs == []
    gap = data.resolution_observations[0]
    assert gap["state"] == "INCOMPLETE"
    assert gap["left"]["value"] == "1XD2" and gap["right"] is None


def test_conflict_is_observed_even_when_no_legacy_pair_exists():
    doc = ezdxf.new()
    insert, _ = symbol(doc, "端子", "1XD2")
    xdata(insert, "LD_SYMB2_LABEL", [(1005, "FFFF")])
    symbol(doc, "装置端子", "2-1n", at=(20, 0), pin_value="323")
    doc.modelspace().add_line((0, 0), (20, 0))
    data = extract(doc)
    pairs, _, _ = resolve(doc, data)
    assert pairs == []
    assert data.resolution_observations[0]["state"] == "CONFIRMED_CONFLICT"
    assert "dangling_label_handle" in data.resolution_observations[0]["reason_codes"]


def test_no_metadata_is_an_explicit_gap_not_a_silent_skip():
    data = SuperworksData()
    assert resolve(ezdxf.new(), data)[0] == []
    assert data.resolution_observations[0]["reason_codes"] == ["no_sw_ports"]


def test_compatible_route_reuses_shared_index_and_geometry(monkeypatch):
    page = SheetRecord("S1", "F1", "test.dwg", 1, "1", "test", "二次原理图",
        "primary", "filename", True, audit_area_bbox=(-5, -5, 30, 30))
    context = SharedRecognitionContext.create([])
    first = extract_wire_pairs([page], [], [], load_config(None), shared_context=context)
    monkeypatch.setattr("dwg_audit.audit.recognition_coordinator.build_line_groups",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("Geometry rebuilt")))
    second = extract_wire_pairs([page], [], [], load_config(None), shared_context=context)
    assert first.line_groups is second.line_groups
    assert context.counts["route_group_builds"] == 1
    assert context.counts["route_group_reuses"] == 1


def test_complete_native_target_never_runs_v1_candidate_pairing(monkeypatch):
    doc = ezdxf.new()
    symbol(doc, "端子", "1XD2")
    symbol(doc, "装置端子", "2-1n", at=(20, 0), pin_value="323")
    doc.modelspace().add_line((0, 0), (20, 0))
    data = extract(doc)
    native, _, _ = resolve(doc, data)
    context = SharedRecognitionContext.create(text_items(doc))
    context.accept_native(native, data.resolution_observations)
    page = SheetRecord("S1", "F1", "test.dwg", 1, "1", "test", "二次原理图",
        "primary", "filename", True, audit_area_bbox=(-5, -5, 30, 30))
    context.route_groups[("W", ("S1",))] = [LineGroup("GW1", "S1", "F1", 0, 0, 20, 0, 20, 1)]
    monkeypatch.setattr("dwg_audit.audit.page_extractors.build_terminal_candidates",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("V1 candidates on complete SW target")))
    result = extract_wire_pairs([page], text_items(doc), [], load_config(None),
        shared_context=context, target_line_group_ids=set())
    assert result.terminal_candidates == [] and result.pair_candidates == []


def test_native_ownership_requires_physical_texts_not_only_same_value():
    from dwg_audit.domain.models import Pair
    page = SheetRecord("S1", "F1", "test.dwg", 1, "1", "test", "二次原理图",
        "primary", "filename", True)
    native = Pair("SW", "G", "S1", "F1", None, "1XD2", "2-1n323", .99, "pass", "verified",
        left_text_id="L", right_text_id="R", evidence={"source": "superworks", "native_resolution_state": "RESOLVED"})
    context = SharedRecognitionContext.create([])
    context.accept_native([native], [])
    ids = context.pair_ids("V1")
    assert not ids.admit(page, "1XD2", "2-1n323", "L", "R")
    assert ids.admit(page, "1XD2", "2-1n323", "different-L", "different-R")
    assert ids.admit(page, "1XD2", "2-1n324", "L", "R")


def test_dispatch_uses_parser_state_instead_of_the_final_pair_status():
    from dwg_audit.domain.models import Pair
    pair = Pair("P", "G", "S", "F", None, "A1", "B2", .99, "pass", "candidate",
        evidence={"native_resolution_state": "INCOMPLETE"})
    context = SharedRecognitionContext.create([])
    context.accept_native([pair], [])
    assert ("S", "G") not in context.closed_groups
    pair.status = "review"
    pair.evidence["native_resolution_state"] = "RESOLVED"
    context.accept_native([pair], [])
    assert ("S", "G") in context.closed_groups


def test_draft_geometry_cannot_use_the_high_confidence_bypass():
    from dwg_audit.domain.models import Pair
    from dwg_audit.audit.recognition_coordinator import finalize_evidence
    from dwg_audit.audit.rules import _high_confidence_source_eligible
    pair = Pair("P", "G", "S", "F", None, "A1", "B2", .999, "pass", "draft",
        confidence_bucket="high", evidence={"structured_source": "table_mapping",
            "selected_right_physical_endpoint": {"topology_state": "UNKNOWN"}})
    finalize_evidence([pair], SharedRecognitionContext.create([]))
    assert pair.status == "review" and pair.confidence_bucket == "review"
    assert pair.evidence["recognition_state"] == "AMBIGUOUS"
    assert not _high_confidence_source_eligible(pair)


def test_verified_geometry_is_a_witness_and_fixed_identity_is_not_overwritten():
    from dwg_audit.domain.models import Pair
    from dwg_audit.audit.recognition_coordinator import finalize_evidence
    pair = Pair("P", "G", "S", "F", None, "A1", "B2", .999, "pass", "geometry",
        evidence={"superworks": {"partial": True,
            "left": {"value": "A9", "wire_touched": True, "port_ids": ["native-port"]}},
            "selected_right_physical_endpoint": {"source": "reciprocal_cad_label_and_terminal_geometry"}})
    context = SharedRecognitionContext.create([])
    finalize_evidence([pair], context)
    assert pair.left_value == "A9"
    assert pair.status == "review"
    assert pair.evidence["engine_evidence_conflicts"][0]["candidate"] == "A1"
    assert pair.evidence["engine_evidence_conflicts"][0]["fixed_identity"] == "A9"
    assert pair.evidence["engine_contributors"] == ["v1", "v2", "superworks"]
    assert context.counts["verified_v2_geometry_bindings"] == 1


def test_confirmed_native_conflict_survives_high_scoring_fallback():
    from dwg_audit.domain.models import Pair
    from dwg_audit.audit.recognition_coordinator import finalize_evidence
    pair = Pair("P", "G", "S", "F", None, "A1", "B2", .999, "pass", "fallback",
        evidence={"sw_conflicts": ["dangling_label_handle"]})
    finalize_evidence([pair], SharedRecognitionContext.create([]))
    assert pair.evidence["recognition_state"] == "CONFIRMED_CONFLICT"
    assert pair.status == "review"


def test_no_pair_native_conflict_is_audited_and_noise_is_not_a_gap():
    from dwg_audit.audit.recognition_coordinator import build_resolution_issues
    doc = ezdxf.new()
    insert, _ = symbol(doc, "端子", "1XD2")
    xdata(insert, "LD_SYMB2_LABEL", [(1005, "FFFF")])
    symbol(doc, "装置端子", "2-1n", at=(20, 0), pin_value="323")
    doc.modelspace().add_line((0, 0), (20, 0))
    data = extract(doc)
    resolve(doc, data)
    issues = build_resolution_issues(data.resolution_observations, [], [])
    assert issues and issues[0].rule_id == "R-SUPERWORKS-CONFLICT"
    assert issues[0].pair_id is None and issues[0].evidence["line_start"] == [0, 0]
    assert issues[0].evidence["handling_class"] == "review"
    assert issues[0].evidence["review_group_size"] == 1
    assert build_resolution_issues(data.resolution_observations, [], [], issues) == []
    data = SuperworksData()
    resolve(ezdxf.new(), data)
    assert build_resolution_issues(data.resolution_observations, [], []) == []


def test_discarded_fallback_does_not_hide_a_native_gap():
    from dwg_audit.audit.recognition_coordinator import build_resolution_issues
    from dwg_audit.domain.models import Pair
    observation = {"record_id": "gap", "object_key": "F:handle:port:left", "file_id": "F", "sheet_id": "S", "line_group_id": "G", "state": "INCOMPLETE", "left": {"wire_touched": True, "port_ids": ["port"]}}
    rejected = Pair("P", "G", "S", "F", None, None, None, .1, "discard", "no evidence")
    assert len(build_resolution_issues([observation], [rejected], [])) == 1
    rejected.evidence["discard_reason"] = "device_internal"
    assert build_resolution_issues([observation], [rejected], []) == []


def test_native_gaps_group_per_sheet_without_dropping_physical_witnesses():
    from dwg_audit.audit.recognition_coordinator import build_resolution_issues
    base = {"file_id": "F", "sheet_id": "S", "state": "INCOMPLETE",
        "left": {"wire_touched": True, "port_ids": ["port"]}}
    issues = build_resolution_issues([{**base, "record_id": str(n), "object_key": f"F:handle{n}:left", "line_group_id": f"G{n}",
        "left": {"wire_touched": True, "port_ids": [f"port{n}"]}} for n in range(2)], [], [])
    assert len(issues) == 2 and len({i.evidence["object_key"] for i in issues}) == 2
    assert len({i.evidence["review_group_id"] for i in issues}) == 1
    assert all(i.evidence["review_group_size"] == 2 for i in issues)
