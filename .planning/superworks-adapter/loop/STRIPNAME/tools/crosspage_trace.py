import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from crosspage_harness import load_pairs
from dwg_audit.audit import rules as R
from collections import defaultdict

path = sys.argv[1]
pairs = load_pairs(path)
class Ctx: pass
ctx = Ctx(); ctx.pairs = pairs; ctx.high_threshold = 0.92
strip_links = R._superworks_strip_link_index(pairs)
hp = R._high_confidence_pairs(ctx)
scoped = defaultdict(list)
for pair in hp:
    if pair.pair_kind == "table_mapping" and R._is_superworks_pair(pair):
        m = R._table_mapping_evidence(pair)
        key = (pair.left_value, "superworks_strip_slot", m.get("sw_side"), m.get("sw_branch"))
    else:
        key = (pair.left_value, "logical_endpoint")
    scoped[key].append(pair)
for key, lp in scoped.items():
    if key[0] != sys.argv[2]:
        continue
    rights = {p.right_value for p in lp if p.right_value and not R._is_terminal_strip_bridge_claim(p)}
    sheets = {p.sheet_id for p in lp}
    print("KEY", key, "rights", sorted(rights), "sheets", sorted(sheets))
    for p in lp:
        print("   ", p.pair_id, p.sheet_id, p.left_value, '->', p.right_value, p.pair_kind, p.status, p.confidence, p.confidence_bucket,
              'bridge=', R._is_terminal_strip_bridge_claim(p), 'sw=', R._is_superworks_pair(p))
    if len(rights) > 1 and len(sheets) > 1:
        print("  one_terminal_end", R._values_are_one_terminal_end(sorted(rights)))
        print("  G8", R._is_strip_recorded_one_end_multi_wire(key[0], sorted(rights), strip_links))
        print("  backplate_attach", R._is_authoritative_terminal_strip_backplate_attachment_group(lp))
        print("  inline_component", R._is_authoritative_inline_component_cross_diagram_correspondence(lp))
        print("  structured_cardinality", all(R._is_superworks_pair(p) for p in lp) and R._is_authoritative_structured_cardinality_group(lp))
        print("  page_local_three_col", R._is_page_local_numeric_three_column_group(lp, key[0]))
        print("  cross_view", R._is_authoritative_cross_view_group(lp, shared_value=key[0], shared_side="left"))
        print("  distinct_scopes", R._are_backplate_pairs_in_distinct_explicit_scopes(lp))
