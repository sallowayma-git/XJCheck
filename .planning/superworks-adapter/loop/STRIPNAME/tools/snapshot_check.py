import json,hashlib,pathlib,sys
m=json.load(open('.tmp/superworks_round13_full/code_manifest.json',encoding='utf-8'))
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
for base in ['.tmp/loop_gnd_g1_src','src','.tmp/loop_stripname_v2_src']:
    b=pathlib.Path(base)
    d=[k for k,v in m.items() if h(b/k.replace(chr(92),'/'))!=v]
    print(base,'differ from round13:',d)
