import { convertFileSrc, invoke, isTauri } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
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
      console.warn("Falling back to mock analyze-session flow.", error)
      return emitMockAnalyzeSessionEvents(request.inputRoot, onEvent)
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
      console.warn("Falling back to mock recent projects.", error)
      return getMockRecentProjects()
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
      console.warn("Falling back to mock project result.", error)
      return applyMockStatusOverrides(getMockProjectResult(projectId))
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
      console.warn("Falling back to mock preview.", error)
      return getMockPreview(projectId, issueId)
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
      console.warn("Falling back to mock issue-status update.", error)
      mockIssueStatuses.set(`${projectId}:${issueId}`, status)
      return applyMockStatusOverrides(getMockProjectResult(projectId))
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
      confidence: Number(issue.confidence ?? 0),
      left_value: issue.left_value ?? null,
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
