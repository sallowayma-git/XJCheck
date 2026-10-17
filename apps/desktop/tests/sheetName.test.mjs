import assert from "node:assert/strict"
import { test } from "node:test"

import { cleanText, resolveSheetName } from "../src/lib/issueLocations.ts"

test("sheet title wins and is trimmed", () => {
  const sheet = resolveSheetName({ sheetTitle: " 差动保护回路图\t", filename: "05 差动.dwg", sheetNo: "04" })
  assert.deepEqual(sheet, { name: "差动保护回路图", source: "title", page: "04" })
})

test("falls back to trimmed filename stem without extension", () => {
  const sheet = resolveSheetName({ sheetTitle: "\t  ", filename: " 端子排图.DWG\t", sheetNo: "04" })
  assert.deepEqual(sheet, { name: "端子排图", source: "file", page: "04" })
})

test("falls back to page number when no title or filename", () => {
  const sheet = resolveSheetName({ sheetTitle: "", filename: "  ", sheetNo: " 04 " })
  assert.deepEqual(sheet, { name: "第 04 页", source: "page", page: "04" })
})

test("falls back to unlabelled marker when nothing is known", () => {
  assert.deepEqual(resolveSheetName({}), { name: "未标注图纸", source: "none", page: "" })
})

test("cleanText trims tabs and ignores non-strings", () => {
  assert.equal(cleanText("\t04\t"), "04")
  assert.equal(cleanText(null), "")
  assert.equal(cleanText(undefined), "")
})
