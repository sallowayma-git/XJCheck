from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "",
        "skip_files": ["封面", "目录", "屏面布置", "标牌"],
        "skip_globs": ["*~1.DWG", "*.bak", "*.lck"],
    },
    "ingest": {
        "dwg_reader": "odafc",
        "odafc_path": r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe",
        "convert_version": "R2018",
        "audit_before_load": True,
        "ascii_stage_dir": ".cache/odafc_stage",
    },
    "layout": {
        "page_no_source_priority": ["prj", "title_block", "filename", "manual"],
        "audit_area": {
            "mode": "auto",
            "manual_bbox": None,
            "bottom_trim_ratio": 0.16,
            "side_trim_ratio": 0.02,
        },
        "title_block": {
            "mode": "auto",
            "manual_bbox": None,
            "width_ratio": 0.28,
            "height_ratio": 0.22,
        },
    },
    "geometry": {
        "horizontal_angle_tolerance_deg": 2.0,
        "min_wire_length": 12.0,
        "line_y_tolerance": 1.8,
        "line_gap_tolerance": 4.0,
        "endpoint_search_radius_x": 18.0,
        "endpoint_search_radius_y": 7.0,
    },
    "text": {
        "numeric_pattern": r"^[0-9]+$",
        "allow_suffix": False,
        "min_text_height": 1.0,
        "max_text_height": 8.0,
        "top_k_per_side": 3,
    },
    "confidence": {
        "high_threshold": 0.92,
        "review_threshold": 0.75,
    },
    "rules": {
        "enable": [
            "R-PAIR-MISSING-SIDE",
            "R-PAIR-LOW-CONFIDENCE",
            "R-DUPLICATE-SAME-LINE",
            "R-CROSS-PAGE-CONFLICT",
            "R-ONE-TO-MANY",
            "R-MANY-TO-ONE",
            "R-MISSING-RECIPROCAL",
            "R-DUPLICATE-PAIR",
        ],
        "reciprocal_required": False,
    },
    "report": {
        "include_low_confidence_pairs": True,
        "include_candidate_details": True,
        "export_formats": ["xlsx", "html", "md"],
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    if config_path is None:
        return deepcopy(DEFAULT_CONFIG)

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Config root must be a mapping.")
    return _deep_merge(DEFAULT_CONFIG, loaded)


def write_default_config(output: Path, *, force: bool = False) -> Path:
    if output.exists() and not force:
        raise FileExistsError(f"Refusing to overwrite existing file: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(DEFAULT_CONFIG, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return output
