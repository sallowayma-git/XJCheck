import sys, json, glob; sys.path.insert(0,'.planning/superworks-adapter/loop/GAP/tools')
import gaplib as G, pandas as pd, numpy as np
from collections import Counter, defaultdict
f=pd.read_parquet('.tmp/gap_work/gap2_inner.parquet')
ins=pd.read_parquet('.tmp/gap_work/inserts.parquet')
sn=ins[ins.block=='SolidNode'][['project','file_id','x','y']]
dots=[]
for fp in glob.glob('.tmp/superworks_round19_full/p*/*/findings/sw_connect_dots.parquet'):
    from pathlib import Path
    pid=Path(fp).parts[-4]; d=pd.read_parquet(fp)
    if len(d): dots.append(d.assign(project=pid)[['project','file_id','x','y']])
dots=pd.concat(dots)
out=[]
for proj in G.iter_projects(only=sorted(set(f.project))):
    top=proj.lines[proj.lines.source_block_name.map(lambda v: not G.text(v))]
    sub=f[f.project==proj.pid]
    for r in sub.to_dict('records'):
        key=eval(r['wire_key']) if r['wire_key'].startswith('(') else r['wire_key']
        mem=proj.members.get(key,[])
        if len(mem)<2: continue
        horiz=r['axis']=='horizontal'
        mh={str(m['handle']) for m in mem}
        L=top[top.file_id==r['file_id']]
        cross_line=0; cross_layers=set(); cross_contact=0
        spans=sorted(((min(m['start_x'],m['end_x']),max(m['start_x'],m['end_x'])) if horiz else (min(m['start_y'],m['end_y']),max(m['start_y'],m['end_y']))) for m in mem)
        cross=float(mem[0]['start_y'] if horiz else mem[0]['start_x'])
        gaps=[(b1,a2) for (a1,b1),(a2,b2) in zip(spans,spans[1:]) if a2-b1>0.6]
        res=[]
        for a,b in gaps:
            mid=(a+b)/2
            hit=[]
            for l in L.itertuples():
                if str(l.handle) in mh: continue
                x0,y0,x1,y1=float(l.start_x),float(l.start_y),float(l.end_x),float(l.end_y)
                if horiz:
                    # a vertical line whose x lies inside the gap and which spans the run row
                    if abs(x0-x1)<1e-6 and a-0.6<=x0<=b+0.6 and min(y0,y1)<=cross<=max(y0,y1): hit.append(l.layer)
                else:
                    if abs(y0-y1)<1e-6 and a-0.6<=y0<=b+0.6 and min(x0,x1)<=cross<=max(x0,x1): hit.append(l.layer)
            txt=0
            tf=proj.texts[proj.texts.file_id==r['file_id']]
            if len(tf):
                tx=tf.insert_x.to_numpy(float); ty=tf.insert_y.to_numpy(float)
                if horiz: txt=int(((tx>=a-0.6)&(tx<=b+0.6)&(np.abs(ty-cross)<=6)).any())
                else: txt=int(((ty>=a-0.6)&(ty<=b+0.6)&(np.abs(tx-cross)<=6)).any())
            dt=0
            d=dots[(dots.project==proj.pid)&(dots.file_id==r['file_id'])]
            if len(d):
                dx=d.x.to_numpy(float); dy=d.y.to_numpy(float)
                v=dx if horiz else dy; o=dy if horiz else dx
                dt=int(((v>=a-0.6)&(v<=b+0.6)&(np.abs(o-cross)<=1.5)).any())
            res.append({'gap':round(b-a,2) if False else round(-(a-b),2),'cross_lines':len(hit),'cross_layers':','.join(sorted(set(map(str,hit)))),'text':txt,'dot':dt})
        out.append({'subset':r['subset'],'project':proj.pid,'port_id':r['port_id'],'n_gaps':len(gaps),
                    'gap_detail':json.dumps(res,ensure_ascii=False)})
o=pd.DataFrame(out); o.to_parquet('.tmp/gap_work/gap2_gapcontent.parquet',index=False)
rows=[]
for r in o.to_dict('records'):
    for g in json.loads(r['gap_detail']):
        rows.append({'subset':r['subset'],**g})
G2=pd.DataFrame(rows)
G2['content']=np.select([G2['dot']>0, G2['text']>0, G2['cross_lines']>0],['dot','text','cross_line'],'empty')
print(G2.groupby(['subset','content']).size().to_string())
print(G2[G2.content=='cross_line'].cross_layers.value_counts().head(8).to_string())
