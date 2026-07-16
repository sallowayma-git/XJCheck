"""Fail-closed symbol-library review templates and promotion checks.

The review document is intentionally compatible with the configured symbol
library shape while adding explicit review metadata.  Generated templates are
always non-authoritative: annotations are pending, registry state is unknown,
critical eligibility is disabled, and internal connectivity is not asserted.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
import math
from pathlib import Path
from typing import Any

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import ConnectivityAssertionState
from dwg_audit.audit.symbol_dependency_library import GeometryDefinition
from dwg_audit.audit.symbol_dependency_library import GeometryDefinitionDependency
from dwg_audit.audit.symbol_dependency_library import GeometryIdentity
from dwg_audit.audit.symbol_dependency_library import InternalConnectivityGroup
from dwg_audit.audit.symbol_dependency_library import NestedPortBinding
from dwg_audit.audit.symbol_dependency_library import PortType
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SCHEMA_VERSION
from dwg_audit.audit.symbol_dependency_library import SourceReference
from dwg_audit.audit.symbol_dependency_library import SymbolAlias
from dwg_audit.audit.symbol_dependency_library import SymbolDefinition
from dwg_audit.audit.symbol_dependency_library import SymbolDependency
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity
from dwg_audit.audit.symbol_dependency_library import SymbolLibraryValidation
from dwg_audit.audit.symbol_dependency_library import SymbolPort
from dwg_audit.audit.symbol_dependency_library import ValidationSeverity


REVIEW_WORKFLOW_VERSION = "symbol-library-review-v1"
REVIEW_SCHEMA_FILENAME = "symbol_dependency_library.schema.json"

# ``SourceReference.source_kind`` intentionally remains an open string for
# backward compatibility.  Promotion, however, is fail-closed: only an
# explicitly classified original drawing or human review source can be the
# primary evidence for a completed review.  Derived sources remain useful as
# supporting evidence in pending/review documents, but cannot create human
# authority on their own.  Unknown kinds are treated like derived evidence
# until they are deliberately added to the primary allow-list.
_PRIMARY_REVIEW_SOURCE_KINDS = frozenset(
    {
        "cad_drawing",
        "dwg",
        "dxf",
        "human_annotation",
        "human_review",
        "human_review_input",
        "original_cad_drawing",
        "original_drawing",
        "original_dwg",
        "original_dxf",
        "source_drawing",
        "source_dwg",
        "source_dxf",
    }
)
_DERIVED_REVIEW_SOURCE_KINDS = frozenset(
    {
        "configured_symbol_library",
        "machine_geometry_proposal",
        "project_symbol_inventory",
        "symbol_corpus_queue",
    }
)


class ReviewDocumentStatus(StrEnum):
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    REVIEW_COMPLETE = "REVIEW_COMPLETE"


class ReviewItemStatus(StrEnum):
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    REJECTED = "REJECTED"


class ReviewIssueSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class SymbolReviewIssue:
    code: str
    path: str
    message: str
    severity: ReviewIssueSeverity = ReviewIssueSeverity.ERROR

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "severity": self.severity.value,
        }


@dataclass(frozen=True, slots=True)
class SymbolReviewValidation:
    issues: tuple[SymbolReviewIssue, ...]
    library_validation: SymbolLibraryValidation
    document_status: ReviewDocumentStatus | None
    symbol_count: int
    pending_symbol_count: int

    @property
    def errors(self) -> tuple[SymbolReviewIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is ReviewIssueSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[SymbolReviewIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity is ReviewIssueSeverity.WARNING
        )

    @property
    def valid(self) -> bool:
        return not self.errors and self.library_validation.valid

    @property
    def promotion_ready(self) -> bool:
        return (
            self.valid
            and self.document_status is ReviewDocumentStatus.REVIEW_COMPLETE
            and self.symbol_count > 0
            and self.pending_symbol_count == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "promotion_ready": self.promotion_ready,
            "document_status": (
                self.document_status.value if self.document_status else None
            ),
            "symbol_count": self.symbol_count,
            "pending_symbol_count": self.pending_symbol_count,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [issue.to_dict() for issue in self.issues],
            "library_validation": self.library_validation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SymbolReviewLoadResult:
    document: dict[str, Any] | None
    library: SymbolDependencyLibrary
    validation: SymbolReviewValidation


class SymbolReviewPromotionError(ValueError):
    """Raised when a review document is not safe to promote."""


@dataclass(frozen=True, slots=True)
class _ReviewMetadata:
    status: ReviewItemStatus
    reviewer: str | None
    reviewed_at: str | None
    evidence_source_ids: tuple[str, ...]


class _ParseError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(message)
        self.path = path


def build_symbol_review_document(source: Any) -> dict[str, Any]:
    """Build a deterministic, non-authoritative review backlog.

    ``source`` may be a :class:`SymbolDependencyLibrary` or an artifact bundle
    exposing a ``library`` attribute.  Existing trust is deliberately removed
    because the generated document is a fresh human-review task, not an
    approval export.
    """

    library = _source_library(source)
    symbols = sorted(
        library.symbols,
        key=lambda symbol: symbol.identity.key,
    )
    review_symbols: list[dict[str, Any]] = []
    for rank, symbol in enumerate(symbols, start=1):
        definition_names = sorted(
            {
                alias.value
                for alias in symbol.aliases
                if alias.namespace.casefold() == "definition_name"
            },
            key=str.casefold,
        )
        other_aliases = [
            alias.to_dict()
            for alias in symbol.aliases
            if alias.namespace.casefold() != "definition_name"
        ]
        review_symbols.append(
            {
                "backlog_rank": rank,
                "review_reason_codes": _review_reason_codes(symbol),
                "family": symbol.identity.family,
                "version": symbol.identity.version,
                "fingerprint": symbol.identity.fingerprint,
                "definition_names": definition_names,
                "geometry_dependencies": [
                    dependency.to_dict()
                    for dependency in symbol.geometry_dependencies
                ],
                "symbol_dependencies": [
                    dependency.to_dict() for dependency in symbol.symbol_dependencies
                ],
                "ports": [
                    {
                        "port_id": port.port_id,
                        "local_position": list(port.local_position),
                        "outward_direction": list(port.outward_direction),
                        "port_type": _enum_value(port.port_type),
                        "aliases": list(port.aliases),
                        "source_ids": list(port.source_ids),
                        "annotation_status": (
                            AnnotationStatus.PENDING_HUMAN_REVIEW.value
                        ),
                    }
                    for port in symbol.ports
                ],
                "internal_connectivity_groups": [
                    {
                        "group_id": group.group_id,
                        "port_ids": list(group.port_ids),
                        "state": ConnectivityAssertionState.UNKNOWN.value,
                        "annotation_status": (
                            AnnotationStatus.PENDING_HUMAN_REVIEW.value
                        ),
                        "source_ids": list(group.source_ids),
                    }
                    for group in symbol.internal_connectivity_groups
                ],
                "aliases": other_aliases,
                "sources": [source_ref.to_dict() for source_ref in symbol.sources],
                "annotation_status": AnnotationStatus.PENDING_HUMAN_REVIEW.value,
                "registry_status": RegistryStatus.UNKNOWN.value,
                "critical_issue_eligible": False,
                "review": {
                    "status": ReviewItemStatus.PENDING_HUMAN_REVIEW.value,
                    "reviewer": None,
                    "reviewed_at": None,
                    "evidence_source_ids": [],
                    "notes": None,
                },
            }
        )

    return {
        "$schema": REVIEW_SCHEMA_FILENAME,
        "schema_version": SCHEMA_VERSION,
        "review_workflow": {
            "workflow_version": REVIEW_WORKFLOW_VERSION,
            "document_status": ReviewDocumentStatus.PENDING_HUMAN_REVIEW.value,
            "notes": None,
        },
        "geometry_definitions": [
            definition.to_dict()
            for definition in sorted(
                library.geometry_definitions,
                key=lambda definition: definition.identity.key,
            )
        ],
        "symbols": review_symbols,
    }


def write_symbol_review_template(source: Any, path: str | Path) -> Path:
    """Write a generated review backlog as formatted UTF-8 JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            build_symbol_review_document(source),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def load_symbol_review_document(
    source: str | Path | Mapping[str, Any],
) -> SymbolReviewLoadResult:
    """Load and validate a review document without granting authority."""

    read_document, read_issue = _read_document(source)
    if read_issue is not None:
        empty_library = SymbolDependencyLibrary()
        validation = SymbolReviewValidation(
            issues=(read_issue,),
            library_validation=empty_library.validate(),
            document_status=None,
            symbol_count=0,
            pending_symbol_count=0,
        )
        return SymbolReviewLoadResult(None, empty_library, validation)

    assert read_document is not None
    issues: list[SymbolReviewIssue] = []
    _unexpected_fields(
        read_document,
        {"$schema", "schema_version", "review_workflow", "geometry_definitions", "symbols"},
        "$",
        issues,
    )
    schema_version = read_document.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        _issue(
            issues,
            "UNSUPPORTED_SCHEMA_VERSION",
            "$.schema_version",
            f"expected {SCHEMA_VERSION!r}",
        )

    document_status = _parse_document_workflow(read_document, issues)
    geometry_definitions = _parse_records(
        read_document,
        "geometry_definitions",
        _parse_geometry_definition,
        issues,
    )
    symbols, reviews = _parse_symbols(read_document, issues)
    library = SymbolDependencyLibrary(
        symbols=tuple(symbols),
        geometry_definitions=tuple(geometry_definitions),
    )
    library_validation = library.validate()
    for library_issue in library_validation.issues:
        issues.append(
            SymbolReviewIssue(
                code=f"LIBRARY_{library_issue.code}",
                path=_library_issue_path(library_issue),
                message=library_issue.message,
                severity=(
                    ReviewIssueSeverity.ERROR
                    if library_issue.severity is ValidationSeverity.ERROR
                    else ReviewIssueSeverity.WARNING
                ),
            )
        )

    for index, (symbol, review) in enumerate(zip(symbols, reviews, strict=True)):
        _validate_review_safety(symbol, review, index, issues)

    if document_status is ReviewDocumentStatus.REVIEW_COMPLETE:
        for index, definition in enumerate(geometry_definitions):
            held_out_source_ids = sorted(
                source.source_id for source in definition.sources if source.held_out
            )
            if held_out_source_ids:
                _issue(
                    issues,
                    "HELD_OUT_SOURCE_CANNOT_BE_PROMOTED",
                    f"$.geometry_definitions[{index}].sources",
                    "REVIEW_COMPLETE cannot promote held-out geometry sources: "
                    f"{held_out_source_ids!r}",
                )

    pending_count = sum(
        review.status is ReviewItemStatus.PENDING_HUMAN_REVIEW
        for review in reviews
    )
    if (
        document_status is ReviewDocumentStatus.REVIEW_COMPLETE
        and pending_count
    ):
        _issue(
            issues,
            "DOCUMENT_MARKED_COMPLETE_WITH_PENDING_ITEMS",
            "$.review_workflow.document_status",
            "REVIEW_COMPLETE cannot contain pending symbol reviews",
        )
    ordered = tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.severity.value,
                issue.code,
                issue.path,
                issue.message,
            ),
        )
    )
    validation = SymbolReviewValidation(
        issues=ordered,
        library_validation=library_validation,
        document_status=document_status,
        symbol_count=len(symbols),
        pending_symbol_count=pending_count,
    )
    return SymbolReviewLoadResult(dict(read_document), library, validation)


def validate_symbol_review_document(
    source: str | Path | Mapping[str, Any],
) -> SymbolReviewValidation:
    return load_symbol_review_document(source).validation


def promote_symbol_review_document(
    source: str | Path | Mapping[str, Any],
) -> SymbolDependencyLibrary:
    """Return a production library only after complete, valid human review."""

    result = load_symbol_review_document(source)
    if not result.validation.promotion_ready:
        codes = sorted({issue.code for issue in result.validation.errors})
        if result.validation.document_status is not ReviewDocumentStatus.REVIEW_COMPLETE:
            codes.append("DOCUMENT_REVIEW_NOT_COMPLETE")
        if result.validation.pending_symbol_count:
            codes.append("PENDING_SYMBOL_REVIEW")
        detail = ", ".join(sorted(set(codes))) or "NO_REVIEWED_SYMBOLS"
        raise SymbolReviewPromotionError(
            f"symbol review document is not promotion-ready: {detail}"
        )
    return result.library


def _source_library(source: Any) -> SymbolDependencyLibrary:
    if isinstance(source, SymbolDependencyLibrary):
        return source
    library = getattr(source, "library", None)
    if isinstance(library, SymbolDependencyLibrary):
        return library
    raise TypeError(
        "source must be a SymbolDependencyLibrary or expose a library attribute"
    )


def _review_reason_codes(symbol: SymbolDefinition) -> list[str]:
    reasons = ["HUMAN_REVIEW_REQUIRED"]
    if not any(
        alias.namespace.casefold() == "definition_name" for alias in symbol.aliases
    ):
        reasons.append("DEFINITION_NAME_REVIEW_REQUIRED")
    if not symbol.ports or any(
        port.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED
        for port in symbol.ports
    ):
        reasons.append("PORT_ANNOTATION_REQUIRED")
    if symbol.internal_connectivity_groups:
        reasons.append("INTERNAL_CONNECTIVITY_REVIEW_REQUIRED")
    if symbol.symbol_dependencies:
        reasons.append("NESTED_DEPENDENCY_REVIEW_REQUIRED")
    if not symbol.sources:
        reasons.append("SOURCE_EVIDENCE_REQUIRED")
    return reasons


def _read_document(
    source: str | Path | Mapping[str, Any],
) -> tuple[dict[str, Any] | None, SymbolReviewIssue | None]:
    if isinstance(source, Mapping):
        return dict(source), None
    path = Path(source)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, SymbolReviewIssue(
            code="REVIEW_DOCUMENT_READ_FAILED",
            path=str(path),
            message=str(exc),
        )
    if not isinstance(payload, Mapping):
        return None, SymbolReviewIssue(
            code="REVIEW_DOCUMENT_ROOT_INVALID",
            path="$",
            message="review document root must be an object",
        )
    return dict(payload), None


def _parse_document_workflow(
    document: Mapping[str, Any],
    issues: list[SymbolReviewIssue],
) -> ReviewDocumentStatus | None:
    raw = document.get("review_workflow")
    if not isinstance(raw, Mapping):
        _issue(
            issues,
            "REVIEW_WORKFLOW_MISSING",
            "$.review_workflow",
            "review_workflow must be an object",
        )
        return None
    _unexpected_fields(raw, {"workflow_version", "document_status", "notes"}, "$.review_workflow", issues)
    if raw.get("workflow_version") != REVIEW_WORKFLOW_VERSION:
        _issue(
            issues,
            "UNSUPPORTED_REVIEW_WORKFLOW_VERSION",
            "$.review_workflow.workflow_version",
            f"expected {REVIEW_WORKFLOW_VERSION!r}",
        )
    try:
        _nullable_text(raw, "notes", "$.review_workflow")
    except _ParseError as exc:
        _issue(issues, "SCHEMA_INVALID", exc.path, str(exc))
    try:
        return _enum(
            ReviewDocumentStatus,
            raw.get("document_status"),
            "$.review_workflow.document_status",
        )
    except _ParseError as exc:
        _issue(issues, "SCHEMA_INVALID", exc.path, str(exc))
        return None


def _parse_records(
    document: Mapping[str, Any],
    field: str,
    parser: Any,
    issues: list[SymbolReviewIssue],
) -> list[Any]:
    raw = document.get(field)
    if not isinstance(raw, list):
        _issue(
            issues,
            "SCHEMA_INVALID",
            f"$.{field}",
            f"{field} must be an array",
        )
        return []
    parsed: list[Any] = []
    for index, item in enumerate(raw):
        path = f"$.{field}[{index}]"
        if not isinstance(item, Mapping):
            _issue(issues, "SCHEMA_INVALID", path, "item must be an object")
            continue
        try:
            parsed.append(parser(item, path, issues))
        except _ParseError as exc:
            _issue(issues, "SCHEMA_INVALID", exc.path, str(exc))
    return parsed


def _parse_symbols(
    document: Mapping[str, Any],
    issues: list[SymbolReviewIssue],
) -> tuple[list[SymbolDefinition], list[_ReviewMetadata]]:
    raw = document.get("symbols")
    if not isinstance(raw, list):
        _issue(issues, "SCHEMA_INVALID", "$.symbols", "symbols must be an array")
        return [], []
    symbols: list[SymbolDefinition] = []
    reviews: list[_ReviewMetadata] = []
    for index, item in enumerate(raw):
        path = f"$.symbols[{index}]"
        if not isinstance(item, Mapping):
            _issue(issues, "SCHEMA_INVALID", path, "symbol must be an object")
            continue
        try:
            symbol, review = _parse_symbol(item, path, issues)
        except _ParseError as exc:
            _issue(issues, "SCHEMA_INVALID", exc.path, str(exc))
            continue
        symbols.append(symbol)
        reviews.append(review)
    return symbols, reviews


def _parse_geometry_definition(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> GeometryDefinition:
    _unexpected_fields(
        row,
        {"definition_id", "version", "fingerprint", "aliases", "sources"},
        path,
        issues,
    )
    return GeometryDefinition(
        identity=GeometryIdentity(
            definition_id=_required_text(row, "definition_id", path),
            version=_required_text(row, "version", path),
            fingerprint=_required_text(row, "fingerprint", path),
        ),
        aliases=tuple(_parse_aliases(row, path, issues)),
        sources=tuple(_parse_sources(row, path, issues)),
    )


def _parse_symbol(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> tuple[SymbolDefinition, _ReviewMetadata]:
    _unexpected_fields(
        row,
        {
            "backlog_rank",
            "review_reason_codes",
            "family",
            "version",
            "fingerprint",
            "definition_names",
            "geometry_dependencies",
            "symbol_dependencies",
            "ports",
            "internal_connectivity_groups",
            "aliases",
            "sources",
            "annotation_status",
            "registry_status",
            "critical_issue_eligible",
            "review",
        },
        path,
        issues,
    )
    _required_positive_int(row, "backlog_rank", path)
    _string_list(row, "review_reason_codes", path)
    aliases = [
        SymbolAlias(value=name, namespace="definition_name")
        for name in _string_list(row, "definition_names", path)
    ]
    aliases.extend(_parse_aliases(row, path, issues))
    symbol = SymbolDefinition(
        identity=SymbolIdentity(
            family=_required_text(row, "family", path),
            version=_required_text(row, "version", path),
            fingerprint=_required_text(row, "fingerprint", path),
        ),
        geometry_dependencies=tuple(
            _parse_geometry_dependencies(row, path, issues)
        ),
        symbol_dependencies=tuple(_parse_symbol_dependencies(row, path, issues)),
        ports=tuple(_parse_ports(row, path, issues)),
        internal_connectivity_groups=tuple(
            _parse_connectivity_groups(row, path, issues)
        ),
        aliases=tuple(aliases),
        sources=tuple(_parse_sources(row, path, issues)),
        annotation_status=_enum(
            AnnotationStatus,
            row.get("annotation_status"),
            f"{path}.annotation_status",
        ),
        registry_status=_enum(
            RegistryStatus,
            row.get("registry_status"),
            f"{path}.registry_status",
        ),
        critical_issue_eligible=_required_bool(
            row, "critical_issue_eligible", path
        ),
    )
    return symbol, _parse_review_metadata(row, path, issues)


def _parse_geometry_dependencies(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> list[GeometryDefinitionDependency]:
    items = _mapping_list(row, "geometry_dependencies", path)
    parsed: list[GeometryDefinitionDependency] = []
    for index, item in enumerate(items):
        item_path = f"{path}.geometry_dependencies[{index}]"
        _unexpected_fields(item, {"dependency_id", "target", "required"}, item_path, issues)
        target = _required_mapping(item, "target", item_path)
        _unexpected_fields(target, {"definition_id", "version", "fingerprint"}, f"{item_path}.target", issues)
        parsed.append(
            GeometryDefinitionDependency(
                dependency_id=_required_text(item, "dependency_id", item_path),
                target=GeometryIdentity(
                    definition_id=_required_text(target, "definition_id", f"{item_path}.target"),
                    version=_required_text(target, "version", f"{item_path}.target"),
                    fingerprint=_required_text(target, "fingerprint", f"{item_path}.target"),
                ),
                required=_required_bool(item, "required", item_path),
            )
        )
    return parsed


def _parse_symbol_dependencies(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> list[SymbolDependency]:
    items = _mapping_list(row, "symbol_dependencies", path)
    parsed: list[SymbolDependency] = []
    for index, item in enumerate(items):
        item_path = f"{path}.symbol_dependencies[{index}]"
        _unexpected_fields(
            item,
            {"dependency_id", "target", "instance_name", "local_transform", "port_bindings", "required"},
            item_path,
            issues,
        )
        target = _required_mapping(item, "target", item_path)
        _unexpected_fields(target, {"family", "version", "fingerprint"}, f"{item_path}.target", issues)
        bindings: list[NestedPortBinding] = []
        for binding_index, binding in enumerate(
            _mapping_list(item, "port_bindings", item_path)
        ):
            binding_path = f"{item_path}.port_bindings[{binding_index}]"
            _unexpected_fields(binding, {"parent_port_id", "child_port_id"}, binding_path, issues)
            bindings.append(
                NestedPortBinding(
                    parent_port_id=_required_text(binding, "parent_port_id", binding_path),
                    child_port_id=_required_text(binding, "child_port_id", binding_path),
                )
            )
        parsed.append(
            SymbolDependency(
                dependency_id=_required_text(item, "dependency_id", item_path),
                target=SymbolIdentity(
                    family=_required_text(target, "family", f"{item_path}.target"),
                    version=_required_text(target, "version", f"{item_path}.target"),
                    fingerprint=_required_text(target, "fingerprint", f"{item_path}.target"),
                ),
                instance_name=_nullable_text(item, "instance_name", item_path),
                local_transform=tuple(
                    _number_list(item, "local_transform", item_path)
                ),
                port_bindings=tuple(bindings),
                required=_required_bool(item, "required", item_path),
            )
        )
    return parsed


def _parse_ports(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> list[SymbolPort]:
    items = _mapping_list(row, "ports", path)
    parsed: list[SymbolPort] = []
    for index, item in enumerate(items):
        item_path = f"{path}.ports[{index}]"
        _unexpected_fields(
            item,
            {"port_id", "local_position", "outward_direction", "port_type", "aliases", "source_ids", "annotation_status"},
            item_path,
            issues,
        )
        parsed.append(
            SymbolPort(
                port_id=_required_text(item, "port_id", item_path),
                local_position=_vector(item, "local_position", item_path),
                outward_direction=_vector(item, "outward_direction", item_path),
                port_type=_enum(PortType, item.get("port_type"), f"{item_path}.port_type"),
                aliases=tuple(_string_list(item, "aliases", item_path)),
                source_ids=tuple(_string_list(item, "source_ids", item_path)),
                annotation_status=_enum(
                    AnnotationStatus,
                    item.get("annotation_status"),
                    f"{item_path}.annotation_status",
                ),
            )
        )
    return parsed


def _parse_connectivity_groups(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> list[InternalConnectivityGroup]:
    items = _mapping_list(row, "internal_connectivity_groups", path)
    parsed: list[InternalConnectivityGroup] = []
    for index, item in enumerate(items):
        item_path = f"{path}.internal_connectivity_groups[{index}]"
        _unexpected_fields(
            item,
            {"group_id", "port_ids", "state", "annotation_status", "source_ids"},
            item_path,
            issues,
        )
        parsed.append(
            InternalConnectivityGroup(
                group_id=_required_text(item, "group_id", item_path),
                port_ids=tuple(_string_list(item, "port_ids", item_path)),
                state=_enum(
                    ConnectivityAssertionState,
                    item.get("state"),
                    f"{item_path}.state",
                ),
                annotation_status=_enum(
                    AnnotationStatus,
                    item.get("annotation_status"),
                    f"{item_path}.annotation_status",
                ),
                source_ids=tuple(_string_list(item, "source_ids", item_path)),
            )
        )
    return parsed


def _parse_aliases(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> list[SymbolAlias]:
    items = _mapping_list(row, "aliases", path)
    parsed: list[SymbolAlias] = []
    for index, item in enumerate(items):
        item_path = f"{path}.aliases[{index}]"
        _unexpected_fields(item, {"value", "namespace", "source_id"}, item_path, issues)
        parsed.append(
            SymbolAlias(
                value=_required_text(item, "value", item_path),
                namespace=_required_text(item, "namespace", item_path),
                source_id=_nullable_text(item, "source_id", item_path),
            )
        )
    return parsed


def _parse_sources(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> list[SourceReference]:
    items = _mapping_list(row, "sources", path)
    parsed: list[SourceReference] = []
    for index, item in enumerate(items):
        item_path = f"{path}.sources[{index}]"
        _unexpected_fields(
            item,
            {"source_id", "source_kind", "locator", "project_id", "held_out"},
            item_path,
            issues,
        )
        parsed.append(
            SourceReference(
                source_id=_required_text(item, "source_id", item_path),
                source_kind=_required_text(item, "source_kind", item_path),
                locator=_required_text(item, "locator", item_path),
                project_id=_nullable_text(item, "project_id", item_path),
                held_out=_required_bool(item, "held_out", item_path),
            )
        )
    return parsed


def _parse_review_metadata(
    row: Mapping[str, Any],
    path: str,
    issues: list[SymbolReviewIssue],
) -> _ReviewMetadata:
    review = _required_mapping(row, "review", path)
    review_path = f"{path}.review"
    _unexpected_fields(
        review,
        {"status", "reviewer", "reviewed_at", "evidence_source_ids", "notes"},
        review_path,
        issues,
    )
    _nullable_text(review, "notes", review_path)
    return _ReviewMetadata(
        status=_enum(ReviewItemStatus, review.get("status"), f"{review_path}.status"),
        reviewer=_nullable_text(review, "reviewer", review_path),
        reviewed_at=_nullable_text(review, "reviewed_at", review_path),
        evidence_source_ids=tuple(
            _string_list(review, "evidence_source_ids", review_path)
        ),
    )


def _validate_review_safety(
    symbol: SymbolDefinition,
    review: _ReviewMetadata,
    index: int,
    issues: list[SymbolReviewIssue],
) -> None:
    path = f"$.symbols[{index}]"
    asserted = [
        group
        for group in symbol.internal_connectivity_groups
        if group.state is ConnectivityAssertionState.ASSERTED
    ]
    if review.status is ReviewItemStatus.PENDING_HUMAN_REVIEW:
        if symbol.critical_issue_eligible:
            _issue(
                issues,
                "PENDING_SYMBOL_CANNOT_BE_CRITICAL",
                f"{path}.critical_issue_eligible",
                "pending symbol review cannot be critical-issue eligible",
            )
        if asserted:
            _issue(
                issues,
                "PENDING_SYMBOL_CANNOT_ASSERT_CONNECTIVITY",
                f"{path}.internal_connectivity_groups",
                "pending symbol review cannot contain ASSERTED connectivity",
            )
        if symbol.registry_status is RegistryStatus.REGISTERED:
            _issue(
                issues,
                "PENDING_SYMBOL_CANNOT_BE_REGISTERED",
                f"{path}.registry_status",
                "pending symbol review cannot be REGISTERED",
            )
        if review.reviewer or review.reviewed_at or review.evidence_source_ids:
            _issue(
                issues,
                "PENDING_REVIEW_METADATA_MUST_BE_EMPTY",
                f"{path}.review",
                "pending review must not claim reviewer, time, or review evidence",
            )

    for group_index, group in enumerate(symbol.internal_connectivity_groups):
        if (
            group.annotation_status is AnnotationStatus.PENDING_HUMAN_REVIEW
            and group.state is ConnectivityAssertionState.ASSERTED
        ):
            _issue(
                issues,
                "PENDING_CONNECTIVITY_CANNOT_BE_ASSERTED",
                f"{path}.internal_connectivity_groups[{group_index}]",
                "pending connectivity annotation cannot be ASSERTED",
            )

    if review.status in {
        ReviewItemStatus.HUMAN_CONFIRMED,
        ReviewItemStatus.REJECTED,
    }:
        if not review.reviewer:
            _issue(
                issues,
                "REVIEWER_REQUIRED",
                f"{path}.review.reviewer",
                "completed review requires a reviewer",
            )
        if not review.reviewed_at or not _valid_review_timestamp(review.reviewed_at):
            _issue(
                issues,
                "REVIEW_TIMESTAMP_REQUIRED",
                f"{path}.review.reviewed_at",
                "completed review requires an ISO-8601 timestamp with timezone",
            )
        if not review.evidence_source_ids:
            _issue(
                issues,
                "REVIEW_EVIDENCE_REQUIRED",
                f"{path}.review.evidence_source_ids",
                "completed review requires at least one source id",
            )

    source_ids = {source.source_id for source in symbol.sources}
    missing_review_sources = set(review.evidence_source_ids) - source_ids
    if missing_review_sources:
        _issue(
            issues,
            "DANGLING_REVIEW_EVIDENCE",
            f"{path}.review.evidence_source_ids",
            f"unknown source ids: {sorted(missing_review_sources)!r}",
        )

    if review.status in {
        ReviewItemStatus.HUMAN_CONFIRMED,
        ReviewItemStatus.REJECTED,
    }:
        held_out_source_ids = sorted(
            source.source_id for source in symbol.sources if source.held_out
        )
        if held_out_source_ids:
            _issue(
                issues,
                "HELD_OUT_SOURCE_CANNOT_BE_PROMOTED",
                f"{path}.sources",
                "completed symbol review cannot promote held-out sources: "
                f"{held_out_source_ids!r}",
            )

        review_sources = [
            source
            for source in symbol.sources
            if source.source_id in review.evidence_source_ids
        ]
        if not any(
            not source.held_out
            and _source_kind_class(source.source_kind) == "primary"
            for source in review_sources
        ):
            evidence_kinds = sorted(
                {
                    _canonical_source_kind(source.source_kind)
                    for source in review_sources
                }
            )
            _issue(
                issues,
                "PRIMARY_REVIEW_EVIDENCE_REQUIRED",
                f"{path}.review.evidence_source_ids",
                "completed review requires at least one non-held-out original "
                "drawing or human-review primary source; derived or unknown "
                f"source kinds do not qualify: {evidence_kinds!r}",
            )

    if review.status is ReviewItemStatus.HUMAN_CONFIRMED:
        if symbol.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED:
            _issue(
                issues,
                "CONFIRMED_REVIEW_REQUIRES_CONFIRMED_ANNOTATION",
                f"{path}.annotation_status",
                "human-confirmed review requires HUMAN_CONFIRMED annotation",
            )
    elif review.status is ReviewItemStatus.REJECTED:
        if symbol.annotation_status is not AnnotationStatus.REJECTED:
            _issue(
                issues,
                "REJECTED_REVIEW_REQUIRES_REJECTED_ANNOTATION",
                f"{path}.annotation_status",
                "rejected review requires REJECTED annotation",
            )
        if symbol.critical_issue_eligible or asserted:
            _issue(
                issues,
                "REJECTED_SYMBOL_CANNOT_BE_AUTHORITATIVE",
                path,
                "rejected symbol cannot be critical or assert connectivity",
            )

    has_confirmed_children = any(
        port.annotation_status is AnnotationStatus.HUMAN_CONFIRMED
        for port in symbol.ports
    ) or any(
        group.annotation_status is AnnotationStatus.HUMAN_CONFIRMED
        for group in symbol.internal_connectivity_groups
    )
    if has_confirmed_children and review.status is not ReviewItemStatus.HUMAN_CONFIRMED:
        _issue(
            issues,
            "CONFIRMED_CHILD_REQUIRES_CONFIRMED_REVIEW",
            path,
            "confirmed ports or connectivity require a human-confirmed symbol review",
        )
    if (
        symbol.registry_status is RegistryStatus.REGISTERED
        and review.status is not ReviewItemStatus.HUMAN_CONFIRMED
    ):
        _issue(
            issues,
            "REGISTERED_SYMBOL_REQUIRES_CONFIRMED_REVIEW",
            f"{path}.registry_status",
            "REGISTERED symbol requires a human-confirmed review",
        )


def _required_mapping(
    row: Mapping[str, Any], field: str, path: str
) -> Mapping[str, Any]:
    value = row.get(field)
    if not isinstance(value, Mapping):
        raise _ParseError(f"{path}.{field}", f"{field} must be an object")
    return value


def _canonical_source_kind(value: str) -> str:
    return value.strip().casefold().replace("-", "_").replace(" ", "_")


def _source_kind_class(value: str) -> str:
    kind = _canonical_source_kind(value)
    if kind in _PRIMARY_REVIEW_SOURCE_KINDS:
        return "primary"
    if kind in _DERIVED_REVIEW_SOURCE_KINDS:
        return "derived"
    return "unknown"


def _mapping_list(
    row: Mapping[str, Any], field: str, path: str
) -> list[Mapping[str, Any]]:
    value = row.get(field)
    if not isinstance(value, list):
        raise _ParseError(f"{path}.{field}", f"{field} must be an array")
    if any(not isinstance(item, Mapping) for item in value):
        raise _ParseError(
            f"{path}.{field}", f"every {field} item must be an object"
        )
    return list(value)


def _string_list(row: Mapping[str, Any], field: str, path: str) -> list[str]:
    value = row.get(field)
    if not isinstance(value, list):
        raise _ParseError(f"{path}.{field}", f"{field} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise _ParseError(
            f"{path}.{field}", f"every {field} item must be a non-empty string"
        )
    if len({item.casefold() for item in value}) != len(value):
        raise _ParseError(f"{path}.{field}", f"{field} values must be unique")
    return list(value)


def _number_list(row: Mapping[str, Any], field: str, path: str) -> list[float]:
    value = row.get(field)
    if not isinstance(value, list):
        raise _ParseError(f"{path}.{field}", f"{field} must be an array")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise _ParseError(
                f"{path}.{field}", f"every {field} item must be a number"
            )
        numeric = float(item)
        if not math.isfinite(numeric):
            raise _ParseError(
                f"{path}.{field}", f"every {field} item must be finite"
            )
        result.append(numeric)
    return result


def _vector(
    row: Mapping[str, Any], field: str, path: str
) -> tuple[float, float, float]:
    values = _number_list(row, field, path)
    if len(values) != 3:
        raise _ParseError(
            f"{path}.{field}", f"{field} must contain exactly three numbers"
        )
    return (values[0], values[1], values[2])


def _required_text(row: Mapping[str, Any], field: str, path: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _ParseError(
            f"{path}.{field}", f"{field} must be a non-empty string"
        )
    return value


def _nullable_text(
    row: Mapping[str, Any], field: str, path: str
) -> str | None:
    value = row.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _ParseError(
            f"{path}.{field}", f"{field} must be null or a non-empty string"
        )
    return value


def _required_bool(row: Mapping[str, Any], field: str, path: str) -> bool:
    value = row.get(field)
    if not isinstance(value, bool):
        raise _ParseError(f"{path}.{field}", f"{field} must be a boolean")
    return value


def _required_positive_int(
    row: Mapping[str, Any], field: str, path: str
) -> int:
    value = row.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _ParseError(
            f"{path}.{field}", f"{field} must be a positive integer"
        )
    return value


def _enum(enum_type: type[Any], value: Any, path: str) -> Any:
    if not isinstance(value, str):
        raise _ParseError(path, "value must be a string enum")
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = sorted(item.value for item in enum_type)
        raise _ParseError(path, f"value must be one of {allowed!r}") from exc


def _unexpected_fields(
    row: Mapping[str, Any],
    allowed: set[str],
    path: str,
    issues: list[SymbolReviewIssue],
) -> None:
    for field in sorted(set(row) - allowed):
        _issue(
            issues,
            "UNEXPECTED_FIELD",
            f"{path}.{field}",
            "field is not defined by the symbol library review schema",
        )


def _valid_review_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _library_issue_path(issue: Any) -> str:
    if issue.symbol_id:
        return f"symbol:{issue.symbol_id}"
    if issue.dependency_id:
        return f"dependency:{issue.dependency_id}"
    if issue.port_id:
        return f"port:{issue.port_id}"
    return "$"


def _issue(
    issues: list[SymbolReviewIssue],
    code: str,
    path: str,
    message: str,
    severity: ReviewIssueSeverity = ReviewIssueSeverity.ERROR,
) -> None:
    issues.append(SymbolReviewIssue(code, path, message, severity))


def _enum_value(value: StrEnum | str) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


__all__ = [
    "REVIEW_SCHEMA_FILENAME",
    "REVIEW_WORKFLOW_VERSION",
    "ReviewDocumentStatus",
    "ReviewItemStatus",
    "SymbolReviewIssue",
    "SymbolReviewLoadResult",
    "SymbolReviewPromotionError",
    "SymbolReviewValidation",
    "build_symbol_review_document",
    "load_symbol_review_document",
    "promote_symbol_review_document",
    "validate_symbol_review_document",
    "write_symbol_review_template",
]
