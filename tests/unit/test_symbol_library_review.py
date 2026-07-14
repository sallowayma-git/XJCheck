from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import ConnectivityAssertionState
from dwg_audit.audit.symbol_dependency_library import GeometryDefinition
from dwg_audit.audit.symbol_dependency_library import GeometryDefinitionDependency
from dwg_audit.audit.symbol_dependency_library import GeometryIdentity
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
from dwg_audit.audit.symbol_dependency_library import SymbolPort
from dwg_audit.audit.symbol_library_review import build_symbol_review_document
from dwg_audit.audit.symbol_library_review import load_symbol_review_document
from dwg_audit.audit.symbol_library_review import promote_symbol_review_document
from dwg_audit.audit.symbol_library_review import SymbolReviewPromotionError
from dwg_audit.audit.symbol_library_review import write_symbol_review_template


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "configs" / "symbol_dependency_library.schema.json"
EXAMPLE_PATH = REPO_ROOT / "configs" / "symbol_dependency_library.example.json"


def _source(source_id: str, locator: str) -> SourceReference:
    return SourceReference(
        source_id=source_id,
        source_kind="HUMAN_REVIEW_INPUT",
        locator=locator,
        project_id="P-REVIEW",
    )


def _port(port_id: str, x: float, direction: float) -> SymbolPort:
    return SymbolPort(
        port_id=port_id,
        local_position=(x, 0.0, 0.0),
        outward_direction=(direction, 0.0, 0.0),
        port_type=PortType.ELECTRICAL,
        aliases=(f"alias-{port_id}",),
        source_ids=("review-source",),
        annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
    )


def _authoritative_library() -> SymbolDependencyLibrary:
    geometry_identity = GeometryIdentity(
        definition_id="switch-body",
        version="1",
        fingerprint="geo-switch-v1",
    )
    geometry = GeometryDefinition(
        identity=geometry_identity,
        aliases=(SymbolAlias("SWITCH_BODY", source_id="review-source"),),
        sources=(_source("review-source", "review/switch-body.json"),),
    )
    child_identity = SymbolIdentity("contact", "1", "fp-contact")
    child = SymbolDefinition(
        identity=child_identity,
        ports=(_port("C", 0.0, 1.0),),
        aliases=(
            SymbolAlias(
                "CONTACT_BLOCK",
                namespace="definition_name",
                source_id="review-source",
            ),
        ),
        sources=(_source("review-source", "review/contact.json"),),
        annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
        registry_status=RegistryStatus.REGISTERED,
    )
    parent = SymbolDefinition(
        identity=SymbolIdentity("switch", "2", "fp-switch-v2"),
        geometry_dependencies=(
            GeometryDefinitionDependency("body", geometry_identity),
        ),
        symbol_dependencies=(
            SymbolDependency(
                dependency_id="contact-instance",
                target=child_identity,
                instance_name="K1",
                local_transform=(
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ),
                port_bindings=(NestedPortBinding("A", "C"),),
            ),
        ),
        ports=(_port("A", 0.0, -1.0), _port("B", 10.0, 1.0)),
        internal_connectivity_groups=(
            InternalConnectivityGroup(
                group_id="closed-path",
                port_ids=("A", "B"),
                state=ConnectivityAssertionState.ASSERTED,
                annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
                source_ids=("review-source",),
            ),
        ),
        aliases=(
            SymbolAlias(
                "SWITCH_BLOCK",
                namespace="definition_name",
                source_id="review-source",
            ),
            SymbolAlias("SW", namespace="device_code", source_id="review-source"),
        ),
        sources=(_source("review-source", "review/switch.json"),),
        annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
        registry_status=RegistryStatus.REGISTERED,
        critical_issue_eligible=True,
    )
    return SymbolDependencyLibrary(
        symbols=(parent, child),
        geometry_definitions=(geometry,),
    )


def _pending_two_port_document() -> dict[str, object]:
    library = SymbolDependencyLibrary(
        symbols=(
            SymbolDefinition(
                identity=SymbolIdentity("relay", "1", "fp-relay"),
                ports=(
                    SymbolPort(
                        port_id="A",
                        local_position=(0.0, 0.0, 0.0),
                        outward_direction=(-1.0, 0.0, 0.0),
                        port_type=PortType.ELECTRICAL,
                        source_ids=("review-source",),
                    ),
                    SymbolPort(
                        port_id="B",
                        local_position=(5.0, 0.0, 0.0),
                        outward_direction=(1.0, 0.0, 0.0),
                        port_type=PortType.ELECTRICAL,
                        source_ids=("review-source",),
                    ),
                ),
                internal_connectivity_groups=(
                    InternalConnectivityGroup(
                        group_id="path",
                        port_ids=("A", "B"),
                    ),
                ),
                aliases=(
                    SymbolAlias("RELAY_BLOCK", namespace="definition_name"),
                ),
                sources=(_source("review-source", "review/relay.json"),),
            ),
        )
    )
    return build_symbol_review_document(library)


def _complete_two_port_review(payload: dict[str, object]) -> None:
    payload["review_workflow"]["document_status"] = "REVIEW_COMPLETE"
    symbol = payload["symbols"][0]
    symbol["annotation_status"] = "HUMAN_CONFIRMED"
    symbol["registry_status"] = "REGISTERED"
    symbol["critical_issue_eligible"] = True
    symbol["review"] = {
        "status": "HUMAN_CONFIRMED",
        "reviewer": "reviewer@example.invalid",
        "reviewed_at": "2026-07-13T09:30:00+08:00",
        "evidence_source_ids": ["review-source"],
        "notes": "Identity, ports, and internal path reviewed against source.",
    }
    for port in symbol["ports"]:
        port["annotation_status"] = "HUMAN_CONFIRMED"
    group = symbol["internal_connectivity_groups"][0]
    group["state"] = "ASSERTED"
    group["annotation_status"] = "HUMAN_CONFIRMED"
    group["source_ids"] = ["review-source"]


def test_schema_and_example_are_safe_pending_assets() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "symbol" in schema["$defs"]
    assert "port" in schema["$defs"]
    result = load_symbol_review_document(example)

    assert result.validation.valid
    assert not result.validation.promotion_ready
    assert result.validation.pending_symbol_count == 1
    symbol = result.library.symbols[0]
    assert symbol.annotation_status is AnnotationStatus.PENDING_HUMAN_REVIEW
    assert symbol.registry_status is RegistryStatus.UNKNOWN
    assert not symbol.critical_issue_eligible
    assert all(
        port.annotation_status is AnnotationStatus.PENDING_HUMAN_REVIEW
        for port in symbol.ports
    )
    with pytest.raises(SymbolReviewPromotionError, match="not promotion-ready"):
        promote_symbol_review_document(example)


def test_generated_backlog_downgrades_authority_and_round_trips_fields(
    tmp_path: Path,
) -> None:
    library = _authoritative_library()
    template = build_symbol_review_document(SimpleNamespace(library=library))

    assert template["review_workflow"]["document_status"] == "PENDING_HUMAN_REVIEW"
    assert len(template["symbols"]) == 2
    parent = next(
        item for item in template["symbols"] if item["family"] == "switch"
    )
    assert parent["definition_names"] == ["SWITCH_BLOCK"]
    assert parent["ports"][0]["local_position"] == [0.0, 0.0, 0.0]
    assert parent["ports"][0]["outward_direction"] == [-1.0, 0.0, 0.0]
    assert parent["ports"][0]["port_type"] == "ELECTRICAL"
    assert parent["ports"][0]["annotation_status"] == "PENDING_HUMAN_REVIEW"
    assert parent["internal_connectivity_groups"][0]["state"] == "UNKNOWN"
    assert parent["symbol_dependencies"][0]["target"]["family"] == "contact"
    assert parent["geometry_dependencies"][0]["target"]["definition_id"] == "switch-body"
    assert parent["sources"][0]["source_id"] == "review-source"
    assert parent["annotation_status"] == "PENDING_HUMAN_REVIEW"
    assert parent["registry_status"] == "UNKNOWN"
    assert parent["critical_issue_eligible"] is False

    path = write_symbol_review_template(library, tmp_path / "symbol-review.json")
    result = load_symbol_review_document(path)

    assert result.validation.valid
    assert not result.validation.promotion_ready
    assert len(result.library.geometry_definitions) == 1
    loaded_parent = result.library.resolve(SymbolIdentity("switch", "2", "fp-switch-v2"))
    assert loaded_parent is not None
    assert loaded_parent.symbol_dependencies[0].port_bindings[0].child_port_id == "C"
    assert loaded_parent.geometry_dependencies[0].target.fingerprint == "geo-switch-v1"
    assert not result.library.can_drive_critical(loaded_parent.identity)
    assert not result.library.can_assert_electrical_union(
        loaded_parent.identity, "A", "B"
    )


def test_pending_review_cannot_claim_critical_or_asserted_connectivity() -> None:
    payload = _pending_two_port_document()
    symbol = payload["symbols"][0]
    symbol["critical_issue_eligible"] = True
    symbol["internal_connectivity_groups"][0]["state"] = "ASSERTED"

    result = load_symbol_review_document(payload)
    codes = {issue.code for issue in result.validation.errors}

    assert not result.validation.valid
    assert "PENDING_SYMBOL_CANNOT_BE_CRITICAL" in codes
    assert "PENDING_SYMBOL_CANNOT_ASSERT_CONNECTIVITY" in codes
    assert "PENDING_CONNECTIVITY_CANNOT_BE_ASSERTED" in codes
    with pytest.raises(SymbolReviewPromotionError):
        promote_symbol_review_document(payload)


def test_pending_machine_proposal_remains_valid_and_non_authoritative() -> None:
    payload = _pending_two_port_document()
    symbol = payload["symbols"][0]
    symbol["sources"][0]["source_kind"] = "machine_geometry_proposal"
    symbol["annotation_status"] = "MACHINE_PROPOSED"
    for port in symbol["ports"]:
        port["annotation_status"] = "MACHINE_PROPOSED"
    symbol["internal_connectivity_groups"][0][
        "annotation_status"
    ] = "MACHINE_PROPOSED"

    result = load_symbol_review_document(payload)

    assert result.validation.valid
    assert not result.validation.promotion_ready
    loaded = result.library.symbols[0]
    assert loaded.annotation_status is AnnotationStatus.MACHINE_PROPOSED
    assert loaded.registry_status is RegistryStatus.UNKNOWN
    assert not loaded.critical_issue_eligible


def test_complete_human_review_can_promote_critical_and_asserted_connectivity() -> None:
    payload = _pending_two_port_document()
    _complete_two_port_review(payload)

    result = load_symbol_review_document(payload)
    library = promote_symbol_review_document(payload)
    identity = SymbolIdentity("relay", "1", "fp-relay")

    assert result.validation.valid
    assert result.validation.promotion_ready
    assert library.can_drive_critical(identity)
    assert library.can_assert_electrical_union(identity, "A", "B")


@pytest.mark.parametrize(
    "source_kind",
    ["machine_geometry_proposal", "symbol_corpus_queue"],
)
def test_completed_review_rejects_derived_only_evidence(source_kind: str) -> None:
    payload = _pending_two_port_document()
    payload["symbols"][0]["sources"][0]["source_kind"] = source_kind
    _complete_two_port_review(payload)

    result = load_symbol_review_document(payload)
    codes = {issue.code for issue in result.validation.errors}

    assert "PRIMARY_REVIEW_EVIDENCE_REQUIRED" in codes
    assert not result.validation.promotion_ready
    with pytest.raises(
        SymbolReviewPromotionError, match="PRIMARY_REVIEW_EVIDENCE_REQUIRED"
    ):
        promote_symbol_review_document(payload)


def test_completed_review_allows_derived_support_with_primary_evidence() -> None:
    payload = _pending_two_port_document()
    symbol = payload["symbols"][0]
    symbol["sources"].append(
        {
            "source_id": "machine-proposal",
            "source_kind": "machine_geometry_proposal",
            "locator": "proposals/relay.json",
            "project_id": "P-REVIEW",
            "held_out": False,
        }
    )
    _complete_two_port_review(payload)
    symbol["review"]["evidence_source_ids"].append("machine-proposal")

    result = load_symbol_review_document(payload)

    assert result.validation.valid
    assert result.validation.promotion_ready
    assert promote_symbol_review_document(payload).symbols


def test_completed_review_rejects_held_out_primary_source() -> None:
    payload = _pending_two_port_document()
    payload["symbols"][0]["sources"][0]["held_out"] = True
    _complete_two_port_review(payload)

    result = load_symbol_review_document(payload)
    codes = {issue.code for issue in result.validation.errors}

    assert "HELD_OUT_SOURCE_CANNOT_BE_PROMOTED" in codes
    assert "PRIMARY_REVIEW_EVIDENCE_REQUIRED" in codes
    assert not result.validation.promotion_ready
    with pytest.raises(
        SymbolReviewPromotionError, match="HELD_OUT_SOURCE_CANNOT_BE_PROMOTED"
    ):
        promote_symbol_review_document(payload)


def test_completed_review_requires_reviewer_timestamp_and_known_evidence() -> None:
    payload = _pending_two_port_document()
    payload["review_workflow"]["document_status"] = "REVIEW_COMPLETE"
    symbol = payload["symbols"][0]
    symbol["annotation_status"] = "HUMAN_CONFIRMED"
    symbol["review"] = {
        "status": "HUMAN_CONFIRMED",
        "reviewer": None,
        "reviewed_at": "2026-07-13",
        "evidence_source_ids": ["missing-source"],
        "notes": None,
    }

    result = load_symbol_review_document(payload)
    codes = {issue.code for issue in result.validation.errors}

    assert {
        "REVIEWER_REQUIRED",
        "REVIEW_TIMESTAMP_REQUIRED",
        "DANGLING_REVIEW_EVIDENCE",
    }.issubset(codes)
    assert not result.validation.promotion_ready


def test_loader_fails_closed_on_unknown_or_malformed_fields() -> None:
    payload = deepcopy(_pending_two_port_document())
    payload["symbols"][0]["critical_issue_eligble"] = True
    payload["symbols"][0]["ports"][0]["outward_direction"] = [1.0, 0.0]

    result = load_symbol_review_document(payload)
    codes = {issue.code for issue in result.validation.errors}

    assert "UNEXPECTED_FIELD" in codes
    assert "SCHEMA_INVALID" in codes
    assert not result.validation.promotion_ready


def test_document_round_trip_through_json_mapping_is_deterministic() -> None:
    original = _pending_two_port_document()
    decoded = json.loads(json.dumps(original, sort_keys=True))

    result = load_symbol_review_document(decoded)
    regenerated = build_symbol_review_document(result.library)

    assert result.validation.valid
    assert regenerated["symbols"][0]["family"] == "relay"
    assert regenerated["symbols"][0]["version"] == "1"
    assert regenerated["symbols"][0]["fingerprint"] == "fp-relay"
    assert regenerated["symbols"][0]["definition_names"] == ["RELAY_BLOCK"]
    assert regenerated["symbols"][0]["ports"] == original["symbols"][0]["ports"]
