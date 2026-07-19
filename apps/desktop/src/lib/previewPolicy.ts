export const PREVIEW_MODE_STORAGE_KEY = "xj-toolkit.preview-mode"

export type PreviewMode = "auto" | "manual-only" | "off"

export type PreviewContextParts = {
  revision?: number | null
  runId?: string | null
  projectId?: string | null
  issueId?: string | null
  sheetId?: string | null
  lineGroupId?: string | null
}

export type PreviewEmptyState = "no-issue" | "loading" | "off" | "error" | "manual-only" | "no-preview" | "no-location"

export function parsePreviewMode(value: unknown): PreviewMode {
  return value === "manual-only" || value === "off" ? value : "auto"
}

export function shouldRenderPreview(
  mode: PreviewMode,
  manualGeneration: number,
  handledManualGeneration: number,
): boolean {
  if (mode === "off") {
    return false
  }
  return mode === "auto" || manualGeneration !== handledManualGeneration
}

export function createPreviewContextKey(parts: PreviewContextParts): string {
  return JSON.stringify([
    parts.revision ?? null,
    parts.runId ?? null,
    parts.projectId ?? null,
    parts.issueId ?? null,
    parts.sheetId ?? null,
    parts.lineGroupId ?? null,
  ])
}

export function isPreviewOutputCurrent(outputKey: string | null | undefined, currentKey: string): boolean {
  return Boolean(outputKey && outputKey === currentKey)
}

export function resolvePreviewEmptyState(input: {
  hasIssue: boolean
  isLoading: boolean
  mode: PreviewMode
  hasError: boolean
  hasPreviewOptions: boolean
}): PreviewEmptyState {
  if (!input.hasIssue) {
    return "no-issue"
  }
  if (input.isLoading) {
    return "loading"
  }
  if (input.mode === "off") {
    return "off"
  }
  if (input.hasError) {
    return "error"
  }
  if (input.mode === "manual-only") {
    return "manual-only"
  }
  return input.hasPreviewOptions ? "no-preview" : "no-location"
}
