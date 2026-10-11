import json, glob, sys
import pandas as pd
ROOT='.tmp/superworks_round12_full'
TARGETS=[('p062','21000','PC0019'),('p062','21000','PC0125'),('p071','30000','PC0053'),('p075','8000_9000_-','PC0232'),('p075','8000_9000_-','PC0440')]
def jd(o):
    return json.dumps(o, ensure_ascii=False, default=lambda x: x.tolist() if hasattr(x,'tolist') else str(x))
out={}
for proj,run,pid in TARGETS:
    base=f'{ROOT}/{proj}/{run}/findings'
    p=pd.read_parquet(f'{base}/pairs.parquet')
    row=p[p.pair_id==pid]
    print('=== ',proj,pid, len(row))
    r=row.iloc[0].to_dict()
    ev=r.get('evidence')
    try: ev=json.loads(ev) if isinstance(ev,str) else ev
    except Exception: pass
    r['evidence']=ev
    print(jd(r)[:4000])
    out[f'{proj}_{pid}']=r
json.dump(out, open('.tmp/_dump_targets_tmp.json','w',encoding='utf-8'), ensure_ascii=False, default=str) if False else None
