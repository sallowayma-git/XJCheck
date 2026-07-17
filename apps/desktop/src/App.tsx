import { isTauri } from "@tauri-apps/api/core"
import { getCurrentWindow } from "@tauri-apps/api/window"
import { startTransition, useDeferredValue, useEffect, useEffectEvent, useMemo, useRef, useState } from "react"

import "./App.css"
import logoUrl from "./assets/logo.png"
import { desktopApi } from "./lib/desktopApi"
import type { IssueSummary, ProjectResult, RecentProject, RunStageCard, SidecarEvent } from "./types"

type Screen = "launch" | "process" | "result"

const ISSUE_STATUS_OPTIONS = ["open", "ignored", "resolved", "false_positive"] as const
const PREVIEW_REQUEST_TIMEOUT_MS = 20_000

type ProcessState = {
  sessionId: string | null
  progressRatio: number
  activeStage: string
  totalSheets: number
  completedPages: number
  failedPages: number
  warningCount: number
  stageCards: RunStageCard[]
  logs: string[]
  liveIssues: IssueSummary[]
  completedProjects: RecentProject[]
}

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
  const [result, setResult] = useState<ProjectResult | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null)
  const [previewSrc, setPreviewSrc] = useState<string | null>(null)
  const [selectedPreviewSheetId, setSelectedPreviewSheetId] = useState<string | null>(null)
  const [selectedPreviewLineGroupId, setSelectedPreviewLineGroupId] = useState<string | null>(null)
  const [previewGeneration, setPreviewGeneration] = useState(0)
  const [issueSearch, setIssueSearch] = useState("")
  const [severityFilter, setSeverityFilter] = useState("all")
  const [ruleFilter, setRuleFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [triageFilter, setTriageFilter] = useState("all")
  const [handlingFilter, setHandlingFilter] = useState("all")
  const [issueStatusDraft, setIssueStatusDraft] = useState("open")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isPickingDirectory, setIsPickingDirectory] = useState(false)
  const [isRefreshingPreview, setIsRefreshingPreview] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isSavingIssueStatus, setIsSavingIssueStatus] = useState(false)
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
    completedPages: 0,
    failedPages: 0,
    warningCount: 0,
    stageCards: defaultStageCards(),
    logs: [],
    liveIssues: [],
    completedProjects: [],
  })
  const processEventQueueRef = useRef<SidecarEvent[]>([])
  const processFlushTimerRef = useRef<number | null>(null)


  const refreshRecentProjects = useEffectEvent(async () => {
    try {
      const projects = await desktopApi.listRecentProjects()
      setRecentProjects(projects)
      if (!selectedProjectId && projects[0]) {
        setSelectedProjectId(projects[0].project_id)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "刷新最近项目失败。"
      setLoadError(message)
    }
  })

  useEffect(() => {
    void refreshRecentProjects()
  }, [refreshRecentProjects])

  useEffect(() => {
    if (!isTauri()) {
      return
    }
    let unlisten: (() => void) | undefined
    void getCurrentWindow()
      .onCloseRequested((event) => {
        event.preventDefault()
        // Closing must never wait for a disk-heavy sidecar. Rust also cancels
        // the active preview process tree when the event loop exits.
        void desktopApi.cancelPreview().catch(() => undefined)
        void getCurrentWindow().destroy()
      })
      .then((fn) => {
        unlisten = fn
      })
    return () => {
      unlisten?.()
    }
  }, [])

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
  }, [handleDroppedPaths, screen])

  const loadProjectResult = useEffectEvent(async (projectId: string) => {
    setLoadError(null)
    try {
      setIssueSearch("")
      setSeverityFilter("all")
      setRuleFilter("all")
      setStatusFilter("all")
      setTriageFilter("all")
      setHandlingFilter("all")
      const loaded = await desktopApi.loadResult(projectId)
      setResult(loaded)
      const initialIssue = loaded.issues[0] ?? null
      setSelectedIssueId(initialIssue?.issue_id ?? null)
      setSelectedPreviewSheetId(initialIssue?.sheet_id ?? null)
      setSelectedPreviewLineGroupId(initialIssue?.line_group_id ?? null)
      setPreviewSrc(null)
      startTransition(() => setScreen("result"))
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载项目结果失败，请重试。"
      setLoadError(message)
    }
  })

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
      }
      for (const event of events) {
        nextState = {
          ...nextState,
          logs: [...nextState.logs, formatSidecarLog(event)].slice(-40),
        }

        if (event.event === "run_started") {
          nextState.sessionId = event.session_id
        }

        if (event.event === "progress") {
          nextState.activeStage = event.stage
          nextState.progressRatio = stageProgress(event.stage)
          if (event.stage === "scan") {
            nextState.totalSheets = event.sheet_count ?? nextState.totalSheets
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

        if (event.event === "page_finished" && event.stage === "convert") {
          nextState.completedPages = nextState.completedPages + 1
          nextState.failedPages = nextState.failedPages + (isFailedPageStatus(event.status) ? 1 : 0)
        }

        if (event.event === "warning") {
          nextState.warningCount = nextState.warningCount + 1
        }

        if (event.event === "issue_found") {
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

        if (event.event === "project_stored") {
          nextState.completedProjects = [
            {
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
            },
          ]
        }

        if (event.event === "run_finished") {
          nextState.progressRatio = 1
          nextState.stageCards = nextState.stageCards.map((item) => ({ ...item, done: true }))
          nextState.completedProjects = event.projects
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
  }, [applyProcessEvents])

  async function handleAnalyzeClick() {
    const normalizedInputRoot = inputRoot.trim()
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
    setLoadError(null)
    setIsAnalyzing(true)
    setScreen("process")
    setProcessState({
      sessionId: null,
      progressRatio: 0.02,
      activeStage: "scan",
      totalSheets: 0,
      completedPages: 0,
      failedPages: 0,
      warningCount: 0,
      stageCards: defaultStageCards(),
      logs: [],
      liveIssues: [],
      completedProjects: [],
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
      await refreshRecentProjects()
      if (payload.projects[0]) {
        setSelectedProjectId(payload.projects[0].project_id)
        await loadProjectResult(payload.projects[0].project_id)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "校验失败，请检查项目目录后重试。"
      setLoadError(message)
      setScreen("launch")
    } finally {
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
      if (selectedProjectId === projectId) {
        setSelectedProjectId(null)
        setResult(null)
        setSelectedIssueId(null)
        setPreviewSrc(null)
        setPreviewError(null)
        if (screen === "result") {
          setScreen("launch")
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除项目记录失败。"
      setLoadError(message)
    } finally {
      setIsDeletingProjectId(null)
    }
  }

  const filteredIssues = useMemo(() => {
    const issues = result?.issues ?? []
    const needle = deferredIssueSearch.trim().toLowerCase()
    const filtered = issues.filter((issue) => {
      if (severityFilter !== "all" && issue.severity !== severityFilter) {
        return false
      }
      if (ruleFilter !== "all" && issue.rule_id !== ruleFilter) {
        return false
      }
      if (statusFilter !== "all" && issue.status !== statusFilter) {
        return false
      }
      const handling = resolveHandlingClass(issue)
      if (handlingFilter !== "all" && handling !== handlingFilter) {
        return false
      }
      const triage = issue.one_to_many_classification ?? readOneToManyClassification(issue)
      if (triageFilter !== "all" && (triage ?? "") !== triageFilter) {
        return false
      }
      if (!needle) {
        return true
      }
      return [
        issue.title,
        issue.summary,
        issue.explanation,
        issue.recommended_action,
        issue.filename,
        issue.sheet_no,
        issue.left_value ?? "",
        issue.right_value ?? "",
        labelRule(issue.rule_id),
        labelIssueType(issue.issue_type),
        labelSeverity(issue.severity),
        labelIssueStatus(issue.status),
        labelHandlingClass(handling),
        issue.review_group_label ?? "",
        issue.issue_family ?? "",
        triage ?? "",
        formatPair(issue),
        formatSourcePage(issue).detail,
        formatSourcePage(issue).label,
        formatIssueLocation(issue).label,
        formatIssueLocation(issue).detail,
        issue.values.join(" "),
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    })
    return [...filtered].sort(compareIssuesForReview)
  }, [deferredIssueSearch, handlingFilter, result?.issues, ruleFilter, severityFilter, statusFilter, triageFilter])

  const issueStats = useMemo(() => {
    const issues = result?.issues ?? []
    let openCount = 0
    let seriousOpenCount = 0
    let resolvedCount = 0
    let errorCount = 0
    let warningCount = 0
    let reviewCount = 0
    const groupIds = new Set<string>()
    for (const issue of issues) {
      const handling = resolveHandlingClass(issue)
      if (handling === "error") {
        errorCount += 1
      } else if (handling === "warning") {
        warningCount += 1
      } else {
        reviewCount += 1
      }
      groupIds.add(issue.review_group_id || issue.issue_id)
      if (issue.status === "open") {
        openCount += 1
        if (isSeriousSeverity(issue.severity) || handling === "error") {
          seriousOpenCount += 1
        }
      } else if (issue.status === "resolved") {
        resolvedCount += 1
      }
    }
    return {
      total: issues.length,
      openCount,
      seriousOpenCount,
      resolvedCount,
      errorCount,
      warningCount,
      reviewCount,
      groupCount: groupIds.size,
    }
  }, [result?.issues])

  const issueFilterOptions = useMemo(() => {
    const issues = result?.issues ?? []
    return {
      severities: Array.from(new Set(issues.map((issue) => issue.severity))).sort(compareSeverity),
      rules: Array.from(new Set(issues.map((issue) => issue.rule_id))).sort((left, right) =>
        labelRule(left).localeCompare(labelRule(right), "zh-CN"),
      ),
      statuses: Array.from(new Set(issues.map((issue) => issue.status))).sort(),
      triages: Array.from(
        new Set(
          issues
            .map((issue) => issue.one_to_many_classification ?? readOneToManyClassification(issue))
            .filter((value): value is string => Boolean(value)),
        ),
      ).sort(),
    }
  }, [result?.issues])

  const selectedIssue = useMemo(() => {
    if (!filteredIssues.length) {
      return null
    }
    if (!selectedIssueId) {
      return filteredIssues[0] ?? null
    }
    return filteredIssues.find((issue) => issue.issue_id === selectedIssueId) ?? filteredIssues[0] ?? null
  }, [filteredIssues, selectedIssueId])

  const summaryProject =
    result?.run ??
    recentProjects.find((project) => project.project_id === selectedProjectId) ??
    recentProjects[0] ??
    null
  const inputHealth = describeInputRoot(inputRoot)
  const previewOptions = useMemo(() => buildPreviewOptions(selectedIssue), [selectedIssue])
  const evidenceRefEntries = useMemo(() => buildEvidenceRefEntries(selectedIssue), [selectedIssue])
  const activePreviewOption =
    previewOptions.find((option) => option.sheetId === selectedPreviewSheetId) ??
    previewOptions[0] ??
    null
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
      if (selectedPreviewSheetId !== null) {
        setSelectedPreviewSheetId(null)
      }
      if (selectedPreviewLineGroupId !== null) {
        setSelectedPreviewLineGroupId(null)
      }
      return
    }

    if (!previewOptions.length) {
      if (selectedPreviewSheetId !== selectedIssue.sheet_id) {
        setSelectedPreviewSheetId(selectedIssue.sheet_id)
      }
      if (selectedPreviewLineGroupId !== selectedIssue.line_group_id) {
        setSelectedPreviewLineGroupId(selectedIssue.line_group_id)
      }
      return
    }

    if (!selectedPreviewSheetId || !previewOptions.some((option) => option.sheetId === selectedPreviewSheetId)) {
      setSelectedPreviewSheetId(previewOptions[0].sheetId)
      setSelectedPreviewLineGroupId(resolvePreviewLineGroupForSheet(selectedIssue, previewOptions[0].sheetId))
    }
  }, [previewOptions, selectedIssue, selectedPreviewLineGroupId, selectedPreviewSheetId])

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

  useEffect(() => {
    const projectId = result?.run.project_id ?? selectedProjectId
    if (screen !== "result") {
      setIsRefreshingPreview(false)
      setPreviewError(null)
      return
    }
    if (!projectId || !selectedIssue) {
      setPreviewSrc(null)
      setPreviewError(null)
      setIsRefreshingPreview(false)
      return
    }

    let cancelled = false
    setIsRefreshingPreview(true)
    setPreviewError(null)

    const timer = window.setTimeout(() => {
      void withTimeout(
        desktopApi.renderPreview(projectId, selectedIssue.issue_id, selectedPreviewSheetId, selectedPreviewLineGroupId),
        PREVIEW_REQUEST_TIMEOUT_MS,
        "Preview request timed out.",
      )
        .then((preview) => {
          if (cancelled) {
            return
          }
          setPreviewSrc(preview.preview_src)
          setPreviewError(null)
          setIsRefreshingPreview(false)
        })
        .catch((error) => {
          if (cancelled) {
            return
          }
          const message =
            error instanceof Error ? humanizePreviewError(error.message) : "无法生成该问题的图纸预览，可先查看下方文字说明。"
          // Keep preview failures local so the inspector stays usable.
          setPreviewError(message)
          setPreviewSrc(null)
          setIsRefreshingPreview(false)
        })
    }, 240)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
      void desktopApi.cancelPreview().catch(() => undefined)
    }
  }, [previewGeneration, result?.run.project_id, screen, selectedIssue, selectedPreviewLineGroupId, selectedPreviewSheetId, selectedProjectId])

  async function handleIssueStatusSave() {
    const projectId = result?.run.project_id ?? selectedProjectId
    if (!projectId || !selectedIssue) {
      return
    }
    setIsSavingIssueStatus(true)
    try {
      const updated = await desktopApi.setIssueStatus(projectId, selectedIssue.issue_id, issueStatusDraft)
      setResult(updated)
      setLoadError(null)
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存处理状态失败，请稍后重试。"
      setLoadError(message)
    } finally {
      setIsSavingIssueStatus(false)
    }
  }

  function handlePreviewRegenerateClick() {
    if (!selectedIssue) {
      return
    }
    setPreviewGeneration((current) => current + 1)
  }

  const screenTitle = screen === "launch" ? "项目" : screen === "process" ? "校验中" : "问题"
  const isNativeRuntime = desktopApi.isNative()
  const sessionLabel = isAnalyzing
    ? `正在校验 ${Math.round(processState.progressRatio * 100)}%`
    : summaryProject?.project_name ?? "尚未打开项目"
  const processStatusText = describeProcessStatus(processState, isAnalyzing)

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
          <button type="button" className={screen === "launch" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("launch")}>
            项目
          </button>
          <button type="button" className={screen === "process" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("process")}>
            校验中
          </button>
          <button type="button" className={screen === "result" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("result")}>
            问题
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
                          className={project.project_id === selectedProjectId ? "selected-row" : ""}
                          onClick={() => {
                            setSelectedProjectId(project.project_id)
                            void loadProjectResult(project.project_id)
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
                            <span className={`chip status-${normalizeToken(project.status)}`}>{labelProjectStatus(project.status)}</span>
                          </td>
                          <td className="actions-col">
                            <div className="row-actions">
                              <button
                                type="button"
                                className="ghost-button"
                                disabled={isAnalyzing}
                                onClick={(event) => {
                                  event.stopPropagation()
                                  setSelectedProjectId(project.project_id)
                                  void loadProjectResult(project.project_id)
                                }}
                              >
                                查看
                              </button>
                              <button
                                type="button"
                                className="danger-button"
                                disabled={isDeletingProjectId === project.project_id || isAnalyzing}
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
                <strong>{isAnalyzing ? "校验进行中" : processState.progressRatio >= 1 ? "校验已完成" : "等待开始"}</strong>
                <span>{processStatusText}</span>
                {!isAnalyzing && processState.progressRatio >= 1 ? (
                  <button type="button" className="primary-button" onClick={() => setScreen("result")}>
                    查看问题清单
                  </button>
                ) : null}
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
                  <strong>{processState.totalSheets}</strong>
                  <span>图纸总数</span>
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
                  <strong>{processState.liveIssues.length}</strong>
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
                      <th>把握</th>
                    </tr>
                  </thead>
                  <tbody>
                    {processState.liveIssues.length ? (
                      processState.liveIssues.map((issue) => {
                        const source = formatSourcePage(issue)
                        const location = formatIssueLocation(issue)
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
                                <span className="muted">{labelIssueCategory(issue)}</span>
                              </div>
                            </td>
                            <td>{formatPair(issue)}</td>
                            <td title={location.detail}>{location.label}</td>
                            <td title="识别把握，不是问题严重程度">{formatConfidence(issue.confidence)}</td>
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
              <div className="panel-pad" style={{ paddingBottom: 0 }}>
                <div className="section-heading">
                  <h3>运行提示</h3>
                  <span>{processState.logs.length} 条</span>
                </div>
              </div>
              <pre className="log-stream">{processState.logs.length ? processState.logs.join("\n") : "点击“开始校验”后，这里会显示当前步骤。"}</pre>
            </article>
          </section>
        )}

        {screen === "result" && (
          <section className="result-layout">
            <article className="panel result-toolbar">
              <div className="result-toolbar-metrics">
                <div className="metric-card">
                  <strong>{summaryProject?.sheet_count ?? 0}</strong>
                  <span>图纸页</span>
                </div>
                <div className="metric-card">
                  <strong>{issueStats.total}</strong>
                  <span>问题总数</span>
                </div>
                <div className="metric-card metric-error">
                  <strong>{issueStats.errorCount}</strong>
                  <span>确定性错误</span>
                </div>
                <div className="metric-card metric-warning">
                  <strong>{issueStats.warningCount}</strong>
                  <span>可能有错误</span>
                </div>
                <div className="metric-card metric-review">
                  <strong>{issueStats.reviewCount}</strong>
                  <span>须人工校验</span>
                </div>
                <div className="metric-card">
                  <strong>{issueStats.groupCount}</strong>
                  <span>处理组</span>
                </div>
                <span className="muted" title={summaryProject?.project_name ?? undefined}>
                  {summaryProject?.project_name ?? "未加载项目"}
                </span>
              </div>
              <div className="handling-chip-row" aria-label="问题处理分桶">
                <button
                  type="button"
                  className={handlingFilter === "all" ? "handling-chip active" : "handling-chip"}
                  onClick={() => setHandlingFilter("all")}
                >
                  全部 {issueStats.total}
                </button>
                <button
                  type="button"
                  className={handlingFilter === "error" ? "handling-chip active handling-error" : "handling-chip handling-error"}
                  onClick={() => setHandlingFilter("error")}
                >
                  确定性错误 {issueStats.errorCount}
                </button>
                <button
                  type="button"
                  className={handlingFilter === "warning" ? "handling-chip active handling-warning" : "handling-chip handling-warning"}
                  onClick={() => setHandlingFilter("warning")}
                >
                  可能有错误 {issueStats.warningCount}
                </button>
                <button
                  type="button"
                  className={handlingFilter === "review" ? "handling-chip active handling-review" : "handling-chip handling-review"}
                  onClick={() => setHandlingFilter("review")}
                >
                  须人工校验 {issueStats.reviewCount}
                </button>
                <button
                  type="button"
                  className={statusFilter === "open" ? "handling-chip active" : "handling-chip"}
                  onClick={() => setStatusFilter(statusFilter === "open" ? "all" : "open")}
                >
                  仅待处理 {issueStats.openCount}
                </button>
              </div>
              <p className="result-guide muted">
                建议顺序：先处理「确定性错误」，再看「可能有错误」，最后批量确认「须人工校验」。原则：可以误报，但不能错过真实错误。同类问题归到同一处理组。
              </p>
              <div className="result-toolbar-filters">
                <label className="field compact-field">
                  <span>搜索</span>
                  <input value={issueSearch} onChange={(event) => setIssueSearch(event.target.value)} placeholder="图号 / 端子号 / 说明" />
                </label>
                <label className="field compact-field">
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
                <label className="field compact-field">
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
                <label className="field compact-field">
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
                <label className="field compact-field">
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
            </article>

            <article className="panel result-issue-list">
              <div className="panel-pad" style={{ paddingBottom: 0 }}>
                <div className="section-heading">
                  <h3>问题清单</h3>
                  <span>
                    显示 {filteredIssues.length} / {issueStats.total}
                  </span>
                </div>
              </div>
              <div className="table-wrap">
                <table className="data-table compact">
                  <thead>
                    <tr>
                      <th>处理</th>
                      <th>问题说明</th>
                      <th>端子连接</th>
                      <th>来源图纸</th>
                      <th>位置</th>
                      <th>处理组</th>
                      <th>状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredIssues.length ? (
                      filteredIssues.map((issue) => {
                        const handling = resolveHandlingClass(issue)
                        const source = formatSourcePage(issue)
                        const location = formatIssueLocation(issue)
                        return (
                          <tr
                            key={issue.issue_id}
                            className={issue.issue_id === selectedIssue?.issue_id ? "selected-row" : ""}
                            onClick={() => {
                              setSelectedIssueId(issue.issue_id)
                            }}
                          >
                            <td>
                              <span className={`chip handling-${normalizeToken(handling)}`}>{labelHandlingClass(handling)}</span>
                            </td>
                            <td>
                              <div className="issue-title-cell">
                                <strong>{issue.title}</strong>
                                <span className="muted">{labelIssueCategory(issue)}</span>
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
                      })
                    ) : (
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
                    )}
                  </tbody>
                </table>
              </div>
            </article>

            <article className="result-inspector">
              <div className="panel inspector-header">
                <div className="section-heading">
                  <h3>问题详情</h3>
                  <span title={selectedIssue?.title ?? undefined}>{selectedIssue?.title ?? "未选择"}</span>
                </div>
                {selectedIssue ? (
                  <div className="inspector-badges">
                    <span className={`chip handling-${normalizeToken(resolveHandlingClass(selectedIssue))}`}>
                      {labelHandlingClass(resolveHandlingClass(selectedIssue))}
                    </span>
                    <span className={`badge severity-${normalizeToken(selectedIssue.severity)}`}>{labelSeverity(selectedIssue.severity)}</span>
                    <span className={`chip status-${normalizeToken(selectedIssue.status)}`}>{labelIssueStatus(selectedIssue.status)}</span>
                    <span className={`chip triage-${normalizeToken((selectedIssue.one_to_many_classification ?? readOneToManyClassification(selectedIssue) ?? "none") as string)}`}>
                      {labelTriage(selectedIssue.one_to_many_classification ?? readOneToManyClassification(selectedIssue))}
                    </span>
                  </div>
                ) : null}
                {selectedIssue ? (
                  <div className="status-editor">
                    <label className="field compact-field" style={{ minWidth: 120 }}>
                      <span>处理结论</span>
                      <select value={issueStatusDraft} onChange={(event) => setIssueStatusDraft(event.target.value)}>
                        {ISSUE_STATUS_OPTIONS.map((status) => (
                          <option key={status} value={status}>
                            {labelIssueStatus(status)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button type="button" className="ghost-button" disabled={isSavingIssueStatus} onClick={() => void handleIssueStatusSave()}>
                      {isSavingIssueStatus ? "保存中…" : "保存"}
                    </button>
                    <label className="field compact-field" style={{ minWidth: 160 }}>
                      <span>查看图纸</span>
                      <select
                        value={selectedPreviewSheetId ?? ""}
                        onChange={(event) => {
                          const nextSheetId = event.target.value || null
                          setSelectedPreviewSheetId(nextSheetId)
                          setSelectedPreviewLineGroupId(resolvePreviewLineGroupForSheet(selectedIssue, nextSheetId))
                        }}
                      >
                        {previewOptions.length ? (
                          previewOptions.map((option) => (
                            <option key={option.sheetId} value={option.sheetId}>
                              {option.label}
                            </option>
                          ))
                        ) : (
                          <option value="">暂无关联图纸</option>
                        )}
                      </select>
                    </label>
                    <button type="button" className="ghost-button" disabled={!selectedIssue || isRefreshingPreview} onClick={() => handlePreviewRegenerateClick()}>
                        {isRefreshingPreview ? "刷新中…" : "刷新预览"}
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="panel inspector-preview">
                <div className="preview-shell">
                  {previewSrc ? (
                    <img
                      src={previewSrc}
                      alt="问题定位预览"
                      className="preview-image"
                      onError={() => {
                        setPreviewSrc(null)
                        setPreviewError("预览图未能显示。请查看下方文字说明，或点击“刷新预览”。")
                      }}
                    />
                  ) : (
                    <div className={`preview-empty${selectedIssue && isRefreshingPreview ? " is-loading" : ""}`}>
                      {selectedIssue
                        ? isRefreshingPreview
                          ? "正在生成问题区域预览…"
                          : previewError
                            ? previewError
                            : previewOptions.length
                              ? "暂无预览图。可点击“刷新预览”，或直接阅读下方问题说明。"
                              : "当前问题没有可定位的图纸区域，请阅读文字说明。"
                        : "请从左侧选择一条问题进行复核。"}
                    </div>
                  )}
                </div>
              </div>

              <div className="panel inspector-detail">
                {selectedIssue ? (
                  <div className="issue-detail">
                    <div className="detail-block detail-title">
                      <span>问题说明</span>
                      <strong>{selectedIssue.title}</strong>
                    </div>
                    <div className="detail-grid">
                      <div className="detail-block">
                        <span>处理分桶</span>
                        <strong>{labelHandlingClass(resolveHandlingClass(selectedIssue))}</strong>
                      </div>
                      <div className="detail-block">
                        <span>处理组</span>
                        <strong title={selectedIssue.review_group_label || undefined}>
                          {(selectedIssue.review_group_size ?? 1) > 1
                            ? `${humanizeReviewGroupLabel(selectedIssue)}（${selectedIssue.review_group_size} 处）`
                            : humanizeReviewGroupLabel(selectedIssue) || "单条问题"}
                        </strong>
                      </div>
                      <div className="detail-block">
                        <span>问题类别</span>
                        <strong>{labelIssueCategory(selectedIssue)}</strong>
                      </div>
                      <div className="detail-block">
                        <span>来源图纸</span>
                        <strong>
                          {(() => {
                            const source = formatSourcePage(selectedIssue)
                            return source.secondary ? `${source.label} · ${source.secondary}` : source.label
                          })()}
                        </strong>
                      </div>
                      <div className="detail-block">
                        <span>端子连接</span>
                        <strong>{formatPair(selectedIssue)}</strong>
                      </div>
                      <div className="detail-block">
                        <span>相关端子号</span>
                        <strong>
                          {selectedIssue.values.length
                            ? selectedIssue.values.join("、")
                            : formatPair(selectedIssue)}
                        </strong>
                      </div>
                      <div className="detail-block">
                        <span>连接关系</span>
                        <strong>
                          {labelTriage(selectedIssue.one_to_many_classification ?? readOneToManyClassification(selectedIssue))}
                        </strong>
                      </div>
                      <div className="detail-block">
                        <span>识别把握</span>
                        <strong title="识别把握，不是问题严重程度">{formatConfidence(selectedIssue.confidence)}</strong>
                      </div>
                      <div className="detail-block">
                        <span>图纸位置</span>
                        <strong className={formatIssueLocation(selectedIssue).hasCoord ? "coords-mono" : undefined} title={formatIssueLocation(selectedIssue).detail}>
                          {formatIssueLocation(selectedIssue).label}
                        </strong>
                      </div>
                    </div>
                    {formatLineSemantics(selectedIssue) ? (
                      <div className="detail-block">
                        <span>线端说明</span>
                        <strong>{formatLineSemantics(selectedIssue)}</strong>
                      </div>
                    ) : null}
                    <div className="detail-block">
                      <span>摘要</span>
                      <strong>{selectedIssue.summary || selectedIssue.title}</strong>
                    </div>
                    <div className="detail-grid">
                      <div className="detail-block">
                        <span>详细说明</span>
                        <strong>{selectedIssue.explanation || "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>建议处理</span>
                        <strong>{selectedIssue.recommended_action || "-"}</strong>
                      </div>
                    </div>
                    <div className="detail-block">
                      <span>关联图纸位置</span>
                      {evidenceRefEntries.length ? (
                        <div className="evidence-ref-list">
                          {evidenceRefEntries.map((entry) => (
                            <button
                              key={entry.key}
                              type="button"
                              className={`evidence-ref-card ${entry.sheetId && entry.sheetId === selectedPreviewSheetId ? "active" : ""}`}
                              onClick={() => {
                                if (entry.sheetId) {
                                  setSelectedPreviewSheetId(entry.sheetId)
                                  setSelectedPreviewLineGroupId(entry.lineGroupId)
                                }
                              }}
                              disabled={!entry.sheetId}
                            >
                              <strong>{entry.title}</strong>
                              <span>{entry.subtitle}</span>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <strong className="muted">无额外图纸位置引用</strong>
                      )}
                    </div>
                    <div className="detail-grid">
                      <div className="detail-block">
                        <span>关联图纸</span>
                        <strong>
                          {formatRelatedSourcePages(selectedIssue).length
                            ? formatRelatedSourcePages(selectedIssue).join("；")
                            : formatSourcePage(selectedIssue).label}
                        </strong>
                      </div>
                      <div className="detail-block">
                        <span>当前预览</span>
                        <strong>
                          {isRefreshingPreview
                            ? "正在生成…"
                            : activePreviewOption
                              ? activePreviewOption.caption
                              : formatSourcePage(selectedIssue).label}
                        </strong>
                      </div>
                    </div>
                    <details className="raw-toggle">
                      <summary>更多技术细节（排障用，一般无需查看）</summary>
                      <p className="muted" style={{ margin: "8px 0 0", fontSize: 12 }}>
                        以下为内部编号与原始记录，不影响日常复核。
                      </p>
                      <div className="detail-block" style={{ marginTop: 8 }}>
                        <span>识别把握拆解</span>
                        {Object.keys(scoreBreakdown).length ? (
                          <div className="metric-row">
                            {Object.entries(scoreBreakdown).map(([key, value]) => (
                              <div key={key} className="metric-card compact-metric">
                                <strong>{formatBreakdownValue(value)}</strong>
                                <span>{labelBreakdownKey(key)}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <strong className="muted">无拆解项，仅有总体识别把握。</strong>
                        )}
                      </div>
                      <div className="detail-block" style={{ marginTop: 8 }}>
                        <span>内部编号（仅排障）</span>
                        <strong className="coords-mono">
                          {[
                            selectedIssue.issue_id ? `问题 ${selectedIssue.issue_id}` : null,
                            selectedIssue.rule_id ? `规则 ${selectedIssue.rule_id}` : null,
                            (selectedIssue.line_group_id ?? structuredLocation.lineGroupId)
                              ? `线组 ${selectedIssue.line_group_id ?? structuredLocation.lineGroupId}`
                              : null,
                            selectedIssue.primary_pair_id ? `主配对 ${selectedIssue.primary_pair_id}` : null,
                            selectedIssue.related_pair_ids.length
                              ? `关联配对 ${selectedIssue.related_pair_ids.join("、")}`
                              : null,
                            selectedIssue.sheet_id ? `页面 ${selectedIssue.sheet_id}` : null,
                          ]
                            .filter(Boolean)
                            .join(" · ") || "-"}
                        </strong>
                      </div>
                      <div className="detail-block" style={{ marginTop: 8 }}>
                        <span>证据链（原始）</span>
                        <pre>{JSON.stringify(readEvidenceChain(selectedIssue), null, 2)}</pre>
                      </div>
                      <div className="detail-block" style={{ marginTop: 8 }}>
                        <span>原始证据</span>
                        <pre>{JSON.stringify(selectedIssue.evidence, null, 2)}</pre>
                      </div>
                    </details>
                  </div>
                ) : (
                  <p className="empty-state">请从左侧选择问题，查看定位预览与处理建议。</p>
                )}
              </div>
            </article>
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

function handlingRank(value: string): number {
  if (value === "error") {
    return 0
  }
  if (value === "warning") {
    return 1
  }
  return 2
}

function compareSeverity(left: string, right: string): number {
  const rank = (value: string): number => {
    const key = value.toLowerCase()
    if (["critical", "error", "high"].includes(key)) {
      return 0
    }
    if (["major", "medium", "warning", "warn"].includes(key)) {
      return 1
    }
    if (["minor", "low", "info"].includes(key)) {
      return 2
    }
    if (["review"].includes(key)) {
      return 3
    }
    return 4
  }
  return rank(left) - rank(right) || left.localeCompare(right, "zh-CN")
}

function isSeriousSeverity(value: string | null | undefined): boolean {
  const key = String(value || "").toLowerCase()
  return ["critical", "error", "high", "major"].includes(key)
}

function compareIssuesForReview(left: IssueSummary, right: IssueSummary): number {
  const leftHandling = resolveHandlingClass(left)
  const rightHandling = resolveHandlingClass(right)
  const byHandling = handlingRank(leftHandling) - handlingRank(rightHandling)
  if (byHandling !== 0) {
    return byHandling
  }
  const leftOpen = left.status === "open" ? 0 : 1
  const rightOpen = right.status === "open" ? 0 : 1
  if (leftOpen !== rightOpen) {
    return leftOpen - rightOpen
  }
  const bySeverity = compareSeverity(left.severity, right.severity)
  if (bySeverity !== 0) {
    return bySeverity
  }
  const leftGroupSize = Number(left.review_group_size ?? 1)
  const rightGroupSize = Number(right.review_group_size ?? 1)
  if (rightGroupSize !== leftGroupSize) {
    return rightGroupSize - leftGroupSize
  }
  const byGroup = String(left.review_group_id || left.issue_id).localeCompare(String(right.review_group_id || right.issue_id), "zh-CN")
  if (byGroup !== 0) {
    return byGroup
  }
  const bySheet = String(left.sheet_no || "").localeCompare(String(right.sheet_no || ""), "zh-CN", { numeric: true })
  if (bySheet !== 0) {
    return bySheet
  }
  return left.title.localeCompare(right.title, "zh-CN")
}

function describeProcessStatus(state: ProcessState, analyzing: boolean): string {
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
  if (!filename) {
    return ""
  }
  return filename.replace(/\.(dwg|dxf)$/i, "")
}

function readSheetTitle(issue: Pick<IssueSummary, "evidence" | "filename">): string {
  const fromEvidence = issue.evidence?.sheet_title
  if (typeof fromEvidence === "string" && fromEvidence.trim()) {
    return fromEvidence.trim()
  }
  const stem = formatDrawingName(issue.filename)
  if (!stem) {
    return ""
  }
  // Common project naming: "05 差动保护回路图" → title after leading page number.
  const matched = stem.match(/^\s*\d+[A-Za-z]?\s+(.+)$/)
  return matched?.[1]?.trim() || stem
}

function formatSourcePage(
  issue: Pick<IssueSummary, "filename" | "sheet_no" | "evidence">,
): { label: string; secondary: string; detail: string } {
  const sheetNo = String(issue.sheet_no || issue.evidence?.sheet_no || "").trim()
  const title = readSheetTitle(issue)
  const fileLabel = formatDrawingName(issue.filename) || String(issue.evidence?.filename || "").replace(/\.(dwg|dxf)$/i, "")
  const detailParts = [
    sheetNo ? `图号 ${sheetNo}` : null,
    title || null,
    fileLabel && fileLabel !== title ? `文件 ${fileLabel}` : null,
  ].filter((value): value is string => Boolean(value))

  if (sheetNo && title) {
    return {
      label: `图号 ${sheetNo}`,
      secondary: title,
      detail: detailParts.join(" · "),
    }
  }
  if (sheetNo) {
    return {
      label: `图号 ${sheetNo}`,
      secondary: fileLabel && fileLabel !== sheetNo ? fileLabel : "",
      detail: detailParts.join(" · ") || `图号 ${sheetNo}`,
    }
  }
  if (title) {
    return {
      label: title,
      secondary: fileLabel && fileLabel !== title ? fileLabel : "",
      detail: detailParts.join(" · ") || title,
    }
  }
  if (fileLabel) {
    return { label: fileLabel, secondary: "", detail: fileLabel }
  }
  return { label: "来源页未识别", secondary: "", detail: "未能关联到具体图纸页" }
}

function formatPointPair(value: unknown): string | null {
  if (!Array.isArray(value) || value.length < 2) {
    return null
  }
  const x = Number(value[0])
  const y = Number(value[1])
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return null
  }
  return `(${x.toFixed(1)}, ${y.toFixed(1)})`
}

function formatIssueLocation(
  issue: Pick<IssueSummary, "evidence" | "filename" | "sheet_no" | "left_value" | "right_value">,
): { label: string; detail: string; hasCoord: boolean } {
  const evidence = issue.evidence ?? {}
  const nested =
    evidence.pair_evidence && typeof evidence.pair_evidence === "object" && !Array.isArray(evidence.pair_evidence)
      ? (evidence.pair_evidence as Record<string, unknown>)
      : null
  const start = formatPointPair(evidence.line_start ?? nested?.line_start)
  const end = formatPointPair(evidence.line_end ?? nested?.line_end)
  if (start && end) {
    return {
      label: `${start} → ${end}`,
      detail: `导线坐标 ${start} → ${end}（图纸坐标系）`,
      hasCoord: true,
    }
  }
  if (start) {
    return {
      label: start,
      detail: `导线端点坐标 ${start}（图纸坐标系）`,
      hasCoord: true,
    }
  }
  const source = formatSourcePage(issue)
  const pairHint = [issue.left_value, issue.right_value].filter(Boolean).join(" → ")
  if (source.label !== "来源页未识别") {
    return {
      label: "本页（无坐标）",
      detail: pairHint
        ? `已定位到 ${source.detail || source.label}，端子 ${pairHint}；导线几何坐标未写入本条问题`
        : `已定位到 ${source.detail || source.label}；导线几何坐标未写入本条问题`,
      hasCoord: false,
    }
  }
  return {
    label: "位置未知",
    detail: "未关联到来源图纸，也没有坐标",
    hasCoord: false,
  }
}

function formatRelatedSourcePages(issue: IssueSummary): string[] {
  const labels: string[] = []
  const seen = new Set<string>()
  const push = (meta: { sheet_no?: string | null; filename?: string | null; sheet_title?: string | null }) => {
    const fake: Pick<IssueSummary, "filename" | "sheet_no" | "evidence"> = {
      filename: meta.filename || "",
      sheet_no: meta.sheet_no || "",
      evidence: {
        sheet_title: meta.sheet_title || "",
        filename: meta.filename || "",
        sheet_no: meta.sheet_no || "",
      },
    }
    const source = formatSourcePage(fake)
    const key = source.detail || source.label
    if (!key || seen.has(key) || source.label === "来源页未识别") {
      return
    }
    seen.add(key)
    labels.push(source.secondary ? `${source.label} · ${source.secondary}` : source.label)
  }

  push({
    sheet_no: issue.sheet_no,
    filename: issue.filename,
    sheet_title: typeof issue.evidence?.sheet_title === "string" ? issue.evidence.sheet_title : null,
  })

  for (const ref of issue.evidence_refs) {
    if (!isRecord(ref)) {
      continue
    }
    push({
      sheet_no: readString(ref.sheet_no),
      filename: readString(ref.filename),
      sheet_title: readString(ref.sheet_title),
    })
  }
  return labels
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

function buildPreviewOptions(issue: IssueSummary | null): Array<{ sheetId: string; label: string; caption: string }> {
  if (!issue) {
    return []
  }

  const options = new Map<string, { sheetId: string; label: string; caption: string }>()

  const addOption = (
    sheetId: string | null | undefined,
    prefix: string,
    meta?: {
      sheetNo?: string | null
      filename?: string | null
      sheetTitle?: string | null
    },
  ) => {
    const normalized = sheetId?.trim()
    if (!normalized || options.has(normalized)) {
      return
    }

    const source = formatSourcePage({
      filename: meta?.filename || "",
      sheet_no: meta?.sheetNo || "",
      evidence: {
        sheet_title: meta?.sheetTitle || "",
        filename: meta?.filename || "",
        sheet_no: meta?.sheetNo || "",
      },
    })
    const pageText =
      source.label !== "来源页未识别"
        ? source.secondary
          ? `${source.label} · ${source.secondary}`
          : source.label
        : "关联图纸"
    options.set(normalized, {
      sheetId: normalized,
      label: `${prefix} · ${pageText}`,
      caption: source.detail || pageText,
    })
  }

  addOption(issue.sheet_id, "本页", {
    sheetNo: issue.sheet_no || null,
    filename: issue.filename || null,
    sheetTitle: typeof issue.evidence?.sheet_title === "string" ? issue.evidence.sheet_title : null,
  })

  for (const ref of issue.evidence_refs) {
    const record = isRecord(ref) ? ref : null
    addOption(readString(record?.sheet_id), "关联页", {
      sheetNo: readString(record?.sheet_no),
      filename: readString(record?.filename),
      sheetTitle: readString(record?.sheet_title),
    })
  }

  for (const relatedSheetId of issue.sheet_ids) {
    const matchingRef = issue.evidence_refs.find((ref) => isRecord(ref) && readString(ref.sheet_id) === relatedSheetId)
    const record = isRecord(matchingRef) ? matchingRef : null
    addOption(relatedSheetId, "关联页", {
      sheetNo: readString(record?.sheet_no),
      filename: readString(record?.filename),
      sheetTitle: readString(record?.sheet_title),
    })
  }

  if (!options.size && issue.sheet_id) {
    addOption(issue.sheet_id, "本页", {
      sheetNo: issue.sheet_no || null,
      filename: issue.filename || null,
    })
  }

  return Array.from(options.values())
}

function buildEvidenceRefEntries(
  issue: IssueSummary | null,
): Array<{ key: string; sheetId: string | null; lineGroupId: string | null; title: string; subtitle: string }> {
  if (!issue) {
    return []
  }

  return issue.evidence_refs.map((ref, index) => {
    const record = isRecord(ref) ? ref : null
    const sheetId = readString(record?.sheet_id)
    const sheetNo = readString(record?.sheet_no)
    const filename = readString(record?.filename)
    const sheetTitle = readString(record?.sheet_title)
    const pairId = readString(record?.pair_id)
    const lineGroupId = readString(record?.line_group_id)
    const start = formatPointPair(record?.line_start)
    const end = formatPointPair(record?.line_end)
    const coord =
      start && end ? `${start} → ${end}` : start || formatEvidenceCoord(record?.coord)

    const source = formatSourcePage({
      filename: filename || "",
      sheet_no: sheetNo || "",
      evidence: {
        sheet_title: sheetTitle || "",
        filename: filename || "",
        sheet_no: sheetNo || "",
      },
    })

    const titleBits = [`位置 ${index + 1}`]
    if (source.label !== "来源页未识别") {
      titleBits.push(source.secondary ? `${source.label} · ${source.secondary}` : source.label)
    }

    const subtitleBits = [coord || (source.label !== "来源页未识别" ? "本页（无坐标）" : null)].filter(
      (value): value is string => Boolean(value),
    )

    return {
      key: `${sheetId ?? "no-sheet"}:${pairId ?? lineGroupId ?? index}`,
      sheetId,
      lineGroupId,
      title: titleBits.join(" · "),
      subtitle: subtitleBits.join(" · ") || "点击切换预览图纸",
    }
  })
}

function formatEvidenceCoord(value: unknown): string | null {
  if (!Array.isArray(value) || value.length < 2) {
    return null
  }
  const [x, y] = value
  if (typeof x !== "number" || typeof y !== "number") {
    return null
  }
  return `位置 (${x.toFixed(1)}, ${y.toFixed(1)})`
}

function resolvePreviewLineGroupForSheet(issue: IssueSummary | null, sheetId: string | null): string | null {
  if (!issue || !sheetId) {
    return null
  }
  return issue.sheet_id === sheetId ? issue.line_group_id : null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null
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
    return "无特殊分支关系"
  }
  const map: Record<string, string> = {
    branch: "合法分支",
    review: "需人工确认",
    conflict: "存在冲突",
    none: "无特殊分支关系",
  }
  return map[value.toLowerCase()] ?? "需人工确认"
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
    "R-CROSS-PAGE-CONFLICT": "跨页端子冲突",
    "R-TABLE-MAPPING-SOURCE-CONFLICT": "表格与图内映射不一致",
    "R-SEMANTIC-MAPPING-CONFLICT": "端子语义映射冲突",
    "R-ONE-TO-MANY": "一对多连接",
    "R-MANY-TO-ONE": "多对一连接",
    "R-MISSING-RECIPROCAL": "缺少对端回指",
    "R-PAIR-MISSING-SIDE": "端子缺侧",
    "R-PAIR-LOW-CONFIDENCE": "端子配对不确定",
    "R-DUPLICATE-SAME-LINE": "同线重复端子",
    "R-DUPLICATE-PAIR": "重复配对",
    "R-SHEET-PAGE-MISMATCH": "页码不一致",
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
    pair_missing_side: "端子缺侧",
    pair_low_confidence: "配对不确定",
    duplicate_same_line: "同线重复",
    one_to_many: "一对多",
    many_to_one: "多对一",
    cross_page_conflict: "跨页冲突",
    semantic_mapping_conflict: "语义映射冲突",
    table_mapping_source_conflict: "表格映射冲突",
    missing_reciprocal: "缺少回指",
    sheet_page_mismatch: "页码不一致",
    duplicate_pair: "重复配对",
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

function humanizePreviewError(message: string): string {
  const lower = message.toLowerCase()
  if (lower.includes("no stored result") || lower.includes("no issue found")) {
    return "未找到该问题的校验结果，请重新打开项目或再次校验。"
  }
  if (lower.includes("extent") || lower.includes("bbox")) {
    return "缺少可定位的图纸区域，暂无法生成预览。请查看下方文字说明。"
  }
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "预览生成超时，请稍后点击“刷新预览”。"
  }
  if (message.includes("预览生成失败") || message.includes("preview")) {
    return "无法生成该问题的图纸预览，可先查看下方文字说明。"
  }
  // Strip raw technical prefixes that leak from the sidecar.
  return message
    .replace(/^预览生成失败（.*?）[。.]?\s*/u, "")
    .replace(/^Error:\s*/i, "")
    .trim() || "无法生成预览，请查看文字说明。"
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error(message)), timeoutMs)
    promise.then(
      (value) => {
        window.clearTimeout(timeout)
        resolve(value)
      },
      (error) => {
        window.clearTimeout(timeout)
        reject(error)
      },
    )
  })
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
