import json,glob,collections,sys
sys.path.insert(0,'.planning/superworks-adapter/loop/STRIPNAME/tools')
from identity_census import norm
rows=[]
for f in sorted(glob.glob('.tmp/loop_stripname_census/p*.json')): rows+=json.load(open(f,encoding='utf-8'))
rows=[r for r in rows if 'error' not in r]
cont=collections.defaultdict(set); cont_n=collections.Counter(); oldid=collections.defaultdict(set)
for r in rows:
    old=norm(r['header_text'] or '')+norm(r['row_text'] or '')
    new=norm(r['dz_name'] or '')+norm(r['row_text'] or '')
    oldid[r['project_id']].add(old)
    if old!=new:
        cont[r['project_id']].add(new); cont_n[r['project_id']]+=1
d=json.load(open('.planning/superworks-adapter/unconsumed_port_diagnostics.json',encoding='utf-8'))
aff=collections.Counter(); tot=collections.Counter()
for p in d:
    tot[p['project_id']]+=1
    ident=p.get('endpoint_identity') or ''
    if ident in cont[p['project_id']] and ident not in oldid[p['project_id']]:
        aff[p['project_id']]+=1
print('projects with changed rows:',len(cont_n),' total changed rows',sum(cont_n.values()),' affected unconsumed ports',sum(aff.values()))
for pid,n in aff.most_common(15): print(pid,'affected_unconsumed=',n,'changed_rows=',cont_n[pid],'unconsumed_total=',tot[pid])
print('top by changed rows:',cont_n.most_common(10))
