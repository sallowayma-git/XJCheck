"""Cross-view terminal series chains for complementary auditing.

A device-terminal value claimed by several producer-issued pass component
mappings is a physical series junction (circuit wire -> terminal -> component
port), not a many-to-one conflict. This module owns that shape: the audit
rules use the predicate to hand such groups to chain auditing instead of
raising a review, and the chain records persist the complementary views so
the audit artifacts carry the full long-chain path.
"""

from __future__ import annotations

import math
from collections import defaultdict

from dwg_audit.domain.models import Pair

TERMINAL_STRIP_SUBMODE = "terminal_strip_lattice"
_PORT_OWNER_SUBMODES = {
    "kk_multi_port_component",
    "small_port_box_component",
    "strip_two_port_component",
    "strip_two_port_endpoint_bridge",
    "inline_two_port_component",
}
_CHAIN_SUBMODES = _PORT_OWNER_SUBMODES | {TERMINAL_STRIP_SUBMODE}
_CHAIN_MIN_CONFIDENCE = 0.95
_CHAIN_SCHEMA_VERSION = "1.0"
# The schematic-inline view and the KK/small-port views may describe the very
# same port-to-terminal fact; that is cross-view corroboration (mirroring the
# authoritative schematic/KK duplicate precedent), not a second claim.
_CORROBORATION_SUBMODE_PAIRS = {
    frozenset({"inline_two_port_component", "kk_multi_port_component"}),
    frozenset({"inline_two_port_component", "small_port_box_component"}),
}
# Terminal-chart rows may continue the chain through the cabinet chart
# (chart terminal UD-x bridged to device terminal 1UDx). Only the row-scoped
# terminal_header_table mode is eligible; backplate_virtual_table rows carry
# their own cross-page scope review and must never join a chain.
_CHAIN_TABLE_MAPPING_MODE = "terminal_header_table"


def _table_chain_eligible(pair: Pair) -> bool:
    evidence = pair.evidence or {}
    if evidence.get("source") != "table_mapping":
        return False
    mapping = evidence.get("table_mapping") or {}
    return mapping.get("mapping_mode") == _CHAIN_TABLE_MAPPING_MODE


def _finite_confidence(pair: Pair) -> float | None:
    confidence = pair.confidence
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    value = float(confidence)
    return value if math.isfinite(value) else None


def _is_chain_member(pair: Pair) -> bool:
    confidence = _finite_confidence(pair)
    if confidence is None or pair.status != "pass" or confidence < _CHAIN_MIN_CONFIDENCE:
        return False
    if not str(pair.left_value or "").strip() or not str(pair.right_value or "").strip():
        return False
    if pair.pair_kind == "table_mapping":
        return _table_chain_eligible(pair)
    if pair.pair_kind != "component_mapping":
        return False
    evidence = pair.evidence or {}
    if evidence.get("source") != "component_mapping":
        return False
    return evidence.get("component_submode") in _CHAIN_SUBMODES


def _left_value_claim_is_corroborated(members: list[Pair]) -> bool:
    """Duplicate-left members are allowed only as one corroborated fact."""

    if len(members) != 2:
        return False
    submodes = frozenset(
        str((pair.evidence or {}).get("component_submode")) for pair in members
    )
    if submodes not in _CORROBORATION_SUBMODE_PAIRS:
        return False
    facts = {(str(pair.left_value), str(pair.right_value)) for pair in members}
    return len(facts) == 1


def is_cross_view_terminal_series_chain(linked_pairs: list[Pair]) -> bool:
    """True when the whole group is a producer-owned terminal series junction."""

    if len(linked_pairs) < 2:
        return False
    if not all(_is_chain_member(pair) for pair in linked_pairs):
        return False
    strip_members = [
        pair
        for pair in linked_pairs
        if (pair.evidence or {}).get("component_submode") == TERMINAL_STRIP_SUBMODE
    ]
    if not strip_members:
        return False
    # A junction must be corroborated by at least one non-strip view
    # (component port or terminal-chart row). Two strip rows alone mean two
    # circuit wires claiming one device terminal - a genuine review case.
    strip_ids = {id(pair) for pair in strip_members}
    corroborated_members = [pair for pair in linked_pairs if id(pair) not in strip_ids]
    if not corroborated_members:
        return False
    members_by_left: dict[str, list[Pair]] = defaultdict(list)
    for pair in linked_pairs:
        members_by_left[str(pair.left_value)].append(pair)
    distinct_claims = 0
    for members in members_by_left.values():
        if len(members) == 1:
            distinct_claims += 1
            continue
        if not _left_value_claim_is_corroborated(members):
            return False
        distinct_claims += 1
    return distinct_claims >= 2


def build_terminal_series_chains(pairs: list[Pair]) -> list[dict]:
    """Build one record per terminal series junction across all producer views.

    Members referencing the same junction value are collected regardless of
    sheet, and pass component mappings whose left value equals the junction
    are attached as continuations so multi-hop long chains stay inspectable.
    """

    members_by_junction: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        if _is_chain_member(pair):
            members_by_junction[str(pair.right_value)].append(pair)
    chains: list[dict] = []
    for junction in sorted(members_by_junction):
        members = members_by_junction[junction]
        if not is_cross_view_terminal_series_chain(members):
            continue
        continuations = [
            pair
            for pair in pairs
            if pair.pair_kind == "component_mapping"
            and pair.status == "pass"
            and _finite_confidence(pair) is not None
            and float(_finite_confidence(pair)) >= _CHAIN_MIN_CONFIDENCE
            and str(pair.left_value) == junction
        ]
        chains.append(
            {
                "schema_version": _CHAIN_SCHEMA_VERSION,
                "junction_kind": "device_terminal_series",
                "junction_value": junction,
                "member_count": len(members),
                "members": [_chain_member_record(pair, junction) for pair in members],
                "circuit_side_values": sorted(
                    {
                        str(pair.left_value)
                        for pair in members
                        if (pair.evidence or {}).get("component_submode") == TERMINAL_STRIP_SUBMODE
                    }
                ),
                "component_side_values": sorted(
                    {
                        str(pair.left_value)
                        for pair in members
                        if (pair.evidence or {}).get("component_submode") in _PORT_OWNER_SUBMODES
                    }
                ),
                "chart_side_values": sorted(
                    {
                        str(pair.left_value)
                        for pair in members
                        if pair.pair_kind == "table_mapping"
                    }
                ),
                "continuation_count": len(continuations),
                "continuations": [_chain_member_record(pair, pair.right_value) for pair in continuations],
            }
        )
    return chains


def _chain_member_record(pair: Pair, junction_value: str) -> dict:
    evidence = pair.evidence or {}
    submode = evidence.get("component_submode")
    if pair.pair_kind == "table_mapping":
        role = "chart_side"
    elif submode == TERMINAL_STRIP_SUBMODE:
        role = "circuit_side"
    else:
        role = "component_side"
    return {
        "pair_id": pair.pair_id,
        "sheet_id": pair.sheet_id,
        "file_id": pair.file_id,
        "filename": evidence.get("filename"),
        "sheet_no": evidence.get("sheet_no"),
        "component_submode": submode or _CHAIN_TABLE_MAPPING_MODE,
        "role": role,
        "left_value": pair.left_value,
        "junction_value": junction_value,
        "left_text_id": pair.left_text_id,
        "left_coord": [pair.left_coord_x, pair.left_coord_y],
        "line_group_id": pair.line_group_id,
    }


def summarize_terminal_series_chains(chains: list[dict]) -> dict:
    return {
        "schema_version": _CHAIN_SCHEMA_VERSION,
        "chain_count": len(chains),
        "junction_values": [chain["junction_value"] for chain in chains],
        "circuit_side_member_count": sum(len(chain["circuit_side_values"]) for chain in chains),
        "component_side_member_count": sum(len(chain["component_side_values"]) for chain in chains),
        "continuation_count": sum(chain["continuation_count"] for chain in chains),
    }
