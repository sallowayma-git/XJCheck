"""Load round16 replay tables for all 77 projects into one pickle (scratch, read-only inputs)."""
import json, pickle, sys
from pathlib import Path
import pandas as pd

R = Path("F:/workspace/XJToolkit/.tmp/superworks_round16_full")
FAM = json.loads(Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/COV-GAP/tools/family_map.json").read_text(encoding="utf-8"))
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

tables = {k: [] for k in ["ports", "symbols", "parts", "routes", "strips", "coverage", "pairs", "pages", "lines", "linegroups", "text_assign", "texts"]}
for complete in sorted(R.glob("p*/complete.json")):
    pid = complete.parent.name
    proj = Path(json.loads(complete.read_text(encoding="utf-8"))["project_dir"])
    f = proj / "findings"
    ports = pd.read_parquet(f / "sw_ports.parquet")
    for r in ports.to_dict("records"):
        tables["ports"].append(dict(
            pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            symbol_id=r["symbol_id"], insert_handle=r["insert_handle"], marker_handle=r["marker_handle"],
            port_number=str(r["port_number"] or ""), category=r["category"] or "",
            endpoint_identity=r["endpoint_identity"] if isinstance(r["endpoint_identity"], str) else None,
            label=J(r["label"]) or {}, pin=J(r["pin"]) or {}, reason_codes=J(r["reason_codes"]) or [],
            wire_contacts=J(r["wire_contacts"]) or [], raw_xdata=J(r["raw_xdata"]) or {},
            validation=J(r["validation"]) or {}, instance_path=r["instance_path"],
            start=(r["start_x"], r["start_y"]), end=(r["end_x"], r["end_y"]), tolerance=r["tolerance"]))
    sy = pd.read_parquet(f / "sw_symbols.parquet")
    for r in sy.to_dict("records"):
        tables["symbols"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            insert_handle=r["insert_handle"], block_name=r["block_name"], category=r["category"] or "",
            label=J(r["label"]) or {}, pin_texts=J(r["pin_texts"]) or {}, endpoint_identity=r["endpoint_identity"] if isinstance(r["endpoint_identity"], str) else None,
            raw_xdata=J(r["raw_xdata"]) or {}, reason_codes=J(r["reason_codes"]) or [], validation=J(r["validation"]) or {},
            insert_x=r["insert_x"], insert_y=r["insert_y"]))
    pi = pd.read_parquet(f / "sw_part_instances.parquet")
    for r in pi.to_dict("records"):
        tables["parts"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            insert_handle=r["insert_handle"], block_name=r["block_name"], label=J(r["label"]) or {},
            part_no=J(r["part_no"]) or {}, part_type=r["part_type"], ports=J(r["ports"]) or [],
            reason_codes=J(r["reason_codes"]) or [], validation=J(r["validation"]) or {}))
    rt = pd.read_parquet(f / "sw_wire_routes.parquet")
    for r in rt.to_dict("records"):
        tables["routes"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            source_kind=r["source_kind"], source_handle=r["source_handle"], owner_handle=r["owner_handle"],
            logical_pin=r["logical_pin"], wire_handle=r["wire_handle"], linestyle=r["linestyle"],
            ends=J(r["ends_json"]) or [], reason_codes=J(r["reason_codes_json"]) or [],
            admission_status=r["admission_status"], admission_reason=r["admission_reason"],
            lineno_raw=r["lineno_raw"]))
    st = pd.read_parquet(f / "sw_strip_rows.parquet")
    for r in st.to_dict("records"):
        tables["strips"].append(dict(pid=pid, file_id=r["file_id"], sheet_id=r["sheet_id"], record_id=r["record_id"],
            row_handle=r["row_handle"], header=J(r["header"]) or {}, row=J(r["row"]) or {},
            endpoint_identity=r["endpoint_identity"] if isinstance(r["endpoint_identity"], str) else None,
            connections=J(r["connections"]) or [], potentials=J(r["potentials"]) or [],
            cross_page_refs=J(r["cross_page_refs"]) or [], validation=J(r["validation"]) or {}, reason_codes=J(r["reason_codes"]) or []))
    cv = pd.read_parquet(f / "sw_port_coverage.parquet")
    for r in cv.to_dict("records"):
        tables["coverage"].append(dict(pid=pid, port_id=r["port_id"], sheet_id=r["sheet_id"], category=r["category"],
            page_type=r["page_type"], endpoint_identity=r["endpoint_identity"], eligible=bool(r["eligible"]),
            consumed=bool(r["consumed"]), pass_=bool(r["pass"]), production_pairs=J(r["production_pairs"]) or []))
    pr = pd.read_parquet(f / "pairs.parquet")
    for r in pr.to_dict("records"):
        tables["pairs"].append(dict(pid=pid, pair_id=r["pair_id"], sheet_id=r["sheet_id"], file_id=r["file_id"],
            status=r["status"], left_value=r["left_value"], right_value=r["right_value"], pair_kind=r["pair_kind"],
            line_group_id=r["line_group_id"], evidence=J(r["evidence"]) or {}, rationale=r["rationale"]))
    pg = pd.read_parquet(f / "pages.parquet")
    for r in pg.to_dict("records"):
        tables["pages"].append(dict(pid=pid, sheet_id=r["sheet_id"], file_id=r["file_id"], page_type=r["page_type"],
            filename=r.get("filename"), sheet_no=r.get("sheet_no")))
    print(pid, len(ports), len(rt), len(st), flush=True)

FAM_OK = {k: FAM.get(k) for k in set(t["pid"] for t in tables["ports"])}
pickle.dump({"tables": tables, "family": FAM_OK}, open(OUT, "wb"))
print("saved", OUT)
