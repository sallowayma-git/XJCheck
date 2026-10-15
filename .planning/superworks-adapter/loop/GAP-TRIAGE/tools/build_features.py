"""Per-gap feature extraction for R-RECOGNITION-GAP triage (read-only).

Reads the 2594dbe full-run output (current), the round25 baseline output, and the frozen corpus manifest.
Writes only to .tmp/gap_triage_work/. One row per R-RECOGNITION-GAP issue with the facts needed to classify it:
endpoint categories and identities, device-internal verdict, V1 closure (current and round25), V2 binding,
cross-page coverage, and the free-end geometry.

Run: PYTHONIOENCODING=utf-8 python -I build_features.py
"""
from __future__ import annotations

import glob
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
CUR = REPO / ".tmp/engine_coordination_full_acceptance/current"
R25 = REPO / ".tmp/superworks_round25_full"
WORK = REPO / ".tmp/gap_triage_work"
MANIFEST = REPO / ".planning/superworks-adapter/corpus_manifest.json"

sys.path.insert(0, str(REPO / "src"))
from dwg_audit.audit.superworks_device_internal import device_internal_verdict  # noqa: E402

DEVICE = "装置端子"
INTERNAL = {"内部元件": "INT", "线圈": "COIL"}
CAT_CODE = {"装置端子": "DEV", "内部元件": "INT", "线圈": "COIL", "端子": "TERM", "接地": "GND", "接插件": "CONN"}
NEAR_PORT = 2.5
NEAR_TEXT = 4.0
NEAR_LINE = 0.6
V2_INFO = {}


def jload(v, default):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return default


def pdist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def seg_point_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return pdist(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return pdist(p, (ax + t * dx, ay + t * dy))


def project_dirs(root: Path):
    out = {}
    for d in sorted(glob.glob(str(root / "p*"))):
        pid = Path(d).name
        if not pid[1:].isdigit():
            continue
        fdirs = glob.glob(os.path.join(d, "*", "findings"))
        if fdirs:
            out[pid] = fdirs[0]
    return out


def read_pq(path):
    return pd.read_parquet(path) if os.path.exists(path) else pd.DataFrame()


def load_pairs(fdir):
    pr = read_pq(os.path.join(fdir, "pairs.parquet"))
    rows = []
    for r in pr.itertuples(index=False):
        ev = jload(r.evidence, {})
        pts = []
        for x, y in ((r.left_coord_x, r.left_coord_y), (r.right_coord_x, r.right_coord_y)):
            if x is not None and not (isinstance(x, float) and math.isnan(x)) and y is not None and not (isinstance(y, float) and math.isnan(y)):
                pts.append((float(x), float(y)))
            else:
                pts.append(None)
        for side in ("left", "right"):
            ph = ev.get(f"selected_{side}_physical_endpoint") or {}
            pos = ph.get("position")
            if isinstance(pos, (list, tuple)) and len(pos) == 2 and pos[0] is not None:
                pass
        rows.append({
            "pair_id": r.pair_id, "sheet_id": r.sheet_id, "file_id": r.file_id, "status": r.status,
            "pair_kind": r.pair_kind, "left_value": r.left_value, "right_value": r.right_value,
            "lg": r.line_group_id if isinstance(r.line_group_id, str) else None,
            "discard_reason": (ev.get("discard_reason") if isinstance(ev, dict) else None),
            "pts": pts,
            "line_start": ev.get("line_start"), "line_end": ev.get("line_end"),
            "geom": None,
            "v2_source": any(
                isinstance(ev.get(k), dict) and ev.get(k).get("source") == "reciprocal_cad_label_and_terminal_geometry"
                for k in ("selected_left_physical_endpoint", "selected_right_physical_endpoint")),
        })
    return rows


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    fam_of = {}
    for p in manifest["projects"]:
        root = p["input_root"]
        parts = root.replace("/", "\\").split("\\")
        try:
            i = parts.index("test")
            fam_of[p["project_id"]] = parts[i + 1]
        except ValueError:
            fam_of[p["project_id"]] = parts[-2] if len(parts) > 1 else "unknown"
    cur_dirs = project_dirs(CUR)
    r25_dirs = project_dirs(R25)
    feats = []
    counters = Counter()
    for pid, fdir in cur_dirs.items():
        pdir = os.path.dirname(fdir)
        issues_path = glob.glob(os.path.join(pdir, "..", "audit", "issues.json"))
        if not issues_path:
            issues_path = glob.glob(os.path.join(os.path.dirname(fdir), "audit", "issues.json"))
        if not issues_path:
            print("no issues", pid)
            continue
        issues = json.load(open(issues_path[0], encoding="utf-8"))
        gaps = [i for i in issues if i.get("rule_id") == "R-RECOGNITION-GAP"]
        if not gaps:
            continue
        sp = read_pq(os.path.join(fdir, "sw_ports.parquet"))
        port_by_id = {}
        for r in sp.itertuples(index=False):
            port_by_id[r.record_id] = {
                "category": r.category, "identity": r.endpoint_identity, "label": jload(r.label, {}),
                "port_number": r.port_number, "symbol_id": r.symbol_id, "file_id": r.file_id, "sheet_id": r.sheet_id,
                "wire_contacts": jload(r.wire_contacts, []),
                "start": (r.start_x, r.start_y), "end": (r.end_x, r.end_y),
            }
        cov = read_pq(os.path.join(fdir, "sw_port_coverage.parquet"))
        cov_by_id = {r["port_id"]: r for r in cov.to_dict("records")}
        dil = read_pq(os.path.join(fdir, "sw_device_internal_links.parquet"))
        dil_ports = set(dil.port_id.dropna()) if len(dil) else set()
        dil_elem = set(dil.element_port_id.dropna()) if len(dil) and "element_port_id" in dil else set()
        ucp = read_pq(os.path.join(fdir, "sw_unregistered_symb2.parquet"))
        unreg = []  # (file, sheet, point, block label, resolved, reciprocal, block_name)
        for r in ucp.itertuples(index=False):
            tps = jload(r.termpoints, [])
            for tp in tps:
                for key in ("a", "b"):
                    if tp.get(key):
                        unreg.append((r.file_id, r.sheet_id, tuple(tp[key]), r.label_value, bool(r.label_resolved),
                                      bool(r.label_reciprocal), r.block_name, r.insert_handle))
        unreg_by_sheet = defaultdict(list)
        for u in unreg:
            unreg_by_sheet[(u[0], u[1])].append(u)
        cp = read_pq(os.path.join(fdir, "sw_cross_page_links.parquet"))
        xcover = {}
        for r in cp.itertuples(index=False):
            if r.target_port_id:
                xcover.setdefault(r.target_port_id, []).append((r.relation, bool(r.covers_target)))
        cand = read_pq(os.path.join(fdir, "sw_cross_page_candidates.parquet"))
        xcand = set(cand.target_port_id.dropna()) if len(cand) and "target_port_id" in cand else set()
        pages = read_pq(os.path.join(fdir, "pages.parquet"))
        ptype = {(r.file_id, r.sheet_id): (r.page_type, r.sheet_category) for r in pages.itertuples(index=False)}
        tc = read_pq(os.path.join(fdir, "terminal_candidates.parquet"))
        v2_pts = defaultdict(list)  # (file, sheet) -> [(x,y)]
        v2_info = defaultdict(list)  # (file, sheet) -> [(x,y,text value, port_id)]
        tx_path = os.path.join(fdir, "texts.parquet")
        tx_map = {}
        if os.path.exists(tx_path):
            tx_df = pd.read_parquet(tx_path, columns=["handle", "text"])
            tx_map = dict(zip(tx_df.handle, tx_df.text))
        if len(tc):
            for r in tc.itertuples(index=False):
                pe = jload(r.physical_endpoint_evidence, {})
                if isinstance(pe, dict) and pe.get("position"):
                    v2_pts[(r.file_id, r.sheet_id)].append(tuple(pe["position"]))
                    v2_info[(r.file_id, r.sheet_id)].append((float(pe["position"][0]), float(pe["position"][1]),
                        tx_map.get(pe.get("text_handle")), pe.get("port_id")))
        lg = read_pq(os.path.join(fdir, "line_groups.parquet"))
        lines = read_pq(os.path.join(fdir, "lines.parquet"))
        lg_segs = defaultdict(list)  # (file,sheet) -> (lg, a, b, orientation, length)
        for r in lg.itertuples(index=False):
            lg_segs[(r.file_id, r.sheet_id)].append((r.line_group_id, (r.start_x, r.start_y), (r.end_x, r.end_y), r.orientation, r.length))
        line_segs = defaultdict(list)
        for r in lines.itertuples(index=False):
            blk = r.source_block_name if isinstance(r.source_block_name, str) else None
            line_segs[(r.file_id, r.sheet_id)].append(((r.start_x, r.start_y), (r.end_x, r.end_y), blk, float(r.length or 0.0)))
        text_df = read_pq(os.path.join(fdir, "texts.parquet"))
        texts_by = defaultdict(list)
        if len(text_df):
            for r in text_df.itertuples(index=False):
                if r.insert_x is not None and not (isinstance(r.insert_x, float) and math.isnan(r.insert_x)):
                    texts_by[(r.file_id, r.sheet_id)].append(((r.insert_x, r.insert_y), str(r.text)))
        lg_geom = {}
        for r in lg.itertuples(index=False):
            lg_geom[r.line_group_id] = ((r.start_x, r.start_y), (r.end_x, r.end_y))
        pairs_cur = load_pairs(fdir)
        attach_geom(pairs_cur, lg_geom)
        r25_fdir = r25_dirs.get(pid)
        pairs_r25 = load_pairs(r25_fdir) if r25_fdir else []
        r25_lg = read_pq(os.path.join(r25_fdir, "line_groups.parquet")) if r25_fdir else pd.DataFrame()
        r25_geom = {r.line_group_id: ((r.start_x, r.start_y), (r.end_x, r.end_y)) for r in r25_lg.itertuples(index=False)}
        attach_geom(pairs_r25, r25_geom)
        pairs_by_sheet = defaultdict(list)
        for p in pairs_cur:
            pairs_by_sheet[(p["file_id"], p["sheet_id"])].append(p)
        pairs_r25_by_sheet = defaultdict(list)
        for p in pairs_r25:
            pairs_r25_by_sheet[(p["file_id"], p["sheet_id"])].append(p)
        for gi in gaps:
            ev = gi.get("evidence") or {}
            global V2_INFO
            V2_INFO = v2_info
            feats.append(make_row(pid, fam_of.get(pid, "?"), gi, ev, port_by_id, cov_by_id, dil_ports, dil_elem,
                                  unreg_by_sheet, xcover, xcand, ptype, v2_pts, lg_segs, line_segs, texts_by,
                                  pairs_by_sheet, pairs_r25_by_sheet, counters))
        print("done", pid, len(gaps), flush=True)
    df = pd.DataFrame(feats)
    df.to_pickle(WORK / "features.pkl")
    with open(WORK / "feature_counters.json", "w", encoding="utf-8") as fh:
        json.dump(counters, fh, ensure_ascii=False, indent=1)
    print("rows", len(df))


def covers_segment(seg, geom, tol=0.8):
    """True when the observed segment lies on the geometric line (a, b) of a pair's line group, with overlap."""
    if geom is None or seg is None:
        return False
    a, b = geom
    (x1, y1), (x2, y2) = seg
    if abs(a[1] - b[1]) <= 1e-6 and abs(y1 - a[1]) <= tol and abs(y2 - a[1]) <= tol:
        lo, hi = min(a[0], b[0]) - tol, max(a[0], b[0]) + tol
        return min(x1, x2) >= lo and max(x1, x2) <= hi and abs(x2 - x1) > 1e-6
    if abs(a[0] - b[0]) <= 1e-6 and abs(x1 - a[0]) <= tol and abs(x2 - a[0]) <= tol:
        lo, hi = min(a[1], b[1]) - tol, max(a[1], b[1]) + tol
        return min(y1, y2) >= lo and max(y1, y2) <= hi and abs(y2 - y1) > 1e-6
    return False


def value_match(value, ident):
    v, i = str(value or "").strip(), str(ident or "").strip()
    if not v or not i:
        return False
    return v == i or i.endswith(v) and v.isdigit() or v.endswith(i) and i.isdigit() or i.endswith("n" + v)


def attach_geom(pairs, lg_geom):
    for p in pairs:
        g = lg_geom.get(p["lg"]) if p["lg"] else None
        if g is None and p.get("line_start") and p.get("line_end"):
            try:
                g = (tuple(float(v) for v in p["line_start"][:2]), tuple(float(v) for v in p["line_end"][:2]))
            except Exception:  # noqa: BLE001
                g = None
        p["geom"] = g


def side_info(side, port_by_id, cov_by_id):
    ports = side.get("ports") or []
    port_ids = side.get("port_ids") or []
    p0 = ports[0] if ports else {}
    pid = port_ids[0] if port_ids else ""
    rec = port_by_id.get(pid, {})
    category = rec.get("category") or p0.get("category") or side.get("category") or ""
    identity = rec.get("identity") or p0.get("endpoint_identity") or side.get("value") or ""
    cov = cov_by_id.get(pid)
    contacts = rec.get("wire_contacts") or []
    contact = None
    if contacts:
        c = contacts[0]
        contact = (c.get("x"), c.get("y"))
    return {
        "port_id": pid, "n_ports": len(port_ids), "category": category, "identity": identity,
        "label": rec.get("label", {}) or {}, "port_number": side.get("port_number"),
        "symbol_id": side.get("symbol_id"), "wire_touched": bool(side.get("wire_touched")),
        "reason_codes": list(side.get("reason_codes") or []), "value": side.get("value"),
        "contact": contact, "start": rec.get("start"), "end": rec.get("end"),
        "cov_page_type": cov.get("page_type") if cov else None,
        "cov_reason": list(jload(cov.get("reason_codes"), [])) if cov else [],
        "cov_excluded_dev": bool(cov.get("excluded_device_internal")) if cov else False,
        "cov_overruled": bool(cov.get("device_internal_overruled")) if cov else False,
        "cov_consumed": bool(cov.get("consumed")) if cov else False,
        "cov_pass": bool(cov.get("pass")) if cov else False,
        "cov_eligible": bool(cov.get("eligible")) if cov else False,
    }


def near_pairs(pairs, pts, tol):
    hits = []
    for p in pairs:
        for q in p["pts"]:
            if q is None:
                continue
            if any(pt is not None and pdist(q, pt) <= tol for pt in pts):
                hits.append(p)
                break
    return hits


def free_end_geometry(pt, same_lg, file_sheet, lg_segs, line_segs, unreg_sheet, texts, v2pts, gap_seg=None):
    """Classify what lies at a wire end point that has no identified port.

    Block lines (source_block_name set) are element or symbol geometry; other lines are sheet geometry (wires,
    terminal-strip rails, bus lines, frames). A line collinear with the observed gap segment is the wire itself and
    is ignored. Flags: blk_element (end on a block line), rail_T (end on a vertical sheet line >= 50 units),
    bus_T (end on another sheet line), unreg_pin (SYMB2 termpoint), text_near / text_near_numeric, v2_near, open.
    """
    info = {"blk_element": False, "rail_T": False, "bus_T": False, "unreg_pin": False, "text_near": False,
            "text_near_numeric": False, "v2_near": False, "open": False}
    gap_h = gap_v = None
    if gap_seg is not None:
        (x1, y1), (x2, y2) = gap_seg
        gap_h = abs(y1 - y2) <= 1e-6
        gap_v = abs(x1 - x2) <= 1e-6
    for (a, b, blk, length) in line_segs.get(file_sheet, []):
        if seg_point_dist(pt, a, b) > NEAR_LINE:
            continue
        if blk:
            info["blk_element"] = True
            continue
        horiz = abs(a[1] - b[1]) <= 1e-6
        vert = abs(a[0] - b[0]) <= 1e-6
        if gap_h and horiz and abs(a[1] - gap_seg[0][1]) <= NEAR_LINE:
            continue
        if gap_v and vert and abs(a[0] - gap_seg[0][0]) <= NEAR_LINE:
            continue
        if vert and length >= 50:
            info["rail_T"] = True
        info["bus_T"] = True
    for lgid, a, b, orient, length in lg_segs.get(file_sheet, []):
        if lgid == same_lg:
            continue
    for u in unreg_sheet.get(file_sheet, []):
        if pdist(pt, u[2]) <= 1.5:
            info["unreg_pin"] = True
    for (x, y), txt in texts.get(file_sheet, []):
        if abs(x - pt[0]) <= NEAR_TEXT and abs(y - pt[1]) <= NEAR_TEXT:
            info["text_near"] = True
            if txt.strip().isdigit():
                info["text_near_numeric"] = True
    for q in v2pts.get(file_sheet, []):
        if pdist(pt, q) <= NEAR_PORT:
            info["v2_near"] = True
            break
    info["open"] = not any(info[k] for k in ("blk_element", "rail_T", "bus_T", "unreg_pin"))
    return info


def make_row(pid, fam, gi, ev, port_by_id, cov_by_id, dil_ports, dil_elem, unreg_by_sheet, xcover, xcand,
             ptype, v2_pts, lg_segs, line_segs, texts_by, pairs_by_sheet, pairs_r25_by_sheet, counters):
    left = ev.get("left") or {}
    right = ev.get("right") or {}
    L = side_info(left, port_by_id, cov_by_id)
    R = side_info(right, port_by_id, cov_by_id)
    file_id = gi.get("file_id") or ev.get("file_id")
    sheet_id = gi.get("sheet_id") or ev.get("sheet_id")
    fs = (file_id, sheet_id)
    coords = ev.get("coords") or []
    if len(coords) == 4:
        e1 = (float(coords[0]), float(coords[1]))
        e2 = (float(coords[2]), float(coords[3]))
    else:
        e1 = e2 = None
    lgid = ev.get("line_group_id") or gi.get("line_group_id")
    # Device-internal verdict on the actual endpoint facts (same function the pair layer uses).
    # The device side is whichever side has category 装置端子; the other end is an internal element,
    # a coil, an unregistered pin (no port but a SYMB2 termpoint at the end), or something else.
    dev, oth = (L, R) if L["category"] == DEVICE else (R, L) if R["category"] == DEVICE else (None, None)
    verdict = "no_device_side"
    other_kind = "none"
    if dev is not None:
        if oth["port_id"]:
            other_kind = CAT_CODE.get(oth["category"], oth["category"] or "NOCAT")
            other_label = (oth["label"] or {}).get("normalized") or ""
            other_resolved = bool((oth["label"] or {}).get("resolved"))
            other_dict = {"category": oth["category"], "label": other_label, "label_resolved": other_resolved,
                          "identity": oth["identity"], "unregistered": False}
        else:
            other_kind = "UNREG_OR_NOPORT"
            # unregistered SYMB2 pin at the far end: take the label of the block whose termpoint sits at that end
            ends = [e for e in (e1, e2) if e is not None]
            best = None
            for u in unreg_by_sheet.get(fs, []):
                for e in ends:
                    d = pdist(e, u[2])
                    if d <= 1.5 and (best is None or d < best[0]):
                        best = (d, u)
            if best is not None:
                u = best[1]
                other_dict = {"category": "", "label": u[3] or "", "label_resolved": bool(u[4]), "identity": "",
                              "unregistered": True}
                other_kind = "UNREG_PIN"
            else:
                other_dict = {"category": "", "label": "", "label_resolved": False, "identity": "",
                              "unregistered": False}
        term = {"category": DEVICE, "identity": dev["identity"] or "", "label": (dev["label"] or {}).get("normalized") or "",
                "label_resolved": bool((dev["label"] or {}).get("resolved"))}
        verdict = device_internal_verdict(term, other_dict)
    # Free ends: wire endpoints of the observed segment that carry no identified port on the sides we have.
    free = []
    for side_name, side in (("L", L), ("R", R)):
        pass
    # Use geometric analysis at the two observed segment ends for unresolved sides.
    end_info = []
    for e in (e1, e2):
        if e is None:
            end_info.append(None)
            continue
        end_info.append(free_end_geometry(e, lgid, fs, lg_segs, line_segs, unreg_by_sheet, texts_by, v2_pts, gap_seg=(e1, e2) if e1 else None))
    # V1 closure evidence: any non-discard pair whose endpoint lies on this segment end.
    pts = [e1, e2] + [L["contact"], R["contact"]]
    pts = [tuple(float(v) for v in p) if p and p[0] is not None and p[1] is not None else None for p in pts]
    cur_pairs = pairs_by_sheet.get(fs, [])
    r25_pairs = pairs_r25_by_sheet.get(fs, [])
    ends_pts = [p for p in (e1, e2) if p is not None]
    cur_hit = [p for p in near_pairs(cur_pairs, ends_pts, 3.0) if p["status"] != "discard"]
    cur_hit_any = near_pairs(cur_pairs, ends_pts, 3.0)
    r25_hit = [p for p in near_pairs(r25_pairs, ends_pts, 3.0) if p["status"] != "discard"]
    v1_same_ident = [p for p in cur_hit if p["left_value"] in (L["identity"], R["identity"]) or p["right_value"] in (L["identity"], R["identity"])]
    seg = (e1, e2) if e1 is not None else None
    idents = [x for x in (L["identity"], R["identity"]) if x]
    cur_cov = [p for p in cur_pairs if covers_segment(seg, p["geom"])]
    cur_cov_nd = [p for p in cur_cov if p["status"] != "discard"]
    cur_cov_val = [p for p in cur_cov_nd if any(value_match(p["left_value"], i) or value_match(p["right_value"], i) for i in idents)]
    cur_cov_dev_discard = sum(1 for p in cur_cov if p["status"] == "discard" and p["discard_reason"] == "device_internal")
    r25_cov = [p for p in r25_pairs if covers_segment(seg, p["geom"])]
    r25_cov_nd = [p for p in r25_cov if p["status"] != "discard"]
    r25_cov_val = [p for p in r25_cov_nd if any(value_match(p["left_value"], i) or value_match(p["right_value"], i) for i in idents)]
    cov_extra = {
        "cur_cov_all": len(cur_cov), "cur_cov_nd": len(cur_cov_nd), "cur_cov_val": len(cur_cov_val),
        "cur_cov_pass": sum(1 for p in cur_cov_nd if p["status"] == "pass"),
        "cur_cov_dev_discard": cur_cov_dev_discard,
        "r25_cov_all": len(r25_cov), "r25_cov_nd": len(r25_cov_nd), "r25_cov_val": len(r25_cov_val),
        "r25_cov_pass": sum(1 for p in r25_cov_nd if p["status"] == "pass"),
        "cur_cov_kinds": "|".join(sorted({p["pair_kind"] or "" for p in cur_cov_nd})),
        "cur_cov_vals": "|".join(sorted({f'{p["left_value"]}~{p["right_value"]}' for p in cur_cov_nd}))[:300],
    }
    # V2 binding at an endpoint
    v2_at_end = any(pdist(e, q) <= NEAR_PORT for e in ends_pts for q in v2_pts.get(fs, []))
    v2_hits = [(pdist(e, (x, y)), txt, pid_) for e in ends_pts for (x, y, txt, pid_) in V2_INFO.get(fs, []) if pdist(e, (x, y)) <= 1.0]
    v2_val = sorted(v2_hits)[0][1] if v2_hits else None
    row = {
        "project": pid, "family": fam, "file_id": file_id, "sheet_id": sheet_id,
        "sheet_no": gi.get("sheet_no"), "filename": gi.get("filename"),
        "page_type": (ptype.get(fs) or ("", ""))[0], "sheet_category": (ptype.get(fs) or ("", ""))[1],
        "line_group_id": lgid, "state": ev.get("state") or gi.get("recognition_state"),
        "obs_reasons": "|".join(ev.get("reason_codes") or []),
        "res_reasons": "|".join(ev.get("resolution_reason_codes") or []),
        "n_obs": len(ev.get("resolution_observations") or [1]),
        "conflict_object_id": ev.get("conflict_object_id"),
        "left_cat": CAT_CODE.get(L["category"], L["category"] or "NONE"),
        "right_cat": CAT_CODE.get(R["category"], R["category"] or "NONE"),
        "left_has_port": bool(L["port_id"]), "right_has_port": bool(R["port_id"]),
        "left_identity": L["identity"], "right_identity": R["identity"],
        "left_label": (L["label"] or {}).get("normalized") or "", "right_label": (R["label"] or {}).get("normalized") or "",
        "left_label_resolved": bool((L["label"] or {}).get("resolved")), "right_label_resolved": bool((R["label"] or {}).get("resolved")),
        "left_reasons": "|".join(L["reason_codes"]), "right_reasons": "|".join(R["reason_codes"]),
        "left_cov_reasons": "|".join(L["cov_reason"]), "right_cov_reasons": "|".join(R["cov_reason"]),
        "left_cov_excluded_dev": L["cov_excluded_dev"], "right_cov_excluded_dev": R["cov_excluded_dev"],
        "left_cov_overruled": L["cov_overruled"], "right_cov_overruled": R["cov_overruled"],
        "left_in_dil": L["port_id"] in dil_ports, "right_in_dil": R["port_id"] in dil_ports,
        "left_dil_elem": L["port_id"] in dil_elem, "right_dil_elem": R["port_id"] in dil_elem,
        "device_side": "L" if L["category"] == DEVICE else ("R" if R["category"] == DEVICE else ""),
        "other_kind": other_kind, "dev_verdict": verdict,
        "left_xpage_cover": "|".join(f"{r}:{c}" for r, c in xcover.get(L["port_id"], [])),
        "right_xpage_cover": "|".join(f"{r}:{c}" for r, c in xcover.get(R["port_id"], [])),
        "left_xpage_cand": L["port_id"] in xcand, "right_xpage_cand": R["port_id"] in xcand,
        "cur_nd_near_ends": len(cur_hit), "cur_any_near_ends": len(cur_hit_any),
        "cur_nd_same_ident": len(v1_same_ident),
        "cur_nd_pass_near": sum(1 for p in cur_hit if p["status"] == "pass"),
        "r25_nd_near_ends": len(r25_hit), "r25_pass_near": sum(1 for p in r25_hit if p["status"] == "pass"),
        "v2_at_end": v2_at_end, "v2_end_value": v2_val or "", "v2_end_n": len(v2_hits),
        "end1_geo": json.dumps(end_info[0], ensure_ascii=False) if end_info[0] else "",
        "end2_geo": json.dumps(end_info[1], ensure_ascii=False) if end_info[1] else "",
        "coords": json.dumps(list(coords), ensure_ascii=False),
        "issue_id": gi.get("issue_id"), "left_port_id": L["port_id"], "right_port_id": R["port_id"],
        "left_contact_xy": json.dumps(L["contact"]) if L["contact"] else "",
        "right_contact_xy": json.dumps(R["contact"]) if R["contact"] else "",
        "left_port_number": str(L["port_number"] or ""), "right_port_number": str(R["port_number"] or ""),
        "left_symbol_id": L["symbol_id"] or "", "right_symbol_id": R["symbol_id"] or "",
        "left_wire_touched": L["wire_touched"], "right_wire_touched": R["wire_touched"],
    }
    row.update(cov_extra)
    return row


if __name__ == "__main__":
    main()
