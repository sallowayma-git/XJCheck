from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dwg_audit.report.canonical_scene_artifacts import write_canonical_scene_artifacts


def test_write_canonical_scene_artifacts_preserves_shadow_contract(
    tmp_path: Path,
) -> None:
    scene = {
        "schema_version": "canonical-scene-v1",
        "algorithm_version": "document-walker-v1",
        "file_id": "F0001",
        "sheet_id": "S0001",
        "filename": "04 回路图.dwg",
        "shadow_only": True,
        "complete": False,
        "layouts": ["Model", "Layout1"],
        "entities": [
            {
                "record_id": "CE0001",
                "file_id": "F0001",
                "source_space": "model",
                "layout_name": "Model",
                "source_handle": "10",
                "source_entity_type": "LINE",
                "source_layer": "WIRE",
                "parent_handle": None,
                "definition_name": None,
                "nested_block_path": [],
                "instance_index": None,
                "primitive_kind": "LINE",
                "source_status": "normalized",
                "local_geometry": {"kind": "line"},
                "world_geometry": {"kind": "line"},
                "local_transform": [],
                "world_transform": [],
                "topology_state": "UNKNOWN",
                "topology_union_eligible": False,
            }
        ],
        "layout_views": [
            {
                "record_id": "CV0001",
                "file_id": "F0001",
                "source_space": "paper",
                "layout_name": "Layout1",
                "source_handle": "20",
                "source_entity_type": "VIEWPORT",
                "source_layer": "0",
                "topology_state": "UNKNOWN",
                "topology_union_eligible": False,
            }
        ],
        "diagnostics": [
            {
                "severity": "error",
                "code": "XREF_UNRESOLVED_SOURCE",
                "message": "not loaded",
            }
        ],
        "unresolved_sources": [
            {
                "file_id": "F0001",
                "block_name": "COMMON",
                "raw_path": "common.dwg",
                "reference_handle": "30",
                "layout_name": "Model",
                "nested_block_path": [],
                "reason": "XREF_NOT_LOADED",
            }
        ],
        "source_entity_counts": {"LINE": 1},
        "source_space_counts": {"model": 1},
    }

    summary = write_canonical_scene_artifacts(
        [scene], tmp_path, project_id="P001"
    )

    assert summary["scene_count"] == 1
    assert summary["status_counts"] == {"INCOMPLETE": 1}
    assert summary["record_count"] == 1
    assert summary["view_count"] == 1
    assert summary["unresolved_source_count"] == 1
    assert summary["topology_union_eligible_count"] == 0
    assert summary["shadow_contract_valid"] is True
    assert (tmp_path / "canonical_scene" / "F0001.json").exists()
    assert len(pd.read_parquet(tmp_path / "canonical_scene_records.parquet")) == 1
    assert len(pd.read_parquet(tmp_path / "canonical_scene_views.parquet")) == 1
    assert len(pd.read_parquet(tmp_path / "canonical_scene_diagnostics.parquet")) == 1
    assert json.loads(
        (tmp_path / "canonical_scene_summary.json").read_text(encoding="utf-8")
    ) == summary


def test_empty_canonical_scene_artifacts_keep_stable_schemas(tmp_path: Path) -> None:
    summary = write_canonical_scene_artifacts([], tmp_path, project_id="EMPTY")

    assert summary["scene_count"] == 0
    assert summary["shadow_contract_valid"] is True
    assert pd.read_parquet(tmp_path / "canonical_scene_records.parquet").empty
    assert pd.read_parquet(tmp_path / "canonical_scene_views.parquet").empty
    assert pd.read_parquet(tmp_path / "canonical_scene_diagnostics.parquet").empty
    assert pd.read_parquet(
        tmp_path / "canonical_scene_unresolved_sources.parquet"
    ).empty
