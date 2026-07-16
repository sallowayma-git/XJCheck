"""Fail-closed drawing unit and scale evidence.

This module never silently applies units to geometry.  Declared INSUNITS values
are recorded as evidence only.  Optional candidate unit strings (for example
from title-block measure text) remain CANDIDATE / CONFLICT and cannot authorize
millimetre normalization or tolerance changes until an explicit promotion path
is added later.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any


SCALE_EVIDENCE_SCHEMA_VERSION = "scale-evidence-v1"
SCALE_SUMMARY_SCHEMA_VERSION = "scale-evidence-summary-v1"
TRANSFORM_FIDELITY_SCHEMA_VERSION = "transform-fidelity-v1"

# Explicit unit map for common AutoCAD INSUNITS codes.  Unknown codes stay
# review-only with a stable name rather than inventing a conversion factor.
_INSUNITS_NAMES: dict[int, str] = {
    0: "Unitless",
    1: "Inches",
    2: "Feet",
    3: "Miles",
    4: "Millimeters",
    5: "Centimeters",
    6: "Meters",
    7: "Kilometers",
    8: "Microinches",
    9: "Mils",
    10: "Yards",
    11: "Angstroms",
    12: "Nanometers",
    13: "Microns",
    14: "Decimeters",
    15: "Decameters",
    16: "Hectometers",
    17: "Gigameters",
    18: "Astronomical",
    19: "LightYears",
    20: "Parsecs",
}

# Candidate lexical cues.  These never auto-resolve scale.
_UNIT_CANDIDATE_TOKENS: dict[str, str] = {
    "mm": "Millimeters",
    "millimeter": "Millimeters",
    "millimeters": "Millimeters",
    "毫米": "Millimeters",
    "cm": "Centimeters",
    "centimeter": "Centimeters",
    "centimeters": "Centimeters",
    "厘米": "Centimeters",
    "m": "Meters",
    "meter": "Meters",
    "meters": "Meters",
    "米": "Meters",
    "in": "Inches",
    "inch": "Inches",
    "inches": "Inches",
    "ft": "Feet",
    "foot": "Feet",
    "feet": "Feet",
}

_DECLARED_READY_UNITS = frozenset(
    {
        "Millimeters",
        "Centimeters",
        "Meters",
        "Inches",
        "Feet",
    }
)


@dataclass(frozen=True, slots=True)
class ScaleEvidenceRecord:
    schema_version: str
    file_id: str
    filename: str | None
    units: int | None
    units_name: str | None
    scale_status: str
    evidence_state: str
    authority: str
    declared_ready_for_mm_normalization: bool
    applied_to_geometry: bool
    candidate_units: tuple[str, ...] = ()
    evidence_codes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_units"] = list(self.candidate_units)
        value["evidence_codes"] = list(self.evidence_codes)
        value["notes"] = list(self.notes)
        value["source_refs"] = list(self.source_refs)
        return value


@dataclass(frozen=True, slots=True)
class TransformFidelityRecord:
    schema_version: str
    file_id: str
    filename: str | None
    non_uniform_insert_count: int
    virtual_expansion_failure_count: int
    virtual_expansion_warning_count: int
    ocs_wcs_status: str
    nested_block_units_status: str
    millimetre_readiness: str
    review_required: bool
    evidence_codes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence_codes"] = list(self.evidence_codes)
        value["notes"] = list(self.notes)
        return value


@dataclass(frozen=True, slots=True)
class ScaleEvidenceBundle:
    schema_version: str
    project_id: str
    files: tuple[ScaleEvidenceRecord, ...]
    transforms: tuple[TransformFidelityRecord, ...]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "file_count": len(self.files),
            "files": [item.to_dict() for item in self.files],
            "transforms": [item.to_dict() for item in self.transforms],
            "summary": dict(self.summary),
        }


def unit_name_for_insunits(value: int | None) -> str | None:
    if value is None:
        return None
    return _INSUNITS_NAMES.get(int(value), "Unknown")


def extract_unit_candidates(texts: Iterable[str] | None) -> list[str]:
    """Extract lexical unit candidates from free text without applying them."""

    found: set[str] = set()
    if not texts:
        return []
    for raw in texts:
        token = str(raw or "").strip().lower()
        if not token:
            continue
        # Exact token match first.
        if token in _UNIT_CANDIDATE_TOKENS:
            found.add(_UNIT_CANDIDATE_TOKENS[token])
            continue
        # Bounded word-ish matches for multi-word notes.
        normalized = (
            token.replace("（", " ")
            .replace("）", " ")
            .replace("(", " ")
            .replace(")", " ")
            .replace(":", " ")
            .replace("：", " ")
            .replace(",", " ")
            .replace("，", " ")
            .replace("/", " ")
        )
        for piece in normalized.split():
            piece = piece.strip(".-_")
            if piece in _UNIT_CANDIDATE_TOKENS:
                found.add(_UNIT_CANDIDATE_TOKENS[piece])
    return sorted(found)


def build_file_scale_evidence(
    census: Mapping[str, Any],
    *,
    candidate_texts: Sequence[str] | None = None,
) -> ScaleEvidenceRecord:
    """Build fail-closed scale evidence for one census file payload."""

    file_id = str(census.get("file_id") or census.get("source_file_id") or "").strip()
    filename = census.get("filename")
    filename_text = str(filename) if filename not in (None, "") else None

    raw_units = census.get("units")
    units: int | None
    try:
        units = int(raw_units) if raw_units is not None else None
    except (TypeError, ValueError):
        units = None

    units_name = census.get("units_name")
    if units_name in (None, "", "Unknown"):
        units_name = unit_name_for_insunits(units)
    else:
        units_name = str(units_name)

    census_scale_status = str(census.get("scale_status") or "").upper() or None
    candidates = extract_unit_candidates(candidate_texts)
    evidence_codes: list[str] = []
    notes: list[str] = []
    source_refs: list[str] = []

    if units is None:
        evidence_codes.append("UNITS_READ_MISSING")
        notes.append("INSUNITS value is missing or unreadable.")
        evidence_state = "INVALID"
        authority = "NONE"
        scale_status = "INVALID"
    elif units == 0 or units_name in (None, "Unitless"):
        evidence_codes.append("UNITS_UNSPECIFIED")
        notes.append("Drawing is unitless; millimetre normalization is not authorized.")
        evidence_state = "UNRESOLVED"
        authority = "NONE"
        scale_status = "UNRESOLVED"
    elif units_name == "Unknown":
        evidence_codes.append("UNITS_CODE_UNKNOWN")
        notes.append(f"INSUNITS={units} is not in the supported unit map.")
        evidence_state = "UNRESOLVED"
        authority = "DECLARED_UNKNOWN"
        scale_status = "UNRESOLVED"
    else:
        evidence_codes.append("UNITS_DECLARED")
        notes.append(f"INSUNITS declares {units_name}.")
        evidence_state = "DECLARED"
        authority = "INSUNITS"
        scale_status = "DECLARED"
        source_refs.append(f"insunits:{units}")

    if candidates:
        evidence_codes.append("LEXICAL_UNIT_CANDIDATES")
        notes.append(
            "Lexical unit candidates are review-only and are never applied to geometry."
        )
        source_refs.extend(f"text:{item}" for item in candidates)
        if evidence_state == "DECLARED" and units_name not in candidates:
            evidence_codes.append("DECLARED_VS_CANDIDATE_CONFLICT")
            notes.append(
                f"Declared unit {units_name} conflicts with candidate set {candidates}."
            )
            evidence_state = "CONFLICT"
            scale_status = "CONFLICT"
        elif evidence_state in {"UNRESOLVED", "INVALID"}:
            if len(set(candidates)) == 1:
                evidence_state = "CANDIDATE"
                authority = "TEXT_CANDIDATE"
                scale_status = "CANDIDATE"
            else:
                evidence_state = "CONFLICT"
                authority = "TEXT_CANDIDATE"
                scale_status = "CONFLICT"

    # The census is an independent source contract.  A non-zero INSUNITS value
    # cannot override an explicit UNRESOLVED census classification: the two
    # inputs contradict each other and require review before normalization.
    if census_scale_status == "UNRESOLVED" and units not in (None, 0):
        evidence_codes.append("CENSUS_SCALE_STATUS_CONTRADICTION")
        notes.append(
            "Census scale_status is UNRESOLVED despite non-zero INSUNITS; "
            "millimetre normalization remains blocked."
        )
        evidence_state = "CONFLICT"
        scale_status = "CONFLICT"

    declared_ready = (
        evidence_state == "DECLARED"
        and units_name in _DECLARED_READY_UNITS
        and scale_status == "DECLARED"
    )

    return ScaleEvidenceRecord(
        schema_version=SCALE_EVIDENCE_SCHEMA_VERSION,
        file_id=file_id or "UNKNOWN_FILE",
        filename=filename_text,
        units=units,
        units_name=units_name,
        scale_status=scale_status,
        evidence_state=evidence_state,
        authority=authority,
        declared_ready_for_mm_normalization=declared_ready,
        applied_to_geometry=False,
        candidate_units=tuple(candidates),
        evidence_codes=tuple(sorted(set(evidence_codes))),
        notes=tuple(notes),
        source_refs=tuple(source_refs),
    )


def build_file_transform_fidelity(
    census: Mapping[str, Any],
    *,
    scale_record: ScaleEvidenceRecord | None = None,
) -> TransformFidelityRecord:
    """Summarize transform risks that block certified millimetre readiness."""

    file_id = str(census.get("file_id") or census.get("source_file_id") or "").strip()
    filename = census.get("filename")
    filename_text = str(filename) if filename not in (None, "") else None

    warnings = list(census.get("virtual_expansion_warnings") or [])
    failures = list(census.get("virtual_expansion_failures") or [])
    non_uniform = [
        item
        for item in warnings
        if isinstance(item, Mapping)
        and str(item.get("code") or "") == "NON_UNIFORM_INSERT_SCALE"
    ]

    evidence_codes: list[str] = []
    notes: list[str] = []
    if non_uniform:
        evidence_codes.append("NON_UNIFORM_INSERT_SCALE")
        notes.append(
            f"{len(non_uniform)} non-uniform INSERT scale instance(s) require review."
        )
    if failures:
        evidence_codes.append("VIRTUAL_EXPANSION_FAILURE")
        notes.append(
            f"{len(failures)} virtual expansion failure(s) prevent certified transform fidelity."
        )

    ocs_wcs_status = str(census.get("ocs_wcs_status") or "").strip() or "UNMEASURED"
    nested_block_units_status = (
        str(census.get("nested_block_units_status") or "").strip() or "UNMEASURED"
    )
    ocs_identity = int(census.get("ocs_identity_count") or 0)
    ocs_non_identity = int(census.get("ocs_non_identity_count") or 0)
    ocs_unreadable = int(census.get("ocs_unreadable_count") or 0)
    nested_aligned = int(census.get("nested_block_units_aligned_count") or 0)
    nested_mismatch = int(census.get("nested_block_units_mismatch_count") or 0)
    nested_unitless = int(census.get("nested_block_units_unitless_count") or 0)
    nested_unreadable = int(census.get("nested_block_units_unreadable_count") or 0)

    if ocs_wcs_status == "UNMEASURED":
        evidence_codes.append("OCS_WCS_UNMEASURED")
        notes.append("OCS/WCS fidelity was not measured for this file.")
    elif ocs_wcs_status == "MEASUREMENT_FAILED":
        evidence_codes.append("OCS_WCS_MEASUREMENT_FAILED")
        notes.append("OCS/WCS measurement failed; millimetre readiness remains blocked.")
    elif ocs_wcs_status == "MEASURED_NON_IDENTITY":
        evidence_codes.append("OCS_WCS_NON_IDENTITY")
        notes.append(
            f"Measured non-identity OCS extrusion on {ocs_non_identity} entit(y/ies)."
        )
    elif ocs_wcs_status == "MEASURED_IDENTITY_PARTIAL":
        evidence_codes.append("OCS_WCS_MEASURED_IDENTITY_PARTIAL")
        notes.append(
            f"Measured identity OCS extrusion on {ocs_identity} entit(y/ies) "
            f"with {ocs_unreadable} unreadable sample(s); partial measurement "
            "cannot certify OCS/WCS readiness."
        )
    elif ocs_wcs_status == "MEASURED_IDENTITY":
        evidence_codes.append("OCS_WCS_MEASURED_IDENTITY")
        notes.append(
            f"Measured identity OCS extrusion on {ocs_identity} entit(y/ies)"
            + (
                f" with {ocs_unreadable} unreadable sample(s)."
                if ocs_unreadable
                else "."
            )
        )
    else:
        evidence_codes.append("OCS_WCS_STATUS_UNKNOWN")
        notes.append(f"Unrecognized OCS/WCS status: {ocs_wcs_status}")

    if nested_block_units_status == "UNMEASURED":
        evidence_codes.append("NESTED_BLOCK_UNITS_UNMEASURED")
        notes.append("Nested block unit fidelity was not measured for this file.")
    elif nested_block_units_status == "MEASUREMENT_FAILED":
        evidence_codes.append("NESTED_BLOCK_UNITS_MEASUREMENT_FAILED")
        notes.append("Nested block unit measurement failed.")
    elif nested_block_units_status == "MEASURED_MISMATCH":
        evidence_codes.append("NESTED_BLOCK_UNITS_MISMATCH")
        notes.append(
            f"{nested_mismatch} block definition(s) declare units that differ from the drawing."
        )
    elif nested_block_units_status == "MEASURED_UNITLESS":
        evidence_codes.append("NESTED_BLOCK_UNITS_UNITLESS")
        notes.append(
            f"{nested_unitless} block definition(s) are unitless while drawing units are unresolved."
        )
    elif nested_block_units_status == "MEASURED_ALIGNED_PARTIAL":
        evidence_codes.append("NESTED_BLOCK_UNITS_MEASURED_ALIGNED_PARTIAL")
        notes.append(
            f"{nested_aligned} block definition(s) align with drawing units "
            f"but {nested_unreadable} remain unreadable; partial measurement "
            "cannot certify nested block unit readiness."
        )
    elif nested_block_units_status == "MEASURED_ALIGNED":
        evidence_codes.append("NESTED_BLOCK_UNITS_ALIGNED")
        notes.append(
            f"{nested_aligned} block definition(s) align with drawing units"
            + (
                f" ({nested_unreadable} unreadable)."
                if nested_unreadable
                else "."
            )
        )
    else:
        evidence_codes.append("NESTED_BLOCK_UNITS_STATUS_UNKNOWN")
        notes.append(
            f"Unrecognized nested block units status: {nested_block_units_status}"
        )

    scale_ready = bool(
        scale_record is not None and scale_record.declared_ready_for_mm_normalization
    )
    ocs_ready = ocs_wcs_status == "MEASURED_IDENTITY"
    nested_ready = nested_block_units_status == "MEASURED_ALIGNED"
    if not scale_ready:
        millimetre_readiness = "NOT_READY_SCALE"
        evidence_codes.append("SCALE_NOT_READY")
    elif failures or non_uniform:
        millimetre_readiness = "NOT_READY_TRANSFORM"
        evidence_codes.append("TRANSFORM_NOT_READY")
    elif not ocs_ready:
        millimetre_readiness = "NOT_READY_OCS_WCS"
        evidence_codes.append("OCS_WCS_BLOCKS_MM_READINESS")
    elif not nested_ready:
        millimetre_readiness = "NOT_READY_NESTED_BLOCK_UNITS"
        evidence_codes.append("NESTED_BLOCK_UNITS_BLOCK_MM_READINESS")
    else:
        # Measured clean path is still not applied and still not product-promoted.
        millimetre_readiness = "MEASURED_PENDING_PROMOTION"
        evidence_codes.append("MEASURED_MM_PATH_PENDING_PROMOTION")

    review_required = True
    return TransformFidelityRecord(
        schema_version=TRANSFORM_FIDELITY_SCHEMA_VERSION,
        file_id=file_id or "UNKNOWN_FILE",
        filename=filename_text,
        non_uniform_insert_count=len(non_uniform),
        virtual_expansion_failure_count=len(failures),
        virtual_expansion_warning_count=len(warnings),
        ocs_wcs_status=ocs_wcs_status,
        nested_block_units_status=nested_block_units_status,
        millimetre_readiness=millimetre_readiness,
        review_required=review_required,
        evidence_codes=tuple(sorted(set(evidence_codes))),
        notes=tuple(notes),
    )


def build_project_scale_evidence(
    census_files: Sequence[Mapping[str, Any]],
    *,
    project_id: str,
    candidate_texts_by_file: Mapping[str, Sequence[str]] | None = None,
) -> ScaleEvidenceBundle:
    """Build project-level scale and transform evidence from census payloads."""

    texts_by_file = candidate_texts_by_file or {}
    files: list[ScaleEvidenceRecord] = []
    transforms: list[TransformFidelityRecord] = []
    for item in census_files:
        if not isinstance(item, Mapping):
            continue
        file_id = str(item.get("file_id") or item.get("source_file_id") or "").strip()
        scale = build_file_scale_evidence(
            item,
            candidate_texts=texts_by_file.get(file_id),
        )
        transform = build_file_transform_fidelity(item, scale_record=scale)
        files.append(scale)
        transforms.append(transform)

    files = sorted(files, key=lambda row: (row.file_id, row.filename or ""))
    transforms = sorted(transforms, key=lambda row: (row.file_id, row.filename or ""))
    summary = summarize_scale_evidence(project_id, files, transforms)
    return ScaleEvidenceBundle(
        schema_version=SCALE_EVIDENCE_SCHEMA_VERSION,
        project_id=str(project_id or "UNKNOWN_PROJECT"),
        files=tuple(files),
        transforms=tuple(transforms),
        summary=summary,
    )


def summarize_scale_evidence(
    project_id: str,
    files: Sequence[ScaleEvidenceRecord],
    transforms: Sequence[TransformFidelityRecord],
) -> dict[str, Any]:
    scale_status_counts = Counter(item.scale_status for item in files)
    evidence_state_counts = Counter(item.evidence_state for item in files)
    readiness_counts = Counter(item.millimetre_readiness for item in transforms)
    ocs_status_counts = Counter(item.ocs_wcs_status for item in transforms)
    nested_status_counts = Counter(item.nested_block_units_status for item in transforms)
    applied_count = sum(1 for item in files if item.applied_to_geometry)
    declared_ready = sum(1 for item in files if item.declared_ready_for_mm_normalization)
    non_uniform_total = sum(item.non_uniform_insert_count for item in transforms)
    expansion_failures = sum(
        item.virtual_expansion_failure_count for item in transforms
    )
    measured_pending = sum(
        1
        for item in transforms
        if item.millimetre_readiness == "MEASURED_PENDING_PROMOTION"
    )
    # Project-level OCS/nested status: worst-case rollup, never invent ready.
    if not transforms:
        ocs_project = "UNMEASURED"
        nested_project = "UNMEASURED"
    else:
        ocs_rank = {
            "MEASUREMENT_FAILED": 0,
            "UNMEASURED": 1,
            "MEASURED_NON_IDENTITY": 2,
            "MEASURED_IDENTITY_PARTIAL": 3,
            "MEASURED_IDENTITY": 4,
        }
        nested_rank = {
            "MEASUREMENT_FAILED": 0,
            "UNMEASURED": 1,
            "MEASURED_MISMATCH": 2,
            "MEASURED_UNITLESS": 3,
            "MEASURED_ALIGNED_PARTIAL": 4,
            "MEASURED_ALIGNED": 5,
        }
        ocs_project = min(
            (item.ocs_wcs_status for item in transforms),
            key=lambda status: ocs_rank.get(status, -1),
        )
        nested_project = min(
            (item.nested_block_units_status for item in transforms),
            key=lambda status: nested_rank.get(status, -1),
        )
    return {
        "schema_version": SCALE_SUMMARY_SCHEMA_VERSION,
        "project_id": str(project_id or "UNKNOWN_PROJECT"),
        "file_count": len(files),
        "scale_status_counts": dict(sorted(scale_status_counts.items())),
        "evidence_state_counts": dict(sorted(evidence_state_counts.items())),
        "declared_ready_for_mm_normalization_count": declared_ready,
        "applied_to_geometry_count": applied_count,
        "geometry_mutation_forbidden": applied_count == 0,
        "millimetre_readiness_counts": dict(sorted(readiness_counts.items())),
        "non_uniform_insert_count": non_uniform_total,
        "virtual_expansion_failure_count": expansion_failures,
        "ocs_wcs_status": ocs_project,
        "ocs_wcs_status_counts": dict(sorted(ocs_status_counts.items())),
        "nested_block_units_status": nested_project,
        "nested_block_units_status_counts": dict(sorted(nested_status_counts.items())),
        "measured_pending_promotion_count": measured_pending,
        "canonical_millimetre_ready": False,
        "shadow_only": True,
    }


__all__ = [
    "SCALE_EVIDENCE_SCHEMA_VERSION",
    "SCALE_SUMMARY_SCHEMA_VERSION",
    "TRANSFORM_FIDELITY_SCHEMA_VERSION",
    "ScaleEvidenceBundle",
    "ScaleEvidenceRecord",
    "TransformFidelityRecord",
    "build_file_scale_evidence",
    "build_file_transform_fidelity",
    "build_project_scale_evidence",
    "extract_unit_candidates",
    "summarize_scale_evidence",
    "unit_name_for_insunits",
]
