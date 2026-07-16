"""Shadow-only symbol port placements from approved libraries.

Only REGISTERED symbols with HUMAN_CONFIRMED ports produce placements.
Outputs never authorize electrical union or critical issues by themselves.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolPort


SHADOW_SCHEMA_VERSION = "symbol-port-shadow-v1"
SUMMARY_SCHEMA_VERSION = "symbol-port-shadow-summary-v1"


@dataclass(frozen=True, slots=True)
class SymbolPortShadowPlacement:
    placement_id: str
    project_id: str | None
    sheet_id: str | None
    file_id: str | None
    symbol_instance_id: str | None
    definition_name: str | None
    definition_fingerprint: str
    symbol_family: str
    symbol_version: str
    port_id: str
    port_type: str
    local_position: tuple[float, float, float]
    outward_direction: tuple[float, float, float]
    world_position: tuple[float, float, float] | None
    world_outward_direction: tuple[float, float, float] | None
    transform_status: str
    registry_status: str
    annotation_status: str
    electrical_union_eligible: bool
    critical_issue_eligible: bool
    authority: str
    evidence_codes: tuple[str, ...]
    source_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["local_position"] = list(self.local_position)
        value["outward_direction"] = list(self.outward_direction)
        value["world_position"] = (
            list(self.world_position) if self.world_position is not None else None
        )
        value["world_outward_direction"] = (
            list(self.world_outward_direction)
            if self.world_outward_direction is not None
            else None
        )
        value["evidence_codes"] = list(self.evidence_codes)
        value["source_ids"] = list(self.source_ids)
        return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if hasattr(value, "to_dict") and not isinstance(value, (str, bytes)):
        try:
            # pandas DataFrame
            if hasattr(value, "to_dict") and hasattr(value, "iterrows"):
                return [dict(row) for _, row in value.iterrows()]
        except Exception:
            pass
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        rows: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, Mapping):
                rows.append(dict(item))
        return rows
    return []


def _parse_transform(raw: Any) -> tuple[list[list[float]] | None, str]:
    if raw is None or raw == "":
        return None, "TRANSFORM_MISSING"
    payload = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None, "TRANSFORM_JSON_INVALID"
    matrix = None
    if isinstance(payload, Mapping):
        chain = payload.get("chain")
        if isinstance(chain, Sequence) and chain:
            first = chain[0]
            if isinstance(first, Mapping) and first.get("matrix44") is not None:
                matrix = first.get("matrix44")
            elif isinstance(first, Mapping) and first.get("matrix") is not None:
                matrix = first.get("matrix")
        elif payload.get("matrix44") is not None:
            matrix = payload.get("matrix44")
    elif isinstance(payload, Sequence):
        matrix = payload
    if matrix is None:
        return None, "TRANSFORM_MATRIX_MISSING"
    try:
        rows = [[float(cell) for cell in row] for row in matrix]
    except Exception:
        return None, "TRANSFORM_MATRIX_INVALID"
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        return None, "TRANSFORM_MATRIX_SHAPE"
    return rows, "TRANSFORM_OK"


def _matmul_point(matrix: list[list[float]], point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    # matrix44 stored as rows; translation is last row in inventory dumps
    # (ezdxf Matrix44.rows() layout: r0..r2 linear, r3 translation).
    if abs(matrix[3][3] - 1.0) <= 1e-9 and abs(matrix[0][3]) <= 1e-9 and abs(matrix[1][3]) <= 1e-9:
        # row-major with translation in last row
        wx = matrix[0][0] * x + matrix[1][0] * y + matrix[2][0] * z + matrix[3][0]
        wy = matrix[0][1] * x + matrix[1][1] * y + matrix[2][1] * z + matrix[3][1]
        wz = matrix[0][2] * x + matrix[1][2] * y + matrix[2][2] * z + matrix[3][2]
        return (wx, wy, wz)
    # column-vector style with translation in last column
    wx = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3]
    wy = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3]
    wz = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3]
    return (wx, wy, wz)


def _matmul_direction(
    matrix: list[list[float]], direction: tuple[float, float, float]
) -> tuple[float, float, float]:
    x, y, z = direction
    if abs(matrix[3][3] - 1.0) <= 1e-9 and abs(matrix[0][3]) <= 1e-9 and abs(matrix[1][3]) <= 1e-9:
        wx = matrix[0][0] * x + matrix[1][0] * y + matrix[2][0] * z
        wy = matrix[0][1] * x + matrix[1][1] * y + matrix[2][1] * z
        wz = matrix[0][2] * x + matrix[1][2] * y + matrix[2][2] * z
    else:
        wx = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z
        wy = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z
        wz = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z
    norm = math.sqrt(wx * wx + wy * wy + wz * wz)
    if norm <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (wx / norm, wy / norm, wz / norm)


def _eligible_ports(library: SymbolDependencyLibrary) -> list[tuple[Any, SymbolPort]]:
    rows: list[tuple[Any, SymbolPort]] = []
    for symbol in library.symbols:
        if symbol.registry_status is not RegistryStatus.REGISTERED:
            continue
        if symbol.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED:
            continue
        for port in symbol.ports:
            if port.annotation_status is not AnnotationStatus.HUMAN_CONFIRMED:
                continue
            rows.append((symbol, port))
    return rows


def build_symbol_port_shadow_placements(
    library: SymbolDependencyLibrary | Mapping[str, Any] | None,
    instances: Any,
    *,
    project_id: str | None = None,
) -> list[SymbolPortShadowPlacement]:
    """Project REGISTERED+confirmed ports onto inventory instances (shadow only)."""

    if library is None:
        return []
    if not isinstance(library, SymbolDependencyLibrary):
        return []

    by_fingerprint: dict[str, list[tuple[Any, SymbolPort]]] = {}
    by_name: dict[str, list[tuple[Any, SymbolPort]]] = {}
    for symbol, port in _eligible_ports(library):
        by_fingerprint.setdefault(symbol.identity.fingerprint.casefold(), []).append(
            (symbol, port)
        )
        for alias in symbol.aliases:
            if alias.namespace.casefold() == "definition_name":
                by_name.setdefault(alias.value.casefold(), []).append((symbol, port))

    placements: list[SymbolPortShadowPlacement] = []
    for index, instance in enumerate(_records(instances)):
        fingerprint = _text(instance.get("definition_fingerprint"))
        definition_name = _text(instance.get("definition_name"))
        candidates = []
        if fingerprint:
            candidates = list(by_fingerprint.get(fingerprint.casefold(), []))
        if not candidates and definition_name:
            candidates = list(by_name.get(definition_name.casefold(), []))
        if not candidates:
            continue
        matrix, transform_status = _parse_transform(instance.get("transform_json"))
        instance_id = _text(instance.get("symbol_instance_id")) or f"instance-{index}"
        for symbol, port in candidates:
            world_position = None
            world_direction = None
            evidence = ["SHADOW_PORT_FROM_REGISTERED_LIBRARY"]
            if matrix is not None and transform_status == "TRANSFORM_OK":
                world_position = _matmul_point(matrix, port.local_position)
                world_direction = _matmul_direction(matrix, port.outward_direction)
                evidence.append("WORLD_TRANSFORM_APPLIED")
            else:
                evidence.append(transform_status)
            placements.append(
                SymbolPortShadowPlacement(
                    placement_id=f"SPP:{instance_id}:{port.port_id}",
                    project_id=_text(instance.get("project_id")) or project_id,
                    sheet_id=_text(instance.get("sheet_id")),
                    file_id=_text(instance.get("file_id")),
                    symbol_instance_id=instance_id,
                    definition_name=definition_name,
                    definition_fingerprint=symbol.identity.fingerprint,
                    symbol_family=symbol.identity.family,
                    symbol_version=symbol.identity.version,
                    port_id=port.port_id,
                    port_type=str(
                        port.port_type.value
                        if hasattr(port.port_type, "value")
                        else port.port_type
                    ),
                    local_position=tuple(float(v) for v in port.local_position),  # type: ignore[arg-type]
                    outward_direction=tuple(float(v) for v in port.outward_direction),  # type: ignore[arg-type]
                    world_position=world_position,
                    world_outward_direction=world_direction,
                    transform_status=transform_status,
                    registry_status=symbol.registry_status.value,
                    annotation_status=port.annotation_status.value,
                    electrical_union_eligible=False,
                    critical_issue_eligible=False,
                    authority="SHADOW_ONLY",
                    evidence_codes=tuple(evidence),
                    source_ids=tuple(port.source_ids),
                )
            )
    placements.sort(
        key=lambda item: (
            item.definition_fingerprint,
            item.symbol_instance_id or "",
            item.port_id,
        )
    )
    return placements


def summarize_symbol_port_shadow(
    placements: Sequence[SymbolPortShadowPlacement],
    *,
    project_id: str | None = None,
    library: SymbolDependencyLibrary | None = None,
) -> dict[str, Any]:
    transform_counts = Counter(item.transform_status for item in placements)
    port_type_counts = Counter(item.port_type for item in placements)
    eligible_symbol_count = 0
    eligible_port_count = 0
    if library is not None:
        pairs = _eligible_ports(library)
        eligible_symbol_count = len({symbol.identity.key for symbol, _ in pairs})
        eligible_port_count = len(pairs)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "shadow_schema_version": SHADOW_SCHEMA_VERSION,
        "project_id": project_id,
        "placement_count": len(placements),
        "eligible_registered_symbol_count": eligible_symbol_count,
        "eligible_confirmed_port_count": eligible_port_count,
        "electrical_union_eligible_count": sum(
            1 for item in placements if item.electrical_union_eligible
        ),
        "critical_issue_eligible_count": sum(
            1 for item in placements if item.critical_issue_eligible
        ),
        "transform_status_counts": dict(sorted(transform_counts.items())),
        "port_type_counts": dict(sorted(port_type_counts.items())),
        "authority": "SHADOW_ONLY",
        "shadow_only": True,
        "primary_engine_unchanged": True,
    }


def write_symbol_port_shadow_artifacts(
    placements: Sequence[SymbolPortShadowPlacement],
    output_dir: str | Path,
    *,
    project_id: str | None = None,
    library: SymbolDependencyLibrary | None = None,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = summarize_symbol_port_shadow(
        placements, project_id=project_id, library=library
    )
    placements_path = output / "symbol_port_shadow_placements.json"
    summary_path = output / "symbol_port_shadow_summary.json"
    placements_path.write_text(
        json.dumps(
            {
                "schema_version": SHADOW_SCHEMA_VERSION,
                "project_id": project_id,
                "placements": [item.to_dict() for item in placements],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"placements": placements_path, "summary": summary_path}


__all__ = [
    "SHADOW_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "SymbolPortShadowPlacement",
    "build_symbol_port_shadow_placements",
    "summarize_symbol_port_shadow",
    "write_symbol_port_shadow_artifacts",
]
