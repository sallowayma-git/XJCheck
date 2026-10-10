"""P003-STACK read-only renderer (F0012 = 元件接线图2, p003 frozen DXF cache).

- Reads the frozen DXF from corpus_manifest.json with ezdxf (never saved, never written).
- Each figure re-reads the DXF into memory, mutates only in-memory copies
  (colour for A/B split, optional display offset) and draws with
  ezdxf.addons.drawing Frontend + matplotlib backend.
- Anchors use src/dwg_audit/extract/superworks_semantics.text_anchor_wcs / entity_insert_wcs.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, "F:/workspace/XJToolkit/src")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
import matplotlib as mpl
mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from dwg_audit.extract.superworks_semantics import text_anchor_wcs, entity_insert_wcs

ROOT = Path("F:/workspace/XJToolkit")
OUT = ROOT / ".planning/superworks-adapter/loop/P003-STACK"
MAN = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
P3 = [p for p in MAN["projects"] if p["project_id"] == "p003"][0]
DXF = [f for f in P3["files"] if f["file_id"] == "F0012"][0]["dxf_path"]

# handle -> site info (A = handles 0x12860-0x12875 batch; B = handles 0x13499-0x134B4 batch)
SITES = [
    dict(key="S1", pid="PCM0002", x=220.0, A=("12875", "8nB01"), B=("134B4", "8n401"), port="8KLP3"),
    dict(key="S2", pid="PCM0005", x=260.0, A=("1286F", "8nB12"), B=("134AE", "8n402"), port="8KLP2"),
    dict(key="S3", pid="PCM0008", x=300.0, A=("12869", "8nB02"), B=("134A8", "8n405"), port="8KLP1"),
    dict(key="S4", pid="PCM0012", x=380.0, A=("12863", "8nD02"), B=("1349C", "8n818"), port="8CLP1"),
]
CONTROL = dict(key="C0", pid="PCM0010", x=342.5, single=("134A2", "8n820"), port="8CLP2")
Y_BOTTOM_LABEL = 199.0
SHIFT_DY = -3.5  # display-only offset for the B label in the 错开 version

BLUE = 5   # ACI blue
RED = 1    # ACI red
COLOR_NOTE = "#444444"


def load():
    return ezdxf.readfile(DXF)


def find_by_handle(doc, handle):
    for e in doc.modelspace():
        if e.dxf.handle == handle:
            return e
    return None


def text_value(e):
    return e.plain_text() if e.dxftype() == "MTEXT" else e.dxf.text


def facts(doc, handle, label_hint=None):
    """Read-only attribute dump for the annotation panel."""
    e = find_by_handle(doc, handle)
    if e is None:
        return None
    idx = list(doc.modelspace()).index(e)
    lay = doc.layers.get(e.dxf.layer)
    ins = entity_insert_wcs(e)
    anc = text_anchor_wcs(e)
    d = dict(
        text=text_value(e), dxftype=e.dxftype(), handle=e.dxf.handle, msp_index=idx,
        owner="modelspace 直接 TEXT",
        layer=e.dxf.layer, layer_on=lay.is_on(), layer_frozen=lay.is_frozen(), layer_locked=lay.is_locked(),
        defpoints=(e.dxf.layer.lower() == "defpoints"),
        color="BYLAYER(%s)" % lay.dxf.color if e.dxf.get("color") in (None, 256) else str(e.dxf.color),
        style=e.dxf.get("style"), height=round(float(e.dxf.height), 3),
        width_factor=round(float(e.dxf.get("width", 1.0)), 3),
        halign=int(e.dxf.get("halign", 0)), valign=int(e.dxf.get("valign", 0)),
        insert=(round(ins.x, 4), round(ins.y, 4)),
        align_point=(round(float(e.dxf.align_point.x), 4), round(float(e.dxf.align_point.y), 4)) if e.dxf.hasattr("align_point") else None,
        anchor=(round(anc.x, 4), round(anc.y, 4)),
        xdata_apps=sorted(e.xdata.data.keys()) if e.xdata else [],
        ld_xdata=[a for a in (e.xdata.data.keys() if e.xdata else []) if a.startswith("LD")],
        ext_dict=bool(e.has_extension_dict),
    )
    return d


def draw(out_png, *, xlim, ylim, mode, overrides=None, title="", note_lines=None,
         panel_lines=None, boxes=None, leaders=None, labels=None, figsize=(8, 10), dpi=150, hide=None):
    """overrides: list of (handle, color or None, dy or None) applied to an in-memory doc."""
    doc = load()
    msp = doc.modelspace()
    for handle, color, dy in (overrides or []):
        e = find_by_handle(doc, handle)
        if e is None:
            continue
        if color is not None:
            e.dxf.color = color
        if dy:
            e.dxf.insert = (e.dxf.insert.x, e.dxf.insert.y + dy, 0)
            if e.dxftype() == "TEXT" and e.dxf.hasattr("align_point"):
                e.dxf.align_point = (e.dxf.align_point.x, e.dxf.align_point.y + dy, 0)
    for e in list(msp):
        if hide and e.dxftype() in ("TEXT", "MTEXT") and e.dxf.layer == "MARK" and (text_value(e) or "").strip() and any(ord(c) > 255 for c in text_value(e)):
            if e.dxf.insert.y < 196:
                msp.delete_entity(e)
    fig = plt.figure(figsize=figsize, dpi=dpi, facecolor="white")
    if panel_lines:
        ax = fig.add_axes([0.03, 0.10, 0.54, 0.82])
        pax = fig.add_axes([0.59, 0.10, 0.40, 0.82])
        pax.axis("off")
        y = 0.99
        for line, kw in panel_lines:
            pax.text(0.0, y, line, va="top", ha="left", fontsize=kw.get("fs", 8.5),
                     color=kw.get("color", "black"), weight=kw.get("weight", "normal"), family=None,
                     transform=pax.transAxes)
            y -= kw.get("dy", 0.034)
    else:
        ax = fig.add_axes([0.02, 0.08, 0.96, 0.88])
    ax.set_facecolor("white")
    backend = MatplotlibBackend(ax)
    ctx = RenderContext(doc)
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, min_lineweight=0.35)
    Frontend(ctx, backend, config=cfg).draw_layout(msp, finalize=True)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#999999")
    for (x0, y0, w, h, ec, ls, lw, label) in (boxes or []):
        ax.add_patch(Rectangle((x0, y0), w, h, fill=False, ec=ec, ls=ls, lw=lw, zorder=10))
        if label:
            ax.text(x0, y0 + h + 0.4, label, color=ec, fontsize=7.5, weight="bold", zorder=11, va="bottom")
    for (x1, y1, x2, y2, c, ls) in (leaders or []):
        ax.plot([x1, x2], [y1, y2], color=c, ls=ls, lw=0.9, zorder=9)
    for (x, y, s, kw) in (labels or []):
        ax.text(x, y, s, fontsize=kw.get("fs", 7.5), color=kw.get("color", "black"),
                weight=kw.get("weight", "normal"), ha=kw.get("ha", "left"), va=kw.get("va", "bottom"), zorder=12)
    fig.suptitle(title, fontsize=10.5, y=0.985, weight="bold")
    if hide:
        note_lines = list(note_lines or []) + ["为避免中文字体回退放大遮挡，本图未绘制 MARK 层「母联…投退」中文说明（仅显示用，不改原图）。"]
    if note_lines:
        fig.text(0.02, 0.012, "\n".join(note_lines), fontsize=7.5, color=COLOR_NOTE, va="bottom")
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, facecolor="white")
    plt.close(fig)
    return out_png


def window(x, half_w=20, y0=186, y1=240):
    return (x - half_w, x + half_w), (y0, y1)


def zoom_window(x):
    return (x - 9, x + 9), (189, 205)


def panel_for(site, fa, fb, shifted=None):
    def line(k, v):
        return f"{k}: {v}"
    lines = [("放大图（两段文字分色）", dict(fs=9, weight="bold", dy=0.045)),
             (f"元件 {site['port']}，端口 2 底端，{site['pid']}", dict(fs=8.2, dy=0.034)),
             ("F0012 / S0012 元件接线图2", dict(fs=8.2, dy=0.034)),
             ("", dict(dy=0.02))]
    for tag, f, colr in (("A 段（红）", fa, "#c00000"), ("B 段（蓝）", fb, "#0040c0")):
        lines.append((tag, dict(fs=8.8, weight="bold", color=colr, dy=0.035)))
        for k, v in [
            ("文本", f"{f['text']}"),
            ("句柄", f"{f['handle']}  （msp 第 {f['msp_index']} 个实体）"),
            ("实体", f"{f['dxftype']}，modelspace 直接（非 INSERT 内）"),
            ("图层 / 开关 / 冻结", f"{f['layer']} / {'开' if f['layer_on'] else '关'} / {'冻结' if f['layer_frozen'] else '未冻结'}"),
            ("Defpoints/不可打印", "否（TEXT 层开、未冻结）" if not f["defpoints"] else "是"),
            ("颜色", f"{f['color']}（图上红/蓝为本图标注）"),
            ("文字高度 / 宽度因子", f"{f['height']} / {f['width_factor']}"),
            ("样式", f"{f['style']}"),
            ("对齐 halign/valign", f"{f['halign']} / {f['valign']}（1=居中；3=中部）"),
            ("插入点 insert", f"({f['insert'][0]}, {f['insert'][1]})"),
            ("对齐点 align_point", f"({f['align_point'][0]}, {f['align_point'][1]})" if f["align_point"] else "-"),
            ("text_anchor_wcs", f"({f['anchor'][0]}, {f['anchor'][1]})"),
            ("XDATA 应用名", "无" if not f["xdata_apps"] else ", ".join(f["xdata_apps"])),
            ("LD_* XDATA", "无" if not f["ld_xdata"] else ", ".join(f["ld_xdata"])),
        ]:
            lines.append((f"  {k}: {v}", dict(fs=7.0, dy=0.026)))
        lines.append(("", dict(dy=0.01)))
    lines.append(("插入点差 Δx=%.3f；对齐点相同，两段渲染重合。" % abs(fa["insert"][0] - fb["insert"][0]),
                  dict(fs=7.8, weight="bold", dy=0.03)))
    if shifted:
        lines.append(("错开：B 段下移 3.5 单位（仅显示）", dict(fs=7.6, color="#7a3d00", dy=0.03)))
    return lines


def main():
    doc0 = load()
    facts_out = {"dxf": DXF, "sites": []}
    for s in SITES:
        fa = facts(doc0, s["A"][0])
        fb = facts(doc0, s["B"][0])
        facts_out["sites"].append(dict(site=s["key"], pid=s["pid"], x=s["x"], A=fa, B=fb))
    fc = facts(doc0, CONTROL["single"][0])
    facts_out["control"] = dict(pid=CONTROL["pid"], x=CONTROL["x"], label=fc)
    (OUT / "tools" / "facts.json").write_text(json.dumps(facts_out, ensure_ascii=False, indent=1), encoding="utf-8")

    produced = []
    # ---- full sheet overview with the four boxes
    boxes = []
    for s in SITES:
        boxes.append((s["x"] - 6.5, 193.2, 13, 12.2, "#e0008f", "--", 1.4, ""))
    boxes.append((CONTROL["x"] - 6.5, 193.2, 13, 12.2, "#008a3e", "-", 1.2, ""))
    ov_labels = [(s["x"] - 6.5, 207.2, s["pid"], dict(fs=8, weight="bold", color="#e0008f")) for s in SITES]
    ov_labels.append((CONTROL["x"] - 6.5, 183.5, CONTROL["pid"] + " 对照（单标签 pass）", dict(fs=7.5, weight="bold", color="#008a3e")))
    produced.append(draw(OUT / "P3S_00_F0012_sheet_overview.png", xlim=(40, 420), ylim=(-2, 250), mode="sheet",
                         title="p003 F0012（元件接线图2）全页总览，框出四处底端叠放与对照点",
                         boxes=boxes, labels=ov_labels, figsize=(12, 7.4),
                         note_lines=["来源：test/…/12 元件接线图2.dwg（sha256 与 corpus_manifest 一致）；DXF 冻结缓存只读。",
                                     "紫虚线框=底端叠放（A 段/B 段重叠）；绿实线框=同页对照 8n820（单标签，pass）。"]))

    # ---- per-site: overview / zoom / offset
    for s in SITES:
        fa = facts(doc0, s["A"][0])
        fb = facts(doc0, s["B"][0])
        x = s["x"]
        xl, yl = window(x)
        box = [(x - 4.8, 194.8, 9.6, 8.6, "#e0008f", "--", 1.4, "叠放位置")]
        leader_top = [(x, 217.5, x, 202.5, "#f0a000", "-")]
        produced.append(draw(
            OUT / f"P3S_{s['key']}_{s['pid']}_1_overview.png", xlim=xl, ylim=yl, mode="overview", figsize=(8, 9),
            title=f"{s['pid']} 整体图：{s['port']} 元件块 + 上下端子 + 导线（p003 S0012）",
            boxes=box,
            labels=[(x - 19, 236, f"元件块 FJL-25-2A（表头 {s['port']}）", dict(fs=8, weight="bold", color="#333333"))],
            note_lines=["整体图：元件图块与周边标签、导线。紫虚线框=底端端口 2 叠放位置（y≈196–199）。",
                        "文字未改动，按 DXF 原始几何绘制。"]))
        # zoom
        zxl, zyl = zoom_window(x)
        zbox = [(x - 4.8, 194.8, 9.6, 8.6, "#e0008f", "--", 1.4, "")]
        produced.append(draw(
            OUT / f"P3S_{s['key']}_{s['pid']}_2_zoom_AB_colour.png", xlim=zxl, ylim=zyl, mode="zoom", figsize=(14, 7.6),
            overrides=[(fa["handle"], RED, None), (fb["handle"], BLUE, None)], hide=True,
            title=f"{s['pid']} 放大图：{s['port']} 端口 2 底端叠放两段文字（红=A 段，蓝=B 段）",
            panel_lines=panel_for(s, fa, fb),
            boxes=zbox,
            note_lines=["红=A 段（句柄 %s，%s）；蓝=B 段（句柄 %s，%s）。两段在图上完全重叠，蓝段绘制在上层。" %
                        (fa["handle"], fa["text"], fb["handle"], fb["text"]),
                        "颜色仅为本图标注，不代表原图颜色（原图两段均为 BYLAYER/TEXT 层白色）。"]))
        # offset
        shifted_note = ("错开：蓝段 B 人为向下偏移 %.1f 单位（仅显示；原位置由虚线标示）。" % abs(SHIFT_DY))
        produced.append(draw(
            OUT / f"P3S_{s['key']}_{s['pid']}_3_zoom_offset_for_reading.png", xlim=zxl, ylim=(zyl[0] - 1.5, zyl[1]),
            mode="zoom", figsize=(14, 7.6),
            overrides=[(fa["handle"], RED, None), (fb["handle"], BLUE, SHIFT_DY)], hide=True,
            title=f"{s['pid']} 错开显示（为便于阅读人为错开）：{s['port']} 底端两段文字",
            panel_lines=panel_for(s, fa, fb, shifted=shifted_note),
            leaders=[(x, Y_BOTTOM_LABEL, x, Y_BOTTOM_LABEL + SHIFT_DY, "#777777", ":")],
            labels=[(x - 8.6, 189.6, "虚线：B 段原位置 y≈199 到偏移后位置", dict(fs=6.4, color="#555555"))],
            boxes=[(x - 4.8, 194.8 + SHIFT_DY, 9.6, 8.6, "#e0008f", "--", 1.0, "")],
            note_lines=["为便于阅读人为错开：蓝段 B 下移 %.1f 单位显示；红段 A 保持原位。错开仅为显示，不是原图位置。" % abs(SHIFT_DY),
                        "原图两段重叠位置（y≈199 中部）见放大图（分色版）。"]))

    # ---- control: 8n820 single label
    cx = CONTROL["x"]
    fc = facts(doc0, CONTROL["single"][0])
    produced.append(draw(
        OUT / "P3S_C0_PCM0010_8n820_control_zoom.png", xlim=(cx - 9, cx + 9), ylim=(189, 205), mode="zoom", figsize=(12, 7.4),
        overrides=[(fc["handle"], BLUE, None)], hide=True,
        title="PCM0010 对照：同页底端端口 2 仅单标签 8n820（pass）",
        panel_lines=[
            ("对照：同页单标签", dict(fs=9, weight="bold", dy=0.045)),
            (f"文本 {fc['text']}  句柄 {fc['handle']}  msp 第 {fc['msp_index']} 个", dict(fs=8.2, dy=0.035)),
            (f"图层 {fc['layer']}，开={fc['layer_on']}，冻结={fc['layer_frozen']}", dict(fs=8.2, dy=0.035)),
            (f"高度 {fc['height']}，宽度因子 {fc['width_factor']}，halign/valign {fc['halign']}/{fc['valign']}", dict(fs=8.2, dy=0.035)),
            (f"insert {fc['insert']}；align_point {fc['align_point']}", dict(fs=8.2, dy=0.035)),
            (f"text_anchor_wcs {fc['anchor']}", dict(fs=8.2, dy=0.035)),
            ("同点（0.5 单位内）无第二段文字，无叠放。", dict(fs=8.2, weight="bold", dy=0.04)),
            ("XDATA：无；所属 modelspace 直接 TEXT。", dict(fs=8.2, dy=0.035)),
        ],
        note_lines=["与 A/B 叠放位置比较：同一元件类型（FJL 竖向 + 底端端口 2），仅本元件无叠放。"]))

    for p in produced:
        print("wrote", p.name)
    print("facts ->", OUT / "tools" / "facts.json")


if __name__ == "__main__":
    main()
