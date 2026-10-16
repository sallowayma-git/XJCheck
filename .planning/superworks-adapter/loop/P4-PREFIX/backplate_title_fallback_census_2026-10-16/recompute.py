from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import ezdxf
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / ".planning" / "superworks-adapter" / "corpus_manifest.json").exists())
MANIFEST_PATH = ROOT / ".planning" / "superworks-adapter" / "corpus_manifest.json"
CURRENT_RUN = ROOT / ".tmp" / "precision_loop_20261015" / "p057_slice_10"
sys.path.insert(0, str(ROOT / "src"))

from dwg_audit.audit import table_extractor as te  # noqa: E402
from dwg_audit.domain.models import SheetRecord, TextItem, dxf_text_visibility, is_dxf_visible_text, is_invisible_text  # noqa: E402
from dwg_audit.extract.cad_extract import _entity_visibility, _layer_visibility_by_name  # noqa: E402


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _str(value: Any, default: str = "") -> str:
    return default if _missing(value) else str(value)


def _optional_str(value: Any) -> str | None:
    return None if _missing(value) else str(value)


def _float(value: Any, default: float | None = None) -> float | None:
    if _missing(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _json_value(value: Any, default: Any) -> Any:
    if _missing(value):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _visibility_by_handle(dxf_path: Path, layout_name: str, expand_virtual: bool) -> tuple[dict[str, bool | None], str]:
    """Rebuild the text visibility propagated by cad_extract from the source DXF."""
    digest = hashlib.sha256(dxf_path.read_bytes()).hexdigest()
    doc = ezdxf.readfile(dxf_path)
    layer_visibility = _layer_visibility_by_name(doc)
    try:
        layout = doc.layouts.get(layout_name) if layout_name else None
    except Exception:
        layout = None
    if layout is None:
        layout = doc.modelspace()

    result: dict[str, bool | None] = {}

    def walk(entity: Any, handle: str | None, inherited: bool | None, depth: int = 0) -> None:
        if depth > 24:
            return
        dxftype = entity.dxftype()
        entity_handle = handle or str(getattr(entity.dxf, "handle", "") or f"virtual:{dxftype}")
        layer = str(getattr(entity.dxf, "layer", "0") or "0")
        visible = _entity_visibility(
            entity,
            dxftype=dxftype,
            layer=layer,
            layer_visibility_by_name=layer_visibility,
            inherited_visibility=inherited,
        )
        result[entity_handle] = visible
        if dxftype != "INSERT":
            return
        try:
            attributes = list(entity.attribs)
        except Exception:
            attributes = []
        for index, attrib in enumerate(attributes):
            walk(attrib, f"{entity_handle}:ATTRIB:{index}", visible, depth + 1)
        if expand_virtual:
            try:
                virtual_entities = list(entity.virtual_entities())
            except Exception:
                virtual_entities = []
            for index, virtual in enumerate(virtual_entities):
                walk(virtual, f"{entity_handle}:VIRTUAL:{index}", visible, depth + 1)

    for entity in layout:
        walk(entity, None, True)
    return result, digest


def _make_sheet(row: Any) -> SheetRecord:
    bbox = _json_value(row.audit_area_bbox, None)
    bbox = tuple(float(part) for part in bbox) if bbox is not None else None
    return SheetRecord(
        sheet_id=_str(row.sheet_id),
        file_id=_str(row.file_id),
        filename=_str(row.filename),
        sheet_order=_int(row.sheet_order) or 0,
        sheet_no=_optional_str(row.sheet_no),
        sheet_title=_str(row.sheet_title),
        sheet_category=_optional_str(row.sheet_category),
        audit_role=_str(row.audit_role),
        page_no_source=_str(row.page_no_source),
        is_primary_audit_candidate=bool(row.is_primary_audit_candidate) if not _missing(row.is_primary_audit_candidate) else False,
        source_refs=_json_value(row.source_refs, []),
        warnings=_json_value(row.warnings, []),
        layout_name=_optional_str(row.layout_name),
        drawing_units=_optional_str(row.drawing_units),
        audit_area_bbox=bbox,
    )


def _make_text(row: Any, visibility: dict[str, bool | None]) -> TextItem:
    handle = _str(row.handle)
    return TextItem(
        text_id=_str(row.text_id),
        sheet_id=_str(row.sheet_id),
        file_id=_str(row.file_id),
        handle=handle,
        entity_type=_str(row.entity_type),
        text=_str(row.text),
        normalized_text=_str(row.normalized_text),
        is_numeric_candidate=bool(row.is_numeric_candidate) if not _missing(row.is_numeric_candidate) else False,
        layer=_str(row.layer),
        rotation_deg=_float(row.rotation_deg, 0.0) or 0.0,
        height=_float(row.height, 0.0) or 0.0,
        insert_x=_float(row.insert_x, 0.0) or 0.0,
        insert_y=_float(row.insert_y, 0.0) or 0.0,
        bbox_min_x=_float(row.bbox_min_x, 0.0) or 0.0,
        bbox_min_y=_float(row.bbox_min_y, 0.0) or 0.0,
        bbox_max_x=_float(row.bbox_max_x, 0.0) or 0.0,
        bbox_max_y=_float(row.bbox_max_y, 0.0) or 0.0,
        source_block_name=_optional_str(row.source_block_name),
        color_index=_int(row.color_index),
        true_color=_int(row.true_color),
        text_geometry_json=_str(row.text_geometry_json, "{}"),
        physical_ports_json=_str(row.physical_ports_json, "[]"),
        device_pin_label_json=_str(row.device_pin_label_json, "{}"),
        raw_height=_float(row.raw_height),
        dxf_visible=visibility.get(handle),
    )


def _title_filename_device(sheet: SheetRecord) -> str | None:
    for blob in (sheet.sheet_title or "", sheet.filename or ""):
        match = te._DEVICE_INSTANCE_TITLE_PATTERN.search(blob)
        if match:
            return next(group for group in match.groups() if group)
        bare = re.search(r"(\d+-\d+[A-Za-z])\b", blob)
        if bare and te._DEVICE_INSTANCE_PATTERN.fullmatch(bare.group(1)):
            return bare.group(1)
    return None


def _template_device(free_texts: list[TextItem]) -> tuple[str | None, list[TextItem]]:
    candidates: list[tuple[float, float, str, TextItem]] = []
    for text in free_texts:
        if not te._device_selector_text_allowed(text):
            continue
        value = str(text.normalized_text or "").strip()
        if te._DEVICE_INSTANCE_PATTERN.fullmatch(value):
            candidates.append((-text.insert_y, text.insert_x, value, text))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return (candidates[0][2], [item[3] for item in candidates[:1]]) if candidates else (None, [])


def _route_inputs(sheet: SheetRecord, free_texts: list[TextItem], page_texts: list[TextItem]) -> dict[str, Any]:
    title_device = _title_filename_device(sheet)
    template_device, template_sources = _template_device(free_texts)
    caption_device = te._rear_wiring_caption_device(page_texts)
    if title_device is not None:
        route = "sheet_title_or_filename"
        predicted_device = title_device
    elif caption_device and (
        template_device is None
        or te._backplate_device_core(template_device) != te._backplate_device_core(caption_device)
    ):
        route = "prefixed_rear_wiring_caption"
        predicted_device = caption_device
    elif template_device is not None:
        route = "free_text_compound_device"
        predicted_device = template_device
    else:
        route = "standalone_title_fallback"
        predicted_device = None
    return {
        "title_filename_device": title_device,
        "template_device": template_device,
        "template_source_texts": template_sources,
        "prefixed_rear_wiring_caption_device": caption_device,
        "pre_fallback_route": route,
        "pre_fallback_device": predicted_device,
    }


def _fallback_diagnostics(free_texts: list[TextItem], page_texts: list[TextItem]) -> dict[str, Any]:
    standalone_captions = [
        text for text in page_texts
        if is_dxf_visible_text(text)
        and not is_invisible_text(text)
        and te._STANDALONE_REAR_WIRING_CAPTION_PATTERN.fullmatch(str(text.normalized_text or ""))
    ]
    visible_free = [
        text for text in free_texts
        if is_dxf_visible_text(text) and not is_invisible_text(text)
    ]
    bare: dict[str, list[TextItem]] = defaultdict(list)
    models: dict[str, list[TextItem]] = defaultdict(list)
    for text in visible_free:
        value = str(text.normalized_text or "").strip()
        key = value.casefold()
        if te._BARE_BACKPLATE_DEVICE_PATTERN.fullmatch(value):
            bare[key].append(text)
        elif te._BACKPLATE_MODEL_PATTERN.fullmatch(value):
            models[key].append(text)
    matched_models: set[str] = set()
    if len(bare) == 1:
        for device_texts in bare.values():
            for model_texts in models.values():
                if any(
                    math.hypot(device.insert_x - model.insert_x, device.insert_y - model.insert_y)
                    <= 4.0 * max(float(device.height), float(model.height), 0.0)
                    for device in device_texts
                    for model in model_texts
                ):
                    matched_models.add(str(model_texts[0].normalized_text or "").strip().casefold())
    if not standalone_captions:
        reason = "No visible standalone REAR WIRING caption; helper returns None before examining device/model labels."
    elif len(bare) != 1:
        reason = f"Helper requires exactly one unique bare device token; visible audit-area tokens were {len(bare)}."
    elif not models:
        reason = "Helper found one bare device token but no visible model token matching its model-code pattern."
    elif len(matched_models) != 1:
        reason = f"Helper found {len(matched_models)} unique nearby model codes; it requires exactly one."
    else:
        reason = "Helper predicates pass; a device identity should be returned."
    return {
        "standalone_caption_texts": standalone_captions,
        "bare_device_groups": bare,
        "model_groups": models,
        "nearby_model_groups": matched_models,
        "probe_failure_reason": reason,
    }


def _stable_map_key(project_id: str, file_id: str, source_sha: str, sheet_id: str, mapping: dict[str, Any], handles: dict[str, str]) -> tuple[str, str]:
    values = [
        project_id,
        file_id,
        source_sha,
        sheet_id,
        str(mapping.get("mapping_mode") or ""),
        handles.get(str(mapping.get("header_text_id") or ""), ""),
        handles.get(str(mapping.get("middle_text_id") or ""), ""),
        handles.get(str(mapping.get("right_text_id") or ""), ""),
        str(mapping.get("logical_endpoint") or ""),
        str(mapping.get("right_value") or ""),
    ]
    payload = "\x1f".join(values)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    readable = "/".join([project_id, file_id, sheet_id, "bpvt", values[5] or "-", values[6] or "-", values[7] or "-", values[8], values[9]])
    return readable, digest


def _starts_with_device(logical_endpoint: str, device: str | None) -> bool:
    if not logical_endpoint or not device or not logical_endpoint.startswith(device):
        return False
    return logical_endpoint == device or logical_endpoint[len(device):len(device) + 1] in {"/", "-", "_"} or logical_endpoint[len(device):].isdigit()


def _csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (dict, list, set, tuple)) else value for key, value in row.items()})


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    projects = manifest["projects"]
    if len(projects) != 77:
        raise AssertionError(f"Expected the 77-project corpus, found {len(projects)} projects")

    current_maps_total = 0
    all_pages_total = 0
    page_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    unknown_rows: list[dict[str, Any]] = []
    route_counts: Counter[str] = Counter()
    fallback_attempts = fallback_hits = 0
    title_candidates = title_candidate_fallback_hits = title_candidate_counterfactual_misses = 0
    total_backplate_pages = 0
    backplate_map_total = pair_matches = 0
    map_status_counts: Counter[str] = Counter()
    dxf_checks: dict[tuple[str, str, str], tuple[dict[str, bool | None], str, str]] = {}
    source_by_project_file: dict[tuple[str, str], dict[str, Any]] = {}

    for project in projects:
        for source in project.get("files", []):
            source_by_project_file[(project["project_id"], str(source["file_id"]))] = source

    for project in projects:
        project_id = project["project_id"]
        project_output = CURRENT_RUN / project_id
        finding_dirs = sorted(project_output.glob("*/findings"))
        if len(finding_dirs) != 1:
            raise FileNotFoundError(f"Expected one findings directory for {project_id}, found {finding_dirs}")
        findings_dir = finding_dirs[0]
        pages = pd.read_parquet(findings_dir / "pages.parquet")
        texts_df = pd.read_parquet(findings_dir / "texts.parquet")
        pairs_df = pd.read_parquet(findings_dir / "pairs.parquet")
        findings = json.loads((findings_dir / "findings.json").read_text(encoding="utf-8"))
        all_pages_total += len(pages)
        summary = findings.get("table_extraction_summary") or {}

        for table in summary.get("mappings", []):
            current_maps_total += len(table.get("mappings", []))

        pair_by_mapping_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for _, pair in pairs_df[pairs_df.pair_kind == "table_mapping"].iterrows():
            evidence = _json_value(pair.evidence, {})
            mapping = evidence.get("table_mapping") or {}
            key = (
                _str(pair.sheet_id),
                _str(mapping.get("middle_text_id")),
                _str(mapping.get("right_text_id")),
                _str(mapping.get("logical_endpoint")),
            )
            pair_by_mapping_key[key].append({
                "pair_id": _str(pair.pair_id),
                "status": _str(pair.status),
                "left_value": _str(pair.left_value),
                "right_value": _str(pair.right_value),
                "pair_key": _str(pair.pair_key),
                "confidence": _float(pair.confidence),
            })

        mappings_by_sheet: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for table in summary.get("mappings", []):
            for mapping in table.get("mappings", []):
                if mapping.get("mapping_mode") == "backplate_virtual_table":
                    mappings_by_sheet[_str(mapping.get("sheet_id"))].append(mapping)

        pages_by_sheet = {str(row.sheet_id): row for _, row in pages.iterrows()}
        texts_by_sheet = {str(sheet_id): group for sheet_id, group in texts_df.groupby("sheet_id", sort=False)}
        backplates = pages[pages.sheet_category == "背板接线图"]
        for _, page in backplates.iterrows():
            total_backplate_pages += 1
            sheet = _make_sheet(page)
            file_key = (project_id, sheet.file_id)
            source = source_by_project_file.get(file_key)
            if not source:
                raise KeyError(f"Missing manifest source for {project_id}/{sheet.file_id}")
            dxf_path = Path(source["dxf_path"])
            if not dxf_path.is_file():
                raise FileNotFoundError(f"Source DXF missing: {dxf_path}")
            cache_key = (project_id, sheet.file_id, sheet.layout_name or "Model")
            if cache_key not in dxf_checks:
                visibility, actual_sha = _visibility_by_handle(dxf_path, sheet.layout_name or "Model", expand_virtual=True)
                expected_sha = str(source.get("dxf_sha256") or "")
                if expected_sha and actual_sha.casefold() != expected_sha.casefold():
                    raise AssertionError(f"DXF hash mismatch for {project_id}/{sheet.file_id}: {actual_sha} != {expected_sha}")
                dxf_checks[cache_key] = (visibility, actual_sha, str(source.get("path") or ""))
            visibility, actual_sha, source_dwg = dxf_checks[cache_key]

            text_frame = texts_by_sheet.get(sheet.sheet_id)
            source_texts = [_make_text(row, visibility) for _, row in text_frame.iterrows()] if text_frame is not None else []
            text_by_id = {text.text_id: text for text in source_texts}
            page_texts = source_texts
            free_texts = [
                text for text in source_texts
                if not text.source_block_name and te._text_in_audit_area(text, sheet)
            ]

            inputs = _route_inputs(sheet, free_texts, page_texts)
            fallback_calls: list[str | None] = []
            original_helper = te._visible_standalone_backplate_device

            def capture_helper(free: list[TextItem], page_items: list[TextItem]) -> str | None:
                value = original_helper(free, page_items)
                fallback_calls.append(value)
                return value

            te._visible_standalone_backplate_device = capture_helper
            try:
                resolved_device = te._resolve_backplate_device_instance(free_texts, sheet, page_texts=page_texts)
            finally:
                te._visible_standalone_backplate_device = original_helper

            attempted = bool(fallback_calls)
            fallback_device = fallback_calls[-1] if attempted else None
            fallback_attempts += int(attempted)
            fallback_hits += int(attempted and fallback_device is not None)
            route = inputs["pre_fallback_route"]
            if attempted:
                route = "standalone_title_fallback_hit" if fallback_device is not None else "standalone_title_fallback_no_result"
            elif inputs["pre_fallback_route"] == "standalone_title_fallback":
                raise AssertionError(f"Expected fallback call on {project_id}/{sheet.sheet_id}")
            if resolved_device != (fallback_device if attempted and fallback_device is not None else inputs["pre_fallback_device"]):
                raise AssertionError(
                    f"Route reconstruction mismatch for {project_id}/{sheet.sheet_id}: "
                    f"resolver={resolved_device!r}; inputs={inputs}; calls={fallback_calls}"
                )
            route_counts[route] += 1

            diagnostics = _fallback_diagnostics(free_texts, page_texts)
            standalone_captions = diagnostics["standalone_caption_texts"]
            in_standalone_scope = bool(standalone_captions)
            title_candidates += int(in_standalone_scope)
            title_candidate_fallback_hits += int(in_standalone_scope and attempted and fallback_device is not None)
            probe_result = original_helper(free_texts, page_texts) if in_standalone_scope else None
            counterfactual_miss = in_standalone_scope and probe_result is None
            title_candidate_counterfactual_misses += int(counterfactual_miss)

            page_mappings = mappings_by_sheet.get(sheet.sheet_id, [])
            mapping_keys: list[str] = []
            pair_ids: list[str] = []
            output_identities: list[str] = []
            page_mapping_count = 0
            page_pair_count = 0
            same_device_without_fallback = 0
            fallback_mapping_count = 0
            current_rows_matching_resolver_device = 0
            current_rows_not_matching_resolver_device = 0
            page_map_status = Counter()
            for mapping in page_mappings:
                backplate_map_total += 1
                page_mapping_count += 1
                join_key = (
                    _str(mapping.get("sheet_id")),
                    _str(mapping.get("middle_text_id")),
                    _str(mapping.get("right_text_id")),
                    _str(mapping.get("logical_endpoint")),
                )
                matches = pair_by_mapping_key.get(join_key, [])
                if len(matches) != 1:
                    raise AssertionError(f"Expected one current table_mapping pair for {project_id}/{join_key}; found {len(matches)}")
                pair = matches[0]
                pair_matches += 1
                page_pair_count += 1
                map_status_counts[pair["status"]] += 1
                page_map_status[pair["status"]] += 1
                pair_ids.append(pair["pair_id"])
                logical_endpoint = _str(mapping.get("logical_endpoint"))
                output_identities.append(logical_endpoint)
                header_id = _str(mapping.get("header_text_id"))
                middle_id = _str(mapping.get("middle_text_id"))
                right_id = _str(mapping.get("right_text_id"))
                handles = {
                    header_id: text_by_id[header_id].handle if header_id in text_by_id else "",
                    middle_id: text_by_id[middle_id].handle if middle_id in text_by_id else "",
                    right_id: text_by_id[right_id].handle if right_id in text_by_id else "",
                }
                readable_key, stable_sha = _stable_map_key(project_id, sheet.file_id, actual_sha, sheet.sheet_id, mapping, handles)
                mapping_keys.append(readable_key)
                output_matches_route_device = _starts_with_device(logical_endpoint, resolved_device)
                same_without_fallback = bool(not attempted and resolved_device and output_matches_route_device)
                used_by_fallback = bool(attempted and fallback_device and _starts_with_device(logical_endpoint, fallback_device))
                same_device_without_fallback += int(same_without_fallback)
                fallback_mapping_count += int(used_by_fallback)
                current_rows_matching_resolver_device += int(bool(resolved_device and output_matches_route_device))
                current_rows_not_matching_resolver_device += int(bool(resolved_device and not output_matches_route_device))
                mapping_rows.append({
                    "project_id": project_id,
                    "file_id": sheet.file_id,
                    "source_dwg": source_dwg,
                    "source_dxf": str(dxf_path),
                    "source_dxf_sha256": actual_sha,
                    "source_dxf_hash_verified": True,
                    "sheet_id": sheet.sheet_id,
                    "sheet_no": sheet.sheet_no or "",
                    "filename": sheet.filename,
                    "page_title_input": sheet.sheet_title,
                    "mapping_stable_key": readable_key,
                    "mapping_stable_key_sha256": stable_sha,
                    "pair_id_current": pair["pair_id"],
                    "pair_status_current": pair["status"],
                    "mapping_mode": _str(mapping.get("mapping_mode")),
                    "header_prefix_output": _str(mapping.get("header_prefix")),
                    "header_text_id": header_id,
                    "header_handle": handles.get(header_id, ""),
                    "middle_text_id": middle_id,
                    "middle_handle": handles.get(middle_id, ""),
                    "right_text_id": right_id,
                    "right_handle": handles.get(right_id, ""),
                    "logical_endpoint_output": logical_endpoint,
                    "right_value_output": _str(mapping.get("right_value")),
                    "resolver_route": route,
                    "resolver_device_output": resolved_device or "",
                    "fallback_attempted_actual": attempted,
                    "fallback_returned_device_actual": fallback_device or "",
                    "fallback_device_prefix_matches_current_mapping_output": used_by_fallback,
                    "fallback_device_prefix_mismatch_current_mapping_output": bool(attempted and fallback_device and not _starts_with_device(logical_endpoint, fallback_device)),
                    "current_logical_endpoint_matches_resolver_device_output": bool(resolved_device and output_matches_route_device),
                    "same_resolver_identity_output_without_fallback": same_without_fallback,
                    "composite_output_field_used_as_truth": False,
                })

            dxf_visibility_unknown = sum(dxf_text_visibility(text) is None for text in source_texts)
            page_rows.append({
                "project_id": project_id,
                "file_id": sheet.file_id,
                "source_dwg": source_dwg,
                "source_dxf": str(dxf_path),
                "source_dxf_sha256": actual_sha,
                "source_dxf_hash_verified": True,
                "sheet_id": sheet.sheet_id,
                "sheet_no": sheet.sheet_no or "",
                "filename": sheet.filename,
                "layout_name": sheet.layout_name or "Model",
                "page_title_input": sheet.sheet_title,
                "audit_area_bbox": list(sheet.audit_area_bbox) if sheet.audit_area_bbox else [],
                "raw_visible_standalone_rear_wiring_title": in_standalone_scope,
                "standalone_title_evidence": [
                    {"text_id": text.text_id, "handle": text.handle, "text": text.normalized_text,
                     "insert_x": text.insert_x, "insert_y": text.insert_y}
                    for text in standalone_captions
                ],
                "title_filename_device_input": inputs["title_filename_device"] or "",
                "prefixed_caption_device_input": inputs["prefixed_rear_wiring_caption_device"] or "",
                "template_device_input": inputs["template_device"] or "",
                "template_device_source": [
                    {"text_id": text.text_id, "handle": text.handle, "text": text.normalized_text,
                     "insert_x": text.insert_x, "insert_y": text.insert_y}
                    for text in inputs["template_source_texts"]
                ],
                "resolver_route": route,
                "resolver_device_output": resolved_device or "",
                "fallback_attempted_actual": attempted,
                "fallback_returned_device_actual": fallback_device or "",
                "standalone_title_counterfactual_probe_result": probe_result or "",
                "counterfactual_probe_failure_reason": diagnostics["probe_failure_reason"] if counterfactual_miss else "",
                "visible_bare_device_tokens_in_audit_area": sorted({items[0].normalized_text for items in diagnostics["bare_device_groups"].values()}),
                "visible_model_tokens_in_audit_area": sorted({items[0].normalized_text for items in diagnostics["model_groups"].values()}),
                "unmapped_dxf_visibility_text_count": dxf_visibility_unknown,
                "current_backplate_table_mapping_count": page_mapping_count,
                "current_pair_matched_count": page_pair_count,
                "current_pair_status_counts": dict(page_map_status),
                "current_pair_ids": pair_ids,
                "current_logical_endpoint_outputs": output_identities,
                "stable_mapping_keys": mapping_keys,
                "rows_same_resolver_identity_without_fallback": same_device_without_fallback,
                "rows_using_actual_fallback_result": fallback_mapping_count,
                "current_rows_matching_resolver_device_output": current_rows_matching_resolver_device,
                "current_rows_not_matching_resolver_device_output": current_rows_not_matching_resolver_device,
            })

            if in_standalone_scope and (
                (attempted and fallback_device is None)
                or (not attempted and probe_result is None)
            ):
                # The second case is explicitly counterfactual: the runtime route skipped
                # the helper because a higher-priority source supplied a compound instance.
                runtime_miss = bool(attempted and fallback_device is None)
                caption = standalone_captions[0]
                bare_tokens = sorted({items[0].normalized_text for items in diagnostics["bare_device_groups"].values()})
                model_tokens = sorted({items[0].normalized_text for items in diagnostics["model_groups"].values()})
                unknown_rows.append({
                    "project_id": project_id,
                    "file_id": sheet.file_id,
                    "sheet_id": sheet.sheet_id,
                    "filename": sheet.filename,
                    "source_dwg": source_dwg,
                    "source_dxf": str(dxf_path),
                    "source_dxf_sha256": actual_sha,
                    "unknown_case_key": f"{project_id}/{sheet.file_id}/{sheet.sheet_id}/{caption.handle}",
                    "visible_title_text_id": caption.text_id,
                    "visible_title_handle": caption.handle,
                    "visible_title_text": caption.normalized_text,
                    "actual_fallback_invoked": attempted,
                    "actual_runtime_fallback_miss": runtime_miss,
                    "current_resolver_route": route,
                    "current_resolver_device_output": resolved_device or "",
                    "counterfactual_helper_probe_result": probe_result or "",
                    "counterfactual_probe_failure_reason": diagnostics["probe_failure_reason"],
                    "visible_unique_bare_device_tokens": bare_tokens,
                    "visible_model_code_tokens": model_tokens,
                    "current_backplate_mapping_rows": page_mapping_count,
                    "current_pair_ids": pair_ids,
                    "current_logical_endpoint_outputs": output_identities,
                    "interpretation": (
                        "Actual fallback failure inside standalone-title scope."
                        if runtime_miss else
                        "Not a runtime fallback miss: existing higher-priority route bypassed the helper. "
                        "The helper was probed counterfactually and did not resolve the multiple bare-device tokens."
                    ),
                })

    if all_pages_total != 1745 or total_backplate_pages != 187:
        raise AssertionError(f"Corpus scope mismatch: pages={all_pages_total}, backplate_pages={total_backplate_pages}")
    if pair_matches != backplate_map_total:
        raise AssertionError(f"Backplate map/pair join mismatch: maps={backplate_map_total}, pairs={pair_matches}")

    _csv(
        HERE / "case_level.csv",
        mapping_rows,
        [
            "project_id", "file_id", "source_dwg", "source_dxf", "source_dxf_sha256", "source_dxf_hash_verified",
            "sheet_id", "sheet_no", "filename", "page_title_input", "mapping_stable_key", "mapping_stable_key_sha256",
            "pair_id_current", "pair_status_current", "mapping_mode", "header_prefix_output", "header_text_id", "header_handle",
            "middle_text_id", "middle_handle", "right_text_id", "right_handle", "logical_endpoint_output", "right_value_output",
            "resolver_route", "resolver_device_output", "fallback_attempted_actual", "fallback_returned_device_actual",
            "fallback_device_prefix_matches_current_mapping_output", "fallback_device_prefix_mismatch_current_mapping_output",
            "current_logical_endpoint_matches_resolver_device_output", "same_resolver_identity_output_without_fallback",
            "composite_output_field_used_as_truth",
        ],
    )
    _csv(
        HERE / "page_census.csv",
        page_rows,
        [
            "project_id", "file_id", "source_dwg", "source_dxf", "source_dxf_sha256", "source_dxf_hash_verified",
            "sheet_id", "sheet_no", "filename", "layout_name", "page_title_input", "audit_area_bbox",
            "raw_visible_standalone_rear_wiring_title", "standalone_title_evidence", "title_filename_device_input",
            "prefixed_caption_device_input", "template_device_input", "template_device_source", "resolver_route",
            "resolver_device_output", "fallback_attempted_actual", "fallback_returned_device_actual",
            "standalone_title_counterfactual_probe_result", "counterfactual_probe_failure_reason",
            "visible_bare_device_tokens_in_audit_area", "visible_model_tokens_in_audit_area",
            "unmapped_dxf_visibility_text_count", "current_backplate_table_mapping_count", "current_pair_matched_count",
            "current_pair_status_counts", "current_pair_ids", "current_logical_endpoint_outputs", "stable_mapping_keys",
            "rows_same_resolver_identity_without_fallback", "rows_using_actual_fallback_result",
            "current_rows_matching_resolver_device_output", "current_rows_not_matching_resolver_device_output",
        ],
    )
    _csv(
        HERE / "unknown_shapes.csv",
        unknown_rows,
        [
            "project_id", "file_id", "sheet_id", "filename", "source_dwg", "source_dxf", "source_dxf_sha256",
            "unknown_case_key", "visible_title_text_id", "visible_title_handle", "visible_title_text",
            "actual_fallback_invoked", "actual_runtime_fallback_miss", "current_resolver_route", "current_resolver_device_output",
            "counterfactual_helper_probe_result", "counterfactual_probe_failure_reason", "visible_unique_bare_device_tokens",
            "visible_model_code_tokens", "current_backplate_mapping_rows", "current_pair_ids", "current_logical_endpoint_outputs",
            "interpretation",
        ],
    )

    actual_hit_pages = [row for row in page_rows if row["fallback_attempted_actual"] and row["fallback_returned_device_actual"]]
    actual_miss_pages = [row for row in page_rows if row["fallback_attempted_actual"] and not row["fallback_returned_device_actual"]]
    candidate_pages = [row for row in page_rows if row["raw_visible_standalone_rear_wiring_title"]]
    candidate_same_output = [row for row in candidate_pages if not row["fallback_attempted_actual"] and row["rows_same_resolver_identity_without_fallback"]]
    summary_lines = [
        "# Backplate standalone-title fallback census",
        "",
        "## Scope and method",
        "",
        "- Input corpus: `.planning/superworks-adapter/corpus_manifest.json` (77 projects); current replay artifacts: `.tmp/precision_loop_20261015/p057_slice_10/`.",
        f"- The replay contains {all_pages_total:,} pages. This census is limited to {total_backplate_pages:,} pages whose `sheet_category` is `背板接线图`, because `extract_table_pairs` only enters the backplate virtual-table builder for that category.",
        "- Each relevant page's source DXF was opened read-only, its SHA-256 was checked against the manifest, and entity/layer/INSERT visibility was rebuilt using the same visibility helpers as the extractor. Raw title/device/model text and the current `table_extraction_summary` / `pairs.parquet` were joined by source DXF, sheet, and mapping text handles.",
        "- The exact current resolver was re-run against `TextItem` / `SheetRecord` inputs reconstructed from the current replay's page and text outputs. The helper's own `composite_device_instance` field was not used as truth or as a correctness check. Fallback call counts are from this resolver re-run, not telemetry captured during the original replay. Current `logical_endpoint` and pair rows are reported only as pipeline outputs.",
        "",
        "## Counts",
        "",
        f"- Current table mapping rows in the 77 replay projects: {current_maps_total:,} total; `backplate_virtual_table` rows: {backplate_map_total:,}.",
        f"- Current backplate table mappings joined to `pair_kind=table_mapping` by `(sheet_id, middle_text_id, right_text_id, logical_endpoint)`: {pair_matches:,}/{backplate_map_total:,}.",
        f"- Reconstructed current-resolver reruns over backplate page evidence invoked `_visible_standalone_backplate_device` on {fallback_attempts:,} pages; it returned a device on {fallback_hits:,} and no device on {fallback_attempts - fallback_hits:,}.",
        f"- Visible standalone `REAR WIRING` title pages in scope: {len(candidate_pages):,}; resolver-rerun fallback hits among these: {title_candidate_fallback_hits:,}; counterfactual helper probes with no result: {title_candidate_counterfactual_misses:,}.",
        f"- Current mapping rows whose logical endpoint carries the resolved device prefix without the fallback being called, among standalone-title pages: {sum(row['rows_same_resolver_identity_without_fallback'] for row in candidate_same_output):,}.",
        f"- Current mapping rows whose logical endpoint carries the device returned by an actual fallback call: {sum(row['rows_using_actual_fallback_result'] for row in candidate_pages):,}.",
        f"- Pair statuses for the {backplate_map_total:,} matched current backplate mappings: {dict(sorted(map_status_counts.items()))}.",
        "",
        "### Resolver routes over 187 backplate pages",
        "",
        "| Route | Pages |",
        "|---|---:|",
    ]
    summary_lines.extend(f"| `{route}` | {count:,} |" for route, count in sorted(route_counts.items()))
    summary_lines += [
        "",
        "## Standalone-title candidate and route distinction",
        "",
    ]
    if candidate_pages:
        for row in candidate_pages:
            evidence = row["standalone_title_evidence"]
            pair_ids = row["current_pair_ids"]
            identities = row["current_logical_endpoint_outputs"]
            summary_lines += [
                f"- `{row['project_id']}/{row['sheet_id']}` / `{row['filename']}`: source DXF `{row['source_dxf']}` (SHA-256 `{row['source_dxf_sha256']}`), visible raw caption {evidence}; route=`{row['resolver_route']}`, resolved output=`{row['resolver_device_output'] or '(none)'}`, helper-called=`{row['fallback_attempted_actual']}`, helper-return=`{row['fallback_returned_device_actual'] or '(none)'}`.",
                f"  Current mapping rows/pairs: {row['current_backplate_table_mapping_count']}/{row['current_pair_matched_count']}; pair IDs `{', '.join(pair_ids)}`; current logical endpoint outputs `{', '.join(identities)}`.",
                f"  Current logical endpoints matching resolver device output: {row['current_rows_matching_resolver_device_output']}; not matching: {row['current_rows_not_matching_resolver_device_output']}; rows using actual helper result: {row['rows_using_actual_fallback_result']}. This compares two outputs only; neither establishes the correct physical device identity.",
            ]
    else:
        summary_lines.append("No visible standalone `REAR WIRING` caption matched the current helper's title pattern in the 187 backplate pages.")
    summary_lines += [
        "",
        "## Unknown shapes",
        "",
        f"Resolver-rerun misses inside the exact standalone-title scope: {sum(bool(row['actual_runtime_fallback_miss']) for row in unknown_rows)}.",
    ]
    if unknown_rows:
        for row in unknown_rows:
            summary_lines.append(
                f"- `{row['unknown_case_key']}`: runtime-called={row['actual_fallback_invoked']}, runtime-miss={row['actual_runtime_fallback_miss']}; "
                f"counterfactual result=`{row['counterfactual_helper_probe_result'] or '(none)'}`; {row['counterfactual_probe_failure_reason']} "
                f"The classification is: {row['interpretation']}"
            )
    else:
        summary_lines.append("`unknown_shapes.csv` has a header row and no data rows. Boundary: only visible exact `REAR WIRING` captions with an optional numeric suffix, on backplate-category pages, are considered in-scope unknown candidates.")
    summary_lines += [
        "",
        "## Reproduction and source locations",
        "",
        "Run from the repository root: `python .tmp/precision_loop_20261015/backplate_title_fallback_census_20261016/recompute.py`.",
        "- `src/dwg_audit/audit/table_extractor.py:205-220`: backplate category dispatch into `_build_backplate_virtual_mappings`.",
        "- `src/dwg_audit/audit/table_extractor.py:1557-1569`: source texts and resolver call site.",
        "- `src/dwg_audit/audit/table_extractor.py:1788-1832`: resolver precedence and fallback condition.",
        "- `src/dwg_audit/audit/table_extractor.py:1835-1882`: standalone title, unique bare-device, model-code, and proximity predicates.",
        "- `src/dwg_audit/audit/table_extractor.py:1706-1737`: current logical endpoint creation and mapping evidence fields; reported output only.",
        "",
        "## Files",
        "",
        "- `case_level.csv`: one row per current backplate virtual-table mapping, joined to its exact current table_mapping pair and source-DXF entity handles.",
        "- `page_census.csv`: all 187 backplate pages, including fallback route, standalone-title presence, and page-level pair/output identities.",
        "- `unknown_shapes.csv`: visible in-scope title cases where the real helper missed or a counterfactual probe failed; runtime and counterfactual status remain separate.",
        "- `recompute.py`: read-only census script.",
    ]
    (HERE / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "projects": len(projects),
        "all_pages": all_pages_total,
        "backplate_pages": total_backplate_pages,
        "table_mappings_total": current_maps_total,
        "backplate_mappings": backplate_map_total,
        "matched_pairs": pair_matches,
        "fallback_attempts": fallback_attempts,
        "fallback_hits": fallback_hits,
        "fallback_misses": fallback_attempts - fallback_hits,
        "standalone_title_pages": len(candidate_pages),
        "title_candidate_fallback_hits": title_candidate_fallback_hits,
        "title_candidate_counterfactual_misses": title_candidate_counterfactual_misses,
        "unknown_rows": len(unknown_rows),
        "route_counts": dict(route_counts),
        "pair_status_counts": dict(map_status_counts),
        "dxf_file_layouts_verified": len(dxf_checks),
        "output_dir": str(HERE),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
