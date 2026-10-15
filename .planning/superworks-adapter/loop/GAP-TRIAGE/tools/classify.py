"""Assign each R-RECOGNITION-GAP row to one triage class (read-only; reads .tmp/gap_triage_work/features.pkl).

Precedence (first match wins):
  A  device_internal       device terminal + internal element / coil / unregistered pin; device_internal_verdict
  B  v1_closed             a non-discard V1 pair covers the same wire segment with an identity match
  D  xpage                 cross-page continuity covers a port of the gap (or a candidate exists)
  C  v2_at_end             a V2 terminal binding lies within 1.0 of a segment end and carries a text value
       C_v2_redundant      the value equals a identity SuperWORKS already gives a side (no new identity)
       C_v2_new            the value is not any known identity (candidate identity for the open side)
  X  non_terminal          neither side is a terminal (DEV/TERM) and no end touches a termpoint or rail
  E  unresolved            residual; subclassed by what lies at the free end
       E_unreg_pin         end on an unregistered SYMB2 termpoint (block pin without a SuperWORKS port)
       E_unreg_element     end on an unregistered element INSERT (SuperWORKS does not know the handle)
       E_reg_element_no_port  end on a SuperWORKS-registered element INSERT with no port at that end
       E_rail_T            end on a vertical sheet line >= 50 (terminal-strip rail or frame)
       E_bus_T             end on another sheet line (bus, frame, or wire junction)
       E_text_only         no line or symbol at the end, a text label only
       E_open              nothing at the end
Writes .tmp/gap_triage_work/classified.pkl and summary.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

WORK = Path("F:/workspace/XJToolkit/.tmp/gap_triage_work")


def _ends(row):
    out = []
    for g in (row.end1_geo, row.end2_geo):
        out.append(json.loads(g) if g else {})
    return out


def _ins(row):
    out = []
    for g in (row.end1_ins, row.end2_ins):
        out.append(json.loads(g) if g else [])
    return out


def _xy(s):
    if not s:
        return None
    v = json.loads(s)
    return (float(v[0]), float(v[1])) if v and v[0] is not None else None


def _free_ends(r):
    """Indices of the observed segment ends that carry no SuperWORKS port contact (within 1.0)."""
    coords = json.loads(r.coords) if r.coords else []
    if len(coords) != 4:
        return []
    ends = [(coords[0], coords[1]), (coords[2], coords[3])]
    contacts = [c for c in (_xy(r.left_contact_xy), _xy(r.right_contact_xy)) if c]
    free = []
    for i, e in enumerate(ends):
        if not any(((e[0] - c[0]) ** 2 + (e[1] - c[1]) ** 2) ** 0.5 <= 1.0 for c in contacts):
            free.append(i)
    return free


def _known_identities(row):
    return {str(x) for x in (row.left_identity, row.right_identity) if isinstance(x, str) and x}


def classify_row(r):
    ends = _ends(r)
    xp_true = any(part.endswith("True") for part in ((r.left_xpage_cover or "") + "|" + (r.right_xpage_cover or "")).split("|") if part)
    if r.dev_verdict == "device_internal":
        excl = (r.left_cov_excluded_dev and r.device_side == "L") or (r.right_cov_excluded_dev and r.device_side == "R")
        return "A", "A_" + r.other_kind + ("_excluded" if excl else "_not_excluded")
    if r.cur_cov_val > 0:
        return "B", "B_v1_pass" if r.cur_cov_pass > 0 else "B_v1_review"
    if xp_true or r.left_xpage_cand or r.right_xpage_cand:
        return "D", "D_xpage_cover" if xp_true else "D_xpage_candidate"
    if r.v2_end_n > 0 and r.v2_end_value:
        known = _known_identities(r)
        if str(r.v2_end_value) in known:
            return "C", "C_v2_redundant"
        return "C", "C_v2_new"
    if r.left_cat not in ("DEV", "TERM") and r.right_cat not in ("DEV", "TERM") and not any(
            e.get("unreg_pin") or e.get("rail_T") for e in ends):
        return "X", "X_element_only"
    ins = _ins(r)
    free = _free_ends(r)
    if not free:
        return "E", "E_port_both_ends"
    fe = [ends[i] for i in free]
    fi = [{h["kind"] for h in ins[i]} for i in free]
    if any(e.get("unreg_pin") for e in fe):
        return "E", "E_unreg_pin"
    if any("unreg" in k for k in fi):
        return "E", "E_unreg_element"
    if any("reg" in k for k in fi):
        return "E", "E_reg_element_no_port"
    if any(e.get("rail_T") for e in fe):
        return "E", "E_rail_T"
    if any(e.get("bus_T") for e in fe):
        return "E", "E_bus_T"
    if any(e.get("text_near") for e in fe):
        return "E", "E_text_only"
    return "E", "E_open"


def main():
    df = pd.read_pickle(WORK / "features_ins.pkl")
    res = [classify_row(r) for r in df.itertuples(index=False)]
    df = df.copy()
    df["cls"] = [c for c, _ in res]
    df["sub"] = [s for _, s in res]
    # family and page-type labels for reporting
    df.to_pickle(WORK / "classified.pkl")
    summary = {"total": int(len(df)), "cls": df.cls.value_counts().to_dict(), "sub": df["sub"].value_counts().to_dict()}
    with open(WORK / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
