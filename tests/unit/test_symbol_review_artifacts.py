from __future__ import annotations

import json
from pathlib import Path

import dwg_audit.report.symbol_review_artifacts as symbol_review_artifacts
from dwg_audit.audit.symbol_dependency_artifacts import (
    SymbolDependencyArtifactBundle,
)
from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import (
    ConnectivityAssertionState,
)
from dwg_audit.audit.symbol_dependency_library import InternalConnectivityGroup
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SourceReference
from dwg_audit.audit.symbol_dependency_library import SymbolAlias
from dwg_audit.audit.symbol_dependency_library import SymbolDefinition
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity
from dwg_audit.audit.symbol_dependency_library import SymbolPort
from dwg_audit.audit.symbol_library_review import load_symbol_review_document
from dwg_audit.report.symbol_review_artifacts import BACKLOG_FILENAME
from dwg_audit.report.symbol_review_artifacts import SUMMARY_FILENAME
from dwg_audit.report.symbol_review_artifacts import VALIDATION_FILENAME
from dwg_audit.report.symbol_review_artifacts import (
    build_symbol_review_artifacts,
)
from dwg_audit.report.symbol_review_artifacts import (
    write_symbol_review_artifacts,
)


def _authoritative_symbol(
    family: str = "relay",
    fingerprint: str = "fp-relay",
) -> SymbolDefinition:
    return SymbolDefinition(
        identity=SymbolIdentity(family, "1", fingerprint),
        ports=(
            SymbolPort(
                "B",
                (10.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
            ),
            SymbolPort(
                "A",
                (0.0, 0.0, 0.0),
                (-1.0, 0.0, 0.0),
                annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
            ),
        ),
        internal_connectivity_groups=(
            InternalConnectivityGroup(
                "closed",
                ("B", "A"),
                state=ConnectivityAssertionState.ASSERTED,
                annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
                source_ids=("review-1",),
            ),
        ),
        aliases=(
            SymbolAlias("RELAY_BLOCK", source_id="review-1"),
            SymbolAlias("K", namespace="device_prefix", source_id="review-1"),
        ),
        sources=(
            SourceReference(
                "review-1",
                "HUMAN_REVIEW",
                "review/relay.json",
            ),
        ),
        annotation_status=AnnotationStatus.HUMAN_CONFIRMED,
        registry_status=RegistryStatus.REGISTERED,
        critical_issue_eligible=True,
    )


def test_authoritative_source_is_downgraded_to_safe_pending_backlog(
    tmp_path: Path,
) -> None:
    library = SymbolDependencyLibrary(symbols=(_authoritative_symbol(),))

    summary = write_symbol_review_artifacts(
        library,
        tmp_path,
        project_id="P001",
    )

    backlog = json.loads((tmp_path / BACKLOG_FILENAME).read_text("utf-8"))
    validation = json.loads(
        (tmp_path / VALIDATION_FILENAME).read_text("utf-8")
    )
    symbol = backlog["symbols"][0]
    assert symbol["review"]["status"] == "PENDING_HUMAN_REVIEW"
    assert symbol["annotation_status"] == "PENDING_HUMAN_REVIEW"
    assert symbol["registry_status"] == "UNKNOWN"
    assert symbol["critical_issue_eligible"] is False
    assert {port["annotation_status"] for port in symbol["ports"]} == {
        "PENDING_HUMAN_REVIEW"
    }
    assert symbol["internal_connectivity_groups"][0]["state"] == "UNKNOWN"
    assert validation["safety_contract"]["safe_pending_contract"] is True
    assert summary["status"] == "READY_FOR_REVIEW"
    assert summary["artifact_valid"] is True
    assert summary["critical_capable_count"] == 0
    assert summary["asserted_union_capable_pair_count"] == 0
    assert summary["promotion_ready"] is False
    assert load_symbol_review_document(backlog).validation.valid


def test_output_is_deterministic_across_source_order(tmp_path: Path) -> None:
    first = _authoritative_symbol("zeta", "fp-zeta")
    second = _authoritative_symbol("Alpha", "fp-alpha")
    one = SymbolDependencyLibrary(symbols=(first, second))
    two = SymbolDependencyLibrary(symbols=(second, first))
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    write_symbol_review_artifacts(one, first_dir, project_id="P1")
    write_symbol_review_artifacts(two, second_dir, project_id="P1")

    for filename in (BACKLOG_FILENAME, VALIDATION_FILENAME, SUMMARY_FILENAME):
        assert (first_dir / filename).read_bytes() == (
            second_dir / filename
        ).read_bytes()
    backlog = json.loads((first_dir / BACKLOG_FILENAME).read_text("utf-8"))
    assert [row["family"] for row in backlog["symbols"]] == ["Alpha", "zeta"]
    assert [row["backlog_rank"] for row in backlog["symbols"]] == [1, 2]
    assert [port["port_id"] for port in backlog["symbols"][0]["ports"]] == [
        "A",
        "B",
    ]


def test_empty_library_writes_complete_empty_schema(tmp_path: Path) -> None:
    summary = write_symbol_review_artifacts(
        SymbolDependencyLibrary(),
        tmp_path,
        project_id="P-EMPTY",
    )

    backlog = json.loads((tmp_path / BACKLOG_FILENAME).read_text("utf-8"))
    validation = json.loads(
        (tmp_path / VALIDATION_FILENAME).read_text("utf-8")
    )
    assert backlog["review_workflow"]["document_status"] == (
        "PENDING_HUMAN_REVIEW"
    )
    assert backlog["geometry_definitions"] == []
    assert backlog["symbols"] == []
    assert summary["status"] == "EMPTY"
    assert summary["artifact_valid"] is True
    assert summary["review_ready"] is False
    assert summary["promotion_ready"] is False
    assert validation["safety_contract"]["safe_pending_contract"] is True


def test_invalid_source_type_fails_closed_to_empty_backlog(tmp_path: Path) -> None:
    summary = write_symbol_review_artifacts(
        object(),
        tmp_path,
        project_id="P-BAD",
    )

    backlog = json.loads((tmp_path / BACKLOG_FILENAME).read_text("utf-8"))
    validation = json.loads(
        (tmp_path / VALIDATION_FILENAME).read_text("utf-8")
    )
    assert backlog["symbols"] == []
    assert summary["status"] == "ERROR"
    assert summary["artifact_valid"] is False
    assert validation["safety_contract"]["safe_pending_contract"] is True
    assert {item["code"] for item in validation["artifact_issues"]} == {
        "SYMBOL_REVIEW_BACKLOG_BUILD_FAILED"
    }
    assert validation["source"]["valid"] is False


def test_malformed_library_attribute_fails_closed_without_crashing() -> None:
    class MalformedBundle:
        source_status = "invalid"
        library = "not-a-symbol-library"

    artifacts = build_symbol_review_artifacts(
        MalformedBundle(),
        project_id="P-BAD-LIBRARY",
    )

    assert artifacts["summary"]["status"] == "ERROR"
    assert artifacts["backlog"]["symbols"] == []
    assert artifacts["validation"]["source"]["symbol_count"] == 0
    assert artifacts["validation"]["source"]["valid"] is False


def test_unsafe_generated_document_is_replaced_with_empty_pending_backlog(
    monkeypatch,
) -> None:
    library = SymbolDependencyLibrary(symbols=(_authoritative_symbol(),))
    original_builder = symbol_review_artifacts.build_symbol_review_document

    def unsafe_builder(source):
        document = original_builder(source)
        document["symbols"][0]["critical_issue_eligible"] = True
        return document

    monkeypatch.setattr(
        symbol_review_artifacts,
        "build_symbol_review_document",
        unsafe_builder,
    )

    artifacts = build_symbol_review_artifacts(library, project_id="P-UNSAFE")

    assert artifacts["summary"]["status"] == "ERROR"
    assert artifacts["backlog"]["symbols"] == []
    assert artifacts["summary"]["safe_pending_contract"] is True
    assert {item["code"] for item in artifacts["validation"]["artifact_issues"]} == {
        "UNSAFE_SYMBOL_REVIEW_BACKLOG_REPLACED"
    }


def test_source_load_error_is_preserved_and_cannot_report_valid() -> None:
    library = SymbolDependencyLibrary(symbols=(_authoritative_symbol(),))
    bundle = SymbolDependencyArtifactBundle(
        project_id="P1",
        library=library,
        validation=library.validate(),
        source_status="missing",
        source_path="missing.json",
        load_issues=(
            {
                "code": "SYMBOL_LIBRARY_NOT_FOUND",
                "message": "configured library is missing",
            },
        ),
    )

    artifacts = build_symbol_review_artifacts(bundle, project_id="P1")

    assert artifacts["summary"]["status"] == "INVALID"
    assert artifacts["summary"]["artifact_valid"] is False
    assert artifacts["summary"]["critical_issue_eligible_count"] == 0
    assert artifacts["summary"]["asserted_connectivity_group_count"] == 0
    assert artifacts["validation"]["source"]["error_count"] == 1
    assert artifacts["backlog"]["symbols"][0]["registry_status"] == "UNKNOWN"
