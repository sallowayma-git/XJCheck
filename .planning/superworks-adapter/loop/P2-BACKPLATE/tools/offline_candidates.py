"""Offline run of corroborate_backplate_virtual_pairs over finished round24 pairs (scratch, not a deliverable)."""
import sys, json, glob, math, collections
sys.path.insert(0, sys.argv[1])  # code root (src)
import pandas as pd
from dataclasses import fields
from dwg_audit.domain.models import Pair
from dwg_audit.audit.superworks_extractor import corroborate_backplate_virtual_pairs
RUN = sys.argv[2]
OUT = sys.argv[3]
names = {f.name for f in fields(Pair)}
def clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v
allc = []
stats = collections.Counter()
corr_rows = []
for d in sorted(glob.glob(f'{RUN}/p*/*/findings/pairs.parquet')):
    pid = d.replace(chr(92), '/').split('/')[-4]
    df = pd.read_parquet(d)
    pairs = []
    for r in df.to_dict('records'):
        kw = {k: clean(v) for k, v in r.items() if k in names}
        kw['evidence'] = json.loads(r['evidence']) if isinstance(r['evidence'], str) else (r['evidence'] or {})
        kw['alternative_pair_candidate_ids'] = []
        pairs.append(Pair(**kw))
    before = {p.pair_id: p.evidence for p in pairs}
    out, cands = corroborate_backplate_virtual_pairs(pairs)
    for p in out:
        if 'sw_backplate_corroboration' in (p.evidence or {}):
            stats['corroborated'] += 1
            c = p.evidence['sw_backplate_corroboration']
            corr_rows.append(dict(project=pid, pair_id=p.pair_id, sheet=p.sheet_id, R=p.right_value, L=p.left_value, **{k: str(v) for k, v in c.items()}))
    for c in cands:
        c = dict(c); c['project'] = pid
        allc.append(c)
        stats[c['contradiction_type']] += 1
    stats['bp_pass'] += sum(1 for p in pairs if (p.evidence or {}).get('table_mapping', {}) and (p.evidence['table_mapping'] or {}).get('mapping_mode') == 'backplate_virtual_table' and p.status == 'pass')
    stats['projects'] += 1
print(dict(stats))
pd.DataFrame(allc).to_csv(OUT + '_candidates.csv', index=False, encoding='utf-8-sig')
pd.DataFrame(corr_rows).to_csv(OUT + '_corroborated.csv', index=False, encoding='utf-8-sig')
