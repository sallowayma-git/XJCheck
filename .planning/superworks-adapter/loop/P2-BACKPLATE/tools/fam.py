import json, re, pandas as pd
m = json.load(open('F:/workspace/XJToolkit/.planning/superworks-adapter/corpus_manifest.json', encoding='utf-8'))
m = m['projects'] if isinstance(m, dict) and 'projects' in m else m
fam = {}
for p in m:
    root = p['input_root']
    mm = re.search(r'GJ-(\d+)', root)
    if mm:
        f = 'GJ-' + mm.group(1)
    elif 'N2604' in root:
        f = 'N2604'
    elif 'PAC-885' in root:
        f = 'PAC-885'
    elif '变压器' in root:
        f = '变压器测控柜'
    elif '110' in root:
        f = '110kV'
    else:
        f = 'other'
    fam[p['project_id']] = (f, '')
json.dump(fam, open('F:/workspace/XJToolkit/.tmp/p2bp_work/fam.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(fam))
df = pd.read_csv('F:/workspace/XJToolkit/.tmp/p2bp_work/bp_class.csv', dtype=str, keep_default_na=False)
d = df[df.dup_project == 'False'].copy()
d['family'] = d.project_id.map(lambda p: fam.get(p, ('?', ''))[0])
print(pd.crosstab(d.family, d.cls).to_string())
print(d[d.cls == 'PARTNER_NONBP_ONLY'].project_id.value_counts().head(10).to_dict())
print({p: fam.get(p) for p in ['p057', 'p072', 'p067', 'p073', 'p022', 'p063', 'p074', 'p040', 'p001', 'p050']})
