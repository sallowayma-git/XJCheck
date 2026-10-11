import json,sys,collections,glob
sys.path.insert(0,'.planning/superworks-adapter/loop/STRIPNAME/tools')
from identity_census import norm
rows=[]
for f in sorted(glob.glob('.tmp/loop_stripname_census/p*.json')): rows+=json.load(open(f,encoding='utf-8'))
print('total',len(rows),'errors',sum('error' in r for r in rows), 'projects', len(glob.glob('.tmp/loop_stripname_census/p*.json')))
c=collections.Counter(); ex=collections.defaultdict(list)
for r in rows:
    if 'error' in r: continue
    h=r['header_text'] or ''; dz=r['dz_name']; rt=r['row_text'] or ''
    if not dz:
        c['dz_missing']+=1; ex['dz_missing'].append((r['project_id'],r['filename'],h,rt)) if len(ex['dz_missing'])<5 else None; continue
    cont = norm(h).startswith('上接')
    hn=norm(h)
    key=('continuation' if cont else ('header_empty' if not hn else 'normal'), 'hdr==dz' if hn==norm(dz) else 'hdr!=dz')
    old=hn+norm(rt); new=norm(dz)+norm(rt)
    c[key+('old==new' if old==new else 'old!=new',)]+=1
    if len(ex[key])<6: ex[key].append((r['project_id'],r['filename'],h,dz,rt))
for k,v in sorted(c.items(), key=str): print(k,v)
for k in ex:
    print('---',k)
    for e in ex[k]: print('  ',e)
