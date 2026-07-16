"""Reusable electrical semantic dependency model.

The builders in this module project the current token, attachment, scope and
constraint records into a typed shadow graph.  The graph records semantic
dependencies only: it never mutates geometry, electrical networks, Pair rows or
Issue rows.

Electrical union is deliberately fail closed.  A relation can be union eligible
only when it explicitly requests union, is not shadow-only, and is both
``ASSERTED`` and ``AUTHORITATIVE``.  Relations projected from the current
semantic pipeline are always shadow-only.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum
import hashlib
import json
import math
from typing import Any
from typing import Iterable
from typing import Mapping


SCHEMA_VERSION = "electrical-semantics-v1"
ALGORITHM_VERSION = "shadow-semantic-dependency-v1"


class SemanticKind(StrEnum):
    UNKNOWN = "UNKNOWN"
    ANNOTATION = "ANNOTATION"
    SCOPE = "SCOPE"
    DEVICE = "DEVICE"
    COMPONENT = "COMPONENT"
    TERMINAL_STRIP = "TERMINAL_STRIP"
    PORT = "PORT"
    TERMINAL = "TERMINAL"
    EXTERNAL_ENDPOINT = "EXTERNAL_ENDPOINT"
    WIRE_IDENTITY = "WIRE_IDENTITY"
    NETWORK_ENDPOINT = "NETWORK_ENDPOINT"
    PAGE = "PAGE"
    CROSS_PAGE_REFERENCE = "CROSS_PAGE_REFERENCE"


class SemanticRole(StrEnum):
    ENTITY = "ENTITY"
    DEVICE = "DEVICE"
    PORT = "PORT"
    NETWORK = "NETWORK"
    PAGE = "PAGE"
    CROSS_PAGE_REFERENCE = "CROSS_PAGE_REFERENCE"


class EvidenceSource(StrEnum):
    TEXT_TOKEN = "TEXT_TOKEN"
    SEMANTIC_ATTACHMENT = "SEMANTIC_ATTACHMENT"
    SCOPE_DECISION = "SCOPE_DECISION"
    CONSTRAINT_DECISION = "CONSTRAINT_DECISION"
    PROJECT_PROFILE = "PROJECT_PROFILE"


class EvidenceState(StrEnum):
    ASSERTED = "ASSERTED"
    POSSIBLE = "POSSIBLE"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class AuthorityState(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"
    REVIEW_ONLY = "REVIEW_ONLY"
    OBSERVATIONAL = "OBSERVATIONAL"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class SemanticRelationKind(StrEnum):
    ATTACHED_TO_NETWORK = "ATTACHED_TO_NETWORK"
    PORT_OF_DEVICE = "PORT_OF_DEVICE"
    IN_SCOPE_OF = "IN_SCOPE_OF"
    IN_SEMANTIC_ROW = "IN_SEMANTIC_ROW"
    DEPENDS_ON = "DEPENDS_ON"
    REFERENCES_PAGE = "REFERENCES_PAGE"
    ELECTRICALLY_CONNECTED = "ELECTRICALLY_CONNECTED"


class ConstraintState(StrEnum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    VIOLATION = "VIOLATION"


_TOKEN_SEMANTICS: dict[str, tuple[SemanticKind, SemanticRole]] = {
    "SCOPED_PREFIX": (SemanticKind.SCOPE, SemanticRole.ENTITY),
    "WIRE_N_NUMBER": (SemanticKind.WIRE_IDENTITY, SemanticRole.NETWORK),
    "COMPONENT_BODY": (SemanticKind.COMPONENT, SemanticRole.DEVICE),
    "COMPONENT_PORT": (SemanticKind.PORT, SemanticRole.PORT),
    "EXTERNAL_ENDPOINT": (SemanticKind.EXTERNAL_ENDPOINT, SemanticRole.PORT),
    "TERMINAL_LOCAL": (SemanticKind.TERMINAL, SemanticRole.PORT),
    "DEVICE_TAG": (SemanticKind.DEVICE, SemanticRole.DEVICE),
    "PAGE_REFERENCE": (
        SemanticKind.CROSS_PAGE_REFERENCE,
        SemanticRole.CROSS_PAGE_REFERENCE,
    ),
    "ANNOTATION": (SemanticKind.ANNOTATION, SemanticRole.ENTITY),
}

_LOCAL_RELATIONS = frozenset(
    {
        SemanticRelationKind.ATTACHED_TO_NETWORK,
        SemanticRelationKind.PORT_OF_DEVICE,
        SemanticRelationKind.IN_SCOPE_OF,
        SemanticRelationKind.IN_SEMANTIC_ROW,
        SemanticRelationKind.DEPENDS_ON,
        SemanticRelationKind.ELECTRICALLY_CONNECTED,
    }
)


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    evidence_id: str
    source: EvidenceSource
    source_id: str
    sheet_id: str | None
    state: EvidenceState
    authority: AuthorityState
    confidence: float
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source.value,
            "source_id": self.source_id,
            "sheet_id": self.sheet_id,
            "state": self.state.value,
            "authority": self.authority.value,
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ElectricalSemanticNode:
    node_id: str
    semantic_kind: SemanticKind
    role: SemanticRole
    canonical_key: str
    label: str | None
    project_id: str | None
    sheet_id: str | None
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float
    authority: AuthorityState
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "semantic_kind": self.semantic_kind.value,
            "role": self.role.value,
            "canonical_key": self.canonical_key,
            "label": self.label,
            "project_id": self.project_id,
            "sheet_id": self.sheet_id,
            "source_ids": list(self.source_ids),
            "evidence_ids": list(self.evidence_ids),
            "confidence": self.confidence,
            "authority": self.authority.value,
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class ElectricalSemanticRelation:
    relation_id: str
    relation_kind: SemanticRelationKind
    source_node_id: str
    target_node_id: str
    project_id: str | None
    sheet_id: str | None
    state: EvidenceState
    authority: AuthorityState
    confidence: float
    evidence_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    requests_electrical_union: bool = False
    shadow_only: bool = True

    @property
    def electrical_union_eligible(self) -> bool:
        return (
            self.requests_electrical_union
            and not self.shadow_only
            and self.state is EvidenceState.ASSERTED
            and self.authority is AuthorityState.AUTHORITATIVE
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "relation_kind": self.relation_kind.value,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "project_id": self.project_id,
            "sheet_id": self.sheet_id,
            "state": self.state.value,
            "authority": self.authority.value,
            "confidence": self.confidence,
            "evidence_ids": list(self.evidence_ids),
            "reason_codes": list(self.reason_codes),
            "requests_electrical_union": self.requests_electrical_union,
            "electrical_union_eligible": self.electrical_union_eligible,
            "shadow_only": self.shadow_only,
        }


@dataclass(frozen=True, slots=True)
class RelationConstraintResult:
    constraint_id: str
    relation_id: str
    constraint_kind: str
    state: ConstraintState
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "relation_id": self.relation_id,
            "constraint_kind": self.constraint_kind,
            "state": self.state.value,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ElectricalSemanticGraph:
    project_id: str | None
    nodes: tuple[ElectricalSemanticNode, ...]
    relations: tuple[ElectricalSemanticRelation, ...]
    evidence: tuple[CandidateEvidence, ...]
    constraints: tuple[RelationConstraintResult, ...]
    schema_version: str = SCHEMA_VERSION
    algorithm_version: str = ALGORITHM_VERSION
    shadow_only: bool = True

    @property
    def valid(self) -> bool:
        return not any(
            item.state is ConstraintState.VIOLATION for item in self.constraints
        )

    def to_dict(self) -> dict[str, Any]:
        role_counts = Counter(node.role.value for node in self.nodes)
        relation_state_counts = Counter(relation.state.value for relation in self.relations)
        violation_count = sum(
            item.state is ConstraintState.VIOLATION for item in self.constraints
        )
        return {
            "schema_version": self.schema_version,
            "algorithm_version": self.algorithm_version,
            "project_id": self.project_id,
            "shadow_only": self.shadow_only,
            "valid": self.valid,
            "nodes": [node.to_dict() for node in self.nodes],
            "relations": [relation.to_dict() for relation in self.relations],
            "evidence": [item.to_dict() for item in self.evidence],
            "constraints": [item.to_dict() for item in self.constraints],
            "summary": {
                "node_count": len(self.nodes),
                "relation_count": len(self.relations),
                "evidence_count": len(self.evidence),
                "constraint_count": len(self.constraints),
                "constraint_violation_count": violation_count,
                "electrical_union_eligible_count": sum(
                    relation.electrical_union_eligible for relation in self.relations
                ),
                "blocked_union_request_count": sum(
                    relation.requests_electrical_union
                    and not relation.electrical_union_eligible
                    for relation in self.relations
                ),
                "by_role": dict(sorted(role_counts.items())),
                "by_relation_state": dict(sorted(relation_state_counts.items())),
            },
        }


def build_electrical_semantic_graph(
    text_tokens: Iterable[Mapping[str, Any]] | Any,
    semantic_attachments: Iterable[Mapping[str, Any]] | Any | None = None,
    scope_decisions: Iterable[Mapping[str, Any]] | Any | None = None,
    constraint_decisions: Iterable[Mapping[str, Any]] | Any | None = None,
    project_profile: Mapping[str, Any] | None = None,
    *,
    project_id: str | None = None,
) -> ElectricalSemanticGraph:
    """Build a deterministic shadow-only electrical semantic dependency graph."""
    token_rows = _records(text_tokens)
    attachment_rows = _records(semantic_attachments)
    scope_rows = _records(scope_decisions)
    constraint_rows = _records(constraint_decisions)
    profile = dict(project_profile or {})
    resolved_project_id = project_id or _nullable_text(profile.get("project_id"))

    nodes: dict[str, ElectricalSemanticNode] = {}
    relations: dict[str, ElectricalSemanticRelation] = {}
    evidence: dict[str, CandidateEvidence] = {}
    token_node_ids: dict[str, str] = {}
    page_node_ids: dict[str, str] = {}
    scope_by_token = _scope_keys(scope_rows, attachment_rows)

    def add_evidence(item: CandidateEvidence) -> None:
        evidence.setdefault(item.evidence_id, item)

    def add_node(item: ElectricalSemanticNode) -> None:
        existing = nodes.get(item.node_id)
        nodes[item.node_id] = item if existing is None else _merge_nodes(existing, item)

    def add_relation(item: ElectricalSemanticRelation) -> None:
        relations.setdefault(item.relation_id, item)

    _add_profile_nodes(
        profile,
        project_id=resolved_project_id,
        nodes=nodes,
        evidence=evidence,
        page_node_ids=page_node_ids,
    )

    token_rows_by_id: dict[str, dict[str, Any]] = {}
    for index, token in enumerate(token_rows):
        source_id = _record_id(token, ("token_id", "text_id"), index=index)
        token_id = _nullable_text(token.get("token_id")) or source_id
        token_rows_by_id[token_id] = token
        sheet_id = _nullable_text(token.get("sheet_id"))
        token_kind = str(token.get("token_kind") or "").upper()
        semantic_kind, role = _TOKEN_SEMANTICS.get(
            token_kind,
            (SemanticKind.UNKNOWN, SemanticRole.ENTITY),
        )
        confidence = _confidence(token.get("confidence"))
        evidence_state = (
            EvidenceState.UNKNOWN
            if semantic_kind is SemanticKind.UNKNOWN
            else EvidenceState.POSSIBLE
            if semantic_kind is SemanticKind.ANNOTATION
            else EvidenceState.ASSERTED
        )
        authority = (
            AuthorityState.UNKNOWN
            if evidence_state is EvidenceState.UNKNOWN
            else AuthorityState.REVIEW_ONLY
        )
        token_evidence = _evidence(
            source=EvidenceSource.TEXT_TOKEN,
            source_id=source_id,
            sheet_id=sheet_id,
            state=evidence_state,
            authority=authority,
            confidence=confidence,
            reason_codes=_reason_codes(token),
        )
        add_evidence(token_evidence)
        node_id = _stable_id(
            "ESN1",
            resolved_project_id or "",
            sheet_id or "",
            "token",
            token_id,
        )
        token_node_ids[token_id] = node_id
        label = _nullable_text(
            token.get("normalized_text") or token.get("raw_text")
        )
        add_node(
            ElectricalSemanticNode(
                node_id=node_id,
                semantic_kind=semantic_kind,
                role=role,
                canonical_key=_token_canonical_key(
                    token,
                    semantic_kind,
                    scope_by_token.get(token_id),
                ),
                label=label,
                project_id=resolved_project_id,
                sheet_id=sheet_id,
                source_ids=(source_id,),
                evidence_ids=(token_evidence.evidence_id,),
                confidence=confidence,
                authority=authority,
                attributes={
                    "token_id": token_id,
                    "token_kind": token_kind or "UNKNOWN",
                    "text_id": _nullable_text(token.get("text_id")),
                    "prefix": _nullable_text(token.get("prefix")),
                    "family": _nullable_text(token.get("family")),
                    "ordinal": _nullable_text(token.get("ordinal")),
                    "local_number": _nullable_text(token.get("local_number")),
                    "scope_key": scope_by_token.get(token_id),
                },
            )
        )

    constraint_by_attachment: dict[str, list[dict[str, Any]]] = {}
    constraint_evidence_by_attachment: dict[str, list[str]] = {}
    for index, decision in enumerate(constraint_rows):
        attachment_id = _nullable_text(decision.get("attachment_id"))
        if attachment_id:
            constraint_by_attachment.setdefault(attachment_id, []).append(decision)
        source_id = _record_id(decision, ("decision_id",), index=index)
        decision_evidence = _evidence(
            source=EvidenceSource.CONSTRAINT_DECISION,
            source_id=source_id,
            sheet_id=_nullable_text(decision.get("sheet_id")),
            state=_constraint_decision_state(decision),
            authority=_authority(decision.get("authority")),
            confidence=1.0,
            reason_codes=_reason_codes(decision),
        )
        add_evidence(decision_evidence)
        if attachment_id:
            constraint_evidence_by_attachment.setdefault(attachment_id, []).append(
                decision_evidence.evidence_id
            )

    for index, attachment in enumerate(attachment_rows):
        attachment_id = _record_id(
            attachment,
            ("attachment_id",),
            index=index,
        )
        token_id = _nullable_text(attachment.get("token_id"))
        source_node_id = token_node_ids.get(
            token_id or "",
            _token_node_id(
                resolved_project_id,
                _nullable_text(attachment.get("sheet_id")),
                token_id or "missing-token",
            ),
        )
        sheet_id = _nullable_text(attachment.get("sheet_id"))
        state, authority = _attachment_state_authority(
            attachment,
            constraint_by_attachment.get(attachment_id, []),
        )
        confidence = _confidence(
            attachment.get("score", attachment.get("confidence"))
        )
        attachment_evidence = _evidence(
            source=EvidenceSource.SEMANTIC_ATTACHMENT,
            source_id=attachment_id,
            sheet_id=sheet_id,
            state=state,
            authority=authority,
            confidence=confidence,
            reason_codes=_combined_reasons(
                attachment,
                constraint_by_attachment.get(attachment_id, []),
            ),
        )
        add_evidence(attachment_evidence)
        constraint_evidence_ids = _unique_tuple(
            constraint_evidence_by_attachment.get(attachment_id, [])
        )

        target_node = _attachment_target_node(
            attachment,
            attachment_id=attachment_id,
            project_id=resolved_project_id,
            evidence_id=attachment_evidence.evidence_id,
            state=state,
            confidence=confidence,
        )
        add_node(target_node)
        relation = ElectricalSemanticRelation(
            relation_id=_stable_id(
                "ESR1",
                resolved_project_id or "",
                SemanticRelationKind.ATTACHED_TO_NETWORK.value,
                source_node_id,
                target_node.node_id,
                attachment_id,
            ),
            relation_kind=SemanticRelationKind.ATTACHED_TO_NETWORK,
            source_node_id=source_node_id,
            target_node_id=target_node.node_id,
            project_id=resolved_project_id,
            sheet_id=sheet_id,
            state=state,
            authority=authority,
            confidence=confidence,
            evidence_ids=_unique_tuple(
                (attachment_evidence.evidence_id, *constraint_evidence_ids)
            ),
            reason_codes=attachment_evidence.reason_codes,
            requests_electrical_union=False,
            shadow_only=True,
        )
        add_relation(relation)

    scope_relation_keys: set[tuple[str, str, str]] = set()
    for index, decision in enumerate(scope_rows):
        decision_id = _record_id(decision, ("decision_id",), index=index)
        sheet_id = _nullable_text(decision.get("sheet_id"))
        state, authority = _scope_state_authority(decision.get("state"))
        confidence = _confidence(decision.get("confidence"))
        scope_evidence = _evidence(
            source=EvidenceSource.SCOPE_DECISION,
            source_id=decision_id,
            sheet_id=sheet_id,
            state=state,
            authority=authority,
            confidence=confidence,
            reason_codes=_reason_codes(decision),
        )
        add_evidence(scope_evidence)
        scope_kind = str(decision.get("scope_kind") or "").upper()
        owner_token_id = _nullable_text(decision.get("owner_token_id"))
        if not owner_token_id:
            continue
        members = _string_list(decision.get("member_token_ids"))
        for member_token_id in members:
            scope_relation_keys.add((scope_kind, owner_token_id, member_token_id))
            add_relation(
                _scope_relation(
                    project_id=resolved_project_id,
                    sheet_id=sheet_id,
                    scope_kind=scope_kind,
                    owner_token_id=owner_token_id,
                    member_token_id=member_token_id,
                    decision_id=decision_id,
                    state=state,
                    authority=authority,
                    confidence=confidence,
                    evidence_id=scope_evidence.evidence_id,
                    reason_codes=scope_evidence.reason_codes,
                    token_node_ids=token_node_ids,
                )
            )

    # Scoped attachment rows are a useful fallback when compact decisions were
    # not persisted.  Explicit ScopeDecision rows always win.
    for index, attachment in enumerate(attachment_rows):
        scope_kind = str(attachment.get("scope_kind") or "").upper()
        owner_token_id = _nullable_text(attachment.get("scope_token_id"))
        member_token_id = _nullable_text(attachment.get("token_id"))
        key = (scope_kind, owner_token_id or "", member_token_id or "")
        if (
            not scope_kind
            or not owner_token_id
            or not member_token_id
            or key in scope_relation_keys
        ):
            continue
        attachment_id = _record_id(attachment, ("attachment_id",), index=index)
        state, authority = _scope_state_authority(attachment.get("scope_state"))
        confidence = _confidence(attachment.get("scope_confidence"))
        evidence_id = _evidence_id(EvidenceSource.SEMANTIC_ATTACHMENT, attachment_id)
        add_relation(
            _scope_relation(
                project_id=resolved_project_id,
                sheet_id=_nullable_text(attachment.get("sheet_id")),
                scope_kind=scope_kind,
                owner_token_id=owner_token_id,
                member_token_id=member_token_id,
                decision_id=f"{attachment_id}:scope",
                state=state,
                authority=authority,
                confidence=confidence,
                evidence_id=evidence_id,
                reason_codes=tuple(
                    _string_list(attachment.get("scope_reason_codes"))
                ),
                token_node_ids=token_node_ids,
            )
        )

    for token_id, token in token_rows_by_id.items():
        if str(token.get("token_kind") or "").upper() != "PAGE_REFERENCE":
            continue
        target_sheet_id = _nullable_text(
            token.get("target_sheet_id") or token.get("referenced_sheet_id")
        )
        if not target_sheet_id:
            continue
        target_node_id = page_node_ids.get(target_sheet_id)
        if target_node_id is None:
            target_node_id = _stable_id(
                "ESN1",
                resolved_project_id or "",
                "page",
                target_sheet_id,
            )
            add_node(
                ElectricalSemanticNode(
                    node_id=target_node_id,
                    semantic_kind=SemanticKind.PAGE,
                    role=SemanticRole.PAGE,
                    canonical_key=f"page:{target_sheet_id}",
                    label=None,
                    project_id=resolved_project_id,
                    sheet_id=target_sheet_id,
                    source_ids=(),
                    evidence_ids=(),
                    confidence=0.0,
                    authority=AuthorityState.UNKNOWN,
                    attributes={"sheet_id": target_sheet_id, "placeholder": True},
                )
            )
            page_node_ids[target_sheet_id] = target_node_id
        source_node_id = token_node_ids[token_id]
        token_node = nodes[source_node_id]
        add_relation(
            ElectricalSemanticRelation(
                relation_id=_stable_id(
                    "ESR1",
                    resolved_project_id or "",
                    SemanticRelationKind.REFERENCES_PAGE.value,
                    source_node_id,
                    target_node_id,
                ),
                relation_kind=SemanticRelationKind.REFERENCES_PAGE,
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                project_id=resolved_project_id,
                sheet_id=token_node.sheet_id,
                state=EvidenceState.POSSIBLE,
                authority=AuthorityState.REVIEW_ONLY,
                confidence=token_node.confidence,
                evidence_ids=token_node.evidence_ids,
                reason_codes=("EXPLICIT_TARGET_SHEET_FIELD",),
                requests_electrical_union=False,
                shadow_only=True,
            )
        )

    ordered_nodes = tuple(sorted(nodes.values(), key=lambda item: item.node_id))
    ordered_relations = tuple(
        sorted(relations.values(), key=lambda item: item.relation_id)
    )
    ordered_evidence = tuple(
        sorted(evidence.values(), key=lambda item: item.evidence_id)
    )
    constraints = validate_relation_constraints(ordered_nodes, ordered_relations)
    return ElectricalSemanticGraph(
        project_id=resolved_project_id,
        nodes=ordered_nodes,
        relations=ordered_relations,
        evidence=ordered_evidence,
        constraints=constraints,
    )


def validate_relation_constraints(
    nodes: Iterable[ElectricalSemanticNode],
    relations: Iterable[ElectricalSemanticRelation],
) -> tuple[RelationConstraintResult, ...]:
    """Evaluate structural, role, locality and electrical-union constraints."""
    node_by_id = {node.node_id: node for node in nodes}
    results: list[RelationConstraintResult] = []
    for relation in relations:
        source = node_by_id.get(relation.source_node_id)
        target = node_by_id.get(relation.target_node_id)
        results.append(
            _constraint(
                relation,
                "SOURCE_NODE_EXISTS",
                ConstraintState.PASS if source is not None else ConstraintState.VIOLATION,
                () if source is not None else ("SOURCE_NODE_MISSING",),
            )
        )
        results.append(
            _constraint(
                relation,
                "TARGET_NODE_EXISTS",
                ConstraintState.PASS if target is not None else ConstraintState.VIOLATION,
                () if target is not None else ("TARGET_NODE_MISSING",),
            )
        )

        role_state, role_reasons = _role_constraint(relation, source, target)
        results.append(
            _constraint(
                relation,
                "ROLE_COMPATIBILITY",
                role_state,
                role_reasons,
            )
        )

        locality_state, locality_reasons = _locality_constraint(
            relation,
            source,
            target,
        )
        results.append(
            _constraint(
                relation,
                "SHEET_LOCALITY",
                locality_state,
                locality_reasons,
            )
        )

        union_state, union_reasons = _union_constraint(relation)
        results.append(
            _constraint(
                relation,
                "ELECTRICAL_UNION_GATE",
                union_state,
                union_reasons,
            )
        )
    return tuple(sorted(results, key=lambda item: item.constraint_id))


def can_form_electrical_union(relation: ElectricalSemanticRelation) -> bool:
    """Single public predicate for the fail-closed electrical union invariant."""
    return relation.electrical_union_eligible


def _add_profile_nodes(
    profile: Mapping[str, Any],
    *,
    project_id: str | None,
    nodes: dict[str, ElectricalSemanticNode],
    evidence: dict[str, CandidateEvidence],
    page_node_ids: dict[str, str],
) -> None:
    for index, page in enumerate(_mapping_list(profile.get("page_catalog"))):
        sheet_id = _nullable_text(page.get("sheet_id"))
        if not sheet_id:
            continue
        source_id = f"profile:page:{sheet_id}"
        item_evidence = _evidence(
            source=EvidenceSource.PROJECT_PROFILE,
            source_id=source_id,
            sheet_id=sheet_id,
            state=EvidenceState.ASSERTED,
            authority=AuthorityState.AUTHORITATIVE,
            confidence=1.0,
            reason_codes=("PROJECT_PAGE_CATALOG",),
        )
        evidence[item_evidence.evidence_id] = item_evidence
        node_id = _stable_id("ESN1", project_id or "", "page", sheet_id)
        page_node_ids[sheet_id] = node_id
        nodes[node_id] = ElectricalSemanticNode(
            node_id=node_id,
            semantic_kind=SemanticKind.PAGE,
            role=SemanticRole.PAGE,
            canonical_key=f"page:{sheet_id}",
            label=_nullable_text(page.get("sheet_title")),
            project_id=project_id,
            sheet_id=sheet_id,
            source_ids=(source_id,),
            evidence_ids=(item_evidence.evidence_id,),
            confidence=1.0,
            authority=AuthorityState.AUTHORITATIVE,
            attributes={
                "sheet_no": _nullable_text(page.get("sheet_no")),
                "sheet_category": _nullable_text(page.get("sheet_category")),
                "profile_index": index,
            },
        )

    device_name = _nullable_text(profile.get("device_name"))
    if device_name:
        _add_profile_entity(
            nodes,
            evidence,
            project_id=project_id,
            semantic_kind=SemanticKind.DEVICE,
            role=SemanticRole.DEVICE,
            source_id="profile:device_name",
            canonical_key=f"device:{device_name.casefold()}",
            label=device_name,
            reason_code="PROJECT_DEVICE_NAME",
        )

    for index, strip in enumerate(_mapping_list(profile.get("terminal_strips"))):
        name = _nullable_text(strip.get("name"))
        if not name:
            continue
        _add_profile_entity(
            nodes,
            evidence,
            project_id=project_id,
            semantic_kind=SemanticKind.TERMINAL_STRIP,
            role=SemanticRole.DEVICE,
            source_id=f"profile:terminal_strip:{index}:{name}",
            canonical_key=f"terminal-strip:{name.casefold()}",
            label=name,
            reason_code="PROJECT_TERMINAL_STRIP",
            attributes={
                "style": _nullable_text(strip.get("style")),
                "length": strip.get("length"),
            },
        )


def _add_profile_entity(
    nodes: dict[str, ElectricalSemanticNode],
    evidence: dict[str, CandidateEvidence],
    *,
    project_id: str | None,
    semantic_kind: SemanticKind,
    role: SemanticRole,
    source_id: str,
    canonical_key: str,
    label: str,
    reason_code: str,
    attributes: Mapping[str, Any] | None = None,
) -> None:
    item_evidence = _evidence(
        source=EvidenceSource.PROJECT_PROFILE,
        source_id=source_id,
        sheet_id=None,
        state=EvidenceState.ASSERTED,
        authority=AuthorityState.AUTHORITATIVE,
        confidence=1.0,
        reason_codes=(reason_code,),
    )
    evidence[item_evidence.evidence_id] = item_evidence
    node_id = _stable_id("ESN1", project_id or "", source_id)
    nodes[node_id] = ElectricalSemanticNode(
        node_id=node_id,
        semantic_kind=semantic_kind,
        role=role,
        canonical_key=canonical_key,
        label=label,
        project_id=project_id,
        sheet_id=None,
        source_ids=(source_id,),
        evidence_ids=(item_evidence.evidence_id,),
        confidence=1.0,
        authority=AuthorityState.AUTHORITATIVE,
        attributes=dict(attributes or {}),
    )


def _merge_nodes(
    existing: ElectricalSemanticNode,
    incoming: ElectricalSemanticNode,
) -> ElectricalSemanticNode:
    """Merge duplicate observations without discarding candidate evidence."""
    if (
        existing.semantic_kind is not incoming.semantic_kind
        or existing.role is not incoming.role
    ):
        # A stable node id should not normally collide across semantic kinds.  If
        # malformed input does so, keep the first interpretation and retain the
        # new observation as source/evidence metadata.
        return ElectricalSemanticNode(
            node_id=existing.node_id,
            semantic_kind=existing.semantic_kind,
            role=existing.role,
            canonical_key=existing.canonical_key,
            label=existing.label or incoming.label,
            project_id=existing.project_id or incoming.project_id,
            sheet_id=existing.sheet_id or incoming.sheet_id,
            source_ids=_unique_tuple((*existing.source_ids, *incoming.source_ids)),
            evidence_ids=_unique_tuple(
                (*existing.evidence_ids, *incoming.evidence_ids)
            ),
            confidence=max(existing.confidence, incoming.confidence),
            authority=_merge_authority(existing.authority, incoming.authority),
            attributes={**dict(incoming.attributes), **dict(existing.attributes)},
        )
    return ElectricalSemanticNode(
        node_id=existing.node_id,
        semantic_kind=existing.semantic_kind,
        role=existing.role,
        canonical_key=existing.canonical_key,
        label=existing.label or incoming.label,
        project_id=existing.project_id or incoming.project_id,
        sheet_id=existing.sheet_id or incoming.sheet_id,
        source_ids=_unique_tuple((*existing.source_ids, *incoming.source_ids)),
        evidence_ids=_unique_tuple((*existing.evidence_ids, *incoming.evidence_ids)),
        confidence=max(existing.confidence, incoming.confidence),
        authority=_merge_authority(existing.authority, incoming.authority),
        attributes={**dict(incoming.attributes), **dict(existing.attributes)},
    )


def _merge_authority(
    left: AuthorityState,
    right: AuthorityState,
) -> AuthorityState:
    ranks = {
        AuthorityState.REJECTED: 0,
        AuthorityState.UNKNOWN: 1,
        AuthorityState.REVIEW_ONLY: 2,
        AuthorityState.OBSERVATIONAL: 3,
        AuthorityState.AUTHORITATIVE: 4,
    }
    return left if ranks.get(left, 1) >= ranks.get(right, 1) else right


def _attachment_target_node(
    attachment: Mapping[str, Any],
    *,
    attachment_id: str,
    project_id: str | None,
    evidence_id: str,
    state: EvidenceState,
    confidence: float,
) -> ElectricalSemanticNode:
    sheet_id = _nullable_text(attachment.get("sheet_id"))
    network_id = _nullable_text(attachment.get("electrical_network_id"))
    line_id = _nullable_text(attachment.get("target_line_id"))
    endpoint = _nullable_text(attachment.get("target_endpoint"))
    target_key = (
        f"network:{network_id}"
        if network_id
        else f"line-endpoint:{sheet_id or ''}:{line_id or ''}:{endpoint or ''}"
    )
    node_id = _stable_id("ESN1", project_id or "", target_key)
    authority = (
        AuthorityState.OBSERVATIONAL
        if state is not EvidenceState.REJECTED
        else AuthorityState.REJECTED
    )
    return ElectricalSemanticNode(
        node_id=node_id,
        semantic_kind=SemanticKind.NETWORK_ENDPOINT,
        role=SemanticRole.NETWORK,
        canonical_key=target_key,
        label=None,
        project_id=project_id,
        sheet_id=sheet_id,
        source_ids=(attachment_id,),
        evidence_ids=(evidence_id,),
        confidence=confidence,
        authority=authority,
        attributes={
            "target_kind": _nullable_text(attachment.get("target_kind")),
            "electrical_network_id": network_id,
            "target_line_id": line_id,
            "target_endpoint": endpoint,
            "target_x": attachment.get("target_x"),
            "target_y": attachment.get("target_y"),
        },
    )


def _scope_relation(
    *,
    project_id: str | None,
    sheet_id: str | None,
    scope_kind: str,
    owner_token_id: str,
    member_token_id: str,
    decision_id: str,
    state: EvidenceState,
    authority: AuthorityState,
    confidence: float,
    evidence_id: str,
    reason_codes: tuple[str, ...],
    token_node_ids: Mapping[str, str],
) -> ElectricalSemanticRelation:
    relation_kind = {
        "BODY_PORT": SemanticRelationKind.PORT_OF_DEVICE,
        "SCOPED_PREFIX": SemanticRelationKind.IN_SCOPE_OF,
        "SEMANTIC_ROW": SemanticRelationKind.IN_SEMANTIC_ROW,
    }.get(scope_kind, SemanticRelationKind.DEPENDS_ON)
    source_node_id = token_node_ids.get(
        member_token_id,
        _token_node_id(project_id, sheet_id, member_token_id),
    )
    target_node_id = token_node_ids.get(
        owner_token_id,
        _token_node_id(project_id, sheet_id, owner_token_id),
    )
    return ElectricalSemanticRelation(
        relation_id=_stable_id(
            "ESR1",
            project_id or "",
            relation_kind.value,
            source_node_id,
            target_node_id,
            decision_id,
        ),
        relation_kind=relation_kind,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        project_id=project_id,
        sheet_id=sheet_id,
        state=state,
        authority=authority,
        confidence=confidence,
        evidence_ids=(evidence_id,),
        reason_codes=reason_codes,
        requests_electrical_union=False,
        shadow_only=True,
    )


def _attachment_state_authority(
    attachment: Mapping[str, Any],
    constraint_decisions: list[dict[str, Any]],
) -> tuple[EvidenceState, AuthorityState]:
    selected = bool(attachment.get("selected"))
    attachment_state = str(attachment.get("state") or "").upper()
    authority = _authority(attachment.get("constraint_authority"))
    scope_state = str(attachment.get("scope_state") or "").upper()

    strong_violation = any(
        str(row.get("severity") or "").upper() == "STRONG"
        and str(row.get("state") or "").upper() == "VIOLATION"
        for row in constraint_decisions
    )
    review_decision = any(
        str(row.get("state") or "").upper() == "REVIEW"
        or str(row.get("authority") or "").upper() == "REVIEW_ONLY"
        for row in constraint_decisions
    )
    if not selected or attachment_state == "REJECTED" or strong_violation:
        return EvidenceState.REJECTED, AuthorityState.REJECTED
    if attachment_state == "UNKNOWN":
        return EvidenceState.UNKNOWN, AuthorityState.UNKNOWN
    if scope_state == "CONFLICT":
        return EvidenceState.REJECTED, AuthorityState.REJECTED
    if scope_state == "AMBIGUOUS" or review_decision:
        return EvidenceState.POSSIBLE, AuthorityState.REVIEW_ONLY
    if authority is AuthorityState.AUTHORITATIVE:
        return EvidenceState.ASSERTED, authority
    if authority is AuthorityState.REJECTED:
        return EvidenceState.REJECTED, authority
    return EvidenceState.POSSIBLE, AuthorityState.REVIEW_ONLY


def _scope_state_authority(value: Any) -> tuple[EvidenceState, AuthorityState]:
    state = str(value or "").upper()
    if state == "RESOLVED":
        return EvidenceState.ASSERTED, AuthorityState.AUTHORITATIVE
    if state == "AMBIGUOUS":
        return EvidenceState.POSSIBLE, AuthorityState.REVIEW_ONLY
    if state == "CONFLICT":
        return EvidenceState.REJECTED, AuthorityState.REJECTED
    return EvidenceState.UNKNOWN, AuthorityState.UNKNOWN


def _constraint_decision_state(decision: Mapping[str, Any]) -> EvidenceState:
    state = str(decision.get("state") or "").upper()
    authority = str(decision.get("authority") or "").upper()
    if state == "VIOLATION" or authority == "REJECTED":
        return EvidenceState.REJECTED
    if state == "REVIEW" or authority == "REVIEW_ONLY":
        return EvidenceState.POSSIBLE
    if state == "PASS":
        return EvidenceState.ASSERTED
    return EvidenceState.UNKNOWN


def _role_constraint(
    relation: ElectricalSemanticRelation,
    source: ElectricalSemanticNode | None,
    target: ElectricalSemanticNode | None,
) -> tuple[ConstraintState, tuple[str, ...]]:
    if source is None or target is None:
        return ConstraintState.REVIEW, ("ROLE_CHECK_DEFERRED_MISSING_NODE",)
    expected: tuple[set[SemanticRole], set[SemanticRole]] | None = None
    if relation.relation_kind is SemanticRelationKind.PORT_OF_DEVICE:
        expected = ({SemanticRole.PORT}, {SemanticRole.DEVICE})
    elif relation.relation_kind is SemanticRelationKind.ATTACHED_TO_NETWORK:
        expected = (
            {
                SemanticRole.ENTITY,
                SemanticRole.DEVICE,
                SemanticRole.PORT,
                SemanticRole.NETWORK,
            },
            {SemanticRole.NETWORK},
        )
    elif relation.relation_kind is SemanticRelationKind.REFERENCES_PAGE:
        expected = ({SemanticRole.CROSS_PAGE_REFERENCE}, {SemanticRole.PAGE})
    elif relation.relation_kind is SemanticRelationKind.ELECTRICALLY_CONNECTED:
        expected = (
            {SemanticRole.PORT, SemanticRole.NETWORK},
            {SemanticRole.PORT, SemanticRole.NETWORK},
        )
    if expected is None:
        return ConstraintState.PASS, ()
    source_roles, target_roles = expected
    reasons: list[str] = []
    if source.role not in source_roles:
        reasons.append("SOURCE_ROLE_INCOMPATIBLE")
    if target.role not in target_roles:
        reasons.append("TARGET_ROLE_INCOMPATIBLE")
    if reasons:
        return ConstraintState.VIOLATION, tuple(reasons)
    return ConstraintState.PASS, ()


def _locality_constraint(
    relation: ElectricalSemanticRelation,
    source: ElectricalSemanticNode | None,
    target: ElectricalSemanticNode | None,
) -> tuple[ConstraintState, tuple[str, ...]]:
    if relation.relation_kind not in _LOCAL_RELATIONS:
        return ConstraintState.PASS, ("CROSS_SHEET_RELATION_ALLOWED",)
    if source is None or target is None:
        return ConstraintState.REVIEW, ("SHEET_CHECK_DEFERRED_MISSING_NODE",)
    if source.sheet_id is None or target.sheet_id is None:
        return ConstraintState.REVIEW, ("SHEET_ID_UNKNOWN",)
    if source.sheet_id != target.sheet_id:
        return ConstraintState.VIOLATION, ("CROSS_SHEET_LOCAL_RELATION",)
    return ConstraintState.PASS, ()


def _union_constraint(
    relation: ElectricalSemanticRelation,
) -> tuple[ConstraintState, tuple[str, ...]]:
    if not relation.requests_electrical_union:
        return ConstraintState.PASS, ("UNION_NOT_REQUESTED",)
    if relation.electrical_union_eligible:
        return ConstraintState.PASS, ("ASSERTED_AUTHORITATIVE_UNION",)
    reasons: list[str] = []
    if relation.shadow_only:
        reasons.append("SHADOW_ONLY_RELATION")
    if relation.state is not EvidenceState.ASSERTED:
        reasons.append("NON_ASSERTED_STATE")
    if relation.authority is not AuthorityState.AUTHORITATIVE:
        reasons.append("NON_AUTHORITATIVE_RELATION")
    return ConstraintState.VIOLATION, tuple(reasons or ("UNION_GATE_REJECTED",))


def _constraint(
    relation: ElectricalSemanticRelation,
    kind: str,
    state: ConstraintState,
    reason_codes: tuple[str, ...],
) -> RelationConstraintResult:
    return RelationConstraintResult(
        constraint_id=_stable_id("ESC1", relation.relation_id, kind),
        relation_id=relation.relation_id,
        constraint_kind=kind,
        state=state,
        reason_codes=reason_codes,
    )


def _scope_keys(
    scope_decisions: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for decision in scope_decisions:
        if str(decision.get("state") or "").upper() != "RESOLVED":
            continue
        scope_key = _nullable_text(decision.get("scope_key"))
        if not scope_key:
            continue
        for token_id in _string_list(decision.get("member_token_ids")):
            result.setdefault(token_id, scope_key)
    for attachment in attachments:
        if str(attachment.get("scope_state") or "").upper() != "RESOLVED":
            continue
        token_id = _nullable_text(attachment.get("token_id"))
        scope_key = _nullable_text(attachment.get("scope_key"))
        if token_id and scope_key:
            result.setdefault(token_id, scope_key)
    return result


def _token_canonical_key(
    token: Mapping[str, Any],
    semantic_kind: SemanticKind,
    scope_key: str | None,
) -> str:
    structured = [
        scope_key,
        _nullable_text(token.get("prefix")),
        _nullable_text(token.get("family")),
        _nullable_text(token.get("ordinal")),
        _nullable_text(token.get("local_number")),
    ]
    parts = [item.casefold() for item in structured if item]
    if not parts:
        label = _nullable_text(
            token.get("normalized_text") or token.get("raw_text")
        )
        parts = [label.casefold()] if label else [_record_digest(token)]
    return f"{semantic_kind.value.casefold()}:{'|'.join(parts)}"


def _evidence(
    *,
    source: EvidenceSource,
    source_id: str,
    sheet_id: str | None,
    state: EvidenceState,
    authority: AuthorityState,
    confidence: float,
    reason_codes: Iterable[Any],
) -> CandidateEvidence:
    return CandidateEvidence(
        evidence_id=_evidence_id(source, source_id),
        source=source,
        source_id=source_id,
        sheet_id=sheet_id,
        state=state,
        authority=authority,
        confidence=_confidence(confidence),
        reason_codes=_unique_tuple(str(item) for item in reason_codes if str(item)),
    )


def _evidence_id(source: EvidenceSource, source_id: str) -> str:
    return _stable_id("ESE1", source.value, source_id)


def _authority(value: Any) -> AuthorityState:
    normalized = str(value or "").upper()
    try:
        return AuthorityState(normalized)
    except ValueError:
        return AuthorityState.UNKNOWN


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if hasattr(value, "to_dict"):
        if bool(getattr(value, "empty", False)):
            return []
        try:
            return [dict(row) for row in value.to_dict(orient="records")]
        except TypeError:
            return [dict(row) for row in value.to_dict("records")]
    return [dict(row) for row in value]


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _record_id(
    row: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    index: int,
) -> str:
    for key in keys:
        value = _nullable_text(row.get(key))
        if value:
            return value
    return f"anonymous-{index}-{_record_digest(row)[:16]}"


def _record_digest(row: Mapping[str, Any]) -> str:
    payload = json.dumps(
        {str(key): _json_safe(value) for key, value in row.items()},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    return str(value)


def _confidence(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(result):
        return 0.0
    return min(1.0, max(0.0, result))


def _nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]


def _reason_codes(row: Mapping[str, Any]) -> tuple[str, ...]:
    return _unique_tuple(_string_list(row.get("reason_codes")))


def _combined_reasons(
    attachment: Mapping[str, Any],
    constraint_decisions: list[dict[str, Any]],
) -> tuple[str, ...]:
    material: list[str] = []
    material.extend(_string_list(attachment.get("reason_codes")))
    material.extend(_string_list(attachment.get("scope_reason_codes")))
    material.extend(_string_list(attachment.get("constraint_reason_codes")))
    for decision in constraint_decisions:
        material.extend(_string_list(decision.get("reason_codes")))
    return _unique_tuple(material)


def _unique_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _token_node_id(
    project_id: str | None,
    sheet_id: str | None,
    token_id: str,
) -> str:
    return _stable_id(
        "ESN1",
        project_id or "",
        sheet_id or "",
        "token",
        token_id,
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}-{digest}"


__all__ = [
    "ALGORITHM_VERSION",
    "SCHEMA_VERSION",
    "AuthorityState",
    "CandidateEvidence",
    "ConstraintState",
    "ElectricalSemanticGraph",
    "ElectricalSemanticNode",
    "ElectricalSemanticRelation",
    "EvidenceSource",
    "EvidenceState",
    "RelationConstraintResult",
    "SemanticKind",
    "SemanticRelationKind",
    "SemanticRole",
    "build_electrical_semantic_graph",
    "can_form_electrical_union",
    "validate_relation_constraints",
]
