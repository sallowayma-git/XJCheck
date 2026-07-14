from __future__ import annotations

import json

import ezdxf
import pytest
from ezdxf.entities import Insert

from dwg_audit.extract.document_walker import CANONICAL_SCENE_SCHEMA_VERSION
from dwg_audit.extract.document_walker import build_canonical_scene
from dwg_audit.extract.document_walker import topology_union_allowed
from dwg_audit.extract.document_walker import walk_document


def _diagnostic_codes(scene) -> set[str]:
    return {item.code for item in scene.diagnostics}


def test_walker_reads_model_and_all_paper_layouts_and_separates_viewports() -> None:
    doc = ezdxf.new("R2018")
    model_line = doc.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "WIRE"})
    paper = doc.layout("Layout1")
    paper_text = paper.add_text("SHEET A", dxfattribs={"insert": (2, 3)})
    viewport = paper.add_viewport(
        center=(100, 80),
        size=(160, 100),
        view_center_point=(50, 40),
        view_height=120,
    )
    second = doc.layouts.new("Layout2")
    second.add_line((1, 2), (3, 4), dxfattribs={"layer": "PAPER-WIRE"})

    scene = walk_document(doc, file_id="F1")

    assert scene.schema_version == CANONICAL_SCENE_SCHEMA_VERSION
    assert scene.shadow_only
    assert scene.layouts == ("Model", "Layout1", "Layout2")
    by_handle = {item.source_handle: item for item in scene.entities}
    assert by_handle[model_line.dxf.handle].source_space == "model"
    assert by_handle[model_line.dxf.handle].layout_name == "Model"
    assert by_handle[paper_text.dxf.handle].source_space == "paper"
    assert all(item.source_entity_type != "VIEWPORT" for item in scene.entities)
    assert len(scene.layout_views) == 1
    view = scene.layout_views[0]
    assert view.source_handle == viewport.dxf.handle
    assert view.layout_name == "Layout1"
    assert view.source_space == "paper"
    assert view.center == pytest.approx((100.0, 80.0, 0.0))
    assert view.width == pytest.approx(160.0)
    assert not view.topology_union_eligible
    assert scene.source_space_counts == {"model": 1, "paper": 2}
    json.dumps(scene.to_dict())


def test_nested_insert_preserves_source_handles_path_and_composed_world_geometry() -> None:
    doc = ezdxf.new("R2018")
    inner = doc.blocks.new("INNER")
    source_line = inner.add_line((1, 2), (3, 4), dxfattribs={"layer": "WIRE"})
    outer = doc.blocks.new("OUTER")
    nested_insert = outer.add_blockref(
        "INNER",
        (10, 0),
        dxfattribs={"xscale": 2, "yscale": 2},
    )
    root_insert = doc.modelspace().add_blockref(
        "OUTER",
        (100, 20),
        dxfattribs={"rotation": 90},
    )

    scene = build_canonical_scene(doc)

    line = next(
        item
        for item in scene.entities
        if item.source_handle == source_line.dxf.handle
    )
    assert line.source_entity_type == "LINE"
    assert line.source_layer == "WIRE"
    assert line.parent_handle == nested_insert.dxf.handle
    assert line.definition_name == "INNER"
    assert line.nested_block_path == (
        f"OUTER[{root_insert.dxf.handle}]",
        f"INNER[{nested_insert.dxf.handle}]",
    )
    assert line.local_geometry["start"] == pytest.approx([1.0, 2.0, 0.0])
    assert line.world_geometry["start"] == pytest.approx([96.0, 32.0, 0.0])
    assert line.world_geometry["end"] == pytest.approx([92.0, 36.0, 0.0])
    assert line.local_transform != line.world_transform
    assert not line.topology_union_eligible

    root_record = next(
        item
        for item in scene.entities
        if item.source_handle == root_insert.dxf.handle
    )
    nested_record = next(
        item
        for item in scene.entities
        if item.source_handle == nested_insert.dxf.handle
    )
    assert root_record.world_geometry["insert"] == pytest.approx([100.0, 20.0, 0.0])
    assert nested_record.world_geometry["insert"] == pytest.approx([100.0, 30.0, 0.0])
    assert "NON_UNIFORM_INSERT_SCALE" not in _diagnostic_codes(scene)


def test_minsert_expands_every_physical_instance_with_stable_provenance() -> None:
    doc = ezdxf.new("R2018")
    block = doc.blocks.new("CELL")
    source_line = block.add_line((0, 0), (1, 0))
    array = doc.modelspace().add_blockref(
        "CELL",
        (5, 7),
        dxfattribs={
            "row_count": 2,
            "column_count": 3,
            "row_spacing": 10,
            "column_spacing": 20,
        },
    )

    scene = walk_document(doc)

    references = [
        item
        for item in scene.entities
        if item.source_handle == array.dxf.handle
        and item.primitive_kind == "BLOCK_REFERENCE"
    ]
    lines = [
        item
        for item in scene.entities
        if item.source_handle == source_line.dxf.handle
    ]
    assert len(references) == 6
    assert len(lines) == 6
    assert {item.instance_index for item in references} == set(range(6))
    assert {item.instance_index for item in lines} == set(range(6))
    assert {
        tuple(item.world_geometry["start"][:2]) for item in lines
    } == {
        (5.0, 7.0),
        (25.0, 7.0),
        (45.0, 7.0),
        (5.0, 17.0),
        (25.0, 17.0),
        (45.0, 17.0),
    }
    assert all(item.parent_handle == array.dxf.handle for item in lines)


def test_insert_attribute_world_position_is_not_transformed_twice() -> None:
    doc = ezdxf.new("R2018")
    block = doc.blocks.new("TERM")
    block.add_attdef("TAG", insert=(0, 0), height=2.5)
    insert = doc.modelspace().add_blockref("TERM", (10, 20))
    insert.add_auto_attribs({"TAG": "101"})
    source_attribute = insert.attribs[0]

    scene = walk_document(doc, file_id="F-ATTR")

    attribute = next(
        item
        for item in scene.entities
        if item.source_handle == source_attribute.dxf.handle
    )
    assert attribute.file_id == "F-ATTR"
    assert attribute.parent_handle == insert.dxf.handle
    assert attribute.local_geometry["insert"] == pytest.approx([10.0, 20.0, 0.0])
    assert attribute.world_geometry["insert"] == pytest.approx([10.0, 20.0, 0.0])


def test_virtual_expansion_failure_is_retained_and_stops_child_recursion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = ezdxf.new("R2018")
    block = doc.blocks.new("BROKEN")
    source_line = block.add_line((0, 0), (1, 0))
    insert = doc.modelspace().add_blockref("BROKEN", (0, 0))
    original = Insert.virtual_entities

    def broken(self, *, skipped_entity_callback=None, redraw_order=False):
        if self.dxf.name == "BROKEN":
            raise RuntimeError("cannot transform block")
        return original(
            self,
            skipped_entity_callback=skipped_entity_callback,
            redraw_order=redraw_order,
        )

    monkeypatch.setattr(Insert, "virtual_entities", broken)

    scene = walk_document(doc)

    assert "VIRTUAL_EXPANSION_FAILED" in _diagnostic_codes(scene)
    root = next(item for item in scene.entities if item.source_handle == insert.dxf.handle)
    assert root.source_status == "expansion_failed"
    assert not any(
        item.source_handle == source_line.dxf.handle for item in scene.entities
    )
    assert not scene.complete


def test_skipped_virtual_child_and_non_uniform_scale_are_explicit_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = ezdxf.new("R2018")
    block = doc.blocks.new("SKIP")
    source_line = block.add_line((0, 0), (1, 0))
    insert = doc.modelspace().add_blockref(
        "SKIP",
        (0, 0),
        dxfattribs={"xscale": 2, "yscale": 3},
    )
    original = Insert.virtual_entities

    def skipping(self, *, skipped_entity_callback=None, redraw_order=False):
        if self.dxf.name == "SKIP":
            if skipped_entity_callback is not None:
                skipped_entity_callback(source_line, "unsupported child transform")
            return iter(())
        return original(
            self,
            skipped_entity_callback=skipped_entity_callback,
            redraw_order=redraw_order,
        )

    monkeypatch.setattr(Insert, "virtual_entities", skipping)

    scene = walk_document(doc)

    assert {
        "VIRTUAL_ENTITY_SKIPPED",
        "NON_UNIFORM_INSERT_SCALE",
    } <= _diagnostic_codes(scene)
    skipped = next(
        item for item in scene.diagnostics if item.code == "VIRTUAL_ENTITY_SKIPPED"
    )
    assert skipped.entity_type == "LINE"
    assert skipped.details["skipped_handle"] == source_line.dxf.handle
    assert any(item.source_handle == source_line.dxf.handle for item in scene.entities)
    root = next(item for item in scene.entities if item.source_handle == insert.dxf.handle)
    assert root.source_status == "normalized"


def test_xref_is_retained_as_unresolved_source_without_loading_contents() -> None:
    doc = ezdxf.new("R2018")
    xref = doc.blocks.new("COMMON")
    xref.block.dxf.flags = 4
    xref.block.dxf.xref_path = "refs/common.dwg"
    insert = doc.modelspace().add_blockref("COMMON", (10, 20))

    scene = walk_document(doc)

    assert "XREF_UNRESOLVED_SOURCE" in _diagnostic_codes(scene)
    assert not scene.complete
    assert scene.unresolved_sources
    assert {item.block_name for item in scene.unresolved_sources} == {"COMMON"}
    assert {item.raw_path for item in scene.unresolved_sources} == {"refs/common.dwg"}
    record = next(item for item in scene.entities if item.source_handle == insert.dxf.handle)
    assert record.source_status == "unresolved_source"
    assert record.world_geometry["insert"] == pytest.approx([10.0, 20.0, 0.0])


def test_unsupported_entity_is_retained_and_non_asserted_states_never_union() -> None:
    doc = ezdxf.new("R2018")
    hatch = doc.modelspace().add_hatch()
    scene = walk_document(doc)

    record = next(item for item in scene.entities if item.source_handle == hatch.dxf.handle)
    assert record.source_entity_type == "HATCH"
    assert record.source_status == "retained_unsupported"
    assert record.local_geometry == {}
    assert not record.topology_union_eligible
    assert topology_union_allowed("UNKNOWN") is False
    assert topology_union_allowed("POSSIBLE") is False
    assert topology_union_allowed("REJECTED") is False
    assert topology_union_allowed("ASSERTED") is True
