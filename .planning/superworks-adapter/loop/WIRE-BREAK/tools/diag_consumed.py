"""Diagnostic (read-only): run one project with the snapshot code and log which admitted-time pairs consume a port.

usage: diag_consumed.py PROJECT_ID PORT_SUBSTRING OUT_DIR
Run with PYTHONPATH pointing at the snapshot src.
"""
import json, sys
from pathlib import Path

PLAN = Path("F:/workspace/XJToolkit/.planning/superworks-adapter")
pid, needle, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])

import dwg_audit.audit.superworks_extractor as sx
from dwg_audit.services.execution import run_analysis_workflow

orig = sx._consumed_ports
hits = []

def spy(pairs, cut_group_ids=frozenset()):
    result = orig(pairs, cut_group_ids)
    for port_id, items in result.items():
        if needle == "*" or needle in port_id:
            for pair, side in items:
                hits.append({"port": port_id, "side": side, "pair_id": pair.pair_id, "status": pair.status,
                             "pair_kind": getattr(pair, "pair_kind", None), "line_group_id": pair.line_group_id,
                             "sheet_id": pair.sheet_id, "left": pair.left_value, "right": pair.right_value,
                             "rationale": (pair.rationale or "")[:160]})
    return result

sx._consumed_ports = spy
project = next(p for p in json.loads((PLAN / "corpus_manifest.json").read_text(encoding="utf-8"))["projects"]
               if p["project_id"] == pid)
result = run_analysis_workflow(input_root=Path(project["input_root"]), output_root=out, include_audit=True)
out.mkdir(parents=True, exist_ok=True)
(out / "consumed_hits.json").write_text(json.dumps(hits, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print("hits", len(hits))
for h in hits[:20]:
    print(h)
