import sys, json, re; sys.path.insert(0,'.planning/superworks-adapter/loop/GAP/tools')
import gaplib as G, pandas as pd, numpy as np
from collections import Counter
f=pd.read_parquet('.tmp/gap_work/gap2_inner.parquet')
numre=re.compile(r'^[0-9A-Za-z\-]{2,12}$')
rows=[]
for proj in G.iter_projects(only=sorted(set(f.project))):
    sub=f[f.project==proj.pid]
    for r in sub.to_dict('records'):
        key=eval(r['wire_key']) if r['wire_key'].startswith('(') else r['wire_key']
        mem=proj.members.get(key,[])
        if len(mem)<2: continue
        horiz=r['axis']=='horizontal'
        tf=proj.texts[proj.texts.file_id==r['file_id']]
        tx=tf.insert_x.to_numpy(float); ty=tf.insert_y.to_numpy(float); tt=tf.text.astype(str).str.strip().to_numpy()
        spans=sorted(((min(m['start_x'],m['end_x']),max(m['start_x'],m['end_x'])) if horiz else (min(m['start_y'],m['end_y']),max(m['start_y'],m['end_y']))) for m in mem)
        cross=float(mem[0]['start_y'] if horiz else mem[0]['start_x'])
        for (a1,b1),(a2,b2) in zip(spans,spans[1:]):
            if a2-b1<=0.6: continue
            def labels_near(lo,hi):
                # texts within 5 units of the segment's span and within 6 units across the run
                if horiz: m=(tx>=lo-1)&(tx<=hi+1)&(np.abs(ty-cross)<=6)
                else: m=(ty>=lo-1)&(ty<=hi+1)&(np.abs(tx-cross)<=6)
                return {str(t).casefold() for t,k in zip(tt,m) if k and numre.match(str(t))}
            L=labels_near(a1,b1); R=labels_near(a2,b2)
            shared=bool(L & R)
            rows.append({'subset':r['subset'],'gap':round(a2-b1,2),'L':len(L),'R':len(R),'shared':shared,
                         'either_empty':(len(L)==0 or len(R)==0)})
df=pd.DataFrame(rows)
df.to_parquet('.tmp/gap_work/gap2_labels.parquet',index=False)
print(len(df))
print(df.groupby(['subset','shared']).size().to_string())
print(df.groupby(['subset','either_empty']).size().to_string())
print(pd.crosstab([df.subset,df.shared],df.either_empty).to_string())
