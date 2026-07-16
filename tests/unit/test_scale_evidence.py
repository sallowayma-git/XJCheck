from __future__ import annotations

import ezdxf

from dwg_audit.extract.extraction_census import build_extraction_census
from dwg_audit.extract.scale_evidence import build_file_scale_evidence
from dwg_audit.extract.scale_evidence import build_file_transform_fidelity
from dwg_audit.extract.scale_evidence import build_project_scale_evidence
from dwg_audit.extract.scale_evidence import extract_unit_candidates


def test_unitless_census_is_unresolved_and_never_applied() -> None:
    record = build_file_scale_evidence(
        {
            "file_id": "F1",
            "filename": "a.dwg",
            "units": 0,
            "units_name": "Unitless",
            "scale_status": "UNRESOLVED",
        }
    )
    assert record.scale_status == "UNRESOLVED"
    assert record.evidence_state == "UNRESOLVED"
    assert record.applied_to_geometry is False
    assert record.declared_ready_for_mm_normalization is False
    assert "UNITS_UNSPECIFIED" in record.evidence_codes


def test_declared_millimetres_is_ready_but_not_applied() -> None:
    record = build_file_scale_evidence(
        {
            "file_id": "F2",
            "filename": "b.dwg",
            "units": 4,
            "units_name": "Millimeters",
            "scale_status": "DECLARED",
        }
    )
    assert record.scale_status == "DECLARED"
    assert record.evidence_state == "DECLARED"
    assert record.declared_ready_for_mm_normalization is True
    assert record.applied_to_geometry is False


def test_census_unresolved_conflicts_with_nonzero_declared_units() -> None:
    record = build_file_scale_evidence(
        {
            "file_id": "F2-CONFLICT",
            "filename": "contradictory.dwg",
            "units": 4,
            "units_name": "Millimeters",
            "scale_status": "UNRESOLVED",
        }
    )

    assert record.scale_status == "CONFLICT"
    assert record.evidence_state == "CONFLICT"
    assert record.declared_ready_for_mm_normalization is False
    assert record.applied_to_geometry is False
    assert "CENSUS_SCALE_STATUS_CONTRADICTION" in record.evidence_codes

    transform = build_file_transform_fidelity(
        {
            "file_id": "F2-CONFLICT",
            "ocs_wcs_status": "MEASURED_IDENTITY",
            "nested_block_units_status": "MEASURED_ALIGNED",
        },
        scale_record=record,
    )
    assert transform.millimetre_readiness == "NOT_READY_SCALE"


def test_lexical_candidates_do_not_silently_resolve_unitless() -> None:
    record = build_file_scale_evidence(
        {
            "file_id": "F3",
            "filename": "c.dwg",
            "units": 0,
            "units_name": "Unitless",
            "scale_status": "UNRESOLVED",
        },
        candidate_texts=["单位: mm", "scale note"],
    )
    assert record.scale_status == "CANDIDATE"
    assert record.evidence_state == "CANDIDATE"
    assert record.candidate_units == ("Millimeters",)
    assert record.applied_to_geometry is False
    assert record.declared_ready_for_mm_normalization is False


def test_declared_vs_candidate_conflict_is_explicit() -> None:
    record = build_file_scale_evidence(
        {
            "file_id": "F4",
            "units": 4,
            "units_name": "Millimeters",
        },
        candidate_texts=["inches"],
    )
    assert record.scale_status == "CONFLICT"
    assert record.evidence_state == "CONFLICT"
    assert "DECLARED_VS_CANDIDATE_CONFLICT" in record.evidence_codes
    assert record.applied_to_geometry is False


def test_extract_unit_candidates_is_deterministic() -> None:
    assert extract_unit_candidates(["MM", "毫米", "cm", "unknown"]) == [
        "Centimeters",
        "Millimeters",
    ]


def test_transform_fidelity_blocks_mm_when_non_uniform() -> None:
    scale = build_file_scale_evidence(
        {"file_id": "F5", "units": 4, "units_name": "Millimeters"}
    )
    transform = build_file_transform_fidelity(
        {
            "file_id": "F5",
            "virtual_expansion_warnings": [
                {
                    "code": "NON_UNIFORM_INSERT_SCALE",
                    "message": "non-uniform",
                    "block_name": "B1",
                }
            ],
            "virtual_expansion_failures": [],
            "ocs_wcs_status": "MEASURED_IDENTITY",
            "nested_block_units_status": "MEASURED_ALIGNED",
            "ocs_identity_count": 3,
            "ocs_non_identity_count": 0,
            "ocs_unreadable_count": 0,
        },
        scale_record=scale,
    )
    assert transform.non_uniform_insert_count == 1
    assert transform.millimetre_readiness == "NOT_READY_TRANSFORM"
    assert transform.ocs_wcs_status == "MEASURED_IDENTITY"
    assert transform.review_required is True


def test_measured_identity_path_is_pending_promotion_not_applied() -> None:
    scale = build_file_scale_evidence(
        {"file_id": "F6", "units": 4, "units_name": "Millimeters"}
    )
    transform = build_file_transform_fidelity(
        {
            "file_id": "F6",
            "virtual_expansion_warnings": [],
            "virtual_expansion_failures": [],
            "ocs_wcs_status": "MEASURED_IDENTITY",
            "nested_block_units_status": "MEASURED_ALIGNED",
            "ocs_identity_count": 10,
            "ocs_non_identity_count": 0,
            "nested_block_units_aligned_count": 2,
        },
        scale_record=scale,
    )
    assert transform.millimetre_readiness == "MEASURED_PENDING_PROMOTION"
    assert "MEASURED_MM_PATH_PENDING_PROMOTION" in transform.evidence_codes
    assert transform.review_required is True


def test_partial_identity_ocs_measurement_blocks_mm_readiness() -> None:
    scale = build_file_scale_evidence(
        {"file_id": "F6-OCS", "units": 4, "units_name": "Millimeters"}
    )
    transform = build_file_transform_fidelity(
        {
            "file_id": "F6-OCS",
            "virtual_expansion_warnings": [],
            "virtual_expansion_failures": [],
            "ocs_wcs_status": "MEASURED_IDENTITY_PARTIAL",
            "nested_block_units_status": "MEASURED_ALIGNED",
            "ocs_identity_count": 9,
            "ocs_unreadable_count": 1,
            "nested_block_units_aligned_count": 2,
        },
        scale_record=scale,
    )

    assert transform.millimetre_readiness == "NOT_READY_OCS_WCS"
    assert "OCS_WCS_MEASURED_IDENTITY_PARTIAL" in transform.evidence_codes
    assert "OCS_WCS_BLOCKS_MM_READINESS" in transform.evidence_codes


def test_partial_nested_unit_measurement_blocks_mm_readiness() -> None:
    scale = build_file_scale_evidence(
        {"file_id": "F6-NESTED", "units": 4, "units_name": "Millimeters"}
    )
    transform = build_file_transform_fidelity(
        {
            "file_id": "F6-NESTED",
            "virtual_expansion_warnings": [],
            "virtual_expansion_failures": [],
            "ocs_wcs_status": "MEASURED_IDENTITY",
            "nested_block_units_status": "MEASURED_ALIGNED_PARTIAL",
            "ocs_identity_count": 10,
            "nested_block_units_aligned_count": 2,
            "nested_block_units_unreadable_count": 1,
        },
        scale_record=scale,
    )

    assert transform.millimetre_readiness == "NOT_READY_NESTED_BLOCK_UNITS"
    assert "NESTED_BLOCK_UNITS_MEASURED_ALIGNED_PARTIAL" in transform.evidence_codes
    assert "NESTED_BLOCK_UNITS_BLOCK_MM_READINESS" in transform.evidence_codes


def test_clean_measured_path_remains_shadow_only_and_compatible() -> None:
    bundle = build_project_scale_evidence(
        [
            {
                "file_id": "CLEAN",
                "units": 4,
                "units_name": "Millimeters",
                "scale_status": "DECLARED",
                "virtual_expansion_warnings": [],
                "virtual_expansion_failures": [],
                "ocs_wcs_status": "MEASURED_IDENTITY",
                "nested_block_units_status": "MEASURED_ALIGNED",
                "ocs_identity_count": 10,
                "nested_block_units_aligned_count": 2,
            }
        ],
        project_id="P-CLEAN",
    )

    assert bundle.files[0].declared_ready_for_mm_normalization is True
    assert bundle.files[0].applied_to_geometry is False
    assert bundle.transforms[0].millimetre_readiness == "MEASURED_PENDING_PROMOTION"
    assert bundle.summary["measured_pending_promotion_count"] == 1
    assert bundle.summary["applied_to_geometry_count"] == 0
    assert bundle.summary["canonical_millimetre_ready"] is False


def test_unmeasured_ocs_still_blocks_mm_readiness() -> None:
    scale = build_file_scale_evidence(
        {"file_id": "F7", "units": 4, "units_name": "Millimeters"}
    )
    transform = build_file_transform_fidelity(
        {
            "file_id": "F7",
            "virtual_expansion_warnings": [],
            "virtual_expansion_failures": [],
        },
        scale_record=scale,
    )
    assert transform.ocs_wcs_status == "UNMEASURED"
    assert transform.millimetre_readiness == "NOT_READY_OCS_WCS"


def test_project_bundle_summary_forbids_geometry_mutation() -> None:
    bundle = build_project_scale_evidence(
        [
            {
                "file_id": "A",
                "units": 0,
                "units_name": "Unitless",
                "scale_status": "UNRESOLVED",
                "virtual_expansion_warnings": [],
                "virtual_expansion_failures": [],
                "ocs_wcs_status": "MEASURED_IDENTITY",
                "nested_block_units_status": "MEASURED_UNITLESS",
            },
            {
                "file_id": "B",
                "units": 4,
                "units_name": "Millimeters",
                "scale_status": "DECLARED",
                "virtual_expansion_warnings": [
                    {"code": "NON_UNIFORM_INSERT_SCALE", "message": "x"}
                ],
                "virtual_expansion_failures": [],
                "ocs_wcs_status": "MEASURED_IDENTITY",
                "nested_block_units_status": "MEASURED_ALIGNED",
            },
        ],
        project_id="P001",
    )
    assert bundle.summary["geometry_mutation_forbidden"] is True
    assert bundle.summary["canonical_millimetre_ready"] is False
    assert bundle.summary["applied_to_geometry_count"] == 0
    assert bundle.summary["file_count"] == 2
    assert bundle.summary["non_uniform_insert_count"] == 1


def test_census_measures_identity_ocs_and_aligned_block_units() -> None:
    doc = ezdxf.new("R2018")
    doc.units = 4
    block = doc.blocks.new("SYM")
    block.units = 4
    block.add_line((0, 0), (10, 0))
    doc.modelspace().add_blockref("SYM", (1, 2))
    doc.modelspace().add_line((0, 0), (5, 0))

    census = build_extraction_census(doc)
    payload = census.to_dict()

    assert payload["ocs_wcs_status"] == "MEASURED_IDENTITY"
    assert payload["ocs_identity_count"] >= 2
    assert payload["ocs_non_identity_count"] == 0
    assert payload["nested_block_units_status"] == "MEASURED_ALIGNED"
    assert payload["nested_block_units_aligned_count"] >= 1

    scale = build_file_scale_evidence(payload)
    transform = build_file_transform_fidelity(payload, scale_record=scale)
    assert transform.millimetre_readiness == "MEASURED_PENDING_PROMOTION"
    assert transform.ocs_wcs_status == "MEASURED_IDENTITY"


def test_census_detects_non_identity_ocs_extrusion() -> None:
    doc = ezdxf.new("R2018")
    doc.units = 4
    msp = doc.modelspace()
    line = msp.add_line((0, 0), (1, 0))
    line.dxf.extrusion = (0, 1, 0)

    census = build_extraction_census(doc)
    assert census.ocs_wcs_status == "MEASURED_NON_IDENTITY"
    assert census.ocs_non_identity_count >= 1

    transform = build_file_transform_fidelity(
        census.to_dict(),
        scale_record=build_file_scale_evidence(census.to_dict()),
    )
    assert transform.millimetre_readiness == "NOT_READY_OCS_WCS"
