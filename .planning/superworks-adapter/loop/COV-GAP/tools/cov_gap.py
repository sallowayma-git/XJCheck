"""COV-GAP: read-only coverage-gap analysis over .tmp/superworks_round12_full.

Layers
  a  terminal-strip objects (left / right / _2 per row)
  b  SuperWORKS ports (strict for 端子/装置端子; loose for other categories)
  c  schematic wire-line groups on 二次原理图 pages (endpoint identity)
  d  component / backplane page terminal ports (subset of b)

Per-object records go to the scratch directory given as argv[1] (not into the repository).
"""
import json, math, re, sys, collections
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
RUN = ROOT / ".tmp/superworks_round12_full"
OUT = ROOT / ".planning/superworks-adapter/loop/COV-GAP"
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
FAM = json.loads((OUT / "tools/family_map.json").read_text(encoding="utf-8"))
TERM = {"端子", "装置端子"}
SKIP_DISP = {"skip_stable", "classify_only"}


def J(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (list, dict)):
        return v
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return json.loads(v)
        except Exception:
            return None
    return v


def S(v):
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v)


def F(v):
    try:
        x = float(v)
        return x if x == x else float("nan")
    except Exception:
        return float("nan")


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    l2 = vx * vx + vy * vy
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(l2 > 0, ((px - ax) * vx + (py - ay) * vy) / l2, 0.0)
    t = np.clip(t, 0.0, 1.0)
    dx = ax + t * vx - px
    dy = ay + t * vy - py
    return np.sqrt(dx * dx + dy * dy)


def opposite(side):
    return {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}.get(side, "")


class Sheet:
    def __init__(self):
        self.ports = []
        self.conn = []
        self.dots = []
        self.labels = []
        self.lines = []


def analyze(pid, pdir):
    f = Path(pdir) / "findings"
    pages_df = pd.read_parquet(f / "pages.parquet")
    pages = {}
    for r in pages_df.itertuples():
        pages[r.sheet_id] = dict(page_type=S(r.page_type), disp=S(r.audit_disposition),
                                 role=S(r.audit_role), filename=S(r.filename), sheet_no=S(r.sheet_no))
    ports_df = pd.read_parquet(f / "sw_ports.parquet")
    cov_df = pd.read_parquet(f / "sw_port_coverage.parquet")
    strips_df = pd.read_parquet(f / "sw_strip_rows.parquet")
    pairs_df = pd.read_parquet(f / "pairs.parquet")
    lg_df = pd.read_parquet(f / "line_groups.parquet")
    lines_df = pd.read_parquet(f / "lines.parquet", columns=["line_id", "sheet_id", "start_x", "start_y", "end_x", "end_y"])
    tc_df = pd.read_parquet(f / "terminal_candidates.parquet",
                            columns=["line_group_id", "sheet_id", "side", "status", "rejection_reason", "value",
                                     "endpoint_x", "endpoint_y", "text_id"])
    ta_df = pd.read_parquet(f / "text_assignments.parquet", columns=["text_id", "resolution_status", "assignment_kind"])
    dots_df = pd.read_parquet(f / "sw_connect_dots.parquet", columns=["record_id", "sheet_id", "x", "y"])
    labels_df = pd.read_parquet(f / "sw_connect_labels.parquet",
                                columns=["record_id", "sheet_id", "text", "start_x", "start_y", "end_x", "end_y"])

    # ---------- pairs and SW port references
    by_group = collections.defaultdict(list)
    text_index = collections.defaultdict(list)   # (sheet, text_id) -> [(status, side, lv, rv)]
    port_refs = collections.defaultdict(list)    # port_id -> [(status, side, value_match)]
    n_pairs = 0
    for r in pairs_df.itertuples():
        n_pairs += 1
        ev = J(r.evidence) or {}
        sw = ev.get("superworks") or {}
        rec = dict(pid=r.pair_id, sheet=r.sheet_id, grp=S(r.line_group_id), status=S(r.status), kind=S(r.pair_kind),
                   lv=S(r.left_value).strip(), rv=S(r.right_value).strip(),
                   lt=S(r.left_text_id), rt=S(r.right_text_id),
                   lc=(F(r.left_coord_x), F(r.left_coord_y)), rc=(F(r.right_coord_x), F(r.right_coord_y)))
        if rec["grp"]:
            by_group[rec["grp"]].append(rec)
        for side in ("left", "right"):
            tid = rec["lt"] if side == "left" else rec["rt"]
            if tid:
                text_index[(rec["sheet"], tid)].append((rec["status"], side, rec["lv"], rec["rv"]))
            endpoint = sw.get(side) or {}
            value = rec["lv"] if side == "left" else rec["rv"]
            for port_id in endpoint.get("port_ids", []) or []:
                vm = bool(endpoint.get("value")) and value.casefold() == S(endpoint.get("value")).casefold()
                port_refs[port_id].append((rec["status"], side, vm))

    # ---------- ports / sheets geometry
    sheets = collections.defaultdict(Sheet)
    port_by_id = {}
    for r in ports_df.itertuples():
        contacts = J(r.wire_contacts) or []
        c0 = contacts[0] if contacts else None
        d = dict(rid=r.record_id, sheet=r.sheet_id, cat=S(r.category), ident=S(r.endpoint_identity),
                 ih=S(r.insert_handle), pn=S(r.port_number),
                 sx=F(r.start_x), sy=F(r.start_y), ex=F(r.end_x), ey=F(r.end_y),
                 cx=F(c0["x"]) if c0 else float("nan"), cy=F(c0["y"]) if c0 else float("nan"),
                 has_contact=bool(contacts), reason=J(r.reason_codes) or [])
        port_by_id[r.record_id] = d
        sheets[r.sheet_id].ports.append(d)

    cov_by_id = {r.port_id: r for r in cov_df.itertuples()}

    # ---------- strip rows
    strip_objs = []
    pot_objs = []
    xdata_nonzero = collections.Counter()
    for r in strips_df.itertuples():
        xd = J(r.raw_xdata) or {}
        for slot in ("LDDZ_LEFTTEXT_HANDLE_2", "LDDZ_RIGHTTEXT_HANDLE_2"):
            if any(str(v[1]) not in ("0", "") for v in (xd.get(slot) or [])):
                xdata_nonzero[slot] += 1
        pots = J(r.potentials) or []
        for pt_ in pots:
            pot_objs.append(dict(record_id=r.record_id, sheet=r.sheet_id, text_id=S(pt_.get("text_id")),
                                 value=S(pt_.get("value")), resolved=bool(pt_.get("resolved")),
                                 x=F(pt_.get("x")), y=F(pt_.get("y"))))
        for c in J(r.connections) or []:
            sheets[r.sheet_id].conn.append((F(c.get("x")), F(c.get("y")), S(c.get("text_id")), S(c.get("value")),
                                            bool(c.get("resolved")), r.record_id))
            strip_objs.append(dict(record_id=r.record_id, sheet=r.sheet_id, side=S(c.get("side")),
                                   text_id=S(c.get("text_id")), value=S(c.get("value")),
                                   resolved=bool(c.get("resolved")), x=F(c.get("x")), y=F(c.get("y")),
                                   potentials=len(pots), potentials_resolved=sum(bool(p.get("resolved")) for p in pots)))
    for r in dots_df.itertuples():
        sheets[r.sheet_id].dots.append((F(r.x), F(r.y)))
    for r in labels_df.itertuples():
        sheets[r.sheet_id].labels.append((F(r.start_x), F(r.start_y), F(r.end_x), F(r.end_y), S(r.text)))

    ta_status = {}
    for r in ta_df.itertuples():
        ta_status.setdefault(r.text_id, S(r.resolution_status))

    # ---------- line groups / lines / candidates
    lg_by_id = {}
    lg_members = {}
    for r in lg_df.itertuples():
        lg_by_id[r.line_group_id] = dict(sheet=r.sheet_id, sx=F(r.start_x), sy=F(r.start_y), ex=F(r.end_x), ey=F(r.end_y))
        lg_members[r.line_group_id] = set(J(r.member_line_ids) or [])
    for r in lines_df.itertuples():
        sheets[r.sheet_id].lines.append((r.line_id, F(r.start_x), F(r.start_y), F(r.end_x), F(r.end_y)))
    cands = collections.defaultdict(list)
    for r in tc_df.itertuples():
        cands[S(r.line_group_id)].append(dict(side=S(r.side), status=S(r.status), reason=S(r.rejection_reason),
                                              value=S(r.value), ex=F(r.endpoint_x), ey=F(r.endpoint_y)))

    # ---------- per-sheet port arrays
    arr = {}
    for sid, sh in sheets.items():
        P = sh.ports
        arr[sid] = dict(
            rid=np.array([p["rid"] for p in P], dtype=object),
            sx=np.array([p["sx"] for p in P]), sy=np.array([p["sy"] for p in P]),
            ex=np.array([p["ex"] for p in P]), ey=np.array([p["ey"] for p in P]),
            cx=np.array([p["cx"] for p in P]), cy=np.array([p["cy"] for p in P]))

    def port_hits(sid, qx, qy, exclude, tol=1.0):
        if sid not in arr:
            return []
        a = arr[sid]
        d_seg = seg_dist(qx, qy, a["sx"], a["sy"], a["ex"], a["ey"])
        d_con = np.hypot(a["cx"] - qx, a["cy"] - qy)
        m = (np.nan_to_num(d_seg, nan=1e9) <= tol) | (np.nan_to_num(d_con, nan=1e9) <= tol)
        return [port_by_id[a["rid"][i]] for i in np.nonzero(m)[0] if a["rid"][i] != exclude]

    def strip_hits(sid, qx, qy, tol=1.5):
        if sid not in sheets:
            return []
        return [c for c in sheets[sid].conn if not math.isnan(c[0]) and math.hypot(c[0] - qx, c[1] - qy) <= tol]

    def dot_hits(sid, qx, qy, tol=1.5):
        if sid not in sheets:
            return []
        hits = [(x, y) for x, y in sheets[sid].dots if math.hypot(x - qx, y - qy) <= tol]
        for sx, sy, ex, ey, _t in sheets[sid].labels:
            if min(math.hypot(sx - qx, sy - qy), math.hypot(ex - qx, ey - qy)) <= tol:
                hits.append((sx, sy))
        return hits

    def line_touch(sid, qx, qy, exclude_ids, tol=0.3):
        if sid not in sheets:
            return []
        return [l for l in sheets[sid].lines if l[0] not in exclude_ids and
                min(math.hypot(l[1] - qx, l[2] - qy), math.hypot(l[3] - qx, l[4] - qy)) <= tol]

    # ---------- strip-object coverage
    for o in strip_objs:
        pg = pages.get(o["sheet"], {})
        all_refs = text_index.get((o["sheet"], o["text_id"]), [])
        refs = [x for x in all_refs if x[0] != "discard"]
        o["page_type"] = pg.get("page_type", "")
        o["page_disp"] = pg.get("disp", "")
        o["text_status"] = ta_status.get(o["text_id"], "")
        o["covered_partial"] = bool(refs)
        strict = any((x[2] if x[1] == "left" else x[3]) and (x[3] if x[1] == "left" else x[2]) for x in refs)
        o["covered_strict"] = strict
        if strict:
            o["reason"] = "covered"
        elif not o["resolved"]:
            o["reason"] = "S1_连接文字未解析"
        elif pg.get("disp") in SKIP_DISP or pg.get("role") == "skip":
            o["reason"] = "S5_页面不在配对审计范围"
        elif not refs:
            if all_refs:
                o["reason"] = "S3_仅discard配对"
            elif o["text_status"] in ("rejected", "discarded", "out_of_scope", "unselected", "review", "label_only"):
                o["reason"] = f"S2_文字未入配对({o['text_status']})"
            else:
                o["reason"] = f"S6_无配对({o['text_status'] or '无文字判定'})"
        else:
            o["reason"] = "S4_挂接但另一侧身份缺失"
    strip_cov_strict = {(o["sheet"], o["text_id"]): o["covered_strict"] for o in strip_objs}

    # ---------- strip destination texts ("去向文字", potentials) and cross-page SW targets
    port_key = collections.defaultdict(list)
    for pd_ in port_by_id.values():
        port_key[(pd_["ih"], pd_["pn"])].append(pd_["rid"])
    nd_text = {k for k, refs in text_index.items() if any(x[0] != "discard" for x in refs)}
    pot_pat = re.compile(r"^未定义([0-9A-Za-z]+):(\w+?)_")
    for o in pot_objs:
        pg = pages.get(o["sheet"], {})
        o["page_type"] = pg.get("page_type", "")
        o["covered"] = (o["sheet"], o["text_id"]) in nd_text
        o["t_rid"] = o["t_cat"] = o["t_sheet"] = o["t_ident"] = ""
        o["t_cx"] = o["t_cy"] = float("nan")
        o["t_consumed"] = None
        m = pot_pat.match(o["value"])
        if o["covered"]:
            o["reason"] = "covered"
        elif not o["resolved"]:
            o["reason"] = "X0_去向文字未解析"
        elif pg.get("disp") in SKIP_DISP or pg.get("role") == "skip":
            o["reason"] = "X5_页面不在配对审计范围"
        elif not m:
            o["reason"] = "X4_非跨页去向未被配对"
        else:
            rids = port_key.get((m.group(1), m.group(2)), [])
            if not rids:
                o["reason"] = "X3_跨页目标端口不存在"
            else:
                rid = rids[0]
                tp = port_by_id[rid]
                consumed = bool(cov_by_id[rid].consumed) if rid in cov_by_id else any(
                    x[0] != "discard" for x in port_refs.get(rid, []))
                o["t_rid"], o["t_cat"], o["t_sheet"], o["t_ident"] = rid, tp["cat"], tp["sheet"], tp["ident"]
                o["t_cx"], o["t_cy"], o["t_consumed"] = tp["cx"], tp["cy"], consumed
                o["reason"] = ("X1_跨页目标端口已消费(本链路未建立)" if consumed else "X2_跨页目标端口未消费")

    # ---------- other-end classification for uncovered eligible terminal ports
    def other_end(p, rec):
        g = rec["group"]
        if not g or g not in lg_by_id:
            return "O0_导线组缺失"
        L = lg_by_id[g]
        sid = p["sheet"]
        cx, cy = p["cx"], p["cy"]
        if math.isnan(cx):
            return "O0_无导线接触点"
        ds = math.hypot(cx - L["sx"], cy - L["sy"])
        de = math.hypot(cx - L["ex"], cy - L["ey"])
        qx, qy = (L["ex"], L["ey"]) if ds < de else (L["sx"], L["sy"])
        hits = port_hits(sid, qx, qy, p["rid"])
        if hits:
            def rank(h):
                if h["cat"] in TERM and h["rid"] in cov_by_id and cov_by_id[h["rid"]].eligible:
                    return 0
                if h["cat"] in TERM:
                    return 1
                if h["cat"] == "内部元件":
                    return 2
                return 3
            h = sorted(hits, key=rank)[0]
            if h["cat"] in TERM and h["rid"] in cov_by_id and cov_by_id[h["rid"]].eligible:
                return "O1_对端为可判SW端子但未成对"
            if h["cat"] in TERM:
                return "O2_对端为不可判SW端子"
            if h["cat"] == "内部元件":
                return "O3_对端为内部元件端口(无身份)"
            return "O4_对端为线圈/接地/接插件端口"
        sc = strip_hits(sid, qx, qy)
        if sc:
            covered = any(strip_cov_strict.get((sid, c[2]), False) for c in sc)
            return "O5_对端为端子排连接点" + ("(已覆盖)" if covered else "(未覆盖)")
        if dot_hits(sid, qx, qy):
            return "O6_对端为连接点/连接标签"
        other_side = opposite(rec["side"] or "")
        oc = [c for c in cands.get(g, []) if c["side"] == other_side]
        if any(c["status"] == "accepted" for c in oc):
            return "O7_对端文字已接受但未成对"
        if oc:
            reasons = collections.Counter(c["reason"] or "none" for c in oc)
            return "O8_对端候选全部被拒:" + reasons.most_common(1)[0][0]
        if line_touch(sid, qx, qy, lg_members.get(g, set())):
            return "O9_对端接入其它导线"
        return "O10_对端无实体无文字"

    def classify_port(p, rec, pg):
        if pg.get("disp") in SKIP_DISP or pg.get("role") == "skip":
            return "P0_页面不在配对审计范围"
        if not p["ident"]:
            return "P1_本端身份未解析"
        g = rec["group"]
        grp_pairs = by_group.get(g, []) if g else []
        nd = [x for x in grp_pairs if x["status"] != "discard"]
        refs_nd = [x for x in port_refs.get(p["rid"], []) if x[0] != "discard"]
        if refs_nd and all(not x[2] for x in refs_nd):
            return "P4_SW引用存在但身份值不一致"
        if grp_pairs and not nd:
            return "P3_同组配对均为discard"
        if nd and not refs_nd:
            return "P5_同组有配对但未引用本端口"
        return other_end(p, rec)

    port_objs = []
    for c in cov_df.itertuples():
        p = port_by_id.get(c.port_id)
        if p is None:
            continue
        pg = pages.get(c.sheet_id, {})
        obs_list = J(c.wire_group_observations) or []
        obs = obs_list[0] if obs_list else {}
        rec = dict(port_id=c.port_id, sheet=c.sheet_id, category=c.category, page_type=pg.get("page_type", ""),
                   eligible=bool(c.eligible), consumed=bool(c.consumed), pass_=bool(c.pass_) if hasattr(c, "pass_") else None,
                   reason_codes=list(J(c.reason_codes) or []),
                   group=obs.get("line_group_id"), side=obs.get("endpoint_side"),
                   ident=p["ident"], cx=p["cx"], cy=p["cy"], n_obs=len(obs_list))
        rec["oend"] = ""
        if not rec["eligible"]:
            rec["reason"] = "N0_不在分母(无接线或标签未解析)"
        elif rec["consumed"]:
            rec["reason"] = "covered"
        else:
            rec["reason"] = classify_port(p, rec, pg)
            rec["oend"] = other_end(p, rec)
        rec["page_disp"] = pg.get("disp", "")
        port_objs.append(rec)

    # non-terminal SW ports: loose coverage (referenced by any non-discard SW pair)
    for p in port_by_id.values():
        if p["cat"] in TERM:
            continue
        refs_nd = [x for x in port_refs.get(p["rid"], []) if x[0] != "discard"]
        port_objs.append(dict(port_id=p["rid"], sheet=p["sheet"], category=p["cat"],
                              page_type=pages.get(p["sheet"], {}).get("page_type", ""), eligible=bool(p["has_contact"]),
                              consumed=bool(refs_nd), pass_=None, reason_codes=p["reason"], group=None, side=None,
                              ident=p["ident"], cx=p["cx"], cy=p["cy"], n_obs=0,
                              reason="covered" if refs_nd else ("N1_非端子未引用" if p["has_contact"] else "N0_不在分母(无接线或标签未解析)"),
                              page_disp=pages.get(p["sheet"], {}).get("disp", "")))

    # ---------- layer c: schematic wire groups
    group_objs = []
    for g, L in lg_by_id.items():
        pg = pages.get(L["sheet"], {})
        sid = L["sheet"]
        state = {}
        for sn, (px, py) in (("start", (L["sx"], L["sy"])), ("end", (L["ex"], L["ey"]))):
            res = False
            for x in by_group.get(g, []):
                if x["status"] == "discard":
                    continue
                for coord, val in ((x["lc"], x["lv"]), (x["rc"], x["rv"])):
                    if val and not math.isnan(coord[0]) and math.hypot(coord[0] - px, coord[1] - py) <= 2.0:
                        res = True
            near_c = [c for c in cands.get(g, []) if not math.isnan(c["ex"]) and math.hypot(c["ex"] - px, c["ey"] - py) <= 2.5]
            if any(c["status"] == "accepted" for c in near_c):
                res = True
            if res:
                reason = "resolved"
            elif near_c:
                rs = collections.Counter(c["reason"] or "none" for c in near_c)
                reason = "G1_端点候选全部被拒:" + rs.most_common(1)[0][0]
            elif any(p_["has_contact"] and p_["ident"] == "" for p_ in port_hits(sid, px, py, None)):
                reason = "G2_端点为SW元件端口(无身份)"
            elif strip_hits(sid, px, py):
                reason = "G3_端点为端子排连接点(未配对)"
            elif dot_hits(sid, px, py):
                reason = "G4_端点为连接点/标签"
            elif line_touch(sid, px, py, lg_members.get(g, set())):
                reason = "G5_端点接入其它导线"
            else:
                reason = "G6_端点无任何实体"
            state[sn] = (res, reason)
        n_res = int(state["start"][0]) + int(state["end"][0])
        group_objs.append(dict(group=g, sheet=sid, page_type=pg.get("page_type", ""), page_disp=pg.get("disp", ""),
                               origin="SW元数据" if g.startswith("GWSW") else "legacy",
                               n_resolved=n_res, reason_start=state["start"][1], reason_end=state["end"][1],
                               sx=L["sx"], sy=L["sy"], ex=L["ex"], ey=L["ey"]))

    return dict(pid=pid, strip=strip_objs, pots=pot_objs, ports=port_objs, groups=group_objs,
                xdata_nonzero=dict(xdata_nonzero), n_pairs=n_pairs)


def main():
    run = json.loads((RUN / "run.json").read_text(encoding="utf-8"))
    strip_rows, port_rows, group_rows, pot_rows, meta = [], [], [], [], {}
    for p in run["projects"]:
        pid = p["project_id"]
        res = analyze(pid, p["project_dir"])
        for coll, sink in ((res["strip"], strip_rows), (res["ports"], port_rows), (res["groups"], group_rows), (res["pots"], pot_rows)):
            for o in coll:
                o["project"] = pid
                o["family"] = FAM[pid]
                sink.append(o)
        meta[pid] = dict(xdata_nonzero=res["xdata_nonzero"], n_pairs=res["n_pairs"])
        print(pid, FAM[pid][:8], "strip", len(res["strip"]), "ports", len(res["ports"]), "groups", len(res["groups"]), flush=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(strip_rows).to_pickle(SCRATCH / "strip.pkl")
    pd.DataFrame(port_rows).to_pickle(SCRATCH / "ports.pkl")
    pd.DataFrame(group_rows).to_pickle(SCRATCH / "groups.pkl")
    pd.DataFrame(pot_rows).to_pickle(SCRATCH / "pots.pkl")
    (SCRATCH / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("done strip", len(strip_rows), "pots", len(pot_rows), "ports", len(port_rows), "groups", len(group_rows))


if __name__ == "__main__":
    main()
