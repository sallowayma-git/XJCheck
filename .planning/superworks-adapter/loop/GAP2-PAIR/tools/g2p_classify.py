"""GAP2-PAIR final classification of the 3028 population ports (read-only).

Joins pop.parquet (wire context), sides.parquet (P-side split at the gap), sim_links (method S, with the element
identity guard) and the round19 coverage state. Writes classes.parquet and counts.json to the given directory.

Causes (per port):
  partner      same-identity SuperWORKS port of the same device terminal on the same union wire, gap <= 4
  no_partner   no such port (the union merges with a different identity or a gap > 4)
  side class   what lies on P's side of the gap (away from the partner): internal element with the device label,
               internal element with unresolved label, open end (no SW port), or other / multi
  pair_seg     whether P's own line-group segment has a pair (status of the pair named by P)
  dev_int      round19 DEV-INT verdict for P (excluded reason from the wire multi-end rule, or linked)
  S_link       method S would give a link (element without identity)
Usage: python g2p_classify.py <dir_with_pop_sides_sim>
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


def side_class(row):
    if row["n_partners"] == 0:
        return "no_partner"
    if row["side"] not in ("left", "right"):
        return "coincident_or_none"
    sp = json.loads(row["side_ports"])
    labels = json.loads(row["side_labels"])
    dl = (row["device_label"] or "").casefold()
    internals = [p for p in sp if p["category"] in ("内部元件", "线圈")]
    if not sp:
        return "side_open"
    if len(sp) == 1 and internals:
        lab = labels[internals[0]["port_id"]]
        if not lab["resolved"] or not lab["label"]:
            return "internal_label_unresolved"
        return "internal_same_label" if lab["label"].casefold() == dl else "internal_other_label"
    if len(sp) == 1 and sp[0]["category"] in ("端子", "装置端子") and sp[0]["identity"]:
        return "terminal_with_identity"
    return "multi_or_other"


def main(d: Path):
    pop = pd.read_parquet(d / "pop.parquet")
    sides = pd.read_parquet(d / "sides.parquet")
    links = pd.read_parquet(d / "sim" / "links_joined.parquet")
    sides = sides.drop_duplicates("port_id")
    m = pop.merge(sides[["port_id", "side", "side_ports", "side_labels", "device_label", "n_partners", "gap_w",
                         "partner_port_id", "gap_texts", "gap_dots", "side_cats"]], on="port_id", how="left")
    m["side_class"] = m.apply(side_class, axis=1)
    key = m["project"] + "|" + m["port_id"]
    link_ok = set((links[links.guard_ok.astype(bool)]).apply(lambda r: r.project + "|" + r.port_id, axis=1))
    m["S_link"] = key.isin(link_ok)
    m["gap_has_tail_text"] = False
    for i, r in m.iterrows():
        tail = (r.identity[len(r.device_label):] if isinstance(r.device_label, str) and r.identity.casefold().startswith(
            (r.device_label or "").casefold()) else None)
        hits = json.loads(r.gap_texts) if isinstance(r.gap_texts, str) else []
        m.at[i, "gap_has_tail_text"] = bool(tail) and any(h.strip() == tail for h in hits)
    m["pair_status"] = m["pairs_json"].map(lambda s: ";".join(sorted({p["status"] for p in json.loads(s)})) or "none")
    m["n_pairs"] = m["pairs_json"].map(lambda s: len(json.loads(s)))
    m["n_pairs_live"] = m["pairs_json"].map(lambda s: sum(1 for p in json.loads(s) if p["status"] != "discard"))
    m.to_parquet(d / "classes.parquet", index=False)
    counts = {
        "population": len(m),
        "by_pop": m["pop"].value_counts().to_dict(),
        "partner": m["n_partners"].gt(0).sum(),
        "partner_gap_2_5": int((m["gap_w"].between(2.4, 2.6)).sum()),
        "gap_has_tail_text": int(m["gap_has_tail_text"].sum()),
        "gap_dots_nonzero": int((m["gap_dots"].fillna(0) > 0).sum()),
        "side_class": m.groupby(["pop", "side_class"]).size().rename("n").reset_index().values.tolist(),
        "S_link": int(m["S_link"].sum()),
        "S_link_by_pop": m[m["S_link"]]["pop"].value_counts().to_dict(),
        "pair_status": m["pair_status"].value_counts().to_dict(),
        "n_pairs_live_dist": m["n_pairs_live"].value_counts().to_dict(),
        "wire_ports_dist": m["n_wire_ports"].value_counts().to_dict(),
        "wire_groups_dist": m["n_wire_groups"].value_counts().to_dict(),
        "at_extreme_self": int(m["self_at_extreme"].fillna(False).astype(bool).sum()),
    }
    (d / "counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False, indent=1, default=str)[:4000])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
