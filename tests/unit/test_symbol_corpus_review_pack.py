from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import PortType
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SourceReference
from dwg_audit.audit.symbol_dependency_library import SymbolAlias
from dwg_audit.audit.symbol_dependency_library import SymbolDefinition
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity
from dwg_audit.audit.symbol_dependency_library import SymbolPort
from dwg_audit.audit.symbol_port_shadow import build_symbol_port_shadow_placements
from dwg_audit.report.symbol_corpus_review_pack import consume_symbol_review_document
from dwg_audit.report.symbol_corpus_review_pack import write_symbol_corpus_review_pack


def _queue_payload() -> dict:
    return {
        "schema_version": "symbol-corpus-queue-v1",
        "queue": [
            {
                "review_rank": 1,
                "definition_fingerprint": "fp-top-1",
                "definition_names": ["SYM_A"],
                "total_instance_count": 100,
                "project_coverage": 2,
                "project_ids": ["P001", "P002"],
                "priority_score": 200,
            },
            {
                "review_rank": 2,
                "definition_fingerprint": "fp-top-2",
                "definition_names": ["SYM_B"],
                "total_instance_count": 50,
                "project_coverage": 1,
                "project_ids": ["P001"],
                "priority_score": 50,
            },
        ],
    }


def test_write_review_pack_is_pending_only(tmp_path: Path) -> None:
    result = write_symbol_corpus_review_pack(
        _queue_payload(),
        tmp_path / "pack",
        top_n=2,
    )
    summary = result["summary"]
    assert summary["status"] == "VALID"
    assert summary["template_symbol_count"] == 2
    assert summary["critical_issue_eligible_count"] == 0
    assert summary["promotion_ready"] is False

    combined = json.loads(result["combined_template_path"].read_text(encoding="utf-8"))
    assert combined["review_workflow"]["document_status"] == "PENDING_HUMAN_REVIEW"
    for symbol in combined["symbols"]:
        assert symbol["annotation_status"] == "PENDING_HUMAN_REVIEW"
        assert symbol["registry_status"] == "UNKNOWN"
        assert symbol["critical_issue_eligible"] is False
        assert symbol["ports"] == []

    consumption = consume_symbol_review_document(
        result["combined_template_path"],
        output_dir=tmp_path / "consume-pending",
        promote=False,
    )
    assert consumption["summary"]["valid"] is True
    assert consumption["summary"]["promotion_ready"] is False
    assert consumption["summary"]["promoted"] is False
    assert consumption["summary"]["critical_issue_eligible_count"] == 0


def test_colliding_definition_name_aliases_keep_highest_rank_only(tmp_path: Path) -> None:
    payload = {
        "schema_version": "symbol-corpus-queue-v1",
        "queue": [
            {
                "review_rank": 1,
                "definition_fingerprint": "fp-shared-a",
                "definition_names": ["SHARED_NAME"],
                "total_instance_count": 10,
                "project_coverage": 1,
                "project_ids": ["P001"],
                "priority_score": 10,
            },
            {
                "review_rank": 2,
                "definition_fingerprint": "fp-shared-b",
                "definition_names": ["SHARED_NAME"],
                "total_instance_count": 5,
                "project_coverage": 1,
                "project_ids": ["P001"],
                "priority_score": 5,
            },
        ],
    }
    result = write_symbol_corpus_review_pack(payload, tmp_path / "pack", top_n=2)
    assert result["summary"]["status"] == "VALID"
    assert result["summary"]["review_document_valid"] is True
    combined = json.loads(result["combined_template_path"].read_text(encoding="utf-8"))
    by_fp = {s["fingerprint"]: s for s in combined["symbols"]}
    # definition_name aliases are projected into definition_names for review docs.
    assert by_fp["fp-shared-a"]["definition_names"] == ["SHARED_NAME"]
    assert by_fp["fp-shared-b"]["definition_names"] == []
    # Library must remain unambiguous after collision stripping.
    consumption = consume_symbol_review_document(
        result["combined_template_path"],
        output_dir=tmp_path / "consume",
        promote=False,
    )
    assert consumption["summary"]["valid"] is True


def test_pending_pack_cannot_promote(tmp_path: Path) -> None:
    result = write_symbol_corpus_review_pack(
        _queue_payload(),
        tmp_path / "pack",
        top_n=1,
    )
    consumption = consume_symbol_review_document(
        result["combined_template_path"],
        output_dir=tmp_path / "consume",
        promote=True,
    )
    assert consumption["summary"]["promoted"] is False
    assert consumption["summary"]["promotion_error"]


def test_human_confirmed_review_can_promote_and_feed_port_shadow(tmp_path: Path) -> None:
    result = write_symbol_corpus_review_pack(
        _queue_payload(),
        tmp_path / "pack",
        top_n=1,
    )
    document = json.loads(result["combined_template_path"].read_text(encoding="utf-8"))
    symbol = document["symbols"][0]
    symbol["annotation_status"] = "HUMAN_CONFIRMED"
    symbol["registry_status"] = "REGISTERED"
    symbol["critical_issue_eligible"] = False
    primary_source_id = "human-review-input:fp-top-1"
    symbol["sources"].append(
        {
            "source_id": primary_source_id,
            "source_kind": "HUMAN_REVIEW_INPUT",
            "locator": "P001/F1/source.dwg",
            "project_id": "P001",
            "held_out": False,
        }
    )
    symbol["ports"] = [
        {
            "port_id": "A",
            "local_position": [0.0, 0.0, 0.0],
            "outward_direction": [1.0, 0.0, 0.0],
            "port_type": "ELECTRICAL",
            "aliases": [],
            "source_ids": [primary_source_id, "corpus-queue:fp-top-1"],
            "annotation_status": "HUMAN_CONFIRMED",
        },
        {
            "port_id": "B",
            "local_position": [10.0, 0.0, 0.0],
            "outward_direction": [-1.0, 0.0, 0.0],
            "port_type": "ELECTRICAL",
            "aliases": [],
            "source_ids": [primary_source_id, "corpus-queue:fp-top-1"],
            "annotation_status": "HUMAN_CONFIRMED",
        },
    ]
    symbol["review"] = {
        "status": "HUMAN_CONFIRMED",
        "reviewer": "reviewer@example.invalid",
        "reviewed_at": "2026-07-13T12:00:00+08:00",
        "evidence_source_ids": [primary_source_id, "corpus-queue:fp-top-1"],
        "notes": "Top-1 ports confirmed for shadow consumption test.",
    }
    document["review_workflow"]["document_status"] = "REVIEW_COMPLETE"

    edited = tmp_path / "edited-review.json"
    edited.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    consumption = consume_symbol_review_document(
        edited,
        output_dir=tmp_path / "consume-ready",
        promote=True,
    )
    assert consumption["summary"]["valid"] is True
    assert consumption["summary"]["promoted"] is True
    assert consumption["summary"]["shadow_eligible_port_count"] == 2
    assert consumption["summary"]["critical_issue_eligible_count"] == 0

    library = consumption["library"]
    instances = pd.DataFrame(
        [
            {
                "symbol_instance_id": "SI1",
                "project_id": "P001",
                "sheet_id": "S1",
                "file_id": "F1",
                "definition_name": "SYM_A",
                "definition_fingerprint": "fp-top-1",
                "transform_json": json.dumps(
                    {
                        "chain": [
                            {
                                "matrix44": [
                                    [1.0, 0.0, 0.0, 0.0],
                                    [0.0, 1.0, 0.0, 0.0],
                                    [0.0, 0.0, 1.0, 0.0],
                                    [100.0, 50.0, 0.0, 1.0],
                                ]
                            }
                        ]
                    }
                ),
            }
        ]
    )
    placements = build_symbol_port_shadow_placements(
        library, instances, project_id="P001"
    )
    assert len(placements) == 2
    assert all(not item.electrical_union_eligible for item in placements)
    assert all(not item.critical_issue_eligible for item in placements)
    by_port = {item.port_id: item for item in placements}
    assert by_port["A"].world_position == (100.0, 50.0, 0.0)
    assert by_port["B"].world_position == (110.0, 50.0, 0.0)


def test_unknown_library_ports_never_emit_shadow_placements() -> None:
    library = SymbolDependencyLibrary(
        symbols=(
            SymbolDefinition(
                identity=SymbolIdentity("relay", "1", "fp-x"),
                aliases=(
                    SymbolAlias(
                        value="REL",
                        namespace="definition_name",
                        source_id="s1",
                    ),
                ),
                sources=(
                    SourceReference(
                        source_id="s1",
                        source_kind="test",
                        locator="REL",
                    ),
                ),
                ports=(
                    SymbolPort(
                        port_id="A",
                        local_position=(0.0, 0.0, 0.0),
                        outward_direction=(1.0, 0.0, 0.0),
                        port_type=PortType.ELECTRICAL,
                        annotation_status=AnnotationStatus.PENDING_HUMAN_REVIEW,
                    ),
                ),
                annotation_status=AnnotationStatus.PENDING_HUMAN_REVIEW,
                registry_status=RegistryStatus.UNKNOWN,
                critical_issue_eligible=False,
            ),
        )
    )
    placements = build_symbol_port_shadow_placements(
        library,
        [
            {
                "symbol_instance_id": "SI1",
                "definition_name": "REL",
                "definition_fingerprint": "fp-x",
                "transform_json": None,
            }
        ],
    )
    assert placements == []
