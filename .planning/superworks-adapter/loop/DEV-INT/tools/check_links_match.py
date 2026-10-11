"""Re-run the device-internal rule (the final module) on the findings of a round and compare with its links table.

Usage: python check_links_match.py <round_dir> <run_dir>

The inputs are the round's sw_ports, sw_wire_routes, lines and line_groups (read only). A link matches when its
(project, link_id) exists in the run's sw_device_internal_links.parquet with identical port, element, wire, label,
pin tail, PCL flag and PCL record ids. Used to confirm that a replay of the same inputs is reproduced by the module.
Note: link_id is unique within a project only (file ids repeat across projects), so the key includes the project.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
from dwg_audit.audit.superworks_device_internal import build_device_internal_links, wire_keys_from_lines  # noqa: E402

FIELDS = ["port_id", "element_port_id", "wire_handle", "device_label", "endpoint_identity", "pin_tail",
          "element_label", "element_port_number", "file_id", "sheet_id", "element_insert_handle"]


def _listed(value):
    if isinstance(value, str):
        return sorted(json.loads(value or "[]"))
    return sorted(value or [])


def main():
    round_dir, run_dir = Path(sys.argv[1]), Path(sys.argv[2])
    expected, computed = [], []
    for findings in sorted(round_dir.glob("p*/*/findings")):
        project = findings.parent.parent.name
        ports = pd.read_parquet(findings / "sw_ports.parquet").to_dict("records")
        routes = pd.read_parquet(findings / "sw_wire_routes.parquet").to_dict("records")
        lines = pd.read_parquet(findings / "lines.parquet").to_dict("records")
        groups = pd.read_parquet(findings / "line_groups.parquet").to_dict("records")
        result = build_device_internal_links(ports, routes, wire_group_of=wire_keys_from_lines(lines, groups))
        for link in result["links"]:
            computed.append({"project": project, **link})
        run_file = run_dir / project
        matches = list(run_file.glob("*/findings/sw_device_internal_links.parquet"))
        if matches:
            for row in pd.read_parquet(matches[0]).to_dict("records"):
                expected.append({"project": project, **row})
    exp = {(r["project"], r["link_id"]): r for r in expected}
    got = {(r["project"], r["link_id"]): r for r in computed}
    mismatched = [key for key in exp if key in got and any(
        str(exp[key][f]) != str(got[key][f]) for f in FIELDS)]
    mismatched += [key for key in exp if key in got and (
        bool(exp[key]["pcl_corroborated"]) != bool(got[key]["pcl_corroborated"]) or
        _listed(exp[key]["pcl_record_ids"]) != _listed(got[key]["pcl_record_ids"]) or
        _listed(exp[key]["wire_port_ids"]) != _listed(got[key]["wire_port_ids"]))]
    report = {"run_links": len(exp), "recomputed_links": len(got),
              "only_in_run": len(set(exp) - set(got)), "only_recomputed": len(set(got) - set(exp)),
              "field_mismatches": len(set(mismatched))}
    report["identical"] = (report["only_in_run"] == 0 and report["only_recomputed"] == 0
                           and report["field_mismatches"] == 0)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
