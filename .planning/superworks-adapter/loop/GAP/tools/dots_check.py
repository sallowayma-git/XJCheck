import pandas as pd, glob, numpy as np
from pathlib import Path
n=pd.read_parquet('.tmp/gap_work/net_gap1.parquet')
ins=pd.read_parquet('.tmp/gap_work/inserts.parquet')
sn=ins[ins.block=='SolidNode'][['project','file_id','x','y']]
dots=[]
for f in glob.glob('.tmp/superworks_round19_full/p*/*/findings/sw_connect_dots.parquet'):
    pid=Path(f).parts[-4]
    d=pd.read_parquet(f)
    if len(d):
        dots.append(d.assign(project=pid)[['project','file_id','x','y']])
dots=pd.concat(dots)
print('solidnode', len(sn), 'sw dots', len(dots))
p=pd.read_parquet('.tmp/gap_work/gap1_probe.parquet')[['port_id','project','far_x','far_y']]
n=n.merge(p,on=['port_id','project'],how='left')
t=n[(n.subset=='GAP1')&(n.far_class=='line_tee')].copy()
def has_dot(r, tol=1.2):
    s=sn[(sn.project==r.project)&(sn.file_id==r.file_id)]
    if len(s) and (np.hypot(s.x-r.far_x,s.y-r.far_y)<=tol).any(): return 'solidnode'
    s=dots[(dots.project==r.project)&(dots.file_id==r.file_id)]
    if len(s) and (np.hypot(s.x-r.far_x,s.y-r.far_y)<=tol).any(): return 'swdot'
    return 'none'
t['dj']=[has_dot(r) for r in t.itertuples()]
print(t['dj'].value_counts().to_dict())
print(pd.crosstab(t['dj'], t.n_other_ports.clip(upper=3)).to_string())
