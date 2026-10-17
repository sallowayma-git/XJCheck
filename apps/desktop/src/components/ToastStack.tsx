import { useCallback, useEffect } from "react"

export type ToastItem = {
  id: number
  message: string
}

const TOAST_DURATION_MS = 4000

type ToastStackProps = {
  toasts: ToastItem[]
  onDismiss: (id: number) => void
}

/** Bottom-right stack of short notices. Each one dismisses itself after a few seconds. */
export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  if (toasts.length === 0) {
    return null
  }
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

function ToastCard({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: number) => void }) {
  const dismiss = useCallback(() => onDismiss(toast.id), [onDismiss, toast.id])

  useEffect(() => {
    const timer = window.setTimeout(dismiss, TOAST_DURATION_MS)
    return () => window.clearTimeout(timer)
  }, [dismiss])

  return (
    <div className="toast-card" role="alert">
      <span className="toast-message">{toast.message}</span>
      <button type="button" className="toast-close" aria-label="关闭提示" onClick={dismiss}>
        ×
      </button>
    </div>
  )
}
