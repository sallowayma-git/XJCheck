from __future__ import annotations

import json

import ezdxf

from dwg_audit.extract.primitive_normalizer import normalize_document_primitives


def _world(record) -> dict:
    return json.loads(record.world_geometry_json)


def test_normalizes_required_entity_families_with_provenance() -> None:
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (2, 0), dxfattribs={"layer": "WIRE"})
    msp.add_lwpolyline([(0, 1), (1, 1), (1, 2)])
    polyline = msp.add_polyline2d([(2, 1), (3, 1), (3, 2)])
    polyline.close()
    msp.add_arc((5, 5), radius=2, start_angle=0, end_angle=90)
    msp.add_circle((8, 8), radius=3)

    records = normalize_document_primitives(
        doc,
        sheet_id="S001",
        file_id="F001",
        reader_backend="ezdxf",
        reader_version="test",
    )

    kinds = {record.primitive_kind for record in records}
    assert {"LINE", "ARC", "CIRCLE"} <= kinds
    source_types = {record.source_entity_type for record in records}
    assert {"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE"} <= source_types
    assert all(
        record.entity_handle != "virtual"
        for record in records
        if record.source_entity_type in {"LWPOLYLINE", "POLYLINE"}
    )
    assert all(record.sheet_id == "S001" for record in records)
    assert all(record.file_id == "F001" for record in records)
    assert all(record.reader_backend == "ezdxf" for record in records)
    assert all(record.layer_role_candidate == "UNKNOWN" for record in records)
    assert all(
        record.layer_role_reason_code == "LAYER_ROLE_UNCLASSIFIED"
        for record in records
    )
    assert all(record.entity_handle for record in records)
    assert all(record.bbox_min_x is not None for record in records)


def test_nested_insert_preserves_path_transform_and_world_geometry() -> None:
    doc = ezdxf.new()
    inner = doc.blocks.new("INNER")
    inner.add_line((0, 0), (2, 0), dxfattribs={"layer": "PORT"})
    inner.add_circle((1, 1), radius=0.5)
    outer = doc.blocks.new("OUTER")
    outer.add_blockref(
        "INNER",
        (1, 0),
        dxfattribs={"rotation": 90, "xscale": -1, "yscale": 2},
    )
    doc.modelspace().add_blockref("OUTER", (10, 20), dxfattribs={"rotation": 90})

    records = normalize_document_primitives(
        doc,
        sheet_id="S001",
        file_id="F001",
        reader_backend="ezdxf",
        reader_version="test",
    )

    inserts = [record for record in records if record.primitive_kind == "INSERT"]
    lines = [record for record in records if record.primitive_kind == "LINE"]
    ellipses = [record for record in records if record.primitive_kind == "ELLIPSE"]
    assert len(inserts) == 2
    assert len(lines) == 1
    assert len(ellipses) == 1
    assert ellipses[0].source_entity_type == "CIRCLE"
    assert "OUTER[" in lines[0].nested_path
    assert "INNER[" in lines[0].nested_path
    assert lines[0].definition_name == "INNER"
    assert lines[0].parent_handle is not None
    world = _world(lines[0])
    assert world["start"][:2] == [10.0, 21.0]
    assert world["end"][:2] == [12.0, 21.0]
    transform = json.loads(inserts[1].transform_json)["chain"][-1]
    assert transform["scale"][:2] == [-1.0, 2.0]
    assert len(transform["matrix44"]) == 4
    assert len(json.loads(lines[0].transform_json)["chain"]) == 2


def test_unknown_entity_is_retained_without_becoming_connectivity() -> None:
    doc = ezdxf.new()
    doc.modelspace().add_point((1, 2))

    records = normalize_document_primitives(
        doc,
        sheet_id="S001",
        file_id="F001",
        reader_backend="ezdxf",
        reader_version=None,
    )

    assert len(records) == 1
    assert records[0].primitive_kind == "POINT"
    assert records[0].source_status == "unsupported_retained"
