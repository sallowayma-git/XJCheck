# Symbol port fixtures v1

Phase 117 **schema scaffold only**. This fixture registers Top-N geometry-family
fingerprints with **ports UNKNOWN**. It does not invent ports, declare electrical
connectivity, or wire production symbol registry / wire-component behavior.

## Source

- Non-heldout backlog: `.tmp/phase117_symbol_backlog_non_heldout/symbol_annotation_backlog_top50.json`
- Pre-seed: corpus ranks 1–10 (geometry families by priority)
- Extra seed: `KK2P` when present in top50 (name feature only; still 0 ports)
- Held-out projects from `benchmark_split_v1.csv` must not appear in the JSON

## Document versions

| Field | Value |
| --- | --- |
| `fixture_version` | `symbol-port-fixtures-v1` |
| `fingerprint_version` | `local-geometry-fingerprint-v1` |

## Root object

```json
{
  "fixture_version": "symbol-port-fixtures-v1",
  "fingerprint_version": "local-geometry-fingerprint-v1",
  "entries": [ /* entry objects */ ]
}
```

## Entry fields

| Field | Type | Required | Scaffold default | Notes |
| --- | --- | --- | --- | --- |
| `definition_fingerprint` | string | yes | from backlog | 64-char lowercase hex (SHA-256 style local geometry fingerprint) |
| `definition_names` | list[string] | yes | from backlog | Observed block/definition names for this fingerprint |
| `registry_status` | string | yes | `"UNKNOWN"` | Allowed: `UNKNOWN` \| `CANDIDATE` \| `REGISTERED` |
| `symbol_family` | string \| null | yes | `null` | Family assignment deferred until human review |
| `internal_connectivity_state` | string | yes | `"UNKNOWN"` | Scaffold: always `UNKNOWN` (no invented connectivity) |
| `declared_port_count` | int | yes | `0` | Must equal `len(ports)` |
| `ports` | list | yes | `[]` | Empty until human annotation; no invented ports |
| `critical_issue_eligible` | bool | yes | `false` | Scaffold: always false until ports are registered |
| `annotation_status` | string | yes | `"PENDING_HUMAN_REVIEW"` | Human gate before any production use |
| `notes` | string | yes | free text | Provenance / review notes only |

## Ports array (future)

`ports` remains empty in this version. Future human annotation may add objects, but
that is **out of scope** for Phase 117 scaffold. Until then:

- `declared_port_count == 0`
- `len(ports) == 0`
- no electrical network edges may be derived from this fixture

## Policy

1. **No invented ports.** Empty `ports` is intentional, not incomplete data to auto-fill.
2. **No electrical connectivity.** `internal_connectivity_state` stays `UNKNOWN`.
3. **No critical issues from unregistered symbols.** `critical_issue_eligible` stays `false`.
4. **No held-out leakage.** Do not seed from held-out project ids or held-out-only fingerprints.
5. **Registry status.** All scaffold entries are `UNKNOWN`; promotion to `CANDIDATE` / `REGISTERED` requires human review and fixture version bump.
6. **Production isolation.** This JSON is validation/fixture only. Production code must not treat empty ports as zero-port devices.

## Identity

Matching identity for an entry is `definition_fingerprint` under
`fingerprint_version = local-geometry-fingerprint-v1`. `definition_names` are
review aids and may grow as aliases are observed.
