from __future__ import annotations

import json
from pathlib import Path

from dwg_audit.audit.page_extractors import extract_component_pairs
from dwg_audit.audit.page_extractors import extract_layout_audit_pairs
from dwg_audit.audit.page_extractors import extract_terminal_pairs
from dwg_audit.audit.page_extractors import extract_wire_pairs
from dwg_audit.audit.extraction_gate import evaluate_extraction_completeness
from dwg_audit.audit.table_extractor import extract_table_pairs
from dwg_audit.audit.backplate_components import extract_accessory_backplate_two_port_pairs
from dwg_audit.domain.models import ProjectArtifacts
from dwg_audit.ingest import convert_source_files
from dwg_audit.ingest import discover_project_roots
from dwg_audit.ingest import scan_project
from dwg_audit.page_classifier import classify_pages
from dwg_audit.page_router import disposition_requires_audit
from dwg_audit.page_router import enrich_pages_from_classifications
from dwg_audit.page_router import route_supports_table
from dwg_audit.report import write_project_artifacts
from dwg_audit.extract import extract_cad_artifacts


def _is_downstream_audit_page(page) -> bool:
    disposition = getattr(page, "audit_disposition", None)
    if disposition is not None:
        return (
            disposition_requires_audit(disposition)
            and page.audit_area_bbox is not None
        )
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
    summary: list[dict[str, object]] = []
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
        reader_runs = convert_source_files(
            scan.manifest.source_files,
            output_path,
            config,
            logger,
            event_sink=event_sink,
        ) or []
        extraction_result = extract_cad_artifacts(
            scan,
            scan.manifest.source_files,
            config,
            logger,
        )
        texts, lines, blocks, polylines, pages, extraction_warnings = extraction_result
        primitive_segments = getattr(extraction_result, "primitive_segments", [])
        extraction_censuses = getattr(extraction_result, "extraction_censuses", [])
        canonical_scenes = getattr(extraction_result, "canonical_scenes", [])
        symbol_port_definition_proposals = getattr(
            extraction_result, "symbol_port_definition_proposals", []
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

        # Page Classification Layer（任务书第 4 层）：
        # 基于 extract 后的真实几何特征判定页型，覆盖 scan 阶段的粗推断。
        classifications = classify_pages(pages, texts, lines, polylines, blocks, config)
        enrich_pages_from_classifications(pages, classifications)

        # Page Router Layer（任务书第 5 层）：
        # 把不同图种分发给不同识别器，而不是所有图都走同一条 PairBuilder。
        # 分流规则：
        #   - TableExtractor 页走表格专用链
        #   - 其余纳入审计的页（primary + supplemental）走 PairBuilder 链
        #     （supplemental 页即使 route_target 是 LayoutOnlyExtractor，
        #      用户显式要求纳入审计时仍走 pairing 链，以保留配对证据）
        table_sheet_ids = {
            page.sheet_id for page in pages
            if route_supports_table(page.route_target) and _is_downstream_audit_page(page)
        }
        pairing_sheet_ids = {
            page.sheet_id for page in pages
            if _is_downstream_audit_page(page) and page.sheet_id not in table_sheet_ids
        }
        audit_sheet_ids = pairing_sheet_ids | table_sheet_ids

        audit_pages = [page for page in pages if page.sheet_id in audit_sheet_ids]
        audit_texts = [text for text in texts if text.sheet_id in audit_sheet_ids]
        audit_lines = [line for line in lines if line.sheet_id in audit_sheet_ids]

        route_sheet_ids = {
            "WireDiagramExtractor": {
                page.sheet_id
                for page in audit_pages
                if page.sheet_id in pairing_sheet_ids and page.route_target == "WireDiagramExtractor"
            },
            "ComponentDiagramExtractor": {
                page.sheet_id
                for page in audit_pages
                if page.sheet_id in pairing_sheet_ids and page.route_target == "ComponentDiagramExtractor"
            },
            "TerminalDiagramExtractor": {
                page.sheet_id
                for page in audit_pages
                if page.sheet_id in pairing_sheet_ids and page.route_target == "TerminalDiagramExtractor"
            },
            "LayoutOnlyExtractor": {
                page.sheet_id
                for page in audit_pages
                if page.sheet_id in pairing_sheet_ids and page.route_target == "LayoutOnlyExtractor"
            },
        }
        extractor_runs: list[dict[str, object]] = []
        line_groups = []
        terminal_candidates = []
        pair_candidates = []
        pairs = []
        supplemental_table_mappings = []
        route_extractors = (
            ("WireDiagramExtractor", extract_wire_pairs),
            ("ComponentDiagramExtractor", extract_component_pairs),
            ("TerminalDiagramExtractor", extract_terminal_pairs),
            ("LayoutOnlyExtractor", extract_layout_audit_pairs),
        )
        for route_target, extractor in route_extractors:
            sheet_ids = route_sheet_ids[route_target]
            if not sheet_ids:
                continue
            route_pages = [page for page in audit_pages if page.sheet_id in sheet_ids]
            route_lines = [line for line in audit_lines if line.sheet_id in sheet_ids]
            route_texts = [text for text in audit_texts if text.sheet_id in sheet_ids]
            route_classifications = {
                sheet_id: classifications[sheet_id]
                for sheet_id in sheet_ids
                if sheet_id in classifications
            }
            extractor_kwargs = {"classifications": route_classifications}
            if route_target in {"WireDiagramExtractor", "ComponentDiagramExtractor"}:
                extractor_kwargs["blocks"] = [
                    block for block in blocks if block.sheet_id in sheet_ids
                ]
            extraction_result = extractor(
                route_pages,
                route_texts,
                route_lines,
                config,
                **extractor_kwargs,
            )
            extractor_runs.append(extraction_result.execution_record())
            line_groups.extend(extraction_result.line_groups)
            terminal_candidates.extend(extraction_result.terminal_candidates)
            pair_candidates.extend(extraction_result.pair_candidates)
            pairs.extend(extraction_result.pairs)
            supplemental_table_mappings.extend(extraction_result.table_mappings)

        # TableExtractor 链（任务书第 4 章 113-121 行）：
        # 表格型图走专用抽取器，生成高置信 table_mapping Pair
        table_pages = [page for page in audit_pages if page.sheet_id in table_sheet_ids]
        table_texts = [text for text in audit_texts if text.sheet_id in table_sheet_ids]
        table_lines = [line for line in audit_lines if line.sheet_id in table_sheet_ids]
        table_polylines = [poly for poly in polylines if poly.sheet_id in table_sheet_ids]
        table_pairs, routed_table_mappings = extract_table_pairs(
            table_texts,
            table_lines,
            table_polylines,
            table_pages,
            config,
        )
        table_mappings = [*supplemental_table_mappings, *routed_table_mappings]
        if table_pages:
            extractor_runs.append(
                {
                    "executed_extractor": "TableExtractor",
                    "route_target": "TableExtractor",
                    "sheet_ids": [page.sheet_id for page in table_pages],
                    "page_count": len(table_pages),
                    "line_group_count": 0,
                    "terminal_candidate_count": 0,
                    "pair_candidate_count": 0,
                    "pair_count": len(table_pairs),
                    "table_mapping_count": sum(len(item.get("mappings", [])) for item in routed_table_mappings),
                }
            )
        pairs.extend(table_pairs)

        # Some accessory/backplate pages are primarily routed as Table or Wire
        # even though they contain repeated component instances.  Recover only
        # geometry-owned components outside the normal Component route.
        accessory_pages = [
            page for page in audit_pages
            if page.route_target != "ComponentDiagramExtractor"
        ]
        accessory_sheet_ids = {page.sheet_id for page in accessory_pages}
        accessory_pairs, accessory_mappings = extract_accessory_backplate_two_port_pairs(
            accessory_pages,
            [text for text in audit_texts if text.sheet_id in accessory_sheet_ids],
            [line for line in audit_lines if line.sheet_id in accessory_sheet_ids],
            [block for block in blocks if block.sheet_id in accessory_sheet_ids],
        )
        if accessory_mappings:
            pairs.extend(accessory_pairs)
            table_mappings.extend(accessory_mappings)
            extractor_runs.append(
                {
                    "executed_extractor": "AccessoryBackplateExtractor",
                    "route_target": "supplemental",
                    "sheet_ids": [item["sheet_id"] for item in accessory_mappings],
                    "page_count": len(accessory_mappings),
                    "line_group_count": 0,
                    "terminal_candidate_count": 0,
                    "pair_candidate_count": 0,
                    "pair_count": len(accessory_pairs),
                    "table_mapping_count": sum(len(item.get("mappings", [])) for item in accessory_mappings),
                }
            )

        if event_sink is not None:
            event_sink.emit(
                "progress",
                stage="pair",
                project_root=str(project_root),
                line_group_count=len(line_groups),
                terminal_candidate_count=len(terminal_candidates),
                pair_candidate_count=len(pair_candidates),
                pair_count=len(pairs),
                table_pair_count=len(table_pairs),
            )
        extraction_gate = evaluate_extraction_completeness(
            pages,
            scan.manifest.source_files,
            texts,
            lines,
            blocks,
            polylines,
            extraction_warnings,
            extractor_runs,
            classifications=classifications,
            extraction_censuses=extraction_censuses,
        )
        extraction_gate_payload = extraction_gate.to_dict()
        if event_sink is not None and not extraction_gate_payload["clean_conclusion_allowed"]:
            event_sink.emit(
                "incomplete_extraction",
                project_root=str(project_root),
                analysis_status=extraction_gate_payload["analysis_status"],
                incomplete_page_count=extraction_gate_payload["incomplete_page_count"],
                failure_code_counts=extraction_gate_payload["failure_code_counts"],
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
            extractor_runs=extractor_runs,
            reader_runs=reader_runs,
            primitive_segments=primitive_segments,
            extraction_censuses=extraction_censuses,
            canonical_scenes=canonical_scenes,
            symbol_port_definition_proposals=symbol_port_definition_proposals,
        )
        # 把 PageClassification 和 table_mappings 透传给 artifacts 写入层
        artifacts_page_classifications = classifications
        artifacts_table_mappings = table_mappings
        project_dir = write_project_artifacts(
            artifacts,
            output_path,
            config=config,
            page_classifications=artifacts_page_classifications,
            table_mappings=artifacts_table_mappings,
            extraction_gate=extraction_gate,
        )
        written.append(project_dir)
        if event_sink is not None:
            event_sink.emit(
                "project_finished",
                project_root=str(project_root),
                project_dir=str(project_dir),
                analysis_status=extraction_gate_payload["analysis_status"],
                clean_conclusion_allowed=extraction_gate_payload["clean_conclusion_allowed"],
                incomplete_page_count=extraction_gate_payload["incomplete_page_count"],
                failure_code_counts=extraction_gate_payload["failure_code_counts"],
            )
        summary.append(
            {
                "project_name": scan.manifest.project_name,
                "project_id": scan.manifest.project_id,
                "project_root": scan.project_root,
                "artifact_dir": str(project_dir.resolve()),
                "analysis_status": extraction_gate_payload["analysis_status"],
                "clean_conclusion_allowed": extraction_gate_payload["clean_conclusion_allowed"],
                "incomplete_page_count": extraction_gate_payload["incomplete_page_count"],
                "failure_code_counts": extraction_gate_payload["failure_code_counts"],
            }
        )
    (output_path / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return written
