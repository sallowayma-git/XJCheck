import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import ts from "typescript"

const helperUrl = new URL("../src/lib/previewPolicy.ts", import.meta.url)
const source = readFileSync(helperUrl, "utf8")
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: helperUrl.pathname,
  reportDiagnostics: true,
})
const errors = (transpiled.diagnostics ?? []).filter((diagnostic) => diagnostic.category === ts.DiagnosticCategory.Error)
assert.deepEqual(errors, [])

const helperModule = await import(`data:text/javascript;base64,${Buffer.from(transpiled.outputText).toString("base64")}`)
const {
  createPreviewContextKey,
  isPreviewOutputCurrent,
  parsePreviewMode,
  resolvePreviewEmptyState,
  shouldRenderPreview,
} = helperModule

test("preview mode parsing defaults invalid stored values to auto", () => {
  assert.equal(parsePreviewMode(null), "auto")
  assert.equal(parsePreviewMode("unexpected"), "auto")
  assert.equal(parsePreviewMode("auto"), "auto")
  assert.equal(parsePreviewMode("manual-only"), "manual-only")
  assert.equal(parsePreviewMode("off"), "off")
})

test("preview policy admits only explicit manual generations in manual mode", () => {
  assert.equal(shouldRenderPreview("auto", 0, 0), true)
  assert.equal(shouldRenderPreview("manual-only", 0, 0), false)
  assert.equal(shouldRenderPreview("manual-only", 2, 1), true)
  assert.equal(shouldRenderPreview("off", 2, 1), false)
})

test("preview context keys ignore object identity but change with target identity", () => {
  const base = { revision: 1, runId: "run-1", projectId: "project-1", issueId: "issue-1", sheetId: "S1", lineGroupId: "L1" }
  assert.equal(createPreviewContextKey({ ...base }), createPreviewContextKey({ ...base }))
  assert.notEqual(createPreviewContextKey(base), createPreviewContextKey({ ...base, issueId: "issue-2" }))
  assert.notEqual(createPreviewContextKey(base), createPreviewContextKey({ ...base, sheetId: "S2" }))
  assert.notEqual(createPreviewContextKey(base), createPreviewContextKey({ ...base, lineGroupId: "L2" }))
  assert.notEqual(createPreviewContextKey(base), createPreviewContextKey({ ...base, revision: 2 }))
})

test("preview output is rendered only for the current context", () => {
  assert.equal(isPreviewOutputCurrent("key-1", "key-1"), true)
  assert.equal(isPreviewOutputCurrent("key-1", "key-2"), false)
  assert.equal(isPreviewOutputCurrent(null, "key-1"), false)
})

test("preview empty-state ordering keeps errors visible in manual mode", () => {
  assert.equal(
    resolvePreviewEmptyState({ hasIssue: true, isLoading: true, mode: "manual-only", hasError: true, hasPreviewOptions: true }),
    "loading",
  )
  assert.equal(
    resolvePreviewEmptyState({ hasIssue: true, isLoading: false, mode: "off", hasError: true, hasPreviewOptions: true }),
    "off",
  )
  assert.equal(
    resolvePreviewEmptyState({ hasIssue: true, isLoading: false, mode: "manual-only", hasError: true, hasPreviewOptions: true }),
    "error",
  )
  assert.equal(
    resolvePreviewEmptyState({ hasIssue: true, isLoading: false, mode: "manual-only", hasError: false, hasPreviewOptions: true }),
    "manual-only",
  )
})
