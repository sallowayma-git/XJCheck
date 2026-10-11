"""PIN-1 step 1: pool of production-admitted symb2 candidates (read-only, from a replay directory).

A pool item is a wire-route row admitted as review with an unregistered-INSERT end (identity_source
symb2_text_slot). Stratification keys: project family (COV-GAP family_map) and element type, taken from the
alphabetic prefix of the device label (e.g. 1ZKK -> ZKK, 8ID3 -> ID).

Usage: python 01_pool.py <replay_dir> <out_json>
"""
import json
import re
import sys
from pathlib import Path

FAMILY = json.loads(Path("F:/workspace/XJToolkit/.planning/superworks-adapter/loop/COV-GAP/tools/family_map.json")
                    .read_text(encoding="utf-8"))
TYPE_RE = re.compile(r"[A-Za-z]+")


def element_type(label):
    letters = "".join(TYPE_RE.findall(label or ""))
    return letters.upper() or "(none)"


def _key(value):
    return "".join(str(value or "").split()).casefold()


def physical_pin_counts(project_dir, rows):
    """identity key -> number of distinct physical pins (file, insert, pin) naming it in the project:
    candidate pins of admitted-or-not symb2 ends, and SuperWORKS ports / part ports with an identity."""
    import pandas as pd
    pins = {}
    ports = pd.read_parquet(project_dir / "findings/sw_ports.parquet")
    for p in ports.itertuples():
        if p.endpoint_identity:
            pins.setdefault(_key(p.endpoint_identity), set()).add((p.file_id, str(p.insert_handle), str(p.port_number)))
    parts = pd.read_parquet(project_dir / "findings/sw_part_instances.parquet")
    for part in parts.itertuples():
        raw_ports = json.loads(part.ports) if isinstance(part.ports, str) else list(part.ports or [])
        for port in raw_ports:
            if port.get("endpoint_identity"):
                pins.setdefault(_key(port["endpoint_identity"]), set()).add(
                    (part.file_id, str(port.get("insert_handle")), str(port.get("port_number"))))
    for row in rows.to_dict("records"):
        for e in json.loads(row["ends_json"]):
            if e.get("status") == "resolved_by_symb2_text":
                pins.setdefault(_key(e["identity"]), set()).add((e["file_id"], str(e["terminal_handle"]), str(e["port_number"])))
    return {k: len(v) for k, v in pins.items()}


def main(replay, out):
    import pandas as pd
    pool = []
    for complete in sorted(Path(replay).glob("p*/complete.json")):
        pid = complete.parent.name
        project_dir = Path(json.loads(complete.read_text(encoding="utf-8"))["project_dir"])
        rows = pd.read_parquet(project_dir / "findings/sw_wire_routes.parquet")
        pairs = pd.read_parquet(project_dir / "findings/pairs.parquet")
        pair_ids = set(pairs.pair_id)
        pin_counts = physical_pin_counts(project_dir, rows)
        for row in rows.to_dict("records"):
            if row["admission_status"] != "admitted_review":
                continue
            ends = json.loads(row["ends_json"])
            symb = [e for e in ends if e.get("status") == "resolved_by_symb2_text"]
            term = [e for e in ends if e.get("status") != "resolved_by_symb2_text"]
            if len(symb) != 1 or len(term) != 1:
                continue
            e, t = symb[0], term[0]
            ev = e.get("symb2") or {}
            pool.append(dict(
                pid=pid, family=FAMILY.get(pid), file=row["file_id"], sheet=row["sheet_id"], record=row["record_id"],
                wire=row["wire_handle"], pair_id=row["admitted_pair_id"], pair_present=row["admitted_pair_id"] in pair_ids,
                insert=e["terminal_handle"], pin=str(e["port_number"]), identity=e["identity"],
                label=ev.get("label_text"), slot=ev.get("slot_text"), device=ev.get("record_device"), seq=ev.get("record_seq"),
                slot_handle=ev.get("slot_handle"), label_handle=ev.get("label_handle"),
                term_insert=t.get("terminal_handle"), term_port=str(t.get("port_number")), term_identity=t.get("identity"),
                etype=element_type(ev.get("label_text")), wire_present=bool(row["wire_handle"]),
                identity_pins=pin_counts.get(_key(e["identity"]), 1),
            ))
    Path(out).write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
    import collections
    print("pool", len(pool), dict(collections.Counter(p["family"] for p in pool)))
    print("types", collections.Counter(p["etype"] for p in pool).most_common(12))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
