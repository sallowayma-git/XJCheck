from pathlib import Path

from dwg_audit.ingest.sidecar_parser import extract_device_name
from dwg_audit.ingest.sidecar_parser import parse_prj
from dwg_audit.ingest.sidecar_parser import parse_terminal_xml


def test_parse_text_prj(tmp_path: Path, sample_text_prj: str) -> None:
    prj = tmp_path / "demo.prj"
    prj.write_text(sample_text_prj, encoding="gbk")

    entries, notes, encoding, warnings = parse_prj(prj)

    assert encoding in {"gbk", "gb18030"}
    assert warnings == []
    assert notes["设备名称"] == "示例工程"
    assert [entry.filename for entry in entries] == ["01 封面.dwg", "04 交流回路图1.dwg"]
    assert entries[1].category == "二次原理图"


def test_parse_binary_prj_returns_warning(tmp_path: Path) -> None:
    prj = tmp_path / "binary.prj"
    prj.write_bytes(b"\xf3\x33\xca\xd0\x00\x01")

    entries, notes, encoding, warnings = parse_prj(prj)

    assert entries == []
    assert notes == {}
    assert encoding is None
    assert warnings


def test_parse_terminal_xml(tmp_path: Path, sample_terminal_xml: str) -> None:
    xml_path = tmp_path / "LdDzbInfo.xml"
    xml_path.write_text(sample_terminal_xml, encoding="utf-8")

    strips = parse_terminal_xml(xml_path)

    assert len(strips) == 2
    assert strips[0].name == "ZD"
    assert extract_device_name(xml_path) == "示例项目.prj"
