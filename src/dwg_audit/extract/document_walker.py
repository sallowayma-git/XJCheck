"""Shadow-only, layout-aware canonical scene walker.

The legacy extractor intentionally owns the production recognition path.  This
module is a separate observation layer: it walks every model/paper layout,
retains source provenance, and normalizes geometry without producing pairs or
electrical unions.  Consumers can use the scene to measure extraction loss and
to build a future semantic/symbol layer while keeping the current engine
unchanged.

The walker does not load external references.  XREF definitions and instances
are retained as unresolved source records and emit blocking diagnostics so a
caller cannot mistake an incomplete scene for a complete drawing.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

try:  # The package depends on ezdxf, but keep import errors descriptive.
    from ezdxf.math import Matrix44
except Exception:  # pragma: no cover - exercised only in a broken runtime.
    Matrix44 = Any  # type: ignore[misc,assignment]


CANONICAL_SCENE_SCHEMA_VERSION = "canonical-scene-v1"
WALKER_ALGORITHM_VERSION = "document-walker-v1"

@dataclass(frozen=True, slots=True)
class WalkerDiagnostic:
    """A source-level warning/error retained instead of silently dropping data."""

    severity: str
    code: str
    message: str
    source_space: str | None = None
    layout_name: str | None = None
    handle: str | None = None
    entity_type: str | None = None
    block_name: str | None = None
    nested_block_path: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["nested_block_path"] = list(self.nested_block_path)
        value["details"] = _json_value(self.details)
        return value


@dataclass(frozen=True, slots=True)
class LayoutViewRecord:
    """A paper-space VIEWPORT; it is never emitted as an electrical wire."""

    record_id: str
    file_id: str
    source_space: str
    layout_name: str
    source_handle: str | None
    source_entity_type: str
    source_layer: str
    center: tuple[float, float, float] | None
    width: float | None
    height: float | None
    view_center: tuple[float, float, float] | None
    view_height: float | None
    view_direction: tuple[float, float, float] | None
    view_target: tuple[float, float, float] | None
    twist_angle_deg: float | None
    viewport_id: int | None
    topology_state: str = "UNKNOWN"

    @property
    def topology_union_eligible(self) -> bool:
        # A viewport is a paper-space camera, never electrical geometry.
        return False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["topology_union_eligible"] = self.topology_union_eligible
        return _json_value(value)


@dataclass(frozen=True, slots=True)
class CanonicalEntityRecord:
    """One source entity or one recursively expanded block entity."""

    record_id: str
    file_id: str
    source_space: str
    layout_name: str
    source_handle: str | None
    source_entity_type: str
    source_layer: str
    parent_handle: str | None
    definition_name: str | None
    nested_block_path: tuple[str, ...]
    instance_index: int | None
    primitive_kind: str
    source_status: str
    local_geometry: Mapping[str, Any] | None
    world_geometry: Mapping[str, Any] | None
    local_transform: tuple[tuple[float, ...], ...]
    world_transform: tuple[tuple[float, ...], ...]
    topology_state: str = "UNKNOWN"

    @property
    def nested_path(self) -> str:
        return "/".join(self.nested_block_path)

    @property
    def topology_union_eligible(self) -> bool:
        # Scene records are observations.  They are shadow-only even when a
        # future caller changes the evidence state to ASSERTED.
        return False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["nested_block_path"] = list(self.nested_block_path)
        value["local_transform"] = [list(row) for row in self.local_transform]
        value["world_transform"] = [list(row) for row in self.world_transform]
        value["local_geometry"] = _json_value(self.local_geometry)
        value["world_geometry"] = _json_value(self.world_geometry)
        value["topology_union_eligible"] = self.topology_union_eligible
        return value


@dataclass(frozen=True, slots=True)
class UnresolvedSourceRecord:
    """An XREF source that was deliberately not loaded by this walker."""

    file_id: str
    block_name: str
    raw_path: str | None
    reference_handle: str | None
    layout_name: str | None
    nested_block_path: tuple[str, ...] = ()
    reason: str = "XREF_NOT_LOADED"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["nested_block_path"] = list(self.nested_block_path)
        return value


@dataclass(frozen=True, slots=True)
class CanonicalScene:
    """The complete shadow observation produced by :class:`DocumentWalker`."""

    schema_version: str
    algorithm_version: str
    file_id: str
    entities: tuple[CanonicalEntityRecord, ...]
    layout_views: tuple[LayoutViewRecord, ...]
    diagnostics: tuple[WalkerDiagnostic, ...]
    unresolved_sources: tuple[UnresolvedSourceRecord, ...]
    layouts: tuple[str, ...]
    source_entity_counts: Mapping[str, int]
    source_space_counts: Mapping[str, int]
    shadow_only: bool = True

    @property
    def records(self) -> tuple[CanonicalEntityRecord, ...]:
        """Compatibility alias used by callers that call scene items records."""

        return self.entities

    @property
    def views(self) -> tuple[LayoutViewRecord, ...]:
        return self.layout_views

    @property
    def complete(self) -> bool:
        """A scene is complete only when no error-level source loss occurred."""

        return not any(item.severity.lower() == "error" for item in self.diagnostics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "algorithm_version": self.algorithm_version,
            "file_id": self.file_id,
            "shadow_only": self.shadow_only,
            "complete": self.complete,
            "layouts": list(self.layouts),
            "entities": [item.to_dict() for item in self.entities],
            "records": [item.to_dict() for item in self.entities],
            "layout_views": [item.to_dict() for item in self.layout_views],
            "views": [item.to_dict() for item in self.layout_views],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "unresolved_sources": [
                item.to_dict() for item in self.unresolved_sources
            ],
            "source_entity_counts": dict(self.source_entity_counts),
            "source_space_counts": dict(self.source_space_counts),
        }


def topology_union_allowed(state: str | None) -> bool:
    """Return whether an evidence state may form a topology union.

    The canonical scene never requests a union, but keeping this gate here
    makes the invariant explicit for downstream adapters: UNKNOWN and POSSIBLE
    are always non-union states, and only ASSERTED can pass the evidence gate.
    """

    return str(state or "UNKNOWN").upper() == "ASSERTED"


class DocumentWalker:
    """Walk an ezdxf document into a provenance-preserving shadow scene."""

    def __init__(
        self,
        document: Any,
        *,
        file_id: str | None = None,
        document_path: str | Path | None = None,
    ) -> None:
        self.document = document
        self.file_id = file_id or _document_file_id(document, document_path)
        self.document_path = str(document_path) if document_path is not None else None
        self._records: list[CanonicalEntityRecord] = []
        self._views: list[LayoutViewRecord] = []
        self._diagnostics: list[WalkerDiagnostic] = []
        self._unresolved_sources: list[UnresolvedSourceRecord] = []
        self._record_counter = 0
        self._view_counter = 0
        self._seen_xref_blocks: set[str] = set()

    def walk(self) -> CanonicalScene:
        layouts: list[str] = []
        try:
            layout_iter = iter(self.document.layouts)
        except Exception as exc:
            self._diagnostic(
                "error",
                "LAYOUT_ENUMERATION_FAILED",
                str(exc),
            )
            layout_iter = iter(())

        # Record all XREF definitions even when no INSERT happens to reference
        # them.  This makes an unresolved external source visible in census
        # output rather than dependent on page classification.
        self._scan_xref_definitions()

        while True:
            try:
                layout = next(layout_iter)
            except StopIteration:
                break
            except Exception as exc:
                self._diagnostic(
                    "error",
                    "LAYOUT_ENUMERATION_FAILED",
                    str(exc),
                )
                break

            layout_name = _layout_name(layout)
            layouts.append(layout_name)
            source_space = _layout_space(layout)
            try:
                entities = iter(layout)
            except Exception as exc:
                self._diagnostic(
                    "error",
                    "LAYOUT_SCAN_FAILED",
                    str(exc),
                    source_space=source_space,
                    layout_name=layout_name,
                )
                continue

            while True:
                try:
                    entity = next(entities)
                except StopIteration:
                    break
                except Exception as exc:
                    self._diagnostic(
                        "error",
                        "LAYOUT_SCAN_FAILED",
                        str(exc),
                        source_space=source_space,
                        layout_name=layout_name,
                    )
                    break

                entity_type = _entity_type(entity)
                if entity_type == "VIEWPORT":
                    self._emit_view(entity, layout_name, source_space)
                    continue
                self._visit(
                    entity,
                    source_space=source_space,
                    layout_name=layout_name,
                    parent_handle=None,
                    parent_local=_identity_matrix(),
                    parent_world=_identity_matrix(),
                    nested_path=(),
                    block_stack=(),
                    definition_name=None,
                    instance_index=None,
                )

        counts = Counter(item.source_entity_type for item in self._records)
        space_counts = Counter(item.source_space for item in self._records)
        return CanonicalScene(
            schema_version=CANONICAL_SCENE_SCHEMA_VERSION,
            algorithm_version=WALKER_ALGORITHM_VERSION,
            file_id=self.file_id,
            entities=tuple(self._records),
            layout_views=tuple(self._views),
            diagnostics=tuple(self._diagnostics),
            unresolved_sources=tuple(self._unresolved_sources),
            layouts=tuple(layouts),
            source_entity_counts=dict(sorted(counts.items())),
            source_space_counts=dict(sorted(space_counts.items())),
        )

    def _visit(
        self,
        entity: Any,
        *,
        source_space: str,
        layout_name: str,
        parent_handle: str | None,
        parent_local: Matrix44,
        parent_world: Matrix44,
        nested_path: tuple[str, ...],
        block_stack: tuple[str, ...],
        definition_name: str | None,
        instance_index: int | None,
    ) -> None:
        entity_type = _entity_type(entity)
        source_handle = _entity_handle(entity)
        source_layer = _entity_layer(entity)

        if entity_type == "INSERT":
            self._visit_insert(
                entity,
                source_space=source_space,
                layout_name=layout_name,
                parent_handle=parent_handle,
                parent_local=parent_local,
                parent_world=parent_world,
                nested_path=nested_path,
                block_stack=block_stack,
                instance_index=instance_index,
            )
            return

        local_geometry = _geometry(entity)
        world_entity, transform_error = _transformed_copy(entity, parent_world)
        world_geometry = _geometry(world_entity) if world_entity is not None else None
        status = "normalized"
        if not _is_supported_geometry(entity_type) or not local_geometry:
            status = "retained_unsupported"
        if transform_error is not None:
            status = "retained_unsupported"
            self._diagnostic(
                "error",
                "ENTITY_TRANSFORM_FAILED",
                transform_error,
                source_space=source_space,
                layout_name=layout_name,
                handle=source_handle,
                entity_type=entity_type,
                block_name=definition_name,
                nested_block_path=nested_path,
            )

        self._emit_entity(
            entity,
            source_space=source_space,
            layout_name=layout_name,
            parent_handle=parent_handle,
            definition_name=definition_name,
            nested_path=nested_path,
            instance_index=instance_index,
            primitive_kind=entity_type,
            source_status=status,
            local_geometry=local_geometry,
            world_geometry=world_geometry,
            local_transform=parent_local,
            world_transform=parent_world,
        )

    def _visit_insert(
        self,
        entity: Any,
        *,
        source_space: str,
        layout_name: str,
        parent_handle: str | None,
        parent_local: Matrix44,
        parent_world: Matrix44,
        nested_path: tuple[str, ...],
        block_stack: tuple[str, ...],
        instance_index: int | None,
    ) -> None:
        source_handle = _entity_handle(entity)
        block_name = _insert_name(entity)
        instances, expansion_failed = self._insert_instances(
            entity,
            source_space=source_space,
            layout_name=layout_name,
            nested_path=nested_path,
        )
        if not instances:
            instances = [(entity, instance_index)]
            expansion_failed = True

        for instance, array_index in instances:
            # The virtual MINSERT copies intentionally have no handle.  Keep
            # the original INSERT handle as the stable source identity.
            effective_index = array_index if array_index is not None else instance_index
            local_matrix, matrix_error = _entity_matrix(instance)
            if matrix_error is not None:
                local_matrix = _identity_matrix()
                self._diagnostic(
                    "error",
                    "INSERT_TRANSFORM_UNAVAILABLE",
                    matrix_error,
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=source_handle,
                    entity_type="INSERT",
                    block_name=block_name,
                    nested_block_path=nested_path,
                )
            world_matrix = local_matrix @ parent_world
            path_entry = _path_entry(block_name, source_handle)
            full_path = (*nested_path, path_entry)
            status = "expansion_failed" if expansion_failed else "normalized"
            if _non_uniform_scale(instance):
                self._diagnostic(
                    "warning",
                    "NON_UNIFORM_INSERT_SCALE",
                    "Non-uniform INSERT scaling may make child geometry lossy.",
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=source_handle,
                    entity_type="INSERT",
                    block_name=block_name,
                    nested_block_path=full_path,
                    details={"scale": _scale_values(instance)},
                )

            block = self._get_block(block_name)
            xref, xref_path = _xref_info(block)
            local_geometry = _geometry(instance)
            world_geometry = _insert_world_geometry(instance, world_matrix)
            if xref:
                status = "unresolved_source"
                self._record_unresolved_xref(
                    block_name,
                    xref_path,
                    source_handle,
                    layout_name,
                    full_path,
                )

            self._emit_entity(
                entity,
                source_space=source_space,
                layout_name=layout_name,
                parent_handle=parent_handle,
                definition_name=block_name,
                nested_path=full_path,
                instance_index=effective_index,
                primitive_kind="BLOCK_REFERENCE",
                source_status=status,
                local_geometry=local_geometry,
                world_geometry=world_geometry,
                local_transform=local_matrix,
                world_transform=world_matrix,
            )

            self._emit_insert_attributes(
                instance,
                entity,
                source_space=source_space,
                layout_name=layout_name,
                parent_handle=source_handle,
                definition_name=block_name,
                nested_path=full_path,
                instance_index=effective_index,
                # ATTRIB coordinates attached to an INSERT are already in the
                # INSERT owner's coordinate system.  Applying the INSERT's own
                # matrix again would double its translation/rotation.
                parent_local=parent_local,
                parent_world=parent_world,
            )

            if expansion_failed or xref:
                continue
            if block is None:
                self._diagnostic(
                    "error",
                    "BLOCK_DEFINITION_MISSING",
                    "INSERT references a block definition that is not available.",
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=source_handle,
                    entity_type="INSERT",
                    block_name=block_name,
                    nested_block_path=full_path,
                )
                continue
            block_key = str(block_name or "").casefold()
            if block_key in {item.casefold() for item in block_stack}:
                self._diagnostic(
                    "error",
                    "BLOCK_EXPANSION_CYCLE",
                    "Nested INSERT cycle detected; recursion stopped.",
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=source_handle,
                    entity_type="INSERT",
                    block_name=block_name,
                    nested_block_path=full_path,
                )
                continue
            try:
                children = iter(block)
            except Exception as exc:
                self._diagnostic(
                    "error",
                    "BLOCK_DEFINITION_SCAN_FAILED",
                    str(exc),
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=source_handle,
                    entity_type="INSERT",
                    block_name=block_name,
                    nested_block_path=full_path,
                )
                continue
            next_stack = (*block_stack, str(block_name or ""))
            while True:
                try:
                    child = next(children)
                except StopIteration:
                    break
                except Exception as exc:
                    self._diagnostic(
                        "error",
                        "BLOCK_DEFINITION_SCAN_FAILED",
                        str(exc),
                        source_space=source_space,
                        layout_name=layout_name,
                        handle=source_handle,
                        entity_type="INSERT",
                        block_name=block_name,
                        nested_block_path=full_path,
                    )
                    break
                self._visit(
                    child,
                    source_space=source_space,
                    layout_name=layout_name,
                    parent_handle=source_handle,
                    parent_local=local_matrix,
                    parent_world=world_matrix,
                    nested_path=full_path,
                    block_stack=next_stack,
                    definition_name=block_name,
                    instance_index=effective_index,
                )

    def _insert_instances(
        self,
        entity: Any,
        *,
        source_space: str,
        layout_name: str,
        nested_path: tuple[str, ...],
    ) -> tuple[list[tuple[Any, int | None]], bool]:
        count = _mcount(entity)
        if count <= 1:
            instances = [(entity, None)]
        else:
            try:
                instances = [
                    (item, index) for index, item in enumerate(entity.multi_insert())
                ]
            except Exception as exc:
                self._diagnostic(
                    "error",
                    "MINSERT_EXPANSION_FAILED",
                    str(exc),
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=_entity_handle(entity),
                    entity_type="INSERT",
                    block_name=_insert_name(entity),
                    nested_block_path=nested_path,
                )
                return [], True
            if not instances:
                self._diagnostic(
                    "error",
                    "MINSERT_EXPANSION_EMPTY",
                    "MINSERT reported instances but yielded no virtual inserts.",
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=_entity_handle(entity),
                    entity_type="INSERT",
                    block_name=_insert_name(entity),
                    nested_block_path=nested_path,
                )
                return [], True

        # Probe ezdxf's own expander solely for diagnostics.  The actual walk
        # uses source block definitions so original handles and nested paths
        # remain stable even when virtual copies have no handle.
        for instance, _ in instances:
            probe = getattr(instance, "virtual_entities", None)
            if not callable(probe):
                continue
            skipped: list[tuple[Any, str]] = []

            def on_skipped(child: Any, reason: str) -> None:
                skipped.append((child, str(reason)))

            try:
                list(probe(skipped_entity_callback=on_skipped))
            except Exception as exc:
                self._diagnostic(
                    "error",
                    "VIRTUAL_EXPANSION_FAILED",
                    str(exc),
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=_entity_handle(entity),
                    entity_type="INSERT",
                    block_name=_insert_name(entity),
                    nested_block_path=nested_path,
                )
                return instances, True
            for child, reason in skipped:
                self._diagnostic(
                    "error",
                    "VIRTUAL_ENTITY_SKIPPED",
                    reason,
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=_entity_handle(entity),
                    entity_type=_entity_type(child),
                    block_name=_insert_name(entity),
                    nested_block_path=nested_path,
                    details={"skipped_handle": _entity_handle(child)},
                )
        return instances, False

    def _emit_insert_attributes(
        self,
        instance: Any,
        source_entity: Any,
        *,
        source_space: str,
        layout_name: str,
        parent_handle: str | None,
        definition_name: str | None,
        nested_path: tuple[str, ...],
        instance_index: int | None,
        parent_local: Matrix44,
        parent_world: Matrix44,
    ) -> None:
        attributes = tuple(getattr(instance, "attribs", ()) or ())
        if not attributes and instance is not source_entity:
            attributes = tuple(getattr(source_entity, "attribs", ()) or ())
        for attribute in attributes:
            local_geometry = _geometry(attribute)
            world_entity, transform_error = _transformed_copy(attribute, parent_world)
            world_geometry = (
                _geometry(world_entity) if world_entity is not None else None
            )
            status = "normalized" if transform_error is None else "retained_unsupported"
            if transform_error is not None:
                self._diagnostic(
                    "error",
                    "ATTRIBUTE_TRANSFORM_FAILED",
                    transform_error,
                    source_space=source_space,
                    layout_name=layout_name,
                    handle=_entity_handle(attribute),
                    entity_type="ATTRIB",
                    block_name=definition_name,
                    nested_block_path=nested_path,
                )
            self._emit_entity(
                attribute,
                source_space=source_space,
                layout_name=layout_name,
                parent_handle=parent_handle,
                definition_name=definition_name,
                nested_path=nested_path,
                instance_index=instance_index,
                primitive_kind="ATTRIB",
                source_status=status,
                local_geometry=local_geometry,
                world_geometry=world_geometry,
                local_transform=parent_local,
                world_transform=parent_world,
            )

    def _emit_entity(
        self,
        entity: Any,
        *,
        source_space: str,
        layout_name: str,
        parent_handle: str | None,
        definition_name: str | None,
        nested_path: tuple[str, ...],
        instance_index: int | None,
        primitive_kind: str,
        source_status: str,
        local_geometry: Mapping[str, Any] | None,
        world_geometry: Mapping[str, Any] | None,
        local_transform: Matrix44,
        world_transform: Matrix44,
    ) -> None:
        self._record_counter += 1
        self._records.append(
            CanonicalEntityRecord(
                record_id=f"CE{self._record_counter:08d}",
                file_id=self.file_id,
                source_space=source_space,
                layout_name=layout_name,
                source_handle=_entity_handle(entity),
                source_entity_type=_entity_type(entity),
                source_layer=_entity_layer(entity),
                parent_handle=parent_handle,
                definition_name=definition_name,
                nested_block_path=nested_path,
                instance_index=instance_index,
                primitive_kind=primitive_kind,
                source_status=source_status,
                local_geometry=_json_value(local_geometry),
                world_geometry=_json_value(world_geometry),
                local_transform=_matrix_tuple(local_transform),
                world_transform=_matrix_tuple(world_transform),
            )
        )

    def _emit_view(
        self,
        entity: Any,
        layout_name: str,
        source_space: str,
    ) -> None:
        self._view_counter += 1
        self._views.append(
            LayoutViewRecord(
                record_id=f"LV{self._view_counter:08d}",
                file_id=self.file_id,
                source_space=source_space,
                layout_name=layout_name,
                source_handle=_entity_handle(entity),
                source_entity_type="VIEWPORT",
                source_layer=_entity_layer(entity),
                center=_point(getattr(entity.dxf, "center", None)),
                width=_float_attr(entity, "width"),
                height=_float_attr(entity, "height"),
                view_center=_point(getattr(entity.dxf, "view_center_point", None)),
                view_height=_float_attr(entity, "view_height"),
                view_direction=_point(getattr(entity.dxf, "view_direction", None)),
                view_target=_point(getattr(entity.dxf, "view_target", None)),
                twist_angle_deg=_float_attr(entity, "twist_angle"),
                viewport_id=_int_attr(entity, "id"),
            )
        )

    def _scan_xref_definitions(self) -> None:
        try:
            blocks = iter(self.document.blocks)
        except Exception:
            return
        while True:
            try:
                block = next(blocks)
            except StopIteration:
                break
            except Exception:
                break
            name = str(getattr(block, "name", "") or "")
            is_xref, raw_path = _xref_info(block)
            if not is_xref or name.casefold() in self._seen_xref_blocks:
                continue
            self._seen_xref_blocks.add(name.casefold())
            self._record_unresolved_xref(name, raw_path, None, None, ())

    def _record_unresolved_xref(
        self,
        block_name: str | None,
        raw_path: str | None,
        reference_handle: str | None,
        layout_name: str | None,
        nested_path: tuple[str, ...],
    ) -> None:
        if not block_name:
            return
        candidate = UnresolvedSourceRecord(
            file_id=self.file_id,
            block_name=str(block_name),
            raw_path=raw_path,
            reference_handle=reference_handle,
            layout_name=layout_name,
            nested_block_path=nested_path,
        )
        if candidate not in self._unresolved_sources:
            self._unresolved_sources.append(candidate)
        self._diagnostic(
            "error",
            "XREF_UNRESOLVED_SOURCE",
            "External reference was detected but not loaded by the shadow walker.",
            layout_name=layout_name,
            handle=reference_handle,
            entity_type="INSERT" if reference_handle else None,
            block_name=str(block_name),
            nested_block_path=nested_path,
            details={"xref_path": raw_path},
        )

    def _get_block(self, block_name: str | None) -> Any | None:
        if not block_name:
            return None
        try:
            return self.document.blocks.get(block_name)
        except Exception:
            try:
                return self.document.blocks[block_name]
            except Exception:
                return None

    def _diagnostic(self, severity: str, code: str, message: str, **kwargs: Any) -> None:
        self._diagnostics.append(
            WalkerDiagnostic(
                severity=severity,
                code=code,
                message=message,
                **kwargs,
            )
        )


def walk_document(
    document: Any,
    *,
    file_id: str | None = None,
    document_path: str | Path | None = None,
) -> CanonicalScene:
    """Build a shadow canonical scene from an ezdxf-like document."""

    return DocumentWalker(
        document,
        file_id=file_id,
        document_path=document_path,
    ).walk()


def build_canonical_scene(
    document: Any,
    *,
    file_id: str | None = None,
    document_path: str | Path | None = None,
) -> CanonicalScene:
    """Descriptive alias for :func:`walk_document`."""

    return walk_document(document, file_id=file_id, document_path=document_path)


def _document_file_id(document: Any, document_path: str | Path | None) -> str:
    if document_path is not None:
        return Path(document_path).stem
    value = getattr(document, "filename", None)
    if value:
        try:
            return Path(str(value)).stem
        except (TypeError, ValueError):
            pass
    return "document"


def _layout_name(layout: Any) -> str:
    return str(getattr(layout, "name", "<unnamed-layout>") or "<unnamed-layout>")


def _layout_space(layout: Any) -> str:
    try:
        if bool(getattr(layout, "is_modelspace")):
            return "model"
    except Exception:
        pass
    try:
        if bool(getattr(layout, "is_any_paperspace")):
            return "paper"
    except Exception:
        pass
    return "layout"


def _entity_type(entity: Any) -> str:
    try:
        value = str(entity.dxftype() or "<UNKNOWN>").upper()
    except Exception:
        return "<UNKNOWN>"
    return value or "<UNKNOWN>"


def _entity_handle(entity: Any) -> str | None:
    try:
        value = getattr(entity.dxf, "handle", None)
    except Exception:
        return None
    return str(value) if value else None


def _entity_layer(entity: Any) -> str:
    try:
        return str(getattr(entity.dxf, "layer", "0") or "0")
    except Exception:
        return "0"


def _insert_name(entity: Any) -> str | None:
    try:
        value = getattr(entity.dxf, "name", None)
    except Exception:
        return None
    return str(value) if value else None


def _path_entry(block_name: str | None, handle: str | None) -> str:
    name = str(block_name or "<unnamed>")
    return f"{name}[{handle or 'virtual'}]"


def _identity_matrix() -> Matrix44:
    return Matrix44() if Matrix44 is not Any else None  # type: ignore[return-value]


def _matrix_tuple(matrix: Matrix44) -> tuple[tuple[float, ...], ...]:
    try:
        return tuple(
            tuple(float(item) for item in row) for row in matrix.rows()
        )
    except Exception:
        return tuple(tuple(float(item) for item in row) for row in _identity_matrix().rows())


def _entity_matrix(entity: Any) -> tuple[Matrix44, str | None]:
    try:
        return entity.matrix44(), None
    except Exception as exc:
        return _identity_matrix(), str(exc)


def _transformed_copy(entity: Any, matrix: Matrix44) -> tuple[Any | None, str | None]:
    try:
        copy = entity.copy()
    except Exception:
        # A few test doubles expose transform but not copy; do not mutate a
        # source document entity in that case.
        return None, "entity copy is unavailable"
    try:
        copy.transform(matrix)
    except Exception as exc:
        return None, str(exc)
    return copy, None


def _mcount(entity: Any) -> int:
    try:
        return max(int(getattr(entity, "mcount")), 1)
    except Exception:
        try:
            rows = int(getattr(entity.dxf, "row_count", 1) or 1)
            columns = int(getattr(entity.dxf, "column_count", 1) or 1)
            return max(rows * columns, 1)
        except Exception:
            return 1


def _non_uniform_scale(entity: Any) -> bool:
    # Electrical geometry is normalized in the XY plane.  A default zscale of
    # 1 must not make an otherwise uniform 2D INSERT look non-uniform.
    xscale, yscale, _ = _scale_values(entity)
    return abs(abs(xscale) - abs(yscale)) > 1e-12


def _scale_values(entity: Any) -> tuple[float, float, float]:
    values: list[float] = []
    for name in ("xscale", "yscale", "zscale"):
        try:
            values.append(float(getattr(entity.dxf, name, 1.0) or 1.0))
        except Exception:
            values.append(1.0)
    return tuple(values)  # type: ignore[return-value]


def _xref_info(block: Any) -> tuple[bool, str | None]:
    if block is None:
        return False, None
    record = getattr(block, "block", None) or getattr(block, "block_record", None)
    if record is None:
        return False, None
    try:
        marker = getattr(record, "is_xref")
        is_xref = bool(marker() if callable(marker) else marker)
    except Exception:
        try:
            is_xref = bool(int(getattr(record.dxf, "flags", 0) or 0) & 4)
        except Exception:
            is_xref = False
    try:
        value = getattr(record.dxf, "xref_path", None)
        raw_path = str(value) if value else None
    except Exception:
        raw_path = None
    return is_xref, raw_path


def _is_supported_geometry(entity_type: str) -> bool:
    return entity_type in {
        "LINE",
        "LWPOLYLINE",
        "POLYLINE",
        "ARC",
        "CIRCLE",
        "ELLIPSE",
        "SPLINE",
        "XLINE",
        "RAY",
        "TEXT",
        "MTEXT",
        "ATTRIB",
        "ATTDEF",
        "POINT",
    }


def _geometry(entity: Any) -> dict[str, Any]:
    """Return JSON-compatible local/world geometry for common DXF entities."""

    if entity is None:
        return {}
    entity_type = _entity_type(entity)
    try:
        dxf = entity.dxf
        if entity_type == "LINE":
            return {"kind": "line", "start": _point(dxf.start), "end": _point(dxf.end)}
        if entity_type in {"ARC", "CIRCLE"}:
            value: dict[str, Any] = {
                "kind": entity_type.lower(),
                "center": _point(dxf.center),
                "radius": float(dxf.radius),
            }
            if entity_type == "ARC":
                value.update(
                    start_angle=float(dxf.start_angle),
                    end_angle=float(dxf.end_angle),
                )
            return value
        if entity_type == "ELLIPSE":
            return {
                "kind": "ellipse",
                "center": _point(dxf.center),
                "major_axis": _point(dxf.major_axis),
                "ratio": float(dxf.ratio),
                "start_param": float(getattr(dxf, "start_param", 0.0)),
                "end_param": float(getattr(dxf, "end_param", 6.283185307179586)),
            }
        if entity_type in {"TEXT", "ATTRIB", "ATTDEF"}:
            return {
                "kind": "text",
                "insert": _point(dxf.insert),
                "text": str(getattr(dxf, "text", "") or ""),
                "height": _optional_float(dxf, "height"),
                "rotation_deg": _optional_float(dxf, "rotation"),
            }
        if entity_type == "MTEXT":
            return {
                "kind": "mtext",
                "insert": _point(dxf.insert),
                "text": str(getattr(dxf, "text", "") or ""),
                "char_height": _optional_float(dxf, "char_height"),
                "rotation_deg": _optional_float(dxf, "rotation"),
            }
        if entity_type == "POINT":
            return {"kind": "point", "location": _point(dxf.location)}
        if entity_type in {"LWPOLYLINE", "POLYLINE"}:
            return _polyline_geometry(entity)
        if entity_type in {"XLINE", "RAY"}:
            return {
                "kind": entity_type.lower(),
                "base": _point(getattr(dxf, "basepoint", getattr(dxf, "start", None))),
                "unit_vector": _point(
                    getattr(dxf, "unitvector", getattr(dxf, "direction", None))
                ),
            }
        if entity_type == "SPLINE":
            return {
                "kind": "spline",
                "control_points": [_point(item) for item in getattr(dxf, "control_points", ())],
                "fit_points": [_point(item) for item in getattr(dxf, "fit_points", ())],
                "degree": int(getattr(dxf, "degree", 0) or 0),
            }
        if entity_type == "INSERT":
            return {
                "kind": "block_reference",
                "insert": _point(dxf.insert),
                "name": str(getattr(dxf, "name", "") or ""),
                "rotation_deg": _optional_float(dxf, "rotation"),
                "scale": list(_scale_values(entity)),
            }
    except Exception:
        return {}
    return {}


def _insert_world_geometry(entity: Any, matrix: Matrix44) -> dict[str, Any]:
    """Describe a block instance from its composed matrix without double transform."""

    try:
        origin = matrix.transform((0.0, 0.0, 0.0))
        xaxis = matrix.transform_direction((1.0, 0.0, 0.0))
        yaxis = matrix.transform_direction((0.0, 1.0, 0.0))
        rotation = math.degrees(math.atan2(xaxis.y, xaxis.x))
        return {
            "kind": "block_reference",
            "insert": _point(origin),
            "name": str(getattr(entity.dxf, "name", "") or ""),
            "rotation_deg": rotation,
            "scale": [float(xaxis.magnitude), float(yaxis.magnitude), 1.0],
        }
    except Exception:
        return {
            "kind": "block_reference",
            "name": str(getattr(getattr(entity, "dxf", None), "name", "") or ""),
        }


def _polyline_geometry(entity: Any) -> dict[str, Any]:
    entity_type = _entity_type(entity)
    if entity_type == "LWPOLYLINE":
        try:
            points = []
            for item in entity.get_points("xyseb"):
                points.append(
                    {
                        "x": float(item[0]),
                        "y": float(item[1]),
                        "start_width": float(item[2]),
                        "end_width": float(item[3]),
                        "bulge": float(item[4]),
                    }
                )
            return {
                "kind": "lwpolyline",
                "points": points,
                "closed": bool(getattr(entity, "closed", False)),
            }
        except Exception:
            return {"kind": "lwpolyline", "points": []}
    try:
        points = []
        for vertex in entity.vertices:
            points.append(
                {
                    "location": _point(vertex.dxf.location),
                    "bulge": float(getattr(vertex.dxf, "bulge", 0.0) or 0.0),
                }
            )
        return {
            "kind": "polyline",
            "points": points,
            "closed": bool(getattr(entity, "is_closed", False)),
        }
    except Exception:
        return {"kind": "polyline", "points": []}


def _point(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        return (float(value.x), float(value.y), float(getattr(value, "z", 0.0)))
    except Exception:
        try:
            values = tuple(value)
            return (
                float(values[0]),
                float(values[1]),
                float(values[2]) if len(values) > 2 else 0.0,
            )
        except Exception:
            return None


def _float_attr(entity: Any, name: str) -> float | None:
    try:
        value = getattr(entity.dxf, name, None)
        return float(value) if value is not None else None
    except Exception:
        return None


def _optional_float(dxf: Any, name: str) -> float | None:
    try:
        value = getattr(dxf, name, None)
        return float(value) if value is not None else None
    except Exception:
        return None


def _int_attr(entity: Any, name: str) -> int | None:
    try:
        value = getattr(entity.dxf, name, None)
        return int(value) if value is not None else None
    except Exception:
        return None


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    return str(value)


__all__ = [
    "CANONICAL_SCENE_SCHEMA_VERSION",
    "WALKER_ALGORITHM_VERSION",
    "CanonicalEntityRecord",
    "CanonicalScene",
    "DocumentWalker",
    "LayoutViewRecord",
    "UnresolvedSourceRecord",
    "WalkerDiagnostic",
    "build_canonical_scene",
    "topology_union_allowed",
    "walk_document",
]
