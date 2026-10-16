# p072/p073 `1-1n` → `1n` identity audit

## Result

- Compared previous replay `.tmp/p1_fpfix_full77` with the newer 10-project replay `.tmp/precision_loop_20261015/p057_slice_10` using `(project, file_id, sheet_id, left_text_id, right_text_id, pair_kind)`. The candidate set is 158 stable pair records: p072 79 and p073 79.
- A field-by-field comparison of all 158 pairs preserves status, endpoints, and all non-identity fields. After normalizing identity echoes in `table_mapping.composite_device_instance`, `logical_endpoint`, and SW evidence, the only substantive change is the backplate instance prefix from `1-1n` to `1n`.
- Randomized, header-stratified visual sample: 30 cases, 15 per project, covering all seven header prefixes in each project. All 30 independently support the new `1n` prefix (yes 30, no 0, uncertain 0).
- Each case has its own screenshot. 30/30 paths exist; 30/30 `(project, pair_id)` and screenshot paths are unique; image byte hashes are also 30/30 unique. No missing images.

## Independent drawing evidence

The screenshots are generated from the frozen converted DXFs and show three uncensored drawing crops per case: the visible page title, the literal terminal-table header, and the sampled row. p072 and p073 both visibly read `1n REAR WIRING`; the title's `1n` is reinforced by a separate visible MARK text `1n`. Raw-DXF inspection records two old `1-1n` MARK texts per page with `invisible=1`. No SuperWORKS overlay, selected pair truth, or pipeline identity decision was used to decide the new prefix.

## Row-level record

See [`judgments.csv`](judgments.csv) for all fields and per-example rationale. [`sample_assignments.csv`](sample_assignments.csv) preserves the seeded sample; [`change_population.csv`](change_population.csv) lists all 158 transitions; [`dxf_inventory.json`](dxf_inventory.json) records source text handles, layers, flags, and hashes; [`screenshot_validation.csv`](screenshot_validation.csv) lists image paths, dimensions, and SHA-256 hashes. All 30 reviewed screenshots are stored beside this report under [`screenshots/`](screenshots/).

## Reproduction and references

- Run `python .tmp/precision_loop_20261015/p072_p073_identity_audit_20261016/generate_audit.py` to rebuild the change population and seeded screenshots; run `python .tmp/precision_loop_20261015/p072_p073_identity_audit_20261016/finalize_audit.py` after visual review to produce row judgments and image validation.
- The comparison design documented 158 transitions and 79 per project in `.planning/superworks-adapter/loop/REVIEW-2026-10-16/README.md:33,67-73`; its stable key is implemented by `.planning/superworks-adapter/loop/REVIEW-2026-10-16/tools/pair_join.py:6-10,22-31`.
- This audit's independent key comparison and 79-per-project assertions are in `generate_audit.py:89-117`; raw DXF text inventory is at `generate_audit.py:49-76`; seeded stratification and screenshot generation are at `generate_audit.py:169-214`; missing-image, uniqueness, and hash checks are in `finalize_audit.py:17-71`.
- The crop renderer is `.planning/superworks-adapter/round4/I/round4_samples_v2.py:201-221,363-403`.

## Per-case screenshots

- [01 p072 P0003: 1-1n/NR1181C-2 → 1n/NR1181C-2 — yes](<screenshots/01_p072_P0003.png>)
- [02 p072 P0011: 1-1n/NR1181C-6 → 1n/NR1181C-6 — yes](<screenshots/02_p072_P0011.png>)
- [03 p072 P0014: 1-1n/NR1502A-1 → 1n/NR1502A-1 — yes](<screenshots/03_p072_P0014.png>)
- [04 p072 P0023: 1-1n/NR1502A-15 → 1n/NR1502A-15 — yes](<screenshots/04_p072_P0023.png>)
- [05 p072 P0026: 1-1n/NR1502A-22 → 1n/NR1502A-22 — yes](<screenshots/05_p072_P0026.png>)
- [06 p072 P0033: 1-1n/NR1548C-20 → 1n/NR1548C-20 — yes](<screenshots/06_p072_P0033.png>)
- [07 p072 P0037: 1-1n/RX1-1 → 1n/RX1-1 — yes](<screenshots/07_p072_P0037.png>)
- [08 p072 P0038: 1-1n/RX1-2 → 1n/RX1-2 — yes](<screenshots/08_p072_P0038.png>)
- [09 p072 P0040: 1-1n/TX2-4 → 1n/TX2-4 — yes](<screenshots/09_p072_P0040.png>)
- [10 p072 P0042: 1-1n/TX2-6 → 1n/TX2-6 — yes](<screenshots/10_p072_P0042.png>)
- [11 p072 P0045: 1-1n/NR1552A-5 → 1n/NR1552A-5 — yes](<screenshots/11_p072_P0045.png>)
- [12 p072 P0049: 1-1n/NR1552A-16 → 1n/NR1552A-16 — yes](<screenshots/12_p072_P0049.png>)
- [13 p072 P0053: 1-1n/NR1552A-22 → 1n/NR1552A-22 — yes](<screenshots/13_p072_P0053.png>)
- [14 p072 P0061: 1-1n/NR1551A-10 → 1n/NR1551A-10 — yes](<screenshots/14_p072_P0061.png>)
- [15 p072 P0072: 1-1n/NR1551A-24 → 1n/NR1551A-24 — yes](<screenshots/15_p072_P0072.png>)
- [16 p073 P0002: 1-1n/NR1181C-7 → 1n/NR1181C-7 — yes](<screenshots/16_p073_P0002.png>)
- [17 p073 P0006: 1-1n/NR1181C-9 → 1n/NR1181C-9 — yes](<screenshots/17_p073_P0006.png>)
- [18 p073 P0017: 1-1n/NR1502A-6 → 1n/NR1502A-6 — yes](<screenshots/18_p073_P0017.png>)
- [19 p073 P0025: 1-1n/NR1502A-17 → 1n/NR1502A-17 — yes](<screenshots/19_p073_P0025.png>)
- [20 p073 P0035: 1-1n/NR1548C-28 → 1n/NR1548C-28 — yes](<screenshots/20_p073_P0035.png>)
- [21 p073 P0038: 1-1n/RX1-2 → 1n/RX1-2 — yes](<screenshots/21_p073_P0038.png>)
- [22 p073 P0041: 1-1n/TX2-5 → 1n/TX2-5 — yes](<screenshots/22_p073_P0041.png>)
- [23 p073 P0042: 1-1n/TX2-6 → 1n/TX2-6 — yes](<screenshots/23_p073_P0042.png>)
- [24 p073 P0043: 1-1n/NR1552A-1 → 1n/NR1552A-1 — yes](<screenshots/24_p073_P0043.png>)
- [25 p073 P0052: 1-1n/NR1552A-19 → 1n/NR1552A-19 — yes](<screenshots/25_p073_P0052.png>)
- [26 p073 P0058: 1-1n/NR1551A-5 → 1n/NR1551A-5 — yes](<screenshots/26_p073_P0058.png>)
- [27 p073 P0060: 1-1n/NR1551A-7 → 1n/NR1551A-7 — yes](<screenshots/27_p073_P0060.png>)
- [28 p073 P0063: 1-1n/NR1551A-12 → 1n/NR1551A-12 — yes](<screenshots/28_p073_P0063.png>)
- [29 p073 P0067: 1-1n/NR1551A-17 → 1n/NR1551A-17 — yes](<screenshots/29_p073_P0067.png>)
- [30 p073 P0077: 1-1n/NR1551A-27 → 1n/NR1551A-27 — yes](<screenshots/30_p073_P0077.png>)
