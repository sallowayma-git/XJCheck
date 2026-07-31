import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"

import ts from "typescript"

const helperUrl = new URL("../src/lib/previewPan.ts", import.meta.url)
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
const { clampPreviewPan, computeContainSize, computePreviewPanBounds, normalizePreviewScale } = helperModule

test("preview scale is bounded to the supported interaction range", () => {
  assert.equal(normalizePreviewScale(undefined), 1)
  assert.equal(normalizePreviewScale(0.5), 1)
  assert.equal(normalizePreviewScale(2.1), 2.1)
  assert.equal(normalizePreviewScale(9), 2.3)
})

test("contain size preserves the SVG aspect ratio inside the viewport", () => {
  assert.deepEqual(computeContainSize({ width: 960, height: 540 }, { width: 400, height: 200 }), {
    width: 355.55555555555554,
    height: 200,
  })
  assert.deepEqual(computeContainSize({ width: 0, height: 540 }, { width: 400, height: 200 }), {
    width: 0,
    height: 0,
  })
})

test("pan bounds use scaled content overflow and clamp both axes", () => {
  const metrics = {
    viewport: { width: 400, height: 200 },
    content: { width: 355.55555555555554, height: 200 },
    scale: 2.1,
  }
  const bounds = computePreviewPanBounds(metrics)
  assert.ok(bounds.maxX > 170)
  assert.equal(bounds.maxY, 110)
  assert.deepEqual(clampPreviewPan({ x: 999, y: -999 }, metrics), {
    x: bounds.maxX,
    y: -110,
  })
})

test("content without overflow cannot be panned", () => {
  const metrics = {
    viewport: { width: 400, height: 200 },
    content: { width: 300, height: 100 },
    scale: 1,
  }
  assert.deepEqual(computePreviewPanBounds(metrics), { maxX: 0, maxY: 0 })
  assert.deepEqual(clampPreviewPan({ x: 20, y: -10 }, metrics), { x: 0, y: 0 })
})
