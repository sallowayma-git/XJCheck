"""P2-BACKPLATE step 2 (read-only): per backplate virtual-table pass pair (round23), join to SW evidence through
the external terminal designator R and classify. Writes .tmp/p2bp_work/bp_class.csv and bp_class_summary.json.
Row rule: SW backplate identity = <device><column digits><2-digit row>; row = last two digits.
"""
import sys, re, random
sys.path.insert(0, 'F:/workspace/XJToolkit/.tmp/p2bp_work')
from load_common import *

def normr(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().replace('@', '').replace(' ', '').replace('\u3000', '')
    return s or None

ID_RE = re.compile(r'^(?P<dev>.*?)(?P<digits>\d{3,})$')          # numeric: <dev><col digits><2-digit row>
ALPHA_RE = re.compile(r'^(?P<dev>.*?)(?P<letter>[A-Z])(?P<digits>\d{2})$')  # alpha bay: <dev><letter><2-digit row>

def parse_bp(x):
    """Backplate-style SW identity. Device must end with 'n' (backplate device naming in this corpus)."""
    if not x:
        return None
    m = ID_RE.match(x)
    if m and m.group('dev').rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ').endswith('n'):
        d = m.group('digits')
        return dict(dev=m.group('dev').rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ'), col=d[:-2], row=int(d[-2:]), raw=x, form='numeric')
    m = ALPHA_RE.match(x)
    if m and m.group('dev').endswith('n'):
        return dict(dev=m.group('dev'), col=m.group('letter'), row=int(m.group('digits')), raw=x, form='alpha')
    return None

def ndev(d):
    return re.sub(r'^\d+-', '', (d or '').rstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))

rows = []
summary_proj = {}
for pid, fd in project_dirs():
    pg = pd.read_parquet(f'{fd}/pages.parquet')
    pgmap = {r.sheet_id: dict(sheet_no=r.sheet_no, subtype=r.page_subtype, filename=r.filename) for r in pg.itertuples()}
    pr = pd.read_parquet(f'{fd}/pairs.parquet')
    st = pd.read_parquet(f'{fd}/sw_strip_rows.parquet', columns=['sheet_id', 'endpoint_identity', 'connections'])
    sw_pairs = []
    bp = []
    for r in pr.itertuples():
        ev = jl(r.evidence) or {}
        is_sw = str(r.pair_id).startswith('PSW') or ev.get('source') == 'superworks' or 'superworks' in ev
        if is_sw and r.status == 'pass':
            sw_pairs.append((r.sheet_id, normr(r.left_value), normr(r.right_value)))
        tm = ev.get('table_mapping') or {}
        if tm.get('mapping_mode') == 'backplate_virtual_table' and r.status == 'pass':
            bp.append((r, tm))
    sw_by_val = {}
    for sh, a, b in sw_pairs:
        for me, other in ((a, b), (b, a)):
            if me:
                sw_by_val.setdefault(me, []).append((sh, other))
    strip_by_val = {}
    for r in st.itertuples():
        ei = normr(r.endpoint_identity)
        conns = [normr(c.get('value')) for c in (jl(r.connections) or []) if c and c.get('value')]
        if ei:
            strip_by_val.setdefault(ei, []).append((r.sheet_id, [c for c in conns if c]))
    # project-wide list of backplate identities for permutation control
    for r, tm in bp:
        L = normr(r.left_value); R = normr(r.right_value)
        row = tm.get('row_number'); dev = tm.get('composite_device_instance')
        sheet = r.sheet_id; pinfo = pgmap.get(sheet, {})
        dup_project = any({a, b} == {L, R} for _, a, b in sw_pairs)
        e1 = [o for sh, o in sw_by_val.get(R, []) if sh == sheet and o]
        e2 = [o for sh, o in sw_by_val.get(R, []) if sh != sheet and o]
        e3 = [c for sh, conns in strip_by_val.get(R, []) for c in conns]
        internal = parse_bp(R) is not None and parse_bp(R)['row'] is not None and len(parse_bp(R)['dev']) > 0
        def tag(cands):
            out = []
            for c in cands:
                p = parse_bp(c)
                if p is None:
                    out.append(('nonbp', c, None, None))
                else:
                    out.append(('bp', c, p['row'] == row, (ndev(p['dev']) == ndev(dev)) if dev else None))
            return out
        t1, t2, t3 = tag(e1), tag(e2), tag(e3)
        def agree(tags, need_dev=True):
            return any(k == 'bp' and rowok and (devok or devok is None or not need_dev) for k, c, rowok, devok in tags)
        def conflict(tags):
            return any(k == 'bp' and not rowok and (devok is None or devok) for k, c, rowok, devok in tags)
        def tagv(lst):
            out = []
            for c in lst:
                p = parse_bp(c)
                if p is None:
                    out.append(('nonbp', c, None, None))
                else:
                    out.append(('bp', c, p['row'] == row, (ndev(p['dev']) == ndev(dev)) if dev else None))
            return out
        def ok(tags):
            return any(k == 'bp' and rw and (dv is None or dv) for k, c, rw, dv in tags)
        def rowdevdiff(tags):
            return any(k == 'bp' and rw and dv is False for k, c, rw, dv in tags)
        def conflict(tags):
            return any(k == 'bp' and rw is False and (dv is None or dv) for k, c, rw, dv in tags)
        T1, T2, T3 = tagv(e1), tagv(e2), tagv(e3)
        if ok(T1):
            cls = 'AGREE_SAME_SHEET'
        elif ok(T2 + T3):
            cls = 'AGREE_OTHER_SHEET'
        elif conflict(T1 + T2 + T3):
            cls = 'CONFLICT_SAME_SHEET' if conflict(T1) else 'CONFLICT_OTHER_SHEET'
        elif rowdevdiff(T1 + T2 + T3):
            cls = 'ROW_AGREE_DEV_DIFF'
        elif e1 or e2 or e3:
            cls = 'PARTNER_NONBP_ONLY'
        else:
            cls = 'NO_SW_PARTNER'
        if internal and cls != 'NO_SW_PARTNER':
            cls = 'INTERNAL_' + cls
        rows.append(dict(project_id=pid, pair_id=r.pair_id, sheet_id=sheet, sheet_no=pinfo.get('sheet_no'),
                         subtype=pinfo.get('subtype'), filename=pinfo.get('filename'), L=L, R=R, row=row,
                         device=dev, header_prefix=tm.get('header_prefix'), composite=bool(dev),
                         left_text_id=r.left_text_id, right_text_id=r.right_text_id,
                         dup_project=dup_project, e1=json.dumps(e1, ensure_ascii=False), e2=json.dumps(e2, ensure_ascii=False),
                         e3=json.dumps(e3, ensure_ascii=False), cls=cls, n_e1=len(e1), n_e2=len(e2), n_e3=len(e3),
                         internal=internal))
df = pd.DataFrame(rows)
df.to_csv('F:/workspace/XJToolkit/.tmp/p2bp_work/bp_class.csv', index=False, encoding='utf-8-sig')
d3 = df[~df.dup_project]
print('all bp pass pairs', len(df), '| non-dup (D3-like)', len(d3))
print(d3.cls.value_counts().to_string())
print(pd.crosstab(d3.subtype, d3.cls).to_string())
print(d3.groupby('cls').project_id.nunique().to_string())
print(pd.crosstab(d3.subtype, d3.cls).T.to_string())
