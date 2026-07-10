# Phase 105 Geometry Shadow Slice

- Status: implemented shadow slice; not production topology truth
- Scope: CAD line geometry only
- Primary output remains: legacy Pair

## Contract

The shadow builder consumes in-scope `LineEntity` records and emits:

- `geometry_shadow_nodes.parquet`
- `geometry_shadow_edges.parquet`
- `geometry_shadow_components.parquet`
- `pair_geometry_shadow.parquet`
- `pair_geometry_shadow_summary.json`
- `geometry_shadow_observations.parquet`
- `geometry_shadow_observation_summary.json`

It does not consume text, blocks, filenames, terminal values, or project-specific identifiers when deciding connectivity. Text and block gap bridges remain legacy evidence and cannot create a geometry edge.

Only exact geometry within `topology.geometry_graph_asserted_snap_tolerance` is materialized. The wider legacy junction tolerance is deliberately not reused. An internal crossing remains disconnected unless `merge_crossings` is enabled or a generic connection-marker primitive is present.

## Primitive Classification

A common CAD connection dot is exported as two short `LWPOLYLINE` segments with the same parent handle and reversed coincident geometry. These segments are classified as a connection marker rather than two wire edges. A marker at an orthogonal crossing promotes that crossing to an asserted junction and is retained as node evidence.

This rule is based on source geometry and parent identity. It contains no page name, layer whitelist, coordinate, device family, or terminal value.

## Pair Projection

`pair_geometry_shadow` projects each legacy Pair's LineGroup member lines onto geometry components. Its status is one of:

- `unique_geometry_component`
- `multiple_geometry_components`
- `no_geometry_component`
- `no_line_group`

This status is context evidence only. A unique component does not prove that legacy left/right text values are correct, and no Pair status, kind, confidence, issue, or coverage assignment is changed.

## Four-State Observations

The geometry shadow retains connectivity evidence without materializing uncertain relations:

- `ASSERTED`: an existing canonical junction supported by exact geometry or a connection marker.
- `POSSIBLE`: a unique pair of open endpoints is collinear, faces each other, and is within the configured observation distance.
- `UNKNOWN`: the same geometric gap test has competing endpoint candidates.
- `REJECTED`: an internal orthogonal crossing has no marker or enabled crossing policy.

Only `ASSERTED` relations are already represented by geometry components. `POSSIBLE` and `UNKNOWN` never merge components; `REJECTED` crossings remain disconnected. The table is explicitly `geometry-shadow/v1`, not `graph-schema/v1`, because full run/provenance/confidence closure is still pending.

## Frozen-Sample Metrics

| Project | Ordinary pairs | Unique component | Multiple components | Unique ratio |
|---|---:|---:|---:|---:|
| first | 728 | 579 | 149 | 79.5330% |
| second | 561 | 338 | 223 | 60.2496% |
| held-out remote cabinet | 491 | 434 | 57 | 88.3910% |

The held-out project has the highest unique-component ratio despite having no project-specific structural mapping families. This supports improving geometry, port binding, and semantic attachment rather than adding more sample-specific ordinary rules.

### Multiple-Component Gap Evidence

| Project | Multiple ordinary | With gap evidence | Contains POSSIBLE | Contains UNKNOWN |
|---|---:|---:|---:|---:|
| first | 149 | 141 | 96 | 48 |
| second | 223 | 214 | 42 | 180 |
| held-out remote cabinet | 57 | 20 | 20 | 0 |

Rows can contain both POSSIBLE and UNKNOWN observations when a LineGroup spans more than two components. The high UNKNOWN count on second prevents unsafe automatic bridging and identifies the next Symbol-Port/ConstraintResolver input queue.

## Remaining Boundary

The shadow tables intentionally do not claim Graph Schema v1 compliance yet. Phase 105 still needs provenance tables, primitive segments, explicit POSSIBLE/REJECTED observations, witness paths, Symbol-Port bindings, and an Electrical Net materializer that consumes only final ASSERTED decisions.
