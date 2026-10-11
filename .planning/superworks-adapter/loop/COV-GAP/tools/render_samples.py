"""Render DXF close-ups for the stratified samples of the Top-8 uncovered buckets (read-only).

Reuses the drawing helpers of round4/I/round4_samples_v2.py (ezdxf frontend, COLOR_SWAP_BW, panel layout).
Marks: red = own endpoint / potential text / layer-d text; blue = far end / cross-page target port;
orange = wire-group endpoints.
"""
import importlib.util, json, math, sys
from pathlib import Path
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
OUT = ROOT / ".planning/superworks-adapter/loop/COV-GAP"
SCR = Path(sys.argv[1])
RUN = ROOT / ".tmp/superworks_round12_full"
SPEC = importlib.util.spec_from_file_location("r4", str(ROOT / ".planning/superworks-adapter/round4/I/round4_samples_v2.py"))
r4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r4)

R = json.loads((SCR / "aggregate.json").read_text(encoding="utf-8"))
SAMPLES = R["samples"]
union = pd.read_pickle(SCR / "union.pkl")
pots = pd.read_pickle(SCR / "pots_fam.pkl")
groups = pd.read_pickle(SCR / "groups.pkl")
run = json.loads((RUN / "run.json").read_text(encoding="utf-8"))
PDIR = {p["project_id"]: Path(p["project_dir"]) for p in run["projects"]}
cache = r4.DxfCache()
PROJ = {}


def project(pid):
    if pid not in PROJ:
        PROJ[pid] = r4.Project(pid, PDIR[pid])
    return PROJ[pid]


def fnum(v):
    try:
        x = float(v)
        return None if x != x else x
    except Exception:
        return None


def far_end(sample):
    """Return far endpoint of the sample's wire group (opposite to the contact)."""
    g = groups[(groups.project == sample["project"]) & (groups.group == sample.get("group"))]
    if g.empty:
        return None, None, None
    g = g.iloc[0]
    cx, cy = fnum(sample["x"]), fnum(sample["y"])
    ds = math.hypot(cx - g.sx, cy - g.sy)
    de = math.hypot(cx - g.ex, cy - g.ey)
    fx, fy = (g.ex, g.ey) if ds < de else (g.sx, g.sy)
    return (g.sx, g.sy, g.ex, g.ey), fx, fy


def target_panel(s):
    """Panel on the cross-page target sheet (its own DXF) for an a2 sample; None if no target."""
    pot = pots[(pots.project == s["project"]) & (pots.sheet == s["sheet"]) & (pots.text_id == s["obj"].split("|")[1])]
    if pot.empty or not isinstance(pot.iloc[0].t_sheet, str) or not pot.iloc[0].t_sheet:
        return None
    r = pot.iloc[0]
    P = project(s["project"])
    fid = P.pages.get(r.t_sheet, {}).get("file_id")
    dxf = P.dxf_for(fid, r.t_sheet)
    tx, ty = fnum(r.t_cx), fnum(r.t_cy)
    if tx is None or ty is None or dxf is None:
        return None
    page = P.pages.get(r.t_sheet, {})
    win = (tx - 18, ty - 12, tx + 18, ty + 12)
    title = [f"[目标页] {page.get('sheet_no')} {page.get('filename')} | {page.get('page_type')} | {r.t_sheet}",
             f"目标端口 {r.t_rid} 类别={r.t_cat} 身份={r.t_ident} 已消费={r.t_consumed}",
             f"窗口 x[{win[0]:.1f},{win[2]:.1f}] y[{win[1]:.1f},{win[3]:.1f}]"]
    return r4.Panel(title, dxf_path=dxf, window=win, points=[(tx, ty, "blue")])


def build_panel(bucket, s):
    layer = s["layer"]
    pid, sheet = s["project"], s["sheet"]
    P = project(pid)
    file_id = P.pages.get(sheet, {}).get("file_id")
    dxf = P.dxf_for(file_id, sheet)
    marks, boxes, extra = [], [], []
    if layer.startswith("a2"):
        tx, ty = fnum(s["x"]), fnum(s["y"])
        pot = pots[(pots.project == pid) & (pots.sheet == sheet) & (pots.text_id == s["obj"].split("|")[1])]
        t_cx = t_cy = None
        if not pot.empty:
            r = pot.iloc[0]
            t_cx, t_cy = fnum(r.t_cx), fnum(r.t_cy)
            extra.append(f"去向文字 {r.value} @({tx:.2f},{ty:.2f}) 判定={r.reason}")
            extra.append(f"目标端口 {r.t_rid} 类别={r.t_cat} 目标页={r.t_sheet} 目标端口已消费={r.t_consumed}")
        marks.append((tx, ty, "red"))
        if t_cx is not None:
            marks.append((t_cx, t_cy, "blue"))
        pts = [(x, y) for x, y, _ in marks]
    elif layer.startswith("d_"):
        tx, ty = fnum(s["x"]), fnum(s["y"])
        marks.append((tx, ty, "red"))
        extra.append(f"数字文字 {s['ident']} 判定桶={bucket}")
        pts = [(tx, ty)]
    else:
        cx, cy = fnum(s["x"]), fnum(s["y"])
        marks.append((cx, cy, "red"))
        seg, fx, fy = far_end(s)
        if fx is not None:
            marks.append((fx, fy, "blue"))
            boxes.append((min(seg[0], seg[2]), min(seg[1], seg[3]), max(seg[0], seg[2]), max(seg[1], seg[3]), "orange"))
            pts = [(cx, cy), (fx, fy)]
        else:
            pts = [(cx, cy)]
        extra.append(f"本端身份={s['ident']} 导线组={s.get('group')} 端侧={s.get('side')} 对端类={s.get('oend')}")
    xs = [p[0] for p in pts if p[0] is not None]
    ys = [p[1] for p in pts if p[1] is not None]
    pad = 9.0
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    if x1 - x0 < 36:
        c = (x0 + x1) / 2; x0, x1 = c - 18, c + 18
    if y1 - y0 < 24:
        c = (y0 + y1) / 2; y0, y1 = c - 12, c + 12
    page = P.pages.get(sheet, {})
    title = [f"{bucket}", f"{pid} {P.dir.name[:24]} | {page.get('sheet_no')} {page.get('filename')} | {page.get('page_type')} | {sheet}",
             f"对象 {s['obj']}  窗口 x[{x0:.1f},{x1:.1f}] y[{y0:.1f},{y1:.1f}]"] + extra
    return r4.Panel(title, dxf_path=dxf, window=(x0, y0, x1, y1), boxes=boxes, points=marks)


def main():
    index = []
    OUT_PNG = OUT / "png"
    OUT_PNG.mkdir(parents=True, exist_ok=True)
    for n, (bucket, picks) in enumerate(SAMPLES.items(), start=1):
        panels = []
        for k, s in enumerate(picks, start=1):
            panel = build_panel(bucket, s)
            if s["layer"].startswith("a2"):
                panel.title_lines = [t for t in panel.title_lines]
                if panel.points and len(panel.points) > 0:
                    panel.points = [pt for pt in panel.points if pt[2] == "red"]
                tp = target_panel(s)
                cell_panels = [panel] + ([tp] if tp is not None else [])
            else:
                cell_panels = [panel]
            panels.append(cell_panels)
            out = OUT_PNG / f"B{n}_{k}.png"
            header = [f"B{n}-{k} {bucket}",
                      f"项目 {s['project']} 页 {s['sheet']} 对象 {s['obj']}",
                      "红=本端/文字  蓝=对端/目标端口  橙=导线组端点连线框"]
            r4._render_issue_png(out, header, cell_panels, cache)
            index.append({"bucket": bucket, "n": n, "k": k, "png": out.name, "sample": {kk: (str(vv) if not isinstance(vv, (int, float)) else vv) for kk, vv in s.items()},
                          "entities_drawn": panel.meta.get("entities_drawn")})
            print("ok", out.name, bucket[:24], panel.meta.get("entities_drawn"), flush=True)
        out = OUT_PNG / f"bucket_B{n}.png"
        header = [f"B{n} {bucket}", "每桶 3 例：红=本端/文字 蓝=对端/目标端口 橙=导线组端点框"]
        flat = [pn for cell in panels for pn in cell]
        r4._render_issue_png(out, header, flat, cache)
    (OUT / "png" / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
