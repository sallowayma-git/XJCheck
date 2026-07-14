from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any


BBox = tuple[float, float, float, float]


@dataclass(slots=True)
class SourceFileRecord:
    file_id: str
    path: str
    filename: str
    ext: str
    sha256: str
    size_bytes: int
    sheet_order: int
    detected_page_no: str | None
    detected_from: str
    sheet_title: str
    sheet_category: str | None
    skip_reason: str | None
    valid_dwg_header: bool
    sidecar_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conversion_status: str = "pending"
    dxf_path: str | None = None
    conversion_detail: str | None = None
    conversion_version: str | None = None
    conversion_audit: bool | None = None
    conversion_duration_ms: int | None = None


@dataclass(slots=True)
class SidecarInfo:
    kind: str
    path: str | None
    status: str
    encoding: str | None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TerminalStrip:
    style: str
    name: str
    length: float


@dataclass(slots=True)
class SheetRecord:
    sheet_id: str
    file_id: str
    filename: str
    sheet_order: int
    sheet_no: str | None
    sheet_title: str
    sheet_category: str | None
    audit_role: str
    page_no_source: str
    is_primary_audit_candidate: bool
    source_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    layout_name: str | None = None
    drawing_units: str | None = None
    extent_bbox: BBox | None = None
    frame_bbox: BBox | None = None
    title_block_bbox: BBox | None = None
    audit_area_bbox: BBox | None = None
    page_type: str | None = None
    page_subtype: str | None = None
    page_type_confidence: float | None = None
    table_like: bool | None = None
    grid_heavy: bool | None = None
    route_target: str | None = None
    audit_disposition: str | None = None
    capabilities: list[str] = field(default_factory=list)
    capability_evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    communication_media: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TextItem:
    text_id: str
    sheet_id: str
    file_id: str
    handle: str
    entity_type: str
    text: str
    normalized_text: str
    is_numeric_candidate: bool
    layer: str
    rotation_deg: float
    height: float
    insert_x: float
    insert_y: float
    bbox_min_x: float
    bbox_min_y: float
    bbox_max_x: float
    bbox_max_y: float
    source_block_name: str | None = None


@dataclass(slots=True)
class LineEntity:
    line_id: str
    sheet_id: str
    file_id: str
    handle: str
    source_entity_type: str
    layer: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    length: float
    angle_deg: float
    bbox_min_x: float
    bbox_min_y: float
    bbox_max_x: float
    bbox_max_y: float


@dataclass(slots=True)
class BlockRecord:
    block_id: str
    sheet_id: str
    file_id: str
    handle: str
    name: str
    layer: str
    insert_x: float
    insert_y: float
    rotation_deg: float
    attributes_json: str


@dataclass(slots=True)
class PolylineRecord:
    polyline_id: str
    sheet_id: str
    file_id: str
    handle: str
    source_entity_type: str
    layer: str
    vertex_count: int
    is_closed: bool
    bbox_min_x: float
    bbox_min_y: float
    bbox_max_x: float
    bbox_max_y: float


@dataclass(slots=True)
class LineGroup:
    line_group_id: str
    sheet_id: str
    file_id: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    length: float
    wire_candidate_score: float
    member_line_ids: list[str] = field(default_factory=list)
    layer_hints: list[str] = field(default_factory=list)
    orientation: str = "horizontal"
    row_band_id: str | None = None


@dataclass(slots=True)
class TerminalCandidate:
    candidate_id: str
    line_group_id: str
    sheet_id: str
    file_id: str
    side: str
    text_id: str
    text: str
    value: str | None
    score: float
    status: str
    rejection_reason: str | None
    endpoint_x: float
    endpoint_y: float
    distance_x: float
    distance_y: float
    text_insert_x: float | None = None
    text_insert_y: float | None = None
    vertical_alignment_score: float | None = None
    horizontal_side_score: float | None = None
    text_type_score: float | None = None
    height_score: float | None = None
    rank: int | None = None
    source_block_name: str | None = None
    channel: str = "terminal_numeric_channel"
    channel_detail: str | None = None


@dataclass(slots=True)
class PairCandidate:
    pair_candidate_id: str
    line_group_id: str
    sheet_id: str
    file_id: str
    left_candidate_id: str | None
    right_candidate_id: str | None
    left_value: str | None
    right_value: str | None
    score: float
    status: str
    rationale: str
    left_text_id: str | None = None
    right_text_id: str | None = None
    pair_key: str | None = None
    left_score: float | None = None
    right_score: float | None = None
    wire_score: float | None = None
    ambiguity_gap: float | None = None


@dataclass(slots=True)
class Pair:
    pair_id: str
    line_group_id: str
    sheet_id: str
    file_id: str
    selected_pair_candidate_id: str | None
    left_value: str | None
    right_value: str | None
    confidence: float
    status: str
    rationale: str
    alternative_pair_candidate_ids: list[str] = field(default_factory=list)
    confidence_bucket: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    left_candidate_id: str | None = None
    right_candidate_id: str | None = None
    left_text_id: str | None = None
    right_text_id: str | None = None
    left_coord_x: float | None = None
    left_coord_y: float | None = None
    right_coord_x: float | None = None
    right_coord_y: float | None = None
    pair_key: str | None = None
    left_score: float | None = None
    right_score: float | None = None
    wire_score: float | None = None
    ambiguity_gap: float | None = None
    pair_kind: str = "ordinary_pair"


@dataclass(slots=True)
class ExtractionWarning:
    warning_id: str
    file_id: str | None
    sheet_id: str | None
    stage: str
    code: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class PageClassification:
    """Page Classification Layer 输出（任务书第 4 层）。

    基于几何统计特征判定页型，独立于文件名/sidecar 启发式。
    """

    sheet_id: str
    page_type: str
    page_subtype: str | None
    page_type_confidence: float
    table_like: bool
    grid_heavy: bool
    route_target: str
    features: dict[str, Any] = field(default_factory=dict)
    audit_disposition: str = "classify_only"
    capabilities: tuple[str, ...] = ()
    capability_evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    communication_media: tuple[str, ...] = ()


@dataclass(slots=True)
class Issue:
    issue_id: str
    rule_id: str
    severity: str
    status: str
    confidence: float
    message: str
    sheet_id: str | None
    file_id: str | None
    pair_id: str | None
    line_group_id: str | None
    left_value: str | None
    right_value: str | None
    filename: str | None = None
    sheet_no: str | None = None
    sheet_order: int | None = None
    rationale: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    issue_type: str | None = None
    title: str | None = None
    summary: str | None = None
    explanation: str | None = None
    recommended_action: str | None = None
    primary_pair_id: str | None = None
    related_pair_ids: list[str] = field(default_factory=list)
    sheet_ids: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class Manifest:
    project_id: str
    project_name: str
    created_at: str
    tool_version: str
    input_root: str
    file_count: int
    sheet_count: int
    valid_dwg_files: int
    invalid_dwg_files: int
    config_version: str = "0.1"
    source_files: list[SourceFileRecord] = field(default_factory=list)
    sidecars: list[SidecarInfo] = field(default_factory=list)
    project_name_sources: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectScanResult:
    manifest: Manifest
    pages: list[SheetRecord]
    terminal_strips: list[TerminalStrip]
    project_root: str


@dataclass(slots=True)
class ProjectArtifacts:
    scan: ProjectScanResult
    texts: list[TextItem] = field(default_factory=list)
    lines: list[LineEntity] = field(default_factory=list)
    blocks: list[BlockRecord] = field(default_factory=list)
    polylines: list[PolylineRecord] = field(default_factory=list)
    line_groups: list[LineGroup] = field(default_factory=list)
    terminal_candidates: list[TerminalCandidate] = field(default_factory=list)
    pair_candidates: list[PairCandidate] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    extraction_warnings: list[ExtractionWarning] = field(default_factory=list)
    extractor_runs: list[dict[str, Any]] = field(default_factory=list)
    reader_runs: list[Any] = field(default_factory=list)
    primitive_segments: list[Any] = field(default_factory=list)
    extraction_censuses: list[dict[str, Any]] = field(default_factory=list)
    canonical_scenes: list[dict[str, Any]] = field(default_factory=list)
    symbol_port_definition_proposals: list[dict[str, Any]] = field(
        default_factory=list
    )


def record_dict(instance: Any) -> dict[str, Any]:
    return asdict(instance)
