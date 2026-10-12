"""P1-DEDUPE step 0: count legacy pass pairs that a same-sheet SW pass pair repeats (read-only, round-23 outputs).

Two superseder definitions are reported:
  strict  superseder.evidence.source == 'superworks' (SW-produced pair only)
  census  any SW-touched pass pair (SW keys present or SW-produced), as in LEGACY-CENSUS tag a/b1/b2
Two equivalence definitions:
  exact   unordered identical cleaned values (census vkey)
  prod    production rule: each end equal under _identities_agree in both directions, unordered ends
"""
import glob, json, os, sys, collections
import pandas as pd

ROOT = "F:/workspace/XJToolkit"
RUN = os.path.join(ROOT, ".tmp/superworks_round23_full")
sys.path.insert(0, os.path.join(ROOT, ".planning/superworks-adapter/round23_full_src"))
from dwg_audit.audit.superworks_extractor import _identities_agree  # noqa: E402

SW_KEYS = ("superworks", "superworks_constraints", "sw_conflicts", "sw_dictionary_warnings")


def jload(v):
    if v is None or (isinstance(v, float) and v != v):
        return {}
    return json.loads(v) if isinstance(v, str) else (v or {})


def blank(v):
    return v is None or (isinstance(v, float) and v != v) or not str(v).strip()


def ends_agree(a, b):
    if blank(a) or blank(b):
        return False
    return bool(_identities_agree(str(a), str(b)) and _identities_agree(str(b), str(a)))


def prod_equal(old, sw):
    return ((ends_agree(old[0], sw[0]) and ends_agree(old[1], sw[1]))
            or (ends_agree(old[0], sw[1]) and ends_agree(old[1], sw[0])))


def exact_equal(old, sw):
    if any(blank(x) for x in (*old, *sw)):
        return False
    return sorted(map(str, old)) == sorted(map(str, sw))


def main():
    rows = []
    for pdir in sorted(glob.glob(os.path.join(RUN, "p*"))):
        pid = os.path.basename(pdir)
        if not os.path.isdir(pdir):
            continue
        pq = glob.glob(os.path.join(pdir, "*", "findings", "pairs.parquet"))
        if not pq:
            continue
        df = pd.read_parquet(pq[0])
        sup = pd.read_parquet(os.path.join(os.path.dirname(pq[0]), "superworks_supersession.parquet"))
        new_ids = set()
        for v in sup.get("new_pairs", []) if "new_pairs" in sup else []:
            pass
        ev = {r.pair_id: jload(r.evidence) for r in df.itertuples(index=False)}
        ledger_new = set()
        for r in sup.itertuples(index=False):
            np_ = getattr(r, "new_pairs", None)
            if isinstance(np_, str):
                np_ = json.loads(np_)
            for p in np_ or []:
                ledger_new.add(p.get("pair_id"))
        for r in df.itertuples(index=False):
            e = ev[r.pair_id]
            sw_any = any(k in e for k in SW_KEYS) or r.pair_id in ledger_new
            sw_prod = e.get("source") == "superworks" or e.get("component_submode") == "superworks_connect_line_port"
            rows.append(dict(project=pid, pair_id=r.pair_id, sheet_id=r.sheet_id, status=r.status, sw_prod=sw_prod,
                             pair_kind=r.pair_kind, left=r.left_value, right=r.right_value,
                             src=e.get("source"), sw_any=sw_any, sw_keys=",".join(k for k in SW_KEYS if k in e),
                             in_ledger=r.pair_id in ledger_new,
                             tm=isinstance(e.get("table_mapping"), dict),
                             lt=r.left_text_id, rt=r.right_text_id))
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(os.path.dirname(__file__), "..", "pairs_index_r23.parquet"), index=False)
    legacy = df[(~df.sw_any) & (df.src != "superworks") & (df.status.isin(["pass", "review"]))]
    out = {}
    for name, sel in (("sw_produced", lambda d: d[(d.sw_prod) & (d.status == "pass")]),
                      ("strict", lambda d: d[(d.src == "superworks") & (d.status == "pass")]),
                      ("census", lambda d: d[(d.sw_any) & (d.status == "pass")])):
        for eq_name, eq in (("exact", exact_equal), ("prod", prod_equal)):
            hits = []
            sw_by_sheet = collections.defaultdict(list)
            for r in sel(df).itertuples(index=False):
                sw_by_sheet[(r.project, r.sheet_id)].append(r)
            for r in legacy.itertuples(index=False):
                cands = sw_by_sheet.get((r.project, r.sheet_id), [])
                for c in cands:
                    if eq((r.left, r.right), (c.left, c.right)):
                        hits.append((r.project, r.sheet_id, r.pair_id, r.status, r.pair_kind, c.pair_id, c.pair_kind))
                        break
            h = pd.DataFrame(hits, columns=["project", "sheet_id", "pair_id", "status", "pair_kind", "sw_pair_id", "sw_pair_kind"])
            out[f"{name}|{eq_name}"] = {"total": int(len(h)), "pass": int((h.status == "pass").sum()) if len(h) else 0,
                                         "review": int((h.status == "review").sum()) if len(h) else 0}
            if eq_name == "prod":
                h.to_csv(os.path.join(os.path.dirname(__file__), f"hits_{name}_{eq_name}.csv"), index=False, encoding="utf-8")
                if len(h):
                    print(name, eq_name, "by legacy kind/status:\n", h.groupby(["pair_kind", "status"]).size().to_string())
                    print("sw partner kinds:\n", h.groupby(["sw_pair_kind"]).size().to_string())
    print(json.dumps(out, indent=2))
    print("legacy pass total:", int(((legacy.status == "pass")).sum()), "legacy review total:", int((legacy.status == "review").sum()))


if __name__ == "__main__":
    main()
