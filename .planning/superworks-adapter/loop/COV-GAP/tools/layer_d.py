"""Layer d: component / backplane wiring pages, text-level port objects (read-only).

Universe: texts on 元件接线图 / 背板接线图 / 背板表格型图 pages that are numeric-like
(port-number candidates) and not out_of_scope.  Covered: resolution_status == resolved
AND consumed by at least one non-discard pair.
"""
import json, sys, glob
from pathlib import Path
import pandas as pd

RUN = Path("F:/workspace/XJToolkit/.tmp/superworks_round12_full")
SCR = Path(sys.argv[1])
FAM_NAMES = {"正式典设": "正式典设", "【出原理图】N2604HBJ20732J合同": "N2604合同",
             "110kV变压器保护柜": "110kV变压器保护柜", "PAC-885G-H": "PAC-885G-H",
             "变压器测控柜(2圈变，2台测控)": "变压器测控柜"}
D_PAGE = {"元件接线图", "背板接线图", "背板表格型图"}
run = json.loads((RUN / "run.json").read_text(encoding="utf-8"))
FAM = json.loads((Path(__file__).parent / "family_map.json").read_text(encoding="utf-8"))


def ids_of(v):
    if v is None or isinstance(v, float):
        return []
    if isinstance(v, str):
        return json.loads(v) if v[:1] == "[" else ([v] if v else [])
    return list(v)


rows = []
for p in run["projects"]:
    pid = p["project_id"]
    d = Path(p["project_dir"]) / "findings"
    ta = pd.read_parquet(d / "text_assignments.parquet",
                         columns=["text_id", "sheet_id", "page_type", "resolution_status", "assignment_kind",
                                  "consumed_by_pair_ids", "is_numeric_like", "text", "insert_x", "insert_y",
                                  "explain_reason", "rejection_reason"])
    pr = pd.read_parquet(d / "pairs.parquet", columns=["pair_id", "status"])
    nd = set(pr.pair_id[pr.status != "discard"])
    sub = ta[ta.page_type.isin(D_PAGE)]
    for r in sub.itertuples():
        if r.resolution_status == "out_of_scope" or not r.is_numeric_like:
            continue
        ids = ids_of(r.consumed_by_pair_ids)
        consumed_nd = any(x in nd for x in ids)
        covered = (r.resolution_status == "resolved") and consumed_nd
        ex_ = str(r.explain_reason or "")
        rj_ = str(r.rejection_reason or "")
        if covered:
            reason = "covered"
        elif r.resolution_status == "rejected":
            reason = "D1a_元件内部引脚号被拒(block_internal_pin_number)" if "block_internal_pin" in rj_ + ex_ else (
                "D1b_被派生数字替代(superseded)" if "superseded" in rj_ else "D1z_其它拒绝:" + rj_[:30])
        elif r.resolution_status == "unselected":
            reason = "D1c_候选已接受但未被选中"
        elif r.resolution_status == "discarded":
            if ex_.startswith("Covered by component_mapping"):
                reason = "D1d_声称被component_mapping覆盖但台账无非discard挂接"
            elif "block_internal_pin" in ex_:
                reason = "D1e_元件内部引脚对被discard"
            elif ex_.startswith("Structural"):
                reason = "D1f_端子排结构边框被discard"
            else:
                reason = "D1g_其它discard:" + ex_[:40]
        elif r.resolution_status in ("review", "label_only", "structural_evidence"):
            reason = f"D1h_{r.resolution_status}"
        elif not ids:
            reason = "D2_已解析但未被任何配对消费"
        else:
            reason = "D3_仅被discard配对消费"
        rows.append(dict(project=pid, family=FAM[pid], fam=FAM_NAMES.get(FAM[pid]),
                         sheet=r.sheet_id, page_type=r.page_type, text_id=r.text_id, text=r.text,
                         numeric=bool(r.is_numeric_like), status=r.resolution_status, kind=r.assignment_kind,
                         covered=covered, reason=reason, explain=ex_[:80], x=float(r.insert_x) if r.insert_x == r.insert_x else None,
                         y=float(r.insert_y) if r.insert_y == r.insert_y else None))
df = pd.DataFrame(rows)
df.to_pickle(SCR / "layer_d.pkl")
print("layer d universe", len(df), "covered", int(df.covered.sum()), "rate", round(df.covered.mean(), 4))
print(df.groupby("page_type").covered.agg(["size", "sum", "mean"]).to_string())
print(df.reason.value_counts().to_string())
