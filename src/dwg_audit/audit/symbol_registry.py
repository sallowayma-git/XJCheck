from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import pandas as pd


SYMBOL_SCHEMA_VERSION = "symbol-definition-v1"
SYMBOL_FINGERPRINT_VERSION = "local-geometry-fingerprint-v1"

_BACKLOG_COLUMNS = [
    "corpus_rank",
    "definition_fingerprint",
    "definition_names",
    "total_instance_count",
    "project_coverage",
    "project_ids",
    "priority_score",
    "registry_status",
    "critical_issue_eligible",
    "reason_code",
]


def definition_fingerprint_from_children(
    children: pd.DataFrame | list[Mapping[str, Any]],
) -> str:
    """Hash local child geometry only; path/handle/world/transform translation excluded.

    Empty children yield a stable fingerprint of the empty signature list.
    """
    if isinstance(children, pd.DataFrame):
        if children.empty:
            signatures: list[str] = []
        else:
            signatures = sorted(
                {_child_signature(row) for _, row in children.iterrows()}
            )
    elif not children:
        signatures = []
    else:
        signatures = sorted(
            {_child_signature(pd.Series(dict(row))) for row in children}
        )
    return hashlib.sha256(
        json.dumps(signatures, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def build_project_symbol_inventory(
    primitive_segments: pd.DataFrame,
    *,
    project_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if primitive_segments.empty:
        empty = pd.DataFrame()
        return empty, empty.copy(), empty.copy(), _summary([], [], [])

    inserts = primitive_segments.loc[
        (primitive_segments["primitive_kind"] == "INSERT")
        & primitive_segments["definition_name"].notna()
    ]
    children = primitive_segments.loc[
        (primitive_segments["primitive_kind"] != "INSERT")
        & primitive_segments["definition_name"].notna()
    ]
    definition_names = sorted(
        {
            str(value)
            for value in inserts["definition_name"]
            if str(value).strip()
        }
    )
    definitions: list[dict[str, Any]] = []
    instances: list[dict[str, Any]] = []
    unknown_queue: list[dict[str, Any]] = []
    fingerprint_by_name: dict[str, str] = {}
    definition_id_by_name: dict[str, str] = {}
    for name in definition_names:
        definition_children = children.loc[children["definition_name"] == name]
        fingerprint = definition_fingerprint_from_children(definition_children)
        fingerprint_by_name[name] = fingerprint
        definition_id = _symbol_definition_id(name, fingerprint)
        definition_id_by_name[name] = definition_id
        definition_instances = inserts.loc[inserts["definition_name"] == name]
        slot_types = sorted(
            {
                str(value)
                for value in definition_children.loc[
                    definition_children["source_entity_type"].isin(
                        ["ATTRIB", "ATTDEF", "TEXT", "MTEXT"]
                    ),
                    "source_entity_type",
                ]
            }
        )
        transforms = sorted(
            {
                str(value)
                for value in definition_instances["transform_json"]
            }
        )
        instance_count = len(definition_instances)
        sheet_count = int(definition_instances["sheet_id"].nunique())
        signatures = sorted(
            {
                _child_signature(row)
                for _, row in definition_children.iterrows()
            }
        )
        definitions.append(
            {
                "symbol_definition_id": definition_id,
                "schema_version": SYMBOL_SCHEMA_VERSION,
                "fingerprint_version": SYMBOL_FINGERPRINT_VERSION,
                "project_id": project_id,
                "definition_name": name,
                "definition_fingerprint": fingerprint,
                "instance_count": instance_count,
                "sheet_count": sheet_count,
                "local_geometry_signature_count": len(signatures),
                "transform_variant_count": len(transforms),
                "text_slot_entity_types": slot_types,
                "registry_status": "UNKNOWN",
                "symbol_family": None,
                "internal_connectivity_state": "UNKNOWN",
                "declared_port_count": 0,
                "critical_issue_eligible": False,
            }
        )
        unknown_queue.append(
            {
                "unknown_symbol_id": f"US1-{project_id}-{definition_id.removeprefix('SD1-')}",
                "project_id": project_id,
                "symbol_definition_id": definition_id,
                "definition_name": name,
                "definition_fingerprint": fingerprint,
                "instance_count": instance_count,
                "project_coverage": 1,
                "audit_impact_proxy": instance_count,
                "priority_score": instance_count,
                "reason_code": "UNREGISTERED_DEFINITION_REVIEW_REQUIRED",
                "critical_issue_eligible": False,
                "status": "OPEN",
            }
        )

    for _, insert in inserts.iterrows():
        name = str(insert["definition_name"])
        fingerprint = fingerprint_by_name[name]
        instances.append(
            {
                "symbol_instance_id": f"SI1-{project_id}-{insert['primitive_id']}",
                "project_id": project_id,
                "sheet_id": str(insert["sheet_id"]),
                "file_id": str(insert["file_id"]),
                "entity_handle": str(insert["entity_handle"]),
                "definition_name": name,
                "definition_fingerprint": fingerprint,
                "nested_path": str(insert["nested_path"]),
                "transform_json": str(insert["transform_json"]),
                "registry_status": "UNKNOWN",
                "symbol_family": None,
            }
        )
    unknown_queue.sort(
        key=lambda row: (-int(row["priority_score"]), row["definition_name"])
    )
    for rank, row in enumerate(unknown_queue, start=1):
        row["project_rank"] = rank

    return (
        pd.DataFrame(definitions),
        pd.DataFrame(instances),
        pd.DataFrame(unknown_queue),
        _summary(definitions, instances, unknown_queue),
    )


def rank_symbol_annotation_backlog(
    definition_frames: list[pd.DataFrame],
) -> pd.DataFrame:
    """Rank geometry families across projects for annotation backlog.

    Groups by definition_fingerprint (geometry family). Does not read labels
    or mark critical issues.
    """
    frames = [frame for frame in definition_frames if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=_BACKLOG_COLUMNS)

    combined = pd.concat(frames, ignore_index=True)
    # Definitions with no local geometry signatures are transparent INSERT
    # wrappers.  Their expanded descendants are inventoried independently, so
    # the wrapper itself has no port/connectivity question for a human to
    # answer.  Do not classify it as whole-symbol IGNORE: that would wrongly
    # suppress meaningful descendants through ancestor policy.
    if "local_geometry_signature_count" in combined.columns:
        signature_counts = pd.to_numeric(
            combined["local_geometry_signature_count"], errors="coerce"
        )
        combined = combined[signature_counts.isna() | signature_counts.gt(0)]
    if combined.empty:
        return pd.DataFrame(columns=_BACKLOG_COLUMNS)
    ranked_rows: list[dict[str, Any]] = []
    for fingerprint, group in combined.groupby("definition_fingerprint", sort=False):
        definition_names = sorted(
            {str(name) for name in group["definition_name"] if str(name).strip()}
        )
        project_ids = sorted(
            {str(pid) for pid in group["project_id"] if str(pid).strip()}
        )
        total_instance_count = int(group["instance_count"].sum())
        project_coverage = len(project_ids)
        ranked_rows.append(
            {
                "definition_fingerprint": str(fingerprint),
                "definition_names": definition_names,
                "total_instance_count": total_instance_count,
                "project_coverage": project_coverage,
                "project_ids": project_ids,
                "priority_score": total_instance_count * project_coverage,
                "registry_status": "UNKNOWN",
                "critical_issue_eligible": False,
                "reason_code": "UNREGISTERED_DEFINITION_REVIEW_REQUIRED",
            }
        )

    ranked_rows.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            -int(row["total_instance_count"]),
            str(row["definition_fingerprint"]),
        )
    )
    for rank, row in enumerate(ranked_rows, start=1):
        row["corpus_rank"] = rank

    return pd.DataFrame(ranked_rows)[_BACKLOG_COLUMNS]


def _symbol_definition_id(definition_name: str, fingerprint: str) -> str:
    digest = hashlib.sha256(
        f"{definition_name}\0{fingerprint}".encode("utf-8")
    ).hexdigest()[:32]
    return f"SD1-{digest}"


def _child_signature(row: pd.Series) -> str:
    return "|".join(
        [
            str(row.get("source_entity_type") or ""),
            str(row.get("primitive_kind") or ""),
            str(row.get("layer") or ""),
            str(row.get("linetype") or ""),
            str(row.get("local_geometry_json") or "{}"),
        ]
    )


def _summary(
    definitions: list[dict[str, Any]],
    instances: list[dict[str, Any]],
    unknown_queue: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "symbol-inventory-summary-v1",
        "definition_count": len(definitions),
        "instance_count": len(instances),
        "unknown_definition_count": len(unknown_queue),
        "registered_definition_count": 0,
        "unknown_critical_issue_eligible_count": sum(
            bool(row["critical_issue_eligible"]) for row in unknown_queue
        ),
    }
