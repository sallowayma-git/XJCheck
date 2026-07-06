from __future__ import annotations

from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_CAUSE_CATEGORIES = (
    "page_misclassified",
    "extractor_missing",
    "candidate_noise",
    "pairing_wrong",
    "relationship_missing",
    "rule_too_strict",
    "insufficient_evidence",
)

_SPECIALIZED_PAIR_KINDS = {
    "bridge_mapping",
    "component_mapping",
    "continuation",
    "semantic_mapping",
    "table_mapping",
    "wire_component_mapping",
}
_COMPONENT_ENDPOINT_RE = re.compile(
    r"(?:\d+-)?\d*KLP\d|(?:\d+-)?\d*QD\d|(?:\d+-)?\d*n\d{3}|YD\d|ZD\d",
    re.IGNORECASE,
)
_LOCAL_PORT_VALUES = {"1", "2", "3", "4", "5", "6"}
_NOISY_TEXT_LAYERS = {"DIM", "MARK", "BOARD"}


@dataclass(slots=True)
class RootCauseDecision:
    root_cause: str
    confidence: float
    rationale: str
    tags: list[str]
    context: dict[str, Any]


def write_issue_root_cause_audit(
    project_dir: Path,
    frames: dict[str, pd.DataFrame],
    issues_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Attach temporary root-cause diagnostics to issues and write an audit summary.

    The diagnostics are intentionally heuristic: they convert a large issue list
    into engineering buckets without changing rule outcomes.
    """

    audit_dir = project_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    enriched = enrich_issues_with_root_causes(frames, issues_frame)
    summary = build_issue_root_cause_summary(enriched)

    enriched.to_parquet(audit_dir / "issues.parquet", index=False)
    enriched.to_json(audit_dir / "issues.json", orient="records", force_ascii=False, indent=2)
    (audit_dir / "issue_root_cause_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (audit_dir / "issue_root_cause_audit.md").write_text(
        _format_root_cause_markdown(summary),
        encoding="utf-8",
    )
    return enriched


def enrich_issues_with_root_causes(
    frames: dict[str, pd.DataFrame],
    issues_frame: pd.DataFrame,
) -> pd.DataFrame:
    if issues_frame.empty:
        enriched = issues_frame.copy()
        for column in (
            "root_cause",
            "root_cause_confidence",
            "root_cause_rationale",
            "diagnostic_tags",
            "diagnostic_context",
        ):
            if column not in enriched.columns:
                enriched[column] = []
        return enriched

    context = _FrameContext(frames)
    diagnostic_columns = [
        "root_cause",
        "root_cause_confidence",
        "root_cause_rationale",
        "diagnostic_tags",
        "diagnostic_context",
        "page_type",
        "page_subtype",
        "route_target",
        "audit_disposition",
        "pair_kind",
    ]
    rows: list[dict[str, Any]] = []
    for _, issue in issues_frame.iterrows():
        decision = _classify_issue(issue, context)
        row = issue.to_dict()
        row["root_cause"] = decision.root_cause
        row["root_cause_confidence"] = decision.confidence
        row["root_cause_rationale"] = decision.rationale
        row["diagnostic_tags"] = decision.tags
        row["diagnostic_context"] = decision.context
        row["page_type"] = decision.context.get("page_type")
        row["page_subtype"] = decision.context.get("page_subtype")
        row["route_target"] = decision.context.get("route_target")
        row["audit_disposition"] = decision.context.get("audit_disposition")
        row["pair_kind"] = decision.context.get("pair_kind")
        rows.append(row)
    base_columns = [column for column in issues_frame.columns if column not in diagnostic_columns]
    return pd.DataFrame(rows, columns=[*base_columns, *diagnostic_columns])


def build_issue_root_cause_summary(enriched_issues: pd.DataFrame) -> dict[str, Any]:
    root_counts = _count_column(enriched_issues, "root_cause")
    rule_counts = _nested_counts(enriched_issues, ("rule_id", "root_cause"))
    page_counts = _page_counts(enriched_issues)
    page_type_counts = _nested_counts(enriched_issues, ("page_type", "root_cause"))
    route_counts = _nested_counts(enriched_issues, ("route_target", "root_cause"))
    pair_kind_counts = _nested_counts(enriched_issues, ("pair_kind", "root_cause"))

    return {
        "schema_version": 1,
        "issue_count": int(len(enriched_issues)),
        "root_cause_counts": root_counts,
        "rule_root_cause_counts": rule_counts,
        "page_type_root_cause_counts": page_type_counts,
        "route_root_cause_counts": route_counts,
        "pair_kind_root_cause_counts": pair_kind_counts,
        "top_pages": page_counts[:10],
        "category_definitions": {
            "page_misclassified": "Page type or audit disposition routed the page into an inconsistent audit path.",
            "extractor_missing": "The page class is plausible, but the route-specific extractor did not emit the expected structured relationship.",
            "candidate_noise": "A local number, layer marker, block pin, or non-terminal text appears to have entered terminal candidate selection.",
            "pairing_wrong": "Candidates are present, but line grouping or endpoint pairing likely split or paired the geometry incorrectly.",
            "relationship_missing": "The symptom should likely be represented as a specialized mapping rather than an ordinary pair.",
            "rule_too_strict": "A specialized relationship was extracted, but the project rule still treats it too rigidly for default-correct real samples.",
            "insufficient_evidence": "The current findings do not contain enough evidence for a narrower automated root-cause label.",
        },
    }


class _FrameContext:
    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self.pages = _index_by(frames.get("pages", pd.DataFrame()), "sheet_id")
        self.pairs = _index_by(frames.get("pairs", pd.DataFrame()), "pair_id")
        self.candidates = _index_by(frames.get("terminal_candidates", pd.DataFrame()), "candidate_id")
        self.texts = _index_by(frames.get("texts", pd.DataFrame()), "text_id")


def _classify_issue(issue: pd.Series, context: _FrameContext) -> RootCauseDecision:
    evidence = _dict_cell(issue.get("evidence"))
    pair_evidence = _dict_cell(evidence.get("pair_evidence"))
    pair = context.pairs.get(_string_cell(issue.get("pair_id")), {})
    page = context.pages.get(_string_cell(issue.get("sheet_id")), {})
    pair_kind = _string_cell(pair.get("pair_kind")) or _string_cell(pair_evidence.get("pair_kind")) or "ordinary_pair"
    rule_id = _string_cell(issue.get("rule_id")) or "unknown"
    audit_disposition = _string_cell(page.get("audit_disposition"))
    route_target = _string_cell(page.get("route_target"))
    page_type = _string_cell(page.get("page_type"))

    base_context = {
        "filename": _string_cell(issue.get("filename")) or _string_cell(page.get("filename")),
        "sheet_no": _string_cell(issue.get("sheet_no")) or _string_cell(page.get("sheet_no")),
        "page_type": page_type,
        "page_subtype": _string_cell(page.get("page_subtype")),
        "route_target": route_target,
        "audit_disposition": audit_disposition,
        "pair_kind": pair_kind,
        "rule_id": rule_id,
    }

    if audit_disposition in {"classify_only", "skip_stable"} or route_target in {"LayoutOnlyExtractor", "SkipExtractor"}:
        return RootCauseDecision(
            "page_misclassified",
            0.85,
            "Issue appeared on a page that is classified as non-audited or layout-only.",
            ["non_audit_page_has_issue"],
            base_context,
        )

    if pair_kind in _SPECIALIZED_PAIR_KINDS and pair_kind != "ordinary_pair":
        if rule_id in {
            "R-CROSS-PAGE-CONFLICT",
            "R-SEMANTIC-MAPPING-CONFLICT",
            "R-TABLE-MAPPING-SOURCE-CONFLICT",
            "R-ONE-TO-MANY",
            "R-MANY-TO-ONE",
        }:
            return RootCauseDecision(
                "rule_too_strict",
                0.6,
                "A specialized relationship exists, but the project-level rule still requires manual review on a default-correct sample.",
                ["specialized_relation_rule_review", f"pair_kind:{pair_kind}"],
                base_context,
            )
        return RootCauseDecision(
            "insufficient_evidence",
            0.4,
            "The issue already references a specialized relationship and needs human semantic confirmation.",
            [f"pair_kind:{pair_kind}"],
            base_context,
        )

    if "元件接线图" in (page_type or "") and pair_kind == "ordinary_pair":
        return RootCauseDecision(
            "extractor_missing",
            0.72,
            "Component page emitted ordinary pair symptoms instead of component_mapping evidence.",
            ["component_page_ordinary_pair"],
            base_context,
        )

    if route_target == "TableExtractor" and pair_kind == "ordinary_pair":
        return RootCauseDecision(
            "extractor_missing",
            0.7,
            "Table-routed page emitted ordinary pair symptoms instead of table_mapping evidence.",
            ["table_route_ordinary_pair"],
            base_context,
        )

    if _looks_like_relationship_missing(issue, pair, pair_evidence, page):
        return RootCauseDecision(
            "relationship_missing",
            0.68,
            "Ordinary pair symptoms match a component/semantic endpoint pattern that should likely become a structured mapping.",
            ["ordinary_pair_should_be_structured"],
            base_context,
        )

    if _looks_like_candidate_noise(issue, pair, pair_evidence, context):
        return RootCauseDecision(
            "candidate_noise",
            0.74,
            "Selected endpoint contains a local short number, noisy layer text, or block-internal candidate.",
            _candidate_noise_tags(issue, pair, pair_evidence, context),
            base_context,
        )

    if rule_id == "R-PAIR-MISSING-SIDE" and evidence.get("chain_kind") == "complementary_half_pair":
        return RootCauseDecision(
            "pairing_wrong",
            0.82,
            "Complementary half-pairs indicate one wire chain was split around inline text.",
            ["complementary_half_pair", "inline_wire_split"],
            base_context | {
                "bridge_gap": evidence.get("bridge_gap"),
                "shared_value": evidence.get("shared_value"),
            },
        )

    if rule_id in {"R-DUPLICATE-SAME-LINE"}:
        return RootCauseDecision(
            "candidate_noise",
            0.65,
            "Multiple close candidates on the same line side require candidate-source triage.",
            ["duplicate_same_line_candidates"],
            base_context,
        )

    if rule_id in {"R-CROSS-PAGE-CONFLICT", "R-ONE-TO-MANY", "R-MANY-TO-ONE", "R-MISSING-RECIPROCAL"}:
        return RootCauseDecision(
            "rule_too_strict",
            0.52,
            "Project-level consistency rule fired on a default-correct sample without enough relation-specific semantics.",
            ["project_rule_review"],
            base_context,
        )

    return RootCauseDecision(
        "insufficient_evidence",
        0.35,
        "Current issue, pair, and candidate evidence is not enough for a narrower automated diagnosis.",
        ["needs_manual_reading"],
        base_context,
    )


def _looks_like_relationship_missing(
    issue: pd.Series,
    pair: dict[str, Any],
    pair_evidence: dict[str, Any],
    page: dict[str, Any],
) -> bool:
    page_type = _string_cell(page.get("page_type")) or ""
    route_target = _string_cell(page.get("route_target")) or ""
    filename = _string_cell(page.get("filename")) or _string_cell(issue.get("filename")) or ""
    values = [
        _string_cell(issue.get("left_value")),
        _string_cell(issue.get("right_value")),
        _string_cell(pair.get("left_value")),
        _string_cell(pair.get("right_value")),
        _string_cell(pair_evidence.get("selected_left_raw_text")),
        _string_cell(pair_evidence.get("selected_right_raw_text")),
    ]
    compact = " ".join(value for value in values if value)
    has_component_endpoint = bool(_COMPONENT_ENDPOINT_RE.search(compact))
    has_local_port = any(value in _LOCAL_PORT_VALUES for value in values if value)
    if route_target == "WireDiagramExtractor" and has_component_endpoint and (has_local_port or "信号回路" in filename):
        return True
    if "端子图" in page_type and pair_evidence.get("semantic_marker_texts"):
        return True
    return False


def _looks_like_candidate_noise(
    issue: pd.Series,
    pair: dict[str, Any],
    pair_evidence: dict[str, Any],
    context: _FrameContext,
) -> bool:
    values = [
        _string_cell(issue.get("left_value")),
        _string_cell(issue.get("right_value")),
        _string_cell(pair.get("left_value")),
        _string_cell(pair.get("right_value")),
        _string_cell(pair_evidence.get("selected_left_raw_text")),
        _string_cell(pair_evidence.get("selected_right_raw_text")),
    ]
    if any(_is_bare_local_numeric(value) for value in values if value):
        return True
    for candidate in _selected_candidates(pair, pair_evidence, context):
        channel = _string_cell(candidate.get("channel"))
        source_block_name = _string_cell(candidate.get("source_block_name"))
        text_id = _string_cell(candidate.get("text_id"))
        text = context.texts.get(text_id, {})
        layer = (_string_cell(text.get("layer")) or "").upper()
        if channel and channel != "terminal_numeric_channel":
            return True
        if source_block_name and any(_is_bare_local_numeric(value) for value in values if value):
            return True
        if layer in _NOISY_TEXT_LAYERS and any(_is_bare_local_numeric(value) for value in values if value):
            return True
    return False


def _candidate_noise_tags(
    issue: pd.Series,
    pair: dict[str, Any],
    pair_evidence: dict[str, Any],
    context: _FrameContext,
) -> list[str]:
    tags: set[str] = set()
    values = [
        _string_cell(issue.get("left_value")),
        _string_cell(issue.get("right_value")),
        _string_cell(pair.get("left_value")),
        _string_cell(pair.get("right_value")),
        _string_cell(pair_evidence.get("selected_left_raw_text")),
        _string_cell(pair_evidence.get("selected_right_raw_text")),
    ]
    if any(_is_bare_local_numeric(value) for value in values if value):
        tags.add("bare_local_numeric")
    for candidate in _selected_candidates(pair, pair_evidence, context):
        channel = _string_cell(candidate.get("channel"))
        if channel and channel != "terminal_numeric_channel":
            tags.add(f"candidate_channel:{channel}")
        if _string_cell(candidate.get("source_block_name")):
            tags.add("block_internal_candidate")
        text_id = _string_cell(candidate.get("text_id"))
        text = context.texts.get(text_id, {})
        layer = (_string_cell(text.get("layer")) or "").upper()
        if layer in _NOISY_TEXT_LAYERS:
            tags.add(f"text_layer:{layer}")
    return sorted(tags) or ["candidate_noise"]


def _selected_candidates(
    pair: dict[str, Any],
    pair_evidence: dict[str, Any],
    context: _FrameContext,
) -> list[dict[str, Any]]:
    ids = {
        _string_cell(pair.get("left_candidate_id")),
        _string_cell(pair.get("right_candidate_id")),
        _string_cell(pair_evidence.get("selected_left_candidate_id")),
        _string_cell(pair_evidence.get("selected_right_candidate_id")),
    }
    return [context.candidates[item] for item in ids if item and item in context.candidates]


def _is_bare_local_numeric(value: str) -> bool:
    return value.isdigit() and len(value) <= 1


def _index_by(frame: pd.DataFrame, column: str) -> dict[str, dict[str, Any]]:
    if frame.empty or column not in frame.columns:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        key = _string_cell(row.get(column))
        if key:
            result[key] = {name: _json_safe(_decode_cell(value)) for name, value in row.to_dict().items()}
    return result


def _count_column(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if frame.empty or column not in frame.columns:
        return {}
    counter = Counter(_string_cell(value) or "unknown" for value in frame[column].tolist())
    return dict(sorted(counter.items()))


def _nested_counts(frame: pd.DataFrame, columns: tuple[str, str]) -> dict[str, dict[str, int]]:
    outer, inner = columns
    if frame.empty or outer not in frame.columns or inner not in frame.columns:
        return {}
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for _, row in frame.iterrows():
        outer_value = _string_cell(row.get(outer)) or "unknown"
        inner_value = _string_cell(row.get(inner)) or "unknown"
        counts[outer_value][inner_value] += 1
    return {key: dict(sorted(value.items())) for key, value in sorted(counts.items())}


def _page_counts(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    counter: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for _, row in frame.iterrows():
        filename = _string_cell(row.get("filename")) or "unknown"
        sheet_no = _string_cell(row.get("sheet_no")) or "unknown"
        root_cause = _string_cell(row.get("root_cause")) or "unknown"
        counter[(filename, sheet_no)][root_cause] += 1
    rows = []
    for (filename, sheet_no), counts in counter.items():
        rows.append(
            {
                "filename": filename,
                "sheet_no": sheet_no,
                "issue_count": int(sum(counts.values())),
                "root_cause_counts": dict(sorted(counts.items())),
            }
        )
    return sorted(rows, key=lambda item: (-int(item["issue_count"]), item["filename"], item["sheet_no"]))


def _format_root_cause_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Issue Root-Cause Audit",
        "",
        f"- IssueCount: `{summary['issue_count']}`",
        f"- RootCauseCounts: `{json.dumps(summary['root_cause_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## By Rule",
        "",
    ]
    for rule_id, counts in summary["rule_root_cause_counts"].items():
        lines.append(f"- `{rule_id}`: `{json.dumps(counts, ensure_ascii=False, sort_keys=True)}`")
    lines.extend(["", "## Top Pages", ""])
    for page in summary["top_pages"]:
        lines.append(
            f"- `{page['filename']}` sheet `{page['sheet_no']}`: "
            f"`{page['issue_count']}` issues, "
            f"`{json.dumps(page['root_cause_counts'], ensure_ascii=False, sort_keys=True)}`"
        )
    lines.extend(["", "## Categories", ""])
    for key, value in summary["category_definitions"].items():
        lines.append(f"- `{key}`: {value}")
    return "\n".join(lines) + "\n"


def _dict_cell(value: Any) -> dict[str, Any]:
    decoded = _decode_cell(value)
    return decoded if isinstance(decoded, dict) else {}


def _string_cell(value: Any) -> str | None:
    decoded = _decode_cell(value)
    if decoded is None:
        return None
    text = str(decoded)
    if text in {"", "None", "nan", "NaN"}:
        return None
    return text


def _decode_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, bytearray)):
        value = value.tolist()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped[:1] in {"{", "["}:
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _json_safe(value: Any) -> Any:
    value = _decode_cell(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
