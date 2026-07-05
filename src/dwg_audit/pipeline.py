from __future__ import annotations

import json
from pathlib import Path

from dwg_audit.audit import build_line_groups
from dwg_audit.audit import build_pairs
from dwg_audit.audit import build_terminal_candidates
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.ingest import convert_source_files
from dwg_audit.ingest import discover_project_roots
from dwg_audit.ingest import scan_project
from dwg_audit.report import write_project_artifacts
from dwg_audit.extract import extract_cad_artifacts


def _is_downstream_audit_page(page) -> bool:
    return (
        page.is_primary_audit_candidate
        and page.audit_area_bbox is not None
    )


def analyze_input_root(
    input_path: Path,
    output_path: Path,
    config: dict,
    logger,
    *,
    event_sink = None,
) -> list[Path]:
    project_roots = discover_project_roots(input_path)
    written: list[Path] = []
    summary: list[dict[str, str]] = []
    for project_root in project_roots:
        logger.info("Analyzing project root: %s", project_root)
        if event_sink is not None:
            event_sink.emit("project_started", project_root=str(project_root))
        scan = scan_project(project_root, config=config)
        if event_sink is not None:
            event_sink.emit(
                "progress",
                stage="scan",
                project_root=str(project_root),
                file_count=scan.manifest.file_count,
                sheet_count=scan.manifest.sheet_count,
            )
        convert_source_files(scan.manifest.source_files, output_path, config, logger, event_sink=event_sink)
        texts, lines, blocks, polylines, pages, extraction_warnings = extract_cad_artifacts(
            scan,
            scan.manifest.source_files,
            config,
            logger,
        )
        if event_sink is not None:
            event_sink.emit(
                "progress",
                stage="extract",
                project_root=str(project_root),
                text_count=len(texts),
                line_count=len(lines),
                block_count=len(blocks),
                polyline_count=len(polylines),
                warning_count=len(extraction_warnings),
            )
        scan.pages = pages
        audit_sheet_ids = {page.sheet_id for page in pages if _is_downstream_audit_page(page)}
        audit_pages = [page for page in pages if page.sheet_id in audit_sheet_ids]
        audit_texts = [text for text in texts if text.sheet_id in audit_sheet_ids]
        audit_lines = [line for line in lines if line.sheet_id in audit_sheet_ids]
        line_groups = build_line_groups(audit_lines, audit_pages, config, audit_texts)
        terminal_candidates = build_terminal_candidates(line_groups, audit_texts, config, audit_pages)
        pair_candidates, pairs = build_pairs(line_groups, terminal_candidates, audit_pages, config)
        if event_sink is not None:
            event_sink.emit(
                "progress",
                stage="pair",
                project_root=str(project_root),
                line_group_count=len(line_groups),
                terminal_candidate_count=len(terminal_candidates),
                pair_candidate_count=len(pair_candidates),
                pair_count=len(pairs),
            )
        artifacts = ProjectArtifacts(
            scan=scan,
            texts=texts,
            lines=lines,
            blocks=blocks,
            polylines=polylines,
            line_groups=line_groups,
            terminal_candidates=terminal_candidates,
            pair_candidates=pair_candidates,
            pairs=pairs,
            issues=[],
            extraction_warnings=extraction_warnings,
        )
        project_dir = write_project_artifacts(artifacts, output_path)
        written.append(project_dir)
        if event_sink is not None:
            event_sink.emit(
                "project_finished",
                project_root=str(project_root),
                project_dir=str(project_dir),
            )
        summary.append(
            {
                "project_name": scan.manifest.project_name,
                "project_id": scan.manifest.project_id,
                "project_root": scan.project_root,
                "artifact_dir": str(project_dir.resolve()),
            }
        )
    (output_path / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return written
