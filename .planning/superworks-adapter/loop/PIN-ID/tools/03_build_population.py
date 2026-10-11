"""PIN-ID step 1: build the two unidentified-pin populations and their candidate identities (read-only).

Pop-S: SuperWORKS internal-element ports (category 内部元件/线圈/接插件/接地) with no endpoint identity.
Pop-X: element pin ends in LOGGEN wire records whose INSERT was never registered as a SuperWORKS symbol
       (status insert_not_sw). Their INSERT carries LD_SYMB2_LABEL and (often) LD_SYMB2_TERM_TEXT_n links,
       but no LD_SYMB2_SPECIAL, so extract/superworks_semantics.walk drops them.

Inputs : 01_load_replay.py pickle (replay tables) and 02_scan_symb2.py pickle (DXF scan).
Outputs: <out_dir>/pop_s.pkl, pop_x.pkl, summary.json (large tables stay out of the repository).
Usage  : python 03_build_population.py <all.pkl> <scan_all.pkl> <out_dir>
"""
import collections
import json
import pickle
import re
import sys
from pathlib import Path

CAT_INT = {"内部元件", "线圈", "接插件", "接地"}
CAT_TERM = {"端子", "装置端子"}
CONN_STYLE = "端子排内接元件"


def split_values(text):
    out = []
    for v in (text or "").replace("，", ",").split(","):
        v = v.strip().strip("&")
        if v:
            out.append(v)
    return out


def dup_stats(items, key_fn, loc_fn, partner_fn):
    """Same candidate identity on several physical pins of one project; conflict = distinct terminal partners."""
    groups = collections.defaultdict(lambda: {"locs": set(), "partners": set()})
    for it in items:
        k = key_fn(it)
        if not k:
            continue
        g = groups[(it["pid"], k.casefold())]
        g["locs"].add(loc_fn(it))
        pf = partner_fn(it)
        if pf:
            g["partners"].add(pf)
    multi = {k: v for k, v in groups.items() if len(v["locs"]) > 1}
    conflict = {k: v for k, v in multi.items() if len(v["partners"]) > 1}
    return dict(identities=len(groups), multi_location=len(multi), multi_location_distinct_partners=len(conflict))


def main(all_pkl, scan_pkl, out_dir):
    D = pickle.load(open(all_pkl, "rb"))
    T, FAM = D["tables"], D["family"]
    S = [r for r in pickle.load(open(scan_pkl, "rb")) if "error" not in r]
    scan = {(r["pid"], r["file"], r["handle"]): r for r in S}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows_by_id = collections.defaultdict(list)
    for s in T["strips"]:
        if s["endpoint_identity"]:
            rows_by_id[(s["pid"], s["endpoint_identity"].casefold())].append(s)

    def row_values(rows):
        vals = set()
        for r in rows:
            for c in r["connections"]:
                if c.get("style") == CONN_STYLE:
                    vals.update(v.casefold() for v in split_values(c.get("value")))
        return vals

    wire_index = collections.defaultdict(list)
    for p in T["ports"]:
        for c in p["wire_contacts"] or []:
            wire_index[(p["pid"], p["file_id"], c.get("wire_handle"))].append(p)

    # ---------------- Pop-S: SW internal ports without identity
    pop_s = []
    for p in T["ports"]:
        if p["category"] not in CAT_INT or p["endpoint_identity"] is not None:
            continue
        lab = (p["label"] or {}).get("normalized") or ""
        sc = scan.get((p["pid"], p["file_id"], p["insert_handle"]), {})
        partners = []
        for c in p["wire_contacts"] or []:
            for q in wire_index[(p["pid"], p["file_id"], c.get("wire_handle"))]:
                if q["insert_handle"] != p["insert_handle"] and q["category"] in CAT_TERM and q["endpoint_identity"]:
                    partners.append(q)
        partner_id = partners[0]["endpoint_identity"] if partners else None
        partner_insert = partners[0]["insert_handle"] if partners else None
        rows = rows_by_id.get((p["pid"], partner_id.casefold()), []) if partner_id else []
        vals = row_values(rows)
        row_cands = sorted(v for v in vals
                           if lab and (v.startswith(lab.casefold() + "-") or re.fullmatch(re.escape(lab.casefold()) + r"[0-9a-z]+", v)))
        pin = p["pin"] if isinstance(p["pin"], dict) else {}
        pop_s.append(dict(
            pid=p["pid"], family=FAM.get(p["pid"]), file=p["file_id"], sheet=p["sheet_id"], insert=p["insert_handle"],
            block=sc.get("block"), port=p["port_number"], category=p["category"], label=lab,
            label_ok=bool(lab), has_wire=bool(p["wire_contacts"]),
            wire=[c.get("wire_handle") for c in p["wire_contacts"] or []],
            reasons=p["reason_codes"], partner_identity=partner_id, partner_insert=partner_insert,
            partner_row_found=bool(rows),
            row_candidates=row_cands, scan_term_texts=len(sc.get("term_texts") or {}),
            pin_resolved=bool(pin.get("resolved")), k_num=(f"{lab}-{p['port_number']}" if lab else None),
            nearest_rejected=(pin.get("nearest_rejected") or {}).get("reason"),
            model_owner=(p["instance_path"] or "").count("/") == 1,
        ))

    # ---------------- Pop-X: insert_not_sw ends of LOGGEN records
    pop_x = []
    for r in T["routes"]:
        if r["source_kind"] != "LOGGEN":
            continue
        for e in r["ends"]:
            if e.get("status") != "insert_not_sw":
                continue
            sc = scan.get((r["pid"], r["file_id"], e.get("terminal_handle")), {})
            others = [o for o in r["ends"] if o is not e]
            other = others[0] if others else {}
            pin = str(e.get("pin") or "")
            seq = str(e.get("seq") or "")
            dev = e.get("device") or ""
            lab = (sc.get("label_text") or "").strip()
            slot = (sc.get("term_texts") or {}).get(pin)
            resolved = other.get("status") == "resolved"
            tid = (other.get("identity") or "") if resolved else ""
            term_partner = resolved and other.get("category") in CAT_TERM
            rows = rows_by_id.get((r["pid"], tid.casefold()), []) if tid else []
            vals = row_values(rows)
            k_rec = f"{dev}-{seq}" if dev and seq else None
            k_slot = f"{lab}-{slot}" if (lab and slot) else None
            row_check = None
            if k_rec and term_partner:
                if not rows:
                    row_check = "row_missing"
                elif k_rec.casefold() in vals:
                    row_check = "agree"
                elif any(v.startswith(dev.casefold() + "-") for v in vals):
                    row_check = "disagree_same_device_other_pin"
                else:
                    row_check = "disagree_device_absent"
            pop_x.append(dict(
                pid=r["pid"], family=FAM.get(r["pid"]), file=r["file_id"], record=r["record_id"], wire=r["wire_handle"],
                insert=e.get("terminal_handle"), block=sc.get("block"), pin=pin, seq=seq, device=dev,
                scan_label=lab, scan_has_label=bool(lab), slot_text=slot, slot_exists=slot is not None,
                k_rec=k_rec, k_slot=k_slot,
                k_agree=bool(k_rec and k_slot and k_rec.casefold() == k_slot.casefold()),
                other_status=other.get("status"), other_category=other.get("category"),
                other_identity=(other.get("identity") if resolved else None),
                n_ends=len(r["ends"]), term_partner=term_partner, row_check=row_check, row_found=bool(rows),
                other_port_ids=other.get("port_ids") or [], other_file=other.get("file_id"),
                other_insert=other.get("terminal_handle"), other_terminal_port=other.get("port_number"),
                model_owner=(sc.get("owner") == "model"),
            ))

    dup_x = dup_stats(pop_x, lambda it: it["k_rec"], lambda it: (it["file"], it["insert"], it["pin"]),
                      lambda it: it["other_identity"] if it["term_partner"] else None)
    dup_s = dup_stats(pop_s, lambda it: it["k_num"], lambda it: (it["file"], it["insert"], it["port"]),
                      lambda it: it["partner_identity"])

    summary = {
        "pop_s_total": len(pop_s),
        "pop_s_with_wire": sum(1 for x in pop_s if x["has_wire"]),
        "pop_s_with_terminal_partner": sum(1 for x in pop_s if x["partner_identity"]),
        "pop_s_label_ok": sum(1 for x in pop_s if x["label_ok"]),
        "pop_s_scan_term_text_links": sum(1 for x in pop_s if x["scan_term_texts"]),
        "pop_s_pin_resolved": sum(1 for x in pop_s if x["pin_resolved"]),
        "pop_s_nearest_rejected": sum(1 for x in pop_s if x["nearest_rejected"]),
        "pop_s_row_candidates_unique": sum(1 for x in pop_s if len(x["row_candidates"]) == 1),
        "pop_s_dup_k_num": dup_s,
        "pop_x_total": len(pop_x),
        "pop_x_symbols": len({(x["pid"], x["file"], x["insert"]) for x in pop_x}),
        "pop_x_scan_label": sum(1 for x in pop_x if x["scan_has_label"]),
        "pop_x_slot_exists": sum(1 for x in pop_x if x["slot_exists"]),
        "pop_x_k_rec": sum(1 for x in pop_x if x["k_rec"]),
        "pop_x_k_slot": sum(1 for x in pop_x if x["k_slot"]),
        "pop_x_k_agree": sum(1 for x in pop_x if x["k_agree"]),
        "pop_x_k_slot_present_but_disagree": sum(1 for x in pop_x if x["k_slot"] and x["k_rec"] and not x["k_agree"]),
        "pop_x_term_partner": sum(1 for x in pop_x if x["term_partner"]),
        "pop_x_row_check": dict(collections.Counter(x["row_check"] for x in pop_x if x["row_check"])),
        "pop_x_dup_k_rec": dup_x,
    }
    pickle.dump(pop_s, open(out_dir / "pop_s.pkl", "wb"))
    pickle.dump(pop_x, open(out_dir / "pop_x.pkl", "wb"))
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
