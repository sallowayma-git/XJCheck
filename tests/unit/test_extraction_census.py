from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import ezdxf

from dwg_audit.extract.extraction_census import CENSUS_SCHEMA_VERSION
from dwg_audit.extract.extraction_census import build_extraction_census


class _FakeEntity:
    def __init__(self, entity_type: str, *, handle: str = "E1", name: str | None = None) -> None:
        self._entity_type = entity_type
        self.dxf = SimpleNamespace(handle=handle, name=name)
        self.attribs: list[_FakeEntity] = []

    def dxftype(self) -> str:
        return self._entity_type


class _FakeInsert(_FakeEntity):
    def __init__(self, *, mode: str = "ok") -> None:
        super().__init__("INSERT", handle="I1", name="BROKEN")
        self.mode = mode
        self.mcount = 1
        self.has_uniform_scaling = True

    def virtual_entities(self, *, skipped_entity_callback=None):
        if self.mode == "raise":
            raise RuntimeError("cannot transform block")
        if self.mode == "skip" and skipped_entity_callback is not None:
            skipped_entity_callback(
                _FakeEntity("DIMENSION", handle="D1"),
                "non-uniform transformation not supported",
            )
        return iter([_FakeEntity("LINE", handle="VL1")])


class _FakeLayout(list):
    def __init__(
        self,
        name: str,
        entities: list[object],
        *,
        model: bool = False,
        paper: bool = False,
    ) -> None:
        super().__init__(entities)
        self.name = name
        self.is_modelspace = model
        self.is_any_paperspace = paper


class _BrokenLayout(_FakeLayout):
    def __iter__(self):
        raise RuntimeError("layout entity database is unreadable")


class _FakeBlock(list):
    def __init__(self, name: str, entities: list[object]) -> None:
        super().__init__(entities)
        self.name = name
        self.is_any_layout = False
        self.block = SimpleNamespace(
            is_xref=False,
            dxf=SimpleNamespace(flags=0, xref_path=""),
        )


class _FakeDocument:
    def __init__(self, layouts: list[object], blocks: list[object] | None = None) -> None:
        self.layouts = layouts
        self.blocks = blocks or []
        self.units = 4
        self.filename = None


def _error_codes(census) -> set[str]:
    return {item.code for item in census.errors}


def test_census_counts_layouts_and_nested_block_graph_fail_closed() -> None:
    doc = ezdxf.new("R2018")
    doc.units = 4
    inner = doc.blocks.new(name="INNER")
    inner.add_line((0, 0), (10, 0))
    outer = doc.blocks.new(name="OUTER")
    outer.add_blockref("INNER", (0, 0))
    doc.modelspace().add_line((0, 0), (20, 0))
    doc.modelspace().add_blockref("OUTER", (5, 5))
    doc.layout("Layout1").add_text("PAPER CONTENT")

    census = build_extraction_census(doc)

    assert census.schema_version == CENSUS_SCHEMA_VERSION
    assert census.status == "INCOMPLETE"
    assert not census.complete
    assert census.entity_counts_by_layout["Model"] == {"INSERT": 1, "LINE": 1}
    assert census.entity_counts_by_layout["Layout1"] == {"TEXT": 1}
    assert census.model_space_entity_count == 2
    assert census.paper_space_entity_count == 1
    assert census.paper_space_native_entity_count == 1
    assert census.paper_space_viewport_count == 0
    assert census.unprocessed_layout_entity_count == 1
    assert census.unprocessed_layout_native_entity_count == 1
    assert census.block_definition_count == 2
    assert census.block_definition_entity_counts == {
        "INNER": {"LINE": 1},
        "OUTER": {"INSERT": 1},
    }
    assert census.block_reference_count == 1
    assert census.block_instance_count == 1
    assert census.nested_block_reference_count == 1
    assert census.nested_block_max_depth == 2
    assert census.virtual_expansion_attempts == 2
    assert census.virtual_expansion_failures == ()
    assert _error_codes(census) == {"LAYOUT_NOT_CONSUMED"}
    assert census.entity_counts_by_type == {"INSERT": 2, "LINE": 2, "TEXT": 1}
    assert census.xref_count == 0

    all_layouts = build_extraction_census(doc, consumed_layout_names=None)

    assert all_layouts.status == "COMPLETE"
    assert all_layouts.complete
    assert all_layouts.errors == ()
    payload = json.loads(json.dumps(all_layouts.to_dict()))
    assert payload["units_name"] == "Millimeters"
    assert payload["entity_counts_by_type"] == {"INSERT": 2, "LINE": 2, "TEXT": 1}
    assert payload["virtual_entity_failures"] == []


def test_census_includes_insert_attributes_in_layout_entity_counts() -> None:
    doc = ezdxf.new("R2018")
    doc.units = 4
    block = doc.blocks.new(name="TERM")
    block.add_attdef("TERM", insert=(0, 0), height=2.5)
    insert = doc.modelspace().add_blockref("TERM", (10, 10))
    insert.add_auto_attribs({"TERM": "101"})

    census = build_extraction_census(doc, consumed_layout_names=None)

    assert census.complete
    assert census.entity_counts_by_layout["Model"] == {"ATTRIB": 1, "INSERT": 1}
    assert census.block_definition_entity_counts["TERM"] == {"ATTDEF": 1}


def test_census_marks_unsupported_proxy_entities_incomplete() -> None:
    document = _FakeDocument(
        [
            _FakeLayout(
                "Model",
                [_FakeEntity("ACAD_PROXY_ENTITY"), _FakeEntity("CIRCLE", handle="C1")],
                model=True,
            )
        ]
    )

    census = build_extraction_census(document, consumed_layout_names=None)

    assert census.status == "INCOMPLETE"
    assert census.proxy_entity_count == 1
    assert census.proxy_entity_counts == {"ACAD_PROXY_ENTITY": 1}
    assert census.unsupported_entity_count == 2
    assert census.unsupported_entity_counts == {
        "ACAD_PROXY_ENTITY": 1,
        "CIRCLE": 1,
    }
    assert census.shadow_unsupported_entity_counts == {"ACAD_PROXY_ENTITY": 1}
    assert _error_codes(census) == {"PROXY_ENTITY_PRESENT"}
    assert {item.code for item in census.warnings} >= {
        "SEMANTIC_UNSUPPORTED_ENTITY_TYPE",
        "SHADOW_UNSUPPORTED_ENTITY_TYPE",
    }


def test_census_records_virtual_expansion_exception() -> None:
    insert = _FakeInsert(mode="raise")
    document = _FakeDocument(
        [_FakeLayout("Model", [insert], model=True)],
        [_FakeBlock("BROKEN", [_FakeEntity("LINE")])],
    )

    census = build_extraction_census(document, consumed_layout_names=None)

    assert not census.complete
    assert census.virtual_expansion_attempts == 1
    assert [item.code for item in census.virtual_expansion_failures] == [
        "VIRTUAL_EXPANSION_FAILED"
    ]
    assert "VIRTUAL_EXPANSION_FAILED" in _error_codes(census)


def test_census_records_skipped_virtual_entity_as_blocking_warning() -> None:
    insert = _FakeInsert(mode="skip")
    document = _FakeDocument(
        [_FakeLayout("Model", [insert], model=True)],
        [_FakeBlock("BROKEN", [_FakeEntity("LINE")])],
    )

    census = build_extraction_census(document, consumed_layout_names=None)

    assert not census.complete
    assert [item.code for item in census.virtual_expansion_warnings] == [
        "VIRTUAL_ENTITY_SKIPPED"
    ]
    assert census.virtual_expansion_warnings[0].entity_type == "DIMENSION"
    assert "VIRTUAL_ENTITY_SKIPPED" in _error_codes(census)


def test_census_resolves_xref_path_but_requires_explicit_content_load(tmp_path: Path) -> None:
    doc = ezdxf.new("R2018")
    doc.units = 4
    xref = doc.blocks.new(name="COMMON")
    xref.block.dxf.flags = 4
    xref.block.dxf.xref_path = "refs/common.dwg"
    doc.modelspace().add_blockref("COMMON", (0, 0))
    document_path = tmp_path / "host.dxf"

    missing = build_extraction_census(
        doc,
        document_path=document_path,
        consumed_layout_names=None,
    )

    assert missing.missing_xrefs == ("COMMON",)
    assert missing.xref_definitions[0].resolution_status == "missing"
    assert {"XREF_NOT_RESOLVED", "XREF_CONTENT_NOT_LOADED"} <= _error_codes(missing)

    xref_path = tmp_path / "refs" / "common.dwg"
    xref_path.parent.mkdir()
    xref_path.touch()
    resolved_not_loaded = build_extraction_census(
        doc,
        document_path=document_path,
        consumed_layout_names=None,
    )

    assert resolved_not_loaded.missing_xrefs == ()
    assert resolved_not_loaded.xref_definitions[0].resolution_status == "resolved"
    assert not resolved_not_loaded.complete
    assert _error_codes(resolved_not_loaded) == {"XREF_CONTENT_NOT_LOADED"}

    loaded = build_extraction_census(
        doc,
        document_path=document_path,
        consumed_layout_names=None,
        loaded_xref_names={"common"},
    )

    assert loaded.complete
    assert loaded.xref_definitions[0].content_loaded
    assert loaded.xref_definitions[0].resolved_path == str(xref_path)


def test_census_layout_scan_failure_and_unitless_document_fail_closed() -> None:
    broken = _FakeDocument([_BrokenLayout("Model", [], model=True)])
    broken.units = 0

    census = build_extraction_census(broken, consumed_layout_names=None)

    assert census.status == "INCOMPLETE"
    assert not census.complete
    assert "LAYOUT_SCAN_FAILED" in _error_codes(census)
    assert "UNITS_UNSPECIFIED" in {item.code for item in census.warnings}
    assert census.scale_status == "UNRESOLVED"


def test_census_preserves_conversion_warnings_without_hiding_them() -> None:
    doc = ezdxf.new("R2018")
    doc.units = 4

    census = build_extraction_census(
        doc,
        consumed_layout_names=None,
        conversion_warnings=["ODA repaired one object"],
    )

    assert census.complete
    assert census.conversion_warnings == ("ODA repaired one object",)
    assert [item.code for item in census.warnings] == ["CONVERSION_WARNING"]
    assert census.to_dict()["conversion_warnings"] == ["ODA repaired one object"]


def test_census_counts_all_minsert_instances() -> None:
    doc = ezdxf.new("R2018")
    doc.units = 4
    block = doc.blocks.new(name="CELL")
    block.add_line((0, 0), (1, 0))
    insert = doc.modelspace().add_blockref("CELL", (0, 0))
    insert.dxf.row_count = 2
    insert.dxf.column_count = 3
    insert.dxf.row_spacing = 10
    insert.dxf.column_spacing = 10

    census = build_extraction_census(doc, consumed_layout_names=None)

    assert census.complete
    assert census.block_reference_count == 1
    assert census.block_instance_count == 6
    assert census.virtual_expansion_attempts == 6


def test_viewport_only_paperspace_is_reviewable_not_missing_native_content() -> None:
    document = _FakeDocument(
        [
            _FakeLayout("Model", [_FakeEntity("LINE")], model=True),
            _FakeLayout(
                "Layout1",
                [_FakeEntity("VIEWPORT"), _FakeEntity("VIEWPORT", handle="V2")],
                paper=True,
            ),
        ]
    )

    census = build_extraction_census(document)

    assert census.complete
    assert census.paper_space_entity_count == 2
    assert census.paper_space_native_entity_count == 0
    assert census.paper_space_viewport_count == 2
    assert census.unprocessed_layout_entity_count == 2
    assert census.unprocessed_layout_native_entity_count == 0
    assert _error_codes(census) == set()
    assert "VIEWPORT_LAYOUT_NOT_INTERPRETED" in {
        item.code for item in census.warnings
    }


def test_semantic_and_shadow_coverage_are_reported_independently() -> None:
    document = _FakeDocument(
        [
            _FakeLayout(
                "Model",
                [_FakeEntity("ARC"), _FakeEntity("HATCH", handle="H1")],
                model=True,
            )
        ]
    )

    census = build_extraction_census(document, consumed_layout_names=None)

    assert census.complete
    assert not census.semantic_coverage_complete
    assert census.unsupported_entity_counts == {"ARC": 1, "HATCH": 1}
    assert not census.shadow_coverage_complete
    assert census.shadow_unsupported_entity_counts == {"HATCH": 1}
