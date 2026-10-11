"""PIN-S step 1: load the round18 replay tables (read-only) into one pickle.
Usage: python -X utf8 01_load18.py <out.pkl>"""
import json, pickle, sys
from pathlib import Path
import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
R = ROOT / ".tmp/superworks_round18_full"
FAM = json.loads((ROOT / ".planning/superworks-adapter/loop/COV-GAP/tools/family_map.json").read_text(encoding="utf-8"))
OUT = Path(sys.argv[1])

def J(v):
    if v is None or (isinstance(v, float) and v != v):
        return None
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v

def proj_dir(pdir):
    subs = [d for d in pdir.iterdir() if d.is_dir() and (d / "findings").is_dir()]
    return subs[0]

tables = {k: [] for k in ["ports", "symbols", "parts", "routes", "strips", "coverage", "pairs", "pages"]}
pids = []
for complete in sorted(R.glob("p*/complete.json")):
    pid = complete.parent.name
    pids.append(pid)
    f = proj_dir(complete.parent) / "findings"
    for r in pd.read_parquet(f / "sw_ports.parquet").to_dict("records"):
        tables["ports"].append(dict(
            pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            symbol_id=r["symbol_id"], insert_handle=r["insert_handle"], marker_handle=r["marker_handle"],
            port_number=str(r["port_number"] or ""), category=r["category"] or "",
            endpoint_identity=r["endpoint_identity"] if isinstance(r["endpoint_identity"], str) else None,
            label=J(r["label"]) or {}, pin=J(r["pin"]) or {}, reason_codes=J(r["reason_codes"]) or [],
            wire_contacts=J(r["wire_contacts"]) or [], raw_xdata=J(r["raw_xdata"]) or {},
            validation=J(r["validation"]) or {}, instance_path=r["instance_path"],
            start=(r["start_x"], r["start_y"]), end=(r["end_x"], r["end_y"]), tolerance=r["tolerance"]))
    for r in pd.read_parquet(f / "sw_symbols.parquet").to_dict("records"):
        tables["symbols"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            insert_handle=r["insert_handle"], block_name=r["block_name"], category=r["category"] or "",
            label=J(r["label"]) or {}, pin_texts=J(r["pin_texts"]) or {},
            endpoint_identity=r["endpoint_identity"] if isinstance(r["endpoint_identity"], str) else None,
            raw_xdata=J(r["raw_xdata"]) or {}, reason_codes=J(r["reason_codes"]) or [], validation=J(r["validation"]) or {},
            insert_x=r["insert_x"], insert_y=r["insert_y"]))
    for r in pd.read_parquet(f / "sw_part_instances.parquet").to_dict("records"):
        tables["parts"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            insert_handle=r["insert_handle"], block_name=r["block_name"], label=J(r["label"]) or {},
            part_no=J(r["part_no"]) or {}, part_type=r["part_type"], ports=J(r["ports"]) or [],
            reason_codes=J(r["reason_codes"]) or [], validation=J(r["validation"]) or {}))
    for r in pd.read_parquet(f / "sw_wire_routes.parquet").to_dict("records"):
        tables["routes"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            source_kind=r["source_kind"], source_handle=r["source_handle"], owner_handle=r["owner_handle"],
            logical_pin=r["logical_pin"], wire_handle=r["wire_handle"], linestyle=r["linestyle"],
            ends=J(r["ends_json"]) or [], reason_codes=J(r["reason_codes_json"]) or [],
            admission_status=r["admission_status"], admission_reason=r["admission_reason"], lineno_raw=r["lineno_raw"], admitted_pair_id=r["admitted_pair_id"]))
    for r in pd.read_parquet(f / "sw_strip_rows.parquet").to_dict("records"):
        tables["strips"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            row_handle=r["row_handle"], header=J(r["header"]) or {}, row=J(r["row"]) or {},
            endpoint_identity=r["endpoint_identity"] if isinstance(r["endpoint_identity"], str) else None,
            connections=J(r["connections"]) or [], potentials=J(r["potentials"]) or [],
            cross_page_refs=J(r["cross_page_refs"]) or [], validation=J(r["validation"]) or {}, reason_codes=J(r["reason_codes"]) or []))
    for r in pd.read_parquet(f / "sw_port_coverage.parquet").to_dict("records"):
        tables["coverage"].append(dict(pid=pid, port_id=r["port_id"], sheet_id=r["sheet_id"], category=r["category"],
            page_type=r["page_type"], endpoint_identity=r["endpoint_identity"], eligible=bool(r["eligible"]),
            consumed=bool(r["consumed"]), pass_=bool(r["pass"]), production_pairs=J(r["production_pairs"]) or []))
    for r in pd.read_parquet(f / "pairs.parquet").to_dict("records"):
        tables["pairs"].append(dict(pid=pid, pair_id=r["pair_id"], sheet_id=r["sheet_id"], file_id=r["file_id"],
            status=r["status"], left_value=r["left_value"], right_value=r["right_value"], pair_kind=r["pair_kind"],
            line_group_id=r["line_group_id"], evidence=J(r["evidence"]) or {}, rationale=r["rationale"]))
    for r in pd.read_parquet(f / "pages.parquet").to_dict("records"):
        tables["pages"].append(dict(pid=pid, sheet_id=r["sheet_id"], file_id=r["file_id"], page_type=r["page_type"],
            filename=r.get("filename"), sheet_no=r.get("sheet_no")))
    print(pid, flush=True)

# project directory and DXF manifest mapping
man = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
dxf = {}
for proj in man["projects"]:
    for f in proj["files"]:
        dxf[(proj["project_id"], f["file_id"])] = f["dxf_path"]
pickle.dump({"tables": tables, "family": FAM, "pids": pids, "dxf": dxf,
             "pdir": {p: str(proj_dir(R / p)) for p in pids}, "manifest_projects": {p["project_id"]: p.get("project_name") for p in man["projects"]}},
            open(OUT, "wb"))
print("saved", OUT, {k: len(v) for k, v in tables.items()})
