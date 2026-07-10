from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pandas as pd


_COVERAGE_KEYS = (
    "total_texts",
    "audit_scope_texts",
    "assigned_texts",
    "unexplained_texts",
    "unexplained_numeric_texts",
    "unassigned_wire_segments",
    "unclassified_blocks",
    "out_of_scope_texts",
    "coverage_ratio",
    "identity_ok",
    "suspicious_out_of_scope_expansion",
)


def write_baseline_manifest(
    project_dir: Path,
    *,
    alias: str,
    input_root: Path,
    config_path: Path,
    arbitration_paths: list[Path] | None = None,
    output_dir: Path | None = None,
    repo_root: Path | None = None,
) -> Path:
    project_dir = project_dir.resolve()
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    _require_bundle(project_dir, findings_dir, audit_dir)

    baseline_dir = (output_dir or project_dir / "baseline").resolve()
    baseline_dir.mkdir(parents=True, exist_ok=True)
    frozen_config = baseline_dir / "config.yml"
    shutil.copy2(config_path.resolve(), frozen_config)

    frozen_arbitration = []
    arbitration_dir = baseline_dir / "arbitration"
    for source in arbitration_paths or []:
        source = source.resolve()
        arbitration_dir.mkdir(parents=True, exist_ok=True)
        target = arbitration_dir / source.name
        shutil.copy2(source, target)
        frozen_arbitration.append(
            {
                "path": target.relative_to(baseline_dir).as_posix(),
                "sha256": _file_sha256(target),
            }
        )

    pairs = pd.read_parquet(findings_dir / "pairs.parquet")
    issues = pd.read_parquet(audit_dir / "issues.parquet")
    junctions = pd.read_parquet(findings_dir / "wire_junctions.parquet")
    networks = pd.read_parquet(findings_dir / "wire_networks.parquet")
    findings_payload = _read_json(findings_dir / "findings.json")
    topology_shadow = _read_json(audit_dir / "topology_shadow_report.json")
    geometry_observation_summary = _read_optional_json(
        findings_dir / "geometry_shadow_observation_summary.json"
    )
    pair_geometry_summary = _read_optional_json(
        findings_dir / "pair_geometry_shadow_summary.json"
    )
    project_manifest = _read_json(project_dir / "manifest.json")

    pair_kind_counts = _value_counts(pairs, "pair_kind")
    pair_status_counts = _value_counts(pairs, "status")
    issue_rule_counts = _value_counts(issues, "rule_id")
    issue_rule_pair_kind_counts = _group_counts(issues, ["rule_id", "pair_kind"])
    coverage = findings_payload.get("entity_coverage_summary") or {}
    pair_ids = set(pairs["pair_id"].dropna().astype(str)) if "pair_id" in pairs else set()
    issue_pair_ids = set(issues["pair_id"].dropna().astype(str)) if "pair_id" in issues else set()

    artifacts = _artifact_inventory(project_dir, findings_dir, audit_dir)
    manifest = {
        "schema_version": 1,
        "phase": "104",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "worktree": _worktree_identity(repo_root.resolve()) if repo_root else None,
        "project": {
            "alias": alias,
            "input_root": str(input_root.resolve()),
            "project_dir": str(project_dir),
            "source_manifest_sha256": _file_sha256(project_dir / "manifest.json"),
            "file_count": int(project_manifest.get("file_count") or 0),
            "sheet_count": int(project_manifest.get("sheet_count") or 0),
        },
        "config": {
            "path": frozen_config.relative_to(baseline_dir).as_posix(),
            "sha256": _file_sha256(frozen_config),
        },
        "artifacts": {"files": artifacts},
        "metrics": {
            "pair_count": len(pairs),
            "pair_kind_counts": pair_kind_counts,
            "pair_status_counts": pair_status_counts,
            "issue_count": len(issues),
            "issue_rule_counts": issue_rule_counts,
            "issue_rule_pair_kind_counts": issue_rule_pair_kind_counts,
            "coverage": {key: coverage.get(key) for key in _COVERAGE_KEYS},
            "legacy_topology": {
                "wire_junction_count": len(junctions),
                "wire_network_count": len(networks),
            },
            "topology_shadow": {
                key: topology_shadow.get(key)
                for key in (
                    "candidate_issue_count",
                    "recoverable_issue_count",
                    "recoverable_ratio",
                    "reason_counts",
                    "branch_local_status_counts",
                )
            },
            "graph_shadow": {
                "geometry_observations": geometry_observation_summary,
                "pair_geometry": pair_geometry_summary,
            },
        },
        "redlines": {
            "pair_kind_identity_ok": sum(pair_kind_counts.values()) == len(pairs),
            "pair_status_identity_ok": sum(pair_status_counts.values()) == len(pairs),
            "issue_rule_identity_ok": sum(issue_rule_counts.values()) == len(issues),
            "issue_pair_ids_resolve": issue_pair_ids <= pair_ids,
            "coverage_identity_ok": bool(coverage.get("identity_ok")),
            "no_out_of_scope_expansion": not bool(coverage.get("suspicious_out_of_scope_expansion")),
            "topology_shadow_bounds_ok": int(topology_shadow.get("recoverable_issue_count") or 0)
            <= int(topology_shadow.get("candidate_issue_count") or 0),
            "geometry_observation_state_identity_ok": _geometry_observation_identity_ok(
                geometry_observation_summary
            ),
            "geometry_observation_states_valid": set(
                (geometry_observation_summary.get("state_counts") or {}).keys()
            ) <= {"ASSERTED", "POSSIBLE", "REJECTED", "UNKNOWN"},
        },
        "arbitration": frozen_arbitration,
    }
    output_path = baseline_dir / "baseline_manifest.json"
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _require_bundle(project_dir: Path, findings_dir: Path, audit_dir: Path) -> None:
    required = (
        project_dir / "manifest.json",
        findings_dir / "findings.json",
        findings_dir / "pairs.parquet",
        findings_dir / "wire_junctions.parquet",
        findings_dir / "wire_networks.parquet",
        audit_dir / "issues.parquet",
        audit_dir / "topology_shadow_report.json",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Baseline bundle is incomplete: {', '.join(missing)}")


def _artifact_inventory(project_dir: Path, findings_dir: Path, audit_dir: Path) -> list[dict[str, Any]]:
    paths = [project_dir / "manifest.json"]
    paths.extend(path for root in (findings_dir, audit_dir) for path in root.rglob("*") if path.is_file())
    inventory = []
    for path in sorted(paths, key=lambda item: item.relative_to(project_dir).as_posix()):
        entry: dict[str, Any] = {
            "path": path.relative_to(project_dir).as_posix(),
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        if path.suffix.lower() == ".parquet":
            entry["rows"] = len(pd.read_parquet(path))
        inventory.append(entry)
    return inventory


def _worktree_identity(repo_root: Path) -> dict[str, Any]:
    head = _git_output(repo_root, ["rev-parse", "HEAD"]).strip()
    status = _git_output(repo_root, ["status", "--short"])
    diff = _git_bytes(repo_root, ["diff", "--binary", "HEAD", "--"])
    fingerprint = sha256()
    fingerprint.update(status.encode("utf-8"))
    fingerprint.update(diff)
    untracked = _git_bytes(repo_root, ["ls-files", "--others", "--exclude-standard", "-z"])
    for raw_path in sorted(path for path in untracked.split(b"\0") if path):
        relative = raw_path.decode("utf-8")
        path = repo_root / relative
        if not path.is_file():
            continue
        fingerprint.update(raw_path)
        fingerprint.update(path.read_bytes())
    return {
        "head": head,
        "dirty": bool(status.strip()),
        "dirty_files": status.splitlines(),
        "diff_sha256": fingerprint.hexdigest(),
    }


def _value_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame:
        return {}
    return {
        str(key): int(value)
        for key, value in frame[column].fillna("<null>").value_counts().sort_index().items()
    }


def _group_counts(frame: pd.DataFrame, columns: list[str]) -> dict[str, int]:
    if any(column not in frame for column in columns):
        return {}
    grouped = frame[columns].fillna("<null>").value_counts().sort_index()
    return {" | ".join(str(value) for value in key): int(count) for key, count in grouped.items()}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_json(path: Path) -> dict[str, Any]:
    return _read_json(path) if path.exists() else {}


def _geometry_observation_identity_ok(summary: dict[str, Any]) -> bool:
    if not summary:
        return True
    state_counts = summary.get("state_counts") or {}
    return sum(int(value) for value in state_counts.values()) == int(
        summary.get("observation_count") or 0
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_output(repo_root: Path, args: list[str]) -> str:
    return _git_bytes(repo_root, args).decode("utf-8", errors="replace")


def _git_bytes(repo_root: Path, args: list[str]) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    return result.stdout
