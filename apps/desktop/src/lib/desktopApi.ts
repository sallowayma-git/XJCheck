import { convertFileSrc, invoke, isTauri } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
import { open } from "@tauri-apps/plugin-dialog"
import type { UnlistenFn } from "@tauri-apps/api/event"

import { emitMockAnalyzeSessionEvents, getMockPreview, getMockProjectResult, getMockRecentProjects } from "./mockData"
import type { AnalyzeSessionRequest, AnalyzeSessionResult, DiagnosticPage, IssueDetail, IssueFilterOptions, IssuePage, IssueQuery, IssueStats, IssueStatus, IssueSummary, PreviewPayload, ProjectResult, ProjectSummary, RecentProject, SidecarEvent } from "../types"
import type { DesktopSettings } from "./settings"
import { defaultSettings, normalizeSettings } from "./settings"
import { createSerialQueue, humanizeDeleteErrorMessage, type ProjectDeleteOutcome } from "./projectDeletion"

const DESKTOP_EVENT_NAME = "dwg-audit://sidecar-event"

const COMMANDS = {
  analyzeSession: "desktop_analyze_session",
  listRecentProjects: "desktop_list_recent_projects",
  loadResult: "desktop_load_result",
  loadResultSummary: "desktop_load_result_summary",
  loadResultIssues: "desktop_load_result_issues",
  loadResultDiagnostics: "desktop_load_result_diagnostics",
  loadResultIssueDetail: "desktop_load_result_issue_detail",
  cancelResultLoad: "desktop_cancel_result_load",
  registerPreviewSession: "desktop_register_preview_session",
  renderPreview: "desktop_render_preview",
  cancelPreview: "desktop_cancel_preview",
  setIssueStatus: "desktop_set_issue_status",
  deleteProjects: "desktop_delete_projects",
  cleanupWorkspaces: "desktop_cleanup_workspaces",
  readSettings: "desktop_read_settings",
  writeSettings: "desktop_write_settings",
} as const

const mockIssueStatuses = new Map<string, IssueStatus>()

// Every delete goes through one queue so two deletes never race for the sidecar workspace lease.
const enqueueProjectDelete = createSerialQueue()

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
      throw new Error(humanizeAnalyzeErrorMessage(error))
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

  async loadResult(
    projectId: string,
    runId: string | null = null,
    requestGeneration: number | null = null,
    clientSessionId: string | null = null,
    clientSessionEpoch: number | null = null,
  ): Promise<ProjectResult> {
    if (!isTauri()) {
      return applyMockStatusOverrides(getMockProjectResult(projectId))
    }

    try {
      const result = await invoke<ProjectResult>(COMMANDS.loadResult, {
        projectId,
        runId,
        requestGeneration,
        clientSessionId,
        clientSessionEpoch,
      })
      return normalizeProjectResult(result)
    } catch (error) {
      throw toDesktopError("加载校验结果失败。", error)
    }
  },

  async loadResultSummary(
    projectId: string,
    runId: string | null = null,
    requestGeneration: number | null = null,
    clientSessionId: string | null = null,
    clientSessionEpoch: number | null = null,
  ): Promise<ProjectSummary> {
    if (!isTauri()) {
      const mock = getMockProjectResult(projectId)
      return {
        run: mock.run,
        issue_count: mock.issues.length,
        page_finding_count: mock.page_findings.length,
        issue_stats: mockIssueStats(mock.issues),
        filter_options: mockIssueFilterOptions(mock.issues),
      }
    }
    try {
      const summary = await invoke<ProjectSummary>(COMMANDS.loadResultSummary, {
        projectId,
        runId,
        requestGeneration,
        clientSessionId,
        clientSessionEpoch,
      })
      return { ...summary, run: normalizeRecentProject(summary.run) }
    } catch (error) {
      throw toDesktopError("加载项目概要失败。", error)
    }
  },

  async loadResultIssues(
    projectId: string,
    limit: number,
    offset = 0,
    runId: string | null = null,
    requestGeneration: number | null = null,
    clientSessionId: string | null = null,
    clientSessionEpoch: number | null = null,
    filters: IssueQuery = {},
  ): Promise<IssuePage> {
    if (!isTauri()) {
      const mock = applyMockStatusOverrides(getMockProjectResult(projectId))
      const safeLimit = Math.max(1, Math.min(Math.trunc(limit), mock.issues.length) || 1)
      const safeOffset = Math.max(0, Math.trunc(offset))
      const filtered = mock.issues.filter((issue) => matchesMockIssue(issue, filters))
      return {
        run: mock.run,
        items: filtered.slice(safeOffset, safeOffset + safeLimit),
        total: filtered.length,
        limit: safeLimit,
        offset: safeOffset,
      }
    }
    try {
      const page = await invoke<IssuePage>(COMMANDS.loadResultIssues, {
        projectId,
        runId,
        limit,
        offset: offset || null,
        requestGeneration,
        clientSessionId,
        clientSessionEpoch,
        search: filters.search ?? null,
        severity: filters.severity ?? null,
        ruleId: filters.rule_id ?? null,
        statusFilter: filters.status ?? null,
        triage: filters.triage ?? null,
        handling: filters.handling ?? null,
      })
      return {
        run: normalizeRecentProject(page.run),
        items: page.items.map(normalizeIssueSummary),
        total: Number(page.total ?? page.items.length),
        limit: Number(page.limit ?? limit),
        offset: Number(page.offset ?? offset),
      }
    } catch (error) {
      throw toDesktopError("加载问题列表失败。", error)
    }
  },

  async loadResultDiagnostics(
    projectId: string,
    limit = 100,
    offset = 0,
    runId: string | null = null,
  ): Promise<DiagnosticPage> {
    if (!isTauri()) {
      const mock = getMockProjectResult(projectId)
      return {
        run: mock.run,
        items: [],
        total: 0,
        limit,
        offset,
        recognition_summary: {
          coverage_ratio: null,
          unclosed_count: 0,
          diagnostic_count: 0,
          by_rule: {},
          by_presentation: {},
          by_reason_code: {},
          by_observation_reason_code: {},
          suppressed_count: 0,
          suppressed_by: {},
          by_page: [],
        },
      }
    }
    try {
      const page = await invoke<DiagnosticPage>(COMMANDS.loadResultDiagnostics, {
        projectId,
        runId,
        limit,
        offset,
      })
      return {
        ...page,
        run: normalizeRecentProject(page.run),
        items: page.items.map(normalizeIssueSummary),
        total: Number(page.total ?? page.items.length),
        limit: Number(page.limit ?? limit),
        offset: Number(page.offset ?? offset),
      }
    } catch (error) {
      throw toDesktopError("加载诊断明细失败。", error)
    }
  },

  async loadResultIssueDetail(
    projectId: string,
    issueId: string,
    runId: string | null = null,
    requestGeneration: number | null = null,
    clientSessionId: string | null = null,
    clientSessionEpoch: number | null = null,
  ): Promise<IssueDetail | null> {
    if (!isTauri()) {
      const mock = applyMockStatusOverrides(getMockProjectResult(projectId))
      const issue = mock.issues.find((item) => item.issue_id === issueId) ?? null
      return issue ? { run: mock.run, issue } : null
    }
    try {
      const payload = await invoke<IssueDetail | null>(COMMANDS.loadResultIssueDetail, {
        projectId,
        runId,
        issueId,
        requestGeneration,
        clientSessionId,
        clientSessionEpoch,
      })
      if (!payload) {
        return null
      }
      return { run: normalizeRecentProject(payload.run), issue: normalizeIssueSummary(payload.issue) }
    } catch (error) {
      throw toDesktopError("加载问题详情失败。", error)
    }
  },

  async cancelResultLoad(
    requestGeneration: number,
    clientSessionId: string | null = null,
    clientSessionEpoch: number | null = null,
  ): Promise<boolean> {
    if (!isTauri()) {
      return true
    }
    const payload = await invoke<{ cancelled?: boolean }>(COMMANDS.cancelResultLoad, {
      requestGeneration,
      clientSessionId,
      clientSessionEpoch,
    })
    return payload.cancelled === true
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
    runId: string | null = null,
    focus: number[][] | null = null,
  ): Promise<PreviewPayload> {
    if (!isTauri()) {
      return getMockPreview(projectId, issueId, requestId, sheetId, focus)
    }

    try {
      const payload = await invoke<Omit<PreviewPayload, "preview_src"> & { preview_src?: string | null }>(COMMANDS.renderPreview, {
        projectId,
        runId,
        issueId,
        sheetId,
        lineGroupId,
        requestId,
        requestGeneration,
        clientSessionId,
        clientSessionEpoch,
        // 与 locations[i].bbox 同一 CAD 坐标系；无框时传 null（Rust Option<String>）
        focusJson: focus && focus.length ? JSON.stringify(focus) : null,
      })
      const normalized = normalizePreviewPayload(payload)
      if (normalized.request_id !== requestId) {
        throw new Error("Preview response ownership mismatch.")
      }
      if (normalized.project_id !== projectId || normalized.issue_id !== issueId) {
        throw new Error("Preview response target mismatch.")
      }
      if (runId !== null && normalized.run_id !== runId) {
        throw new Error("Preview response run mismatch.")
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

  async setIssueStatus(projectId: string, issueId: string, status: IssueStatus, runId: string | null = null): Promise<void> {
    if (!isTauri()) {
      mockIssueStatuses.set(`${projectId}:${issueId}`, status)
      return
    }

    try {
      await invoke(COMMANDS.setIssueStatus, {
        projectId,
        runId,
        issueId,
        status,
      })
    } catch (error) {
      throw toDesktopError("保存处理状态失败。", error)
    }
  },

  /**
   * Deletes project records, one outcome per requested id. Never rejects: a
   * whole-call failure (for example the workspace is busy) is reported as a
   * failure for every id, so the caller can roll each one back.
   */
  async deleteProjects(projectIds: readonly string[]): Promise<ProjectDeleteOutcome[]> {
    const ids = [...projectIds]
    if (ids.length === 0) {
      return []
    }
    if (!isTauri()) {
      return ids.map((projectId) => ({ project_id: projectId, ok: true, not_found: false, error: null }))
    }
    return enqueueProjectDelete(async () => {
      try {
        const payload = await invoke<{ results?: Array<Partial<ProjectDeleteOutcome>> }>(COMMANDS.deleteProjects, {
          projectIds: ids,
        })
        const byId = new Map((payload.results ?? []).map((item) => [String(item.project_id ?? ""), item]))
        return ids.map((projectId) => {
          const item = byId.get(projectId)
          if (!item) {
            return { project_id: projectId, ok: false, not_found: false, error: "删除结果缺失。" }
          }
          return {
            project_id: projectId,
            ok: item.ok === true,
            not_found: item.not_found === true,
            error: item.ok === true ? null : humanizeDeleteErrorMessage(String(item.error ?? "")),
          }
        })
      } catch (error) {
        const message = error instanceof Error ? humanizeDeleteErrorMessage(error.message) : "删除项目记录失败。"
        return ids.map((projectId) => ({ project_id: projectId, ok: false, not_found: false, error: message }))
      }
    })
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

function mockIssueStats(issues: IssueSummary[]): IssueStats {
  const stats: IssueStats = {
    total: issues.length,
    open_count: 0,
    serious_open_count: 0,
    resolved_count: 0,
    error_count: 0,
    warning_count: 0,
    review_count: 0,
    group_count: new Set(issues.map((issue) => issue.review_group_id || issue.issue_id)).size,
  }
  for (const issue of issues) {
    const handling = issue.handling_class || "review"
    if (handling === "error") stats.error_count += 1
    else if (handling === "warning") stats.warning_count += 1
    else stats.review_count += 1
    if (issue.status === "open") {
      stats.open_count += 1
      if (["critical", "error", "high", "major"].includes(issue.severity) || handling === "error") {
        stats.serious_open_count += 1
      }
    } else if (issue.status === "resolved") {
      stats.resolved_count += 1
    }
  }
  return stats
}

function mockIssueFilterOptions(issues: IssueSummary[]): IssueFilterOptions {
  return {
    severities: [...new Set(issues.map((issue) => issue.severity))].sort(),
    rules: [...new Set(issues.map((issue) => issue.rule_id))].sort(),
    statuses: [...new Set(issues.map((issue) => issue.status))].sort(),
    triages: [...new Set(issues.map((issue) => issue.one_to_many_classification).filter(Boolean) as string[])].sort(),
  }
}

function matchesMockIssue(issue: IssueSummary, filters: IssueQuery): boolean {
  if (filters.severity && filters.severity !== "all" && issue.severity !== filters.severity) return false
  if (filters.rule_id && filters.rule_id !== "all" && issue.rule_id !== filters.rule_id) return false
  if (filters.status && filters.status !== "all" && issue.status !== filters.status) return false
  const triage = issue.one_to_many_classification ?? (typeof issue.evidence?.one_to_many_classification === "string" ? issue.evidence.one_to_many_classification : null)
  if (filters.triage && filters.triage !== "all" && triage !== filters.triage) return false
  const handling = issue.handling_class || (typeof issue.evidence?.handling_class === "string" ? issue.evidence.handling_class : "review")
  if (filters.handling && filters.handling !== "all" && handling !== filters.handling) return false
  const search = String(filters.search || "").trim().toLowerCase()
  if (!search) return true
  return [
    issue.title,
    issue.summary,
    issue.explanation,
    issue.recommended_action,
    issue.filename,
    issue.sheet_no,
    issue.left_value || "",
    issue.right_value || "",
    issue.rule_id,
    issue.issue_type,
    issue.values.join(" "),
    JSON.stringify(issue.evidence),
  ]
    .join(" ")
    .toLowerCase()
    .includes(search)
}

function normalizeIssueSummary(issue: IssueSummary): IssueSummary {
  return {
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
  }
}

function normalizeProjectResult(result: ProjectResult): ProjectResult {
  return {
    run: normalizeRecentProject(result.run),
    issues: result.issues.map(normalizeIssueSummary),
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
    series_chains: result.series_chains ?? null,
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

/** 带可展示原因的操作错误：message 仍是 “前缀 + 原因”，detail 单独给界面在下方展示。 */
export class DesktopOperationError extends Error {
  readonly prefix: string
  readonly detail: string | null

  constructor(prefix: string, detail: string | null) {
    super(detail ? `${prefix} ${detail}` : prefix)
    this.name = "DesktopOperationError"
    this.prefix = prefix
    this.detail = detail
  }
}

function toDesktopError(prefix: string, error: unknown): Error {
  if (error instanceof Error) {
    const message = humanizeDesktopErrorMessage(error.message)
    return new DesktopOperationError(prefix, message || null)
  }
  return new DesktopOperationError(prefix, null)
}

function humanizeAnalyzeErrorMessage(error: unknown): string {
  const text = error instanceof Error ? error.message.trim() : String(error ?? "").trim()
  if (!text) {
    return "审计未能完成，请检查所选项目目录后重试。"
  }

  const lower = text.toLowerCase()
  const knownCauses: Array<[string, string]> = [
    ["snapshot projects must have unique run ids", "多个子项目生成了重名结果目录，本次结果未保存；请更新应用后重试。"],
    ["an incomplete batch cannot replace the successful snapshot", "部分图纸未能完整提取，本次未替换已有校验结果；请检查失败图纸后重试。"],
    ["a project without drawing pages", "所选目录中没有找到可用的 DWG 图纸，请选择包含图纸的项目目录。"],
    ["input path not found", "找不到所选项目文件夹，请确认路径存在且磁盘已连接。"],
    ["config path not found", "找不到审计配置文件，请检查配置后重试。"],
    ["database is locked", "本机校验数据库正被另一个任务占用，请等待当前任务结束后重试。"],
    ["database disk image is malformed", "本机校验数据库无法读取；原有会话文件未被自动删除，请联系支持并提供日志。"],
    ["no such column", "本机旧版校验数据库升级未完成；已有会话数据未被自动删除，请检查数据库权限后重启应用。"],
    ["failed to start dwg audit sidecar", "未能启动本地图纸审计引擎，请修复或重新安装程序后重试。"],
    ["permission", "程序没有访问项目或会话数据的权限，请检查文件夹权限后重试。"],
    ["access is denied", "程序没有访问项目或会话数据的权限，请检查文件夹权限后重试。"],
    ["timed out", "审计处理超时，项目文件仍保留；请检查磁盘状态后重试。"],
    ["timeout", "审计处理超时，项目文件仍保留；请检查磁盘状态后重试。"],
  ]
  const match = knownCauses.find(([needle]) => lower.includes(needle))
  if (match) {
    return match[1]
  }

  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  const exceptionLine = [...lines].reverse().find((line) =>
    /^(?:[A-Za-z_][\w.]*Error|Exception):\s*.+$/i.test(line),
  )
  const diagnostic = exceptionLine ?? lines[lines.length - 1] ?? text
  const compact = diagnostic.replace(/\s+/g, " ").slice(0, 280)
  if (lower.includes("traceback") || exceptionLine) {
    return `审计未能完成，错误详情：${compact}。请根据该原因检查项目文件或运行环境后重试。`
  }
  return `审计未能完成，原因：${compact}。请检查所选项目目录和本机运行环境后重试。`
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
