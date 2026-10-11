"""Supporting numbers for README: member handles, port distances, hidden-numeral pair impact (read-only)."""
import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
import pandas as pd

out = {}

# 1) PC0053 member lines -> handles, and free-end distance to every SW port of its page
tl = table("p071", "30000", "lines")
mem = tl[tl.line_id.isin(["L3480", "L3482"])][["line_id", "handle", "start_x", "start_y", "end_x", "end_y", "layer"]]
out["pc0053_members"] = jsonable(mem.to_dict("records"))

def pj(v):
    try:
        return json.loads(v) if isinstance(v, str) else v
    except Exception:
        return v

checks = [("p062", "21000", "/170A7", "S0012", (315.597, 135.609)),
          ("p062", "21000", "/1152C", "S0013", (221.51, 282.1)),
          ("p071", "30000", "/263B0", "S0011", (225.875, 281.702)),
          ("p075", "8000_9000_-", "/3214C", "S0014", (227.508, 260.5)),
          ("p075", "8000_9000_-", "/3205D", "S0015", (227.508, 260.5))]
port_min = {}
for proj, run, inst, sid, pt in checks:
    pi = table(proj, run, "sw_part_instances")
    x = pi[(pi.instance_path == inst) & (pi.sheet_id == sid)]
    best = None
    n = 0
    if not x.empty:
        for p in pj(x.iloc[0].ports) or []:
            for kx, ky in (("start_x", "start_y"), ("end_x", "end_y")):
                if p.get(kx) is None:
                    continue
                n += 1
                d = dist(p[kx], p[ky], *pt)
                if best is None or d < best[0]:
                    best = (round(d, 3), str(p.get("port_number")), round(p[kx], 3), round(p[ky], 3))
    port_min[f"{proj}{inst}{sid}"] = dict(n_port_points=n, nearest=best)
out["sw_port_min_distance_to_free_end"] = port_min

# 2) hidden numerals (DXF height 1e-05) that became accepted terminal candidates: pair-level impact
J = pd.read_csv(OUT / "tools" / "invisible_numeric_joined.csv", encoding="utf-8-sig")
A = J[J.cand_accepted > 0]
rows = []
for _, r in A.iterrows():
    run = {"p062": "21000", "p071": "30000", "p075": "8000_9000_-"}.get(r.project)
    if run is None:
        # locate run dir by project
        import glob
        g = glob.glob(str(ROUND / r.project / "*" / "findings" / "pairs.parquet"))
        run = Path(g[0]).parent.parent.name
    pairs = table(r.project, run, "pairs")
    tc = table(r.project, run, "terminal_candidates")
    lg = table(r.project, run, "line_groups")
    c = tc[(tc.text_id == r.text_id) & (tc.status == "accepted")]
    for _, cc in c.iterrows():
        p = pairs[pairs.line_group_id == cc.line_group_id]
        p = p[(p.left_text_id == r.text_id) | (p.right_text_id == r.text_id)]
        if p.empty:
            rows.append(dict(project=r.project, sheet_id=r.sheet_id, text_id=r.text_id, text=r.text,
                             candidate_id=cc.candidate_id, side=cc.side, line_group_id=cc.line_group_id,
                             pair_id="", status="", pair_single_ended="", rationale="(no pair row keeps this candidate)"))
            continue
        for _, q in p.iterrows():
            single = (pd.isna(q.left_value) != pd.isna(q.right_value))
            L = lg[lg.line_group_id == q.line_group_id]
            layer = L.layer_hints.iloc[0] if not L.empty else ""
            rows.append(dict(project=r.project, sheet_id=r.sheet_id, text_id=r.text_id, text=r.text,
                             candidate_id=cc.candidate_id, side=cc.side, line_group_id=q.line_group_id,
                             pair_id=q.pair_id, status=q.status, pair_kind=q.pair_kind, rationale=q.rationale,
                             left_value=str(q.left_value), right_value=str(q.right_value),
                             pair_single_ended=bool(single), line_layers=str(layer),
                             line_len=round(float(L.length.iloc[0]), 3) if not L.empty else None))
R = pd.DataFrame(rows)
R.to_csv(OUT / "tools" / "hidden_numeral_accepted_pairs.csv", index=False, encoding="utf-8-sig")
out["hidden_accepted_summary"] = dict(
    n_texts=int(A.text_id.nunique()),
    by_project=A.groupby("project").size().to_dict(),
    pair_status=R.status.fillna("(none)").replace("", "(none)").value_counts().to_dict(),
)
json.dump(jsonable(out), open(OUT / "tools" / "_impact.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(jsonable(out), ensure_ascii=False, indent=1)[:5000])
