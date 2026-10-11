"""Compare replay outputs of a base run and a hooked run: every findings table and issues must match.

Usage: python zero_impact.py <base_dir> <hooked_dir> [<reference_dir>]
Excludes sw_wire_routes* (new diagnostic). Optional reference (e.g. superworks_round13_full) is compared for pairs/issues.
"""
import json
import sys
from pathlib import Path

import pandas as pd

PROJECTS = ["p001", "p003", "p022", "p044", "p050", "p051", "p061", "p071", "p075", "p076"]


def project_dir(root: Path, pid: str) -> Path:
    return Path(json.loads((root / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"])


def findings_frames(directory: Path):
    return {p.name: p for p in sorted((directory / "findings").glob("*.parquet")) if not p.name.startswith("sw_wire_routes")}


def main(base: Path, hooked: Path, reference: Path | None) -> None:
    report = {}
    for pid in PROJECTS:
        b, h = project_dir(base, pid), project_dir(hooked, pid)
        mismatches = []
        fb, fh = findings_frames(b), findings_frames(h)
        if set(fb) != set(fh):
            mismatches.append(("file_set", sorted(set(fb) ^ set(fh))))
        for name in sorted(set(fb) & set(fh)):
            if not pd.read_parquet(fb[name]).equals(pd.read_parquet(fh[name])):
                mismatches.append(("parquet", name))
        ib = json.loads((b / "audit/issues.json").read_text(encoding="utf-8"))
        ih = json.loads((h / "audit/issues.json").read_text(encoding="utf-8"))
        if ib != ih:
            mismatches.append(("issues.json", len(ib), len(ih)))
        if (b / "audit/audit_report.md").read_text(encoding="utf-8") != (h / "audit/audit_report.md").read_text(encoding="utf-8"):
            mismatches.append(("audit_report.md",))
        entry = {"mismatches": mismatches, "pairs": len(pd.read_parquet(fh["pairs.parquet"])),
                 "issues": len(ih), "hooked_has_routes": (h / "findings/sw_wire_routes.parquet").exists()}
        if reference is not None:
            r = project_dir(reference, pid)
            pr = pd.read_parquet(r / "findings/pairs.parquet")
            ph = pd.read_parquet(fh["pairs.parquet"])
            entry["vs_reference_pairs_equal"] = bool(pr.equals(ph))
            entry["vs_reference_pairs_shape"] = [len(pr), len(ph)]
            ir = json.loads((r / "audit/issues.json").read_text(encoding="utf-8"))
            entry["vs_reference_issues_equal"] = ir == ih
            entry["vs_reference_issues_count"] = [len(ir), len(ih)]
        report[pid] = entry
        print(pid, entry, flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=1)[:200])
    out = hooked / "zero_impact.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
