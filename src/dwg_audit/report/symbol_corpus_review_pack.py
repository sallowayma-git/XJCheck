"""Top-N corpus symbol review pack generation and consumption.

Builds editable human-review templates from a non-held-out Top-N queue and
persisted project inventories.  Generated documents are always PENDING and
never auto-critical.  Consumption routes through the existing
``validate-symbol-review`` / ``promote-symbol-review`` gate.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.audit.symbol_dependency_library import AnnotationStatus
from dwg_audit.audit.symbol_dependency_library import RegistryStatus
from dwg_audit.audit.symbol_dependency_library import SourceReference
from dwg_audit.audit.symbol_dependency_library import SymbolAlias
from dwg_audit.audit.symbol_dependency_library import SymbolDefinition
from dwg_audit.audit.symbol_dependency_library import SymbolDependencyLibrary
from dwg_audit.audit.symbol_dependency_library import SymbolIdentity
from dwg_audit.audit.symbol_library_review import SymbolReviewPromotionError
from dwg_audit.audit.symbol_library_review import build_symbol_review_document
from dwg_audit.audit.symbol_library_review import load_symbol_review_document
from dwg_audit.audit.symbol_library_review import promote_symbol_review_document
from dwg_audit.audit.symbol_library_review import write_symbol_review_template
from dwg_audit.report.symbol_corpus_queue import _find_findings_dir


PACK_SCHEMA_VERSION = "symbol-corpus-review-pack-v1"
SUMMARY_SCHEMA_VERSION = "symbol-corpus-review-pack-summary-v1"
CONSUMPTION_SCHEMA_VERSION = "symbol-review-consumption-v1"

MANIFEST_FILENAME = "symbol_corpus_review_pack_manifest.json"
SUMMARY_FILENAME = "symbol_corpus_review_pack_summary.json"
COMBINED_TEMPLATE_FILENAME = "symbol_corpus_review_topn.json"
TEMPLATES_DIRNAME = "templates"
CONSUMPTION_SUMMARY_FILENAME = "symbol_review_consumption_summary.json"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _load_queue_rows(source: str | Path | Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(source, Mapping):
        rows = source.get("queue") if "queue" in source else source.get("rows")
        if rows is None and "definition_fingerprint" in source:
            return [dict(source)]
        return [dict(row) for row in (rows or []) if isinstance(row, Mapping)]
    if isinstance(source, Sequence) and not isinstance(source, (str, bytes, Path)):
        return [dict(row) for row in source if isinstance(row, Mapping)]
    path = Path(source)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, Mapping):
        return _load_queue_rows(payload)
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    raise ValueError(f"unsupported queue payload: {path}")


def _inventory_frames(
    project_dirs: Mapping[str, Path],
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for alias, project_dir in sorted(project_dirs.items()):
        findings = _find_findings_dir(Path(project_dir))
        if findings is None:
            continue
        path = findings / "symbol_definitions_v1.parquet"
        if not path.is_file():
            continue
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        out = frame.copy()
        out["source_project_alias"] = alias
        frames[alias] = out
    return frames


def build_topn_review_library(
    queue_rows: Sequence[Mapping[str, Any]],
    *,
    project_dirs: Mapping[str, Path] | None = None,
    inventory_frames: Mapping[str, pd.DataFrame] | None = None,
    top_n: int | None = None,
) -> tuple[SymbolDependencyLibrary, list[dict[str, Any]]]:
    """Build a PENDING-only library for the ranked Top-N queue families."""

    rows = [dict(row) for row in queue_rows]
    rows.sort(
        key=lambda row: (
            int(row.get("review_rank") or row.get("corpus_rank") or 10**9),
            str(row.get("definition_fingerprint") or ""),
        )
    )
    if top_n is not None:
        rows = rows[: max(1, int(top_n))]

    frames = dict(inventory_frames or {})
    if project_dirs and not frames:
        frames = _inventory_frames(project_dirs)

    symbols: list[SymbolDefinition] = []
    manifest_rows: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    claimed_definition_name_aliases: set[str] = set()

    for row in rows:
        fingerprint = _text(row.get("definition_fingerprint"))
        if not fingerprint or fingerprint.casefold() in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint.casefold())

        names = row.get("definition_names") or []
        if isinstance(names, str):
            names = [part for part in names.split("|") if part]
        names = [str(name) for name in names if str(name).strip()]
        project_ids = row.get("project_ids") or []
        if isinstance(project_ids, str):
            project_ids = [part for part in project_ids.split("|") if part]
        project_ids = [str(pid) for pid in project_ids if str(pid).strip()]

        # Prefer inventory identity fields from the first covering project.
        family = names[0] if names else fingerprint[:16]
        version = "inventory-v1"
        inventory_hit = False
        for alias in project_ids:
            frame = frames.get(alias)
            if frame is None or frame.empty or "definition_fingerprint" not in frame.columns:
                continue
            matches = frame[
                frame["definition_fingerprint"].astype(str) == fingerprint
            ]
            if matches.empty:
                continue
            hit = matches.iloc[0].to_dict()
            inventory_hit = True
            family = _text(hit.get("symbol_family")) or _text(hit.get("definition_name")) or family
            if not names:
                names = [_text(hit.get("definition_name"))] if _text(hit.get("definition_name")) else names
            break

        source_id = f"corpus-queue:{fingerprint[:16]}"
        # definition_name aliases must be unique within a review library. When
        # the same CAD block name maps to multiple fingerprints, keep the alias
        # only on the highest-ranked family so validation stays fail-closed.
        unique_names: list[str] = []
        for name in sorted(set(names), key=str.casefold):
            key = name.casefold()
            if key in claimed_definition_name_aliases:
                continue
            claimed_definition_name_aliases.add(key)
            unique_names.append(name)
        aliases = tuple(
            SymbolAlias(
                value=name,
                namespace="definition_name",
                source_id=source_id,
            )
            for name in unique_names
        )
        sources = (
            SourceReference(
                source_id=source_id,
                source_kind="symbol_corpus_queue",
                locator=fingerprint,
                project_id=project_ids[0] if project_ids else None,
            ),
        )
        symbol = SymbolDefinition(
            identity=SymbolIdentity(
                family=family,
                version=version,
                fingerprint=fingerprint,
            ),
            aliases=aliases,
            sources=sources,
            ports=(),
            internal_connectivity_groups=(),
            annotation_status=AnnotationStatus.PENDING_HUMAN_REVIEW,
            registry_status=RegistryStatus.UNKNOWN,
            critical_issue_eligible=False,
        )
        symbols.append(symbol)
        manifest_rows.append(
            {
                "review_rank": int(row.get("review_rank") or row.get("corpus_rank") or len(manifest_rows) + 1),
                "definition_fingerprint": fingerprint,
                "definition_names": list(names),
                "project_ids": list(project_ids),
                "total_instance_count": int(row.get("total_instance_count") or 0),
                "project_coverage": int(row.get("project_coverage") or len(project_ids)),
                "inventory_resolved": inventory_hit,
                "annotation_status": AnnotationStatus.PENDING_HUMAN_REVIEW.value,
                "registry_status": RegistryStatus.UNKNOWN.value,
                "critical_issue_eligible": False,
                "declared_port_count": 0,
                "template_relative_path": f"{TEMPLATES_DIRNAME}/{int(row.get('review_rank') or len(manifest_rows)):03d}_{fingerprint[:12]}.json",
            }
        )

    library = SymbolDependencyLibrary(symbols=tuple(symbols))
    return library, manifest_rows


def write_symbol_corpus_review_pack(
    queue_source: str | Path | Mapping[str, Any] | Sequence[Mapping[str, Any]],
    output_dir: str | Path,
    *,
    project_dirs: Mapping[str, Path] | None = None,
    top_n: int | None = 10,
) -> dict[str, Any]:
    """Write Top-N editable review templates and a pack manifest."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    templates_dir = output / TEMPLATES_DIRNAME
    templates_dir.mkdir(parents=True, exist_ok=True)

    queue_rows = _load_queue_rows(queue_source)
    library, manifest_rows = build_topn_review_library(
        queue_rows,
        project_dirs=project_dirs,
        top_n=top_n,
    )

    combined_path = write_symbol_review_template(
        library, output / COMBINED_TEMPLATE_FILENAME
    )

    per_symbol_paths: list[str] = []
    for row, symbol in zip(manifest_rows, library.symbols, strict=False):
        single = SymbolDependencyLibrary(symbols=(symbol,))
        rel = str(row["template_relative_path"])
        target = output / rel
        write_symbol_review_template(single, target)
        per_symbol_paths.append(rel)

    document = build_symbol_review_document(library)
    validation = load_symbol_review_document(document).validation
    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "pack_schema_version": PACK_SCHEMA_VERSION,
        "top_n": top_n,
        "queue_row_count": len(queue_rows),
        "template_symbol_count": len(manifest_rows),
        "pending_human_review_count": len(manifest_rows),
        "critical_issue_eligible_count": 0,
        "declared_port_count_total": 0,
        "inventory_resolved_count": sum(
            1 for row in manifest_rows if row.get("inventory_resolved")
        ),
        "promotion_ready": False,
        "auto_critical_forbidden": True,
        "shadow_only": True,
        "review_document_valid": validation.valid,
        "review_document_promotion_ready": validation.promotion_ready,
        "status": "VALID" if manifest_rows else "EMPTY",
    }
    manifest = {
        "schema_version": PACK_SCHEMA_VERSION,
        "summary": summary,
        "combined_template": COMBINED_TEMPLATE_FILENAME,
        "templates": per_symbol_paths,
        "symbols": manifest_rows,
        "instructions": {
            "annotate": (
                "Edit port local_position/outward_direction/port_type and optional "
                "internal_connectivity_groups. Keep annotation_status PENDING until "
                "a human confirms the symbol."
            ),
            "validate": "dwg-audit validate-symbol-review -i <edited.json>",
            "promote": (
                "dwg-audit promote-symbol-review -i <edited.json> -o <library.json> "
                "only after REVIEW_COMPLETE + HUMAN_CONFIRMED + REGISTERED as required."
            ),
            "consume": "dwg-audit consume-symbol-review -i <edited.json> -o <consumption_dir>",
            "constraints": [
                "PENDING symbols cannot be REGISTERED or critical_issue_eligible",
                "ASSERTED connectivity requires human-confirmed ports and review",
                "Held-out projects must not be used to tune ranking or ports",
                "Promoted libraries remain shadow-only until product promotion gates pass",
            ],
        },
    }
    (output / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / SUMMARY_FILENAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "output_dir": output,
        "manifest_path": output / MANIFEST_FILENAME,
        "summary_path": output / SUMMARY_FILENAME,
        "combined_template_path": combined_path,
        "template_paths": [output / rel for rel in per_symbol_paths],
        "summary": summary,
        "manifest": manifest,
        "library": library,
    }


def consume_symbol_review_document(
    source: str | Path | Mapping[str, Any],
    *,
    output_dir: str | Path | None = None,
    promote: bool = False,
) -> dict[str, Any]:
    """Validate a human review document and optionally promote it fail-closed.

    PENDING documents remain non-authoritative.  Promotion never auto-sets
    critical eligibility beyond what the human document already claims and the
    library validators accept.
    """

    result = load_symbol_review_document(source)
    validation = result.validation
    library = result.library

    registry_counts = Counter(
        symbol.registry_status.value for symbol in library.symbols
    )
    annotation_counts = Counter(
        symbol.annotation_status.value for symbol in library.symbols
    )
    port_annotation_counts = Counter(
        port.annotation_status.value
        for symbol in library.symbols
        for port in symbol.ports
    )
    critical_count = sum(symbol.critical_issue_eligible for symbol in library.symbols)
    registered_confirmed = [
        symbol
        for symbol in library.symbols
        if symbol.registry_status is RegistryStatus.REGISTERED
        and symbol.annotation_status is AnnotationStatus.HUMAN_CONFIRMED
    ]
    shadow_eligible_port_count = sum(
        1
        for symbol in registered_confirmed
        for port in symbol.ports
        if port.annotation_status is AnnotationStatus.HUMAN_CONFIRMED
    )

    promotion_error: str | None = None
    promoted_path: str | None = None
    promoted = False
    if promote:
        if not validation.promotion_ready:
            promotion_error = "review document is not promotion_ready"
        else:
            try:
                promoted_library = promote_symbol_review_document(source)
                promoted = True
                library = promoted_library
                if output_dir is not None:
                    out = Path(output_dir)
                    out.mkdir(parents=True, exist_ok=True)
                    target = out / "promoted_symbol_dependency_library.json"
                    target.write_text(
                        json.dumps(
                            promoted_library.to_dict(),
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    promoted_path = str(target)
            except SymbolReviewPromotionError as exc:
                promotion_error = str(exc)

    summary = {
        "schema_version": CONSUMPTION_SCHEMA_VERSION,
        "valid": validation.valid,
        "promotion_ready": validation.promotion_ready,
        "promoted": promoted,
        "promotion_error": promotion_error,
        "promoted_library_path": promoted_path,
        "symbol_count": len(library.symbols),
        "port_count": sum(len(symbol.ports) for symbol in library.symbols),
        "critical_issue_eligible_count": critical_count,
        "registry_status_counts": dict(sorted(registry_counts.items())),
        "annotation_status_counts": dict(sorted(annotation_counts.items())),
        "port_annotation_status_counts": dict(sorted(port_annotation_counts.items())),
        "registered_human_confirmed_symbol_count": len(registered_confirmed),
        "shadow_eligible_port_count": shadow_eligible_port_count,
        "auto_critical_forbidden": True,
        "shadow_only": True,
        "primary_engine_unchanged": True,
        "validation": validation.to_dict(),
    }

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / CONSUMPTION_SUMMARY_FILENAME).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (out / "symbol_review_validation.json").write_text(
            json.dumps(validation.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return {
        "summary": summary,
        "library": library,
        "validation": validation,
    }


__all__ = [
    "COMBINED_TEMPLATE_FILENAME",
    "CONSUMPTION_SCHEMA_VERSION",
    "MANIFEST_FILENAME",
    "PACK_SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "build_topn_review_library",
    "consume_symbol_review_document",
    "write_symbol_corpus_review_pack",
]
