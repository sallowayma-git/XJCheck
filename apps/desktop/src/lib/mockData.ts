import type { AnalyzeSessionResult, IssueSummary, PreviewPayload, ProjectResult, RecentProject, SidecarEvent } from "../types"

const mockIssues: IssueSummary[] = [
  {
    issue_id: "I0001",
    rule_id: "R-PAIR-LOW-CONFIDENCE",
    issue_type: "R-PAIR-LOW-CONFIDENCE",
    title: "Left/right candidate still requires review",
    summary: "Pair remains below automatic pass threshold.",
    explanation: "Left and right endpoint candidates are both present, but the ambiguity gap is still too small.",
    recommended_action: "Inspect both endpoint labels and compare nearby competing candidates.",
    severity: "review",
    status: "open",
    confidence: 0.74,
    sheet_id: "S0005",
    file_id: "F0005",
    filename: "05 差动保护回路图.dwg",
    sheet_no: "05",
    line_group_id: "G0001",
    left_value: "101",
    right_value: "201",
    primary_pair_id: "P0001",
    related_pair_ids: [],
    sheet_ids: ["S0005"],
    values: ["101", "201"],
    evidence_refs: [{ pair_id: "P0001", filename: "05 差动保护回路图.dwg", sheet_no: "05" }],
    one_to_many_classification: null,
    evidence: {
      filename: "05 差动保护回路图.dwg",
      sheet_no: "05",
      line_group_id: "G0001",
      line_start: [124.2, 388.4],
      line_end: [201.5, 388.4],
      line_orientation: "horizontal",
      left_side_label: "left",
      right_side_label: "right",
      candidate_notes: ["left endpoint inside-zone numeric text", "right endpoint vertical offset borderline"],
    },
  },
  {
    issue_id: "I0002",
    rule_id: "R-ONE-TO-MANY",
    issue_type: "R-ONE-TO-MANY",
    title: "One source terminal fans out to competing targets",
    summary: "One-to-many cluster requires branch-style review.",
    explanation: "Multiple candidate targets share the same source value without enough context to auto-resolve them.",
    recommended_action: "Compare the linked sheets and confirm whether this source is an allowed branch.",
    severity: "major",
    status: "ignored",
    confidence: 0.91,
    sheet_id: "S0008",
    file_id: "F0008",
    filename: "08 差动保护及信号回路.dwg",
    sheet_no: "08",
    line_group_id: "G0204",
    left_value: "307",
    right_value: "411",
    primary_pair_id: "P0204",
    related_pair_ids: ["P0205"],
    sheet_ids: ["S0008", "S0010"],
    values: ["307", "411", "412", "413"],
    evidence_refs: [
      { pair_id: "P0204", filename: "08 差动保护及信号回路.dwg", sheet_no: "08" },
      { pair_id: "P0205", filename: "10 差动保护跳闸回路.dwg", sheet_no: "10" },
    ],
    one_to_many_classification: "review",
    evidence: {
      filename: "08 差动保护及信号回路.dwg",
      sheet_no: "08",
      related_values: ["411", "412", "413"],
      one_to_many_classification: "review",
      rationale: "branch candidate requires manual judgement rather than automatic hard error",
    },
  },
  {
    issue_id: "I0003",
    rule_id: "R-CROSS-PAGE-CONFLICT",
    issue_type: "R-CROSS-PAGE-CONFLICT",
    title: "Cross-page mapping conflicts with another sheet",
    summary: "Cross-page mapping conflict is considered high risk.",
    explanation: "The same source value is mapped to different target values on different sheets.",
    recommended_action: "Prioritize these sheets and verify which target is authoritative.",
    severity: "critical",
    status: "resolved",
    confidence: 0.96,
    sheet_id: "S0012",
    file_id: "F0012",
    filename: "12 调压信号回路.dwg",
    sheet_no: "12",
    line_group_id: "G0301",
    left_value: "521",
    right_value: "622",
    primary_pair_id: "P0301",
    related_pair_ids: ["P0410"],
    sheet_ids: ["S0012", "S0016"],
    values: ["521", "622", "623"],
    evidence_refs: [
      { pair_id: "P0301", filename: "12 调压信号回路.dwg", sheet_no: "12" },
      { pair_id: "P0410", filename: "16 调压闭锁回路.dwg", sheet_no: "16" },
    ],
    one_to_many_classification: "conflict",
    evidence: {
      filename: "12 调压信号回路.dwg",
      sheet_no: "12",
      conflict_sheet_ids: ["S0012", "S0016"],
      line_start: [88.0, 142.0],
      line_end: [170.0, 142.0],
      line_orientation: "horizontal",
      left_side_label: "left",
      right_side_label: "right",
      one_to_many_classification: "conflict",
    },
  },
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

const previewSvg = [
  "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
  "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"720\" height=\"420\" viewBox=\"0 0 720 420\">",
  "<rect width=\"720\" height=\"420\" fill=\"#fffdf8\" />",
  "<rect x=\"24\" y=\"24\" width=\"672\" height=\"372\" rx=\"22\" fill=\"#f4ecdf\" stroke=\"#d9c5a8\" />",
  "<line x1=\"112\" y1=\"210\" x2=\"612\" y2=\"210\" stroke=\"#39342f\" stroke-width=\"3\" />",
  "<text x=\"128\" y=\"194\" font-size=\"20\" font-family=\"Consolas, monospace\" fill=\"#2d2419\">101</text>",
  "<text x=\"570\" y=\"194\" font-size=\"20\" font-family=\"Consolas, monospace\" fill=\"#2d2419\">201</text>",
  "<rect x=\"94\" y=\"184\" width=\"536\" height=\"48\" fill=\"rgba(209,31,31,0.05)\" stroke=\"#d11f1f\" stroke-width=\"3\" />",
  "<circle cx=\"112\" cy=\"210\" r=\"6\" fill=\"#d11f1f\" />",
  "<circle cx=\"612\" cy=\"210\" r=\"6\" fill=\"#d11f1f\" />",
  "<text x=\"36\" y=\"58\" font-size=\"22\" font-family=\"Segoe UI, sans-serif\" fill=\"#18120c\">Mock issue preview</text>",
  "<text x=\"36\" y=\"84\" font-size=\"13\" font-family=\"Segoe UI, sans-serif\" fill=\"#6d5d47\">sheet=05 | issue=I0001 | rule=R-PAIR-LOW-CONFIDENCE</text>",
  "</svg>",
].join("")

const previewSrc = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(previewSvg)}`

export function getMockRecentProjects(): RecentProject[] {
  return structuredClone(mockRecentProjects)
}

export function getMockProjectResult(projectId: string): ProjectResult {
  const result = mockProjectResults[projectId] ?? mockProjectResults["wbh-demo"]
  return structuredClone(result)
}

export function getMockPreview(projectId: string, issueId: string | null): PreviewPayload {
  const result = getMockProjectResult(projectId)
  const issue = result.issues.find((item) => item.issue_id === issueId) ?? result.issues[0] ?? null
  return {
    project_id: projectId,
    sheet_id: issue?.sheet_no ?? "05",
    issue_id: issue?.issue_id ?? null,
    preview_path: null,
    preview_src: previewSrc,
    artifact_dir: result.run.artifact_dir,
  }
}

export async function emitMockAnalyzeSessionEvents(
  inputRoot: string,
  onEvent: (event: SidecarEvent) => void,
): Promise<AnalyzeSessionResult> {
  const project = getMockRecentProjects()[0]
  const events: SidecarEvent[] = [
    {
      event: "run_started",
      session_id: "mock-session",
      input_root: inputRoot,
      workspace_root: "F:\\workspace\\XJToolkit\\.tmp\\desktop_sessions\\mock-session",
      include_audit: true,
    },
    {
      event: "project_started",
      project_root: inputRoot,
    },
    {
      event: "progress",
      stage: "scan",
      file_count: 28,
      sheet_count: 24,
      project_root: inputRoot,
    },
    {
      event: "page_started",
      stage: "convert",
      file_id: "F0001",
      filename: "05 差动保护回路图.dwg",
      sheet_order: 5,
    },
    {
      event: "page_finished",
      stage: "convert",
      file_id: "F0001",
      filename: "05 差动保护回路图.dwg",
      status: "converted",
      dxf_path: "F:\\workspace\\XJToolkit\\.tmp\\mock\\F0001.dxf",
    },
    {
      event: "warning",
      stage: "convert",
      file_id: "F0014",
      filename: "14 备用回路图.dwg",
      message: "Non-standard DWG header; using cached findings for review only.",
    },
    {
      event: "page_finished",
      stage: "convert",
      file_id: "F0014",
      filename: "14 备用回路图.dwg",
      status: "failed_invalid_header",
    },
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
    {
      event: "progress",
      stage: "pair",
      line_group_count: 585,
      terminal_candidate_count: 3025,
      pair_candidate_count: 623,
      pair_count: 585,
      project_root: inputRoot,
    },
    {
      event: "issue_found",
      project_dir: project.artifact_dir,
      issue_id: mockIssues[0].issue_id,
      rule_id: mockIssues[0].rule_id,
      severity: mockIssues[0].severity,
      title: mockIssues[0].title,
      filename: mockIssues[0].filename,
      sheet_no: mockIssues[0].sheet_no,
      left_value: mockIssues[0].left_value,
      right_value: mockIssues[0].right_value,
      confidence: mockIssues[0].confidence,
      issue_type: mockIssues[0].issue_type,
      one_to_many_classification: mockIssues[0].one_to_many_classification,
    },
    {
      event: "progress",
      stage: "audit",
      pair_count: 585,
      issue_count: 482,
      project_dir: project.artifact_dir,
    },
    {
      event: "project_stored",
      session_id: project.session_id,
      run_id: project.run_id,
      project_id: project.project_id,
      project_name: project.project_name,
      artifact_dir: project.artifact_dir,
      sheet_count: project.sheet_count,
      pair_count: project.pair_count,
      issue_count: project.issue_count,
    },
    {
      event: "run_finished",
      session_id: project.session_id,
      project_count: 1,
      projects: [project],
    },
  ]

  for (const event of events) {
    onEvent(event)
    await delay(90)
  }

  return { projects: [project] }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
