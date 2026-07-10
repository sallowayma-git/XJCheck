"""Pseudocode for the topology-first XJCheck V2 pipeline.

This file is intentionally close to Python, but it is not a drop-in patch. The
interfaces define stage boundaries and non-negotiable gates for implementation.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineOptions:
    reader_backend: str = "auto"
    legacy_mode: str = "shadow"
    learning_mode: str = "off"
    fail_on_incomplete_reader: bool = True


class IncompleteProjectError(RuntimeError):
    pass


def analyze_project(input_root: Path, output_root: Path, config: dict) -> None:
    run = RunContext.create(input_root, output_root, config)

    # Stage 0: project truth and stable ordering.
    project_profile = ProjectProfiler().build(
        dwg_files=discover_dwg_files(input_root),
        prj_file=find_optional_prj(input_root),
        terminal_xml=find_optional_terminal_xml(input_root),
    )
    FindingsWriter(run).write_project_profile(project_profile)

    # Stage 1: reader probe and extraction completeness gate.
    reader = CadReaderRegistry(config).select(project_profile)
    documents = []
    for sheet in project_profile.sheets:
        if sheet.audit_policy == "skip":
            continue
        document = reader.read(sheet.source_path)
        documents.append(document)
        FindingsWriter(run).write_reader_result(document.reader_result)

    completeness = ExtractionCompletenessEvaluator().evaluate(project_profile, documents)
    FindingsWriter(run).write_extraction_completeness(completeness)
    if not completeness.can_issue_clean_conclusion:
        # A failed conversion or zero-entity audit page is not a clean drawing.
        raise IncompleteProjectError(completeness.explanation)

    # Stage 2: lossless primitive model. No electrical inference here.
    primitives = PrimitiveNormalizer(config).normalize_all(documents)
    FindingsWriter(run).write_primitives(primitives)

    # Stage 3: geometry candidates and four-state decisions.
    geometry_candidates = GeometryCandidateBuilder(config).build(primitives)
    geometry_decisions = JunctionDecisionEngine(config).decide(geometry_candidates)
    assert_no_possible_edge_materialized(geometry_decisions)
    geometry_graph = GeometryGraphBuilder().build(primitives, geometry_decisions)
    FindingsWriter(run).write_geometry(geometry_candidates, geometry_decisions, geometry_graph)

    # Stage 4: symbols are resolved before electrical networks are materialized.
    registry = SymbolRegistry.load(config["symbols"]["library_paths"])
    symbol_instances = SymbolInstanceResolver(registry).resolve(primitives.blocks)
    port_candidates = PortCandidateBuilder(config).build(symbol_instances, geometry_graph)
    port_decisions = PortBinder(config).bind(port_candidates)
    FindingsWriter(run).write_symbols(symbol_instances, port_candidates, port_decisions)

    # Stage 5: use only ASSERTED topology and selected symbol-port relations.
    networks = ElectricalNetworkBuilder(config).build(
        geometry_graph=geometry_graph,
        symbol_instances=symbol_instances,
        port_decisions=port_decisions,
    )
    network_diagnostics = NetworkValidator(config).validate(networks)
    FindingsWriter(run).write_networks(networks, network_diagnostics)

    # Stage 6: neighborhood is allowed only to create semantic candidates.
    tokens = TokenParser(config).parse(primitives.texts, project_profile)
    attachment_candidates = SemanticAttachmentCandidateBuilder(config).build(
        tokens=tokens,
        networks=networks,
        symbols=symbol_instances,
        project_profile=project_profile,
    )
    FindingsWriter(run).write_semantic_candidates(tokens, attachment_candidates)

    # Stage 7: joint resolution prevents independent local winners from colliding.
    resolution = ConstraintResolver(config).solve(
        topology_decisions=geometry_decisions,
        port_candidates=port_candidates,
        attachment_candidates=attachment_candidates,
        project_profile=project_profile,
    )
    FindingsWriter(run).write_constraint_resolution(resolution)

    # Re-materialize semantic networks only from the selected global solution.
    semantic_model = SemanticModelBuilder().build(
        networks=networks,
        symbols=symbol_instances,
        tokens=tokens,
        resolution=resolution,
    )

    # Stage 8: project-level endpoint identity and cross-page candidates.
    endpoint_candidates = CrossPageEndpointBuilder(config).build(semantic_model, project_profile)
    cross_page_resolution = CrossPageMatcher(config).resolve(endpoint_candidates, resolution)
    project_graph = ProjectGraphBuilder().build(semantic_model, cross_page_resolution)
    FindingsWriter(run).write_project_graph(endpoint_candidates, cross_page_resolution, project_graph)

    # Stage 9: rules consume Findings V2, never DWG/DXF files directly.
    issues = RuleEngine(config).run(project_graph)
    issues = IssueGate(config).apply(
        issues=issues,
        completeness=completeness,
        unresolved_topology=geometry_decisions.unresolved,
        unresolved_symbols=symbol_instances.unresolved,
        alternative_solution_gap=resolution.objective_gap,
    )
    issues = WitnessPathBuilder().attach(issues, project_graph, geometry_graph)
    FindingsWriter(run).write_issues(issues)

    # Stage 10: legacy is an independent shadow for comparison only.
    if config["legacy"]["neighborhood_engine"]["mode"] == "shadow":
        legacy = LegacyNeighborhoodPipeline().run_from_primitives(primitives, project_profile)
        comparison = EngineComparator().compare(legacy, issues, project_graph)
        FindingsWriter(run).write_legacy_comparison(comparison)

    ReportBuilder(config).build(run)
