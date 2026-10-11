"""Visual check for the 'page not routed' bucket: 3 numeric out_of_scope texts on 元件接线图 (read-only)."""
import importlib.util, json, random, sys
from pathlib import Path
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
OUT = ROOT / ".planning/superworks-adapter/loop/COV-GAP"
RUN = ROOT / ".tmp/superworks_round12_full"
SPEC = importlib.util.spec_from_file_location("r4", str(ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"))
r4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r4)
run = json.loads((RUN / "run.json").read_text(encoding="utf-8"))
cache = r4.DxfCache()
rng = random.Random(20261012)
pool = []
for p in run["projects"]:
    d = Path(p["project_dir"]) / "findings"
    ta = pd.read_parquet(d / "text_assignments.parquet",
                         columns=["sheet_id", "page_type", "resolution_status", "is_numeric_like", "text", "insert_x", "insert_y", "text_id"])
    sub = ta[(ta.page_type == "元件接线图") & (ta.resolution_status == "out_of_scope") & ta.is_numeric_like.astype(bool)]
    for r in sub.itertuples():
        pool.append((p["project_id"], p["project_dir"], r))
projs = sorted({x[0] for x in pool})
rng.shuffle(projs)
picks = []
for pj in projs[:3]:
    cands = [x for x in pool if x[0] == pj]
    picks.append(cands[rng.randrange(len(cands))])
panels, info = [], []
for k, (pid, pdir, r) in enumerate(picks, start=1):
    P = r4.Project(pid, Path(pdir))
    fid = P.pages.get(r.sheet_id, {}).get("file_id")
    dxf = P.dxf_for(fid, r.sheet_id)
    x, y = float(r.insert_x), float(r.insert_y)
    win = (x - 14, y - 10, x + 14, y + 10)
    page = P.pages.get(r.sheet_id, {})
    title = [f"OOS{k} 文字 '{r.text}' {r.text_id} | {page.get('sheet_no')} {page.get('filename')} | 页型 {r.page_type} | {r.sheet_id}",
             f"判定 out_of_scope  窗口 x[{win[0]:.1f},{win[2]:.1f}] y[{win[1]:.1f},{win[3]:.1f}]"]
    pan = r4.Panel(title, dxf_path=dxf, window=win, points=[(x, y, "red")])
    panels.append(pan)
    info.append(dict(project=pid, sheet=r.sheet_id, text=r.text, text_id=r.text_id, x=x, y=y))
out = OUT / "png" / "out_of_scope_yuanjian.png"
r4._render_issue_png(out, ["页面类型未路由：元件接线图上 out_of_scope 的数字文字（3 例，随机）", "红=文字插入点"], panels, cache)
(OUT / "png" / "out_of_scope_yuanjian.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(info, ensure_ascii=False))
