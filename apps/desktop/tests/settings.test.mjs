import assert from "node:assert/strict"
import { test } from "node:test"

import {
  DEFAULT_CACHE_CAP_BYTES,
  DEFAULT_CONVERT_WORKERS,
  DEFAULT_ODA_TIMEOUT_SECONDS,
  DEFAULT_STAGE_TELEMETRY_ENABLED,
  defaultSettings,
  normalizeSettings,
} from "../src/lib/settings.ts"

test("defaultSettings matches current sidecar behavior exactly", () => {
  const actual = defaultSettings()
  assert.equal(actual.convertWorkers, DEFAULT_CONVERT_WORKERS)
  assert.equal(actual.odaTimeoutSeconds, DEFAULT_ODA_TIMEOUT_SECONDS)
  assert.equal(actual.cacheCapBytes, DEFAULT_CACHE_CAP_BYTES)
  assert.equal(actual.stageTelemetryEnabled, DEFAULT_STAGE_TELEMETRY_ENABLED)
})

test("normalizing undefined returns defaults", () => {
  assert.deepEqual(normalizeSettings(undefined), defaultSettings())
  assert.deepEqual(normalizeSettings(null), defaultSettings())
  assert.deepEqual(normalizeSettings("garbage"), defaultSettings())
})

test("convert_workers rejects out-of-range and falls back to default", () => {
  assert.equal(normalizeSettings({ convertWorkers: -1 }).convertWorkers, DEFAULT_CONVERT_WORKERS)
  assert.equal(normalizeSettings({ convertWorkers: 17 }).convertWorkers, DEFAULT_CONVERT_WORKERS)
  assert.equal(normalizeSettings({ convertWorkers: 4 }).convertWorkers, 4)
  assert.equal(normalizeSettings({ convertWorkers: "8" }).convertWorkers, 8)
})

test("oda_timeout_seconds clamps to the 1..86400 contract", () => {
  assert.equal(normalizeSettings({ odaTimeoutSeconds: 0 }).odaTimeoutSeconds, DEFAULT_ODA_TIMEOUT_SECONDS)
  assert.equal(normalizeSettings({ odaTimeoutSeconds: 86401 }).odaTimeoutSeconds, DEFAULT_ODA_TIMEOUT_SECONDS)
  assert.equal(normalizeSettings({ odaTimeoutSeconds: 60 }).odaTimeoutSeconds, 60)
})

test("cacheCapBytes accepts null and parses integer strings", () => {
  assert.equal(normalizeSettings({ cacheCapBytes: null }).cacheCapBytes, null)
  assert.equal(normalizeSettings({ cacheCapBytes: "" }).cacheCapBytes, null)
  assert.equal(normalizeSettings({ cacheCapBytes: 1024 }).cacheCapBytes, 1024)
})

test("stageTelemetryEnabled coerces unknown to default false", () => {
  assert.equal(normalizeSettings({ stageTelemetryEnabled: true }).stageTelemetryEnabled, true)
  assert.equal(normalizeSettings({ stageTelemetryEnabled: "yes" }).stageTelemetryEnabled, false)
  assert.equal(normalizeSettings({ stageTelemetryEnabled: null }).stageTelemetryEnabled, false)
})