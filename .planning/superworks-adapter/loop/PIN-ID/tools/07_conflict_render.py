"""PIN-ID step 2b: render a few R1 candidates that collide with an existing pass pair (read-only).

Reads r1_conflicts.json (written by 06_consistency_conflicts.py) and renders the first sample of each pair kind,
so the existing pass pair and the Pop-X candidate can be judged on the drawing.
Usage: python 07_conflict_render.py <all.pkl> <pop_x.pkl> <conflicts.json> <out_png_dir> <scratch_dir>
"""
import importlib.util
import json
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sr", str(HERE / "05_sample_render.py"))
sr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sr)


def main(all_pkl, popx_pkl, conflicts_json, png_dir, scratch):
    D = pickle.load(open(all_pkl, "rb"))
    T, FAM = D["tables"], D["family"]
    px = pickle.load(open(popx_pkl, "rb"))
    conflicts = json.load(open(conflicts_json, encoding="utf-8"))
    dmap = sr.dxf_map()
    r4 = sr.load_r4()
    cache = r4.DxfCache()
    png_dir = Path(png_dir)
    png_dir.mkdir(parents=True, exist_ok=True)
    picks = {}
    for c in conflicts:
        picks.setdefault(c["pair_kind"], c)
    recs = []
    for kind, c in picks.items():
        cand = next(x for x in px if x["pid"] == c["pid"] and x["file"] == c["file"] and x["k_rec"] == c["cand"]
                    and c["term_port"] in x["other_port_ids"])
        dxf = dmap[(cand["pid"], cand["file"])]
        doc, _i, _c = cache.get(dxf)
        geo = sr.pop_x_geometry(doc, dict(insert=cand["insert"], pin=cand["pin"], wire=cand["wire"],
                                          other_insert=cand.get("other_insert")))
        if not geo or not geo.get("seg"):
            recs.append(dict(kind=kind, status="no_marker"))
            continue
        seg = geo["seg"]
        mid = ((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2)
        pts = [mid, seg[0], seg[1]] + ([geo["term"]] if geo.get("term") else []) + (geo.get("wire") or [])
        ctx = sr.window_around(pts, pad=16, min_size=44)
        head = [f"[冲突 {kind}] {cand['pid']} {cand['file']} {FAM.get(cand['pid'])} | 候选 {cand['k_rec']} | 端子 {c['term_identity']}",
                f"现有通过配对 {c['pair']} ({c['pair_kind']}) 另一侧值 {c['pair_other']} | 端子侧值 {c['term_value']}",
                f"标签 {cand['scan_label']} | 脚号(TERMPOINT) {cand['pin']} | 槽位 {cand['slot_text']} | 序号 {cand['seq']} | 导线 {cand['wire']}",
                "红=候选脚号标记，蓝=标签，洋红=端子，橙=导线端点"]
        marks = [(mid[0], mid[1], "red")]
        if geo.get("label"):
            marks.append((geo["label"][0], geo["label"][1], "blue"))
        if geo.get("term"):
            marks.append((geo["term"][0], geo["term"][1], "magenta"))
        for p in geo.get("wire") or []:
            marks.append((p[0], p[1], "orange"))
        panel = r4.Panel(["上下文窗口"], dxf_path=dxf, window=ctx, boxes=[], points=marks)
        fname = f"conflict_{kind}_{cand['pid']}_{cand['file']}.png"
        r4._render_issue_png(png_dir / fname, head, [panel], cache)
        recs.append(dict(kind=kind, png=f"png/{fname}", pid=cand["pid"], file=cand["file"], candidate=cand["k_rec"],
                         term_identity=c["term_identity"], pair=c["pair"], pair_kind=kind, pair_other=c["pair_other"],
                         term_value=c["term_value"], pair_status=c["pair_status"]))
        print(kind, fname, flush=True)
    Path(scratch).mkdir(parents=True, exist_ok=True)
    (Path(scratch) / "conflict_renders.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:6])
