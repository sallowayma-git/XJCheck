import { useEffect, useRef, useState } from "react"

import { desktopApi, DesktopOperationError } from "../lib/desktopApi"
import type { BBox } from "../lib/issueLocations"
import { beginRequest, createRequestGeneration, invalidateRequests, isCurrentRequest } from "../lib/requestGeneration"
import { normalizePreviewScale, type PreviewSize } from "../lib/previewPan"
import { boxToCanvasPercent, type PreviewExtent } from "../lib/previewGeometry"
import {
  createPreviewContextKey,
  resolvePreviewEmptyState,
  shouldRenderPreview,
  type PreviewMode,
} from "../lib/previewPolicy"
import { usePreviewViewport } from "../lib/usePreviewViewport"
import type { PreviewPayload } from "../types"

const PANE_REQUEST_TIMEOUT_MS = 20_000
const PANE_REQUEST_DELAY_MS = 120
const PANE_ERROR_TITLE = "无法生成该位置的图纸预览。"
const PANE_MISSING_FALLBACK = "该图纸几何数据缺失，请重新校验项目"

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
  /** 问题编号：后端据此恢复问题高亮；无问题时为 null。 */
  issueId: string | null
  /** 问题所在线组（仅当与图纸一致时传入），用于恢复线端高亮。 */
  lineGroupId: string | null
  sheetId: string | null
  /** 需要取景的包围盒列表；null 表示渲染整张图。 */
  focus: number[][] | null
  /** 需要高亮的框（卡片选中的位置），只在前端叠加显示。 */
  highlightBox: BBox | null
  clientSessionId: string
  clientSessionEpoch: number | null
  /** 预览方式（设置页切换，立即生效）。 */
  previewMode: PreviewMode
  emptyText: string
}

type PaneStatus = "idle" | "loading" | "ready" | "error" | "missing"

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
  lineGroupId,
  sheetId,
  focus,
  highlightBox,
  clientSessionId,
  clientSessionEpoch,
  previewMode,
  emptyText,
}: LocationPreviewPaneProps) {
  const generationRef = useRef(createRequestGeneration())
  const [preview, setPreview] = useState<PreviewPayload | null>(null)
  const [status, setStatus] = useState<PaneStatus>("idle")
  const [errorText, setErrorText] = useState<string | null>(null)
  const [errorDetail, setErrorDetail] = useState<string | null>(null)
  const [natural, setNatural] = useState<PreviewSize | null>(null)
  /** 用户在本面板点击“生成预览”或“重新预览”的记录，并记下当时的目标上下文。 */
  const [manualRequest, setManualRequest] = useState<{ id: number; contextKey: string } | null>(null)

  const focusKey = focus ? JSON.stringify(focus) : "sheet"
  const contextKey = `${createPreviewContextKey({ projectId, runId, issueId, sheetId, lineGroupId })}|${focusKey}`
  const manualAdmitted = manualRequest !== null && manualRequest.contextKey === contextKey
  const admitted = shouldRenderPreview(previewMode, manualAdmitted ? 1 : 0, 0)

  useEffect(() => {
    setPreview(null)
    setErrorText(null)
    setErrorDetail(null)
    setNatural(null)
    if (!projectId || !sheetId || clientSessionEpoch === null) {
      setStatus("idle")
      return
    }
    if (!admitted) {
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
        lineGroupId,
        clientSessionId,
        clientSessionEpoch,
        runId,
        focus,
      )
      void withTimeout(pending, PANE_REQUEST_TIMEOUT_MS, "操作超时，请稍后重试。")
        .then((payload) => {
          settled = true
          if (!isCurrentRequest(state, token) || payload.request_id !== requestId) {
            return
          }
          if (payload.geometry_missing) {
            setPreview(null)
            setErrorText(payload.geometry_missing_message || PANE_MISSING_FALLBACK)
            setStatus("missing")
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
          if (error instanceof DesktopOperationError) {
            setErrorText(error.prefix || PANE_ERROR_TITLE)
            setErrorDetail(error.detail)
          } else {
            setErrorText(PANE_ERROR_TITLE)
            setErrorDetail(error instanceof Error && error.message ? error.message : null)
          }
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
    // focus 的内容由 focusKey 唯一确定；manualRequest 的变化用于触发手动生成与重新预览。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, runId, issueId, lineGroupId, sheetId, focusKey, clientSessionEpoch, previewMode, admitted, manualRequest])

  const viewport = usePreviewViewport({
    baseScale: normalizePreviewScale(preview?.viewport_scale),
    naturalSize: natural,
    resetKey: `${issueId ?? ""}|${sheetId ?? ""}|${focusKey}|${preview?.request_id ?? ""}`,
  })

  const src = preview?.preview_src ?? null
  const extent = preview?.focus_bbox && preview.focus_bbox.length === 4 ? (preview.focus_bbox as PreviewExtent) : null
  const frame = extent && highlightBox ? boxToCanvasPercent(highlightBox, extent) : null

  const emptyState = resolvePreviewEmptyState({
    hasIssue: Boolean(projectId && sheetId),
    isLoading: status === "loading",
    mode: previewMode,
    hasError: status === "error",
    hasPreviewOptions: Boolean(projectId && sheetId),
  })

  function requestPreview(): void {
    setManualRequest((current) => ({ id: (current?.id ?? 0) + 1, contextKey }))
  }

  const userTriggered = manualRequest !== null
  const showAction = !src && (status === "error" || previewMode === "manual-only" || (status === "loading" && userTriggered))
  const actionLabel = status === "loading" ? "生成中…" : status === "error" ? "重新预览" : "生成预览"

  let message = emptyText
  if (status === "missing") {
    message = errorText ?? PANE_MISSING_FALLBACK
  } else if (status === "error") {
    message = errorText ?? PANE_ERROR_TITLE
  } else if (emptyState === "loading") {
    message = "正在生成区域预览…"
  } else if (emptyState === "off") {
    message = "预览已关闭，可在设置中开启"
  } else if (emptyState === "manual-only") {
    message = "点击下方按钮生成预览"
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
                setErrorText("预览图未能显示，可稍后重试。")
                setErrorDetail(null)
                setStatus("error")
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
          <div className={`preview-empty${status === "loading" ? " is-loading" : ""}`}>
            <span>{message}</span>
            {status === "error" && errorDetail ? <span className="preview-error-detail">{errorDetail}</span> : null}
            {showAction ? (
              <button type="button" className="ghost-button tb-small-button" disabled={status === "loading"} onClick={requestPreview}>
                {actionLabel}
              </button>
            ) : null}
          </div>
        )}
        {viewport.canPan ? <span className="preview-pan-hint">拖动查看周边</span> : null}
      </div>
    </section>
  )
}
