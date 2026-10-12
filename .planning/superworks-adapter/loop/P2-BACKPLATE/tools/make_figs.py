import sys, json, re
import pandas as pd
sys.path.insert(0, 'F:/workspace/XJToolkit/.tmp/p2bp_work')
from load_common import *
from render_cases import run, plt
OUT = 'F:/workspace/XJToolkit/.planning/superworks-adapter/loop/P2-BACKPLATE/png'
os.makedirs(OUT, exist_ok=True)
manifest = json.load(open('F:/workspace/XJToolkit/.planning/superworks-adapter/corpus_manifest.json', encoding='utf-8'))
manifest = manifest['projects'] if isinstance(manifest, dict) else manifest
DXF = {(p['project_id'], f['file_id']): f['dxf_path'] for p in manifest for f in p['files']}
FAM = json.load(open('F:/workspace/XJToolkit/.tmp/p2bp_work/fam.json', encoding='utf-8'))
cls = pd.read_csv('F:/workspace/XJToolkit/.tmp/p2bp_work/bp_class.csv', dtype=str, keep_default_na=False)

def fl(x):
    try:
        return float(x)
    except Exception:
        return None

def base_spec(pid, pair_id):
    fd = dict(project_dirs())[pid]
    pr = pd.read_parquet(f'{fd}/pairs.parquet')
    pair = pr[pr.pair_id == pair_id].iloc[0]
    ev = jl(pair.evidence); tm = ev['table_mapping']
    sh = pair.sheet_id
    pg = pd.read_parquet(f'{fd}/pages.parquet')
    p = pg[pg.sheet_id == sh].iloc[0]
    fid = pair.file_id
    texts = pd.read_parquet(f'{fd}/findings/texts.parquet', columns=['text_id','sheet_id','insert_x','insert_y','source_block_name','normalized_text']) if False else None
    marks = {}
    hc = tm.get('header_coord'); mc = tm.get('middle_coord'); rc = [fl(pair.right_coord_x), fl(pair.right_coord_y)]
    marks['hdr'] = (hc, '#d62fbf', 'hdr ' + str(tm.get('header_prefix')))
    marks['row'] = (mc, '#1f4fd1', 'row ' + str(tm.get('row_number')) + ' (V1 L=' + str(pair.left_value) + ')')
    marks['R'] = (rc if None not in rc else None, '#c81e1e', 'R ' + str(pair.right_value))
    return fd, pair, tm, sh, fid, p, marks

def sw_port_xy(fd, sheet, value):
    pt = pd.read_parquet(f'{fd}/sw_ports.parquet', columns=['sheet_id','endpoint_identity','start_x','start_y','end_x','end_y'])
    x = pt[(pt.sheet_id == sheet) & (pt.endpoint_identity == value)]
    if len(x) == 0:
        return None
    r = x.iloc[0]
    return [(fl(r.start_x) + fl(r.end_x)) / 2, (fl(r.start_y) + fl(r.end_y)) / 2]

def judge_spec(pid, pair_id, label):
    fd, pair, tm, sh, fid, p, marks = base_spec(pid, pair_id)
    dxf = DXF[(pid, fid)]
    row = cls[(cls.project_id == pid) & (cls.pair_id == pair_id)].iloc[0]
    e1 = json.loads(row.e1)
    partner = next((c for c in e1), None)
    if partner:
        xy = sw_port_xy(fd, sh, partner)
        marks['sw'] = (xy, '#1a9b3a', 'SW partner ' + partner)
    pts = [v[0] for v in marks.values() if v and v[0]] + []
    pts = [v[0] for k, v in marks.items() if v and v[0]]
    spec = dict(dxf=dxf, pts=pts, marks=marks,
                title=f"{label}\n{pid} {p.filename[:18]} sheet {p.sheet_no} {pair_id}\nL={pair.left_value} R={pair.right_value} row {tm.get('row_number')}\nSW e1={row.e1[:60]} e2={row.e2[:50]} e3={row.e3[:40]}")
    return spec

def struct_spec(pid, sheet_id, pair_id, label):
    fd, pair, tm, sh, fid, p, marks = base_spec(pid, pair_id)
    tx = pd.read_parquet(f'{fd}/findings/texts.parquet', columns=['sheet_id','insert_x','insert_y','source_block_name'])
    t = tx[(tx.sheet_id == sh) & tx.source_block_name.notna()]
    xs = t.insert_x.map(fl).dropna(); ys = t.insert_y.map(fl).dropna()
    pts = [[xs.min(), ys.min()], [xs.max(), ys.max()]] if len(xs) else [hc for hc in [tm.get('header_coord')] if hc]
    marks = {}
    spec = dict(dxf=DXF[(pid, fid)], pts=pts, marks={}, title=f"{label}\n{pid} {p.filename[:24]} s{p.sheet_no} [{p.page_subtype}]\nfamily {FAM[pid][0]}")
    return spec

if __name__ == '__main__':
    which = sys.argv[1]
    if which == 'struct':
        specs = [
            struct_spec('p001', 'S0011', 'P0001', 'A GJ-73 backplate table'),
            struct_spec('p022', 'S0015', 'P0000', 'B GJ-76 geometric table'),
            struct_spec('p040', 'S0016', 'P0000', 'C GJ-80 table'),
            struct_spec('p063', 'S0013', 'P0061', 'D N2604 table'),
        ]
        run(specs, f'{OUT}/P2BP_structure_1.png', 'Backplate virtual-table pages, four families (window = virtual table texts)')
    elif which == 'judge':
        def pid_of(pid, R, cl):
            x = cls[(cls.project_id == pid) & (cls.R == R) & (cls.cls == cl) & (cls.dup_project == 'False')]
            return x.pair_id.iloc[0]
        groups = [
            ('judge_1', [('p007', pid_of('p007','1I18D1','AGREE_SAME_SHEET'), 'J1 same-sheet agree'),
                         ('p065', pid_of('p065','1KLP8-2','AGREE_SAME_SHEET'), 'J2 same-sheet agree'),
                         ('p001', pid_of('p001','7UD1','AGREE_OTHER_SHEET'), 'J3 other-sheet agree'),
                         ('p057', pid_of('p057','7U1D68','ROW_AGREE_DEV_DIFF'), 'J4 dev-diff 1-1n vs 7n')]),
            ('judge_2', [('p072', pid_of('p072','4XD8','ROW_AGREE_DEV_DIFF'), 'J5 dev-diff 1-1n vs 4n'),
                         ('p023', pid_of('p023','1-7QD9','CONFLICT_SAME_SHEET'), 'J6 row 02 vs 32'),
                         ('p063', pid_of('p063','1-25I1D5','CONFLICT_SAME_SHEET'), 'J7 row 1 vs C02'),
                         ('p058', pid_of('p058','1PT-u3','CONFLICT_SAME_SHEET'), 'J8 row 18 vs 17')]),
            ('judge_3', [('p039', pid_of('p039','3-2KLP6-1','PARTNER_NONBP_ONLY'), 'J9 non-backplate partner'),
                         ('p001', pid_of('p001','1KLP11-2','NO_SW_PARTNER'), 'J10 no SW partner')]),
        ]
        for name, items in groups:
            specs = []
            for pid, pair_id, label in items:
                try:
                    specs.append(judge_spec(pid, pair_id, label))
                except Exception as e:
                    print('skip', pid, pair_id, e)
            if specs:
                run(specs, f'{OUT}/P2BP_{name}.png', 'SW partner check: blue = V1 row number, red = external R, green = SW port of R on same sheet')
