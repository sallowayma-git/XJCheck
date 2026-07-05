from pathlib import Path

from dwg_audit.ingest.project_scanner import discover_project_roots
from dwg_audit.ingest.project_scanner import scan_project
from dwg_audit.utils.config import DEFAULT_CONFIG


def test_discover_project_roots_finds_nested_dirs(tmp_path: Path) -> None:
    project = tmp_path / "test" / "projectA"
    project.mkdir(parents=True)
    (project / "01 封面.dwg").write_bytes(b"AC1018demo")

    roots = discover_project_roots(tmp_path / "test")

    assert roots == [project]


def test_scan_project_uses_prj_metadata(tmp_path: Path, sample_text_prj: str, sample_terminal_xml: str) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "demo.prj").write_text(sample_text_prj, encoding="gbk")
    (project / "LdDzbInfo.xml").write_text(sample_terminal_xml, encoding="utf-8")
    (project / "01 封面.dwg").write_bytes(b"AC1018demo")
    (project / "04 交流回路图1.dwg").write_bytes(b"AC1018data")

    result = scan_project(project, DEFAULT_CONFIG)

    assert result.manifest.file_count == 2
    assert result.manifest.valid_dwg_files == 2
    assert result.pages[1].sheet_category == "二次原理图"
    assert result.pages[1].is_primary_audit_candidate is True
    assert result.terminal_strips[0].style == "左侧"


def test_scan_project_marks_non_primary_pages_as_secondary(tmp_path: Path) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "07 屏端子图.dwg").write_bytes(b"AC1018data")

    result = scan_project(project, DEFAULT_CONFIG)

    assert result.pages[0].sheet_category == "屏端子图"
    assert result.pages[0].audit_role == "secondary"
    assert result.pages[0].is_primary_audit_candidate is False


def test_scan_project_keeps_backplate_pages_secondary_even_with_protection_keywords(tmp_path: Path) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "17 差动保护背板图.dwg").write_bytes(b"AC1018data")

    result = scan_project(project, DEFAULT_CONFIG)

    assert result.pages[0].sheet_category == "背板接线图"
    assert result.pages[0].audit_role == "secondary"
    assert result.pages[0].is_primary_audit_candidate is False


def test_scan_project_splits_component_wiring_from_backplate_category(tmp_path: Path) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "21 元件接线图1.dwg").write_bytes(b"AC1018data")

    result = scan_project(project, DEFAULT_CONFIG)

    assert result.pages[0].sheet_category == "元件接线图"
    assert result.pages[0].audit_role == "secondary"
    assert result.pages[0].is_primary_audit_candidate is False


def test_scan_project_normalizes_prj_backplate_bucket_for_component_wiring(tmp_path: Path, sample_terminal_xml: str) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "demo.prj").write_text(
        (
            "$BEGIN CONTENT OF PRJ\r\n"
            "背板接线图:\r\n"
            "21 元件接线图1.dwg<>\r\n"
            "$END CONTENT OF PRJ\r\n"
            "$EOF\r\n"
        ),
        encoding="gbk",
    )
    (project / "LdDzbInfo.xml").write_text(sample_terminal_xml, encoding="utf-8")
    (project / "21 元件接线图1.dwg").write_bytes(b"AC1018data")

    result = scan_project(project, DEFAULT_CONFIG)

    assert result.pages[0].sheet_category == "元件接线图"
    assert result.pages[0].audit_role == "secondary"


def test_scan_project_marks_skipped_pages_as_skip(tmp_path: Path) -> None:
    project = tmp_path / "projectA"
    project.mkdir()
    (project / "01 封面.dwg").write_bytes(b"AC1018data")

    result = scan_project(project, DEFAULT_CONFIG)

    assert result.manifest.source_files[0].skip_reason == "matched skip keyword: 封面"
    assert result.pages[0].audit_role == "skip"
    assert result.pages[0].is_primary_audit_candidate is False
    assert "matched skip keyword: 封面" in result.pages[0].warnings
