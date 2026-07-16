from __future__ import annotations

import re

from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace
from collections import defaultdict

from dwg_audit.audit import component_diagrams
from dwg_audit.audit.candidates import build_terminal_candidates
from dwg_audit.audit.component_diagrams import extract_strip_two_port_component_pairs
from dwg_audit.audit.line_groups import build_line_groups
from dwg_audit.audit.pairs import build_pairs
from dwg_audit.audit.table_extractor import extract_terminal_header_table_pairs
from dwg_audit.audit.wire_components import extract_component_prefixed_signal_pairs
from dwg_audit.domain.models import BlockRecord
from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import LineGroup
from dwg_audit.domain.models import PageClassification
from dwg_audit.domain.models import Pair
from dwg_audit.domain.models import PairCandidate
from dwg_audit.domain.models import SheetRecord
from dwg_audit.domain.models import TerminalCandidate
from dwg_audit.domain.models import TextItem
from dwg_audit.utils.ids import IdFactory


@dataclass(slots=True)
class PairingExtractionResult:
    executed_extractor: str
    route_target: str
    pages: list[SheetRecord]
    line_groups: list[LineGroup]
    terminal_candidates: list[TerminalCandidate]
    pair_candidates: list[PairCandidate]
    pairs: list[Pair]
    table_mappings: list[dict[str, object]] = field(default_factory=list)

    def execution_record(self) -> dict[str, object]:
        return {
            "executed_extractor": self.executed_extractor,
            "route_target": self.route_target,
            "sheet_ids": [page.sheet_id for page in self.pages],
            "page_count": len(self.pages),
            "line_group_count": len(self.line_groups),
            "terminal_candidate_count": len(self.terminal_candidates),
            "pair_candidate_count": len(self.pair_candidates),
            "pair_count": len(self.pairs),
            "table_mapping_count": sum(len(item.get("mappings", [])) for item in self.table_mappings),
        }


def extract_wire_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity],
    config: dict,
    *,
    classifications: dict[str, PageClassification] | None = None,
) -> PairingExtractionResult:
    return _extract_pairs_for_route(
        executed_extractor="WireDiagramExtractor",
        route_target="WireDiagramExtractor",
        pages=pages,
        texts=texts,
        lines=lines,
        config=config,
        classifications=classifications,
    )


def extract_component_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity],
    config: dict,
    *,
    blocks: list[BlockRecord] | None = None,
    classifications: dict[str, PageClassification] | None = None,
) -> PairingExtractionResult:
    return _extract_pairs_for_route(
        executed_extractor="ComponentDiagramExtractor",
        route_target="ComponentDiagramExtractor",
        pages=pages,
        texts=texts,
        lines=lines,
        blocks=blocks,
        config=config,
        classifications=classifications,
    )


def extract_terminal_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity],
    config: dict,
    *,
    classifications: dict[str, PageClassification] | None = None,
) -> PairingExtractionResult:
    return _extract_pairs_for_route(
        executed_extractor="TerminalDiagramExtractor",
        route_target="TerminalDiagramExtractor",
        pages=pages,
        texts=texts,
        lines=lines,
        config=config,
        classifications=classifications,
    )


def extract_layout_audit_pairs(
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity],
    config: dict,
    *,
    classifications: dict[str, PageClassification] | None = None,
) -> PairingExtractionResult:
    return _extract_pairs_for_route(
        executed_extractor="LayoutOnlyAuditFallback",
        route_target="LayoutOnlyExtractor",
        pages=pages,
        texts=texts,
        lines=lines,
        config=config,
        classifications=classifications,
    )


def _extract_pairs_for_route(
    *,
    executed_extractor: str,
    route_target: str,
    pages: list[SheetRecord],
    texts: list[TextItem],
    lines: list[LineEntity],
    blocks: list[BlockRecord] | None = None,
    config: dict,
    classifications: dict[str, PageClassification] | None = None,
) -> PairingExtractionResult:
    id_stem = _extractor_id_stem(executed_extractor)
    route_sheet_ids = {page.sheet_id for page in pages}
    route_classifications = {
        sheet_id: classification
        for sheet_id, classification in (classifications or {}).items()
        if sheet_id in route_sheet_ids
    }
    line_groups = build_line_groups(
        lines,
        pages,
        config,
        texts,
        classifications=route_classifications,
        group_id_factory=IdFactory(f"G{id_stem}"),
        band_id_factory=IdFactory(f"RB{id_stem}"),
    )
    terminal_candidates = build_terminal_candidates(
        line_groups,
        texts,
        config,
        pages,
        candidate_id_factory=IdFactory(f"C{id_stem}"),
    )
    pair_candidates, pairs = build_pairs(
        line_groups,
        terminal_candidates,
        pages,
        config,
        pair_candidate_id_factory=IdFactory(f"PC{id_stem}"),
        pair_id_factory=IdFactory(f"P{id_stem}"),
    )
    if executed_extractor == "WireDiagramExtractor":
        _mark_inline_wire_split_continuation_pairs(pairs, line_groups, pages, config)
    if executed_extractor == "WireDiagramExtractor":
        _mark_schematic_ac_phase_covered_ordinary_pairs(pairs, pages)
    if executed_extractor == "WireDiagramExtractor":
        _mark_schematic_ground_covered_ordinary_pairs(pairs, pages)
    if executed_extractor == "WireDiagramExtractor":
        wire_component_pairs = extract_component_prefixed_signal_pairs(
            pages,
            texts,
            lines,
            pair_id_factory=IdFactory(f"P{id_stem}M"),
            config=config,
        )
        _mark_wire_component_covered_ordinary_pairs(pairs, wire_component_pairs)
        pairs.extend(wire_component_pairs)
    if executed_extractor == "ComponentDiagramExtractor":
        component_pairs, consumed_group_ids = extract_strip_two_port_component_pairs(
            pages,
            texts,
            line_groups,
            pair_id_factory=IdFactory(f"P{id_stem}M"),
        )
        endpoint_bridge_extractor = getattr(component_diagrams, "extract_strip_two_port_endpoint_bridge_pairs", None)
        if callable(endpoint_bridge_extractor):
            endpoint_bridge_pairs, endpoint_bridge_consumed_group_ids = endpoint_bridge_extractor(
                pages,
                texts,
                line_groups,
                pair_id_factory=IdFactory(f"P{id_stem}B"),
            )
            component_pairs.extend(endpoint_bridge_pairs)
            consumed_group_ids.update(endpoint_bridge_consumed_group_ids)
        kk_extractor = getattr(component_diagrams, "extract_kk_multi_port_component_pairs", None)
        if callable(kk_extractor):
            kk_pairs, kk_consumed_group_ids = kk_extractor(
                pages,
                texts,
                line_groups,
                blocks=blocks or [],
                pair_id_factory=IdFactory(f"P{id_stem}K"),
            )
            component_pairs.extend(kk_pairs)
            consumed_group_ids.update(kk_consumed_group_ids)
        small_port_extractor = getattr(component_diagrams, "extract_small_port_box_component_pairs", None)
        if callable(small_port_extractor):
            small_port_pairs, small_port_consumed_group_ids = small_port_extractor(
                pages,
                texts,
                line_groups,
                blocks=blocks or [],
                pair_id_factory=IdFactory(f"P{id_stem}S"),
            )
            component_pairs.extend(small_port_pairs)
            consumed_group_ids.update(small_port_consumed_group_ids)
        if component_pairs:
            _mark_consumed_component_ordinary_pairs(pairs, consumed_group_ids)
            pairs.extend(component_pairs)
    table_mappings = []
    if executed_extractor == "TerminalDiagramExtractor":
        table_pairs, table_mappings = extract_terminal_header_table_pairs(
            texts,
            pages,
            pair_id_factory=IdFactory(f"P{id_stem}M"),
        )
        retry_pages = _terminal_header_table_retry_pages(pages)
        if retry_pages:
            retry_pairs, retry_mappings = extract_terminal_header_table_pairs(
                texts,
                retry_pages,
                pair_id_factory=IdFactory(f"P{id_stem}MR"),
            )
            _extend_unique_pairs(table_pairs, retry_pairs)
            table_mappings = _merge_table_mappings(table_mappings, retry_mappings)
        _mark_terminal_prefixed_endpoint_ordinary_pairs(pairs, table_mappings)
        _promote_regular_terminal_row_array_pairs(pairs, line_groups, pages, config)
        pairs.extend(table_pairs)
    if executed_extractor == "WireDiagramExtractor":
        _shadow_grid_wire_ordinary_pairs(pairs, pages)
    return PairingExtractionResult(
        executed_extractor=executed_extractor,
        route_target=route_target,
        pages=pages,
        line_groups=line_groups,
        terminal_candidates=terminal_candidates,
        pair_candidates=pair_candidates,
        pairs=pairs,
        table_mappings=table_mappings,
    )


def _extractor_id_stem(executed_extractor: str) -> str:
    mapping = {
        "WireDiagramExtractor": "W",
        "ComponentDiagramExtractor": "C",
        "TerminalDiagramExtractor": "T",
        "LayoutOnlyAuditFallback": "L",
    }
    return mapping.get(executed_extractor, "X")


def _mark_consumed_component_ordinary_pairs(pairs: list[Pair], consumed_group_ids: set[str]) -> None:
    for pair in pairs:
        if pair.line_group_id not in consumed_group_ids:
            continue
        if pair.pair_kind != "ordinary_pair":
            continue
        pair.status = "discard"
        pair.confidence_bucket = "low"
        pair.rationale = "Covered by component_mapping from ComponentDiagramExtractor."
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["covered_by_component_mapping"] = True


def _shadow_grid_wire_ordinary_pairs(pairs: list[Pair], pages: list[SheetRecord]) -> None:
    sheet_map = {page.sheet_id: page for page in pages}
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        sheet = sheet_map.get(pair.sheet_id)
        if sheet is None or sheet.sheet_category != "二次原理图":
            continue
        if sheet.route_target != "WireDiagramExtractor":
            continue
        if not (sheet.grid_heavy or sheet.page_subtype == "grid_heavy_wire_diagram"):
            continue
        if pair.evidence.get("line_orientation") != "grid":
            continue
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = "wire_grid_primary"


def _mark_input_matrix_covered_ordinary_pairs(
    pairs: list[Pair],
    wire_component_pairs: list[Pair],
) -> None:
    _mark_wire_component_covered_ordinary_pairs(pairs, wire_component_pairs)


def _mark_wire_component_covered_ordinary_pairs(
    pairs: list[Pair],
    wire_component_pairs: list[Pair],
) -> None:
    covered_text_reasons = _wire_component_local_number_text_reasons(wire_component_pairs)
    if not covered_text_reasons:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.status == "discard":
            continue
        covered_reasons = _pair_text_coverage_reasons(pair, covered_text_reasons)
        if not covered_reasons:
            continue
        pair.status = "discard"
        pair.confidence_bucket = "low"
        pair.rationale = _wire_component_coverage_rationale(covered_reasons)
        pair.evidence["ordinary_pair_eligible"] = False
        for reason in covered_reasons:
            pair.evidence[f"covered_by_{reason}"] = True


def _ordinary_single_sided_text_ids(pairs: list[Pair]) -> set[str]:
    text_ids: set[str] = set()
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.status == "discard":
            continue
        if bool(pair.left_value) == bool(pair.right_value):
            continue
        for value in _pair_selected_text_ids(pair):
            text_ids.add(value)
    return text_ids


def _mark_inline_wire_split_continuation_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    pages: list[SheetRecord],
    config: dict,
) -> None:
    sheet_map = {page.sheet_id: page for page in pages}
    group_map = {group.line_group_id: group for group in line_groups}
    missing_left: list[Pair] = []
    missing_right_by_key: dict[tuple[str, str, str], list[Pair]] = {}
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair" or pair.status == "discard":
            continue
        sheet = sheet_map.get(pair.sheet_id)
        if sheet is None or sheet.sheet_category != "二次原理图":
            continue
        if pair.left_value is None and pair.right_value and pair.right_text_id:
            missing_left.append(pair)
            continue
        if pair.right_value is None and pair.left_value and pair.left_text_id:
            key = (pair.sheet_id, pair.left_text_id, pair.left_value)
            missing_right_by_key.setdefault(key, []).append(pair)

    inline_gap = float(config.get("geometry", {}).get("inline_numeric_bridge_gap", 13.0))
    inline_y_tol = float(config.get("geometry", {}).get("inline_numeric_bridge_y_tolerance", 4.0))
    used_pair_ids: set[str] = set()
    for left_pair in missing_left:
        if left_pair.pair_id in used_pair_ids:
            continue
        key = (left_pair.sheet_id, left_pair.right_text_id or "", left_pair.right_value or "")
        candidates = [
            pair
            for pair in missing_right_by_key.get(key, [])
            if pair.pair_id not in used_pair_ids
        ]
        matches = [
            (float(evidence["bridge_gap"]), right_pair, evidence)
            for right_pair in candidates
            if (evidence := _inline_wire_split_evidence(left_pair, right_pair, group_map, inline_gap, inline_y_tol))
            is not None
        ]
        if not matches:
            continue
        _, right_pair, evidence = sorted(matches, key=lambda item: item[0])[0]
        _tag_inline_wire_split_pair(left_pair, right_pair, evidence)
        _tag_inline_wire_split_pair(right_pair, left_pair, evidence)
        used_pair_ids.add(left_pair.pair_id)
        used_pair_ids.add(right_pair.pair_id)


def _inline_wire_split_evidence(
    missing_left: Pair,
    missing_right: Pair,
    group_map: dict[str, LineGroup],
    inline_gap: float,
    inline_y_tol: float,
) -> dict[str, object] | None:
    left_group = group_map.get(missing_left.line_group_id)
    right_group = group_map.get(missing_right.line_group_id)
    if left_group is None or right_group is None:
        return None
    if not _inline_wire_split_group_candidate(left_group, inline_y_tol):
        return None
    if not _inline_wire_split_group_candidate(right_group, inline_y_tol):
        return None
    if abs(left_group.start_y - right_group.start_y) > inline_y_tol:
        return None
    if left_group.row_band_id and right_group.row_band_id and left_group.row_band_id != right_group.row_band_id:
        return None

    bridge_gap = right_group.start_x - left_group.end_x
    min_gap, max_gap = _inline_wire_split_gap_bounds(left_group, right_group, inline_gap)
    if bridge_gap < min_gap or bridge_gap > max_gap:
        return None
    if missing_left.right_coord_y is None or missing_right.left_coord_y is None:
        return None
    bridge_y_delta = abs(missing_left.right_coord_y - missing_right.left_coord_y)
    if bridge_y_delta > inline_y_tol:
        return None

    return {
        "semantic_kind": "continuation_inline_wire_split",
        "continuation_kind": "schematic_inline_wire_split_half_chain",
        "shared_text_id": missing_left.right_text_id,
        "shared_value": missing_left.right_value,
        "bridge_gap": round(bridge_gap, 4),
        "bridge_gap_min": round(min_gap, 4),
        "bridge_gap_max": round(max_gap, 4),
        "bridge_y_delta": round(bridge_y_delta, 4),
        "line_group_y_delta": round(abs(left_group.start_y - right_group.start_y), 4),
    }


def _inline_wire_split_group_candidate(group: LineGroup, inline_y_tol: float) -> bool:
    if group.orientation not in {"horizontal", "grid"}:
        return False
    if abs(group.start_y - group.end_y) > inline_y_tol:
        return False
    layers = {str(layer).upper() for layer in group.layer_hints}
    if layers and layers.issubset({"DIM"}):
        return False
    return group.wire_candidate_score >= 0.55


def _inline_wire_split_gap_bounds(left_group: LineGroup, right_group: LineGroup, inline_gap: float) -> tuple[float, float]:
    if "grid" in {left_group.orientation, right_group.orientation}:
        return -3.0, max(inline_gap, 20.0)
    return 0.0, inline_gap


def _tag_inline_wire_split_pair(pair: Pair, related_pair: Pair, evidence: dict[str, object]) -> None:
    pair.pair_kind = "continuation"
    pair.evidence["pair_kind"] = "continuation"
    pair.evidence["semantic_kind"] = evidence["semantic_kind"]
    pair.evidence["continuation_kind"] = evidence["continuation_kind"]
    pair.evidence["ordinary_pair_eligible"] = False
    pair.evidence["covered_by_inline_wire_split_half_chain"] = True
    pair.evidence["related_inline_wire_split_pair_id"] = related_pair.pair_id
    pair.evidence["shared_text_id"] = evidence["shared_text_id"]
    pair.evidence["shared_value"] = evidence["shared_value"]
    pair.evidence["bridge_gap"] = evidence["bridge_gap"]
    pair.evidence["bridge_gap_min"] = evidence["bridge_gap_min"]
    pair.evidence["bridge_gap_max"] = evidence["bridge_gap_max"]
    pair.evidence["bridge_y_delta"] = evidence["bridge_y_delta"]
    pair.evidence["line_group_y_delta"] = evidence["line_group_y_delta"]
    if "continuation relation" not in pair.rationale:
        pair.rationale = f"{pair.rationale}; continuation relation"


def _mark_schematic_ac_phase_covered_ordinary_pairs(pairs: list[Pair], pages: list[SheetRecord]) -> None:
    sheet_map = {page.sheet_id: page for page in pages}
    covered_text_reasons = _schematic_ac_phase_numeric_text_reasons(pairs, sheet_map)
    if not covered_text_reasons:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.status == "discard":
            continue
        sheet = sheet_map.get(pair.sheet_id)
        if sheet is None or sheet.sheet_category != "二次原理图":
            continue
        if bool(pair.left_value) == bool(pair.right_value):
            continue
        covered_reasons = _pair_text_coverage_reasons(pair, covered_text_reasons)
        if not covered_reasons:
            continue
        pair.status = "discard"
        pair.confidence_bucket = "low"
        pair.rationale = (
            "Covered by schematic_ac_phase_label semantic_mapping; AC phase numeric text "
            "must not be emitted as a bare ordinary half-pair."
        )
        pair.evidence["ordinary_pair_eligible"] = False
        for reason in covered_reasons:
            pair.evidence[f"covered_by_{reason}"] = True


def _schematic_ac_phase_numeric_text_reasons(
    pairs: list[Pair],
    sheet_map: dict[str, SheetRecord],
) -> dict[str, str]:
    text_reasons: dict[str, str] = {}
    for pair in pairs:
        evidence = pair.evidence or {}
        if pair.pair_kind != "semantic_mapping":
            continue
        sheet = sheet_map.get(pair.sheet_id)
        if sheet is None or sheet.sheet_category != "二次原理图":
            continue
        if evidence.get("semantic_mapping_kind") != "schematic_ac_phase_label":
            continue
        if evidence.get("semantic_kind") not in {"schematic_semantic_endpoint", "schematic_semantic_annotation"}:
            continue
        value = evidence.get("numeric_endpoint_text_id")
        if isinstance(value, str) and value:
            text_reasons[value] = "schematic_ac_phase_label_semantic_mapping"
    return text_reasons


def _mark_schematic_ground_covered_ordinary_pairs(pairs: list[Pair], pages: list[SheetRecord]) -> None:
    sheet_map = {page.sheet_id: page for page in pages}
    covered_text_reasons = _schematic_ground_numeric_text_reasons(pairs, sheet_map)
    if not covered_text_reasons:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.status == "discard":
            continue
        sheet = sheet_map.get(pair.sheet_id)
        if sheet is None or sheet.sheet_category != "二次原理图":
            continue
        if bool(pair.left_value) == bool(pair.right_value):
            continue
        covered_reasons = _pair_text_coverage_reasons(pair, covered_text_reasons)
        if not covered_reasons:
            continue
        pair.status = "discard"
        pair.confidence_bucket = "low"
        pair.rationale = (
            "Covered by schematic ground semantic_mapping; GND-covered numeric text "
            "must not be emitted as a bare ordinary half-pair."
        )
        pair.evidence["ordinary_pair_eligible"] = False
        for reason in covered_reasons:
            pair.evidence[f"covered_by_{reason}"] = True


def _schematic_ground_numeric_text_reasons(
    pairs: list[Pair],
    sheet_map: dict[str, SheetRecord],
) -> dict[str, str]:
    text_reasons: dict[str, str] = {}
    for pair in pairs:
        evidence = pair.evidence or {}
        if pair.pair_kind != "semantic_mapping":
            continue
        sheet = sheet_map.get(pair.sheet_id)
        if sheet is None or sheet.sheet_category != "二次原理图":
            continue
        if evidence.get("semantic_mapping_kind") != "schematic_dc_function_label":
            continue
        if evidence.get("semantic_kind") != "schematic_semantic_endpoint":
            continue
        semantic_endpoint = str(evidence.get("semantic_endpoint") or "").strip().upper()
        if semantic_endpoint != "GND":
            continue
        value = evidence.get("numeric_endpoint_text_id")
        if isinstance(value, str) and value:
            text_reasons[value] = "schematic_ground_semantic_mapping"
    return text_reasons


def _input_matrix_local_number_text_ids(wire_component_pairs: list[Pair]) -> set[str]:
    return {
        text_id
        for text_id, reason in _wire_component_local_number_text_reasons(wire_component_pairs).items()
        if reason == "input_matrix_wire_mapping"
    }


def _wire_component_local_number_text_reasons(wire_component_pairs: list[Pair]) -> dict[str, str]:
    text_reasons: dict[str, str] = {}
    text_ids: set[str] = set()
    for pair in wire_component_pairs:
        evidence = pair.evidence or {}
        if pair.pair_kind != "wire_component_mapping":
            continue
        component_submode = evidence.get("component_submode")
        if component_submode == "input_matrix_wire_mapping":
            values = (pair.right_text_id, evidence.get("local_number_text_id"))
        elif component_submode in {
            "component_prefixed_signal_circuit",
            "first_prefixed_external_endpoint_mapping",
            "scoped_visible_prefix_external_endpoint_mapping",
            "inline_klp_component_port_mapping",
            "inline_body_port_mapping",
        }:
            values = (evidence.get("local_number_text_id"),)
        else:
            continue
        for value in values:
            if isinstance(value, str) and value:
                text_ids.add(value)
                text_reasons[value] = str(component_submode)
    return text_reasons


def _pair_text_coverage_reasons(pair: Pair, covered_text_reasons: dict[str, str]) -> set[str]:
    return {
        covered_text_reasons[text_id]
        for text_id in _pair_selected_text_ids(pair)
        if text_id in covered_text_reasons
    }


def _pair_selected_text_ids(pair: Pair) -> set[str]:
    evidence = pair.evidence or {}
    values = {
        pair.left_text_id,
        pair.right_text_id,
        evidence.get("selected_left_text_id"),
        evidence.get("selected_right_text_id"),
    }
    return {value for value in values if isinstance(value, str) and value}


def _wire_component_coverage_rationale(covered_reasons: set[str]) -> str:
    if "component_prefixed_signal_circuit" in covered_reasons:
        return (
            "Covered by component_prefixed_signal_circuit; component local number "
            "must not be emitted as a bare ordinary pair."
        )
    if "first_prefixed_external_endpoint_mapping" in covered_reasons:
        return (
            "Covered by first_prefixed_external_endpoint_mapping; prefixed external local number "
            "must not be emitted as a bare ordinary pair."
        )
    if "scoped_visible_prefix_external_endpoint_mapping" in covered_reasons:
        return (
            "Covered by scoped_visible_prefix_external_endpoint_mapping; scoped local number "
            "must not be emitted as a bare ordinary pair."
        )
    if {
        "inline_klp_component_port_mapping",
        "inline_body_port_mapping",
    } & covered_reasons:
        return (
            "Covered by inline body-port mapping; structured component local number "
            "must not be emitted as a bare ordinary pair."
        )
    return "Covered by input_matrix_wire_mapping; matrix local number must not be emitted as a bare ordinary pair."


def _mark_terminal_prefixed_endpoint_ordinary_pairs(
    pairs: list[Pair],
    table_mappings: list[dict[str, object]],
) -> None:
    covered_text_ids = _terminal_header_table_text_ids(table_mappings)
    if not covered_text_ids:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.status == "discard":
            continue
        if not _uses_derived_prefixed_terminal_endpoint(pair):
            continue
        if not _pair_uses_any_selected_text_id(pair, covered_text_ids):
            continue
        pair.status = "discard"
        pair.confidence_bucket = "low"
        pair.rationale = "Covered by terminal structured endpoint; prefixed terminal text must not be reduced to a bare ordinary pair."
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["covered_by_terminal_structured_endpoint"] = True


def _promote_regular_terminal_row_array_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    pages: list[SheetRecord],
    config: dict,
) -> None:
    """Promote unique two-sided rows in a stable terminal array."""

    terminal_sheet_ids = {
        page.sheet_id
        for page in pages
        if page.route_target == "TerminalDiagramExtractor" or page.sheet_category == "屏端子图"
    }
    if not terminal_sheet_ids:
        return
    group_map = {group.line_group_id: group for group in line_groups}
    clusters: dict[tuple[str, float, float, float], list[tuple[Pair, LineGroup]]] = defaultdict(list)
    for pair in pairs:
        if pair.sheet_id not in terminal_sheet_ids:
            continue
        if pair.pair_kind != "ordinary_pair" or pair.status != "review":
            continue
        if not pair.left_value or not pair.right_value or not pair.left_text_id or not pair.right_text_id:
            continue
        if pair.alternative_pair_candidate_ids:
            continue
        evidence = pair.evidence or {}
        if evidence.get("line_orientation") != "horizontal":
            continue
        if evidence.get("selected_left_channel") != "terminal_numeric_channel":
            continue
        if evidence.get("selected_right_channel") != "terminal_numeric_channel":
            continue
        if not evidence.get("selected_left_candidate_id") or not evidence.get("selected_right_candidate_id"):
            continue
        ambiguity_gap = evidence.get("score_breakdown", {}).get("ambiguity_gap")
        if ambiguity_gap not in {None, ""}:
            continue
        group = group_map.get(pair.line_group_id)
        if group is None or group.orientation != "horizontal":
            continue
        min_x, max_x = sorted((group.start_x, group.end_x))
        key = (pair.sheet_id, round(min_x, 1), round(max_x, 1), round(group.length, 1))
        clusters[key].append((pair, group))

    min_rows = int(config.get("geometry", {}).get("terminal_row_array_min_rows", 6))
    high_threshold = float(config.get("confidence", {}).get("high_threshold", 0.92))
    for key, rows in clusters.items():
        if len(rows) < 3:
            continue
        y_values = sorted({round((group.start_y + group.end_y) / 2.0, 4) for _, group in rows})
        if len(y_values) != len(rows):
            continue
        diffs = [right - left for left, right in zip(y_values, y_values[1:], strict=False) if right > left]
        if not diffs:
            continue
        pitch = min(diffs)
        if not 2.0 <= pitch <= 20.0:
            continue
        regular = 0
        for diff in diffs:
            multiple = diff / pitch
            nearest = round(multiple)
            if 1 <= nearest <= 6 and abs(multiple - nearest) <= 0.08:
                regular += 1
        if regular / len(diffs) < 0.9:
            continue
        ordered_rows = sorted(
            rows,
            key=lambda item: (item[1].start_y + item[1].end_y) / 2.0,
        )
        short_sequential = _terminal_row_values_are_consecutive(ordered_rows)
        if len(rows) < min_rows and not short_sequential:
            continue
        array_id = f"{key[0]}:{key[1]:.1f}:{key[2]:.1f}:{key[3]:.1f}"
        for pair, _ in rows:
            original_confidence = pair.confidence
            pair.confidence = max(pair.confidence, high_threshold)
            pair.status = "pass"
            pair.confidence_bucket = "high"
            pair.rationale = "Accepted by stable terminal row-array geometry with unique two-sided candidates."
            pair.evidence["terminal_row_array_authority"] = True
            pair.evidence["terminal_row_array_id"] = array_id
            pair.evidence["terminal_row_array_size"] = len(rows)
            pair.evidence["terminal_row_array_pitch"] = round(pitch, 4)
            pair.evidence["pre_array_confidence"] = original_confidence


def _terminal_row_values_are_consecutive(rows: list[tuple[Pair, LineGroup]]) -> bool:
    if len(rows) < 3:
        return False
    try:
        left_values = [int(str(pair.left_value)) for pair, _ in rows]
        right_values = [int(str(pair.right_value)) for pair, _ in rows]
    except (TypeError, ValueError):
        return False
    left_deltas = [right - left for left, right in zip(left_values, left_values[1:], strict=False)]
    right_deltas = [right - left for left, right in zip(right_values, right_values[1:], strict=False)]
    return (
        bool(left_deltas)
        and len(set(left_deltas)) == 1
        and len(set(right_deltas)) == 1
        and abs(left_deltas[0]) == 1
        and left_deltas[0] == right_deltas[0]
    )


def _terminal_header_table_text_ids(table_mappings: list[dict[str, object]]) -> set[str]:
    text_ids: set[str] = set()
    for mapping in _iter_terminal_header_table_mappings(table_mappings):
        if mapping.get("mapping_mode") != "terminal_header_table":
            continue
        for key in ("middle_text_id", "left_text_id", "right_text_id"):
            value = mapping.get(key)
            if isinstance(value, str) and value:
                text_ids.add(value)
    return text_ids


def _iter_terminal_header_table_mappings(
    table_mappings: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in table_mappings:
        nested = item.get("mappings")
        if isinstance(nested, list):
            rows.extend(row for row in nested if isinstance(row, dict))
        else:
            rows.append(item)
    return rows


def _pair_uses_any_selected_text_id(pair: Pair, text_ids: set[str]) -> bool:
    evidence = pair.evidence or {}
    selected_ids = {
        evidence.get("selected_left_text_id"),
        evidence.get("selected_right_text_id"),
    }
    return any(isinstance(text_id, str) and text_id in text_ids for text_id in selected_ids)


def _pair_uses_any_text_id(pair: Pair, text_ids: set[str]) -> bool:
    evidence = pair.evidence or {}
    selected_ids = {
        pair.left_text_id,
        pair.right_text_id,
        evidence.get("selected_left_text_id"),
        evidence.get("selected_right_text_id"),
    }
    return any(isinstance(text_id, str) and text_id in text_ids for text_id in selected_ids)


def _uses_derived_prefixed_terminal_endpoint(pair: Pair) -> bool:
    evidence = pair.evidence or {}
    left_raw = str(evidence.get("selected_left_raw_text") or "")
    right_raw = str(evidence.get("selected_right_raw_text") or "")
    left_derived = evidence.get("selected_left_is_derived_numeric") is True
    right_derived = evidence.get("selected_right_is_derived_numeric") is True
    return (
        left_derived
        and _looks_like_prefixed_terminal_endpoint(left_raw)
    ) or (
        right_derived
        and _looks_like_prefixed_terminal_endpoint(right_raw)
    )


def _looks_like_prefixed_terminal_endpoint(value: str) -> bool:
    return bool(re.fullmatch(r"(?i)\d+(?:-\d+)?n\d{3,}", value.strip()))


def _terminal_header_table_retry_pages(
    pages: list[SheetRecord],
) -> list[SheetRecord]:
    retry_pages: list[SheetRecord] = []
    for page in pages:
        if (
            page.sheet_category != "屏端子图"
            or page.audit_role != "supplemental"
        ):
            continue
        expanded_bbox = page.extent_bbox or page.frame_bbox or _padded_bbox(page.audit_area_bbox)
        if expanded_bbox is None or expanded_bbox == page.audit_area_bbox:
            continue
        retry_pages.append(replace(page, audit_area_bbox=expanded_bbox))
    return retry_pages


def _padded_bbox(bbox: tuple[float, float, float, float] | None) -> tuple[float, float, float, float] | None:
    if bbox is None:
        return None
    min_x, min_y, max_x, max_y = bbox
    pad_x = max(5.0, (max_x - min_x) * 0.1)
    pad_y = max(5.0, (max_y - min_y) * 0.1)
    return (
        min_x - pad_x,
        min_y - pad_y,
        max_x + pad_x,
        max_y + pad_y,
    )


def _extend_unique_pairs(existing: list[Pair], additions: list[Pair]) -> None:
    seen = {_pair_dedupe_key(pair) for pair in existing}
    for pair in additions:
        key = _pair_dedupe_key(pair)
        if key in seen:
            continue
        existing.append(pair)
        seen.add(key)


def _pair_dedupe_key(pair: Pair) -> tuple[object, ...]:
    return (
        pair.sheet_id,
        pair.pair_key,
        pair.left_text_id,
        pair.right_text_id,
        pair.left_value,
        pair.right_value,
    )


def _merge_table_mappings(
    existing: list[dict[str, object]],
    additions: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged = [_copy_table_mapping_item(item) for item in existing]
    by_sheet = {str(item.get("sheet_id")): item for item in merged if item.get("sheet_id") is not None}
    seen_by_sheet = {
        sheet_id: {_mapping_dedupe_key(mapping) for mapping in item.get("mappings", [])}
        for sheet_id, item in by_sheet.items()
    }

    for item in additions:
        sheet_id_value = item.get("sheet_id")
        if sheet_id_value is None:
            continue
        sheet_id = str(sheet_id_value)
        target = by_sheet.get(sheet_id)
        if target is None:
            target = _copy_table_mapping_item(item)
            _refresh_table_mapping_item(target)
            merged.append(target)
            by_sheet[sheet_id] = target
            seen_by_sheet[sheet_id] = {
                _mapping_dedupe_key(mapping)
                for mapping in target.get("mappings", [])
            }
            continue

        target_mappings = target.setdefault("mappings", [])
        seen = seen_by_sheet.setdefault(sheet_id, set())
        for mapping in item.get("mappings", []):
            key = _mapping_dedupe_key(mapping)
            if key in seen:
                continue
            target_mappings.append(dict(mapping))
            seen.add(key)
        target["three_column"] = bool(target.get("three_column") or item.get("three_column"))
        target["col_count"] = max(int(target.get("col_count") or 0), int(item.get("col_count") or 0))
        _refresh_table_mapping_item(target)
    return merged


def _copy_table_mapping_item(item: dict[str, object]) -> dict[str, object]:
    copied = dict(item)
    copied["mappings"] = [dict(mapping) for mapping in item.get("mappings", [])]
    return copied


def _refresh_table_mapping_item(item: dict[str, object]) -> None:
    item["row_count"] = len(item.get("mappings", []))


def _mapping_dedupe_key(mapping: object) -> tuple[object, ...]:
    if not isinstance(mapping, dict):
        return (mapping,)
    return (
        mapping.get("mapping_mode"),
        mapping.get("sheet_id"),
        mapping.get("logical_endpoint"),
        mapping.get("row_number"),
        mapping.get("middle_text_id"),
        mapping.get("left_text_id"),
        mapping.get("right_text_id"),
        mapping.get("left_value"),
        mapping.get("right_value"),
    )
