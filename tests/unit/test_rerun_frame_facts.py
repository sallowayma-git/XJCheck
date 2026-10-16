from __future__ import annotations

import pandas as pd

from dwg_audit.report.rerun import _gap_facts


def _line(x1, y1, x2, y2):
    return {
        "file_id": "F1", "sheet_id": "S1", "source_block_name": None,
        "start_x": x1, "start_y": y1, "end_x": x2, "end_y": y2,
    }


def test_gap_facts_only_exposes_closed_captioned_frames_and_keeps_connect_dots(tmp_path):
    findings = tmp_path / "findings"
    findings.mkdir()
    for name in ("lines", "texts", "sw_connect_dots", "sw_ports"):
        (findings / f"{name}.parquet").touch()

    lines = [
        _line(0, 0, 40, 0), _line(0, 30, 40, 30), _line(0, 0, 0, 30), _line(40, 0, 40, 30),
        _line(60, 0, 100, 0), _line(60, 30, 100, 30), _line(60, 0, 60, 30),
        # A closed rectangle inside a block is excluded from device/component frame facts.
        {**_line(110, 0, 150, 0), "source_block_name": "FRAME_BLOCK"},
    ]
    texts = [{
        "file_id": "F1", "sheet_id": "S1", "normalized_text": "From BCU", "text": "From BCU",
        "bbox_min_x": 10, "bbox_min_y": 31, "bbox_max_x": 25, "bbox_max_y": 33,
    }]
    dots = [{"file_id": "F1", "sheet_id": "S1", "x": 40, "y": 15}]
    ports = [{"file_id": "F1", "sheet_id": "S1", "record_id": "P1", "label": '{"value":"From BCU"}'}]
    facts = _gap_facts(tmp_path, {
        "lines": pd.DataFrame(lines),
        "texts": pd.DataFrame(texts),
        "sw_connect_dots": pd.DataFrame(dots),
        "sw_ports": pd.DataFrame(ports),
    }, [])

    assert facts.frame_boundaries == {
        ("F1", "S1"): [{"rect": (0.0, 0.0, 40.0, 30.0), "label": "From BCU", "captions": ["From BCU"]}],
    }
    assert facts.frame_connect_dots == {("F1", "S1"): [(40.0, 15.0)]}
    assert facts.frame_port_labels == {("F1", "S1"): {"P1": "From BCU"}}
