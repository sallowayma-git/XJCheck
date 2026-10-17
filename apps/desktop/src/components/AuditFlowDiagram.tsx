export type AuditFlowDot = {
  id: string
  label: string
  title: string
  projectName: string
  projectRoot: string
  phase: "input" | "superworks" | "coordination" | "result"
  failed: boolean
}

export type AuditFlowCoverage = {
  projectName: string
  value: string
}

type AuditFlowDiagramProps = {
  projectName: string
  pageCount: number
  totalIssues: number
  coverageByProject: AuditFlowCoverage[]
  activeStage: string
  isAnalyzing: boolean
  isComplete: boolean
  flowDots: AuditFlowDot[]
}

const motionPaths: Record<AuditFlowDot["phase"], string> = {
  input: "M 50 10 C 50 17, 50 25, 50 39",
  superworks: "M 50 29 C 50 35, 50 43, 50 50",
  coordination: "M 50 50 C 50 53, 50 56, 50 58",
  result: "M 50 76 C 50 78, 50 80, 50 82",
}

export function AuditFlowDiagram({
  projectName,
  pageCount,
  totalIssues,
  coverageByProject,
  activeStage,
  isAnalyzing,
  isComplete,
  flowDots,
}: AuditFlowDiagramProps) {
  const inputActive = isAnalyzing && (activeStage === "scan" || activeStage === "convert")
  const superworksActive = isAnalyzing && activeStage === "extract"
  const coordinationActive = isAnalyzing && (activeStage === "pair" || activeStage === "audit")
  const resultActive = isComplete
  const status = isComplete ? "已完成" : isAnalyzing ? "处理中" : "等待开始"

  return (
    <article className="panel process-flow panel-pad">
      <div className="flow-heading">
        <h3>审计数据流</h3>
        <span>{status}</span>
      </div>
      <p className="flow-note">
        {isComplete
          ? "页面已汇入结果；覆盖率按项目列出。"
          : "圆点按页面事件和整体阶段推进；当前事件不含逐页引擎分流。"}
      </p>
      <div className="flow-diagram" aria-label="图纸从输入、引擎识别到协调审计和结果的流程图">
        <svg className="flow-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <marker id="audit-flow-arrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L5,2.5 L0,5 z" />
            </marker>
          </defs>
          <path className="flow-edge" d="M 50 19 C 50 22, 50 25, 50 29" markerEnd="url(#audit-flow-arrow)" />
          <path className="flow-edge flow-edge-optional" d="M 36 39 C 33 39, 32 39, 29 39" markerEnd="url(#audit-flow-arrow)" />
          <path className="flow-edge flow-edge-optional" d="M 64 39 C 67 39, 68 39, 71 39" markerEnd="url(#audit-flow-arrow)" />
          <path className="flow-edge flow-edge-optional" d="M 15 50 C 15 54, 37 55, 48 58" markerEnd="url(#audit-flow-arrow)" />
          <path className="flow-edge flow-edge-optional" d="M 85 50 C 85 54, 63 55, 52 58" markerEnd="url(#audit-flow-arrow)" />
          <path className="flow-edge" d="M 50 50 C 50 53, 50 56, 50 58" markerEnd="url(#audit-flow-arrow)" />
          <path className="flow-edge" d="M 50 76 C 50 78, 50 80, 50 82" markerEnd="url(#audit-flow-arrow)" />
        </svg>

        <svg className="flow-particles" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {flowDots.map((dot, index) => {
            const phase = dot.phase
            const parkedAtEngine = phase === "superworks"
            const dotOffset = (index % 5) - 2
            return (
              <g
                key={`${dot.id}:${phase}`}
                className={`flow-particle ${dot.failed ? "failed" : ""} ${isComplete ? "settled" : ""}`}
              >
                <circle
                  cx={parkedAtEngine ? 50 + dotOffset * 1.15 : 0}
                  cy={parkedAtEngine ? 39 + Math.floor(index / 5) * 1.4 : 0}
                  r="1.35"
                >
                  {!parkedAtEngine ? (
                    <animateMotion
                      path={motionPaths[phase]}
                      dur={`${0.85 + (index % 3) * 0.12}s`}
                      begin={`${(index % 4) * 0.09}s`}
                      repeatCount="1"
                      fill="freeze"
                    />
                  ) : null}
                  <title>{`${dot.label} · ${dot.title}${dot.failed ? " · 转换失败" : ""}`}</title>
                </circle>
              </g>
            )
          })}
        </svg>

        <div className={`flow-node flow-node-input ${inputActive ? "active" : ""}`}>
          <span className="flow-node-kicker">输入</span>
          <strong title={projectName}>{projectName}</strong>
          <span>{pageCount > 0 ? `${pageCount} 张图纸` : "正在扫描图纸"}</span>
        </div>

        <div className="flow-engine-row" aria-label="引擎识别阶段">
          <div className="flow-node flow-node-engine flow-node-v1">
            <strong>V1 引擎</strong>
            <span>按需协同</span>
          </div>
          <div className={`flow-node flow-node-engine flow-node-superworks ${superworksActive ? "active" : ""}`}>
            <strong>SuperWORKS 引擎</strong>
            <span>主路由</span>
          </div>
          <div className="flow-node flow-node-engine flow-node-v2">
            <strong>V2 引擎</strong>
            <span>按需协同</span>
          </div>
        </div>
        <span className="flow-branch-note">对象级按需补证</span>

        <div className={`flow-node flow-node-coordination ${coordinationActive ? "active" : ""}`}>
          <strong>协调审计</strong>
          <span>汇总三引擎结果并核对问题</span>
        </div>

        <div className={`flow-node flow-node-result ${resultActive ? "active" : ""}`}>
          <div className="flow-result-summary">
            <strong>结果</strong>
            <span>用户问题 {totalIssues} 条</span>
          </div>
          <div className="flow-coverage-list" aria-label="各项目识别覆盖率">
            {coverageByProject.length ? coverageByProject.map((item) => (
              <span key={item.projectName} title={`${item.projectName}：${item.value}`}>
                {item.projectName} · {item.value}
              </span>
            )) : <span>{isAnalyzing ? "覆盖率将在项目审计完成后显示" : "尚无覆盖率数据"}</span>}
          </div>
        </div>
      </div>
    </article>
  )
}
