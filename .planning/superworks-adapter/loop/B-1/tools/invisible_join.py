import sys, glob, re
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
import pandas as pd
d = pd.read_csv(OUT / "tools" / "dxf_text_heights_all.csv", encoding="utf-8-sig", dtype={"handle": str, "text": str})
d["height"] = pd.to_numeric(d.height, errors="coerce")
tiny = d[d.height.notna() & (d.height < 0.01)].copy()
print("TEXT total", len(d), "tiny(<0.01)", len(tiny), "tiny numeric", int(tiny.text.fillna('').str.match(r"^\d+$").sum()))
print("height distribution of tiny:", tiny.height.round(7).value_counts().head(5).to_dict())
print("tiny by layer:", tiny.layer.value_counts().head(8).to_dict())
tiny_num = tiny[tiny.text.fillna('').str.match(r"^\d+$")]
print("tiny numeric by project (top):", tiny_num.project.value_counts().head(15).to_dict(), "projects:", tiny_num.project.nunique())
# join to round12 texts
rows = []
for rd in sorted(glob.glob(str(ROUND / "p*" / "*" / "findings" / "texts.parquet")) + glob.glob(str(ROUND / "p*" / "*" / "*" / "findings" / "texts.parquet"))):
    rd = Path(rd); fd = rd.parent
    proj = fd.relative_to(ROUND).parts[0]
    tx = pd.read_parquet(rd)
    pairs = pd.read_parquet(fd / "pairs.parquet")
    tc = pd.read_parquet(fd / "terminal_candidates.parquet")
    rows.append((proj, tx, pairs, tc))
print("runs", len(rows))
joined = []
for proj, tx, pairs, tc in rows:
    tx = tx.copy(); tx["handle"] = tx.handle.astype(str)
    tt = tiny_num[tiny_num.project == proj]
    if tt.empty: continue
    m = tx.merge(tt[["file_id", "handle", "height", "layer"]], on=["file_id", "handle"], how="inner", suffixes=("", "_dxf"))
    for _, t in m.iterrows():
        c = tc[tc.text_id == t.text_id]
        acc = c[c.status == "accepted"]
        pr_l = pairs[pairs.left_text_id == t.text_id]
        pr_r = pairs[pairs.right_text_id == t.text_id]
        pr = pd.concat([pr_l, pr_r]).drop_duplicates("pair_id")
        joined.append(dict(project=proj, sheet_id=t.sheet_id, file_id=t.file_id, text_id=t.text_id, text=t.text, handle=t.handle,
                           dxf_height=t.height_dxf, is_numeric_candidate=t.is_numeric_candidate,
                           cand_n=len(c), cand_accepted=len(acc), accepted_values=";".join(acc.value.astype(str)),
                           rejection_reasons=";".join(sorted(set(c.rejection_reason.dropna().astype(str)))),
                           pair_ids=";".join(pr.pair_id.astype(str)), pair_status=";".join(pr.status.astype(str))))
J = pd.DataFrame(joined)
J.to_csv(OUT / "tools" / "invisible_numeric_joined.csv", index=False, encoding="utf-8-sig")
print("invisible numeric TEXT in round12 texts:", len(J))
print("  texts that are numeric candidates:", int(J.is_numeric_candidate.sum()))
print("  with >=1 accepted terminal candidate:", int((J.cand_accepted > 0).sum()))
print("  pair status of consuming pairs (any):", J.pair_status.fillna('').str.split(';').explode().replace('', pd.NA).value_counts(dropna=True).to_dict())
print("  by project:", J.groupby('project').size().sort_values(ascending=False).head(20).to_dict())
