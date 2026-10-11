"""Stream-scan every manifest DXF for TEXT entities with near-zero height (read-only)."""
import sys, json, re, time
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
import pandas as pd

NUM = re.compile(r"^\d+$")
def scan_file(path):
    res = []
    try:
        lines = open(path, encoding="utf-8", errors="ignore").read().split("\n")
    except Exception as e:
        return None, str(e)
    n = len(lines)
    i = 0
    cur = None
    rec = None
    # DXF is code/value line pairs
    pairs = []
    for k in range(0, n - 1, 2):
        pairs.append((lines[k].strip(), lines[k + 1].strip()))
    rec = None
    for code, val in pairs:
        if code == "0":
            if rec is not None and rec.get("type") == "TEXT":
                res.append(rec)
            rec = {"type": val}
            continue
        if rec is None:
            continue
        if code == "5": rec["handle"] = val
        elif code == "8": rec["layer"] = val
        elif code == "40": rec.setdefault("height", float(val) if val.replace('.', '', 1).replace('-', '', 1).replace('e', '', 1).replace('E', '', 1).replace('+', '', 1).isdigit() or True else None)
        elif code == "1": rec["text"] = val
        elif code == "10": rec["x"] = val
        elif code == "20": rec["y"] = val
    if rec is not None and rec.get("type") == "TEXT":
        res.append(rec)
    return res, None

t0 = time.time()
rows = []
bad = []
for p in MANIFEST["projects"]:
    for f in p["files"]:
        recs, err = scan_file(f["dxf_path"])
        if recs is None:
            bad.append((p["project_id"], f["file_id"], err)); continue
        for r in recs:
            h = r.get("height")
            rows.append(dict(project=p["project_id"], file_id=f["file_id"], handle=r.get("handle"), layer=r.get("layer"),
                             text=r.get("text"), height=h, x=r.get("x"), y=r.get("y")))
df = pd.DataFrame(rows)
df.to_csv(OUT / "tools" / "dxf_text_heights_all.csv", index=False, encoding="utf-8-sig")
print("files scanned", sum(len(p['files']) for p in MANIFEST['projects']), "TEXT rows", len(df), "bad", len(bad), "secs", round(time.time()-t0,1))
