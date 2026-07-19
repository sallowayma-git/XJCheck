import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import ts from "typescript"

const helperUrl = new URL("../src/lib/requestGeneration.ts", import.meta.url)
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
  beginRequest,
  createRequestGeneration,
  invalidateRequests,
  isCurrentRequest,
  shouldInvalidateScreenIntent,
} = helperModule

function deferred() {
  let resolve
  const promise = new Promise((next) => {
    resolve = next
  })
  return { promise, resolve }
}

test("only the latest request may commit an out-of-order result", async () => {
  const state = createRequestGeneration()
  const older = deferred()
  const newer = deferred()
  const commits = []

  async function run(promise) {
    const generation = beginRequest(state)
    const value = await promise
    if (isCurrentRequest(state, generation)) {
      commits.push(value)
    }
  }

  const olderRun = run(older.promise)
  const newerRun = run(newer.promise)
  newer.resolve("newer")
  await newerRun
  older.resolve("older")
  await olderRun

  assert.deepEqual(commits, ["newer"])
})

test("a stale finally block cannot clear the latest loading state", async () => {
  const state = createRequestGeneration()
  const older = deferred()
  const newer = deferred()
  let loadingRequest = null

  async function run(name, promise) {
    const generation = beginRequest(state)
    loadingRequest = name
    try {
      await promise
    } finally {
      if (isCurrentRequest(state, generation)) {
        loadingRequest = null
      }
    }
  }

  const olderRun = run("older", older.promise)
  const newerRun = run("newer", newer.promise)
  older.resolve("older")
  await olderRun
  assert.equal(loadingRequest, "newer")

  newer.resolve("newer")
  await newerRun
  assert.equal(loadingRequest, null)
})

test("invalidation prevents an abandoned request from committing", () => {
  const state = createRequestGeneration()
  const generation = beginRequest(state)

  invalidateRequests(state)

  assert.equal(isCurrentRequest(state, generation), false)
})

test("same-screen navigation preserves an active request intent", () => {
  assert.equal(shouldInvalidateScreenIntent("process", "process"), false)
  assert.equal(shouldInvalidateScreenIntent("process", "launch"), true)
  assert.equal(shouldInvalidateScreenIntent("process", "result"), true)
})
