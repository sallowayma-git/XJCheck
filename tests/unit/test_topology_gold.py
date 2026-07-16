from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from dwg_audit.report.topology_gold import CERTIFIED_STATUS
from dwg_audit.report.topology_gold import COMPLETE_REVIEW_STATUS
from dwg_audit.report.topology_gold import HELDOUT_USAGE
from dwg_audit.report.topology_gold import HUMAN_LABEL_BASIS
from dwg_audit.report.topology_gold import SCHEMA_VERSION
from dwg_audit.report.topology_gold import build_topology_gold_template
from dwg_audit.report.topology_gold import load_topology_gold_pack
from dwg_audit.report.topology_gold import validate_topology_gold_pack


def test_pending_template_is_valid_but_never_project_measured(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"

    pack = build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )
    validation = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert sorted(path.name for path in pack_dir.iterdir()) == [
        "connectivity_members.csv",
        "junctions.csv",
        "manifest.json",
        "open_endpoints.csv",
        "pages.csv",
    ]
    assert pack.manifest["schema_version"] == SCHEMA_VERSION
    assert pack.manifest["reviewer"] is None
    assert pack.manifest["reviewed_at"] is None
    assert pack.manifest["label_basis"] is None
    assert pack.manifest["not_a_human_gold_standard"] is True
    assert len(pack.pages) == 1
    assert pack.pages[0]["dwg_sha256"] == "1" * 64
    assert not pack.junctions
    assert not pack.connectivity_members
    assert not pack.open_endpoints
    assert validation.valid is True
    assert validation.certification_ready is False
    assert validation.project_scope is False


def test_human_certified_pack_requires_real_review_evidence(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="validation",
        output_dir=pack_dir,
    )
    manifest = _manifest(pack_dir)
    manifest["status"] = CERTIFIED_STATUS
    manifest["reviewer"] = ""
    manifest["reviewed_at"] = "2026-07-13T12:00:00"
    manifest["label_basis"] = "MACHINE_PREDICTION"
    _write_manifest(pack_dir, manifest)

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="validation",
    )

    assert result.valid is False
    assert result.certification_ready is False
    assert result.project_scope is False
    assert _has_error(result, "REVIEWER_MISSING")
    assert _has_error(result, "REVIEW_TIME_INVALID")
    assert _has_error(result, "LABEL_BASIS_INVALID")
    assert _has_error(result, "HUMAN_GOLD_DISCLAIMER_INVALID")
    assert _has_error(result, "REVIEW_INCOMPLETE")
    assert _has_error(result, "CERTIFIED_REVIEW_STATUS_INVALID")
    assert _has_error(result, "NON_VACUOUS_TOPOLOGY_GOLD_REQUIRED")


def test_certified_empty_label_tables_never_become_project_scope(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="validation",
        output_dir=pack_dir,
    )
    _certify_manifest(pack_dir)
    page = _read_rows(pack_dir / "pages.csv")[0]
    page.update(
        {
            "review_status": COMPLETE_REVIEW_STATUS,
            "junctions_review_complete": "true",
            "connectivity_review_complete": "true",
            "open_endpoints_review_complete": "true",
        }
    )
    _write_rows(pack_dir / "pages.csv", [page])

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="validation",
    )

    assert result.valid is False
    assert result.certification_ready is False
    assert result.project_scope is False
    assert _has_error(result, "NON_VACUOUS_TOPOLOGY_GOLD_REQUIRED")


def test_complete_human_review_can_be_certified_for_exact_project_scope(
    tmp_path: Path,
) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="validation",
        output_dir=pack_dir,
    )
    _certify_manifest(pack_dir)
    page = _read_rows(pack_dir / "pages.csv")[0]
    page.update(
        {
            "review_status": COMPLETE_REVIEW_STATUS,
            "junctions_review_complete": "true",
            "connectivity_review_complete": "true",
            "open_endpoints_review_complete": "true",
        }
    )
    _write_rows(pack_dir / "pages.csv", [page])
    _write_rows(
        pack_dir / "junctions.csv",
        [
            {
                "junction_id": "J1",
                "sheet_id": "S0001",
                "file_id": "F0001",
                "x": "1.0",
                "y": "2.0",
                "expected_connected": "true",
                "source_handles_json": '["A1", "A2"]',
                "label_source": HUMAN_LABEL_BASIS,
                "notes": "reviewed on source drawing",
            }
        ],
    )
    _write_rows(
        pack_dir / "connectivity_members.csv",
        [
            {
                "network_id": "N1",
                "member_id": "M1",
                "sheet_id": "S0001",
                "file_id": "F0001",
                "source_handle": "A1",
                "x": "1.0",
                "y": "2.0",
                "label_source": HUMAN_LABEL_BASIS,
                "notes": "",
            },
            {
                "network_id": "N1",
                "member_id": "M2",
                "sheet_id": "S0001",
                "file_id": "F0001",
                "source_handle": "A2",
                "x": "3.0",
                "y": "4.0",
                "label_source": HUMAN_LABEL_BASIS,
                "notes": "",
            },
        ],
    )
    _write_rows(
        pack_dir / "open_endpoints.csv",
        [
            {
                "endpoint_id": "E1",
                "sheet_id": "S0001",
                "file_id": "F0001",
                "source_handle": "A1",
                "x": "1.0",
                "y": "2.0",
                "expected_open": "false",
                "label_source": HUMAN_LABEL_BASIS,
                "notes": "",
            }
        ],
    )

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="validation",
    )

    assert result.valid is True, result.errors
    assert result.certification_ready is True
    assert result.project_scope is True


def test_stale_dwg_hash_is_rejected(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )
    page = _read_rows(pack_dir / "pages.csv")[0]
    page["dwg_sha256"] = "f" * 64
    _write_rows(pack_dir / "pages.csv", [page])

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert result.valid is False
    assert _has_error(result, "DWG_HASH_MISMATCH")


def test_missing_and_duplicate_page_coverage_are_rejected(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    missing_pack = tmp_path / "missing"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=missing_pack,
    )
    _write_rows(missing_pack / "pages.csv", [])
    missing = validate_topology_gold_pack(
        missing_pack,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    duplicate_pack = tmp_path / "duplicate"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=duplicate_pack,
    )
    page = _read_rows(duplicate_pack / "pages.csv")[0]
    _write_rows(duplicate_pack / "pages.csv", [page, page])
    duplicate = validate_topology_gold_pack(
        duplicate_pack,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert missing.valid is False
    assert _has_error(missing, "PAGE_COVERAGE_MISMATCH")
    assert duplicate.valid is False
    assert _has_error(duplicate, "DUPLICATE_PAGE")


def test_machine_label_and_non_finite_coordinate_are_rejected(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )
    _write_rows(
        pack_dir / "junctions.csv",
        [
            {
                "junction_id": "J1",
                "sheet_id": "S0001",
                "file_id": "F0001",
                "x": "nan",
                "y": "2.0",
                "expected_connected": "true",
                "source_handles_json": '["A1", "A2"]',
                "label_source": "MACHINE_PREDICTION",
                "notes": "",
            }
        ],
    )

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert result.valid is False
    assert _has_error(result, "MACHINE_OR_UNKNOWN_LABEL_SOURCE")
    assert _has_error(result, "NON_FINITE_COORDINATE")


def test_unknown_handle_and_multiple_network_ownership_are_rejected(
    tmp_path: Path,
) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )
    base = {
        "sheet_id": "S0001",
        "file_id": "F0001",
        "x": "1.0",
        "y": "2.0",
        "label_source": HUMAN_LABEL_BASIS,
        "notes": "",
    }
    _write_rows(
        pack_dir / "connectivity_members.csv",
        [
            {**base, "network_id": "N1", "member_id": "M1", "source_handle": "A1"},
            {**base, "network_id": "N2", "member_id": "M2", "source_handle": "A1"},
            {**base, "network_id": "N3", "member_id": "M3", "source_handle": "FFFF"},
        ],
    )

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert result.valid is False
    assert _has_error(result, "MULTIPLE_NETWORK_OWNERSHIP")
    assert _has_error(result, "UNKNOWN_SOURCE_HANDLE")


def test_non_line_handle_cannot_enter_topology_gold(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    findings = project / "findings"
    pd.DataFrame(
        [{"sheet_id": "S0001", "file_id": "F0001", "handle": "TEXT1"}]
    ).to_parquet(findings / "texts.parquet", index=False)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )
    _write_rows(
        pack_dir / "connectivity_members.csv",
        [
            {
                "network_id": "N1",
                "member_id": "M1",
                "sheet_id": "S0001",
                "file_id": "F0001",
                "source_handle": "TEXT1",
                "x": "1.0",
                "y": "2.0",
                "label_source": HUMAN_LABEL_BASIS,
                "notes": "",
            }
        ],
    )

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert result.valid is False
    assert _has_error(result, "UNKNOWN_SOURCE_HANDLE")


def test_missing_annotation_table_fails_closed(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )
    (pack_dir / "open_endpoints.csv").unlink()

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert result.valid is False
    assert _has_error(result, "PACK_LOAD_ERROR")


def test_load_rejects_duplicate_or_changed_table_columns(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )
    (pack_dir / "junctions.csv").write_text(
        "junction_id,junction_id\n",
        encoding="utf-8",
    )

    result = validate_topology_gold_pack(
        pack_dir,
        project_dir=project,
        project_id="P001",
        split="calibration",
    )

    assert result.valid is False
    assert _has_error(result, "PACK_LOAD_ERROR")


def _project_bundle(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    findings = project / "findings"
    findings.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "file_id": "F0001",
                "filename": "04 schematic.dwg",
                "sha256": "1" * 64,
            }
        ]
    ).to_parquet(findings / "source_files.parquet", index=False)
    pd.DataFrame(
        [
            {
                "sheet_id": "S0001",
                "file_id": "F0001",
                "handle": "A1",
            },
            {
                "sheet_id": "S0001",
                "file_id": "F0001",
                "handle": "A2",
            },
        ]
    ).to_parquet(findings / "lines.parquet", index=False)
    (project / "extraction_completeness.json").write_text(
        json.dumps(
            {
                "analysis_status": "COMPLETE",
                "clean_conclusion_allowed": True,
                "incomplete_page_count": 0,
                "pages": [
                    {
                        "sheet": "S0001",
                        "file": "F0001",
                        "filename": "04 schematic.dwg",
                        "audit_role": "primary",
                        "audit_disposition": "audit_required",
                        "status": "COMPLETE",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return project


def _certify_manifest(pack_dir: Path) -> None:
    manifest = _manifest(pack_dir)
    manifest.update(
        {
            "status": CERTIFIED_STATUS,
            "annotation_status": COMPLETE_REVIEW_STATUS,
            "reviewer": "reviewer@example.com",
            "reviewed_at": "2026-07-13T12:00:00+08:00",
            "label_basis": HUMAN_LABEL_BASIS,
            "not_a_human_gold_standard": False,
            "heldout_usage": HELDOUT_USAGE,
            "review_complete": {
                "junctions": True,
                "connectivity": True,
                "open_endpoints": True,
            },
        }
    )
    _write_manifest(pack_dir, manifest)


def _manifest(pack_dir: Path) -> dict[str, object]:
    return json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(pack_dir: Path, manifest: dict[str, object]) -> None:
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        columns = list(csv.DictReader(handle).fieldnames or [])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _has_error(result, code: str) -> bool:
    return any(error.startswith(code + ":") for error in result.errors)


def test_public_loader_reads_the_generated_pack(tmp_path: Path) -> None:
    project = _project_bundle(tmp_path)
    pack_dir = tmp_path / "gold"
    build_topology_gold_template(
        project,
        project_id="P001",
        split="calibration",
        output_dir=pack_dir,
    )

    loaded = load_topology_gold_pack(pack_dir)

    assert loaded.directory == pack_dir
    assert loaded.manifest["status"] == "PENDING"
    assert loaded.pages[0]["sheet_id"] == "S0001"
