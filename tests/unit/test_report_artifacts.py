import json
from pathlib import Path

import pandas as pd

from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SidecarInfo
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.report.artifacts import write_audit_outputs
from dwg_audit.report.artifacts import write_project_artifacts


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

    project_dir = write_project_artifacts(ProjectArtifacts(scan=scan), tmp_path)
    findings_dir = project_dir / "findings"
    page_findings_dir = findings_dir / "page_findings"
    findings_payload = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))

    assert (project_dir / "manifest.json").exists()
    assert (findings_dir / "findings.md").exists()
    assert (findings_dir / "findings.json").exists()
    assert (findings_dir / "polylines.parquet").exists()
    assert (findings_dir / "extraction_warnings.parquet").exists()
    assert not page_findings_dir.exists()
    assert findings_payload["page_findings_count"] == 1
    assert len(findings_payload["page_findings"]) == 1
    assert findings_payload["page_findings"][0]["sheet_id"] == "S0001"
    assert findings_payload["page_findings"][0]["file_id"] == "F0001"
    assert findings_payload["page_findings"][0]["audit_role"] == "skip"
    assert findings_payload["page_findings"][0]["audit_disposition"] == "skip_stable"
    assert findings_payload["page_findings"][0]["filename"] == "01.dwg"
    assert findings_payload["page_findings"][0]["route_target"] == "SkipExtractor"
    assert findings_payload["page_findings"][0]["structure_summary"]["pair_count"] == 0
    assert findings_payload["audit_disposition_counts"] == {"skip_stable": 1}
    assert "page_findings/" not in findings_payload["artifacts"]["findings"]


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
    assert "filename=04.dwg" in excel_issues.loc[0, "evidence_display"]
    assert "left_value=101" in excel_issues.loc[0, "evidence_display"]
    assert excel_issues.loc[0, "one_to_many_classification"] == "conflict"
