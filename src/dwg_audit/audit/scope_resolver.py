from __future__ import annotations

import math
from collections import Counter
from collections import defaultdict
from typing import Any


ALGORITHM_VERSION = "scope-resolver-v1"

_SCOPED_EXTERNAL_X_TOL = 75.0
_SCOPED_EXTERNAL_ROW_Y_TOL = 2.5

_PREFIX_EQUALITY_KINDS = frozenset({"EXTERNAL_ENDPOINT", "DEVICE_TAG", "COMPONENT_BODY"})
_PREFIX_GEOMETRY_KINDS = frozenset({"TERMINAL_LOCAL", "WIRE_N_NUMBER"})

_BODY_PORT_X_PAD = 48.0
_BODY_PORT_Y_TOL = 28.0
_BODY_PORT_AMBIGUOUS_GAP = 3.0

_SEMANTIC_ROW_MARKERS = (
    "AC230V",
    "Shielding",
    "3U0",
    "ZKK",
    "CLP",
    "KLP",
    "DK",
    "UA",
    "UB",
    "UC",
    "UN",
)
_SEMANTIC_ROW_MARKER_KINDS = frozenset({"ANNOTATION", "DEVICE_TAG", "COMPONENT_BODY"})
_SEMANTIC_ROW_Y_TOL = 5.0
_SEMANTIC_ROW_X_TOL = 120.0
_SEMANTIC_ROW_DY_GAP = 0.5
_SEMANTIC_ROW_DX_GAP = 5.0

_SCOPE_PRIORITY = ("BODY_PORT", "SCOPED_PREFIX", "SEMANTIC_ROW")


def resolve_attachment_scopes(
    tokens: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
    *,
    texts: list[Any] | None = None,  # optional; unused when tokens carry coords
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return (scoped_attachments, scope_decisions, summary).

    Pure shadow scope resolver: re-scopes/annotates semantic attachment candidates
    using token relationships. Does not create Pair/Issue or mutate topology.
    """
    del texts  # reserved for future use when tokens lack coordinates

    tokens_by_id: dict[str, dict[str, Any]] = {}
    tokens_by_sheet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for token in tokens:
        token_id = str(token.get("token_id") or "")
        if token_id:
            tokens_by_id[token_id] = token
        sheet_id = str(token.get("sheet_id") or "")
        tokens_by_sheet[sheet_id].append(token)

    # member_token_id -> list of binding dicts (one per scope kind attempted)
    # binding: {scope_kind, scope_key, owner_token_id, state, confidence, reason_codes}
    bindings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    decisions: list[dict[str, Any]] = []
    decision_counter = 0

    def _emit_decision(
        *,
        sheet_id: str,
        scope_kind: str,
        scope_key: str | None,
        owner_token_id: str | None,
        member_token_ids: list[str],
        state: str,
        confidence: float,
        reason_codes: list[str],
    ) -> None:
        nonlocal decision_counter
        decision_counter += 1
        decisions.append(
            {
                "decision_id": f"SD{decision_counter:04d}",
                "sheet_id": sheet_id,
                "scope_kind": scope_kind,
                "scope_key": scope_key,
                "owner_token_id": owner_token_id,
                "member_token_ids": list(member_token_ids),
                "state": state,
                "confidence": confidence,
                "reason_codes": list(reason_codes),
                "algorithm_version": ALGORITHM_VERSION,
            }
        )

    # --- A) SCOPED_PREFIX ---
    for sheet_id in sorted(tokens_by_sheet.keys()):
        sheet_tokens = tokens_by_sheet[sheet_id]
        owners = [
            t
            for t in sheet_tokens
            if str(t.get("token_kind") or "") == "SCOPED_PREFIX"
        ]
        if not owners:
            continue

        # Group resolved members by owner for compact decisions.
        resolved_by_owner: dict[str, list[str]] = defaultdict(list)
        owner_meta: dict[str, dict[str, Any]] = {}

        for member in sorted(sheet_tokens, key=lambda t: str(t.get("token_id") or "")):
            kind = str(member.get("token_kind") or "")
            member_id = str(member.get("token_id") or "")
            if not member_id:
                continue

            prefix_cands: list[dict[str, Any]] = []
            geom_cands: list[tuple[float, dict[str, Any]]] = []

            member_prefix = member.get("prefix")
            mx = float(member.get("insert_x") or 0.0)
            my = float(member.get("insert_y") or 0.0)

            for owner in owners:
                owner_prefix = owner.get("prefix")
                ox = float(owner.get("insert_x") or 0.0)
                oy = float(owner.get("insert_y") or 0.0)
                dx = abs(mx - ox)
                dy = abs(my - oy)
                dist = math.hypot(mx - ox, my - oy)

                if (
                    kind in _PREFIX_EQUALITY_KINDS
                    and member_prefix is not None
                    and owner_prefix is not None
                    and str(member_prefix) == str(owner_prefix)
                ):
                    prefix_cands.append(owner)

                # Geometry neighborhood for geometry kinds always; also for
                # prefix-bearing kinds when checking conflict.
                if dx <= _SCOPED_EXTERNAL_X_TOL and dy <= _SCOPED_EXTERNAL_ROW_Y_TOL:
                    geom_cands.append((dist, owner))

            geom_cands.sort(key=lambda item: (item[0], str(item[1].get("token_id") or "")))

            # Geometry-only members (TERMINAL_LOCAL / WIRE_N_NUMBER)
            if kind in _PREFIX_GEOMETRY_KINDS:
                if len(geom_cands) == 0:
                    continue
                if len(geom_cands) > 1:
                    # Multiple owners in neighborhood → AMBIGUOUS
                    first_owner = geom_cands[0][1]
                    bindings[member_id].append(
                        {
                            "scope_kind": "SCOPED_PREFIX",
                            "scope_key": first_owner.get("prefix"),
                            "owner_token_id": str(first_owner.get("token_id") or ""),
                            "state": "AMBIGUOUS",
                            "confidence": 0.7,
                            "reason_codes": ["MULTIPLE_OWNERS", "GEOMETRIC_NEIGHBORHOOD"],
                        }
                    )
                    _emit_decision(
                        sheet_id=sheet_id,
                        scope_kind="SCOPED_PREFIX",
                        scope_key=str(first_owner.get("prefix")) if first_owner.get("prefix") is not None else None,
                        owner_token_id=str(first_owner.get("token_id") or "") or None,
                        member_token_ids=[member_id],
                        state="AMBIGUOUS",
                        confidence=0.7,
                        reason_codes=["MULTIPLE_OWNERS", "GEOMETRIC_NEIGHBORHOOD"],
                    )
                    continue

                owner = geom_cands[0][1]
                owner_id = str(owner.get("token_id") or "")
                scope_key = owner.get("prefix")
                bindings[member_id].append(
                    {
                        "scope_kind": "SCOPED_PREFIX",
                        "scope_key": scope_key,
                        "owner_token_id": owner_id,
                        "state": "RESOLVED",
                        "confidence": 0.9,
                        "reason_codes": ["GEOMETRIC_NEIGHBORHOOD"],
                    }
                )
                resolved_by_owner[owner_id].append(member_id)
                owner_meta[owner_id] = {
                    "scope_key": scope_key,
                    "confidence": 0.9,
                    "reason_codes": ["GEOMETRIC_NEIGHBORHOOD"],
                }
                continue

            # Prefix-equality members (EXTERNAL_ENDPOINT / DEVICE_TAG / COMPONENT_BODY)
            if kind in _PREFIX_EQUALITY_KINDS:
                if len(prefix_cands) == 0 and len(geom_cands) == 0:
                    continue

                if len(prefix_cands) > 1:
                    first = prefix_cands[0]
                    bindings[member_id].append(
                        {
                            "scope_kind": "SCOPED_PREFIX",
                            "scope_key": first.get("prefix"),
                            "owner_token_id": str(first.get("token_id") or ""),
                            "state": "AMBIGUOUS",
                            "confidence": 0.7,
                            "reason_codes": ["MULTIPLE_OWNERS", "PREFIX_EQUALITY"],
                        }
                    )
                    _emit_decision(
                        sheet_id=sheet_id,
                        scope_kind="SCOPED_PREFIX",
                        scope_key=str(first.get("prefix")) if first.get("prefix") is not None else None,
                        owner_token_id=str(first.get("token_id") or "") or None,
                        member_token_ids=[member_id],
                        state="AMBIGUOUS",
                        confidence=0.7,
                        reason_codes=["MULTIPLE_OWNERS", "PREFIX_EQUALITY"],
                    )
                    continue

                if len(prefix_cands) == 1:
                    prefix_owner = prefix_cands[0]
                    prefix_owner_id = str(prefix_owner.get("token_id") or "")
                    prefix_key = prefix_owner.get("prefix")

                    # Check geometric conflict against a different owner
                    conflict = False
                    if geom_cands:
                        nearest_geom = geom_cands[0][1]
                        nearest_geom_id = str(nearest_geom.get("token_id") or "")
                        nearest_dist = geom_cands[0][0]
                        if nearest_geom_id != prefix_owner_id:
                            # Distance to prefix owner (may or may not be in neighborhood)
                            ox = float(prefix_owner.get("insert_x") or 0.0)
                            oy = float(prefix_owner.get("insert_y") or 0.0)
                            dist_prefix = math.hypot(mx - ox, my - oy)
                            pdx = abs(mx - ox)
                            pdy = abs(my - oy)
                            prefix_in_neighborhood = (
                                pdx <= _SCOPED_EXTERNAL_X_TOL
                                and pdy <= _SCOPED_EXTERNAL_ROW_Y_TOL
                            )
                            if (
                                not prefix_in_neighborhood
                                or (nearest_dist * 2.0 < dist_prefix)
                            ):
                                conflict = True

                    if conflict:
                        nearest_geom = geom_cands[0][1]
                        bindings[member_id].append(
                            {
                                "scope_kind": "SCOPED_PREFIX",
                                "scope_key": prefix_key,
                                "owner_token_id": prefix_owner_id,
                                "state": "CONFLICT",
                                "confidence": 0.5,
                                "reason_codes": ["PREFIX_GEOMETRY_CONFLICT"],
                            }
                        )
                        _emit_decision(
                            sheet_id=sheet_id,
                            scope_kind="SCOPED_PREFIX",
                            scope_key=str(prefix_key) if prefix_key is not None else None,
                            owner_token_id=prefix_owner_id or None,
                            member_token_ids=[member_id],
                            state="CONFLICT",
                            confidence=0.5,
                            reason_codes=["PREFIX_GEOMETRY_CONFLICT"],
                        )
                    else:
                        bindings[member_id].append(
                            {
                                "scope_kind": "SCOPED_PREFIX",
                                "scope_key": prefix_key,
                                "owner_token_id": prefix_owner_id,
                                "state": "RESOLVED",
                                "confidence": 0.95,
                                "reason_codes": ["PREFIX_EQUALITY"],
                            }
                        )
                        resolved_by_owner[prefix_owner_id].append(member_id)
                        owner_meta[prefix_owner_id] = {
                            "scope_key": prefix_key,
                            "confidence": 0.95,
                            "reason_codes": ["PREFIX_EQUALITY"],
                        }
                    continue

                # No prefix equality but geometry neighborhood has candidates
                if len(geom_cands) > 1:
                    first_owner = geom_cands[0][1]
                    bindings[member_id].append(
                        {
                            "scope_kind": "SCOPED_PREFIX",
                            "scope_key": first_owner.get("prefix"),
                            "owner_token_id": str(first_owner.get("token_id") or ""),
                            "state": "AMBIGUOUS",
                            "confidence": 0.7,
                            "reason_codes": ["MULTIPLE_OWNERS", "GEOMETRIC_NEIGHBORHOOD"],
                        }
                    )
                    _emit_decision(
                        sheet_id=sheet_id,
                        scope_kind="SCOPED_PREFIX",
                        scope_key=str(first_owner.get("prefix")) if first_owner.get("prefix") is not None else None,
                        owner_token_id=str(first_owner.get("token_id") or "") or None,
                        member_token_ids=[member_id],
                        state="AMBIGUOUS",
                        confidence=0.7,
                        reason_codes=["MULTIPLE_OWNERS", "GEOMETRIC_NEIGHBORHOOD"],
                    )
                elif len(geom_cands) == 1:
                    owner = geom_cands[0][1]
                    owner_id = str(owner.get("token_id") or "")
                    scope_key = owner.get("prefix")
                    bindings[member_id].append(
                        {
                            "scope_kind": "SCOPED_PREFIX",
                            "scope_key": scope_key,
                            "owner_token_id": owner_id,
                            "state": "RESOLVED",
                            "confidence": 0.9,
                            "reason_codes": ["GEOMETRIC_NEIGHBORHOOD"],
                        }
                    )
                    resolved_by_owner[owner_id].append(member_id)
                    owner_meta[owner_id] = {
                        "scope_key": scope_key,
                        "confidence": 0.9,
                        "reason_codes": ["GEOMETRIC_NEIGHBORHOOD"],
                    }

        for owner_id in sorted(resolved_by_owner.keys()):
            members = resolved_by_owner[owner_id]
            meta = owner_meta.get(owner_id, {})
            _emit_decision(
                sheet_id=sheet_id,
                scope_kind="SCOPED_PREFIX",
                scope_key=str(meta["scope_key"]) if meta.get("scope_key") is not None else None,
                owner_token_id=owner_id or None,
                member_token_ids=members,
                state="RESOLVED",
                confidence=float(meta.get("confidence") or 0.95),
                reason_codes=list(meta.get("reason_codes") or ["PREFIX_EQUALITY"]),
            )

    # --- B) BODY_PORT ---
    for sheet_id in sorted(tokens_by_sheet.keys()):
        sheet_tokens = tokens_by_sheet[sheet_id]
        bodies = [
            t
            for t in sheet_tokens
            if str(t.get("token_kind") or "") == "COMPONENT_BODY"
        ]
        ports = [
            t
            for t in sheet_tokens
            if str(t.get("token_kind") or "") == "COMPONENT_PORT"
        ]
        if not bodies or not ports:
            continue

        resolved_by_body: dict[str, list[str]] = defaultdict(list)
        body_meta: dict[str, dict[str, Any]] = {}

        for port in sorted(ports, key=lambda t: str(t.get("token_id") or "")):
            port_id = str(port.get("token_id") or "")
            if not port_id:
                continue
            px = float(port.get("insert_x") or 0.0)
            py = float(port.get("insert_y") or 0.0)

            candidates: list[tuple[float, dict[str, Any]]] = []
            for body in bodies:
                bx, by, half_w = _body_center_and_half_width(body)
                if abs(py - by) > _BODY_PORT_Y_TOL:
                    continue
                if abs(px - bx) > (half_w + _BODY_PORT_X_PAD):
                    continue
                dist = math.hypot(px - bx, py - by)
                candidates.append((dist, body))

            if not candidates:
                continue

            candidates.sort(key=lambda item: (item[0], str(item[1].get("token_id") or "")))
            best_dist, best_body = candidates[0]
            body_id = str(best_body.get("token_id") or "")
            scope_key = str(best_body.get("normalized_text") or "")

            if len(candidates) >= 2:
                second_dist = candidates[1][0]
                if second_dist - best_dist < _BODY_PORT_AMBIGUOUS_GAP:
                    bindings[port_id].append(
                        {
                            "scope_kind": "BODY_PORT",
                            "scope_key": scope_key,
                            "owner_token_id": body_id,
                            "state": "AMBIGUOUS",
                            "confidence": 0.7,
                            "reason_codes": ["MULTIPLE_OWNERS", "NEAREST_BODY"],
                        }
                    )
                    _emit_decision(
                        sheet_id=sheet_id,
                        scope_kind="BODY_PORT",
                        scope_key=scope_key or None,
                        owner_token_id=body_id or None,
                        member_token_ids=[port_id],
                        state="AMBIGUOUS",
                        confidence=0.7,
                        reason_codes=["MULTIPLE_OWNERS", "NEAREST_BODY"],
                    )
                    continue

            bindings[port_id].append(
                {
                    "scope_kind": "BODY_PORT",
                    "scope_key": scope_key,
                    "owner_token_id": body_id,
                    "state": "RESOLVED",
                    "confidence": 0.9,
                    "reason_codes": ["NEAREST_BODY"],
                }
            )
            resolved_by_body[body_id].append(port_id)
            body_meta[body_id] = {
                "scope_key": scope_key,
                "confidence": 0.9,
                "reason_codes": ["NEAREST_BODY"],
            }

        for body_id in sorted(resolved_by_body.keys()):
            members = resolved_by_body[body_id]
            meta = body_meta.get(body_id, {})
            _emit_decision(
                sheet_id=sheet_id,
                scope_kind="BODY_PORT",
                scope_key=str(meta.get("scope_key") or "") or None,
                owner_token_id=body_id or None,
                member_token_ids=members,
                state="RESOLVED",
                confidence=float(meta.get("confidence") or 0.9),
                reason_codes=list(meta.get("reason_codes") or ["NEAREST_BODY"]),
            )

    # --- C) SEMANTIC_ROW ---
    for sheet_id in sorted(tokens_by_sheet.keys()):
        sheet_tokens = tokens_by_sheet[sheet_id]
        markers: list[dict[str, Any]] = []
        for t in sheet_tokens:
            kind = str(t.get("token_kind") or "")
            if kind not in _SEMANTIC_ROW_MARKER_KINDS:
                continue
            text = str(t.get("normalized_text") or "")
            if _has_semantic_marker(text):
                markers.append(t)
        if not markers:
            continue

        terminals = [
            t
            for t in sheet_tokens
            if str(t.get("token_kind") or "") == "TERMINAL_LOCAL"
        ]
        if not terminals:
            continue

        resolved_by_marker: dict[str, list[str]] = defaultdict(list)
        marker_meta: dict[str, dict[str, Any]] = {}

        for terminal in sorted(terminals, key=lambda t: str(t.get("token_id") or "")):
            term_id = str(terminal.get("token_id") or "")
            if not term_id:
                continue
            tx = float(terminal.get("insert_x") or 0.0)
            ty = float(terminal.get("insert_y") or 0.0)

            cands: list[tuple[float, float, dict[str, Any]]] = []
            for marker in markers:
                mx = float(marker.get("insert_x") or 0.0)
                my = float(marker.get("insert_y") or 0.0)
                dy = abs(ty - my)
                dx = abs(tx - mx)
                if dy <= _SEMANTIC_ROW_Y_TOL and dx <= _SEMANTIC_ROW_X_TOL:
                    cands.append((dy, dx, marker))

            if not cands:
                continue

            cands.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                    str(item[2].get("token_id") or ""),
                )
            )
            best_dy, best_dx, best_marker = cands[0]
            marker_id = str(best_marker.get("token_id") or "")
            scope_key = str(best_marker.get("normalized_text") or "")

            if len(cands) >= 2:
                second_dy, second_dx, _ = cands[1]
                if (
                    abs(second_dy - best_dy) < _SEMANTIC_ROW_DY_GAP
                    and abs(second_dx - best_dx) < _SEMANTIC_ROW_DX_GAP
                ):
                    bindings[term_id].append(
                        {
                            "scope_kind": "SEMANTIC_ROW",
                            "scope_key": scope_key,
                            "owner_token_id": marker_id,
                            "state": "AMBIGUOUS",
                            "confidence": 0.7,
                            "reason_codes": ["MULTIPLE_OWNERS", "SEMANTIC_ROW_MARKER"],
                        }
                    )
                    _emit_decision(
                        sheet_id=sheet_id,
                        scope_kind="SEMANTIC_ROW",
                        scope_key=scope_key or None,
                        owner_token_id=marker_id or None,
                        member_token_ids=[term_id],
                        state="AMBIGUOUS",
                        confidence=0.7,
                        reason_codes=["MULTIPLE_OWNERS", "SEMANTIC_ROW_MARKER"],
                    )
                    continue

            bindings[term_id].append(
                {
                    "scope_kind": "SEMANTIC_ROW",
                    "scope_key": scope_key,
                    "owner_token_id": marker_id,
                    "state": "RESOLVED",
                    "confidence": 0.9,
                    "reason_codes": ["SEMANTIC_ROW_MARKER"],
                }
            )
            resolved_by_marker[marker_id].append(term_id)
            marker_meta[marker_id] = {
                "scope_key": scope_key,
                "confidence": 0.9,
                "reason_codes": ["SEMANTIC_ROW_MARKER"],
            }

        for marker_id in sorted(resolved_by_marker.keys()):
            members = resolved_by_marker[marker_id]
            meta = marker_meta.get(marker_id, {})
            _emit_decision(
                sheet_id=sheet_id,
                scope_kind="SEMANTIC_ROW",
                scope_key=str(meta.get("scope_key") or "") or None,
                owner_token_id=marker_id or None,
                member_token_ids=members,
                state="RESOLVED",
                confidence=float(meta.get("confidence") or 0.9),
                reason_codes=list(meta.get("reason_codes") or ["SEMANTIC_ROW_MARKER"]),
            )

    # --- Annotate attachments with priority BODY_PORT > SCOPED_PREFIX > SEMANTIC_ROW ---
    token_scope: dict[str, dict[str, Any]] = {}
    for token_id, kind_bindings in bindings.items():
        by_kind = {str(b["scope_kind"]): b for b in kind_bindings}
        chosen = None
        for kind in _SCOPE_PRIORITY:
            if kind in by_kind:
                chosen = by_kind[kind]
                break
        if chosen is None:
            continue
        reason_codes = list(chosen.get("reason_codes") or [])
        # Note priority if a lower-priority binding was overridden
        lower_present = [
            k for k in _SCOPE_PRIORITY if k in by_kind and k != chosen["scope_kind"]
        ]
        if lower_present and chosen["scope_kind"] == "BODY_PORT":
            if "PRIORITY_BODY_PORT" not in reason_codes:
                reason_codes = reason_codes + ["PRIORITY_BODY_PORT"]
        token_scope[token_id] = {
            "scope_kind": chosen["scope_kind"],
            "scope_token_id": chosen.get("owner_token_id") or None,
            "scope_key": (
                str(chosen["scope_key"])
                if chosen.get("scope_key") is not None
                else None
            ),
            "scope_state": chosen["state"],
            "scope_reason_codes": reason_codes,
            "scope_confidence": float(chosen.get("confidence") or 0.0),
        }

    scoped_attachments: list[dict[str, Any]] = []
    for attachment in attachments:
        row = dict(attachment)
        token_id = str(attachment.get("token_id") or "")
        scope = token_scope.get(token_id)
        if scope is not None:
            row["scope_kind"] = scope["scope_kind"]
            row["scope_token_id"] = scope["scope_token_id"]
            row["scope_key"] = scope["scope_key"]
            row["scope_state"] = scope["scope_state"]
            row["scope_reason_codes"] = list(scope["scope_reason_codes"])
            row["scope_confidence"] = scope["scope_confidence"]
        else:
            row["scope_kind"] = None
            row["scope_token_id"] = None
            row["scope_key"] = None
            row["scope_state"] = "UNSCOPED"
            row["scope_reason_codes"] = ["NO_OWNER"]
            row["scope_confidence"] = 0.0
        scoped_attachments.append(row)

    summary = _build_summary(scoped_attachments, decisions)
    return scoped_attachments, decisions, summary


def _body_center_and_half_width(body: dict[str, Any]) -> tuple[float, float, float]:
    """Return (center_x, insert_y, half_width) for a COMPONENT_BODY token."""
    by = float(body.get("insert_y") or 0.0)
    bbox = body.get("bbox")
    if (
        isinstance(bbox, (list, tuple))
        and len(bbox) >= 4
        and all(isinstance(v, (int, float)) for v in bbox[:4])
    ):
        min_x = float(bbox[0])
        max_x = float(bbox[2])
        center_x = (min_x + max_x) / 2.0
        half_w = abs(max_x - min_x) / 2.0
        return center_x, by, half_w
    bx = float(body.get("insert_x") or 0.0)
    return bx, by, 0.0


def _has_semantic_marker(text: str) -> bool:
    upper = text.upper()
    for marker in _SEMANTIC_ROW_MARKERS:
        if marker.upper() in upper:
            return True
    return False


def _build_summary(
    scoped_attachments: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    by_state: Counter[str] = Counter()
    by_scope_kind: Counter[str] = Counter()
    scoped_count = 0
    unscoped_count = 0
    ambiguous_count = 0
    conflict_count = 0

    for row in scoped_attachments:
        state = str(row.get("scope_state") or "UNSCOPED")
        by_state[state] += 1
        kind = row.get("scope_kind")
        if kind is not None:
            by_scope_kind[str(kind)] += 1
        if state == "RESOLVED":
            scoped_count += 1
        elif state == "UNSCOPED":
            unscoped_count += 1
        elif state == "AMBIGUOUS":
            ambiguous_count += 1
        elif state == "CONFLICT":
            conflict_count += 1

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "attachment_count": len(scoped_attachments),
        "scoped_attachment_count": scoped_count,
        "unscoped_attachment_count": unscoped_count,
        "ambiguous_count": ambiguous_count,
        "conflict_count": conflict_count,
        "decision_count": len(decisions),
        "by_scope_kind": dict(sorted(by_scope_kind.items())),
        "by_state": dict(sorted(by_state.items())),
    }
