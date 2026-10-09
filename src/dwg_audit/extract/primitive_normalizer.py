from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ezdxf.path import make_path
from ezdxf.path import from_hatch
from dwg_audit.extract.text_geometry import cad_text_geometry


PRIMITIVE_SCHEMA_VERSION = "primitive-segment-v1"
PRIMITIVE_ALGORITHM_VERSION = "ezdxf-normalizer-v1"


@dataclass(slots=True)
class PrimitiveSegment:
    primitive_id: str
    schema_version: str
    algorithm_version: str
    sheet_id: str
    file_id: str
    layout_name: str
    entity_handle: str
    parent_handle: str | None
    source_entity_type: str
    primitive_kind: str
    definition_name: str | None
    nested_path: str
    layer: str
    layer_role_candidate: str
    layer_role_reason_code: str
    linetype: str
    segment_index: int
    local_geometry_json: str
    world_geometry_json: str
    transform_json: str
    bbox_min_x: float | None
    bbox_min_y: float | None
    bbox_max_x: float | None
    bbox_max_y: float | None
    reader_backend: str
    reader_version: str | None
    source_status: str
    preview_geometry_json: str = "{}"
    visible: bool = True


def normalize_document_primitives(
    document: Any,
    *,
    sheet_id: str,
    file_id: str,
    reader_backend: str,
    reader_version: str | None,
    layout_name: str = "Model",
) -> list[PrimitiveSegment]:
    """Normalize modelspace entities without feeding legacy recognition."""
    records: list[PrimitiveSegment] = []

    def entity_visible(entity: Any, effective_layer: str) -> bool:
        if bool(getattr(entity.dxf, "invisible", 0)):
            return False
        if entity.dxftype() in {"ATTRIB", "ATTDEF"} and entity.is_invisible:
            return False
        if document.layers.has_entry(effective_layer):
            layer = document.layers.get(effective_layer)
            if layer.is_off() or layer.is_frozen():
                return False
        return True

    def emit(
        source: Any,
        world: Any,
        *,
        parent_handle: str | None,
        definition_name: str | None,
        path: tuple[str, ...],
        segment_index: int = 0,
        source_status: str = "normalized",
        local_geometry_override: dict[str, Any] | None = None,
        world_geometry_override: dict[str, Any] | None = None,
        primitive_kind_override: str | None = None,
        transform_override: dict[str, Any] | None = None,
        inherited_visible: bool = True,
    ) -> None:
        source_type = source.dxftype()
        world_type = world.dxftype()
        local_geometry = local_geometry_override or _geometry(source)
        world_geometry = world_geometry_override or _geometry(world)
        bbox = _geometry_bbox(world_geometry)
        preview_geometry = {}
        if world_type in {"CIRCLE", "ARC", "ELLIPSE"} and not world.dxf.extrusion.isclose((0, 0, 1)):
            if world_type == "ELLIPSE":
                axis_x, axis_y = world.dxf.major_axis, world.minor_axis
            else:
                ocs = world.ocs()
                axis_x = ocs.to_wcs((world.dxf.radius, 0, 0))
                axis_y = ocs.to_wcs((0, world.dxf.radius, 0))
            preview_geometry = {"curve_axis_x": _point(axis_x), "curve_axis_y": _point(axis_y)}
        if world_type in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
            preview_geometry = cad_text_geometry(world)
        if world_type == "HATCH" and bool(world.dxf.solid_fill):
            try:
                preview_geometry = {"rings": [
                    [_point(p) for p in path.flattening(distance=0.01, segments=16)]
                    for path in from_hatch(world)
                ]}
            except Exception:
                preview_geometry = {"diagnostic": "HATCH_BOUNDARY_UNAVAILABLE"}
        handle = str(getattr(source.dxf, "handle", "") or "virtual")
        records.append(
            PrimitiveSegment(
                primitive_id=f"PS{len(records) + 1:08d}",
                schema_version=PRIMITIVE_SCHEMA_VERSION,
                algorithm_version=PRIMITIVE_ALGORITHM_VERSION,
                sheet_id=sheet_id,
                file_id=file_id,
                layout_name=layout_name,
                entity_handle=handle,
                parent_handle=parent_handle,
                source_entity_type=source_type,
                primitive_kind=primitive_kind_override or world_type,
                definition_name=definition_name,
                nested_path="/".join(path),
                layer=str(getattr(world.dxf, "layer", "0") or "0"),
                layer_role_candidate="UNKNOWN",
                layer_role_reason_code="LAYER_ROLE_UNCLASSIFIED",
                linetype=str(getattr(world.dxf, "linetype", "BYLAYER") or "BYLAYER"),
                segment_index=segment_index,
                local_geometry_json=_json(local_geometry),
                world_geometry_json=_json(world_geometry),
                transform_json=_json(
                    transform_override
                    if transform_override is not None
                    else (_insert_transform(world) if world_type == "INSERT" else {})
                ),
                bbox_min_x=bbox[0] if bbox else None,
                bbox_min_y=bbox[1] if bbox else None,
                bbox_max_x=bbox[2] if bbox else None,
                bbox_max_y=bbox[3] if bbox else None,
                reader_backend=reader_backend,
                reader_version=reader_version,
                source_status=source_status,
                preview_geometry_json=_json(preview_geometry),
                visible=inherited_visible and not bool(getattr(world.dxf, "invisible", 0)),
            )
        )

    def visit(
        source: Any,
        world: Any,
        *,
        parent_handle: str | None = None,
        definition_name: str | None = None,
        path: tuple[str, ...] = (),
        transform_chain: tuple[dict[str, Any], ...] = (),
        inherited_visible: bool = True,
        inherited_layer: str = "0",
    ) -> None:
        entity_type = world.dxftype()
        layer = str(getattr(world.dxf, "layer", "0") or "0")
        effective_layer = inherited_layer if layer == "0" else layer
        inherited_visible = inherited_visible and entity_visible(world, effective_layer)
        source_handle = str(getattr(source.dxf, "handle", "") or "virtual")
        if entity_type == "INSERT":
            name = str(getattr(world.dxf, "name", "") or "")
            insert_path = (*path, f"{name}[{source_handle}]")
            insert_transform = _insert_transform(world)
            child_transform_chain = (*transform_chain, insert_transform)
            emit(
                source,
                world,
                parent_handle=parent_handle,
                definition_name=name or definition_name,
                path=insert_path,
                transform_override={"chain": child_transform_chain},
                inherited_visible=inherited_visible,
            )
            for index, attrib in enumerate(getattr(world, "attribs", ())):
                emit(
                    attrib,
                    attrib,
                    parent_handle=source_handle,
                    definition_name=name,
                    path=insert_path,
                    segment_index=index,
                    transform_override={"chain": child_transform_chain},
                    inherited_visible=inherited_visible and entity_visible(
                        attrib, effective_layer if attrib.dxf.layer == "0" else attrib.dxf.layer
                    ),
                )
            try:
                source_children = list(source.block())
                world_children = list(world.virtual_entities())
            except Exception:
                return
            for index, world_child in enumerate(world_children):
                source_child = world_child.source_of_copy or (source_children[index] if index < len(source_children) else world_child)
                visit(
                    source_child,
                    world_child,
                    parent_handle=source_handle,
                    definition_name=name,
                    path=insert_path,
                    transform_chain=child_transform_chain,
                    inherited_visible=inherited_visible and not bool(getattr(world.dxf, "invisible", 0)),
                    inherited_layer=effective_layer,
                )
            return

        if entity_type in {"LWPOLYLINE", "POLYLINE"}:
            inherited_visible = inherited_visible and not bool(getattr(world.dxf, "invisible", 0))
            try:
                source_parts = list(source.virtual_entities())
                world_parts = list(world.virtual_entities())
            except Exception:
                source_parts = []
                world_parts = []
            if world_parts:
                for index, world_part in enumerate(world_parts):
                    source_part = source_parts[index] if index < len(source_parts) else world_part
                    emit(
                        source,
                        world_part,
                        parent_handle=parent_handle,
                        definition_name=definition_name,
                        path=path,
                        segment_index=index,
                        local_geometry_override=_geometry(source_part),
                        transform_override={"chain": transform_chain},
                        inherited_visible=inherited_visible,
                    )
                return
            local_segments = _flattened_segments(source)
            world_segments = _flattened_segments(world)
            if world_segments:
                for index, world_geometry in enumerate(world_segments):
                    local_geometry = (
                        local_segments[index]
                        if index < len(local_segments)
                        else world_geometry
                    )
                    emit(
                        source,
                        world,
                        parent_handle=parent_handle,
                        definition_name=definition_name,
                        path=path,
                        segment_index=index,
                        local_geometry_override=local_geometry,
                        world_geometry_override=world_geometry,
                        primitive_kind_override="LINE",
                        transform_override={"chain": transform_chain},
                        inherited_visible=inherited_visible,
                    )
                return

        supported = entity_type in {
            "LINE",
            "ARC",
            "CIRCLE",
            "ELLIPSE",
            "ATTRIB",
        }
        emit(
            source,
            world,
            parent_handle=parent_handle,
            definition_name=definition_name,
            path=path,
            source_status="normalized" if supported else "unsupported_retained",
            transform_override={"chain": transform_chain},
            inherited_visible=inherited_visible,
        )

    for entity in document.modelspace():
        visit(entity, entity)
    return records


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _point(value: Any) -> list[float]:
    return [float(value.x), float(value.y), float(getattr(value, "z", 0.0))]


def _geometry(entity: Any) -> dict[str, Any]:
    entity_type = entity.dxftype()
    if entity_type == "LINE":
        return {"start": _point(entity.dxf.start), "end": _point(entity.dxf.end)}
    if entity_type in {"ARC", "CIRCLE"}:
        value: dict[str, Any] = {
            "center": _point(entity.ocs().to_wcs(entity.dxf.center)),
            "radius": float(entity.dxf.radius),
        }
        if entity_type == "ARC":
            value.update(
                start_angle=float(entity.dxf.start_angle),
                end_angle=float(entity.dxf.end_angle),
            )
        return value
    if entity_type == "ELLIPSE":
        return {
            "center": _point(entity.dxf.center),
            "major_axis": _point(entity.dxf.major_axis),
            "ratio": float(entity.dxf.ratio),
            "start_param": float(entity.dxf.start_param),
            "end_param": float(entity.dxf.end_param),
        }
    if entity_type in {"ATTRIB", "TEXT", "MTEXT", "INSERT"}:
        insert = getattr(entity.dxf, "insert", None)
        return {"insert": _point(insert)} if insert is not None else {}
    return {}


def _insert_transform(entity: Any) -> dict[str, Any]:
    insert = getattr(entity.dxf, "insert", None)
    value = {
        "translation": _point(insert) if insert is not None else [0.0, 0.0, 0.0],
        "rotation_deg": float(getattr(entity.dxf, "rotation", 0.0) or 0.0),
        "scale": [
            float(getattr(entity.dxf, "xscale", 1.0) or 1.0),
            float(getattr(entity.dxf, "yscale", 1.0) or 1.0),
            float(getattr(entity.dxf, "zscale", 1.0) or 1.0),
        ],
    }
    try:
        value["matrix44"] = [
            [float(item) for item in row] for row in entity.matrix44().rows()
        ]
    except Exception:
        pass
    return value


def _flattened_segments(entity: Any) -> list[dict[str, Any]]:
    try:
        points = list(make_path(entity).flattening(distance=0.01, segments=16))
    except Exception:
        return []
    return [
        {"start": _point(start), "end": _point(end)}
        for start, end in zip(points, points[1:], strict=False)
    ]


def _geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    if "start" in geometry and "end" in geometry:
        xs = [geometry["start"][0], geometry["end"][0]]
        ys = [geometry["start"][1], geometry["end"][1]]
        return min(xs), min(ys), max(xs), max(ys)
    if "center" in geometry and "radius" in geometry:
        x, y = geometry["center"][:2]
        radius = geometry["radius"]
        return x - radius, y - radius, x + radius, y + radius
    if "center" in geometry and "major_axis" in geometry:
        x, y = geometry["center"][:2]
        major = geometry["major_axis"]
        major_radius = (major[0] ** 2 + major[1] ** 2) ** 0.5
        radius = max(major_radius, major_radius * abs(geometry["ratio"]))
        return x - radius, y - radius, x + radius, y + radius
    if "insert" in geometry:
        x, y = geometry["insert"][:2]
        return x, y, x, y
    return None
