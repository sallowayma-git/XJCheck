"""PIN-S step 5: classify Pop-S markers by the form of their pin-text evidence, and estimate each class's
precision on metadata truth (the same classifier is applied to the truth rows with their links removed).

Classes (first match wins; A is checked first when the marker has a TERMTEXTPOINT anchor):
  A_anchor_ok        anchor-linked, unique text near the anchor, pin-like         (M1)
  B_model_owned      nearest model text within DMAX, unique, pin-like, owned by this marker
  C_contested        nearest model text is closer to / equidistant with another marker
  D_text_tie         two model texts equally near this marker
  E_nonpin_nearest   nearest model text is not pin-like (device name, unit, etc.)
  F_block_only       no model text within DMAX; only own-block text within DMAX
  H_far_only         texts exist only beyond DMAX
  G_none             no text at all within the candidate radius
Usage: python -X utf8 05_classify.py
"""
import collections, json, math, pickle, re
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
OUTD = Path("F:/workspace/XJToolkit/.tmp/pin_s_work/classify")
OUTD.mkdir(parents=True, exist_ok=True)
M = pickle.load(open(WORK / "markers.pkl", "rb"))["rows"]
INTERNAL = ("内部元件", "线圈", "接插件", "接地")
DMAX = 3.0
ANCHOR_R = 4.0
PIN_TOKEN = re.compile(r"\d{1,3}|[A-Za-z]{1,2}\d{1,3}|\d{1,3}[A-Za-z]{1,2}")  # strict: digits, 1-2 letters + digits


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def pin_like(v):
    return bool(v) and bool(PIN_TOKEN.fullmatch(v))


def anchor_pick(r):
    if not r["anchors"]:
        return None
    for _h, cx, cy in r["anchors"]:
        near = sorted(((math.hypot(c[4] - cx, c[5] - cy), c) for c in r["cands"]), key=lambda t: t[0])
        near = [t for t in near if t[0] <= ANCHOR_R]
        if not near:
            continue
        if len(near) > 1 and near[1][0] - near[0][0] < 0.5:
            continue
        if pin_like(near[0][1][3]):
            return near[0][1]
    return None


def classify(r):
    """Return (class, candidate used or None)."""
    a = anchor_pick(r)
    if a is not None:
        return "A_anchor_ok", a
    model = [c for c in r["cands"] if c[0] == "model" and c[7] <= DMAX]
    block = [c for c in r["cands"] if c[0] == "block" and c[7] <= DMAX]
    if not model:
        if block:
            return "F_block_only", block[0]
        if r["cands"]:
            return "H_far_only", None
        return "G_none", None
    c0 = model[0]
    if not pin_like(c0[3]):
        return "E_nonpin_nearest", c0
    if len(model) > 1 and model[1][7] - c0[7] < max(0.25, 0.25 * (c0[6] or 0)):
        return "D_text_tie", c0
    if c0[10] not in (0, None):
        return "C_contested", c0
    if c0[12] is not None and c0[12] - c0[7] < 0.25:
        return "C_contested", c0
    return "B_model_owned", c0


def position_bucket(c, r):
    """Position of the chosen text in marker-local frame: along-pin (u) and across (w)."""
    L = r["L"] or 1.0
    u = c[8] / L
    w = c[9]
    along = "beyond_tip" if u > 0.5 + 0.25 else ("beyond_root" if u < -0.5 - 0.25 else "over_pin")
    side = "left_of_pin" if w > 0.5 else ("right_of_pin" if w < -0.5 else "on_axis")
    return along, side


if __name__ == "__main__":
    pops = [r for r in M if r["in_replay"] and r["replay_category"] in INTERNAL and not r["replay_identity"] and not r["replay_part"]]
    res = {"n_popS": len(pops)}
    cls_count = collections.Counter()
    cls_by_block = collections.defaultdict(collections.Counter)
    cls_by_label = collections.defaultdict(collections.Counter)
    pos = collections.defaultdict(collections.Counter)
    anchor_stats = collections.Counter()
    for r in pops:
        k, c = classify(r)
        cls_count[k] += 1
        cls_by_block[r["block"]][k] += 1
        cls_by_label[r["label_prefix"] or "(none)"][k] += 1
        if c is not None and k in ("B_model_owned", "A_anchor_ok"):
            pos[k]["|".join(position_bucket(c, r))] += 1
        anchor_stats[("anchor" if r["anchors"] else "no_anchor", "tl_resolved" if r["truth"] is not None else ("tl_dangling" if r["term_link_for_number"] is not None else "no_tl"))] += 1
    res["classes"] = cls_count.most_common()
    res["anchor_tl"] = {f"{a}|{b}": n for (a, b), n in anchor_stats.items()}
    res["positions"] = {k: dict(v) for k, v in pos.items()}
    res["by_block"] = {b: dict(v) for b, v in sorted(cls_by_block.items(), key=lambda t: -sum(t[1].values()))}
    res["by_label_prefix"] = {b: dict(v) for b, v in sorted(cls_by_label.items(), key=lambda t: -sum(t[1].values()))[:40]}

    # class precision on truth rows (links removed before classification; value compared with truth)
    truth_rows = collections.defaultdict(list)
    for r in M:
        if r["truth"] is None:
            continue
        if not r["in_replay"]:
            truth_rows["TX_popX_component"].append(r)
        elif r["replay_part"] or r["truth_src"] == "definition_text_reference_block":
            truth_rows["TP_part_definition"].append(r)
        elif r["replay_category"] in INTERNAL:
            truth_rows["TI_internal_metadata"].append(r)
        else:
            truth_rows["TS_device_terminal"].append(r)
    prec = {}
    for name, rows in truth_rows.items():
        table = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            k, c = classify(r)
            table[k][0] += 1
            if c is not None and norm(c[3]) == norm(r["truth"]):
                table[k][1] += 1
        prec[name] = {k: {"n": v[0], "correct": v[1], "precision": round(v[1] / v[0], 4) if v[0] else None}
                      for k, v in sorted(table.items())}
    res["truth_class_precision"] = prec
    json.dump(res, open(OUTD / "classify_summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Pop-S", res["n_popS"])
    for k, n in res["classes"]:
        print(f"  {k:20s} {n}")
    print("anchor|tl", res["anchor_tl"])
    print("positions", res["positions"])
    for name, t in prec.items():
        print(name, {k: (v["n"], v["precision"]) for k, v in t.items()})
