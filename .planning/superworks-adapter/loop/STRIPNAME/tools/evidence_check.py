import glob,json,sys,collections
from pathlib import Path
import pandas as pd
sys.path.insert(0,'.planning/superworks-adapter/loop/STRIPNAME/tools')
from identity_census import norm
cen=collections.Counter(); cen_src=collections.Counter()
census={}
for f in glob.glob('.tmp/loop_stripname_census/p*.json'):
    for r in json.load(open(f,encoding='utf-8')):
        if 'error' in r: continue
        pid=r['project_id']
        mis = norm(r['header_text'] or '')!=norm(r['dz_name'] or '')
        census[(pid,r['row_handle'],r['file_id'])]=mis
for pid in ['p075','p061','p046','p045','p030','p048']:
    s=pd.read_parquet(glob.glob(f'.tmp/loop_stripname/{pid}/*/findings/sw_strip_rows.parquet')[0])
    mm=0; src=collections.Counter(); bad=0; n=0
    for r in s.itertuples():
        v=json.loads(r.validation) if isinstance(r.validation,str) else r.validation
        src[v.get('strip_name_source')]+=1
        if v.get('header_mismatch'): mm+=1
        key=(pid, r.row_handle, r.file_id)
        if key in census:
            n+=1
            if census[key]!=bool(v.get('header_mismatch')): bad+=1
    print(pid,'rows',len(s),'header_mismatch',mm,'sources',dict(src),'matched census rows',n,'disagree',bad)
