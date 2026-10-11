"""PIN-M5 step 2: match schematic pins to layout PCL logical pins through the same-label part and the
far terminal identity (read-only, round18 replay tables).

Schematic pin P (label L, wire other-end terminal identity set T_P) is matched to logical pin k of a layout
part labelled L when some PCL record of that part has a FAR identity (sw_port) in T_P.
P gets identity L-k only when exactly one k matches (over all copies of the part in the project).

Populations
  TX  Pop-X: LOGGEN PART2 ends with empty SW category, status resolved_by_symb2_text or insert_not_sw.
              Truth = record sequence / slot text (display pin number).
  TI  SW coil / connector ports with resolved pin text (LD_SYMB2_TERM_TEXT_n). Truth = pin text.
  PS  Pop-S: SW internal ports (内部元件/线圈/接插件/接地) without identity. No truth.

Output: .tmp/pin_m5_work/m5_pins.pkl (one row per schematic pin) and a printed summary.
Usage: python -X utf8 02_m5_match.py
"""
import pickle, re, collections, json
from pathlib import Path

WORK = Path("F:/workspace/XJToolkit/.tmp/pin_m5_work")
D = pickle.load(open(WORK / "all18.pkl", "rb"))
T = D["tables"]
INTERNAL = ("内部元件", "线圈", "接插件", "接地")
TERMINAL = ("端子", "装置端子")


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).upper()


def key_id(s):
    """Identity key for comparison: uppercase, no spaces, dashes or underscores."""
    return re.sub(r"[\s\-_~]", "", str(s or "")).upper()


def pn(s):
    """Pin key: uppercase, digits without leading zeros."""
    s = norm(s)
    return str(int(s)) if re.fullmatch(r"\d+", s) else s


pages = {(p["pid"], p["file_id"]): p["page_type"] for p in T["pages"]}
wire_index = collections.defaultdict(list)  # (pid, fid, wire) -> port dicts on that wire
for p in T["ports"]:
    for c in p.get("wire_contacts") or []:
        wire_index[(p["pid"], p["file_id"], c.get("wire_handle"))].append(p)
for part in T["parts"]:
    for q in part["ports"]:
        for c in q.get("wire_contacts") or []:
            wire_index[(part["pid"], q["file_id"], c.get("wire_handle"))].append(dict(q, _part=True, pid=part["pid"]))

sym_block = {(s["pid"], s["record_id"]): s["block_name"] for s in T["symbols"]}


def other_terminals(port):
    """Identities of terminal contacts (SW 端子/装置端子 with identity) on the same wire(s) as the port."""
    out = set()
    other_cats = collections.Counter()
    wires = {c.get("wire_handle") for c in (port.get("wire_contacts") or [])}
    for w in wires:
        for q in wire_index.get((port["pid"], port["file_id"], w), []):
            if q is port or (q.get("insert_handle") == port.get("insert_handle") and q.get("marker_handle") == port.get("marker_handle")):
                continue
            if q.get("_part"):
                other_cats["layout_part"] += 1
                continue
            cat = q.get("category") or ""
            if cat in TERMINAL and q.get("endpoint_identity"):
                out.add(key_id(q["endpoint_identity"]))
            elif cat in TERMINAL:
                other_cats["terminal_unidentified"] += 1
            elif cat in INTERNAL:
                other_cats["internal"] += 1
            else:
                other_cats["other"] += 1
    return out, wires, dict(other_cats)


# ---- layout side: part label per part instance; PCL rows per owner
part_label = {}
for part in T["parts"]:
    lab = part["label"] or {}
    part_label[(part["pid"], part["file_id"], part["insert_handle"])] = norm(lab.get("normalized") or lab.get("value"))

pcl_rows = collections.defaultdict(list)  # (pid, fid, owner) -> rows
for r in T["routes"]:
    if r["source_kind"] != "PCL":
        continue
    far = next((e for e in r["ends"] if e.get("role") == "FAR"), None) or {}
    # far identity candidates: SW identity (sw_port), or the text identity when the far end is a
    # terminal strip terminal (its text 'label+pin' has the same form as a SW 端子 identity).
    # Device-terminal text names the far device, not the SW label, so it is not used.
    cands = []
    if far.get("identity_source") == "sw_port" and far.get("identity"):
        cands.append((key_id(far["identity"]), "sw"))
    elif far.get("far_text_identity") and far.get("category") == "端子":
        cands.append((key_id(far["far_text_identity"]), "text"))
    pcl_rows[(r["pid"], r["file_id"], r["owner_handle"])].append({
        "pin": pn(r["logical_pin"]), "cands": cands,
        "far_cat": far.get("category") or "", "far_src": far.get("far_source"), "wire": r["wire_handle"]})

label_pins = collections.defaultdict(lambda: collections.defaultdict(set))  # (pid, L) -> far_id -> {(pin, owner)}
label_pin_set = collections.defaultdict(set)  # (pid, L) -> pins seen
owner_no_label = 0
for (pid, fid, owner), rows in pcl_rows.items():
    L = part_label.get((pid, fid, owner))
    if not L:
        owner_no_label += 1
        continue
    for r in rows:
        label_pin_set[(pid, L)].add(r["pin"])
        for fid_key, src in r["cands"]:
            label_pins[(pid, L)][fid_key].add((r["pin"], (fid, owner), src))
print("PCL owners without part label:", owner_no_label, flush=True)


def match(pid, L, T_set):
    pins, owners, srcs = set(), set(), set()
    for t in T_set:
        for pin, ok, src in label_pins.get((pid, L), {}).get(t, ()):
            pins.add(pin)
            owners.add(ok)
            srcs.add(src)
    return pins, owners, srcs


rows_out = []

# ---- TX: Pop-X LOGGEN ends (no SW category)
for r in T["routes"]:
    if r["source_kind"] != "LOGGEN":
        continue
    for i, e in enumerate(r["ends"]):
        if (e.get("category") or "") != "" or e.get("status") not in ("resolved_by_symb2_text", "insert_not_sw"):
            continue
        s2 = e.get("symb2") or {}
        L = norm(s2.get("label_text") or s2.get("record_device") or e.get("device"))
        truth = pn(s2.get("slot_text") or s2.get("record_seq") or e.get("seq") or "")
        T_set = set()
        for j, o in enumerate(r["ends"]):
            if j == i:
                continue
            if (o.get("category") or "") in TERMINAL and o.get("identity") and o.get("status") in ("resolved", "resolved_by_text"):
                T_set.add(key_id(o["identity"]))
        rows_out.append({"cls": "TX", "pid": r["pid"], "fid": e.get("file_id"), "label": L, "T": sorted(T_set),
                         "truth": truth, "truth_src": "symb2_slot" if s2.get("slot_text") else "record_seq",
                         "block": e.get("block"), "page_type": pages.get((r["pid"], e.get("file_id"))),
                         "record": r["record_id"], "wire": r["wire_handle"], "other_ends": len(r["ends"]) - 1,
                         "status_src": e.get("status"), "device": e.get("device")})

# ---- TI: SW coil / connector ports with resolved pin text
for p in T["ports"]:
    if p["category"] not in ("线圈", "接插件"):
        continue
    pin = p.get("pin") or {}
    if not (pin.get("resolved") and pin.get("normalized")):
        continue
    L = norm((p.get("label") or {}).get("normalized"))
    T_set, wires, cats = other_terminals(p)
    rows_out.append({"cls": "TI", "pid": p["pid"], "fid": p["file_id"], "label": L, "T": sorted(T_set),
                     "truth": pn(pin["normalized"]), "truth_src": "term_text",
                     "block": sym_block.get((p["pid"], p["symbol_id"])), "page_type": pages.get((p["pid"], p["file_id"])),
                     "record": p["record_id"], "wire": ",".join(sorted(str(w) for w in wires)),
                     "other_ends": sum(cats.values()), "status_src": p["category"], "device": L})

# ---- PS: Pop-S (SW internal ports without identity)
for p in T["ports"]:
    if p["category"] not in INTERNAL or p.get("endpoint_identity"):
        continue
    L = norm((p.get("label") or {}).get("normalized"))
    T_set, wires, cats = other_terminals(p)
    rows_out.append({"cls": "PS", "pid": p["pid"], "fid": p["file_id"], "label": L, "T": sorted(T_set),
                     "truth": None, "truth_src": None, "block": sym_block.get((p["pid"], p["symbol_id"])),
                     "page_type": pages.get((p["pid"], p["file_id"])), "record": p["record_id"],
                     "wire": ",".join(sorted(str(w) for w in wires)), "other_ends": sum(cats.values()),
                     "status_src": p["category"], "device": L, "port_number": p["port_number"],
                     "other_cats": json.dumps(cats, ensure_ascii=False)})

# ---- evaluate
for row in rows_out:
    T_set = set(row["T"])
    row["label_in_layout"] = (row["pid"], row["label"]) in label_pin_set
    row["conn_supported"] = any(t in label_pins.get((row["pid"], row["label"]), {}) for t in T_set) if T_set and row["label"] else False
    pins, owners, srcs = match(row["pid"], row["label"], T_set) if (row["label_in_layout"] and T_set) else (set(), set(), set())
    row["match_src"] = ",".join(sorted(srcs))
    row["cands"] = sorted(pins)
    row["n_copies"] = len(owners)
    row["pred"] = next(iter(pins)) if len(pins) == 1 else None
    if not row["label"]:
        row["status"] = "no_label"
    elif not row["label_in_layout"]:
        row["status"] = "no_label_in_layout"
    elif not T_set:
        row["status"] = "no_terminal"
    elif not pins:
        row["status"] = "no_match"
    elif len(pins) == 1:
        row["status"] = "unique"
    else:
        row["status"] = "ambiguous"
    if row["cls"] in ("TX", "TI"):
        row["agree"] = (row["pred"] == row["truth"]) if row["pred"] is not None else None

# ---- shared-terminal gate: a schematic terminal shared by several pins of the same label cannot pin one k
mult = collections.Counter()
for row in rows_out:
    for t in set(row["T"]):
        mult[(row["pid"], row["label"], t)] += 1
for row in rows_out:
    shared = any(mult[(row["pid"], row["label"], t)] > 1 for t in row["T"])
    row["shared_terminal"] = shared
    row["pred_strict"] = row["pred"] if (row["pred"] is not None and not shared) else None
    if row["cls"] in ("TX", "TI"):
        row["agree_strict"] = (row["pred_strict"] == row["truth"]) if row["pred_strict"] is not None else None

pickle.dump(rows_out, open(WORK / "m5_pins.pkl", "wb"))
print("rows", len(rows_out))
for k, v in sorted(collections.Counter((r["cls"], r["status"]) for r in rows_out).items()):
    print(" ", k, v)
for cls in ("TX", "TI"):
    sub = [r for r in rows_out if r["cls"] == cls and r["pred"] is not None]
    ag = sum(1 for r in sub if r["agree"])
    print(cls, "unique predictions", len(sub), "agree", ag, "rate", round(ag / len(sub), 4) if sub else None)
    print(cls, "conn_supported", sum(1 for r in rows_out if r["cls"] == cls and r["conn_supported"]))

for cls in ("TX", "TI"):
    sub = [r for r in rows_out if r["cls"] == cls and r["pred_strict"] is not None]
    ag = sum(1 for r in sub if r["agree_strict"])
    print(cls, "STRICT unique predictions", len(sub), "agree", ag, "rate", round(ag / len(sub), 4) if sub else None)
    print(cls, "STRICT by source", collections.Counter((r["match_src"], bool(r["agree_strict"])) for r in sub))
