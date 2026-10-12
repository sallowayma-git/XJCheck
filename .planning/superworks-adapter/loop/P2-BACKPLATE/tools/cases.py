"""P2-BACKPLATE step 3: build case records (for rendering and manual judgement). Read-only."""
import sys, json, random, re
import pandas as pd
sys.path.insert(0, 'F:/workspace/XJToolkit/.tmp/p2bp_work')
from load_common import *
cls = pd.read_csv('F:/workspace/XJToolkit/.tmp/p2bp_work/bp_class.csv', dtype=str, keep_default_na=False)
cls = cls[cls.dup_project == 'False']
manifest = json.load(open('F:/workspace/XJToolkit/.planning/superworks-adapter/corpus_manifest.json', encoding='utf-8'))
manifest = manifest['projects'] if isinstance(manifest, dict) else manifest
dxf = {}
for p in manifest:
    for f in p['files']:
        dxf[(p['project_id'], f['file_id'])] = f['dxf_path']
random.seed(5)
picks = []
def pick(cl, n, pool=None, key=None):
    x = cls[cls.cls == cl] if pool is None else pool
    rows = x.to_dict('records')
    random.shuffle(rows)
    seen = set(); out = []
    for r in rows:
        k = r['project_id']
        if key and k in seen:
            continue
        seen.add(k); out.append(r)
        if len(out) >= n: break
    return out
# stratified sample: 2 same-sheet agree (sanity), 1 other-sheet agree, 4 dev-diff, 2 conflict (virtual + geometric),
# 2 nonbp-only, 1 no-partner
sel = []
sel += [('AGREE_SAME_SHEET', r) for r in pick('AGREE_SAME_SHEET', 2, key=True)]
sel += [('AGREE_OTHER_SHEET', r) for r in pick('AGREE_OTHER_SHEET', 1, key=True)]
sel += [('ROW_AGREE_DEV_DIFF', r) for r in pick('ROW_AGREE_DEV_DIFF', 4, key=True)]
sel += [('CONFLICT_SAME_SHEET', r) for r in pick('CONFLICT_SAME_SHEET', 2, key=True)]
sel += [('PARTNER_NONBP_ONLY', r) for r in pick('PARTNER_NONBP_ONLY', 2, key=True)]
sel += [('NO_SW_PARTNER', r) for r in pick('NO_SW_PARTNER', 1, key=True)]
out = []
for cl, r in sel:
    pid = r['project_id']
    pr = pd.read_parquet(f"{dict(project_dirs())[pid]}/pairs.parquet")
    pair = pr[pr.pair_id == r['pair_id']].iloc[0]
    ev = jl(pair.evidence)
    tm = ev['table_mapping']
    file_id = pair.file_id
    out.append(dict(cls_eval=cl, project_id=pid, pair_id=r['pair_id'], sheet_id=r['sheet_id'], file_id=file_id,
                    sheet_no=r['sheet_no'], subtype=r['subtype'], filename=r['filename'], L=r['L'], R=r['R'],
                    row=int(r['row']), device=r['device'], e1=r['e1'], e2=r['e2'], e3=r['e3'],
                    left_text_raw=pair.left_value, right_text_raw=pair.right_value,
                    header_text_id=tm.get('header_text_id'), header_coord=tm.get('header_coord'),
                    middle_text_id=tm.get('middle_text_id'), middle_coord=tm.get('middle_coord'),
                    right_text_id=pair.right_text_id, right_coord=[pair.right_coord_x, pair.right_coord_y],
                    dxf=dxf.get((pid, file_id))))
json.dump(out, open('F:/workspace/XJToolkit/.tmp/p2bp_work/cases.json', 'w'), ensure_ascii=False, indent=1, default=str)
for c in out:
    print(c['cls_eval'], c['project_id'], c['sheet_no'], c['subtype'][:12], c['L'], c['R'], c['row'], c['device'], c['e1'][:60], c['e3'][:40], c['dxf'] is not None)
