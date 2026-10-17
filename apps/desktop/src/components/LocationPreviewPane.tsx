import { useEffect, useRef, useState } from "react"

import { desktopApi } from "../lib/desktopApi"
import type { BBox } from "../lib/issueLocations"
import { beginRequest, createRequestGeneration, invalidateRequests, isCurrentRequest } from "../lib/requestGeneration"
import { normalizePreviewScale, type PreviewSize } from "../lib/previewPan"
import { boxToCanvasPercent, type PreviewExtent } from "../lib/previewGeometry"
import { usePreviewViewport } from "../lib/usePreviewViewport"
import type { PreviewPayload } from "../types"

const PANE_REQUEST_TIMEOUT_MS = 20_000
const PANE_REQUEST_DELAY_MS = 120

let paneRequestSequence = 0

function createPaneRequestId(): string {
  paneRequestSequence += 1
  const randomId = globalThis.crypto?.randomUUID?.()
  return randomId ? `pane-${randomId}` : `pane-${Date.now().toString(36)}-${paneRequestSequence.toString(36)}`
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

export type LocationPreviewPaneProps = {
  caption: string
  subcaption: string
  projectId: string | null
  runId: string | null
  /** 位置预览按图纸与取景框请求，不依赖问题编号（后端只需 sheetId + focusJson）。 */
  issueId: string | null
  sheetId: string | null
  /** 需要取景的包围盒列表；null 表示渲染整张图。 */
  focus: number[][] | null
  /** 需要高亮的框（卡片选中的位置），只在前端叠加显示。 */
  highlightBox: BBox | null
  clientSessionId: string
  clientSessionEpoch: number | null
  emptyText: string
}

/**
 * 单个图纸位置的预览面板。独立发起 renderPreview，拥有自己的请求代次；
 * 缩放与平移只作用于已渲染的图像，切换高亮框不会重新请求。
 */
export function LocationPreviewPane({
  caption,
  subcaption,
  projectId,
  runId,
  issueId,
  sheetId,
  focus,
  highlightBox,
  clientSessionId,
  clientSessionEpoch,
  emptyText,
}: LocationPreviewPaneProps) {
  const generationRef = useRef(createRequestGeneration())
  const [preview, setPreview] = useState<PreviewPayload | null>(null)
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle")
  const [errorText, setErrorText] = useState<string | null>(null)
  const [natural, setNatural] = useState<PreviewSize | null>(null)

  const focusKey = focus ? JSON.stringify(focus) : "sheet"

  useEffect(() => {
    setPreview(null)
    setErrorText(null)
    setNatural(null)
    if (!projectId || !sheetId || clientSessionEpoch === null) {
      setStatus("idle")
      return
    }
    const state = generationRef.current
    const token = beginRequest(state)
    const requestId = createPaneRequestId()
    let sent = false
    let settled = false
    setStatus("loading")
    const timer = window.setTimeout(() => {
      if (!isCurrentRequest(state, token)) {
        return
      }
      sent = true
      const pending = desktopApi.renderPreview(
        projectId,
        issueId,
        requestId,
        token,
        sheetId,
        null,
        clientSessionId,
        clientSessionEpoch,
        runId,
        focus,
      )
      void withTimeout(pending, PANE_REQUEST_TIMEOUT_MS, "Preview request timed out.")
        .then((payload) => {
          settled = true
          if (!isCurrentRequest(state, token) || payload.request_id !== requestId) {
            return
          }
          setPreview(payload)
          setStatus("ready")
        })
        .catch((error: unknown) => {
          settled = true
          if (!isCurrentRequest(state, token)) {
            return
          }
          setErrorText(error instanceof Error && error.message ? error.message : "无法生成该位置的图纸预览。")
          setStatus("error")
        })
    }, PANE_REQUEST_DELAY_MS)
    return () => {
      window.clearTimeout(timer)
      invalidateRequests(state)
      if (sent && !settled) {
        void desktopApi.cancelPreview(requestId, token, clientSessionId, clientSessionEpoch).catch(() => undefined)
      }
    }
    // focus 的内容由 focusKey 唯一确定。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, runId, issueId, sheetId, focusKey, clientSessionEpoch])

  const viewport = usePreviewViewport({
    baseScale: normalizePreviewScale(preview?.viewport_scale),
    naturalSize: natural,
    resetKey: `${issueId ?? ""}|${sheetId ?? ""}|${focusKey}|${preview?.request_id ?? ""}`,
  })

  const src = preview?.preview_src ?? null
  const extent = preview?.focus_bbox && preview.focus_bbox.length === 4 ? (preview.focus_bbox as PreviewExtent) : null
  const frame = extent && highlightBox ? boxToCanvasPercent(highlightBox, extent) : null

  let message = emptyText
  if (status === "loading") {
    message = "正在生成区域预览…"
  } else if (status === "error") {
    message = errorText ?? "无法生成该位置的图纸预览，可稍后重试。"
  }

  return (
    <section className="location-pane">
      <div className="location-pane-head">
        <strong title={caption}>{caption}</strong>
        <span>{subcaption}</span>
      </div>
      {src ? (
        <div className="preview-zoombar">
          <span className="muted">滚轮缩放 · 拖动平移 · 双击适应</span>
          <span className="preview-zoom-value">{viewport.zoomPercent}%</span>
          <button type="button" className="ghost-button tb-small-button" disabled={viewport.isDefaultView} onClick={viewport.reset}>
            适应
          </button>
        </div>
      ) : null}
      <div
        ref={viewport.attachShell}
        className={`preview-shell${viewport.canPan ? " is-pannable" : ""}${viewport.isDragging ? " is-dragging" : ""}`}
        aria-label={`${caption}，${viewport.canPan ? "可拖动查看周边区域" : "图纸预览"}`}
        role="group"
        tabIndex={viewport.canPan ? 0 : undefined}
        {...viewport.shellHandlers}
      >
        {src ? (
          <div
            className="preview-pan-layer"
            style={{
              width: viewport.content.width > 0 ? `${viewport.content.width}px` : "100%",
              height: viewport.content.height > 0 ? `${viewport.content.height}px` : "100%",
              transform: `translate3d(${viewport.pan.x}px, ${viewport.pan.y}px, 0) scale(${viewport.effectiveScale})`,
            }}
          >
            <img
              src={src}
              alt={caption}
              className="preview-image"
              draggable={false}
              onLoad={(event) =>
                setNatural({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })
              }
              onError={() => {
                setPreview(null)
                setStatus("error")
                setErrorText("预览图未能显示，可稍后重试。")
              }}
            />
            {frame ? (
              <span
                className="preview-frame"
                style={{ left: `${frame.left}%`, top: `${frame.top}%`, width: `${frame.width}%`, height: `${frame.height}%` }}
              />
            ) : null}
          </div>
        ) : (
          <div className={`preview-empty${status === "loading" ? " is-loading" : ""}`}>{message}</div>
        )}
        {viewport.canPan ? <span className="preview-pan-hint">拖动查看周边</span> : null}
      </div>
    </section>
  )
}
