import { isTauri } from "@tauri-apps/api/core"
import { getCurrentWindow } from "@tauri-apps/api/window"
import { useVirtualizer } from "@tanstack/react-virtual"
import {
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react"

import "./App.css"
import logoUrl from "./assets/logo.png"
import { AuditFlowDiagram, type AuditFlowDot, type AuditFlowCoverage } from "./components/AuditFlowDiagram"
import { desktopApi } from "./lib/desktopApi"
import { IssueInspector, type InspectorTechnicalRow } from "./components/IssueInspector"
import {
  cleanText,
  getIssueLocations,
  resolveSheetName,
  stripDrawingExtension,
  summarizeLocations,
} from "./lib/issueLocations"
import {
  UI_SCALE_DEFAULT,
  UI_SCALE_MAX,
  UI_SCALE_MIN,
  UI_SCALE_STEP,
  applyUiScale,
  clampUiScale,
  loadUiScale,
  persistUiScale,
} from "./lib/uiScale"
import { loadResultToolbarCollapsed, saveResultToolbarCollapsed } from "./lib/viewPrefs"
import {
  beginRequest,
  createRequestGeneration,
  invalidateRequests,
  isCurrentRequest,
  shouldCommitKeyedRequest,
  shouldReloadKeyedRequest,
  shouldInvalidateScreenIntent,
} from "./lib/requestGeneration"
import {
  defaultSettings,
  loadSettings,
  normalizeSettings,
  persistSettings,
  type DesktopSettings,
} from "./lib/settings"
import type { DiagnosticPage, IssueQuery, IssueSummary, ProjectResult, ProjectSummary, RecentProject, RecognitionSummary, RunStageCard, SidecarEvent } from "./types"

type Screen = "launch" | "process" | "result" | "settings"

const ISSUE_STATUS_OPTIONS = ["open", "ignored", "resolved", "false_positive"] as const
const RESULT_ISSUE_PAGE_SIZE = 500

function buildIssueQuery(
  search: string,
  severity: string,
  ruleId: string,
  status: string,
  triage: string,
  handling: string,
): IssueQuery {
  return {
    search: search.trim() || null,
    severity: severity === "all" ? null : severity,
    rule_id: ruleId === "all" ? null : ruleId,
    status: status === "all" ? null : status,
    triage: triage === "all" ? null : triage,
    handling: handling === "all" ? null : handling,
  }
}

function issueQueryKey(query: IssueQuery): string {
  return JSON.stringify([
    query.search ?? "",
    query.severity ?? "",
    query.rule_id ?? "",
    query.status ?? "",
    query.triage ?? "",
    query.handling ?? "",
  ])
}

function updateSummaryIssueStatus(
  summary: ProjectSummary,
  issue: IssueSummary,
  nextStatus: string,
): ProjectSummary {
  if (issue.status === nextStatus) {
    return summary
  }
  const issueStats = { ...summary.issue_stats }
  const serious = isSeriousSeverity(issue.severity) || resolveHandlingClass(issue) === "error"
  if (issue.status === "open") {
    issueStats.open_count = Math.max(0, issueStats.open_count - 1)
    if (serious) issueStats.serious_open_count = Math.max(0, issueStats.serious_open_count - 1)
  } else if (issue.status === "resolved") {
    issueStats.resolved_count = Math.max(0, issueStats.resolved_count - 1)
  }
  if (nextStatus === "open") {
    issueStats.open_count += 1
    if (serious) issueStats.serious_open_count += 1
  } else if (nextStatus === "resolved") {
    issueStats.resolved_count += 1
  }
  const statuses = summary.filter_options.statuses.includes(nextStatus)
    ? summary.filter_options.statuses
    : [...summary.filter_options.statuses, nextStatus].sort()
  return {
    ...summary,
    issue_stats: issueStats,
    filter_options: { ...summary.filter_options, statuses },
  }
}

type ProcessState = {
  sessionId: string | null
  progressRatio: number
  activeStage: string
  totalSheets: number
  currentProjectRoot: string | null
  currentProjectName: string | null
  currentProjectSheetCount: number
  completedPages: number
  failedPages: number
  totalIssueCount: number
  analysisIncomplete: boolean
  failureMessage: string | null
  warningCount: number
  stageCards: RunStageCard[]
  logs: string[]
  liveIssues: IssueSummary[]
  completedProjects: RecentProject[]
  coverageByProject: Array<{ projectName: string; coverageRatio: number | null }>
  flowDots: AuditFlowDot[]
  /** 按需分流页数；真实运行无逐页分流信息时为 null。 */
  routeCounts: { v1: number; v2: number } | null
}

/** 结果页工具栏“处理顺序”提示文字（原常驻说明，现收入 ⓘ 提示）。 */
const RESULT_GUIDE_TEXT = "建议顺序：先处理「确定性错误」，再看「可能有错误」，最后批量确认「须人工校验」。原则：可以误报，但不能错过真实错误。同类问题归到同一处理组。"
const MAX_FLOW_DOTS = 60
/** 浏览器演示模式下模拟运行使用的示例项目路径（仅用于展示名称）。 */
const DEMO_INPUT_ROOT = "F:\\workspace\\XJToolkit\\test\\110kV变压器保护柜"
const MAX_PROCESS_LOG_LINES = 500

type LaunchImportStatusTone = "info" | "ready" | "warn"

type LaunchImportStatus = {
  tone: LaunchImportStatusTone
  message: string
}

function App() {
  const [screen, setScreen] = useState<Screen>("launch")
  const [inputRoot, setInputRoot] = useState("")
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [result, setResult] = useState<ProjectResult | null>(null)
  const [resultSummary, setResultSummary] = useState<ProjectSummary | null>(null)
  const [resultIssueTotal, setResultIssueTotal] = useState(0)
  const [diagnosticItems, setDiagnosticItems] = useState<IssueSummary[]>([])
  const [diagnosticTotal, setDiagnosticTotal] = useState(0)
  const [diagnosticLoadedRunId, setDiagnosticLoadedRunId] = useState<string | null>(null)
  const [isLoadingDiagnostics, setIsLoadingDiagnostics] = useState(false)
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null)
  const [previewClientSessionId] = useState(createPreviewClientSessionId)
  const [previewClientSessionEpoch, setPreviewClientSessionEpoch] = useState<number | null>(null)
  const [, setPreviewClientSessionError] = useState<string | null>(null)
  const [issueSearch, setIssueSearch] = useState("")
  const [severityFilter, setSeverityFilter] = useState("all")
  const [ruleFilter, setRuleFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [triageFilter, setTriageFilter] = useState("all")
  const [handlingFilter, setHandlingFilter] = useState("all")
  const [issueStatusDraft, setIssueStatusDraft] = useState("open")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isPickingDirectory, setIsPickingDirectory] = useState(false)
  const [toolbarCollapsed, setToolbarCollapsed] = useState<boolean>(loadResultToolbarCollapsed)
  const [toolbarGuideOpen, setToolbarGuideOpen] = useState(false)
  const [isSavingIssueStatus, setIsSavingIssueStatus] = useState(false)
  const [isLoadingProjectId, setIsLoadingProjectId] = useState<string | null>(null)
  const [isLoadingMoreIssues, setIsLoadingMoreIssues] = useState(false)
  const [isReloadingIssueQuery, setIsReloadingIssueQuery] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isDropTargetActive, setIsDropTargetActive] = useState(false)
  const [launchImportStatus, setLaunchImportStatus] = useState<LaunchImportStatus | null>(null)
  const [isDeletingProjectId, setIsDeletingProjectId] = useState<string | null>(null)
  const deferredIssueSearch = useDeferredValue(issueSearch)
  const [processState, setProcessState] = useState<ProcessState>({
    sessionId: null,
    progressRatio: 0,
    activeStage: "scan",
    totalSheets: 0,
    currentProjectRoot: null,
    currentProjectName: null,
    currentProjectSheetCount: 0,
    completedPages: 0,
    failedPages: 0,
    totalIssueCount: 0,
    analysisIncomplete: false,
    failureMessage: null,
    warningCount: 0,
    stageCards: defaultStageCards(),
    logs: [],
    liveIssues: [],
    completedProjects: [],
    coverageByProject: [],
    flowDots: [],
    routeCounts: desktopApi.isNative() ? null : { v1: 0, v2: 0 },
  })
  const processEventQueueRef = useRef<SidecarEvent[]>([])
  const processFlushTimerRef = useRef<number | null>(null)
  const logStreamRef = useRef<HTMLPreElement | null>(null)
  const logAutoFollowRef = useRef(true)
  const analysisInFlightRef = useRef(false)
  const projectLoadGenerationRef = useRef(createRequestGeneration())
  const screenIntentGenerationRef = useRef(createRequestGeneration())
  const [uiScale, setUiScale] = useState<number>(loadUiScale)
  const [settings, setSettings] = useState<DesktopSettings>(loadSettings)
  const [settingsSnapshot, setSettingsSnapshot] = useState<DesktopSettings | null>(null)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const selectedProjectIdRef = useRef<string | null>(null)
  const selectedRunIdRef = useRef<string | null>(null)
  const issuePageLoadInFlightRef = useRef<number | null>(null)
  const issuePageQueryKeyRef = useRef<string | null>(null)
  const appliedIssueQueryKeyRef = useRef<string | null>(null)
  const previewClientSessionEpochRef = useRef<number | null>(null)
  const previewClientSessionRegistrationRef = useRef<Promise<number> | null>(null)
  const appDisposedRef = useRef(false)
  const activeIssueQuery = useMemo(
    () =>
      buildIssueQuery(
        deferredIssueSearch,
        severityFilter,
        ruleFilter,
        statusFilter,
        triageFilter,
        handlingFilter,
      ),
    [deferredIssueSearch, handlingFilter, ruleFilter, severityFilter, statusFilter, triageFilter],
  )
  const activeIssueQueryKey = issueQueryKey(activeIssueQuery)
  const activeIssueQueryRef = useRef(activeIssueQuery)
  const activeIssueQueryKeyRef = useRef(activeIssueQueryKey)
  activeIssueQueryRef.current = activeIssueQuery
  activeIssueQueryKeyRef.current = activeIssueQueryKey

  function selectProject(projectId: string | null, runId: string | null = null): void {
    selectedProjectIdRef.current = projectId
    selectedRunIdRef.current = runId
    setSelectedProjectId(projectId)
    setSelectedRunId(runId)
  }

  function navigateToScreen(nextScreen: Screen): void {
    if (shouldInvalidateScreenIntent(screen, nextScreen)) {
      invalidateRequests(screenIntentGenerationRef.current)
    }
    if (isLoadingProjectId) {
      const generation = projectLoadGenerationRef.current.current
      void desktopApi.cancelResultLoad(generation, previewClientSessionId, previewClientSessionEpochRef.current).catch(() => undefined)
      invalidateRequests(projectLoadGenerationRef.current)
      setIsLoadingProjectId(null)
      selectProject(result?.run.project_id ?? null, result?.run.run_id ?? null)
    } else if (screen === "result" && nextScreen !== "result") {
      const generation = projectLoadGenerationRef.current.current
      void desktopApi.cancelResultLoad(generation, previewClientSessionId, previewClientSessionEpochRef.current).catch(() => undefined)
      invalidateRequests(projectLoadGenerationRef.current)
      issuePageLoadInFlightRef.current = null
      issuePageQueryKeyRef.current = null
      setIsLoadingMoreIssues(false)
      setIsReloadingIssueQuery(false)
    }
    setScreen(nextScreen)
  }

  function updateSettingsField(patch: Partial<DesktopSettings>): void {
    setSettings((prev) => {
      return normalizeSettings({ ...prev, ...patch })
    })
  }

  function updateUiScale(next: number): void {
    const clamped = clampUiScale(next)
    setUiScale(clamped)
    applyUiScale(clamped)
    persistUiScale(clamped)
  }

  async function saveSettings(next: DesktopSettings): Promise<void> {
    setSettingsSaving(true)
    setSettingsError(null)
    try {
      const confirmed = await desktopApi.writeSettings(normalizeSettings(next))
      persistSettings(confirmed)
      setSettings(confirmed)
      setSettingsSnapshot(confirmed)
    } catch (error) {
      setSettingsError(error instanceof Error ? error.message : "保存设置失败。")
      throw error
    } finally {
      setSettingsSaving(false)
    }
  }

  async function resetSettings(): Promise<void> {
    await saveSettings(defaultSettings())
  }


  const refreshRecentProjects = useEffectEvent(async () => {
    try {
      const projects = await desktopApi.listRecentProjects()
      setRecentProjects(projects)
      if (!selectedProjectId && projects[0]) {
        selectProject(projects[0].project_id, projects[0].run_id)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "刷新最近项目失败。"
      setLoadError(message)
    }
  })

  useEffect(() => {
    void refreshRecentProjects()
  }, [])

  // On mount, ask the Rust side whether an override file already exists. If
  // yes, its normalized values win over the localStorage defaults so the
  // Settings screen never drifts from what the sidecar actually sees. If the
  // file is missing (the common case) the localStorage defaults stay in effect,
  // which equals the pre-settings behavior exactly.
  useEffect(() => {
    let disposed = false
    void desktopApi
      .readSettings()
      .then((next) => {
        if (!disposed) {
          persistSettings(next)
          setSettings(next)
          setSettingsSnapshot(next)
        }
      })
      .catch(() => {
        // Browser-mock mode has nothing to read; leave defaults in place.
      })
    return () => {
      disposed = true
    }
  }, [])

  const ensurePreviewClientSession = useEffectEvent(async (): Promise<number> => {
    const existing = previewClientSessionEpochRef.current
    if (existing !== null) {
      return existing
    }
    let registration = previewClientSessionRegistrationRef.current
    if (!registration) {
      registration = desktopApi.registerPreviewSession(previewClientSessionId)
      previewClientSessionRegistrationRef.current = registration
    }
    try {
      const epoch = await registration
      if (previewClientSessionRegistrationRef.current === registration) {
        previewClientSessionEpochRef.current = epoch
        if (!appDisposedRef.current) {
          setPreviewClientSessionEpoch(epoch)
          setPreviewClientSessionError(null)
        }
      }
      return epoch
    } catch (error) {
      if (previewClientSessionRegistrationRef.current === registration && !appDisposedRef.current) {
        setPreviewClientSessionError(error instanceof Error ? error.message : "无法初始化图纸预览。")
      }
      throw error
    } finally {
      if (previewClientSessionRegistrationRef.current === registration) {
        previewClientSessionRegistrationRef.current = null
      }
    }
  })

  useEffect(() => {
    void ensurePreviewClientSession().catch(() => undefined)
  }, [previewClientSessionId])

  const applyImportedInputRoot = useEffectEvent((nextPath: string, source: "picker" | "drop") => {
    setInputRoot(nextPath)
    setLoadError(null)
    setLaunchImportStatus({
      tone: "ready",
      message: source === "picker" ? "目录已选定，可开始校验。" : "拖入目录已接收，可开始校验。",
    })
  })

  const handleDroppedPaths = useEffectEvent((paths: string[]) => {
    setIsDropTargetActive(false)
    const droppedPath = pickDroppedInputRoot(paths)
    if (!droppedPath) {
      setLoadError("请一次拖入单个项目文件夹；暂不支持直接拖入单个 DWG 或多个路径。")
      setLaunchImportStatus({
        tone: "warn",
        message: "请拖入一个完整的项目目录，以便扫描与页序保持一致。",
      })
      return
    }
    applyImportedInputRoot(droppedPath, "drop")
  })

  useEffect(() => {
    if (screen !== "launch" || !isTauri()) {
      setIsDropTargetActive(false)
      return
    }

    let disposed = false
    let unlisten: (() => void) | null = null

    void getCurrentWindow()
      .onDragDropEvent((event) => {
        if (event.payload.type === "enter" || event.payload.type === "over") {
          setIsDropTargetActive(true)
          setLaunchImportStatus({
            tone: "info",
            message: "松开鼠标后将该文件夹作为待审计项目。",
          })
          return
        }
        if (event.payload.type === "leave") {
          setIsDropTargetActive(false)
          return
        }
        if (event.payload.type === "drop") {
          handleDroppedPaths(event.payload.paths)
        }
      })
      .then((dispose) => {
        if (disposed) {
          dispose()
          return
        }
        unlisten = dispose
      })
      .catch((error) => {
        const message = error instanceof Error ? error.message : "无法订阅拖放事件。"
        setLoadError(message)
      })

    return () => {
      disposed = true
      unlisten?.()
    }
  }, [screen])

  const loadProjectResult = useEffectEvent(async (projectId: string, runId: string | null = null) => {
    const previousGeneration = projectLoadGenerationRef.current.current
    if (previousGeneration > 0) {
      void desktopApi
        .cancelResultLoad(previousGeneration, previewClientSessionId, previewClientSessionEpochRef.current)
        .catch(() => undefined)
    }
    const generation = beginRequest(projectLoadGenerationRef.current)
    setIsLoadingProjectId(projectId)
    let resultClientSessionEpoch = previewClientSessionEpoch
    if (desktopApi.isNative() && resultClientSessionEpoch === null) {
      try {
        resultClientSessionEpoch = await ensurePreviewClientSession()
      } catch (error) {
        if (isCurrentRequest(projectLoadGenerationRef.current, generation)) {
          setLoadError(error instanceof Error ? error.message : "无法初始化桌面结果会话。")
          setIsLoadingProjectId(null)
        }
        return
      }
    }
    if (appDisposedRef.current || !isCurrentRequest(projectLoadGenerationRef.current, generation)) {
      return
    }
    setIsLoadingMoreIssues(false)
    setIsReloadingIssueQuery(false)
    setResult(null)
    setResultSummary(null)
    setResultIssueTotal(0)
    setDiagnosticItems([])
    setDiagnosticTotal(0)
    setDiagnosticLoadedRunId(null)
    setDiagnosticError(null)
    issuePageLoadInFlightRef.current = null
    issuePageQueryKeyRef.current = null
    appliedIssueQueryKeyRef.current = null
    setLoadError(null)
    try {
      setIssueSearch("")
      setSeverityFilter("all")
      setRuleFilter("all")
      setStatusFilter("all")
      setTriageFilter("all")
      setHandlingFilter("all")
      const summary = await desktopApi.loadResultSummary(
        projectId,
        runId,
        generation,
        previewClientSessionId,
        resultClientSessionEpoch,
      )
      if (!isCurrentRequest(projectLoadGenerationRef.current, generation)) {
        return
      }
      const firstPage = await desktopApi.loadResultIssues(
        projectId,
        RESULT_ISSUE_PAGE_SIZE,
        0,
        summary.run.run_id,
        generation,
        previewClientSessionId,
        resultClientSessionEpoch,
        {},
      )
      if (!isCurrentRequest(projectLoadGenerationRef.current, generation)) {
        return
      }
      if (firstPage.run.run_id !== summary.run.run_id) {
        throw new Error("项目结果在加载期间发生变化，请重试。")
      }
      selectProject(summary.run.project_id, summary.run.run_id)
      const loaded: ProjectResult = {
        run: summary.run,
        issues: firstPage.items,
        page_findings: [],
        series_chains: null,
      }
      setResultSummary(summary)
      setResult(loaded)
      setResultIssueTotal(firstPage.total)
      appliedIssueQueryKeyRef.current = issueQueryKey({})
      const initialIssue = firstPage.items[0] ?? null
      setSelectedIssueId(initialIssue?.issue_id ?? null)
      setScreen("result")
    } catch (error) {
      if (!isCurrentRequest(projectLoadGenerationRef.current, generation)) {
        return
      }
      const message = error instanceof Error ? error.message : "加载项目结果失败，请重试。"
      setLoadError(message)
    } finally {
      if (isCurrentRequest(projectLoadGenerationRef.current, generation)) {
        setIsLoadingProjectId(null)
      }
    }
  })

  const loadDiagnostics = async (offset = 0) => {
    const projectId = result?.run.project_id ?? selectedProjectId
    const runId = result?.run.run_id ?? selectedRunId
    if (!projectId || !runId || isLoadingDiagnostics) {
      return
    }
    setIsLoadingDiagnostics(true)
    setDiagnosticError(null)
    try {
      const requestedRunId = runId
      const page: DiagnosticPage = await desktopApi.loadResultDiagnostics(projectId, 100, offset, requestedRunId)
      if (page.run.run_id !== requestedRunId) {
        return
      }
      setDiagnosticItems((current) => (offset === 0 ? page.items : [...current, ...page.items]))
      setDiagnosticTotal(page.total)
      setDiagnosticLoadedRunId(page.run.run_id)
    } catch (error) {
      setDiagnosticError(error instanceof Error ? error.message : "加载诊断明细失败。")
    } finally {
      setIsLoadingDiagnostics(false)
    }
  }

  const loadMoreIssues = useEffectEvent(async () => {
    const current = result
    const projectId = current?.run.project_id ?? selectedProjectIdRef.current
    const runId = current?.run.run_id
    const generation = projectLoadGenerationRef.current.current
    if (
      !projectId ||
      !runId ||
      !isCurrentRequest(projectLoadGenerationRef.current, generation) ||
      issuePageLoadInFlightRef.current !== null ||
      appliedIssueQueryKeyRef.current !== activeIssueQueryKey ||
      !resultIssueTotal ||
      (current?.issues.length ?? 0) >= resultIssueTotal
    ) {
      return
    }
    const requestGeneration = beginRequest(projectLoadGenerationRef.current)
    const requestQueryKey = activeIssueQueryKey
    issuePageLoadInFlightRef.current = requestGeneration
    issuePageQueryKeyRef.current = requestQueryKey
    setIsLoadingMoreIssues(true)
    const offset = current?.issues.length ?? 0
    try {
      const page = await desktopApi.loadResultIssues(
        projectId,
        RESULT_ISSUE_PAGE_SIZE,
        offset,
        runId,
        requestGeneration,
        previewClientSessionId,
        previewClientSessionEpochRef.current,
        activeIssueQuery,
      )
      if (
        !shouldCommitKeyedRequest(
          projectLoadGenerationRef.current,
          requestGeneration,
          requestQueryKey,
          activeIssueQueryKeyRef.current,
        ) ||
        page.run.run_id !== runId ||
        selectedProjectIdRef.current !== projectId
      ) {
        return
      }
      setResult((previous) => {
        if (!previous || previous.run.run_id !== runId) {
          return previous
        }
        const seen = new Set(previous.issues.map((issue) => issue.issue_id))
        const appended = page.items.filter((issue) => !seen.has(issue.issue_id))
        return { ...previous, issues: [...previous.issues, ...appended] }
      })
      setResultIssueTotal(page.total)
      setLoadError(null)
    } catch (error) {
      if (isCurrentRequest(projectLoadGenerationRef.current, requestGeneration)) {
        setLoadError(error instanceof Error ? error.message : "加载更多问题失败，请重试。")
      }
    } finally {
      if (issuePageLoadInFlightRef.current === requestGeneration) {
        issuePageLoadInFlightRef.current = null
        issuePageQueryKeyRef.current = null
      }
      if (isCurrentRequest(projectLoadGenerationRef.current, requestGeneration)) {
        setIsLoadingMoreIssues(false)
      }
    }
  })

  const reloadIssuesForQuery = useEffectEvent(async (query: IssueQuery, queryKey: string) => {
    const current = result
    const projectId = current?.run.project_id
    const runId = current?.run.run_id
    if (!projectId || !runId) {
      return
    }
    const previousGeneration = issuePageLoadInFlightRef.current
    if (previousGeneration !== null) {
      void desktopApi
        .cancelResultLoad(previousGeneration, previewClientSessionId, previewClientSessionEpochRef.current)
        .catch(() => undefined)
    }
    const generation = beginRequest(projectLoadGenerationRef.current)
    issuePageLoadInFlightRef.current = generation
    issuePageQueryKeyRef.current = queryKey
    setIsReloadingIssueQuery(true)
    setIsLoadingMoreIssues(false)
    setLoadError(null)
    try {
      const page = await desktopApi.loadResultIssues(
        projectId,
        RESULT_ISSUE_PAGE_SIZE,
        0,
        runId,
        generation,
        previewClientSessionId,
        previewClientSessionEpochRef.current,
        query,
      )
      if (
        !shouldCommitKeyedRequest(
          projectLoadGenerationRef.current,
          generation,
          queryKey,
          activeIssueQueryKeyRef.current,
        ) ||
        page.run.run_id !== runId ||
        selectedProjectIdRef.current !== projectId
      ) {
        return
      }
      setResult((previous) =>
        previous?.run.run_id === runId ? { ...previous, issues: page.items } : previous,
      )
      setResultIssueTotal(page.total)
      appliedIssueQueryKeyRef.current = queryKey
      const initialIssue = page.items[0] ?? null
      setSelectedIssueId(initialIssue?.issue_id ?? null)
    } catch (error) {
      if (isCurrentRequest(projectLoadGenerationRef.current, generation)) {
        setLoadError(error instanceof Error ? error.message : "筛选问题列表失败，请重试。")
      }
    } finally {
      if (issuePageLoadInFlightRef.current === generation) {
        issuePageLoadInFlightRef.current = null
        issuePageQueryKeyRef.current = null
      }
      if (isCurrentRequest(projectLoadGenerationRef.current, generation)) {
        setIsReloadingIssueQuery(false)
      }
    }
  })

  useEffect(() => {
    appDisposedRef.current = false
    return () => {
      appDisposedRef.current = true
    }
  }, [])

  useLayoutEffect(() => {
    const logStream = logStreamRef.current
    if (logStream && logAutoFollowRef.current) {
      logStream.scrollTop = logStream.scrollHeight
    }
  }, [processState.logs])

  useEffect(() => {
    if (
      screen !== "result" ||
      !result?.run.run_id ||
      !shouldReloadKeyedRequest(
        appliedIssueQueryKeyRef.current,
        activeIssueQueryKey,
        issuePageQueryKeyRef.current,
      )
    ) {
      return
    }
    const timer = window.setTimeout(() => {
      void reloadIssuesForQuery(activeIssueQuery, activeIssueQueryKey)
    }, 180)
    return () => window.clearTimeout(timer)
  }, [activeIssueQuery, activeIssueQueryKey, result?.run.run_id, screen])

  const applyProcessEvents = useEffectEvent((events: SidecarEvent[]) => {
    if (!events.length) {
      return
    }
    setProcessState((current) => {
      let nextState: ProcessState = {
        ...current,
        logs: [...current.logs],
        stageCards: current.stageCards.map((item) => ({ ...item })),
        liveIssues: [...current.liveIssues],
        completedProjects: [...current.completedProjects],
        coverageByProject: [...current.coverageByProject],
        flowDots: [...current.flowDots],
      }
      for (const event of events) {
        nextState = {
          ...nextState,
          logs: [...nextState.logs, formatSidecarLog(event)].slice(-MAX_PROCESS_LOG_LINES),
        }

        if (event.event === "run_started") {
          nextState.sessionId = event.session_id
        }

        if (event.event === "project_started") {
          nextState.currentProjectRoot = event.project_root
          nextState.currentProjectName = getPathBaseName(event.project_root)
          nextState.currentProjectSheetCount = 0
        }

        if (event.event === "progress") {
          nextState.activeStage = event.stage
          nextState.progressRatio = stageProgress(event.stage)
          if (event.stage === "scan") {
            nextState.totalSheets = event.sheet_count ?? nextState.totalSheets
            nextState.currentProjectSheetCount = event.sheet_count ?? nextState.currentProjectSheetCount
          }
          if (event.stage === "extract") {
            nextState.flowDots = moveProjectFlowDots(
              nextState.flowDots,
              nextState.currentProjectRoot,
              "superworks",
            )
          } else if (event.stage === "pair" || event.stage === "audit") {
            nextState.flowDots = moveProjectFlowDots(
              nextState.flowDots,
              nextState.currentProjectRoot,
              "coordination",
            )
          }
          nextState.stageCards = nextState.stageCards.map((item) =>
            item.stage === event.stage
              ? {
                  ...item,
                  detail: summarizeProgress(event),
                  done: false,
                }
              : stageOrder(item.stage) < stageOrder(event.stage)
                ? { ...item, done: true }
                : item,
          )
        }

        if (event.event === "page_started" && event.stage === "convert") {
          const projectName = nextState.currentProjectName ?? getPathBaseName(nextState.currentProjectRoot ?? inputRoot)
          const id = `${nextState.currentProjectRoot ?? inputRoot}|${event.file_id}`
          const dot: AuditFlowDot = {
            id,
            label: event.sheet_order != null ? `图${event.sheet_order}` : `图${formatLogDrawingName(event.filename)}`,
            title: event.filename,
            projectName,
            projectRoot: nextState.currentProjectRoot ?? inputRoot,
            phase: "input",
            branch: null,
            failed: false,
          }
          nextState.flowDots = [...nextState.flowDots.filter((item) => item.id !== id), dot].slice(-MAX_FLOW_DOTS)
        }

        if (event.event === "page_finished" && event.stage === "convert") {
          nextState.completedPages = nextState.completedPages + 1
          nextState.failedPages = nextState.failedPages + (isFailedPageStatus(event.status) ? 1 : 0)
          const projectName = nextState.currentProjectName ?? getPathBaseName(nextState.currentProjectRoot ?? inputRoot)
          const id = `${nextState.currentProjectRoot ?? inputRoot}|${event.file_id}`
          const existingDot = nextState.flowDots.find((item) => item.id === id)
          // demo_route 只由浏览器演示模式的模拟事件携带；真实事件没有逐页分流信息。
          const branch = event.demo_route ?? null
          if (branch && nextState.routeCounts) {
            nextState.routeCounts = { ...nextState.routeCounts, [branch]: nextState.routeCounts[branch] + 1 }
          }
          const finishedDot: AuditFlowDot = {
            id,
            label: existingDot?.label ?? `图${formatLogDrawingName(event.filename)}`,
            title: event.filename,
            projectName,
            projectRoot: nextState.currentProjectRoot ?? inputRoot,
            phase: "superworks",
            branch,
            failed: isFailedPageStatus(event.status),
          }
          nextState.flowDots = [...nextState.flowDots.filter((item) => item.id !== id), finishedDot].slice(-MAX_FLOW_DOTS)
        }

        if (event.event === "warning") {
          nextState.warningCount = nextState.warningCount + 1
        }

        if (event.event === "incomplete_extraction") {
          nextState.analysisIncomplete = true
        }

        if (event.event === "issue_found") {
          nextState.totalIssueCount += 1
          nextState.liveIssues = [
            {
              issue_id: event.issue_id,
              rule_id: event.rule_id,
              issue_type: event.issue_type ?? event.rule_id,
              title: event.title,
              summary: event.title,
              explanation: "",
              recommended_action: "",
              severity: event.severity,
              status: "open",
              confidence: event.confidence ?? 0,
              sheet_id: null,
              file_id: null,
              filename: event.filename ?? "",
              sheet_no: event.sheet_no ?? "",
              line_group_id: null,
              left_value: event.left_value ?? null,
              right_value: event.right_value ?? null,
              primary_pair_id: null,
              related_pair_ids: [],
              sheet_ids: [],
              values: [event.left_value, event.right_value].filter((value): value is string => Boolean(value)),
              evidence_refs: [],
              one_to_many_classification: event.one_to_many_classification ?? null,
              handling_class: event.handling_class ?? null,
              evidence: {
                filename: event.filename ?? "",
                sheet_no: event.sheet_no ?? "",
                sheet_title: event.sheet_title ?? "",
                line_start: event.line_start ?? null,
                line_end: event.line_end ?? null,
                handling_class: event.handling_class ?? null,
              },
            },
            ...nextState.liveIssues,
          ].slice(0, 50)
        }

        if (event.event === "audit_finished") {
          if (nextState.currentProjectName) {
            nextState.coverageByProject = upsertProjectCoverage(
              nextState.coverageByProject,
              nextState.currentProjectName,
              event.coverage_ratio ?? null,
            )
          }
        }

        if (event.event === "project_stored") {
          const storedProject: RecentProject = {
              run_id: event.run_id,
              session_id: nextState.sessionId ?? "session-runtime",
              project_id: event.project_id,
              project_name: event.project_name,
              input_root: inputRoot,
              artifact_dir: event.artifact_dir,
              updated_at: new Date().toISOString(),
              status: "completed",
              sheet_count: event.sheet_count,
              pair_count: event.pair_count,
              issue_count: event.issue_count,
              diagnostic_count: event.diagnostic_count,
              coverage_ratio: event.coverage_ratio ?? null,
          }
          nextState.completedProjects = [
            ...nextState.completedProjects.filter((project) => project.run_id !== storedProject.run_id),
            storedProject,
          ]
          nextState.totalIssueCount = nextState.completedProjects.reduce((sum, project) => sum + project.issue_count, 0)
          nextState.coverageByProject = upsertProjectCoverage(
            nextState.coverageByProject,
            event.project_name,
            event.coverage_ratio ?? null,
          )
          nextState.flowDots = moveProjectFlowDots(nextState.flowDots, event.project_name, "result")
        }

        if (event.event === "run_finished") {
          nextState.progressRatio = 1
          nextState.stageCards = nextState.stageCards.map((item) => ({ ...item, done: true }))
          nextState.completedProjects = event.projects
          nextState.totalSheets = event.projects.reduce((sum, project) => sum + project.sheet_count, 0)
          nextState.totalIssueCount = event.projects.reduce((sum, project) => sum + project.issue_count, 0)
          nextState.coverageByProject = event.projects.map((project) => ({
            projectName: project.project_name,
            coverageRatio: project.coverage_ratio ?? null,
          }))
          nextState.flowDots = nextState.flowDots.map((dot) => ({ ...dot, phase: "result" }))
        }
      }
      return nextState
    })
  })

  const handleEvent = useEffectEvent((event: SidecarEvent) => {
    // Batch high-frequency sidecar events so process screen does not thrash React.
    processEventQueueRef.current.push(event)
    if (processFlushTimerRef.current != null) {
      return
    }
    processFlushTimerRef.current = window.setTimeout(() => {
      processFlushTimerRef.current = null
      const batch = processEventQueueRef.current
      processEventQueueRef.current = []
      applyProcessEvents(batch)
    }, 80)
  })

  useEffect(() => {
    return () => {
      if (processFlushTimerRef.current != null) {
        window.clearTimeout(processFlushTimerRef.current)
        processFlushTimerRef.current = null
      }
      if (processEventQueueRef.current.length) {
        applyProcessEvents(processEventQueueRef.current)
        processEventQueueRef.current = []
      }
    }
  }, [])

  useEffect(() => {
    const requestGeneration = projectLoadGenerationRef.current
    return () => {
      const generation = requestGeneration.current
      if (generation > 0) {
        void desktopApi
          .cancelResultLoad(generation, previewClientSessionId, previewClientSessionEpochRef.current)
          .catch(() => undefined)
      }
    }
  }, [previewClientSessionId])

  async function handleAnalyzeClick(inputOverride?: string) {
    if (analysisInFlightRef.current) {
      return
    }
    const normalizedInputRoot = (inputOverride ?? inputRoot).trim()
    if (!normalizedInputRoot) {
      setLoadError("请先选择项目目录。")
      return
    }
    if (isLikelyProjectFilePath(normalizedInputRoot)) {
      setLoadError("请选择项目文件夹，不要选择单个图纸文件。")
      setLaunchImportStatus({
        tone: "warn",
        message: "应选择整套图纸所在的项目目录，而不是某一个 DWG 文件。",
      })
      return
    }
    const screenIntentGeneration = beginRequest(screenIntentGenerationRef.current)
    analysisInFlightRef.current = true
    const previousResultGeneration = projectLoadGenerationRef.current.current
    if (previousResultGeneration > 0) {
      void desktopApi
        .cancelResultLoad(previousResultGeneration, previewClientSessionId, previewClientSessionEpochRef.current)
        .catch(() => undefined)
    }
    invalidateRequests(projectLoadGenerationRef.current)
    issuePageLoadInFlightRef.current = null
    issuePageQueryKeyRef.current = null
    setIsLoadingProjectId(null)
    setIsLoadingMoreIssues(false)
    setIsReloadingIssueQuery(false)
    setLoadError(null)
    setIsAnalyzing(true)
    setScreen("process")
    logAutoFollowRef.current = true
    setProcessState({
      sessionId: null,
      progressRatio: 0.02,
      activeStage: "scan",
      totalSheets: 0,
      currentProjectRoot: null,
      currentProjectName: null,
      currentProjectSheetCount: 0,
      completedPages: 0,
      failedPages: 0,
      totalIssueCount: 0,
      analysisIncomplete: false,
      failureMessage: null,
      warningCount: 0,
      stageCards: defaultStageCards(),
      logs: [],
      liveIssues: [],
      completedProjects: [],
      coverageByProject: [],
      flowDots: [],
      routeCounts: desktopApi.isNative() ? null : { v1: 0, v2: 0 },
    })

    try {
      const payload = await desktopApi.analyzeSession({ inputRoot: normalizedInputRoot }, handleEvent)
      if (processFlushTimerRef.current != null) {
        window.clearTimeout(processFlushTimerRef.current)
        processFlushTimerRef.current = null
      }
      if (processEventQueueRef.current.length) {
        applyProcessEvents(processEventQueueRef.current)
        processEventQueueRef.current = []
      }
      setRecentProjects(await desktopApi.listRecentProjects())
      if (payload.projects[0] && isCurrentRequest(screenIntentGenerationRef.current, screenIntentGeneration)) {
        selectProject(payload.projects[0].project_id, payload.projects[0].run_id)
        await loadProjectResult(payload.projects[0].project_id, payload.projects[0].run_id)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "校验失败，请检查项目目录后重试。"
      if (processFlushTimerRef.current != null) {
        window.clearTimeout(processFlushTimerRef.current)
        processFlushTimerRef.current = null
      }
      if (processEventQueueRef.current.length) {
        applyProcessEvents(processEventQueueRef.current)
        processEventQueueRef.current = []
      }
      setProcessState((current) => ({ ...current, failureMessage: message }))
      setLoadError(message)
      if (isCurrentRequest(screenIntentGenerationRef.current, screenIntentGeneration)) {
        setScreen("process")
      }
    } finally {
      analysisInFlightRef.current = false
      setIsAnalyzing(false)
    }
  }

  async function handlePickDirectoryClick() {
    if (!isTauri()) {
      setLaunchImportStatus({
        tone: "info",
        message: "当前是浏览器演示界面，请使用桌面客户端选择本机项目目录。",
      })
      return
    }

    setIsPickingDirectory(true)
    try {
      const selected = await desktopApi.pickProjectDirectory(inputRoot)
      if (selected) {
        applyImportedInputRoot(selected, "picker")
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "打开系统目录对话框失败。"
      setLoadError(message)
    } finally {
      setIsPickingDirectory(false)
    }
  }

  async function handleDeleteProject(projectId: string, projectName: string) {
    if (!projectId) {
      return
    }
    if (isDeletingProjectId) {
      return
    }
    if (isLoadingProjectId) {
      return
    }
    const confirmed = window.confirm(
      `确认删除项目记录「${projectName || projectId}」？\n将移除应用内保存的问题清单与定位信息，且不可恢复。`,
    )
    if (!confirmed) {
      return
    }
    setIsDeletingProjectId(projectId)
    setLoadError(null)
    try {
      if (isTauri()) {
        await desktopApi.deleteProject(projectId)
      }
      setRecentProjects((current) => current.filter((item) => item.project_id !== projectId))
      if (selectedProjectIdRef.current === projectId) {
        const generation = projectLoadGenerationRef.current.current
        void desktopApi.cancelResultLoad(generation, previewClientSessionId, previewClientSessionEpochRef.current).catch(() => undefined)
        invalidateRequests(projectLoadGenerationRef.current)
        issuePageLoadInFlightRef.current = null
        issuePageQueryKeyRef.current = null
        setIsLoadingMoreIssues(false)
        setIsReloadingIssueQuery(false)
        selectProject(null)
        setResult(null)
        setResultSummary(null)
        setResultIssueTotal(0)
        setDiagnosticItems([])
        setDiagnosticTotal(0)
        setDiagnosticLoadedRunId(null)
        setDiagnosticError(null)
        setSelectedIssueId(null)
        setScreen("launch")
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除项目记录失败。"
      setLoadError(message)
    } finally {
      setIsDeletingProjectId(null)
    }
  }

  const filteredIssues = useMemo(() => result?.issues ?? [], [result?.issues])

  const issueStats = {
    total: resultSummary?.issue_stats.total ?? 0,
    openCount: resultSummary?.issue_stats.open_count ?? 0,
    seriousOpenCount: resultSummary?.issue_stats.serious_open_count ?? 0,
    resolvedCount: resultSummary?.issue_stats.resolved_count ?? 0,
    errorCount: resultSummary?.issue_stats.error_count ?? 0,
    warningCount: resultSummary?.issue_stats.warning_count ?? 0,
    reviewCount: resultSummary?.issue_stats.review_count ?? 0,
    groupCount: resultSummary?.issue_stats.group_count ?? 0,
  }

  const issueFilterOptions = resultSummary?.filter_options ?? {
    severities: [],
    rules: [],
    statuses: [],
    triages: [],
  }

  const recognitionSummary = (resultSummary?.run.metadata?.recognition_summary ?? null) as RecognitionSummary | null

  const selectedIssue = useMemo(() => {
    if (!filteredIssues.length) {
      return null
    }
    if (!selectedIssueId) {
      return filteredIssues[0] ?? null
    }
    return filteredIssues.find((issue) => issue.issue_id === selectedIssueId) ?? filteredIssues[0] ?? null
  }, [filteredIssues, selectedIssueId])

  // Virtualize the per-issue list. Everything below this point keeps the same
  // `<table>` markup and styling; only the rendered rows are windowed. The
  // table remains scrollable inside `.result-issue-list` so tens of thousands
  // of rows no longer force the WebView to commit the full DOM at once.
  const issueListParentRef = useRef<HTMLDivElement | null>(null)
  const issueRowVirtualizer = useVirtualizer({
    count: filteredIssues.length,
    getScrollElement: () => issueListParentRef.current,
    estimateSize: () => 48,
    getItemKey: (index) => filteredIssues[index]?.issue_id ?? index,
    overscan: 12,
  })
  const totalIssueCount = resultSummary?.issue_count ?? Math.max(resultIssueTotal, result?.issues.length ?? 0)
  const filteredIssueTotal = Math.max(resultIssueTotal, result?.issues.length ?? 0)
  const issueQueryNeedsReload = appliedIssueQueryKeyRef.current !== activeIssueQueryKey
  const accessibleIssueRowCount = filteredIssueTotal

  useEffect(() => {
    issueRowVirtualizer.measure()
    issueRowVirtualizer.scrollToOffset(0)
  }, [deferredIssueSearch, handlingFilter, issueRowVirtualizer, ruleFilter, severityFilter, statusFilter, triageFilter, result?.run.run_id])

  const summaryProject =
    result?.run ??
    recentProjects.find(
      (project) =>
        project.project_id === selectedProjectId && (!selectedRunId || project.run_id === selectedRunId),
    ) ??
    recentProjects[0] ??
    null
  const inputHealth = describeInputRoot(inputRoot)
  function toggleResultToolbar(): void {
    const next = !toolbarCollapsed
    setToolbarCollapsed(next)
    saveResultToolbarCollapsed(next)
  }

  const structuredLocation = useMemo(() => readStructuredLocation(selectedIssue), [selectedIssue])
  const scoreBreakdown = useMemo(
    () => (selectedIssue ? readScoreBreakdown(selectedIssue.evidence) : {}),
    [selectedIssue],
  )

  useEffect(() => {
    setIssueStatusDraft(selectedIssue?.status ?? "open")
  }, [selectedIssue?.issue_id, selectedIssue?.status])

  useEffect(() => {
    if (!selectedIssue) {
      if (selectedIssueId !== null) {
        setSelectedIssueId(null)
      }
      return
    }
    if (selectedIssue.issue_id !== selectedIssueId) {
      setSelectedIssueId(selectedIssue.issue_id)
    }
  }, [selectedIssue, selectedIssueId])

  async function handleIssueStatusSave() {
    const projectId = result?.run.project_id ?? selectedProjectId
    const runId = result?.run.run_id ?? null
    if (!projectId || !runId || !selectedIssue) {
      return
    }
    const issueId = selectedIssue.issue_id
    const nextStatus = issueStatusDraft
    setIsSavingIssueStatus(true)
    try {
      await desktopApi.setIssueStatus(projectId, issueId, nextStatus, runId)
      if (selectedProjectIdRef.current !== projectId || selectedRunIdRef.current !== runId) {
        return
      }
      setResult((current) => {
        if (
          !current ||
          current.run.project_id !== projectId ||
          current.run.run_id !== runId ||
          selectedProjectIdRef.current !== projectId
        ) {
          return current
        }
        return {
          ...current,
          issues: current.issues.map((issue) => (issue.issue_id === issueId ? { ...issue, status: nextStatus } : issue)),
        }
      })
      setResultSummary((current) =>
        current && current.run.run_id === runId
          ? updateSummaryIssueStatus(current, selectedIssue, nextStatus)
          : current,
      )
      appliedIssueQueryKeyRef.current = null
      const currentQuery = activeIssueQueryRef.current
      void reloadIssuesForQuery(currentQuery, activeIssueQueryKeyRef.current)
      if (selectedProjectIdRef.current === projectId) {
        setLoadError(null)
      }
    } catch (error) {
      if (selectedProjectIdRef.current === projectId) {
        const message = error instanceof Error ? error.message : "保存处理状态失败，请稍后重试。"
        setLoadError(message)
      }
    } finally {
      setIsSavingIssueStatus(false)
    }
  }

  const screenTitle = screen === "launch" ? "项目" : screen === "process" ? "校验中" : screen === "result" ? "问题" : "设置"
  const isNativeRuntime = desktopApi.isNative()
  const sessionLabel = isAnalyzing
    ? `正在校验 ${Math.round(processState.progressRatio * 100)}%`
    : summaryProject?.project_name ?? "尚未打开项目"
  const processStatusText = describeProcessStatus(processState, isAnalyzing)
  const completedFlowSheets = processState.completedProjects.reduce((sum, project) => sum + project.sheet_count, 0)
  const flowInputName = !isAnalyzing && processState.completedProjects.length && inputRoot.trim()
    ? getPathBaseName(inputRoot)
    : processState.currentProjectName ?? getPathBaseName(inputRoot)
  const flowInputPageCount = !isAnalyzing && processState.completedProjects.length
    ? completedFlowSheets
    : processState.currentProjectSheetCount || processState.totalSheets
  const flowCoverage: AuditFlowCoverage[] = processState.coverageByProject.map((item) => ({
    projectName: item.projectName,
    value: formatCoverageRatio(item.coverageRatio),
  }))

  return (
    <div className="shell">
      <header className="topbar">
        <div className="product-mark">
          <img className="product-logo" src={logoUrl} alt="许继集团" />
          <div className="product-mark-text">
            <strong>图纸端子校验</strong>
            <span>本地离线 · 跨页核对</span>
          </div>
        </div>
        <nav className="nav-strip" aria-label="主视图">
          <button type="button" className={screen === "launch" ? "nav-chip active" : "nav-chip"} onClick={() => navigateToScreen("launch")}>
            项目
          </button>
          <button type="button" className={screen === "process" ? "nav-chip active" : "nav-chip"} onClick={() => navigateToScreen("process")}>
            校验中
          </button>
          <button type="button" className={screen === "result" ? "nav-chip active" : "nav-chip"} onClick={() => navigateToScreen("result")}>
            问题
          </button>
          <button type="button" className={screen === "settings" ? "nav-chip active" : "nav-chip"} onClick={() => navigateToScreen("settings")}>
            设置
          </button>
        </nav>
        <div className="session-meta">
          <span className={`engine-pill ${isNativeRuntime ? "native" : "mock"}`}>
            {isNativeRuntime ? "本机运行" : "演示"}
          </span>
          <strong title={sessionLabel}>
            {screenTitle} · {sessionLabel}
          </strong>
        </div>
      </header>

      {loadError ? <div className="global-error">{loadError}</div> : null}

      <main className="workspace">
        {screen === "launch" && (
          <section className="launch-layout">
            <article className="panel launch-import">
              <div className="panel-pad">
                <div className="section-heading">
                  <h3>导入图纸项目</h3>
                  <span>{isNativeRuntime ? "校验结果保存在本机" : "当前为界面演示"}</span>
                </div>
              </div>
              <div className="launch-import-body panel-pad" style={{ paddingTop: 0 }}>
                <div className={`dropzone ${isDropTargetActive ? "dropzone-active" : ""}`}>
                  <h3>把整套图纸文件夹拖到这里</h3>
                  <p>也可点“选择目录”。请选择项目总目录（里面有多张图纸），不要只拖单个图纸文件。</p>
                </div>
                <div className={`input-health ${inputHealth.tone}`}>
                  <strong>{inputHealth.title}</strong>
                  <span>{inputHealth.detail}</span>
                </div>
                {launchImportStatus ? (
                  <div className={`drop-status ${launchImportStatus.tone}`}>
                    <strong>{launchImportStatus.tone === "ready" ? "就绪" : launchImportStatus.tone === "warn" ? "需注意" : "提示"}</strong>
                    <span>{launchImportStatus.message}</span>
                  </div>
                ) : null}
                <label className="field">
                  <span>项目文件夹</span>
                  <input
                    value={inputRoot}
                    onChange={(event) => {
                      setInputRoot(event.target.value)
                      setLaunchImportStatus(null)
                    }}
                    placeholder="例如：D:\工程图纸\某某保护柜"
                  />
                </label>
                <div className="button-row launch-actions">
                  <button type="button" className="primary-button" disabled={!inputRoot.trim() || isAnalyzing} onClick={() => void handleAnalyzeClick()}>
                    {isAnalyzing ? "校验中…" : "开始校验"}
                  </button>
                  <button type="button" className="ghost-button" disabled={isPickingDirectory || isAnalyzing} onClick={() => void handlePickDirectoryClick()}>
                    {isPickingDirectory ? "打开中…" : "选择目录"}
                  </button>
                </div>
                {!isNativeRuntime ? (
                  <div className="drop-status warn">
                    <strong>当前为演示界面</strong>
                    <span>正式校验请使用桌面客户端，对本机图纸项目进行检查。</span>
                  </div>
                ) : null}
                <div className="launch-import-footer muted">
                  校验完成后可在“问题”页逐条复核。软件只保留问题清单和定位信息，临时转换文件会在退出时清理。
                </div>
              </div>
            </article>

            <article className="panel launch-recent">
              <div className="panel-pad">
                <div className="section-heading">
                  <h3>最近校验</h3>
                  <button type="button" className="ghost-button" onClick={() => void refreshRecentProjects()}>
                    刷新
                  </button>
                </div>
              </div>
              <div className="table-wrap launch-recent-table">
                <table className="data-table compact">
                  <thead>
                    <tr>
                      <th>项目</th>
                      <th>校验时间</th>
                      <th>图纸</th>
                      <th>问题</th>
                      <th>状态</th>
                      <th className="actions-col">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentProjects.length ? (
                      recentProjects.map((project) => (
                        <tr
                          key={project.run_id}
                          className={project.run_id === selectedRunId ? "selected-row" : ""}
                          onClick={() => {
                            if (isAnalyzing || isDeletingProjectId || isLoadingProjectId === project.project_id) {
                              return
                            }
                            if (project.snapshot_available === false) {
                              setInputRoot(project.input_root)
                              return
                            }
                            selectProject(project.project_id, project.run_id)
                            void loadProjectResult(project.project_id, project.run_id)
                          }}
                        >
                          <td>
                            <div className="issue-title-cell">
                              <strong>{project.project_name}</strong>
                              <span className="muted" title={project.input_root}>
                                {shortenPath(project.input_root)}
                              </span>
                            </div>
                          </td>
                          <td>{formatAuditTime(project.updated_at)}</td>
                          <td>{project.sheet_count} 页</td>
                          <td>{project.issue_count} 条</td>
                          <td>
                            <span className={`chip status-${normalizeToken(project.status)}`}>{project.snapshot_available === false ? "需重新分析" : labelProjectStatus(project.status)}</span>
                          </td>
                          <td className="actions-col">
                            <div className="row-actions">
                              <button
                                type="button"
                                className="ghost-button"
                                disabled={isAnalyzing || Boolean(isDeletingProjectId) || isLoadingProjectId === project.project_id}
                                onClick={(event) => {
                                  event.stopPropagation()
                                  if (project.snapshot_available === false) {
                                    setInputRoot(project.input_root)
                                    void handleAnalyzeClick(project.input_root)
                                    return
                                  }
                                  selectProject(project.project_id, project.run_id)
                                  void loadProjectResult(project.project_id, project.run_id)
                                }}
                              >
                                {project.snapshot_available === false ? "重新分析" : isLoadingProjectId === project.project_id ? "加载中…" : "查看"}
                              </button>
                              <button
                                type="button"
                                className="danger-button"
                                disabled={Boolean(isDeletingProjectId) || Boolean(isLoadingProjectId) || isAnalyzing}
                                onClick={(event) => {
                                  event.stopPropagation()
                                  void handleDeleteProject(project.project_id, project.project_name)
                                }}
                              >
                                {isDeletingProjectId === project.project_id ? "删除中…" : "删除"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6}>
                          <div className="empty-state">还没有校验记录。完成一次校验后，可在这里快速打开结果。</div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </section>
        )}

        {screen === "process" && (
          <section className="process-layout">
            <article className="panel process-stages panel-pad">
                <div className="section-heading">
                  <h3>正在做什么</h3>
                  <span>{processStatusText}</span>
                </div>
              <div className="process-status-banner">
                <strong>{processState.analysisIncomplete ? "分析未完成" : processState.failureMessage ? "校验失败" : isAnalyzing ? "校验进行中" : processState.progressRatio >= 1 ? "校验已完成" : "等待开始"}</strong>
                <span>{processStatusText}</span>
                {!isAnalyzing && processState.progressRatio >= 1 ? (
                  <button type="button" className="primary-button" onClick={() => setScreen("result")}>
                    查看问题清单
                  </button>
                ) : null}
                {!isNativeRuntime && !isAnalyzing ? (
                  <button type="button" className="ghost-button" onClick={() => void handleAnalyzeClick(DEMO_INPUT_ROOT)}>
                    演示运行
                  </button>
                ) : null}
                {!isAnalyzing && (processState.failureMessage || processState.analysisIncomplete) && (
                  <button type="button" className="primary-button" onClick={() => void handleAnalyzeClick()}>
                    重新分析
                  </button>
                )}
              </div>
              <div className="stage-grid">
                {processState.stageCards.map((card) => (
                  <div key={card.stage} className={`stage-card ${processState.activeStage === card.stage ? "active" : ""} ${card.done ? "done" : ""}`}>
                    <strong>{card.label}</strong>
                    <span>{card.detail}</span>
                  </div>
                ))}
              </div>
            </article>

            <article className="panel process-progress panel-pad">
                <div className="section-heading">
                  <h3>总体进度</h3>
                  <span>{Math.round(processState.progressRatio * 100)}%</span>
                </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${Math.round(processState.progressRatio * 100)}%` }} />
              </div>
              <div className="progress-meta">
                <div className="metric-inline">
                  <strong>{isAnalyzing ? processState.currentProjectSheetCount || processState.totalSheets : processState.totalSheets}</strong>
                  <span>{isAnalyzing ? "当前项目图纸" : "图纸总数"}</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.completedPages}</strong>
                  <span>已处理</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.failedPages}</strong>
                  <span>处理失败</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.warningCount}</strong>
                  <span>提醒</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.totalIssueCount}</strong>
                  <span>已发现问题</span>
                </div>
              </div>
            </article>

            <article className="panel process-live-issues">
              <div className="panel-pad" style={{ paddingBottom: 0 }}>
                <div className="section-heading">
                  <h3>边校验边发现的问题</h3>
                  <span>{processState.liveIssues.length} 条</span>
                </div>
              </div>
              <div className="table-wrap">
                <table className="data-table compact">
                  <thead>
                    <tr>
                      <th>来源图纸</th>
                      <th>问题</th>
                      <th>端子</th>
                      <th>位置</th>
                      <th>程序把握度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {processState.liveIssues.length ? (
                      processState.liveIssues.map((issue) => {
                        const source = formatSourcePage(issue)
                        const location = describeIssueLocationCell(issue)
                        return (
                          <tr key={issue.issue_id}>
                            <td title={source.detail || source.label}>
                              <div className="issue-title-cell">
                                <strong>{source.label}</strong>
                                {source.secondary ? <span className="muted">{source.secondary}</span> : null}
                              </div>
                            </td>
                            <td>
                              <div className="issue-title-cell">
                                <strong>{issue.title}</strong>
                              </div>
                            </td>
                            <td>{formatPair(issue)}</td>
                            <td title={location.detail}>{location.label}</td>
                            <td title="程序把握度，不是问题严重程度">{formatConfidence(issue.confidence)}</td>
                          </tr>
                        )
                      })
                    ) : (
                      <tr>
                        <td colSpan={5}>
                          <div className="empty-state">
                            {isAnalyzing ? "正在识别图纸，发现问题后会显示在这里。" : "开始校验后，发现的问题会实时出现在这里。"}
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="panel process-logs">
              <div className="process-log-rail" aria-label="运行提示">
                <h3>运行提示</h3>
                <span>{processState.logs.length} 条</span>
              </div>
              <pre
                ref={logStreamRef}
                className="log-stream"
                onScroll={(event) => {
                  const element = event.currentTarget
                  logAutoFollowRef.current = element.scrollHeight - element.clientHeight - element.scrollTop <= 18
                }}
              >
                {processState.logs.length ? processState.logs.join("\n") : "点击“开始校验”后，这里会显示当前步骤。"}
              </pre>
            </article>

            <AuditFlowDiagram
              projectName={flowInputName || "等待读取项目"}
              pageCount={flowInputPageCount}
              processedPages={processState.completedPages}
              coordinatedPages={processState.activeStage === "pair" || processState.activeStage === "audit" || processState.progressRatio >= 1 ? processState.completedPages : 0}
              routeCounts={processState.routeCounts}
              totalIssues={processState.totalIssueCount}
              coverageByProject={flowCoverage}
              activeStage={processState.activeStage}
              isAnalyzing={isAnalyzing}
              isComplete={!isAnalyzing && processState.progressRatio >= 1}
              flowDots={processState.flowDots}
            />
          </section>
        )}

        {screen === "result" && (
          <section className="result-layout">
            {result?.run.metadata?.clean_conclusion_allowed === false && (
              <div className="panel" role="status">
                <strong>分析未完成</strong>
                <p>部分图纸未成功读取，当前结果不能作为无问题结论。请检查失败页面后重新分析。</p>
              </div>
            )}
            <article className={`panel result-toolbar${toolbarCollapsed ? " is-collapsed" : ""}`}>
              <div className="result-toolbar-bar">
                <div className="result-toolbar-metrics">
                  <span className="tb-stat">
                    <strong>{summaryProject?.sheet_count ?? 0}</strong>
                    <span>图纸页</span>
                  </span>
                  <button
                    type="button"
                    className={`tb-stat tb-action${handlingFilter === "all" ? " is-active" : ""}`}
                    aria-pressed={handlingFilter === "all"}
                    onClick={() => setHandlingFilter("all")}
                  >
                    <strong>{totalIssueCount}</strong>
                    <span>问题</span>
                  </button>
                  <button
                    type="button"
                    className={`tb-stat tb-action metric-error${handlingFilter === "error" ? " is-active" : ""}`}
                    aria-pressed={handlingFilter === "error"}
                    onClick={() => setHandlingFilter("error")}
                  >
                    <strong>{issueStats.errorCount}</strong>
                    <span>确定性错误</span>
                  </button>
                  <button
                    type="button"
                    className={`tb-stat tb-action metric-warning${handlingFilter === "warning" ? " is-active" : ""}`}
                    aria-pressed={handlingFilter === "warning"}
                    onClick={() => setHandlingFilter("warning")}
                  >
                    <strong>{issueStats.warningCount}</strong>
                    <span>可能有错误</span>
                  </button>
                  <button
                    type="button"
                    className={`tb-stat tb-action metric-review${handlingFilter === "review" ? " is-active" : ""}`}
                    aria-pressed={handlingFilter === "review"}
                    onClick={() => setHandlingFilter("review")}
                  >
                    <strong>{issueStats.reviewCount}</strong>
                    <span>须人工校验</span>
                  </button>
                  <button
                    type="button"
                    className={`tb-stat tb-action${statusFilter === "open" ? " is-active" : ""}`}
                    aria-pressed={statusFilter === "open"}
                    onClick={() => setStatusFilter(statusFilter === "open" ? "all" : "open")}
                  >
                    <strong>{issueStats.openCount}</strong>
                    <span>待处理</span>
                  </button>
                  <span className="tb-stat">
                    <strong>{issueStats.groupCount}</strong>
                    <span>同类问题组</span>
                  </span>
                </div>
                <div className="result-toolbar-meta">
                  <span className="tb-project" title={summaryProject?.project_name ?? undefined}>
                    {summaryProject?.project_name ?? "未加载项目"}
                  </span>
                  <span className="tb-coverage" aria-label="识别覆盖率与未闭合诊断">
                    覆盖率 <strong>{formatCoverageRatio(recognitionSummary?.coverage_ratio)}</strong>
                    <span className="tb-sep">·</span>
                    {recognitionSummary?.unclosed_count ?? 0} 处未闭合
                    <span className="tb-sep">·</span>
                    {recognitionSummary?.diagnostic_count ?? 0} 条内部诊断
                  </span>
                <details
                  className="tb-details"
                  onToggle={(event) => {
                    if (event.currentTarget.open && diagnosticLoadedRunId !== result?.run.run_id && !isLoadingDiagnostics) {
                      void loadDiagnostics(0)
                    }
                  }}
                >
                  <summary>诊断明细</summary>
                  {recognitionSummary ? (
                    <div className="diagnostic-summary-content">
                      <div className="diagnostic-breakdown">
                        <span>按来源</span>
                        {Object.entries(recognitionSummary.by_presentation ?? {}).map(([key, count]) => (
                          <span key={key}>{labelDiagnosticPresentation(key)} {count}</span>
                        ))}
                        <span>按原因</span>
                        {Object.entries(recognitionSummary.by_reason_code ?? {}).map(([key, count]) => (
                          <span key={key}>{labelDiagnosticReason(key)} {count}</span>
                        ))}
                        {Object.keys(recognitionSummary.by_observation_reason_code ?? {}).length ? (
                          <>
                            <span className="diagnostic-breakdown-label">按识别状态</span>
                            {Object.entries(recognitionSummary.by_observation_reason_code ?? {}).map(([key, count]) => (
                              <span key={key}>{labelDiagnosticReason(key)} {count}</span>
                            ))}
                          </>
                        ) : null}
                      </div>
                      {recognitionSummary.by_page?.length ? (
                        <div className="diagnostic-page-summary">
                          <strong>逐页覆盖</strong>
                          {recognitionSummary.by_page.map((page) => (
                            <span key={page.sheet_id ?? page.sheet_no ?? page.filename ?? "page"}>
                              {resolveSheetName({ filename: page.filename, sheetNo: page.sheet_no }).name} · 覆盖率 {formatCoverageRatio(page.coverage_ratio)} · {page.unclosed_count} 处未闭合
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {diagnosticError ? <p className="diagnostic-error">{diagnosticError}</p> : null}
                      {diagnosticItems.length ? (
                        <div className="table-wrap diagnostic-table-wrap">
                          <table className="data-table compact">
                            <thead>
                              <tr>
                                <th>来源图纸</th>
                                <th>诊断</th>
                                <th>端点</th>
                                <th>原因</th>
                                <th>类别</th>
                              </tr>
                            </thead>
                            <tbody>
                              {diagnosticItems.map((issue) => {
                                const reasonCodes = Array.isArray(issue.evidence.resolution_reason_codes)
                                  ? issue.evidence.resolution_reason_codes
                                  : issue.evidence.reason_codes
                                const reasons = Array.isArray(reasonCodes)
                                  ? reasonCodes.map(String).map(labelDiagnosticReason).join("、")
                                  : "未分类"
                                const presentation = typeof issue.evidence.presentation === "string"
                                  ? labelDiagnosticPresentation(issue.evidence.presentation)
                                  : "诊断项"
                                return (
                                  <tr key={issue.issue_id}>
                                    <td>{issue.sheet_no || issue.filename ? formatSourcePage(issue).label : issue.sheet_id || "项目级"}</td>
                                    <td>{issue.title || issue.summary}</td>
                                    <td>{[issue.left_value, issue.right_value].filter(Boolean).join(" → ") || "未识别"}</td>
                                    <td>{reasons}</td>
                                    <td>{presentation}</td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      ) : isLoadingDiagnostics ? (
                        <p className="muted">正在加载诊断明细…</p>
                      ) : (
                        <p className="muted">当前项目没有未闭合诊断。</p>
                      )}
                      {diagnosticItems.length < diagnosticTotal ? (
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={isLoadingDiagnostics}
                          onClick={() => void loadDiagnostics(diagnosticItems.length)}
                        >
                          {isLoadingDiagnostics ? "加载中…" : `加载更多（${diagnosticItems.length}/${diagnosticTotal}）`}
                        </button>
                      ) : diagnosticItems.length ? (
                        <span className="muted">已显示 {diagnosticItems.length}/{diagnosticTotal} 条诊断</span>
                      ) : null}
                    </div>
                  ) : (
                    <p className="muted">当前项目未提供识别覆盖率诊断摘要。</p>
                  )}
                </details>
                {result?.series_chains ? (
                  <span className="tb-muted tb-chain">
                    串联链 {result.series_chains.chain_count} 条
                    <button
                      type="button"
                      className="ghost-button tb-small-button"
                      onClick={() => {
                        const projectId = result.run.project_id.replace(/[^A-Za-z0-9._-]+/g, "_") || "project"
                        downloadJsonFile(`series_chains_${projectId}.json`, result.series_chains)
                      }}
                    >
                      下载 JSON
                    </button>
                  </span>
                ) : null}
                </div>
                <button
                  type="button"
                  className="ghost-button tb-small-button tb-toggle"
                  aria-expanded={!toolbarCollapsed}
                  onClick={toggleResultToolbar}
                >
                  {toolbarCollapsed ? "展开筛选" : "收起"}
                </button>
              </div>

              {toolbarCollapsed ? null : (
                <div className="result-toolbar-row">
                <label className="tb-search">
                  <span>搜索</span>
                  <input value={issueSearch} onChange={(event) => setIssueSearch(event.target.value)} placeholder="图号 / 端子号 / 说明" />
                </label>
                  <div className="tb-filters">
                    <label className="tb-field">
                      <span>严重程度</span>
                      <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
                        <option value="all">全部</option>
                        {issueFilterOptions.severities.map((value) => (
                          <option key={value} value={value}>
                            {labelSeverity(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="tb-field">
                      <span>问题类别</span>
                      <select value={ruleFilter} onChange={(event) => setRuleFilter(event.target.value)}>
                        <option value="all">全部</option>
                        {issueFilterOptions.rules.map((value) => (
                          <option key={value} value={value}>
                            {labelRule(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="tb-field">
                      <span>处理状态</span>
                      <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                        <option value="all">全部</option>
                        {issueFilterOptions.statuses.map((value) => (
                          <option key={value} value={value}>
                            {labelIssueStatus(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="tb-field">
                      <span>连接关系</span>
                      <select value={triageFilter} onChange={(event) => setTriageFilter(event.target.value)}>
                        <option value="all">全部</option>
                        {issueFilterOptions.triages.map((value) => (
                          <option key={value} value={value}>
                            {labelTriage(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="tb-guide">
                    <button
                      type="button"
                      className="ghost-button tb-small-button tb-info"
                      title={RESULT_GUIDE_TEXT}
                      aria-expanded={toolbarGuideOpen}
                      onClick={() => setToolbarGuideOpen((open) => !open)}
                    >
                      <svg viewBox="0 0 16 16" aria-hidden="true">
                        <circle cx="8" cy="8" r="6.5" />
                        <path d="M8 7.2v3.8M8 4.9v.2" />
                      </svg>
                      处理顺序
                    </button>
                    {toolbarGuideOpen ? (
                      <p className="tb-guide-pop" role="note">
                        {RESULT_GUIDE_TEXT}
                      </p>
                    ) : null}
                  </div>
                </div>
              )}
            </article>

            <article className="panel result-issue-list">
              <div className="panel-pad" style={{ paddingBottom: 0 }}>
                <div className="section-heading">
                  <h3>问题清单</h3>
                  <span>
                    显示 {filteredIssues.length} / 筛选结果 {filteredIssueTotal} / 全部 {totalIssueCount}
                    {isLoadingMoreIssues || isReloadingIssueQuery ? " · 加载中…" : ""}
                  </span>
                </div>
              </div>
              <div
                className="table-wrap result-issue-list-scroll"
                ref={issueListParentRef}
                onScroll={(event) => {
                  const target = event.currentTarget
                   if (!isReloadingIssueQuery && target.scrollHeight - target.scrollTop - target.clientHeight < 720) {
                    void loadMoreIssues()
                  }
                }}
              >
                <table className="data-table compact" aria-rowcount={accessibleIssueRowCount || undefined}>
                  <thead>
                    <tr>
                      <th>处理</th>
                      <th>问题说明</th>
                      <th>端子连接</th>
                      <th>来源图纸</th>
                      <th>位置</th>
                      <th>同类组</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!filteredIssues.length ? (
                      <tr>
                        <td colSpan={7}>
                          <div className="empty-state">
                            {result
                              ? handlingFilter !== "all"
                                ? `当前「${labelHandlingClass(handlingFilter)}」分桶下没有问题。`
                                : "当前筛选条件下没有问题。"
                              : "请先在“项目”页导入图纸项目，或打开最近校验记录。"}
                          </div>
                        </td>
                      </tr>
                    ) : (
                      <>
                        {(() => {
                          const items = issueRowVirtualizer.getVirtualItems()
                          const totalSize = issueRowVirtualizer.getTotalSize()
                          const firstOffset = items.length ? items[0].start : 0
                          const lastEnd = items.length ? items[items.length - 1].end : 0
                          const tailPad = Math.max(0, totalSize - lastEnd)
                          return (
                            <>
                              {firstOffset > 0 ? (
                                <tr aria-hidden style={{ height: `${firstOffset}px` }}>
                                  <td colSpan={7} style={{ padding: 0, border: 0 }} />
                                </tr>
                              ) : null}
                              {items.map((virtualRow) => {
                                const issue = filteredIssues[virtualRow.index]
                                if (!issue) {
                                  return null
                                }
                                const handling = resolveHandlingClass(issue)
                                const source = formatSourcePage(issue)
                                const location = describeIssueLocationCell(issue)
                                return (
                                  <tr
                                    key={issue.issue_id}
                                    ref={issueRowVirtualizer.measureElement}
                                    data-index={virtualRow.index}
                                    aria-rowindex={virtualRow.index + 2}
                                    aria-selected={issue.issue_id === selectedIssue?.issue_id}
                                    tabIndex={0}
                                    className={issue.issue_id === selectedIssue?.issue_id ? "selected-row" : ""}
                                    onClick={() => {
                                      setSelectedIssueId(issue.issue_id)
                                    }}
                                    onKeyDown={(event) => {
                                      if (event.key === "Enter" || event.key === " ") {
                                        event.preventDefault()
                                        setSelectedIssueId(issue.issue_id)
                                      }
                                    }}
                                  >
                                    <td>
                                      <span className={`chip handling-${normalizeToken(handling)}`}>{labelHandlingClass(handling)}</span>
                                    </td>
                                    <td>
                                      <div className="issue-title-cell">
                                        <strong>{issue.title}</strong>
                                      </div>
                                    </td>
                                    <td>{formatPair(issue)}</td>
                                    <td title={source.detail || source.label}>
                                      <div className="issue-title-cell">
                                        <strong>{source.label}</strong>
                                        {source.secondary ? <span className="muted">{source.secondary}</span> : null}
                                      </div>
                                    </td>
                                    <td title={location.detail}>{location.label}</td>
                                    <td title={issue.review_group_label || undefined}>
                                      {(issue.review_group_size ?? 1) > 1
                                        ? `${issue.review_group_size} 处同类`
                                        : "单条"}
                                    </td>
                                    <td>
                                      <span className={`chip status-${normalizeToken(issue.status)}`}>{labelIssueStatus(issue.status)}</span>
                                    </td>
                                  </tr>
                                )
                              })}
                              {tailPad > 0 ? (
                                <tr aria-hidden style={{ height: `${tailPad}px` }}>
                                  <td colSpan={7} style={{ padding: 0, border: 0 }} />
                                </tr>
                              ) : null}
                            </>
                          )
                        })()}
                      </>
                    )}
                  </tbody>
                </table>
              </div>
              {result && (issueQueryNeedsReload || result.issues.length < filteredIssueTotal) ? (
                <div className="issue-load-more">
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={isLoadingMoreIssues || isReloadingIssueQuery}
                    onClick={() => {
                      if (issueQueryNeedsReload) {
                        void reloadIssuesForQuery(activeIssueQuery, activeIssueQueryKey)
                      } else {
                        void loadMoreIssues()
                      }
                    }}
                  >
                    {isLoadingMoreIssues || isReloadingIssueQuery
                      ? "加载中…"
                      : issueQueryNeedsReload
                        ? "重新加载筛选结果"
                        : `加载更多（剩余 ${filteredIssueTotal - result.issues.length}）`}
                  </button>
                </div>
              ) : null}
            </article>

            <article className="result-inspector">
              {selectedIssue ? (
                <IssueInspector
                  key={selectedIssue.issue_id}
                  issue={selectedIssue}
                  handlingClass={resolveHandlingClass(selectedIssue)}
                  projectId={result?.run.project_id ?? selectedProjectId}
                  runId={result?.run.run_id ?? null}
                  clientSessionId={previewClientSessionId}
                  clientSessionEpoch={previewClientSessionEpoch}
                  statusDraft={issueStatusDraft}
                  statusOptions={ISSUE_STATUS_OPTIONS}
                  statusLabel={labelIssueStatus}
                  onStatusDraftChange={setIssueStatusDraft}
                  onSaveStatus={() => void handleIssueStatusSave()}
                  isSavingStatus={isSavingIssueStatus}
                  technicalRows={buildTechnicalRows(selectedIssue, structuredLocation)}
                  scoreRows={buildScoreRows(scoreBreakdown)}
                  rawSections={buildRawSections(selectedIssue)}
                />
              ) : (
                <div className="panel inspector-header">
                  <p className="empty-state">请从左侧选择问题，查看定位预览与处理建议。</p>
                </div>
              )}
            </article>
          </section>
        )}

        {screen === "settings" && (
          <section className="settings-screen">
            <div className="panel panel-pad">
              <div className="section-heading">
                <h3>界面字号</h3>
                <span>当前 {uiScale}%</span>
              </div>
              <p className="muted">调整全部界面文字的大小，包括表格、卡片与数据流图。设置仅保存在本机，不影响校验结果。</p>
              <div className="ui-scale-control" role="group" aria-label="界面字号">
                <button
                  type="button"
                  className="ghost-button ui-scale-button"
                  aria-label="减小界面字号"
                  disabled={uiScale <= UI_SCALE_MIN}
                  onClick={() => updateUiScale(uiScale - UI_SCALE_STEP)}
                >
                  A−
                </button>
                <output className="ui-scale-value" aria-live="polite">{uiScale}%</output>
                <button
                  type="button"
                  className="ghost-button ui-scale-button"
                  aria-label="增大界面字号"
                  disabled={uiScale >= UI_SCALE_MAX}
                  onClick={() => updateUiScale(uiScale + UI_SCALE_STEP)}
                >
                  A+
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={uiScale === UI_SCALE_DEFAULT}
                  onClick={() => updateUiScale(UI_SCALE_DEFAULT)}
                >
                  恢复默认
                </button>
              </div>
              <div className="ui-scale-sample">
                示例：图纸端子校验 · 跨页核对 · 110kV 变压器保护柜
              </div>
            </div>

            <div className="panel panel-pad">
              <div className="section-heading">
                <h3>性能与运行设置</h3>
                <span>
                  {settingsSnapshot && JSON.stringify(settings) === JSON.stringify(settingsSnapshot)
                    ? "已保存"
                    : "未保存更改"}
                </span>
              </div>
              <p className="muted">
                所有设置默认值与本机表现一致；逐项修改并保存后才会作为后端运行参数写入配置文件。
              </p>

              <div className="settings-grid">
                <div className="field">
                  <label htmlFor="settings-convert-workers">ODA 并发上限</label>
                  <select
                    id="settings-convert-workers"
                    value={String(settings.convertWorkers)}
                    onChange={(event) => {
                      const parsed = Number.parseInt(event.target.value, 10)
                      updateSettingsField({ convertWorkers: Number.isFinite(parsed) ? parsed : 0 })
                    }}
                  >
                    <option value="0">自动（默认：内存感知 1 或 2）</option>
                    <option value="1">1 路</option>
                    <option value="2">2 路</option>
                    <option value="3">3 路</option>
                    <option value="4">4 路</option>
                    <option value="6">6 路</option>
                    <option value="8">8 路</option>
                  </select>
                  <span className="field-help">单次转换的 ODA 子进程并发上限。低配机器或卡顿明显时优先调低。</span>
                </div>

                <div className="field">
                  <label htmlFor="settings-oda-timeout">ODA 转换超时（秒）</label>
                  <input
                    id="settings-oda-timeout"
                    type="number"
                    min={1}
                    max={86400}
                    value={settings.odaTimeoutSeconds}
                    onChange={(event) => {
                      const parsed = Number.parseInt(event.target.value, 10)
                      if (!Number.isFinite(parsed)) {
                        return
                      }
                      updateSettingsField({ odaTimeoutSeconds: parsed })
                    }}
                  />
                  <span className="field-help">单个 DWG 文件转换的等待时间上限，超时后会终止整个 ODA 进程树。</span>
                </div>

              </div>

              {settingsError ? <div className="global-error">{settingsError}</div> : null}

              <div className="settings-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    void resetSettings().catch(() => {
                      /* error is stored in settingsError */
                    })
                  }}
                  disabled={settingsSaving}
                >
                  恢复默认
                </button>
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => {
                    void saveSettings(settings).catch(() => {
                      /* error 已写入 settingsError state */
                    })
                  }}
                  disabled={settingsSaving || (settingsSnapshot !== null && JSON.stringify(settings) === JSON.stringify(settingsSnapshot))}
                >
                  {settingsSaving ? "保存中…" : "保存设置"}
                </button>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

function defaultStageCards(): RunStageCard[] {
  return [
    { stage: "scan", label: "扫描", detail: "查找项目与图纸文件", done: false },
    { stage: "convert", label: "转换", detail: "图纸格式转换", done: false },
    { stage: "extract", label: "识别", detail: "识别文字、导线与端子", done: false },
    { stage: "pair", label: "配对", detail: "建立端子连接关系", done: false },
    { stage: "audit", label: "检查", detail: "按电气规则核对", done: false },
    { stage: "render", label: "整理", detail: "整理结果与定位信息", done: false },
  ]
}

function stageProgress(stage: string): number {
  const order = ["scan", "convert", "extract", "pair", "audit", "render"]
  const index = order.indexOf(stage)
  return index < 0 ? 0 : (index + 1) / order.length
}

function stageOrder(stage: string): number {
  return ["scan", "convert", "extract", "pair", "audit", "render"].indexOf(stage)
}

function getPathBaseName(path: string): string {
  const segments = path.replace(/[\\/]+$/, "").split(/[\\/]+/)
  return segments[segments.length - 1] || path
}

function moveProjectFlowDots(
  dots: AuditFlowDot[],
  projectKey: string | null,
  phase: AuditFlowDot["phase"],
): AuditFlowDot[] {
  if (!projectKey) {
    return dots
  }
  return dots.map((dot) =>
    dot.projectRoot === projectKey || dot.projectName === projectKey
      ? { ...dot, phase }
      : dot,
  )
}

function upsertProjectCoverage(
  coverage: ProcessState["coverageByProject"],
  projectName: string,
  coverageRatio: number | null,
): ProcessState["coverageByProject"] {
  return [
    ...coverage.filter((item) => item.projectName !== projectName),
    { projectName, coverageRatio },
  ]
}

function labelStage(stage: string): string {
  const map: Record<string, string> = {
    scan: "扫描图纸",
    convert: "转换图纸",
    extract: "识别图元",
    pair: "端子配对",
    audit: "规则检查",
    render: "整理结果",
  }
  return map[stage] ?? stage
}

function summarizeProgress(event: SidecarEvent): string {
  if (event.event !== "progress") {
    return ""
  }
  if (event.stage === "scan") {
    return `已发现 ${event.file_count ?? 0} 个文件、${event.sheet_count ?? 0} 张图纸`
  }
  if (event.stage === "convert") {
    return `待转换 ${event.file_count ?? 0} 张图纸`
  }
  if (event.stage === "extract") {
    return `已识别 ${event.text_count ?? 0} 处文字、${event.line_count ?? 0} 条线段`
  }
  if (event.stage === "pair") {
    return `已建立 ${event.pair_count ?? 0} 组端子连接`
  }
  if (event.stage === "audit") {
    return `已发现 ${event.issue_count ?? 0} 个问题`
  }
  return "正在整理结果"
}

function formatSidecarLog(event: SidecarEvent): string {
  const stamp = new Date().toLocaleTimeString("zh-CN", { hour12: false })
  switch (event.event) {
    case "run_started":
      return `[${stamp}] 开始校验`
    case "project_started":
      return `[${stamp}] 正在处理项目`
    case "project_artifacts_ready":
      return `[${stamp}] 图纸数据已准备就绪`
    case "progress":
      return `[${stamp}] ${labelStage(event.stage)} · ${summarizeProgress(event)}`
    case "page_started":
      return `[${stamp}] 开始处理 · ${formatLogDrawingName(event.filename)}`
    case "page_finished":
      return `[${stamp}] 完成 · ${formatLogDrawingName(event.filename)} · ${labelPageStatus(event.status)}`
    case "warning":
      return `[${stamp}] 注意 · ${formatLogDrawingName(event.filename) || "图纸"} · ${humanizeRuntimeMessage(event.message)}`
    case "issue_found": {
      const source = formatSourcePage({
        filename: event.filename ?? "",
        sheet_no: event.sheet_no ?? "",
        evidence: {
          sheet_title: event.sheet_title ?? "",
          filename: event.filename ?? "",
          sheet_no: event.sheet_no ?? "",
        },
      })
      const sourceText = source.secondary ? `${source.label} · ${source.secondary}` : source.label
      return `[${stamp}] 发现问题 · ${labelHandlingClass(event.handling_class ?? event.severity)} · ${event.title} · ${sourceText}`
    }
    case "audit_finished":
      return `[${stamp}] 检查完成 · 共 ${event.issue_count} 个问题`
    case "project_stored":
      return `[${stamp}] 结果已保存 · ${event.project_name} · ${event.issue_count} 个问题`
    case "run_finished":
      return `[${stamp}] 校验结束 · 共 ${event.project_count} 个项目`
    default:
      return `[${stamp}] 运行中`
  }
}

/** 列表“位置”列：简短摘要 + 悬停时列出各位置。 */
function describeIssueLocationCell(issue: IssueSummary): { label: string; detail: string } {
  const views = getIssueLocations(issue)
  return {
    label: summarizeLocations(views),
    detail: views.length ? views.map((view) => view.title).join("\n") : "未定位到图纸",
  }
}

/** 更多技术细节中的结构化字段（客户界面不直接展示）。 */
function buildTechnicalRows(
  issue: IssueSummary,
  structuredLocation: { coords: string; lineGroupId: string | null },
): InspectorTechnicalRow[] {
  const codes: unknown = Array.isArray(issue.evidence.resolution_reason_codes)
    ? issue.evidence.resolution_reason_codes
    : issue.evidence.reason_codes
  const reasonText = Array.isArray(codes) ? codes.map((code) => String(code)).join("、") : ""
  const pairIds = [issue.primary_pair_id, ...issue.related_pair_ids].filter((value): value is string => Boolean(value))
  return [
    { label: "处理分桶", value: labelHandlingClass(resolveHandlingClass(issue)) },
    {
      label: "处理组",
      value:
        (issue.review_group_size ?? 1) > 1
          ? `${humanizeReviewGroupLabel(issue)}（${issue.review_group_size} 处）`
          : humanizeReviewGroupLabel(issue) || "单条问题",
    },
    { label: "问题类别", value: labelIssueCategory(issue) },
    { label: "连接关系", value: labelTriage(issue.one_to_many_classification ?? readOneToManyClassification(issue)) },
    { label: "程序把握度", value: formatConfidence(issue.confidence) },
    { label: "线端说明", value: formatLineSemantics(issue) || "-" },
    { label: "坐标", value: structuredLocation.coords || "-", mono: true },
    { label: "pair_id", value: pairIds.join("、") || "-", mono: true },
    { label: "line_group_id", value: issue.line_group_id ?? structuredLocation.lineGroupId ?? "-", mono: true },
    { label: "rule_id", value: issue.rule_id || "-", mono: true },
    { label: "reason_codes", value: reasonText || "-", mono: true },
    { label: "issue_id", value: issue.issue_id, mono: true },
  ]
}

function buildScoreRows(scoreBreakdown: Record<string, number | string>): InspectorTechnicalRow[] {
  return Object.entries(scoreBreakdown).map(([key, value]) => ({
    label: labelBreakdownKey(key),
    value: formatBreakdownValue(value),
  }))
}

function buildRawSections(issue: IssueSummary): Array<{ title: string; text: string }> {
  const sections: Array<{ title: string; text: string }> = []
  const superworks = readSuperworksEvidence(issue)
  if (superworks) {
    sections.push({ title: "来源：superworks", text: JSON.stringify(superworks, null, 2) })
  }
  sections.push({ title: "证据链（原始）", text: JSON.stringify(readEvidenceChain(issue), null, 2) })
  sections.push({ title: "原始证据", text: JSON.stringify(issue.evidence, null, 2) })
  return sections
}

function formatLogDrawingName(filename: string | null | undefined): string {
  if (!filename) {
    return "图纸"
  }
  return formatDrawingName(filename) || filename
}

function humanizeRuntimeMessage(message: string | null | undefined): string {
  if (!message) {
    return "出现提示"
  }
  let text = message.trim()
  // Common converter / pipeline English leaks.
  const replacements: Array<[RegExp, string]> = [
    [/missing converter/gi, "缺少转换工具"],
    [/invalid header/gi, "文件头异常"],
    [/timed? out/gi, "处理超时"],
    [/permission denied/gi, "无访问权限"],
    [/not found/gi, "未找到"],
    [/failed/gi, "失败"],
    [/error/gi, "错误"],
    [/warning/gi, "警告"],
    [/Duplicate sheet numbers detected[^.]*\.?/gi, "发现重复图号，已按图纸顺序继续处理。"],
  ]
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement)
  }
  return text
}

function formatPair(issue: Pick<IssueSummary, "left_value" | "right_value">): string {
  const left = issue.left_value?.trim() || "未识别"
  const right = issue.right_value?.trim() || "未识别"
  return `${left} → ${right}`
}

function formatCoverageRatio(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "未提供"
  }
  const percentage = Math.abs(value) <= 1 ? value * 100 : value
  return `${percentage.toFixed(1)}%`
}

function labelDiagnosticPresentation(value: string): string {
  const labels: Record<string, string> = {
    terminal: "端子级",
    observation: "识别观察",
    page_summary: "页面汇总",
    issue: "其他诊断",
  }
  return labels[value] ?? value.replaceAll("_", " ")
}

function labelDiagnosticReason(value: string): string {
  const labels: Record<string, string> = {
    unresolved_endpoint_identity: "端点身份未定",
    unresolved_pin_text: "脚号文字未定",
    endpoint_identity_missing: "缺少端点身份",
    missing_label_reference: "缺少标签引用",
    same_physical_port: "疑似同一物理端口",
    label_far_from_symbol: "标签离符号较远",
    unpinned_element: "元件脚号未识别",
    native_relation_incomplete: "SuperWORKS 原生关系不完整",
    unspecified: "未分类",
  }
  return labels[value] ?? value.replaceAll("_", " ")
}

function resolveHandlingClass(issue: Pick<IssueSummary, "handling_class" | "rule_id" | "severity" | "confidence" | "evidence" | "one_to_many_classification">): string {
  const direct = String(issue.handling_class || "").trim().toLowerCase()
  if (direct === "error" || direct === "warning" || direct === "review") {
    return direct
  }
  const fromEvidence = String(issue.evidence?.handling_class || "").trim().toLowerCase()
  if (fromEvidence === "error" || fromEvidence === "warning" || fromEvidence === "review") {
    return fromEvidence
  }
  const triage = String(
    issue.one_to_many_classification ||
      issue.evidence?.one_to_many_classification ||
      issue.evidence?.many_to_one_classification ||
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
    all: "全部",
  }
  if (!value) {
    return "须人工校验"
  }
  return map[value] ?? value
}

function isSeriousSeverity(value: string | null | undefined): boolean {
  const key = String(value || "").toLowerCase()
  return ["critical", "error", "high", "major"].includes(key)
}

function describeProcessStatus(state: ProcessState, analyzing: boolean): string {
  if (state.analysisIncomplete) {
    return "部分图纸读取未完成，上一份成功快照保持可用。"
  }
  if (state.failureMessage) {
    return "本次校验失败，上一份成功快照保持可用。"
  }
  if (!analyzing && state.completedProjects.length) {
    return `校验完成：${state.completedProjects.length} 个项目，共发现 ${state.liveIssues.length} 个问题`
  }
  if (!analyzing) {
    return "等待开始校验"
  }
  const stageLabel = labelStage(state.activeStage)
  if (state.totalSheets > 0) {
    return `${stageLabel}中 · 已完成 ${state.completedPages}/${state.totalSheets} 张图纸`
  }
  return `${stageLabel}中`
}

function shortenPath(path: string, max = 48): string {
  const normalized = path.replace(/\\/g, "/").trim()
  if (normalized.length <= max) {
    return normalized
  }
  const parts = normalized.split("/").filter(Boolean)
  if (parts.length <= 2) {
    return `…${normalized.slice(-(max - 1))}`
  }
  const tail = parts.slice(-2).join("/")
  if (tail.length + 2 >= max) {
    return `…${tail.slice(-(max - 1))}`
  }
  return `…/${tail}`
}

function formatDrawingName(filename: string | null | undefined): string {
  return stripDrawingExtension(filename)
}

/** 来源图纸：主标签是图名（回退见 resolveSheetName），页码只作副文字且仅在主标签是图名时显示。 */
function formatSourcePage(
  issue: Pick<IssueSummary, "filename" | "sheet_no" | "evidence">,
): { label: string; secondary: string; detail: string } {
  const sheetNo = cleanText(issue.sheet_no) || cleanText(issue.evidence?.sheet_no)
  const fileName = cleanText(issue.filename) || cleanText(issue.evidence?.filename)
  const sheet = resolveSheetName({ sheetTitle: issue.evidence?.sheet_title, filename: fileName, sheetNo })
  const pageText = sheetNo ? `第 ${sheetNo} 页` : ""
  const showPage = sheet.source === "title" || sheet.source === "file"
  const fileLabel = stripDrawingExtension(fileName)
  const detailParts = [
    sheet.name,
    pageText || null,
    fileLabel && fileLabel !== sheet.name ? `文件 ${fileLabel}` : null,
  ].filter((value): value is string => Boolean(value))
  return {
    label: sheet.name,
    secondary: showPage ? pageText : "",
    detail: detailParts.join(" · "),
  }
}

function readSuperworksEvidence(issue: Pick<IssueSummary, "evidence">): Record<string, unknown> | null {
  const evidence = issue.evidence ?? {}
  const nested = evidence.pair_evidence
  const pair = nested && typeof nested === "object" && !Array.isArray(nested)
    ? nested as Record<string, unknown> : evidence
  const sw = pair.superworks
  return sw && typeof sw === "object" && !Array.isArray(sw) ? sw as Record<string, unknown> : null
}

function readOneToManyClassification(issue: Pick<IssueSummary, "one_to_many_classification" | "evidence">): string | null {
  if (typeof issue.one_to_many_classification === "string" && issue.one_to_many_classification.trim()) {
    return issue.one_to_many_classification
  }
  const value = issue.evidence.one_to_many_classification
  return typeof value === "string" && value.trim() ? value : null
}

function readScoreBreakdown(evidence: Record<string, unknown>): Record<string, number | string> {
  const nested = evidence.pair_evidence
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    const scoreBreakdown = (nested as Record<string, unknown>).score_breakdown
    if (scoreBreakdown && typeof scoreBreakdown === "object" && !Array.isArray(scoreBreakdown)) {
      return scoreBreakdown as Record<string, number | string>
    }
  }
  const direct = evidence.score_breakdown
  if (direct && typeof direct === "object" && !Array.isArray(direct)) {
    return direct as Record<string, number | string>
  }
  return {}
}

function readPairEvidence(issue: Pick<IssueSummary, "evidence">): Record<string, unknown> {
  const nested = issue.evidence.pair_evidence
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return nested as Record<string, unknown>
  }
  return issue.evidence
}

function readLineOrientation(issue: Pick<IssueSummary, "evidence">): string | null {
  const value = readPairEvidence(issue).line_orientation
  return typeof value === "string" && value.trim() ? value : null
}

function formatLineSemantics(issue: Pick<IssueSummary, "evidence">): string {
  const evidence = readPairEvidence(issue)
  const parts: string[] = []
  const orientation = readLineOrientation(issue)
  const leftSide = humanizeSideLabel(
    typeof evidence.left_side_label === "string" && evidence.left_side_label.trim() ? evidence.left_side_label : null,
  )
  const rightSide = humanizeSideLabel(
    typeof evidence.right_side_label === "string" && evidence.right_side_label.trim() ? evidence.right_side_label : null,
  )

  if (orientation) {
    parts.push(`方向：${labelLineOrientation(orientation)}`)
  }
  if (leftSide) {
    parts.push(`左端：${leftSide}`)
  }
  if (rightSide) {
    parts.push(`右端：${rightSide}`)
  }
  return parts.join("；")
}

function humanizeSideLabel(value: string | null): string | null {
  if (!value) {
    return null
  }
  const map: Record<string, string> = {
    left: "左侧",
    right: "右侧",
    top: "上侧",
    bottom: "下侧",
    start: "起点侧",
    end: "终点侧",
  }
  const key = value.trim().toLowerCase()
  if (map[key]) {
    return map[key]
  }
  // Drop pure English technical tokens.
  if (/^[a-z_]+$/i.test(value) && !/[\u4e00-\u9fff]/.test(value)) {
    return null
  }
  return value
}

function labelIssueCategory(
  issue: Pick<IssueSummary, "issue_family" | "rule_id" | "issue_type" | "title"> | Pick<IssueSummary, "issue_family" | "rule_id" | "title">,
): string {
  const family = String(issue.issue_family || "").trim()
  if (family && !looksTechnicalToken(family)) {
    return family
  }
  const byRule = labelRule(issue.rule_id)
  if (byRule && byRule !== "未分类") {
    return byRule
  }
  const issueType = "issue_type" in issue ? issue.issue_type : undefined
  const byType = labelIssueType(issueType)
  if (byType && byType !== "-") {
    return byType
  }
  return issue.title || "未分类"
}

function humanizeReviewGroupLabel(issue: Pick<IssueSummary, "review_group_label" | "title" | "issue_family" | "rule_id">): string {
  const raw = String(issue.review_group_label || "").trim()
  if (!raw) {
    return issue.title || labelIssueCategory(issue)
  }
  if (looksTechnicalToken(raw)) {
    return issue.title || labelIssueCategory(issue)
  }
  return raw
}

function looksTechnicalToken(value: string): boolean {
  return /^(R-|S\d{3,}|G\d{3,}|P\d{3,}|I\d{3,}|F\d{3,})/i.test(value) || /_/.test(value) && !/[\u4e00-\u9fff]/.test(value)
}

function readStructuredLocation(issue: IssueSummary | null): { coords: string; lineGroupId: string | null } {
  if (!issue) {
    return { coords: "", lineGroupId: null }
  }
  const evidence = readPairEvidence(issue)
  const lineGroupId =
    issue.line_group_id ??
    (typeof evidence.line_group_id === "string" && evidence.line_group_id.trim() ? evidence.line_group_id : null)
  const start = formatPoint(evidence.line_start)
  const end = formatPoint(evidence.line_end)
  if (start && end) {
    return { coords: `${start} → ${end}`, lineGroupId }
  }
  if (start) {
    return { coords: start, lineGroupId }
  }
  return { coords: "", lineGroupId }
}

function formatPoint(value: unknown): string | null {
  if (!Array.isArray(value) || value.length < 2) {
    return null
  }
  const [x, y] = value
  if (typeof x !== "number" || typeof y !== "number") {
    return null
  }
  return `(${x.toFixed(1)}, ${y.toFixed(1)})`
}

function readEvidenceChain(issue: Pick<IssueSummary, "evidence" | "evidence_refs" | "related_pair_ids" | "sheet_ids" | "values" | "primary_pair_id">): Record<string, unknown> {
  const evidence = issue.evidence
  const chain: Record<string, unknown> = {}
  for (const key of ["filename", "sheet_no", "sheet_order", "line_group_id", "line_start", "line_end", "pair_evidence", "line_orientation", "left_side_label", "right_side_label"]) {
    if (key in evidence) {
      chain[key] = evidence[key]
    }
  }
  if (issue.evidence_refs.length) {
    chain.evidence_refs = issue.evidence_refs
  }
  if (issue.related_pair_ids.length) {
    chain.related_pair_ids = issue.related_pair_ids
  }
  if (issue.sheet_ids.length) {
    chain.sheet_ids = issue.sheet_ids
  }
  if (issue.values.length) {
    chain.values = issue.values
  }
  if (issue.primary_pair_id) {
    chain.primary_pair_id = issue.primary_pair_id
  }
  if (Object.keys(chain).length > 0) {
    return chain
  }
  return evidence
}

function formatBreakdownValue(value: number | string): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(2)
  }
  return String(value)
}

function labelBreakdownKey(key: string): string {
  const map: Record<string, string> = {
    confidence: "总置信度",
    issue_conf: "问题置信度",
    pair_conf: "配对置信度",
    terminal_conf: "端点置信度",
    left_terminal_conf: "左端置信度",
    right_terminal_conf: "右端置信度",
    wire_candidate_score: "导线候选分",
    candidate_gap_score: "候选分差",
    vertical_alignment_score: "垂直对齐",
    horizontal_side_score: "左右侧一致性",
    text_type_score: "文本类型",
    height_score: "字高",
    distance_score: "距离",
    orientation_score: "方向一致性",
    same_line_score: "同线一致性",
    total: "合计",
  }
  if (map[key]) {
    return map[key]
  }
  return key
    .replace(/_/g, " ")
    .replace(/\bscore\b/gi, "分值")
    .replace(/\bconf(idence)?\b/gi, "把握")
    .replace(/\bleft\b/gi, "左")
    .replace(/\bright\b/gi, "右")
}

function isFailedPageStatus(status: string | null | undefined): boolean {
  if (!status) {
    return false
  }
  return !["converted", "cached", "skipped"].includes(status)
}

function describeInputRoot(inputRoot: string): { title: string; detail: string; tone: "ready" | "warn" } {
  const value = inputRoot.trim()
  if (!value) {
    return {
      title: "未选目录",
      detail: "请选择或拖入图纸项目文件夹后再开始校验。",
      tone: "warn",
    }
  }
  if (/^[a-zA-Z]:\\/.test(value) || value.startsWith("\\\\")) {
    if (isLikelyProjectFilePath(value)) {
      return {
        title: "请选择文件夹",
        detail: "应选择项目目录，而不是单个图纸文件。",
        tone: "warn",
      }
    }
    return {
      title: "目录已就绪",
      detail: "可开始对本机项目进行校验。",
      tone: "ready",
    }
  }
  return {
    title: "路径需确认",
    detail: "建议使用“选择目录”，避免路径填写错误。",
    tone: "warn",
  }
}

function isLikelyProjectFilePath(value: string): boolean {
  const leaf = value.replace(/[\\/]+$/, "").split(/[\\/]/).pop() ?? ""
  return /\.(dwg|dxf|prj|xml|json|md|txt|svg|png|jpg|jpeg|xlsx|html)$/i.test(leaf)
}

function pickDroppedInputRoot(paths: string[]): string | null {
  if (paths.length !== 1) {
    return null
  }
  const candidate = paths[0]?.trim()
  if (!candidate || isLikelyProjectFilePath(candidate)) {
    return null
  }
  return candidate
}

function normalizeToken(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "_") || "unknown"
}

function labelSeverity(value: string): string {
  const map: Record<string, string> = {
    critical: "严重",
    error: "错误",
    high: "高",
    major: "重要",
    medium: "中",
    warn: "警告",
    warning: "警告",
    review: "待复核",
    low: "低",
    info: "提示",
    minor: "次要",
  }
  return map[value.toLowerCase()] ?? "一般"
}

function labelIssueStatus(value: string): string {
  const map: Record<string, string> = {
    open: "待处理",
    ignored: "已忽略",
    resolved: "已处理",
    false_positive: "误报",
  }
  return map[value] ?? "待处理"
}

function labelTriage(value: string | null | undefined): string {
  if (!value) {
    return "普通连接"
  }
  const map: Record<string, string> = {
    branch: "正常分支",
    review: "待确认",
    conflict: "有冲突",
    none: "普通连接",
  }
  return map[value.toLowerCase()] ?? "待确认"
}

function labelProjectStatus(value: string): string {
  const map: Record<string, string> = {
    completed: "已完成",
    running: "进行中",
    failed: "失败",
    open: "待处理",
  }
  return map[value.toLowerCase()] ?? value
}

function labelRule(value: string | null | undefined): string {
  if (!value) {
    return "未分类"
  }
  const map: Record<string, string> = {
    "R-CROSS-PAGE-CONFLICT": "同一端子跨图接线不一致",
    "R-TABLE-MAPPING-SOURCE-CONFLICT": "端子表与图内连线不一致",
    "R-SEMANTIC-MAPPING-CONFLICT": "端子含义对应不一致",
    "R-ONE-TO-MANY": "一个端子接出多根线",
    "R-MANY-TO-ONE": "多个端子接到同一端子",
    "R-MISSING-RECIPROCAL": "连接缺少对向标注",
    "R-PAIR-MISSING-SIDE": "导线只识别到一端",
    "R-PAIR-LOW-CONFIDENCE": "导线两端配对不确定",
    "R-DUPLICATE-SAME-LINE": "同一导线重复标注",
    "R-DUPLICATE-PAIR": "重复的端子配对",
    "R-SHEET-PAGE-MISMATCH": "图号与页面不一致",
    "R-SUPERWORKS-CONFLICT": "端子图形重叠或引用异常",
  }
  if (map[value]) {
    return map[value]
  }
  if (value.startsWith("R-") || looksTechnicalToken(value)) {
    return "其他检查项"
  }
  return value
}

function labelIssueType(value: string | null | undefined): string {
  if (!value) {
    return "-"
  }
  const map: Record<string, string> = {
    pair_missing_side: "导线只识别到一端",
    pair_low_confidence: "导线两端配对不确定",
    duplicate_same_line: "同一导线重复标注",
    one_to_many: "一个端子接出多根线",
    many_to_one: "多个端子接到同一端子",
    cross_page_conflict: "跨页冲突",
    semantic_mapping_conflict: "端子含义对应不一致",
    table_mapping_source_conflict: "端子表与图内连线不一致",
    missing_reciprocal: "缺少回指",
    sheet_page_mismatch: "图号与页面不一致",
    duplicate_pair: "重复的端子配对",
  }
  if (map[value]) {
    return map[value]
  }
  if (value.startsWith("R-")) {
    return labelRule(value)
  }
  if (looksTechnicalToken(value)) {
    return "其他类型"
  }
  return value
}

function labelLineOrientation(value: string | null | undefined): string {
  if (!value) {
    return "-"
  }
  const map: Record<string, string> = {
    horizontal: "水平",
    vertical: "垂直",
    diagonal: "斜向",
    unknown: "未知",
  }
  return map[value.toLowerCase()] ?? value
}

function labelPageStatus(status: string): string {
  const map: Record<string, string> = {
    converted: "已转换",
    cached: "沿用缓存",
    skipped: "已跳过",
    failed: "失败",
    failed_invalid_header: "文件头异常",
    missing_converter: "缺少转换工具",
  }
  return map[status] ?? status
}

function formatConfidence(value: number): string {
  if (!Number.isFinite(value)) {
    return "-"
  }
  const ratio = value > 1 ? value / 100 : value
  return `${Math.round(Math.max(0, Math.min(1, ratio)) * 100)}%`
}

function downloadJsonFile(fileName: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = objectUrl
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}

function createPreviewClientSessionId(): string {
  const randomId = globalThis.crypto?.randomUUID?.()
  return randomId ? `session-${randomId}` : `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

function formatAuditTime(value: string): string {
  if (!value) {
    return "-"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString("zh-CN", { hour12: false })
}

export default App
