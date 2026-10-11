from pathlib import Path
import glob,json,collections
import pandas as pd
def J(x): return json.loads(x) if isinstance(x,str) else (x or {})
c=collections.Counter(); per=collections.Counter()
for d in sorted(glob.glob('.tmp/superworks_round13_full/p*/*/findings/pairs.parquet')):
    pid=Path(d).parts[2]
    df=pd.read_parquet(d)
    for r in df.itertuples():
        ev=J(r.evidence); tm=ev.get('table_mapping') or {}
        src='sw' if ev.get('source')=='superworks' else 'other'
        hit=False
        for side,v in (('left',r.left_value),('right',r.right_value)):
            if isinstance(v,str) and v.startswith('上接'):
                c[(src,side)]+=1; hit=True
        hp=tm.get('header_prefix')
        if isinstance(hp,str) and hp.startswith('上接') and src!='sw':
            c[(src,'header_prefix')]+=1; hit=True
        if hit and src!='sw': per[pid]+=1
print('round13 corpus 上接 hits by source/side:',dict(c))
print('non-sw pair projects with 上接:',dict(per))
