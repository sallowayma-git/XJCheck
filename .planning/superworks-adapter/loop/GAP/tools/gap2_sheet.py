import glob, pandas as pd
from pathlib import Path
g=pd.read_parquet('.tmp/gap_work/gap2_inner.parquet')
titles={}
for f in glob.glob('.tmp/superworks_round19_full/p*/*/findings/pages.parquet'):
    pid=Path(f).parts[-4]
    p=pd.read_parquet(f)[['file_id','sheet_title','filename']]
    for r in p.itertuples(): titles[(pid,r.file_id)]=f"{r.sheet_title} {r.filename}"
g['title']=[titles.get((p,f),'') for p,f in zip(g.project,g.file_id)]
sig=g.title.str.contains('信号|告警|signal|alarm',case=False)
g['signal_sheet']=sig
m=pd.read_parquet('.tmp/gap_work/gap2_gapcontent.parquet')
print(pd.crosstab(g.subset,g.signal_sheet))
# runs whose merge needed a bridge wider than the default 4 units
print(pd.crosstab([g.subset,g.signal_sheet],g.max_gap.clip(upper=30).round(0)>4))
g[['subset','project','file_id','port_id','signal_sheet','max_gap']].to_parquet('.tmp/gap_work/gap2_sheet.parquet',index=False)
