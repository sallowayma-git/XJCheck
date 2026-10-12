"""P2-BACKPLATE judgement sample (read-only).

Input : candidate table (csv of the production sw_backplate_contradictions rows; the 10-project replay is checked
        against it first), the round replay root that holds the pairs (coordinates), the frozen corpus manifest.
Sample: stratified by contradiction type and project. same_sheet_row_conflict: 14 cases spread over projects;
        device_prefix_differs: 30 cases spread over projects (seeded, reproducible).
Output: cases.json with the coordinates needed for rendering. No judgement is written here.
Usage : python sample_candidates.py <candidates.csv> <replay_root> <corpus_manifest.json> <out_cases.json>
"""
import sys, json, random, glob, os, math
import pandas as pd

cand_csv, replay, manifest_path, out_path = sys.argv[1:5]
rng = random.Random(20260612)
cands = pd.read_csv(cand_csv, dtype=str, keep_default_na=False)
print("candidates", len(cands), cands.contradiction_type.value_counts().to_dict(), flush=True)
manifest = json.load(open(manifest_path, encoding="utf-8"))
manifest = manifest["projects"] if isinstance(manifest, dict) else manifest
dxf_of = {(p["project_id"], f["file_id"]): f["dxf_path"] for p in manifest for f in p["files"]}


def pick_stratified(frame, n):
    groups = {p: g.to_dict("records") for p, g in frame.groupby("project")}
    for g in groups.values():
        rng.shuffle(g)
    order = sorted(groups)
    rng.shuffle(order)
    out, i = [], 0
    while len(out) < n and any(groups.values()):
        p = order[i % len(order)]
        if groups[p]:
            out.append(groups[p].pop())
        i += 1
    return out


same = cands[cands.contradiction_type == "same_sheet_row_conflict"]
dev = cands[cands.contradiction_type == "device_prefix_differs"]
if len(sys.argv) > 5 and sys.argv[5] == "census_same_sheet":
    # complete census of same_sheet_row_conflict: every candidate row, in candidate-table order
    sel = [("same_sheet_row_conflict", r) for r in same.to_dict("records")]
else:
    sel = [("same_sheet_row_conflict", r) for r in pick_stratified(same, 14)]
    sel += [("device_prefix_differs", r) for r in pick_stratified(dev, 30)]
print("selected", len(sel), pd.Series([s[1]["project"] for s in sel]).value_counts().to_dict(), flush=True)

pair_tables = {}
def pairs_of(project):
    if project not in pair_tables:
        pdir = glob.glob(os.path.join(replay, project, "*", "findings"))[0]
        pair_tables[project] = pd.read_parquet(os.path.join(pdir, "pairs.parquet"))
    return pair_tables[project]

def nn(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x

cases = []
for n, (ctype, r) in enumerate(sel, 1):
    pairs = pairs_of(r["project"])
    v1 = pairs[pairs.pair_id == r["pair_id"]].iloc[0]
    sw = pairs[pairs.pair_id == r["sw_pair_id"]].iloc[0]
    tm = json.loads(v1.evidence)["table_mapping"]
    if nn(sw.left_value) == r["sw_identity"]:
        sw_id_xy, sw_R_xy = [sw.left_coord_x, sw.left_coord_y], [sw.right_coord_x, sw.right_coord_y]
    else:
        sw_id_xy, sw_R_xy = [sw.right_coord_x, sw.right_coord_y], [sw.left_coord_x, sw.left_coord_y]
    cases.append(dict(
        case_no=n + (100 if len(sys.argv) > 5 and sys.argv[5] == "census_same_sheet" else 0), cls=ctype, project=r["project"], pair_id=r["pair_id"], sw_pair_id=r["sw_pair_id"],
        file_id=v1.file_id, sheet_id=v1.sheet_id, sheet_no=r["sheet_no"], filename=r["filename"],
        dxf=dxf_of.get((r["project"], v1.file_id)),
        v1_left=v1.left_value, R=v1.right_value, v1_row=int(r["v1_row"]), v1_device=r["v1_device"],
        header_prefix=nn(tm.get("header_prefix")), header_coord=tm.get("header_coord"),
        row_xy=[float(v1.left_coord_x), float(v1.left_coord_y)], R_xy=[float(v1.right_coord_x), float(v1.right_coord_y)],
        sw_identity=r["sw_identity"], sw_row=int(r["sw_row"]), sw_device=r["sw_device"],
        sw_left=sw.left_value, sw_right=sw.right_value, sw_id_xy=[float(v) for v in sw_id_xy],
        sw_R_xy=[float(v) for v in sw_R_xy], sw_partner_count=int(r["sw_partner_count"]),
        sw_same_sheet=r["sw_same_sheet"]))
missing = [c["case_no"] for c in cases if not c["dxf"] or any(v is None or (isinstance(v, float) and math.isnan(v))
           for v in c["row_xy"] + c["R_xy"] + c["sw_id_xy"])]
print("missing dxf/coords:", missing, flush=True)
json.dump(cases, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("wrote", out_path, len(cases), flush=True)
