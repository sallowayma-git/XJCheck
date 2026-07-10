# ADR-104: Topology-First Graph Pipeline

- Status: accepted
- Phase: 104
- Decision date: 2026-07-10
- Normative schema: graph_schema_v1.md

## Decision

The recognition pipeline SHALL use graph materialization as its connectivity truth. Native CAD entities are normalized into a Geometry Graph; symbol ports add electrical semantics; Electrical Nets are materialized from asserted relations only; semantic attachments identify existing objects; and the Project Graph resolves cross-sheet identities. Rules consume materialized objects and SHALL NOT repair recognition or infer connectivity.

LineGroup, neighborhood candidates, and legacy pairs remain compatibility projections during migration. They are not sources of electrical truth.

## Scope And Non-Goals

This ADR governs Phase 104's data contract and migration controls. It does not move modules, replace every extractor, enable a learned model, or alter user results. Shadow findings may be emitted before they drive results, but they must meet the schema and evidence contract.

## Five-Layer Contract

| Layer | Owns | May decide | Must not decide | Exit artifact |
|---|---|---|---|---|
| Geometry Graph | primitives, intersections, junction observations, CAD-space adjacency | geometric relation state | symbol behavior, text identity, cross-page equivalence | nodes, edges, decisions, witnesses |
| Symbol-Port Graph | instances, transformed ports, declared internal connections | port location and library-declared behavior | unbound geometry union | instances, ports, bindings |
| Electrical Net Graph | components of asserted geometry and bound ports | membership and open endpoints | semantic identity or cross-page match | nets, members, paths |
| Semantic Attachment Graph | text/token role, scope, candidates, assignments | attachment to an existing object | geometry connectivity or forced identity | tokens, candidates, assignments |
| Project Graph | sheets, endpoint/network/terminal identities, alternatives | project-wide matches under constraints | page-local extraction or audit compensation | endpoints, matches, constraints |

Each relation has one owning layer. Consumers may reference it but may not overwrite its decision. A defect is fixed in the owning layer, followed by a fresh run and relation diff.

## Required Invariants

1. All topology decisions use exactly ASSERTED, POSSIBLE, REJECTED, or UNKNOWN. State is explicit and reviewable, not a confidence alias.
2. Only ASSERTED geometry edges and asserted port bindings may contribute to Union-Find or connected-component materialization. Every other state remains persisted.
3. Every final net endpoint exposes a witness path to primitives and source CAD entities. Derived records retain schema provenance.
4. A crossing, gap, text bridge, or block span is not asserted merely because it is near. Evidence and competing interpretations exist before promotion.
5. Symbol internal connection follows the library declaration. An unknown symbol never silently becomes pass-through.
6. Semantic and project solvers may rank candidates but cannot override asserted/rejected topology or declared symbol connectivity.
7. Non-unique high-risk identity, attachment, or cross-page result requires review and must not silently collapse to top-1.

## Compatibility And Migration

The rollout order is shadow -> compare -> primary -> legacy_off.

| Mode | Source of user result | Required behavior |
|---|---|---|
| shadow | legacy pipeline | emit v1 findings; no pair/rule behavior change |
| compare | legacy pipeline | emit stable relation diff, coverage, and witness evidence |
| primary | v1 graphs | retain legacy projections and equivalence reporting |
| legacy_off | v1 graphs | allowed only after final gate; preserve legacy readers or an export adapter |

The migration configuration contract is:

    recognition:
      primary_engine: topology
      legacy_neighborhood:
        mode: shadow
        allow_for_text_candidates: true
        allow_for_connectivity: false
        allow_for_final_pair: false

Phase A uses a non-disruptive runtime declaration instead:

    recognition:
      primary_engine: legacy
      legacy_neighborhood:
        mode: shadow-compatible
        allow_for_text_candidates: true
        allow_for_connectivity: false
        allow_for_final_pair: false

`primary_engine: legacy` is the sole active behavior switch in Phase A, so current Pair and Issue output remains unchanged. The nested `shadow-compatible` permissions declare what legacy neighborhood logic may do after topology becomes primary; pipeline code MUST NOT enforce those deny flags against the current legacy engine before the primary switch. The switch to `primary_engine: topology` and `mode: shadow` requires its own gate and zero-drift comparison.

Neighborhood logic may create semantic candidate evidence only. It cannot decide net connectivity or final pair identity. LineGroup is an Electrical Net projection for reports and regression compatibility. TerminalCandidate, PairCandidate, and legacy Pair are shadow/adapter objects only.

## Phase Gates

| Gate | Entry requirement | Exit evidence | Stop condition |
|---|---|---|---|
| A: contract baseline | current behavior frozen | ADR, v1 schema, baseline bundle with findings/pairs/issues/coverage/topology by sheet | missing baseline or undocumented schema deviation |
| B: geometry/net shadow | A accepted | primitives, decisions, nets, complete witnesses; sampled junction checks; zero incorrect net merge on red-line cases | asserted edge lacks provenance or witness |
| C: symbol-port | B schema stable | Top-N coverage, transformed ports, bindings, unknown-symbol review queue, no migration behavior drift | unknown internal behavior assumed connected |
| D: semantic/constraints | B and C artifacts available | alternatives, assignment decisions, constraint decisions, measured truth set | solver overwrites topology or hides alternatives |
| E: project/rules | D identities stable | cross-page candidates, project constraints, graph-witness issues, legacy-equivalence proof | hard error lacks unambiguous evidence |
| F: learning evaluation | E deterministic baseline stable and three project splits available | held-out metrics, calibration, label provenance, shadow predictions | model bypasses graph constraints or automatic precision is inadequate |

A -> B is strictly serial. C may start once B schema is stable. D consumes B/C, E consumes D, and F cannot start before E. A gate failure returns work to the owning layer; it is not solved with a report filter or rule patch.

## Acceptance

Phase 104 is accepted when both documents permit an implementation without interpretation changes:

- Every required findings table has a primary key, foreign-key targets, required provenance, decision/state handling where applicable, and confidence fields.
- A reader can explain any net, port binding, attachment, or cross-page choice and locate its source handle, sheet, coordinates, and run.
- A validator can reject invalid states, missing witnesses, dangling references, confidence outside [0,1], and legacy objects used as truth.
- Migration modes and gates produce observable evidence, including legacy/new relation diffs and changed IDs.

Rule count or issue count alone is not acceptance evidence. Precision, coverage, relation diffs, and explained-object coverage remain required.

## Open Questions

| ID | Question | Owner | Needed before |
|---|---|---|---|
| OQ-104-01 | Project namespace and source-file fingerprint for stable IDs | platform | B implementation |
| OQ-104-02 | Tolerances that are project configuration versus reader constants | topology | B implementation |
| OQ-104-03 | First Top-N symbol families and library review authority | symbols | C entry |
| OQ-104-04 | Ambiguity threshold and reviewer workflow for requires_review | audit | D entry |
| OQ-104-05 | Legacy readers needing an export after legacy_off | platform | E exit |
