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

function App() {
  const [screen, setScreen] = useState<Screen>("launch")
  const [inputRoot, setInputRoot] = useState("F:\\workspace\\XJToolkit\\test\\110kV变压器保护柜")
  const [recentProjects, setRecentProjects] = useState<RecentProject[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)
  const [result, setResult] = useState<ProjectResult | null>(null)
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null)
  const [previewSrc, setPreviewSrc] = useState<string | null>(null)
  const [issueSearch, setIssueSearch] = useState("")
  const [issueStatusDraft, setIssueStatusDraft] = useState("open")
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isSavingIssueStatus, setIsSavingIssueStatus] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
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
    const projects = await desktopApi.listRecentProjects()
    setRecentProjects(projects)
    if (!selectedProjectId && projects[0]) {
      setSelectedProjectId(projects[0].project_id)
    }
  })

  useEffect(() => {
    void refreshRecentProjects()
  }, [refreshRecentProjects])

  const loadProjectResult = useEffectEvent(async (projectId: string) => {
    setLoadError(null)
    const loaded = await desktopApi.loadResult(projectId)
    setResult(loaded)
    const initialIssue = loaded.issues[0] ?? null
    setSelectedIssueId(initialIssue?.issue_id ?? null)
    const preview = await desktopApi.renderPreview(projectId, initialIssue?.issue_id ?? null)
    setPreviewSrc(preview.preview_src)
    startTransition(() => setScreen("result"))
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
            title: event.title,
            severity: event.severity,
            status: "open",
            confidence: event.confidence ?? 0,
            filename: event.filename ?? "",
            sheet_no: event.sheet_no ?? "",
            left_value: event.left_value ?? null,
            right_value: event.right_value ?? null,
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
    if (!inputRoot.trim()) {
      setLoadError("Project directory is required.")
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
      const payload = await desktopApi.analyzeSession({ inputRoot }, handleEvent)
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

  const filteredIssues = useMemo(() => {
    const issues = result?.issues ?? []
    const needle = deferredIssueSearch.trim().toLowerCase()
    if (!needle) {
      return issues
    }
    return issues.filter((issue) =>
      [
        issue.issue_id,
        issue.rule_id,
        issue.title,
        issue.filename,
        issue.sheet_no,
        issue.left_value ?? "",
        issue.right_value ?? "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    )
  }, [deferredIssueSearch, result?.issues])

  const selectedIssue = useMemo(() => {
    if (!result || !selectedIssueId) {
      return result?.issues[0] ?? null
    }
    return result.issues.find((issue) => issue.issue_id === selectedIssueId) ?? result.issues[0] ?? null
  }, [result, selectedIssueId])

  const summaryProject =
    result?.run ??
    recentProjects.find((project) => project.project_id === selectedProjectId) ??
    recentProjects[0] ??
    null
  const inputHealth = describeInputRoot(inputRoot)

  useEffect(() => {
    setIssueStatusDraft(selectedIssue?.status ?? "open")
  }, [selectedIssue?.issue_id, selectedIssue?.status])

  async function handleIssueStatusSave() {
    const projectId = result?.run.project_id ?? selectedProjectId
    if (!projectId || !selectedIssue) {
      return
    }
    setIsSavingIssueStatus(true)
    try {
      const updated = await desktopApi.setIssueStatus(projectId, selectedIssue.issue_id, issueStatusDraft)
      setResult(updated)
    } finally {
      setIsSavingIssueStatus(false)
    }
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

        {screen === "launch" && (
          <section className="launch-grid">
            <article className="launch-card dropzone">
              <p className="eyebrow">Input</p>
              <h3>Import project directory</h3>
              <p>
                Desktop shell should support drag-and-drop folder import and native directory selection. This skeleton keeps the input explicit so the sidecar contract stays visible.
              </p>
              <div className={`input-health ${inputHealth.tone}`}>
                <strong>{inputHealth.title}</strong>
                <span>{inputHealth.detail}</span>
              </div>
              <label className="field">
                <span>Project directory</span>
                <input value={inputRoot} onChange={(event) => setInputRoot(event.target.value)} placeholder="Select a folder to analyze" />
              </label>
              {loadError ? <p className="error-note">{loadError}</p> : null}
              <div className="button-row">
                <button type="button" className="primary-button" disabled={!inputRoot.trim() || isAnalyzing} onClick={() => void handleAnalyzeClick()}>
                  {isAnalyzing ? "Analyzing..." : "Start analysis"}
                </button>
                <button type="button" className="ghost-button">
                  Native folder picker
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
                    <th>Rule</th>
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
                      <td>{issue.rule_id}</td>
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
                        void desktopApi
                          .renderPreview(result?.run.project_id ?? selectedProjectId ?? "project-alpha", issue.issue_id)
                          .then((preview) => setPreviewSrc(preview.preview_src))
                      }}
                    >
                      <td>{issue.severity}</td>
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
                  </div>
                  <div className="detail-block">
                    <span>Evidence chain</span>
                    <pre>{JSON.stringify(selectedIssue.evidence, null, 2)}</pre>
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
                    {previewSrc ? <img src={previewSrc} alt="Issue preview" className="preview-image" /> : <div className="preview-empty">Preview will be supplied by render-preview.</div>}
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
      detail: "Enter a local project directory before starting the sidecar run.",
      tone: "warn",
    }
  }
  if (/^[a-zA-Z]:\\/.test(value) || value.startsWith("\\\\")) {
    return {
      title: "Input looks ready",
      detail: "Absolute Windows path detected. The shell can pass this directly to the Python sidecar.",
      tone: "ready",
    }
  }
  return {
    title: "Manual verification suggested",
    detail: "This does not look like an absolute Windows directory yet. Native folder-picker wiring is still pending.",
    tone: "warn",
  }
}

export default App
