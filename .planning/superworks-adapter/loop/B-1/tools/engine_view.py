import sys, json
sys.path.insert(0, "F:/workspace/XJToolkit/.planning/superworks-adapter/loop/B-1/tools")
from common import *
pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 60); pd.set_option("display.max_columns", 40)
for proj, run, pid, fid, sid, name in TARGETS:
    print("#" * 20, name)
    tx = table(proj, run, "texts")
    tc = table(proj, run, "terminal_candidates")
    ta = table(proj, run, "text_assignments")
    lg = table(proj, run, "line_groups")
    pairs = table(proj, run, "pairs")
    g = pairs[pairs.pair_id == pid].iloc[0]
    print("pair line_group", g.line_group_id, "status", g.status, "left", g.left_value, "right", g.right_value)
    L = lg[lg.line_group_id == g.line_group_id].iloc[0]
    print("linegroup", L[["sheet_id","start_x","start_y","end_x","end_y","length","wire_candidate_score","member_line_ids","layer_hints","orientation"]].to_dict())
    # texts within 25 of the line group
    cx = (L.start_x + L.end_x) / 2; cy = (L.start_y + L.end_y) / 2
    near = tx[(tx.sheet_id == sid) & ((tx.insert_x - cx).abs() < 25) & ((tx.insert_y - cy).abs() < 25)]
    cols = ["text_id","handle","entity_type","text","layer","insert_x","insert_y","bbox_min_x","bbox_min_y","bbox_max_x","bbox_max_y","is_numeric_candidate","source_block_name"]
    print(near[cols].to_string())
    ids = set(near.text_id)
    print("-- terminal_candidates for group")
    t2 = tc[tc.line_group_id == g.line_group_id]
    print(t2[["candidate_id","side","text_id","text","value","score","status","rejection_reason","endpoint_x","endpoint_y","text_insert_x","text_insert_y","channel","channel_detail"]].to_string())
    print("-- text_assignments for near texts")
    a2 = ta[ta.text_id.isin(ids)]
    print(a2[["text_id","text","layer","channel","audit_role","audit_disposition","assignment_kind","consumed_by_pair_ids"]].to_string())
