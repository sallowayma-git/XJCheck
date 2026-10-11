"""GAP2-S analysis (read-only): the existing SW-element links whose element carries an identity, the accepted cut widths,
and the shape of the components_not_two refusals (offline DEV-INT on the round20 inputs).
Usage: python g2s_identified_analysis.py ROUND OUT_JSON
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
import dwg_audit.audit.superworks_device_internal as D  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g2s_offline as O  # noqa: E402

ROUND = Path(sys.argv[1])
OUT = Path(sys.argv[2])

refused_components = Counter()
original_judge = D._judge_split


def spy(a, b, ca, cb, component_count, file_id, dots, model_segments):
    reason, geometry = original_judge(a, b, ca, cb, component_count, file_id, dots, model_segments)
    if reason == "components_not_two":
        refused_components[component_count] += 1
    return reason, geometry


D._judge_split = spy

identified_existing = []
body_widths = Counter()
for pdir in sorted(glob.glob(str(ROUND / "p*" / "*" / "findings"))):
    findings = Path(pdir)
    pid = findings.parent.parent.name
    ports, lines, groups, routes, unregistered, endpoints, dots = O.load(findings)
    port_by = {p["record_id"]: p for p in ports}
    base = D.build_device_internal_links(ports, routes, wire_group_of=D.wire_keys_from_lines(lines, groups),
                                         unregistered=unregistered, wire_endpoints=endpoints)
    for link in base["links"]:
        if link["source"] == "sw_internal_element" and link.get("element_port_id"):
            element = port_by.get(link["element_port_id"], {})
            identity = O.text(element.get("endpoint_identity"))
            if identity:
                device = port_by.get(link["port_id"], {})
                identified_existing.append({
                    "project": pid, "port_id": link["port_id"], "device_identity": link["endpoint_identity"],
                    "element_port_id": link["element_port_id"], "element_label": link["element_label"],
                    "element_identity": identity, "same_identity_as_device": identity.casefold() == link["endpoint_identity"].casefold(),
                    "pcl": link["pcl_corroborated"], "element_category": element.get("category"),
                    "device_wire_ports": len(link["wire_port_ids"]),
                })
    split = D.split_terminal_wires(ports, lines, groups, dots)
    for record in split["splits"]:
        body_widths[round(record["body_width"], 2)] += 1

df = pd.DataFrame(identified_existing)
summary = {
    "identified_existing_links": len(df),
    "by_project": df.groupby("project").size().to_dict() if len(df) else {},
    "same_identity_as_device": int(df["same_identity_as_device"].sum()) if len(df) else 0,
    "pcl_corroborated": int(df["pcl"].sum()) if len(df) else 0,
    "element_category": df["element_category"].value_counts().to_dict() if len(df) else {},
    "device_wire_ports": df["device_wire_ports"].value_counts().to_dict() if len(df) else {},
    "accepted_body_widths": dict(body_widths),
    "refused_components_not_two_by_component_count": dict(refused_components),
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"summary": summary, "rows": identified_existing}, ensure_ascii=False, indent=1, default=str),
               encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
