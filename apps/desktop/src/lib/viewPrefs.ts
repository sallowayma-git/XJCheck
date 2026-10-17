/** 界面折叠等纯展示偏好，仅保存在本机；读写均有 try/catch，存储不可用时退回默认值。 */

export const RESULT_TOOLBAR_COLLAPSED_KEY = "xj-toolkit.result-toolbar-collapsed"

export function loadResultToolbarCollapsed(): boolean {
  if (typeof window === "undefined") {
    return false
  }
  try {
    return window.localStorage.getItem(RESULT_TOOLBAR_COLLAPSED_KEY) === "1"
  } catch {
    return false
  }
}

export function saveResultToolbarCollapsed(collapsed: boolean): void {
  if (typeof window === "undefined") {
    return
  }
  try {
    if (collapsed) {
      window.localStorage.setItem(RESULT_TOOLBAR_COLLAPSED_KEY, "1")
    } else {
      window.localStorage.removeItem(RESULT_TOOLBAR_COLLAPSED_KEY)
    }
  } catch {
    // 存储不可用时仅保留本次会话内的状态。
  }
}
