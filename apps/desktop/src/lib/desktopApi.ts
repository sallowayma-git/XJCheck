import { convertFileSrc, invoke, isTauri } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
import { open } from "@tauri-apps/plugin-dialog"
import type { UnlistenFn } from "@tauri-apps/api/event"

import { emitMockAnalyzeSessionEvents, getMockPreview, getMockProjectResult, getMockRecentProjects } from "./mockData"
import type { AnalyzeSessionRequest, AnalyzeSessionResult, IssueStatus, PreviewPayload, ProjectResult, RecentProject, SidecarEvent } from "../types"
import type { DesktopSettings } from "./settings"
import { defaultSettings, normalizeSettings } from "./settings"

const DESKTOP_EVENT_NAME = "dwg-audit://sidecar-event"

const COMMANDS = {
  analyzeSession: "desktop_analyze_session",
  listRecentProjects: "desktop_list_recent_projects",
  loadResult: "desktop_load_result",
  registerPreviewSession: "desktop_register_preview_session",
  renderPreview: "desktop_render_preview",
  cancelPreview: "desktop_cancel_preview",
  setIssueStatus: "desktop_set_issue_status",
  deleteProject: "desktop_delete_project",
  cleanupWorkspaces: "desktop_cleanup_workspaces",
  readSettings: "desktop_read_settings",
  writeSettings: "desktop_write_settings",
} as const

const mockIssueStatuses = new Map<string, IssueStatus>()

export type DesktopRuntimeMode = "native" | "browser-mock"

export const desktopApi = {
  runtimeMode(): DesktopRuntimeMode {
    return isTauri() ? "native" : "browser-mock"
  },

  isNative(): boolean {
    return isTauri()
  },

  async analyzeSession(request: AnalyzeSessionRequest, onEvent: (event: SidecarEvent) => void): Promise<AnalyzeSessionResult> {
    if (!isTauri()) {
      return emitMockAnalyzeSessionEvents(request.inputRoot, onEvent)
    }

    let unlisten: UnlistenFn | null = null
    try {
      unlisten = await listen<SidecarEvent>(DESKTOP_EVENT_NAME, (event) => onEvent(event.payload))
      const payload = await invoke<AnalyzeSessionResult>(COMMANDS.analyzeSession, {
        inputRoot: request.inputRoot,
        sessionId: request.sessionId ?? null,
      })
      return {
        projects: payload.projects.map(normalizeRecentProject),
      }
    } catch (error) {
      throw toDesktopError("审计任务启动失败。", error)
    } finally {
      unlisten?.()
    }
  },

  async listRecentProjects(): Promise<RecentProject[]> {
    if (!isTauri()) {
      return getMockRecentProjects()
    }

    try {
      const projects = await invoke<RecentProject[]>(COMMANDS.listRecentProjects)
      return projects.map(normalizeRecentProject)
    } catch (error) {
      throw toDesktopError("读取最近项目失败。", error)
    }
  },

  async loadResult(projectId: string): Promise<ProjectResult> {
    if (!isTauri()) {
      return applyMockStatusOverrides(getMockProjectResult(projectId))
    }

    try {
      const result = await invoke<ProjectResult>(COMMANDS.loadResult, { projectId })
      return normalizeProjectResult(result)
    } catch (error) {
      throw toDesktopError("加载校验结果失败。", error)
    }
  },

  async registerPreviewSession(clientSessionId: string): Promise<number> {
    if (!isTauri()) {
      return 0
    }

    try {
      const payload = await invoke<{ client_session_id?: string; client_session_epoch?: number }>(COMMANDS.registerPreviewSession, {
        clientSessionId,
      })
      if (payload.client_session_id !== clientSessionId || !Number.isSafeInteger(payload.client_session_epoch)) {
        throw new Error("Preview session registration mismatch.")
      }
      return payload.client_session_epoch as number
    } catch (error) {
      throw toDesktopError("无法初始化图纸预览。", error)
    }
  },

  async renderPreview(
    projectId: string,
    issueId: string | null,
    requestId: string,
    requestGeneration: number,
    sheetId: string | null = null,
    lineGroupId: string | null = null,
    clientSessionId: string | null = null,
    clientSessionEpoch: number | null = null,
  ): Promise<PreviewPayload> {
    if (!isTauri()) {
      return getMockPreview(projectId, issueId, requestId)
    }

    try {
      const payload = await invoke<Omit<PreviewPayload, "preview_src"> & { preview_src?: string | null }>(COMMANDS.renderPreview, {
        projectId,
        issueId,
        sheetId,
        lineGroupId,
        requestId,
        requestGeneration,
        clientSessionId,
        clientSessionEpoch,
      })
      const normalized = normalizePreviewPayload(payload)
      if (normalized.request_id !== requestId) {
        throw new Error("Preview response ownership mismatch.")
      }
      if (normalized.project_id !== projectId || normalized.issue_id !== issueId) {
        throw new Error("Preview response target mismatch.")
      }
      if (sheetId !== null && normalized.sheet_id !== sheetId) {
        throw new Error("Preview response sheet mismatch.")
      }
      return normalized
    } catch (error) {
      throw toDesktopError("无法生成图纸预览。", error)
    }
  },

  async cancelPreview(
    requestId: string,
    requestGeneration: number,
    clientSessionId: string | null = null,
    clientSessionEpoch: number | null = null,
  ): Promise<boolean> {
    if (!isTauri()) {
      return true
    }
    const payload = await invoke<{ cancelled?: boolean }>(COMMANDS.cancelPreview, {
      requestId,
      requestGeneration,
      clientSessionId,
      clientSessionEpoch,
    })
    return payload.cancelled === true
  },

  async setIssueStatus(projectId: string, issueId: string, status: IssueStatus): Promise<void> {
    if (!isTauri()) {
      mockIssueStatuses.set(`${projectId}:${issueId}`, status)
      return
    }

    try {
      await invoke(COMMANDS.setIssueStatus, {
        projectId,
        issueId,
        status,
      })
    } catch (error) {
      throw toDesktopError("保存处理状态失败。", error)
    }
  },

  async deleteProject(projectId: string): Promise<void> {
    if (!isTauri()) {
      return
    }
    try {
      await invoke(COMMANDS.deleteProject, { projectId })
    } catch (error) {
      throw toDesktopError("删除项目记录失败。", error)
    }
  },

  async cleanupWorkspaces(): Promise<void> {
    if (!isTauri()) {
      return
    }
    try {
      await invoke(COMMANDS.cleanupWorkspaces)
    } catch (error) {
      throw toDesktopError("清理过程文件失败。", error)
    }
  },

  async readSettings(): Promise<DesktopSettings> {
    if (!isTauri()) {
      return defaultSettings()
    }
    try {
      const raw = await invoke<unknown>(COMMANDS.readSettings)
      return normalizeSettings(raw)
    } catch (error) {
      throw toDesktopError("读取设置失败。", error)
    }
  },

  async writeSettings(next: DesktopSettings): Promise<DesktopSettings> {
    if (!isTauri()) {
      return next
    }
    try {
      const raw = await invoke<unknown>(COMMANDS.writeSettings, { settings: next })
      return normalizeSettings(raw)
    } catch (error) {
      throw toDesktopError("保存设置失败。", error)
    }
  },

  async pickProjectDirectory(defaultPath?: string | null): Promise<string | null> {
    if (!isTauri()) {
      return null
    }

    try {
      const selected = await open({
        title: "选择 DWG 项目目录",
        directory: true,
        multiple: false,
        defaultPath: defaultPath?.trim() || undefined,
      })
      if (Array.isArray(selected)) {
        return typeof selected[0] === "string" ? selected[0] : null
      }
      return typeof selected === "string" ? selected : null
    } catch (error) {
      throw toDesktopError("打开目录选择器失败。", error)
    }
  },
}

function applyMockStatusOverrides(result: ProjectResult): ProjectResult {
  const next = structuredClone(result)
  next.issues = next.issues.map((issue) => ({
    ...issue,
    status: mockIssueStatuses.get(`${next.run.project_id}:${issue.issue_id}`) ?? issue.status,
  }))
  return next
}

function normalizeRecentProject(project: RecentProject): RecentProject {
  return {
    ...project,
    sheet_count: Number(project.sheet_count ?? 0),
    pair_count: Number(project.pair_count ?? 0),
    issue_count: Number(project.issue_count ?? 0),
  }
}

function normalizeProjectResult(result: ProjectResult): ProjectResult {
  return {
    run: normalizeRecentProject(result.run),
    issues: result.issues.map((issue) => ({
      ...issue,
      issue_type: issue.issue_type ?? issue.rule_id,
      summary: issue.summary ?? issue.title ?? "",
      explanation: issue.explanation ?? "",
      recommended_action: issue.recommended_action ?? "",
      confidence: Number(issue.confidence ?? 0),
      sheet_id: issue.sheet_id ?? null,
      file_id: issue.file_id ?? null,
      left_value: issue.left_value ?? null,
      line_group_id: issue.line_group_id ?? null,
      primary_pair_id: issue.primary_pair_id ?? null,
      related_pair_ids: Array.isArray(issue.related_pair_ids) ? issue.related_pair_ids.map(String) : [],
      sheet_ids: Array.isArray(issue.sheet_ids) ? issue.sheet_ids.map(String) : [],
      values: Array.isArray(issue.values) ? issue.values.map(String) : [],
      evidence_refs: Array.isArray(issue.evidence_refs) ? issue.evidence_refs : [],
      one_to_many_classification:
        issue.one_to_many_classification ??
        (typeof issue.evidence?.one_to_many_classification === "string" ? issue.evidence.one_to_many_classification : null),
      handling_class:
        issue.handling_class ??
        (typeof issue.evidence?.handling_class === "string" ? issue.evidence.handling_class : null) ??
        deriveHandlingClass(issue),
      handling_label:
        issue.handling_label ??
        (typeof issue.evidence?.handling_label === "string" ? issue.evidence.handling_label : null) ??
        labelHandlingClass(
          issue.handling_class ??
            (typeof issue.evidence?.handling_class === "string" ? issue.evidence.handling_class : null) ??
            deriveHandlingClass(issue),
        ),
      review_group_id:
        issue.review_group_id ??
        (typeof issue.evidence?.review_group_id === "string" ? issue.evidence.review_group_id : null) ??
        issue.issue_id,
      review_group_label:
        issue.review_group_label ??
        (typeof issue.evidence?.review_group_label === "string" ? issue.evidence.review_group_label : null) ??
        issue.title,
      review_group_size: Number(
        issue.review_group_size ??
          (typeof issue.evidence?.review_group_size === "number" ? issue.evidence.review_group_size : 1) ??
          1,
      ),
      issue_family:
        issue.issue_family ??
        (typeof issue.evidence?.issue_family === "string" ? issue.evidence.issue_family : null) ??
        issue.title,
      right_value: issue.right_value ?? null,
      evidence: issue.evidence ?? {},
    })),
    page_findings: Array.isArray(result.page_findings)
      ? result.page_findings.map((pageFinding) => ({
          ...pageFinding,
          file_id: pageFinding.file_id ?? null,
          sheet_no: pageFinding.sheet_no ?? null,
          sheet_order: Number(pageFinding.sheet_order ?? 0),
          page_type_confidence: Number(pageFinding.page_type_confidence ?? 0),
          layout_summary: pageFinding.layout_summary ?? {},
          structure_summary: pageFinding.structure_summary ?? {},
          high_confidence_signals: Array.isArray(pageFinding.high_confidence_signals)
            ? pageFinding.high_confidence_signals.map(String)
            : [],
          open_questions: Array.isArray(pageFinding.open_questions)
            ? pageFinding.open_questions.map(String)
            : [],
          warnings: Array.isArray(pageFinding.warnings) ? pageFinding.warnings.map(String) : [],
        }))
      : [],
  }
}

function normalizePreviewPayload(payload: Omit<PreviewPayload, "preview_src"> & { preview_src?: string | null }): PreviewPayload {
  // Prefer inline SVG data URL: avoids asset-protocol file locks and WebView stalls.
  let rawPreviewSrc: string | null = payload.preview_src ?? null
  if (!rawPreviewSrc && payload.preview_svg) {
    rawPreviewSrc = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(payload.preview_svg)}`
  }
  if (!rawPreviewSrc && payload.preview_path) {
    rawPreviewSrc = convertFileSrc(payload.preview_path)
  }
  return {
    ...payload,
    preview_src: rawPreviewSrc ? withCacheBust(rawPreviewSrc) : null,
  }
}

function toDesktopError(prefix: string, error: unknown): Error {
  if (error instanceof Error) {
    const message = humanizeDesktopErrorMessage(error.message)
    return new Error(message ? `${prefix} ${message}` : prefix)
  }
  return new Error(prefix)
}

function humanizeDesktopErrorMessage(message: string): string {
  const text = message.trim()
  if (!text) {
    return ""
  }
  const lower = text.toLowerCase()
  if (lower.includes("no stored result") || lower.includes("no stored issue")) {
    return "未找到对应校验结果，请重新打开项目。"
  }
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "操作超时，请稍后重试。"
  }
  if (lower.includes("permission") || lower.includes("access is denied")) {
    return "没有访问权限，请检查目录权限。"
  }
  if (lower.includes("not found") || lower.includes("enoent")) {
    return "未找到相关文件或目录。"
  }
  // Drop raw stack / path-heavy technical noise when it dominates.
  if (/traceback|exception|at\s+\S+\(|error:\s*error/i.test(text)) {
    return "请稍后重试；若仍失败可重新校验该项目。"
  }
  return text
}

function withCacheBust(src: string): string {
  // Data URLs must not receive query params; browsers treat them as part of the payload.
  if (src.startsWith("data:")) {
    return src
  }
  const separator = src.includes("?") ? "&" : "?"
  return `${src}${separator}v=${Date.now()}`
}

function deriveHandlingClass(issue: {
  rule_id?: string
  severity?: string
  confidence?: number
  evidence?: Record<string, unknown>
  one_to_many_classification?: string | null
}): string {
  const evidence = issue.evidence ?? {}
  const triage = String(
    issue.one_to_many_classification ||
      evidence.one_to_many_classification ||
      evidence.many_to_one_classification ||
      "",
  ).toLowerCase()
  if (triage.includes("conflict")) {
    return "error"
  }
  if (triage.includes("branch")) {
    return "warning"
  }
  if (triage.includes("review")) {
    return issue.rule_id === "R-CROSS-PAGE-CONFLICT" || issue.rule_id === "R-TABLE-MAPPING-SOURCE-CONFLICT"
      ? "error"
      : "review"
  }
  const severity = String(issue.severity || "").toLowerCase()
  if (["critical", "error", "high"].includes(severity)) {
    return "error"
  }
  const ruleDefaults: Record<string, string> = {
    "R-CROSS-PAGE-CONFLICT": "error",
    "R-TABLE-MAPPING-SOURCE-CONFLICT": "error",
    "R-SEMANTIC-MAPPING-CONFLICT": "error",
    "R-MISSING-RECIPROCAL": "warning",
    "R-MANY-TO-ONE": "warning",
    "R-DUPLICATE-PAIR": "warning",
    "R-SHEET-PAGE-MISMATCH": "warning",
    "R-ONE-TO-MANY": "warning",
    "R-PAIR-MISSING-SIDE": "review",
    "R-PAIR-LOW-CONFIDENCE": "review",
    "R-DUPLICATE-SAME-LINE": "review",
  }
  const mapped = ruleDefaults[String(issue.rule_id || "")]
  if (mapped) {
    return mapped
  }
  if (["major", "medium", "warning", "warn"].includes(severity)) {
    return "warning"
  }
  return "review"
}

function labelHandlingClass(value: string | null | undefined): string {
  const map: Record<string, string> = {
    error: "确定性错误",
    warning: "可能有错误",
    review: "须人工校验",
  }
  if (!value) {
    return "须人工校验"
  }
  return map[value] ?? value
}
