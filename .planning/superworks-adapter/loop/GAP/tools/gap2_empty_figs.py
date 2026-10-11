import sys, json, random; sys.path.insert(0,'.planning/superworks-adapter/loop/GAP/tools')
import pandas as pd, numpy as np
from pathlib import Path
import gap_figs as F
import gap_render as R
work=Path('.tmp/gap_work'); out=Path('.tmp/gap_work/figs2'); (out/'png').mkdir(parents=True,exist_ok=True)
gc=pd.read_parquet(work/'gap2_gapcontent.parquet')
g2=pd.read_parquet(work/'gap2_inner.parquet')
rows=[]
for r in gc.to_dict('records'):
    det=json.loads(r['gap_detail'])
    empties=[g for g in det if g['text']==0 and g['dot']==0 and g['cross_lines']==0]
    rows.append({'project':r['project'],'port_id':r['port_id'],'n_empty':len(empties),'n_gaps':len(det),'subset':r['subset']})
e=pd.DataFrame(rows)
m=g2.merge(e[['project','port_id','n_empty']],on=['project','port_id'])
m=m[(m.n_empty>0)&(m.n_members<=3)]
rng=random.Random(20261012)
picked=m.sample(n=9,random_state=20261012)
recs=picked.to_dict('records')
samples=[]; sheet=0
for i in range(0,len(recs),3):
    sheet+=1; panels=[]; header=[]
    for j,row in enumerate(recs[i:i+3]):
        pl,meta=F.g2_build(row,work)
        panels.extend(pl)
        header.append(f"E-{i+j+1:02d} {row['subset']} {meta['title']} [{row['project']} {row['file_id']}] 空断口")
        samples.append({'sample':f"E-{i+j+1:02d}",'subset':row['subset'],'project':row['project'],'file_id':row['file_id'],'port_id':row['port_id'],'sheet':f'GAP_G2E_{sheet:02d}.png',**meta['record']})
    R.render(out/'png'/f'GAP_G2E_{sheet:02d}.png',['GAP 目视样例 G2E（空断口：无文字、无圆点、无穿过线）']+header,panels,cols=2)
Path(out/'samples_e.json').write_text(json.dumps(samples,ensure_ascii=False,indent=1,default=str),encoding='utf-8')
print('done', len(samples), len(m))
