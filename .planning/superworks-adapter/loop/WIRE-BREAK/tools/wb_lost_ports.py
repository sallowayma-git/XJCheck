import pandas as pd, json, sys
from collections import Counter
projects=['p001','p003','p022','p026','p044','p051','p061','p071','p074','p075']
lost=Counter(); newc=Counter(); examples=[]
for pid in projects:
    import glob
    bdir=glob.glob(f'.tmp/superworks_round22_full/{pid}/*/findings')[0]
    ndir=glob.glob(f'.tmp/loop_wbreak/{pid}/*/findings')[0]
    b=pd.read_parquet(bdir+'/sw_port_coverage.parquet'); n=pd.read_parquet(ndir+'/sw_port_coverage.parquet')
    m=b.merge(n,on='port_id',suffixes=('_b','_n'))
    d=m[(m.consumed_b)&(~m.consumed_n)]
    for _,r in d.iterrows():
        lost[(pid,r.endpoint_identity_b)]+=1
        if len(examples)<40: examples.append((pid,r.port_id,r.endpoint_identity_b,r.category_b))
    g=m[(~m.consumed_b)&(m.consumed_n)]
    newc[pid]=len(g)
print('lost ports total', sum(lost.values()))
print('gained ports', dict(newc))
for e in examples[:40]: print(e)
