import json
from copy import deepcopy
from dataclasses import fields
from pathlib import Path

import pandas as pd

from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SidecarInfo
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem
from dwg_audit.domain.models import record_dict
from dwg_audit.extract.primitive_normalizer import PRIMITIVE_ALGORITHM_VERSION
from dwg_audit.extract.primitive_normalizer import PRIMITIVE_SCHEMA_VERSION
from dwg_audit.extract.primitive_normalizer import PrimitiveSegment
from dwg_audit.readers import ReaderRun
from dwg_audit.report.artifacts import load_report_frames
from dwg_audit.report.artifacts import write_audit_outputs
from dwg_audit.report.artifacts import write_project_artifacts
from dwg_audit.report.rerun import rerun_audit_from_findings
from dwg_audit.utils.config import DEFAULT_CONFIG


def test_load_report_frames_reads_only_requested_frames(monkeypatch, tmp_path: Path) -> None:
    findings_dir = tmp_path / "findings"
    audit_dir = tmp_path / "audit"
    findings_dir.mkdir()
    audit_dir.mkdir()
    for path in (
        findings_dir / "pairs.parquet",
        findings_dir / "source_files.parquet",
        audit_dir / "issues.parquet",
    ):
        path.touch()

    reads: list[str] = []

    def fake_read_parquet(path: Path) -> pd.DataFrame:
        reads.append(path.name)
        return pd.DataFrame({"source": [path.stem]})

    monkeypatch.setattr(pd, "read_parquet", fake_read_parquet)

    frames = load_report_frames(tmp_path, names=("pairs", "issues"))

    assert set(frames) == {"pairs", "issues"}
    assert reads == ["pairs.parquet", "issues.parquet"]


def test_production_writer_short_circuits_shadow_artifacts(monkeypatch, tmp_path: Path) -> None:
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Production Project",
            project_name="Production Project",
            created_at="2026-07-19T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=0,
            sheet_count=0,
            valid_dwg_files=0,
            invalid_dwg_files=0,
            source_files=[],
            sidecars=[],
            project_name_sources={},
            warnings=[],
        ),
        pages=[],
        terminal_strips=[],
        project_root="C:/demo",
    )
    config = deepcopy(DEFAULT_CONFIG)
    config["report"]["export_formats"] = ["html"]

    def fail_shadow_work(*_args, **_kwargs):
        raise AssertionError("production writer entered shadow work")

    monkeypatch.setattr(
        "dwg_audit.report.artifacts.build_project_scale_evidence",
        fail_shadow_work,
    )

    stale_findings = tmp_path / "Production_Project" / "findings"
    stale_findings.mkdir(parents=True)
    (stale_findings / "blocks.parquet").write_bytes(b"stale")
    (stale_findings / "old_diagnostic.json").write_text("stale", encoding="utf-8")
    stale_page_findings = stale_findings / "page_findings"
    stale_page_findings.mkdir()
    (stale_page_findings / "old.json").write_text("stale", encoding="utf-8")
    stale_audit = tmp_path / "Production_Project" / "audit"
    stale_audit.mkdir(parents=True)
    (stale_audit / "issues.parquet").write_bytes(b"stale")
    (stale_audit / "issue_root_cause_audit.json").write_text("stale", encoding="utf-8")

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan), tmp_path, config=config)
    findings_dir = project_dir / "findings"

    assert {
        path.name for path in findings_dir.iterdir() if path.is_file()
    } == {
        "findings.json",
        "findings.md",
        "line_groups.parquet",
        "lines.parquet",
        "pages.parquet",
        "pairs.parquet",
        "runtime_profile.json",
        "source_files.parquet",
        "terminal_candidates.parquet",
        "texts.parquet",
    }
    payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))
    assert payload["run_profile"] == "production"
    assert payload["diagnostics_status"] == "not_generated_for_profile"
    assert "wire_networks.parquet" not in payload["artifacts"]["findings"]
    assert "issue_root_cause_audit.json" not in payload["artifacts"]["audit"]
    assert "audit_report.html" in payload["artifacts"]["audit"]
    assert "audit_report.md" not in payload["artifacts"]["audit"]
    assert not (findings_dir / "blocks.parquet").exists()
    assert not (findings_dir / "old_diagnostic.json").exists()
    assert not (findings_dir / "page_findings").exists()
    assert not (project_dir / "audit" / "issues.parquet").exists()
    assert not (project_dir / "audit" / "issue_root_cause_audit.json").exists()

    audit_dir = rerun_audit_from_findings(project_dir, config)
    assert (audit_dir / "issues.parquet").exists()
    assert (audit_dir / "audit_report.html").exists()
    assert not (audit_dir / "audit_report.md").exists()
    assert not (audit_dir / "audit_v2_issue_clusters.parquet").exists()


def test_write_project_artifacts_creates_findings_outputs(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/01.dwg",
        filename="01.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=1,
        detected_page_no="01",
        detected_from="filename",
        sheet_title="封面",
        sheet_category="封面/目录",
        skip_reason="matched skip keyword: 封面",
        valid_dwg_header=True,
        conversion_status="skipped",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[SidecarInfo("prj", None, "missing", None, ["No .prj sidecar found."])],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                "01.dwg",
                1,
                "01",
                "封面",
                "封面/目录",
                "skip",
                "filename",
                False,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )

    reader_run = ReaderRun(
        file_id="F0001",
        backend_name="odafc",
        backend_version="27.1.0",
        backend_build_id=None,
        capabilities={"native_dwg": True},
        discovery_source="config",
        options={"target_version": "R2018", "audit": True},
        status="skipped",
        cache_hit=False,
        cache_identity_enforced=True,
        document_path=None,
        error_code=None,
        detail=source.skip_reason,
    )
    extraction_gate_payload = {
        "analysis_status": "COMPLETE",
        "clean_conclusion_allowed": True,
        "incomplete_page_count": 0,
        "incomplete_sheet_ids": [],
        "failure_code_counts": {},
        "pages": [
            {
                "sheet": "S0001",
                "file": "F0001",
                "filename": "01.dwg",
                "audit_role": "skip",
                "audit_disposition": "skip_stable",
                "status": "NOT_APPLICABLE",
                "failure_codes": [],
                "primitive_counts": {"text": 0, "line": 0, "block": 0, "polyline": 0, "total": 0},
                "warning_codes": [],
                "executed_extractor": None,
            }
        ],
    }

    class GateStub:
        def to_dict(self) -> dict:
            return extraction_gate_payload

    project_dir = write_project_artifacts(
        ProjectArtifacts(scan=scan, reader_runs=[reader_run]),
        tmp_path,
        extraction_gate=GateStub(),
    )
    findings_dir = project_dir / "findings"
    page_findings_dir = findings_dir / "page_findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))
    reader_run_payload = json.loads((project_dir / "reader_run.json").read_text(encoding="utf-8"))
    extraction_gate_written = json.loads(
        (project_dir / "extraction_completeness.json").read_text(encoding="utf-8")
    )

    assert (project_dir / "manifest.json").exists()
    assert reader_run_payload == {
        "schema_version": "reader-run-manifest/v1",
        "project_id": "Demo 项目",
        "runs": [reader_run.to_dict()],
    }
    assert extraction_gate_written == extraction_gate_payload
    assert json.loads((project_dir / "manifest.json").read_text(encoding="utf-8")) == record_dict(scan.manifest)
    assert list(pd.read_parquet(findings_dir / "source_files.parquet").columns) == [
        field.name for field in fields(SourceFileRecord)
    ]
    assert "reader_run" not in findings_payload
    assert "reader_runs" not in findings_payload
    assert (findings_dir / "findings.md").exists()
    assert (findings_dir / "findings.json").exists()
    assert (findings_dir / "polylines.parquet").exists()
    assert (findings_dir / "primitive_segments.parquet").exists()
    extraction_census = json.loads(
        (findings_dir / "extraction_census.json").read_text(encoding="utf-8")
    )
    assert extraction_census == {
        "schema_version": "extraction-census-project-v1",
        "project_id": "Demo 项目",
        "file_count": 0,
        "files": [],
    }
    extraction_census_summary = json.loads(
        (findings_dir / "extraction_census_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert extraction_census_summary["file_count"] == 0
    assert extraction_census_summary["status_counts"] == {}
    assert extraction_census_summary["error_code_counts"] == {}
    scale_summary = json.loads(
        (findings_dir / "scale_evidence_summary.json").read_text(encoding="utf-8")
    )
    assert scale_summary["file_count"] == 0
    assert scale_summary["applied_to_geometry_count"] == 0
    assert scale_summary["geometry_mutation_forbidden"] is True
    assert scale_summary["canonical_millimetre_ready"] is False
    shadow_gap_summary = json.loads(
        (findings_dir / "shadow_gap_triage_summary.json").read_text(encoding="utf-8")
    )
    assert shadow_gap_summary["total_shadow_unsupported_entities"] == 0
    assert shadow_gap_summary["any_adapter_authorized"] is False
    canonical_scene_summary = json.loads(
        (findings_dir / "canonical_scene_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert canonical_scene_summary["scene_count"] == 0
    assert canonical_scene_summary["shadow_contract_valid"] is True
    assert (findings_dir / "canonical_scene").is_dir()
    assert pd.read_parquet(findings_dir / "canonical_scene_records.parquet").empty
    assert pd.read_parquet(findings_dir / "canonical_scene_views.parquet").empty
    assert pd.read_parquet(
        findings_dir / "canonical_scene_diagnostics.parquet"
    ).empty
    assert pd.read_parquet(findings_dir / "primitive_segments.parquet").empty
    assert json.loads(
        (findings_dir / "primitive_segments_summary.json").read_text(encoding="utf-8")
    ) == {
        "schema_version": "primitive-summary-v1",
        "primitive_schema_version": "primitive-segment-v1",
        "total": 0,
        "kind_counts": {},
        "status_counts": {},
        "unsupported_kind_counts": {},
    }
    symbol_summary = json.loads(
        (findings_dir / "symbol_inventory_summary.json").read_text(encoding="utf-8")
    )
    assert symbol_summary["definition_count"] == 0
    assert symbol_summary["unknown_critical_issue_eligible_count"] == 0
    assert (findings_dir / "symbol_definitions_v1.parquet").exists()
    assert (findings_dir / "symbol_instances_v1.parquet").exists()
    assert (findings_dir / "unknown_symbol_queue_v1.parquet").exists()
    symbol_dependency_library = json.loads(
        (findings_dir / "symbol_dependency_library.json").read_text(
            encoding="utf-8"
        )
    )
    assert symbol_dependency_library["source_status"] == "not_configured"
    assert symbol_dependency_library["summary"]["symbol_count"] == 0
    symbol_dependency_validation = json.loads(
        (findings_dir / "symbol_dependency_validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert symbol_dependency_validation["valid"] is True
    assert symbol_dependency_validation["load_issues"] == []
    assert (findings_dir / "symbol_dependency_issues.parquet").exists()
    assert pd.read_parquet(findings_dir / "symbol_dependency_issues.parquet").empty
    symbol_dependency_summary = json.loads(
        (findings_dir / "symbol_dependency_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert symbol_dependency_summary["library_valid"] is True
    port_shadow_summary = json.loads(
        (findings_dir / "symbol_port_shadow_summary.json").read_text(encoding="utf-8")
    )
    assert port_shadow_summary["placement_count"] == 0
    assert port_shadow_summary["electrical_union_eligible_count"] == 0
    assert port_shadow_summary["critical_issue_eligible_count"] == 0
    port_shadow_placements = json.loads(
        (findings_dir / "symbol_port_shadow_placements.json").read_text(encoding="utf-8")
    )
    assert port_shadow_placements["placements"] == []
    assert (findings_dir / "extraction_warnings.parquet").exists()
    assert (findings_dir / "wire_junctions.parquet").exists()
    assert (findings_dir / "wire_networks.parquet").exists()
    assert (findings_dir / "geometry_shadow_nodes.parquet").exists()
    assert (findings_dir / "geometry_shadow_edges.parquet").exists()
    assert (findings_dir / "geometry_shadow_components.parquet").exists()
    assert (findings_dir / "geometry_shadow_observations.parquet").exists()
    assert (findings_dir / "junction_observations_v2.parquet").exists()
    assert (findings_dir / "topology_decisions.parquet").exists()
    topology_decision_summary = json.loads(
        (findings_dir / "topology_decision_summary.json").read_text(encoding="utf-8")
    )
    assert topology_decision_summary["decision_count"] == 0
    assert topology_decision_summary["non_asserted_union_violation_count"] == 0
    electrical_summary = json.loads(
        (findings_dir / "electrical_network_summary.json").read_text(encoding="utf-8")
    )
    assert electrical_summary["network_count"] == 0
    assert electrical_summary["non_asserted_union_application_count"] == 0
    assert (findings_dir / "electrical_networks_v2.parquet").exists()
    assert (findings_dir / "network_members_v2.parquet").exists()
    assert (findings_dir / "network_open_endpoints_v2.parquet").exists()
    assert (findings_dir / "possible_boundaries_v2.parquet").exists()
    assert (findings_dir / "topology_decision_applications.parquet").exists()
    assert (findings_dir / "network_endpoint_witnesses_v2.parquet").exists()
    witness_summary = json.loads(
        (findings_dir / "network_witness_summary.json").read_text(encoding="utf-8")
    )
    assert witness_summary["witness_count"] == 0
    assert witness_summary["witness_completeness"] == 1.0
    validation_summary = json.loads(
        (findings_dir / "network_validation_summary.json").read_text(encoding="utf-8")
    )
    assert validation_summary["suspicion_count"] == 0
    assert (findings_dir / "network_validation_suspicions_v2.parquet").exists()
    assert (findings_dir / "network_boundaries_v2.parquet").exists()
    assert (findings_dir / "legacy_pair_network_equivalence.parquet").exists()
    assert json.loads(
        (findings_dir / "legacy_pair_network_equivalence_summary.json").read_text(
            encoding="utf-8"
        )
    )["legacy_result_change_count"] == 0
    assert (findings_dir / "geometry_shadow_observation_summary.json").exists()
    assert (findings_dir / "pair_geometry_shadow.parquet").exists()
    assert (findings_dir / "pair_geometry_shadow_summary.json").exists()
    assert not page_findings_dir.exists()
    assert findings_payload["page_findings_count"] == 1
    assert len(findings_payload["page_findings"]) == 1
    assert findings_payload["page_findings"][0]["sheet_id"] == "S0001"
    assert findings_payload["page_findings"][0]["file_id"] == "F0001"
    assert findings_payload["page_findings"][0]["audit_role"] == "skip"
    assert findings_payload["page_findings"][0]["audit_disposition"] == "skip_stable"
    assert findings_payload["page_findings"][0]["filename"] == "01.dwg"
    assert findings_payload["page_findings"][0]["route_target"] == "SkipExtractor"
    assert findings_payload["analysis_status"] == "COMPLETE"
    assert findings_payload["clean_conclusion_allowed"] is True
    assert findings_payload["incomplete_page_count"] == 0
    assert findings_payload["failure_code_counts"] == {}
    assert findings_payload["page_findings"][0]["extraction_status"] == "NOT_APPLICABLE"
    assert findings_payload["page_findings"][0]["failure_codes"] == []
    assert findings_payload["page_findings"][0]["structure_summary"]["pair_count"] == 0
    assert findings_payload["audit_disposition_counts"] == {"skip_stable": 1}
    assert "page_findings/" not in findings_payload["artifacts"]["findings"]
    assert "wire_junctions.parquet" in findings_payload["artifacts"]["findings"]
    assert "primitive_segments.parquet" in findings_payload["artifacts"]["findings"]
    assert "primitive_segments_summary.json" in findings_payload["artifacts"]["findings"]
    assert "extraction_census.json" in findings_payload["artifacts"]["findings"]
    assert "extraction_census_summary.json" in findings_payload["artifacts"]["findings"]
    assert "scale_evidence.json" in findings_payload["artifacts"]["findings"]
    assert "scale_evidence_summary.json" in findings_payload["artifacts"]["findings"]
    assert "transform_fidelity.json" in findings_payload["artifacts"]["findings"]
    assert "shadow_gap_triage.json" in findings_payload["artifacts"]["findings"]
    assert "shadow_gap_triage_summary.json" in findings_payload["artifacts"]["findings"]
    assert "canonical_scene/" in findings_payload["artifacts"]["findings"]
    assert "canonical_scene_records.parquet" in findings_payload["artifacts"]["findings"]
    assert "canonical_scene_views.parquet" in findings_payload["artifacts"]["findings"]
    assert "canonical_scene_diagnostics.parquet" in findings_payload["artifacts"]["findings"]
    assert "canonical_scene_unresolved_sources.parquet" in findings_payload["artifacts"]["findings"]
    assert "canonical_scene_summary.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_definitions_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "symbol_instances_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "unknown_symbol_queue_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "symbol_inventory_summary.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_dependency_library.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_dependency_validation.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_dependency_issues.parquet" in findings_payload["artifacts"]["findings"]
    assert "symbol_dependency_summary.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_review_backlog.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_review_validation.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_review_summary.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_port_shadow_placements.json" in findings_payload["artifacts"]["findings"]
    assert "symbol_port_shadow_summary.json" in findings_payload["artifacts"]["findings"]
    assert "wire_networks.parquet" in findings_payload["artifacts"]["findings"]

    assert "geometry_shadow_nodes.parquet" in findings_payload["artifacts"]["findings"]
    assert "geometry_shadow_edges.parquet" in findings_payload["artifacts"]["findings"]
    assert "geometry_shadow_components.parquet" in findings_payload["artifacts"]["findings"]
    assert "geometry_shadow_observations.parquet" in findings_payload["artifacts"]["findings"]
    assert "junction_observations_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "topology_decisions.parquet" in findings_payload["artifacts"]["findings"]
    assert "topology_decision_summary.json" in findings_payload["artifacts"]["findings"]
    assert "electrical_networks_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "network_members_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "network_open_endpoints_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "possible_boundaries_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "topology_decision_applications.parquet" in findings_payload["artifacts"]["findings"]
    assert "electrical_network_summary.json" in findings_payload["artifacts"]["findings"]
    assert "network_endpoint_witnesses_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "network_witness_summary.json" in findings_payload["artifacts"]["findings"]
    assert "network_validation_suspicions_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "network_validation_summary.json" in findings_payload["artifacts"]["findings"]
    assert "network_boundaries_v2.parquet" in findings_payload["artifacts"]["findings"]
    assert "network_boundary_summary.json" in findings_payload["artifacts"]["findings"]
    assert "legacy_pair_network_equivalence.parquet" in findings_payload["artifacts"]["findings"]
    assert "legacy_pair_network_equivalence_summary.json" in findings_payload["artifacts"]["findings"]
    assert "geometry_shadow_observation_summary.json" in findings_payload["artifacts"]["findings"]
    assert "pair_geometry_shadow.parquet" in findings_payload["artifacts"]["findings"]
    assert "pair_geometry_shadow_summary.json" in findings_payload["artifacts"]["findings"]
    assert "project_profile.json" in findings_payload["artifacts"]["findings"]
    assert "text_tokens.parquet" in findings_payload["artifacts"]["findings"]
    assert "semantic_attachment_candidates.parquet" in findings_payload["artifacts"]["findings"]
    assert "semantic_attachment_summary.json" in findings_payload["artifacts"]["findings"]
    assert "scope_decisions.parquet" in findings_payload["artifacts"]["findings"]
    assert "scope_resolution_summary.json" in findings_payload["artifacts"]["findings"]
    assert "constraint_decisions.parquet" in findings_payload["artifacts"]["findings"]
    assert "constraint_resolution_summary.json" in findings_payload["artifacts"]["findings"]
    assert (findings_dir / "project_profile.json").exists()
    assert (findings_dir / "text_tokens.parquet").exists()
    assert (findings_dir / "semantic_attachment_candidates.parquet").exists()
    assert (findings_dir / "semantic_attachment_summary.json").exists()
    assert (findings_dir / "scope_decisions.parquet").exists()
    assert (findings_dir / "scope_resolution_summary.json").exists()
    assert (findings_dir / "constraint_decisions.parquet").exists()
    assert (findings_dir / "constraint_resolution_summary.json").exists()
    assert (findings_dir / "electrical_semantic_nodes.parquet").exists()
    assert (findings_dir / "electrical_semantic_relations.parquet").exists()
    assert (findings_dir / "electrical_semantic_evidence.parquet").exists()
    assert (findings_dir / "electrical_semantic_constraints.parquet").exists()
    electrical_semantic_summary = json.loads(
        (findings_dir / "electrical_semantic_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert electrical_semantic_summary["shadow_only"] is True
    assert electrical_semantic_summary["valid"] is True
    assert electrical_semantic_summary["electrical_union_eligible_count"] == 0
    assert findings_payload["project_profile_summary"]["page_count"] == 1
    assert findings_payload["project_profile_summary"]["strip_count"] == 0
    assert findings_payload["semantic_attachment_summary"]["total_count"] == 0
    assert "decision_count" in findings_payload["scope_resolution_summary"]
    assert "decision_count" in findings_payload["constraint_resolution_summary"]
    assert findings_payload["constraint_resolution_summary"]["inviolable_strong_constraints"] is True
    assert (findings_dir / "endpoint_identities_v1.parquet").exists()
    assert (findings_dir / "cross_page_endpoint_candidates_v1.parquet").exists()
    assert (findings_dir / "project_graph_summary.json").exists()
    assert (findings_dir / "engine_comparison_v1.json").exists()
    assert "endpoint_identities_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "cross_page_endpoint_candidates_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "project_graph_summary.json" in findings_payload["artifacts"]["findings"]
    assert "engine_comparison_v1.json" in findings_payload["artifacts"]["findings"]
    assert findings_payload["project_graph_summary"]["node_counts"]["endpoint_identities"] == 0
    assert findings_payload["engine_comparison"]["pair_count"] == 0
    assert pd.read_parquet(findings_dir / "endpoint_identities_v1.parquet").empty
    assert pd.read_parquet(findings_dir / "cross_page_endpoint_candidates_v1.parquet").empty
    assert "audit_v2_issue_clusters.parquet" in findings_payload["artifacts"]["audit"]
    assert "failure_queue.parquet" in findings_payload["artifacts"]["audit"]


def test_write_project_artifacts_persists_phase119_shadow_semantic_artifacts(
    tmp_path: Path,
) -> None:
    """One numeric text near a line endpoint yields tokens + attachment shadow files."""
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/04.dwg",
        filename="04.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=4,
        detected_page_no="04",
        detected_from="filename",
        sheet_title="交流回路图1",
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-11T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[
                SidecarInfo("prj", "C:/demo/demo.prj", "parsed", "gbk", []),
                SidecarInfo(
                    "terminal_xml",
                    "C:/demo/LdDzbInfo.xml",
                    "parsed",
                    "utf-8",
                    [],
                ),
            ],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                "04.dwg",
                4,
                "04",
                "交流回路图1",
                "二次原理图",
                "primary",
                "filename",
                True,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    texts = [
        TextItem(
            text_id="T1",
            sheet_id="S0001",
            file_id="F0001",
            handle="H1",
            entity_type="TEXT",
            text="101",
            normalized_text="101",
            is_numeric_candidate=True,
            layer="0",
            rotation_deg=0.0,
            height=2.5,
            insert_x=10.0,
            insert_y=20.0,
            bbox_min_x=9.0,
            bbox_min_y=19.0,
            bbox_max_x=12.0,
            bbox_max_y=22.0,
        )
    ]
    lines = [
        LineEntity(
            line_id="L1",
            sheet_id="S0001",
            file_id="F0001",
            handle="H2",
            source_entity_type="LINE",
            layer="0",
            start_x=10.0,
            start_y=20.0,
            end_x=50.0,
            end_y=20.0,
            length=40.0,
            angle_deg=0.0,
            bbox_min_x=10.0,
            bbox_min_y=20.0,
            bbox_max_x=50.0,
            bbox_max_y=20.0,
        )
    ]

    project_dir = write_project_artifacts(
        ProjectArtifacts(scan=scan, texts=texts, lines=lines),
        tmp_path,
    )
    findings_dir = project_dir / "findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))
    project_profile = json.loads((findings_dir / "project_profile.json").read_text(encoding="utf-8"))
    tokens = pd.read_parquet(findings_dir / "text_tokens.parquet")
    attachments = pd.read_parquet(findings_dir / "semantic_attachment_candidates.parquet")
    attachment_summary = json.loads(
        (findings_dir / "semantic_attachment_summary.json").read_text(encoding="utf-8")
    )

    assert (findings_dir / "project_profile.json").exists()
    assert (findings_dir / "text_tokens.parquet").exists()
    assert (findings_dir / "semantic_attachment_candidates.parquet").exists()
    assert (findings_dir / "semantic_attachment_summary.json").exists()
    assert (findings_dir / "scope_decisions.parquet").exists()
    assert (findings_dir / "scope_resolution_summary.json").exists()
    assert (findings_dir / "constraint_decisions.parquet").exists()
    assert (findings_dir / "constraint_resolution_summary.json").exists()
    assert "project_profile.json" in findings_payload["artifacts"]["findings"]
    assert "text_tokens.parquet" in findings_payload["artifacts"]["findings"]
    assert "semantic_attachment_candidates.parquet" in findings_payload["artifacts"]["findings"]
    assert "semantic_attachment_summary.json" in findings_payload["artifacts"]["findings"]
    assert "scope_decisions.parquet" in findings_payload["artifacts"]["findings"]
    assert "scope_resolution_summary.json" in findings_payload["artifacts"]["findings"]
    assert "constraint_decisions.parquet" in findings_payload["artifacts"]["findings"]
    assert "constraint_resolution_summary.json" in findings_payload["artifacts"]["findings"]
    assert "electrical_semantic_nodes.parquet" in findings_payload["artifacts"]["findings"]
    assert "electrical_semantic_relations.parquet" in findings_payload["artifacts"]["findings"]
    assert "electrical_semantic_evidence.parquet" in findings_payload["artifacts"]["findings"]
    assert "electrical_semantic_constraints.parquet" in findings_payload["artifacts"]["findings"]
    assert "electrical_semantic_summary.json" in findings_payload["artifacts"]["findings"]

    assert project_profile["schema_version"] == "project-profile-v1"
    assert project_profile["project_id"] == "Demo 项目"
    assert findings_payload["project_profile_summary"]["page_count"] == 1
    assert findings_payload["project_profile_summary"]["strip_count"] == 0
    assert findings_payload["project_profile_summary"]["sidecar_status"]["prj"] == "parsed"

    assert not tokens.empty
    assert tokens.iloc[0]["token_kind"] == "TERMINAL_LOCAL"
    assert tokens.iloc[0]["local_number"] == "101"
    assert tokens.iloc[0]["token_id"] == "TK1-T1"

    assert not attachments.empty
    selected = attachments[attachments["selected"] == True]  # noqa: E712
    assert len(selected) >= 1
    assert selected.iloc[0]["target_line_id"] == "L1"
    assert selected.iloc[0]["token_kind"] == "TERMINAL_LOCAL"
    assert attachment_summary["selected_count"] >= 1
    assert attachment_summary["total_count"] >= 1
    assert findings_payload["semantic_attachment_summary"]["selected_count"] >= 1
    assert findings_payload["semantic_attachment_summary"]["total_count"] >= 1
    assert "decision_count" in findings_payload["scope_resolution_summary"]
    assert "decision_count" in findings_payload["constraint_resolution_summary"]
    assert "algorithm_version" in findings_payload["constraint_resolution_summary"]
    assert findings_payload["constraint_resolution_summary"]["inviolable_strong_constraints"] is True
    constraint_summary = json.loads(
        (findings_dir / "constraint_resolution_summary.json").read_text(encoding="utf-8")
    )
    assert constraint_summary["algorithm_version"] == "constraint-resolver-v1"


def test_write_project_artifacts_builds_symbol_inventory_from_insert_primitives(
    tmp_path: Path,
) -> None:
    """Non-empty INSERT + local LINE child yields one unknown definition and two instances."""
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/04.dwg",
        filename="04.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=4,
        detected_page_no="04",
        detected_from="filename",
        sheet_title="交流回路图1",
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                "04.dwg",
                4,
                "04",
                "交流回路图1",
                "二次原理图",
                "primary",
                "filename",
                True,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    local_line_geometry = '{"end":[1,0,0],"start":[0,0,0]}'
    primitive_segments = [
        PrimitiveSegment(
            primitive_id="PS00000001",
            schema_version=PRIMITIVE_SCHEMA_VERSION,
            algorithm_version=PRIMITIVE_ALGORITHM_VERSION,
            sheet_id="S0001",
            file_id="F0001",
            layout_name="Model",
            entity_handle="I1",
            parent_handle=None,
            source_entity_type="INSERT",
            primitive_kind="INSERT",
            definition_name="DEVICE",
            nested_path="DEVICE[I1]",
            layer="0",
            layer_role_candidate="UNKNOWN",
            layer_role_reason_code="LAYER_ROLE_UNCLASSIFIED",
            linetype="BYLAYER",
            segment_index=0,
            local_geometry_json='{"insert":[0,0,0]}',
            world_geometry_json='{"insert":[0,0,0]}',
            transform_json='{"translation":[0,0,0]}',
            bbox_min_x=0.0,
            bbox_min_y=0.0,
            bbox_max_x=1.0,
            bbox_max_y=1.0,
            reader_backend="odafc",
            reader_version="27.1.0",
            source_status="normalized",
        ),
        PrimitiveSegment(
            primitive_id="PS00000002",
            schema_version=PRIMITIVE_SCHEMA_VERSION,
            algorithm_version=PRIMITIVE_ALGORITHM_VERSION,
            sheet_id="S0001",
            file_id="F0001",
            layout_name="Model",
            entity_handle="I2",
            parent_handle=None,
            source_entity_type="INSERT",
            primitive_kind="INSERT",
            definition_name="DEVICE",
            nested_path="DEVICE[I2]",
            layer="0",
            layer_role_candidate="UNKNOWN",
            layer_role_reason_code="LAYER_ROLE_UNCLASSIFIED",
            linetype="BYLAYER",
            segment_index=0,
            local_geometry_json='{"insert":[100,50,0]}',
            world_geometry_json='{"insert":[100,50,0]}',
            transform_json='{"translation":[100,50,0]}',
            bbox_min_x=100.0,
            bbox_min_y=50.0,
            bbox_max_x=101.0,
            bbox_max_y=51.0,
            reader_backend="odafc",
            reader_version="27.1.0",
            source_status="normalized",
        ),
        PrimitiveSegment(
            primitive_id="PS00000003",
            schema_version=PRIMITIVE_SCHEMA_VERSION,
            algorithm_version=PRIMITIVE_ALGORITHM_VERSION,
            sheet_id="S0001",
            file_id="F0001",
            layout_name="Model",
            entity_handle="L1",
            parent_handle="I1",
            source_entity_type="LINE",
            primitive_kind="LINE",
            definition_name="DEVICE",
            nested_path="DEVICE[I1]",
            layer="PORT",
            layer_role_candidate="UNKNOWN",
            layer_role_reason_code="LAYER_ROLE_UNCLASSIFIED",
            linetype="BYLAYER",
            segment_index=0,
            local_geometry_json=local_line_geometry,
            world_geometry_json=local_line_geometry,
            transform_json="{}",
            bbox_min_x=0.0,
            bbox_min_y=0.0,
            bbox_max_x=1.0,
            bbox_max_y=0.0,
            reader_backend="odafc",
            reader_version="27.1.0",
            source_status="normalized",
        ),
    ]

    project_dir = write_project_artifacts(
        ProjectArtifacts(scan=scan, primitive_segments=primitive_segments),
        tmp_path,
    )
    findings_dir = project_dir / "findings"
    symbol_summary = json.loads(
        (findings_dir / "symbol_inventory_summary.json").read_text(encoding="utf-8")
    )
    definitions = pd.read_parquet(findings_dir / "symbol_definitions_v1.parquet")
    instances = pd.read_parquet(findings_dir / "symbol_instances_v1.parquet")
    unknown_queue = pd.read_parquet(findings_dir / "unknown_symbol_queue_v1.parquet")
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    assert symbol_summary["definition_count"] == 1
    assert symbol_summary["instance_count"] == 2
    assert symbol_summary["unknown_definition_count"] == 1
    assert symbol_summary["unknown_critical_issue_eligible_count"] == 0

    assert not definitions.empty
    assert len(definitions) == 1
    assert definitions.iloc[0]["definition_name"] == "DEVICE"
    assert definitions.iloc[0]["instance_count"] == 2
    assert definitions.iloc[0]["registry_status"] == "UNKNOWN"
    assert bool(definitions.iloc[0]["critical_issue_eligible"]) is False
    assert "definition_fingerprint" in definitions.columns
    assert "registry_status" in definitions.columns
    assert "critical_issue_eligible" in definitions.columns
    assert str(definitions.iloc[0]["definition_fingerprint"])

    assert not instances.empty
    assert len(instances) == 2
    assert set(instances["entity_handle"]) == {"I1", "I2"}
    assert set(instances["definition_name"]) == {"DEVICE"}
    assert "definition_fingerprint" in instances.columns
    assert "registry_status" in instances.columns
    assert (
        instances.iloc[0]["definition_fingerprint"]
        == definitions.iloc[0]["definition_fingerprint"]
    )

    assert not unknown_queue.empty
    assert len(unknown_queue) == 1
    assert unknown_queue.iloc[0]["definition_name"] == "DEVICE"
    assert bool(unknown_queue.iloc[0]["critical_issue_eligible"]) is False
    assert "definition_fingerprint" in unknown_queue.columns
    assert "critical_issue_eligible" in unknown_queue.columns

    assert "symbol_definitions_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "symbol_instances_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "unknown_symbol_queue_v1.parquet" in findings_payload["artifacts"]["findings"]
    assert "symbol_inventory_summary.json" in findings_payload["artifacts"]["findings"]


def test_write_project_artifacts_can_persist_page_findings_when_enabled(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/01.dwg",
        filename="01.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=1,
        detected_page_no="01",
        detected_from="filename",
        sheet_title="封面",
        sheet_category="封面/目录",
        skip_reason="matched skip keyword: 封面",
        valid_dwg_header=True,
        conversion_status="skipped",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[SidecarInfo("prj", None, "missing", None, ["No .prj sidecar found."])],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                "01.dwg",
                1,
                "01",
                "封面",
                "封面/目录",
                "skip",
                "filename",
                False,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )

    project_dir = write_project_artifacts(
        ProjectArtifacts(scan=scan),
        tmp_path,
        config={"runtime": {"persist_page_findings_files": True}},
    )
    assert not (project_dir / "reader_run.json").exists()
    findings_dir = project_dir / "findings"
    page_findings_dir = findings_dir / "page_findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))
    page_finding_payload = json.loads((page_findings_dir / "S0001.json").read_text(encoding="utf-8"))
    page_finding_text = (page_findings_dir / "S0001.md").read_text(encoding="utf-8")

    assert page_findings_dir.exists()
    assert (page_findings_dir / "S0001.json").exists()
    assert (page_findings_dir / "S0001.md").exists()
    assert "page_findings/" in findings_payload["artifacts"]["findings"]
    assert page_finding_payload["sheet_id"] == "S0001"
    assert page_finding_payload["file_id"] == "F0001"
    assert page_finding_payload["filename"] == "01.dwg"
    assert page_finding_payload["audit_role"] == "skip"
    assert page_finding_payload["audit_disposition"] == "skip_stable"
    assert page_finding_payload["route_target"] == "SkipExtractor"
    assert page_finding_payload["structure_summary"]["pair_count"] == 0
    assert "# Page Findings `S0001`" in page_finding_text
    assert "- AuditDisposition: `skip_stable`" in page_finding_text
    assert "- RouteTarget: `SkipExtractor`" in page_finding_text


def test_write_project_artifacts_persists_page_classification_fields_to_pages_parquet(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/04.dwg",
        filename="04.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=4,
        detected_page_no="04",
        detected_from="filename",
        sheet_title="交流回路图1",
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-06T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord("S0001", "F0001", "04.dwg", 4, "04", "交流回路图1", "二次原理图", "primary", "filename", True)
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )

    scan.pages[0].page_type = "二次原理图"
    scan.pages[0].page_subtype = "grid_heavy_wire_diagram"
    scan.pages[0].page_type_confidence = 0.88
    scan.pages[0].table_like = False
    scan.pages[0].grid_heavy = True
    scan.pages[0].route_target = "WireDiagramExtractor"
    scan.pages[0].audit_disposition = "audit_required"

    project_dir = write_project_artifacts(
        ProjectArtifacts(scan=scan),
        tmp_path,
        page_classifications={
            "S0001": PageClassification(
                sheet_id="S0001",
                page_type="二次原理图",
                page_subtype="grid_heavy_wire_diagram",
                page_type_confidence=0.88,
                table_like=False,
                grid_heavy=True,
                route_target="WireDiagramExtractor",
                features={"grid_band_count": 10, "horizontal_line_ratio": 0.82, "polyline_count": 3},
                audit_disposition="audit_required",
            )
        },
    )

    pages = pd.read_parquet(project_dir / "findings" / "pages.parquet")
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))

    page = pages.iloc[0]
    assert page["page_type"] == "二次原理图"
    assert page["page_subtype"] == "grid_heavy_wire_diagram"
    assert page["page_type_confidence"] == 0.88
    assert bool(page["grid_heavy"]) is True
    assert bool(page["table_like"]) is False
    assert page["route_target"] == "WireDiagramExtractor"
    assert page["audit_disposition"] == "audit_required"
    assert "PageClassifier labeled this page as `二次原理图` / `grid_heavy_wire_diagram`" in findings_payload["page_findings"][0]["recognition_strategy"]


def test_write_project_artifacts_marks_no_table_pages_detected_in_summary(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/04.dwg",
        filename="04.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=4,
        detected_page_no="04",
        detected_from="filename",
        sheet_title="交流回路图1",
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-06T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord("S0001", "F0001", "04.dwg", 4, "04", "交流回路图1", "二次原理图", "primary", "filename", True)
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )

    scan.pages[0].page_type = "二次原理图"
    scan.pages[0].page_subtype = "grid_heavy_wire_diagram"
    scan.pages[0].page_type_confidence = 0.88
    scan.pages[0].table_like = False
    scan.pages[0].grid_heavy = True
    scan.pages[0].route_target = "WireDiagramExtractor"
    scan.pages[0].audit_disposition = "audit_required"

    project_dir = write_project_artifacts(
        ProjectArtifacts(scan=scan),
        tmp_path,
        page_classifications={
            "S0001": PageClassification(
                sheet_id="S0001",
                page_type="二次原理图",
                page_subtype="grid_heavy_wire_diagram",
                page_type_confidence=0.88,
                table_like=False,
                grid_heavy=True,
                route_target="WireDiagramExtractor",
                features={"grid_band_count": 10},
                audit_disposition="audit_required",
            )
        },
    )

    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
    findings_text = (project_dir / "findings" / "findings.md").read_text(encoding="utf-8")

    summary = findings_payload["table_extraction_summary"]
    assert summary["status"] == "no_table_pages_detected"
    assert summary["classified_table_pages"] == 0
    assert summary["classified_table_filenames"] == []
    assert "## Table Extraction" in findings_text
    assert "Status: `no_table_pages_detected`" in findings_text


def test_write_project_artifacts_summarizes_terminal_candidate_channels(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/21.dwg",
        filename="21.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=21,
        detected_page_no="21",
        detected_from="filename",
        sheet_title="左侧端子图1",
        sheet_category="屏端子图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-06T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord("S0001", "F0001", "21.dwg", 21, "21", "左侧端子图1", "屏端子图", "supplemental", "filename", True)
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    candidates = [
        TerminalCandidate(
            "C0001",
            "G1",
            "S0001",
            "F0001",
            "left",
            "T1",
            "108",
            "108",
            0.9,
            "accepted",
            None,
            100.0,
            200.0,
            2.0,
            1.0,
            channel="terminal_numeric_channel",
        ),
        TerminalCandidate(
            "C0002",
            "G1",
            "S0001",
            "F0001",
            "right",
            "T2",
            "KLP",
            None,
            0.0,
            "rejected",
            "not_numeric",
            120.0,
            200.0,
            3.0,
            1.0,
            channel="semantic_channel",
            channel_detail="terminal_semantic_marker",
        ),
        TerminalCandidate(
            "C0003",
            "G1",
            "S0001",
            "F0001",
            "right",
            "T3",
            "1",
            None,
            0.0,
            "rejected",
            "block_internal_pin_number",
            130.0,
            200.0,
            4.0,
            1.0,
            channel="noise_channel",
            channel_detail="block_internal_pin_number",
        ),
    ]

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan, terminal_candidates=candidates), tmp_path)
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))

    channel_counts = findings_payload["page_findings"][0]["structure_summary"]["terminal_candidate_channel_counts"]
    assert findings_payload["page_findings"][0]["audit_disposition"] == "audit_required"
    assert channel_counts == {
        "noise_channel": 1,
        "semantic_channel": 1,
        "terminal_numeric_channel": 1,
    }


def test_write_project_artifacts_includes_continuation_candidate_channel_counts(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/26.dwg",
        filename="26.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=26,
        detected_page_no="26",
        detected_from="filename",
        sheet_title="右侧端子图1",
        sheet_category="屏端子图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-06T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord("S0001", "F0001", "26.dwg", 26, "26", "右侧端子图1", "屏端子图", "supplemental", "filename", True)
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    candidates = [
        TerminalCandidate(
            "C0001",
            "G1",
            "S0001",
            "F0001",
            "left",
            "T1",
            "3-2n420",
            "420",
            0.9,
            "accepted",
            None,
            325.0,
            145.0,
            2.0,
            1.0,
            channel="continuation_channel",
            channel_detail="terminal_same_value_bridge",
        ),
        TerminalCandidate(
            "C0002",
            "G1",
            "S0001",
            "F0001",
            "right",
            "T2",
            "1-2n420",
            "420",
            0.88,
            "accepted",
            None,
            400.0,
            145.0,
            2.0,
            1.0,
            channel="continuation_channel",
            channel_detail="terminal_same_value_bridge",
        ),
        TerminalCandidate(
            "C0003",
            "G1",
            "S0001",
            "F0001",
            "left",
            "T3",
            "KLP",
            None,
            0.0,
            "rejected",
            "not_numeric",
            350.0,
            145.0,
            2.0,
            1.0,
            channel="semantic_channel",
            channel_detail="terminal_semantic_marker",
        ),
    ]

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan, terminal_candidates=candidates), tmp_path)
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))

    channel_counts = findings_payload["page_findings"][0]["structure_summary"]["terminal_candidate_channel_counts"]
    assert channel_counts == {
        "continuation_channel": 2,
        "semantic_channel": 1,
    }


def test_write_project_artifacts_summarizes_continuation_pair_kinds(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/26.dwg",
        filename="26.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=26,
        detected_page_no="26",
        detected_from="filename",
        sheet_title="右侧端子图1",
        sheet_category="屏端子图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-06T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord("S0001", "F0001", "26.dwg", 26, "26", "右侧端子图1", "屏端子图", "supplemental", "filename", True)
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id="PC1",
            left_value="420",
            right_value="420",
            confidence=0.88,
            status="review",
            rationale="continuation relation",
            alternative_pair_candidate_ids=[],
            confidence_bucket="review",
            evidence={
                "filename": "26.dwg",
                "sheet_no": "26",
                "sheet_order": 26,
                "line_group_id": "G0001",
                "pair_kind": "continuation",
                "continuation_kind": "terminal_same_value_bridge",
                "line_orientation": "horizontal",
            },
            pair_kind="continuation",
        )
    ]

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan, pairs=pairs), tmp_path)
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))

    assert findings_payload["pair_evidence_summary"]["pair_kind_counts"] == {"continuation": 1}
    assert findings_payload["page_findings"][0]["audit_disposition"] == "audit_required"
    assert findings_payload["page_findings"][0]["structure_summary"]["pair_kind_counts"] == {"continuation": 1}


def test_write_project_artifacts_records_one_to_many_review_table(tmp_path: Path) -> None:
    sources = [
        SourceFileRecord(
            file_id="F0001",
            path="C:/demo/04.dwg",
            filename="04.dwg",
            ext=".dwg",
            sha256="abc",
            size_bytes=10,
            sheet_order=4,
            detected_page_no="04",
            detected_from="filename",
            sheet_title="交流回路图1",
            sheet_category="二次原理图",
            skip_reason=None,
            valid_dwg_header=True,
            conversion_status="converted",
        ),
        SourceFileRecord(
            file_id="F0002",
            path="C:/demo/05.dwg",
            filename="05.dwg",
            ext=".dwg",
            sha256="def",
            size_bytes=10,
            sheet_order=5,
            detected_page_no="05",
            detected_from="filename",
            sheet_title="交流回路图2",
            sheet_category="二次原理图",
            skip_reason=None,
            valid_dwg_header=True,
            conversion_status="converted",
        ),
    ]
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=2,
            sheet_count=2,
            valid_dwg_files=2,
            invalid_dwg_files=0,
            source_files=sources,
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord("S0001", "F0001", "04.dwg", 4, "04", "交流回路图1", "二次原理图", "primary", "filename", True),
            SheetRecord("S0002", "F0002", "05.dwg", 5, "05", "交流回路图2", "二次原理图", "primary", "filename", True),
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    pairs = [
        Pair(
            pair_id="P0001",
            line_group_id="G0001",
            sheet_id="S0001",
            file_id="F0001",
            selected_pair_candidate_id="PC1",
            left_value="101",
            right_value="201",
            confidence=0.97,
            status="pass",
            rationale="ok",
            alternative_pair_candidate_ids=[],
            confidence_bucket="high",
            evidence={"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4},
        ),
        Pair(
            pair_id="P0002",
            line_group_id="G0002",
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id="PC2",
            left_value="101",
            right_value="202",
            confidence=0.96,
            status="pass",
            rationale="ok",
            alternative_pair_candidate_ids=[],
            confidence_bucket="high",
            evidence={"filename": "05.dwg", "sheet_no": "05", "sheet_order": 5},
        ),
        Pair(
            pair_id="P0003",
            line_group_id="G0003",
            sheet_id="S0002",
            file_id="F0002",
            selected_pair_candidate_id="PC3",
            left_value="201",
            right_value="101",
            confidence=0.95,
            status="pass",
            rationale="reverse reference",
            alternative_pair_candidate_ids=[],
            confidence_bucket="high",
            evidence={"filename": "05.dwg", "sheet_no": "05", "sheet_order": 5},
        ),
    ]

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan, pairs=pairs), tmp_path)
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
    findings_text = (project_dir / "findings" / "findings.md").read_text(encoding="utf-8")

    table = findings_payload["one_to_many_review_table"]
    assert table["cluster_count"] == 1
    assert table["branch_cluster_count"] == 0
    assert table["review_cluster_count"] == 0
    assert table["conflict_cluster_count"] == 1
    assert table["clusters"][0]["cluster_id"] == "OTM:101"
    assert table["clusters"][0]["left_value"] == "101"
    assert table["clusters"][0]["classification"] == "conflict"
    assert table["clusters"][0]["classification_reason"] == "cross_page_multi_target"
    assert table["clusters"][0]["right_values"] == ["201", "202"]
    assert table["clusters"][0]["cross_page"] is True
    assert table["clusters"][0]["reciprocal_pair_count"] == 1
    assert table["clusters"][0]["pairs"][0]["location"]["sheet_no"] == "04"
    assert table["clusters"][0]["pairs"][0]["pair_id"] == "P0001"
    assert "## 一对多簇复核表" in findings_text
    assert "ConflictClusters: `1`" in findings_text
    assert "`101` -> `201, 202` (classification=conflict, reason=cross_page_multi_target, cross_page=True" in findings_text


def test_write_project_artifacts_marks_same_sheet_one_to_many_as_review(tmp_path: Path) -> None:
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[
                SourceFileRecord(
                    file_id="F0001",
                    path="C:/demo/04.dwg",
                    filename="04.dwg",
                    ext=".dwg",
                    sha256="abc",
                    size_bytes=10,
                    sheet_order=4,
                    detected_page_no="04",
                    detected_from="filename",
                    sheet_title="交流回路图1",
                    sheet_category="二次原理图",
                    skip_reason=None,
                    valid_dwg_header=True,
                    conversion_status="converted",
                )
            ],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[SheetRecord("S0001", "F0001", "04.dwg", 4, "04", "交流回路图1", "二次原理图", "primary", "filename", True)],
        terminal_strips=[],
        project_root="C:/demo",
    )
    pairs = [
        Pair("P0001", "G0001", "S0001", "F0001", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4}),
        Pair("P0002", "G0002", "S0001", "F0001", "PC2", "101", "202", 0.74, "review", "weak evidence", [], "review", {"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4}),
    ]

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan, pairs=pairs), tmp_path)
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))

    table = findings_payload["one_to_many_review_table"]
    assert table["cluster_count"] == 1
    assert table["branch_cluster_count"] == 0
    assert table["review_cluster_count"] == 1
    assert table["conflict_cluster_count"] == 0
    assert table["clusters"][0]["classification"] == "review"
    assert table["clusters"][0]["classification_reason"] == "weak_evidence"


def test_write_project_artifacts_marks_allowlisted_one_to_many_as_branch(tmp_path: Path) -> None:
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[
                SourceFileRecord(
                    file_id="F0001",
                    path="C:/demo/04.dwg",
                    filename="04.dwg",
                    ext=".dwg",
                    sha256="abc",
                    size_bytes=10,
                    sheet_order=4,
                    detected_page_no="04",
                    detected_from="filename",
                    sheet_title="交流回路图1",
                    sheet_category="二次原理图",
                    skip_reason=None,
                    valid_dwg_header=True,
                    conversion_status="converted",
                )
            ],
            sidecars=[],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[SheetRecord("S0001", "F0001", "04.dwg", 4, "04", "交流回路图1", "二次原理图", "primary", "filename", True)],
        terminal_strips=[],
        project_root="C:/demo",
    )
    pairs = [
        Pair("P0001", "G0001", "S0001", "F0001", "PC1", "101", "201", 0.97, "pass", "ok", [], "high", {"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4}),
        Pair("P0002", "G0002", "S0001", "F0001", "PC2", "101", "202", 0.96, "pass", "ok", [], "high", {"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4}),
    ]

    project_dir = write_project_artifacts(
        ProjectArtifacts(scan=scan, pairs=pairs),
        tmp_path,
        config={"rules": {"one_to_many_branch_left_values": ["101"]}},
    )
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))

    table = findings_payload["one_to_many_review_table"]
    assert table["cluster_count"] == 1
    assert table["branch_cluster_count"] == 1
    assert table["review_cluster_count"] == 0
    assert table["conflict_cluster_count"] == 0
    assert table["clusters"][0]["classification"] == "branch"
    assert table["clusters"][0]["classification_reason"] == "allowlisted_branch"


def test_write_audit_outputs_emits_issue_artifacts_with_evidence_fields(tmp_path: Path) -> None:
    source = SourceFileRecord(
        file_id="F0001",
        path="C:/demo/04.dwg",
        filename="04.dwg",
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=4,
        detected_page_no="04",
        detected_from="filename",
        sheet_title="交流回路图1",
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
    )
    scan = ProjectScanResult(
        manifest=Manifest(
            project_id="Demo 项目",
            project_name="Demo 项目",
            created_at="2026-07-03T00:00:00+00:00",
            tool_version="0.2.0",
            input_root="C:/demo",
            file_count=1,
            sheet_count=1,
            valid_dwg_files=1,
            invalid_dwg_files=0,
            source_files=[source],
            sidecars=[SidecarInfo("prj", None, "missing", None, ["No .prj sidecar found."])],
            project_name_sources={"filesystem_project_name": "Demo 项目"},
            warnings=[],
        ),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                "04.dwg",
                4,
                "04",
                "交流回路图1",
                "二次原理图",
                "primary",
                "filename",
                True,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )
    issue = Issue(
        issue_id="I0001",
        rule_id="R-CROSS-PAGE-CONFLICT",
        severity="critical",
        status="open",
        confidence=0.97,
        message="conflict",
        sheet_id="S0001",
        file_id="F0001",
        pair_id="P0001",
        line_group_id="G0001",
        left_value="101",
        right_value="201",
        evidence={
            "filename": "04.dwg",
            "sheet_no": "04",
            "sheet_order": 4,
            "line_start": [10.0, 20.0],
            "line_end": [40.0, 20.0],
            "rationale": "ok",
            "one_to_many_classification": "conflict",
        },
        title="跨页配对冲突",
        summary="数字 101 在不同跨页位置出现冲突配对。",
        explanation="同一线号在高置信 pair 中关联到了不一致的目标数字。",
        recommended_action="优先复核 04.dwg 上对应线端的跨页引用。",
    )
    pair = Pair(
        pair_id="P0001",
        line_group_id="G0001",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC1",
        left_value="101",
        right_value="201",
        confidence=0.97,
        status="pass",
        rationale="ok",
        alternative_pair_candidate_ids=[],
        confidence_bucket="high",
        evidence={"filename": "04.dwg", "sheet_no": "04", "sheet_order": 4},
    )
    review_pair = Pair(
        pair_id="P0002",
        line_group_id="G0002",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC2",
        left_value="202",
        right_value="301",
        confidence=0.74,
        status="review",
        rationale="right side has competing numeric candidates",
        alternative_pair_candidate_ids=["PC3"],
        confidence_bucket="review",
        evidence={
            "filename": "04.dwg",
            "sheet_no": "04",
            "sheet_order": 4,
            "line_start": [60.0, 25.0],
            "line_end": [96.0, 25.0],
        },
    )
    discard_pair = Pair(
        pair_id="P0003",
        line_group_id="G0003",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC3",
        left_value=None,
        right_value=None,
        confidence=0.18,
        status="discard",
        rationale="missing numeric candidates on both sides",
        alternative_pair_candidate_ids=[],
        confidence_bucket="low",
        evidence={
            "filename": "04.dwg",
            "sheet_no": "04",
            "sheet_order": 4,
            "line_start": [12.0, 30.0],
            "line_end": [24.0, 30.0],
        },
    )

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan, pairs=[pair, review_pair, discard_pair]), tmp_path)
    audit_dir = write_audit_outputs(
        project_dir,
        issues=[issue],
        pairs=[pair, review_pair, discard_pair],
        source_files=scan.manifest.source_files,
        project_name=scan.manifest.project_name,
    )
    findings_payload = json.loads((project_dir / "findings" / "findings.json").read_text(encoding="utf-8"))
    findings_text = (project_dir / "findings" / "findings.md").read_text(encoding="utf-8")
    issues_payload = json.loads((audit_dir / "issues.json").read_text(encoding="utf-8"))
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert findings_payload["pair_evidence_summary"]["pairs_with_evidence"] == 3
    assert findings_payload["pair_evidence_summary"]["review_pairs"] == 1
    assert findings_payload["pair_evidence_summary"]["confidence_bucket_counts"] == {"high": 1, "low": 1, "review": 1}
    assert findings_payload["audit_disposition_counts"] == {"audit_required": 1}
    assert findings_payload["pair_evidence_summary"]["examples"][0]["summary"] == (
        "filename=04.dwg, sheet_no=04, sheet_order=4, line_group=G0001, left_value=101, right_value=201"
    )
    assert findings_payload["pair_evidence_summary"]["review_examples"][0]["pair_id"] == "P0002"
    assert "## Pair Evidence 摘要" in findings_text
    assert "## 待复核 Pair 概览" in findings_text
    assert "## 代表性 Pair 证据" in findings_text
    assert "AuditDispositionCounts: `{\"audit_required\": 1}`" in findings_text
    assert "ConfidenceBuckets: `{\"high\": 1, \"low\": 1, \"review\": 1}`" in findings_text
    assert "ReviewPairs: `1`" in findings_text
    assert "filename=04.dwg, sheet_no=04, sheet_order=4, line_group=G0001, left_value=101, right_value=201" in findings_text
    assert "`P0002` 202 -> 301 (status=review, bucket=review, conf=0.74)" in findings_text
    assert "rationale=right side has competing numeric candidates" in findings_text

    assert issues_payload[0]["issue_id"] == "I0001"
    assert issues_payload[0]["filename"] == "04.dwg"
    assert issues_payload[0]["sheet_no"] == "04"
    assert issues_payload[0]["sheet_order"] == 4
    assert issues_payload[0]["rationale"] == "ok"
    assert issues_payload[0]["evidence"]["filename"] == "04.dwg"

    assert "## 审计概览" in report_text
    assert "SeverityCounts: `{\"critical\": 1}`" in report_text
    assert "RuleCounts: `{\"R-CROSS-PAGE-CONFLICT\": 1}`" in report_text
    assert "ReviewPairs: `1`" in report_text
    assert "## 待复核 Pair" in report_text
    assert "`P0002` 202 -> 301 (status=review, bucket=review, conf=0.74)" in report_text
    assert "`P0003` ? -> ?" not in report_text
    assert "evidence=filename=04.dwg, sheet_no=04, sheet_order=4, line_start=[60.0, 25.0], line_end=[96.0, 25.0]" in report_text
    assert "## 异常清单" in report_text
    assert "### `I0001` 跨页配对冲突" in report_text
    assert "- Location: file=04.dwg, sheet_no=04, sheet_order=4, line_group=G0001, line_start=[10.0, 20.0], line_end=[40.0, 20.0]" in report_text
    assert "- OneToManyTriage: `conflict`" in report_text
    assert "- Summary: 数字 101 在不同跨页位置出现冲突配对。" in report_text
    assert "- Explanation: 同一线号在高置信 pair 中关联到了不一致的目标数字。" in report_text
    assert "- RecommendedAction: 优先复核 04.dwg 上对应线端的跨页引用。" in report_text
    assert (audit_dir / "audit_v2_issue_clusters.parquet").exists()
    assert (audit_dir / "audit_v2_summary.json").exists()
    assert (audit_dir / "failure_queue.parquet").exists()
    assert (audit_dir / "failure_queue_summary.json").exists()
    audit_v2_summary = json.loads(
        (audit_dir / "audit_v2_summary.json").read_text(encoding="utf-8")
    )
    assert audit_v2_summary["issue_count"] == 1
    assert audit_v2_summary["cluster_count"] >= 1
    assert audit_v2_summary["legacy_issue_stream_retained"] is True
    failure_queue_summary = json.loads(
        (audit_dir / "failure_queue_summary.json").read_text(encoding="utf-8")
    )
    assert "item_count" in failure_queue_summary
    assert "audit_v2_issue_clusters.parquet" in findings_payload["artifacts"]["audit"]
    assert "failure_queue.parquet" in findings_payload["artifacts"]["audit"]


def test_write_audit_outputs_shows_continuation_pair_semantics(tmp_path: Path) -> None:
    continuation_pair = Pair(
        pair_id="P0001",
        line_group_id="G0001",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC1",
        left_value="420",
        right_value="420",
        confidence=0.88,
        status="review",
        rationale="continuation relation",
        alternative_pair_candidate_ids=[],
        confidence_bucket="review",
        evidence={
            "filename": "26.dwg",
            "sheet_no": "26",
            "sheet_order": 26,
            "line_group_id": "G0001",
            "line_start": [325.0, 145.0],
            "line_end": [400.0, 145.0],
            "pair_kind": "continuation",
            "continuation_kind": "terminal_same_value_bridge",
            "line_orientation": "horizontal",
        },
        pair_kind="continuation",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[],
        pairs=[continuation_pair],
        source_files=[],
        project_name="Demo 项目",
        formats=["md"],
    )
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert "pair_kind=continuation" in report_text
    assert "continuation_kind=terminal_same_value_bridge" in report_text


def test_write_audit_outputs_shows_bridge_mapping_pair_semantics(tmp_path: Path) -> None:
    bridge_pair = Pair(
        pair_id="P0001",
        line_group_id="G0001",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC1",
        left_value="110",
        right_value="330",
        confidence=0.89,
        status="review",
        rationale="bridge mapping relation",
        alternative_pair_candidate_ids=[],
        confidence_bucket="review",
        evidence={
            "filename": "21.dwg",
            "sheet_no": "21",
            "sheet_order": 21,
            "line_group_id": "G0001",
            "line_start": [310.0, 226.0],
            "line_end": [385.0, 226.0],
            "pair_kind": "bridge_mapping",
            "bridge_mapping_kind": "terminal_short_bridge_cross_column",
            "line_orientation": "horizontal",
        },
        pair_kind="bridge_mapping",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[],
        pairs=[bridge_pair],
        source_files=[],
        project_name="Demo 项目",
        formats=["md"],
    )
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert "pair_kind=bridge_mapping" in report_text
    assert "bridge_mapping_kind=terminal_short_bridge_cross_column" in report_text


def test_write_audit_outputs_shows_semantic_mapping_pair_semantics(tmp_path: Path) -> None:
    semantic_pair = Pair(
        pair_id="P0001",
        line_group_id="G0001",
        sheet_id="S0001",
        file_id="F0001",
        selected_pair_candidate_id="PC1",
        left_value=None,
        right_value="108",
        confidence=0.86,
        status="review",
        rationale="semantic mapping relation",
        alternative_pair_candidate_ids=[],
        confidence_bucket="review",
        evidence={
            "filename": "21.dwg",
            "sheet_no": "21",
            "sheet_order": 21,
            "line_group_id": "G0001",
            "line_start": [127.5, 255.0],
            "line_end": [202.5, 255.0],
            "pair_kind": "semantic_mapping",
            "semantic_mapping_kind": "terminal_semantic_row",
            "semantic_marker_texts": ["3-21KLP2-1", "3-21KLP1-1"],
            "line_orientation": "horizontal",
        },
        pair_kind="semantic_mapping",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[],
        pairs=[semantic_pair],
        source_files=[],
        project_name="Demo 项目",
        formats=["md"],
    )
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert "pair_kind=semantic_mapping" in report_text
    assert "semantic_mapping_kind=terminal_semantic_row" in report_text
    assert "semantic_markers=3-21KLP2-1|3-21KLP1-1" in report_text


def test_write_audit_outputs_respects_requested_report_formats(tmp_path: Path) -> None:
    issue = Issue(
        issue_id="I0001",
        rule_id="R-CROSS-PAGE-CONFLICT",
        severity="critical",
        status="open",
        confidence=0.91,
        message="conflict",
        sheet_id="S0001",
        file_id="F0001",
        pair_id="P0001",
        line_group_id="G0001",
        left_value="101",
        right_value="201",
        evidence_refs=[
            {
                "filename": "04.dwg",
                "sheet_no": "04",
                "sheet_order": 4,
                "line_group_id": "G0001",
            }
        ],
        title="跨页配对冲突",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[issue],
        pairs=[],
        source_files=[],
        project_name="Demo 项目",
        formats=["md"],
    )
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert (audit_dir / "audit_report.md").exists()
    assert not (audit_dir / "audit_report.html").exists()
    assert not (audit_dir / "issues.xlsx").exists()
    assert "- Evidence: ref1: filename=04.dwg, sheet_no=04, sheet_order=4" in report_text


def test_write_audit_outputs_adds_evidence_display_to_html_and_excel(tmp_path: Path) -> None:
    issue = Issue(
        issue_id="I0001",
        rule_id="R-CROSS-PAGE-CONFLICT",
        severity="critical",
        status="open",
        confidence=0.91,
        message="conflict",
        sheet_id="S0001",
        file_id="F0001",
        pair_id="P0001",
        line_group_id="G0001",
        left_value="101",
        right_value="201",
        evidence={
            "many_to_one_classification": "component_split_endpoint_group_review",
            "component_submode": "strip_two_port_component",
            "component_branch_kind": "split_endpoint_group",
            "shared_endpoint": "5KLP3-1",
            "external_endpoint_splits": ["5KLP3-1"],
        },
        evidence_refs=[
            {
                "filename": "04.dwg",
                "sheet_no": "04",
                "sheet_order": 4,
                "line_group_id": "G0001",
                "left_value": "101",
                "right_value": "201",
                "one_to_many_classification": "conflict",
            }
        ],
        title="跨页配对冲突",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[issue],
        pairs=[],
        source_files=[],
        project_name="Demo 项目",
        formats="html,xlsx",
    )
    html = (audit_dir / "audit_report.html").read_text(encoding="utf-8")
    excel_issues = pd.read_excel(audit_dir / "issues.xlsx", sheet_name="issues")

    assert not (audit_dir / "audit_report.md").exists()
    assert "evidence_display" in html
    assert "ref1: filename=04.dwg, sheet_no=04, sheet_order=4" in html
    assert "evidence_display" in excel_issues.columns
    assert "one_to_many_classification" in excel_issues.columns
    assert "many_to_one_classification" in excel_issues.columns
    assert "review_classification" in excel_issues.columns
    assert "filename=04.dwg" in excel_issues.loc[0, "evidence_display"]
    assert "left_value=101" in excel_issues.loc[0, "evidence_display"]
    assert excel_issues.loc[0, "one_to_many_classification"] == "conflict"
    assert excel_issues.loc[0, "many_to_one_classification"] == "component_split_endpoint_group_review"
    assert excel_issues.loc[0, "review_classification"] == "conflict"


def test_write_audit_outputs_compacts_terminal_header_row_band_evidence(tmp_path: Path) -> None:
    issue = Issue(
        issue_id="I0021",
        rule_id="R-ONE-TO-MANY",
        severity="review",
        status="open",
        confidence=0.97,
        message="Terminal header table row-band multi-endpoint review.",
        sheet_id="S0023",
        file_id="F0023",
        pair_id="PTM0001",
        line_group_id=None,
        left_value="1-21QD1",
        right_value="1-21n116",
        evidence={
            "filename": "23 右侧端子图1.dwg",
            "sheet_no": "23",
            "sheet_order": 23,
            "one_to_many_classification": "terminal_header_table_multi_endpoint_review",
            "terminal_header_table_row_band_review": True,
            "terminal_header_table_aggregate_review": True,
            "aggregated_logical_endpoint_ranges": ["1-21QD1..1-21QD38"],
            "aggregated_row_number_ranges": ["1..38"],
            "aggregated_terminal_header_table_endpoint_ranges": [
                "1-21n116..1-21n222",
                "1-21n301..1-21n330",
                "1-21n524..1-21n531",
            ],
            "header_prefix": "1-21QD",
            "endpoint_columns": ["left_endpoint", "right_endpoint"],
            "cluster_size": 38,
            "cluster_pair_ids": [f"PTM{index:04d}" for index in range(1, 77)],
        },
        evidence_refs=[
            {
                "filename": "23 右侧端子图1.dwg",
                "sheet_no": "23",
                "sheet_order": 23,
                "pair_id": f"PTM{index:04d}",
                "left_value": f"1-21QD{index}",
                "right_value": f"1-21n{115 + index}",
            }
            for index in range(1, 77)
        ],
        title="端子表多端点行映射待复核",
        summary="Terminal header table row-band multi-endpoint review.",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[issue],
        pairs=[],
        source_files=[],
        project_name="Demo 项目",
        formats="md,xlsx",
    )
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")
    excel_issues = pd.read_excel(audit_dir / "issues.xlsx", sheet_name="issues")
    evidence_display = excel_issues.loc[0, "evidence_display"]

    assert "logical=1-21QD1..1-21QD38" in report_text
    assert "terminal_endpoints=1-21n116..1-21n222|1-21n301..1-21n330|1-21n524..1-21n531" in report_text
    assert "rows=1..38" in report_text
    assert "pair_count=76" in report_text
    assert "ref76:" not in report_text
    assert "logical=1-21QD1..1-21QD38" in evidence_display
    assert "pair_count=76" in evidence_display
    assert "ref76:" not in evidence_display


def test_write_audit_outputs_shows_many_to_one_component_split_review(tmp_path: Path) -> None:
    issue = Issue(
        issue_id="I0183",
        rule_id="R-MANY-TO-ONE",
        severity="review",
        status="open",
        confidence=0.97,
        message="Right value 5KLP3-1 is referenced by multiple component endpoints.",
        sheet_id="S0024",
        file_id="F0024",
        pair_id="PCM0066",
        line_group_id="GC0124",
        left_value="5KLP5-1",
        right_value="5KLP3-1",
        evidence={
            "filename": "23 元件接线图3.dwg",
            "sheet_no": "23",
            "sheet_order": 24,
            "many_to_one_classification": "component_split_endpoint_group_review",
            "component_submode": "strip_two_port_component",
            "component_branch_kind": "split_endpoint_group",
            "shared_endpoint": "5KLP3-1",
            "external_endpoint_raw_values": ["5KLP3-1,5KLP2-1"],
            "external_endpoint_splits": ["5KLP3-1"],
            "external_endpoint_text_ids": ["T3841"],
        },
        title="组件逗号端点邻接待复核",
        summary="组件逗号拆分端点邻接待复核。",
        explanation="共享邻接端来自逗号分隔端点组。",
        recommended_action="按原始逗号文本和组件端口复核。",
    )

    audit_dir = write_audit_outputs(
        tmp_path / "project",
        issues=[issue],
        pairs=[],
        source_files=[],
        project_name="Demo 项目",
        formats="md",
    )
    report_text = (audit_dir / "audit_report.md").read_text(encoding="utf-8")

    assert "- ReviewClassification: `component_split_endpoint_group_review`" in report_text
    assert "- ManyToOneTriage: `component_split_endpoint_group_review`" in report_text
    assert "component_submode=strip_two_port_component" in report_text
    assert "component_branch_kind=split_endpoint_group" in report_text
    assert "shared_endpoint=5KLP3-1" in report_text
    assert "external_endpoint_splits=5KLP3-1" in report_text
