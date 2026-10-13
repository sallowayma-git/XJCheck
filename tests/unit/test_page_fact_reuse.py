import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import ezdxf

from dwg_audit.extract.cad_extract import extract_cad_artifacts, page_fact_fingerprint, decode_page_facts
from dwg_audit.readers import EzdxfReader
from dwg_audit.utils.config import DEFAULT_CONFIG
from test_cad_extract import _source_file, _scan, DummyLogger
from test_superworks_semantics import symbol


def extract_pages(paths, *, cache=None, fingerprint="version-1"):
    scan = _scan()
    scan.project_root = str(paths[0].parent)
    sources = []
    pages = []
    for n, path in enumerate(paths, 1):
        source = _source_file(path)
        source.file_id = f"F{n:04d}"
        source.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        sources.append(source)
        page = _scan().pages[0]
        page.file_id = source.file_id
        page.sheet_id = f"S{n:04d}"
        pages.append(page)
    scan.pages = pages
    return extract_cad_artifacts(scan, sources, DEFAULT_CONFIG, DummyLogger(),
        cached_pages=cache, capture_page_facts=True, fingerprint=fingerprint)


def drawings(tmp_path):
    paths = []
    for n in range(2):
        doc = ezdxf.new()
        symbol(doc, "端子", "1XD2")
        symbol(doc, "装置端子", "2-1n", at=(20, 0), pin_value="323")
        doc.modelspace().add_line((0, 0), (20, 0))
        path = tmp_path / f"{n}.dxf"
        doc.saveas(path)
        paths.append(path)
    return paths


def assert_same_facts(a, b):
    for name in ("texts", "lines", "blocks", "polylines", "pages", "primitive_segments", "terminal_port_bindings"):
        assert [asdict(x) for x in getattr(a, name)] == [asdict(x) for x in getattr(b, name)]
    assert [asdict(x) for x in a.superworks.ports] == [asdict(x) for x in b.superworks.ports]
    assert a.superworks.wire_endpoints == b.superworks.wire_endpoints


def test_same_inputs_reuse_typed_facts_without_opening_cad(tmp_path, monkeypatch):
    paths = drawings(tmp_path)
    first = extract_pages(paths)
    monkeypatch.setattr(EzdxfReader, "read", lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("CAD read on cache hit")))
    second = extract_pages(paths, cache=json.loads(json.dumps(first.page_facts)))
    assert second.reused_page_count == 2
    assert_same_facts(first, second)
    facts = decode_page_facts(first.page_facts[str(paths[0].resolve())]["facts"])
    assert all(isinstance(k, tuple) for k in facts["superworks"].wire_endpoints)
    assert all(isinstance(k, int) for v in facts["superworks"].wire_endpoints.values() for k in v)


def test_changed_page_reuses_other_page_and_matches_full_extraction(tmp_path, monkeypatch):
    paths = drawings(tmp_path)
    first = extract_pages(paths)
    doc = ezdxf.readfile(paths[1])
    doc.modelspace().add_text("new label", dxfattribs={"insert": (50, 20)})
    doc.saveas(paths[1])
    original = EzdxfReader.read
    reads = []
    def read(self, path, options):
        reads.append(Path(path))
        return original(self, path, options)
    monkeypatch.setattr(EzdxfReader, "read", read)
    incremental = extract_pages(paths, cache=first.page_facts)
    assert incremental.reused_page_count == 1 and reads == [paths[1]]
    full = extract_pages(paths)
    assert_same_facts(full, incremental)


def test_id_count_change_invalidates_suffix_and_version_invalidates_all(tmp_path):
    paths = drawings(tmp_path)
    first = extract_pages(paths)
    doc = ezdxf.readfile(paths[0])
    doc.modelspace().add_text("extra")
    doc.saveas(paths[0])
    incremental = extract_pages(paths, cache=first.page_facts)
    assert incremental.reused_page_count == 0
    assert_same_facts(extract_pages(paths), incremental)
    assert extract_pages(paths, cache=incremental.page_facts, fingerprint="version-2").reused_page_count == 0


def test_xml_and_config_fingerprints_invalidate_current_page_facts(tmp_path):
    paths = drawings(tmp_path)
    version = page_fact_fingerprint(tmp_path, DEFAULT_CONFIG)
    first = extract_pages(paths, fingerprint=version)
    (tmp_path / "LdDzbInfo.xml").write_text("<root/>")
    changed = page_fact_fingerprint(tmp_path, DEFAULT_CONFIG)
    assert changed != version
    assert page_fact_fingerprint(tmp_path, {**DEFAULT_CONFIG, "config_version": "changed"}) != changed
    assert extract_pages(paths, cache=first.page_facts, fingerprint=changed).reused_page_count == 0


def test_corrupt_facts_fall_back_to_fresh_cad(tmp_path):
    paths = drawings(tmp_path)
    first = extract_pages(paths)
    first.page_facts[str(paths[0].resolve())]["facts"] = {"type": "UnknownExecutableClass", "fields": {}}
    fresh = extract_pages(paths, cache=first.page_facts)
    assert fresh.reused_page_count == 1
    assert_same_facts(extract_pages(paths), fresh)
