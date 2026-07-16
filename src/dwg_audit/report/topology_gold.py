from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

import pandas as pd

from dwg_audit.report.project_bundle import resolve_project_bundle_dir


SCHEMA_VERSION = "topology-gold-pack-v1"
PENDING_STATUS = "PENDING"
CERTIFIED_STATUS = "HUMAN_CERTIFIED"
PENDING_REVIEW_STATUS = "PENDING_HUMAN_REVIEW"
COMPLETE_REVIEW_STATUS = "REVIEW_COMPLETE"
HUMAN_LABEL_BASIS = "HUMAN_SOURCE_DRAWING_REVIEW"
HELDOUT_USAGE = "evaluation_only_never_tuning"

_PACK_FILENAMES = (
    "manifest.json",
    "pages.csv",
    "junctions.csv",
    "connectivity_members.csv",
    "open_endpoints.csv",
)
_REVIEW_KINDS = ("junctions", "connectivity", "open_endpoints")
_PAGE_COLUMNS = (
    "sheet_id",
    "file_id",
    "filename",
    "dwg_sha256",
    "audit_role",
    "audit_disposition",
    "review_status",
    "junctions_review_complete",
    "connectivity_review_complete",
    "open_endpoints_review_complete",
)
_JUNCTION_COLUMNS = (
    "junction_id",
    "sheet_id",
    "file_id",
    "x",
    "y",
    "expected_connected",
    "source_handles_json",
    "label_source",
    "notes",
)
_CONNECTIVITY_COLUMNS = (
    "network_id",
    "member_id",
    "sheet_id",
    "file_id",
    "source_handle",
    "x",
    "y",
    "label_source",
    "notes",
)
_OPEN_ENDPOINT_COLUMNS = (
    "endpoint_id",
    "sheet_id",
    "file_id",
    "source_handle",
    "x",
    "y",
    "expected_open",
    "label_source",
    "notes",
)
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TopologyGoldPackError(ValueError):
    """Raised when a topology-gold pack cannot be loaded or built safely."""


@dataclass(frozen=True, slots=True)
class TopologyGoldPack:
    directory: Path
    manifest: dict[str, Any]
    pages: tuple[dict[str, str], ...]
    junctions: tuple[dict[str, str], ...]
    connectivity_members: tuple[dict[str, str], ...]
    open_endpoints: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class TopologyGoldValidation:
    valid: bool
    certification_ready: bool
    project_scope: bool
    status: str | None
    errors: tuple[str, ...]
    page_count: int
    junction_count: int
    connectivity_member_count: int
    open_endpoint_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "valid": self.valid,
            "certification_ready": self.certification_ready,
            "project_scope": self.project_scope,
            "status": self.status,
            "errors": list(self.errors),
            "page_count": self.page_count,
            "junction_count": self.junction_count,
            "connectivity_member_count": self.connectivity_member_count,
            "open_endpoint_count": self.open_endpoint_count,
        }


@dataclass(frozen=True, slots=True)
class _ProjectSnapshot:
    bundle_dir: Path
    pages: tuple[dict[str, Any], ...]
    handles_by_sheet: dict[str, frozenset[str]]
    handle_inventory_available: bool


def build_topology_gold_template(
    project_dir: Path,
    *,
    project_id: str,
    split: str,
    output_dir: Path,
) -> TopologyGoldPack:
    """Write a deterministic, label-free topology gold review template.

    The template binds every audit-required page to its persisted DWG SHA-256.
    It deliberately contains no labels, reviewer identity, review timestamp, or
    certification claim. Existing pack files are never overwritten.
    """

    project_id = _required_text(project_id, "project_id")
    split = _required_text(split, "split")
    snapshot = _load_project_snapshot(Path(project_dir))
    if not snapshot.pages:
        raise TopologyGoldPackError(
            "project has no audit-required pages; project-scope template is undefined"
        )

    output_dir = Path(output_dir)
    existing = [name for name in _PACK_FILENAMES if (output_dir / name).exists()]
    if existing:
        raise TopologyGoldPackError(
            "refusing to overwrite topology gold pack files: " + ", ".join(existing)
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    page_bindings = [_manifest_page_binding(page) for page in snapshot.pages]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "split": split,
        "status": PENDING_STATUS,
        "annotation_status": PENDING_REVIEW_STATUS,
        "reviewer": None,
        "reviewed_at": None,
        "label_basis": None,
        "not_a_human_gold_standard": True,
        "heldout_usage": HELDOUT_USAGE,
        "review_complete": {kind: False for kind in _REVIEW_KINDS},
        "source_binding": {
            "source_files_artifact": "findings/source_files.parquet",
            "extraction_completeness_artifact": "extraction_completeness.json",
            "audit_required_page_count": len(page_bindings),
            "pages": page_bindings,
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        output_dir / "pages.csv",
        _PAGE_COLUMNS,
        (
            {
                **_manifest_page_binding(page),
                "audit_role": page["audit_role"],
                "audit_disposition": page["audit_disposition"],
                "review_status": PENDING_REVIEW_STATUS,
                "junctions_review_complete": False,
                "connectivity_review_complete": False,
                "open_endpoints_review_complete": False,
            }
            for page in snapshot.pages
        ),
    )
    _write_csv(output_dir / "junctions.csv", _JUNCTION_COLUMNS, ())
    _write_csv(
        output_dir / "connectivity_members.csv", _CONNECTIVITY_COLUMNS, ()
    )
    _write_csv(output_dir / "open_endpoints.csv", _OPEN_ENDPOINT_COLUMNS, ())
    return load_topology_gold_pack(output_dir)


def load_topology_gold_pack(pack_dir: Path) -> TopologyGoldPack:
    """Load one pack with exact file and column contracts.

    Semantic and source-binding validation is intentionally separate so callers
    can inspect a syntactically sound pending pack without granting it authority.
    """

    pack_dir = Path(pack_dir)
    missing = [name for name in _PACK_FILENAMES if not (pack_dir / name).is_file()]
    if missing:
        raise TopologyGoldPackError("missing pack files: " + ", ".join(missing))
    try:
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TopologyGoldPackError(
            f"unable to read manifest.json: {type(exc).__name__}"
        ) from exc
    if not isinstance(manifest, dict):
        raise TopologyGoldPackError("manifest.json must contain a JSON object")
    return TopologyGoldPack(
        directory=pack_dir,
        manifest=manifest,
        pages=_read_csv(pack_dir / "pages.csv", _PAGE_COLUMNS),
        junctions=_read_csv(pack_dir / "junctions.csv", _JUNCTION_COLUMNS),
        connectivity_members=_read_csv(
            pack_dir / "connectivity_members.csv", _CONNECTIVITY_COLUMNS
        ),
        open_endpoints=_read_csv(
            pack_dir / "open_endpoints.csv", _OPEN_ENDPOINT_COLUMNS
        ),
    )


def validate_topology_gold_pack(
    pack_dir: Path,
    *,
    project_dir: Path,
    project_id: str,
    split: str,
) -> TopologyGoldValidation:
    """Validate source binding, human provenance, and project-wide coverage.

    A valid pending pack remains non-authoritative. ``project_scope`` and
    ``certification_ready`` become true only for a fully reviewed, human-certified
    pack whose pages and DWG hashes exactly match the current project bundle.
    """

    errors: list[str] = []
    try:
        pack = load_topology_gold_pack(pack_dir)
    except TopologyGoldPackError as exc:
        return _validation_failure(f"PACK_LOAD_ERROR: {exc}")
    try:
        expected_project_id = _required_text(project_id, "project_id")
        expected_split = _required_text(split, "split")
        snapshot = _load_project_snapshot(Path(project_dir))
    except TopologyGoldPackError as exc:
        return _validation_failure(
            f"PROJECT_BINDING_ERROR: {exc}",
            pack=pack,
        )

    manifest = pack.manifest
    status = _text(manifest.get("status")) or None
    annotation_status = _text(manifest.get("annotation_status")) or None
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_MISMATCH: manifest schema is not topology-gold-pack-v1")
    if _text(manifest.get("project_id")) != expected_project_id:
        errors.append("PROJECT_ID_MISMATCH: manifest project_id does not match requested project")
    if _text(manifest.get("split")) != expected_split:
        errors.append("SPLIT_MISMATCH: manifest split does not match requested split")
    if status not in {PENDING_STATUS, CERTIFIED_STATUS}:
        errors.append("INVALID_STATUS: status must be PENDING or HUMAN_CERTIFIED")
    if manifest.get("heldout_usage") != HELDOUT_USAGE:
        errors.append(
            "INVALID_HELDOUT_USAGE: heldout_usage must be evaluation_only_never_tuning"
        )

    expected_bindings = [_manifest_page_binding(page) for page in snapshot.pages]
    _validate_manifest_source_binding(manifest, expected_bindings, errors)
    page_map, page_reviews_complete = _validate_pages(
        pack.pages,
        snapshot.pages,
        errors,
    )
    has_labels = bool(
        pack.junctions or pack.connectivity_members or pack.open_endpoints
    )
    _validate_junctions(pack.junctions, page_map, snapshot, errors)
    _validate_connectivity(pack.connectivity_members, page_map, snapshot, errors)
    _validate_open_endpoints(pack.open_endpoints, page_map, snapshot, errors)

    review_complete = manifest.get("review_complete")
    manifest_reviews_complete = isinstance(review_complete, Mapping) and all(
        review_complete.get(kind) is True for kind in _REVIEW_KINDS
    )
    if not isinstance(review_complete, Mapping) or any(
        not isinstance(review_complete.get(kind), bool) for kind in _REVIEW_KINDS
    ):
        errors.append(
            "INVALID_REVIEW_COMPLETENESS: manifest must contain three boolean review flags"
        )

    if status == PENDING_STATUS:
        if annotation_status != PENDING_REVIEW_STATUS:
            errors.append(
                "PENDING_REVIEW_STATUS_INVALID: pending packs must remain PENDING_HUMAN_REVIEW"
            )
        if manifest.get("not_a_human_gold_standard") is not True:
            errors.append(
                "PENDING_AUTHORITY_VIOLATION: pending packs must state not_a_human_gold_standard=true"
            )
    elif status == CERTIFIED_STATUS:
        if annotation_status != COMPLETE_REVIEW_STATUS:
            errors.append(
                "CERTIFIED_REVIEW_STATUS_INVALID: HUMAN_CERTIFIED requires REVIEW_COMPLETE"
            )
        _validate_certification_metadata(manifest, errors)
        if not manifest_reviews_complete or not page_reviews_complete:
            errors.append(
                "REVIEW_INCOMPLETE: all three review classes must be complete for every page"
            )
        incomplete_pages = [
            page["sheet_id"]
            for page in snapshot.pages
            if _text(page.get("status")).upper() not in {"COMPLETE", "OK"}
        ]
        if incomplete_pages:
            errors.append(
                "SOURCE_EXTRACTION_INCOMPLETE: certified pack references incomplete audit pages"
            )
        missing_label_tables = [
            name
            for name, rows in (
                ("junctions", pack.junctions),
                ("connectivity", pack.connectivity_members),
                ("open_endpoints", pack.open_endpoints),
            )
            if not rows
        ]
        if missing_label_tables:
            errors.append(
                "NON_VACUOUS_TOPOLOGY_GOLD_REQUIRED: certified packs require "
                "human-reviewed rows in all three label tables; empty="
                + ",".join(missing_label_tables)
            )

    valid = not errors
    certification_ready = bool(valid and status == CERTIFIED_STATUS)
    project_scope = certification_ready
    return TopologyGoldValidation(
        valid=valid,
        certification_ready=certification_ready,
        project_scope=project_scope,
        status=status,
        errors=tuple(errors),
        page_count=len(pack.pages),
        junction_count=len(pack.junctions),
        connectivity_member_count=len(pack.connectivity_members),
        open_endpoint_count=len(pack.open_endpoints),
    )


def _validation_failure(
    error: str,
    *,
    pack: TopologyGoldPack | None = None,
) -> TopologyGoldValidation:
    return TopologyGoldValidation(
        valid=False,
        certification_ready=False,
        project_scope=False,
        status=_text(pack.manifest.get("status")) or None if pack else None,
        errors=(error,),
        page_count=len(pack.pages) if pack else 0,
        junction_count=len(pack.junctions) if pack else 0,
        connectivity_member_count=len(pack.connectivity_members) if pack else 0,
        open_endpoint_count=len(pack.open_endpoints) if pack else 0,
    )


def _load_project_snapshot(project_dir: Path) -> _ProjectSnapshot:
    bundle_dir = resolve_project_bundle_dir(project_dir)
    source_path = bundle_dir / "findings" / "source_files.parquet"
    gate_path = bundle_dir / "extraction_completeness.json"
    if not source_path.is_file():
        raise TopologyGoldPackError(f"missing source artifact: {source_path}")
    if not gate_path.is_file():
        raise TopologyGoldPackError(f"missing extraction artifact: {gate_path}")
    try:
        sources = pd.read_parquet(source_path)
    except Exception as exc:
        raise TopologyGoldPackError(
            f"unable to read source_files.parquet: {type(exc).__name__}"
        ) from exc
    required_source_columns = {"file_id", "filename", "sha256"}
    missing_columns = required_source_columns.difference(sources.columns)
    if missing_columns:
        raise TopologyGoldPackError(
            "source_files.parquet missing columns: " + ", ".join(sorted(missing_columns))
        )
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TopologyGoldPackError(
            f"unable to read extraction_completeness.json: {type(exc).__name__}"
        ) from exc
    gate_pages = gate.get("pages") if isinstance(gate, Mapping) else None
    if not isinstance(gate_pages, list):
        raise TopologyGoldPackError("extraction completeness pages must be a list")

    sources_by_file: dict[str, dict[str, str]] = {}
    for row in sources.to_dict(orient="records"):
        file_id = _text(row.get("file_id"))
        sha = _text(row.get("sha256")).lower()
        if not file_id:
            raise TopologyGoldPackError("source_files.parquet contains an empty file_id")
        if file_id in sources_by_file:
            raise TopologyGoldPackError(f"duplicate source file_id: {file_id}")
        if not _HEX_SHA256.fullmatch(sha):
            raise TopologyGoldPackError(f"invalid DWG sha256 for {file_id}")
        sources_by_file[file_id] = {
            "file_id": file_id,
            "filename": _text(row.get("filename")),
            "dwg_sha256": sha,
        }

    pages: list[dict[str, Any]] = []
    seen_sheets: set[str] = set()
    for raw_page in gate_pages:
        if not isinstance(raw_page, Mapping) or not _is_audit_required(raw_page):
            continue
        sheet_id = _text(raw_page.get("sheet") or raw_page.get("sheet_id"))
        file_id = _text(raw_page.get("file") or raw_page.get("file_id"))
        if not sheet_id or not file_id:
            raise TopologyGoldPackError("audit-required extraction page lacks sheet/file id")
        if sheet_id in seen_sheets:
            raise TopologyGoldPackError(f"duplicate audit-required sheet: {sheet_id}")
        seen_sheets.add(sheet_id)
        source = sources_by_file.get(file_id)
        if source is None:
            raise TopologyGoldPackError(
                f"audit-required page {sheet_id} references unknown file {file_id}"
            )
        filename = _text(raw_page.get("filename")) or source["filename"]
        if filename != source["filename"]:
            raise TopologyGoldPackError(
                f"filename mismatch between extraction page and source file: {file_id}"
            )
        pages.append(
            {
                "sheet_id": sheet_id,
                "file_id": file_id,
                "filename": filename,
                "dwg_sha256": source["dwg_sha256"],
                "audit_role": _text(raw_page.get("audit_role")),
                "audit_disposition": _text(raw_page.get("audit_disposition")),
                "status": _text(raw_page.get("status")),
            }
        )
    pages.sort(key=lambda row: (row["sheet_id"], row["file_id"]))
    handles, inventory_available = _load_source_handles(bundle_dir)
    return _ProjectSnapshot(
        bundle_dir=bundle_dir,
        pages=tuple(pages),
        handles_by_sheet=handles,
        handle_inventory_available=inventory_available,
    )


def _load_source_handles(
    bundle_dir: Path,
) -> tuple[dict[str, frozenset[str]], bool]:
    findings = bundle_dir / "findings"
    by_sheet: dict[str, set[str]] = {}
    available = False
    path = findings / "lines.parquet"
    if not path.is_file():
        return {}, False
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return {}, False
    if "sheet_id" not in frame.columns or "handle" not in frame.columns:
        return {}, False
    available = True
    for row in frame.to_dict(orient="records"):
        sheet_id = _text(row.get("sheet_id"))
        if not sheet_id:
            continue
        handle = _normalized_handle(row.get("handle"))
        if handle:
            by_sheet.setdefault(sheet_id, set()).add(handle)
    return {key: frozenset(value) for key, value in by_sheet.items()}, available


def _validate_manifest_source_binding(
    manifest: Mapping[str, Any],
    expected_bindings: list[dict[str, str]],
    errors: list[str],
) -> None:
    binding = manifest.get("source_binding")
    if not isinstance(binding, Mapping):
        errors.append("SOURCE_BINDING_MISSING: manifest source_binding must be an object")
        return
    if binding.get("source_files_artifact") != "findings/source_files.parquet":
        errors.append("SOURCE_BINDING_INVALID: source_files artifact path is not canonical")
    if binding.get("extraction_completeness_artifact") != "extraction_completeness.json":
        errors.append("SOURCE_BINDING_INVALID: extraction artifact path is not canonical")
    if binding.get("audit_required_page_count") != len(expected_bindings):
        errors.append("PAGE_COVERAGE_MISMATCH: manifest page count is stale")
    raw_pages = binding.get("pages")
    if not isinstance(raw_pages, list):
        errors.append("SOURCE_BINDING_INVALID: manifest pages must be a list")
        return
    actual = []
    for item in raw_pages:
        if not isinstance(item, Mapping):
            errors.append("SOURCE_BINDING_INVALID: manifest page binding must be an object")
            continue
        actual.append(
            {
                "sheet_id": _text(item.get("sheet_id")),
                "file_id": _text(item.get("file_id")),
                "filename": _text(item.get("filename")),
                "dwg_sha256": _text(item.get("dwg_sha256")).lower(),
            }
        )
    if actual != expected_bindings:
        errors.append("SOURCE_BINDING_MISMATCH: manifest page/hash binding is stale or reordered")


def _validate_pages(
    actual_pages: tuple[dict[str, str], ...],
    expected_pages: tuple[dict[str, Any], ...],
    errors: list[str],
) -> tuple[dict[str, dict[str, str]], bool]:
    expected = {page["sheet_id"]: page for page in expected_pages}
    actual: dict[str, dict[str, str]] = {}
    seen_files: set[str] = set()
    all_reviews_complete = True
    for row in actual_pages:
        sheet_id = _text(row.get("sheet_id"))
        file_id = _text(row.get("file_id"))
        if not sheet_id or not file_id:
            errors.append("PAGE_ID_MISSING: pages.csv contains an empty sheet_id or file_id")
            continue
        if sheet_id in actual:
            errors.append(f"DUPLICATE_PAGE: pages.csv repeats sheet_id {sheet_id}")
            continue
        if file_id in seen_files:
            errors.append(f"DUPLICATE_PAGE: pages.csv repeats file_id {file_id}")
        seen_files.add(file_id)
        actual[sheet_id] = row
        expected_page = expected.get(sheet_id)
        if expected_page is None:
            errors.append(f"UNKNOWN_PAGE: pages.csv contains non-audit page {sheet_id}")
        else:
            for field in (
                "file_id",
                "filename",
                "dwg_sha256",
                "audit_role",
                "audit_disposition",
            ):
                value = _text(row.get(field))
                if field == "dwg_sha256":
                    value = value.lower()
                if value != _text(expected_page.get(field)):
                    code = "DWG_HASH_MISMATCH" if field == "dwg_sha256" else "PAGE_BINDING_MISMATCH"
                    errors.append(f"{code}: {sheet_id} field {field} is stale")
        review_status = _text(row.get("review_status"))
        if review_status not in {PENDING_REVIEW_STATUS, COMPLETE_REVIEW_STATUS}:
            errors.append(f"INVALID_PAGE_REVIEW_STATUS: {sheet_id}")
        flags: list[bool] = []
        for kind in _REVIEW_KINDS:
            parsed = _strict_bool(row.get(f"{kind}_review_complete"))
            if parsed is None:
                errors.append(f"INVALID_PAGE_REVIEW_FLAG: {sheet_id} {kind}")
                parsed = False
            flags.append(parsed)
        page_complete = review_status == COMPLETE_REVIEW_STATUS and all(flags)
        if not page_complete:
            all_reviews_complete = False
        if review_status == COMPLETE_REVIEW_STATUS and not all(flags):
            errors.append(f"CONFLICTING_PAGE_REVIEW: {sheet_id} is complete with incomplete review flags")
        if review_status == PENDING_REVIEW_STATUS and any(flags):
            errors.append(f"CONFLICTING_PAGE_REVIEW: {sheet_id} is pending with completed review flags")
    if set(actual) != set(expected):
        missing = sorted(set(expected).difference(actual))
        extra = sorted(set(actual).difference(expected))
        errors.append(
            "PAGE_COVERAGE_MISMATCH: missing="
            + ",".join(missing)
            + " extra="
            + ",".join(extra)
        )
    return actual, all_reviews_complete and len(actual) == len(expected)


def _validate_junctions(
    rows: tuple[dict[str, str], ...],
    pages: Mapping[str, Mapping[str, str]],
    snapshot: _ProjectSnapshot,
    errors: list[str],
) -> None:
    seen_ids: set[str] = set()
    seen_keys: dict[tuple[Any, ...], bool] = {}
    for index, row in enumerate(rows, start=2):
        identity = _text(row.get("junction_id"))
        if not identity:
            errors.append(f"JUNCTION_ID_MISSING: row {index}")
        elif identity in seen_ids:
            errors.append(f"DUPLICATE_JUNCTION: {identity}")
        seen_ids.add(identity)
        sheet_id = _validate_annotation_page(row, pages, "junction", index, errors)
        x = _finite_coordinate(row.get("x"), "junction", index, "x", errors)
        y = _finite_coordinate(row.get("y"), "junction", index, "y", errors)
        expected = _strict_bool(row.get("expected_connected"))
        if expected is None:
            errors.append(f"INVALID_JUNCTION_LABEL: row {index} expected_connected")
        handles = _json_handles(row.get("source_handles_json"), "junction", index, errors)
        _validate_human_label_source(row, "junction", index, errors)
        _validate_handles(handles, sheet_id, snapshot, "junction", index, errors)
        if sheet_id and x is not None and y is not None and expected is not None:
            key = (sheet_id, x, y, tuple(sorted(handles)))
            previous = seen_keys.get(key)
            if previous is not None:
                code = "CONFLICTING_JUNCTION" if previous != expected else "DUPLICATE_JUNCTION"
                errors.append(f"{code}: row {index}")
            else:
                seen_keys[key] = expected


def _validate_connectivity(
    rows: tuple[dict[str, str], ...],
    pages: Mapping[str, Mapping[str, str]],
    snapshot: _ProjectSnapshot,
    errors: list[str],
) -> None:
    seen_members: set[str] = set()
    ownership: dict[tuple[str, str], str] = {}
    for index, row in enumerate(rows, start=2):
        network_id = _text(row.get("network_id"))
        member_id = _text(row.get("member_id"))
        if not network_id:
            errors.append(f"NETWORK_ID_MISSING: row {index}")
        if not member_id:
            errors.append(f"MEMBER_ID_MISSING: row {index}")
        elif member_id in seen_members:
            errors.append(f"DUPLICATE_CONNECTIVITY_MEMBER: {member_id}")
        seen_members.add(member_id)
        sheet_id = _validate_annotation_page(row, pages, "connectivity", index, errors)
        _finite_coordinate(row.get("x"), "connectivity", index, "x", errors)
        _finite_coordinate(row.get("y"), "connectivity", index, "y", errors)
        _validate_human_label_source(row, "connectivity", index, errors)
        handle = _normalized_handle(row.get("source_handle"))
        _validate_handles((handle,) if handle else (), sheet_id, snapshot, "connectivity", index, errors)
        if sheet_id and handle and network_id:
            key = (sheet_id, handle)
            previous = ownership.get(key)
            if previous is not None:
                code = "MULTIPLE_NETWORK_OWNERSHIP" if previous != network_id else "DUPLICATE_CONNECTIVITY_MEMBER"
                errors.append(f"{code}: {sheet_id}/{handle}")
            else:
                ownership[key] = network_id


def _validate_open_endpoints(
    rows: tuple[dict[str, str], ...],
    pages: Mapping[str, Mapping[str, str]],
    snapshot: _ProjectSnapshot,
    errors: list[str],
) -> None:
    seen_ids: set[str] = set()
    seen_keys: dict[tuple[Any, ...], bool] = {}
    for index, row in enumerate(rows, start=2):
        endpoint_id = _text(row.get("endpoint_id"))
        if not endpoint_id:
            errors.append(f"ENDPOINT_ID_MISSING: row {index}")
        elif endpoint_id in seen_ids:
            errors.append(f"DUPLICATE_OPEN_ENDPOINT: {endpoint_id}")
        seen_ids.add(endpoint_id)
        sheet_id = _validate_annotation_page(row, pages, "open_endpoint", index, errors)
        x = _finite_coordinate(row.get("x"), "open_endpoint", index, "x", errors)
        y = _finite_coordinate(row.get("y"), "open_endpoint", index, "y", errors)
        expected = _strict_bool(row.get("expected_open"))
        if expected is None:
            errors.append(f"INVALID_OPEN_ENDPOINT_LABEL: row {index} expected_open")
        _validate_human_label_source(row, "open_endpoint", index, errors)
        handle = _normalized_handle(row.get("source_handle"))
        _validate_handles((handle,) if handle else (), sheet_id, snapshot, "open_endpoint", index, errors)
        if sheet_id and handle and x is not None and y is not None and expected is not None:
            key = (sheet_id, handle, x, y)
            previous = seen_keys.get(key)
            if previous is not None:
                code = "CONFLICTING_OPEN_ENDPOINT" if previous != expected else "DUPLICATE_OPEN_ENDPOINT"
                errors.append(f"{code}: row {index}")
            else:
                seen_keys[key] = expected


def _validate_annotation_page(
    row: Mapping[str, str],
    pages: Mapping[str, Mapping[str, str]],
    table: str,
    row_number: int,
    errors: list[str],
) -> str:
    sheet_id = _text(row.get("sheet_id"))
    file_id = _text(row.get("file_id"))
    page = pages.get(sheet_id)
    if not sheet_id or page is None:
        errors.append(f"UNKNOWN_ANNOTATION_PAGE: {table} row {row_number}")
        return sheet_id
    if file_id != _text(page.get("file_id")):
        errors.append(f"ANNOTATION_FILE_MISMATCH: {table} row {row_number}")
    return sheet_id


def _validate_human_label_source(
    row: Mapping[str, str],
    table: str,
    row_number: int,
    errors: list[str],
) -> None:
    if _text(row.get("label_source")) != HUMAN_LABEL_BASIS:
        errors.append(f"MACHINE_OR_UNKNOWN_LABEL_SOURCE: {table} row {row_number}")


def _validate_handles(
    handles: Iterable[str],
    sheet_id: str,
    snapshot: _ProjectSnapshot,
    table: str,
    row_number: int,
    errors: list[str],
) -> None:
    handles = tuple(handle for handle in handles if handle)
    if not handles:
        errors.append(f"SOURCE_HANDLE_MISSING: {table} row {row_number}")
        return
    if not snapshot.handle_inventory_available:
        errors.append(f"SOURCE_HANDLE_INVENTORY_UNAVAILABLE: {table} row {row_number}")
        return
    known = snapshot.handles_by_sheet.get(sheet_id, frozenset())
    for handle in handles:
        if handle not in known:
            errors.append(f"UNKNOWN_SOURCE_HANDLE: {table} row {row_number} {handle}")


def _validate_certification_metadata(
    manifest: Mapping[str, Any],
    errors: list[str],
) -> None:
    if not _text(manifest.get("reviewer")):
        errors.append("REVIEWER_MISSING: HUMAN_CERTIFIED requires reviewer")
    reviewed_at = _text(manifest.get("reviewed_at"))
    if not _timezone_aware_timestamp(reviewed_at):
        errors.append("REVIEW_TIME_INVALID: HUMAN_CERTIFIED requires a timezone-aware timestamp")
    if manifest.get("label_basis") != HUMAN_LABEL_BASIS:
        errors.append("LABEL_BASIS_INVALID: HUMAN_CERTIFIED requires human source drawing review")
    if manifest.get("not_a_human_gold_standard") is not False:
        errors.append("HUMAN_GOLD_DISCLAIMER_INVALID: certified pack must set false")
    if manifest.get("heldout_usage") != HELDOUT_USAGE:
        errors.append("INVALID_HELDOUT_USAGE: certified pack can only be used for evaluation")


def _is_audit_required(page: Mapping[str, Any]) -> bool:
    disposition = _text(page.get("audit_disposition")).casefold()
    role = _text(page.get("audit_role")).casefold()
    return disposition == "audit_required" or role in {"primary", "supplemental"}


def _manifest_page_binding(page: Mapping[str, Any]) -> dict[str, str]:
    return {
        "sheet_id": _text(page.get("sheet_id")),
        "file_id": _text(page.get("file_id")),
        "filename": _text(page.get("filename")),
        "dwg_sha256": _text(page.get("dwg_sha256")).lower(),
    }


def _write_csv(
    path: Path,
    columns: tuple[str, ...],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def _read_csv(path: Path, columns: tuple[str, ...]) -> tuple[dict[str, str], ...]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != columns:
                raise TopologyGoldPackError(
                    f"{path.name} columns must exactly match: {', '.join(columns)}"
                )
            return tuple({key: value or "" for key, value in row.items()} for row in reader)
    except TopologyGoldPackError:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise TopologyGoldPackError(
            f"unable to read {path.name}: {type(exc).__name__}"
        ) from exc


def _json_handles(
    value: Any,
    table: str,
    row_number: int,
    errors: list[str],
) -> tuple[str, ...]:
    try:
        parsed = json.loads(_text(value))
    except (TypeError, json.JSONDecodeError):
        errors.append(f"INVALID_SOURCE_HANDLES: {table} row {row_number}")
        return ()
    if not isinstance(parsed, list) or not parsed:
        errors.append(f"INVALID_SOURCE_HANDLES: {table} row {row_number}")
        return ()
    handles = tuple(_normalized_handle(item) for item in parsed)
    if any(not handle for handle in handles) or len(set(handles)) != len(handles):
        errors.append(f"INVALID_SOURCE_HANDLES: {table} row {row_number}")
    return tuple(handle for handle in handles if handle)


def _finite_coordinate(
    value: Any,
    table: str,
    row_number: int,
    field: str,
    errors: list[str],
) -> float | None:
    try:
        coordinate = float(_text(value))
    except (TypeError, ValueError):
        errors.append(f"NON_FINITE_COORDINATE: {table} row {row_number} {field}")
        return None
    if not math.isfinite(coordinate):
        errors.append(f"NON_FINITE_COORDINATE: {table} row {row_number} {field}")
        return None
    return coordinate


def _strict_bool(value: Any) -> bool | None:
    if value is True or value == 1 or _text(value).casefold() == "true":
        return True
    if value is False or value == 0 or _text(value).casefold() == "false":
        return False
    return None


def _timezone_aware_timestamp(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _normalized_handle(value: Any) -> str:
    text = _text(value)
    if not text or text.casefold() in {"nan", "none", "null"}:
        return ""
    return text.upper()


def _required_text(value: Any, field: str) -> str:
    text = _text(value)
    if not text:
        raise TopologyGoldPackError(f"{field} must be a non-empty string")
    return text


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


__all__ = [
    "CERTIFIED_STATUS",
    "COMPLETE_REVIEW_STATUS",
    "HELDOUT_USAGE",
    "HUMAN_LABEL_BASIS",
    "PENDING_REVIEW_STATUS",
    "PENDING_STATUS",
    "SCHEMA_VERSION",
    "TopologyGoldPack",
    "TopologyGoldPackError",
    "TopologyGoldValidation",
    "build_topology_gold_template",
    "load_topology_gold_pack",
    "validate_topology_gold_pack",
]
