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
    return (
        mapping.get("mapping_mode") == _CHAIN_TABLE_MAPPING_MODE
        and mapping.get("source") in {None, "table_mapping"}
        and str(mapping.get("sheet_id") or "") == str(pair.sheet_id or "")
        and str(mapping.get("logical_endpoint") or "") == str(pair.left_value or "")
        and str(mapping.get("right_value") or "") == str(pair.right_value or "")
        and mapping.get("row_number_sequence_valid") is True
        and bool(mapping.get("header_prefix"))
        and bool(mapping.get("header_text_id"))
        and bool(mapping.get("middle_text_id"))
        and mapping.get("row_number") is not None
        and isinstance(mapping.get("column_roles"), dict)
        and (
            mapping["column_roles"].get("left") == "terminal_endpoint"
            or mapping["column_roles"].get("right") == "terminal_endpoint"
        )
    )


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
        return _table_chain_eligible(pair) and _has_complete_table_chain_evidence(pair)
    if pair.pair_kind != "component_mapping":
        return False
    evidence = pair.evidence or {}
    if evidence.get("source") != "component_mapping":
        return False
    return (
        evidence.get("component_submode") in _CHAIN_SUBMODES
        and _has_complete_component_chain_evidence(pair)
    )


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_coordinate(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item)) for item in value)
    )


def _pair_coordinate_matches(value: object, x: object, y: object) -> bool:
    return _finite_coordinate(value) and isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool) and not isinstance(y, bool) and math.isfinite(float(x)) and math.isfinite(float(y)) and float(value[0]) == float(x) and float(value[1]) == float(y)


def _complete_component_identity(pair: Pair, evidence: dict) -> bool:
    return (
        evidence.get("source") == "component_mapping"
        and evidence.get("pair_kind") == "component_mapping"
        and _nonempty_text(evidence.get("component_body"))
        and _nonempty_text(evidence.get("component_port"))
        and _nonempty_text(evidence.get("component_body_text_id"))
        and _nonempty_text(evidence.get("component_port_text_id"))
        and _nonempty_text(evidence.get("external_endpoint"))
        and _nonempty_text(evidence.get("external_endpoint_raw"))
        and _nonempty_text(evidence.get("external_endpoint_text_id"))
        and _nonempty_text(evidence.get("logical_endpoint"))
        and str(evidence["logical_endpoint"]).strip() == str(pair.left_value).strip()
        and str(evidence["external_endpoint"]).strip() == str(pair.right_value).strip()
        and str(pair.left_text_id or "").strip() == str(evidence["component_port_text_id"]).strip()
        and str(pair.right_text_id or "").strip() == str(evidence["external_endpoint_text_id"]).strip()
        and _pair_coordinate_matches(evidence.get("component_port_coord"), pair.left_coord_x, pair.left_coord_y)
        and _pair_coordinate_matches(evidence.get("external_endpoint_coord"), pair.right_coord_x, pair.right_coord_y)
    )


def _has_complete_component_chain_evidence(pair: Pair) -> bool:
    evidence = pair.evidence or {}
    submode = evidence.get("component_submode")
    if submode == TERMINAL_STRIP_SUBMODE:
        left_pin = evidence.get("terminal_strip_left_pin")
        right_pin = evidence.get("terminal_strip_right_pin")
        flank_groups = evidence.get("terminal_strip_flank_group_ids")
        flank_lines = evidence.get("terminal_strip_flank_line_ids")
        return (
            evidence.get("source") == "component_mapping"
            and evidence.get("pair_kind") == "component_mapping"
            and _nonempty_text(evidence.get("terminal_strip_instance"))
            and _nonempty_text(evidence.get("terminal_strip_instance_text_id"))
            and isinstance(evidence.get("terminal_strip_block_names"), list)
            and bool(evidence["terminal_strip_block_names"])
            and _nonempty_text(evidence.get("terminal_strip_insert_handle"))
            and isinstance(evidence.get("terminal_strip_pin_row"), int)
            and evidence["terminal_strip_pin_row"] >= 1
            and isinstance(evidence.get("terminal_strip_pin_row_count"), int)
            and evidence["terminal_strip_pin_row_count"] >= evidence["terminal_strip_pin_row"]
            and isinstance(evidence.get("terminal_strip_pitch"), (int, float))
            and math.isfinite(float(evidence["terminal_strip_pitch"]))
            and evidence["terminal_strip_pitch"] > 0
            and isinstance(left_pin, dict)
            and isinstance(right_pin, dict)
            and _nonempty_text(left_pin.get("text_id"))
            and _nonempty_text(right_pin.get("text_id"))
            and _finite_coordinate(left_pin.get("coord"))
            and _finite_coordinate(right_pin.get("coord"))
            and _nonempty_text(evidence.get("left_terminal_text_id"))
            and _nonempty_text(evidence.get("right_terminal_text_id"))
            and _pair_coordinate_matches(evidence.get("left_terminal_coord"), pair.left_coord_x, pair.left_coord_y)
            and _pair_coordinate_matches(evidence.get("right_terminal_coord"), pair.right_coord_x, pair.right_coord_y)
            and str(evidence.get("left_terminal") or "") == str(pair.left_value or "")
            and str(evidence.get("right_terminal") or "") == str(pair.right_value or "")
            and _nonempty_text(evidence.get("line_group_id"))
            and pair.line_group_id == evidence.get("line_group_id")
            and isinstance(evidence.get("supporting_line_ids"), list)
            and bool(evidence["supporting_line_ids"])
            and isinstance(flank_groups, list)
            and len(flank_groups) >= 2
            and isinstance(flank_lines, list)
            and len(flank_lines) >= 2
        )
    if submode not in _PORT_OWNER_SUBMODES:
        return False
    if submode == "strip_two_port_endpoint_bridge":
        return _has_complete_endpoint_bridge_evidence(pair)
    if not _complete_component_identity(pair, evidence):
        return False
    if submode == "inline_two_port_component":
        return (
            evidence.get("mapping_mode") == "schematic_inline_two_port"
            and evidence.get("recognition_mode") == "geometry_insert_backed_inline_two_port"
            and evidence.get("internal_connectivity_inferred") is False
            and evidence.get("electrical_union_eligible") is False
            and evidence.get("ordinary_pair_eligible") is False
            and _nonempty_text(evidence.get("component_block_name"))
            and _nonempty_text(evidence.get("component_block_handle"))
        )
    common = (
        _nonempty_text(evidence.get("component_block_name"))
        and _nonempty_text(evidence.get("line_group_id"))
        and pair.line_group_id == evidence.get("line_group_id")
        and isinstance(evidence.get("supporting_line_ids"), list)
        and bool(evidence["supporting_line_ids"])
        and evidence.get("left_side_label") == "component_port"
        and evidence.get("right_side_label") == "external_endpoint"
    )
    if submode == "kk_multi_port_component":
        return common and _nonempty_text(evidence.get("component_block_id"))
    if submode == "small_port_box_component":
        bbox = evidence.get("component_instance_bbox")
        return common and evidence.get("endpoint_side") in {"top", "bottom", "left", "right"} and isinstance(bbox, (list, tuple)) and len(bbox) == 4 and all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in bbox)
    if submode == "strip_two_port_component":
        return common and evidence.get("endpoint_side") in {"top", "bottom", "left", "right"} and str(evidence.get("external_endpoint_split") or "") == str(pair.right_value or "")
    return False


def _has_complete_endpoint_bridge_evidence(pair: Pair) -> bool:
    evidence = pair.evidence or {}
    required = ("component_block_name", "top_port", "bottom_port", "top_endpoint", "top_endpoint_raw", "top_endpoint_text_id", "bottom_endpoint", "bottom_endpoint_raw", "bottom_endpoint_text_id", "logical_endpoint", "external_endpoint", "line_group_id")
    return (
        all(_nonempty_text(evidence.get(key)) for key in required)
        and evidence.get("line_orientation") == "strip_two_port_endpoint_bridge_vertical"
        and evidence.get("left_side_label") == "top_endpoint"
        and evidence.get("right_side_label") == "bottom_endpoint"
        and evidence.get("top_port") == "1"
        and evidence.get("bottom_port") == "2"
        and evidence.get("top_endpoint") == pair.left_value
        and evidence.get("bottom_endpoint") == pair.right_value
        and evidence.get("logical_endpoint") == pair.left_value
        and evidence.get("external_endpoint") == pair.right_value
        and pair.left_text_id == evidence.get("top_endpoint_text_id")
        and pair.right_text_id == evidence.get("bottom_endpoint_text_id")
        and _pair_coordinate_matches(evidence.get("top_endpoint_coord"), pair.left_coord_x, pair.left_coord_y)
        and _pair_coordinate_matches(evidence.get("bottom_endpoint_coord"), pair.right_coord_x, pair.right_coord_y)
        and isinstance(evidence.get("supporting_line_ids"), list)
        and bool(evidence["supporting_line_ids"])
        and pair.line_group_id == evidence.get("line_group_id")
    )


def _has_complete_table_chain_evidence(pair: Pair) -> bool:
    evidence = pair.evidence or {}
    mapping = evidence.get("table_mapping")
    if not isinstance(mapping, dict):
        return False
    return (
        _nonempty_text(evidence.get("filename"))
        and _nonempty_text(evidence.get("sheet_no"))
        and _nonempty_text(pair.left_text_id)
        and _nonempty_text(pair.right_text_id)
        and _finite_coordinate([pair.left_coord_x, pair.left_coord_y])
        and _finite_coordinate([pair.right_coord_x, pair.right_coord_y])
        and _finite_coordinate(mapping.get("middle_coord"))
        and _finite_coordinate(mapping.get("header_coord"))
        and _finite_coordinate(mapping.get("right_coord"))
    )


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
    scopes = [(str(pair.sheet_id or "").strip(), str(pair.file_id or "").strip()) for pair in linked_pairs]
    if any(not sheet_id or not file_id for sheet_id, file_id in scopes) or len(set(scopes)) != len(scopes):
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
        member_ids = {pair.pair_id for pair in members}
        continuations = [
            pair
            for pair in pairs
            if pair.pair_id not in member_ids
            and pair.pair_kind == "component_mapping"
            and _is_chain_member(pair)
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
        "right_text_id": pair.right_text_id,
        "right_coord": [pair.right_coord_x, pair.right_coord_y],
        "line_group_id": pair.line_group_id,
        "scope_key": [pair.sheet_id, pair.file_id],
        "producer_evidence": {
            "source": evidence.get("source"),
            "pair_kind": pair.pair_kind,
            "component_submode": submode,
            "mapping_mode": ((evidence.get("table_mapping") or {}).get("mapping_mode")
                             if isinstance(evidence.get("table_mapping"), dict) else None),
            "left_text_id": pair.left_text_id,
            "right_text_id": pair.right_text_id,
            "left_coord": [pair.left_coord_x, pair.left_coord_y],
            "right_coord": [pair.right_coord_x, pair.right_coord_y],
        },
    }


def summarize_terminal_series_chains(chains: list[dict]) -> dict:
    circuit_members = sum(
        sum(member.get("role") == "circuit_side" for member in chain["members"])
        for chain in chains
    )
    component_members = sum(
        sum(member.get("role") == "component_side" for member in chain["members"])
        for chain in chains
    )
    chart_members = sum(
        sum(member.get("role") == "chart_side" for member in chain["members"])
        for chain in chains
    )
    return {
        "schema_version": _CHAIN_SCHEMA_VERSION,
        "chain_count": len(chains),
        "junction_values": [chain["junction_value"] for chain in chains],
        "circuit_side_member_count": circuit_members,
        "component_side_member_count": component_members,
        "chart_side_member_count": chart_members,
        "circuit_side_distinct_value_count": sum(len(chain["circuit_side_values"]) for chain in chains),
        "component_side_distinct_value_count": sum(len(chain["component_side_values"]) for chain in chains),
        "chart_side_distinct_value_count": sum(len(chain["chart_side_values"]) for chain in chains),
        "continuation_count": sum(chain["continuation_count"] for chain in chains),
    }
