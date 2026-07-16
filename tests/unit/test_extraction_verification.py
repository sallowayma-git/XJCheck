from __future__ import annotations

import json
from pathlib import Path

from dwg_audit.report.extraction_verification import evaluate_extraction_verification
from dwg_audit.report.extraction_verification import write_extraction_verification_artifacts


def _write_project(
    project_dir: Path,
    *,
    project_id: str = "demo",
    gate_status: str = "COMPLETE",
    incomplete_pages: int = 0,
    unassigned_wires: int = 10,
    lines: int = 100,
    unclassified_blocks: int = 5,
    blocks: int = 50,
    unknown_symbols: int = 0,
    scale_unresolved: int = 0,
    table_mappings: int = 3,
    component_mappings: int = 2,
    page_type: str = "二次原理图",
    route_target: str = "WireDiagramExtractor",
    page_confidence: float = 0.9,
    table_like: bool = False,
) -> None:
    findings = project_dir / "findings"
    audit = project_dir / "audit"
    findings.mkdir(parents=True)
    audit.mkdir(parents=True)

    (project_dir / "extraction_completeness.json").write_text(
        json.dumps(
            {
                "analysis_status": gate_status,
                "incomplete_page_count": incomplete_pages,
                "project_id": project_id,
                "pages": [
                    {
                        "sheet_id": "S0001",
                        "status": "COMPLETE",
                        "primitive_counts": {
                            "total": lines + blocks,
                            "text": 20,
                            "line": lines,
                            "block": blocks,
                            "polyline": 0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (findings / "findings.json").write_text(
        json.dumps(
            {
                "project_id": project_id,
                "sheet_count": 1,
                "included_audit_pages": 1,
                "file_count": 1,
                "stats": {
                    "texts": 20,
                    "lines": lines,
                    "blocks": blocks,
                    "polylines": 0,
                    "pairs": table_mappings + component_mappings + 1,
                    "issues": 0,
                },
                "entity_coverage_summary": {
                    "coverage_ratio": 1.0,
                    "unexplained_texts": 0,
                    "unassigned_wire_segments": unassigned_wires,
                    "unclassified_blocks": unclassified_blocks,
                },
                "pair_evidence_summary": {
                    "pair_kind_counts": {
                        "table_mapping": table_mappings,
                        "component_mapping": component_mappings,
                        "ordinary_pair": 1,
                    }
                },
                "page_findings": [
                    {
                        "sheet_id": "S0001",
                        "filename": "01 demo.dwg",
                        "sheet_no": "01",
                        "page_type": page_type,
                        "page_type_confidence": page_confidence,
                        "route_target": route_target,
                        "audit_disposition": "audit_required",
                        "audit_role": "primary",
                        "table_like": table_like,
                        "grid_heavy": False,
                        "structure_summary": {
                            "pair_count": table_mappings + component_mappings + 1,
                            "table_mapping_count": table_mappings,
                            "text_count": 20,
                            "line_count": lines,
                            "block_count": blocks,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (findings / "extraction_census_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "extraction-census-summary-v1",
                "project_id": project_id,
                "file_count": 1,
                "status_counts": {"COMPLETE": 1},
                "scale_status_counts": {
                    "UNRESOLVED": scale_unresolved,
                    "DECLARED": 1 - scale_unresolved if scale_unresolved <= 1 else 0,
                },
                "semantic_unsupported_entity_counts": {},
                "warning_code_counts": {},
            }
        ),
        encoding="utf-8",
    )
    (findings / "scale_evidence_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "scale-evidence-summary-v1",
                "scale_status_counts": {
                    "UNRESOLVED": scale_unresolved,
                    "DECLARED": max(0, 1 - scale_unresolved),
                },
            }
        ),
        encoding="utf-8",
    )
    (findings / "canonical_scene_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "canonical-scene-summary-v1",
                "status_counts": {"COMPLETE": 1},
            }
        ),
        encoding="utf-8",
    )
    (findings / "symbol_inventory_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "symbol-inventory-summary-v1",
                "definition_count": unknown_symbols,
                "registered_definition_count": 0,
                "unknown_definition_count": unknown_symbols,
                "instance_count": unknown_symbols * 2,
            }
        ),
        encoding="utf-8",
    )
    (audit / "failure_queue_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "failure-queue-summary-v1",
                "item_count": 0,
                "failure_count": 0,
                "critical_count": 0,
            }
        ),
        encoding="utf-8",
    )


def test_evaluate_extraction_verification_pass_when_healthy(tmp_path: Path) -> None:
    project = tmp_path / "healthy"
    _write_project(project, unassigned_wires=10, lines=100, unclassified_blocks=5, blocks=50)
    evaluation = evaluate_extraction_verification({"healthy": project})
    assert evaluation["summary"]["status"] == "PASS"
    assert evaluation["project_rows"][0]["health_status"] == "PASS"
    assert evaluation["project_rows"][0]["table_mapping_pairs"] == 3
    assert evaluation["project_rows"][0]["component_mapping_pairs"] == 2
    assert evaluation["page_rows"][0]["sheet_id"] == "S0001"


def test_evaluate_extraction_verification_review_on_high_wire_gap(tmp_path: Path) -> None:
    project = tmp_path / "wires"
    _write_project(project, unassigned_wires=80, lines=100, unknown_symbols=4, scale_unresolved=1)
    evaluation = evaluate_extraction_verification({"wires": project})
    row = evaluation["project_rows"][0]
    assert row["health_status"] == "REVIEW"
    assert "high_unassigned_wire_ratio" in row["review_reasons"]
    assert "unknown_symbol_definitions:4" in row["review_reasons"]
    assert "scale_unresolved_files:1" in row["review_reasons"]


def test_evaluate_extraction_verification_fail_on_incomplete_gate(tmp_path: Path) -> None:
    project = tmp_path / "broken"
    _write_project(project, gate_status="INCOMPLETE", incomplete_pages=2)
    evaluation = evaluate_extraction_verification({"broken": project})
    row = evaluation["project_rows"][0]
    assert row["health_status"] == "FAIL"
    assert "gate_status:INCOMPLETE" in row["fail_reasons"]
    assert "incomplete_pages:2" in row["fail_reasons"]


def test_evaluate_extraction_verification_fail_on_missing_artifacts(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    evaluation = evaluate_extraction_verification({"empty": empty})
    row = evaluation["project_rows"][0]
    assert row["health_status"] == "FAIL"
    assert "missing_artifacts" in row["fail_reasons"]


def test_write_extraction_verification_artifacts(tmp_path: Path) -> None:
    project = tmp_path / "healthy"
    _write_project(project)
    evaluation = evaluate_extraction_verification({"healthy": project})
    out = tmp_path / "scorecard"
    paths = write_extraction_verification_artifacts(evaluation, out)
    assert paths["by_project"].is_file()
    assert paths["by_page"].is_file()
    assert paths["summary"].is_file()
    assert paths["markdown"].is_file()
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["summary"]["project_count"] == 1
    assert "Extraction Verification Scorecard" in paths["markdown"].read_text(encoding="utf-8")


def test_review_layout_only_content_pages(tmp_path: Path) -> None:
    project = tmp_path / "layout"
    _write_project(
        project,
        page_type="装置背板接线图",
        route_target="LayoutOnlyExtractor",
        page_confidence=0.4,
        table_like=True,
        unassigned_wires=0,
        lines=100,
        unclassified_blocks=0,
        blocks=10,
    )
    evaluation = evaluate_extraction_verification({"layout": project})
    row = evaluation["project_rows"][0]
    assert row["health_status"] == "REVIEW"
    assert "layout_only_content_pages:1" in row["review_reasons"]
    assert "table_like_non_routed:1" in row["review_reasons"]
    assert "low_page_type_confidence:1" in row["review_reasons"]
