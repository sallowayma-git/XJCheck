"""MACHINE_PROPOSED electrical connection review pack.

Builds a human-reviewable pre-annotation pack from non-authoritative shadow
artifacts that already exist on a project findings bundle:

- cross-page endpoint candidates (project graph)
- open network endpoints / endpoint identities
- semantic attachment + constraint review decisions
- legacy pair review rows (connection symptoms only)

Hard safety contract
--------------------
- Every proposal is ``annotation_status=MACHINE_PROPOSED``.
- The pack is never human gold, never certification-ready, and never eligible
  for electrical union or critical auto-issues.
- Generation never mutates geometry, Pair/Issue rows, topology networks, or
  ``primary_engine``.
- Held-out projects may be packaged only as ``evaluation_only_never_tuning``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from dwg_audit.report.project_bundle import find_findings_dir, resolve_project_bundle_dir


SCHEMA_VERSION = "electrical-connection-review-pack-v1"
SUMMARY_SCHEMA_VERSION = "electrical-connection-review-pack-summary-v1"
ALGORITHM_VERSION = "electrical-connection-proposal-v1"

MACHINE_PROPOSED = "MACHINE_PROPOSED"
PENDING_HUMAN_DECISION = "PENDING"
HELD_OUT_USAGE = "evaluation_only_never_tuning"

FAMILY_CROSS_PAGE = "CROSS_PAGE_ENDPOINT_MATCH"
FAMILY_OPEN_ENDPOINT = "OPEN_ENDPOINT_LABEL"
FAMILY_ATTACHMENT_REVIEW = "SEMANTIC_ATTACHMENT_REVIEW"
FAMILY_PAIR_REVIEW = "LEGACY_PAIR_CONNECTION_REVIEW"

_TASKBOOK_CITATIONS = {
    FAMILY_CROSS_PAGE: (
        "18.8.2 Project Graph: cross-page rules only at project layer",
        "18.9.2.3 POSSIBLE/UNKNOWN/REJECTED must not enter electrical union",
        "18.9.8 human labels target CROSS_PAGE_MATCH / NOT_MATCH decisions",
    ),
    FAMILY_OPEN_ENDPOINT: (
        "18.8.3 open endpoints and witness paths remain reviewable evidence",
        "18.9.2.2 text neighbourhood cannot invent geometric connectivity",
        "18.9.8 open-endpoint / text attachment labels route to schema or library",
    ),
    FAMILY_ATTACHMENT_REVIEW: (
        "18.8.7 ConstraintResolver precedes ranking; strong constraints inviolable",
        "18.9.2.2 attachment candidates are non-topology authority",
        "18.9.8 TEXT_LABELS_PORT / TEXT_LABELS_NET require human decision routing",
    ),
    FAMILY_PAIR_REVIEW: (
        "18.8.1 topology is connectivity truth; legacy Pair is compatibility evidence",
        "18.9.2.6 alternatives and rejected candidates must be retained",
        "18.6 relation inference owns structure; rules only validate recognised relations",
    ),
}

_MANIFEST_NAME = "manifest.json"
_PROPOSALS_NAME = "proposals.json"
_SUMMARY_NAME = "summary.json"
_CHECKLIST_NAME = "HUMAN_REVIEW_CHECKLIST.md"
_CONSUMPTION_SUMMARY_NAME = "consumption_summary.json"
_DECISION_LEDGER_NAME = "human_decision_ledger.json"
_ROUTING_SUMMARY_NAME = "knowledge_routing_summary.json"

CONSUMPTION_SCHEMA_VERSION = "electrical-connection-consumption-v1"
HUMAN_REVIEWED = "HUMAN_REVIEWED"
ALLOWED_HUMAN_DECISIONS = frozenset(
    {
        PENDING_HUMAN_DECISION,
        "CONNECTED",
        "NOT_CONNECTED",
        "AMBIGUOUS",
        "DEFER",
    }
)
TERMINAL_HUMAN_DECISIONS = frozenset(
    {"CONNECTED", "NOT_CONNECTED", "AMBIGUOUS", "DEFER"}
)
_FAMILY_KNOWLEDGE_ROUTE = {
    FAMILY_CROSS_PAGE: "CROSS_PAGE",
    FAMILY_OPEN_ENDPOINT: "ENDPOINT",
    FAMILY_ATTACHMENT_REVIEW: "TEXT_ATTACHMENT",
    FAMILY_PAIR_REVIEW: "DATASET",
}


class ElectricalConnectionReviewPackError(ValueError):
    """Raised when a connection review pack cannot be built or loaded."""


@dataclass(frozen=True, slots=True)
class ElectricalConnectionReviewValidation:
    valid: bool
    proposal_count: int
    machine_proposed_count: int
    human_reviewed_count: int
    pending_decision_count: int
    decided_count: int
    review_complete: bool
    certification_ready: bool
    promotion_ready: bool
    critical_issue_eligible_count: int
    electrical_union_eligible_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def human_confirmed_count(self) -> int:
        """Backward-compatible alias for callers using confirmation terminology.

        The pack currently distinguishes only machine-proposed and human-reviewed
        rows; no row is authoritative merely because it was reviewed.
        """

        return self.human_reviewed_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "proposal_count": self.proposal_count,
            "machine_proposed_count": self.machine_proposed_count,
            "human_reviewed_count": self.human_reviewed_count,
            "pending_decision_count": self.pending_decision_count,
            "decided_count": self.decided_count,
            "review_complete": self.review_complete,
            "certification_ready": self.certification_ready,
            "promotion_ready": self.promotion_ready,
            "critical_issue_eligible_count": self.critical_issue_eligible_count,
            "electrical_union_eligible_count": self.electrical_union_eligible_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "authority": (
                MACHINE_PROPOSED
                if self.decided_count == 0
                else "MIXED_MACHINE_AND_HUMAN_DECISIONS"
            ),
            "not_a_human_gold_standard": True,
            "topology_gold_ready": False,
            "primary_engine_flip_ready": False,
        }


def build_electrical_connection_proposals(
    project_dir: str | Path,
    *,
    project_id: str,
    split: str,
    max_proposals: int = 100,
) -> list[dict[str, Any]]:
    """Build ranked MACHINE_PROPOSED connection proposals for one project."""

    project_id = _required_text(project_id, "project_id")
    split = _required_text(split, "split")
    if max_proposals <= 0:
        raise ElectricalConnectionReviewPackError("max_proposals must be positive")

    bundle = resolve_project_bundle_dir(Path(project_dir))
    findings = find_findings_dir(bundle)
    if findings is None or not findings.is_dir():
        raise ElectricalConnectionReviewPackError(
            f"project findings directory not found under {project_dir}"
        )

    proposals: list[dict[str, Any]] = []
    proposals.extend(
        _cross_page_proposals(
            findings,
            project_id=project_id,
            split=split,
        )
    )
    proposals.extend(
        _open_endpoint_proposals(
            findings,
            project_id=project_id,
            split=split,
        )
    )
    proposals.extend(
        _attachment_review_proposals(
            findings,
            project_id=project_id,
            split=split,
        )
    )
    proposals.extend(
        _pair_review_proposals(
            findings,
            project_id=project_id,
            split=split,
        )
    )

    ranked = sorted(
        proposals,
        key=lambda row: (
            int(row.get("priority_rank") or 10_000),
            -float(row.get("priority_score") or 0.0),
            str(row.get("family") or ""),
            str(row.get("proposal_id") or ""),
        ),
    )
    selected = _select_with_family_quotas(ranked, max_proposals=max_proposals)
    # Stable presentation order after ranking cut.
    for index, row in enumerate(selected, start=1):
        row["review_order"] = index
    return selected


def write_electrical_connection_review_pack(
    project_dir: str | Path,
    *,
    project_id: str,
    split: str,
    output_dir: str | Path,
    max_proposals: int = 100,
) -> dict[str, Any]:
    """Write a pending electrical connection review pack and summary."""

    output = Path(output_dir)
    existing = [
        name
        for name in (_MANIFEST_NAME, _PROPOSALS_NAME, _SUMMARY_NAME, _CHECKLIST_NAME)
        if (output / name).exists()
    ]
    if existing:
        raise ElectricalConnectionReviewPackError(
            "refusing to overwrite electrical connection review pack files: "
            + ", ".join(existing)
        )

    proposals = build_electrical_connection_proposals(
        project_dir,
        project_id=project_id,
        split=split,
        max_proposals=max_proposals,
    )
    output.mkdir(parents=True, exist_ok=True)

    family_counts = Counter(str(row.get("family") or "UNKNOWN") for row in proposals)
    heldout = _is_heldout_split(split)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "project_id": project_id,
        "split": split,
        "status": MACHINE_PROPOSED,
        "annotation_status": MACHINE_PROPOSED,
        "review_status": "PENDING_HUMAN_REVIEW",
        "not_a_human_gold_standard": True,
        "human_confirmed": False,
        "certification_ready": False,
        "promotion_ready": False,
        "critical_issue_eligible": False,
        "electrical_union_eligible": False,
        "shadow_only": True,
        "primary_engine_unchanged": True,
        "heldout_usage": HELD_OUT_USAGE if heldout else "development_review_only",
        "heldout_evaluation_only": heldout,
        "generated_at": generated_at,
        "max_proposals": max_proposals,
        "proposal_count": len(proposals),
        "source_project_dir": str(Path(project_dir)),
        "source_findings_dir": str(
            find_findings_dir(resolve_project_bundle_dir(Path(project_dir))) or ""
        ),
        "taskbook_redlines": [
            "POSSIBLE/UNKNOWN/REJECTED never enter electrical union",
            "text neighbourhood cannot establish geometric connectivity",
            "machine proposals are never human gold or primary-engine authority",
            "held-out results are evaluation-only and must not tune rules",
        ],
    }
    (output / _MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    proposals_payload = {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "project_id": project_id,
        "split": split,
        "annotation_status": MACHINE_PROPOSED,
        "not_a_human_gold_standard": True,
        "proposal_count": len(proposals),
        "proposals": proposals,
    }
    (output / _PROPOSALS_NAME).write_text(
        json.dumps(proposals_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "project_id": project_id,
        "split": split,
        "proposal_count": len(proposals),
        "by_family": dict(sorted(family_counts.items())),
        "authority": MACHINE_PROPOSED,
        "human_confirmed": False,
        "certification_ready": False,
        "promotion_ready": False,
        "critical_issue_eligible_count": 0,
        "electrical_union_eligible_count": 0,
        "primary_engine_unchanged": True,
        "heldout_evaluation_only": heldout,
    }
    (output / _SUMMARY_NAME).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checklist_path = _write_checklist(
        output / _CHECKLIST_NAME,
        project_id=project_id,
        split=split,
        proposals=proposals,
        family_counts=family_counts,
    )

    validation = validate_electrical_connection_review_pack(output)
    return {
        "manifest": manifest,
        "summary": summary,
        "proposals": proposals,
        "validation": validation.to_dict(),
        "pack_dir": str(output),
        "manifest_path": str(output / _MANIFEST_NAME),
        "proposals_path": str(output / _PROPOSALS_NAME),
        "summary_path": str(output / _SUMMARY_NAME),
        "checklist_path": str(checklist_path),
    }


def load_electrical_connection_review_pack(pack_dir: str | Path) -> dict[str, Any]:
    """Load pack files with a strict file contract."""

    pack_dir = Path(pack_dir)
    missing = [
        name
        for name in (_MANIFEST_NAME, _PROPOSALS_NAME, _SUMMARY_NAME)
        if not (pack_dir / name).is_file()
    ]
    if missing:
        raise ElectricalConnectionReviewPackError(
            "electrical connection review pack missing required files: "
            + ", ".join(missing)
        )
    manifest = _load_json(pack_dir / _MANIFEST_NAME)
    proposals_doc = _load_json(pack_dir / _PROPOSALS_NAME)
    summary = _load_json(pack_dir / _SUMMARY_NAME)
    proposals = proposals_doc.get("proposals")
    if not isinstance(proposals, list):
        raise ElectricalConnectionReviewPackError("proposals.json must contain a list")
    return {
        "manifest": manifest,
        "proposals_document": proposals_doc,
        "proposals": proposals,
        "summary": summary,
        "pack_dir": pack_dir,
    }


def validate_electrical_connection_review_pack(
    pack_dir: str | Path,
    *,
    mode: str = "machine_draft",
) -> ElectricalConnectionReviewValidation:
    """Validate pack safety and optional human-decision integrity.

    Parameters
    ----------
    mode:
        ``machine_draft`` requires pure MACHINE_PROPOSED + PENDING decisions.
        ``human_decisions`` allows terminal human decisions while remaining
        non-authoritative for topology gold / primary flip / electrical union.
    """

    mode_token = str(mode or "machine_draft").strip().lower()
    if mode_token not in {"machine_draft", "human_decisions"}:
        return ElectricalConnectionReviewValidation(
            valid=False,
            proposal_count=0,
            machine_proposed_count=0,
            human_reviewed_count=0,
            pending_decision_count=0,
            decided_count=0,
            review_complete=False,
            certification_ready=False,
            promotion_ready=False,
            critical_issue_eligible_count=0,
            electrical_union_eligible_count=0,
            errors=(f"VALIDATION_MODE_INVALID:{mode}",),
            warnings=(),
        )

    errors: list[str] = []
    warnings: list[str] = []
    try:
        pack = load_electrical_connection_review_pack(pack_dir)
    except ElectricalConnectionReviewPackError as exc:
        return ElectricalConnectionReviewValidation(
            valid=False,
            proposal_count=0,
            machine_proposed_count=0,
            human_reviewed_count=0,
            pending_decision_count=0,
            decided_count=0,
            review_complete=False,
            certification_ready=False,
            promotion_ready=False,
            critical_issue_eligible_count=0,
            electrical_union_eligible_count=0,
            errors=(str(exc),),
            warnings=(),
        )

    manifest = pack["manifest"]
    proposals = pack["proposals"]
    summary = pack["summary"]

    if str(manifest.get("schema_version") or "") != SCHEMA_VERSION:
        errors.append("MANIFEST_SCHEMA_INVALID")
    if str(summary.get("schema_version") or "") != SUMMARY_SCHEMA_VERSION:
        errors.append("SUMMARY_SCHEMA_INVALID")
    if manifest.get("not_a_human_gold_standard") is not True:
        errors.append("HUMAN_GOLD_DISCLAIMER_INVALID")
    if manifest.get("critical_issue_eligible") is True:
        errors.append("MACHINE_PACK_CRITICAL_ELIGIBLE")
    if manifest.get("electrical_union_eligible") is True:
        errors.append("MACHINE_PACK_UNION_ELIGIBLE")
    if mode_token == "machine_draft":
        if manifest.get("human_confirmed") is True:
            errors.append("MACHINE_PACK_MARKED_HUMAN_CONFIRMED")
        if manifest.get("certification_ready") is True:
            errors.append("MACHINE_PACK_MARKED_CERTIFICATION_READY")
        if manifest.get("promotion_ready") is True:
            errors.append("MACHINE_PACK_MARKED_PROMOTION_READY")
        if str(manifest.get("annotation_status") or "") != MACHINE_PROPOSED:
            errors.append("MANIFEST_ANNOTATION_STATUS_INVALID")

    machine_count = 0
    human_reviewed_count = 0
    pending_count = 0
    decided_count = 0
    critical_count = 0
    union_count = 0
    for index, row in enumerate(proposals):
        if not isinstance(row, Mapping):
            errors.append(f"PROPOSAL_{index}_NOT_OBJECT")
            continue
        status = str(row.get("annotation_status") or "")
        decision = str(row.get("human_decision") or "")
        if status == MACHINE_PROPOSED:
            machine_count += 1
        elif status == HUMAN_REVIEWED:
            human_reviewed_count += 1
            if mode_token == "machine_draft":
                errors.append(f"PROPOSAL_{index}_HUMAN_STATUS_FORBIDDEN")
        elif status in {"HUMAN_CONFIRMED", "HUMAN_CERTIFIED", "REVIEW_COMPLETE"}:
            # Reserved for other gold packs / symbol promotion.
            human_reviewed_count += 1
            errors.append(f"PROPOSAL_{index}_HUMAN_STATUS_FORBIDDEN")
        else:
            errors.append(f"PROPOSAL_{index}_ANNOTATION_STATUS_INVALID")

        if row.get("critical_issue_eligible") is True:
            critical_count += 1
            errors.append(f"PROPOSAL_{index}_CRITICAL_ELIGIBLE")
        if row.get("electrical_union_eligible") is True:
            union_count += 1
            errors.append(f"PROPOSAL_{index}_UNION_ELIGIBLE")
        if row.get("shadow_only") is not True:
            errors.append(f"PROPOSAL_{index}_SHADOW_ONLY_REQUIRED")
        if row.get("not_a_human_gold_standard") is not True:
            errors.append(f"PROPOSAL_{index}_HUMAN_GOLD_DISCLAIMER_INVALID")
        if decision not in ALLOWED_HUMAN_DECISIONS:
            errors.append(f"PROPOSAL_{index}_HUMAN_DECISION_INVALID")
        elif decision == PENDING_HUMAN_DECISION:
            pending_count += 1
        else:
            decided_count += 1
            if mode_token == "machine_draft":
                errors.append(f"PROPOSAL_{index}_DECISION_NOT_PENDING_IN_MACHINE_DRAFT")
            else:
                reviewer = _text(row.get("reviewer")) or _text(manifest.get("reviewer"))
                reviewed_at = _text(row.get("reviewed_at")) or _text(
                    manifest.get("reviewed_at")
                )
                if not reviewer:
                    errors.append(f"PROPOSAL_{index}_REVIEWER_MISSING")
                if not _timezone_aware_timestamp(reviewed_at):
                    errors.append(f"PROPOSAL_{index}_REVIEW_TIME_INVALID")
                if status == MACHINE_PROPOSED:
                    warnings.append(
                        f"PROPOSAL_{index}_DECISION_PRESENT_BUT_STATUS_STILL_MACHINE"
                    )
        if not row.get("proposal_id"):
            errors.append(f"PROPOSAL_{index}_ID_MISSING")
        if not row.get("family"):
            errors.append(f"PROPOSAL_{index}_FAMILY_MISSING")
        if not row.get("evidence_refs"):
            errors.append(f"PROPOSAL_{index}_EVIDENCE_MISSING")
        if not row.get("taskbook_citations"):
            errors.append(f"PROPOSAL_{index}_TASKBOOK_CITATION_MISSING")
        if _FAMILY_KNOWLEDGE_ROUTE.get(str(row.get("family") or "")) is None:
            errors.append(f"PROPOSAL_{index}_FAMILY_ROUTE_UNKNOWN")

    if int(summary.get("proposal_count") or -1) != len(proposals):
        errors.append("SUMMARY_PROPOSAL_COUNT_MISMATCH")
    if int(manifest.get("proposal_count") or -1) != len(proposals):
        errors.append("MANIFEST_PROPOSAL_COUNT_MISMATCH")
    if summary.get("promotion_ready") is True:
        errors.append("SUMMARY_PROMOTION_READY")
    if summary.get("certification_ready") is True:
        errors.append("SUMMARY_CERTIFICATION_READY")

    review_complete = (
        bool(proposals) and pending_count == 0 and decided_count == len(proposals)
    )
    valid = not errors
    return ElectricalConnectionReviewValidation(
        valid=valid,
        proposal_count=len(proposals),
        machine_proposed_count=machine_count,
        human_reviewed_count=human_reviewed_count,
        pending_decision_count=pending_count,
        decided_count=decided_count,
        review_complete=review_complete,
        certification_ready=False,
        promotion_ready=False,
        critical_issue_eligible_count=critical_count,
        electrical_union_eligible_count=union_count,
        errors=tuple(dict.fromkeys(errors)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def consume_electrical_connection_review_pack(
    pack_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    reviewer: str | None = None,
    reviewed_at: str | None = None,
    require_complete: bool = False,
    write_reviewed_pack: bool = True,
) -> dict[str, Any]:
    """Consume human decisions from a connection review pack.

    Safety contract
    ---------------
    - Records human decisions and knowledge-routing targets only.
    - Never marks topology gold, primary-engine flip, electrical union, or
      critical auto-issue eligibility.
    - Never mutates source findings, geometry, Pair/Issue, or runtime config.
    """

    pack_dir = Path(pack_dir)
    pack = load_electrical_connection_review_pack(pack_dir)
    manifest = dict(pack["manifest"])
    proposals_doc = dict(pack["proposals_document"])
    proposals = [dict(row) for row in pack["proposals"] if isinstance(row, Mapping)]

    reviewer_token = _text(reviewer) or _text(manifest.get("reviewer"))
    reviewed_at_token = _text(reviewed_at) or _text(manifest.get("reviewed_at"))
    if not reviewed_at_token:
        reviewed_at_token = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    decided_rows: list[dict[str, Any]] = []
    pending_rows: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    family_decision_counts: Counter[str] = Counter()

    for index, row in enumerate(proposals):
        decision = str(row.get("human_decision") or PENDING_HUMAN_DECISION)
        family = str(row.get("family") or "")
        route = _FAMILY_KNOWLEDGE_ROUTE.get(family, "DATASET")
        row_reviewer = _text(row.get("reviewer")) or reviewer_token
        row_reviewed_at = _text(row.get("reviewed_at")) or reviewed_at_token
        decision_counts[decision] += 1

        if decision == PENDING_HUMAN_DECISION:
            pending_rows.append(row)
            continue

        row["annotation_status"] = HUMAN_REVIEWED
        row["reviewer"] = row_reviewer
        row["reviewed_at"] = row_reviewed_at
        row["knowledge_route"] = route
        row["shadow_only"] = True
        row["not_a_human_gold_standard"] = True
        row["critical_issue_eligible"] = False
        row["electrical_union_eligible"] = False
        row["topology_gold_ready"] = False
        row["primary_engine_flip_ready"] = False
        family_decision_counts[f"{family}:{decision}"] += 1
        route_counts[route] += 1
        decided_rows.append(
            {
                "proposal_id": row.get("proposal_id"),
                "family": family,
                "human_decision": decision,
                "knowledge_route": route,
                "sheet_ids": list(row.get("sheet_ids") or []),
                "labels": list(row.get("labels") or []),
                "source_handles": list(row.get("source_handles") or []),
                "evidence_refs": list(row.get("evidence_refs") or []),
                "taskbook_citations": list(row.get("taskbook_citations") or []),
                "reviewer": row_reviewer,
                "reviewed_at": row_reviewed_at,
                "notes": _text(row.get("notes")),
                "shadow_only": True,
                "not_a_human_gold_standard": True,
                "electrical_union_eligible": False,
                "critical_issue_eligible": False,
                "topology_gold_ready": False,
                "primary_engine_flip_ready": False,
                "payload": dict(row.get("payload") or {}),
            }
        )
        proposals[index] = row

    proposals_doc["proposals"] = proposals
    proposals_doc["annotation_status"] = (
        HUMAN_REVIEWED if decided_rows and not pending_rows else MACHINE_PROPOSED
    )
    proposals_doc["human_decision_counts"] = dict(sorted(decision_counts.items()))
    proposals_doc["not_a_human_gold_standard"] = True

    manifest["reviewer"] = reviewer_token or None
    manifest["reviewed_at"] = reviewed_at_token if decided_rows else manifest.get("reviewed_at")
    manifest["human_decision_count"] = len(decided_rows)
    manifest["pending_decision_count"] = len(pending_rows)
    manifest["review_complete"] = bool(proposals) and not pending_rows and bool(decided_rows)
    manifest["human_confirmed"] = False
    manifest["certification_ready"] = False
    manifest["promotion_ready"] = False
    manifest["critical_issue_eligible"] = False
    manifest["electrical_union_eligible"] = False
    manifest["topology_gold_ready"] = False
    manifest["primary_engine_flip_ready"] = False
    manifest["not_a_human_gold_standard"] = True
    manifest["annotation_status"] = (
        HUMAN_REVIEWED if manifest["review_complete"] else MACHINE_PROPOSED
    )
    manifest["consumption_schema_version"] = CONSUMPTION_SCHEMA_VERSION

    out = Path(output_dir) if output_dir is not None else pack_dir
    out.mkdir(parents=True, exist_ok=True)

    if write_reviewed_pack:
        (out / _MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (out / _PROPOSALS_NAME).write_text(
            json.dumps(proposals_doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    ledger = {
        "schema_version": CONSUMPTION_SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "project_id": manifest.get("project_id"),
        "split": manifest.get("split"),
        "decision_count": len(decided_rows),
        "pending_count": len(pending_rows),
        "review_complete": manifest["review_complete"],
        "reviewer": reviewer_token or None,
        "reviewed_at": reviewed_at_token if decided_rows else None,
        "not_a_human_gold_standard": True,
        "topology_gold_ready": False,
        "primary_engine_flip_ready": False,
        "electrical_union_eligible_count": 0,
        "critical_issue_eligible_count": 0,
        "decisions": decided_rows,
    }
    (out / _DECISION_LEDGER_NAME).write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    routing = {
        "schema_version": "electrical-connection-knowledge-routing-v1",
        "by_route": dict(sorted(route_counts.items())),
        "by_family_decision": dict(sorted(family_decision_counts.items())),
        "routing_policy": {
            FAMILY_CROSS_PAGE: "CROSS_PAGE",
            FAMILY_OPEN_ENDPOINT: "ENDPOINT",
            FAMILY_ATTACHMENT_REVIEW: "TEXT_ATTACHMENT",
            FAMILY_PAIR_REVIEW: "DATASET",
        },
        "forbidden_routes": [
            "ISSUE_ID_PATCH",
            "ASSERTED_ELECTRICAL_UNION",
            "PRIMARY_ENGINE_FLIP",
            "TOPOLOGY_GOLD_AUTO_CERTIFY",
        ],
    }
    (out / _ROUTING_SUMMARY_NAME).write_text(
        json.dumps(routing, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    validation = validate_electrical_connection_review_pack(out, mode="human_decisions")
    if require_complete and not validation.review_complete:
        errors = list(validation.errors) + ["REVIEW_INCOMPLETE"]
        validation = ElectricalConnectionReviewValidation(
            valid=False,
            proposal_count=validation.proposal_count,
            machine_proposed_count=validation.machine_proposed_count,
            human_reviewed_count=validation.human_reviewed_count,
            pending_decision_count=validation.pending_decision_count,
            decided_count=validation.decided_count,
            review_complete=False,
            certification_ready=False,
            promotion_ready=False,
            critical_issue_eligible_count=validation.critical_issue_eligible_count,
            electrical_union_eligible_count=validation.electrical_union_eligible_count,
            errors=tuple(dict.fromkeys(errors)),
            warnings=validation.warnings,
        )

    if decided_rows and not reviewer_token:
        errors = list(validation.errors) + ["REVIEWER_MISSING"]
        validation = ElectricalConnectionReviewValidation(
            valid=False,
            proposal_count=validation.proposal_count,
            machine_proposed_count=validation.machine_proposed_count,
            human_reviewed_count=validation.human_reviewed_count,
            pending_decision_count=validation.pending_decision_count,
            decided_count=validation.decided_count,
            review_complete=False,
            certification_ready=False,
            promotion_ready=False,
            critical_issue_eligible_count=validation.critical_issue_eligible_count,
            electrical_union_eligible_count=validation.electrical_union_eligible_count,
            errors=tuple(dict.fromkeys(errors)),
            warnings=validation.warnings,
        )

    consumption = {
        "schema_version": CONSUMPTION_SCHEMA_VERSION,
        "project_id": manifest.get("project_id"),
        "split": manifest.get("split"),
        "pack_dir": str(out),
        "source_pack_dir": str(pack_dir),
        "decision_count": len(decided_rows),
        "pending_count": len(pending_rows),
        "review_complete": validation.review_complete,
        "by_decision": dict(sorted(decision_counts.items())),
        "by_route": dict(sorted(route_counts.items())),
        "reviewer": reviewer_token or None,
        "reviewed_at": reviewed_at_token if decided_rows else None,
        "valid": validation.valid,
        "promotion_ready": False,
        "certification_ready": False,
        "topology_gold_ready": False,
        "primary_engine_flip_ready": False,
        "electrical_union_eligible_count": 0,
        "critical_issue_eligible_count": 0,
        "not_a_human_gold_standard": True,
        "shadow_only": True,
        "primary_engine_unchanged": True,
        "ledger_path": str(out / _DECISION_LEDGER_NAME),
        "routing_summary_path": str(out / _ROUTING_SUMMARY_NAME),
        "validation": validation.to_dict(),
    }
    (out / _CONSUMPTION_SUMMARY_NAME).write_text(
        json.dumps(consumption, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = dict(pack["summary"])
    summary["human_decision_count"] = len(decided_rows)
    summary["pending_decision_count"] = len(pending_rows)
    summary["review_complete"] = validation.review_complete
    summary["promotion_ready"] = False
    summary["certification_ready"] = False
    summary["human_confirmed"] = False
    summary["topology_gold_ready"] = False
    summary["primary_engine_flip_ready"] = False
    if write_reviewed_pack:
        (out / _SUMMARY_NAME).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return consumption


def apply_human_decisions_for_tests(
    pack_dir: str | Path,
    decisions: Mapping[str, str],
    *,
    reviewer: str,
    reviewed_at: str,
) -> None:
    """Test helper: fill selected proposal decisions in-place."""

    pack = load_electrical_connection_review_pack(pack_dir)
    proposals_doc = dict(pack["proposals_document"])
    proposals = []
    for row in pack["proposals"]:
        item = dict(row)
        proposal_id = str(item.get("proposal_id") or "")
        if proposal_id in decisions:
            item["human_decision"] = decisions[proposal_id]
            item["reviewer"] = reviewer
            item["reviewed_at"] = reviewed_at
        proposals.append(item)
    proposals_doc["proposals"] = proposals
    manifest = dict(pack["manifest"])
    manifest["reviewer"] = reviewer
    manifest["reviewed_at"] = reviewed_at
    pack_dir = Path(pack_dir)
    (pack_dir / _PROPOSALS_NAME).write_text(
        json.dumps(proposals_doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (pack_dir / _MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _timezone_aware_timestamp(value: str) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _select_with_family_quotas(
    ranked: Sequence[Mapping[str, Any]],
    *,
    max_proposals: int,
) -> list[dict[str, Any]]:
    """Keep global rank order while reserving slots for each evidence family.

    Cross-page candidates dominate raw volume on real projects. Without a
    soft quota, open-endpoint / attachment / pair reviews never reach humans.
    """

    if max_proposals <= 0:
        return []
    if len(ranked) <= max_proposals:
        return [dict(row) for row in ranked]

    families = [
        FAMILY_CROSS_PAGE,
        FAMILY_ATTACHMENT_REVIEW,
        FAMILY_OPEN_ENDPOINT,
        FAMILY_PAIR_REVIEW,
    ]
    # Soft floors: leave room for mixed evidence without starving dominant families.
    floors = {
        FAMILY_CROSS_PAGE: max(1, int(max_proposals * 0.40)),
        FAMILY_ATTACHMENT_REVIEW: max(1, int(max_proposals * 0.20)),
        FAMILY_OPEN_ENDPOINT: max(1, int(max_proposals * 0.20)),
        FAMILY_PAIR_REVIEW: max(1, int(max_proposals * 0.10)),
    }
    # Ensure floors never exceed capacity.
    while sum(floors.values()) > max_proposals:
        richest = max(floors, key=lambda key: floors[key])
        if floors[richest] <= 1:
            break
        floors[richest] -= 1

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    counts: Counter[str] = Counter()

    def _take(row: Mapping[str, Any]) -> None:
        proposal_id = str(row.get("proposal_id") or "")
        if proposal_id in selected_ids:
            return
        if len(selected) >= max_proposals:
            return
        selected.append(dict(row))
        selected_ids.add(proposal_id)
        counts[str(row.get("family") or "UNKNOWN")] += 1

    # Pass 1: honour soft floors in global rank order.
    for family in families:
        floor = floors.get(family, 0)
        if floor <= 0:
            continue
        for row in ranked:
            if len(selected) >= max_proposals:
                break
            if str(row.get("family") or "") != family:
                continue
            if counts[family] >= floor:
                break
            _take(row)

    # Pass 2: fill remaining slots by pure rank.
    for row in ranked:
        if len(selected) >= max_proposals:
            break
        _take(row)

    # Re-sort selected by original rank for presentation.
    selected.sort(
        key=lambda row: (
            int(row.get("priority_rank") or 10_000),
            -float(row.get("priority_score") or 0.0),
            str(row.get("family") or ""),
            str(row.get("proposal_id") or ""),
        )
    )
    return selected


def _cross_page_proposals(
    findings: Path,
    *,
    project_id: str,
    split: str,
) -> list[dict[str, Any]]:
    path = findings / "cross_page_endpoint_candidates_v1.parquet"
    if not path.is_file():
        return []
    frame = _read_parquet(path)
    if frame.empty:
        return []

    label_counts = (
        frame["label"].astype(str).value_counts()
        if "label" in frame.columns
        else pd.Series(dtype=int)
    )
    proposals: list[dict[str, Any]] = []
    for row in frame.to_dict(orient="records"):
        label = _text(row.get("label"))
        alternatives = int(label_counts.get(label, 1)) if label else 1
        confidence = _confidence(row.get("confidence"))
        reciprocal = bool(row.get("reciprocal"))
        # High-impact ambiguous cross-page labels first; unique high-confidence next.
        priority_score = (
            40.0
            + min(alternatives, 50) * 1.5
            + (8.0 if reciprocal else 0.0)
            + confidence * 10.0
        )
        priority_rank = 10 if alternatives > 2 else 20
        sheet_ids = _unique_texts([row.get("sheet_id_a"), row.get("sheet_id_b")])
        proposal_id = _proposal_id(
            FAMILY_CROSS_PAGE,
            row.get("match_id") or label,
            *sheet_ids,
        )
        proposals.append(
            _base_proposal(
                proposal_id=proposal_id,
                family=FAMILY_CROSS_PAGE,
                project_id=project_id,
                split=split,
                confidence=confidence,
                priority_rank=priority_rank,
                priority_score=priority_score,
                sheet_ids=sheet_ids,
                labels=[label] if label else [],
                source_handles=[],
                source_line_ids=[],
                coords=[],
                reason_codes=_reason_list(row.get("reason_codes"))
                + ([f"LABEL_ALTERNATIVES_{alternatives}"] if alternatives else []),
                evidence_refs=[
                    {
                        "artifact": "findings/cross_page_endpoint_candidates_v1.parquet",
                        "match_id": _text(row.get("match_id")),
                        "endpoint_id_a": _text(row.get("endpoint_id_a")),
                        "endpoint_id_b": _text(row.get("endpoint_id_b")),
                        "relation": _text(row.get("relation")),
                        "state": _text(row.get("state")),
                    }
                ],
                machine_rationale=(
                    f"Shared label {label!r} links endpoints on "
                    f"{'/'.join(sheet_ids) or 'unknown sheets'} "
                    f"(reciprocal={reciprocal}, alternatives={alternatives}). "
                    "Cross-page match remains CANDIDATE/MACHINE_PROPOSED until human review."
                ),
                payload={
                    "match_id": _text(row.get("match_id")),
                    "endpoint_id_a": _text(row.get("endpoint_id_a")),
                    "endpoint_id_b": _text(row.get("endpoint_id_b")),
                    "relation": _text(row.get("relation")),
                    "state": _text(row.get("state")),
                    "reciprocal": reciprocal,
                    "label_alternative_count": alternatives,
                    "suggested_human_decision_options": [
                        "CONNECTED",
                        "NOT_CONNECTED",
                        "AMBIGUOUS",
                        "DEFER",
                    ],
                },
            )
        )
    return proposals


def _open_endpoint_proposals(
    findings: Path,
    *,
    project_id: str,
    split: str,
) -> list[dict[str, Any]]:
    path = findings / "endpoint_identities_v1.parquet"
    if not path.is_file():
        # Fall back to open-endpoint geometry only.
        open_path = findings / "network_open_endpoints_v2.parquet"
        if not open_path.is_file():
            return []
        frame = _read_parquet(open_path)
        proposals: list[dict[str, Any]] = []
        for row in frame.to_dict(orient="records"):
            sheet_id = _text(row.get("sheet_id"))
            node_id = _text(row.get("node_id"))
            handles = _json_list(row.get("source_handles"))
            line_ids = _json_list(row.get("source_line_ids"))
            coord = _coord_pair(row.get("coord"))
            proposal_id = _proposal_id(FAMILY_OPEN_ENDPOINT, sheet_id, node_id, *handles[:2])
            proposals.append(
                _base_proposal(
                    proposal_id=proposal_id,
                    family=FAMILY_OPEN_ENDPOINT,
                    project_id=project_id,
                    split=split,
                    confidence=0.35,
                    priority_rank=40,
                    priority_score=25.0,
                    sheet_ids=[sheet_id] if sheet_id else [],
                    labels=[],
                    source_handles=handles,
                    source_line_ids=line_ids,
                    coords=[coord] if coord else [],
                    reason_codes=[_text(row.get("reason_code")) or "OPEN_ENDPOINT"],
                    evidence_refs=[
                        {
                            "artifact": "findings/network_open_endpoints_v2.parquet",
                            "electrical_network_id": _text(row.get("electrical_network_id")),
                            "node_id": node_id,
                            "sheet_id": sheet_id,
                        }
                    ],
                    machine_rationale=(
                        "Geometry-only open endpoint with no endpoint-identity label. "
                        "Human review may attach a terminal/port label or mark unresolved."
                    ),
                    payload={
                        "electrical_network_id": _text(row.get("electrical_network_id")),
                        "node_id": node_id,
                        "boundary_state": _text(row.get("boundary_state")),
                        "authority": "GEOMETRY_ONLY",
                    },
                )
            )
        return proposals

    frame = _read_parquet(path)
    if frame.empty:
        return []

    # Prefer labeled authoritative open endpoints and unlabeled geometry opens.
    proposals = []
    for row in frame.to_dict(orient="records"):
        identity_kind = _text(row.get("identity_kind"))
        if identity_kind not in {"NETWORK_OPEN", "ATTACHMENT_SELECTED", ""}:
            # Keep only open/attachment identities for connection review.
            if _text(row.get("boundary_state")) != "OPEN":
                continue
        authority = _text(row.get("authority")) or "UNKNOWN"
        label = _text(row.get("label")) or _text(row.get("attached_token_text"))
        sheet_id = _text(row.get("sheet_id"))
        handles = _json_list(row.get("source_handles"))
        line_ids = _json_list(row.get("source_line_ids"))
        coord = None
        if row.get("coord_x") is not None and row.get("coord_y") is not None:
            try:
                coord = (float(row["coord_x"]), float(row["coord_y"]))
            except (TypeError, ValueError):
                coord = None

        if authority == "AUTHORITATIVE" and label:
            priority_rank = 30
            priority_score = 32.0 + min(len(label), 12) * 0.4
            confidence = 0.7
            rationale = (
                f"Authoritative open endpoint labelled {label!r} on {sheet_id or 'sheet'}. "
                "Confirm whether the label owns this network end or is only nearby text."
            )
        elif authority == "GEOMETRY_ONLY":
            priority_rank = 45
            priority_score = 18.0
            confidence = 0.3
            rationale = (
                "Geometry-only open endpoint without authoritative attachment. "
                "Do not invent connectivity from text proximity alone."
            )
        else:
            priority_rank = 50
            priority_score = 15.0
            confidence = 0.4
            rationale = "Open endpoint identity needs human label/attachment confirmation."

        proposal_id = _proposal_id(
            FAMILY_OPEN_ENDPOINT,
            row.get("endpoint_id") or row.get("node_id"),
            sheet_id,
            label,
        )
        proposals.append(
            _base_proposal(
                proposal_id=proposal_id,
                family=FAMILY_OPEN_ENDPOINT,
                project_id=project_id,
                split=split,
                confidence=confidence,
                priority_rank=priority_rank,
                priority_score=priority_score,
                sheet_ids=[sheet_id] if sheet_id else [],
                labels=[label] if label else [],
                source_handles=handles,
                source_line_ids=line_ids,
                coords=[coord] if coord else [],
                reason_codes=_unique_texts(
                    [
                        identity_kind,
                        authority,
                        _text(row.get("boundary_state")),
                        _text(row.get("attached_token_kind")),
                    ]
                ),
                evidence_refs=[
                    {
                        "artifact": "findings/endpoint_identities_v1.parquet",
                        "endpoint_id": _text(row.get("endpoint_id")),
                        "electrical_network_id": _text(row.get("electrical_network_id")),
                        "node_id": _text(row.get("node_id")),
                        "attachment_id": _text(row.get("attachment_id")),
                        "authority": authority,
                    }
                ],
                machine_rationale=rationale,
                payload={
                    "endpoint_id": _text(row.get("endpoint_id")),
                    "identity_kind": identity_kind,
                    "namespace": _text(row.get("namespace")),
                    "local_key": _text(row.get("local_key")),
                    "attached_token_id": _text(row.get("attached_token_id")),
                    "attached_token_kind": _text(row.get("attached_token_kind")),
                    "authority": authority,
                    "suggested_human_decision_options": [
                        "CONNECTED",
                        "NOT_CONNECTED",
                        "AMBIGUOUS",
                        "DEFER",
                    ],
                },
            )
        )
    return proposals


def _attachment_review_proposals(
    findings: Path,
    *,
    project_id: str,
    split: str,
) -> list[dict[str, Any]]:
    decisions_path = findings / "constraint_decisions.parquet"
    attachments_path = findings / "semantic_attachment_candidates.parquet"
    if not decisions_path.is_file():
        return []

    decisions = _read_parquet(decisions_path)
    if decisions.empty:
        return []
    if "state" in decisions.columns:
        review = decisions[
            decisions["state"].astype(str).isin(["REVIEW", "VIOLATION"])
        ]
    else:
        review = decisions.iloc[0:0]
    if review.empty and "authority" in decisions.columns:
        # Some frames store authority only.
        review = decisions[
            decisions["authority"].astype(str).isin(["REVIEW_ONLY", "REJECTED"])
        ]
    if review.empty:
        return []

    attachments = (
        _read_parquet(attachments_path)
        if attachments_path.is_file()
        else pd.DataFrame()
    )
    attachment_by_id: dict[str, dict[str, Any]] = {}
    if not attachments.empty and "attachment_id" in attachments.columns:
        for row in attachments.to_dict(orient="records"):
            attachment_by_id[_text(row.get("attachment_id"))] = row

    proposals: list[dict[str, Any]] = []
    for row in review.to_dict(orient="records"):
        attachment_id = _text(row.get("attachment_id"))
        att = attachment_by_id.get(attachment_id, {})
        constraint_kind = _text(row.get("constraint_kind")) or "CONSTRAINT_REVIEW"
        sheet_id = _text(row.get("sheet_id")) or _text(att.get("sheet_id"))
        token_text = _text(att.get("token_text"))
        confidence = _confidence(att.get("score")) if att else 0.4
        if constraint_kind == "LOW_MARGIN_REVIEW":
            priority_rank = 25
            priority_score = 36.0 + (1.0 - min(confidence, 1.0)) * 10.0
        elif constraint_kind == "SCOPE_AMBIGUITY_NOT_AUTHORITATIVE":
            priority_rank = 28
            priority_score = 34.0
        else:
            priority_rank = 35
            priority_score = 28.0

        handles = _json_list(att.get("source_handles")) if att else []
        line_ids = _unique_texts([att.get("target_line_id")]) if att else []
        coord = None
        if att and att.get("target_x") is not None and att.get("target_y") is not None:
            try:
                coord = (float(att["target_x"]), float(att["target_y"]))
            except (TypeError, ValueError):
                coord = None

        proposal_id = _proposal_id(
            FAMILY_ATTACHMENT_REVIEW,
            row.get("decision_id") or attachment_id,
            sheet_id,
            constraint_kind,
        )
        proposals.append(
            _base_proposal(
                proposal_id=proposal_id,
                family=FAMILY_ATTACHMENT_REVIEW,
                project_id=project_id,
                split=split,
                confidence=confidence,
                priority_rank=priority_rank,
                priority_score=priority_score,
                sheet_ids=[sheet_id] if sheet_id else [],
                labels=[token_text] if token_text else [],
                source_handles=handles,
                source_line_ids=line_ids,
                coords=[coord] if coord else [],
                reason_codes=_unique_texts(
                    [
                        constraint_kind,
                        _text(row.get("severity")),
                        _text(row.get("state")),
                        *_reason_list(row.get("reason_codes")),
                        *_reason_list(att.get("reason_codes")),
                        *_reason_list(att.get("constraint_reason_codes")),
                        *_reason_list(att.get("scope_reason_codes")),
                    ]
                ),
                evidence_refs=[
                    {
                        "artifact": "findings/constraint_decisions.parquet",
                        "decision_id": _text(row.get("decision_id")),
                        "attachment_id": attachment_id,
                        "token_id": _text(row.get("token_id") or att.get("token_id")),
                        "constraint_kind": constraint_kind,
                        "state": _text(row.get("state")),
                        "authority": _text(row.get("authority")),
                    },
                    *(
                        [
                            {
                                "artifact": "findings/semantic_attachment_candidates.parquet",
                                "attachment_id": attachment_id,
                                "token_kind": _text(att.get("token_kind")),
                                "target_line_id": _text(att.get("target_line_id")),
                                "selected": bool(att.get("selected")),
                                "scope_state": _text(att.get("scope_state")),
                            }
                        ]
                        if att
                        else []
                    ),
                ],
                machine_rationale=(
                    f"Constraint {constraint_kind} left attachment "
                    f"{attachment_id or 'unknown'} in review "
                    f"(token={token_text!r}). "
                    "Strong constraints stay inviolable; human decides label ownership."
                ),
                payload={
                    "decision_id": _text(row.get("decision_id")),
                    "attachment_id": attachment_id,
                    "token_id": _text(row.get("token_id") or att.get("token_id")),
                    "token_kind": _text(att.get("token_kind")),
                    "constraint_kind": constraint_kind,
                    "scope_state": _text(att.get("scope_state")),
                    "margin": att.get("margin"),
                    "suggested_human_decision_options": [
                        "CONNECTED",
                        "NOT_CONNECTED",
                        "AMBIGUOUS",
                        "DEFER",
                    ],
                },
            )
        )
    return proposals


def _pair_review_proposals(
    findings: Path,
    *,
    project_id: str,
    split: str,
) -> list[dict[str, Any]]:
    path = findings / "pairs.parquet"
    if not path.is_file():
        return []
    frame = _read_parquet(path)
    if frame.empty or "status" not in frame.columns:
        return []
    review = frame[frame["status"].astype(str) == "review"]
    if review.empty:
        return []

    proposals: list[dict[str, Any]] = []
    for row in review.to_dict(orient="records"):
        pair_kind = _text(row.get("pair_kind")) or "ordinary_pair"
        confidence = _confidence(row.get("confidence"))
        sheet_id = _text(row.get("sheet_id"))
        left = _text(row.get("left_value"))
        right = _text(row.get("right_value"))
        labels = _unique_texts([left, right])
        # Continuations and semantic mappings are higher-value connection reviews.
        kind_boost = {
            "semantic_mapping": 12.0,
            "continuation": 10.0,
            "bridge_mapping": 11.0,
            "ordinary_pair": 6.0,
            "wire_component_mapping": 8.0,
            "component_mapping": 7.0,
            "table_mapping": 5.0,
        }.get(pair_kind, 4.0)
        priority_rank = 55
        priority_score = 20.0 + kind_boost + (1.0 - confidence) * 8.0
        coords = []
        for prefix in ("left", "right"):
            x = row.get(f"{prefix}_coord_x")
            y = row.get(f"{prefix}_coord_y")
            if x is None or y is None or (isinstance(x, float) and math.isnan(x)):
                continue
            try:
                coords.append((float(x), float(y)))
            except (TypeError, ValueError):
                continue
        proposal_id = _proposal_id(
            FAMILY_PAIR_REVIEW,
            row.get("pair_id"),
            sheet_id,
            pair_kind,
            left,
            right,
        )
        proposals.append(
            _base_proposal(
                proposal_id=proposal_id,
                family=FAMILY_PAIR_REVIEW,
                project_id=project_id,
                split=split,
                confidence=confidence,
                priority_rank=priority_rank,
                priority_score=priority_score,
                sheet_ids=[sheet_id] if sheet_id else [],
                labels=labels,
                source_handles=[],
                source_line_ids=_unique_texts([row.get("line_group_id")]),
                coords=coords,
                reason_codes=_unique_texts(
                    [
                        pair_kind,
                        _text(row.get("status")),
                        _text(row.get("confidence_bucket")),
                        _text(row.get("rationale")),
                    ]
                ),
                evidence_refs=[
                    {
                        "artifact": "findings/pairs.parquet",
                        "pair_id": _text(row.get("pair_id")),
                        "line_group_id": _text(row.get("line_group_id")),
                        "sheet_id": sheet_id,
                        "pair_kind": pair_kind,
                        "status": _text(row.get("status")),
                        "left_value": left,
                        "right_value": right,
                    }
                ],
                machine_rationale=(
                    f"Legacy pair {row.get('pair_id')} is in review "
                    f"({pair_kind}: {left or '?'} -> {right or '?'}). "
                    "Treat as connection symptom evidence only; topology V2 remains shadow."
                ),
                payload={
                    "pair_id": _text(row.get("pair_id")),
                    "pair_kind": pair_kind,
                    "pair_key": _text(row.get("pair_key")),
                    "left_text_id": _text(row.get("left_text_id")),
                    "right_text_id": _text(row.get("right_text_id")),
                    "suggested_human_decision_options": [
                        "CONNECTED",
                        "NOT_CONNECTED",
                        "AMBIGUOUS",
                        "DEFER",
                    ],
                },
            )
        )
    return proposals


def _base_proposal(
    *,
    proposal_id: str,
    family: str,
    project_id: str,
    split: str,
    confidence: float,
    priority_rank: int,
    priority_score: float,
    sheet_ids: Sequence[str],
    labels: Sequence[str],
    source_handles: Sequence[str],
    source_line_ids: Sequence[str],
    coords: Sequence[tuple[float, float]],
    reason_codes: Sequence[str],
    evidence_refs: Sequence[Mapping[str, Any]],
    machine_rationale: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "family": family,
        "project_id": project_id,
        "split": split,
        "annotation_status": MACHINE_PROPOSED,
        "human_decision": PENDING_HUMAN_DECISION,
        "confidence": float(confidence),
        "priority_rank": int(priority_rank),
        "priority_score": float(priority_score),
        "sheet_ids": list(sheet_ids),
        "labels": list(labels),
        "source_handles": list(source_handles),
        "source_line_ids": list(source_line_ids),
        "coords": [{"x": x, "y": y} for x, y in coords],
        "reason_codes": list(reason_codes),
        "evidence_refs": [dict(item) for item in evidence_refs],
        "taskbook_citations": list(_TASKBOOK_CITATIONS.get(family, ())),
        "machine_rationale": machine_rationale,
        "critical_issue_eligible": False,
        "electrical_union_eligible": False,
        "shadow_only": True,
        "not_a_human_gold_standard": True,
        "heldout_evaluation_only": _is_heldout_split(split),
        "payload": dict(payload),
    }


def _write_checklist(
    path: Path,
    *,
    project_id: str,
    split: str,
    proposals: Sequence[Mapping[str, Any]],
    family_counts: Mapping[str, int],
) -> Path:
    lines = [
        "# Electrical Connection Human Review Checklist",
        "",
        f"- project_id: `{project_id}`",
        f"- split: `{split}`",
        f"- proposal_count: `{len(proposals)}`",
        f"- authority: `{MACHINE_PROPOSED}` only",
        "- certification_ready: `false`",
        "- promotion_ready: `false`",
        "- primary_engine: unchanged (`legacy`)",
        "",
        "## Safety",
        "",
        "1. Do **not** treat any row as human gold until an independent human marks it.",
        "2. Do **not** union POSSIBLE/UNKNOWN/REJECTED topology into ASSERTED networks.",
        "3. Text proximity alone cannot establish geometric connectivity.",
        "4. Held-out packs are evaluation-only; never tune rules from them.",
        "",
        "## Family counts",
        "",
    ]
    if family_counts:
        for family, count in sorted(family_counts.items()):
            lines.append(f"- `{family}`: {count}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Review order (top proposals)",
            "",
            "| order | proposal_id | family | sheets | labels | confidence | decision |",
            "|---:|---|---|---|---|---:|---|",
        ]
    )
    for row in proposals[:80]:
        sheets = ",".join(str(s) for s in (row.get("sheet_ids") or [])[:4])
        labels = ",".join(str(s) for s in (row.get("labels") or [])[:4])
        lines.append(
            "| {order} | `{pid}` | `{family}` | {sheets} | {labels} | {conf:.3f} | PENDING |".format(
                order=row.get("review_order") or "",
                pid=row.get("proposal_id") or "",
                family=row.get("family") or "",
                sheets=sheets or "-",
                labels=labels or "-",
                conf=float(row.get("confidence") or 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Decision vocabulary",
            "",
            "- `CONNECTED` / `NOT_CONNECTED` / `AMBIGUOUS` / `DEFER`",
            "- Leave `human_decision=PENDING` until a human reviewer acts.",
            "",
            "## Evidence roots",
            "",
            "- `findings/cross_page_endpoint_candidates_v1.parquet`",
            "- `findings/endpoint_identities_v1.parquet`",
            "- `findings/constraint_decisions.parquet`",
            "- `findings/semantic_attachment_candidates.parquet`",
            "- `findings/pairs.parquet`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _proposal_id(family: str, *parts: Any) -> str:
    digest = hashlib.sha1(
        "|".join([family, *[str(part or "") for part in parts]]).encode("utf-8")
    ).hexdigest()[:16]
    return f"ECP-{digest}"


def _is_heldout_split(split: str) -> bool:
    token = str(split or "").strip().lower()
    return "heldout" in token or token in {"test", "held_out", "held-out"}


def _read_parquet(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except Exception as exc:  # pragma: no cover - defensive IO boundary
        raise ElectricalConnectionReviewPackError(
            f"failed to read parquet {path}: {exc}"
        ) from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ElectricalConnectionReviewPackError(
            f"failed to read json {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ElectricalConnectionReviewPackError(f"{path.name} must be a JSON object")
    return payload


def _required_text(value: Any, field: str) -> str:
    text = _text(value)
    if not text:
        raise ElectricalConnectionReviewPackError(f"{field} is required")
    return text


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _unique_texts(values: Iterable[Any]) -> list[str]:
    seen: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.append(text)
    return seen


def _confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number) or math.isinf(number):
        return 0.0
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number


def _reason_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return [text]
            if isinstance(parsed, list):
                return _unique_texts(parsed)
        return [text]
    if isinstance(value, (list, tuple, set)):
        return _unique_texts(value)
    try:
        # numpy arrays / pandas lists
        return _unique_texts(list(value))
    except TypeError:
        return [_text(value)] if _text(value) else []


def _json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and math.isnan(value):
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return [text]
            if isinstance(parsed, list):
                return _unique_texts(parsed)
        return [text]
    if isinstance(value, (list, tuple, set)):
        return _unique_texts(value)
    try:
        return _unique_texts(list(value))
    except TypeError:
        return [_text(value)] if _text(value) else []


def _coord_pair(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    try:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return float(value[0]), float(value[1])
        # numpy array
        seq = list(value)
        if len(seq) >= 2:
            return float(seq[0]), float(seq[1])
    except Exception:
        return None
    return None


__all__ = [
    "ALGORITHM_VERSION",
    "CONSUMPTION_SCHEMA_VERSION",
    "ElectricalConnectionReviewPackError",
    "ElectricalConnectionReviewValidation",
    "HUMAN_REVIEWED",
    "MACHINE_PROPOSED",
    "SCHEMA_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "apply_human_decisions_for_tests",
    "build_electrical_connection_proposals",
    "consume_electrical_connection_review_pack",
    "load_electrical_connection_review_pack",
    "validate_electrical_connection_review_pack",
    "write_electrical_connection_review_pack",
]
