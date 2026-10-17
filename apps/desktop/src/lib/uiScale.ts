/**
 * 界面字号（仅影响界面文字，与 sidecar 运行参数无关）。
 * 通过根元素的 --ui-font-scale 变量缩放所有以 calc(Npx * var(--ui-font-scale)) 书写的字号。
 */

export const UI_SCALE_STORAGE_KEY = "xj-toolkit.ui-scale"
export const UI_SCALE_MIN = 85
export const UI_SCALE_MAX = 140
export const UI_SCALE_STEP = 5
export const UI_SCALE_DEFAULT = 100

export function clampUiScale(value: number): number {
  if (!Number.isFinite(value)) {
    return UI_SCALE_DEFAULT
  }
  const stepped = Math.round(value / UI_SCALE_STEP) * UI_SCALE_STEP
  return Math.min(UI_SCALE_MAX, Math.max(UI_SCALE_MIN, stepped))
}

export function loadUiScale(): number {
  if (typeof window === "undefined") {
    return UI_SCALE_DEFAULT
  }
  try {
    const raw = window.localStorage.getItem(UI_SCALE_STORAGE_KEY)
    if (!raw) {
      return UI_SCALE_DEFAULT
    }
    return clampUiScale(Number(raw))
  } catch {
    return UI_SCALE_DEFAULT
  }
}

export function persistUiScale(percent: number): void {
  if (typeof window === "undefined") {
    return
  }
  try {
    if (percent === UI_SCALE_DEFAULT) {
      window.localStorage.removeItem(UI_SCALE_STORAGE_KEY)
    } else {
      window.localStorage.setItem(UI_SCALE_STORAGE_KEY, String(percent))
    }
  } catch {
    // 存储不可用时仅保留本次会话内的设置。
  }
}

export function applyUiScale(percent: number): void {
  if (typeof document === "undefined") {
    return
  }
  document.documentElement.style.setProperty("--ui-font-scale", String(percent / 100))
}
