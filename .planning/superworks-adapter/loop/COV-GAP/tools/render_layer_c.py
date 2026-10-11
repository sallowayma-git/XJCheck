"""Layer c visual check: render 3 schematic wire groups with no resolved endpoint (read-only)."""
import importlib.util, json, random, sys
from pathlib import Path
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
OUT = ROOT / ".planning/superworks-adapter/loop/COV-GAP"
SCR = Path(sys.argv[1])
RUN = ROOT / ".tmp/superworks_round12_full"
SPEC = importlib.util.spec_from_file_location("r4", str(ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"))
r4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r4)

g = pd.read_pickle(SCR / "schematic_groups.pkl")
run = json.loads((RUN / "run.json").read_text(encoding="utf-8"))
PDIR = {p["project_id"]: Path(p["project_dir"]) for p in run["projects"]}
cache = r4.DxfCache()
rng = random.Random(20261011)
none = g[g.n_resolved == 0]
picks = []
projs = list(none.project.unique())
rng.shuffle(projs)
for pj in projs[:3]:
    sub = none[none.project == pj]
    picks.append(sub.iloc[rng.randrange(len(sub))])
panels, info = [], []
for k, row in enumerate(picks, start=1):
    P = r4.Project(row.project, PDIR[row.project])
    fid = P.pages.get(row.sheet, {}).get("file_id")
    dxf = P.dxf_for(fid, row.sheet)
    xs = [row.sx, row.ex]; ys = [row.sy, row.ey]
    x0, x1 = min(xs) - 12, max(xs) + 12
    y0, y1 = min(ys) - 10, max(ys) + 10
    if x1 - x0 < 40:
        c = (x0 + x1) / 2; x0, x1 = c - 20, c + 20
    if y1 - y0 < 26:
        c = (y0 + y1) / 2; y0, y1 = c - 13, c + 13
    page = P.pages.get(row.sheet, {})
    title = [f"C{k} {row.group} | {row.origin} | {page.get('sheet_no')} {page.get('filename')} | {row.sheet}",
             f"端点状态 起={row.reason_start} | 止={row.reason_end}",
             f"窗口 x[{x0:.1f},{x1:.1f}] y[{y0:.1f},{y1:.1f}]"]
    pan = r4.Panel(title, dxf_path=dxf, window=(x0, y0, x1, y1),
                   boxes=[(min(xs) - 0.6, min(ys) - 0.6, max(xs) + 0.6, max(ys) + 0.6, "orange")],
                   points=[(row.sx, row.sy, "red"), (row.ex, row.ey, "red")])
    panels.append(pan)
    info.append(dict(group=row.group, project=row.project, sheet=row.sheet, reason_start=row.reason_start, reason_end=row.reason_end,
                     entities=pan.meta.get("entities_drawn")))
out = OUT / "png" / "layer_c_none_groups.png"
r4._render_issue_png(out, ["层 c 目视核对：两端都未解析的二次原理图导线组（3 例，随机）",
                           "橙框=导线组线段  红点=两端点"], panels, cache)
(OUT / "png" / "layer_c_none_groups.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(info, ensure_ascii=False))
