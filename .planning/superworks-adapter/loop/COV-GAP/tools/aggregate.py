"""Aggregate COV-GAP object records into layer tables, bucket counts and stratified samples."""
import json, sys, random
from pathlib import Path
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
OUT = ROOT / ".planning/superworks-adapter/loop/COV-GAP"
SCR = Path(sys.argv[1])
FAM_NAMES = {"正式典设": "正式典设", "【出原理图】N2604HBJ20732J合同": "N2604合同",
             "110kV变压器保护柜": "110kV变压器保护柜", "PAC-885G-H": "PAC-885G-H",
             "变压器测控柜(2圈变，2台测控)": "变压器测控柜"}
FAM_ORDER = ["正式典设", "N2604合同", "110kV变压器保护柜", "PAC-885G-H", "变压器测控柜"]
D_PAGE = ["元件接线图", "背板接线图", "背板表格型图"]
TERM = {"端子", "装置端子"}

strip = pd.read_pickle(SCR / "strip.pkl")
pots = pd.read_pickle(SCR / "pots.pkl")
ports = pd.read_pickle(SCR / "ports.pkl")
groups = pd.read_pickle(SCR / "groups.pkl")
for df in (strip, pots, ports, groups):
    df["fam"] = df.family.map(FAM_NAMES)


def rate(n, d):
    return round(n / d, 4) if d else None


def by(df, col, flag):
    out = []
    for k, sub in df.groupby(col):
        n = len(sub)
        c = int(sub[flag].sum())
        out.append({col: k, "universe": n, "covered": c, "rate": rate(c, n)})
    return sorted(out, key=lambda x: -x["universe"])


R = {}

# ---- layer a: 端子排行 左/右 (connection objects)
a = strip.copy()
a["cov"] = a.covered_strict.astype(bool)
R["a_strip_connections"] = {
    "universe": len(a), "left": int((a.side == "left").sum()), "right": int((a.side == "right").sum()),
    "_2_slots_nonzero_in_xdata": 0, "covered": int(a["cov"].sum()), "rate": rate(a["cov"].sum(), len(a)),
    "covered_by": a[a["cov"]].groupby(["side"]).size().to_dict(),
    "pass_table_mapping_refs": "every connection carries one pass table_mapping pair (strict: both sides non-empty)",
    "by_family": by(a, "fam", "cov"), "by_page_type": by(a, "page_type", "cov"),
}

# ---- layer a': 端子排去向文字 (potentials)
p2 = pots.copy()
p2["cov"] = p2.covered.astype(bool)
p2["grp"] = p2.reason.str.extract(r"^(X\d)")[0]
R["a2_strip_destination_texts"] = {
    "universe": len(p2), "resolved_text": int(p2.resolved.astype(bool).sum()),
    "consumed_by_nondiscard_pair": int(p2["cov"].sum()), "rate": rate(p2["cov"].sum(), len(p2)),
    "uncovered_reasons": p2[~p2["cov"]].reason.value_counts().to_dict(),
    "by_family": by(p2, "fam", "cov"), "by_page_type": by(p2, "page_type", "cov"),
}
xs = p2[p2.reason.str.startswith("X3") | p2.reason.str.startswith("X1") | p2.reason.str.startswith("X2")]
R["a2_cross_page_target_check"] = {
    "cross_page_candidates": int(p2.reason.str.match(r"^X[123]").sum()),
    "target_found_with_identity": int(p2.reason.str.match(r"^X[12]").sum()),
    "target_category": p2[p2.reason.str.match(r"^X[12]")].t_cat.value_counts().to_dict(),
    "target_consumed": p2[p2.reason.str.match(r"^X[12]")].t_consumed.map({True: "consumed", False: "not_consumed"}).value_counts().to_dict(),
}

# ---- layer b: SW terminal ports (strict) / other categories (loose)
pt = ports[ports.category.isin(TERM)].copy()
pt["elig"] = pt.eligible.astype(bool)
pt["cov"] = pt.reason.eq("covered")
pe = pt[pt.elig]
R["b_terminal_ports_strict"] = {
    "rows": len(pt), "eligible": len(pe), "covered": int(pe["cov"].sum()), "rate": rate(pe["cov"].sum(), len(pe)),
    "not_eligible": int((~pt.elig).sum()),
    "by_category": by(pe, "category", "cov"), "by_family": by(pe, "fam", "cov"), "by_page_type": by(pe, "page_type", "cov"),
    "uncovered_primary": pe[~pe["cov"]].reason.value_counts().to_dict(),
}
oth = ports[~ports.category.isin(TERM)].copy()
oth["cov"] = oth.reason.eq("covered")
oe = oth[oth.eligible.astype(bool)]
R["b_other_categories_loose"] = {
    "by_category_total": oth.groupby("category").size().to_dict(),
    "by_category_with_wire": oe.groupby("category").size().to_dict(),
    "by_category_referenced_nondiscard": oe.groupby("category")["cov"].sum().astype(int).to_dict(),
    "rate_loose": {k: rate(v, oe[oe.category == k].shape[0]) for k, v in oe.groupby("category")["cov"].sum().items()},
}

# ---- layer d: component / backplane pages (terminal ports, strict)
pd_ = pe[pe.page_type.isin(D_PAGE)]
R["d_component_backplane_terminal"] = {
    "eligible": len(pd_), "covered": int(pd_["cov"].sum()), "rate": rate(pd_["cov"].sum(), len(pd_)),
    "by_page_type": by(pd_, "page_type", "cov"), "by_family": by(pd_, "fam", "cov"),
    "uncovered_primary": pd_[~pd_["cov"]].reason.value_counts().to_dict(),
}

# ---- layer c: schematic wire groups (二次原理图)
g = groups[groups.page_type == "二次原理图"].copy()
g["state"] = g.n_resolved.map({2: "两端都解析", 1: "只解析一端", 0: "两端都没有"})
R["c_schematic_groups"] = {
    "universe": len(g), "dist": g.state.value_counts().to_dict(),
    "rate_both": rate((g.n_resolved == 2).sum(), len(g)),
    "by_origin": {o: {"universe": int(len(s)), "both": int((s.n_resolved == 2).sum()), "one": int((s.n_resolved == 1).sum()),
                      "none": int((s.n_resolved == 0).sum()), "rate_both": rate((s.n_resolved == 2).sum(), len(s))}
                  for o, s in g.groupby("origin")},
    "by_family": {f: {"universe": int(len(s)), "both": int((s.n_resolved == 2).sum()), "rate_both": rate((s.n_resolved == 2).sum(), len(s))}
                  for f, s in g.groupby("fam")},
    "unresolved_endpoint_reasons": pd.concat([g.reason_start, g.reason_end])[lambda s: ~s.str.startswith("resolved")]
        .value_counts().to_dict(),
    "all_groups_by_page_type": {pt_: {"groups": int(len(s)), "both": int((s.n_resolved == 2).sum())}
                                for pt_, s in groups.groupby("page_type")},
}

# ---- layer d (text level, component / backplane pages)
ld = pd.read_pickle(SCR / "layer_d.pkl")
ld["cov"] = ld.covered.astype(bool)
R["d_component_backplane_text_level"] = {
    "universe": len(ld), "covered": int(ld["cov"].sum()), "rate": rate(ld["cov"].sum(), len(ld)),
    "by_page_type": by(ld, "page_type", "cov"), "by_family": by(ld, "fam", "cov"),
    "uncovered_primary": ld[~ld["cov"]].reason.value_counts().to_dict(),
}

# ---- uncovered union: each uncovered object gets exactly one primary bucket
own_end = {"P0", "P1", "P4"}
pe_u = pe[~pe["cov"]].copy()
pe_u["tag"] = pe_u.reason.where(pe_u.reason.str[:2].isin(["P3", "P5"]), "")
pe_u["primary"] = pe_u.apply(lambda r: r.reason if r.reason[:2] in own_end else (r.oend or r.reason), axis=1)
ub = pd.DataFrame({
    "layer": "b_SW端子(严格口径)", "bucket": pe_u.primary, "tag": pe_u.tag,
    "project": pe_u.project, "fam": pe_u.fam, "page_type": pe_u.page_type, "sheet": pe_u.sheet,
    "obj": pe_u.port_id, "ident": pe_u.ident, "x": pe_u.cx, "y": pe_u.cy, "group": pe_u.group,
    "side": pe_u.side, "category": pe_u.category, "oend": pe_u.oend})
ua = p2[~p2["cov"]].copy()
ua_df = pd.DataFrame({
    "layer": "a2_端子排去向文字", "bucket": ua.reason, "tag": "",
    "project": ua.project, "fam": ua.fam, "page_type": ua.page_type, "sheet": ua.sheet,
    "obj": ua.record_id + "|" + ua.text_id, "ident": ua.value, "x": ua.x, "y": ua.y,
    "group": None, "side": None, "category": ua.t_cat, "oend": ""})
ud = ld[~ld["cov"]].copy()
ud_df = pd.DataFrame({
    "layer": "d_元件接线/背板页文字", "bucket": ud.reason, "tag": "",
    "project": ud.project, "fam": ud.fam, "page_type": ud.page_type, "sheet": ud.sheet,
    "obj": ud.text_id, "ident": ud.text, "x": ud.x, "y": ud.y,
    "group": None, "side": None, "category": None, "oend": ""})
union = pd.concat([ub, ua_df, ud_df], ignore_index=True)
total_unc = len(union)
buckets = []
for bkt, n in union.bucket.value_counts().items():
    sub = union[union.bucket == bkt]
    buckets.append({"bucket": bkt, "count": int(n), "share_of_all_uncovered": rate(n, total_unc),
                    "layer": sub.layer.value_counts().to_dict(), "projects": int(sub.project.nunique()),
                    "families": sub.fam.value_counts().to_dict(), "page_types": sub.page_type.value_counts().head(3).to_dict(),
                    "tags": sub.tag[sub.tag != ""].value_counts().to_dict()})
R["uncovered_union"] = {"total": total_unc, "buckets": buckets[:25],
                        "layer_totals": union.layer.value_counts().to_dict()}
# sanity: P-type rows cross-tab with other-end class (what is on the far side when the port is discard-only / value-mismatch)
pe_unc = pe[~pe["cov"]].copy()
R["p_vs_other_end_crosstab"] = pd.crosstab(pe_unc.reason, pe_unc.oend.fillna("")).to_dict(orient="index")

union.to_pickle(SCR / "union.pkl")
ld.to_pickle(SCR / "layer_d_fam.pkl")
g.to_pickle(SCR / "schematic_groups.pkl")
p2.to_pickle(SCR / "pots_fam.pkl")
pe.to_pickle(SCR / "terminal_eligible.pkl")

# ---- stratified samples per top bucket (distinct projects first, seeded)
rng = random.Random(20261010)
SAMPLES = {}
for b in buckets[:8]:
    sub = union[union.bucket == b["bucket"]]
    picks = []
    projs = list(sub.project.unique())
    rng.shuffle(projs)
    for pj in projs:
        if len(picks) >= 3:
            break
        cand = sub[sub.project == pj]
        picks.append(cand.iloc[rng.randrange(len(cand))])
    while len(picks) < 3 and len(picks) < len(sub):
        row = sub.iloc[rng.randrange(len(sub))]
        if not any(row.obj == q.obj and row.project == q.project for q in picks):
            picks.append(row)
    SAMPLES[b["bucket"]] = [{k: (None if (isinstance(v, float) and v != v) else (v.item() if hasattr(v, "item") else v))
                             for k, v in row.to_dict().items()} for row in picks]
R["samples"] = SAMPLES

(SCR / "aggregate.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: R[k] for k in ("a_strip_connections", "a2_strip_destination_texts", "a2_cross_page_target_check")},
                 ensure_ascii=False, indent=1, default=str)[:5000])
print(json.dumps({k: R[k] for k in ("b_terminal_ports_strict", "b_other_categories_loose", "d_component_backplane_terminal")},
                 ensure_ascii=False, indent=1, default=str)[:6000])
print(json.dumps(R["c_schematic_groups"], ensure_ascii=False, indent=1, default=str)[:3000])
print(json.dumps(R["uncovered_union"], ensure_ascii=False, indent=1, default=str)[:7000])
