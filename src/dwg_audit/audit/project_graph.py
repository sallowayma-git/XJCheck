"""Project graph builders: endpoint identities, cross-page candidates, summary.

Shadow-only Phase 120 builders. Never mutates topology or Pair/Issue outputs.
No POSSIBLE union; attachments are non-topology authority sources only.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

from dwg_audit.audit.audit_v2 import compare_legacy_new_relations

ALGORITHM_VERSION = "project-graph-v1"
ENDPOINT_IDENTITY_SCHEMA = "endpoint-identity-v1"
ENDPOINT_SCHEMA_VERSION = ENDPOINT_IDENTITY_SCHEMA  # alias

_DISTANCE_GATE = 2.0
_AMBIGUOUS_SCOPE_STATES = frozenset({"AMBIGUOUS", "CONFLICT"})

__all__ = [
    "ALGORITHM_VERSION",
    "ENDPOINT_IDENTITY_SCHEMA",
    "ENDPOINT_SCHEMA_VERSION",
    "build_endpoint_identities",
    "build_cross_page_endpoint_candidates",
    "build_project_graph",
    "compare_legacy_new_relations",
]


def _listish(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return list(value.tolist())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if hasattr(value, "to_dict"):
        if getattr(value, "empty", False):
            return []
        return list(value.to_dict("records"))
    return []


def _is_authoritative_attachment(att: dict[str, Any]) -> bool:
    if "constraint_authority" in att and att.get("constraint_authority") is not None:
        return att.get("constraint_authority") == "AUTHORITATIVE"
    selected = bool(att.get("selected"))
    scope = att.get("scope_state")
    if scope in _AMBIGUOUS_SCOPE_STATES:
        return False
    return selected


def _distance(
    ep_x: float | None,
    ep_y: float | None,
    att: dict[str, Any],
) -> float | None:
    tx, ty = att.get("target_x"), att.get("target_y")
    if tx is None or ty is None or ep_x is None or ep_y is None:
        return None
    return ((float(tx) - float(ep_x)) ** 2 + (float(ty) - float(ep_y)) ** 2) ** 0.5


def _pick_attachment(
    endpoint: dict[str, Any],
    attachments_same_sheet: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Pick best AUTHORITATIVE attachment for an open endpoint.

    Rules:
    - Must be same sheet + authoritative (caller filters sheet).
    - If has target_x/y and endpoint has coords: distance > 2.0 → reject.
    - Prefer target_line_id in source_line_ids.
    - Distance-only fallback is eligible when coords present and distance <= 2.0.
    - Without line match and without coords → not eligible.
    """
    source_lines = {str(x) for x in _listish(endpoint.get("source_line_ids"))}
    ep_coord = _listish(endpoint.get("coord"))
    ep_x = float(ep_coord[0]) if len(ep_coord) >= 2 else None
    ep_y = float(ep_coord[1]) if len(ep_coord) >= 2 else None

    candidates: list[tuple[dict[str, Any], bool, float | None]] = []
    for att in attachments_same_sheet:
        if not _is_authoritative_attachment(att):
            continue
        dist = _distance(ep_x, ep_y, att)
        # Distance gate: reject even with line match when beyond threshold
        if dist is not None and dist > _DISTANCE_GATE:
            continue
        line_id = att.get("target_line_id")
        line_match = line_id is not None and str(line_id) in source_lines
        # If no coords for distance and no line match, skip
        if dist is None and not line_match:
            continue
        candidates.append((att, line_match, dist))

    if not candidates:
        return None

    def sort_key(item: tuple[dict[str, Any], bool, float | None]) -> tuple:
        att, line_match, dist = item
        d = dist if dist is not None else float("inf")
        return (0 if line_match else 1, d, str(att.get("attachment_id") or ""))

    candidates.sort(key=sort_key)
    return candidates[0][0]


def _endpoint_id_open(project_id: str | None, sheet_id: str, node_id: str) -> str:
    digest = hashlib.sha256(
        f"{project_id or ''}|{sheet_id}|{node_id}".encode()
    ).hexdigest()[:16]
    return f"EP1-{digest}"


def _endpoint_id_token(project_id: str | None, sheet_id: str, token_id: str) -> str:
    digest = hashlib.sha256(
        f"{project_id or ''}|{sheet_id}|{token_id}".encode()
    ).hexdigest()[:16]
    return f"EP1-TOK-{digest}"


def build_endpoint_identities(
    open_endpoints: pd.DataFrame | list[dict[str, Any]] | None,
    authoritative_attachments: pd.DataFrame | list[dict[str, Any]] | None = None,
    *,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build endpoint identity rows from open endpoints and authoritative attachments.

    Emits NETWORK_OPEN identities for open endpoints (optionally labeled by nearest
    AUTHORITATIVE attachment) and ATTACHMENT_SELECTED identities for every
    authoritative attachment token. Shadow-only; no topology mutation.
    """
    open_rows = _records(open_endpoints)
    att_rows = _records(authoritative_attachments)

    # Index attachments by sheet for efficient lookup
    attachments_by_sheet: dict[str, list[dict[str, Any]]] = {}
    for att in att_rows:
        sheet = str(att.get("sheet_id") or "")
        attachments_by_sheet.setdefault(sheet, []).append(att)

    identities: list[dict[str, Any]] = []

    # NETWORK_OPEN identities
    for endpoint in open_rows:
        sheet_id = str(endpoint.get("sheet_id") or "")
        node_id = endpoint.get("node_id")
        node_id_str = str(node_id) if node_id is not None else ""
        ep_coord = _listish(endpoint.get("coord"))
        coord_x = float(ep_coord[0]) if len(ep_coord) >= 2 else None
        coord_y = float(ep_coord[1]) if len(ep_coord) >= 2 else None

        att = _pick_attachment(endpoint, attachments_by_sheet.get(sheet_id, []))

        label = None
        attached_token_id = None
        attached_token_kind = None
        attached_token_text = None
        attachment_id = None
        authority = "GEOMETRY_ONLY"

        if att is not None:
            label = att.get("token_text")
            attached_token_id = att.get("token_id")
            attached_token_kind = att.get("token_kind")
            attached_token_text = att.get("token_text")
            attachment_id = att.get("attachment_id")
            authority = "AUTHORITATIVE"

        identities.append(
            {
                "endpoint_id": _endpoint_id_open(project_id, sheet_id, node_id_str),
                "schema_version": ENDPOINT_IDENTITY_SCHEMA,
                "project_id": project_id,
                "sheet_id": sheet_id,
                "node_id": node_id,
                "electrical_network_id": endpoint.get("electrical_network_id"),
                "coord_x": coord_x,
                "coord_y": coord_y,
                "source_line_ids": list(_listish(endpoint.get("source_line_ids"))),
                "source_handles": list(_listish(endpoint.get("source_handles"))),
                "boundary_state": endpoint.get("boundary_state"),
                "identity_kind": "NETWORK_OPEN",
                "namespace": f"sheet:{sheet_id}",
                "local_key": node_id_str,
                "label": label,
                "attached_token_id": attached_token_id,
                "attached_token_kind": attached_token_kind,
                "attached_token_text": attached_token_text,
                "attachment_id": attachment_id,
                "authority": authority,
                "algorithm_version": ALGORITHM_VERSION,
            }
        )

    # ATTACHMENT_SELECTED identities for every AUTHORITATIVE attachment
    for att in att_rows:
        if not _is_authoritative_attachment(att):
            continue
        sheet_id = str(att.get("sheet_id") or "")
        token_id = str(att.get("token_id") or "")
        token_text = att.get("token_text")
        scope_key = att.get("scope_key")
        target_line_id = att.get("target_line_id")
        target_x = att.get("target_x")
        target_y = att.get("target_y")

        identities.append(
            {
                "endpoint_id": _endpoint_id_token(project_id, sheet_id, token_id),
                "schema_version": ENDPOINT_IDENTITY_SCHEMA,
                "project_id": project_id,
                "sheet_id": sheet_id,
                "node_id": None,
                "electrical_network_id": None,
                "coord_x": float(target_x) if target_x is not None else None,
                "coord_y": float(target_y) if target_y is not None else None,
                "source_line_ids": (
                    [target_line_id] if target_line_id is not None else []
                ),
                "source_handles": [],
                "boundary_state": None,
                "identity_kind": "ATTACHMENT_SELECTED",
                "namespace": (
                    f"scope:{scope_key}" if scope_key else f"sheet:{sheet_id}"
                ),
                "local_key": str(token_text) if token_text is not None else "",
                "label": token_text,
                "attached_token_id": att.get("token_id"),
                "attached_token_kind": att.get("token_kind"),
                "attached_token_text": token_text,
                "attachment_id": att.get("attachment_id"),
                "authority": "AUTHORITATIVE",
                "algorithm_version": ALGORITHM_VERSION,
            }
        )

    return identities


def build_cross_page_endpoint_candidates(
    endpoint_identities: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Build undirected cross-page label match candidates (CANDIDATE only, never ACCEPT).

    Only among AUTHORITATIVE identities with non-empty label. Groups by
    normalized (strip+upper) label; emits pairwise candidates when the label
    appears on >=2 distinct sheets.
    """
    identities = endpoint_identities or []
    # Group AUTHORITATIVE labeled identities by normalized label
    by_label: dict[str, list[dict[str, Any]]] = {}
    for ident in identities:
        if ident.get("authority") != "AUTHORITATIVE":
            continue
        label = ident.get("label")
        if not label:
            continue
        normalized = str(label).strip().upper()
        if not normalized:
            continue
        by_label.setdefault(normalized, []).append(ident)

    candidates: list[dict[str, Any]] = []
    for normalized_label, group in sorted(by_label.items()):
        # Distinct sheets for this label
        sheets = sorted({str(ident.get("sheet_id") or "") for ident in group})
        n_sheets = len(sheets)
        if n_sheets < 2:
            continue

        # Group identities by sheet
        by_sheet: dict[str, list[dict[str, Any]]] = {}
        for ident in group:
            sheet = str(ident.get("sheet_id") or "")
            by_sheet.setdefault(sheet, []).append(ident)

        confidence = min(1.0, 0.55 + 0.1 * n_sheets)

        # Cartesian product across distinct sheets, sheet_a < sheet_b
        for i, sheet_a in enumerate(sheets):
            for sheet_b in sheets[i + 1 :]:
                for ident_a in by_sheet.get(sheet_a, []):
                    for ident_b in by_sheet.get(sheet_b, []):
                        ep_a = str(ident_a.get("endpoint_id") or "")
                        ep_b = str(ident_b.get("endpoint_id") or "")
                        match_digest = hashlib.sha256(
                            f"{ep_a}|{ep_b}|{normalized_label}".encode()
                        ).hexdigest()[:16]
                        candidates.append(
                            {
                                "match_id": f"XPM-{match_digest}",
                                "label": normalized_label,
                                "sheet_id_a": sheet_a,
                                "endpoint_id_a": ep_a,
                                "sheet_id_b": sheet_b,
                                "endpoint_id_b": ep_b,
                                "relation": "CROSS_PAGE_LABEL",
                                "state": "CANDIDATE",
                                "reciprocal": True,
                                "confidence": confidence,
                                "reason_codes": ["SHARED_AUTHORITATIVE_LABEL"],
                                "algorithm_version": ALGORITHM_VERSION,
                            }
                        )

    return candidates


def build_project_graph(
    endpoint_identities: list[dict[str, Any]] | None = None,
    cross_page_candidates: list[dict[str, Any]] | None = None,
    electrical_networks_df: pd.DataFrame | list | None = None,
    project_profile: dict[str, Any] | None = None,
    constraint_summary: dict[str, Any] | None = None,
    *,
    project_id: str | None = None,
    electrical_networks: pd.DataFrame | list | None = None,
) -> dict[str, Any]:
    """Build a project-graph summary dict (shadow-only, no POSSIBLE union).

    project_profile is accepted for API compat but unused in v1.
    electrical_networks is an alias for electrical_networks_df.
    """
    _ = project_profile  # API compatibility; unused in v1
    identities = endpoint_identities or []
    candidates = cross_page_candidates or []
    networks_src = (
        electrical_networks_df
        if electrical_networks_df is not None
        else electrical_networks
    )
    networks = _records(networks_src)

    authoritative_count = sum(
        1 for ident in identities if ident.get("authority") == "AUTHORITATIVE"
    )
    geometry_only_count = sum(
        1 for ident in identities if ident.get("authority") == "GEOMETRY_ONLY"
    )
    attachment_count = sum(
        1
        for ident in identities
        if ident.get("identity_kind") == "ATTACHMENT_SELECTED"
    )
    unlabeled_open = sum(
        1
        for ident in identities
        if ident.get("identity_kind") == "NETWORK_OPEN" and not ident.get("label")
    )
    review_only = 0
    if constraint_summary:
        review_only = int(constraint_summary.get("review_only_count") or 0)

    return {
        "schema_version": "project-graph-v1",
        "algorithm_version": ALGORITHM_VERSION,
        "project_id": project_id,
        "node_counts": {
            "endpoint_identities": len(identities),
            "authoritative_endpoints": authoritative_count,
            "geometry_only_endpoints": geometry_only_count,
            "attachment_endpoints": attachment_count,
            "electrical_networks": len(networks),
        },
        "edge_counts": {
            "cross_page_candidates": len(candidates),
        },
        "sources": {
            "asserted_networks": True,
            "authoritative_attachments_only": True,
            "possible_union": False,
        },
        "unresolved": {
            "unlabeled_open_endpoints": unlabeled_open,
            "review_only_attachments_excluded": review_only,
        },
        "redlines": {
            "no_possible_union": True,
            "no_filename_patch": True,
            "attachments_non_topology": True,
        },
    }
