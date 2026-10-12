"""Permutation control on bp_class.csv: give row i the SW partner lists of a random other row j (same project).
Chance agreement of the row(+device) rule = the rate at which a wrong R's SW partners still 'agree' with row i."""
import json, random, re
import pandas as pd
random.seed(7)
UP = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
def parse(x):
    """Same rule as classify.py parse_bp."""
    if not x: return None
    m = re.match(r'^(?P<dev>.*?)(?P<digits>\d{3,})$', x)
    if m and m.group('dev').rstrip(UP).endswith('n'):
        d = m.group('digits'); return dict(dev=m.group('dev').rstrip(UP), row=int(d[-2:]))
    m = re.match(r'^(?P<dev>.*?)(?P<letter>[A-Z])(?P<digits>\d{2})$', x)
    if m and m.group('dev').endswith('n'):
        return dict(dev=m.group('dev'), row=int(m.group('digits')))
    return None
def ndev(d): return re.sub(r'^\d+-', '', (d or '').rstrip(UP))
df = pd.read_csv('F:/workspace/XJToolkit/.tmp/p2bp_work/bp_class.csv', dtype=str, keep_default_na=False)
d3 = df[df.dup_project == 'False'].copy()
def agree_list(lst, row, dev):
    for c in lst:
        p = parse(c)
        if p and p['row'] == row and (not dev or ndev(p['dev']) == ndev(dev)):
            return True
    return False
res = dict(n=0, same_real=0, same_perm=0, other_real=0, other_perm=0)
for pid, g in d3.groupby('project_id'):
    rows = g.to_dict('records')
    for _ in range(20):  # 20 random permutations per project
        for i, r in enumerate(rows):
            cands = [x for x in rows if x['R'] != r['R']]
            if not cands: continue
            j = random.choice(cands)
            row = int(r['row']); dev = r['device'] or None
            e1j = json.loads(j['e1']); e2j = json.loads(j['e2']) + json.loads(j['e3'])
            if _ == 0:
                res['n'] += 1
                res['same_real'] += int(r['cls'] == 'AGREE_SAME_SHEET')
                res['other_real'] += int(r['cls'] == 'AGREE_OTHER_SHEET')
            res['same_perm'] += int(agree_list(e1j, row, dev)) / 20.0 / 1.0 * 1
            res['other_perm'] += int(agree_list(e2j, row, dev)) / 20.0
print({k: round(v, 1) for k, v in res.items()})
n = res['n']
print('chance rate same-sheet %.3f  other-sheet %.3f' % (res['same_perm'] / n, res['other_perm'] / n))
print('real rate same-sheet %.3f  other-sheet %.3f' % (res['same_real'] / n, res['other_real'] / n))

# Restricted control: rows not already agreeing on the same sheet (the population that E2/E3 would decide)
random.seed(11)
pop = d3[d3.cls != 'AGREE_SAME_SHEET']
hit_real = 0; hit_perm = 0; n2 = 0
for pid, g in pop.groupby('project_id'):
    allrows = d3[d3.project_id == pid].to_dict('records')
    for r in g.to_dict('records'):
        n2 += 1
        row = int(r['row']); dev = r['device'] or None
        hit_real += int(agree_list(json.loads(r['e2']) + json.loads(r['e3']), row, dev))
        acc = 0.0
        cands = [x for x in allrows if x['R'] != r['R']]
        for _ in range(20):
            j = random.choice(cands)
            acc += agree_list(json.loads(j['e2']) + json.loads(j['e3']), row, dev)
        hit_perm += acc / 20.0
print('restricted population (not same-sheet agree):', n2)
print('other-sheet real agree %d (%.3f) vs chance %.1f (%.3f)' % (hit_real, hit_real/n2, hit_perm, hit_perm/n2))
