"""For each pass pair removed by WIRE-BREAK (base only), check its base line group for a symbol body in its span.

A symbol body in the span: on the group's line, two TERMPOINT marks of one symbol, one left and one right of the
centre, both inside the group span (SuperWORKS ports and unregistered SYMB2 TERMPOINTs of the same sheet).
usage: wb_removed_pass.py BASE_ROOT NEW_ROOT OUT_JSON p001 ...
"""
import glob, json, os, sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

base, new, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
pids = sys.argv[4:]
results = []
for pid in pids:
    bd = glob.glob(str(base / pid / "*" / "findings"))[0]
    nd = glob.glob(str(new / pid / "*" / "findings"))[0]
    bp = pd.read_parquet(bd + "/pairs.parquet")
    np_ = pd.read_parquet(nd + "/pairs.parquet")
    bg = pd.read_parquet(bd + "/line_groups.parquet").set_index("line_group_id")
    ports = pd.read_parquet(bd + "/sw_ports.parquet")
    unreg = pd.read_parquet(bd + "/sw_unregistered_symb2.parquet")
    marks = defaultdict(list)  # sheet -> [(key, rid, x1,y1,x2,y2)]
    for r in ports.itertuples():
        marks[r.sheet_id].append((r.symbol_id, r.record_id, r.start_x, r.start_y, r.end_x, r.end_y))
    for r in unreg.itertuples():
        for t in json.loads(r.termpoints):
            (ax, ay), (bx, by) = t["a"], t["b"]
            marks[r.sheet_id].append((f"SW:{r.file_id}:{r.sheet_id}:{r.instance_path}", f"{r.record_id}#{t['number']}", ax, ay, bx, by))
    lines_by_id = {}
    lines_df = pd.read_parquet(bd + "/lines.parquet")
    for ln in lines_df.itertuples():
        lines_by_id[(ln.sheet_id, ln.line_id)] = (ln.start_x, ln.start_y, ln.end_x, ln.end_y)
    # removed pass: base pass pairs whose content key has no pass in new
    norm = lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
    nkeys = set(zip(np_.sheet_id, np_.left_value.map(norm), np_.right_value.map(norm), np_.pair_kind, np_.status))
    status = os.environ.get("WB_STATUS", "pass")
    for r in bp[bp.status == status].itertuples():
        lv = "" if r.left_value is None or (isinstance(r.left_value, float) and pd.isna(r.left_value)) else str(r.left_value)
        rv = "" if r.right_value is None or (isinstance(r.right_value, float) and pd.isna(r.right_value)) else str(r.right_value)
        if (r.sheet_id, lv, rv, r.pair_kind, status) in nkeys:
            continue
        g = bg.loc[r.line_group_id] if r.line_group_id in bg.index else None
        if g is None:
            results.append({"pid": pid, "pair_id": r.pair_id, "reason": "no_base_line_group", "kind": r.pair_kind,
                            "left": lv, "right": rv})
            continue
        horizontal = abs(g.start_y - g.end_y) < 1e-6
        lo, hi = (min(g.start_x, g.end_x), max(g.start_x, g.end_x)) if horizontal else (min(g.start_y, g.end_y), max(g.start_y, g.end_y))
        cross = g.start_y if horizontal else g.start_x
        # Uncovered gaps of the base group's member segments (per gap, not the whole span).
        spans = []
        members = g.member_line_ids
        if isinstance(members, str):
            members = json.loads(members or "[]")
        for mid_id in members:
            ln = lines_by_id.get((r.sheet_id, mid_id))
            if ln is None:
                continue
            a1, a2 = (min(ln[0], ln[2]), max(ln[0], ln[2])) if horizontal else (min(ln[1], ln[3]), max(ln[1], ln[3]))
            spans.append((a1, a2))
        spans.sort()
        gaps = []
        reach = None
        for a1, a2 in spans:
            if reach is not None and a1 - reach > 1e-6:
                gaps.append((reach, a1))
            reach = a2 if reach is None else max(reach, a2)
        body = None
        for glo, ghi in gaps:
            tol = 1.0
            inside = defaultdict(list)
            for key, rid, x1, y1, x2, y2 in marks[r.sheet_id]:
                ax1, ax2, c = (x1, x2, y1) if horizontal else (y1, y2, x1)
                if abs(c - cross) > 1.0 or min(ax1, ax2) < glo - tol or max(ax1, ax2) > ghi + tol:
                    continue
                inside[key].append(((ax1 + ax2) / 2.0, rid))
            mid = (glo + ghi) / 2.0
            for key, items in inside.items():
                if any(c < mid for c, _ in items) and any(c > mid for c, _ in items):
                    body = (key, round(glo, 2), round(ghi, 2))
                    break
            if body:
                break
        results.append({"pid": pid, "pair_id": r.pair_id, "sheet": r.sheet_id, "kind": r.pair_kind, "left": lv,
                        "right": rv, "group": r.line_group_id, "span": [round(lo, 2), round(hi, 2)],
                        "uncovered_gaps": [[round(a, 2), round(b, 2)] for a, b in gaps],
                        "symbol_body_inside_span": body is not None, "body": body})
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
from collections import Counter
print(Counter((x.get("symbol_body_inside_span"), x.get("reason")) for x in results))
print("total removed pass:", len(results))
