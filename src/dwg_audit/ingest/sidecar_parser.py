from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from dwg_audit.domain.models import TerminalStrip


@dataclass(slots=True)
class PrjEntry:
    filename: str
    page_no: str | None
    title: str
    category: str | None
    order: int


_DWG_LINE = re.compile(
    r"^(?P<page>\d+)\s+(?P<title>.+?)\.dwg<>$",
    re.IGNORECASE,
)


def parse_prj(path: Path) -> tuple[list[PrjEntry], dict[str, str], str | None, list[str]]:
    data = path.read_bytes()
    warnings: list[str] = []

    for encoding in ("gb18030", "gbk", "utf-8-sig", "utf-8"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "$BEGIN CONTENT OF PRJ" in text:
            return _parse_text_prj(text), _parse_prj_notes(text), encoding, warnings

    warnings.append("Unsupported or binary .prj format; falling back to filename-only metadata.")
    return [], {}, None, warnings


def _parse_prj_notes(text: str) -> dict[str, str]:
    notes: dict[str, str] = {}
    blocks = re.findall(r"\$BEGIN_ONE_NOTE\r*\n(.*?)\r*\n\$END_ONE_NOTE", text, flags=re.S)
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        key = lines[0]
        value = "\n".join(lines[1:]).strip()
        if value:
            notes[key] = value
        elif key not in notes:
            notes[key] = ""
    return notes


def _parse_text_prj(text: str) -> list[PrjEntry]:
    start = text.find("$BEGIN CONTENT OF PRJ")
    end = text.find("$END CONTENT OF PRJ")
    if start == -1 or end == -1 or end <= start:
        return []

    content = text[start:end]
    current_category: str | None = None
    entries: list[PrjEntry] = []
    order = 0
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":"):
            current_category = line[:-1].strip() or None
            continue
        match = _DWG_LINE.match(line)
        if not match:
            continue
        order += 1
        filename = f"{match.group('page')} {match.group('title')}.dwg"
        entries.append(
            PrjEntry(
                filename=filename,
                page_no=match.group("page"),
                title=match.group("title"),
                category=current_category,
                order=order,
            )
        )
    return entries


def parse_terminal_xml(path: Path) -> list[TerminalStrip]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    device = root.find(".//DEVICEITEM")
    if device is None:
        return []

    strips: list[TerminalStrip] = []
    for item in device.findall("DZBNAMEITEM"):
        try:
            length = float(item.attrib.get("DzbLength", "0") or 0)
        except ValueError:
            length = 0.0
        strips.append(
            TerminalStrip(
                style=item.attrib.get("DzbStyle", ""),
                name=item.attrib.get("DzbName", ""),
                length=length,
            )
        )
    return strips


def extract_device_name(path: Path) -> str | None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    device = root.find(".//DEVICEITEM")
    if device is None:
        return None
    return device.attrib.get("DeviceName") or None
