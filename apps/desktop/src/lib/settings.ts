/**
 * Persisted desktop settings that override sidecar runtime defaults.
 *
 * Every field MUST default to the *current* sidecar behavior, so a user that
 * never touches the Settings screen observes no change. The serialized override
 * file is only read by the Rust side and appended to spawned sidecars as
 * `--config <path>` when at least one override differs from the default; absence
 * of the file preserves the legacy `DEFAULT_CONFIG`-only path.
 */

export const SETTINGS_STORAGE_KEY = "xj-toolkit.settings"

/** Convert worker override; mirrors `configs/default.yml ingest.convert_workers`. 0 = auto. */
export const DEFAULT_CONVERT_WORKERS = 0

/**
 * ODA wall-time timeout in seconds; mirrors `configs.default.yml ingest.oda_timeout_seconds`.
 */
export const DEFAULT_ODA_TIMEOUT_SECONDS = 300

/**
 * Maximum bytes the desktop allows `ingest.ascii_stage_dir` (the on-disk ODA
 * staging cache) to grow to before pruning. `null` means no enforcement, which
 * matches the pre-settings behavior.
 */
export const DEFAULT_CACHE_CAP_BYTES = null

/**
 * Whether the sidecar emits `stage_telemetry` events during analysis. The
 * default of `false` matches the pre-settings event stream shape.
 */
export const DEFAULT_STAGE_TELEMETRY_ENABLED = false

export type DesktopSettings = {
  convertWorkers: number
  odaTimeoutSeconds: number
  cacheCapBytes: number | null
  stageTelemetryEnabled: boolean
}

export function defaultSettings(): DesktopSettings {
  return {
    convertWorkers: DEFAULT_CONVERT_WORKERS,
    odaTimeoutSeconds: DEFAULT_ODA_TIMEOUT_SECONDS,
    cacheCapBytes: DEFAULT_CACHE_CAP_BYTES,
    stageTelemetryEnabled: DEFAULT_STAGE_TELEMETRY_ENABLED,
  }
}

export function normalizeSettings(value: unknown): DesktopSettings {
  const fallback = defaultSettings()
  if (!value || typeof value !== "object") {
    return fallback
  }
  const raw = value as Record<string, unknown>
  const convertWorkers = parseInteger(raw.convertWorkers, fallback.convertWorkers)
  const odaTimeoutSeconds = parseInteger(raw.odaTimeoutSeconds, fallback.odaTimeoutSeconds)
  return {
    convertWorkers: clampInteger(convertWorkers, 0, 16, fallback.convertWorkers),
    odaTimeoutSeconds: clampInteger(odaTimeoutSeconds, 1, 86400, fallback.odaTimeoutSeconds),
    cacheCapBytes: parseNullableInteger(raw.cacheCapBytes, fallback.cacheCapBytes),
    stageTelemetryEnabled: parseBoolean(raw.stageTelemetryEnabled, fallback.stageTelemetryEnabled),
  }
}

export function loadSettings(): DesktopSettings {
  if (typeof window === "undefined") {
    return defaultSettings()
  }
  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY)
    if (!raw) {
      return defaultSettings()
    }
    return normalizeSettings(JSON.parse(raw))
  } catch {
    return defaultSettings()
  }
}

function settingsEqual(a: DesktopSettings, b: DesktopSettings): boolean {
  return (
    a.convertWorkers === b.convertWorkers &&
    a.odaTimeoutSeconds === b.odaTimeoutSeconds &&
    a.cacheCapBytes === b.cacheCapBytes &&
    a.stageTelemetryEnabled === b.stageTelemetryEnabled
  )
}

export function persistSettings(next: DesktopSettings): void {
  if (typeof window === "undefined") {
    return
  }
  try {
    if (settingsEqual(next, defaultSettings())) {
      // Reverting every override back to the defaults is equivalent to disabling
      // overrides; drop the localStorage entry so the Rust side treats the
      // override file as absent and reuses DEFAULT_CONFIG verbatim.
      window.localStorage.removeItem(SETTINGS_STORAGE_KEY)
    } else {
      window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(next))
    }
  } catch {
    // Keep the in-memory preference when storage is unavailable.
  }
}

function parseInteger(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value)
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number.parseInt(value, 10)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return fallback
}

function parseNullableInteger(value: unknown, fallback: number | null): number | null {
  if (value === null || value === undefined) {
    return fallback
  }
  if (typeof value === "string" && value.trim() === "") {
    return fallback
  }
  const parsed = parseInteger(value, 0)
  return Number.isFinite(parsed) ? Math.max(0, parsed) : fallback
}

function clampInteger(value: number, min: number, max: number, fallback: number): number {
  if (!Number.isFinite(value)) {
    return fallback
  }
  if (value < min || value > max) {
    return fallback
  }
  return value
}

function parseBoolean(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") {
    return value
  }
  return fallback
}