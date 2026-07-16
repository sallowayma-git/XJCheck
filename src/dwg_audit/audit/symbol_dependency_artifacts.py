from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import ConnectivityAssertionState
from dwg_audit.audit.symbol_dependency_library import InternalConnectivityGroup
from dwg_audit.audit.symbol_dependency_library import NestedPortBinding
from dwg_audit.audit.symbol_dependency_library import PortType
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SourceReference
from dwg_audit.audit.symbol_dependency_library import SymbolAlias
from dwg_audit.audit.symbol_dependency_library import SymbolDefinition
from dwg_audit.audit.symbol_dependency_library import SymbolDependency
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity
from dwg_audit.audit.symbol_dependency_library import SymbolLibraryValidation
from dwg_audit.audit.symbol_dependency_library import SymbolPort


ARTIFACT_SCHEMA_VERSION = "symbol-dependency-artifacts-v1"


@dataclass(frozen=True, slots=True)
class SymbolDependencyArtifactBundle:
    project_id: str
    library: SymbolDependencyLibrary
    validation: SymbolLibraryValidation
    source_status: str
    source_path: str | None
    load_issues: tuple[dict[str, str], ...] = ()

    def summary(self) -> dict[str, Any]:
        registry_counts = Counter(
            symbol.registry_status.value for symbol in self.library.symbols
        )
        annotation_counts = Counter(
            symbol.annotation_status.value for symbol in self.library.symbols
        )
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "project_id": self.project_id,
            "source_status": self.source_status,
            "source_path": self.source_path,
            "load_issue_count": len(self.load_issues),
            "library_valid": self.validation.valid and not self.load_issues,
            "symbol_count": len(self.library.symbols),
            "geometry_definition_count": len(self.library.geometry_definitions),
            "port_count": sum(len(symbol.ports) for symbol in self.library.symbols),
            "asserted_connectivity_group_count": sum(
                group.state is ConnectivityAssertionState.ASSERTED
                for symbol in self.library.symbols
                for group in symbol.internal_connectivity_groups
            ),
            "critical_issue_eligible_count": sum(
                symbol.critical_issue_eligible for symbol in self.library.symbols
            ),
            "critical_capable_count": sum(
                self.library.can_drive_critical(symbol.identity)
                for symbol in self.library.symbols
            ),
            "registry_status_counts": dict(sorted(registry_counts.items())),
            "annotation_status_counts": dict(sorted(annotation_counts.items())),
            "validation_error_count": len(self.validation.errors),
            "validation_warning_count": len(self.validation.warnings),
            "validation_code_counts": self.validation.to_dict()["summary"]["by_code"],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "project_id": self.project_id,
            "source_status": self.source_status,
            "source_path": self.source_path,
            "load_issues": list(self.load_issues),
            "library": self.library.to_dict(),
            "validation": self.validation.to_dict(),
            "summary": self.summary(),
        }


def build_symbol_dependency_artifacts(
    inventory: Any,
    *,
    project_id: str,
    config: Mapping[str, Any] | None = None,
) -> SymbolDependencyArtifactBundle:
    approved_rows, source_status, source_path, load_issues = _load_approved_rows(
        config or {}
    )
    approved_symbols: list[SymbolDefinition] = []
    for index, row in enumerate(approved_rows):
        try:
            approved_symbols.append(_approved_symbol(row, index=index))
        except (KeyError, TypeError, ValueError) as exc:
            load_issues.append(
                {
                    "code": "SYMBOL_LIBRARY_RECORD_INVALID",
                    "message": f"record {index}: {exc}",
                }
            )

    matched_inventory_keys = {
        (alias.value.casefold(), symbol.identity.fingerprint.casefold())
        for symbol in approved_symbols
        for alias in symbol.aliases
        if alias.namespace.casefold() == "definition_name"
    }
    symbols = list(approved_symbols)
    for row in _records(inventory):
        definition_name = _text(row.get("definition_name"))
        fingerprint = _text(row.get("definition_fingerprint"))
        if not definition_name or not fingerprint:
            load_issues.append(
                {
                    "code": "SYMBOL_INVENTORY_IDENTITY_MISSING",
                    "message": "inventory row is missing definition_name or definition_fingerprint",
                }
            )
            continue
        if (definition_name.casefold(), fingerprint.casefold()) in matched_inventory_keys:
            continue
        family = _text(row.get("symbol_family")) or definition_name
        source_id = _text(row.get("symbol_definition_id")) or (
            f"inventory:{definition_name}:{fingerprint[:12]}"
        )
        symbols.append(
            SymbolDefinition(
                identity=SymbolIdentity(
                    family=family,
                    version="inventory-v1",
                    fingerprint=fingerprint,
                ),
                aliases=(
                    SymbolAlias(
                        value=definition_name,
                        namespace="definition_name",
                        source_id=source_id,
                    ),
                ),
                sources=(
                    SourceReference(
                        source_id=source_id,
                        source_kind="project_symbol_inventory",
                        locator=definition_name,
                        project_id=project_id,
                    ),
                ),
                annotation_status=AnnotationStatus.PENDING_HUMAN_REVIEW,
                registry_status=RegistryStatus.UNKNOWN,
                critical_issue_eligible=False,
            )
        )

    library = SymbolDependencyLibrary(symbols=tuple(symbols))
    validation = library.validate()
    return SymbolDependencyArtifactBundle(
        project_id=project_id,
        library=library,
        validation=validation,
        source_status=source_status,
        source_path=source_path,
        load_issues=tuple(load_issues),
    )


def _load_approved_rows(
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], str, str | None, list[dict[str, str]]]:
    section = config.get("symbol_library")
    section = section if isinstance(section, Mapping) else {}
    raw_path = _text(section.get("path"))
    if not raw_path:
        return [], "not_configured", None, []
    path = Path(raw_path).expanduser()
    if not path.is_file():
        return (
            [],
            "missing",
            str(path),
            [
                {
                    "code": "SYMBOL_LIBRARY_NOT_FOUND",
                    "message": f"configured symbol library does not exist: {path}",
                }
            ],
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return (
            [],
            "invalid",
            str(path),
            [{"code": "SYMBOL_LIBRARY_READ_FAILED", "message": str(exc)}],
        )
    if isinstance(payload, Mapping) and "review_workflow" in payload:
        from dwg_audit.audit.symbol_library_review import SymbolReviewPromotionError
        from dwg_audit.audit.symbol_library_review import promote_symbol_review_document

        try:
            promoted = promote_symbol_review_document(payload)
        except SymbolReviewPromotionError as exc:
            return (
                [],
                "review_not_ready",
                str(path),
                [
                    {
                        "code": "SYMBOL_REVIEW_NOT_PROMOTION_READY",
                        "message": str(exc),
                    }
                ],
            )
        rows = [_production_symbol_row(symbol) for symbol in promoted.symbols]
        return rows, "loaded_review", str(path), []

    rows = payload.get("symbols") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return (
            [],
            "invalid",
            str(path),
            [
                {
                    "code": "SYMBOL_LIBRARY_SCHEMA_INVALID",
                    "message": "symbol library must be a list or contain a symbols list",
                }
            ],
        )
    return [dict(row) for row in rows if isinstance(row, Mapping)], "loaded", str(path), []


def _approved_symbol(row: Mapping[str, Any], *, index: int) -> SymbolDefinition:
    family = _required_text(row, "family")
    fingerprint = _required_text(row, "fingerprint")
    version = _text(row.get("version")) or "1"
    aliases: list[SymbolAlias] = [
        SymbolAlias(
            value=value,
            namespace="definition_name",
            source_id=f"approved:{index}",
        )
        for value in _strings(row.get("definition_names"))
    ]
    for item in _mappings(row.get("aliases")):
        aliases.append(
            SymbolAlias(
                value=_required_text(item, "value"),
                namespace=_text(item.get("namespace")) or "definition_name",
                source_id=_text(item.get("source_id")),
            )
        )
    sources = tuple(
        SourceReference(
            source_id=_required_text(item, "source_id"),
            source_kind=_required_text(item, "source_kind"),
            locator=_required_text(item, "locator"),
            project_id=_text(item.get("project_id")),
            held_out=bool(item.get("held_out", False)),
        )
        for item in _mappings(row.get("sources"))
    )
    if not sources:
        sources = (
            SourceReference(
                source_id=f"approved:{index}",
                source_kind="configured_symbol_library",
                locator=family,
            ),
        )
    identity = SymbolIdentity(family=family, version=version, fingerprint=fingerprint)
    return SymbolDefinition(
        identity=identity,
        symbol_dependencies=tuple(
            _symbol_dependency(item) for item in _mappings(row.get("symbol_dependencies"))
        ),
        ports=tuple(_port(item) for item in _mappings(row.get("ports"))),
        internal_connectivity_groups=tuple(
            _connectivity_group(item)
            for item in _mappings(row.get("internal_connectivity_groups"))
        ),
        aliases=tuple(aliases),
        sources=sources,
        annotation_status=_enum(
            AnnotationStatus,
            row.get("annotation_status"),
            AnnotationStatus.PENDING_HUMAN_REVIEW,
        ),
        registry_status=_enum(
            RegistryStatus,
            row.get("registry_status"),
            RegistryStatus.UNKNOWN,
        ),
        critical_issue_eligible=bool(row.get("critical_issue_eligible", False)),
    )


def _production_symbol_row(symbol: SymbolDefinition) -> dict[str, Any]:
    row = symbol.to_dict()
    row["definition_names"] = sorted(
        {
            alias.value
            for alias in symbol.aliases
            if alias.namespace.casefold() == "definition_name"
        },
        key=str.casefold,
    )
    return row


def _symbol_dependency(row: Mapping[str, Any]) -> SymbolDependency:
    target = row.get("target")
    if not isinstance(target, Mapping):
        raise ValueError("symbol dependency target must be an object")
    return SymbolDependency(
        dependency_id=_required_text(row, "dependency_id"),
        target=SymbolIdentity(
            family=_required_text(target, "family"),
            version=_required_text(target, "version"),
            fingerprint=_required_text(target, "fingerprint"),
        ),
        instance_name=_text(row.get("instance_name")),
        local_transform=tuple(float(value) for value in row.get("local_transform", [])),
        port_bindings=tuple(
            NestedPortBinding(
                parent_port_id=_required_text(item, "parent_port_id"),
                child_port_id=_required_text(item, "child_port_id"),
            )
            for item in _mappings(row.get("port_bindings"))
        ),
        required=bool(row.get("required", True)),
    )


def _port(row: Mapping[str, Any]) -> SymbolPort:
    return SymbolPort(
        port_id=_required_text(row, "port_id"),
        local_position=_vector(row.get("local_position"), "local_position"),
        outward_direction=_vector(
            row.get("outward_direction"), "outward_direction"
        ),
        port_type=_enum(PortType, row.get("port_type"), PortType.UNKNOWN),
        aliases=tuple(_strings(row.get("aliases"))),
        source_ids=tuple(_strings(row.get("source_ids"))),
        annotation_status=_enum(
            AnnotationStatus,
            row.get("annotation_status"),
            AnnotationStatus.PENDING_HUMAN_REVIEW,
        ),
    )


def _connectivity_group(row: Mapping[str, Any]) -> InternalConnectivityGroup:
    return InternalConnectivityGroup(
        group_id=_required_text(row, "group_id"),
        port_ids=tuple(_strings(row.get("port_ids"))),
        state=_enum(
            ConnectivityAssertionState,
            row.get("state"),
            ConnectivityAssertionState.UNKNOWN,
        ),
        annotation_status=_enum(
            AnnotationStatus,
            row.get("annotation_status"),
            AnnotationStatus.PENDING_HUMAN_REVIEW,
        ),
        source_ids=tuple(_strings(row.get("source_ids"))),
    )


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            records = value.to_dict("records")
        except TypeError:
            records = None
        if isinstance(records, list):
            return [dict(item) for item in records]
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _mappings(value: Any) -> list[Mapping[str, Any]]:
    decoded = _decode(value)
    return list(decoded) if isinstance(decoded, list) else []


def _strings(value: Any) -> list[str]:
    decoded = _decode(value)
    if isinstance(decoded, str):
        return [decoded] if decoded.strip() else []
    if not isinstance(decoded, Iterable) or isinstance(decoded, Mapping):
        return []
    return [text for item in decoded if (text := _text(item))]


def _decode(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def _vector(value: Any, field: str) -> tuple[float, float, float]:
    decoded = _decode(value)
    if not isinstance(decoded, (list, tuple)) or len(decoded) != 3:
        raise ValueError(f"{field} must contain three coordinates")
    return tuple(float(item) for item in decoded)  # type: ignore[return-value]


def _required_text(row: Mapping[str, Any], field: str) -> str:
    value = _text(row.get(field))
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _enum(enum_type: type[Any], value: Any, default: Any) -> Any:
    text = _text(value)
    if not text:
        return default
    try:
        return enum_type(text.upper())
    except ValueError as exc:
        raise ValueError(f"invalid {enum_type.__name__}: {value}") from exc


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "SymbolDependencyArtifactBundle",
    "build_symbol_dependency_artifacts",
]
