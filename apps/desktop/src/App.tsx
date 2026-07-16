import { isTauri } from "@tauri-apps/api/core"
import { getCurrentWindow } from "@tauri-apps/api/window"
import { startTransition, useDeferredValue, useEffect, useEffectEvent, useMemo, useState } from "react"

import "./App.css"
import { desktopApi } from "./lib/desktopApi"
import type { IssueSummary, ProjectResult, RecentProject, RunStageCard, SidecarEvent } from "./types"

type Screen = "launch" | "process" | "result"

const ISSUE_STATUS_OPTIONS = ["open", "ignored", "resolved", "false_positive"] as const

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
  const [issueStatusDraft, setIssueStatusDraft] = useState("open")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isPickingDirectory, setIsPickingDirectory] = useState(false)
  const [isRefreshingPreview, setIsRefreshingPreview] = useState(false)
  const [isSavingIssueStatus, setIsSavingIssueStatus] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isDropTargetActive, setIsDropTargetActive] = useState(false)
  const [launchImportStatus, setLaunchImportStatus] = useState<LaunchImportStatus | null>(null)
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
      const loaded = await desktopApi.loadResult(projectId)
      setResult(loaded)
      const initialIssue = loaded.issues[0] ?? null
      setSelectedIssueId(initialIssue?.issue_id ?? null)
      setSelectedPreviewSheetId(initialIssue?.sheet_id ?? null)
      setSelectedPreviewLineGroupId(initialIssue?.line_group_id ?? null)
      setPreviewSrc(null)
      startTransition(() => setScreen("result"))
    } catch (error) {
      const message = error instanceof Error ? error.message : `加载项目 ${projectId} 失败。`
      setLoadError(message)
    }
  })

  const handleEvent = useEffectEvent((event: SidecarEvent) => {
    setProcessState((current) => {
      const nextLogs = [...current.logs, formatSidecarLog(event)]
      const nextState: ProcessState = {
        ...current,
        logs: nextLogs.slice(-40),
      }

      if (event.event === "run_started") {
        nextState.sessionId = event.session_id
      }

      if (event.event === "progress") {
        nextState.activeStage = event.stage
        nextState.progressRatio = stageProgress(event.stage)
        if (event.stage === "scan") {
          nextState.totalSheets = event.sheet_count ?? current.totalSheets
        }
        nextState.stageCards = current.stageCards.map((item) =>
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
        nextState.completedPages = current.completedPages + 1
        nextState.failedPages = current.failedPages + (isFailedPageStatus(event.status) ? 1 : 0)
      }

      if (event.event === "warning") {
        nextState.warningCount = current.warningCount + 1
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
            evidence: {},
          },
          ...current.liveIssues,
        ].slice(0, 50)
      }

      if (event.event === "project_stored") {
        nextState.completedProjects = [
          {
            run_id: event.run_id,
            session_id: current.sessionId ?? "session-runtime",
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
        nextState.stageCards = current.stageCards.map((item) => ({ ...item, done: true }))
        nextState.completedProjects = event.projects
      }

      return nextState
    })
  })

  async function handleAnalyzeClick() {
    const normalizedInputRoot = inputRoot.trim()
    if (!normalizedInputRoot) {
      setLoadError("请先选择项目目录。")
      return
    }
    if (isLikelyProjectFilePath(normalizedInputRoot)) {
      setLoadError("请选择项目文件夹，而不是单个 DWG/DXF 文件。")
      setLaunchImportStatus({
        tone: "warn",
        message: "当前路径看起来像文件。请改为项目目录，以保证扫描与页序正确。",
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
      await refreshRecentProjects()
      if (payload.projects[0]) {
        setSelectedProjectId(payload.projects[0].project_id)
        await loadProjectResult(payload.projects[0].project_id)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "项目审计失败。"
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
        message: "浏览器预览无法打开系统目录对话框，请在桌面客户端中选择，或手动输入路径。",
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

  const filteredIssues = useMemo(() => {
    const issues = result?.issues ?? []
    const needle = deferredIssueSearch.trim().toLowerCase()
    return issues.filter((issue) => {
      if (severityFilter !== "all" && issue.severity !== severityFilter) {
        return false
      }
      if (ruleFilter !== "all" && issue.rule_id !== ruleFilter) {
        return false
      }
      if (statusFilter !== "all" && issue.status !== statusFilter) {
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
        issue.issue_id,
        issue.rule_id,
        issue.issue_type,
        issue.title,
        issue.summary,
        issue.explanation,
        issue.recommended_action,
        issue.filename,
        issue.sheet_no,
        issue.left_value ?? "",
        issue.right_value ?? "",
        triage ?? "",
        readLineOrientation(issue) ?? "",
        formatLineSemantics(issue),
        issue.values.join(" "),
        issue.related_pair_ids.join(" "),
        issue.sheet_ids.join(" "),
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    })
  }, [deferredIssueSearch, result?.issues, ruleFilter, severityFilter, statusFilter, triageFilter])

  const issueFilterOptions = useMemo(() => {
    const issues = result?.issues ?? []
    return {
      severities: Array.from(new Set(issues.map((issue) => issue.severity))).sort(),
      rules: Array.from(new Set(issues.map((issue) => issue.rule_id))).sort(),
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
      return
    }
    if (!projectId || !selectedIssue) {
      setPreviewSrc(null)
      setIsRefreshingPreview(false)
      return
    }

    let cancelled = false
    setIsRefreshingPreview(true)

    void desktopApi
      .renderPreview(projectId, selectedIssue.issue_id, selectedPreviewSheetId, selectedPreviewLineGroupId)
      .then((preview) => {
        if (cancelled) {
          return
        }
        setPreviewSrc(preview.preview_src)
        setLoadError(null)
        setIsRefreshingPreview(false)
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        const message = error instanceof Error ? error.message : `生成问题 ${selectedIssue.issue_id} 的预览失败。`
        setLoadError(message)
        setPreviewSrc(null)
        setIsRefreshingPreview(false)
      })

    return () => {
      cancelled = true
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
      const message = error instanceof Error ? error.message : `更新问题 ${selectedIssue.issue_id} 状态失败。`
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

  const screenTitle = screen === "launch" ? "启动" : screen === "process" ? "过程" : "结果"
  const isNativeRuntime = desktopApi.isNative()
  const sessionLabel = isAnalyzing
    ? `运行中 ${Math.round(processState.progressRatio * 100)}%`
    : summaryProject?.project_name ?? "未加载项目"

  return (
    <div className="shell">
      <header className="topbar">
        <div className="product-mark">
          <strong>图纸跨页审计</strong>
          <span>本地离线校验</span>
        </div>
        <nav className="nav-strip" aria-label="主视图">
          <button type="button" className={screen === "launch" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("launch")}>
            启动
          </button>
          <button type="button" className={screen === "process" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("process")}>
            过程
          </button>
          <button type="button" className={screen === "result" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("result")}>
            结果
          </button>
        </nav>
        <div className="session-meta">
          <span className={`engine-pill ${isNativeRuntime ? "native" : "mock"}`}>
            {isNativeRuntime ? "引擎：本地 sidecar" : "引擎：浏览器 mock"}
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
                  <h3>导入项目</h3>
                  <span>{isNativeRuntime ? "输出目录由本机管理" : "当前为浏览器预览，数据为 mock"}</span>
                </div>
              </div>
              <div className="launch-import-body panel-pad" style={{ paddingTop: 0 }}>
                <div className={`dropzone ${isDropTargetActive ? "dropzone-active" : ""}`}>
                  <h3>项目目录</h3>
                  <p>拖入文件夹，或点“选择目录”。正式审计须在桌面客户端调用本地引擎。</p>
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
                  <span>项目目录</span>
                  <input
                    value={inputRoot}
                    onChange={(event) => {
                      setInputRoot(event.target.value)
                      setLaunchImportStatus(null)
                    }}
                    placeholder="项目根目录路径"
                  />
                </label>
                <div className="button-row">
                  <button type="button" className="primary-button" disabled={!inputRoot.trim() || isAnalyzing} onClick={() => void handleAnalyzeClick()}>
                    {isAnalyzing ? "运行中…" : "开始校验"}
                  </button>
                  <button type="button" className="ghost-button" disabled={isPickingDirectory || isAnalyzing} onClick={() => void handlePickDirectoryClick()}>
                    {isPickingDirectory ? "打开中…" : "选择目录"}
                  </button>
                </div>
                {!isNativeRuntime ? (
                  <div className="drop-status warn">
                    <strong>未连接本地引擎</strong>
                    <span>浏览器仅可预览界面与 mock 数据。请用 `npm run tauri:dev` 或安装包启动，以接入 Python sidecar。</span>
                  </div>
                ) : null}
              </div>
            </article>

            <article className="panel launch-recent">
              <div className="panel-pad">
                <div className="section-heading">
                  <h3>最近项目</h3>
                  <button type="button" className="ghost-button" onClick={() => void refreshRecentProjects()}>
                    刷新
                  </button>
                </div>
              </div>
              <div className="table-wrap">
                <table className="data-table compact">
                  <thead>
                    <tr>
                      <th>项目名称</th>
                      <th>最近校验时间</th>
                      <th>图纸页数</th>
                      <th>问题数</th>
                      <th>状态</th>
                      <th>路径</th>
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
                          <td>{project.project_name}</td>
                          <td>{formatAuditTime(project.updated_at)}</td>
                          <td>{project.sheet_count}</td>
                          <td>{project.issue_count}</td>
                          <td>
                            <span className={`chip status-${normalizeToken(project.status)}`}>{labelProjectStatus(project.status)}</span>
                          </td>
                          <td className="path-cell" title={project.input_root}>
                            {project.input_root}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={6}>
                          <div className="empty-state">暂无最近项目。完成一次审计后将显示在此列表。</div>
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
                  <h3>阶段</h3>
                  <span>当前 {labelStage(processState.activeStage)}</span>
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
                  <h3>进度</h3>
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
                  <span>已处理页</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.failedPages}</strong>
                  <span>失败页</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.warningCount}</strong>
                  <span>警告</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.liveIssues.length}</strong>
                  <span>实时问题</span>
                </div>
              </div>
            </article>

            <article className="panel process-live-issues">
              <div className="panel-pad" style={{ paddingBottom: 0 }}>
                <div className="section-heading">
                  <h3>实时问题</h3>
                  <span>{processState.liveIssues.length}</span>
                </div>
              </div>
              <div className="table-wrap">
                <table className="data-table compact">
                  <thead>
                    <tr>
                      <th>文件</th>
                      <th>规则</th>
                      <th>类型</th>
                      <th>标题</th>
                      <th>图号</th>
                      <th>配对</th>
                      <th>状态</th>
                      <th>置信度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {processState.liveIssues.length ? (
                      processState.liveIssues.map((issue) => (
                        <tr key={issue.issue_id}>
                          <td>{issue.filename || "-"}</td>
                          <td>{issue.rule_id}</td>
                          <td>{issue.issue_type}</td>
                          <td>{issue.title}</td>
                          <td>{issue.sheet_no || "-"}</td>
                          <td>{formatPair(issue)}</td>
                          <td>
                            <span className={`chip status-${normalizeToken(issue.status)}`}>{labelIssueStatus(issue.status)}</span>
                          </td>
                          <td>{issue.confidence.toFixed(2)}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={8}>
                          <div className="empty-state">审计开始后将在此实时列出发现问题。</div>
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
                  <h3>日志</h3>
                  <span>{processState.logs.length}</span>
                </div>
              </div>
              <pre className="log-stream">{processState.logs.length ? processState.logs.join("\n") : "等待引擎事件…"}</pre>
            </article>
          </section>
        )}

        {screen === "result" && (
          <section className="result-layout">
            <article className="panel result-toolbar">
              <div className="result-toolbar-metrics">
                <div className="metric-card">
                  <strong>{summaryProject?.sheet_count ?? 0}</strong>
                  <span>图纸</span>
                </div>
                <div className="metric-card">
                  <strong>{summaryProject?.pair_count ?? 0}</strong>
                  <span>配对</span>
                </div>
                <div className="metric-card">
                  <strong>{summaryProject?.issue_count ?? filteredIssues.length}</strong>
                  <span>问题</span>
                </div>
                <div className="metric-card">
                  <strong>{filteredIssues.length}</strong>
                  <span>筛选后</span>
                </div>
                <span className="muted" title={summaryProject?.project_name ?? undefined}>
                  {summaryProject?.project_name ?? "未加载项目"}
                </span>
              </div>
              <div className="result-toolbar-filters">
                <label className="field compact-field">
                  <span>筛选问题</span>
                  <input value={issueSearch} onChange={(event) => setIssueSearch(event.target.value)} placeholder="规则 / 图号 / 端子" />
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
                  <span>规则</span>
                  <select value={ruleFilter} onChange={(event) => setRuleFilter(event.target.value)}>
                    <option value="all">全部</option>
                    {issueFilterOptions.rules.map((value) => (
                      <option key={value} value={value}>
                        {value}
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
                  <span>一对多</span>
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
                  <span>{filteredIssues.length}</span>
                </div>
              </div>
              <div className="table-wrap">
                <table className="data-table compact">
                  <thead>
                    <tr>
                      <th>严重程度</th>
                      <th>类型</th>
                      <th>线向</th>
                      <th>一对多</th>
                      <th>状态</th>
                      <th>置信度</th>
                      <th>规则</th>
                      <th>标题</th>
                      <th>图号</th>
                      <th>配对</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredIssues.length ? (
                      filteredIssues.map((issue) => {
                        const triage = issue.one_to_many_classification ?? readOneToManyClassification(issue)
                        return (
                          <tr
                            key={issue.issue_id}
                            className={issue.issue_id === selectedIssue?.issue_id ? "selected-row" : ""}
                            onClick={() => {
                              setSelectedIssueId(issue.issue_id)
                            }}
                          >
                            <td>
                              <span className={`badge severity-${normalizeToken(issue.severity)}`}>{labelSeverity(issue.severity)}</span>
                            </td>
                            <td>{issue.issue_type}</td>
                            <td>{readLineOrientation(issue) ?? "-"}</td>
                            <td>
                              <span className={`chip triage-${normalizeToken(triage ?? "none")}`}>{labelTriage(triage)}</span>
                            </td>
                            <td>
                              <span className={`chip status-${normalizeToken(issue.status)}`}>{labelIssueStatus(issue.status)}</span>
                            </td>
                            <td>{issue.confidence.toFixed(2)}</td>
                            <td>{issue.rule_id}</td>
                            <td>{issue.title}</td>
                            <td>{issue.sheet_no || "-"}</td>
                            <td>{formatPair(issue)}</td>
                          </tr>
                        )
                      })
                    ) : (
                      <tr>
                        <td colSpan={10}>
                          <div className="empty-state">{result ? "当前筛选条件下无问题。" : "请先从启动页导入项目或打开最近项目。"}</div>
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
                  <span title={selectedIssue?.issue_id ?? undefined}>{selectedIssue?.issue_id ?? "未选择"}</span>
                </div>
                {selectedIssue ? (
                  <div className="inspector-badges">
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
                      <span>复核状态</span>
                      <select value={issueStatusDraft} onChange={(event) => setIssueStatusDraft(event.target.value)}>
                        {ISSUE_STATUS_OPTIONS.map((status) => (
                          <option key={status} value={status}>
                            {labelIssueStatus(status)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button type="button" className="ghost-button" disabled={isSavingIssueStatus} onClick={() => void handleIssueStatusSave()}>
                      {isSavingIssueStatus ? "保存中…" : "保存状态"}
                    </button>
                    <label className="field compact-field" style={{ minWidth: 160 }}>
                      <span>预览来源</span>
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
                          <option value="">无关联图纸引用</option>
                        )}
                      </select>
                    </label>
                    <button type="button" className="ghost-button" disabled={!selectedIssue || isRefreshingPreview} onClick={() => handlePreviewRegenerateClick()}>
                        {isRefreshingPreview ? "渲染中…" : "重生成预览"}
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="panel inspector-preview">
                <div className="preview-shell">
                  {previewSrc ? (
                    <img src={previewSrc} alt="问题定位预览" className="preview-image" />
                  ) : (
                    <div className={`preview-empty${selectedIssue && isRefreshingPreview ? " is-loading" : ""}`}>
                      {selectedIssue
                        ? isRefreshingPreview
                          ? "正在渲染当前页预览…"
                          : previewOptions.length
                            ? "若源图可访问，将在此显示定位预览；否则请依赖下方文字证据。"
                            : "当前问题无可用预览引用，请查看文字证据。"
                        : "请从左侧选择问题进行复核。"}
                    </div>
                  )}
                </div>
              </div>

              <div className="panel inspector-detail">
                {selectedIssue ? (
                  <div className="issue-detail">
                    <div className="detail-block detail-title">
                      <span>标题</span>
                      <strong>{selectedIssue.title}</strong>
                    </div>
                    <div className="detail-grid">
                      <div className="detail-block">
                        <span>规则</span>
                        <strong>{selectedIssue.rule_id}</strong>
                      </div>
                      <div className="detail-block">
                        <span>问题类型</span>
                        <strong>{selectedIssue.issue_type}</strong>
                      </div>
                      <div className="detail-block">
                        <span>文件名</span>
                        <strong>{selectedIssue.filename || "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>图号 / 页</span>
                        <strong>{selectedIssue.sheet_no || selectedIssue.sheet_id || "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>线组 ID</span>
                        <strong>{selectedIssue.line_group_id ?? structuredLocation.lineGroupId ?? "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>坐标</span>
                        <strong className="coords-mono">{structuredLocation.coords || "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>关联数字</span>
                        <strong>{selectedIssue.values.length ? selectedIssue.values.join(", ") : formatPair(selectedIssue)}</strong>
                      </div>
                      <div className="detail-block">
                        <span>置信度（识别把握，非业务严重程度）</span>
                        <strong>{selectedIssue.confidence.toFixed(2)}</strong>
                      </div>
                      <div className="detail-block">
                        <span>线向</span>
                        <strong>{readLineOrientation(selectedIssue) ?? "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>一对多判定</span>
                        <strong>{labelTriage(selectedIssue.one_to_many_classification ?? readOneToManyClassification(selectedIssue))}</strong>
                      </div>
                    </div>
                    <div className="detail-block">
                      <span>线语义</span>
                      <strong>{formatLineSemantics(selectedIssue) || "-"}</strong>
                    </div>
                    <div className="detail-block">
                      <span>摘要</span>
                      <strong>{selectedIssue.summary || selectedIssue.title}</strong>
                    </div>
                    <div className="detail-grid">
                      <div className="detail-block">
                        <span>说明</span>
                        <strong>{selectedIssue.explanation || "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>建议处理</span>
                        <strong>{selectedIssue.recommended_action || "-"}</strong>
                      </div>
                    </div>
                    <div className="detail-block">
                      <span>置信度拆解</span>
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
                        <strong className="muted">无拆解字段，仅显示问题总置信度。</strong>
                      )}
                    </div>
                    <div className="detail-block">
                      <span>证据引用</span>
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
                        <strong>-</strong>
                      )}
                    </div>
                    <div className="detail-grid">
                      <div className="detail-block">
                        <span>关联配对</span>
                        <strong>{selectedIssue.related_pair_ids.length ? selectedIssue.related_pair_ids.join(", ") : "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>关联图纸</span>
                        <strong>{selectedIssue.sheet_ids.length ? selectedIssue.sheet_ids.join(", ") : "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>主配对</span>
                        <strong>{selectedIssue.primary_pair_id ?? "-"}</strong>
                      </div>
                      <div className="detail-block">
                        <span>当前预览</span>
                        <strong>
                          {isRefreshingPreview
                            ? "正在渲染…"
                            : activePreviewOption
                              ? activePreviewOption.caption
                              : selectedIssue.sheet_id ?? "-"}
                        </strong>
                      </div>
                    </div>
                    <details className="raw-toggle">
                      <summary>高级：证据链 / 原始证据</summary>
                      <div className="detail-block" style={{ marginTop: 8 }}>
                        <span>证据链</span>
                        <pre>{JSON.stringify(readEvidenceChain(selectedIssue), null, 2)}</pre>
                      </div>
                      <div className="detail-block" style={{ marginTop: 8 }}>
                        <span>原始证据</span>
                        <pre>{JSON.stringify(selectedIssue.evidence, null, 2)}</pre>
                      </div>
                    </details>
                  </div>
                ) : (
                  <p className="empty-state">请从左侧选择问题，查看定位预览、置信度拆解与证据。</p>
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
    { stage: "scan", label: "扫描", detail: "发现项目与图纸", done: false },
    { stage: "convert", label: "转换", detail: "DWG → DXF", done: false },
    { stage: "extract", label: "抽取", detail: "实体与版面抽取", done: false },
    { stage: "pair", label: "配对", detail: "候选与配对", done: false },
    { stage: "audit", label: "审计", detail: "规则与问题聚类", done: false },
    { stage: "render", label: "预览", detail: "预览与证据", done: false },
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
    scan: "扫描",
    convert: "转换",
    extract: "抽取",
    pair: "配对",
    audit: "审计",
    render: "预览",
  }
  return map[stage] ?? stage
}

function summarizeProgress(event: SidecarEvent): string {
  if (event.event !== "progress") {
    return ""
  }
  if (event.stage === "scan") {
    return `${event.file_count ?? 0} 文件 / ${event.sheet_count ?? 0} 图纸`
  }
  if (event.stage === "convert") {
    return `${event.file_count ?? 0} 个转换候选`
  }
  if (event.stage === "extract") {
    return `${event.text_count ?? 0} 文本，${event.line_count ?? 0} 线段`
  }
  if (event.stage === "pair") {
    return `${event.pair_count ?? 0} 配对，${event.line_group_count ?? 0} 线组`
  }
  if (event.stage === "audit") {
    return `${event.issue_count ?? 0} 个问题`
  }
  return "生成预览"
}

function formatSidecarLog(event: SidecarEvent): string {
  const stamp = new Date().toLocaleTimeString("zh-CN", { hour12: false })
  switch (event.event) {
    case "run_started":
      return `[${stamp}] 任务开始 · session=${event.session_id}`
    case "project_started":
      return `[${stamp}] 项目开始 · ${event.project_root}`
    case "project_artifacts_ready":
      return `[${stamp}] 工件就绪 · ${event.project_dir}`
    case "progress":
      return `[${stamp}] 进度 · ${labelStage(event.stage)} · ${summarizeProgress(event)}`
    case "page_started":
      return `[${stamp}] 页开始 · ${event.filename} · ${labelStage(event.stage)}`
    case "page_finished":
      return `[${stamp}] 页完成 · ${event.filename} · ${event.status}`
    case "warning":
      return `[${stamp}] 警告 · ${event.filename ?? "-"} · ${event.message}`
    case "issue_found":
      return `[${stamp}] 发现问题 · ${event.severity} · ${event.rule_id} · ${event.title}`
    case "audit_finished":
      return `[${stamp}] 审计完成 · ${event.issue_count} 个问题`
    case "project_stored":
      return `[${stamp}] 结果已入库 · ${event.project_name} · ${event.issue_count} 问题`
    case "run_finished":
      return `[${stamp}] 任务结束 · ${event.project_count} 个项目`
    default:
      return `[${stamp}] ${JSON.stringify(event)}`
  }
}

function formatPair(issue: Pick<IssueSummary, "left_value" | "right_value">): string {
  return `${issue.left_value ?? "?"} → ${issue.right_value ?? "?"}`
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
  const orientation = typeof evidence.line_orientation === "string" && evidence.line_orientation.trim() ? evidence.line_orientation : null
  const leftSide = typeof evidence.left_side_label === "string" && evidence.left_side_label.trim() ? evidence.left_side_label : null
  const rightSide = typeof evidence.right_side_label === "string" && evidence.right_side_label.trim() ? evidence.right_side_label : null

  if (orientation) {
    parts.push(`线向=${orientation}`)
  }
  if (leftSide) {
    parts.push(`左=${leftSide}`)
  }
  if (rightSide) {
    parts.push(`右=${rightSide}`)
  }
  return parts.join("，")
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
  }
  return map[key] ?? key
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
      detail: "选择或拖入项目根目录后再开始。",
      tone: "warn",
    }
  }
  if (/^[a-zA-Z]:\\/.test(value) || value.startsWith("\\\\")) {
    if (isLikelyProjectFilePath(value)) {
      return {
        title: "路径像文件",
        detail: "应指向项目文件夹，而不是单个 DWG。",
        tone: "warn",
      }
    }
    return {
      title: "路径可用",
      detail: "Windows 绝对路径，可交给本地引擎。",
      tone: "ready",
    }
  }
  return {
    title: "路径需确认",
    detail: "非绝对路径。建议用目录选择器，避免输错。",
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
    },
  ) => {
    const normalized = sheetId?.trim()
    if (!normalized || options.has(normalized)) {
      return
    }

    const bits = [prefix]
    const captionBits = []
    if (meta?.sheetNo) {
      bits.push(`图 ${meta.sheetNo}`)
      captionBits.push(`图 ${meta.sheetNo}`)
    }
    if (meta?.filename) {
      bits.push(meta.filename)
      captionBits.push(meta.filename)
    }
    if (!captionBits.length) {
      captionBits.push(normalized)
    }

    options.set(normalized, {
      sheetId: normalized,
      label: bits.join(" · "),
      caption: captionBits.join(" · "),
    })
  }

  addOption(issue.sheet_id, "问题所在页", {
    sheetNo: issue.sheet_no || null,
    filename: issue.filename || null,
  })

  for (const ref of issue.evidence_refs) {
    const record = isRecord(ref) ? ref : null
    addOption(readString(record?.sheet_id), "证据引用", {
      sheetNo: readString(record?.sheet_no),
      filename: readString(record?.filename),
    })
  }

  for (const relatedSheetId of issue.sheet_ids) {
    addOption(relatedSheetId, "关联页")
  }

  if (!options.size && issue.sheet_id) {
    addOption(issue.sheet_id, "问题所在页")
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
    const pairId = readString(record?.pair_id)
    const lineGroupId = readString(record?.line_group_id)
    const coord = formatEvidenceCoord(record?.coord)

    const titleBits = [`引用 ${index + 1}`]
    if (sheetNo) {
      titleBits.push(`图 ${sheetNo}`)
    } else if (sheetId) {
      titleBits.push(sheetId)
    }

    const subtitleBits = [filename, pairId, lineGroupId, coord].filter((value): value is string => Boolean(value))

    return {
      key: `${sheetId ?? "no-sheet"}:${pairId ?? lineGroupId ?? index}`,
      sheetId,
      lineGroupId,
      title: titleBits.join(" · "),
      subtitle: subtitleBits.join(" · ") || "无附加引用详情",
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
  return `坐标 (${x.toFixed(1)}, ${y.toFixed(1)})`
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
    review: "复核",
    low: "低",
    info: "信息",
    minor: "次要",
  }
  return map[value.toLowerCase()] ?? value
}

function labelIssueStatus(value: string): string {
  const map: Record<string, string> = {
    open: "待处理",
    ignored: "已忽略",
    resolved: "已处理",
    false_positive: "误报",
  }
  return map[value] ?? value
}

function labelTriage(value: string | null | undefined): string {
  if (!value) {
    return "无"
  }
  const map: Record<string, string> = {
    branch: "分支",
    review: "待复核",
    conflict: "冲突",
  }
  return map[value.toLowerCase()] ?? value
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
