"""LEGACY-CENSUS step 1: tag every final pair of the round-23 full replay (read-only).

Source tags (per final pair):
  a   pure SuperWORKS output (fresh SW pair, no legacy predecessor)
  b1  legacy claim replaced by SW with a changed identity/text (ledger categories B, C, D)
  b2  legacy claim confirmed by SW (ledger E/F, or SW annotation attached without a replacement)
  c   pure legacy output, both ends have a SW port on the same sheet (SW did not confirm)
  d   pure legacy output, at least one end has no SW port (SW blind spot)
Writes .tmp/legacy_census_work/pairs_tagged.parquet and side tables.
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import defaultdict

import pandas as pd

ROOT = "F:/workspace/XJToolkit"
RUN = os.path.join(ROOT, ".tmp/superworks_round23_full")
WORK = os.path.join(ROOT, ".tmp/legacy_census_work")
os.makedirs(WORK, exist_ok=True)

SW_EVIDENCE_KEYS = ("superworks", "superworks_constraints", "sw_conflicts", "sw_dictionary_warnings")


def jload(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def norm(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def family_of(root_text):
    m = re.search(r"GJ-(\d+)", root_text)
    if m:
        return f"GJ-{m.group(1)}"
    if "N2604" in root_text:
        return "N2604"
    if "PAC-885" in root_text:
        return "PAC-885"
    return "other"


def project_list():
    out = []
    for pdir in sorted(glob.glob(os.path.join(RUN, "p[0-9][0-9][0-9]"))):
        pid = os.path.basename(pdir)
        rs = json.load(open(os.path.join(pdir, "run_summary.json"), encoding="utf-8"))[0]
        art = glob.glob(os.path.join(pdir, "*", "findings"))[0]
        out.append((pid, rs["project_root"], art))
    return out


def load_project(root_text, fdir):
    pairs = pd.read_parquet(os.path.join(fdir, "pairs.parquet"))
    pages = pd.read_parquet(os.path.join(fdir, "pages.parquet"))
    ports = pd.read_parquet(os.path.join(fdir, "sw_ports.parquet"))
    cov = pd.read_parquet(os.path.join(fdir, "sw_port_coverage.parquet"))
    ledger = pd.read_parquet(os.path.join(fdir, "superworks_supersession.parquet"))
    symbols = pd.read_parquet(os.path.join(fdir, "sw_symbols.parquet"))
    issues = pd.read_parquet(os.path.join(os.path.dirname(fdir), "audit", "issues.parquet"))

    # Ledger: which pair ids were produced by SW as fresh output (old None) or as a replacement of a legacy claim.
    fresh_new, repl_new, repl_cat = set(), set(), defaultdict(set)
    for row in ledger.itertuples(index=False):
        old = jload(row.old_pair)
        news = jload(row.new_pairs) or []
        if old is None:
            fresh_new.update(n.get("pair_id") for n in news)
        else:
            for n in news:
                repl_new.add(n.get("pair_id"))
                repl_cat[n.get("pair_id")].add(row.category)

    # SW ports: text ids (label / pin) and endpoint identities, indexed per sheet.
    port_rows = []
    text_index = defaultdict(list)
    id_index = defaultdict(list)
    proj_id_index = defaultdict(set)
    for p in ports.itertuples(index=False):
        label = jload(p.label) or {}
        pin = jload(p.pin) or {}
        texts = {label.get("text_id"), pin.get("text_id")} - {None}
        ident = norm(p.endpoint_identity)
        idx = len(port_rows)
        port_rows.append({"port_id": p.record_id, "sheet_id": p.sheet_id, "identity": ident,
                          "category": norm(p.category), "port_number": norm(p.port_number)})
        for t in texts:
            text_index[(p.sheet_id, t)].append(idx)
        if ident:
            id_index[(p.sheet_id, ident)].append(idx)
            proj_id_index[ident].add(p.sheet_id)
    cov_by_port = {r.port_id: r for r in cov.itertuples(index=False)}
    sw_symbol_blocks = {norm(x) for x in symbols.block_name if norm(x)}
    page_info = {r.sheet_id: r for r in pages.itertuples(index=False)}
    return dict(pairs=pairs, port_rows=port_rows, text_index=text_index, id_index=id_index,
                proj_id_index=proj_id_index, cov_by_port=cov_by_port, fresh_new=fresh_new,
                repl_new=repl_new, repl_cat=repl_cat, sw_symbol_blocks=sw_symbol_blocks,
                page_info=page_info, issues=issues, family=family_of(root_text))


def end_match(ctx, sheet, text_id, value):
    """Return (kind, port_indexes) for one legacy end on one sheet."""
    if text_id is not None and (sheet, text_id) in ctx["text_index"]:
        return "port_by_text", ctx["text_index"][(sheet, text_id)]
    if value and (sheet, value) in ctx["id_index"]:
        return "port_by_identity", ctx["id_index"][(sheet, value)]
    if value and value in ctx["proj_id_index"]:
        return "identity_elsewhere", []
    return "none", []


def end_sw_reason(ctx, port_idx):
    """One short code per end: why SW did not confirm through the matched port."""
    codes = []
    for i in port_idx:
        prow = ctx["port_rows"][i]
        cov = ctx["cov_by_port"].get(prow["port_id"])
        if prow["identity"] is None:
            codes.append("port_identity_unresolved")
            continue
        if cov is None:
            codes.append("port_no_coverage_row")
            continue
        if bool(cov.consumed):
            codes.append("port_consumed_by_other_sw_pair")
            continue
        reasons = jload(cov.reason_codes) or []
        if "no_wire_contact" in reasons:
            codes.append("port_no_wire_contact")
        elif "no_matching_production_pair" in reasons:
            codes.append("port_wire_no_sw_pair")
        elif reasons:
            codes.append("port_" + "_".join(sorted(reasons))[:60])
        else:
            codes.append("port_unconsumed_other")
    if not codes:
        return "none"
    for key in ("port_identity_unresolved", "port_consumed_by_other_sw_pair", "port_no_wire_contact",
                "port_wire_no_sw_pair"):
        if key in codes:
            return key
    return codes[0]


def end_kind(ev, side):
    """Object type of one end, from the legacy producer's own evidence."""
    ch = norm(ev.get(f"selected_{side}_channel")) or "none"
    detail = norm(ev.get(f"selected_{side}_channel_detail")) or ""
    if ev.get(f"selected_{side}_physical_endpoint"):
        return "v2_physical_terminal"
    if "physical_terminal" in detail:
        return "cad_terminal_label"
    if norm(ev.get(f"selected_{side}_source_block_name")):
        return "block_text"
    if ch == "terminal_numeric_channel":
        return "terminal_numeric"
    if ch in ("wire_logic_endpoint_channel", "schematic_semantic_endpoint_channel"):
        return "logic_endpoint"
    if ch == "continuation_channel":
        return "continuation"
    if ch == "none":
        return "absent"
    return "other:" + ch


def build():
    rows, issue_rows, project_meta = [], [], []
    for pid, root_text, fdir in project_list():
        ctx = load_project(root_text, fdir)
        pages = ctx["page_info"]
        project_meta.append({"project_id": pid, "family": ctx["family"],
                             "root": root_text.replace("F:\\workspace\\XJToolkit\\test\\", ""),
                             "pairs": len(ctx["pairs"]), "issues": len(ctx["issues"]),
                             "sw_ports": len(ctx["port_rows"])})
        for r in ctx["issues"].itertuples(index=False):
            issue_rows.append({"project_id": pid, "issue_id": r.issue_id, "rule_id": r.rule_id,
                               "severity": r.severity, "sheet_id": r.sheet_id, "pair_id": r.pair_id,
                               "primary_pair_id": r.primary_pair_id,
                               "related_pair_ids": list(r.related_pair_ids) if r.related_pair_ids is not None else [],
                               "message": r.message})
        for p in ctx["pairs"].itertuples(index=False):
            ev = jload(p.evidence) or {}
            pair_id = p.pair_id
            sheet = p.sheet_id
            pg = pages.get(sheet)
            route = norm(getattr(pg, "route_target", None)) if pg is not None else None
            subtype = norm(getattr(pg, "page_subtype", None)) if pg is not None else None
            sw_keys = [k for k in SW_EVIDENCE_KEYS if k in ev]
            if ev.get("source") == "superworks" and pair_id not in ctx["repl_new"]:
                tag = "a"
            elif pair_id in ctx["fresh_new"] and pair_id not in ctx["repl_new"]:
                tag = "a"
            elif pair_id in ctx["repl_new"]:
                tag = "b1" if ctx["repl_cat"][pair_id] & {"B", "C", "D"} else "b2"
            elif sw_keys:
                tag = "b2"
            else:
                tag = None
            # b2 sub-kinds: what SW actually said about the legacy claim.
            swd = ev.get("superworks") if isinstance(ev.get("superworks"), dict) else {}
            if tag == "b2":
                if swd.get("partial"):
                    b2_sub = "b2p_partial_sw_side_missing"
                elif swd.get("validation_only"):
                    b2_sub = "b2v_validation_only"
                elif "superworks_constraints" in ev and "superworks" not in ev:
                    b2_sub = "b2c_constraint_only"
                elif swd:
                    b2_sub = "b2e_sw_identity_agrees"
                else:
                    b2_sub = "b2x_other"
            else:
                b2_sub = ""
            left_v, right_v = norm(p.left_value), norm(p.right_value)
            lt, rt = norm(p.left_text_id), norm(p.right_text_id)
            lk = rk = lr = rr = None
            blind = ""
            if tag is None:
                lk, lp = end_match(ctx, sheet, lt, left_v)
                rk, rp = end_match(ctx, sheet, rt, right_v)
                lr = end_sw_reason(ctx, lp)
                rr = end_sw_reason(ctx, rp)
                lo, ro = lk.startswith("port"), rk.startswith("port")
                tag = "c" if (lo and ro) else "d"
                blind = "" if (lo and ro) else ("both_blind" if not (lo or ro) else "one_side_blind")
            obj_sub = ""
            if isinstance(ev.get("table_mapping"), dict):
                obj_sub = "tm:" + str(ev["table_mapping"].get("mapping_mode"))
            elif ev.get("component_submode"):
                obj_sub = "cs:" + str(ev.get("component_submode"))
            elif ev.get("semantic_kind") or ev.get("bridge_mapping_kind"):
                obj_sub = "sk:" + str(ev.get("semantic_kind") or ev.get("bridge_mapping_kind"))
            rows.append({
                "project_id": pid, "family": ctx["family"], "pair_id": pair_id, "sheet_id": sheet,
                "obj_sub": obj_sub, "orient": norm(ev.get("line_orientation")) or "",
                "status": p.status, "pair_kind": p.pair_kind, "route_target": route, "page_subtype": subtype,
                "tag": tag, "b2_sub": b2_sub, "blind": blind,
                "left_value": left_v, "right_value": right_v, "left_text_id": lt, "right_text_id": rt,
                "left_match": lk, "right_match": rk, "left_sw_reason": lr, "right_sw_reason": rr,
                "evidence_source": norm(ev.get("source")), "sw_keys": ",".join(sw_keys),
                "repl_cats": ",".join(sorted(ctx["repl_cat"].get(pair_id, set()))),
                "left_kind": end_kind(ev, "left"), "right_kind": end_kind(ev, "right"),
                "left_v2_port": bool(ev.get("selected_left_physical_endpoint")),
                "right_v2_port": bool(ev.get("selected_right_physical_endpoint")),
                "left_block": norm(ev.get("selected_left_source_block_name")),
                "right_block": norm(ev.get("selected_right_source_block_name")),
                "line_group_id": norm(p.line_group_id),
                "confidence": float(p.confidence) if p.confidence is not None else None,
                "rationale": norm(p.rationale),
                "left_x": p.left_coord_x, "left_y": p.left_coord_y,
                "right_x": p.right_coord_x, "right_y": p.right_coord_y,
            })
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(WORK, "pairs_tagged.parquet"), index=False)
    pd.DataFrame(project_meta).to_parquet(os.path.join(WORK, "projects.parquet"), index=False)
    pd.DataFrame(issue_rows).to_parquet(os.path.join(WORK, "issues_all.parquet"), index=False)
    print("pairs", len(df), "issues", len(issue_rows))
    print(df.groupby(["tag", "status"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    build()
