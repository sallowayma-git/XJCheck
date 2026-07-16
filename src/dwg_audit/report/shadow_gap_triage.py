"""Shadow geometry gap triage by electrical relevance.

The corpus currently retains ARC/CIRCLE/ELLIPSE in the shadow primitive layer but
not HATCH/SPLINE/POINT/ACAD_TABLE/SOLID/OLE2FRAME.  This module classifies those
gaps without authorizing new geometry adapters.  Classification is evidence for
review prioritization only.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


SHADOW_GAP_SCHEMA_VERSION = "shadow-gap-triage-v1"
SHADOW_GAP_SUMMARY_SCHEMA_VERSION = "shadow-gap-triage-summary-v1"

# Relevance classes are deliberately coarse and fail closed to review.
_RELEVANCE_POLICY: dict[str, dict[str, Any]] = {
    "HATCH": {
        "relevance": "LIKELY_DECORATIVE",
        "adapter_authorized": False,
        "reason_codes": [
            "FILL_REGION_COMMON",
            "RARELY_CARRIES_ELECTRICAL_CONNECTIVITY",
        ],
        "recommended_action": "KEEP_SHADOW_UNSUPPORTED_UNTIL_PROVEN_ELECTRICAL",
    },
    "SPLINE": {
        "relevance": "POSSIBLE_ELECTRICAL_GEOMETRY",
        "adapter_authorized": False,
        "reason_codes": [
            "CURVE_MAY_REPRESENT_WIRE_OR_ANNOTATION",
            "NEEDS_CORPUS_SAMPLE_REVIEW",
        ],
        "recommended_action": "REVIEW_SAMPLE_SHEETS_BEFORE_ADAPTER",
    },
    "POINT": {
        "relevance": "POSSIBLE_MARKER",
        "adapter_authorized": False,
        "reason_codes": [
            "MAY_BE_INSERTION_OR_ALIGNMENT_MARKER",
            "NOT_SUFFICIENT_FOR_CONNECTIVITY",
        ],
        "recommended_action": "REVIEW_AS_MARKER_CANDIDATE_ONLY",
    },
    "ACAD_TABLE": {
        "relevance": "SEMANTIC_TABLE_OBJECT",
        "adapter_authorized": False,
        "reason_codes": [
            "STRUCTURED_TABLE_OBJECT",
            "SHOULD_ROUTE_THROUGH_TABLE_MAPPING_NOT_WIRE_GEOMETRY",
        ],
        "recommended_action": "DEFER_TO_TABLE_STRUCTURE_PIPELINE",
    },
    "SOLID": {
        "relevance": "LIKELY_DECORATIVE",
        "adapter_authorized": False,
        "reason_codes": [
            "FILLED_POLYGON_COMMON_FOR_SYMBOL_BODY",
            "CONNECTIVITY_SHOULD_USE_SYMBOL_PORTS",
        ],
        "recommended_action": "KEEP_SHADOW_UNSUPPORTED_USE_SYMBOL_PORTS",
    },
    "OLE2FRAME": {
        "relevance": "EXTERNAL_EMBEDDED_CONTENT",
        "adapter_authorized": False,
        "reason_codes": [
            "EMBEDDED_OLE_OBJECT",
            "NOT_NATIVE_DXF_GEOMETRY",
        ],
        "recommended_action": "FAIL_CLOSED_NO_NATIVE_GEOMETRY_ADAPTER",
    },
}

_DEFAULT_POLICY = {
    "relevance": "UNKNOWN",
    "adapter_authorized": False,
    "reason_codes": ["UNCLASSIFIED_SHADOW_GAP"],
    "recommended_action": "REVIEW_BEFORE_ANY_ADAPTER",
}


def classify_shadow_entity_type(entity_type: str) -> dict[str, Any]:
    key = str(entity_type or "").strip().upper()
    policy = dict(_RELEVANCE_POLICY.get(key, _DEFAULT_POLICY))
    policy["entity_type"] = key or "UNKNOWN"
    policy["adapter_authorized"] = False
    return policy


def build_shadow_gap_triage(
    census_files: Sequence[Mapping[str, Any]],
    *,
    project_id: str,
) -> dict[str, Any]:
    """Aggregate shadow-unsupported entity counts into a review triage artifact."""

    totals: Counter[str] = Counter()
    file_hits: Counter[str] = Counter()
    for item in census_files:
        if not isinstance(item, Mapping):
            continue
        counts = item.get("shadow_unsupported_entity_counts") or {}
        if not isinstance(counts, Mapping):
            continue
        seen_types: set[str] = set()
        for entity_type, raw_count in counts.items():
            key = str(entity_type or "").strip().upper() or "UNKNOWN"
            try:
                count = int(raw_count)
            except (TypeError, ValueError):
                count = 0
            if count <= 0:
                continue
            totals[key] += count
            seen_types.add(key)
        for key in seen_types:
            file_hits[key] += 1

    rows: list[dict[str, Any]] = []
    for entity_type, count in sorted(
        totals.items(),
        key=lambda pair: (-pair[1], pair[0]),
    ):
        policy = classify_shadow_entity_type(entity_type)
        rows.append(
            {
                "entity_type": entity_type,
                "entity_count": count,
                "file_count": int(file_hits.get(entity_type, 0)),
                "relevance": policy["relevance"],
                "adapter_authorized": False,
                "reason_codes": list(policy["reason_codes"]),
                "recommended_action": policy["recommended_action"],
            }
        )

    authorized = [row for row in rows if row["adapter_authorized"]]
    summary = {
        "schema_version": SHADOW_GAP_SUMMARY_SCHEMA_VERSION,
        "project_id": str(project_id or "UNKNOWN_PROJECT"),
        "entity_type_count": len(rows),
        "total_shadow_unsupported_entities": int(sum(totals.values())),
        "adapter_authorized_count": len(authorized),
        "any_adapter_authorized": bool(authorized),
        "shadow_only": True,
        "relevance_counts": dict(
            sorted(Counter(row["relevance"] for row in rows).items())
        ),
    }
    return {
        "schema_version": SHADOW_GAP_SCHEMA_VERSION,
        "project_id": str(project_id or "UNKNOWN_PROJECT"),
        "rows": rows,
        "summary": summary,
    }


__all__ = [
    "SHADOW_GAP_SCHEMA_VERSION",
    "SHADOW_GAP_SUMMARY_SCHEMA_VERSION",
    "build_shadow_gap_triage",
    "classify_shadow_entity_type",
]
