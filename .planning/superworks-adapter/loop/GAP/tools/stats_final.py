import sys, json; sys.path.insert(0,'.planning/superworks-adapter/loop/GAP/tools')
import gaplib as G, pandas as pd, numpy as np
from collections import Counter, defaultdict
det=pd.read_parquet('.tmp/gap_work/gap1_detail.parquet')
tee=det[(det.subset=='GAP1')&(det.far_class=='line_tee')]
# T-line geometry: find the line containing F in the interior, its orientation and how many other lines touch it
res=[]
cache={}
for pid,grp in tee.groupby('project'):
    proj=next(G.iter_projects(only=[pid]))
    top=proj.lines[proj.lines.source_block_name.map(lambda v: not G.text(v))]
    for fid,g in grp.groupby('file_id'):
        L=top[top.file_id==fid]
        for r in g.to_dict('records'):
            fx,fy=float(r['far_x']),float(r['far_y'])
            cand=[]
            for l in L.itertuples():
                if str(l.handle)==str(r['wire_handle']): continue
                x0,y0,x1,y1=float(l.start_x),float(l.start_y),float(l.end_x),float(l.end_y)
                dx,dy=x1-x0,y1-y0; L2=dx*dx+dy*dy or 1e-12
                t=((fx-x0)*dx+(fy-y0)*dy)/L2
                if 0.02<t<0.98:
                    px,py=x0+t*dx,y0+t*dy
                    if np.hypot(fx-px,fy-py)<=0.6: cand.append((str(l.handle),abs(dx)<1e-6,abs(dy)<1e-6,np.hypot(dx,dy)))
            if not cand: res.append({'orient':'none'}); continue
            h,vert,horiz,ln=cand[0]
            # stubs: other lines having an endpoint on the T-line (within 0.6)
            ends=[]
            for l in L.itertuples():
                if str(l.handle)==h: continue
                for ex,ey in ((float(l.start_x),float(l.start_y)),(float(l.end_x),float(l.end_y))):
                    x0,y0,x1,y1=[float(v) for v in (cand and [0,0,0,0])] if False else (None,None,None,None)
            res.append({'orient':'vertical' if vert else ('horizontal' if horiz else 'diagonal'),'tline_len':ln,'n_cand':len(cand)})
o=pd.DataFrame(res)
print('T-line orientation', o.orient.value_counts().to_dict())
print('T-line length', o.tline_len.describe().round(1).to_dict())
# unique runs and ports per run
f=pd.read_parquet('.tmp/gap_work/gap2_inner.parquet')
print('GAP2 unique runs', f.groupby('subset').apply(lambda x: x[['project','file_id','wire_key']].drop_duplicates().shape[0]).to_dict())
print('GAP2 ports per unique run (device terminals)', f.groupby(['subset']).size().to_dict())
gc=pd.read_parquet('.tmp/gap_work/gap2_gapcontent.parquet')
per=[]
for r in gc.to_dict('records'):
    det2=json.loads(r['gap_detail'])
    kinds=set('dot' if g['dot'] else 'text' if g['text'] else 'cross' if g['cross_lines'] else 'empty' for g in det2)
    per.append({'subset':r['subset'],'kinds':'+'.join(sorted(kinds))})
p=pd.DataFrame(per)
print(p.groupby(['subset','kinds']).size().to_string())
