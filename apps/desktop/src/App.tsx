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
      const message = error instanceof Error ? error.message : "Failed to refresh recent projects."
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
      message: source === "picker" ? "Native folder selected. Ready to launch the sidecar run." : "Dropped folder captured. Ready to launch the sidecar run.",
    })
  })

  const handleDroppedPaths = useEffectEvent((paths: string[]) => {
    setIsDropTargetActive(false)
    const droppedPath = pickDroppedInputRoot(paths)
    if (!droppedPath) {
      setLoadError("Drop a single project folder. Dragging individual DWG files or multiple paths is not supported yet.")
      setLaunchImportStatus({
        tone: "warn",
        message: "Drop one project folder at a time so the desktop shell can pass a clean root to the Python sidecar.",
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
            message: "Release to stage this project folder as the next analysis input.",
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
        const message = error instanceof Error ? error.message : "Failed to subscribe to native drag-and-drop events."
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
      const message = error instanceof Error ? error.message : `Failed to load project ${projectId}.`
      setLoadError(message)
    }
  })

  const handleEvent = useEffectEvent((event: SidecarEvent) => {
    setProcessState((current) => {
      const nextLogs = [...current.logs, JSON.stringify(event)]
      const nextState: ProcessState = {
        ...current,
        logs: nextLogs.slice(-20),
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
        ].slice(0, 12)
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
      setLoadError("Project directory is required.")
      return
    }
    if (isLikelyProjectFilePath(normalizedInputRoot)) {
      setLoadError("Select the project folder instead of a single DWG/DXF sidecar file.")
      setLaunchImportStatus({
        tone: "warn",
        message: "This path looks like a file. Choose the project directory so scanning, sidecars and page ordering stay intact.",
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
      const message = error instanceof Error ? error.message : "Failed to analyze project."
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
        message: "Browser preview cannot open the native picker. Run the Tauri shell or type a path manually here.",
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
      const message = error instanceof Error ? error.message : "Failed to open the native directory picker."
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
        const message = error instanceof Error ? error.message : `Failed to render preview for ${selectedIssue.issue_id}.`
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
      const message = error instanceof Error ? error.message : `Failed to update issue ${selectedIssue.issue_id}.`
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

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <p className="eyebrow">DWG Audit Desktop</p>
          <h1>Cross-page verification cockpit</h1>
          <p className="lede">
            Local review client for project import, process monitoring, evidence-led issue triage and recent project recall.
          </p>
        </div>

        <section className="sidebar-section">
          <div className="section-heading">
            <h2>Recent Projects</h2>
            <button type="button" className="ghost-button" onClick={() => void refreshRecentProjects()}>
              Refresh
            </button>
          </div>
          <div className="recent-list">
            {recentProjects.map((project) => (
              <button
                type="button"
                key={project.run_id}
                className={`recent-card ${project.project_id === selectedProjectId ? "active" : ""}`}
                onClick={() => {
                  setSelectedProjectId(project.project_id)
                  void loadProjectResult(project.project_id)
                }}
              >
                <strong>{project.project_name}</strong>
                <span>{project.issue_count} issues</span>
                <span>{project.sheet_count} sheets</span>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Current Surface</p>
            <h2>{screen === "launch" ? "Launch" : screen === "process" ? "Run Monitor" : "Results Review"}</h2>
          </div>
          <div className="nav-strip">
            <button type="button" className={screen === "launch" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("launch")}>
              Launch
            </button>
            <button type="button" className={screen === "process" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("process")}>
              Process
            </button>
            <button type="button" className={screen === "result" ? "nav-chip active" : "nav-chip"} onClick={() => setScreen("result")}>
              Result
            </button>
          </div>
        </header>

        {loadError ? <div className="global-error">{loadError}</div> : null}

        {screen === "launch" && (
          <section className="launch-grid">
            <article className={`launch-card dropzone ${isDropTargetActive ? "dropzone-active" : ""}`}>
              <p className="eyebrow">Input</p>
              <h3>Import project directory</h3>
              <p>
                Pick a project folder natively or drop it onto this card. The shell will keep the project root explicit, then hand it to the existing Python sidecar pipeline unchanged.
              </p>
              <div className={`input-health ${inputHealth.tone}`}>
                <strong>{inputHealth.title}</strong>
                <span>{inputHealth.detail}</span>
              </div>
              {launchImportStatus ? <p className={`drop-status ${launchImportStatus.tone}`}>{launchImportStatus.message}</p> : null}
              <label className="field">
                <span>Project directory</span>
                <input
                  value={inputRoot}
                  onChange={(event) => {
                    setInputRoot(event.target.value)
                    setLaunchImportStatus(null)
                  }}
                  placeholder="Select a folder to analyze"
                />
              </label>
              {loadError ? <p className="error-note">{loadError}</p> : null}
              <div className="button-row">
                <button type="button" className="primary-button" disabled={!inputRoot.trim() || isAnalyzing} onClick={() => void handleAnalyzeClick()}>
                  {isAnalyzing ? "Analyzing..." : "Start analysis"}
                </button>
                <button type="button" className="ghost-button" disabled={isPickingDirectory || isAnalyzing} onClick={() => void handlePickDirectoryClick()}>
                  {isPickingDirectory ? "Opening picker..." : "Native folder picker"}
                </button>
              </div>
            </article>

            <article className="launch-card">
              <p className="eyebrow">Desktop-side conventions</p>
              <h3>What the shell already assumes</h3>
              <ul className="fact-list">
                <li>Temporary workspace is managed internally and not exposed as a required user choice.</li>
                <li>Recent project recall comes from SQLite-backed `list-recent-projects` results.</li>
                <li>Process view is driven by streamed sidecar events rather than polling parquet files directly.</li>
              </ul>
            </article>
          </section>
        )}

        {screen === "process" && (
          <section className="process-layout">
            <article className="panel progress-panel">
              <div className="section-heading">
                <h3>Run progress</h3>
                <span>{Math.round(processState.progressRatio * 100)}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${Math.round(processState.progressRatio * 100)}%` }} />
              </div>
              <div className="progress-meta">
                <div className="metric-inline">
                  <strong>{processState.totalSheets}</strong>
                  <span>Total sheets</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.completedPages}</strong>
                  <span>Pages handled</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.failedPages}</strong>
                  <span>Failed pages</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.warningCount}</strong>
                  <span>Warnings</span>
                </div>
                <div className="metric-inline">
                  <strong>{processState.liveIssues.length}</strong>
                  <span>Live issues</span>
                </div>
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

            <article className="panel">
              <div className="section-heading">
                <h3>Live issue table</h3>
                <span>{processState.liveIssues.length} visible</span>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Rule</th>
                    <th>Type</th>
                    <th>Title</th>
                    <th>Sheet</th>
                    <th>Pair</th>
                    <th>Status</th>
                    <th>Conf</th>
                  </tr>
                </thead>
                <tbody>
                  {processState.liveIssues.map((issue) => (
                    <tr key={issue.issue_id}>
                      <td>{issue.filename || "-"}</td>
                      <td>{issue.rule_id}</td>
                      <td>{issue.issue_type}</td>
                      <td>{issue.title}</td>
                      <td>{issue.sheet_no}</td>
                      <td>{formatPair(issue)}</td>
                      <td>{issue.status}</td>
                      <td>{issue.confidence.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>

            <article className="panel logs-panel">
              <div className="section-heading">
                <h3>Event stream</h3>
                <span>{processState.logs.length} lines</span>
              </div>
              <pre className="log-stream">{processState.logs.join("\n")}</pre>
            </article>
          </section>
        )}

        {screen === "result" && (
          <section className="result-layout">
            <article className="panel result-summary">
              <div className="section-heading">
                <h3>Result summary</h3>
                <span>{summaryProject?.project_name ?? "No project loaded"}</span>
              </div>
              {summaryProject && (
                <div className="metric-row">
                  <div className="metric-card">
                    <strong>{summaryProject.sheet_count}</strong>
                    <span>Sheets</span>
                  </div>
                  <div className="metric-card">
                    <strong>{summaryProject.pair_count}</strong>
                    <span>Pairs</span>
                  </div>
                  <div className="metric-card">
                    <strong>{summaryProject.issue_count}</strong>
                    <span>Issues</span>
                  </div>
                </div>
              )}
              <label className="field">
                <span>Filter issues</span>
                <input value={issueSearch} onChange={(event) => setIssueSearch(event.target.value)} placeholder="Search by rule, sheet or pair" />
              </label>
              <div className="filter-grid">
                <label className="field compact-field">
                  <span>Severity</span>
                  <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
                    <option value="all">All</option>
                    {issueFilterOptions.severities.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field compact-field">
                  <span>Rule</span>
                  <select value={ruleFilter} onChange={(event) => setRuleFilter(event.target.value)}>
                    <option value="all">All</option>
                    {issueFilterOptions.rules.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field compact-field">
                  <span>Status</span>
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                    <option value="all">All</option>
                    {issueFilterOptions.statuses.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field compact-field">
                  <span>1:N</span>
                  <select value={triageFilter} onChange={(event) => setTriageFilter(event.target.value)}>
                    <option value="all">All</option>
                    {issueFilterOptions.triages.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </article>

            <article className="panel issue-table-panel">
              <div className="section-heading">
                <h3>Issue board</h3>
                <span>{filteredIssues.length} rows</span>
              </div>
              <table className="data-table compact">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Type</th>
                    <th>Orient</th>
                    <th>1:N</th>
                    <th>Status</th>
                    <th>Rule</th>
                    <th>Title</th>
                    <th>Sheet</th>
                    <th>Pair</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredIssues.map((issue) => (
                    <tr
                      key={issue.issue_id}
                      className={issue.issue_id === selectedIssue?.issue_id ? "selected-row" : ""}
                      onClick={() => {
                        setSelectedIssueId(issue.issue_id)
                      }}
                    >
                      <td>{issue.severity}</td>
                      <td>{issue.issue_type}</td>
                      <td>{readLineOrientation(issue) ?? "-"}</td>
                      <td>{issue.one_to_many_classification ?? readOneToManyClassification(issue) ?? "-"}</td>
                      <td>{issue.status}</td>
                      <td>{issue.rule_id}</td>
                      <td>{issue.title}</td>
                      <td>{issue.sheet_no}</td>
                      <td>{formatPair(issue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>

            <article className="panel issue-detail-panel">
              <div className="section-heading">
                <h3>Issue detail</h3>
                <span>{selectedIssue?.issue_id ?? "None selected"}</span>
              </div>
              {selectedIssue ? (
                <div className="issue-detail">
                  <div className="detail-block">
                    <span>Title</span>
                    <strong>{selectedIssue.title}</strong>
                  </div>
                  <div className="detail-grid">
                    <div className="detail-block">
                      <span>Rule</span>
                      <strong>{selectedIssue.rule_id}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Issue type</span>
                      <strong>{selectedIssue.issue_type}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Line orientation</span>
                      <strong>{readLineOrientation(selectedIssue) ?? "-"}</strong>
                    </div>
                    <div className="detail-block">
                      <span>1:N triage</span>
                      <strong>{selectedIssue.one_to_many_classification ?? readOneToManyClassification(selectedIssue) ?? "-"}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Severity</span>
                      <strong>{selectedIssue.severity}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Status</span>
                      <strong>{selectedIssue.status}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Confidence</span>
                      <strong>{selectedIssue.confidence.toFixed(2)}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Sheet</span>
                      <strong>{selectedIssue.sheet_no}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Line group</span>
                      <strong>{selectedIssue.line_group_id ?? "-"}</strong>
                    </div>
                  </div>
                  <div className="detail-block">
                    <span>Line semantics</span>
                    <strong>{formatLineSemantics(selectedIssue) || "-"}</strong>
                  </div>
                  <div className="detail-block">
                    <span>Summary</span>
                    <strong>{selectedIssue.summary || selectedIssue.title}</strong>
                  </div>
                  <div className="detail-grid">
                    <div className="detail-block">
                      <span>Explanation</span>
                      <strong>{selectedIssue.explanation || "-"}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Recommended action</span>
                      <strong>{selectedIssue.recommended_action || "-"}</strong>
                    </div>
                  </div>
                  <div className="detail-block">
                    <span>Confidence breakdown</span>
                    <div className="metric-row">
                      {Object.entries(readScoreBreakdown(selectedIssue.evidence)).map(([key, value]) => (
                        <div key={key} className="metric-card compact-metric">
                          <strong>{formatBreakdownValue(value)}</strong>
                          <span>{key}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="detail-block">
                    <span>Evidence chain</span>
                    <pre>{JSON.stringify(readEvidenceChain(selectedIssue), null, 2)}</pre>
                  </div>
                  <div className="detail-block">
                    <span>Raw evidence</span>
                    <pre>{JSON.stringify(selectedIssue.evidence, null, 2)}</pre>
                  </div>
                  <div className="detail-grid">
                    <div className="detail-block">
                      <span>Related pairs</span>
                      <strong>{selectedIssue.related_pair_ids.length ? selectedIssue.related_pair_ids.join(", ") : "-"}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Related sheets</span>
                      <strong>{selectedIssue.sheet_ids.length ? selectedIssue.sheet_ids.join(", ") : "-"}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Observed values</span>
                      <strong>{selectedIssue.values.length ? selectedIssue.values.join(", ") : "-"}</strong>
                    </div>
                    <div className="detail-block">
                      <span>Primary pair</span>
                      <strong>{selectedIssue.primary_pair_id ?? "-"}</strong>
                    </div>
                  </div>
                  <div className="detail-block">
                    <span>Evidence refs</span>
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
                    <label className="field compact-field">
                      <span>Preview source</span>
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
                          <option value="">No related sheet references</option>
                        )}
                      </select>
                    </label>
                    <div className="detail-block">
                      <span>Active preview</span>
                      <strong>{activePreviewOption?.caption ?? selectedIssue.sheet_id ?? "-"}</strong>
                    </div>
                  </div>
                  <div className="detail-grid">
                    <div className="detail-block">
                      <span>Preview controls</span>
                      <div className="button-row">
                        <button type="button" className="ghost-button" disabled={!selectedIssue || isRefreshingPreview} onClick={() => handlePreviewRegenerateClick()}>
                          {isRefreshingPreview ? "Rendering..." : "Regenerate preview"}
                        </button>
                      </div>
                    </div>
                    <div className="detail-block">
                      <span>Preview state</span>
                      <strong>
                        {isRefreshingPreview
                          ? "Rendering current preview source"
                          : activePreviewOption
                            ? `Ready: ${activePreviewOption.caption}`
                            : "Waiting for selectable preview source"}
                      </strong>
                    </div>
                  </div>
                  <div className="detail-block">
                    <span>Review status</span>
                    <div className="status-editor">
                      <select value={issueStatusDraft} onChange={(event) => setIssueStatusDraft(event.target.value)}>
                        {ISSUE_STATUS_OPTIONS.map((status) => (
                          <option key={status} value={status}>
                            {status}
                          </option>
                        ))}
                      </select>
                      <button type="button" className="ghost-button" disabled={isSavingIssueStatus} onClick={() => void handleIssueStatusSave()}>
                        {isSavingIssueStatus ? "Saving..." : "Save status"}
                      </button>
                    </div>
                  </div>
                  <div className="preview-shell">
                    {previewSrc ? (
                      <img src={previewSrc} alt="Issue preview" className="preview-image" />
                    ) : (
                      <div className="preview-empty">
                        {previewOptions.length
                          ? "Preview is being rendered for the selected sheet reference."
                          : "Preview will be supplied by render-preview."}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <p className="empty-state">Select an issue to inspect its confidence breakdown and preview overlay.</p>
              )}
            </article>
          </section>
        )}
      </main>
    </div>
  )
}

function defaultStageCards(): RunStageCard[] {
  return [
    { stage: "scan", label: "Scan", detail: "Project discovery", done: false },
    { stage: "convert", label: "Convert", detail: "DWG -> DXF", done: false },
    { stage: "extract", label: "Extract", detail: "CAD entities + layout", done: false },
    { stage: "pair", label: "Pair", detail: "Candidates + pass/review/discard", done: false },
    { stage: "audit", label: "Audit", detail: "Rules + issue clustering", done: false },
    { stage: "render", label: "Render", detail: "Preview + evidence surfaces", done: false },
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

function summarizeProgress(event: SidecarEvent): string {
  if (event.event !== "progress") {
    return ""
  }
  if (event.stage === "scan") {
    return `${event.file_count ?? 0} files / ${event.sheet_count ?? 0} sheets`
  }
  if (event.stage === "convert") {
    return `${event.file_count ?? 0} converted candidates`
  }
  if (event.stage === "extract") {
    return `${event.text_count ?? 0} texts, ${event.line_count ?? 0} lines`
  }
  if (event.stage === "pair") {
    return `${event.pair_count ?? 0} pairs, ${event.line_group_count ?? 0} groups`
  }
  if (event.stage === "audit") {
    return `${event.issue_count ?? 0} issues`
  }
  return "Preview generation"
}

function formatPair(issue: Pick<IssueSummary, "left_value" | "right_value">): string {
  return `${issue.left_value ?? "?"} -> ${issue.right_value ?? "?"}`
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
  return { confidence: Number(evidence.confidence ?? 0) }
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
    parts.push(`orientation=${orientation}`)
  }
  if (leftSide) {
    parts.push(`left_side=${leftSide}`)
  }
  if (rightSide) {
    parts.push(`right_side=${rightSide}`)
  }
  return parts.join(", ")
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
      title: "Project path required",
      detail: "Use the native picker, drag a folder onto this card, or paste a local project directory before starting the sidecar run.",
      tone: "warn",
    }
  }
  if (/^[a-zA-Z]:\\/.test(value) || value.startsWith("\\\\")) {
    if (isLikelyProjectFilePath(value)) {
      return {
        title: "Folder expected",
        detail: "This looks like a file path. Switch to the project directory so scanning, sidecars and recent-project recall stay aligned.",
        tone: "warn",
      }
    }
    return {
      title: "Input looks ready",
      detail: "Absolute Windows path detected. The shell can pass this directly to the Python sidecar.",
      tone: "ready",
    }
  }
  return {
    title: "Manual verification suggested",
    detail: "This is not an absolute Windows path yet. Use the picker or drop a folder to avoid mistyping the project root.",
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
      bits.push(`sheet ${meta.sheetNo}`)
      captionBits.push(`sheet ${meta.sheetNo}`)
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

  addOption(issue.sheet_id, "Issue sheet", {
    sheetNo: issue.sheet_no || null,
    filename: issue.filename || null,
  })

  for (const ref of issue.evidence_refs) {
    const record = isRecord(ref) ? ref : null
    addOption(readString(record?.sheet_id), "Evidence ref", {
      sheetNo: readString(record?.sheet_no),
      filename: readString(record?.filename),
    })
  }

  for (const relatedSheetId of issue.sheet_ids) {
    addOption(relatedSheetId, "Related sheet")
  }

  if (!options.size && issue.sheet_id) {
    addOption(issue.sheet_id, "Issue sheet")
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

    const titleBits = [`Ref ${index + 1}`]
    if (sheetNo) {
      titleBits.push(`sheet ${sheetNo}`)
    } else if (sheetId) {
      titleBits.push(sheetId)
    }

    const subtitleBits = [filename, pairId, lineGroupId, coord].filter((value): value is string => Boolean(value))

    return {
      key: `${sheetId ?? "no-sheet"}:${pairId ?? lineGroupId ?? index}`,
      sheetId,
      lineGroupId,
      title: titleBits.join(" · "),
      subtitle: subtitleBits.join(" · ") || "No extra reference detail",
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
  return `coord (${x.toFixed(1)}, ${y.toFixed(1)})`
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

export default App
