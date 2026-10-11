"""MULTI-SEG: final gap and end classes for the 870 refused candidates (read-only).

Reads .tmp/multiseg_work/cls870.json (ms_classify.py) and the replay tables; writes sig870.json with, per candidate:
  gaps: one class per gap between pieces, in axis order
  ends: one class per outer end
Gap classes (measured, no names or handles used):
  BODY       the candidate's own terminal body (its two contacts across the gap)
  UNREG2     an unregistered SYMB2 block whose two TERMPOINTs sit at the gap ends (a registered-less 2-pin symbol)
  SWELEM     a SuperWORKS internal element or coil port (TERMPOINT) at a gap end or inside the gap
  DEVBODY    another SuperWORKS device terminal TERMPOINT in the gap, no element port
  FRAME      a model-space line crosses the gap, with no port and no unregistered pin (device frame or wire)
  LBL        texts only in the gap (wire or cable label, no symbol)
  DOT        a connect dot in the gap, nothing else
  EMPTY      nothing in the gap
End classes: TERM (plain terminal 端子), ELEM (SW internal element), UNREG (unregistered pin), DEVTERM (device
terminal port that is not the candidate pair), BRANCH (T: a model line ends on it and another passes through),
CORNER (a model line ends on it), DOT, BLANK.
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

WORK = M.ROOT / ".tmp" / "multiseg_work"
ELEM_CATS = {"内部元件", "线圈"}


def near(p, q, tol=0.6):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def unreg_span(proj, fid, x0, x1, y):
    for b in proj.unreg:
        if M.text(b["file_id"]) != fid:
            continue
        left = right = False
        for tp in M.jload(b.get("termpoints"), []):
            for p in (tp["a"], tp["b"]):
                if abs(p[1] - y) <= 0.6:
                    left = left or abs(p[0] - x0) <= 0.6
                    right = right or abs(p[0] - x1) <= 0.6
        if left and right:
            return True
    return False


def unreg_at_end(proj, fid, x, y):
    for b in proj.unreg:
        if M.text(b["file_id"]) != fid:
            continue
        for tp in M.jload(b.get("termpoints"), []):
            for p in (tp["a"], tp["b"]):
                if near(p, (x, y)):
                    return True
    return False


def gap_class(rec_gap, proj, fid, y, x0, x1, candidate):
    if candidate:
        return "BODY"
    if unreg_span(proj, fid, x0, x1, y):
        return "UNREG2"
    cats = {t["category"] for t in rec_gap["termpoints"]}
    if cats & ELEM_CATS:
        return "SWELEM"
    if cats:
        return "DEVBODY"
    if rec_gap["crossing_lines"]:
        return "FRAME"
    if rec_gap["texts"]:
        return "LBL"
    if rec_gap["dots"]:
        return "DOT"
    return "EMPTY"


def end_class(tokens, proj, fid, x, y):
    t = set(tokens)
    if "port:端子" in t or "contact:端子" in t:
        return "TERM"
    if t & {"port:内部元件", "contact:内部元件", "port:线圈", "contact:线圈"}:
        return "ELEM"
    if "unreg_pin" in t or unreg_at_end(proj, fid, x, y):
        return "UNREG"
    if "port:装置端子" in t or "contact:装置端子" in t:
        return "DEVTERM"
    if "T" in t:
        return "BRANCH"
    if "branch" in t:
        return "BRANCH"
    if "corner" in t:
        return "CORNER"
    if "dot" in t:
        return "DOT"
    return "BLANK"


def main():
    cls = json.loads((WORK / "cls870.json").read_text(encoding="utf-8"))
    by_pid = defaultdict(list)
    for i, r in enumerate(cls):
        by_pid[r["pid"]].append((i, r))
    out = [None] * len(cls)
    for pid, items in by_pid.items():
        proj = M.Project(pid, next((M.ROUND / pid).glob("*/findings")))
        for i, r in items:
            fid = r["file_id"]
            gaps = []
            for g in r["gaps"]:
                gaps.append(gap_class(g, proj, fid, r["y"], g["x0"], g["x1"], g["is_candidate_gap"]))
            left = end_class(r["ends"]["outer_left"], proj, fid, r["pieces"][0]["xmin"], r["y"])
            right = end_class(r["ends"]["outer_right"], proj, fid, r["pieces"][-1]["xmax"], r["y"])
            sig = "%s|%s|%s" % (left, "-".join(gaps), right)
            out[i] = {"index": i, "pid": pid, "file_id": fid, "sheet_id": r["sheet_id"],
                      "line_group_id": r["line_group_id"], "identity": r["identity"], "tail": r["tail"],
                      "port_a": r["port_a"], "port_b": r["port_b"], "n_pieces": r["n_pieces"],
                      "n_lines": r["n_lines"], "orientation": r["orientation"], "y": r["y"],
                      "left": left, "gaps": gaps, "right": right, "signature": sig,
                      "pieces": [(p["xmin"], p["xmax"]) for p in r["pieces"]],
                      "ca": r["ca"], "cb": r["cb"]}
        print("done", pid, flush=True)
    (WORK / "sig870.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    sig = Counter(o["signature"] for o in out)
    print("signatures", len(sig))
    for k, v in sig.most_common(40):
        print(v, k)
    gc = Counter(g for o in out for g in o["gaps"] if g != "BODY")
    print("non-body gap classes", dict(gc))
    print("ends left", dict(Counter(o["left"] for o in out)), "right", dict(Counter(o["right"] for o in out)))


if __name__ == "__main__":
    main()
