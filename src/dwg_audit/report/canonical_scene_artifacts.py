from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd


SUMMARY_SCHEMA_VERSION = "canonical-scene-summary-v1"
SCENE_SCHEMA_VERSION = "canonical-scene-v1"

_RECORD_COLUMNS = (
    "record_id",
    "file_id",
    "sheet_id",
    "filename",
    "source_space",
    "layout_name",
    "source_handle",
    "source_entity_type",
    "source_layer",
    "parent_handle",
    "definition_name",
    "nested_block_path",
    "instance_index",
    "primitive_kind",
    "source_status",
    "local_geometry",
    "world_geometry",
    "local_transform",
    "world_transform",
    "topology_state",
    "topology_union_eligible",
)
_VIEW_COLUMNS = (
    "record_id",
    "file_id",
    "sheet_id",
    "filename",
    "source_space",
    "layout_name",
    "source_handle",
    "source_entity_type",
    "source_layer",
    "center",
    "width",
    "height",
    "view_center",
    "view_height",
    "view_direction",
    "view_target",
    "twist_angle_deg",
    "viewport_id",
    "topology_state",
    "topology_union_eligible",
)
_DIAGNOSTIC_COLUMNS = (
    "file_id",
    "sheet_id",
    "filename",
    "severity",
    "code",
    "message",
    "source_space",
    "layout_name",
    "handle",
    "entity_type",
    "block_name",
    "nested_block_path",
    "details",
)
_SOURCE_COLUMNS = (
    "file_id",
    "sheet_id",
    "filename",
    "block_name",
    "raw_path",
    "reference_handle",
    "layout_name",
    "nested_block_path",
    "reason",
)


def write_canonical_scene_artifacts(
    scenes: Iterable[Mapping[str, Any]],
    findings_dir: Path,
    *,
    project_id: str,
) -> dict[str, Any]:
    material = [dict(scene) for scene in scenes]
    findings_dir = Path(findings_dir)
    scene_dir = findings_dir / "canonical_scene"
    scene_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    views: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    unresolved_sources: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    diagnostic_code_counts: Counter[str] = Counter()
    diagnostic_severity_counts: Counter[str] = Counter()
    source_entity_counts: Counter[str] = Counter()
    source_space_counts: Counter[str] = Counter()
    invalid_scene_count = 0
    layout_count = 0

    for index, scene in enumerate(material):
        file_id = str(scene.get("file_id") or scene.get("source_file_id") or f"FILE{index + 1}")
        sheet_id = _nullable_text(scene.get("sheet_id"))
        filename = _nullable_text(scene.get("filename"))
        complete = bool(scene.get("complete", False))
        status_counts["COMPLETE" if complete else "INCOMPLETE"] += 1
        if (
            scene.get("schema_version") != SCENE_SCHEMA_VERSION
            or scene.get("shadow_only") is not True
        ):
            invalid_scene_count += 1
        layouts = scene.get("layouts")
        if isinstance(layouts, list):
            layout_count += len(layouts)

        entity_rows = scene.get("entities")
        if not isinstance(entity_rows, list):
            entity_rows = scene.get("records")
        entity_rows = entity_rows if isinstance(entity_rows, list) else []
        for row in entity_rows:
            if not isinstance(row, Mapping):
                continue
            record = {**dict(row), "sheet_id": sheet_id, "filename": filename}
            records.append(record)
            source_entity_counts[str(record.get("source_entity_type") or "UNKNOWN")] += 1
            source_space_counts[str(record.get("source_space") or "UNKNOWN")] += 1

        view_rows = scene.get("layout_views")
        if not isinstance(view_rows, list):
            view_rows = scene.get("views")
        view_rows = view_rows if isinstance(view_rows, list) else []
        for row in view_rows:
            if isinstance(row, Mapping):
                views.append({**dict(row), "sheet_id": sheet_id, "filename": filename})

        for row in scene.get("diagnostics", []) or []:
            if not isinstance(row, Mapping):
                continue
            diagnostic = {
                "file_id": file_id,
                "sheet_id": sheet_id,
                "filename": filename,
                **dict(row),
            }
            diagnostics.append(diagnostic)
            diagnostic_code_counts[str(diagnostic.get("code") or "UNKNOWN")] += 1
            diagnostic_severity_counts[
                str(diagnostic.get("severity") or "UNKNOWN").upper()
            ] += 1

        for row in scene.get("unresolved_sources", []) or []:
            if isinstance(row, Mapping):
                unresolved_sources.append(
                    {
                        "file_id": file_id,
                        "sheet_id": sheet_id,
                        "filename": filename,
                        **dict(row),
                    }
                )

        (scene_dir / f"{_slug(file_id)}.json").write_text(
            json.dumps(scene, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    _frame(records, _RECORD_COLUMNS).to_parquet(
        findings_dir / "canonical_scene_records.parquet", index=False
    )
    _frame(views, _VIEW_COLUMNS).to_parquet(
        findings_dir / "canonical_scene_views.parquet", index=False
    )
    _frame(diagnostics, _DIAGNOSTIC_COLUMNS).to_parquet(
        findings_dir / "canonical_scene_diagnostics.parquet", index=False
    )
    _frame(unresolved_sources, _SOURCE_COLUMNS).to_parquet(
        findings_dir / "canonical_scene_unresolved_sources.parquet", index=False
    )

    union_eligible_record_count = sum(
        bool(row.get("topology_union_eligible")) for row in records
    ) + sum(bool(row.get("topology_union_eligible")) for row in views)
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "scene_schema_version": SCENE_SCHEMA_VERSION,
        "project_id": project_id,
        "scene_count": len(material),
        "status_counts": dict(sorted(status_counts.items())),
        "invalid_scene_count": invalid_scene_count,
        "layout_count": layout_count,
        "record_count": len(records),
        "view_count": len(views),
        "diagnostic_count": len(diagnostics),
        "diagnostic_code_counts": dict(sorted(diagnostic_code_counts.items())),
        "diagnostic_severity_counts": dict(
            sorted(diagnostic_severity_counts.items())
        ),
        "unresolved_source_count": len(unresolved_sources),
        "source_entity_counts": dict(sorted(source_entity_counts.items())),
        "source_space_counts": dict(sorted(source_space_counts.items())),
        "topology_union_eligible_count": union_eligible_record_count,
        "shadow_contract_valid": (
            invalid_scene_count == 0 and union_eligible_record_count == 0
        ),
    }
    (findings_dir / "canonical_scene_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def _frame(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> pd.DataFrame:
    serialized: list[dict[str, Any]] = []
    for item in rows:
        row: dict[str, Any] = {}
        for key, value in item.items():
            row[str(key)] = (
                json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (dict, list, tuple))
                else value
            )
        serialized.append(row)
    ordered = list(columns)
    extra = sorted({key for row in serialized for key in row}.difference(ordered))
    return pd.DataFrame(serialized, columns=[*ordered, *extra])


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return slug or "scene"


def _nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "SCENE_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "write_canonical_scene_artifacts",
]
