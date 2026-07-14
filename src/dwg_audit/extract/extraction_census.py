"""Document-level extraction completeness census.

The legacy extractor intentionally exposes only a small, model-space view of a
DXF document.  This module records what is present in the source document
before that view is built.  It is deliberately independent from the legacy
recognition models so it can be used by readers, conversion diagnostics, and
future document walkers without changing pair generation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:  # ezdxf is a runtime dependency, but keep duck-typed tests importable.
    from ezdxf import units as _ezdxf_units
except Exception:  # pragma: no cover - only used in a broken runtime.
    _ezdxf_units = None


CENSUS_SCHEMA_VERSION = "extraction-census-v2"

# These are the entity types consumed by the current production extractor.
# Primitive normalization may retain more geometry, but retained shadow
# primitives are not yet part of the legacy semantic recognition contract.
DEFAULT_SUPPORTED_ENTITY_TYPES = frozenset(
    {
        "TEXT",
        "MTEXT",
        "ATTRIB",
        "ATTDEF",
        "LINE",
        "LWPOLYLINE",
        "POLYLINE",
        "INSERT",
    }
)

# Entities retained with usable geometry or source records by the current
# primitive normalizer. This is deliberately broader than the legacy semantic
# extractor and lets the census report both coverage tiers independently.
DEFAULT_SHADOW_SUPPORTED_ENTITY_TYPES = frozenset(
    {
        *DEFAULT_SUPPORTED_ENTITY_TYPES,
        "ARC",
        "CIRCLE",
        "ELLIPSE",
    }
)

PROXY_ENTITY_TYPES = frozenset(
    {
        "ACAD_PROXY_ENTITY",
        "ACAD_PROXY_OBJECT",
        "PROXY_ENTITY",
        "PROXY_OBJECT",
    }
)


@dataclass(frozen=True, slots=True)
class CensusDiagnostic:
    severity: str
    code: str
    message: str
    layout_name: str | None = None
    block_name: str | None = None
    handle: str | None = None
    entity_type: str | None = None
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LayoutCensus:
    name: str
    kind: str
    is_modelspace: bool
    is_paperspace: bool
    consumed_by_extractor: bool
    entity_count: int
    native_entity_count: int
    viewport_count: int
    entity_counts: dict[str, int]
    insert_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class XrefDefinitionCensus:
    block_name: str
    raw_path: str | None
    flags: int | None
    reference_count: int
    resolution_status: str
    candidate_paths: tuple[str, ...] = ()
    resolved_path: str | None = None
    content_loaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_paths"] = list(self.candidate_paths)
        return value


@dataclass(frozen=True, slots=True)
class VirtualExpansionIssue:
    code: str
    message: str
    layout_name: str | None
    block_name: str | None
    handle: str | None
    entity_type: str | None = None
    nested_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExtractionCensus:
    schema_version: str
    status: str
    complete: bool
    units: int | None
    units_name: str | None
    scale_status: str
    layouts: tuple[LayoutCensus, ...]
    entity_counts_by_layout: dict[str, dict[str, int]]
    block_definition_count: int
    block_definition_entity_counts: dict[str, dict[str, int]]
    model_space_entity_count: int
    paper_space_entity_count: int
    paper_space_native_entity_count: int
    paper_space_viewport_count: int
    unprocessed_layout_entity_count: int
    unprocessed_layout_native_entity_count: int
    block_reference_count: int
    block_instance_count: int
    nested_block_reference_count: int
    nested_block_max_depth: int
    xref_definitions: tuple[XrefDefinitionCensus, ...]
    missing_xrefs: tuple[str, ...]
    proxy_entity_count: int
    proxy_entity_counts: dict[str, int]
    unsupported_entity_count: int
    unsupported_entity_counts: dict[str, int]
    semantic_coverage_complete: bool
    shadow_unsupported_entity_count: int
    shadow_unsupported_entity_counts: dict[str, int]
    shadow_coverage_complete: bool
    virtual_expansion_attempts: int
    virtual_expansion_failures: tuple[VirtualExpansionIssue, ...]
    virtual_expansion_warnings: tuple[VirtualExpansionIssue, ...]
    warnings: tuple[CensusDiagnostic, ...] = ()
    errors: tuple[CensusDiagnostic, ...] = ()
    conversion_warnings: tuple[str, ...] = ()
    # Phase 126: measured OCS/WCS and nested block unit fidelity.  These fields
    # are evidence only; they never authorize millimetre geometry mutation.
    ocs_wcs_status: str = "UNMEASURED"
    ocs_identity_count: int = 0
    ocs_non_identity_count: int = 0
    ocs_unreadable_count: int = 0
    nested_block_units_status: str = "UNMEASURED"
    nested_block_units_aligned_count: int = 0
    nested_block_units_mismatch_count: int = 0
    nested_block_units_unitless_count: int = 0
    nested_block_units_unreadable_count: int = 0

    @property
    def entity_counts_by_type(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for layout_counts in self.entity_counts_by_layout.values():
            counts.update(layout_counts)
        for block_counts in self.block_definition_entity_counts.values():
            counts.update(block_counts)
        return dict(sorted(counts.items()))

    @property
    def xref_count(self) -> int:
        return len(self.xref_definitions)

    @property
    def virtual_entity_failures(self) -> tuple[VirtualExpansionIssue, ...]:
        return self.virtual_expansion_failures

    @property
    def virtual_entity_warnings(self) -> tuple[VirtualExpansionIssue, ...]:
        return self.virtual_expansion_warnings

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible, stable representation."""

        value: dict[str, Any] = {
            "schema_version": self.schema_version,
            "status": self.status,
            "complete": self.complete,
            "units": self.units,
            "units_name": self.units_name,
            "scale_status": self.scale_status,
            "layouts": [item.to_dict() for item in self.layouts],
            "entity_counts_by_layout": {
                name: dict(counts)
                for name, counts in self.entity_counts_by_layout.items()
            },
            "entity_counts_by_type": self.entity_counts_by_type,
            "block_definition_count": self.block_definition_count,
            "block_definition_entity_counts": {
                name: dict(counts)
                for name, counts in self.block_definition_entity_counts.items()
            },
            "model_space_entity_count": self.model_space_entity_count,
            "paper_space_entity_count": self.paper_space_entity_count,
            "paper_space_native_entity_count": self.paper_space_native_entity_count,
            "paper_space_viewport_count": self.paper_space_viewport_count,
            "unprocessed_layout_entity_count": self.unprocessed_layout_entity_count,
            "unprocessed_layout_native_entity_count": self.unprocessed_layout_native_entity_count,
            "block_reference_count": self.block_reference_count,
            "block_instance_count": self.block_instance_count,
            "nested_block_reference_count": self.nested_block_reference_count,
            "nested_block_max_depth": self.nested_block_max_depth,
            "xref_count": self.xref_count,
            "xref_definitions": [item.to_dict() for item in self.xref_definitions],
            "missing_xrefs": list(self.missing_xrefs),
            "proxy_entity_count": self.proxy_entity_count,
            "proxy_entity_counts": dict(self.proxy_entity_counts),
            "unsupported_entity_count": self.unsupported_entity_count,
            "unsupported_entity_counts": dict(self.unsupported_entity_counts),
            "semantic_coverage_complete": self.semantic_coverage_complete,
            "shadow_unsupported_entity_count": self.shadow_unsupported_entity_count,
            "shadow_unsupported_entity_counts": dict(
                self.shadow_unsupported_entity_counts
            ),
            "shadow_coverage_complete": self.shadow_coverage_complete,
            "virtual_expansion_attempts": self.virtual_expansion_attempts,
            "virtual_expansion_failures": [
                item.to_dict() for item in self.virtual_expansion_failures
            ],
            "virtual_entity_failures": [
                item.to_dict() for item in self.virtual_entity_failures
            ],
            "virtual_expansion_warnings": [
                item.to_dict() for item in self.virtual_expansion_warnings
            ],
            "virtual_entity_warnings": [
                item.to_dict() for item in self.virtual_entity_warnings
            ],
            "warnings": [item.to_dict() for item in self.warnings],
            "errors": [item.to_dict() for item in self.errors],
            "conversion_warnings": list(self.conversion_warnings),
            "ocs_wcs_status": self.ocs_wcs_status,
            "ocs_identity_count": self.ocs_identity_count,
            "ocs_non_identity_count": self.ocs_non_identity_count,
            "ocs_unreadable_count": self.ocs_unreadable_count,
            "nested_block_units_status": self.nested_block_units_status,
            "nested_block_units_aligned_count": self.nested_block_units_aligned_count,
            "nested_block_units_mismatch_count": self.nested_block_units_mismatch_count,
            "nested_block_units_unitless_count": self.nested_block_units_unitless_count,
            "nested_block_units_unreadable_count": self.nested_block_units_unreadable_count,
        }
        return value


@dataclass(slots=True)
class _InsertContext:
    entity: Any
    layout_name: str | None
    block_name: str | None
    nested_path: str


def _entity_type(entity: Any) -> str:
    try:
        value = entity.dxftype()
    except Exception:
        return "<UNKNOWN>"
    value = str(value or "<UNKNOWN>").upper()
    return value or "<UNKNOWN>"


def _entity_handle(entity: Any) -> str | None:
    try:
        value = getattr(entity.dxf, "handle", None)
    except Exception:
        return None
    return str(value) if value else None


def _is_insert(entity: Any) -> bool:
    return _entity_type(entity) == "INSERT"


def _is_proxy(entity_type: str) -> bool:
    return entity_type in PROXY_ENTITY_TYPES or "PROXY" in entity_type


def _layout_kind(layout: Any) -> tuple[str, bool, bool]:
    try:
        is_model = bool(getattr(layout, "is_modelspace", False))
    except Exception:
        is_model = False
    try:
        is_paper = bool(getattr(layout, "is_any_paperspace", False))
    except Exception:
        is_paper = False
    if is_model:
        return "model", True, False
    if is_paper:
        return "paper", False, True
    return "layout", False, False


def _layout_name(layout: Any) -> str:
    try:
        value = getattr(layout, "name", "<unnamed-layout>")
    except Exception:
        value = "<unnamed-layout>"
    return str(value or "<unnamed-layout>")


def _block_name(block: Any) -> str:
    try:
        value = getattr(block, "name", "<unnamed-block>")
    except Exception:
        value = "<unnamed-block>"
    return str(value or "<unnamed-block>")


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _unit_name(value: int | None) -> str | None:
    if value is None:
        return None
    if _ezdxf_units is not None:
        try:
            return str(_ezdxf_units.unit_name(value))
        except Exception:
            pass
    return "Unknown"


_IDENTITY_EXTRUSION_EPS = 1e-9


def _extrusion_vector(entity: Any) -> tuple[float, float, float] | None:
    """Read an entity extrusion vector when the DXF attribute is available."""

    try:
        dxf = getattr(entity, "dxf", None)
        if dxf is None:
            return None
        if hasattr(dxf, "hasattr"):
            try:
                if not bool(dxf.hasattr("extrusion")) and not hasattr(dxf, "extrusion"):
                    # Some duck-typed test doubles lack extrusion entirely.
                    raw = getattr(dxf, "extrusion", None)
                    if raw is None:
                        return None
            except Exception:
                pass
        raw = getattr(dxf, "extrusion", None)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        values = tuple(float(item) for item in raw)
    except Exception:
        try:
            values = (float(raw[0]), float(raw[1]), float(raw[2]))
        except Exception:
            return None
    if len(values) != 3:
        return None
    return values  # type: ignore[return-value]


def _is_identity_extrusion(vector: tuple[float, float, float]) -> bool:
    x, y, z = vector
    return (
        abs(x) <= _IDENTITY_EXTRUSION_EPS
        and abs(y) <= _IDENTITY_EXTRUSION_EPS
        and abs(z - 1.0) <= _IDENTITY_EXTRUSION_EPS
    )


def _block_units_value(block: Any) -> tuple[int | None, bool]:
    """Return ``(units, readable)`` for a block definition.

    AutoCAD block units of ``0`` mean unitless / inherit drawing units.
    """

    try:
        raw = getattr(block, "units", None)
        if raw is not None:
            return _safe_int(raw), True
    except Exception:
        pass
    record = getattr(block, "block_record", None)
    if record is None:
        record = getattr(block, "block", None)
    if record is None:
        return None, False
    try:
        dxf = getattr(record, "dxf", None)
        if dxf is None:
            return None, False
        raw = getattr(dxf, "units", None)
        if raw is None:
            # Missing attribute is treated as unitless inherit (0), not unreadable.
            return 0, True
        return _safe_int(raw), True
    except Exception:
        return None, False


def _classify_ocs_wcs_status(
    *,
    identity_count: int,
    non_identity_count: int,
    unreadable_count: int,
) -> str:
    measured = identity_count + non_identity_count
    if measured == 0 and unreadable_count == 0:
        return "UNMEASURED"
    if measured == 0 and unreadable_count > 0:
        return "MEASUREMENT_FAILED"
    if non_identity_count > 0:
        return "MEASURED_NON_IDENTITY"
    if unreadable_count > 0:
        # Identity samples exist but some entities could not be read.
        return "MEASURED_IDENTITY_PARTIAL"
    return "MEASURED_IDENTITY"


def _classify_nested_block_units_status(
    *,
    aligned_count: int,
    mismatch_count: int,
    unitless_count: int,
    unreadable_count: int,
) -> str:
    total = aligned_count + mismatch_count + unitless_count + unreadable_count
    if total == 0:
        return "MEASURED_ALIGNED"
    if unreadable_count and aligned_count + mismatch_count + unitless_count == 0:
        return "MEASUREMENT_FAILED"
    if mismatch_count > 0:
        return "MEASURED_MISMATCH"
    if unitless_count > 0 and aligned_count == 0:
        return "MEASURED_UNITLESS"
    if unreadable_count > 0:
        return "MEASURED_ALIGNED_PARTIAL"
    return "MEASURED_ALIGNED"


def _xref_info(block: Any) -> tuple[bool, int | None, str | None]:
    """Read xref flags defensively across ezdxf versions and test doubles."""

    record = getattr(block, "block", None)
    if record is None:
        record = getattr(block, "block_record", None)
    is_xref = False
    flags: int | None = None
    raw_path: str | None = None
    try:
        marker = getattr(record, "is_xref")
        is_xref = bool(marker() if callable(marker) else marker)
    except Exception:
        is_xref = False
    try:
        flags = _safe_int(getattr(record.dxf, "flags", None))
        raw = getattr(record.dxf, "xref_path", None)
        raw_path = str(raw) if raw else None
    except Exception:
        pass
    return is_xref, flags, raw_path


def _candidate_paths(
    raw_path: str | None,
    *,
    document_path: Path | None,
    search_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    if not raw_path:
        return ()
    raw = Path(raw_path).expanduser()
    values: list[Path] = []
    if raw.is_absolute():
        values.append(raw)
    else:
        if document_path is not None:
            values.append(document_path.parent / raw)
        values.extend(path / raw for path in search_paths)
        # AutoCAD commonly stores a basename in the xref record while the
        # actual file is located in one of the configured search directories.
        values.extend(path / raw.name for path in search_paths)
        values.append(raw)

    # Missing extensions are common in hand-authored test fixtures.  Add the
    # two formats without replacing the original candidate.
    expanded: list[Path] = []
    for value in values:
        expanded.append(value)
        if value.suffix == "":
            expanded.extend((value.with_suffix(".dwg"), value.with_suffix(".dxf")))
    result: list[Path] = []
    seen: set[str] = set()
    for value in expanded:
        key = str(value).casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return tuple(result)


def _path_exists(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _mcount(entity: Any) -> int:
    try:
        value = int(getattr(entity, "mcount"))
        return max(value, 1)
    except Exception:
        try:
            rows = int(getattr(entity.dxf, "row_count", 1) or 1)
            columns = int(getattr(entity.dxf, "column_count", 1) or 1)
            return max(rows * columns, 1)
        except Exception:
            return 1


def _insert_name(entity: Any) -> str | None:
    try:
        value = getattr(entity.dxf, "name", None)
        return str(value) if value else None
    except Exception:
        return None


def _attached_attributes(entity: Any) -> Iterable[Any]:
    return tuple(getattr(entity, "attribs", ()) or ())


def _definition_entities(block: Any) -> Iterable[Any]:
    return block


def _has_expandable_definition_content(counts: dict[str, int]) -> bool:
    """ATTDEF-only blocks are represented by INSERT ATTRIB records instead."""

    return any(
        count
        for entity_type, count in counts.items()
        if entity_type not in {"ATTDEF", "ATTRIB", "SEQEND"}
    )


def build_extraction_census(
    document: Any,
    *,
    document_path: str | Path | None = None,
    supported_entity_types: Collection[str] = DEFAULT_SUPPORTED_ENTITY_TYPES,
    shadow_supported_entity_types: Collection[str] = DEFAULT_SHADOW_SUPPORTED_ENTITY_TYPES,
    consumed_layout_names: Collection[str] | None = ("Model",),
    xref_search_paths: Iterable[str | Path] = (),
    loaded_xref_names: Collection[str] = (),
    path_exists: Callable[[Path], bool] | None = None,
    conversion_warnings: Iterable[str] = (),
) -> ExtractionCensus:
    """Build a fail-closed census from an ezdxf-like document.

    ``consumed_layout_names`` describes the layouts the caller's recognition
    engine actually consumes.  The default mirrors today's ModelSpace-only
    pipeline and deliberately marks populated PaperSpace layouts incomplete.
    Pass ``None`` when all layouts have been integrated by a future walker.
    ``loaded_xref_names`` is explicit because merely finding an external file
    is not proof that its entities were merged into the scene.
    """

    supported = {str(item).upper() for item in supported_entity_types}
    shadow_supported = {
        str(item).upper() for item in shadow_supported_entity_types
    }
    consumed = (
        None
        if consumed_layout_names is None
        else {str(item).casefold() for item in consumed_layout_names}
    )
    exists = path_exists or _path_exists
    source_path = Path(document_path) if document_path is not None else None
    if source_path is None:
        try:
            candidate = getattr(document, "filename", None)
        except Exception:
            candidate = None
        if candidate:
            try:
                source_path = Path(candidate)
            except (TypeError, ValueError):
                source_path = None
    search_paths = tuple(Path(item).expanduser() for item in xref_search_paths)
    loaded_names = {str(item).casefold() for item in loaded_xref_names}
    conversion_warning_values = tuple(str(item) for item in conversion_warnings)

    layouts: list[LayoutCensus] = []
    entity_counts_by_layout: dict[str, dict[str, int]] = {}
    block_definition_entity_counts: dict[str, dict[str, int]] = {}
    layout_inserts: list[_InsertContext] = []
    definition_inserts: list[_InsertContext] = []
    block_layouts: dict[str, Any] = {}
    semantic_unsupported: Counter[str] = Counter()
    shadow_unsupported: Counter[str] = Counter()
    all_proxy: Counter[str] = Counter()
    errors: list[CensusDiagnostic] = []
    warnings: list[CensusDiagnostic] = []
    virtual_failures: list[VirtualExpansionIssue] = []
    virtual_warnings: list[VirtualExpansionIssue] = []
    virtual_attempts = 0
    ocs_identity_count = 0
    ocs_non_identity_count = 0
    ocs_unreadable_count = 0
    nested_block_units_aligned_count = 0
    nested_block_units_mismatch_count = 0
    nested_block_units_unitless_count = 0
    nested_block_units_unreadable_count = 0

    for message in conversion_warning_values:
        warnings.append(
            CensusDiagnostic(
                "warning",
                "CONVERSION_WARNING",
                message,
            )
        )

    def observe_entity(
        entity: Any,
        *,
        counts: Counter[str],
        owner_kind: str,
        owner_name: str,
        insert_sink: list[_InsertContext],
        nested_path: str,
    ) -> str:
        nonlocal ocs_identity_count, ocs_non_identity_count, ocs_unreadable_count
        entity_type = _entity_type(entity)
        counts[entity_type] += 1
        if entity_type != "VIEWPORT" and entity_type not in supported:
            semantic_unsupported[entity_type] += 1
        if entity_type != "VIEWPORT" and entity_type not in shadow_supported:
            shadow_unsupported[entity_type] += 1
        if _is_proxy(entity_type):
            all_proxy[entity_type] += 1
        if entity_type == "<UNKNOWN>":
            errors.append(
                CensusDiagnostic(
                    "error",
                    "ENTITY_TYPE_UNREADABLE",
                    "Entity type could not be read.",
                    layout_name=owner_name if owner_kind == "layout" else None,
                    block_name=owner_name if owner_kind == "block" else None,
                    handle=_entity_handle(entity),
                )
            )
        # Measure OCS extrusion for geometry-bearing entity types.  Missing
        # extrusion attributes are treated as the DXF default identity (0,0,1).
        if entity_type not in {"VIEWPORT", "<UNKNOWN>"}:
            extrusion = _extrusion_vector(entity)
            if extrusion is None:
                # Duck-typed test doubles and entities without extrusion are
                # assumed identity-default only when the entity has a dxf bag;
                # otherwise count as unreadable so status stays fail-closed.
                try:
                    has_dxf = getattr(entity, "dxf", None) is not None
                except Exception:
                    has_dxf = False
                if has_dxf:
                    ocs_identity_count += 1
                else:
                    ocs_unreadable_count += 1
            elif _is_identity_extrusion(extrusion):
                ocs_identity_count += 1
            else:
                ocs_non_identity_count += 1
        if entity_type == "INSERT":
            name = _insert_name(entity)
            insert_sink.append(
                _InsertContext(
                    entity=entity,
                    layout_name=owner_name if owner_kind == "layout" else None,
                    block_name=name,
                    nested_path=nested_path,
                )
            )
        return entity_type

    # Scan each layout directly.  A failed iteration is retained as an error,
    # and any entities observed before the failure remain diagnostic evidence.
    try:
        layout_iter = iter(document.layouts)
    except Exception as exc:
        errors.append(
            CensusDiagnostic("error", "LAYOUT_ENUMERATION_FAILED", str(exc))
        )
        layout_iter = iter(())

    while True:
        try:
            layout = next(layout_iter)
        except StopIteration:
            break
        except Exception as exc:
            errors.append(
                CensusDiagnostic("error", "LAYOUT_ENUMERATION_FAILED", str(exc))
            )
            break

        name = _layout_name(layout)
        kind, is_model, is_paper = _layout_kind(layout)
        counts: Counter[str] = Counter()
        inserts_before = len(layout_inserts)
        try:
            for index, entity in enumerate(layout):
                observe_entity(
                    entity,
                    counts=counts,
                    owner_kind="layout",
                    owner_name=name,
                    insert_sink=layout_inserts,
                    nested_path=f"{name}/{index}",
                )
                # Attached ATTRIB records are stored on INSERT rather than as
                # layout members, so census them explicitly as content.
                for attr_index, attrib in enumerate(_attached_attributes(entity)):
                    observe_entity(
                        attrib,
                        counts=counts,
                        owner_kind="layout",
                        owner_name=name,
                        insert_sink=[],
                        nested_path=f"{name}/{index}/ATTRIB:{attr_index}",
                    )
        except Exception as exc:
            errors.append(
                CensusDiagnostic(
                    "error",
                    "LAYOUT_SCAN_FAILED",
                    str(exc),
                    layout_name=name,
                )
            )
        entity_count = sum(counts.values())
        viewport_count = counts.get("VIEWPORT", 0)
        native_entity_count = entity_count - viewport_count
        consumed_here = consumed is None or name.casefold() in consumed
        layouts.append(
            LayoutCensus(
                name=name,
                kind=kind,
                is_modelspace=is_model,
                is_paperspace=is_paper,
                consumed_by_extractor=consumed_here,
                entity_count=entity_count,
                native_entity_count=native_entity_count,
                viewport_count=viewport_count,
                entity_counts=dict(sorted(counts.items())),
                insert_count=len(layout_inserts) - inserts_before,
            )
        )
        entity_counts_by_layout[name] = dict(sorted(counts.items()))
        if not consumed_here and native_entity_count:
            errors.append(
                CensusDiagnostic(
                    "error",
                    "LAYOUT_NOT_CONSUMED",
                    "Layout contains entities but is not in the caller's consumed layout set.",
                    layout_name=name,
                )
            )
        if not consumed_here and viewport_count:
            warnings.append(
                CensusDiagnostic(
                    "warning",
                    "VIEWPORT_LAYOUT_NOT_INTERPRETED",
                    "PaperSpace viewport definitions are present but layout viewport mapping is not interpreted.",
                    layout_name=name,
                    entity_type="VIEWPORT",
                )
            )

    if not layouts:
        errors.append(
            CensusDiagnostic("error", "NO_LAYOUTS", "Document exposes no readable layouts.")
        )

    # Scan user block definitions once, excluding the layout backing blocks.
    try:
        block_iter = iter(document.blocks)
    except Exception as exc:
        errors.append(CensusDiagnostic("error", "BLOCK_ENUMERATION_FAILED", str(exc)))
        block_iter = iter(())

    while True:
        try:
            block = next(block_iter)
        except StopIteration:
            break
        except Exception as exc:
            errors.append(CensusDiagnostic("error", "BLOCK_ENUMERATION_FAILED", str(exc)))
            break
        try:
            is_layout_block = bool(getattr(block, "is_any_layout", False))
        except Exception as exc:
            is_layout_block = False
            errors.append(
                CensusDiagnostic(
                    "error",
                    "BLOCK_LAYOUT_KIND_FAILED",
                    str(exc),
                    block_name=_block_name(block),
                )
            )
        if is_layout_block:
            continue
        name = _block_name(block)
        key = name.casefold()
        block_layouts[key] = block
        # Nested block unit measurement is independent of entity expansion.
        # Unit value 0 means unitless / inherit drawing units.
        block_units, block_units_readable = _block_units_value(block)
        if not block_units_readable:
            nested_block_units_unreadable_count += 1
        else:
            # Drawing units are not finalized until later; stash raw for a second
            # pass after units are known.  For now classify relative to temporary
            # document.units when available, else defer via unitless bucket.
            try:
                provisional_drawing_units = _safe_int(getattr(document, "units", None))
            except Exception:
                provisional_drawing_units = None
            if block_units in (None, 0):
                if provisional_drawing_units not in (None, 0):
                    # Inherit declared drawing units → aligned for scale fidelity.
                    nested_block_units_aligned_count += 1
                else:
                    nested_block_units_unitless_count += 1
            elif provisional_drawing_units in (None, 0):
                # Block declares units while drawing is unitless → mismatch risk.
                nested_block_units_mismatch_count += 1
            elif block_units == provisional_drawing_units:
                nested_block_units_aligned_count += 1
            else:
                nested_block_units_mismatch_count += 1
        counts: Counter[str] = Counter()
        try:
            for index, entity in enumerate(_definition_entities(block)):
                observe_entity(
                    entity,
                    counts=counts,
                    owner_kind="block",
                    owner_name=name,
                    insert_sink=definition_inserts,
                    nested_path=f"{name}/{index}",
                )
                for attr_index, attrib in enumerate(_attached_attributes(entity)):
                    observe_entity(
                        attrib,
                        counts=counts,
                        owner_kind="block",
                        owner_name=name,
                        insert_sink=[],
                        nested_path=f"{name}/{index}/ATTRIB:{attr_index}",
                    )
        except Exception as exc:
            errors.append(
                CensusDiagnostic(
                    "error",
                    "BLOCK_SCAN_FAILED",
                    str(exc),
                    block_name=name,
                )
            )
        block_definition_entity_counts[name] = dict(sorted(counts.items()))

    # Count block graph depth from visible layout roots.  This is deliberately
    # independent from virtual entity expansion: it remains useful when a
    # block cannot be transformed.
    graph: dict[str, set[str]] = defaultdict(set)
    for item in definition_inserts:
        if item.block_name:
            owner = item.nested_path.split("/", 1)[0].casefold()
            graph[owner].add(item.block_name.casefold())
    max_depth = 0

    def visit_depth(name: str, depth: int, active: tuple[str, ...]) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        if name in active:
            errors.append(
                CensusDiagnostic(
                    "error",
                    "BLOCK_REFERENCE_CYCLE",
                    "Block reference graph contains a cycle.",
                    block_name=name,
                    path="/".join((*active, name)),
                )
            )
            return
        if name not in block_layouts:
            errors.append(
                CensusDiagnostic(
                    "error",
                    "BLOCK_DEFINITION_MISSING",
                    "INSERT references a block definition that is not present.",
                    block_name=name,
                )
            )
            return
        for child in sorted(graph.get(name, ())):
            visit_depth(child, depth + 1, (*active, name))

    for item in layout_inserts:
        if item.block_name:
            visit_depth(item.block_name.casefold(), 1, ())

    # Resolve xref records after the block inventory is available so reference
    # counts include both layout and nested block INSERTs.
    reference_counts: Counter[str] = Counter()
    for item in (*layout_inserts, *definition_inserts):
        if item.block_name:
            reference_counts[item.block_name.casefold()] += 1
    xrefs: list[XrefDefinitionCensus] = []
    missing_xrefs: list[str] = []
    for key, block in sorted(block_layouts.items()):
        is_xref, flags, raw_path = _xref_info(block)
        if not is_xref:
            continue
        candidates = _candidate_paths(
            raw_path,
            document_path=source_path,
            search_paths=search_paths,
        )
        resolved: Path | None = None
        for candidate in candidates:
            try:
                candidate_exists = bool(exists(candidate))
            except Exception as exc:
                errors.append(
                    CensusDiagnostic(
                        "error",
                        "XREF_PATH_CHECK_FAILED",
                        str(exc),
                        block_name=_block_name(block),
                        path=str(candidate),
                    )
                )
                candidate_exists = False
            if candidate_exists:
                resolved = candidate
                break
        if not raw_path:
            resolution_status = "missing_path"
        elif resolved is not None:
            resolution_status = "resolved"
        elif candidates:
            resolution_status = "missing"
        else:
            resolution_status = "unresolved"
        content_loaded = key in loaded_names
        record = XrefDefinitionCensus(
            block_name=_block_name(block),
            raw_path=raw_path,
            flags=flags,
            reference_count=reference_counts.get(key, 0),
            resolution_status=resolution_status,
            candidate_paths=tuple(str(item) for item in candidates),
            resolved_path=str(resolved) if resolved is not None else None,
            content_loaded=content_loaded,
        )
        xrefs.append(record)
        if resolution_status != "resolved":
            missing_xrefs.append(record.block_name)
            errors.append(
                CensusDiagnostic(
                    "error",
                    "XREF_NOT_RESOLVED",
                    f"XREF path could not be resolved ({resolution_status}).",
                    block_name=record.block_name,
                    path=raw_path,
                )
            )
        if not content_loaded:
            errors.append(
                CensusDiagnostic(
                    "error",
                    "XREF_CONTENT_NOT_LOADED",
                    "XREF file may exist, but its entities were not loaded into this census.",
                    block_name=record.block_name,
                    path=raw_path,
                )
            )

    # Exercise virtual expansion for every stored INSERT.  The callback is
    # essential: ezdxf can skip unsupported children without raising.
    for item in (*layout_inserts, *definition_inserts):
        entity = item.entity
        instances: list[Any]
        count = _mcount(entity)
        if count > 1:
            try:
                instances = list(entity.multi_insert())
            except Exception as exc:
                instances = [entity]
                issue = VirtualExpansionIssue(
                    "MINSERT_EXPANSION_FAILED",
                    str(exc),
                    item.layout_name,
                    item.block_name,
                    _entity_handle(entity),
                    nested_path=item.nested_path,
                )
                virtual_failures.append(issue)
                errors.append(
                    CensusDiagnostic(
                        "error",
                        issue.code,
                        issue.message,
                        layout_name=item.layout_name,
                        block_name=item.block_name,
                        handle=_entity_handle(entity),
                        entity_type="INSERT",
                        path=item.nested_path,
                    )
                )
        else:
            instances = [entity]
        for instance in instances:
            virtual_attempts += 1
            skipped: list[tuple[Any, str]] = []

            def on_skipped(child: Any, reason: str) -> None:
                skipped.append((child, str(reason)))

            try:
                expanded = list(instance.virtual_entities(skipped_entity_callback=on_skipped))
            except Exception as exc:
                issue = VirtualExpansionIssue(
                    "VIRTUAL_EXPANSION_FAILED",
                    str(exc),
                    item.layout_name,
                    item.block_name,
                    _entity_handle(instance) or _entity_handle(entity),
                    entity_type="INSERT",
                    nested_path=item.nested_path,
                )
                virtual_failures.append(issue)
                errors.append(
                    CensusDiagnostic(
                        "error",
                        issue.code,
                        issue.message,
                        layout_name=item.layout_name,
                        block_name=item.block_name,
                        handle=issue.handle,
                        entity_type="INSERT",
                        path=item.nested_path,
                    )
                )
                continue
            for child, reason in skipped:
                child_type = _entity_type(child)
                issue = VirtualExpansionIssue(
                    "VIRTUAL_ENTITY_SKIPPED",
                    reason,
                    item.layout_name,
                    item.block_name,
                    _entity_handle(instance) or _entity_handle(entity),
                    entity_type=child_type,
                    nested_path=item.nested_path,
                )
                virtual_warnings.append(issue)
                errors.append(
                    CensusDiagnostic(
                        "error",
                        issue.code,
                        issue.message,
                        layout_name=item.layout_name,
                        block_name=item.block_name,
                        handle=issue.handle,
                        entity_type=child_type,
                        path=item.nested_path,
                    )
                )
            if not expanded and item.block_name:
                definition_counts = next(
                    (
                        counts
                        for name, counts in block_definition_entity_counts.items()
                        if name.casefold() == item.block_name.casefold()
                    ),
                    {},
                )
                if _has_expandable_definition_content(definition_counts) and item.block_name.casefold() not in {
                    record.block_name.casefold() for record in xrefs
                }:
                    issue = VirtualExpansionIssue(
                        "EMPTY_VIRTUAL_EXPANSION",
                        "INSERT expansion returned no entities for a non-empty block definition.",
                        item.layout_name,
                        item.block_name,
                        _entity_handle(instance) or _entity_handle(entity),
                        entity_type="INSERT",
                        nested_path=item.nested_path,
                    )
                    virtual_warnings.append(issue)
                    errors.append(
                        CensusDiagnostic(
                            "error",
                            issue.code,
                            issue.message,
                            layout_name=item.layout_name,
                            block_name=item.block_name,
                            handle=issue.handle,
                            entity_type="INSERT",
                            path=item.nested_path,
                        )
                    )
            try:
                if not bool(getattr(instance, "has_uniform_scaling")):
                    virtual_warnings.append(
                        VirtualExpansionIssue(
                            "NON_UNIFORM_INSERT_SCALE",
                            "Non-uniform INSERT scaling can make virtual text geometry inaccurate.",
                            item.layout_name,
                            item.block_name,
                            _entity_handle(instance) or _entity_handle(entity),
                            entity_type="INSERT",
                            nested_path=item.nested_path,
                        )
                    )
            except Exception:
                pass

    # Coverage is tiered. Legacy semantic gaps and shadow-retention gaps remain
    # visible without automatically making common decorative/source entities
    # fatal. Proxy/custom objects remain blocking because their content is
    # opaque to both tiers.
    for entity_type, count in sorted(semantic_unsupported.items()):
        warnings.append(
            CensusDiagnostic(
                "warning",
                "SEMANTIC_UNSUPPORTED_ENTITY_TYPE",
                f"{count} stored entity/ies are outside the legacy semantic extractor set.",
                entity_type=entity_type,
            )
        )
    for entity_type, count in sorted(shadow_unsupported.items()):
        warnings.append(
            CensusDiagnostic(
                "warning",
                "SHADOW_UNSUPPORTED_ENTITY_TYPE",
                f"{count} stored entity/ies are not normalized into a supported shadow primitive.",
                entity_type=entity_type,
            )
        )
    if all_proxy:
        errors.append(
            CensusDiagnostic(
                "error",
                "PROXY_ENTITY_PRESENT",
                "Proxy/custom entities require a reader-specific adapter before clean extraction can be claimed.",
            )
        )
    if not layouts:
        errors.append(
            CensusDiagnostic("error", "NO_READABLE_CONTENT", "No layout content was readable.")
        )

    try:
        raw_units = getattr(document, "units", None)
    except Exception as exc:
        raw_units = None
        errors.append(CensusDiagnostic("error", "UNITS_READ_FAILED", str(exc)))
    units = _safe_int(raw_units)
    units_name = _unit_name(units)
    if units is None or units == 0:
        warnings.append(
            CensusDiagnostic(
                "warning",
                "UNITS_UNSPECIFIED",
                "Drawing units are missing or unitless; coordinate tolerances cannot be certified.",
            )
        )
    scale_status = "DECLARED" if units not in (None, 0) else "UNRESOLVED"

    model_count = sum(item.entity_count for item in layouts if item.is_modelspace)
    paper_count = sum(item.entity_count for item in layouts if item.is_paperspace)
    paper_native_count = sum(
        item.native_entity_count for item in layouts if item.is_paperspace
    )
    paper_viewport_count = sum(
        item.viewport_count for item in layouts if item.is_paperspace
    )
    unprocessed_count = sum(
        item.entity_count for item in layouts if not item.consumed_by_extractor
    )
    unprocessed_native_count = sum(
        item.native_entity_count
        for item in layouts
        if not item.consumed_by_extractor
    )
    block_reference_count = len(layout_inserts)
    block_instance_count = sum(_mcount(item.entity) for item in layout_inserts)
    nested_reference_count = len(definition_inserts)
    status = "COMPLETE" if not errors else ("FAILED" if not layouts else "INCOMPLETE")
    ocs_wcs_status = _classify_ocs_wcs_status(
        identity_count=ocs_identity_count,
        non_identity_count=ocs_non_identity_count,
        unreadable_count=ocs_unreadable_count,
    )
    nested_block_units_status = _classify_nested_block_units_status(
        aligned_count=nested_block_units_aligned_count,
        mismatch_count=nested_block_units_mismatch_count,
        unitless_count=nested_block_units_unitless_count,
        unreadable_count=nested_block_units_unreadable_count,
    )
    return ExtractionCensus(
        schema_version=CENSUS_SCHEMA_VERSION,
        status=status,
        complete=not errors,
        units=units,
        units_name=units_name,
        scale_status=scale_status,
        layouts=tuple(layouts),
        entity_counts_by_layout=entity_counts_by_layout,
        block_definition_count=len(block_layouts),
        block_definition_entity_counts=block_definition_entity_counts,
        model_space_entity_count=model_count,
        paper_space_entity_count=paper_count,
        paper_space_native_entity_count=paper_native_count,
        paper_space_viewport_count=paper_viewport_count,
        unprocessed_layout_entity_count=unprocessed_count,
        unprocessed_layout_native_entity_count=unprocessed_native_count,
        block_reference_count=block_reference_count,
        block_instance_count=block_instance_count,
        nested_block_reference_count=nested_reference_count,
        nested_block_max_depth=max_depth,
        xref_definitions=tuple(xrefs),
        missing_xrefs=tuple(sorted(missing_xrefs)),
        proxy_entity_count=sum(all_proxy.values()),
        proxy_entity_counts=dict(sorted(all_proxy.items())),
        unsupported_entity_count=sum(semantic_unsupported.values()),
        unsupported_entity_counts=dict(sorted(semantic_unsupported.items())),
        semantic_coverage_complete=not semantic_unsupported,
        shadow_unsupported_entity_count=sum(shadow_unsupported.values()),
        shadow_unsupported_entity_counts=dict(sorted(shadow_unsupported.items())),
        shadow_coverage_complete=not shadow_unsupported,
        virtual_expansion_attempts=virtual_attempts,
        virtual_expansion_failures=tuple(virtual_failures),
        virtual_expansion_warnings=tuple(virtual_warnings),
        warnings=tuple(warnings),
        errors=tuple(errors),
        conversion_warnings=conversion_warning_values,
        ocs_wcs_status=ocs_wcs_status,
        ocs_identity_count=ocs_identity_count,
        ocs_non_identity_count=ocs_non_identity_count,
        ocs_unreadable_count=ocs_unreadable_count,
        nested_block_units_status=nested_block_units_status,
        nested_block_units_aligned_count=nested_block_units_aligned_count,
        nested_block_units_mismatch_count=nested_block_units_mismatch_count,
        nested_block_units_unitless_count=nested_block_units_unitless_count,
        nested_block_units_unreadable_count=nested_block_units_unreadable_count,
    )


__all__ = [
    "CENSUS_SCHEMA_VERSION",
    "DEFAULT_SHADOW_SUPPORTED_ENTITY_TYPES",
    "DEFAULT_SUPPORTED_ENTITY_TYPES",
    "PROXY_ENTITY_TYPES",
    "CensusDiagnostic",
    "ExtractionCensus",
    "LayoutCensus",
    "VirtualExpansionIssue",
    "XrefDefinitionCensus",
    "build_extraction_census",
]
