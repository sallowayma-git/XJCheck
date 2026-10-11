import sys, json
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from crosspage_harness import load_pairs
want = sys.argv[2].split(',')
for p in load_pairs(sys.argv[1]):
    if p.pair_id in want:
        ev = p.evidence or {}
        print(p.pair_id, 'kind=', p.pair_kind, 'status=', p.status, 'line_group=', p.line_group_id)
        for k in ['semantic_kind','bridge_mapping_kind','terminal_short_bridge','series_chain','strip_connection_jumper','terminal_cross_strip_link','strip_corroborated','source','structured_source','pair_kind']:
            if k in ev: print('   ', k, '=', ev[k])
        tm = ev.get('table_mapping') or {}
        if tm: print('    table_mapping.same_strip_destination=', tm.get('same_strip_destination'))
        sw = ev.get('superworks') or {}
        print('    superworks.strip_relation=', sw.get('strip_relation'), 'keys=', sorted(sw.keys())[:12])
        print('    left/right', p.left_value, p.right_value, 'ev keys', sorted(ev.keys()))
