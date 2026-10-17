/**
 * Pure helpers for optimistic and batch project deletion.
 *
 * The UI keeps the stored project list intact while a delete is in flight and
 * hides in-flight ids at render time. That makes rollback a simple matter of
 * dropping the id from the pending set: the card returns in its original order.
 */

export type ProjectDeleteOutcome = {
  project_id: string
  ok: boolean
  not_found: boolean
  error: string | null
}

export type ProjectDeleteFailure = {
  projectId: string
  message: string
}

export type ProjectDeleteSettlement = {
  succeededIds: string[]
  failed: ProjectDeleteFailure[]
}

const DEFAULT_DELETE_ERROR = "删除项目记录失败。"
const BUSY_DELETE_MESSAGE = "分析进行中，请稍后再删除。"

/** Drops every project whose id is in `hiddenIds`. Order is preserved. */
export function excludeProjectIds<T extends { project_id: string }>(
  projects: readonly T[],
  hiddenIds: ReadonlySet<string>,
): T[] {
  if (hiddenIds.size === 0) {
    return [...projects]
  }
  return projects.filter((project) => !hiddenIds.has(project.project_id))
}

/** Maps each requested id to its outcome. A missing outcome counts as a failure. */
export function settleProjectDeletes(
  requestedIds: readonly string[],
  outcomes: readonly ProjectDeleteOutcome[],
): ProjectDeleteSettlement {
  const byId = new Map(outcomes.map((outcome) => [outcome.project_id, outcome]))
  const succeededIds: string[] = []
  const failed: ProjectDeleteFailure[] = []
  for (const projectId of requestedIds) {
    const outcome = byId.get(projectId)
    if (!outcome) {
      failed.push({ projectId, message: DEFAULT_DELETE_ERROR })
    } else if (outcome.ok) {
      succeededIds.push(projectId)
    } else {
      failed.push({ projectId, message: outcome.error || DEFAULT_DELETE_ERROR })
    }
  }
  return { succeededIds, failed }
}

/**
 * Builds the failure toast. A single requested project gets the plain form;
 * a batch gets a count, with the first reason as an example.
 */
export function deleteFailureToast(failed: readonly ProjectDeleteFailure[], requestedCount: number): string {
  if (failed.length === 0) {
    return ""
  }
  if (requestedCount <= 1) {
    return `删除失败：${failed[0].message}`
  }
  return `${failed.length} 个项目删除失败：${failed[0].message}`
}

/** Turns a raw sidecar or bridge error into a short user-facing reason. */
export function humanizeDeleteErrorMessage(message: string): string {
  const text = message.trim()
  if (!text) {
    return DEFAULT_DELETE_ERROR
  }
  const lower = text.toLowerCase()
  if (lower.includes("workspace is active") || text.includes("分析进行中")) {
    return BUSY_DELETE_MESSAGE
  }
  if (lower.includes("permission") || lower.includes("access is denied")) {
    return "没有访问权限，请检查目录权限。"
  }
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "操作超时，请稍后重试。"
  }
  return text
}

/**
 * Runs tasks one at a time, in submission order. A failed task does not block
 * the ones queued after it. Used so deletes never contend for the sidecar lock.
 */
export function createSerialQueue(): <T>(task: () => Promise<T>) => Promise<T> {
  let tail: Promise<unknown> = Promise.resolve()
  return <T>(task: () => Promise<T>): Promise<T> => {
    const run = tail.then(task)
    tail = run.catch(() => undefined)
    return run
  }
}

/** Adds the id when absent, removes it when present. Returns a new set. */
export function toggleProjectSelection(selected: ReadonlySet<string>, projectId: string): Set<string> {
  const next = new Set(selected)
  if (next.has(projectId)) {
    next.delete(projectId)
  } else {
    next.add(projectId)
  }
  return next
}

/**
 * Selects every visible project, or clears the selection when all visible
 * projects are already selected.
 */
export function toggleAllProjectSelection(
  visibleIds: readonly string[],
  selected: ReadonlySet<string>,
): Set<string> {
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selected.has(id))
  return allSelected ? new Set() : new Set(visibleIds)
}
