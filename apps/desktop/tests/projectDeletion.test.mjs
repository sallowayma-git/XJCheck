import assert from "node:assert/strict"
import { test } from "node:test"

import {
  createSerialQueue,
  deleteFailureToast,
  excludeProjectIds,
  humanizeDeleteErrorMessage,
  settleProjectDeletes,
  toggleAllProjectSelection,
  toggleProjectSelection,
} from "../src/lib/projectDeletion.ts"

const projects = [
  { project_id: "a", project_name: "A" },
  { project_id: "b", project_name: "B" },
  { project_id: "c", project_name: "C" },
]

test("excludeProjectIds hides only the given ids and keeps original order", () => {
  const visible = excludeProjectIds(projects, new Set(["b"]))
  assert.deepEqual(visible.map((item) => item.project_id), ["a", "c"])
  assert.deepEqual(excludeProjectIds(projects, new Set()).map((item) => item.project_id), ["a", "b", "c"])
  // Returns a new array; the source list is untouched.
  assert.equal(projects.length, 3)
})

test("rollback is restoring the original order once the pending id is dropped", () => {
  const pending = new Set(["b"])
  assert.deepEqual(excludeProjectIds(projects, pending).map((item) => item.project_id), ["a", "c"])
  pending.delete("b")
  assert.deepEqual(excludeProjectIds(projects, pending).map((item) => item.project_id), ["a", "b", "c"])
})

test("settleProjectDeletes splits ids into succeeded and failed with reasons", () => {
  const settlement = settleProjectDeletes(["a", "b", "c"], [
    { project_id: "a", ok: true, not_found: false, error: null },
    { project_id: "b", ok: false, not_found: false, error: "分析进行中，请稍后再删除。" },
    { project_id: "c", ok: true, not_found: true, error: null },
  ])
  assert.deepEqual(settlement.succeededIds, ["a", "c"])
  assert.deepEqual(settlement.failed, [{ projectId: "b", message: "分析进行中，请稍后再删除。" }])
})

test("settleProjectDeletes treats a missing outcome as a failure with a fallback reason", () => {
  const settlement = settleProjectDeletes(["a", "b"], [{ project_id: "a", ok: true, not_found: false, error: null }])
  assert.deepEqual(settlement.succeededIds, ["a"])
  assert.equal(settlement.failed.length, 1)
  assert.equal(settlement.failed[0].projectId, "b")
  assert.ok(settlement.failed[0].message.length > 0)
})

test("settleProjectDeletes falls back to a generic reason when ok is false and error is empty", () => {
  const settlement = settleProjectDeletes(["a"], [{ project_id: "a", ok: false, not_found: false, error: "" }])
  assert.equal(settlement.failed[0].message, "删除项目记录失败。")
})

test("deleteFailureToast uses the plain form for a single project", () => {
  assert.equal(
    deleteFailureToast([{ projectId: "a", message: "没有访问权限" }], 1),
    "删除失败：没有访问权限",
  )
})

test("deleteFailureToast summarises a batch by count", () => {
  assert.equal(
    deleteFailureToast(
      [
        { projectId: "a", message: "分析进行中，请稍后再删除。" },
        { projectId: "b", message: "分析进行中，请稍后再删除。" },
      ],
      3,
    ),
    "2 个项目删除失败：分析进行中，请稍后再删除。",
  )
  assert.equal(deleteFailureToast([], 2), "")
})

test("humanizeDeleteErrorMessage maps a busy workspace to the retry hint", () => {
  assert.equal(
    humanizeDeleteErrorMessage("Workspace is active; analysis/cleanup must wait"),
    "分析进行中，请稍后再删除。",
  )
  assert.equal(humanizeDeleteErrorMessage("分析进行中，请稍后再删除"), "分析进行中，请稍后再删除。")
  assert.equal(humanizeDeleteErrorMessage("   "), "删除项目记录失败。")
  assert.equal(humanizeDeleteErrorMessage("access is denied"), "没有访问权限，请检查目录权限。")
})

test("createSerialQueue runs tasks strictly one after another", async () => {
  const enqueue = createSerialQueue()
  const events = []
  const slow = (label, ms) => async () => {
    events.push(`start:${label}`)
    await new Promise((resolve) => setTimeout(resolve, ms))
    events.push(`end:${label}`)
    return label
  }
  const results = await Promise.all([enqueue(slow("first", 20)), enqueue(slow("second", 1))])
  assert.deepEqual(results, ["first", "second"])
  assert.deepEqual(events, ["start:first", "end:first", "start:second", "end:second"])
})

test("createSerialQueue keeps running later tasks after one rejects", async () => {
  const enqueue = createSerialQueue()
  const failing = enqueue(async () => {
    throw new Error("boom")
  })
  const next = enqueue(async () => "ok")
  await assert.rejects(failing, /boom/)
  assert.equal(await next, "ok")
})

test("toggleProjectSelection adds and removes one id without mutating the input", () => {
  const original = new Set(["a"])
  const added = toggleProjectSelection(original, "b")
  assert.deepEqual([...added].sort(), ["a", "b"])
  assert.deepEqual([...original], ["a"])
  assert.deepEqual([...toggleProjectSelection(added, "a")], ["b"])
})

test("toggleAllProjectSelection selects all visible ids, then clears when all are selected", () => {
  const visible = ["a", "b"]
  assert.deepEqual([...toggleAllProjectSelection(visible, new Set(["a"]))].sort(), ["a", "b"])
  assert.deepEqual([...toggleAllProjectSelection(visible, new Set(["a", "b"]))], [])
  assert.deepEqual([...toggleAllProjectSelection([], new Set())], [])
})
