import { convertFileSrc, invoke, isTauri } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
import { open } from "@tauri-apps/plugin-dialog"
import type { UnlistenFn } from "@tauri-apps/api/event"

import { emitMockAnalyzeSessionEvents, getMockPreview, getMockProjectResult, getMockRecentProjects } from "./mockData"
import type { AnalyzeSessionRequest, AnalyzeSessionResult, IssueStatus, PreviewPayload, ProjectResult, RecentProject, SidecarEvent } from "../types"

const DESKTOP_EVENT_NAME = "dwg-audit://sidecar-event"

const COMMANDS = {
  analyzeSession: "desktop_analyze_session",
  listRecentProjects: "desktop_list_recent_projects",
  loadResult: "desktop_load_result",
  renderPreview: "desktop_render_preview",
  setIssueStatus: "desktop_set_issue_status",
} as const

const mockIssueStatuses = new Map<string, IssueStatus>()

export const desktopApi = {
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
      throw toDesktopError("Failed to run native analyze-session.", error)
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
      throw toDesktopError("Failed to load native recent projects.", error)
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
      throw toDesktopError(`Failed to load native result for project ${projectId}.`, error)
    }
  },

  async renderPreview(projectId: string, issueId: string | null, sheetId: string | null = null): Promise<PreviewPayload> {
    if (!isTauri()) {
      return getMockPreview(projectId, issueId)
    }

    try {
      const payload = await invoke<Omit<PreviewPayload, "preview_src"> & { preview_src?: string | null }>(COMMANDS.renderPreview, {
        projectId,
        issueId,
        sheetId,
      })
      return normalizePreviewPayload(payload)
    } catch (error) {
      throw toDesktopError(`Failed to render native preview for project ${projectId}.`, error)
    }
  },

  async setIssueStatus(projectId: string, issueId: string, status: IssueStatus): Promise<ProjectResult> {
    if (!isTauri()) {
      mockIssueStatuses.set(`${projectId}:${issueId}`, status)
      return applyMockStatusOverrides(getMockProjectResult(projectId))
    }

    try {
      await invoke(COMMANDS.setIssueStatus, {
        projectId,
        issueId,
        status,
      })
      return await this.loadResult(projectId)
    } catch (error) {
      throw toDesktopError(`Failed to update native issue status for ${issueId}.`, error)
    }
  },

  async pickProjectDirectory(defaultPath?: string | null): Promise<string | null> {
    if (!isTauri()) {
      return null
    }

    try {
      const selected = await open({
        title: "Select DWG project directory",
        directory: true,
        multiple: false,
        defaultPath: defaultPath?.trim() || undefined,
      })
      if (Array.isArray(selected)) {
        return typeof selected[0] === "string" ? selected[0] : null
      }
      return typeof selected === "string" ? selected : null
    } catch (error) {
      throw toDesktopError("Failed to open native directory picker.", error)
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
      right_value: issue.right_value ?? null,
      evidence: issue.evidence ?? {},
    })),
  }
}

function normalizePreviewPayload(payload: Omit<PreviewPayload, "preview_src"> & { preview_src?: string | null }): PreviewPayload {
  return {
    ...payload,
    preview_src: payload.preview_src ?? (payload.preview_path ? convertFileSrc(payload.preview_path) : null),
  }
}

function toDesktopError(prefix: string, error: unknown): Error {
  if (error instanceof Error) {
    return new Error(`${prefix} ${error.message}`)
  }
  return new Error(prefix)
}
