from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import ezdxf

from dwg_audit.domain.models import ProjectScanResult
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.extract.cad_extract import extract_cad_artifacts
from dwg_audit.utils.config import DEFAULT_CONFIG


class DummyLogger:
    def info(self, *_args, **_kwargs) -> None:
        return None


def _source_file(
    dxf_path: Path,
    *,
    filename: str = "demo.dwg",
    detected_page_no: str | None = "01",
    detected_from: str = "filename",
    sheet_title: str = "Demo",
) -> SourceFileRecord:
    return SourceFileRecord(
        file_id="F0001",
        path=str(dxf_path),
        filename=filename,
        ext=".dwg",
        sha256="abc",
        size_bytes=10,
        sheet_order=1,
        detected_page_no=detected_page_no,
        detected_from=detected_from,
        sheet_title=sheet_title,
        sheet_category="二次原理图",
        skip_reason=None,
        valid_dwg_header=True,
        conversion_status="converted",
        dxf_path=str(dxf_path),
    )


def _scan(
    *,
    filename: str = "demo.dwg",
    sheet_no: str | None = "01",
    sheet_title: str = "Demo",
    page_no_source: str = "filename",
) -> ProjectScanResult:
    return ProjectScanResult(
        manifest=SimpleNamespace(source_files=[]),
        pages=[
            SheetRecord(
                "S0001",
                "F0001",
                filename,
                1,
                sheet_no,
                sheet_title,
                "二次原理图",
                "primary",
                page_no_source,
                True,
            )
        ],
        terminal_strips=[],
        project_root="C:/demo",
    )


def test_extract_cad_artifacts_reads_insert_attrib_and_polylines(tmp_path: Path) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_text("101", dxfattribs={"insert": (10, 20), "height": 2.5})
    msp.add_lwpolyline([(0, 0), (30, 0), (30, 10)])
    poly = msp.add_polyline2d([(40, 0), (70, 0), (70, 10)])
    block = doc.blocks.new(name="TERM")
    block.add_attdef("TERM", insert=(0, 0), height=2.5)
    ref = msp.add_blockref("TERM", (80, 20))
    ref.add_auto_attribs({"TERM": "202"})
    dxf_path = tmp_path / "demo.dxf"
    doc.saveas(dxf_path)

    texts, lines, blocks, polylines, pages, warnings = extract_cad_artifacts(
        _scan(),
        [_source_file(dxf_path)],
        DEFAULT_CONFIG,
        DummyLogger(),
    )

    assert any(item.entity_type == "ATTRIB" and item.text == "202" and item.is_numeric_candidate for item in texts)
    assert any(item.entity_type == "TEXT" and item.text == "101" for item in texts)
    assert len(blocks) == 1
    assert '"TERM": "202"' in blocks[0].attributes_json
    assert len(polylines) == 2
    assert len(lines) == 4
    assert pages[0].frame_bbox is not None
    assert warnings == []
    assert any(item.source_entity_type == "POLYLINE" for item in lines)


def test_extract_cad_artifacts_respects_manual_layout_boxes(tmp_path: Path) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_text("101", dxfattribs={"insert": (10, 20), "height": 2.5})
    msp.add_line((0, 0), (100, 0))
    dxf_path = tmp_path / "demo.dxf"
    doc.saveas(dxf_path)

    config = {
        **DEFAULT_CONFIG,
        "layout": {
            **DEFAULT_CONFIG["layout"],
            "audit_area": {"mode": "manual", "manual_bbox": [10, 20, 300, 400], "bottom_trim_ratio": 0.16, "side_trim_ratio": 0.02},
            "title_block": {"mode": "manual", "manual_bbox": [250, 0, 400, 80], "width_ratio": 0.28, "height_ratio": 0.22},
        },
    }

    _, _, _, _, pages, _ = extract_cad_artifacts(
        _scan(),
        [_source_file(dxf_path)],
        config,
        DummyLogger(),
    )

    assert pages[0].audit_area_bbox == (10.0, 20.0, 300.0, 400.0)
    assert pages[0].title_block_bbox == (250.0, 0.0, 400.0, 80.0)


def test_extract_cad_artifacts_backfills_page_no_and_title_from_title_block_text(tmp_path: Path) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 60))
    msp.add_text("页号: 08", dxfattribs={"insert": (76, 4), "height": 2.5})
    msp.add_text("图名: 交流回路图1", dxfattribs={"insert": (74, 9), "height": 2.5})
    dxf_path = tmp_path / "demo.dxf"
    doc.saveas(dxf_path)

    _, _, _, _, pages, _ = extract_cad_artifacts(
        _scan(filename="demo.dwg", sheet_no=None, sheet_title="demo", page_no_source="unknown"),
        [_source_file(dxf_path, filename="demo.dwg", detected_page_no=None, detected_from="unknown", sheet_title="demo")],
        DEFAULT_CONFIG,
        DummyLogger(),
    )

    assert pages[0].sheet_no == "08"
    assert pages[0].page_no_source == "title_block"
    assert pages[0].sheet_title == "交流回路图1"
    assert "title_block" in pages[0].source_refs


def test_extract_cad_artifacts_keeps_filename_page_no_when_priority_prefers_filename(tmp_path: Path) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 60))
    msp.add_text("页号: 08", dxfattribs={"insert": (76, 4), "height": 2.5})
    msp.add_text("图名: 交流回路图1", dxfattribs={"insert": (74, 9), "height": 2.5})
    dxf_path = tmp_path / "demo.dxf"
    doc.saveas(dxf_path)

    config = {
        **DEFAULT_CONFIG,
        "layout": {
            **DEFAULT_CONFIG["layout"],
            "page_no_source_priority": ["prj", "filename", "title_block", "manual"],
        },
    }

    _, _, _, _, pages, _ = extract_cad_artifacts(
        _scan(filename="01 文件名标题.dwg", sheet_no="01", sheet_title="文件名标题", page_no_source="filename"),
        [_source_file(dxf_path, filename="01 文件名标题.dwg", detected_page_no="01", detected_from="filename", sheet_title="文件名标题")],
        config,
        DummyLogger(),
    )

    assert pages[0].sheet_no == "01"
    assert pages[0].page_no_source == "filename"
    assert any("kept existing source filename" in warning for warning in pages[0].warnings)
