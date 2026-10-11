"""GAP2-S offline replay of the DEV-INT module on frozen findings (read-only; writes only to --out).

For every project folder under ROUND/<pid>/<family>/findings it rebuilds the DEV-INT inputs from the stored parquet
rows and calls the production build_device_internal_links. mode=base runs the unsplit rule (wire mapping of the stored
line groups) and is checked against the stored sw_device_internal_links.parquet. mode=split runs the GAP2-S rule.
Usage: python g2s_offline.py ROUND OUT [base|split] [pid ...]
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
from dwg_audit.audit.superworks_device_internal import (  # noqa: E402
    build_device_internal_links, wire_keys_from_lines)


def jload(value, default):
    if value is None or (isinstance(value, float) and value != value):
        return default
    return json.loads(value) if isinstance(value, str) else value


def text(value):
    return "" if value is None or (isinstance(value, float) and value != value) else str(value)


def findings_dirs(round_dir: Path, pids):
    for path in sorted(round_dir.glob("p*/*/findings")):
        pid = path.parent.parent.name
        if not pids or pid in pids:
            yield pid, path


def load(findings: Path):
    rd = lambda name: pd.read_parquet(findings / f"{name}.parquet")  # noqa: E731
    ports = []
    for r in rd("sw_ports").to_dict("records"):
        ports.append({**r, "label": jload(r.get("label"), {}) or {},
                      "wire_contacts": jload(r.get("wire_contacts"), []) or []})
    lines = []
    for r in rd("lines").to_dict("records"):
        lines.append({"file_id": text(r["file_id"]), "line_id": text(r["line_id"]), "handle": text(r["handle"]),
                      "source_block_name": text(r.get("source_block_name")), "sx": r["start_x"], "sy": r["start_y"],
                      "ex": r["end_x"], "ey": r["end_y"]})
    groups = [{"file_id": text(r["file_id"]), "member_line_ids": jload(r.get("member_line_ids"), []) or []}
              for r in rd("line_groups").to_dict("records")]
    routes = [dict(r) for r in rd("sw_wire_routes").to_dict("records")]
    unregistered = []
    for r in rd("sw_unregistered_symb2").to_dict("records"):
        termpoints = [{"number": t["number"], "a": tuple(t["a"]), "b": tuple(t["b"])}
                      for t in jload(r.get("termpoints"), [])]
        unregistered.append({"record_id": r["record_id"], "file_id": text(r["file_id"]),
                             "insert_handle": text(r["insert_handle"]), "label_value": text(r["label_value"]),
                             "label_resolved": bool(r["label_resolved"]), "termpoints": termpoints})
    endpoints = {}
    for line in lines:
        if line["source_block_name"]:
            continue
        endpoints.setdefault((line["file_id"], line["handle"]), {})
        endpoints[(line["file_id"], line["handle"])][0] = (float(line["sx"]), float(line["sy"]))
        endpoints[(line["file_id"], line["handle"])][1] = (float(line["ex"]), float(line["ey"]))
    dots = [{"file_id": text(r["file_id"]), "x": r["x"], "y": r["y"]} for r in rd("sw_connect_dots").to_dict("records")]
    return ports, lines, groups, routes, unregistered, endpoints, dots


def main(round_dir: Path, out: Path, mode: str, pids):
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    total = Counter()
    for pid, findings in findings_dirs(round_dir, pids):
        ports, lines, groups, routes, unregistered, endpoints, dots = load(findings)
        kwargs = dict(unregistered=unregistered, wire_endpoints=endpoints)
        if mode == "base":
            from dwg_audit.audit.superworks_device_internal import wire_keys_from_lines as wk
            result = build_device_internal_links(ports, routes, wire_group_of=wk(lines, groups), **kwargs)
        else:
            result = build_device_internal_links(ports, routes, terminal_split={"lines": lines, "line_groups": groups,
                                                                                "connect_dots": dots}, **kwargs)
        links = result["links"]
        ids = {l["link_id"] for l in links}
        stored = pd.read_parquet(findings / "sw_device_internal_links.parquet")
        stored_ids = set(stored["link_id"]) if len(stored) else set()
        rec = {"links": len(links), "stored_links": len(stored_ids), "match_stored": ids == stored_ids,
               "stats": result["stats"], "splits": len(result["terminal_splits"])}
        summary[pid] = rec
        total.update({"links": len(links), "stored_links": len(stored_ids)})
        total.update({k: v for k, v in result["stats"].items() if not k.startswith("split_refused") and isinstance(v, int)})
        rows = [{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in l.items()}
                for l in links]
        pd.DataFrame(rows).to_parquet(out / f"{pid}_links.parquet", index=False) if rows else None
        if result["terminal_splits"]:
            pd.DataFrame(result["terminal_splits"]).to_parquet(out / f"{pid}_splits.parquet", index=False)
        print(pid, rec["links"], "stored", rec["stored_links"], "match", rec["match_stored"], "splits", rec["splits"],
              flush=True)
    (out / f"summary_{mode}.json").write_text(json.dumps({"projects": summary, "total": dict(total)},
                                                        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("TOTAL", dict(total))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "split", sys.argv[4:])
