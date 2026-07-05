export type IssueStatus = "open" | "ignored" | "resolved" | "false_positive" | string

export type RecentProject = {
  run_id: string
  session_id: string
  project_id: string
  project_name: string
  input_root: string
  artifact_dir: string
  updated_at: string
  status: string
  sheet_count: number
  pair_count: number
  issue_count: number
}

export type ProjectRun = RecentProject & {
  created_at?: string
  metadata?: Record<string, unknown>
}

export type IssueSummary = {
  issue_id: string
  rule_id: string
  issue_type: string
  title: string
  summary: string
  explanation: string
  recommended_action: string
  severity: string
  status: IssueStatus
  confidence: number
  sheet_id: string | null
  file_id: string | null
  filename: string
  sheet_no: string
  line_group_id: string | null
  left_value: string | null
  right_value: string | null
  primary_pair_id: string | null
  related_pair_ids: string[]
  sheet_ids: string[]
  values: string[]
  evidence_refs: Record<string, unknown>[]
  one_to_many_classification: string | null
  evidence: Record<string, unknown>
}

export type PageFindingSummary = {
  sheet_id: string
  file_id: string | null
  filename: string
  sheet_no: string | null
  sheet_order: number
  sheet_title: string
  page_type: string
  page_type_confidence: number
  audit_role: string
  route_target: string
  layout_summary: Record<string, unknown>
  structure_summary: Record<string, unknown>
  recognition_strategy: string
  number_matching_strategy: string
  high_confidence_signals: string[]
  open_questions: string[]
  warnings: string[]
}

export type ProjectResult = {
  run: ProjectRun
  issues: IssueSummary[]
  page_findings: PageFindingSummary[]
}

export type PreviewPayload = {
  project_id: string
  sheet_id: string | null
  issue_id: string | null
  preview_path?: string | null
  preview_src: string | null
  artifact_dir?: string
}

export type AnalyzeSessionRequest = {
  inputRoot: string
  sessionId?: string | null
}

export type AnalyzeSessionResult = {
  projects: RecentProject[]
}

export type RunStageCard = {
  stage: string
  label: string
  detail: string
  done: boolean
}

export type RunStartedEvent = {
  event: "run_started"
  session_id: string
  input_root: string
  workspace_root: string
  include_audit: boolean
}

export type ProjectStartedEvent = {
  event: "project_started"
  project_root: string
}

export type ProjectArtifactsReadyEvent = {
  event: "project_artifacts_ready"
  session_id: string
  project_dir: string
}

export type ProgressEvent = {
  event: "progress"
  stage: string
  project_root?: string
  project_dir?: string
  file_count?: number
  sheet_count?: number
  text_count?: number
  line_count?: number
  block_count?: number
  polyline_count?: number
  warning_count?: number
  line_group_count?: number
  terminal_candidate_count?: number
  pair_candidate_count?: number
  pair_count?: number
  issue_count?: number
}

export type PageStartedEvent = {
  event: "page_started"
  stage: string
  file_id: string
  filename: string
  sheet_order?: number
}

export type PageFinishedEvent = {
  event: "page_finished"
  stage: string
  file_id: string
  filename: string
  status: string
  dxf_path?: string | null
}

export type WarningEvent = {
  event: "warning"
  stage: string
  file_id?: string
  filename?: string
  message: string
}

export type IssueFoundEvent = {
  event: "issue_found"
  project_dir?: string
  issue_id: string
  rule_id: string
  issue_type?: string
  severity: string
  title: string
  filename?: string
  sheet_no?: string
  left_value?: string | null
  right_value?: string | null
  confidence?: number
  one_to_many_classification?: string | null
}

export type AuditFinishedEvent = {
  event: "audit_finished"
  project_dir: string
  audit_dir?: string
  issue_count: number
}

export type ProjectStoredEvent = {
  event: "project_stored"
  session_id: string
  run_id: string
  project_id: string
  project_name: string
  artifact_dir: string
  sheet_count: number
  pair_count: number
  issue_count: number
}

export type RunFinishedEvent = {
  event: "run_finished"
  session_id: string
  project_count: number
  projects: RecentProject[]
}

export type SidecarEvent =
  | RunStartedEvent
  | ProjectStartedEvent
  | ProjectArtifactsReadyEvent
  | ProgressEvent
  | PageStartedEvent
  | PageFinishedEvent
  | WarningEvent
  | IssueFoundEvent
  | AuditFinishedEvent
  | ProjectStoredEvent
  | RunFinishedEvent
