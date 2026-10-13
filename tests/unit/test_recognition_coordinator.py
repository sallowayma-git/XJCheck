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
        left_text_id="L", right_text_id="R", evidence={"source": "superworks"})
    context = SharedRecognitionContext.create([])
    context.accept_native([native], [])
    ids = context.pair_ids("V1")
    assert not ids.admit(page, "1XD2", "2-1n323", "L", "R")
    assert ids.admit(page, "1XD2", "2-1n323", "different-L", "different-R")
    assert ids.admit(page, "1XD2", "2-1n324", "L", "R")


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
    assert pair.left_value == "A1"
    assert pair.status == "review"
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

