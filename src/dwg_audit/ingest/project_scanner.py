from __future__ import annotations

import hashlib
import re
from datetime import UTC
from datetime import datetime
from pathlib import Path

from dwg_audit import __version__
from dwg_audit.domain.models import Manifest
from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SidecarInfo
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.ingest.sidecar_parser import extract_device_name
from dwg_audit.ingest.sidecar_parser import parse_prj
from dwg_audit.ingest.sidecar_parser import parse_terminal_xml
from dwg_audit.utils.ids import IdFactory


_PAGE_PREFIX_PATTERN = re.compile(r"^(?P<page>\d+)\s+(?P<title>.+?)(?:\.dwg)?$", re.IGNORECASE)
_DEFAULT_SUPPLEMENTAL_CATEGORIES = {"屏端子图", "元件接线图"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _natural_sort_key(path: Path) -> tuple[int, str]:
    match = _PAGE_PREFIX_PATTERN.match(path.stem)
    if not match:
        return (10_000, path.name.lower())
    return (int(match.group("page")), path.name.lower())


def _valid_dwg_header(path: Path) -> bool:
    return path.read_bytes()[:4].startswith(b"AC10")


def _clean_project_name(value: str | None) -> str | None:
    if not value:
        return value
    return value[:-4] if value.lower().endswith(".prj") else value


def discover_project_roots(input_path: Path) -> list[Path]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    if input_path.is_file():
        raise ValueError("Input path must be a directory.")

    direct = list(input_path.glob("*.dwg"))
    if direct:
        return [input_path]

    roots = sorted({dwg.parent for dwg in input_path.rglob("*.dwg")})
    return [root for root in roots if any(root.glob("*.dwg"))]


def _infer_category(title: str) -> str | None:
    rules = [
        ("封面/目录", ("封面", "目录")),
        ("屏面布置图", ("屏面布置",)),
        ("屏端子图", ("端子图",)),
        ("元件接线图", ("元件接线图",)),
        ("背板接线图", ("背板",)),
        ("二次原理图", ("回路图", "回路", "信号", "保护", "出口", "操作", "开入", "控制")),
    ]
    for category, keywords in rules:
        if any(keyword in title for keyword in keywords):
            return category
    return None


def _normalize_category(category: str | None, title: str) -> str | None:
    overrides = [
        ("封面/目录", ("封面", "目录")),
        ("屏面布置图", ("屏面布置",)),
        ("屏端子图", ("端子图",)),
        ("元件接线图", ("元件接线图",)),
        ("背板接线图", ("背板",)),
    ]
    for normalized, keywords in overrides:
        if any(keyword in title for keyword in keywords):
            return normalized
    return category


def _infer_audit_role(category: str | None, title: str, skip_reason: str | None, config: dict) -> str:
    if skip_reason:
        return "skip"
    project_config = config.get("project", {})
    primary_categories = {str(item) for item in project_config.get("audit_primary_categories", ["二次原理图"])}
    supplemental_categories = {str(item) for item in project_config.get("audit_supplemental_categories", [])}
    secondary_categories = {
        str(item)
        for item in project_config.get(
            "audit_secondary_categories",
            ["背板接线图", "元件接线图", "屏端子图", "屏面布置图", "封面/目录"],
        )
    }
    primary_keywords = tuple(str(item) for item in project_config.get("audit_primary_title_keywords", []))
    secondary_keywords = tuple(str(item) for item in project_config.get("audit_secondary_title_keywords", []))
    if category in primary_categories:
        return "primary"
    if category in supplemental_categories:
        return "supplemental"
    if category in _DEFAULT_SUPPLEMENTAL_CATEGORIES:
        return "supplemental"
    if category in secondary_categories:
        return "secondary"
    if any(keyword in title for keyword in secondary_keywords):
        return "secondary"
    if any(keyword in title for keyword in primary_keywords):
        return "primary"
    return "secondary"


def _should_skip(title: str, filename: str, category: str | None, config: dict) -> str | None:
    for pattern in config.get("project", {}).get("skip_globs", []):
        if Path(filename).match(pattern):
            return f"matched skip glob: {pattern}"
    for keyword in config.get("project", {}).get("skip_files", []):
        if keyword and (keyword in title or (category and keyword in category)):
            return f"matched skip keyword: {keyword}"
    if "~1" in filename:
        return "detected backup duplicate suffix"
    return None


def scan_project(input_path: Path, config: dict) -> ProjectScanResult:
    prj_path = next(input_path.glob("*.prj"), None)
    terminal_xml_path = input_path / "LdDzbInfo.xml"

    prj_entries, prj_notes, prj_encoding, prj_warnings = ([], {}, None, [])
    if prj_path is not None:
        prj_entries, prj_notes, prj_encoding, prj_warnings = parse_prj(prj_path)
    prj_map = {entry.filename: entry for entry in prj_entries}

    terminal_strips = parse_terminal_xml(terminal_xml_path) if terminal_xml_path.exists() else []
    device_name = extract_device_name(terminal_xml_path) if terminal_xml_path.exists() else None

    dwg_files = [path for path in input_path.glob("*.dwg") if path.is_file()]
    dwg_files = sorted(dwg_files, key=_natural_sort_key)
    if prj_entries:
        dwg_files = sorted(
            dwg_files,
            key=lambda path: (
                prj_map[path.name].order if path.name in prj_map else 99_999,
                _natural_sort_key(path),
            ),
        )

    file_ids = IdFactory("F")
    sheet_ids = IdFactory("S")
    source_files: list[SourceFileRecord] = []
    pages: list[SheetRecord] = []

    valid_count = 0
    invalid_count = 0

    for fallback_order, dwg_path in enumerate(dwg_files, start=1):
        prj_entry = prj_map.get(dwg_path.name)
        prefix_match = _PAGE_PREFIX_PATTERN.match(dwg_path.stem)
        page_no = prefix_match.group("page") if prefix_match else None
        title = prefix_match.group("title") if prefix_match else dwg_path.stem
        page_source = "filename" if prefix_match else "unknown"

        if prj_entry:
            title = prj_entry.title
            page_no = prj_entry.page_no or page_no
            page_source = "prj"

        category = _normalize_category(prj_entry.category if prj_entry else _infer_category(title), title)
        skip_reason = _should_skip(title, dwg_path.name, category, config)
        valid_header = _valid_dwg_header(dwg_path)
        if valid_header:
            valid_count += 1
        else:
            invalid_count += 1

        warnings: list[str] = []
        if skip_reason:
            warnings.append(skip_reason)
        if not valid_header:
            warnings.append("DWG header is not a standard AC10* header; conversion may fail.")
        if prj_path is None:
            warnings.append("No .prj sidecar found.")

        source_file = SourceFileRecord(
            file_id=file_ids.next(),
            path=str(dwg_path.resolve()),
            filename=dwg_path.name,
            ext=dwg_path.suffix.lower(),
            sha256=_sha256(dwg_path),
            size_bytes=dwg_path.stat().st_size,
            sheet_order=prj_entry.order if prj_entry else fallback_order,
            detected_page_no=page_no,
            detected_from=page_source,
            sheet_title=title,
            sheet_category=category,
            skip_reason=skip_reason,
            valid_dwg_header=valid_header,
            sidecar_refs=[kind for kind, exists in (("prj", prj_entry is not None), ("terminal_xml", terminal_xml_path.exists())) if exists],
            warnings=warnings,
        )
        source_files.append(source_file)

        audit_role = _infer_audit_role(category, title, skip_reason, config)
        pages.append(
            SheetRecord(
                sheet_id=sheet_ids.next(),
                file_id=source_file.file_id,
                filename=dwg_path.name,
                sheet_order=source_file.sheet_order,
                sheet_no=page_no,
                sheet_title=title,
                sheet_category=category,
                audit_role=audit_role,
                page_no_source=page_source,
                is_primary_audit_candidate=audit_role in {"primary", "supplemental"},
                source_refs=source_file.sidecar_refs.copy(),
                warnings=warnings.copy(),
            )
        )

    warnings: list[str] = prj_warnings.copy()
    if len({page.sheet_no for page in pages if page.sheet_no}) != len([page.sheet_no for page in pages if page.sheet_no]):
        warnings.append("Duplicate sheet numbers detected; use sheet_order as the primary stable order.")

    project_name_sources = {"filesystem_project_name": input_path.name}
    if prj_path is not None:
        project_name_sources["prj_project_name"] = _clean_project_name(prj_path.stem) or prj_path.stem
    if device_name:
        project_name_sources["device_name"] = _clean_project_name(device_name) or device_name
    if prj_notes.get("设备名称"):
        project_name_sources["prj_note_device_name"] = _clean_project_name(prj_notes["设备名称"]) or prj_notes["设备名称"]

    project_name = (
        config.get("project", {}).get("name", "").strip()
        or project_name_sources.get("device_name")
        or project_name_sources.get("prj_project_name")
        or input_path.name
    )

    manifest = Manifest(
        project_id=input_path.name,
        project_name=project_name,
        created_at=datetime.now(UTC).isoformat(),
        tool_version=__version__,
        input_root=str(input_path.resolve()),
        file_count=len(source_files),
        sheet_count=len(pages),
        valid_dwg_files=valid_count,
        invalid_dwg_files=invalid_count,
        config_version=str(config.get("config_version", "0.1")),
        source_files=source_files,
        sidecars=[
            SidecarInfo(
                kind="prj",
                path=str(prj_path.resolve()) if prj_path else None,
                status="parsed" if prj_entries else ("unsupported" if prj_path else "missing"),
                encoding=prj_encoding,
                warnings=prj_warnings.copy() if prj_path else ["No .prj sidecar found."],
            ),
            SidecarInfo(
                kind="terminal_xml",
                path=str(terminal_xml_path.resolve()) if terminal_xml_path.exists() else None,
                status="parsed" if terminal_xml_path.exists() else "missing",
                encoding="utf-8" if terminal_xml_path.exists() else None,
                warnings=[] if terminal_xml_path.exists() else ["No LdDzbInfo.xml found."],
            ),
        ],
        project_name_sources=project_name_sources,
        warnings=warnings,
    )
    return ProjectScanResult(
        manifest=manifest,
        pages=pages,
        terminal_strips=terminal_strips,
        project_root=str(input_path.resolve()),
    )
