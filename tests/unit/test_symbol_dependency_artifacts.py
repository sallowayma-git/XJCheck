from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.audit.symbol_dependency_artifacts import build_symbol_dependency_artifacts
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity


def _inventory() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol_definition_id": "SD1-DEMO",
                "definition_name": "DEMO_BLOCK",
                "definition_fingerprint": "abc123",
                "symbol_family": None,
                "registry_status": "UNKNOWN",
                "critical_issue_eligible": False,
            }
        ]
    )


def test_inventory_only_library_remains_unknown_and_non_authoritative() -> None:
    bundle = build_symbol_dependency_artifacts(
        _inventory(), project_id="P1", config={}
    )

    assert bundle.source_status == "not_configured"
    assert bundle.validation.valid
    assert bundle.load_issues == ()
    assert len(bundle.library.symbols) == 1
    symbol = bundle.library.symbols[0]
    assert symbol.registry_status.value == "UNKNOWN"
    assert symbol.annotation_status.value == "PENDING_HUMAN_REVIEW"
    assert not bundle.library.can_drive_critical(symbol.identity)
    assert not bundle.library.can_assert_electrical_union(
        symbol.identity, "P1", "P2"
    )
    assert bundle.summary()["critical_capable_count"] == 0


def test_human_confirmed_config_can_register_ports_and_assert_connectivity(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "symbols.json"
    library_path.write_text(
        json.dumps(
            {
                "symbols": [
                    {
                        "family": "DEMO_FAMILY",
                        "version": "1",
                        "fingerprint": "abc123",
                        "definition_names": ["DEMO_BLOCK"],
                        "registry_status": "REGISTERED",
                        "annotation_status": "HUMAN_CONFIRMED",
                        "critical_issue_eligible": True,
                        "ports": [
                            {
                                "port_id": "P1",
                                "local_position": [0, 0, 0],
                                "outward_direction": [-1, 0, 0],
                                "port_type": "ELECTRICAL",
                                "annotation_status": "HUMAN_CONFIRMED",
                            },
                            {
                                "port_id": "P2",
                                "local_position": [10, 0, 0],
                                "outward_direction": [1, 0, 0],
                                "port_type": "ELECTRICAL",
                                "annotation_status": "HUMAN_CONFIRMED",
                            },
                        ],
                        "internal_connectivity_groups": [
                            {
                                "group_id": "G1",
                                "port_ids": ["P1", "P2"],
                                "state": "ASSERTED",
                                "annotation_status": "HUMAN_CONFIRMED",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    bundle = build_symbol_dependency_artifacts(
        _inventory(),
        project_id="P1",
        config={"symbol_library": {"path": str(library_path)}},
    )

    identity = SymbolIdentity("DEMO_FAMILY", "1", "abc123")
    assert bundle.source_status == "loaded"
    assert bundle.validation.valid
    assert len(bundle.library.symbols) == 1
    assert bundle.library.can_drive_critical(identity)
    assert bundle.library.can_assert_electrical_union(identity, "P1", "P2")
    assert bundle.summary()["critical_capable_count"] == 1


def test_unconfirmed_critical_record_is_invalid_and_cannot_drive_critical(
    tmp_path: Path,
) -> None:
    library_path = tmp_path / "symbols.json"
    library_path.write_text(
        json.dumps(
            {
                "symbols": [
                    {
                        "family": "DEMO_FAMILY",
                        "fingerprint": "abc123",
                        "definition_names": ["DEMO_BLOCK"],
                        "registry_status": "REGISTERED",
                        "annotation_status": "PENDING_HUMAN_REVIEW",
                        "critical_issue_eligible": True,
                        "ports": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    bundle = build_symbol_dependency_artifacts(
        _inventory(),
        project_id="P1",
        config={"symbol_library": {"path": str(library_path)}},
    )

    assert not bundle.validation.valid
    assert {
        issue.code for issue in bundle.validation.errors
    } >= {
        "CRITICAL_REQUIRES_HUMAN_CONFIRMATION",
        "CRITICAL_REQUIRES_CONFIRMED_PORTS",
    }
    assert bundle.summary()["critical_capable_count"] == 0


def test_missing_configured_library_is_reported_without_promoting_inventory(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"

    bundle = build_symbol_dependency_artifacts(
        _inventory(),
        project_id="P1",
        config={"symbol_library": {"path": str(missing)}},
    )

    assert bundle.source_status == "missing"
    assert bundle.load_issues[0]["code"] == "SYMBOL_LIBRARY_NOT_FOUND"
    assert bundle.summary()["library_valid"] is False
    assert bundle.library.symbols[0].registry_status.value == "UNKNOWN"


def test_pending_review_document_is_not_loaded_as_production_library(
    tmp_path: Path,
) -> None:
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "schema_version": "symbol-dependency-library-v1",
                "review_workflow": {
                    "workflow_version": "symbol-library-review-v1",
                    "document_status": "PENDING_HUMAN_REVIEW",
                    "notes": None,
                },
                "geometry_definitions": [],
                "symbols": [],
            }
        ),
        encoding="utf-8",
    )

    bundle = build_symbol_dependency_artifacts(
        _inventory(),
        project_id="P1",
        config={"symbol_library": {"path": str(review_path)}},
    )

    assert bundle.source_status == "review_not_ready"
    assert bundle.load_issues[0]["code"] == "SYMBOL_REVIEW_NOT_PROMOTION_READY"
    assert bundle.library.symbols[0].registry_status.value == "UNKNOWN"
    assert bundle.summary()["library_valid"] is False
