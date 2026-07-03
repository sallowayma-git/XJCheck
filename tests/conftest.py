from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_text_prj() -> str:
    return (
        "$BEGIN NOTE OF PRJ\r\n"
        "$BEGIN_ONE_NOTE\r\n"
        "设备名称\r\n"
        "示例工程\r\n"
        "$END_ONE_NOTE\r\n"
        "$END NOTE OF PRJ\r\n"
        "$BEGIN CONTENT OF PRJ\r\n"
        "封面/目录:\r\n"
        "01 封面.dwg<>\r\n"
        "二次原理图:\r\n"
        "04 交流回路图1.dwg<>\r\n"
        "$END CONTENT OF PRJ\r\n"
        "$EOF\r\n"
    )


@pytest.fixture
def sample_terminal_xml() -> str:
    return (
        '<?xml version="1.0"?>'
        '<SuperWORKS Version="2026,01,07,14,52,35">'
        '<DEVICEITEM DeviceName="示例项目.prj" Location="">'
        '<DZBNAMEITEM DzbStyle="左侧" DzbName="ZD" DzbLength="68.20"/>'
        '<DZBNAMEITEM DzbStyle="右侧" DzbName="1-21QD" DzbLength="545.60"/>'
        "</DEVICEITEM></SuperWORKS>"
    )


def write_project_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
