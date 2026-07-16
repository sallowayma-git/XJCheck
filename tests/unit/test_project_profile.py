from __future__ import annotations

from dwg_audit.audit.project_profile import build_project_profile
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SidecarInfo
from dwg_audit.domain.models import TerminalStrip


def _make_scan() -> ProjectScanResult:
    pages = [
        SheetRecord(
            sheet_id="S1",
            file_id="F1",
            filename="01 封面.dwg",
            sheet_order=1,
            sheet_no="01",
            sheet_title="封面",
            sheet_category="封面/目录",
            audit_role="skip",
            page_no_source="prj",
            is_primary_audit_candidate=False,
        ),
        SheetRecord(
            sheet_id="S2",
            file_id="F2",
            filename="04 交流回路图1.dwg",
            sheet_order=2,
            sheet_no="04",
            sheet_title="交流回路图1",
            sheet_category="二次原理图",
            audit_role="primary",
            page_no_source="prj",
            is_primary_audit_candidate=True,
        ),
    ]
    strips = [
        TerminalStrip(style="左侧", name="ZD", length=120.0),
        TerminalStrip(style="右侧", name="YD", length=80.0),
    ]
    manifest = Manifest(
        project_id="projectA",
        project_name="示例工程",
        created_at="2026-07-11T00:00:00Z",
        tool_version="0.1.0",
        input_root=r"F:\data\projectA",
        file_count=2,
        sheet_count=2,
        valid_dwg_files=2,
        invalid_dwg_files=0,
        sidecars=[
            SidecarInfo(
                kind="prj",
                path=r"F:\data\projectA\demo.prj",
                status="parsed",
                encoding="gbk",
            ),
            SidecarInfo(
                kind="terminal_xml",
                path=r"F:\data\projectA\LdDzbInfo.xml",
                status="parsed",
                encoding="utf-8",
            ),
        ],
        project_name_sources={
            "filesystem_project_name": "projectA",
            "prj_project_name": "demo",
            "device_name": "示例项目",
            "prj_note_device_name": "示例工程",
        },
        warnings=["Duplicate sheet numbers detected; use sheet_order as the primary stable order."],
    )
    return ProjectScanResult(
        manifest=manifest,
        pages=pages,
        terminal_strips=strips,
        project_root=r"F:\data\projectA",
    )


def test_build_project_profile_from_minimal_scan() -> None:
    profile = build_project_profile(_make_scan())

    assert profile["schema_version"] == "project-profile-v1"
    assert profile["project_id"] == "projectA"
    assert profile["project_name"] == "示例工程"
    assert profile["project_root"] == r"F:\data\projectA"
    assert profile["sidecar_status"] == {"prj": "parsed", "terminal_xml": "parsed"}
    # Prefer prj_note_device_name over terminal xml device_name.
    assert profile["device_name"] == "示例工程"
    assert profile["terminal_strips"] == [
        {"style": "左侧", "name": "ZD", "length": 120.0},
        {"style": "右侧", "name": "YD", "length": 80.0},
    ]
    assert len(profile["page_catalog"]) == 2
    assert profile["page_catalog"][1] == {
        "sheet_id": "S2",
        "filename": "04 交流回路图1.dwg",
        "sheet_no": "04",
        "sheet_title": "交流回路图1",
        "sheet_category": "二次原理图",
        "page_no_source": "prj",
        "audit_role": "primary",
    }
    terms = {(item["term"], item["kind"], item["source"]) for item in profile["alias_lexicon"]}
    assert ("ZD", "terminal_strip", "terminal_xml") in terms
    assert ("YD", "terminal_strip", "terminal_xml") in terms
    assert ("示例工程", "device_name", "prj_note_device_name") in terms
    assert ("封面", "sheet_title", "page_catalog") in terms
    assert ("交流回路图1", "sheet_title", "page_catalog") in terms
    assert profile["warnings"] == [
        "Duplicate sheet numbers detected; use sheet_order as the primary stable order."
    ]
    assert profile["evidence"] == {
        "sidecar_kinds": ["prj", "terminal_xml"],
        "page_count": 2,
        "strip_count": 2,
    }


def test_build_project_profile_falls_back_to_terminal_device_name() -> None:
    scan = _make_scan()
    scan.manifest.project_name_sources = {
        "filesystem_project_name": "projectA",
        "device_name": "示例项目",
    }

    profile = build_project_profile(scan)

    assert profile["device_name"] == "示例项目"
    device_entries = [
        item for item in profile["alias_lexicon"] if item["kind"] == "device_name"
    ]
    assert device_entries == [
        {"term": "示例项目", "source": "device_name", "kind": "device_name"}
    ]


def test_build_project_profile_missing_sidecars() -> None:
    scan = _make_scan()
    scan.manifest.sidecars = []
    scan.manifest.project_name_sources = {"filesystem_project_name": "projectA"}
    scan.terminal_strips = []

    profile = build_project_profile(scan)

    assert profile["sidecar_status"] == {"prj": "missing", "terminal_xml": "missing"}
    assert profile["device_name"] is None
    assert profile["terminal_strips"] == []
    assert profile["evidence"]["strip_count"] == 0
    assert profile["evidence"]["sidecar_kinds"] == []
