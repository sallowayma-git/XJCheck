"""GAP2-PAIR join of method-S links with the round19 coverage state (read-only).

Writes sim/links_joined.parquet: one row per new method-S link with project-qualified flags
  in_unc        the port is eligible and not consumed_with_internal in round19 (uncovered)
  consumed      the port is consumed by a non-discard pair (round19 sw_port_coverage.consumed)
  eligible, int_consumed, reason   round19 coverage fields of the port
  elem_ident    endpoint identity of the link's internal element ('' when none)
  guard_ok      True when elem_ident is empty (the element-identity guard keeps the link)
Keys are (project, port_id) because a port_id repeats across projects.
Usage: python g2p_join.py <sim_dir> <round_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def proj_of(path: Path) -> str:
    return path.parent.parent.parent.name


def main(sim_dir: Path, round_dir: Path):
    links = pd.read_parquet(sim_dir / "sim_links.parquet")
    unc = pd.read_parquet(sim_dir / "uncovered.parquet") if (sim_dir / "uncovered.parquet").exists() else None
    if unc is None:
        raise SystemExit("copy or link .tmp/gap2p_base/uncovered.parquet to the sim dir first")
    cov_rows = []
    for f in sorted(round_dir.glob("p*/*/findings/sw_port_coverage.parquet")):
        d = pd.read_parquet(f)
        d["project"] = proj_of(f)
        cov_rows.append(d[["project", "port_id", "eligible", "consumed", "consumed_with_internal", "reason_codes"]])
    cov = pd.concat(cov_rows).drop_duplicates(["project", "port_id"]).set_index(["project", "port_id"])
    ident = {}
    for f in sorted(round_dir.glob("p*/*/findings/sw_ports.parquet")):
        d = pd.read_parquet(f, columns=["record_id", "endpoint_identity"])
        p = proj_of(f)
        for rid, val in zip(d["record_id"], d["endpoint_identity"]):
            ident[(p, rid)] = val if isinstance(val, str) else ""
    unc_key = set(zip(unc["project"], unc["port_id"]))
    out = links.copy()
    keys = list(zip(out["project"], out["port_id"]))
    out["in_unc"] = [k in unc_key for k in keys]
    out["consumed"] = [bool(cov["consumed"].get(k, False)) for k in keys]
    out["eligible"] = [bool(cov["eligible"].get(k, False)) for k in keys]
    out["int_consumed"] = [bool(cov["consumed_with_internal"].get(k, False)) for k in keys]
    out["reason"] = [str(cov["reason_codes"].get(k, "[]")) for k in keys]
    out["elem_ident"] = [ident.get((p, e), "") for p, e in zip(out["project"], out["element_port_id"].fillna(""))]
    out["guard_ok"] = out["elem_ident"].eq("")
    out.to_parquet(sim_dir / "links_joined.parquet", index=False)
    print("links", len(out), "in_unc", int(out.in_unc.sum()), "consumed", int(out.consumed.sum()),
          "guard_ok", int(out.guard_ok.sum()))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
