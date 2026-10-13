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
