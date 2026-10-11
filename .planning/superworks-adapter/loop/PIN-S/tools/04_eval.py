"""PIN-S step 4: evaluate geometric pin-text methods on metadata truth (holdout: links removed before matching).

Truth subsets (metadata links, never used by the methods):
  TX   : Pop-X symbols (no LD_SYMB2_SPECIAL) with LD_SYMB2_TERM_TEXT_n links, marker number n
  TP   : part-level markers (LDPARTLAYT_PART) with TERMPOINT 1005 -> text (definition_text_reference)
  TI   : internal-category markers (replay) with instance TERM_TEXT links (线圈/接插件)
  TS   : device-terminal markers (装置端子) with instance TERM_TEXT links (calibration only)
Methods:
  M1 anchor : TERMTEXTPOINT anchor whose 1005 link is this marker; the unique text whose insertion point lies
              within ANCHOR_R of the anchor centre.
  M2 nearest: nearest candidate text (model or block) to the marker segment; accepted when it is closer than
              the second nearest by a margin, within DMAX, and its value is pin-like.
  M2o/M2b   : M2 restricted to model-space texts / block-own texts.
Usage: python -X utf8 04_eval.py
"""
import collections, json, pickle, re, math
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
M = pickle.load(open(WORK / "markers.pkl", "rb"))["rows"]
INTERNAL = ("内部元件", "线圈", "接插件", "接地")
PIN_TOKEN = re.compile(r"[+\-]|\d{1,3}|[A-Za-z]{1,4}\d{1,3}|\d{1,2}[A-Za-z]\d{1,2}|\d{1,3}[A-Za-z]{1,2}")  # v2 token rule (see README)
ANCHOR_R = 4.0


def pin_like(v):
    return bool(v) and bool(PIN_TOKEN.fullmatch(v))


def subset(r):
    if r["truth"] is None:
        return None
    if not r["in_replay"]:
        return "TX"
    if r["replay_part"] if "replay_part" in r else False:
        return "TP"
    if r["truth_src"] == "definition_text_reference_block":
        return "TP"
    if r["replay_category"] in ("线圈", "接插件", "内部元件", "接地"):
        return "TI"
    return "TS"


def m2(r, dmax=3.0, margin_k=0.25, src=None, owned=False):
    cands = [c for c in r["cands"] if (src is None or c[0] == src)]
    if not cands:
        return None
    c0 = cands[0]
    if c0[7] > dmax:
        return None
    if len(cands) > 1:
        c1 = cands[1]
        if c1[7] - c0[7] < max(0.25, margin_k * (c0[6] or 0)):
            return None
    if owned and c0[10] not in (0, None):
        return None
    if not pin_like(c0[3]):
        return None
    return c0[3]


def m1(r, anchor_r=ANCHOR_R, margin=0.5):
    if not r["anchors"]:
        return None
    best = None
    for h, cx, cy in r["anchors"]:
        near = sorted(((math.hypot(c[4] - cx, c[5] - cy), c) for c in r["cands"]), key=lambda t: t[0])
        near = [t for t in near if t[0] <= anchor_r]
        if not near:
            continue
        if len(near) > 1 and near[1][0] - near[0][0] < margin:
            continue
        cand = near[0][1]
        if pin_like(cand[3]):
            best = cand[3]
            break
    return best


def score(rows, fn):
    n = len(rows); res = 0; ok = 0
    for r in rows:
        v = fn(r)
        if v is None:
            continue
        res += 1
        if norm(v) == norm(r["truth"]):
            ok += 1
    return {"n": n, "resolved": res, "correct": ok, "precision": round(ok / res, 4) if res else None,
            "coverage": round(res / n, 4) if n else None}


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


if __name__ == "__main__":
    S = collections.defaultdict(list)
    for r in M:
        s = subset(r)
        if s:
            S[s].append(r)
    print({k: len(v) for k, v in S.items()})
    out = {}
    for s in ("TX", "TP", "TI", "TS"):
        rows = S[s]
        anc = [r for r in rows if r["anchors"]]
        out[s] = {"n": len(rows), "anchor_rows": len(anc),
                  "M1": score(anc, m1) if anc else None,
                  "M2_dmax3": score(rows, lambda r: m2(r, 3.0)),
                  "M2_dmax3_owned": score(rows, lambda r: m2(r, 3.0, owned=True)),
                  "M2_model": score(rows, lambda r: m2(r, 3.0, src="model")),
                  "M2_block": score(rows, lambda r: m2(r, 3.0, src="block")),
                  "M2_dmax2": score(rows, lambda r: m2(r, 2.0)),
                  "M2_dmax5": score(rows, lambda r: m2(r, 5.0)),
                  "truth_in_cands": round(sum(1 for r in rows if any(norm(c[3]) == norm(r["truth"]) for c in r["cands"])) / max(1, len(rows)), 4)}
        print(s, json.dumps(out[s], ensure_ascii=False))
    json.dump(out, open(WORK / "eval_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
