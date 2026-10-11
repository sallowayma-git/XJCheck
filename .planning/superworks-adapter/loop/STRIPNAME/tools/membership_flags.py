import json,sys,collections
sys.path.insert(0,'.planning/superworks-adapter/loop/STRIPNAME/tools')
from compare_stripname import load
PIDS=['p075','p061','p046','p045','p030','p048']
def flags(root):
    out={}
    for pid in PIDS:
        p,_,_,_=load(root,pid)
        for r in p.itertuples():
            ev=r.evidence if isinstance(r.evidence,dict) else json.loads(r.evidence)
            if ev.get('source')!='superworks': continue
            sm=ev.get('strip_membership') or ev.get('superworks',{}).get('strip_membership') or ('bridge' if ev.get('terminal_short_bridge') else ('cross' if ev.get('terminal_cross_strip_link') else None))
            out[(pid,r.pair_id)]=(sm, bool(ev.get('terminal_short_bridge')), bool(ev.get('terminal_cross_strip_link')), ev.get('strip_corroborated'), str(r.pair_kind))
    return out
R=flags('.tmp/superworks_round13_full'); V1=flags('.tmp/loop_stripname'); V2=flags('.tmp/loop_stripname_v2')
def diff(a,b):
    c=collections.Counter()
    for k in a:
        if k in b and a[k][:3]!=b[k][:3]: c[(a[k][0],a[k][1],a[k][2],'->',b[k][0],b[k][1],b[k][2])]+=1
    return c
print('round13 -> v2 membership/bridge flag changes:', sum(diff(R,V2).values()))
for k,v in diff(R,V2).most_common(8): print('  ',v,k)
print('v1 -> v2 membership/bridge flag changes:', sum(diff(V1,V2).values()))
for k,v in diff(V1,V2).most_common(8): print('  ',v,k)
print('pair_kind round13 -> v2 changes:', sum(1 for k in R if k in V2 and R[k][4]!=V2[k][4]))
print('pair_kind v1 -> v2 changes:', sum(1 for k in V1 if k in V2 and V1[k][4]!=V2[k][4]))
print('--- v1 flipped pairs:')
for k in V1:
    if k in V2 and V1[k][:3]!=V2[k][:3]:
        print('  ',k, V1[k][:3],'v2',V2[k][:3])
