from __future__ import annotations

import pytest

from dwg_audit.audit.electrical_semantics import AuthorityState
from dwg_audit.audit.electrical_semantics import ConstraintState
from dwg_audit.audit.electrical_semantics import ElectricalSemanticNode
from dwg_audit.audit.electrical_semantics import ElectricalSemanticRelation
from dwg_audit.audit.electrical_semantics import EvidenceSource
from dwg_audit.audit.electrical_semantics import EvidenceState
from dwg_audit.audit.electrical_semantics import SemanticKind
from dwg_audit.audit.electrical_semantics import SemanticRelationKind
from dwg_audit.audit.electrical_semantics import SemanticRole
from dwg_audit.audit.electrical_semantics import build_electrical_semantic_graph
from dwg_audit.audit.electrical_semantics import can_form_electrical_union
from dwg_audit.audit.electrical_semantics import validate_relation_constraints


def _token(
    token_id: str,
    token_kind: str,
    text: str,
    *,
    sheet_id: str = "S1",
    confidence: float = 0.9,
    **extra: object,
) -> dict:
    return {
        "token_id": token_id,
        "text_id": token_id.removeprefix("TK-"),
        "sheet_id": sheet_id,
        "file_id": "F1",
        "token_kind": token_kind,
        "raw_text": text,
        "normalized_text": text,
        "confidence": confidence,
        "reason_codes": [f"MATCH_{token_kind}"],
        **extra,
    }


def _attachment(
    *,
    attachment_id: str = "SA0001",
    token_id: str = "TK-PORT",
    authority: str | None = "AUTHORITATIVE",
    selected: bool = True,
    state: str = "SELECTED",
    scope_state: str = "RESOLVED",
) -> dict:
    row = {
        "attachment_id": attachment_id,
        "sheet_id": "S1",
        "token_id": token_id,
        "token_kind": "TERMINAL_LOCAL",
        "token_text": "12",
        "target_kind": "LINE_ENDPOINT",
        "target_line_id": "L1",
        "target_endpoint": "end",
        "target_x": 10.0,
        "target_y": 20.0,
        "selected": selected,
        "state": state,
        "score": 0.96,
        "scope_state": scope_state,
        "reason_codes": ["NEAREST_LINE_ENDPOINT"],
    }
    if authority is not None:
        row["constraint_authority"] = authority
    return row


def test_token_projection_normalizes_semantic_kinds_and_roles() -> None:
    tokens = [
        _token("TK-SCOPE", "SCOPED_PREFIX", "1n", prefix="1"),
        _token("TK-WIRE", "WIRE_N_NUMBER", "n12", local_number="12"),
        _token("TK-BODY", "COMPONENT_BODY", "1KLP1", family="KLP", ordinal="1"),
        _token("TK-PORT", "COMPONENT_PORT", "1", ordinal="1"),
        _token("TK-EXT", "EXTERNAL_ENDPOINT", "1QD2", family="QD", ordinal="2"),
        _token("TK-TERM", "TERMINAL_LOCAL", "12", local_number="12"),
        _token("TK-DEVICE", "DEVICE_TAG", "1ID1", family="ID", ordinal="1"),
        _token("TK-REF", "PAGE_REFERENCE", "see page"),
        _token("TK-NOTE", "ANNOTATION", "note", confidence=0.4),
    ]

    graph = build_electrical_semantic_graph(tokens, project_id="P1")
    by_token = {
        node.attributes.get("token_id"): node
        for node in graph.nodes
        if node.attributes.get("token_id")
    }

    assert by_token["TK-SCOPE"].semantic_kind is SemanticKind.SCOPE
    assert by_token["TK-SCOPE"].role is SemanticRole.ENTITY
    assert by_token["TK-WIRE"].role is SemanticRole.NETWORK
    assert by_token["TK-BODY"].role is SemanticRole.DEVICE
    assert by_token["TK-PORT"].role is SemanticRole.PORT
    assert by_token["TK-EXT"].semantic_kind is SemanticKind.EXTERNAL_ENDPOINT
    assert by_token["TK-TERM"].semantic_kind is SemanticKind.TERMINAL
    assert by_token["TK-DEVICE"].semantic_kind is SemanticKind.DEVICE
    assert by_token["TK-REF"].role is SemanticRole.CROSS_PAGE_REFERENCE
    assert by_token["TK-NOTE"].semantic_kind is SemanticKind.ANNOTATION
    assert by_token["TK-NOTE"].authority is AuthorityState.REVIEW_ONLY
    assert graph.relations == ()


def test_authoritative_attachment_is_asserted_but_remains_shadow_only() -> None:
    tokens = [_token("TK-PORT", "TERMINAL_LOCAL", "12", local_number="12")]

    graph = build_electrical_semantic_graph(
        tokens,
        [_attachment()],
        project_id="P1",
    )

    relation = next(
        item
        for item in graph.relations
        if item.relation_kind is SemanticRelationKind.ATTACHED_TO_NETWORK
    )
    target = next(node for node in graph.nodes if node.node_id == relation.target_node_id)
    assert relation.state is EvidenceState.ASSERTED
    assert relation.authority is AuthorityState.AUTHORITATIVE
    assert relation.shadow_only is True
    assert relation.requests_electrical_union is False
    assert can_form_electrical_union(relation) is False
    assert target.role is SemanticRole.NETWORK
    assert target.semantic_kind is SemanticKind.NETWORK_ENDPOINT
    sources = {item.source for item in graph.evidence}
    assert EvidenceSource.TEXT_TOKEN in sources
    assert EvidenceSource.SEMANTIC_ATTACHMENT in sources
    assert graph.to_dict()["summary"]["electrical_union_eligible_count"] == 0


@pytest.mark.parametrize(
    ("state", "authority"),
    [
        (EvidenceState.UNKNOWN, AuthorityState.UNKNOWN),
        (EvidenceState.POSSIBLE, AuthorityState.REVIEW_ONLY),
        (EvidenceState.REJECTED, AuthorityState.REJECTED),
    ],
)
def test_unknown_possible_and_rejected_relations_never_union(
    state: EvidenceState,
    authority: AuthorityState,
) -> None:
    relation = ElectricalSemanticRelation(
        relation_id=f"R-{state.value}",
        relation_kind=SemanticRelationKind.ELECTRICALLY_CONNECTED,
        source_node_id="N1",
        target_node_id="N2",
        project_id="P1",
        sheet_id="S1",
        state=state,
        authority=authority,
        confidence=1.0,
        requests_electrical_union=True,
        shadow_only=False,
    )

    assert can_form_electrical_union(relation) is False
    constraints = validate_relation_constraints([], [relation])
    union_gate = next(
        item for item in constraints if item.constraint_kind == "ELECTRICAL_UNION_GATE"
    )
    assert union_gate.state is ConstraintState.VIOLATION
    assert "NON_ASSERTED_STATE" in union_gate.reason_codes


def test_only_asserted_authoritative_non_shadow_relation_can_union() -> None:
    relation = ElectricalSemanticRelation(
        relation_id="R-ASSERTED",
        relation_kind=SemanticRelationKind.ELECTRICALLY_CONNECTED,
        source_node_id="N1",
        target_node_id="N2",
        project_id="P1",
        sheet_id="S1",
        state=EvidenceState.ASSERTED,
        authority=AuthorityState.AUTHORITATIVE,
        confidence=1.0,
        requests_electrical_union=True,
        shadow_only=False,
    )
    assert can_form_electrical_union(relation) is True


def test_asserted_authoritative_shadow_relation_still_cannot_union() -> None:
    relation = ElectricalSemanticRelation(
        relation_id="R-SHADOW",
        relation_kind=SemanticRelationKind.ELECTRICALLY_CONNECTED,
        source_node_id="N1",
        target_node_id="N2",
        project_id="P1",
        sheet_id="S1",
        state=EvidenceState.ASSERTED,
        authority=AuthorityState.AUTHORITATIVE,
        confidence=1.0,
        requests_electrical_union=True,
        shadow_only=True,
    )
    assert can_form_electrical_union(relation) is False
    union_gate = next(
        item
        for item in validate_relation_constraints([], [relation])
        if item.constraint_kind == "ELECTRICAL_UNION_GATE"
    )
    assert union_gate.state is ConstraintState.VIOLATION
    assert union_gate.reason_codes == ("SHADOW_ONLY_RELATION",)


def test_multiple_attachment_candidates_merge_network_node_evidence() -> None:
    tokens = [
        _token("TK-PORT", "TERMINAL_LOCAL", "12", local_number="12"),
        _token("TK-ALT", "WIRE_N_NUMBER", "n12", local_number="12"),
    ]
    attachments = [
        _attachment(attachment_id="SA0001", token_id="TK-PORT"),
        _attachment(
            attachment_id="SA0002",
            token_id="TK-ALT",
            authority="REVIEW_ONLY",
        ),
    ]

    graph = build_electrical_semantic_graph(tokens, attachments, project_id="P1")

    network_nodes = [node for node in graph.nodes if node.role is SemanticRole.NETWORK]
    endpoint = next(
        node
        for node in network_nodes
        if node.semantic_kind is SemanticKind.NETWORK_ENDPOINT
    )
    assert set(endpoint.source_ids) == {"SA0001", "SA0002"}
    assert len(endpoint.evidence_ids) == 2
    attached_relations = [
        item
        for item in graph.relations
        if item.relation_kind is SemanticRelationKind.ATTACHED_TO_NETWORK
    ]
    assert len(attached_relations) == 2


def test_body_port_scope_builds_role_checked_dependency() -> None:
    tokens = [
        _token("TK-BODY", "COMPONENT_BODY", "1KLP1", family="KLP", ordinal="1"),
        _token("TK-PORT", "COMPONENT_PORT", "1", ordinal="1"),
    ]
    decisions = [
        {
            "decision_id": "SD0001",
            "sheet_id": "S1",
            "scope_kind": "BODY_PORT",
            "scope_key": "1KLP1",
            "owner_token_id": "TK-BODY",
            "member_token_ids": ["TK-PORT"],
            "state": "RESOLVED",
            "confidence": 0.93,
            "reason_codes": ["NEAREST_BODY"],
        }
    ]

    graph = build_electrical_semantic_graph(
        tokens,
        scope_decisions=decisions,
        project_id="P1",
    )

    relation = next(
        item
        for item in graph.relations
        if item.relation_kind is SemanticRelationKind.PORT_OF_DEVICE
    )
    source = next(node for node in graph.nodes if node.node_id == relation.source_node_id)
    target = next(node for node in graph.nodes if node.node_id == relation.target_node_id)
    assert source.role is SemanticRole.PORT
    assert target.role is SemanticRole.DEVICE
    assert relation.state is EvidenceState.ASSERTED
    assert relation.authority is AuthorityState.AUTHORITATIVE
    assert relation.electrical_union_eligible is False
    assert "1klp1" in source.canonical_key
    relation_constraints = [
        item for item in graph.constraints if item.relation_id == relation.relation_id
    ]
    assert all(item.state is not ConstraintState.VIOLATION for item in relation_constraints)
    assert graph.valid is True


@pytest.mark.parametrize(
    ("scope_state", "expected_state", "expected_authority"),
    [
        ("AMBIGUOUS", EvidenceState.POSSIBLE, AuthorityState.REVIEW_ONLY),
        ("CONFLICT", EvidenceState.REJECTED, AuthorityState.REJECTED),
        ("UNSCOPED", EvidenceState.UNKNOWN, AuthorityState.UNKNOWN),
    ],
)
def test_uncertain_scope_relations_are_preserved_without_union(
    scope_state: str,
    expected_state: EvidenceState,
    expected_authority: AuthorityState,
) -> None:
    tokens = [
        _token("TK-SCOPE", "SCOPED_PREFIX", "1n", prefix="1"),
        _token("TK-TERM", "TERMINAL_LOCAL", "12", local_number="12"),
    ]
    decisions = [
        {
            "decision_id": "SD0001",
            "sheet_id": "S1",
            "scope_kind": "SCOPED_PREFIX",
            "scope_key": "1",
            "owner_token_id": "TK-SCOPE",
            "member_token_ids": ["TK-TERM"],
            "state": scope_state,
            "confidence": 0.7,
            "reason_codes": ["SCOPE_EVIDENCE"],
        }
    ]

    graph = build_electrical_semantic_graph(
        tokens,
        scope_decisions=decisions,
        project_id="P1",
    )
    relation = graph.relations[0]
    assert relation.state is expected_state
    assert relation.authority is expected_authority
    assert relation.electrical_union_eligible is False


def test_strong_constraint_violation_demotes_attachment_to_rejected() -> None:
    tokens = [_token("TK-PORT", "TERMINAL_LOCAL", "12", local_number="12")]
    decisions = [
        {
            "decision_id": "CR0001",
            "attachment_id": "SA0001",
            "sheet_id": "S1",
            "constraint_kind": "ONE_SELECTED_PER_TOKEN",
            "severity": "STRONG",
            "state": "VIOLATION",
            "authority": "REJECTED",
            "reason_codes": ["DUPLICATE_SELECTED"],
        }
    ]

    graph = build_electrical_semantic_graph(
        tokens,
        [_attachment()],
        constraint_decisions=decisions,
        project_id="P1",
    )

    relation = next(
        item
        for item in graph.relations
        if item.relation_kind is SemanticRelationKind.ATTACHED_TO_NETWORK
    )
    assert relation.state is EvidenceState.REJECTED
    assert relation.authority is AuthorityState.REJECTED
    assert "DUPLICATE_SELECTED" in relation.reason_codes
    assert relation.electrical_union_eligible is False
    assert EvidenceSource.CONSTRAINT_DECISION in {
        item.source for item in graph.evidence
    }


def test_explicit_cross_page_target_links_reference_to_profile_page() -> None:
    tokens = [
        _token(
            "TK-REF",
            "PAGE_REFERENCE",
            "see page",
            sheet_id="S1",
            target_sheet_id="S2",
        )
    ]
    profile = {
        "project_id": "P1",
        "page_catalog": [
            {"sheet_id": "S1", "sheet_title": "Source"},
            {"sheet_id": "S2", "sheet_title": "Target"},
        ],
    }

    graph = build_electrical_semantic_graph(tokens, project_profile=profile)

    relation = next(
        item
        for item in graph.relations
        if item.relation_kind is SemanticRelationKind.REFERENCES_PAGE
    )
    source = next(node for node in graph.nodes if node.node_id == relation.source_node_id)
    target = next(node for node in graph.nodes if node.node_id == relation.target_node_id)
    assert source.role is SemanticRole.CROSS_PAGE_REFERENCE
    assert target.role is SemanticRole.PAGE
    assert target.sheet_id == "S2"
    assert relation.state is EvidenceState.POSSIBLE
    assert relation.electrical_union_eligible is False
    assert graph.valid is True


def test_missing_scope_owner_is_retained_as_a_constraint_violation() -> None:
    tokens = [_token("TK-PORT", "COMPONENT_PORT", "1", ordinal="1")]
    decisions = [
        {
            "decision_id": "SD0001",
            "sheet_id": "S1",
            "scope_kind": "BODY_PORT",
            "scope_key": "missing",
            "owner_token_id": "TK-MISSING",
            "member_token_ids": ["TK-PORT"],
            "state": "RESOLVED",
            "confidence": 0.9,
            "reason_codes": ["BROKEN_FIXTURE"],
        }
    ]

    graph = build_electrical_semantic_graph(
        tokens,
        scope_decisions=decisions,
        project_id="P1",
    )

    assert graph.valid is False
    target_checks = [
        item
        for item in graph.constraints
        if item.constraint_kind == "TARGET_NODE_EXISTS"
    ]
    assert len(target_checks) == 1
    assert target_checks[0].state is ConstraintState.VIOLATION
    assert target_checks[0].reason_codes == ("TARGET_NODE_MISSING",)
    payload = graph.to_dict()
    assert payload["summary"]["constraint_violation_count"] >= 1
    assert payload["summary"]["electrical_union_eligible_count"] == 0


def test_role_constraint_rejects_port_owner_with_wrong_target_role() -> None:
    source = ElectricalSemanticNode(
        node_id="N1",
        semantic_kind=SemanticKind.PORT,
        role=SemanticRole.PORT,
        canonical_key="port:1",
        label="1",
        project_id="P1",
        sheet_id="S1",
        source_ids=(),
        evidence_ids=(),
        confidence=1.0,
        authority=AuthorityState.AUTHORITATIVE,
    )
    target = ElectricalSemanticNode(
        node_id="N2",
        semantic_kind=SemanticKind.WIRE_IDENTITY,
        role=SemanticRole.NETWORK,
        canonical_key="wire:1",
        label="1",
        project_id="P1",
        sheet_id="S1",
        source_ids=(),
        evidence_ids=(),
        confidence=1.0,
        authority=AuthorityState.AUTHORITATIVE,
    )
    relation = ElectricalSemanticRelation(
        relation_id="R1",
        relation_kind=SemanticRelationKind.PORT_OF_DEVICE,
        source_node_id="N1",
        target_node_id="N2",
        project_id="P1",
        sheet_id="S1",
        state=EvidenceState.ASSERTED,
        authority=AuthorityState.AUTHORITATIVE,
        confidence=1.0,
    )

    checks = validate_relation_constraints([source, target], [relation])
    role_check = next(item for item in checks if item.constraint_kind == "ROLE_COMPATIBILITY")
    assert role_check.state is ConstraintState.VIOLATION
    assert role_check.reason_codes == ("TARGET_ROLE_INCOMPATIBLE",)
