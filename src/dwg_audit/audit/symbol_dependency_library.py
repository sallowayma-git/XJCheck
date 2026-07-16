"""Versioned symbol definitions, dependencies, ports, and safety validation.

This module is intentionally independent from the recognition pipeline.  It
models reusable symbol knowledge while keeping machine-proposed and unknown
definitions observational.  Critical findings and electrical unions are
fail-closed until the relevant symbol and port annotations are human confirmed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum
import math
from typing import Any
from typing import Iterable


SCHEMA_VERSION = "symbol-dependency-library-v1"


class AnnotationStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    MACHINE_PROPOSED = "MACHINE_PROPOSED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    REJECTED = "REJECTED"


class RegistryStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    CANDIDATE = "CANDIDATE"
    REGISTERED = "REGISTERED"
    DEPRECATED = "DEPRECATED"


class PortType(StrEnum):
    UNKNOWN = "UNKNOWN"
    ELECTRICAL = "ELECTRICAL"
    POWER = "POWER"
    SIGNAL = "SIGNAL"
    CONTROL = "CONTROL"
    COMMUNICATION = "COMMUNICATION"
    GROUND = "GROUND"
    SHIELD = "SHIELD"
    MECHANICAL = "MECHANICAL"


class ConnectivityAssertionState(StrEnum):
    UNKNOWN = "UNKNOWN"
    POSSIBLE = "POSSIBLE"
    ASSERTED = "ASSERTED"
    REJECTED = "REJECTED"


class ValidationSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class SymbolIdentity:
    family: str
    version: str
    fingerprint: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.family, self.version, self.fingerprint)

    @property
    def canonical_id(self) -> str:
        return f"{self.family}@{self.version}#{self.fingerprint}"

    def to_dict(self) -> dict[str, str]:
        return {
            "family": self.family,
            "version": self.version,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class GeometryIdentity:
    definition_id: str
    version: str
    fingerprint: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.definition_id, self.version, self.fingerprint)

    @property
    def canonical_id(self) -> str:
        return f"{self.definition_id}@{self.version}#{self.fingerprint}"

    def to_dict(self) -> dict[str, str]:
        return {
            "definition_id": self.definition_id,
            "version": self.version,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class SymbolAlias:
    value: str
    namespace: str = "definition_name"
    source_id: str | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (_canonical_text(self.namespace), _canonical_text(self.value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "namespace": self.namespace,
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class SourceReference:
    source_id: str
    source_kind: str
    locator: str
    project_id: str | None = None
    held_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "locator": self.locator,
            "project_id": self.project_id,
            "held_out": self.held_out,
        }


@dataclass(frozen=True, slots=True)
class GeometryDefinition:
    identity: GeometryIdentity
    aliases: tuple[SymbolAlias, ...] = ()
    sources: tuple[SourceReference, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity.to_dict(),
            "aliases": [alias.to_dict() for alias in self.aliases],
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass(frozen=True, slots=True)
class GeometryDefinitionDependency:
    dependency_id: str
    target: GeometryIdentity
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency_id": self.dependency_id,
            "target": self.target.to_dict(),
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class NestedPortBinding:
    parent_port_id: str
    child_port_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "parent_port_id": self.parent_port_id,
            "child_port_id": self.child_port_id,
        }


@dataclass(frozen=True, slots=True)
class SymbolDependency:
    dependency_id: str
    target: SymbolIdentity
    instance_name: str | None = None
    local_transform: tuple[float, ...] = ()
    port_bindings: tuple[NestedPortBinding, ...] = ()
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "dependency_id": self.dependency_id,
            "target": self.target.to_dict(),
            "instance_name": self.instance_name,
            "local_transform": list(self.local_transform),
            "port_bindings": [binding.to_dict() for binding in self.port_bindings],
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class SymbolPort:
    port_id: str
    local_position: tuple[float, float, float]
    outward_direction: tuple[float, float, float]
    port_type: PortType | str = PortType.UNKNOWN
    aliases: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    annotation_status: AnnotationStatus = AnnotationStatus.PENDING_HUMAN_REVIEW

    def to_dict(self) -> dict[str, Any]:
        return {
            "port_id": self.port_id,
            "local_position": list(self.local_position),
            "outward_direction": list(self.outward_direction),
            "port_type": _enum_value(self.port_type),
            "aliases": list(self.aliases),
            "source_ids": list(self.source_ids),
            "annotation_status": self.annotation_status.value,
        }


@dataclass(frozen=True, slots=True)
class InternalConnectivityGroup:
    group_id: str
    port_ids: tuple[str, ...]
    state: ConnectivityAssertionState = ConnectivityAssertionState.UNKNOWN
    annotation_status: AnnotationStatus = AnnotationStatus.PENDING_HUMAN_REVIEW
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "port_ids": list(self.port_ids),
            "state": self.state.value,
            "annotation_status": self.annotation_status.value,
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True, slots=True)
class SymbolDefinition:
    identity: SymbolIdentity
    geometry_dependencies: tuple[GeometryDefinitionDependency, ...] = ()
    symbol_dependencies: tuple[SymbolDependency, ...] = ()
    ports: tuple[SymbolPort, ...] = ()
    internal_connectivity_groups: tuple[InternalConnectivityGroup, ...] = ()
    aliases: tuple[SymbolAlias, ...] = ()
    sources: tuple[SourceReference, ...] = ()
    annotation_status: AnnotationStatus = AnnotationStatus.PENDING_HUMAN_REVIEW
    registry_status: RegistryStatus = RegistryStatus.UNKNOWN
    critical_issue_eligible: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity.to_dict(),
            "geometry_dependencies": [
                dependency.to_dict() for dependency in self.geometry_dependencies
            ],
            "symbol_dependencies": [
                dependency.to_dict() for dependency in self.symbol_dependencies
            ],
            "ports": [port.to_dict() for port in self.ports],
            "internal_connectivity_groups": [
                group.to_dict() for group in self.internal_connectivity_groups
            ],
            "aliases": [alias.to_dict() for alias in self.aliases],
            "sources": [source.to_dict() for source in self.sources],
            "annotation_status": self.annotation_status.value,
            "registry_status": self.registry_status.value,
            "critical_issue_eligible": self.critical_issue_eligible,
        }


@dataclass(frozen=True, slots=True)
class SymbolLibraryValidationIssue:
    code: str
    severity: ValidationSeverity
    message: str
    symbol_id: str | None = None
    dependency_id: str | None = None
    port_id: str | None = None
    cycle: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "symbol_id": self.symbol_id,
            "dependency_id": self.dependency_id,
            "port_id": self.port_id,
            "cycle": list(self.cycle),
        }


@dataclass(frozen=True, slots=True)
class SymbolLibraryValidation:
    issues: tuple[SymbolLibraryValidationIssue, ...]

    @property
    def errors(self) -> tuple[SymbolLibraryValidationIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is ValidationSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[SymbolLibraryValidationIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is ValidationSeverity.WARNING
        )

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        counts = Counter(issue.code for issue in self.issues)
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": {
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
                "by_code": dict(sorted(counts.items())),
            },
        }


@dataclass(frozen=True, slots=True)
class SymbolDependencyLibrary:
    symbols: tuple[SymbolDefinition, ...] = ()
    geometry_definitions: tuple[GeometryDefinition, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def validate(self) -> SymbolLibraryValidation:
        return validate_symbol_dependency_library(self)

    def resolve(self, identity: SymbolIdentity) -> SymbolDefinition | None:
        matches = [symbol for symbol in self.symbols if symbol.identity == identity]
        return matches[0] if len(matches) == 1 else None

    def resolve_alias(
        self,
        value: str,
        *,
        namespace: str = "definition_name",
    ) -> SymbolDefinition | None:
        key = (_canonical_text(namespace), _canonical_text(value))
        matches = [
            symbol
            for symbol in self.symbols
            if any(alias.key == key for alias in symbol.aliases)
        ]
        return matches[0] if len(matches) == 1 else None

    def can_drive_critical(self, identity: SymbolIdentity) -> bool:
        if not self.validate().valid:
            return False
        symbol = self.resolve(identity)
        return symbol is not None and _critical_prerequisites_met(symbol)

    def can_assert_electrical_union(
        self,
        identity: SymbolIdentity,
        first_port_id: str,
        second_port_id: str,
    ) -> bool:
        if not self.validate().valid:
            return False
        symbol = self.resolve(identity)
        if symbol is None or not _symbol_is_human_registered(symbol):
            return False
        first = _canonical_text(first_port_id)
        second = _canonical_text(second_port_id)
        if not first or not second or first == second:
            return False
        ports = {_canonical_text(port.port_id): port for port in symbol.ports}
        if first not in ports or second not in ports:
            return False
        if any(
            ports[port_id].annotation_status is not AnnotationStatus.HUMAN_CONFIRMED
            for port_id in (first, second)
        ):
            return False
        return any(
            group.state is ConnectivityAssertionState.ASSERTED
            and group.annotation_status is AnnotationStatus.HUMAN_CONFIRMED
            and {first, second}.issubset(
                {_canonical_text(port_id) for port_id in group.port_ids}
            )
            for group in symbol.internal_connectivity_groups
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "geometry_definitions": [
                definition.to_dict() for definition in self.geometry_definitions
            ],
            "symbols": [symbol.to_dict() for symbol in self.symbols],
        }


def validate_symbol_dependency_library(
    library: SymbolDependencyLibrary,
) -> SymbolLibraryValidation:
    issues: list[SymbolLibraryValidationIssue] = []
    symbol_index = _unique_index(
        (symbol.identity.key, symbol) for symbol in library.symbols
    )
    geometry_index = _unique_index(
        (definition.identity.key, definition)
        for definition in library.geometry_definitions
    )

    _validate_duplicate_identities(library, issues)
    _validate_aliases(library.symbols, issues)
    for geometry in library.geometry_definitions:
        _validate_geometry_definition(geometry, issues)
    for symbol in library.symbols:
        _validate_symbol_definition(
            symbol,
            symbol_index=symbol_index,
            geometry_index=geometry_index,
            issues=issues,
        )
    _validate_dependency_cycles(library.symbols, symbol_index, issues)

    ordered = sorted(
        issues,
        key=lambda issue: (
            issue.severity.value,
            issue.code,
            issue.symbol_id or "",
            issue.dependency_id or "",
            issue.port_id or "",
            issue.cycle,
        ),
    )
    return SymbolLibraryValidation(issues=tuple(ordered))


def _validate_duplicate_identities(
    library: SymbolDependencyLibrary,
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    symbol_counts = Counter(symbol.identity.key for symbol in library.symbols)
    for identity_key, count in symbol_counts.items():
        if count > 1:
            identity = next(
                symbol.identity
                for symbol in library.symbols
                if symbol.identity.key == identity_key
            )
            _error(
                issues,
                "DUPLICATE_SYMBOL_DEFINITION",
                f"symbol identity occurs {count} times",
                symbol_id=identity.canonical_id,
            )
    geometry_counts = Counter(
        definition.identity.key for definition in library.geometry_definitions
    )
    for identity_key, count in geometry_counts.items():
        if count > 1:
            identity = next(
                definition.identity
                for definition in library.geometry_definitions
                if definition.identity.key == identity_key
            )
            _error(
                issues,
                "DUPLICATE_GEOMETRY_DEFINITION",
                f"geometry identity occurs {count} times",
                symbol_id=identity.canonical_id,
            )


def _validate_aliases(
    symbols: Iterable[SymbolDefinition],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    owners: dict[tuple[str, str], set[str]] = {}
    for symbol in symbols:
        for alias in symbol.aliases:
            if not alias.key[0] or not alias.key[1]:
                _error(
                    issues,
                    "INVALID_SYMBOL_ALIAS",
                    "alias namespace and value must be non-empty",
                    symbol_id=symbol.identity.canonical_id,
                )
                continue
            owners.setdefault(alias.key, set()).add(symbol.identity.canonical_id)
    for alias_key, symbol_ids in owners.items():
        if len(symbol_ids) > 1:
            _error(
                issues,
                "AMBIGUOUS_SYMBOL_ALIAS",
                f"alias {alias_key[0]}:{alias_key[1]} resolves to multiple symbols",
                cycle=tuple(sorted(symbol_ids)),
            )


def _validate_geometry_definition(
    definition: GeometryDefinition,
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    identity = definition.identity
    if not all(text.strip() for text in identity.key):
        _error(
            issues,
            "INVALID_GEOMETRY_IDENTITY",
            "geometry definition id, version, and fingerprint are required",
            symbol_id=identity.canonical_id,
        )
    _validate_sources(definition.sources, identity.canonical_id, issues)


def _validate_symbol_definition(
    symbol: SymbolDefinition,
    *,
    symbol_index: dict[tuple[str, str, str], SymbolDefinition],
    geometry_index: dict[tuple[str, str, str], GeometryDefinition],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    symbol_id = symbol.identity.canonical_id
    if not all(text.strip() for text in symbol.identity.key):
        _error(
            issues,
            "INVALID_SYMBOL_IDENTITY",
            "symbol family, version, and fingerprint are required",
            symbol_id=symbol_id,
        )
    _validate_sources(symbol.sources, symbol_id, issues)

    ports: dict[str, SymbolPort] = {}
    port_counts = Counter(_canonical_text(port.port_id) for port in symbol.ports)
    for port in symbol.ports:
        port_key = _canonical_text(port.port_id)
        if not port_key:
            _error(
                issues,
                "INVALID_PORT_ID",
                "port id must be non-empty",
                symbol_id=symbol_id,
            )
            continue
        if port_counts[port_key] > 1:
            _error(
                issues,
                "DUPLICATE_PORT_ID",
                f"port id {port.port_id!r} is duplicated",
                symbol_id=symbol_id,
                port_id=port.port_id,
            )
        else:
            ports[port_key] = port
        if not _finite_vector(port.local_position, allow_zero=True):
            _error(
                issues,
                "INVALID_PORT_POSITION",
                "port position must contain three finite coordinates",
                symbol_id=symbol_id,
                port_id=port.port_id,
            )
        if not _finite_vector(port.outward_direction, allow_zero=False):
            _error(
                issues,
                "INVALID_PORT_DIRECTION",
                "port direction must be a non-zero finite 3D vector",
                symbol_id=symbol_id,
                port_id=port.port_id,
            )
        if not _enum_value(port.port_type).strip():
            _error(
                issues,
                "INVALID_PORT_TYPE",
                "port type must be non-empty",
                symbol_id=symbol_id,
                port_id=port.port_id,
            )

    _validate_geometry_dependencies(symbol, geometry_index, issues)
    _validate_symbol_dependencies(symbol, symbol_index, ports, issues)
    _validate_connectivity_groups(symbol, ports, issues)
    _validate_asserted_dependency_bindings(symbol, symbol_index, issues)
    _validate_critical_eligibility(symbol, issues)
    _validate_critical_dependencies(symbol, symbol_index, issues)


def _validate_geometry_dependencies(
    symbol: SymbolDefinition,
    geometry_index: dict[tuple[str, str, str], GeometryDefinition],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    symbol_id = symbol.identity.canonical_id
    counts = Counter(dep.dependency_id for dep in symbol.geometry_dependencies)
    for dependency in symbol.geometry_dependencies:
        if not dependency.dependency_id.strip():
            _error(
                issues,
                "INVALID_DEPENDENCY_ID",
                "geometry dependency id must be non-empty",
                symbol_id=symbol_id,
            )
        elif counts[dependency.dependency_id] > 1:
            _error(
                issues,
                "DUPLICATE_DEPENDENCY_ID",
                f"dependency id {dependency.dependency_id!r} is duplicated",
                symbol_id=symbol_id,
                dependency_id=dependency.dependency_id,
            )
        if dependency.target.key not in geometry_index:
            _dependency_issue(
                issues,
                dependency.required,
                "DANGLING_GEOMETRY_DEPENDENCY",
                f"geometry dependency target "
                f"{dependency.target.canonical_id} is missing",
                symbol_id=symbol_id,
                dependency_id=dependency.dependency_id,
            )


def _validate_symbol_dependencies(
    symbol: SymbolDefinition,
    symbol_index: dict[tuple[str, str, str], SymbolDefinition],
    parent_ports: dict[str, SymbolPort],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    symbol_id = symbol.identity.canonical_id
    all_dependency_ids = [dep.dependency_id for dep in symbol.geometry_dependencies]
    all_dependency_ids.extend(dep.dependency_id for dep in symbol.symbol_dependencies)
    counts = Counter(all_dependency_ids)
    for dependency in symbol.symbol_dependencies:
        if not dependency.dependency_id.strip():
            _error(
                issues,
                "INVALID_DEPENDENCY_ID",
                "symbol dependency id must be non-empty",
                symbol_id=symbol_id,
            )
        elif counts[dependency.dependency_id] > 1:
            _error(
                issues,
                "DUPLICATE_DEPENDENCY_ID",
                f"dependency id {dependency.dependency_id!r} is duplicated",
                symbol_id=symbol_id,
                dependency_id=dependency.dependency_id,
            )
        if dependency.local_transform and (
            len(dependency.local_transform) not in {12, 16}
            or not all(
                math.isfinite(float(value)) for value in dependency.local_transform
            )
        ):
            _error(
                issues,
                "INVALID_NESTED_SYMBOL_TRANSFORM",
                "nested symbol transform must contain 12 or 16 finite values",
                symbol_id=symbol_id,
                dependency_id=dependency.dependency_id,
            )
        target = symbol_index.get(dependency.target.key)
        if target is None:
            _dependency_issue(
                issues,
                dependency.required,
                "DANGLING_SYMBOL_DEPENDENCY",
                f"symbol dependency target {dependency.target.canonical_id} is missing",
                symbol_id=symbol_id,
                dependency_id=dependency.dependency_id,
            )
            continue
        child_ports = {
            _canonical_text(port.port_id): port for port in target.ports
        }
        for binding in dependency.port_bindings:
            if _canonical_text(binding.parent_port_id) not in parent_ports:
                _error(
                    issues,
                    "DANGLING_PARENT_PORT_BINDING",
                    f"parent port {binding.parent_port_id!r} is missing",
                    symbol_id=symbol_id,
                    dependency_id=dependency.dependency_id,
                    port_id=binding.parent_port_id,
                )
            if _canonical_text(binding.child_port_id) not in child_ports:
                _error(
                    issues,
                    "DANGLING_CHILD_PORT_BINDING",
                    f"child port {binding.child_port_id!r} is missing",
                    symbol_id=symbol_id,
                    dependency_id=dependency.dependency_id,
                    port_id=binding.child_port_id,
                )


def _validate_connectivity_groups(
    symbol: SymbolDefinition,
    ports: dict[str, SymbolPort],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    symbol_id = symbol.identity.canonical_id
    group_counts = Counter(
        _canonical_text(group.group_id)
        for group in symbol.internal_connectivity_groups
    )
    for group in symbol.internal_connectivity_groups:
        group_key = _canonical_text(group.group_id)
        if not group_key:
            _error(
                issues,
                "INVALID_CONNECTIVITY_GROUP_ID",
                "connectivity group id must be non-empty",
                symbol_id=symbol_id,
            )
        elif group_counts[group_key] > 1:
            _error(
                issues,
                "DUPLICATE_CONNECTIVITY_GROUP_ID",
                f"connectivity group id {group.group_id!r} is duplicated",
                symbol_id=symbol_id,
            )
        canonical_ports = [_canonical_text(port_id) for port_id in group.port_ids]
        if len(canonical_ports) < 2 or len(set(canonical_ports)) < 2:
            _error(
                issues,
                "CONNECTIVITY_GROUP_TOO_SMALL",
                "connectivity group must contain at least two distinct ports",
                symbol_id=symbol_id,
            )
        for raw_port_id, port_id in zip(group.port_ids, canonical_ports, strict=True):
            if port_id not in ports:
                _error(
                    issues,
                    "DANGLING_CONNECTIVITY_PORT",
                    f"connectivity group references missing port {raw_port_id!r}",
                    symbol_id=symbol_id,
                    port_id=raw_port_id,
                )
        if group.state is ConnectivityAssertionState.ASSERTED:
            if not _symbol_is_human_registered(symbol):
                _error(
                    issues,
                    "ASSERTED_UNION_REQUIRES_REGISTERED_SYMBOL",
                    "ASSERTED internal connectivity requires a human-confirmed "
                    "registered symbol",
                    symbol_id=symbol_id,
                )
            if group.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED:
                _error(
                    issues,
                    "ASSERTED_UNION_REQUIRES_HUMAN_CONFIRMATION",
                    "ASSERTED internal connectivity group must be human confirmed",
                    symbol_id=symbol_id,
                )
            referenced_ports = [ports.get(port_id) for port_id in canonical_ports]
            if any(
                port is None
                or port.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED
                for port in referenced_ports
            ):
                _error(
                    issues,
                    "ASSERTED_UNION_REQUIRES_CONFIRMED_PORTS",
                    "ASSERTED internal connectivity requires all referenced ports "
                    "to be human confirmed",
                    symbol_id=symbol_id,
                )


def _validate_asserted_dependency_bindings(
    symbol: SymbolDefinition,
    symbol_index: dict[tuple[str, str, str], SymbolDefinition],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    """Prevent an ASSERTED parent group from inheriting trust from an unknown child."""
    asserted_parent_ports = {
        _canonical_text(port_id)
        for group in symbol.internal_connectivity_groups
        if group.state is ConnectivityAssertionState.ASSERTED
        for port_id in group.port_ids
    }
    if not asserted_parent_ports:
        return
    symbol_id = symbol.identity.canonical_id
    for dependency in symbol.symbol_dependencies:
        bound = {
            binding.parent_port_id: binding.child_port_id
            for binding in dependency.port_bindings
            if _canonical_text(binding.parent_port_id) in asserted_parent_ports
        }
        if not bound:
            continue
        target = symbol_index.get(dependency.target.key)
        target_ports = (
            {_canonical_text(port.port_id): port for port in target.ports}
            if target is not None
            else {}
        )
        if target is None or not _symbol_is_human_registered(target):
            _error(
                issues,
                "ASSERTED_UNION_REQUIRES_CONFIRMED_DEPENDENCIES",
                "ASSERTED connectivity cannot bind to an unknown or unconfirmed "
                "child symbol",
                symbol_id=symbol_id,
                dependency_id=dependency.dependency_id,
            )
            continue
        if any(
            _canonical_text(child_port_id) not in target_ports
            or target_ports[_canonical_text(child_port_id)].annotation_status
            is not AnnotationStatus.HUMAN_CONFIRMED
            for child_port_id in bound.values()
        ):
            _error(
                issues,
                "ASSERTED_UNION_REQUIRES_CONFIRMED_DEPENDENCIES",
                "ASSERTED connectivity requires human-confirmed child ports",
                symbol_id=symbol_id,
                dependency_id=dependency.dependency_id,
            )


def _validate_critical_eligibility(
    symbol: SymbolDefinition,
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    if not symbol.critical_issue_eligible:
        return
    symbol_id = symbol.identity.canonical_id
    if symbol.registry_status is not RegistryStatus.REGISTERED:
        _error(
            issues,
            "CRITICAL_REQUIRES_REGISTERED_SYMBOL",
            "critical eligibility requires REGISTERED registry status",
            symbol_id=symbol_id,
        )
    if symbol.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED:
        _error(
            issues,
            "CRITICAL_REQUIRES_HUMAN_CONFIRMATION",
            "critical eligibility requires human-confirmed symbol annotation",
            symbol_id=symbol_id,
        )
    if not symbol.ports or any(
        port.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED
        for port in symbol.ports
    ):
        _error(
            issues,
            "CRITICAL_REQUIRES_CONFIRMED_PORTS",
            "critical eligibility requires at least one port and all ports human "
            "confirmed",
            symbol_id=symbol_id,
        )


def _validate_critical_dependencies(
    symbol: SymbolDefinition,
    symbol_index: dict[tuple[str, str, str], SymbolDefinition],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    if not symbol.critical_issue_eligible:
        return
    untrusted = any(
        dependency.required
        and (
            (target := symbol_index.get(dependency.target.key)) is None
            or not _human_registered_dependency_chain(target, symbol_index, set())
        )
        for dependency in symbol.symbol_dependencies
    )
    if untrusted:
        _error(
            issues,
            "CRITICAL_REQUIRES_CONFIRMED_DEPENDENCIES",
            "critical eligibility requires all required nested symbols to be "
            "human-confirmed and registered",
            symbol_id=symbol.identity.canonical_id,
        )


def _validate_sources(
    sources: tuple[SourceReference, ...],
    symbol_id: str,
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    counts = Counter(source.source_id for source in sources)
    for source in sources:
        if not source.source_id.strip() or not source.source_kind.strip():
            _error(
                issues,
                "INVALID_SOURCE_REFERENCE",
                "source id and source kind must be non-empty",
                symbol_id=symbol_id,
            )
        if not source.locator.strip():
            _error(
                issues,
                "INVALID_SOURCE_REFERENCE",
                "source locator must be non-empty",
                symbol_id=symbol_id,
            )
        if counts[source.source_id] > 1:
            _error(
                issues,
                "DUPLICATE_SOURCE_REFERENCE",
                f"source id {source.source_id!r} is duplicated",
                symbol_id=symbol_id,
            )


def _validate_dependency_cycles(
    symbols: tuple[SymbolDefinition, ...],
    symbol_index: dict[tuple[str, str, str], SymbolDefinition],
    issues: list[SymbolLibraryValidationIssue],
) -> None:
    adjacency: dict[tuple[str, str, str], tuple[tuple[str, str, str], ...]] = {}
    for symbol in symbols:
        adjacency[symbol.identity.key] = tuple(
            dependency.target.key
            for dependency in symbol.symbol_dependencies
            if dependency.target.key in symbol_index
        )
    for cycle in _find_cycles(adjacency):
        cycle_ids = tuple(symbol_index[key].identity.canonical_id for key in cycle)
        _error(
            issues,
            "SYMBOL_DEPENDENCY_CYCLE",
            "nested symbol dependency cycle detected",
            symbol_id=cycle_ids[0],
            cycle=cycle_ids,
        )


def _find_cycles(
    adjacency: dict[tuple[str, str, str], tuple[tuple[str, str, str], ...]],
) -> tuple[tuple[tuple[str, str, str], ...], ...]:
    visiting: set[tuple[str, str, str]] = set()
    visited: set[tuple[str, str, str]] = set()
    stack: list[tuple[str, str, str]] = []
    cycles: set[tuple[tuple[str, str, str], ...]] = set()

    def visit(node: tuple[str, str, str]) -> None:
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for target in adjacency.get(node, ()):
            if target in visiting:
                start = stack.index(target)
                cycles.add(_canonical_cycle(tuple(stack[start:])))
            elif target not in visited:
                visit(target)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(adjacency):
        visit(node)
    return tuple(sorted(cycles))


def _canonical_cycle(
    cycle: tuple[tuple[str, str, str], ...],
) -> tuple[tuple[str, str, str], ...]:
    rotations = tuple(cycle[index:] + cycle[:index] for index in range(len(cycle)))
    return min(rotations)


def _critical_prerequisites_met(symbol: SymbolDefinition) -> bool:
    return (
        symbol.critical_issue_eligible
        and _symbol_is_human_registered(symbol)
        and bool(symbol.ports)
        and all(
            port.annotation_status is AnnotationStatus.HUMAN_CONFIRMED
            for port in symbol.ports
        )
    )


def _human_registered_dependency_chain(
    symbol: SymbolDefinition,
    symbol_index: dict[tuple[str, str, str], SymbolDefinition],
    visiting: set[tuple[str, str, str]],
) -> bool:
    if not _symbol_is_human_registered(symbol):
        return False
    if any(
        port.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED
        for port in symbol.ports
    ):
        return False
    if symbol.identity.key in visiting:
        return False
    visiting.add(symbol.identity.key)
    try:
        for dependency in symbol.symbol_dependencies:
            if not dependency.required:
                continue
            target = symbol_index.get(dependency.target.key)
            if target is None or not _human_registered_dependency_chain(
                target, symbol_index, visiting
            ):
                return False
        return True
    finally:
        visiting.remove(symbol.identity.key)


def _symbol_is_human_registered(symbol: SymbolDefinition) -> bool:
    return (
        symbol.registry_status is RegistryStatus.REGISTERED
        and symbol.annotation_status is AnnotationStatus.HUMAN_CONFIRMED
    )


def _finite_vector(values: tuple[float, ...], *, allow_zero: bool) -> bool:
    if len(values) != 3:
        return False
    try:
        numeric = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(value) for value in numeric):
        return False
    return allow_zero or any(abs(value) > 0.0 for value in numeric)


def _unique_index(items: Iterable[tuple[Any, Any]]) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    duplicates: set[Any] = set()
    for key, value in items:
        if key in result:
            duplicates.add(key)
        else:
            result[key] = value
    for key in duplicates:
        result.pop(key, None)
    return result


def _dependency_issue(
    issues: list[SymbolLibraryValidationIssue],
    required: bool,
    code: str,
    message: str,
    **context: Any,
) -> None:
    issues.append(
        SymbolLibraryValidationIssue(
            code=code,
            severity=(
                ValidationSeverity.ERROR if required else ValidationSeverity.WARNING
            ),
            message=message,
            **context,
        )
    )


def _error(
    issues: list[SymbolLibraryValidationIssue],
    code: str,
    message: str,
    **context: Any,
) -> None:
    issues.append(
        SymbolLibraryValidationIssue(
            code=code,
            severity=ValidationSeverity.ERROR,
            message=message,
            **context,
        )
    )


def _canonical_text(value: str) -> str:
    return value.strip().casefold()


def _enum_value(value: StrEnum | str) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


__all__ = [
    "AnnotationStatus",
    "ConnectivityAssertionState",
    "GeometryDefinition",
    "GeometryDefinitionDependency",
    "GeometryIdentity",
    "InternalConnectivityGroup",
    "NestedPortBinding",
    "PortType",
    "RegistryStatus",
    "SCHEMA_VERSION",
    "SourceReference",
    "SymbolAlias",
    "SymbolDefinition",
    "SymbolDependency",
    "SymbolDependencyLibrary",
    "SymbolIdentity",
    "SymbolLibraryValidation",
    "SymbolLibraryValidationIssue",
    "SymbolPort",
    "ValidationSeverity",
    "validate_symbol_dependency_library",
]
