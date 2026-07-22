from __future__ import annotations

import math
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
from dwg_audit.audit.table_extractor import extract_component_panel_port_table_pairs
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
    blocks: list[BlockRecord] | None = None,
    classifications: dict[str, PageClassification] | None = None,
) -> PairingExtractionResult:
    return _extract_pairs_for_route(
        executed_extractor="WireDiagramExtractor",
        route_target="WireDiagramExtractor",
        pages=pages,
        texts=texts,
        lines=lines,
        blocks=blocks,
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
    table_mappings = []
    if executed_extractor == "ComponentDiagramExtractor":
        _promote_xjdz_structural_component_pairs(
            pairs,
            line_groups,
            texts,
            lines,
        )
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
        panel_table_pairs, panel_table_mappings, panel_consumed_group_ids = (
            extract_component_panel_port_table_pairs(
                texts,
                lines,
                line_groups,
                pages,
                pair_id_factory=IdFactory(f"P{id_stem}V"),
            )
        )
        component_pairs.extend(panel_table_pairs)
        consumed_group_ids.update(panel_consumed_group_ids)
        table_mappings.extend(panel_table_mappings)
        if component_pairs:
            _mark_consumed_component_ordinary_pairs(pairs, consumed_group_ids)
            pairs.extend(component_pairs)
            mark_component_mapping_endpoint_covered_ordinary_pairs(pairs, component_pairs)
        # Device-panel silkscreen pin lattices (HMC HD/BCD grids) stay as graph
        # evidence but must not enter ordinary terminal / cross-page audit.
        _shadow_hmc_silkscreen_ordinary_pairs(pairs, pages, texts)
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
            retry_sheet_ids = {page.sheet_id for page in retry_pages}
            # The expanded retry has the complete neighboring-header context.
            # Replace partial-bbox results for those sheets instead of unioning
            # stale relations that the wider ownership corridors rejected.
            table_pairs = [pair for pair in table_pairs if pair.sheet_id not in retry_sheet_ids]
            table_mappings = [
                mapping
                for mapping in table_mappings
                if mapping.get("sheet_id") not in retry_sheet_ids
            ]
            _extend_unique_pairs(table_pairs, retry_pairs)
            table_mappings = _merge_table_mappings(table_mappings, retry_mappings)
        _mark_terminal_prefixed_endpoint_ordinary_pairs(pairs, table_mappings)
        _promote_regular_terminal_row_array_pairs(pairs, line_groups, pages, config)
        pairs.extend(table_pairs)
    if executed_extractor == "WireDiagramExtractor":
        _shadow_grid_wire_ordinary_pairs(pairs, pages)
        _shadow_communication_medium_ordinary_pairs(pairs, pages)
        _shadow_repeated_panel_silkscreen_ordinary_pairs(pairs, pages, texts, blocks or [])
        _shadow_ct_polarity_reference_ordinary_pairs(
            pairs,
            pages,
            texts,
            line_groups,
            lines,
            terminal_candidates,
        )
        _shadow_parallel_grid_separator_ordinary_pairs(pairs, line_groups, lines)
    _shadow_closed_tall_polyline_enclosure_ordinary_pairs(pairs, line_groups, lines, texts)
    if executed_extractor == "WireDiagramExtractor":
        _shadow_connect_multidrop_rail_ordinary_pairs(pairs, line_groups, lines)
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


def _component_mapping_endpoint_keys(component_pairs: list[Pair]) -> set[tuple[str, str]]:
    """Text ids and normalized endpoint tokens already bound by component_mapping."""
    keys: set[tuple[str, str]] = set()
    for pair in component_pairs:
        if pair.pair_kind != "component_mapping":
            continue
        sheet_id = str(pair.sheet_id or "")
        for text_id in (pair.left_text_id, pair.right_text_id):
            if text_id:
                keys.add((sheet_id, f"text:{text_id}"))
        evidence = pair.evidence or {}
        for raw in (
            pair.left_value,
            pair.right_value,
            evidence.get("selected_left_raw_text"),
            evidence.get("selected_right_raw_text"),
            evidence.get("external_endpoint"),
            evidence.get("body_port"),
        ):
            token = str(raw or "").strip()
            if not token:
                continue
            keys.add((sheet_id, f"raw:{token.lower()}"))
            alias = _component_endpoint_display_alias(token)
            if alias:
                keys.add((sheet_id, f"alias:{alias}"))
    return keys


def _component_endpoint_display_alias(token: str) -> str | None:
    """Normalize only an optional numeric scope before an n-terminal value."""

    match = re.fullmatch(r"(?:\d+(?:-\d+)*)?(n\d{2,})", token.strip(), re.IGNORECASE)
    return match.group(1).lower() if match else None


def mark_component_mapping_endpoint_covered_ordinary_pairs(
    pairs: list[Pair],
    component_pairs: list[Pair],
) -> None:
    """Shadow ordinary stubs that only restate already-mapped component endpoints."""
    keys = _component_mapping_endpoint_keys(component_pairs)
    if not keys:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        if len([value for value in (pair.left_value, pair.right_value) if value]) != 1:
            continue
        evidence = pair.evidence or {}
        sheet_id = str(pair.sheet_id or "")
        hit = False
        for text_id in (pair.left_text_id, pair.right_text_id):
            if text_id and (sheet_id, f"text:{text_id}") in keys:
                hit = True
                break
        if not hit:
            for raw in (
                pair.left_value,
                pair.right_value,
                evidence.get("selected_left_raw_text"),
                evidence.get("selected_right_raw_text"),
            ):
                token = str(raw or "").strip()
                if not token:
                    continue
                if (sheet_id, f"raw:{token.lower()}") in keys:
                    hit = True
                    break
                alias = _component_endpoint_display_alias(token)
                if alias and (sheet_id, f"alias:{alias}") in keys:
                    hit = True
                    break
        if not hit:
            continue
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = "covered_by_component_mapping_endpoint"
        pair.evidence["covered_by_component_mapping_endpoint"] = True


def _mark_component_mapping_endpoint_covered_ordinary_pairs(
    pairs: list[Pair],
    component_pairs: list[Pair],
) -> None:
    """Backward-compatible private alias for older callers and focused tests."""

    mark_component_mapping_endpoint_covered_ordinary_pairs(pairs, component_pairs)


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


def _shadow_parallel_grid_separator_ordinary_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    lines: list[LineEntity],
) -> None:
    """Shadow repeated, text-backed separator rows with no electrical drop.

    A separator is accepted only when the producer supplies a complete local
    parallel-row family: at least two rows repeat one side/value/text claim,
    another parallel row has no endpoint claim, and no interior vertical line
    touches any row. Boundary touches remain permitted because frame edges can
    terminate at a separator without making an interior connection.
    """

    tolerance = 0.25
    group_by_id = {group.line_group_id: group for group in line_groups}
    line_by_id = {line.line_id: line for line in lines}
    pairs_by_group: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        pairs_by_group[pair.line_group_id].append(pair)

    def _group_lines(group: LineGroup) -> list[LineEntity] | None:
        member_lines = [line_by_id.get(line_id) for line_id in group.member_line_ids]
        if not member_lines or any(line is None for line in member_lines):
            return None
        resolved = [line for line in member_lines if line is not None]
        if any(
            str(line.source_entity_type or "").upper() != "LINE"
            or not str(line.layer or "").strip()
            or str(line.layer or "").casefold() == "connect"
            or line.source_block_name is not None
            or abs(float(line.start_y) - float(line.end_y)) > tolerance
            for line in resolved
        ):
            return None
        return resolved

    groups_by_scope: dict[tuple[str, str], list[tuple[LineGroup, list[LineEntity]]]] = defaultdict(list)
    for group in line_groups:
        resolved = _group_lines(group)
        if resolved is None or str(group.orientation or "").casefold() != "horizontal":
            continue
        groups_by_scope[(group.sheet_id, group.file_id)].append((group, resolved))

    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        if pair.alternative_pair_candidate_ids or pair.ambiguity_gap is not None:
            continue
        present_sides = [
            side
            for side in ("left", "right")
            if str(getattr(pair, f"{side}_value", None) or "").strip()
        ]
        if len(present_sides) != 1:
            continue
        present_side = present_sides[0]
        present_value = str(getattr(pair, f"{present_side}_value") or "").strip()
        present_text_id = str(getattr(pair, f"{present_side}_text_id") or "").strip()
        if (
            not present_value
            or not present_text_id
            or present_text_id.casefold() in {"nan", "none", "null"}
        ):
            continue

        group = group_by_id.get(pair.line_group_id)
        if group is None:
            continue
        group_lines = _group_lines(group)
        if group_lines is None:
            continue
        group_min_x, group_max_x = sorted((float(group.start_x), float(group.end_x)))
        group_width = group_max_x - group_min_x
        if group_width <= 0.0:
            continue
        scope = (group.sheet_id, group.file_id)
        parallel: list[tuple[LineGroup, list[LineEntity]]] = []
        for candidate_group, candidate_lines in groups_by_scope.get(scope, []):
            candidate_min_x, candidate_max_x = sorted(
                (float(candidate_group.start_x), float(candidate_group.end_x))
            )
            if (
                abs(candidate_min_x - group_min_x) > tolerance
                or abs(candidate_max_x - group_max_x) > tolerance
                or abs((candidate_max_x - candidate_min_x) - group_width) > tolerance
            ):
                continue
            candidate_layer = {str(line.layer or "").casefold() for line in candidate_lines}
            group_layer = {str(line.layer or "").casefold() for line in group_lines}
            if not candidate_layer or candidate_layer != group_layer:
                continue
            parallel.append((candidate_group, candidate_lines))
        if len(parallel) < 3:
            continue

        row_y_by_group = {
            candidate_group.line_group_id: (float(candidate_group.start_y) + float(candidate_group.end_y)) / 2.0
            for candidate_group, _ in parallel
        }
        row_ys = sorted(row_y_by_group.values())
        if any(abs(left - right) <= tolerance for left, right in zip(row_ys, row_ys[1:])):
            continue
        row_gaps = [right - left for left, right in zip(row_ys, row_ys[1:])]
        if max(row_gaps) - min(row_gaps) > tolerance:
            continue
        if row_ys[-1] - row_ys[0] > group_width + tolerance:
            continue

        parallel_pairs: list[Pair] = []
        valid_family = True
        for candidate_group, _ in parallel:
            candidate_pairs = pairs_by_group.get(candidate_group.line_group_id, [])
            if len(candidate_pairs) != 1 or candidate_pairs[0].pair_kind != "ordinary_pair":
                valid_family = False
                break
            parallel_pairs.append(candidate_pairs[0])
        if not valid_family:
            continue

        valued_pairs = [
            candidate
            for candidate in parallel_pairs
            if str(getattr(candidate, "left_value", None) or "").strip()
            or str(getattr(candidate, "right_value", None) or "").strip()
        ]
        unvalued_pairs = [
            candidate
            for candidate in parallel_pairs
            if not str(getattr(candidate, "left_value", None) or "").strip()
            and not str(getattr(candidate, "right_value", None) or "").strip()
            and not str(getattr(candidate, "left_text_id", None) or "").strip()
            and not str(getattr(candidate, "right_text_id", None) or "").strip()
        ]
        if (
            len(valued_pairs) < 2
            or not unvalued_pairs
            or len(valued_pairs) + len(unvalued_pairs) != len(parallel_pairs)
        ):
            continue
        if any(
            candidate.status == "discard"
            or candidate.evidence.get("ordinary_pair_eligible") is False
            or candidate.alternative_pair_candidate_ids
            or candidate.ambiguity_gap is not None
            for candidate in valued_pairs
        ):
            continue
        other_side = "right" if present_side == "left" else "left"
        if any(
            str(getattr(candidate, f"{present_side}_value", None) or "").strip() != present_value
            or str(getattr(candidate, f"{present_side}_text_id", None) or "").strip() != present_text_id
            or bool(str(getattr(candidate, f"{other_side}_value", None) or "").strip())
            or bool(str(getattr(candidate, f"{other_side}_text_id", None) or "").strip())
            or not str(candidate.selected_pair_candidate_id or "").strip()
            or str(candidate.evidence.get("line_orientation") or "").casefold() != "horizontal"
            or str(candidate.evidence.get(f"selected_{present_side}_candidate_id") or "").strip() == ""
            or str(candidate.evidence.get(f"selected_{present_side}_text_id") or "").strip() != present_text_id
            or str(candidate.evidence.get(f"selected_{present_side}_raw_text") or "").strip() != present_value
            or candidate.evidence.get(f"selected_{other_side}_candidate_id") is not None
            or candidate.evidence.get(f"selected_{other_side}_text_id") is not None
            or candidate.evidence.get(f"selected_{other_side}_raw_text") is not None
            for candidate in valued_pairs
        ):
            continue
        if any(
            candidate.status != "discard"
            or not str(candidate.selected_pair_candidate_id or "").strip()
            or str(candidate.evidence.get("line_orientation") or "").casefold() != "horizontal"
            or any(
                candidate.evidence.get(key) is not None
                for key in (
                    "selected_left_candidate_id",
                    "selected_left_text_id",
                    "selected_left_raw_text",
                    "selected_right_candidate_id",
                    "selected_right_text_id",
                    "selected_right_raw_text",
                )
            )
            for candidate in unvalued_pairs
        ):
            continue

        member_ids = {
            str(line.line_id)
            for _, candidate_lines in parallel
            for line in candidate_lines
        }
        row_bounds = [
            (
                min(float(candidate_group.start_x), float(candidate_group.end_x)),
                max(float(candidate_group.start_x), float(candidate_group.end_x)),
                row_y_by_group[candidate_group.line_group_id],
            )
            for candidate_group, _ in parallel
        ]
        touches_interior = False
        for line in lines:
            if str(line.line_id) in member_ids:
                continue
            dx = abs(float(line.start_x) - float(line.end_x))
            dy = abs(float(line.start_y) - float(line.end_y))
            if dx > tolerance or dy <= tolerance:
                continue
            if line.sheet_id != group.sheet_id or line.file_id != group.file_id:
                continue
            line_x = (float(line.start_x) + float(line.end_x)) / 2.0
            for row_min_x, row_max_x, row_y in row_bounds:
                if not row_min_x + tolerance < line_x < row_max_x - tolerance:
                    continue
                if min(float(line.start_y), float(line.end_y)) - tolerance <= row_y <= max(float(line.start_y), float(line.end_y)) + tolerance:
                    touches_interior = True
                    break
            if touches_interior:
                break
        if touches_interior:
            continue

        for candidate in valued_pairs:
            candidate.evidence["ordinary_pair_eligible"] = False
            candidate.evidence["ordinary_pair_shadow_only"] = True
            candidate.evidence["ordinary_pair_shadow_reason"] = "parallel_grid_separator"
            candidate.evidence["parallel_grid_separator"] = {
                "parallel_line_group_ids": sorted(candidate_group.line_group_id for candidate_group, _ in parallel),
                "parallel_row_ys": [round(value, 6) for value in row_ys],
                "shared_side": present_side,
                "shared_value": present_value,
                "shared_text_id": present_text_id,
                "unvalued_line_group_ids": sorted(
                    candidate.line_group_id
                    for candidate in unvalued_pairs
                ),
            }


def _shadow_communication_medium_ordinary_pairs(pairs: list[Pair], pages: list[SheetRecord]) -> None:
    """Keep ordinary wire pairs off critical audit when page is a communication medium sheet.

    Communication drawings (serial/fiber/network) still extract pairs for review assist, but
    bare numeric missing-side noise must not surface as ordinary terminal-pair issues.
    """
    sheet_map = {page.sheet_id: page for page in pages}
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        sheet = sheet_map.get(pair.sheet_id)
        if sheet is None or sheet.route_target != "WireDiagramExtractor":
            continue
        media = list(getattr(sheet, "communication_media", None) or [])
        if not media:
            continue
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = "communication_medium"
        pair.evidence["communication_media"] = media


def _shadow_ct_polarity_reference_ordinary_pairs(
    pairs: list[Pair],
    pages: list[SheetRecord],
    texts: list[TextItem],
    line_groups: list[LineGroup],
    lines: list[LineEntity],
    terminal_candidates: list[TerminalCandidate] | None = None,
) -> None:
    """Keep complete CT-polarity reference annotations out of endpoint audit."""

    geometry_tolerance = 1e-6
    motif_radius = 20.0
    required_motif_tokens = ("P1", "P2", "S1", "S2")
    pages_by_scope: dict[tuple[str, str], list[SheetRecord]] = defaultdict(list)
    groups_by_key: dict[tuple[str, str, str], list[LineGroup]] = defaultdict(list)
    lines_by_key: dict[tuple[str, str, str], list[LineEntity]] = defaultdict(list)
    for page in pages:
        pages_by_scope[(page.sheet_id, page.file_id)].append(page)
    for group in line_groups:
        groups_by_key[(group.sheet_id, group.file_id, group.line_group_id)].append(group)
    for line in lines:
        lines_by_key[(line.sheet_id, line.file_id, line.line_id)].append(line)
    texts_by_scope: dict[tuple[str, str], list[TextItem]] = defaultdict(list)
    text_by_key: dict[tuple[str, str, str], list[TextItem]] = defaultdict(list)
    for text in texts:
        scope = (text.sheet_id, text.file_id)
        texts_by_scope[scope].append(text)
        text_by_key[(*scope, text.text_id)].append(text)
    candidates_by_key: dict[tuple[str, str, str], list[TerminalCandidate]] = defaultdict(list)
    for candidate in terminal_candidates or []:
        candidates_by_key[(candidate.sheet_id, candidate.file_id, candidate.candidate_id)].append(candidate)

    def _finite_point(first: object, second: object) -> tuple[float, float] | None:
        try:
            point = (float(first), float(second))
        except (TypeError, ValueError):
            return None
        return point if all(math.isfinite(value) for value in point) else None

    def _finite_scalar(value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _same_point(
        first: tuple[float, float] | None,
        second: tuple[float, float] | None,
    ) -> bool:
        return first is not None and second is not None and all(
            abs(left - right) <= geometry_tolerance
            for left, right in zip(first, second, strict=True)
        )

    def _same_segment(group: LineGroup, line: LineEntity) -> bool:
        group_start = _finite_point(group.start_x, group.start_y)
        group_end = _finite_point(group.end_x, group.end_y)
        line_start = _finite_point(line.start_x, line.start_y)
        line_end = _finite_point(line.end_x, line.end_y)
        return (
            _same_point(group_start, line_start) and _same_point(group_end, line_end)
        ) or (
            _same_point(group_start, line_end) and _same_point(group_end, line_start)
        )

    def _evidence_geometry_matches(evidence: dict[str, object], group: LineGroup) -> bool:
        raw_start = evidence.get("line_start")
        raw_end = evidence.get("line_end")
        if not (
            isinstance(raw_start, (list, tuple))
            and len(raw_start) == 2
            and isinstance(raw_end, (list, tuple))
            and len(raw_end) == 2
        ):
            return False
        evidence_start = _finite_point(raw_start[0], raw_start[1])
        evidence_end = _finite_point(raw_end[0], raw_end[1])
        group_start = _finite_point(group.start_x, group.start_y)
        group_end = _finite_point(group.end_x, group.end_y)
        return _same_point(evidence_start, group_start) and _same_point(
            evidence_end,
            group_end,
        )

    def _motif_text_ids(
        scope_texts: list[TextItem],
        endpoint: tuple[float, float],
    ) -> list[str] | None:
        tokens: dict[str, list[str]] = defaultdict(list)
        for text in scope_texts:
            if text.source_block_name is not None:
                continue
            text_point = _finite_point(text.insert_x, text.insert_y)
            if text_point is None:
                continue
            distance = math.hypot(text_point[0] - endpoint[0], text_point[1] - endpoint[1])
            if not math.isfinite(distance) or distance > motif_radius:
                continue
            token = str(text.normalized_text or text.text or "").strip().upper()
            if token in {*required_motif_tokens, "*"}:
                tokens[token].append(text.text_id)
        if any(len(tokens[token]) != 1 for token in required_motif_tokens):
            return None
        if len(tokens["*"]) < 2:
            return None
        motif_ids = sorted(
            text_id
            for token in (*required_motif_tokens, "*")
            for text_id in tokens[token]
        )
        return motif_ids if len(set(motif_ids)) == len(motif_ids) else None

    def _semantic_text_ids(scope_texts: list[TextItem]) -> tuple[list[str], list[str]] | None:
        polarity_ids: list[str] = []
        power_flow_ids: list[str] = []
        for text in scope_texts:
            if text.source_block_name is not None:
                continue
            raw = f"{text.normalized_text or ''} {text.text or ''}".casefold()
            has_ct = re.search(r"(?<![a-z0-9])ct(?![a-z0-9])", raw) is not None or "电流互感器" in raw
            has_polarity = "polarity" in raw or "极性" in raw
            if has_ct and has_polarity:
                polarity_ids.append(text.text_id)
            if "power flow" in raw or "功率流向" in raw:
                power_flow_ids.append(text.text_id)
        if not polarity_ids or not power_flow_ids:
            return None
        if not any(polarity_id != power_flow_id for polarity_id in polarity_ids for power_flow_id in power_flow_ids):
            return None
        return sorted(set(polarity_ids)), sorted(set(power_flow_ids))

    for pair in pairs:
        evidence = pair.evidence
        if not isinstance(evidence, dict):
            continue
        if (
            pair.pair_kind != "ordinary_pair"
            or pair.status != "review"
            or evidence.get("ordinary_pair_eligible") is False
            or pair.alternative_pair_candidate_ids != []
            or pair.ambiguity_gap is not None
        ):
            continue
        scope = (pair.sheet_id, pair.file_id)
        page_rows = pages_by_scope.get(scope, [])
        if len(page_rows) != 1 or page_rows[0].route_target != "WireDiagramExtractor":
            continue
        present_sides = [
            side
            for side in ("left", "right")
            if str(getattr(pair, f"{side}_value", None) or "").strip()
        ]
        if len(present_sides) != 1:
            continue
        present_side = present_sides[0]
        missing_side = "right" if present_side == "left" else "left"
        selected_candidate_id = getattr(pair, f"{present_side}_candidate_id", None)
        selected_text_id = getattr(pair, f"{present_side}_text_id", None)
        selected_value = str(getattr(pair, f"{present_side}_value", None) or "").strip()
        selected_raw = evidence.get(f"selected_{present_side}_raw_text")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                pair.selected_pair_candidate_id,
                selected_candidate_id,
                selected_text_id,
                selected_raw,
            )
        ):
            continue
        if (
            re.fullmatch(r"[+-]?\d+(?:\.\d+)?", selected_value) is None
            or re.fullmatch(r"[+-]?\d+(?:\.\d+)?", str(selected_raw).strip()) is None
            or str(getattr(pair, "pair_key", "") or "")
            != (f"?->{selected_value}" if present_side == "right" else f"{selected_value}->?")
            or evidence.get("pair_key") != getattr(pair, "pair_key", None)
        ):
            continue
        if (
            evidence.get("line_group_id") != pair.line_group_id
            or evidence.get("selected_pair_candidate_id") != pair.selected_pair_candidate_id
            or evidence.get(f"selected_{present_side}_candidate_id") != selected_candidate_id
            or evidence.get(f"selected_{present_side}_text_id") != selected_text_id
            or evidence.get(f"selected_{present_side}_channel") != "terminal_numeric_channel"
            or evidence.get(f"selected_{present_side}_channel_detail") is not None
            or evidence.get(f"selected_{present_side}_source_block_name") is not None
            or evidence.get(f"selected_{present_side}_is_derived_numeric") is not False
            or evidence.get("alternative_pair_candidate_ids") != []
            or any(
                evidence.get(f"selected_{missing_side}_{field}") is not None
                for field in ("candidate_id", "text_id", "raw_text", "channel", "channel_detail", "source_block_name")
            )
            or getattr(pair, f"{missing_side}_candidate_id", None) is not None
            or getattr(pair, f"{missing_side}_text_id", None) is not None
        ):
            continue
        score_breakdown = evidence.get("score_breakdown")
        if not isinstance(score_breakdown, dict) or score_breakdown.get("ambiguity_gap") is not None:
            continue

        group_rows = groups_by_key.get((*scope, pair.line_group_id), [])
        group = group_rows[0] if len(group_rows) == 1 else None
        if group is None:
            continue
        member_line_ids = group.member_line_ids
        if (
            not isinstance(member_line_ids, list)
            or len(member_line_ids) != 1
            or not isinstance(member_line_ids[0], str)
            or not member_line_ids[0].strip()
            or (group.sheet_id, group.file_id) != scope
            or str(group.orientation or "").casefold() != "horizontal"
            or evidence.get("line_orientation") != group.orientation
            or not _evidence_geometry_matches(evidence, group)
        ):
            continue
        line_rows = lines_by_key.get((*scope, member_line_ids[0]), [])
        line = line_rows[0] if len(line_rows) == 1 else None
        if (
            line is None
            or (line.sheet_id, line.file_id) != scope
            or str(line.source_entity_type or "").upper() != "LINE"
            or str(line.layer or "").strip().casefold() == "connect"
            or line.source_block_name is not None
            or not _same_segment(group, line)
        ):
            continue

        candidate_rows = candidates_by_key.get((*scope, str(selected_candidate_id)), [])
        text_rows = text_by_key.get((*scope, str(selected_text_id)), [])
        if len(candidate_rows) != 1 or len(text_rows) != 1:
            continue
        candidate = candidate_rows[0]
        selected_text = text_rows[0]
        pair_text_point = _finite_point(
            getattr(pair, f"{present_side}_coord_x", None),
            getattr(pair, f"{present_side}_coord_y", None),
        )
        candidate_text_point = _finite_point(candidate.text_insert_x, candidate.text_insert_y)
        selected_text_point = _finite_point(selected_text.insert_x, selected_text.insert_y)
        candidate_endpoint = _finite_point(candidate.endpoint_x, candidate.endpoint_y)
        group_endpoint = _finite_point(
            group.start_x if present_side == "left" else group.end_x,
            group.start_y if present_side == "left" else group.end_y,
        )
        candidate_distance_x = _finite_scalar(candidate.distance_x)
        candidate_distance_y = _finite_scalar(candidate.distance_y)
        expected_distance_x = (
            abs(candidate_text_point[0] - candidate_endpoint[0])
            if candidate_text_point is not None and candidate_endpoint is not None
            else None
        )
        expected_distance_y = (
            abs(candidate_text_point[1] - candidate_endpoint[1])
            if candidate_text_point is not None and candidate_endpoint is not None
            else None
        )
        if (
            candidate.line_group_id != pair.line_group_id
            or (candidate.sheet_id, candidate.file_id) != scope
            or candidate.side != present_side
            or candidate.text_id != selected_text_id
            or str(candidate.value or "").strip() != selected_value
            or str(candidate.text or "").strip() != str(selected_raw).strip()
            or str(selected_text.text or "").strip() != str(selected_raw).strip()
            or str(selected_text.normalized_text or selected_text.text or "").strip() != selected_value
            or str(candidate.status or "").casefold() != "accepted"
            or candidate.rejection_reason not in (None, "")
            or candidate.channel != "terminal_numeric_channel"
            or candidate.channel_detail != evidence.get(f"selected_{present_side}_channel_detail")
            or candidate.source_block_name is not None
            or selected_text.source_block_name is not None
            or selected_text.is_numeric_candidate is not True
            or not _same_point(pair_text_point, candidate_text_point)
            or not _same_point(candidate_text_point, selected_text_point)
            or not _same_point(candidate_endpoint, group_endpoint)
            or expected_distance_x is None
            or expected_distance_y is None
            or candidate_distance_x is None
            or candidate_distance_y is None
            or abs(candidate_distance_x - expected_distance_x) > 1e-3
            or abs(candidate_distance_y - expected_distance_y) > 1e-3
        ):
            continue

        scope_texts = texts_by_scope.get(scope, [])
        group_start = _finite_point(group.start_x, group.start_y)
        group_end = _finite_point(group.end_x, group.end_y)
        if group_start is None or group_end is None:
            continue
        start_motif_ids = _motif_text_ids(
            scope_texts,
            group_start,
        )
        end_motif_ids = _motif_text_ids(
            scope_texts,
            group_end,
        )
        semantic_ids = _semantic_text_ids(scope_texts)
        if start_motif_ids is None or end_motif_ids is None or semantic_ids is None:
            continue
        if set(start_motif_ids) & set(end_motif_ids):
            continue
        polarity_ids, power_flow_ids = semantic_ids
        annotation_ids = [*start_motif_ids, *end_motif_ids, *polarity_ids, *power_flow_ids]
        if any(len(text_by_key.get((*scope, text_id), [])) != 1 for text_id in annotation_ids):
            continue
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = "ct_polarity_reference_annotation"
        pair.evidence["ct_polarity_reference_annotation"] = {
            "line_id": line.line_id,
            "selected_side": present_side,
            "selected_candidate_id": selected_candidate_id,
            "selected_text_id": selected_text_id,
            "selected_raw_text": selected_raw,
            "endpoint_motif_text_ids": {
                "start": start_motif_ids,
                "end": end_motif_ids,
            },
            "semantic_text_ids": {
                "ct_polarity": polarity_ids,
                "power_flow": power_flow_ids,
            },
        }


def _shadow_connect_multidrop_rail_ordinary_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    lines: list[LineEntity],
) -> None:
    """Keep complete CONNECT distribution rails out of endpoint-pair audit."""

    tolerance = 0.25
    group_by_id = {group.line_group_id: group for group in line_groups}
    line_by_id = {line.line_id: line for line in lines}
    lines_by_sheet: dict[tuple[str, str], list[LineEntity]] = defaultdict(list)
    for line in lines:
        lines_by_sheet[(line.sheet_id, line.file_id)].append(line)

    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        if pair.alternative_pair_candidate_ids or pair.ambiguity_gap is not None:
            continue
        present_sides = [
            side
            for side in ("left", "right")
            if str(getattr(pair, f"{side}_value", None) or "").strip()
        ]
        if len(present_sides) != 1:
            continue
        present_side = present_sides[0]
        missing_side = "right" if present_side == "left" else "left"
        if not str(getattr(pair, f"{present_side}_text_id", None) or "").strip():
            continue
        if getattr(pair, f"{missing_side}_text_id", None) is not None:
            continue

        group = group_by_id.get(pair.line_group_id)
        if group is None or str(group.orientation or "").casefold() != "horizontal":
            continue
        member_lines = [line_by_id.get(line_id) for line_id in group.member_line_ids]
        if not member_lines or any(line is None for line in member_lines):
            continue
        group_y = (float(group.start_y) + float(group.end_y)) / 2.0
        group_min_x = min(float(group.start_x), float(group.end_x))
        group_max_x = max(float(group.start_x), float(group.end_x))
        if any(
            str(line.source_entity_type or "").upper() != "LINE"
            or str(line.layer or "").casefold() != "connect"
            or line.source_block_name is not None
            or abs(float(line.start_y) - float(line.end_y)) > tolerance
            or abs((float(line.start_y) + float(line.end_y)) / 2.0 - group_y) > tolerance
            for line in member_lines
            if line is not None
        ):
            continue

        drop_lines: list[LineEntity] = []
        drop_xs: list[float] = []
        member_ids = {str(line.line_id) for line in member_lines if line is not None}
        for line in lines_by_sheet.get((pair.sheet_id, pair.file_id), []):
            if str(line.line_id) in member_ids:
                continue
            if (
                str(line.source_entity_type or "").upper() != "LINE"
                or str(line.layer or "").casefold() != "connect"
                or line.source_block_name is not None
                or abs(float(line.start_x) - float(line.end_x)) > tolerance
                or abs(float(line.start_y) - float(line.end_y)) <= tolerance
            ):
                continue
            endpoint_touches = (
                abs(float(line.start_y) - group_y) <= tolerance,
                abs(float(line.end_y) - group_y) <= tolerance,
            )
            if sum(endpoint_touches) != 1:
                continue
            drop_x = float(line.start_x) if endpoint_touches[0] else float(line.end_x)
            if not group_min_x + tolerance < drop_x < group_max_x - tolerance:
                continue
            if any(abs(drop_x - existing) <= tolerance for existing in drop_xs):
                continue
            drop_lines.append(line)
            drop_xs.append(drop_x)
        if len(drop_xs) < 2:
            continue

        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = "connect_multidrop_rail"
        pair.evidence["connect_multidrop_rail"] = {
            "member_line_ids": sorted(member_ids),
            "interior_drop_line_ids": sorted(str(line.line_id) for line in drop_lines),
            "interior_drop_xs": sorted(round(value, 6) for value in drop_xs),
            "interior_drop_count": len(drop_xs),
        }


def _shadow_closed_tall_polyline_enclosure_ordinary_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    lines: list[LineEntity],
    texts: list[TextItem] | None = None,
) -> None:
    """Keep auxiliary closed-polyline edges as geometry evidence, not electrical pairs.

    A tall frame is self-proving geometry. A shorter frame is shadowed only when it
    duplicates one unique CONNECT claim on the same text and side; this preserves
    real open-ended CONNECT claims and all structured mappings.
    """

    line_by_id = {line.line_id: line for line in lines}
    parent_lines: dict[tuple[str, str, str], list[tuple[int, LineEntity]]] = defaultdict(list)
    for line in lines:
        if str(line.source_entity_type or "").upper() != "LWPOLYLINE":
            continue
        parent_handle, separator, segment_index = str(line.handle or "").rpartition(":")
        if not separator or not parent_handle or not segment_index.isdigit():
            continue
        parent_lines[(line.sheet_id, line.file_id, parent_handle)].append((int(segment_index), line))

    enclosure_by_line_id: dict[str, dict[str, object]] = {}
    ambiguous_enclosure_line_ids: set[str] = set()
    for (sheet_id, file_id, parent_handle), indexed_lines in parent_lines.items():
        enclosure = _closed_polyline_enclosure(indexed_lines)
        if enclosure is None:
            continue
        width = float(enclosure["width"])
        height = float(enclosure["height"])
        evidence = {
            "sheet_id": sheet_id,
            "file_id": file_id,
            "parent_handle": parent_handle,
            "parent_key": (sheet_id, file_id, parent_handle),
            "layer": enclosure["layer"],
            "width": width,
            "height": height,
            "member_line_ids": list(enclosure["member_line_ids"]),
            "min_x": float(enclosure["min_x"]),
            "min_y": float(enclosure["min_y"]),
            "max_x": float(enclosure["max_x"]),
            "max_y": float(enclosure["max_y"]),
            "is_tall": height >= 4.0 * width,
        }
        for line_id in enclosure["member_line_ids"]:
            if line_id in ambiguous_enclosure_line_ids:
                continue
            if line_id in enclosure_by_line_id:
                enclosure_by_line_id.pop(line_id, None)
                ambiguous_enclosure_line_ids.add(line_id)
                continue
            enclosure_by_line_id[line_id] = evidence

    if not enclosure_by_line_id:
        return

    group_enclosures: dict[str, dict[str, object]] = {}
    group_by_id = {group.line_group_id: group for group in line_groups}
    for group in line_groups:
        raw_member_line_ids = [str(line_id) for line_id in group.member_line_ids if str(line_id)]
        member_line_ids = set(raw_member_line_ids)
        if not member_line_ids:
            continue
        if len(raw_member_line_ids) != len(member_line_ids):
            continue
        if any(line_id not in line_by_id for line_id in member_line_ids):
            continue
        if any(
            line_by_id[line_id].sheet_id != group.sheet_id
            or line_by_id[line_id].file_id != group.file_id
            for line_id in member_line_ids
        ):
            continue
        enclosure_candidates = {
            tuple(enclosure_by_line_id[line_id]["parent_key"]): enclosure_by_line_id[line_id]
            for line_id in member_line_ids
            if line_id in enclosure_by_line_id
            and enclosure_by_line_id[line_id]["sheet_id"] == group.sheet_id
            and enclosure_by_line_id[line_id]["file_id"] == group.file_id
        }
        if not enclosure_candidates:
            continue
        enclosures = list(enclosure_candidates.values())
        reference = enclosures[0]
        if any(not _equivalent_polyline_bbox(reference, enclosure) for enclosure in enclosures[1:]):
            continue
        if len({str(enclosure["layer"]) for enclosure in enclosures}) != 1:
            continue
        enclosure_member_ids = {
            str(line_id)
            for enclosure in enclosures
            for line_id in enclosure["member_line_ids"]
        }
        if not member_line_ids.issubset(enclosure_member_ids):
            continue
        contributions: dict[tuple[str, str, str], list[LineEntity]] = defaultdict(list)
        for line_id in member_line_ids:
            enclosure = enclosure_by_line_id.get(line_id)
            if enclosure is None:
                continue
            contributions[tuple(enclosure["parent_key"])].append(line_by_id[line_id])
        repeated_edge = _repeated_closed_polyline_edge_evidence(
            group,
            contributions,
            reference,
        )
        group_enclosures[group.line_group_id] = {
            **reference,
            "parent_handles": sorted(str(key[2]) for key in enclosure_candidates),
            "parent_keys": sorted(enclosure_candidates),
            "member_line_ids": sorted(enclosure_member_ids),
            "is_tall": all(bool(enclosure["is_tall"]) for enclosure in enclosures),
            "repeated_edge": repeated_edge,
        }

    text_by_id = {text.text_id: text for text in (texts or [])}

    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        enclosure = group_enclosures.get(pair.line_group_id)
        if enclosure is None:
            continue
        if not enclosure["is_tall"]:
            repeated_edge = enclosure.get("repeated_edge")
            repeated_claim = (
                _authoritative_repeated_enclosure_half_pair(pair, group_by_id.get(pair.line_group_id))
                if isinstance(repeated_edge, dict)
                else None
            )
            if repeated_claim is not None:
                pair.evidence["ordinary_pair_shadow_reason"] = "closed_repeated_polyline_enclosure_edge"
                pair.evidence["closed_polyline_enclosure"] = {
                    "parent_handles": repeated_edge["parent_handles"],
                    "parent_count": repeated_edge["parent_count"],
                    "member_edge_line_ids": repeated_edge["member_edge_line_ids"],
                    "layer": repeated_edge["layer"],
                    "width": enclosure["width"],
                    "height": enclosure["height"],
                    **repeated_claim,
                }
            else:
                primary = _unique_nearby_connect_claim(
                    pair,
                    enclosure,
                    pairs,
                    group_by_id,
                    line_by_id,
                    text_by_id,
                )
                if primary is None:
                    continue
                pair.evidence["ordinary_pair_shadow_reason"] = "closed_polyline_duplicate_enclosure_edge"
                pair.evidence["closed_polyline_enclosure"] = {
                    "parent_handles": enclosure["parent_handles"],
                    "width": enclosure["width"],
                    "height": enclosure["height"],
                    "canonical_pair_id": primary.pair_id,
                    "canonical_line_group_id": primary.line_group_id,
                }
        else:
            pair.evidence["ordinary_pair_shadow_reason"] = "closed_tall_polyline_enclosure_edge"
            pair.evidence["closed_polyline_enclosure"] = {
                "parent_handle": enclosure["parent_handles"][0],
                "width": enclosure["width"],
                "height": enclosure["height"],
            }
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True


def _equivalent_polyline_bbox(left: dict[str, object], right: dict[str, object]) -> bool:
    """Treat duplicate parent polylines as one frame only at CAD precision."""

    tolerance = 0.25
    try:
        coordinates = [
            (float(left[key]), float(right[key]))
            for key in ("min_x", "min_y", "max_x", "max_y")
        ]
    except (KeyError, TypeError, ValueError):
        return False
    return all(
        math.isfinite(left_value)
        and math.isfinite(right_value)
        and abs(left_value - right_value) <= tolerance
        for left_value, right_value in coordinates
    )


def _repeated_closed_polyline_edge_evidence(
    group: LineGroup,
    contributions: dict[tuple[str, str, str], list[LineEntity]],
    enclosure: dict[str, object],
) -> dict[str, object] | None:
    """Prove that at least three closed parents contribute one coincident edge."""

    tolerance = 0.25
    if len(contributions) < 3 or any(len(lines) != 1 for lines in contributions.values()):
        return None
    edges = [lines[0] for lines in contributions.values()]
    if len(edges) != len(contributions):
        return None
    if any(
        edge.sheet_id != group.sheet_id
        or edge.file_id != group.file_id
        or str(edge.source_entity_type or "").upper() != "LWPOLYLINE"
        or edge.source_block_name is not None
        for edge in edges
    ):
        return None
    layers = {str(edge.layer or "") for edge in edges}
    if len(layers) != 1 or not next(iter(layers)):
        return None
    group_layers = {str(layer or "") for layer in group.layer_hints if str(layer or "")}
    if group_layers and group_layers != layers:
        return None
    orientation = str(group.orientation or "").casefold()
    if orientation not in {"horizontal", "vertical"}:
        return None
    group_coordinates = (
        float(group.start_x),
        float(group.start_y),
        float(group.end_x),
        float(group.end_y),
    )
    if not all(math.isfinite(value) for value in group_coordinates):
        return None
    group_min_axis, group_max_axis = sorted(
        (group_coordinates[0], group_coordinates[2])
        if orientation == "horizontal"
        else (group_coordinates[1], group_coordinates[3])
    )
    group_cross_axis = (
        (group_coordinates[1] + group_coordinates[3]) / 2.0
        if orientation == "horizontal"
        else (group_coordinates[0] + group_coordinates[2]) / 2.0
    )
    for edge in edges:
        edge_coordinates = (
            float(edge.start_x),
            float(edge.start_y),
            float(edge.end_x),
            float(edge.end_y),
        )
        if not all(math.isfinite(value) for value in edge_coordinates):
            return None
        if orientation == "horizontal":
            edge_min_axis, edge_max_axis = sorted((edge_coordinates[0], edge_coordinates[2]))
            edge_cross_values = (edge_coordinates[1], edge_coordinates[3])
        else:
            edge_min_axis, edge_max_axis = sorted((edge_coordinates[1], edge_coordinates[3]))
            edge_cross_values = (edge_coordinates[0], edge_coordinates[2])
        if (
            abs(edge_min_axis - group_min_axis) > tolerance
            or abs(edge_max_axis - group_max_axis) > tolerance
            or any(abs(value - group_cross_axis) > tolerance for value in edge_cross_values)
        ):
            return None
    try:
        width = float(enclosure["width"])
        height = float(enclosure["height"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(width) or not math.isfinite(height):
        return None
    return {
        "parent_handles": sorted(key[2] for key in contributions),
        "parent_count": len(contributions),
        "member_edge_line_ids": sorted(str(edge.line_id) for edge in edges),
        "layer": next(iter(layers)),
    }


def _authoritative_repeated_enclosure_half_pair(
    pair: Pair,
    group: LineGroup | None,
) -> dict[str, object] | None:
    """Require complete Pair/evidence identity before repeated-frame shadowing."""

    if group is None or pair.status != "review":
        return None
    if pair.sheet_id != group.sheet_id or pair.file_id != group.file_id:
        return None
    evidence = pair.evidence or {}
    if (
        evidence.get("ordinary_pair_eligible") is False
        or evidence.get("ordinary_pair_shadow_only") is True
        or evidence.get("ordinary_pair_shadow_reason")
        or pair.alternative_pair_candidate_ids
        or pair.ambiguity_gap is not None
    ):
        return None
    present_sides = [
        side
        for side in ("left", "right")
        if isinstance(getattr(pair, f"{side}_value", None), str)
        and bool(getattr(pair, f"{side}_value"))
    ]
    if len(present_sides) != 1:
        return None
    present_side = present_sides[0]
    absent_side = "right" if present_side == "left" else "left"
    value = getattr(pair, f"{present_side}_value")
    text_id = getattr(pair, f"{present_side}_text_id")
    candidate_id = getattr(pair, f"{present_side}_candidate_id")
    if not isinstance(value, str) or not value or value.strip() != value:
        return None
    if (
        not isinstance(text_id, str)
        or not text_id
        or text_id.strip() != text_id
        or text_id.casefold() in {"nan", "none", "null"}
    ):
        return None
    if not isinstance(candidate_id, str) or not candidate_id or candidate_id.strip() != candidate_id:
        return None
    if any(
        getattr(pair, f"{absent_side}_{field}") is not None
        for field in ("value", "text_id", "candidate_id")
    ):
        return None
    if (
        not isinstance(pair.selected_pair_candidate_id, str)
        or not pair.selected_pair_candidate_id
        or pair.selected_pair_candidate_id.strip() != pair.selected_pair_candidate_id
    ):
        return None
    if (
        evidence.get("pair_kind") != "ordinary_pair"
        or evidence.get("line_orientation") != group.orientation
        or evidence.get("selected_pair_candidate_id") != pair.selected_pair_candidate_id
        or evidence.get(f"selected_{present_side}_candidate_id") != candidate_id
        or evidence.get(f"selected_{present_side}_text_id") != text_id
        or evidence.get(f"selected_{present_side}_raw_text") != value
        or evidence.get(f"selected_{present_side}_is_derived_numeric") is not False
        or evidence.get(f"selected_{present_side}_source_block_name") is not None
        or any(
            evidence.get(f"selected_{absent_side}_{field}") is not None
            for field in ("candidate_id", "text_id", "raw_text", "channel", "source_block_name")
        )
        or evidence.get("alternative_pair_candidate_ids") != []
    ):
        return None
    score_breakdown = evidence.get("score_breakdown")
    if not isinstance(score_breakdown, dict) or score_breakdown.get("ambiguity_gap") is not None:
        return None
    line_start = evidence.get("line_start")
    line_end = evidence.get("line_end")
    if not (
        isinstance(line_start, list)
        and len(line_start) == 2
        and isinstance(line_end, list)
        and len(line_end) == 2
    ):
        return None
    try:
        evidence_coordinates = tuple(float(value) for value in (*line_start, *line_end))
    except (TypeError, ValueError):
        return None
    group_coordinates = (group.start_x, group.start_y, group.end_x, group.end_y)
    if any(
        not math.isfinite(actual)
        or abs(actual - float(expected)) > 0.25
        for actual, expected in zip(evidence_coordinates, group_coordinates)
    ):
        return None
    return {
        "shared_side": present_side,
        "shared_value": value,
        "shared_text_id": text_id,
    }


def _pair_claims(pair: Pair) -> set[tuple[str, str, str]]:
    """Return text/value/side claims that can safely identify a duplicate edge."""

    evidence = pair.evidence or {}
    claims: set[tuple[str, str, str]] = set()
    for side in ("left", "right"):
        value = getattr(pair, f"{side}_value", None)
        other = getattr(pair, "right_value" if side == "left" else "left_value", None)
        text_ids = {
            getattr(pair, f"{side}_text_id", None),
            evidence.get(f"selected_{side}_text_id"),
        }
        if value is None or other is not None:
            continue
        for text_id in text_ids:
            normalized_text_id = text_id.strip() if isinstance(text_id, str) else ""
            if normalized_text_id and normalized_text_id.casefold() not in {"nan", "none", "null"}:
                claims.add((normalized_text_id, str(value), side))
    return claims


def _unique_nearby_connect_claim(
    frame_pair: Pair,
    enclosure: dict[str, object],
    pairs: list[Pair],
    group_by_id: dict[str, LineGroup],
    line_by_id: dict[str, LineEntity],
    text_by_id: dict[str, TextItem],
) -> Pair | None:
    claims = _pair_claims(frame_pair)
    if not claims:
        return None
    matching: list[tuple[Pair, float, float]] = []
    for candidate in pairs:
        if candidate is frame_pair or candidate.pair_kind != "ordinary_pair":
            continue
        if candidate.evidence.get("ordinary_pair_eligible") is False:
            continue
        if candidate.alternative_pair_candidate_ids or candidate.ambiguity_gap is not None:
            continue
        if candidate.sheet_id != frame_pair.sheet_id or candidate.file_id != frame_pair.file_id:
            continue
        if not claims.intersection(_pair_claims(candidate)):
            continue
        group = group_by_id.get(candidate.line_group_id)
        if group is None or str(group.orientation or "").casefold() != "horizontal":
            continue
        member_lines = [line_by_id[line_id] for line_id in group.member_line_ids if line_id in line_by_id]
        if not member_lines or not all(
            str(line.layer or "").casefold() == "connect"
            and str(line.source_entity_type or "").upper() == "LINE"
            for line in member_lines
        ):
            continue
        group_min_x = min(float(group.start_x), float(group.end_x))
        group_max_x = max(float(group.start_x), float(group.end_x))
        group_width = group_max_x - group_min_x
        frame_width = float(enclosure["width"])
        overlap = max(
            0.0,
            min(group_max_x, float(enclosure["max_x"]))
            - max(group_min_x, float(enclosure["min_x"])),
        )
        if min(group_width, frame_width) <= 0.0:
            continue
        overlap_ratio = overlap / min(group_width, frame_width)
        span_ratio = min(group_width, frame_width) / max(group_width, frame_width)
        if group_width > frame_width + 0.25 or overlap_ratio < 0.95 or span_ratio < 0.75:
            continue
        group_y = (float(group.start_y) + float(group.end_y)) / 2.0
        frame_y_delta = min(
            abs(group_y - float(enclosure["min_y"])),
            abs(group_y - float(enclosure["max_y"])),
        )
        heights = [
            float(text_by_id[text_id].height)
            for text_id, _, _ in claims
            if text_id in text_by_id and float(text_by_id[text_id].height) > 0.0
        ]
        if not heights:
            continue
        y_tolerance = min(3.25, max(1.5, 1.25 * max(heights)))
        if frame_y_delta > y_tolerance:
            continue
        matching.append((candidate, overlap_ratio, frame_y_delta))
    if len(matching) != 1:
        return None
    primary, overlap_ratio, frame_y_delta = matching[0]
    primary.evidence.setdefault("auxiliary_enclosure_matches", []).append(
        {
            "frame_pair_id": frame_pair.pair_id,
            "overlap_ratio": round(overlap_ratio, 4),
            "span_ratio": round(span_ratio, 4),
            "y_delta": round(frame_y_delta, 4),
        }
    )
    return primary


def _closed_tall_polyline_enclosure(
    indexed_lines: list[tuple[int, LineEntity]],
) -> tuple[float, float, list[str]] | None:
    enclosure = _closed_polyline_enclosure(indexed_lines)
    if enclosure is None or float(enclosure["height"]) < 4.0 * float(enclosure["width"]):
        return None

    return (
        float(enclosure["width"]),
        float(enclosure["height"]),
        list(enclosure["member_line_ids"]),
    )


def _closed_polyline_enclosure(
    indexed_lines: list[tuple[int, LineEntity]],
) -> dict[str, object] | None:
    if len(indexed_lines) != 4 or {index for index, _ in indexed_lines} != {0, 1, 2, 3}:
        return None
    lines = [line for _, line in sorted(indexed_lines)]
    if len({str(line.layer or "") for line in lines}) != 1:
        return None

    endpoint_counts: dict[tuple[float, float], int] = defaultdict(int)
    for line in lines:
        coordinates = (
            float(line.start_x),
            float(line.start_y),
            float(line.end_x),
            float(line.end_y),
        )
        if not all(math.isfinite(value) for value in coordinates):
            return None
        start = (round(float(line.start_x), 6), round(float(line.start_y), 6))
        end = (round(float(line.end_x), 6), round(float(line.end_y), 6))
        if start == end or not (start[0] == end[0] or start[1] == end[1]):
            return None
        endpoint_counts[start] += 1
        endpoint_counts[end] += 1
    if len(endpoint_counts) != 4 or set(endpoint_counts.values()) != {2}:
        return None

    xs = {point[0] for point in endpoint_counts}
    ys = {point[1] for point in endpoint_counts}
    if len(xs) != 2 or len(ys) != 2:
        return None
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    if width <= 0.0 or height <= 0.0:
        return None
    return {
        "layer": str(lines[0].layer or ""),
        "width": width,
        "height": height,
        "member_line_ids": [line.line_id for line in lines],
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
    }


_SIGNAL_ALARM_SHADOW_PATTERNS = (
    re.compile(r"信号回路|Signal\s*circuit", re.IGNORECASE),
    re.compile(r"电度表告警|Watt-?hour\s*meter\s*alarm", re.IGNORECASE),
    re.compile(r"辅助电源失电|Air\s*switch\s*open\s*alarm|空开断开告警", re.IGNORECASE),
    # Generic dry-contact / device alarm face labels on 信号回路图 sheets.
    re.compile(r"失电告警|失步告警|异常告警|告警回路", re.IGNORECASE),
)


def _sheet_has_signal_alarm_cues(page: SheetRecord, texts: list[TextItem] | None = None) -> bool:
    """True when page texts/title show meter alarm / signal-circuit role (not serial media)."""
    if texts:
        for text in texts:
            if text.sheet_id != page.sheet_id:
                continue
            raw = f"{text.normalized_text or ''} {text.text or ''}"
            if any(pattern.search(raw) for pattern in _SIGNAL_ALARM_SHADOW_PATTERNS):
                return True
    # Title/filename assist: e.g. "05 信号回路图.dwg" without in-body "信号回路" text.
    blob = f"{page.sheet_title or ''} {page.filename or ''}"
    return any(pattern.search(blob) for pattern in _SIGNAL_ALARM_SHADOW_PATTERNS)


def _shadow_signal_alarm_ordinary_pairs(
    pairs: list[Pair],
    pages: list[SheetRecord],
    texts: list[TextItem] | None = None,
) -> None:
    """Compatibility no-op: page-level alarm cues cannot prove a pair is noise."""
    _ = pairs, pages, texts


_PANEL_SILKSCREEN_PAGE_CUE = re.compile(
    r"通信|COMMUNICATION|告警|ALARM|电度表",
    re.IGNORECASE,
)
_PANEL_SILKSCREEN_DIGIT = re.compile(r"^\d{1,2}$")


def _shadow_repeated_panel_silkscreen_ordinary_pairs(
    pairs: list[Pair],
    pages: list[SheetRecord],
    texts: list[TextItem],
    blocks: list[BlockRecord],
) -> None:
    """Ignore numeric silkscreen anchored to a repeated communication-panel lattice.

    A title cue is only routing context. Authority comes from repeated block columns
    plus DIM numeric labels at the same insertion rows; real two-sided pairs and
    block-owned endpoint text remain audit-visible.
    """

    page_map = {
        page.sheet_id: page
        for page in pages
        if page.route_target == "WireDiagramExtractor"
        and page.sheet_category == "二次原理图"
        and _PANEL_SILKSCREEN_PAGE_CUE.search(
            f"{page.sheet_title or ''} {page.filename or ''}"
        )
    }
    if not page_map:
        return

    blocks_by_sheet: dict[str, list[BlockRecord]] = defaultdict(list)
    for block in blocks:
        if block.sheet_id in page_map:
            blocks_by_sheet[block.sheet_id].append(block)

    silkscreen_text_ids: set[tuple[str, str]] = set()
    for sheet_id, sheet_blocks in blocks_by_sheet.items():
        columns: dict[int, set[int]] = defaultdict(set)
        for block in sheet_blocks:
            name = str(block.name or "").lower()
            if "title" in name or "signblock" in name:
                continue
            columns[round(block.insert_x / 2.5)].add(round(block.insert_y / 2.0))
        frequent_columns = {column for column, rows in columns.items() if len(rows) >= 4}
        if not frequent_columns:
            continue
        anchors = [
            block
            for block in sheet_blocks
            if round(block.insert_x / 2.5) in frequent_columns
        ]
        anchor_rows = {round(block.insert_y / 2.0) for block in anchors}
        if len(anchor_rows) < 4:
            continue

        for text in texts:
            if text.sheet_id != sheet_id:
                continue
            token = str(text.normalized_text or text.text or "").strip()
            if str(text.layer or "").upper() != "DIM":
                continue
            if text.source_block_name or not _PANEL_SILKSCREEN_DIGIT.fullmatch(token):
                continue
            if any(
                abs(text.insert_x - block.insert_x) <= 4.0
                and abs(text.insert_y - block.insert_y) <= 2.0
                for block in anchors
            ):
                silkscreen_text_ids.add((sheet_id, text.text_id))

    if not silkscreen_text_ids:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair" or pair.sheet_id not in page_map:
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        sides = [value for value in (pair.left_value, pair.right_value) if value]
        if len(sides) != 1 or not _PANEL_SILKSCREEN_DIGIT.fullmatch(str(sides[0])):
            continue
        selected_ids = {
            (pair.sheet_id, text_id)
            for text_id in (pair.left_text_id, pair.right_text_id)
            if text_id
        }
        if not selected_ids.intersection(silkscreen_text_ids):
            continue
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = "repeated_panel_numeric_silkscreen"


_EQUIPMENT_PANEL_IGNORE_FAMILY = "communication.equipment_panel_ignored.v1"
_PANEL_MARK_SCOPE_PATTERN = re.compile(r"^\d+(?:-\d+)+n$", re.IGNORECASE)
_PANEL_MARK_BARE_DIGIT_PATTERN = re.compile(r"^\d{1,3}$")
_FIREWALL_PANEL_MODEL_PATTERN = re.compile(
    r"^(?:NGFW[A-Z0-9-]*|HX-SFW-[A-Z0-9-]+)$",
    re.IGNORECASE,
)


def _panel_model_label_matches(row: dict[str, object], value: object) -> bool:
    raw = str(value or "").strip()
    canonical_value = re.sub(r"[\W_]+", "", raw.casefold())
    canonical_definition = re.sub(
        r"[\W_]+", "", str(row.get("definition_name") or "").casefold()
    )
    if canonical_definition and canonical_value == canonical_definition:
        return True
    if row.get("matched_family_rule_id") != "firewall-eth-usb-optical-power-panel-v1":
        return False
    return bool(
        _FIREWALL_PANEL_MODEL_PATTERN.fullmatch(raw)
        and re.search(r"\d", raw)
    )


def mark_ignored_equipment_panel_ordinary_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    texts: list[TextItem],
    lines: list[LineEntity],
    symbol_port_definition_proposals: list[dict[str, object]],
) -> None:
    """Consume geometry-proven whole-panel IGNORE decisions at pair level.

    Symbol proposals are produced before route extraction, but historically their
    ``communication.equipment_panel_ignored.v1`` decision was only persisted as
    an artifact.  That left panel-owned virtual lines and the short MARK callout
    above a panel in the ordinary terminal graph.  This pass binds only complete
    geometry proposals back to those pairs; it does not infer IGNORE from a block
    name or from a bare numeric value.
    """

    from dwg_audit.audit.symbol_port_proposal import apply_human_symbol_policy_to_proposal_row

    evaluated_rows: list[dict[str, object]] = []
    for source_row in symbol_port_definition_proposals:
        row = dict(source_row)
        if not row.get("family_id") or not row.get("behavior_mode"):
            row = apply_human_symbol_policy_to_proposal_row(row)
        evaluated_rows.append(row)
    panel_rows = [
        row
        for row in evaluated_rows
        if row.get("family_id") == _EQUIPMENT_PANEL_IGNORE_FAMILY
        and row.get("behavior_mode") == "IGNORE"
        and row.get("allow_port_emission") is False
        and row.get("allow_external_attachment") is False
    ]
    if not panel_rows:
        return

    def normalized(value: object) -> str:
        return str(value or "").strip().casefold()

    line_by_id = {line.line_id: line for line in lines}
    group_by_id = {group.line_group_id: group for group in line_groups}
    text_by_id = {text.text_id: text for text in texts}
    lines_by_sheet_and_definition: dict[tuple[str, str], list[LineEntity]] = defaultdict(list)
    mark_texts_by_sheet: dict[str, list[TextItem]] = defaultdict(list)
    for line in lines:
        definition_name = normalized(line.source_block_name)
        if definition_name:
            lines_by_sheet_and_definition[(line.sheet_id, definition_name)].append(line)
    for text_item in texts:
        if (
            not text_item.source_block_name
            and str(text_item.layer or "").strip().upper() == "MARK"
        ):
            mark_texts_by_sheet[text_item.sheet_id].append(text_item)

    panel_instances_by_key: dict[
        tuple[str, str], list[tuple[str, dict[str, object]]]
    ] = defaultdict(list)
    panel_bboxes_by_sheet: dict[
        str,
        list[tuple[float, float, float, float, str, dict[str, object]]],
    ] = defaultdict(list)

    for row in panel_rows:
        sheet_id = str(row.get("sheet_id") or "")
        definition_name = normalized(row.get("definition_name"))
        if not sheet_id or not definition_name:
            continue
        handles = row.get("instance_handles")
        if not isinstance(handles, list):
            continue
        for raw_handle in handles:
            instance_handle = str(raw_handle or "").strip()
            if not instance_handle:
                continue
            panel_instances_by_key[(sheet_id, definition_name)].append((instance_handle, row))
            instance_lines = [
                line
                for line in lines_by_sheet_and_definition.get(
                    (sheet_id, definition_name), []
                )
                if (
                    line.handle == instance_handle
                    or line.handle.startswith(f"{instance_handle}:")
                )
            ]
            if not instance_lines:
                continue
            panel_bboxes_by_sheet[sheet_id].append(
                (
                    min(line.bbox_min_x for line in instance_lines),
                    min(line.bbox_min_y for line in instance_lines),
                    max(line.bbox_max_x for line in instance_lines),
                    max(line.bbox_max_y for line in instance_lines),
                    instance_handle,
                    row,
                )
            )

    panel_sheets = {sheet_id for sheet_id, _ in panel_instances_by_key}

    def selected_texts(pair: Pair) -> list[TextItem]:
        evidence = pair.evidence or {}
        ids = {
            pair.left_text_id,
            pair.right_text_id,
            evidence.get("selected_left_text_id"),
            evidence.get("selected_right_text_id"),
        }
        return [text_by_id[text_id] for text_id in ids if text_id in text_by_id]

    def approved_owner(
        *, sheet_id: str, definition_name: object, entity_handle: object
    ) -> tuple[dict[str, object], str] | None:
        normalized_name = normalized(definition_name)
        handle = str(entity_handle or "").strip()
        if not normalized_name or not handle:
            return None
        for instance_handle, row in panel_instances_by_key.get(
            (sheet_id, normalized_name), []
        ):
            if handle == instance_handle or handle.startswith(f"{instance_handle}:"):
                return row, instance_handle
        return None

    def mark(
        pair: Pair,
        row: dict[str, object],
        instance_handle: str,
        reason: str,
    ) -> None:
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = reason
        pair.evidence["ignored_panel_family_id"] = _EQUIPMENT_PANEL_IGNORE_FAMILY
        pair.evidence["ignored_panel_definition_name"] = row.get("definition_name")
        pair.evidence["ignored_panel_definition_fingerprint"] = (
            row.get("definition_fingerprint") or row.get("fingerprint")
        )
        pair.evidence["ignored_panel_instance_handle"] = instance_handle
        pair.evidence["ignored_panel_family_rule_id"] = row.get("matched_family_rule_id")

    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        sheet_id = str(pair.sheet_id or "")
        if sheet_id not in panel_sheets:
            continue

        # A pair is panel-owned when either its selected text or one of its
        # member line entities belongs to an explicitly approved instance.
        selected_owner = next(
            (
                owner
                for text_item in selected_texts(pair)
                if (
                    owner := approved_owner(
                        sheet_id=sheet_id,
                        definition_name=text_item.source_block_name,
                        entity_handle=text_item.handle,
                    )
                )
            ),
            None,
        )
        if selected_owner is not None:
            row, instance_handle = selected_owner
            mark(
                pair,
                row,
                instance_handle,
                "ignored_equipment_panel_geometry",
            )
            continue
        group = group_by_id.get(pair.line_group_id)
        if group is None:
            continue
        members = [line_by_id[line_id] for line_id in group.member_line_ids if line_id in line_by_id]
        member_owner = next(
            (
                owner
                for line in members
                if (
                    owner := approved_owner(
                        sheet_id=sheet_id,
                        definition_name=line.source_block_name,
                        entity_handle=line.handle,
                    )
                )
            ),
            None,
        )
        if member_owner is not None:
            row, instance_handle = member_owner
            mark(
                pair,
                row,
                instance_handle,
                "ignored_equipment_panel_geometry",
            )
            continue

        # Panel placement callouts are free MARK geometry immediately above the
        # actual panel.  Require both a model label and a scoped n-reference so
        # a normal MARK-layer terminal or wire cannot inherit panel IGNORE.
        layers = {str(layer or "").strip().upper() for layer in group.layer_hints}
        if layers != {"MARK"} or group.orientation != "horizontal":
            continue
        values = [value for value in (pair.left_value, pair.right_value) if value]
        raw_values = [
            value
            for value in (
                pair.left_value,
                pair.right_value,
                pair.evidence.get("selected_left_raw_text"),
                pair.evidence.get("selected_right_raw_text"),
            )
            if value
        ]
        if len(values) != 1 or not any(
            _PANEL_MARK_BARE_DIGIT_PATTERN.fullmatch(str(value).strip()) for value in raw_values
        ):
            continue
        group_min_x, group_max_x = sorted((group.start_x, group.end_x))
        group_y = (group.start_y + group.end_y) / 2.0
        for min_x, min_y, max_x, max_y, instance_handle, row in panel_bboxes_by_sheet.get(sheet_id, []):
            if group_y < max_y or group_y - max_y > 30.0:
                continue
            if group_max_x < min_x or group_min_x > max_x:
                continue
            nearby = [
                text
                for text in mark_texts_by_sheet.get(sheet_id, [])
                if text.insert_y >= group_y - 6.0
                and text.insert_y <= group_y + 2.0
                and text.bbox_max_x >= group_min_x - 2.0
                and text.bbox_min_x <= group_max_x + 8.0
            ]
            scope_texts = [
                text
                for text in nearby
                if _PANEL_MARK_SCOPE_PATTERN.fullmatch(str(text.normalized_text or text.text or "").strip())
            ]
            model_texts = [
                text
                for text in nearby
                if _panel_model_label_matches(
                    row, text.normalized_text or text.text
                )
            ]
            if scope_texts and model_texts:
                mark(
                    pair,
                    row,
                    instance_handle,
                    "ignored_equipment_panel_mark_callout",
                )
                break


# Device front-panel silkscreen (human-adjudicated): HMC pin grids with HD*/BCD*
# labels are artwork, not cross-page terminal mappings.
_HMC_SILKSCREEN_TITLE_PATTERN = re.compile(
    r"HMC(?:[-\s]?\w+)?\s*(?:wiring\s*diagram|panel|接线图|面板)",
    re.IGNORECASE,
)
_HMC_HD_PIN_PATTERN = re.compile(r"^HD\d+$", re.IGNORECASE)
_HMC_BCD_LABEL_PATTERN = re.compile(r"^BCD(\s+\d+|\s*COM)?$", re.IGNORECASE)
_HMC_PIN_DIGIT_PATTERN = re.compile(r"^\d{1,3}$")
_HMC_COMPONENT_ENDPOINT_PATTERN = re.compile(
    r"(?:KLP|GD|n\d{2,}|\d+-\d+[A-Za-z])",
    re.IGNORECASE,
)


def _sheet_has_hmc_silkscreen_cues(
    page: SheetRecord,
    texts: list[TextItem] | None = None,
) -> bool:
    """True when page texts show an HMC device-panel pin lattice (silkscreen)."""
    title_hits = 0
    hd_hits = 0
    bcd_hits = 0
    blob = f"{page.sheet_title or ''} {page.filename or ''}"
    if _HMC_SILKSCREEN_TITLE_PATTERN.search(blob):
        title_hits = 1
    if texts:
        for text in texts:
            if text.sheet_id != page.sheet_id:
                continue
            raw = f"{text.normalized_text or ''} {text.text or ''}".strip()
            token = (text.normalized_text or text.text or "").strip()
            if _HMC_SILKSCREEN_TITLE_PATTERN.search(raw):
                title_hits += 1
            if _HMC_HD_PIN_PATTERN.fullmatch(token):
                hd_hits += 1
            if _HMC_BCD_LABEL_PATTERN.fullmatch(token) or re.search(
                r"BCD\s*(?:code|COM|\d+)",
                raw,
                re.IGNORECASE,
            ):
                bcd_hits += 1
    # Title alone is enough (human-adjudicated HMC panels). Dense HD+BCD lattice
    # without title also qualifies so unlabeled variants still shadow.
    if title_hits:
        return True
    return hd_hits >= 6 and bcd_hits >= 2


def _pair_is_hmc_silkscreen_pin_stub(pair: Pair) -> bool:
    """Ordinary stub around HD/BCD/bare pin numbers — not a real terminal pair."""
    evidence = pair.evidence or {}
    left_raw = str(evidence.get("selected_left_raw_text") or "").strip()
    right_raw = str(evidence.get("selected_right_raw_text") or "").strip()
    left_value = str(pair.left_value or "").strip()
    right_value = str(pair.right_value or "").strip()

    for raw in (left_raw, right_raw):
        if not raw:
            continue
        if _HMC_HD_PIN_PATTERN.fullmatch(raw):
            return True
        if _HMC_BCD_LABEL_PATTERN.fullmatch(raw) or raw.upper().startswith("BCD"):
            return True

    # Keep real component endpoints (KLP/GD/n###) out of the silkscreen mask.
    for raw in (left_raw, right_raw, left_value, right_value):
        if raw and _HMC_COMPONENT_ENDPOINT_PATTERN.search(raw):
            return False

    orientation = str(evidence.get("line_orientation") or "").lower()
    if orientation not in {"vertical", "horizontal", "grid", ""}:
        return False

    # Empty both sides: pure pin-cell geometry with no terminal text.
    if not left_value and not right_value:
        return True

    # Single-sided or dual bare pin digits (1..999) on silkscreen lattice stubs.
    sides = [value for value in (left_value, right_value) if value]
    if sides and all(_HMC_PIN_DIGIT_PATTERN.fullmatch(value) for value in sides):
        return True
    return False


def _shadow_hmc_silkscreen_ordinary_pairs(
    pairs: list[Pair],
    pages: list[SheetRecord],
    texts: list[TextItem] | None = None,
) -> None:
    """Shadow HMC device-panel pin-grid ordinary pairs (silkscreen, not terminals).

    Human adjudication: HMC pin grids are front-panel artwork. Keep pairs for
    graph/review assist, but exclude them from ordinary terminal audit and
    cross-page reciprocal rules.
    """
    hmc_sheets = {
        page.sheet_id
        for page in pages
        if page.route_target == "ComponentDiagramExtractor"
        and _sheet_has_hmc_silkscreen_cues(page, texts)
    }
    if not hmc_sheets:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.sheet_id not in hmc_sheets:
            continue
        if pair.evidence.get("ordinary_pair_eligible") is False:
            continue
        if not _pair_is_hmc_silkscreen_pin_stub(pair):
            continue
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = "hmc_panel_silkscreen"


def _shadow_component_long_bare_digit_ordinary_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    pages: list[SheetRecord],
) -> None:
    """Compatibility no-op: line length plus one digit is not IGNORE authority."""
    _ = pairs, line_groups, pages


def _shadow_external_designator_derived_ordinary_pairs(
    pairs: list[Pair],
    pages: list[SheetRecord],
) -> None:
    """Compatibility no-op: CD/GD/ZK names are valid endpoint evidence."""
    _ = pairs, pages


_XJDZ_DEFINITION_PATTERN = re.compile(r"^XJDZ[A-Za-z0-9._-]*$", re.IGNORECASE)
_XJDZ_HIERARCHICAL_ENDPOINT_PATTERN = re.compile(
    r"^\d+(?:-\d+)+[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*$",
    re.IGNORECASE,
)


def _promote_xjdz_structural_component_pairs(
    pairs: list[Pair],
    line_groups: list[LineGroup],
    texts: list[TextItem],
    lines: list[LineEntity],
) -> None:
    """Preserve XJDZ block-terminal identity instead of bare pin digits.

    XJDZ connector drawings place numeric native pins on definition-owned
    BORDER routes.  The route is structural mapping evidence, never authority
    for conductivity between different component pins.
    """

    text_by_id = {text.text_id: text for text in texts}
    line_by_id = {line.line_id: line for line in lines}
    groups_by_id = {group.line_group_id: group for group in line_groups}
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair" or pair.status != "review":
            continue
        group = groups_by_id.get(pair.line_group_id)
        if group is None:
            continue
        definition_names = sorted(
            {
                str(line_by_id[line_id].source_block_name or "").strip()
                for line_id in group.member_line_ids
                if line_id in line_by_id
                and _XJDZ_DEFINITION_PATTERN.fullmatch(
                    str(line_by_id[line_id].source_block_name or "").strip()
                )
            }
        )
        if not definition_names:
            continue
        left_text = text_by_id.get(pair.left_text_id or "")
        right_text = text_by_id.get(pair.right_text_id or "")
        if left_text is None or right_text is None:
            continue
        pin_definitions = {
            str(text.source_block_name or "").strip()
            for text in (left_text, right_text)
            if str(text.normalized_text or text.text or "").strip().strip("@&").strip().isdigit()
            and str(text.source_block_name or "").strip() in definition_names
        }
        if len(pin_definitions) == 1:
            definition_name = next(iter(pin_definitions))
        elif len(definition_names) == 1:
            definition_name = definition_names[0]
        else:
            continue
        instance_handles = sorted(
            {
                str(line_by_id[line_id].handle or "").split(":VIRTUAL:", 1)[0]
                for line_id in group.member_line_ids
                if line_id in line_by_id
                and str(line_by_id[line_id].source_block_name or "").strip().casefold()
                == definition_name.casefold()
                and str(line_by_id[line_id].handle or "").strip()
            }
        )
        if len(instance_handles) != 1:
            continue
        left_value = _xjdz_structural_endpoint_value(left_text, definition_name)
        right_value = _xjdz_structural_endpoint_value(right_text, definition_name)
        if left_value is None or right_value is None:
            continue
        if left_value[1] == "native_pin" and right_value[1] == "native_pin":
            continue

        pair.left_value = left_value[0]
        pair.right_value = right_value[0]
        pair.pair_key = f"{pair.left_value}->{pair.right_value}"
        pair.confidence = 0.97
        pair.confidence_bucket = "high"
        pair.status = "pass"
        pair.rationale = (
            "XJDZ structural terminal mapping: preserve full endpoint and "
            "definition-owned native pin identity; no internal union."
        )
        pair.alternative_pair_candidate_ids = []
        pair.pair_kind = "component_mapping"
        pair.evidence.update(
            {
                "source": "component_mapping",
                "pair_kind": "component_mapping",
                "component_submode": "xjdz_structural_terminal",
                "xjdz_definition_name": definition_name,
                "xjdz_instance_handles": instance_handles,
                "left_structural_role": left_value[1],
                "right_structural_role": right_value[1],
                "internal_connectivity_inferred": False,
                "electrical_union_eligible": False,
                "ordinary_pair_eligible": False,
            }
        )


def _xjdz_structural_endpoint_value(
    text: TextItem,
    definition_name: str,
) -> tuple[str, str] | None:
    cleaned = str(text.normalized_text or text.text or "").strip().strip("@&").strip()
    if (
        str(text.source_block_name or "").strip().casefold() == definition_name.casefold()
        and cleaned.isdigit()
    ):
        return (f"{definition_name}:{cleaned}", "native_pin")
    pieces = [piece.strip() for piece in cleaned.split(",")]
    if pieces and all(_XJDZ_HIERARCHICAL_ENDPOINT_PATTERN.fullmatch(piece) for piece in pieces):
        return (",".join(pieces), "external_endpoint")
    return None


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
            "spmu_signal_panel_row_mapping",
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
    if "spmu_signal_panel_row_mapping" in covered_reasons:
        return (
            "Covered by spmu_signal_panel_row_mapping; instance-qualified SPMU row number "
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
    """Shadow ordinary pairs restating terminal_header_table middle/side geometry.

    High-confidence table_mapping pairs own header+row composite keys. Bare
    ordinary digit pairs (e.g. 10→519 from middle 10 + derived 1n519) must not
    flood R-PAIR-LOW-CONFIDENCE once those texts are covered.
    """
    covered_text_ids = _terminal_header_table_text_ids(table_mappings)
    if not covered_text_ids:
        return
    for pair in pairs:
        if pair.pair_kind != "ordinary_pair":
            continue
        if pair.status == "discard":
            continue
        if not _pair_uses_any_selected_text_id(pair, covered_text_ids):
            continue

        uses_prefixed = _uses_derived_prefixed_terminal_endpoint(pair)
        restates_middle_row = _is_terminal_header_middle_row_restatement(pair)
        if not uses_prefixed and not restates_middle_row:
            continue

        pair.status = "discard"
        pair.confidence_bucket = "low"
        if uses_prefixed:
            pair.rationale = (
                "Covered by terminal structured endpoint; prefixed terminal text "
                "must not be reduced to a bare ordinary pair."
            )
            pair.evidence["covered_by_terminal_structured_endpoint"] = True
        else:
            pair.rationale = (
                "Covered by terminal_header_table mapping; bare middle-row ordinary "
                "pair is shadowed by header+row composite keys."
            )
            pair.evidence["covered_by_terminal_header_table_row"] = True
        pair.evidence["ordinary_pair_eligible"] = False
        pair.evidence["ordinary_pair_shadow_only"] = True
        pair.evidence["ordinary_pair_shadow_reason"] = (
            "covered_by_terminal_structured_endpoint"
            if uses_prefixed
            else "covered_by_terminal_header_table_row"
        )


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


def _is_terminal_header_middle_row_restatement(pair: Pair) -> bool:
    """True when ordinary pair is bare-digit middle-row geometry (e.g. 10→519)."""
    left = str(pair.left_value or "").strip()
    right = str(pair.right_value or "").strip()
    if not left or not right:
        return False
    if not left.isdigit():
        return False
    # Right may already be the derived bare suffix (519 from 1n519).
    if right.isdigit():
        return True
    evidence = pair.evidence or {}
    right_raw = str(evidence.get("selected_right_raw_text") or right)
    left_raw = str(evidence.get("selected_left_raw_text") or left)
    return left_raw.isdigit() and (
        right_raw.isdigit() or _looks_like_prefixed_terminal_endpoint(right_raw)
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
