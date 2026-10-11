import sys, json; sys.path.insert(0,'.planning/superworks-adapter/loop/GAP/tools')
import gaplib as G, pandas as pd, numpy as np
from collections import Counter, defaultdict
d=pd.read_parquet('.tmp/gap_work/gap2_detail.parquet')
out=[]
for proj in G.iter_projects(only=sorted(set(d.project))):
    sub=d[d.project==proj.pid]
    ports_by_file=defaultdict(list)
    for p in proj.ports.to_dict('records'):
        for c in G.contacts_of(p):
            ports_by_file[(p['file_id'],str(c.get('wire_handle')))].append((p['record_id'],float(c['x']),float(c['y'])))
    for r in sub.to_dict('records'):
        fid=r['file_id']; k=r['wire_key']
        key=eval(k) if k.startswith('(') else k
        mem=proj.members.get(key,[])
        if not mem: out.append({**r,'inner_gaps':-1,'members_with_2ends':-1,'interior_ports':-1}); continue
        horiz = r['axis']=='horizontal'
        segs=[]
        for m in mem:
            a=(float(m['start_x']),float(m['start_y'])); b=(float(m['end_x']),float(m['end_y']))
            lo,hi=(min(a[0],b[0]),max(a[0],b[0])) if horiz else (min(a[1],b[1]),max(a[1],b[1]))
            segs.append((lo,hi,m['handle']))
        segs.sort()
        ports=[]
        for m in mem:
            for pid_,x,y in ports_by_file.get((fid,str(m['handle'])),[]):
                ports.append((pid_, x if horiz else y, m['handle']))
        # unique ports
        seen={}
        for pid_,v,h in ports: seen.setdefault(pid_,(v,h))
        pv=[v for v,_ in seen.values()]
        # members with ports at both of their ends (each segment carries its own two ports)
        per_member=[]
        for lo,hi,h in segs:
            n_end=sum(1 for v,_ in seen.values() if abs(v-lo)<=1.0 or abs(v-hi)<=1.0)
            per_member.append(n_end)
        members_2ends=sum(1 for n in per_member if n>=2)
        # inner gaps: gap between consecutive segments with ports at both inner boundaries (<=1.0)
        inner=0
        for (lo1,hi1,_),(lo2,hi2,_) in zip(segs,segs[1:]):
            if lo2-hi1>0.6:
                left=any(abs(v-hi1)<=1.0 for v in pv); right=any(abs(v-lo2)<=1.0 for v in pv)
                if left and right: inner+=1
        interior=sum(1 for v in pv if any(lo+1.0<v<hi-1.0 for lo,hi,_ in segs))
        out.append({**r,'inner_gaps':inner,'members_with_2ends':members_2ends,'interior_ports':interior,'per_member_ends':json.dumps(per_member)})
frame=pd.DataFrame(out)
frame.to_parquet('.tmp/gap_work/gap2_inner.parquet',index=False)
for s in ['GAP2a','GAP2b']:
    x=frame[frame.subset==s]
    print(s, len(x))
    print(' inner_gaps>0', (x.inner_gaps>0).sum(), ' members_with_2ends>=2', (x.members_with_2ends>=2).sum(), ' interior_ports>0', (x.interior_ports>0).sum())
    print(' all members carry 2 ends', (x.members_with_2ends==x.n_members).sum(), ' pattern counts', Counter(zip(x.inner_gaps.clip(upper=2), x.interior_ports.clip(upper=2))).most_common(8))
