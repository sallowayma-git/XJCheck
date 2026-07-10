"""Pseudocode for identity-aware cross-page matching and explainable audit."""


def build_cross_page_endpoints(semantic_model, project_profile):
    endpoints = []
    for network in semantic_model.networks:
        for boundary in network.boundaries:
            if boundary.kind not in {
                "open_network_endpoint",
                "verified_symbol_port",
                "interruption_marker",
                "table_terminal_endpoint",
            }:
                continue

            identity_candidates = semantic_model.identities_for(boundary)
            endpoints.append(
                CrossPageEndpoint(
                    endpoint_id=new_id("XPE"),
                    sheet_id=network.sheet_id,
                    network_id=network.network_id,
                    geometry_node_id=boundary.geometry_node_id,
                    symbol_port_id=boundary.symbol_port_id,
                    coord=boundary.xy,
                    medium=boundary.medium,
                    direction=boundary.direction,
                    identity_candidates=identity_candidates,
                    topology_confidence=network.confidence,
                    unresolved_boundary_decisions=network.possible_boundary_decisions,
                )
            )
    return endpoints


def canonical_identity(candidate, project_profile):
    # Bare numbers are not globally unique. Scope is mandatory where available.
    return TerminalIdentity(
        terminal_strip_scope=candidate.terminal_strip_scope,
        terminal_number=normalize_terminal_number(candidate.value),
        device_scope=candidate.device_scope,
        medium=candidate.medium,
        direction=candidate.direction,
        source_role=candidate.role,
    )


def build_cross_page_candidates(endpoints, project_profile, config):
    index = identity_index(endpoints)
    candidates = []
    for source in endpoints:
        for source_identity in source.identity_candidates:
            key = canonical_identity(source_identity, project_profile)
            for target in index.compatible_targets(key, exclude_sheet=source.sheet_id):
                if source.medium != target.medium and not has_verified_medium_adapter(source, target):
                    continue
                candidates.append(
                    CrossPageMatchCandidate(
                        candidate_id=new_id("XPM"),
                        source_endpoint_id=source.endpoint_id,
                        target_endpoint_id=target.endpoint_id,
                        canonical_identity=key,
                        score=score_cross_page_match(source, target, key, project_profile),
                        reciprocal_candidate_id=find_reciprocal(source, target, key),
                        evidence_ids=collect_evidence(source, target, key),
                    )
                )
    return top_k_per_endpoint(candidates, config.candidate_top_k)


class CrossPageConflictRule:
    rule_id = "XJ-XPAGE-001"

    def evaluate(self, project_graph):
        issues = []
        for identity, selected_edges in project_graph.matches_by_identity().items():
            incompatible = incompatible_target_groups(selected_edges)
            if not incompatible:
                continue

            confidence = weakest_link_confidence(selected_edges)
            decision_mode = "automatic" if automatic_gate(selected_edges, confidence) else "review_required"
            witness = []
            for edge in selected_edges:
                witness.extend(project_graph.witness_path(edge))

            issues.append(
                IssueV2(
                    issue_id=new_id("I"),
                    rule_id=self.rule_id,
                    severity="critical" if decision_mode == "automatic" else "review",
                    decision_mode=decision_mode,
                    confidence=confidence,
                    summary=describe_incompatible_identity(identity, incompatible),
                    explanation=explain_selected_and_rejected_candidates(selected_edges),
                    evidence_refs=deduplicate(evidence_ids(selected_edges)),
                    witness_path=deduplicate_path(witness),
                    weakest_evidence=find_weakest_evidence(selected_edges),
                    alternatives=collect_near_equal_alternatives(selected_edges),
                    recommended_action="Review the listed sheets, endpoints and witness paths before correcting the source drawing.",
                    status="open",
                )
            )
        return issues


def automatic_gate(edges, confidence):
    return all(
        [
            confidence >= 0.985,
            all(e.reader_complete for e in edges),
            all(not e.unresolved_topology for e in edges),
            all(not e.unresolved_symbol for e in edges),
            all(e.identity_is_unique for e in edges),
            all(e.constraint_solution_is_unique for e in edges),
        ]
    )
