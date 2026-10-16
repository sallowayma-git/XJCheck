from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

from dwg_audit.services.execution import run_analysis_workflow


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    plan = ROOT / ".planning/superworks-adapter"
    corpus = json.loads((plan / "corpus_manifest.json").read_text(encoding="utf-8"))
    project = next(item for item in corpus["projects"] if item["project_id"] == "p067")
    source = next(item for item in project["files"] if item["file_id"] == "F0013")
    base = ROOT / ".tmp/precision_loop_20261015/p067_single_visibility_with_prj"
    input_root = base / "input"
    output_root = base / "output"
    input_root.mkdir(parents=True, exist_ok=False)
    output_root.mkdir(parents=True, exist_ok=False)

    source_path = Path(source["path"])
    if sha256(source_path) != source["sha256"]:
        raise AssertionError("Frozen source DWG hash mismatch")
    shutil.copy2(source_path, input_root / source_path.name)
    for xml_path in project["xml"]:
        shutil.copy2(xml_path, input_root / Path(xml_path).name)
    for project_file in Path(project["input_root"]).glob("*.prj"):
        shutil.copy2(project_file, input_root / project_file.name)

    cached_dxf = Path(source["dxf_path"])
    if sha256(cached_dxf) != source["dxf_sha256"]:
        raise AssertionError("Frozen source DXF hash mismatch")
    cache = output_root / "cache/converted_dxf"
    cache.mkdir(parents=True)
    shutil.copy2(cached_dxf, cache / f'F0001_{source["sha256"][:8]}.dxf')

    result = run_analysis_workflow(input_root=input_root, output_root=output_root, include_audit=True)
    if len(result.project_dirs) != 1:
        raise RuntimeError(f"expected one page result, got {len(result.project_dirs)}")
    project_dir = result.project_dirs[0]
    pairs = pd.read_parquet(project_dir / "findings/pairs.parquet")
    backplate = []
    for row in pairs.to_dict(orient="records"):
        evidence = row.get("evidence") or "{}"
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        mapping = evidence.get("table_mapping") or {}
        if mapping.get("mapping_mode") == "backplate_virtual_table":
            backplate.append({
                "pair_id": row["pair_id"],
                "status": row["status"],
                "left_value": row["left_value"],
                "right_value": row["right_value"],
                "composite_device_instance": mapping.get("composite_device_instance"),
                "header_prefix": mapping.get("header_prefix"),
                "row_number": mapping.get("row_number"),
            })

    full_findings = ROOT / ".tmp/precision_loop_20261015/p057_slice_10/p067/26000_220kV/findings"
    full_pairs = pd.read_parquet(full_findings / "pairs.parquet")
    full_selected = []
    for row in full_pairs.to_dict(orient="records"):
        evidence = row.get("evidence") or "{}"
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        mapping = evidence.get("table_mapping") or {}
        if mapping.get("mapping_mode") == "backplate_virtual_table" and row.get("sheet_id") == "S0013":
            full_selected.append({
                "status": row["status"],
                "left_value": row["left_value"],
                "right_value": row["right_value"],
                "composite_device_instance": mapping.get("composite_device_instance"),
                "header_prefix": mapping.get("header_prefix"),
                "row_number": mapping.get("row_number"),
            })
    key = lambda item: (item["status"], item["left_value"], item["right_value"],
                        item["composite_device_instance"], item["header_prefix"], item["row_number"])
    isolated_rows = sorted(map(key, backplate))
    full_rows = sorted(map(key, full_selected))
    if isolated_rows != full_rows:
        raise AssertionError(f"Single-page mappings differ from 77-project replay: {len(backplate)} vs {len(full_selected)}")

    issues_path = project_dir / "audit/issues.json"
    issues = json.loads(issues_path.read_text(encoding="utf-8")) if issues_path.exists() else []
    summary = {
        "input_source": source_path.as_posix(),
        "source_sha256": source["sha256"],
        "cached_dxf": cached_dxf.as_posix(),
        "project_dir": project_dir.as_posix(),
        "pair_count": len(pairs),
        "backplate_mapping_count": len(backplate),
        "backplate_mapping_status_counts": pd.Series([item["status"] for item in backplate]).value_counts().to_dict(),
        "backplate_device_instances": sorted({item["composite_device_instance"] for item in backplate}),
        "backplate_contradiction_count": len(pd.read_parquet(project_dir / "findings/sw_backplate_contradictions.parquet")),
        "issue_count": len(issues),
        "matches_full_replay_page_mappings": True,
        "backplate_mappings": backplate,
    }
    (base / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
