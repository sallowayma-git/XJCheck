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
        "audit_primary_categories": ["二次原理图"],
        "audit_secondary_categories": ["背板接线图", "元件接线图", "屏端子图", "屏面布置图", "封面/目录"],
        "audit_supplemental_categories": [],
        "audit_primary_title_keywords": ["回路", "信号", "保护", "出口", "操作", "开入", "控制"],
        "audit_secondary_title_keywords": ["背板", "端子图", "元件接线图", "接线图", "布置", "封面", "目录", "标牌"],
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
        "inline_numeric_bridge_gap": 13.0,
        "inline_numeric_bridge_y_tolerance": 4.0,
        "endpoint_search_radius_x": 18.0,
        "endpoint_search_radius_y": 7.0,
        "grid_band_y_tolerance": 5.0,
        "grid_min_band_count": 8,
    },
    "text": {
        "numeric_pattern": r"^[0-9]+$",
        "allow_suffix": False,
        "min_text_height": 1.0,
        "max_text_height": 8.0,
        "top_k_per_side": 3,
        "deprioritized_layers": ["DIM", "MARK"],
        "deprioritized_layer_penalty": 0.03,
        "single_char_penalty_layers": ["DIM", "MARK"],
        "single_char_penalty": 0.12,
        "single_char_reject_layers": [],
        "block_internal_numeric_penalty": -0.15,
    },
    "extract": {
        "insert_virtual_entity_categories": ["元件接线图"],
    },
    "page_category_overrides": {
        "二次原理图": {
            "text": {
                "single_char_reject_layers": ["DIM", "MARK"],
            }
        },
        "元件接线图": {
            "geometry": {
                "line_group_orientation": "auto",
            },
            "text": {
                "numeric_suffix_patterns": [
                    r"(?i)n(?P<value>\d{3,})$",
                    r"(?i)(?:CD|GD|ZK-?)(?P<value>\d{1,3})$",
                    r"(?i)HD(?P<value>\d{1,3})$",
                ],
                "derived_numeric_penalty": -0.18,
                "virtual_single_char_reject_blocks": ["FJL-25-2A_Mirror"],
            },
        },
        "屏端子图": {
            "geometry": {
                "endpoint_search_radius_x": 30.0,
            },
            "text": {
                "numeric_suffix_patterns": [r"(?i)n(?P<value>\d{3,})$"],
                "derived_numeric_penalty": -0.08,
                "terminal_strip_bypass_patterns": [
                    r"未定义.*回路图",
                    r"说明",
                    r"^上接",
                    r"^下接",
                    r"^(?:ZD|3-21UD|3-21ID|3-21GD|3-21QD)$",
                ],
                "terminal_strip_distance_x_weight": 0.2,
                "terminal_strip_distance_y_weight": 0.45,
            }
        }
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
            "R-SEMANTIC-MAPPING-CONFLICT",
            "R-TABLE-MAPPING-SOURCE-CONFLICT",
            "R-ONE-TO-MANY",
            "R-MANY-TO-ONE",
            "R-MISSING-RECIPROCAL",
            "R-DUPLICATE-PAIR",
            "R-SHEET-PAGE-MISMATCH",
        ],
        "reciprocal_required": False,
        "one_to_many_branch_left_values": [],
    },
    "report": {
        "include_low_confidence_pairs": True,
        "include_candidate_details": True,
        "export_formats": ["xlsx", "html", "md"],
    },
    "runtime": {
        "persist_page_findings_files": False,
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
