"""LEGACY-CENSUS step 4a: offline replay of the extraction-stage symbol port proposals (read-only).

For every frozen DXF in corpus_manifest.json, reproduce cad_extract's proposal loop:
  for each INSERT definition name in model space -> propose_ports_from_block -> classify_definition_family.
Records one row per (file, definition) with the SW / non-SW flag (definition name is absent from the
project's sw_symbols), port count, family id and the INSERT handles (for joining with pair evidence).
Code: the round-23 snapshot (the code that produced the replay), imported in isolation.
Output: .tmp/legacy_census_work/v2_proposals.parquet
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from collections import defaultdict
from multiprocessing import Pool

SNAP = "F:/workspace/XJToolkit/.planning/superworks-adapter/round23_full_src"
RUN = "F:/workspace/XJToolkit/.tmp/superworks_round23_full"
WORK = "F:/workspace/XJToolkit/.tmp/legacy_census_work"
MANIFEST = "F:/workspace/XJToolkit/.planning/superworks-adapter/corpus_manifest.json"
OUT = os.path.join(WORK, "v2_proposals.parquet")

_CTX = {}


def _init():
    sys.path.insert(0, SNAP)
    import ezdxf  # noqa: F401
    from dwg_audit.audit.symbol_port_proposal import propose_ports_from_block, classify_definition_family
    from dwg_audit.audit.symbol_port_proposal import apply_human_symbol_policy_to_proposal_row
    _CTX["propose"] = propose_ports_from_block
    _CTX["classify"] = classify_definition_family
    _CTX["policy"] = apply_human_symbol_policy_to_proposal_row


def _sw_names_by_project():
    import pandas as pd
    out = {}
    for d in glob.glob(os.path.join(RUN, "p[0-9][0-9][0-9]")):
        pid = os.path.basename(d)
        f = glob.glob(os.path.join(d, "*", "findings", "sw_symbols.parquet"))
        names = set()
        if f:
            names = {str(x).strip() for x in pd.read_parquet(f[0], columns=["block_name"]).block_name if x}
        out[pid] = names
    return out


def work_file(args):
    pid, file_id, dxf, sw_names = args
    import ezdxf
    rows = []
    t0 = time.time()
    try:
        try:
            doc = ezdxf.readfile(dxf)
        except Exception:
            doc = ezdxf.recover.readfile(dxf)[0]
    except Exception as exc:  # noqa: BLE001
        return {"file_id": file_id, "project_id": pid, "error": f"{type(exc).__name__}: {exc}", "rows": []}
    handles = defaultdict(list)
    for e in doc.modelspace():
        if e.dxftype() == "INSERT":
            handles[e.dxf.name].append(e.dxf.handle)
    for name in sorted(handles):
        row = {"project_id": pid, "file_id": file_id, "dxf": os.path.basename(dxf), "definition_name": name,
               "insert_count": len(handles[name]), "insert_handles": json.dumps(sorted(handles[name])),
               "is_sw_definition": name in sw_names, "n_ports": 0, "family_id": None,
               "classifier_status": None, "classifier_confidence": None, "rule_id": None, "error": None}
        try:
            block = doc.blocks.get(name)
            if block is None:
                row["error"] = "no_block"
                rows.append(row)
                continue
            proposal = _CTX["propose"](block, definition_name=name, source_dxf=dxf, max_ports=6)
            payload = proposal.to_dict()
            row["n_ports"] = len(proposal.ports)
            fam = _CTX["classify"](payload)
            row["family_id"] = fam.get("family_id")
            row["classifier_status"] = fam.get("classifier_status")
            row["classifier_confidence"] = fam.get("classifier_confidence")
            row["rule_id"] = fam.get("matched_family_rule_id")
            # The artifact writer's policy step (report/artifacts.py): decides whether the ports may be emitted.
            full = _CTX["policy"]({**payload, "ports": [port.to_review_port() for port in proposal.ports],
                                   "file_id": file_id, "definition_name": name})
            row["behavior_mode"] = full.get("behavior_mode")
            row["allow_port_emission"] = full.get("allow_port_emission")
            row["allow_external_attachment"] = full.get("allow_external_attachment")
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        rows.append(row)
    return {"file_id": file_id, "project_id": pid, "error": None, "rows": rows, "sec": round(time.time() - t0, 2)}


def main():
    import pandas as pd
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    sw = _sw_names_by_project()
    jobs = []
    for p in manifest["projects"]:
        for f in p["files"]:
            jobs.append((p["project_id"], f["file_id"], f["dxf_path"], sw.get(p["project_id"], set())))
    print("files", len(jobs), flush=True)
    all_rows, errors = [], []
    t0 = time.time()
    with Pool(processes=int(os.environ.get("V2_WORKERS", "12")), initializer=_init) as pool:
        for n, res in enumerate(pool.imap_unordered(work_file, jobs, chunksize=1), 1):
            if res["error"]:
                errors.append({"project_id": res["project_id"], "file_id": res["file_id"], "error": res["error"]})
            all_rows.extend(res["rows"])
            if n % 100 == 0 or n == len(jobs):
                print(f"{n}/{len(jobs)} {time.time()-t0:.0f}s", flush=True)
    df = pd.DataFrame(all_rows)
    df.to_parquet(OUT, index=False)
    pd.DataFrame(errors).to_parquet(os.path.join(WORK, "v2_proposals_file_errors.parquet"), index=False)
    print("rows", len(df), "file errors", len(errors), flush=True)


if __name__ == "__main__":
    main()
