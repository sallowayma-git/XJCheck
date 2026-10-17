/**
 * 预览图坐标变换，与 src/dwg_audit/desktop/preview.py 保持一致：
 *   _CANVAS_WIDTH/HEIGHT = 960 x 540，_HEADER_HEIGHT = 52，_EDGE_PAD = 18；
 *   scale = min((960 - 2*pad) / w, (540 - header - 2*pad) / h)，内容在画布内居中；
 *   sx(x) = origin_x + (x - min_x) * scale；sy(y) = origin_y + (max_y - y) * scale（CAD y 向上 → SVG y 向下）。
 * focus_bbox（取景范围，CAD 坐标）即 _build_svg 的 extent。
 */

export const PREVIEW_CANVAS = {
  width: 960,
  height: 540,
  header: 52,
  edgePad: 18,
} as const

export type PreviewExtent = [number, number, number, number]

export type CanvasTransform = {
  scale: number
  sx: (x: number) => number
  sy: (y: number) => number
}

export function makeCanvasTransform(extent: PreviewExtent): CanvasTransform {
  const [minX, minY, maxX, maxY] = extent
  const width = Math.max(maxX - minX, 1e-6)
  const height = Math.max(maxY - minY, 1e-6)
  const availW = PREVIEW_CANVAS.width - PREVIEW_CANVAS.edgePad * 2
  const availH = PREVIEW_CANVAS.height - PREVIEW_CANVAS.header - PREVIEW_CANVAS.edgePad * 2
  const scale = Math.min(availW / width, availH / height)
  const contentW = width * scale
  const contentH = height * scale
  const originX = (PREVIEW_CANVAS.width - contentW) / 2
  const originY = PREVIEW_CANVAS.header + (PREVIEW_CANVAS.height - PREVIEW_CANVAS.header - contentH) / 2
  return {
    scale,
    sx: (x) => originX + (x - minX) * scale,
    sy: (y) => originY + (maxY - y) * scale,
  }
}

/** CAD 包围盒在预览图（画布）上的百分比位置，用于叠加高亮框。 */
export function boxToCanvasPercent(
  box: [number, number, number, number],
  extent: PreviewExtent,
): { left: number; top: number; width: number; height: number } | null {
  if (extent.some((value) => !Number.isFinite(value)) || box.some((value) => !Number.isFinite(value))) {
    return null
  }
  const transform = makeCanvasTransform(extent)
  const left = transform.sx(Math.min(box[0], box[2]))
  const right = transform.sx(Math.max(box[0], box[2]))
  const top = transform.sy(Math.max(box[1], box[3]))
  const bottom = transform.sy(Math.min(box[1], box[3]))
  return {
    left: (left / PREVIEW_CANVAS.width) * 100,
    top: (top / PREVIEW_CANVAS.height) * 100,
    width: ((right - left) / PREVIEW_CANVAS.width) * 100,
    height: ((bottom - top) / PREVIEW_CANVAS.height) * 100,
  }
}
