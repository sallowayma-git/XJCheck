"""Final tallies for the GAP triage README (read-only).

Reads .tmp/gap_triage_work/classified.pkl and the current/round25 coverage tables, writes
.planning/superworks-adapter/loop/GAP-TRIAGE/details.json (ASCII-safe keys, UTF-8 text values) and prints a summary.
Offline estimates are labelled as such in the output; no run outputs are changed.
"""
from __future__ import annotations

import glob
import json
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path("F:/workspace/XJToolkit")
CUR = REPO / ".tmp/engine_coordination_full_acceptance/current"
WORK = REPO / ".tmp/gap_triage_work"
OUT = REPO / ".planning/superworks-adapter/loop/GAP-TRIAGE/details.json"


def has(x):
    return isinstance(x, str) and x.strip() != ""


def coverage_table():
    frames = []
    for p in glob.glob(str(CUR / "p*" / "*" / "findings" / "sw_port_coverage.parquet")):
        pid = p.split("\\")[-4] if "\\" in p else p.split("/")[-4]
        d = pd.read_parquet(p, columns=["port_id", "category", "eligible", "consumed", "pass", "excluded_device_internal",
                                         "device_internal_overruled", "page_type", "endpoint_identity"])
        d["project"] = pid
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def main():
    df = pd.read_pickle(WORK / "classified.pkl")
    fam_map = json.load(open(WORK / "family_map.json", encoding="utf-8"))
    name_to_code = {v: k for k, v in fam_map.items()}
    df["fam"] = df.family.map(name_to_code)
    df["Lid"] = df.left_identity.map(has)
    df["Rid"] = df.right_identity.map(has)
    cov = coverage_table()
    cov_key = cov.set_index(["project", "port_id"])
    eligible_not_consumed = set(zip(cov[(cov.eligible) & (~cov.consumed)].project, cov[(cov.eligible) & (~cov.consumed)].port_id))
    excluded = set(zip(cov[cov.excluded_device_internal].project, cov[cov.excluded_device_internal].port_id))
    out = {}
    out["total"] = int(len(df))
    out["cls_counts"] = df.cls.value_counts().to_dict()
    out["sub_counts"] = df["sub"].value_counts().to_dict()
    out["family_counts"] = {f: int(n) for f, n in df.fam.value_counts().items()} if "fam" in df else {}
    out["cls_by_family"] = {k: {str(a): int(b) for a, b in v.items()} for k, v in pd.crosstab(df.cls, df.fam).to_dict("index").items()} if "fam" in df else {}
    out["cls_by_pair"] = {k: {str(a): int(b) for a, b in v.items()} for k, v in pd.crosstab(df["sub"], df.left_cat + "|" + df.right_cat).to_dict("index").items()}
    out["reason_codes"] = df.res_reasons.value_counts().to_dict()

    # coverage effect: terminal ports on the gap segments that are eligible and not yet consumed
    def term_ports(rows, side_cols):
        s = set()
        for r in rows.itertuples(index=False):
            for pid_col, cat_col in side_cols:
                pid = getattr(r, pid_col)
                cat = getattr(r, cat_col)
                if pid and cat in ("DEV", "TERM"):
                    s.add((r.project, pid))
        return s

    side_cols = [("left_port_id", "left_cat"), ("right_port_id", "right_cat")]
    gains = {}
    for name in ["B", "C_v2_redundant", "E_port_both_ends", "E_rail_T", "E_bus_T", "E_reg_element_no_port", "E_unreg_pin", "E_unreg_element", "E_open", "E_text_only"]:
        sub = df[(df["sub"] == name) if name in set(df["sub"]) else (df.cls == name)]
        ports = term_ports(sub, side_cols)
        gains[name] = {"terminal_ports_on_rows": len(ports),
                       "eligible_not_consumed": len(ports & eligible_not_consumed)}
    a_not = df[df["sub"].str.endswith("_not_excluded")]
    a_ports = set()
    for r in a_not.itertuples(index=False):
        pid = r.left_port_id if r.device_side == "L" else (r.right_port_id if r.device_side == "R" else "")
        if pid:
            a_ports.add((r.project, pid))
    gains["A_not_excluded_device_ports"] = {"unique": len(a_ports),
                                           "eligible_not_consumed": len(a_ports & eligible_not_consumed),
                                           "already_excluded": len(a_ports & excluded)}
    a_exc = df[df["sub"].str.endswith("_excluded")]
    a_ex_ports = set()
    for r in a_exc.itertuples(index=False):
        pid = r.left_port_id if r.device_side == "L" else (r.right_port_id if r.device_side == "R" else "")
        if pid:
            a_ex_ports.add((r.project, pid))
    gains["A_excluded_device_ports"] = {"unique": len(a_ex_ports), "eligible_not_consumed": len(a_ex_ports & eligible_not_consumed)}
    out["coverage_candidates"] = gains

    # identity presence by subclass
    ident = {}
    for name, g in df.groupby("sub"):
        ident[name] = {"both": int((g.Lid & g.Rid).sum()), "one": int((g.Lid ^ g.Rid).sum()), "none": int((~g.Lid & ~g.Rid).sum())}
    out["identity_presence"] = ident
    out["one_side_identity_missing_is_int_or_coil"] = int(((~df.Lid) & df.left_cat.isin(["INT", "COIL"])).sum()
                                                          + ((~df.Rid) & df.right_cat.isin(["INT", "COIL"])).sum())
    # offline residual estimate (policy P1-P4 plus same-identity suppression and G1P label rule)
    P1 = int(df["sub"].eq("A_INT_excluded").sum() + df["sub"].eq("A_COIL_excluded").sum() + df["sub"].eq("A_UNREG_PIN_excluded").sum())
    P2 = int((df.cls == "B").sum())
    P3 = int((df.cls == "D").sum() - (df["sub"] == "D_xpage_candidate").sum())
    P4 = int((df.cls == "X").sum())
    pb = df[df["sub"] == "E_port_both_ends"]
    P6 = int((pb.Lid & pb.Rid & (pb.left_identity == pb.right_identity)).sum())
    unreg = df[df["sub"] == "E_unreg_pin"]
    dev_label_eq = unreg[(unreg.device_side == "L") & (unreg.left_label == unreg.right_label) & (unreg.right_label != "")]
    dev_label_eq2 = unreg[(unreg.device_side == "R") & (unreg.left_label == unreg.right_label) & (unreg.left_label != "")]
    P7 = int(len(dev_label_eq) + len(dev_label_eq2))
    residual = out["total"] - P1 - P2 - P3 - P4 - P6 - P7
    out["offline_residual"] = {
        "P1_device_internal_excluded_already_in_coverage": P1,
        "P2_v1_closed_by_physical_segment": P2,
        "P3_xpage_cover_minus_candidates": P3,
        "P4_non_terminal_element_only_removed_from_issues": P4,
        "P6_same_identity_multi_contact_suppressed": P6,
        "P7_unregistered_pin_same_label_device_internal": P7,
        "residual_before_human_triage": residual,
    }
    # residual composition (after policy): group by likely action
    rest = df.copy()
    keep = pd.Series(True, index=rest.index)
    keep &= ~rest["sub"].isin(["A_INT_excluded", "A_COIL_excluded", "A_UNREG_PIN_excluded", "B_v1_pass", "B_v1_review",
                              "D_xpage_cover", "X_element_only"])
    keep &= ~((rest["sub"] == "E_port_both_ends") & rest.Lid & rest.Rid & (rest.left_identity == rest.right_identity))
    keep &= ~((rest["sub"] == "E_unreg_pin") & (rest.left_label == rest.right_label) & (rest.left_label != ""))
    rest = rest[keep]
    out["residual_composition"] = rest["sub"].value_counts().to_dict()

    # per family / page-type views for the README (families coded G1..G5 by map file)
    fam_map_path = WORK / "family_map.json"
    out["family_map"] = json.load(open(fam_map_path, encoding="utf-8")) if fam_map_path.exists() else {}
    out["page_type_by_cls"] = {k: {str(a): int(b) for a, b in v.items()} for k, v in pd.crosstab(df.cls, df.page_type).to_dict("index").items()}

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ["total", "cls_counts", "sub_counts", "offline_residual", "coverage_candidates", "residual_composition"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
