export type PreviewPoint = {
  x: number
  y: number
}

export type PreviewSize = {
  width: number
  height: number
}

export type PreviewPanMetrics = {
  viewport: PreviewSize
  content: PreviewSize
  scale: number
}

export type PreviewPanBounds = {
  maxX: number
  maxY: number
}

export function normalizePreviewScale(value: unknown): number {
  const numeric = typeof value === "number" ? value : Number(value)
  if (!Number.isFinite(numeric)) {
    return 1
  }
  return Math.min(2.3, Math.max(1, numeric))
}

export function computeContainSize(natural: PreviewSize, viewport: PreviewSize): PreviewSize {
  if (
    !Number.isFinite(natural.width) ||
    !Number.isFinite(natural.height) ||
    !Number.isFinite(viewport.width) ||
    !Number.isFinite(viewport.height) ||
    natural.width <= 0 ||
    natural.height <= 0 ||
    viewport.width <= 0 ||
    viewport.height <= 0
  ) {
    return { width: 0, height: 0 }
  }
  const ratio = Math.min(viewport.width / natural.width, viewport.height / natural.height)
  return {
    width: natural.width * ratio,
    height: natural.height * ratio,
  }
}

export function computePreviewPanBounds(metrics: PreviewPanMetrics): PreviewPanBounds {
  const scale = normalizePreviewScale(metrics.scale)
  const scaledWidth = Math.max(0, metrics.content.width) * scale
  const scaledHeight = Math.max(0, metrics.content.height) * scale
  return {
    maxX: Math.max(0, (scaledWidth - Math.max(0, metrics.viewport.width)) / 2),
    maxY: Math.max(0, (scaledHeight - Math.max(0, metrics.viewport.height)) / 2),
  }
}

export function clampPreviewPan(point: PreviewPoint, metrics: PreviewPanMetrics): PreviewPoint {
  const bounds = computePreviewPanBounds(metrics)
  const x = Number.isFinite(point.x) ? point.x : 0
  const y = Number.isFinite(point.y) ? point.y : 0
  return {
    x: bounds.maxX > 0 ? Math.min(bounds.maxX, Math.max(-bounds.maxX, x)) : 0,
    y: bounds.maxY > 0 ? Math.min(bounds.maxY, Math.max(-bounds.maxY, y)) : 0,
  }
}
