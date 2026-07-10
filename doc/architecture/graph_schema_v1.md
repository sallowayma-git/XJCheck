# Graph Schema v1

- Status: normative Phase 104 contract
- Version: graph-schema/v1
- Applies to: shadow and primary topology-first findings
- Related ADR: topology_first_adr.md

## Conventions

Findings are append-only records scoped to one run_id; corrections create a new run rather than mutate evidence. Files are Parquet tables under findings/. Nullable fields are explicitly noted as optional; all others are required. Timestamps are RFC 3339 UTC. Coordinates are normalized drawing units and retain their source coordinate system in provenance.

id values are stable UUIDv5 strings. Derive them from the schema namespace, record kind, canonical sorted input IDs, canonical normalized attributes, and a discriminator where repeated objects are valid. Do not include run_id in a semantic object ID. run_id is a UUIDv7 (or equivalent time-sortable unique ID) created at execution start. The canonicalization algorithm and namespace UUID are recorded in run_manifest.

Source CAD entities use source_entity_id = entity:<project_id>:<sheet_id>:<handle>. The normalized handle is uppercase with leading zeroes removed. An entity without a durable handle uses a reader-assigned stable object key and source_handle_kind = reader_assigned; it must not masquerade as a handle.

### Common Columns

Every table contains these columns unless the table definition is stricter:

| Column | Type | Contract |
|---|---|---|
| id | string | primary key; stable object or decision ID |
| schema_version | string | exactly graph-schema/v1 |
| project_id, sheet_id, run_id | string | project, sheet, and producing-run scope |
| created_at | timestamp | producing-run UTC time |
| provenance_id | string | FK to provenance |
| confidence_id | string | FK to confidence for inferred records; optional only for raw source inventory |

project_id and sheet_id are opaque stable IDs, not display names. A cross-sheet aggregate sets sheet_id to null and references sheets through a membership table.

### Provenance

provenance is the required evidence anchor. A derived record has one primary provenance row; complete inputs are represented in provenance_inputs.

| Table | Additional required columns |
|---|---|
| provenance | reader_name, reader_version, source_file_fingerprint, source_handle, source_handle_kind, entity_type, layer, raw_coordinate_system, raw_geometry_json, generation_reason, pipeline_stage, config_fingerprint |
| provenance_inputs | provenance_id, input_id, input_kind, ordinal |
| run_manifest | run_id, pipeline_version, schema_version, id_namespace, canonicalization_version, config_fingerprint, input_manifest_fingerprint |

raw_geometry_json includes original coordinates or a block transform sufficient to reproduce the object. It may be null only for a project-level constraint without direct CAD geometry. generation_reason is a machine-readable reason code, never a free-text replacement for evidence.

## Decisions And Confidence

### Four-State Decision

All decision-bearing tables use this exact enum:

    ASSERTED | POSSIBLE | REJECTED | UNKNOWN

ASSERTED is sufficient evidence to materialize the relation. POSSIBLE is a credible alternative pending resolution. REJECTED records an evaluated non-relation. UNKNOWN means evidence is absent or insufficient to classify. Scores may support a decision but do not define state.

ASSERTED can become REJECTED only in a later run with new evidence. Within a run, decision history is append-only and exactly one is_final = true decision exists per decision_subject_id and decision_type.

topology_decisions requires:

    decision_id, decision_subject_id, node_a_id, node_b_id, decision_type, state,
    is_final, rule_score, symbol_score, model_score, final_confidence,
    decision_source, evidence_ids, alternative_decision_ids, reason_code

decision_source is one of geometry_rule, symbol_library, constraint, human_review, or model_assisted. evidence_ids and alternative_decision_ids are arrays of IDs. reason_code is versioned by the producing module.

### Confidence

confidence has one row per assessment:

    confidence_id, subject_id, subject_kind, extraction_confidence,
    geometry_confidence, junction_confidence, symbol_confidence,
    port_binding_confidence, network_confidence, text_assignment_confidence,
    cross_page_match_confidence, audit_confidence, final_confidence,
    weakest_evidence, requires_review, calibration_id, rationale

All populated numeric values are finite decimals in [0,1]; non-applicable dimensions are null, not zero. final_confidence is required for inferred objects. weakest_evidence names the lowest applicable dimension or a reason code. requires_review is required when a final choice is ambiguous, unknown, or below the configured auto-decision policy.

## Findings Tables

The tables below are v1 minimum. PK is id unless shown otherwise. All referenced IDs are foreign keys that must exist in the same run, except stable source/provenance records shared by the run manifest.

### Geometry Graph

| Table | PK / required relation columns | Additional required payload |
|---|---|---|
| primitive_segments | id, source_entity_id | start_x, start_y, end_x, end_y, primitive_kind, segment_ordinal |
| geometry_nodes | id | node_kind, x, y, source_entity_ids |
| geometry_edges | id, node_a_id, node_b_id, primitive_segment_id | edge_kind, length, state |
| junction_observations | id, node_id, observed_edge_ids | junction_kind, state, observation_reason |
| topology_decisions | decision_id, node_a_id, node_b_id | all decision columns above |

geometry_edges.state is the final topology state for that edge and agrees with its final topology_decisions row. Original segments are split at every asserted intersection before net materialization. Crossings default to REJECTED or UNKNOWN unless independent evidence asserts a junction.

### Symbol-Port Graph

| Table | PK / required relation columns | Additional required payload |
|---|---|---|
| symbol_instances | id, source_entity_id | family_id (optional if unknown), family_state, transform_json, library_version |
| symbol_ports | id, symbol_instance_id | port_key, x, y, port_role, state |
| symbol_internal_connections | id, symbol_instance_id, port_a_id, port_b_id | behavior, state, library_rule_id |
| port_bindings | id, symbol_port_id, geometry_node_id | state, binding_kind, distance, decision_id |

behavior is exactly permanent_connected, switched, isolated, unknown, pass_through, or visual_only. One port has at most one final asserted external binding. unknown behavior cannot add a net connection.

### Electrical Net Graph

| Table | PK / required relation columns | Additional required payload |
|---|---|---|
| electrical_networks | id | network_key, member_count, total_length, materialization_state |
| network_members | composite: network_id, member_id | member_kind, membership_reason |
| network_open_endpoints | id, network_id, geometry_node_id | endpoint_kind, state, witness_path_id |
| network_paths | id, network_id, start_object_id, end_object_id | ordered_edge_ids, source_entity_ids, path_state |

Only asserted geometry edges and asserted port bindings may appear in an electrical_networks component. Every network member has a witness path or is a path origin. network_key is a deterministic hash of sorted asserted member IDs for cross-run diffs, not a display name.

### Semantic Attachment Graph

| Table | PK / required relation columns | Additional required payload |
|---|---|---|
| semantic_tokens | id, source_entity_id | text, normalized_text, role, role_state, bounding_box_json |
| text_assignment_candidates | id, token_id, target_id | target_kind, rank, feature_json, state, decision_id |
| text_assignments | id, token_id, target_id | target_kind, assignment_role, state, chosen_candidate_id, alternative_candidate_ids |

One token has at most one final asserted primary assignment for an assignment_role unless that role is explicitly multi-valued. Candidate rank is stable within a run. Tied or policy-ambiguous candidates set requires_review.

### Project Graph And Constraints

| Table | PK / required relation columns | Additional required payload |
|---|---|---|
| cross_page_endpoints | id, network_open_endpoint_id | endpoint_identity_key, sheet_reference, state |
| cross_page_match_candidates | id, endpoint_a_id, endpoint_b_id | rank, state, feature_json, decision_id |
| constraint_decisions | id, decision_subject_id | constraint_set_version, state, selected_ids, rejected_ids, alternative_solution_ids, reason_code |

Cross-page matching operates only on cross_page_endpoints; page-local open endpoints are not implicitly matched. A constraint decision retains every feasible near-optimal alternative that triggers review.

## Referential And Materialization Rules

1. Every referenced ID resolves. A legacy pair cannot be evidence for geometry, net, port, or semantic truth.
2. Every non-source row has provenance_inputs that transitively reach one or more source_entity_id values, unless it is a project-level constraint.
3. Every ASSERTED relation has a non-empty evidence ID list and a witness-capable path through its layer. POSSIBLE, REJECTED, and UNKNOWN are never discarded after materialization.
4. A final choice with POSSIBLE alternatives, an UNKNOWN dependency, or policy-ambiguous confidence sets requires_review = true.
5. No net contains an edge whose final decision is not ASSERTED. No rule issue claims a graph relation without its IDs and witness path IDs.

## Legacy Compatibility Tables

Legacy projections are emitted in legacy/ or tagged compatibility_only = true; they are outside the v1 truth graph.

| Legacy object | v1 source | Compatibility rule |
|---|---|---|
| LineGroup | electrical_networks plus network_members | derive rendered line groups and retain network_id |
| TerminalCandidate | semantic_tokens plus candidates/assignments | retain token_id, target ID, rank, and state |
| PairCandidate | cross-page match or semantic candidates | retain candidate IDs and cannot create a net edge |
| legacy Pair | asserted project relation | retain graph relation IDs and witness IDs |

The adapter produces a relation-diff report with added, removed, and changed stable IDs. A legacy object without a v1 back-reference is an adapter failure, not a fallback truth source.

## Validation And Gate Evidence

Before publishing a run, validate schema version, primary-key uniqueness, foreign keys, state enum, decision uniqueness, confidence ranges, provenance closure, net materialization, path reachability, and compatibility back-references. Emit a validation report with row counts, unresolved references, invalid decisions, review counts, and changed IDs versus baseline.

| Gate | Required tables | Required validation result |
|---|---|---|
| A | run_manifest, provenance, baseline relation diff | schema/version and baseline fingerprint recorded |
| B | all Geometry and Electrical Net tables | no invalid net member; every sampled final endpoint has a witness |
| C | all Symbol-Port tables | no asserted binding to unknown internal behavior without review |
| D | all Semantic tables and constraint_decisions | alternatives persisted; no topology override |
| E | all Project tables and legacy adapter report | every hard issue has graph IDs and witnesses |
| F | later labels/predictions extension | project split and calibration evidence; v1 constraints remain enforced |

## Open Schema Questions

| ID | Open decision | Blocking scope |
|---|---|---|
| OQ-104-01 | Canonical project_id and source-file fingerprint algorithm | stable production IDs |
| OQ-104-02 | Versioned tolerance configuration and units policy | Geometry B implementation |
| OQ-104-03 | family_id registry namespace and library override precedence | Symbol C implementation |
| OQ-104-04 | Machine-readable ambiguity/review policy and reviewer resolution table | Semantic D implementation |
| OQ-104-05 | Exact legacy export filenames and retention period | E cutover |

