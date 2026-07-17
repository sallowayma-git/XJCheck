import type { AnalyzeSessionResult, IssueSummary, PreviewPayload, ProjectResult, RecentProject, SidecarEvent } from "../types"

const mockIssues: IssueSummary[] = [
  {
    issue_id: "I0001",
    rule_id: "R-PAIR-LOW-CONFIDENCE",
    issue_type: "pair_low_confidence",
    title: "端子配对不确定",
    summary: "这对端子的识别把握偏低，建议人工看一眼。",
    explanation: "导线两端都能找到候选端子号，但备选相差不大，程序不敢自动定论。",
    recommended_action: "打开图纸对照两端端子号，确认是否配对正确；若正确可标为已处理。",
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
    handling_class: "review",
    handling_label: "须人工校验",
    review_group_id: "review|R-PAIR-LOW-CONFIDENCE|S0005",
    review_group_label: "须人工校验 · 端子配对不确定 · 图号 05 · 共 1 处",
    review_group_size: 1,
    issue_family: "端子配对不确定",
    evidence: {
      filename: "05 差动保护回路图.dwg",
      sheet_no: "05",
      sheet_title: "差动保护回路图",
      line_group_id: "G0001",
      line_start: [124.2, 388.4],
      line_end: [201.5, 388.4],
      line_orientation: "horizontal",
      left_side_label: "left",
      right_side_label: "right",
      handling_class: "review",
      review_group_id: "review|R-PAIR-LOW-CONFIDENCE|S0005",
      review_group_label: "须人工校验 · 端子配对不确定 · 图号 05 · 共 1 处",
      review_group_size: 1,
      issue_family: "端子配对不确定",
    },
  },
  {
    issue_id: "I0002",
    rule_id: "R-ONE-TO-MANY",
    issue_type: "one_to_many",
    title: "一对多连接",
    summary: "同一端子连到多个对端，请确认是正常分支还是画错。",
    explanation: "源端子 307 同时连到 411、412、413。若设计允许分支可忽略；若应一对一则需改图。",
    recommended_action: "对照关联图纸，确认是否合法分支；非法则修正对端端子号。",
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
      {
        pair_id: "P0204",
        sheet_id: "S0008",
        filename: "08 差动保护及信号回路.dwg",
        sheet_no: "08",
        sheet_title: "差动保护及信号回路",
        line_start: [90.0, 210.0],
        line_end: [160.0, 210.0],
      },
      {
        pair_id: "P0205",
        sheet_id: "S0010",
        filename: "10 差动保护跳闸回路.dwg",
        sheet_no: "10",
        sheet_title: "差动保护跳闸回路",
        line_start: [120.0, 180.0],
        line_end: [190.0, 180.0],
      },
    ],
    one_to_many_classification: "branch",
    handling_class: "warning",
    handling_label: "可能有错误",
    review_group_id: "warning|R-ONE-TO-MANY|307",
    review_group_label: "警告 · 一对多连接 · 端子 307 · 共 1 处",
    review_group_size: 1,
    issue_family: "一对多连接",
    evidence: {
      filename: "08 差动保护及信号回路.dwg",
      sheet_no: "08",
      sheet_title: "差动保护及信号回路",
      related_values: ["411", "412", "413"],
      one_to_many_classification: "branch",
      line_start: [90.0, 210.0],
      line_end: [160.0, 210.0],
      handling_class: "warning",
      review_group_id: "warning|R-ONE-TO-MANY|307",
      review_group_label: "警告 · 一对多连接 · 端子 307 · 共 1 处",
      review_group_size: 1,
      issue_family: "一对多连接",
    },
  },
  {
    issue_id: "I0003",
    rule_id: "R-CROSS-PAGE-CONFLICT",
    issue_type: "cross_page_conflict",
    title: "跨页端子冲突",
    summary: "同一端子在不同图纸上对端不一致，优先处理。",
    explanation: "端子 521 在图号 12 连到 622，在图号 16 却连到 623，属于高风险冲突。",
    recommended_action: "先核对相关图纸，确认正确的对端端子，并统一改图。",
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
      {
        pair_id: "P0301",
        sheet_id: "S0012",
        filename: "12 调压信号回路.dwg",
        sheet_no: "12",
        sheet_title: "调压信号回路",
        line_start: [88.0, 142.0],
        line_end: [170.0, 142.0],
      },
      {
        pair_id: "P0410",
        sheet_id: "S0016",
        filename: "16 调压闭锁回路.dwg",
        sheet_no: "16",
        sheet_title: "调压闭锁回路",
      },
    ],
    one_to_many_classification: "conflict",
    handling_class: "error",
    handling_label: "确定性错误",
    review_group_id: "error|R-CROSS-PAGE-CONFLICT|521",
    review_group_label: "错误 · 跨页端子冲突 · 端子 521 · 共 1 处",
    review_group_size: 1,
    issue_family: "跨页端子冲突",
    evidence: {
      filename: "12 调压信号回路.dwg",
      sheet_no: "12",
      sheet_title: "调压信号回路",
      conflict_sheet_ids: ["S0012", "S0016"],
      line_start: [88.0, 142.0],
      line_end: [170.0, 142.0],
      line_orientation: "horizontal",
      left_side_label: "left",
      right_side_label: "right",
      one_to_many_classification: "conflict",
      handling_class: "error",
      review_group_id: "error|R-CROSS-PAGE-CONFLICT|521",
      review_group_label: "错误 · 跨页端子冲突 · 端子 521 · 共 1 处",
      review_group_size: 1,
      issue_family: "跨页端子冲突",
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
