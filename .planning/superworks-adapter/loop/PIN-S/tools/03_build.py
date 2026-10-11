"""PIN-S step 3: join round18 replay ports with DXF geometry and build the marker table.

Inputs : .tmp/pin_s_work/all18.pkl (01_load18), .tmp/pin_s_work/geom/*.pkl (02_geom)
Outputs: .tmp/pin_s_work/markers.pkl
  markers : one row per TERMPOINT marker of every symbol INSERT in the corpus
            (Pop-S = replay internal port without identity; 'linked' = metadata gives a truth text)
Usage: python -X utf8 03_build.py
"""
import glob
import pickle
import re
import collections
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_s_work")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
INTERNAL = ("内部元件", "线圈", "接插件", "接地")
TERMINAL = ("端子", "装置端子")


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def label_prefix(v):
    """Device letters of a label: '1ZKK3' -> 'ZKK', '1-21QD2' -> 'QD', '1n' -> 'N'."""
    m = re.fullmatch(r"[0-9\-~]*([A-Za-z]+)[0-9\-~]*", str(v or ""))
    return m.group(1).upper() if m else ""


# ---- replay ports indexed by (pid, fid, instance_path, marker_handle)
rp = {}
for p in T["ports"]:
    rp[(p["pid"], p["file_id"], p["instance_path"], p["marker_handle"])] = p
for part in T["parts"]:
    for q in part["ports"]:
        rp[(part["pid"], q["file_id"], q["instance_path"], q["marker_handle"])] = dict(q, _part=True, pid=part["pid"])

# ---- wire index: all contacts on each wire handle within a file (any port, any category)
wire_contacts = collections.defaultdict(list)
for key, p in rp.items():
    for c in p.get("wire_contacts") or []:
        wire_contacts[(key[0], key[1], c.get("wire_handle"))].append(key)

# ---- geometry
geo = {}
texts_model = {}
mk_rows = []
for fn in sorted(glob.glob(str(WORK / "geom" / "*.pkl"))):
    g = pickle.load(open(fn, "rb"))
    if g.get("error"):
        print("geom error", fn, g["error"][:120])
        continue
    pid, fid = g["pid"], g["fid"]
    mt = {h: (v, x, y, ht, rot, layer) for (h, v, x, y, ht, rot, layer) in g["model_texts"]}
    texts_model[(pid, fid)] = mt
    for s in g["symbols"]:
        own = {t["h"]: t for t in s["own_texts"]}
        anchors_by_link = collections.defaultdict(list)
        for a in s["anchors"]:
            if a.get("link"):
                anchors_by_link[a["link"]].append(a)
        for m in s["markers"]:
            key = (pid, fid, m["instance"], m["marker"])
            port = rp.get(key)
            # replay identity for this marker
            tl = None
            if s["term_links"] and m["number"] in s["term_links"]:
                tl = s["term_links"][m["number"]]
            truth_text, truth_src = None, None
            # (1) instance TERM_TEXT_n link: keyed by the marker number
            if tl:
                if tl in own:
                    truth_text, truth_src = own[tl]["v"], "instance_term_text_block"
                elif tl in mt:
                    truth_text, truth_src = mt[tl][0], "instance_term_text_model"
            # (2) TERMPOINT 1005 link inside the library definition
            if truth_text is None and m.get("tp_link"):
                h = m["tp_link"]
                if h in own:
                    truth_text, truth_src = own[h]["v"], "definition_text_reference_block"
                elif h in mt:
                    truth_text, truth_src = mt[h][0], "definition_text_reference_model"
            cands = []
            for c in m["cands"]:
                cands.append((c["src"], c.get("kind"), c["h"], c["v"], c["x"], c["y"], c["ht"], c["dist"], c["u"], c["w"],
                              c.get("rank_marker"), c.get("n_markers_within"), c.get("second_marker_dist"), c.get("layer")))
            anc = anchors_by_link.get(m["marker"], [])
            row = {
                "pid": pid, "fid": fid, "instance": m["instance"], "insert": m["insert"], "block": m["block"],
                "category_sw": s["category"] or "", "label_h": s["label_h"], "marker": m["marker"],
                "number": m["number"] or "", "tp_link": m.get("tp_link"), "termautodim": m.get("termautodim"),
                "ax": m["ax"], "ay": m["ay"], "bx": m["bx"], "by": m["by"], "L": m["L"], "ang": m["ang"],
                "mid": m["mid"], "anchors": [(a["anchor"], a["cx"], a["cy"]) for a in anc],
                "term_link_for_number": tl, "truth": truth_text, "truth_src": truth_src,
                "cands": cands, "ix": s["ix"], "iy": s["iy"],
                "in_replay": port is not None,
                "replay_category": port["category"] if port else None,
                "replay_identity": port.get("endpoint_identity") if port else None,
                "replay_pin_resolved": bool((port or {}).get("pin", {}).get("resolved")) if port else None,
                "replay_pin_method": ((port or {}).get("pin") or {}).get("resolution_method") if port else None,
                "replay_label": ((port or {}).get("label") or {}).get("normalized") if port else None,
                "replay_wire": sorted({c.get("wire_handle") for c in ((port or {}).get("wire_contacts") or [])}) if port else [],
                "replay_part": bool(port and port.get("_part")),
                "xdata_apps": s["xdata_apps"],
                "wire_contacts_n": len((port or {}).get("wire_contacts") or []) if port else 0,
                "label_text_key": port.get("label", {}).get("normalized") if port else None,
            }
            mk_rows.append(row)
    print("loaded", fid, pid, len(mk_rows), flush=True) if len(mk_rows) % 5000 < 3 else None

# ---- wire other-end classification for replay ports
def other_end(row):
    """For a marker's wire(s): identity class of the other contact(s) on the same wire handle."""
    if not row["replay_wire"]:
        return "no_wire"
    classes = []
    for w in row["replay_wire"]:
        others = [k for k in wire_contacts.get((row["pid"], row["fid"], w), [])
                  if not (k[2] == row["instance"] and k[3] == row["marker"])]
        if not others:
            classes.append("wire_no_other_contact")
            continue
        for k in others:
            q = rp[k]
            cat = q["category"]
            ident = q.get("endpoint_identity")
            if cat in TERMINAL and ident:
                classes.append("other_terminal_identified")
            elif cat in TERMINAL:
                classes.append("other_terminal_unidentified")
            elif cat in INTERNAL and ident:
                classes.append("other_internal_identified")
            elif cat in INTERNAL:
                classes.append("other_internal_unidentified")
            else:
                classes.append("other_" + (cat or "part"))
    order = ["other_terminal_identified", "other_internal_identified", "other_terminal_unidentified",
             "other_internal_unidentified", "wire_no_other_contact"]
    for o in order:
        if o in classes:
            return o
    return classes[0]

for row in mk_rows:
    row["other_end"] = other_end(row) if row["in_replay"] else None
    row["label_prefix"] = label_prefix(row["replay_label"] or "")

pickle.dump({"rows": mk_rows, "texts_model": texts_model, "n_rows": len(mk_rows)}, open(WORK / "markers.pkl", "wb"))
print("markers", len(mk_rows), "in replay", sum(r["in_replay"] for r in mk_rows), "truth", sum(r["truth"] is not None for r in mk_rows))
