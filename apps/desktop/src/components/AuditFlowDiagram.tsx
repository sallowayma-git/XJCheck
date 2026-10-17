import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react"

export type AuditFlowDot = {
  id: string
  label: string
  title: string
  projectName: string
  projectRoot: string
  phase: "input" | "superworks" | "coordination" | "result"
  /** 按需协同分流去向；真实运行事件不含该信息，恒为 null。 */
  branch: "v1" | "v2" | null
  failed: boolean
}

export type AuditFlowCoverage = {
  projectName: string
  value: string
}

/** 按需分流页数；null 表示当前运行无逐页分流信息，界面只显示阶段。 */
export type AuditFlowRouteCounts = { v1: number; v2: number } | null

type AuditFlowDiagramProps = {
  projectName: string
  pageCount: number
  processedPages: number
  coordinatedPages: number
  routeCounts: AuditFlowRouteCounts
  totalIssues: number
  coverageByProject: AuditFlowCoverage[]
  activeStage: string
  isAnalyzing: boolean
  isComplete: boolean
  flowDots: AuditFlowDot[]
}

type NodeKey = "input" | "sw" | "v1" | "v2" | "coord" | "result"
type EdgeKey = "input>sw" | "sw>coord" | "sw>v1" | "v1>coord" | "sw>v2" | "v2>coord" | "coord>result"

type Journey = {
  id: string
  label: string
  failed: boolean
  edges: EdgeKey[]
  step: number
  edgeStart: number
  pauseUntil: number | null
}

type DotSnapshot = {
  phase: AuditFlowDot["phase"]
  branch: AuditFlowDot["branch"]
}

type Box = { left: number; top: number; width: number; height: number }

type Geometry = {
  width: number
  height: number
  paths: Record<EdgeKey, string>
}

const NODE_KEYS: NodeKey[] = ["input", "sw", "v1", "v2", "coord", "result"]
const STAGE_ORDER = ["scan", "convert", "extract", "pair", "audit", "render"]

/** 同时在途的圆点上限（性能）。 */
const SLOT_COUNT = 6
const LAUNCH_GAP_MS = 160
const PAUSE_MS = 220

const EDGES: Array<{ key: EdgeKey; from: NodeKey; to: NodeKey; fromX: number; toX: number; branch: boolean }> = [
  { key: "input>sw", from: "input", to: "sw", fromX: 0.5, toX: 0.5, branch: false },
  { key: "sw>coord", from: "sw", to: "coord", fromX: 0.5, toX: 0.5, branch: false },
  { key: "sw>v1", from: "sw", to: "v1", fromX: 0.3, toX: 0.5, branch: true },
  { key: "v1>coord", from: "v1", to: "coord", fromX: 0.5, toX: 0.3, branch: true },
  { key: "sw>v2", from: "sw", to: "v2", fromX: 0.7, toX: 0.5, branch: true },
  { key: "v2>coord", from: "v2", to: "coord", fromX: 0.5, toX: 0.7, branch: true },
  { key: "coord>result", from: "coord", to: "result", fromX: 0.5, toX: 0.5, branch: false },
]

const EDGE_DURATION_MS: Record<EdgeKey, number> = {
  "input>sw": 640,
  "sw>coord": 820,
  "sw>v1": 620,
  "v1>coord": 620,
  "sw>v2": 620,
  "v2>coord": 620,
  "coord>result": 860,
}

const EDGE_TARGET: Record<EdgeKey, NodeKey> = {
  "input>sw": "sw",
  "sw>coord": "coord",
  "sw>v1": "v1",
  "v1>coord": "coord",
  "sw>v2": "v2",
  "v2>coord": "coord",
  "coord>result": "result",
}

const PHASE_NODE: Record<AuditFlowDot["phase"], NodeKey> = {
  input: "input",
  superworks: "sw",
  coordination: "coord",
  result: "result",
}

/** 根据阶段变化与分流去向，得到圆点需要走过的连线。 */
function routeEdges(
  from: AuditFlowDot["phase"],
  to: AuditFlowDot["phase"],
  branch: AuditFlowDot["branch"],
): EdgeKey[] {
  const nodes: NodeKey[] = ["input", "sw", ...(branch ? [branch] : []), "coord", "result"]
  const start = nodes.indexOf(PHASE_NODE[from])
  const end = nodes.indexOf(PHASE_NODE[to])
  if (start < 0 || end <= start) {
    return []
  }
  const edges: EdgeKey[] = []
  const chain = nodes.slice(start, end + 1)
  for (let index = 0; index < chain.length - 1; index += 1) {
    edges.push(`${chain[index]}>${chain[index + 1]}` as EdgeKey)
  }
  return edges
}

function edgePath(from: Box, fromX: number, to: Box, toX: number): string {
  const ax = from.left + from.width * fromX
  const ay = from.top + from.height
  const bx = to.left + to.width * toX
  const by = to.top
  const dy = Math.max(by - ay, 16)
  const c1 = ay + dy * 0.5
  const c2 = by - dy * 0.5
  return `M ${ax.toFixed(1)} ${ay.toFixed(1)} C ${ax.toFixed(1)} ${c1.toFixed(1)}, ${bx.toFixed(1)} ${c2.toFixed(1)}, ${bx.toFixed(1)} ${by.toFixed(1)}`
}

function measureGeometry(
  container: HTMLElement,
  nodes: Partial<Record<NodeKey, HTMLElement | null>>,
): Geometry | null {
  const boxes = {} as Record<NodeKey, Box>
  for (const key of NODE_KEYS) {
    const element = nodes[key]
    if (!element) {
      return null
    }
    boxes[key] = {
      left: element.offsetLeft,
      top: element.offsetTop,
      width: element.offsetWidth,
      height: element.offsetHeight,
    }
  }
  const paths = {} as Record<EdgeKey, string>
  for (const edge of EDGES) {
    paths[edge.key] = edgePath(boxes[edge.from], edge.fromX, boxes[edge.to], edge.toX)
  }
  return { width: container.clientWidth, height: container.clientHeight, paths }
}

function sameGeometry(a: Geometry, b: Geometry): boolean {
  if (a.width !== b.width || a.height !== b.height) {
    return false
  }
  return EDGES.every((edge) => a.paths[edge.key] === b.paths[edge.key])
}

function easeInOut(value: number): number {
  return value * value * (3 - 2 * value)
}

export function AuditFlowDiagram({
  projectName,
  pageCount,
  processedPages,
  coordinatedPages,
  routeCounts,
  totalIssues,
  coverageByProject,
  activeStage,
  isAnalyzing,
  isComplete,
  flowDots,
}: AuditFlowDiagramProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const nodeRefs = useRef<Partial<Record<NodeKey, HTMLDivElement | null>>>({})
  const edgeRefs = useRef<Partial<Record<EdgeKey, SVGPathElement | null>>>({})
  const slotRefs = useRef<Array<HTMLDivElement | null>>([])
  const queueRef = useRef<Journey[]>([])
  const slotsRef = useRef<Array<Journey | null>>(Array.from({ length: SLOT_COUNT }, () => null))
  const nextLaunchRef = useRef(0)
  const frameRef = useRef<number | null>(null)
  const seenRef = useRef(new Map<string, DotSnapshot>())
  const [geometry, setGeometry] = useState<Geometry | null>(null)

  const stageIndex = STAGE_ORDER.indexOf(activeStage)
  const inputActive = isAnalyzing && (activeStage === "scan" || activeStage === "convert")
  const swActive = isAnalyzing && activeStage === "extract"
  const coordActive = isAnalyzing && (activeStage === "pair" || activeStage === "audit")
  const idle = !isAnalyzing && !isComplete && processedPages === 0 && flowDots.length === 0
  const status = isComplete ? "已完成" : isAnalyzing ? "处理中" : "等待开始"
  const statusTone = isComplete ? "is-complete" : isAnalyzing ? "is-running" : "is-idle"
  const note = isComplete
    ? "图纸已全部汇入结果，覆盖率按项目列出"
    : "图纸逐页进入 SuperWORKS，需要时由 V1、V2 补证后汇入协调审计"

  const flashNode = (key: NodeKey) => {
    const element = nodeRefs.current[key]
    if (!element) {
      return
    }
    element.removeAttribute("data-hit")
    void element.offsetWidth
    element.setAttribute("data-hit", "1")
    window.setTimeout(() => {
      if (element.getAttribute("data-hit") === "1") {
        element.removeAttribute("data-hit")
      }
    }, 700)
  }

  const tick = (now: number) => {
    frameRef.current = null
    const slots = slotsRef.current
    if (queueRef.current.length && now >= nextLaunchRef.current) {
      const free = slots.findIndex((slot) => slot === null)
      if (free >= 0) {
        const journey = queueRef.current.shift()
        if (journey) {
          journey.edgeStart = now
          slots[free] = journey
          nextLaunchRef.current = now + LAUNCH_GAP_MS
          const element = slotRefs.current[free]
          if (element) {
            element.classList.toggle("is-failed", journey.failed)
            const tag = element.querySelector(".flow-pulse-tag")
            if (tag) {
              tag.textContent = journey.label
            }
          }
        }
      }
    }

    let busy = queueRef.current.length > 0
    slots.forEach((journey, index) => {
      if (!journey) {
        return
      }
      busy = true
      const element = slotRefs.current[index]
      if (!element) {
        return
      }
      if (journey.pauseUntil !== null) {
        if (now < journey.pauseUntil) {
          return
        }
        journey.pauseUntil = null
        journey.edgeStart = now
      }
      const edge = journey.edges[journey.step]
      const path = edgeRefs.current[edge]
      if (!path) {
        slots[index] = null
        element.style.opacity = "0"
        return
      }
      const progress = Math.min(1, (now - journey.edgeStart) / EDGE_DURATION_MS[edge])
      const length = path.getTotalLength()
      const point = path.getPointAtLength(length * easeInOut(progress))
      element.style.opacity = "1"
      element.style.transform = `translate(${point.x.toFixed(1)}px, ${point.y.toFixed(1)}px)`
      if (progress >= 1) {
        flashNode(EDGE_TARGET[edge])
        journey.step += 1
        element.style.opacity = "0"
        if (journey.step >= journey.edges.length) {
          slots[index] = null
          return
        }
        journey.pauseUntil = now + PAUSE_MS
      }
    })

    if (busy) {
      frameRef.current = window.requestAnimationFrame(tick)
    }
  }

  const scheduleFrame = () => {
    if (frameRef.current === null) {
      frameRef.current = window.requestAnimationFrame(tick)
    }
  }

  const resetPulses = () => {
    queueRef.current = []
    slotsRef.current = slotsRef.current.map(() => null)
    slotRefs.current.forEach((element) => {
      if (element) {
        element.style.opacity = "0"
      }
    })
    if (frameRef.current !== null) {
      window.cancelAnimationFrame(frameRef.current)
      frameRef.current = null
    }
  }

  // 监听圆点阶段变化，把新的移动路径排入队列。
  useEffect(() => {
    const seen = seenRef.current
    if (!flowDots.length) {
      if (seen.size) {
        seen.clear()
        resetPulses()
      }
      return
    }
    for (const dot of flowDots) {
      const previous = seen.get(dot.id)
      seen.set(dot.id, { phase: dot.phase, branch: dot.branch })
      if (!previous || (previous.phase === dot.phase && previous.branch === dot.branch)) {
        continue
      }
      if (dot.failed && dot.phase !== "superworks") {
        continue
      }
      const edges = routeEdges(previous.phase, dot.phase, dot.branch)
      if (!edges.length) {
        continue
      }
      const existing =
        queueRef.current.find((journey) => journey.id === dot.id) ??
        slotsRef.current.find((journey) => journey?.id === dot.id) ??
        null
      if (existing) {
        existing.edges.push(...edges)
      } else {
        queueRef.current.push({
          id: dot.id,
          label: dot.label,
          failed: dot.failed,
          edges,
          step: 0,
          edgeStart: 0,
          pauseUntil: null,
        })
      }
    }
    scheduleFrame()
    // scheduleFrame/resetPulses 只读取 ref，依赖 flowDots 即可。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flowDots])

  useEffect(() => {
    return () => {
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current)
        frameRef.current = null
      }
    }
  }, [])

  // 节点尺寸随字号/窗口变化时重新量取连线端点。
  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }
    const update = () => {
      const next = measureGeometry(container, nodeRefs.current)
      if (next) {
        setGeometry((previous) => (previous && sameGeometry(previous, next) ? previous : next))
      }
    }
    update()
    const observer = new ResizeObserver(() => update())
    observer.observe(container)
    for (const key of NODE_KEYS) {
      const element = nodeRefs.current[key]
      if (element) {
        observer.observe(element)
      }
    }
    return () => observer.disconnect()
  }, [])

  const coverageLines = coverageByProject.length
    ? coverageByProject.map((item) => (
        <span key={item.projectName} title={`${item.projectName}：${item.value}`}>
          {item.projectName} · 覆盖率 {item.value}
        </span>
      ))
    : [
        <span key="pending" className="flow-coverage-pending">
          {isAnalyzing ? "覆盖率将在项目审计完成后显示" : "尚无覆盖率数据"}
        </span>,
      ]

  const mainEdgeLive = isAnalyzing
  const branchEdgeLive = coordActive

  return (
    <article className="panel process-flow panel-pad">
      <div className="flow-heading">
        <h3>审计数据流</h3>
        <span className={`flow-status ${statusTone}`}>{status}</span>
      </div>
      <p className="flow-note">{note}</p>
      <div className="flow-stage" aria-label="图纸从输入、SuperWORKS 识别到按需协同、协调审计和结果的数据流">
        <div ref={containerRef} className={`flow-diagram ${idle ? "is-idle" : ""}`}>
          {geometry ? (
            <svg
              className="flow-lines"
              viewBox={`0 0 ${geometry.width} ${geometry.height}`}
              aria-hidden="true"
            >
              <defs>
                <marker id="flow-arrow-main" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
                  <path d="M0,0 L8,4 L0,8 z" className="flow-arrow-main" />
                </marker>
                <marker id="flow-arrow-branch" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
                  <path d="M0,0 L8,4 L0,8 z" className="flow-arrow-branch" />
                </marker>
              </defs>
              {EDGES.map((edge) => {
                const live = edge.branch ? branchEdgeLive : mainEdgeLive
                const className = `flow-line ${edge.branch ? "is-branch" : "is-main"} ${live ? "is-live" : ""}`
                return (
                  <path
                    key={edge.key}
                    ref={(element) => {
                      edgeRefs.current[edge.key] = element
                    }}
                    d={geometry.paths[edge.key]}
                    className={className}
                    markerEnd={edge.branch ? "url(#flow-arrow-branch)" : "url(#flow-arrow-main)"}
                  />
                )
              })}
            </svg>
          ) : null}

          <FlowNode
            nodeKey="input"
            nodeRef={(element) => {
              nodeRefs.current.input = element
            }}
            className="flow-node-input"
            active={inputActive}
            done={isComplete || stageIndex > 1}
            icon={<IconSheets />}
            title={projectName}
            subtitle="图纸输入"
            count={pageCount > 0 ? `${pageCount} 页` : "扫描中"}
          />

          <FlowNode
            nodeKey="sw"
            nodeRef={(element) => {
              nodeRefs.current.sw = element
            }}
            className="flow-node-sw"
            active={swActive}
            done={isComplete || stageIndex > 2}
            icon={<IconChip />}
            title="SuperWORKS 引擎"
            subtitle="主识别路由，逐页识别"
            count={`${processedPages} 页`}
          />

          <FlowNode
            nodeKey="v1"
            nodeRef={(element) => {
              nodeRefs.current.v1 = element
            }}
            className="flow-node-v flow-node-v1"
            active={coordActive && (routeCounts?.v1 ?? 0) > 0}
            done={isComplete}
            title="V1 引擎"
            subtitle="按需协同"
            count={routeCounts ? `${routeCounts.v1} 页` : undefined}
          />

          <div className="flow-branch-label">按需协同</div>

          <FlowNode
            nodeKey="v2"
            nodeRef={(element) => {
              nodeRefs.current.v2 = element
            }}
            className="flow-node-v flow-node-v2"
            active={coordActive && (routeCounts?.v2 ?? 0) > 0}
            done={isComplete}
            title="V2 引擎"
            subtitle="按需协同"
            count={routeCounts ? `${routeCounts.v2} 页` : undefined}
          />

          <FlowNode
            nodeKey="coord"
            nodeRef={(element) => {
              nodeRefs.current.coord = element
            }}
            className="flow-node-coord"
            active={coordActive}
            done={isComplete}
            icon={<IconMerge />}
            title="协调审计"
            subtitle="汇总三引擎结果并核对"
            count={`${coordinatedPages} 页`}
          />

          <FlowNode
            nodeKey="result"
            nodeRef={(element) => {
              nodeRefs.current.result = element
            }}
            className="flow-node-result"
            active={isComplete}
            done={isComplete}
            icon={<IconReport />}
            title="审计结果"
            subtitle="问题与覆盖率"
            count={`${totalIssues} 条`}
          >
            <div className="flow-coverage-list" aria-label="各项目识别覆盖率">
              {coverageLines}
            </div>
          </FlowNode>

          <div className="flow-pulses" aria-hidden="true">
            {Array.from({ length: SLOT_COUNT }, (_, index) => (
              <div
                key={index}
                ref={(element) => {
                  slotRefs.current[index] = element
                }}
                className="flow-pulse"
                style={{ opacity: 0 }}
              >
                <span className="flow-pulse-dot" />
                <span className="flow-pulse-tag" />
              </div>
            ))}
          </div>
        </div>
        {idle ? <p className="flow-idle-hint">选择项目后开始</p> : null}
      </div>
    </article>
  )
}

type FlowNodeProps = {
  nodeKey: NodeKey
  nodeRef: (element: HTMLDivElement | null) => void
  className: string
  active: boolean
  done: boolean
  icon?: ReactNode
  title: string
  subtitle: string
  count?: string
  children?: ReactNode
}

function FlowNode({ nodeKey, nodeRef, className, active, done, icon, title, subtitle, count, children }: FlowNodeProps) {
  return (
    <div
      ref={nodeRef}
      className={`flow-node flow-node-${nodeKey} ${className} ${active ? "is-active" : ""} ${done ? "is-done" : ""}`}
    >
      <div className="flow-node-main">
        {icon ? (
          <span className="flow-node-icon" aria-hidden="true">
            {icon}
          </span>
        ) : null}
        <div className="flow-node-body">
          <strong title={title}>{title}</strong>
          <span title={subtitle}>{subtitle}</span>
        </div>
        {count !== undefined ? <span className="flow-node-count">{count}</span> : null}
      </div>
      {children}
      {done ? (
        <span className="flow-node-done" aria-label="已完成">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m5 12 4 4 10-10" />
          </svg>
        </span>
      ) : null}
    </div>
  )
}

function IconSheets() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 3h7l4 4v11a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M4 7v12a1 1 0 0 0 1 1h9" />
      <path d="M11 11h5M11 14h5M11 17h3" />
    </svg>
  )
}

function IconChip() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="2" />
      <rect x="10" y="10" width="4" height="4" rx="0.5" />
      <path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4" />
    </svg>
  )
}

function IconMerge() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="6" cy="5" r="2" />
      <circle cx="6" cy="19" r="2" />
      <circle cx="18" cy="12" r="2" />
      <path d="M6 7v10" />
      <path d="M8 6c5 0 8 2 8 5" />
      <path d="M8 18c5 0 8-2 8-5" />
    </svg>
  )
}

function IconReport() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4h6v3H9z" />
      <path d="m9 13 2 2 4-4" />
    </svg>
  )
}
