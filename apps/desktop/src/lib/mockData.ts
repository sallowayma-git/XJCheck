import { makeCanvasTransform, type PreviewExtent } from "./previewGeometry"
import type { AnalyzeSessionResult, IssueLocation, IssueSummary, PreviewPayload, ProjectResult, RecentProject, SidecarEvent } from "../types"

/** 演示用图纸（与 getMockPreview 的图号标题一致）。 */
const MOCK_SHEETS: Record<string, { sheetNo: string; title: string; filename: string; order: number }> = {
  S0005: { sheetNo: "05", title: "差动保护回路图", filename: "05 差动保护回路图.dwg", order: 5 },
  S0008: { sheetNo: "08", title: "差动保护及信号回路", filename: "08 差动保护及信号回路.dwg", order: 8 },
  S0009: { sheetNo: "09", title: "断路器控制回路", filename: "09 断路器控制回路.dwg", order: 9 },
  S0012: { sheetNo: "12", title: "调压信号回路", filename: "12 调压信号回路.dwg", order: 12 },
  S0014: { sheetNo: "14", title: "备用回路图", filename: "14 备用回路图.dwg", order: 14 },
  S0016: { sheetNo: "16", title: "调压控制回路", filename: "16 调压控制回路.dwg", order: 16 },
}

type MockLocationInput = {
  id: string
  role: IssueLocation["role"]
  sheetId: string
  terminal?: string | null
  peer?: string | null
  pairId?: string | null
  /** 导线端点 [x1, y1, x2, y2]，无导线时为 null */
  wire?: [number, number, number, number] | null
  bbox: [number, number, number, number] | null
  lineGroupId?: string | null
  renderable?: boolean
}

function mockLocation(input: MockLocationInput): IssueLocation {
  const sheet = MOCK_SHEETS[input.sheetId]
  const wire = input.wire
    ? {
        line_group_id: input.lineGroupId ?? null,
        start: [input.wire[0], input.wire[1]],
        end: [input.wire[2], input.wire[3]],
      }
    : null
  return {
    location_id: input.id,
    role: input.role,
    sheet_id: input.sheetId,
    file_id: `F${sheet.sheetNo}`,
    filename: sheet.filename,
    sheet_no: sheet.sheetNo,
    sheet_title: sheet.title,
    sheet_order: sheet.order,
    terminal: input.terminal ?? null,
    peer: input.peer ?? null,
    text_id: null,
    point: input.bbox ? [(input.bbox[0] + input.bbox[2]) / 2, (input.bbox[1] + input.bbox[3]) / 2] : null,
    wire,
    bbox: input.bbox,
    pair_id: input.pairId ?? null,
    renderable: input.renderable ?? Boolean(input.bbox),
  }
}

type MockIssueInput = {
  id: string
  rule: string
  issueType: string
  title: string
  summary: string
  explanation: string
  action: string
  severity: string
  handling: "error" | "warning" | "review"
  confidence: number
  sheetId: string
  left: string | null
  right: string | null
  pairId?: string
  evidence?: Record<string, unknown>
  locations: IssueLocation[]
}

const MOCK_HANDLING_LABEL: Record<MockIssueInput["handling"], string> = {
  error: "确定性错误",
  warning: "可能有错误",
  review: "须人工校验",
}

function makeMockIssue(input: MockIssueInput): IssueSummary {
  const primary = MOCK_SHEETS[input.sheetId]
  const sheetIds = Array.from(
    new Set(input.locations.map((location) => location.sheet_id).filter((value): value is string => Boolean(value))),
  )
  return {
    issue_id: input.id,
    rule_id: input.rule,
    issue_type: input.issueType,
    title: input.title,
    summary: input.summary,
    explanation: input.explanation,
    recommended_action: input.action,
    severity: input.severity,
    status: "open",
    confidence: input.confidence,
    sheet_id: input.sheetId,
    file_id: `F${primary.sheetNo}`,
    filename: primary.filename,
    sheet_no: primary.sheetNo,
    line_group_id: input.locations[0]?.wire?.line_group_id ?? null,
    left_value: input.left,
    right_value: input.right,
    primary_pair_id: input.pairId ?? null,
    related_pair_ids: [],
    sheet_ids: sheetIds,
    values: [input.left, input.right].filter((value): value is string => Boolean(value)),
    evidence_refs: [],
    one_to_many_classification: null,
    handling_class: input.handling,
    handling_label: MOCK_HANDLING_LABEL[input.handling],
    review_group_id: `${input.rule}|${input.sheetId}`,
    review_group_label: input.title,
    review_group_size: 1,
    issue_family: input.title,
    evidence: {
      filename: primary.filename,
      sheet_no: primary.sheetNo,
      sheet_title: primary.title,
      handling_class: input.handling,
      ...(input.evidence ?? {}),
    },
    locations: input.locations,
  }
}

const mockIssues: IssueSummary[] = [
  makeMockIssue({
    id: "I0101",
    rule: "R-CROSS-PAGE-CONFLICT",
    issueType: "cross_page_conflict",
    title: "跨页端子冲突",
    summary: "同一端子在两张图上接到了不同的端子。",
    explanation: "端子 521 在图 12 接到 622，在图 16 却接到 623，两处应一致。",
    action: "核对两张图的实际接线，以正确一方为准修改另一张图上的对端端子号。",
    severity: "critical",
    handling: "error",
    confidence: 0.92,
    sheetId: "S0012",
    left: "521",
    right: "622",
    pairId: "P0121",
    locations: [
      mockLocation({
        id: "L0101-a",
        role: "conflict_party",
        sheetId: "S0012",
        terminal: "521",
        peer: "622",
        pairId: "P0121",
        wire: [300, 200, 420, 200],
        bbox: [280, 180, 440, 220],
        lineGroupId: "G0121",
      }),
      mockLocation({
        id: "L0101-b",
        role: "other_party",
        sheetId: "S0016",
        terminal: "521",
        peer: "623",
        pairId: "P0161",
        wire: [260, 300, 380, 300],
        bbox: [240, 280, 400, 320],
        lineGroupId: "G0161",
      }),
    ],
  }),
  makeMockIssue({
    id: "I0102",
    rule: "R-SUPERWORKS-CONFLICT",
    issueType: "superworks_conflict",
    title: "端子图形重叠",
    summary: "同一位置有两个重叠的端子图形。",
    explanation: "两个端子图块位置几乎重合，其中一个没有编号。",
    action: "到图上确认该处只有一个端子；若是重复绘制，删除多余图块或补上端子编号。",
    severity: "major",
    handling: "review",
    confidence: 0.68,
    sheetId: "S0005",
    left: "无编号",
    right: null,
    evidence: { reason_codes: ["competing_physical_port_instances"] },
    locations: [
      mockLocation({
        id: "L0102-a",
        role: "unnumbered_symbol",
        sheetId: "S0005",
        terminal: "无编号",
        bbox: [120, 300, 190, 340],
      }),
    ],
  }),
  makeMockIssue({
    id: "I0103",
    rule: "R-TABLE-MAPPING-SOURCE-CONFLICT",
    issueType: "table_mapping_source_conflict",
    title: "端子表与图内连线不一致",
    summary: "端子表与图内连线对同一端子的记录不一致。",
    explanation: "端子表记录 207 接 305，图内连线显示 207 接 306。",
    action: "核对端子表与图内连线，修正记录不一致的一方。",
    severity: "critical",
    handling: "error",
    confidence: 0.88,
    sheetId: "S0008",
    left: "207",
    right: "305",
    locations: [
      mockLocation({
        id: "L0103-a",
        role: "table_row",
        sheetId: "S0008",
        terminal: "207",
        peer: "305",
        bbox: null,
        renderable: false,
      }),
      mockLocation({
        id: "L0103-b",
        role: "wire",
        sheetId: "S0008",
        terminal: "207",
        peer: "306",
        wire: [400, 135, 480, 135],
        bbox: [384, 118, 496, 152],
        lineGroupId: "G0081",
      }),
    ],
  }),
  makeMockIssue({
    id: "I0104",
    rule: "R-MANY-TO-ONE",
    issueType: "many_to_one",
    title: "多对一连接",
    summary: "多个端子接到了同一个端子。",
    explanation: "端子 412 同时被 201 与 318 连接。",
    action: "若是并联或分支，在图上标注保留；否则修正其中一个端子号。",
    severity: "major",
    handling: "warning",
    confidence: 0.8,
    sheetId: "S0005",
    left: "201",
    right: "412",
    pairId: "P0051",
    locations: [
      mockLocation({
        id: "L0104-a",
        role: "wire",
        sheetId: "S0005",
        terminal: "201",
        peer: "412",
        pairId: "P0051",
        wire: [560, 380, 660, 380],
        bbox: [540, 362, 680, 398],
        lineGroupId: "G0051",
      }),
      mockLocation({
        id: "L0104-b",
        role: "wire",
        sheetId: "S0009",
        terminal: "318",
        peer: "412",
        pairId: "P0091",
        wire: [200, 420, 300, 420],
        bbox: [180, 402, 320, 438],
        lineGroupId: "G0091",
      }),
    ],
  }),
  makeMockIssue({
    id: "I0105",
    rule: "R-PAIR-MISSING-SIDE",
    issueType: "pair_missing_side",
    title: "导线缺一端端子号",
    summary: "导线只识别到一端的端子号。",
    explanation: "导线另一端没有识别到端子号。",
    action: "到图上确认导线另一端的端子号，并补全标注。",
    severity: "major",
    handling: "review",
    confidence: 0.6,
    sheetId: "S0014",
    left: "631",
    right: null,
    evidence: { reason_codes: ["port_unlabeled"] },
    locations: [
      mockLocation({
        id: "L0105-a",
        role: "wire",
        sheetId: "S0014",
        terminal: "631",
        peer: null,
        wire: [300, 170, 400, 170],
        bbox: [284, 152, 416, 188],
        lineGroupId: "G0141",
      }),
    ],
  }),
  makeMockIssue({
    id: "I0106",
    rule: "R-PAIR-LOW-CONFIDENCE",
    issueType: "pair_low_confidence",
    title: "端子配对不确定",
    summary: "1CD2 的两个备选配对把握都不高。",
    explanation: "1CD2 两侧的候选端子相差不大，程序无法自动定论。",
    action: "打开图纸对照两端端子号，确认是否配对正确；若正确可标为已处理。",
    severity: "review",
    handling: "review",
    confidence: 0.74,
    sheetId: "S0005",
    left: "1CD2",
    right: "101",
    pairId: "P0001",
    locations: [
      mockLocation({
        id: "L0106-a",
        role: "wire",
        sheetId: "S0005",
        terminal: "1CD2",
        peer: "101",
        pairId: "P0001",
        wire: [120, 236, 200, 236],
        bbox: [108, 222, 212, 250],
        lineGroupId: "G0001",
      }),
      mockLocation({
        id: "L0106-b",
        role: "wire",
        sheetId: "S0005",
        terminal: "1CD2",
        peer: "201",
        pairId: "P0002",
        wire: [190, 252, 270, 252],
        bbox: [178, 238, 282, 266],
        lineGroupId: "G0002",
      }),
    ],
  }),
]


const mockRecentProjects: RecentProject[] = [
  {
    run_id: "mock-session:wbh-demo",
    session_id: "mock-session",
    project_id: "wbh-demo",
    project_name: "110kV变压器保护柜",
    input_root: "F:\\workspace\\XJToolkit\\test\\110kV变压器保护柜",
    artifact_dir: "F:\\workspace\\XJToolkit\\.tmp\\desktop_sessions\\mock-session\\110kV变压器保护柜",
    updated_at: "2026-07-05T02:30:00+08:00",
    status: "completed",
    sheet_count: 24,
    pair_count: 585,
    issue_count: 482,
  },
]

const mockProjectResults: Record<string, ProjectResult> = {
  "wbh-demo": {
    run: {
      ...mockRecentProjects[0],
      created_at: "2026-07-05T02:10:00+08:00",
      metadata: {
        include_audit: true,
        manifest_warnings: ["Duplicate sheet numbers detected; use sheet_order as the stable order."],
      },
    },
    issues: mockIssues,
    series_chains: {
      schema_version: "1.0",
      chain_count: 1,
      continuation_count: 0,
      chains: [
        {
          junction_kind: "device_terminal_series",
          junction_value: "1UD1",
          member_count: 1,
          members: [
            {
              pair_id: "PCK0002",
              sheet_id: "S0019",
              filename: "19 元件接线图1.dwg",
              role: "component_side",
            },
          ],
          continuations: [],
        },
      ],
    },
    page_findings: [
      {
        sheet_id: "S0005",
        file_id: "F0005",
        filename: "05 差动保护回路图.dwg",
        sheet_no: "05",
        sheet_order: 5,
        sheet_title: "差动保护回路图",
        page_type: "二次原理图",
        page_type_confidence: 0.9,
        audit_role: "primary",
        route_target: "WireDiagramExtractor",
        layout_summary: {
          layout_name: "Model",
          page_no_source: "filename",
        },
        structure_summary: {
          line_group_count: 1,
          pair_count: 1,
          issue_count: 1,
        },
        recognition_strategy: "Use wire-diagram routing with horizontal line grouping.",
        number_matching_strategy: "Use endpoint windows around horizontal line groups.",
        high_confidence_signals: ["Primary audit page with direct line evidence."],
        open_questions: ["Competing right-side candidates still require manual review."],
        warnings: [],
      },
    ],
  },
}

export function getMockRecentProjects(): RecentProject[] {
  return structuredClone(mockRecentProjects)
}

export function getMockProjectResult(projectId: string): ProjectResult {
  const result = mockProjectResults[projectId] ?? mockProjectResults["wbh-demo"]
  return structuredClone(result)
}

const MOCK_CANVAS = { width: 960, height: 540 }

/** 某张图上演示问题的连线（来自 locations 中的 wire），与后端一样以 CAD 坐标（y 向上）给出。 */
function mockWiresOnSheet(sheetId: string): Array<{ x1: number; y1: number; x2: number; y2: number; start: string; end: string }> {
  const wires: Array<{ x1: number; y1: number; x2: number; y2: number; start: string; end: string }> = []
  for (const issue of mockIssues) {
    for (const location of issue.locations ?? []) {
      if (location.sheet_id !== sheetId || !location.wire) {
        continue
      }
      const [x1, y1] = location.wire.start ?? [0, 0]
      const [x2, y2] = location.wire.end ?? [0, 0]
      wires.push({ x1, y1, x2, y2, start: location.terminal ?? "", end: location.peer ?? "" })
    }
  }
  return wires
}

/** 取景范围：围绕框外扩并夹在图幅之内；无框时为整张图。 */
function mockExtent(boxes: number[][]): PreviewExtent {
  if (!boxes.length) {
    return [0, 0, MOCK_CANVAS.width, MOCK_CANVAS.height]
  }
  const margin = 70
  return [
    Math.max(0, Math.min(...boxes.map((box) => box[0])) - margin),
    Math.max(0, Math.min(...boxes.map((box) => box[1])) - margin),
    Math.min(MOCK_CANVAS.width, Math.max(...boxes.map((box) => box[2])) + margin),
    Math.min(MOCK_CANVAS.height, Math.max(...boxes.map((box) => box[3])) + margin),
  ]
}

/** 与 preview.py 一致：先按取景范围做坐标变换，再绘制图元与框。 */
function buildMockPreviewSvg(sheetId: string, extent: PreviewExtent, boxes: number[][]): string {
  const { sx, sy } = makeCanvasTransform(extent)
  const sheet = MOCK_SHEETS[sheetId]
  const title = sheet ? `图 ${sheet.sheetNo} ${sheet.title}` : "未标注图纸"
  const parts: string[] = []
  parts.push(`<rect x="0" y="0" width="${MOCK_CANVAS.width}" height="${MOCK_CANVAS.height}" fill="#fffdf8" />`)
  parts.push(
    `<text x="18" y="34" font-size="20" font-family="Segoe UI, sans-serif" fill="#18120c">${title}</text>`,
  )
  const [x0, y0, x1, y1] = extent
  parts.push(
    `<rect x="${sx(x0)}" y="${sy(y1)}" width="${sx(x1) - sx(x0)}" height="${sy(y0) - sy(y1)}" fill="none" stroke="#e4d9c6" stroke-width="1" />`,
  )
  for (const wire of mockWiresOnSheet(sheetId)) {
    parts.push(
      `<line x1="${sx(wire.x1)}" y1="${sy(wire.y1)}" x2="${sx(wire.x2)}" y2="${sy(wire.y2)}" stroke="#39342f" stroke-width="3" />`,
    )
    parts.push(`<circle cx="${sx(wire.x1)}" cy="${sy(wire.y1)}" r="4" fill="#39342f" />`)
    parts.push(`<circle cx="${sx(wire.x2)}" cy="${sy(wire.y2)}" r="4" fill="#39342f" />`)
    if (wire.start) {
      parts.push(
        `<text x="${sx(wire.x1) - 16}" y="${sy(wire.y1) - 10}" font-size="18" font-family="Consolas, monospace" fill="#2d2419">${wire.start}</text>`,
      )
    }
    if (wire.end) {
      parts.push(
        `<text x="${sx(wire.x2) + 6}" y="${sy(wire.y2) - 10}" font-size="18" font-family="Consolas, monospace" fill="#2d2419">${wire.end}</text>`,
      )
    }
  }
  boxes.forEach((box, index) => {
    const left = sx(Math.min(box[0], box[2]))
    const right = sx(Math.max(box[0], box[2]))
    const top = sy(Math.max(box[1], box[3]))
    const bottom = sy(Math.min(box[1], box[3]))
    parts.push(
      `<rect data-focus-index="${index}" x="${left}" y="${top}" width="${right - left}" height="${bottom - top}" fill="rgba(176,45,32,0.08)" stroke="#b02d20" stroke-width="3" />`,
    )
    if (boxes.length > 1) {
      parts.push(
        `<text x="${left + 4}" y="${top + 15}" font-size="14" font-weight="700" fill="#b02d20" font-family="Segoe UI, sans-serif">${String.fromCharCode(65 + index)}</text>`,
      )
    }
  })
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${MOCK_CANVAS.width}" height="${MOCK_CANVAS.height}" viewBox="0 0 ${MOCK_CANVAS.width} ${MOCK_CANVAS.height}">${parts.join("")}</svg>`
}

export function getMockPreview(
  projectId: string,
  issueId: string | null,
  requestId = "mock-preview",
  sheetId: string | null = null,
  focus: number[][] | null = null,
): PreviewPayload {
  const result = getMockProjectResult(projectId)
  const issue = issueId ? result.issues.find((item) => item.issue_id === issueId) ?? null : null
  const resolvedSheet = sheetId ?? issue?.sheet_id ?? "S0005"
  const boxes = (focus ?? []).filter((box) => box.length === 4)
  const extent = mockExtent(boxes)
  const svg = buildMockPreviewSvg(resolvedSheet, extent, boxes)
  return {
    request_id: requestId,
    project_id: projectId,
    sheet_id: resolvedSheet,
    issue_id: issue?.issue_id ?? null,
    preview_path: null,
    preview_src: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
    artifact_dir: result.run.artifact_dir,
    focus_bbox: extent,
    initial_focus_bbox: extent,
    cropped_to_issue: boxes.length > 0,
    viewport_scale: 1,
  }
}

const DEMO_PAGE_TITLES = [
  "电源回路图",
  "差动保护回路图",
  "跳闸回路图",
  "合闸回路图",
  "信号回路图",
  "测量回路图",
  "控制回路图",
  "直流回路图",
]
const DEMO_PAGE_COUNT = 24
const DEMO_FAILED_PAGE = 14

/**
 * 演示模式（浏览器 mock）的模拟运行：按页推进，部分页面按需分流到 V1 / V2。
 * `demo_route` 只在 mock 事件中出现，真实 sidecar 事件不含分流信息。
 */
export async function emitMockAnalyzeSessionEvents(
  inputRoot: string,
  onEvent: (event: SidecarEvent) => void,
): Promise<AnalyzeSessionResult> {
  const project = getMockRecentProjects()[0]
  const emit = async (event: SidecarEvent, wait: number) => {
    onEvent(event)
    await delay(wait)
  }

  await emit(
    {
      event: "run_started",
      session_id: "mock-session",
      input_root: inputRoot,
      workspace_root: "F:\\workspace\\XJToolkit\\.tmp\\desktop_sessions\\mock-session",
      include_audit: true,
    },
    120,
  )
  await emit({ event: "project_started", project_root: inputRoot }, 120)
  await emit(
    {
      event: "progress",
      stage: "scan",
      file_count: 28,
      sheet_count: DEMO_PAGE_COUNT,
      project_root: inputRoot,
    },
    260,
  )

  for (let index = 1; index <= DEMO_PAGE_COUNT; index += 1) {
    const order = String(index).padStart(2, "0")
    const filename = `${order} ${DEMO_PAGE_TITLES[(index - 1) % DEMO_PAGE_TITLES.length]}.dwg`
    const fileId = `F${String(index).padStart(4, "0")}`
    await emit({ event: "page_started", stage: "convert", file_id: fileId, filename, sheet_order: index }, 240)
    if (index === DEMO_FAILED_PAGE) {
      await emit(
        {
          event: "warning",
          stage: "convert",
          file_id: fileId,
          filename,
          message: "Non-standard DWG header; using cached findings for review only.",
        },
        60,
      )
      await emit({ event: "page_finished", stage: "convert", file_id: fileId, filename, status: "failed_invalid_header" }, 260)
      continue
    }
    const demoRoute = index % 4 === 1 ? "v1" : index % 4 === 3 ? "v2" : null
    await emit(
      {
        event: "page_finished",
        stage: "convert",
        file_id: fileId,
        filename,
        status: "converted",
        dxf_path: `F:\\workspace\\XJToolkit\\.tmp\\mock\\${fileId}.dxf`,
        demo_route: demoRoute,
      },
      260,
    )
  }

  await emit(
    {
      event: "progress",
      stage: "extract",
      text_count: 3025,
      line_count: 1887,
      block_count: 42,
      polyline_count: 211,
      warning_count: 3,
      project_root: inputRoot,
    },
    900,
  )
  await emit(
    {
      event: "progress",
      stage: "pair",
      line_group_count: 585,
      terminal_candidate_count: 3025,
      pair_candidate_count: 623,
      pair_count: 585,
      project_root: inputRoot,
    },
    1000,
  )

  for (const issue of mockIssues.slice(0, 3)) {
    await emit(
      {
        event: "issue_found",
        project_dir: project.artifact_dir,
        issue_id: issue.issue_id,
        rule_id: issue.rule_id,
        severity: issue.severity,
        title: issue.title,
        filename: issue.filename,
        sheet_no: issue.sheet_no,
        left_value: issue.left_value,
        right_value: issue.right_value,
        confidence: issue.confidence,
        issue_type: issue.issue_type,
        one_to_many_classification: issue.one_to_many_classification,
      },
      300,
    )
  }

  await emit(
    {
      event: "progress",
      stage: "audit",
      pair_count: 585,
      issue_count: project.issue_count,
      project_dir: project.artifact_dir,
    },
    700,
  )
  const demoProject: RecentProject = { ...project, coverage_ratio: 0.967 }
  await emit(
    {
      event: "project_stored",
      session_id: demoProject.session_id,
      run_id: demoProject.run_id,
      project_id: demoProject.project_id,
      project_name: demoProject.project_name,
      artifact_dir: demoProject.artifact_dir,
      sheet_count: demoProject.sheet_count,
      pair_count: demoProject.pair_count,
      issue_count: demoProject.issue_count,
      coverage_ratio: demoProject.coverage_ratio,
    },
    500,
  )
  await emit(
    {
      event: "run_finished",
      session_id: demoProject.session_id,
      project_count: 1,
      projects: [demoProject],
    },
    0,
  )

  return { projects: [demoProject] }
}

function delay(ms: number): Promise<void> {
  if (ms <= 0) {
    return Promise.resolve()
  }
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
