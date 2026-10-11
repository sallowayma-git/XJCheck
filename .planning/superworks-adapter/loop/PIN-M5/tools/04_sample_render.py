"""PIN-M5 step 4: stratified sample of M5 identifications and two-panel renders (read-only).

Each sample is one schematic pin (left panel: its schematic window with the TERMPOINT marker in red) and the
layout part pin that M5 matched (right panel: the same logical pin on the 元件接线图/背板 page, marker in red,
with the far terminal text of its PCL record in green when visible).

Usage:
  python -X utf8 04_sample_render.py sample <out_spec.json> <seed>
  python -X utf8 04_sample_render.py render <spec.json> <png_dir>
"""
import json, math, pickle, random, re, sys, warnings
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

warnings.filterwarnings("ignore")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_m5_work")
PIN_S_GEOM = Path("F:/workspace/XJToolkit/.tmp/pin_s_work/geom")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
DXF = D["dxf"]
ROWS = pickle.load(open(WORK / "m5_pins.pkl", "rb"))


def pn(s):
    s = re.sub(r"\s+", "", str(s or "")).upper()
    return str(int(s)) if re.fullmatch(r"\d+", s) else s


def key_id(s):
    return re.sub(r"[\s\-_~]", "", str(s or "")).upper()


def part_pin_geom(pid, fid, owner, k):
    for p in T["parts"]:
        if p["pid"] == pid and p["file_id"] == fid and p["insert_handle"] == owner:
            for q in p["ports"]:
                if pn(q.get("port_number")) == k:
                    return (q["start_x"] + q["end_x"]) / 2, (q["start_y"] + q["end_y"]) / 2, p["label"].get("normalized"), (q["start_x"], q["start_y"], q["end_x"], q["end_y"])
    return None


def layout_match(pid, L, T_set, k):
    """Find the PCL record (owner, fid) of label L with pin k and far identity in T_set (sw or text)."""
    for r in T["routes"]:
        if r["source_kind"] != "PCL" or r["pid"] != pid or pn(r["logical_pin"]) != k:
            continue
        far = next((e for e in r["ends"] if e.get("role") == "FAR"), None) or {}
        ids = set()
        if far.get("identity_source") == "sw_port" and far.get("identity"):
            ids.add(key_id(far["identity"]))
        if far.get("far_text_identity") and far.get("category") == "端子":
            ids.add(key_id(far["far_text_identity"]))
        if not (ids & T_set):
            continue
        lab = None
        for p in T["parts"]:
            if p["pid"] == pid and p["file_id"] == r["file_id"] and p["insert_handle"] == r["owner_handle"]:
                lab = norm(p["label"].get("normalized"))
        if lab == L:
            return {"fid": r["file_id"], "owner": r["owner_handle"], "far_text": far.get("far_text_identity"),
                    "far_sw": far.get("identity"), "wire": r["wire_handle"], "record": r["record_id"]}
    return None


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def sample(out_path, seed):
    rnd = random.Random(seed)
    strict_tx = [r for r in ROWS if r["cls"] == "TX" and r.get("pred_strict")]
    strict_ps = [r for r in ROWS if r["cls"] == "PS" and r.get("pred_strict")]
    spec = []
    # Pop-X truth-backed (8): 4 sw-source, 4 text-source
    sw = [r for r in strict_tx if r["match_src"] == "sw"]
    tx = [r for r in strict_tx if r["match_src"] == "text"]
    for i, r in enumerate(rnd.sample(sw, 4) + rnd.sample(tx, 4)):
        spec.append({"name": f"TX{i+1:02d}", "cls": "TX", "row": r})
    # Pop-S (22): by block family
    quotas = [("SYMB2_M_PWF191", 6), ("SYMB2_M_PWF194", 4), ("SYMB2_M_PWF229", 3), ("SYMB2_M_PWF163", 2),
              ("SYMB2_M_PWF192", 2), ("SYMB2_M_PWF196", 1), ("SYMB2_M_PWF4", 1), ("SYMB2_M_PWF210", 1),
              ("SYMB2_M_PWF216", 1), ("SYMB2_M_PWF168", 1)]
    j = 0
    for blk, n in quotas:
        pool = [r for r in strict_ps if r["block"] == blk]
        for r in rnd.sample(pool, min(n, len(pool))):
            j += 1
            spec.append({"name": f"PS{j:02d}", "cls": "PS", "row": r, "block": blk})
    for s in spec:
        r = s["row"]
        s["pid"] = r["pid"]
        s["fid"] = r["fid"]
        s["label"] = r["label"]
        s["T"] = r["T"]
        s["pred"] = r["pred_strict"]
        s["truth"] = r.get("truth")
        s["match_src"] = r["match_src"]
        s["record"] = r["record"]
        s["block"] = r.get("block")
        s["wire"] = r["wire"]
        if s["cls"] == "PS":
            s["port_number"] = r["port_number"]
        del s["row"]
    # layout matches for the chosen pin
    routes = {(r["pid"], r["record_id"]): r for r in T["routes"] if r["source_kind"] == "LOGGEN"}
    for s in spec:
        T_set = set(s["T"])
        lm = layout_match(s["pid"], s["label"], T_set, s["pred"])
        s["layout"] = lm
        if s["cls"] == "TX":
            rt = routes[(s["pid"], s["record"])]
            for e in rt["ends"]:
                if (e.get("category") or "") == "" and e.get("status") in ("resolved_by_symb2_text", "insert_not_sw"):
                    s["sch_insert"] = e.get("terminal_handle")
                    s["sch_pin"] = pn(e.get("port_number"))
                    s["sch_file"] = e.get("file_id")
                    break
    json.dump(spec, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("samples", len(spec), {c: sum(1 for x in spec if x["cls"] == c) for c in ("TX", "PS")})


def tx_geom(pid, fid, insert_handle, pin):
    """Schematic Pop-X pin geometry from the PIN-S geom cache (TERMPOINT marker of the INSERT, number == pin)."""
    import pickle as pk
    fn = PIN_S_GEOM / f"{pid}_{fid}.pkl"
    if not fn.exists():
        return None
    g = pk.load(open(fn, "rb"))
    for sym in g["symbols"]:
        if str(sym.get("insert")) == str(insert_handle):
            for m in sym["markers"]:
                if pn(m.get("number")) == pin:
                    return (m["ax"], m["ay"], m["bx"], m["by"])
    return None


def draw_panel(ax, msp, cx, cy, half, hl, label_text, title, far_text=None, extra=None):
    segs, texts = window(msp, cx, cy, half)
    lc = LineCollection([s[:2] for s in segs], colors="#888888", linewidths=0.6)
    ax.add_collection(lc)
    wires = set((extra or {}).get("wires") or [])
    for a, b, h in segs:
        if h in wires:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#00a040", lw=2.0, zorder=4)
    off = []
    for m in (extra or {}).get("markers", []):
        inside = all(abs(x - cx) <= half and abs(y - cy) <= half for x, y in ((m[0], m[1]), (m[2], m[3])))
        if not inside:
            off.append(m[4])
            continue
        ax.plot([m[0], m[2]], [m[1], m[3]], color="magenta", lw=2.2, zorder=5)
        ax.text(m[0], m[1] + 0.8, m[4], fontsize=7, color="magenta", fontweight="bold", zorder=6)
    if off:
        ax.set_xlabel("terminal off-window: " + ", ".join(off), fontsize=7, color="magenta")
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half, cy + half)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for x, y, val, h in texts:
        col = "#222222"
        if label_text and val.replace(" ", "") == label_text:
            col = "blue"
        if far_text and val.replace(" ", "").upper() == far_text.upper():
            col = "green"
        ax.text(x, y, val, fontsize=max(5, min(9, h * 2.2)), color=col, ha="left", va="bottom",
                fontweight="bold" if col != "#222222" else "normal")
    if hl:
        ax.plot([hl[0], hl[2]], [hl[1], hl[3]], color="red", lw=2.6, solid_capstyle="butt", zorder=5)
    ax.set_title(title, fontsize=7)


def window(msp, cx, cy, half):
    segs, texts = [], []

    def add(e, depth=0):
        t = e.dxftype()
        if t == "INSERT":
            if depth > 3:
                return
            try:
                for v in e.virtual_entities():
                    add(v, depth + 1)
            except Exception:
                pass
            return
        try:
            if t == "LINE":
                s, en = e.dxf.start, e.dxf.end
                if max(s.x, en.x) < cx - half or min(s.x, en.x) > cx + half or max(s.y, en.y) < cy - half or min(s.y, en.y) > cy + half:
                    return
                segs.append(((s.x, s.y), (en.x, en.y), e.dxf.handle))
            elif t == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points()]
                if not pts or not any(abs(x - cx) <= half and abs(y - cy) <= half for x, y in pts):
                    return
                for a, b in zip(pts, pts[1:]):
                    segs.append((a, b, e.dxf.handle))
            elif t in ("TEXT", "MTEXT"):
                x, y = e.dxf.insert.x, e.dxf.insert.y
                if abs(x - cx) <= half and abs(y - cy) <= half:
                    val = e.plain_text() if t == "MTEXT" else e.dxf.text
                    h = e.dxf.char_height if t == "MTEXT" else e.dxf.height
                    texts.append((x, y, str(val), float(h or 2.5)))
        except Exception:
            pass

    for e in msp:
        if e.dxftype() == "INSERT":
            ix, iy = e.dxf.insert.x, e.dxf.insert.y
            if abs(ix - cx) > half + 60 or abs(iy - cy) > half + 60:
                continue
        add(e)
    return segs, texts


def other_terminal_marker(s):
    """Marker (x1,y1,x2,y2,text) of the terminal on the same wire as the schematic pin, from the replay ports table."""
    T_set = set(s["T"])
    for p in T["ports"]:
        if p["pid"] != s["pid"] or p["file_id"] != s["fid"]:
            continue
        if p["category"] not in ("端子", "装置端子") or not p.get("endpoint_identity"):
            continue
        if key_id(p["endpoint_identity"]) not in T_set:
            continue
        wires = {c.get("wire_handle") for c in (p.get("wire_contacts") or [])}
        if s.get("wire") and any(w in wires for w in str(s["wire"]).split(",") if w):
            return (p["start"][0], p["start"][1], p["end"][0], p["end"][1], p["endpoint_identity"])
    return None


def render(spec_path, png_dir):
    spec = json.load(open(spec_path, encoding="utf-8"))
    png_dir = Path(png_dir)
    png_dir.mkdir(parents=True, exist_ok=True)
    cache = {}
    for s in spec:
        try:
            key = (s["pid"], s["fid"])
            if key not in cache:
                cache[key] = ezdxf.readfile(DXF[key]).modelspace()
            msp = cache[key]
            # schematic pin geometry
            sch = None
            if s["cls"] == "PS":
                for p in T["ports"]:
                    if p["record_id"] == s["record"]:
                        sch = (p["start"][0], p["start"][1], p["end"][0], p["end"][1])
                        break
            elif s["cls"] == "TX":
                sch = tx_geom(s["pid"], s["sch_file"], s["sch_insert"], s["sch_pin"])
            if sch is None:
                s["note"] = "no schematic geometry"
                continue
            cx, cy = (sch[0] + sch[2]) / 2, (sch[1] + sch[3]) / 2
            lm = s.get("layout")
            fig, axes = plt.subplots(1, 2, figsize=(11, 5.6), dpi=105)
            sch_extra = {"wires": [w for w in str(s.get("wire", "")).split(",") if w], "markers": []}
            tmk = other_terminal_marker(s)
            if tmk:
                sch_extra["markers"].append(tmk)
            draw_panel(axes[0], msp, cx, cy, 13.0, sch, s["label"], f"{s['name']} schematic {s.get('block','')} label {s['label']}", far_text=None, extra=sch_extra)
            if lm:
                lmsp = cache.get((s["pid"], lm["fid"]))
                if lmsp is None:
                    lmsp = ezdxf.readfile(DXF[(s["pid"], lm["fid"])]).modelspace()
                    cache[(s["pid"], lm["fid"])] = lmsp
                g = part_pin_geom(s["pid"], lm["fid"], lm["owner"], s["pred"])
                if g:
                    lx, ly, _, hl = g
                    draw_panel(axes[1], lmsp, lx, ly, 13.0, hl, s["label"], f"layout pin {s['pred']} far {lm['far_text'] or lm['far_sw']}", far_text=lm["far_text"], extra={"wires": [lm["wire"]], "markers": []})
                else:
                    axes[1].set_title("layout pin geometry not found")
            else:
                axes[1].set_title("no layout match")
            fig.suptitle(f"{s['name']} {s['cls']} label {s['label']} pred {s['pred']} truth {s.get('truth')} T {','.join(s['T'])} src {s['match_src']}", fontsize=8)
            fig.tight_layout(rect=(0, 0, 1, 0.95))
            out = png_dir / f"{s['name']}.png"
            fig.savefig(out)
            plt.close(fig)
            print("saved", out, flush=True)
        except Exception as exc:
            print("ERR", s["name"], repr(exc)[:200], flush=True)
    json.dump(spec, open(spec_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        sample(sys.argv[2], int(sys.argv[3]))
    else:
        render(sys.argv[2], sys.argv[3])
