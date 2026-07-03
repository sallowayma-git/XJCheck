from __future__ import annotations

import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Any

import pandas as pd

from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import ExtractionWarning
from dwg_audit.domain.models import Issue
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import PairCandidate
from dwg_audit.domain.models import PolylineRecord
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import SidecarInfo
from dwg_audit.domain.models import SourceFileRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TerminalStrip
from dwg_audit.domain.models import TextItem
from dwg_audit.domain.models import record_dict

_REPORT_FORMATS = ("md", "html", "xlsx")


def _frame(records: list[Any], cls: type) -> pd.DataFrame:
    columns = [field.name for field in fields(cls)]
    if not records:
        return pd.DataFrame(columns=columns)

    serialized: list[dict[str, Any]] = []
    for item in records:
        row = record_dict(item)
        for key, value in list(row.items()):
            if isinstance(value, (list, tuple, dict)):
                row[key] = json.dumps(value, ensure_ascii=False)
        serialized.append(row)
    return pd.DataFrame(serialized, columns=columns)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return slug or "project"


def write_project_artifacts(artifacts: ProjectArtifacts, output_dir: Path) -> Path:
    project_slug = _slugify(artifacts.scan.manifest.project_id)
    project_dir = output_dir / project_slug
    findings_dir = project_dir / "findings"
    project_dir.mkdir(parents=True, exist_ok=True)
    findings_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = project_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(record_dict(artifacts.scan.manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _frame(artifacts.scan.manifest.source_files, SourceFileRecord).to_parquet(findings_dir / "source_files.parquet", index=False)
    _frame(artifacts.scan.manifest.sidecars, SidecarInfo).to_parquet(findings_dir / "sidecars.parquet", index=False)
    _frame(artifacts.scan.pages, SheetRecord).to_parquet(findings_dir / "pages.parquet", index=False)
    _frame(artifacts.scan.terminal_strips, TerminalStrip).to_parquet(findings_dir / "terminal_strips.parquet", index=False)
    _frame(artifacts.texts, TextItem).to_parquet(findings_dir / "texts.parquet", index=False)
    _frame(artifacts.lines, LineEntity).to_parquet(findings_dir / "lines.parquet", index=False)
    _frame(artifacts.blocks, BlockRecord).to_parquet(findings_dir / "blocks.parquet", index=False)
    _frame(artifacts.polylines, PolylineRecord).to_parquet(findings_dir / "polylines.parquet", index=False)
    _frame(artifacts.line_groups, LineGroup).to_parquet(findings_dir / "line_groups.parquet", index=False)
    _frame(artifacts.terminal_candidates, TerminalCandidate).to_parquet(findings_dir / "terminal_candidates.parquet", index=False)
    _frame(artifacts.pair_candidates, PairCandidate).to_parquet(findings_dir / "pair_candidates.parquet", index=False)
    _frame(artifacts.pairs, Pair).to_parquet(findings_dir / "pairs.parquet", index=False)
    _frame(artifacts.extraction_warnings, ExtractionWarning).to_parquet(findings_dir / "extraction_warnings.parquet", index=False)

    findings_payload = _build_findings_payload(artifacts)
    (findings_dir / "findings.json").write_text(json.dumps(findings_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (findings_dir / "findings.md").write_text(_build_findings_markdown(findings_payload), encoding="utf-8")
    return project_dir


def write_audit_outputs(
    project_dir: Path,
    issues: list[Issue],
    pairs: list[Pair],
    source_files: list[SourceFileRecord],
    project_name: str,
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> Path:
    audit_dir = project_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    issues_frame = _frame(issues, Issue)
    issues_frame.to_parquet(audit_dir / "issues.parquet", index=False)
    issues_frame.to_json(audit_dir / "issues.json", orient="records", force_ascii=False, indent=2)

    frames = {
        "issues": issues_frame,
        "pairs": _frame(pairs, Pair),
        "low_confidence_pairs": _frame([pair for pair in pairs if pair.status != "pass"], Pair),
        "files": _frame(source_files, SourceFileRecord),
    }
    _write_reports(audit_dir, project_name, frames, formats=formats)
    return audit_dir


def _stringify_summary_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _pair_evidence_summary(pair: Pair) -> str:
    evidence = pair.evidence or {}
    parts: list[str] = []

    for key in ("filename", "sheet_no", "sheet_order", "line_start", "line_end"):
        value = evidence.get(key)
        if value in (None, "", [], {}):
            continue
        parts.append(f"{key}={_stringify_summary_value(value)}")

    line_group = evidence.get("line_group_id") or evidence.get("line_group") or pair.line_group_id
    if line_group:
        parts.append(f"line_group={line_group}")

    if pair.left_value:
        parts.append(f"left_value={pair.left_value}")
    if pair.right_value:
        parts.append(f"right_value={pair.right_value}")

    return ", ".join(parts) if parts else "no evidence"


def _build_pair_findings_summary(pairs: list[Pair]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    with_evidence = 0
    examples: list[dict[str, Any]] = []

    for pair in pairs:
        status_counts[pair.status] = status_counts.get(pair.status, 0) + 1
        if pair.evidence:
            with_evidence += 1
        if len(examples) >= 5:
            continue
        examples.append(
            {
                "pair_id": pair.pair_id,
                "status": pair.status,
                "confidence": pair.confidence,
                "summary": _pair_evidence_summary(pair),
            }
        )

    return {
        "total_pairs": len(pairs),
        "pairs_with_evidence": with_evidence,
        "status_counts": status_counts,
        "examples": examples,
    }


def _build_findings_payload(artifacts: ProjectArtifacts) -> dict[str, Any]:
    manifest = artifacts.scan.manifest
    primary_pages = [page for page in artifacts.scan.pages if page.is_primary_audit_candidate]
    failed = [item for item in manifest.source_files if item.conversion_status.startswith("failed")]
    converted = [item for item in manifest.source_files if item.conversion_status in {"converted", "cached"}]
    return {
        "project_name": manifest.project_name,
        "project_id": manifest.project_id,
        "input_root": manifest.input_root,
        "file_count": manifest.file_count,
        "sheet_count": manifest.sheet_count,
        "valid_dwg_files": manifest.valid_dwg_files,
        "invalid_dwg_files": manifest.invalid_dwg_files,
        "primary_audit_pages": len(primary_pages),
        "converted_pages": len(converted),
        "failed_pages": len(failed),
        "sidecars": [record_dict(sidecar) for sidecar in manifest.sidecars],
        "warnings": manifest.warnings,
        "stats": {
            "texts": len(artifacts.texts),
            "lines": len(artifacts.lines),
            "blocks": len(artifacts.blocks),
            "polylines": len(artifacts.polylines),
            "line_groups": len(artifacts.line_groups),
            "terminal_candidates": len(artifacts.terminal_candidates),
            "pair_candidates": len(artifacts.pair_candidates),
            "pairs": len(artifacts.pairs),
            "issues": len(artifacts.issues),
            "extraction_warnings": len(artifacts.extraction_warnings),
        },
        "pair_evidence_summary": _build_pair_findings_summary(artifacts.pairs),
        "failed_files": [
            {
                "filename": item.filename,
                "conversion_status": item.conversion_status,
                "conversion_detail": item.conversion_detail,
            }
            for item in failed
        ],
        "key_observations": [
            "当前流水线支持按文件级继续执行，坏页不会阻断整项目 findings 生成。",
            "ODA 转换使用 ASCII staging，以规避中文路径兼容问题。",
            "sheet_no 与 sheet_order 分离保存，避免重复页号覆盖。",
        ],
        "artifacts": {
            "findings": [
                "findings.md",
                "findings.json",
                "pages.parquet",
                "texts.parquet",
                "blocks.parquet",
                "lines.parquet",
                "polylines.parquet",
                "line_groups.parquet",
                "terminal_candidates.parquet",
                "pair_candidates.parquet",
                "pairs.parquet",
                "extraction_warnings.parquet",
                "source_files.parquet",
                "sidecars.parquet",
                "terminal_strips.parquet",
            ],
            "audit": [
                "issues.parquet",
                "issues.json",
                "audit_report.md",
                "audit_report.html",
                "issues.xlsx",
            ],
        },
    }


def _build_findings_markdown(payload: dict[str, Any]) -> str:
    pair_summary = payload["pair_evidence_summary"]
    lines = [
        "# Findings",
        "",
        f"项目：{payload['project_name']}",
        f"输入目录：`{payload['input_root']}`",
        f"DWG 文件数：`{payload['file_count']}`",
        f"有效 DWG 头：`{payload['valid_dwg_files']}`",
        f"无效 DWG 头：`{payload['invalid_dwg_files']}`",
        f"主审计页数：`{payload['primary_audit_pages']}`",
        f"成功转换页数：`{payload['converted_pages']}`",
        f"转换失败页数：`{payload['failed_pages']}`",
        "",
        "## Sidecars",
        "",
    ]
    for sidecar in payload["sidecars"]:
        lines.append(f"- `{sidecar['kind']}`: `{sidecar['status']}`")
    lines.extend(
        [
            "",
            "## 抽取统计",
            "",
            f"- Texts: `{payload['stats']['texts']}`",
            f"- Lines: `{payload['stats']['lines']}`",
            f"- Blocks: `{payload['stats']['blocks']}`",
            f"- Polylines: `{payload['stats']['polylines']}`",
            f"- LineGroups: `{payload['stats']['line_groups']}`",
            f"- TerminalCandidates: `{payload['stats']['terminal_candidates']}`",
            f"- PairCandidates: `{payload['stats']['pair_candidates']}`",
            f"- Pairs: `{payload['stats']['pairs']}`",
            f"- Issues: `{payload['stats']['issues']}`",
            f"- ExtractionWarnings: `{payload['stats']['extraction_warnings']}`",
            "",
            "## Pair Evidence 摘要",
            "",
            f"- PairsWithEvidence: `{pair_summary['pairs_with_evidence']}/{pair_summary['total_pairs']}`",
            f"- StatusCounts: `{json.dumps(pair_summary['status_counts'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## 关键观察",
            "",
        ]
    )
    for item in pair_summary["examples"]:
        confidence = item["confidence"]
        confidence_text = f"{confidence:.2f}" if isinstance(confidence, (float, int)) else str(confidence)
        lines.append(f"- `{item['pair_id']}` ({item['status']}, conf={confidence_text}): {item['summary']}")
    for item in payload["key_observations"]:
        lines.append(f"- {item}")
    if payload["failed_files"]:
        lines.extend(["", "## 转换失败页", ""])
        for item in payload["failed_files"]:
            lines.append(f"- `{item['filename']}`: {item['conversion_detail'] or item['conversion_status']}")
    return "\n".join(lines) + "\n"


def export_reports(
    project_dir: Path,
    artifacts: ProjectArtifacts,
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> None:
    frames = {
        "issues": _frame(artifacts.issues, Issue),
        "pairs": _frame(artifacts.pairs, Pair),
        "low_confidence_pairs": _frame(
            [pair for pair in artifacts.pairs if pair.status != "pass"],
            Pair,
        ),
        "files": _frame(artifacts.scan.manifest.source_files, SourceFileRecord),
    }
    _write_reports(project_dir / "audit", artifacts.scan.manifest.project_name, frames, formats=formats)


def _normalize_report_formats(formats: list[str] | tuple[str, ...] | set[str] | str | None) -> set[str]:
    if formats is None:
        return set(_REPORT_FORMATS)
    requested = formats.split(",") if isinstance(formats, str) else list(formats)
    normalized = {item.strip().lower().lstrip(".") for item in requested if item and item.strip()}
    unknown = normalized.difference(_REPORT_FORMATS)
    if unknown:
        raise ValueError(f"Unsupported report format(s): {', '.join(sorted(unknown))}")
    if not normalized:
        raise ValueError("At least one report format is required.")
    return normalized


def _decode_jsonish(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, float) and pd.isna(raw):
        return None
    if isinstance(raw, str) and not raw:
        return None
    if isinstance(raw, (list, tuple, dict)) and not raw:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return None


def _read_evidence_key(row: pd.Series, key: str) -> Any:
    for column in ("evidence_refs", "evidence"):
        payload = _decode_jsonish(row.get(column))
        if isinstance(payload, dict) and key in payload:
            return payload.get(key)
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and key in item:
                    return item.get(key)
    return None


def _format_evidence_part(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _format_evidence_mapping(payload: dict[str, Any]) -> str:
    preferred_keys = (
        "filename",
        "sheet_no",
        "sheet_order",
        "file_id",
        "sheet_id",
        "pair_id",
        "line_group_id",
        "left_value",
        "right_value",
        "line_start",
        "line_end",
        "confidence",
    )
    ordered_keys = [key for key in preferred_keys if key in payload]
    ordered_keys.extend(sorted(key for key in payload if key not in set(ordered_keys)))
    return ", ".join(f"{key}={_format_evidence_part(payload[key])}" for key in ordered_keys)


def _format_evidence_value(value: Any) -> str:
    payload = _decode_jsonish(value)
    if isinstance(payload, dict):
        return _format_evidence_mapping(payload)
    if isinstance(payload, list):
        parts = []
        for index, item in enumerate(payload, start=1):
            if isinstance(item, dict):
                parts.append(f"ref{index}: {_format_evidence_mapping(item)}")
            else:
                parts.append(f"ref{index}: {_format_evidence_part(item)}")
        return "; ".join(parts)
    return "" if payload is None else _format_evidence_part(payload)


def _evidence_display(row: pd.Series) -> str:
    refs = _format_evidence_value(row.get("evidence_refs"))
    if refs:
        return refs
    return _format_evidence_value(row.get("evidence"))


def _prepare_report_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or ("evidence_refs" not in frame.columns and "evidence" not in frame.columns):
        return frame
    report_frame = frame.copy()
    report_frame["evidence_display"] = report_frame.apply(_evidence_display, axis=1)
    return report_frame


def _write_reports(
    audit_dir: Path,
    project_name: str,
    frames: dict[str, pd.DataFrame],
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> None:
    selected_formats = _normalize_report_formats(formats)
    audit_dir.mkdir(parents=True, exist_ok=True)
    report_frames = {name: _prepare_report_frame(frame) for name, frame in frames.items()}

    if "md" in selected_formats:
        markdown_lines = [
            "# Audit Report",
            "",
            f"项目：{project_name}",
            "",
            "## 异常清单",
            "",
        ]
        issues = frames["issues"]
        if issues.empty:
            markdown_lines.append("未发现异常。")
        else:
            for _, row in issues.iterrows():
                title = row.get("title") or row.get("message")
                sheet_no = _read_evidence_key(row, "sheet_no")
                sheet_order = _read_evidence_key(row, "sheet_order")
                filename = _read_evidence_key(row, "filename")
                line_start = _read_evidence_key(row, "line_start")
                line_end = _read_evidence_key(row, "line_end")
                evidence = _evidence_display(row)
                markdown_lines.append(
                    f"- `{row.get('rule_id', '')}` `{row.get('severity', '')}`: {title} "
                    f"(file={filename}, sheet_no={sheet_no}, sheet_order={sheet_order}, "
                    f"line_group={row.get('line_group_id')}, left={row.get('left_value')}, right={row.get('right_value')}, "
                    f"line_start={line_start}, line_end={line_end}, confidence={row.get('confidence')}, evidence={evidence})"
                )
        (audit_dir / "audit_report.md").write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    if "html" in selected_formats:
        html = ["<html><head><meta charset='utf-8'><title>Audit Report</title></head><body>"]
        html.append(f"<h1>{project_name}</h1>")
        for name, frame in report_frames.items():
            html.append(f"<h2>{name}</h2>")
            html.append(frame.to_html(index=False, escape=False))
        html.append("</body></html>")
        (audit_dir / "audit_report.html").write_text("".join(html), encoding="utf-8")

    if "xlsx" in selected_formats:
        with pd.ExcelWriter(audit_dir / "issues.xlsx", engine="openpyxl") as writer:
            for sheet_name, frame in report_frames.items():
                frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def load_report_frames(project_dir: Path) -> dict[str, pd.DataFrame]:
    findings_dir = project_dir / "findings"
    audit_dir = project_dir / "audit"
    frames = {}
    for name in (
        "pages",
        "texts",
        "lines",
        "blocks",
        "polylines",
        "line_groups",
        "terminal_candidates",
        "pair_candidates",
        "pairs",
        "source_files",
        "sidecars",
        "terminal_strips",
        "extraction_warnings",
    ):
        path = findings_dir / f"{name}.parquet"
        frames[name] = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    issue_path = audit_dir / "issues.parquet"
    frames["issues"] = pd.read_parquet(issue_path) if issue_path.exists() else pd.DataFrame()
    return frames


def export_existing_reports(
    project_dir: Path,
    formats: list[str] | tuple[str, ...] | set[str] | str | None = None,
) -> None:
    manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
    frames = load_report_frames(project_dir)
    files = frames.get("source_files", pd.DataFrame())
    pairs = frames.get("pairs", pd.DataFrame())
    low_conf = pairs[pairs["status"] != "pass"] if not pairs.empty and "status" in pairs.columns else pd.DataFrame()
    _write_reports(
        project_dir / "audit",
        manifest["project_name"],
        {
            "issues": frames.get("issues", pd.DataFrame()),
            "pairs": pairs,
            "low_confidence_pairs": low_conf,
            "files": files,
        },
        formats=formats,
    )
