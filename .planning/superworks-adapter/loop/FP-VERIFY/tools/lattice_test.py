"""Read-only structural test for the 425 restored terminal-strip V1 passes (cur findings + pickles).
Per pair: same-row?, native through-wire inside terminal box?, line-group member provenance, SW pass coverage of each label."""
import json, sys, os, collections
import pandas as pd
W = "F:/workspace/XJToolkit/.tmp/fp_verify_work/"
CUR = "F:/workspace/XJToolkit/.tmp/engine_coordination_full_acceptance/current/"
gain = pd.read_pickle(W + "gain_matched.pkl")
cur = pd.read_pickle(W + "cur_pairs.pkl")
g = gain[gain.pair_kind == "component_mapping"].copy()
rows = []
for (pid, sid), grp in g.groupby(["project_id", "sheet_id"]):
    base = f"{CUR}{pid}/project/findings/"
    lines = pd.read_parquet(base + "lines.parquet"); lines = lines[lines.sheet_id == sid]
    lg = pd.read_parquet(base + "line_groups.parquet"); lg = lg[lg.sheet_id == sid].set_index("line_group_id")
    cs = cur[(cur.project_id == pid) & (cur.sheet_id == sid)]
    passes = cs[cs.status == "pass"]
    for p in grp.itertuples(index=False):
        ev = json.loads(p.evidence) if isinstance(p.evidence, str) else (p.evidence or {})
        ly, ry = p.left_coord_y, p.right_coord_y
        lx, rx = p.left_coord_x, p.right_coord_x
        row_y = ev.get("terminal_strip_row_y")
        same_row = abs(ly - ry) < 0.01
        # native line spanning the strip interior at the pin band (y in row_y+1.0..row_y+2.0), not TSB-14 virtual
        lo, hi = min(lx, rx), max(lx, rx)
        band = lines[(lines.start_y.between((row_y or ly) + 1.0, (row_y or ly) + 2.0)) & (lines.end_y.between((row_y or ly) + 1.0, (row_y or ly) + 2.0))]
        spanning = band[(band[["start_x", "end_x"]].min(axis=1) <= lo + 12) & (band[["start_x", "end_x"]].max(axis=1) >= hi - 12)]
        native_through = len(spanning[spanning.source_block_name.isna()])
        virt_through = len(spanning[spanning.source_block_name.notna()])
        # line group provenance
        lgid = p.line_group_id
        mem_src = None
        if isinstance(lgid, str) and lgid in lg.index:
            ids = json.loads(lg.loc[lgid, "member_line_ids"]) if isinstance(lg.loc[lgid, "member_line_ids"], str) else list(lg.loc[lgid, "member_line_ids"])
            mm = lines[lines.line_id.isin(ids)]
            mem_src = ",".join(sorted(set(mm.source_block_name.fillna("NATIVE").astype(str)))) if len(mm) else "NO_MEMBER_LINES"
        # SW pass coverage on each label within sheet
        def sw_cov(label):
            return int(((passes.left_value == label) | (passes.right_value == label)).sum() > 0 and
                       ((passes.pair_kind.isin(["component_mapping", "wire_component_mapping"])) & ((passes.left_value == label) | (passes.right_value == label)) & passes.pair_id.str.startswith("PSW")).sum() > 0)
        rows.append(dict(project_id=pid, sheet_id=sid, pair_id=p.pair_id, left=p.left_value, right=p.right_value,
                         same_row=same_row, row_y=row_y, ly=ly, ry=ry, lx=lx, rx=rx,
                         native_through=native_through, virt_through=virt_through, lg_id=lgid, lg_member_src=mem_src,
                         sw_left=sw_cov(p.left_value), sw_right=sw_cov(p.right_value),
                         strip=ev.get("terminal_strip_instance"), pin_row=ev.get("terminal_strip_pin_row"),
                         left_terminal_text=ev.get("left_terminal_text_id"), right_terminal_text=ev.get("right_terminal_text_id")))
R = pd.DataFrame(rows)
R.to_pickle(W + "lattice_test.pkl")
print("rows", len(R))
print("same_row:", R.same_row.value_counts().to_dict())
print("native_through (non-virtual line spanning box at pin band):", R.native_through.gt(0).sum(), "| virtual spanning:", R.virt_through.gt(0).sum())
print("line group member provenance:", R.lg_member_src.fillna("NONE").value_counts().head(6).to_dict())
print("SW pass covers left label:", R.sw_left.value_counts().to_dict(), "| right:", R.sw_right.value_counts().to_dict())
print("both labels SW-covered:", ((R.sw_left == 1) & (R.sw_right == 1)).sum())
print("per project:", R.groupby("project_id").size().to_dict())
