from pathlib import Path
import glob,json,sys
from collections import defaultdict,Counter
sys.path.insert(0,'.planning/superworks-adapter/loop/STRIPNAME/tools')
from identity_census import norm
rows=[]
for f in sorted(glob.glob('.tmp/loop_stripname_census/p*.json')): rows+=json.load(open(f,encoding='utf-8'))
rows=[r for r in rows if 'error' not in r]
dz=defaultdict(set); hd=defaultdict(set)
for r in rows:
    rt=norm(r['row_text'] or '')
    dz[r['project_id']].add(norm(r['dz_name'])+rt)
    hd[r['project_id']].add(norm(r['header_text'] or '')+rt)
diag=json.load(open('.planning/superworks-adapter/unconsumed_port_diagnostics.json',encoding='utf-8'))
c=Counter(); aff=[]
for p in diag:
    i=(p.get("endpoint_identity") or "").strip().split("~")[0]
    pid=p['project_id']
    inDZ = i in dz[pid]; inH = i in hd[pid]
    key=('in_dz' if inDZ else 'no_dz')+'/'+('in_hdr' if inH else 'no_hdr')
    c[key]+=1
    if inDZ and not inH: aff.append(p)
print(c)
print('DZ-only (affected by header defect):', len(aff))
print('diag rows:', len(diag))
import pandas as pd
r13={}
for d in glob.glob('.tmp/superworks_round13_full/p*/*/findings/sw_port_coverage.parquet'):
    pid=Path(d).parts[2]
    cov=pd.read_parquet(d)
    for r in cov.itertuples(): r13[r.port_id]=(bool(r.consumed), bool(r.eligible))
cc=Counter()
for p in aff:
    cc[r13.get(p['port_id'],('missing',None))]+=1
print('affected diag ports, round13 (consumed, eligible):', cc)
print('affected diag ports by project:', Counter(p['project_id'] for p in aff).most_common(10))
