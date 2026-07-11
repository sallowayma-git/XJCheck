# Symbol definition fixtures v1 (Phase 117 Top-N)

Minimal reproducible **child signature** fixtures for the top geometry families
from the non-held-out Phase 117 corpus, plus a multi-port *name* example (`KK2P`).

## Policy

| Rule | Value |
|------|--------|
| Held-out projects | **Excluded**. Source is non-held-out only (`phase117_corpus_non_heldout`, project `P001`). |
| Fingerprint algorithm version | `local-geometry-fingerprint-v1` (`SYMBOL_FINGERPRINT_VERSION`) |
| Ports / internal connectivity | **None claimed**. `declared_port_count` is always `0`. `internal_connectivity_state` is `UNKNOWN`. Do not invent port coordinates. |
| Names vs identity | **Definition names are features, not identities.** A geometry family is keyed by `definition_fingerprint`. Multiple names may share one fingerprint (e.g. `SYMB2_M_PWF231` + `SYMB2_M_PWF248`). |
| Critical issues | `critical_issue_eligible` remains **`false`** until human registration of the symbol definition. |
| What is stored | Unique child signatures only: `source_entity_type`, `primitive_kind`, `layer`, `linetype`, `local_geometry_json`. Handles, `nested_path`, world geometry, and instance transforms are excluded from fixture identity. |
| Truncation | Cap is ~40 unique signatures per family. All families in v1 are **below** the cap (full unique sets stored). If truncation is needed later, document it in the family row and keep full-parquet recompute as an optional integration-style unit test. |

## Families included

| family_id | corpus_rank | definition_name(s) | definition_fingerprint (prefix) | unique signatures (P001) |
|-----------|-------------|--------------------|---------------------------------|--------------------------|
| `top1_pwf165` | 1 | `SYMB2_M_PWF165` | `39b95b5118323d4d…` | 11 |
| `top2_pwf231_pwf248` | 2 | `SYMB2_M_PWF231`, `SYMB2_M_PWF248` | `2ede8a4fcebd9582…` | 8 |
| `top3_pwf191` | 3 | `SYMB2_M_PWF191` | `9a1c6d15833092f3…` | 22 |
| `top4_pwf194` | 4 | `SYMB2_M_PWF194` | `a78b06f3c9ab76dc…` | 7 |
| `top5_pwf243` | 5 | `SYMB2_M_PWF243` | `b3115ea33fe4e1b5…` | 11 |
| `name_example_kk2p` | ~20 | `KK2P` | `3f7ef8a0ca8b8818…` | 21 |

`KK2P` is included only as a multi-port **name** example. The fixture does **not** declare electrical ports or internal connectivity.

## Fixture files

- `tests/fixtures/symbol_definition_fixtures_v1.json` — nested child signatures + sample INSERT stubs for synthetic inventory tests
- `tests/fixtures/symbol_definition_fixtures_v1.md` — this policy document

## How to regenerate from primitives

1. Ensure a non-held-out project run exists with:
   - `primitive_segments.parquet`
   - `symbol_definitions_v1.parquet`
2. Default source used for v1:
   ```
   .tmp/phase117_corpus_non_heldout/P001/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings/
   ```
3. For each target fingerprint / definition name(s):
   - Select non-`INSERT` rows with matching `definition_name`
   - Deduplicate child signatures on:
     `(source_entity_type, primitive_kind, layer, linetype, local_geometry_json)`
   - Recompute `definition_fingerprint_from_children` and assert equality with the stored full fingerprint from `symbol_definitions_v1.parquet`
4. Store only unique signatures (not every instance). Cap at ~40 if a family is huge; document truncation.
5. Do **not** copy handles, nested paths, world transforms, or invent ports.

Optional one-shot helper used during authoring (not part of the product API):

```text
python .tmp/_extract_symbol_fixtures_v1.py
```

## Tests

See `tests/unit/test_symbol_definition_fixtures.py`:

1. Recompute fingerprint from fixture `child_signatures` → match stored fingerprint.
2. Build a synthetic primitive DataFrame (1–2 INSERT rows + children from signatures) → `build_project_symbol_inventory` yields `UNKNOWN`, `critical_issue_eligible=false`, matching fingerprint, `declared_port_count=0`.
3. If P001 `primitive_segments.parquet` is present on disk, recompute full-children fingerprint for `SYMB2_M_PWF165` and match the fixture (skip if missing).

## Non-goals

- No production code changes.
- No held-out projects.
- No wire-component / pipeline / baseline / artifact changes.
- No port coordinate registration.
