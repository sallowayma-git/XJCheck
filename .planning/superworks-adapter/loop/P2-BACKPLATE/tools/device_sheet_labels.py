import json, glob, re, sys
import pandas as pd
cases = json.load(open('F:/workspace/XJToolkit/.tmp/p2bp/cases.json', encoding='utf-8'))
RUN = 'F:/workspace/XJToolkit/.tmp/superworks_round24_full'
def tf(project):
    return pd.read_parquet(glob.glob(f'{RUN}/{project}/*/findings/texts.parquet')[0], columns=['sheet_id','normalized_text','source_block_name'])
cache = {}
for c in cases:
    if c['cls'] != 'device_prefix_differs':
        continue
    p = c['project']
    if p not in cache:
        cache[p] = tf(p)
    t = cache[p]
    s = t[t.sheet_id == c['sheet_id']]
    v1, sw = c['v1_device'], c['sw_device']
    v1_hits = s[s.normalized_text.fillna('').str.contains(re.escape(v1), regex=True)]
    sw_hits = s[s.normalized_text.fillna('').str.startswith(sw)]
    v1_proj = t[t.normalized_text.fillna('').str.startswith(v1)]
    sw_proj = t[t.normalized_text.fillna('').str.startswith(sw)]
    # sheet-level prefixes of device-like labels
    dev_like = s.normalized_text.fillna('').str.extract(r'^(\d+(?:-\d+)?n)')[0].dropna()
    top = dev_like.value_counts().head(4).to_dict()
    print(f"#{c['case_no']} {p} sh{c['sheet_no']} V1 {v1}: sheet {len(v1_hits)} (proj {len(v1_proj)}) | SW {sw}: sheet {len(sw_hits)} (proj {len(sw_proj)}) | sheet device-like prefixes {top}")
    ex = list(s[s.normalized_text.fillna('').str.contains(re.escape(v1))].normalized_text.head(4))
    if ex: print('    v1 texts on sheet:', ex)
