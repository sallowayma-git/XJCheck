import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type KeyboardEvent as ReactKeyboardEvent } from "react"

import {
  clampPreviewPan,
  computeContainSize,
  computePreviewPanBounds,
  type PreviewPanMetrics,
  type PreviewPoint,
  type PreviewSize,
} from "./previewPan"

/** 预览区的缩放范围（相对取景基准，即 sidecar 给出的初始视图）。 */
export const PREVIEW_ZOOM_MIN = 0.5
export const PREVIEW_ZOOM_MAX = 8
const DEFAULT_NATURAL_SIZE: PreviewSize = { width: 960, height: 540 }

type DragState = {
  pointerId: number
  startClientX: number
  startClientY: number
  startPan: PreviewPoint
}

type UsePreviewViewportOptions = {
  /** 取景基准倍率（sidecar 的 viewport_scale）；缩放倍率在其上相乘。 */
  baseScale: number
  /** 图像原始尺寸，未知时使用默认值。 */
  naturalSize: PreviewSize | null
  /** 内容变化时（如换图、换问题）复位缩放与平移。 */
  resetKey: string
}

/**
 * 单个预览面板的缩放 / 平移 / 复位逻辑。
 * 滚轮以鼠标位置为中心缩放（阻止页面滚动），按住拖动平移，双击或 reset() 复位。
 * 只对已渲染的图像做 CSS 变换，不触发任何重新渲染请求。
 */
export function usePreviewViewport({ baseScale, naturalSize, resetKey }: UsePreviewViewportOptions) {
  const [shellNode, setShellNode] = useState<HTMLDivElement | null>(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<PreviewPoint>({ x: 0, y: 0 })
  const [viewport, setViewport] = useState<PreviewSize>({ width: 0, height: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef<DragState | null>(null)
  const latestRef = useRef({ zoom, pan, viewport, baseScale, naturalSize })
  const wheelRef = useRef<(event: WheelEvent) => void>(() => undefined)

  const effectiveScale = baseScale * zoom
  const natural = naturalSize ?? DEFAULT_NATURAL_SIZE
  const content = useMemo(() => computeContainSize(natural, viewport), [natural, viewport])
  const metrics: PreviewPanMetrics = useMemo(
    () => ({ viewport, content, scale: effectiveScale }),
    [viewport, content, effectiveScale],
  )
  const bounds = useMemo(() => computePreviewPanBounds(metrics), [metrics])
  const canPan = bounds.maxX > 0 || bounds.maxY > 0

  latestRef.current = { zoom, pan, viewport, baseScale, naturalSize }

  // 内容切换时复位，且不依赖缩放本身。
  useLayoutEffect(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setIsDragging(false)
    dragRef.current = null
  }, [resetKey, baseScale])

  // 量取视口尺寸；窗口或面板尺寸变化时重新约束平移范围。
  useLayoutEffect(() => {
    if (!shellNode) {
      return
    }
    const measure = () => {
      const rect = shellNode.getBoundingClientRect()
      const next = { width: rect.width, height: rect.height }
      setViewport((previous) =>
        previous.width === next.width && previous.height === next.height ? previous : next,
      )
    }
    measure()
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure)
    observer?.observe(shellNode)
    window.addEventListener("resize", measure)
    return () => {
      observer?.disconnect()
      window.removeEventListener("resize", measure)
    }
  }, [shellNode])

  // 缩放或尺寸变化后，把平移量收回到合法范围内。
  useLayoutEffect(() => {
    setPan((current) => clampPreviewPan(current, metrics))
  }, [metrics])

  // 滚轮：以鼠标位置为缩放中心；原生监听以便阻止页面滚动。
  wheelRef.current = (event: WheelEvent) => {
    const shell = shellNode
    if (!shell) {
      return
    }
    event.preventDefault()
    const current = latestRef.current
    const rect = shell.getBoundingClientRect()
    const cursorX = event.clientX - rect.left - rect.width / 2
    const cursorY = event.clientY - rect.top - rect.height / 2
    const delta = Math.max(-120, Math.min(120, event.deltaY))
    const nextZoom = Math.min(PREVIEW_ZOOM_MAX, Math.max(PREVIEW_ZOOM_MIN, current.zoom * Math.exp(-delta * 0.0015)))
    if (nextZoom === current.zoom) {
      return
    }
    const ratio = nextZoom / current.zoom
    const nextPan = {
      x: cursorX - ratio * (cursorX - current.pan.x),
      y: cursorY - ratio * (cursorY - current.pan.y),
    }
    const nextMetrics: PreviewPanMetrics = {
      viewport: current.viewport,
      content: computeContainSize(current.naturalSize ?? DEFAULT_NATURAL_SIZE, current.viewport),
      scale: current.baseScale * nextZoom,
    }
    setZoom(nextZoom)
    setPan(clampPreviewPan(nextPan, nextMetrics))
  }

  useEffect(() => {
    if (!shellNode) {
      return
    }
    const listener = (event: WheelEvent) => wheelRef.current(event)
    shellNode.addEventListener("wheel", listener, { passive: false })
    return () => shellNode.removeEventListener("wheel", listener)
  }, [shellNode])

  const reset = useCallback(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [])

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>): void {
    if (!canPan || !event.isPrimary || event.button !== 0) {
      return
    }
    event.preventDefault()
    event.currentTarget.focus()
    event.currentTarget.setPointerCapture(event.pointerId)
    dragRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startPan: pan,
    }
    setIsDragging(true)
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>): void {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) {
      return
    }
    event.preventDefault()
    setPan(
      clampPreviewPan(
        {
          x: drag.startPan.x + (event.clientX - drag.startClientX),
          y: drag.startPan.y + (event.clientY - drag.startClientY),
        },
        metrics,
      ),
    )
  }

  function finishDrag(event: ReactPointerEvent<HTMLDivElement>, releaseCapture: boolean): void {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) {
      return
    }
    if (releaseCapture && event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    dragRef.current = null
    setIsDragging(false)
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>): void {
    if (!canPan) {
      return
    }
    const step = event.shiftKey ? 60 : 24
    const moves: Record<string, PreviewPoint> = {
      ArrowLeft: { x: step, y: 0 },
      ArrowRight: { x: -step, y: 0 },
      ArrowUp: { x: 0, y: step },
      ArrowDown: { x: 0, y: -step },
    }
    if (event.key === "Home") {
      event.preventDefault()
      setPan({ x: 0, y: 0 })
      return
    }
    const move = moves[event.key]
    if (!move) {
      return
    }
    event.preventDefault()
    setPan((current) =>
      clampPreviewPan({ x: current.x + move.x, y: current.y + move.y }, metrics),
    )
  }

  const attachShell = useCallback((node: HTMLDivElement | null) => {
    setShellNode(node)
  }, [])

  return {
    attachShell,
    zoom,
    zoomPercent: Math.round(zoom * 100),
    effectiveScale,
    pan,
    content,
    canPan,
    isDragging,
    isDefaultView: zoom === 1 && pan.x === 0 && pan.y === 0,
    reset,
    shellHandlers: {
      onPointerDown: handlePointerDown,
      onPointerMove: handlePointerMove,
      onPointerUp: (event: ReactPointerEvent<HTMLDivElement>) => finishDrag(event, true),
      onPointerCancel: (event: ReactPointerEvent<HTMLDivElement>) => finishDrag(event, true),
      onLostPointerCapture: (event: ReactPointerEvent<HTMLDivElement>) => finishDrag(event, false),
      onKeyDown: handleKeyDown,
      onDoubleClick: reset,
    },
  }
}
