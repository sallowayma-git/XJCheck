# Backplate standalone-title fallback census

## Scope and method

- Input corpus: `.planning/superworks-adapter/corpus_manifest.json` (77 projects); current replay artifacts: `.tmp/precision_loop_20261015/p057_slice_10/`.
- The replay contains 1,745 pages. This census is limited to 187 pages whose `sheet_category` is `背板接线图`, because `extract_table_pairs` only enters the backplate virtual-table builder for that category.
- Each relevant page's source DXF was opened read-only, its SHA-256 was checked against the manifest, and entity/layer/INSERT visibility was rebuilt using the same visibility helpers as the extractor. Raw title/device/model text and the current `table_extraction_summary` / `pairs.parquet` were joined by source DXF, sheet, and mapping text handles.
- The exact current resolver was re-run against `TextItem` / `SheetRecord` inputs reconstructed from the current replay's page and text outputs. The helper's own `composite_device_instance` field was not used as truth or as a correctness check. Fallback call counts are from this resolver re-run, not telemetry captured during the original replay. Current `logical_endpoint` and pair rows are reported only as pipeline outputs.

## Counts

- Current table mapping rows in the 77 replay projects: 37,033 total; `backplate_virtual_table` rows: 15,521.
- Current backplate table mappings joined to `pair_kind=table_mapping` by `(sheet_id, middle_text_id, right_text_id, logical_endpoint)`: 15,521/15,521.
- Reconstructed current-resolver reruns over backplate page evidence invoked `_visible_standalone_backplate_device` on 16 pages; it returned a device on 1 and no device on 15.
- Visible standalone `REAR WIRING` title pages in scope: 1; resolver-rerun fallback hits among these: 1; counterfactual helper probes with no result: 0.
- Current mapping rows whose logical endpoint carries the resolved device prefix without the fallback being called, among standalone-title pages: 0.
- Current mapping rows whose logical endpoint carries the device returned by an actual fallback call: 95.
- Pair statuses for the 15,521 matched current backplate mappings: {'discard': 11399, 'pass': 4122}.

### Resolver routes over 187 backplate pages

| Route | Pages |
|---|---:|
| `free_text_compound_device` | 9 |
| `prefixed_rear_wiring_caption` | 24 |
| `sheet_title_or_filename` | 138 |
| `standalone_title_fallback_hit` | 1 |
| `standalone_title_fallback_no_result` | 15 |

## Standalone-title candidate and route distinction

- `p057/S0009` / `09 装置背板.dwg`: source DXF `C:\Users\25788\AppData\Local\Temp\claude\F--workspace-XJToolkit\367e37bd-5006-413b-a449-e1c665a8b237\scratchpad\dxf\t2\16000 220kV电压并列柜\09 装置背板.dxf` (SHA-256 `612c4c770b4a4ddf391f7aa99e2d58f4cf7bc5e0c2f5f94f22df6918ce2c3bae`), visible raw caption [{'text_id': 'T1344', 'handle': '2629C', 'text': 'REAR WIRING', 'insert_x': 320.3673184357541, 'insert_y': 9.78491620111732}]; route=`standalone_title_fallback_hit`, resolved output=`7n`, helper-called=`True`, helper-return=`7n`.
  Current mapping rows/pairs: 95/95; pair IDs `P0001, P0002, P0003, P0004, P0005, P0006, P0007, P0008, P0009, P0010, P0011, P0012, P0013, P0014, P0015, P0016, P0017, P0018, P0019, P0020, P0021, P0022, P0023, P0024, P0025, P0026, P0027, P0028, P0029, P0030, P0031, P0032, P0033, P0034, P0035, P0036, P0037, P0038, P0039, P0040, P0041, P0042, P0043, P0044, P0045, P0046, P0047, P0048, P0049, P0050, P0051, P0052, P0053, P0054, P0055, P0056, P0057, P0058, P0059, P0060, P0061, P0062, P0063, P0064, P0065, P0066, P0067, P0068, P0069, P0070, P0071, P0072, P0073, P0074, P0075, P0076, P0077, P0078, P0079, P0080, P0081, P0082, P0083, P0084, P0085, P0086, P0087, P0088, P0089, P0090, P0091, P0092, P0093, P0094, P0095`; current logical endpoint outputs `7n201, 7n202, 7n205, 7n206, 7n207, 7n210, 7n211, 7n212, 7n219, 7n220, 7n223, 7n224, 7n227, 7n232, 7n401, 7n402, 7n405, 7n406, 7n407, 7n410, 7n411, 7n412, 7n419, 7n420, 7n423, 7n424, 7n427, 7n432, 7n301, 7n302, 7n305, 7n306, 7n307, 7n310, 7n311, 7n312, 7n323, 7n324, 7n327, 7n101, 7n102, 7n103, 7n104, 7n105, 7n106, 7n117, 7n118, 7n126, 7n127, 7n128, 7n501, 7n503, 7n505, 7n507, 7n509, 7n511, 7n517, 7n519, 7n523, 7n527, 7n529, 7n805, 7n807, 7n809, 7n811, 7n813, 7n815, 7n817, 7n605, 7n607, 7n609, 7n611, 7n613, 7n615, 7n617, 7n705, 7n707, 7n709, 7n711, 7n713, 7n715, 7n717, 7n502, 7n504, 7n506, 7n508, 7n510, 7n512, 7n518, 7n520, 7n522, 7n526, 7n528, 7n530, 7n532`.
  Current logical endpoints matching resolver device output: 95; not matching: 0; rows using actual helper result: 95. This compares two outputs only; neither establishes the correct physical device identity.

## Unknown shapes

Resolver-rerun misses inside the exact standalone-title scope: 0.
`unknown_shapes.csv` has a header row and no data rows. Boundary: only visible exact `REAR WIRING` captions with an optional numeric suffix, on backplate-category pages, are considered in-scope unknown candidates.

## Reproduction and source locations

Run from the repository root: `python .tmp/precision_loop_20261015/backplate_title_fallback_census_20261016/recompute.py`.
- `src/dwg_audit/audit/table_extractor.py:205-220`: backplate category dispatch into `_build_backplate_virtual_mappings`.
- `src/dwg_audit/audit/table_extractor.py:1557-1569`: source texts and resolver call site.
- `src/dwg_audit/audit/table_extractor.py:1788-1832`: resolver precedence and fallback condition.
- `src/dwg_audit/audit/table_extractor.py:1835-1882`: standalone title, unique bare-device, model-code, and proximity predicates.
- `src/dwg_audit/audit/table_extractor.py:1706-1737`: current logical endpoint creation and mapping evidence fields; reported output only.

## Files

- `case_level.csv`: one row per current backplate virtual-table mapping, joined to its exact current table_mapping pair and source-DXF entity handles.
- `page_census.csv`: all 187 backplate pages, including fallback route, standalone-title presence, and page-level pair/output identities.
- `unknown_shapes.csv`: visible in-scope title cases where the real helper missed or a counterfactual probe failed; runtime and counterfactual status remain separate.
- `recompute.py`: read-only census script.
