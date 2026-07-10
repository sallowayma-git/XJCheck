"""Pseudocode for deterministic geometry candidates and auditable decisions."""

from dataclasses import dataclass
from enum import Enum


class DecisionState(str, Enum):
    ASSERTED = "ASSERTED"
    POSSIBLE = "POSSIBLE"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TopologyCandidate:
    candidate_id: str
    relation_type: str
    object_a: str
    object_b: str
    location: tuple[float, float]
    features: dict[str, float | str | bool]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class TopologyDecision:
    candidate_id: str
    state: DecisionState
    confidence: float
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]


def build_candidates(primitives, spatial_index, config):
    candidates = []

    # Strong candidates from exact CAD geometry.
    for endpoint in primitives.endpoints:
        for other in spatial_index.endpoints_near(endpoint, config.snap_tolerance):
            candidates.append(candidate_endpoint_endpoint(endpoint, other))
        for segment in spatial_index.segments_near(endpoint, config.on_segment_tolerance):
            if segment.parent_id != endpoint.parent_id:
                candidates.append(candidate_endpoint_on_segment(endpoint, segment))

    # Segment intersections are observations, not automatic electrical unions.
    for segment_a, segment_b in spatial_index.intersecting_segment_pairs():
        intersection = exact_intersection(segment_a, segment_b)
        if intersection:
            candidates.append(candidate_segment_crossing(segment_a, segment_b, intersection))

    # Gap candidates retain all evidence; text/block evidence cannot directly union.
    for endpoint_a, endpoint_b in spatial_index.collinear_open_endpoint_pairs(config.max_gap):
        candidates.append(
            TopologyCandidate(
                candidate_id=new_id("TC"),
                relation_type="gap_bridge",
                object_a=endpoint_a.id,
                object_b=endpoint_b.id,
                location=midpoint(endpoint_a.xy, endpoint_b.xy),
                features={
                    "gap": distance(endpoint_a.xy, endpoint_b.xy),
                    "angle_delta": angle_delta(endpoint_a.tangent, endpoint_b.tangent),
                    "same_layer": endpoint_a.layer == endpoint_b.layer,
                    "intervening_text_count": spatial_index.text_between(endpoint_a, endpoint_b),
                    "intervening_block_count": spatial_index.blocks_between(endpoint_a, endpoint_b),
                    "competing_segment_count": spatial_index.competing_segments(endpoint_a, endpoint_b),
                },
                evidence_ids=(endpoint_a.id, endpoint_b.id),
            )
        )
    return candidates


def decide_candidate(candidate, evidence_context, config) -> TopologyDecision:
    f = candidate.features

    if candidate.relation_type == "endpoint_endpoint":
        if f["distance"] <= config.strong_snap and not f["conflicting_layers"]:
            return decision(candidate, DecisionState.ASSERTED, 1.0, "EXACT_ENDPOINT_SNAP")

    if candidate.relation_type == "endpoint_on_segment":
        if f["perpendicular_distance"] <= config.on_segment_tolerance:
            return decision(candidate, DecisionState.ASSERTED, 0.999, "T_JUNCTION_ENDPOINT_ON_BODY")

    if candidate.relation_type == "segment_crossing":
        if evidence_context.has_bridge_arc(candidate.location):
            return decision(candidate, DecisionState.REJECTED, 0.999, "BRIDGE_ARC_NON_CONNECTING")
        if evidence_context.has_verified_junction_dot(candidate.location):
            return decision(candidate, DecisionState.ASSERTED, 0.999, "EXPLICIT_JUNCTION_DOT")
        if f["one_segment_ends_here"]:
            return decision(candidate, DecisionState.ASSERTED, 0.999, "ENDPOINT_AT_CROSSING")
        return decision(candidate, DecisionState.POSSIBLE, 0.50, "CROSSING_WITHOUT_CONNECTIVITY_MARKER")

    if candidate.relation_type == "gap_bridge":
        symbol = evidence_context.symbol_covering_gap(candidate)
        if symbol and symbol.is_human_verified and symbol.behavior == "pass_through":
            return decision(candidate, DecisionState.ASSERTED, 0.999, "VERIFIED_SYMBOL_PASS_THROUGH")
        if f["intervening_text_count"] > 0 or f["intervening_block_count"] > 0:
            # Important: text or block-center proximity is evidence, not truth.
            return decision(candidate, DecisionState.POSSIBLE, 0.70, "INLINE_OBJECT_GAP_CANDIDATE")
        return decision(candidate, DecisionState.UNKNOWN, 0.20, "UNEXPLAINED_GAP")

    return decision(candidate, DecisionState.UNKNOWN, 0.0, "UNSUPPORTED_RELATION")


def materialize_geometry_graph(primitives, decisions):
    graph = GeometryGraph()
    graph.add_primitive_segments(primitives.segments)

    # Split segments at asserted T/intersection nodes only.
    for decision in decisions:
        if decision.state == DecisionState.ASSERTED:
            graph.apply_asserted_relation(decision)
        else:
            graph.add_boundary_decision(decision)

    # Connected components use only asserted edges.
    graph.assert_no_possible_relation_in_components()
    return graph
