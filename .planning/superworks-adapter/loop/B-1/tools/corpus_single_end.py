import sys, json, glob, re
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
BARE_N = re.compile(r"^(?:\d+-)?\d+n$", re.I)
rows = []
runs = sorted({str(Path(p).parent.parent) for p in glob.glob(str(ROUND / "**" / "findings" / "pairs.parquet"), recursive=True)})
def pj(v):
    try: return json.loads(v) if isinstance(v, str) else v
    except Exception: return v
for rd in runs:
    rd = Path(rd)
    if "cache" in rd.parts: continue
    proj = rd.relative_to(ROUND).parts[0]
    run = str(rd.relative_to(ROUND / proj))
    fd = rd / "findings"
    try:
        pairs = pd.read_parquet(fd / "pairs.parquet")
        lg = pd.read_parquet(fd / "line_groups.parquet")
        tx = pd.read_parquet(fd / "texts.parquet")
        pi = pd.read_parquet(fd / "sw_part_instances.parquet") if (fd / "sw_part_instances.parquet").exists() else pd.DataFrame()
        pg = pd.read_parquet(fd / "pages.parquet")
    except Exception as e:
        print("skip", rd, e); continue
    swpn = set()
    for _, x in pi.iterrows():
        d = pj(x.part_no)
        if isinstance(d, dict) and d.get("text_id"): swpn.add(d["text_id"])
    lgi = lg.set_index("line_group_id")
    ptype = pg.set_index("sheet_id")["page_type"].to_dict() if "page_type" in pg else {}
    pcat = pg.set_index("sheet_id")["sheet_category"].to_dict() if "sheet_category" in pg else {}
    for _, p in pairs.iterrows():
        single = (pd.isna(p.left_value) or p.left_value is None) != (pd.isna(p.right_value) or p.right_value is None)
        if not single: continue
        present_side = "left" if not (pd.isna(p.left_value) or p.left_value is None) else "right"
        missing = "right" if present_side == "left" else "left"
        g = lgi.loc[p.line_group_id] if p.line_group_id in lgi.index else None
        if g is None: continue
        mx, my = (g.end_x, g.end_y) if missing == "right" else (g.start_x, g.start_y)
        px, py = (g.start_x, g.start_y) if missing == "right" else (g.end_x, g.end_y)
        sheet = p.sheet_id
        t_sheet = tx[tx.sheet_id == sheet]
        cand = t_sheet[(t_sheet.insert_x - mx).abs().le(16) & (t_sheet.insert_y - my).abs().le(16)]
        bare = cand[cand.text.astype(str).str.strip().str.match(BARE_N)]
        pres_text_id = p.left_text_id if present_side == "left" else p.right_text_id
        ptxt = None
        if pres_text_id is not None and not (isinstance(pres_text_id, float)):
            m = tx[tx.text_id == pres_text_id]
            if len(m): ptxt = m.iloc[0]
        rows.append(dict(
            project=proj, run=run, pair_id=p.pair_id, sheet_id=sheet, file_id=p.file_id,
            status=p.status, rationale=p.rationale, pair_kind=p.pair_kind,
            present_value=str(p.left_value if present_side == "left" else p.right_value),
            present_text_id=pres_text_id, present_layer=(None if ptxt is None else ptxt.layer),
            present_is_sw_part_no=bool(pres_text_id in swpn),
            line_layers=str(g.layer_hints), line_len=round(float(g.length), 2),
            line_orientation=g.orientation,
            missing_side=missing,
            bare_n_within16=int(len(bare)), bare_n_texts=";".join(bare.text.astype(str).tolist()[:4]),
            bare_n_layers=";".join(sorted(set(bare.layer.astype(str)))),
            sheet_category=pcat.get(sheet), page_type=ptype.get(sheet),
        ))
df = pd.DataFrame(rows)
df.to_pickle(str(OUT / "tools" / "_single_end_all.pkl")) if False else None
out = OUT / "tools" / "single_end_corpus.csv"
df.to_csv(out, index=False, encoding="utf-8-sig")
print("single-ended pairs total", len(df))
print(df.status.value_counts().to_dict())
bn = df[df.bare_n_within16 > 0]
print("with bare-n text within 16 of missing end:", len(bn), bn.status.value_counts().to_dict())
print("  of which present side SW part_no:", int(bn.present_is_sw_part_no.sum()), bn[bn.present_is_sw_part_no].status.value_counts().to_dict())
print("  of which MARK line:", int((bn.line_layers.str.contains('MARK')).sum()), bn[bn.line_layers.str.contains('MARK')].status.value_counts().to_dict())
print("  by project:", bn.groupby("project").size().to_dict())
print("single-ended by project:", df.groupby("project").size().to_dict())
