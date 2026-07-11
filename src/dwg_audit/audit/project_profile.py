from __future__ import annotations

from typing import Any

from dwg_audit.domain.models import ProjectScanResult


SCHEMA_VERSION = "project-profile-v1"


def build_project_profile(scan: ProjectScanResult) -> dict[str, Any]:
    """Build a pure project-profile-v1 dict from an existing scan result.

    Pure function: no IO. Never invents device/strip values beyond scan fields.
    """
    manifest = scan.manifest
    sources = dict(manifest.project_name_sources or {})

    device_name = _resolve_device_name(sources)
    sidecar_status = _sidecar_status(manifest.sidecars)
    terminal_strips = [
        {"style": strip.style, "name": strip.name, "length": strip.length}
        for strip in scan.terminal_strips
    ]
    page_catalog = [
        {
            "sheet_id": page.sheet_id,
            "filename": page.filename,
            "sheet_no": page.sheet_no,
            "sheet_title": page.sheet_title,
            "sheet_category": page.sheet_category,
            "page_no_source": page.page_no_source,
            "audit_role": page.audit_role,
        }
        for page in scan.pages
    ]
    alias_lexicon = _build_alias_lexicon(
        device_name=device_name,
        sources=sources,
        terminal_strips=scan.terminal_strips,
        pages=scan.pages,
    )
    sidecar_kinds = sorted(
        {
            str(getattr(sidecar, "kind", "") or "")
            for sidecar in manifest.sidecars
            if getattr(sidecar, "kind", None)
        }
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": manifest.project_id,
        "project_name": manifest.project_name,
        "project_root": scan.project_root,
        "sidecar_status": sidecar_status,
        "device_name": device_name,
        "terminal_strips": terminal_strips,
        "page_catalog": page_catalog,
        "alias_lexicon": alias_lexicon,
        "warnings": list(manifest.warnings or []),
        "evidence": {
            "sidecar_kinds": sidecar_kinds,
            "page_count": len(scan.pages),
            "strip_count": len(scan.terminal_strips),
        },
    }


def _resolve_device_name(sources: dict[str, str]) -> str | None:
    """Prefer prj note device name, then terminal-xml device_name source."""
    for key in ("prj_note_device_name", "device_name"):
        value = sources.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _sidecar_status(sidecars: list[Any]) -> dict[str, str]:
    status = {"prj": "missing", "terminal_xml": "missing"}
    for sidecar in sidecars or []:
        kind = str(getattr(sidecar, "kind", "") or "")
        if kind in status:
            status[kind] = str(getattr(sidecar, "status", "missing") or "missing")
    return status


def _build_alias_lexicon(
    *,
    device_name: str | None,
    sources: dict[str, str],
    terminal_strips: list[Any],
    pages: list[Any],
) -> list[dict[str, str]]:
    """Weak semantic lexicon only: strips, device name, distinct sheet titles."""
    lexicon: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(term: str | None, source: str, kind: str) -> None:
        text = str(term or "").strip()
        if not text:
            return
        key = (text, source, kind)
        if key in seen:
            return
        seen.add(key)
        lexicon.append({"term": text, "source": source, "kind": kind})

    for strip in terminal_strips:
        _add(getattr(strip, "name", None), "terminal_xml", "terminal_strip")

    if device_name:
        if sources.get("prj_note_device_name") and str(sources["prj_note_device_name"]).strip() == device_name:
            device_source = "prj_note_device_name"
        elif sources.get("device_name") and str(sources["device_name"]).strip() == device_name:
            device_source = "device_name"
        else:
            device_source = "project_name_sources"
        _add(device_name, device_source, "device_name")

    for page in pages:
        _add(getattr(page, "sheet_title", None), "page_catalog", "sheet_title")

    return lexicon
