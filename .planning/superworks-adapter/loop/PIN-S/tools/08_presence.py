"""PIN-S step 8: presence of pin-number-like model-space text around each marker, out to 25 drawing units.
Pin-like = digits (1-3) or 1-2 letters + digits (1-3) or digits + 1-2 letters (strict; see 04_eval).
Compares Pop-S (no identity) with metadata truth rows (Pop-X components, internal metadata, part definitions).
Usage: python -X utf8 08_presence.py"""
import collections, json, math, pickle, re
from pathlib import Path
import numpy as np

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
OUTD = WORK / "classify"
MK = pickle.load(open(WORK / "markers.pkl", "rb"))
M, TM = MK["rows"], MK["texts_model"]
INTERNAL = ("内部元件", "线圈", "接插件", "接地")
STRICT = re.compile(r"[+\-]|\d{1,3}|[A-Za-z]{1,4}\d{1,3}|\d{1,2}[A-Za-z]\d{1,2}|\d{1,3}[A-Za-z]{1,2}")  # v2 token rule (see README)
RMAX = 25.0
BINS = [1.5, 3, 6, 9, 12, 25]

def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 <= 1e-18:
        return np.hypot(px - ax, py - ay)
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
    return np.hypot(px - (ax + t * dx), py - (ay + t * dy))

by_file = collections.defaultdict(list)
for r in M:
    by_file[(r["pid"], r["fid"])].append(r)

def classify_presence(group_rows):
    """Return per row: nearest strict pin-like model text distance (<=RMAX) and its value."""
    out = {}
    for key, rows in group_rows.items():
        texts = TM.get(key, {})
        if not texts:
            for r in rows:
                out[id(r)] = (None, None)
            continue
        items = [(h, v, x, y) for h, (v, x, y, ht, rot, layer) in texts.items() if STRICT.fullmatch(re.sub(r"\s+", "", v))]
        if not items:
            for r in rows:
                out[id(r)] = (None, None)
            continue
        X = np.array([t[2] for t in items]); Y = np.array([t[3] for t in items])
        for r in rows:
            d = seg_dist(X, Y, r["ax"], r["ay"], r["bx"], r["by"])
            i = int(np.argmin(d))
            out[id(r)] = (float(d[i]) if d[i] <= RMAX else None, items[i][1] if d[i] <= RMAX else None)
    return out

if __name__ == "__main__":
    pops = [r for r in M if r["in_replay"] and r["replay_category"] in INTERNAL and not r["replay_identity"] and not r["replay_part"]]
    truth_tx = [r for r in M if r["truth"] is not None and not r["in_replay"]]
    truth_tp = [r for r in M if r["truth"] is not None and r["in_replay"] and (r["replay_part"] or r["truth_src"] == "definition_text_reference_block")]
    truth_ti = [r for r in M if r["truth"] is not None and r["in_replay"] and r["replay_category"] in ("线圈", "接插件")]
    res = {}
    for name, rows in (("PopS", pops), ("TX_truth", truth_tx), ("TP_truth", truth_tp), ("TI_truth", truth_ti)):
        g = collections.defaultdict(list)
        for r in rows:
            g[(r["pid"], r["fid"])].append(r)
        pres = classify_presence(g)
        dists = [pres[id(r)][0] for r in rows if pres[id(r)][0] is not None]
        hist = collections.Counter()
        for d in dists:
            hist[next(b for b in BINS if d <= b)] += 1
        res[name] = {"n": len(rows), "pin_like_within_25": len(dists),
                     "bins_cum": {f"<= {b}": sum(1 for d in dists if d <= b) for b in BINS},
                     "exact_truth_match_nearest": None}
        if name != "PopS":
            hit = 0
            for r in rows:
                pass
        print(name, res[name], flush=True)
        if name == "PopS":
            pop_pres = pres
            pop_rows = rows
    # per block family presence within 6 for Pop-S
    fam = collections.defaultdict(lambda: [0, 0])
    for r in pops:
        d = pop_pres[id(r)][0]
        fam[r["block"]][0] += 1
        if d is not None and d <= 6:
            fam[r["block"]][1] += 1
    res["PopS_family_presence_le6"] = {b: {"n": v[0], "with_pin_like_le6": v[1], "rate": round(v[1] / v[0], 3)} for b, v in sorted(fam.items(), key=lambda t: -t[1][0])}
    json.dump(res, open(OUTD / "presence_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved")
