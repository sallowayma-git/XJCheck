"""Pseudocode for a CP-SAT based global candidate resolver."""

from ortools.sat.python import cp_model

SCALE = 10_000


def solve_candidates(port_candidates, attachment_candidates, cross_page_candidates, facts, config):
    model = cp_model.CpModel()

    x_port = {c.id: model.NewBoolVar(f"port_{c.id}") for c in port_candidates}
    x_attach = {c.id: model.NewBoolVar(f"attach_{c.id}") for c in attachment_candidates}
    x_cross = {c.id: model.NewBoolVar(f"cross_{c.id}") for c in cross_page_candidates}

    # Hard constraint: one primary geometry/network binding per symbol port.
    for port_id, candidates in group_by(port_candidates, key=lambda c: c.port_id).items():
        model.Add(sum(x_port[c.id] for c in candidates) <= 1)

    # Hard constraint: one primary terminal identity assignment per endpoint.
    for endpoint_id, candidates in group_by(
        attachment_candidates, key=lambda c: c.target_endpoint_id
    ).items():
        primary = [c for c in candidates if c.role == "terminal_number"]
        model.Add(sum(x_attach[c.id] for c in primary) <= 1)

    # Hard constraint: a text token cannot label unrelated endpoints simultaneously.
    for token_id, candidates in group_by(attachment_candidates, key=lambda c: c.token_id).items():
        exclusive = [c for c in candidates if c.exclusive]
        model.Add(sum(x_attach[c.id] for c in exclusive) <= 1)

    # Hard constraint: verified symbol behavior is authoritative.
    for c in port_candidates:
        if c.forbidden_by_verified_symbol:
            model.Add(x_port[c.id] == 0)
        if c.required_by_verified_symbol:
            model.Add(x_port[c.id] == 1)

    # Hard constraint: media cannot cross unless an explicit adapter exists.
    for c in cross_page_candidates:
        if not c.medium_compatible and not c.has_verified_adapter:
            model.Add(x_cross[c.id] == 0)

    # Optional reciprocal relation. Use implication, not an unconditional assumption.
    for c in cross_page_candidates:
        if c.reciprocal_candidate_id and c.reciprocal_required:
            model.Add(x_cross[c.id] == x_cross[c.reciprocal_candidate_id])

    # Link a cross-page candidate to selected endpoint identities.
    for c in cross_page_candidates:
        for required_attachment_id in c.required_attachment_ids:
            model.Add(x_cross[c.id] <= x_attach[required_attachment_id])

    terms = []
    for c in port_candidates:
        terms.append(int(c.score * SCALE) * x_port[c.id])
        if c.topology_state == "POSSIBLE":
            terms.append(-int(config.penalize_possible_bridge * SCALE) * x_port[c.id])
    for c in attachment_candidates:
        terms.append(int(c.score * SCALE) * x_attach[c.id])
    for c in cross_page_candidates:
        terms.append(int(c.score * SCALE) * x_cross[c.id])
        if c.reciprocal_candidate_id:
            terms.append(int(config.prefer_reciprocal * SCALE) * x_cross[c.id])

    model.Maximize(sum(terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = config.timeout_seconds
    solver.parameters.num_search_workers = config.num_workers
    status = solver.Solve(model)
    if status not in {cp_model.OPTIMAL, cp_model.FEASIBLE}:
        return Resolution.failed(status_name=solver.StatusName(status))

    selected = {
        "port": [c.id for c in port_candidates if solver.Value(x_port[c.id])],
        "attachment": [c.id for c in attachment_candidates if solver.Value(x_attach[c.id])],
        "cross_page": [c.id for c in cross_page_candidates if solver.Value(x_cross[c.id])],
    }

    # Re-solve after excluding the best exact assignment to estimate ambiguity.
    second_best = solve_second_best(model, solver, selected, terms, config)
    objective_gap = normalized_objective_gap(solver.ObjectiveValue(), second_best.objective)
    return Resolution(
        status=solver.StatusName(status),
        selected=selected,
        objective=solver.ObjectiveValue(),
        second_best=second_best,
        objective_gap=objective_gap,
        review_required=objective_gap < config.review_if_objective_gap_below,
        reason=("NEAR_EQUAL_GLOBAL_SOLUTIONS" if objective_gap < config.review_if_objective_gap_below else "UNIQUE_SOLUTION"),
    )
