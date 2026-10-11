"""Render one two-panel PNG per R-PAIR-MISSING-SIDE item (read-only; DXF from manifest cache)."""
import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.config import Configuration, ColorPolicy, BackgroundPolicy
import ezdxf

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

FACTS = json.loads((OUT / "tools" / "_facts.json").read_text(encoding="utf-8"))
LAYER_COLOR = {"MARK": "#7b2cbf", "DIM": "#1d4ed8", "0": "#6b7280"}
CFG = Configuration.defaults().with_changes(color_policy=ColorPolicy.BLACK, background_policy=BackgroundPolicy.WHITE)


def draw_base(ax, doc, xlim, ylim):
    ctx = RenderContext(doc)
    be = MatplotlibBackend(ax)
    fe = Frontend(ctx, be, config=CFG)
    fe.draw_layout(doc.modelspace(), finalize=True)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.set_facecolor("white")
    ax.set_xticks([])
    ax.set_yticks([])


def overlay(ax, F, xlim, ylim, detail_level):
    sx, sy = F["line_group"]["start"]
    ex, ey = F["line_group"]["end"]
    ix, iy = F["identified_point"]
    mx, my = F["missing_point"]
    # line group (orange)
    ax.plot([sx, ex], [sy, ey], color="#ff8c00", lw=3.2 if detail_level == "wide" else 4.2, alpha=0.85, zorder=10,
            solid_capstyle="butt")
    ax.plot([sx, ex], [sy, ey], color="#ff8c00", lw=0, marker="none")
    # texts in window
    for t in F["nearby_texts"]:
        ix0, iy0 = t["engine_insert"]
        if not (xlim[0] - 2 <= ix0 <= xlim[1] + 2 and ylim[0] - 2 <= iy0 <= ylim[1] + 2):
            continue
        col = LAYER_COLOR.get(t["layer"], "#374151")
        hidden = (t["dxf_height"] is not None and t["dxf_height"] < 0.01)
        fs = 6.6 if detail_level == "wide" else 7.6
        tag = f'{t["text_id"]}/{t["handle"]} {t["layer"]} "{t["text"]}"' + (" 隐形" if hidden else "")
        if t["dxf_anchor"] is not None:
            ax_, ay_ = t["dxf_anchor"]
            ax.plot([ax_], [ay_], marker="o", ms=2.8 if detail_level == "wide" else 4, color=col, zorder=12)
        else:
            ax_, ay_ = ix0, iy0
        bx = ax_ + (0.9 if detail_level == "wide" else 0.4)
        by = ay_ + (1.6 if detail_level == "wide" else 0.8)
        ax.text(bx, by, tag, fontsize=fs, color=col, zorder=14,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=col, lw=0.6, alpha=0.9))
    # device INSERTs (gray dashed frames)
    for ins in F["inserts_near_stub"]:
        x0, y0, x1, y1 = ins["bbox"]
        if x1 < xlim[0] or x0 > xlim[1] or y1 < ylim[0] or y0 > ylim[1]:
            continue
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#9ca3af", ls="--", lw=0.9, zorder=8))
        ax.text(x0 + 0.5, y1 + 0.4 if detail_level == "wide" else y1 + 0.2,
                f'器件块 {ins["block"]} (INSERT {ins["handle"]})', fontsize=7 if detail_level == "wide" else 8,
                color="#4b5563", zorder=14)
    # identified side (green) and missing side (red)
    ax.scatter([ix], [iy], s=70 if detail_level == "wide" else 120, c="#16a34a", zorder=16, edgecolors="black", linewidths=0.6)
    ax.scatter([mx], [my], s=90 if detail_level == "wide" else 150, c="#dc2626", marker="X", zorder=16, edgecolors="black", linewidths=0.6)
    ax.annotate("已识别一侧 (绿)", (ix, iy), xytext=(ix - 0.6, iy + 6.0 if detail_level == "wide" else iy + 2.8),
                fontsize=7 if detail_level == "wide" else 9, color="#166534", zorder=18,
                arrowprops=dict(arrowstyle="-", color="#166534", lw=0.6))
    ax.annotate("缺失一侧端点 (红): 1 单位内无实体", (mx, my), xytext=(mx + 1.2, my - 6.5 if detail_level == "wide" else my - 3.2),
                fontsize=7 if detail_level == "wide" else 9, color="#991b1b", zorder=18,
                arrowprops=dict(arrowstyle="-", color="#991b1b", lw=0.6))
    ax.annotate("线组 (橙)", ((sx + ex) / 2, (sy + ey) / 2), xytext=((sx + ex) / 2 - 2.0, (sy + ey) / 2 - 5.0 if detail_level == "wide" else (sy + ey) / 2 - 2.6),
                fontsize=7 if detail_level == "wide" else 9, color="#c2410c", zorder=18,
                arrowprops=dict(arrowstyle="-", color="#c2410c", lw=0.6))


def xdata_note(F):
    parts = []
    for h, d in F["line_group"]["stub_xdata"].items():
        parts.append(f"线段 {h}: " + ",".join(sorted(d.keys())))
    num = F["numeral"]
    parts.append(f'数字文字 {num["handle"]} "{num["text"]}": ' + ",".join(f"{k}={v[-1] if v else ''}" for k, v in num["xdata_apps"].items()))
    for ins in F["inserts_near_stub"]:
        keys = ins["xdata_apps"]
        pick = ["LDPARTLAYT_LINE_HANDLE", "LDPARTLAYT_PARTNO_HANDLE", "LDPARTLAYT_PARTLABEL_HANDLE", "LDPARTLAYT_PARTTYPE_HANDLE"]
        if any(k in keys for k in pick):
            parts.append(f'器件 {ins["block"]} ({ins["handle"]}) SW 版式记录: ' + ", ".join(f'{k.replace("LDPARTLAYT_", "")}={keys[k][-1]}' for k in pick if k in keys))
    if F["sw_part_with_numeral"]:
        s = F["sw_part_with_numeral"][0]
        parts.append(f'SW 实例 {s["instance_path"]} label={s["label"]["value"]} part_no={s["part_no"]["value"]} type={s["part_type"]}')
    else:
        parts.append("SW 实例: 无 part_no 记录指向该数字文字")
    return "\n".join(parts)


def render(name, F):
    proj, fid, sid = F["project"], F["file_id"], F["sheet_id"]
    doc = ezdxf.readfile(dxf_path(proj, fid))
    sx, sy = F["line_group"]["start"]
    ex, ey = F["line_group"]["end"]
    cx, cy = (sx + ex) / 2, (sy + ey) / 2
    wide = ((cx - 60, cx + 60), (cy - 40, cy + 40))
    zoom = ((cx - 16, cx + 16), (cy - 10, cy + 10))
    fig = plt.figure(figsize=(18, 11), dpi=100)
    ax1 = fig.add_axes([0.03, 0.30, 0.55, 0.55])
    ax2 = fig.add_axes([0.63, 0.30, 0.35, 0.55])
    draw_base(ax1, doc, *wide)
    overlay(ax1, F, *wide, "wide")
    ax1.set_title("宽视图（±60 × ±40 单位）：线组两端、器件块、周边全部文字", fontsize=10)
    draw_base(ax2, doc, *zoom)
    overlay(ax2, F, *zoom, "zoom")
    ax2.set_title("近景（±16 × ±10 单位）", fontsize=10)
    pr = F["pair"]
    head1 = f'{proj} | {F["sheet_no"]} {F["filename"]} | 页 {sid}（{F["sheet_category"]}）| 文件 {fid}'
    head2 = f'{F["pair_id"]} | 状态 {pr["status"]} | rationale: {pr["rationale"]}'
    fig.text(0.03, 0.955, head1, fontsize=12, weight="bold")
    fig.text(0.03, 0.925, head2, fontsize=10)
    fig.text(0.03, 0.895, "图例：橙=线组  绿=已识别一侧  红X=缺失一侧端点  紫/蓝/灰框=周边文字(按图层)  灰虚线框=器件块  *隐形*=DXF 文字高度 1e-05（屏幕不可见）",
             fontsize=8.5, color="#111827")
    foot1 = (f'pair {F["pair_id"]}：左值 {pr["left_value"]}（{pr["left_text_id"]}），右值 None；线组 {F["line_group"]["line_group_id"]} '
             f'start({sx:.2f},{sy:.2f}) end({ex:.2f},{ey:.2f})；数字文字 DXF height={F["numeral"]["raw_dxf_height"]}，'
             f'引擎钳制后 height={F["numeral"]["engine_clamped_height"]}')
    fig.text(0.03, 0.205, foot1, fontsize=9)
    import textwrap
    xnote = []
    for raw_line in xdata_note(F).split("\n"):
        xnote.extend(textwrap.wrap(raw_line, 190) or [""])
    fig.text(0.03, 0.175, "XDATA / SW 证据：", fontsize=9, weight="bold")
    for i, line in enumerate(xnote[:9]):
        fig.text(0.03, 0.150 - i * 0.021, line, fontsize=7.8, color="#1f2937")
    out = OUT / f"B1_{name}.png"
    fig.savefig(out, dpi=105)
    plt.close(fig)
    return out


if __name__ == "__main__":
    names = list(FACTS.keys())
    for n in names:
        p = render(n, FACTS[n])
        print("wrote", p.name, flush=True)
