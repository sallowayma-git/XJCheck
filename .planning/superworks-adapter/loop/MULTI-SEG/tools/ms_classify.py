"""MULTI-SEG: classify the 870 split candidates refused as components_not_two (read-only).

For each refused candidate (one device-terminal pair across one line group that has three or more end-point pieces)
the script records:
  - the pieces of the group (ordered along the axis: extent, length, raw segment count, end contacts);
  - every gap between consecutive pieces: width, what fills it (texts with their value and whether the value is the
    device terminal tail, connect dots, TERMPOINTs of ports, model lines crossing it, unregistered block pins), and
    whether the gap is the candidate's own terminal body (its two contacts) or another terminal body;
  - the object touching each outer end of the group and each inner piece end (port category, unregistered pin, dot,
    text, non-member model line as a corner or a T, or blank).
Output: .tmp/multiseg_work/cls870.json (one record per candidate), printed counts. No src file is touched.
Usage: python ms_classify.py [ROUND_ROOT] [OUT_JSON]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ms_common as M  # noqa: E402
import ms_geom as G  # noqa: E402

DI = M.DI
OUT_DEFAULT = M.ROOT / ".tmp" / "multiseg_work" / "cls870.json"


def tail_of(identity: str, label: str) -> str:
    if identity and label and identity.casefold().startswith(label.casefold()) and len(identity) > len(label):
        return identity[len(label):]
    return ""


def classify_text(t, tail, label):
    value = M.text(t.get("text"))
    norm = M.text(t.get("normalized_text")) or value
    if value.isdigit() and tail and value == tail:
        return "tail"
    if M.text(t.get("is_numeric_candidate")).lower() in ("true", "1") or bool(t.get("is_numeric_candidate")):
        if value.isdigit():
            return "num"
        return "numtext"
    if label and norm.casefold().startswith(label.casefold()):
        return "label"
    return "text"


def end_tokens(geo, fid, point, member_ids, contacts_near):
    tokens = []
    ports = geo.ports_at(fid, point)
    for port in ports:
        tokens.append("port:" + M.text(port.get("category")))
    for port, c in contacts_near:
        tokens.append("contact:" + M.text(port.get("category")))
    for block, number in geo.pins_at(fid, point):
        tokens.append("unreg_pin")
    if geo.dots_in_rect(fid, point[0] - G.DOT_TOL, point[0] + G.DOT_TOL, point[1] - G.DOT_TOL, point[1] + G.DOT_TOL):
        tokens.append("dot")
    ends, through = geo.model_touching(fid, point, member_ids)
    if ends:
        tokens.append("corner" if len(ends) == 1 and not through else "branch")
    if through:
        tokens.append("T")
    if not tokens:
        tokens.append("blank")
    return sorted(set(tokens))


def contacts_at(proj_ports_by_file, fid, point, tol=0.3):
    out = []
    for port in proj_ports_by_file.get(fid, ()):
        for c in DI._contacts_of(port):
            x, y = DI._number(c.get("x")), DI._number(c.get("y"))
            if x is None or y is None:
                continue
            if abs(x - point[0]) <= tol and abs(y - point[1]) <= tol:
                out.append((port, c))
                break
    return out


def piece_index_of(pieces, x):
    """Index of the piece whose x-extent holds x (with a 0.05 tolerance), or None."""
    for i, p in enumerate(pieces):
        if p["xmin"] - 0.05 <= x <= p["xmax"] + 0.05:
            return i
    return None


def gap_is_candidate(i, pieces, cand) -> bool:
    """True when the candidate's two contacts lie on the two pieces that border gap i."""
    ia, ib = piece_index_of(pieces, cand["ca"][0]), piece_index_of(pieces, cand["cb"][0])
    return ia is not None and ib is not None and {ia, ib} == {i, i + 1}


def analyse_project(proj, geo, cands, groups, roots, segments):
    recs = []
    ports_by_file = defaultdict(list)
    for port in proj.ports:
        ports_by_file[M.text(port["file_id"])].append(port)
    for c in cands:
        if c["reason"] != "components_not_two":
            continue
        keys = c["keys"]
        fid = c["file_id"]
        group = groups[c["group_index"]][0]
        member_ids = {k[1] for k in keys}
        pieces = G.piece_extents(keys, segments, c["roots"])
        ys = [segments[k]["sy"] for k in keys] + [segments[k]["ey"] for k in keys]
        y = sum(ys) / len(ys)
        yspread = max(ys) - min(ys)
        label = M.text(M.jload(c["port_a"].get("label"), {}).get("normalized"))
        identity = M.text(c["port_a"].get("endpoint_identity"))
        tail = tail_of(identity, label)
        # gaps between consecutive pieces
        gaps = []
        for i in range(len(pieces) - 1):
            left, right = pieces[i], pieces[i + 1]
            x0, x1 = left["xmax"], right["xmin"]
            width = x1 - x0
            rect = (x0 - 0.6, x1 + 0.6, y - G.CROSS_TOL, y + G.CROSS_TOL)
            tx = geo.texts_in_rect(fid, *rect)
            text_kinds = [{"value": M.text(t.get("text")), "kind": classify_text(t, tail, label),
                           "bbox": [float(t["bbox_min_x"]), float(t["bbox_min_y"]), float(t["bbox_max_x"]), float(t["bbox_max_y"])]}
                          for t in tx]
            dots = geo.dots_in_rect(fid, x0 - 0.6, x1 + 0.6, y - G.CROSS_TOL, y + G.CROSS_TOL)
            termpoints = []
            for port, (ax, ay, bx, by) in geo.ports_by_file.get(fid, ()):
                mx, my = (ax + bx) / 2, (ay + by) / 2
                if x0 - 0.6 <= mx <= x1 + 0.6 and abs(my - y) <= G.CROSS_TOL:
                    termpoints.append({"record_id": M.text(port.get("record_id")), "category": M.text(port.get("category")),
                                       "identity": M.text(port.get("endpoint_identity")),
                                       "insert": M.text(port.get("insert_handle"))})
            crossing = [l["line_id"] for l in geo.model_by_file.get(fid, ())
                        if l["line_id"] not in member_ids
                        and DI._segment_distance((x0 + 0.05, y), (x1 - 0.05, y),
                                                 (l["sx"], l["sy"]), (l["ex"], l["ey"])) <= 0.02]
            gaps.append({"index": i, "x0": x0, "x1": x1, "width": round(width, 4), "dots": len(dots),
                         "texts": text_kinds, "termpoints": termpoints, "crossing_lines": crossing,
                         "is_candidate_gap": gap_is_candidate(i, pieces, c)})
        # ends: outer ends of the whole group, and inner piece ends
        outer_left = pieces[0]
        outer_right = pieces[-1]
        ends = {}
        ends["outer_left"] = end_tokens(geo, fid, (outer_left["xmin"], outer_left["y"]), member_ids,
                                        contacts_at(ports_by_file, fid, (outer_left["xmin"], outer_left["y"])))
        ends["outer_right"] = end_tokens(geo, fid, (outer_right["xmax"], outer_right["y"]), member_ids,
                                         contacts_at(ports_by_file, fid, (outer_right["xmax"], outer_right["y"])))
        pieces_out = []
        for i, p in enumerate(pieces):
            pieces_out.append({"index": i, "xmin": round(p["xmin"], 4), "xmax": round(p["xmax"], 4),
                               "n_lines": len(p["keys"]), "y": round(p["y"], 4),
                               "yspread": round(p["yspread"], 4)})
        recs.append({"pid": proj.pid, "file_id": fid, "sheet_id": c["sheet_id"], "line_group_id": c["line_group_id"],
                     "orientation": c["orientation"], "identity": identity, "label": label, "tail": tail,
                     "port_a": M.text(c["port_a"]["record_id"]), "port_b": M.text(c["port_b"]["record_id"]),
                     "insert": M.text(c["port_a"]["insert_handle"]),
                     "category_a": M.text(c["port_a"]["category"]), "category_b": M.text(c["port_b"]["category"]),
                     "n_pieces": len(pieces), "n_lines": len(keys), "pieces": pieces_out, "gaps": gaps,
                     "ends": ends, "y": round(y, 4), "yspread": round(yspread, 4),
                     "handle_a": c["handle_a"], "handle_b": c["handle_b"],
                     "ca": list(c["ca"]), "cb": list(c["cb"])})
    return recs


def main(round_root: Path, out_path: Path):
    all_recs = []
    for proj in M.load_all(round_root):
        cands, groups, roots, segments, model, dots = M.enumerate_split_candidates(proj)
        geo = G.Geo(proj)
        all_recs.extend(analyse_project(proj, geo, cands, groups, roots, segments))
        print("done", proj.pid, len(all_recs), flush=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_recs, ensure_ascii=False, indent=1), encoding="utf-8")
    print("records", len(all_recs))


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else M.ROUND
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT_DEFAULT
    main(root, out)
