import sys, json, re
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
pd.set_option("display.width", 320); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_columns", 30)
PATTERNS = {"p062": ["52n", "58n", "XSQ_22E2HM"], "p071": ["1n", "25n", "51n", "WYD-811", "WXH-822A-P", "WHH-811A"], "p075": ["1-26n", "2-26n", "26n", "TS3000"]}
for proj, run in [("p062", "21000"), ("p071", "30000"), ("p075", "8000_9000_-")]:
    tx = table(proj, run, "texts")
    pg = table(proj, run, "pages")[["sheet_id", "file_id", "filename", "sheet_no", "sheet_title", "sheet_category", "page_type"]]
    print("########", proj)
    for pat in PATTERNS[proj]:
        m = tx[tx.normalized_text.astype(str).str.fullmatch(pat, case=False) | tx.text.astype(str).str.strip().eq(pat)]
        if m.empty: continue
        m = m.merge(pg, on=["sheet_id", "file_id"], how="left")
        m["ax"] = m.insert_x.round(2); m["ay"] = m.insert_y.round(2)
        print(f"-- text '{pat}': {len(m)} occurrences")
        print(m[["sheet_no", "sheet_title", "sheet_category", "text_id", "handle", "layer", "entity_type", "ax", "ay", "is_numeric_candidate"]].to_string(index=False))
