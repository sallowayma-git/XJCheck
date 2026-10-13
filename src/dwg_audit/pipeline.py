from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path

from dwg_audit.audit.line_groups import wire_break_evidence_by_sheet
from dwg_audit.audit.page_extractors import extract_component_pairs
from dwg_audit.audit.page_extractors import extract_layout_audit_pairs
from dwg_audit.audit.page_extractors import extract_terminal_pairs
from dwg_audit.audit.page_extractors import extract_wire_pairs
from dwg_audit.audit.extraction_gate import evaluate_extraction_completeness
from dwg_audit.audit.table_extractor import extract_table_pairs
from dwg_audit.audit.backplate_components import extract_accessory_backplate_two_port_pairs
from dwg_audit.audit.page_extractors import mark_component_mapping_endpoint_covered_ordinary_pairs
from dwg_audit.audit.page_extractors import mark_ignored_equipment_panel_ordinary_pairs
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
from dwg_audit.utils.config import resolve_runtime_profile


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


def _block_line_rows(primitive_segments) -> list:
    """WIRE-BREAK round 25: visible LINE primitives of block instances (an element's own leads), as
    (sheet_id, x1, y1, x2, y2) rows for the wire walk. Model lines come from the line list instead."""
    if primitive_segments is None:
        return []
    rows = []
    for item in primitive_segments:
        if getattr(item, "primitive_kind", None) != "LINE" or not getattr(item, "definition_name", None):
            continue
        if not getattr(item, "visible", True):
            continue
        try:
            geometry = json.loads(getattr(item, "world_geometry_json", None) or "{}")
            (x1, y1, _), (x2, y2, _) = geometry["start"], geometry["end"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        rows.append((item.sheet_id, float(x1), float(y1), float(x2), float(y2)))
    return rows


def _write_sw_wire_routes(project_dir, superworks, logger) -> None:
    """Diagnostic output: sw_wire_routes.parquet and its stats. The rows were resolved during the
    SuperWORKS extraction (superworks_extractor), from DXF documents already open in cad_extract."""
    rows = getattr(superworks, "wire_route_rows", None) or []
    if not rows:
        return
    from dwg_audit.extract.superworks_loggen import write_wire_route_rows
    try:
        findings = project_dir / "findings"
        findings.mkdir(parents=True, exist_ok=True)
        write_wire_route_rows(findings / "sw_wire_routes.parquet", rows)
        (findings / "sw_wire_routes_stats.json").write_text(
            json.dumps(superworks.wire_route_stats, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    except Exception as exc:  # a diagnostic must never fail the project run
        logger.warning("sw_wire_routes skipped: %s", exc)


def analyze_input_root(
    input_path: Path,
    output_path: Path,
    config: dict,
    logger,
    *,
    event_sink = None,
    cached_page_facts=None,
    current_page_facts=None,
) -> list[Path]:
    project_roots = discover_project_roots(input_path)
    written: list[Path] = []
    summary: list[dict[str, object]] = []
    for project_root in project_roots:
        project_started = time.perf_counter()
        stage_seconds = {}
        logger.info("Analyzing project root: %s", project_root)
        if event_sink is not None:
            event_sink.emit("project_started", project_root=str(project_root))
        scan = scan_project(project_root, config=config)
        stage_seconds["scan"] = time.perf_counter() - project_started
        if event_sink is not None:
            event_sink.emit(
                "progress",
                stage="scan",
                project_root=str(project_root),
                file_count=scan.manifest.file_count,
                sheet_count=scan.manifest.sheet_count,
            )
        stage_started = time.perf_counter()
        include_canonical_scenes = resolve_runtime_profile(config) != "production"
        page_fact_kwargs = dict(include_canonical_scenes=include_canonical_scenes)
        conversion_sources = scan.manifest.source_files
        if current_page_facts is not None:
            from dwg_audit.extract.cad_extract import page_fact_fingerprint, reusable_page_facts
            fingerprint = page_fact_fingerprint(project_root, config)
            cache = (cached_page_facts or {}).get(str(project_root.resolve()), {})
            page_fact_kwargs.update(cached_pages=cache, capture_page_facts=True, fingerprint=fingerprint)
            # Sequential IDs are part of the legacy contract. Skip conversion of the
            # unchanged prefix; a changed page conservatively converts the suffix.
            conversion_sources = []
            prefix_unchanged = True
            counters = [0] * 5
            sheet_map = {p.file_id: p for p in scan.pages}
            for source in scan.manifest.source_files:
                payload = cache.get(str(Path(source.path).resolve()))
                if prefix_unchanged and reusable_page_facts(source, sheet_map[source.file_id], payload, fingerprint, counters,
                        include_canonical_scenes=include_canonical_scenes):
                    source.conversion_status = "cached"
                    counters = payload["end_counters"]
                else:
                    prefix_unchanged = False
                    conversion_sources.append(source)
        reader_runs = convert_source_files(
            conversion_sources,
            output_path,
            config,
            logger,
            event_sink=event_sink,
        ) or []
        stage_seconds["convert"] = time.perf_counter() - stage_started
        stage_started = time.perf_counter()
        extraction_result = extract_cad_artifacts(
            scan,
            scan.manifest.source_files,
            config,
            logger,
            **page_fact_kwargs,
        )
        if current_page_facts is not None:
            current_page_facts[str(project_root.resolve())] = getattr(extraction_result, "page_facts", {})
        stage_seconds["cad_extract"] = time.perf_counter() - stage_started
        cad_extraction_result = extraction_result
        stage_seconds["reused_page_count"] = getattr(extraction_result, "reused_page_count", 0)
        stage_started = time.perf_counter()
        texts, lines, blocks, polylines, pages, extraction_warnings = extraction_result
        primitive_segments = getattr(extraction_result, "primitive_segments", [])
        extraction_censuses = getattr(extraction_result, "extraction_censuses", [])
        canonical_scenes = getattr(extraction_result, "canonical_scenes", [])
        symbol_port_definition_proposals = getattr(
            extraction_result, "symbol_port_definition_proposals", []
        )
        terminal_port_bindings = getattr(extraction_result, "terminal_port_bindings", [])
        superworks = getattr(extraction_result, "superworks", None)
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
        stage_seconds["classify"] = time.perf_counter() - stage_started
        stage_started = time.perf_counter()

        # Page Router Layer（任务书第 5 层）：
        # 把不同图种分发给不同识别器，而不是所有图都走同一条 PairBuilder。
        # 分流规则：
        #   - TableExtractor 页走表格专用链
        #   - 其余纳入审计的页（primary + supplemental）走 PairBuilder 链
        #     （supplemental 页即使 route_target 是 LayoutOnlyExtractor，
        #      用户显式要求纳入审计时仍走 pairing 链，以保留配对证据）
        relation_cache = None
        source_signature = [(str(Path(s.path).resolve()), s.file_id, s.sha256) for s in scan.manifest.source_files]
        if current_page_facts is not None and getattr(extraction_result, "reused_page_count", 0) == len(scan.manifest.source_files):
            saved = cache.get("_relations") or {}
            if saved.get("fingerprint") == fingerprint and saved.get("source_signature") == [list(row) for row in source_signature]:
                from dwg_audit.extract.cad_extract import decode_page_facts
                try:
                    relation_cache = decode_page_facts(saved["facts"])
                    required = {"pairs", "line_groups", "terminal_candidates", "pair_candidates", "table_mappings",
                        "extractor_runs", "superworks_supersession", "sw_backplate_contradictions", "superworks"}
                    if not isinstance(relation_cache, dict) or not required <= relation_cache.keys():
                        relation_cache = None
                except (KeyError, ValueError, TypeError):
                    relation_cache = None
        if relation_cache is not None:
            from dwg_audit.audit.recognition_coordinator import SharedRecognitionContext
            shared_context = SharedRecognitionContext()
            shared_context.counts["recognition_reused"] = len(relation_cache["pairs"])
            pairs = relation_cache["pairs"]
            line_groups = relation_cache["line_groups"]
            terminal_candidates = relation_cache["terminal_candidates"]
            pair_candidates = relation_cache["pair_candidates"]
            table_mappings = relation_cache["table_mappings"]
            extractor_runs = relation_cache["extractor_runs"]
            superworks_supersession = relation_cache["superworks_supersession"]
            sw_backplate_contradictions = relation_cache["sw_backplate_contradictions"]
            extracted_seconds = getattr(superworks, "extraction_seconds", 0.0)
            superworks = relation_cache["superworks"]
            if superworks is not None:
                superworks.extraction_seconds = extracted_seconds
                superworks.recognition_seconds = 0.0
            table_pairs = [p for p in pairs if p.pair_kind == "table_mapping"]
            for stage in ("v1", "superworks_native", "superworks_reconcile", "superworks", "merge"):
                stage_seconds[stage] = 0.0
        else:
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
            # SuperWORKS ports and connect dots tell a real wire break at two terminals from a merged wire.
            # WIRE-BREAK: TERMPOINT marks of registered ports and unregistered SYMB2 blocks mark symbol bodies.
            wire_break_evidence = (
                wire_break_evidence_by_sheet(
                    getattr(superworks, "ports", None),
                    getattr(superworks, "connect_dots", None),
                    getattr(superworks, "unregistered_symb2", None),
                )
                if superworks is not None else None
            )
            supplemental_table_mappings = []
            from dwg_audit.audit.recognition_coordinator import SharedRecognitionContext
            shared_context = SharedRecognitionContext.create(audit_texts, wire_break_evidence)
            route_extractors = (
                ("WireDiagramExtractor", extract_wire_pairs),
                ("ComponentDiagramExtractor", extract_component_pairs),
                ("TerminalDiagramExtractor", extract_terminal_pairs),
                ("LayoutOnlyExtractor", extract_layout_audit_pairs),
            )
            stems = {"WireDiagramExtractor": "W", "ComponentDiagramExtractor": "C",
                     "TerminalDiagramExtractor": "T", "LayoutOnlyExtractor": "L"}
            for route_target, _ in route_extractors:
                sheet_ids = route_sheet_ids[route_target]
                if not sheet_ids:
                    continue
                line_groups.extend(shared_context.groups_for_route(id_stem=stems[route_target],
                    pages=[p for p in audit_pages if p.sheet_id in sheet_ids],
                    texts=[t for t in audit_texts if t.sheet_id in sheet_ids],
                    lines=[line for line in audit_lines if line.sheet_id in sheet_ids], config=config,
                    classifications={sid: classifications[sid] for sid in sheet_ids if sid in classifications},
                    wire_break_evidence=wire_break_evidence))
            if superworks is not None and wire_break_evidence:
                from dwg_audit.audit.line_groups import symbol_cut_group_ids
                superworks.topology_cut_group_ids = symbol_cut_group_ids(line_groups, wire_break_evidence)
            from dwg_audit.audit.superworks_extractor import extract_superworks_pairs
            block_rows = _block_line_rows(primitive_segments)
            native_started = time.perf_counter()
            native_pairs, native_mappings, native_ledger = extract_superworks_pairs(
                superworks, pages=audit_pages, texts=audit_texts, lines=audit_lines,
                line_groups=line_groups, pairs=[], table_mappings=[], block_rows=block_rows,
                native_only=True, shared_context=shared_context)
            # A pin inferred from the strip being audited is not independent authority.
            # Defer these component candidates until the local V1 geometry is available.
            deferred_ids = {p.pair_id for p in native_pairs
                if p.evidence.get("component_submode") == "superworks_connect_line_port"
                and not p.evidence.get("independent_pin_verification")}
            if deferred_ids:
                native_pairs = [p for p in native_pairs if p.pair_id not in deferred_ids]
                native_ledger = [entry for entry in native_ledger if not any(
                    p.get("pair_id") in deferred_ids for p in entry.get("new_pairs", []))]
                shared_context.counts["native_component_candidates_deferred"] = len(deferred_ids)
            stage_seconds["superworks_native"] = time.perf_counter() - native_started
            shared_context.accept_native(native_pairs, getattr(superworks, "resolution_observations", []))
            stage_started = time.perf_counter()
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
                extractor_kwargs = {"classifications": route_classifications, "wire_break_evidence": wire_break_evidence}
                extractor_kwargs["shared_context"] = shared_context
                extractor_kwargs["target_line_group_ids"] = {
                    g.line_group_id for g in line_groups if g.sheet_id in sheet_ids
                    and (g.sheet_id, g.line_group_id) not in shared_context.closed_groups
                }
                if route_target in {"WireDiagramExtractor", "ComponentDiagramExtractor"}:
                    extractor_kwargs["blocks"] = [
                        block for block in blocks if block.sheet_id in sheet_ids
                    ]
                if route_target == "WireDiagramExtractor":
                    extractor_kwargs["terminal_port_bindings"] = [
                        binding
                        for binding in terminal_port_bindings
                        if binding.sheet_id in sheet_ids
                    ]
                extraction_result = extractor(
                    route_pages,
                    route_texts,
                    route_lines,
                    config,
                    **extractor_kwargs,
                )
                extractor_runs.append(extraction_result.execution_record())
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
                pair_id_factory=shared_context.pair_ids("P"),
            )
            table_mappings = [*native_mappings, *supplemental_table_mappings, *routed_table_mappings]
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
            pairs.extend(native_pairs)
            stage_seconds["v1"] = time.perf_counter() - stage_started

            if superworks is not None and wire_break_evidence:
                # WIRE-BREAK: unknown-shape rows and counts collected while the line groups were built.
                superworks.topology_unknown = [row for ev in wire_break_evidence.values() for row in ev.log]
                topology_counts: dict[str, int] = {}
                for ev in wire_break_evidence.values():
                    for key, count in ev.stats.items():
                        topology_counts[key] = topology_counts.get(key, 0) + int(count)
                superworks.topology_stats = topology_counts
                # WIRE-BREAK: line groups that end on a symbol-body cut (their legacy half pairs are provisional).
                from dwg_audit.audit.line_groups import symbol_cut_group_ids
                superworks.topology_cut_group_ids = symbol_cut_group_ids(line_groups, wire_break_evidence)

            from dwg_audit.audit.superworks_extractor import extract_superworks_pairs
            block_rows = _block_line_rows(primitive_segments)
            stage_started = time.perf_counter()
            pairs, table_mappings, superworks_supersession = extract_superworks_pairs(
                superworks, pages=audit_pages, texts=audit_texts, lines=audit_lines,
                line_groups=line_groups, pairs=pairs, table_mappings=table_mappings,
                wire_route_sheet_numbers={page.file_id: page.sheet_no or "" for page in pages},
                block_rows=block_rows,
                shared_context=shared_context,
            )
            stage_seconds["superworks_reconcile"] = time.perf_counter() - stage_started
            stage_seconds["superworks"] = stage_seconds["superworks_native"] + stage_seconds["superworks_reconcile"]
            if superworks is not None:
                superworks.recognition_seconds += stage_seconds["superworks_native"]
            superworks_supersession = [*native_ledger, *superworks_supersession]
            stage_started = time.perf_counter()

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

            # The accessory pass runs after extract_superworks_pairs, so its legacy rows
            # were never checked against SW connect-line rows; retire exact duplicates here.
            from dwg_audit.audit.superworks_extractor import supersede_equivalent_component_duplicates
            pairs, superworks_supersession = supersede_equivalent_component_duplicates(
                pairs, superworks_supersession,
            )
            mark_ignored_equipment_panel_ordinary_pairs(
                pairs,
                line_groups,
                audit_texts,
                audit_lines,
                symbol_port_definition_proposals,
            )

            # Both table-edge passes run after the panel mark: a panel-owned pair (ordinary_pair_eligible=False,
            # ignored_panel_family_id) is never retired here and leaves no ledger entry.
            from dwg_audit.audit.superworks_extractor import supersede_border_row_duplicates
            pairs, superworks_supersession = supersede_border_row_duplicates(
                pairs, superworks_supersession, audit_lines, line_groups, audit_texts,
            )
            from dwg_audit.audit.superworks_extractor import supersede_cell_edge_pairs
            pairs, superworks_supersession = supersede_cell_edge_pairs(
                pairs, superworks_supersession, audit_lines, line_groups, audit_texts,
            )
            # Every SW and legacy pair now exists: retire legacy pass/review pairs a same-sheet SW pass repeats.
            from dwg_audit.audit.superworks_extractor import supersede_legacy_duplicates_of_sw
            pairs, superworks_supersession = supersede_legacy_duplicates_of_sw(pairs, superworks_supersession)
            # P2-BACKPLATE: evidence for backplate virtual-table pairs that a same-project SW pass pair corroborates;
            # disagreements become audit-only candidate rows (no status change).
            from dwg_audit.audit.superworks_extractor import corroborate_backplate_virtual_pairs
            pairs, sw_backplate_contradictions = corroborate_backplate_virtual_pairs(pairs)
            from dwg_audit.audit.superworks_extractor import supersede_backplate_row_misreads
            pairs, superworks_supersession = supersede_backplate_row_misreads(pairs, superworks_supersession, sw_backplate_contradictions)

            authoritative_component_pairs = [
                pair
                for pair in pairs
                if pair.pair_kind == "component_mapping"
                and pair.status == "pass"
                and float(pair.confidence or 0.0) >= 0.95
                and (pair.evidence or {}).get("source") == "component_mapping"
                and (pair.evidence or {}).get("ordinary_pair_eligible") is False
            ]
            mark_component_mapping_endpoint_covered_ordinary_pairs(
                pairs,
                authoritative_component_pairs,
            )
            from dwg_audit.audit.recognition_coordinator import finalize_evidence
            pairs = finalize_evidence(pairs, shared_context)
            stage_seconds["merge"] = time.perf_counter() - stage_started

        if current_page_facts is not None:
            from dwg_audit.extract.cad_extract import encode_page_facts
            # Current facts and current relationships replace each other in the same
            # SQLite transaction. Any input change recomputes project dependencies.
            current_page_facts[str(project_root.resolve())]["_relations"] = {
                "fingerprint": fingerprint, "source_signature": [list(row) for row in source_signature],
                "facts": encode_page_facts(dict(pairs=pairs, line_groups=line_groups,
                    terminal_candidates=terminal_candidates, pair_candidates=pair_candidates,
                    table_mappings=table_mappings, extractor_runs=extractor_runs,
                    superworks_supersession=superworks_supersession,
                    sw_backplate_contradictions=sw_backplate_contradictions, superworks=superworks))}

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
            superworks=superworks,
            superworks_supersession=superworks_supersession,
            sw_backplate_contradictions=sw_backplate_contradictions,
        )
        # 把 PageClassification 和 table_mappings 透传给 artifacts 写入层
        artifacts_page_classifications = classifications
        artifacts_table_mappings = table_mappings
        stage_started = time.perf_counter()
        project_dir = write_project_artifacts(
            artifacts,
            output_path,
            config=config,
            page_classifications=artifacts_page_classifications,
            table_mappings=artifacts_table_mappings,
            extraction_gate=extraction_gate,
        )
        _write_sw_wire_routes(project_dir, superworks, logger)
        stage_seconds["write"] = time.perf_counter() - stage_started
        stage_seconds["analysis_total"] = time.perf_counter() - project_started
        performance = {
            "schema_version": 1,
            "stage_seconds": stage_seconds,
            "inputs": [{"file_id": s.file_id, "sha256": s.sha256} for s in scan.manifest.source_files],
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "counts": {"pages": len(pages), "lines": len(lines), "pairs": len(pairs),
                       "line_groups": len(line_groups), "terminal_candidates": len(terminal_candidates),
                       "reused_pages": getattr(cad_extraction_result, "reused_page_count", 0)},
            "cad_detail_seconds": getattr(cad_extraction_result, "stage_seconds", {}),
            "sw_timing": {"extraction_seconds": getattr(superworks, "extraction_seconds", 0.0),
                          "recognition_seconds": getattr(superworks, "recognition_seconds", 0.0)},
            "shared_seconds": dict(shared_context.seconds),
            "shared_counts": dict(shared_context.counts),
        }
        (project_dir / "performance.json").write_text(json.dumps(performance, ensure_ascii=False, indent=2), encoding="utf-8")
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
